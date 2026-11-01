"""Regression tests for Auth0-compatible API authentication and release gates."""

import asyncio
from types import SimpleNamespace

from artificial_scientist import main


def invoke_asgi(app, path: str, headers: list[tuple[bytes, bytes]] | None = None):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers or [],
        "server": ("testserver", 443),
        "client": ("127.0.0.1", 12345),
    }
    asyncio.run(app(scope, receive, send))
    return sent


def response_status(messages):
    return next(
        message["status"]
        for message in messages
        if message["type"] == "http.response.start"
    )


def test_oidc_middleware_protects_literature_and_discovery_routes(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(
            environment="production",
            oidc_issuer="https://tenant.example/",
            oidc_audience="https://api.example",
            oidc_jwks_url="https://tenant.example/.well-known/jwks.json",
            oidc_audience_claim="aud",
            oidc_token_use=None,
            oidc_required_scope=None,
        ),
    )
    called = []

    async def downstream(scope, receive, send):
        called.append(scope["path"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = main.OIDCAuthenticationMiddleware(downstream)
    protected_paths = (
        "/api/v1/literature/search",
        "/api/v1/discovery/decompose",
        "/api/v1/autonomy/workflows",
    )
    for path in protected_paths:
        messages = invoke_asgi(middleware, path)
        assert response_status(messages) == 401
    assert called == []


def test_oidc_middleware_accepts_a_valid_auth0_audience_token(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(
            environment="production",
            oidc_issuer="https://tenant.example/",
            oidc_audience="https://api.example",
            oidc_jwks_url="https://tenant.example/.well-known/jwks.json",
            oidc_audience_claim="aud",
            oidc_token_use=None,
            oidc_required_scope=None,
        ),
    )
    monkeypatch.setattr(
        main,
        "validate_oidc_bearer_token",
        lambda token, **kwargs: SimpleNamespace(subject="auth0|subject", issuer=kwargs["issuer"]),
    )

    async def downstream(scope, receive, send):
        assert scope["state"]["authenticated_principal"].subject == "auth0|subject"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = main.OIDCAuthenticationMiddleware(downstream)
    messages = invoke_asgi(
        middleware,
        "/api/v1/literature/search",
        [(b"authorization", b"Bearer signed-access-token")],
    )
    assert response_status(messages) == 200


def test_phase7_record_and_discovery_gate_is_active_outside_development(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(environment="production"),
    )

    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = main.Phase7RecordIsolationGateMiddleware(downstream)
    for path in ("/api/v1/records", "/api/v1/discovery/decompose"):
        messages = invoke_asgi(middleware, path)
        assert response_status(messages) == 503

def test_oidc_middleware_does_not_bypass_similarly_named_routes(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(
            environment="production",
            oidc_issuer="https://tenant.example/",
            oidc_audience="https://api.example",
            oidc_jwks_url="https://tenant.example/.well-known/jwks.json",
            oidc_audience_claim="aud",
            oidc_token_use=None,
            oidc_required_scope=None,
        ),
    )
    called = []

    async def downstream(scope, receive, send):
        called.append(scope["path"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = main.OIDCAuthenticationMiddleware(downstream)
    for path in ("/api/v1/labyrinth", "/api/v1/records-export"):
        messages = invoke_asgi(middleware, path)
        assert response_status(messages) == 401
    assert called == []

