"""coach-prep-app suite conftest: subprocess/network guards + shared
fixtures. Mirrors doc-ingest-app/tests/conftest.py's guard shape."""
from __future__ import annotations

import subprocess
import urllib.request
from pathlib import Path

import pytest

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
    if request.node.get_closest_marker("allow_network"):
        yield
        return

    def _blocked(what: str):
        def _raise(*args, **kwargs):
            raise RuntimeError(
                f"{what} called from a test with no stub -- add "
                "@pytest.mark.allow_network with a docstring justification, "
                "or mock the call."
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
    yield
    monkeypatch.setattr(urllib.request, "urlopen", _real_urlopen)


@pytest.fixture
def tmp_db_path(tmp_path) -> Path:
    return tmp_path / "coach_prep_test.db"


@pytest.fixture
def conn(tmp_db_path):
    from coach_prep_app import db
    connection = db.init_db(tmp_db_path)
    yield connection
    connection.close()
