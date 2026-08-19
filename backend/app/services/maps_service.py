"""Route & geocoding service.

Uses the Google Maps Geocoding + Directions APIs when GOOGLE_MAPS_API_KEY is
set in the environment. If the key is missing, or the live call fails for any
reason (network, quota, invalid key), this falls back to a free local
estimate — haversine great-circle distance plus a per-route-type assumed
average speed — so the route-optimization feature always works without a
paid key. Every result is tagged so the caller (and the frontend) can tell
which path produced it; nothing pretends a live/estimated result is the other.
"""
import math
from typing import Optional

import httpx

from app.config import settings
from app.models import RouteType

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"

# Assumed average speeds (km/h) used only by the local fallback estimator,
# per route type — a rough stand-in for what live traffic/routing data would
# otherwise provide.
_FALLBACK_SPEEDS_KMH = {
    RouteType.SHORTEST: 45,
    RouteType.FASTEST: 65,
    RouteType.TRAFFIC_AVOIDANCE: 50,
    RouteType.FUEL_EFFICIENT: 55,
}

# Google Directions API params per route type.
_GOOGLE_PARAMS = {
    RouteType.SHORTEST: {},
    RouteType.FASTEST: {"departure_time": "now"},
    RouteType.TRAFFIC_AVOIDANCE: {"departure_time": "now", "avoid": "tolls"},
    RouteType.FUEL_EFFICIENT: {"avoid": "highways"},
}


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _local_geocode_estimate(address: str) -> tuple[float, float]:
    """Deterministic pseudo-coordinates derived from the address text.

    Used only when there is no API key and the address can't be geocoded for
    real. It keeps repeated calls for the same address consistent (so
    distance/route recalculation is stable) but the coordinates are NOT real
    locations — this is clearly a placeholder, not a geocoding result.
    """
    h = sum(ord(c) for c in address)
    lat = -60 + (h % 12000) / 100.0
    lng = -180 + (h * 7 % 36000) / 100.0
    return lat, lng


async def geocode(address: str) -> tuple[Optional[float], Optional[float], bool]:
    """Returns (lat, lng, is_estimated)."""
    if settings.google_maps_api_key:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    GEOCODE_URL, params={"address": address, "key": settings.google_maps_api_key}
                )
                data = resp.json()
                if data.get("status") == "OK" and data.get("results"):
                    loc = data["results"][0]["geometry"]["location"]
                    return loc["lat"], loc["lng"], False
        except Exception:
            pass  # fall through to local estimate
    lat, lng = _local_geocode_estimate(address)
    return lat, lng, True


async def get_route(origin: str, destination: str, route_type: RouteType) -> dict:
    """Returns distance_km, duration_minutes, traffic_delay_minutes, is_estimated, source."""
    if settings.google_maps_api_key:
        try:
            params = {
                "origin": origin,
                "destination": destination,
                "key": settings.google_maps_api_key,
                **_GOOGLE_PARAMS.get(route_type, {}),
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(DIRECTIONS_URL, params=params)
                data = resp.json()
                if data.get("status") == "OK" and data.get("routes"):
                    leg = data["routes"][0]["legs"][0]
                    distance_km = leg["distance"]["value"] / 1000.0
                    duration_min = leg["duration"]["value"] / 60.0
                    duration_traffic = leg.get("duration_in_traffic", {}).get("value")
                    traffic_delay = (duration_traffic / 60.0 - duration_min) if duration_traffic else 0.0
                    return {
                        "distance_km": round(distance_km, 2),
                        "duration_minutes": round(duration_min, 1),
                        "traffic_delay_minutes": round(max(traffic_delay, 0.0), 1),
                        "is_estimated": False,
                        "source": "google_maps",
                    }
        except Exception:
            pass  # fall through to local estimate

    olat, olng, _ = await geocode(origin)
    dlat, dlng, _ = await geocode(destination)
    distance_km = _haversine_km(olat, olng, dlat, dlng) * 1.3  # rough road-vs-straight-line factor
    speed = _FALLBACK_SPEEDS_KMH[route_type]
    duration_min = (distance_km / speed) * 60
    # Traffic-avoidance/fastest routes get a small simulated traffic delay so
    # the figure isn't always zero in demo mode.
    traffic_delay = round(duration_min * 0.08, 1) if route_type in (
        RouteType.FASTEST, RouteType.TRAFFIC_AVOIDANCE
    ) else 0.0

    return {
        "distance_km": round(distance_km, 2),
        "duration_minutes": round(duration_min, 1),
        "traffic_delay_minutes": traffic_delay,
        "is_estimated": True,
        "source": "local_estimate",
    }
