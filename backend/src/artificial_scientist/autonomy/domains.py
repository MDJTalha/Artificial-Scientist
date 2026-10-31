"""Phase 14: evidence-gated multidisciplinary domain registry."""
from __future__ import annotations

from dataclasses import dataclass

_ALLOWED_RISK_CLASSES = frozenset({"low", "moderate", "high", "critical"})
_MAX_NAME = 80
_MAX_TOOL = 80
_MAX_CASE = 160


@dataclass(frozen=True)
class DomainSpec:
    name: str
    risk_class: str
    tools: tuple[str, ...]
    validation_cases: tuple[str, ...]
    expert_required: bool = True


class DomainRegistry:
    def __init__(self) -> None:
        self._domains: dict[str, DomainSpec] = {}

    @staticmethod
    def _validate_items(items: tuple[str, ...], *, label: str, maximum: int) -> None:
        if not items or any(not isinstance(item, str) or not item.strip() for item in items):
            raise ValueError(f"{label} must contain non-empty strings")
        if len(set(items)) != len(items):
            raise ValueError(f"{label} must not contain duplicates")
        if any(len(item.strip()) > maximum for item in items):
            raise ValueError(f"{label} entries are too long")

    def register(self, spec: DomainSpec) -> None:
        name = spec.name.strip()
        if not name or len(name) > _MAX_NAME:
            raise ValueError("domain name must be bounded and non-empty")
        if spec.risk_class not in _ALLOWED_RISK_CLASSES:
            raise ValueError("unknown domain risk class")
        self._validate_items(spec.tools, label="tools", maximum=_MAX_TOOL)
        self._validate_items(spec.validation_cases, label="validation_cases", maximum=_MAX_CASE)
        if name in self._domains:
            raise ValueError("domain already registered")
        normalized = DomainSpec(
            name=name,
            risk_class=spec.risk_class,
            tools=tuple(tool.strip() for tool in spec.tools),
            validation_cases=tuple(case.strip() for case in spec.validation_cases),
            expert_required=bool(spec.expert_required),
        )
        self._domains[name] = normalized

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
        if physical_action:
            return False
        if not validation_passed:
            return False
        if spec.expert_required and not expert_approved:
            return False
        return True

    def list(self) -> tuple[DomainSpec, ...]:
        return tuple(self._domains.values())
