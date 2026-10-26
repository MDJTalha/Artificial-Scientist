# Phase 5 — Mathematics and Scientific Tools

**Status:** Core implementation checks passed on commit `bdf3dfffea45ed428fcb21667d282c035fc8d49d`. See the [passing GitHub Actions run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40266731194).  
**Branch:** \`phase-5-mathematical-tools\`, stacked on \`phase-4-knowledge-graph\`.  
**Objective:** provide useful symbolic, numerical, statistical, and dimensional-analysis functions with clear mathematical assumptions, bounded inputs, reference cases, and explicit failure behavior.

## Implemented capabilities

### Safe symbolic operations

\`POST /api/v1/math/symbolic\`

Supported operations: \`simplify\`, \`differentiate\`, \`integrate\`, \`solve\`, \`substitute\`, and \`evaluate\`.

Example derivative request:

\`\`\`json
{
  "operation": "differentiate",
  "expression": "x**3 + sin(x)",
  "symbols": ["x"],
  "variable": "x"
}
\`\`\`

The parser builds SymPy expressions only from a strict Python-AST allowlist. It permits finite numeric constants, declared simple symbols, \`pi\` and \`E\`, arithmetic operators \`+\`, \`-\`, \`*\`, \`/\`, \`**\`, unary signs, and one-argument functions \`abs\`, \`acos\`, \`asin\`, \`atan\`, \`ceil\`, \`cos\`, \`cosh\`, \`exp\`, \`floor\`, \`log\`, \`sin\`, \`sinh\`, \`sqrt\`, \`tan\`, and \`tanh\`.

It rejects Python attribute access, imports, indexing, comprehensions, arbitrary calls, undeclared names, non-finite constants, oversized expressions, and powers with non-literal or excessive exponents. Inputs have an 80-node AST limit and a 500-character expression limit. At most 10 distinct symbols are accepted; result text is bounded. The endpoint does not use SymPy's string parser or \`eval\` to interpret user input. SymPy's own documentation warns that \`sympify\` uses \`eval\` on strings, which is why this project builds expression trees from an allowlist instead: [SymPy sympify security note](https://docs.sympy.org/latest/modules/core.html#sympy.core.sympify.sympify).

The \`solve\` operation solves the submitted expression as an equation equal to zero. \`integrate\` returns an indefinite symbolic integral where SymPy can construct one; an unevaluated expression is not necessarily a closed-form answer. Numerical evaluation requires substitutions for every remaining free symbol and rejects complex/non-finite output.

### Numerical integration

\`POST /api/v1/math/numeric/integrate\`

Uses SciPy adaptive QUADPACK quadrature to estimate a real definite integral. The response includes value, estimated absolute error, evaluation count, requested tolerances, and a convergence/warning flag. The integration interval must be finite and ordered, input expression symbols must be declared through the independent variable and parameter map, and values/tolerances are bounded.

A numerical error estimate is algorithmic evidence about the calculation, not a proof that the result is mathematically exact or that the integrand's model is scientifically valid.

### Real root finding

\`POST /api/v1/math/numeric/root\`

Uses Brent's bracketed solver. The interval must be finite and ordered; endpoint function values must be finite and have opposite signs or contain an endpoint root. The response includes root, function value, convergence status, iterations, function calls, and original bracket. The method finds a bracketed real root; it does not claim to find every root or prove uniqueness outside the bracket.

### Scientific plotting

`POST /api/v1/math/plot` returns an in-memory PNG image for a one-dimensional real-valued function over a finite interval. The plot endpoint uses the same allowlisted expression parser as numeric calculations, supports optional title and axis labels, and caps sampling at 1,000 points. It writes no files to the host, sets `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`, and rejects undefined/non-finite samples or image output larger than 2 MiB. This is a deterministic function plot, not a charting language, arbitrary-data-file renderer, or code execution environment.

### Descriptive statistics

\`POST /api/v1/math/statistics\`

For 2–100,000 finite bounded values, returns count, mean, median, variance, standard deviation, minimum, maximum, and 25th/50th/75th percentiles. \`variance_mode\` explicitly selects \`sample\` or \`population\`; quantiles use linear interpolation. Inputs with non-finite values or excessive scale are rejected rather than returning invalid numeric JSON.

These calculations describe the submitted values only. They do not establish sampling quality, causal effects, representativeness, or statistical significance.

### Unit conversion and dimensional analysis

- \`GET /api/v1/math/units\` lists the accepted unit tokens.
- \`POST /api/v1/math/units/convert\` converts a numeric quantity using Pint after resolving both tokens through the project's allowlist.
- \`POST /api/v1/math/units/check\` evaluates arithmetic expressions over named quantities and checks compatibility with an expected unit.

The initial unit subset includes common length, area, volume, time, mass, temperature, amount-of-substance, current, luminous-intensity, angle, and derived units, as well as common velocity, acceleration, density, energy-per-mass, and power-per-area expressions. Arbitrary unit strings or user-defined units are not accepted.

The dimensional checker supports numeric constants, variables, unary signs, addition, subtraction, multiplication, division, and small numeric constant powers. Function calls are rejected in dimensional expressions. It separately reports:
- syntax/quantity-combination validity;
- whether the calculated dimensions match the expected unit;
- actual unit/dimensionality when calculable;
- converted magnitude when compatible.

Dimensional compatibility can reject invalid physical equations, but a compatible equation can still be based on a wrong model or measurement.

## Common safety and resource limits

- No arbitrary Python code execution.
- No dynamic imports, shell access, filesystem access, network access, or model calls from a mathematical expression.
- Input expressions are short and AST node counts are capped.
- Powers are limited to numeric constants within ±12.
- Symbol/parameter counts are limited to 10.
- Integration uses a fixed maximum of 100 adaptive subintervals and bounded tolerances.
- Root solving is bracketed, with tolerance and iteration limits.
- Statistics input is capped at 100,000 values.
- Unit names are resolved only from an explicit allowlist.
- Non-finite numeric results are rejected.
- Errors are converted into concise validation responses instead of returning stack traces.

These controls reduce exposure but do not replace authentication, external request-rate limiting, per-process CPU/memory limits, or deployment isolation. The API remains unauthenticated and intended for localhost development only.

## Reference-case and adversarial tests

Deterministic tests include:
- Differentiation: derivative of \(x^3 + \sin(x)\).
- Simplification and polynomial solving for \(x^2-4=0\).
- Symbolic antiderivative of \(3x^2\) and substitution/evaluation.
- Rejection of imports, Python attributes, indexing, comprehensions, undeclared names, excessive powers, and oversized ASTs.
- Numerical integral \(\int_0^1 x^2\,dx = 1/3\) with an explicit estimated error.
- Brent root for \(x^2-2\) on the bracket \([1,2]\), checked against \(\sqrt{2}\).
- Rejection of root brackets without a sign change.
- Sample and population variance reference values and linear quartiles.
- SI length conversion and Celsius/Fahrenheit conversion.
- Dimensional check of speed multiplied by time to produce length.
- Reporting a mismatched expected dimension and incompatible addition.
- API status/error contracts for each family of operations.
- PNG rendering signature, plot sample bounds, non-finite-domain rejection, and in-memory output limit.

## Acceptance criteria

- [x] Ruff and all backend tests passed on Python 3.12 and 3.13.
- [x] Frontend type-check, all 6 frontend tests, and production build passed.
- [x] The verified code-head push run is linked below. Documentation-head and pull-request CI will be recorded after their results are confirmed.
- [x] Symbolic expressions never evaluate arbitrary Python text.
- [x] Numerical integration returns an error estimate and an explicit convergence status.
- [x] Root finding requires and reports a finite bracket.
- [x] Statistics modes, quantile method, input bounds, and expected reference cases are documented.
- [x] Unit conversion accepts only allowlisted tokens and rejects incompatible dimensions.
- [x] Dimensional-expression validation distinguishes an invalid expression from an expected-unit mismatch.
- [x] The plot endpoint returns bounded PNG bytes without writing files or executing user code.
- [x] Known limitations remain explicit; no result is presented as a proof of scientific truth.

## Verified CI result

- [Passing code-commit GitHub Actions run](https://github.com/MDJTalha/Artificial-Scientist/actions/runs/40266731194) for `bdf3dfffea45ed428fcb21667d282c035fc8d49d`.
- Backend: Ruff passed; 75 tests passed on Python 3.12 and 75 tests passed on Python 3.13.
- Frontend: TypeScript type-check passed, 6 unit tests passed, and production build completed.
- The suite includes mathematical reference cases, invalid-input/security tests, unit dimensionality cases, and PNG plotting output checks.
- Tests establish code behavior for these cases; they do not certify every mathematical expression, numeric stability for every domain, or scientific validity.

The core Phase 5 acceptance checks have passed. The change remains stacked on Phase 4 and awaits review/integration; no earlier pull request is merged.

## Not implemented in this phase

- Symbolic theorem proving or proof certificates.
- A computer algebra system equivalent to a general-purpose mathematics platform.
- General PDE/ODE solving, optimizers, matrix/eigenvalue APIs, arbitrary precision numerical solvers, or GPU computation.
- Statistical hypothesis tests, Bayesian inference, causal inference, experimental design, or machine learning.
- A complete, domain-reviewed unit ontology or automatic inference of missing units.
- Multi-series plotting, user-supplied datasets/files, 3D visualization, and publication-ready scientific figure workflows.
- Sandboxed execution of arbitrary generated code.

## Libraries and external references

- [SymPy](https://docs.sympy.org/latest/index.html) — symbolic computation.
- [SciPy integration API](https://docs.scipy.org/doc/scipy/reference/integrate.html) and [root finding API](https://docs.scipy.org/doc/scipy/reference/optimize.html) — numerical methods.
- [NumPy](https://numpy.org/doc/stable/) — descriptive statistics and quantiles.
- [Pint](https://pint.readthedocs.io/en/stable/) — unit conversions and dimensionality checks.

Versions are constrained in \`backend/pyproject.toml\` and resolved by the GitHub Actions dependency installation. The CI result is the evidence of the actual dependency and test combination used for this branch.
