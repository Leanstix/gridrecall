from fastapi.testclient import TestClient

from gridrecall_api.main import app
from gridrecall_api.schemas import ActionType


def test_health_and_initial_state() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        state = client.get("/api/demo")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert state.json()["phase"] == "ready"
    assert state.json()["metrics"]["operational_memories"] == 0


def test_second_incident_uses_outcome_memory() -> None:
    with TestClient(app) as client:
        first = client.post("/api/demo/incidents/first")
        second = client.post("/api/demo/incidents/second")

    assert first.status_code == 200
    assert first.json()["phase"] == "first_resolved"
    assert first.json()["memories"][0]["failed_actions"] == [
        ActionType.APPROVED_INVERTER_RESET
    ]

    payload = second.json()
    assert payload["phase"] == "memory_proven"
    latest = payload["incidents"][-1]
    assert latest["recommendation"]["action"] == ActionType.INSPECT_VENTILATION
    assert ActionType.APPROVED_INVERTER_RESET in latest["recommendation"]["avoided_actions"]
    assert latest["recommendation"]["evidence"][0]["site_name"] == "Ajegunle Mini-Grid"
    assert payload["metrics"]["failed_actions_not_repeated"] == 1


def test_reset_is_idempotent() -> None:
    with TestClient(app) as client:
        client.post("/api/demo/incidents/first")
        first_reset = client.post("/api/demo/reset")
        second_reset = client.post("/api/demo/reset")

    assert first_reset.json()["phase"] == "ready"
    assert second_reset.json()["incidents"] == []
    assert second_reset.json()["memories"] == []
