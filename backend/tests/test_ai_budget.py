"""Concurrency and limit tests for tenant-scoped AI inference budgets."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from artificial_scientist.ai_budget import AiBudgetExceeded, AiInvocationBudgetStore


def test_ai_budget_reserves_requests_and_tokens_and_finalizes(tmp_path):
    store = AiInvocationBudgetStore(str(tmp_path / "ai-budget.sqlite3"))
    reservation = store.reserve(
        tenant_id="tenant-a",
        requested_tokens=400,
        provider="ollama",
        model="research-model",
        daily_request_limit=2,
        daily_token_budget=800,
    )
    store.finalize(
        reservation,
        status="completed",
        prompt_sha256="a" * 64,
        response_sha256="b" * 64,
        input_tokens=70,
        output_tokens=120,
        record_id="model-invocation-record-1",
    )
    second = store.reserve(
        tenant_id="tenant-a",
        requested_tokens=400,
        provider="ollama",
        model="research-model",
        daily_request_limit=2,
        daily_token_budget=800,
    )
    store.finalize(second, status="failed")
    with pytest.raises(AiBudgetExceeded, match="request limit"):
        store.reserve(
            tenant_id="tenant-a",
            requested_tokens=1,
            provider="ollama",
            model="research-model",
            daily_request_limit=2,
            daily_token_budget=800,
        )


def test_ai_budget_is_isolated_by_tenant(tmp_path):
    store = AiInvocationBudgetStore(str(tmp_path / "ai-tenant-budget.sqlite3"))
    store.reserve(
        tenant_id="tenant-a",
        requested_tokens=500,
        provider="ollama",
        model="model-a",
        daily_request_limit=1,
        daily_token_budget=500,
    )
    store.reserve(
        tenant_id="tenant-b",
        requested_tokens=500,
        provider="ollama",
        model="model-b",
        daily_request_limit=1,
        daily_token_budget=500,
    )


def test_ai_budget_rejects_concurrent_reservations_beyond_daily_cap(tmp_path):
    store = AiInvocationBudgetStore(str(tmp_path / "ai-budget-race.sqlite3"))

    def reserve_one(index: int) -> str:
        return store.reserve(
            tenant_id="tenant-concurrent",
            requested_tokens=100,
            provider="ollama",
            model=f"model-{index}",
            daily_request_limit=3,
            daily_token_budget=10_000,
        )

    def attempt(index: int) -> bool:
        try:
            reserve_one(index)
            return True
        except AiBudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=12) as executor:
        outcomes = list(executor.map(attempt, range(12)))

    assert sum(outcomes) == 3


def test_ai_budget_reserves_tokens_atomically(tmp_path):
    store = AiInvocationBudgetStore(str(tmp_path / "ai-token-budget.sqlite3"))
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(
                store.reserve,
                tenant_id="tenant-tokens",
                requested_tokens=300,
                provider="ollama",
                model=f"model-{index}",
                daily_request_limit=20,
                daily_token_budget=900,
            )
            for index in range(8)
        ]
    results = []
    for future in futures:
        try:
            results.append(future.result())
        except AiBudgetExceeded:
            pass

    assert len(results) == 3
