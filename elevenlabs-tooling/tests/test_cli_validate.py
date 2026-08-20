import json

import elevenlabs_tooling.log as log_module
from elevenlabs_tooling.cli import EXIT_FINDINGS, EXIT_PASS, EXIT_UNPARSEABLE, EXIT_UNREADABLE_INPUT, main

TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/someVoiceId?output_format=mp3_44100_192"


def _write_payload(tmp_path, data):
    path = tmp_path / "payload.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _logged_events():
    files = list(log_module.LOG_DIR.glob("tooling-*.log"))
    assert files, "expected at least one log file to be written"
    return [
        json.loads(line)["event"]
        for line in files[0].read_text(encoding="utf-8").strip().splitlines()
    ]


def test_validate_passes_clean_payload(tmp_path):
    payload_path = _write_payload(tmp_path, {"text": "hi", "model_id": "eleven_flash_v2_5"})
    code = main(["validate", "--payload", str(payload_path), "--url", TTS_URL])
    assert code == EXIT_PASS


def test_validate_passed_writes_log_entry(tmp_path):
    payload_path = _write_payload(tmp_path, {"text": "hi", "model_id": "eleven_flash_v2_5"})
    main(["validate", "--payload", str(payload_path), "--url", TTS_URL])
    assert "validate.passed" in _logged_events()


def test_validate_reports_blocking_findings_with_the_check_code_and_message(tmp_path, capsys):
    payload_path = _write_payload(tmp_path, {"text": "hi"})  # missing model_id -> E4
    code = main(["validate", "--payload", str(payload_path), "--url", TTS_URL])
    assert code == EXIT_FINDINGS
    captured = capsys.readouterr()
    assert "E4: model_id must be present and non-empty" in captured.err


def test_validate_rejected_writes_log_entry(tmp_path):
    payload_path = _write_payload(tmp_path, {"text": "hi"})  # missing model_id -> E4
    main(["validate", "--payload", str(payload_path), "--url", TTS_URL])
    assert "validate.rejected" in _logged_events()


def test_validate_missing_payload_file(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    code = main(["validate", "--payload", str(missing), "--url", TTS_URL])
    assert code == EXIT_UNREADABLE_INPUT


def test_validate_unparseable_json(tmp_path):
    payload_path = tmp_path / "broken.json"
    payload_path.write_text("{not valid json", encoding="utf-8")
    code = main(["validate", "--payload", str(payload_path), "--url", TTS_URL])
    assert code == EXIT_UNPARSEABLE


def test_validate_json_that_is_not_an_object(tmp_path):
    payload_path = tmp_path / "list.json"
    payload_path.write_text("[1, 2, 3]", encoding="utf-8")
    code = main(["validate", "--payload", str(payload_path), "--url", TTS_URL])
    assert code == EXIT_UNPARSEABLE


def test_validate_invalid_utf8_payload_is_unparseable_not_a_crash(tmp_path):
    payload_path = tmp_path / "badbytes.json"
    payload_path.write_bytes(b"\xff\xfe\x00\x01not utf-8")
    code = main(["validate", "--payload", str(payload_path), "--url", TTS_URL])
    assert code == EXIT_UNPARSEABLE


def test_validate_unreadable_payload_file_is_unreadable_input_not_a_crash(tmp_path, monkeypatch):
    payload_path = _write_payload(tmp_path, {"text": "hi", "model_id": "eleven_flash_v2_5"})

    def _boom(self, *args, **kwargs):
        raise OSError("simulated permission error")

    monkeypatch.setattr("pathlib.Path.read_bytes", _boom)
    code = main(["validate", "--payload", str(payload_path), "--url", TTS_URL])
    assert code == EXIT_UNREADABLE_INPUT


def test_validate_prints_warnings_without_blocking(tmp_path, capsys):
    payload_path = _write_payload(tmp_path, {"text": "hi", "model_id": "eleven_flash_v2_5"})
    url_without_output_format = "https://api.elevenlabs.io/v1/text-to-speech/x"
    code = main(["validate", "--payload", str(payload_path), "--url", url_without_output_format])
    assert code == EXIT_PASS
    captured = capsys.readouterr()
    assert "W1" in captured.err
