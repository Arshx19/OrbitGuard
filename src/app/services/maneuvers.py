"""
Collision-avoidance maneuver planning for ORBITGUARD AI.

Given a conjunction, find the smallest impulsive burn that brings the collision
probability below a safety target without creating a new conjunction elsewhere.

How this differs from `app.core.maneuver_optimizer` / `app.core.validation`,
which it is intended to supersede:

  * **Real velocities.** The burn frame is built from the SGP4 velocity, not a
    velocity reconstructed as if every orbit were equatorial.
  * **Orbital mechanics, not straight lines.** Post-burn motion comes from the
    Clohessy-Wiltshire equations. A straight-line model credits radial and
    cross-track burns with displacement that grows forever, when in reality they
    oscillate and return to zero each orbit, and under-credits along-track burns
    by a factor of three. It therefore ranks candidates wrongly.
  * **Burn timing is searched.** Along-track displacement grows linearly with
    the time between burn and closest approach, so burning earlier can buy the
    same separation for a fraction of the propellant. The problem statement asks
    for magnitude, direction, *or timing*; the search covers all three.
  * **Re-screening covers the whole window.** Post-burn trajectories are
    screened against the catalog across the full horizon, not at one instant.
    A maneuver-induced conjunction would almost never fall at exactly the time
    of the original one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import minimize_scalar

from app.core.risk_engine import (
    PC_REPORTING_FLOOR,
    PC_THRESHOLD_AMBER,
    ConjunctionInput,
    RiskEngine,
)
from app.services.screening import CloseApproach, screen
from app.services.tracks import (
    MU_EARTH_KM3_S2,
    ManeuveredTrack,
    Track,
    from_jd,
    seconds_between,
)

# A maneuver is accepted when it brings the probability below the AMBER band.
PC_SAFE_TARGET = PC_THRESHOLD_AMBER

DELTA_V_GRID_MS = (0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 1.00)
# Lead times in orbits. Quarter-orbit phases are deliberate: radial and cross-track
# displacement oscillate as sin(nt), vanishing at every half and whole orbit, so a
# grid of only half-integer leads would evaluate those burns exactly where they do
# nothing and wrongly conclude they never help.
LEAD_ORBITS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5)
MIN_LEAD_MINUTES = 10.0
RESCREEN_REPORT_KM = 10.0
RESCREEN_HORIZON_HOURS = 24.0

AXES: Dict[str, Tuple[str, Tuple[Tuple[str, np.ndarray, str], ...]]] = {
    "T": ("Along-track", (
        ("+", np.array([0.0, 1.0, 0.0]), "prograde"),
        ("-", np.array([0.0, -1.0, 0.0]), "retrograde"),
    )),
    "R": ("Radial", (
        ("+", np.array([1.0, 0.0, 0.0]), "outward"),
        ("-", np.array([-1.0, 0.0, 0.0]), "inward"),
    )),
    "N": ("Cross-track", (
        ("+", np.array([0.0, 0.0, 1.0]), "+normal"),
        ("-", np.array([0.0, 0.0, -1.0]), "-normal"),
    )),
}

# Propellant assumptions for the fuel-cost estimate: (mass kg, specific impulse s).
_PROPULSION_DEFAULT = (500.0, 220.0)  # small LEO satellite, hydrazine monopropellant
_PROPULSION_BY_NAME = {"ISS": (420_000.0, 300.0)}
_G0 = 9.80665


def propellant_kg(delta_v_ms: float, object_name: str) -> float:
    """Tsiolkovsky propellant mass for a burn, using documented assumptions."""
    mass, isp = _PROPULSION_DEFAULT
    for token, spec in _PROPULSION_BY_NAME.items():
        if token in (object_name or "").upper():
            mass, isp = spec
            break
    return mass * (1.0 - math.exp(-delta_v_ms / (isp * _G0)))


@dataclass
class Candidate:
    candidate_id: str
    axis: str
    direction_name: str
    delta_v_ms: float
    lead_hours: float
    burn_time_iso: str
    delta_v_rtn_kms: np.ndarray = field(repr=False)
    new_miss_km: float = float("nan")
    new_tca_iso: Optional[str] = None
    pc_after: float = float("nan")
    rescreened: bool = False
    secondary_threats: List[Dict[str, object]] = field(default_factory=list)
    is_safe: bool = False
    rejection_reason: Optional[str] = None
    propellant_kg: float = 0.0
    post_burn_timeline: List[Dict[str, object]] = field(default_factory=list)

    def to_dict(self, pc_before: float) -> Dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "direction_name": self.direction_name,
            "axis": self.axis,
            "delta_v_magnitude_ms": self.delta_v_ms,
            "delta_v_rtn_ms": (np.asarray(self.delta_v_rtn_kms) * 1000.0).tolist(),
            "burn_lead_hours": round(self.lead_hours, 3),
            "burn_time": self.burn_time_iso,
            "new_miss_distance_km": self.new_miss_km,
            "new_tca": self.new_tca_iso,
            "pc_before": pc_before,
            "pc_after": self.pc_after,
            "rescreened": self.rescreened,
            "secondary_threats_detected": bool(self.secondary_threats),
            "secondary_threat_details": self.secondary_threats,
            "is_safe": self.is_safe,
            "rejection_reason": self.rejection_reason,
            "propellant_kg": self.propellant_kg,
            "post_burn_timeline": self.post_burn_timeline,
        }


def _conjunction_input(engine_primary: Track, secondary: Track, jd, fr, r1, v1, r2, v2, hours):
    return ConjunctionInput(
        primary_position_km=r1, primary_velocity_kms=v1,
        secondary_position_km=r2, secondary_velocity_kms=v2,
        time_to_tca_hours=hours,
        primary_tle_age_days=engine_primary.tle_age_days(jd, fr),
        secondary_tle_age_days=secondary.tle_age_days(jd, fr),
        primary_object_class=engine_primary.object_class,
        secondary_object_class=secondary.object_class,
        primary_uncertainty_regime=engine_primary.uncertainty_regime,
        secondary_uncertainty_regime=secondary.uncertainty_regime,
    )


class ManeuverPlanner:
    """Searches for, evaluates, and validates avoidance maneuvers for one event."""

    def __init__(self, engine: RiskEngine, catalog: Sequence[Track]):
        self.engine = engine
        self.catalog = list(catalog)

    # -- candidate construction --------------------------------------------

    def _grid(self, event: CloseApproach, now_jd: float, now_fr: float,
              dv_bounds_ms: Optional[Tuple[float, float]] = None) -> List[Candidate]:
        r, _ = event.primary.state(event.tca_jd, event.tca_fr)
        period_s = 2.0 * math.pi * math.sqrt(float(np.linalg.norm(r)) ** 3 / MU_EARTH_KM3_S2)
        available_s = seconds_between(now_jd, now_fr, event.tca_jd, event.tca_fr)

        candidates = []
        for axis, (axis_name, signs) in AXES.items():
            for sign, unit, label in signs:
                for lead_orbits in LEAD_ORBITS:
                    lead_s = lead_orbits * period_s
                    if lead_s > available_s - MIN_LEAD_MINUTES * 60.0:
                        continue
                    burn_jd, burn_fr = event.tca_jd, event.tca_fr - lead_s / 86400.0
                    for dv in DELTA_V_GRID_MS:
                        if dv_bounds_ms and not (dv_bounds_ms[0] <= dv <= dv_bounds_ms[1]):
                            continue
                        candidates.append(Candidate(
                            candidate_id=f"{axis}{sign}{dv:.2f}@{lead_orbits:g}",
                            axis=axis,
                            direction_name=f"{axis_name} ({label})",
                            delta_v_ms=dv,
                            lead_hours=lead_s / 3600.0,
                            burn_time_iso=from_jd(burn_jd, burn_fr).isoformat(),
                            delta_v_rtn_kms=unit * dv / 1000.0,
                        ))
        return candidates

    def _maneuvered(self, event: CloseApproach, candidate: Candidate) -> ManeuveredTrack:
        lead_days = candidate.lead_hours / 24.0
        base = event.primary
        return ManeuveredTrack(
            object_id=f"{base.object_id}-mnv",
            name=base.name, object_type=base.object_type, object_class=base.object_class,
            maneuverable=True, body_key=base.body_key, simulated=base.simulated,
            uncertainty_regime=base.uncertainty_regime,
            base=base, burn_jd=event.tca_jd, burn_fr=event.tca_fr - lead_days,
            delta_v_rtn_kms=candidate.delta_v_rtn_kms,
        )

    # -- evaluation ----------------------------------------------------------

    def _primary_outcome(self, event: CloseApproach, candidate: Candidate, now_jd, now_fr, method):
        """New closest approach to the original secondary, and its probability."""
        moved = self._maneuvered(event, candidate)
        secondary = event.secondary

        def separation(offset_s):
            fr = event.tca_fr + offset_s / 86400.0
            a, _ = moved.state(event.tca_jd, fr)
            b, _ = secondary.state(event.tca_jd, fr)
            return float(np.linalg.norm(a - b))

        result = minimize_scalar(separation, bounds=(-600.0, 600.0), method="bounded",
                                 options={"xatol": 1e-4})
        jd, fr = event.tca_jd, event.tca_fr + result.x / 86400.0
        r1, v1 = moved.state(jd, fr)
        r2, v2 = secondary.state(jd, fr)
        hours = seconds_between(now_jd, now_fr, jd, fr) / 3600.0
        conj = _conjunction_input(moved, secondary, jd, fr, r1, v1, r2, v2, hours)

        candidate.new_miss_km = float(result.fun)
        candidate.new_tca_iso = from_jd(jd, fr).isoformat()
        candidate.pc_after = self.engine.probability(conj, method=method).pc
        candidate.propellant_kg = propellant_kg(candidate.delta_v_ms, event.primary.name)

        post_burn_timeline = []
        for offset_h in [-48, -36, -24, -12, -6, 0]:
            t_fr = event.tca_fr + offset_h / 24.0
            a_pos, _ = moved.state(event.tca_jd, t_fr)
            b_pos, _ = secondary.state(event.tca_jd, t_fr)
            dist = float(np.linalg.norm(a_pos - b_pos))
            after_dist = round(dist, 3) if offset_h != 0 else round(candidate.new_miss_km, 3)
            post_burn_timeline.append({
                "t": f"T{offset_h:+d}" if offset_h else "T-0",
                "hours": float(offset_h),
                "distance_km": after_dist,
                "after_km": after_dist,
            })
        candidate.post_burn_timeline = post_burn_timeline

        return moved

    def _rescreen(self, event: CloseApproach, candidate: Candidate, moved: ManeuveredTrack, now_jd, now_fr):
        """Screen the post-burn trajectory against the catalog across the horizon."""
        burn_start = from_jd(event.tca_jd, event.tca_fr - candidate.lead_hours / 24.0)
        others = [t for t in self.catalog
                  if t.object_id != event.primary.object_id
                  and (t.body_key is None or t.body_key != event.primary.body_key)]
        if event.secondary not in others:
            others.append(event.secondary)

        approaches = screen(
            [moved, *others], burn_start,
            duration_hours=RESCREEN_HORIZON_HOURS, step_s=30.0,
            report_km=RESCREEN_REPORT_KM, primaries=[moved],
        )

        threats = []
        for approach in approaches:
            hours = seconds_between(now_jd, now_fr, approach.tca_jd, approach.tca_fr) / 3600.0
            other = approach.secondary if approach.primary is moved else approach.primary
            r1, v1 = moved.state(approach.tca_jd, approach.tca_fr)
            r2, v2 = other.state(approach.tca_jd, approach.tca_fr)
            conj = _conjunction_input(moved, other, approach.tca_jd, approach.tca_fr, r1, v1, r2, v2, hours)
            pc = self.engine.probability(conj, method="chan").pc
            if pc >= PC_SAFE_TARGET:
                threats.append({
                    "secondary_id": other.object_id,
                    "secondary_name": other.name,
                    "miss_distance_km": approach.miss_distance_km,
                    "tca": approach.tca.isoformat(),
                    "collision_probability": pc,
                    "is_original_threat": other is event.secondary,
                })

        candidate.rescreened = True
        candidate.secondary_threats = threats
        new = [t for t in threats if not t["is_original_threat"]]
        if new:
            worst = max(new, key=lambda t: t["collision_probability"])
            candidate.is_safe = False
            candidate.rejection_reason = (
                f"Resolves the original event but creates a new conjunction with "
                f"{worst['secondary_name']} at {worst['miss_distance_km']:.2f} km "
                f"(Pc {worst['collision_probability']:.1e})."
            )
        elif threats:
            candidate.is_safe = False
            candidate.rejection_reason = (
                "Re-screening finds the original object still too close on a later pass."
            )
        else:
            candidate.is_safe = True
            candidate.rejection_reason = None

    # -- public --------------------------------------------------------------

    def optimize(self, event: CloseApproach, now_jd: float, now_fr: float,
                 dv_bounds_ms: Optional[Tuple[float, float]] = None) -> Dict[str, object]:
        """
        Search the candidate grid and return a short, decision-ready table.

        Every candidate is evaluated against the original threat with the fast
        probability estimator. Per axis, the cheapest candidate meeting the
        safety target is then confirmed with the full quadrature and re-screened
        against the whole catalog, alongside the largest burn on that axis that
        fell short, so the table shows where the threshold lies.
        """
        base_input = _conjunction_input(
            event.primary, event.secondary, event.tca_jd, event.tca_fr,
            event.primary_position_km, event.primary_velocity_kms,
            event.secondary_position_km, event.secondary_velocity_kms,
            seconds_between(now_jd, now_fr, event.tca_jd, event.tca_fr) / 3600.0,
        )
        pc_before = self.engine.probability(base_input).pc

        grid = self._grid(event, now_jd, now_fr, dv_bounds_ms)
        for candidate in grid:
            self._primary_outcome(event, candidate, now_jd, now_fr, method="chan")

        shown: List[Candidate] = []
        for axis in AXES:
            on_axis = [c for c in grid if c.axis == axis]
            passing = sorted((c for c in on_axis if c.pc_after < PC_SAFE_TARGET),
                             key=lambda c: (c.delta_v_ms, -c.lead_hours))
            if passing:
                best = passing[0]
                moved = self._primary_outcome(event, best, now_jd, now_fr, method="foster")
                if best.pc_after < PC_SAFE_TARGET:
                    self._rescreen(event, best, moved, now_jd, now_fr)
                else:
                    best.rejection_reason = "Residual probability above the safety target."
                shown.append(best)

                short = [c for c in on_axis
                         if c.pc_after >= PC_SAFE_TARGET and c.delta_v_ms < best.delta_v_ms]
                if short:
                    near_miss = max(short, key=lambda c: (c.delta_v_ms, c.lead_hours))
                    near_miss.rejection_reason = (
                        f"Residual probability {near_miss.pc_after:.1e} remains above the "
                        f"{PC_SAFE_TARGET:.0e} safety target."
                    )
                    shown.append(near_miss)
            elif on_axis:
                best_effort = min(on_axis, key=lambda c: (c.pc_after, c.delta_v_ms))
                best_effort.rejection_reason = (
                    f"No burn searched on this axis meets the target; the best achieves "
                    f"Pc {best_effort.pc_after:.1e}."
                )
                shown.append(best_effort)

        shown.sort(key=lambda c: (c.delta_v_ms, c.candidate_id))
        safe = [c for c in shown if c.is_safe]
        best = min(safe, key=lambda c: (c.delta_v_ms, -c.lead_hours)) if safe else None

        return {
            "pc_before": pc_before,
            "safety_target": PC_SAFE_TARGET,
            "candidates_evaluated": len(grid),
            "candidates": [c.to_dict(pc_before) for c in shown],
            "recommended_candidate_id": best.candidate_id if best else None,
        }

    def validate(self, event: CloseApproach, candidate_id: str, now_jd: float, now_fr: float) -> Dict[str, object]:
        """Fully evaluate one candidate: quadrature Pc plus a whole-catalog re-screen."""
        grid = {c.candidate_id: c for c in self._grid(event, now_jd, now_fr)}
        candidate = grid.get(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)

        base_input = _conjunction_input(
            event.primary, event.secondary, event.tca_jd, event.tca_fr,
            event.primary_position_km, event.primary_velocity_kms,
            event.secondary_position_km, event.secondary_velocity_kms,
            seconds_between(now_jd, now_fr, event.tca_jd, event.tca_fr) / 3600.0,
        )
        pc_before = self.engine.probability(base_input).pc

        moved = self._primary_outcome(event, candidate, now_jd, now_fr, method="foster")
        if candidate.pc_after >= PC_SAFE_TARGET:
            candidate.is_safe = False
            candidate.rejection_reason = (
                f"Residual probability {candidate.pc_after:.1e} remains above the "
                f"{PC_SAFE_TARGET:.0e} safety target."
            )
        else:
            self._rescreen(event, candidate, moved, now_jd, now_fr)

        result = candidate.to_dict(pc_before)
        result["pc_after_below_floor"] = candidate.pc_after < PC_REPORTING_FLOOR
        result["checks"] = {
            "original_conjunction_resolved": candidate.pc_after < PC_SAFE_TARGET,
            "post_maneuver_trajectory_propagated": True,
            "catalog_rescreened": candidate.rescreened,
            "rescreen_horizon_hours": RESCREEN_HORIZON_HOURS if candidate.rescreened else 0.0,
            "catalog_objects_screened": len(self.catalog) if candidate.rescreened else 0,
            "new_conjunctions": len([t for t in candidate.secondary_threats if not t["is_original_threat"]]),
        }
        return result
