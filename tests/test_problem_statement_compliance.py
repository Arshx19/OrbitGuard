"""
================================================================================
ORBITGUARD AI - PROBLEM STATEMENT COMPLIANCE & VERIFICATION SUITE
================================================================================
This test script validates that the codebase satisfies all core and bonus
requirements specified in the problem statement:

1. [CORE] Ingest publicly available TLE data for a defined set of tracked objects.
2. [CORE] Established propagation model (SGP4) to project future positions.
3. [CORE] Risk-scoring layer on top of propagated trajectories flagging close approaches.
4. [CORE] Concrete recommended avoidance maneuver (delta-v magnitude/direction/timing).
5. [CORE] Before/after trajectory comparison (predicted intersection vs. corrected).
6. [BONUS] Rank multiple simultaneous conjunction events by urgency/severity.
7. [BONUS] Estimate fuel-cost tradeoff of maneuver against collision probability.

Every check runs the real pipeline on the committed CelesTrak catalog: nothing
here asserts on values typed into the test itself. Each requirement prints the
evidence it verified, so `python tests/test_problem_statement_compliance.py`
doubles as a demonstration report.
================================================================================
"""

import sys
import os
import math
from datetime import timedelta
import numpy as np

# Ensure UTF-8 output on Windows consoles safely
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
os.environ.setdefault("ORBITGUARD_ALLOW_NETWORK", "0")

from app.core.data_ingestion import load_tle_from_string
from app.core.propagation import OrbitalPropagator
from app.core.risk_engine import PC_THRESHOLD_CRITICAL, format_pc
from app.core.tle_source import CelesTrakClient, tle_epoch_utc
from app.services.maneuvers import PC_SAFE_TARGET, propellant_kg
from app.services.tracks import ManeuveredTrack, clohessy_wiltshire
from app.services.world import World

ISS_TLE = """1 25544U 98067A   26255.48371528  .00014298  00000+0  25372-3 0  9993
2 25544  51.6418 205.7891 0005721 110.2345 250.0123 15.49821456500124"""

_WORLD = None


def _world():
    """Build the screened world once and share it across requirements."""
    global _WORLD
    if _WORLD is None:
        _WORLD = World().build()
    return _WORLD


def test_core_requirement_1_tle_ingestion():
    """Requirement 1: Public TLE Ingestion from CelesTrak data."""
    print("\n" + "=" * 65)
    print("▶ [REQUIREMENT 1] Public TLE Data Ingestion (CelesTrak)")
    print("=" * 65)

    # 1. Parse an official ISS element set.
    parsed_iss = load_tle_from_string(ISS_TLE)
    assert parsed_iss is not None, "Failed to parse standard ISS TLE string"
    assert parsed_iss.satellite_number == 25544, "NORAD Catalog ID mismatch"
    assert parsed_iss.satrec is not None, "SGP4 Satrec record not generated"
    assert abs(parsed_iss.inclination - 51.6418) < 1e-4, "Inclination mismatch"

    # The epoch must be *correct*, not merely present: day 255.48 of 2026 is
    # 12 September, 11:36 UTC.
    epoch = tle_epoch_utc(parsed_iss)
    assert (epoch.year, epoch.month, epoch.day, epoch.hour) == (2026, 9, 12, 11), f"Wrong epoch {epoch}"

    print(f"  ✓ Ingested TLE: NORAD ID {parsed_iss.satellite_number}")
    print(f"    - Inclination: {parsed_iss.inclination:.4f}° | Mean Motion: {parsed_iss.mean_motion:.4f} rev/day")
    print(f"    - Epoch: {epoch.isoformat()} (verified against day-of-year 255.48)")

    # 2. Load the CelesTrak catalog snapshot the system screens.
    client = CelesTrakClient()
    objects = client.fetch_groups(["stations", "iridium-33-debris", "cosmos-1408-debris"], allow_network=False)
    assert len(objects) > 100, f"Expected a real catalog, loaded {len(objects)} objects"
    assert all(o.satrec is not None for o in objects), "Every catalog object needs an SGP4 record"
    names = {o.object_name for o in objects}
    assert any("ISS" in n for n in names), "Object names from the three-line format were not captured"
    print(f"  ✓ Ingested {len(objects)} objects from the CelesTrak catalog snapshot, with names")
    print("  ★ RESULT: REQUIREMENT 1 FULLY COMPLIANT\n")
    return True


def test_core_requirement_2_sgp4_propagation():
    """Requirement 2: SGP4 Orbital Trajectory Propagation."""
    print("=" * 65)
    print("▶ [REQUIREMENT 2] SGP4 Trajectory Propagation Model")
    print("=" * 65)

    tle_data = load_tle_from_string(ISS_TLE)
    propagator = OrbitalPropagator()

    start = tle_epoch_utc(tle_data).replace(tzinfo=None)
    horizon = start + timedelta(hours=6)
    times, positions = propagator.propagate_multiple_times(
        tle_data.satrec, start_time=start, end_time=horizon, time_step=timedelta(minutes=30)
    )
    assert len(positions) >= 12, "Propagation did not generate sufficient time steps"
    for pos in positions:
        r = np.linalg.norm(pos)
        assert 6371.0 < r < 8000.0, f"Unphysical orbit radius {r:.1f} km"

    velocity = propagator.calculate_velocity(tle_data.satrec, start)
    speed = float(np.linalg.norm(velocity))
    assert 7.5 < speed < 7.8, f"ISS orbital speed should be ~7.66 km/s, got {speed:.3f}"

    print(f"  ✓ SGP4 propagated {len(positions)} states over 6 h")
    print(f"    - |r| {np.linalg.norm(positions[0]):.1f} km -> {np.linalg.norm(positions[-1]):.1f} km")
    print(f"    - Orbital speed at epoch: {speed:.3f} km/s")
    print("  ★ RESULT: REQUIREMENT 2 FULLY COMPLIANT\n")
    return True


def test_core_requirement_3_conjunction_and_risk_scoring():
    """Requirement 3: Close-approach detection above a threshold, and risk scoring."""
    print("=" * 65)
    print("▶ [REQUIREMENT 3] Conjunction Screening & Risk-Scoring Layer")
    print("=" * 65)

    world = _world()
    report_km = world.config["report_km"]
    screened = [e for e in world.events.values() if not e.simulated]
    assert screened, "Screening the real catalog found no close approaches"
    assert all(e.approach.miss_distance_km <= report_km for e in screened), "Event reported above the threshold"

    # Refinement: the reported miss is the true minimum, not a coarse sample.
    refined_better = sum(e.approach.coarse_distance_km > e.approach.miss_distance_km for e in screened)
    assert refined_better > 0, "TCA refinement never improved on the sampled minimum"

    for event in screened + [world.events["CONJ-001"]]:
        a = event.assessment
        assert 0.0 <= a.pc <= 1.0 and 0.0 <= a.risk_score <= 100.0
        assert a.severity in ("GREEN", "AMBER", "HIGH", "CRITICAL")

    sim = world.events["CONJ-001"]
    assert sim.simulated and sim.assessment.pc >= PC_THRESHOLD_CRITICAL, "Demo event should be CRITICAL"

    # Explainability: each factor is a real recomputation of the probability.
    top = max(sim.assessment.factors, key=lambda f: f.contribution_percent)
    assert top.counterfactual_pc < sim.assessment.pc, "Counterfactual should lower the probability"

    closest = min(screened, key=lambda e: e.approach.miss_distance_km)
    print(f"  ✓ Screened {len(world.tracks)} objects: {len(screened)} real close approaches within {report_km:g} km")
    print(f"    - Closest: {closest.approach.primary.name} vs {closest.approach.secondary.name}, "
          f"{closest.approach.miss_distance_km:.3f} km (sampled {closest.approach.coarse_distance_km:.1f} km before refinement)")
    print(f"  ✓ Risk layer on the simulated ISS event: Pc {sim.assessment.pc:.2e}, "
          f"{sim.assessment.severity}, score {sim.assessment.risk_score:.1f}/100")
    print(f"    - Top driver: {top.display_name} ({top.contribution_percent:.0f}%) — {top.explanation}")
    print("  ★ RESULT: REQUIREMENT 3 FULLY COMPLIANT\n")
    return True


def test_core_requirement_4_avoidance_maneuver():
    """Requirement 4: Concrete recommended avoidance maneuver, computed and justified."""
    print("=" * 65)
    print("▶ [REQUIREMENT 4] Avoidance Maneuver Optimization & Justification")
    print("=" * 65)

    world = _world()
    event = world.events["CONJ-001"]
    plan = world.maneuvers(event)
    best_id = plan["recommended_candidate_id"]
    assert best_id is not None, "No safe maneuver found"
    best = next(c for c in plan["candidates"] if c["candidate_id"] == best_id)

    assert best["is_safe"], "Recommended maneuver is not safe"
    assert best["pc_after"] < PC_SAFE_TARGET < plan["pc_before"], "Maneuver does not bring Pc below target"
    assert best["delta_v_magnitude_ms"] > 0 and best["burn_lead_hours"] > 0, "Maneuver must have magnitude and timing"
    assert np.linalg.norm(best["delta_v_rtn_ms"]) == _approx(best["delta_v_magnitude_ms"]), "Direction vector inconsistent"

    # Justification: the along-track burn's secular drift is 3 * dv * t (CW).
    lead_s = best["burn_lead_hours"] * 3600.0
    radius = float(np.linalg.norm(event.approach.primary_position_km))
    n = math.sqrt(398600.4418 / radius ** 3)
    whole_orbits = 2 * math.pi / n * round(lead_s * n / (2 * math.pi))
    dr, _ = clohessy_wiltshire(np.array(best["delta_v_rtn_ms"]) / 1000.0, n, np.array([whole_orbits]))
    if abs(best["delta_v_rtn_ms"][1]) > 0:
        expected = 3.0 * abs(best["delta_v_rtn_ms"][1]) / 1000.0 * whole_orbits
        assert abs(abs(dr[0, 1]) - expected) < 1e-6 * max(1.0, expected), "CW secular drift mismatch"

    print(f"  ✓ Searched {plan['candidates_evaluated']} candidates across direction, magnitude and timing")
    print(f"  ✓ Recommended: {best['delta_v_magnitude_ms']:.2f} m/s {best['direction_name']}, "
          f"{best['burn_lead_hours']:.2f} h before TCA")
    print(f"    - Delta-v RTN: {[round(x, 3) for x in best['delta_v_rtn_ms']]} m/s")
    print(f"    - Pc {plan['pc_before']:.2e} -> {best['pc_after']:.2e}; miss -> {best['new_miss_distance_km']:.2f} km")
    print(f"    - Justification: an along-track burn changes the orbital period, so the spacecraft drifts "
          f"3·Δv·t along track (Clohessy-Wiltshire)")
    print("  ★ RESULT: REQUIREMENT 4 FULLY COMPLIANT\n")
    return True


def _approx(value, rel=1e-9):
    class _Approx:
        def __eq__(self, other):
            return abs(other - value) <= rel * max(1.0, abs(value))
    return _Approx()


def test_core_requirement_5_before_after_trajectory_visualization():
    """Requirement 5: Before / after trajectory separation, verified by re-propagation."""
    print("=" * 65)
    print("▶ [REQUIREMENT 5] Before / After Trajectory Separation Verification")
    print("=" * 65)

    world = _world()
    event = world.events["CONJ-001"]
    plan = world.maneuvers(event)
    result = world.validate(event, plan["recommended_candidate_id"])

    before = event.approach.miss_distance_km
    after = result["new_miss_distance_km"]
    assert after > before, "Maneuver did not increase separation"
    assert result["checks"]["catalog_rescreened"], "Post-maneuver trajectory was not re-screened"
    assert result["checks"]["new_conjunctions"] == 0, "Maneuver created a new conjunction"

    # Independently re-propagate the maneuvered track at the original TCA.
    a = event.approach
    lead_days = result["burn_lead_hours"] / 24.0
    moved = ManeuveredTrack(
        object_id="check", name=a.primary.name, object_type=a.primary.object_type,
        object_class=a.primary.object_class, base=a.primary,
        burn_jd=a.tca_jd, burn_fr=a.tca_fr - lead_days,
        delta_v_rtn_kms=np.array(result["delta_v_rtn_ms"]) / 1000.0,
    )
    r_moved, _ = moved.state(a.tca_jd, a.tca_fr)
    r_base, _ = a.primary.state(a.tca_jd, a.tca_fr)
    displacement = float(np.linalg.norm(r_moved - r_base))
    assert displacement > 0.5, f"Maneuvered trajectory barely moved ({displacement:.3f} km)"

    print(f"  ✓ Before: {a.primary.name} vs {a.secondary.name}, miss {before:.3f} km at TCA")
    print(f"  ✓ After:  miss {after:.2f} km; maneuvered spacecraft displaced {displacement:.2f} km at the original TCA")
    print(f"  ✓ Re-screened {result['checks']['catalog_objects_screened']} objects over "
          f"{result['checks']['rescreen_horizon_hours']:g} h: {result['checks']['new_conjunctions']} new conjunctions")
    print(f"    - Timeline before maneuver: " + ", ".join(f"{p['t']} {p['distance_km']:.1f} km" for p in event.timeline))
    print("  ★ RESULT: REQUIREMENT 5 FULLY COMPLIANT\n")
    return True


def test_bonus_1_multi_conjunction_ranking():
    """Bonus 1: Multi-conjunction ranking by urgency & severity."""
    print("=" * 65)
    print("▶ [BONUS 1] Multi-Conjunction Ranking by Urgency and Severity")
    print("=" * 65)

    world = _world()
    ranked = world.active_events()
    assert len(ranked) >= 2, "Need several simultaneous events to rank"
    screened = [e for e in ranked if not e.simulated]
    scores = [e.assessment.risk_score for e in screened]
    assert scores == sorted(scores, reverse=True), "Screened events are not ordered by risk score"

    # Urgency modulates the score without changing the probability.
    sim = world.events["CONJ-001"]
    hours = sim.assessment.time_to_tca_hours
    engine = world.engine
    pc = sim.assessment.pc
    soon = engine.retime(sim.assessment, 1.0).risk_score
    later = engine.retime(sim.assessment, 60.0).risk_score
    engine.retime(sim.assessment, hours)
    assert soon > later and sim.assessment.pc == pc, "Urgency should raise priority, not probability"

    print(f"  ✓ Ranked {len(ranked)} simultaneous events (simulated demo event pinned first):")
    for rank, e in enumerate(ranked[:5], 1):
        print(f"    #{rank} [{e.event_id}] {e.approach.primary.name} vs {e.approach.secondary.name} | "
              f"{e.assessment.severity} {e.assessment.risk_score:.1f}/100 | Pc {format_pc(e.assessment.pc)} | "
              f"TCA in {e.assessment.time_to_tca_hours:.1f} h")
    print(f"  ✓ Same event scored {soon:.1f} at 1 h out vs {later:.1f} at 60 h out, probability unchanged")
    print("  ★ RESULT: BONUS 1 FULLY COMPLIANT\n")
    return True


def test_bonus_2_fuel_cost_tradeoff():
    """Bonus 2: Fuel-Cost vs. Collision Probability Trade-off Analysis."""
    print("=" * 65)
    print("▶ [BONUS 2] Fuel-Cost Tradeoff vs. Avoided Collision Probability")
    print("=" * 65)

    world = _world()
    event = world.events["CONJ-001"]
    plan = world.maneuvers(event)
    candidates = sorted(plan["candidates"], key=lambda c: c["delta_v_magnitude_ms"])
    assert all(c["propellant_kg"] > 0 for c in candidates), "Every candidate needs a propellant cost"

    # Tsiolkovsky: more delta-v always costs more propellant.
    costs = [propellant_kg(dv, event.approach.primary.name) for dv in (0.05, 0.1, 0.3, 1.0)]
    assert costs == sorted(costs), "Propellant cost should grow with delta-v"

    print(f"  ✓ Trade-off for {event.approach.primary.name} (Pc before {plan['pc_before']:.2e}, "
          f"target {plan['safety_target']:.0e}):")
    print(f"    {'Δv (m/s)':<10} {'Direction':<28} {'Propellant (kg)':<17} {'Pc after':<11} {'Safe'}")
    for c in candidates:
        print(f"    {c['delta_v_magnitude_ms']:<10.2f} {c['direction_name']:<28} {c['propellant_kg']:<17.1f} "
              f"{c['pc_after']:<11.1e} {'yes' if c['is_safe'] else 'no'}")
    best = next(c for c in candidates if c["candidate_id"] == plan["recommended_candidate_id"])
    factor = plan["pc_before"] / max(best["pc_after"], 1e-12)
    print(f"  ✓ Recommended burn spends {best['propellant_kg']:.1f} kg to reduce Pc by a factor of {factor:.1e}")
    print("  ★ RESULT: BONUS 2 FULLY COMPLIANT\n")
    return True


def run_all_compliance_tests():
    """Execute complete compliance verification suite."""
    print("\n" + "#" * 65)
    print("   ORBITGUARD AI - PROBLEM STATEMENT COMPLIANCE VERIFICATION   ")
    print("#" * 65)

    suite = [
        ("Core Req 1: TLE Data Ingestion", test_core_requirement_1_tle_ingestion),
        ("Core Req 2: SGP4 Orbit Propagation", test_core_requirement_2_sgp4_propagation),
        ("Core Req 3: Conjunction Detection & Risk-Scoring", test_core_requirement_3_conjunction_and_risk_scoring),
        ("Core Req 4: Concrete Avoidance Maneuver", test_core_requirement_4_avoidance_maneuver),
        ("Core Req 5: Trajectory Before/After Verification", test_core_requirement_5_before_after_trajectory_visualization),
        ("Bonus Req 1: Urgency & Severity Ranking", test_bonus_1_multi_conjunction_ranking),
        ("Bonus Req 2: Fuel-Cost vs. Collision Risk Trade-off", test_bonus_2_fuel_cost_tradeoff),
    ]

    passed_count = 0
    total = len(suite)

    for name, test_fn in suite:
        try:
            if test_fn():
                passed_count += 1
        except AssertionError as e:
            print(f"  ❌ FAILED: {name} -> {e}\n")
        except Exception as e:
            print(f"  ❌ ERROR in {name} -> {e}\n")

    print("#" * 65)
    print(f"VERIFICATION SUMMARY: {passed_count}/{total} REQUIREMENTS VERIFIED")
    if passed_count == total:
        print("🎉 STATUS: 100% COMPLIANT WITH ALL CORE & BONUS REQUIREMENTS!")
    else:
        print(f"⚠️ STATUS: {total - passed_count} REQUIREMENT(S) FAILED")
    print("#" * 65 + "\n")
    return 0 if passed_count == total else 1


if __name__ == "__main__":
    sys.exit(run_all_compliance_tests())
