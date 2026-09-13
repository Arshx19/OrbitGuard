"""Pydantic schemas for satellite API endpoints."""

from pydantic import BaseModel, Field
from typing import Optional, List


class SatelliteSchema(BaseModel):
    satellite_number: int = Field(...)
    name: str = Field(...)
    international_designator: Optional[str] = Field(None)
    inclination_deg: float = Field(...)
    eccentricity: float = Field(...)
    mean_motion_orbits_per_day: float = Field(...)
    epoch: Optional[str] = Field(None)

    # --- added (optional) ---
    object_type: Optional[str] = Field(None, description="Active Satellite / Debris / Rocket Body.")
    maneuverable: Optional[bool] = Field(None)
    tle_age_days: Optional[float] = Field(None)


class SatelliteListResponse(BaseModel):
    total_tracked: int
    satellites: List[SatelliteSchema]

    # --- added (optional): dashboard counts, computed from screening ---
    active_conjunctions: Optional[int] = Field(None)
    high_risk_events: Optional[int] = Field(None)
    satellites_monitored: Optional[int] = Field(None)
