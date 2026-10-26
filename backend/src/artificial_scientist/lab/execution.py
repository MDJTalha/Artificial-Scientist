"""Process-isolated execution helper with an enforceable wall-clock deadline."""

from __future__ import annotations

import math
import multiprocessing
import os
from collections.abc import Callable
from typing import Any

try:
    import resource
except ImportError:  # Windows does not provide POSIX resource limits.
    resource = None  # type: ignore[assignment]


# POSIX worker limits. These are defense-in-depth limits, not a complete sandbox.
_WORKER_CPU_SECONDS = 25
_WORKER_ADDRESS_SPACE_BYTES = 2 * 1024 * 1024 * 1024
_WORKER_FILE_SIZE_BYTES = 8 * 1024 * 1024
_WORKER_OPEN_FILES = 64


class LabExecutionError(ValueError):
    """An isolated lab operation failed or could not be started."""


class LabExecutionTimeout(LabExecutionError):
    """An isolated lab operation exceeded its wall-clock deadline."""


def _stop_process(process: Any) -> None:
    """Stop a worker and escalate to kill if termination does not finish promptly."""
    if not process.is_alive():
        process.join(timeout=0)
        return
    process.terminate()
    process.join(timeout=2)
    if process.is_alive() and hasattr(process, "kill"):
        process.kill()
        process.join(timeout=2)


def _apply_worker_resource_limits() -> None:
    """Apply best-effort POSIX CPU, address-space, file-size, and descriptor limits.

    Windows has no standard-library equivalent for these POSIX rlimits. Callers
    must not interpret their absence as filesystem, network, or syscall isolation.
    """
    if os.name != "posix" or resource is None:
        return

    limits = (
        (resource.RLIMIT_CPU, _WORKER_CPU_SECONDS),
        (resource.RLIMIT_AS, _WORKER_ADDRESS_SPACE_BYTES),
        (resource.RLIMIT_FSIZE, _WORKER_FILE_SIZE_BYTES),
        (resource.RLIMIT_NOFILE, _WORKER_OPEN_FILES),
    )
    if hasattr(resource, "RLIMIT_CORE"):
        limits += ((resource.RLIMIT_CORE, 0),)
    for limit, maximum in limits:
        _, hard = resource.getrlimit(limit)
        bounded_hard = maximum if hard == resource.RLIM_INFINITY else min(hard, maximum)
        resource.setrlimit(limit, (min(maximum, bounded_hard), bounded_hard))


def _worker_entry(
    send_connection: Any,
    target: Callable[..., dict[str, Any]],
    args: tuple[Any, ...],
) -> None:
    """Run one trusted, allowlisted operation and return a serializable result."""
    try:
        _apply_worker_resource_limits()
        send_connection.send({"ok": True, "result": target(*args)})
    except Exception as error:
        try:
            send_connection.send(
                {
                    "ok": False,
                    "error_type": type(error).__name__,
                    "error": str(error).replace("\\n", " ")[:500],
                }
            )
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        send_connection.close()


def run_isolated(
    target: Callable[..., dict[str, Any]],
    args: tuple[Any, ...],
    timeout_seconds: float,
) -> dict[str, Any]:
    """Execute a trusted callable in a child process and terminate it on timeout.

    POSIX workers receive CPU, address-space, file-size, descriptor, and core-dump
    limits. These controls are not a complete OS security sandbox: they do not
    isolate filesystems, network access, syscalls, or kernel attack surface.
    """
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise LabExecutionError("Lab step timeout must be a finite positive number.")

    context = multiprocessing.get_context("spawn")
    receive_connection, send_connection = context.Pipe(duplex=False)
    process = context.Process(
        target=_worker_entry,
        args=(send_connection, target, args),
        daemon=True,
    )
    try:
        process.start()
    except Exception as error:
        receive_connection.close()
        send_connection.close()
        raise LabExecutionError("Could not start the isolated lab worker.") from error
    send_connection.close()
    try:
        if not receive_connection.poll(timeout_seconds):
            _stop_process(process)
            raise LabExecutionTimeout(
                f"Lab step exceeded its {timeout_seconds:g}-second execution deadline."
            )
        try:
            message = receive_connection.recv()
        except (EOFError, OSError) as error:
            raise LabExecutionError("Isolated lab worker exited without a result.") from error
        process.join(timeout=2)
        if process.is_alive():
            _stop_process(process)
        if not message.get("ok"):
            error_type = str(message.get("error_type", "WorkerError"))[:80]
            error = str(message.get("error", "Isolated operation failed."))[:500]
            raise LabExecutionError(f"{error_type}: {error}")
        result = message.get("result")
        if not isinstance(result, dict):
            raise LabExecutionError("Isolated lab worker returned an invalid result.")
        return result
    finally:
        receive_connection.close()
        if process.is_alive():
            _stop_process(process)
        if not process.is_alive():
            process.close()
