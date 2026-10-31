"""Shared pytest fixtures for deterministic API configuration."""

import pytest


@pytest.fixture(autouse=True)
def use_development_environment_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep ordinary API tests in development unless a test explicitly overrides it.

    Settings are cached, so changing the environment variable alone is insufficient.
    Clear the cache before and after each test to prevent configuration leaking between
    tests and to let release-gate tests deliberately select a production environment.
    """
    monkeypatch.setenv("ARTIFICIAL_SCIENTIST_ENV", "development")
    from artificial_scientist.config import get_settings

    clear_cache = getattr(get_settings, "cache_clear", None)
    if callable(clear_cache):
        clear_cache()
    yield
    if callable(clear_cache):
        clear_cache()
