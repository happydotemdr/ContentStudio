import asyncio
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Callable


@dataclass
class TurnResult:
    session_id: str | None
    result_text: str | None
    cost_usd: float | None
    success: bool


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
    which_fn: Callable[[str], str | None] = shutil.which,
) -> list[str]:
    """Build the claude argv WITHOUT the prompt.

    The prompt is deliberately not placed on the command line. On Windows
    `claude` resolves to an npm .cmd shim, which _platform_argv has to run
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
        "--allowedTools", allowed_tools,
    ]
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


def scoped_permissions_settings() -> str:
    """Inline --settings JSON scoping Write/Edit to runs/** and rgs-briefs/**,
    per the design spec's §5 permission-scoping requirement — a pipeline-stage
    turn must never touch docs/, output/, or .claude/skills/. The Tool(pattern)
    syntax mirrors --allowedTools "Bash(git diff *)" from Claude Code's own
    headless-mode docs; re-verify the exact permission-rule syntax against
    `claude --help` / the current settings reference when implementing this
    task, since CLI flag/settings shapes can change between releases."""
    return json.dumps({
        "permissions": {
            "allow": [
                "Write(runs/**)",
                "Edit(runs/**)",
                "Write(rgs-briefs/**)",
                "Edit(rgs-briefs/**)",
            ],
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


def _platform_argv(argv: list[str]) -> list[str]:
    """On Windows, `claude` resolves via shutil.which to an npm .cmd/.bat shim,
    which asyncio.create_subprocess_exec cannot exec directly (it is not a real
    PE executable) — it must be run through the shell via `cmd /c`. Other
    platforms and a plain .exe/extensionless binary pass through unchanged."""
    if os.name == "nt" and argv[0].lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c"] + argv
    return argv


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


async def stream_claude_turn(
    prompt: str,
    cwd: Path,
    resume_session_id: str | None,
    allowed_tools: str = "Read,Glob,Grep,Write,Edit",
    settings_path: str | None = None,
) -> AsyncIterator[dict]:
    argv = _platform_argv(build_claude_argv(prompt, resume_session_id, allowed_tools, settings_path))
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
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
            process.kill()
            await process.wait()
