"""API endpoints for traceable research records."""

from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from artificial_scientist.config import get_settings
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
) -> RecordEnvelope:
    """Persist a validated record and its server-generated creation audit event."""
    try:
        return store.create(record)
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
) -> RecordListResponse:
    """List recent records with safe pagination and optional type filtering."""
    try:
        items, total = store.list_records(
            record_type=record_type,
            limit=limit,
            offset=offset,
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
) -> AuditEventListResponse:
    """Read audit events; clients cannot create or edit them through the API."""
    try:
        items, total = store.list_audit_events(limit=limit, offset=offset)
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
) -> RecordEnvelope:
    """Fetch an immutable record, check its payload hash, and validate its schema."""
    try:
        return store.get(record_id)
    except RecordStoreError as error:
        raise _translate_store_error(error) from error
