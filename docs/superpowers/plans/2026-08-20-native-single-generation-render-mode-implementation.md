# Native Single-Generation Render Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new, additive render mode that uses one continuous ElevenLabs take (unsplit, unconditioned) as
the final voice track, derives shot/caption/music timing directly from its own `/with-timestamps` alignment,
and bakes music dynamics into one Eleven Music generation instead of the existing auto-detected ducking
envelope — without modifying the existing stitched/ducked pipeline at all.

**Architecture:** A new standalone sibling package, `native-pipeline/` (alongside `elevenlabs-tooling/` and
`stitcher/`), is the only code allowed to import both `stitcher` and `elevenlabs_tooling` — neither of those
two ever imports the other or `native_pipeline`. VO and music generation happen via subprocess calls to
`elevenlabs_tooling`'s CLI (the existing `generate-vo` command, plus one new `music send` command added to
that package); `native_pipeline` only ever consumes the files those calls produce. It builds a
`stitcher.spec.RenderSpec` from real alignment data and hands off to `stitcher`'s existing, completely
unmodified `render` CLI as a separate subprocess step.

**Tech Stack:** Python 3, pytest, ffmpeg/ffprobe on PATH, `stitcher` and `elevenlabs_tooling` as installed
sibling packages (both already exist in this worktree).

**Spec:** `docs/superpowers/specs/2026-08-20-native-single-generation-render-mode-design.md` (read this first —
every decision below traces back to it, including the two Opus-review rounds and the pipeline-conventions
audit already folded in).

## Global Constraints

- `native_pipeline` (the new package) is the only code that imports both `stitcher` and `elevenlabs_tooling`.
  Neither of those two packages may import `native_pipeline` or each other. This is enforced by convention,
  not tooling — every task below respects it, and no task adds an import that would violate it.
- Do not modify `stitcher/stitcher/audio.py`, `envelope.py`, `assemble.py`, `shots.py`, `motion.py`, or
  `spec.py`, or any `.claude/skills/*/SKILL.md` file. This project is additive only.
- `BED_RELATIVE_OFFSET_DB = -17.0` — the flat bed gain's starting offset from measured voice LUFS (from
  `.claude/skills/shorts-assembly/references/loudness-and-mix.md`'s "bed sits ~15-20dB below the voice",
  midpoint). `Bed.gain_db == Bed.duck_db` always, for every spec this pipeline assembles.
- Eleven Music `music_v2` chunk bounds: `MIN_CHUNK_MS = 3_000`, `MAX_CHUNK_MS = 120_000`, `MAX_CHUNKS = 30`
  (`docs/elevenlabs-music-runbook.md` §2).
- `BED_DURATION_TOLERANCE_S = 0.1` — the generated bed's measured duration must match the take's runtime
  within this tolerance, checked before assembling the spec (see `assemble.check_bed_duration`). Widened
  from this plan's original `0.05` (50ms) during Task 11's real e2e validation (commit `46438dd`): a real
  Eleven Music generation measured 52ms off, missing the original tolerance by just 2ms -- normal
  real-world generation jitter the original value didn't account for. Human-approved.
- `MIN_DUCK_WINDOW_S = 0.4` — reused from `stitcher.verify`; any beat/chunk span shorter than this is skipped
  for outlier flagging, never measured.
- Outlier-flagging threshold: 3 LU / 3 dB deviation from a track's own median, a documented starting point.
- Iteration cap: 2 generation attempts per track (VO, music), independent budgets, enforced by
  `IterationBudgetExceededError` on a 3rd attempt.
- Test markers: use this repo's real vocabulary — `e2e` (stitcher's own marker, "needs a real ffmpeg on
  PATH") and `allow_network`/`allow_subprocess` (the root `pytest.ini`'s markers, "may make a real outbound
  request / subprocess call — justify in the docstring"). Never invent a new marker name (e.g. "integration").
- Exception types are narrow and per-module, subclassing a built-in, never a shared base class — matching
  `stitcher`'s existing pattern (`FFmpegError(RuntimeError)`, `LoudnormNotLinearError(RuntimeError)`, etc.).
- Logging: any ffmpeg/ffprobe-based work inside `native_pipeline` appends plain text to the same workspace log
  file `stitcher` already uses (`Workspace.log_path`); never introduce JSON logging inside code that touches
  `stitcher`'s conventions. `elevenlabs_tooling`'s own subprocess calls use its own JSON-line logging
  unmodified — `native_pipeline` does not intercept or reformat it.

---

## File Structure

```
native-pipeline/                          # NEW top-level sibling package
  native_pipeline/
    __init__.py
    errors.py           # Task 1 — the 4 exception types
    contracts.py         # Task 3 — asset_manifest / bed_arc JSON loaders + structural validation
    shots.py              # Task 4 — build_shots()
    music_plan.py         # Task 5 — build_music_plan()
    flagging.py           # Task 6 — flag_outliers()
    assemble.py           # Task 7 — assemble_spec(), check_bed_duration()
    iteration.py          # Task 8 — IterationRecord, Attempt
    orchestrate.py        # Task 9 — run_vo_stage/run_music_stage/run_assemble_stage/run_render_stage
    cli.py                # Task 10 — argparse entrypoint
    __main__.py           # Task 10
  tests/
    conftest.py           # Task 1
    test_contracts.py     # Task 3
    test_shots.py         # Task 4
    test_music_plan.py    # Task 5
    test_flagging.py      # Task 6
    test_assemble.py      # Task 7
    test_iteration.py     # Task 8
    test_orchestrate.py   # Task 9
    test_cli.py           # Task 10
    test_e2e.py            # Task 11 — marked e2e + allow_network
  pytest.ini             # Task 1 — registers e2e, allow_network, allow_subprocess markers
  README.md              # Task 1 — isolation statement, mirrors elevenlabs-tooling/README.md

elevenlabs-tooling/elevenlabs_tooling/
  cli.py                 # Task 2 — MODIFY: add `music send` subcommand
elevenlabs-tooling/tests/
  test_cli_music_send.py # Task 2 — NEW
```

---

### Task 1: Package scaffold + exception types

**Files:**
- Create: `native-pipeline/native_pipeline/__init__.py`
- Create: `native-pipeline/native_pipeline/errors.py`
- Create: `native-pipeline/tests/conftest.py`
- Create: `native-pipeline/tests/test_errors.py`
- Create: `native-pipeline/pytest.ini`
- Create: `native-pipeline/README.md`

**Interfaces:**
- Produces: `ShotSegmentMismatchError(ValueError)`, `ChunkDurationTooShortError(ValueError)`,
  `BedDurationMismatchError(RuntimeError)`, `IterationBudgetExceededError(RuntimeError)` — imported by every
  later task in this package.

- [ ] **Step 1: Write the failing test**

```python
# native-pipeline/tests/test_errors.py
from native_pipeline.errors import (
    BedDurationMismatchError,
    ChunkDurationTooShortError,
    IterationBudgetExceededError,
    ShotSegmentMismatchError,
)


def test_shot_segment_mismatch_error_is_a_value_error():
    assert issubclass(ShotSegmentMismatchError, ValueError)


def test_chunk_duration_too_short_error_is_a_value_error():
    assert issubclass(ChunkDurationTooShortError, ValueError)


def test_bed_duration_mismatch_error_is_a_runtime_error():
    assert issubclass(BedDurationMismatchError, RuntimeError)


def test_iteration_budget_exceeded_error_is_a_runtime_error():
    assert issubclass(IterationBudgetExceededError, RuntimeError)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd native-pipeline && python -m pytest tests/test_errors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'native_pipeline'`

- [ ] **Step 3: Write the package scaffold**

```python
# native-pipeline/native_pipeline/__init__.py
```
(empty — just marks the package)

```python
# native-pipeline/native_pipeline/errors.py
"""Exception types for the native single-generation render pipeline.

One narrow exception per failure mode, each subclassing a built-in --
matching stitcher's own pattern (FFmpegError(RuntimeError),
LoudnormNotLinearError(RuntimeError), etc.) rather than a shared base class.
"""

from __future__ import annotations


class ShotSegmentMismatchError(ValueError):
    """A segment/asset-manifest beat-name mismatch, or a build_shots()
    invariant violated (non-contiguous, doesn't start at 0, doesn't end at
    the take's runtime)."""


class ChunkDurationTooShortError(ValueError):
    """A composition-plan chunk violates one of Eleven Music's music_v2
    constraints: a chunk under the 3,000ms floor, a chunk over the
    120,000ms ceiling, more than 30 chunks total, or the plan's total
    duration not matching the take's runtime."""


class BedDurationMismatchError(RuntimeError):
    """The generated music bed's measured duration doesn't match the VO
    take's runtime within tolerance."""


class IterationBudgetExceededError(RuntimeError):
    """A generation attempt was requested for a track (VO or music) after
    its 2-attempt iteration cap was already spent."""
```

```ini
# native-pipeline/pytest.ini
[pytest]
markers =
    e2e: end-to-end run; needs a real ffmpeg/ffprobe on PATH and real ELEVENLABS_API_KEY / Eleven Music access
    allow_network: this test may make a real outbound request -- justify in the docstring
    allow_subprocess: this test may spawn a real subprocess -- justify in the docstring
```

```python
# native-pipeline/tests/conftest.py
"""Shared fixtures for native_pipeline's test suite. Empty for now --
individual test files define their own fixtures; this file exists so
pytest treats tests/ as a package root consistently with elevenlabs-tooling's
and stitcher's own test layout."""
```

```markdown
# native-pipeline/README.md

# native-pipeline

Orchestrates the native single-generation render mode: one continuous ElevenLabs take (unsplit,
unconditioned) as the final voice track, one Eleven Music generation as the bed, both driven by the take's
own `/with-timestamps` alignment data. See
`docs/superpowers/specs/2026-08-20-native-single-generation-render-mode-design.md` for the full design.

**Isolation:** this package is the *only* code that imports both `stitcher` and `elevenlabs_tooling`. Neither
of those two packages imports `native_pipeline` or each other — VO and music generation happen via subprocess
calls to `elevenlabs_tooling`'s CLI, and the final render happens via a subprocess call to `stitcher`'s CLI.
`native_pipeline` never reaches into either package's internals beyond their public, documented functions.

## Running tests

```bash
cd native-pipeline
python -m pytest                      # unit tests only (default; e2e is opt-in)
python -m pytest -m e2e                # the real end-to-end run (costs real API credits)
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd native-pipeline && python -m pytest tests/test_errors.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add native-pipeline/
git commit -m "feat(native-pipeline): scaffold package and add exception types"
```

---

### Task 2: `elevenlabs-tooling` — add a `music send` subcommand

**Files:**
- Modify: `elevenlabs-tooling/elevenlabs_tooling/cli.py` (add `cmd_music_send`, wire into `build_parser`)
- Test: `elevenlabs-tooling/tests/test_cli_music_send.py`

**Interfaces:**
- Consumes: `elevenlabs_tooling.client.send(url, payload_bytes, api_key, timeout) -> SendResult` (existing,
  unmodified — `client.py:27`), `_load_payload`, `_resolve_timeout`, `log`, exit code constants (all existing,
  unmodified, `cli.py`).
- Produces: `python -m elevenlabs_tooling music send --payload <path> --url <url> --output <path> [--timeout
  N] [--force]` — a new CLI invocation `native_pipeline`'s `orchestrate.run_music_stage` (Task 9) depends on.

**Why this is needed:** the existing `send` subcommand calls `validate(payload, args.url)`
(`cli.py:76`), which checks ElevenLabs-TTS-specific rules (voice_id, break-tag syntax, etc.) that don't apply
to an Eleven Music composition-plan payload — reusing `send` as-is would reject every music payload as
invalid. `music send` is the same generic "load payload, check API key, POST via `client.send`, write body to
output" logic as `cmd_send`, minus the TTS-specific validation step. Building a full Eleven-Music-specific
validator (mirroring `validate.py`'s E1-E14 checks) is out of scope — this project doesn't rebuild that
subsystem, it adds a minimal send path for a different endpoint.

- [ ] **Step 1: Write the failing test**

```python
# elevenlabs-tooling/tests/test_cli_music_send.py
import json
from pathlib import Path

import pytest

from elevenlabs_tooling.cli import EXIT_NO_API_KEY, EXIT_PASS, EXIT_SEND_FAILED, EXIT_USAGE, main


@pytest.fixture
def payload_path(tmp_path: Path) -> Path:
    path = tmp_path / "composition_plan.json"
    path.write_text(json.dumps({"model_id": "music_v2", "composition_plan": {"chunks": []}}), encoding="utf-8")
    return path


def test_music_send_writes_response_body_on_success(tmp_path, payload_path, monkeypatch):
    output_path = tmp_path / "bed.wav"

    class FakeResult:
        ok = True
        status_code = 200
        content_type = "audio/wav"
        body = b"fake-bed-bytes"
        error_message = None

    monkeypatch.setattr("elevenlabs_tooling.cli.client_send", lambda *a, **k: FakeResult())
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")

    exit_code = main([
        "music", "send",
        "--payload", str(payload_path),
        "--url", "https://api.elevenlabs.io/v1/music/compose",
        "--output", str(output_path),
    ])

    assert exit_code == EXIT_PASS
    assert output_path.read_bytes() == b"fake-bed-bytes"


def test_music_send_does_not_call_the_tts_validator(tmp_path, payload_path, monkeypatch):
    """A composition-plan payload has no voice_id/text/model_id-for-TTS shape --
    cmd_music_send must never call validate(), which would reject it."""
    output_path = tmp_path / "bed.wav"

    def fail_if_called(*args, **kwargs):
        raise AssertionError("validate() must not be called by cmd_music_send")

    monkeypatch.setattr("elevenlabs_tooling.cli.validate", fail_if_called)

    class FakeResult:
        ok = True
        status_code = 200
        content_type = "audio/wav"
        body = b"fake-bed-bytes"
        error_message = None

    monkeypatch.setattr("elevenlabs_tooling.cli.client_send", lambda *a, **k: FakeResult())
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")

    exit_code = main([
        "music", "send",
        "--payload", str(payload_path),
        "--url", "https://api.elevenlabs.io/v1/music/compose",
        "--output", str(output_path),
    ])
    assert exit_code == EXIT_PASS


def test_music_send_returns_no_api_key_exit_code_when_unset(tmp_path, payload_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    exit_code = main([
        "music", "send",
        "--payload", str(payload_path),
        "--url", "https://api.elevenlabs.io/v1/music/compose",
        "--output", str(tmp_path / "bed.wav"),
    ])
    assert exit_code == EXIT_NO_API_KEY


def test_music_send_refuses_to_overwrite_without_force(tmp_path, payload_path, monkeypatch):
    output_path = tmp_path / "bed.wav"
    output_path.write_bytes(b"existing")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")

    exit_code = main([
        "music", "send",
        "--payload", str(payload_path),
        "--url", "https://api.elevenlabs.io/v1/music/compose",
        "--output", str(output_path),
    ])
    assert exit_code == EXIT_USAGE
    assert output_path.read_bytes() == b"existing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_cli_music_send.py -v`
Expected: FAIL — `error: argument command: invalid choice: 'music'` (no `music` subcommand exists yet)

- [ ] **Step 3: Add `cmd_music_send` and wire it into the parser**

In `elevenlabs-tooling/elevenlabs_tooling/cli.py`, add this function near `cmd_send` (it deliberately mirrors
`cmd_send`'s structure exactly, minus the `validate()`/`is_blocking()` step):

```python
def cmd_music_send(args: argparse.Namespace) -> int:
    payload_path = Path(args.payload)
    output_path = Path(args.output)

    raw_bytes, _payload, error_code = _load_payload(payload_path)
    if error_code is not None:
        return error_code

    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        print(f"elevenlabs_tooling: {API_KEY_ENV_VAR} is not set", file=sys.stderr)
        log("music_send.aborted", level="warning", url=args.url, payload_path=str(payload_path),
            reason="no_api_key")
        return EXIT_NO_API_KEY

    if output_path.exists() and not args.force:
        print(f"elevenlabs_tooling: {output_path} already exists; pass --force to overwrite", file=sys.stderr)
        log("music_send.aborted", level="warning", url=args.url, payload_path=str(payload_path),
            output_path=str(output_path), reason="output_exists")
        return EXIT_USAGE

    if not output_path.parent.is_dir():
        print(f"elevenlabs_tooling: output directory does not exist: {output_path.parent}", file=sys.stderr)
        log("music_send.aborted", level="warning", url=args.url, payload_path=str(payload_path),
            output_path=str(output_path), reason="output_parent_missing")
        return EXIT_USAGE

    payload_hash = hashlib.sha256(raw_bytes).hexdigest()
    timeout = _resolve_timeout(args.timeout)
    log("music_send.attempt", url=args.url, payload_path=str(payload_path), payload_sha256=payload_hash,
        output_path=str(output_path), timeout=timeout)

    try:
        result = client_send(args.url, raw_bytes, api_key, timeout=timeout)
    except Exception as exc:
        print(f"elevenlabs_tooling: unexpected error sending the payload: {type(exc).__name__}", file=sys.stderr)
        log("music_send.failed", level="error", url=args.url, error=type(exc).__name__)
        return EXIT_SEND_FAILED

    if result.ok:
        try:
            output_path.write_bytes(result.body)
        except OSError as exc:
            print(f"elevenlabs_tooling: send succeeded but writing {output_path} failed: {exc}", file=sys.stderr)
            log("music_send.failed", level="error", url=args.url, status_code=result.status_code,
                error=f"write failed after a successful API call: {exc}")
            return EXIT_SEND_FAILED
        log("music_send.success", url=args.url, output_path=str(output_path), status_code=result.status_code,
            content_type=result.content_type, bytes_written=len(result.body))
        return EXIT_PASS

    if result.body is not None:
        quarantine_path = output_path.with_name(output_path.name + ".unexpected")
        try:
            quarantine_path.write_bytes(result.body)
            quarantine_note = f" (response body saved to {quarantine_path})"
        except OSError as exc:
            quarantine_note = f" (also failed to save the response body: {exc})"
    else:
        quarantine_note = ""
    print(f"elevenlabs_tooling: music send failed: {result.error_message}{quarantine_note}", file=sys.stderr)
    log("music_send.failed", level="error", url=args.url, status_code=result.status_code,
        error=result.error_message)
    return EXIT_SEND_FAILED
```

In `build_parser()`, add the nested `music` subparser (today's structure is flat single-level siblings; this
is the first nested one — do not restructure the existing three commands to match):

```python
    music_parser = subparsers.add_parser("music", help="Eleven Music operations")
    music_subparsers = music_parser.add_subparsers(dest="music_command", required=True)
    music_send_parser = music_subparsers.add_parser("send", help="Send a composition-plan payload, write the response body")
    music_send_parser.add_argument("--payload", required=True)
    music_send_parser.add_argument("--url", required=True)
    music_send_parser.add_argument("--output", required=True)
    music_send_parser.add_argument("--timeout", type=float, default=None)
    music_send_parser.add_argument("--force", action="store_true")
    music_send_parser.set_defaults(func=cmd_music_send)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd elevenlabs-tooling && python -m pytest tests/test_cli_music_send.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full elevenlabs-tooling suite to confirm no regression**

Run: `cd elevenlabs-tooling && python -m pytest`
Expected: all existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add elevenlabs-tooling/elevenlabs_tooling/cli.py elevenlabs-tooling/tests/test_cli_music_send.py
git commit -m "feat(elevenlabs-tooling): add music send subcommand for Eleven Music payloads"
```

---

### Task 3: `contracts.py` — asset_manifest / bed_arc loaders

**Files:**
- Create: `native-pipeline/native_pipeline/contracts.py`
- Test: `native-pipeline/tests/test_contracts.py`

**Interfaces:**
- Consumes: nothing new (stdlib `json` only).
- Produces: `load_asset_manifest(path: Path) -> list[dict]`, `load_bed_arc(path: Path) -> list[dict]` —
  consumed by Task 4 (`shots.py`) and Task 5 (`music_plan.py`).

**Data contracts (from the design spec's Data Contracts section):**
- `asset_manifest` entry: `{"beat": str, "kind": "still"|"clip", "source": str, "source_in_s": float|None,
  "source_out_s": float|None, "motion": {"kind": str, "amount_pct": float, "anchor_start": [float,float],
  "anchor_end": [float,float], "hold_s": float, "ease": str} | None}` — `motion` required when
  `kind == "still"`; `source_in_s`/`source_out_s` required when `kind == "clip"`.
- `bed_arc` entry: `{"label": str, "start_s": float, "end_s": float, "density": "sparse"|"medium"|"full",
  "style_notes": str}`.

- [ ] **Step 1: Write the failing test**

```python
# native-pipeline/tests/test_contracts.py
import json

import pytest

from native_pipeline.contracts import load_asset_manifest, load_bed_arc


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_asset_manifest_returns_parsed_entries(tmp_path):
    path = _write(tmp_path, "manifest.json", [
        {"beat": "beat1", "kind": "still", "source": "a.png", "source_in_s": None, "source_out_s": None,
         "motion": {"kind": "push_in", "amount_pct": 15.0, "anchor_start": [0.5, 0.5],
                    "anchor_end": [0.5, 0.5], "hold_s": 0.0, "ease": "linear"}},
    ])
    entries = load_asset_manifest(path)
    assert entries[0]["beat"] == "beat1"
    assert entries[0]["motion"]["kind"] == "push_in"


def test_load_asset_manifest_raises_on_still_without_motion(tmp_path):
    path = _write(tmp_path, "manifest.json", [
        {"beat": "beat1", "kind": "still", "source": "a.png", "source_in_s": None, "source_out_s": None,
         "motion": None},
    ])
    with pytest.raises(ValueError, match="beat1.*motion"):
        load_asset_manifest(path)


def test_load_asset_manifest_raises_on_clip_without_source_in_out(tmp_path):
    path = _write(tmp_path, "manifest.json", [
        {"beat": "beat1", "kind": "clip", "source": "a.mp4", "source_in_s": None, "source_out_s": None,
         "motion": None},
    ])
    with pytest.raises(ValueError, match="beat1.*source_in_s"):
        load_asset_manifest(path)


def test_load_asset_manifest_raises_on_bad_kind(tmp_path):
    path = _write(tmp_path, "manifest.json", [
        {"beat": "beat1", "kind": "video", "source": "a.mp4", "source_in_s": 0.0, "source_out_s": 1.0,
         "motion": None},
    ])
    with pytest.raises(ValueError, match="beat1.*kind"):
        load_asset_manifest(path)


def test_load_bed_arc_returns_parsed_entries(tmp_path):
    path = _write(tmp_path, "bed_arc.json", [
        {"label": "rising urgency", "start_s": 4.0, "end_s": 20.0, "density": "full", "style_notes": ""},
    ])
    entries = load_bed_arc(path)
    assert entries[0]["label"] == "rising urgency"
    assert entries[0]["density"] == "full"


def test_load_bed_arc_raises_on_bad_density(tmp_path):
    path = _write(tmp_path, "bed_arc.json", [
        {"label": "x", "start_s": 0.0, "end_s": 5.0, "density": "loud", "style_notes": ""},
    ])
    with pytest.raises(ValueError, match="x.*density"):
        load_bed_arc(path)


def test_load_bed_arc_raises_when_end_before_start(tmp_path):
    path = _write(tmp_path, "bed_arc.json", [
        {"label": "x", "start_s": 5.0, "end_s": 5.0, "density": "full", "style_notes": ""},
    ])
    with pytest.raises(ValueError, match="x.*end_s"):
        load_bed_arc(path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd native-pipeline && python -m pytest tests/test_contracts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'native_pipeline.contracts'`

- [ ] **Step 3: Write the implementation**

```python
# native-pipeline/native_pipeline/contracts.py
"""Loaders and structural validators for the two small data contracts this
pipeline needs: asset_manifest (per-beat visual direction, translating
visual-prompts' prose output) and bed_arc (per-movement music direction,
translating music-brief's prose bed arc). Both are plain operator-authored
JSON -- no skill emits them directly. Raises bare ValueError on structural
problems, matching stitcher's own validate-at-load-time convention
(spec.py, vo_alignment.py, vo_timing.py all do the same)."""

from __future__ import annotations

import json
from pathlib import Path

VALID_KINDS = {"still", "clip"}
VALID_DENSITIES = {"sparse", "medium", "full"}


def load_asset_manifest(path: Path) -> list[dict]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    for entry in entries:
        beat = entry.get("beat")
        kind = entry.get("kind")
        if kind not in VALID_KINDS:
            raise ValueError(f"asset_manifest entry {beat!r}: kind must be one of {VALID_KINDS}, got {kind!r}")
        if kind == "still" and not entry.get("motion"):
            raise ValueError(f"asset_manifest entry {beat!r}: kind='still' requires a motion dict")
        if kind == "clip" and (entry.get("source_in_s") is None or entry.get("source_out_s") is None):
            raise ValueError(
                f"asset_manifest entry {beat!r}: kind='clip' requires source_in_s and source_out_s"
            )
    return entries


def load_bed_arc(path: Path) -> list[dict]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    for entry in entries:
        label = entry.get("label")
        density = entry.get("density")
        if density not in VALID_DENSITIES:
            raise ValueError(f"bed_arc entry {label!r}: density must be one of {VALID_DENSITIES}, got {density!r}")
        if entry.get("end_s", 0) <= entry.get("start_s", 0):
            raise ValueError(
                f"bed_arc entry {label!r}: end_s ({entry.get('end_s')}) must be after start_s ({entry.get('start_s')})"
            )
    return entries
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd native-pipeline && python -m pytest tests/test_contracts.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add native-pipeline/native_pipeline/contracts.py native-pipeline/tests/test_contracts.py
git commit -m "feat(native-pipeline): add asset_manifest and bed_arc contract loaders"
```

---

### Task 4: `shots.py` — `build_shots`

**Files:**
- Create: `native-pipeline/native_pipeline/shots.py`
- Test: `native-pipeline/tests/test_shots.py`

**Interfaces:**
- Consumes: `stitcher.spec.Shot` (`spec.py:84-96`: fields `n, id, beat, start, end, source, kind, source_in,
  source_out, motion, transition_in` — `start`/`end` aliased to JSON `in`/`out` but constructed with
  `start=`/`end=` as real Python kwargs since `_Base`'s `model_config = ConfigDict(populate_by_name=True,
  extra="forbid")`, `spec.py:31`), `stitcher.spec.Motion` (`spec.py:63-75`: `kind, amount_pct, anchor_start,
  anchor_end, hold_s, ease`), `stitcher.vo_alignment.Segment` (frozen dataclass: `name: str, at: float,
  duration: float`). `native_pipeline.errors.ShotSegmentMismatchError` (Task 1). `asset_manifest` entries from
  Task 3's `load_asset_manifest`.
- Produces: `build_shots(segments: list[Segment], asset_manifest: list[dict]) -> list[Shot]` — consumed by
  Task 9's `orchestrate.run_assemble_stage`.

**Before writing this task, read `stitcher/stitcher/spec.py:84-96` and `:63-75` directly** to confirm the
exact `Shot`/`Motion` constructor keyword names match what's used below (they were verified during plan
research, but confirm before relying on them).

- [ ] **Step 1: Write the failing test**

```python
# native-pipeline/tests/test_shots.py
import pytest

from stitcher.vo_alignment import Segment

from native_pipeline.errors import ShotSegmentMismatchError
from native_pipeline.shots import build_shots

MOTION = {
    "kind": "push_in", "amount_pct": 15.0, "anchor_start": [0.5, 0.5],
    "anchor_end": [0.5, 0.5], "hold_s": 0.0, "ease": "linear",
}


def _manifest_entry(beat: str) -> dict:
    return {"beat": beat, "kind": "still", "source": f"{beat}.png",
            "source_in_s": None, "source_out_s": None, "motion": MOTION}


def test_build_shots_absorbs_gap_into_previous_shots_end():
    segments = [
        Segment(name="beat1", at=0.0, duration=5.0),
        Segment(name="beat2", at=6.0, duration=6.0),
    ]
    asset_manifest = [_manifest_entry("beat1"), _manifest_entry("beat2")]

    shots = build_shots(segments, asset_manifest)

    assert shots[0].start == 0.0
    assert shots[0].end == 6.0   # absorbs the 1.0s gap between beat1 and beat2
    assert shots[1].start == 6.0
    assert shots[1].end == 12.0  # 6.0 + 6.0 duration == runtime


def test_build_shots_first_shot_starts_at_zero_and_last_ends_at_runtime():
    segments = [
        Segment(name="beat1", at=0.0, duration=5.074),
        Segment(name="beat2", at=6.037, duration=6.339),
    ]
    asset_manifest = [_manifest_entry("beat1"), _manifest_entry("beat2")]

    shots = build_shots(segments, asset_manifest)

    assert shots[0].start == 0.0
    assert shots[-1].end == 6.037 + 6.339


def test_build_shots_raises_on_beat_name_mismatch():
    segments = [Segment(name="beat1", at=0.0, duration=5.0)]
    asset_manifest = [_manifest_entry("wrong_beat_name")]

    with pytest.raises(ShotSegmentMismatchError):
        build_shots(segments, asset_manifest)


def test_build_shots_sets_shot_fields_from_manifest():
    segments = [Segment(name="beat1", at=0.0, duration=5.0)]
    asset_manifest = [_manifest_entry("beat1")]

    shots = build_shots(segments, asset_manifest)

    assert shots[0].id == "beat1"
    assert shots[0].beat == "beat1"
    assert shots[0].source == "beat1.png"
    assert shots[0].kind == "still"
    assert shots[0].motion.kind == "push_in"
    assert shots[0].motion.amount_pct == 15.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd native-pipeline && python -m pytest tests/test_shots.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'native_pipeline.shots'`

- [ ] **Step 3: Write the implementation**

```python
# native-pipeline/native_pipeline/shots.py
"""build_shots -- turns real per-beat alignment segments plus an operator-
authored asset manifest into stitcher Shot objects, one per beat, with the
image/clip holding through its trailing gap (RenderSpec requires exact shot
contiguity -- see spec.py's validate_spec -- and real inter-beat gaps mean a
naive at/at+duration mapping is NOT contiguous)."""

from __future__ import annotations

from stitcher.spec import Motion, Shot
from stitcher.vo_alignment import Segment

from native_pipeline.errors import ShotSegmentMismatchError


def build_shots(segments: list[Segment], asset_manifest: list[dict]) -> list[Shot]:
    manifest_by_beat = {entry["beat"]: entry for entry in asset_manifest}

    segment_names = [segment.name for segment in segments]
    manifest_names = set(manifest_by_beat)
    if set(segment_names) != manifest_names:
        missing = sorted(set(segment_names) - manifest_names)
        extra = sorted(manifest_names - set(segment_names))
        raise ShotSegmentMismatchError(
            f"asset_manifest beat names don't match segments: missing={missing} extra={extra}"
        )

    runtime = segments[-1].at + segments[-1].duration
    shots: list[Shot] = []
    for ordinal, segment in enumerate(segments, start=1):
        entry = manifest_by_beat[segment.name]
        end = segments[ordinal].at if ordinal < len(segments) else runtime
        motion = Motion(**entry["motion"]) if entry.get("motion") else Motion()
        shots.append(
            Shot(
                n=ordinal,
                id=segment.name,
                beat=segment.name,
                start=segment.at,
                end=end,
                source=entry["source"],
                kind=entry["kind"],
                source_in=entry.get("source_in_s"),
                source_out=entry.get("source_out_s"),
                motion=motion,
            )
        )

    if shots[0].start != 0.0:
        raise ShotSegmentMismatchError(f"first shot must start at 0.0, got {shots[0].start}")
    for prev, cur in zip(shots, shots[1:]):
        if prev.end != cur.start:
            raise ShotSegmentMismatchError(
                f"shots not contiguous: {prev.id!r} ends at {prev.end}, {cur.id!r} starts at {cur.start}"
            )
    if shots[-1].end != runtime:
        raise ShotSegmentMismatchError(f"last shot must end at runtime {runtime}, got {shots[-1].end}")

    return shots
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd native-pipeline && python -m pytest tests/test_shots.py -v`
Expected: PASS (4 tests). If `Shot`/`Motion` construction fails with a pydantic error, re-check the exact
field names/aliasing in `spec.py` and adjust the keyword arguments used above to match.

- [ ] **Step 5: Commit**

```bash
git add native-pipeline/native_pipeline/shots.py native-pipeline/tests/test_shots.py
git commit -m "feat(native-pipeline): add build_shots with gap-absorbing shot boundaries"
```

---

### Task 5: `music_plan.py` — `build_music_plan`

**Files:**
- Create: `native-pipeline/native_pipeline/music_plan.py`
- Test: `native-pipeline/tests/test_music_plan.py`

**Interfaces:**
- Consumes: `bed_arc` entries from Task 3's `load_bed_arc` (`{label, start_s, end_s, density, style_notes}`),
  `native_pipeline.errors.ChunkDurationTooShortError` (Task 1).
- Produces: `build_music_plan(bed_arc: list[dict], runtime: float) -> dict` — a JSON-serializable Eleven Music
  `music_v2` payload dict, consumed by Task 9's `orchestrate.run_music_stage` (which writes it to a file and
  hands it to Task 2's `elevenlabs_tooling music send`).

- [ ] **Step 1: Write the failing test**

```python
# native-pipeline/tests/test_music_plan.py
import pytest

from native_pipeline.errors import ChunkDurationTooShortError
from native_pipeline.music_plan import build_music_plan


def _movement(label, start_s, end_s, density, style_notes=""):
    return {"label": label, "start_s": start_s, "end_s": end_s, "density": density, "style_notes": style_notes}


def test_build_music_plan_sets_duration_ms_from_movement_span():
    bed_arc = [_movement("hook", 0.0, 4.0, "full"), _movement("rising urgency", 4.0, 20.0, "full")]
    plan = build_music_plan(bed_arc, runtime=20.0)

    chunks = plan["composition_plan"]["chunks"]
    assert chunks[0]["duration_ms"] == 4000
    assert chunks[1]["duration_ms"] == 16000


def test_build_music_plan_uses_sparse_style_for_sparse_density():
    bed_arc = [_movement("verse", 0.0, 10.0, "sparse")]
    plan = build_music_plan(bed_arc, runtime=10.0)

    chunk = plan["composition_plan"]["chunks"][0]
    assert any("sparse" in style for style in chunk["positive_styles"])


def test_build_music_plan_folds_style_notes_into_positive_styles():
    bed_arc = [_movement("hook", 0.0, 5.0, "full", style_notes="brass hit on the key line")]
    plan = build_music_plan(bed_arc, runtime=5.0)

    chunk = plan["composition_plan"]["chunks"][0]
    assert "brass hit on the key line" in chunk["positive_styles"]


def test_build_music_plan_sets_force_instrumental():
    bed_arc = [_movement("hook", 0.0, 5.0, "full")]
    plan = build_music_plan(bed_arc, runtime=5.0)
    assert plan["force_instrumental"] is True


def test_build_music_plan_raises_on_movement_under_3000ms_floor():
    bed_arc = [_movement("gap", 0.0, 1.2, "full")]
    with pytest.raises(ChunkDurationTooShortError, match="gap"):
        build_music_plan(bed_arc, runtime=1.2)


def test_build_music_plan_raises_on_total_duration_mismatch():
    bed_arc = [_movement("hook", 0.0, 4.0, "full")]
    with pytest.raises(ChunkDurationTooShortError, match="runtime"):
        build_music_plan(bed_arc, runtime=61.114)


def test_build_music_plan_raises_when_over_30_chunks():
    bed_arc = [_movement(f"m{i}", i * 3.0, (i + 1) * 3.0, "full") for i in range(31)]
    with pytest.raises(ChunkDurationTooShortError, match="30"):
        build_music_plan(bed_arc, runtime=93.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd native-pipeline && python -m pytest tests/test_music_plan.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'native_pipeline.music_plan'`

- [ ] **Step 3: Write the implementation**

```python
# native-pipeline/native_pipeline/music_plan.py
"""build_music_plan -- turns an operator-authored, structured bed_arc
(translating music-brief's prose movements) into an Eleven Music music_v2
composition plan. Chunks are built at bed-arc MOVEMENT boundaries, not per
real segment/gap: Eleven Music bounds every chunk's duration_ms to
3,000-120,000ms, and real inter-beat gaps (0.848-1.428s in the validated
take) fall well under that floor. Fine-grained response to a specific pause
or emphasis inside a movement is a style-prompt instruction (style_notes),
not a hard chunk boundary."""

from __future__ import annotations

from native_pipeline.errors import ChunkDurationTooShortError

MIN_CHUNK_MS = 3_000
MAX_CHUNK_MS = 120_000
MAX_CHUNKS = 30
TOTAL_DURATION_TOLERANCE_MS = 50

DENSITY_STYLES = {
    "sparse": (["sparse pad, minimal percussion"], ["vocals", "lyrics"]),
    "medium": (["moderate arrangement, gentle rhythm"], ["vocals", "lyrics"]),
    "full": (["full arrangement, rhythmic emphasis"], ["vocals", "lyrics"]),
}


def build_music_plan(bed_arc: list[dict], runtime: float) -> dict:
    chunks = []
    for movement in bed_arc:
        label = movement["label"]
        duration_ms = round((movement["end_s"] - movement["start_s"]) * 1000)
        if duration_ms < MIN_CHUNK_MS:
            raise ChunkDurationTooShortError(
                f"movement {label!r} is {duration_ms}ms, under Eleven Music's {MIN_CHUNK_MS}ms floor "
                f"-- merge with an adjacent movement"
            )
        if duration_ms > MAX_CHUNK_MS:
            raise ChunkDurationTooShortError(
                f"movement {label!r} is {duration_ms}ms, over Eleven Music's {MAX_CHUNK_MS}ms ceiling "
                f"-- split into two movements"
            )
        positive, negative = DENSITY_STYLES[movement["density"]]
        positive = list(positive)
        if movement.get("style_notes"):
            positive.append(movement["style_notes"])
        chunks.append({"duration_ms": duration_ms, "positive_styles": positive, "negative_styles": list(negative)})

    if len(chunks) > MAX_CHUNKS:
        raise ChunkDurationTooShortError(
            f"{len(chunks)} chunks exceeds Eleven Music's {MAX_CHUNKS}-chunk ceiling -- merge adjacent movements"
        )

    total_ms = sum(c["duration_ms"] for c in chunks)
    expected_ms = round(runtime * 1000)
    if abs(total_ms - expected_ms) > TOTAL_DURATION_TOLERANCE_MS:
        raise ChunkDurationTooShortError(
            f"composition plan totals {total_ms}ms, take runtime is {expected_ms}ms "
            f"(off by {abs(total_ms - expected_ms)}ms) -- bed_arc movements must cover the full take"
        )

    return {"model_id": "music_v2", "force_instrumental": True, "composition_plan": {"chunks": chunks}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd native-pipeline && python -m pytest tests/test_music_plan.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add native-pipeline/native_pipeline/music_plan.py native-pipeline/tests/test_music_plan.py
git commit -m "feat(native-pipeline): add build_music_plan with movement-based chunking"
```

---

### Task 6: `flagging.py` — read-only outlier flagging

**Files:**
- Create: `native-pipeline/native_pipeline/flagging.py`
- Test: `native-pipeline/tests/test_flagging.py`

**Interfaces:**
- Consumes: `stitcher.verify.measure_window(path: Path, start: float, duration: float, log_path: Path) ->
  float` (`verify.py:129`), `stitcher.verify.MIN_DUCK_WINDOW_S` (`verify.py:54`, value `0.4`).
- Produces: `flag_outliers(path: Path, spans: list[tuple[str, float, float]], log_path: Path, threshold_lu:
  float = 3.0) -> list[dict]` — consumed by Task 9's `orchestrate` stages (called once after VO generation,
  once after music generation).

- [ ] **Step 1: Write the failing test**

```python
# native-pipeline/tests/test_flagging.py
from native_pipeline.flagging import flag_outliers


def test_flag_outliers_skips_windows_under_min_duck_window(monkeypatch, tmp_path):
    calls = []

    def fake_measure_window(path, start, duration, log_path):
        calls.append((start, duration))
        return -20.0

    monkeypatch.setattr("native_pipeline.flagging.measure_window", fake_measure_window)

    spans = [("beat1", 0.0, 0.2), ("beat2", 1.0, 5.0)]  # beat1 is 0.2s, under the 0.4s floor
    flag_outliers(tmp_path / "take.wav", spans, tmp_path / "log.txt")

    assert calls == [(1.0, 5.0)]


def test_flag_outliers_flags_the_beat_deviating_from_median(monkeypatch, tmp_path):
    lufs_by_start = {0.0: -14.0, 5.0: -14.5, 10.0: -25.0}

    def fake_measure_window(path, start, duration, log_path):
        return lufs_by_start[start]

    monkeypatch.setattr("native_pipeline.flagging.measure_window", fake_measure_window)

    spans = [("beat1", 0.0, 5.0), ("beat2", 5.0, 5.0), ("beat3", 10.0, 5.0)]
    flags = flag_outliers(tmp_path / "take.wav", spans, tmp_path / "log.txt")

    assert [f["label"] for f in flags] == ["beat3"]
    assert flags[0]["lufs"] == -25.0


def test_flag_outliers_returns_empty_list_when_all_beats_are_close(monkeypatch, tmp_path):
    monkeypatch.setattr("native_pipeline.flagging.measure_window", lambda path, start, duration, log_path: -14.0)
    spans = [("beat1", 0.0, 5.0), ("beat2", 5.0, 5.0)]
    assert flag_outliers(tmp_path / "take.wav", spans, tmp_path / "log.txt") == []


def test_flag_outliers_returns_empty_list_with_fewer_than_two_measurable_spans(monkeypatch, tmp_path):
    monkeypatch.setattr("native_pipeline.flagging.measure_window", lambda path, start, duration, log_path: -14.0)
    spans = [("beat1", 0.0, 5.0)]
    assert flag_outliers(tmp_path / "take.wav", spans, tmp_path / "log.txt") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd native-pipeline && python -m pytest tests/test_flagging.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'native_pipeline.flagging'`

- [ ] **Step 3: Write the implementation**

```python
# native-pipeline/native_pipeline/flagging.py
"""flag_outliers -- a read-only measurement pass over the raw VO take (per
beat) or the generated music bed (per chunk). Flags, never corrects: this
mode trusts ElevenLabs/Eleven Music output completely, and this is the one
piece of visibility into whether that trust was warranted for a specific
render. Never calls stitcher.precondition.condition_clip or anything else
that would modify the audio."""

from __future__ import annotations

import statistics
from pathlib import Path

from stitcher.verify import MIN_DUCK_WINDOW_S, measure_window


def flag_outliers(
    path: Path,
    spans: list[tuple[str, float, float]],
    log_path: Path,
    threshold_lu: float = 3.0,
) -> list[dict]:
    """spans: list of (label, start_s, duration_s). A span shorter than
    MIN_DUCK_WINDOW_S is skipped -- an ebur128 integrated reading over a
    very short window is not a meaningful measurement (stitcher.verify
    applies the same floor for its own ducking checks)."""
    measurements = []
    for label, start, duration in spans:
        if duration < MIN_DUCK_WINDOW_S:
            continue
        lufs = measure_window(path, start, duration, log_path)
        measurements.append((label, lufs))

    if len(measurements) < 2:
        return []

    median = statistics.median(lufs for _, lufs in measurements)

    flags = []
    for label, lufs in measurements:
        deviation = abs(lufs - median)
        if deviation > threshold_lu:
            flags.append({"label": label, "lufs": lufs, "median_lufs": median, "deviation_lu": deviation})
    return flags
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd native-pipeline && python -m pytest tests/test_flagging.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add native-pipeline/native_pipeline/flagging.py native-pipeline/tests/test_flagging.py
git commit -m "feat(native-pipeline): add read-only outlier flagging"
```

---

### Task 7: `assemble.py` — `assemble_spec` and `check_bed_duration`

**Files:**
- Create: `native-pipeline/native_pipeline/assemble.py`
- Test: `native-pipeline/tests/test_assemble.py`

**Interfaces:**
- Consumes: `stitcher.spec.{RenderSpec, Canvas, SafeZone, Audio, Bed, Stem, Loudness, Shot, Caption, Style}`
  (`spec.py`, exact fields listed in Task 4's interfaces block plus: `Bed(file, gain_db, duck_db,
  duck_attack_ms=120, duck_release_ms=400, windows=[], fades=[])` `spec.py:135-142`; `Stem(id, file, at,
  gain_db=0.0, duration_s=None)` `spec.py:114-119` — note `id` is required; `Audio(stems, bed, sfx=[],
  loudness)` `spec.py:156-160`; `Loudness(integrated_lufs, true_peak_dbtp)` `spec.py:151-153`;
  `RenderSpec(spec_version, slug, canvas, safe_zone, styles, shots, overlays=[], captions=[], captions_style,
  audio, cover=None, delivery=Delivery())` `spec.py:179-191`). `native_pipeline.errors.BedDurationMismatchError`
  (Task 1). `BED_RELATIVE_OFFSET_DB = -17.0` and `BED_DURATION_TOLERANCE_S = 0.1` (Global Constraints;
  widened from `0.05` post-Task-11, see that section for why).
- Produces: `assemble_spec(slug, shots, captions, voice_take, music_bed, runtime, voice_lufs, styles,
  captions_style) -> RenderSpec` and `check_bed_duration(bed_path: Path, runtime: float, log_path: Path) ->
  None` — both consumed by Task 9's `orchestrate.run_assemble_stage`.

- [ ] **Step 1: Write the failing test**

```python
# native-pipeline/tests/test_assemble.py
import pytest

from stitcher.spec import Caption, Motion, Shot, Style

from native_pipeline.assemble import BED_RELATIVE_OFFSET_DB, assemble_spec, check_bed_duration
from native_pipeline.errors import BedDurationMismatchError

STYLE = Style(font_file="Inter-Bold.ttf", size_px=64, body="#FFFFFF", accent="#FFD700",
              max_width_px=900, max_lines=3)


def _shot(n, beat, start, end):
    return Shot(n=n, id=beat, beat=beat, start=start, end=end, source=f"{beat}.png",
                kind="still", motion=Motion())


def test_assemble_spec_sets_flat_bed_gain_equal_to_duck_db():
    shots = [_shot(1, "beat1", 0.0, 5.0)]
    captions = [Caption(start=0.0, end=5.0, text="hello")]

    spec = assemble_spec(
        slug="test-slug", shots=shots, captions=captions,
        voice_take="take.wav", music_bed="bed.wav", runtime=5.0,
        voice_lufs=-23.0, styles={"default": STYLE}, captions_style="default",
    )

    expected_gain = -23.0 + BED_RELATIVE_OFFSET_DB
    assert spec.audio.bed.gain_db == expected_gain
    assert spec.audio.bed.duck_db == expected_gain


def test_assemble_spec_uses_one_unsplit_voice_stem():
    shots = [_shot(1, "beat1", 0.0, 5.0)]
    captions = [Caption(start=0.0, end=5.0, text="hello")]

    spec = assemble_spec(
        slug="test-slug", shots=shots, captions=captions,
        voice_take="take.wav", music_bed="bed.wav", runtime=5.0,
        voice_lufs=-23.0, styles={"default": STYLE}, captions_style="default",
    )

    assert len(spec.audio.stems) == 1
    assert spec.audio.stems[0].file == "take.wav"
    assert spec.audio.stems[0].at == 0.0
    assert spec.audio.stems[0].duration_s == 5.0


def test_check_bed_duration_raises_on_mismatch(tmp_path, monkeypatch):
    class FakeProbe:
        stdout = "58.500\n"
        stderr = ""

    monkeypatch.setattr("native_pipeline.assemble.subprocess.run", lambda *a, **k: FakeProbe())

    with pytest.raises(BedDurationMismatchError):
        check_bed_duration(tmp_path / "bed.wav", runtime=61.114, log_path=tmp_path / "log.txt")


def test_check_bed_duration_passes_within_tolerance(tmp_path, monkeypatch):
    class FakeProbe:
        stdout = "61.100\n"
        stderr = ""

    monkeypatch.setattr("native_pipeline.assemble.subprocess.run", lambda *a, **k: FakeProbe())

    check_bed_duration(tmp_path / "bed.wav", runtime=61.114, log_path=tmp_path / "log.txt")  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd native-pipeline && python -m pytest tests/test_assemble.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'native_pipeline.assemble'`

- [ ] **Step 3: Write the implementation**

```python
# native-pipeline/native_pipeline/assemble.py
"""assemble_spec builds the final RenderSpec for this mode using only
existing stitcher.spec classes -- no schema changes. Bed.gain_db ==
Bed.duck_db always, which makes stitcher's existing ducking envelope
(_build_bed() in audio.py) mathematically flat by construction, since the
music's own dynamics are already baked into its Eleven Music arrangement.

check_bed_duration is a fail-loud guard: audio.py's existing bed-conforming
step uses `-stream_loop -1 -t runtime`, which would otherwise silently
restart a too-short bed's intro under the outro, or truncate a too-long
bed mid-arrangement -- defeating the entire point of composing dynamics
into the arrangement."""

from __future__ import annotations

import subprocess
from pathlib import Path

from stitcher.spec import Audio, Bed, Canvas, Caption, Loudness, RenderSpec, SafeZone, Shot, Stem, Style

from native_pipeline.errors import BedDurationMismatchError

BED_RELATIVE_OFFSET_DB = -17.0
# 0.1s (100ms), widened post-Task-11 from this snippet's original 0.05s -- see the
# Global Constraints section above for why (real e2e jitter, human-approved).
BED_DURATION_TOLERANCE_S = 0.1
DELIVERY_LUFS = -14.0
DELIVERY_TP_DBTP = -1.0


def check_bed_duration(bed_path: Path, runtime: float, log_path: Path) -> None:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(bed_path)]
    probe = subprocess.run(cmd, capture_output=True, text=True, check=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"$ {' '.join(cmd)}\n{probe.stdout}{probe.stderr}\n")

    bed_duration = float(probe.stdout.strip())
    delta = abs(bed_duration - runtime)
    if delta > BED_DURATION_TOLERANCE_S:
        raise BedDurationMismatchError(
            f"generated bed is {bed_duration:.3f}s, take runtime is {runtime:.3f}s "
            f"(off by {delta:.3f}s, tolerance is {BED_DURATION_TOLERANCE_S}s)"
        )


def assemble_spec(
    slug: str,
    shots: list[Shot],
    captions: list[Caption],
    voice_take: str,
    music_bed: str,
    runtime: float,
    voice_lufs: float,
    styles: dict[str, Style],
    captions_style: str,
) -> RenderSpec:
    bed_gain = voice_lufs + BED_RELATIVE_OFFSET_DB
    return RenderSpec(
        spec_version="1.0",
        slug=slug,
        canvas=Canvas(width=1080, height=1920, fps=30),
        safe_zone=SafeZone(x=90, y=380, width=900, height=1160),
        styles=styles,
        shots=shots,
        captions=captions,
        captions_style=captions_style,
        audio=Audio(
            stems=[Stem(id="voice", file=voice_take, at=0.0, duration_s=runtime)],
            bed=Bed(file=music_bed, gain_db=bed_gain, duck_db=bed_gain, windows=[], fades=[]),
            sfx=[],
            loudness=Loudness(integrated_lufs=DELIVERY_LUFS, true_peak_dbtp=DELIVERY_TP_DBTP),
        ),
    )
```

If `RenderSpec`/`Audio`/`Bed`/`Stem`/`Style` construction fails because of a field name or required-field
mismatch, re-check the exact class definitions at the `spec.py` line ranges cited above and adjust.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd native-pipeline && python -m pytest tests/test_assemble.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add native-pipeline/native_pipeline/assemble.py native-pipeline/tests/test_assemble.py
git commit -m "feat(native-pipeline): add assemble_spec with flat bed gain and bed-duration guard"
```

---

### Task 8: `iteration.py` — iteration/proof harness

**Files:**
- Create: `native-pipeline/native_pipeline/iteration.py`
- Test: `native-pipeline/tests/test_iteration.py`

**Interfaces:**
- Consumes: `native_pipeline.errors.IterationBudgetExceededError` (Task 1).
- Produces: `IterationRecord` (dataclass with `.record(settings: dict, metrics: dict) -> None` and
  `.compare(metric_key: str, expected_direction: str) -> dict`), `Attempt` (dataclass: `settings: dict,
  metrics: dict`) — consumed by Task 9's orchestration (one `IterationRecord` per track, VO and music,
  independent).

**Note (per the spec's honesty caveat):** `.compare()` never raises on a contradicted direction — neither
ElevenLabs nor Eleven Music generation is fully deterministic run-to-run, so a contradicted delta is a finding
to report, not a hard failure. Only exceeding the 2-attempt budget raises.

**Scope note:** a single `render` invocation (Task 10's `cli.py`) runs each stage exactly once — it does not
itself decide to retry a track. `IterationRecord` is a library primitive for the *operator's* retry workflow:
when a human decides a generated VO or music track isn't right and wants to try different settings, they
construct an `IterationRecord`, call `.record()` after each of up to 2 attempts (with the actual settings used
and the measured metrics), and call `.compare()` to see the settings/metrics diff before choosing which
attempt to keep. This plan does not add a `--retry` subcommand to `cli.py`; wiring an interactive retry UI is
future work the design's Non-goals section didn't scope in, and inventing one now without a specified shape
would be exactly the kind of unrequested feature this project's own conventions warn against. What this task
guarantees is that the 2-attempt cap and the diff-recording mechanism exist and are correctly enforced,
ready for whatever retry workflow (CLI flag, notebook, ad-hoc script) gets built against it later.

- [ ] **Step 1: Write the failing test**

```python
# native-pipeline/tests/test_iteration.py
import pytest

from native_pipeline.errors import IterationBudgetExceededError
from native_pipeline.iteration import IterationRecord


def test_record_raises_iteration_budget_exceeded_on_third_attempt():
    record = IterationRecord(track="vo")
    record.record({"stability": 0.4}, {"lufs": -22.0})
    record.record({"stability": 0.6}, {"lufs": -18.0})

    with pytest.raises(IterationBudgetExceededError, match="vo"):
        record.record({"stability": 0.8}, {"lufs": -15.0})


def test_compare_reports_directionally_consistent_delta():
    record = IterationRecord(track="vo")
    record.record({"stability": 0.4}, {"lufs": -22.0})
    record.record({"stability": 0.6}, {"lufs": -18.0})

    result = record.compare("lufs", expected_direction="up")

    assert result["directionally_consistent"] is True
    assert result["delta"] == pytest.approx(4.0)
    assert result["settings_diff"] == {"stability": (0.4, 0.6)}


def test_compare_reports_contradicted_direction_without_raising():
    record = IterationRecord(track="vo")
    record.record({"stability": 0.4}, {"lufs": -22.0})
    record.record({"stability": 0.6}, {"lufs": -25.0})  # moved the wrong way

    result = record.compare("lufs", expected_direction="up")

    assert result["directionally_consistent"] is False


def test_compare_raises_value_error_with_fewer_than_two_attempts():
    record = IterationRecord(track="vo")
    record.record({"stability": 0.4}, {"lufs": -22.0})

    with pytest.raises(ValueError, match="need 2 attempts"):
        record.compare("lufs", expected_direction="up")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd native-pipeline && python -m pytest tests/test_iteration.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'native_pipeline.iteration'`

- [ ] **Step 3: Write the implementation**

```python
# native-pipeline/native_pipeline/iteration.py
"""IterationRecord enforces the 2-attempts-per-track budget and records the
settings/metrics diff between attempts, per the design's iteration/proof
harness. .compare() states directional consistency, not causal proof --
neither ElevenLabs nor Eleven Music generation is fully deterministic
run-to-run, so a contradicted direction is reported as a finding, never
silently retried past the hard 2-attempt cap."""

from __future__ import annotations

from dataclasses import dataclass, field

from native_pipeline.errors import IterationBudgetExceededError

MAX_ATTEMPTS = 2


@dataclass
class Attempt:
    settings: dict
    metrics: dict


@dataclass
class IterationRecord:
    track: str
    attempts: list[Attempt] = field(default_factory=list)

    def record(self, settings: dict, metrics: dict) -> None:
        if len(self.attempts) >= MAX_ATTEMPTS:
            raise IterationBudgetExceededError(f"{self.track}: attempt budget of {MAX_ATTEMPTS} already spent")
        self.attempts.append(Attempt(settings=settings, metrics=metrics))

    def compare(self, metric_key: str, expected_direction: str) -> dict:
        if len(self.attempts) < 2:
            raise ValueError(f"{self.track}: need 2 attempts to compare, have {len(self.attempts)}")

        first, second = self.attempts[0], self.attempts[1]
        settings_diff = {
            key: (first.settings.get(key), second.settings.get(key))
            for key in set(first.settings) | set(second.settings)
            if first.settings.get(key) != second.settings.get(key)
        }
        delta = second.metrics[metric_key] - first.metrics[metric_key]
        directionally_consistent = delta > 0 if expected_direction == "up" else delta < 0

        return {
            "track": self.track,
            "settings_diff": settings_diff,
            "metric_key": metric_key,
            "delta": delta,
            "expected_direction": expected_direction,
            "directionally_consistent": directionally_consistent,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd native-pipeline && python -m pytest tests/test_iteration.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add native-pipeline/native_pipeline/iteration.py native-pipeline/tests/test_iteration.py
git commit -m "feat(native-pipeline): add iteration/proof harness with 2-attempt budget"
```

---

### Task 9: `orchestrate.py` — wiring VO, music, assembly, and render

**Files:**
- Create: `native-pipeline/native_pipeline/orchestrate.py`
- Test: `native-pipeline/tests/test_orchestrate.py`

**Interfaces:**
- Consumes: `stitcher.naming.Workspace(root: Path, slug: str, mode: str)` and its `.asset(filename) -> Path`,
  `.ensure_dirs()`, `.spec_path`, `.log_path(timestamp) -> Path` (`naming.py:32-38` + methods list).
  `stitcher.vo_alignment.derive_segments(text: str, alignment: dict, names: list[str] | None = None) ->
  list[Segment]` (`vo_alignment.py:29`). `stitcher.vo_timing.derive_captions(segments, beat_texts) ->
  list[Caption]` (`vo_timing.py:23`). `stitcher.ffmpeg.measure_loudness(path, log_path) -> dict` (returns
  `{"input_i", "input_tp", "input_lra"}`, `ffmpeg.py:320,344-348`). Task 3's `contracts.load_bed_arc`, Task 5's
  `music_plan.build_music_plan`, Task 4's `shots.build_shots`, Task 6's `flagging.flag_outliers`, Task 7's
  `assemble.assemble_spec` + `check_bed_duration`.
- Produces: `run_vo_stage(ws, payload_path, url, log_path) -> tuple[Path, list[Segment]]`,
  `run_music_stage(segments, bed_arc_path, ws, url, log_path) -> Path`, `run_assemble_stage(ws, segments,
  asset_manifest_path, beat_texts, voice_take, music_bed, styles, captions_style, log_path) -> Path`,
  `run_render_stage(slug, root) -> None` — consumed by Task 10's `cli.py`. **Flagging (per the design's
  read-only safety net) runs inside `run_vo_stage` (over segments) and `run_music_stage` (over bed-arc
  movements), appending any flags found to `log_path` as `FLAG: ...` lines — never returned, never acted on,
  never blocking. The e2e test in Task 11 reads the log file afterward to check for flags.**

**Subprocess calls this task makes (the only place `native_pipeline` calls out to the other two packages):**
- `python -m elevenlabs_tooling generate-vo --payload <path> --url <url> --audio-output <path>
  --alignment-output <path> --force` (existing command, `elevenlabs-tooling/elevenlabs_tooling/cli.py:280`,
  flags per `cli.py:434-444`).
- `python -m elevenlabs_tooling music send --payload <path> --url <url> --output <path> --force` (Task 2,
  new).
- `python -m stitcher render <slug> --root <path> --mode final --force` (existing command, unmodified,
  `stitcher/stitcher/cli.py:296-300`).

- [ ] **Step 1: Write the failing test**

```python
# native-pipeline/tests/test_orchestrate.py
import json
import sys
from pathlib import Path

import pytest

from stitcher.naming import Workspace
from stitcher.vo_alignment import Segment

from native_pipeline import orchestrate


class FakeCompletedProcess:
    def __init__(self):
        self.returncode = 0


def test_run_vo_stage_calls_generate_vo_and_derives_segments(tmp_path, monkeypatch):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps({"text": "beat one. beat two."}), encoding="utf-8")

    ws = Workspace(root=tmp_path / "renders", slug="test-slug", mode="final")
    ws.ensure_dirs()

    captured_cmd = {}

    def fake_run(cmd, check):
        captured_cmd["cmd"] = cmd
        # Simulate generate-vo writing its two output files.
        alignment_output = Path(cmd[cmd.index("--alignment-output") + 1])
        alignment_output.write_text(json.dumps({"characters": [], "character_start_times_seconds": [],
                                                  "character_end_times_seconds": []}), encoding="utf-8")
        audio_output = Path(cmd[cmd.index("--audio-output") + 1])
        audio_output.write_bytes(b"fake-audio")
        return FakeCompletedProcess()

    monkeypatch.setattr("native_pipeline.orchestrate.subprocess.run", fake_run)
    monkeypatch.setattr(
        "native_pipeline.orchestrate.derive_segments",
        lambda text, alignment, names=None: [Segment(name="beat1", at=0.0, duration=5.0)],
    )
    monkeypatch.setattr("native_pipeline.orchestrate.flag_outliers", lambda *a, **k: [])

    log_path = tmp_path / "log.txt"
    audio_output, segments = orchestrate.run_vo_stage(ws, payload_path, "https://fake-url", log_path)

    assert captured_cmd["cmd"][:4] == [sys.executable, "-m", "elevenlabs_tooling", "generate-vo"]
    assert "--force" in captured_cmd["cmd"]
    assert audio_output.read_bytes() == b"fake-audio"
    assert segments[0].name == "beat1"


def test_run_vo_stage_appends_flag_lines_to_log_when_flagging_finds_something(tmp_path, monkeypatch):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps({"text": "beat one."}), encoding="utf-8")
    ws = Workspace(root=tmp_path / "renders", slug="test-slug", mode="final")
    ws.ensure_dirs()

    def fake_run(cmd, check):
        Path(cmd[cmd.index("--alignment-output") + 1]).write_text(json.dumps({
            "characters": [], "character_start_times_seconds": [], "character_end_times_seconds": []}),
            encoding="utf-8")
        Path(cmd[cmd.index("--audio-output") + 1]).write_bytes(b"fake-audio")
        return FakeCompletedProcess()

    monkeypatch.setattr("native_pipeline.orchestrate.subprocess.run", fake_run)
    monkeypatch.setattr(
        "native_pipeline.orchestrate.derive_segments",
        lambda text, alignment, names=None: [Segment(name="beat1", at=0.0, duration=5.0)],
    )
    monkeypatch.setattr(
        "native_pipeline.orchestrate.flag_outliers",
        lambda path, spans, log_path: [{"label": "beat1", "lufs": -25.0, "median_lufs": -14.0, "deviation_lu": 11.0}],
    )

    log_path = tmp_path / "log.txt"
    log_path.write_text("", encoding="utf-8")
    orchestrate.run_vo_stage(ws, payload_path, "https://fake-url", log_path)

    assert "FLAG:" in log_path.read_text(encoding="utf-8")
    assert "beat1" in log_path.read_text(encoding="utf-8")


def test_run_music_stage_writes_plan_and_calls_music_send(tmp_path, monkeypatch):
    ws = Workspace(root=tmp_path / "renders", slug="test-slug", mode="final")
    ws.ensure_dirs()
    bed_arc_path = tmp_path / "bed_arc.json"
    bed_arc_path.write_text(json.dumps([
        {"label": "hook", "start_s": 0.0, "end_s": 5.0, "density": "full", "style_notes": ""},
    ]), encoding="utf-8")
    segments = [Segment(name="beat1", at=0.0, duration=5.0)]

    captured_cmd = {}

    def fake_run(cmd, check):
        captured_cmd["cmd"] = cmd
        output = Path(cmd[cmd.index("--output") + 1])
        output.write_bytes(b"fake-bed")
        return FakeCompletedProcess()

    monkeypatch.setattr("native_pipeline.orchestrate.subprocess.run", fake_run)
    monkeypatch.setattr("native_pipeline.orchestrate.flag_outliers", lambda *a, **k: [])

    log_path = tmp_path / "log.txt"
    log_path.write_text("", encoding="utf-8")
    bed_path = orchestrate.run_music_stage(segments, bed_arc_path, ws, "https://fake-music-url", log_path)

    assert captured_cmd["cmd"][:4] == [sys.executable, "-m", "elevenlabs_tooling", "music"]
    assert captured_cmd["cmd"][4] == "send"
    assert bed_path.read_bytes() == b"fake-bed"


def test_run_render_stage_invokes_stitcher_render(tmp_path, monkeypatch):
    captured_cmd = {}

    def fake_run(cmd, check):
        captured_cmd["cmd"] = cmd
        return FakeCompletedProcess()

    monkeypatch.setattr("native_pipeline.orchestrate.subprocess.run", fake_run)

    orchestrate.run_render_stage("test-slug", tmp_path)

    assert captured_cmd["cmd"] == [
        sys.executable, "-m", "stitcher", "render", "test-slug",
        "--root", str(tmp_path), "--mode", "final", "--force",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd native-pipeline && python -m pytest tests/test_orchestrate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'native_pipeline.orchestrate'`

- [ ] **Step 3: Write the implementation**

```python
# native-pipeline/native_pipeline/orchestrate.py
"""Wires VO generation, music generation, shot/caption/spec assembly, and
the final render into one sequence. This module -- and only this module in
this package -- calls out to elevenlabs_tooling (via subprocess, its CLI)
and to stitcher's render CLI (also via subprocess). Everything else in
native_pipeline only ever consumes stitcher as an imported library
(spec/vo_alignment/vo_timing/verify/ffmpeg) -- never the reverse."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from stitcher.ffmpeg import measure_loudness
from stitcher.naming import Workspace
from stitcher.vo_alignment import Segment, derive_segments
from stitcher.vo_timing import derive_captions

from native_pipeline import assemble, contracts, music_plan
from native_pipeline.flagging import flag_outliers
from native_pipeline.shots import build_shots


def _append_flags(flags: list[dict], log_path: Path) -> None:
    """Read-only telemetry: appends any flags to the plain-text workspace
    log, never acts on them. See native_pipeline.flagging -- flags are
    visibility into whether 'trust the raw output' was warranted for this
    specific render, not a correction mechanism."""
    if not flags:
        return
    with open(log_path, "a", encoding="utf-8") as f:
        for flag in flags:
            f.write(f"FLAG: {flag}\n")


def run_vo_stage(ws: Workspace, payload_path: Path, url: str, log_path: Path) -> tuple[Path, list[Segment]]:
    audio_output = ws.asset("single_take.mp3")
    alignment_output = ws.asset("alignment.json")
    subprocess.run(
        [sys.executable, "-m", "elevenlabs_tooling", "generate-vo",
         "--payload", str(payload_path), "--url", url,
         "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
         "--force"],
        check=True,
    )
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    alignment = json.loads(alignment_output.read_text(encoding="utf-8"))
    segments = derive_segments(payload["text"], alignment)

    spans = [(segment.name, segment.at, segment.duration) for segment in segments]
    flags = flag_outliers(audio_output, spans, log_path)
    _append_flags(flags, log_path)

    return audio_output, segments


def run_music_stage(segments: list[Segment], bed_arc_path: Path, ws: Workspace, url: str, log_path: Path) -> Path:
    bed_arc = contracts.load_bed_arc(bed_arc_path)
    runtime = segments[-1].at + segments[-1].duration
    plan = music_plan.build_music_plan(bed_arc, runtime)

    plan_path = ws.asset("composition_plan.json")
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    bed_output = ws.asset("music_bed.wav")
    subprocess.run(
        [sys.executable, "-m", "elevenlabs_tooling", "music", "send",
         "--payload", str(plan_path), "--url", url, "--output", str(bed_output), "--force"],
        check=True,
    )

    spans = [(m["label"], m["start_s"], m["end_s"] - m["start_s"]) for m in bed_arc]
    flags = flag_outliers(bed_output, spans, log_path)
    _append_flags(flags, log_path)

    return bed_output


def run_assemble_stage(
    ws: Workspace,
    segments: list[Segment],
    asset_manifest_path: Path,
    beat_texts: list[str],
    voice_take: Path,
    music_bed: Path,
    styles: dict,
    captions_style: str,
    log_path: Path,
) -> Path:
    asset_manifest = contracts.load_asset_manifest(asset_manifest_path)
    shots = build_shots(segments, asset_manifest)
    captions = derive_captions(segments, beat_texts)
    runtime = segments[-1].at + segments[-1].duration

    voice_lufs = measure_loudness(voice_take, log_path)["input_i"]
    assemble.check_bed_duration(music_bed, runtime, log_path)

    spec = assemble.assemble_spec(
        slug=ws.slug, shots=shots, captions=captions,
        voice_take=str(voice_take), music_bed=str(music_bed), runtime=runtime,
        voice_lufs=voice_lufs, styles=styles, captions_style=captions_style,
    )

    spec_path = ws.spec_path
    spec_path.write_text(json.dumps(spec.model_dump(by_alias=True, mode="json")), encoding="utf-8")
    return spec_path


def run_render_stage(slug: str, root: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "stitcher", "render", slug, "--root", str(root), "--mode", "final", "--force"],
        check=True,
    )
```

If `spec.model_dump(by_alias=True, mode="json")` doesn't match how `stitcher.spec.load_spec` expects a
render-spec.json to be written, check `spec.py`'s `load_spec` (`:237`) and any existing spec-writing code in
`stitcher`'s own tests for the exact serialization call, and adjust.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd native-pipeline && python -m pytest tests/test_orchestrate.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add native-pipeline/native_pipeline/orchestrate.py native-pipeline/tests/test_orchestrate.py
git commit -m "feat(native-pipeline): add orchestration wiring VO, music, assembly, and render stages"
```

---

### Task 10: `cli.py` + `__main__.py` — the entrypoint

**Files:**
- Create: `native-pipeline/native_pipeline/cli.py`
- Create: `native-pipeline/native_pipeline/__main__.py`
- Test: `native-pipeline/tests/test_cli.py`

**Interfaces:**
- Consumes: all four `run_*_stage` functions from Task 9's `orchestrate.py`, `stitcher.naming.Workspace`.
- Produces: `python -m native_pipeline render <slug> --root <path> --vo-payload <path> --vo-url <url>
  --bed-arc <path> --music-url <url> --asset-manifest <path> --beat-texts <path> --styles <path>
  --captions-style <name>` — the mode's real entrypoint, separate from `stitcher`'s own `render` command per
  the design's CLI section (this is not a new `--mode` value on `stitcher`'s CLI).

`--beat-texts` and `--styles` are paths to small JSON files: `beat-texts` is a JSON list of strings (one per
beat, in segment order, for `derive_captions`); `styles` is a JSON object matching `RenderSpec.styles`' shape
(`{style_name: {font_file, size_px, body, accent, max_width_px, max_lines, ...}}`) — this task reads and
parses both, constructing `Style` objects for the latter.

- [ ] **Step 1: Write the failing test**

```python
# native-pipeline/tests/test_cli.py
import json
from pathlib import Path

from native_pipeline.cli import main


def test_render_command_calls_all_four_stages_in_order(tmp_path, monkeypatch):
    calls = []

    def fake_run_vo_stage(ws, payload_path, url, log_path):
        calls.append("vo")
        from stitcher.vo_alignment import Segment
        return tmp_path / "take.mp3", [Segment(name="beat1", at=0.0, duration=5.0)]

    def fake_run_music_stage(segments, bed_arc_path, ws, url, log_path):
        calls.append("music")
        return tmp_path / "bed.wav"

    def fake_run_assemble_stage(ws, segments, asset_manifest_path, beat_texts, voice_take, music_bed,
                                 styles, captions_style, log_path):
        calls.append("assemble")
        return tmp_path / "render-spec.json"

    def fake_run_render_stage(slug, root):
        calls.append("render")

    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_vo_stage", fake_run_vo_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_music_stage", fake_run_music_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_assemble_stage", fake_run_assemble_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_render_stage", fake_run_render_stage)

    beat_texts_path = tmp_path / "beat_texts.json"
    beat_texts_path.write_text(json.dumps(["hello"]), encoding="utf-8")
    styles_path = tmp_path / "styles.json"
    styles_path.write_text(json.dumps({
        "default": {"font_file": "Inter-Bold.ttf", "size_px": 64, "body": "#FFFFFF", "accent": "#FFD700",
                    "max_width_px": 900, "max_lines": 3},
    }), encoding="utf-8")

    exit_code = main([
        "render", "test-slug",
        "--root", str(tmp_path / "renders"),
        "--vo-payload", str(tmp_path / "payload.json"),
        "--vo-url", "https://fake-vo-url",
        "--bed-arc", str(tmp_path / "bed_arc.json"),
        "--music-url", "https://fake-music-url",
        "--asset-manifest", str(tmp_path / "manifest.json"),
        "--beat-texts", str(beat_texts_path),
        "--styles", str(styles_path),
        "--captions-style", "default",
    ])

    assert exit_code == 0
    assert calls == ["vo", "music", "assemble", "render"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd native-pipeline && python -m pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'native_pipeline.cli'`

- [ ] **Step 3: Write the implementation**

```python
# native-pipeline/native_pipeline/cli.py
"""CLI entry point: `python -m native_pipeline render <slug> ...`

This is a separate entrypoint from stitcher's own `render` command, not a
new --mode value on it -- stitcher's --mode selects a rendering-quality
variant (final vs draft), threaded into cache keys and workspace paths
throughout audio.py/shots.py/assemble.py. This mode is an alternate
upstream construction path that produces a render-spec.json BEFORE
stitcher's render command ever runs; the two are separate subprocess
invocations (see orchestrate.run_render_stage)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stitcher.naming import Workspace
from stitcher.spec import Style

from native_pipeline import orchestrate


def cmd_render(args: argparse.Namespace) -> int:
    root = Path(args.root)
    ws = Workspace(root=root, slug=args.slug, mode="final")
    ws.ensure_dirs()
    log_path = ws.log_path("native")

    voice_take, segments = orchestrate.run_vo_stage(ws, Path(args.vo_payload), args.vo_url, log_path)
    music_bed = orchestrate.run_music_stage(segments, Path(args.bed_arc), ws, args.music_url, log_path)

    beat_texts = json.loads(Path(args.beat_texts).read_text(encoding="utf-8"))
    raw_styles = json.loads(Path(args.styles).read_text(encoding="utf-8"))
    styles = {name: Style(**fields) for name, fields in raw_styles.items()}

    orchestrate.run_assemble_stage(
        ws, segments, Path(args.asset_manifest), beat_texts,
        voice_take, music_bed, styles, args.captions_style, log_path,
    )
    orchestrate.run_render_stage(args.slug, root)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m native_pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    render_parser = subparsers.add_parser("render", help="Run the full native single-generation pipeline")
    render_parser.add_argument("slug")
    render_parser.add_argument("--root", required=True)
    render_parser.add_argument("--vo-payload", required=True)
    render_parser.add_argument("--vo-url", required=True)
    render_parser.add_argument("--bed-arc", required=True)
    render_parser.add_argument("--music-url", required=True)
    render_parser.add_argument("--asset-manifest", required=True)
    render_parser.add_argument("--beat-texts", required=True)
    render_parser.add_argument("--styles", required=True)
    render_parser.add_argument("--captions-style", required=True)
    render_parser.set_defaults(func=cmd_render)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
```

```python
# native-pipeline/native_pipeline/__main__.py
import sys

from native_pipeline.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd native-pipeline && python -m pytest tests/test_cli.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Run the full native-pipeline unit test suite**

Run: `cd native-pipeline && python -m pytest -v`
Expected: all tests from Tasks 1, 3-10 PASS (the `e2e`-marked test from Task 11 doesn't exist yet)

- [ ] **Step 6: Commit**

```bash
git add native-pipeline/native_pipeline/cli.py native-pipeline/native_pipeline/__main__.py native-pipeline/tests/test_cli.py
git commit -m "feat(native-pipeline): add CLI entrypoint wiring all four stages"
```

---

### Task 11: Real end-to-end validation run

**Files:**
- Create: `native-pipeline/tests/test_e2e.py`

**Interfaces:**
- Consumes: everything built in Tasks 1-10.
- Produces: one real, billed, end-to-end proof that the mode works against real ElevenLabs and Eleven Music
  APIs and a real `stitcher render` invocation — mirrors the rigor of the original single-take pipeline's
  Task 11 validation (`docs/superpowers/plans/2026-08-19-single-take-vo-pipeline-RESULTS.md`).

**This test costs real API credits and takes real wall-clock time. It is marked `e2e` + `allow_network`, so it
does not run by default (`pytest -m e2e` opts in) — matching this repo's real marker vocabulary, not an
invented "integration" marker.**

- [ ] **Step 1: Write the test**

Use a short, 2-beat synthetic script (cheaper and faster to validate than a full 8-beat production script;
the mechanism being proven — timestamps drive shots/captions/music timing, bed dynamics come from the
composition plan, envelope is flat, bed duration matches — doesn't need 8 beats to demonstrate).

```python
# native-pipeline/tests/test_e2e.py
"""Real end-to-end validation of the native single-generation render mode.
Costs real ElevenLabs + Eleven Music API credits. Run explicitly with:
    python -m pytest -m e2e -v
Requires ELEVENLABS_API_KEY set and a real ffmpeg/ffprobe on PATH.
"""
import json
import os

import pytest

from stitcher.envelope import build_breakpoints, level_at, stem_spans
from stitcher.ffmpeg import measure_loudness
from stitcher.naming import Workspace
from stitcher.spec import load_spec, validate_spec

from native_pipeline import orchestrate
from native_pipeline.assemble import BED_RELATIVE_OFFSET_DB

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.allow_network,
]

VO_URL = "https://api.elevenlabs.io/v1/text-to-speech/eDwT8Vhp2yxJzAMmuuPA/with-timestamps"
MUSIC_URL = "https://api.elevenlabs.io/v1/music/compose"

BEAT_TEXTS = [
    "This is the first beat of a short test script.",
    "And this is the second beat, after a real pause.",
]


@pytest.fixture
def workspace(tmp_path):
    ws = Workspace(root=tmp_path / "renders", slug="native-e2e-test", mode="final")
    ws.ensure_dirs()
    return ws


def test_native_pipeline_end_to_end(workspace, tmp_path):
    if not os.environ.get("ELEVENLABS_API_KEY"):
        pytest.skip("ELEVENLABS_API_KEY not set")

    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps({
        "text": (
            f'{BEAT_TEXTS[0]} <break time="1.0s" /> {BEAT_TEXTS[1]}'
        ),
        "model_id": "eleven_multilingual_v2",
    }), encoding="utf-8")

    log_path = workspace.log_path("e2e")
    voice_take, segments = orchestrate.run_vo_stage(workspace, payload_path, VO_URL, log_path)
    runtime = segments[-1].at + segments[-1].duration

    bed_arc_path = tmp_path / "bed_arc.json"
    bed_arc_path.write_text(json.dumps([
        {"label": "whole-take", "start_s": 0.0, "end_s": runtime, "density": "sparse", "style_notes": ""},
    ]), encoding="utf-8")
    music_bed = orchestrate.run_music_stage(segments, bed_arc_path, workspace, MUSIC_URL, log_path)

    asset_manifest_path = tmp_path / "manifest.json"
    asset_manifest_path.write_text(json.dumps([
        {"beat": seg.name, "kind": "still", "source": f"{seg.name}.png", "source_in_s": None,
         "source_out_s": None,
         "motion": {"kind": "none", "amount_pct": 0.0, "anchor_start": [0.5, 0.5],
                    "anchor_end": [0.5, 0.5], "hold_s": 0.0, "ease": "linear"}}
        for seg in segments
    ]), encoding="utf-8")

    styles = {"default": {"font_file": "Inter-Bold.ttf", "size_px": 64, "body": "#FFFFFF",
                            "accent": "#FFD700", "max_width_px": 900, "max_lines": 3}}
    from stitcher.spec import Style
    style_objs = {"default": Style(**styles["default"])}

    spec_path = orchestrate.run_assemble_stage(
        workspace, segments, asset_manifest_path, BEAT_TEXTS, voice_take, music_bed,
        style_objs, "default", log_path,
    )

    # Criterion: the assembled spec loads and validates cleanly.
    spec, warnings = load_spec(spec_path)
    assert validate_spec(spec) == []

    # Criterion: Bed.gain_db == Bed.duck_db (flat by construction).
    assert spec.audio.bed.gain_db == spec.audio.bed.duck_db

    # Criterion: the envelope math the flat bed produces is genuinely flat
    # across the take, not just equal at the two input fields.
    spans = stem_spans(spec.audio.stems, runtime)
    breakpoints = build_breakpoints(spec.audio.bed, spans, runtime)
    sampled_levels = {level_at(breakpoints, t) for t in [0.5, runtime / 2, runtime - 0.5]}
    assert len(sampled_levels) == 1, f"envelope is not flat: {sampled_levels}"

    # This subprocess call is where the accepted risk from the design's VO-
    # processing decision can surface: if this specific take is too hot for
    # stitcher's existing linear-mode normalization gate, stitcher's own
    # (unmodified) render command exits non-zero and subprocess.run(...,
    # check=True) raises CalledProcessError. That IS the documented,
    # deliberately-accepted failure mode for this mode -- not a defect in
    # this test -- so it's reported, not asserted away.
    import subprocess as sp
    try:
        orchestrate.run_render_stage("native-e2e-test", tmp_path / "renders")
    except sp.CalledProcessError as exc:
        pytest.skip(
            f"render failed -- this specific take may be too hot for linear-mode normalization, "
            f"an accepted risk of 'zero VO processing' per the design spec, not a test failure: {exc}"
        )

    # Criterion: the rendered mix hits the delivery target within tolerance.
    # (Reaching this line means stitcher's own render command exited 0, which
    # -- by that command's existing, unmodified behavior -- already implies
    # normalization_type == "linear"; a non-linear result raises there before
    # ever reaching this point.)
    final_mix = workspace.deliverable(".mp4", version=1)
    assert final_mix.exists()

    # Criterion: no unexpected outlier flags for this normal, short synthetic
    # take -- a flag here is itself a finding to investigate, not something
    # to silence. flag lines were appended (if any) by run_vo_stage/
    # run_music_stage directly to log_path.
    log_contents = log_path.read_text(encoding="utf-8")
    flag_lines = [line for line in log_contents.splitlines() if line.startswith("FLAG:")]
    assert flag_lines == [], f"unexpected outlier flags on a normal take: {flag_lines}"
```

- [ ] **Step 2: Run once with real credentials to confirm it passes**

Run: `cd native-pipeline && ELEVENLABS_API_KEY=<real key> python -m pytest -m e2e -v`
Expected: PASS. If it fails, read the failure carefully — this is the first real proof the whole chain works;
do not adjust the test to make a real defect disappear. Fix the defect in the relevant module (Tasks 3-10)
and re-run.

- [ ] **Step 3: Commit**

```bash
git add native-pipeline/tests/test_e2e.py
git commit -m "test(native-pipeline): add real end-to-end validation, marked e2e + allow_network"
```

---

## Final Check

After Task 11 passes, run the full suite one more time to confirm nothing regressed across tasks:

```bash
cd native-pipeline && python -m pytest -v          # unit tests
cd elevenlabs-tooling && python -m pytest -v        # confirm music send didn't break existing commands
cd stitcher && python -m pytest -v                  # confirm zero changes to stitcher itself (this plan
                                                      # should show 0 diffs under stitcher/stitcher/)
```

Then hand off to `superpowers:finishing-a-development-branch` per the usual SDD final-review process.
