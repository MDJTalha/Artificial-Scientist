"""Phase 8: explicit, recoverable scientific workflow orchestration.

The engine is intentionally policy-driven: it stores state transitions and requires
explicit approval tokens for consequential actions. It never executes arbitrary code.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from datetime import UTC, datetime

class WorkflowState(StrEnum):
    DRAFT="draft"; PLANNED="planned"; AWAITING_APPROVAL="awaiting_approval"; APPROVED="approved"
    RUNNING="running"; PAUSED="paused"; VERIFYING="verifying"; COMPLETED="completed"; FAILED="failed"; CANCELLED="cancelled"

class WorkflowError(ValueError): pass

_ALLOWED={
 WorkflowState.DRAFT:{WorkflowState.PLANNED,WorkflowState.CANCELLED},
 WorkflowState.PLANNED:{WorkflowState.AWAITING_APPROVAL,WorkflowState.FAILED,WorkflowState.CANCELLED},
 WorkflowState.AWAITING_APPROVAL:{WorkflowState.APPROVED,WorkflowState.CANCELLED},
 WorkflowState.APPROVED:{WorkflowState.RUNNING,WorkflowState.CANCELLED},
 WorkflowState.RUNNING:{WorkflowState.PAUSED,WorkflowState.VERIFYING,WorkflowState.FAILED,WorkflowState.CANCELLED},
 WorkflowState.PAUSED:{WorkflowState.RUNNING,WorkflowState.CANCELLED},
 WorkflowState.VERIFYING:{WorkflowState.COMPLETED,WorkflowState.FAILED,WorkflowState.PAUSED},
 WorkflowState.FAILED:{WorkflowState.AWAITING_APPROVAL,WorkflowState.CANCELLED},
 WorkflowState.COMPLETED:set(), WorkflowState.CANCELLED:set(),
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
    state: WorkflowState=WorkflowState.DRAFT
    consequential: bool=True
    approval_token: str|None=None
    transitions: list[Transition]=field(default_factory=list)
    checkpoints: list[str]=field(default_factory=list)
class WorkflowEngine:
    def __init__(self): self._workflows: dict[str,Workflow]={}
    def create(self, workflow_id:str, *, consequential:bool=True)->Workflow:
        if workflow_id in self._workflows: raise WorkflowError("workflow already exists")
        w=Workflow(workflow_id=workflow_id,consequential=consequential); self._workflows[workflow_id]=w; return w
    def get(self, workflow_id:str)->Workflow:
        try:return self._workflows[workflow_id]
        except KeyError as e: raise WorkflowError("unknown workflow") from e
    def transition(self, workflow_id:str, to_state:WorkflowState, *, actor:str, reason:str, approval_token:str|None=None)->Workflow:
        w=self.get(workflow_id)
        if to_state not in _ALLOWED[w.state]: raise WorkflowError(f"invalid transition {w.state}->{to_state}")
        if to_state is WorkflowState.RUNNING and w.consequential and not (w.approval_token and approval_token==w.approval_token):
            raise WorkflowError("consequential workflow requires valid approval")
        old=w.state; w.state=to_state
        w.transitions.append(Transition(old,to_state,datetime.now(UTC),reason,actor)); return w
    def approve(self, workflow_id:str, token:str, *, actor:str)->Workflow:
        if not token or len(token)>256: raise WorkflowError("invalid approval token")
        w=self.get(workflow_id); w.approval_token=token
        return self.transition(workflow_id,WorkflowState.APPROVED,actor=actor,reason="explicit approval")
    def checkpoint(self, workflow_id:str, digest:str)->None:
        if not digest or len(digest)>128: raise WorkflowError("invalid checkpoint digest")
        self.get(workflow_id).checkpoints.append(digest)
    def recover(self, workflow_id:str)->Workflow:
        w=self.get(workflow_id)
        if w.state is WorkflowState.RUNNING: w.state=WorkflowState.PAUSED
        return w
