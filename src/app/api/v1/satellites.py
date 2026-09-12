"""Tracked-object endpoints."""

import math

from fastapi import APIRouter

from app.services.tracks import TLETrack
from app.services.world import get_world

router = APIRouter(prefix="/satellites", tags=["satellites"])


@router.get("")
def list_satellites():
    """Every object in the screened catalog."""
    world = get_world()
    now_jd, now_fr = world.now_jd()
    objects = []
    for track in world.tracks:
        entry = {
            "id": track.object_id,
            "name": track.name,
            "type": track.object_type,
            "maneuverable": track.maneuverable,
            "tle_age_days": round(track.tle_age_days(now_jd, now_fr), 3),
        }
        if isinstance(track, TLETrack):
            entry["norad_id"] = track.norad_id
            entry["inclination_deg"] = round(math.degrees(track.satrec.inclo), 4)
        objects.append(entry)
    return objects


@router.get("/stats")
def satellite_stats():
    """Headline counts for the dashboard."""
    return get_world().stats()
