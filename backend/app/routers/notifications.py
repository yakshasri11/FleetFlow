from sqlalchemy import or_
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import NotificationOut
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _visible_to(current_user: models.User):
    return or_(
        models.Notification.user_id == current_user.id,
        models.Notification.role == current_user.role,
    )


@router.get("/", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Notification).filter(_visible_to(current_user))
    if unread_only:
        query = query.filter(models.Notification.is_read == "false")
    return query.order_by(models.Notification.created_at.desc()).all()


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    count = (
        db.query(models.Notification)
        .filter(_visible_to(current_user), models.Notification.is_read == "false")
        .count()
    )
    return {"unread_count": count}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    notification = (
        db.query(models.Notification)
        .filter(models.Notification.id == notification_id, _visible_to(current_user))
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = "true"
    db.commit()
    db.refresh(notification)
    return notification


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    updated = (
        db.query(models.Notification)
        .filter(_visible_to(current_user), models.Notification.is_read == "false")
        .update({"is_read": "true"}, synchronize_session=False)
    )
    db.commit()
    return {"marked_read": updated}
