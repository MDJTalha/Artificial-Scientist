from artificial_scientist.autonomy.workflow import WorkflowEngine,WorkflowState,WorkflowError
from artificial_scientist.autonomy.verification import IndependentVerifier
from artificial_scientist.autonomy.memory import ResearchMemory
from artificial_scientist.autonomy.collaboration import CollaborationEngine,AgentRole
from artificial_scientist.autonomy.writing import ScientificWriter,Citation,WritingError
from artificial_scientist.autonomy.governance import GovernanceEngine,BenchmarkCase,BenchmarkResult,Decision
from artificial_scientist.autonomy.domains import DomainRegistry,DomainSpec
from artificial_scientist.autonomy.engine import ScientificAutonomyEngine

def test_workflow_requires_approval():
 e=WorkflowEngine();e.create("w");e.transition("w",WorkflowState.PLANNED,actor="s",reason="plan");e.transition("w",WorkflowState.AWAITING_APPROVAL,actor="s",reason="gate")
 try:e.transition("w",WorkflowState.RUNNING,actor="s",reason="no approval")
 except WorkflowError:pass
 else:raise AssertionError("approval bypass")

def test_verifier_and_memory():
 assert IndependentVerifier.compare([1,2],[1,2]).passed
 m=ResearchMemory();a=m.put("claim",{"x":1},evidence=("src:1",));m.put("claim",{"x":2},evidence=("src:2",));assert len(m.history("claim"))==2;assert a.digest

def test_collaboration_conflict():
 c=CollaborationEngine([AgentRole("statistician","stats",2),AgentRole("reviewer","review",2)])
 c.delegate("a","statistician",budget=2);c.delegate("b","reviewer",budget=2);c.complete("a","A");c.complete("b","B");assert c.resolve(["a","b"],"A")=="A"

def test_writing_blocks_unverified_references():
 w=ScientificWriter()
 try:w.build("T",["C"],[Citation("1","x","doi:x",False)],methods="M",limitations="L",data_statement="D")
 except WritingError:pass
 else:raise AssertionError("unverified citation accepted")

def test_governance_blocks_critical_failure():
 g=GovernanceEngine([BenchmarkCase("s","security","ok"),BenchmarkCase("n","normal","ok")])
 d=g.evaluate([BenchmarkResult("s",False,"bad"),BenchmarkResult("n",True,"ok")]);assert d.decision is Decision.BLOCK

def test_domain_requires_validation_and_expert():
 d=DomainRegistry();d.register(DomainSpec("physics","high",("solver",),("harmonic-oscillator",)))
 assert not d.authorize("physics",validation_passed=True,expert_approved=False)
 assert d.authorize("physics",validation_passed=True,expert_approved=True)
 assert not d.authorize("physics",validation_passed=True,expert_approved=True,physical_action=True)

def test_end_to_end_autonomy_is_governed():
 e=ScientificAutonomyEngine([BenchmarkCase("s","security","ok")]);e.start("w")
 r=e.run_verified("w",[1.0],[1.0],[BenchmarkResult("s",True,"ok")],"approved")
 assert r.workflow_state=="completed" and r.verification_passed and r.governance_decision=="release"
