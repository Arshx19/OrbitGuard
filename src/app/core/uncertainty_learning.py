"""
Learning how fast TLE position error grows, from measured data.

Collision probability needs a position covariance, and public element sets do
not come with one. `app.core.uncertainty` therefore started from an *assumed*
error-growth model. This module replaces the assumption with a measurement.

WHERE THE TRUTH COMES FROM

For several constellations, CelesTrak publishes Supplemental GP element sets:
orbits fitted to the operators' own high-precision ephemerides rather than to
radar tracking. Propagating a satellite's standard element set and its
supplemental one to the same instant, and differencing them in the radial /
along-track / cross-track frame, measures the standard set's position error at
that element set's age. Tens of thousands of such comparisons are available
without an account.

WHAT IS FITTED

Per axis, the error standard deviation grows with element-set age as a
low-order polynomial:

    sigma(age) = a + b * age  [+ c * age^2]

Two things make a naive fit wrong, and both are handled explicitly:

  * **Maneuvers.** A satellite that fires its thrusters after its element set
    was generated can be tens of kilometres from where the set predicts. These
    are real but belong to a different process than the error growth being
    modelled. The likelihood is a two-component mixture -- a Gaussian whose width
    grows with age, plus a heavy-tailed (Cauchy) outlier component -- so a small
    fraction of maneuver-contaminated samples cannot inflate sigma for everything
    else, and element sets that are wildly wrong cannot dominate the fit.
  * **Maneuvering constellations.** Starlink maneuvers every few days and its
    element sets degrade about ten times faster than those of quieter
    satellites. Pooling it with them would make the "typical" error a Starlink
    error. Separate models are fitted per regime.

HOW IT IS VALIDATED

Model form (linear or quadratic growth) is chosen by held-out likelihood under
cross-validation, with folds split *by satellite* so no object's samples appear
in both training and evaluation. Calibration is then checked on held-out
satellites: a well-calibrated model should put about 68% of errors within one
sigma, 95% within two, and 99.7% within three. The same check is run on the
original assumed model, which is how its miscalibration is quantified rather
than merely asserted.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Sequence

import numpy as np
from scipy.optimize import minimize

from app.core.data_ingestion import TLEData
from app.core.uncertainty import TLEUncertaintyModel

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6378.137

# Truth is the supplemental set propagated to these offsets past its own epoch.
# Kept short: the supplemental set also degrades with age, and its error must
# stay small next to the error being measured.
TRUTH_OFFSETS_DAYS = (0.0, 0.25, 0.5)

# The outlier component's scale, as a multiple of each axis's robust spread.
OUTLIER_SCALE = 10.0

COVERAGE_LEVELS = (1.0, 2.0, 3.0)
GAUSSIAN_COVERAGE = {1.0: 0.6827, 2.0: 0.9545, 3.0: 0.9973}

_LOG_FLOOR = -12.0
_AXES = ("radial", "along_track", "cross_track")


@dataclass
class ErrorSamples:
    """Measured element-set errors: one row per (object, evaluation time)."""

    object_id: np.ndarray
    constellation: np.ndarray
    age_days: np.ndarray
    """Absolute element-set age at evaluation, days."""

    error_rtn_km: np.ndarray
    """Standard minus truth position, RTN frame of the truth state, shape (n, 3)."""

    altitude_km: np.ndarray

    def __len__(self) -> int:
        return len(self.age_days)

    def subset(self, mask: np.ndarray) -> "ErrorSamples":
        return ErrorSamples(
            self.object_id[mask], self.constellation[mask], self.age_days[mask],
            self.error_rtn_km[mask], self.altitude_km[mask],
        )

    @classmethod
    def concatenate(cls, parts: Sequence["ErrorSamples"]) -> "ErrorSamples":
        return cls(*(np.concatenate([getattr(p, f) for p in parts]) for f in
                     ("object_id", "constellation", "age_days", "error_rtn_km", "altitude_km")))


def _rtn_basis(r: np.ndarray, v: np.ndarray) -> np.ndarray:
    u_r = r / np.linalg.norm(r)
    h = np.cross(r, v)
    u_n = h / np.linalg.norm(h)
    return np.column_stack([u_r, np.cross(u_n, u_r), u_n])


def measure_errors(
    standard: Sequence[TLEData],
    supplemental: Sequence[TLEData],
    constellation: str,
    truth_offsets_days: Sequence[float] = TRUTH_OFFSETS_DAYS,
) -> ErrorSamples:
    """
    Difference standard element sets against supplemental truth.

    Args:
        standard: Standard GP element sets.
        supplemental: Supplemental GP element sets for the same constellation.
        constellation: Label recorded on every sample.
        truth_offsets_days: Evaluation times relative to each supplemental epoch.

    Returns:
        One sample per matched object per offset at which both propagations
        succeed.
    """
    by_number = {tle.satellite_number: tle for tle in standard if tle.satrec is not None}
    ids, ages, errors, altitudes = [], [], [], []

    for truth in supplemental:
        match = by_number.get(truth.satellite_number)
        if match is None or truth.satrec is None:
            continue
        std, sup = match.satrec, truth.satrec
        for offset in truth_offsets_days:
            jd, fr = sup.jdsatepoch, sup.jdsatepochF + offset
            e1, r1, _ = std.sgp4(jd, fr)
            e2, r2, v2 = sup.sgp4(jd, fr)
            if e1 or e2:
                continue
            r1, r2, v2 = np.asarray(r1), np.asarray(r2), np.asarray(v2)
            basis = _rtn_basis(r2, v2)
            ids.append(truth.satellite_number)
            ages.append(abs((jd - std.jdsatepoch) + (fr - std.jdsatepochF)))
            errors.append(basis.T @ (r1 - r2))
            altitudes.append(float(np.linalg.norm(r2)) - EARTH_RADIUS_KM)

    count = len(ids)
    logger.info("%s: %d error samples from %d objects.", constellation, count, len(set(ids)))
    return ErrorSamples(
        object_id=np.asarray(ids, dtype=np.int64),
        constellation=np.full(count, constellation, dtype=object),
        age_days=np.asarray(ages, dtype=np.float64),
        error_rtn_km=np.asarray(errors, dtype=np.float64).reshape(count, 3),
        altitude_km=np.asarray(altitudes, dtype=np.float64),
    )


# ---------------------------------------------------------------------------
# Robust maximum-likelihood fit
# ---------------------------------------------------------------------------


def _robust_spread(errors: np.ndarray) -> np.ndarray:
    """Per-axis spread by median absolute deviation, scaled to a Gaussian sigma."""
    centred = errors - np.median(errors, axis=0)
    return np.maximum(1.4826 * np.median(np.abs(centred), axis=0), 1e-6)


def _sigmas(coefficients: np.ndarray, age: np.ndarray) -> np.ndarray:
    """coefficients: (3 axes, 3 terms) of [a, b, c]. Returns (n, 3)."""
    powers = np.stack([np.ones_like(age), age, age * age], axis=-1)  # (n, 3)
    return powers @ coefficients.T


def _unpack(theta: np.ndarray, degree: int) -> tuple:
    terms = degree + 1
    coefficients = np.zeros((3, 3))
    coefficients[:, :terms] = np.exp(theta[: 3 * terms].reshape(3, terms))
    weight = 1.0 / (1.0 + math.exp(-theta[3 * terms]))
    return coefficients, weight


def _log_likelihood(coefficients, weight, outlier_sigma, age, errors) -> np.ndarray:
    """
    Per-sample log-likelihood under the inlier/outlier mixture.

    Inliers are Gaussian with age-dependent width. Outliers are Cauchy, whose
    heavy tail matters: the training data contains element sets thousands of
    kilometres off -- freshly launched satellites still raising their orbits.
    Under a Gaussian outlier component each of those scores a log-likelihood in
    the thousands, swamping every other sample. Under a Cauchy one the penalty
    grows only logarithmically, so no hand-chosen cutoff is needed to decide
    which samples count.
    """
    sigma = _sigmas(coefficients, age)
    inlier = -1.5 * math.log(2.0 * math.pi) - np.sum(0.5 * (errors / sigma) ** 2 + np.log(sigma), axis=1)
    outlier = -np.sum(np.log(math.pi * outlier_sigma) + np.log1p((errors / outlier_sigma) ** 2), axis=1)
    return np.logaddexp(math.log(1.0 - weight) + inlier, math.log(weight) + outlier)


@dataclass
class FittedModel:
    degree: int
    coefficients: np.ndarray
    """(3, 3): per axis (radial, along-track, cross-track), [epoch, growth, curvature]."""

    outlier_fraction: float
    outlier_sigma_km: np.ndarray
    mean_nll: float

    def sigmas(self, age: np.ndarray) -> np.ndarray:
        return _sigmas(self.coefficients, np.asarray(age, dtype=np.float64))

    def as_uncertainty_model(self, source: str, age_range) -> TLEUncertaintyModel:
        c = self.coefficients
        return TLEUncertaintyModel.from_coefficients(
            epoch_km=tuple(c[:, 0]), growth_km_per_day=tuple(c[:, 1]),
            curvature_km_per_day2=tuple(c[:, 2]), source=source,
            trained_age_range_days=tuple(age_range),
        )


def fit(samples: ErrorSamples, degree: int, outlier_sigma_km: np.ndarray = None) -> FittedModel:
    """
    Maximum-likelihood fit of sigma(age) with a broad outlier component.

    Args:
        samples: Training samples for one regime.
        degree: 1 for linear growth, 2 to add a quadratic term.
        outlier_sigma_km: Width of the outlier component per axis. Defaults to
            OUTLIER_SCALE times each axis's robust spread in the training data.
    """
    age, errors = samples.age_days, samples.error_rtn_km
    spread = _robust_spread(errors)
    if outlier_sigma_km is None:
        outlier_sigma_km = OUTLIER_SCALE * spread

    terms = degree + 1
    initial = np.zeros((3, terms))
    initial[:, 0] = 0.5 * spread
    initial[:, 1] = 0.5 * spread
    if degree == 2:
        initial[:, 2] = 0.05 * spread
    theta0 = np.concatenate([np.log(initial).ravel(), [math.log(0.05 / 0.95)]])

    def objective(theta):
        coefficients, weight = _unpack(theta, degree)
        return -np.mean(_log_likelihood(coefficients, weight, outlier_sigma_km, age, errors))

    bounds = [(_LOG_FLOOR, 5.0)] * (3 * terms) + [(-9.0, 0.0)]  # outlier weight <= 0.5
    result = minimize(objective, theta0, method="L-BFGS-B", bounds=bounds,
                      options={"maxiter": 2000})
    coefficients, weight = _unpack(result.x, degree)
    return FittedModel(degree, coefficients, weight, np.asarray(outlier_sigma_km), float(result.fun))


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def coverage(sigmas: np.ndarray, errors: np.ndarray) -> Dict[str, Dict[str, float]]:
    """Fraction of errors within k sigma, per axis, for k in COVERAGE_LEVELS."""
    ratio = np.abs(errors) / sigmas
    return {
        axis: {f"{k:g}_sigma": float(np.mean(ratio[:, i] <= k)) for k in COVERAGE_LEVELS}
        for i, axis in enumerate(_AXES)
    }


def assumed_sigmas(model: TLEUncertaintyModel, age: np.ndarray) -> np.ndarray:
    return np.array([model.sigmas_rtn_km(a) for a in age])


def grouped_folds(object_id: np.ndarray, k: int, seed: int = 7) -> List[np.ndarray]:
    """Split sample indices into k folds such that each object lands in exactly one."""
    objects = np.unique(object_id)
    rng = np.random.default_rng(seed)
    rng.shuffle(objects)
    fold_of = {obj: i % k for i, obj in enumerate(objects)}
    labels = np.array([fold_of[o] for o in object_id])
    return [np.nonzero(labels == i)[0] for i in range(k)]


def _mean(dicts: List[Dict[str, Dict[str, float]]]) -> Dict[str, Dict[str, float]]:
    return {axis: {key: float(np.mean([d[axis][key] for d in dicts])) for key in dicts[0][axis]}
            for axis in dicts[0]}


def cross_validate(samples: ErrorSamples, degree: int, k: int = 5) -> Dict[str, object]:
    """Held-out likelihood and calibration, folding by object."""
    held_out_nll, learned_cov, assumed_cov = [], [], []
    by_constellation: Dict[str, List[Dict]] = {}
    assumed = TLEUncertaintyModel()

    for fold in grouped_folds(samples.object_id, k):
        train_mask = np.ones(len(samples), dtype=bool)
        train_mask[fold] = False
        train, test = samples.subset(train_mask), samples.subset(~train_mask)

        model = fit(train, degree)
        held_out_nll.append(-float(np.mean(_log_likelihood(
            model.coefficients, model.outlier_fraction, model.outlier_sigma_km,
            test.age_days, test.error_rtn_km))))
        learned_cov.append(coverage(model.sigmas(test.age_days), test.error_rtn_km))
        assumed_cov.append(coverage(assumed_sigmas(assumed, test.age_days), test.error_rtn_km))

        for name in np.unique(test.constellation):
            m = test.constellation == name
            by_constellation.setdefault(str(name), []).append(
                coverage(model.sigmas(test.age_days[m]), test.error_rtn_km[m]))

    return {
        "folds": k,
        "held_out_mean_nll": float(np.mean(held_out_nll)),
        "held_out_nll_standard_error": float(np.std(held_out_nll, ddof=1) / math.sqrt(k)),
        "coverage_learned": _mean(learned_cov),
        "coverage_assumed": _mean(assumed_cov),
        "coverage_learned_by_constellation": {n: _mean(c) for n, c in by_constellation.items()},
    }


def select_degree(selection: Dict[int, Dict[str, object]]) -> int:
    """
    Pick the growth order by the one-standard-error rule.

    Take the simplest model whose held-out likelihood is within one standard
    error of the best. A quadratic term that wins by less than the fold-to-fold
    noise has not earned its extra parameters, and would extrapolate badly past
    the ages seen in training.
    """
    best = min(selection, key=lambda d: selection[d]["held_out_mean_nll"])
    threshold = selection[best]["held_out_mean_nll"] + selection[best]["held_out_nll_standard_error"]
    return min(d for d in selection if selection[d]["held_out_mean_nll"] <= threshold)


def train_regime(samples: ErrorSamples, description: str, k: int = 5) -> Dict[str, object]:
    """
    Select the growth model by cross-validation, then fit it on all data.

    Returns a serialisable record: coefficients, provenance, the model-selection
    evidence, and held-out calibration against the assumed model.
    """
    selection = {degree: cross_validate(samples, degree, k) for degree in (1, 2)}
    best = select_degree(selection)
    final = fit(samples, best)

    age_range = (float(np.percentile(samples.age_days, 1)), float(np.percentile(samples.age_days, 99)))
    n_objects = int(len(np.unique(samples.object_id)))
    constellations = sorted({str(c) for c in samples.constellation})
    source = (
        f"learned from {len(samples):,} measured errors on {n_objects:,} satellites "
        f"({', '.join(constellations)})"
    )

    reference_ages = np.array([0.5, 1.0, 2.0])
    learned_ref = final.sigmas(reference_ages)
    assumed_ref = assumed_sigmas(TLEUncertaintyModel(), reference_ages)

    return {
        "description": description,
        "source": source,
        "constellations": constellations,
        "n_samples": int(len(samples)),
        "n_objects": n_objects,
        "trained_age_range_days": list(age_range),
        "growth_model": {1: "linear", 2: "quadratic"}[best],
        "coefficients": {
            "epoch_km": final.coefficients[:, 0].tolist(),
            "growth_km_per_day": final.coefficients[:, 1].tolist(),
            "curvature_km_per_day2": final.coefficients[:, 2].tolist(),
        },
        "outlier_fraction": final.outlier_fraction,
        "model_selection": {
            {1: "linear", 2: "quadratic"}[d]: {
                "held_out_mean_nll": selection[d]["held_out_mean_nll"],
                "standard_error": selection[d]["held_out_nll_standard_error"],
            }
            for d in selection
        },
        "cross_validation": selection[best],
        "sigma_comparison_km": {
            f"{age:g}_days": {
                axis: {"learned": float(learned_ref[i, j]), "assumed": float(assumed_ref[i, j])}
                for j, axis in enumerate(_AXES)
            }
            for i, age in enumerate(reference_ages)
        },
    }


def model_document(regimes: Dict[str, Dict[str, object]]) -> Dict[str, object]:
    """Wrap per-regime results with provenance for writing to models/."""
    return {
        "schema_version": 1,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "method": (
            "Standard CelesTrak GP element sets propagated with SGP4 and differenced "
            "against CelesTrak Supplemental GP (operator-ephemeris-derived) element "
            "sets in the RTN frame; per-axis sigma(age) fitted by maximum likelihood "
            "with a Gaussian outlier component; growth order selected by 5-fold "
            "cross-validation grouped by satellite."
        ),
        "regimes": regimes,
    }
