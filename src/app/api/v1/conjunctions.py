"""Conjunction endpoints."""

from fastapi import APIRouter, HTTPException

from app.services.world import get_world

router = APIRouter(prefix="/conjunctions", tags=["conjunctions"])


@router.get("")
def list_conjunctions():
    """
    Upcoming close approaches, highest priority first.

    The simulated demonstration event, when enabled, is listed first and carries
    `simulated: true`.
    """
    world = get_world()
    return [world.event_payload(event) for event in world.active_events()]


@router.get("/{conjunction_id}")
def get_conjunction(conjunction_id: str):
    world = get_world()
    event = world.events.get(conjunction_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"No conjunction {conjunction_id!r}.")
    return world.event_payload(event)
