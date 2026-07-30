# pipeline_app/routes/browse.py
from fastapi import APIRouter, Request

from pipeline_app import browse_service

router = APIRouter()


def _folder_context(request: Request, root: str, rel_path: str) -> dict:
    repo_root = request.app.state.repo_root
    try:
        root_dir = browse_service.root_path(repo_root, root)
    except ValueError:
        return {"error": "Invalid path."}

    is_pipeline_top = root == "pipeline" and rel_path.strip() in ("", ".", "/")
    if is_pipeline_top:
        if not root_dir.is_dir():
            return {"empty_message": "No pipeline runs yet."}
        try:
            entries = browse_service.list_pipeline_projects(request.app.state.conn, repo_root)
        except browse_service.FolderReadError as exc:
            return {"error": f"Could not read folder: {exc}"}
        return {"entries": entries}

    try:
        folder = browse_service.resolve_under_output(root_dir, rel_path)
    except browse_service.PathSafetyError:
        return {"error": "Invalid path."}
    if not folder.is_dir():
        return {"error": "Folder not found."}
    try:
        return {"entries": browse_service.list_children(folder, root_dir, repo_root)}
    except browse_service.FolderReadError as exc:
        return {"error": f"Could not read folder: {exc}"}


@router.get("/browse")
def browse_root(request: Request):
    context = {
        "output": _folder_context(request, "output", ""),
        "pipeline": _folder_context(request, "pipeline", ""),
        "active_nav": "browse",
        "cli_available": request.app.state.cli_available,
    }
    return request.app.state.templates.TemplateResponse(request, "browse.html", context)


@router.get("/browse/tree")
def browse_tree(request: Request, path: str = "", root: str = "output"):
    context = _folder_context(request, root, path)
    context["root"] = root
    return request.app.state.templates.TemplateResponse(
        request, "partials/browse_tree_items.html", context
    )


@router.get("/browse/file")
def browse_file(request: Request, path: str = "", root: str = "output"):
    repo_root = request.app.state.repo_root
    try:
        root_dir = browse_service.root_path(repo_root, root)
    except ValueError:
        return request.app.state.templates.TemplateResponse(
            request, "partials/browse_file.html", {"error": "Invalid path."}
        )

    try:
        file_path = browse_service.resolve_under_output(root_dir, path)
    except browse_service.PathSafetyError:
        file_path = None
        context = {"error": "Invalid path."}

    if file_path is not None:
        if not file_path.exists():
            context = {"error": "Path does not exist."}
        elif file_path.is_dir():
            context = {"error": "Path is a directory, not a file."}
        elif file_path.name == "pointer.yaml":
            target = browse_service.resolve_grounding_pointer(file_path.parent, repo_root)
            if target is None:
                context = {"error": "Grounding pointer could not be resolved."}
            else:
                context = browse_service.render_md_file(target)
        elif not file_path.name.lower().endswith(".md"):
            context = {"error": "Not a valid .md file path."}
        else:
            context = browse_service.render_md_file(file_path)

    return request.app.state.templates.TemplateResponse(
        request, "partials/browse_file.html", context
    )
