# pipeline_app/routes/browse.py
from fastapi import APIRouter, Request

from pipeline_app import browse_service

router = APIRouter()


def _folder_context(request: Request, rel_path: str) -> dict:
    root = browse_service.output_root(request.app.state.repo_root)
    try:
        folder = browse_service.resolve_under_output(root, rel_path)
    except browse_service.PathSafetyError:
        return {"error": "Invalid path."}
    if not folder.is_dir():
        return {"error": "Folder not found."}
    return {"entries": browse_service.list_children(folder, root)}


@router.get("/browse")
def browse_root(request: Request):
    context = _folder_context(request, "")
    return request.app.state.templates.TemplateResponse(request, "browse.html", context)


@router.get("/browse/tree")
def browse_tree(request: Request, path: str = ""):
    context = _folder_context(request, path)
    return request.app.state.templates.TemplateResponse(
        request, "partials/browse_tree_items.html", context
    )


@router.get("/browse/file")
def browse_file(request: Request, path: str = ""):
    root = browse_service.output_root(request.app.state.repo_root)
    try:
        file_path = browse_service.resolve_under_output(root, path)
    except browse_service.PathSafetyError:
        file_path = None
        context = {"error": "Invalid path."}

    if file_path is not None:
        if not file_path.exists():
            context = {"error": "Path does not exist."}
        elif file_path.is_dir():
            context = {"error": "Path is a directory, not a file."}
        elif not file_path.name.lower().endswith(".md"):
            context = {"error": "Not a valid .md file path."}
        else:
            context = browse_service.render_md_file(file_path)

    return request.app.state.templates.TemplateResponse(
        request, "partials/browse_file.html", context
    )
