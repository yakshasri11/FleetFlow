from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.models import UserRole
from app.schemas import FuelRecordCreate, FuelRecordUpdate, FuelRecordOut
from app.services.auth_service import require_roles

router = APIRouter(prefix="/fuel", tags=["Fuel"])


def _validate_create(db: Session, payload: FuelRecordCreate):
    if not db.query(models.Vehicle).filter(models.Vehicle.id == payload.vehicle_id).first():
        raise HTTPException(status_code=400, detail=f"Vehicle ID {payload.vehicle_id} does not exist")
    if not db.query(models.Driver).filter(models.Driver.id == payload.driver_id).first():
        raise HTTPException(status_code=400, detail=f"Driver ID {payload.driver_id} does not exist")
    if payload.fuel_quantity_liters <= 0:
        raise HTTPException(status_code=400, detail="Fuel quantity must be greater than zero")
    if payload.fuel_cost <= 0:
        raise HTTPException(status_code=400, detail="Fuel cost must be greater than zero")


@router.post("/", response_model=FuelRecordOut)
def create_fuel_record(
    payload: FuelRecordCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DRIVER)),
):
    _validate_create(db, payload)
    record = models.FuelRecord(**payload.dict())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/", response_model=list[FuelRecordOut])
def get_all_fuel_records(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DRIVER)),
):
    query = db.query(models.FuelRecord)
    if current_user.role == UserRole.DRIVER:
        query = query.filter(models.FuelRecord.driver_id == current_user.driver_id)
    return query.order_by(models.FuelRecord.id.desc()).all()


@router.get("/{record_id}", response_model=FuelRecordOut)
def get_fuel_record(
    record_id: int, db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DRIVER)),
):
    record = db.query(models.FuelRecord).filter(models.FuelRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Fuel record not found")
    if current_user.role == UserRole.DRIVER and record.driver_id != current_user.driver_id:
        raise HTTPException(status_code=404, detail="Fuel record not found")
    return record


@router.put("/{record_id}", response_model=FuelRecordOut)
def update_fuel_record(
    record_id: int,
    update: FuelRecordUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    record = db.query(models.FuelRecord).filter(models.FuelRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Fuel record not found")

    update_data = update.dict(exclude_unset=True)
    if update_data.get("fuel_quantity_liters") is not None and update_data["fuel_quantity_liters"] <= 0:
        raise HTTPException(status_code=400, detail="Fuel quantity must be greater than zero")
    if update_data.get("fuel_cost") is not None and update_data["fuel_cost"] <= 0:
        raise HTTPException(status_code=400, detail="Fuel cost must be greater than zero")

    for field, value in update_data.items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{record_id}")
def delete_fuel_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    record = db.query(models.FuelRecord).filter(models.FuelRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Fuel record not found")
    db.delete(record)
    db.commit()
    return {"message": f"Fuel record {record_id} deleted"}
