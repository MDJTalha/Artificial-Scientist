"""Safe, repeatable legacy ownership migration rehearsal on a SQLite snapshot.

This command never applies ownership claims to the source database. It snapshots the
source with SQLite's backup API, runs dry-run and apply against the temporary copy,
then verifies ownership and audit invariants before reporting success.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from artificial_scientist.legacy_claim import LegacyClaimError, claim_legacy_runs


def rehearse_legacy_claims(
    database_path: str,
    claims: list[dict[str, Any]],
    *,
    operator_principal_id: str,
) -> dict[str, Any]:
    """Rehearse claims against a consistent temporary snapshot, never the source DB."""
    source_path = Path(database_path)
    if database_path == ":memory:" or not source_path.is_file():
        raise LegacyClaimError("Rehearsal requires an existing on-disk database file.")
    if not operator_principal_id:
        raise LegacyClaimError("Rehearsal requires an operator principal ID.")

    with tempfile.TemporaryDirectory(prefix="asds-phase6-rehearsal-") as temporary:
        snapshot_path = Path(temporary) / "rehearsal.sqlite3"
        with sqlite3.connect(str(source_path), timeout=10.0) as source:
            with sqlite3.connect(str(snapshot_path), timeout=10.0) as snapshot:
                source.backup(snapshot)

        dry_run = claim_legacy_runs(str(snapshot_path), claims)
        with sqlite3.connect(str(snapshot_path), timeout=10.0) as connection:
            connection.row_factory = sqlite3.Row
            before_audit_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM asds_security_audit WHERE action = 'legacy:claim'"
                ).fetchone()[0]
            )

        applied = claim_legacy_runs(
            str(snapshot_path),
            claims,
            apply=True,
            operator_principal_id=operator_principal_id,
        )

        normalized_claims = applied["claims"]
        with sqlite3.connect(str(snapshot_path), timeout=10.0) as connection:
            connection.row_factory = sqlite3.Row
            after_audit_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM asds_security_audit WHERE action = 'legacy:claim'"
                ).fetchone()[0]
            )
            if after_audit_count - before_audit_count != len(normalized_claims):
                raise LegacyClaimError("Rehearsal audit count does not match the claim manifest.")

            for claim in normalized_claims:
                run_id = claim["run_id"]
                tenant_id = claim["tenant_id"]
                run = connection.execute(
                    "SELECT tenant_id FROM lab_runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                attempt = connection.execute(
                    "SELECT tenant_id FROM lab_execution_attempts WHERE run_id = ?", (run_id,)
                ).fetchone()
                if run is None and attempt is None:
                    raise LegacyClaimError(f"Rehearsal lost run and attempt {run_id}.")
                if any(
                    row is not None and row["tenant_id"] != tenant_id
                    for row in (run, attempt)
                ):
                    raise LegacyClaimError(f"Rehearsal ownership verification failed for {run_id}.")

                event = connection.execute(
                    """SELECT 1 FROM asds_security_audit
                    WHERE action = 'legacy:claim' AND target_id = ?
                      AND tenant_id = ? AND principal_id = ? AND outcome = 'allowed'
                    ORDER BY occurred_at DESC LIMIT 1""",
                    (run_id, tenant_id, operator_principal_id),
                ).fetchone()
                if event is None:
                    raise LegacyClaimError(f"Rehearsal audit verification failed for {run_id}.")

        return {
            "mode": "rehearsal",
            "source_database_modified": False,
            "claims_checked": dry_run["claims_checked"],
            "claims_that_needed_updates": dry_run["claims_to_update"],
            "claims_applied_on_temporary_snapshot": applied["claims_checked"],
            "ownership_verified": True,
            "operator_audit_verified": True,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, help="Existing SQLite database file.")
    parser.add_argument(
        "--manifest",
        required=True,
        help='JSON file with exactly {"claims": [...]}' ,
    )
    parser.add_argument("--operator-principal-id", required=True, help="Existing operator UUID.")
    args = parser.parse_args()
    try:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or set(manifest) != {"claims"}:
            raise LegacyClaimError('Manifest must be an object with exactly one "claims" field.')
        result = rehearse_legacy_claims(
            args.database,
            manifest["claims"],
            operator_principal_id=args.operator_principal_id,
        )
    except (OSError, json.JSONDecodeError, sqlite3.Error, LegacyClaimError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
