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
    lab_api_key: str | None
    oidc_issuer: str | None
    oidc_audience: str | None
    oidc_jwks_url: str | None
    model_provider: str | None = None
    model_base_url: str | None = None
    model_name: str | None = None
    model_api_key: str | None = None
    model_timeout_seconds: str = "30"
    model_max_tokens: str = "1200"


def get_settings() -> Settings:
    """Read settings with production-safe defaults; local development is opt-in."""
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
        environment=os.getenv("ARTIFICIAL_SCIENTIST_ENV", "production"),
        allowed_origins=allowed_origins,
        database_path=os.getenv(
            "ARTIFICIAL_SCIENTIST_DB_PATH", "data/artificial_scientist.sqlite3"
        ),
        openalex_api_key=os.getenv("OPENALEX_API_KEY") or None,
        crossref_contact_email=os.getenv("CROSSREF_CONTACT_EMAIL") or None,
        lab_api_key=os.getenv("ARTIFICIAL_SCIENTIST_LAB_API_KEY") or None,
        oidc_issuer=os.getenv("ARTIFICIAL_SCIENTIST_OIDC_ISSUER") or None,
        oidc_audience=os.getenv("ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE") or None,
        oidc_jwks_url=os.getenv("ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL") or None,
        model_provider=os.getenv("ARTIFICIAL_SCIENTIST_MODEL_PROVIDER") or None,
        model_base_url=os.getenv("ARTIFICIAL_SCIENTIST_MODEL_BASE_URL") or None,
        model_name=os.getenv("ARTIFICIAL_SCIENTIST_MODEL_NAME") or None,
        model_api_key=os.getenv("ARTIFICIAL_SCIENTIST_MODEL_API_KEY") or None,
        model_timeout_seconds=os.getenv("ARTIFICIAL_SCIENTIST_MODEL_TIMEOUT_SECONDS", "30"),
        model_max_tokens=os.getenv("ARTIFICIAL_SCIENTIST_MODEL_MAX_TOKENS", "1200"),
    )
