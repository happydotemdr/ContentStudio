import datetime
import sqlite3
from pathlib import Path

from pipeline_app import artifacts, db as db_mod
from pipeline_app.pipeline_config import StageDef, stage_dir_name
from pipeline_app.state_machine import StageStatus, is_locked_or_running, stages_to_unlock


def approve_stage(
    conn: sqlite3.Connection,
    repo_root: Path,
    run_dir: Path,
    project_id: int,
    stage_defs: list[StageDef],
    stage_id: str,
    override_reason: str | None = None,
) -> list[str]:
    stage_row = db_mod.get_stage(conn, project_id, stage_id)
    if is_locked_or_running(stage_row["status"]):
        raise ValueError(
            f"Stage '{stage_id}' is {stage_row['status']} and cannot be approved yet."
        )
    stage_def = next(s for s in stage_defs if s.id == stage_id)
    stage_dir = run_dir / stage_dir_name(stage_def)

    latest = artifacts.resolve_latest_artifact(repo_root, stage_id, stage_dir)
    if latest is None:
        raise ValueError(f"No artifact to approve for stage '{stage_id}'.")

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # Re-approving a stage whose artifact is already stamped final must not
    # rewrite it: stamp_final changes finalized_at (and therefore the file's
    # sha256) every time it runs, and propagate_staleness's hash check would
    # treat that churn as a real change, spuriously flipping approved
    # dependents stale even though nothing substantive happened. Gated on
    # the artifact's own status, not the stage's DB row status -- a stale
    # stage (approved, then flipped stale by the cascade) still has an
    # already-final artifact on disk, and stage.html's override note makes
    # approving it directly (without regenerating) an encouraged path, not
    # an edge case.
    latest_meta, _ = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))

    failing = [
        g for g in (latest_meta.get("gates") or [])
        if g.get("status") in ("fail", "error")
    ]
    if failing and not override_reason:
        names = ", ".join(f"{g['name']} ({g['status']})" for g in failing)
        raise ValueError(
            f"Stage '{stage_id}' has a failing gate: {names}. "
            "Fix the findings and regenerate, or approve with an override reason."
        )

    already_final = latest_meta.get("status") == "final"
    if stage_id != "grounding" and not already_final:
        artifacts.stamp_final(latest, now, gate_override_reason=override_reason)
    db_mod.update_stage_status(conn, stage_row["id"], StageStatus.APPROVED.value, approved_at=now)

    all_rows = db_mod.list_stages(conn, project_id)
    approved_ids = {r["stage_id"] for r in all_rows if r["status"] == StageStatus.APPROVED.value}
    newly_unlocked = stages_to_unlock(stage_defs, approved_ids)

    for uid in newly_unlocked:
        row = db_mod.get_stage(conn, project_id, uid)
        if row is not None and row["status"] == StageStatus.LOCKED.value:
            db_mod.update_stage_status(conn, row["id"], StageStatus.READY.value)

    return newly_unlocked
