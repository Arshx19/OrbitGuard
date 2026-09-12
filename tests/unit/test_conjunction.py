"""Unit tests for app.core.conjunction."""

import pytest
import sys
import os
from datetime import datetime, timedelta
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from app.core.conjunction import ConjunctionDetector, ConjunctionResult


def test_conjunction_result_to_dict():
    res = ConjunctionResult(
        satellite1_id=25544,
        satellite2_id=25545,
        tca=datetime(2026, 9, 12, 12, 0, 0),
        miss_distance=0.42,
        position1=np.array([1000.0, 2000.0, 3000.0]),
        position2=np.array([1000.3, 2000.2, 3000.2])
    )
    d = res.to_dict()
    assert d['satellite1_id'] == 25544
    assert d['satellite2_id'] == 25545
    assert d['miss_distance_km'] == 0.42


def test_conjunction_geometry():
    detector = ConjunctionDetector(miss_distance_threshold=5.0)
    pos1 = np.array([7000.0, 0.0, 0.0])
    pos2 = np.array([7000.4, 0.0, 0.0])
    vel1 = np.array([0.0, 7.5, 0.0])
    vel2 = np.array([0.0, -7.5, 0.0])

    geom = detector.calculate_conjunction_geometry(pos1, pos2, vel1, vel2)
    assert abs(geom['miss_distance_km'] - 0.4) < 1e-3
    assert abs(geom['relative_speed_kms'] - 15.0) < 1e-3
