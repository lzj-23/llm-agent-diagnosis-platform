from fastapi.testclient import TestClient

from diagnosis_agent.api import create_app
from diagnosis_agent.config import Settings


def test_frontend_and_assets_resolve_from_configured_root(tmp_path):
    settings = Settings(runtime_dir=str(tmp_path), web_api_key="")
    with TestClient(create_app(settings, start_workers=False)) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert client.get("/assets/app.js").status_code == 200


def test_api_persistence_auth_idempotency(tmp_path):
    app = create_app(
        Settings(runtime_dir=str(tmp_path), web_api_key="local-test"), start_workers=False
    )
    with TestClient(app) as client:
        assert client.get("/api/cases").status_code == 401
        headers = {"x-api-key": "local-test", "idempotency-key": "example"}
        body = {"question": "排查延迟", "case_id": "latency-0"}
        first = client.post("/api/tasks", json=body, headers=headers)
        assert first.status_code == 202
        second = client.post("/api/tasks", json=body, headers=headers)
        assert second.json()["id"] == first.json()["id"]
        assert second.json()["created"] is False
        body["question"] = "检查不同问题"
        assert client.post("/api/tasks", json=body, headers=headers).status_code == 409
        assert (
            client.get("/api/tasks/" + first.json()["id"], headers=headers).json()["status"]
            == "pending"
        )
        assert (
            client.post(
                "/api/tasks", json=body, headers={**headers, "origin": "https://evil.test"}
            ).status_code
            == 403
        )
