"""API for structured hypothesis comparison and falsification planning."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from artificial_scientist.api.routes.records import get_record_store
from artificial_scientist.discovery import (
    DiscoveryAssessmentRequest,
    DiscoveryAssessmentResponse,
    assess_candidates,
)
from artificial_scientist.records.models import HypothesisRecord, RecordEnvelope
from artificial_scientist.records.store import (
    InvalidRelationship,
    RecordConflict,
    RecordIntegrityError,
    RecordNotFound,
    RecordStore,
    RecordStoreError,
)

router = APIRouter(prefix="/api/v1/discovery", tags=["hypothesis discovery"])


def _validate_evidence_references(store: RecordStore, candidate: object) -> None:
    """Fail before writes if a referenced source or claim is missing or has wrong type."""
    for record_id in candidate.source_record_ids:
        try:
            record = store.get(record_id)
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
            record = store.get(record_id)
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
    "/assess",
    response_model=DiscoveryAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assess competing hypotheses and persist their research records",
)
def assess_hypotheses(
    request: DiscoveryAssessmentRequest,
    store: Annotated[RecordStore, Depends(get_record_store)],
) -> DiscoveryAssessmentResponse:
    """Assess structure, detect likely duplicates, and persist auditable hypothesis records."""
    result = assess_candidates(request)
    for candidate in request.candidates:
        _validate_evidence_references(store, candidate)

    saved: list[RecordEnvelope] = []
    try:
        for candidate, assessment in zip(request.candidates, result.assessments, strict=True):
            notes = request.novelty_screen_notes
            if request.novelty_screen_status == "screened" and not notes:
                notes = (
                    "Caller marked a novelty screen as completed but supplied no search notes; "
                    "treat this as unverified and repeat a documented literature search."
                )
            record = HypothesisRecord(
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
            saved.append(store.create(record))
            assessment.persisted_record_id = saved[-1].id
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

    return result
