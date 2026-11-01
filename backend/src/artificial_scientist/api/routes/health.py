"""Process health and core application readiness endpoints."""

from __future__ import annotations

import sqlite3
from urllib.parse import urlsplit

from fastapi import APIRouter, Response

from artificial_scientist.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["system"])


def _valid_https_endpoint(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        return False
    return bool(
        parsed.scheme.lower() == "https"
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
        and not any(character.isspace() for character in value)
    )


def _check_database(database_path: str) -> tuple[bool, str]:
    if not database_path or database_path == ":memory:":
        return False, "A durable SQLite file path is required."
    if not database_path.startswith("/"):
        return False, "Production database path must be absolute."
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(database_path, timeout=2.0)
        quick_check = connection.execute("PRAGMA quick_check").fetchone()
        if quick_check is None or quick_check[0] != "ok":
            return False, "SQLite integrity check did not return ok."
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
        return True, "SQLite database is readable and writable."
    except (OSError, sqlite3.Error):
        return False, "SQLite database is unavailable or not writable."
    finally:
        if connection is not None:
            connection.close()


@router.get("/health", summary="Check whether the API process is responding")
def health_check() -> dict[str, str]:
    """Report API process health without implying research capability."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/ready", summary="Check core API readiness and deployment configuration")
def readiness_check(response: Response) -> dict[str, object]:
    """Check durable storage, OIDC and production CORS configuration.

    This is core API readiness, not proof of sandbox deployment, monitoring,
    independent security review, backup/restore rehearsal, or scientific validity.
    """
    settings = get_settings()
    production = settings.environment.lower() != "development"
    checks: dict[str, bool] = {}
    details: dict[str, str] = {}

    if production:
        database_ok, database_detail = _check_database(settings.database_path)
        checks["durable_database"] = database_ok
        details["durable_database"] = database_detail

        oidc_ok = bool(
            _valid_https_endpoint(settings.oidc_issuer)
            and _valid_https_endpoint(settings.oidc_jwks_url)
            and settings.oidc_audience
            and len(settings.oidc_audience) <= 512
        )
        checks["oidc_configuration"] = oidc_ok
        details["oidc_configuration"] = (
            "HTTPS issuer, audience and JWKS endpoint are configured."
            if oidc_ok
            else "A valid HTTPS issuer, API audience and HTTPS JWKS endpoint are required."
        )

        origins_ok = bool(settings.allowed_origins) and all(
            _valid_https_endpoint(origin) for origin in settings.allowed_origins
        )
        checks["https_cors_origins"] = origins_ok
        details["https_cors_origins"] = (
            "All allowed browser origins use HTTPS."
            if origins_ok
            else "Production CORS must contain one or more explicit HTTPS origins; wildcards are not allowed."
        )
    else:
        checks["development_mode"] = True
        details["development_mode"] = (
            "OIDC and tenant checks are bypassed in local development. "
            "Do not expose this environment to shared or public networks."
        )

    ready = all(checks.values())
    response.status_code = 200 if ready else 503
    return {
        "status": "ready" if ready else "not_ready",
        "service": settings.app_name,
        "scope": "core_api_configuration_and_storage",
        "checks": checks,
        "details": details,
        "capability_gates": {
            "laboratory_execution": (
                "requires_reviewed_os_sandbox_deployment_and_independent_acceptance"
            ),
            "ai_inference": "requires_configured_and_approved_model_provider",
            "production_operations": (
                "requires_monitoring_alerting_backup_restore_and_incident_response_evidence"
            ),
        },
        "note": (
            "A ready response is not a production certification. External sandbox, "
            "operations, recovery, security and scientific validation gates remain separate."
        ),
    }
