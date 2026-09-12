"""Risk analysis endpoint."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.world import get_world

router = APIRouter(prefix="/risk", tags=["risk"])


class RiskRequest(BaseModel):
    conjunction_id: str


@router.post("/analyze")
def analyze_risk(request: RiskRequest):
    """
    Collision probability, 0-100 priority score, severity, and the counterfactual
    explanation of each risk factor for one conjunction.
    """
    world = get_world()
    event = world.events.get(request.conjunction_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"No conjunction {request.conjunction_id!r}.")

    payload = world.event_payload(event)
    payload["pc_detail"] = event.assessment.pc_result.to_dict()
    return payload
