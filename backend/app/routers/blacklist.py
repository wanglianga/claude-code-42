from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import (ActivityRestriction, BlacklistEntry, OperationRecord, Pet,
                      User)
from ..serializers import blacklist_dict, restriction_dict

router = APIRouter(prefix="/blacklist", tags=["黑名单"])


@router.get("")
def list_blacklist(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(BlacklistEntry)
    if user.role == "owner":
        pet_ids = [p.id for p in db.query(Pet).filter(Pet.owner_id == user.id).all()]
        q = q.filter((BlacklistEntry.owner_id == user.id) | (BlacklistEntry.pet_id.in_(pet_ids or [-1])))
    return [blacklist_dict(b) for b in q.order_by(BlacklistEntry.created_at.desc()).limit(200).all()]


@router.post("/{entry_id}/lift")
def lift(entry_id: int, db: Session = Depends(get_db),
         user: User = Depends(require_roles("manager", "admin"))):
    b = db.get(BlacklistEntry, entry_id)
    if not b:
        raise HTTPException(404, "黑名单记录不存在")
    if not b.active:
        raise HTTPException(400, "该记录已解除")
    b.active = False
    b.lifted_at = datetime.utcnow()
    b.lifted_by = user.id
    db.add(OperationRecord(record_type="blacklist", title="黑名单解除",
                           content=f"黑名单 #{b.id}（{b.level}）已解除：{b.reason}",
                           related_event_id=b.event_id, created_by=user.id))
    db.commit()
    return {"ok": True}


@router.get("/restrictions")
def list_restrictions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(ActivityRestriction)
    if user.role == "owner":
        pet_ids = [p.id for p in db.query(Pet).filter(Pet.owner_id == user.id).all()]
        q = q.filter(ActivityRestriction.pet_id.in_(pet_ids or [-1]))
    return [restriction_dict(r) for r in q.order_by(ActivityRestriction.created_at.desc()).limit(200).all()]


@router.post("/restrictions/{restriction_id}/lift")
def lift_restriction(restriction_id: int, db: Session = Depends(get_db),
                     user: User = Depends(require_roles("manager", "admin"))):
    r = db.get(ActivityRestriction, restriction_id)
    if not r:
        raise HTTPException(404, "限制记录不存在")
    if not r.active:
        raise HTTPException(400, "该限制已解除")
    r.active = False
    r.lifted_at = datetime.utcnow()
    db.add(OperationRecord(record_type="restriction", title="活动资格限制解除",
                           content=f"限制 #{r.id}（{r.restriction_type}）已解除",
                           related_event_id=r.event_id, created_by=user.id))
    db.commit()
    return {"ok": True}
