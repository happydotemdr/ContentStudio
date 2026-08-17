"""Shared filesystem-path helpers for the discovery engine (Tasks 6-13).
Ported from download_brandintel.py's slugify (that script is left unmodified
-- see the design spec's "Relationship to the existing manual script")."""
from __future__ import annotations

import html
import re
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path


def slugify(value: str, maxlen: int = 80) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE).strip().lower()
    value = re.sub(r"[\s_-]+", "-", value)
    return (value[:maxlen].rstrip("-")) or "untitled"


def handle_slug(handle: str) -> str:
    """The single directory-name component for a tracked handle.

    Exists so a collision check and the real path can never drift apart: both
    call this, so a guard cannot compute a slug that differs from the one the
    engine writes to. See find_slug_collision for what that guard is for.

    Deliberately lossy, and deliberately NOT fixed. slugify() strips periods
    and lowercases, so 'john.doe.5' and 'johndoe5' both land here as
    'johndoe5'. That mapping is load-bearing: directories written under it
    already hold captured content (every Bluesky handle contains periods --
    'adamgrant.bsky.social' is on disk as 'adamgrantbskysocial'). Making the
    slug collision-preserving would repoint those handles at fresh
    directories, on_disk_ids() would return an empty set, and the engine would
    re-download and re-pay for each account's whole back-catalogue. So the
    collision is fenced off at registration instead of being encoded away.
    """
    return slugify(handle.lstrip("@"))


def find_slug_collision(handle: str, existing_handles: Iterable[str]) -> str | None:
    """The first handle in existing_handles that would share a directory with
    `handle` despite being a different string, or None.

    Two handles colliding here are billed separately on every run while
    writing to one directory, so whichever runs second reads the first's files
    via on_disk_ids(), finds them already captured, and reports the healthy
    'no_new_content'. Paid for, captured nothing, looks like a quiet day.

    An exactly-equal handle is not reported: that is a plain duplicate, which
    UNIQUE(platform, handle) and the route's own check already reject with a
    clearer message. Compare within one platform only -- directories are
    namespaced by platform, so facebook/nasa and instagram/nasa are distinct.
    """
    slug = handle_slug(handle)
    for existing in existing_handles:
        if existing != handle and handle_slug(existing) == slug:
            return existing
    return None


def group_slug_collisions(handles: Iterable[str]) -> dict[str, list[str]]:
    """slug -> the two-or-more distinct handles sharing it. Empty when clean.

    For reporting collisions that are already registered, which the
    registration guard cannot see because they predate it. Distinct handle
    strings only: a repeated identical string is one account, not two
    accounts sharing a directory.
    """
    by_slug: dict[str, list[str]] = defaultdict(list)
    for handle in handles:
        bucket = by_slug[handle_slug(handle)]
        if handle not in bucket:
            bucket.append(handle)
    return {slug: found for slug, found in by_slug.items() if len(found) > 1}


def handle_dir(repo_root: Path, platform: str, handle: str) -> Path:
    return repo_root / "output" / "brand-intel" / platform / handle_slug(handle)


def run_record_path(repo_root: Path, run_id: str) -> Path:
    return repo_root / "output" / "discovery-runs" / f"{run_id}.md"


def spawn_log_path(repo_root: Path, spawn_id: str) -> Path:
    """Where a spawned cron child's captured stdout/stderr live (B-61/E-11).

    Named by spawn_id rather than PID: PIDs are reused by the OS, so naming
    by PID would let a later, unrelated child silently overwrite an earlier
    dead child's diagnostic output."""
    return repo_root / "output" / "discovery-runs" / "spawn-logs" / f"{spawn_id}.log"


def run_owner_path(repo_root: Path, run_row_id: int) -> Path:
    """Sidecar recording which OS process owns a 'running' row. Lives on disk
    rather than on the row because discovery_runs' schema belongs to another
    package; the reclaim sweep reads it to answer "is that process actually
    gone?" instead of trusting a heartbeat that a sleeping machine freezes."""
    return repo_root / "output" / "discovery-runs" / ".owners" / f"{run_row_id}.json"
