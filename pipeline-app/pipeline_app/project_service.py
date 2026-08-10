import datetime
import re
import sqlite3
from pathlib import Path

from pipeline_app import db as db_mod
from pipeline_app.pipeline_config import StageDef, stage_dir_name
from pipeline_app.state_machine import compute_initial_status

# The slug is user-supplied (POST /projects form field) and becomes a
# filesystem path segment, so anything outside [a-z0-9-] — including the dots
# and separators that make up `../..` — collapses to a hyphen.
_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def sanitize_slug(slug: str) -> str:
    cleaned = _SLUG_RE.sub("-", slug.strip().lower()).strip("-")
    if not cleaned:
        raise ValueError("slug must contain at least one alphanumeric character")
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
    run_id = f"{cleaned_slug}-{now.strftime('%Y%m%d-%H%M%S')}"

    run_dir = repo_root / "runs" / run_id
    # Defence in depth: if sanitize_slug is ever weakened, refuse to create a
    # directory that escapes runs/ rather than silently writing outside it.
    # Checked before the DB insert so a rejected slug leaves no orphan row.
    if run_dir.resolve().parent != (repo_root / "runs").resolve():
        raise ValueError(f"slug resolves outside the runs directory: {slug!r}")

    with db_mod.transaction(conn):
        project_id = db_mod.create_project(conn, run_id, cleaned_slug, brand, now.isoformat())
        run_dir.mkdir(parents=True, exist_ok=True)

        applicable = [s for s in stage_defs if s.brand_scope is None or s.brand_scope == brand]
        for stage in applicable:
            status = compute_initial_status(stage.depends_on)
            db_mod.create_stage_row(conn, project_id, stage.id, status.value)
            (run_dir / stage_dir_name(stage)).mkdir(parents=True, exist_ok=True)

    return {"project_id": project_id, "run_id": run_id, "run_dir": run_dir}
