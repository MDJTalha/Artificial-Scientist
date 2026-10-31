from types import SimpleNamespace

from fastapi.testclient import TestClient

from artificial_scientist.api.routes import autonomy as autonomy_routes
from artificial_scientist.main import app


def test_autonomy_workflow_api_persists_and_enforces_approval(monkeypatch, tmp_path):
    database = str(tmp_path / "autonomy-api.sqlite3")
    monkeypatch.setattr(
        autonomy_routes,
        "get_settings",
        lambda: SimpleNamespace(database_path=database),
    )
    client = TestClient(app)

    created = client.post(
        "/api/v1/autonomy/workflows",
        json={"workflow_id": "api-workflow", "consequential": True},
    )
    assert created.status_code == 201
    assert created.json()["state"] == "draft"

    assert client.post(
        "/api/v1/autonomy/workflows/api-workflow/plan",
        json={"actor": "system", "reason": "plan"},
    ).status_code == 200
    assert client.post(
        "/api/v1/autonomy/workflows/api-workflow/request-approval",
        json={"actor": "system", "reason": "gate"},
    ).status_code == 200

    approved = client.post(
        "/api/v1/autonomy/workflows/api-workflow/approve",
        json={"token": "secret", "actor": "operator"},
    )
    assert approved.status_code == 200
    assert approved.json()["approval_token_hash_present"] is True

    fetched = client.get("/api/v1/autonomy/workflows/api-workflow")
    assert fetched.status_code == 200
    assert fetched.json()["state"] == "approved"


def test_autonomy_workflow_api_fails_closed_for_invalid_transition(monkeypatch, tmp_path):
    database = str(tmp_path / "autonomy-api-invalid.sqlite3")
    monkeypatch.setattr(
        autonomy_routes,
        "get_settings",
        lambda: SimpleNamespace(database_path=database),
    )
    client = TestClient(app)
    client.post(
        "/api/v1/autonomy/workflows",
        json={"workflow_id": "invalid-transition", "consequential": True},
    )
    response = client.post(
        "/api/v1/autonomy/workflows/invalid-transition/approve",
        json={"token": "secret", "actor": "operator"},
    )
    assert response.status_code == 409
