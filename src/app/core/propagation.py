"""
Orbital propagation module for ORBITGUARD AI.
Implements SGP4 propagator for calculating satellite positions over time.
"""

import logging
from typing import List, Optional, Tuple, Union
from datetime import datetime, timedelta
import numpy as np

from sgp4.api import Satrec, jday

logger = logging.getLogger(__name__)


class OrbitalPropagator:
    """Handles orbital propagation using SGP4 algorithm."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def propagate_single_satellite(
        self,
        satrec: Satrec,
        target_time: datetime
    ) -> Optional[np.ndarray]:
        """
        Propagate a single satellite to a target time.

        Args:
            satrec: SGP4 satellite record
            target_time: Target datetime for propagation

        Returns:
            Position vector [x, y, z] in kilometers, or None if propagation failed
        """
        try:
            # Convert datetime to Julian day
            jd, fr = jday(
                target_time.year, target_time.month, target_time.day,
                target_time.hour, target_time.minute,
                target_time.second + target_time.microsecond / 1e6
            )

            # Propagate using SGP4
            error_code, position, velocity = satrec.sgp4(jd, fr)

            if error_code != 0:
                logger.warning(f"SGP4 propagation error {error_code}")
                return None

            # Return position in kilometers
            return np.array(position, dtype=np.float64)

        except Exception as e:
            logger.error(f"Error in satellite propagation: {e}")
            return None

    def propagate_multiple_times(
        self,
        satrec: Satrec,
        start_time: datetime,
        end_time: datetime,
        time_step: timedelta
    ) -> Tuple[List[datetime], List[np.ndarray]]:
        """
        Propagate satellite over a time range with regular intervals.

        Args:
            satrec: SGP4 satellite record
            start_time: Start datetime
            end_time: End datetime
            time_step: Time interval between calculations

        Returns:
            Tuple of (timestamps, positions) where positions is list of [x,y,z] arrays
        """
        timestamps = []
        positions = []

        current_time = start_time
        while current_time <= end_time:
            position = self.propagate_single_satellite(satrec, current_time)
            if position is not None:
                timestamps.append(current_time)
                positions.append(position)
            current_time += time_step

        return timestamps, positions

    def propagate_satellite_array(
        self,
        satrecs: List[Satrec],
        target_times: List[datetime]
    ) -> np.ndarray:
        """
        Propagate multiple satellites to multiple times.

        Args:
            satrecs: List of SGP4 satellite records
            target_times: List of target datetimes

        Returns:
            3D numpy array of shape (n_satellites, n_times, 3) with positions in km
        """
        n_sats = len(satrecs)
        n_times = len(target_times)
        positions = np.full((n_sats, n_times, 3), np.nan, dtype=np.float64)

        for i, satrec in enumerate(satrecs):
            for j, target_time in enumerate(target_times):
                pos = self.propagate_single_satellite(satrec, target_time)
                if pos is not None:
                    positions[i, j] = pos

        return positions

    def calculate_velocity(
        self,
        satrec: Satrec,
        target_time: datetime
    ) -> Optional[np.ndarray]:
        """
        Calculate velocity vector for a satellite at target time.

        Args:
            satrec: SGP4 satellite record
            target_time: Target datetime

        Returns:
            Velocity vector [vx, vy, vz] in km/s, or None if failed
        """
        try:
            # Convert datetime to Julian day
            jd, fr = jday(
                target_time.year, target_time.month, target_time.day,
                target_time.hour, target_time.minute,
                target_time.second + target_time.microsecond / 1e6
            )

            # Propagate using SGP4 (returns both position and velocity)
            error_code, position, velocity = satrec.sgp4(jd, fr)

            if error_code != 0:
                logger.warning(f"SGP4 propagation error {error_code} for velocity calculation")
                return None

            # Return velocity in km/s
            return np.array(velocity, dtype=np.float64)

        except Exception as e:
            logger.error(f"Error calculating velocity: {e}")
            return None

    def propagate_with_covariance(
        self,
        satrec: Satrec,
        target_time: datetime,
        position_covariance: Optional[np.ndarray] = None
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Propagate satellite and optionally propagate covariance matrix.

        Args:
            satrec: SGP4 satellite record
            target_time: Target datetime
            position_covariance: 3x3 position covariance matrix (optional)

        Returns:
            Tuple of (position, propagated_covariance) or (None, None) if failed
        """
        position = self.propagate_single_satellite(satrec, target_time)
        if position is None:
            return None, None

        # For now, return position only (covariance propagation would require
        # implementing state transition matrix, which is complex)
        # In a full implementation, you'd propagate the 6x6 state covariance
        # using the STM from SGP4
        return position, position_covariance


def propagate_tle_array(
    tle_objects: List,
    target_times: List[datetime]
) -> np.ndarray:
    """
    Convenience function to propagate an array of TLE objects.

    Args:
        tle_objects: List of TLEData objects from data_ingestion module
        target_times: List of target datetimes for propagation

    Returns:
        3D numpy array of shape (n_objects, n_times, 3) with positions in km
    """
    propagator = OrbitalPropagator()

    # Extract satrec objects from TLEData
    satrecs = []
    valid_objects = []

    for tle_obj in tle_objects:
        if hasattr(tle_obj, 'satrec') and tle_obj.satrec is not None:
            satrecs.append(tle_obj.satrec)
            valid_objects.append(tle_obj)
        else:
            logger.warning("Skipping TLE object without valid satrec")

    if not satrecs:
        logger.error("No valid satellite records for propagation")
        return np.array([])

    return propagator.propagate_satellite_array(satrecs, target_times)


def propagate_single_tle(
    tle_object,
    target_time: datetime
) -> Optional[np.ndarray]:
    """
    Convenience function to propagate a single TLE object.

    Args:
        tle_object: TLEData object from data_ingestion module
        target_time: Target datetime for propagation

    Returns:
        Position vector [x, y, z] in kilometers, or None if failed
    """
    if not hasattr(tle_object, 'satrec') or tle_object.satrec is None:
        logger.error("TLE object has no valid satrec")
        return None

    propagator = OrbitalPropagator()
    return propagator.propagate_single_satellite(tle_object.satrec, target_time)


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    # This would typically be called after loading TLE data
    from data_ingestion import load_sample_tles

    try:
        tle_list = load_sample_tles()
        if tle_list:
            tle = tle_list[0]
            logger.info(f"Loaded TLE for satellite {tle.satellite_number}")

            # Propagate to current time
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            position = propagate_single_tle(tle, now)

            if position is not None:
                logger.info(f"Position at {now}: {position} km")
            else:
                logger.error("Failed to propagate to current time")

            # Propagate over next 2 hours with 10-minute intervals
            from datetime import timedelta
            start_time = now
            end_time = now + timedelta(hours=2)
            time_step = timedelta(minutes=10)

            timestamps, positions = propagator.propagate_multiple_times(
                tle.satrec, start_time, end_time, time_step
            )

            logger.info(f"Propagated over {len(timestamps)} time steps")
            if positions:
                logger.info(f"First position: {positions[0]} km")
                logger.info(f"Last position: {positions[-1]} km")
        else:
            logger.error("Failed to load sample TLE data")
    except ImportError:
        logger.warning("Could not import data_ingestion for demo")