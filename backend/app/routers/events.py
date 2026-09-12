import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import (ActivityRestriction, BlacklistEntry, Compensation, Event,
                      EventParticipant, EventUpdate, FacilityRectification,
                      Incident, MedicalRecord, OperationRecord, Pet, User)
from ..serializers import (COMPENSATION_STATUS, RECTIFICATION_STATUS,
                           blacklist_dict, event_dict, incident_dict,
                           restriction_dict, user_dict)

router = APIRouter(prefix="/events", tags=["事件协同"])


# ---------------- 公共工具 ----------------

def add_update(db: Session, event_id: int, actor_id: int, action: str, content: str = ""):
    db.add(EventUpdate(event_id=event_id, actor_id=actor_id, action=action, content=content))


def create_event_internal(db: Session, creator: User, title: str, event_type: str,
                          priority: str = "medium", zone_id: int | None = None,
                          pet_id: int | None = None, owner_id: int | None = None,
                          description: str = "") -> Event:
    """创建事件并把巡场、园区管理、宠物主人、合作医院、客服串到同一事件。"""
    ev = Event(code="E" + uuid.uuid4().hex[:8].upper(), title=title, event_type=event_type,
               priority=priority, zone_id=zone_id, pet_id=pet_id, owner_id=owner_id,
               description=description, created_by=creator.id)
    db.add(ev)
    db.flush()

    # 先汇总再落库（去重）：创建者/主人可能同时属于某个职能角色，
    # 逐个查询插入在 autoflush=False 下会漏掉未落库的行，导致唯一约束冲突
    participants = {creator.id: creator.role}
    if owner_id:
        participants.setdefault(owner_id, "owner")
    # 自动串联巡场、园区管理、合作医院、客服（无论从哪个入口创建，五方角色必须齐全）
    for role in ("patrol", "manager", "hospital", "service"):
        for u in db.query(User).filter(User.role == role).all():
            participants.setdefault(u.id, role)
    for uid, role in participants.items():
        db.add(EventParticipant(event_id=ev.id, user_id=uid, participant_role=role))

    add_update(db, ev.id, creator.id, "创建事件",
               "事件创建，已通知巡场、园区管理、宠物主人、合作医院与客服协同处置")
    return ev


def get_event_or_404(db: Session, event_id: int) -> Event:
    ev = db.get(Event, event_id)
    if not ev:
        raise HTTPException(404, "事件不存在")
    return ev


def check_event_visible(db: Session, user: User, event_id: int):
    if user.role in ("manager", "admin"):
        return
    joined = db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == user.id).first()
    if not joined:
        raise HTTPException(403, "您不是该事件的协同方，无权查看")


# ---------------- 事件列表 / 创建 / 详情 ----------------

@router.get("")
def list_events(status: str = "", event_type: str = "", db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    q = db.query(Event)
    if user.role not in ("manager", "admin"):
        joined = db.query(EventParticipant.event_id).filter(EventParticipant.user_id == user.id)
        q = q.filter(Event.id.in_(joined))
    if status:
        q = q.filter(Event.status == status)
    if event_type:
        q = q.filter(Event.event_type == event_type)
    return [event_dict(e, db) for e in q.order_by(Event.created_at.desc()).limit(200).all()]


class EventIn(BaseModel):
    title: str
    event_type: str
    priority: str = "medium"
    zone_id: int | None = None
    pet_id: int | None = None
    description: str = ""


@router.post("")
def create_event(data: EventIn, db: Session = Depends(get_db),
                 user: User = Depends(require_roles("patrol", "gate", "manager", "admin"))):
    owner_id = None
    if data.pet_id:
        pet = db.get(Pet, data.pet_id)
        if not pet:
            raise HTTPException(404, "宠物不存在")
        owner_id = pet.owner_id
    ev = create_event_internal(db, creator=user, title=data.title, event_type=data.event_type,
                               priority=data.priority, zone_id=data.zone_id,
                               pet_id=data.pet_id, owner_id=owner_id,
                               description=data.description)
    db.commit()
    return event_dict(ev, db)


@router.get("/{event_id}")
def event_detail(event_id: int, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    ev = get_event_or_404(db, event_id)
    check_event_visible(db, user, event_id)

    participants = db.query(EventParticipant).filter(EventParticipant.event_id == event_id).all()
    updates = db.query(EventUpdate).filter(EventUpdate.event_id == event_id).order_by(EventUpdate.created_at).all()
    medical = db.query(MedicalRecord).filter(MedicalRecord.event_id == event_id).all()
    comps = db.query(Compensation).filter(Compensation.event_id == event_id).all()
    bl = db.query(BlacklistEntry).filter(BlacklistEntry.event_id == event_id).all()
    restr = db.query(ActivityRestriction).filter(ActivityRestriction.event_id == event_id).all()
    rects = db.query(FacilityRectification).filter(FacilityRectification.event_id == event_id).all()
    incidents = db.query(Incident).filter(Incident.event_id == event_id).all()

    return {
        "event": event_dict(ev, db),
        "participants": [{
            "id": p.id, "participant_role": p.participant_role,
            "user": user_dict(p.user),
        } for p in participants],
        "updates": [{
            "id": u.id, "action": u.action, "content": u.content,
            "actor": user_dict(u.actor),
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
        } for u in updates],
        "incidents": [incident_dict(i) for i in incidents],
        "medical_records": [{
            "id": m.id, "patient_type": m.patient_type, "patient_name": m.patient_name,
            "pet_id": m.pet_id, "pet_name": m.pet.name if m.pet else "",
            "injury_desc": m.injury_desc, "treatment": m.treatment,
            "cost": float(m.cost or 0),
            "hospital": m.hospital_user.name if m.hospital_user else "",
            "treated_at": m.treated_at.strftime("%Y-%m-%d %H:%M") if m.treated_at else "",
        } for m in medical],
        "compensations": [{
            "id": c.id, "payer_name": c.payer.name if c.payer else "",
            "payee_name": c.payee_name, "amount": float(c.amount), "reason": c.reason,
            "status": c.status, "status_label": COMPENSATION_STATUS.get(c.status, c.status),
            "handler": c.handler.name if c.handler else "",
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "",
        } for c in comps],
        "blacklist": [blacklist_dict(b) for b in bl],
        "restrictions": [restriction_dict(r) for r in restr],
        "rectifications": [{
            "id": r.id, "zone_name": r.zone.name if r.zone else "", "issue": r.issue,
            "action": r.action, "status": r.status,
            "status_label": RECTIFICATION_STATUS.get(r.status, r.status),
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
        } for r in rects],
    }


# ---------------- 协同：进展 / 状态 ----------------

class UpdateIn(BaseModel):
    action: str
    content: str = ""


@router.post("/{event_id}/updates")
def post_update(event_id: int, data: UpdateIn, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    ev = get_event_or_404(db, event_id)
    check_event_visible(db, user, event_id)
    if ev.status == "closed":
        raise HTTPException(400, "事件已关闭，无法追加进展")
    add_update(db, event_id, user.id, data.action, data.content)
    db.commit()
    return {"ok": True}


@router.post("/{event_id}/status")
def set_status(event_id: int, db: Session = Depends(get_db),
               user: User = Depends(require_roles("manager", "admin"))):
    ev = get_event_or_404(db, event_id)
    if ev.status == "open":
        ev.status = "processing"
        add_update(db, event_id, user.id, "开始处理", "园区管理已介入处理")
    db.commit()
    return event_dict(ev, db)


# ---------------- 医疗处置（合作医院） ----------------

class MedicalIn(BaseModel):
    pet_id: int | None = None
    patient_type: str = "pet"
    patient_name: str = ""
    injury_desc: str
    treatment: str = ""
    cost: float = 0


@router.post("/{event_id}/medical")
def add_medical(event_id: int, data: MedicalIn, db: Session = Depends(get_db),
                user: User = Depends(require_roles("hospital", "manager", "admin"))):
    ev = get_event_or_404(db, event_id)
    if ev.status == "closed":
        raise HTTPException(400, "事件已关闭")
    rec = MedicalRecord(event_id=event_id, pet_id=data.pet_id, patient_type=data.patient_type,
                        patient_name=data.patient_name, hospital_user_id=user.id,
                        injury_desc=data.injury_desc, treatment=data.treatment, cost=data.cost)
    db.add(rec)
    add_update(db, event_id, user.id, "医疗处置登记",
               f"{data.patient_name}：{data.injury_desc}；处置：{data.treatment}；费用 {data.cost} 元")
    db.commit()
    return {"ok": True, "id": rec.id}


# ---------------- 赔付（客服） ----------------

class CompensationIn(BaseModel):
    payer_owner_id: int | None = None
    payee_name: str
    amount: float
    reason: str = ""


@router.post("/{event_id}/compensations")
def add_compensation(event_id: int, data: CompensationIn, db: Session = Depends(get_db),
                     user: User = Depends(require_roles("service", "manager", "admin"))):
    ev = get_event_or_404(db, event_id)
    if ev.status == "closed":
        raise HTTPException(400, "事件已关闭")
    c = Compensation(event_id=event_id, payer_owner_id=data.payer_owner_id,
                     payee_name=data.payee_name, amount=data.amount,
                     reason=data.reason, handled_by=user.id)
    db.add(c)
    add_update(db, event_id, user.id, "赔付登记",
               f"赔付 {data.payee_name} {data.amount} 元：{data.reason}")
    db.commit()
    return {"ok": True, "id": c.id}


class CompensationUpdate(BaseModel):
    status: str  # paid/rejected/pending


@router.put("/compensations/{comp_id}")
def update_compensation(comp_id: int, data: CompensationUpdate, db: Session = Depends(get_db),
                        user: User = Depends(require_roles("service", "manager", "admin"))):
    c = db.get(Compensation, comp_id)
    if not c:
        raise HTTPException(404, "赔付记录不存在")
    if data.status not in ("paid", "rejected", "pending"):
        raise HTTPException(400, "状态不合法")
    c.status = data.status
    if data.status in ("paid", "rejected"):
        c.resolved_at = datetime.utcnow()
    add_update(db, c.event_id, user.id, "赔付状态更新",
               f"赔付单 #{c.id} 更新为 {COMPENSATION_STATUS.get(data.status)}")
    db.commit()
    return {"ok": True}


# ---------------- 黑名单 / 活动资格（园区管理） ----------------

class BlacklistIn(BaseModel):
    pet_id: int | None = None
    owner_id: int | None = None
    level: str = "warning"
    reason: str = ""


@router.post("/{event_id}/blacklist")
def add_blacklist(event_id: int, data: BlacklistIn, db: Session = Depends(get_db),
                  user: User = Depends(require_roles("manager", "admin"))):
    ev = get_event_or_404(db, event_id)
    if not data.pet_id and not data.owner_id:
        raise HTTPException(400, "需指定宠物或主人")
    if data.level not in ("warning", "restricted", "banned"):
        raise HTTPException(400, "级别不合法")
    b = BlacklistEntry(pet_id=data.pet_id, owner_id=data.owner_id, level=data.level,
                       reason=data.reason, event_id=event_id, created_by=user.id)
    db.add(b)
    db.flush()
    target = f"宠物#{data.pet_id}" if data.pet_id else f"主人#{data.owner_id}"
    add_update(db, event_id, user.id, "黑名单处置", f"{target} 列入黑名单（{data.level}）：{data.reason}")
    db.add(OperationRecord(record_type="blacklist", title=f"黑名单新增（{data.level}）",
                           content=f"事件 {ev.code}：{target}，原因：{data.reason}",
                           related_event_id=event_id, created_by=user.id))
    db.commit()
    return {"ok": True, "id": b.id}


class RestrictionIn(BaseModel):
    pet_id: int
    restriction_type: str
    reason: str = ""


@router.post("/{event_id}/restrictions")
def add_restriction(event_id: int, data: RestrictionIn, db: Session = Depends(get_db),
                    user: User = Depends(require_roles("manager", "admin"))):
    ev = get_event_or_404(db, event_id)
    valid = ("leash_only", "muzzle_required", "no_activity_zone", "no_social_zone", "activity_ban")
    if data.restriction_type not in valid:
        raise HTTPException(400, "限制类型不合法")
    r = ActivityRestriction(pet_id=data.pet_id, restriction_type=data.restriction_type,
                            reason=data.reason, event_id=event_id)
    db.add(r)
    add_update(db, event_id, user.id, "活动资格限制",
               f"宠物#{data.pet_id} 新增限制 {data.restriction_type}：{data.reason}")
    db.add(OperationRecord(record_type="restriction", title="活动资格限制",
                           content=f"事件 {ev.code}：宠物#{data.pet_id} {data.restriction_type}，原因：{data.reason}",
                           related_event_id=event_id, created_by=user.id))
    db.commit()
    return {"ok": True, "id": r.id}


# ---------------- 设施整改（园区管理） ----------------

class RectificationIn(BaseModel):
    zone_id: int | None = None
    issue: str
    action: str = ""


@router.post("/{event_id}/rectifications")
def add_rectification(event_id: int, data: RectificationIn, db: Session = Depends(get_db),
                      user: User = Depends(require_roles("manager", "admin"))):
    ev = get_event_or_404(db, event_id)
    if ev.status == "closed":
        raise HTTPException(400, "事件已关闭，无法再登记整改")
    r = FacilityRectification(event_id=event_id, zone_id=data.zone_id,
                              issue=data.issue, action=data.action)
    db.add(r)
    add_update(db, event_id, user.id, "设施整改登记", f"问题：{data.issue}；措施：{data.action}")
    db.add(OperationRecord(record_type="rectification", title="设施整改登记",
                           content=f"事件 {ev.code}：{data.issue} -> {data.action}",
                           related_event_id=event_id, created_by=user.id))
    db.commit()
    return {"ok": True, "id": r.id}


class RectificationUpdate(BaseModel):
    status: str  # pending/in_progress/done


@router.put("/rectifications/{rect_id}")
def update_rectification(rect_id: int, data: RectificationUpdate, db: Session = Depends(get_db),
                         user: User = Depends(require_roles("manager", "admin"))):
    r = db.get(FacilityRectification, rect_id)
    if not r:
        raise HTTPException(404, "整改记录不存在")
    ev = db.get(Event, r.event_id)
    if ev and ev.status == "closed":
        raise HTTPException(400, "事件已关闭，整改状态不可再变更")
    if data.status not in ("pending", "in_progress", "done"):
        raise HTTPException(400, "状态不合法")
    r.status = data.status
    if data.status == "done":
        r.completed_at = datetime.utcnow()
    add_update(db, r.event_id, user.id, "整改状态更新",
               f"整改单 #{r.id} 更新为 {RECTIFICATION_STATUS.get(data.status)}")
    db.commit()
    return {"ok": True}


# ---------------- 关闭事件 ----------------

class CloseIn(BaseModel):
    resolution_summary: str


@router.post("/{event_id}/close")
def close_event(event_id: int, data: CloseIn, db: Session = Depends(get_db),
                user: User = Depends(require_roles("manager", "admin"))):
    ev = get_event_or_404(db, event_id)
    if ev.status == "closed":
        raise HTTPException(400, "事件已关闭")
    ev.status = "closed"
    ev.closed_at = datetime.utcnow()
    ev.closed_by = user.id
    ev.resolution_summary = data.resolution_summary
    add_update(db, event_id, user.id, "事件关闭", data.resolution_summary)

    # 处置结果归档：伤情 / 赔付 / 黑名单 / 活动资格 / 设施整改 -> 园区运营记录
    medical = db.query(MedicalRecord).filter(MedicalRecord.event_id == event_id).all()
    comps = db.query(Compensation).filter(Compensation.event_id == event_id).all()
    bl = db.query(BlacklistEntry).filter(BlacklistEntry.event_id == event_id, BlacklistEntry.active.is_(True)).all()
    restr = db.query(ActivityRestriction).filter(ActivityRestriction.event_id == event_id, ActivityRestriction.active.is_(True)).all()
    rects = db.query(FacilityRectification).filter(FacilityRectification.event_id == event_id).all()

    parts = [f"事件 {ev.code}（{ev.title}）关闭归档："]
    parts.append(f"伤情 {len(medical)} 条（费用合计 {sum(float(m.cost or 0) for m in medical):.2f} 元）")
    parts.append(f"赔付 {len(comps)} 笔（金额合计 {sum(float(c.amount or 0) for c in comps):.2f} 元）")
    parts.append(f"生效黑名单 {len(bl)} 条、活动资格限制 {len(restr)} 条、设施整改 {len(rects)} 项")
    parts.append(f"处置结论：{data.resolution_summary}")
    db.add(OperationRecord(record_type="event_closure", title=f"事件 {ev.code} 关闭归档",
                           content="；".join(parts), related_event_id=event_id,
                           created_by=user.id))
    db.commit()
    return event_dict(ev, db)
