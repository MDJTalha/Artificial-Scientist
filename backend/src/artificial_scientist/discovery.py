"""Deterministic hypothesis quality checks; this module does not claim scientific truth."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HypothesisCandidate(BaseModel):
    """A candidate hypothesis submitted by a researcher or an upstream model."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=3, max_length=300)
    statement: str = Field(min_length=10, max_length=6000)
    assumptions: list[str] = Field(min_length=1, max_length=30)
    alternative_explanations: list[str] = Field(min_length=1, max_length=30)
    predictions: list[str] = Field(min_length=1, max_length=30)
    falsification_criteria: list[str] = Field(min_length=1, max_length=30)
    discriminating_test: str = Field(min_length=10, max_length=4000)
    source_record_ids: list[UUID] = Field(default_factory=list, max_length=100)
    claim_record_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator(
        "assumptions",
        "alternative_explanations",
        "predictions",
        "falsification_criteria",
    )
    @classmethod
    def require_nonblank_items(cls, values: list[str]) -> list[str]:
        cleaned = [" ".join(value.split()) for value in values]
        if any(not value for value in cleaned):
            raise ValueError("list items must not be blank")
        if len({value.casefold() for value in cleaned}) != len(cleaned):
            raise ValueError("list items must be unique")
        return cleaned


class DiscoveryAssessmentRequest(BaseModel):
    """A bounded request to assess a set of competing hypotheses."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    research_question: str = Field(min_length=10, max_length=5000)
    candidates: list[HypothesisCandidate] = Field(min_length=2, max_length=10)
    novelty_screen_status: Literal["not_run", "screened"] = "not_run"
    novelty_screen_notes: str | None = Field(default=None, max_length=4000)

    @field_validator("novelty_screen_notes")
    @classmethod
    def normalize_novelty_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class CandidateAssessment(BaseModel):
    """Transparent rubric result, not a probability of correctness."""

    title: str
    completeness_score: int = Field(ge=0, le=100)
    rubric: dict[str, bool]
    concerns: list[str]
    near_duplicate_of: str | None = None
    novelty_status: Literal["not_assessed", "provisional_screen_only"] = "not_assessed"
    persisted_record_id: UUID | None = None


class DiscoveryAssessmentResponse(BaseModel):
    research_question: str
    assessments: list[CandidateAssessment]
    overall_status: Literal["draft", "needs_revision", "ready_for_expert_review"]
    limitations: list[str]


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", value.casefold()))


def _similarity(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
    sequence = SequenceMatcher(None, left.casefold(), right.casefold()).ratio()
    return max(jaccard, sequence)


def assess_candidates(request: DiscoveryAssessmentRequest) -> DiscoveryAssessmentResponse:
    """Score structure and testability without inferring truth or guaranteed novelty."""
    assessments: list[CandidateAssessment] = []
    for index, candidate in enumerate(request.candidates):
        rubric = {
            "explicit_assumptions": bool(candidate.assumptions),
            "alternative_explanations": bool(candidate.alternative_explanations),
            "testable_predictions": bool(candidate.predictions),
            "falsification_criteria": bool(candidate.falsification_criteria),
            "discriminating_test": len(candidate.discriminating_test.strip()) >= 10,
            "traceable_sources": bool(candidate.source_record_ids or candidate.claim_record_ids),
        }
        score = round(sum(rubric.values()) * 100 / len(rubric))
        concerns: list[str] = []
        if not rubric["traceable_sources"]:
            concerns.append("No source or claim records are linked; evidence traceability is missing.")
        if not rubric["alternative_explanations"]:
            concerns.append("At least one serious alternative explanation is required.")
        if not rubric["falsification_criteria"]:
            concerns.append("Specify an observable result that would count against this hypothesis.")
        if not rubric["discriminating_test"]:
            concerns.append("Describe a test that distinguishes this candidate from alternatives.")
        duplicate_of = None
        for previous in request.candidates[:index]:
            if _similarity(candidate.statement, previous.statement) >= 0.82:
                duplicate_of = previous.title
                concerns.append(f"Potential near-duplicate of '{previous.title}'; compare explicitly.")
                break
        if request.novelty_screen_status == "not_run":
            novelty_status = "not_assessed"
        else:
            novelty_status = "provisional_screen_only"
            concerns.append(
                "Novelty screening is provisional and depends on the scope and quality of the recorded search."
            )
        assessments.append(
            CandidateAssessment(
                title=candidate.title,
                completeness_score=score,
                rubric=rubric,
                concerns=concerns,
                near_duplicate_of=duplicate_of,
                novelty_status=novelty_status,
            )
        )

    if any(item.completeness_score < 100 or item.near_duplicate_of for item in assessments):
        overall_status = "needs_revision"
    elif request.novelty_screen_status == "screened":
        overall_status = "ready_for_expert_review"
    else:
        overall_status = "draft"

    return DiscoveryAssessmentResponse(
        research_question=request.research_question,
        assessments=assessments,
        overall_status=overall_status,
        limitations=[
            "Completeness scores measure the presence of required fields, not truth, probability, importance, or scientific merit.",
            "Text similarity is a simple heuristic and can miss paraphrases or flag unrelated statements.",
            "Novelty cannot be guaranteed by a search; expert review and reproducible literature-search records are required.",
            "Candidates are supplied by the caller; this endpoint does not independently generate hypotheses or verify evidence.",
        ],
    )
