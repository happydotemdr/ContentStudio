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

# --- the stitcher's own code version, as one number ------------------------
#
# ******************* BUMP THIS WHEN RENDER-AFFECTING CODE CHANGES ***********
#
# Every cache key folds in the spec, the input assets, the ffmpeg build and
# the run mode -- but nothing in any key changed when the STITCHER's OWN CODE
# changed. So after fixing a filter, an argv, or a constant that lands in a
# command line, `render` reported "no changes; v01 is current" and did
# nothing, until someone remembered `--force` or `clean`. During active
# development that is not a stale cache, it is a misleading one.
#
# CACHE_EPOCH is that missing input. It is folded into every stage key
# (shots, overlays, audio, assemble) and into cli.run_digest, so bumping it
# invalidates the whole workspace's cache in one edit.
#
# WHAT "RENDER-AFFECTING" MEANS -- bump for any change that could make the
# same spec and the same assets produce different BYTES on disk:
#   - any filter string, filtergraph shape, or filter constant
#     (shots.py, motion.py, envelope.py, audio.py, assemble.py, overlays.py);
#   - any ffmpeg/ffprobe argv: added, removed or reordered flags, encoder
#     settings, pixel format, colour tagging, -fps_mode, CRF/preset defaults;
#   - any numeric constant that reaches a command line or a computed frame
#     count (LRA_TARGET, DRAFT_CRF, DRAFT_PRESET, supersample factors,
#     rounding of frame bounds);
#   - any change to overlay text layout, font handling, or PNG composition.
#
# Do NOT bump for: comments, docstrings, tests, type annotations, error
# messages, verify.py's measurement code (stage F reads the output, it does
# not produce it), or CLI wiring that cannot change a rendered byte.
#
# WHY A HAND-BUMPED INTEGER rather than a package version or a source hash: a
# human decides when the output could have changed, and this is honest about
# that. A source hash would invalidate the cache on a typo fix in a comment;
# a package version would only be right if it were bumped with the same
# discipline, one indirection further away. If in doubt, bump it -- the cost
# is one re-render, and the cost of not bumping it is shipping a stale master.
CACHE_EPOCH = 1


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


def _safe_json_default(obj: object) -> str:
    """Convert objects that can safely be part of a cache key.

    json.dumps calls this for any value it cannot serialize natively,
    at any depth (including nested in lists/dicts). Only primitives, lists,
    dicts, and Path objects are deterministic and safe to cache. Anything
    else raises TypeError.
    """
    if isinstance(obj, Path):
        return str(obj)
    # Reject sets, frozensets, arbitrary objects, and anything else
    raise TypeError(
        f"payload_digest cannot serialize {type(obj).__name__} objects "
        f"(found {obj!r}); pass only primitives, lists, dicts, and Paths"
    )


def payload_digest(*parts: object) -> str:
    """SHA-256 over a JSON rendering of the parts, in the order given.

    Accepts only deterministic types: primitives, lists, dicts, and pathlib.Path.
    Raises TypeError if any part contains a set, frozenset, or unrecognized type
    at any nesting depth.
    """
    blob = json.dumps(
        parts, sort_keys=True, default=_safe_json_default, separators=(",", ":")
    )
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
