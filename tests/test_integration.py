"""
Integration test for ORBITGUARD AI core modules.
Tests the workflow from TLE ingestion to propagation to conjunction detection.
"""

import sys
import os
import io
from datetime import datetime, timedelta, timezone
import logging
import numpy as np

# Ensure UTF-8 output on Windows safely without closing stream
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app.core.data_ingestion import TLEData, TLEParser, load_tle_from_string
from app.core.propagation import propagate_single_tle, OrbitalPropagator
from app.core.conjunction import ConjunctionDetector, ConjunctionResult


def test_tle_ingestion():
    """Test TLE data ingestion."""
    print("Testing TLE data ingestion...")

    tle_string = """1 25544U 98067A   21275.51473713  .00001282  00000-0  28138-4 0  9925
2 25544  51.6439 211.2001 0007416  82.7281 135.4221 15.49105483281166"""

    tle_data = load_tle_from_string(tle_string)

    assert tle_data is not None, "Failed to parse TLE string"
    assert tle_data.satellite_number == 25544
    assert tle_data.designation == "98067A"
    assert tle_data.inclination == 51.6439
    assert tle_data.satrec is not None, "Failed to create SGP4 record"

    print(f"✅ Parsed TLE for satellite {tle_data.satellite_number}")
    print(f"   Designation: {tle_data.designation}")
    print(f"   Epoch: {tle_data.epoch}")
    print(f"   Inclination: {tle_data.inclination}°")
    print(f"   Mean Motion: {tle_data.mean_motion} orbits/day")
    print("✅ SGP4 record created successfully")
    return True


def test_propagation():
    """Test orbital propagation."""
    print("\nTesting orbital propagation...")

    tle_string = """1 25544U 98067A   21275.51473713  .00001282  00000-0  28138-4 0  9925
2 25544  51.6439 211.2001 0007416  82.7281 135.4221 15.49105483281166"""

    tle_data = load_tle_from_string(tle_string)
    assert tle_data is not None, "Could not parse TLE string"

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    position = propagate_single_tle(tle_data, now)

    assert position is not None, "Propagation returned None"
    print(f"✅ Propagated position at {now}:")
    print(f"   [{position[0]:.2f}, {position[1]:.2f}, {position[2]:.2f}] km")

    propagator = OrbitalPropagator()
    start_time = now
    end_time = now + timedelta(hours=1)
    time_step = timedelta(minutes=15)

    timestamps, positions = propagator.propagate_multiple_times(
        tle_data.satrec, start_time, end_time, time_step
    )

    assert len(timestamps) > 0 and len(positions) > 0, "No positions generated for time range"
    print(f"✅ Propagated over {len(timestamps)} time steps")
    print(f"   First position: [{positions[0][0]:.2f}, {positions[0][1]:.2f}, {positions[0][2]:.2f}] km")
    print(f"   Last position:  [{positions[-1][0]:.2f}, {positions[-1][1]:.2f}, {positions[-1][2]:.2f}] km")

    return True


def test_conjunction_detection():
    """Test conjunction detection with mock data."""
    print("\nTesting conjunction detection...")

    detector = ConjunctionDetector(miss_distance_threshold=5.0)

    pos1 = np.array([0.0, 0.0, 0.0])  # km
    pos2 = np.array([3.0, 4.0, 0.0])  # km (5km away)
    time_now = datetime.now(timezone.utc).replace(tzinfo=None)

    conjunction = ConjunctionResult(
        satellite1_id=1,
        satellite2_id=2,
        tca=time_now,
        miss_distance=5.0,
        position1=pos1,
        position2=pos2
    )

    print(f"✅ Created conjunction result: {conjunction}")

    distance = np.linalg.norm(pos1 - pos2)
    assert abs(distance - 5.0) < 1e-3
    print(f"✅ Calculated distance: {distance:.2f} km")

    positions = {1: np.array([pos1]), 2: np.array([pos2])}
    timestamps = [time_now]

    conjunctions = detector.find_conjunctions_in_timeframe(positions, timestamps)
    assert len(conjunctions) > 0, "Detector did not find the conjunction"

    print(f"✅ Detector found {len(conjunctions)} conjunction(s)")
    return True


def test_full_workflow():
    """Test a simplified full workflow."""
    print("\nTesting simplified full workflow...")

    tle_string_iss = """1 25544U 98067A   21275.51473713  .00001282  00000-0  28138-4 0  9925
2 25544  51.6439 211.2001 0007416  82.7281 135.4221 15.49105483281166"""

    tle_string_close = """1 25545U 98067B   21275.51473713  .00001282  00000-0  28138-4 0  9926
2 25545  51.6439 211.2001 0007416  82.7281 135.4221 15.49105483281166"""

    tle_iss = load_tle_from_string(tle_string_iss)
    tle_close = load_tle_from_string(tle_string_close)

    assert tle_iss is not None and tle_close is not None, "Could not parse TLE strings"

    print(f"✅ Loaded TLE for ISS (sat {tle_iss.satellite_number})")
    print(f"✅ Loaded TLE for close satellite (sat {tle_close.satellite_number})")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    pos_iss = propagate_single_tle(tle_iss, now)
    pos_close = propagate_single_tle(tle_close, now)

    assert pos_iss is not None and pos_close is not None, "Propagation failed"

    print(f"✅ ISS position at {now}: [{pos_iss[0]:.2f}, {pos_iss[1]:.2f}, {pos_iss[2]:.2f}] km")
    print(f"✅ Close satellite position at {now}: [{pos_close[0]:.2f}, {pos_close[1]:.2f}, {pos_close[2]:.2f}] km")

    distance = np.linalg.norm(pos_iss - pos_close)
    print(f"✅ Distance between satellites: {distance:.2f} km")

    detector = ConjunctionDetector(miss_distance_threshold=10.0)

    positions = {
        tle_iss.satellite_number: np.array([pos_iss]),
        tle_close.satellite_number: np.array([pos_close])
    }
    timestamps = [now]

    conjunctions = detector.find_conjunctions_in_timeframe(positions, timestamps)
    assert len(conjunctions) > 0, "No conjunctions found"

    print(f"✅ Conjunction detection found {len(conjunctions)} conjunction(s)")
    conj = conjunctions[0]
    print(f"   Closest approach: {conj.miss_distance:.2f} km at {conj.tca}")

    return True


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("ORBITGUARD AI Integration Test")
    print("=" * 60)

    logging.basicConfig(level=logging.WARNING)

    tests = [
        test_tle_ingestion,
        test_propagation,
        test_conjunction_detection,
        test_full_workflow
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ FAILED {test.__name__}: {e}")
        print()

    print("=" * 60)
    print(f"Integration Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! The integration is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())