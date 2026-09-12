"""Unit tests for app.core.data_ingestion."""

import pytest
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from app.core.data_ingestion import TLEParser, load_tle_from_string, TLEData


SAMPLE_ISS_TLE = """1 25544U 98067A   21275.51473713  .00001282  00000-0  28138-4 0  9925
2 25544  51.6439 211.2001 0007416  82.7281 135.4221 15.49105483281166"""


def test_parse_sgp4_float():
    assert TLEParser._parse_sgp4_float(" 00000-0") == 0.0
    assert abs(TLEParser._parse_sgp4_float(" 28138-4") - 2.8138e-5) < 1e-9
    assert abs(TLEParser._parse_sgp4_float("-12345-6") - (-1.2345e-7)) < 1e-11


def test_load_tle_from_string():
    tle = load_tle_from_string(SAMPLE_ISS_TLE)
    assert tle is not None
    assert tle.satellite_number == 25544
    assert tle.designation == "98067A"
    assert tle.inclination == 51.6439
    assert tle.satrec is not None
