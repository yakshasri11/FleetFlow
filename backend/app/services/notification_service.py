from typing import Optional

from sqlalchemy.orm import Session

from app import models


def create_notification(
    db: Session,
    type: "models.NotificationType",
    title: str,
    message: str,
    user_id: Optional[int] = None,
    role: Optional["models.UserRole"] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[int] = None,
    commit: bool = True,
) -> models.Notification:
    """Creates a notification for one user (user_id) or every user of a role
    (role). This is a local/in-app implementation — it writes a row that the
    frontend polls/displays. It does NOT send email/SMS/push; wiring a real
    provider (SendGrid, Twilio, FCM) only needs credentials, the call site
    here would stay the same.
    """
    notification = models.Notification(
        user_id=user_id,
        role=role,
        type=type,
        title=title,
        message=message,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
    )
    db.add(notification)
    if commit:
        db.commit()
        db.refresh(notification)
    return notification


def find_driver_user_id(db: Session, driver_id: Optional[int]) -> Optional[int]:
    """A Driver record isn't itself a login — this finds the User account
    (if any) linked to it via User.driver_id, so a notification can target
    that specific driver instead of broadcasting to the whole Driver role."""
    if not driver_id:
        return None
    user = db.query(models.User).filter(models.User.driver_id == driver_id).first()
    return user.id if user else None
