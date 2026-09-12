"""
TLE (Two-Line Element) Data Loader for ORBITGUARD AI
Handles loading and parsing of TLE data from various sources
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

@dataclass
class Satellite:
    """Represents a satellite with orbital elements from TLE data"""
    # Identifiers
    norad_id: int
    name: str
    international_designator: str

    # Orbital Elements (from TLE line 1)
    epoch_year: int
    epoch_day: float  # Day of year with fractional portion
    epoch: datetime   # Computed epoch datetime

    # Orbital Elements (from TLE line 2)
    inclination: float          # degrees
    raan: float                 # Right Ascension of Ascending Node (degrees)
    eccentricity: float         # (unitless, leading decimal point assumed)
    arg_perigee: float          # Argument of Perigee (degrees)
    mean_anomaly: float         # Mean Anomaly (degrees)
    mean_motion: float          # Revolutions per day

    # Additional metadata
    ephemeris_type: int = 0
    element_set_number: int = 0
    revolution_number_at_epoch: int = 0
    bstar: float = 0.0          # Drag coefficient (/earth radii)
    mean_motion_dot: float = 0.0 # First derivative of mean motion (/day^2)
    mean_motion_ddot: float = 0.0 # Second derivative of mean motion (/day^3)

    def __post_init__(self):
        """Compute epoch datetime from year and day"""
        # Handle YYXXX format where YY is year with implied century
        year = self.epoch_year
        if year < 57:
            year += 2000
        else:
            year += 1900

        # Convert day of year to month/day
        day_int = int(self.epoch_day)
        day_fraction = self.epoch_day - day_int

        # Create datetime for Jan 1 of the year, then add days
        try:
            self.epoch = datetime(year, 1, 1) + \
                        timedelta(days=day_int - 1, seconds=day_fraction * 86400)
        except Exception as e:
            logger.warning(f"Could not compute epoch for satellite {self.norad_id}: {e}")
            self.epoch = datetime(year, 1, 1)

@dataclass
class TLEData:
    """Container for TLE data (2 or 3 lines)"""
    line1: str
    line2: str
    line3: Optional[str] = None  # Optional for 3-line TLE

    @property
    def is_three_line(self) -> bool:
        return self.line3 is not None and len(self.line3.strip()) > 0

class TLEParseError(Exception):
    """Exception raised when TLE parsing fails"""
    pass

class TLELoader:
    """Loads and parses TLE data from files or strings"""

    @staticmethod
    def parse_tle_line1(line: str) -> dict:
        """
        Parse TLE line 1 format:
        AAAAAAAAAA  NNNNNU  NNNNAAA  NNNNN.NNNNNNNN  .NNNNNNNN  +NNNNNNN  +  NNNNN-N  +  NNNNN-N  N  NNNNN
        0123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890

        Field indices (0-based, inclusive):
        00-01: Line Number (1)
        02-07: Satellite Number
        08-08: Elset Classification
        09-11: International Designator (last 2 digits of launch year)
        12-14: International Designator (launch number of year)
        15-17: International Designator (piece of launch)
        18-31: Epoch (YYDD.DDDDDDDD)
        32-32: FirstDerivative of Mean Motion Sign
        33-35: FirstDerivative of Mean Motion Magnitude
        36-36: FirstDerivative of Mean Motion Exponent Sign
        37-37: FirstDerivative of Mean Motion Exponent Magnitude
        38-38: SecondDerivative of Mean Motion Sign
        39-41: SecondDerivative of Mean Motion Magnitude
        42-42: SecondDerivative of Mean Motion Exponent Sign
        43-43: SecondDerivative of Mean Motion Exponent Magnitude
        44-44: BSTAR Drag Sign
        45-48: BSTAR Drag Magnitude
        49-49: BSTAR Drag Exponent Sign
        50-50: BSTAR Drag Exponent Magnitude
        51-51: Ephemeris Type
        52-53: Element Number
        54-58: Checksum (Modulo 10)
        """
        if len(line) < 69:
            raise TLEParseError(f"TLE line 1 too short: {len(line)} characters")

        if line[0] != '1':
            raise TLEParseError(f"TLE line 1 must start with '1', got '{line[0]}'")

        try:
            # Extract fields using fixed-width parsing
            norad_id = int(line[2:7].strip())
            classification = line[7:8].strip()

            # International Designator: YYYYNNNXXXXX
            # YY = last 2 digits of launch year
            # NNN = launch number of the year
            # XXX = piece of the launch
            intl_desig = line[9:17].strip()

            # Epoch: YYDD.DDDDDDDD
            epoch_str = line[18:32].strip()
            epoch_year = int(epoch_str[0:2])
            epoch_day = float(epoch_str[2:])

            # First Derivative of Mean Motion
            mean_motion_dot_sign = 1 if line[33] == '+' else -1
            mean_motion_dot_mag = float(line[34:36]) / 100000.0  # Actually scaled
            mean_motion_dot_exp_sign = 1 if line[36] == '+' else -1
            mean_motion_dot_exp = int(line[37])
            mean_motion_dot = mean_motion_dot_sign * mean_motion_dot_mag * (10 ** mean_motion_dot_exp)

            # Second Derivative of Mean Motion
            mean_motion_ddot_sign = 1 if line[38] == '+' else -1
            mean_motion_ddot_mag = float(line[39:41]) / 10000.0  # Actually scaled
            mean_motion_ddot_exp_sign = 1 if line[41] == '+' else -1
            mean_motion_ddot_exp = int(line[42])
            mean_motion_ddot = mean_motion_ddot_sign * mean_motion_ddot_mag * (10 ** mean_motion_ddot_exp)

            # BSTAR Drag Term
            bstar_sign = 1 if line[44] == '+' else -1
            bstar_mag = float(line[45:48]) / 10000.0  # Actually scaled
            bstar_exp_sign = 1 if line[48] == '+' else -1
            bstar_exp = int(line[49])
            bstar = bstar_sign * bstar_mag * (10 ** bstar_exp)

            ephemeris_type = int(line[50])
            element_set_number = int(line[51:53])

            return {
                'norad_id': norad_id,
                'classification': classification,
                'international_designator': intl_desig,
                'epoch_year': epoch_year,
                'epoch_day': epoch_day,
                'mean_motion_dot': mean_motion_dot,
                'mean_motion_ddot': mean_motion_ddot,
                'bstar': bstar,
                'ephemeris_type': ephemeris_type,
                'element_set_number': element_set_number
            }

        except (ValueError, IndexError) as e:
            raise TLEParseError(f"Error parsing TLE line 1: {e}")

    @staticmethod
    def parse_tle_line2(line: str) -> dict:
        """
        Parse TLE line 2 format:
        NNNNN NNN.NNNNNNN NNN.NNNNNNN NNNNNNN NNN.NNNNN NNN.NNNNN NNN.NNNNNN NNNNNNNN
        012345678901234567890123456789012345678901234567890123456789012345678901234567890

        Field indices:
        00-01: Line Number (2)
        02-07: Satellite Number
        08-15: Inclination (degrees)
        16-24: Right Ascension of Ascending Node (degrees)
        25-31: Eccentricity (decimal point assumed)
        32-39: Argument of Perigee (degrees)
        40-47: Mean Anomaly (degrees)
        48-52: Mean Motion (revs/day)
        53-56: Revolution number at epoch
        57-68: Checksum (Modulo 10)
        """
        if len(line) < 69:
            raise TLEParseError(f"TLE line 2 too short: {len(line)} characters")

        if line[0] != '2':
            raise TLEParseError(f"TLE line 2 must start with '2', got '{line[0]}'")

        try:
            norad_id = int(line[2:7].strip())
            inclination = float(line[8:16])
            raan = float(line[17:25])

            # Eccentricity: decimal point assumed at column 25
            ecc_str = line[26:33].strip()
            if not ecc_str:
                raise TLEParseError("Empty eccentricity field")
            eccentricity = float("0." + ecc_str)  # Add leading "0."

            arg_perigee = float(line[34:42])
            mean_anomaly = float(line[43:51])
            mean_motion = float(line[52:63])
            revolution_number_at_epoch = int(line[63:68])

            return {
                'norad_id': norad_id,
                'inclination': inclination,
                'raan': raan,
                'eccentricity': eccentricity,
                'arg_perigee': arg_perigee,
                'mean_anomaly': mean_anomaly,
                'mean_motion': mean_motion,
                'revolution_number_at_epoch': revolution_number_at_epoch
            }

        except (ValueError, IndexError) as e:
            raise TLEParseError(f"Error parsing TLE line 2: {e}")

    @staticmethod
    def parse_tle_line3(line: str) -> dict:
        """
        Parse TLE line 3 (optional) format:
        NNNNN AAAAAAAAA A AAAAAAAAA A 00000-0 0  0000
        01234567890123456789012345678901234567890123456789012345678901234567890

        Field indices:
        00-01: Line Number (3)
        02-07: Satellite Number
        08-15: Ephemeris Type (not used, usually blank)
        16-23: Blank
        24-31: Right Ascension at Ephemeris Time (degrees)
        32-38: Blank
        39-46: Declination at Ephemeris Time (degrees)
        47-49: BSTAR Exponent/Tag
        50-50: Blank
        51-52: Blank
        53-56: Blank
        57-62: Blank
        63-68: Blank
        69-??: Checksum? (varies)
        """
        # Line 3 is often not used for basic orbital mechanics
        # For now, we'll just validate the satellite number matches
        if len(line) < 69:
            raise TLEParseError(f"TLE line 3 too short: {len(line)} characters")

        if line[0] != '3':
            raise TLEParseError(f"TLE line 3 must start with '3', got '{line[0]}'")

        try:
            norad_id = int(line[2:7].strip())
            # Additional data could be parsed here if needed for advanced applications
            return {
                'norad_id': norad_id
                # Other fields from line 3 are typically not needed for basic propagation
            }
        except (ValueError, IndexError) as e:
            raise TLEParseError(f"Error parsing TLE line 3: {e}")

    @classmethod
    def parse_tle(cls, line1: str, line2: str, line3: Optional[str] = None) -> Satellite:
        """
        Parse a complete TLE set (2 or 3 lines) into a Satellite object
        """
        # Validate line numbers match
        if not line1.startswith('1') or not line2.startswith('2'):
            raise TLEParseError("Invalid TLE line identifiers")

        # Parse both lines
        data1 = cls.parse_tle_line1(line1)
        data2 = cls.parse_tle_line2(line2)

        # Verify NORAD IDs match
        if data1['norad_id'] != data2['norad_id']:
            raise TLEParseError(
                f"NORAD ID mismatch: line1={data1['norad_id']}, line2={data2['norad_id']}"
            )

        norad_id = data1['norad_id']

        # Parse line 3 if provided
        if line3:
            data3 = cls.parse_tle_line3(line3)
            if data3['norad_id'] != norad_id:
                raise TLEParseError(
                    f"NORAD ID mismatch in line 3: expected={norad_id}, got={data3['norad_id']}"
                )
            # Merge line 3 data if needed
            data1.update(data3)

        # Create Satellite object
        satellite = Satellite(
            norad_id=norad_id,
            name="",  # Will be set from file loading context
            international_designator=data1['international_designator'],
            epoch_year=data1['epoch_year'],
            epoch_day=data1['epoch_day'],
            inclination=data2['inclination'],
            raan=data2['raan'],
            eccentricity=data2['eccentricity'],
            arg_perigee=data2['arg_perigee'],
            mean_anomaly=data2['mean_anomaly'],
            mean_motion=data2['mean_motion'],
            ephemeris_type=data1.get('ephemeris_type', 0),
            element_set_number=data1.get('element_set_number', 0),
            revolution_number_at_epoch=data2.get('revolution_number_at_epoch', 0),
            bstar=data1.get('bstar', 0.0),
            mean_motion_dot=data1.get('mean_motion_dot', 0.0),
            mean_motion_ddot=data1.get('mean_motion_ddot', 0.0)
        )

        return satellite

    @classmethod
    def load_tle_from_string(cls, tle_string: str) -> List[Satellite]:
        """
        Load TLE data from a string containing one or more TLE sets
        Handles both 2-line and 3-line TLE formats
        """
        satellites = []
        lines = [line.strip() for line in tle_string.strip().split('\n') if line.strip()]

        i = 0
        while i < len(lines):
            # Look for line 1
            if lines[i].startswith('1'):
                # We have a line 1, look for line 2
                if i + 1 >= len(lines):
                    logger.warning("Incomplete TLE set: missing line 2")
                    break

                if not lines[i + 1].startswith('2'):
                    logger.warning(f"Expected line 2, got: {lines[i + 1][:20]}...")
                    i += 1
                    continue

                # Check if there's a line 3
                line3 = None
                if i + 2 < len(lines) and lines[i + 2].startswith('3'):
                    line3 = lines[i + 2]
                    i += 3  # Skip line 3
                else:
                    i += 2  # Skip line 2

                try:
                    satellite = cls.parse_tle(lines[i - 2 if line3 else i - 1],
                                            lines[i - 1],
                                            line3)
                    satellites.append(satellite)
                except TLEParseError as e:
                    logger.warning(f"Failed to parse TLE set: {e}")
                    # Continue to next potential TLE set
            else:
                i += 1

        return satellites

    @classmethod
    def load_tle_from_file(cls, filepath: str) -> List[Satellite]:
        """
        Load TLE data from a file
        Supports standard TLE file formats (2-line or 3-line per satellite)
        """
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            return cls.load_tle_from_string(content)
        except FileNotFoundError:
            logger.error(f"TLE file not found: {filepath}")
            raise
        except Exception as e:
            logger.error(f"Error reading TLE file {filepath}: {e}")
            raise

    @classmethod
    def load_tle_from_url(cls, url: str) -> List[Satellite]:
        """
        Load TLE data from a URL (requires requests or urllib)
        For now, this is a placeholder - would need to implement actual HTTP fetch
        """
        # Placeholder for URL loading - in practice would use requests or urllib
        logger.warning("URL loading not implemented yet - use load_tle_from_file instead")
        raise NotImplementedError("URL loading not yet implemented")


# Utility functions for validation and verification
def validate_tle_checksum(line: str) -> bool:
    """
    Validate TLE line checksum (modulo 10)
    Returns True if checksum is valid
    """
    if len(line) < 69:
        return False

    # Checksum is last character
    given_checksum = line[-1]

    # Compute checksum: sum of all digits (minus signs count as -1, blanks as 0)
    # Modulo 10 of the sum
    total = 0
    for char in line[0:68]:  # Exclude the checksum character itself
        if char.isdigit():
            total += int(char)
        elif char == '-':
            total -= 1
        # Blanks, letters, +, . all count as 0

    computed_checksum = total % 10
    return str(computed_checksum) == given_checksum


def quick_tle_validation(satellite: Satellite) -> Tuple[bool, List[str]]:
    """
    Perform basic validation on a parsed Satellite object
    Returns (is_valid, list_of_errors)
    """
    errors = []

    # Validate NORAD ID range (typically 1-99999)
    if not (1 <= satellite.norad_id <= 99999):
        errors.append(f"NORAD ID {satellite.norad_id} out of valid range")

    # Validate inclination (0-180 degrees)
    if not (0 <= satellite.inclination <= 180):
        errors.append(f"Inclination {satellite.inclination} out of range [0,180]")

    # Validate RAAN (0-360 degrees)
    if not (0 <= satellite.raan < 360):
        errors.append(f"RAAN {satellite.raan} out of range [0,360)")

    # Validate eccentricity (0 <= e < 1 for elliptical orbits)
    if not (0 <= satellite.eccentricity < 1):
        errors.append(f"Eccentricity {satellite.eccentricity} out of range [0,1)")

    # Validate mean motion (typically > 0 for Earth orbits)
    if satellite.mean_motion <= 0:
        errors.append(f"Mean motion {satellite.mean_motion} must be positive")

    # Validate epoch year (reasonable bounds)
    year = satellite.epoch_year
    if year < 57:  # 2057
        year += 2000
    else:
        year += 1900

    if year < 1957 or year > 2050:
        errors.append(f"Epoch year {year} seems unreasonable")

    return len(errors) == 0, errors


# Example usage and testing
if __name__ == "__main__":
    # Example TLE (ISS - ZARYA)
    # 1 25544U 98067A   24255.51782528  .00016717  00000+0  35226-3 0  9994
    # 2 25544  51.6416 247.4627 0003682  33.9335 315.0876 15.50050725428536

    example_tle_1 = "1 25544U 98067A   24255.51782528  .00016717  00000+0  35226-3 0  9994"
    example_tle_2 = "2 25544  51.6416 247.4627 0003682  33.9335 315.0876 15.50050725428536"

    try:
        sat = TLELoader.parse_tle(example_tle_1, example_tle_2)
        print(f"Parsed satellite: {sat}")
        print(f"Epoch: {sat.epoch}")

        is_valid, errors = quick_tle_validation(sat)
        print(f"Validation: {'PASS' if is_valid else 'FAIL'}")
        if errors:
            print(f"Errors: {errors}")

    except TLEParseError as e:
        print(f"Parse error: {e}")