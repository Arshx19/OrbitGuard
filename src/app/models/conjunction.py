"""Pydantic schemas for conjunction, risk, and maneuver API endpoints."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


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


class SHAPFactor(BaseModel):
    factor: str = Field(...)
    contribution_percentage: float = Field(...)


class RiskAnalyzeRequest(BaseModel):
    conjunction_id: Optional[str] = Field(None)
    miss_distance_km: Optional[float] = Field(None)
    relative_speed_kms: Optional[float] = Field(None)
    time_to_tca_hours: Optional[float] = Field(None)
    radial_velocity_kms: float = Field(-0.5)
    approach_angle_degrees: float = Field(88.5)
    uncertainty_factor: float = Field(1.5)


class RiskAnalyzeResponse(BaseModel):
    risk_score: float = Field(...)
    risk_level: str = Field(...)
    explanation_summary: str = Field(...)
    shap_factors: List[SHAPFactor]


class ManeuverRequest(BaseModel):
    conjunction_id: str = Field(...)
    primary_satellite_id: int = Field(...)
    threat_satellite_id: int = Field(...)
    tca: str = Field(...)
    dv_min_ms: float = Field(0.05)
    dv_max_ms: float = Field(1.0)


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


class ManeuverOptimizeResponse(BaseModel):
    conjunction_id: str
    optimal_candidate: Optional[ManeuverCandidateSchema]
    all_candidates: List[ManeuverCandidateSchema]
