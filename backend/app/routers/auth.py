from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.models import UserRole
from app.schemas import UserCreate, UserOut, UserUpdate, Token, PasswordChange, AdminPasswordReset
from app.services.auth_service import (
    hash_password, verify_password, create_access_token, get_current_user, require_roles,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


def _check_unique(db: Session, username: str, email: str):
    if db.query(models.User).filter(models.User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")


@router.get("/bootstrap-status")
def bootstrap_status(db: Session = Depends(get_db)):
    """Public, no-auth endpoint — just tells the frontend whether the
    one-time first-admin registration is still available, so it can hide
    the Create Account tab once a real Admin exists."""
    return {"registration_open": db.query(models.User).count() == 0}


@router.post("/register", response_model=UserOut)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Open ONLY when the database has zero users — this is how the very
    first Admin account gets created on a fresh deployment. Every account
    after that must be created by an Admin via POST /auth/users."""
    if db.query(models.User).count() > 0:
        raise HTTPException(
            status_code=403,
            detail="Self-registration is disabled. Ask an administrator to create your account.",
        )
    _check_unique(db, payload.username, payload.email)
    user = models.User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=UserRole.ADMIN,  # the bootstrap account is always Admin, regardless of what was submitted
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if user.is_active != "true":
        raise HTTPException(status_code=403, detail="This account has been disabled")

    token = create_access_token({"sub": user.username, "role": user.role.value})
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.put("/me/password")
def change_own_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password updated"}


# ==================== Admin-only user management ====================

@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), current_user: models.User = Depends(require_roles(UserRole.ADMIN))):
    return db.query(models.User).order_by(models.User.id).all()


@router.post("/users", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN)),
):
    _check_unique(db, payload.username, payload.email)
    if payload.driver_id is not None:
        if not db.query(models.Driver).filter(models.Driver.id == payload.driver_id).first():
            raise HTTPException(status_code=400, detail=f"Driver ID {payload.driver_id} does not exist")
    user = models.User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        driver_id=payload.driver_id if payload.role == UserRole.DRIVER else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN)),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id and payload.role is not None and payload.role != UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="You cannot remove your own Admin role")
    if user.id == current_user.id and payload.is_active == "false":
        raise HTTPException(status_code=400, detail="You cannot disable your own account")

    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-password")
def admin_reset_password(
    user_id: int,
    payload: AdminPasswordReset,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.ADMIN)),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message": f"Password reset for {user.username}"}
