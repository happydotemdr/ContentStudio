import contextlib
import datetime
import json
import sqlite3
import time
from pathlib import Path
from typing import AsyncIterator

from pipeline_app import artifacts, cli_runner, db as db_mod, prompt_builder
from pipeline_app.pipeline_config import StageDef, stage_dir_name
from pipeline_app.state_machine import StageStatus, is_stale


class TurnAlreadyRunningError(Exception):
    pass


def any_turn_running(conn: sqlite3.Connection) -> bool:
    return len(db_mod.list_running_turns(conn)) > 0


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _relpath(path: Path, run_dir: Path) -> str:
    return str(path.relative_to(run_dir)).replace("\\", "/")


def _current_upstream_hashes(run_dir: Path, upstream_defs: list[StageDef]) -> dict[str, str]:
    """Hashes keyed by the CURRENT latest artifact path per upstream stage —
    not the exact path recorded in some dependent's frontmatter. Artifacts are
    never mutated in place (regenerating writes artifact.v2.md, v1 is left
    untouched), so re-hashing the recorded path would always match and
    staleness would never fire. Comparing against the current latest path
    instead means a regenerate changes which path is "current" for that
    stage, so a stale dependent's recorded path stops matching anything here
    (state_machine.is_stale treats a missing key as a mismatch)."""
    hashes: dict[str, str] = {}
    for up in upstream_defs:
        up_dir = run_dir / stage_dir_name(up)
        up_latest = artifacts.latest_artifact_path(up_dir)
        if up_latest is not None:
            hashes[_relpath(up_latest, run_dir)] = artifacts.compute_sha256(up_latest)
    return hashes


def propagate_staleness(
    conn: sqlite3.Connection,
    run_dir: Path,
    all_stage_defs: list[StageDef],
    project_id: int,
    changed_stage_id: str,
) -> None:
    """Flip approved downstream stages to stale when changed_stage_id's latest
    artifact no longer matches the hash they recorded, then cascade: anything
    approved that was built on a stage this call just made stale is stale too.
    Public because both paths that mint a new artifact version call it:
    run_stage_turn (chat / regenerate) and
    routes.stages.edit_stage_output_route (hand edit)."""
    newly_stale: list[str] = []
    for dep_stage in _dependents_of(all_stage_defs, changed_stage_id):
        row = db_mod.get_stage(conn, project_id, dep_stage.id)
        if row is None or row["status"] != StageStatus.APPROVED.value:
            continue
        stage_dir = run_dir / stage_dir_name(dep_stage)
        latest = artifacts.latest_artifact_path(stage_dir)
        if latest is None:
            continue
        meta, _ = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))
        recorded = meta.get("depends_on") or []
        dep_upstream_defs = [s for s in all_stage_defs if s.id in dep_stage.depends_on]
        current_hashes = _current_upstream_hashes(run_dir, dep_upstream_defs)
        if is_stale(recorded, current_hashes):
            db_mod.update_stage_status(conn, row["id"], StageStatus.STALE.value)
            newly_stale.append(dep_stage.id)

    # Second level and beyond is status-driven, not hash-driven: a stale
    # stage's own artifact file is never rewritten (only its DB row changes),
    # so its dependents' recorded hashes still match and is_stale would say
    # False. Being built on a stage that is itself stale is what makes them
    # stale. Terminates regardless of topology because a stage is enqueued
    # only at the moment it leaves `approved`, so at most once.
    queue = list(newly_stale)
    while queue:
        stale_stage_id = queue.pop()
        for dep_stage in _dependents_of(all_stage_defs, stale_stage_id):
            row = db_mod.get_stage(conn, project_id, dep_stage.id)
            if row is None or row["status"] != StageStatus.APPROVED.value:
                continue
            db_mod.update_stage_status(conn, row["id"], StageStatus.STALE.value)
            queue.append(dep_stage.id)


def _dependents_of(all_stage_defs: list[StageDef], stage_id: str) -> list[StageDef]:
    return [s for s in all_stage_defs if stage_id in s.depends_on]


async def run_stage_turn(
    conn: sqlite3.Connection,
    repo_root: Path,
    run_dir: Path,
    templates_dir: Path,
    project_id: int,
    run_id: str,
    stage_def: StageDef,
    all_stage_defs: list[StageDef],
    user_message: str,
    grounding_pointer: str | None = None,
    finalize_artifact: bool = True,
) -> AsyncIterator[dict]:
    if any_turn_running(conn):
        raise TurnAlreadyRunningError("Another stage turn is already running.")

    stage_row = db_mod.get_stage(conn, project_id, stage_def.id)
    stage_dir = run_dir / stage_dir_name(stage_def)
    events_dir = stage_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    events_path = events_dir / f"{int(time.time() * 1000)}.jsonl"

    turn_id = db_mod.create_turn(conn, stage_row["id"], "running", _utcnow(), str(events_path))
    db_mod.update_stage_status(conn, stage_row["id"], StageStatus.RUNNING.value)

    raw_output_path = stage_dir / "raw_output.md"
    upstream_stage_defs = [s for s in all_stage_defs if s.id in stage_def.depends_on]
    upstream_paths = [
        p for p in (
            artifacts.latest_artifact_path(run_dir / stage_dir_name(up))
            for up in upstream_stage_defs
        ) if p is not None
    ]

    is_first_turn = stage_row["claude_session_id"] is None
    if is_first_turn:
        input_files = [str(p) for p in upstream_paths]
        prompt = prompt_builder.render_kickoff_prompt(templates_dir, stage_def.id, {
            "skill": stage_def.skill,
            "user_message": user_message,
            "grounding_pointer": grounding_pointer,
            "input_file": input_files[0] if input_files else None,
            "input_files": input_files,
            "raw_output_path": str(raw_output_path),
        })
        resume_id = None
    else:
        prompt = user_message
        resume_id = stage_row["claude_session_id"]

    before_mtime = raw_output_path.stat().st_mtime if raw_output_path.exists() else None

    collected: list[dict] = []
    turn_stream = cli_runner.stream_claude_turn(
        prompt, repo_root, resume_id,
        settings_path=cli_runner.scoped_permissions_settings(),
    )
    try:
        async with contextlib.aclosing(turn_stream):
            with events_path.open("a", encoding="utf-8") as f:
                async for event in turn_stream:
                    collected.append(event)
                    f.write(json.dumps(event) + "\n")
                    yield event
    except BaseException:
        # Client disconnect (GeneratorExit) or any turn-time exception: the
        # `aclosing` context still guarantees stream_claude_turn's own
        # finally block runs and kills the subprocess. Record the turn as
        # aborted rather than leaving it `running` forever (which would wedge
        # the app's single-flight lock) and stop — no further DB/artifact
        # work is attempted for a turn that didn't finish normally.
        db_mod.update_turn(conn, turn_id, "aborted", _utcnow())
        raise

    result = cli_runner.extract_turn_result(collected)
    db_mod.update_turn(
        conn, turn_id,
        "complete" if result.success else "failed",
        _utcnow(), result.cost_usd,
    )
    if result.session_id:
        db_mod.update_stage_session(conn, stage_row["id"], result.session_id)

    if not finalize_artifact:
        return

    artifact_written = raw_output_path.exists() and (
        before_mtime is None or raw_output_path.stat().st_mtime != before_mtime
    )

    if not artifact_written:
        db_mod.update_stage_status(conn, stage_row["id"], StageStatus.NO_ARTIFACT.value)
        return

    version = artifacts.next_version_number(stage_dir)
    depends_on = [
        {"path": _relpath(p, run_dir), "sha256": artifacts.compute_sha256(p)}
        for p in upstream_paths
    ]
    body = raw_output_path.read_text(encoding="utf-8")
    meta = {
        "schema_version": 1,
        "run_id": run_id,
        "stage": stage_def.skill,
        "version": version,
        "status": "draft",
        "created_at": _utcnow(),
        "finalized_at": None,
        "supersedes": f"artifact.v{version - 1}.md" if version > 1 else None,
        "depends_on": depends_on,
    }
    artifacts.write_artifact(stage_dir, version, meta, body)
    db_mod.update_stage_status(conn, stage_row["id"], StageStatus.AWAITING_REVIEW.value)
    propagate_staleness(conn, run_dir, all_stage_defs, project_id, stage_def.id)
