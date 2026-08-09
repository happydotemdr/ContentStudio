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
