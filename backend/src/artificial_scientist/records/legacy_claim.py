"""Explicit, audited operator workflow for claiming legacy research records.

Dry-run is the default. Applying claims requires an existing operator principal,
an existing tenant, and an explicit manifest. Conflicting ownership always fails.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from artificial_scientist.records.models import SourceRecord
from artificial_scientist.records.store import _source_identity_lookup_key


class LegacyRecordClaimError(ValueError):
    """Raised when a legacy research-record ownership claim is unsafe."""


def _normalize_claims(claims: list[dict[str, Any]]) -> list[tuple[str, str]]:
    if not isinstance(claims, list) or not claims or len(claims) > 1000:
        raise LegacyRecordClaimError("Manifest must contain between 1 and 1000 claims.")
    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            raise LegacyRecordClaimError("Each claim must be an object.")
        try:
            record_id = str(UUID(str(claim["record_id"])))
            tenant_id = str(UUID(str(claim["tenant_id"])))
        except (KeyError, TypeError, ValueError) as error:
            raise LegacyRecordClaimError(
                "Each claim needs valid record_id and tenant_id UUIDs."
            ) from error
        if record_id in seen:
            raise LegacyRecordClaimError("A record may appear only once in a claim manifest.")
        seen.add(record_id)
        normalized.append((record_id, tenant_id))
    return normalized


def claim_legacy_records(
    database_path: str,
    claims: list[dict[str, Any]],
    *,
    apply: bool = False,
    operator_principal_id: str | None = None,
) -> dict[str, Any]:
    """Validate claims and optionally assign ownership atomically with security audits."""
    normalized = _normalize_claims(claims)
    if apply and not operator_principal_id:
        raise LegacyRecordClaimError("Applying claims requires an operator principal ID.")
    if operator_principal_id is not None:
        try:
            operator_principal_id = str(UUID(operator_principal_id))
        except ValueError as error:
            raise LegacyRecordClaimError(
                "Operator principal ID must be a UUID."
            ) from error

    path = Path(database_path)
    if database_path != ":memory:" and not path.is_file():
        raise LegacyRecordClaimError(
            "Database file does not exist; refusing to initialize a new database."
        )

    connection = sqlite3.connect(database_path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        tables = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required = {
            "research_records",
            "source_identity",
            "asds_tenants",
            "asds_principals",
            "asds_security_audit",
        }
        if not required.issubset(tables):
            raise LegacyRecordClaimError(
                "Database is missing required research or authorization tables."
            )

        connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        if apply:
            operator = connection.execute(
                "SELECT 1 FROM asds_principals WHERE principal_id = ?",
                (operator_principal_id,),
            ).fetchone()
            if operator is None:
                raise LegacyRecordClaimError(
                    "Operator principal does not exist in the tenant directory."
                )

        planned: list[dict[str, Any]] = []
        for record_id, tenant_id in normalized:
            if connection.execute(
                "SELECT 1 FROM asds_tenants WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone() is None:
                raise LegacyRecordClaimError(
                    f"Target tenant does not exist for record {record_id}."
                )

            record = connection.execute(
                "SELECT tenant_id, record_type, payload_json FROM research_records "
                "WHERE id = ?",
                (record_id,),
            ).fetchone()
            if record is None:
                raise LegacyRecordClaimError(
                    f"No research record exists for {record_id}."
                )
            owner = record["tenant_id"]
            if owner is not None and owner != tenant_id:
                raise LegacyRecordClaimError(
                    f"Conflicting existing tenant ownership for record {record_id}."
                )

            source_identity_key = None
            if record["record_type"] == "source":
                source = SourceRecord.model_validate_json(str(record["payload_json"]))
                source_identity_key = _source_identity_lookup_key(source, tenant_id)
                conflict = connection.execute(
                    "SELECT record_id FROM source_identity WHERE identity_key = ?",
                    (source_identity_key,),
                ).fetchone()
                if conflict is not None and str(conflict["record_id"]) != record_id:
                    raise LegacyRecordClaimError(
                        f"Source identity conflicts with record {conflict['record_id']}."
                    )

            planned.append(
                {
                    "record_id": record_id,
                    "tenant_id": tenant_id,
                    "record_type": str(record["record_type"]),
                    "needs_claim": owner is None,
                    "source_identity_key": source_identity_key,
                }
            )

        if apply:
            connection.execute("DROP TRIGGER IF EXISTS research_records_no_update")
            connection.execute("DROP TRIGGER IF EXISTS source_identity_no_update")
            connection.execute("DROP TRIGGER IF EXISTS source_identity_no_delete")
            try:
                now = datetime.now(UTC).isoformat()
                for item in planned:
                    if item["needs_claim"]:
                        connection.execute(
                            "UPDATE research_records SET tenant_id = ? "
                            "WHERE id = ? AND tenant_id IS NULL",
                            (item["tenant_id"], item["record_id"]),
                        )
                    if item["record_type"] == "source":
                        connection.execute(
                            "UPDATE source_identity SET identity_key = ?, tenant_id = ? "
                            "WHERE record_id = ?",
                            (
                                item["source_identity_key"],
                                item["tenant_id"],
                                item["record_id"],
                            ),
                        )
                    event_id = str(uuid4())
                    connection.execute(
                        """INSERT INTO asds_security_audit
                        (event_id, occurred_at, principal_id, tenant_id, action,
                         target_type, target_id, outcome, correlation_id, metadata_json)
                        VALUES (?, ?, ?, ?, 'legacy:record-claim', 'record', ?,
                                'allowed', ?, ?)""",
                        (
                            event_id,
                            now,
                            operator_principal_id,
                            item["tenant_id"],
                            item["record_id"],
                            event_id,
                            json.dumps(
                                {
                                    "operation": "operator_legacy_record_claim",
                                    "record_type": item["record_type"],
                                },
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                        ),
                    )
                connection.execute(
                    """CREATE TRIGGER IF NOT EXISTS research_records_no_update
                    BEFORE UPDATE ON research_records
                    BEGIN
                        SELECT RAISE(ABORT, 'research records are append-only');
                    END"""
                )
                connection.execute(
                    """CREATE TRIGGER IF NOT EXISTS source_identity_no_update
                    BEFORE UPDATE ON source_identity
                    BEGIN
                        SELECT RAISE(ABORT, 'source identities are append-only');
                    END"""
                )
                connection.execute(
                    """CREATE TRIGGER IF NOT EXISTS source_identity_no_delete
                    BEFORE DELETE ON source_identity
                    BEGIN
                        SELECT RAISE(ABORT, 'source identities are append-only');
                    END"""
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        else:
            connection.rollback()

        return {
            "mode": "apply" if apply else "dry-run",
            "claims_checked": len(planned),
            "claims_to_update": sum(item["needs_claim"] for item in planned),
            "claims": planned,
        }
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, help="Existing SQLite database path.")
    parser.add_argument("--manifest", required=True, help="JSON file containing a claims array.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply validated claims; without this flag the command only dry-runs.",
    )
    parser.add_argument(
        "--operator-principal-id",
        help="Existing internal principal UUID; required with --apply.",
    )
    args = parser.parse_args()
    try:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or set(manifest) != {"claims"}:
            raise LegacyRecordClaimError(
                'Manifest must be an object with exactly one "claims" field.'
            )
        result = claim_legacy_records(
            args.database,
            manifest["claims"],
            apply=args.apply,
            operator_principal_id=args.operator_principal_id,
        )
    except (OSError, json.JSONDecodeError, LegacyRecordClaimError, sqlite3.Error) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
