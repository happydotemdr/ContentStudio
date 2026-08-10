import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app import obs
from pipeline_app.main import create_app


@pytest.fixture
def repo_root(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    return tmp_path


@contextmanager
def _app_client(repo_root: Path):
    """`create_app` driven as a context manager, which is the only thing that
    runs the app's lifespan -- and therefore its shutdown hook.

    These tests used to call `create_app(...)` bare, which runs no lifespan at
    all: the shared connection stayed open for the life of the process, which
    is why this module was the `"P1"` entry in conftest.py's
    `_CONNECTION_LEAKS_BY_PACKAGE` (A-85). Shaped like the canonical `client`
    fixture in tests/conftest.py, `finally` included, so the connection also
    closes when TestClient's own startup raises.
    """
    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.state.conn.close()


def test_cli_available_true_when_binary_found(repo_root: Path, monkeypatch):
    monkeypatch.setattr(
        "pipeline_app.preflight.check_cli_available",
        lambda: {"available": True, "path": r"C:\fake\claude.CMD", "error": None},
    )
    with _app_client(repo_root) as client:
        assert client.app.state.cli_available is True


def test_cli_available_false_when_missing(repo_root: Path, monkeypatch):
    monkeypatch.setattr(
        "pipeline_app.preflight.check_cli_available",
        lambda: {"available": False, "path": None, "error": "not found"},
    )
    with _app_client(repo_root) as client:
        assert client.app.state.cli_available is False


def test_app_shutdown_closes_the_connection_and_truncates_the_wal(repo_root: Path, monkeypatch):
    monkeypatch.setattr(obs, "LOG_DIR", repo_root / "logs")
    wal_path = repo_root / "pipeline.db-wal"

    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    try:
        with TestClient(app) as client:
            assert client.get("/doctor").status_code == 200
            # Precondition, verified rather than assumed. Probed on this host:
            # after create_app + GET /doctor the -wal file exists but is 0
            # bytes, so `.exists()` on its own would hold while the
            # post-condition below ("gone, or present and empty") was ALREADY
            # satisfied -- the test would pass against an app with no shutdown
            # hook at all. Force a real write through the app's own shared
            # connection and require the WAL to actually hold data, so
            # "checkpointed away" cannot be confused with "nothing was ever
            # written".
            obs.record_event(app.state.conn, kind="test.wal_seed", severity="info",
                             source="test_main", message="force a WAL write")
            assert wal_path.stat().st_size > 0

        # Shutdown ran: the shared connection is closed...
        with pytest.raises(sqlite3.ProgrammingError):
            app.state.conn.execute("SELECT 1")
        # ...and the WAL was checkpointed away. Existence is checked FIRST:
        # closing a checkpointed WAL database deletes the -wal file outright,
        # so `.stat()` raises FileNotFoundError precisely when the
        # implementation is correct. Absent and present-but-empty are both
        # correct post-shutdown states; the failing state is a WAL that still
        # holds data.
        assert not wal_path.exists() or wal_path.stat().st_size == 0
    finally:
        app.state.conn.close()


def test_shutdown_logs_and_survives_a_checkpoint_that_fails(repo_root: Path, monkeypatch):
    """The checkpoint runs on a connection that may itself be what broke, so a
    failing PRAGMA must be reported and swallowed -- a shutdown hook that
    raises would take the whole teardown with it. Logged via obs.log rather
    than obs.record_event on purpose: the events row would be written on the
    very connection that just failed. A-85's failure mode is `latent`, not
    `silent`, so no surfacing leg is owed."""
    monkeypatch.setattr(obs, "LOG_DIR", repo_root / "logs")

    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    try:
        with TestClient(app) as client:
            assert client.get("/doctor").status_code == 200
            # Close it out from under the shutdown hook: the PRAGMA now raises.
            app.state.conn.close()
        # Leaving the `with` block at all proves shutdown did not re-raise.
        logged = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((repo_root / "logs").glob("app-*.log"))
        )
        assert "db.checkpoint_failed" in logged
        # The reason, not just the fact -- a bare "it failed" line is the same
        # defect class this programme keeps finding.
        assert "ProgrammingError" in logged
    finally:
        app.state.conn.close()
