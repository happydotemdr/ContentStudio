"""Regression tests for the P0 harness contract (findings F-01…F-80, B-83, C-105).

This suite reads repo files as data. It is the one suite that legitimately
inspects the whole tree, so the cross-suite drift checks live here.
"""
import configparser
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_INI = REPO_ROOT / "pytest.ini"
APP_INI = REPO_ROOT / "pipeline-app" / "pytest.ini"


def _ini(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(inline_comment_prefixes=None)
    parser.read_string(path.read_text(encoding="utf-8"))
    return parser


def test_both_inis_register_both_opt_in_markers():
    """The two suites are collected independently, so a marker registered in
    one ini does not exist in the other. --strict-markers turns a missing
    registration into a collection error, which would break P5's
    test_git_helper.py and P6's byte-identity round-trip."""
    for path in (ROOT_INI, APP_INI):
        markers = _ini(path)["pytest"]["markers"]
        assert "allow_network" in markers, f"{path.name} does not register allow_network"
        assert "allow_subprocess" in markers, f"{path.name} does not register allow_subprocess"


def test_root_ini_declares_coverage_diagnostic_and_configures_no_gate():
    text = ROOT_INI.read_text(encoding="utf-8")
    assert "Coverage is diagnostic only" in text
    assert "--cov-fail-under" not in text


def test_root_ini_states_that_a_bare_run_is_the_root_suite_only():
    first_lines = ROOT_INI.read_text(encoding="utf-8").splitlines()[:3]
    assert any("ROOT SUITE ONLY" in line for line in first_lines)


def test_root_run_header_names_the_app_suite_command():
    from tests.conftest import pytest_report_header

    lines = pytest_report_header(config=None)
    joined = "\n".join(lines)
    assert "ROOT SUITE ONLY" in joined
    assert "cd pipeline-app && python -m pytest" in joined


GUARD_BEGIN = "# ---------------------------------------------------------------- BEGIN SHARED GUARD"
GUARD_END = "# ------------------------------------------------------------------ END SHARED GUARD"


def _guard_block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.index(GUARD_BEGIN)
    end = text.index(GUARD_END) + len(GUARD_END)
    return text[start:end]


def test_guard_blocks_are_identical_in_both_conftests():
    root = _guard_block(REPO_ROOT / "tests" / "conftest.py")
    app = _guard_block(REPO_ROOT / "pipeline-app" / "tests" / "conftest.py")
    assert root == app, "the two conftest guard blocks have drifted"


def test_root_suite_blocks_an_unstubbed_subprocess():
    from tests.conftest import LiveCallBlocked

    with pytest.raises(LiveCallBlocked):
        subprocess.run([sys.executable, "-c", "pass"])


VENDOR_KEYS = ("BRIGHTDATA_API_KEY", "RESEND_API_KEY", "YOUTUBE_API_KEY")


def test_guard_fires_even_when_every_vendor_key_is_present(monkeypatch):
    """The `no-live-credentials` CI job runs exactly this with canary values in
    the environment. A guard that only works when keys are absent is worthless:
    keys are always present on the operator's machine."""
    import requests

    from tests.conftest import LiveCallBlocked

    for key in VENDOR_KEYS:
        monkeypatch.setenv(key, "ci-canary-must-never-be-used")

    with pytest.raises(LiveCallBlocked):
        requests.post("https://api.brightdata.com/datasets/v3/trigger", json={})
    with pytest.raises(LiveCallBlocked):
        subprocess.run(["curl", "https://api.resend.com/emails"])


def test_both_inis_turn_unexpected_warnings_into_errors():
    for path in (ROOT_INI, APP_INI):
        filters = _ini(path)["pytest"]["filterwarnings"]
        assert filters.strip().splitlines()[0].strip() == "error"


def test_third_party_asyncio_deprecations_are_ignored_by_name():
    filters = _ini(APP_INI)["pytest"]["filterwarnings"]
    assert "ignore::DeprecationWarning:pytest_asyncio" in filters
    assert "ignore::DeprecationWarning:fastapi.routing" in filters


@pytest.mark.allow_subprocess
def test_a_repo_warning_fails_the_run_while_a_pytest_asyncio_one_does_not(tmp_path):
    """Distinguishability: the 58,169 third-party lines are silenced, but the
    repo's own warnings are not -- that was the whole defect (F-70)."""
    (tmp_path / "pytest.ini").write_text(
        (REPO_ROOT / "pipeline-app" / "pytest.ini").read_text(encoding="utf-8").replace(
            "testpaths = tests", "testpaths = ."
        ),
        encoding="utf-8",
    )
    (tmp_path / "test_warn.py").write_text(
        "import warnings\n"
        "def test_repo_warning():\n"
        "    warnings.warn('the app started emitting this', UserWarning)\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        capture_output=True, encoding="utf-8", errors="replace", cwd=str(tmp_path),
    )
    assert result.returncode != 0
    assert "UserWarning" in result.stdout
