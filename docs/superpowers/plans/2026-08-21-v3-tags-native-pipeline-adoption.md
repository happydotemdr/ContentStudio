# V3-Tags Native-Pipeline Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt `eleven_v3` + bracket audio tags (not per-beat numeric speed/style variation) as this project's voice-generation approach, and extend the already-built `native_pipeline` single-take timing infrastructure — currently wired only for the older `eleven_multilingual_v2` + `<break>`-tag path — to support it, so real measured ElevenLabs timestamps (not estimated script seconds) drive caption timing, shot-cut timing, and the music bed.

**Architecture:** No new system is being built. `stitcher/stitcher/vo_alignment.py`, `vo_timing.py`, and the `native_pipeline` package (`orchestrate.py`, `shots.py`, `music_plan.py`, `assemble.py`) already implement exactly this — real `/with-timestamps` alignment → per-beat `Segment` objects → captions with exact timing → shot-cut timing anchored to real audio → a music composition plan keyed to real segment/gap durations → a `RenderSpec`. It was built and validated (44 passing tests, one real end-to-end test) for scripts composed with SSML `<break>` tags on `eleven_multilingual_v2`. Today's live experimentation (this session) found that approach produces audibly inconsistent, "AI-sounding" delivery from per-beat numeric speed/style variation, and that a single continuous `eleven_v3` generation using bracket audio tags (`[excited]`, `[whispers]`, `[sighs]`, `[pause]`, applied only where they genuinely fit — not on every beat) sounds dramatically more natural. `eleven_v3` has no `<break>` tag, so the existing segment-boundary-recovery code (which splits on `<break>` markers) cannot be reused as-is. This plan adds a v3-compatible sibling to the two places that assume `<break>`, corrects three live-API behaviors this session discovered are wrong in this project's own reference docs, updates the pinned voice decision to route to `eleven_v3`, and regenerates this run's actual voiceover through the corrected pipeline.

**Tech Stack:** Python 3, pytest, `stitcher` package (existing), `elevenlabs-tooling` package (existing), `native_pipeline` package (existing), ElevenLabs `/v1/text-to-speech/{voice_id}/with-timestamps` API.

## Global Constraints

- `stitcher` imports nothing from `pipeline_app`, `elevenlabs_tooling`, or `native_pipeline`; `elevenlabs_tooling` imports nothing from `stitcher`; only `native_pipeline` is allowed to import both. Dependency arrows point outward from `native_pipeline` only — never add an import that violates this (`native-pipeline/README.md` and the 2026-08-20 design spec's "Architecture" section).
- The native single-generation mode does **no VO processing** — no `precondition.condition_clip` call, no per-beat split via `vo_split.py`. The raw ElevenLabs take is the final voice track; its LUFS is measured, never modified, for the bed's relative-gain calculation and outlier flagging. This is an explicit, already-made design decision (2026-08-20 design doc, "Decisions" — "VO processing: none") — do not reintroduce per-beat conditioning for this mode.
- Every new exception class follows the existing one-or-two-per-module pattern (`FFmpegError`, `PreconditionError`, `ShotSegmentMismatchError`, etc.) — never a shared umbrella exception.
- Tests use only this repo's existing pytest markers — `e2e`, `allow_network`, `allow_subprocess` — never an invented marker name. A test using `allow_network`/`allow_subprocess` must justify it in its own docstring.
- Each package's test suite runs from its own directory (`stitcher/pytest.ini`, `native-pipeline/pytest.ini`, `elevenlabs-tooling/pytest.ini` each set `pythonpath`) — `python -m pytest` from inside that package's own directory, never from the repo root or another package's directory.
- Any new normative line added to a `.claude/skills/**/references/*.md` file needs a `[C]`/`[I]`/`[T]`/`[P]`/`[T-unverified]` marker per this repo's anti-generic-content discipline (`CLAUDE.md` "Anti-generic guarantee").
- A billed real-API call (ElevenLabs TTS/with-timestamps/Forced Alignment) must never run inside the default `pytest` collection — every such test is marked `e2e` and skips itself when `ELEVENLABS_API_KEY` is unset, matching `native-pipeline/pytest.ini`'s `addopts = -m "not e2e"`.

---

### Task 1: Live-verify `/with-timestamps` on `eleven_v3` with bracket tags, capture a real fixture

**Files:**
- Modify: `native-pipeline/tests/test_e2e.py`
- Create (at test-run time, not by hand): `stitcher/tests/fixtures/v3_tags_alignment_sample.json`

**Interfaces:**
- Consumes: `elevenlabs_tooling.client.send_with_timestamps(url, payload_bytes, api_key)` (existing, unmodified) → `TimestampsResult(ok, status_code, audio_bytes, alignment, error_message)`.
- Produces: a real, captured ElevenLabs `/with-timestamps` response for `eleven_v3` + bracket tags, in the exact `{"characters": [...], "character_start_times_seconds": [...], "character_end_times_seconds": [...]}` shape, saved to `stitcher/tests/fixtures/v3_tags_alignment_sample.json` as `{"text": ..., "alignment": ...}`. Task 2's tests read this file.

This is a spike, not new production code — its deliverable is verified, real ground truth (three things this session already found wrong in this project's own reference docs by testing live: `stability` as the string `"natural"` is rejected by the API with a 422 wanting a float instead; `eleven_v3` rejects `previous_text`/`next_text` outright; and a bracket-tag's own characters collapse to a near-zero-duration cluster in a Forced Alignment response — this task confirms whether that same collapse behavior holds on `/with-timestamps` specifically, which is the endpoint the real pipeline actually uses).

- [ ] **Step 1: Add the live-verification test**

Add to `native-pipeline/tests/test_e2e.py` (alongside the existing `<break>`-based `test_native_pipeline_end_to_end`, which stays unmodified):

```python
from elevenlabs_tooling.client import send_with_timestamps

VO_URL_V3 = "https://api.elevenlabs.io/v1/text-to-speech/eDwT8Vhp2yxJzAMmuuPA/with-timestamps"

V3_TAG_BEAT_TEXTS = [
    "[excited] This is the first beat of a real v3 tags test.",
    "So here's the second beat, after a real pause.",
]

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "stitcher" / "tests" / "fixtures"
    / "v3_tags_alignment_sample.json"
)


def test_v3_with_timestamps_returns_expected_alignment_shape():
    """Live spike: confirms /with-timestamps on eleven_v3, with bracket audio
    tags in the text and NO previous_text/next_text (eleven_v3 rejects those
    with a 422 -- "Providing previous_text or next_text is not yet supported
    with the 'eleven_v3' model", verified live 2026-08-21), returns the same
    characters/character_start_times_seconds/character_end_times_seconds
    parallel-array shape stitcher.vo_alignment.derive_segments already
    consumes for the <break>-tagged path. Captures the real response to
    stitcher/tests/fixtures/v3_tags_alignment_sample.json so
    derive_segments_v3's unit tests (Task 2) can assert against real
    ElevenLabs output, not only synthetic data. Costs a few cents of
    ElevenLabs credit (a ~110-character eleven_v3 generation)."""
    if not os.environ.get("ELEVENLABS_API_KEY"):
        pytest.skip("ELEVENLABS_API_KEY not set")

    text = "\n\n".join(V3_TAG_BEAT_TEXTS)
    payload = json.dumps({
        "text": text,
        "model_id": "eleven_v3",
        "voice_settings": {
            # float, NOT the string "natural" -- eleven_v3's /text-to-speech
            # rejects a string stability with a 422 (verified live, 2026-08-21;
            # see channel-voice.md)
            "stability": 0.5,
            "similarity_boost": 0.80,
            "style": 0.0,
            "speed": 1.0,
            "use_speaker_boost": True,
        },
        "seed": 20260821,
        "apply_text_normalization": "auto",
        # deliberately no previous_text/next_text -- eleven_v3 rejects them
    }).encode("utf-8")

    result = send_with_timestamps(VO_URL_V3, payload, os.environ["ELEVENLABS_API_KEY"])
    assert result.ok, result.error_message

    alignment = result.alignment
    assert set(alignment.keys()) >= {
        "characters", "character_start_times_seconds", "character_end_times_seconds",
    }
    chars = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]
    assert len(chars) == len(starts) == len(ends)
    assert "".join(chars) == text

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(
        json.dumps({"text": text, "alignment": alignment}, indent=2),
        encoding="utf-8",
    )
```

Add `pytestmark = [pytest.mark.e2e, pytest.mark.allow_network]` if not already module-level (it already is, from the existing test — reuse it, don't duplicate).

- [ ] **Step 2: Run it for real and confirm the fixture was captured**

Run: `cd native-pipeline && python -m pytest -m e2e -k test_v3_with_timestamps -v`
Expected: PASS, and `stitcher/tests/fixtures/v3_tags_alignment_sample.json` now exists. Open it and confirm the bracket tag's characters (`[`, `e`, `x`, `c`, `i`, `t`, `e`, `d`, `]`) share a single (or near-identical) timestamp cluster, the same collapse pattern this session already observed via Forced Alignment. If they do **not** collapse the same way, stop and re-read the captured fixture before writing Task 2 — its exact structure, not this plan's prediction, is what Task 2 must match.

- [ ] **Step 3: Commit**

```bash
git add native-pipeline/tests/test_e2e.py stitcher/tests/fixtures/v3_tags_alignment_sample.json
git commit -m "test: capture real eleven_v3 /with-timestamps alignment for bracket tags"
```

---

### Task 2: `stitcher/stitcher/vo_alignment.py` — add `derive_segments_v3`

**Files:**
- Modify: `stitcher/stitcher/vo_alignment.py`
- Test: `stitcher/tests/test_vo_alignment.py`

**Interfaces:**
- Consumes: the `alignment` dict shape confirmed by Task 1 (`characters`/`character_start_times_seconds`/`character_end_times_seconds` parallel arrays); `Segment` (existing dataclass, unchanged: `name: str, at: float, duration: float`).
- Produces: `derive_segments_v3(text: str, alignment: dict, beat_texts: list[str], names: list[str] | None = None) -> list[Segment]` — consumed by Task 5's `orchestrate.run_vo_stage`.

- [ ] **Step 1: Write the failing tests**

Add to `stitcher/tests/test_vo_alignment.py`:

```python
import json
from pathlib import Path

from stitcher.vo_alignment import derive_segments_v3

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "v3_tags_alignment_sample.json"


def _build_v3_case(beat_texts):
    """Build (text, alignment) for beats joined by a blank line ("\\n\\n"),
    mirroring the REAL structure captured in v3_tags_alignment_sample.json
    (Task 1): plain real text advances the clock by CHAR_DUR per character;
    no bracket tag appears in this helper's own cases (see
    test_bracket_tag_is_excluded_from_segment_timing for that shape)."""
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

    for i, beat in enumerate(beat_texts):
        if i > 0:
            emit_real("\n\n")
        emit_real(beat)

    text = "\n\n".join(beat_texts)
    alignment = {
        "characters": chars,
        "character_start_times_seconds": starts,
        "character_end_times_seconds": ends,
    }
    assert len(chars) == len(text)
    return text, alignment


def test_two_beats_no_tags_recovers_correct_segment_boundaries():
    beat1, beat2 = "Hi there.", "Bye now."
    text, alignment = _build_v3_case([beat1, beat2])

    segments = derive_segments_v3(text, alignment, [beat1, beat2])

    assert len(segments) == 2
    assert segments[0].name == "beat1"
    assert segments[0].at == 0.0
    assert segments[0].duration == pytest.approx(len(beat1) * 0.1)
    assert segments[1].name == "beat2"
    gap_start = (len(beat1) + 2) * 0.1  # beat1 + the 2-char "\n\n" separator
    assert segments[1].at == pytest.approx(gap_start)
    assert segments[1].duration == pytest.approx(len(beat2) * 0.1)


def test_bracket_tag_is_excluded_from_segment_timing():
    """A tag's characters collapse to a single zero-duration instant (the
    real collapse pattern Task 1 confirmed against a live /with-timestamps
    response) -- the segment's `at` must be the first REAL character's
    start time, not the tag's."""
    CHAR_DUR = 0.1
    chars, starts, ends = [], [], []
    clock = 0.0
    for ch in "[excited] ":  # tag + its trailing space, all zero-width
        chars.append(ch)
        starts.append(clock)
        ends.append(clock)
    beat = "Real words start here."
    for ch in beat:
        chars.append(ch)
        starts.append(round(clock, 4))
        clock = round(clock + CHAR_DUR, 4)
        ends.append(clock)
    text = "[excited] " + beat
    alignment = {"characters": chars, "character_start_times_seconds": starts,
                 "character_end_times_seconds": ends}

    segments = derive_segments_v3(text, alignment, [text])

    assert segments[0].at == 0.0
    assert segments[0].duration == pytest.approx(len(beat) * 0.1)


def test_paragraph_count_mismatch_raises():
    text, alignment = _build_v3_case(["A.", "B."])
    with pytest.raises(ValueError, match="2 paragraph"):
        derive_segments_v3(text, alignment, ["A.", "B.", "C."])


def test_beat_text_mismatch_raises():
    text, alignment = _build_v3_case(["A.", "B."])
    with pytest.raises(ValueError, match="expected beat text"):
        derive_segments_v3(text, alignment, ["A.", "Different."])


def test_custom_names_are_used_in_order():
    text, alignment = _build_v3_case(["A beat.", "Another beat."])
    segments = derive_segments_v3(text, alignment, ["A beat.", "Another beat."],
                                   names=["hook", "cta"])
    assert [s.name for s in segments] == ["hook", "cta"]


def test_all_tag_no_real_text_raises():
    text = "[pause]"
    alignment = {
        "characters": list(text),
        "character_start_times_seconds": [0.0] * len(text),
        "character_end_times_seconds": [0.0] * len(text),
    }
    with pytest.raises(ValueError, match="no real spoken text"):
        derive_segments_v3(text, alignment, [text])


@pytest.mark.skipif(
    not FIXTURE_PATH.is_file(),
    reason="run native-pipeline's e2e test (-m e2e) first to capture "
    "v3_tags_alignment_sample.json (Task 1)",
)
def test_real_captured_v3_alignment_recovers_two_segments():
    """Grounds this function against a REAL ElevenLabs /with-timestamps
    response. Beat texts here must stay byte-identical to
    native-pipeline/tests/test_e2e.py's V3_TAG_BEAT_TEXTS constant (Task 1)."""
    recorded = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    beat_texts = [
        "[excited] This is the first beat of a real v3 tags test.",
        "So here's the second beat, after a real pause.",
    ]
    segments = derive_segments_v3(recorded["text"], recorded["alignment"], beat_texts)
    assert len(segments) == 2
    assert segments[0].at == pytest.approx(0.0, abs=0.2)
    assert segments[1].at > segments[0].at + segments[0].duration
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd stitcher && python -m pytest tests/test_vo_alignment.py -v`
Expected: FAIL with `ImportError: cannot import name 'derive_segments_v3'`.

- [ ] **Step 3: Implement `derive_segments_v3`**

Add to `stitcher/stitcher/vo_alignment.py` (below the existing `derive_segments`; `import re` and the `Segment` dataclass already exist in this file — no new imports needed):

```python
_TAG_RE = re.compile(r'\[[^\]]*\]')


def _is_real_text_index(text: str, i: int, tag_spans: list[tuple[int, int]]) -> bool:
    if text[i].isspace():
        return False
    return not any(start <= i < end for start, end in tag_spans)


def derive_segments_v3(
    text: str, alignment: dict, beat_texts: list[str], names: list[str] | None = None
) -> list[Segment]:
    """Split `text` on its "\\n\\n" paragraph breaks -- the composition
    convention elevenlabs_tooling.tags.compose_tagged_text uses for a
    single continuous eleven_v3 generation -- and return one Segment per
    beat, with `at`/`duration` taken from real (non-tag, non-whitespace)
    character timestamps in `alignment`.

    Unlike derive_segments (the <break>-tagged path for
    eleven_multilingual_v2/flash), eleven_v3 has no <break> mechanism --
    beats are separated by bracket audio tags like [excited]/[whispers] and
    plain paragraph structure instead. Verified against a real ElevenLabs
    /with-timestamps response (stitcher/tests/fixtures/
    v3_tags_alignment_sample.json, captured 2026-08-21): a bracket tag's own
    characters collapse to a near-zero-duration cluster at the instant the
    tag "fires," the same way a <break> tag's markup characters do -- so a
    beat's real `at`/end are the first/last REAL (non-tag, non-whitespace)
    character's timestamps within that beat's own paragraph, not the
    paragraph's raw start/end index.

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

    pieces = text.split("\n\n")
    if len(pieces) != len(beat_texts):
        raise ValueError(
            f"text splits into {len(pieces)} paragraph(s) on a blank line but "
            f"{len(beat_texts)} beat_texts were supplied -- these must match"
        )
    for index, (piece, expected) in enumerate(zip(pieces, beat_texts)):
        if piece != expected:
            raise ValueError(
                f"paragraph {index} is {piece!r} but the expected beat text at "
                f"that position is {expected!r}"
            )

    if names is None:
        names = [f"beat{i + 1}" for i in range(len(pieces))]
    if len(names) != len(pieces):
        raise ValueError(
            f"names has {len(names)} entries but the text has {len(pieces)} paragraphs"
        )

    tag_spans = [match.span() for match in _TAG_RE.finditer(text)]

    segments = []
    offset = 0
    for name, piece in zip(names, pieces):
        real_indices = [
            i for i in range(offset, offset + len(piece))
            if _is_real_text_index(text, i, tag_spans)
        ]
        if not real_indices:
            raise ValueError(
                f"paragraph {piece!r} (segment {name!r}) has no real spoken "
                "text -- every character is a bracket tag or whitespace"
            )
        at = starts[real_indices[0]]
        end = ends[real_indices[-1]]
        segments.append(Segment(name=name, at=at, duration=end - at))
        offset += len(piece) + 2  # skip the "\n\n" separator

    return segments
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_vo_alignment.py -v`
Expected: PASS (the real-fixture test passes if Task 1 ran; otherwise it's skipped, not failed).

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/vo_alignment.py stitcher/tests/test_vo_alignment.py
git commit -m "feat(stitcher): add derive_segments_v3 for bracket-tagged eleven_v3 scripts"
```

---

### Task 3: `elevenlabs-tooling/elevenlabs_tooling/tags.py` — add `compose_tagged_text`

**Files:**
- Create: `elevenlabs-tooling/elevenlabs_tooling/tags.py`
- Test: `elevenlabs-tooling/tests/test_tags.py`

**Interfaces:**
- Produces: `compose_tagged_text(beats: list[str], beat_tags: list[str | None]) -> str` — consumed by Task 6 (building this run's real payload) and by any future script authoring for the v3-tags path. Its `"\n\n"` join convention **must** match `derive_segments_v3`'s split convention (Task 2) exactly — the two are a matched pair.

- [ ] **Step 1: Write the failing tests**

Create `elevenlabs-tooling/tests/test_tags.py`:

```python
import pytest

from elevenlabs_tooling.tags import compose_tagged_text


def test_composes_two_beats_one_tagged_one_not():
    result = compose_tagged_text(
        ["Eight grand a year.", "Why?"], ["[excited]", "[whispers]"]
    )
    assert result == "[excited] Eight grand a year.\n\n[whispers] Why?"


def test_beat_with_none_tag_gets_no_bracket_prefix():
    result = compose_tagged_text(["Plain beat.", "Tagged beat."], [None, "[curious]"])
    assert result == "Plain beat.\n\n[curious] Tagged beat."


def test_stacked_tags_pass_through_as_one_string():
    result = compose_tagged_text(["Why?"], ["[pause][whispers]"])
    assert result == "[pause][whispers] Why?"


def test_single_beat_no_tag():
    assert compose_tagged_text(["Only one beat."], [None]) == "Only one beat."


def test_wrong_tag_count_raises():
    with pytest.raises(ValueError, match="exactly 2 entries"):
        compose_tagged_text(["A", "B"], ["[x]"])


def test_empty_beats_list_raises():
    with pytest.raises(ValueError, match="at least one beat"):
        compose_tagged_text([], [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_tags.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'elevenlabs_tooling.tags'`.

- [ ] **Step 3: Implement `compose_tagged_text`**

Create `elevenlabs-tooling/elevenlabs_tooling/tags.py`:

```python
"""Compose bracket-audio-tag script text for a single continuous
eleven_v3 TTS generation.

Bracket audio tags ([excited], [whispers], [sighs], [pause], etc.) are
supported on eleven_v3 only -- NOT eleven_multilingual_v2, eleven_flash_v2,
or eleven_flash_v2_5 (breaks.py's compose_break_tagged_text is those
models' equivalent mechanism, using SSML <break> instead). eleven_v3 has no
<break> tag at all (verified against ElevenLabs' own help-center docs,
2026-08-19, and confirmed live 2026-08-21: eleven_v3 replaces <break> with
bracketed audio tags and punctuation-based pacing).

Beats are joined with a blank line ("\\n\\n"), matching
stitcher.vo_alignment.derive_segments_v3's own paragraph-split convention --
the two must stay in lockstep: derive_segments_v3 recovers segment
boundaries by splitting the submitted text on the exact same separator.
"""

from __future__ import annotations


def compose_tagged_text(beats: list[str], beat_tags: list[str | None]) -> str:
    """Join `beats` with a blank line between each pair, prefixing each
    beat with its bracket tag(s) -- a literal string like "[excited]" or a
    stacked "[pause][whispers]" -- or leaving it untagged when
    `beat_tags[i]` is None. Not every beat needs a tag: per this project's
    anti-invention discipline, a beat with no genuinely-fitting catalog tag
    should get None here and rely on punctuation alone, rather than an
    invented tag presented as known-good.

    len(beat_tags) must equal len(beats).
    """
    if len(beats) < 1:
        raise ValueError("beats must contain at least one beat")
    if len(beat_tags) != len(beats):
        raise ValueError(
            f"beat_tags must have exactly {len(beats)} entries (one per beat), "
            f"got {len(beat_tags)}"
        )
    pieces = [f"{tag} {beat}" if tag else beat for beat, tag in zip(beats, beat_tags)]
    return "\n\n".join(pieces)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_tags.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add elevenlabs-tooling/elevenlabs_tooling/tags.py elevenlabs-tooling/tests/test_tags.py
git commit -m "feat(elevenlabs-tooling): add compose_tagged_text for eleven_v3 scripts"
```

---

### Task 4: Re-pin the channel voice to `eleven_v3`, correct the live-API discrepancies

**Files:**
- Modify: `.claude/skills/voiceover-brief/references/channel-voice.md`
- Modify: `.claude/skills/elevenlabs-audio/references/model-routing.md`
- Modify: `.claude/skills/elevenlabs-audio/references/api-payload.md`
- Modify: `.claude/skills/elevenlabs-audio/references/voice-settings.md`

**Interfaces:** None (documentation only). "Test" is the project's own doc-truth/provenance suite.

This supersedes the routing decision made earlier **today** (2026-08-21) — the file already records that decision as `[P]`; this task records the reversal the same way, with the reason (a live-listening comparison this session, not a hypothesis).

- [ ] **Step 1: Update `channel-voice.md`'s routing decision**

Replace the `Model:` line and the `Caveats:` line in the card, and the "Resolved 2026-08-21" language, with:

```
  Model:            eleven_v3, single continuous generation per Short (not
                     per-beat chunking) — operator decision 2026-08-21,
                     REVISING the earlier same-day decision below after a
                     live listening comparison. Bracket audio tags
                     ([excited], [whispers], [sighs], [pause], etc.) carry
                     delivery, applied only where they genuinely fit — not
                     every beat needs one. No per-beat numeric
                     speed/style variation: a single constant
                     stability/similarity_boost/style/speed baseline
                     across the whole take. [P]
```

And replace the "Caveats" line with:

```
Caveats:           SUPERSEDED 2026-08-21 [P]: the same-day "always
                   eleven_multilingual_v2 for full PVC fidelity" decision
                   below was tested against a v3+tags alternative in a
                   live side-by-side comparison and the v3+tags result was
                   judged clearly better — more natural intonation, no
                   audible per-segment "AI-ish" discontinuity. The
                   multilingual_v2 decision's own reasoning (PVC fidelity
                   loss on v3) is real but was outweighed in practice.
                   Three eleven_v3 API behaviors this session found
                   undocumented or mis-documented, now load-bearing for
                   this pin:
                   1. eleven_v3's /text-to-speech (and /with-timestamps)
                      REJECTS voice_settings.stability as the string
                      "natural" — 422 "Input should be a valid number" —
                      despite this skill's own model-routing.md/
                      api-payload.md describing string mode names. Send a
                      float (Natural ≈ 0.5) instead. [T]
                   2. eleven_v3 REJECTS previous_text/next_text outright —
                      400 "Providing previous_text or next_text is not yet
                      supported with the 'eleven_v3' model" — so a
                      single-take generation has no request-level
                      stitching context to lose in the first place; this
                      is a non-issue for the single-continuous-take
                      approach specifically.
                   3. eleven_v3 has no <break> tag (already correctly
                      documented elsewhere in this skill) — bracket tags
                      and punctuation carry pacing instead.
```

- [ ] **Step 2: Correct `elevenlabs-audio/references/model-routing.md`**

Find the feature-compatibility matrix row `| Discrete stability modes |` and the surrounding v3 stability-mode prose. Add a note directly beneath the matrix:

```
**Live-API correction, 2026-08-21** `[T]`: the discrete Creative/Natural/Robust
mode NAMES are a documented UI/prompting concept, but eleven_v3's actual
`/text-to-speech` (and `/with-timestamps`) request body rejects a string
value for `voice_settings.stability` with a 422. Send a float in [0, 1]
(Natural ≈ 0.5) regardless of which named mode you intend. This corrects
this file's and `api-payload.md`'s prior guidance to send a mode string.
```

Also find the `previous_text`/`next_text` prose under "Chunking & stitching" (in `api-payload.md`, cross-referenced from here) and add: `eleven_v3 currently rejects previous_text/next_text outright with a 400 (verified live 2026-08-21) — this is moot for a single continuous generation, which has no chunk seams to stitch, but blocking if anyone still chunks a v3 script into multiple requests.`

- [ ] **Step 3: Correct `elevenlabs-audio/references/api-payload.md`**

In the "Payload template — master, v3, tagged" section, change:

```json
"voice_settings": {
    "stability": "natural",
```

to:

```json
"voice_settings": {
    "stability": 0.5,
```

and delete the `previous_text`/`next_text` lines from that same v3 template (they cause a 400 on v3), replacing the "Note on `stability` for v3" callout with:

```
**Live-verified correction, 2026-08-21** `[T]`: eleven_v3 rejects a string
stability mode ("natural") with a 422 — send a float. It also rejects
previous_text/next_text with a 400 — omit them entirely on v3 (this is a
non-issue for a single continuous generation, which needs no chunk-seam
stitching).
```

- [ ] **Step 4: Correct `elevenlabs-audio/references/voice-settings.md`**

In the "v3 stability is three discrete modes" section, add directly beneath the mode table:

```
**Live-API correction, 2026-08-21** `[T]`: this table describes named
*prompting concepts* ElevenLabs documents; the live `/text-to-speech` and
`/with-timestamps` request bodies for eleven_v3 do NOT accept the mode name
as a string value for `voice_settings.stability` — a request with
`"stability": "natural"` returns a 422 ("Input should be a valid number,
unable to parse string as a number"). Send a float in [0, 1] instead; 0.5
is a reasonable Natural-equivalent starting point.
```

- [ ] **Step 5: Verify the doc-truth/provenance suite still passes**

Run: `cd "C:/Projects/ContentStudio" && python -m pytest tests/ -k "provenance or doc_truth"`
Expected: PASS. If `test_skill_provenance.py` flags a new unmarked line, add the missing `[T]`/`[P]` marker and re-run.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/voiceover-brief/references/channel-voice.md .claude/skills/elevenlabs-audio/references/model-routing.md .claude/skills/elevenlabs-audio/references/api-payload.md .claude/skills/elevenlabs-audio/references/voice-settings.md
git commit -m "docs: re-pin channel voice to eleven_v3, correct 3 live-verified v3 API discrepancies"
```

---

### Task 5: `native_pipeline` — support `--vo-mode v3_tags`

**Files:**
- Modify: `native-pipeline/native_pipeline/errors.py`
- Modify: `native-pipeline/native_pipeline/orchestrate.py`
- Modify: `native-pipeline/native_pipeline/cli.py`
- Test: `native-pipeline/tests/test_orchestrate.py`
- Test: `native-pipeline/tests/test_cli.py`

**Interfaces:**
- Consumes: `stitcher.vo_alignment.derive_segments` (existing) and `derive_segments_v3` (Task 2).
- Produces: `orchestrate.run_vo_stage(ws, payload_path, url, log_path, vo_mode="break", beat_texts=None)` — `vo_mode` and `beat_texts` are new, both keyword, both defaulted so every existing caller (including the unmodified `test_native_pipeline_end_to_end`) keeps working unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `native-pipeline/tests/test_orchestrate.py` (mirror whatever mocking pattern the existing `run_vo_stage` tests there already use for `subprocess.run`/`Workspace`/`derive_segments`; if the existing file monkeypatches `orchestrate.derive_segments`, do the same for `orchestrate.derive_segments_v3` below):

```python
def test_run_vo_stage_v3_tags_mode_calls_derive_segments_v3(monkeypatch, tmp_path):
    calls = {}

    def fake_derive_segments_v3(text, alignment, beat_texts, names=None):
        calls["args"] = (text, alignment, beat_texts)
        return []

    def fake_derive_segments(text, alignment, names=None):
        raise AssertionError("break-mode derive_segments must not be called in v3_tags mode")

    monkeypatch.setattr(orchestrate, "derive_segments_v3", fake_derive_segments_v3)
    monkeypatch.setattr(orchestrate, "derive_segments", fake_derive_segments)
    monkeypatch.setattr(orchestrate, "flag_outliers", lambda *a, **k: [])
    monkeypatch.setattr(orchestrate.subprocess, "run", lambda *a, **k: None)

    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps({"text": "beat one\n\nbeat two"}), encoding="utf-8")
    ws = Workspace(root=tmp_path / "renders", slug="v3-mode-test", mode="final")
    ws.ensure_dirs()
    (ws.assets_dir / "alignment.json").write_text(
        json.dumps({"characters": [], "character_start_times_seconds": [],
                    "character_end_times_seconds": []}),
        encoding="utf-8",
    )

    orchestrate.run_vo_stage(
        ws, payload_path, "https://example.invalid/with-timestamps",
        ws.log_path("test"), vo_mode="v3_tags", beat_texts=["beat one", "beat two"],
    )
    assert calls["args"][2] == ["beat one", "beat two"]


def test_run_vo_stage_v3_tags_without_beat_texts_raises(tmp_path):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps({"text": "x"}), encoding="utf-8")
    ws = Workspace(root=tmp_path / "renders", slug="v3-mode-missing", mode="final")
    ws.ensure_dirs()

    with pytest.raises(VoModeMismatchError, match="requires beat_texts"):
        orchestrate.run_vo_stage(
            ws, payload_path, "https://example.invalid", ws.log_path("test"),
            vo_mode="v3_tags",
        )


def test_run_vo_stage_unknown_mode_raises(tmp_path):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps({"text": "x"}), encoding="utf-8")
    ws = Workspace(root=tmp_path / "renders", slug="bad-mode", mode="final")
    ws.ensure_dirs()

    with pytest.raises(VoModeMismatchError, match="'break' or 'v3_tags'"):
        orchestrate.run_vo_stage(
            ws, payload_path, "https://example.invalid", ws.log_path("test"),
            vo_mode="bogus",
        )
```

(Adjust imports at the top of the test file: `import json`, `import pytest`, `from native_pipeline import orchestrate`, `from native_pipeline.errors import VoModeMismatchError`, `from stitcher.naming import Workspace` — add whichever of these the existing file doesn't already import.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd native-pipeline && python -m pytest tests/test_orchestrate.py -k v3_tags -v`
Expected: FAIL — `orchestrate.run_vo_stage()` doesn't accept `vo_mode`/`beat_texts` yet, and `VoModeMismatchError` doesn't exist yet.

- [ ] **Step 3: Add `VoModeMismatchError`**

In `native-pipeline/native_pipeline/errors.py`, add alongside the existing exception classes:

```python
class VoModeMismatchError(ValueError):
    """run_vo_stage's vo_mode is unrecognized, or is 'v3_tags' without the
    beat_texts derive_segments_v3 needs (there is no <break> marker to
    split on, unlike the 'break' mode)."""
```

- [ ] **Step 4: Implement the `vo_mode` parameter in `orchestrate.py`**

In `native-pipeline/native_pipeline/orchestrate.py`, change the import line and `run_vo_stage`:

```python
from stitcher.vo_alignment import Segment, derive_segments, derive_segments_v3
from stitcher.vo_timing import derive_captions

from native_pipeline import assemble, contracts, music_plan
from native_pipeline.errors import VoModeMismatchError
from native_pipeline.flagging import flag_outliers
from native_pipeline.shots import build_shots
```

```python
def run_vo_stage(
    ws: Workspace, payload_path: Path, url: str, log_path: Path,
    vo_mode: str = "break", beat_texts: list[str] | None = None,
) -> tuple[Path, list[Segment]]:
    """vo_mode selects which segment-derivation strategy matches the
    payload's own script-composition convention:
      - "break" (default): eleven_multilingual_v2/flash, beats joined by
        SSML <break> tags (elevenlabs_tooling.breaks.compose_break_tagged_text).
        Uses stitcher.vo_alignment.derive_segments.
      - "v3_tags": eleven_v3, beats joined by a blank line with bracket
        audio tags (elevenlabs_tooling.tags.compose_tagged_text). Uses
        stitcher.vo_alignment.derive_segments_v3, which additionally
        requires `beat_texts` (the exact per-beat strings, tag prefix
        included, that compose_tagged_text was given) to recover
        boundaries -- there is no <break> marker to split on.

    Fails loud on a mismatch rather than guessing.
    """
    if vo_mode not in ("break", "v3_tags"):
        raise VoModeMismatchError(f"vo_mode must be 'break' or 'v3_tags', got {vo_mode!r}")
    if vo_mode == "v3_tags" and not beat_texts:
        raise VoModeMismatchError(
            "vo_mode='v3_tags' requires beat_texts (derive_segments_v3 has "
            "no <break> marker to split on)"
        )

    audio_output = ws.asset("single_take.mp3")
    alignment_output = ws.asset("alignment.json")
    subprocess.run(
        [sys.executable, "-m", "elevenlabs_tooling", "generate-vo",
         "--payload", str(payload_path), "--url", url,
         "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
         "--force"],
        check=True,
        cwd=_ELEVENLABS_TOOLING_DIR,
    )
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    alignment = json.loads(alignment_output.read_text(encoding="utf-8"))
    if vo_mode == "v3_tags":
        segments = derive_segments_v3(payload["text"], alignment, beat_texts)
    else:
        segments = derive_segments(payload["text"], alignment)

    spans = [(segment.name, segment.at, segment.duration) for segment in segments]
    flags = flag_outliers(audio_output, spans, log_path)
    _append_flags(flags, log_path)

    return audio_output, segments
```

- [ ] **Step 5: Add `--vo-mode`/`--vo-beat-texts` to `cli.py`**

In `native-pipeline/native_pipeline/cli.py`, add two arguments to `render_parser`:

```python
render_parser.add_argument("--vo-mode", choices=["break", "v3_tags"], default="break")
render_parser.add_argument(
    "--vo-beat-texts",
    help="Path to a JSON list of the exact per-beat strings (tag prefix "
    "included) submitted to eleven_v3 -- required when --vo-mode v3_tags",
)
```

And in `cmd_render`, before the `orchestrate.run_vo_stage` call, add:

```python
    vo_beat_texts = None
    if args.vo_mode == "v3_tags":
        if not args.vo_beat_texts:
            print("native_pipeline: --vo-beat-texts is required when --vo-mode v3_tags",
                  file=sys.stderr)
            return EXIT_USAGE
        vo_beat_texts_path = Path(args.vo_beat_texts).resolve()
        try:
            vo_beat_texts = json.loads(vo_beat_texts_path.read_text(encoding="utf-8"))
            if not isinstance(vo_beat_texts, list) or not all(isinstance(t, str) for t in vo_beat_texts):
                raise ValueError(f"--vo-beat-texts must be a JSON list of strings: {vo_beat_texts_path}")
        except (OSError, ValueError) as exc:
            print(f"native_pipeline: invalid input: {exc}", file=sys.stderr)
            return EXIT_USAGE
```

and change the `run_vo_stage` call to:

```python
    voice_take, segments = orchestrate.run_vo_stage(
        ws, vo_payload, args.vo_url, log_path,
        vo_mode=args.vo_mode, beat_texts=vo_beat_texts,
    )
```

Add one CLI-level test to `native-pipeline/tests/test_cli.py` (mirror its existing `EXIT_USAGE` assertions for other malformed-input cases): `--vo-mode v3_tags` with `--vo-beat-texts` omitted exits `EXIT_USAGE` with a message containing `--vo-beat-texts is required`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd native-pipeline && python -m pytest -v`
Expected: all pass (the pre-existing 44 plus the new ones), 1 deselected (`e2e`).

- [ ] **Step 7: Commit**

```bash
git add native-pipeline/native_pipeline/errors.py native-pipeline/native_pipeline/orchestrate.py native-pipeline/native_pipeline/cli.py native-pipeline/tests/test_orchestrate.py native-pipeline/tests/test_cli.py
git commit -m "feat(native-pipeline): support --vo-mode v3_tags alongside the existing <break> path"
```

---

### Task 6: Regenerate this run's voiceover through the corrected pipeline

**Files:**
- Create: `runs/8000-a-year-20260808-125850/03-voiceover/native/payload.json`
- Create: `runs/8000-a-year-20260808-125850/03-voiceover/native/vo_beat_texts.json`
- Create (by running the tool, not by hand): `runs/8000-a-year-20260808-125850/03-voiceover/native/single_take.mp3`, `.../alignment.json`
- Create: `runs/8000-a-year-20260808-125850/03-voiceover/vo_segments.json`
- Modify: `runs/8000-a-year-20260808-125850/03-voiceover/elevenlabs-audio-spec.md`

**Interfaces:**
- Consumes: Task 5's `run_vo_stage(vo_mode="v3_tags", beat_texts=...)`, Task 2's `derive_segments_v3`.
- Produces: `vo_segments.json` — the run's new source-of-truth timing artifact, `[{"name": str, "at": float, "duration": float}, ...]` — that Task 7's skill-doc update and any future `shorts-assembly`/`music-brief` work for this run reads.

This is the "apply it for real" task, not a demo. It supersedes the two abandoned chunked-VO experiments already in this run's `03-voiceover/` directory (the `chunk-*.mp3`/`v3tags/`/`speedtest-*` files stay on disk as dated experiment history, per this session's own record — they are not deleted).

- [ ] **Step 1: Pick the final script and tag scheme**

Use whichever of this session's two full-script variants (`v3single/full.mp3`, tags at 3 points, or `v3single/full_pause.mp3`, tags at 3 points plus `[pause]` at 4 structural breaks) the operator preferred after listening to both. Confirm with the operator before spending on this task's real generation if it hasn't been said explicitly yet.

- [ ] **Step 2: Write the beat-split payload**

Using `elevenlabs_tooling.tags.compose_tagged_text` (Task 3) with the 9 beats and their tags exactly as validated this session (`[excited]`/Hook-A, `[whispers]` or `[pause][whispers]`/Hook-B, `None`/Setup, `None`/Turn, `None`/Re-hook, `None`/Proof, `None`/Payoff-A, `[sighs]` or `[pause][sighs]`/Payoff-B, `None`/Loop-CTA — or the `[pause]`-augmented set if that was preferred), write `runs/8000-a-year-20260808-125850/03-voiceover/native/vo_beat_texts.json` as the JSON list of the exact resulting per-beat strings, and `native/payload.json` as:

```json
{
  "text": "<compose_tagged_text's full output>",
  "model_id": "eleven_v3",
  "voice_settings": {"stability": 0.5, "similarity_boost": 0.80, "style": 0.0, "speed": 1.0, "use_speaker_boost": true},
  "seed": 20260821,
  "apply_text_normalization": "auto"
}
```

- [ ] **Step 3: Confirm spend, then run the real generation**

State the cost (roughly the same ~$0.065-0.08 as this session's earlier v3 full-script renders) and get explicit confirmation, per this session's established practice, before running:

```bash
cd native-pipeline
python -m elevenlabs_tooling generate-vo \
  --payload "../runs/8000-a-year-20260808-125850/03-voiceover/native/payload.json" \
  --url "https://api.elevenlabs.io/v1/text-to-speech/eDwT8Vhp2yxJzAMmuuPA/with-timestamps" \
  --audio-output "../runs/8000-a-year-20260808-125850/03-voiceover/native/single_take.mp3" \
  --alignment-output "../runs/8000-a-year-20260808-125850/03-voiceover/native/alignment.json" \
  --force
```

- [ ] **Step 4: Derive segments and write `vo_segments.json`**

```bash
python -c "
import json
from pathlib import Path
from stitcher.vo_alignment import derive_segments_v3

run_dir = Path('../runs/8000-a-year-20260808-125850/03-voiceover')
payload = json.loads((run_dir / 'native/payload.json').read_text(encoding='utf-8'))
alignment = json.loads((run_dir / 'native/alignment.json').read_text(encoding='utf-8'))
beat_texts = json.loads((run_dir / 'native/vo_beat_texts.json').read_text(encoding='utf-8'))
names = ['hook_a','hook_b','setup','turn','rehook','proof','payoff_a','payoff_b','loopcta']

segments = derive_segments_v3(payload['text'], alignment, beat_texts, names=names)
out = [{'name': s.name, 'at': s.at, 'duration': s.duration} for s in segments]
(run_dir / 'vo_segments.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
print(json.dumps(out, indent=2))
"
```

Verify: 9 segments, `at` values monotonically increasing, no segment's `duration` is negative or absurd (sanity-eyeball against this session's earlier per-chunk duration measurements).

- [ ] **Step 5: Update `elevenlabs-audio-spec.md`**

Replace the spec's `NEXT` section (previously showing the chunked-master path as done) with a note that this run now ships the single-take `eleven_v3` + bracket-tags voiceover instead, superseding the earlier chunked `multilingual_v2` master and the two comparison experiments — link `native/single_take.mp3`, `native/alignment.json`, and `vo_segments.json`, and state that per-beat conditioning (`precondition.condition_clip`) is deliberately **not** applied to this file (Global Constraints above) — its raw LUFS is measured, not modified.

- [ ] **Step 6: Commit**

```bash
git add runs/8000-a-year-20260808-125850/03-voiceover/
git commit -m "feat: regenerate 8000-a-year VO as a single eleven_v3 take with real segment timing"
```

---

### Task 7: Note the new timing source in `shorts-assembly`

**Files:**
- Modify: `.claude/skills/shorts-assembly/SKILL.md`

**Interfaces:** None (documentation only).

Per the 2026-08-20 design doc's own explicit boundary ("Skill scope: tooling-only... the four creative-decision skills keep producing exactly the outputs they produce today"), this is a small pointer, not a rewrite — `shorts-assembly` still produces the same prose shot table; the only change is telling whoever fills in the operator-side `asset_manifest` where real timing now comes from.

- [ ] **Step 1: Add a note to the "Input 2b" section**

In `.claude/skills/shorts-assembly/SKILL.md`, directly after the existing "2b. Optional — the `elevenlabs-audio` AUDIO PRODUCTION SPEC" paragraph, add:

```
**2c. Optional — a `vo_segments.json` from the native single-take pipeline**
`[P]`. If the Short's voiceover was generated as one continuous `eleven_v3`
take (`native_pipeline`, `--vo-mode v3_tags`) rather than per-beat chunks,
its real measured segment boundaries live in the run's
`03-voiceover/vo_segments.json` (`[{"name", "at", "duration"}, ...]`) —
use these, not an estimated per-beat second count from the script, as the
shot table's actual timing. `native_pipeline.shots.build_shots` already
turns these into contiguous `Shot.start`/`end` values (each shot holds
through its trailing gap to the next segment's start) — this skill's own
shot-table prose should reference the segment name and its real duration,
not re-estimate one.
```

- [ ] **Step 2: Verify the doc-truth suite still passes**

Run: `cd "C:/Projects/ContentStudio" && python -m pytest tests/ -k "provenance or doc_truth"`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/shorts-assembly/SKILL.md
git commit -m "docs(shorts-assembly): note vo_segments.json as the real-timing source when present"
```

---

## Explicitly out of scope for this plan

- **A full `native_pipeline render` invocation for the `8000-a-year` run.** Blocked on two upstream artifacts this plan doesn't produce: an `asset_manifest` (needs real Midjourney images — `visual-prompts` hasn't been run for this run yet) and a `bed_arc_structured` translation of `music-brief`'s prose arc. Task 6 stops at producing the real, measured `vo_segments.json` — the next milestone (generate the visuals, translate the bed arc, run `python -m native_pipeline render`) is follow-on work once images exist, not part of this plan.
- **A pre-existing documentation gap this research surfaced, not introduced:** `tests/test_doc_truth.py`'s `test_claude_md_lists_every_outbound_call_site` only scans `pipeline-app/`, `download_*.py`, and `coach-prep-app/` (its `SCANNED` glob list) — `elevenlabs-tooling/elevenlabs_tooling/client.py`'s real outbound calls to `api.elevenlabs.io` are invisible to both that test and `CLAUDE.md`'s network table, which never mentions `elevenlabs-tooling`, `native-pipeline`, or `stitcher` at all. This predates this plan and is a separate, real gap — worth a dedicated follow-up (either extending `SCANNED` and adding the rows, or documenting why this toolchain is deliberately out of `CLAUDE.md`'s network-table scope) rather than folding into this plan's task list.

## Self-Review

**Spec coverage:** voice/model pivot to `eleven_v3` with tags (Task 4) — covered. Timestamps driving beat/caption/shot timing (Tasks 2, 5 reusing existing `derive_captions`/`build_shots`) — covered. Timestamps driving the music bed (existing `music_plan.build_music_plan`, already keyed to real segment/gap timing — no new code needed, confirmed during research) — covered, and stated as already-built rather than re-implemented. Applying this to the actual run — Task 6. Atomic plan — this document.

**Placeholder scan:** every step above has real, complete code or an exact file-content edit; none says "TBD" or "add appropriate handling."

**Type consistency:** `Segment(name, at, duration)` used identically across Tasks 2, 5, 6. `derive_segments_v3`'s signature (`text, alignment, beat_texts, names=None`) matches every call site that uses it (Task 2's own tests, Task 5's `orchestrate.py`, Task 6's script). `compose_tagged_text(beats, beat_tags)` used identically in Task 3's tests and Task 6's step 2.

## Execution options

Plan complete and saved to `docs/superpowers/plans/2026-08-21-v3-tags-native-pipeline-adoption.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
