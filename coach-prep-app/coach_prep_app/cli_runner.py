# coach-prep-app/coach_prep_app/cli_runner.py
"""Small subprocess helpers for invoking the claude CLI. A local copy of
pipeline_app/cli_runner.py's three generic pieces -- coach-prep-app already
depends on doc-ingest-app; duplicating three small functions here avoids a
second cross-app coupling on pipeline-app."""
from __future__ import annotations

import os
import subprocess
import shutil
from typing import Callable


def resolve_claude_binary(which_fn: Callable[[str], str | None] = shutil.which) -> str:
    path = which_fn("claude")
    if path is None:
        raise FileNotFoundError(
            "claude CLI not found on PATH. Install Claude Code and ensure 'claude' is on PATH."
        )
    return path


def platform_argv(argv: list[str]) -> list[str]:
    if os.name == "nt" and argv[0].lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c"] + argv
    return argv


def kill_process_tree(process) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                capture_output=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        process.kill()
