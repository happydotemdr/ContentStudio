import asyncio
import json
import os
import sys
import time
from pathlib import Path

import pytest

from pipeline_app.cli_runner import (
    build_claude_argv,
    extract_turn_result,
    parse_stream_json_lines,
    resolve_claude_binary,
)

INJECTION_PROMPT = 'benign " & echo pwned>INJECTED.txt & echo "'


def test_resolve_claude_binary_returns_path_when_found():
    path = resolve_claude_binary(which_fn=lambda name: r"C:\fake\claude.CMD")
    assert path == r"C:\fake\claude.CMD"


def test_resolve_claude_binary_raises_when_not_found():
    with pytest.raises(FileNotFoundError):
        resolve_claude_binary(which_fn=lambda name: None)


def test_build_claude_argv_first_turn_has_no_resume():
    argv = build_claude_argv(
        "/shorts-ideation do the thing",
        resume_session_id=None,
        allowed_tools="Read,Glob,Grep,Write,Edit",
        settings_path=None,
        which_fn=lambda name: "claude",
    )
    assert argv[0] == "claude"
    assert "-p" in argv
    # The prompt is never placed on the command line — it goes over stdin.
    assert "/shorts-ideation do the thing" not in argv
    assert "--resume" not in argv
    assert "--allowedTools" in argv
    idx = argv.index("--allowedTools")
    assert argv[idx + 1] == "Read,Glob,Grep,Write,Edit"
    # --verbose is required by the real claude CLI whenever --print is combined
    # with --output-format stream-json — without it the CLI exits immediately
    # with "Error: When using --print, --output-format=stream-json requires --verbose".
    assert "--verbose" in argv


def test_build_claude_argv_resume_turn_includes_session_id():
    argv = build_claude_argv(
        "continue please",
        resume_session_id="session-abc",
        allowed_tools="Read,Glob,Grep,Write,Edit",
        settings_path=None,
        which_fn=lambda name: "claude",
    )
    idx = argv.index("--resume")
    assert argv[idx + 1] == "session-abc"
    assert "--verbose" in argv


def test_build_claude_argv_appends_disallowed_tools_when_provided():
    argv = build_claude_argv(
        "prompt text",
        resume_session_id=None,
        allowed_tools="Read,Glob,Grep,Write,Edit",
        settings_path=None,
        disallowed_tools="Bash,WebFetch",
        which_fn=lambda name: "claude",
    )
    assert "--disallowedTools" in argv
    idx = argv.index("--disallowedTools")
    assert argv[idx + 1] == "Bash,WebFetch"


def test_build_claude_argv_omits_disallowed_tools_when_not_provided():
    argv = build_claude_argv(
        "prompt text",
        resume_session_id=None,
        allowed_tools="Read,Glob,Grep,Write,Edit",
        settings_path=None,
        which_fn=lambda name: "claude",
    )
    assert "--disallowedTools" not in argv


def test_build_claude_argv_always_includes_strict_mcp_config():
    """A pipeline turn must not inherit whatever MCP servers happen to be
    configured on the machine running it -- a real recorded init event showed
    13 unscoped MCP servers attached to a pipeline turn, including
    family-brain's brain_* tools, which CLAUDE.md firewalls off absolutely.
    --disallowedTools' path-scoped Write/Edit denials don't touch MCP tool
    names (e.g. mcp__filesystem__write_file), so --strict-mcp-config is the
    only thing that actually closes this gap. No --mcp-config flag is passed,
    so --strict-mcp-config alone means zero MCP servers load (verified
    against `claude --help`, 2026-07-27)."""
    argv = build_claude_argv(
        "prompt text",
        resume_session_id=None,
        allowed_tools="Read,Glob,Grep,Write,Edit",
        settings_path=None,
        which_fn=lambda name: "claude",
    )
    assert "--strict-mcp-config" in argv


@pytest.mark.asyncio
async def test_parse_stream_json_lines_yields_parsed_dicts():
    async def fake_lines():
        for line in [b'{"type": "system", "subtype": "init"}\n', b'  \n', b'{"type": "result", "result": "ok"}\n']:
            yield line

    events = [e async for e in parse_stream_json_lines(fake_lines())]
    assert events == [
        {"type": "system", "subtype": "init"},
        {"type": "result", "result": "ok"},
    ]


@pytest.mark.asyncio
async def test_parse_stream_json_lines_skips_invalid_json():
    async def fake_lines():
        yield b"not json at all\n"
        yield b'{"type": "result", "result": "ok"}\n'

    events = [e async for e in parse_stream_json_lines(fake_lines())]
    assert events == [{"type": "result", "result": "ok"}]


def test_extract_turn_result_finds_session_id_and_result():
    events = [
        {"type": "system", "subtype": "init", "session_id": "session-xyz"},
        {"type": "assistant", "message": {}},
        {"type": "result", "result": "final text", "total_cost_usd": 0.02, "is_error": False},
    ]
    result = extract_turn_result(events)
    assert result.session_id == "session-xyz"
    assert result.result_text == "final text"
    assert result.cost_usd == 0.02
    assert result.success is True


def test_extract_turn_result_marks_failure_on_is_error():
    events = [{"type": "result", "result": "oops", "is_error": True}]
    result = extract_turn_result(events)
    assert result.success is False


def test_platform_argv_wraps_cmd_shim_on_windows(monkeypatch):
    from pipeline_app.cli_runner import platform_argv

    monkeypatch.setattr("pipeline_app.cli_runner.os.name", "nt")
    argv = platform_argv([r"C:\Users\me\AppData\Roaming\npm\claude.CMD", "-p", "hi"])
    assert argv == ["cmd", "/c", r"C:\Users\me\AppData\Roaming\npm\claude.CMD", "-p", "hi"]


def test_platform_argv_passes_through_non_windows_or_non_shim(monkeypatch):
    from pipeline_app.cli_runner import platform_argv

    monkeypatch.setattr("pipeline_app.cli_runner.os.name", "posix")
    argv = platform_argv(["/usr/local/bin/claude", "-p", "hi"])
    assert argv == ["/usr/local/bin/claude", "-p", "hi"]


class _FakeStdin:
    def __init__(self):
        self.chunks: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        self.chunks.append(data)

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        pass

    @property
    def written(self) -> bytes:
        return b"".join(self.chunks)


class _FakeStdout:
    def __init__(self, lines: list[bytes]):
        self._lines = list(lines)

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        if not self._lines:
            raise StopAsyncIteration
        return self._lines.pop(0)


class _FakeProcess:
    def __init__(self, lines: list[bytes]):
        self.stdin = _FakeStdin()
        self.stdout = _FakeStdout(lines)
        self.returncode = None

    async def wait(self) -> int:
        self.returncode = 0
        return 0

    def kill(self) -> None:
        self.returncode = -9


@pytest.mark.asyncio
async def test_prompt_is_passed_via_stdin_not_argv(monkeypatch, tmp_path: Path):
    """The user's chat message must never reach the child's command line —
    on Windows the `cmd /c` shim wrapper would interpret its metacharacters."""
    from pipeline_app import cli_runner

    monkeypatch.setattr(cli_runner, "resolve_claude_binary", lambda *a, **k: "claude")

    captured: dict = {}

    async def fake_exec(*argv, **kwargs):
        captured["argv"] = list(argv)
        proc = _FakeProcess([b'{"type": "result", "result": "ok"}\n'])
        captured["proc"] = proc
        return proc

    monkeypatch.setattr(cli_runner.asyncio, "create_subprocess_exec", fake_exec)

    events = [
        e async for e in cli_runner.stream_claude_turn(INJECTION_PROMPT, tmp_path, None)
    ]

    assert events == [{"type": "result", "result": "ok"}]
    assert INJECTION_PROMPT not in captured["argv"]
    assert not any("pwned" in part for part in captured["argv"])
    assert captured["proc"].stdin.written == INJECTION_PROMPT.encode("utf-8")
    assert captured["proc"].stdin.closed is True


@pytest.mark.asyncio
async def test_stream_claude_turn_denies_bash_and_web_tools_by_default(monkeypatch, tmp_path: Path):
    """A pipeline-stage turn must never shell out, reach the live web, or
    write outside runs/**/rgs-briefs/** -- see CLAUDE.md's permission-scoping
    requirement. --allowedTools alone doesn't enforce this (it's an additive
    allow-list); --disallowedTools is the subtractive rule that's documented
    (`claude --help`) to actually block a tool regardless of permission mode.
    This test only proves the flag is constructed correctly -- it does not
    prove runtime enforcement, which the real `claude` CLI would have to
    verify (see this task's Step 5 manual smoke check)."""
    from pipeline_app import cli_runner

    monkeypatch.setattr(cli_runner, "resolve_claude_binary", lambda *a, **k: "claude")

    captured: dict = {}

    async def fake_exec(*argv, **kwargs):
        captured["argv"] = list(argv)
        return _FakeProcess([b'{"type": "result", "result": "ok"}\n'])

    monkeypatch.setattr(cli_runner.asyncio, "create_subprocess_exec", fake_exec)

    async for _ in cli_runner.stream_claude_turn("prompt", tmp_path, None):
        pass

    argv = captured["argv"]
    assert "--disallowedTools" in argv
    idx = argv.index("--disallowedTools")
    disallowed = argv[idx + 1].split(",")
    for tool in (
        "Bash", "PowerShell", "WebFetch", "WebSearch", "NotebookEdit",
        "Write(docs/**)", "Write(.claude/**)",
    ):
        assert tool in disallowed, tool


@pytest.mark.asyncio
async def test_stream_claude_turn_passes_strict_mcp_config(monkeypatch, tmp_path: Path):
    """See test_build_claude_argv_always_includes_strict_mcp_config -- this
    proves the flag survives all the way to the argv stream_claude_turn
    actually execs, not just build_claude_argv in isolation."""
    from pipeline_app import cli_runner

    monkeypatch.setattr(cli_runner, "resolve_claude_binary", lambda *a, **k: "claude")

    captured: dict = {}

    async def fake_exec(*argv, **kwargs):
        captured["argv"] = list(argv)
        return _FakeProcess([b'{"type": "result", "result": "ok"}\n'])

    monkeypatch.setattr(cli_runner.asyncio, "create_subprocess_exec", fake_exec)

    async for _ in cli_runner.stream_claude_turn("prompt", tmp_path, None):
        pass

    assert "--strict-mcp-config" in captured["argv"]


def test_child_env_strips_the_apps_vendor_keys(monkeypatch):
    """D-46: stream_claude_turn passed `dict(os.environ)` straight through, so a
    turn -- and any PreToolUse hook it induced -- inherited RESEND_API_KEY,
    YOUTUBE_API_KEY and BRIGHTDATA_API_KEY."""
    from pipeline_app import cli_runner
    for name in ("RESEND_API_KEY", "YOUTUBE_API_KEY", "BRIGHTDATA_API_KEY"):
        monkeypatch.setenv(name, "secret")
    env = cli_runner.child_env()
    assert "RESEND_API_KEY" not in env
    assert "YOUTUBE_API_KEY" not in env
    assert "BRIGHTDATA_API_KEY" not in env


def test_child_env_keeps_the_credentials_the_cli_needs_to_authenticate(monkeypatch):
    """Distinguishability: 'stripped a vendor key' must not become 'stripped the
    key the CLI logs in with'. A blanket *_API_KEY filter would break the app."""
    from pipeline_app import cli_runner
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "secret")
    env = cli_runner.child_env()
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-x"
    assert "BRIGHTDATA_API_KEY" not in env
    assert env["PYTHONIOENCODING"] == "utf-8"


@pytest.mark.asyncio
async def test_stream_claude_turn_launches_with_the_scrubbed_env(monkeypatch, tmp_path: Path):
    """Surfacing/binding: assert the scrub is what the subprocess actually gets,
    not merely that a helper exists."""
    from pipeline_app import cli_runner

    monkeypatch.setattr(cli_runner, "resolve_claude_binary", lambda *a, **k: "claude")
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "secret")

    captured: dict = {}

    async def fake_exec(*argv, **kwargs):
        captured["env"] = kwargs.get("env")
        return _FakeProcess([b'{"type": "result", "result": "ok"}\n'])

    monkeypatch.setattr(cli_runner.asyncio, "create_subprocess_exec", fake_exec)

    async for _ in cli_runner.stream_claude_turn("prompt", tmp_path, None):
        pass

    assert "BRIGHTDATA_API_KEY" not in captured["env"]


def test_injection_shaped_prompt_never_reaches_cmd_shim_command_line(monkeypatch):
    """Even with the Windows `cmd /c` wrapper applied, nothing from the prompt
    appears in the command list, so cmd.exe has nothing to re-parse."""
    from pipeline_app.cli_runner import platform_argv

    monkeypatch.setattr("pipeline_app.cli_runner.os.name", "nt")
    argv = build_claude_argv(
        INJECTION_PROMPT,
        resume_session_id=None,
        allowed_tools="Read,Glob,Grep,Write,Edit",
        settings_path=None,
        which_fn=lambda name: r"C:\npm\claude.CMD",
    )
    wrapped = platform_argv(argv)
    assert wrapped[:2] == ["cmd", "/c"]
    joined = " ".join(wrapped)
    assert "pwned" not in joined
    assert "INJECTED" not in joined
    assert "&" not in joined


@pytest.mark.skipif(os.name != "nt", reason="cmd.exe shim injection path is Windows-only")
@pytest.mark.asyncio
async def test_injection_shaped_prompt_does_not_execute_via_cmd_shim(monkeypatch, tmp_path: Path):
    """End-to-end proof against a real cmd.exe: a stub claude.cmd echoes stdin
    to a marker file. If the prompt were still on the command line, cmd.exe
    would honour the embedded `& echo pwned>INJECTED.txt &` and create that
    file in the working directory."""
    from pipeline_app import cli_runner

    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    shim = shim_dir / "claude.cmd"
    shim.write_text(
        '@echo off\r\nfindstr "^" > "%~dp0stdin-capture.txt"\r\n', encoding="utf-8"
    )
    monkeypatch.setattr(cli_runner, "resolve_claude_binary", lambda *a, **k: str(shim))

    cwd = tmp_path / "cwd"
    cwd.mkdir()

    async for _ in cli_runner.stream_claude_turn(INJECTION_PROMPT, cwd, None):
        pass

    assert not (cwd / "INJECTED.txt").exists()
    assert not (shim_dir / "INJECTED.txt").exists()
    assert not (tmp_path / "INJECTED.txt").exists()
    captured = (shim_dir / "stdin-capture.txt").read_text(encoding="utf-8")
    assert "benign" in captured


CHILD_SLEEP_SECONDS = 2.0


def _write_cmd_shim_that_spawns_a_slow_child(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build a `.cmd` shim shaped like the npm `claude` shim: a batch file whose
    real work happens in a *separate* child process (here, python). Returns the
    shim plus the markers that child writes when it starts and if it completes."""
    started = tmp_path / "child-started.txt"
    completed = tmp_path / "child-completed.txt"
    child_py = tmp_path / "slow_child.py"
    child_py.write_text(
        "import pathlib, sys, time\n"
        "pathlib.Path(sys.argv[1]).write_text('started')\n"
        f"time.sleep({CHILD_SLEEP_SECONDS})\n"
        "pathlib.Path(sys.argv[2]).write_text('completed')\n",
        encoding="utf-8",
    )
    shim = tmp_path / "slow.cmd"
    shim.write_text(
        "@echo off\r\n"
        f'"{sys.executable}" "{child_py}" "{started}" "{completed}"\r\n',
        encoding="utf-8",
    )
    return shim, started, completed


async def _await_marker(marker: Path, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if marker.exists():
            return True
        await asyncio.sleep(0.05)
    return False


@pytest.mark.skipif(os.name != "nt", reason="cmd.exe shim process-tree kill is Windows-only")
@pytest.mark.asyncio
async def test_kill_process_tree_kills_the_child_behind_the_cmd_shim(tmp_path: Path):
    """On Windows `claude` runs through `cmd /c` (see platform_argv), so the
    process object we hold is cmd.exe and the real work is a descendant.
    process.kill() would terminate only cmd.exe and leave the descendant running
    to completion; kill_process_tree must take the whole tree down."""
    from pipeline_app.cli_runner import kill_process_tree

    shim, started, completed = _write_cmd_shim_that_spawns_a_slow_child(tmp_path)
    process = await asyncio.create_subprocess_exec(
        "cmd", "/c", str(shim),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        # Only meaningful if the descendant genuinely got running first —
        # otherwise killing cmd.exe alone would trivially prevent the marker.
        assert await _await_marker(started, timeout=10.0), "slow child never started"

        kill_started = time.monotonic()
        kill_process_tree(process)
        await process.wait()
        elapsed = time.monotonic() - kill_started

        # Returning fast proves we did not simply wait out the descendant.
        assert elapsed < CHILD_SLEEP_SECONDS / 2
        # Wait past when the descendant would have finished naturally.
        await asyncio.sleep(CHILD_SLEEP_SECONDS + 1.0)
        assert not completed.exists(), "descendant survived the kill and ran to completion"
    finally:
        if process.returncode is None:
            kill_process_tree(process)
            await process.wait()


@pytest.mark.skipif(os.name != "nt", reason="taskkill is Windows-only")
def test_kill_process_tree_tolerates_an_already_exited_pid():
    """Race: the process can exit between the returncode check and the kill.
    taskkill then returns nonzero, which must not raise."""
    from pipeline_app.cli_runner import kill_process_tree

    class _GoneProcess:
        pid = 999999  # not a live PID

        def kill(self) -> None:  # pragma: no cover - must not be reached on nt
            raise AssertionError("should have gone through taskkill")

    kill_process_tree(_GoneProcess())


def test_kill_process_tree_uses_plain_kill_off_windows(monkeypatch):
    from pipeline_app import cli_runner

    monkeypatch.setattr("pipeline_app.cli_runner.os.name", "posix")

    class _Proc:
        pid = 4242
        killed = False

        def kill(self) -> None:
            self.killed = True

    proc = _Proc()
    cli_runner.kill_process_tree(proc)
    assert proc.killed is True


@pytest.mark.parametrize("path,allowed", [
    ("runs/abc-1/02-scripting/raw_output.md", True),
    ("rgs-briefs/2026-08-08-a.md", True),
    ("scripts/lint_prompt_sheet.py", False),      # D-45: gates.py exec_module's this in-process
    ("scripts/lint_script_language.py", False),
    (".claude/hooks/protect_briefs.py", False),   # D-46: runs as an unrestricted subprocess
    (".claude/settings.json", False),
    (".claude/skills/shorts-assembly/SKILL.md", False),
    ("docs/style-library.md", False),
    ("output/brand-intel/x.json", False),
    ("pipeline.yaml", False),
    ("pipeline-app/pipeline_app/cli_runner.py", False),   # its own runner
    ("../FamilyBrain/anything.md", False),
    ("C:/Windows/System32/x.dll", False),
])
def test_pipeline_turn_write_scope(path, allowed):
    """Effect, not echo. F-11's predecessor deserialized the JSON literal the
    function hard-codes and asserted the four strings survived -- so it could
    never have caught that `permissions.allow` grants rather than restricts."""
    from pipeline_app import cli_runner
    assert cli_runner.permits_write(path) is allowed


def test_the_shipped_flags_are_derived_from_the_policy_permits_write_evaluates():
    """Binds the behavioral test above to what actually ships: a future widening
    of the flags without widening the policy would break here."""
    from pipeline_app import cli_runner

    argv = cli_runner.build_claude_argv(
        "p", None, cli_runner.PIPELINE_ALLOWED_TOOLS, cli_runner.pipeline_permissions_settings(),
        cli_runner.PIPELINE_DISALLOWED_TOOLS, which_fn=lambda _n: "/usr/bin/claude")
    allowed = argv[argv.index("--allowedTools") + 1].split(",")
    assert "Write" not in allowed and "Edit" not in allowed      # never unpatterned
    assert {t for t in allowed if t.startswith(("Write(", "Edit("))} == {
        f"{tool}({pattern})"
        for pattern in cli_runner.WRITE_ALLOW_PATTERNS for tool in ("Write", "Edit")
    }
    denied = argv[argv.index("--disallowedTools") + 1]
    for pattern in cli_runner.WRITE_DENY_PATTERNS:
        assert f"Write({pattern})" in denied and f"Edit({pattern})" in denied


def test_settings_json_carries_a_deny_block_not_just_an_allow_list():
    """D-43: the only key emitted was `permissions.allow`, which grants."""
    from pipeline_app import cli_runner
    data = json.loads(cli_runner.pipeline_permissions_settings())
    assert data["permissions"]["deny"], "an allow-only settings blob restricts nothing"
    assert "Write(scripts/**)" in data["permissions"]["deny"]
    assert "Write(.claude/**)" in data["permissions"]["deny"]


def test_scoped_permissions_settings_is_gone():
    """The old name asserted a control that did not exist; a reviewer grepping
    for it must find nothing rather than a renamed shim."""
    from pipeline_app import cli_runner
    assert not hasattr(cli_runner, "scoped_permissions_settings")


def test_default_allowed_tools_includes_task():
    """Gate E (shorts-scripting) and Gate B (midjourney-prompting) both dispatch
    a fresh reviewing agent via Task. cli_runner's comments say Task is
    deliberately undenied, but the allowed_tools default never listed it, and
    headless -p has no one to approve an unlisted tool -- so Gate B has very
    likely been failing silently."""
    import inspect

    from pipeline_app import cli_runner

    signature = inspect.signature(cli_runner.stream_claude_turn)
    default = signature.parameters["allowed_tools"].default
    assert "Task" in default.split(",")
