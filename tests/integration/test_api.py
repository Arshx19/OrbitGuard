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
