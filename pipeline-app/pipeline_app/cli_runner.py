import asyncio
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Callable


@dataclass
class TurnResult:
    session_id: str | None
    result_text: str | None
    cost_usd: float | None
    success: bool


# ONE policy. --allowedTools, --disallowedTools and the --settings deny block are
# all derived from it, and permits_write() is what the tests assert on -- so the
# shipped flags cannot drift from the behaviour under test (F-11).
#
# --allowedTools is the auto-approve list and headless `claude -p` has nobody to
# approve anything absent from it, so NARROWING it is what actually restricts.
# The previous bare "Write,Edit" auto-approved every path on the machine, and the
# `permissions.allow` blob that claimed to scope writes only granted (D-43/D-44).
WRITE_ALLOW_PATTERNS = ("runs/**", "rgs-briefs/**")
WRITE_DENY_PATTERNS = (
    "docs/**",
    "output/**",
    # .claude/** entire, not just skills/**: settings.json registers
    # .claude/hooks/protect_briefs.py as a PreToolUse hook that then runs as an
    # unrestricted Python subprocess (D-46).
    ".claude/**",
    # gates.py loads scripts/lint_*.py by file path and exec_module's them INSIDE
    # the uvicorn process after every turn. A turn that edits a linter gets
    # arbitrary in-process code execution -- the exact capability the Bash and
    # PowerShell denials exist to remove (D-45).
    "scripts/**",
    "pipeline-app/**",
    "pipeline.yaml",
)
DENIED_TOOLS = ("Bash", "PowerShell", "WebFetch", "WebSearch", "NotebookEdit")

_WRITE_TOOLS = ("Write", "Edit")


def _scoped(tools: tuple[str, ...], patterns: tuple[str, ...]) -> list[str]:
    return [f"{tool}({pattern})" for pattern in patterns for tool in tools]


PIPELINE_ALLOWED_TOOLS = ",".join(
    # Task is required, not optional: midjourney-prompting's Gate B and
    # shorts-scripting's Gate E both dispatch a fresh reviewing agent through it.
    ["Read", "Glob", "Grep", "Skill", "Task"] + _scoped(_WRITE_TOOLS, WRITE_ALLOW_PATTERNS)
)
PIPELINE_DISALLOWED_TOOLS = ",".join(
    list(DENIED_TOOLS) + _scoped(_WRITE_TOOLS, WRITE_DENY_PATTERNS)
)


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def permits_write(path: str) -> bool:
    """Would a pipeline-stage turn be allowed to write `path`? Repo-relative,
    forward slashes. This is the single source of truth for the write scope --
    assert on this, never on the flag literals."""
    normalised = path.replace("\\", "/")
    if (normalised.startswith("/") or ".." in normalised.split("/")
            or re.match(r"^[A-Za-z]:", normalised)):
        return False        # nothing outside the project is auto-approved
    if any(_glob_to_regex(p).match(normalised) for p in WRITE_DENY_PATTERNS):
        return False
    return any(_glob_to_regex(p).match(normalised) for p in WRITE_ALLOW_PATTERNS)


def resolve_claude_binary(which_fn: Callable[[str], str | None] = shutil.which) -> str:
    path = which_fn("claude")
    if path is None:
        raise FileNotFoundError(
            "claude CLI not found on PATH. Install Claude Code and ensure 'claude' is on PATH."
        )
    return path


def build_claude_argv(
    prompt: str,
    resume_session_id: str | None,
    allowed_tools: str,
    settings_path: str | None,
    disallowed_tools: str | None = None,
    which_fn: Callable[[str], str | None] = shutil.which,
) -> list[str]:
    """Build the claude argv WITHOUT the prompt.

    The prompt is deliberately not placed on the command line. On Windows
    `claude` resolves to an npm .cmd shim, which platform_argv has to run
    through `cmd /c`; cmd.exe does not honour subprocess's `\\"` escaping (a
    backslash is literal and a quote just toggles quoting), so any `"` in a
    user-supplied prompt would break out of quoting and let the rest of the
    prompt run as shell commands — completely bypassing the --allowedTools
    sandbox. `claude -p` with no positional prompt reads the prompt from stdin
    (verified against `claude --help` and a live run, 2026-07-26), so
    stream_claude_turn feeds it over a stdin pipe instead.
    """
    binary = resolve_claude_binary(which_fn)
    argv = [
        binary, "-p",
        "--output-format", "stream-json",
        "--include-partial-messages",
        # Required by the real claude CLI whenever --print is combined with
        # --output-format stream-json; omitting it makes the CLI exit
        # immediately with "Error: When using --print, --output-format=
        # stream-json requires --verbose" (verified against a live run,
        # 2026-07-26).
        "--verbose",
        # A pipeline turn must not inherit whatever MCP servers happen to be
        # configured on the machine running it -- a real recorded init event
        # showed 13 unscoped MCP servers attached to a pipeline turn,
        # including family-brain's brain_* tools, which CLAUDE.md firewalls
        # off absolutely. --disallowedTools' path-scoped Write/Edit denials
        # don't touch MCP tool names (e.g. mcp__filesystem__write_file), so
        # this is the only thing that actually closes that gap. No
        # --mcp-config flag is passed below, so --strict-mcp-config alone
        # means zero MCP servers load (verified against `claude --help`,
        # 2026-07-27). Unconditional: pipeline turns never legitimately need
        # any MCP server.
        "--strict-mcp-config",
        "--allowedTools", allowed_tools,
    ]
    if disallowed_tools:
        argv += ["--disallowedTools", disallowed_tools]
    if resume_session_id:
        argv += ["--resume", resume_session_id]
    if settings_path:
        argv += ["--settings", settings_path]
    return argv


async def parse_stream_json_lines(lines: AsyncIterator[bytes]) -> AsyncIterator[dict]:
    async for line in lines:
        text = line.decode("utf-8").strip()
        if not text:
            continue
        try:
            yield json.loads(text)
        except json.JSONDecodeError:
            continue


def pipeline_permissions_settings() -> str:
    """Inline --settings JSON for a stage turn. `allow` pre-approves the two
    write roots; `deny` is the half that actually refuses. The former name
    (scoped_permissions_settings) and its docstring claimed an allow-only blob
    scoped writes, which it never did (D-43)."""
    return json.dumps({
        "permissions": {
            "allow": _scoped(_WRITE_TOOLS, WRITE_ALLOW_PATTERNS),
            "deny": list(DENIED_TOOLS) + _scoped(_WRITE_TOOLS, WRITE_DENY_PATTERNS),
        }
    })


def extract_turn_result(events: list[dict]) -> TurnResult:
    session_id = None
    result_text = None
    cost_usd = None
    success = False
    for event in events:
        if event.get("type") == "system" and event.get("subtype") == "init":
            session_id = event.get("session_id")
        if event.get("type") == "result":
            result_text = event.get("result")
            cost_usd = event.get("total_cost_usd")
            success = not event.get("is_error", False)
    return TurnResult(session_id=session_id, result_text=result_text, cost_usd=cost_usd, success=success)


def platform_argv(argv: list[str]) -> list[str]:
    """On Windows, `claude` resolves via shutil.which to an npm .cmd/.bat shim,
    which asyncio.create_subprocess_exec cannot exec directly (it is not a real
    PE executable) — it must be run through the shell via `cmd /c`. Other
    platforms and a plain .exe/extensionless binary pass through unchanged."""
    if os.name == "nt" and argv[0].lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c"] + argv
    return argv


def kill_process_tree(process) -> None:
    """Terminate the child *and every process it spawned*.

    On Windows `claude` resolves to an npm .cmd shim that platform_argv has to
    run through `cmd /c`, so `process` is cmd.exe and the real claude/node
    process is a descendant. process.kill() sends the kill to cmd.exe only,
    orphaning that descendant to run to completion — it would keep writing into
    runs/ and rgs-briefs/ under a turn the app has already marked aborted and
    released the single-flight lock for (verified empirically: the descendant's
    completion marker still appeared after process.kill()). `taskkill /T` walks
    the whole tree; /F forces it. Harmless on a leaf process with no children,
    so it is applied unconditionally on nt rather than re-deriving whether the
    cmd wrapper was used for this particular invocation.

    Never raises: if the PID already exited (a race against the returncode
    check) taskkill just exits nonzero, which is not checked, and a taskkill
    that itself hangs is bounded by the timeout.
    """
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                capture_output=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            pass  # cleanup is best-effort; process.wait() below is the real signal
    else:
        process.kill()


async def _feed_prompt_stdin(process, prompt: str) -> None:
    """Write the prompt to the child's stdin and close it.

    Run as a background task so a prompt larger than the OS pipe buffer cannot
    deadlock: the child may not drain stdin until it has written some stdout,
    and stream_claude_turn is concurrently reading stdout."""
    stdin = process.stdin
    if stdin is None:
        return
    try:
        stdin.write(prompt.encode("utf-8"))
        await stdin.drain()
    except (BrokenPipeError, ConnectionResetError):
        pass  # child exited early; its stdout/exit code is the real signal
    finally:
        try:
            stdin.close()
            await stdin.wait_closed()
        except (BrokenPipeError, ConnectionResetError, AttributeError):
            pass


# Credentials the claude CLI itself may need to authenticate. Everything else
# matching a secret-shaped suffix is stripped from a stage turn's environment:
# a turn has no legitimate use for the app's vendor keys, and .claude/hooks/**
# runs as an unrestricted subprocess that would otherwise inherit them (D-46).
_ENV_KEEP = frozenset({"ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN"})
_ENV_SECRET_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD")


def child_env() -> dict[str, str]:
    env = {
        key: value for key, value in os.environ.items()
        if key in _ENV_KEEP or not key.upper().endswith(_ENV_SECRET_SUFFIXES)
    }
    env["PYTHONIOENCODING"] = "utf-8"
    return env


async def stream_claude_turn(
    prompt: str,
    cwd: Path,
    resume_session_id: str | None,
    # Task is required, not optional: midjourney-prompting's Gate B and
    # shorts-scripting's Gate E both dispatch a fresh reviewing agent through
    # it. PIPELINE_DISALLOWED_TOOLS deliberately does not deny Task, but
    # --allowedTools is the auto-approve list and headless -p has nobody to
    # approve anything absent from it -- so omitting Task here silently
    # degraded Gate B rather than surfacing an error.
    allowed_tools: str = PIPELINE_ALLOWED_TOOLS,
    disallowed_tools: str = PIPELINE_DISALLOWED_TOOLS,
    settings_path: str | None = None,
) -> AsyncIterator[dict]:
    argv = platform_argv(build_claude_argv(
        prompt, resume_session_id, allowed_tools, settings_path, disallowed_tools,
    ))
    env = child_env()
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(cwd),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=env,
        limit=1024 * 1024 * 10,  # stream-json + --include-partial-messages lines
                                  # can exceed the asyncio StreamReader default
                                  # 64 KiB line limit; 10 MiB avoids LimitOverrunError.
    )
    stdin_task = asyncio.ensure_future(_feed_prompt_stdin(process, prompt))
    try:
        assert process.stdout is not None
        async for event in parse_stream_json_lines(process.stdout):
            yield event
        await stdin_task
        await process.wait()
    finally:
        if not stdin_task.done():
            stdin_task.cancel()
        # Guarantees the subprocess is not orphaned when this generator is
        # closed early (client disconnect, exception in the caller) — see
        # run_stage_turn's use of contextlib.aclosing in Task 8.
        if process.returncode is None:
            kill_process_tree(process)
            await process.wait()
