from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import (ActivityRestriction, BlacklistEntry, Event, Incident,
                      MedicalRecord, Pet, Reservation, User)
from ..seed import size_of
from ..serializers import (blacklist_dict, event_dict, incident_dict, pet_dict,
                           reservation_dict, restriction_dict)

router = APIRouter(prefix="/pets", tags=["宠物档案"])


class PetIn(BaseModel):
    name: str
    breed: str
    weight_kg: float
    vaccine_status: str = "valid"
    vaccine_expiry: date | None = None
    rabies_vaccine_no: str = ""
    sterilized: bool = False
    attack_history: bool = False
    attack_history_desc: str = ""
    leash_required: bool = True
    dog_license_no: str = ""
    license_expiry: date | None = None
    notes: str = ""


def _check_vaccine_consistency(data: PetIn):
    # 若填写了过期日期，自动修正疫苗状态
    if data.vaccine_expiry and data.vaccine_expiry < date.today() and data.vaccine_status == "valid":
        data.vaccine_status = "expired"


@router.get("")
def list_pets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Pet)
    if user.role == "owner":
        q = q.filter(Pet.owner_id == user.id)
    pets = q.order_by(Pet.id).all()
    result = []
    for p in pets:
        d = pet_dict(p)
        d["active_blacklist"] = db.query(BlacklistEntry).filter(
            BlacklistEntry.pet_id == p.id, BlacklistEntry.active.is_(True)).count()
        d["active_restrictions"] = db.query(ActivityRestriction).filter(
            ActivityRestriction.pet_id == p.id, ActivityRestriction.active.is_(True)).count()
        result.append(d)
    return result


@router.post("")
def create_pet(data: PetIn, db: Session = Depends(get_db),
               user: User = Depends(require_roles("owner"))):
    _check_vaccine_consistency(data)
    pet = Pet(owner_id=user.id, name=data.name.strip(), breed=data.breed.strip(),
              weight_kg=data.weight_kg, size_category=size_of(data.weight_kg),
              vaccine_status=data.vaccine_status, vaccine_expiry=data.vaccine_expiry,
              rabies_vaccine_no=data.rabies_vaccine_no, sterilized=data.sterilized,
              attack_history=data.attack_history, attack_history_desc=data.attack_history_desc,
              leash_required=data.leash_required, dog_license_no=data.dog_license_no,
              license_expiry=data.license_expiry, notes=data.notes)
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet_dict(pet)


@router.put("/{pet_id}")
def update_pet(pet_id: int, data: PetIn, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    pet = db.get(Pet, pet_id)
    if not pet:
        raise HTTPException(404, "宠物不存在")
    if user.role == "owner" and pet.owner_id != user.id:
        raise HTTPException(403, "只能修改自己的宠物档案")
    if user.role not in ("owner", "manager", "admin"):
        raise HTTPException(403, "无权限")
    _check_vaccine_consistency(data)
    for field in ("name", "breed", "weight_kg", "vaccine_status", "vaccine_expiry",
                  "rabies_vaccine_no", "sterilized", "attack_history", "attack_history_desc",
                  "leash_required", "dog_license_no", "license_expiry", "notes"):
        setattr(pet, field, getattr(data, field))
    pet.size_category = size_of(data.weight_kg)
    db.commit()
    return pet_dict(pet)


@router.get("/{pet_id}")
def pet_profile(pet_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pet = db.get(Pet, pet_id)
    if not pet:
        raise HTTPException(404, "宠物不存在")
    if user.role == "owner" and pet.owner_id != user.id:
        raise HTTPException(403, "只能查看自己的宠物档案")

    incidents = db.query(Incident).filter(Incident.pet_id == pet_id).order_by(Incident.occurred_at.desc()).all()
    blacklist = db.query(BlacklistEntry).filter(BlacklistEntry.pet_id == pet_id).order_by(BlacklistEntry.created_at.desc()).all()
    restrictions = db.query(ActivityRestriction).filter(ActivityRestriction.pet_id == pet_id).order_by(ActivityRestriction.created_at.desc()).all()
    medical = db.query(MedicalRecord).filter(MedicalRecord.pet_id == pet_id).order_by(MedicalRecord.treated_at.desc()).all()
    reservations = db.query(Reservation).filter(Reservation.pet_id == pet_id).order_by(Reservation.created_at.desc()).limit(10).all()
    events = db.query(Event).filter(Event.pet_id == pet_id).order_by(Event.created_at.desc()).all()

    return {
        "pet": pet_dict(pet),
        "incidents": [incident_dict(i) for i in incidents],
        "blacklist": [blacklist_dict(b) for b in blacklist],
        "restrictions": [restriction_dict(r) for r in restrictions],
        "medical_records": [{
            "id": m.id, "event_id": m.event_id, "patient_name": m.patient_name,
            "injury_desc": m.injury_desc, "treatment": m.treatment, "cost": float(m.cost or 0),
            "treated_at": m.treated_at.strftime("%Y-%m-%d %H:%M") if m.treated_at else "",
            "hospital": m.hospital_user.name if m.hospital_user else "",
        } for m in medical],
        "reservations": [reservation_dict(r) for r in reservations],
        "events": [event_dict(e, db) for e in events],
    }
