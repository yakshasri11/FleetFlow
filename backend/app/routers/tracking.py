from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.models import UserRole, TripStatus
from app.schemas import LocationUpdate, LocationOut, TripTrackingOut
from app.services.auth_service import get_current_user, require_roles

router = APIRouter(prefix="/tracking", tags=["Live Tracking"])


@router.post("/location", response_model=LocationOut)
def submit_location(
    payload: LocationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DRIVER)),
):
    """A Driver submits their own current location for their own active
    trip. Enforced server-side — a driver cannot submit a location for a
    trip that isn't theirs, no matter what trip_id they send."""
    if not current_user.driver_id:
        raise HTTPException(status_code=403, detail="This account is not linked to a driver record")

    trip = db.query(models.Trip).filter(models.Trip.id == payload.trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.driver_id != current_user.driver_id:
        raise HTTPException(status_code=403, detail="This trip is not assigned to you")

    shipment = db.query(models.Shipment).filter(models.Shipment.trip_id == trip.id).first()

    location = models.DriverLocation(
        driver_id=current_user.driver_id,
        trip_id=trip.id,
        shipment_id=shipment.id if shipment else None,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


def _build_tracking_out(db: Session, trip: models.Trip) -> TripTrackingOut:
    shipment = db.query(models.Shipment).filter(models.Shipment.trip_id == trip.id).first()
    latest = (
        db.query(models.DriverLocation)
        .filter(models.DriverLocation.trip_id == trip.id)
        .order_by(models.DriverLocation.recorded_at.desc())
        .first()
    )
    seconds_since = None
    if latest:
        seconds_since = max(int((datetime.utcnow() - latest.recorded_at).total_seconds()), 0)

    return TripTrackingOut(
        trip_id=trip.id,
        shipment_id=shipment.id if shipment else None,
        tracking_number=shipment.tracking_number if shipment else None,
        driver_name=trip.driver.name if trip.driver else None,
        vehicle_registration=trip.vehicle.registration_number if trip.vehicle else None,
        status=trip.status.value,
        origin=shipment.origin if shipment else None,
        destination=shipment.destination if shipment else None,
        latest_latitude=latest.latitude if latest else None,
        latest_longitude=latest.longitude if latest else None,
        last_updated=latest.recorded_at if latest else None,
        seconds_since_update=seconds_since,
        has_live_location=latest is not None,
    )


@router.get("/trip/{trip_id}", response_model=TripTrackingOut)
def get_trip_tracking(
    trip_id: int, db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if current_user.role == UserRole.DRIVER and trip.driver_id != current_user.driver_id:
        raise HTTPException(status_code=404, detail="Trip not found")
    return _build_tracking_out(db, trip)


@router.get("/active", response_model=list[TripTrackingOut])
def get_active_tracking(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DISPATCHER, UserRole.DRIVER)
    ),
):
    """Active trips with their latest known location — this is what powers
    the Dispatcher/Manager 'Active Trips' table and the Live Tracking map.
    A Driver only ever gets their own trips back, enforced here."""
    query = db.query(models.Trip).filter(
        models.Trip.status.in_([TripStatus.SCHEDULED, TripStatus.IN_PROGRESS]),
        models.Trip.deleted == "false",
    )
    if current_user.role == UserRole.DRIVER:
        query = query.filter(models.Trip.driver_id == current_user.driver_id)
    trips = query.all()
    return [_build_tracking_out(db, t) for t in trips]
