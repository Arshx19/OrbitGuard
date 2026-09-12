"""Unit tests for app.core.maneuver_optimizer."""

import pytest
import sys
import os
from datetime import datetime
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from app.core.maneuver_optimizer import ManeuverOptimizer, compute_rtn_frame, rtn_to_eci_delta_v


def test_compute_rtn_frame():
    pos_eci = np.array([7000.0, 0.0, 0.0])
    vel_eci = np.array([0.0, 7.5, 0.0])

    u_r, u_t, u_n = compute_rtn_frame(pos_eci, vel_eci)
    assert np.allclose(u_r, [1.0, 0.0, 0.0])
    assert np.allclose(u_t, [0.0, 1.0, 0.0])
    assert np.allclose(u_n, [0.0, 0.0, 1.0])


def test_generate_candidate_grid():
    optimizer = ManeuverOptimizer()
    burn_time = datetime(2026, 9, 12, 12, 0, 0)
    grid = optimizer.generate_candidate_grid(burn_time, dv_min_ms=0.1, dv_max_ms=0.5, num_steps=3)
    assert len(grid) > 0
    # Along track candidates should exist
    along_track = [c for c in grid if "Along-track" in c.direction_name]
    assert len(along_track) > 0
