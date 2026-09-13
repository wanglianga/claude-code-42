from datetime import datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
    Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False)  # owner/gate/patrol/manager/hospital/service/admin
    name = Column(String(64), nullable=False)
    phone = Column(String(32), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Pet(Base):
    __tablename__ = "pets"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(64), nullable=False)
    breed = Column(String(64), nullable=False)
    weight_kg = Column(Float, nullable=False)
    size_category = Column(String(16), nullable=False)  # small/medium/large
    vaccine_status = Column(String(16), nullable=False, default="valid")  # valid/expired/missing
    vaccine_expiry = Column(Date, nullable=True)
    rabies_vaccine_no = Column(String(64), default="")
    sterilized = Column(Boolean, default=False)
    attack_history = Column(Boolean, default=False)
    attack_history_desc = Column(Text, default="")
    leash_required = Column(Boolean, default=True)
    dog_license_no = Column(String(64), default="")
    license_expiry = Column(Date, nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship("User")


class Zone(Base):
    __tablename__ = "zones"
    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False)  # large_dog/small_dog/social/training/activity
    name = Column(String(64), nullable=False)
    capacity = Column(Integer, nullable=False)
    allowed_sizes = Column(String(64), default="small,medium,large")
    requires_no_attack_history = Column(Boolean, default=False)
    description = Column(Text, default="")
    active = Column(Boolean, default=True)


class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    visit_date = Column(Date, nullable=False)
    time_slot = Column(String(16), nullable=False)  # morning/afternoon/evening
    # confirmed/waitlisted/rejected/cancelled/completed
    status = Column(String(16), nullable=False, default="confirmed")
    result_reason = Column(String(255), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    pet = relationship("Pet")
    owner = relationship("User")
    zone = relationship("Zone")


class EntryCheck(Base):
    __tablename__ = "entry_checks"
    id = Column(Integer, primary_key=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False)
    staff_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    check_time = Column(DateTime, default=datetime.utcnow)
    vaccine_ok = Column(Boolean, default=False)
    license_ok = Column(Boolean, default=False)
    leash_ok = Column(Boolean, default=False)
    identity_ok = Column(Boolean, default=False)
    result = Column(String(16), nullable=False)  # passed/failed
    fail_reasons = Column(String(255), default="")
    allowed_area = Column(String(32), default="denied")  # free_activity/leash_only/denied
    notes = Column(Text, default="")
    reservation = relationship("Reservation")
    staff = relationship("User")


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False)
    title = Column(String(128), nullable=False)
    # pet_conflict/injury/vaccine_expired/uncooperative/overcrowding/other
    event_type = Column(String(32), nullable=False)
    status = Column(String(16), nullable=False, default="open")  # open/processing/closed
    priority = Column(String(16), default="medium")  # low/medium/high/critical
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    location = Column(String(255), default="")  # 冲突位置
    description = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    closed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolution_summary = Column(Text, default="")
    zone = relationship("Zone")
    pet = relationship("Pet")


class Incident(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False)
    related_pet_id = Column(Integer, ForeignKey("pets.id"), nullable=True)  # 冲突对方宠物
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    # chasing/barking/toy_fight/bite/waste/equipment_damage/other
    incident_type = Column(String(32), nullable=False)
    severity = Column(String(16), nullable=False, default="low")  # low/medium/high/critical
    location = Column(String(255), default="")  # 冲突位置
    description = Column(Text, default="")
    has_injury = Column(Boolean, default=False)
    owner_cooperative = Column(Boolean, default=True)
    occurred_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    pet = relationship("Pet", foreign_keys=[pet_id])
    related_pet = relationship("Pet", foreign_keys=[related_pet_id])
    reporter = relationship("User")
    zone = relationship("Zone")


class EventParticipant(Base):
    __tablename__ = "event_participants"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    participant_role = Column(String(32), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_user"),)
    user = relationship("User")


class EventUpdate(Base):
    __tablename__ = "event_updates"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(64), nullable=False)
    content = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    actor = relationship("User")


class MedicalRecord(Base):
    __tablename__ = "medical_records"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=True)
    patient_type = Column(String(16), default="pet")  # pet/person
    patient_name = Column(String(64), default="")
    hospital_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    injury_desc = Column(Text, nullable=False)
    treatment = Column(Text, default="")
    cost = Column(Numeric(10, 2), default=0)
    treated_at = Column(DateTime, default=datetime.utcnow)
    hospital_user = relationship("User")
    pet = relationship("Pet")


class Compensation(Base):
    __tablename__ = "compensations"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    payer_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    payee_name = Column(String(64), default="")
    amount = Column(Numeric(10, 2), nullable=False)
    reason = Column(String(255), default="")
    status = Column(String(16), default="pending")  # pending/paid/rejected
    handled_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    payer = relationship("User", foreign_keys=[payer_owner_id])
    handler = relationship("User", foreign_keys=[handled_by])


class BlacklistEntry(Base):
    __tablename__ = "blacklist_entries"
    id = Column(Integer, primary_key=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    level = Column(String(16), nullable=False, default="warning")  # warning/restricted/banned
    reason = Column(Text, default="")
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    lifted_at = Column(DateTime, nullable=True)
    lifted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    pet = relationship("Pet")
    owner = relationship("User", foreign_keys=[owner_id])


class ActivityRestriction(Base):
    __tablename__ = "activity_restrictions"
    id = Column(Integer, primary_key=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False)
    # leash_only/muzzle_required/no_activity_zone/no_social_zone/activity_ban
    restriction_type = Column(String(32), nullable=False)
    reason = Column(Text, default="")
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    lifted_at = Column(DateTime, nullable=True)
    pet = relationship("Pet")


class FacilityRectification(Base):
    __tablename__ = "facility_rectifications"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True)
    issue = Column(String(255), nullable=False)
    action = Column(Text, default="")
    status = Column(String(16), default="pending")  # pending/in_progress/done
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    zone = relationship("Zone")


class ConflictParty(Base):
    """冲突双方档案：入园状态、牵引、陈述与责任认定结果。"""
    __tablename__ = "conflict_parties"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    entry_check_id = Column(Integer, ForeignKey("entry_checks.id"), nullable=True)  # 当日入园核验
    leash_compliant = Column(Boolean, default=True)  # 冲突时是否拴绳
    owner_statement = Column(Text, default="")  # 主人陈述
    statement_at = Column(DateTime, nullable=True)
    # 责任认定结果
    responsibility_percent = Column(Integer, nullable=True)  # 责任比例 0-100
    determination = Column(Text, default="")  # 认定说明
    entry_sanction = Column(String(16), default="none")  # none/warning/restricted/banned
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("event_id", "pet_id", name="uq_conflict_event_pet"),)
    pet = relationship("Pet")
    owner = relationship("User")
    entry_check = relationship("EntryCheck")


class ConflictPhoto(Base):
    """巡场员现场照片。"""
    __tablename__ = "conflict_photos"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    note = Column(String(255), default="")
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    uploader = relationship("User")


class Settlement(Base):
    """事件结算单：医疗费用 × 责任比例。"""
    __tablename__ = "settlements"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    medical_total = Column(Numeric(10, 2), default=0)
    detail = Column(Text, default="")  # 结算明细
    compensation_id = Column(Integer, ForeignKey("compensations.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class OperationRecord(Base):
    __tablename__ = "operation_records"
    id = Column(Integer, primary_key=True)
    # event_closure/blacklist/restriction/rectification/zone_change/review_decision
    record_type = Column(String(32), nullable=False)
    title = Column(String(128), nullable=False)
    content = Column(Text, default="")
    related_event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    creator = relationship("User")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    id = Column(Integer, primary_key=True)
    title = Column(String(128), nullable=False)
    decision_type = Column(String(32), nullable=False)  # rezone/add_patrol/restrict_pets/policy
    content = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    creator = relationship("User")
