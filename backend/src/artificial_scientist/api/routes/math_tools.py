"""HTTP endpoints for the bounded mathematical and scientific-tools service."""

from typing import Annotated

from fastapi import APIRouter, HTTPException

from artificial_scientist.math_tools.engine import (
    MathToolError,
    check_dimensions,
    convert_unit,
    describe_statistics,
    find_root,
    integrate_numerically,
    list_supported_units,
    run_symbolic,
)
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

router = APIRouter(prefix="/api/v1/math", tags=["mathematics and scientific tools"])


def _translate_math_error(error: MathToolError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(error))


@router.get("/units", summary="List explicitly supported unit tokens")
def get_supported_units() -> dict[str, object]:
    """Return the controlled unit vocabulary accepted by conversion and dimension checks."""
    return {
        "units": list_supported_units(),
        "note": (
            "Only listed unit tokens are accepted. This is a practical initial subset "
            "of common scientific and SI units, not a complete unit ontology."
        ),
    }


@router.post("/symbolic", response_model=SymbolicResponse)
def symbolic_computation(request: SymbolicRequest) -> SymbolicResponse:
    """Simplify, differentiate, integrate, solve, substitute, or evaluate an expression."""
    try:
        return run_symbolic(request)
    except MathToolError as error:
        raise _translate_math_error(error) from error
    except (ArithmeticError, TypeError, ValueError, OverflowError) as error:
        raise HTTPException(
            status_code=422,
            detail="The symbolic operation could not be completed for this expression.",
        ) from error


@router.post("/numeric/integrate", response_model=NumericIntegrationResponse)
def numerical_integration(
    request: NumericIntegrationRequest,
) -> NumericIntegrationResponse:
    """Compute a definite integral with adaptive quadrature and expose its error estimate."""
    try:
        return integrate_numerically(request)
    except MathToolError as error:
        raise _translate_math_error(error) from error


@router.post("/numeric/root", response_model=RootResponse)
def numerical_root_finding(request: RootRequest) -> RootResponse:
    """Find a real root using Brent's method within the caller-provided finite bracket."""
    try:
        return find_root(request)
    except MathToolError as error:
        raise _translate_math_error(error) from error


@router.post("/statistics", response_model=StatisticsResponse)
def descriptive_statistics(request: StatisticsRequest) -> StatisticsResponse:
    """Return bounded descriptive statistics for a supplied numeric sample."""
    try:
        return describe_statistics(request)
    except MathToolError as error:
        raise _translate_math_error(error) from error


@router.post("/units/convert", response_model=UnitConversionResponse)
def unit_conversion(request: UnitConversionRequest) -> UnitConversionResponse:
    """Convert a numeric quantity between allowlisted, dimensionally compatible units."""
    try:
        return convert_unit(request)
    except MathToolError as error:
        raise _translate_math_error(error) from error


@router.post("/units/check", response_model=DimensionCheckResponse)
def dimensional_analysis(
    request: DimensionCheckRequest,
) -> DimensionCheckResponse:
    """Check arithmetic-expression dimensional compatibility against an expected unit."""
    try:
        return check_dimensions(request)
    except MathToolError as error:
        raise _translate_math_error(error) from error
