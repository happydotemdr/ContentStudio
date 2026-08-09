"""App-suite conftest: the wrong-tree guard, the live-call guard, the
connection-leak detector, and the shared conn/client fixtures.

Sibling: <repo>/tests/conftest.py. The guard block between the BEGIN/END
markers is duplicated there verbatim, not imported (finding F-64).
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent


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
