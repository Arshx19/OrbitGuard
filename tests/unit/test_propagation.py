"""Unit tests for app.core.propagation."""

import pytest
import sys
import os
from datetime import datetime, timedelta
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from app.core.data_ingestion import load_tle_from_string
from app.core.propagation import OrbitalPropagator, propagate_single_tle

SAMPLE_ISS_TLE = """1 25544U 98067A   21275.51473713  .00001282  00000-0  28138-4 0  9925
2 25544  51.6439 211.2001 0007416  82.7281 135.4221 15.49105483281166"""


def test_propagate_single_tle():
    tle = load_tle_from_string(SAMPLE_ISS_TLE)
    assert tle is not None
    now = datetime(2026, 9, 12, 12, 0, 0)
    pos = propagate_single_tle(tle, now)
    assert pos is not None
    assert len(pos) == 3
    # Low Earth orbit distance from Earth center ~ 6700 - 7000 km
    r_norm = np.linalg.norm(pos)
    assert 6000.0 < r_norm < 8000.0


def test_propagate_multiple_times():
    tle = load_tle_from_string(SAMPLE_ISS_TLE)
    propagator = OrbitalPropagator()
    start_time = datetime(2026, 9, 12, 12, 0, 0)
    end_time = start_time + timedelta(hours=1)
    time_step = timedelta(minutes=15)

    timestamps, positions = propagator.propagate_multiple_times(tle.satrec, start_time, end_time, time_step)
    assert len(timestamps) == 5
    assert len(positions) == 5
