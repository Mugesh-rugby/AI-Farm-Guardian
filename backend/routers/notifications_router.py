from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models, schemas
from auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=List[schemas.NotificationOut])
@router.get("/", response_model=List[schemas.NotificationOut])
def list_notifications(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user.id)
        .order_by(models.Notification.created_at.desc())
        .all()
    )


@router.put("/{notif_id}/read")
def mark_read(notif_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    notif = db.query(models.Notification).filter(models.Notification.id == notif_id, models.Notification.user_id == user.id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.read = True
    notif.is_read = True
    db.commit()
    return {"ok": True}


@router.put("/read-all")
def mark_all_read(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    db.query(models.Notification).filter(models.Notification.user_id == user.id).update({"read": True, "is_read": True})
    db.commit()
    return {"ok": True}
