import os
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .config import UPLOAD_DIR
from .database import Base, SessionLocal, engine
from .routers import (activities, analytics, auth, blacklist, entry_checks,
                      events, incidents, pets, reservations, users, zones)
from .seed import seed_if_empty

app = FastAPI(title="城市宠物公园入园预约与冲突处置平台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    # 等待数据库就绪（compose 已配置 depends_on healthy，这里再做一层重试兜底）
    last_err = None
    for _ in range(30):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2)
    else:
        raise RuntimeError(f"数据库连接失败: {last_err}")

    Base.metadata.create_all(bind=engine)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()


app.mount("/api/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(pets.router, prefix="/api")
app.include_router(zones.router, prefix="/api")
app.include_router(reservations.router, prefix="/api")
app.include_router(entry_checks.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(blacklist.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(activities.router, prefix="/api")
