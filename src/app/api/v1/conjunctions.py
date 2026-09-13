"""Conjunctions API router, serving close approaches found by screening the TLE catalog.

Events come from the screening pipeline in app.services.screening: every tracked
object is propagated with SGP4, candidate pairs are filtered by orbital radius,
and each close approach is refined to its true time of closest approach before
being assessed by the risk engine. One event may be simulated -- a constructed
conjunction against the real ISS, so the demo always has a critical, maneuverable
event -- and it is marked `simulated: true`.
"""

from typing import List

from fastapi import APIRouter, HTTPException

from app.api.v1.serializers import conjunction_summary
from app.models.conjunction import ConjunctionSummary
from app.services.world import get_world

router = APIRouter()


@router.get("/conjunctions", response_model=List[ConjunctionSummary])
def get_conjunctions():
    """Upcoming close approaches, the simulated event first, then by risk score."""
    world = get_world()
    return [conjunction_summary(world, event) for event in world.active_events()]


@router.get("/conjunctions/{conjunction_id}", response_model=ConjunctionSummary)
def get_conjunction_detail(conjunction_id: str):
    """Get detailed conjunction information for a specific event."""
    world = get_world()
    event = world.events.get(conjunction_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Conjunction {conjunction_id} not found")
    return conjunction_summary(world, event)
