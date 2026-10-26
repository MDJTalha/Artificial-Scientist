"""Validated request and response contracts for the bounded math toolkit."""

from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")


def _finite_number(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("numeric inputs must be finite")
    if abs(value) > 1e100:
        raise ValueError("absolute numeric inputs must not exceed 1e100")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SymbolicRequest(StrictModel):
    operation: Literal["simplify", "differentiate", "integrate", "solve", "substitute", "evaluate"]
    expression: str = Field(min_length=1, max_length=500)
    symbols: list[str] = Field(default_factory=list, max_length=10)
    variable: str | None = Field(default=None, max_length=32)
    substitutions: dict[str, float] = Field(default_factory=dict, max_length=10)

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("symbols must be unique")
        if any(not Identifier.fullmatch(value) for value in values):
            raise ValueError("symbols must be simple ASCII identifiers")
        if {"pi", "E"} & set(values):
            raise ValueError("pi and E are reserved constants")
        return values

    @field_validator("substitutions")
    @classmethod
    def validate_substitutions(cls, values: dict[str, float]) -> dict[str, float]:
        for name, value in values.items():
            if not Identifier.fullmatch(name) or name in {"pi", "E"}:
                raise ValueError("substitution keys must be simple non-reserved identifiers")
            _finite_number(value)
        return values

    @model_validator(mode="after")
    def validate_operation(self) -> SymbolicRequest:
        if self.variable is not None:
            if not Identifier.fullmatch(self.variable) or self.variable in {"pi", "E"}:
                raise ValueError("variable must be a simple non-reserved identifier")
        if self.operation in {"differentiate", "integrate", "solve"} and not self.variable:
            raise ValueError(f"{self.operation} requires variable")
        if len(set(self.symbols) | set(self.substitutions)) > 10:
            raise ValueError("at most 10 distinct symbols and substitutions are supported")
        return self


class SymbolicResponse(BaseModel):
    operation: str
    expression: str
    result: str
    results: list[str] = Field(default_factory=list)
    free_symbols: list[str] = Field(default_factory=list)
    numeric_value: float | None = None
    method: str
    note: str = (
        "Results are computational outputs, not an independent proof of a mathematical "
        "theorem. Review assumptions and domains before scientific use."
    )


class NumericRequest(StrictModel):
    expression: str = Field(min_length=1, max_length=500)
    variable: str = Field(min_length=1, max_length=32)
    parameters: dict[str, float] = Field(default_factory=dict, max_length=10)

    @field_validator("variable")
    @classmethod
    def validate_variable(cls, value: str) -> str:
        if not Identifier.fullmatch(value) or value in {"pi", "E"}:
            raise ValueError("variable must be a simple non-reserved identifier")
        return value

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, values: dict[str, float]) -> dict[str, float]:
        for name, value in values.items():
            if not Identifier.fullmatch(name) or name in {"pi", "E"}:
                raise ValueError("parameter keys must be simple non-reserved identifiers")
            if not math.isfinite(value) or abs(value) > 1e100:
                raise ValueError("parameters must be finite and bounded by 1e100")
        return values

    @model_validator(mode="after")
    def variable_not_parameter(self) -> NumericRequest:
        if self.variable in self.parameters:
            raise ValueError("the independent variable must not also be a parameter")
        return self


class NumericIntegrationRequest(NumericRequest):
    lower: float
    upper: float
    absolute_tolerance: float = Field(default=1e-9, ge=1e-12, le=1e-3)
    relative_tolerance: float = Field(default=1e-9, ge=1e-12, le=1e-3)

    @field_validator("lower", "upper")
    @classmethod
    def validate_bounds(cls, value: float) -> float:
        return _finite_number(value)

    @model_validator(mode="after")
    def ordered_bounds(self) -> NumericIntegrationRequest:
        if self.lower >= self.upper:
            raise ValueError("lower must be less than upper")
        return self


class NumericIntegrationResponse(BaseModel):
    value: float
    estimated_absolute_error: float
    evaluations: int = Field(ge=1)
    converged: bool
    warning: str | None = None
    method: str = "SciPy adaptive QUADPACK quadrature"
    tolerance: dict[str, float]
    note: str = (
        "Numerical integration reports an estimate and error bound from the algorithm; "
        "it does not prove the integral is exact."
    )


class RootRequest(NumericRequest):
    lower: float
    upper: float
    tolerance: float = Field(default=1e-10, ge=1e-12, le=1e-3)
    max_iterations: int = Field(default=100, ge=1, le=500)

    @field_validator("lower", "upper")
    @classmethod
    def validate_bounds(cls, value: float) -> float:
        return _finite_number(value)

    @model_validator(mode="after")
    def ordered_bracket(self) -> RootRequest:
        if self.lower >= self.upper:
            raise ValueError("lower must be less than upper")
        return self


class PlotRequest(NumericRequest):
    """A bounded one-dimensional scalar function plot; no user code is evaluated."""

    lower: float
    upper: float
    points: int = Field(default=400, ge=50, le=1000)
    title: str = Field(default="Mathematical function", max_length=120)
    x_label: str = Field(default="x", max_length=80)
    y_label: str = Field(default="f(x)", max_length=80)

    @field_validator("lower", "upper")
    @classmethod
    def validate_plot_bounds(cls, value: float) -> float:
        return _finite_number(value)

    @model_validator(mode="after")
    def ordered_plot_bounds(self) -> PlotRequest:
        if self.lower >= self.upper:
            raise ValueError("lower must be less than upper")
        return self


class RootResponse(BaseModel):
    root: float
    function_value: float
    converged: bool
    iterations: int = Field(ge=0)
    function_calls: int = Field(ge=1)
    bracket: tuple[float, float]
    method: str = "Brent's bracketed root solver"
    note: str = (
        "A root is reported only for a validated finite computation. The supplied "
        "bracket and model assumptions still require review."
    )


class StatisticsRequest(StrictModel):
    values: list[float] = Field(min_length=2, max_length=100_000)
    variance_mode: Literal["sample", "population"] = "sample"

    @field_validator("values")
    @classmethod
    def finite_bounded_values(cls, values: list[float]) -> list[float]:
        for value in values:
            _finite_number(value)
        return values


class StatisticsResponse(BaseModel):
    count: int = Field(ge=2)
    mean: float
    median: float
    variance: float = Field(ge=0)
    standard_deviation: float = Field(ge=0)
    minimum: float
    maximum: float
    quartiles: dict[str, float]
    variance_mode: Literal["sample", "population"]
    method: str = "NumPy float64 descriptive statistics and linear quantiles"
    note: str = (
        "Statistics describe the supplied values only; they do not determine sampling "
        "quality, causal effects, or scientific significance."
    )


class UnitConversionRequest(StrictModel):
    value: float
    source_unit: str = Field(min_length=1, max_length=40)
    target_unit: str = Field(min_length=1, max_length=40)

    @field_validator("value")
    @classmethod
    def finite_bounded_value(cls, value: float) -> float:
        return _finite_number(value)


class UnitConversionResponse(BaseModel):
    input_value: float
    input_unit: str
    converted_value: float
    target_unit: str
    dimensionality: str
    method: str = "Pint unit registry conversion"
    note: str = (
        "Only the toolkit's allowlisted units can be used; conversions do not establish "
        "that the selected physical quantity or measurement is scientifically correct."
    )


class QuantityInput(StrictModel):
    value: float
    unit: str = Field(min_length=1, max_length=40)

    @field_validator("value")
    @classmethod
    def finite_bounded_value(cls, value: float) -> float:
        return _finite_number(value)


class DimensionCheckRequest(StrictModel):
    expression: str = Field(min_length=1, max_length=300)
    variables: dict[str, QuantityInput] = Field(min_length=1, max_length=10)
    expected_unit: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def validate_names(self) -> DimensionCheckRequest:
        if any(
            not Identifier.fullmatch(name) or name in {"pi", "E"}
            for name in self.variables
        ):
            raise ValueError("quantity keys must be simple non-reserved identifiers")
        return self


class DimensionCheckResponse(BaseModel):
    expression: str
    expression_valid: bool
    matches_expected_unit: bool
    actual_unit: str | None = None
    actual_dimensionality: str | None = None
    expected_unit: str
    converted_value: float | None = None
    message: str
    method: str = "Pint dimension and unit compatibility checks"
