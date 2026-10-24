from sqlalchemy.orm import Session
from datetime import datetime

try:
    from models import Notification
except ImportError:
    from backend.models import Notification


class AlertService:
    def create_notification(self, db: Session, user_id: int, title: str, message: str, level: str = "warning", category: str = "ALERT"):
        noti = Notification(
            user_id=user_id,
            title=title,
            message=message,
            level=level,
            category=category,
            read=False,
            is_read=False,
            created_at=datetime.utcnow()
        )
        db.add(noti)
        db.commit()
        db.refresh(noti)
        return noti

    def get_user_notifications(self, db: Session, user_id: int):
        return db.query(Notification).filter(Notification.user_id == user_id).order_by(Notification.created_at.desc()).all()

    def mark_read(self, db: Session, noti_id: int, user_id: int):
        noti = db.query(Notification).filter(Notification.id == noti_id, Notification.user_id == user_id).first()
        if noti:
            noti.read = True
            noti.is_read = True
            db.commit()
        return noti


alert_service = AlertService()
