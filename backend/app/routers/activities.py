import json
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import TIME_SLOTS
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import (Activity, ActivityRegistration, ActivityRestriction,
                      Pet, User)
from ..serializers import (ACTIVITY_TYPES, INTENSITY_LABELS, REG_STATUS_LABELS,
                           SIZE_LABELS)
from .reservations import _active_blacklist

router = APIRouter(prefix="/activities", tags=["活动"])


def effective_capacity(a: Activity) -> int:
    """有效容量 = min(场地容量, 教练数量 × 每名教练可带宠物数)。"""
    return min(a.capacity, a.coach_count * a.pets_per_coach)


def activity_dict(db: Session, a: Activity) -> dict:
    regs = db.query(ActivityRegistration).filter(ActivityRegistration.activity_id == a.id).all()
    return {
        "id": a.id, "title": a.title,
        "activity_type": a.activity_type,
        "activity_type_label": ACTIVITY_TYPES.get(a.activity_type, a.activity_type),
        "activity_date": a.activity_date.isoformat(),
        "time_slot": a.time_slot, "time_slot_label": TIME_SLOTS.get(a.time_slot, a.time_slot),
        "intensity": a.intensity,
        "intensity_label": INTENSITY_LABELS.get(a.intensity, a.intensity),
        "allowed_sizes": a.allowed_sizes.split(",") if a.allowed_sizes else [],
        "allowed_size_labels": [SIZE_LABELS.get(s, s) for s in (a.allowed_sizes.split(",") if a.allowed_sizes else [])],
        "capacity": a.capacity, "coach_count": a.coach_count,
        "pets_per_coach": a.pets_per_coach,
        "effective_capacity": effective_capacity(a),
        "coach_names": [c.strip() for c in a.coach_names.split(",") if c.strip()],
        "insurance_policy_no": a.insurance_policy_no,
        "insured_count": a.insured_count, "insured_pets": a.insured_pets,
        "coach_assignments": json.loads(a.coach_assignments) if a.coach_assignments else {},
        "status": a.status,
        "registered_count": sum(1 for r in regs if r.status == "registered"),
        "waitlist_count": sum(1 for r in regs if r.status == "waitlisted"),
        "admitted_count": sum(1 for r in regs if r.status == "admitted"),
    }


def registration_dict(r: ActivityRegistration) -> dict:
    return {
        "id": r.id, "activity_id": r.activity_id,
        "pet_id": r.pet_id, "pet_name": r.pet.name if r.pet else "",
        "breed": r.pet.breed if r.pet else "",
        "size_label": SIZE_LABELS.get(r.pet.size_category, "") if r.pet else "",
        "owner_id": r.owner_id, "owner_name": r.owner.name if r.owner else "",
        "owner_phone": r.owner.phone if r.owner else "",
        "status": r.status, "status_label": REG_STATUS_LABELS.get(r.status, r.status),
        "queue_position": r.queue_position,
        "reject_reason": r.reject_reason,
        "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
    }


def sync_activity_state(db: Session, a: Activity):
    """候补入场/检录变化后：同步活动保险与教练分组名单。"""
    admitted = db.query(ActivityRegistration).filter(
        ActivityRegistration.activity_id == a.id,
        ActivityRegistration.status == "admitted").order_by(ActivityRegistration.decided_at).all()
    a.insured_count = len(admitted)
    a.insured_pets = "、".join(r.pet.name for r in admitted if r.pet)
    coaches = [c.strip() for c in a.coach_names.split(",") if c.strip()]
    assignments = {c: [] for c in coaches}
    for i, r in enumerate(admitted):
        if coaches:
            assignments[coaches[i % len(coaches)]].append(r.pet.name if r.pet else "")
    a.coach_assignments = json.dumps(assignments, ensure_ascii=False)


# ---------------- 活动管理 ----------------

class ActivityIn(BaseModel):
    title: str
    activity_type: str = "frisbee"
    activity_date: date
    time_slot: str = "morning"
    intensity: str = "medium"
    allowed_sizes: list[str] = ["small", "medium", "large"]
    capacity: int = 20
    coach_count: int = 1
    pets_per_coach: int = 8
    coach_names: str = ""
    insurance_policy_no: str = ""


@router.post("")
def create_activity(data: ActivityIn, db: Session = Depends(get_db),
                    user: User = Depends(require_roles("manager", "admin"))):
    if data.activity_type not in ACTIVITY_TYPES:
        raise HTTPException(400, "活动类型不合法")
    if data.time_slot not in TIME_SLOTS:
        raise HTTPException(400, "时段不合法")
    if data.intensity not in INTENSITY_LABELS:
        raise HTTPException(400, "强度不合法")
    if data.capacity < 1 or data.coach_count < 1 or data.pets_per_coach < 1:
        raise HTTPException(400, "容量与教练配置必须为正数")
    a = Activity(title=data.title, activity_type=data.activity_type,
                 activity_date=data.activity_date, time_slot=data.time_slot,
                 intensity=data.intensity, allowed_sizes=",".join(data.allowed_sizes),
                 capacity=data.capacity, coach_count=data.coach_count,
                 pets_per_coach=data.pets_per_coach, coach_names=data.coach_names,
                 insurance_policy_no=data.insurance_policy_no, created_by=user.id)
    db.add(a)
    db.commit()
    return activity_dict(db, a)


@router.get("")
def list_activities(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Activity).order_by(Activity.activity_date.desc(), Activity.id.desc()).limit(100).all()
    return [activity_dict(db, a) for a in rows]


@router.get("/{activity_id}")
def activity_detail(activity_id: int, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    a = db.get(Activity, activity_id)
    if not a:
        raise HTTPException(404, "活动不存在")
    regs = db.query(ActivityRegistration).filter(
        ActivityRegistration.activity_id == activity_id).order_by(
        ActivityRegistration.queue_position.asc().nullslast(),
        ActivityRegistration.created_at).all()
    out = activity_dict(db, a)
    out["registrations"] = [registration_dict(r) for r in regs]
    if user.role == "owner":
        out["my_registrations"] = [registration_dict(r) for r in regs if r.owner_id == user.id]
    return out


# ---------------- 报名 ----------------

def _check_eligibility(db: Session, a: Activity, pet: Pet) -> str | None:
    """返回拒绝原因，None 表示通过。规则：体型、强度、疫苗、黑名单、活动资格限制。"""
    if pet.size_category not in (a.allowed_sizes or "").split(","):
        return f"该活动不允许{SIZE_LABELS.get(pet.size_category)}宠物参加"
    if a.intensity == "high" and pet.attack_history:
        return "高强度活动不接受有攻击史的宠物"
    if pet.vaccine_status != "valid" or (pet.vaccine_expiry and pet.vaccine_expiry < a.activity_date):
        return "疫苗已过期或缺失，无法报名"
    bl = _active_blacklist(db, pet.id, pet.owner_id)
    if bl:
        return f"该宠物或主人处于黑名单：{bl.reason}"
    restrictions = db.query(ActivityRestriction).filter(
        ActivityRestriction.pet_id == pet.id, ActivityRestriction.active.is_(True)).all()
    rtypes = {r.restriction_type for r in restrictions}
    if "activity_ban" in rtypes:
        return "该宠物已被暂停一切入园活动资格"
    if "no_activity_zone" in rtypes:
        return "该宠物被限制进入活动区"
    return None


def _do_register(db: Session, a: Activity, pet: Pet) -> ActivityRegistration:
    used = db.query(ActivityRegistration).filter(
        ActivityRegistration.activity_id == a.id,
        ActivityRegistration.status.in_(["registered", "admitted"])).count()
    if used >= effective_capacity(a):
        max_q = db.query(ActivityRegistration).filter(
            ActivityRegistration.activity_id == a.id,
            ActivityRegistration.queue_position.isnot(None)).order_by(
            ActivityRegistration.queue_position.desc()).first()
        reg = ActivityRegistration(
            activity_id=a.id, pet_id=pet.id, owner_id=pet.owner_id,
            status="waitlisted",
            queue_position=(max_q.queue_position + 1) if max_q else 1)
    else:
        reg = ActivityRegistration(activity_id=a.id, pet_id=pet.id, owner_id=pet.owner_id,
                                   status="registered")
    db.add(reg)
    db.flush()
    return reg


@router.post("/{activity_id}/register")
def register(activity_id: int, data: dict, db: Session = Depends(get_db),
             user: User = Depends(require_roles("owner"))):
    a = db.get(Activity, activity_id)
    if not a or a.status != "open":
        raise HTTPException(404, "活动不存在或已截止")
    pet = db.get(Pet, int(data.get("pet_id", 0)))
    if not pet or pet.owner_id != user.id:
        raise HTTPException(404, "宠物不存在或不属于当前账号")
    reason = _check_eligibility(db, a, pet)
    if reason:
        raise HTTPException(400, reason)
    dup = db.query(ActivityRegistration).filter(
        ActivityRegistration.activity_id == a.id, ActivityRegistration.pet_id == pet.id,
        ActivityRegistration.status.in_(["registered", "waitlisted", "admitted"])).first()
    if dup:
        raise HTTPException(400, "该宠物已报名本活动")
    reg = _do_register(db, a, pet)
    db.commit()
    return registration_dict(reg)


@router.post("/{activity_id}/walkin")
def walkin(activity_id: int, data: dict, db: Session = Depends(get_db),
           user: User = Depends(require_roles("coach", "manager", "admin"))):
    """活动当天临时报到：教练现场登记（满员则进入候补队列）。"""
    a = db.get(Activity, activity_id)
    if not a or a.status != "open":
        raise HTTPException(404, "活动不存在或已截止")
    if a.activity_date != date.today():
        raise HTTPException(400, "仅活动当天可现场登记")
    pet = db.get(Pet, int(data.get("pet_id", 0)))
    if not pet:
        raise HTTPException(404, "宠物不存在")
    reason = _check_eligibility(db, a, pet)
    if reason:
        raise HTTPException(400, reason)
    dup = db.query(ActivityRegistration).filter(
        ActivityRegistration.activity_id == a.id, ActivityRegistration.pet_id == pet.id,
        ActivityRegistration.status.in_(["registered", "waitlisted", "admitted"])).first()
    if dup:
        raise HTTPException(400, "该宠物已报名本活动")
    reg = _do_register(db, a, pet)
    db.commit()
    return registration_dict(reg)


@router.post("/registrations/{reg_id}/cancel")
def cancel_registration(reg_id: int, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    r = db.get(ActivityRegistration, reg_id)
    if not r:
        raise HTTPException(404, "报名记录不存在")
    if user.role == "owner" and r.owner_id != user.id:
        raise HTTPException(403, "只能取消自己的报名")
    if user.role not in ("owner", "manager", "admin"):
        raise HTTPException(403, "无权限")
    if r.status not in ("registered", "waitlisted"):
        raise HTTPException(400, "当前状态不可取消")
    was_registered = r.status == "registered"
    r.status = "cancelled"
    if was_registered:
        _promote_next(db, r.activity_id)
    db.commit()
    return {"ok": True}


# ---------------- 检录（活动当天） ----------------

def _promote_next(db: Session, activity_id: int):
    """名额空出时，队首候补递补为已报名（名额保留给下一位排队用户）。"""
    nxt = db.query(ActivityRegistration).filter(
        ActivityRegistration.activity_id == activity_id,
        ActivityRegistration.status == "waitlisted").order_by(
        ActivityRegistration.queue_position).first()
    if nxt:
        nxt.status = "registered"
        nxt.queue_position = None
    return nxt


class CheckinIn(BaseModel):
    registration_id: int
    decision: str  # admit/reject
    reason: str = ""


@router.post("/{activity_id}/checkin")
def checkin(activity_id: int, data: CheckinIn, db: Session = Depends(get_db),
            user: User = Depends(require_roles("coach", "manager", "admin"))):
    """现场教练检录：允许入场或拒绝；拒绝已报名者名额递补给队首候补。"""
    a = db.get(Activity, activity_id)
    if not a:
        raise HTTPException(404, "活动不存在")
    if a.activity_date != date.today():
        raise HTTPException(400, "仅活动当天可检录")
    r = db.get(ActivityRegistration, data.registration_id)
    if not r or r.activity_id != activity_id:
        raise HTTPException(404, "报名记录不存在")
    if r.status not in ("registered", "waitlisted"):
        raise HTTPException(400, f"当前状态（{REG_STATUS_LABELS.get(r.status)}）不可检录")

    if data.decision == "admit":
        admitted = db.query(ActivityRegistration).filter(
            ActivityRegistration.activity_id == activity_id,
            ActivityRegistration.status == "admitted").count()
        if admitted >= effective_capacity(a):
            raise HTTPException(400, "入场名额已满，无法放行")
        r.status = "admitted"
        r.queue_position = None
        r.decided_by = user.id
        r.decided_at = datetime.utcnow()
        db.flush()
        sync_activity_state(db, a)  # 同步活动保险与教练名单
    elif data.decision == "reject":
        was_registered = r.status == "registered"
        r.status = "rejected"
        r.reject_reason = data.reason or "现场检录未通过"
        r.queue_position = None
        r.decided_by = user.id
        r.decided_at = datetime.utcnow()
        if was_registered:
            _promote_next(db, activity_id)  # 名额保留给下一位排队用户
    else:
        raise HTTPException(400, "decision 须为 admit 或 reject")

    db.commit()
    return activity_detail(activity_id, db=db, user=user)
