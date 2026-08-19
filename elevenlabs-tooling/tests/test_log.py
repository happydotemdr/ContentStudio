import json

import elevenlabs_tooling.log as log_module
from elevenlabs_tooling.log import log


def test_log_writes_json_line_to_stderr(capsys):
    log("send.attempt", url="https://api.elevenlabs.io/v1/music", foo="bar")
    captured = capsys.readouterr()
    line = json.loads(captured.err.strip())
    assert line["event"] == "send.attempt"
    assert line["level"] == "info"
    assert line["url"] == "https://api.elevenlabs.io/v1/music"
    assert line["foo"] == "bar"
    assert "ts" in line


def test_log_appends_to_dated_file():
    log("send.success", output_path="out.mp3")
    files = list(log_module.LOG_DIR.glob("tooling-*.log"))
    assert len(files) == 1
    contents = files[0].read_text(encoding="utf-8")
    line = json.loads(contents.strip())
    assert line["event"] == "send.success"
    assert line["output_path"] == "out.mp3"


def test_log_appends_multiple_calls_as_separate_lines():
    log("validate.passed")
    log("validate.rejected", level="warning")
    files = list(log_module.LOG_DIR.glob("tooling-*.log"))
    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "validate.passed"
    assert json.loads(lines[1])["event"] == "validate.rejected"
    assert json.loads(lines[1])["level"] == "warning"


def test_log_never_raises_when_log_dir_is_unwritable(monkeypatch):
    def _boom(*args, **kwargs):
        raise OSError("simulated permission error")

    monkeypatch.setattr(log_module.Path, "mkdir", _boom)
    # Must not raise.
    log("send.failed", level="error", error="disk full")


def test_log_never_raises_when_repr_itself_raises(capsys):
    class ExplodesOnRepr:
        def __repr__(self):
            raise RuntimeError("boom")

    # json.dumps(..., default=repr) calls repr() on this and that call
    # raises -- log() must still not raise, and must fall back to the
    # "<unserializable>" record.
    log("send.attempt", weird=ExplodesOnRepr())

    captured = capsys.readouterr()
    line = json.loads(captured.err.strip())
    assert line["fields"] == "<unserializable>"
    assert line["event"] == "send.attempt"
