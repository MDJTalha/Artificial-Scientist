"""Tests for the global Cognito authentication boundary."""

from types import SimpleNamespace

import pytest

from artificial_scientist import main


@pytest.mark.asyncio
async def test_cognito_middleware_rejects_missing_bearer_token(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(
            environment="production",
            oidc_issuer="https://cognito-idp.example.amazonaws.com/pool",
            oidc_audience="client-id",
            oidc_jwks_url="https://cognito-idp.example.amazonaws.com/pool/.well-known/jwks.json",
            oidc_audience_claim="client_id",
            oidc_token_use="access",
            oidc_required_scope="asds-api/access",
        ),
    )
    sent = []

    async def app(_scope, _receive, _send):
        raise AssertionError("Protected route must not be reached without a bearer token")

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    middleware = main.CognitoAuthenticationMiddleware(app)
    await middleware(
        {"type": "http", "path": "/api/v1/math/units", "headers": []},
        receive,
        send,
    )

    assert sent[0]["status"] == 401
    assert (b"www-authenticate", b"Bearer") in sent[0]["headers"]


@pytest.mark.asyncio
async def test_cognito_middleware_leaves_health_public_and_validates_protected_route(monkeypatch):
    principal = SimpleNamespace(subject="sub-1", issuer="https://issuer.example", audience="client")
    settings = SimpleNamespace(
        environment="production",
        oidc_issuer="https://issuer.example",
        oidc_audience="client",
        oidc_jwks_url="https://issuer.example/jwks",
        oidc_audience_claim="client_id",
        oidc_token_use="access",
        oidc_required_scope="asds-api/access",
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    calls = []

    def validate(token, **kwargs):
        calls.append((token, kwargs))
        return principal

    monkeypatch.setattr(main, "validate_oidc_bearer_token", validate)
    reached = []

    async def app(scope, _receive, send):
        reached.append(scope)
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(_message):
        pass

    middleware = main.CognitoAuthenticationMiddleware(app)
    health_scope = {"type": "http", "path": "/api/v1/health", "headers": []}
    await middleware(health_scope, receive, send)
    assert health_scope in reached
    assert not calls

    protected_scope = {
        "type": "http",
        "path": "/api/v1/math/units",
        "headers": [(b"authorization", b"Bearer valid-token")],
    }
    await middleware(protected_scope, receive, send)
    assert protected_scope in reached
    assert protected_scope["state"]["authenticated_principal"] is principal
    assert calls[0][0] == "valid-token"
    assert calls[0][1]["audience_claim"] == "client_id"
    assert calls[0][1]["expected_scope"] == "asds-api/access"
