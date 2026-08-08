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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline_app import db  # noqa: E402
from pipeline_app.discovery_paths import find_slug_collision, handle_slug  # noqa: E402


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


def _seed(conn: sqlite3.Connection, platform: str, handle: str, display_name: str | None,
          cohort: str, keyword_filter: str | None, now: str) -> bool:
    """Upsert one handle, unless it would share an output directory with one
    already registered. Returns whether it was seeded.

    Skips rather than aborting: one bad manifest row must not stop the rest of
    the import. Queried fresh each call so a collision between two entries in
    the same manifest is caught too, not just against pre-existing rows.
    """
    clash = find_slug_collision(
        handle, [row["handle"] for row in db.list_platform_handles(conn, platform)]
    )
    if clash is not None:
        print(f"  !! skipping {platform}/{handle}: it shares the output directory "
              f"output/brand-intel/{platform}/{handle_slug(handle)} with "
              f"already-registered {platform}/{clash}, so both would be billed "
              f"while writing to the same files", file=sys.stderr)
        return False
    db.upsert_handle_from_migration(
        conn, platform, handle, display_name, cohort, keyword_filter,
        status="validated", included=True, added_at=now,
    )
    return True


def migrate(conn: sqlite3.Connection, manifest_path: Path, now: str) -> int:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    count = 0
    for entry in data.get("youtube", []):
        handle = entry.get("handle")
        if not handle:
            continue
        note = entry.get("note", "")
        if _seed(conn, "youtube", handle, entry.get("display_name"),
                 derive_cohort(note, handle), entry.get("keyword_filter"), now):
            count += 1
    for entry in data.get("bluesky", []):
        handle = entry.get("handle")
        if not handle:
            continue
        note = entry.get("note", "")
        if _seed(conn, "bluesky", handle, entry.get("display_name"),
                 derive_cohort(note, handle), None, now):
            count += 1
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default=None, help="path to brand_sources.json (default: repo-root manifests/)")
    ap.add_argument("--db-path", default=None, help="path to pipeline.db (default: pipeline-app/pipeline.db)")
    args = ap.parse_args()

    pipeline_app_root = Path(__file__).resolve().parents[1]
    repo_root = pipeline_app_root.parent
    manifest_path = Path(args.manifest) if args.manifest else repo_root / "manifests" / "brand_sources.json"
    db_path = Path(args.db_path) if args.db_path else pipeline_app_root / "pipeline.db"

    schema_path = pipeline_app_root / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    conn = db.get_connection(db_path)
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    count = migrate(conn, manifest_path, now)
    conn.close()
    print(f"migrated {count} handles from {manifest_path} into {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
