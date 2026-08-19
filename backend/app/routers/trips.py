from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app import models
from app.models import UserRole, VehicleStatus, TripStatus, AttendanceStatus, NotificationType
from app.schemas import TripCreate, TripUpdate, TripOut, CompletionRequest, StatusHistoryOut
from app.services.auth_service import get_current_user, require_roles
from app.services.notification_service import create_notification, find_driver_user_id
from app.services.status_history_service import record_status

router = APIRouter(prefix="/trips", tags=["Trips"])


def _enrich(trip: models.Trip) -> models.Trip:
    trip.driver_name = trip.driver.name if trip.driver else None
    trip.vehicle_registration = trip.vehicle.registration_number if trip.vehicle else None
    return trip


def _require_own_driver_id(current_user: models.User) -> int:
    if current_user.role != UserRole.DRIVER or not current_user.driver_id:
        raise HTTPException(status_code=403, detail="This account is not linked to a driver record")
    return current_user.driver_id


def _driver_is_on_leave_today(db: Session, driver_id: int) -> bool:
    today = datetime.utcnow().date()
    record = (
        db.query(models.DriverAttendance)
        .filter(models.DriverAttendance.driver_id == driver_id)
        .order_by(models.DriverAttendance.date.desc())
        .first()
    )
    return bool(record and record.status == AttendanceStatus.LEAVE and record.date.date() == today)


def _notify_assignment(db: Session, trip: models.Trip, shipment, current_user: models.User):
    """Fires the 'New Shipment/Trip Assigned' notification to the driver's
    own linked User account (not a role-wide broadcast), plus the
    shipment's dispatcher if one is set (falls back to a Dispatcher-role
    broadcast so dispatch operations aren't left blind when no one specific
    is assigned yet)."""
    driver_user_id = find_driver_user_id(db, trip.driver_id)
    when = trip.scheduled_start.strftime("%Y-%m-%d %H:%M") if trip.scheduled_start else "unscheduled"
    detail = (
        f"Pickup: {shipment.origin if shipment else '-'} | "
        f"Destination: {shipment.destination if shipment else '-'} | "
        f"Vehicle: {trip.vehicle_registration or '-'} | Scheduled: {when}"
    )
    title = f"New {'Shipment' if shipment else 'Trip'} Assigned" + (f" — {shipment.tracking_number}" if shipment else f" — TRP-{trip.id}")

    if driver_user_id:
        create_notification(
            db, type=NotificationType.DRIVER_ASSIGNMENT, title=title, message=detail,
            user_id=driver_user_id, related_entity_type="trip", related_entity_id=trip.id, commit=False,
        )

    dispatcher_user_id = shipment.dispatcher_user_id if shipment else None
    create_notification(
        db, type=NotificationType.DRIVER_ASSIGNMENT, title=title, message=detail,
        user_id=dispatcher_user_id, role=None if dispatcher_user_id else UserRole.DISPATCHER,
        related_entity_type="trip", related_entity_id=trip.id, commit=False,
    )


@router.post("/", response_model=TripOut)
def create_trip(
    trip: TripCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DISPATCHER)),
):
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == trip.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=400, detail=f"Vehicle ID {trip.vehicle_id} does not exist")
    if vehicle.status == VehicleStatus.MAINTENANCE:
        raise HTTPException(status_code=400, detail=f"Vehicle {vehicle.id} is under maintenance and cannot be assigned to a trip")

    driver = db.query(models.Driver).filter(models.Driver.id == trip.driver_id).first()
    if not driver:
        raise HTTPException(status_code=400, detail=f"Driver ID {trip.driver_id} does not exist")

    active_trip = db.query(models.Trip).filter(
        models.Trip.driver_id == driver.id,
        models.Trip.status.in_([TripStatus.SCHEDULED, TripStatus.IN_PROGRESS]),
    ).first()
    if active_trip:
        raise HTTPException(status_code=400, detail=f"Driver {driver.id} already has an active trip and cannot receive another")

    if _driver_is_on_leave_today(db, driver.id):
        raise HTTPException(status_code=400, detail=f"Driver {driver.id} is on leave today and cannot be assigned")

    db_trip = models.Trip(
        driver_id=trip.driver_id,
        vehicle_id=trip.vehicle_id,
        scheduled_start=trip.scheduled_start,
        scheduled_end=trip.scheduled_end,
    )
    db.add(db_trip)

    # Reserve the driver/vehicle for this trip immediately
    driver.status = "on_trip"
    vehicle.status = VehicleStatus.ON_TRIP

    db.commit()
    db.refresh(db_trip)
    _enrich(db_trip)
    record_status(db, "trip", db_trip.id, TripStatus.SCHEDULED.value, current_user.id)

    shipment = None
    if trip.shipment_ids:
        db.query(models.Shipment).filter(models.Shipment.id.in_(trip.shipment_ids)).update(
            {"trip_id": db_trip.id, "status": models.ShipmentStatus.ASSIGNED}, synchronize_session=False
        )
        db.commit()
        db.refresh(db_trip)
        shipment = db.query(models.Shipment).filter(models.Shipment.id.in_(trip.shipment_ids)).first()
        if shipment:
            record_status(db, "shipment", shipment.id, models.ShipmentStatus.ASSIGNED.value, current_user.id)

    _notify_assignment(db, db_trip, shipment, current_user)
    db.commit()

    return _enrich(db_trip)


@router.get("/", response_model=list[TripOut])
def get_trips(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    query = db.query(models.Trip).options(
        joinedload(models.Trip.driver), joinedload(models.Trip.vehicle)
    ).filter(models.Trip.deleted == "false")
    if current_user.role == UserRole.DRIVER:
        # A driver only ever sees their own trips — enforced here, not just hidden in the UI.
        query = query.filter(models.Trip.driver_id == current_user.driver_id)
    return [_enrich(t) for t in query.order_by(models.Trip.id.desc()).all()]


@router.get("/{trip_id}", response_model=TripOut)
def get_trip(trip_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id, models.Trip.deleted == "false").first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if current_user.role == UserRole.DRIVER and trip.driver_id != current_user.driver_id:
        raise HTTPException(status_code=404, detail="Trip not found")
    return _enrich(trip)


@router.get("/{trip_id}/history", response_model=list[StatusHistoryOut])
def get_trip_history(trip_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if current_user.role == UserRole.DRIVER and trip.driver_id != current_user.driver_id:
        raise HTTPException(status_code=404, detail="Trip not found")
    return (
        db.query(models.StatusHistory)
        .filter(models.StatusHistory.entity_type == "trip", models.StatusHistory.entity_id == trip_id)
        .order_by(models.StatusHistory.changed_at.asc())
        .all()
    )


@router.put("/{trip_id}", response_model=TripOut)
def update_trip(
    trip_id: int,
    update: TripUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    changed_status = "status" in update.dict(exclude_unset=True)
    for field, value in update.dict(exclude_unset=True).items():
        setattr(trip, field, value)

    # Completing or cancelling a trip frees up the driver and vehicle again
    if trip.status in (TripStatus.COMPLETED, TripStatus.CANCELLED):
        driver = db.query(models.Driver).filter(models.Driver.id == trip.driver_id).first()
        vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == trip.vehicle_id).first()
        if driver:
            driver.status = "available"
        if vehicle and vehicle.status != VehicleStatus.MAINTENANCE:
            vehicle.status = VehicleStatus.AVAILABLE

        if trip.status == TripStatus.COMPLETED:
            db.query(models.Shipment).filter(models.Shipment.trip_id == trip.id).update(
                {"status": models.ShipmentStatus.DELIVERED}, synchronize_session=False
            )

    if changed_status:
        record_status(db, "trip", trip.id, trip.status.value, current_user.id)

    db.commit()
    db.refresh(trip)
    return _enrich(trip)


@router.delete("/{trip_id}")
def delete_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    """Soft-deletes a trip. Only completed or cancelled trips can be
    deleted — an active trip must be cancelled/completed first."""
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.status not in (TripStatus.COMPLETED, TripStatus.CANCELLED):
        raise HTTPException(status_code=400, detail="Only completed or cancelled trips can be deleted")
    trip.deleted = "true"
    trip.deleted_at = datetime.utcnow()
    trip.deleted_by = current_user.id
    db.commit()
    return {"message": f"Trip {trip_id} deleted"}


def _get_own_trip_or_403(db: Session, trip_id: int, current_user: models.User) -> models.Trip:
    driver_id = _require_own_driver_id(current_user)
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.driver_id != driver_id:
        raise HTTPException(status_code=403, detail="This trip is not assigned to you")
    return trip


@router.post("/{trip_id}/start", response_model=TripOut)
def start_trip(
    trip_id: int, db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DRIVER)),
):
    trip = _get_own_trip_or_403(db, trip_id, current_user)
    if trip.status != TripStatus.SCHEDULED:
        raise HTTPException(status_code=400, detail=f"Trip must be Scheduled to start (currently {trip.status.value})")
    trip.status = TripStatus.IN_PROGRESS
    trip.actual_start = datetime.utcnow()
    db.query(models.Shipment).filter(models.Shipment.trip_id == trip.id).update(
        {"status": models.ShipmentStatus.IN_TRANSIT}, synchronize_session=False
    )
    record_status(db, "trip", trip.id, TripStatus.IN_PROGRESS.value, current_user.id)
    shipment = db.query(models.Shipment).filter(models.Shipment.trip_id == trip.id).first()
    if shipment:
        record_status(db, "shipment", shipment.id, models.ShipmentStatus.IN_TRANSIT.value, current_user.id)
    db.commit()
    db.refresh(trip)
    return _enrich(trip)


@router.post("/{trip_id}/arrive", response_model=TripOut)
def mark_arrived(
    trip_id: int, db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DRIVER)),
):
    trip = _get_own_trip_or_403(db, trip_id, current_user)
    if trip.status != TripStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Trip must be In Progress to mark arrival")
    trip.actual_arrival = datetime.utcnow()
    record_status(db, "trip", trip.id, "arrived", current_user.id)
    db.commit()
    db.refresh(trip)
    return _enrich(trip)


@router.post("/{trip_id}/complete", response_model=TripOut)
def complete_delivery(
    trip_id: int,
    payload: CompletionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DRIVER)),
):
    trip = _get_own_trip_or_403(db, trip_id, current_user)
    if trip.status != TripStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Trip must be In Progress to complete")
    trip.status = TripStatus.COMPLETED
    trip.actual_end = datetime.utcnow()

    driver = db.query(models.Driver).filter(models.Driver.id == trip.driver_id).first()
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == trip.vehicle_id).first()
    if driver:
        driver.status = "available"
    if vehicle and vehicle.status != VehicleStatus.MAINTENANCE:
        vehicle.status = VehicleStatus.AVAILABLE

    shipment = db.query(models.Shipment).filter(models.Shipment.trip_id == trip.id).first()
    if shipment:
        shipment.status = models.ShipmentStatus.DELIVERED
        shipment.completed_at = datetime.utcnow()
        shipment.completed_by = current_user.id
        shipment.completion_note = payload.completion_note
        shipment.completion_lat = payload.completion_lat
        shipment.completion_lng = payload.completion_lng
        record_status(db, "shipment", shipment.id, models.ShipmentStatus.DELIVERED.value, current_user.id)

        # Notify Manager/Admin, and the responsible Dispatcher (or a
        # role-wide broadcast if none is specifically assigned).
        completion_msg = (
            f"{shipment.tracking_number} was successfully completed by "
            f"{driver.name if driver else 'the driver'}. Completion note: {payload.completion_note}"
        )
        create_notification(
            db, type=NotificationType.DELIVERY_UPDATE, title=f"Shipment Completed — {shipment.tracking_number}",
            message=completion_msg, role=UserRole.FLEET_MANAGER,
            related_entity_type="shipment", related_entity_id=shipment.id, commit=False,
        )
        create_notification(
            db, type=NotificationType.DELIVERY_UPDATE, title=f"Shipment Completed — {shipment.tracking_number}",
            message=completion_msg, role=UserRole.ADMIN,
            related_entity_type="shipment", related_entity_id=shipment.id, commit=False,
        )
        dispatcher_msg = f"TRP-{trip.id} ({shipment.tracking_number}) has been completed by {driver.name if driver else 'the driver'}."
        create_notification(
            db, type=NotificationType.DELIVERY_UPDATE, title=f"Trip Completed — TRP-{trip.id}",
            message=dispatcher_msg,
            user_id=shipment.dispatcher_user_id, role=None if shipment.dispatcher_user_id else UserRole.DISPATCHER,
            related_entity_type="trip", related_entity_id=trip.id, commit=False,
        )

    record_status(db, "trip", trip.id, "completed", current_user.id)
    db.commit()
    db.refresh(trip)
    return _enrich(trip)
