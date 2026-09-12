"""
Tests for the screening, track, and maneuver services.

Physics first: the Clohessy-Wiltshire solution must reproduce the textbook
behaviour of each burn direction, and screening must recover a known miss
distance that the coarse sampling alone would badly overstate.
"""

import math
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from app.services.maneuvers import LEAD_ORBITS, propellant_kg  # noqa: E402
from app.services.screening import screen  # noqa: E402
from app.services.tracks import (  # noqa: E402
    MU_EARTH_KM3_S2,
    TwoBodyTrack,
    clohessy_wiltshire,
    from_jd,
    to_jd,
)
from app.services.world import classify, geometry_label  # noqa: E402

RADIUS_KM = 6778.0
N = math.sqrt(MU_EARTH_KM3_S2 / RADIUS_KM**3)
PERIOD_S = 2 * math.pi / N


class TestTime:
    def test_julian_round_trip(self):
        moment = datetime(2026, 9, 12, 17, 4, 36, 557000, tzinfo=timezone.utc)
        back = from_jd(*to_jd(moment))
        assert abs((back - moment).total_seconds()) < 1e-3


class TestClohessyWiltshire:
    def test_along_track_secular_drift_is_three_dv_t(self):
        # Matches the vis-viva / period-change derivation: 0.30 m/s over 4.2 h
        # gives about 13.6 km. Sample at whole orbits so the periodic term is zero.
        t = np.array([3.0 * PERIOD_S])
        dr, _ = clohessy_wiltshire(np.array([0.0, 0.3e-3, 0.0]), N, t)
        assert dr[0, 1] == pytest.approx(-3.0 * 0.3e-3 * t[0], rel=1e-9)

    def test_radial_burn_returns_to_origin_every_orbit(self):
        dr, _ = clohessy_wiltshire(np.array([1e-3, 0.0, 0.0]), N, np.array([PERIOD_S, 2 * PERIOD_S]))
        assert np.allclose(dr, 0.0, atol=1e-9)

    def test_cross_track_burn_is_bounded_and_peaks_at_quarter_orbit(self):
        t = np.linspace(0, 3 * PERIOD_S, 400)
        dv = 1e-3
        dr, _ = clohessy_wiltshire(np.array([0.0, 0.0, dv]), N, t)
        assert np.max(np.abs(dr[:, 2])) == pytest.approx(dv / N, rel=1e-3)
        quarter, _ = clohessy_wiltshire(np.array([0.0, 0.0, dv]), N, np.array([PERIOD_S / 4]))
        assert quarter[0, 2] == pytest.approx(dv / N, rel=1e-9)

    def test_nothing_happens_before_the_burn(self):
        dr, dv = clohessy_wiltshire(np.array([1e-3, 1e-3, 1e-3]), N, np.array([-100.0]))
        assert np.allclose(dr, 0.0) and np.allclose(dv, 0.0)

    def test_lead_grid_is_not_phase_degenerate(self):
        # Radial and cross-track displacement vanish at every half orbit. A lead
        # grid made only of half-integer orbits would evaluate those burns exactly
        # where they do nothing.
        assert any((lead * 2) % 1 != 0 for lead in LEAD_ORBITS)


class TestTwoBody:
    def test_energy_is_conserved(self):
        v_circ = math.sqrt(MU_EARTH_KM3_S2 / RADIUS_KM)
        jd, fr = to_jd(datetime(2026, 9, 12, tzinfo=timezone.utc))
        track = TwoBodyTrack(
            object_id="t", name="t", object_type="Debris", object_class="debris_fragment",
            epoch_jd=jd, epoch_fr=fr,
            position_km=np.array([RADIUS_KM, 0.0, 0.0]),
            velocity_kms=np.array([0.0, v_circ * 1.01, 0.0]),
        )
        offsets = np.array([-12, -3, 0, 5, 20]) / 24.0
        r, v = track.states(np.full(5, jd), fr + offsets)
        energy = 0.5 * np.sum(v**2, axis=1) - MU_EARTH_KM3_S2 / np.linalg.norm(r, axis=1)
        assert np.ptp(energy) < 1e-7


def _crossing_pair(miss_km, start):
    """
    Two two-body objects built to pass each other at a known miss distance.

    The offset is radial, which is perpendicular to the relative velocity (that
    lies in the along-track / cross-track plane). Only then is the separation at
    the constructed instant the true minimum; an offset with any component along
    the relative velocity makes the real closest approach nearer, and earlier.

    Orbits in crossing planes meet at both nodes, every half orbit, so callers
    should screen a window containing one encounter.
    """
    # Fall midway between 30-second samples, so the coarse grid never lands on
    # the closest approach -- the situation refinement exists to handle.
    tca = start + timedelta(minutes=20, seconds=15)
    jd, fr = to_jd(tca)
    v = math.sqrt(MU_EARTH_KM3_S2 / RADIUS_KM)
    common = dict(object_type="Debris", object_class="debris_fragment", epoch_jd=jd, epoch_fr=fr)
    a = TwoBodyTrack(object_id="a", name="A", position_km=np.array([RADIUS_KM, 0.0, 0.0]),
                     velocity_kms=np.array([0.0, v, 0.0]), **common)
    b = TwoBodyTrack(object_id="b", name="B", position_km=np.array([RADIUS_KM + miss_km, 0.0, 0.0]),
                     velocity_kms=np.array([0.0, v * math.cos(1.2), v * math.sin(1.2)]), **common)
    return a, b, tca


class TestScreening:
    START = datetime(2026, 9, 12, 12, tzinfo=timezone.utc)
    WINDOW_H = 40 / 60  # one encounter; the next node crossing is ~46 min away

    def test_refinement_recovers_the_true_miss(self):
        a, b, tca = _crossing_pair(0.42, self.START)
        found = screen([a, b], self.START, duration_hours=self.WINDOW_H, step_s=30.0, report_km=5.0)
        assert len(found) == 1
        event = found[0]
        assert event.miss_distance_km == pytest.approx(0.42, abs=0.01)
        assert abs((event.tca - tca).total_seconds()) < 1.0
        # The whole point of refining: the sampled minimum is far worse.
        assert event.coarse_distance_km > 10 * event.miss_distance_km

    def test_distant_pairs_are_not_reported(self):
        a, b, _ = _crossing_pair(40.0, self.START)
        assert screen([a, b], self.START, duration_hours=self.WINDOW_H, report_km=25.0) == []

    def test_one_body_is_never_screened_against_itself(self):
        a, b, _ = _crossing_pair(0.0, self.START)
        a.body_key = b.body_key = "same station"
        assert screen([a, b], self.START, duration_hours=self.WINDOW_H, report_km=5.0) == []

    def test_maneuverable_object_is_reported_as_primary(self):
        a, b, _ = _crossing_pair(0.42, self.START)
        b.maneuverable = True
        event = screen([a, b], self.START, duration_hours=self.WINDOW_H, report_km=5.0)[0]
        assert event.primary is b


class TestClassification:
    def test_debris_group_membership_wins_over_name(self):
        # "IRIDIUM 33" is the dead hulk, not an operational satellite.
        assert classify("IRIDIUM 33", "iridium-33-debris")["maneuverable"] is False

    def test_named_debris(self):
        assert classify("COSMOS 1408 DEB")["object_type"] == "Debris"

    def test_station_modules_are_maneuverable(self):
        assert classify("ISS (ZARYA)", "stations")["maneuverable"] is True

    def test_geometry_labels(self):
        v = np.array([0.0, 7.6, 0.0])
        assert geometry_label(v, v) == "Parallel"
        assert geometry_label(v, -v) == "Head-on"
        assert geometry_label(v, np.array([7.6, 0.0, 0.0])) == "Crossing"


class TestPropellant:
    def test_matches_rocket_equation(self):
        expected = 500.0 * (1 - math.exp(-0.30 / (220.0 * 9.80665)))
        assert propellant_kg(0.30, "SMALLSAT") == pytest.approx(expected)

    def test_iss_uses_its_own_mass(self):
        assert propellant_kg(0.10, "ISS (ZARYA)") > 100 * propellant_kg(0.10, "SMALLSAT")
