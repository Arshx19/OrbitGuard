"""Maneuver optimization & validation API router.

Candidates are searched, not scripted. The planner (app.services.maneuvers) tries
burns across direction, magnitude, and timing, propagates each with the
Clohessy-Wiltshire equations, recomputes collision probability, and re-screens
the cheapest safe option per axis against the whole catalog over 24 hours.
`/maneuver/validate` runs that full check on one chosen candidate.
"""

from fastapi import APIRouter, HTTPException

from app.api.v1.serializers import candidate_schema
from app.models.conjunction import ManeuverOptimizeResponse, ManeuverRequest, ValidationChecks
from app.services.maneuvers import PC_SAFE_TARGET
from app.services.world import get_world

router = APIRouter()


def _event(conjunction_id: str):
    world = get_world()
    event = world.events.get(conjunction_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Conjunction {conjunction_id} not found")
    return world, event


def _not_maneuverable(req: ManeuverRequest) -> ManeuverOptimizeResponse:
    return ManeuverOptimizeResponse(
        conjunction_id=req.conjunction_id,
        optimal_candidate=None,
        all_candidates=[],
        reason="Neither object in this conjunction is maneuverable.",
    )


@router.post("/maneuver/optimize", response_model=ManeuverOptimizeResponse)
def optimize_maneuver(req: ManeuverRequest):
    """Search for the minimum-delta-v burn that brings collision probability below target."""
    world, event = _event(req.conjunction_id)
    if not event.approach.primary.maneuverable:
        return _not_maneuverable(req)

    plan = world.maneuvers(event, dv_bounds_ms=(req.dv_min_ms, req.dv_max_ms))
    target = plan["safety_target"]
    recommended = plan["recommended_candidate_id"]
    candidates = [candidate_schema(c, target, recommended) for c in plan["candidates"]]

    return ManeuverOptimizeResponse(
        conjunction_id=req.conjunction_id,
        optimal_candidate=next((c for c in candidates if c.recommended), None),
        all_candidates=candidates,
        candidates_evaluated=plan["candidates_evaluated"],
        safety_target=target,
        pc_before=plan["pc_before"],
        reason=None if candidates else "No candidate burns fit the requested delta-v range and time available.",
    )


@router.post("/maneuver/validate", response_model=ManeuverOptimizeResponse)
def validate_maneuver(req: ManeuverRequest):
    """
    Re-propagate one candidate and re-screen the full catalog before accepting it.

    Validates `candidate_id` if given, otherwise the recommended candidate.
    """
    world, event = _event(req.conjunction_id)
    if not event.approach.primary.maneuverable:
        return _not_maneuverable(req)

    candidate_id = req.candidate_id
    if not candidate_id:
        plan = world.maneuvers(event, dv_bounds_ms=(req.dv_min_ms, req.dv_max_ms))
        candidate_id = plan["recommended_candidate_id"]
        if not candidate_id:
            raise HTTPException(status_code=409, detail="No safe candidate to validate.")

    try:
        result = world.validate(event, candidate_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

    validated = candidate_schema(result, PC_SAFE_TARGET)
    return ManeuverOptimizeResponse(
        conjunction_id=req.conjunction_id,
        optimal_candidate=validated if validated.is_safe else None,
        all_candidates=[validated],
        safety_target=PC_SAFE_TARGET,
        pc_before=result["pc_before"],
        validated_candidate=validated,
        checks=ValidationChecks(**result["checks"]),
    )
