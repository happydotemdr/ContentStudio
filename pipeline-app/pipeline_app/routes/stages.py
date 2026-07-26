import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from pipeline_app import artifacts, db as db_mod
from pipeline_app.pipeline_config import stage_dir_name

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


@router.get("/projects/{project_id}/stages/{stage_id}", response_class=HTMLResponse)
def stage_page(request: Request, project_id: int, stage_id: str):
    conn = request.app.state.conn
    project = db_mod.get_project(conn, project_id)
    stage_defs = request.app.state.stage_defs
    stage_def = next(s for s in stage_defs if s.id == stage_id)
    run_dir = request.app.state.repo_root / "runs" / project["run_id"]
    stage_dir = run_dir / stage_dir_name(stage_def)

    input_body = None
    if stage_def.depends_on:
        up_def = next(s for s in stage_defs if s.id == stage_def.depends_on[0])
        up_dir = run_dir / stage_dir_name(up_def)
        up_latest = artifacts.latest_artifact_path(up_dir)
        if up_latest is not None:
            _, input_body = artifacts.parse_frontmatter(up_latest.read_text(encoding="utf-8"))

    output_body = None
    latest = artifacts.latest_artifact_path(stage_dir)
    if latest is not None:
        _, output_body = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))

    transcript = _load_transcript(stage_dir)

    return request.app.state.templates.TemplateResponse(
        request, "stage.html",
        {
            "project": project, "stage_id": stage_id,
            "input_body": input_body, "output_body": output_body,
            "transcript": transcript,
        },
    )
