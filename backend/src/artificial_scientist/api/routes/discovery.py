"""API for structured hypothesis comparison and falsification planning."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from artificial_scientist.api.routes.literature import get_literature_service
from artificial_scientist.api.routes.records import get_record_store, record_access
from artificial_scientist.discovery import (
    DiscoveryAssessmentRequest,
    HypothesisGenerationRequest,
    HypothesisGenerationResponse,
    DiscoveryAssessmentResponse,
    HypothesisCandidate,
    PriorWorkCandidateResult,
    PriorWorkMatch,
    PriorWorkScreenRequest,
    PriorWorkScreenResponse,
    ResearchQuestionDecompositionRequest,
    ResearchQuestionDecompositionResponse,
    assess_candidates,
    decompose_research_question,
    generate_hypotheses,
)
from artificial_scientist.literature.models import LiteratureSearchRequest
from artificial_scientist.literature.service import LiteratureService
from artificial_scientist.records.models import HypothesisRecord
from artificial_scientist.records.store import (
    InvalidRelationship,
    RecordConflict,
    RecordIntegrityError,
    RecordNotFound,
    RecordStore,
    RecordStoreError,
)

router = APIRouter(prefix="/api/v1/discovery", tags=["hypothesis discovery"])


def _validate_evidence_references(
    store: RecordStore, candidate: HypothesisCandidate, *, tenant_id: str | None = None
) -> None:
    """Fail before writes if a referenced source or claim is missing or has wrong type."""
    for record_id in candidate.source_record_ids:
        try:
            record = store.get(record_id, tenant_id=tenant_id)
        except RecordNotFound as error:
            raise HTTPException(
                status_code=422, detail=f"Source record {record_id} does not exist."
            ) from error
        except RecordStoreError as error:
            raise HTTPException(
                status_code=500, detail="Evidence reference integrity verification failed."
            ) from error
        if record.record_type != "source":
            raise HTTPException(
                status_code=422, detail=f"Evidence record {record_id} is not a source."
            )
    for record_id in candidate.claim_record_ids:
        try:
            record = store.get(record_id, tenant_id=tenant_id)
        except RecordNotFound as error:
            raise HTTPException(
                status_code=422, detail=f"Claim record {record_id} does not exist."
            ) from error
        except RecordStoreError as error:
            raise HTTPException(
                status_code=500, detail="Evidence reference integrity verification failed."
            ) from error
        if record.record_type != "claim":
            raise HTTPException(
                status_code=422, detail=f"Evidence record {record_id} is not a claim."
            )


@router.post(
    "/decompose",
    response_model=ResearchQuestionDecompositionResponse,
    summary="Create a bounded research-question decomposition draft",
)
def decompose_question(
    request: ResearchQuestionDecompositionRequest,
    tenant_id: Annotated[str | None, Depends(record_access("discovery:decompose"))],
) -> ResearchQuestionDecompositionResponse:
    """Extract conservative variable/context hints and expose unresolved details."""
    return decompose_research_question(request)


@router.post(
    "/prior-work-screen",
    response_model=PriorWorkScreenResponse,
    summary="Screen competing hypotheses against scholarly metadata",
)
def screen_prior_work(
    request: PriorWorkScreenRequest,
    service: Annotated[LiteratureService, Depends(get_literature_service)],
    tenant_id: Annotated[str | None, Depends(record_access("discovery:prior-work-screen"))],
) -> PriorWorkScreenResponse:
    """Search bounded OpenAlex/Crossref metadata; results are not proof of novelty."""
    results: list[PriorWorkCandidateResult] = []
    for candidate in request.candidates:
        query = f"{candidate.title}: {candidate.statement}"[:500]
        response = service.search(
            LiteratureSearchRequest(
                query=query,
                limit=request.results_per_candidate,
                providers=request.providers,
                persist_results=False,
            )
        )
        matches = [
            PriorWorkMatch(
                title=item.title,
                doi=item.doi,
                publication_year=item.publication_year,
                source_url=str(item.source_url),
                cited_by_count=item.cited_by_count,
                is_retracted=item.is_retracted,
            )
            for item in response.results
        ]
        if response.status == "unavailable":
            interpretation = (
                "The metadata search was unavailable; no novelty conclusion can be drawn."
            )
        elif matches:
            interpretation = (
                "Related metadata was returned. Review original sources and compare "
                "methods, results, populations, and limitations before judging novelty."
            )
        else:
            interpretation = (
                "No matches were returned by the queried providers; this does not establish "
                "novelty or prove that relevant work does not exist."
            )
        results.append(
            PriorWorkCandidateResult(
                title=candidate.title,
                query=response.query,
                search_status=response.status,
                total_results=response.total_results,
                matches=matches,
                provider_status=[item.model_dump(mode="json") for item in response.providers],
                interpretation=interpretation,
            )
        )

    successful = sum(item.search_status == "ok" for item in results)
    if successful == len(results):
        overall_status = "complete"
    elif successful or any(item.search_status == "partial" for item in results):
        overall_status = "partial"
    else:
        overall_status = "unavailable"
    return PriorWorkScreenResponse(
        research_question=request.research_question,
        results=results,
        overall_status=overall_status,
        limitations=[
            "This searches bibliographic metadata only; it does not retrieve or assess full text.",
            "Search coverage, indexing delays, query wording, and provider outages can hide "
            "relevant work.",
            "A result is a prior-work lead, not evidence that the candidate is true or false.",
            "No result is not proof of novelty. Expert review and a documented search "
            "strategy remain required.",
        ],
    )


@router.post(
    "/assess",
    response_model=DiscoveryAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assess competing hypotheses and persist their research records",
)
def assess_hypotheses(
    request: DiscoveryAssessmentRequest,
    store: Annotated[RecordStore, Depends(get_record_store)],
    tenant_id: Annotated[str | None, Depends(record_access("discovery:assess"))],
) -> DiscoveryAssessmentResponse:
    """Assess structure, detect likely duplicates, and persist auditable hypothesis records."""
    result = assess_candidates(request)
    for candidate in request.candidates:
        _validate_evidence_references(store, candidate, tenant_id=tenant_id)

    records: list[HypothesisRecord] = []
    for candidate in request.candidates:
        notes = request.novelty_screen_notes
        if request.novelty_screen_status == "screened" and not notes:
            notes = (
                "Caller marked a novelty screen as completed but supplied no search notes; "
                "treat this as unverified and repeat a documented literature search."
            )
        records.append(
            HypothesisRecord(
                title=candidate.title,
                hypothesis=candidate.statement,
                assumptions=candidate.assumptions,
                alternative_explanations=candidate.alternative_explanations,
                falsification_criteria=candidate.falsification_criteria,
                predictions=candidate.predictions,
                discriminating_test=candidate.discriminating_test,
                source_record_ids=candidate.source_record_ids,
                claim_record_ids=candidate.claim_record_ids,
                novelty_assessment=(
                    "literature_screened"
                    if request.novelty_screen_status == "screened"
                    else "not_assessed"
                ),
                novelty_notes=notes,
                provenance={
                    "method": "human_provided",
                    "notes": (
                        "Structured hypothesis assessment; rubric scores are not scientific "
                        "confidence estimates."
                    ),
                },
            )
        )
    try:
        saved = store.create_many(records, tenant_id=tenant_id)
    except (InvalidRelationship, RecordConflict) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RecordIntegrityError as error:
        raise HTTPException(
            status_code=500, detail="Stored research record failed integrity verification."
        ) from error
    except RecordStoreError as error:
        raise HTTPException(
            status_code=500, detail="Hypothesis records could not be persisted."
        ) from error

    for assessment, envelope in zip(result.assessments, saved, strict=True):
        assessment.persisted_record_id = envelope.id
    return result
