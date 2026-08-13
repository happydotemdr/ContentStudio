"""roster sync: seed and update pipeline-app's `handles` table from the
repo-root manifests/brand_sources.json. Read-only against the JSON file and
against output/brand-intel/. Safe to re-run: the manifest is authoritative for
manifest-owned columns (display_name, cohort, keyword_filter, included,
creator_id), which move to match the manifest on every sync; the DB is
authoritative for run-owned columns (status, validated_at,
last_seen_published_at), which only a real discovery run writes and this
script never touches.

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
    drift: list[tuple[str, str]] = field(default_factory=list)
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
    """Legacy fallback only. Every shipped manifest entry carries an explicit
    `cohort`; this exists so a hand-written third-party manifest without one
    still imports (B-77)."""
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
    """slug -> creators.id, inserting or updating each declared creator."""
    ids: dict[str, int] = {}
    for slug, spec in creators.items():
        display_name = (spec or {}).get("display_name") or slug
        conn.execute(
            "INSERT INTO creators (slug, display_name) VALUES (?, ?) "
            "ON CONFLICT(slug) DO UPDATE SET display_name = excluded.display_name",
            (slug, display_name),
        )
        ids[slug] = conn.execute(
            "SELECT id FROM creators WHERE slug = ?", (slug,)).fetchone()["id"]
    conn.commit()
    return ids


_MANIFEST_OWNED = ("display_name", "cohort", "keyword_filter", "included", "creator_id")


def upsert_handle(conn: sqlite3.Connection, platform: str, handle: str, *, display_name,
                   cohort: str, keyword_filter, included: bool, creator_id, added_at: str) -> str:
    """Insert or update ONE handle. Returns 'inserted' | 'updated' | 'unchanged'.

    Only manifest-owned columns are written. status / validated_at /
    last_seen_published_at are owned by the discovery run and are never touched
    here -- a re-seed must not un-learn what a real fetch discovered (B-75/B-76).
    """
    before = db.get_handle_by_platform_and_handle(conn, platform, handle)
    conn.execute(
        "INSERT INTO handles (platform, handle, display_name, cohort, keyword_filter, "
        "                     included, status, added_at, creator_id) "
        "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?) "
        "ON CONFLICT(platform, handle) DO UPDATE SET "
        "  display_name = excluded.display_name, "
        "  cohort       = excluded.cohort, "
        "  keyword_filter = excluded.keyword_filter, "
        "  included     = excluded.included, "
        "  creator_id   = excluded.creator_id",
        (platform, handle, display_name, cohort, keyword_filter,
         1 if included else 0, added_at, creator_id),
    )
    conn.commit()
    after = db.get_handle_by_platform_and_handle(conn, platform, handle)
    if before is None:
        return "inserted"
    return "unchanged" if all(before[c] == after[c] for c in _MANIFEST_OWNED) else "updated"


def find_drift(conn: sqlite3.Connection, data: dict) -> list[tuple[str, str]]:
    """(platform, handle) rows in the DB that the manifest does not declare.

    Reported, never deleted: a hand-added handle is a legitimate way to work,
    and the point is that the divergence stops being invisible (B-76).
    """
    declared = {(p, e["handle"]) for p in PLATFORMS for e in data[p] if e.get("handle")}
    return sorted(
        (row["platform"], row["handle"])
        for row in db.list_handles(conn)
        if (row["platform"], row["handle"]) not in declared
    )


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
    cohort = entry.get("cohort") or derive_cohort(entry.get("note", ""), handle)
    keyword_filter = entry.get("keyword_filter")
    included = bool(entry.get("included", True))

    slug = entry.get("creator")
    if slug is not None and slug not in creator_ids:
        raise ManifestError(
            f"{platform}/{entry.get('handle')} names creator {slug!r}, which is not "
            f"in the manifest's `creators` block. Every handle must belong to a "
            f"declared creator -- that slug is the only cross-platform identity."
        )

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
    creator_id = creator_ids.get(entry.get("creator"))
    outcome = upsert_handle(
        conn, platform, handle, display_name=display_name, cohort=cohort,
        keyword_filter=keyword_filter, included=included, creator_id=creator_id,
        added_at=now,
    )
    if outcome == "inserted":
        result.seeded += 1
    elif outcome == "updated":
        result.updated += 1


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


@dataclass(frozen=True)
class Cell:
    state: str                     # tracked | declared-excluded | not tracked | UNANSWERABLE
    handle: str | None = None


@dataclass
class CoverageReport:
    creators: dict[str, str]                    # slug -> display_name
    platforms: tuple[str, ...]
    cells: dict[tuple[str, str], Cell]

    def cell(self, creator: str, platform: str) -> Cell:
        return self.cells[(creator, platform)]

    def count(self, state: str) -> int:
        return sum(1 for c in self.cells.values() if c.state == state)


def build_coverage_report(data: dict) -> CoverageReport:
    """The creator x platform matrix, computed from the manifest ALONE.

    Deliberately does not read the database: the operator's question has to be
    answerable from a fresh checkout, in a diff, on another machine. A cell is
    UNANSWERABLE only when the manifest carries no key for that platform at
    all -- which is exactly the B-70 state this package eliminates.
    """
    creators = {slug: (spec or {}).get("display_name") or slug
                for slug, spec in (data.get("creators") or {}).items()}
    declared: dict[tuple[str, str], dict] = {}
    for platform in PLATFORMS:
        for entry in data.get(platform) or []:
            if entry.get("creator") and entry.get("handle"):
                declared[(entry["creator"], platform)] = entry

    cells: dict[tuple[str, str], Cell] = {}
    for slug in creators:
        for platform in PLATFORMS:
            if platform not in data:
                cells[(slug, platform)] = Cell("UNANSWERABLE")
                continue
            entry = declared.get((slug, platform))
            if entry is None:
                cells[(slug, platform)] = Cell("not tracked")
            elif entry.get("included", True):
                cells[(slug, platform)] = Cell("tracked", entry["handle"])
            else:
                cells[(slug, platform)] = Cell("declared-excluded", entry["handle"])
    return CoverageReport(creators, PLATFORMS, cells)


_GLYPH = {"tracked": "YES", "declared-excluded": "off", "not tracked": "-",
          "UNANSWERABLE": "??"}


def print_coverage_report(report: CoverageReport) -> None:
    width = max((len(s) for s in report.creators), default=7) + 2
    print("creator x platform coverage (from the manifest alone)\n")
    print(" " * width + "  ".join(f"{p:<17}" for p in report.platforms))
    for slug in sorted(report.creators):
        row = "  ".join(f"{_GLYPH[report.cell(slug, p).state]:<17}" for p in report.platforms)
        print(f"{slug:<{width}}{row}")
    print("\n  YES tracked          :", report.count("tracked"))
    print("  off declared-excluded:", report.count("declared-excluded"))
    print("  -   not tracked      :", report.count("not tracked"))
    print("  ??  UNANSWERABLE :", report.count("UNANSWERABLE"))
    print("\n  `rss` is intentionally not a column: it has a manifest key and a")
    print("  download_brandintel.py branch, but no adapter, so it is not part of")
    print("  the daily discovery path.")


def _fail_manifest_error(conn: sqlite3.Connection, manifest_path: Path, exc: ManifestError) -> int:
    """Shared handler for a ManifestError raised from either the normal write
    path (migrate()) or --report's read-only path: same logging, same
    non-zero exit, regardless of which path found the bad manifest first."""
    obs.log("roster.manifest_invalid", level="error", manifest=str(manifest_path),
            error=str(exc))
    obs.record_event(conn, kind="roster.manifest_invalid", severity="error",
                     source="migrate_handles_from_manifest",
                     message=str(exc), detail={"manifest": str(manifest_path)})
    print(f"! {exc}", file=sys.stderr)
    conn.close()
    return 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default=None, help="path to brand_sources.json (default: repo-root manifests/)")
    ap.add_argument("--db-path", default=None, help="path to pipeline.db (default: pipeline-app/pipeline.db)")
    ap.add_argument("--report", action="store_true",
                     help="print the creator x platform coverage matrix computed from the "
                          "manifest alone, then exit without opening any write path")
    args = ap.parse_args(argv)

    pipeline_app_root = Path(__file__).resolve().parents[1]
    repo_root = pipeline_app_root.parent
    manifest_path = Path(args.manifest) if args.manifest else repo_root / "manifests" / "brand_sources.json"
    db_path = Path(args.db_path) if args.db_path else pipeline_app_root / "pipeline.db"

    schema_path = pipeline_app_root / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    conn = db.get_connection(db_path)

    if args.report:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        try:
            validate_keys(data)
        except ManifestError as exc:
            return _fail_manifest_error(conn, manifest_path, exc)
        conn.close()
        print_coverage_report(build_coverage_report(data))
        return 0

    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    try:
        result = migrate(conn, manifest_path, now)
    except ManifestError as exc:
        return _fail_manifest_error(conn, manifest_path, exc)
    if result.drift:
        for platform, handle in result.drift:
            print(f"  ?? drift: {platform}/{handle} is in the DB but not declared in the manifest")
        message = ("DB handles not declared in the manifest: "
                   + ", ".join(f"{platform}/{handle}" for platform, handle in result.drift))
        obs.log("roster.drift", level="warning", manifest=str(manifest_path),
                drift=result.drift)
        obs.record_event(conn, kind="roster.drift", severity="warning",
                         source="migrate_handles_from_manifest",
                         message=message, detail={"drift": result.drift})
    conn.close()
    print(f"roster sync: {manifest_path}  ->  {db_path}")
    print(f"  inserted : {result.seeded}")
    print(f"  updated  : {result.updated}")
    print(f"  skipped  : {result.skipped}")
    print(f"  drift    : {len(result.drift)}")
    if result.seeded > 0:
        print(f"  {result.seeded} handle(s) pending validation -- run a discovery validate pass to confirm each is live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
