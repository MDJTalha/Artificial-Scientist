"""Deployment-neutral execution boundary for the controlled laboratory.

The production service deliberately fails closed until a reviewed OS-level
sandbox adapter is configured. The existing local subprocess runner is kept
only for development and trusted allowlisted operations; it is not advertised
or usable as a hostile-code sandbox.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from artificial_scientist.lab.execution import run_isolated


class ExecutionAdapterUnavailable(RuntimeError):
    """Raised when the configured execution boundary is not available."""


class LabExecutionAdapter(Protocol):
    """Interface implemented by a deployment-specific execution boundary."""

    name: str

    def execute(
        self,
        target: Callable[..., dict[str, Any]],
        args: tuple[Any, ...],
        *,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        """Execute one bounded operation inside the adapter boundary."""


@dataclass(frozen=True, slots=True)
class LocalDevelopmentExecutionAdapter:
    """Development-only adapter for the existing trusted allowlist."""

    name: str = "local-process-development"

    def execute(
        self,
        target: Callable[..., dict[str, Any]],
        args: tuple[Any, ...],
        *,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        return run_isolated(target, args, timeout_seconds)


@dataclass(frozen=True, slots=True)
class ReviewedSandboxExecutionAdapter:
    """Contract for a separately deployed reviewed sandbox.

    A production adapter must be implemented by the deployment layer. It must
    enforce OS/orchestrator isolation for filesystem, network, identity,
    syscalls/capabilities and resources before this adapter is considered
    available. Keeping this explicit prevents accidental fallback to the local
    process runner.
    """

    name: str

    def execute(
        self,
        target: Callable[..., dict[str, Any]],
        args: tuple[Any, ...],
        *,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        raise ExecutionAdapterUnavailable(
            f"Execution adapter {self.name!r} is declared but has no reviewed "
            "sandbox implementation.",
        )


def get_execution_adapter() -> LabExecutionAdapter:
    """Resolve the execution boundary and fail closed outside development.

    Local-process execution is intentionally accepted only when the application
    environment is explicitly development. Production-like environments must
    select a reviewed external sandbox adapter; until one is registered, lab
    execution is unavailable rather than silently falling back to a child
    process with inherited host access.
    """

    environment = os.getenv("ARTIFICIAL_SCIENTIST_ENV", "production").strip().lower()
    mode = os.getenv("ARTIFICIAL_SCIENTIST_LAB_EXECUTION_MODE", "").strip().lower()

    if environment == "development" and mode in {"", "local-process"}:
        return LocalDevelopmentExecutionAdapter()

    if mode.startswith("sandbox:") and len(mode) > len("sandbox:"):
        return ReviewedSandboxExecutionAdapter(name=mode)

    raise ExecutionAdapterUnavailable(
        "No reviewed lab execution sandbox is configured for this environment."
    )
