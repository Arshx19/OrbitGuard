"""
Conjunction detection module for ORBITGUARD AI.
Handles detection of close approaches between satellites and calculation of miss distance and TCA.
"""

import logging
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta
import numpy as np
from scipy.spatial.distance import cdist
from itertools import combinations

logger = logging.getLogger(__name__)


class ConjunctionResult:
    """Container for conjunction detection results."""

    def __init__(
        self,
        satellite1_id: int,
        satellite2_id: int,
        tca: datetime,
        miss_distance: float,
        position1: Optional[np.ndarray] = None,
        position2: Optional[np.ndarray] = None,
        velocity1: Optional[np.ndarray] = None,
        velocity2: Optional[np.ndarray] = None
    ):
        self.satellite1_id = satellite1_id
        self.satellite2_id = satellite2_id
        self.tca = tca  # Time of Closest Approach
        self.miss_distance = miss_distance  # in kilometers
        self.position1 = position1
        self.position2 = position2
        self.velocity1 = velocity1
        self.velocity2 = velocity2

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            'satellite1_id': self.satellite1_id,
            'satellite2_id': self.satellite2_id,
            'tca': self.tca.isoformat() if self.tca else None,
            'miss_distance_km': self.miss_distance,
            'position1_km': self.position1.tolist() if self.position1 is not None else None,
            'position2_km': self.position2.tolist() if self.position2 is not None else None,
            'velocity1_kms': self.velocity1.tolist() if self.velocity1 is not None else None,
            'velocity2_kms': self.velocity2.tolist() if self.velocity2 is not None else None
        }

    def __repr__(self) -> str:
        return (f"Conjunction(sat{self.satellite1_id}-sat{self.satellite2_id}, "
                f"TCA={self.tca}, miss_distance={self.miss_distance:.3f} km)")


class ConjunctionDetector:
    """Detects conjunctions (close approaches) between orbiting objects."""

    def __init__(self, miss_distance_threshold: float = 5.0):
        """
        Initialize conjunction detector.

        Args:
            miss_distance_threshold: Miss distance threshold for triggering conjunction alert (km)
        """
        self.miss_distance_threshold = miss_distance_threshold
        self.logger = logging.getLogger(__name__)

    def find_conjunctions_in_timeframe(
        self,
        positions: Dict[int, np.ndarray],
        timestamps: List[datetime]
    ) -> List[ConjunctionResult]:
        """
        Find conjunctions over a timeframe for multiple satellites.

        Args:
            positions: Dictionary mapping satellite_id to position array of shape (n_times, 3)
            timestamps: List of datetime objects corresponding to position arrays

        Returns:
            List of ConjunctionResult objects
        """
        conjunctions = []
        satellite_ids = list(positions.keys())

        self.logger.info(f"Checking {len(satellite_ids)} satellites for conjunctions over {len(timestamps)} time steps")

        # For each time step, check all satellite pairs
        for time_idx, current_time in enumerate(timestamps):
            # Get positions at this time step
            time_positions = {}
            for sat_id in satellite_ids:
                if time_idx < positions[sat_id].shape[0]:
                    time_positions[sat_id] = positions[sat_id][time_idx]

            # Check all pairs at this time step
            for sat1_id, sat2_id in combinations(satellite_ids, 2):
                if sat1_id in time_positions and sat2_id in time_positions:
                    pos1 = time_positions[sat1_id]
                    pos2 = time_positions[sat2_id]

                    # Calculate distance
                    distance = np.linalg.norm(pos1 - pos2)

                    # Check if within threshold
                    if distance <= self.miss_distance_threshold:
                        conjunction = ConjunctionResult(
                            satellite1_id=sat1_id,
                            satellite2_id=sat2_id,
                            tca=current_time,
                            miss_distance=float(distance),
                            position1=pos1.copy(),
                            position2=pos2.copy()
                        )
                        conjunctions.append(conjunction)
                        self.logger.info(
                            f"Conjunction detected: {conjunction}"
                        )

        return conjunctions

    def find_tca_for_pair(
        self,
        positions1: np.ndarray,
        positions2: np.ndarray,
        timestamps: List[datetime]
    ) -> Optional[ConjunctionResult]:
        """
        Find Time of Closest Approach (TCA) for a satellite pair over time.

        Args:
            positions1: Position array for satellite 1 of shape (n_times, 3)
            positions2: Position array for satellite 2 of shape (n_times, 3)
            timestamps: List of datetime objects

        Returns:
            ConjunctionResult for the closest approach, or None if no conjunction below threshold
        """
        if positions1.shape[0] != positions2.shape[0] or positions1.shape[0] != len(timestamps):
            self.logger.error("Position arrays and timestamps must have matching dimensions")
            return None

        # Calculate distances at each time step
        distances = np.linalg.norm(positions1 - positions2, axis=1)

        # Find minimum distance
        min_idx = np.argmin(distances)
        min_distance = distances[min_idx]

        # Check if below threshold
        if min_distance <= self.miss_distance_threshold:
            tca = timestamps[min_idx]
            conjunction = ConjunctionResult(
                satellite1_id=0,  # Will be set by caller
                satellite2_id=0,  # Will be set by caller
                tca=tca,
                miss_distance=float(min_distance),
                position1=positions1[min_idx].copy(),
                position2=positions2[min_idx].copy()
            )
            return conjunction

        return None

    def find_all_tcas(
        self,
        positions: Dict[int, np.ndarray],
        timestamps: List[datetime]
    ) -> List[ConjunctionResult]:
        """
        Find TCAs for all satellite pairs.

        Args:
            positions: Dictionary mapping satellite_id to position array of shape (n_times, 3)
            timestamps: List of datetime objects

        Returns:
            List of ConjunctionResult objects for all TCAs below threshold
        """
        conjunctions = []
        satellite_ids = list(positions.keys())

        self.logger.info(f"Finding TCAs for {len(satellite_ids)} satellites")

        # Check all unique pairs
        for sat1_id, sat2_id in combinations(satellite_ids, 2):
            if sat1_id in positions and sat2_id in positions:
                pos1 = positions[sat1_id]
                pos2 = positions[sat2_id]

                conjunction = self.find_tca_for_pair(pos1, pos2, timestamps)
                if conjunction is not None:
                    # Set the satellite IDs properly
                    conjunction.satellite1_id = sat1_id
                    conjunction.satellite2_id = sat2_id
                    conjunctions.append(conjunction)
                    self.logger.info(f"TCA found: {conjunction}")

        return conjunctions

    def calculate_relative_velocity(
        self,
        velocity1: np.ndarray,
        velocity2: np.ndarray
    ) -> Tuple[np.ndarray, float]:
        """
        Calculate relative velocity between two satellites.

        Args:
            velocity1: Velocity vector of satellite 1 (km/s)
            velocity2: Velocity vector of satellite 2 (km/s)

        Returns:
            Tuple of (relative_velocity_vector, relative_speed)
        """
        relative_velocity = velocity1 - velocity2
        relative_speed = np.linalg.norm(relative_velocity)
        return relative_velocity, relative_speed

    def calculate_conjunction_geometry(
        self,
        position1: np.ndarray,
        position2: np.ndarray,
        velocity1: Optional[np.ndarray] = None,
        velocity2: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Calculate conjunction geometry including approach velocity and angle.

        Args:
            position1: Position vector of satellite 1 (km)
            position2: Position vector of satellite 2 (km)
            velocity1: Velocity vector of satellite 1 (km/s, optional)
            velocity2: Velocity vector of satellite 2 (km/s, optional)

        Returns:
            Dictionary with conjunction geometry details
        """
        # Miss distance vector (from sat2 to sat1)
        miss_vector = position1 - position2
        miss_distance = np.linalg.norm(miss_vector)
        miss_unit_vector = miss_vector / miss_distance if miss_distance > 0 else np.zeros(3)

        result = {
            'miss_distance_km': float(miss_distance),
            'miss_vector_km': miss_vector.tolist(),
            'miss_unit_vector': miss_unit_vector.tolist()
        }

        # If velocities are provided, calculate approach characteristics
        if velocity1 is not None and velocity2 is not None:
            relative_velocity, relative_speed = self.calculate_relative_velocity(velocity1, velocity2)

            # Radial velocity component (along miss vector)
            radial_velocity = np.dot(relative_velocity, miss_unit_vector)

            # Tangential velocity component
            tangential_velocity = relative_velocity - radial_velocity * miss_unit_vector
            tangential_speed = np.linalg.norm(tangential_velocity)

            # Approach angle (angle between relative velocity and miss vector)
            if relative_speed > 0 and miss_distance > 0:
                approach_angle = np.degrees(np.arccos(
                    np.clip(np.dot(relative_velocity, miss_vector) / (relative_speed * miss_distance), -1, 1)
                ))
            else:
                approach_angle = 0.0

            result.update({
                'relative_velocity_kms': relative_velocity.tolist(),
                'relative_speed_kms': float(relative_speed),
                'radial_velocity_kms': float(radial_velocity),
                'tangential_velocity_kms': tangential_velocity.tolist(),
                'tangential_speed_kms': float(tangential_speed),
                'approach_angle_degrees': float(approach_angle),
                'is_approaching': radial_velocity < 0  # Negative radial velocity means approaching
            })

        return result


def detect_conjunctions_simple(
    tle_objects: List,
    propagator_fn,
    start_time: datetime,
    end_time: datetime,
    time_step: timedelta,
    miss_distance_threshold: float = 5.0
) -> List[ConjunctionResult]:
    """
    Simple conjunction detection workflow.

    Args:
        tle_objects: List of TLEData objects
        propagator_fn: Function that takes (tle_object, target_time) and returns position
        start_time: Start of analysis period
        end_time: End of analysis period
        time_step: Time step for propagation
        miss_distance_threshold: Conjunction alert threshold (km)

    Returns:
        List of ConjunctionResult objects
    """
    detector = ConjunctionDetector(miss_distance_threshold)

    # Generate time array
    timestamps = []
    current_time = start_time
    while current_time <= end_time:
        timestamps.append(current_time)
        current_time += time_step

    # Propagate all satellites to all times
    positions = {}  # satellite_id -> position array (n_times, 3)

    for tle_obj in tle_objects:
        sat_id = getattr(tle_obj, 'satellite_number', hash(tle_obj))  # Fallback ID
        pos_list = []

        for target_time in timestamps:
            position = propagator_fn(tle_obj, target_time)
            if position is not None:
                pos_list.append(position)
            else:
                # Use NaN for failed propagations to maintain array shape
                pos_list.append(np.full(3, np.nan))

        positions[sat_id] = np.array(pos_list)

    # Find conjunctions
    conjunctions = detector.find_conjunctions_in_timeframe(positions, timestamps)

    return conjunctions


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    # Mock example - in practice, this would use real TLE data and propagator
    logger.info("Conjunction detection module ready for use")