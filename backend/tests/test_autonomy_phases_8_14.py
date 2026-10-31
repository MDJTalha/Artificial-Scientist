import pytest

from artificial_scientist.autonomy.collaboration import AgentRole, CollaborationEngine
from artificial_scientist.autonomy.domains import DomainRegistry, DomainSpec
from artificial_scientist.autonomy.engine import ScientificAutonomyEngine
from artificial_scientist.autonomy.governance import (
    BenchmarkCase,
    BenchmarkResult,
    Decision,
    GovernanceEngine,
)
from artificial_scientist.autonomy.memory import ResearchMemory
from artificial_scientist.autonomy.verification import IndependentVerifier
from artificial_scientist.autonomy.workflow import WorkflowEngine, WorkflowError, WorkflowState
from artificial_scientist.autonomy.writing import Citation, ScientificWriter, WritingError


def test_workflow_requires_approval():
    engine = WorkflowEngine()
    engine.create("w")
    engine.transition("w", WorkflowState.PLANNED, actor="s", reason="plan")
    engine.transition("w", WorkflowState.AWAITING_APPROVAL, actor="s", reason="gate")
    try:
        engine.transition("w", WorkflowState.RUNNING, actor="s", reason="no approval")
    except WorkflowError:
        pass
    else:
        raise AssertionError("approval bypass")


def test_verifier_and_memory():
    assert IndependentVerifier.compare([1, 2], [1, 2]).passed
    memory = ResearchMemory()
    item = memory.put("claim", {"x": 1}, evidence=("src:1",))
    memory.put("claim", {"x": 2}, evidence=("src:2",))
    assert len(memory.history("claim")) == 2
    assert item.digest


def test_collaboration_conflict():
    collaboration = CollaborationEngine([
        AgentRole("statistician", "stats", 2),
        AgentRole("reviewer", "review", 2),
    ])
    collaboration.delegate("a", "statistician", budget=2)
    collaboration.delegate("b", "reviewer", budget=2)
    collaboration.complete("a", "A")
    collaboration.complete("b", "B")
    assert collaboration.resolve(["a", "b"], "A") == "A"


def test_writing_blocks_unverified_references():
    writer = ScientificWriter()
    try:
        writer.build(
            "T",
            ["C"],
            [Citation("1", "x", "doi:x", False)],
            methods="M",
            limitations="L",
            data_statement="D",
        )
    except WritingError:
        pass
    else:
        raise AssertionError("unverified citation accepted")


def test_governance_blocks_critical_failure():
    governance = GovernanceEngine([
        BenchmarkCase("s", "security", "ok"),
        BenchmarkCase("n", "normal", "ok"),
    ])
    decision = governance.evaluate([
        BenchmarkResult("s", False, "bad"),
        BenchmarkResult("n", True, "ok"),
    ])
    assert decision.decision is Decision.BLOCK


def test_domain_requires_validation_and_expert():
    domains = DomainRegistry()
    domains.register(
        DomainSpec("physics", "high", ("solver",), ("harmonic-oscillator",))
    )
    assert not domains.authorize("physics", validation_passed=True, expert_approved=False)
    assert domains.authorize("physics", validation_passed=True, expert_approved=True)
    assert not domains.authorize(
        "physics", validation_passed=True, expert_approved=True, physical_action=True
    )


def test_end_to_end_autonomy_is_governed():
    engine = ScientificAutonomyEngine([BenchmarkCase("s", "security", "ok")])
    engine.start("w")
    result = engine.run_verified(
        "w",
        [1.0],
        [1.0],
        [BenchmarkResult("s", True, "ok")],
        "approved",
    )
    assert result.workflow_state == "completed"
    assert result.verification_passed
    assert result.governance_decision == "release"


def test_domain_registry_rejects_invalid_definitions():
    domains = DomainRegistry()
    with pytest.raises(ValueError, match="risk class"):
        domains.register(DomainSpec("x", "unknown", ("solver",), ("case",)))

    with pytest.raises(ValueError, match="duplicates"):
        domains.register(DomainSpec("x", "low", ("solver", "solver"), ("case",)))

    with pytest.raises(ValueError, match="non-empty"):
        domains.register(DomainSpec("x", "low", ("",), ("case",)))


def test_domain_registry_normalizes_bounded_definitions():
    domains = DomainRegistry()
    domains.register(DomainSpec(" physics ", "high", (" solver ",), (" case-1 ",)))
    assert domains.get("physics").tools == ("solver",)
    assert domains.get("physics").validation_cases == ("case-1",)
    with pytest.raises(ValueError, match="already registered"):
        domains.register(DomainSpec("physics", "high", ("other",), ("case-2",)))


def test_domain_registry_rejects_normalized_duplicates_and_unbounded_values():
    domains = DomainRegistry()
    with pytest.raises(ValueError, match="duplicates"):
        domains.register(
            DomainSpec("dup", "low", ("solver", " solver "), ("case",))
        )
    with pytest.raises(ValueError, match="too long"):
        domains.register(
            DomainSpec("x", "low", ("s" * 81,), ("case",))
        )
    with pytest.raises(ValueError, match="too long"):
        domains.register(
            DomainSpec("x", "low", ("solver",), ("c" * 161,))
        )
    with pytest.raises(ValueError, match="boolean"):
        domains.register(
            DomainSpec("x", "low", ("solver",), ("case",), expert_required="yes")
        )


def test_critical_domain_always_requires_expert_approval():
    domains = DomainRegistry()
    domains.register(
        DomainSpec(
            "Critical Research",
            "CRITICAL",
            ("solver",),
            ("independent replication",),
            expert_required=False,
        )
    )
    assert not domains.authorize(
        "Critical Research",
        validation_passed=True,
        expert_approved=False,
    )
    assert domains.authorize(
        "Critical Research",
        validation_passed=True,
        expert_approved=True,
    )


def test_domain_registration_is_case_insensitive_for_names():
    domains = DomainRegistry()
    domains.register(DomainSpec("Astrophysics", "low", ("solver",), ("case",)))
    with pytest.raises(ValueError, match="already registered"):
        domains.register(DomainSpec(" astrophysics ", "low", ("solver",), ("case-2",)))
