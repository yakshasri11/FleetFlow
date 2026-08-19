from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app import models
from app.models import UserRole, NotificationType
from app.schemas import ShipmentCreate, ShipmentUpdate, ShipmentOut, StatusHistoryOut
from app.utils import generate_tracking_number
from app.services.auth_service import get_current_user, require_roles
from app.services.notification_service import create_notification
from app.services.status_history_service import record_status

router = APIRouter(prefix="/shipments", tags=["Shipments"])

# Created -> Assigned -> In Transit -> Delayed -> Delivered / Cancelled
_VALID_TRANSITIONS = {
    models.ShipmentStatus.CREATED: {models.ShipmentStatus.ASSIGNED, models.ShipmentStatus.CANCELLED},
    models.ShipmentStatus.ASSIGNED: {
        models.ShipmentStatus.IN_TRANSIT, models.ShipmentStatus.CANCELLED,
    },
    models.ShipmentStatus.IN_TRANSIT: {
        models.ShipmentStatus.DELAYED, models.ShipmentStatus.DELIVERED, models.ShipmentStatus.CANCELLED,
    },
    models.ShipmentStatus.DELAYED: {
        models.ShipmentStatus.IN_TRANSIT, models.ShipmentStatus.DELIVERED, models.ShipmentStatus.CANCELLED,
    },
    models.ShipmentStatus.DELIVERED: set(),
    models.ShipmentStatus.CANCELLED: set(),
}


def _enrich(shipment: models.Shipment) -> models.Shipment:
    if shipment.trip:
        shipment.driver_name = shipment.trip.driver.name if shipment.trip.driver else None
        shipment.vehicle_registration = shipment.trip.vehicle.registration_number if shipment.trip.vehicle else None
    else:
        shipment.driver_name = None
        shipment.vehicle_registration = None
    return shipment


@router.get("/", response_model=list[ShipmentOut])
def get_shipments(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    query = db.query(models.Shipment).options(
        joinedload(models.Shipment.trip).joinedload(models.Trip.driver),
        joinedload(models.Shipment.trip).joinedload(models.Trip.vehicle),
    ).filter(models.Shipment.deleted == "false")
    if current_user.role == UserRole.DRIVER:
        # A driver only ever sees shipments on their own trips — enforced
        # here at the query level, not just hidden in the UI.
        query = query.join(models.Trip, models.Shipment.trip_id == models.Trip.id).filter(
            models.Trip.driver_id == current_user.driver_id
        )
    return [_enrich(s) for s in query.order_by(models.Shipment.id.desc()).all()]


@router.get("/{shipment_id}", response_model=ShipmentOut)
def get_shipment(shipment_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    shipment = db.query(models.Shipment).filter(
        models.Shipment.id == shipment_id, models.Shipment.deleted == "false"
    ).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if current_user.role == UserRole.DRIVER:
        trip = db.query(models.Trip).filter(models.Trip.id == shipment.trip_id).first() if shipment.trip_id else None
        if not trip or trip.driver_id != current_user.driver_id:
            raise HTTPException(status_code=404, detail="Shipment not found")
    return _enrich(shipment)


@router.get("/{shipment_id}/history", response_model=list[StatusHistoryOut])
def get_shipment_history(shipment_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    shipment = db.query(models.Shipment).filter(models.Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if current_user.role == UserRole.DRIVER:
        trip = db.query(models.Trip).filter(models.Trip.id == shipment.trip_id).first() if shipment.trip_id else None
        if not trip or trip.driver_id != current_user.driver_id:
            raise HTTPException(status_code=404, detail="Shipment not found")
    return (
        db.query(models.StatusHistory)
        .filter(models.StatusHistory.entity_type == "shipment", models.StatusHistory.entity_id == shipment_id)
        .order_by(models.StatusHistory.changed_at.asc())
        .all()
    )


@router.post("/", response_model=ShipmentOut)
def create_shipment(
    shipment: ShipmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DISPATCHER)),
):
    db_shipment = models.Shipment(
        tracking_number=generate_tracking_number(),
        origin=shipment.origin,
        destination=shipment.destination,
    )
    db.add(db_shipment)
    db.commit()
    db.refresh(db_shipment)
    record_status(db, "shipment", db_shipment.id, models.ShipmentStatus.CREATED.value, current_user.id, commit=True)
    return _enrich(db_shipment)


@router.put("/{shipment_id}", response_model=ShipmentOut)
def update_shipment(
    shipment_id: int,
    update: ShipmentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DISPATCHER)
    ),
):
    shipment = db.query(models.Shipment).filter(models.Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    update_data = update.dict(exclude_unset=True)
    old_status = shipment.status
    old_dispatcher = shipment.dispatcher_user_id

    if "status" in update_data and update_data["status"] != old_status:
        new_status = update_data["status"]
        if new_status not in _VALID_TRANSITIONS.get(old_status, set()):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot move shipment from '{old_status.value}' to '{new_status.value}'",
            )

    for field, value in update_data.items():
        setattr(shipment, field, value)

    if "status" in update_data and update_data["status"] != old_status:
        record_status(db, "shipment", shipment.id, shipment.status.value, current_user.id)
        create_notification(
            db,
            type=models.NotificationType.SHIPMENT_STATUS,
            title=f"Shipment {shipment.tracking_number} — {shipment.status.value}",
            message=f"Shipment {shipment.tracking_number} moved from {old_status.value} to {shipment.status.value}.",
            role=UserRole.DISPATCHER if not shipment.dispatcher_user_id else None,
            user_id=shipment.dispatcher_user_id,
            related_entity_type="shipment",
            related_entity_id=shipment.id,
            commit=False,
        )
        if shipment.status == models.ShipmentStatus.DELAYED:
            create_notification(
                db,
                type=models.NotificationType.DELIVERY_UPDATE,
                title=f"Delayed: {shipment.tracking_number}",
                message=f"Shipment {shipment.tracking_number} ({shipment.origin} -> {shipment.destination}) is delayed.",
                role=UserRole.FLEET_MANAGER,
                related_entity_type="shipment",
                related_entity_id=shipment.id,
                commit=False,
            )

    # Assigning/changing a dispatcher notifies that dispatcher directly.
    if "dispatcher_user_id" in update_data and update_data["dispatcher_user_id"] != old_dispatcher and shipment.dispatcher_user_id:
        create_notification(
            db,
            type=NotificationType.DRIVER_ASSIGNMENT,
            title=f"Shipment Assigned to You — {shipment.tracking_number}",
            message=f"{shipment.tracking_number}: {shipment.origin} -> {shipment.destination}, status {shipment.status.value}.",
            user_id=shipment.dispatcher_user_id,
            related_entity_type="shipment",
            related_entity_id=shipment.id,
            commit=False,
        )

    db.commit()
    db.refresh(shipment)
    return _enrich(shipment)


@router.delete("/{shipment_id}")
def delete_or_cancel_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    """If the shipment is already Delivered or Cancelled, this permanently
    (soft-)deletes the record. Otherwise it cancels the shipment first —
    matching the UI's single Delete action to both cases without a second
    endpoint."""
    shipment = db.query(models.Shipment).filter(models.Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    if shipment.status in (models.ShipmentStatus.DELIVERED, models.ShipmentStatus.CANCELLED):
        shipment.deleted = "true"
        shipment.deleted_at = datetime.utcnow()
        shipment.deleted_by = current_user.id
        db.commit()
        return {"message": f"Shipment {shipment.tracking_number} deleted"}

    shipment.status = models.ShipmentStatus.CANCELLED
    record_status(db, "shipment", shipment.id, models.ShipmentStatus.CANCELLED.value, current_user.id)
    db.commit()
    return {"message": f"Shipment {shipment.tracking_number} cancelled"}
