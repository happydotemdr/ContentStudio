import asyncio
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
    from pipeline_app.cli_runner import _platform_argv

    monkeypatch.setattr("pipeline_app.cli_runner.os.name", "nt")
    argv = _platform_argv([r"C:\Users\me\AppData\Roaming\npm\claude.CMD", "-p", "hi"])
    assert argv == ["cmd", "/c", r"C:\Users\me\AppData\Roaming\npm\claude.CMD", "-p", "hi"]


def test_platform_argv_passes_through_non_windows_or_non_shim(monkeypatch):
    from pipeline_app.cli_runner import _platform_argv

    monkeypatch.setattr("pipeline_app.cli_runner.os.name", "posix")
    argv = _platform_argv(["/usr/local/bin/claude", "-p", "hi"])
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


def test_injection_shaped_prompt_never_reaches_cmd_shim_command_line(monkeypatch):
    """Even with the Windows `cmd /c` wrapper applied, nothing from the prompt
    appears in the command list, so cmd.exe has nothing to re-parse."""
    from pipeline_app.cli_runner import _platform_argv

    monkeypatch.setattr("pipeline_app.cli_runner.os.name", "nt")
    argv = build_claude_argv(
        INJECTION_PROMPT,
        resume_session_id=None,
        allowed_tools="Read,Glob,Grep,Write,Edit",
        settings_path=None,
        which_fn=lambda name: r"C:\npm\claude.CMD",
    )
    wrapped = _platform_argv(argv)
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
    """On Windows `claude` runs through `cmd /c` (see _platform_argv), so the
    process object we hold is cmd.exe and the real work is a descendant.
    process.kill() would terminate only cmd.exe and leave the descendant running
    to completion; _kill_process_tree must take the whole tree down."""
    from pipeline_app.cli_runner import _kill_process_tree

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
        _kill_process_tree(process)
        await process.wait()
        elapsed = time.monotonic() - kill_started

        # Returning fast proves we did not simply wait out the descendant.
        assert elapsed < CHILD_SLEEP_SECONDS / 2
        # Wait past when the descendant would have finished naturally.
        await asyncio.sleep(CHILD_SLEEP_SECONDS + 1.0)
        assert not completed.exists(), "descendant survived the kill and ran to completion"
    finally:
        if process.returncode is None:
            _kill_process_tree(process)
            await process.wait()


@pytest.mark.skipif(os.name != "nt", reason="taskkill is Windows-only")
def test_kill_process_tree_tolerates_an_already_exited_pid():
    """Race: the process can exit between the returncode check and the kill.
    taskkill then returns nonzero, which must not raise."""
    from pipeline_app.cli_runner import _kill_process_tree

    class _GoneProcess:
        pid = 999999  # not a live PID

        def kill(self) -> None:  # pragma: no cover - must not be reached on nt
            raise AssertionError("should have gone through taskkill")

    _kill_process_tree(_GoneProcess())


def test_kill_process_tree_uses_plain_kill_off_windows(monkeypatch):
    from pipeline_app import cli_runner

    monkeypatch.setattr("pipeline_app.cli_runner.os.name", "posix")

    class _Proc:
        pid = 4242
        killed = False

        def kill(self) -> None:
            self.killed = True

    proc = _Proc()
    cli_runner._kill_process_tree(proc)
    assert proc.killed is True


def test_scoped_permissions_settings_scopes_write_edit_to_runs_and_rgs_briefs():
    from pipeline_app.cli_runner import scoped_permissions_settings
    import json as _json

    data = _json.loads(scoped_permissions_settings())
    allow = data["permissions"]["allow"]
    assert "Write(runs/**)" in allow
    assert "Edit(runs/**)" in allow
    assert "Write(rgs-briefs/**)" in allow
    assert "Edit(rgs-briefs/**)" in allow
