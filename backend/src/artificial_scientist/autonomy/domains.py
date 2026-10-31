"""Phase 14: evidence-gated multidisciplinary domain registry."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainSpec:
    name: str
    risk_class: str
    tools: tuple[str, ...]
    validation_cases: tuple[str, ...]
    expert_required: bool = True


class DomainRegistry:
    def __init__(self):
        self._domains: dict[str, DomainSpec] = {}

    def register(self, spec: DomainSpec) -> None:
        if not spec.name or not spec.validation_cases or not spec.tools:
            raise ValueError("domain requires tools and validation cases")
        if spec.name in self._domains:
            raise ValueError("domain already registered")
        self._domains[spec.name] = spec

    def get(self, name: str) -> DomainSpec:
        return self._domains[name]

    def authorize(
        self,
        name: str,
        *,
        validation_passed: bool,
        expert_approved: bool,
        physical_action: bool = False,
    ) -> bool:
        spec = self.get(name)
        if not validation_passed:
            return False
        if spec.expert_required and not expert_approved:
            return False
        return not physical_action

    def list(self) -> tuple[DomainSpec, ...]:
        return tuple(self._domains.values())
