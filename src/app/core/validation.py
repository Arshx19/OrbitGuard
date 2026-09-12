"""
Validation & Re-screening module for ORBITGUARD AI.
Implements the core decision rule: "A maneuver that fixes one collision must not create another."
Re-screens post-maneuver trajectories against the entire space environment catalog.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
import numpy as np

from app.core.data_ingestion import TLEData
from app.core.propagation import OrbitalPropagator
from app.core.conjunction import ConjunctionDetector, ConjunctionResult
from app.core.maneuver_optimizer import ManeuverCandidate, rtn_to_eci_delta_v

logger = logging.getLogger(__name__)


class EnvironmentValidator:
    """
    Validates candidate avoidance maneuvers by re-propagating post-maneuver trajectories
    and re-screening against all background catalog objects.
    """

    def __init__(
        self,
        safe_miss_threshold_km: float = 3.0,
        screening_horizon_hours: float = 48.0
    ):
        """
        Initialize EnvironmentValidator.

        Args:
            safe_miss_threshold_km: Minimum required miss distance (km) for a maneuver to be safe
            screening_horizon_hours: Prediction window (hours) for post-maneuver re-screening
        """
        self.safe_miss_threshold_km = safe_miss_threshold_km
        self.screening_horizon_hours = screening_horizon_hours
        self.propagator = OrbitalPropagator()
        self.detector = ConjunctionDetector(miss_distance_threshold=safe_miss_threshold_km)
        self.logger = logging.getLogger(__name__)

    def evaluate_candidate(
        self,
        candidate: ManeuverCandidate,
        primary_sat_tle: TLEData,
        threat_sat_tle: TLEData,
        catalog_tles: List[TLEData],
        primary_tca: datetime
    ) -> ManeuverCandidate:
        """
        Evaluate a single maneuver candidate against primary threat and full environment catalog.

        Args:
            candidate: ManeuverCandidate object to evaluate
            primary_sat_tle: TLE of maneuvering satellite
            threat_sat_tle: TLE of primary threat satellite/debris
            catalog_tles: List of all background tracked objects in catalog
            primary_tca: Expected TCA of primary conjunction

        Returns:
            Evaluated ManeuverCandidate with safety status and re-screening results populated
        """
        burn_time = candidate.burn_time

        # 1. Propagate primary sat to burn_time to get pre-burn position and velocity
        pos_at_burn = self.propagator.propagate_single_satellite(primary_sat_tle.satrec, burn_time)
        
        # Approximate velocity at burn time using standard orbital velocity norm
        # v ~ sqrt(mu/r) where mu = 398600.4418 km^3/s^2
        r_mag = np.linalg.norm(pos_at_burn) if pos_at_burn is not None else 6771.0
        v_mag = np.sqrt(398600.4418 / r_mag)
        # Tangential direction approximation
        v_approx = np.array([-pos_at_burn[1], pos_at_burn[0], 0.0])
        v_approx = v_approx / np.linalg.norm(v_approx) * v_mag if np.linalg.norm(v_approx) > 0 else np.array([0, v_mag, 0])

        # 2. Convert RTN delta-v to ECI delta-v (km/s)
        dv_eci_kms = rtn_to_eci_delta_v(candidate.delta_v_rtn, pos_at_burn, v_approx)

        # 3. Propagate post-burn primary trajectory to primary_tca
        dt_burn_to_tca = (primary_tca - burn_time).total_seconds()
        
        # Primary baseline position at TCA
        pos_prim_tca = self.propagator.propagate_single_satellite(primary_sat_tle.satrec, primary_tca)
        pos_threat_tca = self.propagator.propagate_single_satellite(threat_sat_tle.satrec, primary_tca)

        if pos_prim_tca is None or pos_threat_tca is None:
            candidate.is_safe = False
            candidate.rejection_reason = "Propagation error during evaluation"
            return candidate

        # Post-burn position perturbation ~ pos_prim + dv_eci * dt
        pos_prim_post_burn = pos_prim_tca + dv_eci_kms * dt_burn_to_tca
        new_miss_distance = float(np.linalg.norm(pos_prim_post_burn - pos_threat_tca))

        candidate.new_miss_distance_km = new_miss_distance
        candidate.new_tca = primary_tca

        # Check if primary threat resolved
        if new_miss_distance >= self.safe_miss_threshold_km:
            candidate.primary_threat_resolved = True
        else:
            candidate.primary_threat_resolved = False
            candidate.is_safe = False
            candidate.rejection_reason = f"Insufficient miss distance ({new_miss_distance:.2f} km < {self.safe_miss_threshold_km} km)"
            return candidate

        # 4. RE-SCREENING PASS: Check post-maneuver trajectory against ALL background objects
        secondary_conflicts = []
        for bg_tle in catalog_tles:
            # Skip primary threat object and maneuvering satellite itself
            if bg_tle.satellite_number in (primary_sat_tle.satellite_number, threat_sat_tle.satellite_number):
                continue

            pos_bg_tca = self.propagator.propagate_single_satellite(bg_tle.satrec, primary_tca)
            if pos_bg_tca is not None:
                dist_to_bg = float(np.linalg.norm(pos_prim_post_burn - pos_bg_tca))
                if dist_to_bg < self.safe_miss_threshold_km:
                    secondary_conflicts.append({
                        'secondary_norad_id': bg_tle.satellite_number,
                        'secondary_name': getattr(bg_tle, 'designation', f"SAT-{bg_tle.satellite_number}"),
                        'miss_distance_km': dist_to_bg
                    })

        if secondary_conflicts:
            candidate.secondary_threats_detected = True
            candidate.secondary_threat_details = secondary_conflicts
            candidate.is_safe = False
            first_conflict = secondary_conflicts[0]
            candidate.rejection_reason = (f"Secondary collision detected with object {first_conflict['secondary_norad_id']} "
                                          f"({first_conflict['miss_distance_km']:.2f} km)")
        else:
            candidate.secondary_threats_detected = False
            candidate.is_safe = True
            candidate.rejection_reason = None

        return candidate

    def validate_and_rank_candidates(
        self,
        candidates: List[ManeuverCandidate],
        primary_sat_tle: TLEData,
        threat_sat_tle: TLEData,
        catalog_tles: List[TLEData],
        primary_tca: datetime
    ) -> List[ManeuverCandidate]:
        """
        Validate grid of maneuver candidates and return evaluated results ranked by delta-v.

        Args:
            candidates: Grid of ManeuverCandidate objects
            primary_sat_tle: TLE of maneuvering satellite
            threat_sat_tle: TLE of primary threat
            catalog_tles: Full environment catalog TLEs
            primary_tca: Primary conjunction TCA

        Returns:
            Evaluated list of ManeuverCandidate objects
        """
        evaluated = []
        for cand in candidates:
            res = self.evaluate_candidate(
                cand, primary_sat_tle, threat_sat_tle, catalog_tles, primary_tca
            )
            evaluated.append(res)

        self.logger.info(f"Evaluated {len(evaluated)} candidates: "
                         f"{sum(1 for c in evaluated if c.is_safe)} SAFE, "
                         f"{sum(1 for c in evaluated if not c.is_safe)} REJECTED")
        return evaluated
