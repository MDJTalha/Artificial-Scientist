"""Persistence and integrity tests for controlled-lab runs."""

import json
import sqlite3

import pytest

from artificial_scientist.lab.engine import run_lab
from artificial_scientist.lab.integrity import result_digest
from artificial_scientist.lab.models import LabRunRequest
from artificial_scientist.lab.store import LabRunNotFound, LabRunStore


def _sample_run():
    return run_lab(
        LabRunRequest(
            title="Persisted statistics",
            steps=[
                {
                    "step_id": "summary",
                    "operation": "statistics",
                    "inputs": {"values": [2, 4, 6], "variance_mode": "population"},
                }
            ],
        )
    )


def test_lab_run_survives_store_recreation_and_lists_with_total(tmp_path) -> None:
    database = str(tmp_path / "lab-runs.sqlite3")
    original = _sample_run()
    LabRunStore(database).save(original)

    reopened = LabRunStore(database)
    restored = reopened.get(original.run_id)
    items, total = reopened.list_runs(limit=10, offset=0)

    assert restored.run_id == original.run_id
    assert restored.result_sha256 == original.result_sha256
    assert restored.steps[0].output == original.steps[0].output
    assert total == 1
    assert len(items) == 1


def test_lab_store_rejects_missing_run_and_detects_payload_tampering(tmp_path) -> None:
    database = str(tmp_path / "lab-runs.sqlite3")
    store = LabRunStore(database)
    run = _sample_run()
    store.save(run)

    with pytest.raises(LabRunNotFound):
        store.get("00000000-0000-0000-0000-000000000000")

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT payload_json FROM lab_runs WHERE run_id = ?", (str(run.run_id),)
        ).fetchone()
        payload = row[0].replace('"status":"completed"', '"status":"failed"')
        connection.execute(
            "UPDATE lab_runs SET payload_json = ? WHERE run_id = ?",
            (payload, str(run.run_id)),
        )

    with pytest.raises(RuntimeError, match="hash does not match"):
        store.get(run.run_id)



def test_lab_store_detects_tampering_outside_step_results(tmp_path) -> None:
    database = str(tmp_path / "lab-runs.sqlite3")
    store = LabRunStore(database)
    run = _sample_run()
    store.save(run)

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT payload_json FROM lab_runs WHERE run_id = ?", (str(run.run_id),)
        ).fetchone()
        payload = json.loads(row[0])
        payload["title"] = "Altered title"
        connection.execute(
            "UPDATE lab_runs SET payload_json = ? WHERE run_id = ?",
            (json.dumps(payload), str(run.run_id)),
        )

    with pytest.raises(RuntimeError, match="hash does not match"):
        store.get(run.run_id)



def test_run_result_artifact_is_durable_and_provenance_linked(tmp_path) -> None:
    database = str(tmp_path / "lab-artifacts.sqlite3")
    store = LabRunStore(database)
    run = _sample_run()
    store.save(run)

    reopened = LabRunStore(database)
    artifacts = reopened.list_artifacts(run.run_id)
    assert len(artifacts) == 1
    metadata = artifacts[0]
    assert metadata.run_id == run.run_id
    assert metadata.artifact_type == "run-result-json"
    assert metadata.provenance["configuration_sha256"] == run.configuration_sha256
    assert metadata.provenance["result_sha256"] == run.result_sha256
    assert metadata.provenance["step_ids"] == ["summary"]

    artifact = reopened.get_artifact(metadata.artifact_id)
    assert artifact.sha256 == metadata.sha256
    assert artifact.content["run_id"] == str(run.run_id)
    assert artifact.content["steps"][0]["step_id"] == "summary"


def test_artifact_integrity_detects_content_tampering(tmp_path) -> None:
    database = str(tmp_path / "lab-artifacts.sqlite3")
    store = LabRunStore(database)
    run = _sample_run()
    store.save(run)
    artifact = store.list_artifacts(run.run_id)[0]

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE lab_artifacts SET content_json = ? WHERE artifact_id = ?",
            (b'{"corrupted":true}', str(artifact.artifact_id)),
        )

    with pytest.raises(RuntimeError, match="artifact digest"):
        store.get_artifact(artifact.artifact_id)


def test_oversized_run_artifact_is_rejected_atomically(tmp_path) -> None:
    database = str(tmp_path / "lab-artifacts.sqlite3")
    store = LabRunStore(database)
    original = _sample_run()
    payload = original.model_dump(mode="json")
    payload["logs"] = ["x" * (1_048_577)]
    payload["result_sha256"] = result_digest(payload)
    run = original.model_copy(update=payload)

    with pytest.raises(ValueError, match="1 MiB"):
        store.save(run)

    with sqlite3.connect(database) as connection:
        count = connection.execute("SELECT COUNT(*) FROM lab_runs").fetchone()[0]
    assert count == 0



def test_artifact_listing_rejects_provenance_tampering(tmp_path) -> None:
    database = str(tmp_path / "lab-artifact-provenance.sqlite3")
    store = LabRunStore(database)
    run = _sample_run()
    store.save(run)
    artifact = store.list_artifacts(run.run_id)[0]

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE lab_artifacts SET provenance_json = ? WHERE artifact_id = ?",
            (json.dumps({"run_id": "forged"}), str(artifact.artifact_id)),
        )

    with pytest.raises(RuntimeError, match="provenance"):
        store.list_artifacts(run.run_id)


def test_tenant_ownership_schema_migrates_legacy_records_without_assignment(tmp_path) -> None:
    database = str(tmp_path / "legacy-lab.sqlite3")
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE lab_runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                configuration_sha256 TEXT NOT NULL,
                result_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE lab_execution_attempts (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                configuration_sha256 TEXT NOT NULL,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                finished_at TEXT,
                failure_reason TEXT,
                result_sha256 TEXT,
                request_json TEXT NOT NULL
            );
            INSERT INTO lab_runs VALUES (
                'legacy-run', 'completed',
                'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
                '2026-01-01T00:00:00+00:00', '{}'
            );
            INSERT INTO lab_execution_attempts VALUES (
                'legacy-run', 'completed', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:01+00:00',
                '2026-01-01T00:00:01+00:00', NULL,
                'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', '{}'
            );
            """
        )

    LabRunStore(database)
    # Reopening proves the migration is safe to apply repeatedly.
    LabRunStore(database)
    with sqlite3.connect(database) as connection:
        run_tenant = connection.execute(
            "SELECT tenant_id FROM lab_runs WHERE run_id = 'legacy-run'"
        ).fetchone()[0]
        attempt_tenant = connection.execute(
            "SELECT tenant_id FROM lab_execution_attempts WHERE run_id = 'legacy-run'"
        ).fetchone()[0]
        run_columns = {row[1] for row in connection.execute("PRAGMA table_info(lab_runs)")}
        attempt_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(lab_execution_attempts)")
        }

    assert "tenant_id" in run_columns
    assert "tenant_id" in attempt_columns
    assert run_tenant is None
    assert attempt_tenant is None

