"""Core API readiness tests for storage, OIDC and HTTPS origin gates."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from artificial_scientist.api.routes import health as health_routes
from artificial_scientist.main import app


def _production_settings(database_path: str):
    return SimpleNamespace(
        app_name="Artificial Scientist",
        environment="production",
        database_path=database_path,
        oidc_issuer="https://identity.example.test/",
        oidc_audience="asds-api",
        oidc_jwks_url="https://identity.example.test/.well-known/jwks.json",
        allowed_origins=("https://research.example.test",),
    )


def test_readiness_passes_when_durable_sqlite_oidc_and_https_origins_are_ready(
    monkeypatch, tmp_path
):
    database = str(tmp_path / "ready.sqlite3")
    monkeypatch.setattr(
        health_routes,
        "get_settings",
        lambda: _production_settings(database),
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"] == {
        "durable_database": True,
        "oidc_configuration": True,
        "https_cors_origins": True,
    }
    assert payload["capability_gates"]["laboratory_execution"].startswith("requires_reviewed")


def test_readiness_fails_closed_when_oidc_is_missing(monkeypatch, tmp_path):
    settings = _production_settings(str(tmp_path / "missing-oidc.sqlite3"))
    settings.oidc_jwks_url = None
    monkeypatch.setattr(health_routes, "get_settings", lambda: settings)

    with TestClient(app) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["oidc_configuration"] is False


def test_readiness_rejects_relative_or_in_memory_production_database(monkeypatch):
    settings = _production_settings(":memory:")
    monkeypatch.setattr(health_routes, "get_settings", lambda: settings)

    with TestClient(app) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["durable_database"] is False


def test_readiness_rejects_insecure_or_wildcard_browser_origins(monkeypatch, tmp_path):
    settings = _production_settings(str(tmp_path / "bad-origin.sqlite3"))
    settings.allowed_origins = ("http://research.example.test",)
    monkeypatch.setattr(health_routes, "get_settings", lambda: settings)

    with TestClient(app) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["https_cors_origins"] is False


def test_development_readiness_is_explicitly_scoped(monkeypatch):
    settings = SimpleNamespace(
        app_name="Artificial Scientist",
        environment="development",
        database_path=":memory:",
        oidc_issuer=None,
        oidc_audience=None,
        oidc_jwks_url=None,
        allowed_origins=("http://127.0.0.1:5173",),
    )
    monkeypatch.setattr(health_routes, "get_settings", lambda: settings)

    with TestClient(app) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json()["scope"] == "core_api_configuration_and_storage"
    assert response.json()["checks"] == {"development_mode": True}
    assert "Do not expose" in response.json()["details"]["development_mode"]
