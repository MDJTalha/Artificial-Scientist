"""Container entrypoint for the fixed allowlisted laboratory operations."""
from __future__ import annotations

import json
import sys

from artificial_scientist.lab.engine import _execute_step_direct

ALLOWED = {"symbolic", "integrate", "root", "statistics", "unit_convert"}


def main() -> int:
    request = json.load(sys.stdin)
    if not isinstance(request, dict):
        raise ValueError("Sandbox request must be an object.")
    operation = request.get("operation")
    inputs = request.get("inputs")
    if operation not in ALLOWED or not isinstance(inputs, dict):
        raise ValueError("Sandbox request is not an allowed operation.")
    result = _execute_step_direct(operation, inputs)
    json.dump({"ok": True, "result": result}, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
