"""Tests for configurable OIDC bearer-token validation."""

from types import SimpleNamespace

import jwt
import pytest

from artificial_scientist import identity


def test_oidc_validator_checks_signature_issuer_audience_and_required_claims(monkeypatch):
    captured = {}

    class FakeJWKClient:
        def __init__(self, url, **kwargs):
            captured["url"] = url
            captured["client_kwargs"] = kwargs

        def get_signing_key_from_jwt(self, token):
            captured["token"] = token
            return SimpleNamespace(key="trusted-public-key")

    def fake_decode(token, key, **kwargs):
        captured["decode"] = kwargs
        assert key == "trusted-public-key"
        return {
            "sub": "principal-123",
            "iss": "https://identity.example.test/",
            "aud": ["scientific-api", "other-api"],
            "exp": 2_000_000_000,
            "iat": 1_900_000_000,
        }

    monkeypatch.setattr(identity, "PyJWKClient", FakeJWKClient)
    monkeypatch.setattr(identity.jwt, "decode", fake_decode)
    principal = identity.validate_oidc_bearer_token(
        "signed-token",
        issuer="https://identity.example.test/",
        audience="scientific-api",
        jwks_url="https://identity.example.test/.well-known/jwks.json",
    )

    assert principal.subject == "principal-123"
    assert principal.issuer == "https://identity.example.test/"
    assert principal.audience == "scientific-api"
    assert captured["url"] == "https://identity.example.test/.well-known/jwks.json"
    assert captured["client_kwargs"]["timeout"] == 5
    assert captured["decode"]["algorithms"] == ["RS256"]
    assert captured["decode"]["issuer"] == "https://identity.example.test/"
    assert captured["decode"]["audience"] == "scientific-api"
    assert set(captured["decode"]["options"]["require"]) == {
        "exp", "iat", "iss", "aud", "sub"
    }


def test_oidc_validator_rejects_non_https_jwks_url():
    with pytest.raises(identity.IdentityConfigurationError, match="HTTPS"):
        identity.validate_oidc_bearer_token(
            "token",
            issuer="https://identity.example.test/",
            audience="scientific-api",
            jwks_url="http://identity.example.test/jwks.json",
        )


def test_oidc_validator_requires_complete_trust_configuration():
    with pytest.raises(identity.IdentityConfigurationError, match="must all be configured"):
        identity.validate_oidc_bearer_token(
            "token", issuer="", audience="scientific-api", jwks_url="https://example.test/jwks"
        )


def test_oidc_validator_wraps_jwt_validation_errors(monkeypatch):
    class FakeJWKClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_signing_key_from_jwt(self, _token):
            return SimpleNamespace(key="trusted-public-key")

    monkeypatch.setattr(identity, "PyJWKClient", FakeJWKClient)

    def reject(*_args, **_kwargs):
        raise jwt.InvalidTokenError("private detail")

    monkeypatch.setattr(identity.jwt, "decode", reject)
    with pytest.raises(identity.InvalidIdentityError, match="validation failed"):
        identity.validate_oidc_bearer_token(
            "bad-token",
            issuer="https://identity.example.test/",
            audience="scientific-api",
            jwks_url="https://identity.example.test/jwks.json",
        )
