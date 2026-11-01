"""SQLite-backed per-tenant daily AI request and token reservations."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class AiBudgetExceeded(ValueError):
    """Raised when a tenant reaches its daily AI request or token budget."""


class AiInvocationBudgetStore:
    """Reserve daily inference budgets atomically across API processes."""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_invocation_budget (
                    reservation_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    day_utc TEXT NOT NULL,
                    requested_tokens INTEGER NOT NULL CHECK(requested_tokens BETWEEN 1 AND 2048),
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(
                        status IN ('reserved','completed','failed','unrecorded')
                    ),
                    prompt_sha256 TEXT,
                    response_sha256 TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    record_id TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ai_invocation_budget_tenant_day
                ON ai_invocation_budget(tenant_id, day_utc, created_at)
                """
            )
            connection.commit()

    def reserve(
        self,
        *,
        tenant_id: str,
        requested_tokens: int,
        provider: str,
        model: str,
        daily_request_limit: int,
        daily_token_budget: int,
    ) -> str:
        if not tenant_id or len(tenant_id) > 200:
            raise ValueError("A bounded tenant identifier is required for AI inference.")
        if not 1 <= requested_tokens <= 2048:
            raise ValueError("Requested model tokens exceed the accepted range.")
        if not 1 <= daily_request_limit <= 10_000:
            raise ValueError("Daily AI request limit must be between 1 and 10,000.")
        if not 1 <= daily_token_budget <= 10_000_000:
            raise ValueError("Daily AI token budget must be between 1 and 10,000,000.")
        if not provider or not model or len(model) > 200:
            raise ValueError("Provider and model identifiers are required.")

        now = datetime.now(UTC)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        reservation_id = str(uuid4())
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT COUNT(*) AS request_count,
                       COALESCE(SUM(requested_tokens), 0) AS reserved_tokens
                FROM ai_invocation_budget
                WHERE tenant_id = ? AND day_utc = ?
                """,
                (tenant_id, day_start.date().isoformat()),
            ).fetchone()
            request_count = int(row["request_count"])
            reserved_tokens = int(row["reserved_tokens"])
            if request_count >= daily_request_limit:
                connection.rollback()
                raise AiBudgetExceeded("Tenant daily AI request limit has been reached.")
            if reserved_tokens + requested_tokens > daily_token_budget:
                connection.rollback()
                raise AiBudgetExceeded("Tenant daily AI token budget would be exceeded.")
            connection.execute(
                """
                INSERT INTO ai_invocation_budget (
                    reservation_id, tenant_id, day_utc, requested_tokens,
                    provider, model, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'reserved', ?)
                """,
                (
                    reservation_id,
                    tenant_id,
                    day_start.date().isoformat(),
                    requested_tokens,
                    provider,
                    model,
                    now.isoformat(),
                ),
            )
            connection.commit()
        return reservation_id

    def finalize(
        self,
        reservation_id: str,
        *,
        status: str,
        prompt_sha256: str | None = None,
        response_sha256: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        record_id: str | None = None,
    ) -> None:
        if status not in {"completed", "failed", "unrecorded"}:
            raise ValueError("Invalid AI invocation reservation status.")
        for name, value in (
            ("prompt_sha256", prompt_sha256),
            ("response_sha256", response_sha256),
        ):
            if value is not None and (
                len(value) != 64 or any(char not in "0123456789abcdef" for char in value)
            ):
                raise ValueError(f"{name} must be a SHA-256 hex digest.")
        for value in (input_tokens, output_tokens):
            if value is not None and (isinstance(value, bool) or not 0 <= value <= 10**9):
                raise ValueError("Token usage values must be non-negative bounded integers.")

        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    UPDATE ai_invocation_budget
                    SET status = ?, prompt_sha256 = ?, response_sha256 = ?,
                        input_tokens = ?, output_tokens = ?, record_id = ?, completed_at = ?
                    WHERE reservation_id = ? AND status = 'reserved'
                    """,
                    (
                        status,
                        prompt_sha256,
                        response_sha256,
                        input_tokens,
                        output_tokens,
                        record_id,
                        now,
                        reservation_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("AI invocation reservation is missing or already finalized.")
