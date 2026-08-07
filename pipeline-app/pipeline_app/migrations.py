"""One-shot, idempotent schema/state migrations run at app startup.

Kept separate from db.py: db.py holds the durable query surface, this holds
corrections that exist only because the topology changed under projects that
were already on disk.
"""

import datetime
import re
import sqlite3
from pathlib import Path

from pipeline_app import artifacts, db as db_mod
from pipeline_app.pipeline_config import StageDef, stage_dir_name
from pipeline_app.state_machine import StageStatus

_WORLD_HEADING_RE = re.compile(r"^\s*WORLD LOCK\s*$")
_WORLD_ENTRY_RE = re.compile(r"^\s+([a-z][a-z0-9_]*)\s*:\s*(.+?)\s*$")

# Statuses meaning "this project already got past visual", so a styleboard row
# inserted now must be `approved` or visual would regress to unreachable.
_PAST_VISUAL = {
    StageStatus.APPROVED.value,
    StageStatus.AWAITING_REVIEW.value,
    StageStatus.STALE.value,
    StageStatus.NO_ARTIFACT.value,
}


def extract_world_lock_block(text: str) -> str | None:
    """The verbatim WORLD LOCK block from a legacy sheet, or None.

    Deliberately re-implemented here rather than imported from
    scripts/lint_prompt_sheet.py: that module returns a parsed dict, and this needs the
    original lines byte-for-byte so the synthetic artifact is a faithful copy of what the
    project actually rendered against.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not _WORLD_HEADING_RE.match(line):
            continue
        block = [line.strip()]
        for entry in lines[i + 1:]:
            if not _WORLD_ENTRY_RE.match(entry):
                break
            block.append(entry.rstrip())
        return "\n".join(block) if len(block) > 1 else None
    return None


def backfill_styleboard_rows(
    conn: sqlite3.Connection,
    repo_root: Path,
    stage_defs: list[StageDef],
) -> list[int]:
    """Give every pre-existing project the styleboard row the new topology requires.

    create_project materialises stage rows once, at creation, so a project made before
    styleboard existed has no row for it -- and stages_to_unlock requires ALL declared
    dependencies approved, so `visual` could never leave `locked` for that project.

    Where the project already produced a visual sheet, its WORLD LOCK block is lifted
    into a synthetic styleboard artifact and the row is approved, preserving the
    project's real world lock rather than blanking it.
    """
    stage_def = next((s for s in stage_defs if s.id == "styleboard"), None)
    if stage_def is None:
        return []

    visual_def = next((s for s in stage_defs if s.id == "visual"), None)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    touched: list[int] = []

    for project in db_mod.list_projects(conn):
        project_id = project["id"]
        if db_mod.get_stage(conn, project_id, "styleboard") is not None:
            continue

        run_dir = repo_root / "runs" / project["run_id"]
        world_block = None
        if visual_def is not None:
            visual_latest = artifacts.latest_artifact_path(run_dir / stage_dir_name(visual_def))
            if visual_latest is not None:
                _meta, body = artifacts.parse_frontmatter(
                    visual_latest.read_text(encoding="utf-8")
                )
                world_block = extract_world_lock_block(body)

        visual_row = db_mod.get_stage(conn, project_id, "visual")
        got_past_visual = visual_row is not None and visual_row["status"] in _PAST_VISUAL

        if world_block is not None:
            stage_dir = run_dir / stage_dir_name(stage_def)
            artifacts.write_artifact(
                stage_dir,
                1,
                {
                    "schema_version": 1,
                    "run_id": project["run_id"],
                    "stage": stage_def.skill,
                    "version": 1,
                    "status": "final",
                    "created_at": now,
                    "finalized_at": now,
                    "supersedes": None,
                    "depends_on": [],
                    "backfilled": True,
                },
                f"=== STYLEBOARD — {project['run_id']} (backfilled) ===\n\n"
                f"{world_block}\n\n"
                "BINDINGS\n"
                "  none — this styleboard was reconstructed from an existing prompt sheet's\n"
                "  WORLD LOCK block. Its shots carry literal --sref codes, not slots.\n\n"
                "DISCOVERY REQUESTS\n"
                "  none\n",
            )
            status = StageStatus.APPROVED.value
        elif got_past_visual:
            # Past visual but no liftable world lock: approve anyway rather than wedge a
            # project that is already finished. There is nothing to reconstruct.
            status = StageStatus.APPROVED.value
        else:
            scripting_row = db_mod.get_stage(conn, project_id, "scripting")
            status = (
                StageStatus.READY.value
                if scripting_row is not None
                and scripting_row["status"] == StageStatus.APPROVED.value
                else StageStatus.LOCKED.value
            )

        row_id = db_mod.create_stage_row(conn, project_id, "styleboard", status)
        if status == StageStatus.APPROVED.value:
            db_mod.update_stage_status(conn, row_id, status, approved_at=now)
        (run_dir / stage_dir_name(stage_def)).mkdir(parents=True, exist_ok=True)
        touched.append(project_id)

    return touched
