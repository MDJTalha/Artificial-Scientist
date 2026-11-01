"""API-level tests for optional tenant AI inference and invocation provenance."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from artificial_scientist.ai_gateway import ModelGeneration
from artificial_scientist.api.routes import ai as ai_routes
from artificial_scientist.api.routes.records import get_record_store
from artificial_scientist.main import app
from artificial_scientist.records.store import RecordStore


def _settings(database: str):
    return SimpleNamespace(
        environment="development",
        database_path=database,
        model_provider="ollama",
        model_base_url="http://127.0.0.1:11434",
        model_name="research-model",
        model_api_key=None,
        model_timeout_seconds="10",
        model_max_tokens="1200",
        model_daily_request_limit="2",
        model_daily_token_budget="1000",
    )


def _generation(prompt: str, content: str = "An unverified model suggestion.") -> ModelGeneration:
    import hashlib

    prompt_bytes = prompt.encode("utf-8")
    response_bytes = content.encode("utf-8")
    return ModelGeneration(
        provider="ollama",
        model="research-model",
        content=content,
        prompt_sha256=hashlib.sha256(prompt_bytes).hexdigest(),
        response_sha256=hashlib.sha256(response_bytes).hexdigest(),
        prompt_bytes=len(prompt_bytes),
        response_bytes=len(response_bytes),
        input_tokens=20,
        output_tokens=12,
        finish_reason="stop",
    )


def test_ai_capabilities_disclose_only_safe_provider_configuration(monkeypatch, tmp_path):
    settings = _settings(str(tmp_path / "ai-capabilities.sqlite3"))
    monkeypatch.setattr(ai_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(
        ai_routes,
        "resolve_model_gateway_config",
        lambda value: SimpleNamespace(
            provider="ollama",
            model="research-model",
            max_output_tokens=800,
        ),
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/ai/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["provider"] == "ollama"
    assert payload["model"] == "research-model"
    assert payload["max_output_tokens"] == 800
    assert payload["daily_request_limit"] == 2
    assert payload["daily_token_budget"] == 1000
    assert "api_key" not in str(payload).lower()
    assert "127.0.0.1" not in str(payload)


def test_ai_generate_stores_hash_only_invocation_provenance(
    monkeypatch, tmp_path
):
    database = str(tmp_path / "ai-inference.sqlite3")
    settings = _settings(database)
    store = RecordStore(database)
    prompt = "Help compare alternative explanations for the supplied research question."
    generated = "A model-generated suggestion; it is not a verified scientific result."
    monkeypatch.setattr(ai_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(
        ai_routes,
        "resolve_model_gateway_config",
        lambda value: SimpleNamespace(
            provider="ollama",
            model="research-model",
            max_output_tokens=1200,
        ),
    )
    monkeypatch.setattr(
        ai_routes,
        "generate_research_assistance",
        lambda value, text, max_output_tokens: _generation(text, generated),
    )
    app.dependency_overrides[get_record_store] = lambda: store

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/ai/generate",
                json={"prompt": prompt, "max_output_tokens": 300},
            )
        assert response.status_code == 201
        body = response.json()
        assert body["content"] == generated
        assert body["provider"] == "ollama"
        assert body["requires_human_review"] is True
        assert body["input_tokens"] == 20
        assert body["output_tokens"] == 12
        assert len(body["prompt_sha256"]) == 64
        assert len(body["response_sha256"]) == 64

        from uuid import UUID

        record = store.get(UUID(body["invocation_record_id"]), tenant_id="development")
        serialized = str(record.payload)
        assert record.record_type == "model_invocation"
        assert body["prompt_sha256"] in serialized
        assert body["response_sha256"] in serialized
        assert prompt not in serialized
        assert generated not in serialized

        import sqlite3

        with sqlite3.connect(database) as connection:
            ledger = connection.execute(
                "SELECT status, requested_tokens, record_id FROM ai_invocation_budget"
            ).fetchone()
        assert ledger == ("completed", 300, body["invocation_record_id"])
    finally:
        app.dependency_overrides.pop(get_record_store, None)


def test_ai_daily_budget_blocks_provider_calls_after_limit(
    monkeypatch, tmp_path
):
    database = str(tmp_path / "ai-daily-budget.sqlite3")
    settings = _settings(database)
    settings.model_daily_request_limit = "1"
    store = RecordStore(database)
    calls = {"count": 0}

    def generate(value, prompt, *, max_output_tokens):
        calls["count"] += 1
        return _generation(prompt)

    monkeypatch.setattr(ai_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(
        ai_routes,
        "resolve_model_gateway_config",
        lambda value: SimpleNamespace(
            provider="ollama",
            model="research-model",
            max_output_tokens=1200,
        ),
    )
    monkeypatch.setattr(ai_routes, "generate_research_assistance", generate)
    app.dependency_overrides[get_record_store] = lambda: store

    try:
        with TestClient(app) as client:
            first = client.post(
                "/api/v1/ai/generate",
                json={"prompt": "First request", "max_output_tokens": 800},
            )
            second = client.post(
                "/api/v1/ai/generate",
                json={"prompt": "Second request", "max_output_tokens": 100},
            )
        assert first.status_code == 201
        assert second.status_code == 429
        assert "daily AI request limit" in second.json()["detail"]
        assert calls["count"] == 1
    finally:
        app.dependency_overrides.pop(get_record_store, None)


def test_ai_generation_fails_closed_when_provider_is_not_configured(
    monkeypatch, tmp_path
):
    database = str(tmp_path / "ai-disabled.sqlite3")
    settings = _settings(database)
    monkeypatch.setattr(ai_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(ai_routes, "resolve_model_gateway_config", lambda value: None)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/generate",
            json={"prompt": "Do a research analysis", "max_output_tokens": 200},
        )

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]
