"""Capture the runtime environment needed to interpret controlled-lab results."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import platform
import sys


_RELEVANT_PACKAGES = ("artificial-scientist", "numpy", "scipy", "sympy", "pint", "pydantic")


def capture_environment_manifest() -> dict[str, str]:
    """Return a stable-key manifest of interpreter, platform, and scientific packages."""
    manifest = {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_abi": f"{sys.version_info.major}.{sys.version_info.minor}",
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "machine": platform.machine(),
    }
    for package in _RELEVANT_PACKAGES:
        try:
            manifest[f"package:{package}"] = version(package)
        except PackageNotFoundError:
            manifest[f"package:{package}"] = "not-installed"
    return dict(sorted(manifest.items()))
