import datetime
import re
import shutil
import sqlite3
from pathlib import Path

from pipeline_app import db as db_mod
from pipeline_app.pipeline_config import StageDef, stage_dir_name
from pipeline_app.state_machine import compute_initial_status

# The slug is user-supplied (POST /projects form field) and becomes a
# filesystem path segment, so anything outside [a-z0-9-] — including the dots
# and separators that make up `../..` — collapses to a hyphen.
_SLUG_RE = re.compile(r"[^a-z0-9-]+")

# The deepest path a run directory carries is
#   <repo_root>/runs/<slug>-YYYYmmdd-HHMMSS/02b-styleboard/events/<ms>.jsonl
# ~47 characters below the run directory. Windows' default MAX_PATH is 260,
# so an unbounded slug fails halfway through creation with an OSError and
# leaves a committed project with a partial set of stage rows (A-78).
MAX_SLUG_LENGTH = 60


def sanitize_slug(slug: str) -> str:
    cleaned = _SLUG_RE.sub("-", slug.strip().lower()).strip("-")
    if not cleaned:
        raise ValueError("slug must contain at least one alphanumeric character")
    if len(cleaned) > MAX_SLUG_LENGTH:
        raise ValueError(
            f"slug is {len(cleaned)} characters after cleaning; the limit is "
            f"{MAX_SLUG_LENGTH} so the deepest run path stays within the platform limit"
        )
    return cleaned


def create_project(
    conn: sqlite3.Connection,
    repo_root: Path,
    slug: str,
    brand: str,
    stage_defs: list[StageDef],
    now: datetime.datetime | None = None,
) -> dict:
    cleaned_slug = sanitize_slug(slug)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    applicable = [s for s in stage_defs if s.brand_scope is None or s.brand_scope == brand]
    return _create_once(conn, repo_root, cleaned_slug, brand, applicable, now)


def _create_once(conn, repo_root, cleaned_slug, brand, applicable, now) -> dict:
    run_id = f"{cleaned_slug}-{now.strftime('%Y%m%d-%H%M%S')}"
    run_dir = repo_root / "runs" / run_id
    # Defence in depth: if sanitize_slug is ever weakened, refuse to create a
    # directory that escapes runs/ rather than silently writing outside it.
    # Checked before the DB insert so a rejected slug leaves no orphan row.
    if run_dir.resolve().parent != (repo_root / "runs").resolve():
        raise ValueError(f"slug resolves outside the runs directory: {cleaned_slug!r}")

    created_dir = False
    try:
        with db_mod.transaction(conn):
            project_id = db_mod.create_project(conn, run_id, cleaned_slug, brand, now.isoformat())
            for stage in applicable:
                status = compute_initial_status(stage.depends_on)
                db_mod.create_stage_row(conn, project_id, stage.id, status.value)
            # Two explicit single-level calls rather than one mkdir(parents=True):
            # pathlib's own parents=True recursion re-enters Path.mkdir for each
            # missing level, which under a mid-flight-fault test double
            # (monkeypatching Path.mkdir to fail on a specific call number)
            # attributes the injected failure to the runs/ parent instead of
            # run_dir itself, silently skipping run_dir creation. Splitting keeps
            # the exist_ok=False collision check (T18) on run_dir specifically.
            run_dir.parent.mkdir(parents=True, exist_ok=True)
            run_dir.mkdir(exist_ok=False)
            created_dir = True
            for stage in applicable:
                (run_dir / stage_dir_name(stage)).mkdir(parents=True, exist_ok=True)
    except BaseException:
        if created_dir:
            shutil.rmtree(run_dir, ignore_errors=True)
        raise
    return {"project_id": project_id, "run_id": run_id, "run_dir": run_dir}
