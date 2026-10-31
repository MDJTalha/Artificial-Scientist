"""Sanitized live OIDC/JWKS discovery probe.

Fetches only provider metadata/JWKS and never prints tokens or private keys.
"""
from __future__ import annotations
import argparse
import json
import ssl
import urllib.request
from urllib.parse import urlsplit

def fetch_json(url: str, timeout: float = 5.0) -> dict:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("URL must be HTTPS with a hostname.")
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(
        request, timeout=timeout, context=ssl.create_default_context()
    ) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("Provider response is not a JSON object.")
    return value

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("jwks_url")
    args = parser.parse_args()
    payload = fetch_json(args.jwks_url)
    keys = payload.get("keys")
    if not isinstance(keys, list) or not keys:
        raise RuntimeError("JWKS contains no keys.")
    sanitized = []
    for key in keys:
        if isinstance(key, dict):
            sanitized.append(
                {"kid": key.get("kid"), "kty": key.get("kty"), "alg": key.get("alg"), "use": key.get("use")}
            )
    print(json.dumps({"key_count": len(keys), "keys": sanitized}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
