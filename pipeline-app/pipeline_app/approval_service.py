import datetime
import sqlite3
from pathlib import Path

from pipeline_app import artifacts, db as db_mod
from pipeline_app.pipeline_config import StageDef, stage_dir_name
from pipeline_app.state_machine import StageStatus, stages_to_unlock


def approve_stage(
    conn: sqlite3.Connection,
    repo_root: Path,
    run_dir: Path,
    project_id: int,
    stage_defs: list[StageDef],
    stage_id: str,
) -> list[str]:
    stage_row = db_mod.get_stage(conn, project_id, stage_id)
    stage_def = next(s for s in stage_defs if s.id == stage_id)
    stage_dir = run_dir / stage_dir_name(stage_def)

    latest = artifacts.resolve_latest_artifact(repo_root, stage_id, stage_dir)
    if latest is None:
        raise ValueError(f"No artifact to approve for stage '{stage_id}'.")

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    artifacts.stamp_final(latest, now)
    db_mod.update_stage_status(conn, stage_row["id"], StageStatus.APPROVED.value, approved_at=now)

    all_rows = db_mod.list_stages(conn, project_id)
    approved_ids = {r["stage_id"] for r in all_rows if r["status"] == StageStatus.APPROVED.value}
    newly_unlocked = stages_to_unlock(stage_defs, approved_ids)

    for uid in newly_unlocked:
        row = db_mod.get_stage(conn, project_id, uid)
        if row is not None and row["status"] == StageStatus.LOCKED.value:
            db_mod.update_stage_status(conn, row["id"], StageStatus.READY.value)

    return newly_unlocked
