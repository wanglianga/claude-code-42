import os
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import (ActivityRestriction, BlacklistEntry, Compensation,
                      ConflictParty, ConflictPhoto, EntryCheck, Event,
                      EventEvidence, EventParticipant, EventUpdate,
                      FacilityRectification, Incident, MedicalRecord,
                      OperationRecord, Pet, Reservation, Settlement, User)
from ..serializers import (COMPENSATION_STATUS, EVIDENCE_TYPES,
                           RECTIFICATION_STATUS, SANCTION_LABELS, SIZE_LABELS,
                           VACCINE_LABELS, blacklist_dict, entry_check_dict,
                           event_dict, incident_dict, restriction_dict,
                           user_dict)

router = APIRouter(prefix="/events", tags=["事件协同"])


# ---------------- 公共工具 ----------------

def add_update(db: Session, event_id: int, actor_id: int, action: str, content: str = ""):
    db.add(EventUpdate(event_id=event_id, actor_id=actor_id, action=action, content=content))


def create_event_internal(db: Session, creator: User, title: str, event_type: str,
                          priority: str = "medium", zone_id: int | None = None,
                          pet_id: int | None = None, owner_id: int | None = None,
                          description: str = "",
                          extra_owner_ids: list[int] | None = None) -> Event:
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
    for oid in (extra_owner_ids or []):
        participants.setdefault(oid, "owner")
    # 自动串联巡场、园区管理、合作医院、客服（无论从哪个入口创建，五方角色必须齐全）
    for role in ("patrol", "manager", "hospital", "service"):
        for u in db.query(User).filter(User.role == role).all():
            participants.setdefault(u.id, role)
    for uid, role in participants.items():
        db.add(EventParticipant(event_id=ev.id, user_id=uid, participant_role=role))

    add_update(db, ev.id, creator.id, "创建事件",
               "事件创建，已通知巡场、园区管理、宠物主人、合作医院与客服协同处置")
    return ev


def _latest_entry_check(db: Session, pet_id: int) -> EntryCheck | None:
    return (db.query(EntryCheck).join(Reservation, EntryCheck.reservation_id == Reservation.id)
            .filter(Reservation.pet_id == pet_id)
            .order_by(EntryCheck.check_time.desc()).first())


def create_conflict_parties(db: Session, ev: Event, pet_ids: list[int]):
    """为两只宠物的冲突建立双方档案：绑定当日入园核验状态与牵引情况，便于快速定位双方。"""
    for pid in pet_ids:
        pet = db.get(Pet, pid)
        if not pet:
            continue
        exists = db.query(ConflictParty).filter(
            ConflictParty.event_id == ev.id, ConflictParty.pet_id == pid).first()
        if exists:
            continue
        check = _latest_entry_check(db, pid)
        db.add(ConflictParty(
            event_id=ev.id, pet_id=pid, owner_id=pet.owner_id,
            entry_check_id=check.id if check else None,
            leash_compliant=check.leash_ok if check else True))
    db.flush()


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


def _conflict_party_dict(db: Session, p: ConflictParty) -> dict:
    pet = p.pet
    owner = p.owner
    return {
        "id": p.id, "pet_id": p.pet_id,
        "pet_name": pet.name if pet else "", "breed": pet.breed if pet else "",
        "size_label": SIZE_LABELS.get(pet.size_category, "") if pet else "",
        "owner_id": p.owner_id,
        "owner_name": owner.name if owner else "",
        "owner_phone": owner.phone if owner else "",
        "leash_required": pet.leash_required if pet else True,
        "leash_compliant": p.leash_compliant,
        "vaccine_label": VACCINE_LABELS.get(pet.vaccine_status, "") if pet else "",
        "attack_history": pet.attack_history if pet else False,
        "entry_check": entry_check_dict(p.entry_check) if p.entry_check else None,
        "owner_statement": p.owner_statement,
        "statement_at": p.statement_at.strftime("%Y-%m-%d %H:%M") if p.statement_at else None,
        "responsibility_percent": p.responsibility_percent,
        "determination": p.determination,
        "entry_sanction": p.entry_sanction,
        "entry_sanction_label": SANCTION_LABELS.get(p.entry_sanction, p.entry_sanction),
    }


def conflict_dict(db: Session, ev: Event) -> dict | None:
    parties = db.query(ConflictParty).filter(ConflictParty.event_id == ev.id).all()
    if not parties:
        return None
    photos = db.query(ConflictPhoto).filter(ConflictPhoto.event_id == ev.id).all()
    settlement = (db.query(Settlement).filter(Settlement.event_id == ev.id)
                  .order_by(Settlement.id.desc()).first())
    return {
        "location": ev.location,
        "parties": [_conflict_party_dict(db, p) for p in parties],
        "photos": [{
            "id": ph.id, "url": f"/api/uploads/{ph.filename}", "note": ph.note,
            "uploader": ph.uploader.name if ph.uploader else "",
            "created_at": ph.created_at.strftime("%Y-%m-%d %H:%M") if ph.created_at else "",
        } for ph in photos],
        "settlement": {
            "id": settlement.id, "medical_total": float(settlement.medical_total or 0),
            "detail": settlement.detail,
            "created_at": settlement.created_at.strftime("%Y-%m-%d %H:%M") if settlement.created_at else "",
        } if settlement else None,
    }


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
    evidence = db.query(EventEvidence).filter(EventEvidence.event_id == event_id).order_by(EventEvidence.created_at).all()

    return {
        "event": event_dict(ev, db),
        "conflict": conflict_dict(db, ev),
        "evidence": [{
            "id": e.id, "evidence_type": e.evidence_type,
            "type_label": EVIDENCE_TYPES.get(e.evidence_type, e.evidence_type),
            "title": e.title, "content": e.content,
            "url": f"/api/uploads/{e.filename}" if e.filename else None,
            "creator": e.creator.name if e.creator else "",
            "created_at": e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else "",
        } for e in evidence],
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


# ---------------- 冲突责任判断 ----------------

class ConflictSetupIn(BaseModel):
    pet_id: int
    related_pet_id: int
    location: str = ""


@router.post("/{event_id}/conflict/parties")
def setup_conflict(event_id: int, data: ConflictSetupIn, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("patrol", "manager", "admin"))):
    """手动为事件建立双方冲突档案（如未从巡场记录升级的事件）。"""
    ev = get_event_or_404(db, event_id)
    if ev.status == "closed":
        raise HTTPException(400, "事件已关闭")
    if data.pet_id == data.related_pet_id:
        raise HTTPException(400, "双方宠物不能相同")
    existing = db.query(ConflictParty).filter(ConflictParty.event_id == event_id).count()
    if existing:
        raise HTTPException(400, "该事件已建立冲突档案")
    pets = []
    for pid in (data.pet_id, data.related_pet_id):
        pet = db.get(Pet, pid)
        if not pet:
            raise HTTPException(404, f"宠物 #{pid} 不存在")
        pets.append(pet)
    create_conflict_parties(db, ev, [p.id for p in pets])
    # 双方主人加入协同
    for pet in pets:
        joined = db.query(EventParticipant).filter(
            EventParticipant.event_id == event_id,
            EventParticipant.user_id == pet.owner_id).first()
        if not joined:
            db.add(EventParticipant(event_id=event_id, user_id=pet.owner_id,
                                    participant_role="owner"))
    if data.location:
        ev.location = data.location
    add_update(db, event_id, user.id, "建立冲突档案",
               f"冲突双方：{pets[0].name} vs {pets[1].name}，已绑定入园状态与主人联系方式")
    db.commit()
    return {"ok": True}


class StatementIn(BaseModel):
    statement: str


@router.post("/{event_id}/conflict/statement")
def submit_statement(event_id: int, data: StatementIn, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """冲突一方的主人提交陈述。"""
    ev = get_event_or_404(db, event_id)
    if ev.status == "closed":
        raise HTTPException(400, "事件已关闭")
    party = db.query(ConflictParty).filter(
        ConflictParty.event_id == event_id,
        ConflictParty.owner_id == user.id).first()
    if not party:
        raise HTTPException(403, "您不是该冲突的当事主人")
    if not data.statement.strip():
        raise HTTPException(400, "陈述内容不能为空")
    party.owner_statement = data.statement.strip()
    party.statement_at = datetime.utcnow()
    add_update(db, event_id, user.id, "主人陈述", data.statement.strip())
    db.commit()
    return {"ok": True}


@router.post("/{event_id}/conflict/photos")
async def upload_photo(event_id: int, file: UploadFile = File(...),
                       db: Session = Depends(get_db),
                       user: User = Depends(require_roles("patrol", "manager", "admin"))):
    """巡场员上传现场照片。"""
    ev = get_event_or_404(db, event_id)
    if ev.status == "closed":
        raise HTTPException(400, "事件已关闭")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "仅支持图片文件")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过 5MB")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1].lower() or ".jpg"
    fname = f"ev{event_id}_{uuid.uuid4().hex[:10]}{ext}"
    with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
        f.write(content)
    photo = ConflictPhoto(event_id=event_id, filename=fname,
                          note=file.filename or "", uploaded_by=user.id)
    db.add(photo)
    add_update(db, event_id, user.id, "上传现场照片", file.filename or fname)
    db.commit()
    return {"ok": True, "url": f"/api/uploads/{fname}"}


def _liability_suggestion(db: Session, ev: Event, parties: list[ConflictParty]):
    """规则建议：未拴绳 / 攻击史 / 疫苗核验未过 / 违规入园 / 违反活动限制 加分。"""
    scores = {}
    reasons = {}
    for p in parties:
        pet = p.pet
        score = 0
        rs = []
        if not p.leash_compliant:
            score += 25
            rs.append("冲突时未按规定拴牵引绳 +25")
        if pet and pet.attack_history:
            score += 15
            rs.append("有攻击史 +15")
        chk = p.entry_check
        if chk and not chk.vaccine_ok:
            score += 10
            rs.append("入园疫苗核验未通过 +10")
        if chk and chk.result == "failed":
            score += 10
            rs.append("核验未通过仍入园 +10")
        if pet and ev.zone:
            violated = db.query(ActivityRestriction).filter(
                ActivityRestriction.pet_id == pet.id,
                ActivityRestriction.active.is_(True)).all()
            for r in violated:
                if (r.restriction_type == "no_social_zone" and ev.zone.code == "social") or \
                   (r.restriction_type == "no_activity_zone" and ev.zone.code == "activity") or \
                   r.restriction_type == "activity_ban":
                    score += 20
                    rs.append(f"违反生效限制（{r.restriction_type}）进入该区域 +20")
                    break
        scores[p.pet_id] = score
        reasons[p.pet_id] = rs
    total = sum(scores.values())
    result = []
    for p in parties:
        if total == 0:
            pct = 50
        else:
            pct = round(scores[p.pet_id] / total * 100)
            pct = max(10, min(90, pct))
        result.append({
            "pet_id": p.pet_id, "pet_name": p.pet.name if p.pet else "",
            "suggested_percent": pct, "reasons": reasons[p.pet_id],
        })
    # 保证合计 100
    if len(result) == 2:
        result[1]["suggested_percent"] = 100 - result[0]["suggested_percent"]
    return result


@router.get("/{event_id}/conflict/suggestion")
def liability_suggestion(event_id: int, db: Session = Depends(get_db),
                         user: User = Depends(require_roles("manager", "admin"))):
    ev = get_event_or_404(db, event_id)
    parties = db.query(ConflictParty).filter(ConflictParty.event_id == event_id).all()
    if len(parties) != 2:
        raise HTTPException(400, "该事件未建立双方冲突档案")
    return {"parties": _liability_suggestion(db, ev, parties)}


class DeterminePartyIn(BaseModel):
    pet_id: int
    responsibility_percent: int
    entry_sanction: str = "none"  # none/warning/restricted/banned
    determination: str = ""


class DetermineIn(BaseModel):
    parties: list[DeterminePartyIn]


@router.post("/{event_id}/conflict/determine")
def determine_liability(event_id: int, data: DetermineIn, db: Session = Depends(get_db),
                        user: User = Depends(require_roles("manager", "admin"))):
    """管理人员根据规则判定双方责任比例、赔付与是否限制入园；结果影响双方后续预约权限。"""
    ev = get_event_or_404(db, event_id)
    if ev.status == "closed":
        raise HTTPException(400, "事件已关闭，无法再认定责任")
    parties = db.query(ConflictParty).filter(ConflictParty.event_id == event_id).all()
    if len(parties) != 2 or len(data.parties) != 2:
        raise HTTPException(400, "需要双方冲突档案与两方认定结果")
    if sum(p.responsibility_percent for p in data.parties) != 100:
        raise HTTPException(400, "双方责任比例合计必须为 100")
    for p in data.parties:
        if not (0 <= p.responsibility_percent <= 100):
            raise HTTPException(400, "责任比例须在 0-100 之间")
        if p.entry_sanction not in SANCTION_LABELS:
            raise HTTPException(400, "处置级别不合法")

    by_pet = {p.pet_id: p for p in parties}
    for inp in data.parties:
        party = by_pet.get(inp.pet_id)
        if not party:
            raise HTTPException(400, f"宠物 #{inp.pet_id} 不属于该冲突")
        party.responsibility_percent = inp.responsibility_percent
        party.entry_sanction = inp.entry_sanction
        party.determination = inp.determination
        pet_name = party.pet.name if party.pet else f"#{inp.pet_id}"
        # 限制入园/拉黑/警告 -> 黑名单，影响后续预约与活动报名
        if inp.entry_sanction != "none":
            db.add(BlacklistEntry(
                pet_id=inp.pet_id, owner_id=party.owner_id, level=inp.entry_sanction,
                reason=f"冲突责任认定（{inp.responsibility_percent}%）：{inp.determination}",
                event_id=event_id, created_by=user.id))
            db.add(OperationRecord(
                record_type="blacklist", title=f"责任认定黑名单（{SANCTION_LABELS[inp.entry_sanction]}）",
                content=f"事件 {ev.code}：{pet_name} 责任 {inp.responsibility_percent}%，{inp.determination}",
                related_event_id=event_id, created_by=user.id))
        add_update(db, event_id, user.id, "责任认定",
                   f"{pet_name} 责任 {inp.responsibility_percent}%，处置：{SANCTION_LABELS[inp.entry_sanction]}。{inp.determination}")
    db.commit()
    return {"ok": True}


@router.post("/{event_id}/settlement")
def create_settlement(event_id: int, db: Session = Depends(get_db),
                      user: User = Depends(require_roles("manager", "admin"))):
    """按责任比例结算医疗费用，生成结算单与赔付记录。"""
    ev = get_event_or_404(db, event_id)
    if ev.status == "closed":
        raise HTTPException(400, "事件已关闭")
    parties = db.query(ConflictParty).filter(ConflictParty.event_id == event_id).all()
    if len(parties) != 2:
        raise HTTPException(400, "该事件未建立双方冲突档案")
    if any(p.responsibility_percent is None for p in parties):
        raise HTTPException(400, "请先完成责任认定再结算")
    existing = db.query(Settlement).filter(Settlement.event_id == event_id).first()
    if existing:
        raise HTTPException(400, "该事件已生成结算单")

    a, b = parties[0], parties[1]
    records = db.query(MedicalRecord).filter(MedicalRecord.event_id == event_id).all()
    total = sum(float(m.cost or 0) for m in records)
    # 各方已付医疗费：按医疗记录关联的宠物归属；未关联宠物的计入责任较轻一方（受害方）
    paid = {a.pet_id: 0.0, b.pet_id: 0.0}
    victim = a if a.responsibility_percent <= b.responsibility_percent else b
    for m in records:
        cost = float(m.cost or 0)
        if m.pet_id == a.pet_id:
            paid[a.pet_id] += cost
        elif m.pet_id == b.pet_id:
            paid[b.pet_id] += cost
        else:
            paid[victim.pet_id] += cost

    share_a = round(total * a.responsibility_percent / 100, 2)
    share_b = round(total * (100 - a.responsibility_percent) / 100, 2)
    net_a = round(paid[a.pet_id] - share_a, 2)  # >0 表示 A 多付，应由 B 补付

    name_a = a.pet.name if a.pet else "甲方"
    name_b = b.pet.name if b.pet else "乙方"
    detail = (f"责任比例 {name_a} {a.responsibility_percent}% : {name_b} {b.responsibility_percent}%；"
              f"医疗费合计 {total:.2f} 元，{name_a}方承担 {share_a:.2f} 元、{name_b}方承担 {share_b:.2f} 元；"
              f"{name_a}方已付 {paid[a.pet_id]:.2f} 元、{name_b}方已付 {paid[b.pet_id]:.2f} 元。")

    comp = None
    if abs(net_a) > 0.005:
        if net_a > 0:  # B 补付 A
            payer, payee, amount = b, a, net_a
        else:        # A 补付 B
            payer, payee, amount = a, b, -net_a
        payer_name = payer.owner.name if payer.owner else ""
        payee_name = payee.owner.name if payee.owner else ""
        comp = Compensation(event_id=event_id, payer_owner_id=payer.owner_id,
                            payee_name=payee_name, amount=round(amount, 2),
                            reason=f"事件结算：责任 {payer.responsibility_percent}% 方补付医疗费",
                            handled_by=user.id)
        db.add(comp)
        db.flush()
        detail += f"结算：{payer_name} 应向 {payee_name} 支付 {amount:.2f} 元。"
    else:
        detail += "各方承担与已付一致，无需补付。"

    st = Settlement(event_id=event_id, medical_total=total, detail=detail,
                    compensation_id=comp.id if comp else None, created_by=user.id)
    db.add(st)
    add_update(db, event_id, user.id, "事件结算", detail)
    db.commit()
    return {"ok": True, "id": st.id, "detail": detail}


# ---------------- 证据留存与园区责任划分 ----------------

def _save_upload(prefix: str, file: UploadFile, content: bytes) -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1].lower() or ".bin"
    fname = f"{prefix}_{uuid.uuid4().hex[:10]}{ext}"
    with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
        f.write(content)
    return fname


@router.post("/{event_id}/evidence")
async def add_evidence(event_id: int,
                       evidence_type: str = Form(...), title: str = Form(...),
                       content: str = Form(""), file: UploadFile | None = File(None),
                       db: Session = Depends(get_db),
                       user: User = Depends(require_roles("patrol", "manager", "admin", "hospital"))):
    """留存监控片段、医疗凭证、责任划分文件等证据（关闭后只读）。"""
    ev = get_event_or_404(db, event_id)
    if ev.status == "closed":
        raise HTTPException(400, "事件已关闭，无法再补充证据")
    if evidence_type not in EVIDENCE_TYPES:
        raise HTTPException(400, "证据类型不合法")
    fname = None
    if file and file.filename:
        data = await file.read()
        if len(data) > 20 * 1024 * 1024:
            raise HTTPException(400, "附件不能超过 20MB")
        fname = _save_upload(f"evd{event_id}", file, data)
    rec = EventEvidence(event_id=event_id, evidence_type=evidence_type, title=title,
                        content=content, filename=fname, created_by=user.id)
    db.add(rec)
    add_update(db, event_id, user.id, "证据留存",
               f"[{EVIDENCE_TYPES[evidence_type]}] {title}")
    db.commit()
    return {"ok": True, "id": rec.id}


class ParkLiabilityIn(BaseModel):
    percent: int
    note: str = ""


@router.put("/{event_id}/park-liability")
def set_park_liability(event_id: int, data: ParkLiabilityIn, db: Session = Depends(get_db),
                       user: User = Depends(require_roles("manager", "admin"))):
    """园区责任划分（园区在事件中的责任比例与说明）。"""
    ev = get_event_or_404(db, event_id)
    if ev.status == "closed":
        raise HTTPException(400, "事件已关闭，园区责任划分不可再变更")
    if not (0 <= data.percent <= 100):
        raise HTTPException(400, "比例须在 0-100 之间")
    ev.park_liability_percent = data.percent
    ev.park_liability_note = data.note
    add_update(db, event_id, user.id, "园区责任划分",
               f"园区承担责任 {data.percent}%：{data.note}")
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
    # 冲突责任认定与结算归档
    parties = db.query(ConflictParty).filter(ConflictParty.event_id == event_id).all()
    if parties and all(p.responsibility_percent is not None for p in parties):
        liability = "，".join(
            f"{p.pet.name if p.pet else p.pet_id} {p.responsibility_percent}%（{SANCTION_LABELS.get(p.entry_sanction)}）"
            for p in parties)
        parts.append(f"责任认定：{liability}")
    settlement = db.query(Settlement).filter(Settlement.event_id == event_id).first()
    if settlement:
        parts.append(f"事件结算：{settlement.detail}")
    evidence_count = db.query(EventEvidence).filter(EventEvidence.event_id == event_id).count()
    if evidence_count:
        parts.append(f"证据留存 {evidence_count} 件（监控片段/医疗凭证/责任划分）")
    if ev.park_liability_percent is not None:
        parts.append(f"园区责任 {ev.park_liability_percent}%：{ev.park_liability_note}")
    parts.append(f"处置结论：{data.resolution_summary}")
    db.add(OperationRecord(record_type="event_closure", title=f"事件 {ev.code} 关闭归档",
                           content="；".join(parts), related_event_id=event_id,
                           created_by=user.id))
    db.commit()
    return event_dict(ev, db)
