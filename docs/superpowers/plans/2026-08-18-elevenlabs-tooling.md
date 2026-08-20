# elevenlabs-tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `elevenlabs-tooling/`, a standalone Python package that validates and sends an ElevenLabs API payload (TTS or music), matching the design in `docs/superpowers/specs/2026-08-18-elevenlabs-tooling-design.md` exactly.

**Architecture:** A `validate.py` module runs a fixed checklist (`Finding(check, message)`, "E#" blocking / "W#" warning) against a payload dict and a URL, with zero network access and no assumption about field types beyond what it checks. A `client.py` module does the one HTTP POST, catching `requests.exceptions.RequestException` and returning a `SendResult` rather than raising, so callers get uniform control flow. A `log.py` module writes structured, dual-sink (stderr + dated file) log lines that never raise. `cli.py` wires these three together behind `python -m elevenlabs_tooling send|validate`, owning the exit-code contract and the order of operations (read → parse → validate → check API key → check output collision → log → send → write/quarantine).

**Tech Stack:** Python 3, `requests` (HTTP), `pytest` (tests, HTTP mocked via `unittest.mock`). No other third-party dependencies.

## Global Constraints

- Package lives at `elevenlabs-tooling/elevenlabs_tooling/` (repo-root sibling to `stitcher/`), imports nothing from `pipeline_app`, reads no skill file at runtime.
- `client.send()` never re-serializes the payload — it POSTs the exact bytes read from `--payload`.
- `log()` never raises, under any circumstance, including a read-only log directory or a field whose `__repr__` itself raises.
- `client.send()` never raises `requests.exceptions.RequestException` to its caller — it catches that specific exception type and returns a `SendResult`.
- Every validation check that reads a payload field guards its type before comparing/measuring it — a malformed payload must produce a `Finding`, never an uncaught `TypeError`.
- Exit codes are fixed and must not be renumbered: `EXIT_PASS=0`, `EXIT_FINDINGS=1`, `EXIT_USAGE=2`, `EXIT_UNREADABLE_INPUT=3`, `EXIT_UNPARSEABLE=4`, `EXIT_SEND_FAILED=5`, `EXIT_NO_API_KEY=6`.
- No test in this package makes a real network call. Every HTTP interaction in the test suite goes through `unittest.mock.patch`, and every test's log output is isolated to a `tmp_path`, never the real `elevenlabs-tooling/logs/` directory.
- Every module uses `from __future__ import annotations` (matches `stitcher`'s style throughout), including `__main__.py`.

---

### Task 1: Package scaffold + `validate.py` — URL and payload-shape checks (E1–E3)

**Files:**
- Create: `elevenlabs-tooling/requirements.txt`
- Create: `elevenlabs-tooling/pytest.ini`
- Create: `elevenlabs-tooling/elevenlabs_tooling/__init__.py`
- Create: `elevenlabs-tooling/elevenlabs_tooling/validate.py`
- Test: `elevenlabs-tooling/tests/test_validate.py`
- Modify: `.gitignore` (repo root)

**Interfaces:**
- Consumes: nothing (first task)
- Produces: `Finding` (frozen dataclass: `check: str`, `message: str`), `is_blocking(finding: Finding) -> bool`, `validate(payload: dict, url: str) -> list[Finding]`, module constants `PINNED_NARRATOR_VOICE_ID = "eDwT8Vhp2yxJzAMmuuPA"`, `ALLOWED_HOST = "api.elevenlabs.io"`

- [ ] **Step 1: Scaffold the package**

Create `elevenlabs-tooling/requirements.txt`:

```
requests>=2.31
pytest>=8.3
```

Create `elevenlabs-tooling/pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = tests
```

Create `elevenlabs-tooling/elevenlabs_tooling/__init__.py` (empty file — marks the package).

Append to the repo root's `.gitignore`:

```
# elevenlabs-tooling's structured request logs (elevenlabs_tooling/log.py):
# one tooling-YYYY-MM-DD.log per day, local diagnostics only.
elevenlabs-tooling/logs/
```

- [ ] **Step 2: Write the failing tests for E1–E3**

Create `elevenlabs-tooling/tests/test_validate.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_validate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'elevenlabs_tooling.validate'` (the module doesn't exist yet).

- [ ] **Step 4: Implement `validate.py` (E1–E3 only for now)**

Create `elevenlabs-tooling/elevenlabs_tooling/validate.py`:

```python
"""Payload/URL validation -- the hard gate before any ElevenLabs API call.

Structure mirrors scripts/lint_prompt_sheet.py (Gate C) in the parent repo: a
flat list of Finding(check, message) accumulated by running every check to
completion, never stopping at the first problem. "E#" findings block a send;
"W#" findings are informational only.

Every check that reads a payload field guards its type before comparing or
measuring it: a malformed payload must produce a Finding, never an uncaught
TypeError from a tool whose entire job is to fail safely on bad input.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

PINNED_NARRATOR_VOICE_ID = "eDwT8Vhp2yxJzAMmuuPA"
ALLOWED_HOST = "api.elevenlabs.io"
ALLOWED_SCHEME = "https"
OUT_OF_SCOPE_PATH_MARKERS = (
    "/stream",
    "/compose_stream",
    "/music/detailed",
    "/compose_detailed",
    "/compose_detailed_stream",
)


@dataclass(frozen=True)
class Finding:
    check: str
    message: str


def is_blocking(finding: Finding) -> bool:
    return finding.check.startswith("E")


def validate(payload: dict, url: str) -> list[Finding]:
    """Run every check; return every finding. Never stops at the first one."""
    findings: list[Finding] = []
    findings.extend(_check_url(url))
    findings.extend(_check_shape(payload))
    return findings


def _check_url(url: str) -> list[Finding]:
    findings: list[Finding] = []
    parts = urlsplit(url)
    if parts.scheme != ALLOWED_SCHEME or parts.hostname != ALLOWED_HOST:
        findings.append(Finding(
            "E1",
            f"URL must be {ALLOWED_SCHEME}://{ALLOWED_HOST}/... , got "
            f"{parts.scheme!r}://{parts.hostname!r}",
        ))
    lowered_path = parts.path.lower()
    for marker in OUT_OF_SCOPE_PATH_MARKERS:
        if marker in lowered_path:
            findings.append(Finding(
                "E2",
                f"URL path {parts.path!r} targets a v1-out-of-scope endpoint "
                f"({marker}) -- streaming and multipart-detailed responses "
                "are not supported by this tool",
            ))
            break
    return findings


def _check_shape(payload: dict) -> list[Finding]:
    has_text = bool(payload.get("text"))
    has_prompt = payload.get("prompt") is not None
    has_plan = payload.get("composition_plan") is not None
    music_field_count = sum([has_prompt, has_plan])

    if has_text and music_field_count == 0:
        return []
    if not has_text and music_field_count == 1:
        return []
    if has_text and music_field_count > 0:
        return [Finding(
            "E3",
            "payload has both a TTS field (text) and a music field "
            "(prompt/composition_plan) -- pick one shape",
        )]
    if music_field_count > 1:
        return [Finding(
            "E3",
            "payload has both prompt and composition_plan -- they are "
            "mutually exclusive",
        )]
    return [Finding(
        "E3",
        "payload is neither TTS-shaped (non-empty text) nor music-shaped "
        "(exactly one of prompt/composition_plan)",
    )]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_validate.py -v`
Expected: PASS (14 tests).

- [ ] **Step 6: Commit**

```bash
git add .gitignore elevenlabs-tooling/requirements.txt elevenlabs-tooling/pytest.ini \
        elevenlabs-tooling/elevenlabs_tooling/__init__.py \
        elevenlabs-tooling/elevenlabs_tooling/validate.py \
        elevenlabs-tooling/tests/test_validate.py
git commit -m "feat(elevenlabs-tooling): scaffold package, validate E1-E3 (URL host/scheme/scope, payload shape)"
```

---

### Task 2: `validate.py` — remaining checks (E4–E14, W1–W2)

**Files:**
- Modify: `elevenlabs-tooling/elevenlabs_tooling/validate.py`
- Test: `elevenlabs-tooling/tests/test_validate.py`

**Interfaces:**
- Consumes: `Finding`, `is_blocking`, `validate`, `PINNED_NARRATOR_VOICE_ID` (Task 1)
- Produces: `validate()` now runs the full E1–E14/W1–W2 checklist (no new public names)

- [ ] **Step 1: Write the failing tests for E4–E14, W1–W2**

Append to `elevenlabs-tooling/tests/test_validate.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_validate.py -v`
Expected: the new tests FAIL (E4–E14/W1–W2 checks don't exist yet); the Task 1 tests still PASS.

- [ ] **Step 3: Implement the remaining checks**

Replace the body of `validate()` in `elevenlabs-tooling/elevenlabs_tooling/validate.py` and add the new check functions:

```python
SPEED_MIN, SPEED_MAX = 0.7, 1.2
SIMILARITY_WARN_ABOVE = 0.9
MAX_DICTIONARY_LOCATORS = 3
MAX_REQUEST_IDS = 3
SEED_MIN, SEED_MAX = 0, 4_294_967_295


def validate(payload: dict, url: str) -> list[Finding]:
    """Run every check; return every finding. Never stops at the first one."""
    findings: list[Finding] = []
    findings.extend(_check_url(url))
    findings.extend(_check_shape(payload))
    findings.extend(_check_model_id(payload))
    findings.extend(_check_speed(payload))
    findings.extend(_check_stitching_conflict(payload, url))
    findings.extend(_check_pvc_v3(payload, url))
    findings.extend(_check_dictionary_locators(payload))
    findings.extend(_check_request_ids(payload))
    findings.extend(_check_seed_range(payload))
    findings.extend(_check_music_conflicts(payload))
    findings.extend(_check_output_format(url))
    findings.extend(_check_similarity_boost(payload))
    return findings


def _check_model_id(payload: dict) -> list[Finding]:
    if not payload.get("model_id"):
        return [Finding("E4", "model_id must be present and non-empty")]
    return []


def _check_speed(payload: dict) -> list[Finding]:
    settings = payload.get("voice_settings") or {}
    speed = settings.get("speed")
    if speed is None:
        return []
    if not isinstance(speed, (int, float)) or isinstance(speed, bool):
        return [Finding("E5", f"voice_settings.speed {speed!r} must be a number")]
    if not (SPEED_MIN <= speed <= SPEED_MAX):
        return [Finding(
            "E5",
            f"voice_settings.speed {speed!r} is outside the valid range "
            f"{SPEED_MIN}-{SPEED_MAX}",
        )]
    return []


def _check_stitching_conflict(payload: dict, url: str) -> list[Finding]:
    query = parse_qs(urlsplit(url).query)
    enable_logging = query.get("enable_logging", ["true"])[0].lower()
    has_stitching = "previous_request_ids" in payload or "next_request_ids" in payload
    if enable_logging == "false" and has_stitching:
        return [Finding(
            "E6",
            "enable_logging=false in the URL disables request stitching, "
            "but the payload sets previous_request_ids/next_request_ids",
        )]
    return []


def _voice_id_from_tts_path(parts) -> str | None:
    """The path segment right after 'text-to-speech', or None.

    Not simply the last segment: /v1/text-to-speech/{voice_id}/with-timestamps
    is a real, in-scope path shape where the voice_id is NOT last.
    """
    segments = [segment for segment in parts.path.split("/") if segment]
    if "text-to-speech" not in segments:
        return None
    index = segments.index("text-to-speech")
    if index + 1 >= len(segments):
        return None
    return segments[index + 1]


def _check_pvc_v3(payload: dict, url: str) -> list[Finding]:
    parts = urlsplit(url)
    voice_id = _voice_id_from_tts_path(parts)
    model_id = str(payload.get("model_id") or "")
    if voice_id != PINNED_NARRATOR_VOICE_ID or "v3" not in model_id:
        return []
    if "use_pvc_as_ivc" not in payload:
        return [Finding(
            "E7",
            "the pinned narrator is a PVC on a v3 model; use_pvc_as_ivc "
            "must be set explicitly (true or false) -- see "
            "channel-voice.md Open action 3",
        )]
    if not isinstance(payload["use_pvc_as_ivc"], bool):
        return [Finding("E7", "use_pvc_as_ivc must be a boolean")]
    return []


def _check_dictionary_locators(payload: dict) -> list[Finding]:
    locators = payload.get("pronunciation_dictionary_locators")
    if locators is None:
        return []
    if not isinstance(locators, list):
        return [Finding("E8", "pronunciation_dictionary_locators must be a list")]
    if len(locators) > MAX_DICTIONARY_LOCATORS:
        return [Finding(
            "E8",
            f"pronunciation_dictionary_locators has {len(locators)} entries, "
            f"the maximum is {MAX_DICTIONARY_LOCATORS}",
        )]
    return []


def _check_request_ids(payload: dict) -> list[Finding]:
    findings: list[Finding] = []
    for field in ("previous_request_ids", "next_request_ids"):
        ids = payload.get(field)
        if ids is None:
            continue
        if not isinstance(ids, list):
            findings.append(Finding("E9", f"{field} must be a list"))
            continue
        if len(ids) > MAX_REQUEST_IDS:
            findings.append(Finding(
                "E9",
                f"{field} has {len(ids)} entries, the maximum is {MAX_REQUEST_IDS}",
            ))
    return findings


def _check_seed_range(payload: dict) -> list[Finding]:
    seed = payload.get("seed")
    if seed is None:
        return []
    if isinstance(seed, bool) or not isinstance(seed, int) or not (SEED_MIN <= seed <= SEED_MAX):
        return [Finding(
            "E10", f"seed {seed!r} must be an integer in {SEED_MIN}-{SEED_MAX}"
        )]
    return []


def _check_music_conflicts(payload: dict) -> list[Finding]:
    findings: list[Finding] = []
    has_prompt = payload.get("prompt") is not None
    plan = payload.get("composition_plan")
    has_plan = plan is not None

    if payload.get("seed") is not None and has_prompt:
        findings.append(Finding(
            "E11", "seed is plan-only and cannot be used together with prompt"
        ))
    if payload.get("force_instrumental") is not None and has_plan:
        findings.append(Finding(
            "E12",
            "force_instrumental is prompt-only and does not apply to composition_plan",
        ))
    if payload.get("music_length_ms") is not None and has_plan:
        findings.append(Finding(
            "E13",
            "music_length_ms is prompt-only; a composition_plan's length "
            "comes from its chunks",
        ))
    if has_plan and isinstance(plan, dict) and plan.get("chunks"):
        if payload.get("model_id") != "music_v2":
            findings.append(Finding(
                "E14",
                "composition_plan.chunks is set but model_id is not "
                "'music_v2' -- chunk plans require music_v2",
            ))
    return findings


def _check_output_format(url: str) -> list[Finding]:
    query = parse_qs(urlsplit(url).query)
    if "output_format" not in query:
        return [Finding(
            "W1",
            "URL has no output_format query param -- a default applies, "
            "but state the value chosen rather than leaving it implicit",
        )]
    return []


def _check_similarity_boost(payload: dict) -> list[Finding]:
    settings = payload.get("voice_settings") or {}
    similarity = settings.get("similarity_boost")
    if similarity is None:
        return []
    if not isinstance(similarity, (int, float)) or isinstance(similarity, bool):
        return [Finding(
            "W2", f"voice_settings.similarity_boost {similarity!r} must be a number"
        )]
    if similarity > SIMILARITY_WARN_ABOVE:
        return [Finding(
            "W2",
            f"voice_settings.similarity_boost {similarity!r} is above "
            f"{SIMILARITY_WARN_ABOVE} -- risk of an over-enunciated artifact "
            "(voice-selection.md) or reproducing reference noise "
            "(voice-settings.md, [T-unverified])",
        )]
    return []
```

Add the new module-level constants (`SPEED_MIN`, etc., shown above) directly below the existing `OUT_OF_SCOPE_PATH_MARKERS` constant. Add `_voice_id_from_tts_path` and `_check_pvc_v3` as new top-level functions (there is no earlier version of `_check_pvc_v3` to replace).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_validate.py -v`
Expected: PASS (all tests, Task 1's and Task 2's — 58 total).

- [ ] **Step 5: Commit**

```bash
git add elevenlabs-tooling/elevenlabs_tooling/validate.py elevenlabs-tooling/tests/test_validate.py
git commit -m "feat(elevenlabs-tooling): validate E4-E14, W1-W2 -- full checklist, type-safe"
```

---

### Task 3: `log.py` — structured, never-raises logging + test isolation

**Files:**
- Create: `elevenlabs-tooling/elevenlabs_tooling/log.py`
- Create: `elevenlabs-tooling/tests/conftest.py`
- Test: `elevenlabs-tooling/tests/test_log.py`

**Interfaces:**
- Consumes: nothing
- Produces: `log(event: str, *, level: str = "info", **fields) -> None`, `LOG_DIR: Path` (= `elevenlabs-tooling/logs/`); `conftest.py`'s autouse `_isolate_log_dir` fixture, which every later test (Tasks 5–6 included) inherits automatically — no test file after this task needs to patch `LOG_DIR` itself

- [ ] **Step 1: Write the failing tests**

Create `elevenlabs-tooling/tests/conftest.py`:

```python
import pytest

import elevenlabs_tooling.log as log_module


@pytest.fixture(autouse=True)
def _isolate_log_dir(tmp_path, monkeypatch):
    """Every test in this suite writes logs into its own throwaway tmp_path,
    never the real elevenlabs-tooling/logs/ directory. Autouse -- no test
    file needs to request this explicitly."""
    monkeypatch.setattr(log_module, "LOG_DIR", tmp_path / "logs")
```

Create `elevenlabs-tooling/tests/test_log.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_log.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'elevenlabs_tooling.log'`.

- [ ] **Step 3: Implement `log.py`**

Create `elevenlabs-tooling/elevenlabs_tooling/log.py`:

```python
"""Structured, dual-sink logging that never raises.

Mirrors pipeline_app/obs.py's log() shape without importing pipeline_app:
every event is a JSON line written to stderr AND appended to a dated file
under elevenlabs-tooling/logs/. A failure to log must never mask or
interrupt the thing being logged -- every I/O boundary below is wrapped.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def log(event: str, *, level: str = "info", **fields) -> None:
    """Structured line to stderr AND to LOG_DIR/tooling-YYYY-MM-DD.log.

    Never raises.
    """
    now = _utcnow()
    record = {"ts": now.isoformat(timespec="seconds"), "level": level, "event": event}
    record.update(fields)

    try:
        line = json.dumps(record, default=repr, ensure_ascii=False)
    except Exception:  # noqa: BLE001 -- an unserializable field must not kill the caller
        line = json.dumps({
            "ts": now.isoformat(timespec="seconds"),
            "level": level,
            "event": event,
            "fields": "<unserializable>",
        })

    try:
        print(line, file=sys.stderr, flush=True)
    except Exception:  # noqa: BLE001 -- a detached/closed stderr must not kill the caller
        pass

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"tooling-{now.strftime('%Y-%m-%d')}.log"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001 -- a read-only disk must not kill the caller
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_log.py -v`
Expected: PASS (5 tests). Also re-run `tests/test_validate.py` to confirm `conftest.py` didn't break anything unrelated: PASS (58 tests, unaffected).

- [ ] **Step 5: Commit**

```bash
git add elevenlabs-tooling/elevenlabs_tooling/log.py elevenlabs-tooling/tests/conftest.py \
        elevenlabs-tooling/tests/test_log.py
git commit -m "feat(elevenlabs-tooling): add never-raises dual-sink log() + test log isolation"
```

---

### Task 4: `client.py` — the HTTP call

**Files:**
- Create: `elevenlabs-tooling/elevenlabs_tooling/client.py`
- Test: `elevenlabs-tooling/tests/test_client.py`

**Interfaces:**
- Consumes: nothing (uses `requests` directly)
- Produces: `SendResult` (frozen dataclass: `ok: bool`, `status_code: int | None`, `content_type: str | None`, `body: bytes | None`, `error_message: str | None`), `send(url: str, payload_bytes: bytes, api_key: str, timeout: float = DEFAULT_TIMEOUT_S) -> SendResult`, `DEFAULT_TIMEOUT_S: float`

- [ ] **Step 1: Write the failing tests**

Create `elevenlabs-tooling/tests/test_client.py`:

```python
from unittest.mock import MagicMock, patch

import requests

from elevenlabs_tooling.client import DEFAULT_TIMEOUT_S, SendResult, send


def _mock_response(status_code=200, content_type="audio/mpeg", content=b"FAKE_MP3_BYTES", raise_exc=None):
    response = MagicMock()
    response.status_code = status_code
    response.headers = {"Content-Type": content_type}
    response.content = content
    response.text = content.decode("utf-8", errors="replace")
    if raise_exc:
        response.raise_for_status.side_effect = raise_exc
    else:
        response.raise_for_status.return_value = None
    return response


@patch("elevenlabs_tooling.client.requests.post")
def test_send_success_returns_ok_with_body(mock_post):
    mock_post.return_value = _mock_response()
    result = send("https://api.elevenlabs.io/v1/music", b'{"prompt": "x"}', "fake-key")
    assert result.ok is True
    assert result.status_code == 200
    assert result.content_type == "audio/mpeg"
    assert result.body == b"FAKE_MP3_BYTES"
    assert result.error_message is None


@patch("elevenlabs_tooling.client.requests.post")
def test_send_sends_correct_headers_and_raw_body(mock_post):
    mock_post.return_value = _mock_response()
    payload_bytes = b'{"prompt": "exact bytes"}'
    send("https://api.elevenlabs.io/v1/music", payload_bytes, "my-secret-key", timeout=45.0)
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["xi-api-key"] == "my-secret-key"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert kwargs["data"] == payload_bytes
    assert kwargs["timeout"] == 45.0


@patch("elevenlabs_tooling.client.requests.post")
def test_send_unexpected_content_type_returns_not_ok_but_keeps_body(mock_post):
    mock_post.return_value = _mock_response(content_type="application/json", content=b'{"weird": true}')
    result = send("https://api.elevenlabs.io/v1/music", b"{}", "fake-key")
    assert result.ok is False
    assert result.body == b'{"weird": true}'
    assert "audio/*" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_non_2xx_returns_not_ok_with_no_body(mock_post):
    error_response = _mock_response(status_code=422, content_type="application/json")
    error_response.text = '{"detail": "invalid voice_id"}'
    http_error = requests.exceptions.HTTPError("422 Client Error")
    http_error.response = error_response
    mock_post.return_value = _mock_response(status_code=422, raise_exc=http_error)
    result = send("https://api.elevenlabs.io/v1/music", b"{}", "fake-key")
    assert result.ok is False
    assert result.status_code == 422
    assert result.body is None
    assert "invalid voice_id" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_network_error_returns_not_ok_with_no_status(mock_post):
    mock_post.side_effect = requests.exceptions.ConnectionError("connection refused")
    result = send("https://api.elevenlabs.io/v1/music", b"{}", "fake-key")
    assert result.ok is False
    assert result.status_code is None
    assert result.body is None
    assert "connection refused" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_timeout_returns_not_ok(mock_post):
    mock_post.side_effect = requests.exceptions.Timeout("timed out")
    result = send("https://api.elevenlabs.io/v1/music", b"{}", "fake-key")
    assert result.ok is False
    assert "timed out" in result.error_message


def test_default_timeout_is_300_seconds():
    assert DEFAULT_TIMEOUT_S == 300.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'elevenlabs_tooling.client'`.

- [ ] **Step 3: Implement `client.py`**

Create `elevenlabs-tooling/elevenlabs_tooling/client.py`:

```python
"""Thin HTTP client for the ElevenLabs API.

send() never lets requests.exceptions.RequestException propagate -- it
returns a SendResult instead, so callers get uniform control flow. Any other
exception (a genuine bug) is not caught here.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

DEFAULT_TIMEOUT_S = 300.0


@dataclass(frozen=True)
class SendResult:
    ok: bool
    status_code: int | None
    content_type: str | None
    body: bytes | None
    error_message: str | None


def send(
    url: str,
    payload_bytes: bytes,
    api_key: str,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> SendResult:
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(url, headers=headers, data=payload_bytes, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        error_response = getattr(exc, "response", None)
        status_code = getattr(error_response, "status_code", None)
        if error_response is not None:
            body_text = error_response.text[:2000]
            message = f"{exc} -- response body: {body_text}"
        else:
            message = str(exc)
        return SendResult(
            ok=False,
            status_code=status_code,
            content_type=None,
            body=None,
            error_message=message,
        )

    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("audio/"):
        return SendResult(
            ok=False,
            status_code=response.status_code,
            content_type=content_type,
            body=response.content,
            error_message=(
                f"expected an audio/* response, got Content-Type {content_type!r}"
            ),
        )

    return SendResult(
        ok=True,
        status_code=response.status_code,
        content_type=content_type,
        body=response.content,
        error_message=None,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_client.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add elevenlabs-tooling/elevenlabs_tooling/client.py elevenlabs-tooling/tests/test_client.py
git commit -m "feat(elevenlabs-tooling): add client.send() -- POST, never raises RequestException"
```

---

### Task 5: `cli.py` — `validate` subcommand

**Files:**
- Create: `elevenlabs-tooling/elevenlabs_tooling/cli.py`
- Test: `elevenlabs-tooling/tests/test_cli_validate.py`

**Interfaces:**
- Consumes: `Finding`, `is_blocking`, `validate` (Task 1/2); `log` (Task 3, plus the autouse `_isolate_log_dir` fixture from `conftest.py` — no manual `LOG_DIR` patching needed in this task's tests)
- Produces: all 7 exit code constants (`EXIT_PASS=0`, `EXIT_FINDINGS=1`, `EXIT_USAGE=2`, `EXIT_UNREADABLE_INPUT=3`, `EXIT_UNPARSEABLE=4`, `EXIT_SEND_FAILED=5`, `EXIT_NO_API_KEY=6`) — the last two are defined here but unused until Task 6's `cmd_send`; `_load_payload(payload_path: Path) -> tuple[bytes | None, dict | None, int | None]`; `cmd_validate(args) -> int`; `build_parser() -> argparse.ArgumentParser`; `main(argv: list[str] | None = None) -> int` (send-related pieces added in Task 6)

- [ ] **Step 1: Write the failing tests**

Create `elevenlabs-tooling/tests/test_cli_validate.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_cli_validate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'elevenlabs_tooling.cli'`.

- [ ] **Step 3: Implement `cli.py` (validate path only)**

Create `elevenlabs-tooling/elevenlabs_tooling/cli.py`:

```python
"""CLI entry point: `python -m elevenlabs_tooling send|validate ...`"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from elevenlabs_tooling.log import log
from elevenlabs_tooling.validate import Finding, is_blocking, validate

EXIT_PASS = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_UNREADABLE_INPUT = 3
EXIT_UNPARSEABLE = 4
EXIT_SEND_FAILED = 5
EXIT_NO_API_KEY = 6


def _print_findings(findings: list[Finding]) -> None:
    for finding in findings:
        print(f"{finding.check}: {finding.message}", file=sys.stderr)


def _load_payload(payload_path: Path) -> tuple[bytes | None, dict | None, int | None]:
    """Returns (raw_bytes, parsed_dict, error_exit_code).

    On success, error_exit_code is None and the other two are set. On
    failure, raw_bytes and parsed_dict are None and error_exit_code names
    the exit code to return. Every failure mode -- missing file, unreadable
    file, invalid JSON, invalid UTF-8, valid JSON that isn't an object --
    is caught here rather than left to crash the process.
    """
    if not payload_path.is_file():
        print(f"elevenlabs_tooling: payload file not found: {payload_path}", file=sys.stderr)
        return None, None, EXIT_UNREADABLE_INPUT

    try:
        raw_bytes = payload_path.read_bytes()
    except OSError as exc:
        print(f"elevenlabs_tooling: cannot read payload file {payload_path}: {exc}", file=sys.stderr)
        return None, None, EXIT_UNREADABLE_INPUT

    try:
        parsed = json.loads(raw_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"elevenlabs_tooling: payload is not valid JSON: {exc}", file=sys.stderr)
        return None, None, EXIT_UNPARSEABLE

    if not isinstance(parsed, dict):
        print(
            f"elevenlabs_tooling: payload must be a JSON object, got {type(parsed).__name__}",
            file=sys.stderr,
        )
        return None, None, EXIT_UNPARSEABLE

    return raw_bytes, parsed, None


def cmd_validate(args: argparse.Namespace) -> int:
    payload_path = Path(args.payload)
    _raw_bytes, payload, error_code = _load_payload(payload_path)
    if error_code is not None:
        return error_code

    findings = validate(payload, args.url)
    _print_findings(findings)
    blocking = [f for f in findings if is_blocking(f)]
    if blocking:
        log(
            "validate.rejected",
            level="warning",
            url=args.url,
            payload_path=str(payload_path),
            findings=[f.check for f in blocking],
        )
        return EXIT_FINDINGS

    log("validate.passed", url=args.url, payload_path=str(payload_path))
    return EXIT_PASS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m elevenlabs_tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate a payload against a URL without sending it"
    )
    validate_parser.add_argument("--payload", required=True)
    validate_parser.add_argument("--url", required=True)
    validate_parser.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_cli_validate.py -v`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add elevenlabs-tooling/elevenlabs_tooling/cli.py elevenlabs-tooling/tests/test_cli_validate.py
git commit -m "feat(elevenlabs-tooling): add cli.py with the validate subcommand"
```

---

### Task 6: `cli.py` — `send` subcommand, `__main__.py`

**Files:**
- Modify: `elevenlabs-tooling/elevenlabs_tooling/cli.py`
- Create: `elevenlabs-tooling/elevenlabs_tooling/__main__.py`
- Test: `elevenlabs-tooling/tests/test_cli_send.py`

**Interfaces:**
- Consumes: `SendResult`, `send` as `client_send` (Task 4); `DEFAULT_TIMEOUT_S` (Task 4); everything from Task 5
- Produces: `cmd_send(args) -> int`; `_resolve_timeout(cli_value: float | None) -> float`; `API_KEY_ENV_VAR = "ELEVENLABS_API_KEY"`; `TIMEOUT_ENV_VAR = "ELEVENLABS_TOOLING_TIMEOUT_S"`; `build_parser()` now also registers `send`

- [ ] **Step 1: Write the failing tests**

Create `elevenlabs-tooling/tests/test_cli_send.py`:

```python
import json
from unittest.mock import patch

import elevenlabs_tooling.log as log_module
from elevenlabs_tooling.cli import (
    EXIT_FINDINGS,
    EXIT_NO_API_KEY,
    EXIT_PASS,
    EXIT_SEND_FAILED,
    EXIT_USAGE,
    main,
)
from elevenlabs_tooling.client import SendResult

MUSIC_URL = "https://api.elevenlabs.io/v1/music?output_format=mp3_44100_192"


def _write_payload(tmp_path, data):
    path = tmp_path / "payload.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _valid_payload_path(tmp_path):
    return _write_payload(tmp_path, {"prompt": "a calm ambient bed", "model_id": "music_v1"})


def _logged_events():
    files = list(log_module.LOG_DIR.glob("tooling-*.log"))
    assert files, "expected at least one log file to be written"
    return [
        json.loads(line)["event"]
        for line in files[0].read_text(encoding="utf-8").strip().splitlines()
    ]


@patch("elevenlabs_tooling.cli.client_send")
def test_send_success_writes_output_and_returns_pass(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"FAKE_AUDIO", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_PASS
    assert output_path.read_bytes() == b"FAKE_AUDIO"
    mock_send.assert_called_once()


@patch("elevenlabs_tooling.cli.client_send")
def test_send_success_writes_attempt_and_success_log_entries(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"FAKE_AUDIO", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    main(["send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path)])

    events = _logged_events()
    assert "send.attempt" in events
    assert "send.success" in events


@patch("elevenlabs_tooling.cli.client_send")
def test_send_blocked_by_validation_never_calls_client(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    payload_path = _write_payload(tmp_path, {"prompt": "x"})  # missing model_id -> E4
    output_path = tmp_path / "out.mp3"

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_FINDINGS
    mock_send.assert_not_called()
    assert not output_path.exists()


@patch("elevenlabs_tooling.cli.client_send")
def test_send_missing_api_key_returns_no_api_key(mock_send, tmp_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_NO_API_KEY
    assert not output_path.exists()
    mock_send.assert_not_called()


@patch("elevenlabs_tooling.cli.client_send")
def test_send_missing_api_key_reported_after_validation_findings(mock_send, tmp_path, monkeypatch, capsys):
    # A payload with BOTH a validation problem and no API key must report
    # the validation problem (EXIT_FINDINGS), not hide it behind the key
    # check -- and must not touch the network either way.
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    payload_path = _write_payload(tmp_path, {"prompt": "x"})  # missing model_id -> E4
    output_path = tmp_path / "out.mp3"

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_FINDINGS
    mock_send.assert_not_called()
    captured = capsys.readouterr()
    assert "E4: model_id must be present and non-empty" in captured.err


@patch("elevenlabs_tooling.cli.client_send")
def test_send_refuses_to_overwrite_existing_output_without_force(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"
    output_path.write_bytes(b"EXISTING")

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_USAGE
    assert output_path.read_bytes() == b"EXISTING"
    mock_send.assert_not_called()


@patch("elevenlabs_tooling.cli.client_send")
def test_send_overwrites_existing_output_with_force(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"NEW_AUDIO", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"
    output_path.write_bytes(b"OLD_AUDIO")

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
        "--force",
    ])

    assert code == EXIT_PASS
    assert output_path.read_bytes() == b"NEW_AUDIO"


@patch("elevenlabs_tooling.cli.client_send")
def test_send_output_parent_directory_missing(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "does_not_exist" / "out.mp3"

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_USAGE
    mock_send.assert_not_called()


@patch("elevenlabs_tooling.cli.client_send")
def test_send_bare_filename_output_with_no_directory_component_works(mock_send, tmp_path, monkeypatch):
    # --output out.mp3 (no directory) must resolve its parent to the cwd,
    # not crash on an empty parent.
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.chdir(tmp_path)
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"X", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)

    code = main(["send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", "out.mp3"])

    assert code == EXIT_PASS
    assert (tmp_path / "out.mp3").read_bytes() == b"X"


@patch("elevenlabs_tooling.cli.client_send")
def test_send_non_2xx_failure_writes_nothing(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=False, status_code=422, content_type=None, body=None, error_message="invalid voice_id"
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_SEND_FAILED
    assert not output_path.exists()


@patch("elevenlabs_tooling.cli.client_send")
def test_send_failure_writes_send_failed_log_entry(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=False, status_code=422, content_type=None, body=None, error_message="invalid voice_id"
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    main(["send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path)])

    assert "send.failed" in _logged_events()


@patch("elevenlabs_tooling.cli.client_send")
def test_send_unexpected_content_type_quarantines_body(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=False,
        status_code=200,
        content_type="application/json",
        body=b'{"unexpected": true}',
        error_message="expected an audio/* response, got Content-Type 'application/json'",
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_SEND_FAILED
    assert not output_path.exists()
    quarantine_path = tmp_path / "out.mp3.unexpected"
    assert quarantine_path.read_bytes() == b'{"unexpected": true}'


@patch("elevenlabs_tooling.cli.client_send")
def test_send_passes_cli_timeout_to_client(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"X", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
        "--timeout", "12.5",
    ])

    _, kwargs = mock_send.call_args
    assert kwargs["timeout"] == 12.5


@patch("elevenlabs_tooling.cli.client_send")
def test_send_uses_env_timeout_when_no_cli_flag(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setenv("ELEVENLABS_TOOLING_TIMEOUT_S", "77")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"X", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    main(["send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path)])

    _, kwargs = mock_send.call_args
    assert kwargs["timeout"] == 77.0


@patch("elevenlabs_tooling.cli.client_send")
def test_send_falls_back_to_default_on_invalid_env_timeout(mock_send, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setenv("ELEVENLABS_TOOLING_TIMEOUT_S", "not-a-number")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"X", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    main(["send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path)])

    _, kwargs = mock_send.call_args
    assert kwargs["timeout"] == 300.0
    captured = capsys.readouterr()
    assert "ELEVENLABS_TOOLING_TIMEOUT_S" in captured.err


@patch("elevenlabs_tooling.cli.client_send")
def test_send_falls_back_to_default_on_non_positive_cli_timeout(mock_send, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"X", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
        "--timeout", "-5",
    ])

    _, kwargs = mock_send.call_args
    assert kwargs["timeout"] == 300.0
    captured = capsys.readouterr()
    assert "--timeout" in captured.err


@patch("elevenlabs_tooling.cli.client_send")
def test_send_cli_timeout_overrides_env_timeout(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setenv("ELEVENLABS_TOOLING_TIMEOUT_S", "77")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"X", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
        "--timeout", "12.5",
    ])

    _, kwargs = mock_send.call_args
    assert kwargs["timeout"] == 12.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_cli_send.py -v`
Expected: FAIL — `ImportError` (no `send` subcommand / `client_send` / `EXIT_NO_API_KEY` wired in yet).

- [ ] **Step 3: Implement the `send` subcommand**

Modify `elevenlabs-tooling/elevenlabs_tooling/cli.py`. Add these imports at the top (alongside the existing ones):

```python
import hashlib
import os

from elevenlabs_tooling.client import DEFAULT_TIMEOUT_S
from elevenlabs_tooling.client import send as client_send
```

Add these module constants near the exit-code constants:

```python
API_KEY_ENV_VAR = "ELEVENLABS_API_KEY"
TIMEOUT_ENV_VAR = "ELEVENLABS_TOOLING_TIMEOUT_S"
```

Add `_resolve_timeout` and `cmd_send` (place them after `cmd_validate`):

```python
def _resolve_timeout(cli_value: float | None) -> float:
    """--timeout wins over ELEVENLABS_TOOLING_TIMEOUT_S wins over the
    300s default. An invalid value at EITHER level (non-numeric, zero, or
    negative) warns and falls through to the next level rather than being
    used or crashing."""
    if cli_value is not None:
        if cli_value > 0:
            return cli_value
        print(
            f"elevenlabs_tooling: --timeout {cli_value!g} is not a positive "
            "number of seconds; falling back to the environment/default",
            file=sys.stderr,
        )

    raw = os.environ.get(TIMEOUT_ENV_VAR)
    if raw is None or raw.strip() == "":
        return DEFAULT_TIMEOUT_S
    try:
        value = float(raw)
    except ValueError:
        value = 0.0
    if value <= 0:
        print(
            f"elevenlabs_tooling: {TIMEOUT_ENV_VAR}={raw!r} is not a positive "
            f"number of seconds; using the default of {DEFAULT_TIMEOUT_S:g}s",
            file=sys.stderr,
        )
        return DEFAULT_TIMEOUT_S
    return value


def cmd_send(args: argparse.Namespace) -> int:
    payload_path = Path(args.payload)
    output_path = Path(args.output)

    raw_bytes, payload, error_code = _load_payload(payload_path)
    if error_code is not None:
        return error_code

    findings = validate(payload, args.url)
    _print_findings(findings)
    blocking = [f for f in findings if is_blocking(f)]
    if blocking:
        log(
            "validate.rejected",
            level="warning",
            url=args.url,
            payload_path=str(payload_path),
            findings=[f.check for f in blocking],
        )
        return EXIT_FINDINGS

    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        print(f"elevenlabs_tooling: {API_KEY_ENV_VAR} is not set", file=sys.stderr)
        return EXIT_NO_API_KEY

    if output_path.exists() and not args.force:
        print(
            f"elevenlabs_tooling: {output_path} already exists; pass --force to overwrite",
            file=sys.stderr,
        )
        return EXIT_USAGE
    # Path(".").is_dir() is True, so a bare filename like "out.mp3" (parent
    # == the cwd) passes this check correctly rather than being rejected.
    if not output_path.parent.is_dir():
        print(
            f"elevenlabs_tooling: output directory does not exist: {output_path.parent}",
            file=sys.stderr,
        )
        return EXIT_USAGE

    payload_hash = hashlib.sha256(raw_bytes).hexdigest()
    timeout = _resolve_timeout(args.timeout)
    log(
        "send.attempt",
        url=args.url,
        payload_path=str(payload_path),
        payload_sha256=payload_hash,
        output_path=str(output_path),
        timeout=timeout,
    )

    result = client_send(args.url, raw_bytes, api_key, timeout=timeout)

    if result.ok:
        try:
            output_path.write_bytes(result.body)
        except OSError as exc:
            # Credits are already spent and the audio came back fine -- the
            # failure is purely local disk I/O. Still logged as a failure
            # since nothing usable landed at --output.
            print(
                f"elevenlabs_tooling: send succeeded but writing {output_path} failed: {exc}",
                file=sys.stderr,
            )
            log(
                "send.failed",
                level="error",
                url=args.url,
                status_code=result.status_code,
                error=f"write failed after a successful API call: {exc}",
            )
            return EXIT_SEND_FAILED
        log(
            "send.success",
            url=args.url,
            output_path=str(output_path),
            status_code=result.status_code,
            content_type=result.content_type,
            bytes_written=len(result.body),
        )
        return EXIT_PASS

    if result.body is not None:
        quarantine_path = output_path.with_name(output_path.name + ".unexpected")
        try:
            quarantine_path.write_bytes(result.body)
            quarantine_note = f" (response body saved to {quarantine_path})"
        except OSError as exc:
            quarantine_note = f" (also failed to save the response body: {exc})"
        print(
            f"elevenlabs_tooling: send failed: {result.error_message}{quarantine_note}",
            file=sys.stderr,
        )
        log(
            "send.failed",
            level="error",
            url=args.url,
            status_code=result.status_code,
            content_type=result.content_type,
            error=result.error_message,
        )
        return EXIT_SEND_FAILED

    print(f"elevenlabs_tooling: send failed: {result.error_message}", file=sys.stderr)
    log(
        "send.failed",
        level="error",
        url=args.url,
        status_code=result.status_code,
        error=result.error_message,
    )
    return EXIT_SEND_FAILED
```

Update `build_parser()` to register the `send` subcommand — replace the whole function:

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m elevenlabs_tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate a payload against a URL without sending it"
    )
    validate_parser.add_argument("--payload", required=True)
    validate_parser.add_argument("--url", required=True)
    validate_parser.set_defaults(func=cmd_validate)

    send_parser = subparsers.add_parser("send", help="Validate and send a payload")
    send_parser.add_argument("--payload", required=True)
    send_parser.add_argument("--url", required=True)
    send_parser.add_argument("--output", required=True)
    send_parser.add_argument("--timeout", type=float, default=None)
    send_parser.add_argument("--force", action="store_true")
    send_parser.set_defaults(func=cmd_send)

    return parser
```

Create `elevenlabs-tooling/elevenlabs_tooling/__main__.py`:

```python
from __future__ import annotations

import sys

from elevenlabs_tooling.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_cli_send.py -v`
Expected: PASS (17 tests).

Then run the full suite to confirm nothing regressed:

Run: `cd elevenlabs-tooling && python -m pytest tests/ -v`
Expected: PASS (all tests across all five test files).

- [ ] **Step 5: Commit**

```bash
git add elevenlabs-tooling/elevenlabs_tooling/cli.py elevenlabs-tooling/elevenlabs_tooling/__main__.py \
        elevenlabs-tooling/tests/test_cli_send.py
git commit -m "feat(elevenlabs-tooling): add cli.py send subcommand and __main__ entry point"
```

---

### Task 7: `README.md` and full-suite verification

**Files:**
- Create: `elevenlabs-tooling/README.md`

**Interfaces:**
- Consumes: everything from Tasks 1–6 (documents the finished package; no code changes)
- Produces: nothing new

- [ ] **Step 1: Write the README**

Create `elevenlabs-tooling/README.md`. Note the outer fence below uses four backticks specifically so the inner three-backtick fences inside the README's own bash examples are preserved literally rather than being interpreted as closing the outer block — copy everything between the two ```` lines exactly as-is, backticks included:

````markdown
# elevenlabs-tooling

Validates and sends a caller-authored ElevenLabs API payload. Standalone: it
imports nothing from `pipeline_app`, reads no skill, and never decides what
to say to ElevenLabs -- that judgment (voice pick, settings-per-beat,
chunking, prompt craft) lives entirely in the `elevenlabs-audio` and
`elevenlabs-music` skills, which each emit a payload + curl template this
tool then executes.

Design: `docs/superpowers/specs/2026-08-18-elevenlabs-tooling-design.md`.

All commands below assume `cd elevenlabs-tooling` first.

## Install

```bash
pip install -r requirements.txt
```

Requires `ELEVENLABS_API_KEY` set in the environment before `send` (not
`validate`, which never touches the network).

## Use

Validate a payload without spending anything:

```bash
python -m elevenlabs_tooling validate \
  --payload payload.json \
  --url "https://api.elevenlabs.io/v1/text-to-speech/VOICE_ID?output_format=mp3_44100_192"
```

Validate and send:

```bash
python -m elevenlabs_tooling send \
  --payload payload.json \
  --url "https://api.elevenlabs.io/v1/text-to-speech/VOICE_ID?output_format=mp3_44100_192" \
  --output out.mp3
```

`--url` is always the complete URL (base path + query string) exactly as the
skill's curl template gives it -- this tool never constructs one.

`send` refuses to overwrite an existing `--output` file; pass `--force` to
allow it. Its parent directory must already exist.

## Exit codes

```
0  EXIT_PASS               validation clean / send succeeded
1  EXIT_FINDINGS           blocking (E#) errors found -- the payload is the problem
2  EXIT_USAGE              argparse only, or a CLI-level problem (e.g. --output exists without --force)
3  EXIT_UNREADABLE_INPUT   payload file or --url missing/unreadable
4  EXIT_UNPARSEABLE        payload file is not valid JSON, or is valid JSON that isn't an object
5  EXIT_SEND_FAILED        validation passed but the live API call failed, or returned an unexpected content-type
6  EXIT_NO_API_KEY         ELEVENLABS_API_KEY not set (checked only after validation passes)
```

## Validation checklist

See the design spec's "Validation" section for the full E1-E14/W1-W2 table
and the reasoning behind each check. `E#` findings block a send; `W#`
findings print but never block.

## Logging

Every attempt -- rejected, sent, succeeded, or failed -- is logged as a JSON
line to stderr and appended to `elevenlabs-tooling/logs/tooling-YYYY-MM-DD.log`,
written *before* the network call fires. Logging never raises.

## Timeouts

Default 300 seconds. Override with `--timeout SECONDS` or the
`ELEVENLABS_TOOLING_TIMEOUT_S` environment variable (`--timeout` wins if
both are set). An invalid override at either level warns and falls back
rather than crashing.

## Out of scope (v1)

Streaming endpoints, `/v1/music/detailed`'s multipart response, batch/
multi-payload orchestration, automatic retries, and cost estimation/dry-run.
See the design spec for the reasoning behind each boundary.

## Tests

```bash
python -m pytest tests/ -v
```

No test makes a real network call -- the HTTP layer is mocked throughout --
and every test's logging is isolated to a throwaway directory via an autouse
fixture in `tests/conftest.py`, never the real `logs/` directory.
````

- [ ] **Step 2: Run the full test suite one more time**

Run: `cd elevenlabs-tooling && python -m pytest tests/ -v`
Expected: PASS, every test across `test_validate.py`, `test_log.py`, `test_client.py`, `test_cli_validate.py`, `test_cli_send.py`.

- [ ] **Step 3: Commit**

```bash
git add elevenlabs-tooling/README.md
git commit -m "docs(elevenlabs-tooling): add README"
```

---

## Manual verification (not automated — costs real credits)

Once the package is implemented and its own test suite is green, confirm
the one assumption the design spec flags as unverified before relying on it
further: that `POST /v1/music`'s success response is a direct `audio/*` body,
the same shape as the TTS endpoint. Author one small real payload for each
endpoint per the relevant skill's guidance, run `python -m elevenlabs_tooling
send` against both, and confirm both produce a playable audio file. If music's
compose response turns out to need different handling, only
`elevenlabs_tooling/client.py`'s response-parsing branch changes.
