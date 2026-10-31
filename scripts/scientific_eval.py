"""Deterministic smoke benchmark for repository scientific primitives.

This is a reproducible harness, not evidence of scientific validity or
domain-expert approval.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from artificial_scientist.math_tools.engine import convert_unit, describe_statistics
from artificial_scientist.math_tools.models import StatisticsRequest, UnitConversionRequest

def main() -> int:
    statistics = describe_statistics(
        StatisticsRequest(values=[1, 2, 3, 4], variance_mode="population")
    )
    conversion = convert_unit(
        UnitConversionRequest(value=1, source_unit="meter", target_unit="cm")
    )
    result = {
        "statistics_mean": statistics.mean,
        "statistics_variance": statistics.variance,
        "meter_to_centimeter": conversion.converted_value,
    }
    expected = {
        "statistics_mean": 2.5,
        "statistics_variance": 1.25,
        "meter_to_centimeter": 100.0,
    }
    if result != expected:
        print(json.dumps({"status": "FAIL", "result": result, "expected": expected}))
        return 1
    print(json.dumps({"status": "PASS", "result": result}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
