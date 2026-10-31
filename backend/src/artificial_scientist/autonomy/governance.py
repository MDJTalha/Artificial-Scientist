"""Phase 13: repeatable evaluation, adversarial checks, and release governance."""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
class Decision(StrEnum): BLOCK="block"; CONDITIONAL="conditional"; RELEASE="release"
@dataclass(frozen=True)
class BenchmarkCase:
    case_id:str; category:str; expected:str; adversarial:bool=False
@dataclass(frozen=True)
class BenchmarkResult:
    case_id:str; passed:bool; observed:str
@dataclass(frozen=True)
class GovernanceDecision:
    decision:Decision; passed:int; failed:int; critical_failures:tuple[str,...]; unresolved:tuple[str,...]
class GovernanceEngine:
    def __init__(self,cases:list[BenchmarkCase]):
        if not cases or len(cases)>10000: raise ValueError("bounded benchmark suite required")
        self.cases=tuple(cases)
    def evaluate(self,results:list[BenchmarkResult],*,critical_categories:tuple[str,...]=("security","integrity"),unresolved:tuple[str,...]=())->GovernanceDecision:
        by_id={c.case_id:c for c in self.cases}; failures=[]; passed=0
        for r in results:
            c=by_id.get(r.case_id)
            if c is None: failures.append("unknown:"+r.case_id); continue
            if r.passed: passed+=1
            elif c.category in critical_categories: failures.append(r.case_id)
        missing=[c.case_id for c in self.cases if c.case_id not in {r.case_id for r in results}]
        critical=tuple(failures+missing)
        decision=Decision.BLOCK if critical else (Decision.CONDITIONAL if unresolved else Decision.RELEASE)
        return GovernanceDecision(decision,passed,len(results)-passed,critical,unresolved)
