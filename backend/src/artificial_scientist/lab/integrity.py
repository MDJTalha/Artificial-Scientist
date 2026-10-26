"""Canonical integrity digest for persisted controlled-lab run records."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def result_digest(payload: dict[str, Any]) -> str:
    """Hash every persisted response field except the digest field itself."""
    canonical_payload = dict(payload)
    canonical_payload.pop("result_sha256", None)
    canonical = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
