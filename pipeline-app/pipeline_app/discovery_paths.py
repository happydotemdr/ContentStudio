"""Shared filesystem-path helpers for the discovery engine (Tasks 6-13).
Ported from download_brandintel.py's slugify (that script is left unmodified
-- see the design spec's "Relationship to the existing manual script")."""
from __future__ import annotations

import hashlib
import html
import re
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

WINDOWS_RESERVED = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}
)


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

    B-62: slugify()'s \\w preserves Windows reserved device names --
    con/prn/aux/nul/com1..com9/lpt1..lpt9 -- which cannot exist as directory
    names on Windows; mkdir fails on every run and records an opaque OS
    error. It also collapses any all-punctuation handle to the fixed
    fallback 'untitled', so two such handles would collide. Both cases get a
    short sha1-of-handle suffix appended here to disambiguate. The audit's
    other proposal -- also reject reserved names at registration with a 400
    -- is deliberately NOT implemented: disambiguating makes the handle work,
    so a 400 would refuse a registration that is now perfectly serviceable.
    The two are alternatives; this is the better one.
    """
    slug = slugify(handle.lstrip("@"))
    if slug in WINDOWS_RESERVED or slug == "untitled":
        slug = f"{slug}-{hashlib.sha1(handle.encode('utf-8')).hexdigest()[:8]}"
    return slug


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


class SlugCollisionError(Exception):
    """Raised by assert_no_slug_collision when `handle` would share a directory
    with an already-registered handle. str(exc) is the full operator-facing
    message -- callers should not construct their own text on top of it."""


def assert_no_slug_collision(handle: str, existing_handles: Iterable[str], platform: str = "") -> None:
    """Raise SlugCollisionError if `handle` would collide (see
    find_slug_collision); otherwise return None.

    B-63: find_slug_collision was called from exactly one place -- the web
    form's add_handle route. That left every other write path free to
    introduce the exact same collision: migrate_handles_from_manifest.py
    (P10) writes through db.upsert_handle_from_migration (P1), which enforces
    only UNIQUE(platform, handle) and has no idea handle_slug() can map two
    distinct strings onto one directory. This function is the one gate both
    should call -- P8 owns discovery_paths.py but cannot reach db.py or
    migrate_handles_from_manifest.py, so this publishes the check for P1 and
    P10 to adopt rather than implementing it a second time in each of their
    files. Until they do, a migration-introduced collision is caught instead
    by the runtime detector: discovery_engine._warn_on_directory_collisions
    records a 'discovery.slug_collision' event on every run, which is a
    durable, queryable record -- not the stderr-only print that made B-42
    invisible.
    """
    clash = find_slug_collision(handle, existing_handles)
    if clash is not None:
        raise SlugCollisionError(
            f"handle shares a directory with an existing one: {platform}/{handle} and "
            f"{platform}/{clash} both resolve to "
            f"output/brand-intel/{platform}/{handle_slug(handle)}. They would be "
            f"billed separately every run while writing to one directory, and "
            f"whichever ran second would read the other's files and report "
            f"'no_new_content'. Register one, or use handles differing by more "
            f"than punctuation or capitalization."
        )


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
