"""Tests for the Phase 1 API foundation."""

from fastapi.testclient import TestClient

from artificial_scientist.main import app

client = TestClient(app)


def test_root_returns_application_identity() -> None:
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "Artificial Scientist"
    assert body["version"] == "0.1.0"
    assert body["status"] == "running"
    assert body["docs"] == "/docs"


def test_health_endpoint_reports_api_process_health() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": "ok",
        "service": "Artificial Scientist",
        "version": "0.1.0",
    }


def test_readiness_endpoint_discloses_its_scope() -> None:
    response = client.get("/api/v1/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["scope"] == "application_only"


def test_openapi_schema_is_available() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    body = response.json()
    assert body["info"]["title"] == "Artificial Scientist"
    assert "/api/v1/health" in body["paths"]
