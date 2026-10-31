"""Phase 10: versioned scientific memory with contradictions and rollback."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from artificial_scientist.autonomy.store import AutonomyStore


@dataclass(frozen=True)
class MemoryVersion:
    key: str
    version: int
    value: dict
    status: str
    evidence: tuple[str, ...]
    created_at: datetime
    digest: str
    supersedes: int | None


class MemoryError(ValueError):
    """Raised when a memory operation violates provenance requirements."""


class ResearchMemory:
    def __init__(self, store: AutonomyStore | None = None):
        self.store = store
        self._items: dict[str, list[MemoryVersion]] = {}
        if store:
            self._load_persisted()

    def _load_persisted(self) -> None:
        for key in self.store.memory_keys():
            for row in self.store.memory_history(key):
                self._items.setdefault(key, []).append(
                    MemoryVersion(
                        key=row["key_name"],
                        version=int(row["version"]),
                        value=json.loads(row["value_json"]),
                        status=row["status"],
                        evidence=tuple(json.loads(row["evidence_json"])),
                        created_at=datetime.fromisoformat(row["created_at"]),
                        digest=row["digest"],
                        supersedes=row["supersedes_version"],
                    )
                )

    def put(
        self,
        key: str,
        value: dict,
        *,
        evidence: tuple[str, ...],
        status: str = "active",
    ) -> MemoryVersion:
        if not key or len(key) > 200 or not evidence:
            raise MemoryError("key and evidence are required")
        versions = self._items.setdefault(key, [])
        previous = versions[-1] if versions else None
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = sha256(payload.encode("utf-8")).hexdigest()
        item = MemoryVersion(
            key=key,
            version=len(versions) + 1,
            value=value,
            status=status,
            evidence=tuple(evidence),
            created_at=datetime.now(UTC),
            digest=digest,
            supersedes=previous.version if previous else None,
        )
        if self.store:
            persisted_version = self.store.memory_put(
                key, value, status, tuple(evidence), digest, item.supersedes
            )
            if persisted_version != item.version:
                raise MemoryError("persistent memory version diverged")
        versions.append(item)
        return item

    def history(self, key: str) -> tuple[MemoryVersion, ...]:
        return tuple(self._items.get(key, ()))

    def contradict(self, key: str, *, evidence: tuple[str, ...], reason: str) -> MemoryVersion:
        if not reason or not evidence:
            raise MemoryError("contradiction requires reason and evidence")
        current = self.current(key)
        return self.put(
            key,
            {"contradicts": current.digest, "reason": reason},
            evidence=evidence,
            status="disputed",
        )

    def rollback(self, key: str, version: int) -> MemoryVersion:
        versions = self._items.get(key, [])
        if version < 1 or version > len(versions):
            raise MemoryError("unknown memory version")
        target = versions[version - 1]
        return self.put(
            key, target.value, evidence=target.evidence, status="rollback"
        )

    def current(self, key: str) -> MemoryVersion:
        versions = self._items.get(key, [])
        if not versions:
            raise MemoryError("unknown memory key")
        return versions[-1]
