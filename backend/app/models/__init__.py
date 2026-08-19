import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import relationship

from app.database import Base


# ==================== Auth ====================

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    FLEET_MANAGER = "fleet_manager"
    DRIVER = "driver"
    DISPATCHER = "dispatcher"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(SqlEnum(UserRole), default=UserRole.DISPATCHER, nullable=False)
    # Links a DRIVER-role account to their Driver record, so trips/shipments
    # can be filtered to "only what this driver is assigned" at the query
    # level (not just hidden in the UI).
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    is_active = Column(String, default="true", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    driver = relationship("Driver")


# ==================== Fleet ====================

class VehicleStatus(str, enum.Enum):
    AVAILABLE = "available"
    ON_TRIP = "on_trip"
    MAINTENANCE = "maintenance"


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    registration_number = Column(String, unique=True, index=True, nullable=False)
    vehicle_type = Column(String, nullable=False)
    capacity = Column(Float, nullable=True)
    fuel_type = Column(String, nullable=True)
    status = Column(SqlEnum(VehicleStatus), default=VehicleStatus.AVAILABLE, nullable=False)


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    license_number = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    # Simple string status ("available" / "on_trip" / "off_duty") to keep it
    # human-readable in the API without forcing every caller through an enum.
    status = Column(String, default="available", nullable=False)


# ==================== Shipments & Trips ====================

class ShipmentStatus(str, enum.Enum):
    CREATED = "created"
    ASSIGNED = "assigned"
    IN_TRANSIT = "in_transit"
    DELAYED = "delayed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    tracking_number = Column(String, unique=True, index=True, nullable=False)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    status = Column(SqlEnum(ShipmentStatus), default=ShipmentStatus.CREATED, nullable=False)
    eta = Column(DateTime, nullable=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True)
    # The Dispatcher responsible for this shipment, if any — lets completion/
    # assignment notifications target one specific dispatcher instead of a
    # role-wide broadcast.
    dispatcher_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    completion_note = Column(String, nullable=True)
    completion_lat = Column(Float, nullable=True)
    completion_lng = Column(Float, nullable=True)
    deleted = Column(String, default="false", nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    trip = relationship("Trip", back_populates="shipments")


class TripStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    scheduled_start = Column(DateTime, nullable=True)
    scheduled_end = Column(DateTime, nullable=True)
    actual_start = Column(DateTime, nullable=True)
    actual_arrival = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    status = Column(SqlEnum(TripStatus), default=TripStatus.SCHEDULED, nullable=False)
    total_distance_km = Column(Float, nullable=True)
    deleted = Column(String, default="false", nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    driver = relationship("Driver")
    vehicle = relationship("Vehicle")
    shipments = relationship("Shipment", back_populates="trip")


class StatusHistory(Base):
    __tablename__ = "status_history"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, nullable=False)  # "shipment" or "trip"
    entity_id = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow)


class DriverLocation(Base):
    """Latest + historical driver location, submitted by the driver's own
    device via polling (POST /tracking/location). Not real GPS hardware —
    the browser's Geolocation API on whatever device the driver is using."""
    __tablename__ = "driver_locations"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)


# ==================== Maintenance ====================

class MaintenanceCategory(str, enum.Enum):
    OIL_CHANGE = "Oil Change"
    TYRE_REPLACEMENT = "Tyre Replacement"
    BRAKE_SERVICE = "Brake Service"
    ENGINE_SERVICE = "Engine Service"
    GENERAL_INSPECTION = "General Inspection"


class MaintenanceStatus(str, enum.Enum):
    SCHEDULED = "Scheduled"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"


class Maintenance(Base):
    __tablename__ = "maintenance_records"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    category = Column(SqlEnum(MaintenanceCategory), nullable=False)
    service_date = Column(DateTime, nullable=False)
    next_service_date = Column(DateTime, nullable=True)
    service_cost = Column(Float, nullable=True)
    service_provider = Column(String, nullable=True)
    status = Column(SqlEnum(MaintenanceStatus), default=MaintenanceStatus.SCHEDULED, nullable=False)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Soft delete — maintenance history is never permanently removed
    is_archived = Column(String, default="false", nullable=False)
    # Prevents Celery from sending the same reminder twice for the same due date
    reminder_sent = Column(String, default="false", nullable=False)

    vehicle = relationship("Vehicle")


# ==================== Driver Assignment & Attendance ====================

class AssignmentStatus(str, enum.Enum):
    ASSIGNED = "Assigned"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class DriverAssignment(Base):
    __tablename__ = "driver_assignments"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True)
    assignment_date = Column(DateTime, default=datetime.utcnow)
    status = Column(SqlEnum(AssignmentStatus), default=AssignmentStatus.ASSIGNED, nullable=False)
    remarks = Column(String, nullable=True)

    driver = relationship("Driver")
    vehicle = relationship("Vehicle")
    trip = relationship("Trip")


class AttendanceStatus(str, enum.Enum):
    PRESENT = "Present"
    ABSENT = "Absent"
    LEAVE = "Leave"


class DriverAttendance(Base):
    __tablename__ = "driver_attendance"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    status = Column(SqlEnum(AttendanceStatus), default=AttendanceStatus.PRESENT, nullable=False)
    check_in_time = Column(DateTime, nullable=True)
    check_out_time = Column(DateTime, nullable=True)

    driver = relationship("Driver")


# ==================== Fuel Monitoring ====================

class FuelRecord(Base):
    __tablename__ = "fuel_records"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    fuel_quantity_liters = Column(Float, nullable=False)
    fuel_cost = Column(Float, nullable=False)
    odometer_reading = Column(Float, nullable=True)
    fuel_date = Column(DateTime, default=datetime.utcnow)
    fuel_station = Column(String, nullable=True)
    remarks = Column(String, nullable=True)

    vehicle = relationship("Vehicle")
    driver = relationship("Driver")


# ==================== Route Optimization ====================

class RouteType(str, enum.Enum):
    SHORTEST = "shortest"
    FASTEST = "fastest"
    TRAFFIC_AVOIDANCE = "traffic_avoidance"
    FUEL_EFFICIENT = "fuel_efficient"


class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    origin_lat = Column(Float, nullable=True)
    origin_lng = Column(Float, nullable=True)
    destination_lat = Column(Float, nullable=True)
    destination_lng = Column(Float, nullable=True)
    route_type = Column(SqlEnum(RouteType), default=RouteType.FASTEST, nullable=False)
    distance_km = Column(Float, nullable=True)
    duration_minutes = Column(Float, nullable=True)
    traffic_delay_minutes = Column(Float, nullable=True, default=0.0)
    # "true" when Google Maps could not be reached (no/invalid API key, or the call
    # failed) and the figures below were estimated locally instead of from a live API.
    is_estimated = Column(String, default="false", nullable=False)
    source = Column(String, default="google_maps", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    recalculated_at = Column(DateTime, nullable=True)

    trip = relationship("Trip")


# ==================== Notifications ====================

class NotificationType(str, enum.Enum):
    MAINTENANCE_ALERT = "maintenance_alert"
    DELIVERY_UPDATE = "delivery_update"
    DRIVER_ASSIGNMENT = "driver_assignment"
    SHIPMENT_STATUS = "shipment_status"
    ROUTE_CHANGE = "route_change"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    # A notification targets either one specific user (user_id) or every user
    # of a given role (role) — e.g. every Fleet Manager. At least one is set.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    role = Column(SqlEnum(UserRole), nullable=True)
    type = Column(SqlEnum(NotificationType), nullable=False)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    related_entity_type = Column(String, nullable=True)
    related_entity_id = Column(Integer, nullable=True)
    is_read = Column(String, default="false", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
