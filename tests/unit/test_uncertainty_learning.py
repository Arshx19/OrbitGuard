"""
Tests for the learned uncertainty model.

The central check is recovery: errors are generated from a known sigma(age),
contaminated with the kind of wild outliers the real data contains, and the fit
must find the true coefficients. A method that only "runs" would pass a smoke
test and still learn nonsense.
"""

import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from app.core.data_ingestion import load_tle_from_string  # noqa: E402
from app.core.risk_engine import ConjunctionInput, RiskEngine  # noqa: E402
from app.core.uncertainty import (  # noqa: E402
    LEARNED_MODEL_PATH,
    REGIME_MANEUVERING,
    REGIME_PASSIVE,
    TLEUncertaintyModel,
    learned_models,
    uncertainty_regime,
)
from app.core.uncertainty_learning import (  # noqa: E402
    ErrorSamples,
    coverage,
    fit,
    grouped_folds,
    measure_errors,
    model_document,
    select_degree,
    train_regime,
)

TRUE_A = np.array([0.05, 0.80, 0.10])  # radial, along-track, cross-track, km
TRUE_B = np.array([0.03, 0.45, 0.02])  # km/day


def synthetic(n_objects=600, per_object=3, outlier_fraction=0.0, curvature=None, seed=3):
    rng = np.random.default_rng(seed)
    object_id = np.repeat(np.arange(n_objects), per_object)
    age = rng.uniform(0.1, 1.5, size=object_id.size)
    sigma = TRUE_A + np.outer(age, TRUE_B)
    if curvature is not None:
        sigma = sigma + np.outer(age**2, curvature)
    errors = rng.normal(size=sigma.shape) * sigma

    outliers = rng.random(object_id.size) < outlier_fraction
    # Thousands of kilometres off, like a satellite still raising its orbit.
    errors[outliers] = rng.normal(size=(outliers.sum(), 3)) * np.array([2000.0, 6000.0, 50.0])

    return ErrorSamples(
        object_id=object_id,
        constellation=np.full(object_id.size, "synthetic", dtype=object),
        age_days=age,
        error_rtn_km=errors,
        altitude_km=np.full(object_id.size, 800.0),
    )


class TestRecovery:
    def test_recovers_known_growth(self):
        model = fit(synthetic(), degree=1)
        assert model.coefficients[:, 0] == pytest.approx(TRUE_A, rel=0.15)
        assert model.coefficients[:, 1] == pytest.approx(TRUE_B, rel=0.25)

    def test_wild_outliers_do_not_corrupt_the_fit(self):
        # Five percent of samples thousands of kilometres off. A plain Gaussian
        # fit would inflate sigma enormously; the mixture must not.
        model = fit(synthetic(outlier_fraction=0.05), degree=1)
        assert model.coefficients[:, 0] == pytest.approx(TRUE_A, rel=0.2)
        assert model.coefficients[:, 1] == pytest.approx(TRUE_B, rel=0.3)
        assert model.outlier_fraction == pytest.approx(0.05, abs=0.02)

    def test_wild_outliers_do_not_destabilise_held_out_scoring(self):
        # The fit itself survives outliers under almost any mixture; what breaks
        # is scoring. With a light-tailed outlier component each sample thousands
        # of kilometres off scores a log-likelihood in the thousands, so held-out
        # likelihood -- and the model selection that depends on it -- swings
        # wildly from fold to fold. This happened on the real Starlink data.
        from app.core.uncertainty_learning import cross_validate

        result = cross_validate(synthetic(n_objects=600, outlier_fraction=0.02), degree=1)
        assert np.isfinite(result["held_out_mean_nll"])
        assert result["held_out_nll_standard_error"] < 0.25

    def test_fitted_sigmas_are_calibrated(self):
        samples = synthetic(n_objects=1500)
        model = fit(samples, degree=1)
        cov = coverage(model.sigmas(samples.age_days), samples.error_rtn_km)
        for axis in cov.values():
            assert axis["1_sigma"] == pytest.approx(0.683, abs=0.03)
            assert axis["2_sigma"] == pytest.approx(0.954, abs=0.02)


class TestModelSelection:
    def test_prefers_linear_when_growth_is_linear(self):
        result = train_regime(synthetic(n_objects=800), "synthetic")
        assert result["growth_model"] == "linear"

    def test_detects_genuine_curvature(self):
        samples = synthetic(n_objects=800, curvature=np.array([0.0, 4.0, 0.0]))
        assert train_regime(samples, "synthetic")["growth_model"] == "quadratic"

    def test_one_standard_error_rule(self):
        # Quadratic wins, but by less than the noise: take the simpler model.
        close = {1: {"held_out_mean_nll": 1.00, "held_out_nll_standard_error": 0.05},
                 2: {"held_out_mean_nll": 0.98, "held_out_nll_standard_error": 0.05}}
        assert select_degree(close) == 1
        clear = {1: {"held_out_mean_nll": 1.00, "held_out_nll_standard_error": 0.01},
                 2: {"held_out_mean_nll": 0.90, "held_out_nll_standard_error": 0.01}}
        assert select_degree(clear) == 2


class TestFolds:
    def test_no_satellite_appears_in_two_folds(self):
        samples = synthetic(n_objects=100)
        folds = grouped_folds(samples.object_id, k=5)
        seen = [set(samples.object_id[f]) for f in folds]
        for i in range(5):
            for j in range(i + 1, 5):
                assert not seen[i] & seen[j]
        assert sum(len(f) for f in folds) == len(samples)


ISS = """1 25544U 98067A   26255.20788499  .00004954  00000+0  97729-4 0  9996
2 25544  51.6305 229.4056 0004952 131.3152 228.8264 15.49086570585247"""


class TestMeasurement:
    def test_identical_element_sets_measure_zero_error(self):
        tle = load_tle_from_string(ISS)
        samples = measure_errors([tle], [tle], "self", truth_offsets_days=(0.0, 0.5))
        assert len(samples) == 2
        assert np.allclose(samples.error_rtn_km, 0.0, atol=1e-9)
        assert samples.age_days == pytest.approx([0.0, 0.5])


class TestRegimes:
    def test_frequent_maneuverers(self):
        assert uncertainty_regime("STARLINK-1008") == REGIME_MANEUVERING

    def test_everything_else_is_passive(self):
        for name in ("IRIDIUM 33 DEB", "ISS (ZARYA)", "COSMOS 1408 DEB", ""):
            assert uncertainty_regime(name) == REGIME_PASSIVE


class TestPersistence:
    def test_round_trip_through_json(self, tmp_path):
        result = train_regime(synthetic(n_objects=300), "synthetic")
        path = tmp_path / "model.json"
        path.write_text(json.dumps(model_document({REGIME_PASSIVE: result})))

        loaded = learned_models(str(path))[REGIME_PASSIVE]
        c = result["coefficients"]
        expected = [c["epoch_km"][i] + c["growth_km_per_day"][i] * 1.0 + c["curvature_km_per_day2"][i]
                    for i in range(3)]
        assert loaded.sigmas_rtn_km(1.0) == pytest.approx(expected)
        assert loaded.source.startswith("learned")

    def test_missing_file_means_no_learned_models(self, tmp_path):
        assert learned_models(str(tmp_path / "absent.json")) is None


class TestEngineUsesRegimes:
    def test_each_object_gets_its_regime_model(self):
        tight = TLEUncertaintyModel.from_coefficients((0.01, 0.05, 0.01), (0, 0, 0), source="tight")
        engine = RiskEngine(uncertainty_models={REGIME_PASSIVE: tight})
        base = dict(
            primary_position_km=np.array([6778.0, 0.0, 0.0]),
            primary_velocity_kms=np.array([0.0, 7.669, 0.0]),
            secondary_position_km=np.array([6778.0 - 0.3, 0.0, 0.0]),
            secondary_velocity_kms=np.array([0.0, -4.0, 6.5]),
            time_to_tca_hours=4.0, primary_tle_age_days=1.0, secondary_tle_age_days=1.0,
        )
        with_regime = engine.assess(ConjunctionInput(
            **base, primary_uncertainty_regime=REGIME_PASSIVE, secondary_uncertainty_regime=REGIME_PASSIVE))
        without = engine.assess(ConjunctionInput(**base))

        assert with_regime.uncertainty_summary["primary_model_source"] == "tight"
        assert without.uncertainty_summary["primary_model_source"] == "assumed"
        assert with_regime.pc != pytest.approx(without.pc)


@pytest.mark.skipif(not os.path.exists(LEARNED_MODEL_PATH), reason="model not trained")
class TestCommittedModel:
    """Lock the evidence behind the shipped model into the test suite."""

    @pytest.fixture(scope="class")
    def document(self):
        with open(LEARNED_MODEL_PATH, encoding="utf-8") as handle:
            return json.load(handle)

    def test_along_track_dominates(self, document):
        for regime in document["regimes"].values():
            c = regime["coefficients"]
            assert c["epoch_km"][1] + c["growth_km_per_day"][1] > c["epoch_km"][0] + c["growth_km_per_day"][0]

    def test_maneuvering_elements_degrade_faster(self, document):
        r = document["regimes"]
        assert (r[REGIME_MANEUVERING]["coefficients"]["growth_km_per_day"][1]
                > 5 * r[REGIME_PASSIVE]["coefficients"]["growth_km_per_day"][1])

    def test_learned_model_is_calibrated_on_held_out_satellites(self, document):
        for regime in document["regimes"].values():
            one_sigma = regime["cross_validation"]["coverage_learned"]["along_track"]["1_sigma"]
            assert 0.55 < one_sigma < 0.80

    def test_assumed_model_was_measurably_miscalibrated(self, document):
        cv = document["regimes"][REGIME_MANEUVERING]["cross_validation"]
        assert cv["coverage_assumed"]["along_track"]["1_sigma"] < 0.40
