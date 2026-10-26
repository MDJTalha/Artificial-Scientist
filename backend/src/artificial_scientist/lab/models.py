"""Strict request and response contracts for controlled computational runs."""

from __future__ import annotations

import json
import re
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_STEP_ID = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


class LabModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LabStep(LabModel):
    """A declarative call to one existing allowlisted scientific operation."""

    step_id: str = Field(min_length=1, max_length=32)
    operation: Literal["symbolic", "integrate", "root", "statistics", "unit_convert"]
    inputs: dict[str, Any] = Field(min_length=1, max_length=20)

    @field_validator("step_id")
    @classmethod
    def validate_step_id(cls, value: str) -> str:
        if not _STEP_ID.fullmatch(value):
            raise ValueError("step_id must be a lowercase identifier")
        return value

    @field_validator("inputs")
    @classmethod
    def validate_inputs(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            encoded = json.dumps(value, allow_nan=False, separators=(",", ":"))
        except (TypeError, ValueError) as error:
            raise ValueError("step inputs must be JSON-compatible finite values") from error
        if len(encoded.encode("utf-8")) > 16_384:
            raise ValueError("step inputs must not exceed 16 KiB")
        return value


class LabRunRequest(LabModel):
    title: str = Field(min_length=3, max_length=200)
    steps: list[LabStep] = Field(min_length=1, max_length=20)
    plan_record_id: UUID | None = None
    random_seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    step_timeout_seconds: float = Field(default=10.0, gt=0, le=30)

    @model_validator(mode="after")
    def validate_unique_steps_and_size(self) -> LabRunRequest:
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("step_id values must be unique")
        encoded = json.dumps(self.model_dump(mode="json"), allow_nan=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 65_536:
            raise ValueError("run configuration must not exceed 64 KiB")
        return self


class LabStepResult(BaseModel):
    step_id: str
    operation: str
    status: Literal["completed", "failed", "skipped"]
    output: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: float = Field(ge=0)


class LabRunResponse(BaseModel):
    run_id: UUID
    title: str
    status: Literal["completed", "failed"]
    configuration_sha256: str
    result_sha256: str
    started_at: str
    completed_at: str
    duration_ms: float = Field(ge=0)
    steps: list[LabStepResult]
    logs: list[str]
    plan_record_id: UUID | None = None
    random_seed: int | None = None
    execution_policy: str = (
        "Declarative allowlisted operations only; arbitrary generated code is never executed."
    )
    limitations: list[str] = [
        "Canonical JSON run-result artifacts are stored; "
        "general binary scientific artifacts and retention policies are not implemented.",
        "Wall-clock duration is measured, not enforced as a hard process timeout.",
        "This service is not an operating-system sandbox and must remain on "
        "trusted local infrastructure.",
    ]



class LabArtifactMetadata(LabModel):
    """Metadata and provenance for an immutable persisted run artifact."""

    artifact_id: UUID
    run_id: UUID
    artifact_type: Literal["run-result-json"]
    content_type: Literal["application/json"]
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0, le=1_048_576)
    created_at: str
    provenance: dict[str, Any]


class LabArtifactResponse(LabArtifactMetadata):
    """Artifact metadata plus its validated JSON document."""

    content: dict[str, Any]
