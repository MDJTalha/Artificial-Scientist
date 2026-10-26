"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from artificial_scientist.api.routes.health import router as health_router
from artificial_scientist.api.routes.literature import router as literature_router
from artificial_scientist.api.routes.records import router as records_router
from artificial_scientist.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Research-first software foundation. Scientific research engines and "
        "autonomous discovery capabilities are not implemented yet."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(literature_router)
app.include_router(records_router)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    """Identify this API without overstating the current implementation."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }
