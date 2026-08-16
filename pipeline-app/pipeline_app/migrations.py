"""One-shot, idempotent schema/state migrations run at app startup.

Kept separate from db.py: db.py holds the durable query surface, this holds
corrections that exist only because the topology changed under projects that
were already on disk.
"""

import datetime
import re
import sqlite3
import sys
from pathlib import Path

import yaml

from pipeline_app import artifacts, db as db_mod, obs
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


class BackfillWouldOverwriteError(Exception):
    """A real artifact already occupies the styleboard stage directory."""


# Reading and parsing a legacy project's artifact off disk is the one part of this
# migration touching data this code doesn't control -- a hand-edited file, a partial
# write from a crashed prior run, a permissions problem. These are the exception
# categories that kind of damage actually raises. Deliberately NOT catching
# everything: a bug in this module's own logic (AttributeError, KeyError, a bad
# sqlite3 call) should still crash startup loudly rather than be silently skipped
# per-project. BackfillWouldOverwriteError (A-73) belongs here too: a real,
# hand-authored artifact occupying the stage directory is exactly the kind of
# on-disk fact this migration doesn't control, and one project's real artifact
# must not take the whole startup down for every other project.
_PER_PROJECT_RECOVERABLE = (
    OSError, UnicodeDecodeError, yaml.YAMLError, artifacts.MalformedArtifactError,
    BackfillWouldOverwriteError,
)


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


def _adoptable_synthetic(stage_dir: Path, run_id: str) -> Path | None:
    """This stage dir's current artifact if it is OUR OWN prior synthetic, else
    None -- and a raise if it is anyone else's.

    A-73: the migration was guarded only by "this project has no styleboard DB
    ROW". A filesystem check was never made, and the filesystem is the
    authority on whether an artifact exists -- the DB row is not.
    """
    latest = artifacts.latest_artifact_path(stage_dir)
    if latest is None:
        return None
    meta, _ = artifacts.read_artifact(latest)
    if meta.get("backfilled") is True and meta.get("run_id") == run_id:
        return latest
    raise BackfillWouldOverwriteError(
        f"{latest} already exists and was not written by this migration "
        f"(backfilled={meta.get('backfilled')!r}, run_id={meta.get('run_id')!r}); "
        "refusing to overwrite a real styleboard artifact"
    )


def _write_synthetic_artifact(
    stage_dir: Path, run_id: str, stage_def: StageDef, now: str, body: str,
    depends_on: list[dict],
) -> Path:
    stage_dir.mkdir(parents=True, exist_ok=True)
    adopted = _adoptable_synthetic(stage_dir, run_id)
    if adopted is not None:
        # Idempotent adoption -- see _backfill_one_project's docstring (A-73).
        return adopted
    reservation = artifacts.reserve_version(stage_dir)
    try:
        return artifacts.write_reserved_artifact(
            reservation,
            {
                "schema_version": 1,
                "run_id": run_id,
                "stage": stage_def.skill,
                "version": reservation.version,
                "status": "final",
                "created_at": now,
                "finalized_at": now,
                "supersedes": None,
                "depends_on": depends_on,
                # styleboard registers no gates (gates.GATE_REGISTRY), so [] is
                # the registry-consistent value. Written EXPLICITLY: an absent
                # key is indistinguishable from a clean run to
                # approval_service's never_ran check (A-61).
                "gates": [],
                "backfilled": True,
            },
            body,
        )
    except BaseException:
        artifacts.release_version(reservation)
        raise


def _scripting_depends_on(run_dir: Path, stage_defs: list[StageDef]) -> list[dict]:
    """Compute the synthetic styleboard's depends_on from the scripting
    artifact that actually exists at backfill time, so the reconstructed
    styleboard participates in the cascade like any other artifact (A-61)."""
    scripting_def = next((s for s in stage_defs if s.id == "scripting"), None)
    if scripting_def is None:
        return []
    latest = artifacts.latest_artifact_path(run_dir / stage_dir_name(scripting_def))
    if latest is None:
        return []
    return artifacts.compute_depends_on(run_dir, [latest])


def _backfill_one_project(
    conn: sqlite3.Connection,
    repo_root: Path,
    stage_def: StageDef,
    visual_def: StageDef | None,
    project: sqlite3.Row,
    now: str,
    stage_defs: list[StageDef],
) -> None:
    """Give one legacy project its styleboard row and, where recoverable, a
    synthetic styleboard artifact behind it.

    Ordering. A-73 proposes inserting the DB row before the disk write, or
    making the pair transactional. Neither is available here:
    db_mod.create_stage_row calls conn.commit() internally (db.py:67, via
    commit_unless_in_transaction), and db.py
    belongs to package P1. The equivalent property is bought with idempotent
    adoption instead -- _adoptable_synthetic recognises this migration's own
    prior output by (backfilled, run_id) and returns it UNCHANGED, so a crash
    between the disk write and the row insert converges on the next boot
    without rewriting a byte. The artifact's sha256 is stable across the retry,
    so no dependent is spuriously staled.
    """
    project_id = project["id"]
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
        _write_synthetic_artifact(
            run_dir / stage_dir_name(stage_def),
            project["run_id"],
            stage_def,
            now,
            f"=== STYLEBOARD — {project['run_id']} (backfilled) ===\n\n"
            f"{world_block}\n\n"
            "BINDINGS\n"
            "  none — this styleboard was reconstructed from an existing prompt sheet's\n"
            "  WORLD LOCK block. Its shots carry literal --sref codes, not slots.\n\n"
            "DISCOVERY REQUESTS\n"
            "  none\n",
            depends_on=_scripting_depends_on(run_dir, stage_defs),
        )
        status = StageStatus.APPROVED.value
    elif got_past_visual:
        # Past visual but no liftable world lock: still approve rather than wedge a
        # project that is already finished -- but back that approval with an honest
        # synthetic artifact instead of an empty stage dir. approve_stage's own
        # invariant (approval_service.py) is that every approved stage resolves to a
        # real artifact; a migration must not create the one row in the whole app
        # that violates it.
        _write_synthetic_artifact(
            run_dir / stage_dir_name(stage_def),
            project["run_id"],
            stage_def,
            now,
            f"=== STYLEBOARD — {project['run_id']} (backfilled) ===\n\n"
            "WORLD LOCK\n"
            "  not recoverable — this project completed visual before styleboard existed\n"
            "  as a stage, and no WORLD LOCK block could be found in its visual prompt\n"
            "  sheet to lift verbatim. Nothing was reconstructed; there is no world lock\n"
            "  on record for this project.\n\n"
            "BINDINGS\n"
            "  none — no source material existed to reconstruct from.\n\n"
            "DISCOVERY REQUESTS\n"
            "  none\n",
            depends_on=_scripting_depends_on(run_dir, stage_defs),
        )
        status = StageStatus.APPROVED.value
    else:
        scripting_row = db_mod.get_stage(conn, project_id, "scripting")
        status = (
            StageStatus.READY.value
            if scripting_row is not None
            and scripting_row["status"] == StageStatus.APPROVED.value
            else StageStatus.LOCKED.value
        )

    with db_mod.transaction(conn):
        row_id = db_mod.create_stage_row(conn, project_id, "styleboard", status)
        if status == StageStatus.APPROVED.value:
            db_mod.update_stage_status(conn, row_id, status, approved_at=now)
    (run_dir / stage_dir_name(stage_def)).mkdir(parents=True, exist_ok=True)


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

    Runs on every app startup, so a single corrupt/unreadable legacy artifact must not
    take the whole app down, and must not repeat forever: a project whose processing
    raises is skipped (loudly, to stderr) for this run, and because nothing was
    committed for it yet (the risky disk read happens before any DB write), the guard
    at the top of the loop retries it cleanly on the next startup rather than skipping
    it forever or leaving a half-written artifact with no row.
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

        try:
            _backfill_one_project(
                conn, repo_root, stage_def, visual_def, project, now, stage_defs
            )
        except _PER_PROJECT_RECOVERABLE as exc:
            message = (
                "migrations.backfill_styleboard_rows: skipping project "
                f"{project_id} (run_id={project['run_id']!r}) -- unreadable, "
                f"malformed, or already-occupied styleboard: "
                f"{type(exc).__name__}: {exc}"
            )
            print(message, file=sys.stderr)
            # A-74: the print alone left the project with no styleboard row, so
            # `visual` was permanently locked and the styleboard page returned
            # "Stage not applicable to this project" -- a message asserting a
            # brand-scoping decision when the real cause is a failed migration.
            # The event row is what makes that findable.
            try:
                obs.record_event(
                    conn,
                    kind="migration.backfill_skipped",
                    severity="error",
                    source="migrations.backfill_styleboard_rows",
                    message=message,
                    detail={
                        "project_id": project_id,
                        "run_id": project["run_id"],
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                )
            except Exception:  # noqa: BLE001 -- recording must never mask the skip
                pass
            continue

        touched.append(project_id)

    return touched


# The five gates Task 1-5 register, mapped to the check they satisfy on
# backfill. Kept here rather than importing gates.GATE_REGISTRY: this
# migration must know exactly which entries IT is responsible for stamping,
# independent of whatever the registry grows to later.
GATE_COVERAGE_STAGE_GATES = {
    "ideation": "gate_o_ideation_contract",
    "voiceover": "gate_o_voiceover_contract",
    "music": "gate_o_music_contract",
    "assembly": "gate_o_assembly_contract",
    "repurpose": "gate_o_repurpose_contract",
}


def backfill_gate_coverage_artifacts(
    conn: sqlite3.Connection, repo_root: Path, stage_defs: list[StageDef],
) -> list[str]:
    """Grandfather every already-approved artifact in the five newly-gated
    stages so registering their gates does not retroactively block them.

    Stamps a pass-shaped entry (the only way classify_gates treats a gate as
    non-blocking) plus a genuine, visible override via
    artifacts.record_gate_override -- the artifact's real content is never
    re-checked against the new gate, and the override note says so, rather
    than silently pretending it was verified.

    Idempotent: skips any artifact whose gates list already names the
    relevant gate, so a repeat run (every app startup) touches nothing after
    the first.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    touched: list[str] = []
    by_id = {s.id: s for s in stage_defs}

    for project in db_mod.list_projects(conn):
        for stage_id, gate_name in GATE_COVERAGE_STAGE_GATES.items():
            stage_def = by_id.get(stage_id)
            if stage_def is None:
                continue
            row = db_mod.get_stage(conn, project["id"], stage_id)
            if row is None or row["status"] != StageStatus.APPROVED.value:
                continue
            stage_dir = repo_root / "runs" / project["run_id"] / stage_dir_name(stage_def)
            latest = artifacts.resolve_latest_artifact(repo_root, stage_id, stage_dir)
            if latest is None:
                continue
            meta, _body = artifacts.read_artifact(latest)
            existing_names = {g.get("name") for g in (meta.get("gates") or [])}
            if gate_name in existing_names:
                continue
            meta.setdefault("gates", []).append(
                {"name": gate_name, "status": "pass", "findings": []}
            )
            artifacts._atomic_write_text(latest, artifacts.render_frontmatter(meta, _body))
            artifacts.record_gate_override(
                latest,
                f"grandfathered by the 2026-08-16 gate-coverage migration -- approved before "
                f"{gate_name!r} existed; content was never checked against it",
                at=now,
            )
            touched.append(str(latest.relative_to(repo_root)).replace("\\", "/"))
    return touched
