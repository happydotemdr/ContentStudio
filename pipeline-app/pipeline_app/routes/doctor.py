from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from pipeline_app import db as db_mod

router = APIRouter()

RECENT_EVENT_WINDOW_DAYS = 7


@router.get("/doctor")
def doctor_page(request: Request):
    repo_root = request.app.state.repo_root
    skills_dir = repo_root / ".claude" / "skills"
    skill_names = sorted(p.name for p in skills_dir.iterdir() if p.is_dir()) if skills_dir.exists() else []
    since = (datetime.now(timezone.utc) - timedelta(days=RECENT_EVENT_WINDOW_DAYS)) \
        .isoformat(timespec="seconds")
    return request.app.state.templates.TemplateResponse(
        request, "doctor.html",
        {
            "repo_root": str(repo_root),
            "db_path": str(getattr(request.app.state, "db_path", "")),
            "cli": request.app.state.cli_probe.get(),
            "skill_names": skill_names,
            # Direct attribute access, not getattr(..., 0): create_app (T14)
            # unconditionally sets this to an int or to None, never leaves it
            # absent, so a default that collapses "missing" into "0" is not
            # defensive, it is a third route back to the exact ambiguity this
            # package exists to remove. None means "this instance never ran
            # the startup sweep because another one holds the lease" --
            # different from 0 (A-76).
            "orphaned_count": request.app.state.orphaned_count,
            "recent_events": db_mod.list_unacknowledged_events(
                request.app.state.conn, since_iso=since
            ),
            "unacknowledged_error_total": db_mod.count_unacknowledged_events(
                request.app.state.conn
            ),
            "active_nav": "doctor",
            "cli_available": request.app.state.cli_available,
        },
    )


@router.post("/doctor/events/{event_id}/ack")
def acknowledge(request: Request, event_id: int):
    db_mod.acknowledge_event(request.app.state.conn, event_id)
    return RedirectResponse("/doctor", status_code=303)
