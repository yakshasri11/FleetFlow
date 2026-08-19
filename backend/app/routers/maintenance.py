from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.models import UserRole, VehicleStatus, MaintenanceStatus
from app.schemas import MaintenanceCreate, MaintenanceUpdate, MaintenanceOut
from app.services.auth_service import require_roles
from app.services.notification_service import create_notification

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])


@router.post("/", response_model=MaintenanceOut)
def create_maintenance(
    record: MaintenanceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == record.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=400, detail=f"Vehicle ID {record.vehicle_id} does not exist")

    db_record = models.Maintenance(**record.dict())
    db.add(db_record)
    vehicle.status = VehicleStatus.MAINTENANCE  # scheduling takes the vehicle out of rotation

    create_notification(
        db,
        type=models.NotificationType.MAINTENANCE_ALERT,
        title=f"Maintenance scheduled: {vehicle.registration_number}",
        message=f"{record.category.value} scheduled for {vehicle.registration_number} on {record.service_date}.",
        role=UserRole.FLEET_MANAGER,
        related_entity_type="maintenance",
        commit=False,
    )

    db.commit()
    db.refresh(db_record)
    return db_record


@router.get("/", response_model=list[MaintenanceOut])
def get_all_maintenance(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    return db.query(models.Maintenance).filter(models.Maintenance.is_archived == "false").all()


@router.get("/{maintenance_id}", response_model=MaintenanceOut)
def get_maintenance(
    maintenance_id: int, db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    record = db.query(models.Maintenance).filter(models.Maintenance.id == maintenance_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    return record


@router.put("/{maintenance_id}", response_model=MaintenanceOut)
def update_maintenance(
    maintenance_id: int,
    update: MaintenanceUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    record = db.query(models.Maintenance).filter(models.Maintenance.id == maintenance_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")

    update_data = update.dict(exclude_unset=True)
    if "next_service_date" in update_data:
        record.reminder_sent = "false"  # due date changed -> old reminder no longer applies

    for field, value in update_data.items():
        setattr(record, field, value)

    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == record.vehicle_id).first()
    if vehicle:
        if record.status == MaintenanceStatus.IN_PROGRESS:
            vehicle.status = VehicleStatus.MAINTENANCE
        elif record.status == MaintenanceStatus.COMPLETED:
            other_open = db.query(models.Maintenance).filter(
                models.Maintenance.vehicle_id == vehicle.id,
                models.Maintenance.id != record.id,
                models.Maintenance.status != MaintenanceStatus.COMPLETED,
                models.Maintenance.is_archived == "false",
            ).count()
            if other_open == 0:
                vehicle.status = VehicleStatus.AVAILABLE

    db.commit()
    db.refresh(record)
    return record


@router.delete("/{maintenance_id}")
def archive_maintenance(
    maintenance_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    """Soft delete only — maintenance history is never permanently removed."""
    record = db.query(models.Maintenance).filter(models.Maintenance.id == maintenance_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    record.is_archived = "true"
    db.commit()
    return {"message": f"Maintenance record {maintenance_id} archived (not deleted)"}
