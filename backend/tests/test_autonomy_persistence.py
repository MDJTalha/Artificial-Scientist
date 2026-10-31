from artificial_scientist.autonomy.store import AutonomyStore
from artificial_scientist.autonomy.workflow import WorkflowEngine, WorkflowError, WorkflowState


def test_workflow_persists_transitions_and_hashes_approval(tmp_path):
    store = AutonomyStore(tmp_path / "autonomy.sqlite3")
    engine = WorkflowEngine(store, tenant_id="tenant-a")
    engine.create("w")
    engine.transition("w", WorkflowState.PLANNED, actor="system", reason="plan")
    engine.transition("w", WorkflowState.AWAITING_APPROVAL, actor="system", reason="gate")
    engine.approve("w", "secret", actor="operator")
    assert store.workflow("w", tenant_id="tenant-a")["state"] == "approved"
    assert store.workflow("w", tenant_id="tenant-a")["approval_token_hash"] != "secret"
    try:
        engine.transition(
            "w", WorkflowState.RUNNING, actor="operator", reason="run", approval_token="wrong"
        )
    except WorkflowError:
        pass
    else:
        raise AssertionError("approval token bypass")
    engine.transition(
        "w", WorkflowState.RUNNING, actor="operator", reason="run", approval_token="secret"
    )
    assert [row["to_state"] for row in store.transitions("w", tenant_id="tenant-a")] == [
        "planned", "awaiting_approval", "approved", "running"
    ]


def test_memory_versions_are_append_only(tmp_path):
    store = AutonomyStore(tmp_path / "memory.sqlite3")
    assert store.memory_put(
        "claim", {"v": 1}, "active", ("source:1",), "a" * 64, None, tenant_id="tenant-a"
    ) == 1
    assert store.memory_put(
        "claim", {"v": 2}, "disputed", ("source:2",), "b" * 64, 1, tenant_id="tenant-a"
    ) == 2
    history = store.memory_history("claim", tenant_id="tenant-a")
    assert [row["version"] for row in history] == [1, 2]
    assert history[1]["supersedes_version"] == 1


def test_research_memory_recovers_after_restart(tmp_path):
    from artificial_scientist.autonomy.memory import ResearchMemory

    database = tmp_path / "memory-recovery.sqlite3"
    first = ResearchMemory(AutonomyStore(database), tenant_id="tenant-a")
    first.put("hypothesis", {"value": "A"}, evidence=("record:1",))
    second = ResearchMemory(AutonomyStore(database), tenant_id="tenant-a")
    assert second.current("hypothesis").value == {"value": "A"}
    assert second.current("hypothesis").version == 1


def test_persistent_workflow_recovers_across_engine_restart(tmp_path):
    from artificial_scientist.autonomy.workflow import WorkflowEngine, WorkflowState

    database = tmp_path / "workflow-recovery.sqlite3"
    first = WorkflowEngine(AutonomyStore(database), tenant_id="tenant-a")
    first.create("recoverable")
    first.transition(
        "recoverable", WorkflowState.PLANNED, actor="system", reason="plan"
    )
    first.transition(
        "recoverable",
        WorkflowState.AWAITING_APPROVAL,
        actor="system",
        reason="gate",
    )
    first.approve("recoverable", "secret", actor="operator")
    first.transition(
        "recoverable",
        WorkflowState.RUNNING,
        actor="operator",
        reason="run",
        approval_token="secret",
    )
    second = WorkflowEngine(AutonomyStore(database), tenant_id="tenant-a")
    assert second.get("recoverable").state is WorkflowState.RUNNING
    second.recover("recoverable")
    assert second.get("recoverable").state is WorkflowState.PAUSED


def test_tenant_isolation_for_persistent_autonomy(tmp_path):
    database = tmp_path / "tenant-isolation.sqlite3"
    store = AutonomyStore(database)
    owner = WorkflowEngine(store, tenant_id="tenant-a")
    owner.create("same-id")
    try:
        WorkflowEngine(store, tenant_id="tenant-b").get("same-id")
    except WorkflowError:
        pass
    else:
        raise AssertionError("cross-tenant workflow read")
