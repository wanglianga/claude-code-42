import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import TIME_SLOTS
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import (ActivityRestriction, BlacklistEntry, Pet, Reservation,
                      User, Zone)
from ..serializers import reservation_dict

router = APIRouter(prefix="/reservations", tags=["预约"])


class ReservationIn(BaseModel):
    pet_id: int
    zone_id: int
    visit_date: date
    time_slot: str


def _active_blacklist(db: Session, pet_id: int, owner_id: int):
    return db.query(BlacklistEntry).filter(
        BlacklistEntry.active.is_(True),
        BlacklistEntry.level.in_(["restricted", "banned"]),
        (BlacklistEntry.pet_id == pet_id) | (BlacklistEntry.owner_id == owner_id),
    ).first()


def _warning_blacklist(db: Session, pet_id: int, owner_id: int):
    return db.query(BlacklistEntry).filter(
        BlacklistEntry.active.is_(True), BlacklistEntry.level == "warning",
        (BlacklistEntry.pet_id == pet_id) | (BlacklistEntry.owner_id == owner_id),
    ).first()


@router.post("")
def create_reservation(data: ReservationIn, db: Session = Depends(get_db),
                       user: User = Depends(require_roles("owner"))):
    pet = db.get(Pet, data.pet_id)
    if not pet or pet.owner_id != user.id:
        raise HTTPException(404, "宠物不存在或不属于当前账号")
    zone = db.get(Zone, data.zone_id)
    if not zone or not zone.active:
        raise HTTPException(404, "分区不存在或已关闭")
    if data.time_slot not in TIME_SLOTS:
        raise HTTPException(400, "时段不合法")
    if data.visit_date < date.today():
        raise HTTPException(400, "不能预约过去的日期")

    def reject(reason: str):
        r = Reservation(code="R" + uuid.uuid4().hex[:10].upper(), pet_id=pet.id,
                        owner_id=user.id, zone_id=zone.id, visit_date=data.visit_date,
                        time_slot=data.time_slot, status="rejected", result_reason=reason)
        db.add(r)
        db.commit()
        db.refresh(r)
        return {"reservation": reservation_dict(r), "ok": False}

    # 1. 黑名单校验（影响后续活动报名/预约）
    bl = _active_blacklist(db, pet.id, user.id)
    if bl:
        label = "永久拉黑" if bl.level == "banned" else "限制入园"
        return reject(f"该宠物或主人处于黑名单（{label}）：{bl.reason}")

    # 2. 活动资格限制
    restrictions = db.query(ActivityRestriction).filter(
        ActivityRestriction.pet_id == pet.id, ActivityRestriction.active.is_(True)).all()
    rtypes = {r.restriction_type for r in restrictions}
    if "activity_ban" in rtypes:
        return reject("该宠物已被暂停一切入园活动资格")
    if zone.code == "activity" and "no_activity_zone" in rtypes:
        return reject("该宠物被限制进入活动区，无法报名活动")
    if zone.code == "social" and "no_social_zone" in rtypes:
        return reject("该宠物被限制进入社交区")

    # 3. 疫苗校验
    if pet.vaccine_status != "valid" or (pet.vaccine_expiry and pet.vaccine_expiry < data.visit_date):
        return reject("疫苗已过期或缺失，请补种并更新档案后再预约")

    # 4. 体型与分区匹配
    if pet.size_category not in (zone.allowed_sizes or "").split(","):
        return reject(f"{zone.name}不允许该体型（{pet.size_category}）宠物进入")

    # 5. 攻击史限制
    if zone.requires_no_attack_history and pet.attack_history:
        return reject(f"有攻击史的宠物禁止进入{zone.name}")

    # 6. 同人同宠同时段重复预约
    dup = db.query(Reservation).filter(
        Reservation.pet_id == pet.id, Reservation.visit_date == data.visit_date,
        Reservation.time_slot == data.time_slot,
        Reservation.status.in_(["confirmed", "waitlisted"])).first()
    if dup:
        return reject("该宠物在此时段已有有效预约，请勿重复提交")

    # 7. 容量判定：满员进入候补
    used = db.query(Reservation).filter(
        Reservation.zone_id == zone.id, Reservation.visit_date == data.visit_date,
        Reservation.time_slot == data.time_slot, Reservation.status == "confirmed").count()

    warning = _warning_blacklist(db, pet.id, user.id)
    note = f"（提示：该宠物有警告记录：{warning.reason}）" if warning else ""

    if used >= zone.capacity:
        r = Reservation(code="R" + uuid.uuid4().hex[:10].upper(), pet_id=pet.id,
                        owner_id=user.id, zone_id=zone.id, visit_date=data.visit_date,
                        time_slot=data.time_slot, status="waitlisted",
                        result_reason=f"{zone.name}此时段已满员（{used}/{zone.capacity}），已进入候补队列{note}")
    else:
        r = Reservation(code="R" + uuid.uuid4().hex[:10].upper(), pet_id=pet.id,
                        owner_id=user.id, zone_id=zone.id, visit_date=data.visit_date,
                        time_slot=data.time_slot, status="confirmed",
                        result_reason=f"预约成功，当前占用 {used + 1}/{zone.capacity}{note}")
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"reservation": reservation_dict(r), "ok": True}


@router.get("")
def list_reservations(visit_date: date | None = None, status: str = "",
                      zone_id: int | None = None, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    q = db.query(Reservation)
    if user.role == "owner":
        q = q.filter(Reservation.owner_id == user.id)
    if visit_date:
        q = q.filter(Reservation.visit_date == visit_date)
    if status:
        q = q.filter(Reservation.status == status)
    if zone_id:
        q = q.filter(Reservation.zone_id == zone_id)
    return [reservation_dict(r) for r in q.order_by(Reservation.visit_date.desc(), Reservation.id.desc()).limit(200).all()]


@router.post("/{reservation_id}/cancel")
def cancel_reservation(reservation_id: int, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    r = db.get(Reservation, reservation_id)
    if not r:
        raise HTTPException(404, "预约不存在")
    if user.role == "owner" and r.owner_id != user.id:
        raise HTTPException(403, "只能取消自己的预约")
    if user.role not in ("owner", "manager", "admin"):
        raise HTTPException(403, "无权限")
    if r.status not in ("confirmed", "waitlisted"):
        raise HTTPException(400, "当前状态不可取消")
    r.status = "cancelled"
    r.result_reason = (r.result_reason or "") + "｜已取消"
    db.commit()
    return reservation_dict(r)
