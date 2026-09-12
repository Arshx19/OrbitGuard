"""
Integration test for ORBITGUARD AI core modules.
Tests the workflow from TLE ingestion to propagation to conjunction detection.
"""

import sys
import os
import io
from datetime import datetime, timedelta
import logging

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_tle_ingestion():
    """Test TLE data ingestion."""
    print("Testing TLE data ingestion...")

    try:
        from app.core.data_ingestion import TLEDataIngestion, load_tle_from_string

        # Test with sample TLE string (ISS)
        tle_string = """1 25544U 98067A   21275.51473713  .00001282  00000-0  28138-4 0  9925
2 25544  51.6439 211.2001 0007416  82.7281 135.4221 15.49105483281166"""

        tle_data = load_tle_from_string(tle_string)

        if tle_data is None:
            print("❌ FAILED: Could not parse TLE string")
            return False

        print(f"✅ Parsed TLE for satellite {tle_data.satellite_number}")
        print(f"   Designation: {tle_data.designation}")
        print(f"   Epoch: {tle_data.epoch}")
        print(f"   Inclination: {tle_data.inclination}°")
        print(f"   Mean Motion: {tle_data.mean_motion} orbits/day")

        # Test that we can create SGP4 record
        if tle_data.satrec is None:
            print("❌ FAILED: Could not create SGP4 record")
            return False

        print("✅ SGP4 record created successfully")
        return True

    except Exception as e:
        print(f"❌ FAILED: Error in TLE ingestion: {e}")
        return False


def test_propagation():
    """Test orbital propagation."""
    print("\nTesting orbital propagation...")

    try:
        from app.core.data_ingestion import load_tle_from_string
        from app.core.propagation import propagate_single_tle, OrbitalPropagator

        # Test with sample TLE string (ISS)
        tle_string = """1 25544U 98067A   21275.51473713  .00001282  00000-0  28138-4 0  9925
2 25544  51.6439 211.2001 0007416  82.7281 135.4221 15.49105483281166"""

        tle_data = load_tle_from_string(tle_string)
        if tle_data is None:
            print("❌ FAILED: Could not parse TLE string")
            return False

        # Propagate to current time
        now = datetime.utcnow()
        position = propagate_single_tle(tle_data, now)

        if position is None:
            print("❌ FAILED: Propagation returned None")
            return False

        print(f"✅ Propagated position at {now}:")
        print(f"   [{position[0]:.2f}, {position[1]:.2f}, {position[2]:.2f}] km")

        # Test multiple time propagation
        propagator = OrbitalPropagator()
        start_time = now
        end_time = now + timedelta(hours=1)
        time_step = timedelta(minutes=15)

        timestamps, positions = propagator.propagate_multiple_times(
            tle_data.satrec, start_time, end_time, time_step
        )

        if len(timestamps) == 0 or len(positions) == 0:
            print("❌ FAILED: No positions generated for time range")
            return False

        print(f"✅ Propagated over {len(timestamps)} time steps")
        print(f"   First position: [{positions[0][0]:.2f}, {positions[0][1]:.2f}, {positions[0][2]:.2f}] km")
        print(f"   Last position:  [{positions[-1][0]:.2f}, {positions[-1][1]:.2f}, {positions[-1][2]:.2f}] km")

        return True

    except Exception as e:
        print(f"❌ FAILED: Error in propagation: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_conjunction_detection():
    """Test conjunction detection with mock data."""
    print("\nTesting conjunction detection...")

    try:
        from app.core.conjunction import ConjunctionDetector, ConjunctionResult
        import numpy as np

        # Create detector with 5km threshold
        detector = ConjunctionDetector(miss_distance_threshold=5.0)

        # Create mock positions for two satellites that are close
        pos1 = np.array([0.0, 0.0, 0.0])  # km
        pos2 = np.array([3.0, 4.0, 0.0])  # km (5km away)
        time_now = datetime.utcnow()

        # Test conjunction detection
        conjunction = ConjunctionResult(
            satellite1_id=1,
            satellite2_id=2,
            tca=time_now,
            miss_distance=5.0,
            position1=pos1,
            position2=pos2
        )

        print(f"✅ Created conjunction result: {conjunction}")

        # Test distance calculation
        distance = np.linalg.norm(pos1 - pos2)
        print(f"✅ Calculated distance: {distance:.2f} km")

        # Test that our detector would find this conjunction
        positions = {1: np.array([pos1]), 2: np.array([pos2])}
        timestamps = [time_now]

        conjunctions = detector.find_conjunctions_in_timeframe(positions, timestamps)

        if len(conjunctions) == 0:
            print("❌ FAILED: Detector did not find the conjunction")
            return False

        print(f"✅ Detector found {len(conjunctions)} conjunction(s)")
        return True

    except Exception as e:
        print(f"❌ FAILED: Error in conjunction detection: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_workflow():
    """Test a simplified full workflow."""
    print("\nTesting simplified full workflow...")

    try:
        from app.core.data_ingestion import load_tle_from_string
        from app.core.propagation import propagate_single_tle
        from app.core.conjunction import ConjunctionDetector
        import numpy as np

        # Load two TLEs (ISS and a mock satellite close to it)
        tle_string_iss = """1 25544U 98067A   21275.51473713  .00001282  00000-0  28138-4 0  9925
2 25544  51.6439 211.2001 0007416  82.7281 135.4221 15.49105483281166"""

        # Create a second TLE for a satellite very close to ISS (same orbit, slightly different position)
        tle_string_close = """1 25545U 98067B   21275.51473713  .00001282  00000-0  28138-4 0  9926
2 25545  51.6439 211.2001 0007416  82.7281 135.4221 15.49105483281166"""

        tle_iss = load_tle_from_string(tle_string_iss)
        tle_close = load_tle_from_string(tle_string_close)

        if tle_iss is None or tle_close is None:
            print("❌ FAILED: Could not parse TLE strings")
            return False

        print(f"✅ Loaded TLE for ISS (sat {tle_iss.satellite_number})")
        print(f"✅ Loaded TLE for close satellite (sat {tle_close.satellite_number})")

        # Propagate both to current time
        now = datetime.utcnow()
        pos_iss = propagate_single_tle(tle_iss, now)
        pos_close = propagate_single_tle(tle_close, now)

        if pos_iss is None or pos_close is None:
            print("❌ FAILED: Propagation failed for one or both satellites")
            return False

        print(f"✅ ISS position at {now}: [{pos_iss[0]:.2f}, {pos_iss[1]:.2f}, {pos_iss[2]:.2f}] km")
        print(f"✅ Close satellite position at {now}: [{pos_close[0]:.2f}, {pos_close[1]:.2f}, {pos_close[2]:.2f}] km")

        # Calculate distance between them
        distance = np.linalg.norm(pos_iss - pos_close)
        print(f"✅ Distance between satellites: {distance:.2f} km")

        # Test conjunction detection
        detector = ConjunctionDetector(miss_distance_threshold=10.0)  # 10km threshold

        positions = {
            tle_iss.satellite_number: np.array([pos_iss]),
            tle_close.satellite_number: np.array([pos_close])
        }
        timestamps = [now]

        conjunctions = detector.find_conjunctions_in_timeframe(positions, timestamps)

        print(f"✅ Conjunction detection found {len(conjunctions)} conjunction(s)")

        if len(conjunctions) > 0:
            conj = conjunctions[0]
            print(f"   Closest approach: {conj.miss_distance:.2f} km at {conj.tca}")

        return True

    except Exception as e:
        print(f"❌ FAILED: Error in full workflow: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("ORBITGUARD AI Integration Test")
    print("=" * 60)

    # Configure logging
    logging.basicConfig(level=logging.WARNING)  # Reduce noise

    tests = [
        test_tle_ingestion,
        test_propagation,
        test_conjunction_detection,
        test_full_workflow
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()  # Add space between tests

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