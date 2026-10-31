"""Deployment-neutral execution boundary for the controlled laboratory.

Production deployments fail closed unless a reviewed sandbox adapter is
configured. The Docker adapter below is deliberately restricted to the fixed
allowlisted math worker; it does not execute arbitrary user shell commands.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from artificial_scientist.lab.execution import run_isolated


class ExecutionAdapterUnavailable(RuntimeError):
    """Raised when the configured execution boundary is not available."""


class LabExecutionAdapter(Protocol):
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
class DockerSandboxExecutionAdapter:
    """Execute only the repository's fixed math worker inside Docker isolation."""

    image: str
    name: str = "sandbox:docker"

    def execute(
        self,
        target: Callable[..., dict[str, Any]],
        args: tuple[Any, ...],
        *,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        if target.__name__ != "_execute_step_direct" or target.__module__ != "artificial_scientist.lab.engine":
            raise ExecutionAdapterUnavailable("Docker adapter accepts only the fixed lab worker.")
        if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], dict):
            raise ExecutionAdapterUnavailable("Docker adapter received an invalid operation contract.")
        if not shutil.which("docker"):
            raise ExecutionAdapterUnavailable("Docker executable is unavailable.")
        if not self.image.strip():
            raise ExecutionAdapterUnavailable("Sandbox image is not configured.")

        container_name = f"asds-lab-{uuid.uuid4().hex}"
        command = [
            "docker", "run", "--rm", "--name", container_name,
            "--network", "none",
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "64",
            "--memory", "512m",
            "--cpus", "1.0",
            "--ulimit", "nofile=64:64",
            "--ulimit", "nproc=64:64",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",
            "--user", "65532:65532",
            self.image,
            "python", "-m", "artificial_scientist.lab.sandbox_worker",
        ]
        payload = json.dumps(
            {"operation": args[0], "inputs": args[1]},
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONUNBUFFERED": "1"},
            )
            stdout, stderr = process.communicate(input=payload, timeout=timeout_seconds)
        except subprocess.TimeoutExpired as error:
            if process is not None:
                try:
                    subprocess.run(
                        ["docker", "rm", "-f", container_name],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                    )
                finally:
                    process.kill()
                    process.communicate()
            raise ExecutionAdapterUnavailable(
                f"Docker sandbox exceeded its {timeout_seconds:g}-second deadline."
            ) from error
        except OSError as error:
            raise ExecutionAdapterUnavailable("Could not start the Docker sandbox.") from error
        finally:
            if process is not None and process.poll() is None:
                process.kill()

        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()[:500]
            raise ExecutionAdapterUnavailable(
                f"Docker sandbox failed with exit code {process.returncode}: {detail}"
            )
        try:
            response = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ExecutionAdapterUnavailable("Docker sandbox returned invalid JSON.") from error
        if not isinstance(response, dict) or response.get("ok") is not True:
            raise ExecutionAdapterUnavailable("Docker sandbox returned an invalid result.")
        result = response.get("result")
        if not isinstance(result, dict):
            raise ExecutionAdapterUnavailable("Docker sandbox result is not an object.")
        return result


@dataclass(frozen=True, slots=True)
class ReviewedSandboxExecutionAdapter:
    """Compatibility contract for non-Docker reviewed deployment adapters."""

    name: str

    def execute(
        self,
        target: Callable[..., dict[str, Any]],
        args: tuple[Any, ...],
        *,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        raise ExecutionAdapterUnavailable(
            f"Execution adapter {self.name!r} is declared but has no reviewed sandbox implementation.",
        )


def get_execution_adapter() -> LabExecutionAdapter:
    """Resolve the execution boundary and fail closed outside development."""
    environment = os.getenv("ARTIFICIAL_SCIENTIST_ENV", "production").strip().lower()
    mode = os.getenv("ARTIFICIAL_SCIENTIST_LAB_EXECUTION_MODE", "").strip().lower()

    if environment == "development" and mode in {"", "local-process"}:
        return LocalDevelopmentExecutionAdapter()

    if mode == "sandbox:docker":
        image = os.getenv("ARTIFICIAL_SCIENTIST_LAB_SANDBOX_IMAGE", "").strip()
        if not image:
            raise ExecutionAdapterUnavailable(
                "ARTIFICIAL_SCIENTIST_LAB_SANDBOX_IMAGE is required for sandbox:docker."
            )
        return DockerSandboxExecutionAdapter(image=image)

    if mode.startswith("sandbox:") and len(mode) > len("sandbox:"):
        return ReviewedSandboxExecutionAdapter(name=mode)

    raise ExecutionAdapterUnavailable(
        "No reviewed lab execution sandbox is configured for this environment."
    )
