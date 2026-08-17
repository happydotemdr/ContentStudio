# coach-prep-app/tests/test_generate.py
from __future__ import annotations

import json

from coach_prep_app import generate

SAMPLE_BUNDLE = {
    "client_display_name": "Sean",
    "last_meeting_email": {"source_label": "last-meeting-email", "text": "Do the 5-minute exercise."},
    "last_meeting_note": {"source_label": "last-meeting-note", "text": "Discussed morality as a strength."},
    "program_sources": [
        {"source_label": "program-structure-v3", "text": "12-week arc, 4 pillars."},
        {"source_label": "judge-module", "text": "The Judge saboteur worksheet."},
    ],
}


def test_build_prompt_includes_every_source_label_and_body():
    prompt = generate.build_prompt(SAMPLE_BUNDLE)
    assert "last-meeting-email" in prompt
    assert "Do the 5-minute exercise." in prompt
    assert "program-structure-v3" in prompt
    assert "12-week arc, 4 pillars." in prompt
    assert "judge-module" in prompt


def test_parse_envelope_extracts_result_text():
    stdout = json.dumps({"is_error": False, "result": "## Activities\n- x [last-meeting-email]"})
    assert generate.parse_envelope(stdout) == "## Activities\n- x [last-meeting-email]"


def test_parse_envelope_returns_none_on_error_envelope():
    stdout = json.dumps({"is_error": True, "result": None})
    assert generate.parse_envelope(stdout) is None


def test_parse_envelope_returns_none_on_malformed_json():
    assert generate.parse_envelope("not json") is None


def test_parse_envelope_returns_none_on_empty_result():
    stdout = json.dumps({"is_error": False, "result": "   "})
    assert generate.parse_envelope(stdout) is None
