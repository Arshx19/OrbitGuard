"""Unit tests for app.core.validation."""

import pytest
import sys
import os
from datetime import datetime, timedelta
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from app.core.data_ingestion import load_tle_from_string
from app.core.maneuver_optimizer import ManeuverCandidate
from app.core.validation import EnvironmentValidator

SAMPLE_ISS_TLE = """1 25544U 98067A   21275.51473713  .00001282  00000-0  28138-4 0  9925
2 25544  51.6439 211.2001 0007416  82.7281 135.4221 15.49105483281166"""

SAMPLE_CLOSE_TLE = """1 25545U 98067B   21275.51473713  .00001282  00000-0  28138-4 0  9926
2 25545  51.6439 211.2001 0007416  82.7281 135.4221 15.49105483281166"""


def test_environment_validator():
    validator = EnvironmentValidator(safe_miss_threshold_km=2.0)
    tle_iss = load_tle_from_string(SAMPLE_ISS_TLE)
    tle_close = load_tle_from_string(SAMPLE_CLOSE_TLE)

    now = datetime(2026, 9, 12, 12, 0, 0)
    tca = now + timedelta(hours=4)
    burn_time = now + timedelta(hours=1)

    cand = ManeuverCandidate(
        candidate_id="CAND-01",
        delta_v_rtn=np.array([0.0, 0.3, 0.0]),  # 0.3 m/s along track
        direction_name="Along-track (+ Prograde)",
        burn_time=burn_time,
        delta_v_magnitude_ms=0.3
    )

    eval_cand = validator.evaluate_candidate(
        candidate=cand,
        primary_sat_tle=tle_iss,
        threat_sat_tle=tle_close,
        catalog_tles=[tle_iss, tle_close],
        primary_tca=tca
    )

    assert eval_cand.new_miss_distance_km is not None
    assert eval_cand.primary_threat_resolved is True
