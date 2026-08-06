"""Content hashing and the per-mode stage manifest.

The manifest lives at work/<mode>/manifest.json. Because work/ is partitioned
by run mode, a cached draft artifact can never satisfy a final-mode lookup
(spec §2 rule 4, §5).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

_CHUNK = 1 << 20
_MISSING_SENTINEL = b"\x00stitcher:missing\x00"


def file_digest(path: Path) -> str:
    """SHA-256 of a file's bytes. Missing files hash to a stable sentinel."""
    digest = hashlib.sha256()
    if not path.exists():
        digest.update(_MISSING_SENTINEL)
        digest.update(str(path.name).encode("utf-8"))
        return digest.hexdigest()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def payload_digest(*parts: object) -> str:
    """SHA-256 over a JSON rendering of the parts, in the order given."""
    blob = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Manifest:
    """Maps a stage artifact key to the digest of everything determining it."""

    def __init__(self, path: Path, entries: dict[str, str] | None = None) -> None:
        self.path = path
        self._entries: dict[str, str] = dict(entries or {})

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        if not path.exists():
            return cls(path)
        return cls(path, json.loads(path.read_text(encoding="utf-8")))

    def get(self, key: str) -> str | None:
        return self._entries.get(key)

    def set(self, key: str, digest: str) -> None:
        self._entries[key] = digest

    def is_fresh(self, key: str, digest: str, artifact: Path) -> bool:
        """A cache hit needs both a matching digest and a surviving artifact."""
        return self._entries.get(key) == digest and artifact.exists()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._entries, indent=2, sort_keys=True), encoding="utf-8"
        )

    def as_dict(self) -> dict[str, str]:
        return dict(self._entries)
