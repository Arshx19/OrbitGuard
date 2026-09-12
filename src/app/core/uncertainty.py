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
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TLEUncertaintyModel:
    """
    Parameterised RTN position-uncertainty growth for a TLE-derived ephemeris.

    Standard deviations grow linearly with propagation age:

        sigma(age) = sigma_at_epoch + growth_rate * age_days

    Linear growth is a deliberate simplification. Along-track error from a
    semi-major-axis bias is closer to linear-in-time over the day or two that
    matters for conjunction screening, and pretending to more sophistication
    than the input data supports would be false precision.
    """

    sigma_radial_epoch_km: float = 0.10
    sigma_along_track_epoch_km: float = 0.30
    sigma_cross_track_epoch_km: float = 0.10

    growth_radial_km_per_day: float = 0.20
    growth_along_track_km_per_day: float = 1.50
    growth_cross_track_km_per_day: float = 0.20

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
            self.sigma_radial_epoch_km + self.growth_radial_km_per_day * age,
            self.sigma_along_track_epoch_km + self.growth_along_track_km_per_day * age,
            self.sigma_cross_track_epoch_km + self.growth_cross_track_km_per_day * age,
        )

    def covariance_rtn_km2(self, age_days: float) -> np.ndarray:
        """Diagonal 3x3 covariance in the RTN frame, km^2."""
        sigma_r, sigma_t, sigma_n = self.sigmas_rtn_km(age_days)
        return np.diag([sigma_r**2, sigma_t**2, sigma_n**2])

    def describe(self, age_days: float) -> Dict[str, float]:
        """Human-readable summary for display alongside a Pc figure."""
        sigma_r, sigma_t, sigma_n = self.sigmas_rtn_km(age_days)
        return {
            "tle_age_days": abs(float(age_days)),
            "sigma_radial_km": sigma_r,
            "sigma_along_track_km": sigma_t,
            "sigma_cross_track_km": sigma_n,
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
