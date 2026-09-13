"""
Validation tests for the collision probability computation.

These check physical behaviour rather than structure. A test that only asserts
"a number came back" would have passed against the previous implementation,
which returned classifier confidence on synthetic data.
"""

import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from app.core.collision_probability import (  # noqa: E402
    chan_pc,
    collision_probability,
    encounter_plane_basis,
    pc_dilution_curve,
    project_to_encounter_plane,
)

# A crossing conjunction at 12.4 km/s, the scenario used throughout the deck.
R_REL = np.array([0.42, 0.0, 0.0])
V_REL = np.array([0.0, 12.4, 0.0])
HBR_M = 5.0  # each object, so 10 m combined


def isotropic(sigma_km):
    return np.eye(3) * sigma_km**2


class TestEncounterPlane:
    def test_basis_is_orthonormal_and_perpendicular_to_relative_velocity(self):
        basis = encounter_plane_basis(R_REL, V_REL)
        assert basis.shape == (3, 2)
        # Columns are unit length and mutually orthogonal.
        assert np.allclose(basis.T @ basis, np.eye(2), atol=1e-12)
        # Both columns lie in the plane perpendicular to the relative velocity.
        v_hat = V_REL / np.linalg.norm(V_REL)
        assert np.allclose(basis.T @ v_hat, np.zeros(2), atol=1e-12)

    def test_projected_miss_preserves_perpendicular_separation(self):
        # With the miss vector already perpendicular to the relative velocity,
        # projection must not shorten it.
        geometry = project_to_encounter_plane(
            R_REL, V_REL, isotropic(0.3), isotropic(0.3)
        )
        assert np.linalg.norm(geometry.projected_miss_km) == pytest.approx(0.42, rel=1e-9)

    def test_velocity_component_of_miss_is_discarded(self):
        # A separation purely along the relative velocity is not a miss distance
        # in the encounter plane: the objects pass through the same point at
        # different times.
        r_along = np.array([0.0, 5.0, 0.0])  # parallel to V_REL
        geometry = project_to_encounter_plane(
            r_along, V_REL, isotropic(0.3), isotropic(0.3)
        )
        assert np.linalg.norm(geometry.projected_miss_km) == pytest.approx(0.0, abs=1e-9)

    def test_zero_relative_velocity_is_rejected(self):
        with pytest.raises(ValueError, match="encounter plane is undefined"):
            encounter_plane_basis(R_REL, np.zeros(3))

    def test_covariances_add(self):
        # Independent uncertainties combine additively, so two objects each with
        # sigma s must match one with sqrt(2)*s against a certain object.
        both = project_to_encounter_plane(
            R_REL, V_REL, isotropic(0.3), isotropic(0.3)
        )
        combined = project_to_encounter_plane(
            R_REL, V_REL, isotropic(0.3 * math.sqrt(2)), np.zeros((3, 3))
        )
        assert np.allclose(
            both.projected_covariance_km2, combined.projected_covariance_km2, atol=1e-12
        )


class TestFosterAgainstChan:
    """Two independent estimators must agree, or neither can be trusted."""

    @pytest.mark.parametrize("sigma_km", [0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0])
    def test_quadrature_matches_analytic_series(self, sigma_km):
        result = collision_probability(
            R_REL, V_REL, isotropic(sigma_km), isotropic(sigma_km), HBR_M, HBR_M
        )
        series = result.diagnostics["chan_cross_check"]
        assert result.pc == pytest.approx(series, rel=1e-5)


class TestPhysicalBehaviour:
    def test_pc_falls_as_miss_distance_grows(self):
        probabilities = [
            collision_probability(
                np.array([d, 0.0, 0.0]), V_REL, isotropic(0.3), isotropic(0.3),
                HBR_M, HBR_M,
            ).pc
            for d in [0.1, 0.5, 1.0, 2.0, 5.0]
        ]
        assert probabilities == sorted(probabilities, reverse=True)

    def test_pc_grows_with_object_size(self):
        small = collision_probability(
            R_REL, V_REL, isotropic(0.3), isotropic(0.3), 0.5, 0.5
        ).pc
        large = collision_probability(
            R_REL, V_REL, isotropic(0.3), isotropic(0.3), 10.0, 10.0
        ).pc
        assert large > small
        # Pc scales with the square of the combined radius when the radius is
        # small compared with the uncertainty: 20x radius gives ~400x Pc.
        assert large / small == pytest.approx(400.0, rel=0.05)

    def test_probability_dilution_peak_matches_theory(self):
        # For an isotropic projected covariance and a hard-body radius small
        # compared with sigma, Pc is maximised at sigma = miss / sqrt(2).
        miss = 0.42
        best_sigma, best_pc = None, -1.0
        for sigma_projected in np.linspace(0.05, 0.60, 111):
            per_object = sigma_projected / math.sqrt(2)
            pc = collision_probability(
                np.array([miss, 0.0, 0.0]), V_REL,
                isotropic(per_object), isotropic(per_object), HBR_M, HBR_M,
                method="chan",
            ).pc
            if pc > best_pc:
                best_sigma, best_pc = sigma_projected, pc
        assert best_sigma == pytest.approx(miss / math.sqrt(2), rel=0.02)

    def test_pc_is_not_monotonic_in_uncertainty(self):
        # The dilution effect: more uncertainty does not mean more risk. This is
        # the behaviour a distance-based heuristic cannot reproduce.
        curve = pc_dilution_curve(
            R_REL, V_REL, isotropic(0.1), isotropic(0.1), HBR_M, HBR_M
        )
        values = [point["pc"] for point in curve]
        peak_index = values.index(max(values))
        assert 0 < peak_index < len(values) - 1, "peak should be interior, not at an edge"

    def test_small_radius_limit_matches_closed_form(self):
        # For R << sigma, Pc -> pi R^2 * N(0; miss, C).
        sigma_projected, miss, radius_km = 0.4, 0.42, 0.010
        per_object = sigma_projected / math.sqrt(2)
        pc = collision_probability(
            np.array([miss, 0.0, 0.0]), V_REL,
            isotropic(per_object), isotropic(per_object),
            radius_km * 1000.0 / 2, radius_km * 1000.0 / 2,
        ).pc
        expected = (
            math.pi * radius_km**2
            * (1.0 / (2.0 * math.pi * sigma_projected**2))
            * math.exp(-(miss**2) / (2.0 * sigma_projected**2))
        )
        assert pc == pytest.approx(expected, rel=1e-3)

    def test_pc_stays_a_probability(self):
        # Even in an absurd worst case the result must remain in [0, 1].
        pc = collision_probability(
            np.zeros(3), V_REL, isotropic(0.001), isotropic(0.001), 500.0, 500.0
        ).pc
        assert 0.0 <= pc <= 1.0

    def test_direct_hit_with_tight_covariance_is_near_certain(self):
        pc = collision_probability(
            np.zeros(3), V_REL, isotropic(0.0005), isotropic(0.0005), 50.0, 50.0
        ).pc
        assert pc > 0.5


class TestChanSeries:
    def test_series_converges_for_large_separation(self):
        pc = chan_pc(np.array([50.0, 0.0]), np.eye(2) * 0.09, 0.01)
        assert 0.0 <= pc < 1e-12

    def test_series_handles_zero_miss(self):
        pc = chan_pc(np.array([0.0, 0.0]), np.eye(2) * 0.09, 0.01)
        assert 0.0 < pc < 1.0
