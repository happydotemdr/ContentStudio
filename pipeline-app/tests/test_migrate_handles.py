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


def test_rerun_applies_a_changed_display_name_and_keyword_filter(conn, tmp_path):
    """FAULT: INSERT OR IGNORE (db.py:186-189) meant the manifest stopped being
    the source of truth after the first run (B-76)."""
    base = {"creators": {"c": {"display_name": "C"}},
            **{p: [] for p in mig.PLATFORMS}, "rss": []}
    base["youtube"] = [{"handle": "@c", "creator": "c", "display_name": "Old",
                        "cohort": "guru", "included": True, "keyword_filter": None}]
    path = _write(tmp_path, base)
    mig.migrate(conn, path, now="2026-08-08T00:00:00+00:00")

    base["youtube"][0].update(display_name="New", keyword_filter="only this",
                              cohort="shorts-specialist", included=False)
    path.write_text(json.dumps(base), encoding="utf-8")
    result = mig.migrate(conn, path, now="2026-08-08T01:00:00+00:00")

    row = db.get_handle_by_platform_and_handle(conn, "youtube", "@c")
    assert row["display_name"] == "New"
    assert row["keyword_filter"] == "only this"
    assert row["cohort"] == "shorts-specialist"
    assert row["included"] == 0
    assert result.updated == 1 and result.seeded == 0


def test_rerun_preserves_run_owned_status_and_last_seen(conn, tmp_path):
    """DISTINGUISHABILITY: manifest-owned columns move, run-owned columns do
    not. A re-seed must not erase what a real fetch learned."""
    base = {"creators": {"c": {"display_name": "C"}},
            **{p: [] for p in mig.PLATFORMS}, "rss": []}
    base["youtube"] = [{"handle": "@c", "creator": "c", "display_name": "C",
                        "cohort": "guru", "included": True}]
    path = _write(tmp_path, base)
    mig.migrate(conn, path, now="2026-08-08T00:00:00+00:00")
    row_id = db.get_handle_by_platform_and_handle(conn, "youtube", "@c")["id"]
    db.set_handle_status(conn, row_id, "invalid", validated_at="2026-08-08T00:30:00+00:00")
    db.set_handle_last_seen(conn, row_id, "2026-08-07T00:00:00+00:00")

    base["youtube"][0]["display_name"] = "C2"
    path.write_text(json.dumps(base), encoding="utf-8")
    mig.migrate(conn, path, now="2026-08-08T01:00:00+00:00")

    row = db.get_handle(conn, row_id)
    assert row["display_name"] == "C2"                       # manifest-owned: moved
    assert row["status"] == "invalid"                        # run-owned: untouched
    assert row["validated_at"] == "2026-08-08T00:30:00+00:00"
    assert row["last_seen_published_at"] == "2026-08-07T00:00:00+00:00"


def test_main_prints_updated_separately_from_seeded(conn, tmp_path, capsys):
    """SURFACING: `migrated N handles` counted rows it did not write. The
    summary must distinguish inserted from updated from unchanged."""
    db_path = tmp_path / "p.db"
    mig.main(["--manifest", str(SHIPPED_MANIFEST), "--db-path", str(db_path)])
    capsys.readouterr()
    mig.main(["--manifest", str(SHIPPED_MANIFEST), "--db-path", str(db_path)])
    out = capsys.readouterr().out
    assert "inserted : 0" in out
    assert "updated  : 0" in out


def test_a_db_handle_missing_from_the_manifest_is_reported_as_drift(conn, tmp_path, capsys):
    db.create_handle(conn, "instagram", "@ghost", "Ghost", "guru", None,
                     "2026-08-01T00:00:00+00:00")
    payload = {"creators": {}, **{p: [] for p in mig.PLATFORMS}, "rss": []}
    result = mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")

    assert ("instagram", "@ghost") in result.drift
    assert db.get_handle_by_platform_and_handle(conn, "instagram", "@ghost") is not None, \
        "drift is reported, never auto-deleted -- deletion is the operator's call"


def test_drift_records_a_warning_event(tmp_path):
    db_path = tmp_path / "p.db"
    db.init_db(db_path, Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql")
    conn = db.get_connection(db_path)
    db.create_handle(conn, "instagram", "@ghost", "Ghost", "guru", None,
                     "2026-08-01T00:00:00+00:00")
    conn.close()

    rc = mig.main(["--manifest", str(SHIPPED_MANIFEST), "--db-path", str(db_path)])
    assert rc == 0                                  # drift is a warning, not a failure

    conn = db.get_connection(db_path)
    rows = conn.execute("SELECT * FROM events WHERE kind = 'roster.drift'").fetchall()
    conn.close()
    assert len(rows) == 1 and rows[0]["severity"] == "warning"
    assert "@ghost" in rows[0]["message"]


def test_handles_of_one_creator_share_a_creator_id(conn, tmp_path):
    """The join key that makes 'does this creator have a platform we are not
    tracking?' computable. Adam Grant is on two platforms, unlinked before."""
    payload = {"creators": {"adam-grant": {"display_name": "Adam Grant"}},
               **{p: [] for p in mig.PLATFORMS}, "rss": []}
    payload["youtube"] = [{"handle": "@bigthink", "creator": "adam-grant",
                           "cohort": "general-interest", "included": False}]
    payload["bluesky"] = [{"handle": "adamgrant.bsky.social", "creator": "adam-grant",
                           "cohort": "general-interest", "included": False}]
    mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")

    yt = db.get_handle_by_platform_and_handle(conn, "youtube", "@bigthink")
    bs = db.get_handle_by_platform_and_handle(conn, "bluesky", "adamgrant.bsky.social")
    assert yt["creator_id"] is not None
    assert yt["creator_id"] == bs["creator_id"]
    row = conn.execute("SELECT * FROM creators WHERE id = ?", (yt["creator_id"],)).fetchone()
    assert row["slug"] == "adam-grant" and row["display_name"] == "Adam Grant"


def test_an_entry_naming_an_undeclared_creator_is_a_manifest_error(conn, tmp_path):
    payload = {"creators": {}, **{p: [] for p in mig.PLATFORMS}, "rss": []}
    payload["youtube"] = [{"handle": "@x", "creator": "nobody",
                           "cohort": "guru", "included": True}]
    with pytest.raises(mig.ManifestError) as excinfo:
        mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")
    assert "nobody" in str(excinfo.value)


def test_coverage_report_cell_states_are_exhaustive(tmp_path):
    """A cell is one of exactly three states. UNANSWERABLE means 'the manifest
    has no key for this platform, so we cannot say' -- 74 of 90 cells were in
    that state before this package (B-70)."""
    payload = {"creators": {"c": {"display_name": "C"}},
               **{p: [] for p in mig.PLATFORMS}, "rss": []}
    payload["youtube"] = [{"handle": "@c", "creator": "c", "cohort": "guru", "included": True}]
    payload["x"] = [{"handle": "@c_x", "creator": "c", "cohort": "guru", "included": False}]
    del payload["facebook"]                                   # simulate the old manifest

    report = mig.build_coverage_report(
        json.loads(_write(tmp_path, payload).read_text(encoding="utf-8")))

    assert report.cell("c", "youtube").state == "tracked"
    assert report.cell("c", "x").state == "declared-excluded"
    assert report.cell("c", "instagram").state == "not tracked"
    assert report.cell("c", "facebook").state == "UNANSWERABLE"


def test_shipped_manifest_has_zero_unanswerable_cells():
    """THE coverage test. 'Are we tracking all social platforms for our key
    creators?' is answerable from the repo for every creator and every
    platform, or this fails (B-70, B-81)."""
    data = json.loads(SHIPPED_MANIFEST.read_text(encoding="utf-8"))
    report = mig.build_coverage_report(data)

    # Anti-tautology: a report over zero creators or zero platforms would also
    # have zero UNANSWERABLE cells. Pin the shape first.
    assert sorted(report.platforms) == sorted(mig.PLATFORMS)
    assert len(report.creators) == 15
    assert len(report.cells) == 15 * len(mig.PLATFORMS) == 105

    unanswerable = [(c, p) for (c, p), cell in report.cells.items()
                    if cell.state == "UNANSWERABLE"]
    assert unanswerable == [], (
        f"{len(unanswerable)} creator x platform cells cannot be answered from "
        f"the repo: {unanswerable[:10]}")


def test_report_mode_prints_the_matrix_and_exits_zero(tmp_path, capsys):
    rc = mig.main(["--manifest", str(SHIPPED_MANIFEST),
                   "--db-path", str(tmp_path / "p.db"), "--report"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "UNANSWERABLE : 0" in out
    assert "adam-grant" in out
    assert "linkedin-profile" in out


def test_report_mode_writes_nothing_to_the_database(tmp_path):
    """--report is read-only: an operator answering a coverage question must
    not accidentally re-seed the roster."""
    db_path = tmp_path / "p.db"
    mig.main(["--manifest", str(SHIPPED_MANIFEST), "--db-path", str(db_path), "--report"])
    conn = db.get_connection(db_path)
    assert db.list_handles(conn) == []
    conn.close()


def test_shipped_manifest_has_no_slug_collisions():
    """handle_slug is lossy (periods stripped, lowercased). Two colliding
    handles on one platform get billed twice into one directory."""
    from pipeline_app.discovery_paths import handle_slug
    data = json.loads(SHIPPED_MANIFEST.read_text(encoding="utf-8"))
    for platform in mig.PLATFORMS:
        slugs = [handle_slug(e["handle"]) for e in data[platform]]
        assert len(slugs) == len(set(slugs)), f"slug collision on {platform}: {slugs}"


def test_shipped_manifest_seeds_every_declared_handle(conn):
    """Replaces test_migrate_seeds_all_16_handles_as_validated, whose name
    promised a coverage guarantee over three synthetic entries (B-81)."""
    data = json.loads(SHIPPED_MANIFEST.read_text(encoding="utf-8"))
    expected = sum(len(data[p]) for p in mig.PLATFORMS)
    result = mig.migrate(conn, SHIPPED_MANIFEST, now="2026-08-08T00:00:00+00:00")
    assert expected == 16
    assert result.seeded == expected
    assert result.skipped == 0 and result.errors == []
    assert len(db.list_handles(conn)) == expected
