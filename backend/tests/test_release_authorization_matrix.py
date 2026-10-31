"""Endpoint authorization contract and adversarial negative coverage.

These tests intentionally inspect the application route graph so adding a new
tenant-scoped endpoint without an authorization dependency fails CI.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

import artificial_scientist.api.routes.autonomy as autonomy_routes
import artificial_scientist.api.routes.discovery as discovery_routes
import artificial_scientist.api.routes.knowledge as knowledge_routes
import artificial_scientist.api.routes.records as records_routes
import artificial_scientist.main as main
from artificial_scientist.authorization import AuthorizationDenied


def _dependency_names(route) -> set[str]:
    names: set[str] = set()
    for dependency in route.dependant.dependencies:
        call = dependency.call
        if call is not None:
            names.add(getattr(call, "__name__", call.__class__.__name__))
    return names


@pytest.mark.parametrize(
    ("router", "public_paths"),
    [
        (records_routes.router, set()),
        (discovery_routes.router, set()),
        (knowledge_routes.router, set()),
        (autonomy_routes.router, set()),
    ],
)
def test_every_research_router_endpoint_declares_record_access(
    router, public_paths
) -> None:
    """Every non-public research route must carry the shared tenant dependency."""
    routes = [route for route in router.routes if getattr(route, "endpoint", None)]
    assert routes
    for route in routes:
        if route.path in public_paths:
            continue
        names = _dependency_names(route)
        assert "dependency" in names or any(
            "record_access" in repr(dependency.call)
            for dependency in route.dependant.dependencies
        ), f"missing tenant authorization dependency: {route.methods} {route.path}"


def test_record_authorization_denies_cross_tenant_selector_before_handler(
    monkeypatch,
) -> None:
    """A principal without membership receives a non-disclosing denial."""
    configured = main.get_settings()
    production = replace(
        configured,
        environment="production",
        oidc_issuer="https://issuer.example/",
        oidc_audience="asds-api",
        oidc_jwks_url="https://issuer.example/.well-known/jwks.json",
    )
    monkeypatch.setattr(records_routes, "get_settings", lambda: production)

    def deny(*args, **kwargs):
        raise AuthorizationDenied("denied")

    monkeypatch.setattr(records_routes.TenantDirectory, "authorize", deny)
    monkeypatch.setattr(
        records_routes,
        "validate_oidc_bearer_token",
        lambda *args, **kwargs: type(
            "Principal", (), {"issuer": "https://issuer.example/", "subject": "user-a"}
        )(),
    )

    with TestClient(main.app) as client:
        response = client.get(
            "/api/v1/records",
            headers={
                "Authorization": "Bearer synthetic-token",
                "X-Tenant-Id": "00000000-0000-0000-0000-000000000001",
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Requested tenant resource is not available."


def test_health_is_the_only_intentionally_public_system_route() -> None:
    public = {
        (method, route.path)
        for route in main.app.routes
        if getattr(route, "methods", None)
        for method in route.methods
        if route.path == "/api/v1/health"
    }
    assert public
    assert all(
        route.path == "/api/v1/health" or route.path.startswith("/docs")
        for route in main.app.routes
        if getattr(route, "methods", None)
    )
