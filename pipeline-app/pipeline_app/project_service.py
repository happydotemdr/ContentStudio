import datetime
import sqlite3
from pathlib import Path

from pipeline_app import db as db_mod
from pipeline_app.pipeline_config import StageDef, stage_dir_name
from pipeline_app.state_machine import compute_initial_status


def create_project(
    conn: sqlite3.Connection,
    repo_root: Path,
    slug: str,
    brand: str,
    stage_defs: list[StageDef],
    now: datetime.datetime | None = None,
) -> dict:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    run_id = f"{slug}-{now.strftime('%Y%m%d-%H%M%S')}"
    project_id = db_mod.create_project(conn, run_id, slug, brand, now.isoformat())

    run_dir = repo_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    applicable = [s for s in stage_defs if s.brand_scope is None or s.brand_scope == brand]
    for stage in applicable:
        status = compute_initial_status(stage.depends_on)
        db_mod.create_stage_row(conn, project_id, stage.id, status.value)
        (run_dir / stage_dir_name(stage)).mkdir(parents=True, exist_ok=True)

    return {"project_id": project_id, "run_id": run_id, "run_dir": run_dir}
