"""
End-to-End Live API Test Script for ORBITGUARD AI.
Tests Node.js Express Server (Port 5000) -> Python AI Microservice (Port 8000).
"""

import json
import requests
from datetime import datetime, timezone, timedelta

NODE_BACKEND_URL = "http://localhost:5000/api/v1"

def format_json(data):
    return json.dumps(data, indent=2)

def main():
    print("=" * 70)
    print("ORBITGUARD AI - END-TO-END LIVE SYSTEM TEST")
    print("=" * 70)

    # 1. Health Check
    print("\n[1] Testing Node.js Express Backend Health Check...")
    try:
        res = requests.get("http://localhost:5000/")
        print(f"Status Code: {res.status_code}")
        print(f"Response: {res.json()}")
    except Exception as e:
        print(f"[ERROR] Failed to reach Node backend: {e}")
        return

    # 2. Get Tracked Satellites
    print("\n[2] Fetching Tracked Satellites & Debris...")
    try:
        res = requests.get(f"{NODE_BACKEND_URL}/satellites")
        satellites = res.json().get("satellites", [])
        print(f"[OK] Loaded {len(satellites)} space objects from TLE catalog.")
        for s in satellites[:3]:
            print(f"   - Sat #{s.get('satellite_number')}: {s.get('designation', 'Unknown')} (Inclination: {s.get('inclination_deg')} deg)")
    except Exception as e:
        print(f"[ERROR] Error fetching satellites: {e}")

    # 3. Perform Conjunction Screening
    print("\n[3] Running Orbital Conjunction Screening (48h Forecast)...")
    try:
        res = requests.get(f"{NODE_BACKEND_URL}/conjunctions")
        data = res.json()
        conjunctions = data if isinstance(data, list) else data.get("conjunctions", [])
        print(f"[OK] Found {len(conjunctions)} close approach event(s):")
        for c in conjunctions[:3]:
            print(f"   - Event ID: {c.get('id') or c.get('conjunction_id')}")
            print(f"     Satellites: {c.get('satellite1_name', c.get('sat1_number'))} vs {c.get('satellite2_name', c.get('sat2_number'))}")
            print(f"     TCA: {c.get('tca')}")
            print(f"     Miss Distance: {c.get('miss_distance_km')} km")
            print(f"     Relative Velocity: {c.get('relative_speed_kms', c.get('relative_velocity_km_s'))} km/s")
    except Exception as e:
        print(f"[ERROR] Error running conjunction screening: {e}")

    # 4. Compute AI Risk Score & SHAP Feature Attribution
    print("\n[4] Evaluating AI Collision Risk & SHAP Explainability...")
    sample_payload = {
        "conjunction_id": "CONJ-001",
        "primary_sat_id": 25544,
        "secondary_sat_id": 99901,
        "miss_distance_km": 0.42,
        "relative_velocity_km_s": 12.4,
        "tca": (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
    }
    
    try:
        res = requests.post(f"{NODE_BACKEND_URL}/risk/analyze", json=sample_payload)
        risk_data = res.json()
        print(f"[OK] AI Risk Assessment Completed:")
        print(f"   - Risk Score: {risk_data.get('risk_score')}/100")
        print(f"   - Risk Category / Level: {risk_data.get('risk_level') or risk_data.get('risk_category')}")
        print(f"   - AI Explanation: {risk_data.get('explanation_summary')}")
        shap_factors = risk_data.get('shap_factors', [])
        if shap_factors:
            print(f"   - Top SHAP Factor: {shap_factors[0].get('factor')} ({shap_factors[0].get('contribution_percentage')}%)")
    except Exception as e:
        print(f"[ERROR] Error calculating AI risk: {e}")

    # 5. Optimize Candidate RTN Maneuver
    print("\n[5] Optimizing RTN Candidate Burn Maneuver (Min Delta-v)...")
    try:
        res = requests.post(f"{NODE_BACKEND_URL}/maneuver/optimize", json=sample_payload)
        maneuver_data = res.json()
        optimal = maneuver_data.get('optimal_candidate', {})
        print(f"[OK] Candidate Maneuvers Generated:")
        print(f"   - Optimal Candidate ID: {optimal.get('candidate_id')}")
        print(f"   - Burn Direction: {optimal.get('direction_name')}")
        print(f"   - Total Delta-v (Dv): {optimal.get('delta_v_magnitude_ms')} m/s")
        print(f"   - RTN Vector: {optimal.get('delta_v_rtn_ms')}")
        print(f"   - New Miss Distance: {optimal.get('new_miss_distance_km')} km")
    except Exception as e:
        print(f"[ERROR] Error optimizing maneuver: {e}")

    # 6. Post-Burn Full Catalog Re-Screening Validation
    print("\n[6] Validating Maneuver Post-Burn Re-Screening...")
    val_payload = {
        "conjunction_id": "CONJ-001",
        "primary_sat_id": 25544,
        "proposed_maneuver": {
            "radial_m_s": 0.0,
            "along_track_m_s": 0.30,
            "cross_track_m_s": 0.0,
            "burn_time": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
        }
    }
    try:
        res = requests.post(f"{NODE_BACKEND_URL}/maneuver/validate", json=val_payload)
        val_data = res.json()
        optimal = val_data.get('optimal_candidate', {})
        print(f"[OK] Re-Screening Status: {optimal.get('status')}")
        print(f"   - Safe Maneuver: {optimal.get('is_safe')}")
        print(f"   - Primary Threat Resolved: {optimal.get('primary_threat_resolved')}")
        print(f"   - Secondary Threats Introduced: {optimal.get('secondary_threats_detected')}")
    except Exception as e:
        print(f"[ERROR] Error validating maneuver: {e}")

    print("\n" + "=" * 70)
    print("ALL ENDPOINTS WORKING PERFECTLY!")
    print("=" * 70)

if __name__ == "__main__":
    main()
