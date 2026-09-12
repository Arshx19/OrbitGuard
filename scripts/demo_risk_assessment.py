"""
End-to-end demonstration of the ORBITGUARD AI risk layer.

Runs the full path a real assessment takes: a published TLE is parsed, SGP4
propagates it to a chosen time of closest approach, a conjunction is set up
against it, and the risk engine returns a collision probability, a priority
score, and a counterfactual explanation of both.

Run it with:

    .venv/Scripts/python.exe scripts/demo_risk_assessment.py

A note on the scenario: the primary object and its state vector are real -- a
published ISS element set propagated by SGP4. The secondary is *constructed*, by
placing an object at a chosen miss distance from the primary's true position with
a crossing velocity. Real catalogs rarely serve up a sub-kilometre conjunction on
demand, and a demo needs a reproducible one. Everything downstream of that
placement is genuine computation, and the construction is labelled wherever it
appears so nobody mistakes it for a detection.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import timedelta

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.core.data_ingestion import load_tle_from_string  # noqa: E402
from app.core.propagation import OrbitalPropagator  # noqa: E402
from app.core.risk_engine import ConjunctionInput, RiskEngine  # noqa: E402
from app.core.uncertainty import TLEUncertaintyModel  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

# A real, published element set for the ISS.
ISS_TLE = """1 25544U 98067A   24255.51782528  .00016717  00000+0  35226-3 0  9994
2 25544  51.6416 247.4627 0003682  33.9335 315.0876 15.50050725428536"""

RULE = "=" * 78


def build_scenario(miss_distance_km: float, lead_time_hours: float, tle_age_days: float):
    """
    Propagate the real primary and construct a secondary at a chosen miss.

    Returns:
        A ConjunctionInput ready for assessment.
    """
    tle = load_tle_from_string(ISS_TLE)
    if tle is None:
        raise RuntimeError("Failed to parse the ISS element set.")

    propagator = OrbitalPropagator()

    # Evaluate at a realistic propagation age rather than years past epoch.
    tca = tle.epoch + timedelta(days=tle_age_days)

    position = propagator.propagate_single_satellite(tle.satrec, tca)
    velocity = propagator.calculate_velocity(tle.satrec, tca)
    if position is None or velocity is None:
        raise RuntimeError("SGP4 propagation failed for the primary object.")

    # Place the secondary `miss_distance_km` away, offset perpendicular to the
    # primary's velocity so the separation is a genuine miss distance rather
    # than an along-track lag.
    v_hat = velocity / np.linalg.norm(velocity)
    offset_dir = np.cross(v_hat, position / np.linalg.norm(position))
    offset_dir /= np.linalg.norm(offset_dir)
    secondary_position = position + offset_dir * miss_distance_km

    # Give it a crossing velocity: same speed, rotated well away from the
    # primary's, producing the ~10 km/s relative speed typical of a crossing
    # conjunction in LEO.
    speed = float(np.linalg.norm(velocity))
    secondary_velocity = speed * (
        -0.55 * v_hat + 0.835 * offset_dir
    )

    return ConjunctionInput(
        primary_position_km=position,
        primary_velocity_kms=velocity,
        secondary_position_km=secondary_position,
        secondary_velocity_kms=secondary_velocity,
        time_to_tca_hours=lead_time_hours,
        primary_tle_age_days=tle_age_days,
        secondary_tle_age_days=tle_age_days,
        primary_object_class="large_satellite",
        secondary_object_class="debris_fragment",
        primary_id=25544,
        secondary_id=90001,
        tca=tca,
    )


def print_assessment(assessment) -> None:
    """Render one assessment the way the operator dashboard would."""
    print(RULE)
    print(
        f"CONJUNCTION  {assessment.primary_id} vs {assessment.secondary_id}"
        f"        [{assessment.severity}]"
    )
    print(RULE)
    print(f"  Risk score              {assessment.risk_score:.1f} / 100")
    print(f"  Collision probability   {assessment.pc:.3e}")
    print(f"  Miss distance           {assessment.miss_distance_km:.3f} km")
    print(f"  Relative velocity       {assessment.relative_speed_kms:.2f} km/s")
    print(f"  Time to closest approach{assessment.time_to_tca_hours:>7.1f} h")
    print(f"  Combined hard-body radius {assessment.combined_hbr_m:.1f} m")

    uncertainty = assessment.uncertainty_summary
    print(
        f"  Ephemeris age           {uncertainty['primary_tle_age_days']:.2f} days "
        f"(along-track sigma {uncertainty['primary_sigma_along_track_km']:.2f} km)"
    )

    print("\n  WHY IS THIS EVENT DANGEROUS?")
    raising = [f for f in assessment.factors if f.direction == "raises"]
    reducing = [f for f in assessment.factors if f.direction == "reduces"]

    if not raising:
        print("    No risk-elevating factors identified.")
    for factor in raising:
        bar = "#" * int(round(factor.contribution_percent / 2.5))
        print(
            f"    {factor.display_name:<24} {bar:<40} "
            f"{factor.contribution_percent:5.1f}%"
        )
    for factor in raising:
        print(f"      - {factor.explanation}")

    if reducing:
        print("\n  CURRENTLY LOWERING THE PROBABILITY (uncertainty dilution)")
        for factor in reducing:
            print(
                f"    {factor.display_name:<24} "
                f"{factor.contribution_percent:+5.1f}%"
            )
            print(f"      - {factor.explanation}")

    print(f"\n  SUMMARY\n    {assessment.narrative}")
    print()


def main() -> None:
    engine = RiskEngine()

    print("\nORBITGUARD AI -- risk layer demonstration")
    print("Primary object and state vector are real (SGP4 on a published TLE).")
    print("The secondary is a constructed scenario; see the module docstring.\n")

    # --- the headline event ------------------------------------------------
    scenario = build_scenario(
        miss_distance_km=0.42, lead_time_hours=4.2, tle_age_days=0.5
    )
    print_assessment(engine.assess(scenario))

    # --- staleness sensitivity --------------------------------------------
    print(RULE)
    print("SENSITIVITY TO EPHEMERIS AGE  (identical geometry, 0.42 km miss)")
    print(RULE)
    print(f"  {'TLE age':>9} {'sigma_AT':>10} {'Pc':>12} {'severity':>10} {'score':>7}")
    for age in [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]:
        assessment = engine.assess(
            build_scenario(miss_distance_km=0.42, lead_time_hours=4.2, tle_age_days=age)
        )
        sigma = assessment.uncertainty_summary["primary_sigma_along_track_km"]
        print(
            f"  {age:7.2f} d {sigma:9.2f} km {assessment.pc:12.3e} "
            f"{assessment.severity:>10} {assessment.risk_score:7.1f}"
        )
    print(
        "\n  The same geometry changes severity band purely from how stale the\n"
        "  tracking data is. Probability depends on the overlap between the\n"
        "  uncertainty distribution and the target, not on distance alone --\n"
        "  which is precisely what a distance threshold cannot capture.\n"
    )

    # --- what a maneuver buys ---------------------------------------------
    print(RULE)
    print("MANEUVER BENEFIT  (0.30 m/s along-track, 4.2 h before TCA)")
    print(RULE)
    scenario = build_scenario(
        miss_distance_km=0.42, lead_time_hours=4.2, tle_age_days=0.5
    )
    # A 0.30 m/s along-track burn 4.2 h out yields ~13.6 km of displacement,
    # from the period change it induces (verified against vis-viva separately).
    v_hat = scenario.primary_velocity_kms / np.linalg.norm(
        scenario.primary_velocity_kms
    )
    after = scenario.relative_position_km() + v_hat * 13.6
    result = engine.pc_reduction(scenario, after)

    below_floor = result["pc_after_below_floor"]
    print(f"  Pc before maneuver      {result['pc_before']:.3e}")
    if below_floor:
        print(f"  Pc after maneuver       below {result['pc_after']:.0e} (reporting floor)")
        print(f"  Reduction factor        greater than {result['reduction_factor']:.0e}x")
    else:
        print(f"  Pc after maneuver       {result['pc_after']:.3e}")
        print(f"  Reduction factor        {result['reduction_factor']:.1f}x")

    # Tsiolkovsky, for a 500 kg satellite on hydrazine monopropellant.
    delta_v_ms, mass_kg, isp_s, g0 = 0.30, 500.0, 220.0, 9.80665
    propellant_g = mass_kg * (1.0 - np.exp(-delta_v_ms / (isp_s * g0))) * 1000.0
    print(f"  Propellant cost         {propellant_g:.1f} g")
    print(
        f"\n  Spending {propellant_g:.0f} g of propellant retires a "
        f"{result['pc_before']:.1e} probability of losing the spacecraft.\n"
    )


if __name__ == "__main__":
    main()
