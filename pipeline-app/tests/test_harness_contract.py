"""Regression tests for the P0 harness contract, app-suite half."""
import configparser
import os
import subprocess
import sys
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
