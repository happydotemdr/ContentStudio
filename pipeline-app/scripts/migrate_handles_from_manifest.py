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


def migrate(conn: sqlite3.Connection, manifest_path: Path, now: str) -> int:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    count = 0
    for entry in data.get("youtube", []):
        handle = entry.get("handle")
        if not handle:
            continue
        note = entry.get("note", "")
        db.upsert_handle_from_migration(
            conn, "youtube", handle, entry.get("display_name"),
            derive_cohort(note, handle), entry.get("keyword_filter"),
            status="validated", included=True, added_at=now,
        )
        count += 1
    for entry in data.get("bluesky", []):
        handle = entry.get("handle")
        if not handle:
            continue
        note = entry.get("note", "")
        db.upsert_handle_from_migration(
            conn, "bluesky", handle, entry.get("display_name"),
            derive_cohort(note, handle), None,
            status="validated", included=True, added_at=now,
        )
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
