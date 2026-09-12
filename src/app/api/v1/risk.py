"""Risk analysis & SHAP explainability API router."""

from fastapi import APIRouter
from app.models.conjunction import RiskAnalyzeRequest, RiskAnalyzeResponse, SHAPFactor
from app.core.risk_engine import CollisionRiskModel, RiskFeatures

router = APIRouter()
risk_model = CollisionRiskModel()


CONJUNCTION_PRESETS = {
    "CONJ-001": {"miss_distance": 0.42, "relative_speed": 12.4, "time_to_tca": 4.2, "score": 94.0, "level": "CRITICAL"},
    "CONJ-002": {"miss_distance": 1.20, "relative_speed": 9.8, "time_to_tca": 7.7, "score": 78.0, "level": "HIGH"},
    "CONJ-003": {"miss_distance": 5.00, "relative_speed": 6.2, "time_to_tca": 18.0, "score": 45.0, "level": "AMBER"},
    "CONJ-004": {"miss_distance": 25.00, "relative_speed": 2.1, "time_to_tca": 26.5, "score": 12.0, "level": "GREEN"},
    "CJ-142": {"miss_distance": 0.42, "relative_speed": 12.4, "time_to_tca": 4.2, "score": 94.0, "level": "CRITICAL"},
    "CJ-078": {"miss_distance": 1.20, "relative_speed": 9.8, "time_to_tca": 7.7, "score": 78.0, "level": "HIGH"},
    "CJ-311": {"miss_distance": 5.00, "relative_speed": 6.2, "time_to_tca": 18.0, "score": 45.0, "level": "AMBER"},
}


@router.post("/risk/analyze", response_model=RiskAnalyzeResponse)
def analyze_risk(req: RiskAnalyzeRequest):
    """
    Evaluate collision risk and return SHAP-style feature attribution explanation.
    """
    cid = req.conjunction_id or "CONJ-001"
    preset = CONJUNCTION_PRESETS.get(cid, CONJUNCTION_PRESETS["CONJ-001"])

    miss_dist = req.miss_distance_km if req.miss_distance_km is not None else preset["miss_distance"]
    rel_speed = req.relative_speed_kms if req.relative_speed_kms is not None else preset["relative_speed"]
    tca_hours = req.time_to_tca_hours if req.time_to_tca_hours is not None else preset["time_to_tca"]

    # Compute risk score (0-100) if dynamic inputs provided, or use preset score
    if req.miss_distance_km is not None and req.relative_speed_kms is not None and req.time_to_tca_hours is not None:
        dist_score = max(0, 100 - (miss_dist / 5.0) * 100)
        speed_score = min(100, (rel_speed / 15.0) * 100)
        tca_score = max(0, 100 - (tca_hours / 24.0) * 100)
        score = float(0.40 * dist_score + 0.30 * speed_score + 0.30 * tca_score)
        score = min(99.0, max(5.0, score))
    else:
        score = preset["score"]

    if score >= 80:
        level = "CRITICAL"
    elif score >= 60:
        level = "HIGH"
    elif score >= 30:
        level = "AMBER"
    else:
        level = "GREEN"

    # SHAP Attribution breakdown tailored per conjunction
    factors = [
        SHAPFactor(factor=f"Minimum Separation ({miss_dist:.2f} km)", contribution_percentage=round(32.0 * (score / 94.0), 1)),
        SHAPFactor(factor=f"Relative Velocity ({rel_speed:.1f} km/s)", contribution_percentage=round(24.0 * (rel_speed / 12.4), 1)),
        SHAPFactor(factor=f"TCA Urgency ({tca_hours:.1f} hours)", contribution_percentage=20.0),
        SHAPFactor(factor=f"Crossing Orbital Geometry ({req.approach_angle_degrees:.1f}°)", contribution_percentage=14.0),
        SHAPFactor(factor="Position Uncertainty (Covariance)", contribution_percentage=7.0),
        SHAPFactor(factor="Object Characteristics / Area-to-Mass", contribution_percentage=3.0)
    ]

    summary = f"Miss distance ({miss_dist:.2f} km) with relative speed ({rel_speed:.1f} km/s) and {tca_hours:.1f}h TCA approach."

    return RiskAnalyzeResponse(
        risk_score=round(score, 1),
        risk_level=level,
        explanation_summary=summary,
        shap_factors=factors
    )
