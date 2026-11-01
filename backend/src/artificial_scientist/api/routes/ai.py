"""Tenant-protected optional AI research-assistance API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from artificial_scientist.ai_gateway import (
    ModelGatewayInvalidResponse,
    ModelGatewayUnavailable,
    generate_research_assistance,
    resolve_model_gateway_config,
)
from artificial_scientist.api.routes.records import get_record_store, record_access
from artificial_scientist.config import get_settings
from artificial_scientist.records.models import ModelInvocationRecord
from artificial_scientist.records.store import RecordStore, RecordStoreError

router = APIRouter(prefix="/api/v1/ai", tags=["optional AI assistance"])


class AiCapabilityResponse(BaseModel):
    configured: bool
    provider: str | None = None
    model: str | None = None
    max_output_tokens: int
    requires_human_review: bool = True
    note: str


class AiGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    prompt: str = Field(min_length=1, max_length=12_000)
    max_output_tokens: int = Field(default=800, ge=1, le=2_048)


class AiGenerationResponse(BaseModel):
    invocation_record_id: str
    provider: str
    model: str
    content: str
    prompt_sha256: str
    response_sha256: str
    prompt_bytes: int
    response_bytes: int
    input_tokens: int | None
    output_tokens: int | None
    finish_reason: str | None
    requires_human_review: bool = True
    limitations: list[str]


def _capabilities() -> AiCapabilityResponse:
    settings = get_settings()
    try:
        config = resolve_model_gateway_config(settings)
    except ModelGatewayUnavailable:
        return AiCapabilityResponse(
            configured=False,
            max_output_tokens=0,
            note="Model provider settings are incomplete or invalid; AI inference remains disabled.",
        )
    if config is None:
        return AiCapabilityResponse(
            configured=False,
            max_output_tokens=0,
            note="No model provider is configured. No AI service is contacted.",
        )
    return AiCapabilityResponse(
        configured=True,
        provider=config.provider,
        model=config.model,
        max_output_tokens=config.max_output_tokens,
        note=(
            "A manually invoked model can draft research assistance only. It does not "
            "retrieve evidence, validate claims, establish novelty or authorize experiments."
        ),
    )


@router.get("/capabilities", response_model=AiCapabilityResponse)
def get_ai_capabilities(
    tenant_id: Annotated[str | None, Depends(record_access("ai:inference"))],
) -> AiCapabilityResponse:
    """Report provider readiness without returning provider URLs, keys or secrets."""
    del tenant_id
    return _capabilities()


@router.post(
    "/generate",
    response_model=AiGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_ai_assistance(
    payload: AiGenerationRequest,
    request: Request,
    tenant_id: Annotated[str | None, Depends(record_access("ai:inference"))],
    store: Annotated[RecordStore, Depends(get_record_store)],
) -> AiGenerationResponse:
    """Manually invoke the configured model and persist hash-only provenance."""
    settings = get_settings()
    try:
        generation = generate_research_assistance(
            settings,
            payload.prompt,
            max_output_tokens=payload.max_output_tokens,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except ModelGatewayUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except ModelGatewayInvalidResponse as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Configured model provider returned an invalid response.",
        ) from error

    record = ModelInvocationRecord(
        provider=generation.provider,
        model=generation.model,
        prompt_sha256=generation.prompt_sha256,
        response_sha256=generation.response_sha256,
        prompt_bytes=generation.prompt_bytes,
        response_bytes=generation.response_bytes,
        input_tokens=generation.input_tokens,
        output_tokens=generation.output_tokens,
        finish_reason=generation.finish_reason,
        provenance={
            "method": "model_inference",
            "notes": (
                "Optional manually invoked model assistance. The raw prompt and model "
                "output are not stored in this provenance record. Output is unverified."
            ),
        },
    )
    try:
        saved = store.create(record, tenant_id=tenant_id or "development")
    except RecordStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model output could not be linked to a persisted invocation record.",
        ) from error

    request.state.model_invocation_record_id = str(saved.id)
    return AiGenerationResponse(
        invocation_record_id=str(saved.id),
        provider=generation.provider,
        model=generation.model,
        content=generation.content,
        prompt_sha256=generation.prompt_sha256,
        response_sha256=generation.response_sha256,
        prompt_bytes=generation.prompt_bytes,
        response_bytes=generation.response_bytes,
        input_tokens=generation.input_tokens,
        output_tokens=generation.output_tokens,
        finish_reason=generation.finish_reason,
        limitations=[
            "This text is model-generated research assistance, not a verified scientific result.",
            "The model was not given access to literature retrieval, laboratory instruments or external tools by this endpoint.",
            "No generated citations, observations, measurements or claims should be treated as evidence without independent verification.",
            "Review the full prompt and output before storing any content in a research record or manuscript.",
        ],
    )
