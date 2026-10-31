"""Cross-phase bounded autonomy coordinator for Phases 8-14."""
from __future__ import annotations

from dataclasses import dataclass

from artificial_scientist.autonomy.governance import (
    BenchmarkCase,
    BenchmarkResult,
    Decision,
    GovernanceEngine,
)
from artificial_scientist.autonomy.verification import IndependentVerifier
from artificial_scientist.autonomy.workflow import WorkflowEngine, WorkflowState


@dataclass(frozen=True)
class AutonomyResult:
    workflow_state: str
    verification_passed: bool
    governance_decision: str


class ScientificAutonomyEngine:
    """Coordinate planning, verification, and governance without bypassing approvals."""

    def __init__(self, governance_cases: list[BenchmarkCase]):
        self.workflow = WorkflowEngine()
        self.verifier = IndependentVerifier()
        self.governance = GovernanceEngine(governance_cases)

    def start(self, workflow_id: str) -> None:
        self.workflow.create(workflow_id, consequential=True)
        self.workflow.transition(
            workflow_id, WorkflowState.PLANNED, actor="system", reason="validated plan"
        )
        self.workflow.transition(
            workflow_id,
            WorkflowState.AWAITING_APPROVAL,
            actor="system",
            reason="consequential gate",
        )

    def run_verified(
        self,
        workflow_id: str,
        observed: list[float],
        expected: list[float],
        results: list[BenchmarkResult],
        approval_token: str,
    ) -> AutonomyResult:
        self.workflow.approve(workflow_id, approval_token, actor="authorized_operator")
        self.workflow.transition(
            workflow_id,
            WorkflowState.RUNNING,
            actor="authorized_operator",
            reason="approved execution",
            approval_token=approval_token,
        )
        verification = self.verifier.compare(observed, expected)
        self.workflow.transition(
            workflow_id,
            WorkflowState.VERIFYING,
            actor="verification",
            reason="independent verification",
        )
        decision = self.governance.evaluate(results)
        target = (
            WorkflowState.COMPLETED
            if verification.passed and decision.decision is not Decision.BLOCK
            else WorkflowState.FAILED
        )
        self.workflow.transition(
            workflow_id, target, actor="governance", reason=decision.decision.value
        )
        return AutonomyResult(
            self.workflow.get(workflow_id).state.value,
            verification.passed,
            decision.decision.value,
        )
