"""API endpoints for traceable research records."""

from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from artificial_scientist.authorization import (
    AuthorizationDenied,
    TenantDirectory,
    stable_principal_id,
)
from artificial_scientist.config import get_settings
from artificial_scientist.identity import (
    IdentityConfigurationError,
    InvalidIdentityError,
    validate_oidc_bearer_token,
)
from artificial_scientist.records.models import (
    AuditEventListResponse,
    RecordEnvelope,
    RecordInput,
    RecordListResponse,
    RecordType,
)
from artificial_scientist.records.store import (
    DuplicateSource,
    InvalidRelationship,
    RecordConflict,
    RecordIntegrityError,
    RecordNotFound,
    RecordStore,
    RecordStoreError,
)

router = APIRouter(prefix="/api/v1/records", tags=["research records"])


def require_record_access(
    request: Request,
    action: str,
    authorization: str | None,
    x_tenant_id: str | None,
) -> str | None:
    if get_settings().environment.lower() == "development":
        return None
    settings = get_settings()
    issuer = getattr(settings, "oidc_issuer", None)
    audience = getattr(settings, "oidc_audience", None)
    jwks_url = getattr(settings, "oidc_jwks_url", None)
    if not (issuer and audience and jwks_url):
        raise HTTPException(status_code=503, detail="OIDC authentication is not fully configured.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Valid bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not x_tenant_id:
        raise HTTPException(status_code=403, detail="Tenant membership is required.")
    try:
        principal = validate_oidc_bearer_token(
            authorization.removeprefix("Bearer ").strip(),
            issuer=issuer, audience=audience, jwks_url=jwks_url,
            audience_claim=getattr(settings, "oidc_audience_claim", "aud"),
            expected_token_use=getattr(settings, "oidc_token_use", None),
            expected_scope=getattr(settings, "oidc_required_scope", None),
        )
        principal_id = stable_principal_id(principal.issuer, principal.subject)
        TenantDirectory(settings.database_path).authorize(principal_id, x_tenant_id, action)
    except IdentityConfigurationError as error:
        raise HTTPException(
            status_code=503, detail="OIDC authentication configuration is invalid."
        ) from error
    except InvalidIdentityError as error:
        raise HTTPException(
            status_code=401,
            detail="Bearer token validation failed.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except (AuthorizationDenied, ValueError) as error:
        raise HTTPException(
            status_code=404, detail="Requested tenant resource is not available."
        ) from error
    request.state.authenticated_principal = principal
    return x_tenant_id


def record_access(action: str):
    def dependency(
        request: Request,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> str | None:
        return require_record_access(request, action, authorization, x_tenant_id)
    return dependency




@lru_cache(maxsize=1)
def get_record_store() -> RecordStore:
    """Create a short-lived store facade; every operation opens its own connection."""
    return RecordStore(get_settings().database_path)


def _translate_store_error(error: RecordStoreError) -> HTTPException:
    if isinstance(error, (RecordConflict, DuplicateSource)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, InvalidRelationship):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, RecordNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, RecordIntegrityError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored record failed integrity verification.",
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="The research record operation failed.",
    )


@router.post(
    "",
    response_model=RecordEnvelope,
    status_code=status.HTTP_201_CREATED,
    summary="Create a typed research record",
)
def create_record(
    record: RecordInput,
    store: Annotated[RecordStore, Depends(get_record_store)],
    tenant_id: Annotated[str | None, Depends(record_access("record:create"))],
) -> RecordEnvelope:
    """Persist a validated record and its server-generated creation audit event."""
    try:
        return store.create(record, tenant_id=tenant_id)
    except RecordStoreError as error:
        raise _translate_store_error(error) from error


@router.get(
    "",
    response_model=RecordListResponse,
    summary="List research records",
)
def list_records(
    store: Annotated[RecordStore, Depends(get_record_store)],
    record_type: RecordType | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    tenant_id: Annotated[str | None, Depends(record_access("record:list"))] = None,
) -> RecordListResponse:
    """List recent records with safe pagination and optional type filtering."""
    try:
        items, total = store.list_records(
            record_type=record_type,
            limit=limit,
            offset=offset, tenant_id=tenant_id,
        )
    except RecordStoreError as error:
        raise _translate_store_error(error) from error
    return RecordListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/audit-events",
    response_model=AuditEventListResponse,
    summary="List server-generated record creation events",
)
def list_audit_events(
    store: Annotated[RecordStore, Depends(get_record_store)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    tenant_id: Annotated[str | None, Depends(record_access("record:audit:read"))] = None,
) -> AuditEventListResponse:
    """Read audit events; clients cannot create or edit them through the API."""
    try:
        items, total = store.list_audit_events(limit=limit, offset=offset, tenant_id=tenant_id)
    except RecordStoreError as error:
        raise _translate_store_error(error) from error
    return AuditEventListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{record_id}",
    response_model=RecordEnvelope,
    summary="Fetch a record and verify its checksum",
)
def get_record(
    record_id: UUID,
    store: Annotated[RecordStore, Depends(get_record_store)],
    tenant_id: Annotated[str | None, Depends(record_access("record:read"))],
) -> RecordEnvelope:
    """Fetch an immutable record, check its payload hash, and validate its schema."""
    try:
        return store.get(record_id, tenant_id=tenant_id)
    except RecordStoreError as error:
        raise _translate_store_error(error) from error
