from artificial_scientist.autonomy.store import AutonomyStore
from artificial_scientist.autonomy.workflow import WorkflowEngine,WorkflowState,WorkflowError

def test_workflow_persists_transitions_and_hashes_approval(tmp_path):
    store=AutonomyStore(tmp_path/"autonomy.sqlite3")
    engine=WorkflowEngine(store); engine.create("w")
    engine.transition("w",WorkflowState.PLANNED,actor="system",reason="plan")
    engine.transition("w",WorkflowState.AWAITING_APPROVAL,actor="system",reason="gate")
    engine.approve("w","secret",actor="operator")
    assert store.workflow("w")["state"]=="approved"
    assert store.workflow("w")["approval_token_hash"] != "secret"
    try: engine.transition("w",WorkflowState.RUNNING,actor="operator",reason="run",approval_token="wrong")
    except WorkflowError: pass
    else: raise AssertionError("approval token bypass")
    engine.transition("w",WorkflowState.RUNNING,actor="operator",reason="run",approval_token="secret")
    assert [x["to_state"] for x in store.transitions("w")]==["planned","awaiting_approval","approved","running"]

def test_memory_versions_are_append_only(tmp_path):
    store=AutonomyStore(tmp_path/"memory.sqlite3")
    assert store.memory_put("claim",{"v":1},"active",("source:1",),"a"*64,None)==1
    assert store.memory_put("claim",{"v":2},"disputed",("source:2",),"b"*64,1)==2
    history=store.memory_history("claim")
    assert [row["version"] for row in history]==[1,2]
    assert history[1]["supersedes_version"]==1
