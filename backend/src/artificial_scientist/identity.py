"""OIDC bearer-token validation for protected API boundaries.

This module validates tokens against an operator-configured issuer, audience, and JWKS
endpoint. It deliberately does not implement login, issue tokens, or infer tenant membership.
"""

from __future__ import annotations

from dataclasses import dataclass

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
) -> AuthenticatedPrincipal:
    """Validate a signed OIDC access token using only RS256 and configured trust values."""
    if not issuer or not audience or not jwks_url:
        raise IdentityConfigurationError(
            "OIDC issuer, audience, and JWKS URL must all be configured."
        )
    if not jwks_url.startswith("https://"):
        raise IdentityConfigurationError("OIDC JWKS URL must use HTTPS.")

    try:
        key_client = PyJWKClient(jwks_url, timeout=5, cache_jwk_set=True)
        signing_key = key_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={
                "require": ["exp", "iat", "iss", "aud", "sub"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": True,
                "verify_aud": True,
            },
            leeway=0,
        )
    except (PyJWTError, OSError, ValueError) as error:
        raise InvalidIdentityError("Bearer token validation failed.") from error

    subject = claims.get("sub")
    claim_issuer = claims.get("iss")
    claim_audience = claims.get("aud")
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

    return AuthenticatedPrincipal(
        subject=subject,
        issuer=claim_issuer,
        audience=audience,
    )
