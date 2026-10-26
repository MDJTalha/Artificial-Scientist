"""Safe declarative runner for bounded, allowlisted mathematical operations."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

from artificial_scientist.lab.execution import run_isolated
from artificial_scientist.lab.integrity import result_digest
from artificial_scientist.lab.models import LabRunRequest, LabRunResponse, LabStepResult
from artificial_scientist.math_tools.engine import (
    MathToolError,
    convert_unit,
    describe_statistics,
    find_root,
    integrate_numerically,
    run_symbolic,
)
from artificial_scientist.math_tools.models import (
    NumericIntegrationRequest,
    RootRequest,
    StatisticsRequest,
    SymbolicRequest,
    UnitConversionRequest,
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _execute_step_direct(operation: str, inputs: dict[str, object]) -> dict[str, object]:
    """Validate inputs through the same strict contracts used by the public math API."""
    dispatch = {
        "symbolic": (SymbolicRequest, run_symbolic),
        "integrate": (NumericIntegrationRequest, integrate_numerically),
        "root": (RootRequest, find_root),
        "statistics": (StatisticsRequest, describe_statistics),
        "unit_convert": (UnitConversionRequest, convert_unit),
    }
    model, function = dispatch[operation]
    request = model.model_validate(inputs)
    response = function(request)
    return response.model_dump(mode="json")


def _execute_step(
    operation: str, inputs: dict[str, object], timeout_seconds: float
) -> dict[str, object]:
    """Run one allowlisted math operation in a killable child process."""
    return run_isolated(_execute_step_direct, (operation, inputs), timeout_seconds)


def run_lab(request: LabRunRequest) -> LabRunResponse:
    """Run a bounded sequence; a failed step stops all later steps."""
    started = datetime.now(UTC)
    start_clock = time.perf_counter()
    configuration = request.model_dump(mode="json")
    configuration_hash = hashlib.sha256(
        _canonical_json(configuration).encode("utf-8")
    ).hexdigest()
    run_id = uuid4()
    logs = [f"run={run_id} accepted_steps={len(request.steps)}"]
    results: list[LabStepResult] = []
    failed = False

    for step in request.steps:
        step_start = time.perf_counter()
        if failed:
            results.append(
                LabStepResult(
                    step_id=step.step_id,
                    operation=step.operation,
                    status="skipped",
                    error="Skipped because an earlier step failed.",
                    duration_ms=0,
                )
            )
            continue
        try:
            output = _execute_step(step.operation, step.inputs, request.step_timeout_seconds)
            results.append(
                LabStepResult(
                    step_id=step.step_id,
                    operation=step.operation,
                    status="completed",
                    output=output,
                    duration_ms=max(0.0, (time.perf_counter() - step_start) * 1000),
                )
            )
            logs.append(f"step={step.step_id} status=completed operation={step.operation}")
        except (
            ValidationError,
            MathToolError,
            ArithmeticError,
            RecursionError,
            TypeError,
            ValueError,
        ) as error:
            failed = True
            message = str(error).replace("\n", " ")[:500] or "Invalid operation inputs."
            results.append(
                LabStepResult(
                    step_id=step.step_id,
                    operation=step.operation,
                    status="failed",
                    error=message,
                    duration_ms=max(0.0, (time.perf_counter() - step_start) * 1000),
                )
            )
            logs.append(f"step={step.step_id} status=failed operation={step.operation}")

    completed = datetime.now(UTC)
    duration_ms = max(0.0, (time.perf_counter() - start_clock) * 1000)
    logs.append(f"run_status={'failed' if failed else 'completed'} duration_ms={duration_ms:.3f}")
    response = LabRunResponse(
        run_id=run_id,
        title=request.title,
        status="failed" if failed else "completed",
        configuration_sha256=configuration_hash,
        result_sha256="0" * 64,
        started_at=started.isoformat(),
        completed_at=completed.isoformat(),
        duration_ms=duration_ms,
        steps=results,
        logs=logs,
        plan_record_id=request.plan_record_id,
        random_seed=request.random_seed,
    )
    digest = result_digest(response.model_dump(mode="json"))
    return response.model_copy(update={"result_sha256": digest})
