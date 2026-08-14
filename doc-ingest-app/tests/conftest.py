"""doc-ingest-app suite conftest: subprocess/network guards + shared fixtures."""
from __future__ import annotations

import subprocess
import sqlite3
import urllib.request
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1]

_real_subprocess_run = subprocess.run
_real_urlopen = urllib.request.urlopen


@pytest.fixture(autouse=True)
def _block_unmarked_subprocess(request, monkeypatch):
    if request.node.get_closest_marker("allow_subprocess"):
        yield
        return

    def _blocked_run(*args, **kwargs):
        raise RuntimeError(
            "subprocess.run called from an unmarked test -- add "
            "@pytest.mark.allow_subprocess with a docstring justification, "
            "or stub the call."
        )

    monkeypatch.setattr(subprocess, "run", _blocked_run)
    yield
    monkeypatch.setattr(subprocess, "run", _real_subprocess_run)


@pytest.fixture(autouse=True)
def _block_unmarked_network(request, monkeypatch):
    """Blocks urllib AND requests/httpx -- urllib alone (an earlier version
    of this guard) doesn't cover what this app's own dependencies actually
    use: firecrawl-py and google-auth's credential refresh are both built on
    `requests`, not urllib, so a forgotten mock there would make a real,
    possibly billed, call while the test still passes silently. Mirrors
    pipeline-app/tests/conftest.py's guard shape."""
    if request.node.get_closest_marker("allow_network"):
        yield
        return

    def _blocked(what: str):
        def _raise(*args, **kwargs):
            raise RuntimeError(
                f"{what} called from a test with no stub -- add "
                "@pytest.mark.allow_network with a docstring justification, "
                "or mock the call (firecrawl.Firecrawl, the Drive `service` "
                "object, etc.)."
            )
        return _raise

    monkeypatch.setattr(urllib.request, "urlopen", _blocked("urllib.request.urlopen"))

    try:
        import requests
        import requests.sessions
    except ImportError:
        pass
    else:
        for name in ("request", "get", "post", "put", "patch", "delete", "head"):
            if hasattr(requests, name):
                monkeypatch.setattr(requests, name, _blocked(f"requests.{name}"))
        monkeypatch.setattr(requests.sessions.Session, "request", _blocked("requests.Session.request"))

    try:
        import httpx
    except ImportError:
        pass
    else:
        monkeypatch.setattr(httpx.Client, "request", _blocked("httpx.Client.request"))
        monkeypatch.setattr(httpx, "request", _blocked("httpx.request"))

    yield
    monkeypatch.setattr(urllib.request, "urlopen", _real_urlopen)


@pytest.fixture
def tmp_db_path(tmp_path) -> Path:
    # Use a separate temp directory for the database (not inside tmp_path,
    # which is the input tree). This ensures tests checking for no writes
    # to the input tree don't see database file changes.
    import tempfile
    db_dir = tempfile.mkdtemp()
    db_path = Path(db_dir) / "doc_ingest_test.db"
    yield db_path
    # Clean up
    import shutil
    try:
        shutil.rmtree(db_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def conn(tmp_db_path):
    from doc_ingest import db

    connection = db.init_db(tmp_db_path)
    yield connection
    connection.close()


@pytest.fixture
def lock_test_dir():
    """Real icacls locking is intentionally one-way and the same non-elevated
    account cannot undo it (spec §10) -- files created here are NOT
    guaranteed deletable after a test locks them. Deliberately NOT tmp_path:
    pytest's retention cleanup of old tmp_path runs would hit a real
    PermissionError. Gitignored; accumulates over time; clear from an
    elevated shell periodically."""
    d = Path(__file__).resolve().parent / ".lock_test_scratch"
    d.mkdir(exist_ok=True)
    return d
