"""Phase 8: explicit, recoverable scientific workflow orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from artificial_scientist.autonomy.store import AutonomyStore


class WorkflowState(StrEnum):
    DRAFT = "draft"
    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    RUNNING = "running"
    PAUSED = "paused"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowError(ValueError):
    """Raised when a workflow transition or approval is invalid."""


_ALLOWED = {
    WorkflowState.DRAFT: {WorkflowState.PLANNED, WorkflowState.CANCELLED},
    WorkflowState.PLANNED: {
        WorkflowState.AWAITING_APPROVAL,
        WorkflowState.FAILED,
        WorkflowState.CANCELLED,
    },
    WorkflowState.AWAITING_APPROVAL: {WorkflowState.APPROVED, WorkflowState.CANCELLED},
    WorkflowState.APPROVED: {WorkflowState.RUNNING, WorkflowState.CANCELLED},
    WorkflowState.RUNNING: {
        WorkflowState.PAUSED,
        WorkflowState.VERIFYING,
        WorkflowState.FAILED,
        WorkflowState.CANCELLED,
    },
    WorkflowState.PAUSED: {WorkflowState.RUNNING, WorkflowState.CANCELLED},
    WorkflowState.VERIFYING: {
        WorkflowState.COMPLETED,
        WorkflowState.FAILED,
        WorkflowState.PAUSED,
    },
    WorkflowState.FAILED: {WorkflowState.AWAITING_APPROVAL, WorkflowState.CANCELLED},
    WorkflowState.COMPLETED: set(),
    WorkflowState.CANCELLED: set(),
}


@dataclass(frozen=True)
class Transition:
    from_state: WorkflowState
    to_state: WorkflowState
    at: datetime
    reason: str
    actor: str


@dataclass
class Workflow:
    workflow_id: str
    state: WorkflowState = WorkflowState.DRAFT
    consequential: bool = True
    approval_token_hash: str | None = None
    transitions: list[Transition] = field(default_factory=list)
    checkpoints: list[str] = field(default_factory=list)


class WorkflowEngine:
    def __init__(
        self,
        store: AutonomyStore | None = None,
        *,
        tenant_id: str | None = None,
    ):
        if store is not None and not tenant_id:
            raise WorkflowError("tenant_id is required for persistent workflows")
        self._workflows: dict[str, Workflow] = {}
        self.store = store
        self.tenant_id = tenant_id

    @staticmethod
    def _hash(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()

    def _load(self, workflow_id: str) -> Workflow | None:
        if self.store is None:
            return None
        try:
            row = self.store.workflow(workflow_id, tenant_id=self.tenant_id)
        except KeyError:
            return None
        transitions = [
            Transition(
                WorkflowState(item["from_state"]),
                WorkflowState(item["to_state"]),
                datetime.fromisoformat(item["occurred_at"]),
                item["reason"],
                item["actor"],
            )
            for item in self.store.transitions(workflow_id, tenant_id=self.tenant_id)
        ]
        checkpoints = [
            item["digest"]
            for item in self.store.checkpoints(workflow_id, tenant_id=self.tenant_id)
        ]
        return Workflow(
            workflow_id=workflow_id,
            state=WorkflowState(row["state"]),
            consequential=bool(row["consequential"]),
            approval_token_hash=row["approval_token_hash"],
            transitions=transitions,
            checkpoints=checkpoints,
        )

    def create(self, workflow_id: str, *, consequential: bool = True) -> Workflow:
        if workflow_id in self._workflows or self._load(workflow_id) is not None:
            raise WorkflowError("workflow already exists")
        workflow = Workflow(workflow_id=workflow_id, consequential=consequential)
        if self.store:
            self.store.save_workflow(
                workflow_id,
                workflow.state.value,
                consequential,
                None,
                tenant_id=self.tenant_id,
            )
        self._workflows[workflow_id] = workflow
        return workflow

    def get(self, workflow_id: str) -> Workflow:
        workflow = self._workflows.get(workflow_id) or self._load(workflow_id)
        if workflow is None:
            raise WorkflowError("unknown workflow")
        self._workflows[workflow_id] = workflow
        return workflow

    def transition(
        self,
        workflow_id: str,
        to_state: WorkflowState,
        *,
        actor: str,
        reason: str,
        approval_token: str | None = None,
    ) -> Workflow:
        workflow = self.get(workflow_id)
        if to_state not in _ALLOWED[workflow.state]:
            raise WorkflowError(f"invalid transition {workflow.state}->{to_state}")
        if to_state is WorkflowState.RUNNING and workflow.consequential:
            supplied_hash = self._hash(approval_token or "")
            if not workflow.approval_token_hash or supplied_hash != workflow.approval_token_hash:
                raise WorkflowError("consequential workflow requires valid approval")
        old_state = workflow.state
        now = datetime.now(UTC)
        if self.store:
            try:
                self.store.transition(
                    workflow_id,
                    old_state.value,
                    to_state.value,
                    actor,
                    reason,
                    tenant_id=self.tenant_id,
                )
            except ValueError as error:
                self._workflows.pop(workflow_id, None)
                raise WorkflowError(str(error)) from error
        workflow.state = to_state
        workflow.transitions.append(Transition(old_state, to_state, now, reason, actor))
        return workflow

    def approve(self, workflow_id: str, token: str, *, actor: str) -> Workflow:
        if not token or len(token) > 256:
            raise WorkflowError("invalid approval token")
        workflow = self.get(workflow_id)
        if WorkflowState.APPROVED not in _ALLOWED[workflow.state]:
            raise WorkflowError("workflow is not awaiting approval")
        old_state = workflow.state
        token_hash = self._hash(token)
        now = datetime.now(UTC)
        if self.store:
            try:
                self.store.approve(
                    workflow_id,
                    old_state.value,
                    token_hash,
                    actor,
                    tenant_id=self.tenant_id,
                )
            except ValueError as error:
                self._workflows.pop(workflow_id, None)
                raise WorkflowError(str(error)) from error
        workflow.approval_token_hash = token_hash
        workflow.state = WorkflowState.APPROVED
        workflow.transitions.append(
            Transition(old_state, workflow.state, now, "explicit approval", actor)
        )
        return workflow

    def checkpoint(self, workflow_id: str, digest: str) -> None:
        if not digest or len(digest) > 128:
            raise WorkflowError("invalid checkpoint digest")
        self.get(workflow_id).checkpoints.append(digest)
        if self.store:
            self.store.checkpoint(
                workflow_id, digest, tenant_id=self.tenant_id
            )

    def recover(self, workflow_id: str) -> Workflow:
        workflow = self.get(workflow_id)
        if workflow.state is WorkflowState.RUNNING:
            return self.transition(
                workflow_id,
                WorkflowState.PAUSED,
                actor="recovery",
                reason="interruption recovery",
            )
        return workflow
