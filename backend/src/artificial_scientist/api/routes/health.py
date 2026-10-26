"""Process health and application readiness endpoints."""

from fastapi import APIRouter

from artificial_scientist.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/health", summary="Check whether the API process is responding")
def health_check() -> dict[str, str]:
    """Report API process health without implying research capability."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/ready", summary="Check whether the API application is ready")
def readiness_check() -> dict[str, str]:
    """Report application readiness; external dependencies are not checked yet."""
    settings = get_settings()
    return {
        "status": "ready",
        "service": settings.app_name,
        "scope": "application_only",
    }
