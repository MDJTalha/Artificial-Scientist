"""Release-gate tests for unscoped Phase 7 endpoints."""

from dataclasses import replace

from fastapi.testclient import TestClient

import artificial_scientist.api.routes.records as records_routes
import artificial_scientist.main as main


def test_production_research_routes_require_configured_oidc(monkeypatch) -> None:
    configured = main.get_settings()
    production = replace(
        configured,
        environment="production",
        oidc_issuer=None,
        oidc_audience=None,
        oidc_jwks_url=None,
    )
    monkeypatch.setattr(main, "get_settings", lambda: production)
    monkeypatch.setattr(records_routes, "get_settings", lambda: production)
    with TestClient(main.app) as client:
        for path in ("/api/v1/records", "/api/v1/discovery/decompose"):
            response = client.get(path) if path.endswith("records") else client.post(
                path, json={"research_question": "Does temperature affect reaction rate?"}
            )
            assert response.status_code == 503
            assert (
                "tenant-scoped record authorization is implemented and reviewed"
                in response.json()["detail"]
            )

def test_production_health_remains_available_without_record_access(monkeypatch) -> None:
    configured = main.get_settings()
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: replace(configured, environment="production"),
    )
    with TestClient(main.app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_endpoint_remains_available_while_research_routes_are_gated(
    monkeypatch,
) -> None:
    configured = main.get_settings()
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: replace(configured, environment="production"),
    )

    with TestClient(main.app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200


def test_development_keeps_discovery_routes_available(monkeypatch) -> None:
    configured = main.get_settings()
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: replace(configured, environment="development"),
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/discovery/decompose",
            json={"research_question": "Does temperature affect reaction rate?"},
        )

    assert response.status_code == 200
