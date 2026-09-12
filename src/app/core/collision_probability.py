"""
Collision probability (Pc) computation for ORBITGUARD AI.

This module implements Foster's 2D method, the standard technique used in
operational conjunction assessment (NASA CARA, ESA SSA) to answer the question
a miss distance alone cannot: *how likely is this close approach to actually be
a collision?*

The method rests on a few assumptions that hold well for typical LEO
conjunctions:

  1. The encounter is "short" -- relative motion through the conjunction is
     effectively rectilinear, because the relative velocity (kilometres per
     second) is enormous compared to the duration over which the objects are
     close.
  2. Position uncertainty is Gaussian, and the two objects' uncertainties are
     independent, so their covariances add.
  3. Velocity uncertainty is negligible over the encounter.

Under those assumptions the 3D problem collapses to a 2D one. We project both
objects onto the *encounter plane* -- the plane perpendicular to the relative
velocity vector at closest approach -- and the collision probability becomes the
integral of a 2D Gaussian over a disk whose radius is the combined hard-body
radius of the two objects.

A note on interpretation, because this trips people up: Pc is **not** monotonic
in uncertainty. Holding miss distance fixed and inflating the covariance, Pc
rises to a maximum and then *falls* again. This is the well-known "probability
dilution" effect -- when you know very little about where an object is, the
probability mass smears out and comparatively little of it lands on the target.
It is a genuine property of the physics, not a bug, and `pc_dilution_curve()`
exists to let the UI show it.

References
----------
Foster, J.L. and Estes, H.S. (1992), "A Parametric Analysis of Orbital Debris
Collision Probability and Maneuver Rate for Space Vehicles", NASA/JSC-25898.
Chan, F.K. (2008), "Spacecraft Collision Probability", Aerospace Press.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import integrate

logger = logging.getLogger(__name__)

# Numerical floor for covariance eigenvalues (km^2). Guards against a singular
# projected covariance when an input covariance is degenerate or zero.
_MIN_VARIANCE_KM2 = 1e-12


@dataclass
class EncounterGeometry:
    """The conjunction reduced to its encounter-plane representation."""

    miss_distance_km: float
    """Full 3D separation at TCA."""

    relative_speed_kms: float
    """Magnitude of the relative velocity at TCA."""

    projected_miss_km: np.ndarray
    """2D miss vector in the encounter plane, shape (2,)."""

    projected_covariance_km2: np.ndarray
    """Combined 2x2 position covariance projected into the encounter plane."""

    basis: np.ndarray
    """3x2 matrix whose columns span the encounter plane in the inertial frame."""

    def sigmas_km(self) -> Tuple[float, float]:
        """Principal-axis standard deviations of the projected covariance."""
        eigenvalues = np.linalg.eigvalsh(self.projected_covariance_km2)
        eigenvalues = np.maximum(eigenvalues, _MIN_VARIANCE_KM2)
        return float(np.sqrt(eigenvalues[0])), float(np.sqrt(eigenvalues[1]))

    def to_dict(self) -> Dict[str, object]:
        sigma_minor, sigma_major = self.sigmas_km()
        return {
            "miss_distance_km": self.miss_distance_km,
            "relative_speed_kms": self.relative_speed_kms,
            "projected_miss_km": self.projected_miss_km.tolist(),
            "sigma_minor_km": sigma_minor,
            "sigma_major_km": sigma_major,
        }


@dataclass
class PcResult:
    """Collision probability together with the geometry that produced it."""

    pc: float
    """Probability of collision, dimensionless, in [0, 1]."""

    method: str
    """Which estimator produced `pc`."""

    combined_hbr_m: float
    """Combined hard-body radius used for the integration."""

    geometry: EncounterGeometry

    diagnostics: Dict[str, object] = field(default_factory=dict)

    @property
    def pc_log10(self) -> float:
        """log10(Pc), floored at -12 so it stays finite for display and scoring."""
        return math.log10(self.pc) if self.pc > 1e-12 else -12.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "collision_probability": self.pc,
            "collision_probability_log10": self.pc_log10,
            "method": self.method,
            "combined_hbr_m": self.combined_hbr_m,
            "geometry": self.geometry.to_dict(),
            "diagnostics": self.diagnostics,
        }


def encounter_plane_basis(
    relative_position_km: np.ndarray,
    relative_velocity_kms: np.ndarray,
) -> np.ndarray:
    """
    Build an orthonormal basis for the encounter plane.

    The encounter plane is perpendicular to the relative velocity. We choose the
    first basis vector along the component of the relative position that lies in
    that plane, which makes the projected miss vector conveniently equal to
    ``(|r_perp|, 0)``. The second completes a right-handed set.

    Args:
        relative_position_km: r1 - r2 at TCA, shape (3,), kilometres.
        relative_velocity_kms: v1 - v2 at TCA, shape (3,), km/s.

    Returns:
        A 3x2 matrix whose columns are the in-plane basis vectors.

    Raises:
        ValueError: if the relative velocity is zero, which would leave the
            encounter plane undefined.
    """
    v_rel = np.asarray(relative_velocity_kms, dtype=np.float64)
    r_rel = np.asarray(relative_position_km, dtype=np.float64)

    v_norm = np.linalg.norm(v_rel)
    if v_norm <= 0.0:
        raise ValueError(
            "Relative velocity is zero; the encounter plane is undefined. "
            "Foster's method assumes a short, rectilinear encounter."
        )
    v_hat = v_rel / v_norm

    # Component of the miss vector lying in the encounter plane.
    r_perp = r_rel - np.dot(r_rel, v_hat) * v_hat
    r_perp_norm = np.linalg.norm(r_perp)

    if r_perp_norm < 1e-9:
        # Degenerate: the objects are nearly head-on along the relative velocity.
        # Any in-plane basis is valid, so build one from an arbitrary vector.
        fallback = np.array([1.0, 0.0, 0.0])
        if abs(np.dot(fallback, v_hat)) > 0.9:
            fallback = np.array([0.0, 1.0, 0.0])
        x_hat = fallback - np.dot(fallback, v_hat) * v_hat
        x_hat /= np.linalg.norm(x_hat)
    else:
        x_hat = r_perp / r_perp_norm

    z_hat = np.cross(v_hat, x_hat)
    z_hat /= np.linalg.norm(z_hat)

    return np.column_stack([x_hat, z_hat])


def project_to_encounter_plane(
    relative_position_km: np.ndarray,
    relative_velocity_kms: np.ndarray,
    covariance_1_km2: np.ndarray,
    covariance_2_km2: np.ndarray,
) -> EncounterGeometry:
    """
    Reduce a 3D conjunction to its 2D encounter-plane representation.

    The two objects' covariances are assumed independent, so the combined
    uncertainty is their sum. Both must already be expressed in the same
    inertial frame as the position and velocity vectors.

    Args:
        relative_position_km: r1 - r2 at TCA, shape (3,).
        relative_velocity_kms: v1 - v2 at TCA, shape (3,).
        covariance_1_km2: 3x3 position covariance of object 1, km^2.
        covariance_2_km2: 3x3 position covariance of object 2, km^2.

    Returns:
        An EncounterGeometry describing the projected conjunction.
    """
    r_rel = np.asarray(relative_position_km, dtype=np.float64)
    v_rel = np.asarray(relative_velocity_kms, dtype=np.float64)

    basis = encounter_plane_basis(r_rel, v_rel)

    combined_cov = np.asarray(covariance_1_km2, dtype=np.float64) + np.asarray(
        covariance_2_km2, dtype=np.float64
    )

    # Project: C_2D = B^T C B
    projected_cov = basis.T @ combined_cov @ basis

    # Symmetrise to kill accumulated floating-point asymmetry, then regularise
    # so the inverse is always well defined.
    projected_cov = 0.5 * (projected_cov + projected_cov.T)
    projected_cov += np.eye(2) * _MIN_VARIANCE_KM2

    projected_miss = basis.T @ r_rel

    return EncounterGeometry(
        miss_distance_km=float(np.linalg.norm(r_rel)),
        relative_speed_kms=float(np.linalg.norm(v_rel)),
        projected_miss_km=projected_miss,
        projected_covariance_km2=projected_cov,
        basis=basis,
    )


def _integrate_gaussian_over_disk(
    mean_km: np.ndarray,
    covariance_km2: np.ndarray,
    radius_km: float,
) -> Tuple[float, float]:
    """
    Integrate a 2D Gaussian over a disk of given radius centred at the origin.

    This is the heart of Foster's method. We integrate in polar coordinates,
    which keeps the domain a simple rectangle and lets the adaptive quadrature
    do its job.

    Returns:
        Tuple of (probability, estimated absolute error).
    """
    det = float(np.linalg.det(covariance_km2))
    if det <= 0.0:
        logger.warning("Projected covariance is singular (det=%g); Pc set to 0.", det)
        return 0.0, 0.0

    inv_cov = np.linalg.inv(covariance_km2)
    norm_const = 1.0 / (2.0 * math.pi * math.sqrt(det))
    mx, my = float(mean_km[0]), float(mean_km[1])

    def integrand(theta: float, rho: float) -> float:
        dx = rho * math.cos(theta) - mx
        dy = rho * math.sin(theta) - my
        exponent = -0.5 * (
            inv_cov[0, 0] * dx * dx
            + (inv_cov[0, 1] + inv_cov[1, 0]) * dx * dy
            + inv_cov[1, 1] * dy * dy
        )
        # rho is the Jacobian of the polar transform.
        return norm_const * math.exp(exponent) * rho

    value, abserr = integrate.dblquad(
        integrand,
        0.0,
        radius_km,
        lambda _: 0.0,
        lambda _: 2.0 * math.pi,
        epsabs=1e-14,
        epsrel=1e-10,
    )
    return float(np.clip(value, 0.0, 1.0)), float(abserr)


def chan_pc(
    mean_km: np.ndarray,
    covariance_km2: np.ndarray,
    radius_km: float,
    max_terms: int = 60,
) -> float:
    """
    Chan's analytic series approximation to the same integral.

    Chan's method equivalently circularises the problem and evaluates a rapidly
    converging series. It is far cheaper than quadrature, which matters when
    screening thousands of pairs, and it serves as an independent check on the
    numerical result -- if the two disagree, something is wrong with the inputs.

    Args:
        mean_km: Projected miss vector, shape (2,).
        covariance_km2: 2x2 projected covariance.
        radius_km: Combined hard-body radius.
        max_terms: Series truncation point.

    Returns:
        Approximate collision probability.
    """
    # Rotate into the principal axes of the covariance so it becomes diagonal.
    eigenvalues, eigenvectors = np.linalg.eigh(covariance_km2)
    eigenvalues = np.maximum(eigenvalues, _MIN_VARIANCE_KM2)
    sigma_x, sigma_y = np.sqrt(eigenvalues)

    mean_rotated = eigenvectors.T @ np.asarray(mean_km, dtype=np.float64)
    x_m, y_m = float(mean_rotated[0]), float(mean_rotated[1])

    u = (radius_km * radius_km) / (sigma_x * sigma_y)
    v = (x_m / sigma_x) ** 2 + (y_m / sigma_y) ** 2

    # Pc = e^{-v/2} * sum_m [ (v/2)^m / m! ] * [ 1 - e^{-u/2} * sum_{k<=m} (u/2)^k / k! ]
    total = 0.0
    outer_term = 1.0  # (v/2)^m / m!, updated incrementally
    inner_term = 1.0  # (u/2)^k / k!
    inner_sum = 1.0  # running sum_{k<=m}

    half_u, half_v = 0.5 * u, 0.5 * v
    exp_neg_half_u = math.exp(-half_u)

    for m in range(max_terms + 1):
        if m > 0:
            outer_term *= half_v / m
            inner_term *= half_u / m
            inner_sum += inner_term
        total += outer_term * (1.0 - exp_neg_half_u * inner_sum)
        # The outer factor decays like a Poisson pmf; stop once it cannot matter.
        if m > 5 and outer_term < 1e-18:
            break

    pc = math.exp(-half_v) * total
    return float(np.clip(pc, 0.0, 1.0))


def collision_probability(
    relative_position_km: np.ndarray,
    relative_velocity_kms: np.ndarray,
    covariance_1_km2: np.ndarray,
    covariance_2_km2: np.ndarray,
    hard_body_radius_1_m: float = 5.0,
    hard_body_radius_2_m: float = 5.0,
    method: str = "foster",
) -> PcResult:
    """
    Compute the probability of collision for a conjunction.

    Args:
        relative_position_km: r1 - r2 at TCA, shape (3,).
        relative_velocity_kms: v1 - v2 at TCA, shape (3,).
        covariance_1_km2: 3x3 inertial position covariance of object 1.
        covariance_2_km2: 3x3 inertial position covariance of object 2.
        hard_body_radius_1_m: Effective radius of object 1, metres.
        hard_body_radius_2_m: Effective radius of object 2, metres.
        method: "foster" for adaptive quadrature (accurate, slower) or "chan"
            for the analytic series (fast, used when screening in bulk).

    Returns:
        A PcResult carrying the probability and the encounter geometry.
    """
    geometry = project_to_encounter_plane(
        relative_position_km,
        relative_velocity_kms,
        covariance_1_km2,
        covariance_2_km2,
    )

    combined_hbr_m = hard_body_radius_1_m + hard_body_radius_2_m
    combined_hbr_km = combined_hbr_m / 1000.0

    diagnostics: Dict[str, object] = {}

    if method == "chan":
        pc = chan_pc(
            geometry.projected_miss_km,
            geometry.projected_covariance_km2,
            combined_hbr_km,
        )
    elif method == "foster":
        pc, abserr = _integrate_gaussian_over_disk(
            geometry.projected_miss_km,
            geometry.projected_covariance_km2,
            combined_hbr_km,
        )
        diagnostics["quadrature_abserr"] = abserr
        # Cross-check against the independent series solution. A large relative
        # disagreement means one of them is being pushed outside its comfort
        # zone, which is worth surfacing rather than hiding.
        approx = chan_pc(
            geometry.projected_miss_km,
            geometry.projected_covariance_km2,
            combined_hbr_km,
        )
        diagnostics["chan_cross_check"] = approx
        if pc > 1e-12 and approx > 1e-12:
            rel_diff = abs(pc - approx) / max(pc, approx)
            diagnostics["cross_check_relative_difference"] = rel_diff
            if rel_diff > 0.05:
                logger.warning(
                    "Foster quadrature (%.3e) and Chan series (%.3e) disagree by "
                    "%.1f%%; treat this Pc with caution.",
                    pc, approx, 100.0 * rel_diff,
                )
    else:
        raise ValueError(f"Unknown method {method!r}; expected 'foster' or 'chan'.")

    return PcResult(
        pc=pc,
        method=method,
        combined_hbr_m=combined_hbr_m,
        geometry=geometry,
        diagnostics=diagnostics,
    )


def pc_dilution_curve(
    relative_position_km: np.ndarray,
    relative_velocity_kms: np.ndarray,
    covariance_1_km2: np.ndarray,
    covariance_2_km2: np.ndarray,
    hard_body_radius_1_m: float = 5.0,
    hard_body_radius_2_m: float = 5.0,
    scale_factors: Optional[np.ndarray] = None,
) -> List[Dict[str, float]]:
    """
    Trace how Pc varies as the covariance is scaled up and down.

    This produces the probability-dilution curve: Pc peaks at an intermediate
    level of uncertainty and falls away on both sides. It is worth plotting,
    because it shows an operator *why* a tighter tracking solution can either
    raise or lower the reported risk, and it is something no distance-based
    heuristic can reproduce.

    Args:
        scale_factors: Multipliers applied to both **covariance matrices**.
            Because covariance goes as sigma squared, a scale factor of `s`
            stretches the standard deviations by `sqrt(s)`. Defaults to a
            log-spaced sweep from 0.1x to 10x in covariance.

    Returns:
        A list of records ordered by scale, each carrying the scale factor, the
        resulting combined in-plane standard deviations, and the probability.
        The sigmas are reported explicitly so callers never have to re-derive
        them from the scale factor.
    """
    if scale_factors is None:
        scale_factors = np.logspace(-1.0, 1.0, 25)

    curve: List[Dict[str, float]] = []
    for scale in scale_factors:
        result = collision_probability(
            relative_position_km,
            relative_velocity_kms,
            np.asarray(covariance_1_km2) * scale,
            np.asarray(covariance_2_km2) * scale,
            hard_body_radius_1_m,
            hard_body_radius_2_m,
            method="chan",  # fast; the curve only needs shape, not 10 digits
        )
        sigma_minor, sigma_major = result.geometry.sigmas_km()
        curve.append(
            {
                "covariance_scale": float(scale),
                "sigma_minor_km": sigma_minor,
                "sigma_major_km": sigma_major,
                "pc": result.pc,
            }
        )

    return curve
