import datetime
import json

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, StreamingResponse

from pipeline_app import approval_service, artifacts, db as db_mod, grounding_service, turn_service
from pipeline_app.pipeline_config import build_stage_nav, stage_dir_name

router = APIRouter()


def _load_transcript(stage_dir):
    events_dir = stage_dir / "events"
    messages = []
    if not events_dir.exists():
        return messages
    for events_file in sorted(events_dir.glob("*.jsonl")):
        for line in events_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("type") == "result":
                messages.append({"type": "assistant", "text": event.get("result", "")})
    return messages


def _resolve_project_stage(request: Request, project_id: int, stage_id: str):
    """Resolve (project, stage_def, stage_row) or raise the right 404.

    stage_def comes from the full pipeline.yaml topology, but create_project
    only materialises the stage ROWS whose brand_scope matches the project's
    brand — so a `generic` project has no `grounding` row even though the
    topology defines that stage. Without the stage_row check the grounding
    routes would render a phantom page and blow up with a TypeError deeper in
    turn_service."""
    conn = request.app.state.conn
    project = db_mod.get_project(conn, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    stage_defs = request.app.state.stage_defs
    stage_def = next((s for s in stage_defs if s.id == stage_id), None)
    if stage_def is None:
        raise HTTPException(status_code=404, detail="Stage not found")
    stage_row = db_mod.get_stage(conn, project_id, stage_id)
    if stage_row is None:
        raise HTTPException(status_code=404, detail="Stage not applicable to this project")
    return project, stage_def, stage_row


@router.get("/projects/{project_id}/stages/{stage_id}", response_class=HTMLResponse)
def stage_page(request: Request, project_id: int, stage_id: str):
    project, stage_def, _stage_row = _resolve_project_stage(request, project_id, stage_id)
    stage_defs = request.app.state.stage_defs
    run_dir = request.app.state.repo_root / "runs" / project["run_id"]
    stage_dir = run_dir / stage_dir_name(stage_def)

    input_body = None
    if stage_def.depends_on:
        up_def = next(s for s in stage_defs if s.id == stage_def.depends_on[0])
        up_dir = run_dir / stage_dir_name(up_def)
        up_latest = artifacts.latest_artifact_path(up_dir)
        if up_latest is not None:
            _, input_body = artifacts.parse_frontmatter(up_latest.read_text(encoding="utf-8"))

    # Grounding is an optional RGS companion, not a formal `depends_on` --
    # the chat/turn_service path already hands it to the AI via
    # grounding_pointer (see stage_chat below), so the Input panel must show
    # it too or the page looks like grounding produced nothing usable.
    grounding_input_body = None
    if project["brand"] == "raisinggoodsports" and stage_id != "grounding":
        grounding_dir = run_dir / "00-grounding"
        pointer = grounding_service.read_pointer(grounding_dir)
        if pointer:
            grounding_path = request.app.state.repo_root / pointer
            if grounding_path.exists():
                _, grounding_input_body = artifacts.parse_frontmatter(
                    grounding_path.read_text(encoding="utf-8")
                )

    output_body = None
    if stage_id == "grounding":
        # Grounding's real output lands in rgs-briefs/, referenced by a
        # pointer.yaml the turn route writes into stage_dir -- not the
        # artifact.v{N}.md convention every other stage uses.
        pointer = grounding_service.read_pointer(stage_dir)
        latest = (request.app.state.repo_root / pointer) if pointer else None
    else:
        latest = artifacts.latest_artifact_path(stage_dir)
    if latest is not None:
        _, output_body = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))

    transcript = _load_transcript(stage_dir)
    stage_rows = db_mod.list_stages(request.app.state.conn, project_id)
    nav = build_stage_nav(stage_defs, stage_rows)

    return request.app.state.templates.TemplateResponse(
        request, "stage.html",
        {
            "project": project, "stage_id": stage_id,
            "input_body": input_body, "grounding_input_body": grounding_input_body,
            "output_body": output_body,
            "transcript": transcript, "nav": nav,
        },
    )


@router.post("/projects/{project_id}/stages/{stage_id}/chat")
async def stage_chat(request: Request, project_id: int, stage_id: str, message: str = Form(...)):
    project, stage_def, _stage_row = _resolve_project_stage(request, project_id, stage_id)
    conn = request.app.state.conn
    repo_root = request.app.state.repo_root
    stage_defs = request.app.state.stage_defs
    run_dir = repo_root / "runs" / project["run_id"]
    templates_dir = repo_root / "pipeline-app" / "stage_templates"

    # Checked here, before any response is started: run_stage_turn also checks
    # internally, but that check does not execute until the StreamingResponse
    # body generator is first iterated — by then a 200 and SSE headers are
    # already committed, so the client would see a broken stream instead of an
    # explicit "already running" error. Checking here lets a concurrent
    # request get a clean 409 with no response ever started.
    if turn_service.any_turn_running(conn):
        return PlainTextResponse("Another stage turn is already running.", status_code=409)

    grounding_pointer = None
    if project["brand"] == "raisinggoodsports" and stage_id != "grounding":
        grounding_dir = run_dir / "00-grounding"
        grounding_pointer = grounding_service.read_pointer(grounding_dir)

    if stage_id == "grounding":
        async def event_stream():
            rgs_briefs_dir = repo_root / "rgs-briefs"
            grounding_dir = run_dir / "00-grounding"
            before = grounding_service.snapshot_rgs_briefs(rgs_briefs_dir)

            async for event in turn_service.run_stage_turn(
                conn, repo_root, run_dir, templates_dir,
                project_id, project["run_id"], stage_def, stage_defs, message,
                finalize_artifact=False,
            ):
                yield f"data: {json.dumps(event)}\n\n"

            # The grounding skill's real artifact lands in rgs-briefs/, not
            # runs/ — finalize_artifact=False above skips turn_service's
            # normal artifact/status handling so this stage-specific path can
            # take over: identify which file appeared, supersede whichever
            # brief this project pointed at before (if regenerating), and
            # point at the new one.
            after = grounding_service.snapshot_rgs_briefs(rgs_briefs_dir)
            new_brief = grounding_service.identify_new_brief(before, after)
            stage_row = db_mod.get_stage(conn, project_id, "grounding")
            if new_brief is not None:
                grounding_service.supersede_previous_brief(repo_root, grounding_dir)
                grounding_service.write_pointer(grounding_dir, f"rgs-briefs/{new_brief}")
                db_mod.update_stage_status(conn, stage_row["id"], "awaiting_review")
            else:
                db_mod.update_stage_status(conn, stage_row["id"], "no_artifact")

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    async def event_stream():
        async for event in turn_service.run_stage_turn(
            conn, repo_root, run_dir, templates_dir,
            project_id, project["run_id"], stage_def, stage_defs, message,
            grounding_pointer=grounding_pointer,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/projects/{project_id}/stages/{stage_id}/approve")
def approve_stage_route(request: Request, project_id: int, stage_id: str):
    project, _stage_def, _stage_row = _resolve_project_stage(request, project_id, stage_id)
    conn = request.app.state.conn
    repo_root = request.app.state.repo_root
    stage_defs = request.app.state.stage_defs
    run_dir = repo_root / "runs" / project["run_id"]
    try:
        approval_service.approve_stage(conn, repo_root, run_dir, project_id, stage_defs, stage_id)
    except ValueError as exc:
        # Nothing to approve yet — an explicit conflict state, never a 500.
        return PlainTextResponse(str(exc), status_code=409)
    return RedirectResponse(url=f"/projects/{project_id}/stages/{stage_id}", status_code=303)


@router.post("/projects/{project_id}/stages/{stage_id}/edit")
def edit_stage_output_route(request: Request, project_id: int, stage_id: str, body: str = Form(...)):
    project, stage_def, stage_row = _resolve_project_stage(request, project_id, stage_id)
    conn = request.app.state.conn
    repo_root = request.app.state.repo_root
    stage_defs = request.app.state.stage_defs
    run_dir = repo_root / "runs" / project["run_id"]
    stage_dir = run_dir / stage_dir_name(stage_def)

    latest = artifacts.latest_artifact_path(stage_dir)
    prior_meta = {}
    if latest is not None:
        prior_meta, _ = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))

    version = artifacts.next_version_number(stage_dir)
    meta = {
        "schema_version": 1,
        "run_id": project["run_id"],
        "stage": stage_def.skill,
        "version": version,
        "status": "draft",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "finalized_at": None,
        "supersedes": f"artifact.v{version - 1}.md" if version > 1 else None,
        "depends_on": prior_meta.get("depends_on", []),
    }
    artifacts.write_artifact(stage_dir, version, meta, body)

    # Design spec §2: a hand edit mints artifact.v{N+1}.md exactly like a
    # regenerate does, so it gets the same downstream treatment — approved
    # dependents whose recorded hash no longer matches go stale, and this
    # stage drops back to awaiting_review because a fresh unapproved draft
    # now exists (even if the stage had already been approved).
    turn_service.propagate_staleness(conn, run_dir, stage_defs, project_id, stage_id)
    db_mod.update_stage_status(conn, stage_row["id"], "awaiting_review")

    return RedirectResponse(url=f"/projects/{project_id}/stages/{stage_id}", status_code=303)
