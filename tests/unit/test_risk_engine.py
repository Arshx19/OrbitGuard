"""
Tests for the risk engine.

The emphasis is on the properties that make the score defensible: that it is
driven by a real probability, that urgency cannot manufacture risk on its own,
and that the counterfactual explanations agree with the calculation they claim
to explain.
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from app.core.risk_engine import (  # noqa: E402
    PC_THRESHOLD_CRITICAL,
    ConjunctionInput,
    RiskEngine,
    severity_for_pc,
)
from app.core.uncertainty import TLEUncertaintyModel  # noqa: E402


def make_conjunction(miss_km=0.42, hours=4.2, age_days=1.0, **overrides):
    """A crossing conjunction in a 400 km orbit, built around a given miss."""
    primary_position = np.array([6778.0, 0.0, 0.0])
    primary_velocity = np.array([0.0, 7.669, 0.0])
    # Offset the secondary along the radial direction, and give it a velocity
    # crossing the primary's so the relative speed is realistically large.
    secondary_position = primary_position - np.array([miss_km, 0.0, 0.0])
    secondary_velocity = np.array([0.0, -4.0, 6.5])

    params = dict(
        primary_position_km=primary_position,
        primary_velocity_kms=primary_velocity,
        secondary_position_km=secondary_position,
        secondary_velocity_kms=secondary_velocity,
        time_to_tca_hours=hours,
        primary_tle_age_days=age_days,
        secondary_tle_age_days=age_days,
        primary_id=25544,
        secondary_id=99999,
    )
    params.update(overrides)
    return ConjunctionInput(**params)


class TestSeverityBands:
    @pytest.mark.parametrize(
        "pc,expected",
        [
            (1e-3, "CRITICAL"),
            (1e-4, "CRITICAL"),
            (5e-5, "HIGH"),
            (5e-6, "AMBER"),
            (1e-9, "GREEN"),
        ],
    )
    def test_thresholds(self, pc, expected):
        assert severity_for_pc(pc) == expected


class TestScoring:
    def test_score_is_bounded(self):
        engine = RiskEngine()
        for miss in [0.001, 0.1, 1.0, 50.0]:
            assessment = engine.assess(make_conjunction(miss_km=miss))
            assert 0.0 <= assessment.risk_score <= 100.0

    def test_closer_approach_scores_higher(self):
        engine = RiskEngine()
        near = engine.assess(make_conjunction(miss_km=0.2))
        far = engine.assess(make_conjunction(miss_km=8.0))
        assert near.risk_score > far.risk_score
        assert near.pc > far.pc

    def test_urgency_cannot_manufacture_risk(self):
        # A negligible-probability event must stay negligible however imminent
        # it is. This is the failure mode of additive risk scores.
        engine = RiskEngine()
        imminent = engine.assess(make_conjunction(miss_km=200.0, hours=0.5))
        distant = engine.assess(make_conjunction(miss_km=200.0, hours=60.0))
        assert imminent.risk_score == pytest.approx(0.0, abs=1e-9)
        assert distant.risk_score == pytest.approx(0.0, abs=1e-9)

    def test_urgency_raises_score_at_equal_probability(self):
        engine = RiskEngine()
        soon = engine.assess(make_conjunction(hours=1.0))
        later = engine.assess(make_conjunction(hours=60.0))
        assert soon.pc == pytest.approx(later.pc, rel=1e-12), "Pc must not depend on TCA"
        assert soon.risk_score > later.risk_score

    def test_probability_is_independent_of_time_to_tca(self):
        # Stated explicitly because conflating the two is the common mistake.
        engine = RiskEngine()
        assessments = [engine.assess(make_conjunction(hours=h)) for h in [0.5, 12, 48]]
        probabilities = {round(a.pc, 18) for a in assessments}
        assert len(probabilities) == 1


class TestExplainability:
    def test_contributions_sum_to_one_hundred(self):
        engine = RiskEngine()
        assessment = engine.assess(make_conjunction())
        elevating = [f for f in assessment.factors if f.contribution_percent > 0]
        assert elevating, "a close, uncertain conjunction should have risk drivers"
        assert sum(f.contribution_percent for f in elevating) == pytest.approx(100.0)

    def test_counterfactual_matches_a_real_recomputation(self):
        # The explanation must be the physics evaluated twice, not a narrative
        # bolted on afterwards. Reproduce the miss-distance counterfactual by
        # hand and check it agrees.
        engine = RiskEngine(benign_miss_distance_km=10.0)
        conjunction = make_conjunction(miss_km=0.42)
        assessment = engine.assess(conjunction)

        factor = next(f for f in assessment.factors if f.name == "miss_distance")

        r_rel = conjunction.relative_position_km()
        scaled = r_rel * (10.0 / np.linalg.norm(r_rel))
        recomputed = engine._pc_for(conjunction, relative_position_km=scaled).pc

        assert factor.counterfactual_pc == pytest.approx(recomputed, rel=1e-12)
        assert factor.counterfactual_pc < assessment.pc

    def test_fresh_ephemeris_removes_the_staleness_factor(self):
        engine = RiskEngine()
        fresh = engine.assess(make_conjunction(age_days=0.0))
        assert not any(f.name == "tle_staleness" for f in fresh.factors)

    def test_stale_ephemeris_is_a_named_driver(self):
        engine = RiskEngine()
        stale = engine.assess(make_conjunction(miss_km=3.0, age_days=4.0))
        names = {f.name for f in stale.factors}
        assert "tle_staleness" in names

    def test_narrative_mentions_probability_and_severity(self):
        engine = RiskEngine()
        assessment = engine.assess(make_conjunction())
        assert "Collision probability" in assessment.narrative
        assert assessment.severity in assessment.narrative


class TestUncertaintyModel:
    def test_along_track_error_dominates(self):
        model = TLEUncertaintyModel()
        sigma_r, sigma_t, sigma_n = model.sigmas_rtn_km(age_days=3.0)
        assert sigma_t > sigma_r
        assert sigma_t > sigma_n

    def test_uncertainty_grows_with_age(self):
        model = TLEUncertaintyModel()
        young = model.sigmas_rtn_km(0.0)[1]
        old = model.sigmas_rtn_km(5.0)[1]
        assert old > young

    def test_covariance_rotation_preserves_eigenvalues(self):
        # Rotating a covariance between frames must not change its scale.
        from app.core.uncertainty import covariance_rtn_to_inertial

        model = TLEUncertaintyModel()
        cov_rtn = model.covariance_rtn_km2(age_days=2.0)
        cov_eci = covariance_rtn_to_inertial(
            cov_rtn, np.array([6778.0, 0.0, 0.0]), np.array([0.0, 7.669, 0.0])
        )
        assert np.allclose(
            np.sort(np.linalg.eigvalsh(cov_rtn)),
            np.sort(np.linalg.eigvalsh(cov_eci)),
            rtol=1e-10,
        )


class TestRankingAndManeuver:
    def test_queue_is_ordered_by_score(self):
        engine = RiskEngine()
        events = [
            make_conjunction(miss_km=5.0, hours=40.0, primary_id=1),
            make_conjunction(miss_km=0.3, hours=3.0, primary_id=2),
            make_conjunction(miss_km=1.5, hours=10.0, primary_id=3),
        ]
        ranked = engine.assess_many(events)
        scores = [a.risk_score for a in ranked]
        assert scores == sorted(scores, reverse=True)
        assert ranked[0].primary_id == 2

    def test_maneuver_reduces_probability(self):
        engine = RiskEngine()
        conjunction = make_conjunction(miss_km=0.42)
        # A 13.6 km along-track displacement, the figure a 0.30 m/s burn buys
        # over a 4.2 hour lead time.
        after = conjunction.relative_position_km() + np.array([0.0, 13.6, 0.0])
        result = engine.pc_reduction(conjunction, after)
        assert result["pc_after"] < result["pc_before"]
        assert result["reduction_factor"] > 1.0

    def test_critical_event_crosses_the_maneuver_threshold(self):
        # Close approach on fresh tracking data: the uncertainty is small enough
        # that the probability mass genuinely overlaps the target.
        engine = RiskEngine()
        assessment = engine.assess(make_conjunction(miss_km=0.10, age_days=0.0))
        assert assessment.pc >= PC_THRESHOLD_CRITICAL
        assert assessment.severity == "CRITICAL"

    def test_staleness_alone_can_change_the_severity_band(self):
        # The same geometry assessed on fresh versus half-day-old elements lands
        # in different bands, because Pc depends on the overlap between the
        # uncertainty distribution and the target -- not on distance alone.
        # This is the behaviour that distinguishes a real Pc from a heuristic.
        engine = RiskEngine()
        fresh = engine.assess(make_conjunction(miss_km=0.42, age_days=0.0))
        stale = engine.assess(make_conjunction(miss_km=0.42, age_days=0.5))
        assert fresh.severity == "AMBER"
        assert stale.severity == "HIGH"
        assert stale.pc > fresh.pc
