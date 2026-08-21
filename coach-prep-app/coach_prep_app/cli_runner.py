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


# --- Isolated `claude -p` invocation ----------------------------------------
#
# ONE definition of the isolation policy, shared by every call site that sends
# client material to Anthropic: generate.py (drafting), select_frameworks.py
# (activity selection), and tools/build_framework_catalog.py (cataloguing).
# Copying this per module is how one of them quietly drifts into allowing a
# tool or reading an MCP config -- which is the single failure this whole app
# is built to prevent. Same shape as pipeline_app/comment_draft.py's.

import json
import re
import sys
import tempfile

DEFAULT_TIMEOUT_S = 180

DISALLOWED_TOOLS = (
    "Bash,PowerShell,WebFetch,WebSearch,Read,Write,Edit,NotebookEdit,"
    "Glob,Grep,Task,Skill,TodoWrite,BashOutput,KillShell"
)

DELIMITER = "<<<BUNDLE>>>"
_DELIMITER_SCRUB = "[delimiter removed]"
_DELIMITER_RE = re.compile(re.escape(DELIMITER), re.IGNORECASE)


def scrub_delimiter(text: str) -> str:
    """Untrusted client text (a meeting transcript, a sent email, a converted
    framework doc) with every literal copy of the prompt's own fence delimiter
    neutralized -- without this, text containing the delimiter closes the
    fenced block early and everything after it reads as prompt rather than as
    material to draft from. Same hazard and same fix as
    pipeline_app/comment_draft.py's scrub_delimiter."""
    return _DELIMITER_RE.sub(_DELIMITER_SCRUB, text)


def parse_envelope(stdout: str) -> str | None:
    try:
        envelope = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(envelope, dict) or envelope.get("is_error"):
        return None
    inner = envelope.get("result")
    return inner if isinstance(inner, str) and inner.strip() else None


def run_isolated(prompt: str, timeout_s: int = DEFAULT_TIMEOUT_S, label: str = "cli_runner") -> str | None:
    """Run one `claude -p` turn with every tool denied, no MCP servers, and an
    empty scratch working directory. Returns the model's text, or None on any
    failure -- never raises, so a caller looping over several clients or
    several corpus files is not aborted by one bad turn.

    `label` only prefixes diagnostics on stderr, so a failure names which
    stage produced it."""
    try:
        binary = resolve_claude_binary()
    except FileNotFoundError as exc:
        print(f"{label}: {exc}", file=sys.stderr)
        return None

    argv = platform_argv([
        binary, "-p", "--output-format", "json",
        "--strict-mcp-config",
        "--disallowedTools", DISALLOWED_TOOLS,
    ])

    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as scratch:
            try:
                process = subprocess.Popen(
                    argv, cwd=scratch, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                )
            except (OSError, ValueError) as exc:
                print(f"{label}: could not start claude: {exc}", file=sys.stderr)
                return None
            try:
                stdout, _ = process.communicate(prompt, timeout=timeout_s)
            except subprocess.TimeoutExpired:
                kill_process_tree(process)
                try:
                    process.communicate(timeout=5)
                except (subprocess.TimeoutExpired, OSError, ValueError):
                    pass
                print(f"{label}: timed out after {timeout_s}s", file=sys.stderr)
                return None
            except (OSError, ValueError) as exc:
                kill_process_tree(process)
                print(f"{label}: subprocess failed: {exc}", file=sys.stderr)
                return None
    except OSError as exc:
        print(f"{label}: scratch directory failed: {exc}", file=sys.stderr)
        return None

    if process.returncode != 0:
        print(f"{label}: claude exited {process.returncode}", file=sys.stderr)
        return None

    return parse_envelope(stdout)
