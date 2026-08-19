from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.models import UserRole
from app.schemas import VehicleCreate, VehicleUpdate, VehicleOut
from app.services.auth_service import require_roles

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.get("/", response_model=list[VehicleOut])
def get_vehicles(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DISPATCHER)),
):
    return db.query(models.Vehicle).all()


@router.get("/{vehicle_id}", response_model=VehicleOut)
def get_vehicle(
    vehicle_id: int, db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DISPATCHER)),
):
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@router.post("/", response_model=VehicleOut)
def create_vehicle(
    vehicle: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    if db.query(models.Vehicle).filter(models.Vehicle.registration_number == vehicle.registration_number).first():
        raise HTTPException(status_code=400, detail="A vehicle with this registration number already exists")

    db_vehicle = models.Vehicle(**vehicle.dict())
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle


@router.put("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(
    vehicle_id: int,
    update: VehicleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    update_data = update.dict(exclude_unset=True)
    if "registration_number" in update_data:
        existing = db.query(models.Vehicle).filter(
            models.Vehicle.registration_number == update_data["registration_number"],
            models.Vehicle.id != vehicle_id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="A vehicle with this registration number already exists")

    for field, value in update_data.items():
        setattr(vehicle, field, value)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}")
def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.status == models.VehicleStatus.ON_TRIP:
        raise HTTPException(status_code=400, detail="Cannot delete a vehicle that is currently on a trip")
    db.delete(vehicle)
    db.commit()
    return {"message": f"Vehicle {vehicle_id} deleted"}
