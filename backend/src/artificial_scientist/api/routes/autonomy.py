"""Protected API surface for bounded Phase 8 workflow orchestration."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from artificial_scientist.api.routes.records import record_access
from artificial_scientist.autonomy.store import AutonomyStore
from artificial_scientist.autonomy.workflow import WorkflowEngine, WorkflowError, WorkflowState
from artificial_scientist.config import get_settings

router = APIRouter(prefix="/api/v1/autonomy", tags=["scientific autonomy"])


class WorkflowCreateRequest(BaseModel):
    workflow_id: str = Field(min_length=1, max_length=200)
    consequential: bool = True


class WorkflowTransitionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=1000)


class WorkflowApprovalRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)
    actor: str = Field(min_length=1, max_length=200)


class WorkflowCheckpointRequest(BaseModel):
    digest: str = Field(min_length=1, max_length=128)


def _engine(tenant_id: str | None) -> WorkflowEngine:
    settings = get_settings()
    if getattr(settings, "database_url", None):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "PostgreSQL is configured, but autonomy persistence is not migrated. "
                "Requests are blocked to prevent split-database writes."
            ),
        )
    effective_tenant = tenant_id or "development"
    return WorkflowEngine(
        AutonomyStore(settings.database_path),
        tenant_id=effective_tenant,
    )


def _serialize(workflow) -> dict:
    return {
        "workflow_id": workflow.workflow_id,
        "state": workflow.state.value,
        "consequential": workflow.consequential,
        "approval_token_hash_present": workflow.approval_token_hash is not None,
        "checkpoints": list(workflow.checkpoints),
        "transitions": [
            {
                "from_state": item.from_state.value,
                "to_state": item.to_state.value,
                "at": item.at.isoformat(),
                "reason": item.reason,
                "actor": item.actor,
            }
            for item in workflow.transitions
        ],
    }


def _error(error: WorkflowError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


@router.post("/workflows", status_code=status.HTTP_201_CREATED)
def create_workflow(
    request: WorkflowCreateRequest,
    tenant_id: Annotated[str | None, Depends(record_access("autonomy:workflow:create"))],
) -> dict:
    engine = _engine(tenant_id)
    try:
        workflow = engine.create(
            request.workflow_id, consequential=request.consequential
        )
    except WorkflowError as error:
        raise _error(error) from error
    return _serialize(workflow)


@router.get("/workflows/{workflow_id}")
def get_workflow(
    workflow_id: str,
    tenant_id: Annotated[str | None, Depends(record_access("autonomy:workflow:read"))],
) -> dict:
    engine = _engine(tenant_id)
    try:
        return _serialize(engine.get(workflow_id))
    except WorkflowError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/workflows/{workflow_id}/plan")
def plan_workflow(
    workflow_id: str,
    request: WorkflowTransitionRequest,
    tenant_id: Annotated[str | None, Depends(record_access("autonomy:workflow:write"))],
) -> dict:
    return _transition(workflow_id, WorkflowState.PLANNED, request, tenant_id)


@router.post("/workflows/{workflow_id}/request-approval")
def request_approval(
    workflow_id: str,
    request: WorkflowTransitionRequest,
    tenant_id: Annotated[str | None, Depends(record_access("autonomy:workflow:write"))],
) -> dict:
    return _transition(
        workflow_id, WorkflowState.AWAITING_APPROVAL, request, tenant_id
    )


@router.post("/workflows/{workflow_id}/approve")
def approve_workflow(
    workflow_id: str,
    request: WorkflowApprovalRequest,
    tenant_id: Annotated[str | None, Depends(record_access("autonomy:workflow:approve"))],
) -> dict:
    engine = _engine(tenant_id)
    try:
        workflow = engine.approve(
            workflow_id, request.token, actor=request.actor
        )
    except WorkflowError as error:
        raise _error(error) from error
    return _serialize(workflow)


@router.post("/workflows/{workflow_id}/checkpoint")
def checkpoint_workflow(
    workflow_id: str,
    request: WorkflowCheckpointRequest,
    tenant_id: Annotated[str | None, Depends(record_access("autonomy:workflow:write"))],
) -> dict:
    engine = _engine(tenant_id)
    try:
        engine.checkpoint(workflow_id, request.digest)
        return _serialize(engine.get(workflow_id))
    except WorkflowError as error:
        raise _error(error) from error


@router.post("/workflows/{workflow_id}/recover")
def recover_workflow(
    workflow_id: str,
    tenant_id: Annotated[str | None, Depends(record_access("autonomy:workflow:write"))],
) -> dict:
    engine = _engine(tenant_id)
    try:
        return _serialize(engine.recover(workflow_id))
    except WorkflowError as error:
        raise _error(error) from error


def _transition(
    workflow_id: str,
    target: WorkflowState,
    request: WorkflowTransitionRequest,
    tenant_id: str | None,
) -> dict:
    engine = _engine(tenant_id)
    try:
        workflow = engine.transition(
            workflow_id,
            target,
            actor=request.actor,
            reason=request.reason,
        )
    except WorkflowError as error:
        raise _error(error) from error
    return _serialize(workflow)
