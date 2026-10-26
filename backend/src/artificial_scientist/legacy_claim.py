"""Explicit, audited operator workflow for claiming legacy lab records.

Dry-run is the default. Applying claims requires an existing operator principal,
an existing tenant, and an explicit manifest; conflicting ownership always fails.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4


class LegacyClaimError(ValueError):
    """Raised when a legacy ownership claim is incomplete or conflicts."""


def _normalize_claims(claims: list[dict[str, Any]]) -> list[tuple[str, str]]:
    if not isinstance(claims, list) or not claims or len(claims) > 1000:
        raise LegacyClaimError("Manifest must contain between 1 and 1000 claims.")
    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            raise LegacyClaimError("Each claim must be an object.")
        try:
            run_id = str(UUID(str(claim["run_id"])))
            tenant_id = str(UUID(str(claim["tenant_id"])))
        except (KeyError, TypeError, ValueError) as error:
            raise LegacyClaimError("Each claim needs valid run_id and tenant_id UUIDs.") from error
        if run_id in seen:
            raise LegacyClaimError("A run may appear only once in a claim manifest.")
        seen.add(run_id)
        normalized.append((run_id, tenant_id))
    return normalized


def claim_legacy_runs(
    database_path: str,
    claims: list[dict[str, Any]],
    *,
    apply: bool = False,
    operator_principal_id: str | None = None,
) -> dict[str, Any]:
    """Validate claims and optionally assign ownership atomically with audit records."""
    normalized = _normalize_claims(claims)
    if apply and not operator_principal_id:
        raise LegacyClaimError("Applying claims requires an operator principal ID.")
    if operator_principal_id is not None:
        try:
            operator_principal_id = str(UUID(operator_principal_id))
        except ValueError as error:
            raise LegacyClaimError("Operator principal ID must be a UUID.") from error

    path = Path(database_path)
    if database_path != ":memory:" and not path.is_file():
        raise LegacyClaimError(
            "Database file does not exist; refusing to initialize a new database."
        )

    connection = sqlite3.connect(database_path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required = {
            "lab_runs",
            "lab_execution_attempts",
            "asds_tenants",
            "asds_principals",
            "asds_security_audit",
        }
        if not required.issubset(tables):
            raise LegacyClaimError("Database is missing required lab or authorization tables.")

        connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        if apply:
            operator = connection.execute(
                "SELECT 1 FROM asds_principals WHERE principal_id = ?",
                (operator_principal_id,),
            ).fetchone()
            if operator is None:
                raise LegacyClaimError("Operator principal does not exist in the tenant directory.")

        planned: list[dict[str, Any]] = []
        for run_id, tenant_id in normalized:
            if connection.execute(
                "SELECT 1 FROM asds_tenants WHERE tenant_id = ?", (tenant_id,)
            ).fetchone() is None:
                raise LegacyClaimError(f"Target tenant does not exist for run {run_id}.")

            run = connection.execute(
                "SELECT tenant_id FROM lab_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            attempt = connection.execute(
                "SELECT tenant_id FROM lab_execution_attempts WHERE run_id = ?", (run_id,)
            ).fetchone()
            if run is None and attempt is None:
                raise LegacyClaimError(f"No lab run or execution attempt exists for {run_id}.")

            owners = [
                row["tenant_id"] for row in (run, attempt) if row is not None
            ]
            if any(owner is not None and owner != tenant_id for owner in owners):
                raise LegacyClaimError(f"Conflicting existing tenant ownership for run {run_id}.")

            run_needs_claim = run is not None and run["tenant_id"] is None
            attempt_needs_claim = attempt is not None and attempt["tenant_id"] is None
            planned.append({
                "run_id": run_id,
                "tenant_id": tenant_id,
                "run_needs_claim": run_needs_claim,
                "attempt_needs_claim": attempt_needs_claim,
            })

        if apply:
            now = datetime.now(UTC).isoformat()
            for item in planned:
                if item["run_needs_claim"]:
                    connection.execute(
                        "UPDATE lab_runs SET tenant_id = ? WHERE run_id = ? AND tenant_id IS NULL",
                        (item["tenant_id"], item["run_id"]),
                    )
                if item["attempt_needs_claim"]:
                    connection.execute(
                        """UPDATE lab_execution_attempts SET tenant_id = ?
                        WHERE run_id = ? AND tenant_id IS NULL""",
                        (item["tenant_id"], item["run_id"]),
                    )
                event_id = str(uuid4())
                connection.execute(
                    """INSERT INTO asds_security_audit
                    (event_id, occurred_at, principal_id, tenant_id, action, target_type,
                     target_id, outcome, correlation_id, metadata_json)
                    VALUES (?, ?, ?, ?, 'legacy:claim', 'run', ?, 'allowed', ?, ?)""",
                    (
                        event_id,
                        now,
                        operator_principal_id,
                        item["tenant_id"],
                        item["run_id"],
                        event_id,
                        json.dumps(
                            {
                                "operation": "operator_legacy_claim",
                                "run_updated": item["run_needs_claim"],
                                "attempt_updated": item["attempt_needs_claim"],
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    ),
                )
            connection.commit()
        else:
            connection.rollback()

        return {
            "mode": "apply" if apply else "dry-run",
            "claims_checked": len(planned),
            "claims_to_update": sum(
                item["run_needs_claim"] or item["attempt_needs_claim"]
                for item in planned
            ),
            "claims": planned,
        }
    except Exception:
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
        help="Apply the validated claims; without this flag the command only dry-runs.",
    )
    parser.add_argument(
        "--operator-principal-id",
        help="Existing internal principal UUID; required with --apply.",
    )
    args = parser.parse_args()
    try:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or set(manifest) != {"claims"}:
            raise LegacyClaimError('Manifest must be an object with exactly one "claims" field.')
        result = claim_legacy_runs(
            args.database,
            manifest["claims"],
            apply=args.apply,
            operator_principal_id=args.operator_principal_id,
        )
    except (OSError, json.JSONDecodeError, LegacyClaimError, sqlite3.Error) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
