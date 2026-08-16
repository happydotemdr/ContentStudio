import contextlib
import datetime
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import AsyncIterator

from pipeline_app import artifacts, cli_runner, db as db_mod, gates, grounding_service, obs, prompt_builder
from pipeline_app.pipeline_config import StageDef, stage_dir_name
from pipeline_app.state_machine import StageStatus, is_locked_or_running, is_stale


class TurnAlreadyRunningError(Exception):
    pass


class StageNotRunnableError(Exception):
    pass


class MissingUpstreamArtifactError(StageNotRunnableError):
    """A declared, required dependency resolved to no artifact on disk. Refusing
    is the point: rendering a prompt that names a nonexistent path (or the
    literal string "None") makes the model invent its way around the gap."""


def any_turn_running(conn: sqlite3.Connection) -> bool:
    return len(db_mod.list_running_turns(conn)) > 0


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _relpath(path: Path, run_dir: Path) -> str:
    return str(path.relative_to(run_dir)).replace("\\", "/")


def _current_upstream_hashes(
    run_dir: Path, upstream_defs: list[StageDef], repo_root: Path | None = None
) -> dict[str, str]:
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
        if up.id == "grounding":
            if repo_root is None:
                # Never silent: without a root the pointer cannot be followed, so
                # this upstream would simply vanish from the hash set and its
                # dependents would look permanently fresh (A-14).
                obs.log("staleness.pointer_upstream_unresolvable", level="warning",
                        upstream=up.id, run_dir=str(run_dir))
                continue
            up_latest = artifacts.resolve_latest_artifact(repo_root, up.id, up_dir)
        else:
            up_latest = artifacts.latest_artifact_path(up_dir)
        if up_latest is not None:
            hashes[_relpath(up_latest, run_dir)] = artifacts.compute_sha256(up_latest)
    return hashes


_INVALIDATABLE = (StageStatus.APPROVED.value, StageStatus.AWAITING_REVIEW.value)


def propagate_staleness(
    conn: sqlite3.Connection,
    run_dir: Path,
    all_stage_defs: list[StageDef],
    project_id: int,
    changed_stage_id: str,
    repo_root: Path | None = None,
) -> None:
    """Flip approved (or awaiting-review) downstream stages to stale when
    changed_stage_id's latest artifact no longer matches the hash they
    recorded, then cascade: anything invalidatable that was built on a stage
    this call just made stale is stale too. A draft sitting at
    awaiting_review is included -- it was built on the old upstream just as
    much as an approved artifact was, and approving it must not silently
    launder in the stale input (A-44). `locked` stages are never included:
    they have not run yet, so there is nothing built on stale input to flag.
    Public because both paths that mint a new artifact version call it:
    run_stage_turn (chat / regenerate) and
    routes.stages.edit_stage_output_route (hand edit)."""
    newly_stale: list[str] = []
    for dep_stage in _dependents_of(all_stage_defs, changed_stage_id):
        row = db_mod.get_stage(conn, project_id, dep_stage.id)
        if row is None or row["status"] not in _INVALIDATABLE:
            continue
        stage_dir = run_dir / stage_dir_name(dep_stage)
        latest = artifacts.latest_artifact_path(stage_dir)
        if latest is None:
            continue
        meta, _ = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))
        recorded = meta.get("depends_on") or []
        dep_upstream_defs = [s for s in all_stage_defs if s.id in dep_stage.all_depends_on]
        current_hashes = _current_upstream_hashes(run_dir, dep_upstream_defs, repo_root=repo_root)
        if is_stale(recorded, current_hashes):
            db_mod.update_stage_status(conn, row["id"], StageStatus.STALE.value)
            newly_stale.append(dep_stage.id)

    # Second level and beyond is status-driven, not hash-driven: a stale
    # stage's own artifact file is never rewritten (only its DB row changes),
    # so its dependents' recorded hashes still match and is_stale would say
    # False. Being built on a stage that is itself stale is what makes them
    # stale. Terminates regardless of topology because a stage is enqueued
    # only at the moment it leaves the invalidatable set, so at most once.
    queue = list(newly_stale)
    while queue:
        stale_stage_id = queue.pop()
        for dep_stage in _dependents_of(all_stage_defs, stale_stage_id):
            row = db_mod.get_stage(conn, project_id, dep_stage.id)
            if row is None or row["status"] not in _INVALIDATABLE:
                continue
            db_mod.update_stage_status(conn, row["id"], StageStatus.STALE.value)
            queue.append(dep_stage.id)


def _dependents_of(all_stage_defs: list[StageDef], stage_id: str) -> list[StageDef]:
    return [s for s in all_stage_defs if stage_id in s.all_depends_on]


def propagate_grounding_staleness(
    conn: sqlite3.Connection, repo_root: Path, run_dir: Path,
    all_stage_defs: list[StageDef], project_id: int,
) -> list[str]:
    """Grounding's artifact lives in rgs-briefs/ behind a pointer and no stage
    lists it in depends_on, so the hash cascade cannot see it. Any stage whose
    artifact recorded a brief path that is no longer the pointer target was built
    on a superseded thinker/research pairing (A-13). Public because the grounding
    turn route is what repoints the pointer and should call it there too."""
    current = grounding_service.read_pointer(run_dir / "00-grounding")
    if current is None:
        return []
    stale: list[str] = []
    for stage_def in all_stage_defs:
        if stage_def.id == "grounding":
            continue
        row = db_mod.get_stage(conn, project_id, stage_def.id)
        if row is None or row["status"] not in _INVALIDATABLE:
            continue
        latest = artifacts.latest_artifact_path(run_dir / stage_dir_name(stage_def))
        if latest is None:
            continue
        meta, _body = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))
        briefs = [d.get("path") for d in (meta.get("depends_on") or [])
                  if str(d.get("path", "")).startswith("rgs-briefs/")]
        if briefs and current not in briefs:
            db_mod.update_stage_status(conn, row["id"], StageStatus.STALE.value)
            stale.append(stage_def.id)
    if stale:
        obs.record_event(
            conn, kind="handoff.grounding_repointed", severity="warning", source="turn_service",
            message=f"grounding brief is now {current!r}; marked stale: {', '.join(stale)}",
            detail={"pointer": current, "stale": stale},
        )
    return stale


_VERSION_RE = re.compile(r"^artifact\.v(\d+)\.md$")


def _approved_artifact_path(stage_dir: Path) -> Path | None:
    """The newest artifact a human actually approved -- approval_service.
    stamp_final writes `status: final` into the frontmatter -- not merely the
    newest file on disk. A gate keyed to an unapproved draft records a pass
    against a world the operator never accepted (A-32)."""
    versions = []
    for path in stage_dir.glob("artifact.v*.md"):
        match = _VERSION_RE.match(path.name)
        if match:
            versions.append((int(match.group(1)), path))
    for _version, path in sorted(versions, reverse=True):
        meta, _body = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
        if meta.get("status") == "final":
            return path
    return None


def _session_inputs_path(stage_dir: Path) -> Path:
    return stage_dir / "session_inputs.json"


def _write_session_inputs(stage_dir: Path, run_dir: Path, inputs: dict[str, str]) -> None:
    """What the CLI session for this stage has actually been shown. Kept beside
    the events log rather than in the DB so no schema change is needed."""
    stage_dir.mkdir(parents=True, exist_ok=True)
    snapshot = {sid: _relpath(Path(p), run_dir) for sid, p in inputs.items()}
    _session_inputs_path(stage_dir).write_text(
        json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")


def _read_session_inputs(stage_dir: Path) -> dict[str, str]:
    path = _session_inputs_path(stage_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        obs.log("handoff.session_inputs_unreadable", level="warning", path=str(path))
        return {}
    return data if isinstance(data, dict) else {}


def _resumed_prompt(conn, stage_dir: Path, run_dir: Path, stage_def: StageDef,
                    inputs: dict[str, str], user_message: str) -> str:
    """A resumed session's transcript still names the artifact versions it was
    opened on. If any upstream has since been superseded, say so in the prompt --
    otherwise the model answers from the old paths while the artifact it writes
    records the new ones as its provenance (A-05)."""
    seen = _read_session_inputs(stage_dir)
    current = {sid: _relpath(Path(p), run_dir) for sid, p in inputs.items()}
    if seen == current:
        return user_message
    changed = sorted(sid for sid in current if seen.get(sid) != current[sid])
    dropped = sorted(sid for sid in seen if sid not in current)
    lines = ["UPSTREAM CHANGED SINCE THIS SESSION LAST READ IT."]
    lines += [f"- {sid}: now `{current[sid]}` (was `{seen.get(sid, 'absent')}`)" for sid in changed]
    lines += [f"- {sid}: no longer available (was `{seen[sid]}`)" for sid in dropped]
    lines.append("Re-read every path above before answering; do not rely on the earlier version.")
    obs.record_event(
        conn, kind="handoff.upstream_changed", severity="warning", source="turn_service",
        message=f"stage '{stage_def.id}' resumed against changed upstream(s): {changed + dropped}",
        detail={"stage": stage_def.id, "changed": changed, "dropped": dropped,
                "seen": seen, "current": current},
    )
    _write_session_inputs(stage_dir, run_dir, inputs)
    return "\n".join(lines) + "\n\n" + user_message


def _resume_failed(events: list[dict]) -> bool:
    """The CLI never opened the resumed session: no system/init carrying a
    session id, and the turn ended in error. Both halves matter -- an error on a
    session that DID open is an ordinary failed turn, not a dead id."""
    opened = any(
        e.get("type") == "system" and e.get("subtype") == "init" and e.get("session_id")
        for e in events
    )
    errored = (not events) or any(e.get("type") == "result" and e.get("is_error") for e in events)
    return not opened and errored


def _resolve_upstream(repo_root: Path, run_dir: Path, up: StageDef) -> Path | None:
    """The artifact an upstream stage hands downstream. Grounding's real output
    lives in rgs-briefs/ behind a pointer, so it needs the pointer-aware
    resolver (A-14); every other stage hands down its approved version."""
    stage_dir = run_dir / stage_dir_name(up)
    if up.id == "grounding":
        return artifacts.resolve_latest_artifact(repo_root, up.id, stage_dir)
    return _approved_artifact_path(stage_dir)


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
    if is_locked_or_running(stage_row["status"]):
        raise StageNotRunnableError(
            f"Stage '{stage_def.id}' is {stage_row['status']} and cannot accept chat messages yet."
        )
    stage_dir = run_dir / stage_dir_name(stage_def)
    raw_output_path = stage_dir / "raw_output.md"

    required_defs = [s for s in all_stage_defs if s.id in stage_def.depends_on]
    optional_defs = [s for s in all_stage_defs if s.id in stage_def.optional_depends_on]

    # Keyed by stage id, not a list: templates address upstreams by name
    # (prompt_builder.KICKOFF_CONTEXT_KEYS), so positional drift when an
    # upstream drops out is structurally impossible (A-09/A-16).
    inputs: dict[str, str] = {}
    missing: list[str] = []
    for up in required_defs:
        path = _resolve_upstream(repo_root, run_dir, up)
        if path is None:
            missing.append(up.id)
        else:
            inputs[up.id] = str(path)
    if missing:
        obs.record_event(
            conn, kind="handoff.upstream_missing", severity="error", source="turn_service",
            message=(f"stage '{stage_def.id}' cannot start: no approved artifact for "
                     f"{', '.join(missing)}"),
            detail={"stage": stage_def.id, "missing": missing},
        )
        raise MissingUpstreamArtifactError(
            f"Stage '{stage_def.id}' requires {missing} but no approved artifact exists for "
            "them. Approve or regenerate the upstream stage first."
        )
    for up in optional_defs:
        path = _resolve_upstream(repo_root, run_dir, up)
        if path is None:
            obs.log("handoff.optional_upstream_absent", level="info",
                    stage=stage_def.id, upstream=up.id)
        else:
            inputs[up.id] = str(path)
    upstream_paths = [Path(p) for p in inputs.values()]
    upstream_by_stage = {sid: Path(p) for sid, p in inputs.items()}

    events_dir = stage_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    events_path = events_dir / f"{int(time.time() * 1000)}.jsonl"

    turn_id = db_mod.create_turn(conn, stage_row["id"], "running", _utcnow(), str(events_path))
    prior_status = stage_row["status"]
    db_mod.update_stage_status(conn, stage_row["id"], StageStatus.RUNNING.value)

    is_first_turn = stage_row["claude_session_id"] is None
    if is_first_turn:
        prompt = prompt_builder.render_kickoff_prompt(templates_dir, stage_def.id, {
            "skill": stage_def.skill,
            "user_message": user_message,
            "grounding_pointer": grounding_pointer,
            "inputs": inputs,
            "raw_output_path": str(raw_output_path),
        })
        resume_id = None
        _write_session_inputs(stage_dir, run_dir, inputs)
    else:
        prompt = _resumed_prompt(conn, stage_dir, run_dir, stage_def, inputs, user_message)
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
                    # Captured the moment it's known, not just on success --
                    # an aborted turn (see except below) still resumes from
                    # this session on the next attempt instead of re-paying
                    # for the whole kickoff prompt.
                    if (
                        event.get("type") == "system"
                        and event.get("subtype") == "init"
                        and event.get("session_id")
                    ):
                        db_mod.update_stage_session(conn, stage_row["id"], event["session_id"])
                    yield event
    except BaseException:
        # Client disconnect (GeneratorExit) or any turn-time exception: the
        # `aclosing` context still guarantees stream_claude_turn's own
        # finally block runs and kills the subprocess. Record the turn as
        # aborted rather than leaving it `running` forever (which would wedge
        # the app's single-flight lock) and stop — no further DB/artifact
        # work is attempted for a turn that didn't finish normally.
        #
        # The stage row also has to come back out of RUNNING here, not just
        # the turn: an aborted turn is invisible to preflight's startup
        # sweep (it only looks for turns still `running`), so without this
        # the stage would stay wedged at RUNNING permanently -- even across
        # a restart -- since chat/approve/edit all reject a running stage.
        # Restore exactly what the turn interrupted. Re-deriving the status from
        # artifact existence (the old rule) always produced AWAITING_REVIEW for a
        # stage that had any artifact, which laundered `stale` -- and
        # `approved` -- into `awaiting_review` on nothing more than an aborted
        # turn, erasing the stage-page warning permanently (A-46).
        db_mod.update_stage_status(conn, stage_row["id"], prior_status)
        # extract_turn_result is safe to call on a partial `collected` -- it
        # simply returns None fields for whatever never arrived. Covers the
        # rare case where a `result` event (and its cost) was captured just
        # before the disconnect, instead of always discarding it.
        partial = cli_runner.extract_turn_result(collected)
        db_mod.update_turn(conn, turn_id, "aborted", _utcnow(), partial.cost_usd)
        raise

    result = cli_runner.extract_turn_result(collected)
    db_mod.update_turn(
        conn, turn_id,
        "complete" if result.success else "failed",
        _utcnow(), result.cost_usd,
    )
    if resume_id is not None and _resume_failed(collected):
        db_mod.update_stage_session(conn, stage_row["id"], None)
        obs.record_event(
            conn, kind="handoff.session_unresumable", severity="warning", source="turn_service",
            message=(f"stage '{stage_def.id}' session {resume_id} could not be resumed; cleared "
                     "so the next turn re-renders the kickoff prompt"),
            detail={"stage": stage_def.id, "session_id": resume_id},
        )
    elif result.session_id:
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
    # The grounding brief is a real input that arrives out-of-band (routes.stages
    # resolves the pointer and passes it as grounding_pointer), so it never
    # appears in upstream_paths. Recording it here is what lets a re-pointed
    # brief be detected at all -- modelling grounding as a depends_on edge is
    # forbidden by the brand-scope rule (A-12), since ideation is unscoped.
    if grounding_pointer:
        brief = repo_root / grounding_pointer
        if brief.exists():
            depends_on.append({"path": grounding_pointer,
                               "sha256": artifacts.compute_sha256(brief)})
        else:
            obs.record_event(
                conn, kind="handoff.grounding_brief_missing", severity="error",
                source="turn_service",
                message=f"stage '{stage_def.id}' was passed grounding pointer "
                        f"'{grounding_pointer}' but no such file exists",
                detail={"stage": stage_def.id, "pointer": grounding_pointer},
            )
    gate_results = gates.run_gates_for_stage(
        repo_root, stage_def.id, raw_output_path, upstream_by_stage
    )
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
        "gates": gate_results,
    }
    artifacts.write_artifact(stage_dir, version, meta, body)
    db_mod.update_stage_status(conn, stage_row["id"], StageStatus.AWAITING_REVIEW.value)
    propagate_staleness(conn, run_dir, all_stage_defs, project_id, stage_def.id, repo_root=repo_root)
    propagate_grounding_staleness(conn, repo_root, run_dir, all_stage_defs, project_id)
