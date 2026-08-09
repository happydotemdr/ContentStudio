"""Regression tests for the P0 harness contract, app-suite half."""
import configparser
import os
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
APP_INI = APP_ROOT / "pytest.ini"


def _ini(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(inline_comment_prefixes=None)
    parser.read_string(path.read_text(encoding="utf-8"))
    return parser


def test_app_ini_registers_the_two_opt_in_markers():
    markers = _ini(APP_INI)["pytest"]["markers"]
    assert "allow_network" in markers
    assert "allow_subprocess" in markers


def test_app_ini_declares_coverage_diagnostic_and_configures_no_gate():
    text = APP_INI.read_text(encoding="utf-8")
    assert "Coverage is diagnostic only" in text
    assert "--cov-fail-under" not in text


def test_session_start_accepts_the_working_tree():
    import conftest

    conftest.pytest_sessionstart(session=None)  # must not raise


def test_session_start_rejects_a_pipeline_app_from_another_checkout(monkeypatch, tmp_path):
    import types

    import conftest

    foreign = tmp_path / "other-checkout" / "pipeline-app" / "pipeline_app"
    foreign.mkdir(parents=True)
    (foreign / "__init__.py").write_text("", encoding="utf-8")
    fake = types.ModuleType("pipeline_app")
    fake.__file__ = str(foreign / "__init__.py")
    monkeypatch.setitem(sys.modules, "pipeline_app", fake)

    with pytest.raises(pytest.UsageError) as excinfo:
        conftest.pytest_sessionstart(session=None)

    message = str(excinfo.value)
    assert str(foreign) in message                       # the wrong tree, named
    assert str(APP_ROOT / "pipeline_app") in message      # the right tree, named
    assert "pip uninstall" in message


def test_unstubbed_requests_post_is_blocked():
    import requests

    import conftest

    with pytest.raises(conftest.LiveCallBlocked) as excinfo:
        requests.post("https://api.brightdata.com/datasets/v3/trigger", json={})
    assert "BRIGHTDATA_API_KEY" in str(excinfo.value)


def test_unstubbed_urlopen_is_blocked():
    import conftest

    with pytest.raises(conftest.LiveCallBlocked):
        urllib.request.urlopen("https://www.googleapis.com/youtube/v3/search")


def test_unstubbed_subprocess_run_is_blocked():
    import conftest

    with pytest.raises(conftest.LiveCallBlocked):
        subprocess.run(["yt-dlp", "--dump-json", "https://youtube.com/watch?v=x"])


@pytest.mark.allow_subprocess
def test_marked_test_may_spawn_a_real_process():
    result = subprocess.run(
        [sys.executable, "-c", "print('ok')"],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    assert result.stdout.strip() == "ok"


def test_a_stubbed_call_still_wins_over_the_guard(monkeypatch):
    """The guard must never defeat an explicit stub -- 40+ existing tests
    monkeypatch subprocess.run and must keep working."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: "stubbed")
    assert subprocess.run(["anything"]) == "stubbed"


VENDOR_KEYS = ("BRIGHTDATA_API_KEY", "RESEND_API_KEY", "YOUTUBE_API_KEY")


def test_guard_fires_even_when_every_vendor_key_is_present(monkeypatch):
    """The `no-live-credentials` CI job runs exactly this with canary values in
    the environment. A guard that only works when keys are absent is worthless:
    keys are always present on the operator's machine."""
    import requests

    import conftest

    for key in VENDOR_KEYS:
        monkeypatch.setenv(key, "ci-canary-must-never-be-used")

    with pytest.raises(conftest.LiveCallBlocked):
        requests.post("https://api.brightdata.com/datasets/v3/trigger", json={})
    with pytest.raises(conftest.LiveCallBlocked):
        subprocess.run(["curl", "https://api.resend.com/emails"])


def test_shared_conn_fixture_is_initialised_and_closes(conn):
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stages'").fetchone()
    assert row is not None


def test_shared_client_fixture_serves_the_app(client):
    assert client.get("/doctor").status_code == 200


def test_shared_client_fixture_closes_its_connection_on_teardown(tmp_path, monkeypatch):
    """create_app() opens app.state.conn (pipeline_app/main.py) and wires no
    shutdown handler to close it. The client fixture must close it itself on
    teardown -- on both the passing and the raising path -- or every test
    that requests `client` leaks a sqlite handle, which is exactly the class
    of leak this fixture exists to eliminate (F-65/F-66)."""
    import sqlite3

    import conftest

    gen = conftest.client.__wrapped__(tmp_path, monkeypatch)
    test_client = next(gen)
    connection = test_client.app.state.conn

    # Sanity: the connection is live while the fixture is active.
    connection.execute("SELECT 1")

    with pytest.raises(StopIteration):
        next(gen)  # drive the fixture generator through its teardown

    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def test_unclosed_detects_an_open_connection(tmp_path):
    import conftest

    connection = sqlite3.connect(tmp_path / "x.db")
    try:
        assert conftest._is_open(connection) is True
    finally:
        connection.close()


def test_unclosed_does_not_flag_a_closed_connection(tmp_path):
    import conftest

    connection = sqlite3.connect(tmp_path / "x.db")
    connection.close()
    assert conftest._is_open(connection) is False


def test_leak_allowlist_entries_all_still_exist():
    """Shrink-only ratchet: an allowlisted module that has been renamed or
    fixed must be removed from the list, not left to rot."""
    import conftest

    for rel in conftest._KNOWN_CONNECTION_LEAKS:
        assert (APP_ROOT / rel).exists(), f"{rel} is allowlisted but does not exist"


def test_both_allowlists_are_keyed_by_owning_package():
    """Every remediation agent must be able to find its own entries with one
    grep for its package id, without reading P0's plan."""
    import conftest
    import re as _re

    for mapping in (conftest._CONNECTION_LEAKS_BY_PACKAGE, conftest._SUBPROCESS_ALLOWED_BY_PACKAGE):
        assert mapping.keys(), "an empty allowlist must be deleted, not left as {}"
        for package in mapping:
            assert _re.fullmatch(r"P\d{1,2}", package), f"{package!r} is not a package id"

    assert "P0" not in conftest._CONNECTION_LEAKS_BY_PACKAGE, (
        "P0 owns every file this suite collects for itself, so a leak in a "
        "P0-owned file has no other package to come back and convert it -- "
        "P0 must fix the leak directly instead of allowlisting it."
    )


@pytest.mark.allow_subprocess
def test_a_leaking_test_fails_with_a_nonzero_exit(tmp_path):
    """Surfacing: the operator-reachable signal is a failed test and a non-zero
    process exit, not a ResourceWarning lost in 58,169 lines (F-70)."""
    (tmp_path / "conftest.py").write_text(
        "import importlib.util\n"
        f"_spec = importlib.util.spec_from_file_location('p0conf', r'{APP_ROOT / 'tests' / 'conftest.py'}')\n"
        "_m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_m)\n"
        "_no_leaked_sqlite_connections = _m._no_leaked_sqlite_connections\n",
        encoding="utf-8",
    )
    (tmp_path / "test_leak.py").write_text(
        "import sqlite3\n"
        "def test_leaks(tmp_path):\n"
        "    sqlite3.connect(tmp_path / 'db.sqlite')\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(tmp_path), "-q", "-p", "no:cacheprovider"],
        capture_output=True, encoding="utf-8", errors="replace", cwd=str(tmp_path),
    )
    assert result.returncode != 0
    assert "sqlite connection" in result.stdout
