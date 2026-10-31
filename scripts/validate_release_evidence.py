#!/usr/bin/env python3
"""Validate the machine-readable ASDS release-gate policy without external dependencies."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "docs" / "release" / "release-gates.json"


def main() -> int:
    data = json.loads(POLICY.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise SystemExit("unsupported release-gates schema_version")

    policy = data.get("policy", {})
    if policy.get("external_gates_must_not_be_marked_complete_without_evidence") is not True:
        raise SystemExit("external-gate safety policy must be enabled")
    if policy.get("repository_ci_is_not_production_certification") is not True:
        raise SystemExit("CI/non-certification policy must be enabled")

    gates = data.get("gates")
    if not isinstance(gates, list) or not gates:
        raise SystemExit("release-gate list is empty")

    required = {"id", "name", "class", "status", "evidence_required"}
    seen: set[str] = set()
    for gate in gates:
        if not required <= gate.keys():
            raise SystemExit(f"incomplete gate record: {gate!r}")
        gate_id = gate["id"]
        if not isinstance(gate_id, str) or not gate_id or gate_id in seen:
            raise SystemExit(f"duplicate/invalid gate id: {gate_id!r}")
        seen.add(gate_id)
        if not isinstance(gate["evidence_required"], list) or not gate["evidence_required"]:
            raise SystemExit(f"missing evidence requirements: {gate_id}")

        if gate["class"] == "external" and gate["status"] == "complete":
            raise SystemExit(
                f"external gate {gate_id!r} cannot be marked complete by repository metadata alone"
            )
        if gate["class"] not in {"repository", "external"}:
            raise SystemExit(f"invalid gate class for {gate_id}: {gate['class']!r}")

    print(f"validated {len(gates)} release gates; external gates remain evidence-gated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
