"""Authentication session endpoint tests: token validation precedes membership discovery."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from artificial_scientist.api.routes import auth as auth_routes
from artificial_scientist.authorization import TenantDirectory
from artificial_scientist.identity import AuthenticatedPrincipal
from artificial_scientist.main import app


def _settings(database_path: str):
    return SimpleNamespace(
        environment="production",
        database_path=database_path,
        oidc_issuer="https://identity.example.test/",
        oidc_audience="asds-api",
        oidc_jwks_url="https://identity.example.test/.well-known/jwks.json",
    )


def test_session_endpoint_returns_only_operator_provisioned_active_memberships(
    monkeypatch, tmp_path
):
    database = str(tmp_path / "auth-session.sqlite3")
    directory = TenantDirectory(database)
    principal = AuthenticatedPrincipal(
        subject="user-subject-123",
        issuer="https://identity.example.test/",
        audience="asds-api",
    )
    principal_id = directory.register_principal(principal.issuer, principal.subject)
    tenant_a = directory.create_tenant("external-tenant-a", "Research Group A")
    tenant_b = directory.create_tenant("external-tenant-b", "Research Group B")
    directory.grant_membership(principal_id, tenant_a, "researcher")
    directory.grant_membership(principal_id, tenant_b, "viewer")
    directory.revoke_membership(principal_id, tenant_b)

    monkeypatch.setattr(auth_routes, "get_settings", lambda: _settings(database))
    monkeypatch.setattr(
        auth_routes,
        "validate_oidc_bearer_token",
        lambda token, **kwargs: principal if token == "signed-access-token" else None,
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/auth/session",
            headers={"Authorization": "Bearer signed-access-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["principal_id"] == principal_id
    assert payload["issuer"] == principal.issuer
    assert payload["memberships"] == [
        {
            "tenant_id": tenant_a,
            "tenant_name": "Research Group A",
            "role": "researcher",
        }
    ]
    events = directory.list_audit_events(None, limit=20)
    assert any(event["action"] == "auth:session:read" for event in events)


def test_session_endpoint_fails_closed_without_oidc_configuration(
    monkeypatch, tmp_path
):
    settings = _settings(str(tmp_path / "auth-unconfigured.sqlite3"))
    settings.oidc_jwks_url = None
    monkeypatch.setattr(auth_routes, "get_settings", lambda: settings)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/auth/session",
            headers={"Authorization": "Bearer signed-access-token"},
        )

    assert response.status_code == 503
    assert "not fully configured" in response.json()["detail"]


def test_session_endpoint_rejects_missing_bearer_token(monkeypatch, tmp_path):
    database = str(tmp_path / "auth-missing-token.sqlite3")
    monkeypatch.setattr(
        auth_routes,
        "get_settings",
        lambda: _settings(database),
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/auth/session")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_session_endpoint_rejects_invalid_signed_token(monkeypatch, tmp_path):
    database = str(tmp_path / "auth-invalid-token.sqlite3")
    monkeypatch.setattr(auth_routes, "get_settings", lambda: _settings(database))

    def reject_token(token, **kwargs):
        raise auth_routes.InvalidIdentityError("invalid")

    monkeypatch.setattr(auth_routes, "validate_oidc_bearer_token", reject_token)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/auth/session",
            headers={"Authorization": "Bearer invalid"},
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
