import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pipeline_app import db as db_mod
from pipeline_app import migrations
from pipeline_app import obs
from pipeline_app import preflight
from pipeline_app.pipeline_config import load_topology
from pipeline_app.routes import browse, discovery, doctor, inspector, projects, skills, stages

PACKAGE_DIR = Path(__file__).resolve().parent

RECONCILE_LEASE_SECONDS = 120
HEARTBEAT_INTERVAL_SECONDS = 30  # several ticks inside the 120s lease window

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _same_host(candidate: str, host_header: str) -> bool:
    """A form POST carries Origin in every current browser; Referer is the
    fallback for the ones that strip it. Neither present means a non-browser
    client (curl, the test suite, the cron runner's own HTTP calls), which no
    cross-site attack can produce -- so that case is allowed, deliberately and
    with the residual gap recorded here rather than left implicit."""
    return urlsplit(candidate).netloc.casefold() == host_header.casefold()


class _CliProbe:
    """One cached answer to "is the Claude CLI installed", shared by the banner
    and the /doctor panel.

    Before this, the banner was a startup snapshot and /doctor was a live probe,
    so one response could carry two different answers to the same question and
    restart was the only way to reconcile them (A-83). The TTL exists only so
    `shutil.which` is not called on every request; correctness comes from both
    readers sharing one snapshot per request."""

    def __init__(self, ttl_seconds: float = 5.0) -> None:
        self._ttl = ttl_seconds
        self._at = 0.0
        self._value: dict | None = None

    def get(self) -> dict:
        now = time.monotonic()
        if self._value is None or now - self._at >= self._ttl:
            self._value = preflight.check_cli_available()
            self._at = now
        return self._value

    def invalidate(self) -> None:
        self._value = None


def _claim_reconcile_lease(conn, token: str, now: datetime,
                           lease_seconds: int = RECONCILE_LEASE_SECONDS) -> bool:
    """True if this process may run the startup sweep.

    A clean shutdown releases the lease (see the lifespan handler), so a genuine
    restart sweeps immediately. A crash leaves it, and the lease expires after
    `lease_seconds` -- long enough that uvicorn's other workers, which start
    within seconds, are correctly refused."""
    now_iso = now.isoformat(timespec="seconds")
    with db_mod.transaction(conn):
        cur = conn.execute(
            "INSERT OR IGNORE INTO app_instances (id, owner_token, claimed_at, heartbeat_at) "
            "VALUES (1, ?, ?, ?)", (token, now_iso, now_iso),
        )
        if cur.rowcount == 1:
            return True
        row = conn.execute("SELECT * FROM app_instances WHERE id = 1").fetchone()
        age = (now - datetime.fromisoformat(row["heartbeat_at"])).total_seconds()
        if age < lease_seconds:
            return False
        conn.execute(
            "UPDATE app_instances SET owner_token = ?, claimed_at = ?, heartbeat_at = ? "
            "WHERE id = 1 AND owner_token = ?", (token, now_iso, now_iso, row["owner_token"]),
        )
        return True


def _release_reconcile_lease(conn, token: str) -> None:
    try:
        conn.execute("DELETE FROM app_instances WHERE id = 1 AND owner_token = ?", (token,))
        conn.commit()
    except Exception as exc:  # noqa: BLE001 -- shutdown must not raise
        obs.log("app.lease_release_failed", level="warning",
                error=f"{type(exc).__name__}: {exc}")


async def _heartbeat_reconcile_lease(conn, token: str) -> None:
    """Keeps this instance's `app_instances` row fresh for as long as the
    process is alive, independent of request traffic -- a single long-running
    turn stream can hold one HTTP request open for minutes without touching
    any other route, and `heartbeat_at` must not go stale during that time."""
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        try:
            now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
            conn.execute(
                "UPDATE app_instances SET heartbeat_at = ? WHERE id = 1 AND owner_token = ?",
                (now_iso, token),
            )
            db_mod.commit_unless_in_transaction(conn)
        except Exception as exc:  # noqa: BLE001 -- a missed heartbeat must not kill the app
            obs.log("app.heartbeat_failed", level="warning", error=f"{type(exc).__name__}: {exc}")


def create_app(repo_root: Path, db_path: Path) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        heartbeat_task = (
            asyncio.create_task(_heartbeat_reconcile_lease(app.state.conn, app.state.instance_token))
            if app.state.orphaned_count is not None else None
        )
        yield
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        _release_reconcile_lease(app.state.conn, app.state.instance_token)
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
    app.state.instance_token = f"{os.getpid()}:{uuid.uuid4().hex[:8]}"
    if _claim_reconcile_lease(app.state.conn, app.state.instance_token,
                              datetime.now(timezone.utc)):
        app.state.orphaned_count = preflight.reconcile_orphaned_turns(
            app.state.conn, app.state.repo_root, app.state.stage_defs
        )
    else:
        # None, not 0: "I swept and found nothing" and "I never swept" are
        # different facts, and collapsing them is how A-76 stayed invisible.
        app.state.orphaned_count = None
        obs.record_event(
            app.state.conn, kind="app.startup.reconcile_skipped", severity="warning",
            source="main.create_app",
            message="another live app instance holds the reconcile lease; "
                    "skipped the startup orphan sweep",
            detail={"instance_token": app.state.instance_token},
        )
    app.state.cli_probe = _CliProbe()
    app.state.cli_available = app.state.cli_probe.get()["available"]

    @app.middleware("http")
    async def _refresh_cli_banner(request, call_next):
        # Ten route modules read request.app.state.cli_available as a plain
        # bool and all ten belong to other packages, so the attribute stays a
        # bool -- it is just refreshed from the same snapshot /doctor reads,
        # once, at the top of the request.
        request.app.state.cli_available = request.app.state.cli_probe.get()["available"]
        return await call_next(request)

    @app.middleware("http")
    async def _reject_cross_origin_mutations(request, call_next):
        if request.method in _MUTATING_METHODS:
            claimed = request.headers.get("origin") or request.headers.get("referer")
            host = request.headers.get("host", "")
            if claimed and not _same_host(claimed, host):
                obs.record_event(
                    request.app.state.conn,
                    kind="security.cross_origin_post_rejected", severity="error",
                    source="main.csrf_guard",
                    message=f"rejected {request.method} {request.url.path} claiming origin "
                            f"{claimed}",
                    detail={"method": request.method, "path": request.url.path,
                            "claimed_origin": claimed, "host": host},
                )
                return PlainTextResponse("cross-origin request rejected", status_code=403)
        return await call_next(request)

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
