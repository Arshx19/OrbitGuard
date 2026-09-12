"""
End-to-end tests of the HTTP API.

These run the real application against the committed catalog snapshot: the world
is built once per module (screening and risk assessment included), then every
endpoint the frontend calls is exercised through FastAPI's test client.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

os.environ.setdefault("ORBITGUARD_ALLOW_NETWORK", "0")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

API = "/api/v1"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def conjunctions(client):
    response = client.get(f"{API}/conjunctions")
    assert response.status_code == 200
    return response.json()


class TestSystem:
    def test_health_reports_provenance(self, client):
        body = client.get(f"{API}/health").json()
        assert body["status"] == "ok"
        assert body["objects"] > 0
        assert body["catalog"], "the catalog snapshots behind the data should be reported"

    def test_cors_allows_the_dev_frontend(self, client):
        response = client.options(
            f"{API}/risk/analyze",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


class TestCatalog:
    def test_stats_are_consistent_with_the_lists(self, client, conjunctions):
        stats = client.get(f"{API}/satellites/stats").json()
        satellites = client.get(f"{API}/satellites").json()
        assert stats["objects_tracked"] == len(satellites)
        assert stats["active_conjunctions"] == len(conjunctions)
        assert stats["high_risk_events"] == sum(
            c["severity"] in ("HIGH", "CRITICAL") for c in conjunctions
        )


class TestConjunctions:
    def test_simulated_event_is_present_and_labelled(self, conjunctions):
        simulated = [c for c in conjunctions if c["simulated"]]
        assert len(simulated) == 1
        assert simulated[0]["conjunction_id"] == "SIM-001"
        assert simulated[0]["severity"] == "CRITICAL"

    def test_screened_events_are_real_and_labelled_as_such(self, conjunctions):
        screened = [c for c in conjunctions if not c["simulated"]]
        assert screened, "the committed catalog produces genuine close approaches"
        assert all(c["miss_distance_km"] <= 25.0 for c in screened)

    def test_every_event_carries_what_the_frontend_renders(self, conjunctions):
        required = {
            "conjunction_id", "primary_name", "secondary_name", "tca", "miss_distance_km",
            "relative_speed_kms", "collision_probability", "risk_score", "severity",
            "factors", "timeline", "geometry", "narrative",
        }
        for c in conjunctions:
            assert required <= c.keys()
            assert 0 <= c["collision_probability"] <= 1
            assert 0 <= c["risk_score"] <= 100
            assert c["timeline"][-1]["t"] == "T-0"

    def test_lookup_and_404(self, client):
        assert client.get(f"{API}/conjunctions/SIM-001").json()["conjunction_id"] == "SIM-001"
        assert client.get(f"{API}/conjunctions/NOPE").status_code == 404


class TestRisk:
    def test_analyze_returns_explanation_and_detail(self, client):
        body = client.post(f"{API}/risk/analyze", json={"conjunction_id": "SIM-001"}).json()
        assert body["factors"]
        assert "pc_detail" in body
        assert "*" not in body["narrative"], "narrative is plain text, not markdown"

    def test_analyze_unknown_is_404(self, client):
        assert client.post(f"{API}/risk/analyze", json={"conjunction_id": "NOPE"}).status_code == 404


@pytest.fixture(scope="module")
def plan(client):
    response = client.post(f"{API}/maneuver/optimize", json={"conjunction_id": "SIM-001"})
    assert response.status_code == 200
    return response.json()


class TestManeuver:
    def test_a_safe_maneuver_is_recommended(self, plan):
        assert plan["recommended_candidate_id"] is not None
        recommended = next(c for c in plan["candidates"]
                           if c["candidate_id"] == plan["recommended_candidate_id"])
        assert recommended["is_safe"]
        assert recommended["pc_after"] < plan["safety_target"] < plan["pc_before"]

    def test_recommendation_is_the_cheapest_safe_option_shown(self, plan):
        safe = [c for c in plan["candidates"] if c["is_safe"]]
        cheapest = min(c["delta_v_magnitude_ms"] for c in safe)
        recommended = next(c for c in safe if c["candidate_id"] == plan["recommended_candidate_id"])
        assert recommended["delta_v_magnitude_ms"] == cheapest

    def test_rejections_explain_themselves(self, plan):
        for candidate in plan["candidates"]:
            if not candidate["is_safe"]:
                assert candidate["rejection_reason"]

    def test_validation_rescreens_the_catalog(self, client, plan):
        body = client.post(f"{API}/maneuver/validate", json={
            "conjunction_id": "SIM-001",
            "candidate_id": plan["recommended_candidate_id"],
        }).json()
        assert body["is_safe"]
        assert body["checks"]["catalog_rescreened"]
        assert body["checks"]["catalog_objects_screened"] > 0
        assert body["checks"]["new_conjunctions"] == 0

    def test_debris_only_event_offers_no_maneuver(self, client, conjunctions):
        debris = next(c for c in conjunctions if not c["maneuverable"])
        body = client.post(f"{API}/maneuver/optimize", json={"conjunction_id": debris["conjunction_id"]}).json()
        assert body["candidates"] == []
        assert body["reason"]

    def test_unknown_candidate_is_404(self, client):
        response = client.post(f"{API}/maneuver/validate",
                               json={"conjunction_id": "SIM-001", "candidate_id": "NOPE"})
        assert response.status_code == 404
