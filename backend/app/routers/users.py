from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..models import User
from ..serializers import user_dict

router = APIRouter(prefix="/users", tags=["用户"])


@router.get("")
def list_users(role: str = "", db: Session = Depends(get_db),
               _: User = Depends(require_roles("manager", "admin", "gate", "patrol"))):
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    return [user_dict(u) for u in q.order_by(User.id).all()]
