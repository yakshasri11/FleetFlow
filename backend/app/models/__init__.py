from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="dispatcher")
    created_at = Column(DateTime, default=datetime.utcnow)


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    license_number = Column(String, unique=True, nullable=False)
    phone = Column(String)
    assigned_vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    status = Column(String, default="available")

    vehicle = relationship("Vehicle", back_populates="driver")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    registration_number = Column(String, unique=True, index=True, nullable=False)
    vehicle_type = Column(String)
    capacity = Column(Float)
    fuel_type = Column(String)
    status = Column(String, default="available")

    driver = relationship("Driver", back_populates="vehicle", uselist=False)
    shipments = relationship("Shipment", back_populates="vehicle")


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    tracking_number = Column(String, unique=True, index=True, nullable=False)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    status = Column(String, default="created")
    eta = Column(DateTime, nullable=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    vehicle = relationship("Vehicle", back_populates="shipments")
