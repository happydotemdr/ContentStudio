"""One-time application of ContentStudio's initial brand tagging to the 15
discovery handles that predate the handle_brands table. See
docs/superpowers/specs/2026-08-15-brand-scoped-discovery-email-design.md for
the RaisingGoodSports/Freedom2BeU classification rationale.

Idempotent, but NOT safe to re-run casually once Task 6's /discovery/handles UI
has shipped: set_handle_brands replaces a handle's tag set, so re-running this
script always resets these 15 handles' tags back to the BRAND_TAGS mapping
below, silently discarding any manual retagging an operator has done since via
that UI. It reproduces the same end state every time -- that consistency is
exactly what makes it destructive to an operator's later changes. Treat this
as a one-time initial-application script, not something to run again after
the handles page exists.

Usage: python tools/tag_handle_brands_2026_08.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline_app import db  # noqa: E402

# (platform, handle) -> brand tags. Every entry carries "guru": these are the
# pipeline's original inspiration-roster handles, and this tagging must not
# remove them from that section -- it only adds a more specific brand on top
# where one applies.
BRAND_TAGS: dict[tuple[str, str], list[str]] = {
    ("instagram", "aspenprojectplay"): ["guru", "raisinggoodsports"],
    ("instagram", "ctgprojecthq"): ["guru", "raisinggoodsports"],
    ("linkedin-company", "positive-coaching-alliance"): ["guru", "raisinggoodsports"],
    ("linkedin-profile", "coachjohnosullivan"): ["guru", "raisinggoodsports"],
    ("instagram", "drbeckyatgoodinside"): ["guru", "freedom2beu"],
    ("linkedin-profile", "drbecky"): ["guru", "freedom2beu"],
    ("linkedin-profile", "danielpink"): ["guru", "freedom2beu"],
    ("linkedin-profile", "nireyal"): ["guru", "freedom2beu"],
    ("youtube", "@ImpactParents"): ["guru", "freedom2beu"],
    ("youtube", "@danielpinktv"): ["guru", "freedom2beu"],
    ("youtube", "@drdansiegel"): ["guru", "freedom2beu"],
    ("youtube", "@goodinside"): ["guru", "freedom2beu"],
    ("youtube", "@nirandfar"): ["guru", "freedom2beu"],
    ("youtube", "@positive-intelligence"): ["guru", "freedom2beu"],
    ("youtube", "@NextBigIdeaClub"): ["guru"],
}


def apply(conn) -> tuple[list[str], list[str]]:
    """Apply BRAND_TAGS to `conn`. Returns (missing, untagged):
    `missing` is every BRAND_TAGS entry with no matching DB row (skipped);
    `untagged` is every INCLUDED DB handle BRAND_TAGS does not mention (left
    as-is). Scoped to included_only=True: an excluded handle produces no
    items in any digest run, so flagging it as "untagged" would false-alarm
    on ordinary roster housekeeping rather than a real coverage gap (Low
    finding #6, pre-execution review)."""
    missing: list[str] = []
    for (platform, handle), brands in BRAND_TAGS.items():
        row = db.get_handle_by_platform_and_handle(conn, platform, handle)
        if row is None:
            missing.append(f"{platform}/{handle}")
            continue
        db.set_handle_brands(conn, row["id"], sorted(set(brands)))
        print(f"  {platform}/{handle}: {', '.join(sorted(set(brands)))}")

    untagged = [
        f"{r['platform']}/{r['handle']}" for r in db.list_handles(conn, included_only=True)
        if (r["platform"], r["handle"]) not in BRAND_TAGS
    ]
    return missing, untagged


def main() -> int:
    pipeline_app_root = Path(__file__).resolve().parents[1]
    db_path = pipeline_app_root / "pipeline.db"
    schema_path = pipeline_app_root / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    conn = db.get_connection(db_path)

    missing, untagged = apply(conn)
    conn.close()

    if missing:
        print(f"\n! not found in the DB (skipped): {', '.join(missing)}", file=sys.stderr)
    if untagged:
        print(f"\n?? handle(s) in the DB not covered by this script: {', '.join(untagged)}",
              file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
