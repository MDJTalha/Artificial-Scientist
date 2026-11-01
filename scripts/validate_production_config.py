"""Fail-closed preflight validation for production configuration.

This validates configuration shape only. It does not contact an identity
provider or claim that a sandbox or production deployment is certified.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlsplit

REQUIRED = (
    "ARTIFICIAL_SCIENTIST_ENV",
    "ARTIFICIAL_SCIENTIST_ALLOWED_ORIGINS",
    "ARTIFICIAL_SCIENTIST_OIDC_ISSUER",
    "ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE",
    "ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL",
    "ARTIFICIAL_SCIENTIST_DB_PATH",
)


def _valid_https_url(value: str, *, allow_path: bool) -> bool:
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or any(character.isspace() for character in value)
    ):
        return False
    return allow_path or parsed.path in {"", "/"}


def validate_configuration(environment: dict[str, str]) -> list[str]:
    failures: list[str] = []
    if environment.get("ARTIFICIAL_SCIENTIST_ENV", "").strip().lower() != "production":
        failures.append("ARTIFICIAL_SCIENTIST_ENV must be exactly 'production'.")

    for name in REQUIRED[1:]:
        if not environment.get(name, "").strip():
            failures.append(f"{name} is required.")

    issuer = environment.get("ARTIFICIAL_SCIENTIST_OIDC_ISSUER", "").strip()
    if issuer and not _valid_https_url(issuer, allow_path=True):
        failures.append("OIDC issuer must be a valid HTTPS URL without credentials/query/fragment.")

    jwks = environment.get("ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL", "").strip()
    if jwks and not _valid_https_url(jwks, allow_path=True):
        failures.append("OIDC JWKS URL must be a valid HTTPS URL without credentials/query/fragment.")

    audience = environment.get("ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE", "").strip()
    if audience and (len(audience) > 512 or any(character.isspace() for character in audience)):
        failures.append("OIDC audience must be a bounded non-empty identifier.")

    database_path = environment.get("ARTIFICIAL_SCIENTIST_DB_PATH", "").strip()
    if database_path and (
        database_path == ":memory:" or not os.path.isabs(database_path)
    ):
        failures.append("Production database path must be absolute and file-backed.")

    configured_origins = environment.get(
        "ARTIFICIAL_SCIENTIST_ALLOWED_ORIGINS", ""
    ).strip()
    origins = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
    if configured_origins and not origins:
        failures.append("At least one explicit HTTPS browser origin is required.")
    for origin in origins:
        if not _valid_https_url(origin, allow_path=False) or urlsplit(origin).hostname == "*":
            failures.append("Every production CORS origin must be an explicit HTTPS origin.")
            break

    execution_mode = environment.get(
        "ARTIFICIAL_SCIENTIST_LAB_EXECUTION_MODE", ""
    ).strip().lower()
    if not execution_mode.startswith("sandbox:"):
        failures.append(
            "ARTIFICIAL_SCIENTIST_LAB_EXECUTION_MODE must name a reviewed sandbox adapter."
        )
    elif execution_mode == "sandbox:docker":
        image = environment.get("ARTIFICIAL_SCIENTIST_LAB_SANDBOX_IMAGE", "").strip()
        if not re.search(r"@sha256:[a-f0-9]{64}$", image):
            failures.append(
                "Docker sandbox image must be pinned by an immutable SHA-256 digest."
            )

    if environment.get("ARTIFICIAL_SCIENTIST_LAB_API_KEY"):
        failures.append("Do not configure the legacy LAB_API_KEY for production bearer authentication.")
    return failures


def main() -> int:
    failures = validate_configuration(dict(os.environ))
    if failures:
        print("PRODUCTION PREFLIGHT: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("PRODUCTION PREFLIGHT: PASS (configuration shape only)")
    print("No external provider, sandbox, database, or scientific certification is implied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
