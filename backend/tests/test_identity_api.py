"""API-boundary tests for configured OIDC authentication."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from artificial_scientist.api.routes import lab as lab_routes
from artificial_scientist.api.routes.lab import get_lab_store
from artificial_scientist.authorization import TenantDirectory
from artificial_scientist.identity import AuthenticatedPrincipal
from artificial_scientist.lab.store import LabRunStore
from artificial_scientist.main import app


def test_configured_oidc_cannot_be_bypassed_with_legacy_api_key(monkeypatch):
    monkeypatch.setattr(
        lab_routes,
        "get_settings",
        lambda: SimpleNamespace(
            environment="production",
            lab_api_key="legacy-shared-secret-that-is-long-enough",
            oidc_issuer="https://identity.example.test/",
            oidc_audience="scientific-api",
            oidc_jwks_url="https://identity.example.test/jwks.json",
        ),
    )
    monkeypatch.setattr(
        lab_routes,
        "validate_oidc_bearer_token",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Token validator must not run without a bearer token.")
        ),
    )

    client = TestClient(app)
    assert client.get(
        "/api/v1/lab/runs",
        headers={"X-Lab-API-Key": "legacy-shared-secret-that-is-long-enough"},
    ).status_code == 401


def test_configured_oidc_accepts_only_validated_bearer_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(
        lab_routes,
        "get_settings",
        lambda: SimpleNamespace(
            environment="production",
            lab_api_key="legacy-shared-secret-that-is-long-enough",
            oidc_issuer="https://identity.example.test/",
            oidc_audience="scientific-api",
            oidc_jwks_url="https://identity.example.test/jwks.json",
            database_path=str(tmp_path / "oidc-api.sqlite3"),
        ),
    )
    validated = []
    principal = AuthenticatedPrincipal(
        subject="researcher-123",
        issuer="https://identity.example.test/",
        audience="scientific-api",
    )
    monkeypatch.setattr(
        lab_routes,
        "validate_oidc_bearer_token",
        lambda token, **kwargs: (validated.append((token, kwargs)) or principal),
    )

    tenant_directory = TenantDirectory(str(tmp_path / "oidc-api.sqlite3"))
    principal_id = tenant_directory.register_principal(principal.issuer, principal.subject)
    tenant_id = tenant_directory.create_tenant("oidc-test-tenant", "OIDC Test Tenant")
    tenant_directory.grant_membership(principal_id, tenant_id, "researcher")

    store = LabRunStore(str(tmp_path / "oidc-api.sqlite3"))
    app.dependency_overrides[get_lab_store] = lambda: store
    try:
        response = TestClient(app).get(
            "/api/v1/lab/runs",
            headers={
                "Authorization": "Bearer signed-token",
                "X-Tenant-ID": tenant_id,
            },
        )
        assert response.status_code == 200
        assert validated[0][0] == "signed-token"
        assert validated[0][1]["issuer"] == "https://identity.example.test/"
    finally:
        app.dependency_overrides.pop(get_lab_store, None)


def test_partial_oidc_configuration_fails_closed(monkeypatch):
    monkeypatch.setattr(
        lab_routes,
        "get_settings",
        lambda: SimpleNamespace(
            environment="production",
            lab_api_key="legacy-shared-secret-that-is-long-enough",
            oidc_issuer="https://identity.example.test/",
            oidc_audience=None,
            oidc_jwks_url=None,
        ),
    )
    response = TestClient(app).get(
        "/api/v1/lab/runs",
        headers={"X-Lab-API-Key": "legacy-shared-secret-that-is-long-enough"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "OIDC authentication is not fully configured."



def test_tenant_scoped_run_api_hides_runs_from_other_tenants(monkeypatch, tmp_path):
    database = str(tmp_path / "tenant-api.sqlite3")
    principal = AuthenticatedPrincipal(
        subject="tenant-api-user",
        issuer="https://identity.example.test/",
        audience="scientific-api",
    )
    monkeypatch.setattr(
        lab_routes,
        "get_settings",
        lambda: SimpleNamespace(
            environment="production",
            lab_api_key=None,
            oidc_issuer="https://identity.example.test/",
            oidc_audience="scientific-api",
            oidc_jwks_url="https://identity.example.test/jwks.json",
            database_path=database,
        ),
    )
    monkeypatch.setattr(
        lab_routes, "validate_oidc_bearer_token", lambda *_args, **_kwargs: principal
    )
    directory = TenantDirectory(database)
    principal_id = directory.register_principal(principal.issuer, principal.subject)
    tenant_a = directory.create_tenant("tenant-api-a", "Tenant API A")
    tenant_b = directory.create_tenant("tenant-api-b", "Tenant API B")
    directory.grant_membership(principal_id, tenant_a, "researcher")

    store = LabRunStore(database)
    app.dependency_overrides[get_lab_store] = lambda: store
    try:
        from artificial_scientist.lab.engine import run_lab
        from artificial_scientist.lab.models import LabRunRequest

        run_a = run_lab(
            LabRunRequest(
                title="Visible tenant run",
                steps=[{
                    "step_id": "summary",
                    "operation": "statistics",
                    "inputs": {"values": [1, 2, 3], "variance_mode": "population"},
                }],
            ),
        )
        run_b = run_lab(
            LabRunRequest(
                title="Hidden tenant run",
                steps=[{
                    "step_id": "summary",
                    "operation": "statistics",
                    "inputs": {"values": [4, 5, 6], "variance_mode": "population"},
                }],
            ),
        )
        store.save(run_a, tenant_id=tenant_a)
        store.save(run_b, tenant_id=tenant_b)
        client = TestClient(app)
        headers = {
            "Authorization": "Bearer signed-token",
            "X-Tenant-ID": tenant_a,
        }
        response = client.get("/api/v1/lab/runs", headers=headers)
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["title"] == "Visible tenant run"

        hidden = client.get(f"/api/v1/lab/runs/{run_b.run_id}", headers=headers)
        assert hidden.status_code == 404
        no_tenant = client.get(
            "/api/v1/lab/runs",
            headers={"Authorization": "Bearer signed-token"},
        )
        assert no_tenant.status_code == 403
    finally:
        app.dependency_overrides.pop(get_lab_store, None)
