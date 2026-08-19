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


def test_log_rekeys_colliding_ts_field(capsys):
    """A caller's `ts` field is re-keyed to `field_ts` to preserve the reserved timestamp.

    Only `ts` can collide via **fields since `level` and `event` are named
    parameters and will raise TypeError if passed twice. This test ensures
    that if a caller somehow passes ts= in **fields, it doesn't corrupt the
    computed timestamp.
    """
    log("send.attempt", ts="caller-supplied-value", url="http://example.com")
    captured = capsys.readouterr()
    line = json.loads(captured.err.strip())
    # The reserved `ts` field must be present and match the correct timestamp format
    assert "ts" in line
    assert len(line["ts"]) > 0  # ISO format timestamp
    # The caller's `ts` value must be preserved under `field_ts`
    assert line["field_ts"] == "caller-supplied-value"
    assert line["event"] == "send.attempt"
    assert line["url"] == "http://example.com"


def test_log_does_not_corrupt_ts_with_many_fields(capsys):
    """Passing many fields with one attempting to collide with ts preserves both."""
    log(
        "send.attempt",
        ts="fake-ts",
        url="http://example.com",
        retry_count=3,
        duration_ms=1500,
    )
    captured = capsys.readouterr()
    line = json.loads(captured.err.strip())
    # Reserved `ts` must exist and be a proper ISO timestamp
    assert "ts" in line
    assert "T" in line["ts"]  # ISO format marker
    # All other fields present including the re-keyed ts
    assert line["field_ts"] == "fake-ts"
    assert line["url"] == "http://example.com"
    assert line["retry_count"] == 3
    assert line["duration_ms"] == 1500
