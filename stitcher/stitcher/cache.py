"""Content hashing and the per-mode stage manifest.

The manifest lives at work/<mode>/manifest.json. Because work/ is partitioned
by run mode, a cached draft artifact can never satisfy a final-mode lookup
(spec §2 rule 4, §5).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
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
    """SHA-256 over a JSON rendering of the parts, in the order given.

    Raises TypeError if any part is a set or frozenset, as their string
    representation depends on process-specific hash randomization.
    """
    # Check for sets/frozensets which are non-deterministic
    for i, part in enumerate(parts):
        if isinstance(part, (set, frozenset)):
            raise TypeError(
                f"payload_digest does not accept sets or frozensets (part {i} is {type(part).__name__})"
            )

    blob = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Manifest:
    """Maps a stage artifact key to the digest of everything determining it."""

    def __init__(self, path: Path, entries: dict[str, str] | None = None) -> None:
        self.path = path
        self._entries: dict[str, str] = dict(entries or {})

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        """Load manifest from disk, degrading gracefully on errors.

        Returns an empty Manifest if the file is missing, unreadable, contains
        invalid JSON, or contains valid JSON that is not a dict. This ensures
        a corrupted manifest does not brick the workspace.
        """
        if not path.exists():
            return cls(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return cls(path)
            return cls(path, data)
        except (json.JSONDecodeError, TypeError, OSError, UnicodeDecodeError):
            # Corrupt, unreadable, or invalid manifest: return empty
            return cls(path)

    def get(self, key: str) -> str | None:
        return self._entries.get(key)

    def set(self, key: str, digest: str) -> None:
        self._entries[key] = digest

    def is_fresh(self, key: str, digest: str, artifact: Path) -> bool:
        """A cache hit needs both a matching digest and a surviving artifact."""
        return self._entries.get(key) == digest and artifact.exists()

    def save(self) -> None:
        """Save manifest to disk atomically.

        Writes to a temporary file in the same directory, then replaces the
        target atomically to ensure a crash mid-write does not corrupt the manifest.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(self._entries, indent=2, sort_keys=True)

        # Write to temp file in the same directory for atomic replace
        fd, temp_path = tempfile.mkstemp(
            dir=self.path.parent, prefix=".manifest.tmp.", suffix=".json"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(temp_path, self.path)
        except Exception:
            # Clean up temp file if something goes wrong
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def as_dict(self) -> dict[str, str]:
        return dict(self._entries)
