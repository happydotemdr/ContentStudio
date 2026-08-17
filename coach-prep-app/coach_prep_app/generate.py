# coach-prep-app/coach_prep_app/generate.py
"""Generates the coach-prep draft body via an isolated claude -p subprocess
-- same isolation pattern as pipeline_app/comment_draft.py: no tools, no
MCP, empty scratch cwd. The model cannot reach anything beyond what is
embedded in the prompt."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile

from coach_prep_app import cli_runner

DEFAULT_TIMEOUT_S = 180

DISALLOWED_TOOLS = (
    "Bash,PowerShell,WebFetch,WebSearch,Read,Write,Edit,NotebookEdit,"
    "Glob,Grep,Task,Skill,TodoWrite,BashOutput,KillShell"
)

_PROMPT_TEMPLATE = """\
You are drafting a private coach-prep note for Ryan ahead of his next session with {client_display_name}.

Everything between the delimiters below is this one client's own material. Use ONLY this material -- never invent a fact, and never reference any other client.

<<<BUNDLE>>>
## Last session's activities (source label: {email_label})
{last_meeting_email}

## Most recent meeting note (source label: {note_label})
{last_meeting_note}

## Program grounding
{program_sources_block}
<<<BUNDLE>>>

Write three sections in markdown:
1. "## Activities from last session" -- bullet the specific exercises/activities {client_display_name} was asked to do, drawn only from the last-meeting-email material.
2. "## Draft agenda" -- 3-5 bullet agenda items for the upcoming session, grounded in the program material.
3. "## PQ sparks" -- exactly 3 starter questions drawn from the program grounding's saboteur module(s).

Tag EVERY bullet inline with the exact source label it came from, in square brackets, e.g. "- Reflect on the morality exercise [{email_label}]". Use only these labels: {allowed_labels}. If a bullet has no real source, do not write it.

Return ONLY the markdown, no preamble.
"""


def build_prompt(bundle: dict) -> str:
    program_block = "\n\n".join(
        f"### {item['source_label']}\n{item['text']}" for item in bundle["program_sources"]
    )
    allowed_labels = ", ".join(
        [bundle["last_meeting_email"]["source_label"], bundle["last_meeting_note"]["source_label"]]
        + [item["source_label"] for item in bundle["program_sources"]]
    )
    return _PROMPT_TEMPLATE.format(
        client_display_name=bundle["client_display_name"],
        email_label=bundle["last_meeting_email"]["source_label"],
        last_meeting_email=bundle["last_meeting_email"]["text"],
        note_label=bundle["last_meeting_note"]["source_label"],
        last_meeting_note=bundle["last_meeting_note"]["text"],
        program_sources_block=program_block,
        allowed_labels=allowed_labels,
    )


def parse_envelope(stdout: str) -> str | None:
    try:
        envelope = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(envelope, dict) or envelope.get("is_error"):
        return None
    inner = envelope.get("result")
    return inner if isinstance(inner, str) and inner.strip() else None


def generate_draft(bundle: dict, timeout_s: int = DEFAULT_TIMEOUT_S) -> str | None:
    try:
        binary = cli_runner.resolve_claude_binary()
    except FileNotFoundError as exc:
        print(f"generate: {exc}", file=sys.stderr)
        return None

    argv = cli_runner.platform_argv([
        binary, "-p", "--output-format", "json",
        "--strict-mcp-config",
        "--disallowedTools", DISALLOWED_TOOLS,
    ])
    prompt = build_prompt(bundle)

    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as scratch:
            try:
                process = subprocess.Popen(
                    argv, cwd=scratch, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                )
            except (OSError, ValueError) as exc:
                print(f"generate: could not start claude: {exc}", file=sys.stderr)
                return None
            try:
                stdout, _ = process.communicate(prompt, timeout=timeout_s)
            except subprocess.TimeoutExpired:
                cli_runner.kill_process_tree(process)
                try:
                    process.communicate(timeout=5)
                except (subprocess.TimeoutExpired, OSError, ValueError):
                    pass
                print(f"generate: timed out after {timeout_s}s", file=sys.stderr)
                return None
            except (OSError, ValueError) as exc:
                cli_runner.kill_process_tree(process)
                print(f"generate: subprocess failed: {exc}", file=sys.stderr)
                return None
    except OSError as exc:
        print(f"generate: scratch directory failed: {exc}", file=sys.stderr)
        return None

    if process.returncode != 0:
        print(f"generate: claude exited {process.returncode}", file=sys.stderr)
        return None

    return parse_envelope(stdout)
