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
    def _validate_items(
        items: tuple[str, ...], *, label: str, maximum: int
    ) -> tuple[str, ...]:
        if not items or any(not isinstance(item, str) or not item.strip() for item in items):
            raise ValueError(f"{label} must contain non-empty strings")
        normalized = tuple(item.strip() for item in items)
        if len(set(normalized)) != len(normalized):
            raise ValueError(f"{label} must not contain duplicates")
        if any(len(item) > maximum for item in normalized):
            raise ValueError(f"{label} entries are too long")
        return normalized

    def register(self, spec: DomainSpec) -> None:
        name = spec.name.strip()
        if not name or len(name) > _MAX_NAME:
            raise ValueError("domain name must be bounded and non-empty")
        risk_class = spec.risk_class.strip().casefold() if isinstance(spec.risk_class, str) else ""
        if risk_class not in _ALLOWED_RISK_CLASSES:
            raise ValueError("unknown domain risk class")
        tools = self._validate_items(spec.tools, label="tools", maximum=_MAX_TOOL)
        validation_cases = self._validate_items(
            spec.validation_cases, label="validation_cases", maximum=_MAX_CASE
        )
        if not isinstance(spec.expert_required, bool):
            raise ValueError("expert_required must be a boolean")
        if any(existing.casefold() == name.casefold() for existing in self._domains):
            raise ValueError("domain already registered")
        normalized = DomainSpec(
            name=name,
            risk_class=risk_class,
            tools=tools,
            validation_cases=validation_cases,
            expert_required=spec.expert_required,
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
        if (spec.expert_required or spec.risk_class == "critical") and not expert_approved:
            return False
        return True

    def list(self) -> tuple[DomainSpec, ...]:
        return tuple(self._domains.values())
