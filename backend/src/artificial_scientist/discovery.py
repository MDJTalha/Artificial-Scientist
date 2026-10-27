"""Deterministic hypothesis quality checks; this module does not claim scientific truth."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
        if any(len(value) > 2000 for value in cleaned):
            raise ValueError("list items must be at most 2000 characters")
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

    @model_validator(mode="after")
    def require_notes_for_completed_screen(self) -> DiscoveryAssessmentRequest:
        if self.novelty_screen_status == "screened" and not self.novelty_screen_notes:
            raise ValueError(
                "novelty_screen_notes are required when novelty_screen_status is screened"
            )
        return self


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


class ResearchQuestionDecompositionRequest(BaseModel):
    """A bounded request to structure a question before hypothesis review."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    research_question: str = Field(min_length=10, max_length=5000)
    domain_context: str | None = Field(default=None, max_length=1000)


class ResearchQuestionDecompositionResponse(BaseModel):
    research_question: str
    question_type: Literal[
        "causal", "comparative", "descriptive", "predictive", "exploratory", "unclassified"
    ]
    independent_variable: str | None
    dependent_variable: str | None
    system_or_population: str | None
    context: str | None
    missing_elements: list[str]
    clarification_prompts: list[str]
    method: Literal["bounded_heuristic"]
    limitations: list[str]


def decompose_research_question(
    request: ResearchQuestionDecompositionRequest,
) -> ResearchQuestionDecompositionResponse:
    """Extract only conservative patterns and report every unknown explicitly."""
    question = " ".join(request.research_question.split())
    independent: str | None = None
    dependent: str | None = None
    question_type: Literal[
        "causal", "comparative", "descriptive", "predictive", "exploratory", "unclassified"
    ] = "unclassified"

    patterns = (
        (r"how does (.+?) affect (.+?)(?: under | in | among | for | when |\?|$)", "causal"),
        (r"effect of (.+?) on (.+?)(?: under | in | among | for | when |\?|$)", "causal"),
        (
            r"relationship between (.+?) and (.+?)(?: under | in | among | for | when |\?|$)",
            "exploratory",
        ),
        (r"compare (.+?) and (.+?)(?: under | in | among | for | when |\?|$)", "comparative"),
    )
    normalized = question.casefold()
    for pattern, detected_type in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            independent = match.group(1).strip(" .?!")
            dependent = match.group(2).strip(" .?!")
            question_type = detected_type
            break

    if question_type == "unclassified":
        if normalized.startswith(("what is ", "what are ", "which factors ")):
            question_type = "descriptive"
        elif normalized.startswith(("will ", "can ", "to what extent ")):
            question_type = "predictive"
        else:
            question_type = "exploratory"

    system_match = re.search(
        r"\b(?:in|among|for|within)\s+([^,;?]+)",
        question,
        flags=re.IGNORECASE,
    )
    system_or_population = system_match.group(1).strip() if system_match else None
    context = request.domain_context.strip() if request.domain_context else None

    missing: list[str] = []
    prompts: list[str] = []
    if not independent:
        missing.append("independent_variable")
        prompts.append("What factor, intervention, or condition is being varied or compared?")
    if not dependent:
        missing.append("dependent_variable")
        prompts.append("What measurable outcome or response should be explained?")
    if not system_or_population:
        missing.append("system_or_population")
        prompts.append("Which population, system, dataset, or environment is in scope?")
    if not context:
        missing.append("domain_context")
        prompts.append(
            "What domain, setting, and boundary conditions should constrain the question?"
        )
    if not re.search(r"\b(control|adjust|hold constant|confound|baseline)\b", normalized):
        missing.append("confounders_and_controls")
        prompts.append("Which confounders, controls, and baseline comparisons must be considered?")
    if not re.search(r"\b(day|week|month|year|hour|minute|longitudinal|time period)\b", normalized):
        missing.append("time_horizon")
        prompts.append("What time horizon or observation window is relevant, if any?")

    return ResearchQuestionDecompositionResponse(
        research_question=question,
        question_type=question_type,
        independent_variable=independent,
        dependent_variable=dependent,
        system_or_population=system_or_population,
        context=context,
        missing_elements=missing,
        clarification_prompts=prompts,
        method="bounded_heuristic",
        limitations=[
            "This is a conservative text-pattern heuristic, not semantic understanding "
            "or an LLM result.",
            "Extracted variables may be incomplete or misleading; a researcher must "
            "confirm or edit them.",
            "The response does not generate hypotheses, establish causality, or verify "
            "scientific validity.",
        ],
    )


class PriorWorkCandidate(BaseModel):
    """A single candidate submitted for bounded prior-work screening."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=3, max_length=300)
    statement: str = Field(min_length=10, max_length=6000)


class PriorWorkScreenRequest(BaseModel):
    """A bounded live metadata search for competing candidate hypotheses."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    research_question: str = Field(min_length=10, max_length=5000)
    candidates: list[PriorWorkCandidate] = Field(min_length=2, max_length=5)
    providers: list[Literal["openalex", "crossref"]] = Field(
        default_factory=lambda: ["openalex", "crossref"], min_length=1, max_length=2
    )
    results_per_candidate: int = Field(default=5, ge=1, le=5)

    @field_validator("providers")
    @classmethod
    def unique_providers(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("providers must not contain duplicates")
        return values


class PriorWorkMatch(BaseModel):
    title: str
    doi: str | None
    publication_year: int | None
    source_url: str
    cited_by_count: int | None
    is_retracted: bool | None


class PriorWorkCandidateResult(BaseModel):
    title: str
    query: str
    search_status: Literal["ok", "partial", "unavailable"]
    total_results: int
    matches: list[PriorWorkMatch]
    provider_status: list[dict[str, object]]
    interpretation: str


class PriorWorkScreenResponse(BaseModel):
    research_question: str
    results: list[PriorWorkCandidateResult]
    overall_status: Literal["complete", "partial", "unavailable"]
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
            concerns.append(
                "No source or claim records are linked; evidence traceability is missing."
            )
        if not rubric["alternative_explanations"]:
            concerns.append("At least one serious alternative explanation is required.")
        if not rubric["falsification_criteria"]:
            concerns.append(
                "Specify an observable result that would count against this hypothesis."
            )
        if not rubric["discriminating_test"]:
            concerns.append("Describe a test that distinguishes this candidate from alternatives.")
        duplicate_of = None
        for previous in request.candidates[:index]:
            if _similarity(candidate.statement, previous.statement) >= 0.82:
                duplicate_of = previous.title
                concerns.append(
                    f"Potential near-duplicate of '{previous.title}'; compare explicitly."
                )
                break
        if request.novelty_screen_status == "not_run":
            novelty_status = "not_assessed"
        else:
            novelty_status = "provisional_screen_only"
            concerns.append(
                "Novelty screening is provisional and depends on the scope and quality "
                "of the recorded search."
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
            "Completeness scores measure required fields, not truth, probability, importance, "
            "or scientific merit.",
            "Text similarity is a simple heuristic and can miss paraphrases or flag "
            "unrelated statements.",
            "Novelty cannot be guaranteed by a search; expert review and reproducible "
            "literature-search records are required.",
            "Candidates are supplied by the caller; this endpoint does not independently "
            "generate hypotheses or verify evidence.",
        ],
    )
