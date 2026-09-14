import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://petpark:petpark123@localhost:5432/petpark",
)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/data/uploads")

# 入园时段定义
TIME_SLOTS = {
    "morning": "上午 09:00-12:00",
    "afternoon": "下午 13:00-17:00",
    "evening": "晚间 18:00-21:00",
}

# 角色定义
ROLES = {
    "owner": "宠物主人",
    "gate": "入园核验员",
    "patrol": "巡场员",
    "manager": "园区管理",
    "hospital": "合作医院",
    "service": "客服",
    "coach": "教练",
    "admin": "系统管理员",
}
