"""Persistence and integrity tests for controlled-lab runs."""

import json
import sqlite3

import pytest

from artificial_scientist.lab.engine import run_lab
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
