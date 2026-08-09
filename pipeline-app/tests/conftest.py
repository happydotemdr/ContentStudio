"""App-suite conftest: the wrong-tree guard, the live-call guard, the
connection-leak detector, and the shared conn/client fixtures.

Sibling: <repo>/tests/conftest.py. The guard block between the BEGIN/END
markers is duplicated there verbatim, not imported (finding F-64).
"""
from __future__ import annotations

import asyncio
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent

# Modules whose tests legitimately execute a real child process.
#
# KEYED BY OWNING PACKAGE so each remediation agent can find its own entries
# with one grep for its package id and never has to read P0's plan. Add an
# entry only when the child process is the thing under test; everything else
# gets a stub. Entries may be added by the owning package as it needs them --
# unlike _KNOWN_CONNECTION_LEAKS below, this list is not a defect backlog.
#
# P0 deliberately has no entry here: tests/test_harness_contract.py's one real
# subprocess spawn (test_marked_test_may_spawn_a_real_process) already opts in
# via @pytest.mark.allow_subprocess, and this same file also carries the
# negative test proving the guard blocks an unmarked subprocess call
# (test_unstubbed_subprocess_run_is_blocked) -- a module-wide allowance here
# would defeat that test and let real subprocess calls through unguarded for
# the rest of the file. See P0-task-5-report.md for the full writeup.
_SUBPROCESS_ALLOWED_BY_PACKAGE: dict[str, dict[str, str]] = {
    "P4": {
        "tests/test_cli_runner.py": "one real asyncio child process at :400",
    },
    "P5": {
        "tests/test_git_helper.py": "builds a fixture repo with a real `git init`",
    },
    "P6": {
        # P6 reported a byte-identity round-trip that spawns sys.executable.
        "tests/test_discovery_youtube.py": "byte-identity round-trip spawns sys.executable",
    },
}

# Flattened once at import; the per-package structure above is the source of truth.
_SUBPROCESS_ALLOWED_MODULES: dict[str, str] = {
    module: f"{package} -- {reason}"
    for package, modules in _SUBPROCESS_ALLOWED_BY_PACKAGE.items()
    for module, reason in modules.items()
}


def _module_key(request) -> str:
    return Path(str(request.node.fspath)).resolve().relative_to(APP_ROOT).as_posix()


def pytest_sessionstart(session):
    """F-63: `pipeline_app` is pip-installed editable against the MAIN checkout.
    Any invocation that does not put this tree first on sys.path tests code the
    author is not editing, and passes or fails on it silently."""
    import pipeline_app

    resolved = Path(pipeline_app.__file__).resolve().parent
    expected = (APP_ROOT / "pipeline_app").resolve()
    if resolved != expected:
        raise pytest.UsageError(
            f"pipeline_app resolves to {resolved}, but this suite is {expected}.\n"
            "An editable install is shadowing the working tree (finding F-63): the "
            "tests would run against a different checkout.\n"
            "Fix: `python -m pip uninstall -y pipeline-app`, then invoke the suite as "
            "`cd pipeline-app && python -m pytest` so python -m's cwd prepend is the "
            "only source of the package."
        )


# ---------------------------------------------------------------- BEGIN SHARED GUARD
# Duplicated verbatim in the sibling conftest. Keep the two byte-identical;
# tests/test_harness_contract.py::test_guard_blocks_are_identical asserts it.


class LiveCallBlocked(RuntimeError):
    """A test reached the network or spawned a process without stubbing it."""


_GUARD_MESSAGE = (
    "{what} was called from a test with no stub.\n"
    "BRIGHTDATA_API_KEY, RESEND_API_KEY and YOUTUBE_API_KEY are all present in the "
    "ambient environment on this machine, and Bright Data bills per record: one "
    "forgotten stub spawns a real, billed job and the test still passes (finding F-68).\n"
    "Fix: stub the call. If the test genuinely must be real, mark it "
    "@pytest.mark.{mark} and say why in its docstring.\n"
    "call args: {args!r}"
)


def _blocked(what: str, mark: str):
    def _raise(*args, **kwargs):
        raise LiveCallBlocked(_GUARD_MESSAGE.format(what=what, mark=mark, args=args))

    return _raise


@pytest.fixture(autouse=True)
def _block_live_calls(request, monkeypatch):
    """Autouse: make the outbound seams raise unless the test opts in.

    Runs at setup, so a test's own monkeypatch.setattr in the body or in a
    later fixture overrides it -- an explicit stub always wins.
    """
    module_key = _module_key(request)

    if (
        request.node.get_closest_marker("allow_subprocess") is None
        and module_key not in _SUBPROCESS_ALLOWED_MODULES
    ):
        monkeypatch.setattr(subprocess, "Popen", _blocked("subprocess.Popen", "allow_subprocess"))
        monkeypatch.setattr(subprocess, "run", _blocked("subprocess.run", "allow_subprocess"))
        monkeypatch.setattr(
            asyncio, "create_subprocess_exec",
            _blocked("asyncio.create_subprocess_exec", "allow_subprocess"),
        )

    if request.node.get_closest_marker("allow_network") is None:
        monkeypatch.setattr(
            urllib.request, "urlopen", _blocked("urllib.request.urlopen", "allow_network")
        )
        try:
            import requests
            import requests.sessions
        except ImportError:
            pass
        else:
            for name in ("request", "get", "post", "put", "patch", "delete", "head"):
                monkeypatch.setattr(
                    requests, name, _blocked(f"requests.{name}", "allow_network")
                )
            monkeypatch.setattr(
                requests.sessions.Session, "request",
                _blocked("requests.Session.request", "allow_network"),
            )


# ------------------------------------------------------------------ END SHARED GUARD


@pytest.fixture
def conn(tmp_path):
    """The canonical DB fixture. Duplicated in 11 test files today (F-65);
    each package should delete its local copy and use this one.

    yield + unconditional close: 9 of the 11 local copies return without
    closing, which leaks the handle and -- on Windows -- can keep the tmp_path
    file locked through teardown (F-66).
    """
    from pipeline_app import db

    db_path = tmp_path / "pipeline.db"
    schema_path = APP_ROOT / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The canonical FastAPI fixture. Duplicated in 9 test files today (F-65)."""
    from fastapi.testclient import TestClient

    from pipeline_app.main import create_app

    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    with TestClient(app) as test_client:
        yield test_client
