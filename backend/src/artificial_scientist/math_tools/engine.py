"""Bounded symbolic and numerical mathematics, statistics, and dimensional analysis.

Expressions are parsed through a strict Python-AST allowlist. The service never uses
SymPy's string parser or Python eval on user-supplied mathematical text.
"""

from __future__ import annotations

import ast
import math
import operator
import warnings
from collections.abc import Callable
from typing import Any

import numpy as np
import pint
import sympy as sp
from pint.errors import DimensionalityError, PintError
from scipy.integrate import IntegrationWarning, quad
from scipy.optimize import root_scalar

from artificial_scientist.math_tools.models import (
    DimensionCheckRequest,
    DimensionCheckResponse,
    NumericIntegrationRequest,
    NumericIntegrationResponse,
    NumericRequest,
    RootRequest,
    RootResponse,
    StatisticsRequest,
    StatisticsResponse,
    SymbolicRequest,
    SymbolicResponse,
    UnitConversionRequest,
    UnitConversionResponse,
)

MAX_EXPRESSION_NODES = 80
MAX_POWER_ABS = 12
MAX_SYMBOLS = 10
MAX_RESULT_LENGTH = 10_000

SAFE_FUNCTIONS: dict[str, Any] = {
    "abs": sp.Abs,
    "acos": sp.acos,
    "asin": sp.asin,
    "atan": sp.atan,
    "ceil": sp.ceiling,
    "cos": sp.cos,
    "cosh": sp.cosh,
    "exp": sp.exp,
    "floor": sp.floor,
    "log": sp.log,
    "sin": sp.sin,
    "sinh": sp.sinh,
    "sqrt": sp.sqrt,
    "tan": sp.tan,
    "tanh": sp.tanh,
}

BINARY_OPERATORS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# A deliberately bounded vocabulary prevents arbitrary definition parsing while
# covering common SI units, everyday conversions, and frequently used derived units.
UNIT_ALIASES = {
    "1": "dimensionless",
    "dimensionless": "dimensionless",
    "m": "meter",
    "meter": "meter",
    "metre": "meter",
    "km": "kilometer",
    "cm": "centimeter",
    "mm": "millimeter",
    "um": "micrometer",
    "nm": "nanometer",
    "in": "inch",
    "inch": "inch",
    "ft": "foot",
    "mile": "mile",
    "mi": "mile",
    "s": "second",
    "sec": "second",
    "ms": "millisecond",
    "us": "microsecond",
    "min": "minute",
    "h": "hour",
    "hr": "hour",
    "day": "day",
    "kg": "kilogram",
    "g": "gram",
    "mg": "milligram",
    "lb": "pound",
    "K": "kelvin",
    "kelvin": "kelvin",
    "degC": "degree_Celsius",
    "°C": "degree_Celsius",
    "Celsius": "degree_Celsius",
    "degF": "degree_Fahrenheit",
    "°F": "degree_Fahrenheit",
    "Fahrenheit": "degree_Fahrenheit",
    "mol": "mole",
    "mmol": "millimole",
    "A": "ampere",
    "mA": "milliampere",
    "cd": "candela",
    "N": "newton",
    "J": "joule",
    "kJ": "kilojoule",
    "W": "watt",
    "kW": "kilowatt",
    "Pa": "pascal",
    "kPa": "kilopascal",
    "MPa": "megapascal",
    "bar": "bar",
    "L": "liter",
    "l": "liter",
    "mL": "milliliter",
    "Hz": "hertz",
    "kHz": "kilohertz",
    "MHz": "megahertz",
    "rad": "radian",
    "radian": "radian",
    "degree": "degree",
    "deg": "degree",
    "m/s": "meter / second",
    "km/h": "kilometer / hour",
    "mph": "mile / hour",
    "m/s^2": "meter / second ** 2",
    "m/s²": "meter / second ** 2",
    "cm/s": "centimeter / second",
    "kg/m^3": "kilogram / meter ** 3",
    "g/cm^3": "gram / centimeter ** 3",
    "m^2": "meter ** 2",
    "cm^2": "centimeter ** 2",
    "km^2": "kilometer ** 2",
    "m^3": "meter ** 3",
    "cm^3": "centimeter ** 3",
    "N*m": "newton * meter",
    "N·m": "newton * meter",
    "J/kg": "joule / kilogram",
    "W/m^2": "watt / meter ** 2",
}
UNIT_REGISTRY = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)


class MathToolError(ValueError):
    """A bounded, user-correctable mathematical computation error."""


def _literal_number(node: ast.AST) -> float | int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        if isinstance(node.value, bool):
            return None
        if math.isfinite(node.value) and abs(node.value) <= 1e100:
            return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _literal_number(node.operand)
        if value is not None:
            return value if isinstance(node.op, ast.UAdd) else -value
    return None


def _parse_tree(expression: str) -> ast.Expression:
    if len(expression) > 500:
        raise MathToolError("Expression exceeds the 500-character limit.")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, MemoryError) as error:
        raise MathToolError("Expression syntax is invalid.") from error
    if sum(1 for _ in ast.walk(tree)) > MAX_EXPRESSION_NODES:
        raise MathToolError("Expression exceeds the configured complexity limit.")
    return tree


def _parse_symbolic(expression: str, allowed_names: set[str]) -> sp.Expr:
    """Convert an allowlisted AST to SymPy nodes without evaluating Python text."""
    tree = _parse_tree(expression)
    symbols = {name: sp.Symbol(name) for name in allowed_names}
    constants = {"pi": sp.pi, "E": sp.E}
    sympy_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
    }

    def build(node: ast.AST) -> sp.Expr:
        if isinstance(node, ast.Expression):
            return build(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise MathToolError("Only finite numeric literals are allowed.")
            if not math.isfinite(node.value) or abs(node.value) > 1e100:
                raise MathToolError("Numeric literals must be finite and bounded.")
            if isinstance(node.value, int):
                return sp.Integer(node.value)
            return sp.Float(node.value)
        if isinstance(node, ast.Name):
            if node.id in constants:
                return constants[node.id]
            if node.id not in symbols:
                raise MathToolError(f"Symbol '{node.id}' was not declared.")
            return symbols[node.id]
        if isinstance(node, ast.UnaryOp):
            operation = UNARY_OPERATORS.get(type(node.op))
            if operation is None:
                raise MathToolError("Only unary plus and minus are supported.")
            return operation(build(node.operand))
        if isinstance(node, ast.BinOp):
            operation = sympy_operators.get(type(node.op))
            if operation is None:
                raise MathToolError("This arithmetic operator is not supported.")
            if isinstance(node.op, ast.Pow):
                exponent = _literal_number(node.right)
                if exponent is None or abs(exponent) > MAX_POWER_ABS:
                    raise MathToolError(
                        f"Exponents must be numeric constants between "
                        f"-{MAX_POWER_ABS} and {MAX_POWER_ABS}."
                    )
            return operation(build(node.left), build(node.right))
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in SAFE_FUNCTIONS:
                raise MathToolError("Only allowlisted single-variable math functions are supported.")
            if node.keywords or len(node.args) != 1:
                raise MathToolError("Math functions require exactly one positional argument.")
            return SAFE_FUNCTIONS[node.func.id](build(node.args[0]))
        raise MathToolError(f"Expression component '{type(node).__name__}' is not supported.")

    try:
        return build(tree)
    except MathToolError:
        raise
    except (ArithmeticError, TypeError, ValueError, sp.SympifyError) as error:
        raise MathToolError("Expression could not be interpreted safely.") from error


def _bounded_result(value: Any) -> str:
    rendered = str(value)
    if len(rendered) > MAX_RESULT_LENGTH:
        raise MathToolError("The result is too large to return; simplify the expression.")
    return rendered


def _free_symbols(value: sp.Expr) -> list[str]:
    return sorted(str(symbol) for symbol in value.free_symbols)


def run_symbolic(request: SymbolicRequest) -> SymbolicResponse:
    """Run a bounded symbolic operation on an expression parsed from a safe AST."""
    allowed_names = set(request.symbols) | set(request.substitutions)
    if request.variable:
        allowed_names.add(request.variable)
    if len(allowed_names) > MAX_SYMBOLS:
        raise MathToolError(f"At most {MAX_SYMBOLS} distinct symbols are supported.")
    expression = _parse_symbolic(request.expression, allowed_names)
    variable = sp.Symbol(request.variable) if request.variable else None

    if request.operation == "simplify":
        result = sp.simplify(expression)
        return SymbolicResponse(
            operation=request.operation,
            expression=request.expression,
            result=_bounded_result(result),
            free_symbols=_free_symbols(result),
            method="SymPy simplify",
        )
    if request.operation == "differentiate":
        assert variable is not None
        result = sp.diff(expression, variable)
        return SymbolicResponse(
            operation=request.operation,
            expression=request.expression,
            result=_bounded_result(result),
            free_symbols=_free_symbols(result),
            method="SymPy symbolic differentiation",
        )
    if request.operation == "integrate":
        assert variable is not None
        result = sp.integrate(expression, variable)
        return SymbolicResponse(
            operation=request.operation,
            expression=request.expression,
            result=_bounded_result(result),
            free_symbols=_free_symbols(result),
            method="SymPy indefinite symbolic integration",
        )
    if request.operation == "solve":
        assert variable is not None
        results = sp.solve(expression, variable, check=True)
        rendered = [_bounded_result(item) for item in results[:100]]
        if len(results) > 100:
            raise MathToolError("The equation produced more than 100 solutions.")
        return SymbolicResponse(
            operation=request.operation,
            expression=request.expression,
            result="Solutions for expression = 0",
            results=rendered,
            free_symbols=sorted({symbol for item in results for symbol in _free_symbols(item)}),
            method="SymPy equation solving",
        )

    if request.operation in {"substitute", "evaluate"}:
        if not request.substitutions:
            raise MathToolError(f"{request.operation} requires at least one substitution.")
        symbol_substitutions = {
            sp.Symbol(name): sp.Float(value, 17)
            for name, value in request.substitutions.items()
        }
        result = expression.subs(symbol_substitutions)
        if request.operation == "substitute":
            return SymbolicResponse(
                operation=request.operation,
                expression=request.expression,
                result=_bounded_result(result),
                free_symbols=_free_symbols(result),
                method="SymPy exact-structure substitution",
            )
        if result.free_symbols:
            raise MathToolError(
                "Numeric evaluation requires substitutions for every remaining symbol."
            )
        try:
            numeric = complex(sp.N(result, 18))
        except (ArithmeticError, TypeError, ValueError, OverflowError) as error:
            raise MathToolError("Expression did not evaluate to a finite real number.") from error
        if not math.isfinite(numeric.real) or not math.isfinite(numeric.imag):
            raise MathToolError("Expression did not evaluate to a finite real number.")
        if abs(numeric.imag) > 1e-12:
            raise MathToolError("Complex-valued results are not supported by this endpoint.")
        return SymbolicResponse(
            operation=request.operation,
            expression=request.expression,
            result=_bounded_result(sp.N(result, 18)),
            free_symbols=[],
            numeric_value=float(numeric.real),
            method="SymPy numerical evaluation after substitution",
        )
    raise MathToolError("Unsupported symbolic operation.")


def _compiled_real_function(
    expression: str,
    variable: str,
    parameters: dict[str, float],
) -> Callable[[float], float]:
    """Compile a restricted expression into a real scalar function."""
    allowed = {variable, *parameters}
    parsed = _parse_symbolic(expression, allowed)
    ordered_names = sorted(allowed)
    symbols = [sp.Symbol(name) for name in ordered_names]
    try:
        compiled = sp.lambdify(
            symbols,
            parsed,
            modules=["math"],
            cse=True,
            docstring_limit=0,
        )
    except (TypeError, ValueError, SyntaxError) as error:
        raise MathToolError("Expression could not be compiled for numeric computation.") from error

    def evaluate(value: float) -> float:
        substitutions = {variable: value, **parameters}
        try:
            result = compiled(*(substitutions[name] for name in ordered_names))
            if isinstance(result, complex):
                if abs(result.imag) > 1e-12:
                    raise MathToolError("The expression became complex inside the numeric domain.")
                result = result.real
            numeric = float(result)
        except MathToolError:
            raise
        except (ArithmeticError, TypeError, ValueError, OverflowError) as error:
            raise MathToolError(
                "Expression is undefined or numerically unstable at an evaluated point."
            ) from error
        if not math.isfinite(numeric):
            raise MathToolError("Expression returned a non-finite numeric result.")
        return numeric

    return evaluate


def integrate_numerically(
    request: NumericIntegrationRequest,
) -> NumericIntegrationResponse:
    function = _compiled_real_function(request.expression, request.variable, request.parameters)
    captured_warnings: list[warnings.WarningMessage] = []
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always", IntegrationWarning)
            output = quad(
                function,
                request.lower,
                request.upper,
                epsabs=request.absolute_tolerance,
                epsrel=request.relative_tolerance,
                limit=100,
                full_output=1,
            )
            captured_warnings = list(captured)
        value, estimated_error, details = output[:3]
        not_converged = len(output) > 3 or any(
            issubclass(item.category, IntegrationWarning) for item in captured_warnings
        )
        if not math.isfinite(value) or not math.isfinite(estimated_error):
            raise MathToolError("The integral did not produce finite value and error estimates.")
        return NumericIntegrationResponse(
            value=float(value),
            estimated_absolute_error=float(abs(estimated_error)),
            evaluations=int(details.get("neval", 1)),
            converged=not not_converged,
            warning=(
                "The integration algorithm reported a convergence warning; "
                "review the interval, integrand, and error estimate."
                if not_converged
                else None
            ),
            tolerance={
                "absolute": request.absolute_tolerance,
                "relative": request.relative_tolerance,
            },
        )
    except MathToolError:
        raise
    except (ArithmeticError, TypeError, ValueError, OverflowError) as error:
        raise MathToolError("Numerical integration failed on this interval.") from error


def find_root(request: RootRequest) -> RootResponse:
    function = _compiled_real_function(request.expression, request.variable, request.parameters)
    try:
        lower_value = function(request.lower)
        upper_value = function(request.upper)
        if lower_value == 0:
            root = request.lower
            return RootResponse(
                root=root,
                function_value=0.0,
                converged=True,
                iterations=0,
                function_calls=2,
                bracket=(request.lower, request.upper),
            )
        if upper_value == 0:
            root = request.upper
            return RootResponse(
                root=root,
                function_value=0.0,
                converged=True,
                iterations=0,
                function_calls=2,
                bracket=(request.lower, request.upper),
            )
        if (lower_value > 0) == (upper_value > 0):
            raise MathToolError(
                "The bracket endpoints must have opposite signs or include an endpoint root."
            )
        result = root_scalar(
            function,
            bracket=(request.lower, request.upper),
            method="brentq",
            xtol=request.tolerance,
            maxiter=request.max_iterations,
        )
        root = float(result.root)
        function_value = function(root)
        if not math.isfinite(root) or not math.isfinite(function_value):
            raise MathToolError("The root solver produced a non-finite result.")
        return RootResponse(
            root=root,
            function_value=function_value,
            converged=bool(result.converged),
            iterations=int(result.iterations or 0),
            function_calls=int(result.function_calls or 1),
            bracket=(request.lower, request.upper),
        )
    except MathToolError:
        raise
    except (ArithmeticError, TypeError, ValueError, OverflowError) as error:
        raise MathToolError("The root solver failed on the supplied bracket.") from error


def describe_statistics(request: StatisticsRequest) -> StatisticsResponse:
    array = np.asarray(request.values, dtype=np.float64)
    ddof = 1 if request.variance_mode == "sample" else 0
    try:
        mean = float(np.mean(array))
        median = float(np.median(array))
        variance = float(np.var(array, ddof=ddof))
        standard_deviation = float(np.std(array, ddof=ddof))
        quartiles_raw = np.quantile(array, [0.25, 0.5, 0.75], method="linear")
    except (ArithmeticError, TypeError, ValueError, FloatingPointError) as error:
        raise MathToolError("Descriptive statistics failed for the supplied data.") from error
    scalars = [mean, median, variance, standard_deviation, *quartiles_raw.tolist()]
    if not all(math.isfinite(value) for value in scalars):
        raise MathToolError("Statistics returned non-finite results; review the input scale.")
    return StatisticsResponse(
        count=int(array.size),
        mean=mean,
        median=median,
        variance=max(0.0, variance),
        standard_deviation=max(0.0, standard_deviation),
        minimum=float(np.min(array)),
        maximum=float(np.max(array)),
        quartiles={
            "q1": float(quartiles_raw[0]),
            "q2": float(quartiles_raw[1]),
            "q3": float(quartiles_raw[2]),
        },
        variance_mode=request.variance_mode,
    )


def _normalize_unit(unit: str) -> str:
    normalized = UNIT_ALIASES.get(unit.strip())
    if normalized is None:
        raise MathToolError(
            f"Unit '{unit}' is not in the supported unit list. "
            "Use GET /api/v1/math/units to view supported labels."
        )
    try:
        UNIT_REGISTRY.Unit(normalized)
    except (PintError, ValueError) as error:
        raise MathToolError("The selected unit is not available in the unit registry.") from error
    return normalized


def convert_unit(request: UnitConversionRequest) -> UnitConversionResponse:
    source_unit = _normalize_unit(request.source_unit)
    target_unit = _normalize_unit(request.target_unit)
    try:
        quantity = request.value * UNIT_REGISTRY.Unit(source_unit)
        converted = quantity.to(target_unit)
        numeric_value = float(converted.magnitude)
    except DimensionalityError as error:
        raise MathToolError("Source and target units have incompatible dimensions.") from error
    except (PintError, ArithmeticError, TypeError, ValueError, OverflowError) as error:
        raise MathToolError("Unit conversion failed for the supplied value.") from error
    if not math.isfinite(numeric_value):
        raise MathToolError("Unit conversion produced a non-finite value.")
    return UnitConversionResponse(
        input_value=request.value,
        input_unit=request.source_unit,
        converted_value=numeric_value,
        target_unit=request.target_unit,
        dimensionality=str(quantity.dimensionality),
    )


def _evaluate_quantity_ast(
    node: ast.AST,
    bindings: dict[str, Any],
) -> Any:
    if isinstance(node, ast.Expression):
        return _evaluate_quantity_ast(node.body, bindings)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise MathToolError("Only finite numeric constants are supported in unit expressions.")
        if not math.isfinite(node.value) or abs(node.value) > 1e100:
            raise MathToolError("Unit-expression constants must be finite and bounded.")
        return node.value
    if isinstance(node, ast.Name):
        if node.id in {"pi", "E"}:
            return math.pi if node.id == "pi" else math.e
        if node.id not in bindings:
            raise MathToolError(f"Quantity '{node.id}' was not provided.")
        return bindings[node.id]
    if isinstance(node, ast.UnaryOp):
        operation = UNARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise MathToolError("Only unary plus and minus are supported.")
        return operation(_evaluate_quantity_ast(node.operand, bindings))
    if isinstance(node, ast.BinOp):
        operation = BINARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise MathToolError("This arithmetic operator is not supported in unit expressions.")
        if isinstance(node.op, ast.Pow):
            exponent = _literal_number(node.right)
            if exponent is None or abs(exponent) > MAX_POWER_ABS:
                raise MathToolError("Quantity powers must be small numeric constants.")
        left = _evaluate_quantity_ast(node.left, bindings)
        right = _evaluate_quantity_ast(node.right, bindings)
        return operation(left, right)
    raise MathToolError("Unit expressions allow arithmetic only; function calls are not supported.")


def check_dimensions(request: DimensionCheckRequest) -> DimensionCheckResponse:
    expected_unit = _normalize_unit(request.expected_unit)
    bindings: dict[str, Any] = {}
    for name, item in request.variables.items():
        unit = _normalize_unit(item.unit)
        bindings[name] = item.value * UNIT_REGISTRY.Unit(unit)
    try:
        tree = _parse_tree(request.expression)
        if any(isinstance(node, ast.Call) for node in ast.walk(tree)):
            raise MathToolError("Unit expressions allow arithmetic only; function calls are not supported.")
        result = _evaluate_quantity_ast(tree, bindings)
    except DimensionalityError:
        return DimensionCheckResponse(
            expression=request.expression,
            expression_valid=False,
            matches_expected_unit=False,
            expected_unit=request.expected_unit,
            message="The expression combines quantities with incompatible dimensions.",
        )
    except MathToolError:
        raise
    except (PintError, ArithmeticError, TypeError, ValueError, OverflowError) as error:
        raise MathToolError("Dimensional analysis could not evaluate the expression.") from error

    if not isinstance(result, pint.Quantity):
        result = result * UNIT_REGISTRY.dimensionless
    actual_unit = str(result.units)
    dimensionality = str(result.dimensionality)
    try:
        converted = float(result.to(expected_unit).magnitude)
    except DimensionalityError:
        return DimensionCheckResponse(
            expression=request.expression,
            expression_valid=True,
            matches_expected_unit=False,
            actual_unit=actual_unit,
            actual_dimensionality=dimensionality,
            expected_unit=request.expected_unit,
            message=(
                f"The expression has dimensionality {dimensionality}, which is "
                f"incompatible with the expected unit '{request.expected_unit}'."
            ),
        )
    except (PintError, ArithmeticError, TypeError, ValueError, OverflowError) as error:
        raise MathToolError("Dimensional consistency check could not be completed.") from error
    if not math.isfinite(converted):
        raise MathToolError("Dimensional check produced a non-finite value.")
    return DimensionCheckResponse(
        expression=request.expression,
        expression_valid=True,
        matches_expected_unit=True,
        actual_unit=actual_unit,
        actual_dimensionality=dimensionality,
        expected_unit=request.expected_unit,
        converted_value=converted,
        message=f"Expression dimensionality is compatible with '{request.expected_unit}'.",
    )


def list_supported_units() -> list[dict[str, str]]:
    """Return a stable, UI-friendly view of explicitly allowlisted unit tokens."""
    return [
        {"label": alias, "normalized": normalized}
        for alias, normalized in sorted(UNIT_ALIASES.items())
    ]
