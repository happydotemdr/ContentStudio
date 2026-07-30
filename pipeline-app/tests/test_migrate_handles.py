import json
from pathlib import Path

import pytest

from pipeline_app import db
from scripts.migrate_handles_from_manifest import derive_cohort, migrate


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


@pytest.mark.parametrize("note,handle,expected", [
    ("guru channel (manual-seed)", "@Romayroh", "guru"),
    ("shorts specialist (exemplar shorts); added 2026-07-23", "@JennyHoyos", "shorts-specialist"),
    ("Midjourney prompting/features/styles (image+video); added 2026-07-23", "@FutureTechPilot", "midjourney-source"),
    ("shorts/algorithm teaching; added 2026-07-23", "@vidIQ", "guru"),
    ("small-channel tactics + packaging teaching; added 2026-07-23", "@nicknimmin", "guru"),
    ("monetization + packaging teaching; added 2026-07-23", "@robertoblake", "guru"),
    ("app-seeded; Big Think channel filtered to Adam Grant videos", "@bigthink", "general-interest"),
    ("app-seeded", "adamgrant.bsky.social", "general-interest"),
])
def test_derive_cohort(note, handle, expected):
    assert derive_cohort(note, handle) == expected


def test_migrate_seeds_all_16_handles_as_validated(conn, tmp_path):
    manifest_path = tmp_path / "brand_sources.json"
    manifest_path.write_text(json.dumps({
        "youtube": [
            {"handle": "@Romayroh", "display_name": "Romayroh", "keyword_filter": None, "note": "guru channel"},
            {"handle": "@JennyHoyos", "display_name": "Jenny Hoyos", "keyword_filter": None, "note": "shorts specialist"},
        ],
        "bluesky": [
            {"handle": "adamgrant.bsky.social", "display_name": "Adam Grant", "note": "app-seeded"},
        ],
        "rss": [],
    }), encoding="utf-8")
    count = migrate(conn, manifest_path, now="2026-07-30T00:00:00Z")
    assert count == 3
    rows = db.list_handles(conn)
    assert len(rows) == 3
    romayroh = db.get_handle_by_platform_and_handle(conn, "youtube", "@Romayroh")
    assert romayroh["status"] == "validated"
    assert romayroh["included"] == 1
    assert romayroh["cohort"] == "guru"
    bluesky_row = db.get_handle_by_platform_and_handle(conn, "bluesky", "adamgrant.bsky.social")
    assert bluesky_row["cohort"] == "general-interest"


def test_migrate_is_idempotent(conn, tmp_path):
    manifest_path = tmp_path / "brand_sources.json"
    manifest_path.write_text(json.dumps({
        "youtube": [{"handle": "@a", "display_name": "A", "keyword_filter": None, "note": "guru channel"}],
        "bluesky": [], "rss": [],
    }), encoding="utf-8")
    migrate(conn, manifest_path, now="2026-07-30T00:00:00Z")
    handle_row = db.get_handle_by_platform_and_handle(conn, "youtube", "@a")
    db.set_handle_status(conn, handle_row["id"], "invalid")  # simulate manual edit
    count = migrate(conn, manifest_path, now="2026-07-30T01:00:00Z")
    assert count == 1
    assert db.get_handle_by_platform_and_handle(conn, "youtube", "@a")["status"] == "invalid"
