"""Tests for typed research records, provenance, and append-only persistence."""

import json
import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from artificial_scientist.api.routes.records import get_record_store
from artificial_scientist.main import app
from artificial_scientist.records.models import ResearchTaskRecord
from artificial_scientist.records.store import (
    RecordIntegrityError,
    RecordNotFound,
    RecordStore,
    RecordStoreError,
    UnsupportedDatabaseVersion,
)


@pytest.fixture
def store(tmp_path) -> RecordStore:
    return RecordStore(tmp_path / "research-test.sqlite3")


@pytest.fixture
def client(store: RecordStore):
    app.dependency_overrides[get_record_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_task(client: TestClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "record_type": "research_task",
        "title": "Compare numerical solvers",
        "research_question": "How do two numerical solvers compare on a defined test equation?",
        "objective": "Record a bounded computational research question.",
    }
    payload.update(overrides)
    response = client.post("/api/v1/records", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_source(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/records",
        json={
            "record_type": "source",
            "title": "Example numerical methods article",
            "source_url": "https://example.org/numerical-methods",
            "source_kind": "journal_article",
            "authors": ["Example Author"],
            "assessment_status": "unassessed",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_get_and_checksum_round_trip(client: TestClient) -> None:
    created = create_task(client)
    assert created["record_type"] == "research_task"
    assert len(created["content_sha256"]) == 64
    assert created["payload"]["title"] == "Compare numerical solvers"

    fetched = client.get(f"/api/v1/records/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["content_sha256"] == created["content_sha256"]
    assert fetched.json()["payload"] == created["payload"]


def test_list_filter_and_pagination(client: TestClient) -> None:
    create_task(client)
    create_source(client)
    create_task(
        client,
        title="Compare integration strategies",
        research_question="Which integration strategy performs better on the chosen equation?",
    )

    filtered = client.get("/api/v1/records", params={"record_type": "research_task", "limit": 1})
    assert filtered.status_code == 200
    data = filtered.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["items"][0]["record_type"] == "research_task"

    second_page = client.get(
        "/api/v1/records",
        params={"record_type": "research_task", "limit": 1, "offset": 1},
    )
    assert second_page.status_code == 200
    assert second_page.json()["total"] == 2
    assert len(second_page.json()["items"]) == 1


def test_source_to_claim_relationship_is_validated(client: TestClient) -> None:
    source = create_source(client)
    source_id = source["id"]

    claim = client.post(
        "/api/v1/records",
        json={
            "record_type": "claim",
            "claim_text": "This source reports a numerical convergence result.",
            "evidence_status": "source_reported",
            "source_record_ids": [source_id],
        },
    )
    assert claim.status_code == 201, claim.text
    assert claim.json()["payload"]["source_record_ids"] == [source_id]

    missing_source = client.post(
        "/api/v1/records",
        json={
            "record_type": "claim",
            "claim_text": "This claim references an absent source record.",
            "source_record_ids": [str(uuid4())],
        },
    )
    assert missing_source.status_code == 422
    assert "does not exist" in missing_source.json()["detail"]


def test_relationship_must_match_the_expected_record_type(client: TestClient) -> None:
    task = create_task(client)
    response = client.post(
        "/api/v1/records",
        json={
            "record_type": "experiment_plan",
            "title": "Invalid plan relationship",
            "research_question": "Does the record store reject a reference of the wrong type?",
            "hypothesis_record_id": task["id"],
            "method": "This payload intentionally refers to a task instead of a hypothesis.",
            "success_criteria": ["The request is rejected."],
            "failure_criteria": ["The request is incorrectly accepted."],
        },
    )
    assert response.status_code == 422
    assert "expects record type" in response.json()["detail"]


def test_approval_api_can_record_requests_but_not_approval_decisions(
    client: TestClient,
) -> None:
    task = create_task(client)

    invalid_decision = client.post(
        "/api/v1/records",
        json={
            "record_type": "approval_request",
            "target_record_id": task["id"],
            "requested_action": "external_publication",
            "requested_by": "local researcher",
            "rationale": "Request review before external submission.",
            "status": "approved",
        },
    )
    assert invalid_decision.status_code == 422

    request_record = client.post(
        "/api/v1/records",
        json={
            "record_type": "approval_request",
            "target_record_id": task["id"],
            "requested_action": "external_publication",
            "requested_by": "local researcher",
            "rationale": "Request review before external submission.",
        },
    )
    assert request_record.status_code == 201
    assert request_record.json()["payload"]["status"] == "requested"


def test_creation_generates_server_audit_event(client: TestClient) -> None:
    record = create_task(client)
    response = client.get("/api/v1/records/audit-events")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    event = data["items"][0]
    assert event["action"] == "record.created"
    assert event["actor"] == "local-api-client"
    assert event["record_id"] == record["id"]
    assert event["content_sha256"] == record["content_sha256"]

    assert client.post("/api/v1/records/audit-events", json={}).status_code == 405


def test_append_only_records_cannot_be_updated_or_deleted(client: TestClient) -> None:
    record = create_task(client)
    record_url = f"/api/v1/records/{record['id']}"

    assert client.patch(record_url, json={"payload": {"title": "Changed"}}).status_code == 405
    assert client.delete(record_url).status_code == 405


def test_duplicate_id_conflicts_and_unknown_record_is_not_found(client: TestClient) -> None:
    record_id = str(uuid4())
    create_task(client, id=record_id)

    duplicate = client.post(
        "/api/v1/records",
        json={
            "record_type": "research_task",
            "id": record_id,
            "title": "Duplicate task ID",
            "research_question": "Will the API reject a duplicate record identifier?",
            "objective": "Check uniqueness.",
        },
    )
    assert duplicate.status_code == 409
    assert client.get(f"/api/v1/records/{uuid4()}").status_code == 404


def test_records_persist_across_store_instances_and_verify_integrity(tmp_path) -> None:
    database_path = tmp_path / "persistent.sqlite3"
    first_store = RecordStore(database_path)
    created = first_store.create(
        ResearchTaskRecord(
            title="Persistence verification",
            research_question="Does this research record persist across store instances?",
            objective="Confirm durability and stored checksums.",
        )
    )

    reopened_store = RecordStore(database_path)
    assert reopened_store.get(created.id).content_sha256 == created.content_sha256

    # Simulate out-of-band disk corruption for the integrity verification test.
    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP TRIGGER research_records_no_update")
        row = connection.execute(
            "SELECT payload_json FROM research_records WHERE id = ?", (str(created.id),)
        ).fetchone()
        assert row is not None
        tampered_payload = json.dumps({"record_type": "research_task", "tampered": True})
        connection.execute(
            "UPDATE research_records SET payload_json = ? WHERE id = ?",
            (tampered_payload, str(created.id)),
        )

    with pytest.raises(RecordIntegrityError, match="SHA-256 integrity check"):
        reopened_store.get(created.id)


def test_database_triggers_reject_direct_mutation(store: RecordStore) -> None:
    created = store.create(
        ResearchTaskRecord(
            title="Append-only invariant",
            research_question="Can a stored record be overwritten outside the API?",
            objective="Verify the database-level append-only policy.",
        )
    )
    with sqlite3.connect(store.path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE research_records SET payload_json = payload_json WHERE id = ?",
                (str(created.id),),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM research_records WHERE id = ?", (str(created.id),)
            )


def test_record_schema_rejects_unrecognized_fields(client: TestClient) -> None:
    response = client.post(
        "/api/v1/records",
        json={
            "record_type": "research_task",
            "title": "Reject unknown fields",
            "research_question": "Does strict validation reject an unrecognized field?",
            "objective": "Prevent silently accepted schema drift.",
            "claimed_verified": True,
        },
    )
    assert response.status_code == 422


def test_future_database_schema_is_rejected(tmp_path) -> None:
    database_path = tmp_path / "future-schema.sqlite3"
    RecordStore(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA user_version = 99")

    with pytest.raises(UnsupportedDatabaseVersion, match="newer than supported"):
        RecordStore(database_path)


def test_audit_events_are_append_only(store: RecordStore) -> None:
    store.create(
        ResearchTaskRecord(
            title="Audit immutability",
            research_question="Can an audit event be overwritten or deleted?",
            objective="Verify append-only audit protections.",
        )
    )
    with sqlite3.connect(store.path) as connection:
        event = connection.execute(
            "SELECT event_id FROM audit_events LIMIT 1"
        ).fetchone()
        assert event is not None
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE audit_events SET action = action WHERE event_id = ?",
                (event[0],),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM audit_events WHERE event_id = ?", (event[0],)
            )


def test_record_and_audit_writes_roll_back_together(store: RecordStore) -> None:
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_test_audit_event
            BEFORE INSERT ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'injected audit-write failure');
            END
            """
        )

    record = ResearchTaskRecord(
        title="Atomic creation",
        research_question="Does a failed audit write also roll back the record?",
        objective="Ensure record and audit events commit in one transaction.",
    )
    with pytest.raises(RecordStoreError, match="persist the record"):
        store.create(record)

    with pytest.raises(RecordNotFound):
        store.get(record.id)

    records, record_count = store.list_records()
    audit_events, event_count = store.list_audit_events()
    assert records == []
    assert audit_events == []
    assert record_count == 0
    assert event_count == 0



def test_legacy_hypothesis_payload_preserves_checksum_after_schema_additions(
    store: RecordStore,
) -> None:
    """Older valid payloads remain byte-equivalent to the checksum returned by the API."""
    import hashlib
    from datetime import UTC, datetime

    from artificial_scientist.records.models import HypothesisRecord

    record = HypothesisRecord(
        title="Legacy hypothesis",
        hypothesis="A legacy hypothesis payload remains verifiable after schema additions.",
        falsification_criteria=["The predefined effect is not observed."],
    )
    payload = record.model_dump(mode="json")
    payload.pop("predictions")
    payload.pop("discriminating_test")
    payload_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    checksum = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    created_at = datetime.now(UTC).isoformat()

    with sqlite3.connect(store.path) as connection:
        connection.execute(
            """
            INSERT INTO research_records
                (id, record_type, schema_version, created_at, content_sha256, payload_json)
            VALUES (?, 'hypothesis', ?, ?, ?, ?)
            """,
            (str(record.id), record.schema_version, created_at, checksum, payload_json),
        )

    fetched = store.get(record.id)
    assert fetched.content_sha256 == checksum
    assert fetched.payload == payload
    assert "predictions" not in fetched.payload
    assert "discriminating_test" not in fetched.payload
