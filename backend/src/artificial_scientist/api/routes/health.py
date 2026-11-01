"""Process health and dependency-aware application readiness endpoints."""

from fastapi import APIRouter, HTTPException, status

from artificial_scientist.config import get_settings
from artificial_scientist.database import check_database_connection

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/health", summary="Check whether the API process is responding")
def health_check() -> dict[str, str]:
    """Report process liveness without implying dependency or research readiness."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/ready", summary="Check whether required application dependencies are ready")
def readiness_check() -> dict[str, str]:
    """Check PostgreSQL when configured and require it in production."""
    settings = get_settings()
    if not settings.database_url:
        if settings.environment.lower() == "development":
            return {
                "status": "ready",
                "service": settings.app_name,
                "scope": "application_only",
            }
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Required PostgreSQL database is not configured.",
        )

    try:
        check_database_connection(settings.database_url)
    except Exception as error:
        # Return no connection details, credentials, hostnames, or SQL diagnostics.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Required database dependency is unavailable.",
        ) from error

    return {
        "status": "ready",
        "service": settings.app_name,
        "scope": "postgresql",
        "database": "connected",
    }
