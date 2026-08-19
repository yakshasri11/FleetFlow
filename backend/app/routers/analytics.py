from datetime import datetime, timedelta

from sqlalchemy import func
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.models import VehicleStatus, TripStatus, ShipmentStatus, MaintenanceStatus, UserRole
from app.schemas import FuelAnalyticsOut, FleetDashboardOut, OperationalAnalyticsOut
from app.services.auth_service import require_roles

router = APIRouter(tags=["Analytics"])


@router.get("/analytics/fuel", response_model=FuelAnalyticsOut)
def fuel_analytics(db: Session = Depends(get_db), current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DISPATCHER))):
    total_liters = db.query(func.coalesce(func.sum(models.FuelRecord.fuel_quantity_liters), 0.0)).scalar()
    total_cost = db.query(func.coalesce(func.sum(models.FuelRecord.fuel_cost), 0.0)).scalar()
    count = db.query(models.FuelRecord).count()
    avg = (total_liters / count) if count else 0.0

    by_vehicle = (
        db.query(models.FuelRecord.vehicle_id, func.sum(models.FuelRecord.fuel_quantity_liters).label("total"))
        .group_by(models.FuelRecord.vehicle_id).all()
    )
    highest = max(by_vehicle, key=lambda r: r.total, default=None)
    lowest = min(by_vehicle, key=lambda r: r.total, default=None)

    return FuelAnalyticsOut(
        total_fuel_consumed=total_liters,
        total_fuel_cost=total_cost,
        average_fuel_consumption=avg,
        vehicle_highest_usage=highest.vehicle_id if highest else None,
        vehicle_lowest_usage=lowest.vehicle_id if lowest else None,
    )


@router.get("/dashboard/fleet", response_model=FleetDashboardOut)
def fleet_dashboard(db: Session = Depends(get_db), current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DISPATCHER))):
    total_vehicles = db.query(models.Vehicle).count()
    active_vehicles = db.query(models.Vehicle).filter(
        models.Vehicle.status.in_([VehicleStatus.AVAILABLE, VehicleStatus.ON_TRIP])
    ).count()
    under_maintenance = db.query(models.Vehicle).filter(models.Vehicle.status == VehicleStatus.MAINTENANCE).count()

    total_drivers = db.query(models.Driver).count()
    available_drivers = db.query(models.Driver).filter(models.Driver.status == "available").count()
    assigned_drivers = db.query(models.Driver).filter(models.Driver.status == "on_trip").count()

    total_trips = db.query(models.Trip).filter(models.Trip.deleted == "false").count()
    completed_trips = db.query(models.Trip).filter(models.Trip.deleted == "false").filter(models.Trip.status == TripStatus.COMPLETED).count()

    active_shipments = db.query(models.Shipment).filter(models.Shipment.deleted == "false").filter(
        models.Shipment.status.in_([ShipmentStatus.ASSIGNED, ShipmentStatus.IN_TRANSIT])
    ).count()

    total_maintenance = db.query(models.Maintenance).filter(models.Maintenance.is_archived == "false").count()
    total_fuel = db.query(func.coalesce(func.sum(models.FuelRecord.fuel_quantity_liters), 0.0)).scalar()

    return FleetDashboardOut(
        total_vehicles=total_vehicles,
        active_vehicles=active_vehicles,
        vehicles_under_maintenance=under_maintenance,
        total_drivers=total_drivers,
        available_drivers=available_drivers,
        assigned_drivers=assigned_drivers,
        total_trips=total_trips,
        completed_trips=completed_trips,
        active_shipments=active_shipments,
        total_maintenance_records=total_maintenance,
        total_fuel_consumed=total_fuel,
    )


@router.get("/analytics/operations", response_model=OperationalAnalyticsOut)
def operational_analytics(db: Session = Depends(get_db), current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DISPATCHER))):
    total = db.query(models.Shipment).filter(models.Shipment.deleted == "false").count()
    successful = db.query(models.Shipment).filter(models.Shipment.deleted == "false").filter(models.Shipment.status == ShipmentStatus.DELIVERED).count()
    delayed = db.query(models.Shipment).filter(models.Shipment.deleted == "false").filter(models.Shipment.status == ShipmentStatus.DELAYED).count()
    cancelled = db.query(models.Shipment).filter(models.Shipment.deleted == "false").filter(models.Shipment.status == ShipmentStatus.CANCELLED).count()
    avg_distance = db.query(func.avg(models.Trip.total_distance_km)).scalar()

    delivered = db.query(models.Shipment).filter(models.Shipment.deleted == "false").filter(
        models.Shipment.status == ShipmentStatus.DELIVERED, models.Shipment.eta.isnot(None)
    ).all()
    deltas = [(s.eta - s.created_at).total_seconds() / 60 for s in delivered if s.eta and s.created_at]
    avg_delivery = sum(deltas) / len(deltas) if deltas else None

    return OperationalAnalyticsOut(
        total_deliveries=total,
        successful_deliveries=successful,
        delayed_deliveries=delayed,
        cancelled_deliveries=cancelled,
        average_trip_distance=avg_distance,
        average_delivery_time_minutes=avg_delivery,
    )


@router.get("/dashboard/charts")
def dashboard_charts(db: Session = Depends(get_db), current_user: models.User = Depends(require_roles(UserRole.ADMIN, UserRole.FLEET_MANAGER, UserRole.DISPATCHER))):
    """Real, live-calculated data for the 6 required dashboard charts.
    Grouped and shaped so the frontend can hand each series straight to
    Chart.js without further transformation."""

    # 1. Vehicle status distribution
    vehicle_status = {
        status.value: db.query(models.Vehicle).filter(models.Vehicle.status == status).count()
        for status in VehicleStatus
    }

    # 2. Shipment delivery performance (status distribution)
    shipment_status = {
        status.value: db.query(models.Shipment).filter(models.Shipment.deleted == "false").filter(models.Shipment.status == status).count()
        for status in ShipmentStatus
    }

    # 3. Fuel consumption over time (by day, last 14 days of data present)
    fuel_day = func.date(models.FuelRecord.fuel_date).label("day")
    fuel_rows = (
        db.query(fuel_day, func.sum(models.FuelRecord.fuel_quantity_liters).label("liters"))
        .group_by(fuel_day).order_by(fuel_day).all()
    )
    fuel_trend = [{"date": str(r.day), "liters": round(r.liters or 0, 1)} for r in fuel_rows]

    # 4. Fleet utilization trend — vehicles on trip vs total, by day, using
    #    trip start dates as a proxy for utilization on that day.
    trip_day = func.date(models.Trip.scheduled_start).label("day")
    trip_rows = (
        db.query(trip_day, func.count(models.Trip.id).label("trips"))
        .filter(models.Trip.scheduled_start.isnot(None))
        .group_by(trip_day).order_by(trip_day).all()
    )
    total_vehicles = db.query(models.Vehicle).count() or 1
    utilization_trend = [
        {"date": str(r.day), "utilization_percent": round(min(r.trips / total_vehicles, 1.0) * 100, 1)}
        for r in trip_rows
    ]

    # 5. Delivery / ETA performance — on-time vs delayed among delivered+delayed shipments
    delivered_count = shipment_status.get(ShipmentStatus.DELIVERED.value, 0)
    delayed_count = shipment_status.get(ShipmentStatus.DELAYED.value, 0)

    # 6. Maintenance overview — upcoming (due in next 7 days), overdue, completed
    upcoming = db.query(models.Maintenance).filter(
        models.Maintenance.status != MaintenanceStatus.COMPLETED,
        models.Maintenance.is_archived == "false",
        models.Maintenance.next_service_date >= datetime.utcnow(),
        models.Maintenance.next_service_date <= datetime.utcnow() + timedelta(days=7),
    ).count()
    overdue = db.query(models.Maintenance).filter(
        models.Maintenance.status != MaintenanceStatus.COMPLETED,
        models.Maintenance.is_archived == "false",
        models.Maintenance.next_service_date < datetime.utcnow(),
    ).count()
    completed = db.query(models.Maintenance).filter(
        models.Maintenance.status == MaintenanceStatus.COMPLETED,
    ).count()

    return {
        "vehicle_status_distribution": vehicle_status,
        "shipment_status_distribution": shipment_status,
        "fuel_consumption_trend": fuel_trend,
        "fleet_utilization_trend": utilization_trend,
        "delivery_eta_performance": {"delivered": delivered_count, "delayed": delayed_count},
        "maintenance_overview": {"upcoming": upcoming, "overdue": overdue, "completed": completed},
    }
