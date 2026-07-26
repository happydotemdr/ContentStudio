import pytest

from pipeline_app.cli_runner import (
    build_claude_argv,
    extract_turn_result,
    parse_stream_json_lines,
    resolve_claude_binary,
)


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
    assert "/shorts-ideation do the thing" in argv
    assert "--resume" not in argv
    assert "--allowedTools" in argv
    idx = argv.index("--allowedTools")
    assert argv[idx + 1] == "Read,Glob,Grep,Write,Edit"


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


def test_scoped_permissions_settings_scopes_write_edit_to_runs_and_rgs_briefs():
    from pipeline_app.cli_runner import scoped_permissions_settings
    import json as _json

    data = _json.loads(scoped_permissions_settings())
    allow = data["permissions"]["allow"]
    assert "Write(runs/**)" in allow
    assert "Edit(runs/**)" in allow
    assert "Write(rgs-briefs/**)" in allow
    assert "Edit(rgs-briefs/**)" in allow
