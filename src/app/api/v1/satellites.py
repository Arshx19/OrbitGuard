"""Satellites API router serving the tracked catalog.

The catalog is the one screening runs over, so the counts here agree with the
conjunctions endpoint. Element sets come from CelesTrak, cached in data/raw/.
"""

from fastapi import APIRouter, Query

from app.api.v1.serializers import satellite_schema
from app.models.satellite import SatelliteListResponse
from app.services.world import get_world

router = APIRouter()


@router.get("/satellites", response_model=SatelliteListResponse)
def get_satellites(limit: int = Query(50, ge=0, le=5000, description="Maximum objects to list.")):
    """List tracked satellites and debris, with dashboard counts from screening."""
    world = get_world()
    now_jd, now_fr = world.now_jd()
    stats = world.stats()
    return SatelliteListResponse(
        total_tracked=stats["objects_tracked"],
        satellites=[satellite_schema(t, now_jd, now_fr) for t in world.tracks[:limit]],
        active_conjunctions=stats["active_conjunctions"],
        high_risk_events=stats["high_risk_events"],
        satellites_monitored=stats["satellites_monitored"],
    )
