import json
from pathlib import Path

import pytest

from pipeline_app import db
from scripts import migrate_handles_from_manifest as mig
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


def _manifest(tmp_path: Path, youtube: list[dict]) -> Path:
    path = tmp_path / "brand_sources.json"
    payload = {"youtube": youtube, **{p: [] for p in mig.PLATFORMS if p != "youtube"}, "rss": []}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_migrate_skips_a_handle_colliding_with_one_already_registered(conn, tmp_path, capsys):
    """slugify strips periods, so seeding 'john.doe.5' next to a registered
    'johndoe5' would put two billed handles in one directory."""
    db.create_handle(conn, "youtube", "johndoe5", "B", "guru", None, "2026-07-30T00:00:00Z")
    manifest_path = _manifest(tmp_path, [
        {"handle": "john.doe.5", "display_name": "A", "keyword_filter": None, "note": "guru channel"},
    ])

    count = migrate(conn, manifest_path, now="2026-07-30T00:00:00Z")

    assert count == 0
    assert db.get_handle_by_platform_and_handle(conn, "youtube", "john.doe.5") is None
    err = capsys.readouterr().err
    assert "john.doe.5" in err
    assert "johndoe5" in err


def test_migrate_skips_a_collision_between_two_manifest_entries(conn, tmp_path):
    """The check must see rows inserted earlier in this same run, not just rows
    that predate it."""
    manifest_path = _manifest(tmp_path, [
        {"handle": "john.doe.5", "display_name": "A", "keyword_filter": None, "note": "guru channel"},
        {"handle": "johndoe5", "display_name": "B", "keyword_filter": None, "note": "guru channel"},
    ])

    count = migrate(conn, manifest_path, now="2026-07-30T00:00:00Z")

    assert count == 1
    assert db.get_handle_by_platform_and_handle(conn, "youtube", "john.doe.5") is not None
    assert db.get_handle_by_platform_and_handle(conn, "youtube", "johndoe5") is None


def test_migrate_seeds_the_rest_despite_one_collision(conn, tmp_path):
    """One bad manifest row must not abort the whole import."""
    db.create_handle(conn, "youtube", "johndoe5", "B", "guru", None, "2026-07-30T00:00:00Z")
    manifest_path = _manifest(tmp_path, [
        {"handle": "john.doe.5", "display_name": "A", "keyword_filter": None, "note": "guru channel"},
        {"handle": "@Romayroh", "display_name": "R", "keyword_filter": None, "note": "guru channel"},
    ])

    count = migrate(conn, manifest_path, now="2026-07-30T00:00:00Z")

    assert count == 1
    assert db.get_handle_by_platform_and_handle(conn, "youtube", "@Romayroh") is not None


from run_discovery_cron import build_adapters
from scripts.migrate_handles_from_manifest import PLATFORMS


def test_platforms_tuple_matches_the_adapter_registry():
    """The manifest's platform keys ARE the trackable platforms. If an adapter
    is added or renamed and this tuple is not updated, that platform has no
    declarative roster and silently becomes untrackable (B-70)."""
    assert sorted(PLATFORMS) == sorted(build_adapters())
    assert len(PLATFORMS) == 7


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "brand_sources.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _empty_manifest(tmp_path: Path) -> Path:
    return _write(tmp_path, {"creators": {}, **{p: [] for p in mig.PLATFORMS}, "rss": []})


def test_unknown_platform_key_raises_manifest_error(conn, tmp_path):
    """FAULT: a typo'd platform key must fail, not be skipped (B-71)."""
    path = _write(tmp_path, {
        "creators": {"a": {"display_name": "A"}},
        **{p: [] for p in mig.PLATFORMS},
        "rss": [],
        "instgram": [{"handle": "@a", "creator": "a", "cohort": "guru", "included": True}],
    })
    with pytest.raises(mig.ManifestError) as excinfo:
        mig.migrate(conn, path, now="2026-08-08T00:00:00+00:00")
    assert "instgram" in str(excinfo.value)


def test_unknown_key_is_distinguishable_from_an_empty_manifest(conn, tmp_path):
    """DISTINGUISHABILITY: 'we track nobody' and 'your key was dropped' must
    not produce the same outcome. Before the fix both returned 0."""
    good = mig.migrate(conn, _empty_manifest(tmp_path), now="2026-08-08T00:00:00+00:00")
    assert good.seeded == 0 and good.errors == []

    bad_path = _write(tmp_path, {"creators": {}, **{p: [] for p in mig.PLATFORMS},
                                 "rss": [], "instgram": []})
    with pytest.raises(mig.ManifestError):
        mig.migrate(conn, bad_path, now="2026-08-08T00:00:00+00:00")


def test_main_exits_nonzero_and_records_an_event_for_an_unknown_key(tmp_path, capsys):
    """SURFACING: non-zero exit + an `events` row, not just a print (D-02)."""
    db_path = tmp_path / "pipeline.db"
    bad_path = _write(tmp_path, {"creators": {}, **{p: [] for p in mig.PLATFORMS},
                                 "rss": [], "instgram": []})
    rc = mig.main(["--manifest", str(bad_path), "--db-path", str(db_path)])
    assert rc == 2
    conn = db.get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM events WHERE kind = 'roster.manifest_invalid'").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["severity"] == "error"
    assert "instgram" in rows[0]["message"]
