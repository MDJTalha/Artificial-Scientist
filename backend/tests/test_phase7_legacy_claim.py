"""Tests for the explicit legacy research-record ownership workflow."""

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from artificial_scientist.authorization import TenantDirectory
from artificial_scientist.records.legacy_claim import (
    LegacyRecordClaimError,
    claim_legacy_records,
)
from artificial_scientist.records.models import ResearchTaskRecord, SourceRecord
from artificial_scientist.records.store import RecordStore


def _tenant_and_operator(database: Path) -> tuple[str, str]:
    directory = TenantDirectory(str(database))
    principal_id = directory.register_principal("https://issuer.example", f"operator:{uuid4()}")
    tenant_id = directory.create_tenant(f"tenant:{uuid4()}", "Legacy claim tenant")
    return tenant_id, principal_id


def test_dry_run_does_not_assign_legacy_record(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    store = RecordStore(database)
    record = store.create(
        ResearchTaskRecord(
            title="Legacy record",
            research_question="A legacy question",
            objective="Preserve explicit ownership migration.",
        )
    )
    tenant_id, operator_id = _tenant_and_operator(database)

    result = claim_legacy_records(
        str(database),
        [{"record_id": str(record.id), "tenant_id": tenant_id}],
        operator_principal_id=operator_id,
    )

    assert result["mode"] == "dry-run"
    assert result["claims_to_update"] == 1
    assert store.get(record.id, tenant_id=None).id == record.id
    assert store.find_source_by_identity(SourceRecord(
        title="unused",
        source_url="https://example.org/unused",
        external_identifier="unused",
    )) is None


def test_apply_assigns_record_and_writes_security_audit(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    store = RecordStore(database)
    record = store.create(
        ResearchTaskRecord(
            title="Legacy record",
            research_question="A legacy question",
            objective="Preserve explicit ownership migration.",
        )
    )
    tenant_id, operator_id = _tenant_and_operator(database)

    result = claim_legacy_records(
        str(database),
        [{"record_id": str(record.id), "tenant_id": tenant_id}],
        apply=True,
        operator_principal_id=operator_id,
    )

    assert result["mode"] == "apply"
    with pytest.raises(Exception):
        store.get(record.id, tenant_id=None)
    assert store.get(record.id, tenant_id=tenant_id).id == record.id
    with sqlite3.connect(database) as connection:
        event = connection.execute(
            "SELECT action, tenant_id, target_id FROM asds_security_audit "
            "WHERE target_id = ?",
            (str(record.id),),
        ).fetchone()
    assert event == ("legacy:record-claim", tenant_id, str(record.id))


def test_source_claim_rekeys_identity_inside_the_same_transaction(tmp_path: Path) -> None:
    database = tmp_path / "legacy-source.sqlite3"
    store = RecordStore(database)
    source = SourceRecord(
        title="Legacy source",
        source_url="https://example.org/legacy",
        external_identifier=f"legacy:{uuid4()}",
    )
    store.create(source)
    tenant_id, operator_id = _tenant_and_operator(database)

    claim_legacy_records(
        str(database),
        [{"record_id": str(source.id), "tenant_id": tenant_id}],
        apply=True,
        operator_principal_id=operator_id,
    )

    claimed = store.find_source_by_identity(source, tenant_id=tenant_id)
    assert claimed is not None
    assert claimed.id == source.id
    assert store.find_source_by_identity(source, tenant_id=None) is None


def test_conflicting_claim_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "conflict.sqlite3"
    store = RecordStore(database)
    record = store.create(
        ResearchTaskRecord(
            title="Legacy record",
            research_question="A legacy question",
            objective="Conflict test.",
        )
    )
    tenant_a, operator_id = _tenant_and_operator(database)
    tenant_b = TenantDirectory(str(database)).create_tenant(
        f"tenant:{uuid4()}", "Second tenant"
    )

    claim_legacy_records(
        str(database),
        [{"record_id": str(record.id), "tenant_id": tenant_a}],
        apply=True,
        operator_principal_id=operator_id,
    )
    with pytest.raises(LegacyRecordClaimError, match="Conflicting existing tenant"):
        claim_legacy_records(
            str(database),
            [{"record_id": str(record.id), "tenant_id": tenant_b}],
            apply=True,
            operator_principal_id=operator_id,
        )
    assert store.get(record.id, tenant_id=tenant_a).id == record.id
