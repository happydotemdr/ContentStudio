from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

from pipeline_app import db as db_mod
from pipeline_app.project_service import create_project

router = APIRouter()


@router.get("/")
def list_projects(request: Request):
    conn = request.app.state.conn
    projects = db_mod.list_projects(conn)
    return request.app.state.templates.TemplateResponse(
        request, "project_list.html", {"projects": projects}
    )


@router.post("/projects")
def create_project_route(request: Request, slug: str = Form(...), brand: str = Form(...)):
    conn = request.app.state.conn
    try:
        result = create_project(
            conn, request.app.state.repo_root, slug, brand, request.app.state.stage_defs
        )
    except ValueError as exc:
        # Unusable slug (nothing left after sanitisation, or a path that would
        # escape runs/) — an explicit client error, not a 500.
        return PlainTextResponse(str(exc), status_code=400)
    return RedirectResponse(url=f"/projects/{result['project_id']}", status_code=303)


@router.get("/projects/{project_id}")
def project_home(request: Request, project_id: int):
    conn = request.app.state.conn
    project = db_mod.get_project(conn, project_id)
    stages = db_mod.list_stages(conn, project_id)
    return request.app.state.templates.TemplateResponse(
        request, "project_home.html", {"project": project, "stages": stages}
    )
