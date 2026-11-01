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


def test_oidc_validator_fails_closed_when_jwks_key_lookup_fails(monkeypatch):
    class UnavailableJWKClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_signing_key_from_jwt(self, _token):
            raise jwt.PyJWKClientError("upstream JWKS details must not escape")

    monkeypatch.setattr(identity, "PyJWKClient", UnavailableJWKClient)

    with pytest.raises(identity.InvalidIdentityError, match="validation failed") as error:
        identity.validate_oidc_bearer_token(
            "signed-token",
            issuer="https://identity.example.test/",
            audience="scientific-api",
            jwks_url="https://identity.example.test/jwks.json",
        )

    assert "upstream JWKS details" not in str(error.value)


@pytest.mark.parametrize(
    ("claims", "message"),
    [
        (
            {
                "sub": "   ",
                "iss": "https://identity.example.test/",
                "aud": "scientific-api",
                "exp": 2_000_000_000,
                "iat": 1_900_000_000,
            },
            "subject is missing or invalid",
        ),
        (
            {
                "sub": "principal-123",
                "iss": "https://identity.example.test/",
                "aud": "wrong-api",
                "exp": 2_000_000_000,
                "iat": 1_900_000_000,
            },
            "audience is invalid",
        ),
        (
            {
                "sub": "s" * 256,
                "iss": "https://identity.example.test/",
                "aud": "scientific-api",
                "exp": 2_000_000_000,
                "iat": 1_900_000_000,
            },
            "subject is missing or invalid",
        ),
        (
            {
                "sub": "principal-123",
                "iss": "i" * 513,
                "aud": "scientific-api",
                "exp": 2_000_000_000,
                "iat": 1_900_000_000,
            },
            "issuer is missing or invalid",
        ),
    ],
)
def test_oidc_validator_rejects_invalid_identity_claim_shapes(monkeypatch, claims, message):
    class FakeJWKClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_signing_key_from_jwt(self, _token):
            return SimpleNamespace(key="trusted-public-key")

    monkeypatch.setattr(identity, "PyJWKClient", FakeJWKClient)
    monkeypatch.setattr(identity.jwt, "decode", lambda *_args, **_kwargs: claims)

    with pytest.raises(identity.InvalidIdentityError, match=message):
        identity.validate_oidc_bearer_token(
            "signed-token",
            issuer="https://identity.example.test/",
            audience="scientific-api",
            jwks_url="https://identity.example.test/jwks.json",
        )

@pytest.mark.parametrize(
    "jwks_url",
    [
        "https://",
        "https://user:password@identity.example.test/jwks.json",
        "https://identity.example.test/jwks.json#fragment",
        "https://identity.example.test:invalid/jwks.json",
        "https://identity.example.test:65536/jwks.json",
        "https://identity.example.test /jwks.json",
    ],
)
def test_oidc_validator_rejects_malformed_or_unsafe_jwks_urls(jwks_url):
    with pytest.raises(identity.IdentityConfigurationError, match="JWKS URL"):
        identity.validate_oidc_bearer_token(
            "token",
            issuer="https://identity.example.test/",
            audience="scientific-api",
            jwks_url=jwks_url,
        )


@pytest.mark.parametrize(
    ("issuer", "audience"),
    [("   ", "scientific-api"), ("https://identity.example.test/", "  ")],
)
def test_oidc_validator_rejects_blank_trust_values(issuer, audience):
    with pytest.raises(
        identity.IdentityConfigurationError, match="must all be configured"
    ):
        identity.validate_oidc_bearer_token(
            "token",
            issuer=issuer,
            audience=audience,
            jwks_url="https://identity.example.test/jwks.json",
        )



COGNITO_ISSUER = "https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_example"
COGNITO_JWKS = f"{COGNITO_ISSUER}/.well-known/jwks.json"


def test_cognito_access_token_uses_client_id_token_use_and_required_scope(monkeypatch):
    captured = {}

    class FakeJWKClient:
        def __init__(self, url, **kwargs):
            captured["jwks_url"] = url

        def get_signing_key_from_jwt(self, token):
            return SimpleNamespace(key="cognito-public-key")

    def fake_decode(token, key, **kwargs):
        captured["decode"] = kwargs
        return {
            "sub": "cognito-sub-123",
            "iss": COGNITO_ISSUER,
            "client_id": "asds-public-client",
            "token_use": "access",
            "scope": "openid email asds-api/access",
            "exp": 2_000_000_000,
            "iat": 1_900_000_000,
        }

    monkeypatch.setattr(identity, "PyJWKClient", FakeJWKClient)
    monkeypatch.setattr(identity.jwt, "decode", fake_decode)
    principal = identity.validate_oidc_bearer_token(
        "signed-cognito-access-token",
        issuer="https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_example",
        audience="asds-public-client",
        jwks_url=COGNITO_JWKS,
        audience_claim="client_id",
        expected_token_use="access",
        expected_scope="asds-api/access",
    )

    assert principal.subject == "cognito-sub-123"
    assert captured["decode"]["audience"] is None
    assert captured["decode"]["options"]["verify_aud"] is False
    assert set(captured["decode"]["options"]["require"]) == {
        "exp", "iat", "iss", "client_id", "sub"
    }


def test_cognito_access_token_rejects_missing_required_scope(monkeypatch):
    class FakeJWKClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_signing_key_from_jwt(self, _token):
            return SimpleNamespace(key="cognito-public-key")

    monkeypatch.setattr(identity, "PyJWKClient", FakeJWKClient)
    monkeypatch.setattr(
        identity.jwt,
        "decode",
        lambda *_args, **_kwargs: {
            "sub": "cognito-sub-123",
            "iss": "https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_example",
            "client_id": "asds-public-client",
            "token_use": "access",
            "scope": "openid email",
            "exp": 2_000_000_000,
            "iat": 1_900_000_000,
        },
    )

    with pytest.raises(identity.InvalidIdentityError, match="required API scope"):
        identity.validate_oidc_bearer_token(
            "signed-cognito-access-token",
            issuer="https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_example",
            audience="asds-public-client",
            jwks_url=COGNITO_JWKS,
            audience_claim="client_id",
            expected_token_use="access",
            expected_scope="asds-api/access",
        )
