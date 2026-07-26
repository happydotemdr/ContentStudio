from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pipeline_app import db as db_mod
from pipeline_app.pipeline_config import load_topology
from pipeline_app.routes import inspector, projects, skills, stages

PACKAGE_DIR = Path(__file__).resolve().parent


def create_app(repo_root: Path, db_path: Path) -> FastAPI:
    app = FastAPI()
    app.state.repo_root = repo_root
    app.state.stage_defs = load_topology(repo_root / "pipeline.yaml")

    schema_path = PACKAGE_DIR / "schema.sql"
    db_mod.init_db(db_path, schema_path)
    app.state.conn = db_mod.get_connection(db_path)

    app.state.templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static")

    app.include_router(projects.router)
    app.include_router(stages.router)
    app.include_router(skills.router)
    app.include_router(inspector.router)
    return app


def create_default_app() -> FastAPI:
    """Factory for `uvicorn pipeline_app.main:create_default_app --factory`.

    Deliberately NOT a module-level `app = create_app(...)` call — that would
    run at import time, so every test importing anything from this module
    (even `from pipeline_app.main import create_app`) would initialize the
    real pipeline-app/pipeline.db, load the real repo-root pipeline.yaml, and
    run startup reconciliation against production state before any test
    fixture (tmp_path, a fresh in-memory DB) gets a chance to run. Only the
    factory entry point touches real paths, and only when uvicorn calls it."""
    repo_root = Path(__file__).resolve().parents[2]
    return create_app(repo_root=repo_root, db_path=repo_root / "pipeline-app" / "pipeline.db")
