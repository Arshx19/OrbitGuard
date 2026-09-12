"""
TLE position-uncertainty model for ORBITGUARD AI.

Collision probability is meaningless without a covariance, and this is the
uncomfortable part of working from public data: **TLEs do not ship with one.**
Operational conjunction assessment uses covariances from the tracking filter
that produced the ephemeris; those are not public. So any Pc computed from TLEs
rests on an *assumed* uncertainty model, and the honest thing to do is make that
assumption explicit, parameterised, and visible in the UI rather than burying a
magic number somewhere in the risk engine.

The model here captures the three effects that dominate TLE error growth:

  1. **Along-track error dominates.** A small error in the estimated semi-major
     axis becomes a period error, which accumulates as a growing along-track
     offset. This is why the uncertainty ellipsoid of an aging TLE is a long
     thin cigar lying along the velocity vector.
  2. **Error grows with propagation age.** A TLE is most accurate near its
     epoch and degrades from there.
  3. **Radial and cross-track stay comparatively bounded.** Both are largely
     oscillatory rather than secular, so they grow far more slowly.

The default coefficients are order-of-magnitude values consistent with published
TLE-accuracy studies (roughly a kilometre of along-track error per day of
propagation for a typical LEO object). They are *defaults, not measurements*.
Treat them as a documented assumption, report them alongside any Pc, and use
`covariance_sensitivity_band()` to show how much the answer would move if they
are wrong.

A note on what would make this better: fitting these coefficients empirically,
by propagating older TLEs forward and measuring their divergence from later TLEs
for the same object, would turn the assumption into a measurement. That is the
natural next step and the interface here is built to accept fitted coefficients
in place of the defaults.
"""

from __future__ import annotations

import logging
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TLEUncertaintyModel:
    """
    Parameterised RTN position-uncertainty growth for a TLE-derived ephemeris.

    Standard deviations grow with propagation age as a low-order polynomial:

        sigma(age) = sigma_at_epoch + growth_rate * age + curvature * age^2

    The defaults are hand-assumed, order-of-magnitude values with no curvature.
    `learned_models()` loads coefficients fitted to measured TLE errors instead;
    see `app.core.uncertainty_learning` for how, and what the measurements
    showed about the assumption.
    """

    sigma_radial_epoch_km: float = 0.10
    sigma_along_track_epoch_km: float = 0.30
    sigma_cross_track_epoch_km: float = 0.10

    growth_radial_km_per_day: float = 0.20
    growth_along_track_km_per_day: float = 1.50
    growth_cross_track_km_per_day: float = 0.20

    curvature_radial_km_per_day2: float = 0.0
    curvature_along_track_km_per_day2: float = 0.0
    curvature_cross_track_km_per_day2: float = 0.0

    source: str = "assumed"
    """Where the coefficients came from: "assumed", or a description of the fit."""

    trained_age_range_days: Optional[Tuple[float, float]] = field(default=None, compare=False)
    """For a learned model, the element-set ages the training data spanned."""

    def sigmas_rtn_km(self, age_days: float) -> Tuple[float, float, float]:
        """
        Standard deviations in the radial / along-track / cross-track frame.

        Args:
            age_days: Time between the TLE epoch and the evaluation time, in
                days. Negative ages (propagating backwards) are treated by
                magnitude, since error grows in either direction from epoch.

        Returns:
            Tuple of (sigma_radial, sigma_along_track, sigma_cross_track) in km.
        """
        age = abs(float(age_days))
        return (
            self.sigma_radial_epoch_km + self.growth_radial_km_per_day * age
            + self.curvature_radial_km_per_day2 * age * age,
            self.sigma_along_track_epoch_km + self.growth_along_track_km_per_day * age
            + self.curvature_along_track_km_per_day2 * age * age,
            self.sigma_cross_track_epoch_km + self.growth_cross_track_km_per_day * age
            + self.curvature_cross_track_km_per_day2 * age * age,
        )

    @classmethod
    def from_coefficients(
        cls,
        epoch_km: Tuple[float, float, float],
        growth_km_per_day: Tuple[float, float, float],
        curvature_km_per_day2: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        source: str = "learned",
        trained_age_range_days: Optional[Tuple[float, float]] = None,
    ) -> "TLEUncertaintyModel":
        """Build a model from per-axis (radial, along-track, cross-track) coefficients."""
        return cls(
            sigma_radial_epoch_km=float(epoch_km[0]),
            sigma_along_track_epoch_km=float(epoch_km[1]),
            sigma_cross_track_epoch_km=float(epoch_km[2]),
            growth_radial_km_per_day=float(growth_km_per_day[0]),
            growth_along_track_km_per_day=float(growth_km_per_day[1]),
            growth_cross_track_km_per_day=float(growth_km_per_day[2]),
            curvature_radial_km_per_day2=float(curvature_km_per_day2[0]),
            curvature_along_track_km_per_day2=float(curvature_km_per_day2[1]),
            curvature_cross_track_km_per_day2=float(curvature_km_per_day2[2]),
            source=source,
            trained_age_range_days=trained_age_range_days,
        )

    def covariance_rtn_km2(self, age_days: float) -> np.ndarray:
        """Diagonal 3x3 covariance in the RTN frame, km^2."""
        sigma_r, sigma_t, sigma_n = self.sigmas_rtn_km(age_days)
        return np.diag([sigma_r**2, sigma_t**2, sigma_n**2])

    def describe(self, age_days: float) -> Dict[str, float]:
        """Human-readable summary for display alongside a Pc figure."""
        sigma_r, sigma_t, sigma_n = self.sigmas_rtn_km(age_days)
        age = abs(float(age_days))
        # Only ages beyond the training data count as extrapolation: that is where
        # a fitted growth rate is projected into the unmeasured. Ages slightly
        # below the youngest sample just read the epoch term, which is close to
        # what was measured.
        extrapolated = (
            self.trained_age_range_days is not None and age > self.trained_age_range_days[1]
        )
        return {
            "tle_age_days": age,
            "sigma_radial_km": sigma_r,
            "sigma_along_track_km": sigma_t,
            "sigma_cross_track_km": sigma_n,
            "model_source": self.source,
            "extrapolated": extrapolated,
        }


def rtn_rotation_matrix(
    position_km: np.ndarray,
    velocity_kms: np.ndarray,
) -> np.ndarray:
    """
    Build the rotation taking RTN components into the inertial frame.

    Args:
        position_km: Inertial position, shape (3,).
        velocity_kms: Inertial velocity, shape (3,).

    Returns:
        A 3x3 matrix whose columns are the radial, along-track, and cross-track
        unit vectors expressed in the inertial frame.

    Raises:
        ValueError: if position and velocity are parallel or either is zero, in
            which case the orbital frame is undefined.
    """
    r = np.asarray(position_km, dtype=np.float64)
    v = np.asarray(velocity_kms, dtype=np.float64)

    r_norm = np.linalg.norm(r)
    if r_norm <= 0.0:
        raise ValueError("Position vector is zero; the RTN frame is undefined.")
    u_r = r / r_norm

    h = np.cross(r, v)
    h_norm = np.linalg.norm(h)
    if h_norm <= 0.0:
        raise ValueError(
            "Position and velocity are parallel; the orbital plane is undefined."
        )
    u_n = h / h_norm

    u_t = np.cross(u_n, u_r)
    u_t /= np.linalg.norm(u_t)

    return np.column_stack([u_r, u_t, u_n])


def covariance_rtn_to_inertial(
    covariance_rtn_km2: np.ndarray,
    position_km: np.ndarray,
    velocity_kms: np.ndarray,
) -> np.ndarray:
    """
    Rotate an RTN covariance into the inertial frame.

    Covariance transforms as ``C_inertial = M C_rtn M^T`` for rotation M, since
    a covariance is a quadratic form rather than a vector.

    Args:
        covariance_rtn_km2: 3x3 covariance in the RTN frame.
        position_km: Inertial position at the evaluation time.
        velocity_kms: Inertial velocity at the evaluation time.

    Returns:
        3x3 covariance in the inertial frame, km^2.
    """
    rotation = rtn_rotation_matrix(position_km, velocity_kms)
    return rotation @ np.asarray(covariance_rtn_km2, dtype=np.float64) @ rotation.T


def covariance_for_object(
    position_km: np.ndarray,
    velocity_kms: np.ndarray,
    tle_age_days: float,
    model: TLEUncertaintyModel | None = None,
) -> np.ndarray:
    """
    Inertial position covariance for one object at a given propagation age.

    This is the main entry point: give it a state vector and how stale the TLE
    is, and it returns the covariance Foster's method needs.

    Args:
        position_km: Inertial position at the evaluation time, shape (3,).
        velocity_kms: Inertial velocity at the evaluation time, shape (3,).
        tle_age_days: Days between TLE epoch and evaluation time.
        model: Uncertainty model to use. Defaults to `TLEUncertaintyModel()`.

    Returns:
        3x3 inertial position covariance, km^2.
    """
    model = model or TLEUncertaintyModel()
    cov_rtn = model.covariance_rtn_km2(tle_age_days)
    return covariance_rtn_to_inertial(cov_rtn, position_km, velocity_kms)


def covariance_sensitivity_band(
    position_km: np.ndarray,
    velocity_kms: np.ndarray,
    tle_age_days: float,
    model: TLEUncertaintyModel | None = None,
    factors: Tuple[float, ...] = (0.5, 1.0, 2.0),
) -> List[Dict[str, object]]:
    """
    Produce optimistic / nominal / pessimistic covariances.

    Since the uncertainty model is an assumption, any single Pc derived from it
    is really a point on a range. Feeding each of these covariances through the
    Pc calculation gives an honest band to present instead of a single number
    with unearned authority.

    Args:
        factors: Multipliers applied to the standard deviations (not the
            covariance), so 2.0 means "twice as uncertain as nominal".

    Returns:
        One record per factor, each with the sigma multiplier, a label, and the
        corresponding inertial covariance.
    """
    model = model or TLEUncertaintyModel()
    labels = {0.5: "optimistic", 1.0: "nominal", 2.0: "pessimistic"}

    band: List[Dict[str, object]] = []
    for factor in factors:
        # Scale sigmas by `factor`, hence the covariance by factor squared.
        cov_rtn = model.covariance_rtn_km2(tle_age_days) * (factor**2)
        band.append(
            {
                "sigma_multiplier": float(factor),
                "label": labels.get(factor, f"{factor:g}x"),
                "covariance_inertial_km2": covariance_rtn_to_inertial(
                    cov_rtn, position_km, velocity_kms
                ),
            }
        )
    return band


# Representative hard-body radii, in metres. Pc scales with the square of the
# combined radius, so a wrong guess here moves the answer materially -- prefer a
# real value from the satellite catalog whenever one is available.
HARD_BODY_RADIUS_M: Dict[str, float] = {
    "cubesat_1u": 0.15,
    "smallsat": 1.0,
    "typical_leo_satellite": 5.0,
    "large_satellite": 10.0,
    "rocket_body": 8.0,
    "debris_fragment": 0.5,
    "unknown": 5.0,
}


def hard_body_radius_for(object_class: str) -> float:
    """
    Look up a representative radius, falling back to a conservative default.

    Args:
        object_class: One of the keys of `HARD_BODY_RADIUS_M`.

    Returns:
        Radius in metres; the "unknown" default if the class is unrecognised.
    """
    key = (object_class or "unknown").strip().lower()
    if key not in HARD_BODY_RADIUS_M:
        logger.debug("Unknown object class %r; using default hard-body radius.", key)
    return HARD_BODY_RADIUS_M.get(key, HARD_BODY_RADIUS_M["unknown"])


# ---------------------------------------------------------------------------
# Learned models
# ---------------------------------------------------------------------------

REGIME_PASSIVE = "passive"
"""Objects that do not maneuver between element-set updates: debris, rocket
bodies, and quiet satellites. Trained on OneWeb and Planet."""

REGIME_MANEUVERING = "maneuvering"
"""Satellites that maneuver every few days, whose element sets go stale fast.
Trained on Starlink."""

LEARNED_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "models", "tle_uncertainty.json"
)

# Constellations measured to maneuver often enough that their element sets
# degrade far faster than a passive object's. Kept as an explicit list because
# it is a measured finding, not a guess about which satellites have thrusters.
_FREQUENT_MANEUVER_TOKENS = ("STARLINK",)


def uncertainty_regime(object_name: str = "", object_class: str = "") -> str:
    """
    Choose which learned error-growth regime applies to an object.

    The deciding factor is how often an object maneuvers between element-set
    updates, not whether it can: a maneuver the element set has not caught up
    with is what makes along-track error explode. The measured Starlink data
    grows about ten times faster than the passive constellations. Everything
    not known to maneuver frequently -- including debris, rocket bodies, and
    stations that reboost only occasionally -- uses the passive regime.
    """
    upper = (object_name or "").upper()
    if any(token in upper for token in _FREQUENT_MANEUVER_TOKENS):
        return REGIME_MANEUVERING
    return REGIME_PASSIVE


def learned_models(path: Optional[str] = None) -> Optional[Dict[str, TLEUncertaintyModel]]:
    """
    Load the fitted uncertainty models, one per regime.

    Returns None if no trained model file exists, so callers can fall back to
    the assumed defaults and say so.
    """
    path = os.path.abspath(path or LEARNED_MODEL_PATH)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            document = json.load(handle)
        models = {}
        for regime, spec in document["regimes"].items():
            coefficients = spec["coefficients"]
            models[regime] = TLEUncertaintyModel.from_coefficients(
                epoch_km=tuple(coefficients["epoch_km"]),
                growth_km_per_day=tuple(coefficients["growth_km_per_day"]),
                curvature_km_per_day2=tuple(coefficients["curvature_km_per_day2"]),
                source=spec["source"],
                trained_age_range_days=tuple(spec["trained_age_range_days"]),
            )
        return models
    except (OSError, KeyError, ValueError, TypeError) as exc:
        logger.error("Could not load learned uncertainty models from %s: %s", path, exc)
        return None
