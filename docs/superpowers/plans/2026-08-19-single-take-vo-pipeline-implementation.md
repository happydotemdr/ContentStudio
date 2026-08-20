# Single-Take VO Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-beat VO generation + hand-stitched timing with a single continuous
ElevenLabs generation whose exact pause locations (from `/with-timestamps` character-level
alignment) become the one source of truth that VO stem placement, ducking, captions, and shot
timing all derive from — eliminating the class of drift bug found live in this render (shots/
captions 8.945s out of sync with the actual audio) and the ducking-collapse bug found earlier
this session, at the source, for every future render.

**Architecture:** `elevenlabs_tooling` gains one new capability — call ElevenLabs'
`/text-to-speech/{voice_id}/with-timestamps` and save (audio file, alignment JSON) to disk; it
still never gets imported by `stitcher` and vice versa, keeping the file-based interface this
repo already uses between the two packages. `stitcher` gains four new, additive modules that
consume those two files: `vo_alignment.py` parses `<break>` tag positions against the alignment
into exact `Segment` boundaries; `vo_split.py` cuts the single audio file into per-segment stem
files; `vo_timing.py` turns those same boundaries into exact `Caption` spans and rescales any
beat-relative shot/overlay timing onto them; `vo_assemble.py` builds the `Audio` portion of a
`RenderSpec` from the conditioned stems. `stitcher/stitcher/{audio,spec,envelope,naming,ffmpeg,
precondition}.py` are not modified — every existing, tested capability (loudnorm gate, automatic
ducking, per-clip conditioning) is reused exactly as built.

**Tech Stack:** Python 3, ElevenLabs `eleven_multilingual_v2` (the only model, of those
supporting `<break>` tags, that gives this channel's PVC voice full fidelity — v3 does not
support `<break>` at all), `requests`, ffmpeg 9.0, pytest, pydantic v2 (via `stitcher.spec`).

**Source material:** `docs/superpowers/plans/2026-08-19-vo-architecture-test-plan.md` — this
plan's entire architecture is the direct, empirically-validated output of that investigation
(§6a-§6c): Test 0 (silencedetect boundary recovery fails on a blended file), Call 1 (single-take
generation has no artifacts at 7 breaks), Call 2 (`/with-timestamps` gives exact break-timing
ground truth, median 69ms / max 207ms error), and the free split-and-reassemble test (confirmed,
via direct `envelope.level_at()` query, that real gaps restore ducking to exactly `gain_db`/
`duck_db` — +7.00dB swing, matching design exactly). Every constant and API detail below is
copied from that doc's real, measured results — not re-derived.

## Global Constraints

- `stitcher/stitcher/audio.py`, `spec.py`, `envelope.py`, `naming.py`, `ffmpeg.py`,
  `precondition.py` are **not modified**. All four new `stitcher` modules are additive and
  consume these unchanged.
- `elevenlabs_tooling` and `stitcher` communicate **only through files on disk** (an audio file +
  a JSON alignment file) — neither package imports the other. This matches how they're already
  used together in this repo (`elevenlabs_tooling` never appears in `stitcher`'s dependencies).
- The `<break time="Xs" />` SSML tag works on `eleven_multilingual_v2`, `eleven_flash_v2`, and
  `eleven_flash_v2_5` — **not** `eleven_v3` (v3 uses bracketed audio tags instead, a different,
  incompatible mechanism). Every payload in this plan targeting `/with-timestamps` uses
  `model_id: eleven_multilingual_v2`.
- Real, measured break-tag behavior (Call 2, `docs/superpowers/plans/
  2026-08-19-vo-architecture-test-plan.md` §6c): every break runs **longer** than requested, by
  roughly 50–210ms, consistently (never shorter). `Bed`'s ramps are `duck_attack_ms=120`,
  `duck_release_ms=400` (`spec.py:139-140`, unmodified) — a gap needs to clear both (520ms) before
  the envelope reaches a true flat baseline. Task 11's break durations are chosen with this
  margin in mind (§ Task 11).
- Tests: `stitcher/` tests run from `stitcher/` (`cd stitcher && python -m pytest tests/ -v`);
  `elevenlabs-tooling/` tests run from `elevenlabs-tooling/`
  (`cd elevenlabs-tooling && python -m pytest tests/ -v`). Each has its own `pytest.ini`
  (`pythonpath = .`, `testpaths = tests`).
- No ElevenLabs spend in Tasks 1–10 (mocked HTTP/ffmpeg throughout). **Task 11 makes exactly one
  real, billed ElevenLabs API call** (~950 characters ≈ $0.10 at the Multilingual v2 rate) —
  confirm this is still wanted before running it if cost sensitivity has changed since this plan
  was written.
- `elevenlabs_tooling/validate.py`'s `_voice_id_from_tts_path` (`validate.py:163-176`) already
  anticipates `/text-to-speech/{voice_id}/with-timestamps` as an in-scope path shape — no change
  needed there. `PINNED_NARRATOR_VOICE_ID = "eDwT8Vhp2yxJzAMmuuPA"` (`validate.py:18`) is the
  voice this plan's payloads target throughout.

---

## File Structure

| File | Responsibility |
|---|---|
| `elevenlabs-tooling/elevenlabs_tooling/breaks.py` | New. `compose_break_tagged_text()` — joins beat texts with `<break time="Xs" />` tags. |
| `elevenlabs-tooling/elevenlabs_tooling/client.py` | Modified. Adds `TimestampsResult` + `send_with_timestamps()` for the JSON-with-embedded-audio response shape `/with-timestamps` actually returns (existing `send()`/`SendResult` are untouched — they're correct for every other endpoint). |
| `elevenlabs-tooling/elevenlabs_tooling/cli.py` | Modified. Adds a `generate-vo` subcommand wiring `send_with_timestamps` into the existing validate → send → write pattern, writing audio + alignment JSON as two separate output files. |
| `stitcher/stitcher/vo_alignment.py` | New. `Segment` dataclass + `derive_segments()` — the core parsing logic proven in this session's investigation, now as tested production code. |
| `stitcher/stitcher/vo_split.py` | New. `split_segments()` — ffmpeg-trims the single-take audio into one file per `Segment`. |
| `stitcher/stitcher/vo_timing.py` | New. `derive_captions()` (exact caption spans from segments) + `rescale_relative_spans()` (maps beat-relative shot/overlay fractions onto a segment's measured absolute window). |
| `stitcher/stitcher/vo_assemble.py` | New. `build_audio_config()` — builds a real `stitcher.spec.Audio` from segments + conditioned stem files + bed config. |
| `.claude/skills/elevenlabs-audio/references/model-routing.md` | Modified. Documents `<break time="Xs"/>` support (a real gap this session found — the skill currently documents only v3's bracketed `[pause]` tag, which does not apply to this channel's model). |
| `.claude/skills/elevenlabs-audio/references/directorial-prompting.md` | Modified. Cross-references the same gap where pause-related tags are discussed. |
| `.claude/skills/voiceover-brief/references/single-take-architecture.md` | New. Records the `[P]` operator decision (single-take generation, re-roll granularity traded away) with the corpus's contrary position stated honestly, not silently overridden. |
| `docs/superpowers/plans/2026-08-19-single-take-vo-pipeline-RESULTS.md` | New. Written at the end of Task 11, capturing the real run's output. |

---

### Task 1: `compose_break_tagged_text()` — the request-side half

**Files:**
- Create: `elevenlabs-tooling/elevenlabs_tooling/breaks.py`
- Test: `elevenlabs-tooling/tests/test_breaks.py`

**Interfaces:**
- Produces: `compose_break_tagged_text(beats: list[str], break_seconds: list[float]) -> str`

- [ ] **Step 1: Write the failing tests**

Create `elevenlabs-tooling/tests/test_breaks.py`:

```python
import pytest

from elevenlabs_tooling.breaks import compose_break_tagged_text


def test_composes_two_beats_with_one_break():
    result = compose_break_tagged_text(["Hello there.", "Goodbye now."], [0.9])
    assert result == 'Hello there. <break time="0.9s" /> Goodbye now.'


def test_composes_three_beats_with_two_breaks_of_different_durations():
    result = compose_break_tagged_text(
        ["First beat.", "Second beat.", "Third beat."], [0.5, 1.2]
    )
    assert result == (
        'First beat. <break time="0.5s" /> Second beat. '
        '<break time="1.2s" /> Third beat.'
    )


def test_single_beat_needs_no_breaks():
    assert compose_break_tagged_text(["Only one beat."], []) == "Only one beat."


def test_wrong_break_count_raises():
    with pytest.raises(ValueError, match="exactly 2 entries"):
        compose_break_tagged_text(["A", "B", "C"], [0.5])


def test_break_duration_zero_raises():
    with pytest.raises(ValueError, match="0-3s range"):
        compose_break_tagged_text(["A", "B"], [0.0])


def test_break_duration_over_three_seconds_raises():
    with pytest.raises(ValueError, match="0-3s range"):
        compose_break_tagged_text(["A", "B"], [3.5])


def test_empty_beats_list_raises():
    with pytest.raises(ValueError, match="at least one beat"):
        compose_break_tagged_text([], [])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_breaks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'elevenlabs_tooling.breaks'`

- [ ] **Step 3: Write `breaks.py`**

Create `elevenlabs-tooling/elevenlabs_tooling/breaks.py`:

```python
"""Compose ElevenLabs SSML <break> tags into a beat-by-beat script for a
single continuous TTS generation.

<break time="Xs" /> is supported on eleven_multilingual_v2, eleven_flash_v2,
and eleven_flash_v2_5 (NOT eleven_v3, which uses bracketed audio tags
instead) -- verified against ElevenLabs' own help-center docs, 2026-08-19.
Real breaks measured via /with-timestamps ground truth run long by roughly
50-210ms versus the requested duration (a consistent, one-directional
bias) -- see docs/superpowers/plans/2026-08-19-vo-architecture-test-plan.md
§6c. Size requested durations with that overshoot in mind, not as exact.
"""

from __future__ import annotations


def compose_break_tagged_text(beats: list[str], break_seconds: list[float]) -> str:
    """Join `beats` with `<break time="Xs" />` tags between each pair.

    len(break_seconds) must be exactly len(beats) - 1 -- one break between
    every pair of adjacent beats, none before the first or after the last.
    """
    if len(beats) < 1:
        raise ValueError("beats must contain at least one beat")
    if len(break_seconds) != len(beats) - 1:
        raise ValueError(
            f"break_seconds must have exactly {len(beats) - 1} entries "
            f"(one between each pair of {len(beats)} beats), got {len(break_seconds)}"
        )
    for seconds in break_seconds:
        if not (0 < seconds <= 3.0):
            raise ValueError(
                f"break duration {seconds}s is outside ElevenLabs' documented "
                "0-3s range for <break> tags"
            )

    parts = [beats[0]]
    for beat, seconds in zip(beats[1:], break_seconds):
        parts.append(f'<break time="{seconds:.1f}s" />')
        parts.append(beat)
    return " ".join(parts)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_breaks.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add elevenlabs-tooling/elevenlabs_tooling/breaks.py elevenlabs-tooling/tests/test_breaks.py
git commit -m "feat(elevenlabs-tooling): add break-tagged script composition"
```

---

### Task 2: `send_with_timestamps()` — the response-side HTTP call

**Files:**
- Modify: `elevenlabs-tooling/elevenlabs_tooling/client.py`
- Test: `elevenlabs-tooling/tests/test_client.py`

**Interfaces:**
- Consumes: `requests.post` (mocked in tests, matching `send()`'s existing test pattern).
- Produces: `TimestampsResult` (frozen dataclass: `ok: bool`, `status_code: int | None`,
  `audio_bytes: bytes | None`, `alignment: dict | None`, `error_message: str | None`);
  `send_with_timestamps(url: str, payload_bytes: bytes, api_key: str, timeout: float = DEFAULT_TIMEOUT_S) -> TimestampsResult`

- [ ] **Step 1: Write the failing tests**

Append to `elevenlabs-tooling/tests/test_client.py` (add `import base64` and `import json` at the
top of the file, alongside the existing imports):

```python
import base64
import json

from elevenlabs_tooling.client import TimestampsResult, send_with_timestamps


def _mock_json_response(status_code=200, content_type="application/json", payload=None, raise_exc=None):
    response = MagicMock()
    response.status_code = status_code
    response.headers = {"Content-Type": content_type}
    response.json.return_value = payload if payload is not None else {}
    response.text = json.dumps(payload if payload is not None else {})
    response.content = response.text.encode("utf-8")
    if raise_exc:
        response.raise_for_status.side_effect = raise_exc
    else:
        response.raise_for_status.return_value = None
    return response


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_success_decodes_audio_and_alignment(mock_post):
    fake_alignment = {
        "characters": ["H", "i"],
        "character_start_times_seconds": [0.0, 0.1],
        "character_end_times_seconds": [0.1, 0.2],
    }
    mock_post.return_value = _mock_json_response(payload={
        "audio_base64": base64.b64encode(b"FAKE_AUDIO_BYTES").decode("ascii"),
        "alignment": fake_alignment,
        "normalized_alignment": fake_alignment,
    })
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b'{"text": "Hi"}', "fake-key",
    )
    assert result.ok is True
    assert result.status_code == 200
    assert result.audio_bytes == b"FAKE_AUDIO_BYTES"
    assert result.alignment == fake_alignment
    assert result.error_message is None


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_sends_correct_headers_and_raw_body(mock_post):
    mock_post.return_value = _mock_json_response(payload={
        "audio_base64": base64.b64encode(b"X").decode("ascii"),
        "alignment": {"characters": []},
    })
    payload_bytes = b'{"text": "exact bytes"}'
    send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        payload_bytes, "my-secret-key", timeout=45.0,
    )
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["xi-api-key"] == "my-secret-key"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert kwargs["data"] == payload_bytes
    assert kwargs["timeout"] == 45.0


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_missing_alignment_field_returns_not_ok(mock_post):
    mock_post.return_value = _mock_json_response(payload={
        "audio_base64": base64.b64encode(b"X").decode("ascii"),
    })
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert "alignment" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_wrong_content_type_returns_not_ok(mock_post):
    mock_post.return_value = _mock_json_response(content_type="audio/mpeg")
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert "application/json" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_non_2xx_returns_not_ok(mock_post):
    error_response = _mock_json_response(status_code=422)
    error_response.text = '{"detail": "invalid voice_id"}'
    http_error = requests.exceptions.HTTPError("422 Client Error")
    http_error.response = error_response
    mock_post.return_value = _mock_json_response(status_code=422, raise_exc=http_error)
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert result.status_code == 422
    assert "invalid voice_id" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_network_error_returns_not_ok(mock_post):
    mock_post.side_effect = requests.exceptions.ConnectionError("connection refused")
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert result.status_code is None
    assert "connection refused" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_malformed_json_body_returns_not_ok(mock_post):
    response = _mock_json_response()
    response.json.side_effect = ValueError("Expecting value: line 1 column 1")
    mock_post.return_value = response
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert result.audio_bytes is None
    assert "did not parse" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_non_dict_json_body_returns_not_ok(mock_post):
    mock_post.return_value = _mock_json_response(payload=["unexpected", "array"])
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert "must be an object" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_invalid_base64_returns_not_ok(mock_post):
    mock_post.return_value = _mock_json_response(payload={
        "audio_base64": "not valid base64!!!",
        "alignment": {"characters": []},
    })
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert "did not decode as base64" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_failure_preserves_raw_body_for_quarantine(mock_post):
    mock_post.return_value = _mock_json_response(payload={"unexpected": "shape"})
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert result.raw_body == b'{"unexpected": "shape"}'
```

`requests` is already imported at the top of `test_client.py` — no new import needed for that.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_client.py -v -k with_timestamps`
Expected: FAIL with `ImportError: cannot import name 'TimestampsResult'`

- [ ] **Step 3: Add `TimestampsResult` and `send_with_timestamps()` to `client.py`**

Add `import base64` to the top of `elevenlabs-tooling/elevenlabs_tooling/client.py` (alongside
the existing `from dataclasses import dataclass` / `import requests`), then append:

```python
@dataclass(frozen=True)
class TimestampsResult:
    ok: bool
    status_code: int | None
    audio_bytes: bytes | None
    alignment: dict | None
    error_message: str | None
    # Raw response bytes, populated only on failure paths that actually
    # received a response body (never on a network-level failure with no
    # response at all) -- lets a caller quarantine an unexpected body after
    # a billed call instead of discarding it, mirroring send()'s own
    # quarantine behavior in cmd_send.
    raw_body: bytes | None = None


def send_with_timestamps(
    url: str,
    payload_bytes: bytes,
    api_key: str,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> TimestampsResult:
    """Like send(), but for endpoints that return application/json with a
    base64-encoded audio field (e.g. /text-to-speech/{voice_id}/with-timestamps)
    instead of a raw audio/* body. Never lets requests.exceptions.RequestException
    propagate -- returns a TimestampsResult instead, mirroring send()'s contract.
    """
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
            raw_body = getattr(error_response, "content", None)
        else:
            message = str(exc)
            raw_body = None
        return TimestampsResult(
            ok=False, status_code=status_code, audio_bytes=None, alignment=None,
            error_message=message, raw_body=raw_body,
        )

    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("application/json"):
        return TimestampsResult(
            ok=False, status_code=response.status_code, audio_bytes=None, alignment=None,
            error_message=(
                f"expected an application/json response, got Content-Type {content_type!r}"
            ),
            raw_body=response.content,
        )

    try:
        body = response.json()
    except ValueError as exc:
        return TimestampsResult(
            ok=False, status_code=response.status_code, audio_bytes=None, alignment=None,
            error_message=f"response Content-Type was application/json but the body did not parse: {exc}",
            raw_body=response.content,
        )

    if not isinstance(body, dict):
        return TimestampsResult(
            ok=False, status_code=response.status_code, audio_bytes=None, alignment=None,
            error_message=f"response JSON must be an object, got {type(body).__name__}",
            raw_body=response.content,
        )

    audio_b64 = body.get("audio_base64")
    alignment = body.get("alignment")
    if audio_b64 is None or alignment is None:
        return TimestampsResult(
            ok=False, status_code=response.status_code, audio_bytes=None, alignment=None,
            error_message=(
                "response JSON is missing 'audio_base64' or 'alignment' -- "
                f"got keys {sorted(body.keys())}"
            ),
            raw_body=response.content,
        )

    try:
        audio_bytes = base64.b64decode(audio_b64, validate=True)
    except (ValueError, TypeError) as exc:
        return TimestampsResult(
            ok=False, status_code=response.status_code, audio_bytes=None, alignment=None,
            error_message=f"audio_base64 field did not decode as base64: {exc}",
            raw_body=response.content,
        )

    return TimestampsResult(
        ok=True, status_code=response.status_code,
        audio_bytes=audio_bytes, alignment=alignment,
        error_message=None,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_client.py -v`
Expected: PASS (all tests, including the 10 new ones — `send()`'s existing tests are untouched
and must still pass)

- [ ] **Step 5: Commit**

```bash
git add elevenlabs-tooling/elevenlabs_tooling/client.py elevenlabs-tooling/tests/test_client.py
git commit -m "feat(elevenlabs-tooling): add send_with_timestamps for the /with-timestamps response shape"
```

---

### Task 3: `generate-vo` CLI subcommand

**Files:**
- Modify: `elevenlabs-tooling/elevenlabs_tooling/cli.py`
- Test: `elevenlabs-tooling/tests/test_cli_generate_vo.py`

**Interfaces:**
- Consumes: `send_with_timestamps` (Task 2), `TimestampsResult` (Task 2), `validate`/`is_blocking`
  (existing, unchanged), `_load_payload`/`_print_findings`/`_resolve_timeout` (existing helpers
  in `cli.py`, unchanged).
- Produces: `cmd_generate_vo(args) -> int`; a `generate-vo` subcommand on the existing parser.

- [ ] **Step 1: Write the failing tests**

Create `elevenlabs-tooling/tests/test_cli_generate_vo.py`:

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
from elevenlabs_tooling.client import TimestampsResult

TTS_URL = (
    "https://api.elevenlabs.io/v1/text-to-speech/eDwT8Vhp2yxJzAMmuuPA/with-timestamps"
    "?output_format=mp3_44100_192"
)

FAKE_ALIGNMENT = {
    "characters": ["H", "i"],
    "character_start_times_seconds": [0.0, 0.1],
    "character_end_times_seconds": [0.1, 0.2],
}


def _write_payload(tmp_path, data):
    path = tmp_path / "payload.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _valid_payload_path(tmp_path):
    return _write_payload(tmp_path, {"text": "Hello world.", "model_id": "eleven_multilingual_v2"})


def _logged_events():
    files = list(log_module.LOG_DIR.glob("tooling-*.log"))
    assert files, "expected at least one log file to be written"
    return [
        json.loads(line)["event"]
        for line in files[0].read_text(encoding="utf-8").strip().splitlines()
    ]


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_success_writes_audio_and_alignment(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = TimestampsResult(
        ok=True, status_code=200, audio_bytes=b"FAKE_AUDIO", alignment=FAKE_ALIGNMENT,
        error_message=None,
    )
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    alignment_output = tmp_path / "vo_alignment.json"

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    assert code == EXIT_PASS
    assert audio_output.read_bytes() == b"FAKE_AUDIO"
    assert json.loads(alignment_output.read_text(encoding="utf-8")) == FAKE_ALIGNMENT
    mock_send.assert_called_once()


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_success_writes_attempt_and_success_log_entries(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = TimestampsResult(
        ok=True, status_code=200, audio_bytes=b"X", alignment=FAKE_ALIGNMENT, error_message=None,
    )
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    alignment_output = tmp_path / "vo_alignment.json"

    main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    events = _logged_events()
    assert "generate_vo.attempt" in events
    assert "generate_vo.success" in events


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_blocked_by_validation_never_calls_client(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    payload_path = _write_payload(tmp_path, {"text": "Hi"})  # missing model_id -> E4
    audio_output = tmp_path / "vo.mp3"
    alignment_output = tmp_path / "vo_alignment.json"

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    assert code == EXIT_FINDINGS
    mock_send.assert_not_called()
    assert not audio_output.exists()
    assert not alignment_output.exists()


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_missing_api_key_returns_no_api_key(mock_send, tmp_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    alignment_output = tmp_path / "vo_alignment.json"

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    assert code == EXIT_NO_API_KEY
    assert not audio_output.exists()
    mock_send.assert_not_called()


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_refuses_to_overwrite_audio_output_without_force(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    audio_output.write_bytes(b"EXISTING")
    alignment_output = tmp_path / "vo_alignment.json"

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    assert code == EXIT_USAGE
    assert audio_output.read_bytes() == b"EXISTING"
    mock_send.assert_not_called()


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_refuses_to_overwrite_alignment_output_without_force(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    alignment_output = tmp_path / "vo_alignment.json"
    alignment_output.write_text('{"existing": true}', encoding="utf-8")

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    assert code == EXIT_USAGE
    assert alignment_output.read_text(encoding="utf-8") == '{"existing": true}'
    mock_send.assert_not_called()


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_overwrites_both_outputs_with_force(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = TimestampsResult(
        ok=True, status_code=200, audio_bytes=b"NEW_AUDIO", alignment=FAKE_ALIGNMENT,
        error_message=None,
    )
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    audio_output.write_bytes(b"OLD_AUDIO")
    alignment_output = tmp_path / "vo_alignment.json"
    alignment_output.write_text('{"old": true}', encoding="utf-8")

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
        "--force",
    ])

    assert code == EXIT_PASS
    assert audio_output.read_bytes() == b"NEW_AUDIO"
    assert json.loads(alignment_output.read_text(encoding="utf-8")) == FAKE_ALIGNMENT


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_send_failure_writes_nothing(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = TimestampsResult(
        ok=False, status_code=422, audio_bytes=None, alignment=None,
        error_message="invalid voice_id",
    )
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    alignment_output = tmp_path / "vo_alignment.json"

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    assert code == EXIT_SEND_FAILED
    assert not audio_output.exists()
    assert not alignment_output.exists()


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_failure_with_a_body_quarantines_it(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = TimestampsResult(
        ok=False, status_code=200, audio_bytes=None, alignment=None,
        error_message="response JSON is missing 'audio_base64' or 'alignment'",
        raw_body=b'{"unexpected": true}',
    )
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    alignment_output = tmp_path / "vo_alignment.json"

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    assert code == EXIT_SEND_FAILED
    assert not audio_output.exists()
    quarantine_path = tmp_path / "vo.mp3.unexpected"
    assert quarantine_path.read_bytes() == b'{"unexpected": true}'
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_cli_generate_vo.py -v`
Expected: FAIL — `main()` rejects the unknown `generate-vo` subcommand (argparse error)

- [ ] **Step 3: Add `cmd_generate_vo` and the subcommand to `cli.py`**

In `elevenlabs-tooling/elevenlabs_tooling/cli.py`, change the import line

```python
from elevenlabs_tooling.client import DEFAULT_TIMEOUT_S
from elevenlabs_tooling.client import send as client_send
```

to also import the new function:

```python
from elevenlabs_tooling.client import DEFAULT_TIMEOUT_S
from elevenlabs_tooling.client import send as client_send
from elevenlabs_tooling.client import send_with_timestamps as client_send_with_timestamps
```

Then add, after `cmd_send` (before `build_parser`):

```python
def cmd_generate_vo(args: argparse.Namespace) -> int:
    payload_path = Path(args.payload)
    audio_output_path = Path(args.audio_output)
    alignment_output_path = Path(args.alignment_output)

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
        log(
            "generate_vo.aborted",
            level="warning",
            url=args.url,
            payload_path=str(payload_path),
            reason="no_api_key",
        )
        return EXIT_NO_API_KEY

    for label, out_path in (("audio", audio_output_path), ("alignment", alignment_output_path)):
        if out_path.exists() and not args.force:
            print(
                f"elevenlabs_tooling: {label} output {out_path} already exists; "
                "pass --force to overwrite",
                file=sys.stderr,
            )
            log(
                "generate_vo.aborted",
                level="warning",
                url=args.url,
                payload_path=str(payload_path),
                reason=f"{label}_output_exists",
            )
            return EXIT_USAGE
        if not out_path.parent.is_dir():
            print(
                f"elevenlabs_tooling: {label} output directory does not exist: {out_path.parent}",
                file=sys.stderr,
            )
            log(
                "generate_vo.aborted",
                level="warning",
                url=args.url,
                payload_path=str(payload_path),
                reason=f"{label}_output_parent_missing",
            )
            return EXIT_USAGE

    payload_hash = hashlib.sha256(raw_bytes).hexdigest()
    timeout = _resolve_timeout(args.timeout)
    log(
        "generate_vo.attempt",
        url=args.url,
        payload_path=str(payload_path),
        payload_sha256=payload_hash,
        audio_output_path=str(audio_output_path),
        alignment_output_path=str(alignment_output_path),
        timeout=timeout,
    )

    try:
        result = client_send_with_timestamps(args.url, raw_bytes, api_key, timeout=timeout)
    except Exception as exc:
        print(
            f"elevenlabs_tooling: unexpected error sending the payload: {type(exc).__name__}",
            file=sys.stderr,
        )
        log("generate_vo.failed", level="error", url=args.url, error=type(exc).__name__)
        return EXIT_SEND_FAILED

    if not result.ok:
        quarantine_note = ""
        if result.raw_body is not None:
            quarantine_path = audio_output_path.with_name(audio_output_path.name + ".unexpected")
            try:
                quarantine_path.write_bytes(result.raw_body)
                quarantine_note = f" (response body saved to {quarantine_path})"
            except OSError as exc:
                quarantine_note = f" (also failed to save the response body: {exc})"
        print(
            f"elevenlabs_tooling: generate-vo failed: {result.error_message}{quarantine_note}",
            file=sys.stderr,
        )
        log(
            "generate_vo.failed",
            level="error",
            url=args.url,
            status_code=result.status_code,
            error=result.error_message,
        )
        return EXIT_SEND_FAILED

    try:
        audio_output_path.write_bytes(result.audio_bytes)
        alignment_output_path.write_text(json.dumps(result.alignment), encoding="utf-8")
    except OSError as exc:
        print(
            f"elevenlabs_tooling: generate-vo succeeded but writing output failed: {exc}",
            file=sys.stderr,
        )
        log(
            "generate_vo.failed",
            level="error",
            url=args.url,
            status_code=result.status_code,
            error=f"write failed after a successful API call: {exc}",
        )
        return EXIT_SEND_FAILED

    log(
        "generate_vo.success",
        url=args.url,
        audio_output_path=str(audio_output_path),
        alignment_output_path=str(alignment_output_path),
        status_code=result.status_code,
        audio_bytes_written=len(result.audio_bytes),
    )
    return EXIT_PASS
```

Then, inside `build_parser()`, after the existing `send_parser` block and before `return parser`:

```python
    generate_vo_parser = subparsers.add_parser(
        "generate-vo",
        help="Validate and send a /with-timestamps TTS payload, writing audio + alignment JSON",
    )
    generate_vo_parser.add_argument("--payload", required=True)
    generate_vo_parser.add_argument("--url", required=True)
    generate_vo_parser.add_argument("--audio-output", required=True)
    generate_vo_parser.add_argument("--alignment-output", required=True)
    generate_vo_parser.add_argument("--timeout", type=float, default=None)
    generate_vo_parser.add_argument("--force", action="store_true")
    generate_vo_parser.set_defaults(func=cmd_generate_vo)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_cli_generate_vo.py -v`
Expected: PASS (9 tests)

Run: `cd elevenlabs-tooling && python -m pytest tests/ -v`
Expected: PASS (every existing test plus the new ones — confirms no regression)

- [ ] **Step 5: Commit**

```bash
git add elevenlabs-tooling/elevenlabs_tooling/cli.py elevenlabs-tooling/tests/test_cli_generate_vo.py
git commit -m "feat(elevenlabs-tooling): add generate-vo CLI subcommand"
```

---

### Task 4: `stitcher.vo_alignment` — parse `/with-timestamps` into exact segment boundaries

**Files:**
- Create: `stitcher/stitcher/vo_alignment.py`
- Test: `stitcher/tests/test_vo_alignment.py`

**Interfaces:**
- Produces: `Segment` (frozen dataclass: `name: str`, `at: float`, `duration: float`);
  `derive_segments(text: str, alignment: dict, names: list[str] | None = None) -> list[Segment]`

- [ ] **Step 1: Write the failing tests**

Create `stitcher/tests/test_vo_alignment.py`:

```python
import pytest

from stitcher.vo_alignment import Segment, derive_segments


def _build_case(beat_texts, break_seconds):
    """Build (text, alignment) for beats joined by <break> tags, with a
    synthetic alignment that mirrors ElevenLabs' real observed structure
    (docs/superpowers/plans/2026-08-19-vo-architecture-test-plan.md §6c):
    the entire pause duration lands on the space character immediately
    before the <break> tag; the tag's own markup characters (and the space
    after it) are zero-width at the instant the pause ends; the next real
    character begins at that exact instant."""
    CHAR_DUR = 0.1
    chars, starts, ends = [], [], []
    clock = 0.0

    def emit_real(s):
        nonlocal clock
        for ch in s:
            chars.append(ch)
            starts.append(round(clock, 4))
            clock = round(clock + CHAR_DUR, 4)
            ends.append(clock)

    def emit_gap_char(ch, gap):
        nonlocal clock
        chars.append(ch)
        starts.append(round(clock, 4))
        clock = round(clock + gap, 4)
        ends.append(clock)

    def emit_zero_width(s):
        for ch in s:
            chars.append(ch)
            starts.append(clock)
            ends.append(clock)

    text_parts = [beat_texts[0]]
    emit_real(beat_texts[0])
    for beat, seconds in zip(beat_texts[1:], break_seconds):
        tag = f'<break time="{seconds:.1f}s" />'
        emit_gap_char(" ", seconds)
        emit_zero_width(tag)
        emit_zero_width(" ")
        emit_real(beat)
        text_parts.append(f' {tag} ')
        text_parts.append(beat)

    text = "".join(text_parts)
    alignment = {
        "characters": chars,
        "character_start_times_seconds": starts,
        "character_end_times_seconds": ends,
    }
    assert len(chars) == len(text)
    return text, alignment


def test_two_beats_one_break_recovers_correct_segment_boundaries():
    beat1, beat2 = "Hi there.", "Bye now."
    text, alignment = _build_case([beat1, beat2], [0.5])

    segments = derive_segments(text, alignment)

    assert len(segments) == 2
    assert segments[0].name == "beat1"
    assert segments[0].at == 0.0
    assert segments[0].duration == pytest.approx(len(beat1) * 0.1)
    assert segments[1].name == "beat2"
    assert segments[1].at == pytest.approx(len(beat1) * 0.1 + 0.5)
    assert segments[1].duration == pytest.approx(len(beat2) * 0.1)


def test_three_beats_two_breaks_recovers_all_boundaries():
    beat1, beat2, beat3 = "First one.", "Second one.", "Third one."
    text, alignment = _build_case([beat1, beat2, beat3], [0.5, 0.3])

    segments = derive_segments(text, alignment)

    assert [s.name for s in segments] == ["beat1", "beat2", "beat3"]
    b1_end = len(beat1) * 0.1
    b2_at = b1_end + 0.5
    b2_end = b2_at + len(beat2) * 0.1
    b3_at = b2_end + 0.3
    assert segments[0].at == 0.0
    assert segments[0].duration == pytest.approx(len(beat1) * 0.1)
    assert segments[1].at == pytest.approx(b2_at)
    assert segments[1].duration == pytest.approx(len(beat2) * 0.1)
    assert segments[2].at == pytest.approx(b3_at)
    assert segments[2].duration == pytest.approx(len(beat3) * 0.1)


def test_custom_names_are_used_in_order():
    text, alignment = _build_case(["A beat.", "Another beat."], [0.4])
    segments = derive_segments(text, alignment, names=["hook", "cta"])
    assert [s.name for s in segments] == ["hook", "cta"]


def test_single_beat_no_breaks_returns_one_segment_spanning_the_whole_text():
    beat = "Just one beat here."
    text, alignment = _build_case([beat], [])
    segments = derive_segments(text, alignment)
    assert len(segments) == 1
    assert segments[0].at == 0.0
    assert segments[0].duration == pytest.approx(len(beat) * 0.1)


def test_mismatched_names_length_raises():
    text, alignment = _build_case(["A.", "B."], [0.5])
    with pytest.raises(ValueError, match="2 segments"):
        derive_segments(text, alignment, names=["only_one"])


def test_alignment_length_mismatch_raises():
    text, alignment = _build_case(["A.", "B."], [0.5])
    alignment["characters"] = alignment["characters"][:-1]
    with pytest.raises(ValueError, match="mismatched lengths"):
        derive_segments(text, alignment)


def test_alignment_text_mismatch_raises():
    text, alignment = _build_case(["A.", "B."], [0.5])
    with pytest.raises(ValueError, match="do not reconstruct"):
        derive_segments("Completely different text.", alignment)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd stitcher && python -m pytest tests/test_vo_alignment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'stitcher.vo_alignment'`

- [ ] **Step 3: Write `vo_alignment.py`**

Create `stitcher/stitcher/vo_alignment.py`:

```python
"""Derive stem segment boundaries from ElevenLabs' /with-timestamps
character-level alignment, given the exact submitted text (including its
<break time="Xs" /> tags).

Verified against real ElevenLabs output (docs/superpowers/plans/
2026-08-19-vo-architecture-test-plan.md §6c): a <break> tag's own markup
characters all collapse to a single zero-duration instant at the moment the
break begins ("<", "b", "r", ... all report the same start==end timestamp).
The real, audible pause length is the gap between the last real spoken
character's end time before the tag and the first real spoken character's
start time after it -- not anything printed for the tag's own characters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_BREAK_RE = re.compile(r'<break time="[\d.]+s" />')


@dataclass(frozen=True)
class Segment:
    name: str
    at: float
    duration: float


def derive_segments(text: str, alignment: dict, names: list[str] | None = None) -> list[Segment]:
    """Split `text` on its <break> tags and return one Segment per piece of
    real spoken text, with `at`/`duration` taken from `alignment`'s
    character-level timestamps.

    `alignment` is the `alignment` field of an ElevenLabs /with-timestamps
    response: {"characters": [...], "character_start_times_seconds": [...],
    "character_end_times_seconds": [...]}. All three lists must be the same
    length as `text`.
    """
    chars = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]
    if not (len(chars) == len(starts) == len(ends)):
        raise ValueError(
            f"alignment lists have mismatched lengths: "
            f"characters={len(chars)} starts={len(starts)} ends={len(ends)}"
        )
    aligned_text = "".join(chars)
    if aligned_text != text:
        raise ValueError(
            "alignment's characters do not reconstruct the submitted text -- "
            f"expected {len(text)} characters, alignment has {len(aligned_text)}"
        )

    total_duration = ends[-1] if ends else 0.0

    breaks = []
    for match in _BREAK_RE.finditer(text):
        i0, i1 = match.span()
        j = i0 - 1
        while j >= 0 and text[j] == " ":
            j -= 1
        pre_end = ends[j]
        k = i1
        while k < len(text) and text[k] == " ":
            k += 1
        post_start = starts[k] if k < len(text) else total_duration
        breaks.append((pre_end, post_start))

    bounds = []
    prev_end = 0.0
    for pre_end, post_start in breaks:
        bounds.append((prev_end, pre_end))
        prev_end = post_start
    bounds.append((prev_end, total_duration))

    if names is None:
        names = [f"beat{i + 1}" for i in range(len(bounds))]
    if len(names) != len(bounds):
        raise ValueError(
            f"names has {len(names)} entries but the text has {len(bounds)} "
            f"segments ({len(breaks)} break tags found)"
        )

    return [
        Segment(name=name, at=start, duration=end - start)
        for name, (start, end) in zip(names, bounds)
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_vo_alignment.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/vo_alignment.py stitcher/tests/test_vo_alignment.py
git commit -m "feat(stitcher): add vo_alignment -- exact segment boundaries from with-timestamps"
```

---

### Task 5: `stitcher.vo_split` — cut the single-take audio into per-segment files

**Files:**
- Create: `stitcher/stitcher/vo_split.py`
- Test: `stitcher/tests/test_vo_split.py`

**Interfaces:**
- Consumes: `stitcher.ffmpeg.run(args, log_path) -> str` (existing, `ffmpeg.py:136-174`);
  `stitcher.vo_alignment.Segment` (Task 4).
- Produces: `split_segments(source: Path, segments: list[Segment], out_dir: Path, log_path: Path) -> list[Path]`

- [ ] **Step 1: Write the failing tests**

Create `stitcher/tests/test_vo_split.py`:

```python
from pathlib import Path

from stitcher import vo_split as vs
from stitcher.vo_alignment import Segment


def test_split_segments_writes_one_file_per_segment_with_correct_trim_args(tmp_path, monkeypatch):
    calls = []

    def fake_run(args, log_path):
        calls.append(args)
        Path(args[-1]).write_bytes(b"wav")
        return ""

    monkeypatch.setattr(vs.ffmpeg, "run", fake_run)

    source = tmp_path / "single_take.mp3"
    source.write_bytes(b"src")
    out_dir = tmp_path / "segments"
    log_path = tmp_path / "log.txt"
    segments = [
        Segment(name="beat1", at=0.0, duration=5.538),
        Segment(name="beat2", at=6.142, duration=5.99),
    ]

    outputs = vs.split_segments(source, segments, out_dir, log_path)

    assert outputs == [out_dir / "beat1.wav", out_dir / "beat2.wav"]
    assert len(calls) == 2
    assert calls[0][calls[0].index("-ss") + 1] == "0.000000"
    assert calls[0][calls[0].index("-t") + 1] == "5.538000"
    assert calls[1][calls[1].index("-ss") + 1] == "6.142000"
    assert calls[1][calls[1].index("-t") + 1] == "5.990000"
    assert calls[0][calls[0].index("-ac") + 1] == "2"
    assert "pcm_s16le" in calls[0]
    for out_path in outputs:
        assert out_path.is_file()


def test_split_segments_creates_out_dir_if_missing(tmp_path, monkeypatch):
    def fake_run(args, log_path):
        Path(args[-1]).write_bytes(b"wav")
        return ""

    monkeypatch.setattr(vs.ffmpeg, "run", fake_run)

    source = tmp_path / "src.mp3"
    source.write_bytes(b"src")
    out_dir = tmp_path / "does" / "not" / "exist" / "yet"
    segments = [Segment(name="only", at=0.0, duration=1.0)]

    vs.split_segments(source, segments, out_dir, tmp_path / "log.txt")

    assert out_dir.is_dir()


def test_split_segments_empty_list_writes_nothing(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(vs.ffmpeg, "run", lambda args, log_path: calls.append(args))

    outputs = vs.split_segments(tmp_path / "src.mp3", [], tmp_path / "out", tmp_path / "log.txt")

    assert outputs == []
    assert calls == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd stitcher && python -m pytest tests/test_vo_split.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'stitcher.vo_split'`

- [ ] **Step 3: Write `vo_split.py`**

Create `stitcher/stitcher/vo_split.py`:

```python
"""Extract each Segment (stitcher.vo_alignment.Segment) from a single
continuous VO recording into its own audio file, via a plain ffmpeg trim --
no re-encoding decisions beyond the standard stitcher intermediate format
(pcm_s16le, 48kHz, stereo), matching precondition.py's own output
convention so condition_clip() can consume these files directly.
"""

from __future__ import annotations

from pathlib import Path

from . import ffmpeg
from .vo_alignment import Segment


def split_segments(
    source: Path,
    segments: list[Segment],
    out_dir: Path,
    log_path: Path,
) -> list[Path]:
    """Write one WAV file per segment to out_dir, named "<segment.name>.wav".
    Returns the output paths in the same order as `segments`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for segment in segments:
        out_path = out_dir / f"{segment.name}.wav"
        ffmpeg.run(
            [
                "ffmpeg", "-hide_banner", "-y",
                "-i", str(source),
                "-ss", f"{segment.at:.6f}",
                "-t", f"{segment.duration:.6f}",
                "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
                str(out_path),
            ],
            log_path,
        )
        outputs.append(out_path)
    return outputs
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_vo_split.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/vo_split.py stitcher/tests/test_vo_split.py
git commit -m "feat(stitcher): add vo_split -- cut a single-take VO into per-segment stems"
```

---

### Task 6: `stitcher.vo_timing` — exact captions, and rescaled shot/overlay timing

**Files:**
- Create: `stitcher/stitcher/vo_timing.py`
- Test: `stitcher/tests/test_vo_timing.py`

**Interfaces:**
- Consumes: `stitcher.spec.Caption` (existing, unchanged); `stitcher.vo_alignment.Segment` (Task 4).
- Produces: `derive_captions(segments: list[Segment], beat_texts: list[str]) -> list[Caption]`;
  `rescale_relative_spans(spans: list[tuple[float, float]], segment: Segment) -> list[tuple[float, float]]`

- [ ] **Step 1: Write the failing tests**

Create `stitcher/tests/test_vo_timing.py`:

```python
import pytest

from stitcher.vo_alignment import Segment
from stitcher.vo_timing import derive_captions, rescale_relative_spans


def test_derive_captions_spans_each_segment_exactly():
    segments = [
        Segment(name="beat1", at=0.0, duration=5.2),
        Segment(name="beat2", at=6.1, duration=4.0),
    ]
    captions = derive_captions(segments, ["First line.", "Second line."])

    assert len(captions) == 2
    assert captions[0].start == 0.0
    assert captions[0].end == 5.2
    assert captions[0].text == "First line."
    assert captions[1].start == 6.1
    assert captions[1].end == pytest.approx(10.1)
    assert captions[1].text == "Second line."


def test_derive_captions_mismatched_lengths_raises():
    segments = [Segment(name="beat1", at=0.0, duration=5.2)]
    with pytest.raises(ValueError, match="must be the same length"):
        derive_captions(segments, ["a", "b"])


def test_rescale_relative_spans_maps_fractions_onto_segment_window():
    segment = Segment(name="beat1", at=10.0, duration=6.0)
    spans = [(0.0, 0.5), (0.5, 1.0)]

    result = rescale_relative_spans(spans, segment)

    assert result == pytest.approx([(10.0, 13.0), (13.0, 16.0)])


def test_rescale_relative_spans_full_span_covers_whole_segment():
    segment = Segment(name="only", at=2.0, duration=4.0)
    result = rescale_relative_spans([(0.0, 1.0)], segment)
    assert result == pytest.approx([(2.0, 6.0)])


def test_rescale_relative_spans_out_of_order_fraction_raises():
    segment = Segment(name="only", at=0.0, duration=4.0)
    with pytest.raises(ValueError, match=r"0 <= start <= end <= 1"):
        rescale_relative_spans([(0.6, 0.4)], segment)


def test_rescale_relative_spans_fraction_out_of_bounds_raises():
    segment = Segment(name="only", at=0.0, duration=4.0)
    with pytest.raises(ValueError, match=r"0 <= start <= end <= 1"):
        rescale_relative_spans([(-0.1, 0.5)], segment)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd stitcher && python -m pytest tests/test_vo_timing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'stitcher.vo_timing'`

- [ ] **Step 3: Write `vo_timing.py`**

Create `stitcher/stitcher/vo_timing.py`:

```python
"""Turn a single-take VO's derived Segment boundaries into absolute timing
for the objects whose spans must never drift from the measured audio.

Two uses:
  - Caption spans map 1:1 onto segments (one caption per beat) -- exact,
    no further decision needed.
  - Shot/overlay cut timing is still shots.py's/visual-prompts' own cadence
    decision (how many cuts within a beat, and roughly where) -- but that
    decision can be expressed as fractions of a beat's OWN duration and
    mapped onto the beat's real, measured window here, instead of being
    authored against an estimated duration that can silently drift out of
    sync with the actual audio (docs/superpowers/plans/
    2026-08-19-vo-architecture-test-plan.md: the live render-spec.json was
    found 8.945s out of sync with its actual audio for exactly this reason).
"""

from __future__ import annotations

from .spec import Caption
from .vo_alignment import Segment


def derive_captions(segments: list[Segment], beat_texts: list[str]) -> list[Caption]:
    """One Caption per segment, spanning it exactly."""
    if len(segments) != len(beat_texts):
        raise ValueError(
            f"segments ({len(segments)}) and beat_texts ({len(beat_texts)}) "
            "must be the same length"
        )
    return [
        Caption(start=segment.at, end=segment.at + segment.duration, text=text)
        for segment, text in zip(segments, beat_texts)
    ]


def rescale_relative_spans(
    spans: list[tuple[float, float]], segment: Segment
) -> list[tuple[float, float]]:
    """Map beat-relative (start_fraction, end_fraction) pairs -- each in
    [0, 1], expressing where within ONE beat's own duration a shot or
    overlay begins/ends -- onto absolute render-timeline seconds, anchored
    to that beat's measured Segment.
    """
    for start_frac, end_frac in spans:
        if not (0.0 <= start_frac <= end_frac <= 1.0):
            raise ValueError(
                f"span ({start_frac}, {end_frac}) must satisfy "
                "0 <= start <= end <= 1"
            )
    return [
        (segment.at + start_frac * segment.duration, segment.at + end_frac * segment.duration)
        for start_frac, end_frac in spans
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_vo_timing.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/vo_timing.py stitcher/tests/test_vo_timing.py
git commit -m "feat(stitcher): add vo_timing -- exact captions and rescaled shot/overlay spans"
```

---

### Task 7: `stitcher.vo_assemble` — build the `Audio` spec from segments and conditioned stems

**Files:**
- Create: `stitcher/stitcher/vo_assemble.py`
- Test: `stitcher/tests/test_vo_assemble.py`

**Interfaces:**
- Consumes: `stitcher.spec.{Audio, Bed, Loudness, Stem}` (existing, unchanged);
  `stitcher.vo_alignment.Segment` (Task 4).
- Produces: `build_audio_config(segments, stem_files, bed_file, bed_gain_db, bed_duck_db, delivery_lufs, delivery_tp_dbtp) -> Audio`

- [ ] **Step 1: Write the failing tests**

Create `stitcher/tests/test_vo_assemble.py`:

```python
import pytest

from stitcher.vo_alignment import Segment
from stitcher.vo_assemble import build_audio_config


def test_builds_one_stem_per_segment_at_its_measured_offset():
    segments = [
        Segment(name="beat1", at=0.0, duration=5.5),
        Segment(name="beat2", at=6.2, duration=4.0),
    ]
    audio = build_audio_config(
        segments,
        stem_files=["beat1_conditioned.wav", "beat2_conditioned.wav"],
        bed_file="BedFull_conditioned.wav",
        bed_gain_db=-22.0,
        bed_duck_db=-29.0,
        delivery_lufs=-14.0,
        delivery_tp_dbtp=-1.0,
    )

    assert len(audio.stems) == 2
    assert audio.stems[0].id == "beat1"
    assert audio.stems[0].file == "beat1_conditioned.wav"
    assert audio.stems[0].at == 0.0
    assert audio.stems[0].gain_db == 0.0
    assert audio.stems[1].id == "beat2"
    assert audio.stems[1].at == 6.2


def test_bed_config_carries_through_with_no_windows_or_fades():
    segments = [Segment(name="only", at=0.0, duration=2.0)]
    audio = build_audio_config(
        segments, ["only.wav"], "bed.wav", bed_gain_db=-13.0, bed_duck_db=-18.0,
        delivery_lufs=-14.0, delivery_tp_dbtp=-1.0,
    )

    assert audio.bed.file == "bed.wav"
    assert audio.bed.gain_db == -13.0
    assert audio.bed.duck_db == -18.0
    assert audio.bed.windows == []
    assert audio.bed.fades == []


def test_loudness_carries_through():
    segments = [Segment(name="only", at=0.0, duration=1.0)]
    audio = build_audio_config(
        segments, ["only.wav"], "bed.wav", -22.0, -29.0,
        delivery_lufs=-14.0, delivery_tp_dbtp=-1.0,
    )
    assert audio.loudness.integrated_lufs == -14.0
    assert audio.loudness.true_peak_dbtp == -1.0


def test_mismatched_segments_and_stem_files_length_raises():
    segments = [Segment(name="a", at=0.0, duration=1.0), Segment(name="b", at=1.0, duration=1.0)]
    with pytest.raises(ValueError, match="must be the same length"):
        build_audio_config(segments, ["only_one.wav"], "bed.wav", -22.0, -29.0, -14.0, -1.0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd stitcher && python -m pytest tests/test_vo_assemble.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'stitcher.vo_assemble'`

- [ ] **Step 3: Write `vo_assemble.py`**

Create `stitcher/stitcher/vo_assemble.py`:

```python
"""Build a stitcher.spec.Audio object from a single-take VO's derived
segments (stitcher.vo_alignment.Segment) plus their conditioned stem files
and a bed configuration. Pure assembly -- no ffmpeg, no I/O beyond what the
caller already did (conditioning each segment via precondition.condition_clip
happens before this module runs, not inside it)."""

from __future__ import annotations

from .spec import Audio, Bed, Loudness, Stem
from .vo_alignment import Segment


def build_audio_config(
    segments: list[Segment],
    stem_files: list[str],
    bed_file: str,
    bed_gain_db: float,
    bed_duck_db: float,
    delivery_lufs: float,
    delivery_tp_dbtp: float,
) -> Audio:
    """segments and stem_files must be the same length and in the same
    order -- stem_files[i] is the conditioned audio file for segments[i]."""
    if len(segments) != len(stem_files):
        raise ValueError(
            f"segments ({len(segments)}) and stem_files ({len(stem_files)}) "
            "must be the same length"
        )
    stems = [
        Stem(id=segment.name, file=stem_file, at=segment.at, gain_db=0.0)
        for segment, stem_file in zip(segments, stem_files)
    ]
    bed = Bed(
        file=bed_file,
        gain_db=bed_gain_db,
        duck_db=bed_duck_db,
        windows=[],
        fades=[],
    )
    return Audio(
        stems=stems,
        bed=bed,
        sfx=[],
        loudness=Loudness(integrated_lufs=delivery_lufs, true_peak_dbtp=delivery_tp_dbtp),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_vo_assemble.py -v`
Expected: PASS (4 tests)

Run: `cd stitcher && python -m pytest tests/ -v`
Expected: PASS (every existing test plus all new ones from Tasks 4-7 — confirms no regression
anywhere in `stitcher`)

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/vo_assemble.py stitcher/tests/test_vo_assemble.py
git commit -m "feat(stitcher): add vo_assemble -- build Audio spec from segments and conditioned stems"
```

---

### Task 8: Document `<break>` tag support in the `elevenlabs-audio` skill

**Files:**
- Modify: `.claude/skills/elevenlabs-audio/references/model-routing.md`
- Modify: `.claude/skills/elevenlabs-audio/references/directorial-prompting.md`

**Interfaces:** None (documentation only). No test step — this task's "test" is the self-review
in Step 2.

- [ ] **Step 1: Add the `<break>` tag row and section to `model-routing.md`**

In `.claude/skills/elevenlabs-audio/references/model-routing.md`, find the feature-compatibility
matrix table (starts `| Feature | \`eleven_v3\` | \`eleven_multilingual_v2\` | \`eleven_flash_v2_5\` | \`eleven_flash_v2\` |`)
and add one row immediately after the `Audio tags` row:

```
| SSML `<break time="Xs" />` | no — use audio tags/punctuation instead | **yes** | **yes** | **yes** |
```

Then, immediately after the "### The two rows that trip people up" subsection and before the
"## Routing decisions" heading (both in this same `model-routing.md` file — "### The hard
constraint is the voice, not the list" is a *different* file, `directorial-prompting.md`, not a
valid anchor here), add a new subsection:

```markdown
### A third row, easy to miss the other direction: `<break>` is NOT a `eleven_v3` feature `[T]`

Unlike every other row in this matrix, `<break time="Xs" />` runs backwards from the rest of the
table: it works on `eleven_multilingual_v2`, `eleven_flash_v2`, and `eleven_flash_v2_5`, and does
**not** work on `eleven_v3` (v3 replaces it with bracketed audio tags and punctuation-based
pacing instead — a different, incompatible mechanism). Verified against ElevenLabs' own
help-center docs, 2026-08-19: max ~3s per break; a large number of breaks in one generation risks
documented instability (speech speeding up, added noise) — not observed at 7 breaks across ~950
characters in practice (`docs/superpowers/plans/2026-08-19-vo-architecture-test-plan.md` §6c).

No duration guarantee is documented, and none should be assumed: real measurement (same doc,
`/with-timestamps` ground truth) shows every break running long by roughly 50-210ms versus the
requested value, consistently in one direction. Confirm actual timing via `/with-timestamps`
rather than trusting the requested duration for anything timing-sensitive (shot cuts, caption
sync).
```

- [ ] **Step 2: Cross-reference in `directorial-prompting.md`**

In `.claude/skills/elevenlabs-audio/references/directorial-prompting.md`, immediately after the
"### Syntax rules" section (a level-3 heading, not level-2 — the new block below lands as its own
sibling section, not nested under it) and before "### Tags vs. the stability mode — the
contradiction to catch", add:

```markdown
### `[pause]` (a v3 audio tag) is not the only pause mechanism — and often not the right one

This file's tag catalog above includes `[pause]` as a documented delivery-control audio tag —
correct, but **`eleven_v3`-only**, like every other tag on this page. For `eleven_multilingual_v2`
or Flash (where audio tags render nothing at all — see `model-routing.md`'s feature matrix), the
actual pause mechanism is the SSML `<break time="Xs" />` tag, a completely different syntax
documented in `model-routing.md`'s "`<break>` is NOT a `eleven_v3` feature" section. Route to
whichever matches the chosen model — don't reach for `[pause]` on a non-v3 job; it will be
silently dropped, not converted.
```

Since this task touches only documentation and produces no code to test, self-review it directly:
read both edited sections back and confirm they render as valid Markdown, the row was inserted in
the right table position (columns aligned), and no existing content was altered besides the two
insertions.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/elevenlabs-audio/references/model-routing.md .claude/skills/elevenlabs-audio/references/directorial-prompting.md
git commit -m "docs(elevenlabs-audio): document <break> tag support on v2/Flash, not v3"
```

---

### Task 9: Record the `[P]` single-take architecture decision in `voiceover-brief`

**Files:**
- Create: `.claude/skills/voiceover-brief/references/single-take-architecture.md`
- Modify: `.claude/skills/voiceover-brief/SKILL.md` — a new reference file with no index entry
  and no workflow pointer is never read by anyone following this skill. `SKILL.md:111-122`'s
  "## Reference files" section is an explicit index (6 entries today) and `SKILL.md:56-83`'s
  numbered workflow steps each name the reference they route to — this task adds the file to both.

**Interfaces:** None (documentation only).

- [ ] **Step 1: Write the new reference file**

Create `.claude/skills/voiceover-brief/references/single-take-architecture.md`:

```markdown
# Single-take generation — the production default for this channel `[P]`

Markers: `[C]` corpus-cited `(Channel, video_id)` · `[I]` industry practice · `[T]` web-verified
tool/policy fact · **`[P]` project/operator decision** — a call made by this project's owner and
recorded here. `[P]` states what was decided, never why it is correct — never cite it as corpus
or vendor support for anything.

## The rule `[P]`

**Voiceover for this channel is generated as ONE continuous ElevenLabs call** — the full script,
beats joined with `<break time="Xs" />` tags (`elevenlabs-audio` skill,
`references/model-routing.md`) — rather than one call per beat. The resulting `/with-timestamps`
alignment (`docs/superpowers/plans/2026-08-19-single-take-vo-pipeline-implementation.md`) is the
one source of truth for stem placement, ducking, captions, and shot timing on every render.

Decided 2026-08-19, after direct comparison: the operator listened to both a per-beat-stitched
mix and a single-take mix of the same script and judged the single-take version clearly better —
not a measured quality claim, a listening judgment, recorded here as the reason this pipeline
exists, not as its justification.

## What this trades away — stated plainly, not silently

`docs/elevenlabs-voiceover-guide.md:96` `[T]`, citing `(Nick Nimmin, IF-PD6XMjYY)`:

> "Generate section-by-section. Don't render one giant block. Section-level generation lets you
> control pacing and re-roll a bad read cheaply — the same logic human narrators use when they
> record each line 2–3 times to have options in the edit."

This channel's own production history backs that reasoning directly: `VO1_provoice_take2.mp3` and
`VO7_provoice_take2.mp3` (the hook and CTA re-rolls from the render that motivated this decision)
are exactly the per-beat re-rolls the corpus describes. **Single-take generation gives that up.**
A flub anywhere in the script means regenerating the whole take — and because TTS is
non-deterministic, every other beat's audio comes out slightly different on a regenerate too,
so a partial fix is not available even in principle with this architecture.

This `[P]` decision overrides that corpus guidance **for this channel's production pipeline**,
on the operator's own judgment of the trade-off, not because the corpus's reasoning was wrong.

## What was verified, not just decided

- `[T]` (verified 2026-08-19) `<break time="Xs" />` works cleanly at 7 breaks across ~950
  characters — no speed-up artifact, no LRA collapse
  (`docs/superpowers/plans/2026-08-19-vo-architecture-test-plan.md` §6c, Call 1/2).
- `[T]` (verified 2026-08-19) `/with-timestamps` gives exact break-timing ground truth (median
  error 69ms, max 207ms across 7 real breaks) — eliminating the need to acoustically guess pause
  locations after the fact.
- `[I]` Splitting the single take at those exact measured boundaries back into per-stem files
  restores `stitcher`'s automatic ducking to its exact designed behavior (`envelope.level_at()`
  returned precisely `gain_db`/`duck_db`, a +7.00dB swing, confirmed directly against the envelope
  math, not inferred from noisy audio measurement) — same doc, §6c, "free follow-up" section. This
  one is this project's own engineering finding, not a vendor fact, hence `[I]` rather than `[T]`.

## Scope boundary

This is a **channel production-pipeline** decision, not a `voice-selection.md` or
`channel-voice.md` change — the pinned voice (`eDwT8Vhp2yxJzAMmuuPA`) and its rationale are
unaffected. It is also not a blanket recommendation for every ElevenLabs job this skill might
support in standalone mode (see `elevenlabs-audio`'s own scope note) — a one-off narration job
with no re-roll history and no downstream timing-derivation pipeline has no reason to adopt this.
```

- [ ] **Step 2: Wire the new file into `SKILL.md` so it's actually read**

In `.claude/skills/voiceover-brief/SKILL.md`'s "## Reference files" list (`SKILL.md:111-122`),
add a new bullet, placed right after the `channel-voice.md` entry (both are pinned,
architecture-level decisions for this channel, read early):

```markdown
- `references/single-take-architecture.md` — **the pinned production-pipeline architecture.**
  Read this alongside `channel-voice.md` — it decides whether the VO is generated per-beat or as
  a single continuous take, which changes how step 4 below applies to this channel.
```

Then, in workflow step 4 (`SKILL.md:73-77`, "Reformat the script text for TTS... Section the
script into TTS generation units... so bad takes can be re-rolled cheaply"), append a sentence at
the end of that step:

```markdown
   For this channel specifically, `references/single-take-architecture.md` supersedes the
   per-beat sectioning above with a `[P]` decision to generate as one continuous take instead —
   read it before applying this step here.
```

- [ ] **Step 3: Self-review**

Read both edited files back and confirm: the `[P]` line in `single-take-architecture.md` states a
decision, not a justification; the corpus's contrary position is quoted, not paraphrased into
agreement; the trade-off (re-roll granularity) is stated as a real cost, not minimized; and
`SKILL.md`'s two edits are the only changes to that file (no other content altered).

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/voiceover-brief/references/single-take-architecture.md .claude/skills/voiceover-brief/SKILL.md
git commit -m "docs(voiceover-brief): record the single-take architecture decision [P]"
```

---

### Task 10: Confirm the full test suites are green

**Files:** None — verification only.

- [ ] **Step 1: Run the `elevenlabs-tooling` suite**

Run: `cd elevenlabs-tooling && python -m pytest tests/ -v`
Expected: PASS, every test (pre-existing + Tasks 1-3's new tests)

- [ ] **Step 2: Run the `stitcher` suite**

Run: `cd stitcher && python -m pytest tests/ -v`
Expected: PASS, every test (367+ pre-existing + Tasks 4-7's new tests — no regression anywhere,
including in `precondition.py`'s suite from the prior plan)

- [ ] **Step 3: Run the repo-root suite**

Tasks 8-9 edit files under `.claude/skills/` — the repo-root suite (not either package's own
suite) is what guards skill provenance/contracts, and neither Task 10 Step 1 nor Step 2 exercises
it. Run: `python -m pytest tests/ -v` from the repo root
(`C:\Projects\ContentStudio\.claude\worktrees\elevenlabs-tooling-impl`).
Expected: PASS, every test (446 baseline + no regressions from Tasks 8-9's edits).

- [ ] **Step 4: Commit**

No files change in this task — if all three suites are green, proceed to Task 11 without a
commit. If any suite fails, STOP and report — do not proceed to the real API call in Task 11
against an unverified base.

---

### Task 11: Real end-to-end validation — full pipeline, one real API call

This task makes **exactly one** real, billed ElevenLabs API call. Everything else is real local
`ffmpeg`/`stitcher` execution — no other network calls, no additional spend.

**Files:**
- Create: `C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711\validate_single_take_pipeline.py`
  — lives under `stitcher/renders/`, excluded wholesale by `.gitignore:43` (`renders/`), never
  `git add`-ed, same reasoning as the prior plan's Task 5 harness.
- Create: `docs/superpowers/plans/2026-08-19-single-take-vo-pipeline-RESULTS.md` (committed).

**Interfaces:**
- Consumes: `elevenlabs_tooling.breaks.compose_break_tagged_text` (Task 1, called directly as a
  library function — no CLI invocation needed for text composition); the `generate-vo` CLI
  (Task 3, invoked via `subprocess` for the one real call); `stitcher.vo_alignment.derive_segments`
  (Task 4); `stitcher.vo_split.split_segments` (Task 5); `stitcher.vo_timing.derive_captions` /
  `rescale_relative_spans` (Task 6); `stitcher.vo_assemble.build_audio_config` (Task 7);
  `stitcher.precondition.condition_clip` (existing, from the prior audio-preconditioning plan);
  `stitcher.audio.build_audio` (existing); `stitcher.envelope.level_at`/`build_breakpoints`/
  `stem_spans` (existing, used to independently verify the ducking envelope, same method as the
  free follow-up test in `docs/superpowers/plans/2026-08-19-vo-architecture-test-plan.md` §6c).

- [ ] **Step 1: Compose the break-tagged script with refined break durations**

Refined durations (Global Constraints: real breaks overshoot 50-210ms, and a gap needs to clear
120ms attack + 400ms release = 520ms before the envelope reaches a true baseline plateau — the
prior test's 0.4-0.6s requests only barely cleared that, giving a 20-30ms audible plateau).

Create `elevenlabs-tooling/compose_payload.py` (throwaway, run once — it imports
**only** `elevenlabs_tooling`, never `stitcher`, keeping the package-boundary constraint intact.
Writes to an **absolute** path under the render directory, not a bare relative filename — Step 2's
CLI call and Step 3's harness both need to read from that exact same location).

**Unlike Task 11's harness script (which lives under `stitcher/renders/`, wholesale-excluded by
`.gitignore:43`), nothing in `.gitignore` covers `elevenlabs-tooling/*.py` at the package root —
`git add` would happily stage this file if run carelessly.** Delete it (or leave it untracked and
just never `git add` it) once Step 2 has run; do not commit it alongside Task 11's other output:

```python
"""One-time script: compose Task 11's break-tagged payload.json. Run from
the elevenlabs-tooling/ directory: `python compose_payload.py`.
"""

import json
from pathlib import Path

from elevenlabs_tooling.breaks import compose_break_tagged_text

RENDER_DIR = Path(
    r"C:/Projects/ContentStudio/stitcher/renders/stop-over-specialization-in-youth-sports-20260811-004711"
)

BEAT_TEXTS = [
    "The oldest warning about pushing your kid into one sport? 2,300 years old.",
    "Aristotle watched the ancient Olympics — and noticed the boy champions "
    "almost never won again as men.",
    "He blamed the early training. Push a young body that hard, and it burns the "
    "strength you were building.",
    "Here's the strange part.",
    "Jump forward 2,300 years — and the modern data agrees.",
    "Chundi and colleagues followed 2,556 NFL players in a 2026 study. The ones "
    "who played multiple sports had longer careers, and fewer injuries. Twelve "
    "more games. Nearly an extra season.",
    "So the kid who plays everything isn't falling behind. Even the researchers "
    "who pushed back agree. Göllich and colleagues showed playing many sports "
    "is what builds the athlete who lasts.",
    "That 2,300-year-old warning? The one-sport kid was never the safe bet.",
]
# 8 beats -> 7 inter-beat breaks. Index 3 (1.3s, the longest) sits at the
# re-hook turn, between "Here's the strange part." and "Jump forward...".
BREAK_SECONDS = [0.9, 0.8, 0.9, 1.3, 0.9, 0.8, 1.0]

composed_text = compose_break_tagged_text(BEAT_TEXTS, BREAK_SECONDS)

payload = {
    "text": composed_text,
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {
        "stability": 0.55,
        "similarity_boost": 0.80,
        "style": 0.30,
        "speed": 1.0,
        "use_speaker_boost": True,
    },
    "apply_text_normalization": "auto",
}

out_path = RENDER_DIR / "payload.json"
out_path.write_text(json.dumps(payload), encoding="utf-8")
print(f"wrote {out_path} ({len(composed_text)} characters)")
```

(Same voice settings as Call 1/2 — no formal lock exists on the pinned voice's card, per
`channel-voice.md`, so these remain the stated, explicit assumption.)

Run: `cd elevenlabs-tooling && python compose_payload.py`
Expected: prints `wrote ...payload.json (956 characters)` — 956 matches Call 1's real character
count exactly (`docs/superpowers/plans/2026-08-19-vo-architecture-test-plan.md` §6b).

- [ ] **Step 2: Make the one real API call via the `generate-vo` CLI**

Run from the `elevenlabs-tooling` directory, with `ELEVENLABS_API_KEY` set in the environment.
**All three file paths are the exact same absolute `RENDER_DIR` paths Step 1 wrote to and Step 3
reads from** -- never bare relative filenames, which would resolve against the current directory
(`elevenlabs-tooling/`) instead and silently misplace the billed output:

```bash
python -m elevenlabs_tooling generate-vo --payload "C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711\payload.json" --url "https://api.elevenlabs.io/v1/text-to-speech/eDwT8Vhp2yxJzAMmuuPA/with-timestamps?output_format=mp3_44100_192&enable_logging=true" --audio-output "C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711\single_take.mp3" --alignment-output "C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711\alignment.json"
```

Expected: exit code 0, `single_take.mp3` and `alignment.json` written directly into the render
directory (not `elevenlabs-tooling/`). If this fails for any
reason, STOP and report — do not retry against a different voice/model/payload without
understanding why first.

- [ ] **Step 3: Write and run the full pipeline harness**

One thing to know before running this: `derive_segments` (Task 4) asserts the alignment's
characters reconstruct the *exact submitted* text. `apply_text_normalization: "auto"` (Step 1's
payload) could in principle cause the alignment to reflect normalized text instead of the raw
submitted text, which would trip that assertion. Real evidence says this won't happen (§6c's
alignment data contains the literal `<break>` markup verbatim, meaning it tracks the raw submitted
text, not a normalized version) — noted here so a failure on that specific assertion has an
immediate, non-mysterious explanation rather than looking like a new bug. `payload.json` and
`single_take.mp3`/`alignment.json` are all saved to disk, so a Step 3 failure never requires
repeating Step 2's billed call to investigate.

Create `C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711\validate_single_take_pipeline.py`:

```python
"""Throwaway end-to-end validation harness for
docs/superpowers/plans/2026-08-19-single-take-vo-pipeline-implementation.md
Task 11. Lives under stitcher/renders/, gitignored, never staged.

Consumes the single_take.mp3 / alignment.json produced by Task 11 Step 2
(one real, already-spent API call -- this script makes no network calls of
its own). Runs the real, tested Tasks 4-7 modules plus the existing,
unmodified precondition.py/audio.py to produce a corrected mix and verify
this session's two real bugs (beat-to-beat/ducking collapse, and the
render-spec timing drift) are both fixed by construction.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(
    0,
    r"C:\Projects\ContentStudio\.claude\worktrees\elevenlabs-tooling-impl\stitcher",
)

from stitcher import audio as au
from stitcher import envelope
from stitcher import ffmpeg
from stitcher import precondition as pc
from stitcher.naming import Workspace
from stitcher.vo_alignment import derive_segments
from stitcher.vo_assemble import build_audio_config
from stitcher.vo_split import split_segments
from stitcher.vo_timing import derive_captions

RENDER_DIR = Path(
    r"C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711"
)
HARNESS_DIR = RENDER_DIR
SINGLE_TAKE_MP3 = HARNESS_DIR / "single_take.mp3"
ALIGNMENT_JSON = HARNESS_DIR / "alignment.json"
PAYLOAD_JSON = HARNESS_DIR / "payload.json"

CONDITION_LUFS = -14.0
CONDITION_TP_DBTP = -2.5
DELIVERY_LUFS = -14.0
DELIVERY_TP_DBTP = -1.0
BED_GAIN_DB = -22.0
BED_DUCK_DB = -29.0

BEAT_NAMES = ["beat1", "beat2", "beat3", "beat4a", "beat4b", "beat5", "beat6", "beat7"]
BEAT_TEXTS = [
    "The oldest warning about pushing your kid into one sport? 2,300 years old.",
    "Aristotle watched the ancient Olympics \u2014 and noticed the boy champions "
    "almost never won again as men.",
    "He blamed the early training. Push a young body that hard, and it burns the "
    "strength you were building.",
    "Here's the strange part.",
    "Jump forward 2,300 years \u2014 and the modern data agrees.",
    "Chundi and colleagues followed 2,556 NFL players in a 2026 study. The ones "
    "who played multiple sports had longer careers, and fewer injuries. Twelve "
    "more games. Nearly an extra season.",
    "So the kid who plays everything isn't falling behind. Even the researchers "
    "who pushed back agree. G\u00f6llich and colleagues showed playing many sports "
    "is what builds the athlete who lasts.",
    "That 2,300-year-old warning? The one-sport kid was never the safe bet.",
]


def main() -> None:
    payload = json.loads(PAYLOAD_JSON.read_text(encoding="utf-8"))
    submitted_text = payload["text"]
    # cmd_generate_vo (Task 3) writes json.dumps(result.alignment) directly --
    # the INNER alignment dict, not a wrapper with an "alignment" key. Do not
    # index into it.
    alignment = json.loads(ALIGNMENT_JSON.read_text(encoding="utf-8"))

    segments = derive_segments(submitted_text, alignment, names=BEAT_NAMES)
    print("Derived segments:")
    for seg in segments:
        print(f"  {seg.name}: at={seg.at:.3f} duration={seg.duration:.3f}")
    runtime = segments[-1].at + segments[-1].duration

    ws = Workspace(root=RENDER_DIR / "_single_take_validation", slug="run", mode="final")
    ws.ensure_dirs()
    log_path = ws.log_path("validate")

    raw_segments_dir = ws.asset("raw_segments")
    raw_paths = split_segments(SINGLE_TAKE_MP3, segments, raw_segments_dir, log_path)

    conditioned_files = []
    lra_deltas = {}
    for seg, raw_path in zip(segments, raw_paths):
        out_path = ws.asset(f"{seg.name}_conditioned.wav")
        result = pc.condition_clip(raw_path, CONDITION_LUFS, CONDITION_TP_DBTP, out_path, log_path)
        conditioned_files.append(out_path.name)
        lra_deltas[seg.name] = (
            result.input_measurement["input_lra"] - result.output_measurement["input_lra"]
        )
        print(
            f"{seg.name}: {result.input_measurement} -> {result.output_measurement} "
            f"(limited={result.limited}, peak_reduction_db={result.peak_reduction_db:.2f})"
        )

    # Reuse an already-conditioned bed from this session's earlier work --
    # _build_bed loops/trims it to whatever runtime is needed.
    bed_candidates = list(RENDER_DIR.rglob("BedFull_provoice_conditioned.wav"))
    if not bed_candidates:
        raise SystemExit("No conditioned bed file found from earlier this session -- cannot proceed.")
    bed_out = ws.asset("BedFull_conditioned.wav")
    shutil.copy2(bed_candidates[0], bed_out)
    print(f"Using bed source: {bed_candidates[0]}")

    audio_config = build_audio_config(
        segments, conditioned_files, "BedFull_conditioned.wav",
        BED_GAIN_DB, BED_DUCK_DB, DELIVERY_LUFS, DELIVERY_TP_DBTP,
    )

    captions = derive_captions(segments, BEAT_TEXTS)
    assert all(
        abs((c.end - c.start) - seg.duration) < 1e-9 for c, seg in zip(captions, segments)
    ), "captions must span their segment exactly"

    from stitcher.spec import Canvas, RenderSpec, SafeZone, Shot

    spec = RenderSpec(
        spec_version="1.0",
        slug="single-take-validation",
        canvas=Canvas(width=1080, height=1920, fps=30),
        safe_zone=SafeZone(x=90, y=380, width=900, height=1160),
        styles={},
        shots=[Shot(n=1, id="dummy", beat="dummy", start=0.0, end=runtime,
                     source="dummy.png", kind="still")],
        captions=captions,
        captions_style="dummy",
        audio=audio_config,
    )

    result = au.build_audio(spec, ws, "final", log_path, missing_audio=[])

    assert result.loudnorm["normalization_type"] == "linear", (
        f"linear-mode gate failed: {result.loudnorm}"
    )
    print("criteria 1-2 PASS: no exception raised, normalization_type == linear")

    remeasured = ffmpeg.measure_loudness(result.mix, log_path)
    assert abs(remeasured["input_i"] - DELIVERY_LUFS) <= 0.5, remeasured
    assert remeasured["input_tp"] <= DELIVERY_TP_DBTP, remeasured
    print(f"criterion 3 PASS: independent re-measurement of the written mix: {remeasured}")

    mean_lra_loss = sum(lra_deltas.values()) / len(lra_deltas)
    print(f"per-clip LRA loss: {lra_deltas}")
    print(f"mean LRA loss: {mean_lra_loss:.2f} LU (gate: <= 1.2)")
    assert mean_lra_loss <= 1.2, lra_deltas
    print("criterion 4 PASS: mean per-clip LRA loss within gate")

    # Per-clip loudness accuracy is already asserted inside condition_clip's
    # own retry loop -- nothing further to check here.

    # --- ducking check: query the real envelope math directly, same method
    # as the free follow-up test in the architecture-review doc §6c. Reuses
    # the actual Stem/Bed objects build_audio_config() already built --
    # no fabricated stand-ins. ---
    durations = {stem.file: seg.duration for stem, seg in zip(audio_config.stems, segments)}
    spans = envelope.stem_spans(audio_config.stems, durations)
    breakpoints = envelope.build_breakpoints(audio_config.bed, spans, runtime)

    # Check EVERY real gap between adjacent segments, not just the widest --
    # the narrowest gap is the meaningful test (the one most likely to fail
    # to reach true baseline before the next stem's attack ramp begins).
    mid_speech_t = (spans[-1][0] + spans[-1][1]) / 2  # middle of the last beat (beat7)
    speech_level = envelope.level_at(breakpoints, mid_speech_t)
    print(f"mid-speech level: {speech_level:.2f} dB")

    gaps = [(spans[i][1], spans[i + 1][0]) for i in range(len(spans) - 1)]
    for gap_start, gap_end in gaps:
        width = gap_end - gap_start
        sample_count = max(1, int(width / 0.01))
        peak = max(
            envelope.level_at(breakpoints, gap_start + i * (width / sample_count))
            for i in range(sample_count + 1)
        )
        delta = peak - speech_level
        print(f"gap {gap_start:.3f}-{gap_end:.3f}s (width {width:.3f}s): peak {peak:.2f} dB, delta {delta:+.2f} dB")
        assert abs(delta - (BED_GAIN_DB - BED_DUCK_DB)) <= 0.5, (
            f"ducking envelope did not reach baseline in the {gap_start:.3f}-{gap_end:.3f}s gap -- "
            f"got {delta:+.2f} dB, expected {BED_GAIN_DB - BED_DUCK_DB:+.1f} dB"
        )
    print("criterion 5 PASS: ducking envelope reaches baseline in every real gap")

    deliverable_dir = RENDER_DIR / "assets" / "provoice-2026-08-19"
    deliverable_dir.mkdir(parents=True, exist_ok=True)
    deliverable_wav = deliverable_dir / "Final_Mix_SingleTakePipeline.wav"
    shutil.copy2(result.mix, deliverable_wav)
    deliverable_mp3 = deliverable_dir / "Final_Mix_SingleTakePipeline.mp3"
    ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-y", "-i", str(result.mix),
         "-c:a", "libmp3lame", "-b:a", "192k", str(deliverable_mp3)],
        log_path,
    )
    print("All criteria passed.")
    print(f"WAV deliverable: {deliverable_wav}")
    print(f"MP3 deliverable: {deliverable_mp3}")
    print(f"Total runtime: {runtime:.3f}s")
    print(f"Captions (exact, derived from measured segments): {[(c.start, c.end, c.text[:30]) for c in captions]}")


if __name__ == "__main__":
    main()
```

Run: `python validate_single_take_pipeline.py` from the render directory.

Expected: the script runs to completion, printing `criteria 1-2 PASS`, `criterion 3 PASS`,
`criterion 4 PASS`, `criterion 5 PASS`, the two deliverable paths, and the exact caption spans.

If any assertion fails: STOP. Do not adjust `BED_GAIN_DB`/`BED_DUCK_DB`/any constant to force a
pass — a failure here is itself a finding (it would mean this specific script's timing broke an
assumption this plan made), and must be reported, not routed around.

- [ ] **Step 4: Listen to the delivered mix**

Play `Final_Mix_SingleTakePipeline.mp3` from `assets/provoice-2026-08-19/`. Compare by ear against
`Final_Mix_SingleTake.mp3` (this session's manually-assembled proof-of-concept) and
`Final_Mix_Preconditioned_DuckFix.wav` (the per-beat baseline). Confirm: single-take prosody
retained, bed audibly breathes in the gaps (not just mathematically), no clipping/leveling.

- [ ] **Step 5: Write the RESULTS doc**

Create `docs/superpowers/plans/2026-08-19-single-take-vo-pipeline-RESULTS.md`, following this
session's established format (see `2026-08-19-audio-preconditioning-implementation-RESULTS.md`):
outcome table against the 5 criteria, the real captured segment/caption timings and LRA numbers
from Step 3's stdout, the deliverable paths, and a closing **Status: pending user
listen-confirmation** line — updated only after the user has actually listened and said so.
**Use only numbers Step 3 actually printed.**

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/plans/2026-08-19-single-take-vo-pipeline-RESULTS.md
git commit -m "docs(single-take-vo): record the real end-to-end pipeline validation run"
```

(The harness script and `payload.json`/`single_take.mp3`/`alignment.json` are never `git add`-ed
— they live under `stitcher/renders/`, gitignored.)

---

## Self-Review

**Spec coverage:**
- Text composition with `<break>` tags — Task 1, using the real corpus of confirmed model
  support (`elevenlabs-audio` skill, Task 8).
- `/with-timestamps` HTTP call, correctly handling its JSON-with-embedded-audio shape (not
  `send()`'s raw-audio-body shape) — Tasks 2-3.
- Exact segment-boundary derivation from real alignment data — Task 4, tested against a fixture
  that reproduces the real observed structure (break markup collapsing to zero-width, verified
  this session).
- Splitting the single take into real per-segment stems — Task 5.
- Captions deriving exactly from measured segments (the fix for the live 8.945s drift bug found
  this session) and a reusable mechanism for shot/overlay timing to do the same — Task 6.
- Building a real `Audio` spec from conditioned stems — Task 7, reusing `precondition.py`
  unchanged.
- The `elevenlabs-audio` skill's documentation gap (only v3's `[pause]` tag documented, not the
  `<break>` tag that actually applies to this channel's model) — Task 8.
- The `[P]` architecture decision, corpus trade-off stated honestly — Task 9.
- Full-suite regression check before spending anything — Task 10.
- Real, one-call, end-to-end proof against the actual render, checking all 5 success criteria
  (linear mode, re-measured loudness, LRA gate, and — new — the ducking envelope reaching exact
  baseline in a real gap, verified the same way this session's free follow-up test did) — Task 11.

**Placeholder scan:** no TBD/TODO; every code block is complete, runnable code. Task 11's
`payload.json`/`single_take.mp3`/`alignment.json` are the one place content is genuinely not
knowable until Step 2's real API call runs — framed as such, not invented.

**Type consistency:** `Segment(name, at, duration)` is identical across Tasks 4-7 and 11.
`derive_segments(text, alignment, names=None) -> list[Segment]`,
`split_segments(source, segments, out_dir, log_path) -> list[Path]`,
`derive_captions(segments, beat_texts) -> list[Caption]`,
`rescale_relative_spans(spans, segment) -> list[tuple[float, float]]`,
`build_audio_config(segments, stem_files, bed_file, bed_gain_db, bed_duck_db, delivery_lufs, delivery_tp_dbtp) -> Audio`
are referenced with the same signature everywhere they appear, including Task 11's real harness.
`TimestampsResult{ok, status_code, audio_bytes, alignment, error_message}` matches between Task 2's
implementation, its own tests, and Task 3's CLI consumption.

---

## Execution Handoff

Plan complete and saved to
`docs/superpowers/plans/2026-08-19-single-take-vo-pipeline-implementation.md`. Two execution
options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks,
fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution
with checkpoints

**Which approach?**
