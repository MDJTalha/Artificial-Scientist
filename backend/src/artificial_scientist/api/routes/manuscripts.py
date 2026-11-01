"""Tenant-protected scientific manuscript drafting and persistence."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from artificial_scientist.autonomy.writing import (
    Citation,
    ScientificWriter,
    WritingError,
)
from artificial_scientist.api.routes.records import get_record_store, record_access
from artificial_scientist.records.models import (
    ManuscriptClaim,
    ManuscriptRecord,
    RecordEnvelope,
    SourceRecord,
)
from artificial_scientist.records.store import (
    RecordNotFound,
    RecordStore,
    RecordStoreError,
)

router = APIRouter(prefix="/api/v1/manuscripts", tags=["scientific manuscripts"])


class ManuscriptClaimInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=5, max_length=5000)
    source_record_ids: list[UUID] = Field(min_length=1, max_length=20)


class ManuscriptCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=3, max_length=300)
    abstract: str = Field(default="", max_length=5000)
    claims: list[ManuscriptClaimInput] = Field(min_length=1, max_length=100)
    methods: str = Field(min_length=10, max_length=12000)
    limitations: str = Field(min_length=10, max_length=12000)
    data_statement: str = Field(min_length=5, max_length=5000)


class ManuscriptSummary(BaseModel):
    id: UUID
    title: str
    created_at: str
    content_sha256: str
    claim_count: int
    citation_count: int
    status: str
    submission_approved: bool


class ManuscriptListResponse(BaseModel):
    items: list[ManuscriptSummary]
    total: int
    limit: int
    offset: int


def _load_source(
    record_id: UUID,
    store: RecordStore,
    tenant_id: str | None,
) -> SourceRecord:
    try:
        envelope = store.get(record_id, tenant_id=tenant_id)
    except RecordNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Citation source {record_id} is not available in this tenant.",
        ) from error
    except RecordStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Citation source integrity validation failed.",
        ) from error

    if envelope.record_type != "source":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Record {record_id} is not a bibliographic source.",
        )
    source = SourceRecord.model_validate(envelope.payload)
    if not source.external_identifier:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Citation source {record_id} has no external identifier.",
        )
    if source.assessment_status in {"retracted", "disputed", "unavailable"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Citation source {record_id} is marked {source.assessment_status}.",
        )
    return source


def _render_markdown(
    request: ManuscriptCreateRequest,
    source_by_id: dict[UUID, SourceRecord],
    citation_numbers: dict[UUID, int],
) -> str:
    writer = ScientificWriter()
    citations = [
        Citation(
            citation_id=str(record_id),
            title=source.title,
            identifier=source.external_identifier or "",
            verified=True,
        )
        for record_id, source in source_by_id.items()
    ]
    try:
        writer.build(
            request.title,
            [claim.text for claim in request.claims],
            citations,
            methods=request.methods,
            limitations=request.limitations,
            data_statement=request.data_statement,
            submission_approved=False,
        )
    except WritingError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    lines = [
        f"# {request.title}",
        "",
        "**Draft status:** Not submitted or approved for external publication.",
        "",
    ]
    if request.abstract.strip():
        lines.extend(["## Abstract", "", request.abstract.strip(), ""])
    lines.extend(["## Claims", ""])
    for index, claim in enumerate(request.claims, start=1):
        numbers = [
            citation_numbers[source_id]
            for source_id in claim.source_record_ids
        ]
        refs = ", ".join(f"[{number}]" for number in numbers)
        lines.extend([f"{index}. {claim.text} {refs}", ""])
    lines.extend(
        [
            "## Methods",
            "",
            request.methods,
            "",
            "## Limitations",
            "",
            request.limitations,
            "",
            "## Data availability statement",
            "",
            request.data_statement,
            "",
            "## References",
            "",
        ]
    )
    for record_id, source in source_by_id.items():
        number = citation_numbers[record_id]
        identifier = source.external_identifier or "Identifier unavailable"
        lines.append(
            f"[{number}] {source.title}. {identifier}. {source.source_url}"
        )
    lines.extend(
        [
            "",
            "---",
            "",
            "## Scientific-integrity notice",
            "",
            "This document is a researcher-authored draft assembled from structured inputs. "
            "A citation resolves to a tenant-owned, integrity-checked bibliographic "
            "metadata record with an external identifier. This check does not establish "
            "that the source supports the associated claim, validate the source's "
            "scientific conclusions, prove novelty, or constitute independent peer "
            "review. Inspect each original source.",
            "",
            "External submission and publication are disabled. A separate authorized "
            "human approval process is required before any consequential external action.",
            "",
        ]
    )
    markdown = "\n".join(lines)
    if len(markdown.encode("utf-8")) > 100_000:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Rendered manuscript exceeds 100 KiB.",
        )
    return markdown


@router.get("", response_model=ManuscriptListResponse)
def list_manuscripts(
    tenant_id: Annotated[str | None, Depends(record_access("manuscript:list"))],
    store: Annotated[RecordStore, Depends(get_record_store)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ManuscriptListResponse:
    try:
        records, total = store.list_records(
            record_type="manuscript",
            limit=limit,
            offset=offset,
            tenant_id=tenant_id,
        )
    except RecordStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Manuscript listing failed.",
        ) from error

    summaries = [
        ManuscriptSummary(
            id=record.id,
            title=str(record.payload["title"]),
            created_at=record.created_at.isoformat(),
            content_sha256=record.content_sha256,
            claim_count=len(record.payload["claims"]),
            citation_count=len(
                {
                    source_id
                    for claim in record.payload["claims"]
                    for source_id in claim["source_record_ids"]
                }
            ),
            status=str(record.payload["status"]),
            submission_approved=bool(record.payload["submission_approved"]),
        )
        for record in records
    ]
    return ManuscriptListResponse(
        items=summaries,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{manuscript_id}", response_model=RecordEnvelope)
def get_manuscript(
    manuscript_id: UUID,
    tenant_id: Annotated[str | None, Depends(record_access("manuscript:read"))],
    store: Annotated[RecordStore, Depends(get_record_store)],
) -> RecordEnvelope:
    try:
        record = store.get(manuscript_id, tenant_id=tenant_id)
    except RecordNotFound as error:
        raise HTTPException(
            status_code=404, detail="Manuscript is not available."
        ) from error
    except RecordStoreError as error:
        raise HTTPException(
            status_code=500,
            detail="Manuscript integrity validation failed.",
        ) from error
    if record.record_type != "manuscript":
        raise HTTPException(status_code=404, detail="Manuscript is not available.")
    return record


@router.post(
    "",
    response_model=RecordEnvelope,
    status_code=status.HTTP_201_CREATED,
)
def create_manuscript(
    request: ManuscriptCreateRequest,
    tenant_id: Annotated[str | None, Depends(record_access("manuscript:create"))],
    store: Annotated[RecordStore, Depends(get_record_store)],
) -> RecordEnvelope:
    source_ids = {
        source_id
        for claim in request.claims
        for source_id in claim.source_record_ids
    }
    if len(source_ids) > 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A manuscript may cite at most 50 unique source records.",
        )

    source_by_id = {
        source_id: _load_source(source_id, store, tenant_id)
        for source_id in sorted(source_ids, key=str)
    }
    citation_numbers = {
        source_id: index
        for index, source_id in enumerate(source_by_id, start=1)
    }
    markdown = _render_markdown(request, source_by_id, citation_numbers)

    manuscript = ManuscriptRecord(
        title=request.title,
        abstract=request.abstract,
        claims=[
            ManuscriptClaim(
                text=claim.text,
                source_record_ids=claim.source_record_ids,
            )
            for claim in request.claims
        ],
        methods=request.methods,
        limitations=request.limitations,
        data_statement=request.data_statement,
        rendered_markdown=markdown,
        provenance={
            "method": "derived_from_records",
            "source_record_ids": sorted(source_ids, key=str),
            "notes": (
                "Structured manuscript draft assembled by a researcher. "
                "Citation resolution validates record integrity and identifiers only."
            ),
        },
    )
    try:
        return store.create(manuscript, tenant_id=tenant_id)
    except RecordStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Manuscript could not be persisted.",
        ) from error
