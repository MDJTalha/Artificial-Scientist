"""API endpoints for the controlled computational laboratory."""

from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from artificial_scientist.config import get_settings
from artificial_scientist.lab.engine import run_lab
from artificial_scientist.lab.manifest import capture_environment_manifest
from artificial_scientist.lab.models import (
    LabArtifactMetadata,
    LabArtifactResponse,
    LabRunRequest,
    LabRunResponse,
    LabRunVerificationResponse,
)
from artificial_scientist.lab.integrity import result_digest
from artificial_scientist.lab.store import (
    LabArtifactNotFound,
    LabRunNotFound,
    LabRunStore,
)

router = APIRouter(prefix="/api/v1/lab", tags=["controlled computational laboratory"])


@lru_cache(maxsize=1)
def get_lab_store() -> LabRunStore:
    """Create the SQLite store for persisted lab-run records."""
    return LabRunStore(get_settings().database_path)


@router.post("/runs", response_model=LabRunResponse, status_code=status.HTTP_201_CREATED)
def create_lab_run(
    request: LabRunRequest,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> LabRunResponse:
    """Execute a bounded declarative run and persist its traceable response."""
    run = run_lab(request)
    return store.save(run)


@router.get("/runs", response_model=dict[str, object])
def list_lab_runs(
    store: Annotated[LabRunStore, Depends(get_lab_store)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    """List persisted lab runs with bounded pagination."""
    try:
        runs, total = store.list_runs(limit=limit, offset=offset)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored lab run failed integrity validation.",
        ) from error
    return {"items": runs, "total": total, "limit": limit, "offset": offset}


@router.get("/runs/{run_id}", response_model=LabRunResponse)
def get_lab_run(
    run_id: UUID,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> LabRunResponse:
    """Retrieve a persisted run by UUID."""
    try:
        return store.get(run_id)
    except LabRunNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lab run not found."
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored lab run failed integrity validation.",
        ) from error


@router.post("/runs/{run_id}/verify", response_model=LabRunVerificationResponse)
def verify_lab_run(
    run_id: UUID,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> LabRunVerificationResponse:
    """Replay a stored declarative configuration and compare scientific outputs."""
    try:
        recorded = store.get(run_id)
    except LabRunNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lab run not found."
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored lab run failed integrity validation.",
        ) from error

    if not recorded.configuration:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This stored run predates replayable configuration metadata.",
        )
    try:
        request = LabRunRequest.model_validate(recorded.configuration)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored lab configuration failed validation.",
        ) from error

    replay = run_lab(request)
    configuration_matches = replay.configuration_sha256 == recorded.configuration_sha256
    current_environment = capture_environment_manifest()
    environment_matches = (
        bool(recorded.environment_manifest)
        and current_environment == recorded.environment_manifest
    )
    recorded_outputs = [
        {
            "step_id": step.step_id,
            "operation": step.operation,
            "status": step.status,
            "output": step.output,
            "error": step.error,
        }
        for step in recorded.steps
    ]
    replay_outputs = [
        {
            "step_id": step.step_id,
            "operation": step.operation,
            "status": step.status,
            "output": step.output,
            "error": step.error,
        }
        for step in replay.steps
    ]
    outputs_match = recorded_outputs == replay_outputs
    differences: list[str] = []
    if not configuration_matches:
        differences.append("configuration_digest_mismatch")
    if not environment_matches:
        differences.append("runtime_environment_mismatch_or_manifest_missing")
    if not outputs_match:
        differences.append("scientific_step_outputs_mismatch")
    return LabRunVerificationResponse(
        run_id=recorded.run_id,
        reproducible=configuration_matches and environment_matches and outputs_match,
        configuration_matches=configuration_matches,
        environment_matches=environment_matches,
        outputs_match=outputs_match,
        differences=differences,
        recorded_environment=recorded.environment_manifest,
        current_environment=current_environment,
    )


@router.get("/runs/{run_id}/artifacts", response_model=list[LabArtifactMetadata])
def list_lab_run_artifacts(
    run_id: UUID,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> list[LabArtifactMetadata]:
    """List artifact metadata and provenance attached to one run."""
    try:
        return store.list_artifacts(run_id)
    except LabRunNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lab run not found."
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored lab artifact failed integrity validation.",
        ) from error


@router.get("/artifacts/{artifact_id}", response_model=LabArtifactResponse)
def get_lab_artifact(
    artifact_id: UUID,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> LabArtifactResponse:
    """Retrieve an artifact after validating its byte digest and run provenance."""
    try:
        return store.get_artifact(artifact_id)
    except LabArtifactNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lab artifact not found."
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored lab artifact failed integrity validation.",
        ) from error
