import datetime
import sqlite3
from pathlib import Path

from pipeline_app import artifacts, db as db_mod
from pipeline_app.gates import GATE_REGISTRY
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

    # Registry-aware, deliberately: reading only what the frontmatter happens to
    # carry makes an ABSENT `gates` key indistinguishable from a clean run. Any
    # artifact minted before this stage had gates -- or by any future path that
    # forgets to run them -- would otherwise approve with no gate having run at
    # all, which is the same silent pass of an unknown result the whole design
    # is built to refuse. A registered gate with no recorded result blocks
    # exactly as a failing one does, and says which of the two it is.
    recorded = latest_meta.get("gates") or []
    failing = [g for g in recorded if g.get("status") in ("fail", "error")]
    reported_names = {g.get("name") for g in recorded}
    never_ran = [
        name for name, _runner in GATE_REGISTRY.get(stage_id, [])
        if name not in reported_names
    ]
    if (failing or never_ran) and not override_reason:
        problems = [f"{g['name']} ({g['status']})" for g in failing]
        problems += [f"{name} (never ran -- no result in the artifact)" for name in never_ran]
        raise ValueError(
            f"Stage '{stage_id}' has a blocking gate: {', '.join(problems)}. "
            "Fix the findings and regenerate, or approve with an override reason."
        )

    already_final = latest_meta.get("status") == "final"
    if stage_id != "grounding":
        if not already_final:
            artifacts.stamp_final(latest, now, gate_override_reason=override_reason)
        elif override_reason:
            # already_final skips stamp_final entirely (see the no-churn
            # comment above), but an override reason supplied on THIS call is
            # still a real decision and must not be dropped just because the
            # artifact was already final -- see artifacts.record_gate_override.
            artifacts.record_gate_override(latest, override_reason)
    db_mod.update_stage_status(conn, stage_row["id"], StageStatus.APPROVED.value, approved_at=now)

    all_rows = db_mod.list_stages(conn, project_id)
    approved_ids = {r["stage_id"] for r in all_rows if r["status"] == StageStatus.APPROVED.value}
    newly_unlocked = stages_to_unlock(stage_defs, approved_ids)

    for uid in newly_unlocked:
        row = db_mod.get_stage(conn, project_id, uid)
        if row is not None and row["status"] == StageStatus.LOCKED.value:
            db_mod.update_stage_status(conn, row["id"], StageStatus.READY.value)

    return newly_unlocked
