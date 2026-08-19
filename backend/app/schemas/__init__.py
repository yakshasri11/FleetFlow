from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models import (
    UserRole, VehicleStatus, ShipmentStatus, TripStatus,
    MaintenanceCategory, MaintenanceStatus, AssignmentStatus, AttendanceStatus,
    RouteType, NotificationType,
)


# ==================== Auth ====================

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: UserRole = UserRole.DISPATCHER
    driver_id: Optional[int] = None  # only meaningful when role == DRIVER

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: UserRole
    driver_id: Optional[int] = None
    is_active: str
    created_at: datetime

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    role: Optional[UserRole] = None
    is_active: Optional[str] = None
    driver_id: Optional[int] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class AdminPasswordReset(BaseModel):
    new_password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ==================== Driver ====================

class DriverBase(BaseModel):
    name: str
    license_number: str
    phone: Optional[str] = None

class DriverCreate(DriverBase):
    pass

class DriverUpdate(BaseModel):
    name: Optional[str] = None
    license_number: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None

class DriverOut(DriverBase):
    id: int
    status: str

    class Config:
        from_attributes = True


# ==================== Vehicle ====================

class VehicleBase(BaseModel):
    registration_number: str
    vehicle_type: str
    capacity: Optional[float] = None
    fuel_type: Optional[str] = None

class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseModel):
    registration_number: Optional[str] = None
    vehicle_type: Optional[str] = None
    capacity: Optional[float] = None
    fuel_type: Optional[str] = None
    status: Optional[VehicleStatus] = None

class VehicleOut(VehicleBase):
    id: int
    status: VehicleStatus

    class Config:
        from_attributes = True


# ==================== Shipment ====================

class ShipmentBase(BaseModel):
    origin: str
    destination: str

class ShipmentCreate(ShipmentBase):
    pass

class ShipmentUpdate(BaseModel):
    status: Optional[ShipmentStatus] = None
    eta: Optional[datetime] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    dispatcher_user_id: Optional[int] = None

class ShipmentOut(ShipmentBase):
    id: int
    tracking_number: str
    status: ShipmentStatus
    eta: Optional[datetime] = None
    trip_id: Optional[int] = None
    dispatcher_user_id: Optional[int] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[int] = None
    completion_note: Optional[str] = None
    completion_lat: Optional[float] = None
    completion_lng: Optional[float] = None
    driver_name: Optional[str] = None
    vehicle_registration: Optional[str] = None

    class Config:
        from_attributes = True

class ShipmentAssignRequest(BaseModel):
    trip_id: int
    dispatcher_user_id: Optional[int] = None

class CompletionRequest(BaseModel):
    completion_note: str
    completion_lat: Optional[float] = None
    completion_lng: Optional[float] = None

class StatusHistoryOut(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    status: str
    changed_by: Optional[int] = None
    changed_at: datetime

    class Config:
        from_attributes = True


# ==================== Trip ====================

class TripCreate(BaseModel):
    driver_id: int
    vehicle_id: int
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    shipment_ids: Optional[list[int]] = None

class TripUpdate(BaseModel):
    status: Optional[TripStatus] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    total_distance_km: Optional[float] = None

class TripOut(BaseModel):
    id: int
    driver_id: int
    vehicle_id: int
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    status: TripStatus
    total_distance_km: Optional[float] = None
    created_at: datetime
    driver_name: Optional[str] = None
    vehicle_registration: Optional[str] = None

    class Config:
        from_attributes = True


# ==================== Maintenance ====================

class MaintenanceBase(BaseModel):
    vehicle_id: int
    category: MaintenanceCategory
    service_date: datetime
    next_service_date: Optional[datetime] = None
    service_cost: Optional[float] = None
    service_provider: Optional[str] = None
    notes: Optional[str] = None

class MaintenanceCreate(MaintenanceBase):
    pass

class MaintenanceUpdate(BaseModel):
    category: Optional[MaintenanceCategory] = None
    service_date: Optional[datetime] = None
    next_service_date: Optional[datetime] = None
    service_cost: Optional[float] = None
    service_provider: Optional[str] = None
    status: Optional[MaintenanceStatus] = None
    notes: Optional[str] = None

class MaintenanceOut(MaintenanceBase):
    id: int
    status: MaintenanceStatus
    created_at: datetime
    is_archived: str

    class Config:
        from_attributes = True


# ==================== Driver Assignment / Attendance ====================

class DriverAssignmentCreate(BaseModel):
    driver_id: int
    vehicle_id: int
    trip_id: Optional[int] = None
    remarks: Optional[str] = None

class DriverAssignmentUpdate(BaseModel):
    status: Optional[AssignmentStatus] = None
    remarks: Optional[str] = None

class DriverAssignmentOut(BaseModel):
    id: int
    driver_id: int
    vehicle_id: int
    trip_id: Optional[int] = None
    assignment_date: datetime
    status: AssignmentStatus
    remarks: Optional[str] = None

    class Config:
        from_attributes = True


class DriverAttendanceCreate(BaseModel):
    driver_id: int
    date: datetime
    status: AttendanceStatus = AttendanceStatus.PRESENT
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None

class DriverAttendanceOut(DriverAttendanceCreate):
    id: int

    class Config:
        from_attributes = True


class DriverPerformanceOut(BaseModel):
    driver_id: int
    total_trips: int
    completed_trips: int
    active_trips: int
    cancelled_trips: int


# ==================== Fuel ====================

class FuelRecordBase(BaseModel):
    vehicle_id: int
    driver_id: int
    fuel_quantity_liters: float
    fuel_cost: float
    odometer_reading: Optional[float] = None
    fuel_station: Optional[str] = None
    remarks: Optional[str] = None

class FuelRecordCreate(FuelRecordBase):
    pass

class FuelRecordUpdate(BaseModel):
    fuel_quantity_liters: Optional[float] = None
    fuel_cost: Optional[float] = None
    odometer_reading: Optional[float] = None
    fuel_station: Optional[str] = None
    remarks: Optional[str] = None

class FuelRecordOut(FuelRecordBase):
    id: int
    fuel_date: datetime

    class Config:
        from_attributes = True


# ==================== Analytics ====================

class FuelAnalyticsOut(BaseModel):
    total_fuel_consumed: float
    total_fuel_cost: float
    average_fuel_consumption: float
    vehicle_highest_usage: Optional[int] = None
    vehicle_lowest_usage: Optional[int] = None

class FleetDashboardOut(BaseModel):
    total_vehicles: int
    active_vehicles: int
    vehicles_under_maintenance: int
    total_drivers: int
    available_drivers: int
    assigned_drivers: int
    total_trips: int
    completed_trips: int
    active_shipments: int
    total_maintenance_records: int
    total_fuel_consumed: float

class OperationalAnalyticsOut(BaseModel):
    total_deliveries: int
    successful_deliveries: int
    delayed_deliveries: int
    cancelled_deliveries: int
    average_trip_distance: Optional[float] = None
    average_delivery_time_minutes: Optional[float] = None


# ==================== Route Optimization ====================

class RouteOptimizeRequest(BaseModel):
    origin: str
    destination: str
    route_type: RouteType = RouteType.FASTEST
    trip_id: Optional[int] = None

class RouteOut(BaseModel):
    id: int
    trip_id: Optional[int] = None
    origin: str
    destination: str
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None
    destination_lat: Optional[float] = None
    destination_lng: Optional[float] = None
    route_type: RouteType
    distance_km: Optional[float] = None
    duration_minutes: Optional[float] = None
    traffic_delay_minutes: Optional[float] = None
    is_estimated: str
    source: str
    created_at: datetime
    recalculated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== Notifications ====================

class NotificationOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    role: Optional[UserRole] = None
    type: NotificationType
    title: str
    message: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
    is_read: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Live Tracking ====================

class LocationUpdate(BaseModel):
    trip_id: int
    latitude: float
    longitude: float

class LocationOut(BaseModel):
    id: int
    driver_id: int
    trip_id: int
    shipment_id: Optional[int] = None
    latitude: float
    longitude: float
    recorded_at: datetime

    class Config:
        from_attributes = True

class TripTrackingOut(BaseModel):
    trip_id: int
    shipment_id: Optional[int] = None
    tracking_number: Optional[str] = None
    driver_name: Optional[str] = None
    vehicle_registration: Optional[str] = None
    status: str
    origin: Optional[str] = None
    destination: Optional[str] = None
    latest_latitude: Optional[float] = None
    latest_longitude: Optional[float] = None
    last_updated: Optional[datetime] = None
    seconds_since_update: Optional[int] = None
    has_live_location: bool = False
