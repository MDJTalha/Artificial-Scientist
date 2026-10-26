"""Opt-in retention job for deployment schedulers.

Run with python -m artificial_scientist.lab.retention from the backend
environment. The job is intentionally not started by the API process.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from artificial_scientist.config import get_settings
from artificial_scientist.lab.store import LabRunStore

_MAX_BATCH_SIZE = 100
_MAX_RETENTION_DAYS = 36_500


def run_retention(
    store: LabRunStore,
    retention_days: int,
    *,
    now: datetime | None = None,
) -> int:
    """Purge expired runs in bounded transactions and return the number removed."""
    if isinstance(retention_days, bool) or not 1 <= retention_days <= _MAX_RETENTION_DAYS:
        raise ValueError(f"retention_days must be between 1 and {_MAX_RETENTION_DAYS}.")
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("now must include a timezone.")
    cutoff = (current_time.astimezone(UTC) - timedelta(days=retention_days)).isoformat()
    deleted_count = 0
    while True:
        deleted = store.purge_runs_before(
            cutoff,
            limit=_MAX_BATCH_SIZE,
            reason=f"scheduled_retention_{retention_days}_days",
        )
        deleted_count += len(deleted)
        if len(deleted) < _MAX_BATCH_SIZE:
            return deleted_count


def main() -> int:
    """Run only when an operator explicitly configures a retention period."""
    configured_days = os.getenv("ARTIFICIAL_SCIENTIST_LAB_RETENTION_DAYS")
    if configured_days is None:
        raise SystemExit(
            "Retention is disabled: set ARTIFICIAL_SCIENTIST_LAB_RETENTION_DAYS "
            "to an explicit value between 1 and 36500."
        )
    try:
        retention_days = int(configured_days)
    except ValueError as error:
        raise SystemExit("ARTIFICIAL_SCIENTIST_LAB_RETENTION_DAYS must be an integer.") from error
    settings = get_settings()
    store = LabRunStore(settings.database_path)
    deleted_count = run_retention(store, retention_days)
    print(f"Retention job complete: deleted {deleted_count} expired run(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
