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


def test_a_second_app_instance_does_not_orphan_a_live_turn(repo_root: Path):
    """FAULT. This is `uvicorn --workers 2` against a running turn."""
    from pipeline_app import db as db_mod

    db_path = repo_root / "pipeline.db"
    first = create_app(repo_root=repo_root, db_path=db_path)
    try:
        project_id = db_mod.create_project(first.state.conn, "a-1", "a", "generic",
                                           "2026-08-08T00:00:00+00:00")
        stage_row_id = db_mod.create_stage_row(first.state.conn, project_id, "ideation", "running")
        db_mod.create_turn(first.state.conn, stage_row_id, "running",
                           "2026-08-08T00:00:00+00:00", "e/1.jsonl")

        second = create_app(repo_root=repo_root, db_path=db_path)
        try:
            assert len(db_mod.list_running_turns(second.state.conn)) == 1
            assert db_mod.get_stage_by_row_id(second.state.conn, stage_row_id)["status"] == "running"
        finally:
            second.state.conn.close()
    finally:
        first.state.conn.close()


def test_a_skipped_sweep_is_distinguishable_from_a_clean_one(repo_root: Path):
    """DISTINGUISHABILITY. `orphaned_count == 0` means 'I swept and found
    nothing'. A second instance that never swept must not report the same
    thing -- that equivalence is the whole defect."""
    db_path = repo_root / "pipeline.db"
    first = create_app(repo_root=repo_root, db_path=db_path)
    try:
        assert first.state.orphaned_count == 0

        second = create_app(repo_root=repo_root, db_path=db_path)
        try:
            assert second.state.orphaned_count is None
        finally:
            second.state.conn.close()
    finally:
        first.state.conn.close()


def test_a_skipped_sweep_records_a_warning_event(repo_root: Path, tmp_path: Path, monkeypatch):
    """SURFACING."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "obs-logs")
    db_path = repo_root / "pipeline.db"
    first = create_app(repo_root=repo_root, db_path=db_path)
    try:
        second = create_app(repo_root=repo_root, db_path=db_path)
        try:
            rows = first.state.conn.execute(
                "SELECT * FROM events WHERE kind = 'app.startup.reconcile_skipped'"
            ).fetchall()
            assert len(rows) == 1
            assert rows[0]["severity"] == "warning"
        finally:
            second.state.conn.close()
    finally:
        first.state.conn.close()


def test_an_expired_lease_is_reclaimed_so_a_real_restart_still_sweeps(repo_root: Path):
    """A crashed instance must not block reconciliation forever."""
    db_path = repo_root / "pipeline.db"
    first = create_app(repo_root=repo_root, db_path=db_path)
    try:
        first.state.conn.execute(
            "UPDATE app_instances SET heartbeat_at = '2020-01-01T00:00:00+00:00' WHERE id = 1"
        )
        first.state.conn.commit()
        second = create_app(repo_root=repo_root, db_path=db_path)
        try:
            assert second.state.orphaned_count == 0  # swept, not skipped
        finally:
            second.state.conn.close()
    finally:
        first.state.conn.close()


def test_a_clean_shutdown_releases_the_lease_so_a_restart_sweeps_immediately(repo_root: Path):
    """A crash leaves the lease to expire (the test above). A CLEAN shutdown
    must not make a genuine restart wait out the same window -- that is
    exactly what `_release_reconcile_lease` exists for, and none of the four
    tests above calls it at all."""
    from fastapi.testclient import TestClient

    db_path = repo_root / "pipeline.db"
    first = create_app(repo_root=repo_root, db_path=db_path)
    with TestClient(first):
        pass  # drives the lifespan: startup is a no-op here, shutdown releases the lease

    second = create_app(repo_root=repo_root, db_path=db_path)
    try:
        assert second.state.orphaned_count == 0  # swept immediately, not after a 120s wait
    finally:
        second.state.conn.close()


def test_the_banner_and_the_doctor_panel_never_disagree_in_one_response(
        repo_root: Path, monkeypatch):
    """A-83: two answers to the same question in one HTML response must be
    the SAME answer, on every host -- not merely equal on the host that
    happens to be running the test. A plain boolean flip cannot prove this
    reliably: if only ONE reader is actually wired to the shared probe, the
    unwired reader falls through to the REAL machine's `claude`-on-PATH
    state, and on any host where that happens to be `True`, it coincidentally
    matches the mock's first value and the test passes with the defect fully
    present. A fake, unmistakable `path` cannot coincidentally match
    anything real, so any reader that bypasses the shared probe is caught
    unconditionally."""
    from fastapi.testclient import TestClient
    from pipeline_app import preflight

    (repo_root / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
    flip = iter([True, False] * 20)
    monkeypatch.setattr(
        preflight, "check_cli_available",
        lambda *a, **k: {"available": next(flip), "path": r"C:\sentinel\claude.cmd", "error": None},
    )
    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    try:
        client = TestClient(app)
        resp = client.get("/doctor")
        # The panel must be reading the probe, not the host: pre-fix doctor.py's
        # `from ... import` binding escaped a plain module-attribute patch and
        # rendered the real machine's path instead.
        assert r"C:\sentinel\claude.cmd" in resp.text
        banner_online = "SYSTEM ONLINE" in resp.text
        panel_found = "NOT FOUND" not in resp.text
        assert banner_online == panel_found
    finally:
        app.state.conn.close()


def test_the_banner_reflects_a_cli_that_appeared_after_startup(repo_root: Path, monkeypatch):
    """Restart was the only way to reconcile the two, and nothing said so."""
    from fastapi.testclient import TestClient
    from pipeline_app import preflight

    available = {"value": False}
    monkeypatch.setattr(
        preflight, "check_cli_available",
        lambda *a, **k: {"available": available["value"], "path": None, "error": "not found"},
    )
    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    try:
        client = TestClient(app)
        assert "CLI UNAVAILABLE" in client.get("/").text

        available["value"] = True
        app.state.cli_probe.invalidate()  # stand in for the TTL elapsing
        assert "SYSTEM ONLINE" in client.get("/").text
    finally:
        app.state.conn.close()


def test_a_long_running_instance_keeps_its_heartbeat_fresh(repo_root: Path, monkeypatch):
    """A-76 REOPENED past the startup window, caught in review: without a
    periodic refresh, ANY instance older than RECONCILE_LEASE_SECONDS looks
    stale to a later instance regardless of whether it is still alive.
    Compared against a fixed 2020 timestamp rather than a freshly-read one,
    so the assertion cannot pass on second-level rounding coincidence."""
    import time
    from fastapi.testclient import TestClient
    from pipeline_app import main as main_mod

    monkeypatch.setattr(main_mod, "HEARTBEAT_INTERVAL_SECONDS", 0.05)
    db_path = repo_root / "pipeline.db"
    app = create_app(repo_root=repo_root, db_path=db_path)
    app.state.conn.execute(
        "UPDATE app_instances SET heartbeat_at = '2020-01-01T00:00:00+00:00' WHERE id = 1"
    )
    app.state.conn.commit()
    with TestClient(app):
        time.sleep(0.3)
        refreshed = app.state.conn.execute(
            "SELECT heartbeat_at FROM app_instances WHERE id = 1"
        ).fetchone()["heartbeat_at"]
    assert refreshed != "2020-01-01T00:00:00+00:00"
