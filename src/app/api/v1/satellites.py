"""Satellites API router serving real TLE data from data/raw/."""

import os
from typing import List
from fastapi import APIRouter

try:
    from app.models.satellite import SatelliteListResponse, SatelliteSchema
    from app.core.data_ingestion import TLEDataIngestion
except ImportError:
    from src.app.models.satellite import SatelliteListResponse, SatelliteSchema
    from src.app.core.data_ingestion import TLEDataIngestion

router = APIRouter()

_data_dir = os.getenv("DATA_DIR", "data/raw")
_ingestion = TLEDataIngestion(_data_dir)


@router.get("/satellites", response_model=SatelliteListResponse)
def get_satellites():
    """List all tracked satellites and space debris in the TLE catalog."""
    tle_objects = _ingestion.load_all_tle_files()

    if not tle_objects:
        return SatelliteListResponse(
            total_tracked=0,
            satellites=[]
        )

    satellites = []
    # Slice first 50 objects for instant API response
    for tle in tle_objects[:50]:
        satellites.append(
            SatelliteSchema(
                satellite_number=tle.satellite_number,
                name=tle.designation or f"SAT #{tle.satellite_number}",
                international_designator=tle.international_designator or "UNKNOWN",
                inclination_deg=tle.inclination,
                eccentricity=tle.eccentricity,
                mean_motion_orbits_per_day=tle.mean_motion,
                epoch=tle.epoch.isoformat() if tle.epoch else "2026-09-12T12:00:00Z"
            )
        )

    return SatelliteListResponse(
        total_tracked=len(tle_objects),
        satellites=satellites
    )
