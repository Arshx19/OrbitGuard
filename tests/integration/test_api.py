"""Integration test for ORBITGUARD AI FastAPI endpoints."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"


def test_get_satellites_endpoint():
    response = client.get("/api/v1/satellites")
    assert response.status_code == 200
    data = response.json()
    assert "total_tracked" in data
    assert len(data["satellites"]) > 0


def test_get_conjunctions_endpoint():
    response = client.get("/api/v1/conjunctions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["risk_level"] in ["CRITICAL", "HIGH", "AMBER", "GREEN"]


def test_risk_analyze_endpoint():
    payload = {
        "miss_distance_km": 0.42,
        "relative_speed_kms": 12.4,
        "time_to_tca_hours": 4.2,
        "radial_velocity_kms": -0.5,
        "approach_angle_degrees": 88.5,
        "uncertainty_factor": 1.5
    }
    response = client.post("/api/v1/risk/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_score"] > 80.0
    assert data["risk_level"] == "CRITICAL"
    assert len(data["shap_factors"]) > 0


def test_maneuver_optimize_endpoint():
    payload = {
        "conjunction_id": "CONJ-001",
        "primary_satellite_id": 25544,
        "threat_satellite_id": 99901,
        "tca": "2026-09-13T04:12:00Z",
        "dv_min_ms": 0.05,
        "dv_max_ms": 1.0
    }
    response = client.post("/api/v1/maneuver/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["optimal_candidate"] is not None
    assert data["optimal_candidate"]["is_safe"] is True
    assert data["optimal_candidate"]["status"] == "VALIDATED"


# --- Regression tests for the computed-engine integration --------------------


def test_maneuver_optimize_accepts_conjunction_id_alone():
    # The frontend sends only conjunction_id. When the other fields were
    # required, every UI request failed validation with a 422 and the page
    # silently fell back to mock candidates.
    response = client.post("/api/v1/maneuver/optimize", json={"conjunction_id": "CONJ-001"})
    assert response.status_code == 200
    data = response.json()
    assert data["candidates_evaluated"] > 0
    assert data["optimal_candidate"]["pc_after"] < data["safety_target"] < data["pc_before"]


def test_maneuver_validate_rescreens_the_chosen_candidate():
    optimal = client.post("/api/v1/maneuver/optimize", json={"conjunction_id": "CONJ-001"}).json()["optimal_candidate"]
    response = client.post("/api/v1/maneuver/validate",
                           json={"conjunction_id": "CONJ-001", "candidate_id": optimal["candidate_id"]})
    assert response.status_code == 200
    data = response.json()
    assert data["validated_candidate"]["candidate_id"] == optimal["candidate_id"]
    assert data["checks"]["catalog_rescreened"] is True
    assert data["checks"]["catalog_objects_screened"] > 0


def test_conjunction_values_are_computed_not_preset():
    data = client.get("/api/v1/conjunctions").json()
    simulated = [c for c in data if c["simulated"]]
    screened = [c for c in data if not c["simulated"]]
    assert len(simulated) == 1 and simulated[0]["id"] == "CONJ-001"
    assert screened, "screening the committed catalog should find real close approaches"
    # Real events vary; presets were identical across refreshes and events.
    assert len({round(c["miss_distance_km"], 6) for c in screened}) > 1
    for c in data:
        assert 0.0 <= c["collision_probability"] <= 1.0
        assert c["timeline"][-1]["t"] == "T-0"


def test_safe_events_keep_a_score_of_zero():
    # A score of 0 is a real value. The frontend once coerced it to 94.
    data = client.get("/api/v1/conjunctions").json()
    green = [c for c in data if c["risk_level"] == "GREEN"]
    assert green and all(c["risk_score"] < 30 for c in green)


def test_unknown_conjunction_is_404_everywhere():
    assert client.get("/api/v1/conjunctions/NOPE").status_code == 404
    assert client.post("/api/v1/risk/analyze", json={"conjunction_id": "NOPE"}).status_code == 404
    assert client.post("/api/v1/maneuver/optimize", json={"conjunction_id": "NOPE"}).status_code == 404


def test_factors_are_counterfactual_and_labelled_as_such():
    data = client.post("/api/v1/risk/analyze", json={"conjunction_id": "CONJ-001"}).json()
    assert data["explanation_method"] == "counterfactual"
    assert all(f["explanation"] for f in data["shap_factors"])
