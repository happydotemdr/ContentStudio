import datetime
import sqlite3
from pathlib import Path

from pipeline_app import artifacts, db as db_mod, obs
from pipeline_app.gates import GATE_REGISTRY
from pipeline_app.pipeline_config import StageDef, stage_dir_name
from pipeline_app.state_machine import StageStatus, is_locked_or_running, stages_to_unlock

KNOWN_STATUSES = frozenset({"pass", "fail", "error"})


def classify_gates(stage_id: str, recorded: list[dict]) -> list[dict]:
    """One entry per gate, carrying `state` and the `blocking` verdict.

    The ONE place a gate result is judged. approve_stage used to consult
    GATE_REGISTRY for a never-ran gate while stage_page's has_failing_gate only
    looked for fail/error, so the page and the 409 disagreed -- that disagreement
    IS E-03. Every surface reads this list: the approve decision, gate_view, and
    has_blocking_gate. Only an explicit "pass" is not blocking (A-35).
    """
    reported = {g.get("name") for g in recorded}
    classified = []
    for g in recorded:
        status = g.get("status")
        state = {
            "pass": "passed", "fail": "failed", "error": "errored",
        }.get(status, "unknown")
        classified.append({
            "name": g.get("name"), "state": state, "status_raw": status,
            "blocking": state != "passed", "findings": g.get("findings") or [],
        })
    classified.extend({
        "name": name, "state": "never_ran", "status_raw": None,
        "blocking": True, "findings": [],
    } for name, _runner in GATE_REGISTRY.get(stage_id, []) if name not in reported)
    return classified


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
    # `recorded` is whatever yaml.safe_load produced from hand-writable
    # frontmatter (grounding's most acutely) -- a string, scalar, or
    # list-of-strings would otherwise reach classify_gates's `.get()`
    # comprehension and surface as an unhandled 500, not the 409 every other
    # approval conflict produces (A-36).
    if not isinstance(recorded, list) or any(not isinstance(g, dict) for g in recorded):
        raise ValueError(
            f"Stage '{stage_id}': the `gates` block in {latest.name} is not a list of "
            f"gate results (found {type(recorded).__name__}). Fix the artifact's "
            "frontmatter, or regenerate the stage."
        )
    classified = classify_gates(stage_id, recorded)
    blocking = [g for g in classified if g["blocking"]]

    # Recorded here regardless of override_reason: an override silences the
    # 409 the operator sees, but a status the codebase doesn't recognize is a
    # vocabulary drift bug that must stay findable in `events` even when
    # someone overrides past it (A-35 SURFACING).
    for g in blocking:
        if g["state"] == "unknown":
            obs.record_event(
                conn, kind="gate.unknown_status", severity="warning", source="approval_service",
                message=(f"gate {g['name']!r} on stage '{stage_id}' recorded status "
                          f"{g['status_raw']!r}, which is not one of {sorted(KNOWN_STATUSES)}"),
                detail={"project_id": project_id, "stage_id": stage_id},
            )

    if blocking and not override_reason:
        problems = []
        for g in blocking:
            if g["state"] == "never_ran":
                problems.append(f"{g['name']} (never ran -- no result in the artifact)")
            elif g["state"] == "unknown":
                problems.append(
                    f"{g['name']} (unrecognized status {g['status_raw']!r} -- only 'pass' passes)"
                )
            else:
                problems.append(f"{g['name']} ({g['status_raw']})")
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
    with db_mod.transaction(conn):
        db_mod.update_stage_status(conn, stage_row["id"], StageStatus.APPROVED.value, approved_at=now)

        all_rows = db_mod.list_stages(conn, project_id)
        approved_ids = {r["stage_id"] for r in all_rows if r["status"] == StageStatus.APPROVED.value}
        newly_unlocked = stages_to_unlock(stage_defs, approved_ids)

        for uid in newly_unlocked:
            row = db_mod.get_stage(conn, project_id, uid)
            if row is not None and row["status"] == StageStatus.LOCKED.value:
                db_mod.update_stage_status(conn, row["id"], StageStatus.READY.value)

    return newly_unlocked
