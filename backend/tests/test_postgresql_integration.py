"""Real PostgreSQL smoke tests, executed by the dedicated CI service job."""

import os

import pytest
from fastapi.testclient import TestClient

from artificial_scientist.database import check_database_connection
from artificial_scientist.main import app


@pytest.fixture
def database_url() -> str:
    value = os.getenv("ARTIFICIAL_SCIENTIST_DATABASE_URL")
    if os.getenv("ASDS_POSTGRES_TEST_DATABASE") != "1":
        pytest.skip("Destructive PostgreSQL integration tests require the explicit CI safety flag.")
    if not value:
        pytest.skip("PostgreSQL service URL is not configured.")
    return value


def test_postgresql_driver_executes_read_only_health_query(database_url: str) -> None:
    check_database_connection(database_url)


def test_readiness_stays_blocked_until_postgresql_adapters_exist(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARTIFICIAL_SCIENTIST_ENV", "production")
    monkeypatch.setenv("ARTIFICIAL_SCIENTIST_DATABASE_URL", database_url)

    response = TestClient(app).get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "PostgreSQL is reachable, but application persistence adapters have not "
        "been migrated. Production readiness remains blocked."
    )


def test_alembic_schema_and_append_only_guards_are_installed(database_url: str) -> None:
    from sqlalchemy import inspect, text

    from artificial_scientist.database import get_database_engine

    engine = get_database_engine(database_url)
    expected = {
        "research_records",
        "audit_events",
        "source_identity",
        "asds_principals",
        "asds_tenants",
        "asds_memberships",
        "asds_security_audit",
        "alembic_version",
    }
    assert expected.issubset(set(inspect(engine).get_table_names()))

    with engine.connect() as connection:
        triggers = set(
            connection.execute(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE NOT tgisinternal AND tgname LIKE '%_append_only'"
                )
            ).scalars()
        )
    assert {
        "research_records_append_only",
        "audit_events_append_only",
        "source_identity_append_only",
        "asds_security_audit_append_only",
    }.issubset(triggers)



def test_postgresql_append_only_triggers_reject_mutation(database_url: str) -> None:
    from uuid import uuid4

    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from artificial_scientist.database import get_database_engine

    engine = get_database_engine(database_url)
    record_id = str(uuid4())
    event_id = str(uuid4())
    created_at = "2026-11-01T00:00:00+00:00"

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO research_records "
                "(id, tenant_id, record_type, schema_version, created_at, "
                "content_sha256, payload_json) "
                "VALUES (:id, NULL, 'source', 1, :created_at, :digest, '{}')"
            ),
            {"id": record_id, "created_at": created_at, "digest": "a" * 64},
        )

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO audit_events "
                "(event_id, tenant_id, occurred_at, action, actor, record_id, "
                "record_type, content_sha256) "
                "VALUES (:event_id, NULL, :occurred_at, 'record.created', "
                "'local-api-client', :record_id, 'source', :digest)"
            ),
            {
                "event_id": event_id,
                "occurred_at": created_at,
                "record_id": record_id,
                "digest": "a" * 64,
            },
        )

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO source_identity (identity_key, tenant_id, record_id) "
                "VALUES (:identity_key, NULL, :record_id)"
            ),
            {"identity_key": f"integration:{record_id}", "record_id": record_id},
        )

    from artificial_scientist.authorization import TenantDirectory

    security_event_id = TenantDirectory(database_url).audit(
        principal_id=None,
        tenant_id=None,
        action="run:read",
        target_type="run",
        target_id="integration-run",
        outcome="failed",
    )
    mutations = [
        ("UPDATE research_records SET payload_json = '{}' WHERE id = :id", record_id),
        ("DELETE FROM audit_events WHERE event_id = :id", event_id),
        ("DELETE FROM source_identity WHERE record_id = :id", record_id),
        (
            "DELETE FROM asds_security_audit WHERE event_id = :id",
            security_event_id,
        ),
    ]
    for statement, identifier in mutations:
        with pytest.raises(DBAPIError):
            with engine.begin() as connection:
                connection.execute(text(statement), {"id": identifier})


def test_postgresql_tenant_directory_persists_membership_and_audit(
    database_url: str,
) -> None:
    from uuid import uuid4

    from artificial_scientist.authorization import (
        AuthorizationDenied,
        TenantDirectory,
        stable_principal_id,
        stable_tenant_id,
    )

    suffix = str(uuid4())
    directory = TenantDirectory(database_url)
    principal_id = directory.register_principal(
        "https://integration.example/", f"subject:{suffix}"
    )
    tenant_id = directory.create_tenant(f"tenant:{suffix}", f"Integration {suffix}")
    assert principal_id == stable_principal_id(
        "https://integration.example/", f"subject:{suffix}"
    )
    assert tenant_id == stable_tenant_id(f"tenant:{suffix}")

    directory.grant_membership(principal_id, tenant_id, "researcher")
    membership = directory.authorize(principal_id, tenant_id, "run:read")
    assert membership.role == "researcher"

    with pytest.raises(AuthorizationDenied):
        directory.authorize(principal_id, tenant_id, "retention:purge")

    directory.revoke_membership(principal_id, tenant_id)
    with pytest.raises(AuthorizationDenied):
        directory.authorize(principal_id, tenant_id, "run:read")

    events = directory.list_audit_events(tenant_id, limit=20)
    assert {event["outcome"] for event in events} == {"allowed", "denied"}
    assert all(event["tenant_id"] == tenant_id for event in events)


def test_postgresql_tenant_directory_rejects_sensitive_audit_metadata(
    database_url: str,
) -> None:
    from artificial_scientist.authorization import TenantDirectory

    directory = TenantDirectory(database_url)
    with pytest.raises(ValueError, match="credentials or payloads"):
        directory.audit(
            principal_id=None,
            tenant_id=None,
            action="run:read",
            target_type="run",
            target_id="run-1",
            outcome="failed",
            metadata={"access_token": "must-not-be-stored"},
        )
