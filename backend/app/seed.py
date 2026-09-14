"""种子数据：首次启动时写入演示账号、分区、宠物、预约与一桩已关闭的示例事件。"""
from datetime import date, datetime, timedelta

from .models import (
    Activity, ActivityRegistration, ActivityRestriction, BlacklistEntry,
    Compensation, ConflictParty, Event, EventParticipant, EventUpdate,
    FacilityRectification, Incident, MedicalRecord, OperationRecord, Pet,
    Reservation, Settlement, User, Zone,
)
from .security import hash_password


def size_of(weight: float) -> str:
    if weight < 10:
        return "small"
    if weight <= 25:
        return "medium"
    return "large"


def seed_if_empty(db):
    if db.query(User).count() > 0:
        return

    today = date.today()

    # ---------- 用户 ----------
    users = [
        ("admin", "admin123", "admin", "系统管理员", "13800000001"),
        ("owner1", "owner123", "owner", "张伟", "13800000002"),
        ("owner2", "owner123", "owner", "李芳", "13800000003"),
        ("gate1", "gate123", "gate", "王强", "13800000004"),
        ("patrol1", "patrol123", "patrol", "赵敏", "13800000005"),
        ("manager1", "manager123", "manager", "陈静", "13800000006"),
        ("hospital1", "hospital123", "hospital", "刘医生(宠安医院)", "13800000007"),
        ("service1", "service123", "service", "周婷", "13800000008"),
        ("coach1", "coach123", "coach", "刘教练", "13800000009"),
    ]
    objs = {}
    for username, pwd, role, name, phone in users:
        u = User(username=username, password_hash=hash_password(pwd), role=role, name=name, phone=phone)
        db.add(u)
        objs[username] = u
    db.flush()

    # ---------- 分区 ----------
    zones = [
        ("large_dog", "大型犬区", 20, "large", False, "体重大于 25kg 的大型犬活动场地，配备加固围栏。"),
        ("small_dog", "小型犬区", 30, "small,medium", False, "25kg 及以下中小型犬活动场地。"),
        ("social", "社交区", 25, "small,medium,large", True, "全体型混养社交场地，有攻击史的宠物禁止进入。"),
        ("training", "训练区", 15, "small,medium,large", False, "服从训练与行为矫正场地。"),
        ("activity", "活动区", 40, "small,medium,large", False, "举办宠物运动会、主题活动的场地，活动报名即预约本区。"),
    ]
    zobjs = {}
    for code, name, cap, sizes, no_attack, desc in zones:
        z = Zone(code=code, name=name, capacity=cap, allowed_sizes=sizes,
                 requires_no_attack_history=no_attack, description=desc)
        db.add(z)
        zobjs[code] = z
    db.flush()

    # ---------- 宠物 ----------
    def mkpet(owner, name, breed, weight, vaccine_status, vaccine_expiry, rabies,
              sterilized, attack, attack_desc, leash, license_no, license_expiry, notes=""):
        p = Pet(owner_id=objs[owner].id, name=name, breed=breed, weight_kg=weight,
                size_category=size_of(weight), vaccine_status=vaccine_status,
                vaccine_expiry=vaccine_expiry, rabies_vaccine_no=rabies,
                sterilized=sterilized, attack_history=attack, attack_history_desc=attack_desc,
                leash_required=leash, dog_license_no=license_no,
                license_expiry=license_expiry, notes=notes)
        db.add(p)
        return p

    doudou = mkpet("owner1", "豆豆", "泰迪", 6.5, "valid", today + timedelta(days=230),
                   "RV2026-0001", True, False, "", True, "DL-2026-0001",
                   today + timedelta(days=300), "性格温顺")
    dahuang = mkpet("owner1", "大黄", "金毛寻回犬", 30, "valid", today + timedelta(days=80),
                    "RV2026-0002", False, False, "", True, "DL-2026-0002",
                    today + timedelta(days=200))
    qiuqiu = mkpet("owner2", "球球", "柯基", 12, "expired", today - timedelta(days=100),
                   "RV2025-0003", True, False, "", True, "DL-2025-0003",
                   today + timedelta(days=100), "疫苗已过期，待补种")
    heibao = mkpet("owner2", "黑豹", "杜宾犬", 38, "valid", today + timedelta(days=60),
                   "RV2026-0004", False, True, "2026年5月曾追咬流浪猫，已接受行为训练",
                   True, "DL-2026-0004", today + timedelta(days=150))
    db.flush()

    # ---------- 今日预约（供入园核验演示） ----------
    def mkres(pet, owner, zone, day, slot, status="confirmed", reason=""):
        r = Reservation(code=f"R{day.strftime('%Y%m%d')}{pet.id}{zone.id}{slot[:2].upper()}",
                        pet_id=pet.id, owner_id=objs[owner].id, zone_id=zone.id,
                        visit_date=day, time_slot=slot, status=status, result_reason=reason)
        db.add(r)
        return r

    mkres(doudou, "owner1", zobjs["small_dog"], today, "morning")
    mkres(dahuang, "owner1", zobjs["large_dog"], today, "morning")
    mkres(qiuqiu, "owner2", zobjs["social"], today, "afternoon")   # 疫苗过期 -> 核验将不通过
    mkres(heibao, "owner2", zobjs["training"], today, "afternoon")
    mkres(doudou, "owner1", zobjs["activity"], today + timedelta(days=1), "evening")
    db.flush()

    # ---------- 历史巡场记录（供复盘分析演示） ----------
    def mkincident(pet, zone, itype, severity, desc, days_ago, has_injury=False,
                   cooperative=True, event_id=None):
        i = Incident(code=f"I{(today - timedelta(days=days_ago)).strftime('%Y%m%d')}{pet.id}{itype[:4].upper()}",
                     pet_id=pet.id, reporter_id=objs["patrol1"].id, zone_id=zone.id,
                     incident_type=itype, severity=severity, description=desc,
                     has_injury=has_injury, owner_cooperative=cooperative,
                     occurred_at=datetime.utcnow() - timedelta(days=days_ago, hours=3),
                     event_id=event_id)
        db.add(i)
        return i

    mkincident(doudou, zobjs["social"], "chasing", "low", "追逐其他小型犬，主人及时制止", 20)
    mkincident(dahuang, zobjs["large_dog"], "barking", "low", "持续吠叫，劝导后缓解", 18)
    mkincident(dahuang, zobjs["social"], "toy_fight", "medium", "与边牧争抢飞盘，未造成伤害", 12)
    mkincident(qiuqiu, zobjs["activity"], "waste", "low", "主人未及时清理粪便，已现场劝导", 9)
    mkincident(heibao, zobjs["training"], "chasing", "medium", "训练中追逐牵引绳，情绪亢奋", 6)
    mkincident(dahuang, zobjs["activity"], "equipment_damage", "medium", "撞坏活动区隔离栏一根", 4)

    # ---------- 一桩已关闭的冲突事件（完整处置链演示） ----------
    ev = Event(code="E-SEED-0001", title="黑豹社交区咬伤豆豆事件", event_type="pet_conflict",
               status="closed", priority="high", zone_id=zobjs["social"].id,
               pet_id=heibao.id, owner_id=objs["owner2"].id,
               location="社交区东侧围栏旁",
               description="黑豹在社交区与豆豆争抢玩具时发生撕咬，豆豆左前腿受伤。",
               created_by=objs["patrol1"].id,
               created_at=datetime.utcnow() - timedelta(days=15),
               closed_at=datetime.utcnow() - timedelta(days=13),
               closed_by=objs["manager1"].id,
               resolution_summary="医疗处置完成，按责任认定 80:20 结算，李芳赔付张伟 640 元；黑豹列入警告级黑名单并限制进入社交区、入园需佩戴嘴套；社交区隔离网完成加固整改。")
    db.add(ev)
    db.flush()

    inc = mkincident(heibao, zobjs["social"], "bite", "critical",
                     "黑豹撕咬豆豆左前腿，现场止血后送医", 15, has_injury=True, event_id=ev.id)
    inc.related_pet_id = doudou.id
    inc.location = "社交区东侧围栏旁"

    for uid, role in [(objs["patrol1"].id, "patrol"), (objs["manager1"].id, "manager"),
                      (objs["owner2"].id, "owner"), (objs["owner1"].id, "owner"),
                      (objs["hospital1"].id, "hospital"), (objs["service1"].id, "service")]:
        db.add(EventParticipant(event_id=ev.id, user_id=uid, participant_role=role))

    db.add_all([
        EventUpdate(event_id=ev.id, actor_id=objs["patrol1"].id, action="上报事件",
                    content="巡场发现撕咬，立即隔离双方并上报", created_at=datetime.utcnow() - timedelta(days=15, hours=-1)),
        EventUpdate(event_id=ev.id, actor_id=objs["manager1"].id, action="园区介入",
                    content="园区管理到场取证，调取监控并联系双方主人", created_at=datetime.utcnow() - timedelta(days=15, hours=-3)),
        EventUpdate(event_id=ev.id, actor_id=objs["service1"].id, action="客服跟进",
                    content="客服与双方主人沟通赔付方案，达成一致", created_at=datetime.utcnow() - timedelta(days=14)),
    ])
    db.add(MedicalRecord(event_id=ev.id, pet_id=doudou.id, patient_type="pet",
                         patient_name="豆豆", hospital_user_id=objs["hospital1"].id,
                         injury_desc="左前腿撕裂伤，深约 1.5cm", treatment="清创缝合 4 针，注射破伤风与抗生素",
                         cost=800, treated_at=datetime.utcnow() - timedelta(days=15, hours=-5)))
    # 冲突双方档案（含责任认定结果）
    db.add(ConflictParty(event_id=ev.id, pet_id=heibao.id, owner_id=objs["owner2"].id,
                         leash_compliant=False,
                         owner_statement="黑豹当时被多只犬围观受到惊吓，平时不这样",
                         statement_at=datetime.utcnow() - timedelta(days=15, hours=-2),
                         responsibility_percent=80, entry_sanction="warning",
                         determination="未佩戴嘴套且有攻击史，负主要责任"))
    db.add(ConflictParty(event_id=ev.id, pet_id=doudou.id, owner_id=objs["owner1"].id,
                         leash_compliant=True,
                         owner_statement="豆豆正常玩耍，被黑豹突然扑咬",
                         statement_at=datetime.utcnow() - timedelta(days=15, hours=-2),
                         responsibility_percent=20, entry_sanction="none",
                         determination="争抢玩具有一定诱因，负次要责任"))
    db.add(Compensation(event_id=ev.id, payer_owner_id=objs["owner2"].id, payee_name="张伟",
                        amount=640, reason="事件结算：责任 80% 方补付医疗费", status="paid",
                        handled_by=objs["service1"].id,
                        created_at=datetime.utcnow() - timedelta(days=14),
                        resolved_at=datetime.utcnow() - timedelta(days=13)))
    db.add(Settlement(event_id=ev.id, medical_total=800,
                      detail="责任比例 黑豹 80% : 豆豆 20%；医疗费合计 800.00 元，黑豹方承担 640.00 元、豆豆方承担 160.00 元；豆豆方已付 800.00 元。结算：李芳 应向 张伟 支付 640.00 元。",
                      created_by=objs["manager1"].id,
                      created_at=datetime.utcnow() - timedelta(days=14)))
    db.add(BlacklistEntry(pet_id=heibao.id, owner_id=objs["owner2"].id, level="warning",
                          reason="社交区咬伤事件，警告一次", event_id=ev.id, active=True,
                          created_by=objs["manager1"].id,
                          created_at=datetime.utcnow() - timedelta(days=13)))
    db.add(ActivityRestriction(pet_id=heibao.id, restriction_type="no_social_zone",
                               reason="咬伤事件后禁止进入社交区", event_id=ev.id, active=True,
                               created_at=datetime.utcnow() - timedelta(days=13)))
    db.add(ActivityRestriction(pet_id=heibao.id, restriction_type="muzzle_required",
                               reason="入园需佩戴嘴套", event_id=ev.id, active=True,
                               created_at=datetime.utcnow() - timedelta(days=13)))
    db.add(FacilityRectification(event_id=ev.id, zone_id=zobjs["social"].id,
                                 issue="社交区隔离网高度不足，大型犬可跃入小型犬活动带",
                                 action="隔离网加高至 1.8m 并增设双层缓冲带", status="done",
                                 created_at=datetime.utcnow() - timedelta(days=14),
                                 completed_at=datetime.utcnow() - timedelta(days=13)))
    db.add(OperationRecord(record_type="event_closure", title="事件 E-SEED-0001 关闭归档",
                           content="黑豹咬伤事件处置完毕：医疗 800 元、按 80:20 责任结算赔付 640 元完成、黑豹警告+限制社交区+需戴嘴套、社交区隔离网整改完成。",
                           related_event_id=ev.id, created_by=objs["manager1"].id,
                           created_at=datetime.utcnow() - timedelta(days=13)))

    # ---------- 活动（飞盘/训练课）与报名 ----------
    frisbee = Activity(title="周末飞盘友谊赛", activity_type="frisbee",
                       activity_date=today, time_slot="evening", intensity="high",
                       allowed_sizes="medium,large", capacity=4, coach_count=2,
                       pets_per_coach=3, coach_names="刘教练,王助教",
                       insurance_policy_no="INS-2026-0901",
                       created_by=objs["manager1"].id)
    training = Activity(title="服从训练基础课", activity_type="training_course",
                        activity_date=today + timedelta(days=1), time_slot="morning",
                        intensity="medium", allowed_sizes="small,medium,large",
                        capacity=10, coach_count=1, pets_per_coach=10,
                        coach_names="刘教练", insurance_policy_no="INS-2026-0902",
                        created_by=objs["manager1"].id)
    db.add_all([frisbee, training])
    db.flush()

    # 飞盘赛报名（高强度不接受攻击史宠物，黑豹不可报；有效容量 min(4, 2*3)=4）
    db.add(ActivityRegistration(activity_id=frisbee.id, pet_id=dahuang.id,
                                owner_id=dahuang.owner_id, status="registered"))
    db.add(ActivityRegistration(activity_id=training.id, pet_id=doudou.id,
                                owner_id=doudou.owner_id, status="registered"))

    db.commit()
    print("[seed] 演示数据初始化完成")
