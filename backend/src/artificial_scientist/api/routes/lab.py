"""API endpoints for the controlled computational laboratory."""

import asyncio
import hashlib
import hmac
import io
import json
import re
import zipfile
from functools import lru_cache
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status

from artificial_scientist.authorization import (
    AuthorizationDenied,
    TenantDirectory,
    stable_principal_id,
)
from artificial_scientist.config import get_settings
from artificial_scientist.identity import (
    AuthenticatedPrincipal,
    IdentityConfigurationError,
    InvalidIdentityError,
    validate_oidc_bearer_token,
)
from artificial_scientist.lab.engine import run_lab
from artificial_scientist.lab.execution_adapter import ExecutionAdapterUnavailable
from artificial_scientist.lab.manifest import capture_environment_manifest
from artificial_scientist.lab.models import (
    LabArtifactMetadata,
    LabArtifactResponse,
    LabRunRequest,
    LabRunResponse,
    LabRunVerificationResponse,
)
from artificial_scientist.lab.scanning import (
    MalwareDetected,
    ScannerUnavailable,
    scan_binary_content,
)
from artificial_scientist.lab.store import (
    LabArtifactNotFound,
    LabExecutionNotFound,
    LabQuotaExceeded,
    LabRunNotFound,
    LabRunStore,
)


def require_lab_access(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    """Require a validated, per-user OIDC identity for non-development lab access."""
    settings = get_settings()
    database_path = getattr(settings, "database_path", None)
    if database_path:
        request.state.security_audit_database_path = database_path
    if settings.environment.lower() == "development":
        request.state.authenticated_principal = AuthenticatedPrincipal(
            subject="local-development-principal",
            issuer="artificial-scientist-development",
            audience="artificial-scientist-lab",
        )
        return

    oidc_values = (
        getattr(settings, "oidc_issuer", None),
        getattr(settings, "oidc_audience", None),
        getattr(settings, "oidc_jwks_url", None),
    )
    if not all(oidc_values):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC authentication is not fully configured.",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not token or " " in token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        principal = validate_oidc_bearer_token(
            token,
            issuer=oidc_values[0],
            audience=oidc_values[1],
            jwks_url=oidc_values[2],
            audience_claim=getattr(settings, "oidc_audience_claim", "aud"),
            expected_token_use=getattr(settings, "oidc_token_use", None),
            expected_scope=getattr(settings, "oidc_required_scope", None),
        )
    except IdentityConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC authentication configuration is invalid.",
        ) from error
    except InvalidIdentityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token validation failed.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    request.state.authenticated_principal = principal


router = APIRouter(
    prefix="/api/v1/lab",
    tags=["controlled computational laboratory"],
    dependencies=[Depends(require_lab_access)],
)


@lru_cache(maxsize=1)
def get_lab_store() -> LabRunStore:
    """Create the SQLite store for persisted lab-run records."""
    return LabRunStore(get_settings().database_path)


def require_tenant_access(request: Request, action: str) -> str | None:
    """Resolve a tenant selector only after server-side principal membership checks.

    Development remains deliberately unscoped for backwards-compatible local testing.
    Production requests require a validated OIDC principal and active tenant membership.
    """
    settings = get_settings()
    if settings.environment.lower() == "development":
        return None
    principal = getattr(request.state, "authenticated_principal", None)
    tenant_id = request.headers.get("x-tenant-id", "").strip()
    if principal is None or not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated tenant membership is required.",
        )
    principal_id = stable_principal_id(principal.issuer, principal.subject)
    correlation_id = request.headers.get("x-correlation-id", "").strip()
    # Correlation IDs are untrusted metadata. Keep a conservative printable
    # alphabet so control characters and whitespace cannot pollute audit records.
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", correlation_id):
        correlation_id = str(uuid4())

    # Tenant IDs are generated UUIDs. Reject malformed or unbounded selectors before
    # opening the directory or writing an audit row containing attacker-controlled data.
    # The rejection itself is still audited, but as an unscoped request with no tenant ID.
    try:
        parsed_tenant_id = UUID(tenant_id)
        valid_tenant_id = str(parsed_tenant_id) == tenant_id.lower()
    except (ValueError, AttributeError):
        valid_tenant_id = False
    if not valid_tenant_id:
        request.state.authorization_audit = {
            "principal_id": principal_id,
            "tenant_id": None,
            "database_path": settings.database_path,
            "action": action,
            "target_type": "request",
            "target_id": None,
            "correlation_id": correlation_id,
            "method": request.method,
            "route": request.url.path,
        }
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested tenant resource is not available.",
        )

    tenant_id = str(parsed_tenant_id)
    directory = TenantDirectory(settings.database_path)
    path_params = request.path_params
    target_id = next(
        (
            str(path_params[key])
            for key in ("run_id", "artifact_id")
            if path_params.get(key) is not None
        ),
        tenant_id,
    )
    target_type = (
        "binary_artifact"
        if "binary-artifacts" in request.url.path
        else "artifact"
        if path_params.get("artifact_id") is not None
        else "run"
        if path_params.get("run_id") is not None
        else "tenant"
    )
    request.state.authorization_audit = {
        "principal_id": principal_id,
        "tenant_id": tenant_id,
        "database_path": settings.database_path,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "correlation_id": correlation_id,
        "method": request.method,
        "route": request.url.path,
    }
    try:
        directory.authorize(principal_id, tenant_id, action)
    except (AuthorizationDenied, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested tenant resource is not available.",
        ) from error
    return tenant_id


@router.post("/runs", response_model=LabRunResponse, status_code=status.HTTP_201_CREATED)
def create_lab_run(
    lab_request: LabRunRequest,
    http_request: Request,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> LabRunResponse:
    """Execute a bounded declarative run and persist its traceable response."""
    tenant_id = require_tenant_access(http_request, "run:create")
    run_id = uuid4()
    try:
        store.begin_execution(run_id, lab_request, tenant_id=tenant_id)
    except LabQuotaExceeded as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Tenant has reached its lab run quota.",
        ) from error
    try:
        run = run_lab(lab_request, run_id=run_id)
        # Persistence can fail independently (for example, a tenant storage quota).
        # Mark the reservation failed rather than leaving a false "running" status.
        return store.save(run, tenant_id=tenant_id)
    except ExecutionAdapterUnavailable as error:
        store.fail_execution(run_id, tenant_id=tenant_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No reviewed lab execution sandbox is configured.",
        ) from error
    except Exception:
        store.fail_execution(run_id, tenant_id=tenant_id)
        raise


@router.get("/runs/{run_id}/execution-status", response_model=dict[str, object])
def get_lab_execution_status(
    run_id: UUID,
    request: Request,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> dict[str, object]:
    """Retrieve durable execution status, including recovered interruptions."""
    tenant_id = require_tenant_access(request, "run:read")
    try:
        return store.get_execution_status(run_id, tenant_id=tenant_id)
    except LabExecutionNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab execution attempt not found.",
        ) from error


@router.get("/runs", response_model=dict[str, object])
def list_lab_runs(
    request: Request,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    """List persisted lab runs with bounded pagination."""
    tenant_id = require_tenant_access(request, "run:list")
    try:
        runs, total = store.list_runs(limit=limit, offset=offset, tenant_id=tenant_id)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored lab run failed integrity validation.",
        ) from error
    return {"items": runs, "total": total, "limit": limit, "offset": offset}


@router.get("/runs/{run_id}", response_model=LabRunResponse)
def get_lab_run(
    run_id: UUID,
    request: Request,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> LabRunResponse:
    """Retrieve a persisted run by UUID."""
    tenant_id = require_tenant_access(request, "run:read")
    try:
        return store.get(run_id, tenant_id=tenant_id)
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
    request: Request,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> LabRunVerificationResponse:
    """Replay a stored declarative configuration and compare scientific outputs."""
    tenant_id = require_tenant_access(request, "run:verify")
    try:
        recorded = store.get(run_id, tenant_id=tenant_id)
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
    request: Request,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> Response:
    """Export a run and its verified result artifact as a checksum-manifest ZIP."""
    tenant_id = require_tenant_access(request, "run:export")
    try:
        run = store.get(run_id, tenant_id=tenant_id)
        artifacts = store.list_artifacts(run_id, tenant_id=tenant_id)
        artifact_documents = [
            store.get_artifact(item.artifact_id, tenant_id=tenant_id).model_dump(mode="json")
            for item in artifacts
        ]
        binary_artifacts = store.list_binary_artifacts(run_id, tenant_id=tenant_id)
        binary_documents = [
            store.get_binary_artifact(UUID(item["artifact_id"]), tenant_id=tenant_id)
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
    request: Request,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> list[LabArtifactMetadata]:
    """List artifact metadata and provenance attached to one run."""
    tenant_id = require_tenant_access(request, "artifact:read")
    try:
        return store.list_artifacts(run_id, tenant_id=tenant_id)
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
    request: Request,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> LabArtifactResponse:
    """Retrieve an artifact after validating its byte digest and run provenance."""
    tenant_id = require_tenant_access(request, "artifact:read")
    try:
        return store.get_artifact(artifact_id, tenant_id=tenant_id)
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
    tenant_id = require_tenant_access(request, "artifact:upload")
    # Check run ownership before consuming or scanning an attacker-controlled body.
    # Otherwise a tenant could make the service spend upload/scanner resources against
    # another tenant's run even though persistence eventually rejects the attachment.
    try:
        store.get(run_id, tenant_id=tenant_id)
    except LabRunNotFound as error:
        raise HTTPException(status_code=404, detail="Lab run not found.") from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=500, detail="Stored lab data failed integrity validation."
        ) from error

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,179}", filename):
        raise HTTPException(status_code=422, detail="Invalid binary artifact filename.")

    raw_content_type = request.headers.get("content-type", "application/octet-stream")
    media_type = raw_content_type.split(";", 1)[0].strip()
    media_type_pattern = r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+"
    if not re.fullmatch(media_type_pattern, media_type):
        raise HTTPException(status_code=422, detail="Invalid binary artifact content type.")

    content_length = request.headers.get("content-length")
    if content_length is not None:
        # HTTP Content-Length is a non-negative ASCII decimal byte count. Reject
        # signs, whitespace, and Unicode digits; compare normalized decimal strings
        # before int conversion so an attacker cannot trigger Python's huge-int limit.
        if not content_length.isascii() or not content_length.isdecimal():
            raise HTTPException(status_code=400, detail="Invalid Content-Length header.")
        normalized_length = content_length.lstrip("0") or "0"
        maximum_length = str(_MAX_BINARY_ARTIFACT_BYTES)
        if len(normalized_length) > len(maximum_length) or (
            len(normalized_length) == len(maximum_length)
            and normalized_length > maximum_length
        ):
            raise HTTPException(
                status_code=413, detail="Binary artifact exceeds the 10 MiB limit."
            )
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > _MAX_BINARY_ARTIFACT_BYTES:
            raise HTTPException(status_code=413, detail="Binary artifact exceeds the 10 MiB limit.")
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content:
        raise HTTPException(
            status_code=422,
            detail="Binary artifacts must be between 1 byte and 10 MiB.",
        )
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
            media_type,
            content,
            scan_status=scan_status,
            tenant_id=tenant_id,
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
    request: Request,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> list[dict[str, object]]:
    """List validated binary attachment metadata for a run."""
    tenant_id = require_tenant_access(request, "artifact:read")
    try:
        return store.list_binary_artifacts(run_id, tenant_id=tenant_id)
    except LabRunNotFound as error:
        raise HTTPException(status_code=404, detail="Lab run not found.") from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=500, detail="Stored binary artifact failed integrity validation."
        ) from error


@router.get("/binary-artifacts/{artifact_id}")
def download_lab_binary_artifact(
    artifact_id: UUID,
    request: Request,
    store: Annotated[LabRunStore, Depends(get_lab_store)],
) -> Response:
    """Download a binary attachment after digest and provenance validation."""
    tenant_id = require_tenant_access(request, "artifact:read")
    try:
        artifact = store.get_binary_artifact(artifact_id, tenant_id=tenant_id)
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
