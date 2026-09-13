"""Risk analysis & explainability API router.

Risk is computed, not looked up. For a screened event the collision probability
comes from Foster's 2D method using the event's state vectors and a position
covariance learned from measured TLE errors; the 0-100 score and severity follow
from that probability, and each factor's contribution is a counterfactual --
the probability recomputed with that factor reset to a benign baseline.

The response keeps the prototype's field names, including `shap_factors`, for
compatibility. `explanation_method` states what the values actually are.
"""

import math

import numpy as np
from fastapi import APIRouter, HTTPException

from app.api.v1.serializers import conjunction_summary, shap_factors
from app.core.risk_engine import ConjunctionInput
from app.core.uncertainty import REGIME_PASSIVE
from app.models.conjunction import RiskAnalyzeRequest, RiskAnalyzeResponse
from app.services.tracks import MU_EARTH_KM3_S2
from app.services.world import get_world

router = APIRouter()

_AD_HOC_RADIUS_KM = 6778.0  # 400 km circular orbit
_AD_HOC_DEFAULT_AGE_DAYS = 0.5
_AD_HOC_DEFAULT_TCA_HOURS = 24.0


_AD_HOC_ORIENTATIONS_DEG = range(0, 180, 15)


def _ad_hoc_conjunctions(req: RiskAnalyzeRequest):
    """
    Build candidate crossing encounters from summary parameters.

    Collision probability needs geometry, not just a distance and a speed. The
    primary sits on a 400 km circular orbit and the secondary crosses it at
    whatever angle gives the requested relative speed. What summary parameters
    cannot supply is the direction of the miss within the encounter plane, and
    it matters enormously: TLE uncertainty is a long thin ellipsoid, so a miss
    along the well-determined radial axis is far safer than the same miss along
    the poorly determined along-track axis. Rather than silently choosing a
    favourable direction, one encounter is built per orientation and the caller
    reports the worst.
    """
    speed = math.sqrt(MU_EARTH_KM3_S2 / _AD_HOC_RADIUS_KM)
    relative = min(float(req.relative_speed_kms), 2.0 * speed * 0.999)
    angle = 2.0 * math.asin(relative / (2.0 * speed))
    age = _AD_HOC_DEFAULT_AGE_DAYS if req.tle_age_days is None else req.tle_age_days
    hours = _AD_HOC_DEFAULT_TCA_HOURS if req.time_to_tca_hours is None else req.time_to_tca_hours

    primary_position = np.array([_AD_HOC_RADIUS_KM, 0.0, 0.0])
    primary_velocity = np.array([0.0, speed, 0.0])
    secondary_velocity = np.array([0.0, speed * math.cos(angle), speed * math.sin(angle)])

    # Orthonormal basis of the encounter plane (perpendicular to relative velocity).
    v_rel = primary_velocity - secondary_velocity
    v_hat = v_rel / np.linalg.norm(v_rel)
    in_plane_a = np.array([1.0, 0.0, 0.0])  # radial; already perpendicular to v_rel
    in_plane_b = np.cross(v_hat, in_plane_a)

    miss = float(req.miss_distance_km)
    for degrees in _AD_HOC_ORIENTATIONS_DEG:
        phi = math.radians(degrees)
        offset = miss * (math.cos(phi) * in_plane_a + math.sin(phi) * in_plane_b)
        yield ConjunctionInput(
            primary_position_km=primary_position,
            primary_velocity_kms=primary_velocity,
            secondary_position_km=primary_position - offset,
            secondary_velocity_kms=secondary_velocity,
            time_to_tca_hours=float(hours),
            primary_tle_age_days=age,
            secondary_tle_age_days=age,
            primary_uncertainty_regime=REGIME_PASSIVE,
            secondary_uncertainty_regime=REGIME_PASSIVE,
        )


@router.post("/risk/analyze", response_model=RiskAnalyzeResponse)
def analyze_risk(req: RiskAnalyzeRequest):
    """
    Collision probability, risk score, and factor explanation.

    Give a `conjunction_id` to analyse a screened event, or `miss_distance_km`
    and `relative_speed_kms` (optionally `time_to_tca_hours`, `tle_age_days`) to
    analyse a hypothetical encounter.
    """
    world = get_world()

    if req.conjunction_id:
        event = world.events.get(req.conjunction_id)
        if event is None:
            raise HTTPException(status_code=404, detail=f"Conjunction {req.conjunction_id} not found")
        summary = conjunction_summary(world, event)  # also refreshes the time-dependent score
        assessment = event.assessment
        return RiskAnalyzeResponse(
            risk_score=round(float(assessment.risk_score), 1),
            risk_level=assessment.severity,
            explanation_summary=assessment.narrative,
            shap_factors=shap_factors(assessment),
            collision_probability=float(assessment.pc),
            uncertainty=assessment.uncertainty_summary,
            conjunction=summary,
        )

    if req.miss_distance_km is None or req.relative_speed_kms is None:
        raise HTTPException(
            status_code=422,
            detail="Provide conjunction_id, or both miss_distance_km and relative_speed_kms.",
        )

    # Worst case over miss orientation: see _ad_hoc_conjunctions for why.
    assessment = max((world.engine.assess(c) for c in _ad_hoc_conjunctions(req)), key=lambda a: a.pc)
    return RiskAnalyzeResponse(
        risk_score=round(float(assessment.risk_score), 1),
        risk_level=assessment.severity,
        explanation_summary=(
            assessment.narrative + " Without the encounter geometry the direction of the miss is "
            "unknown, so this is the worst case over miss orientation."
        ),
        shap_factors=shap_factors(assessment),
        collision_probability=float(assessment.pc),
        uncertainty=assessment.uncertainty_summary,
        ad_hoc=True,
    )
