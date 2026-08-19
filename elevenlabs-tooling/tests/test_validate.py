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


def test_e3_rejects_non_dict_composition_plan():
    findings = validate({"composition_plan": "oops", "model_id": "music_v1"}, MUSIC_URL)
    assert _checks(findings, "E3")


def _valid_tts_payload():
    return {
        "text": "Hello there.",
        "model_id": "eleven_flash_v2_5",
        "voice_settings": {"speed": 1.0, "similarity_boost": 0.75},
    }


def _valid_music_prompt_payload():
    return {"prompt": "a calm ambient bed", "model_id": "music_v1"}


def _valid_music_plan_payload():
    return {
        "composition_plan": {"chunks": [{"text": "intro", "duration_ms": 8000}]},
        "model_id": "music_v2",
    }


def test_e4_rejects_missing_model_id():
    payload = _valid_tts_payload()
    del payload["model_id"]
    assert _checks(validate(payload, TTS_URL), "E4")


def test_e4_rejects_empty_model_id():
    payload = _valid_tts_payload()
    payload["model_id"] = ""
    assert _checks(validate(payload, TTS_URL), "E4")


def test_e4_passes_when_model_id_set():
    assert not _checks(validate(_valid_tts_payload(), TTS_URL), "E4")


def test_e5_rejects_speed_below_range():
    payload = _valid_tts_payload()
    payload["voice_settings"]["speed"] = 0.5
    assert _checks(validate(payload, TTS_URL), "E5")


def test_e5_rejects_speed_above_range():
    payload = _valid_tts_payload()
    payload["voice_settings"]["speed"] = 1.5
    assert _checks(validate(payload, TTS_URL), "E5")


def test_e5_rejects_non_numeric_speed():
    payload = _valid_tts_payload()
    payload["voice_settings"]["speed"] = "fast"
    assert _checks(validate(payload, TTS_URL), "E5")


def test_e5_passes_speed_in_range():
    assert not _checks(validate(_valid_tts_payload(), TTS_URL), "E5")


def test_e6_rejects_zero_retention_with_stitching():
    payload = _valid_tts_payload()
    payload["previous_request_ids"] = ["abc123"]
    url = TTS_URL + "&enable_logging=false"
    assert _checks(validate(payload, url), "E6")


def test_e6_passes_zero_retention_without_stitching():
    url = TTS_URL + "&enable_logging=false"
    assert not _checks(validate(_valid_tts_payload(), url), "E6")


def test_e6_passes_stitching_with_logging_enabled():
    payload = _valid_tts_payload()
    payload["previous_request_ids"] = ["abc123"]
    url = TTS_URL + "&enable_logging=true"
    assert not _checks(validate(payload, url), "E6")


def test_e7_requires_use_pvc_as_ivc_for_pinned_voice_on_v3():
    url = "https://api.elevenlabs.io/v1/text-to-speech/eDwT8Vhp2yxJzAMmuuPA?output_format=mp3_44100_192"
    payload = {"text": "hi", "model_id": "eleven_v3"}
    assert _checks(validate(payload, url), "E7")


def test_e7_passes_when_use_pvc_as_ivc_present():
    url = "https://api.elevenlabs.io/v1/text-to-speech/eDwT8Vhp2yxJzAMmuuPA?output_format=mp3_44100_192"
    payload = {"text": "hi", "model_id": "eleven_v3", "use_pvc_as_ivc": False}
    assert not _checks(validate(payload, url), "E7")


def test_e7_rejects_non_boolean_use_pvc_as_ivc():
    url = "https://api.elevenlabs.io/v1/text-to-speech/eDwT8Vhp2yxJzAMmuuPA?output_format=mp3_44100_192"
    payload = {"text": "hi", "model_id": "eleven_v3", "use_pvc_as_ivc": "true"}
    assert _checks(validate(payload, url), "E7")


def test_e7_does_not_fire_for_other_voices():
    url = "https://api.elevenlabs.io/v1/text-to-speech/someOtherVoice?output_format=mp3_44100_192"
    payload = {"text": "hi", "model_id": "eleven_v3"}
    assert not _checks(validate(payload, url), "E7")


def test_e7_does_not_fire_off_v3_models():
    url = "https://api.elevenlabs.io/v1/text-to-speech/eDwT8Vhp2yxJzAMmuuPA?output_format=mp3_44100_192"
    payload = {"text": "hi", "model_id": "eleven_multilingual_v2"}
    assert not _checks(validate(payload, url), "E7")


def test_e7_finds_voice_id_even_with_a_trailing_path_segment():
    # /v1/text-to-speech/{voice_id}/with-timestamps is a real, in-scope
    # variant -- the voice_id is NOT the last path segment here.
    url = (
        "https://api.elevenlabs.io/v1/text-to-speech/eDwT8Vhp2yxJzAMmuuPA/with-timestamps"
        "?output_format=mp3_44100_192"
    )
    payload = {"text": "hi", "model_id": "eleven_v3"}
    assert _checks(validate(payload, url), "E7")


def test_e8_rejects_too_many_dictionary_locators():
    payload = _valid_tts_payload()
    payload["pronunciation_dictionary_locators"] = [{"pronunciation_dictionary_id": str(i)} for i in range(4)]
    assert _checks(validate(payload, TTS_URL), "E8")


def test_e8_rejects_non_list_dictionary_locators():
    payload = _valid_tts_payload()
    payload["pronunciation_dictionary_locators"] = "not-a-list"
    assert _checks(validate(payload, TTS_URL), "E8")


def test_e8_passes_three_dictionary_locators():
    payload = _valid_tts_payload()
    payload["pronunciation_dictionary_locators"] = [{"pronunciation_dictionary_id": str(i)} for i in range(3)]
    assert not _checks(validate(payload, TTS_URL), "E8")


def test_e9_rejects_too_many_previous_request_ids():
    payload = _valid_tts_payload()
    payload["previous_request_ids"] = ["a", "b", "c", "d"]
    assert _checks(validate(payload, TTS_URL), "E9")


def test_e9_rejects_too_many_next_request_ids():
    payload = _valid_tts_payload()
    payload["next_request_ids"] = ["a", "b", "c", "d"]
    assert _checks(validate(payload, TTS_URL), "E9")


def test_e9_rejects_non_list_request_ids():
    payload = _valid_tts_payload()
    payload["previous_request_ids"] = "not-a-list"
    assert _checks(validate(payload, TTS_URL), "E9")


def test_e9_passes_three_request_ids():
    payload = _valid_tts_payload()
    payload["previous_request_ids"] = ["a", "b", "c"]
    assert not _checks(validate(payload, TTS_URL), "E9")


def test_e10_rejects_seed_out_of_range():
    payload = _valid_tts_payload()
    payload["seed"] = -1
    assert _checks(validate(payload, TTS_URL), "E10")


def test_e10_rejects_non_integer_seed():
    payload = _valid_tts_payload()
    payload["seed"] = 4.5
    assert _checks(validate(payload, TTS_URL), "E10")


def test_e10_passes_valid_seed():
    payload = _valid_tts_payload()
    payload["seed"] = 42
    assert not _checks(validate(payload, TTS_URL), "E10")


def test_e11_rejects_seed_with_prompt():
    payload = _valid_music_prompt_payload()
    payload["seed"] = 42
    assert _checks(validate(payload, MUSIC_URL), "E11")


def test_e11_passes_seed_with_composition_plan():
    payload = _valid_music_plan_payload()
    payload["seed"] = 42
    assert not _checks(validate(payload, MUSIC_URL), "E11")


def test_e12_rejects_force_instrumental_with_composition_plan():
    payload = _valid_music_plan_payload()
    payload["force_instrumental"] = True
    assert _checks(validate(payload, MUSIC_URL), "E12")


def test_e12_passes_force_instrumental_with_prompt():
    payload = _valid_music_prompt_payload()
    payload["force_instrumental"] = True
    assert not _checks(validate(payload, MUSIC_URL), "E12")


def test_e13_rejects_music_length_ms_with_composition_plan():
    payload = _valid_music_plan_payload()
    payload["music_length_ms"] = 30000
    assert _checks(validate(payload, MUSIC_URL), "E13")


def test_e13_passes_music_length_ms_with_prompt():
    payload = _valid_music_prompt_payload()
    payload["music_length_ms"] = 30000
    assert not _checks(validate(payload, MUSIC_URL), "E13")


def test_e14_rejects_chunk_plan_without_music_v2():
    payload = {
        "composition_plan": {"chunks": [{"text": "intro", "duration_ms": 8000}]},
        "model_id": "music_v1",
    }
    assert _checks(validate(payload, MUSIC_URL), "E14")


def test_e14_passes_chunk_plan_with_music_v2():
    assert not _checks(validate(_valid_music_plan_payload(), MUSIC_URL), "E14")


def test_e14_ignores_plan_without_chunks():
    payload = {"composition_plan": {}, "model_id": "music_v1"}
    assert not _checks(validate(payload, MUSIC_URL), "E14")


def test_e14_ignores_null_composition_plan():
    payload = {"prompt": "a calm bed", "composition_plan": None, "model_id": "music_v1"}
    assert not _checks(validate(payload, MUSIC_URL), "E14")


def test_w1_warns_when_output_format_missing():
    url = "https://api.elevenlabs.io/v1/text-to-speech/x"
    findings = validate(_valid_tts_payload(), url)
    assert _checks(findings, "W1")
    assert not any(is_blocking(f) for f in _checks(findings, "W1"))


def test_w1_silent_when_output_format_present():
    assert not _checks(validate(_valid_tts_payload(), TTS_URL), "W1")


def test_w2_warns_above_similarity_threshold():
    payload = _valid_tts_payload()
    payload["voice_settings"]["similarity_boost"] = 0.95
    findings = validate(payload, TTS_URL)
    assert _checks(findings, "W2")
    assert not any(is_blocking(f) for f in _checks(findings, "W2"))


def test_w2_silent_at_or_below_threshold():
    payload = _valid_tts_payload()
    payload["voice_settings"]["similarity_boost"] = 0.9
    assert not _checks(validate(payload, TTS_URL), "W2")


def test_w2_warns_on_non_numeric_similarity_boost():
    payload = _valid_tts_payload()
    payload["voice_settings"]["similarity_boost"] = "high"
    findings = validate(payload, TTS_URL)
    assert _checks(findings, "W2")
    assert not any(is_blocking(f) for f in _checks(findings, "W2"))


def test_fully_valid_tts_payload_has_no_blocking_findings():
    findings = validate(_valid_tts_payload(), TTS_URL)
    assert not [f for f in findings if is_blocking(f)]


def test_fully_valid_music_prompt_payload_has_no_blocking_findings():
    findings = validate(_valid_music_prompt_payload(), MUSIC_URL)
    assert not [f for f in findings if is_blocking(f)]


def test_fully_valid_music_plan_payload_has_no_blocking_findings():
    findings = validate(_valid_music_plan_payload(), MUSIC_URL)
    assert not [f for f in findings if is_blocking(f)]


def test_e5_rejects_non_dict_voice_settings_string():
    payload = _valid_tts_payload()
    payload["voice_settings"] = "loud"
    assert _checks(validate(payload, TTS_URL), "E5")


def test_e5_rejects_non_dict_voice_settings_list():
    payload = _valid_tts_payload()
    payload["voice_settings"] = [1.0, 0.75]
    assert _checks(validate(payload, TTS_URL), "E5")


def test_e5_rejects_non_dict_voice_settings_int():
    payload = _valid_tts_payload()
    payload["voice_settings"] = 42
    assert _checks(validate(payload, TTS_URL), "E5")


def test_w2_rejects_non_dict_voice_settings_string():
    payload = _valid_tts_payload()
    payload["voice_settings"] = "loud"
    findings = validate(payload, TTS_URL)
    w2_findings = _checks(findings, "W2")
    assert w2_findings
    assert not any(is_blocking(f) for f in w2_findings)


def test_w2_rejects_non_dict_voice_settings_list():
    payload = _valid_tts_payload()
    payload["voice_settings"] = [1.0, 0.75]
    findings = validate(payload, TTS_URL)
    w2_findings = _checks(findings, "W2")
    assert w2_findings
    assert not any(is_blocking(f) for f in w2_findings)


def test_w2_rejects_non_dict_voice_settings_int():
    payload = _valid_tts_payload()
    payload["voice_settings"] = 42
    findings = validate(payload, TTS_URL)
    w2_findings = _checks(findings, "W2")
    assert w2_findings
    assert not any(is_blocking(f) for f in w2_findings)
