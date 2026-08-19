from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.models import UserRole, VehicleStatus, AssignmentStatus, AttendanceStatus, TripStatus
from app.schemas import (
    DriverAssignmentCreate, DriverAssignmentUpdate, DriverAssignmentOut,
    DriverAttendanceCreate, DriverAttendanceOut, DriverPerformanceOut,
)
from app.services.auth_service import get_current_user, require_roles
from app.services.notification_service import create_notification

router = APIRouter(tags=["Driver Assignment"])


def _is_driver_on_leave_today(db: Session, driver_id: int) -> bool:
    today = datetime.utcnow().date()
    record = (
        db.query(models.DriverAttendance)
        .filter(models.DriverAttendance.driver_id == driver_id)
        .order_by(models.DriverAttendance.date.desc())
        .first()
    )
    return bool(record and record.status == AttendanceStatus.LEAVE and record.date.date() == today)


@router.post("/assignments/", response_model=DriverAssignmentOut)
def assign_driver(
    payload: DriverAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DISPATCHER)),
):
    driver = db.query(models.Driver).filter(models.Driver.id == payload.driver_id).first()
    if not driver:
        raise HTTPException(status_code=400, detail=f"Driver ID {payload.driver_id} does not exist")
    if driver.status != "available":
        raise HTTPException(status_code=400, detail=f"Driver {driver.id} already has an active assignment")
    if _is_driver_on_leave_today(db, driver.id):
        raise HTTPException(status_code=400, detail=f"Driver {driver.id} is on leave and cannot be assigned")

    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == payload.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=400, detail=f"Vehicle ID {payload.vehicle_id} does not exist")
    if vehicle.status == VehicleStatus.MAINTENANCE:
        raise HTTPException(status_code=400, detail=f"Vehicle {vehicle.id} is under maintenance and cannot be assigned")
    if vehicle.status != VehicleStatus.AVAILABLE:
        raise HTTPException(status_code=400, detail=f"Vehicle {vehicle.id} is not available (status: {vehicle.status.value})")

    assignment = models.DriverAssignment(**payload.dict())
    db.add(assignment)
    driver.status = "on_trip"
    vehicle.status = VehicleStatus.ON_TRIP

    create_notification(
        db,
        type=models.NotificationType.DRIVER_ASSIGNMENT,
        title=f"Driver {driver.name} assigned",
        message=f"{driver.name} was assigned to vehicle {vehicle.registration_number}.",
        role=UserRole.FLEET_MANAGER,
        related_entity_type="driver_assignment",
        related_entity_id=None,  # assigned after commit below
        commit=False,
    )

    db.commit()
    db.refresh(assignment)
    return assignment


@router.get("/assignments/", response_model=list[DriverAssignmentOut])
def view_assignments(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.DriverAssignment).all()


@router.put("/assignments/{assignment_id}", response_model=DriverAssignmentOut)
def update_assignment(
    assignment_id: int,
    update: DriverAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    assignment = db.query(models.DriverAssignment).filter(models.DriverAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    for field, value in update.dict(exclude_unset=True).items():
        setattr(assignment, field, value)

    if assignment.status in (AssignmentStatus.COMPLETED, AssignmentStatus.CANCELLED):
        driver = db.query(models.Driver).filter(models.Driver.id == assignment.driver_id).first()
        vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == assignment.vehicle_id).first()
        if driver:
            driver.status = "available"
        if vehicle and vehicle.status != VehicleStatus.MAINTENANCE:
            vehicle.status = VehicleStatus.AVAILABLE

    db.commit()
    db.refresh(assignment)
    return assignment


@router.delete("/assignments/{assignment_id}")
def remove_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    assignment = db.query(models.DriverAssignment).filter(models.DriverAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    driver = db.query(models.Driver).filter(models.Driver.id == assignment.driver_id).first()
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == assignment.vehicle_id).first()
    if driver:
        driver.status = "available"
    if vehicle and vehicle.status != VehicleStatus.MAINTENANCE:
        vehicle.status = VehicleStatus.AVAILABLE

    db.delete(assignment)
    db.commit()
    return {"message": f"Assignment {assignment_id} removed"}


@router.post("/attendance/", response_model=DriverAttendanceOut)
def create_attendance(
    payload: DriverAttendanceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    if not db.query(models.Driver).filter(models.Driver.id == payload.driver_id).first():
        raise HTTPException(status_code=400, detail=f"Driver ID {payload.driver_id} does not exist")

    record = models.DriverAttendance(**payload.dict())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/attendance/", response_model=list[DriverAttendanceOut])
def list_attendance(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.DriverAttendance).all()


@router.get("/driver/{driver_id}/performance", response_model=DriverPerformanceOut)
def driver_performance(driver_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not db.query(models.Driver).filter(models.Driver.id == driver_id).first():
        raise HTTPException(status_code=404, detail="Driver not found")

    trips = db.query(models.Trip).filter(models.Trip.driver_id == driver_id)
    return DriverPerformanceOut(
        driver_id=driver_id,
        total_trips=trips.count(),
        completed_trips=trips.filter(models.Trip.status == TripStatus.COMPLETED).count(),
        active_trips=trips.filter(models.Trip.status.in_([TripStatus.SCHEDULED, TripStatus.IN_PROGRESS])).count(),
        cancelled_trips=trips.filter(models.Trip.status == TripStatus.CANCELLED).count(),
    )
