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
    def __init__(self, store: AutonomyStore | None = None):
        self._workflows: dict[str, Workflow] = {}
        self.store = store

    @staticmethod
    def _hash(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()

    def create(self, workflow_id: str, *, consequential: bool = True) -> Workflow:
        if workflow_id in self._workflows:
            raise WorkflowError("workflow already exists")
        workflow = Workflow(workflow_id=workflow_id, consequential=consequential)
        self._workflows[workflow_id] = workflow
        if self.store:
            self.store.save_workflow(workflow_id, workflow.state.value, consequential, None)
        return workflow

    def get(self, workflow_id: str) -> Workflow:
        try:
            return self._workflows[workflow_id]
        except KeyError as error:
            raise WorkflowError("unknown workflow") from error

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
            self.store.transition(
                workflow_id, old_state.value, to_state.value, actor, reason
            )
        workflow.state = to_state
        workflow.transitions.append(
            Transition(old_state, to_state, now, reason, actor)
        )
        return workflow

    def approve(self, workflow_id: str, token: str, *, actor: str) -> Workflow:
        if not token or len(token) > 256:
            raise WorkflowError("invalid approval token")
        workflow = self.get(workflow_id)
        if WorkflowState.APPROVED not in _ALLOWED[workflow.state]:
            raise WorkflowError("workflow is not awaiting approval")
        old_state = workflow.state
        workflow.approval_token_hash = self._hash(token)
        now = datetime.now(UTC)
        if self.store:
            self.store.transition(
                workflow_id, old_state.value, WorkflowState.APPROVED.value,
                actor, "explicit approval"
            )
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
            self.store.checkpoint(workflow_id, digest)

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
