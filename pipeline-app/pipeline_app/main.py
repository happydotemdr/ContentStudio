from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pipeline_app import db as db_mod
from pipeline_app import migrations
from pipeline_app import obs
from pipeline_app import preflight
from pipeline_app.pipeline_config import load_topology
from pipeline_app.routes import browse, discovery, doctor, inspector, projects, skills, stages

PACKAGE_DIR = Path(__file__).resolve().parent


def create_app(repo_root: Path, db_path: Path) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        # `init_db` already opens and closes its own short-lived connection;
        # the shared one had no shutdown hook at all, so the WAL was never
        # checkpointed and every caller that built an app leaked a connection
        # and its -wal/-shm files for the life of the process (A-85).
        #
        # Runs only when the app is driven as a context manager -- uvicorn
        # always does, and a test must use `with TestClient(app)`.
        try:
            app.state.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception as exc:  # noqa: BLE001 -- shutdown must not raise
            # obs.log and NOT obs.record_event, deliberately: the connection is
            # about to close and may itself be what failed, so writing an
            # `events` row on it is unreliable by construction. A-85's failure
            # mode is `latent`, not `silent`, so no surfacing leg is owed --
            # this is not a missing event.
            obs.log("db.checkpoint_failed", level="warning",
                    error=f"{type(exc).__name__}: {exc}")
        app.state.conn.close()

    app = FastAPI(lifespan=lifespan)
    app.state.repo_root = repo_root
    app.state.db_path = db_path
    app.state.stage_defs = load_topology(repo_root / "pipeline.yaml")

    schema_path = PACKAGE_DIR / "schema.sql"
    db_mod.init_db(db_path, schema_path)
    app.state.conn = db_mod.get_connection(db_path)
    app.state.backfilled_projects = migrations.backfill_styleboard_rows(
        app.state.conn, app.state.repo_root, app.state.stage_defs
    )
    app.state.orphaned_count = preflight.reconcile_orphaned_turns(
        app.state.conn, app.state.repo_root, app.state.stage_defs
    )
    app.state.cli_available = preflight.check_cli_available()["available"]

    app.state.templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static")

    app.include_router(projects.router)
    app.include_router(discovery.router)
    app.include_router(stages.router)
    app.include_router(skills.router)
    app.include_router(inspector.router)
    app.include_router(doctor.router)
    app.include_router(browse.router)
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
