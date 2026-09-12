"""Maneuver planning and validation endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.world import get_world

router = APIRouter(prefix="/maneuver", tags=["maneuver"])


class OptimizeRequest(BaseModel):
    conjunction_id: str


class ValidateRequest(BaseModel):
    conjunction_id: str
    candidate_id: str


def _event(conjunction_id: str):
    world = get_world()
    event = world.events.get(conjunction_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"No conjunction {conjunction_id!r}.")
    return world, event


@router.post("/optimize")
def optimize(request: OptimizeRequest):
    """
    Search burn magnitude, direction, and timing for the cheapest safe maneuver.

    Returns a short decision table rather than every candidate evaluated: per
    axis, the cheapest burn that meets the safety target (confirmed and
    re-screened against the catalog) and the largest one that fell short.
    """
    world, event = _event(request.conjunction_id)
    if not event.approach.primary.maneuverable:
        return {
            "candidates": [],
            "recommended_candidate_id": None,
            "reason": "Neither object in this conjunction is maneuverable.",
        }
    return world.maneuvers(event)


@router.post("/validate")
def validate(request: ValidateRequest):
    """Re-propagate one candidate and re-screen the full catalog before accepting it."""
    world, event = _event(request.conjunction_id)
    if not event.approach.primary.maneuverable:
        raise HTTPException(status_code=409, detail="Neither object is maneuverable.")
    try:
        return world.validate(event, request.candidate_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No candidate {request.candidate_id!r}.")
