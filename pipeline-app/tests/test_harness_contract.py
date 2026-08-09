"""Regression tests for the P0 harness contract, app-suite half."""
import configparser
import os
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
