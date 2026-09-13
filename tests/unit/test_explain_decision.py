import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from fastapi.testclient import TestClient
from app.main import app
from app.services.world import get_world

client = TestClient(app)


def test_explain_decision_endpoint_valid_conjunction():
    world = get_world()
    events = list(world.events.keys())
    assert len(events) > 0, "Expected at least one conjunction event in world"
    conjunction_id = events[0]

    response = client.post("/api/v1/explain/decision", json={"conjunction_id": conjunction_id})
    assert response.status_code == 200, f"Response failed: {response.text}"

    data = response.json()
    assert data["conjunction_id"] == conjunction_id
    assert "questions" in data
    questions = data["questions"]
    assert "why_high_risk" in questions
    assert "why_selected_maneuver" in questions
    assert "why_others_rejected" in questions
    assert "post_maneuver_impact" in questions
    assert "was_validated" in questions

    assert len(data["shap_attributions"]) > 0
    assert "validation_summary" in data


def test_explain_decision_endpoint_invalid_conjunction():
    response = client.post("/api/v1/explain/decision", json={"conjunction_id": "NON_EXISTENT_ID"})
    assert response.status_code == 404
