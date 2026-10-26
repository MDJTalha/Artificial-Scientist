"""Small, dependency-light application configuration."""

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    app_name: str
    app_version: str
    environment: str
    allowed_origins: tuple[str, ...]
    database_path: str
    openalex_api_key: str | None
    crossref_contact_email: str | None


def get_settings() -> Settings:
    """Read settings; defaults are intended for local development."""
    configured_origins = os.getenv(
        "ARTIFICIAL_SCIENTIST_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    allowed_origins = tuple(
        origin.strip()
        for origin in configured_origins.split(",")
        if origin.strip()
    )

    return Settings(
        app_name=os.getenv("ARTIFICIAL_SCIENTIST_NAME", "Artificial Scientist"),
        app_version=os.getenv("ARTIFICIAL_SCIENTIST_VERSION", "0.1.0"),
        environment=os.getenv("ARTIFICIAL_SCIENTIST_ENV", "development"),
        allowed_origins=allowed_origins,
        database_path=os.getenv(
            "ARTIFICIAL_SCIENTIST_DB_PATH", "data/artificial_scientist.sqlite3"
        ),
        openalex_api_key=os.getenv("OPENALEX_API_KEY") or None,
        crossref_contact_email=os.getenv("CROSSREF_CONTACT_EMAIL") or None,
    )
