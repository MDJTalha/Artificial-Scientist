"""Regression tests for Phase 7 hypothesis assessment and persistence."""

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from artificial_scientist.api.routes.literature import get_literature_service
from artificial_scientist.api.routes.records import get_record_store
from artificial_scientist.discovery import (
    DiscoveryAssessmentRequest,
    HypothesisGenerationRequest,
    ResearchQuestionDecompositionRequest,
    assess_candidates,
    decompose_research_question,
)
from artificial_scientist.literature.models import (
    LiteratureResult,
    LiteratureSearchResponse,
    ProviderSearchStatus,
)
from artificial_scientist.main import app
from artificial_scientist.records.models import ClaimRecord, HypothesisRecord, SourceRecord
from artificial_scientist.records.store import InvalidRelationship, RecordStore


@pytest.fixture(autouse=True)
def opt_in_to_development_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFICIAL_SCIENTIST_ENV", "development")


def candidate(
    title: str = "Hypothesis A",
    statement: str = "Increasing input temperature increases reaction rate under fixed pressure.",
    *,
    sources: list | None = None,
    claims: list | None = None,
) -> dict:
    return {
        "title": title,
        "statement": statement,
        "assumptions": ["Pressure remains fixed."],
        "alternative_explanations": ["Catalyst concentration changed."],
        "predictions": ["Measured rate increases in the predefined temperature range."],
        "falsification_criteria": ["The rate does not increase beyond measurement uncertainty."],
        "discriminating_test": (
            "Randomize temperature levels and measure rate with blinded analysis."
        ),
        "source_record_ids": sources or [],
        "claim_record_ids": claims or [],
    }


@pytest.fixture
def store(tmp_path: Path) -> RecordStore:
    return RecordStore(tmp_path / "discovery.sqlite3")


def test_question_decomposition_extracts_variables_and_exposes_unknowns() -> None:
    result = decompose_research_question(
        ResearchQuestionDecompositionRequest(
            research_question=(
                "How does temperature affect reaction rate under fixed pressure "
                "in a closed reactor?"
            ),
            domain_context="reaction kinetics",
        )
    )
    assert result.question_type == "causal"
    assert result.independent_variable == "temperature"
    assert result.dependent_variable == "reaction rate"
    assert result.system_or_population == "a closed reactor"
    assert "confounders_and_controls" in result.missing_elements
    assert result.method == "bounded_heuristic"


def test_question_decomposition_does_not_invent_unrecognized_variables() -> None:
    result = decompose_research_question(
        ResearchQuestionDecompositionRequest(
            research_question="Why do some complex systems behave unexpectedly?"
        )
    )
    assert result.independent_variable is None
    assert result.dependent_variable is None
    assert "independent_variable" in result.missing_elements
    assert result.clarification_prompts


def test_assessment_is_transparent_and_does_not_claim_truth() -> None:
    request = DiscoveryAssessmentRequest(
        research_question="How does temperature affect reaction rate under fixed pressure?",
        candidates=[
            candidate(sources=[uuid4()]),
            candidate(
                "Hypothesis B",
                (
                    "Catalyst concentration is the dominant driver of reaction rate "
                    "in a closed reactor."
                ),
                sources=[uuid4()],
            ),
        ],
    )
    result = assess_candidates(request)
    assert len(result.assessments) == 2
    assert result.assessments[0].completeness_score == 100
    assert result.assessments[0].rubric["falsification_criteria"] is True
    assert result.overall_status == "draft"
    assert any("not truth" in item for item in result.limitations)


def test_candidate_lists_reject_blank_or_duplicate_items() -> None:
    invalid = candidate()
    invalid["predictions"] = ["Same prediction", " same prediction "]
    with pytest.raises(ValidationError, match="must be unique"):
        DiscoveryAssessmentRequest(
            research_question="How does temperature affect reaction rate?",
            candidates=[
                invalid,
                candidate("Hypothesis B", "An alternate mechanism changes the reaction rate."),
            ],
        )


def test_hypothesis_list_items_have_a_character_limit() -> None:
    invalid = candidate()
    invalid["assumptions"] = ["x" * 2001]
    with pytest.raises(ValidationError, match="at most 2000 characters"):
        DiscoveryAssessmentRequest(
            research_question="How does temperature affect reaction rate?",
            candidates=[
                invalid,
                candidate("Hypothesis B", "Catalyst concentration changes reaction rate."),
            ],
        )


def test_declared_novelty_screen_requires_search_notes() -> None:
    with pytest.raises(ValidationError, match="novelty_screen_notes are required"):
        DiscoveryAssessmentRequest(
            research_question="How does temperature affect reaction rate?",
            candidates=[
                candidate("Hypothesis A", "Temperature increases reaction rate."),
                candidate("Hypothesis B", "Temperature decreases reaction rate."),
            ],
            novelty_screen_status="screened",
        )


def test_near_duplicate_hypotheses_are_flagged() -> None:
    request = DiscoveryAssessmentRequest(
        research_question="What changes reaction rate under controlled conditions?",
        candidates=[
            candidate(
                "First hypothesis",
                "Temperature increases reaction rate under fixed pressure.",
            ),
            candidate(
                "Second hypothesis",
                "Temperature increases reaction rate under fixed pressure.",
            ),
        ],
    )
    result = assess_candidates(request)
    assert result.assessments[1].near_duplicate_of == "First hypothesis"
    assert result.overall_status == "needs_revision"


def test_api_generates_bounded_hypotheses_without_persisting_records() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/discovery/generate",
            json={
                "research_question": "How does temperature affect reaction rate?",
                "independent_variable": "temperature",
                "dependent_variable": "reaction rate",
                "system_or_population": "the reaction system",
                "context": "fixed pressure",
            },
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["candidates"]) == 3
    assert all(
        item["review_status"] == "requires_human_review"
        for item in body["candidates"]
    )
    assert body["candidates"][0]["candidate"]["source_record_ids"] == []



def test_api_persists_hypotheses_with_predictions_and_test(store: RecordStore) -> None:
    source = store.create(
        SourceRecord(
            title="Reaction kinetics reference",
            source_url="https://example.org/kinetics",
            external_identifier="phase7:test:kinetics",
        )
    )
    app.dependency_overrides[get_record_store] = lambda: store
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/discovery/assess",
                json={
                    "research_question": (
                        "How does temperature affect reaction rate under fixed pressure?"
                    ),
                    "candidates": [
                        candidate(sources=[str(source.id)]),
                        candidate(
                            "Hypothesis B",
                            (
                                "Increasing input temperature decreases reaction rate "
                                "under fixed pressure."
                            ),
                            sources=[str(source.id)],
                        ),
                    ],
                },
            )
        assert response.status_code == 201, response.text
        body = response.json()
        assert len(body["assessments"]) == 2
        record_id = body["assessments"][0]["persisted_record_id"]
        stored = store.get(record_id)
        record = HypothesisRecord.model_validate(stored.payload)
        assert record.predictions == [
            "Measured rate increases in the predefined temperature range."
        ]
        assert record.discriminating_test.startswith("Randomize temperature")
        assert record.source_record_ids == [source.id]
        events, total = store.list_audit_events()
        assert total == 3
        assert any(event.record_id == record.id for event in events)
    finally:
        app.dependency_overrides.pop(get_record_store, None)


def test_api_rejects_missing_evidence_before_persisting_any_hypothesis(
    store: RecordStore,
) -> None:
    app.dependency_overrides[get_record_store] = lambda: store
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/discovery/assess",
                json={
                    "research_question": "How does temperature affect reaction rate?",
                    "candidates": [
                        candidate(sources=[str(uuid4())]),
                        candidate(
                            "Hypothesis B",
                            "A different mechanism changes reaction rate under fixed pressure.",
                        ),
                    ],
                },
            )
        assert response.status_code == 422
        _, total = store.list_records()
        assert total == 0
    finally:
        app.dependency_overrides.pop(get_record_store, None)


def test_api_rejects_source_reference_with_wrong_record_type(store: RecordStore) -> None:
    stored_claim = store.create(
        ClaimRecord(
            claim_text="A stored claim record for evidence validation.",
            evidence_status="inferred",
        )
    )
    app.dependency_overrides[get_record_store] = lambda: store
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/discovery/assess",
                json={
                    "research_question": "How does temperature affect reaction rate?",
                    "candidates": [
                        candidate(sources=[str(stored_claim.id)]),
                        candidate(
                            "Hypothesis B",
                            "An alternative mechanism changes reaction rate under fixed pressure.",
                        ),
                    ],
                },
            )
        assert response.status_code == 422
        _, total = store.list_records()
        assert total == 1
    finally:
        app.dependency_overrides.pop(get_record_store, None)



def test_batch_record_creation_rolls_back_every_record_on_reference_failure(
    store: RecordStore,
) -> None:
    first = HypothesisRecord(
        title="Valid hypothesis",
        hypothesis="A testable scientific hypothesis with enough detail.",
        falsification_criteria=["The predicted effect is absent."],
    )
    second = HypothesisRecord(
        title="Invalid hypothesis",
        hypothesis="A second testable scientific hypothesis with enough detail.",
        falsification_criteria=["The predicted effect is absent."],
        source_record_ids=[uuid4()],
    )
    with pytest.raises(InvalidRelationship, match="does not exist"):
        store.create_many([first, second])
    _, total = store.list_records()
    assert total == 0


def test_prior_work_screen_uses_metadata_search_without_persisting() -> None:
    class FakeLiteratureService:
        def __init__(self) -> None:
            self.requests = []

        def search(self, request):
            self.requests.append(request)
            return LiteratureSearchResponse(
                query=request.query,
                status="ok",
                total_results=1,
                results=[
                    LiteratureResult(
                        title="Related reaction kinetics study",
                        doi="10.1234/example",
                        publication_year=2024,
                        source_url="https://example.org/related-study",
                        matched_providers=["openalex"],
                        cited_by_count=4,
                    )
                ],
                providers=[
                    ProviderSearchStatus(
                        provider="openalex", status="ok", result_count=1
                    ),
                    ProviderSearchStatus(
                        provider="crossref", status="ok", result_count=1
                    ),
                ],
            )

    fake_service = FakeLiteratureService()
    app.dependency_overrides[get_literature_service] = lambda: fake_service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/discovery/prior-work-screen",
                json={
                    "research_question": "How does temperature affect reaction rate?",
                    "candidates": [
                        {
                            "title": "Hypothesis A",
                            "statement": (
                                "Temperature increases reaction rate under fixed pressure."
                            ),
                        },
                        {
                            "title": "Hypothesis B",
                            "statement": (
                                "Temperature decreases reaction rate under fixed pressure."
                            ),
                        },
                    ],
                },
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["overall_status"] == "complete"
        assert body["results"][0]["total_results"] == 1
        assert body["results"][0]["matches"][0]["doi"] == "10.1234/example"
        assert len(fake_service.requests) == 2
        assert all(item.persist_results is False for item in fake_service.requests)
        assert all(item.limit == 5 for item in fake_service.requests)
    finally:
        app.dependency_overrides.pop(get_literature_service, None)



def test_discovery_request_body_is_bounded_before_json_parsing() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/discovery/decompose",
        content=b" " * (1024 * 1024 + 1),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "Request body exceeds the endpoint size limit."
