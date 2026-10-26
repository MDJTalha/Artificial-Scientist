"""Validated schemas for source-traceable scientific research records.

These schemas validate the shape of submitted records. They do not independently
verify source truth, the identity of a reviewer, or whether an experiment occurred.
"""

from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class Provenance(BaseModel):
    """Declared origin metadata attached to a research record."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    method: Literal[
        "human_provided",
        "literature_retrieval",
        "computation",
        "simulation",
        "human_observation",
        "model_suggestion",
        "derived_from_records",
    ] = "human_provided"
    source_record_ids: list[UUID] = Field(default_factory=list, max_length=200)
    captured_at: datetime = Field(default_factory=utc_now)
    model_name: str | None = Field(default=None, max_length=200)
    tool_name: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)


RecordType = Literal[
    "research_task",
    "source",
    "claim",
    "hypothesis",
    "experiment_plan",
    "experiment_run",
    "artifact",
    "review",
    "approval_request",
]


class RecordBase(BaseModel):
    """Common structure for append-only scientific records."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: UUID = Field(default_factory=uuid4)
    schema_version: Literal[1] = 1
    provenance: Provenance = Field(default_factory=Provenance)


class ResearchTaskRecord(RecordBase):
    record_type: Literal["research_task"] = "research_task"
    title: str = Field(min_length=3, max_length=200)
    research_question: str = Field(min_length=10, max_length=5000)
    objective: str = Field(min_length=3, max_length=4000)
    status: Literal[
        "created",
        "scoping",
        "literature_review",
        "hypothesis_draft",
        "experiment_planned",
        "awaiting_approval",
        "running",
        "verification",
        "review",
        "completed",
        "failed",
        "cancelled",
        "blocked",
    ] = "created"
    priority: Literal["low", "normal", "high", "critical"] = "normal"
    related_record_ids: list[UUID] = Field(default_factory=list, max_length=200)


class SourceRecord(RecordBase):
    record_type: Literal["source"] = "source"
    title: str = Field(min_length=2, max_length=500)
    source_url: HttpUrl
    source_kind: Literal[
        "journal_article",
        "preprint",
        "book",
        "dataset",
        "technical_documentation",
        "standard",
        "institutional_document",
        "other",
    ] = "other"
    authors: list[str] = Field(default_factory=list, max_length=100)
    published_date: date | None = None
    retrieved_at: datetime = Field(default_factory=utc_now)
    external_identifier: str | None = Field(default=None, max_length=300)
    content_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    license_note: str | None = Field(default=None, max_length=2000)
    assessment_status: Literal[
        "unassessed", "relevant", "disputed", "retracted", "unavailable"
    ] = "unassessed"


class ClaimRecord(RecordBase):
    record_type: Literal["claim"] = "claim"
    claim_text: str = Field(min_length=5, max_length=5000)
    evidence_status: Literal[
        "source_reported",
        "corroborated",
        "computed",
        "observed",
        "inferred",
        "hypothesis",
        "disputed",
        "contradicted",
        "unverified",
    ] = "unverified"
    source_record_ids: list[UUID] = Field(default_factory=list, max_length=200)
    related_claim_ids: list[UUID] = Field(default_factory=list, max_length=200)
    supporting_artifact_ids: list[UUID] = Field(default_factory=list, max_length=200)
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    assessment_notes: str | None = Field(default=None, max_length=4000)


class HypothesisRecord(RecordBase):
    record_type: Literal["hypothesis"] = "hypothesis"
    title: str = Field(min_length=3, max_length=300)
    hypothesis: str = Field(min_length=10, max_length=6000)
    assumptions: list[str] = Field(default_factory=list, max_length=100)
    alternative_explanations: list[str] = Field(default_factory=list, max_length=100)
    falsification_criteria: list[str] = Field(min_length=1, max_length=100)
    source_record_ids: list[UUID] = Field(default_factory=list, max_length=200)
    claim_record_ids: list[UUID] = Field(default_factory=list, max_length=200)
    supersedes_id: UUID | None = None
    status: Literal[
        "proposed", "under_review", "supported", "rejected", "inconclusive"
    ] = "proposed"
    novelty_assessment: Literal[
        "not_assessed", "literature_screened", "expert_reviewed"
    ] = "not_assessed"
    novelty_notes: str | None = Field(default=None, max_length=4000)


class ExperimentPlanRecord(RecordBase):
    record_type: Literal["experiment_plan"] = "experiment_plan"
    title: str = Field(min_length=3, max_length=300)
    research_question: str = Field(min_length=10, max_length=5000)
    hypothesis_record_id: UUID
    method: str = Field(min_length=10, max_length=8000)
    independent_variables: list[str] = Field(default_factory=list, max_length=100)
    dependent_variables: list[str] = Field(default_factory=list, max_length=100)
    controls: list[str] = Field(default_factory=list, max_length=100)
    success_criteria: list[str] = Field(min_length=1, max_length=100)
    failure_criteria: list[str] = Field(min_length=1, max_length=100)
    source_record_ids: list[UUID] = Field(default_factory=list, max_length=200)
    risk_level: Literal["low", "moderate", "high", "restricted"] = "low"
    status: Literal["draft", "proposed", "approval_requested"] = "draft"


class ExperimentRunRecord(RecordBase):
    record_type: Literal["experiment_run"] = "experiment_run"
    plan_record_id: UUID
    execution_status: Literal[
        "not_run", "reported_completed", "reported_failed", "cancelled"
    ] = "not_run"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    summary: str | None = Field(default=None, max_length=8000)
    output_artifact_ids: list[UUID] = Field(default_factory=list, max_length=200)
    random_seed: int | None = Field(default=None, ge=0)
    environment_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")


class ArtifactRecord(RecordBase):
    record_type: Literal["artifact"] = "artifact"
    title: str = Field(min_length=2, max_length=300)
    artifact_kind: Literal[
        "report", "dataset", "source_code", "notebook", "figure", "table",
        "environment_manifest", "experiment_output", "other",
    ] = "other"
    uri: str = Field(min_length=1, max_length=2048)
    sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    media_type: str | None = Field(default=None, max_length=200)
    size_bytes: int | None = Field(default=None, ge=0)
    related_record_ids: list[UUID] = Field(default_factory=list, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


class ReviewRecord(RecordBase):
    record_type: Literal["review"] = "review"
    target_record_id: UUID
    reviewer_kind: Literal["human", "ai_agent", "automated_check"]
    reviewer_label: str = Field(min_length=2, max_length=200)
    outcome: Literal["pending", "accepted", "changes_requested", "rejected", "inconclusive"]
    findings: list[str] = Field(default_factory=list, max_length=200)
    method: str = Field(min_length=3, max_length=4000)
    limitations: list[str] = Field(default_factory=list, max_length=100)


class ApprovalRequestRecord(RecordBase):
    """An approval request only; public record creation cannot approve an action."""

    record_type: Literal["approval_request"] = "approval_request"
    target_record_id: UUID
    requested_action: Literal[
        "external_publication",
        "external_submission",
        "external_data_access",
        "physical_experiment",
        "hardware_control",
        "other_consequential_action",
    ]
    requested_by: str = Field(min_length=2, max_length=200)
    rationale: str = Field(min_length=5, max_length=4000)
    status: Literal["requested"] = "requested"


RecordInput = Annotated[
    ResearchTaskRecord
    | SourceRecord
    | ClaimRecord
    | HypothesisRecord
    | ExperimentPlanRecord
    | ExperimentRunRecord
    | ArtifactRecord
    | ReviewRecord
    | ApprovalRequestRecord,
    Field(discriminator="record_type"),
]


class RecordEnvelope(BaseModel):
    """Server metadata and the validated payload of one stored record."""

    id: UUID
    record_type: RecordType
    schema_version: int
    created_at: datetime
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    payload: dict[str, object]


class RecordListResponse(BaseModel):
    items: list[RecordEnvelope]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class AuditEventEnvelope(BaseModel):
    """Server-generated audit metadata; this is not user-authored research content."""

    event_id: UUID
    occurred_at: datetime
    action: Literal["record.created"]
    actor: Literal["local-api-client"]
    record_id: UUID
    record_type: RecordType
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class AuditEventListResponse(BaseModel):
    items: list[AuditEventEnvelope]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
