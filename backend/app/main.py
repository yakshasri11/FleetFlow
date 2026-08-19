from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import (
    auth, drivers, vehicles, shipments, trips,
    maintenance, driver_assignments, fuel, analytics,
    routes, notifications, reports, tracking,
)

# Creates any tables that don't exist yet (safe no-op for ones that already do).
# For production schema changes, use Alembic migrations instead.
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"[Startup] Could not connect to database yet: {e}")
    print("[Startup] Server will still start -- connect a real database and restart to enable data endpoints.")

from app.config import settings

app = FastAPI(title="FleetFlow API", description="Fleet Management & Logistics Tracking Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(",") if settings.cors_origins != "*" else ["*"],
    # The frontend authenticates with a Bearer token in the Authorization
    # header, not cookies — so CORS "credentials" mode isn't needed, and
    # leaving it off is what allows allow_origins=["*"] to work at all
    # (browsers reject wildcard origins combined with credentials=True).
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(drivers.router)
app.include_router(vehicles.router)
app.include_router(shipments.router)
app.include_router(trips.router)
app.include_router(maintenance.router)
app.include_router(driver_assignments.router)
app.include_router(fuel.router)
app.include_router(analytics.router)
app.include_router(routes.router)
app.include_router(notifications.router)
app.include_router(reports.router)
app.include_router(tracking.router)


@app.get("/")
def home():
    return {"message": "FleetFlow Backend Running Successfully"}
