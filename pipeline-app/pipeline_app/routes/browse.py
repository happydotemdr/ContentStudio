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
