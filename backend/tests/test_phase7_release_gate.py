"""Release-gate tests for unscoped Phase 7 endpoints."""

from dataclasses import replace

from fastapi.testclient import TestClient

import artificial_scientist.main as main


def test_unscoped_research_records_and_discovery_fail_closed_outside_development(
    monkeypatch,
) -> None:
    configured = main.get_settings()
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: replace(configured, environment="production"),
    )

    with TestClient(main.app) as client:
        for method, path in (
            ("get", "/api/v1/records"),
            ("get", "/api/v1/records/audit-events"),
            ("get", "/api/v1/discovery/decompose"),
            ("post", "/api/v1/discovery/assess"),
            ("post", "/api/v1/discovery/prior-work-screen"),
        ):
            response = getattr(client, method)(path, json={} if method == "post" else None)
            assert response.status_code == 503
            assert response.headers["cache-control"] == "no-store"
            assert "tenant-scoped record authorization" in response.json()["detail"]


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
        response = client.get("/health")

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
