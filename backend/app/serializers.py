"""枚举中文标签与对象序列化。"""
from .config import ROLES, TIME_SLOTS

SIZE_LABELS = {"small": "小型", "medium": "中型", "large": "大型"}
VACCINE_LABELS = {"valid": "有效", "expired": "已过期", "missing": "缺失"}
RESERVATION_STATUS = {
    "confirmed": "已确认", "waitlisted": "候补", "rejected": "已拒绝",
    "cancelled": "已取消", "completed": "已完成",
}
INCIDENT_TYPES = {
    "chasing": "追逐", "barking": "吠叫", "toy_fight": "争抢玩具",
    "bite": "咬伤", "waste": "未清理粪便", "equipment_damage": "设备损坏", "other": "其他",
}
SEVERITY_LABELS = {"low": "轻微", "medium": "一般", "high": "严重", "critical": "紧急"}
EVENT_TYPES = {
    "pet_conflict": "宠物冲突", "injury": "人员受伤", "vaccine_expired": "疫苗过期",
    "uncooperative": "主人拒不配合", "overcrowding": "活动区超员", "other": "其他",
}
EVENT_STATUS = {"open": "待处理", "processing": "处理中", "closed": "已关闭"}
PRIORITY_LABELS = {"low": "低", "medium": "中", "high": "高", "critical": "紧急"}
BLACKLIST_LEVELS = {"warning": "警告", "restricted": "限制入园", "banned": "永久拉黑"}
RESTRICTION_TYPES = {
    "leash_only": "仅限牵引区域", "muzzle_required": "需佩戴嘴套",
    "no_activity_zone": "禁止进入活动区", "no_social_zone": "禁止进入社交区",
    "activity_ban": "暂停一切入园活动资格",
}
COMPENSATION_STATUS = {"pending": "待赔付", "paid": "已赔付", "rejected": "已驳回"}
RECTIFICATION_STATUS = {"pending": "待整改", "in_progress": "整改中", "done": "已完成"}
ALLOWED_AREA = {"free_activity": "自由活动区", "leash_only": "仅限牵引区", "denied": "禁止入园"}
SANCTION_LABELS = {"none": "不限制", "warning": "警告", "restricted": "限制入园", "banned": "永久拉黑"}
ACTIVITY_TYPES = {"frisbee": "飞盘", "training_course": "训练课", "social_event": "社交活动"}
INTENSITY_LABELS = {"low": "低强度", "medium": "中强度", "high": "高强度"}
REG_STATUS_LABELS = {
    "registered": "已报名", "waitlisted": "候补中", "admitted": "已入场",
    "rejected": "已拒绝", "cancelled": "已取消",
}
EVIDENCE_TYPES = {
    "surveillance": "监控片段", "medical_certificate": "医疗凭证",
    "liability": "责任划分文件", "other": "其他",
}
RECORD_TYPES = {
    "event_closure": "事件关闭", "blacklist": "黑名单", "restriction": "活动资格",
    "rectification": "设施整改", "zone_change": "分区调整", "review_decision": "复盘决策",
}
DECISION_TYPES = {
    "rezone": "重新划分分区", "add_patrol": "增加巡场员",
    "restrict_pets": "限制特定宠物活动", "policy": "制度调整",
}
CHECK_RESULT = {"passed": "通过", "failed": "未通过"}


def user_dict(u):
    if not u:
        return None
    return {
        "id": u.id, "username": u.username, "name": u.name,
        "role": u.role, "role_label": ROLES.get(u.role, u.role), "phone": u.phone,
    }


def pet_dict(p, with_owner=True):
    d = {
        "id": p.id, "name": p.name, "breed": p.breed, "weight_kg": p.weight_kg,
        "size_category": p.size_category,
        "size_label": SIZE_LABELS.get(p.size_category, p.size_category),
        "vaccine_status": p.vaccine_status,
        "vaccine_label": VACCINE_LABELS.get(p.vaccine_status, p.vaccine_status),
        "vaccine_expiry": p.vaccine_expiry.isoformat() if p.vaccine_expiry else None,
        "rabies_vaccine_no": p.rabies_vaccine_no,
        "sterilized": p.sterilized,
        "attack_history": p.attack_history,
        "attack_history_desc": p.attack_history_desc,
        "leash_required": p.leash_required,
        "dog_license_no": p.dog_license_no,
        "license_expiry": p.license_expiry.isoformat() if p.license_expiry else None,
        "notes": p.notes,
        "owner_id": p.owner_id,
    }
    if with_owner and p.owner:
        d["owner_name"] = p.owner.name
    return d


def zone_dict(z):
    return {
        "id": z.id, "code": z.code, "name": z.name, "capacity": z.capacity,
        "allowed_sizes": z.allowed_sizes.split(",") if z.allowed_sizes else [],
        "allowed_size_labels": [SIZE_LABELS.get(s, s) for s in (z.allowed_sizes.split(",") if z.allowed_sizes else [])],
        "requires_no_attack_history": z.requires_no_attack_history,
        "description": z.description, "active": z.active,
    }


def reservation_dict(r):
    return {
        "id": r.id, "code": r.code,
        "pet_id": r.pet_id, "pet_name": r.pet.name if r.pet else "",
        "pet_breed": r.pet.breed if r.pet else "",
        "owner_id": r.owner_id, "owner_name": r.owner.name if r.owner else "",
        "owner_phone": r.owner.phone if r.owner else "",
        # 预约绑定：犬只免疫状态、牵引规则、主人联系方式
        "vaccine_status": r.pet.vaccine_status if r.pet else "",
        "vaccine_label": VACCINE_LABELS.get(r.pet.vaccine_status, "") if r.pet else "",
        "leash_required": r.pet.leash_required if r.pet else True,
        "zone_id": r.zone_id, "zone_name": r.zone.name if r.zone else "",
        "visit_date": r.visit_date.isoformat(),
        "time_slot": r.time_slot, "time_slot_label": TIME_SLOTS.get(r.time_slot, r.time_slot),
        "status": r.status, "status_label": RESERVATION_STATUS.get(r.status, r.status),
        "result_reason": r.result_reason,
        "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
    }


def entry_check_dict(c):
    r = c.reservation
    return {
        "id": c.id, "reservation_id": c.reservation_id,
        "reservation_code": r.code if r else "",
        "pet_name": r.pet.name if r and r.pet else "",
        "owner_name": r.owner.name if r and r.owner else "",
        "zone_name": r.zone.name if r and r.zone else "",
        "staff_name": c.staff.name if c.staff else "",
        "check_time": c.check_time.strftime("%Y-%m-%d %H:%M") if c.check_time else "",
        "vaccine_ok": c.vaccine_ok, "license_ok": c.license_ok,
        "leash_ok": c.leash_ok, "identity_ok": c.identity_ok,
        "result": c.result, "result_label": CHECK_RESULT.get(c.result, c.result),
        "fail_reasons": c.fail_reasons,
        "allowed_area": c.allowed_area,
        "allowed_area_label": ALLOWED_AREA.get(c.allowed_area, c.allowed_area),
        "notes": c.notes,
    }


def incident_dict(i):
    return {
        "id": i.id, "code": i.code,
        "pet_id": i.pet_id, "pet_name": i.pet.name if i.pet else "",
        "pet_breed": i.pet.breed if i.pet else "",
        "related_pet_id": i.related_pet_id,
        "related_pet_name": i.related_pet.name if i.related_pet else "",
        "reporter_name": i.reporter.name if i.reporter else "",
        "zone_id": i.zone_id, "zone_name": i.zone.name if i.zone else "",
        "incident_type": i.incident_type,
        "incident_type_label": INCIDENT_TYPES.get(i.incident_type, i.incident_type),
        "severity": i.severity, "severity_label": SEVERITY_LABELS.get(i.severity, i.severity),
        "location": i.location,
        "description": i.description,
        "has_injury": i.has_injury, "owner_cooperative": i.owner_cooperative,
        "occurred_at": i.occurred_at.strftime("%Y-%m-%d %H:%M") if i.occurred_at else "",
        "event_id": i.event_id,
    }


def event_dict(e, db=None):
    d = {
        "id": e.id, "code": e.code, "title": e.title,
        "event_type": e.event_type,
        "event_type_label": EVENT_TYPES.get(e.event_type, e.event_type),
        "status": e.status, "status_label": EVENT_STATUS.get(e.status, e.status),
        "priority": e.priority, "priority_label": PRIORITY_LABELS.get(e.priority, e.priority),
        "zone_id": e.zone_id, "zone_name": e.zone.name if e.zone else "",
        "pet_id": e.pet_id, "pet_name": e.pet.name if e.pet else "",
        "owner_id": e.owner_id,
        "location": e.location,
        "description": e.description,
        "park_liability_percent": e.park_liability_percent,
        "park_liability_note": e.park_liability_note,
        "created_at": e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else "",
        "closed_at": e.closed_at.strftime("%Y-%m-%d %H:%M") if e.closed_at else None,
        "resolution_summary": e.resolution_summary,
    }
    if db is not None:
        from .models import User
        creator = db.get(User, e.created_by)
        d["creator_name"] = creator.name if creator else ""
        if e.owner_id:
            owner = db.get(User, e.owner_id)
            d["owner_name"] = owner.name if owner else ""
    return d


def blacklist_dict(b):
    return {
        "id": b.id,
        "pet_id": b.pet_id, "pet_name": b.pet.name if b.pet else "",
        "owner_id": b.owner_id, "owner_name": b.owner.name if b.owner else "",
        "level": b.level, "level_label": BLACKLIST_LEVELS.get(b.level, b.level),
        "reason": b.reason, "event_id": b.event_id, "active": b.active,
        "created_at": b.created_at.strftime("%Y-%m-%d %H:%M") if b.created_at else "",
        "lifted_at": b.lifted_at.strftime("%Y-%m-%d %H:%M") if b.lifted_at else None,
    }


def restriction_dict(r):
    return {
        "id": r.id, "pet_id": r.pet_id, "pet_name": r.pet.name if r.pet else "",
        "restriction_type": r.restriction_type,
        "restriction_label": RESTRICTION_TYPES.get(r.restriction_type, r.restriction_type),
        "reason": r.reason, "event_id": r.event_id, "active": r.active,
        "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
    }
