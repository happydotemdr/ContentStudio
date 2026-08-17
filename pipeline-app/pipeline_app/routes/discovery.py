import datetime
import subprocess
import sys
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse

from pipeline_app import db as db_mod
from pipeline_app import discovery_engine
from pipeline_app import discovery_scheduling
from pipeline_app import email_render
from pipeline_app.discovery_paths import find_slug_collision, handle_slug

router = APIRouter()

COHORT_SUGGESTIONS = ["guru", "shorts-specialist", "midjourney-source", "general-interest"]
BRAND_CHOICES = list(email_render.BRAND_SECTION_ORDER)

# B-60: a window longer than this is almost certainly a fat-fingered year, and
# every day in it is a billable enumerate_newest_first call per handle.
MAX_BACKFILL_DAYS = 730


def _parse_backfill_dates(start: str, end: str) -> tuple[date, date]:
    """Strictly parse and validate a backfill date range before it is ever
    handed to the spawned (billable) cron child.

    Rejects: anything not in strict YYYY-MM-DD form (including a value
    starting with '-', which argparse on the child would otherwise consume
    as a flag rather than a value); start > end; and a window wider than
    MAX_BACKFILL_DAYS.
    """
    parsed = {}
    for label, value in (("start", start), ("end", end)):
        if not value or value.startswith("-"):
            raise ValueError(f"invalid {label} date: {value!r}. Expected YYYY-MM-DD.")
        try:
            parsed_date = datetime.datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"invalid {label} date: {value!r}. Expected YYYY-MM-DD.")
        if parsed_date.isoformat() != value:
            raise ValueError(f"invalid {label} date: {value!r}. Expected YYYY-MM-DD.")
        parsed[label] = parsed_date

    start_date, end_date = parsed["start"], parsed["end"]
    if start_date > end_date:
        raise ValueError(f"start ({start}) must not be after end ({end}).")
    if (end_date - start_date).days > MAX_BACKFILL_DAYS:
        raise ValueError(
            f"backfill window {start} to {end} exceeds the {MAX_BACKFILL_DAYS}-day maximum."
        )
    return start_date, end_date


def _popen(cmd: list[str], **kwargs):
    """The single process-spawn seam for this module. Tests replace THIS, so
    the repo-wide conftest guard on the real spawn call stays armed and a
    route test that forgets to stub fails loudly instead of billing (F-68)."""
    return subprocess.Popen(cmd, **kwargs)


def _spawn_cron(repo_root: Path, args: list[str]) -> None:
    cron_script = repo_root / "pipeline-app" / "run_discovery_cron.py"
    _popen(
        [sys.executable, str(cron_script), *args, "--repo-root", str(repo_root)],
        cwd=str(repo_root),
    )


@router.get("/discovery/handles")
def discovery_handles_page(request: Request):
    conn = request.app.state.conn
    handles = db_mod.list_handles(conn)
    handle_brands = {h["id"]: db_mod.get_handle_brands(conn, h["id"]) for h in handles}
    settings = db_mod.get_settings(conn)
    return request.app.state.templates.TemplateResponse(
        request, "discovery_handles.html",
        {
            "handles": handles, "cohort_suggestions": COHORT_SUGGESTIONS,
            "brand_choices": BRAND_CHOICES, "handle_brands": handle_brands,
            "settings": settings,
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
    # B-58/B-73: reject an unrecognized platform before it is ever persisted.
    # Without this, adapters[platform] raised KeyError OUTSIDE run_discovery's
    # try -- the fire-and-forget validate child died with a traceback nobody
    # saw, no run row was written, and the handle sat at 'pending' forever
    # with no explanation. This is the fast, message-bearing gate; P1's schema
    # CHECK (B-73) is the durable backstop for paths this route can't reach.
    if platform not in discovery_engine.SUPPORTED_PLATFORMS:
        valid = ", ".join(sorted(discovery_engine.SUPPORTED_PLATFORMS))
        return PlainTextResponse(
            f"unrecognized platform: {platform!r}. Valid platforms are: {valid}.",
            status_code=400,
        )
    # Reject before create_handle and before the validate spawn: on the Bright
    # Data platforms that spawn is a billable job, so a handle we refuse to
    # store must not be paid for either.
    clash = find_slug_collision(
        handle, [row["handle"] for row in db_mod.list_platform_handles(conn, platform)]
    )
    if clash is not None:
        return PlainTextResponse(
            f"handle shares a directory with an existing one: {platform}/{handle} and "
            f"{platform}/{clash} both resolve to "
            f"output/brand-intel/{platform}/{handle_slug(handle)}. They would be "
            f"billed separately every run while writing to one directory, and "
            f"whichever ran second would read the other's files and report "
            f"'no_new_content'. Register one, or use handles differing by more "
            f"than punctuation or capitalization.",
            status_code=400,
        )
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


@router.post("/discovery/handles/{handle_id}/brands")
def update_handle_brands(request: Request, handle_id: int, brands: list[str] = Form([])):
    conn = request.app.state.conn
    row = db_mod.get_handle(conn, handle_id)
    if row is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    db_mod.set_handle_brands(conn, handle_id, brands)
    return RedirectResponse(url="/discovery/handles", status_code=303)


@router.get("/discovery/handles/{handle_id}/status")
def handle_status(request: Request, handle_id: int):
    conn = request.app.state.conn
    row = db_mod.get_handle(conn, handle_id)
    if row is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({"status": row["status"]})


@router.post("/discovery/run-now")
def run_now(request: Request):
    # B-59: Run Now had no concurrency guard -- a second click (or a second
    # browser tab) while a run was already active spawned a duplicate,
    # billable cron child that was doomed to lose the single-flight lock
    # (best case) or race the live run for it (worst case). Refuse before
    # spawning rather than let the loser sort itself out downstream.
    conn = request.app.state.conn
    if db_mod.get_running_run(conn) is not None:
        return PlainTextResponse("a discovery run is already active", status_code=409)
    _spawn_cron(request.app.state.repo_root, ["--mode", "incremental"])
    return RedirectResponse(url="/discovery/runs", status_code=303)


@router.post("/discovery/run-now-backfill")
def run_now_backfill(request: Request, start: str = Form(...), end: str = Form(...)):
    try:
        _parse_backfill_dates(start, end)
    except ValueError as exc:
        return PlainTextResponse(str(exc), status_code=400)
    _spawn_cron(request.app.state.repo_root, [
        "--mode", "backfill", "--backfill-start", start, "--backfill-end", end,
    ])
    return RedirectResponse(url="/discovery/runs", status_code=303)


@router.post("/discovery/settings")
def update_settings(request: Request, time_of_day: str = Form(...), timezone: str = Form(...)):
    # B-47: validate against the exact same parsers is_due() uses at runtime, so
    # the route's 400 and the scheduler's own due-check can never drift apart --
    # a value the form accepts must be a value the cron can actually evaluate.
    try:
        discovery_scheduling.parse_time_of_day(time_of_day)
        discovery_scheduling.resolve_timezone(timezone)
    except discovery_scheduling.ScheduleConfigError as exc:
        return PlainTextResponse(str(exc), status_code=400)
    conn = request.app.state.conn
    db_mod.update_settings(conn, "daily", time_of_day, timezone)
    return RedirectResponse(url="/discovery/handles", status_code=303)


@router.get("/discovery/runs")
def discovery_runs_page(request: Request):
    conn = request.app.state.conn
    runs = db_mod.list_runs(conn)
    runs_with_results = [
        {"run": run, "handle_results": db_mod.list_run_handle_results(conn, run["id"])}
        for run in runs
    ]
    return request.app.state.templates.TemplateResponse(
        request, "discovery_runs.html",
        {
            "runs_with_results": runs_with_results, "active_nav": "discovery_runs",
            "cli_available": request.app.state.cli_available,
        },
    )
