import sqlite3
from pathlib import Path

import pytest

from pipeline_app import db as db_mod
from pipeline_app.migrations import backfill_styleboard_rows
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
