from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import (BlacklistEntry, EntryCheck, Event, EventParticipant,
                      FacilityRectification, Incident, OperationRecord, Pet,
                      Reservation, ReviewDecision, User, Zone)
from ..serializers import (DECISION_TYPES, EVENT_TYPES, INCIDENT_TYPES,
                           RECORD_TYPES, SEVERITY_LABELS, SIZE_LABELS)

router = APIRouter(prefix="/analytics", tags=["复盘分析"])


def _pairs(rows, labels=None):
    return [{"label": (labels or {}).get(k, str(k)), "value": v} for k, v in rows]


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()
    data = {"role": user.role}
    if user.role == "owner":
        my_pets = db.query(Pet).filter(Pet.owner_id == user.id).all()
        pet_ids = [p.id for p in my_pets]
        data.update({
            "pets": len(my_pets),
            "upcoming": db.query(Reservation).filter(
                Reservation.owner_id == user.id, Reservation.visit_date >= today,
                Reservation.status == "confirmed").count(),
            "open_events": db.query(Event).filter(Event.owner_id == user.id, Event.status != "closed").count(),
            "blacklist": db.query(BlacklistEntry).filter(
                BlacklistEntry.active.is_(True),
                (BlacklistEntry.owner_id == user.id) | (BlacklistEntry.pet_id.in_(pet_ids or [-1]))).count(),
        })
    elif user.role == "gate":
        data.update({
            "today_confirmed": db.query(Reservation).filter(
                Reservation.visit_date == today, Reservation.status == "confirmed").count(),
            "today_checked": db.query(EntryCheck).join(Reservation).filter(Reservation.visit_date == today).count(),
            "today_failed": db.query(EntryCheck).join(Reservation).filter(
                Reservation.visit_date == today, EntryCheck.result == "failed").count(),
        })
    elif user.role == "patrol":
        data.update({
            "my_incidents": db.query(Incident).filter(Incident.reporter_id == user.id).count(),
            "open_events": db.query(Event).filter(Event.status != "closed").count(),
        })
    else:  # manager / admin / hospital / service
        data.update({
            "open_events": db.query(Event).filter(Event.status != "closed").count(),
            "today_reservations": db.query(Reservation).filter(
                Reservation.visit_date == today, Reservation.status == "confirmed").count(),
            "active_blacklist": db.query(BlacklistEntry).filter(BlacklistEntry.active.is_(True)).count(),
            "pending_rectifications": db.query(FacilityRectification).filter(
                FacilityRectification.status != "done").count(),
            "total_pets": db.query(Pet).count(),
            "total_incidents": db.query(Incident).count(),
        })
    # 最近事件（按角色可见范围）
    q = db.query(Event)
    if user.role not in ("manager", "admin"):
        joined = db.query(EventParticipant.event_id).filter(EventParticipant.user_id == user.id)
        q = q.filter(Event.id.in_(joined))
    from ..serializers import event_dict
    data["recent_events"] = [event_dict(e, db) for e in q.order_by(Event.created_at.desc()).limit(5).all()]
    return data


@router.get("/conflicts")
def conflicts(db: Session = Depends(get_db),
              _: User = Depends(require_roles("manager", "admin"))):
    """按宠物体型、品种、活动类型（分区）、行为类型复盘冲突。"""
    base = db.query(Incident)

    by_size = (base.join(Pet, Incident.pet_id == Pet.id)
               .with_entities(Pet.size_category, func.count(Incident.id))
               .group_by(Pet.size_category).all())
    by_breed = (base.join(Pet, Incident.pet_id == Pet.id)
                .with_entities(Pet.breed, func.count(Incident.id))
                .group_by(Pet.breed).order_by(func.count(Incident.id).desc()).limit(10).all())
    by_zone = (base.join(Zone, Incident.zone_id == Zone.id)
               .with_entities(Zone.name, func.count(Incident.id))
               .group_by(Zone.name).all())
    by_type = (base.with_entities(Incident.incident_type, func.count(Incident.id))
               .group_by(Incident.incident_type).all())
    by_severity = (base.with_entities(Incident.severity, func.count(Incident.id))
                   .group_by(Incident.severity).all())
    events_by_type = (db.query(Event.event_type, func.count(Event.id))
                      .group_by(Event.event_type).all())
    monthly = (db.query(func.to_char(Incident.occurred_at, "YYYY-MM"), func.count(Incident.id))
               .group_by(func.to_char(Incident.occurred_at, "YYYY-MM"))
               .order_by(func.to_char(Incident.occurred_at, "YYYY-MM")).all())

    # 高冲突品种明细（供"限制某些宠物活动"决策参考）
    breed_rows = (db.query(Pet.breed, Pet.size_category, func.count(Incident.id))
                  .join(Pet, Incident.pet_id == Pet.id)
                  .group_by(Pet.breed, Pet.size_category)
                  .order_by(func.count(Incident.id).desc()).limit(10).all())

    return {
        "by_size": _pairs(by_size, SIZE_LABELS),
        "by_breed": [{"label": b, "value": v} for b, v in by_breed],
        "by_zone": [{"label": z, "value": v} for z, v in by_zone],
        "by_type": _pairs(by_type, INCIDENT_TYPES),
        "by_severity": _pairs(by_severity, SEVERITY_LABELS),
        "events_by_type": _pairs(events_by_type, EVENT_TYPES),
        "monthly": [{"label": m, "value": v} for m, v in monthly],
        "breed_detail": [{"breed": b, "size": SIZE_LABELS.get(s, s), "count": c} for b, s, c in breed_rows],
    }


@router.get("/records")
def operation_records(db: Session = Depends(get_db),
                      _: User = Depends(require_roles("manager", "admin"))):
    records = db.query(OperationRecord).order_by(OperationRecord.created_at.desc()).limit(200).all()
    return [{
        "id": r.id, "record_type": r.record_type,
        "record_type_label": RECORD_TYPES.get(r.record_type, r.record_type),
        "title": r.title, "content": r.content, "related_event_id": r.related_event_id,
        "creator": r.creator.name if r.creator else "系统",
        "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
    } for r in records]


class DecisionIn(BaseModel):
    title: str
    decision_type: str
    content: str = ""


@router.get("/decisions")
def list_decisions(db: Session = Depends(get_db),
                   _: User = Depends(require_roles("manager", "admin"))):
    rows = db.query(ReviewDecision).order_by(ReviewDecision.created_at.desc()).limit(100).all()
    return [{
        "id": d.id, "title": d.title, "decision_type": d.decision_type,
        "decision_type_label": DECISION_TYPES.get(d.decision_type, d.decision_type),
        "content": d.content, "creator": d.creator.name if d.creator else "",
        "created_at": d.created_at.strftime("%Y-%m-%d %H:%M") if d.created_at else "",
    } for d in rows]


@router.post("/decisions")
def create_decision(data: DecisionIn, db: Session = Depends(get_db),
                    user: User = Depends(require_roles("manager", "admin"))):
    if data.decision_type not in DECISION_TYPES:
        from fastapi import HTTPException
        raise HTTPException(400, "决策类型不合法")
    d = ReviewDecision(title=data.title, decision_type=data.decision_type,
                       content=data.content, created_by=user.id)
    db.add(d)
    db.add(OperationRecord(record_type="review_decision", title=f"复盘决策：{data.title}",
                           content=f"[{DECISION_TYPES.get(data.decision_type)}] {data.content}",
                           created_by=user.id))
    db.commit()
    return {"ok": True, "id": d.id}
