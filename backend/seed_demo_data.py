"""Seeds FleetFlow with demo data: one login per role (including 2 Drivers,
each linked to their own Driver record so data isolation actually works),
plus two realistic, named shipment examples with real coordinates so the
tracking map and dashboard are meaningful immediately.

Usage:
    cd backend
    python seed_demo_data.py            # adds demo data (safe to re-run)
    python seed_demo_data.py --reset    # WIPES all operational data first,
                                         # then reseeds fresh demo data

--reset drops every row from every operational table AND every user
account, then recreates them. This is meant for demo/dev databases only —
never run it against a database with real production data.
"""
import argparse
import sys
from datetime import datetime, timedelta

from app.database import Base, engine, SessionLocal
from app import models
from app.services.auth_service import hash_password

# Real-world coordinates for the demo locations used below.
LOCATIONS = {
    "Chennai International Airport": (12.9941, 80.1709),
    "Bengaluru": (12.9716, 77.5946),
    "Hyderabad": (17.3850, 78.4867),
    "Chennai": (13.0827, 80.2707),
    "Vijayawada": (16.5062, 80.6480),
    "Warangal": (17.9689, 79.5941),
}

OPERATIONAL_TABLES = [
    models.Notification, models.Route, models.FuelRecord, models.DriverAttendance,
    models.DriverAssignment, models.Maintenance, models.Shipment, models.Trip,
    models.Driver, models.Vehicle,
]


def reset(db):
    print("Resetting operational tables and users...")
    for model in OPERATIONAL_TABLES:
        db.query(model).delete()
    db.query(models.User).delete()
    db.commit()


def seed_drivers_and_users(db):
    """2 named drivers, each with their own Driver record AND their own
    linked User login — this link is what makes driver data isolation
    actually work at the API level, not just in the UI."""
    driver1 = models.Driver(name="Driver Demo 1", license_number="DLDEMO001", phone="9000000001", status="on_trip")
    driver2 = models.Driver(name="Driver Demo 2", license_number="DLDEMO002", phone="9000000002", status="on_trip")
    db.add_all([driver1, driver2])
    db.flush()

    users = [
        models.User(username="admin_demo", email="admin@fleetflow-demo.com",
                    hashed_password=hash_password("Demo@1234"), role=models.UserRole.ADMIN),
        models.User(username="manager_demo", email="manager@fleetflow-demo.com",
                    hashed_password=hash_password("Demo@1234"), role=models.UserRole.FLEET_MANAGER),
        models.User(username="dispatcher_demo", email="dispatcher@fleetflow-demo.com",
                    hashed_password=hash_password("Demo@1234"), role=models.UserRole.DISPATCHER),
        models.User(username="driver1_demo", email="driver1@fleetflow-demo.com",
                    hashed_password=hash_password("Demo@1234"), role=models.UserRole.DRIVER, driver_id=driver1.id),
        models.User(username="driver2_demo", email="driver2@fleetflow-demo.com",
                    hashed_password=hash_password("Demo@1234"), role=models.UserRole.DRIVER, driver_id=driver2.id),
    ]
    db.add_all(users)
    db.commit()
    print("Created 5 demo users (2 of them linked to real Driver records) — see credentials below.")
    dispatcher_user = next(u for u in users if u.username == "dispatcher_demo")
    return driver1, driver2, dispatcher_user


def seed_shipment_example_1(db, driver1, dispatcher_user):
    """SHP-1001 — Chennai International Airport -> Bengaluru, In Transit,
    assigned to Driver Demo 1, dispatched by Dispatcher Demo."""
    vehicle = models.Vehicle(registration_number="TN-01-AB-1234", vehicle_type="Truck", capacity=8.0,
                              fuel_type="Diesel", status=models.VehicleStatus.ON_TRIP)
    db.add(vehicle)
    db.flush()

    trip = models.Trip(
        driver_id=driver1.id, vehicle_id=vehicle.id,
        scheduled_start=datetime.utcnow() - timedelta(hours=2),
        scheduled_end=datetime.utcnow() + timedelta(hours=3),
        actual_start=datetime.utcnow() - timedelta(hours=2),
        status=models.TripStatus.IN_PROGRESS, total_distance_km=346.0,
    )
    db.add(trip)
    db.flush()

    shipment = models.Shipment(
        tracking_number="SHP-1001", origin="Chennai International Airport", destination="Bengaluru",
        status=models.ShipmentStatus.IN_TRANSIT, eta=datetime.utcnow() + timedelta(hours=3),
        trip_id=trip.id, dispatcher_user_id=dispatcher_user.id,
    )
    db.add(shipment)
    db.flush()

    # Status history — shows the workflow's progression, not just a
    # single overwritten status.
    base = datetime.utcnow() - timedelta(hours=2, minutes=5)
    for offset_min, status in [(0, "assigned"), (3, "scheduled"), (5, "in_transit")]:
        db.add(models.StatusHistory(
            entity_type="shipment" if status != "scheduled" else "trip",
            entity_id=shipment.id if status != "scheduled" else trip.id,
            status=status, changed_by=driver1.id, changed_at=base + timedelta(minutes=offset_min),
        ))

    # A short location trail so the map/history has real movement to show,
    # not just a single point.
    for i, frac in enumerate([0.1, 0.25, 0.4]):
        db.add(models.DriverLocation(
            driver_id=driver1.id, trip_id=trip.id, shipment_id=shipment.id,
            latitude=LOCATIONS["Chennai International Airport"][0] + (LOCATIONS["Bengaluru"][0] - LOCATIONS["Chennai International Airport"][0]) * frac,
            longitude=LOCATIONS["Chennai International Airport"][1] + (LOCATIONS["Bengaluru"][1] - LOCATIONS["Chennai International Airport"][1]) * frac,
            recorded_at=datetime.utcnow() - timedelta(minutes=(3 - i) * 20),
        ))

    olat, olng = LOCATIONS["Chennai International Airport"]
    dlat, dlng = LOCATIONS["Bengaluru"]
    route = models.Route(
        trip_id=trip.id, origin="Chennai International Airport", destination="Bengaluru",
        origin_lat=olat, origin_lng=olng, destination_lat=dlat, destination_lng=dlng,
        route_type=models.RouteType.FASTEST, distance_km=346.0, duration_minutes=330.0,
        traffic_delay_minutes=20.0, is_estimated="true", source="local_estimate",
    )
    db.add(route)

    fuel = models.FuelRecord(
        vehicle_id=vehicle.id, driver_id=driver1.id, fuel_quantity_liters=45.0, fuel_cost=4500.0,
        odometer_reading=32100, fuel_date=datetime.utcnow() - timedelta(hours=2),
        fuel_station="Chennai Airport Fuel Station",
    )
    db.add(fuel)

    maintenance = models.Maintenance(
        vehicle_id=vehicle.id, category=models.MaintenanceCategory.GENERAL_INSPECTION,
        service_date=datetime.utcnow() - timedelta(days=15),
        next_service_date=datetime.utcnow() + timedelta(days=15),
        service_cost=600.0, service_provider="FleetFlow Service Center",
        status=models.MaintenanceStatus.COMPLETED, notes="Pre-trip inspection, no issues found.",
    )
    db.add(maintenance)

    db.commit()
    print("Seeded SHP-1001 — Chennai International Airport -> Bengaluru (In Transit, Driver Demo 1, TN-01-AB-1234).")


def seed_shipment_example_2(db, driver2, dispatcher_user):
    """SHP-1002 — Hyderabad -> Chennai, Assigned, Driver Demo 2."""
    vehicle = models.Vehicle(registration_number="TN-02-CD-5678", vehicle_type="Van", capacity=3.5,
                              fuel_type="Petrol", status=models.VehicleStatus.ON_TRIP)
    db.add(vehicle)
    db.flush()

    trip = models.Trip(
        driver_id=driver2.id, vehicle_id=vehicle.id,
        scheduled_start=datetime.utcnow() + timedelta(hours=1),
        scheduled_end=datetime.utcnow() + timedelta(hours=10),
        status=models.TripStatus.SCHEDULED, total_distance_km=627.0,
    )
    db.add(trip)
    db.flush()

    shipment = models.Shipment(
        tracking_number="SHP-1002", origin="Hyderabad", destination="Chennai",
        status=models.ShipmentStatus.ASSIGNED, eta=datetime.utcnow() + timedelta(hours=10),
        trip_id=trip.id, dispatcher_user_id=dispatcher_user.id,
    )
    db.add(shipment)
    db.flush()
    db.add(models.StatusHistory(entity_type="shipment", entity_id=shipment.id,
                                 status="assigned", changed_by=driver2.id, changed_at=datetime.utcnow()))

    olat, olng = LOCATIONS["Hyderabad"]
    dlat, dlng = LOCATIONS["Chennai"]
    route = models.Route(
        trip_id=trip.id, origin="Hyderabad", destination="Chennai",
        origin_lat=olat, origin_lng=olng, destination_lat=dlat, destination_lng=dlng,
        route_type=models.RouteType.TRAFFIC_AVOIDANCE, distance_km=627.0, duration_minutes=660.0,
        traffic_delay_minutes=35.0, is_estimated="true", source="local_estimate",
    )
    db.add(route)

    db.commit()
    print("Seeded SHP-1002 — Hyderabad -> Chennai (Assigned, Driver Demo 2, TN-02-CD-5678).")


def seed_supporting_fleet_data(db, driver1, driver2):
    """A few extra vehicles/shipments/history so charts and the dashboard
    aren't just showing two records — a delivered shipment, a delayed one,
    a maintenance-flagged vehicle, and a fuel history for the trend chart."""
    extra_vehicle = models.Vehicle(registration_number="TN-03-EF-9012", vehicle_type="Truck", capacity=10.0,
                                    fuel_type="Diesel", status=models.VehicleStatus.MAINTENANCE)
    idle_vehicle = models.Vehicle(registration_number="TN-04-GH-3456", vehicle_type="Van", capacity=4.0,
                                   fuel_type="Petrol", status=models.VehicleStatus.AVAILABLE)
    db.add_all([extra_vehicle, idle_vehicle])
    db.flush()

    completed_trip = models.Trip(
        driver_id=driver1.id, vehicle_id=extra_vehicle.id,
        scheduled_start=datetime.utcnow() - timedelta(days=1, hours=5),
        scheduled_end=datetime.utcnow() - timedelta(days=1),
        actual_start=datetime.utcnow() - timedelta(days=1, hours=5),
        actual_end=datetime.utcnow() - timedelta(days=1),
        status=models.TripStatus.COMPLETED, total_distance_km=95.0,
    )
    db.add(completed_trip)
    db.flush()

    shipments = [
        models.Shipment(tracking_number="SHP-1003", origin="Warangal", destination="Hyderabad",
                         status=models.ShipmentStatus.DELIVERED,
                         eta=datetime.utcnow() - timedelta(days=1) + timedelta(hours=2),
                         trip_id=completed_trip.id,
                         created_at=datetime.utcnow() - timedelta(days=1, hours=5)),
        models.Shipment(tracking_number="SHP-1004", origin="Vijayawada", destination="Hyderabad",
                         status=models.ShipmentStatus.DELAYED, eta=datetime.utcnow() + timedelta(hours=6)),
        models.Shipment(tracking_number="SHP-1005", origin="Hyderabad", destination="Warangal",
                         status=models.ShipmentStatus.CREATED),
    ]
    db.add_all(shipments)

    maintenance = models.Maintenance(
        vehicle_id=extra_vehicle.id, category=models.MaintenanceCategory.BRAKE_SERVICE,
        service_date=datetime.utcnow(), next_service_date=datetime.utcnow() + timedelta(days=90),
        service_cost=1450.0, service_provider="FleetFlow Service Center",
        status=models.MaintenanceStatus.IN_PROGRESS, notes="Brake pads worn, replacement in progress.",
    )
    db.add(maintenance)

    fuel_records = [
        models.FuelRecord(vehicle_id=[extra_vehicle, idle_vehicle][i % 2].id,
                           driver_id=[driver1, driver2][i % 2].id,
                           fuel_quantity_liters=30 + i * 4, fuel_cost=(30 + i * 4) * 100,
                           odometer_reading=20000 + i * 500, fuel_date=datetime.utcnow() - timedelta(days=i),
                           fuel_station=f"Fuel Station #{i + 1}")
        for i in range(6)
    ]
    db.add_all(fuel_records)

    db.commit()
    print("Seeded supporting fleet data (2 more vehicles, 3 more shipments across statuses, fuel history).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Wipe all operational data and users before reseeding")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if args.reset:
            reset(db)

        if db.query(models.User).count() > 0 and not args.reset:
            print("Users already exist and --reset was not passed — skipping to avoid duplicates.")
            print("Run with --reset to wipe and reseed fresh demo data.")
            sys.exit(0)

        driver1, driver2, dispatcher_user = seed_drivers_and_users(db)
        seed_shipment_example_1(db, driver1, dispatcher_user)
        seed_shipment_example_2(db, driver2, dispatcher_user)
        seed_supporting_fleet_data(db, driver1, driver2)

        print("\n=== DEMO LOGIN CREDENTIALS ===")
        print("  admin           username=admin_demo       password=Demo@1234")
        print("  fleet_manager   username=manager_demo     password=Demo@1234")
        print("  dispatcher      username=dispatcher_demo  password=Demo@1234")
        print("  driver (#1)     username=driver1_demo     password=Demo@1234  (sees only SHP-1001 / TN-01-AB-1234)")
        print("  driver (#2)     username=driver2_demo     password=Demo@1234  (sees only SHP-1002 / TN-02-CD-5678)")
        print("===============================")
        print("\nSHP-1001: Chennai International Airport -> Bengaluru, In Transit")
        print("SHP-1002: Hyderabad -> Chennai, Assigned")
        print("Re-run with --reset any time to wipe and reload a clean demo state.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
