import json
from pathlib import Path

import pytest

from pipeline_app import db
from scripts import migrate_handles_from_manifest as mig
from scripts.migrate_handles_from_manifest import derive_cohort, migrate


REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_MANIFEST = REPO_ROOT / "manifests" / "brand_sources.json"


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

    result = migrate(conn, manifest_path, now="2026-07-30T00:00:00Z")

    assert result.seeded == 0
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

    result = migrate(conn, manifest_path, now="2026-07-30T00:00:00Z")

    assert result.seeded == 1
    assert db.get_handle_by_platform_and_handle(conn, "youtube", "john.doe.5") is not None
    assert db.get_handle_by_platform_and_handle(conn, "youtube", "johndoe5") is None


def test_migrate_seeds_the_rest_despite_one_collision(conn, tmp_path):
    """One bad manifest row must not abort the whole import."""
    db.create_handle(conn, "youtube", "johndoe5", "B", "guru", None, "2026-07-30T00:00:00Z")
    manifest_path = _manifest(tmp_path, [
        {"handle": "john.doe.5", "display_name": "A", "keyword_filter": None, "note": "guru channel"},
        {"handle": "@Romayroh", "display_name": "R", "keyword_filter": None, "note": "guru channel"},
    ])

    result = migrate(conn, manifest_path, now="2026-07-30T00:00:00Z")

    assert result.seeded == 1
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


def test_every_platform_key_is_seeded_not_just_youtube_and_bluesky(conn, tmp_path):
    """migrate() read only `youtube` and `bluesky` (:68, :76). A handle under
    any other platform key was silently dropped (B-70/B-71)."""
    payload = {"creators": {"c": {"display_name": "C"}},
               **{p: [] for p in mig.PLATFORMS}, "rss": []}
    for platform in mig.PLATFORMS:
        payload[platform] = [{"handle": f"@on-{platform}", "creator": "c",
                              "cohort": "guru", "included": True}]
    result = mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")

    assert result.seeded == len(mig.PLATFORMS)
    for platform in mig.PLATFORMS:
        assert db.get_handle_by_platform_and_handle(
            conn, platform, f"@on-{platform}") is not None


def test_shipped_manifest_declares_every_platform_and_resolves_every_creator():
    data = json.loads(SHIPPED_MANIFEST.read_text(encoding="utf-8"))
    mig.validate_keys(data)                       # raises if a key is unknown or missing
    creators = data["creators"]
    assert len(creators) == 15
    for platform in mig.PLATFORMS:
        for entry in data[platform]:
            assert entry["creator"] in creators, f"{platform}/{entry['handle']}"
            assert entry["cohort"] in {
                "guru", "shorts-specialist", "midjourney-source", "general-interest"}
            assert isinstance(entry["included"], bool)
    assert len(data["youtube"]) == 15
    assert len(data["bluesky"]) == 1


def test_explicit_cohort_beats_the_note_derived_one(conn, tmp_path):
    """The note says 'guru channel' -- a prose rewrite must never be able to
    reclassify an entry that states its cohort (B-77)."""
    payload = {"creators": {"c": {"display_name": "C"}},
               **{p: [] for p in mig.PLATFORMS}, "rss": []}
    payload["youtube"] = [{"handle": "@c", "creator": "c", "cohort": "shorts-specialist",
                           "included": True, "note": "guru channel (manual-seed)"}]
    mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")
    assert db.get_handle_by_platform_and_handle(
        conn, "youtube", "@c")["cohort"] == "shorts-specialist"


def test_shipped_manifest_never_needs_the_derive_cohort_fallback():
    """derive_cohort defaults to 'general-interest', this repo's label for
    'out of scope'. Prove no shipped entry can fall into it by accident."""
    data = json.loads(SHIPPED_MANIFEST.read_text(encoding="utf-8"))
    for platform in mig.PLATFORMS:
        for entry in data[platform]:
            assert "cohort" in entry, f"{platform}/{entry['handle']} would be inferred"


def test_included_false_entry_is_seeded_but_excluded(conn, tmp_path):
    payload = {"creators": {"c": {"display_name": "C"}},
               **{p: [] for p in mig.PLATFORMS}, "rss": []}
    payload["youtube"] = [{"handle": "@out", "creator": "c",
                           "cohort": "general-interest", "included": False}]
    mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")
    row = db.get_handle_by_platform_and_handle(conn, "youtube", "@out")
    assert row is not None, "an excluded creator is still declared, still visible"
    assert row["included"] == 0


def test_shipped_general_interest_entries_are_not_pulled_by_daily_runs(conn):
    """B-78: the manifest's own comment calls these out of scope, and the app
    used to pull them every day anyway."""
    mig.migrate(conn, SHIPPED_MANIFEST, now="2026-08-08T00:00:00+00:00")
    included = {(r["platform"], r["handle"]) for r in db.list_handles(conn, included_only=True)}
    assert ("youtube", "@bigthink") not in included
    assert ("bluesky", "adamgrant.bsky.social") not in included
    assert ("youtube", "@JennyHoyos") in included      # not a blanket exclusion


def test_seeded_handles_are_pending_not_validated(conn, tmp_path):
    """FAULT: 'validated' must be earned by a real fetch (discovery_engine.py:
    245-249). A JSON file is not evidence a channel still exists (B-75)."""
    payload = {"creators": {"c": {"display_name": "C"}},
               **{p: [] for p in mig.PLATFORMS}, "rss": []}
    payload["youtube"] = [{"handle": "@c", "creator": "c", "cohort": "guru", "included": True}]
    mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")
    row = db.get_handle_by_platform_and_handle(conn, "youtube", "@c")
    assert row["status"] == "pending"
    assert row["validated_at"] is None


def test_a_seeded_handle_is_distinguishable_from_a_fetch_validated_one(conn, tmp_path):
    """DISTINGUISHABILITY: before the fix both read `validated`, so the status
    column told the operator nothing."""
    payload = {"creators": {"c": {"display_name": "C"}},
               **{p: [] for p in mig.PLATFORMS}, "rss": []}
    payload["youtube"] = [{"handle": "@seeded", "creator": "c", "cohort": "guru", "included": True}]
    mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")
    seeded = db.get_handle_by_platform_and_handle(conn, "youtube", "@seeded")

    real_id = db.create_handle(conn, "youtube", "@fetched", "F", "guru", None,
                               "2026-08-08T00:00:00+00:00")
    db.set_handle_status(conn, real_id, "validated", validated_at="2026-08-08T00:01:00+00:00")
    fetched = db.get_handle(conn, real_id)

    assert seeded["status"] != fetched["status"]


def test_main_reports_seeded_handles_need_validation(conn, tmp_path, capsys):
    """SURFACING: the operator is told the roster is unverified."""
    rc = mig.main(["--manifest", str(SHIPPED_MANIFEST), "--db-path", str(tmp_path / "p.db")])
    assert rc == 0
    assert "pending validation" in capsys.readouterr().out
