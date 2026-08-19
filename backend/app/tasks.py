from datetime import datetime, timedelta

from app.celery_app import celery_app
from app.database import SessionLocal
from app import models
from app.models import MaintenanceStatus, UserRole, NotificationType
from app.services.notification_service import create_notification


@celery_app.task
def send_maintenance_reminders():
    """Checks for maintenance due within 3 days and sends a reminder.

    Duplicate-alert prevention: each record has a `reminder_sent` flag that
    only gets reset when its `next_service_date` changes, so a reminder for
    the same due date is never sent twice. Completed or archived records are
    excluded entirely, so reminders stop the moment maintenance is done.
    """
    db = SessionLocal()
    try:
        soon = datetime.utcnow() + timedelta(days=3)
        due = db.query(models.Maintenance).filter(
            models.Maintenance.next_service_date <= soon,
            models.Maintenance.status != MaintenanceStatus.COMPLETED,
            models.Maintenance.is_archived == "false",
            models.Maintenance.reminder_sent == "false",
        ).all()

        for record in due:
            print(f"[Maintenance Reminder] Vehicle {record.vehicle_id} — "
                  f"{record.category.value} due {record.next_service_date}")
            create_notification(
                db,
                type=NotificationType.MAINTENANCE_ALERT,
                title=f"Maintenance due soon: vehicle {record.vehicle_id}",
                message=f"{record.category.value} for vehicle {record.vehicle_id} is due {record.next_service_date}.",
                role=UserRole.FLEET_MANAGER,
                related_entity_type="maintenance",
                related_entity_id=record.id,
                commit=False,
            )
            record.reminder_sent = "true"

        db.commit()
        return f"{len(due)} reminder(s) sent"
    finally:
        db.close()
