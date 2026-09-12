"""
Maneuver Optimizer module for ORBITGUARD AI.
Generates candidate collision avoidance maneuvers across Radial, Along-track, and Cross-track directions,
and calculates post-burn orbital trajectories.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
import numpy as np

from sgp4.api import Satrec, WGS72, jday

logger = logging.getLogger(__name__)


class ManeuverCandidate:
    """Container for a candidate collision avoidance maneuver."""

    def __init__(
        self,
        candidate_id: str,
        delta_v_rtn: np.ndarray,  # [dv_radial, dv_along_track, dv_cross_track] in m/s
        direction_name: str,       # 'along_track', 'radial', 'cross_track', 'combined'
        burn_time: datetime,
        delta_v_magnitude_ms: float
    ):
        self.candidate_id = candidate_id
        self.delta_v_rtn = delta_v_rtn
        self.direction_name = direction_name
        self.burn_time = burn_time
        self.delta_v_magnitude_ms = delta_v_magnitude_ms
        
        # Post-maneuver outcomes (set after propagation)
        self.new_miss_distance_km: Optional[float] = None
        self.new_tca: Optional[datetime] = None
        self.primary_threat_resolved: bool = False
        self.secondary_threats_detected: bool = False
        self.secondary_threat_details: List[Dict[str, Any]] = []
        self.is_safe: bool = False
        self.rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert candidate to dictionary for serialization."""
        return {
            'candidate_id': self.candidate_id,
            'delta_v_rtn_ms': self.delta_v_rtn.tolist(),
            'direction_name': self.direction_name,
            'burn_time': self.burn_time.isoformat() if self.burn_time else None,
            'delta_v_magnitude_ms': self.delta_v_magnitude_ms,
            'new_miss_distance_km': self.new_miss_distance_km,
            'new_tca': self.new_tca.isoformat() if self.new_tca else None,
            'primary_threat_resolved': self.primary_threat_resolved,
            'secondary_threats_detected': self.secondary_threats_detected,
            'secondary_threat_details': self.secondary_threat_details,
            'is_safe': self.is_safe,
            'rejection_reason': self.rejection_reason
        }

    def __repr__(self) -> str:
        status = "SAFE" if self.is_safe else f"REJECTED ({self.rejection_reason})"
        return (f"ManeuverCandidate({self.candidate_id}, dv={self.delta_v_magnitude_ms:.3f} m/s "
                f"[{self.direction_name}], status={status})")


def compute_rtn_frame(position_eci: np.ndarray, velocity_eci: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute Radial, Tangential (Along-track), Normal (Cross-track) unit vectors in ECI frame.

    Args:
        position_eci: Position vector [x, y, z] in km
        velocity_eci: Velocity vector [vx, vy, vz] in km/s

    Returns:
        Tuple of (u_radial, u_along_track, u_cross_track) unit vectors in ECI
    """
    r_norm = np.linalg.norm(position_eci)
    u_r = position_eci / r_norm if r_norm > 0 else np.array([1.0, 0.0, 0.0])

    h = np.cross(position_eci, velocity_eci)
    h_norm = np.linalg.norm(h)
    u_n = h / h_norm if h_norm > 0 else np.array([0.0, 0.0, 1.0])

    u_t = np.cross(u_n, u_r)
    u_t_norm = np.linalg.norm(u_t)
    if u_t_norm > 0:
        u_t = u_t / u_t_norm

    return u_r, u_t, u_n


def rtn_to_eci_delta_v(
    delta_v_rtn_ms: np.ndarray,
    position_eci: np.ndarray,
    velocity_eci: np.ndarray
) -> np.ndarray:
    """
    Convert RTN delta-v vector (m/s) to ECI delta-v vector (km/s).

    Args:
        delta_v_rtn_ms: Delta-v in RTN frame [dv_R, dv_T, dv_N] in meters/second
        position_eci: Satellite position [x,y,z] in km
        velocity_eci: Satellite velocity [vx,vy,vz] in km/s

    Returns:
        Delta-v vector in ECI frame in km/s
    """
    u_r, u_t, u_n = compute_rtn_frame(position_eci, velocity_eci)
    dv_r_kms = delta_v_rtn_ms[0] / 1000.0
    dv_t_kms = delta_v_rtn_ms[1] / 1000.0
    dv_n_kms = delta_v_rtn_ms[2] / 1000.0

    delta_v_eci_kms = dv_r_kms * u_r + dv_t_kms * u_t + dv_n_kms * u_n
    return delta_v_eci_kms


class ManeuverOptimizer:
    """
    Generates and evaluates candidate collision avoidance maneuvers.
    Search grid includes along-track, radial, and cross-track directions over a range of delta-v magnitudes.
    """

    def __init__(self, safe_miss_distance_threshold_km: float = 2.0):
        self.safe_miss_distance_threshold_km = safe_miss_distance_threshold_km
        self.logger = logging.getLogger(__name__)

    def generate_candidate_grid(
        self,
        burn_time: datetime,
        dv_min_ms: float = 0.05,
        dv_max_ms: float = 1.0,
        num_steps: int = 6
    ) -> List[ManeuverCandidate]:
        """
        Generate candidate maneuver options across RTN directions.

        Args:
            burn_time: Epoch of proposed burn
            dv_min_ms: Minimum delta-v magnitude in m/s
            dv_max_ms: Maximum delta-v magnitude in m/s
            num_steps: Number of magnitude increments

        Returns:
            List of ManeuverCandidate objects
        """
        candidates = []
        dv_magnitudes = np.linspace(dv_min_ms, dv_max_ms, num_steps)
        cand_count = 1

        # 1. Along-track (pos & neg) - Cheapest direction!
        for mag in dv_magnitudes:
            for direction, sign, name in [(np.array([0, 1, 0]), 1.0, "Along-track (+ Prograde)"),
                                          (np.array([0, 1, 0]), -1.0, "Along-track (- Retrograde)")]:
                dv_rtn = sign * mag * direction
                cid = f"CAND-{cand_count:02d}"
                candidates.append(ManeuverCandidate(
                    candidate_id=cid,
                    delta_v_rtn=dv_rtn,
                    direction_name=name,
                    burn_time=burn_time,
                    delta_v_magnitude_ms=float(mag)
                ))
                cand_count += 1

        # 2. Radial (pos & neg)
        for mag in dv_magnitudes[::2]:  # Sparse sampling for radial
            for direction, sign, name in [(np.array([1, 0, 0]), 1.0, "Radial (+ Outward)"),
                                          (np.array([1, 0, 0]), -1.0, "Radial (- Inward)")]:
                dv_rtn = sign * mag * direction
                cid = f"CAND-{cand_count:02d}"
                candidates.append(ManeuverCandidate(
                    candidate_id=cid,
                    delta_v_rtn=dv_rtn,
                    direction_name=name,
                    burn_time=burn_time,
                    delta_v_magnitude_ms=float(mag)
                ))
                cand_count += 1

        # 3. Cross-track (pos & neg)
        for mag in dv_magnitudes[::2]:  # Sparse sampling for cross-track
            for direction, sign, name in [(np.array([0, 0, 1]), 1.0, "Cross-track (+ Out-of-plane)"),
                                          (np.array([0, 0, 1]), -1.0, "Cross-track (- Out-of-plane)")]:
                dv_rtn = sign * mag * direction
                cid = f"CAND-{cand_count:02d}"
                candidates.append(ManeuverCandidate(
                    candidate_id=cid,
                    delta_v_rtn=dv_rtn,
                    direction_name=name,
                    burn_time=burn_time,
                    delta_v_magnitude_ms=float(mag)
                ))
                cand_count += 1

        self.logger.info(f"Generated {len(candidates)} maneuver candidates for burn time {burn_time}")
        return candidates

    def select_optimal_maneuver(
        self,
        candidates: List[ManeuverCandidate]
    ) -> Optional[ManeuverCandidate]:
        """
        Select candidate with minimum delta-v among all SAFE candidates.

        Args:
            candidates: List of evaluated ManeuverCandidate objects

        Returns:
            Lowest-cost safe ManeuverCandidate, or None if no candidate is safe
        """
        safe_candidates = [c for c in candidates if c.is_safe]
        if not safe_candidates:
            self.logger.warning("No safe maneuver candidate found in grid search!")
            return None

        # Sort by delta_v_magnitude_ms ascending
        safe_candidates.sort(key=lambda c: c.delta_v_magnitude_ms)
        best = safe_candidates[0]
        self.logger.info(f"Selected optimal maneuver: {best}")
        return best
