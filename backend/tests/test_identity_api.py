"""API-boundary tests for configured OIDC authentication."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from artificial_scientist.api.routes import lab as lab_routes
from artificial_scientist.api.routes.lab import get_lab_store
from artificial_scientist.authorization import TenantDirectory
from artificial_scientist.identity import AuthenticatedPrincipal
from artificial_scientist.lab.store import LabRunStore
from artificial_scientist.main import app


def test_unauthenticated_lab_request_is_audited_as_anonymous(monkeypatch, tmp_path):
    database = str(tmp_path / "anonymous-auth-audit.sqlite3")
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

    response = TestClient(app).get("/api/v1/lab/runs")
    assert response.status_code == 401

    events = TenantDirectory(database).list_audit_events(None, limit=100)
    anonymous_denials = [
        event for event in events
        if event["action"] == "authentication:request"
        and event["outcome"] == "denied"
        and event["metadata"].get("http_status") == 401
    ]
    assert anonymous_denials
    assert all(event["principal_id"] is None for event in anonymous_denials)
    assert all(event["correlation_id"] for event in anonymous_denials)


def test_malformed_tenant_selector_is_bounded_and_audited(monkeypatch, tmp_path):
    database = str(tmp_path / "malformed-tenant-selector.sqlite3")
    principal = AuthenticatedPrincipal(
        subject="malformed-tenant-selector-user",
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

    response = TestClient(app).get(
        "/api/v1/lab/runs",
        headers={
            "Authorization": "Bearer signed-token",
            "X-Tenant-ID": "x" * 100_000,
        },
    )
    assert response.status_code == 404

    events = TenantDirectory(database).list_audit_events(None, limit=100)
    selector_denials = [
        event
        for event in events
        if event["action"] == "run:list"
        and event["target_type"] == "request"
        and event["outcome"] == "denied"
        and event["metadata"].get("http_status") == 404
    ]
    assert selector_denials
    assert all(event["tenant_id"] is None for event in selector_denials)
    assert all(event["target_id"] is None for event in selector_denials)


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
        json_artifact_b = store.list_artifacts(run_b.run_id)[0]
        binary_artifact_b = store.save_binary_artifact(
            run_b.run_id,
            "tenant-b.bin",
            "application/octet-stream",
            b"tenant B only",
            scan_status="skipped_development",
            tenant_id=tenant_b,
        )
        client = TestClient(app)
        headers = {
            "Authorization": "Bearer signed-token",
            "X-Tenant-ID": tenant_a,
        }
        response = client.get("/api/v1/lab/runs", headers=headers)
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["title"] == "Visible tenant run"

        denied_paths = [
            ("GET", f"/api/v1/lab/runs/{run_b.run_id}"),
            ("GET", f"/api/v1/lab/runs/{run_b.run_id}/execution-status"),
            ("POST", f"/api/v1/lab/runs/{run_b.run_id}/verify"),
            ("GET", f"/api/v1/lab/runs/{run_b.run_id}/export"),
            ("GET", f"/api/v1/lab/runs/{run_b.run_id}/artifacts"),
            ("GET", f"/api/v1/lab/artifacts/{json_artifact_b.artifact_id}"),
            ("GET", f"/api/v1/lab/runs/{run_b.run_id}/binary-artifacts"),
            ("GET", f"/api/v1/lab/binary-artifacts/{binary_artifact_b['artifact_id']}"),
        ]
        for method, path in denied_paths:
            denied = client.request(method, path, headers=headers)
            assert denied.status_code == 404, (method, path, denied.text)

        audit_events = directory.list_audit_events(tenant_a, limit=100)
        denied_run_events = [
            event
            for event in audit_events
            if event["target_id"] == str(run_b.run_id)
            and event["outcome"] == "denied"
            and event["metadata"].get("http_status") == 404
        ]
        assert denied_run_events
        assert all(event["principal_id"] == principal_id for event in denied_run_events)
        assert all(event["correlation_id"] for event in denied_run_events)

        # Object-ID substitution must be denied and audited at the object level,
        # not merely as a generic run denial.
        artifact_denials = [
            event
            for event in audit_events
            if event["target_id"] == str(json_artifact_b.artifact_id)
            and event["target_type"] == "artifact"
            and event["outcome"] == "denied"
            and event["metadata"].get("http_status") == 404
        ]
        binary_denials = [
            event
            for event in audit_events
            if event["target_id"] == str(binary_artifact_b["artifact_id"])
            and event["target_type"] == "binary_artifact"
            and event["outcome"] == "denied"
            and event["metadata"].get("http_status") == 404
        ]
        assert artifact_denials
        assert binary_denials

        no_tenant = client.get(
            "/api/v1/lab/runs",
            headers={"Authorization": "Bearer signed-token"},
        )
        assert no_tenant.status_code == 403
    finally:
        app.dependency_overrides.pop(get_lab_store, None)

def test_cross_tenant_binary_upload_is_rejected_before_body_scanning(
    monkeypatch, tmp_path
):
    database = str(tmp_path / "tenant-upload-api.sqlite3")
    principal = AuthenticatedPrincipal(
        subject="tenant-upload-user",
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
    monkeypatch.setattr(
        lab_routes,
        "scan_binary_content",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Cross-tenant upload body must not reach the scanner.")
        ),
    )
    directory = TenantDirectory(database)
    principal_id = directory.register_principal(principal.issuer, principal.subject)
    tenant_a = directory.create_tenant("tenant-upload-a", "Tenant Upload A")
    tenant_b = directory.create_tenant("tenant-upload-b", "Tenant Upload B")
    directory.grant_membership(principal_id, tenant_a, "researcher")

    from artificial_scientist.lab.engine import run_lab
    from artificial_scientist.lab.models import LabRunRequest

    store = LabRunStore(database)
    run_b = run_lab(
        LabRunRequest(
            title="Tenant B upload target",
            steps=[
                {
                    "step_id": "summary",
                    "operation": "statistics",
                    "inputs": {"values": [1, 2, 3], "variance_mode": "population"},
                }
            ],
        )
    )
    store.save(run_b, tenant_id=tenant_b)
    app.dependency_overrides[get_lab_store] = lambda: store
    try:
        response = TestClient(app).post(
            f"/api/v1/lab/runs/{run_b.run_id}/binary-artifacts?filename=probe.bin",
            content=b"must-not-be-scanned",
            headers={
                "Authorization": "Bearer signed-token",
                "X-Tenant-ID": tenant_a,
                "Content-Type": "application/octet-stream",
            },
        )
        assert response.status_code == 404

        # The denial must be auditable even though the request body is rejected
        # before it reaches the malware/content scanner.
        upload_denials = [
            event
            for event in directory.list_audit_events(tenant_a, limit=100)
            if event["target_id"] == str(run_b.run_id)
            and event["action"] == "artifact:upload"
            and event["outcome"] == "denied"
            and event["metadata"].get("http_status") == 404
        ]
        assert upload_denials
        assert all(event["principal_id"] == principal_id for event in upload_denials)
        assert all(event["correlation_id"] for event in upload_denials)
    finally:
        app.dependency_overrides.pop(get_lab_store, None)



def test_negative_content_length_is_rejected_before_scanning(monkeypatch, tmp_path):
    database = str(tmp_path / "negative-content-length.sqlite3")
    principal = AuthenticatedPrincipal(
        subject="negative-content-length-user",
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
    monkeypatch.setattr(
        lab_routes,
        "scan_binary_content",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Invalid Content-Length must be rejected before scanning.")
        ),
    )
    directory = TenantDirectory(database)
    principal_id = directory.register_principal(principal.issuer, principal.subject)
    tenant_id = directory.create_tenant("negative-length-tenant", "Negative Length Tenant")
    directory.grant_membership(principal_id, tenant_id, "researcher")

    from artificial_scientist.lab.engine import run_lab
    from artificial_scientist.lab.models import LabRunRequest

    store = LabRunStore(database)
    run = run_lab(
        LabRunRequest(
            title="Content length validation target",
            steps=[
                {
                    "step_id": "summary",
                    "operation": "statistics",
                    "inputs": {"values": [1, 2, 3], "variance_mode": "population"},
                }
            ],
        )
    )
    store.save(run, tenant_id=tenant_id)
    app.dependency_overrides[get_lab_store] = lambda: store
    try:
        response = TestClient(app).post(
            f"/api/v1/lab/runs/{run.run_id}/binary-artifacts?filename=probe.bin",
            content=b"",
            headers={
                "Authorization": "Bearer signed-token",
                "X-Tenant-ID": tenant_id,
                "Content-Type": "application/octet-stream",
                "Content-Length": "-1",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid Content-Length header."

        oversized_decimal = TestClient(app).post(
            f"/api/v1/lab/runs/{run.run_id}/binary-artifacts?filename=probe.bin",
            content=b"",
            headers={
                "Authorization": "Bearer signed-token",
                "X-Tenant-ID": tenant_id,
                "Content-Type": "application/octet-stream",
                "Content-Length": "9" * 10_000,
            },
        )
        assert oversized_decimal.status_code == 413
    finally:
        app.dependency_overrides.pop(get_lab_store, None)



def test_result_persistence_failure_marks_execution_failed(monkeypatch, tmp_path):
    from uuid import UUID

    database = str(tmp_path / "tenant-persistence-failure.sqlite3")
    principal = AuthenticatedPrincipal(
        subject="persistence-failure-user",
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
    tenant_id = directory.create_tenant("persistence-failure-tenant", "Persistence Failure")
    directory.grant_membership(principal_id, tenant_id, "researcher")

    store = LabRunStore(database)
    attempted_ids = []

    def reject_persistence(run, *, tenant_id=None):
        attempted_ids.append(run.run_id)
        raise ValueError("Tenant storage quota reached.")

    monkeypatch.setattr(store, "save", reject_persistence)
    app.dependency_overrides[get_lab_store] = lambda: store
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/v1/lab/runs",
            json={
                "title": "Persistence quota rejection",
                "steps": [
                    {
                        "step_id": "summary",
                        "operation": "statistics",
                        "inputs": {"values": [1, 2, 3], "variance_mode": "population"},
                    }
                ],
            },
            headers={
                "Authorization": "Bearer signed-token",
                "X-Tenant-ID": tenant_id,
            },
        )
        assert response.status_code == 500
        assert len(attempted_ids) == 1
        status = store.get_execution_status(UUID(str(attempted_ids[0])), tenant_id=tenant_id)
        assert status["status"] == "failed"
    finally:
        app.dependency_overrides.pop(get_lab_store, None)



def test_lab_request_fails_closed_when_final_audit_persistence_fails(
    monkeypatch, tmp_path
):
    database = str(tmp_path / "audit-unavailable.sqlite3")
    principal = AuthenticatedPrincipal(
        subject="audit-failure-user",
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
    tenant_id = directory.create_tenant("audit-failure-tenant", "Audit Failure Tenant")
    directory.grant_membership(principal_id, tenant_id, "researcher")

    original_audit = TenantDirectory.audit

    def fail_final_outcome(self, **kwargs):
        metadata = kwargs.get("metadata") or {}
        if "http_status" in metadata:
            raise RuntimeError("simulated audit persistence outage")
        return original_audit(self, **kwargs)

    monkeypatch.setattr(TenantDirectory, "audit", fail_final_outcome)
    store = LabRunStore(database)
    app.dependency_overrides[get_lab_store] = lambda: store
    try:
        response = TestClient(app).get(
            "/api/v1/lab/runs",
            headers={
                "Authorization": "Bearer signed-token",
                "X-Tenant-ID": tenant_id,
            },
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Security audit persistence is unavailable."
    finally:
        app.dependency_overrides.pop(get_lab_store, None)


def test_run_quota_exhaustion_returns_http_429(monkeypatch, tmp_path):
    import artificial_scientist.lab.store as store_module

    database = str(tmp_path / "tenant-run-quota-api.sqlite3")
    principal = AuthenticatedPrincipal(
        subject="tenant-quota-user",
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
    monkeypatch.setattr(store_module, "_MAX_RUNS_PER_TENANT", 0)
    directory = TenantDirectory(database)
    principal_id = directory.register_principal(principal.issuer, principal.subject)
    tenant_id = directory.create_tenant("tenant-quota-api", "Tenant Quota API")
    directory.grant_membership(principal_id, tenant_id, "researcher")

    store = LabRunStore(database)
    app.dependency_overrides[get_lab_store] = lambda: store
    try:
        response = TestClient(app).post(
            "/api/v1/lab/runs",
            headers={
                "Authorization": "Bearer signed-token",
                "X-Tenant-ID": tenant_id,
            },
            json={
                "title": "Quota rejection",
                "steps": [{
                    "step_id": "summary",
                    "operation": "statistics",
                    "inputs": {"values": [1, 2, 3], "variance_mode": "population"},
                }],
            },
        )
        assert response.status_code == 429
        assert response.json()["detail"] == "Tenant has reached its lab run quota."
        quota_events = directory.list_audit_events(tenant_id, limit=100)
        assert any(
            event["action"] == "run:create"
            and event["outcome"] == "denied"
            and event["metadata"].get("http_status") == 429
            for event in quota_events
        )
    finally:
        app.dependency_overrides.pop(get_lab_store, None)
