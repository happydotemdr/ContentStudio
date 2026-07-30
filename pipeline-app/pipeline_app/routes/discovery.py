import datetime
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse

from pipeline_app import db as db_mod

router = APIRouter()

COHORT_SUGGESTIONS = ["guru", "shorts-specialist", "midjourney-source", "general-interest"]


def _spawn_cron(repo_root: Path, args: list[str]) -> None:
    cron_script = repo_root / "pipeline-app" / "run_discovery_cron.py"
    subprocess.Popen(
        [sys.executable, str(cron_script), *args, "--repo-root", str(repo_root)],
        cwd=str(repo_root),
    )


@router.get("/discovery/handles")
def discovery_handles_page(request: Request):
    conn = request.app.state.conn
    handles = db_mod.list_handles(conn)
    return request.app.state.templates.TemplateResponse(
        request, "discovery_handles.html",
        {
            "handles": handles, "cohort_suggestions": COHORT_SUGGESTIONS,
            "active_nav": "discovery_handles", "cli_available": request.app.state.cli_available,
        },
    )


@router.post("/discovery/handles")
def add_handle(
    request: Request, platform: str = Form(...), handle: str = Form(...),
    display_name: str = Form(""), cohort: str = Form(...), keyword_filter: str = Form(""),
):
    conn = request.app.state.conn
    repo_root = request.app.state.repo_root
    if db_mod.get_handle_by_platform_and_handle(conn, platform, handle) is not None:
        return PlainTextResponse(f"handle already exists: {platform}/{handle}", status_code=400)
    added_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    handle_id = db_mod.create_handle(
        conn, platform, handle, display_name or None, cohort, keyword_filter or None, added_at,
    )
    _spawn_cron(repo_root, ["--mode", "validate_handle", "--handle-id", str(handle_id)])
    return RedirectResponse(url="/discovery/handles", status_code=303)


@router.post("/discovery/handles/{handle_id}/toggle")
def toggle_handle_included(request: Request, handle_id: int):
    conn = request.app.state.conn
    row = db_mod.get_handle(conn, handle_id)
    if row is not None:
        db_mod.set_handle_included(conn, handle_id, not bool(row["included"]))
    return RedirectResponse(url="/discovery/handles", status_code=303)


@router.get("/discovery/handles/{handle_id}/status")
def handle_status(request: Request, handle_id: int):
    conn = request.app.state.conn
    row = db_mod.get_handle(conn, handle_id)
    if row is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({"status": row["status"]})
