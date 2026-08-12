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


def test_backfill_skips_a_broken_legacy_project_without_blocking_others(conn, tmp_path):
    """One project with an unreadable/malformed legacy artifact must not crash the
    whole migration (and therefore app startup) -- it should be skipped, and every
    other project still gets backfilled."""
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

    # Nothing was committed for the broken project, so a later startup retries it
    # cleanly rather than skipping it forever or leaving orphaned state.
    touched_again = backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)
    assert touched_again == []


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
