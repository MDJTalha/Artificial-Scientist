"""OIDC session introspection and active tenant discovery."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from artificial_scientist.authorization import TenantDirectory, stable_principal_id
from artificial_scientist.config import get_settings
from artificial_scientist.identity import (
    IdentityConfigurationError,
    InvalidIdentityError,
    validate_oidc_bearer_token,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


class TenantMembershipResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    role: str


class AuthenticatedSessionResponse(BaseModel):
    principal_id: str
    issuer: str
    memberships: list[TenantMembershipResponse]


@router.get("/session", response_model=AuthenticatedSessionResponse)
def get_authenticated_session(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedSessionResponse:
    """Validate the access token and return memberships from the server directory.

    Tenant membership is never accepted from token claims or browser-supplied data.
    The OIDC issuer/subject pair is resolved to a stable local principal, and only
    active memberships provisioned by an operator are returned.
    """
    settings = get_settings()
    if settings.environment.lower() == "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OIDC session discovery is not used in development mode.",
        )
    issuer = settings.oidc_issuer
    audience = settings.oidc_audience
    jwks_url = settings.oidc_jwks_url
    if not (issuer and audience and jwks_url):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC authentication is not fully configured.",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not token or len(token) > 16_384:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        principal = validate_oidc_bearer_token(
            token,
            issuer=issuer,
            audience=audience,
            jwks_url=jwks_url,
        )
    except IdentityConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC authentication configuration is invalid.",
        ) from error
    except InvalidIdentityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token validation failed.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    principal_id = stable_principal_id(principal.issuer, principal.subject)
    directory = TenantDirectory(settings.database_path)
    directory.register_principal(principal.issuer, principal.subject)
    memberships = directory.list_memberships(principal_id)
    directory.audit(
        principal_id=principal_id,
        tenant_id=None,
        action="auth:session:read",
        target_type="principal",
        target_id=principal_id,
        outcome="allowed",
        metadata={"active_tenant_count": len(memberships)},
    )
    return AuthenticatedSessionResponse(
        principal_id=principal_id,
        issuer=principal.issuer,
        memberships=[
            TenantMembershipResponse.model_validate(item) for item in memberships
        ],
    )
