"""Phase 13: repeatable evaluation, adversarial checks, and governance."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Decision(StrEnum):
    BLOCK = "block"
    CONDITIONAL = "conditional"
    RELEASE = "release"


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    category: str
    expected: str
    adversarial: bool = False


@dataclass(frozen=True)
class BenchmarkResult:
    case_id: str
    passed: bool
    observed: str


@dataclass(frozen=True)
class GovernanceDecision:
    decision: Decision
    passed: int
    failed: int
    critical_failures: tuple[str, ...]
    unresolved: tuple[str, ...]


class GovernanceEngine:
    def __init__(self, cases: list[BenchmarkCase]):
        if not cases or len(cases) > 10000:
            raise ValueError("bounded benchmark suite required")
        self.cases = tuple(cases)

    def evaluate(
        self,
        results: list[BenchmarkResult],
        *,
        critical_categories: tuple[str, ...] = ("security", "integrity"),
        unresolved: tuple[str, ...] = (),
    ) -> GovernanceDecision:
        known = {case.case_id: case for case in self.cases}
        failures: list[str] = []
        passed = 0
        result_ids = {result.case_id for result in results}
        for result in results:
            case = known.get(result.case_id)
            if case is None:
                failures.append("unknown:" + result.case_id)
            elif result.passed:
                passed += 1
            elif case.category in critical_categories:
                failures.append(result.case_id)
        missing = [case.case_id for case in self.cases if case.case_id not in result_ids]
        critical = tuple(failures + missing)
        if critical:
            decision = Decision.BLOCK
        elif unresolved:
            decision = Decision.CONDITIONAL
        else:
            decision = Decision.RELEASE
        return GovernanceDecision(
            decision, passed, len(results) - passed, critical, unresolved
        )
