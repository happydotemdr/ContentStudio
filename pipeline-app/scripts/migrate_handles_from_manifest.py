"""One-off: seed pipeline-app's `handles` table from the repo-root
manifests/brand_sources.json. Read-only against the JSON file and against
output/brand-intel/ -- writes only new `handles` rows. Safe to re-run: uses
INSERT OR IGNORE (see db.upsert_handle_from_migration), so a manual edit made
in the UI after the first run is never overwritten.

Usage: python scripts/migrate_handles_from_manifest.py
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline_app import db, obs  # noqa: E402
from pipeline_app.discovery_paths import find_slug_collision, handle_slug  # noqa: E402


# The trackable platforms, in registry order. Pinned to
# run_discovery_cron.build_adapters() by
# test_platforms_tuple_matches_the_adapter_registry, and to P1's
# handles.platform CHECK constraint. `rss` is deliberately NOT here: it has a
# manifest key and a download_brandintel.py branch but no adapter (B-79).
PLATFORMS: tuple[str, ...] = (
    "youtube", "bluesky", "instagram",
    "linkedin-profile", "linkedin-company", "facebook", "x",
)

DOWNLOADER_ONLY_KEYS: frozenset[str] = frozenset({"rss"})
NON_ROSTER_KEYS: frozenset[str] = frozenset({"_comment", "creators"})
KNOWN_KEYS: frozenset[str] = frozenset(PLATFORMS) | DOWNLOADER_ONLY_KEYS | NON_ROSTER_KEYS


class ManifestError(Exception):
    """The manifest is structurally wrong. Always fatal: a roster we cannot
    fully read is worse than no roster, because the operator believes it."""


@dataclass
class MigrateResult:
    seeded: int = 0
    updated: int = 0
    skipped: int = 0
    drift: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def validate_keys(data: dict) -> None:
    unknown = sorted(set(data) - KNOWN_KEYS)
    if unknown:
        raise ManifestError(
            f"unrecognized top-level key(s) {unknown} in the manifest. "
            f"Recognized platform keys are {list(PLATFORMS)}; `rss` is "
            f"downloader-only; `creators` and `_comment` are metadata. "
            f"A platform key that is not in the adapter registry has no "
            f"adapter and would be tracked by nothing."
        )
    missing = [p for p in PLATFORMS if p not in data]
    if missing:
        raise ManifestError(
            f"missing platform key(s) {missing}. Every adapter-registry "
            f"platform must have a key -- use [] to declare 'we track nobody "
            f"here', so a gap is stated rather than absent."
        )


def derive_cohort(note: str, handle: str) -> str:
    note_lower = (note or "").lower()
    if "shorts specialist" in note_lower:
        return "shorts-specialist"
    if "midjourney" in note_lower:
        return "midjourney-source"
    if "guru channel" in note_lower:
        return "guru"
    # vidIQ / nicknimmin / robertoblake: algorithm/packaging/monetization
    # teaching notes with no "guru channel" phrase, but the same
    # creator-education shape as the guru entries -- not a shorts exemplar,
    # not a Midjourney source.
    if any(kw in note_lower for kw in ("teaching", "tactics", "monetization")):
        return "guru"
    return "general-interest"


def upsert_creators(conn: sqlite3.Connection, creators: dict) -> dict[str, int]:
    """Stub -- T10 replaces this body with the real creators upsert. Returns
    an empty map, which is safe because T3's own `_seed_entry` does not yet
    consult `creator_ids` for anything (that check is T10's)."""
    return {}


def find_drift(conn: sqlite3.Connection, data: dict) -> list[tuple[str, str]]:
    """Stub -- T9 replaces this body with the real drift detection. Returns
    no drift, which is safe because T3's own test never reads `result.drift`."""
    return []


def _seed_entry(conn: sqlite3.Connection, platform: str, entry: dict, creators: dict,
                 creator_ids: dict[str, int], now: str, result: MigrateResult) -> None:
    """Upsert one handle, unless it would share an output directory with one
    already registered. Mutates `result` in place rather than returning a bare
    bool, so the caller's loop can accumulate seeded/skipped/errors across
    every platform.

    Skips rather than aborting: one bad manifest row must not stop the rest of
    the import. Queried fresh each call so a collision between two entries in
    the same manifest is caught too, not just against pre-existing rows.
    """
    handle = entry.get("handle")
    if not handle:
        return
    display_name = entry.get("display_name")
    if display_name is None:
        creator_key = entry.get("creator")
        if creator_key is not None:
            display_name = (creators.get(creator_key) or {}).get("display_name")
    cohort = entry.get("cohort")
    if cohort is None:
        cohort = derive_cohort(entry.get("note", ""), handle)
    keyword_filter = entry.get("keyword_filter")

    clash = find_slug_collision(
        handle, [row["handle"] for row in db.list_platform_handles(conn, platform)]
    )
    if clash is not None:
        message = (f"skipping {platform}/{handle}: it shares the output directory "
                   f"output/brand-intel/{platform}/{handle_slug(handle)} with "
                   f"already-registered {platform}/{clash}, so both would be billed "
                   f"while writing to the same files")
        print(f"  !! {message}", file=sys.stderr)
        result.skipped += 1
        result.errors.append(message)
        return
    db.upsert_handle_from_migration(
        conn, platform, handle, display_name, cohort, keyword_filter,
        status="validated", included=True, added_at=now,
    )
    result.seeded += 1


def migrate(conn: sqlite3.Connection, manifest_path: Path, now: str) -> MigrateResult:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_keys(data)
    creators = data.get("creators") or {}
    creator_ids = upsert_creators(conn, creators)          # T10
    result = MigrateResult()
    for platform in PLATFORMS:
        for entry in data[platform]:
            _seed_entry(conn, platform, entry, creators, creator_ids, now, result)
    result.drift = find_drift(conn, data)                  # T9
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default=None, help="path to brand_sources.json (default: repo-root manifests/)")
    ap.add_argument("--db-path", default=None, help="path to pipeline.db (default: pipeline-app/pipeline.db)")
    args = ap.parse_args(argv)

    pipeline_app_root = Path(__file__).resolve().parents[1]
    repo_root = pipeline_app_root.parent
    manifest_path = Path(args.manifest) if args.manifest else repo_root / "manifests" / "brand_sources.json"
    db_path = Path(args.db_path) if args.db_path else pipeline_app_root / "pipeline.db"

    schema_path = pipeline_app_root / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    conn = db.get_connection(db_path)
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    try:
        result = migrate(conn, manifest_path, now)
    except ManifestError as exc:
        obs.log("roster.manifest_invalid", level="error", manifest=str(manifest_path),
                error=str(exc))
        obs.record_event(conn, kind="roster.manifest_invalid", severity="error",
                         source="migrate_handles_from_manifest",
                         message=str(exc), detail={"manifest": str(manifest_path)})
        print(f"! {exc}", file=sys.stderr)
        conn.close()
        return 2
    conn.close()
    print(f"migrated {result.seeded} handles from {manifest_path} into {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
