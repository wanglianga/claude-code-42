from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import TIME_SLOTS
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import OperationRecord, Reservation, User, Zone
from ..serializers import zone_dict

router = APIRouter(prefix="/zones", tags=["分区"])


@router.get("")
def list_zones(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [zone_dict(z) for z in db.query(Zone).order_by(Zone.id).all()]


@router.get("/availability")
def availability(visit_date: date, time_slot: str, db: Session = Depends(get_db),
                 _: User = Depends(get_current_user)):
    """查询某日某时段各分区已确认预约数与剩余容量。"""
    if time_slot not in TIME_SLOTS:
        raise HTTPException(400, "时段不合法")
    zones = db.query(Zone).order_by(Zone.id).all()
    result = []
    for z in zones:
        used = db.query(Reservation).filter(
            Reservation.zone_id == z.id, Reservation.visit_date == visit_date,
            Reservation.time_slot == time_slot, Reservation.status == "confirmed").count()
        d = zone_dict(z)
        d["used"] = used
        d["remaining"] = max(z.capacity - used, 0)
        result.append(d)
    return result


class ZoneIn(BaseModel):
    capacity: int
    active: bool
    allowed_sizes: list[str]
    requires_no_attack_history: bool = False
    description: str = ""


@router.put("/{zone_id}")
def update_zone(zone_id: int, data: ZoneIn, db: Session = Depends(get_db),
                user: User = Depends(require_roles("manager", "admin"))):
    zone = db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(404, "分区不存在")
    old = f"容量 {zone.capacity} -> {data.capacity}；开放 {zone.active} -> {data.active}；体型限制 {zone.allowed_sizes} -> {','.join(data.allowed_sizes)}"
    zone.capacity = data.capacity
    zone.active = data.active
    zone.allowed_sizes = ",".join(data.allowed_sizes)
    zone.requires_no_attack_history = data.requires_no_attack_history
    zone.description = data.description
    db.add(OperationRecord(record_type="zone_change", title=f"分区调整：{zone.name}",
                           content=old, created_by=user.id))
    db.commit()
    return zone_dict(zone)
