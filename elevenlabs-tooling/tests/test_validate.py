from elevenlabs_tooling.validate import Finding, is_blocking, validate

TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/someVoiceId123?output_format=mp3_44100_192"
MUSIC_URL = "https://api.elevenlabs.io/v1/music?output_format=mp3_44100_192"


def _checks(findings, code):
    return [f for f in findings if f.check == code]


def test_is_blocking_distinguishes_e_and_w_codes():
    assert is_blocking(Finding("E1", "x")) is True
    assert is_blocking(Finding("W1", "x")) is False


def test_e1_rejects_wrong_host():
    findings = validate({"text": "hi", "model_id": "eleven_flash_v2_5"},
                         "https://evil.example.com/v1/text-to-speech/x")
    assert _checks(findings, "E1")


def test_e1_rejects_http_scheme():
    findings = validate(
        {"text": "hi", "model_id": "eleven_flash_v2_5"},
        "http://api.elevenlabs.io/v1/text-to-speech/x",
    )
    assert _checks(findings, "E1")


def test_e1_passes_correct_host_and_scheme():
    findings = validate({"text": "hi", "model_id": "eleven_flash_v2_5"}, TTS_URL)
    assert not _checks(findings, "E1")


def test_e2_rejects_stream_endpoint():
    findings = validate(
        {"text": "hi", "model_id": "eleven_flash_v2_5"},
        "https://api.elevenlabs.io/v1/text-to-speech/x/stream",
    )
    assert _checks(findings, "E2")


def test_e2_rejects_music_detailed_endpoint():
    findings = validate(
        {"prompt": "a calm ambient bed", "model_id": "music_v1"},
        "https://api.elevenlabs.io/v1/music/detailed",
    )
    assert _checks(findings, "E2")


def test_e2_passes_compose_endpoint():
    findings = validate({"prompt": "a calm ambient bed", "model_id": "music_v1"}, MUSIC_URL)
    assert not _checks(findings, "E2")


def test_e3_rejects_neither_text_nor_music_fields():
    findings = validate({"model_id": "eleven_flash_v2_5"}, TTS_URL)
    assert _checks(findings, "E3")


def test_e3_rejects_both_prompt_and_composition_plan():
    findings = validate(
        {"prompt": "a", "composition_plan": {"chunks": []}, "model_id": "music_v2"},
        MUSIC_URL,
    )
    assert _checks(findings, "E3")


def test_e3_rejects_text_mixed_with_music_field():
    findings = validate(
        {"text": "hi", "prompt": "a", "model_id": "eleven_flash_v2_5"}, TTS_URL
    )
    assert _checks(findings, "E3")


def test_e3_passes_tts_shape():
    findings = validate({"text": "hi", "model_id": "eleven_flash_v2_5"}, TTS_URL)
    assert not _checks(findings, "E3")


def test_e3_passes_music_prompt_shape():
    findings = validate({"prompt": "a calm bed", "model_id": "music_v1"}, MUSIC_URL)
    assert not _checks(findings, "E3")


def test_e3_passes_music_composition_plan_shape():
    findings = validate(
        {"composition_plan": {"chunks": []}, "model_id": "music_v2"}, MUSIC_URL
    )
    assert not _checks(findings, "E3")


def test_e3_treats_null_composition_plan_as_absent():
    payload = {"prompt": "a calm bed", "composition_plan": None, "model_id": "music_v1"}
    assert not _checks(validate(payload, MUSIC_URL), "E3")
