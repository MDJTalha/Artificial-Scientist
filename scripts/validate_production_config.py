"""Fail-closed preflight validation for production configuration.

This validates configuration shape only. It does not contact an identity
provider or claim that a sandbox or production deployment is certified.
"""
from __future__ import annotations
import os
from urllib.parse import urlsplit

REQUIRED = (
    "ARTIFICIAL_SCIENTIST_ENV",
    "ARTIFICIAL_SCIENTIST_OIDC_ISSUER",
    "ARTIFICIAL_SCIENTIST_OIDC_AUDIENCE",
    "ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL",
    "ARTIFICIAL_SCIENTIST_DB_PATH",
)

def main() -> int:
    failures: list[str] = []
    if os.getenv("ARTIFICIAL_SCIENTIST_ENV", "").strip().lower() != "production":
        failures.append("ARTIFICIAL_SCIENTIST_ENV must be exactly 'production'.")
    for name in REQUIRED[1:]:
        if not os.getenv(name, "").strip():
            failures.append(f"{name} is required.")
    jwks = os.getenv("ARTIFICIAL_SCIENTIST_OIDC_JWKS_URL", "").strip()
    if jwks:
        try:
            parsed = urlsplit(jwks)
            if parsed.scheme.lower() != "https" or not parsed.hostname:
                failures.append("OIDC JWKS URL must be HTTPS with a hostname.")
            if parsed.username or parsed.password or parsed.fragment:
                failures.append("OIDC JWKS URL must not contain credentials or fragments.")
        except ValueError:
            failures.append("OIDC JWKS URL is malformed.")
    execution_mode = os.getenv("ARTIFICIAL_SCIENTIST_LAB_EXECUTION_MODE", "").strip().lower()
    if not execution_mode.startswith("sandbox:"):
        failures.append(
            "ARTIFICIAL_SCIENTIST_LAB_EXECUTION_MODE must name a reviewed sandbox adapter."
        )
    if os.getenv("ARTIFICIAL_SCIENTIST_LAB_API_KEY"):
        failures.append("Do not configure the legacy LAB_API_KEY for production bearer authentication.")
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
