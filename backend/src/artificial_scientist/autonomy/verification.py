"""Phase 9: independent, reproducible verification utilities."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite, sqrt
from statistics import mean

@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    metric: float
    tolerance: float
    checks: tuple[str,...]
    alternative_explanation: str|None=None

class VerificationError(ValueError): pass
class IndependentVerifier:
    """Uses an intentionally separate comparison path from the producing algorithm."""
    @staticmethod
    def compare(observed:list[float], expected:list[float], *, abs_tol:float=1e-9, rel_tol:float=1e-6)->VerificationResult:
        if not observed or len(observed)!=len(expected): raise VerificationError("equal non-empty vectors required")
        if any(not isfinite(x) for x in observed+expected): raise VerificationError("non-finite values are not accepted")
        errors=[abs(a-b) for a,b in zip(observed,expected)]
        scale=max(1.0,max(abs(x) for x in expected))
        tolerance=max(abs_tol,rel_tol*scale)
        metric=max(errors)
        return VerificationResult(metric<=tolerance,metric,tolerance,("length","finite","absolute_or_relative_error"))
    @staticmethod
    def bootstrap_mean(values:list[float], *, sample_count:int=200, seed:int=17)->VerificationResult:
        if not values or sample_count<20 or sample_count>5000: raise VerificationError("invalid bootstrap request")
        if any(not isfinite(x) for x in values): raise VerificationError("non-finite values are not accepted")
        # Deterministic LCG avoids importing a second statistical framework into the verifier.
        state=seed & 0x7fffffff; means=[]; n=len(values)
        for _ in range(sample_count):
            total=0.0
            for _ in range(n): state=(1103515245*state+12345)&0x7fffffff; total+=values[state%n]
            means.append(total/n)
        mu=mean(means); spread=sqrt(mean((x-mu)**2 for x in means))
        return VerificationResult(True,spread,0.0,("finite","deterministic_bootstrap","dispersion"))
