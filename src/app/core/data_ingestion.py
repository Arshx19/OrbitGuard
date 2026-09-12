"""
Data ingestion module for ORBITGUARD AI.
Loads and parses TLE (Two-Line Element) files from data/raw/.
"""

import logging
import os
from typing import List, Optional, Tuple
from datetime import datetime
import re

from sgp4.api import Satrec, WGS72

logger = logging.getLogger(__name__)


class TLEData:
    """Container for TLE data and associated SGP4 satellite record."""

    def __init__(
        self,
        satellite_number: int,
        designation: str,
        classification: str,
        international_designator: str,
        epoch_year: int,
        epoch_day: float,
        first_derivative_mean_motion: float,
        second_derivative_mean_motion: float,
        bstar_drag_term: float,
        element_set_type: str,
        element_number: int,
        inclination: float,
        right_ascension: float,
        eccentricity: float,
        argument_of_perigee: float,
        mean_anomaly: float,
        mean_motion: float,
        mean_motion_dot: float,
        mean_motion_ddot: float,
        revolution_number: int,
        line1: str,
        line2: str,
        satrec: Optional[Satrec] = None
    ):
        self.satellite_number = satellite_number
        self.designation = designation
        self.classification = classification
        self.international_designator = international_designator
        self.epoch_year = epoch_year
        self.epoch_day = epoch_day
        self.first_derivative_mean_motion = first_derivative_mean_motion
        self.second_derivative_mean_motion = second_derivative_mean_motion
        self.bstar_drag_term = bstar_drag_term
        self.element_set_type = element_set_type
        self.element_number = element_number
        self.inclination = inclination  # degrees
        self.right_ascension = right_ascension  # degrees
        self.eccentricity = eccentricity
        self.argument_of_perigee = argument_of_perigee  # degrees
        self.mean_anomaly = mean_anomaly  # degrees
        self.mean_motion = mean_motion  # orbits/day
        self.mean_motion_dot = mean_motion_dot  # orbits/day^2
        self.mean_motion_ddot = mean_motion_ddot  # orbits/day^3
        self.revolution_number = revolution_number
        self.line1 = line1
        self.line2 = line2
        self.satrec = satrec  # SGP4 satellite record

        # Calculate epoch datetime
        self.epoch = self._calculate_epoch()

    def _calculate_epoch(self) -> datetime:
        """Calculate epoch datetime from year and day fraction."""
        year = self.epoch_year
        if year < 1957:  # Handle Y2K-like issue in TLE format
            year += 2000
        elif year < 2000:
            year += 1900

        # Convert day fraction to month/day/hour/minute/second
        day = int(self.epoch_day)
        fraction = self.epoch_day - day

        # Approximate conversion (more precise would need month lengths)
        month = 1
        while day > 31:  # Simplified - assumes 31 days/month for calculation
            day -= 31
            month += 1
            if month > 12:
                month = 1
                year += 1

        hour = int(fraction * 24)
        minute = int((fraction * 24 - hour) * 60)
        second = int(((fraction * 24 - hour) * 60 - minute) * 60)

        return datetime(year, month, day, hour, minute, second)

    def to_dict(self) -> dict:
        """Convert TLE data to dictionary."""
        return {
            'satellite_number': self.satellite_number,
            'designation': self.designation,
            'classification': self.classification,
            'international_designator': self.international_designator,
            'epoch': self.epoch.isoformat() if self.epoch else None,
            'epoch_year': self.epoch_year,
            'epoch_day': self.epoch_day,
            'first_derivative_mean_motion': self.first_derivative_mean_motion,
            'second_derivative_mean_motion': self.second_derivative_mean_motion,
            'bstar_drag_term': self.bstar_drag_term,
            'element_set_type': self.element_set_type,
            'element_number': self.element_number,
            'inclination_deg': self.inclination,
            'right_ascension_deg': self.right_ascension,
            'eccentricity': self.eccentricity,
            'argument_of_perigee_deg': self.argument_of_perigee,
            'mean_anomaly_deg': self.mean_anomaly,
            'mean_motion_orbits_per_day': self.mean_motion,
            'mean_motion_dot': self.mean_motion_dot,
            'mean_motion_ddot': self.mean_motion_ddot,
            'revolution_number': self.revolution_number
        }


class TLEParser:
    """Parses TLE (Two-Line Element) data."""

    TLE_LINE_PATTERN = re.compile(r'^(\d)\s+(.{68})$')

    @staticmethod
    def parse_line1(line1: str) -> Tuple:
        """Parse TLE line 1."""
        # Line 1 format:
        # 1 25544U 98067A   21275.51473713  .00001282  00000-0  28138-4 0  9925
        # 01234567890123456789012345678901234567890123456789012345678901234567890
        #      1         2         3         4         5         6         7
        # Field 0 (1): Line number
        # Field 2 (25544): Satellite number
        # Field 3 (U): Classification
        # Field 4 (98067A): International designator
        # Field 5 (21275.51473713): Epoch year and day
        # Field 6 (.00001282): First derivative of mean motion
        # Field 7 (00000-0): Second derivative of mean motion
        # Field 8 (28138-4): BSTAR drag term
        # Field 9 (0): Element set type
        # Field 10 (9925): Element number
        # Field 11 ( ): Checksum (optional)

        # Extract fields using fixed widths
        line_num = int(line1[0:1])
        satellite_number = int(line1[2:7])
        classification = line1[7:8]
        international_designator = line1[9:17].strip()
        epoch_year = int(line1[18:20])
        epoch_day = float(line1[20:32])
        first_derivative_mean_motion = TLEParser._parse_sgp4_float(line1[33:43])
        second_derivative_mean_motion = TLEParser._parse_sgp4_float(line1[44:52])
        bstar_drag_term = TLEParser._parse_sgp4_float(line1[53:61])
        element_set_type = line1[62:63]
        element_number = int(line1[64:68])

        return (
            line_num, satellite_number, classification, international_designator,
            epoch_year, epoch_day, first_derivative_mean_motion,
            second_derivative_mean_motion, bstar_drag_term, element_set_type,
            element_number
        )

    @staticmethod
    def parse_line2(line2: str) -> Tuple:
        """Parse TLE line 2."""
        # Line 2 format:
        # 2 25544  51.6439 211.2001 0007416  82.7281 135.4221 15.49105483281166
        # 01234567890123456789012345678901234567890123456789012345678901234567890
        #      1         2         3         4         5         6         7
        # Field 0 (2): Line number
        # Field 1 (25544): Satellite number
        # Field 2 (51.6439): Inclination
        # Field 3 (211.2001): Right ascension of ascending node
        # Field 4 (0007416): Eccentricity
        # Field 5 (82.7281): Argument of perigee
        # Field 6 (135.4221): Mean anomaly
        # Field 7 (15.49105483281166): Mean motion
        # Field 8 ( ): Checksum (optional)

        line_num = int(line2[0:1])
        satellite_number = int(line2[2:7])
        inclination = float(line2[8:16])
        right_ascension = float(line2[17:25])
        eccentricity = TLEParser._parse_sgp4_float(line2[26:33])
        argument_of_perigee = float(line2[34:42])
        mean_anomaly = float(line2[43:51])
        mean_motion = float(line2[52:63])

        return (
            line_num, satellite_number, inclination, right_ascension,
            eccentricity, argument_of_perigee, mean_anomaly, mean_motion
        )

    @staticmethod
    def _parse_sgp4_float(field: str) -> float:
        """Parse SGP4 format floating point field (e.g., ' 00000-0', ' 28138-4', '-12345-6')."""
        s = field.strip()
        if not s:
            return 0.0
        try:
            return float(s)
        except ValueError:
            pass

        # SGP4 format: implied decimal point before mantissa digits
        # e.g., '28138-4' -> 0.28138e-4, '-12345-6' -> -0.12345e-6
        match = re.match(r'^([+-]?)(\d+)([+-]\d+)$', s)
        if match:
            sign_str, mantissa_str, exp_str = match.groups()
            sign = -1.0 if sign_str == '-' else 1.0
            mantissa = float('0.' + mantissa_str)
            exp = int(exp_str)
            return sign * mantissa * (10 ** exp)

        return 0.0

    @classmethod
    def parse_tle_lines(cls, line1: str, line2: str) -> Optional[TLEData]:
        """Parse two TLE lines into a TLEData object."""
        try:
            # Validate line numbers
            if not line1.startswith('1 ') or not line2.startswith('2 '):
                logger.warning("Invalid TLE line prefixes")
                return None

            # Parse line 1
            l1_parsed = cls.parse_line1(line1)
            if l1_parsed[0] != 1:  # Line number check
                logger.warning(f"Invalid line 1 number: {l1_parsed[0]}")
                return None

            # Parse line 2
            l2_parsed = cls.parse_line2(line2)
            if l2_parsed[0] != 2:  # Line number check
                logger.warning(f"Invalid line 2 number: {l2_parsed[0]}")
                return None

            # Check satellite numbers match
            if l1_parsed[1] != l2_parsed[1]:  # Satellite numbers
                logger.warning(f"Mismatched satellite numbers: {l1_parsed[1]} vs {l2_parsed[1]}")
                return None

            # Extract parsed values
            (
                _, satellite_number, classification, international_designator,
                epoch_year, epoch_day, first_derivative_mean_motion,
                second_derivative_mean_motion, bstar_drag_term, element_set_type,
                element_number
            ) = l1_parsed

            (
                _, _, inclination, right_ascension, eccentricity,
                argument_of_perigee, mean_anomaly, mean_motion
            ) = l2_parsed

            # Create TLEData object
            tle_data = TLEData(
                satellite_number=satellite_number,
                designation=international_designator,  # Using international designator as designation
                classification=classification,
                international_designator=international_designator,
                epoch_year=epoch_year,
                epoch_day=epoch_day,
                first_derivative_mean_motion=first_derivative_mean_motion,
                second_derivative_mean_motion=second_derivative_mean_motion,
                bstar_drag_term=bstar_drag_term,
                element_set_type=element_set_type,
                element_number=element_number,
                inclination=inclination,
                right_ascension=right_ascension,
                eccentricity=eccentricity,
                argument_of_perigee=argument_of_perigee,
                mean_anomaly=mean_anomaly,
                mean_motion=mean_motion,
                mean_motion_dot=0.0,  # Not directly in TLE, would need derivative calculations
                mean_motion_ddot=0.0,  # Not directly in TLE
                revolution_number=0,  # Not in standard TLE
                line1=line1.strip(),
                line2=line2.strip()
            )

            # Create SGP4 satellite record
            try:
                satrec = Satrec.twoline2rv(line1.strip(), line2.strip())
                tle_data.satrec = satrec
            except Exception as e:
                logger.error(f"Failed to create SGP4 record for satellite {satellite_number}: {e}")

            return tle_data

        except Exception as e:
            logger.error(f"Error parsing TLE lines: {e}")
            logger.debug(f"Line 1: {line1}")
            logger.debug(f"Line 2: {line2}")
            return None


_GLOBAL_TLE_CACHE: dict = {}


class TLEDataIngestion:
    """Main class for ingesting TLE data from files."""

    def __init__(self, data_dir: str = "data/raw"):
        """
        Initialize TLE data ingestion.

        Args:
            data_dir: Directory containing TLE files
        """
        self.data_dir = data_dir
        self.logger = logging.getLogger(__name__)
        self._tle_cache: dict = {}  # Cache for loaded TLE data

    def load_tle_file(self, filename: str) -> List[TLEData]:
        """
        Load TLE data from a single file.

        Args:
            filename: Name of TLE file in data_dir

        Returns:
            List of TLEData objects
        """
        filepath = os.path.join(self.data_dir, filename)
        tle_objects = []

        if not os.path.exists(filepath):
            self.logger.warning(f"TLE file not found: {filepath}")
            return tle_objects

        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()

            clean_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith('#')]
            current_name = ""
            i = 0
            max_sats = 20
            while i < len(clean_lines) and len(tle_objects) < max_sats:
                line = clean_lines[i]
                if line.startswith('1 ') and i + 1 < len(clean_lines):
                    line2 = clean_lines[i + 1]
                    if line2.startswith('2 '):
                        tle_data = TLEParser.parse_tle_lines(line, line2)
                        if tle_data:
                            if current_name:
                                tle_data.designation = current_name
                            tle_objects.append(tle_data)
                            current_name = ""
                        i += 2
                        continue
                else:
                    current_name = line
                i += 1

            self.logger.info(f"Loaded {len(tle_objects)} TLE objects from {filename}")

        except Exception as e:
            self.logger.error(f"Error reading TLE file {filepath}: {e}")

        return tle_objects

    def load_all_tle_files(self) -> List[TLEData]:
        """
        Load TLE data from all files in data_dir.

        Returns:
            List of all TLEData objects from all files
        """
        global _GLOBAL_TLE_CACHE
        if _GLOBAL_TLE_CACHE:
            return list(_GLOBAL_TLE_CACHE.values())
        if self._tle_cache:
            return list(self._tle_cache.values())

        all_tle_objects = []

        if not os.path.exists(self.data_dir):
            self.logger.warning(f"TLE data directory not found: {self.data_dir}")
            os.makedirs(self.data_dir, exist_ok=True)
            return all_tle_objects

        try:
            files = [f for f in os.listdir(self.data_dir)
                    if f.endswith(('.tle', '.txt')) or f in ['tle', 'latest.tle']]

            if not files:
                return all_tle_objects

            for filename in files:
                tle_objects = self.load_tle_file(filename)
                all_tle_objects.extend(tle_objects)

            _GLOBAL_TLE_CACHE = {tle.satellite_number: tle for tle in all_tle_objects}
            self._tle_cache = _GLOBAL_TLE_CACHE
            self.logger.info(f"Total TLE objects loaded: {len(all_tle_objects)}")

        except Exception as e:
            self.logger.error(f"Error scanning TLE directory {self.data_dir}: {e}")

        return all_tle_objects

    def get_tle_by_satellite_number(self, satellite_number: int) -> Optional[TLEData]:
        """
        Get TLE data for a specific satellite number.

        Args:
            satellite_number: NORAD satellite number

        Returns:
            TLEData object or None if not found
        """
        # Load all TLE data if not cached
        if not self._tle_cache:
            tle_objects = self.load_all_tle_files()
            self._tle_cache = {tle.satellite_number: tle for tle in tle_objects}

        return self._tle_cache.get(satellite_number)

    def get_tle_count(self) -> int:
        """Get the number of TLE objects loaded."""
        if not self._tle_cache:
            self.load_all_tle_files()
        return len(self._tle_cache)

    def clear_cache(self):
        """Clear the TLE cache."""
        self._tle_cache.clear()


def load_sample_tles() -> List[TLEData]:
    """
    Convenience function to load sample TLE data.
    Used for testing and demonstrations.

    Returns:
        List of TLEData objects
    """
    ingestion = TLEDataIngestion()
    return ingestion.load_all_tle_files()


def load_tle_from_string(tle_string: str) -> Optional[TLEData]:
    """
    Load TLE data from a string containing exactly two TLE lines.

    Args:
        tle_string: String containing two TLE lines separated by newline

    Returns:
        TLEData object or None if parsing failed
    """
    lines = tle_string.strip().split('\n')
    if len(lines) >= 2:
        line1 = lines[0].strip()
        line2 = lines[1].strip()
        return TLEParser.parse_tle_lines(line1, line2)
    return None


if __name__ == "__main__":
    # Example usage and testing
    logging.basicConfig(level=logging.INFO)

    logger.info("TLE Data Ingestion Module")
    logger.info("=" * 40)

    # Test with sample data if available
    tle_objects = load_sample_tles()

    if tle_objects:
        logger.info(f"Successfully loaded {len(tle_objects)} TLE objects")

        # Show first few objects
        for i, tle in enumerate(tle_objects[:3]):
            logger.info(f"Satellite {tle.satellite_number}: {tle.designation}")
            logger.info(f"  Epoch: {tle.epoch}")
            logger.info(f"  Inclination: {tle.inclination}°")
            logger.info(f"  RAAN: {tle.right_ascension}°")
            logger.info(f"  Eccentricity: {tle.eccentricity}")
            logger.info(f"  Mean Motion: {tle.mean_motion} orbits/day")
            if tle.satrec:
                logger.info(f"  SGP4 Record: Created successfully")
            else:
                logger.info(f"  SGP4 Record: Failed to create")
            logger.info("")
    else:
        logger.info("No TLE objects loaded. Place TLE files in data/raw/ directory.")
        logger.info("TLE files should contain pairs of lines like:")
        logger.info("1 25544U 98067A   21275.51473713  .00001282  00000-0  28138-4 0  9925")
        logger.info("2 25544  51.6439 211.2001 0007416  82.7281 135.4221 15.49105483281166")