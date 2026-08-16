import sqlite3
from pathlib import Path

import pytest

from pipeline_app import artifacts
from pipeline_app import db as db_mod
from pipeline_app import migrations
from pipeline_app.migrations import (
    BackfillWouldOverwriteError,
    _backfill_one_project,
    backfill_styleboard_rows,
)
from pipeline_app.pipeline_config import StageDef

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "pipeline_app"

STAGE_DEFS = [
    StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02", depends_on=[]),
    StageDef(id="styleboard", skill="shorts-styleboard", dir_prefix="02b", depends_on=["scripting"]),
    StageDef(id="visual", skill="visual-prompts", dir_prefix="03",
             depends_on=["scripting", "styleboard"]),
]

LEGACY_SHEET = """\
=== VISUAL PROMPT SHEET — legacy ===

WORLD LOCK
  register_a_sport: club soccer
  register_a_signature_objects: goal net, corner flag

WHOLE-SHORT SETUP
  Aspect ratio: --ar 9:16
"""


@pytest.fixture
def conn(tmp_path):
    connection = sqlite3.connect(tmp_path / "test.db")
    connection.row_factory = sqlite3.Row
    connection.executescript((PACKAGE_DIR / "schema.sql").read_text(encoding="utf-8"))
    connection.commit()
    yield connection
    connection.close()


def _legacy_project(conn, repo_root, run_id, visual_status, sheet=None):
    project_id = db_mod.create_project(conn, run_id, "slug", "generic", "2026-07-01T00:00:00+00:00")
    db_mod.create_stage_row(conn, project_id, "scripting", "approved")
    db_mod.create_stage_row(conn, project_id, "visual", visual_status)
    visual_dir = repo_root / "runs" / run_id / "03-visual"
    visual_dir.mkdir(parents=True, exist_ok=True)
    if sheet is not None:
        (visual_dir / "artifact.v1.md").write_text(
            "---\nschema_version: 1\nstatus: final\n---\n\n" + sheet, encoding="utf-8"
        )
    return project_id


def test_backfill_inserts_a_styleboard_row_for_a_legacy_project(conn, tmp_path):
    pid = _legacy_project(conn, tmp_path, "legacy-1", "locked")
    assert backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS) == [pid]
    assert db_mod.get_stage(conn, pid, "styleboard") is not None


def test_backfill_approves_styleboard_when_a_world_lock_can_be_lifted(conn, tmp_path):
    pid = _legacy_project(conn, tmp_path, "legacy-2", "approved", sheet=LEGACY_SHEET)
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    row = db_mod.get_stage(conn, pid, "styleboard")
    assert row["status"] == "approved"

    written = tmp_path / "runs" / "legacy-2" / "02b-styleboard" / "artifact.v1.md"
    assert written.exists()
    assert "register_a_sport: club soccer" in written.read_text(encoding="utf-8")


def test_backfill_leaves_styleboard_ready_when_there_is_no_world_lock_to_lift(conn, tmp_path):
    pid = _legacy_project(conn, tmp_path, "legacy-3", "locked")
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)
    assert db_mod.get_stage(conn, pid, "styleboard")["status"] == "ready"


def test_backfill_is_idempotent(conn, tmp_path):
    _legacy_project(conn, tmp_path, "legacy-4", "locked")
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)
    assert backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS) == []


def test_backfilled_project_can_unlock_visual(conn, tmp_path):
    """The whole point: without the row, stages_to_unlock can never satisfy visual."""
    from pipeline_app.state_machine import stages_to_unlock

    pid = _legacy_project(conn, tmp_path, "legacy-5", "locked", sheet=LEGACY_SHEET)
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    rows = db_mod.list_stages(conn, pid)
    approved = {r["stage_id"] for r in rows if r["status"] == "approved"}
    assert "visual" in stages_to_unlock(STAGE_DEFS, approved)


def test_backfill_writes_synthetic_artifact_when_past_visual_with_no_recoverable_world_lock(
    conn, tmp_path
):
    """A project that finished visual but has nothing liftable must still get an
    artifact behind its approved styleboard row -- approve_stage's invariant applies
    to rows this migration creates too, not just ones a human approves by hand."""
    pid = _legacy_project(conn, tmp_path, "legacy-6", "approved")  # no sheet written
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    row = db_mod.get_stage(conn, pid, "styleboard")
    assert row["status"] == "approved"

    written = tmp_path / "runs" / "legacy-6" / "02b-styleboard" / "artifact.v1.md"
    assert written.exists()
    assert "not recoverable" in written.read_text(encoding="utf-8")


def test_backfill_one_project_leaves_nothing_behind_when_it_fails_partway(conn, tmp_path, monkeypatch):
    """FAULT (A-70's worked example). _backfill_one_project inserts an approved
    styleboard row, then sets approved_at. Without a transaction boundary the row
    insert commits immediately, so an interruption before approved_at is set
    leaves status='approved', approved_at=NULL forever -- nothing else in the app
    ever revisits an existing styleboard row. Force the failure on the second
    step (the approved_at update) and assert the first step's row (the insert)
    did not survive either."""
    pid = _legacy_project(conn, tmp_path, "legacy-flaky", "approved", sheet=LEGACY_SHEET)
    project = next(p for p in db_mod.list_projects(conn) if p["id"] == pid)
    stage_def = next(s for s in STAGE_DEFS if s.id == "styleboard")
    visual_def = next(s for s in STAGE_DEFS if s.id == "visual")
    now = "2026-08-08T00:00:00+00:00"

    def raise_on_approved_at(*args, **kwargs):
        raise RuntimeError("boom mid-way through the approved_at update")

    monkeypatch.setattr(db_mod, "update_stage_status", raise_on_approved_at)

    with pytest.raises(RuntimeError):
        _backfill_one_project(conn, tmp_path, stage_def, visual_def, project, now, STAGE_DEFS)

    assert db_mod.get_stage(conn, pid, "styleboard") is None


def test_backfill_skips_a_broken_legacy_project_without_blocking_others(
    conn, tmp_path, monkeypatch
):
    """One project with an unreadable/malformed legacy artifact must not crash the
    whole migration (and therefore app startup) -- it should be skipped, and every
    other project still gets backfilled."""
    recorded = []
    monkeypatch.setattr(migrations.obs, "record_event",
                        lambda c, **kw: recorded.append(kw) or 1)

    pid_bad = _legacy_project(conn, tmp_path, "legacy-bad", "approved")
    bad_sheet = tmp_path / "runs" / "legacy-bad" / "03-visual" / "artifact.v1.md"
    bad_sheet.write_text(
        "---\nschema_version: 1\nstatus: 'unterminated\n---\n\nWORLD LOCK\n  x: y\n",
        encoding="utf-8",
    )
    pid_good = _legacy_project(conn, tmp_path, "legacy-good", "locked")

    touched = backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    assert touched == [pid_good]
    assert db_mod.get_stage(conn, pid_bad, "styleboard") is None
    assert db_mod.get_stage(conn, pid_good, "styleboard") is not None

    # A-74: the skip must be findable, not stderr-only.
    skips = [e for e in recorded if e["kind"] == "migration.backfill_skipped"]
    assert len(skips) == 1
    assert skips[0]["severity"] == "error"
    assert skips[0]["detail"]["project_id"] == pid_bad
    assert skips[0]["detail"]["run_id"] == "legacy-bad"

    # Nothing was committed for the broken project, so a later startup retries it
    # cleanly rather than skipping it forever or leaving orphaned state.
    touched_again = backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)
    assert touched_again == []


def test_a_skipped_project_records_an_error_event(conn, tmp_path, monkeypatch):
    """SURFACING. A-74: a per-project OSError/UnicodeDecodeError/YAMLError
    printed one line to stderr and continued. backfilled_projects records only
    successes, /doctor surfaces nothing about backfill, and an operator running
    under a service manager or a detached uvicorn never sees the stderr line."""
    recorded = []
    monkeypatch.setattr(migrations.obs, "record_event",
                        lambda c, **kw: recorded.append(kw) or 1)

    pid_bad = _legacy_project(conn, tmp_path, "legacy-bad", "approved")
    (tmp_path / "runs" / "legacy-bad" / "03-visual" / "artifact.v1.md").write_text(
        "---\nschema_version: 1\nstatus: 'unterminated\n---\n\nWORLD LOCK\n  x: y\n",
        encoding="utf-8",
    )
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    skips = [e for e in recorded if e["kind"] == "migration.backfill_skipped"]
    assert len(skips) == 1
    assert skips[0]["severity"] == "error"
    assert skips[0]["detail"]["project_id"] == pid_bad
    assert skips[0]["detail"]["run_id"] == "legacy-bad"
    assert "legacy-bad" in skips[0]["message"]


def test_a_run_with_no_skips_records_no_skip_event(conn, tmp_path, monkeypatch):
    """DISTINGUISHABILITY. A migration that skipped a project must be
    observably different from one that had nothing to do."""
    recorded = []
    monkeypatch.setattr(migrations.obs, "record_event",
                        lambda c, **kw: recorded.append(kw) or 1)
    _legacy_project(conn, tmp_path, "legacy-fine", "locked")
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)
    assert [e for e in recorded if e["kind"] == "migration.backfill_skipped"] == []


def test_a_failure_to_record_the_event_does_not_mask_the_skip(conn, tmp_path, monkeypatch):
    """FAULT. obs.record_event never raises by contract, but the migration must
    not depend on that: the loop still continues and the other project is still
    backfilled."""
    monkeypatch.setattr(migrations.obs, "record_event",
                        lambda c, **kw: (_ for _ in ()).throw(RuntimeError("db gone")))
    _legacy_project(conn, tmp_path, "legacy-bad2", "approved")
    (tmp_path / "runs" / "legacy-bad2" / "03-visual" / "artifact.v1.md").write_text(
        "---\nstatus: 'unterminated\n---\n\nWORLD LOCK\n  x: y\n", encoding="utf-8")
    pid_good = _legacy_project(conn, tmp_path, "legacy-good2", "locked")

    assert backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS) == [pid_good]


def test_a_skip_event_is_durably_committed_and_readable_on_a_second_connection(conn, tmp_path):
    """SURFACING, end-to-end. The other three tests all mock obs.record_event, so none of
    them proves the row survives using the CORRECT connection -- a wrong/stale conn object
    would pass those tests undetected. This test uses no mock: it runs the real migration
    against a real broken project, then reads the events table back on a SEPARATE
    connection to the same file."""
    import sqlite3

    db_path = tmp_path / "test.db"
    pid_bad = _legacy_project(conn, tmp_path, "legacy-bad3", "approved")
    (tmp_path / "runs" / "legacy-bad3" / "03-visual" / "artifact.v1.md").write_text(
        "---\nschema_version: 1\nstatus: 'unterminated\n---\n\nWORLD LOCK\n  x: y\n",
        encoding="utf-8",
    )
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    second_conn = sqlite3.connect(db_path)
    second_conn.row_factory = sqlite3.Row
    try:
        rows = second_conn.execute(
            "SELECT kind, severity, message, detail FROM events WHERE kind = ?",
            ("migration.backfill_skipped",),
        ).fetchall()
    finally:
        second_conn.close()

    assert len(rows) == 1
    assert rows[0]["severity"] == "error"
    assert "legacy-bad3" in rows[0]["message"]


def test_backfill_refuses_to_overwrite_a_real_styleboard_artifact(conn, tmp_path):
    """A-73, the S0. runs/ and pipeline.db are independently git-ignored and
    independently disposable. Resetting the DB while runs/ is intact used to
    rewrite every project's real 02b-styleboard/artifact.v1.md with the
    synthetic "not recoverable" body -- no backup, no warning."""
    pid = _legacy_project(conn, tmp_path, "legacy-real", "approved")
    styleboard_dir = tmp_path / "runs" / "legacy-real" / "02b-styleboard"
    styleboard_dir.mkdir(parents=True)
    real = styleboard_dir / "artifact.v1.md"
    real.write_text(
        "---\nschema_version: 1\nversion: 1\nstatus: final\n---\n\n"
        "WORLD LOCK\n  register_a_sport: the real hand-authored world\n",
        encoding="utf-8",
    )
    before = real.read_text(encoding="utf-8")

    touched = backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    assert real.read_text(encoding="utf-8") == before
    assert "the real hand-authored world" in real.read_text(encoding="utf-8")
    assert pid not in touched


def test_refusing_to_overwrite_records_an_error_event(conn, tmp_path, monkeypatch):
    """SURFACING. Destroying a styleboard must never be the quiet outcome, and
    declining to destroy it must not be quiet either."""
    recorded = []
    monkeypatch.setattr(migrations.obs, "record_event",
                        lambda c, **kw: recorded.append(kw) or 1)
    _legacy_project(conn, tmp_path, "legacy-real2", "approved")
    d = tmp_path / "runs" / "legacy-real2" / "02b-styleboard"
    d.mkdir(parents=True)
    (d / "artifact.v1.md").write_text(
        "---\nversion: 1\nstatus: final\n---\n\nreal\n", encoding="utf-8")

    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    assert any(e["severity"] == "error" and "overwrite" in e["message"].lower()
               for e in recorded)


def test_a_crash_between_the_artifact_write_and_the_db_row_does_not_churn_the_artifact(
    conn, tmp_path, monkeypatch
):
    """A-73's second hazard: the disk write precedes the DB write, so a failure
    in between left an artifact with no row -- and the next boot rewrote it
    with a fresh `now`, changing its sha256 and spuriously staling every
    dependent.

    create_stage_row raising OSError is caught by backfill_styleboard_rows'
    own _PER_PROJECT_RECOVERABLE guard (OSError is in that tuple), so the
    project is skipped for this run rather than the whole migration crashing
    -- assert on that skip, not pytest.raises. The property under test is the
    one that must hold either way: the artifact this crash left behind on disk
    must come back byte-identical (same sha256) on the retry, not be rewritten
    with a fresh timestamp.
    """
    pid = _legacy_project(conn, tmp_path, "legacy-crash", "approved", sheet=LEGACY_SHEET)

    real_create = db_mod.create_stage_row

    def crash_once(*a, **k):
        raise OSError("killed between the disk write and the row insert")

    monkeypatch.setattr(db_mod, "create_stage_row", crash_once)

    touched = backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)
    assert touched == []
    assert db_mod.get_stage(conn, pid, "styleboard") is None

    written = tmp_path / "runs" / "legacy-crash" / "02b-styleboard" / "artifact.v1.md"
    assert written.exists()
    sha_after_crash = artifacts.compute_sha256(written)

    monkeypatch.setattr(db_mod, "create_stage_row", real_create)
    touched_again = backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    assert touched_again == [pid]
    assert artifacts.compute_sha256(written) == sha_after_crash, \
        "the retry rewrote the artifact with a fresh timestamp and staled its dependents"
    assert len(list((written.parent).glob("artifact.v*.md"))) == 1


def test_backfill_allocates_its_version_rather_than_hardcoding_one(conn, tmp_path):
    """_write_synthetic_artifact passed a literal 1 to write_artifact rather
    than allocating."""
    _legacy_project(conn, tmp_path, "legacy-v", "approved", sheet=LEGACY_SHEET)
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)
    written = tmp_path / "runs" / "legacy-v" / "02b-styleboard" / "artifact.v1.md"
    meta, _ = artifacts.read_artifact(written)
    assert meta["version"] == 1     # first version in an empty dir, but ALLOCATED
    assert (tmp_path / "runs" / "legacy-v" / "02b-styleboard" / ".artifact-version-hwm").exists()


def test_backfilled_styleboard_records_the_scripting_artifact_it_was_built_against(
    conn, tmp_path
):
    """A-61: _write_synthetic_artifact hardcoded depends_on: [] while the row
    was set to approved. styleboard declares depends_on: [scripting], so on
    every migrated project a scripting change could NEVER flip styleboard
    stale -- and `visual` was then regenerated against an unflagged world lock."""
    pid = _legacy_project(conn, tmp_path, "legacy-dep", "approved", sheet=LEGACY_SHEET)
    scripting_dir = tmp_path / "runs" / "legacy-dep" / "02-scripting"
    script = artifacts.write_artifact(
        scripting_dir, 1, {"version": 1, "status": "final"}, "the script")

    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    written = tmp_path / "runs" / "legacy-dep" / "02b-styleboard" / "artifact.v1.md"
    meta, _ = artifacts.read_artifact(written)
    assert meta["depends_on"] == [
        {"path": "02-scripting/artifact.v1.md",
         "sha256": artifacts.compute_sha256(script)},
    ]


def test_a_backfilled_styleboard_goes_stale_when_its_script_is_rewritten(conn, tmp_path):
    """The cascade this was terminating. is_stale must now fire."""
    from pipeline_app.state_machine import is_stale

    _legacy_project(conn, tmp_path, "legacy-dep2", "approved", sheet=LEGACY_SHEET)
    scripting_dir = tmp_path / "runs" / "legacy-dep2" / "02-scripting"
    artifacts.write_artifact(scripting_dir, 1, {"version": 1}, "original script")
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    written = tmp_path / "runs" / "legacy-dep2" / "02b-styleboard" / "artifact.v1.md"
    recorded = artifacts.read_artifact(written)[0]["depends_on"]

    rewritten = artifacts.write_artifact(scripting_dir, 2, {"version": 2}, "REWRITTEN script")
    current = {"02-scripting/artifact.v2.md": artifacts.compute_sha256(rewritten)}
    assert is_stale(recorded, current) is True


def test_backfilled_artifact_records_an_explicit_gates_key(conn, tmp_path):
    """It was the one approved artifact in the app carrying no `gates` key at
    all -- indistinguishable, to approval_service, from a clean run."""
    _legacy_project(conn, tmp_path, "legacy-gates", "approved", sheet=LEGACY_SHEET)
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)
    written = tmp_path / "runs" / "legacy-gates" / "02b-styleboard" / "artifact.v1.md"
    meta, _ = artifacts.read_artifact(written)
    assert "gates" in meta
    assert meta["gates"] == []
    assert meta["backfilled"] is True


def test_durability_contract_backfill_refuses_a_populated_stage_dir(conn, tmp_path):
    """F-18's third clause: test_migrations.py never placed a real artifact
    where the backfill writes."""
    _legacy_project(conn, tmp_path, "legacy-dur", "approved", sheet=LEGACY_SHEET)
    d = tmp_path / "runs" / "legacy-dur" / "02b-styleboard"
    d.mkdir(parents=True)
    real = d / "artifact.v1.md"
    real.write_text("---\nversion: 1\nstatus: final\n---\n\nreal\n", encoding="utf-8")
    sha = artifacts.compute_sha256(real)

    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)
    assert artifacts.compute_sha256(real) == sha


def test_backfill_gate_coverage_stamps_existing_approved_artifacts(conn, tmp_path):
    from pipeline_app import artifacts, db, migrations
    from pipeline_app.pipeline_config import StageDef

    stage_defs = [StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[])]
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-08-06T00:00:00Z")
    row = db.create_stage_row(conn, project_id, "ideation", "approved")
    run_dir = tmp_path / "runs" / "abc-1"
    stage_dir = run_dir / "01-ideation"
    path = artifacts.write_artifact(
        stage_dir, 1, {"status": "final", "stage": "shorts-ideation"}, "old body",
    )

    touched = migrations.backfill_gate_coverage_artifacts(conn, tmp_path, stage_defs)

    assert str(path.relative_to(tmp_path)).replace("\\", "/") in touched
    meta, _ = artifacts.read_artifact(path)
    gate_names = [g["name"] for g in meta["gates"]]
    assert "gate_o_ideation_contract" in gate_names
    passed = next(g for g in meta["gates"] if g["name"] == "gate_o_ideation_contract")
    assert passed["status"] == "pass"
    overrides = artifacts.read_gate_overrides(path)
    assert len(overrides) == 1
    assert "gate-coverage migration" in overrides[0]["reason"]


GATE_COVERAGE_STAGE_DEFS = [
    StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[]),
    StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02",
             depends_on=["ideation"]),
]


def _project_with_downstream(conn, repo_root):
    """An approved ideation artifact plus an approved scripting artifact that
    recorded ideation's PRE-backfill hash -- the exact shape the live scan
    found 17 times across 6 projects."""
    project_id = db_mod.create_project(
        conn, "dep-1", "dep", "generic", "2026-08-16T00:00:00Z")
    db_mod.create_stage_row(conn, project_id, "ideation", "approved")
    db_mod.create_stage_row(conn, project_id, "scripting", "approved")
    run_dir = repo_root / "runs" / "dep-1"
    upstream = artifacts.write_artifact(
        run_dir / "01-ideation", 1,
        {"version": 1, "status": "final", "stage": "shorts-ideation"}, "the brief",
    )
    downstream = artifacts.write_artifact(
        run_dir / "02-scripting", 1,
        {
            "version": 1, "status": "final", "stage": "shorts-scripting",
            "depends_on": artifacts.compute_depends_on(run_dir, [upstream]),
        },
        "the script",
    )
    return run_dir, upstream, downstream


def test_backfill_gate_coverage_repairs_downstream_dependency_hashes(conn, tmp_path):
    """The migration mutates an approved artifact in place, which breaks the
    invariant turn_service._current_upstream_hashes rests on. Every dependent
    that recorded the pre-stamp hash must be re-pointed at the post-stamp one,
    or the whole tree below a backfilled artifact flips stale for a change
    that is pure bookkeeping."""
    from pipeline_app.state_machine import is_stale

    run_dir, upstream, downstream = _project_with_downstream(conn, tmp_path)
    pre_backfill = artifacts.read_artifact(downstream)[0]["depends_on"]
    assert pre_backfill[0]["sha256"] == artifacts.compute_sha256(upstream)

    migrations.backfill_gate_coverage_artifacts(conn, tmp_path, GATE_COVERAGE_STAGE_DEFS)

    # (a) the upstream still got its stamp, unchanged by the repair work
    upstream_meta, _ = artifacts.read_artifact(upstream)
    assert "gate_o_ideation_contract" in [g["name"] for g in upstream_meta["gates"]]
    assert artifacts.read_gate_overrides(upstream)

    # (b) the dependent now records the upstream's NEW hash -- checked through
    # the real staleness entry point, not a hand-rolled comparison.
    new_hash = artifacts.compute_sha256(upstream)
    assert new_hash != pre_backfill[0]["sha256"]
    recorded = artifacts.read_artifact(downstream)[0]["depends_on"]
    assert recorded[0]["sha256"] == new_hash
    assert is_stale(recorded, {"01-ideation/artifact.v1.md": new_hash}) is False


def test_backfill_gate_coverage_repair_cascades_past_the_first_dependent(conn, tmp_path):
    """Repairing a dependent rewrites it, which changes ITS hash -- so the
    grandchild's recorded hash has to move too, or the migration just pushes
    the spurious staleness one level down the DAG instead of removing it."""
    from pipeline_app.state_machine import is_stale

    stage_defs = [
        *GATE_COVERAGE_STAGE_DEFS,
        StageDef(id="styleboard", skill="shorts-styleboard", dir_prefix="02b",
                 depends_on=["scripting"]),
    ]
    run_dir, upstream, downstream = _project_with_downstream(conn, tmp_path)
    grandchild = artifacts.write_artifact(
        run_dir / "02b-styleboard", 1,
        {
            "version": 1, "status": "final", "stage": "shorts-styleboard",
            "depends_on": artifacts.compute_depends_on(run_dir, [downstream]),
        },
        "the styleboard",
    )

    migrations.backfill_gate_coverage_artifacts(conn, tmp_path, stage_defs)

    recorded = artifacts.read_artifact(grandchild)[0]["depends_on"]
    assert recorded[0]["sha256"] == artifacts.compute_sha256(downstream)
    assert is_stale(
        recorded, {"02-scripting/artifact.v1.md": artifacts.compute_sha256(downstream)}
    ) is False


def test_backfill_gate_coverage_repair_is_idempotent(conn, tmp_path):
    """Second run finds no entry carrying the old hash, so it rewrites
    nothing -- the dependent's bytes are identical across the repeat."""
    run_dir, upstream, downstream = _project_with_downstream(conn, tmp_path)
    migrations.backfill_gate_coverage_artifacts(conn, tmp_path, GATE_COVERAGE_STAGE_DEFS)
    after_first = downstream.read_bytes()
    upstream_after_first = upstream.read_bytes()

    assert migrations.backfill_gate_coverage_artifacts(
        conn, tmp_path, GATE_COVERAGE_STAGE_DEFS) == []
    assert downstream.read_bytes() == after_first
    assert upstream.read_bytes() == upstream_after_first


def test_backfill_gate_coverage_leaves_a_genuinely_stale_dependent_stale(conn, tmp_path):
    """The repair matches on (path, old hash) together. A dependent recording
    some other hash for that path was already stale on its own merits and must
    not be laundered clean by the migration."""
    from pipeline_app.state_machine import is_stale

    run_dir, upstream, downstream = _project_with_downstream(conn, tmp_path)
    meta, body = artifacts.read_artifact(downstream)
    meta["depends_on"][0]["sha256"] = "0" * 64
    artifacts._atomic_write_text(downstream, artifacts.render_frontmatter(meta, body))

    migrations.backfill_gate_coverage_artifacts(conn, tmp_path, GATE_COVERAGE_STAGE_DEFS)

    recorded = artifacts.read_artifact(downstream)[0]["depends_on"]
    assert recorded[0]["sha256"] == "0" * 64
    assert is_stale(
        recorded,
        {"01-ideation/artifact.v1.md": artifacts.compute_sha256(upstream)},
    ) is True


def test_backfill_gate_coverage_is_idempotent(conn, tmp_path):
    from pipeline_app import artifacts, db, migrations
    from pipeline_app.pipeline_config import StageDef

    stage_defs = [StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[])]
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-08-06T00:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "approved")
    run_dir = tmp_path / "runs" / "abc-1"
    artifacts.write_artifact(
        run_dir / "01-ideation", 1, {"status": "final", "stage": "shorts-ideation"}, "old body",
    )

    migrations.backfill_gate_coverage_artifacts(conn, tmp_path, stage_defs)
    second_run = migrations.backfill_gate_coverage_artifacts(conn, tmp_path, stage_defs)

    assert second_run == []  # already-stamped artifacts are not touched twice


def test_backfill_gate_coverage_skips_a_malformed_artifact_without_crashing(
    conn, tmp_path, monkeypatch
):
    """A malformed/unreadable artifact in one project/stage must not raise out
    of the migration (and therefore out of create_app at startup) -- it must
    be skipped, logged as an event, and every other approved artifact must
    still get stamped."""
    from pipeline_app import artifacts, db, migrations
    from pipeline_app.pipeline_config import StageDef

    stage_defs = [StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[])]

    recorded = []
    monkeypatch.setattr(migrations.obs, "record_event",
                        lambda c, **kw: recorded.append(kw) or 1)

    pid_bad = db.create_project(conn, "bad-1", "bad", "generic", "2026-08-06T00:00:00Z")
    db.create_stage_row(conn, pid_bad, "ideation", "approved")
    bad_dir = tmp_path / "runs" / "bad-1" / "01-ideation"
    bad_dir.mkdir(parents=True)
    (bad_dir / "artifact.v1.md").write_text(
        "---\nstatus: 'unterminated\n---\n\nbroken\n", encoding="utf-8",
    )

    pid_good = db.create_project(conn, "good-1", "good", "generic", "2026-08-06T00:00:00Z")
    db.create_stage_row(conn, pid_good, "ideation", "approved")
    good_path = artifacts.write_artifact(
        tmp_path / "runs" / "good-1" / "01-ideation", 1,
        {"status": "final", "stage": "shorts-ideation"}, "old body",
    )

    touched = migrations.backfill_gate_coverage_artifacts(conn, tmp_path, stage_defs)

    assert str(good_path.relative_to(tmp_path)).replace("\\", "/") in touched
    assert len(touched) == 1

    skips = [e for e in recorded if e["kind"] == "migration.backfill_skipped"]
    assert len(skips) == 1
    assert skips[0]["severity"] == "error"
    assert skips[0]["detail"]["project_id"] == pid_bad
    assert skips[0]["detail"]["run_id"] == "bad-1"
    assert skips[0]["detail"]["stage_id"] == "ideation"

    meta, _ = artifacts.read_artifact(good_path)
    assert "gate_o_ideation_contract" in [g["name"] for g in meta["gates"]]
