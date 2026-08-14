import datetime
import shutil
import sqlite3
from pathlib import Path
from typing import Callable

from pipeline_app import artifacts, db as db_mod, obs
from pipeline_app.cli_runner import resolve_claude_binary
from pipeline_app.pipeline_config import StageDef, stage_dir_name
from pipeline_app.state_machine import StageStatus


def reconcile_orphaned_turns(conn: sqlite3.Connection, repo_root: Path, stage_defs: list[StageDef]) -> int:
    stage_defs_by_id = {s.id: s for s in stage_defs}
    running = db_mod.list_running_turns(conn)
    for turn in running:
        db_mod.update_turn(conn, turn["id"], "orphaned")
        _unwedge_stage(conn, repo_root, stage_defs_by_id, turn["stage_row_id"], turn["id"])
    return len(running)


def _unwedge_stage(
    conn: sqlite3.Connection,
    repo_root: Path,
    stage_defs_by_id: dict[str, StageDef],
    stage_row_id: int,
    turn_id: int,
) -> None:
    stage_row = db_mod.get_stage_by_row_id(conn, stage_row_id)
    if stage_row is None or stage_row["status"] != StageStatus.RUNNING.value:
        return
    stage_def = stage_defs_by_id.get(stage_row["stage_id"])
    if stage_def is None:
        return
    project = db_mod.get_project(conn, stage_row["project_id"])
    if project is None:
        return
    run_dir = repo_root / "runs" / project["run_id"]
    stage_dir = run_dir / stage_dir_name(stage_def)
    latest = artifacts.resolve_latest_artifact(repo_root, stage_def.id, stage_dir)
    new_status = StageStatus.AWAITING_REVIEW.value if latest is not None else StageStatus.READY.value
    db_mod.update_stage_status(conn, stage_row["id"], new_status)
    if latest is not None:
        # A-77: the artifact that resolves here belongs to a PREVIOUS turn. Say
        # so, or an operator approves it believing the killed turn produced it.
        obs.record_event(
            conn, kind="turn.orphaned", severity="warning", source="preflight",
            message=(
                f"turn {turn_id} on {project['run_id']}/{stage_def.id} was orphaned; "
                f"the stage is showing {latest.name} from an earlier turn"
            ),
            detail={"project_id": project["id"], "stage_id": stage_def.id,
                    "turn_id": turn_id, "artifact": latest.name},
        )
    _quarantine_raw_output(stage_dir)


def _quarantine_raw_output(stage_dir: Path) -> Path | None:
    """Move a dead turn's scratch aside so it cannot masquerade as the next
    turn's before_mtime baseline (A-77). Renamed, never deleted -- a partial
    turn's output is sometimes the only record of what went wrong."""
    raw = stage_dir / "raw_output.md"
    if not raw.is_file():
        return None
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = stage_dir / f"raw_output.orphaned-{stamp}.md"
    raw.replace(target)
    return target


def check_cli_available(which_fn: Callable[[str], str | None] = shutil.which) -> dict:
    try:
        path = resolve_claude_binary(which_fn)
        return {"available": True, "path": path, "error": None}
    except FileNotFoundError as exc:
        return {"available": False, "path": None, "error": str(exc)}
