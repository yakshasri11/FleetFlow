from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.models import UserRole
from app.schemas import DriverCreate, DriverUpdate, DriverOut
from app.services.auth_service import require_roles

router = APIRouter(prefix="/drivers", tags=["Drivers"])


@router.get("/", response_model=list[DriverOut])
def get_drivers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DISPATCHER)),
):
    return db.query(models.Driver).all()


@router.get("/me", response_model=DriverOut)
def get_my_driver_record(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DRIVER)),
):
    if not current_user.driver_id:
        raise HTTPException(status_code=403, detail="This account is not linked to a driver record")
    driver = db.query(models.Driver).filter(models.Driver.id == current_user.driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver record not found")
    return driver


@router.get("/{driver_id}", response_model=DriverOut)
def get_driver(
    driver_id: int, db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DISPATCHER)),
):
    driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


@router.post("/", response_model=DriverOut)
def create_driver(
    driver: DriverCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    if db.query(models.Driver).filter(models.Driver.license_number == driver.license_number).first():
        raise HTTPException(status_code=400, detail="A driver with this license number already exists")

    db_driver = models.Driver(**driver.dict())
    db.add(db_driver)
    db.commit()
    db.refresh(db_driver)
    return db_driver


@router.put("/{driver_id}", response_model=DriverOut)
def update_driver(
    driver_id: int,
    update: DriverUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    update_data = update.dict(exclude_unset=True)
    if "license_number" in update_data:
        existing = db.query(models.Driver).filter(
            models.Driver.license_number == update_data["license_number"],
            models.Driver.id != driver_id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="A driver with this license number already exists")

    for field, value in update_data.items():
        setattr(driver, field, value)
    db.commit()
    db.refresh(driver)
    return driver


@router.delete("/{driver_id}")
def delete_driver(
    driver_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER)),
):
    driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    if driver.status == "on_trip":
        raise HTTPException(status_code=400, detail="Cannot delete a driver who is currently on a trip")
    db.delete(driver)
    db.commit()
    return {"message": f"Driver {driver_id} deleted"}
