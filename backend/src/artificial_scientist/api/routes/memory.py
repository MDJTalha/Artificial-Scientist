"""Tenant-protected API for versioned, evidence-linked scientific memory."""

from __future__ import annotations

import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from artificial_scientist.api.routes.records import get_record_store, record_access
from artificial_scientist.autonomy.memory import (
    MemoryError,
    MemoryVersion,
    ResearchMemory,
)
from artificial_scientist.autonomy.store import AutonomyStore
from artificial_scientist.config import get_settings
from artificial_scientist.records.store import (
    RecordNotFound,
    RecordStore,
    RecordStoreError,
)

router = APIRouter(prefix="/api/v1/memory", tags=["scientific memory"])


class MemoryRequest(BaseModel):
    """A new immutable memory version backed by existing research records."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    value: dict[str, object] = Field(min_length=1)
    evidence_record_ids: list[UUID] = Field(min_length=1, max_length=50)
    status: Literal["active", "proposed"] = "active"

    @field_validator("evidence_record_ids")
    @classmethod
    def unique_evidence(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("evidence_record_ids must be unique")
        return value

    @field_validator("value")
    @classmethod
    def bounded_json_value(cls, value: dict[str, object]) -> dict[str, object]:
        try:
            encoded = json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError) as error:
            raise ValueError(
                "memory value must be finite JSON-compatible data"
            ) from error
        if len(encoded.encode("utf-8")) > 65_536:
            raise ValueError("memory value must not exceed 64 KiB")
        return value


class MemoryContradictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=5, max_length=2000)
    evidence_record_ids: list[UUID] = Field(min_length=1, max_length=50)

    @field_validator("evidence_record_ids")
    @classmethod
    def unique_evidence(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("evidence_record_ids must be unique")
        return value


class MemoryRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)


class MemoryVersionResponse(BaseModel):
    key: str
    version: int
    value: dict[str, object]
    status: str
    evidence: list[str]
    created_at: str
    digest: str
    supersedes: int | None


class MemorySummary(BaseModel):
    key: str
    version: int
    status: str
    created_at: str
    digest: str
    evidence_count: int


class MemoryListResponse(BaseModel):
    items: list[MemorySummary]
    total: int
    limit: int
    offset: int


class MemoryHistoryResponse(BaseModel):
    key: str
    items: list[MemoryVersionResponse]
    total: int


def _memory(tenant_id: str | None) -> ResearchMemory:
    """Use an explicit isolated development namespace or verified tenant identifier."""
    settings = get_settings()
    return ResearchMemory(
        AutonomyStore(settings.database_path),
        tenant_id=tenant_id or "development",
    )


def _serialize(item: MemoryVersion) -> MemoryVersionResponse:
    return MemoryVersionResponse(
        key=item.key,
        version=item.version,
        value=item.value,
        status=item.status,
        evidence=list(item.evidence),
        created_at=item.created_at.isoformat(),
        digest=item.digest,
        supersedes=item.supersedes,
    )


def _validate_evidence(
    evidence_ids: list[UUID],
    store: RecordStore,
    *,
    tenant_id: str | None,
) -> tuple[str, ...]:
    """Require every evidence reference to resolve inside the caller's tenant."""
    validated: list[str] = []
    for record_id in evidence_ids:
        try:
            store.get(record_id, tenant_id=tenant_id)
        except RecordNotFound as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Evidence record {record_id} is not available in this tenant.",
            ) from error
        except RecordStoreError as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Evidence record integrity verification failed.",
            ) from error
        validated.append(str(record_id))
    return tuple(validated)


def _key(key: str = Path(min_length=1, max_length=200)) -> str:
    if not key.strip() or "/" in key or "\\" in key:
        raise HTTPException(
            status_code=422,
            detail="Memory key must be a bounded identifier.",
        )
    return key


@router.get("", response_model=MemoryListResponse)
def list_memory(
    tenant_id: Annotated[str | None, Depends(record_access("memory:list"))],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> MemoryListResponse:
    memory = _memory(tenant_id)
    keys = memory.store.memory_keys(tenant_id=memory.tenant_id)
    summaries: list[MemorySummary] = []
    for key in keys:
        history = memory.history(key)
        if not history:
            continue
        latest = history[-1]
        summaries.append(
            MemorySummary(
                key=latest.key,
                version=latest.version,
                status=latest.status,
                created_at=latest.created_at.isoformat(),
                digest=latest.digest,
                evidence_count=len(latest.evidence),
            )
        )
    # Keys are ordered by the persistence layer; newest version timestamps are not
    # used to reorder tenant keys because one key may be revised independently.
    page = summaries[offset : offset + limit]
    return MemoryListResponse(
        items=page,
        total=len(summaries),
        limit=limit,
        offset=offset,
    )


@router.get("/{key}", response_model=MemoryHistoryResponse)
def get_memory_history(
    key: Annotated[str, Depends(_key)],
    tenant_id: Annotated[str | None, Depends(record_access("memory:read"))],
) -> MemoryHistoryResponse:
    memory = _memory(tenant_id)
    items = memory.history(key)
    if not items:
        raise HTTPException(status_code=404, detail="Memory key is not available.")
    return MemoryHistoryResponse(
        key=key,
        items=[_serialize(item) for item in items],
        total=len(items),
    )


@router.post(
    "/{key}",
    response_model=MemoryVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_memory_version(
    request: MemoryRequest,
    key: Annotated[str, Depends(_key)],
    tenant_id: Annotated[str | None, Depends(record_access("memory:write"))],
    records: Annotated[RecordStore, Depends(get_record_store)],
) -> MemoryVersionResponse:
    evidence = _validate_evidence(
        request.evidence_record_ids, records, tenant_id=tenant_id
    )
    try:
        item = _memory(tenant_id).put(
            key,
            request.value,
            evidence=evidence,
            status=request.status,
        )
    except MemoryError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail="Memory version changed concurrently.",
        ) from error
    return _serialize(item)


@router.post(
    "/{key}/contradict",
    response_model=MemoryVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def contradict_memory(
    request: MemoryContradictionRequest,
    key: Annotated[str, Depends(_key)],
    tenant_id: Annotated[str | None, Depends(record_access("memory:contradict"))],
    records: Annotated[RecordStore, Depends(get_record_store)],
) -> MemoryVersionResponse:
    evidence = _validate_evidence(
        request.evidence_record_ids, records, tenant_id=tenant_id
    )
    try:
        item = _memory(tenant_id).contradict(
            key,
            evidence=evidence,
            reason=request.reason,
        )
    except MemoryError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _serialize(item)


@router.post(
    "/{key}/rollback",
    response_model=MemoryVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def rollback_memory(
    request: MemoryRollbackRequest,
    key: Annotated[str, Depends(_key)],
    tenant_id: Annotated[str | None, Depends(record_access("memory:rollback"))],
) -> MemoryVersionResponse:
    try:
        item = _memory(tenant_id).rollback(key, request.version)
    except MemoryError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _serialize(item)
