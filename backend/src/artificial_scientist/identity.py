"""OIDC bearer-token validation for protected API boundaries.

This module validates tokens against an operator-configured issuer, audience, and JWKS
endpoint. It deliberately does not implement login, issue tokens, or infer tenant membership.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

import jwt
from jwt import PyJWKClient, PyJWTError


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Minimal validated identity; tenant membership is a separate authorization concern."""

    subject: str
    issuer: str
    audience: str


class IdentityConfigurationError(RuntimeError):
    """Raised when OIDC is enabled without complete, valid configuration."""


class InvalidIdentityError(ValueError):
    """Raised when a bearer token is invalid or its claims are not accepted."""


def validate_oidc_bearer_token(
    token: str,
    *,
    issuer: str,
    audience: str,
    jwks_url: str,
    audience_claim: str = "aud",
    expected_token_use: str | None = None,
) -> AuthenticatedPrincipal:
    """Validate a signed OIDC access token using only RS256 and configured trust values."""
    if (
        not isinstance(issuer, str)
        or not issuer.strip()
        or not isinstance(audience, str)
        or not audience.strip()
        or not isinstance(jwks_url, str)
        or not jwks_url.strip()
    ):
        raise IdentityConfigurationError(
            "OIDC issuer, audience, and JWKS URL must all be configured."
        )

    try:
        parsed_jwks_url = urlsplit(jwks_url)
        # Accessing .port also validates that any explicit port is numeric and in range.
        _ = parsed_jwks_url.port
    except ValueError as error:
        raise IdentityConfigurationError("OIDC JWKS URL is invalid.") from error
    if (
        parsed_jwks_url.scheme.lower() != "https"
        or not parsed_jwks_url.hostname
        or parsed_jwks_url.username is not None
        or parsed_jwks_url.password is not None
        or parsed_jwks_url.fragment
        or any(character.isspace() for character in jwks_url)
    ):
        raise IdentityConfigurationError(
            "OIDC JWKS URL must be a valid HTTPS URL without credentials or fragments."
        )

    try:
        key_client = PyJWKClient(jwks_url, timeout=5, cache_jwk_set=True)
        signing_key = key_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience if audience_claim == "aud" else None,
            issuer=issuer,
            options={
                "require": ["exp", "iat", "iss", "aud", "sub"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": True,
                "verify_aud": audience_claim == "aud",
            },
            leeway=0,
        )
    except (PyJWTError, OSError, ValueError) as error:
        raise InvalidIdentityError("Bearer token validation failed.") from error

    subject = claims.get("sub")
    claim_issuer = claims.get("iss")
    claim_audience = claims.get(audience_claim)
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 255:
        raise InvalidIdentityError("Bearer token subject is missing or invalid.")
    if (
        not isinstance(claim_issuer, str)
        or not claim_issuer.strip()
        or len(claim_issuer) > 512
    ):
        raise InvalidIdentityError("Bearer token issuer is missing or invalid.")
    if isinstance(claim_audience, list):
        if audience not in claim_audience:
            raise InvalidIdentityError("Bearer token audience is invalid.")
    elif claim_audience != audience:
        raise InvalidIdentityError("Bearer token audience is invalid.")
    if expected_token_use is not None and claims.get("token_use") != expected_token_use:
        raise InvalidIdentityError("Bearer token type is invalid.")

    return AuthenticatedPrincipal(
        subject=subject,
        issuer=claim_issuer,
        audience=audience,
    )
