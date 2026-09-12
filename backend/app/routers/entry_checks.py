from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..models import (ActivityRestriction, EntryCheck, Reservation, User)
from ..serializers import entry_check_dict, reservation_dict
from .events import create_event_internal

router = APIRouter(prefix="/entry-checks", tags=["入园核验"])

CHECK_ITEMS = {
    "vaccine_ok": "疫苗有效",
    "license_ok": "犬证有效",
    "leash_ok": "牵引绳合规",
    "identity_ok": "主人身份一致",
}


class EntryCheckIn(BaseModel):
    reservation_id: int
    vaccine_ok: bool
    license_ok: bool
    leash_ok: bool
    identity_ok: bool
    notes: str = ""
    escalate: bool = False  # 核验不通过时是否升级为事件


@router.get("/board")
def board(visit_date: date, db: Session = Depends(get_db),
          _: User = Depends(require_roles("gate", "manager", "admin"))):
    """核验工作台：当日已确认预约 + 对应核验记录。"""
    reservations = db.query(Reservation).filter(
        Reservation.visit_date == visit_date,
        Reservation.status.in_(["confirmed", "completed"])).order_by(Reservation.time_slot, Reservation.id).all()
    checks = {c.reservation_id: c for c in db.query(EntryCheck).join(Reservation).filter(Reservation.visit_date == visit_date).all()}
    result = []
    for r in reservations:
        item = reservation_dict(r)
        pet = r.pet
        item["pet"] = {
            "id": pet.id, "name": pet.name, "breed": pet.breed,
            "vaccine_status": pet.vaccine_status,
            "vaccine_expiry": pet.vaccine_expiry.isoformat() if pet.vaccine_expiry else None,
            "dog_license_no": pet.dog_license_no,
            "license_expiry": pet.license_expiry.isoformat() if pet.license_expiry else None,
            "leash_required": pet.leash_required,
            "attack_history": pet.attack_history,
        }
        c = checks.get(r.id)
        item["check"] = entry_check_dict(c) if c else None
        result.append(item)
    return result


@router.post("")
def create_check(data: EntryCheckIn, db: Session = Depends(get_db),
                 user: User = Depends(require_roles("gate", "manager", "admin"))):
    r = db.get(Reservation, data.reservation_id)
    if not r:
        raise HTTPException(404, "预约不存在")
    if r.status not in ("confirmed", "completed"):
        raise HTTPException(400, "仅已确认的预约可核验")
    if r.visit_date != date.today():
        raise HTTPException(400, "只能核验当日入园的预约")
    existing = db.query(EntryCheck).filter(EntryCheck.reservation_id == r.id).first()
    if existing:
        raise HTTPException(400, "该预约已完成核验，请勿重复提交")

    passed = all([data.vaccine_ok, data.license_ok, data.leash_ok, data.identity_ok])
    fails = [label for field, label in CHECK_ITEMS.items() if not getattr(data, field)]

    if passed:
        # 通过核验，但受活动资格限制的宠物不能进入自由活动区
        restricted = db.query(ActivityRestriction).filter(
            ActivityRestriction.pet_id == r.pet_id,
            ActivityRestriction.active.is_(True),
            ActivityRestriction.restriction_type.in_(["leash_only", "no_free_area"])).first()
        allowed = "leash_only" if restricted else "free_activity"
        result, fail_text = "passed", ""
        r.status = "completed"
    else:
        allowed = "denied"
        result = "failed"
        fail_text = "；".join(fails)

    check = EntryCheck(reservation_id=r.id, staff_id=user.id, vaccine_ok=data.vaccine_ok,
                       license_ok=data.license_ok, leash_ok=data.leash_ok,
                       identity_ok=data.identity_ok, result=result,
                       fail_reasons=fail_text, allowed_area=allowed, notes=data.notes)
    db.add(check)
    db.flush()

    event_id = None
    if not passed and data.escalate:
        etype = "vaccine_expired" if not data.vaccine_ok else "uncooperative"
        ev = create_event_internal(
            db, creator=user,
            title=f"入园核验未通过：{r.pet.name}（{fail_text}）",
            event_type=etype, priority="high", zone_id=r.zone_id,
            pet_id=r.pet_id, owner_id=r.owner_id,
            description=f"预约 {r.code} 入园核验未通过项：{fail_text}。备注：{data.notes or '无'}",
        )
        event_id = ev.id

    db.commit()
    db.refresh(check)
    out = entry_check_dict(check)
    out["event_id"] = event_id
    return out


@router.get("")
def list_checks(visit_date: date | None = None, db: Session = Depends(get_db),
                _: User = Depends(require_roles("gate", "manager", "admin"))):
    q = db.query(EntryCheck).join(Reservation)
    if visit_date:
        q = q.filter(Reservation.visit_date == visit_date)
    return [entry_check_dict(c) for c in q.order_by(EntryCheck.check_time.desc()).limit(200).all()]
