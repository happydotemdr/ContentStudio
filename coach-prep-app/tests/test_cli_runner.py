# coach-prep-app/tests/test_cli_runner.py
from __future__ import annotations

import pytest

from coach_prep_app import cli_runner


def test_resolve_claude_binary_returns_the_resolved_path():
    path = cli_runner.resolve_claude_binary(which_fn=lambda name: "/usr/local/bin/claude")
    assert path == "/usr/local/bin/claude"


def test_resolve_claude_binary_raises_when_not_on_path():
    with pytest.raises(FileNotFoundError):
        cli_runner.resolve_claude_binary(which_fn=lambda name: None)


def test_platform_argv_wraps_cmd_shims_on_windows(monkeypatch):
    monkeypatch.setattr(cli_runner.os, "name", "nt")
    result = cli_runner.platform_argv(["claude.cmd", "-p"])
    assert result == ["cmd", "/c", "claude.cmd", "-p"]


def test_platform_argv_passes_through_a_real_binary(monkeypatch):
    monkeypatch.setattr(cli_runner.os, "name", "nt")
    result = cli_runner.platform_argv(["/usr/local/bin/claude", "-p"])
    assert result == ["/usr/local/bin/claude", "-p"]
