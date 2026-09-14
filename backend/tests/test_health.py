from fastapi.testclient import TestClient

from diagnosis_agent.main import app


def test_health_endpoint() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "llm-agent-diagnosis-platform"
