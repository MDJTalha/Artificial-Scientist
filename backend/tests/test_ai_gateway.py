"""Tests for optional provider configuration, bounded inference and response parsing."""

from types import SimpleNamespace

import httpx
import pytest

from artificial_scientist.ai_gateway import (
    ModelGatewayInvalidResponse,
    ModelGatewayUnavailable,
    generate_research_assistance,
    resolve_model_gateway_config,
)


def _settings(**overrides):
    values = {
        "environment": "development",
        "model_provider": "openai_compatible",
        "model_base_url": "http://127.0.0.1:9999/v1",
        "model_name": "local-research-model",
        "model_api_key": "dev-key",
        "model_timeout_seconds": "5",
        "model_max_tokens": "800",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _FakeClient:
    def __init__(self, response=None, error=None, **kwargs):
        self.response = response
        self.error = error
        self.kwargs = kwargs
        self.request = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def post(self, url, *, json, headers):
        self.request = {"url": url, "json": json, "headers": headers}
        if self.error:
            raise self.error
        return self.response


def test_model_gateway_is_disabled_when_provider_is_not_configured():
    settings = _settings(
        model_provider=None,
        model_base_url=None,
        model_name=None,
        model_api_key=None,
    )
    assert resolve_model_gateway_config(settings) is None
    with pytest.raises(ModelGatewayUnavailable, match="not configured"):
        generate_research_assistance(settings, "Summarize a question", max_output_tokens=100)


def test_model_gateway_rejects_partial_provider_configuration():
    settings = _settings(model_name=None)
    with pytest.raises(ModelGatewayUnavailable, match="configured together"):
        resolve_model_gateway_config(settings)


def test_model_gateway_rejects_remote_http_endpoint_in_production():
    settings = _settings(
        environment="production",
        model_base_url="http://models.example.test/v1",
    )
    with pytest.raises(ModelGatewayUnavailable, match="HTTPS"):
        resolve_model_gateway_config(settings)


def test_model_gateway_requires_key_for_openai_compatible_provider():
    settings = _settings(model_api_key=None)
    with pytest.raises(ModelGatewayUnavailable, match="API key is required"):
        resolve_model_gateway_config(settings)


def test_model_gateway_enforces_bounded_timeout_and_token_caps():
    with pytest.raises(ModelGatewayUnavailable, match="timeout"):
        resolve_model_gateway_config(_settings(model_timeout_seconds="120"))
    with pytest.raises(ModelGatewayUnavailable, match="token cap"):
        resolve_model_gateway_config(_settings(model_max_tokens="100000"))


def test_openai_compatible_gateway_returns_hash_only_provenance(monkeypatch):
    response = httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {"content": "A possible hypothesis; validate it independently."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 23, "completion_tokens": 14},
        },
        request=httpx.Request("POST", "http://127.0.0.1:9999/v1/chat/completions"),
    )
    fake = _FakeClient(response=response)
    monkeypatch.setattr("artificial_scientist.ai_gateway.httpx.Client", lambda **kwargs: fake)

    generation = generate_research_assistance(
        _settings(),
        "Assess a question about conductivity.",
        max_output_tokens=200,
    )

    assert generation.provider == "openai_compatible"
    assert generation.model == "local-research-model"
    assert generation.content.startswith("A possible hypothesis")
    assert len(generation.prompt_sha256) == 64
    assert len(generation.response_sha256) == 64
    assert generation.input_tokens == 23
    assert generation.output_tokens == 14
    assert fake.request["url"].endswith("/v1/chat/completions")
    assert fake.request["headers"]["Authorization"] == "Bearer dev-key"
    assert fake.request["json"]["stream"] is False
    assert fake.request["json"]["max_tokens"] == 200
    assert fake.request["json"]["messages"][0]["role"] == "system"


def test_ollama_gateway_uses_local_endpoint_without_api_key(monkeypatch):
    response = httpx.Response(
        200,
        json={
            "message": {"content": "A cautious research suggestion."},
            "done_reason": "stop",
            "prompt_eval_count": 10,
            "eval_count": 8,
        },
        request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"),
    )
    fake = _FakeClient(response=response)
    monkeypatch.setattr("artificial_scientist.ai_gateway.httpx.Client", lambda **kwargs: fake)
    settings = _settings(
        model_provider="ollama",
        model_base_url="http://127.0.0.1:11434",
        model_api_key=None,
    )

    generation = generate_research_assistance(
        settings,
        "Propose alternatives for a material science question.",
        max_output_tokens=150,
    )

    assert generation.provider == "ollama"
    assert generation.content == "A cautious research suggestion."
    assert generation.input_tokens == 10
    assert generation.output_tokens == 8
    assert fake.request["url"] == "http://127.0.0.1:11434/api/chat"
    assert "Authorization" not in fake.request["headers"]
    assert fake.request["json"]["stream"] is False


def test_gateway_rejects_prompt_and_output_token_limits():
    settings = _settings()
    with pytest.raises(ValueError, match="12,000"):
        generate_research_assistance(
            settings,
            "x" * 12_001,
            max_output_tokens=100,
        )
    with pytest.raises(ValueError, match="operator-configured"):
        generate_research_assistance(
            settings,
            "Valid bounded prompt",
            max_output_tokens=801,
        )


def test_gateway_does_not_follow_provider_redirects(monkeypatch):
    response = httpx.Response(
        302,
        headers={"Location": "https://attacker.example"},
        request=httpx.Request("POST", "http://127.0.0.1:9999/v1/chat/completions"),
    )
    fake = _FakeClient(response=response)
    monkeypatch.setattr("artificial_scientist.ai_gateway.httpx.Client", lambda **kwargs: fake)

    with pytest.raises(ModelGatewayUnavailable, match="redirects"):
        generate_research_assistance(
            _settings(),
            "A prompt",
            max_output_tokens=100,
        )


def test_gateway_rejects_oversized_or_malformed_provider_responses(monkeypatch):
    request = httpx.Request("POST", "http://127.0.0.1:9999/v1/chat/completions")
    oversized = httpx.Response(200, content=b"x" * (64 * 1024 + 1), request=request)
    fake = _FakeClient(response=oversized)
    monkeypatch.setattr("artificial_scientist.ai_gateway.httpx.Client", lambda **kwargs: fake)
    with pytest.raises(ModelGatewayInvalidResponse, match="64 KiB"):
        generate_research_assistance(_settings(), "prompt", max_output_tokens=100)

    malformed = httpx.Response(200, content=b"not json", request=request)
    fake = _FakeClient(response=malformed)
    monkeypatch.setattr("artificial_scientist.ai_gateway.httpx.Client", lambda **kwargs: fake)
    with pytest.raises(ModelGatewayInvalidResponse, match="malformed JSON"):
        generate_research_assistance(_settings(), "prompt", max_output_tokens=100)


def test_gateway_does_not_expose_provider_error_body(monkeypatch):
    request = httpx.Request("POST", "http://127.0.0.1:9999/v1/chat/completions")
    response = httpx.Response(500, text="SECRET KEY leaked by provider", request=request)
    fake = _FakeClient(response=response)
    monkeypatch.setattr("artificial_scientist.ai_gateway.httpx.Client", lambda **kwargs: fake)

    with pytest.raises(ModelGatewayUnavailable) as captured:
        generate_research_assistance(_settings(), "prompt", max_output_tokens=100)

    assert "SECRET" not in str(captured.value)
    assert "dev-key" not in str(captured.value)
