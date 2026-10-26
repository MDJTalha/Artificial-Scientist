"""API endpoints for the controlled computational laboratory."""

import asyncio
import hashlib
import hmac
import io
import json
import zipfile
from functools import lru_cache
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status

from artificial_scientist.config import get_settings
from artificial_scientist.lab.engine import run_lab
from artificial_scientist.lab.manifest import capture_environment_manifest
from artificial_scientist.lab.scanning import (
    MalwareDetected,
    ScannerUnavailable,
    scan_binary_content,
)
from artificial_scientist.lab.models import (
    LabArtifactMetadata,
    LabArtifactResponse,
    LabRunRequest,
    LabRunResponse,
    LabRunVerificationResponse,
)
from artificial_scientist.lab.store import (
    LabArtifactNotFound,
    LabExecutionNotFound,
    LabRunNotFound,
    LabRunStore,
)


def require_lab_access(x_lab_api_key: str | None = Header(default=None)) -> None:
    """Require a configured shared API key outside local development."""
    settings = get_settings()
    if settings.environment.lower() == "development":
        return
    if not settings.lab_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lab API authentication is not configured.",
        )
    if len(settings.lab_api_key) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lab API authentication requires a configured key of at least 32 characters.",
        )
    if not x_lab_api_key or not hmac.compare_digest(x_lab_api_key, settings.lab_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid lab API key required.",
            headers={"WWW-Authenticate": "ApiKey"},
        )


router = APIRouter(
    prefix="/api/v1/lab",
    tags=["controlled computational laboratory"],
    dependencies=[Depends(require_lab_access)],
)


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
    run_id = uuid4()
    store.begin_execution(run_id, request)
    try:
        run = run_lab(request, run_id=run_id)
    except Exception:
        store.fail_execution(run_id)
        raise
    return store.save(run)


@router.get("/runs/{run_id}/execution-status", response_model=dict[str, object])
def get_lab_execution_status(
    run_id: UUID,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> dict[str, object]:
    """Retrieve durable execution status, including recovered interruptions."""
    try:
        return store.get_execution_status(run_id)
    except LabExecutionNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab execution attempt not found.",
        ) from error


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


@router.get("/runs/{run_id}/export")
def export_lab_run(
    run_id: UUID,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> Response:
    """Export a run and its verified result artifact as a checksum-manifest ZIP."""
    try:
        run = store.get(run_id)
        artifacts = store.list_artifacts(run_id)
        artifact_documents = [
            store.get_artifact(item.artifact_id).model_dump(mode="json")
            for item in artifacts
        ]
        binary_artifacts = store.list_binary_artifacts(run_id)
        binary_documents = [
            store.get_binary_artifact(UUID(item["artifact_id"]))
            for item in binary_artifacts
        ]
    except LabRunNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lab run not found."
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored lab data failed integrity validation.",
        ) from error

    files = {
        "run.json": json.dumps(
            run.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8"),
        "artifacts.json": json.dumps(
            artifact_documents, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8"),
        "binary-artifacts.json": json.dumps(
            [
                {key: value for key, value in item.items() if key != "content"}
                for item in binary_documents
            ],
            sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8"),
    }
    for item in binary_documents:
        files[f"binary/{item['artifact_id']}-{item['filename']}"] = item["content"]
    manifest = {
        "format": "asds-lab-export-v1",
        "run_id": str(run_id),
        "files": {
            name: {"sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
            for name, content in files.items()
        },
        "note": "Checksums detect accidental changes; this manifest is not digitally signed.",
    }
    files["manifest.json"] = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="lab-run-{run_id}.zip"'},
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



_MAX_BINARY_ARTIFACT_BYTES = 10 * 1024 * 1024


@router.post("/runs/{run_id}/binary-artifacts", status_code=status.HTTP_201_CREATED)
async def upload_lab_binary_artifact(
    run_id: UUID,
    request: Request,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
    filename: str = Query(min_length=1, max_length=180),
) -> dict[str, object]:
    """Upload a bounded binary attachment using the request body as its bytes."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > _MAX_BINARY_ARTIFACT_BYTES:
                raise HTTPException(
                    status_code=413, detail="Binary artifact exceeds the 10 MiB limit."
                )
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header.") from error
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > _MAX_BINARY_ARTIFACT_BYTES:
            raise HTTPException(status_code=413, detail="Binary artifact exceeds the 10 MiB limit.")
        chunks.append(chunk)
    content = b"".join(chunks)
    try:
        scan_status = await asyncio.to_thread(
            scan_binary_content,
            content,
            environment=get_settings().environment,
        )
    except MalwareDetected as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ScannerUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Attachment scanning is unavailable; upload was not stored.",
        ) from error
    try:
        artifact = store.save_binary_artifact(
            run_id,
            filename,
            request.headers.get("content-type", "application/octet-stream")
            .split(";", 1)[0]
            .strip(),
            content,
        )
        return {**artifact, "scan_status": scan_status}
    except LabRunNotFound as error:
        raise HTTPException(status_code=404, detail="Lab run not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=500, detail="Stored lab data failed integrity validation."
        ) from error


@router.get("/runs/{run_id}/binary-artifacts")
def list_lab_binary_artifacts(
    run_id: UUID,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> list[dict[str, object]]:
    """List validated binary attachment metadata for a run."""
    try:
        return store.list_binary_artifacts(run_id)
    except LabRunNotFound as error:
        raise HTTPException(status_code=404, detail="Lab run not found.") from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=500, detail="Stored binary artifact failed integrity validation."
        ) from error


@router.get("/binary-artifacts/{artifact_id}")
def download_lab_binary_artifact(
    artifact_id: UUID,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> Response:
    """Download a binary attachment after digest and provenance validation."""
    try:
        artifact = store.get_binary_artifact(artifact_id)
    except LabArtifactNotFound as error:
        raise HTTPException(status_code=404, detail="Lab binary artifact not found.") from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=500, detail="Stored binary artifact failed integrity validation."
        ) from error
    return Response(
        content=artifact["content"],
        media_type=str(artifact["content_type"]),
        headers={
            "Content-Disposition": f'attachment; filename="{artifact["filename"]}"',
            "X-Content-SHA256": str(artifact["sha256"]),
            "X-Content-Length": str(artifact["size_bytes"]),
            "X-Content-Type-Options": "nosniff",
        },
    )
