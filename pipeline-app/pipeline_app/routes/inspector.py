from pathlib import Path

import markdown
from fastapi import APIRouter, Form, Request

from pipeline_app import artifacts, browse_service

router = APIRouter()


@router.get("/inspector")
def inspector_form(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "inspector.html",
        {"active_nav": "inspector", "cli_available": request.app.state.cli_available},
    )


@router.post("/inspector")
def inspector_inspect(request: Request, path: str = Form(...)):
    # This is a deliberately open, read-only "point it at any .md file on
    # disk" tool (single-user, 127.0.0.1-only local app) — no path
    # containment/allowlisting here, that's intentional per the design spec.
    # Every expected failure mode below is surfaced as an explicit UI error
    # state instead of a raw 500, per the design spec's "no generic 500s".
    file_path = Path(path)

    error = None
    if not file_path.exists():
        error = "Path does not exist."
    elif file_path.is_dir():
        error = "Path is a directory, not a file."
    elif file_path.suffix != ".md":
        error = "Not a valid .md file path."
    else:
        try:
            text = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            error = f"Could not read file: {exc}"
        else:
            meta, body = artifacts.parse_frontmatter(text)
            return request.app.state.templates.TemplateResponse(
                request, "inspector.html",
                {
                    "path": path, "frontmatter": meta,
                    "body_html": browse_service.sanitize_html(markdown.markdown(body)),
                    "active_nav": "inspector",
                    "cli_available": request.app.state.cli_available,
                },
            )

    return request.app.state.templates.TemplateResponse(
        request, "inspector.html",
        {
            "path": path, "error": error,
            "active_nav": "inspector",
            "cli_available": request.app.state.cli_available,
        },
    )
