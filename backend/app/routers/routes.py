from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.models import UserRole
from app.schemas import RouteOptimizeRequest, RouteOut
from app.services.auth_service import get_current_user, require_roles
from app.services.notification_service import create_notification
from app.services import maps_service

router = APIRouter(prefix="/routes", tags=["Route Optimization"])


@router.post("/optimize", response_model=RouteOut)
async def optimize_route(
    payload: RouteOptimizeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DISPATCHER)
    ),
):
    if payload.trip_id is not None:
        if not db.query(models.Trip).filter(models.Trip.id == payload.trip_id).first():
            raise HTTPException(status_code=400, detail=f"Trip ID {payload.trip_id} does not exist")

    result = await maps_service.get_route(payload.origin, payload.destination, payload.route_type)
    olat, olng, _ = await maps_service.geocode(payload.origin)
    dlat, dlng, _ = await maps_service.geocode(payload.destination)

    route = models.Route(
        trip_id=payload.trip_id,
        origin=payload.origin,
        destination=payload.destination,
        origin_lat=olat,
        origin_lng=olng,
        destination_lat=dlat,
        destination_lng=dlng,
        route_type=payload.route_type,
        distance_km=result["distance_km"],
        duration_minutes=result["duration_minutes"],
        traffic_delay_minutes=result["traffic_delay_minutes"],
        is_estimated="true" if result["is_estimated"] else "false",
        source=result["source"],
    )
    db.add(route)

    if payload.trip_id is not None:
        trip = db.query(models.Trip).filter(models.Trip.id == payload.trip_id).first()
        trip.total_distance_km = result["distance_km"]

    db.commit()
    db.refresh(route)
    return route


@router.get("/", response_model=list[RouteOut])
def list_routes(
    trip_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Route)
    if trip_id is not None:
        query = query.filter(models.Route.trip_id == trip_id)
    return query.order_by(models.Route.created_at.desc()).all()


@router.get("/{route_id}", response_model=RouteOut)
def get_route(route_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    route = db.query(models.Route).filter(models.Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


@router.post("/{route_id}/recalculate", response_model=RouteOut)
async def recalculate_route(
    route_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DISPATCHER)
    ),
):
    route = db.query(models.Route).filter(models.Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    result = await maps_service.get_route(route.origin, route.destination, route.route_type)
    old_distance = route.distance_km
    route.distance_km = result["distance_km"]
    route.duration_minutes = result["duration_minutes"]
    route.traffic_delay_minutes = result["traffic_delay_minutes"]
    route.is_estimated = "true" if result["is_estimated"] else "false"
    route.source = result["source"]
    route.recalculated_at = datetime.utcnow()

    create_notification(
        db,
        type=models.NotificationType.ROUTE_CHANGE,
        title="Route recalculated",
        message=(
            f"Route {route.id} ({route.origin} -> {route.destination}) recalculated: "
            f"{old_distance} km -> {route.distance_km} km, ETA {route.duration_minutes} min."
        ),
        role=UserRole.DISPATCHER,
        related_entity_type="route",
        related_entity_id=route.id,
        commit=False,
    )

    db.commit()
    db.refresh(route)
    return route
