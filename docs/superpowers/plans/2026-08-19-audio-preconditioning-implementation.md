# Audio Preconditioning for `stitcher` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested `stitcher/stitcher/precondition.py` module that removes beat-to-beat
loudness inconsistency and dynamic-range collapse from voiceover/bed clips before they enter
`stitcher`'s existing gated `build_audio()` pipeline, then prove it end-to-end against the real
audio assets that motivated this work and deliver a corrected mix for a listen.

**Architecture:** One new pure-function module (`condition_clip`) that measures a raw clip,
applies gain + a true-peak limiter via ffmpeg, re-measures, and retries (up to 4 attempts) until
both a peak ceiling and a loudness target are satisfied simultaneously — never returning a result
that silently missed either. `build_audio()` itself is not modified. A throwaway script (under the
gitignored `stitcher/renders/` tree, so it can never be staged) wires `condition_clip` + a
declarative bed assembly into a real call to `build_audio()` against the actual render assets.

**Tech Stack:** Python 3, ffmpeg 9.0 (real binary, no mocking in the final task), pytest,
pydantic v2 (via `stitcher.spec`).

**Source spec:** `docs/superpowers/specs/2026-08-19-audio-preconditioning-design.md` (v3, three
Opus review rounds, all empirically verified against real files). Every numeric constant and
algorithm step below is copied from that spec verbatim — do not re-derive or re-round any of them.

**Revision note:** this plan went through one Opus implementation-verification round after its
first commit — the reviewer actually assembled Task 1's `precondition.py`, ran the mocked tests,
and ran Task 5's harness against the real render assets, rather than only reading the plan text. It
found one Critical bug (Task 1's temp-file path had no extension ffmpeg could infer a muxer from,
so every *real* `condition_clip` call failed even though all four mocked test tasks passed clean —
none of the mocked tests could see it) plus several Important/Minor gaps, all fixed below: a real,
unmocked `@pytest.mark.e2e` smoke test was added (Task 1) specifically because the mocked suite's
blind spot is exactly the class of bug that slipped through; two defensive guards were added to
`condition_clip` (a digital-silence check and an `alimiter` valid-range floor on the peak-retry
ceiling); a temp-file leak on `PreconditionError` was closed; several internally-contradictory task
descriptions (Tasks 2–4 saying both "Modify precondition.py" and "write the failing test" while
implementing nothing) were corrected to say plainly that they add tests only; the "outside every
git worktree" claim about the throwaway script's location was corrected to the real reason it can
never be committed (it sits under the repo's gitignored `renders/` tree, not outside the repo); and
a vacuous single-item overlap check in Task 5 was replaced with an assertion that actually checks
something. After these fixes, the reviewer confirmed a full green run: `condition_clip` against a
real ffmpeg-generated tone, all mocked unit tests, and Task 5's real end-to-end harness against the
actual 9 files (`normalization_type: linear`, independently re-measured mix at `-13.9 LUFS / -2.0
dBTP`, mean per-clip LRA loss 0.93 LU — all within this plan's stated success criteria).

## Global Constraints

- `stitcher/stitcher/audio.py`, `stitcher/stitcher/spec.py`, `stitcher/stitcher/envelope.py`,
  `stitcher/stitcher/naming.py`, `stitcher/stitcher/ffmpeg.py` are **not modified** by this plan.
  `precondition.py` is a new, additive module; `build_audio()` stays exactly as it is today.
- No ElevenLabs (or any other paid) API call anywhere in this plan. Every task uses either mocked
  ffmpeg (Tasks 1–4) or real local ffmpeg against already-generated audio files (Task 5) — zero
  spend either way.
- Constants, copied exactly from the spec — do not change these values while implementing:
  `CONDITION_ATTACK_MS = 5`, `CONDITION_RELEASE_MS = 50`, `TP_TOLERANCE_DB = 0.1`,
  `LUFS_TOLERANCE = 0.35`, `MAX_ATTEMPTS = 4`, `CONDITION_LUFS = -14.0`,
  `CONDITION_TP_DBTP = -2.5`, `DELIVERY_LUFS = -14.0`, `DELIVERY_TP_DBTP = -1.0`.
- Filter chain order is always `aresample=48000,volume=...dB,alimiter=...` — resample first, gain
  second, limiter third. Every `alimiter` call carries `level=0` and `latency=1` explicitly. Every
  conditioned output is written `-c:a pcm_s16le -ar 48000 -ac 2` (stereo, regardless of source
  channel layout).
- Tests run from the `stitcher/` directory: `cd stitcher && python -m pytest tests/ -v`. The
  project's `pytest.ini` sets `pythonpath = .` and `testpaths = tests`.
- No shot re-cut, no captions/overlay changes, no `.mp4` render, no `cmd_render`/CLI wiring. This
  plan is audio-only, exactly per spec §3/§8.

---

## File Structure

| File | Responsibility |
|---|---|
| `stitcher/stitcher/precondition.py` | New. `condition_clip()`, `ConditionResult`, `PreconditionError`, the module constants. The only new production code this plan adds. |
| `stitcher/tests/test_precondition.py` | New. Mocked-ffmpeg unit tests for `condition_clip()`'s clean/peak-retry/loudness-retry/exhausted paths, following `tests/test_audio.py`'s existing `wire()` pattern. |
| `<render dir>/validate_precondition.py` | New, under the gitignored `renders/` tree (see Task 5) — throwaway, never committed. Runs `condition_clip` + a declarative bed reassembly + a real `build_audio()` call against the actual render assets, and checks §5's five success criteria. |
| `docs/superpowers/plans/2026-08-19-audio-preconditioning-implementation-RESULTS.md` | New. Written at the end of Task 5, capturing the real run's output. |

---

### Task 1: `precondition.py` scaffold — constants, dataclasses, and the clean-path attempt

**Files:**
- Create: `stitcher/stitcher/precondition.py`
- Test: `stitcher/tests/test_precondition.py`

**Interfaces:**
- Produces: `condition_clip(source: Path, target_lufs: float, target_tp_dbtp: float, out_path: Path, log_path: Path) -> ConditionResult`; `ConditionResult` (frozen dataclass: `source: Path`, `output: Path`, `input_measurement: dict`, `output_measurement: dict`, `limited: bool`, `peak_reduction_db: float`); `PreconditionError(Exception)`; module constants `CONDITION_ATTACK_MS`, `CONDITION_RELEASE_MS`, `TP_TOLERANCE_DB`, `LUFS_TOLERANCE`, `MAX_ATTEMPTS`.
- Consumes: `stitcher.ffmpeg.measure_loudness(path, log_path) -> dict` (keys `input_i`/`input_tp`/`input_lra` only — confirmed at `ffmpeg.py:344-348`) and `stitcher.ffmpeg.run(args, log_path) -> str` (confirmed at `ffmpeg.py:136-174`).

- [ ] **Step 1: Write the failing tests for the clean path and its two command-shape properties**

Create `stitcher/tests/test_precondition.py`:

```python
from pathlib import Path

import pytest

from stitcher import precondition as pc


def wire(monkeypatch, measurements: list[dict]):
    """Record ffmpeg.run calls; feed measure_loudness from `measurements` in
    order. The first item is the source measurement (step 1 of the
    algorithm); each remaining item is one attempt's measurement of the
    freshly-written temp file (step 3, looped)."""
    calls: list[list[str]] = []
    remaining = list(measurements)

    def fake_run(args, log_path):
        calls.append(args)
        Path(args[-1]).write_bytes(b"wav")
        return ""

    def fake_measure(path, log_path):
        if not remaining:
            raise AssertionError("measure_loudness called more times than scripted")
        return remaining.pop(0)

    monkeypatch.setattr(pc.ffmpeg, "run", fake_run)
    monkeypatch.setattr(pc.ffmpeg, "measure_loudness", fake_measure)
    return calls


def test_clean_path_accepts_on_the_first_attempt(tmp_path, monkeypatch):
    calls = wire(monkeypatch, [
        {"input_i": -20.0, "input_tp": -6.0, "input_lra": 5.0},   # source
        {"input_i": -14.0, "input_tp": -2.5, "input_lra": 4.0},   # attempt 1: both ok
    ])
    source = tmp_path / "raw.wav"
    source.write_bytes(b"x")
    out_path = tmp_path / "conditioned.wav"
    log_path = tmp_path / "log.txt"

    result = pc.condition_clip(source, -14.0, -2.5, out_path, log_path)

    assert len(calls) == 1
    joined = " ".join(calls[0])
    # resample first, then gain, then limiter -- spec §4.1 step 3, order matters
    assert joined.index("aresample=48000") < joined.index("volume=6.00dB")
    assert joined.index("volume=6.00dB") < joined.index("alimiter=")
    expected_limit = 10 ** (-2.5 / 20)
    assert f"alimiter=limit={expected_limit:.6f}" in joined
    assert "level=0" in joined
    assert "latency=1" in joined  # timing-alignment property (spec §7)
    assert calls[0][calls[0].index("-ac") + 1] == "2"  # output-channel-count property (spec §7)
    assert "pcm_s16le" in calls[0]

    assert result.source == source
    assert result.output == out_path
    assert result.input_measurement == {"input_i": -20.0, "input_tp": -6.0, "input_lra": 5.0}
    assert result.output_measurement == {"input_i": -14.0, "input_tp": -2.5, "input_lra": 4.0}
    # (input_tp=-6.0 + applied_gain=6.0) - output_tp=-2.5 = 2.5
    assert result.peak_reduction_db == pytest.approx(2.5)
    assert result.limited is True  # 2.5 > the 0.05 threshold
    assert out_path.is_file()
    assert out_path.read_bytes() == b"wav"


def test_a_clip_that_needed_no_limiting_reports_limited_false(tmp_path, monkeypatch):
    wire(monkeypatch, [
        {"input_i": -20.0, "input_tp": -20.0, "input_lra": 5.0},  # very quiet source
        {"input_i": -14.0, "input_tp": -14.0, "input_lra": 5.0},  # gain alone landed here
    ])
    source = tmp_path / "raw.wav"
    source.write_bytes(b"x")
    result = pc.condition_clip(source, -14.0, -2.5, tmp_path / "out.wav", tmp_path / "log.txt")
    # (input_tp=-20.0 + applied_gain=6.0) - output_tp=-14.0 = 0.0
    assert result.peak_reduction_db == pytest.approx(0.0)
    assert result.limited is False


@pytest.mark.e2e
def test_condition_clip_against_real_ffmpeg(tmp_path):
    """Every other test in this file mocks ffmpeg.run/measure_loudness, so
    none of them can catch a command that's syntactically invalid to the
    real binary -- e.g. a temp output filename ffmpeg can't infer a muxer
    from, which is exactly the bug an Opus review of this plan caught by
    actually running condition_clip against real ffmpeg (a mocked-only test
    suite went green while the real thing failed on its first call). This
    test runs the real ffmpeg 9.0 binary once, end to end, no mocking."""
    source = tmp_path / "tone.wav"
    pc.ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-y", "-f", "lavfi",
         "-i", "sine=frequency=220:duration=3", "-ac", "1",
         "-c:a", "pcm_s16le", str(source)],
        tmp_path / "gen_log.txt",
    )
    out_path = tmp_path / "conditioned.wav"
    result = pc.condition_clip(source, -14.0, -2.5, out_path, tmp_path / "log.txt")
    assert result.output.is_file()
    assert abs(result.output_measurement["input_i"] + 14.0) <= pc.LUFS_TOLERANCE
    assert pc.ffmpeg.probe(result.output).duration == pytest.approx(3.0, abs=0.05)
```

`stitcher/pytest.ini` already registers the `e2e` marker (`e2e: end-to-end render; needs a real
ffmpeg on PATH`) and does not deselect it by default, so this test runs as part of every normal
`pytest` invocation in this project — matching how the rest of the `stitcher` suite already treats
real-ffmpeg tests.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd stitcher && python -m pytest tests/test_precondition.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'stitcher.precondition'` (or similar
import error) — the module does not exist yet.

- [ ] **Step 3: Write `precondition.py`'s constants, dataclasses, and the complete measure→gain→limit→re-measure→retry loop (all branches — Tasks 2–4 add the per-branch regression tests, they do not add new code)**

Create `stitcher/stitcher/precondition.py`:

```python
"""Per-clip loudness/true-peak conditioning.

Removes beat-to-beat level inconsistency and dynamic-range collapse (spec
docs/superpowers/specs/2026-08-19-audio-preconditioning-design.md §1) by
conditioning each raw VO take and bed segment individually, before it ever
reaches build_audio()'s own two-pass linear loudnorm. build_audio() itself is
unmodified -- this module only makes its inputs safe for that gate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from . import ffmpeg

# Pinned explicitly so a future ffmpeg default change can't silently move
# these -- verified against the installed ffmpeg 9.0 build's
# `-h filter=alimiter` (spec §4.1).
CONDITION_ATTACK_MS = 5
CONDITION_RELEASE_MS = 50

# How far a measured true peak may land over target before triggering a
# tighter-ceiling retry (spec §4.1).
TP_TOLERANCE_DB = 0.1

# How far a conditioned clip's integrated loudness may drift from target
# before triggering a makeup-gain retry. Deliberately 0.35, not 0.3: a
# boundary of exactly 0.3 sits on a floating-point knife edge against
# ebur128's 0.1 LU output granularity (spec §4.1: a real measured
# `-14.3` vs. target `-14.0` case evaluates `abs(-14.3 - -14.0) <= 0.3` as
# False due to `0.30000000000000071...`).
LUFS_TOLERANCE = 0.35

MAX_ATTEMPTS = 4


class PreconditionError(Exception):
    """Raised when, after MAX_ATTEMPTS, the output still fails the peak or
    loudness target. Never silently returned -- a hard stop, matching
    stitcher's existing LoudnormNotLinearError/SilentVoiceError philosophy."""


@dataclass(frozen=True)
class ConditionResult:
    source: Path
    output: Path
    # {input_i, input_tp, input_lra} -- the exact 3 keys
    # ffmpeg.measure_loudness returns (ffmpeg.py:344-348).
    input_measurement: dict
    output_measurement: dict
    # True if peak_reduction_db > 0.05 -- distinguishes "the limiter did
    # something" from "gain alone would have landed here anyway".
    limited: bool
    # (input_measurement['input_tp'] + applied_gain) - output_measurement['input_tp'],
    # using the ACCEPTED attempt's final applied_gain (which the
    # loudness-retry branch, Task 3, may have revised from its initial
    # value). The gap between "what the peak would have been with gain
    # alone" and "what it actually is".
    peak_reduction_db: float


# alimiter's `limit` parameter is only valid in [0.0625, 1] (~-24.08..0
# dBFS) -- verified against the installed ffmpeg 9.0 build's
# `-h filter=alimiter`. A ceiling that would push `limit` below this floor
# is a PreconditionError, not an invalid ffmpeg argument.
_ALIMITER_MIN_DBTP = 20 * math.log10(0.0625)  # ~-24.08


def condition_clip(
    source: Path,
    target_lufs: float,
    target_tp_dbtp: float,
    out_path: Path,
    log_path: Path,
) -> ConditionResult:
    """Condition one clip so it is safe for build_audio()'s linear-loudnorm
    gate, without collapsing dynamics to get there (spec §4.1)."""
    input_measurement = ffmpeg.measure_loudness(source, log_path)
    if ffmpeg.is_digital_silence(input_measurement):
        # Matches stitcher's existing SilentVoiceError philosophy (audio.py):
        # a silent source has no loudness to solve against, so failing loudly
        # here beats a doomed 4-attempt encode loop ending in a confusing
        # "-inf" peak_reduction_db.
        raise PreconditionError(
            f"{source}: input is digital silence (integrated "
            f"{input_measurement['input_i']} LUFS, true peak "
            f"{input_measurement['input_tp']} dBFS) -- there is no loudness "
            "to condition against"
        )
    applied_gain = target_lufs - input_measurement["input_i"]
    ceiling_dbtp = target_tp_dbtp

    temp = out_path.with_suffix(".tmp" + out_path.suffix)
    output_measurement: dict = {}

    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if ceiling_dbtp < _ALIMITER_MIN_DBTP:
                raise PreconditionError(
                    f"{source}: peak-retry tightened the ceiling to "
                    f"{ceiling_dbtp:.2f} dBTP, below alimiter's valid range "
                    f"(>= {_ALIMITER_MIN_DBTP:.2f} dBTP); the source's true "
                    "peak is too extreme for this target to be reachable by "
                    "limiting alone"
                )
            limit = 10 ** (ceiling_dbtp / 20)
            chain = (
                f"aresample=48000,volume={applied_gain:.2f}dB,"
                f"alimiter=limit={limit:.6f}:attack={CONDITION_ATTACK_MS}:"
                f"release={CONDITION_RELEASE_MS}:level=0:latency=1"
            )
            ffmpeg.run(
                ["ffmpeg", "-hide_banner", "-y", "-i", str(source),
                 "-af", chain,
                 "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(temp)],
                log_path,
            )
            output_measurement = ffmpeg.measure_loudness(temp, log_path)

            tp_ok = output_measurement["input_tp"] <= target_tp_dbtp + TP_TOLERANCE_DB
            lufs_ok = abs(output_measurement["input_i"] - target_lufs) <= LUFS_TOLERANCE

            if tp_ok and lufs_ok:
                temp.replace(out_path)
                peak_reduction_db = (
                    (input_measurement["input_tp"] + applied_gain)
                    - output_measurement["input_tp"]
                )
                limited = peak_reduction_db > 0.05
                _log_result(
                    log_path, source, out_path, input_measurement, output_measurement,
                    applied_gain, ceiling_dbtp, attempt, peak_reduction_db,
                )
                return ConditionResult(
                    source, out_path, input_measurement, output_measurement,
                    limited, peak_reduction_db,
                )

            if not tp_ok:
                # Peak still too high -- tighten the ceiling, keep gain fixed.
                ceiling_dbtp -= (output_measurement["input_tp"] - target_tp_dbtp) + 0.2
            else:
                # tp_ok held but lufs_ok didn't: the limiter pulled loudness
                # away from target. Re-solve gain rather than accept the
                # drift -- this is the fix for the defect the second Opus
                # review round found (spec §4.1: a retry that only
                # re-checked peak silently let integrated loudness drift up
                # to 0.4 LU on real material).
                applied_gain += target_lufs - output_measurement["input_i"]

        raise PreconditionError(
            f"{source}: failed to reach target_lufs={target_lufs} / "
            f"target_tp_dbtp={target_tp_dbtp} within {MAX_ATTEMPTS} attempts; "
            f"last measurement: {output_measurement}"
        )
    finally:
        temp.unlink(missing_ok=True)


def _log_result(
    log_path: Path,
    source: Path,
    out_path: Path,
    input_measurement: dict,
    output_measurement: dict,
    applied_gain: float,
    ceiling_dbtp: float,
    attempts: int,
    peak_reduction_db: float,
) -> None:
    """A dynamics-losing fix must be visible in the QA trail, not another
    undocumented silent step (spec §4.1 step 6)."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"# condition_clip {source.name} -> {out_path.name}: "
            f"attempts={attempts} applied_gain={applied_gain:.2f}dB "
            f"ceiling={ceiling_dbtp:.2f}dBTP "
            f"input(I={input_measurement['input_i']:.2f} "
            f"TP={input_measurement['input_tp']:.2f} "
            f"LRA={input_measurement['input_lra']:.2f}) "
            f"output(I={output_measurement['input_i']:.2f} "
            f"TP={output_measurement['input_tp']:.2f} "
            f"LRA={output_measurement['input_lra']:.2f}) "
            f"peak_reduction_db={peak_reduction_db:.2f}\n"
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_precondition.py -v`
Expected: PASS (3 tests: clean path, limited-false, the real-ffmpeg e2e smoke test)

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/precondition.py stitcher/tests/test_precondition.py
git commit -m "feat(stitcher): add precondition.py clean-path conditioning"
```

---

### Task 2: Peak-retry branch — tighten the ceiling, keep gain fixed

**Files:**
- Test-only. No production file is modified — Task 1 already implements this branch; this task adds
  its regression test.
- Test: `stitcher/tests/test_precondition.py`

**Interfaces:**
- Consumes: `condition_clip` (Task 1, unchanged signature).
- Produces: no new symbols — a regression test for the peak-retry branch already written in Task 1's implementation.

- [ ] **Step 1: Write the regression test for this branch**

Append to `stitcher/tests/test_precondition.py`:

```python
def test_a_high_true_peak_triggers_a_tightened_ceiling_retry_with_gain_unchanged(tmp_path, monkeypatch):
    calls = wire(monkeypatch, [
        {"input_i": -20.0, "input_tp": -6.0, "input_lra": 5.0},   # source
        {"input_i": -14.0, "input_tp": -2.0, "input_lra": 4.0},   # attempt 1: tp fails (-2.0 > -2.4)
        {"input_i": -14.0, "input_tp": -3.2, "input_lra": 4.0},   # attempt 2: tp passes at tightened ceiling
    ])
    source = tmp_path / "raw.wav"
    source.write_bytes(b"x")
    out_path = tmp_path / "out.wav"
    log_path = tmp_path / "log.txt"

    result = pc.condition_clip(source, -14.0, -2.5, out_path, log_path)

    assert len(calls) == 2
    first, second = calls
    assert "volume=6.00dB" in " ".join(first)
    assert "volume=6.00dB" in " ".join(second)  # gain untouched by a peak-only retry
    expected_ceiling = -2.5 - ((-2.0 - -2.5) + 0.2)
    expected_limit = 10 ** (expected_ceiling / 20)
    assert f"alimiter=limit={expected_limit:.6f}" in " ".join(second)
    assert result.output_measurement["input_tp"] == -3.2
    assert out_path.is_file()
```

*(This test is expected to already PASS against Task 1's implementation — Task 1's loop shell
already contains the peak-retry branch. This task exists as its own reviewable unit specifically
because §7 of the spec names "peak-retry path" as its own test category, and a reviewer should be
able to confirm this specific branch in isolation.)*

- [ ] **Step 2: Run the test to confirm it passes against the existing implementation**

Run: `cd stitcher && python -m pytest tests/test_precondition.py -v -k tightened_ceiling`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add stitcher/tests/test_precondition.py
git commit -m "test(stitcher): cover precondition's peak-retry branch"
```

---

### Task 3: Loudness-retry branch — re-solve gain rather than accept drift (the critical fix)

**Files:**
- Test-only. No production file is modified — Task 1 already implements this branch; this task adds
  its regression test.
- Test: `stitcher/tests/test_precondition.py`

**Interfaces:**
- Consumes: `condition_clip` (Task 1, unchanged signature).
- Produces: no new symbols — the test that would have caught the v2 spec defect (a retry that
  silently let integrated loudness drift while only re-checking peak).

- [ ] **Step 1: Write the regression test for this branch**

Append to `stitcher/tests/test_precondition.py`:

```python
def test_a_peak_ok_loudness_drifted_result_re_solves_gain_not_just_accepts_drift(tmp_path, monkeypatch):
    """This is the case v2 of the design spec got wrong: it only re-checked
    true peak on retry, so a limiter-induced loudness drift (here, 0.4 LU)
    was silently accepted -- reintroducing the exact beat-to-beat
    inconsistency defect this module exists to remove. v3 re-solves gain."""
    calls = wire(monkeypatch, [
        {"input_i": -20.0, "input_tp": -6.0, "input_lra": 5.0},    # source
        {"input_i": -14.4, "input_tp": -2.4, "input_lra": 4.0},    # attempt 1: tp ok, lufs drifted 0.4 LU
        {"input_i": -14.05, "input_tp": -2.5, "input_lra": 4.0},   # attempt 2: both ok
    ])
    source = tmp_path / "raw.wav"
    source.write_bytes(b"x")
    out_path = tmp_path / "out.wav"
    log_path = tmp_path / "log.txt"

    result = pc.condition_clip(source, -14.0, -2.5, out_path, log_path)

    assert len(calls) == 2
    first, second = calls
    assert "volume=6.00dB" in " ".join(first)
    assert "volume=6.40dB" in " ".join(second)  # 6.0 + (-14.0 - -14.4)
    # ceiling is untouched by a loudness-only retry
    expected_limit = 10 ** (-2.5 / 20)
    assert f"alimiter=limit={expected_limit:.6f}" in " ".join(second)
    assert result.output_measurement["input_i"] == pytest.approx(-14.05)
```

- [ ] **Step 2: Run the test to confirm it passes against the existing implementation**

Run: `cd stitcher && python -m pytest tests/test_precondition.py -v -k re_solves_gain`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add stitcher/tests/test_precondition.py
git commit -m "test(stitcher): cover precondition's loudness-retry branch (the v2 defect fix)"
```

---

### Task 4: Exhausted-retries path — hard failure, never a silently out-of-envelope result

**Files:**
- Test-only. No production file is modified — Task 1 already implements this path; this task adds
  its regression test.
- Test: `stitcher/tests/test_precondition.py`

**Interfaces:**
- Consumes: `condition_clip`, `PreconditionError`, `MAX_ATTEMPTS` (all Task 1).
- Produces: no new symbols.

- [ ] **Step 1: Write the regression test for this path**

Append to `stitcher/tests/test_precondition.py`:

```python
def test_exhausting_all_attempts_raises_precondition_error(tmp_path, monkeypatch):
    # Every attempt reports the same tp_ok-but-lufs-drifted measurement,
    # which never converges inside MAX_ATTEMPTS -- must never be silently
    # accepted or returned.
    calls = wire(monkeypatch, [
        {"input_i": -20.0, "input_tp": -6.0, "input_lra": 5.0},   # source
        {"input_i": -15.0, "input_tp": -2.5, "input_lra": 4.0},   # attempt 1
        {"input_i": -15.0, "input_tp": -2.5, "input_lra": 4.0},   # attempt 2
        {"input_i": -15.0, "input_tp": -2.5, "input_lra": 4.0},   # attempt 3
        {"input_i": -15.0, "input_tp": -2.5, "input_lra": 4.0},   # attempt 4
    ])
    source = tmp_path / "raw.wav"
    source.write_bytes(b"x")
    out_path = tmp_path / "out.wav"
    log_path = tmp_path / "log.txt"

    with pytest.raises(pc.PreconditionError) as caught:
        pc.condition_clip(source, -14.0, -2.5, out_path, log_path)

    assert len(calls) == pc.MAX_ATTEMPTS
    assert not out_path.is_file()
    assert str(source) in str(caught.value)
```

- [ ] **Step 2: Run the test to confirm it passes against the existing implementation**

Run: `cd stitcher && python -m pytest tests/test_precondition.py -v -k exhausting_all_attempts`
Expected: PASS

- [ ] **Step 3: Run the full `precondition.py` test file and the full `stitcher` suite**

Run: `cd stitcher && python -m pytest tests/test_precondition.py -v`
Expected: PASS (6 tests: clean path, limited-false, the real-ffmpeg e2e smoke test, peak-retry,
loudness-retry, exhausted-retries. The properties asserted inline in the clean-path test cover
timing-alignment and output-channel-count per spec §7 — no separate test functions needed for those
two, since they are static properties of the single command built on the clean path, already
asserted in Task 1 Step 1).

Run: `cd stitcher && python -m pytest tests/ -v`
Expected: PASS (every existing `stitcher` test plus the new ones — confirms this module introduced
no regression anywhere else).

- [ ] **Step 4: Commit**

```bash
git add stitcher/tests/test_precondition.py
git commit -m "test(stitcher): cover precondition's exhausted-retries path"
```

---

### Task 5: Real end-to-end validation against the actual render, and delivery

This task makes **zero mocked calls** — every `ffmpeg` invocation is real, against the actual
audio files already generated for `stop-over-specialization-in-youth-sports-20260811-004711`. No
network calls, no ElevenLabs spend. This directly exercises `condition_clip` (Tasks 1–4) and the
real, unmodified `build_audio()`.

**Files:**
- Create: `C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711\validate_precondition.py`
  — lives under `stitcher/renders/`, which the repo's `.gitignore` excludes wholesale
  (`.gitignore:43`, `renders/`). This directory sits inside the same repo's working tree (it is
  **not** outside version control the way an unrelated path would be), but `git add` from any
  worktree cannot reach a file under an ignored directory, so this is what makes the script
  "throwaway" per spec §5/§7 without relying on discipline to avoid staging it.
- Create: `docs/superpowers/plans/2026-08-19-audio-preconditioning-implementation-RESULTS.md`
  (inside the worktree, committed).

**Interfaces:**
- Consumes: `stitcher.precondition.condition_clip` (Task 1), `stitcher.audio.build_audio` (existing,
  `audio.py:347-354`), `stitcher.ffmpeg.{run, measure_loudness, probe}` (existing), `stitcher.naming.Workspace`
  (existing), `stitcher.spec.{RenderSpec, Shot, Canvas, SafeZone, Audio, Stem, Bed, BedWindow, Fade, Loudness}`
  (existing).
- Produces: `Final_Mix_Preconditioned.wav` / `.mp3` in the render's `assets/provoice-2026-08-19/`
  directory (for a human listen), plus the RESULTS.md doc.

- [ ] **Step 1: Verify the 9 raw source files still exist at their expected paths**

Run (PowerShell):

```powershell
Get-ChildItem "C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711\assets\provoice-2026-08-19" -Name "VO*_provoice.mp3","BedA_provoice_v2.mp3","BedB_provoice_v2.mp3"
```

Expected: exactly these 9 names present (confirmed present as of this plan's writing):
`VO1_provoice.mp3`, `VO2_provoice.mp3`, `VO3_provoice.mp3`, `VO4_provoice.mp3`, `VO5_provoice.mp3`,
`VO6_provoice.mp3`, `VO7_provoice.mp3`, `BedA_provoice_v2.mp3`, `BedB_provoice_v2.mp3`. (Note:
`VO1_provoice_take2.mp3` and `VO7_provoice_take2.mp3` also exist in that directory — these are the
alternate takes explicitly NOT used per spec §4.3; do not substitute them.)

If any of the 9 file names above are missing, STOP and report — do not substitute a differently-named
file without confirming it is the same take.

- [ ] **Step 2: Write the validation harness**

Create `C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711\validate_precondition.py`:

```python
"""Throwaway validation harness for
docs/superpowers/specs/2026-08-19-audio-preconditioning-design.md.

Not stitcher code -- deliberately lives under stitcher/renders/, which the
repo's .gitignore excludes wholesale (.gitignore:43, "renders/"), so it can
never be staged (see the implementation plan's Task 5). Run with:
    python validate_precondition.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(
    0,
    r"C:\Projects\ContentStudio\.claude\worktrees\contentstudio-stitcher-first-short-33bc3c\stitcher",
)

from stitcher import audio as au
from stitcher import ffmpeg
from stitcher import precondition as pc
from stitcher.naming import Workspace
from stitcher.spec import (
    Audio, Bed, BedWindow, Canvas, Fade, Loudness, RenderSpec, SafeZone, Shot, Stem,
)

RENDER_DIR = Path(
    r"C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711"
)
ASSETS_DIR = RENDER_DIR / "assets" / "provoice-2026-08-19"

RUNTIME = 51.920000

# (stem id, raw source filename, absolute `at` offset) -- spec §4.3, take 1
# for VO1/VO7.
VO_STEMS = [
    ("vo1", "VO1_provoice.mp3", 0.000000),
    ("vo2", "VO2_provoice.mp3", 5.200000),
    ("vo3", "VO3_provoice.mp3", 10.800000),
    ("vo4", "VO4_provoice.mp3", 16.240000),
    ("vo5", "VO5_provoice.mp3", 22.560000),
    ("vo6", "VO6_provoice.mp3", 35.840000),
    ("vo7", "VO7_provoice.mp3", 46.480000),
]
BED_A_RAW = ASSETS_DIR / "BedA_provoice_v2.mp3"
BED_B_RAW = ASSETS_DIR / "BedB_provoice_v2.mp3"
BED_A_TRIM_TO = 15.022948  # BedA-relative; spec §4.5
PAUSE_IN = 19.514331
PAUSE_OUT = 20.222948
HOLD_OUT = 5.200000

CONDITION_LUFS = -14.0
CONDITION_TP_DBTP = -2.5
DELIVERY_LUFS = -14.0
DELIVERY_TP_DBTP = -1.0
LRA_BASELINE = 6.10  # measured on the raw pre-processing assembled VO, spec §5 criterion 4


def main() -> None:
    ws = Workspace(root=RENDER_DIR / "_precondition_validation", slug="run", mode="final")
    ws.ensure_dirs()
    log_path = ws.log_path("validate")

    # Step 1 of spec §5's harness: confirm the bed's one window is
    # well-formed and inside the runtime (the manual check standing in for
    # validate_spec, which a minimal audio-only spec cannot satisfy -- spec
    # §5 finding N8). There is only one window in this render, so there is
    # no second window to overlap against -- this asserts the invariant that
    # actually matters here rather than a loop that would vacuously pass
    # with zero iterations if left in its two-or-more-windows form.
    assert PAUSE_IN < PAUSE_OUT <= RUNTIME, "bed window is malformed or runs past the runtime"

    # Condition all 9 raw sources individually (spec §4.2).
    vo_results = []
    for stem_id, filename, at in VO_STEMS:
        out_path = ws.asset(f"{stem_id}_conditioned.wav")
        result = pc.condition_clip(
            ASSETS_DIR / filename, CONDITION_LUFS, CONDITION_TP_DBTP, out_path, log_path
        )
        vo_results.append((stem_id, at, result))
        print(
            f"{stem_id}: {result.input_measurement} -> {result.output_measurement} "
            f"(limited={result.limited}, peak_reduction_db={result.peak_reduction_db:.2f})"
        )

    bed_a_out = ws.asset("BedA_conditioned.wav")
    bed_a_result = pc.condition_clip(
        BED_A_RAW, CONDITION_LUFS, CONDITION_TP_DBTP, bed_a_out, log_path
    )
    bed_b_out = ws.asset("BedB_conditioned.wav")
    bed_b_result = pc.condition_clip(
        BED_B_RAW, CONDITION_LUFS, CONDITION_TP_DBTP, bed_b_out, log_path
    )
    print(f"BedA: {bed_a_result.input_measurement} -> {bed_a_result.output_measurement}")
    print(f"BedB: {bed_b_result.input_measurement} -> {bed_b_result.output_measurement}")

    # Every VO stem must fit inside the runtime (spec §4.3) -- _place_stems'
    # downstream atrim would otherwise silently truncate an overrunning clip.
    for stem_id, at, result in vo_results:
        duration = ffmpeg.probe(result.output).duration
        assert at + duration <= RUNTIME + 1e-3, (
            f"{stem_id} overruns runtime: at={at} duration={duration} runtime={RUNTIME}"
        )

    # Assemble BedFull_provoice_conditioned.wav (spec §4.5): silence prepend
    # + BedA trimmed to BedA-relative [0, BED_A_TRIM_TO] + BedB in full,
    # concatenation only, no crossfade engineering.
    silence = ws.asset("_silence_prepend.wav")
    ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-y", "-f", "lavfi",
         "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{HOLD_OUT:.6f}",
         "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(silence)],
        log_path,
    )
    bed_a_trimmed = ws.asset("_BedA_trimmed.wav")
    ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-y", "-i", str(bed_a_out),
         "-t", f"{BED_A_TRIM_TO:.6f}",
         "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(bed_a_trimmed)],
        log_path,
    )
    bed_full = ws.asset("BedFull_provoice_conditioned.wav")
    ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-y",
         "-i", str(silence), "-i", str(bed_a_trimmed), "-i", str(bed_b_out),
         "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
         "-map", "[out]", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(bed_full)],
        log_path,
    )
    bed_full_duration = ffmpeg.probe(bed_full).duration
    assert bed_full_duration >= RUNTIME, (
        f"BedFull is {bed_full_duration}s, shorter than runtime {RUNTIME}s -- "
        "_build_bed would loop-repeat rather than end cleanly"
    )
    print(f"BedFull duration: {bed_full_duration:.6f}s (runtime {RUNTIME}s)")

    # Minimal RenderSpec (spec §5 step 1). validate_spec() is deliberately
    # NOT called (spec §5 / finding N8) -- the manual window-overlap check
    # above covers the one invariant that matters here.
    spec = RenderSpec(
        spec_version="1.0",
        slug="precondition-validation",
        canvas=Canvas(width=1080, height=1920, fps=30),
        safe_zone=SafeZone(x=90, y=380, width=900, height=1160),
        styles={},
        shots=[Shot(n=1, id="dummy", beat="dummy", start=0.0, end=RUNTIME,
                     source="dummy.png", kind="still")],
        captions_style="dummy",
        audio=Audio(
            stems=[
                Stem(id=stem_id, file=f"{stem_id}_conditioned.wav", at=at, gain_db=0.0)
                for stem_id, at, _ in vo_results
            ],
            bed=Bed(
                file="BedFull_provoice_conditioned.wav",
                gain_db=-22.0,
                duck_db=-29.0,
                windows=[BedWindow(start=PAUSE_IN, end=PAUSE_OUT, mode="out")],
                fades=[
                    Fade(at=PAUSE_IN, kind="out", ms=150),
                    Fade(at=PAUSE_OUT, kind="in", ms=150),
                ],
            ),
            sfx=[],
            loudness=Loudness(integrated_lufs=DELIVERY_LUFS, true_peak_dbtp=DELIVERY_TP_DBTP),
        ),
    )

    result = au.build_audio(spec, ws, "final", log_path, missing_audio=[])

    # --- success criteria, spec §5, checked in order -----------------------
    assert result.loudnorm["normalization_type"] == "linear", (
        f"linear-mode gate failed: {result.loudnorm}"
    )
    print("criteria 1-2 PASS: no exception raised, normalization_type == linear")

    remeasured = ffmpeg.measure_loudness(result.mix, log_path)
    assert abs(remeasured["input_i"] - DELIVERY_LUFS) <= 0.5, remeasured
    assert remeasured["input_tp"] <= DELIVERY_TP_DBTP, remeasured
    print(f"criterion 3 PASS: independent re-measurement of the written mix: {remeasured}")

    lra_deltas = {
        stem_id: r.input_measurement["input_lra"] - r.output_measurement["input_lra"]
        for stem_id, _, r in vo_results
    }
    lra_deltas["BedA"] = bed_a_result.input_measurement["input_lra"] - bed_a_result.output_measurement["input_lra"]
    lra_deltas["BedB"] = bed_b_result.input_measurement["input_lra"] - bed_b_result.output_measurement["input_lra"]
    mean_lra_loss = sum(lra_deltas.values()) / len(lra_deltas)
    print(f"per-clip LRA loss: {lra_deltas}")
    print(f"mean LRA loss: {mean_lra_loss:.2f} LU (gate: <= 1.2)")
    assert mean_lra_loss <= 1.2, lra_deltas
    print("criterion 4 PASS: mean per-clip LRA loss within gate")

    loudness_checks = {stem_id: r for stem_id, _, r in vo_results}
    loudness_checks["BedA"] = bed_a_result
    loudness_checks["BedB"] = bed_b_result
    for name, r in loudness_checks.items():
        delta = abs(r.output_measurement["input_i"] - CONDITION_LUFS)
        assert delta <= pc.LUFS_TOLERANCE, f"{name}: {r.output_measurement} (delta={delta})"
    print("criterion 5 PASS: every clip's conditioned loudness is within LUFS_TOLERANCE")

    deliverable_wav = ASSETS_DIR / "Final_Mix_Preconditioned.wav"
    shutil.copy2(result.mix, deliverable_wav)
    deliverable_mp3 = ASSETS_DIR / "Final_Mix_Preconditioned.mp3"
    ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-y", "-i", str(result.mix),
         "-c:a", "libmp3lame", "-b:a", "192k", str(deliverable_mp3)],
        log_path,
    )
    print(f"All criteria passed.")
    print(f"WAV deliverable: {deliverable_wav}")
    print(f"MP3 deliverable: {deliverable_mp3}")
    print(f"Source LRA baseline (raw, pre-processing, prior run): {LRA_BASELINE} LU")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the harness and capture its full output**

Run: `python "C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711\validate_precondition.py"`

Expected: the script runs to completion printing `criteria 1-2 PASS`, `criterion 3 PASS`,
`criterion 4 PASS`, `criterion 5 PASS`, and the two deliverable paths, with no `AssertionError` and
no `PreconditionError`/`LoudnormNotLinearError` raised. Capture the **entire** stdout — every
per-clip measurement line — for the RESULTS doc in Step 5.

If any assertion fails: STOP. Do not adjust `CONDITION_TP_DBTP` or any other constant to force a
pass — per spec §6, a `LoudnormNotLinearError` here is itself a finding (it would mean the derived
1.5 dB margin was insufficient for this specific mix) and must be reported, not silently routed
around.

- [ ] **Step 4: Listen to the delivered mix**

Play `Final_Mix_Preconditioned.mp3` (or `.wav`) from
`C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711\assets\provoice-2026-08-19\`.
Confirm by ear: no audible "leveling" pumping, no clipping/harshness, the re-hook pause at
19.514331s–20.222948s is inaudible as a pause (masked by the declared fades), and BedB's riser is
audible emerging from the fade at 20.222948s.

- [ ] **Step 5: Write the RESULTS doc**

Create `docs/superpowers/plans/2026-08-19-audio-preconditioning-implementation-RESULTS.md`,
following the format of this session's prior `-RESULTS.md` docs (e.g.
`2026-08-19-fix-bed-vocal-leakage-RESULTS.md`): a short outcome table, the real captured
per-clip/bed measurements and the mean LRA loss from Step 3's stdout, the two deliverable paths,
and a closing **Status: pending user listen-confirmation** line (not resolved until the user
confirms by ear, matching this project's established pattern for audio changes) — updated to
**Status: confirmed clean** only after the user has actually listened and said so, never asserted
in advance.

**Use only numbers Step 3 actually printed — do not copy figures from the design spec's §4.4/§5
prose as if they were this run's results.** The spec's own numbers came from an earlier exploratory
pass (e.g. it quotes `LUFS_TOLERANCE` as "0.3 LU" in one place though the shipped constant is 0.35,
and attributes the single largest measured per-clip LRA loss to VO5 in one draft) — those are
useful as *expectations to sanity-check against*, not as substitutes for this run's actual stdout.
If a real captured number differs materially from what the spec predicted, say so plainly in the
RESULTS doc rather than silently reconciling it.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/plans/2026-08-19-audio-preconditioning-implementation-RESULTS.md
git commit -m "docs(precondition): record the real end-to-end validation run"
```

(The validation script itself is never `git add`-ed — it lives outside this repo's worktree
entirely, per Step 2's path.)

---

## Self-Review

**Spec coverage:**
- §4.1 (module, algorithm, all three retry branches, logging) — Tasks 1–4.
- §4.2 (where it plugs in: per-clip conditioning before `render-spec.json` stem/bed placement) —
  Task 5's harness conditions all 9 raw sources individually before spec construction.
- §4.3 (VO stem placement table, take 1 for VO1/VO7, the `at + duration <= runtime` assertion) —
  Task 5's `VO_STEMS` table and its runtime assertion, copied exactly.
- §4.4 (the two decoupled envelopes, all four constants) — Global Constraints + Task 5's spec
  construction (`CONDITION_*` for `condition_clip` calls, `DELIVERY_*` for `Loudness(...)`).
- §4.5 (silence prepend, BedA trim to 15.022948s, BedA→BedB splice at the pause window's end,
  masked by the declared fade not the window) — Task 5 Step 2's bed-assembly block, with the exact
  trim value and fade positions.
- §5 (validation harness construction, all 5 success criteria in order, independent
  re-measurement, mean-not-per-clip LRA gate) — Task 5 Steps 2–3.
- §6 (`PreconditionError` as a hard stop; `build_audio()`'s own gate untouched and treated as a
  real finding if it fires) — Task 4 + Task 5 Step 3's explicit "do not adjust constants to force a
  pass" instruction.
- §7 (all six named test categories: clean path, peak-retry, loudness-retry, exhausted-retries,
  timing-alignment, output-channel-count) — Tasks 1–4; timing-alignment and output-channel-count
  are asserted inline in Task 1's clean-path test rather than as separate test functions, since
  both are static properties of the one command built on that path (noted explicitly in Task 4
  Step 3).
- §8 (out of scope: no shot re-cut, no `elevenlabs_tooling` changes, no `cmd_render` wiring) —
  confirmed nothing in any task touches those; stated in Global Constraints.

**Placeholder scan:** no TBD/TODO; every code block is complete, runnable code; the one place
numbers are genuinely not yet known (Task 5 Step 5's RESULTS doc content) is explicitly framed as
"captured from the real run's stdout," not invented.

**Type consistency:** `condition_clip(source, target_lufs, target_tp_dbtp, out_path, log_path) ->
ConditionResult` is identical across Task 1's implementation, Tasks 2–4's tests, and Task 5's five
call sites. `ConditionResult.{input_measurement, output_measurement, limited, peak_reduction_db}`
field names match everywhere they're read (Tasks 1–4's assertions, Task 5's LRA-delta and
loudness-check dicts). `PreconditionError`/`MAX_ATTEMPTS`/`LUFS_TOLERANCE` are referenced via `pc.`
consistently.

---

## Execution Handoff

Plan complete and saved to
`docs/superpowers/plans/2026-08-19-audio-preconditioning-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks,
fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with
checkpoints

**Which approach?**
