"""Pydantic schemas for satellite API endpoints."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class SatelliteSchema(BaseModel):
    satellite_number: int = Field(...)
    name: str = Field(...)
    international_designator: Optional[str] = Field(None)
    inclination_deg: float = Field(...)
    eccentricity: float = Field(...)
    mean_motion_orbits_per_day: float = Field(...)
    epoch: Optional[str] = Field(None)


class SatelliteListResponse(BaseModel):
    total_tracked: int
    satellites: List[SatelliteSchema]
