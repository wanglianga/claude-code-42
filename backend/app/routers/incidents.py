import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Incident, Pet, User
from ..serializers import incident_dict
from .events import create_event_internal

router = APIRouter(prefix="/incidents", tags=["巡场上报"])


class IncidentIn(BaseModel):
    pet_id: int
    zone_id: int
    incident_type: str
    severity: str = "low"
    description: str = ""
    has_injury: bool = False
    owner_cooperative: bool = True


@router.post("")
def create_incident(data: IncidentIn, db: Session = Depends(get_db),
                    user: User = Depends(require_roles("patrol", "manager", "admin"))):
    pet = db.get(Pet, data.pet_id)
    if not pet:
        raise HTTPException(404, "宠物不存在")
    inc = Incident(code="I" + uuid.uuid4().hex[:8].upper(), pet_id=data.pet_id,
                   reporter_id=user.id, zone_id=data.zone_id,
                   incident_type=data.incident_type, severity=data.severity,
                   description=data.description, has_injury=data.has_injury,
                   owner_cooperative=data.owner_cooperative)
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return incident_dict(inc)


@router.get("")
def list_incidents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Incident)
    if user.role == "owner":
        q = q.join(Pet, Incident.pet_id == Pet.id).filter(Pet.owner_id == user.id)
    return [incident_dict(i) for i in q.order_by(Incident.occurred_at.desc()).limit(200).all()]


class EscalateIn(BaseModel):
    title: str
    event_type: str = "pet_conflict"
    priority: str = "high"
    description: str = ""


@router.post("/{incident_id}/escalate")
def escalate(incident_id: int, data: EscalateIn, db: Session = Depends(get_db),
             user: User = Depends(require_roles("patrol", "manager", "admin"))):
    """巡场记录升级为协同事件，自动串联五方角色。"""
    inc = db.get(Incident, incident_id)
    if not inc:
        raise HTTPException(404, "巡场记录不存在")
    if inc.event_id:
        raise HTTPException(400, "该记录已升级为事件")
    pet = db.get(Pet, inc.pet_id)
    ev = create_event_internal(
        db, creator=user, title=data.title, event_type=data.event_type,
        priority=data.priority, zone_id=inc.zone_id, pet_id=inc.pet_id,
        owner_id=pet.owner_id if pet else None,
        description=data.description or inc.description)
    inc.event_id = ev.id
    db.commit()
    return {"event_id": ev.id, "event_code": ev.code}
