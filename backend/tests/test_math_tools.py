"""Reference-case and adversarial-input tests for the bounded math toolkit."""

from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from artificial_scientist.api.routes.records import get_record_store
from artificial_scientist.main import app
from artificial_scientist.math_tools.engine import (
    MathToolError,
    check_dimensions,
    convert_unit,
    describe_statistics,
    find_root,
    integrate_numerically,
    render_function_plot,
    run_symbolic,
)
from artificial_scientist.math_tools.models import (
    DimensionCheckRequest,
    NumericIntegrationRequest,
    PlotRequest,
    RootRequest,
    StatisticsRequest,
    SymbolicRequest,
    UnitConversionRequest,
)


def test_symbolic_differentiation_matches_reference_expression() -> None:
    result = run_symbolic(
        SymbolicRequest(
            operation="differentiate",
            expression="x**3 + sin(x)",
            symbols=["x"],
            variable="x",
        )
    )
    assert result.result == "3*x**2 + cos(x)"
    assert result.free_symbols == ["x"]


def test_symbolic_simplification_and_exact_solution_reference_cases() -> None:
    simplified = run_symbolic(
        SymbolicRequest(
            operation="simplify",
            expression="(x**2 - 1)/(x - 1)",
            symbols=["x"],
        )
    )
    assert simplified.result == "x + 1"

    solved = run_symbolic(
        SymbolicRequest(
            operation="solve",
            expression="x**2 - 4",
            symbols=["x"],
            variable="x",
        )
    )
    assert set(solved.results) == {"-2", "2"}


def test_symbolic_indefinite_integration_and_substitution() -> None:
    integral = run_symbolic(
        SymbolicRequest(
            operation="integrate",
            expression="3*x**2",
            symbols=["x"],
            variable="x",
        )
    )
    assert integral.result == "x**3"

    substituted = run_symbolic(
        SymbolicRequest(
            operation="substitute",
            expression="x**2 + y",
            symbols=["x", "y"],
            substitutions={"x": 2},
        )
    )
    assert substituted.result == "y + 4"
    assert substituted.free_symbols == ["y"]


def test_symbolic_numeric_evaluation_requires_all_symbols() -> None:
    request = SymbolicRequest(
        operation="evaluate",
        expression="x**2 + 2*x + 1",
        symbols=["x"],
        substitutions={"x": 3},
    )
    result = run_symbolic(request)
    assert result.numeric_value == pytest.approx(16.0)
    assert result.free_symbols == []

    with pytest.raises(MathToolError, match="every remaining symbol"):
        run_symbolic(
            SymbolicRequest(
                operation="evaluate",
                expression="x + y",
                symbols=["x", "y"],
                substitutions={"x": 1},
            )
        )


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('echo unsafe')",
        "x.__class__",
        "x[0]",
        "[x for x in (1, 2)]",
        "open('secret.txt')",
        "x**100",
    ],
)
def test_symbolic_parser_rejects_untrusted_python_and_excessive_powers(
    expression: str,
) -> None:
    with pytest.raises(MathToolError):
        run_symbolic(
            SymbolicRequest(
                operation="simplify",
                expression=expression,
                symbols=["x"],
            )
        )


def test_symbolic_parser_requires_declared_names_and_limits_complexity() -> None:
    with pytest.raises(MathToolError, match="was not declared"):
        run_symbolic(SymbolicRequest(operation="simplify", expression="unknown + 1"))

    with pytest.raises(MathToolError, match="complexity limit"):
        run_symbolic(
            SymbolicRequest(operation="simplify", expression="+".join(["x"] * 50), symbols=["x"])
        )

    with pytest.raises(ValidationError):
        SymbolicRequest(operation="differentiate", expression="x**2", symbols=["x"])


def test_numerical_integration_matches_known_integral_with_error_estimate() -> None:
    result = integrate_numerically(
        NumericIntegrationRequest(
            expression="x**2",
            variable="x",
            lower=0,
            upper=1,
            absolute_tolerance=1e-10,
            relative_tolerance=1e-10,
        )
    )
    assert result.value == pytest.approx(1 / 3, abs=1e-10)
    assert result.estimated_absolute_error >= 0
    assert result.evaluations > 0
    assert result.converged is True
    assert result.warning is None


def test_numerical_integration_supports_parameters_and_reversed_bounds_rejected() -> None:
    result = integrate_numerically(
        NumericIntegrationRequest(
            expression="a*x",
            variable="x",
            parameters={"a": 2},
            lower=0,
            upper=3,
        )
    )
    assert result.value == pytest.approx(9.0)

    with pytest.raises(ValidationError, match="lower must be less"):
        NumericIntegrationRequest(
            expression="x",
            variable="x",
            lower=1,
            upper=0,
        )


def test_numerical_integration_rejects_undeclared_symbols_and_singular_domain() -> None:
    with pytest.raises(MathToolError, match="was not declared"):
        integrate_numerically(
            NumericIntegrationRequest(
                expression="x + missing",
                variable="x",
                lower=0,
                upper=1,
            )
        )

    with pytest.raises(MathToolError):
        integrate_numerically(
            NumericIntegrationRequest(
                expression="1/x",
                variable="x",
                lower=-1,
                upper=1,
            )
        )


def test_numerical_root_finds_square_root_two_with_bracketed_solver() -> None:
    result = find_root(
        RootRequest(
            expression="x**2 - 2",
            variable="x",
            lower=1,
            upper=2,
        )
    )
    assert result.converged is True
    assert result.root == pytest.approx(math.sqrt(2), abs=1e-9)
    assert abs(result.function_value) < 1e-8
    assert result.function_calls > 0


def test_numerical_root_requires_valid_bracket_and_handles_endpoint_root() -> None:
    with pytest.raises(MathToolError, match="opposite signs"):
        find_root(
            RootRequest(
                expression="x**2 + 1",
                variable="x",
                lower=1,
                upper=2,
            )
        )

    endpoint = find_root(
        RootRequest(expression="x", variable="x", lower=0, upper=1)
    )
    assert endpoint.root == 0
    assert endpoint.converged is True


@pytest.mark.parametrize(
    ("mode", "expected_variance"),
    [("sample", 5 / 3), ("population", 1.25)],
)
def test_descriptive_statistics_match_reference_values(
    mode: str, expected_variance: float
) -> None:
    result = describe_statistics(
        StatisticsRequest(values=[1, 2, 3, 4], variance_mode=mode)
    )
    assert result.count == 4
    assert result.mean == pytest.approx(2.5)
    assert result.median == pytest.approx(2.5)
    assert result.variance == pytest.approx(expected_variance)
    assert result.standard_deviation == pytest.approx(math.sqrt(expected_variance))
    assert result.minimum == 1
    assert result.maximum == 4
    assert result.quartiles == {"q1": 1.75, "q2": 2.5, "q3": 3.25}


def test_statistics_reject_nonfinite_and_oversized_input() -> None:
    with pytest.raises(ValidationError):
        StatisticsRequest(values=[1, math.nan])
    with pytest.raises(ValidationError):
        StatisticsRequest(values=[1])
    with pytest.raises(ValidationError):
        StatisticsRequest(values=[1] * 100_001)


def test_function_plot_renders_a_bounded_png_without_writing_files() -> None:
    image = render_function_plot(
        PlotRequest(
            expression="sin(x)",
            variable="x",
            lower=-math.pi,
            upper=math.pi,
            points=100,
            title="Sine reference",
            x_label="Angle",
            y_label="sin(x)",
        )
    )
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(image) < 2 * 1024 * 1024


def test_function_plot_rejects_non_finite_domain_and_excessive_point_count() -> None:
    with pytest.raises(MathToolError, match="undefined or numerically unstable"):
        render_function_plot(
            PlotRequest(
                expression="sqrt(x)",
                variable="x",
                lower=-1,
                upper=1,
                points=50,
            )
        )
    with pytest.raises(ValidationError):
        PlotRequest(expression="x", variable="x", lower=0, upper=1, points=5000)


def test_unit_conversion_matches_length_and_temperature_reference_cases() -> None:
    length = convert_unit(
        UnitConversionRequest(value=1000, source_unit="m", target_unit="km")
    )
    assert length.converted_value == pytest.approx(1.0)
    assert "length" in length.dimensionality

    temperature = convert_unit(
        UnitConversionRequest(value=0, source_unit="°C", target_unit="°F")
    )
    assert temperature.converted_value == pytest.approx(32.0, abs=1e-9)


def test_unit_conversion_rejects_incompatible_or_unlisted_units() -> None:
    with pytest.raises(MathToolError, match="incompatible dimensions"):
        convert_unit(
            UnitConversionRequest(value=1, source_unit="m", target_unit="s")
        )

    with pytest.raises(MathToolError, match="not in the supported unit list"):
        convert_unit(
            UnitConversionRequest(value=1, source_unit="parsec", target_unit="m")
        )


def test_dimensional_analysis_matches_speed_times_time_to_distance() -> None:
    result = check_dimensions(
        DimensionCheckRequest(
            expression="speed * duration",
            variables={
                "speed": {"value": 3, "unit": "m/s"},
                "duration": {"value": 10, "unit": "s"},
            },
            expected_unit="m",
        )
    )
    assert result.expression_valid is True
    assert result.matches_expected_unit is True
    assert result.converted_value == pytest.approx(30)
    assert "length" in (result.actual_dimensionality or "")


def test_dimensional_analysis_reports_expected_unit_mismatch() -> None:
    result = check_dimensions(
        DimensionCheckRequest(
            expression="speed * duration",
            variables={
                "speed": {"value": 3, "unit": "m/s"},
                "duration": {"value": 10, "unit": "s"},
            },
            expected_unit="kg",
        )
    )
    assert result.expression_valid is True
    assert result.matches_expected_unit is False
    assert result.converted_value is None
    assert result.actual_dimensionality is not None


def test_dimensional_analysis_detects_incompatible_addition() -> None:
    result = check_dimensions(
        DimensionCheckRequest(
            expression="distance + duration",
            variables={
                "distance": {"value": 4, "unit": "m"},
                "duration": {"value": 3, "unit": "s"},
            },
            expected_unit="m",
        )
    )
    assert result.expression_valid is False
    assert result.matches_expected_unit is False
    assert "incompatible dimensions" in result.message


def test_dimensional_analysis_rejects_function_calls_and_undeclared_names() -> None:
    with pytest.raises(MathToolError, match="function calls are not supported"):
        check_dimensions(
            DimensionCheckRequest(
                expression="sqrt(distance)",
                variables={"distance": {"value": 4, "unit": "m"}},
                expected_unit="m",
            )
        )

    with pytest.raises(MathToolError, match="was not provided"):
        check_dimensions(
            DimensionCheckRequest(
                expression="distance * missing",
                variables={"distance": {"value": 4, "unit": "m"}},
                expected_unit="m",
            )
        )


def test_math_api_exposes_symbolic_numerical_statistics_and_units(tmp_path) -> None:
    from artificial_scientist.records.store import RecordStore

    store = RecordStore(tmp_path / "math-api.sqlite3")
    app.dependency_overrides[get_record_store] = lambda: store
    try:
        with TestClient(app) as client:
            symbolic = client.post(
                "/api/v1/math/symbolic",
                json={
                    "operation": "differentiate",
                    "expression": "x**2",
                    "symbols": ["x"],
                    "variable": "x",
                },
            )
            assert symbolic.status_code == 200
            assert symbolic.json()["result"] == "2*x"

            integral = client.post(
                "/api/v1/math/numeric/integrate",
                json={
                    "expression": "x**2",
                    "variable": "x",
                    "lower": 0,
                    "upper": 1,
                },
            )
            assert integral.status_code == 200
            assert integral.json()["value"] == pytest.approx(1 / 3)

            root = client.post(
                "/api/v1/math/numeric/root",
                json={
                    "expression": "x**2 - 2",
                    "variable": "x",
                    "lower": 1,
                    "upper": 2,
                },
            )
            assert root.status_code == 200
            assert root.json()["root"] == pytest.approx(math.sqrt(2))

            stats = client.post(
                "/api/v1/math/statistics",
                json={"values": [1, 2, 3, 4], "variance_mode": "population"},
            )
            assert stats.status_code == 200
            assert stats.json()["variance"] == pytest.approx(1.25)

            plot = client.post(
                "/api/v1/math/plot",
                json={
                    "expression": "sin(x)",
                    "variable": "x",
                    "lower": -math.pi,
                    "upper": math.pi,
                    "points": 100,
                },
            )
            assert plot.status_code == 200
            assert plot.headers["content-type"].startswith("image/png")
            assert plot.content.startswith(b"\x89PNG\r\n\x1a\n")
            assert len(plot.content) < 2 * 1024 * 1024

            units = client.get("/api/v1/math/units")
            assert units.status_code == 200
            assert any(item["label"] == "m/s" for item in units.json()["units"])

            converted = client.post(
                "/api/v1/math/units/convert",
                json={"value": 1000, "source_unit": "m", "target_unit": "km"},
            )
            assert converted.status_code == 200
            assert converted.json()["converted_value"] == pytest.approx(1)

            dimensions = client.post(
                "/api/v1/math/units/check",
                json={
                    "expression": "v * t",
                    "variables": {
                        "v": {"value": 3, "unit": "m/s"},
                        "t": {"value": 10, "unit": "s"},
                    },
                    "expected_unit": "m",
                },
            )
            assert dimensions.status_code == 200
            assert dimensions.json()["matches_expected_unit"] is True

            invalid_expression = client.post(
                "/api/v1/math/symbolic",
                json={
                    "operation": "simplify",
                    "expression": "__import__('os').system('echo unsafe')",
                    "symbols": [],
                },
            )
            assert invalid_expression.status_code == 422

            invalid_unit = client.post(
                "/api/v1/math/units/convert",
                json={"value": 1, "source_unit": "m", "target_unit": "second fake"},
            )
            assert invalid_unit.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_unit_check_api_returns_dimension_mismatch_as_a_check_result(tmp_path) -> None:
    from artificial_scientist.records.store import RecordStore

    store = RecordStore(tmp_path / "math-unit-check.sqlite3")
    app.dependency_overrides[get_record_store] = lambda: store
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/math/units/check",
                json={
                    "expression": "mass * speed",
                    "variables": {
                        "mass": {"value": 2, "unit": "kg"},
                        "speed": {"value": 3, "unit": "m/s"},
                    },
                    "expected_unit": "m",
                },
            )
            assert response.status_code == 200
            body = response.json()
            assert body["expression_valid"] is True
            assert body["matches_expected_unit"] is False
    finally:
        app.dependency_overrides.clear()
