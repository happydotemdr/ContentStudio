"""Pure naming/path functions -- no filesystem or DB access anywhere in this
module except long_path's Path.resolve() call (which touches the filesystem
to resolve cwd/symlinks but never reads or writes file content). Gate 2
(Task 12) and worker.py (Task 15) are the callers."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

FORBIDDEN_CHARS = '<>:"/\\|?*'
_FORBIDDEN_RE = re.compile("[" + re.escape(FORBIDDEN_CHARS) + "]")
_WHITESPACE_RUN_RE = re.compile(r"\s+")


def sanitize_component(name: str) -> str:
    """Strips only what Windows mechanically forbids -- not a slugify. The 9
    forbidden characters, trailing spaces/periods, and collapsed whitespace
    runs (spec §6)."""
    stripped = _FORBIDDEN_RE.sub("", name)
    stripped = _WHITESPACE_RUN_RE.sub(" ", stripped)
    return stripped.rstrip(" .")


def _hash8(source_rel_path: str) -> str:
    return hashlib.sha256(source_rel_path.encode("utf-8")).hexdigest()[:8]


def _version_suffix(version: int) -> str:
    return "" if version == 1 else f".v{version}"


def _stem_filename(source_rel_path: str, version: int) -> str:
    filename = source_rel_path.rsplit("/", 1)[-1]
    return f"{sanitize_component(filename)}{_version_suffix(version)}.md"


_SEGMENT_SHORTEN_HEAD = 12
_STEM_SHORTEN_HEAD = 40


def _shorten_if_it_helps(segment: str, digest: str, head: int) -> str:
    """Returns a truncated-head + hash form ONLY if that form is actually
    shorter than the segment as given -- a short segment (e.g. a 1-char
    folder name, or a filename stem under 40 chars) truncated-then-hashed is
    routinely LONGER than the original, since the hash suffix itself is 9
    characters ("~" + 8 hex digits). Applying the shortened form
    unconditionally was the original bug: it grew exactly the paths spec §6
    calls "the common case here, not an edge case" instead of shrinking
    them."""
    shortened = f"{segment[:head]}~{digest}"
    return shortened if len(shortened) < len(segment) else segment


def build_dest_rel_path(source_rel_path: str, version: int, cfg, prefix_len: int = 0) -> str:
    """Mirrors the source tree 1:1 under converted/, preserving the full
    original extension as part of the stem (spec §6) -- Name.docx becomes
    Name.docx.md, never Name.md, so a same-stem .pdf and .docx never collide
    on write. Shortens the deepest segments with a deterministic hash suffix
    if the full path would exceed cfg.long_path_threshold_chars, accounting
    for prefix_len (the absolute-path prefix the caller will prepend)."""
    budget = cfg.long_path_threshold_chars - prefix_len
    parts = source_rel_path.split("/")
    folders = [sanitize_component(p) for p in parts[:-1]]
    filename = _stem_filename(source_rel_path, version)
    candidate = "/".join(folders + [filename])

    if len(candidate) <= budget:
        return candidate

    digest = _hash8(source_rel_path)

    stem, sep, ext_chain = filename.partition(".")
    shortened_stem = _shorten_if_it_helps(stem, digest, _STEM_SHORTEN_HEAD)
    short_filename = f"{shortened_stem}{sep}{ext_chain}" if sep else shortened_stem
    candidate = "/".join(folders + [short_filename])

    if len(candidate) <= budget:
        return candidate

    # Still too long: shorten folder segments, deepest first, skipping any
    # segment a shortened form would not actually make smaller. The \\?\-
    # prefixed I/O in lock.py/worker.py (Task 13/15) is the defense-in-depth
    # backstop for the residual case where nothing left to shorten still
    # doesn't fit (spec §6).
    idx = len(folders) - 1
    while len(candidate) > budget and idx >= 0:
        shortened = _shorten_if_it_helps(folders[idx], digest, _SEGMENT_SHORTEN_HEAD)
        if shortened != folders[idx]:
            folders[idx] = shortened
            candidate = "/".join(folders + [short_filename])
        idx -= 1

    return candidate


def resolve_collision(dest_rel_path: str, is_taken) -> tuple[str, bool]:
    """If dest_rel_path is already occupied by a DIFFERENT source file's
    output, appends a short hash suffix before the final .md and reports the
    collision so the caller can log an events row (spec §6) -- collisions are
    resolved, never left to fail indefinitely, but never silent either."""
    if not is_taken(dest_rel_path):
        return dest_rel_path, False
    digest = hashlib.sha256(dest_rel_path.encode("utf-8")).hexdigest()[:8]
    stem, _, suffix = dest_rel_path.rpartition(".md")
    candidate = f"{stem}~{digest}.md"
    return candidate, True


def long_path(path) -> str:
    """Windows' documented mechanism for addressing paths beyond the
    ~260-char MAX_PATH default without any system-wide policy change: an
    ALREADY-ABSOLUTE path prefixed with \\\\?\\. This is the defense-in-depth
    backstop spec §6 describes for the residual case where naming.py's own
    shortening still couldn't bring a path under
    cfg.long_path_threshold_chars -- Python's open()/os-level file I/O on
    Windows honors this prefix (it maps directly to CreateFileW), so it's
    applied at the one call site that matters most: worker.py's final write
    of the locked output file (Task 15). Deliberately NOT applied to the
    icacls subprocess calls in lock.py -- external command-line tools doing
    their own path parsing are not guaranteed to honor \\\\?\\ the same way,
    and getting that wrong risks a worse failure (icacls misinterpreting the
    prefix as part of the filename) than the rare long-path case it would be
    trying to guard against. A no-op on non-Windows, or for a path that's
    already \\\\?\\-prefixed. Checks the incoming string for that prefix
    BEFORE calling Path.resolve() on it -- feeding an already-prefixed
    string back into pathlib's resolver is its own source of inconsistent
    behavior across Python versions, so the idempotent case short-circuits
    before ever reaching that call."""
    text = str(path)
    if text.startswith("\\\\?\\"):
        return text
    resolved = str(Path(path).resolve())
    if os.name != "nt" or resolved.startswith("\\\\?\\"):
        return resolved
    return "\\\\?\\" + resolved
