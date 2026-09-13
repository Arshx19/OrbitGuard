"""Pydantic schemas for conjunction, risk, and maneuver API endpoints.

Every field from the original prototype contract is kept with its original name
and type, so existing clients keep working. Fields added for the computed engine
are optional and documented; clients that do not know about them can ignore them.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class TimelinePoint(BaseModel):
    t: str = Field(..., description="Label relative to closest approach, e.g. 'T-48'.")
    hours: float = Field(..., description="Hours relative to closest approach.")
    distance_km: float = Field(..., description="Propagated separation at that time.")
    after_km: Optional[float] = Field(None, description="Post-maneuver separation at that time.")


class ConjunctionSummary(BaseModel):
    id: str = Field(...)
    satellite1_id: int = Field(...)
    satellite1_name: str = Field(...)
    satellite2_id: int = Field(...)
    satellite2_name: str = Field(...)
    risk_score: float = Field(...)
    risk_level: str = Field(...)
    miss_distance_km: float = Field(...)
    relative_speed_kms: float = Field(...)
    tca: str = Field(...)

    # --- added for the computed engine (all optional) ---
    collision_probability: Optional[float] = Field(
        None, description="Foster 2D collision probability at closest approach.")
    time_to_tca_hours: Optional[float] = Field(None)
    simulated: bool = Field(
        False, description="True for the constructed demonstration event; screened events are False.")
    maneuverable: Optional[bool] = Field(None, description="Whether satellite1 can maneuver.")
    satellite1_type: Optional[str] = Field(None)
    satellite2_type: Optional[str] = Field(None)
    geometry: Optional[str] = Field(None, description="Parallel / Near-crossing / Crossing / Head-on.")
    timeline: Optional[List[TimelinePoint]] = Field(None)
    uncertainty: Optional[Dict[str, Any]] = Field(
        None, description="TLE ages, along-track sigmas, and which uncertainty model produced them.")
    narrative: Optional[str] = Field(None)


class SHAPFactor(BaseModel):
    """
    One risk factor's contribution.

    The name is kept for compatibility with the original contract. The values are
    not SHAP attributions: each is a counterfactual -- the collision probability
    recomputed with that factor reset to a benign baseline. See `explanation`.
    """
    factor: str = Field(...)
    contribution_percentage: float = Field(...)

    # --- added (optional) ---
    direction: Optional[str] = Field(
        None, description="'raises' or 'reduces'. A reducing factor has a negative percentage.")
    explanation: Optional[str] = Field(None, description="The counterfactual, in plain language.")
    counterfactual_probability: Optional[float] = Field(None)


class RiskAnalyzeRequest(BaseModel):
    conjunction_id: Optional[str] = Field(None)
    miss_distance_km: Optional[float] = Field(None)
    relative_speed_kms: Optional[float] = Field(None)
    time_to_tca_hours: Optional[float] = Field(None)
    radial_velocity_kms: float = Field(-0.5)
    approach_angle_degrees: float = Field(88.5)
    uncertainty_factor: float = Field(1.5)

    # --- added (optional) ---
    tle_age_days: Optional[float] = Field(
        None, description="For ad-hoc analysis: element-set age of both objects. Defaults to 0.5 days.")


class RiskAnalyzeResponse(BaseModel):
    risk_score: float = Field(...)
    risk_level: str = Field(...)
    explanation_summary: str = Field(...)
    shap_factors: List[SHAPFactor]

    # --- added (optional) ---
    collision_probability: Optional[float] = Field(None)
    explanation_method: str = Field(
        "counterfactual", description="How shap_factors were produced.")
    uncertainty: Optional[Dict[str, Any]] = Field(None)
    conjunction: Optional[ConjunctionSummary] = Field(
        None, description="The analysed event, when a conjunction_id was given.")
    ad_hoc: bool = Field(
        False, description="True when analysed from supplied parameters rather than a screened event.")


class ManeuverRequest(BaseModel):
    conjunction_id: str = Field(...)
    # These were required in the original contract, but the conjunction id alone
    # identifies the event, and the frontend sends only that. Requiring them made
    # every frontend request fail validation. They are accepted and ignored.
    primary_satellite_id: Optional[int] = Field(None)
    threat_satellite_id: Optional[int] = Field(None)
    tca: Optional[str] = Field(None)
    dv_min_ms: float = Field(0.05)
    dv_max_ms: float = Field(1.0)

    # --- added (optional) ---
    candidate_id: Optional[str] = Field(
        None, description="For /maneuver/validate: the candidate to validate. Defaults to the recommended one.")


class ManeuverCandidateSchema(BaseModel):
    candidate_id: str = Field(...)
    direction_name: str = Field(...)
    delta_v_magnitude_ms: float = Field(...)
    delta_v_rtn_ms: List[float] = Field(...)
    new_miss_distance_km: Optional[float] = Field(None)
    primary_threat_resolved: bool = Field(...)
    secondary_threats_detected: bool = Field(...)
    is_safe: bool = Field(...)
    status: str = Field(...)
    rejection_reason: Optional[str] = Field(None)

    # --- added (optional) ---
    burn_lead_hours: Optional[float] = Field(None, description="Hours before closest approach.")
    burn_time: Optional[str] = Field(None)
    pc_before: Optional[float] = Field(None)
    pc_after: Optional[float] = Field(None)
    propellant_kg: Optional[float] = Field(None)
    rescreened: Optional[bool] = Field(None)
    recommended: bool = Field(False)
    secondary_threat_details: Optional[List[Dict[str, Any]]] = Field(None)
    post_burn_timeline: Optional[List[TimelinePoint]] = Field(None)


class ValidationChecks(BaseModel):
    original_conjunction_resolved: bool
    post_maneuver_trajectory_propagated: bool
    catalog_rescreened: bool
    rescreen_horizon_hours: float
    catalog_objects_screened: int
    new_conjunctions: int


class ManeuverOptimizeResponse(BaseModel):
    conjunction_id: str
    optimal_candidate: Optional[ManeuverCandidateSchema]
    all_candidates: List[ManeuverCandidateSchema]

    # --- added (optional) ---
    candidates_evaluated: Optional[int] = Field(None)
    safety_target: Optional[float] = Field(None)
    pc_before: Optional[float] = Field(None)
    reason: Optional[str] = Field(None, description="Why no candidates were produced, if none were.")
    validated_candidate: Optional[ManeuverCandidateSchema] = Field(
        None, description="For /maneuver/validate: the candidate that was validated, safe or not.")
    checks: Optional[ValidationChecks] = Field(None)
