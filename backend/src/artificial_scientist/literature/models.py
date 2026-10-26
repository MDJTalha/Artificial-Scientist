"""Typed contracts for scholarly search requests, results, and provider status."""

from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

LiteratureProviderName = Literal["openalex", "crossref"]
ProviderState = Literal["ok", "rate_limited", "unavailable", "invalid_response"]


class LiteratureSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=3, max_length=500)
    limit: int = Field(default=5, ge=1, le=10)
    providers: list[LiteratureProviderName] = Field(
        default_factory=lambda: ["openalex", "crossref"],
        min_length=1,
        max_length=2,
    )
    persist_results: bool = True

    @field_validator("providers")
    @classmethod
    def providers_must_be_unique(
        cls, providers: list[LiteratureProviderName]
    ) -> list[LiteratureProviderName]:
        if len(providers) != len(set(providers)):
            raise ValueError("providers must not contain duplicates")
        return providers


class ProviderSearchStatus(BaseModel):
    provider: LiteratureProviderName
    status: ProviderState
    result_count: int = Field(ge=0)
    message: str | None = Field(default=None, max_length=240)


class LiteratureResult(BaseModel):
    """Normalized bibliographic metadata; not a verification of a scientific claim."""

    title: str = Field(min_length=2, max_length=500)
    authors: list[str] = Field(default_factory=list, max_length=100)
    doi: str | None = Field(default=None, max_length=300)
    publication_date: date | None = None
    publication_year: int | None = Field(default=None, ge=1000, le=9999)
    source_url: HttpUrl
    source_kind: Literal[
        "journal_article", "preprint", "dataset", "standard", "other"
    ] = "other"
    provider_identifiers: dict[str, str] = Field(default_factory=dict)
    matched_providers: list[LiteratureProviderName] = Field(min_length=1, max_length=2)
    is_retracted: bool | None = None
    has_open_access_location: bool | None = None
    cited_by_count: int | None = Field(default=None, ge=0)
    saved_record_id: UUID | None = None


class LiteratureSearchResponse(BaseModel):
    query: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: Literal["ok", "partial", "unavailable"]
    results: list[LiteratureResult]
    total_results: int = Field(ge=0)
    providers: list[ProviderSearchStatus] = Field(min_length=1, max_length=2)
    note: str = (
        "Bibliographic metadata is not itself scientific verification. "
        "Inspect the original source and assess each claim independently."
    )
