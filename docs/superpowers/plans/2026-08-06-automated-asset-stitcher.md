# Automated Asset Stitcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Python + FFmpeg module that turns a versioned `render-spec.json` plus a folder of assets into publication-ready 9:16 Shorts deliverables (master MP4, cover, caption sidecars, QA report).

**Architecture:** A six-stage pipeline (shots → overlays → audio → assemble → derive → verify) where every stage writes named, content-hash-cached artifacts to disk. Exactly two encodes occur per run: a near-lossless per-shot intermediate and one final delivery encode. Python owns all timeline logic and text rasterization; FFmpeg owns pixels and samples. No ML, no network, no GPU.

**Tech Stack:** Python 3.11+, pydantic v2 (spec schema), Pillow (overlay rasterization), FFmpeg/ffprobe 8.x (external binaries), pytest.

**Spec:** `docs/superpowers/specs/2026-08-06-automated-asset-stitcher-design.md`. Read it before Task 1. Where this plan and the spec disagree, the spec wins — raise the conflict rather than guessing.

**One intentional deviation from spec §1:** the spec lists eleven modules. This plan adds two — `motion.py` and `envelope.py` — splitting the pure Ken Burns math out of `shots.py` and the pure ducking math out of `audio.py`. Both are the highest-value unit-test surfaces in the project and both are pure functions; leaving them inside their FFmpeg-executing stages would make them testable only through a render. Thirteen modules total.

## Global Constraints

- **Python 3.11 or newer.** Uses `tomllib`-era stdlib and PEP 604 unions.
- **Pinned exactly** in `stitcher/requirements.txt`: `pydantic==2.9.2`, `Pillow==11.0.0`, `pytest==8.3.3`. Pillow's pin is load-bearing — glyph rasterization shifts between builds and would break golden-image tests (spec §7).
- **FFmpeg and ffprobe 8.x** on `PATH`. `-vsync` is removed in 8.x; always use `-fps_mode`. libx264 required; **libass is NOT required and must not be checked for** (spec §6).
- **Canvas is 1080×1920 only** in v1. Other dimensions are rejected at validation (spec §8).
- **Never `shell=True`.** All subprocess calls pass argv lists (spec §6).
- **Never NVENC.** libx264 only, for reproducibility (spec §8).
- **Any filtergraph that references a filesystem path goes through a `-filter_complex_script` file**, never inline, to avoid Windows `C:\` colon-escaping (spec §4 stage D). Path-free graphs (`-vf`/`-af` in stages A and C) may stay inline — the escaping hazard is paths, not filters.
- **Every ffmpeg command is written to `logs/` before it executes** (spec §6).
- **Time quantization applies to absolute boundaries, never durations.** Durations are derived by differencing quantized boundaries (spec §3).
- **`bed.gain_db` and `bed.duck_db` are levels relative to the measured voice track**, not gains on the bed file and not absolute loudness (spec §3).
- **Exit codes** (shared by `render` and `verify`): 0 success, 1 preflight/validation failure, 2 render failure, 3 QA failure, 4 verification incomplete. `validate` exits 0 or 1 (spec §1).
- Platform is Windows 11. Golden-image tests are marked Windows-only.

## File Structure

| File | Responsibility |
|---|---|
| `stitcher/requirements.txt` | Exact pins. |
| `stitcher/stitcher/__init__.py` | Package marker; exports nothing. |
| `stitcher/stitcher/naming.py` | Every path and filename in the workspace. Pure. |
| `stitcher/stitcher/spec.py` | Pydantic models, loading, frame quantization, validation. Pure. |
| `stitcher/stitcher/ffmpeg.py` | Subprocess wrapper, ffprobe, capability checks, logging. |
| `stitcher/stitcher/cache.py` | Content hashing and the stage manifest. |
| `stitcher/stitcher/preflight.py` | Asset probing, tool checks, path-length check. |
| `stitcher/stitcher/motion.py` | Ken Burns math and FFmpeg expression emission. Pure. |
| `stitcher/stitcher/overlays.py` | Stage B — Pillow text rasterization to RGBA PNG + bbox. |
| `stitcher/stitcher/shots.py` | Stage A — per-shot clip rendering. |
| `stitcher/stitcher/envelope.py` | Ducking envelope math and volume-expression emission. Pure. |
| `stitcher/stitcher/audio.py` | Stage C — stem placement, ducking, loudnorm. |
| `stitcher/stitcher/assemble.py` | Stage D — concat, overlay compositing, final encode. |
| `stitcher/stitcher/derive.py` | Stage E — cover conform, `.srt`/`.ass` sidecars. |
| `stitcher/stitcher/verify.py` | Stage F — measurement, bound checks, QA reports. |
| `stitcher/stitcher/cli.py` | Command dispatch, stage orchestration, version promotion, exit codes. |
| `stitcher/tests/` | One test module per source module, plus `test_e2e.py`. |
| `stitcher/tests/fixtures/` | Minimal spec, generated assets, golden PNGs, golden graphs. |

Dependency order (each task depends only on those before it): naming → spec → ffmpeg → cache → preflight → motion → overlays → shots → envelope → audio → assemble → derive → verify → cli → e2e.

---

### Task 1: Package scaffold and `naming.py`

**Files:**
- Create: `stitcher/requirements.txt`
- Create: `stitcher/stitcher/__init__.py`
- Create: `stitcher/stitcher/naming.py`
- Create: `stitcher/tests/__init__.py`
- Create: `stitcher/pytest.ini`
- Test: `stitcher/tests/test_naming.py`
- Modify: `.gitignore` (add `renders/`)

**Interfaces:**
- Consumes: nothing.
- Produces: `slugify(text: str) -> str`; `SUPERSAMPLE_FINAL: int = 4`; `SUPERSAMPLE_DRAFT: int = 1`; `MAX_PATH_LEN: int = 255`; `class Workspace` (frozen dataclass) with fields `root: Path`, `slug: str`, `mode: str` and members `base`, `spec_path`, `assets_dir`, `work_dir`, `shots_dir`, `overlays_dir`, `audio_dir`, `out_dir`, `logs_dir`, `manifest_path`, `concat_path`, `graph_path`, `master_path` (all `Path` properties); methods `asset(filename: str) -> Path`, `shot_clip(ordinal: int, shot_id: str, label: str) -> Path`, `overlay_png(ordinal: int, overlay_id: str, label: str) -> Path`, `overlay_bbox(ordinal: int, overlay_id: str, label: str) -> Path`, `audio_step(ordinal: str, label: str) -> Path`, `log_path(timestamp: str) -> Path`, `next_version() -> int`, `out_master(version: int) -> Path`, `out_cover(version: int) -> Path`, `out_srt(version: int) -> Path`, `out_ass(version: int) -> Path`, `out_qa_json(version: int) -> Path`, `out_qa_md(version: int) -> Path`, `out_contact_sheet(version: int) -> Path`, `draft_master() -> Path`, `ensure_dirs() -> None`.

- [ ] **Step 1: Create the package skeleton and pins**

`stitcher/requirements.txt`:

```
# Exact pins are load-bearing: Pillow's bundled freetype determines glyph
# rasterization, and golden-image tests compare against committed PNGs.
pydantic==2.9.2
Pillow==11.0.0
pytest==8.3.3
```

`stitcher/stitcher/__init__.py` and `stitcher/tests/__init__.py` are both empty files.

`stitcher/pytest.ini` — created **now**, not later, because every test module from Task 5 onward does `from tests.test_spec import MINIMAL, write`. Without `pythonpath`, that import only works under `python -m pytest` (which happens to put the cwd on `sys.path`) and breaks under a bare `pytest`:

```ini
[pytest]
pythonpath = .
testpaths = tests
markers =
    e2e: end-to-end render; needs a real ffmpeg on PATH
```

Append to the repo-root `.gitignore`:

```
# Asset stitcher workspaces — inputs, intermediates, and deliverables
renders/
```

- [ ] **Step 2: Write the failing test**

`stitcher/tests/test_naming.py`:

```python
from pathlib import Path

import pytest

from stitcher.naming import Workspace, slugify


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    return Workspace(root=tmp_path, slug="nobody-asked-the-kid", mode="final")


def test_slugify_lowercases_and_hyphenates():
    assert slugify("Best Part Was The MUD") == "best-part-was-the-mud"


def test_slugify_strips_punctuation_and_collapses_separators():
    assert slugify("Charlotte Mason -- 1886!") == "charlotte-mason-1886"


def test_slugify_truncates_long_text_without_trailing_hyphen():
    result = slugify("a" * 100)
    assert len(result) == 40
    assert not result.endswith("-")


def test_work_dir_is_partitioned_by_mode(tmp_path: Path):
    final = Workspace(root=tmp_path, slug="s", mode="final")
    draft = Workspace(root=tmp_path, slug="s", mode="draft")
    assert final.work_dir != draft.work_dir
    assert final.work_dir.name == "final"
    assert draft.work_dir.name == "draft"


def test_shot_clip_is_ordinal_id_label_and_sorts_in_playback_order(ws: Workspace):
    first = ws.shot_clip(1, "B-01", "hook")
    tenth = ws.shot_clip(10, "B-10", "payoff-research-2")
    assert first.name == "001_B-01_hook.mkv"
    assert tenth.name == "010_B-10_payoff-research-2.mkv"
    assert sorted([tenth.name, first.name])[0] == first.name


def test_overlay_png_and_bbox_share_a_stem(ws: Workspace):
    png = ws.overlay_png(1, "hook-1", "best-part-was-the-mud")
    bbox = ws.overlay_bbox(1, "hook-1", "best-part-was-the-mud")
    assert png.suffix == ".png"
    assert bbox.suffix == ".json"
    assert png.stem == bbox.stem


def test_audio_step_uses_chain_order_ordinals(ws: Workspace):
    assert ws.audio_step("04a", "bed_conformed").name == "04a_bed_conformed.wav"


def test_next_version_is_one_on_an_empty_workspace(ws: Workspace):
    ws.ensure_dirs()
    assert ws.next_version() == 1


def test_next_version_increments_past_the_highest_existing(ws: Workspace):
    ws.ensure_dirs()
    ws.out_master(1).write_bytes(b"")
    ws.out_master(7).write_bytes(b"")
    assert ws.next_version() == 8


def test_next_version_ignores_draft_outputs(ws: Workspace):
    ws.ensure_dirs()
    ws.draft_master().write_bytes(b"")
    assert ws.next_version() == 1


def test_out_master_is_version_stamped(ws: Workspace):
    assert ws.out_master(3).name == "nobody-asked-the-kid_v03_1080x1920.mp4"


def test_draft_master_is_not_versioned(ws: Workspace):
    assert ws.draft_master().name == "nobody-asked-the-kid_draft_1080x1920.mp4"


def test_master_path_lives_in_work_not_out(ws: Workspace):
    assert ws.master_path.parent == ws.work_dir
    assert ws.master_path.name == "master.mp4"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd stitcher && python -m pytest tests/test_naming.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stitcher.naming'`

- [ ] **Step 4: Implement `naming.py`**

`stitcher/stitcher/naming.py`:

```python
"""Single source of truth for every path and filename in a render workspace.

Filename conventions are behaviour, not formatting: they are asserted in
tests/test_naming.py. Nothing outside this module builds a workspace path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Supersample factor for Ken Burns moves. Position quantization at the working
# resolution is 1/SUPERSAMPLE output pixels; 4 gives 0.25px, invisible under
# lanczos. Draft skips supersampling entirely for speed.
SUPERSAMPLE_FINAL = 4
SUPERSAMPLE_DRAFT = 1

# Windows MAX_PATH. Long-path support is not assumed.
MAX_PATH_LEN = 255

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_SLUG_MAX = 40


def slugify(text: str) -> str:
    """Lowercase, hyphenate, and truncate text for use inside a filename."""
    lowered = _SLUG_STRIP.sub("-", text.lower()).strip("-")
    return lowered[:_SLUG_MAX].rstrip("-")


@dataclass(frozen=True)
class Workspace:
    """Every path for one Short, in one run mode."""

    root: Path
    slug: str
    mode: str  # "final" | "draft"

    # --- directories -----------------------------------------------------

    @property
    def base(self) -> Path:
        return self.root / self.slug

    @property
    def assets_dir(self) -> Path:
        return self.base / "assets"

    @property
    def work_dir(self) -> Path:
        return self.base / "work" / self.mode

    @property
    def shots_dir(self) -> Path:
        return self.work_dir / "shots"

    @property
    def overlays_dir(self) -> Path:
        return self.work_dir / "overlays"

    @property
    def audio_dir(self) -> Path:
        return self.work_dir / "audio"

    @property
    def out_dir(self) -> Path:
        return self.base / "out"

    @property
    def logs_dir(self) -> Path:
        return self.base / "logs"

    def ensure_dirs(self) -> None:
        for directory in (
            self.assets_dir,
            self.shots_dir,
            self.overlays_dir,
            self.audio_dir,
            self.out_dir,
            self.logs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    # --- work artifacts --------------------------------------------------

    @property
    def spec_path(self) -> Path:
        return self.base / "render-spec.json"

    @property
    def manifest_path(self) -> Path:
        return self.work_dir / "manifest.json"

    @property
    def concat_path(self) -> Path:
        return self.work_dir / "concat.txt"

    @property
    def graph_path(self) -> Path:
        return self.work_dir / "graph_assemble.txt"

    @property
    def master_path(self) -> Path:
        """Stage D output. Promoted to out/ only on a QA pass (spec §2 rule 5)."""
        return self.work_dir / "master.mp4"

    def asset(self, filename: str) -> Path:
        return self.assets_dir / filename

    def shot_clip(self, ordinal: int, shot_id: str, label: str) -> Path:
        return self.shots_dir / f"{ordinal:03d}_{shot_id}_{slugify(label)}.mkv"

    def overlay_png(self, ordinal: int, overlay_id: str, label: str) -> Path:
        return self.overlays_dir / f"{ordinal:03d}_{overlay_id}_{slugify(label)}.png"

    def overlay_bbox(self, ordinal: int, overlay_id: str, label: str) -> Path:
        return self.overlay_png(ordinal, overlay_id, label).with_suffix(".json")

    def audio_step(self, ordinal: str, label: str) -> Path:
        return self.audio_dir / f"{ordinal}_{label}.wav"

    def log_path(self, timestamp: str) -> Path:
        return self.logs_dir / f"{timestamp}_{self.mode}.log"

    # --- deliverables ----------------------------------------------------

    def out_master(self, version: int) -> Path:
        return self.out_dir / f"{self.slug}_v{version:02d}_1080x1920.mp4"

    def out_cover(self, version: int) -> Path:
        return self.out_dir / f"{self.slug}_v{version:02d}_cover_1080x1920.png"

    def out_srt(self, version: int) -> Path:
        return self.out_dir / f"{self.slug}_v{version:02d}.srt"

    def out_ass(self, version: int) -> Path:
        return self.out_dir / f"{self.slug}_v{version:02d}.ass"

    def out_qa_json(self, version: int) -> Path:
        return self.out_dir / f"{self.slug}_v{version:02d}_qa.json"

    def out_qa_md(self, version: int) -> Path:
        return self.out_dir / f"{self.slug}_v{version:02d}_qa.md"

    def out_contact_sheet(self, version: int) -> Path:
        return self.out_dir / f"{self.slug}_v{version:02d}_contact-sheet.png"

    def draft_master(self) -> Path:
        """Drafts are disposable and never consume a version number."""
        return self.out_dir / f"{self.slug}_draft_1080x1920.mp4"

    def next_version(self) -> int:
        """One above the highest version already promoted into out/."""
        pattern = re.compile(rf"^{re.escape(self.slug)}_v(\d+)_1080x1920\.mp4$")
        highest = 0
        if self.out_dir.exists():
            for entry in self.out_dir.iterdir():
                match = pattern.match(entry.name)
                if match:
                    highest = max(highest, int(match.group(1)))
        return highest + 1
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_naming.py -v`
Expected: PASS — 13 passed

- [ ] **Step 6: Commit**

```bash
git add stitcher/requirements.txt stitcher/pytest.ini stitcher/stitcher/__init__.py stitcher/stitcher/naming.py stitcher/tests/__init__.py stitcher/tests/test_naming.py .gitignore
git commit -m "feat(stitcher): package scaffold and workspace naming"
```

---

### Task 2: `spec.py` — models, quantization, validation

**Files:**
- Create: `stitcher/stitcher/spec.py`
- Test: `stitcher/tests/test_spec.py`

**Interfaces:**
- Consumes: nothing from Task 1 (pure; `cli.py` wires them together later).
- Produces: models `Canvas`, `SafeZone`, `Style`, `Motion`, `Transition`, `Shot`, `Overlay`, `Caption`, `Stem`, `BedWindow`, `Fade`, `Bed`, `Sfx`, `Loudness`, `Audio`, `Cover`, `Delivery`, `RenderSpec`; functions `quantize(seconds: float, fps: int) -> int`, `frame_residual(seconds: float, fps: int) -> float`, `load_spec(path: Path) -> tuple[RenderSpec, list[str]]`, `validate_spec(spec: RenderSpec) -> list[str]`, `runtime_seconds(spec: RenderSpec) -> float`, `shot_frame_bounds(spec: RenderSpec) -> list[tuple[int, int]]`.
- **Naming note for all later tasks:** JSON keys `in`/`out` are Python keywords or shadow builtins, so every model exposes them as `start`/`end` with pydantic aliases. Always read `shot.start`, never `shot.in_`.

- [ ] **Step 1: Write the failing test**

`stitcher/tests/test_spec.py`:

```python
import json
from pathlib import Path

import pytest

from stitcher.spec import (
    RenderSpec,
    frame_residual,
    load_spec,
    quantize,
    runtime_seconds,
    shot_frame_bounds,
    validate_spec,
)

MINIMAL = {
    "spec_version": "1.0",
    "slug": "demo",
    "canvas": {"width": 1080, "height": 1920, "fps": 30},
    "safe_zone": {"x": 90, "y": 380, "width": 900, "height": 1160},
    "styles": {
        "card": {
            "font_file": "fonts/Inter-Bold.ttf",
            "size_px": 72,
            "body": "#F7F3E8",
            "accent": "#F2A541",
            "ground": "#0E3B43",
            "ground_opacity": 0.85,
            "padding_px": [32, 40],
            "line_spacing": 1.15,
            "align": "center",
            "max_width_px": 820,
            "max_lines": 4,
            "stroke_px": 0,
            "stroke_color": "#000000",
        }
    },
    "shots": [
        {
            "n": 1,
            "id": "B-01",
            "beat": "Hook",
            "in": 0.0,
            "out": 3.0,
            "source": "a.png",
            "kind": "still",
            "motion": {"kind": "push_in", "amount_pct": 15},
            "transition_in": {"kind": "cut"},
        },
        {
            "n": 2,
            "id": "B-02",
            "beat": "Setup",
            "in": 3.0,
            "out": 6.0,
            "source": "b.png",
            "kind": "still",
            "motion": {"kind": "none"},
            "transition_in": {"kind": "cut"},
        },
    ],
    "overlays": [
        {"id": "hook-1", "style": "card", "in": 0.0, "out": 2.0,
         "anchor": "center", "offset_px": [0, 0], "text": "HELLO [[WORLD]]"}
    ],
    "captions": [{"in": 0.0, "out": 2.9, "text": "Hello world."}],
    "captions_style": "card",
    "audio": {
        "stems": [{"id": "vo", "file": "vo.wav", "at": 0.0, "gain_db": 0.0}],
        "bed": {
            "file": "bed.mp3", "gain_db": -8.0, "duck_db": -22.0,
            "duck_attack_ms": 120, "duck_release_ms": 400,
            "windows": [], "fades": [],
        },
        "sfx": [],
        "loudness": {"integrated_lufs": -14.0, "true_peak_dbtp": -1.5},
    },
    "cover": {"source": "cover.png", "overlays": []},
    "delivery": {
        "codec": "libx264", "crf": 18, "preset": "slow", "profile": "high",
        "pix_fmt": "yuv420p", "audio_codec": "aac",
        "audio_bitrate": "192k", "audio_rate": 48000,
    },
}


def write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "render-spec.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_quantize_rounds_to_nearest_frame():
    assert quantize(2.0, 30) == 60
    assert quantize(2.875, 30) == 86
    assert quantize(21.5, 30) == 645


def test_frame_residual_reports_non_frame_aligned_times():
    assert frame_residual(21.5, 30) == pytest.approx(0.0)
    assert frame_residual(2.875, 30) == pytest.approx(0.25)


def test_load_spec_warns_about_non_frame_aligned_times(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][0]["out"] = 2.875
    payload["shots"][1]["in"] = 2.875
    spec, warnings = load_spec(write(tmp_path, payload))
    assert any("2.875" in w and "86.25" in w for w in warnings)


def test_load_spec_exposes_in_out_as_start_end(tmp_path: Path):
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    assert spec.shots[0].start == 0.0
    assert spec.shots[0].end == 3.0


def test_shot_frame_bounds_are_derived_by_differencing_boundaries(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][0]["out"] = 2.875
    payload["shots"][1]["in"] = 2.875
    spec, _ = load_spec(write(tmp_path, payload))
    bounds = shot_frame_bounds(spec)
    # Boundary 2.875s quantizes to frame 86 once, shared by both shots.
    assert bounds == [(0, 86), (86, 180)]
    assert bounds[-1][1] == quantize(runtime_seconds(spec), spec.canvas.fps)


def test_validate_accepts_the_minimal_spec(tmp_path: Path):
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    assert validate_spec(spec) == []


def test_validate_rejects_non_contiguous_shots(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][1]["in"] = 3.5
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("contiguous" in e for e in validate_spec(spec))


def test_validate_rejects_non_1080x1920_canvas(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["canvas"]["width"] = 720
    payload["canvas"]["height"] = 1280
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("1080" in e for e in validate_spec(spec))


def test_validate_rejects_clip_without_source_trim(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][0]["kind"] = "clip"
    payload["shots"][0]["source"] = "a.mp4"
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("source_in" in e for e in validate_spec(spec))


def test_validate_rejects_whip_without_direction(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][1]["transition_in"] = {"kind": "whip", "frames": 4}
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("direction" in e for e in validate_spec(spec))


def test_validate_rejects_overlapping_bed_windows(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["audio"]["bed"]["windows"] = [
        {"in": 0.0, "out": 3.0, "mode": "out", "level_db": None},
        {"in": 2.0, "out": 5.0, "mode": "ducked", "level_db": None},
    ]
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("overlap" in e for e in validate_spec(spec))


def test_validate_rejects_unknown_captions_style(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["captions_style"] = "nope"
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("captions_style" in e for e in validate_spec(spec))


def test_validate_rejects_overlapping_captions(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["captions"] = [
        {"in": 0.0, "out": 2.0, "text": "one"},
        {"in": 1.5, "out": 3.0, "text": "two"},
    ]
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("caption" in e.lower() for e in validate_spec(spec))


def test_validate_rejects_overlay_past_runtime(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["overlays"][0]["out"] = 99.0
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("runtime" in e for e in validate_spec(spec))


def test_unknown_spec_version_is_rejected(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["spec_version"] = "9.9"
    with pytest.raises(ValueError):
        load_spec(write(tmp_path, payload))


def test_unsupported_transition_names_v1(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][1]["transition_in"] = {"kind": "dissolve"}
    with pytest.raises(ValueError, match="not implemented in v1"):
        load_spec(write(tmp_path, payload))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd stitcher && python -m pytest tests/test_spec.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stitcher.spec'`

- [ ] **Step 3: Implement `spec.py`**

`stitcher/stitcher/spec.py`:

```python
"""Render spec models, frame quantization, and validation.

JSON uses `in`/`out`; Python exposes `start`/`end` because `in` is a keyword.
Quantization applies to absolute boundaries only — durations are derived by
differencing, so rounding error cannot accumulate across shots (spec §3).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SUPPORTED_SPEC_VERSIONS = {"1.0"}
V1_TRANSITIONS = {"cut", "whip"}
V1_CANVAS = (1080, 1920)


class _Base(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class Canvas(_Base):
    width: int
    height: int
    fps: int


class SafeZone(_Base):
    x: int
    y: int
    width: int
    height: int


class Style(_Base):
    font_file: str
    size_px: int
    body: str
    accent: str
    ground: str | None = None
    ground_opacity: float = 1.0
    padding_px: tuple[int, int] = (0, 0)
    line_spacing: float = 1.0
    align: Literal["left", "center", "right"] = "center"
    max_width_px: int
    max_lines: int
    stroke_px: int = 0
    stroke_color: str = "#000000"


class Motion(_Base):
    kind: Literal["push_in", "pull_out", "scale_up", "none"] = "none"
    amount_pct: float = 0.0
    anchor_start: tuple[float, float] = (0.5, 0.5)
    anchor_end: tuple[float, float] = (0.5, 0.5)
    hold_s: float = 0.0
    ease: Literal["linear", "ease_in", "ease_out", "ease_in_out"] = "linear"


class Transition(_Base):
    kind: str = "cut"
    direction: Literal["left", "right", "up", "down"] | None = None
    frames: int = 4


class Shot(_Base):
    n: int
    id: str
    beat: str
    start: float = Field(alias="in")
    end: float = Field(alias="out")
    source: str
    kind: Literal["still", "clip"]
    source_in: float | None = None
    source_out: float | None = None
    motion: Motion = Motion()
    transition_in: Transition = Transition()


class Overlay(_Base):
    id: str
    style: str
    start: float = Field(alias="in")
    end: float = Field(alias="out")
    anchor: Literal["center", "upper_third", "lower_third"] = "center"
    offset_px: tuple[int, int] = (0, 0)
    text: str


class Caption(_Base):
    start: float = Field(alias="in")
    end: float = Field(alias="out")
    text: str


class Stem(_Base):
    id: str
    file: str
    at: float
    gain_db: float = 0.0
    duration_s: float | None = None


class BedWindow(_Base):
    start: float = Field(alias="in")
    end: float = Field(alias="out")
    mode: Literal["out", "ducked", "full"]
    level_db: float | None = None


class Fade(_Base):
    at: float
    kind: Literal["in", "out"]
    ms: int


class Bed(_Base):
    file: str
    gain_db: float
    duck_db: float
    duck_attack_ms: int = 120
    duck_release_ms: int = 400
    windows: list[BedWindow] = []
    fades: list[Fade] = []


class Sfx(_Base):
    file: str
    at: float
    gain_db: float = 0.0


class Loudness(_Base):
    integrated_lufs: float
    true_peak_dbtp: float


class Audio(_Base):
    stems: list[Stem]
    bed: Bed | None = None
    sfx: list[Sfx] = []
    loudness: Loudness


class Cover(_Base):
    source: str
    overlays: list[str] = []


class Delivery(_Base):
    codec: str = "libx264"
    crf: int = 18
    preset: str = "slow"
    profile: str = "high"
    pix_fmt: str = "yuv420p"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    audio_rate: int = 48000


class RenderSpec(_Base):
    spec_version: str
    slug: str
    canvas: Canvas
    safe_zone: SafeZone
    styles: dict[str, Style]
    shots: list[Shot]
    overlays: list[Overlay] = []
    captions: list[Caption] = []
    captions_style: str
    audio: Audio
    cover: Cover | None = None
    delivery: Delivery = Delivery()


# --- frame maths ---------------------------------------------------------


def quantize(seconds: float, fps: int) -> int:
    """Absolute time in seconds -> frame index, rounded to nearest."""
    return int(round(seconds * fps))


def frame_residual(seconds: float, fps: int) -> float:
    """How far this time sits from a frame boundary, in frames."""
    exact = seconds * fps
    return abs(exact - round(exact))


def runtime_seconds(spec: RenderSpec) -> float:
    return spec.shots[-1].end if spec.shots else 0.0


def shot_frame_bounds(spec: RenderSpec) -> list[tuple[int, int]]:
    """Quantize each boundary once; derive durations by differencing."""
    fps = spec.canvas.fps
    boundaries = [quantize(spec.shots[0].start, fps)] if spec.shots else []
    for shot in spec.shots:
        boundaries.append(quantize(shot.end, fps))
    return [(boundaries[i], boundaries[i + 1]) for i in range(len(boundaries) - 1)]


# --- loading -------------------------------------------------------------


def _collect_times(payload: dict) -> list[tuple[str, float]]:
    times: list[tuple[str, float]] = []
    for shot in payload.get("shots", []):
        times.append((f"shots[{shot.get('n')}].in", shot["in"]))
        times.append((f"shots[{shot.get('n')}].out", shot["out"]))
    for overlay in payload.get("overlays", []):
        times.append((f"overlays[{overlay.get('id')}].in", overlay["in"]))
        times.append((f"overlays[{overlay.get('id')}].out", overlay["out"]))
    for stem in payload.get("audio", {}).get("stems", []):
        times.append((f"audio.stems[{stem.get('id')}].at", stem["at"]))
    return times


def load_spec(path: Path) -> tuple[RenderSpec, list[str]]:
    """Parse and frame-check a spec. Raises ValueError on unusable input."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    version = payload.get("spec_version")
    if version not in SUPPORTED_SPEC_VERSIONS:
        raise ValueError(f"unsupported spec_version {version!r}")

    for shot in payload.get("shots", []):
        kind = shot.get("transition_in", {}).get("kind", "cut")
        if kind not in V1_TRANSITIONS:
            raise ValueError(
                f"transition_in.kind {kind!r} is not implemented in v1 "
                f"(shot {shot.get('id')}); only {sorted(V1_TRANSITIONS)} are supported"
            )

    try:
        spec = RenderSpec.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"spec failed schema validation:\n{exc}") from exc

    fps = spec.canvas.fps
    warnings = [
        f"{label} = {value}s is not frame-aligned at {fps}fps "
        f"({value * fps:.2f} frames); it will render at frame {quantize(value, fps)}"
        for label, value in _collect_times(payload)
        if frame_residual(value, fps) > 1e-9
    ]
    return spec, warnings


# --- validation ----------------------------------------------------------


def validate_spec(spec: RenderSpec) -> list[str]:
    """Internal-consistency errors. Never touches assets (spec §3)."""
    errors: list[str] = []

    if (spec.canvas.width, spec.canvas.height) != V1_CANVAS:
        errors.append(
            f"canvas {spec.canvas.width}x{spec.canvas.height} is not supported in v1; "
            "only 1080x1920 is implemented"
        )

    if not spec.shots:
        errors.append("shots must not be empty")
        return errors

    for previous, shot in zip(spec.shots, spec.shots[1:]):
        if shot.start != previous.end:
            errors.append(
                f"shots are not contiguous: shot {previous.id} ends at {previous.end}s "
                f"but shot {shot.id} starts at {shot.start}s"
            )

    for shot in spec.shots:
        if shot.end <= shot.start:
            errors.append(f"shot {shot.id} has non-positive duration")
        if shot.kind == "clip" and (shot.source_in is None or shot.source_out is None):
            errors.append(
                f"shot {shot.id} is kind 'clip' and must declare source_in and source_out"
            )
        if shot.transition_in.kind == "whip" and shot.transition_in.direction is None:
            errors.append(
                f"shot {shot.id} has a whip transition without a direction; "
                "direction is required and has no default"
            )

    runtime = runtime_seconds(spec)

    for overlay in spec.overlays:
        if overlay.style not in spec.styles:
            errors.append(f"overlay {overlay.id} references unknown style {overlay.style!r}")
        if overlay.end > runtime or overlay.start < 0:
            errors.append(
                f"overlay {overlay.id} spans {overlay.start}-{overlay.end}s, "
                f"outside the runtime 0-{runtime}s"
            )

    if spec.captions_style not in spec.styles:
        errors.append(f"captions_style {spec.captions_style!r} is not defined in styles")

    for previous, caption in zip(spec.captions, spec.captions[1:]):
        if caption.start < previous.end:
            errors.append(
                f"captions overlap: one ends at {previous.end}s, the next starts at {caption.start}s"
            )
    for caption in spec.captions:
        if caption.end > runtime or caption.start < 0:
            errors.append(f"caption at {caption.start}s falls outside the runtime 0-{runtime}s")

    if spec.audio.bed:
        windows = sorted(spec.audio.bed.windows, key=lambda w: w.start)
        for previous, window in zip(windows, windows[1:]):
            if window.start < previous.end:
                errors.append(
                    f"bed windows overlap at {window.start}s; overlapping windows are rejected "
                    "so precedence among them never arises"
                )

    if spec.cover and spec.cover.overlays:
        known = {overlay.id for overlay in spec.overlays}
        for name in spec.cover.overlays:
            if name not in known:
                errors.append(f"cover references unknown overlay id {name!r}")

    return errors
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_spec.py -v`
Expected: PASS — 18 passed

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/spec.py stitcher/tests/test_spec.py
git commit -m "feat(stitcher): render spec models, frame quantization, validation"
```

---

### Task 3: `ffmpeg.py` — subprocess wrapper, probing, capability checks

**Files:**
- Create: `stitcher/stitcher/ffmpeg.py`
- Test: `stitcher/tests/test_ffmpeg.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `class FFmpegError(RuntimeError)`; `@dataclass ProbeResult` with fields `duration: float`, `width: int | None`, `height: int | None`, `fps: float | None`, `pix_fmt: str | None`, `video_codec: str | None`, `audio_codec: str | None`, `sample_rate: int | None`, `colorspace: str | None`, `profile: str | None = None` (last, with a default, so positional construction in tests stays valid), and properties `has_video: bool`, `has_audio: bool`; functions `run(args: list[str], log_path: Path) -> str` (returns stderr), `probe(path: Path) -> ProbeResult`, `ffmpeg_version() -> str`, `has_encoder(name: str) -> bool`, `measure_loudness(path: Path, log_path: Path) -> dict` returning keys `input_i`, `input_tp`, `input_lra`.

- [ ] **Step 1: Write the failing test**

`stitcher/tests/test_ffmpeg.py`:

```python
import json
import subprocess
from pathlib import Path

import pytest

from stitcher import ffmpeg as ff


def test_run_writes_the_command_to_the_log_before_executing(tmp_path: Path, monkeypatch):
    log = tmp_path / "run.log"
    seen: dict[str, bool] = {}

    def fake_run(args, capture_output, text, check, cwd=None):
        # The log must already exist and name the command by the time we execute.
        seen["logged"] = log.exists() and "-version" in log.read_text(encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "", "ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ff.run(["ffmpeg", "-version"], log)
    assert seen["logged"] is True


def test_run_raises_with_the_command_and_stderr_tail(tmp_path: Path, monkeypatch):
    def fake_run(args, capture_output, text, check, cwd=None):
        return subprocess.CompletedProcess(args, 1, "", "boom: invalid argument")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(ff.FFmpegError) as exc:
        ff.run(["ffmpeg", "-nope"], tmp_path / "run.log")
    assert "-nope" in str(exc.value)
    assert "boom: invalid argument" in str(exc.value)


def test_run_never_uses_a_shell(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(args, capture_output, text, check, cwd=None):
        captured["args"] = args
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ff.run(["ffmpeg", "-i", "C:/a b/c.png"], tmp_path / "run.log")
    assert isinstance(captured["args"], list)


def test_probe_parses_a_video_stream(tmp_path: Path, monkeypatch):
    payload = {
        "format": {"duration": "3.500000"},
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1080,
             "height": 1920, "pix_fmt": "yuv420p", "r_frame_rate": "30000/1001",
             "color_space": "bt709"},
            {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000"},
        ],
    }
    monkeypatch.setattr(ff, "_probe_json", lambda path: payload)
    result = ff.probe(tmp_path / "x.mp4")
    assert result.duration == pytest.approx(3.5)
    assert result.width == 1080
    assert result.fps == pytest.approx(30000 / 1001)
    assert result.video_codec == "h264"
    assert result.audio_codec == "aac"
    assert result.sample_rate == 48000
    assert result.colorspace == "bt709"
    assert result.has_video and result.has_audio


def test_probe_handles_an_audio_only_file(tmp_path: Path, monkeypatch):
    payload = {
        "format": {"duration": "2.875000"},
        "streams": [{"codec_type": "audio", "codec_name": "pcm_s16le",
                     "sample_rate": "48000"}],
    }
    monkeypatch.setattr(ff, "_probe_json", lambda path: payload)
    result = ff.probe(tmp_path / "vo.wav")
    assert result.has_audio and not result.has_video
    assert result.width is None
    assert result.duration == pytest.approx(2.875)


def test_measure_loudness_parses_the_ebur128_summary(tmp_path: Path, monkeypatch):
    stderr = (
        "[Parsed_ebur128_0 @ 0000] Summary:\n"
        "  Integrated loudness:\n"
        "    I:         -14.3 LUFS\n"
        "    Threshold: -24.8 LUFS\n"
        "  Loudness range:\n"
        "    LRA:         6.2 LU\n"
        "  True peak:\n"
        "    Peak:       -1.7 dBFS\n"
    )
    monkeypatch.setattr(ff, "run", lambda args, log_path: stderr)
    result = ff.measure_loudness(tmp_path / "mix.wav", tmp_path / "run.log")
    assert result["input_i"] == pytest.approx(-14.3)
    assert result["input_tp"] == pytest.approx(-1.7)
    assert result["input_lra"] == pytest.approx(6.2)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd stitcher && python -m pytest tests/test_ffmpeg.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stitcher.ffmpeg'`

- [ ] **Step 3: Implement `ffmpeg.py`**

`stitcher/stitcher/ffmpeg.py`:

```python
"""Thin, logged wrapper around the ffmpeg and ffprobe binaries.

Every command is appended to the run log *before* it executes, so a failure
hands you a pasteable command rather than a traceback wrapping a subprocess
error (spec §6). shell=True is never used.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

STDERR_TAIL_LINES = 40


class FFmpegError(RuntimeError):
    """A non-zero exit from ffmpeg or ffprobe."""


@dataclass(frozen=True)
class ProbeResult:
    duration: float
    width: int | None
    height: int | None
    fps: float | None
    pix_fmt: str | None
    video_codec: str | None
    audio_codec: str | None
    sample_rate: int | None
    colorspace: str | None
    # Last, with a default, so existing positional constructions stay valid.
    profile: str | None = None

    @property
    def has_video(self) -> bool:
        return self.video_codec is not None

    @property
    def has_audio(self) -> bool:
        return self.audio_codec is not None


def _quote_for_log(arg: str) -> str:
    return f'"{arg}"' if " " in arg else arg


def run(args: list[str], log_path: Path) -> str:
    """Execute a command, returning stderr. Logs before running."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = " ".join(_quote_for_log(a) for a in args)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"$ {line}\n")

    completed = subprocess.run(args, capture_output=True, text=True, check=False)

    if completed.stderr:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(completed.stderr)
            handle.write("\n")

    if completed.returncode != 0:
        tail = "\n".join((completed.stderr or "").splitlines()[-STDERR_TAIL_LINES:])
        raise FFmpegError(f"command failed (exit {completed.returncode}):\n{line}\n\n{tail}")

    return completed.stderr or ""


def _probe_json(path: Path) -> dict:
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise FFmpegError(f"ffprobe failed on {path}:\n{completed.stderr}")
    return json.loads(completed.stdout)


def _parse_rate(value: str | None) -> float | None:
    if not value or "/" not in value:
        return None
    numerator, denominator = value.split("/", 1)
    denom = float(denominator)
    return float(numerator) / denom if denom else None


def probe(path: Path) -> ProbeResult:
    payload = _probe_json(path)
    video = next((s for s in payload["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in payload["streams"] if s["codec_type"] == "audio"), None)
    return ProbeResult(
        duration=float(payload.get("format", {}).get("duration", 0.0)),
        width=video.get("width") if video else None,
        height=video.get("height") if video else None,
        fps=_parse_rate(video.get("r_frame_rate")) if video else None,
        pix_fmt=video.get("pix_fmt") if video else None,
        video_codec=video.get("codec_name") if video else None,
        audio_codec=audio.get("codec_name") if audio else None,
        sample_rate=int(audio["sample_rate"]) if audio and audio.get("sample_rate") else None,
        colorspace=video.get("color_space") if video else None,
        profile=video.get("profile") if video else None,
    )


def ffmpeg_version() -> str:
    """First line of `ffmpeg -version`. Part of every cache key (spec §5)."""
    completed = subprocess.run(
        ["ffmpeg", "-version"], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise FFmpegError("ffmpeg is not available on PATH")
    return completed.stdout.splitlines()[0].strip()


def has_encoder(name: str) -> bool:
    completed = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, check=False
    )
    return completed.returncode == 0 and name in completed.stdout


_I = re.compile(r"^\s*I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", re.MULTILINE)
_TP = re.compile(r"^\s*Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", re.MULTILINE)
_LRA = re.compile(r"^\s*LRA:\s*(-?\d+(?:\.\d+)?)\s*LU", re.MULTILINE)


def measure_loudness(path: Path, log_path: Path) -> dict:
    """Integrated LUFS, true peak, and LRA via the ebur128 filter."""
    stderr = run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
        log_path,
    )

    def grab(pattern: re.Pattern[str], label: str) -> float:
        matches = pattern.findall(stderr)
        if not matches:
            raise FFmpegError(f"could not read {label} from ebur128 output for {path}")
        return float(matches[-1])

    return {
        "input_i": grab(_I, "integrated loudness"),
        "input_tp": grab(_TP, "true peak"),
        "input_lra": grab(_LRA, "loudness range"),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_ffmpeg.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/ffmpeg.py stitcher/tests/test_ffmpeg.py
git commit -m "feat(stitcher): logged ffmpeg wrapper, probing, loudness measurement"
```

---

### Task 4: `cache.py` — content hashing and the stage manifest

**Files:**
- Create: `stitcher/stitcher/cache.py`
- Test: `stitcher/tests/test_cache.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `file_digest(path: Path) -> str`; `payload_digest(*parts: object) -> str`; `class Manifest` with `__init__(self, path: Path)`, `get(key: str) -> str | None`, `set(key: str, digest: str) -> None`, `save() -> None`, `is_fresh(key: str, digest: str, artifact: Path) -> bool`, and classmethod `load(path: Path) -> Manifest`.

- [ ] **Step 1: Write the failing test**

`stitcher/tests/test_cache.py`:

```python
from pathlib import Path

from stitcher.cache import Manifest, file_digest, payload_digest


def test_file_digest_changes_with_content(tmp_path: Path):
    target = tmp_path / "a.bin"
    target.write_bytes(b"one")
    first = file_digest(target)
    target.write_bytes(b"two")
    assert file_digest(target) != first


def test_file_digest_of_a_missing_file_is_stable_and_distinct(tmp_path: Path):
    missing = tmp_path / "nope.bin"
    assert file_digest(missing) == file_digest(missing)
    present = tmp_path / "yes.bin"
    present.write_bytes(b"")
    assert file_digest(missing) != file_digest(present)


def test_payload_digest_is_order_sensitive():
    assert payload_digest("a", "b") != payload_digest("b", "a")


def test_payload_digest_is_stable_across_calls():
    assert payload_digest({"k": 1}, [2, 3]) == payload_digest({"k": 1}, [2, 3])


def test_is_fresh_requires_both_a_matching_digest_and_a_present_artifact(tmp_path: Path):
    manifest = Manifest(tmp_path / "manifest.json")
    artifact = tmp_path / "shot.mkv"
    manifest.set("shots/001", "abc")

    assert manifest.is_fresh("shots/001", "abc", artifact) is False  # artifact missing
    artifact.write_bytes(b"x")
    assert manifest.is_fresh("shots/001", "abc", artifact) is True
    assert manifest.is_fresh("shots/001", "different", artifact) is False
    assert manifest.is_fresh("shots/999", "abc", artifact) is False


def test_manifest_round_trips_through_disk(tmp_path: Path):
    path = tmp_path / "manifest.json"
    manifest = Manifest(path)
    manifest.set("audio/mix", "deadbeef")
    manifest.save()

    reloaded = Manifest.load(path)
    assert reloaded.get("audio/mix") == "deadbeef"


def test_loading_a_missing_manifest_yields_an_empty_one(tmp_path: Path):
    manifest = Manifest.load(tmp_path / "absent.json")
    assert manifest.get("anything") is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd stitcher && python -m pytest tests/test_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stitcher.cache'`

- [ ] **Step 3: Implement `cache.py`**

`stitcher/stitcher/cache.py`:

```python
"""Content hashing and the per-mode stage manifest.

The manifest lives at work/<mode>/manifest.json. Because work/ is partitioned
by run mode, a cached draft artifact can never satisfy a final-mode lookup
(spec §2 rule 4, §5).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

_CHUNK = 1 << 20
_MISSING_SENTINEL = b"\x00stitcher:missing\x00"


def file_digest(path: Path) -> str:
    """SHA-256 of a file's bytes. Missing files hash to a stable sentinel."""
    digest = hashlib.sha256()
    if not path.exists():
        digest.update(_MISSING_SENTINEL)
        digest.update(str(path.name).encode("utf-8"))
        return digest.hexdigest()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def payload_digest(*parts: object) -> str:
    """SHA-256 over a JSON rendering of the parts, in the order given."""
    blob = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Manifest:
    """Maps a stage artifact key to the digest of everything determining it."""

    def __init__(self, path: Path, entries: dict[str, str] | None = None) -> None:
        self.path = path
        self._entries: dict[str, str] = dict(entries or {})

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        if not path.exists():
            return cls(path)
        return cls(path, json.loads(path.read_text(encoding="utf-8")))

    def get(self, key: str) -> str | None:
        return self._entries.get(key)

    def set(self, key: str, digest: str) -> None:
        self._entries[key] = digest

    def is_fresh(self, key: str, digest: str, artifact: Path) -> bool:
        """A cache hit needs both a matching digest and a surviving artifact."""
        return self._entries.get(key) == digest and artifact.exists()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._entries, indent=2, sort_keys=True), encoding="utf-8"
        )

    def as_dict(self) -> dict[str, str]:
        return dict(self._entries)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_cache.py -v`
Expected: PASS — 7 passed

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/cache.py stitcher/tests/test_cache.py
git commit -m "feat(stitcher): content hashing and stage manifest"
```

---

### Task 5: `preflight.py` — asset probing, tool checks, path length

**Files:**
- Create: `stitcher/stitcher/preflight.py`
- Test: `stitcher/tests/test_preflight.py`

**Interfaces:**
- Consumes: `spec.RenderSpec`, `spec.validate_spec`, `spec.runtime_seconds`; `naming.Workspace`, `naming.MAX_PATH_LEN`; `ffmpeg.probe`, `ffmpeg.ffmpeg_version`, `ffmpeg.has_encoder`, `ffmpeg.ProbeResult`.
- Produces: `@dataclass PreflightReport` with fields `errors: list[str]`, `warnings: list[str]`, `missing_visual: list[str]`, `missing_audio: list[str]` and property `ok: bool`; function `run_preflight(spec: RenderSpec, ws: Workspace, mode: str) -> PreflightReport`.

- [ ] **Step 1: Write the failing test**

`stitcher/tests/test_preflight.py`:

```python
import json
from pathlib import Path

import pytest

from stitcher import preflight as pf
from stitcher.ffmpeg import ProbeResult
from stitcher.naming import Workspace
from stitcher.spec import load_spec
from tests.test_spec import MINIMAL, write


def still(duration: float = 0.0) -> ProbeResult:
    return ProbeResult(duration, 1080, 1920, None, "rgba", "png", None, None, None)


def clip(duration: float) -> ProbeResult:
    return ProbeResult(duration, 1080, 1920, 24.0, "yuv420p", "h264", None, None, "bt709")


def wav(duration: float) -> ProbeResult:
    return ProbeResult(duration, None, None, None, None, None, "pcm_s16le", 48000, None)


@pytest.fixture
def ready(tmp_path: Path, monkeypatch):
    """A workspace whose spec is valid and whose tools are present."""
    monkeypatch.setattr(pf.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 8.0.1")
    monkeypatch.setattr(pf.ffmpeg, "has_encoder", lambda name: name == "libx264")
    ws = Workspace(root=tmp_path, slug="demo", mode="final")
    ws.ensure_dirs()
    for name in ("a.png", "b.png", "cover.png", "vo.wav", "bed.mp3"):
        ws.asset(name).write_bytes(b"x")
    (tmp_path / "fonts").mkdir(exist_ok=True)
    return ws


def load(tmp_path: Path, payload: dict):
    spec, _ = load_spec(write(tmp_path / "spec", payload))
    return spec


@pytest.fixture
def spec_and_font(tmp_path: Path, ready):
    payload = json.loads(json.dumps(MINIMAL))
    font = tmp_path / "Inter-Bold.ttf"
    font.write_bytes(b"font")
    payload["styles"]["card"]["font_file"] = str(font)
    (tmp_path / "spec").mkdir(exist_ok=True)
    return load(tmp_path, payload), ready


def test_preflight_passes_when_everything_is_present(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "final")
    assert report.errors == []
    assert report.ok is True


def test_preflight_reports_every_problem_not_just_the_first(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    ws.asset("a.png").unlink()
    ws.asset("b.png").unlink()
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "final")
    assert len(report.errors) >= 2


def test_final_mode_treats_a_missing_visual_asset_as_an_error(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    ws.asset("a.png").unlink()
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "final")
    assert any("a.png" in e for e in report.errors)


def test_draft_mode_records_a_missing_visual_as_a_placeholder(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    ws.asset("a.png").unlink()
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "draft")
    assert "a.png" in report.missing_visual
    assert not any("a.png" in e for e in report.errors)


def test_draft_mode_aborts_on_a_missing_stem_without_duration_s(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    ws.asset("vo.wav").unlink()
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "draft")
    assert any("duration_s" in e for e in report.errors)


def test_draft_mode_allows_a_missing_stem_that_declares_duration_s(tmp_path, ready, monkeypatch):
    payload = json.loads(json.dumps(MINIMAL))
    font = tmp_path / "Inter-Bold.ttf"
    font.write_bytes(b"font")
    payload["styles"]["card"]["font_file"] = str(font)
    payload["audio"]["stems"][0]["duration_s"] = 2.875
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    ready.asset("vo.wav").unlink()
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ready, "draft")
    assert "vo.wav" in report.missing_audio
    assert report.errors == []


def test_source_trim_outside_the_real_duration_is_a_preflight_error(tmp_path, ready, monkeypatch):
    payload = json.loads(json.dumps(MINIMAL))
    font = tmp_path / "Inter-Bold.ttf"
    font.write_bytes(b"font")
    payload["styles"]["card"]["font_file"] = str(font)
    payload["shots"][0].update(
        {"kind": "clip", "source": "a.mp4", "source_in": 0.0, "source_out": 9.0}
    )
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    ready.asset("a.mp4").write_bytes(b"x")
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: clip(5.0))
    report = pf.run_preflight(spec, ready, "final")
    assert any("source_out" in e and "5.0" in e for e in report.errors)


def test_a_missing_font_file_is_an_error(tmp_path, ready, monkeypatch):
    payload = json.loads(json.dumps(MINIMAL))
    payload["styles"]["card"]["font_file"] = str(tmp_path / "absent.ttf")
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ready, "final")
    assert any("absent.ttf" in e for e in report.errors)


def test_missing_libx264_is_an_error(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    monkeypatch.setattr(pf.ffmpeg, "has_encoder", lambda name: False)
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "final")
    assert any("libx264" in e for e in report.errors)


def test_libass_is_never_required(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    monkeypatch.setattr(pf.ffmpeg, "has_encoder", lambda name: name == "libx264")
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "final")
    assert not any("libass" in e.lower() for e in report.errors)


def test_an_over_long_path_is_an_error(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    monkeypatch.setattr(pf, "MAX_PATH_LEN", 10)
    report = pf.run_preflight(spec, ws, "final")
    assert any("path" in e.lower() for e in report.errors)


def test_a_non_8x_ffmpeg_is_an_error(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    monkeypatch.setattr(pf.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 7.1")
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "final")
    assert any("8" in e for e in report.errors)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd stitcher && python -m pytest tests/test_preflight.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stitcher.preflight'`

- [ ] **Step 3: Implement `preflight.py`**

`stitcher/stitcher/preflight.py`:

```python
"""Everything that must be true before a single frame renders.

Runs to completion and reports every problem at once rather than the first
(spec §6). In final mode any failure aborts; in draft mode a missing visual
asset becomes a placeholder, and a missing stem is tolerated only when it
declares duration_s.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import ffmpeg
from .naming import MAX_PATH_LEN, Workspace
from .spec import RenderSpec, runtime_seconds, validate_spec

_VERSION_RE = re.compile(r"ffmpeg version (\d+)")


@dataclass
class PreflightReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_visual: list[str] = field(default_factory=list)
    missing_audio: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _check_tools(report: PreflightReport) -> None:
    try:
        version = ffmpeg.ffmpeg_version()
    except ffmpeg.FFmpegError as exc:
        report.errors.append(str(exc))
        return

    match = _VERSION_RE.search(version)
    if not match or int(match.group(1)) < 8:
        report.errors.append(
            f"ffmpeg 8.x is required (-fps_mode replaced -vsync); found: {version}"
        )

    # libass is deliberately NOT checked: ASS burn-in was rejected in favour of
    # Pillow compositing, and the .ass sidecar is text written by Python.
    if not ffmpeg.has_encoder("libx264"):
        report.errors.append("ffmpeg has no libx264 encoder; it is required for all encodes")


def _check_paths(spec: RenderSpec, ws: Workspace, report: PreflightReport) -> None:
    candidates = [ws.manifest_path, ws.graph_path, ws.master_path]
    for index, shot in enumerate(spec.shots, start=1):
        candidates.append(ws.shot_clip(index, shot.id, shot.beat))
    for index, overlay in enumerate(spec.overlays, start=1):
        candidates.append(ws.overlay_png(index, overlay.id, overlay.text))
    candidates.append(ws.out_qa_json(99))

    longest = max(candidates, key=lambda p: len(str(p)))
    if len(str(longest)) > MAX_PATH_LEN:
        report.errors.append(
            f"path exceeds {MAX_PATH_LEN} characters ({len(str(longest))}): {longest}. "
            "Use a shorter slug or move the workspace closer to the drive root."
        )


def _check_fonts(spec: RenderSpec, report: PreflightReport) -> None:
    for name, style in spec.styles.items():
        if not Path(style.font_file).is_file():
            report.errors.append(
                f"style {name!r} references a font file that does not exist: {style.font_file}"
            )


def _check_visual_assets(
    spec: RenderSpec, ws: Workspace, mode: str, report: PreflightReport
) -> None:
    sources = {shot.source for shot in spec.shots}
    if spec.cover:
        sources.add(spec.cover.source)

    for source in sorted(sources):
        path = ws.asset(source)
        if not path.is_file():
            if mode == "draft":
                report.missing_visual.append(source)
            else:
                report.errors.append(f"asset not found: {path}")
            continue
        try:
            ffmpeg.probe(path)
        except ffmpeg.FFmpegError as exc:
            report.errors.append(f"asset {source} could not be probed: {exc}")

    for shot in spec.shots:
        if shot.kind != "clip" or shot.source in report.missing_visual:
            continue
        path = ws.asset(shot.source)
        if not path.is_file():
            continue
        probed = ffmpeg.probe(path)
        if shot.source_out is not None and shot.source_out > probed.duration + 1e-6:
            report.errors.append(
                f"shot {shot.id}: source_out {shot.source_out}s exceeds the real duration "
                f"of {shot.source} ({probed.duration}s)"
            )
        if shot.source_in is not None and shot.source_in < 0:
            report.errors.append(f"shot {shot.id}: source_in must not be negative")


def _check_audio_assets(
    spec: RenderSpec, ws: Workspace, mode: str, report: PreflightReport
) -> None:
    for stem in spec.audio.stems:
        path = ws.asset(stem.file)
        if path.is_file():
            continue
        if mode == "draft" and stem.duration_s is not None:
            report.missing_audio.append(stem.file)
        elif mode == "draft":
            report.errors.append(
                f"stem {stem.id!r} file {stem.file} is missing and declares no duration_s; "
                "draft mode can only synthesize silence for a stem of known length"
            )
        else:
            report.errors.append(f"stem file not found: {path}")

    optional = [spec.audio.bed.file] if spec.audio.bed else []
    optional += [item.file for item in spec.audio.sfx]
    for name in optional:
        path = ws.asset(name)
        if path.is_file():
            continue
        if mode == "draft":
            report.missing_audio.append(name)
            report.warnings.append(f"{name} is missing; it will be omitted from the draft mix")
        else:
            report.errors.append(f"audio file not found: {path}")


def run_preflight(spec: RenderSpec, ws: Workspace, mode: str) -> PreflightReport:
    report = PreflightReport()
    report.errors.extend(validate_spec(spec))

    if runtime_seconds(spec) <= 0:
        report.errors.append("spec has zero runtime")

    _check_tools(report)
    _check_paths(spec, ws, report)
    _check_fonts(spec, report)
    _check_visual_assets(spec, ws, mode, report)
    _check_audio_assets(spec, ws, mode, report)
    return report
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_preflight.py -v`
Expected: PASS — 13 passed

- [ ] **Step 5: Run the whole suite so far**

Run: `cd stitcher && python -m pytest tests/ -v`
Expected: PASS — all tests from Tasks 1–5

- [ ] **Step 6: Commit**

```bash
git add stitcher/stitcher/preflight.py stitcher/tests/test_preflight.py
git commit -m "feat(stitcher): preflight asset, tool, font, and path checks"
```

---

### Task 6: `motion.py` — Ken Burns math and expression emission

**Files:**
- Create: `stitcher/stitcher/motion.py`
- Test: `stitcher/tests/test_motion.py`

**Interfaces:**
- Consumes: `spec.Motion`, `spec.Canvas`.
- Produces: `eased(p: float, ease: str) -> float`; `progress_at(frame: int, total_frames: int, hold_frames: int, ease: str) -> float`; `zoom_at(p: float, motion: Motion) -> float`; `anchor_at(p: float, motion: Motion) -> tuple[float, float]`; `crop_rect_at(frame: int, total_frames: int, motion: Motion, canvas: Canvas, supersample: int, hold_frames: int = 0) -> tuple[int, int, int, int]` returning `(scaled_w, scaled_h, crop_x, crop_y)`; `progress_expr(total_frames: int, hold_frames: int, ease: str) -> str`; `scale_exprs(motion, canvas, supersample, total_frames, hold_frames) -> tuple[str, str]`; `crop_exprs(motion, canvas, supersample, total_frames, hold_frames) -> tuple[str, str]`; `crop_size(canvas: Canvas, supersample: int) -> tuple[int, int]`.

**The geometry model, stated once so later tasks do not re-derive it.** The source is cover-fitted to the canvas (1080×1920) — that is "the base" at zoom 1.0. The crop window is a **fixed** `1080·S × 1920·S`. Zoom comes from scaling the base by `z(p)·S`: a larger scaled source behind a fixed window means less content is visible, i.e. zoom in. Position comes from `crop_x = ax · (scaled_w − crop_w)`, which is exactly "the normalized point `ax` stays fixed" — `ax=0` pins the left edge, `ax=1` the right, `ax=0.5` centres. Drift is `ax` interpolating from `anchor_start` to `anchor_end`. Each frame is finally downscaled by `S`, so position quantization at the working resolution becomes `1/S` output pixels.

- [ ] **Step 1: Write the failing test**

```python
# stitcher/tests/test_motion.py
import pytest

from stitcher import motion as mo
from stitcher.spec import Canvas, Motion

CANVAS = Canvas(width=1080, height=1920, fps=30)


def test_eased_endpoints_are_fixed_for_every_curve():
    for ease in ("linear", "ease_in", "ease_out", "ease_in_out"):
        assert mo.eased(0.0, ease) == pytest.approx(0.0)
        assert mo.eased(1.0, ease) == pytest.approx(1.0)


def test_ease_out_starts_faster_than_linear():
    assert mo.eased(0.25, "ease_out") > 0.25


def test_ease_in_starts_slower_than_linear():
    assert mo.eased(0.25, "ease_in") < 0.25


def test_progress_is_zero_during_the_hold():
    assert mo.progress_at(0, 90, 30, "linear") == pytest.approx(0.0)
    assert mo.progress_at(29, 90, 30, "linear") == pytest.approx(0.0)
    assert mo.progress_at(30, 90, 30, "linear") == pytest.approx(0.0)


def test_progress_reaches_one_on_the_last_frame():
    assert mo.progress_at(89, 90, 30, "linear") == pytest.approx(1.0)


def test_progress_is_safe_on_a_single_frame_shot():
    assert mo.progress_at(0, 1, 0, "linear") == pytest.approx(0.0)


def test_zoom_runs_from_one_upward_for_push_in():
    motion = Motion(kind="push_in", amount_pct=15)
    assert mo.zoom_at(0.0, motion) == pytest.approx(1.0)
    assert mo.zoom_at(1.0, motion) == pytest.approx(1.15)


def test_zoom_runs_downward_for_pull_out():
    motion = Motion(kind="pull_out", amount_pct=15)
    assert mo.zoom_at(0.0, motion) == pytest.approx(1.15)
    assert mo.zoom_at(1.0, motion) == pytest.approx(1.0)


def test_zoom_is_flat_for_kind_none():
    motion = Motion(kind="none", amount_pct=15)
    assert mo.zoom_at(0.0, motion) == pytest.approx(1.0)
    assert mo.zoom_at(1.0, motion) == pytest.approx(1.0)


def test_equal_anchors_give_a_pure_centred_push():
    motion = Motion(kind="push_in", amount_pct=20,
                    anchor_start=(0.5, 0.5), anchor_end=(0.5, 0.5))
    _, _, x_start, y_start = mo.crop_rect_at(0, 60, motion, CANVAS, 4)
    scaled_w, scaled_h, x_end, y_end = mo.crop_rect_at(59, 60, motion, CANVAS, 4)
    crop_w, crop_h = mo.crop_size(CANVAS, 4)
    assert (x_start, y_start) == (0, 0)
    assert x_end == round(0.5 * (scaled_w - crop_w))
    assert y_end == round(0.5 * (scaled_h - crop_h))


def test_anchor_zero_pins_the_left_edge():
    motion = Motion(kind="push_in", amount_pct=20,
                    anchor_start=(0.0, 0.0), anchor_end=(0.0, 0.0))
    _, _, x_end, y_end = mo.crop_rect_at(59, 60, motion, CANVAS, 4)
    assert (x_end, y_end) == (0, 0)


def test_anchor_one_pins_the_right_edge():
    motion = Motion(kind="push_in", amount_pct=20,
                    anchor_start=(1.0, 1.0), anchor_end=(1.0, 1.0))
    scaled_w, scaled_h, x_end, y_end = mo.crop_rect_at(59, 60, motion, CANVAS, 4)
    crop_w, crop_h = mo.crop_size(CANVAS, 4)
    assert x_end == scaled_w - crop_w
    assert y_end == scaled_h - crop_h


def test_unequal_anchors_produce_drift():
    drifting = Motion(kind="push_in", amount_pct=15,
                      anchor_start=(0.5, 0.5), anchor_end=(0.5, 0.2))
    steady = Motion(kind="push_in", amount_pct=15,
                    anchor_start=(0.5, 0.5), anchor_end=(0.5, 0.5))
    _, _, _, drift_y = mo.crop_rect_at(59, 60, drifting, CANVAS, 4)
    _, _, _, steady_y = mo.crop_rect_at(59, 60, steady, CANVAS, 4)
    assert drift_y < steady_y


def test_crop_size_is_the_canvas_times_the_supersample():
    assert mo.crop_size(CANVAS, 4) == (4320, 7680)
    assert mo.crop_size(CANVAS, 1) == (1080, 1920)


def test_crop_never_escapes_the_scaled_source():
    motion = Motion(kind="push_in", amount_pct=30, anchor_end=(1.0, 1.0))
    crop_w, crop_h = mo.crop_size(CANVAS, 4)
    for frame in range(60):
        scaled_w, scaled_h, x, y = mo.crop_rect_at(frame, 60, motion, CANVAS, 4)
        assert 0 <= x <= scaled_w - crop_w
        assert 0 <= y <= scaled_h - crop_h


def test_expressions_reference_the_frame_variable_and_are_emitted_unquoted():
    w_expr, h_expr = mo.scale_exprs(Motion(kind="push_in", amount_pct=15), CANVAS, 4, 60, 0)
    x_expr, y_expr = mo.crop_exprs(Motion(kind="push_in", amount_pct=15), CANVAS, 4, 60, 0)
    for expr in (w_expr, h_expr, x_expr, y_expr):
        assert "n" in expr
        assert "'" not in expr


def test_a_static_motion_emits_constant_expressions():
    w_expr, h_expr = mo.scale_exprs(Motion(kind="none"), CANVAS, 4, 60, 0)
    x_expr, y_expr = mo.crop_exprs(Motion(kind="none"), CANVAS, 4, 60, 0)
    assert w_expr == "4320"
    assert h_expr == "7680"
    assert x_expr == "0"
    assert y_expr == "0"


def test_hold_frames_delay_the_move_in_both_forms():
    motion = Motion(kind="push_in", amount_pct=20, hold_s=1.0)
    _, _, x_at_hold, _ = mo.crop_rect_at(29, 90, motion, CANVAS, 4, hold_frames=30)
    _, _, x_after, _ = mo.crop_rect_at(89, 90, motion, CANVAS, 4, hold_frames=30)
    assert x_at_hold == 0
    assert x_after > 0
    assert "30" in mo.progress_expr(90, 30, "linear")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd stitcher && python -m pytest tests/test_motion.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stitcher.motion'`

- [ ] **Step 3: Implement `motion.py`**

```python
# stitcher/stitcher/motion.py
"""Ken Burns geometry, as both Python functions and FFmpeg expressions.

Both forms implement the same closed-form maths, so the Python version can be
unit-tested directly and the expression version locked by a filtergraph golden.

`crop`'s w/h are evaluated once at init and cannot animate, which is why the
zoom must live in `scale=eval=frame` and never in the crop (spec §4 stage A).
"""

from __future__ import annotations

from .spec import Canvas, Motion

ZOOMING_KINDS = {"push_in", "pull_out", "scale_up"}


def crop_size(canvas: Canvas, supersample: int) -> tuple[int, int]:
    return canvas.width * supersample, canvas.height * supersample


# --- Python form ---------------------------------------------------------


def eased(p: float, ease: str) -> float:
    p = min(1.0, max(0.0, p))
    if ease == "ease_in":
        return p * p
    if ease == "ease_out":
        return 1.0 - (1.0 - p) ** 2
    if ease == "ease_in_out":
        return 2 * p * p if p < 0.5 else 1.0 - 2 * (1.0 - p) ** 2
    return p


def progress_at(frame: int, total_frames: int, hold_frames: int, ease: str) -> float:
    span = max(1, total_frames - hold_frames - 1)
    return eased((frame - hold_frames) / span, ease)


def zoom_at(p: float, motion: Motion) -> float:
    if motion.kind not in ZOOMING_KINDS or motion.amount_pct == 0:
        return 1.0
    amount = motion.amount_pct / 100.0
    if motion.kind == "pull_out":
        return 1.0 + amount * (1.0 - p)
    return 1.0 + amount * p


def anchor_at(p: float, motion: Motion) -> tuple[float, float]:
    start_x, start_y = motion.anchor_start
    end_x, end_y = motion.anchor_end
    return (start_x + (end_x - start_x) * p, start_y + (end_y - start_y) * p)


def crop_rect_at(
    frame: int,
    total_frames: int,
    motion: Motion,
    canvas: Canvas,
    supersample: int,
    hold_frames: int = 0,
) -> tuple[int, int, int, int]:
    """Returns (scaled_w, scaled_h, crop_x, crop_y) for one frame."""
    p = progress_at(frame, total_frames, hold_frames, motion.ease)
    zoom = zoom_at(p, motion)
    crop_w, crop_h = crop_size(canvas, supersample)
    scaled_w = round(canvas.width * supersample * zoom)
    scaled_h = round(canvas.height * supersample * zoom)
    anchor_x, anchor_y = anchor_at(p, motion)
    return (
        scaled_w,
        scaled_h,
        round(anchor_x * (scaled_w - crop_w)),
        round(anchor_y * (scaled_h - crop_h)),
    )


# --- FFmpeg expression form ----------------------------------------------
# Emitted UNQUOTED. shots.py wraps each in single quotes inside the
# filtergraph, and that quoting is what protects the commas from the parser.


def _raw_progress_expr(total_frames: int, hold_frames: int) -> str:
    span = max(1, total_frames - hold_frames - 1)
    return f"max(0,min(1,(n-{hold_frames})/{span}))"


def progress_expr(total_frames: int, hold_frames: int, ease: str) -> str:
    raw = _raw_progress_expr(total_frames, hold_frames)
    if ease == "ease_in":
        return f"pow({raw},2)"
    if ease == "ease_out":
        return f"(1-pow(1-{raw},2))"
    if ease == "ease_in_out":
        return f"if(lt({raw},0.5),2*pow({raw},2),1-2*pow(1-{raw},2))"
    return raw


def _zoom_expr(motion: Motion, progress: str) -> str:
    if motion.kind not in ZOOMING_KINDS or motion.amount_pct == 0:
        return "1"
    amount = motion.amount_pct / 100.0
    if motion.kind == "pull_out":
        return f"(1+{amount}*(1-{progress}))"
    return f"(1+{amount}*{progress})"


def _anchor_expr(start: float, end: float, progress: str) -> str:
    return str(start) if start == end else f"({start}+{end - start}*{progress})"


def scale_exprs(
    motion: Motion, canvas: Canvas, supersample: int, total_frames: int, hold_frames: int
) -> tuple[str, str]:
    base_w = canvas.width * supersample
    base_h = canvas.height * supersample
    if motion.kind not in ZOOMING_KINDS or motion.amount_pct == 0:
        return str(base_w), str(base_h)
    zoom = _zoom_expr(motion, progress_expr(total_frames, hold_frames, motion.ease))
    return f"round({base_w}*{zoom})", f"round({base_h}*{zoom})"


def crop_exprs(
    motion: Motion, canvas: Canvas, supersample: int, total_frames: int, hold_frames: int
) -> tuple[str, str]:
    crop_w, crop_h = crop_size(canvas, supersample)
    static_anchor = motion.anchor_start == motion.anchor_end
    no_zoom = motion.kind not in ZOOMING_KINDS or motion.amount_pct == 0
    if no_zoom and static_anchor:
        return "0", "0"

    progress = progress_expr(total_frames, hold_frames, motion.ease)
    scale_w, scale_h = scale_exprs(motion, canvas, supersample, total_frames, hold_frames)
    anchor_x = _anchor_expr(motion.anchor_start[0], motion.anchor_end[0], progress)
    anchor_y = _anchor_expr(motion.anchor_start[1], motion.anchor_end[1], progress)
    return (
        f"round({anchor_x}*({scale_w}-{crop_w}))",
        f"round({anchor_y}*({scale_h}-{crop_h}))",
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_motion.py -v`
Expected: PASS — 17 passed

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/motion.py stitcher/tests/test_motion.py
git commit -m "feat(stitcher): Ken Burns geometry and ffmpeg expression emission"
```

---

### Task 7: `overlays.py` — Pillow rasterization to RGBA PNG

**Files:**
- Create: `stitcher/stitcher/overlays.py`
- Create: `stitcher/tests/fixtures/fonts/README.md`
- Test: `stitcher/tests/test_overlays.py`

**Interfaces:**
- Consumes: `spec.Style`, `spec.Canvas`, `spec.SafeZone`.
- Produces: `parse_accent(text: str) -> list[list[tuple[str, bool]]]` (outer list = hard-broken lines, inner = `(run_text, is_accent)`); `wrap_lines(lines, font, max_width_px) -> list[list[tuple[str, bool]]]`; `class TextOverflowError(ValueError)`; `@dataclass RenderedOverlay` with fields `png: Path`, `bbox: tuple[int, int, int, int]`; `render_overlay(text: str, style: Style, canvas: Canvas, anchor: str, offset_px: tuple[int, int], out_png: Path) -> RenderedOverlay`; `render_placeholder(label: str, canvas: Canvas, out_png: Path) -> Path`; `bbox_within(bbox, safe_zone: SafeZone) -> bool`.

**Every overlay is a full-canvas 1080×1920 RGBA PNG with position already baked in.** Stage D then always composites at `0:0` with no coordinate maths, and the ink bounding box is known in Python, making the safe-zone check a measurement rather than an estimate (spec §4 stage B).

- [ ] **Step 1: Create the font fixture note**

`stitcher/tests/fixtures/fonts/README.md`:

```markdown
# Test fonts

Golden-image tests need a font file that is byte-identical on every machine
that runs them. Place `Inter-Bold.ttf` here (SIL Open Font License) before
running the overlay tests; `tests/test_overlays.py` skips its font-dependent
tests when the file is absent so the rest of the suite still runs.

Do not substitute a system font. Rasterization differs between builds, and the
golden PNGs are compared against a numeric RMSE threshold.
```

- [ ] **Step 2: Write the failing test**

```python
# stitcher/tests/test_overlays.py
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageFont

from stitcher import overlays as ov
from stitcher.spec import Canvas, SafeZone, Style

CANVAS = Canvas(width=1080, height=1920, fps=30)
SAFE = SafeZone(x=90, y=380, width=900, height=1160)
FONT_PATH = Path(__file__).parent / "fixtures" / "fonts" / "Inter-Bold.ttf"
GOLDEN_DIR = Path(__file__).parent / "fixtures" / "goldens"
RMSE_THRESHOLD = 2.0

requires_font = pytest.mark.skipif(
    not FONT_PATH.is_file(), reason="Inter-Bold.ttf fixture not present"
)
windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="glyph rasterization is not portable"
)


def style(**overrides) -> Style:
    base = dict(
        font_file=str(FONT_PATH), size_px=72, body="#F7F3E8", accent="#F2A541",
        ground="#0E3B43", ground_opacity=0.85, padding_px=(32, 40),
        line_spacing=1.15, align="center", max_width_px=820, max_lines=4,
        stroke_px=0, stroke_color="#000000",
    )
    base.update(overrides)
    return Style(**base)


def rmse(a: Image.Image, b: Image.Image) -> float:
    diff = ImageChops.difference(a.convert("RGBA"), b.convert("RGBA"))
    histogram = diff.histogram()
    squared = sum(count * (index % 256) ** 2 for index, count in enumerate(histogram))
    return (squared / (a.width * a.height * 4)) ** 0.5


def test_parse_accent_splits_double_bracket_spans():
    assert ov.parse_accent("BEST PART WAS THE [[MUD]]") == [
        [("BEST PART WAS THE ", False), ("MUD", True)]
    ]


def test_parse_accent_handles_multi_word_and_repeated_accents():
    assert ov.parse_accent("[[IT IS NOT]] on here, not [[NOT]]") == [
        [("IT IS NOT", True), (" on here, not ", False), ("NOT", True)]
    ]


def test_parse_accent_treats_newline_as_a_hard_break():
    assert ov.parse_accent("one [[two]]\nthree") == [
        [("one ", False), ("two", True)],
        [("three", False)],
    ]


def test_parse_accent_leaves_plain_text_alone():
    assert ov.parse_accent("no accent here") == [[("no accent here", False)]]


@requires_font
def test_wrap_lines_breaks_at_the_max_width():
    font = ImageFont.truetype(str(FONT_PATH), 72)
    parsed = ov.parse_accent("one two three four five six seven eight nine ten")
    assert len(ov.wrap_lines(parsed, font, max_width_px=400)) > 1


@requires_font
def test_wrap_lines_preserves_accent_flags_across_a_break():
    font = ImageFont.truetype(str(FONT_PATH), 72)
    parsed = ov.parse_accent("aaaa bbbb cccc [[dddd]] eeee ffff")
    wrapped = ov.wrap_lines(parsed, font, max_width_px=300)
    flattened = [run for line in wrapped for run in line]
    assert any(text.strip() == "dddd" and is_accent for text, is_accent in flattened)


@requires_font
def test_render_overlay_emits_a_full_canvas_rgba_png(tmp_path: Path):
    result = ov.render_overlay("HELLO [[WORLD]]", style(), CANVAS, "center", (0, 0),
                               tmp_path / "card.png")
    with Image.open(result.png) as image:
        assert image.size == (1080, 1920)
        assert image.mode == "RGBA"


@requires_font
def test_render_overlay_writes_a_bbox_sidecar_matching_the_ink(tmp_path: Path):
    result = ov.render_overlay("HELLO [[WORLD]]", style(), CANVAS, "center", (0, 0),
                               tmp_path / "card.png")
    left, top, right, bottom = result.bbox
    assert right > left and bottom > top
    assert result.png.with_suffix(".json").is_file()
    with Image.open(result.png) as image:
        assert image.getbbox() == result.bbox


@requires_font
def test_a_centred_card_lands_inside_the_safe_zone(tmp_path: Path):
    result = ov.render_overlay("HELLO [[WORLD]]", style(), CANVAS, "center", (0, 0),
                               tmp_path / "card.png")
    assert ov.bbox_within(result.bbox, SAFE) is True


@requires_font
def test_an_offset_card_can_escape_the_safe_zone(tmp_path: Path):
    result = ov.render_overlay("HELLO [[WORLD]]", style(), CANVAS, "center", (0, 900),
                               tmp_path / "card.png")
    assert ov.bbox_within(result.bbox, SAFE) is False


@requires_font
def test_text_exceeding_max_lines_raises_rather_than_overflowing(tmp_path: Path):
    with pytest.raises(ov.TextOverflowError):
        ov.render_overlay(
            "one two three four five six seven eight nine ten eleven twelve",
            style(max_width_px=300, max_lines=2), CANVAS, "center", (0, 0),
            tmp_path / "card.png",
        )


def test_render_placeholder_is_visibly_magenta_and_full_canvas(tmp_path: Path):
    out = tmp_path / "ph.png"
    ov.render_placeholder("B-02 MISSING", CANVAS, out)
    with Image.open(out) as image:
        assert image.size == (1080, 1920)
        assert image.convert("RGB").getpixel((10, 10)) == (255, 0, 255)


@requires_font
@windows_only
def test_card_matches_the_committed_golden(tmp_path: Path):
    golden = GOLDEN_DIR / "card_hello_world.png"
    result = ov.render_overlay("HELLO [[WORLD]]", style(), CANVAS, "center", (0, 0),
                               tmp_path / "card.png")
    if not golden.is_file():
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        with Image.open(result.png) as image:
            image.save(golden)
        pytest.skip(f"golden created at {golden}; re-run to compare")
    with Image.open(golden) as expected, Image.open(result.png) as actual:
        assert rmse(expected, actual) < RMSE_THRESHOLD
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd stitcher && python -m pytest tests/test_overlays.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stitcher.overlays'`

- [ ] **Step 4: Implement `overlays.py`**

```python
# stitcher/stitcher/overlays.py
"""Stage B: rasterize overlay text to full-canvas RGBA PNGs.

Every overlay is emitted at full canvas size with position already baked in,
so stage D composites at 0:0 with no coordinate maths and the ink bounding box
is known exactly rather than estimated (spec §4 stage B).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .spec import Canvas, SafeZone, Style

_ACCENT_RE = re.compile(r"\[\[(.+?)\]\]")
_PLACEHOLDER_RGBA = (255, 0, 255, 255)

Run = tuple[str, bool]
Line = list[Run]


class TextOverflowError(ValueError):
    """Text could not be laid out within the style's max_lines."""


@dataclass(frozen=True)
class RenderedOverlay:
    png: Path
    bbox: tuple[int, int, int, int]


def parse_accent(text: str) -> list[Line]:
    """Split text into hard-broken lines of (run, is_accent) pairs."""
    lines: list[Line] = []
    for raw_line in text.split("\n"):
        runs: Line = []
        cursor = 0
        for match in _ACCENT_RE.finditer(raw_line):
            if match.start() > cursor:
                runs.append((raw_line[cursor:match.start()], False))
            runs.append((match.group(1), True))
            cursor = match.end()
        if cursor < len(raw_line):
            runs.append((raw_line[cursor:], False))
        lines.append(runs or [("", False)])
    return lines


def _measure(font: ImageFont.FreeTypeFont, text: str) -> int:
    return int(font.getlength(text))


def _tokenize(line: Line) -> list[Run]:
    """Split runs into word-level tokens, carrying the accent flag."""
    tokens: list[Run] = []
    for text, is_accent in line:
        for word in text.split(" "):
            if word:
                tokens.append((word, is_accent))
    return tokens


def wrap_lines(
    lines: list[Line], font: ImageFont.FreeTypeFont, max_width_px: int
) -> list[Line]:
    """Word-wrap each hard line to max_width_px, preserving accent flags."""
    wrapped: list[Line] = []
    for line in lines:
        current: Line = []
        current_text = ""
        for word, is_accent in _tokenize(line):
            candidate = f"{current_text} {word}".strip()
            if current and _measure(font, candidate) > max_width_px:
                wrapped.append(current)
                current, current_text = [(word, is_accent)], word
            else:
                current.append((word, is_accent))
                current_text = candidate
        wrapped.append(current or [("", False)])
    return wrapped


def _line_text(line: Line) -> str:
    return " ".join(word for word, _ in line)


def _anchor_origin(anchor: str, canvas: Canvas, block_h: int) -> int:
    if anchor == "upper_third":
        return canvas.height // 3 - block_h // 2
    if anchor == "lower_third":
        return canvas.height * 2 // 3 - block_h // 2
    return canvas.height // 2 - block_h // 2


def _hex_to_rgba(value: str, alpha: int) -> tuple[int, int, int, int]:
    text = value.lstrip("#")
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), alpha)


def render_overlay(
    text: str,
    style: Style,
    canvas: Canvas,
    anchor: str,
    offset_px: tuple[int, int],
    out_png: Path,
) -> RenderedOverlay:
    font = ImageFont.truetype(style.font_file, style.size_px)
    lines = wrap_lines(parse_accent(text), font, style.max_width_px)

    if len(lines) > style.max_lines:
        raise TextOverflowError(
            f"text wraps to {len(lines)} lines at {style.max_width_px}px but "
            f"max_lines is {style.max_lines}: {text!r}"
        )

    line_h = int(style.size_px * style.line_spacing)
    block_w = max((_measure(font, _line_text(line)) for line in lines), default=0)
    block_h = line_h * len(lines)
    pad_x, pad_y = style.padding_px

    origin_y = _anchor_origin(anchor, canvas, block_h) + offset_px[1]
    origin_x = (canvas.width - block_w) // 2 + offset_px[0]

    image = Image.new("RGBA", (canvas.width, canvas.height), (0, 0, 0, 0))

    if style.ground:
        plate = Image.new(
            "RGBA",
            (block_w + pad_x * 2, block_h + pad_y * 2),
            _hex_to_rgba(style.ground, int(round(255 * style.ground_opacity))),
        )
        image.alpha_composite(plate, (origin_x - pad_x, origin_y - pad_y))

    draw = ImageDraw.Draw(image)
    body = _hex_to_rgba(style.body, 255)
    accent = _hex_to_rgba(style.accent, 255)
    stroke = _hex_to_rgba(style.stroke_color, 255)

    for row, line in enumerate(lines):
        line_w = _measure(font, _line_text(line))
        if style.align == "left":
            cursor_x = origin_x
        elif style.align == "right":
            cursor_x = origin_x + block_w - line_w
        else:
            cursor_x = origin_x + (block_w - line_w) // 2
        cursor_y = origin_y + row * line_h

        for index, (word, is_accent) in enumerate(line):
            piece = word if index == len(line) - 1 else f"{word} "
            draw.text(
                (cursor_x, cursor_y), piece, font=font,
                fill=accent if is_accent else body,
                stroke_width=style.stroke_px, stroke_fill=stroke,
            )
            cursor_x += _measure(font, piece)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_png)

    bbox = image.getbbox() or (0, 0, 0, 0)
    out_png.with_suffix(".json").write_text(
        json.dumps({"bbox": list(bbox)}), encoding="utf-8"
    )
    return RenderedOverlay(png=out_png, bbox=bbox)


def render_placeholder(label: str, canvas: Canvas, out_png: Path) -> Path:
    """A magenta slate naming a missing asset. Draft mode only (spec §6)."""
    image = Image.new("RGBA", (canvas.width, canvas.height), _PLACEHOLDER_RGBA)
    draw = ImageDraw.Draw(image)
    draw.text(
        (canvas.width // 2, canvas.height // 2), label,
        font=ImageFont.load_default(), fill=(0, 0, 0, 255), anchor="mm",
    )
    out_png.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_png)
    return out_png


def bbox_within(bbox: tuple[int, int, int, int], safe_zone: SafeZone) -> bool:
    left, top, right, bottom = bbox
    return (
        left >= safe_zone.x
        and top >= safe_zone.y
        and right <= safe_zone.x + safe_zone.width
        and bottom <= safe_zone.y + safe_zone.height
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_overlays.py -v`
Expected: PASS — accent-parsing and placeholder tests pass unconditionally; font-dependent tests pass when `Inter-Bold.ttf` is present and otherwise skip with a clear reason. The golden test creates the golden on first run and skips, then compares on every run after.

- [ ] **Step 6: Commit**

```bash
git add stitcher/stitcher/overlays.py stitcher/tests/test_overlays.py stitcher/tests/fixtures/fonts/README.md
git commit -m "feat(stitcher): Pillow overlay rasterization with measured bboxes"
```

---

### Task 8: `shots.py` — stage A, per-shot clip rendering

**Files:**
- Create: `stitcher/stitcher/shots.py`
- Test: `stitcher/tests/test_shots.py`

**Interfaces:**
- Consumes: `spec.Shot`, `spec.Canvas`, `spec.RenderSpec`, `spec.shot_frame_bounds`, `spec.quantize`; `motion.*`; `naming.Workspace`, `naming.SUPERSAMPLE_FINAL`, `naming.SUPERSAMPLE_DRAFT`; `cache.Manifest`, `cache.payload_digest`, `cache.file_digest`; `ffmpeg.run`, `ffmpeg.ffmpeg_version`; `overlays.render_placeholder`.
- Produces: `WHIP_BLUR_PX: int = 40`; `conform_size(canvas: Canvas, motion: Motion) -> tuple[int, int]`; `still_filters(shot, canvas, supersample, total_frames, hold_frames, whip_in, whip_out) -> list[str]`; `clip_filters(shot, canvas, whip_in, whip_out) -> list[str]`; `whip_filters(direction: str, frames: int, total_frames: int, at_head: bool, canvas: Canvas) -> list[str]`; `shot_cache_key(shot, next_transition, source_digest, ffmpeg_build, supersample, mode) -> str`; `render_shot(spec, ws, index, shot, next_transition, supersample, mode, manifest, log_path, is_placeholder) -> Path`; `render_all(spec, ws, mode, manifest, log_path, missing_visual) -> list[Path]`.

**Three things this task must get right, all of them spec requirements rather than preferences:**

1. **Conform before animating, at `canvas × z_max`.** Cover-fitting the source to `1080·z_max × 1920·z_max` means that at maximum zoom the animated scale is a pure `×S` supersample with no detail thrown away, while at zoom 1.0 it is a clean downscale. Conforming to the bare canvas first would discard source detail before the zoom ever used it.
2. **Force and tag BT.709.** PNG sources are RGB, and swscale's default RGB→YUV conversion is BT.601 while players assume BT.709 for HD — a visible palette shift on exactly the colours the reference plan makes binding. Conversion carries `out_color_matrix=bt709:out_range=tv`, and the stream is tagged.
3. **A shot's cache key includes its successor's `transition_in`.** A shot renders its own tail whip when the *next* shot's transition is a whip, so changing shot N+1 must invalidate shot N.

**A note on how the whip is built, because the obvious approach does not work.** `boxblur` cannot ramp: its radii are evaluated once at filter init and their expressions cannot reference `n` or `t`, so a per-frame blur ramp is not expressible. `avgblur` is used instead — it takes separate `sizeX`/`sizeY`, which makes it genuinely *directional* rather than isotropic — and it is gated with `enable=` over the whip's frame window at a fixed radius. Across four frames a constant directional blur reads exactly like a ramped one.

**v1's whip is a directional blur only, with no slide.** A translate would drag un-rendered content in at the trailing edge, and FFmpeg has no edge-clamping pad; the alternatives (scaling the whole shot up to create margin, or splitting and re-concatenating the whip frames) either degrade the entire shot or add a filter graph out of proportion to a four-frame gesture. This is a knowing simplification of the spec's "blur-and-slide" wording, recorded in the spec's own amendment note.

- [ ] **Step 1: Write the failing test**

```python
# stitcher/tests/test_shots.py
import json
from pathlib import Path

import pytest

from stitcher import shots as sh
from stitcher.cache import Manifest
from stitcher.naming import Workspace
from stitcher.spec import Canvas, Motion, Shot, Transition, load_spec
from tests.test_spec import MINIMAL, write

CANVAS = Canvas(width=1080, height=1920, fps=30)


def shot(**overrides) -> Shot:
    base = dict(
        n=1, id="B-01", beat="Hook", **{"in": 0.0, "out": 3.0},
        source="a.png", kind="still",
        motion=Motion(kind="push_in", amount_pct=15),
        transition_in=Transition(kind="cut"),
    )
    base.update(overrides)
    return Shot.model_validate(base)


def test_conform_size_reserves_headroom_for_the_maximum_zoom():
    assert sh.conform_size(CANVAS, Motion(kind="push_in", amount_pct=15)) == (1242, 2208)
    assert sh.conform_size(CANVAS, Motion(kind="none")) == (1080, 1920)


def test_still_filters_conform_then_animate_then_downscale():
    filters = sh.still_filters(shot(), CANVAS, 4, 90, 0, None, None)
    conform_index = next(i for i, f in enumerate(filters) if "force_original_aspect_ratio" in f)
    animate_index = next(i for i, f in enumerate(filters) if "eval=frame" in f)
    colour_index = next(i for i, f in enumerate(filters) if "out_color_matrix" in f)
    format_index = next(i for i, f in enumerate(filters) if f.startswith("format="))
    assert conform_index < animate_index < colour_index
    assert format_index == colour_index + 1
    assert "1080:1920" in ";".join(filters)


def test_still_filters_carry_no_fps_filter_after_the_animated_stage():
    # -framerate on the input already sets the rate; an fps filter here would
    # rewrite frame numbering underneath the n-based expressions.
    filters = sh.still_filters(shot(), CANVAS, 4, 90, 0, None, None)
    assert not any(f.startswith("fps=") for f in filters)


def test_render_shot_sets_framerate_on_a_still_input(tmp_path: Path, monkeypatch):
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    ws.asset("a.png").write_bytes(b"png")
    captured: list[list[str]] = []
    monkeypatch.setattr(sh.ffmpeg, "run", lambda args, log_path: captured.append(args) or "")
    monkeypatch.setattr(sh.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 8.0.1")
    sh.render_shot(spec, ws, 1, spec.shots[0], None, 4, "final",
                   Manifest(ws.manifest_path), ws.log_path("t"), False)
    args = captured[0]
    assert "-framerate" in args
    assert args[args.index("-framerate") + 1] == "30"
    assert args.index("-framerate") < args.index("-i")


def test_still_filters_quote_every_animated_expression():
    filters = sh.still_filters(shot(), CANVAS, 4, 90, 0, None, None)
    animated = next(f for f in filters if "eval=frame" in f)
    assert "w='" in animated and "h='" in animated


def test_still_filters_force_and_tag_bt709():
    joined = ";".join(sh.still_filters(shot(), CANVAS, 4, 90, 0, None, None))
    assert "out_color_matrix=bt709" in joined
    assert "out_range=tv" in joined


def test_still_filters_use_a_fixed_size_crop():
    filters = sh.still_filters(shot(), CANVAS, 4, 90, 0, None, None)
    animated_crop = next(f for f in filters if f.startswith("crop=") and "x='" in f)
    assert "w=4320" in animated_crop and "h=7680" in animated_crop


def test_clip_filters_trim_to_the_source_window_and_conform_fps():
    clip = shot(kind="clip", source="a.mp4", source_in=1.0, source_out=4.0)
    joined = ";".join(sh.clip_filters(clip, CANVAS, None, None))
    assert "trim=start=1.0:end=4.0" in joined
    assert "setpts=PTS-STARTPTS" in joined
    assert "fps=30" in joined


def test_whip_at_the_head_is_gated_to_the_opening_frames():
    joined = ";".join(sh.whip_filters("left", 4, 90, at_head=True, canvas=CANVAS))
    assert "avgblur" in joined
    assert "enable='lt(n,4)'" in joined


def test_whip_at_the_tail_is_gated_to_the_closing_frames():
    joined = ";".join(sh.whip_filters("left", 4, 90, at_head=False, canvas=CANVAS))
    assert "enable='gte(n,86)'" in joined


def test_a_horizontal_whip_blurs_on_x_not_y():
    joined = ";".join(sh.whip_filters("left", 4, 90, at_head=True, canvas=CANVAS))
    assert f"sizeX={sh.WHIP_BLUR_PX}" in joined
    assert "sizeY=1" in joined


def test_a_vertical_whip_blurs_on_y_not_x():
    joined = ";".join(sh.whip_filters("up", 4, 90, at_head=True, canvas=CANVAS))
    assert f"sizeY={sh.WHIP_BLUR_PX}" in joined
    assert "sizeX=1" in joined


def test_the_whip_never_pads_with_black():
    for direction in ("left", "right", "up", "down"):
        joined = ";".join(sh.whip_filters(direction, 4, 90, True, CANVAS))
        assert "pad=" not in joined
        assert "color=black" not in joined


def test_cache_key_changes_when_the_successor_becomes_a_whip():
    cut = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8", 4, "final")
    whip = sh.shot_cache_key(
        shot(), Transition(kind="whip", direction="left"), "src", "ff8", 4, "final"
    )
    assert cut != whip


def test_cache_key_changes_with_the_ffmpeg_build():
    a = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8.0", 4, "final")
    b = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8.1", 4, "final")
    assert a != b


def test_cache_key_changes_between_run_modes():
    final = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8", 4, "final")
    draft = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8", 1, "draft")
    assert final != draft


def test_render_shot_skips_the_encode_on_a_cache_hit(tmp_path: Path, monkeypatch):
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    ws.asset("a.png").write_bytes(b"png")

    calls: list[list[str]] = []
    monkeypatch.setattr(sh.ffmpeg, "run", lambda args, log_path: calls.append(args) or "")
    monkeypatch.setattr(sh.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 8.0.1")

    manifest = Manifest(ws.manifest_path)
    target = ws.shot_clip(1, "B-01", "Hook")

    sh.render_shot(spec, ws, 1, spec.shots[0], spec.shots[1].transition_in,
                   4, "final", manifest, ws.log_path("t"), False)
    assert len(calls) == 1

    target.write_bytes(b"clip")  # the fake ffmpeg never wrote one
    sh.render_shot(spec, ws, 1, spec.shots[0], spec.shots[1].transition_in,
                   4, "final", manifest, ws.log_path("t"), False)
    assert len(calls) == 1  # second call was a cache hit


def test_render_all_returns_one_clip_per_shot_in_timeline_order(tmp_path: Path, monkeypatch):
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    for name in ("a.png", "b.png"):
        ws.asset(name).write_bytes(b"png")

    def fake_run(args, log_path):
        Path(args[-1]).write_bytes(b"clip")
        return ""

    monkeypatch.setattr(sh.ffmpeg, "run", fake_run)
    monkeypatch.setattr(sh.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 8.0.1")

    clips = sh.render_all(spec, ws, "final", Manifest(ws.manifest_path),
                          ws.log_path("t"), missing_visual=[])
    assert [clip.name for clip in clips] == ["001_B-01_hook.mkv", "002_B-02_setup.mkv"]


def test_render_all_uses_a_placeholder_for_a_missing_asset_in_draft(tmp_path: Path, monkeypatch):
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="draft")
    ws.ensure_dirs()
    ws.asset("b.png").write_bytes(b"png")

    def fake_run(args, log_path):
        Path(args[-1]).write_bytes(b"clip")
        return ""

    monkeypatch.setattr(sh.ffmpeg, "run", fake_run)
    monkeypatch.setattr(sh.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 8.0.1")

    sh.render_all(spec, ws, "draft", Manifest(ws.manifest_path),
                  ws.log_path("t"), missing_visual=["a.png"])
    placeholders = list(ws.work_dir.glob("placeholders/*.png"))
    assert len(placeholders) == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd stitcher && python -m pytest tests/test_shots.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stitcher.shots'`

- [ ] **Step 3: Implement `shots.py`**

```python
# stitcher/stitcher/shots.py
"""Stage A: render one conformed, near-lossless clip per shot.

Every clip leaves this stage with identical codec, pix_fmt, timebase, SAR and
frame rate, because the concat demuxer in stage D refuses anything else.

Whip transitions are applied HERE, not in stage D: a shot renders its own head
whip when its own transition_in is a whip, and its own tail whip when the NEXT
shot's transition_in is a whip. That is why a shot's cache key includes its
successor's transition (spec §4 stage A).
"""

from __future__ import annotations

from pathlib import Path

from . import ffmpeg, motion
from .cache import Manifest, file_digest, payload_digest
from .naming import SUPERSAMPLE_DRAFT, SUPERSAMPLE_FINAL, Workspace
from .overlays import render_placeholder
from .spec import Canvas, Motion, RenderSpec, Shot, Transition, shot_frame_bounds

WHIP_BLUR_PX = 40

INTERMEDIATE_PIX_FMT = "yuv444p"
INTERMEDIATE_CRF_FINAL = 12
INTERMEDIATE_CRF_DRAFT = 28
INTERMEDIATE_PRESET_FINAL = "veryfast"
INTERMEDIATE_PRESET_DRAFT = "ultrafast"


def conform_size(canvas: Canvas, shot_motion: Motion) -> tuple[int, int]:
    """Cover size that leaves headroom for the maximum zoom.

    Conforming to canvas * z_max means the animated scale is a pure supersample
    at full zoom rather than an upscale of already-discarded detail.
    """
    if shot_motion.kind in motion.ZOOMING_KINDS and shot_motion.amount_pct:
        z_max = 1.0 + shot_motion.amount_pct / 100.0
    else:
        z_max = 1.0
    return round(canvas.width * z_max), round(canvas.height * z_max)


def _colour_scale(canvas: Canvas) -> str:
    return (
        f"scale={canvas.width}:{canvas.height}:flags=lanczos"
        ":out_color_matrix=bt709:out_range=tv"
    )


def whip_filters(
    direction: str, frames: int, total_frames: int, at_head: bool, canvas: Canvas
) -> list[str]:
    """A directional blur gated to the whip's frames.

    `avgblur` rather than `boxblur`, for two reasons: it takes separate
    sizeX/sizeY so the blur is actually directional, and boxblur's radii are
    evaluated once at init with expressions that cannot reference n or t, so a
    per-frame ramp is not expressible there at all.

    The effect is gated with `enable=` at a fixed radius rather than ramped.
    Over four frames a constant directional blur is indistinguishable from a
    ramped one, and it needs no per-frame expression support.

    No slide: a translate would drag un-rendered content in at the trailing
    edge, and FFmpeg has no edge-clamping pad. See this task's preamble.
    """
    if at_head:
        window = f"lt(n,{frames})"
    else:
        window = f"gte(n,{max(0, total_frames - frames)})"

    horizontal = direction in ("left", "right")
    size_x = WHIP_BLUR_PX if horizontal else 1
    size_y = 1 if horizontal else WHIP_BLUR_PX
    return [f"avgblur=sizeX={size_x}:sizeY={size_y}:enable='{window}'"]


def still_filters(
    shot: Shot,
    canvas: Canvas,
    supersample: int,
    total_frames: int,
    hold_frames: int,
    whip_in: Transition | None,
    whip_out: Transition | None,
) -> list[str]:
    conform_w, conform_h = conform_size(canvas, shot.motion)
    crop_w, crop_h = motion.crop_size(canvas, supersample)
    scale_w, scale_h = motion.scale_exprs(
        shot.motion, canvas, supersample, total_frames, hold_frames
    )
    crop_x, crop_y = motion.crop_exprs(
        shot.motion, canvas, supersample, total_frames, hold_frames
    )

    # No `fps` filter here: render_shot sets -framerate on the input, so the
    # still already arrives at canvas.fps. An `fps` filter placed AFTER the
    # n-based scale/crop would rewrite frame numbering underneath them and the
    # move would silently never complete.
    filters = [
        f"scale={conform_w}:{conform_h}:force_original_aspect_ratio=increase:flags=lanczos",
        f"crop={conform_w}:{conform_h}",
        f"scale=w='{scale_w}':h='{scale_h}':eval=frame:flags=lanczos",
        f"crop=w={crop_w}:h={crop_h}:x='{crop_x}':y='{crop_y}'",
        _colour_scale(canvas),
        # Immediately after the tagged conversion, so nothing downstream can
        # leave the frame in RGB and trigger a default BT.601 conversion later.
        f"format={INTERMEDIATE_PIX_FMT}",
    ]
    filters.extend(_whip_stack(whip_in, whip_out, total_frames, canvas))
    filters.append("setsar=1")
    return filters


def clip_filters(
    shot: Shot, canvas: Canvas, whip_in: Transition | None, whip_out: Transition | None
) -> list[str]:
    # `fps` must precede the whip, whose enable window counts frames.
    filters = [
        f"trim=start={shot.source_in}:end={shot.source_out}",
        "setpts=PTS-STARTPTS",
        f"scale={canvas.width}:{canvas.height}"
        ":force_original_aspect_ratio=increase:flags=lanczos",
        f"crop={canvas.width}:{canvas.height}",
        f"fps={canvas.fps}",
        _colour_scale(canvas),
        f"format={INTERMEDIATE_PIX_FMT}",
    ]
    total_frames = round((shot.source_out - shot.source_in) * canvas.fps)
    filters.extend(_whip_stack(whip_in, whip_out, total_frames, canvas))
    filters.append("setsar=1")
    return filters


def _whip_stack(
    whip_in: Transition | None,
    whip_out: Transition | None,
    total_frames: int,
    canvas: Canvas,
) -> list[str]:
    stack: list[str] = []
    if whip_in and whip_in.kind == "whip":
        stack.extend(
            whip_filters(whip_in.direction, whip_in.frames, total_frames, True, canvas)
        )
    if whip_out and whip_out.kind == "whip":
        stack.extend(
            whip_filters(whip_out.direction, whip_out.frames, total_frames, False, canvas)
        )
    return stack


def shot_cache_key(
    shot: Shot,
    next_transition: Transition | None,
    source_digest: str,
    ffmpeg_build: str,
    supersample: int,
    mode: str,
) -> str:
    return payload_digest(
        shot.model_dump(by_alias=True),
        next_transition.model_dump() if next_transition else None,
        source_digest,
        ffmpeg_build,
        supersample,
        mode,
    )


def render_shot(
    spec: RenderSpec,
    ws: Workspace,
    index: int,
    shot: Shot,
    next_transition: Transition | None,
    supersample: int,
    mode: str,
    manifest: Manifest,
    log_path: Path,
    is_placeholder: bool,
) -> Path:
    canvas = spec.canvas
    bounds = shot_frame_bounds(spec)[index - 1]
    total_frames = bounds[1] - bounds[0]
    hold_frames = round(shot.motion.hold_s * canvas.fps)

    if is_placeholder:
        source = ws.work_dir / "placeholders" / f"{shot.id}.png"
        render_placeholder(f"{shot.id} - {shot.source} MISSING", canvas, source)
    else:
        source = ws.asset(shot.source)

    target = ws.shot_clip(index, shot.id, shot.beat)
    key = f"shots/{index:03d}"
    digest = shot_cache_key(
        shot, next_transition, file_digest(source), ffmpeg.ffmpeg_version(),
        supersample, mode,
    )
    if manifest.is_fresh(key, digest, target):
        return target

    whip_in = shot.transition_in if shot.transition_in.kind == "whip" else None
    whip_out = (
        next_transition
        if next_transition and next_transition.kind == "whip"
        else None
    )

    if shot.kind == "still" or is_placeholder:
        filters = still_filters(
            shot, canvas, supersample, total_frames, hold_frames, whip_in, whip_out
        )
        # -framerate is mandatory: -loop 1 otherwise defaults the input to
        # 25fps, so the n-based motion expressions (built against total_frames
        # at canvas.fps) would only ever reach ~83% of the move before -t cut
        # the input. Nothing downstream would catch it.
        inputs = [
            "-loop", "1", "-framerate", str(canvas.fps),
            "-t", f"{total_frames / canvas.fps:.6f}", "-i", str(source),
        ]
    else:
        filters = clip_filters(shot, canvas, whip_in, whip_out)
        inputs = ["-i", str(source)]

    crf = INTERMEDIATE_CRF_DRAFT if mode == "draft" else INTERMEDIATE_CRF_FINAL
    preset = INTERMEDIATE_PRESET_DRAFT if mode == "draft" else INTERMEDIATE_PRESET_FINAL

    target.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg.run(
        [
            "ffmpeg", "-hide_banner", "-y", *inputs,
            "-vf", ",".join(filters),
            "-frames:v", str(total_frames),
            "-fps_mode", "cfr", "-r", str(canvas.fps),
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
            "-pix_fmt", INTERMEDIATE_PIX_FMT,
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-an", str(target),
        ],
        log_path,
    )
    manifest.set(key, digest)
    return target


def render_all(
    spec: RenderSpec,
    ws: Workspace,
    mode: str,
    manifest: Manifest,
    log_path: Path,
    missing_visual: list[str],
) -> list[Path]:
    supersample = SUPERSAMPLE_DRAFT if mode == "draft" else SUPERSAMPLE_FINAL
    clips: list[Path] = []
    for index, shot in enumerate(spec.shots, start=1):
        successor = spec.shots[index].transition_in if index < len(spec.shots) else None
        clips.append(
            render_shot(
                spec, ws, index, shot, successor, supersample, mode, manifest,
                log_path, shot.source in missing_visual,
            )
        )
    manifest.save()
    return clips
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_shots.py -v`
Expected: PASS — 15 passed

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/shots.py stitcher/tests/test_shots.py
git commit -m "feat(stitcher): stage A per-shot rendering with Ken Burns and whips"
```

---

### Task 9: `envelope.py` — ducking envelope math

**Files:**
- Create: `stitcher/stitcher/envelope.py`
- Test: `stitcher/tests/test_envelope.py`

**Interfaces:**
- Consumes: `spec.Bed`, `spec.Stem`.
- Produces: `SILENCE_DB: float = -100.0`; `@dataclass(frozen=True) Breakpoint` with fields `t: float`, `db: float`; `stem_spans(stems: list[Stem], durations: dict[str, float]) -> list[tuple[float, float]]`; `build_breakpoints(bed: Bed, spans: list[tuple[float, float]], runtime: float) -> list[Breakpoint]`; `level_at(breakpoints: list[Breakpoint], t: float) -> float`; `volume_expr(breakpoints: list[Breakpoint]) -> str`.

**The whole point of this module.** Because every stem's placement and duration are known before rendering, the ducking schedule is fully determined ahead of time — so it is a computed gain envelope rather than a compressor, which is both smaller and actually verifiable (spec §4 stage C). All dB values here are **relative to the voice reference**; `audio.py` adds the single constant offset that turns them into absolute gains.

Precedence is **window > duck > baseline** (spec §3). An explicit window governs its span outright even when a stem is sounding underneath it — that is what makes "bed held out entirely for 0–3s while the child speaks" expressible.

- [ ] **Step 1: Write the failing test**

```python
# stitcher/tests/test_envelope.py
import pytest

from stitcher import envelope as env
from stitcher.spec import Bed, BedWindow, Fade, Stem


def bed(**overrides) -> Bed:
    base = dict(
        file="bed.mp3", gain_db=-8.0, duck_db=-22.0,
        duck_attack_ms=120, duck_release_ms=400, windows=[], fades=[],
    )
    base.update(overrides)
    return Bed(**base)


def test_stem_spans_uses_file_duration_when_present():
    stems = [Stem(id="a", file="a.wav", at=1.0)]
    assert env.stem_spans(stems, {"a.wav": 2.0}) == [(1.0, 3.0)]


def test_stem_spans_falls_back_to_declared_duration_s():
    stems = [Stem(id="a", file="a.wav", at=1.0, duration_s=2.5)]
    assert env.stem_spans(stems, {}) == [(1.0, 3.5)]


def test_baseline_holds_where_no_stem_sounds():
    points = env.build_breakpoints(bed(), [(5.0, 6.0)], runtime=10.0)
    assert env.level_at(points, 0.5) == pytest.approx(-8.0)
    assert env.level_at(points, 9.5) == pytest.approx(-8.0)


def test_bed_is_fully_ducked_while_a_stem_sounds():
    points = env.build_breakpoints(bed(), [(5.0, 6.0)], runtime=10.0)
    assert env.level_at(points, 5.5) == pytest.approx(-22.0)


def test_the_attack_ramp_completes_at_stem_onset():
    points = env.build_breakpoints(bed(), [(5.0, 6.0)], runtime=10.0)
    assert env.level_at(points, 5.0) == pytest.approx(-22.0)      # already down
    assert env.level_at(points, 4.88) == pytest.approx(-8.0)      # ramp not begun
    midpoint = env.level_at(points, 4.94)                          # mid-ramp
    assert -22.0 < midpoint < -8.0


def test_the_release_ramp_begins_at_stem_offset():
    points = env.build_breakpoints(bed(), [(5.0, 6.0)], runtime=10.0)
    assert env.level_at(points, 6.0) == pytest.approx(-22.0)
    assert env.level_at(points, 6.4) == pytest.approx(-8.0)
    assert -22.0 < env.level_at(points, 6.2) < -8.0


def test_overlapping_stems_take_the_most_ducked_level():
    points = env.build_breakpoints(bed(), [(1.0, 4.0), (3.0, 6.0)], runtime=10.0)
    assert env.level_at(points, 3.5) == pytest.approx(-22.0)


def test_a_window_beats_the_duck_even_while_a_stem_sounds():
    windows = [BedWindow.model_validate({"in": 0.0, "out": 3.0, "mode": "out"})]
    points = env.build_breakpoints(bed(windows=windows), [(0.0, 2.875)], runtime=10.0)
    assert env.level_at(points, 1.0) == pytest.approx(env.SILENCE_DB)


def test_a_window_level_db_overrides_both_duck_and_baseline():
    windows = [BedWindow.model_validate(
        {"in": 17.0, "out": 26.0, "mode": "ducked", "level_db": -26.0}
    )]
    points = env.build_breakpoints(bed(windows=windows), [(18.0, 20.0)], runtime=30.0)
    assert env.level_at(points, 19.0) == pytest.approx(-26.0)


def test_window_mode_full_returns_to_the_baseline():
    windows = [BedWindow.model_validate({"in": 2.0, "out": 4.0, "mode": "full"})]
    points = env.build_breakpoints(bed(windows=windows), [(2.5, 3.5)], runtime=10.0)
    assert env.level_at(points, 3.0) == pytest.approx(-8.0)


def test_a_fade_in_ramps_up_from_silence_over_its_declared_length():
    fades = [Fade(at=3.0, kind="in", ms=300)]
    points = env.build_breakpoints(bed(fades=fades), [], runtime=10.0)
    # _level floors at SILENCE_DB, so the fade's start is exactly the floor
    # rather than baseline + full attenuation.
    assert env.level_at(points, 3.0) == pytest.approx(env.SILENCE_DB)
    assert env.level_at(points, 3.3) == pytest.approx(-8.0)
    assert env.SILENCE_DB < env.level_at(points, 3.15) < -8.0


def test_breakpoints_are_sorted_and_bounded_by_the_runtime():
    windows = [BedWindow.model_validate({"in": 0.0, "out": 3.0, "mode": "out"})]
    points = env.build_breakpoints(bed(windows=windows), [(0.0, 2.9)], runtime=10.0)
    times = [point.t for point in points]
    assert times == sorted(times)
    assert times[0] >= 0.0 and times[-1] <= 10.0


def test_volume_expr_is_a_function_of_t_and_converts_db_to_linear_gain():
    points = env.build_breakpoints(bed(), [(5.0, 6.0)], runtime=10.0)
    expr = env.volume_expr(points)
    assert "t" in expr
    assert "pow(10," in expr
    assert "'" not in expr


def test_volume_expr_survives_duplicate_breakpoint_times():
    points = [env.Breakpoint(0.0, -8.0), env.Breakpoint(0.0, -8.0),
              env.Breakpoint(1.0, -22.0)]
    assert isinstance(env.volume_expr(points), str)


def test_level_at_clamps_outside_the_breakpoint_range():
    points = [env.Breakpoint(1.0, -8.0), env.Breakpoint(2.0, -22.0)]
    assert env.level_at(points, 0.0) == pytest.approx(-8.0)
    assert env.level_at(points, 9.0) == pytest.approx(-22.0)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd stitcher && python -m pytest tests/test_envelope.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stitcher.envelope'`

- [ ] **Step 3: Implement `envelope.py`**

```python
# stitcher/stitcher/envelope.py
"""The ducking envelope: a deterministic gain schedule, not a compressor.

Every dB value here is RELATIVE TO THE VOICE REFERENCE. audio.py measures the
assembled voice track once and adds the single constant offset that turns
these into absolute gains (spec §3, §4 stage C).

Precedence is window > duck > baseline. The attack ramp COMPLETES at stem
onset, so the bed is already down when the voice arrives rather than ducking
after the first syllable; the release ramp BEGINS at stem offset.
"""

from __future__ import annotations

from dataclasses import dataclass

from .spec import Bed, Stem

SILENCE_DB = -100.0
_STEP = 0.001  # 1ms, so a window edge is a fast ramp rather than a discontinuity


@dataclass(frozen=True)
class Breakpoint:
    t: float
    db: float


def stem_spans(
    stems: list[Stem], durations: dict[str, float]
) -> list[tuple[float, float]]:
    """(start, end) for each stem. Real file duration wins over duration_s."""
    spans: list[tuple[float, float]] = []
    for stem in stems:
        length = durations.get(stem.file, stem.duration_s)
        if length is None:
            raise ValueError(
                f"stem {stem.id!r} has neither a probed duration nor duration_s"
            )
        spans.append((stem.at, stem.at + length))
    return spans


def _duck_level(
    t: float, spans: list[tuple[float, float]], bed: Bed
) -> float:
    """Baseline, ducked, or mid-ramp — taking the most ducked of all spans."""
    attack = bed.duck_attack_ms / 1000.0
    release = bed.duck_release_ms / 1000.0
    level = bed.gain_db
    for start, end in spans:
        if start - attack <= t < start and attack > 0:
            progress = (t - (start - attack)) / attack
            candidate = bed.gain_db + (bed.duck_db - bed.gain_db) * progress
        elif start <= t <= end:
            candidate = bed.duck_db
        elif end < t <= end + release and release > 0:
            progress = (t - end) / release
            candidate = bed.duck_db + (bed.gain_db - bed.duck_db) * progress
        else:
            continue
        level = min(level, candidate)
    return level


def _window_level(t: float, bed: Bed) -> float | None:
    for window in bed.windows:
        if window.start <= t < window.end:
            if window.level_db is not None:
                return window.level_db
            if window.mode == "out":
                return SILENCE_DB
            if window.mode == "ducked":
                return bed.duck_db
            return bed.gain_db
    return None


def _fade_attenuation(t: float, bed: Bed) -> float:
    """Additive dB attenuation from any fade covering t. Zero elsewhere."""
    attenuation = 0.0
    for fade in bed.fades:
        length = fade.ms / 1000.0
        if length <= 0:
            continue
        if fade.kind == "in" and fade.at <= t < fade.at + length:
            progress = (t - fade.at) / length
            attenuation = min(attenuation, SILENCE_DB * (1.0 - progress))
        elif fade.kind == "out" and fade.at - length < t <= fade.at:
            progress = (t - (fade.at - length)) / length
            attenuation = min(attenuation, SILENCE_DB * progress)
    return attenuation


def _level(t: float, bed: Bed, spans: list[tuple[float, float]]) -> float:
    base = _window_level(t, bed)
    if base is None:
        base = _duck_level(t, spans, bed)
    return max(SILENCE_DB, base + _fade_attenuation(t, bed))


def build_breakpoints(
    bed: Bed, spans: list[tuple[float, float]], runtime: float
) -> list[Breakpoint]:
    """Sample the envelope at every time where its slope can change."""
    attack = bed.duck_attack_ms / 1000.0
    release = bed.duck_release_ms / 1000.0

    times: set[float] = {0.0, runtime}
    for start, end in spans:
        times.update({start - attack, start, end, end + release})
    for window in bed.windows:
        times.update({window.start - _STEP, window.start, window.end, window.end + _STEP})
    for fade in bed.fades:
        length = fade.ms / 1000.0
        if fade.kind == "in":
            times.update({fade.at, fade.at + length})
        else:
            times.update({fade.at - length, fade.at})

    ordered = sorted({round(t, 6) for t in times if 0.0 <= t <= runtime})
    return [Breakpoint(t, _level(t, bed, spans)) for t in ordered]


def level_at(breakpoints: list[Breakpoint], t: float) -> float:
    """Linear interpolation between breakpoints; clamped at both ends."""
    if not breakpoints:
        return 0.0
    if t <= breakpoints[0].t:
        return breakpoints[0].db
    if t >= breakpoints[-1].t:
        return breakpoints[-1].db
    for left, right in zip(breakpoints, breakpoints[1:]):
        if left.t <= t <= right.t:
            if right.t == left.t:
                return right.db
            progress = (t - left.t) / (right.t - left.t)
            return left.db + (right.db - left.db) * progress
    return breakpoints[-1].db


def volume_expr(breakpoints: list[Breakpoint]) -> str:
    """Nested-if FFmpeg expression over t, emitted UNQUOTED.

    audio.py wraps it in single quotes inside the filtergraph, and that
    quoting is what protects the commas from the filter parser.
    """
    unique: list[Breakpoint] = []
    for point in breakpoints:
        if not unique or point.t != unique[-1].t:
            unique.append(point)
    if not unique:
        return "1"
    if len(unique) == 1:
        return f"pow(10,{unique[0].db}/20)"

    def segment(left: Breakpoint, right: Breakpoint) -> str:
        slope = (right.db - left.db) / (right.t - left.t)
        return f"pow(10,({left.db}+{slope}*(t-{left.t}))/20)"

    expr = segment(unique[-2], unique[-1])
    for index in range(len(unique) - 2, 0, -1):
        left, right = unique[index - 1], unique[index]
        expr = f"if(lt(t,{right.t}),{segment(left, right)},{expr})"
    return expr
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_envelope.py -v`
Expected: PASS — 15 passed

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/envelope.py stitcher/tests/test_envelope.py
git commit -m "feat(stitcher): deterministic ducking envelope math"
```

---

### Task 10: `audio.py` — stage C

**Files:**
- Create: `stitcher/stitcher/audio.py`
- Test: `stitcher/tests/test_audio.py`

**Interfaces:**
- Consumes: `spec.RenderSpec`, `spec.runtime_seconds`; `envelope.*`; `ffmpeg.run`, `ffmpeg.probe`, `ffmpeg.measure_loudness`, `ffmpeg.FFmpegError`; `naming.Workspace`; `cache.Manifest`.
- Produces: `LRA_TARGET: float = 11.0`; `class LoudnormNotLinearError(RuntimeError)`; `@dataclass AudioResult` with fields `mix: Path`, `bed_conformed: Path | None`, `bed_ducked: Path | None`, `voice_reference_lufs: float`, `loudnorm: dict`; `parse_loudnorm_json(stderr: str) -> dict`; `build_audio(spec, ws, mode, log_path, missing_audio) -> AudioResult`.

**Two assertions this stage must make rather than assume (spec §4 stage C):** `loudnorm` internally resamples to 192 kHz, so an explicit `aresample=48000` must follow it or the mix silently comes out at 192 kHz; and `linear=true` silently falls back to dynamic mode when true-peak limiting is required, so pass 2's reported `normalization_type` must be checked or the determinism claim is void.

- [ ] **Step 1: Write the failing test**

```python
# stitcher/tests/test_audio.py
import json
from pathlib import Path

import pytest

from stitcher import audio as au
from stitcher.naming import Workspace
from stitcher.spec import load_spec
from tests.test_spec import MINIMAL, write

PASS1 = json.dumps({
    "input_i": "-19.3", "input_tp": "-4.1", "input_lra": "5.2",
    "input_thresh": "-29.5", "target_offset": "0.4",
})
PASS2_LINEAR = json.dumps({
    "input_i": "-19.3", "input_tp": "-4.1", "input_lra": "5.2",
    "input_thresh": "-29.5", "output_i": "-14.0", "output_tp": "-1.5",
    "target_offset": "0.0", "normalization_type": "linear",
})
PASS2_DYNAMIC = json.loads(PASS2_LINEAR)
PASS2_DYNAMIC["normalization_type"] = "dynamic"
PASS2_DYNAMIC = json.dumps(PASS2_DYNAMIC)


def test_parse_loudnorm_json_finds_the_trailing_object():
    stderr = f"[Parsed_loudnorm_0 @ 0x1] \n{PASS1}\n"
    parsed = au.parse_loudnorm_json(stderr)
    assert parsed["input_i"] == "-19.3"


def test_parse_loudnorm_json_raises_when_no_object_is_present():
    with pytest.raises(au.ffmpeg.FFmpegError):
        au.parse_loudnorm_json("no json here at all")


@pytest.fixture
def workspace(tmp_path: Path):
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    for name in ("vo.wav", "bed.mp3"):
        ws.asset(name).write_bytes(b"x")
    return ws


@pytest.fixture
def spec(tmp_path: Path):
    loaded, _ = load_spec(write(tmp_path, MINIMAL))
    return loaded


def wire(monkeypatch, pass2: str = PASS2_LINEAR) -> list[list[str]]:
    """Record ffmpeg calls; return canned loudnorm output on the analysis runs."""
    calls: list[list[str]] = []

    def fake_run(args, log_path):
        calls.append(args)
        joined = " ".join(args)
        # Every branch that names an output file must create it; pass 2 writes
        # 06_mix_final.wav as well as reporting JSON.
        if args[-1] != "-":
            Path(args[-1]).write_bytes(b"wav")
        if "print_format=json" in joined and "measured_I" in joined:
            return f"[Parsed_loudnorm_0 @ 0x1]\n{pass2}\n"
        if "print_format=json" in joined:
            return f"[Parsed_loudnorm_0 @ 0x1]\n{PASS1}\n"
        return ""

    monkeypatch.setattr(au.ffmpeg, "run", fake_run)
    monkeypatch.setattr(au.ffmpeg, "probe", lambda path: _probe(path))
    monkeypatch.setattr(
        au.ffmpeg, "measure_loudness",
        lambda path, log_path: {"input_i": -18.0, "input_tp": -3.0, "input_lra": 6.0},
    )
    return calls


def _probe(path: Path):
    from stitcher.ffmpeg import ProbeResult
    return ProbeResult(2.875, None, None, None, None, None, "pcm_s16le", 48000, None)


def test_build_audio_writes_every_named_intermediate(spec, workspace, monkeypatch):
    wire(monkeypatch)
    result = au.build_audio(spec, workspace, "final", workspace.log_path("t"), [])
    assert workspace.audio_step("03", "vo_assembled").is_file()
    assert workspace.audio_step("04a", "bed_conformed").is_file()
    assert workspace.audio_step("04b", "bed_ducked").is_file()
    assert workspace.audio_step("05", "mix_pre-loudnorm").is_file()
    assert result.mix == workspace.audio_step("06", "mix_final")


def test_loudnorm_pass1_json_is_retained_for_later_verification(spec, workspace, monkeypatch):
    wire(monkeypatch)
    au.build_audio(spec, workspace, "final", workspace.log_path("t"), [])
    retained = workspace.audio_dir / "loudnorm_pass1.json"
    assert retained.is_file()
    assert json.loads(retained.read_text())["input_i"] == "-19.3"


def test_pass_two_always_follows_loudnorm_with_an_explicit_resample(spec, workspace, monkeypatch):
    calls = wire(monkeypatch)
    au.build_audio(spec, workspace, "final", workspace.log_path("t"), [])
    pass2 = [c for c in calls if "measured_I" in " ".join(c)][-1]
    joined = " ".join(pass2)
    assert "aresample=48000" in joined
    assert joined.index("loudnorm") < joined.index("aresample=48000")


def test_a_dynamic_loudnorm_fallback_is_a_hard_failure(spec, workspace, monkeypatch):
    wire(monkeypatch, pass2=PASS2_DYNAMIC)
    with pytest.raises(au.LoudnormNotLinearError):
        au.build_audio(spec, workspace, "final", workspace.log_path("t"), [])


def test_bed_levels_are_offset_by_the_measured_voice_reference(spec, workspace, monkeypatch):
    calls = wire(monkeypatch)
    result = au.build_audio(spec, workspace, "final", workspace.log_path("t"), [])
    assert result.voice_reference_lufs == pytest.approx(-18.0)
    conform = [c for c in calls if "04a_bed_conformed.wav" in " ".join(c)][-1]
    # voice -18 LUFS, gain_db -8 -> bed target -26 LUFS, measured -18 -> -8 dB applied
    assert "volume=-8.0dB" in " ".join(conform)


def test_the_duck_envelope_is_applied_as_a_quoted_volume_expression(spec, workspace, monkeypatch):
    calls = wire(monkeypatch)
    au.build_audio(spec, workspace, "final", workspace.log_path("t"), [])
    duck = [c for c in calls if "04b_bed_ducked.wav" in " ".join(c)][-1]
    joined = " ".join(duck)
    assert "volume=volume='" in joined
    assert "eval=frame" in joined


def test_a_missing_bed_is_omitted_rather_than_faked_in_draft(spec, workspace, monkeypatch):
    wire(monkeypatch)
    ws = Workspace(root=workspace.root, slug="demo", mode="draft")
    ws.ensure_dirs()
    ws.asset("vo.wav").write_bytes(b"x")
    result = au.build_audio(spec, ws, "draft", ws.log_path("t"), ["bed.mp3"])
    assert result.bed_ducked is None
    assert result.mix.is_file()


def test_a_missing_stem_with_duration_s_becomes_silence_in_draft(tmp_path, monkeypatch):
    payload = json.loads(json.dumps(MINIMAL))
    payload["audio"]["stems"][0]["duration_s"] = 2.875
    spec_dir = tmp_path / "s"
    spec_dir.mkdir()
    spec, _ = load_spec(write(spec_dir, payload))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="draft")
    ws.ensure_dirs()
    ws.asset("bed.mp3").write_bytes(b"x")
    calls = wire(monkeypatch)
    au.build_audio(spec, ws, "draft", ws.log_path("t"), ["vo.wav"])
    assert any("anullsrc" in " ".join(c) for c in calls)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd stitcher && python -m pytest tests/test_audio.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stitcher.audio'`

- [ ] **Step 3: Implement `audio.py`**

```python
# stitcher/stitcher/audio.py
"""Stage C: stem placement, ducking, and two-pass loudness normalization.

04a_bed_conformed.wav exists solely so stage F can measure the envelope in
isolation: once voice and bed are summed they cannot be separated, so duck
depth is verified by differencing the two bed intermediates (spec §4 stage F).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import envelope, ffmpeg
from .naming import Workspace
from .spec import RenderSpec, runtime_seconds

LRA_TARGET = 11.0
_JSON_RE = re.compile(r"\{[^{}]*\}\s*$", re.DOTALL)


class LoudnormNotLinearError(RuntimeError):
    """loudnorm fell back to dynamic mode, voiding the determinism claim."""


@dataclass
class AudioResult:
    mix: Path
    bed_conformed: Path | None
    bed_ducked: Path | None
    voice_reference_lufs: float
    loudnorm: dict


def parse_loudnorm_json(stderr: str) -> dict:
    match = _JSON_RE.search(stderr.strip())
    if not match:
        raise ffmpeg.FFmpegError(f"no loudnorm JSON found in output:\n{stderr[-2000:]}")
    return json.loads(match.group(0))


def _place_stems(
    spec: RenderSpec, ws: Workspace, log_path: Path, missing_audio: list[str]
) -> tuple[Path, dict[str, float]]:
    """Gain each stem, place it at its absolute time, and sum them."""
    inputs: list[str] = []
    chains: list[str] = []
    durations: dict[str, float] = {}

    for index, stem in enumerate(spec.audio.stems):
        source = ws.asset(stem.file)
        if stem.file in missing_audio:
            length = stem.duration_s or 0.0
            inputs += ["-f", "lavfi", "-t", f"{length:.6f}",
                       "-i", "anullsrc=r=48000:cl=stereo"]
        else:
            length = ffmpeg.probe(source).duration
            inputs += ["-i", str(source)]
        durations[stem.file] = length

        delay = int(round(stem.at * 1000))
        chains.append(
            f"[{index}:a]volume={stem.gain_db}dB,"
            f"adelay={delay}|{delay},aresample=48000[s{index}]"
        )

    labels = "".join(f"[s{i}]" for i in range(len(spec.audio.stems)))
    graph = ";".join(chains) + (
        f";{labels}amix=inputs={len(spec.audio.stems)}:normalize=0:"
        "dropout_transition=0[vo]"
    )

    target = ws.audio_step("03", "vo_assembled")
    ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-y", *inputs,
         "-filter_complex", graph, "-map", "[vo]",
         "-c:a", "pcm_s16le", "-ar", "48000", str(target)],
        log_path,
    )
    return target, durations


def _build_bed(
    spec: RenderSpec,
    ws: Workspace,
    runtime: float,
    voice_lufs: float,
    durations: dict[str, float],
    log_path: Path,
) -> tuple[Path, Path]:
    bed = spec.audio.bed
    source = ws.asset(bed.file)

    # Conform: trim/loop to runtime and shift so the bed sits gain_db below
    # the voice. Levels in the spec are voice-relative, never absolute.
    measured = ffmpeg.measure_loudness(source, log_path)["input_i"]
    target_lufs = voice_lufs + bed.gain_db
    conform_gain = target_lufs - measured

    conformed = ws.audio_step("04a", "bed_conformed")
    ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-y", "-stream_loop", "-1", "-i", str(source),
         "-t", f"{runtime:.6f}",
         "-af", f"volume={conform_gain:.1f}dB,aresample=48000",
         "-c:a", "pcm_s16le", "-ar", "48000", str(conformed)],
        log_path,
    )

    spans = envelope.stem_spans(spec.audio.stems, durations)
    breakpoints = envelope.build_breakpoints(bed, spans, runtime)
    # The envelope is voice-relative; conform already applied gain_db, so
    # subtract it here to avoid applying the baseline twice.
    shifted = [
        envelope.Breakpoint(point.t, point.db - bed.gain_db) for point in breakpoints
    ]
    expression = envelope.volume_expr(shifted)

    ducked = ws.audio_step("04b", "bed_ducked")
    ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-y", "-i", str(conformed),
         "-af", f"volume=volume='{expression}':eval=frame",
         "-c:a", "pcm_s16le", "-ar", "48000", str(ducked)],
        log_path,
    )
    return conformed, ducked


def build_audio(
    spec: RenderSpec,
    ws: Workspace,
    mode: str,
    log_path: Path,
    missing_audio: list[str],
) -> AudioResult:
    runtime = runtime_seconds(spec)
    voice, durations = _place_stems(spec, ws, log_path, missing_audio)
    voice_lufs = ffmpeg.measure_loudness(voice, log_path)["input_i"]

    conformed = ducked = None
    if spec.audio.bed and spec.audio.bed.file not in missing_audio:
        conformed, ducked = _build_bed(
            spec, ws, runtime, voice_lufs, durations, log_path
        )

    # Sum voice, ducked bed, and sfx.
    inputs = ["-i", str(voice)]
    chains = ["[0:a]anull[m0]"]
    count = 1
    if ducked:
        inputs += ["-i", str(ducked)]
        chains.append(f"[{count}:a]anull[m{count}]")
        count += 1
    for item in spec.audio.sfx:
        if item.file in missing_audio:
            continue
        inputs += ["-i", str(ws.asset(item.file))]
        delay = int(round(item.at * 1000))
        chains.append(
            f"[{count}:a]volume={item.gain_db}dB,adelay={delay}|{delay}[m{count}]"
        )
        count += 1

    labels = "".join(f"[m{i}]" for i in range(count))
    graph = ";".join(chains) + (
        f";{labels}amix=inputs={count}:normalize=0:dropout_transition=0,"
        f"atrim=0:{runtime:.6f},aresample=48000[mix]"
    )

    pre = ws.audio_step("05", "mix_pre-loudnorm")
    ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-y", *inputs,
         "-filter_complex", graph, "-map", "[mix]",
         "-c:a", "pcm_s16le", "-ar", "48000", str(pre)],
        log_path,
    )

    loudness = spec.audio.loudness
    common = (
        f"I={loudness.integrated_lufs}:TP={loudness.true_peak_dbtp}:LRA={LRA_TARGET}"
    )

    pass1 = parse_loudnorm_json(
        ffmpeg.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", str(pre),
             "-af", f"loudnorm={common}:print_format=json", "-f", "null", "-"],
            log_path,
        )
    )
    (ws.audio_dir / "loudnorm_pass1.json").write_text(
        json.dumps(pass1, indent=2), encoding="utf-8"
    )

    final = ws.audio_step("06", "mix_final")
    measured = (
        f"measured_I={pass1['input_i']}:measured_TP={pass1['input_tp']}"
        f":measured_LRA={pass1['input_lra']}:measured_thresh={pass1['input_thresh']}"
        f":offset={pass1['target_offset']}:linear=true:print_format=json"
    )
    pass2 = parse_loudnorm_json(
        ffmpeg.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(pre),
             # aresample MUST follow loudnorm: it resamples internally to 192kHz.
             "-af", f"loudnorm={common}:{measured},aresample=48000",
             "-c:a", "pcm_s16le", "-ar", "48000", str(final)],
            log_path,
        )
    )

    if pass2.get("normalization_type") != "linear":
        raise LoudnormNotLinearError(
            "loudnorm fell back to "
            f"{pass2.get('normalization_type')!r} mode instead of linear, which voids "
            "the determinism guarantee. Lower the true-peak target or reduce input "
            "level so limiting is not required."
        )

    return AudioResult(final, conformed, ducked, voice_lufs, pass2)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_audio.py -v`
Expected: PASS — 10 passed

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/audio.py stitcher/tests/test_audio.py
git commit -m "feat(stitcher): stage C audio placement, ducking, two-pass loudnorm"
```

---

### Task 11: `assemble.py` — stage D

**Files:**
- Create: `stitcher/stitcher/assemble.py`
- Test: `stitcher/tests/test_assemble.py`

**Interfaces:**
- Consumes: `spec.RenderSpec`, `spec.Canvas`, `spec.Overlay`; `naming.Workspace`; `ffmpeg.run`; `overlays.RenderedOverlay`.
- Produces: `DRAFT_CRF: int = 30`; `DRAFT_PRESET: str = "ultrafast"`; `write_concat(clips: list[Path], path: Path) -> Path`; `overlay_enable(start: float, end: float) -> str`; `build_graph(overlay_count: int, enables: list[str]) -> str`; `normalize_graph(graph: str, replacements: dict[str, str]) -> str`; `assemble(spec, ws, mode, clips, overlay_pngs, mix, log_path) -> Path`.

**Two spec requirements this task exists to honour.** Overlay gating uses `gte(t,IN)*lt(t,OUT)`, never `between(t,IN,OUT)` — `between` is inclusive at *both* ends, so adjacent cards (one ending at 2.0, the next starting at 2.0) would both render for one frame. And the filtergraph is written to a file and passed with `-filter_complex_script`, which eliminates the entire class of Windows `C:\` colon-escaping bugs.

Overlay PNGs are single-frame inputs; the `overlay` filter's default `eof_action=repeat` keeps them available for the whole timeline, so their `enable` expression alone controls visibility.

- [ ] **Step 1: Write the failing test**

```python
# stitcher/tests/test_assemble.py
import json
from pathlib import Path

import pytest

from stitcher import assemble as asm
from stitcher.naming import Workspace
from stitcher.spec import load_spec
from tests.test_spec import MINIMAL, write


def test_write_concat_uses_forward_slashes_and_quotes(tmp_path: Path):
    clips = [tmp_path / "a b" / "001.mkv", tmp_path / "a b" / "002.mkv"]
    target = asm.write_concat(clips, tmp_path / "concat.txt")
    body = target.read_text(encoding="utf-8")
    assert "\\" not in body
    assert body.count("file '") == 2


def test_overlay_enable_is_half_open_not_between():
    enable = asm.overlay_enable(0.0, 2.0)
    assert "gte(t,0.0)" in enable
    assert "lt(t,2.0)" in enable
    assert "between" not in enable


def test_adjacent_overlays_never_both_enable_on_the_same_frame():
    first = asm.overlay_enable(0.0, 2.0)
    second = asm.overlay_enable(2.0, 3.0)
    # At t == 2.0 exactly: first is lt(t,2.0) -> false, second is gte(t,2.0) -> true.
    assert "lt(t,2.0)" in first and "gte(t,2.0)" in second


def test_build_graph_chains_one_overlay_per_input_and_ends_at_vout():
    graph = asm.build_graph(2, [asm.overlay_enable(0, 1), asm.overlay_enable(1, 2)])
    assert graph.count("overlay=0:0") == 2
    assert graph.strip().endswith("[vout]")
    assert "[0:v]" in graph


def test_build_graph_with_no_overlays_still_produces_vout():
    graph = asm.build_graph(0, [])
    assert graph.strip().endswith("[vout]")
    assert "overlay" not in graph


def test_normalize_graph_tokenizes_absolute_paths_for_golden_diffs():
    graph = "movie=C:/Users/BKing/renders/demo/work/final/x.png"
    normalized = asm.normalize_graph(graph, {"C:/Users/BKing/renders/demo/work/final": "<WORK>"})
    assert normalized == "movie=<WORK>/x.png"
    assert "BKing" not in normalized


@pytest.fixture
def ready(tmp_path: Path):
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    clips = []
    for index in (1, 2):
        clip = ws.shot_clip(index, f"B-0{index}", "beat")
        clip.write_bytes(b"clip")
        clips.append(clip)
    mix = ws.audio_step("06", "mix_final")
    mix.write_bytes(b"wav")
    return ws, clips, mix


def test_assemble_writes_the_graph_to_a_script_file(tmp_path, ready, monkeypatch):
    ws, clips, mix = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    png = ws.overlay_png(1, "hook-1", "hello")
    png.write_bytes(b"png")

    monkeypatch.setattr(asm.ffmpeg, "run", lambda args, log_path: "")
    asm.assemble(spec, ws, "final", clips, {"hook-1": png}, mix, ws.log_path("t"))
    assert ws.graph_path.is_file()
    assert "[vout]" in ws.graph_path.read_text(encoding="utf-8")


def test_assemble_passes_the_graph_by_script_never_inline(tmp_path, ready, monkeypatch):
    ws, clips, mix = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    png = ws.overlay_png(1, "hook-1", "hello")
    png.write_bytes(b"png")

    captured: list[list[str]] = []
    monkeypatch.setattr(asm.ffmpeg, "run", lambda args, log_path: captured.append(args) or "")
    asm.assemble(spec, ws, "final", clips, {"hook-1": png}, mix, ws.log_path("t"))
    args = captured[0]
    assert "-filter_complex_script" in args
    assert "-filter_complex" not in args


def test_assemble_targets_work_not_out(tmp_path, ready, monkeypatch):
    ws, clips, mix = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    monkeypatch.setattr(asm.ffmpeg, "run", lambda args, log_path: "")
    result = asm.assemble(spec, ws, "final", clips, {}, mix, ws.log_path("t"))
    assert result == ws.master_path
    assert result.parent == ws.work_dir


def test_final_encode_tags_bt709_and_faststart(tmp_path, ready, monkeypatch):
    ws, clips, mix = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    captured: list[list[str]] = []
    monkeypatch.setattr(asm.ffmpeg, "run", lambda args, log_path: captured.append(args) or "")
    asm.assemble(spec, ws, "final", clips, {}, mix, ws.log_path("t"))
    joined = " ".join(captured[0])
    assert "-colorspace bt709" in joined
    assert "-color_primaries bt709" in joined
    assert "-color_trc bt709" in joined
    assert "+faststart" in joined
    assert "-crf 18" in joined


def test_draft_mode_overrides_crf_and_preset_but_keeps_delivery_conformance(
    tmp_path, ready, monkeypatch
):
    ws, clips, mix = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    draft_ws = Workspace(root=ws.root, slug="demo", mode="draft")
    draft_ws.ensure_dirs()
    captured: list[list[str]] = []
    monkeypatch.setattr(asm.ffmpeg, "run", lambda args, log_path: captured.append(args) or "")
    asm.assemble(spec, draft_ws, "draft", clips, {}, mix, draft_ws.log_path("t"))
    joined = " ".join(captured[0])
    assert f"-crf {asm.DRAFT_CRF}" in joined
    assert f"-preset {asm.DRAFT_PRESET}" in joined
    assert "-pix_fmt yuv420p" in joined      # delivery conformance still exercised
    assert "-c:a aac" in joined
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd stitcher && python -m pytest tests/test_assemble.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stitcher.assemble'`

- [ ] **Step 3: Implement `assemble.py`**

```python
# stitcher/stitcher/assemble.py
"""Stage D: concat the shot clips, composite the overlays, encode the master.

The result stays in work/ until stage F passes it; only then is it promoted
into out/ with a version number (spec §2 rule 5).
"""

from __future__ import annotations

from pathlib import Path

from . import ffmpeg
from .naming import Workspace
from .spec import RenderSpec

DRAFT_CRF = 30
DRAFT_PRESET = "ultrafast"


def write_concat(clips: list[Path], path: Path) -> Path:
    """Concat demuxer list. Forward slashes and quoting, read with -safe 0."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"file '{clip.as_posix()}'" for clip in clips]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def overlay_enable(start: float, end: float) -> str:
    """Half-open gating.

    `between(t,a,b)` is inclusive at BOTH ends, so a card ending at 2.0 and the
    next starting at 2.0 would both render for one frame (spec §4 stage D).
    """
    return f"gte(t,{start})*lt(t,{end})"


def build_graph(overlay_count: int, enables: list[str]) -> str:
    """Chain one overlay filter per PNG input, ending at [vout]."""
    if overlay_count == 0:
        return "[0:v]null[vout]"

    steps = []
    current = "0:v"
    for index in range(overlay_count):
        label = "vout" if index == overlay_count - 1 else f"v{index}"
        steps.append(
            f"[{current}][{index + 1}:v]overlay=0:0:enable='{enables[index]}'[{label}]"
        )
        current = label
    return ";".join(steps)


def normalize_graph(graph: str, replacements: dict[str, str]) -> str:
    """Tokenize absolute paths so filtergraph goldens are machine-independent."""
    normalized = graph
    for literal, token in replacements.items():
        normalized = normalized.replace(literal, token)
    return normalized


def assemble(
    spec: RenderSpec,
    ws: Workspace,
    mode: str,
    clips: list[Path],
    overlay_pngs: dict[str, Path],
    mix: Path,
    log_path: Path,
) -> Path:
    concat = write_concat(clips, ws.concat_path)

    ordered = [o for o in spec.overlays if o.id in overlay_pngs]
    enables = [overlay_enable(o.start, o.end) for o in ordered]
    graph = build_graph(len(ordered), enables)
    ws.graph_path.write_text(graph, encoding="utf-8")

    inputs = ["-f", "concat", "-safe", "0", "-i", str(concat)]
    for overlay in ordered:
        inputs += ["-i", str(overlay_pngs[overlay.id])]
    audio_index = 1 + len(ordered)
    inputs += ["-i", str(mix)]

    delivery = spec.delivery
    crf = DRAFT_CRF if mode == "draft" else delivery.crf
    preset = DRAFT_PRESET if mode == "draft" else delivery.preset

    ffmpeg.run(
        [
            "ffmpeg", "-hide_banner", "-y", *inputs,
            "-filter_complex_script", str(ws.graph_path),
            "-map", "[vout]", "-map", f"{audio_index}:a",
            "-c:v", delivery.codec, "-crf", str(crf), "-preset", preset,
            "-profile:v", delivery.profile, "-pix_fmt", delivery.pix_fmt,
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-fps_mode", "cfr", "-r", str(spec.canvas.fps),
            "-c:a", delivery.audio_codec, "-b:a", delivery.audio_bitrate,
            "-ar", str(delivery.audio_rate),
            "-movflags", "+faststart",
            "-shortest", str(ws.master_path),
        ],
        log_path,
    )
    return ws.master_path
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_assemble.py -v`
Expected: PASS — 11 passed

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/assemble.py stitcher/tests/test_assemble.py
git commit -m "feat(stitcher): stage D concat, overlay compositing, final encode"
```

---

### Task 12: `derive.py` — stage E, cover and caption sidecars

**Files:**
- Create: `stitcher/stitcher/derive.py`
- Test: `stitcher/tests/test_derive.py`

**Interfaces:**
- Consumes: `spec.RenderSpec`, `spec.Caption`, `spec.Style`, `spec.Canvas`; `naming.Workspace`; `overlays` (for full-canvas PNG compositing).
- Produces: `srt_timestamp(seconds: float) -> str`; `ass_timestamp(seconds: float) -> str`; `write_srt(captions: list[Caption], path: Path) -> Path`; `write_ass(captions: list[Caption], style: Style, canvas: Canvas, path: Path) -> Path`; `render_cover(spec: RenderSpec, ws: Workspace, overlay_pngs: dict[str, Path], out_png: Path) -> Path`.

**The cover is a conform, not a frame extract.** The reference plan's `B-16` is a supplied standalone asset that never appears in the timeline, so this stage cover-fits and composites it — it never pulls a frame out of the master (spec §4 stage E).

- [ ] **Step 1: Write the failing test**

```python
# stitcher/tests/test_derive.py
import json
from pathlib import Path

import pytest
from PIL import Image

from stitcher import derive as dv
from stitcher.naming import Workspace
from stitcher.spec import Canvas, Caption, Style, load_spec
from tests.test_spec import MINIMAL, write

CANVAS = Canvas(width=1080, height=1920, fps=30)


def captions() -> list[Caption]:
    return [
        Caption.model_validate({"in": 0.0, "out": 2.9, "text": "Hello world."}),
        Caption.model_validate({"in": 3.0, "out": 5.5, "text": "Second line."}),
    ]


def a_style() -> Style:
    return Style(
        font_file="C:/fonts/Inter-Bold.ttf", size_px=72, body="#F7F3E8",
        accent="#F2A541", ground="#0E3B43", ground_opacity=0.85,
        padding_px=(32, 40), line_spacing=1.15, align="center",
        max_width_px=820, max_lines=4, stroke_px=0, stroke_color="#000000",
    )


def test_srt_timestamp_uses_comma_milliseconds():
    assert dv.srt_timestamp(0.0) == "00:00:00,000"
    assert dv.srt_timestamp(2.9) == "00:00:02,900"
    assert dv.srt_timestamp(3661.25) == "01:01:01,250"


def test_ass_timestamp_uses_centiseconds_and_a_single_hour_digit():
    assert dv.ass_timestamp(0.0) == "0:00:00.00"
    assert dv.ass_timestamp(2.9) == "0:00:02.90"


def test_write_srt_numbers_cues_from_one(tmp_path: Path):
    target = dv.write_srt(captions(), tmp_path / "c.srt")
    body = target.read_text(encoding="utf-8")
    assert body.startswith("1\n")
    assert "2\n00:00:03,000 --> 00:00:05,500" in body
    assert "Hello world." in body


def test_write_srt_on_an_empty_caption_list_writes_an_empty_file(tmp_path: Path):
    target = dv.write_srt([], tmp_path / "c.srt")
    assert target.read_text(encoding="utf-8") == ""


def test_write_ass_carries_the_style_colours_in_bgr_order(tmp_path: Path):
    target = dv.write_ass(captions(), a_style(), CANVAS, tmp_path / "c.ass")
    body = target.read_text(encoding="utf-8")
    assert "[Script Info]" in body
    assert "PlayResX: 1080" in body
    assert "&H00E8F3F7" in body        # #F7F3E8 -> &H00BBGGRR
    assert body.count("Dialogue:") == 2


def test_write_ass_escapes_newlines_as_hard_breaks(tmp_path: Path):
    multi = [Caption.model_validate({"in": 0.0, "out": 1.0, "text": "one\ntwo"})]
    body = dv.write_ass(multi, a_style(), CANVAS, tmp_path / "c.ass").read_text("utf-8")
    assert "one\\Ntwo" in body


def test_render_cover_conforms_a_supplied_asset_to_the_canvas(tmp_path: Path):
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    Image.new("RGB", (2048, 2048), (10, 20, 30)).save(ws.asset("cover.png"))

    out = ws.out_cover(1)
    dv.render_cover(spec, ws, {}, out)
    with Image.open(out) as image:
        assert image.size == (1080, 1920)


def test_render_cover_composites_only_its_named_overlays(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["cover"]["overlays"] = ["hook-1"]
    spec, _ = load_spec(write(tmp_path, payload))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    Image.new("RGB", (1080, 1920), (0, 0, 0)).save(ws.asset("cover.png"))

    stripe = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    for x in range(200):
        for y in range(200):
            stripe.putpixel((x, y), (255, 0, 0, 255))
    png = ws.overlay_png(1, "hook-1", "hello")
    stripe.save(png)

    out = ws.out_cover(1)
    dv.render_cover(spec, ws, {"hook-1": png}, out)
    with Image.open(out) as image:
        assert image.convert("RGB").getpixel((10, 10)) == (255, 0, 0)


def test_render_cover_is_a_no_op_when_no_cover_is_declared(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload.pop("cover")
    spec, _ = load_spec(write(tmp_path, payload))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    assert dv.render_cover(spec, ws, {}, ws.out_cover(1)) is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd stitcher && python -m pytest tests/test_derive.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stitcher.derive'`

- [ ] **Step 3: Implement `derive.py`**

```python
# stitcher/stitcher/derive.py
"""Stage E: the cover image and the caption sidecars.

The sidecars are generated from `captions[]` — authored spoken lines — never
from overlay card copy. Cards are designed copy, not a transcript, and an .srt
built from them would be a caption track that does not match the narration
(spec §3).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from .naming import Workspace
from .spec import Canvas, Caption, RenderSpec, Style

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, \
Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},{primary},{outline},{back},-1,0,1,{stroke},0,5,60,60,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def srt_timestamp(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def ass_timestamp(seconds: float) -> str:
    total_cs = int(round(seconds * 100))
    hours, remainder = divmod(total_cs, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, centis = divmod(remainder, 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _ass_colour(hex_value: str) -> str:
    """#RRGGBB -> &H00BBGGRR (ASS stores colours blue-first)."""
    text = hex_value.lstrip("#")
    return f"&H00{text[4:6]}{text[2:4]}{text[0:2]}".upper()


def write_srt(captions: list[Caption], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    blocks = [
        f"{index}\n{srt_timestamp(caption.start)} --> {srt_timestamp(caption.end)}\n"
        f"{caption.text}\n"
        for index, caption in enumerate(captions, start=1)
    ]
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


def write_ass(
    captions: list[Caption], style: Style, canvas: Canvas, path: Path
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = ASS_HEADER.format(
        width=canvas.width,
        height=canvas.height,
        font=Path(style.font_file).stem,
        size=style.size_px,
        primary=_ass_colour(style.body),
        outline=_ass_colour(style.stroke_color),
        back=_ass_colour(style.ground or "#000000"),
        stroke=style.stroke_px,
    )
    lines = [
        f"Dialogue: 0,{ass_timestamp(caption.start)},{ass_timestamp(caption.end)},"
        f"Default,,0,0,0,,{caption.text.replace(chr(10), chr(92) + 'N')}"
        for caption in captions
    ]
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return path


def render_cover(
    spec: RenderSpec,
    ws: Workspace,
    overlay_pngs: dict[str, Path],
    out_png: Path,
) -> Path | None:
    """Conform the supplied cover asset and composite its named overlays.

    Never a frame extract: the cover is a standalone asset that does not
    appear in the timeline.
    """
    if not spec.cover:
        return None

    canvas = spec.canvas
    with Image.open(ws.asset(spec.cover.source)) as source:
        image = source.convert("RGBA")

    scale = max(canvas.width / image.width, canvas.height / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)), Image.LANCZOS
    )
    left = (resized.width - canvas.width) // 2
    top = (resized.height - canvas.height) // 2
    cover = resized.crop((left, top, left + canvas.width, top + canvas.height))

    for name in spec.cover.overlays:
        png = overlay_pngs.get(name)
        if png is None:
            continue
        with Image.open(png) as layer:
            cover.alpha_composite(layer.convert("RGBA"))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    cover.save(out_png)
    return out_png
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_derive.py -v`
Expected: PASS — 9 passed

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/derive.py stitcher/tests/test_derive.py
git commit -m "feat(stitcher): stage E cover conform and caption sidecars"
```

---

### Task 13: `verify.py` — stage F

**Files:**
- Create: `stitcher/stitcher/verify.py`
- Modify: `stitcher/stitcher/audio.py` (persist the pass-2 record — Step 0 below)
- Test: `stitcher/tests/test_verify.py`
- Test: `stitcher/tests/test_audio.py` (one added test for Step 0)

**Interfaces:**
- Consumes: `spec.RenderSpec`, `spec.shot_frame_bounds`, `spec.runtime_seconds`; `naming.Workspace`; `ffmpeg.probe`, `ffmpeg.measure_loudness`, `ffmpeg.run`; `envelope.stem_spans`; `overlays.bbox_within`; `cache.Manifest`.
- Produces: `LOUDNESS_TOLERANCE_LU: float = 1.0`; `DUCK_TOLERANCE_DB: float = 1.5`; `MIN_DUCK_WINDOW_S: float = 0.4`; `AAC_PADDING_SLACK_S: float = 0.05`; `PASS: str = "pass"`, `FAIL: str = "fail"`, `UNAVAILABLE: str = "unavailable"`; `@dataclass Check` with fields `name: str`, `status: str`, `detail: str`; `overall_status(checks: list[Check]) -> str` returning `"pass" | "fail" | "incomplete"`; `measure_window(path: Path, start: float, duration: float, log_path: Path) -> float`; `verify(spec, ws, master, log_path) -> list[Check]`; `contact_sheet(spec, master, out_png, log_path) -> Path | None`; `write_reports(checks: list[Check], json_path: Path, md_path: Path) -> None`.

**Three measurement choices that are load-bearing, not stylistic (spec §4 stage F):**

1. **Duck depth differences the two bed intermediates over identical windows**, never ducked-inside-voice against ducked-outside-voice. The naive comparison measures the envelope *plus the music's own dynamics*, which routinely swing past the 1.5 dB tolerance and would false-fail a correct render. Ramp regions are excluded from the windows.
2. **True peak is measured on `06_mix_final.wav`, before AAC encoding.** AAC decode can overshoot its input by 0.3–1 dB, so a mix correctly normalized to −1.5 dBTP would spuriously fail if measured on the master.
3. **Timeline integrity allows one frame of slack.** AAC priming and padding shift container duration by 20–45 ms; zero tolerance would fail every correct render.

**Frame checksums are deliberately absent.** libx264 output varies by build and thread count, so a checksum produces false failures rather than evidence.

- [ ] **Step 0: Persist the loudnorm pass-2 record so `verify` can re-check it**

Task 10 asserts `normalization_type == "linear"` in-process but never writes the record to disk, so `verify` run later has nothing to read. Add the write to `build_audio` in `stitcher/stitcher/audio.py`, immediately before the `LoudnormNotLinearError` check:

```python
    (ws.work_dir / "loudnorm_pass2.json").write_text(
        json.dumps(pass2, indent=2), encoding="utf-8"
    )

    if pass2.get("normalization_type") != "linear":
```

Add this test to `stitcher/tests/test_audio.py`:

```python
def test_loudnorm_pass2_record_is_persisted_for_verify(spec, workspace, monkeypatch):
    wire(monkeypatch)
    au.build_audio(spec, workspace, "final", workspace.log_path("t"), [])
    record = workspace.work_dir / "loudnorm_pass2.json"
    assert record.is_file()
    assert json.loads(record.read_text())["normalization_type"] == "linear"
```

Run: `cd stitcher && python -m pytest tests/test_audio.py -v`
Expected: PASS — 11 passed

- [ ] **Step 1: Write the failing test**

```python
# stitcher/tests/test_verify.py
import json
from pathlib import Path

import pytest

from stitcher import verify as vf
from stitcher.ffmpeg import ProbeResult
from stitcher.naming import Workspace
from stitcher.spec import load_spec
from tests.test_spec import MINIMAL, write


def good_probe(duration: float = 6.0) -> ProbeResult:
    return ProbeResult(duration, 1080, 1920, 30.0, "yuv420p", "h264",
                       "aac", 48000, "bt709", "High")


@pytest.fixture
def ready(tmp_path: Path):
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    master = ws.master_path
    master.write_bytes(b"mp4")
    # _check_duck probes the stem files to learn their durations.
    for name in ("vo.wav", "bed.mp3"):
        ws.asset(name).write_bytes(b"x")
    ws.audio_step("06", "mix_final").write_bytes(b"wav")
    ws.audio_step("04a", "bed_conformed").write_bytes(b"wav")
    ws.audio_step("04b", "bed_ducked").write_bytes(b"wav")
    (ws.audio_dir / "loudnorm_pass1.json").write_text("{}", encoding="utf-8")
    (ws.work_dir / "loudnorm_pass2.json").write_text(
        json.dumps({"normalization_type": "linear"}), encoding="utf-8"
    )
    png = ws.overlay_png(1, "hook-1", "hello")
    png.write_bytes(b"png")
    png.with_suffix(".json").write_text(json.dumps({"bbox": [200, 500, 800, 700]}), "utf-8")
    return ws, master


def wire(monkeypatch, *, duration=6.0, integrated=-14.0, true_peak=-1.6,
         duck_delta=-14.0):
    monkeypatch.setattr(vf.ffmpeg, "probe", lambda path: good_probe(duration))

    def fake_measure(path, log_path):
        if "mix_final" in str(path):
            return {"input_i": integrated, "input_tp": true_peak, "input_lra": 6.0}
        return {"input_i": integrated, "input_tp": true_peak, "input_lra": 6.0}

    monkeypatch.setattr(vf.ffmpeg, "measure_loudness", fake_measure)

    def fake_window(path, start, dur, log_path):
        return -30.0 + duck_delta if "04b" in str(path) else -30.0

    monkeypatch.setattr(vf, "measure_window", fake_window)
    monkeypatch.setattr(vf.ffmpeg, "run", lambda args, log_path: "")


def status_of(checks, name):
    return next(c.status for c in checks if c.name == name)


def test_a_conforming_render_passes_every_check(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert vf.overall_status(checks) == "pass"


def test_a_wrong_h264_profile_fails_container_conformance(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch)
    monkeypatch.setattr(
        vf.ffmpeg, "probe",
        lambda path: ProbeResult(6.0, 1080, 1920, 30.0, "yuv420p", "h264",
                                 "aac", 48000, "bt709", "Baseline"),
    )
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "container") == vf.FAIL


def test_wrong_resolution_fails_container_conformance(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch)
    monkeypatch.setattr(
        vf.ffmpeg, "probe",
        lambda path: ProbeResult(6.0, 720, 1280, 30.0, "yuv420p", "h264", "aac", 48000, "bt709"),
    )
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "container") == vf.FAIL


def test_missing_bt709_tagging_fails_the_colour_check(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch)
    monkeypatch.setattr(
        vf.ffmpeg, "probe",
        lambda path: ProbeResult(6.0, 1080, 1920, 30.0, "yuv420p", "h264", "aac", 48000, "bt601"),
    )
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "colour_tagging") == vf.FAIL


def test_loudness_outside_one_lu_fails(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch, integrated=-11.5)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "integrated_loudness") == vf.FAIL


def test_true_peak_is_measured_pre_aac_on_the_mix(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    seen: list[str] = []

    def fake_measure(path, log_path):
        seen.append(str(path))
        return {"input_i": -14.0, "input_tp": -1.6, "input_lra": 6.0}

    wire(monkeypatch)
    monkeypatch.setattr(vf.ffmpeg, "measure_loudness", fake_measure)
    vf.verify(spec, ws, master, ws.log_path("t"))
    assert any("06_mix_final.wav" in path for path in seen)


def test_true_peak_over_the_target_fails(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch, true_peak=-0.4)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "true_peak") == vf.FAIL


def test_a_dynamic_loudnorm_record_fails_the_linearity_check(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    (ws.work_dir / "loudnorm_pass2.json").write_text(
        json.dumps({"normalization_type": "dynamic"}), encoding="utf-8"
    )
    wire(monkeypatch)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "loudnorm_linearity") == vf.FAIL


def test_duck_depth_compares_the_two_bed_intermediates(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    probed: list[str] = []

    def fake_window(path, start, dur, log_path):
        probed.append(Path(path).name)
        return -44.0 if "04b" in str(path) else -30.0

    wire(monkeypatch)
    monkeypatch.setattr(vf, "measure_window", fake_window)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert "04a_bed_conformed.wav" in probed
    assert "04b_bed_ducked.wav" in probed
    assert status_of(checks, "duck_depth") == vf.PASS


def test_duck_depth_outside_tolerance_fails(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch, duck_delta=-6.0)   # expected -14 dB, measured -6 dB
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "duck_depth") == vf.FAIL


def test_an_overlay_escaping_the_safe_zone_fails(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    png = ws.overlay_png(1, "hook-1", "hello")
    png.with_suffix(".json").write_text(json.dumps({"bbox": [0, 0, 1080, 1900]}), "utf-8")
    wire(monkeypatch)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "safe_zone") == vf.FAIL


def test_timeline_integrity_allows_one_frame_of_aac_padding(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch, duration=6.03)     # one frame at 30fps
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "timeline_integrity") == vf.PASS


def test_timeline_integrity_fails_beyond_one_frame(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch, duration=6.5)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "timeline_integrity") == vf.FAIL


def test_missing_work_artifacts_report_unavailable_never_pass(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch)
    ws.audio_step("04a", "bed_conformed").unlink()
    ws.audio_step("04b", "bed_ducked").unlink()
    (ws.work_dir / "loudnorm_pass2.json").unlink()
    for sidecar in ws.overlays_dir.glob("*.json"):
        sidecar.unlink()
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "duck_depth") == vf.UNAVAILABLE
    assert status_of(checks, "safe_zone") == vf.UNAVAILABLE
    assert status_of(checks, "loudnorm_linearity") == vf.UNAVAILABLE
    assert vf.overall_status(checks) == "incomplete"


def test_a_placeholder_in_final_mode_is_a_failure(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    (ws.work_dir / "placeholders").mkdir(exist_ok=True)
    (ws.work_dir / "placeholders" / "B-01.png").write_bytes(b"png")
    wire(monkeypatch)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "placeholders") == vf.FAIL


def test_write_reports_emits_both_json_and_markdown(tmp_path: Path):
    checks = [vf.Check("container", vf.PASS, "1080x1920 @ 30fps"),
              vf.Check("true_peak", vf.FAIL, "-0.4 dBTP exceeds -1.5")]
    json_path, md_path = tmp_path / "qa.json", tmp_path / "qa.md"
    vf.write_reports(checks, json_path, md_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert len(payload["checks"]) == 2
    assert "true_peak" in md_path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd stitcher && python -m pytest tests/test_verify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stitcher.verify'`

- [ ] **Step 3: Implement `verify.py`**

```python
# stitcher/stitcher/verify.py
"""Stage F: measure the render and report, never assert without evidence.

Checks that depend on work/ artifacts report UNAVAILABLE when those artifacts
are gone rather than silently passing, which is what distinguishes "could not
fully verify" (exit 4) from "verified and failed" (exit 3).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

from . import envelope, ffmpeg
from .naming import Workspace
from .overlays import bbox_within
from .spec import RenderSpec, runtime_seconds, shot_frame_bounds

LOUDNESS_TOLERANCE_LU = 1.0
DUCK_TOLERANCE_DB = 1.5
MIN_DUCK_WINDOW_S = 0.4
AAC_PADDING_SLACK_S = 0.05

PASS = "pass"
FAIL = "fail"
UNAVAILABLE = "unavailable"


@dataclass
class Check:
    name: str
    status: str
    detail: str


def overall_status(checks: list[Check]) -> str:
    if any(check.status == FAIL for check in checks):
        return "fail"
    if any(check.status == UNAVAILABLE for check in checks):
        return "incomplete"
    return "pass"


def measure_window(path: Path, start: float, duration: float, log_path: Path) -> float:
    """Integrated loudness over one window of a file."""
    stderr = ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{start:.6f}",
         "-t", f"{duration:.6f}", "-i", str(path),
         "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
        log_path,
    )
    matches = re.findall(r"^\s*I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", stderr, re.MULTILINE)
    if not matches:
        raise ffmpeg.FFmpegError(f"no integrated loudness in window of {path}")
    return float(matches[-1])


def _check_container(spec: RenderSpec, probed: ffmpeg.ProbeResult) -> Check:
    problems = []
    if (probed.width, probed.height) != (spec.canvas.width, spec.canvas.height):
        problems.append(f"resolution {probed.width}x{probed.height}")
    if probed.fps is None or abs(probed.fps - spec.canvas.fps) > 0.01:
        problems.append(f"fps {probed.fps}")
    if probed.pix_fmt != spec.delivery.pix_fmt:
        problems.append(f"pix_fmt {probed.pix_fmt}")
    if probed.video_codec != "h264":
        problems.append(f"video codec {probed.video_codec}")
    if probed.profile and probed.profile.lower() != spec.delivery.profile.lower():
        problems.append(f"profile {probed.profile}")
    detail = (
        f"{probed.width}x{probed.height} @ {probed.fps}fps, {probed.pix_fmt}, "
        f"{probed.video_codec}"
    )
    return Check("container", FAIL if problems else PASS,
                 "; ".join(problems) if problems else detail)


def _check_audio_stream(spec: RenderSpec, probed: ffmpeg.ProbeResult) -> Check:
    problems = []
    if probed.audio_codec != "aac":
        problems.append(f"audio codec {probed.audio_codec}")
    if probed.sample_rate != spec.delivery.audio_rate:
        problems.append(f"sample rate {probed.sample_rate}")
    return Check(
        "audio_stream", FAIL if problems else PASS,
        "; ".join(problems) if problems else f"{probed.audio_codec} @ {probed.sample_rate}Hz",
    )


def _check_duck(spec: RenderSpec, ws: Workspace, log_path: Path) -> Check:
    conformed = ws.audio_step("04a", "bed_conformed")
    ducked = ws.audio_step("04b", "bed_ducked")
    if not spec.audio.bed:
        return Check("duck_depth", PASS, "no music bed in this spec")
    if not (conformed.is_file() and ducked.is_file()):
        return Check("duck_depth", UNAVAILABLE,
                     "bed intermediates absent; run with an intact work/ directory")

    bed = spec.audio.bed
    expected = bed.duck_db - bed.gain_db
    attack = bed.duck_attack_ms / 1000.0

    durations = {stem.file: stem.duration_s for stem in spec.audio.stems
                 if stem.duration_s is not None}
    for stem in spec.audio.stems:
        source = ws.asset(stem.file)
        if source.is_file():
            durations[stem.file] = ffmpeg.probe(source).duration

    try:
        spans = envelope.stem_spans(spec.audio.stems, durations)
    except ValueError as exc:
        # A stem whose file is gone and which declares no duration_s: report
        # rather than crash the whole verification pass.
        return Check("duck_depth", UNAVAILABLE, f"stem durations unknown: {exc}")

    measured: list[float] = []
    for start, end in spans:
        window_start = start + attack
        window_length = end - window_start
        if window_length < MIN_DUCK_WINDOW_S:
            continue
        measured.append(
            measure_window(ducked, window_start, window_length, log_path)
            - measure_window(conformed, window_start, window_length, log_path)
        )

    if not measured:
        return Check("duck_depth", UNAVAILABLE,
                     "no voice span long enough to measure outside the ramps")

    worst = max(measured, key=lambda value: abs(value - expected))
    ok = abs(worst - expected) <= DUCK_TOLERANCE_DB
    return Check(
        "duck_depth", PASS if ok else FAIL,
        f"expected {expected:.1f} dB, worst measured {worst:.1f} dB "
        f"(tolerance {DUCK_TOLERANCE_DB} dB)",
    )


def _check_safe_zone(spec: RenderSpec, ws: Workspace) -> Check:
    sidecars = sorted(ws.overlays_dir.glob("*.json"))
    if not sidecars:
        if not spec.overlays:
            return Check("safe_zone", PASS, "no overlays in this spec")
        return Check("safe_zone", UNAVAILABLE,
                     "overlay bbox sidecars absent; run with an intact work/ directory")

    escaped = []
    for sidecar in sidecars:
        bbox = tuple(json.loads(sidecar.read_text(encoding="utf-8"))["bbox"])
        if not bbox_within(bbox, spec.safe_zone):
            escaped.append(f"{sidecar.stem} {bbox}")
    return Check("safe_zone", FAIL if escaped else PASS,
                 "; ".join(escaped) if escaped else f"{len(sidecars)} overlays inside")


def _check_linearity(ws: Workspace) -> Check:
    record = ws.work_dir / "loudnorm_pass2.json"
    if not record.is_file():
        return Check("loudnorm_linearity", UNAVAILABLE,
                     "loudnorm pass 2 record absent; run with an intact work/ directory")
    kind = json.loads(record.read_text(encoding="utf-8")).get("normalization_type")
    return Check("loudnorm_linearity", PASS if kind == "linear" else FAIL,
                 f"normalization_type = {kind!r}")


def _check_placeholders(ws: Workspace) -> Check:
    found = sorted((ws.work_dir / "placeholders").glob("*.png")) \
        if (ws.work_dir / "placeholders").is_dir() else []
    if not found:
        return Check("placeholders", PASS, "none")
    names = ", ".join(path.stem for path in found)
    status = FAIL if ws.mode == "final" else PASS
    return Check("placeholders", status, f"{len(found)} placeholder(s): {names}")


def contact_sheet(
    spec: RenderSpec, master: Path, out_png: Path, log_path: Path
) -> Path | None:
    """One frame from each shot's midpoint, tiled. Informational only."""
    frames: list[Image.Image] = []
    temp_dir = out_png.parent / "_contact"
    temp_dir.mkdir(parents=True, exist_ok=True)
    for index, shot in enumerate(spec.shots, start=1):
        midpoint = (shot.start + shot.end) / 2
        frame = temp_dir / f"{index:03d}.png"
        ffmpeg.run(
            ["ffmpeg", "-hide_banner", "-y", "-ss", f"{midpoint:.3f}",
             "-i", str(master), "-frames:v", "1", "-vf", "scale=216:384", str(frame)],
            log_path,
        )
        if frame.is_file():
            frames.append(Image.open(frame).convert("RGB"))
    if not frames:
        return None

    columns = min(5, len(frames))
    rows = (len(frames) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 216, rows * 384), (0, 0, 0))
    for position, frame in enumerate(frames):
        sheet.paste(frame, ((position % columns) * 216, (position // columns) * 384))
    sheet.save(out_png)
    return out_png


def verify(
    spec: RenderSpec, ws: Workspace, master: Path, log_path: Path
) -> list[Check]:
    probed = ffmpeg.probe(master)
    checks = [_check_container(spec, probed), _check_audio_stream(spec, probed)]

    colour_ok = probed.colorspace == "bt709"
    checks.append(Check("colour_tagging", PASS if colour_ok else FAIL,
                        f"colorspace = {probed.colorspace!r}"))

    integrated = ffmpeg.measure_loudness(master, log_path)["input_i"]
    target = spec.audio.loudness.integrated_lufs
    loud_ok = abs(integrated - target) <= LOUDNESS_TOLERANCE_LU
    checks.append(Check("integrated_loudness", PASS if loud_ok else FAIL,
                        f"{integrated:.1f} LUFS against a target of {target} LUFS"))

    mix = ws.audio_step("06", "mix_final")
    if mix.is_file():
        # Measured pre-AAC: the codec can overshoot its input by 0.3-1 dB.
        peak = ffmpeg.measure_loudness(mix, log_path)["input_tp"]
        peak_ok = peak <= spec.audio.loudness.true_peak_dbtp + 1e-6
        checks.append(Check("true_peak", PASS if peak_ok else FAIL,
                            f"{peak:.1f} dBTP against a ceiling of "
                            f"{spec.audio.loudness.true_peak_dbtp} dBTP"))
    else:
        checks.append(Check("true_peak", UNAVAILABLE,
                            "06_mix_final.wav absent; true peak cannot be measured pre-AAC"))

    checks.append(_check_linearity(ws))
    checks.append(_check_duck(spec, ws, log_path))
    checks.append(_check_safe_zone(spec, ws))

    total_frames = shot_frame_bounds(spec)[-1][1]
    expected_seconds = total_frames / spec.canvas.fps
    # One frame is 33ms at 30fps, but AAC priming/padding can shift container
    # duration by up to ~45ms — so the floor is whichever is larger.
    slack = max(1.0 / spec.canvas.fps, AAC_PADDING_SLACK_S)
    timeline_ok = abs(probed.duration - expected_seconds) <= slack
    checks.append(Check(
        "timeline_integrity", PASS if timeline_ok else FAIL,
        f"container {probed.duration:.3f}s against {expected_seconds:.3f}s "
        f"({total_frames} frames), slack {slack * 1000:.0f}ms",
    ))

    checks.append(_check_placeholders(ws))
    return checks


def write_reports(checks: list[Check], json_path: Path, md_path: Path) -> None:
    status = overall_status(checks)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps({"status": status, "checks": [asdict(c) for c in checks]}, indent=2),
        encoding="utf-8",
    )

    symbols = {PASS: "PASS", FAIL: "FAIL", UNAVAILABLE: "N/A "}
    lines = [f"# QA report — {status.upper()}", "", "| Check | Result | Detail |",
             "|---|---|---|"]
    lines += [
        f"| `{check.name}` | {symbols[check.status]} | {check.detail} |"
        for check in checks
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_verify.py -v`
Expected: PASS — 15 passed

- [ ] **Step 5: Commit**

```bash
git add stitcher/stitcher/verify.py stitcher/tests/test_verify.py
git commit -m "feat(stitcher): stage F measurement and QA reporting"
```

---

### Task 14: `cli.py` — orchestration, promotion, exit codes

**Files:**
- Create: `stitcher/stitcher/cli.py`
- Modify: `stitcher/stitcher/naming.py` (add `out_stem` / `deliverable`, re-express the `out_*` methods through them — Step 0)
- Test: `stitcher/tests/test_cli.py`
- Test: `stitcher/tests/test_naming.py` (two added tests for Step 0)

**Interfaces:**
- Consumes: every module above.
- Produces: `EXIT_OK: int = 0`, `EXIT_PREFLIGHT: int = 1`, `EXIT_RENDER: int = 2`, `EXIT_QA: int = 3`, `EXIT_INCOMPLETE: int = 4`; `run_digest(spec, ws, mode, ffmpeg_build) -> str`; `render_overlays(spec, ws, manifest) -> dict[str, Path]`; `cmd_validate(spec_path: Path) -> int`; `cmd_render(slug: str, root: Path, mode: str, force: bool) -> int`; `cmd_verify(slug: str, root: Path, version: int | None) -> int`; `cmd_clean(slug: str, root: Path, mode: str | None) -> int`; `main(argv: list[str] | None = None) -> int`.

**Promotion rule (spec §2 rule 5).** Stage D always writes `work/<mode>/master.mp4`. Only a clean stage-F pass promotes it into `out/` with a freshly allocated version. A QA-failed render leaves the file in `work/` and writes its report to `logs/`, so failures never consume a version number and `out/` contains only outputs that actually met spec.

**Total-cache-hit rule (spec §5).** If every stage hits cache and an existing `out/` version was produced from an identical run digest, `render` reports "no changes" and exits 0 without re-encoding or allocating a version. `--force` overrides.

- [ ] **Step 0: Add `out_stem` / `deliverable` to `naming.py` and re-express the `out_*` methods**

Draft runs need the same seven deliverable paths as final runs but without a version number. Rather than adding seven parallel `draft_*` methods, collapse both families onto one stem. Replace the deliverables block in `stitcher/stitcher/naming.py` with:

```python
    # --- deliverables ----------------------------------------------------

    def out_stem(self, version: int | None) -> str:
        """Filename stem for one run. None means draft, which is unversioned."""
        return f"{self.slug}_draft" if version is None else f"{self.slug}_v{version:02d}"

    def deliverable(self, suffix: str, version: int | None) -> Path:
        return self.out_dir / f"{self.out_stem(version)}{suffix}"

    def out_master(self, version: int | None) -> Path:
        return self.deliverable("_1080x1920.mp4", version)

    def out_cover(self, version: int | None) -> Path:
        return self.deliverable("_cover_1080x1920.png", version)

    def out_srt(self, version: int | None) -> Path:
        return self.deliverable(".srt", version)

    def out_ass(self, version: int | None) -> Path:
        return self.deliverable(".ass", version)

    def out_qa_json(self, version: int | None) -> Path:
        return self.deliverable("_qa.json", version)

    def out_qa_md(self, version: int | None) -> Path:
        return self.deliverable("_qa.md", version)

    def out_contact_sheet(self, version: int | None) -> Path:
        return self.deliverable("_contact-sheet.png", version)

    def draft_master(self) -> Path:
        """Drafts are disposable and never consume a version number."""
        return self.out_master(None)
```

Add to `stitcher/tests/test_naming.py`:

```python
def test_out_stem_distinguishes_versioned_from_draft(ws: Workspace):
    assert ws.out_stem(3) == "nobody-asked-the-kid_v03"
    assert ws.out_stem(None) == "nobody-asked-the-kid_draft"


def test_every_deliverable_shares_one_stem(ws: Workspace):
    for version in (3, None):
        stem = ws.out_stem(version)
        for path in (ws.out_master(version), ws.out_cover(version), ws.out_srt(version),
                     ws.out_ass(version), ws.out_qa_json(version), ws.out_qa_md(version),
                     ws.out_contact_sheet(version)):
            assert path.name.startswith(stem)
```

Run: `cd stitcher && python -m pytest tests/test_naming.py -v`
Expected: PASS — 15 passed (the existing 13 still pass unchanged)

- [ ] **Step 1: Write the failing test**

```python
# stitcher/tests/test_cli.py
import json
from pathlib import Path

import pytest

from stitcher import cli
from stitcher.naming import Workspace
from stitcher.verify import Check, FAIL, PASS
from tests.test_spec import MINIMAL, write


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    ws = Workspace(root=tmp_path / "renders", slug="demo", mode="final")
    ws.ensure_dirs()
    ws.spec_path.write_text(json.dumps(MINIMAL), encoding="utf-8")
    for name in ("a.png", "b.png", "cover.png", "vo.wav", "bed.mp3"):
        ws.asset(name).write_bytes(b"x")
    return ws


def stub_pipeline(monkeypatch, checks: list[Check]):
    """Replace every stage with a fast fake, leaving orchestration real."""
    monkeypatch.setattr(cli.preflight, "run_preflight",
                        lambda spec, ws, mode: cli.preflight.PreflightReport())
    monkeypatch.setattr(cli.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 8.0.1")
    monkeypatch.setattr(cli.shots, "render_all",
                        lambda *a, **k: [a[1].shots_dir / "001_x_y.mkv"])
    monkeypatch.setattr(cli, "render_overlays", lambda spec, ws, manifest: {})

    def fake_audio(spec, ws, mode, log_path, missing):
        target = ws.audio_step("06", "mix_final")
        target.write_bytes(b"wav")
        return cli.audio.AudioResult(target, None, None, -18.0, {})

    monkeypatch.setattr(cli.audio, "build_audio", fake_audio)

    def fake_assemble(spec, ws, mode, clips, pngs, mix, log_path):
        ws.master_path.write_bytes(b"mp4")
        return ws.master_path

    monkeypatch.setattr(cli.assemble, "assemble", fake_assemble)
    monkeypatch.setattr(cli.verify, "verify", lambda *a, **k: checks)
    monkeypatch.setattr(cli.verify, "contact_sheet", lambda *a, **k: None)
    monkeypatch.setattr(cli.derive, "render_cover", lambda *a, **k: None)


def test_validate_exits_zero_on_a_good_spec(workspace):
    assert cli.cmd_validate(workspace.spec_path) == cli.EXIT_OK


def test_validate_exits_one_on_a_bad_spec(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][1]["in"] = 3.5
    assert cli.cmd_validate(write(tmp_path, payload)) == cli.EXIT_PREFLIGHT


def test_preflight_failure_aborts_before_any_render(workspace, monkeypatch):
    report = cli.preflight.PreflightReport(errors=["asset not found: a.png"])
    monkeypatch.setattr(cli.preflight, "run_preflight", lambda spec, ws, mode: report)
    called: list[str] = []
    monkeypatch.setattr(cli.shots, "render_all",
                        lambda *a, **k: called.append("rendered") or [])
    code = cli.cmd_render("demo", workspace.root, "final", force=False)
    assert code == cli.EXIT_PREFLIGHT
    assert called == []


def test_a_passing_run_promotes_the_master_into_out(workspace, monkeypatch):
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])
    code = cli.cmd_render("demo", workspace.root, "final", force=False)
    assert code == cli.EXIT_OK
    assert workspace.out_master(1).is_file()
    assert not workspace.master_path.exists()


def test_a_failing_qa_leaves_the_master_in_work_and_burns_no_version(
    workspace, monkeypatch
):
    stub_pipeline(monkeypatch, [Check("true_peak", FAIL, "-0.4 exceeds -1.5")])
    code = cli.cmd_render("demo", workspace.root, "final", force=False)
    assert code == cli.EXIT_QA
    assert workspace.master_path.is_file()
    assert not workspace.out_master(1).exists()
    assert workspace.next_version() == 1
    assert list(workspace.logs_dir.glob("*_qa.md"))


def test_versions_increment_across_successful_runs(workspace, monkeypatch):
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])
    cli.cmd_render("demo", workspace.root, "final", force=False)
    cli.cmd_render("demo", workspace.root, "final", force=True)
    assert workspace.out_master(1).is_file()
    assert workspace.out_master(2).is_file()


def test_a_total_cache_hit_is_a_no_op_that_mints_no_version(workspace, monkeypatch):
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])
    cli.cmd_render("demo", workspace.root, "final", force=False)
    code = cli.cmd_render("demo", workspace.root, "final", force=False)
    assert code == cli.EXIT_OK
    assert not workspace.out_master(2).exists()


def test_force_mints_a_new_version_despite_a_total_cache_hit(workspace, monkeypatch):
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])
    cli.cmd_render("demo", workspace.root, "final", force=False)
    cli.cmd_render("demo", workspace.root, "final", force=True)
    assert workspace.out_master(2).is_file()


def test_draft_writes_an_unversioned_master(workspace, monkeypatch):
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])
    code = cli.cmd_render("demo", workspace.root, "draft", force=False)
    assert code == cli.EXIT_OK
    assert workspace.out_master(None).is_file()
    assert workspace.next_version() == 1


def test_run_digest_changes_with_the_ffmpeg_build(workspace):
    from stitcher.spec import load_spec
    spec, _ = load_spec(workspace.spec_path)
    a = cli.run_digest(spec, workspace, "final", "ffmpeg 8.0")
    b = cli.run_digest(spec, workspace, "final", "ffmpeg 8.1")
    assert a != b


def test_run_digest_changes_when_a_font_file_changes(workspace, tmp_path):
    from stitcher.spec import load_spec
    font = tmp_path / "f.ttf"
    font.write_bytes(b"one")
    payload = json.loads(json.dumps(MINIMAL))
    payload["styles"]["card"]["font_file"] = str(font)
    workspace.spec_path.write_text(json.dumps(payload), encoding="utf-8")
    spec, _ = load_spec(workspace.spec_path)

    before = cli.run_digest(spec, workspace, "final", "ffmpeg 8.0")
    font.write_bytes(b"two")
    assert cli.run_digest(spec, workspace, "final", "ffmpeg 8.0") != before


def test_run_digest_changes_between_modes(workspace):
    from stitcher.spec import load_spec
    spec, _ = load_spec(workspace.spec_path)
    assert (cli.run_digest(spec, workspace, "final", "ff")
            != cli.run_digest(spec, workspace, "draft", "ff"))


def test_verify_without_work_returns_the_incomplete_code(workspace, monkeypatch):
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])
    cli.cmd_render("demo", workspace.root, "final", force=False)
    monkeypatch.setattr(
        cli.verify, "verify",
        lambda *a, **k: [Check("duck_depth", cli.verify.UNAVAILABLE, "work/ cleaned")],
    )
    assert cli.cmd_verify("demo", workspace.root, 1) == cli.EXIT_INCOMPLETE


def test_clean_removes_work_but_keeps_out_and_logs(workspace, monkeypatch):
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])
    cli.cmd_render("demo", workspace.root, "final", force=False)
    assert cli.cmd_clean("demo", workspace.root, "final") == cli.EXIT_OK
    assert not workspace.work_dir.exists()
    assert workspace.out_master(1).is_file()
    assert workspace.logs_dir.exists()


def test_main_dispatches_and_returns_the_command_code(workspace, monkeypatch):
    monkeypatch.setattr(cli, "cmd_validate", lambda path: 7)
    assert cli.main(["validate", str(workspace.spec_path)]) == 7
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd stitcher && python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stitcher.cli'`

- [ ] **Step 3: Implement `cli.py`**

```python
# stitcher/stitcher/cli.py
"""Command dispatch and stage orchestration.

Stage D writes work/<mode>/master.mp4; only a clean stage-F pass promotes it
into out/ with a freshly allocated version, so a QA failure never consumes a
version number (spec §2 rule 5).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import assemble, audio, derive, ffmpeg, preflight, shots, verify
from .cache import Manifest, file_digest, payload_digest
from .naming import Workspace
from .overlays import TextOverflowError, render_overlay
from .spec import RenderSpec, load_spec, validate_spec

EXIT_OK = 0
EXIT_PREFLIGHT = 1
EXIT_RENDER = 2
EXIT_QA = 3
EXIT_INCOMPLETE = 4

DEFAULT_ROOT = Path("renders")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def run_digest(spec: RenderSpec, ws: Workspace, mode: str, ffmpeg_build: str) -> str:
    """Everything that determines the whole run (spec §5)."""
    assets = sorted(
        {shot.source for shot in spec.shots}
        | {stem.file for stem in spec.audio.stems}
        | {item.file for item in spec.audio.sfx}
        | ({spec.audio.bed.file} if spec.audio.bed else set())
        | ({spec.cover.source} if spec.cover else set())
    )
    return payload_digest(
        spec.model_dump(by_alias=True),
        [file_digest(ws.asset(name)) for name in assets],
        [file_digest(Path(style.font_file)) for _, style in sorted(spec.styles.items())],
        ffmpeg_build,
        mode,
    )


def render_overlays(
    spec: RenderSpec, ws: Workspace, manifest: Manifest
) -> dict[str, Path]:
    """Stage B: one full-canvas RGBA PNG per overlay, content-hash cached."""
    rendered: dict[str, Path] = {}
    for index, overlay in enumerate(spec.overlays, start=1):
        style = spec.styles[overlay.style]
        target = ws.overlay_png(index, overlay.id, overlay.text)
        key = f"overlays/{index:03d}"
        digest = payload_digest(
            overlay.model_dump(by_alias=True),
            style.model_dump(),
            file_digest(Path(style.font_file)),
            spec.canvas.model_dump(),
        )
        if not manifest.is_fresh(key, digest, target):
            render_overlay(
                overlay.text, style, spec.canvas, overlay.anchor,
                overlay.offset_px, target,
            )
            manifest.set(key, digest)
        rendered[overlay.id] = target
    manifest.save()
    return rendered


def cmd_validate(spec_path: Path) -> int:
    try:
        spec, warnings = load_spec(spec_path)
    except ValueError as exc:
        print(f"spec is unusable:\n{exc}", file=sys.stderr)
        return EXIT_PREFLIGHT

    for warning in warnings:
        print(f"warning: {warning}")

    errors = validate_spec(spec)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return EXIT_PREFLIGHT
    print(f"{spec_path} is valid ({len(spec.shots)} shots, {len(spec.overlays)} overlays)")
    return EXIT_OK


def cmd_render(slug: str, root: Path, mode: str, force: bool) -> int:
    ws = Workspace(root=root, slug=slug, mode=mode)
    ws.ensure_dirs()
    log_path = ws.log_path(_timestamp())

    try:
        spec, warnings = load_spec(ws.spec_path)
    except ValueError as exc:
        print(f"spec is unusable:\n{exc}", file=sys.stderr)
        return EXIT_PREFLIGHT
    for warning in warnings:
        print(f"warning: {warning}")

    report = preflight.run_preflight(spec, ws, mode)
    for warning in report.warnings:
        print(f"warning: {warning}")
    if not report.ok:
        for error in report.errors:
            print(f"error: {error}", file=sys.stderr)
        return EXIT_PREFLIGHT

    manifest = Manifest.load(ws.manifest_path)
    digest = run_digest(spec, ws, mode, ffmpeg.ffmpeg_version())
    recorded_version = manifest.get("run/version")

    if not force and manifest.get("run") == digest and recorded_version:
        existing = ws.out_master(None if mode == "draft" else int(recorded_version))
        if existing.is_file():
            print(f"no changes; {existing.name} is current (use --force to re-render)")
            return EXIT_OK

    try:
        clips = shots.render_all(spec, ws, mode, manifest, log_path, report.missing_visual)
        overlay_pngs = render_overlays(spec, ws, manifest)
        mix = audio.build_audio(spec, ws, mode, log_path, report.missing_audio)
        master = assemble.assemble(
            spec, ws, mode, clips, overlay_pngs, mix.mix, log_path
        )
    except (ffmpeg.FFmpegError, TextOverflowError, audio.LoudnormNotLinearError) as exc:
        print(f"render failed: {exc}", file=sys.stderr)
        return EXIT_RENDER

    checks = verify.verify(spec, ws, master, log_path)
    status = verify.overall_status(checks)

    if status == "fail":
        verify.write_reports(
            checks,
            ws.logs_dir / f"{_timestamp()}_qa.json",
            ws.logs_dir / f"{_timestamp()}_qa.md",
        )
        print(f"QA failed; master left at {master} and the report is in {ws.logs_dir}",
              file=sys.stderr)
        for check in checks:
            if check.status == verify.FAIL:
                print(f"  FAIL {check.name}: {check.detail}", file=sys.stderr)
        return EXIT_QA

    version = None if mode == "draft" else ws.next_version()
    target = ws.out_master(version)
    shutil.move(str(master), str(target))

    derive.render_cover(spec, ws, overlay_pngs, ws.out_cover(version))
    derive.write_srt(spec.captions, ws.out_srt(version))
    derive.write_ass(
        spec.captions, spec.styles[spec.captions_style], spec.canvas, ws.out_ass(version)
    )
    verify.contact_sheet(spec, target, ws.out_contact_sheet(version), log_path)
    verify.write_reports(checks, ws.out_qa_json(version), ws.out_qa_md(version))

    manifest.set("run", digest)
    manifest.set("run/version", str(version) if version is not None else "draft")
    manifest.save()

    print(f"wrote {target}")
    return EXIT_INCOMPLETE if status == "incomplete" else EXIT_OK


def cmd_verify(slug: str, root: Path, version: int | None) -> int:
    ws = Workspace(root=root, slug=slug, mode="final")
    log_path = ws.log_path(_timestamp())
    try:
        spec, _ = load_spec(ws.spec_path)
    except ValueError as exc:
        print(f"spec is unusable:\n{exc}", file=sys.stderr)
        return EXIT_PREFLIGHT

    resolved = version if version is not None else ws.next_version() - 1
    master = ws.out_master(resolved)
    if not master.is_file():
        print(f"no rendered master at {master}", file=sys.stderr)
        return EXIT_PREFLIGHT

    checks = verify.verify(spec, ws, master, log_path)
    verify.write_reports(checks, ws.out_qa_json(resolved), ws.out_qa_md(resolved))
    status = verify.overall_status(checks)
    print(f"{master.name}: {status}")
    return {"pass": EXIT_OK, "fail": EXIT_QA, "incomplete": EXIT_INCOMPLETE}[status]


def cmd_clean(slug: str, root: Path, mode: str | None) -> int:
    modes = [mode] if mode else ["final", "draft"]
    for one in modes:
        work = Workspace(root=root, slug=slug, mode=one).work_dir
        if work.exists():
            shutil.rmtree(work)
            print(f"removed {work}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stitcher")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="schema and consistency only, no assets")
    validate.add_argument("spec", type=Path)

    render = sub.add_parser("render", help="render one Short")
    render.add_argument("slug")
    render.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    render.add_argument("--mode", choices=("final", "draft"), default="final")
    render.add_argument("--force", action="store_true")

    verify_cmd = sub.add_parser("verify", help="re-run QA against an existing output")
    verify_cmd.add_argument("slug")
    verify_cmd.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    verify_cmd.add_argument("--version", type=int, default=None)

    clean = sub.add_parser("clean", help="delete work/, keep out/ and logs/")
    clean.add_argument("slug")
    clean.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    clean.add_argument("--mode", choices=("final", "draft"), default=None)

    args = parser.parse_args(argv)
    if args.command == "validate":
        return cmd_validate(args.spec)
    if args.command == "render":
        return cmd_render(args.slug, args.root, args.mode, args.force)
    if args.command == "verify":
        return cmd_verify(args.slug, args.root, args.version)
    return cmd_clean(args.slug, args.root, args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
```

Also create `stitcher/stitcher/__main__.py` so `python -m stitcher` works:

```python
from .cli import main

raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd stitcher && python -m pytest tests/test_cli.py -v`
Expected: PASS — 15 passed

- [ ] **Step 5: Run the whole suite**

Run: `cd stitcher && python -m pytest tests/ -v`
Expected: PASS — every test from Tasks 1–14

- [ ] **Step 6: Commit**

```bash
git add stitcher/stitcher/cli.py stitcher/stitcher/__main__.py stitcher/stitcher/naming.py stitcher/tests/test_cli.py stitcher/tests/test_naming.py
git commit -m "feat(stitcher): CLI orchestration, QA-gated promotion, cache-hit no-op"
```

---

### Task 15: End-to-end fixture render

**Files:**
- Create: `stitcher/tests/fixtures/make_fixture.py`
- Create: `stitcher/tests/fixtures/__init__.py` (empty — `test_e2e.py` imports `tests.fixtures.make_fixture`)
- Create: `stitcher/tests/test_e2e.py`
- Create: `stitcher/README.md`

`pytest.ini` already exists from Task 1, including the `e2e` marker.

**Interfaces:**
- Consumes: everything.
- Produces: `make_fixture.build(root: Path) -> Path` returning the workspace base directory, with a 6-second, 3-shot spec over generated assets.

**This is the test that proves the stages actually compose**, and its assertions are the QA report itself — which means stage F is exercised on every run rather than only in anger (spec §7). It needs real FFmpeg, so it is marked `e2e` and skipped when FFmpeg is absent.

- [ ] **Step 1: Write the fixture builder**

```python
# stitcher/tests/fixtures/make_fixture.py
"""Generate a tiny, fully-conforming workspace for the end-to-end test.

Assets are synthesized rather than committed: solid-colour PNGs via Pillow and
sine/silence WAVs via ffmpeg's lavfi, so the repository carries no binaries.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image

FONT_CANDIDATES = [
    Path(__file__).parent / "fonts" / "Inter-Bold.ttf",
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
]


def find_font() -> Path | None:
    return next((path for path in FONT_CANDIDATES if path.is_file()), None)


def _tone(path: Path, frequency: int, duration: float) -> None:
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-y", "-f", "lavfi",
         "-i", f"sine=frequency={frequency}:duration={duration}:sample_rate=48000",
         "-ac", "2", "-c:a", "pcm_s16le", str(path)],
        check=True, capture_output=True,
    )


def build(root: Path) -> Path:
    font = find_font()
    if font is None:
        raise RuntimeError("no usable font found for the e2e fixture")

    base = root / "e2e"
    assets = base / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    for name, colour in (
        ("s1.png", (180, 60, 60)),
        ("s2.png", (60, 140, 180)),
        ("s3.png", (90, 170, 90)),
        ("cover.png", (30, 30, 40)),
    ):
        Image.new("RGB", (1600, 2400), colour).save(assets / name)

    _tone(assets / "vo.wav", 220, 5.0)
    _tone(assets / "bed.wav", 110, 6.0)

    spec = {
        "spec_version": "1.0",
        "slug": "e2e",
        "canvas": {"width": 1080, "height": 1920, "fps": 30},
        "safe_zone": {"x": 90, "y": 380, "width": 900, "height": 1160},
        "styles": {
            "card": {
                "font_file": str(font), "size_px": 64, "body": "#F7F3E8",
                "accent": "#F2A541", "ground": "#0E3B43", "ground_opacity": 0.85,
                "padding_px": [32, 40], "line_spacing": 1.15, "align": "center",
                "max_width_px": 760, "max_lines": 4, "stroke_px": 0,
                "stroke_color": "#000000",
            }
        },
        "shots": [
            {"n": 1, "id": "E-01", "beat": "Hook", "in": 0.0, "out": 2.0,
             "source": "s1.png", "kind": "still",
             "motion": {"kind": "push_in", "amount_pct": 12},
             "transition_in": {"kind": "cut"}},
            {"n": 2, "id": "E-02", "beat": "Build", "in": 2.0, "out": 4.0,
             "source": "s2.png", "kind": "still",
             "motion": {"kind": "none"}, "transition_in": {"kind": "cut"}},
            {"n": 3, "id": "E-03", "beat": "Payoff", "in": 4.0, "out": 6.0,
             "source": "s3.png", "kind": "still",
             "motion": {"kind": "push_in", "amount_pct": 8,
                        "anchor_start": [0.5, 0.5], "anchor_end": [0.5, 0.35]},
             "transition_in": {"kind": "cut"}},
        ],
        "overlays": [
            {"id": "card-1", "style": "card", "in": 0.0, "out": 2.0,
             "anchor": "center", "offset_px": [0, 0], "text": "FIRST [[CARD]]"},
            {"id": "card-2", "style": "card", "in": 2.0, "out": 4.0,
             "anchor": "center", "offset_px": [0, 0], "text": "SECOND [[CARD]]"},
        ],
        "captions": [
            {"in": 0.0, "out": 2.9, "text": "First spoken line."},
            {"in": 3.0, "out": 5.0, "text": "Second spoken line."},
        ],
        "captions_style": "card",
        "audio": {
            "stems": [{"id": "vo", "file": "vo.wav", "at": 0.0, "gain_db": 0.0}],
            "bed": {
                "file": "bed.wav", "gain_db": -8.0, "duck_db": -22.0,
                "duck_attack_ms": 120, "duck_release_ms": 400,
                "windows": [], "fades": [],
            },
            "sfx": [],
            "loudness": {"integrated_lufs": -14.0, "true_peak_dbtp": -1.5},
        },
        "cover": {"source": "cover.png", "overlays": []},
        "delivery": {
            "codec": "libx264", "crf": 23, "preset": "veryfast", "profile": "high",
            "pix_fmt": "yuv420p", "audio_codec": "aac",
            "audio_bitrate": "192k", "audio_rate": 48000,
        },
    }
    (base / "render-spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return base
```

- [ ] **Step 2: Write the end-to-end test**

Create an empty `stitcher/tests/fixtures/__init__.py` so `make_fixture` is importable as a module.

`stitcher/tests/test_e2e.py`:

```python
import json
import shutil
from pathlib import Path

import pytest

from stitcher import cli
from stitcher.naming import Workspace
from tests.fixtures import make_fixture

pytestmark = pytest.mark.e2e

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not on PATH",
)
needs_font = pytest.mark.skipif(
    make_fixture.find_font() is None, reason="no usable font for the fixture"
)


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    root = tmp_path_factory.mktemp("renders")
    make_fixture.build(root)
    code = cli.cmd_render("e2e", root, "final", force=False)
    return root, code


@needs_ffmpeg
@needs_font
def test_the_render_exits_clean(rendered):
    _, code = rendered
    assert code == cli.EXIT_OK


@needs_ffmpeg
@needs_font
def test_every_deliverable_is_written(rendered):
    root, _ = rendered
    ws = Workspace(root=root, slug="e2e", mode="final")
    for path in (ws.out_master(1), ws.out_cover(1), ws.out_srt(1), ws.out_ass(1),
                 ws.out_qa_json(1), ws.out_qa_md(1)):
        assert path.is_file(), f"missing deliverable: {path.name}"


@needs_ffmpeg
@needs_font
def test_the_qa_report_is_the_assertion_surface(rendered):
    root, _ = rendered
    ws = Workspace(root=root, slug="e2e", mode="final")
    payload = json.loads(ws.out_qa_json(1).read_text(encoding="utf-8"))
    assert payload["status"] == "pass", json.dumps(payload["checks"], indent=2)
    names = {check["name"] for check in payload["checks"]}
    assert {"container", "colour_tagging", "integrated_loudness", "true_peak",
            "loudnorm_linearity", "duck_depth", "safe_zone",
            "timeline_integrity", "placeholders"} <= names


@needs_ffmpeg
@needs_font
def test_the_master_is_a_conforming_short(rendered):
    from stitcher import ffmpeg
    root, _ = rendered
    ws = Workspace(root=root, slug="e2e", mode="final")
    probed = ffmpeg.probe(ws.out_master(1))
    assert (probed.width, probed.height) == (1080, 1920)
    assert probed.pix_fmt == "yuv420p"
    assert probed.colorspace == "bt709"
    assert probed.audio_codec == "aac"
    assert probed.sample_rate == 48000
    assert abs(probed.duration - 6.0) <= 1 / 30


@needs_ffmpeg
@needs_font
def test_a_second_identical_render_is_a_no_op(rendered):
    root, _ = rendered
    ws = Workspace(root=root, slug="e2e", mode="final")
    assert cli.cmd_render("e2e", root, "final", force=False) == cli.EXIT_OK
    assert not ws.out_master(2).exists()


@needs_ffmpeg
@needs_font
def test_draft_mode_renders_with_a_placeholder_for_a_missing_still(tmp_path):
    root = tmp_path / "renders"
    base = make_fixture.build(root)
    (base / "assets" / "s2.png").unlink()
    ws = Workspace(root=root, slug="e2e", mode="draft")
    assert cli.cmd_render("e2e", root, "draft", force=False) in (cli.EXIT_OK,)
    assert ws.out_master(None).is_file()
    payload = json.loads(ws.out_qa_json(None).read_text(encoding="utf-8"))
    placeholders = next(c for c in payload["checks"] if c["name"] == "placeholders")
    assert "s2" in placeholders["detail"] or "E-02" in placeholders["detail"]
```

- [ ] **Step 3: Run the end-to-end test**

Run: `cd stitcher && python -m pytest tests/test_e2e.py -v -m e2e`
Expected: PASS — 6 passed (or skipped with a clear reason if FFmpeg or a font is unavailable).

If `test_the_qa_report_is_the_assertion_surface` fails, the failing check's `detail` field names the exact discrepancy — read it before touching any code, and fix the stage it points at rather than loosening the tolerance.

- [ ] **Step 4: Write the module README**

`stitcher/README.md`:

```markdown
# Asset Stitcher

Turns a versioned `render-spec.json` plus a folder of assets into
publication-ready 9:16 Shorts deliverables: a master MP4, a cover image,
caption sidecars, and a QA report that measures rather than asserts.

Standalone: it imports nothing from `pipeline_app`, reads no skill, and never
opens the corpus. Design: `docs/superpowers/specs/2026-08-06-automated-asset-stitcher-design.md`.

## Install

```bash
pip install -r stitcher/requirements.txt
```

FFmpeg and ffprobe 8.x must be on `PATH`, built with libx264.

## Use

```bash
python -m stitcher validate renders/<slug>/render-spec.json
```

```bash
python -m stitcher render <slug> --mode draft
```

```bash
python -m stitcher render <slug>
```

`render` exits 0 on success, 1 on preflight or validation failure, 2 on render
failure, 3 on QA failure, 4 when verification could not be completed.

## Workspace

```
renders/<slug>/
  render-spec.json    the input contract
  assets/             inputs, never modified
  work/<mode>/        intermediates: safe to delete, always rebuildable
  out/                deliverables, version-stamped, never overwritten
  logs/               every ffmpeg command line, written before it runs
```

A version is allocated only on a QA pass. A failed render leaves its master in
`work/` and its report in `logs/`, so `out/` contains only outputs that met spec.

## Tests

```bash
cd stitcher && python -m pytest tests/ -v
```

The end-to-end test needs real FFmpeg and a usable font; it skips cleanly
without them. Golden-image tests are Windows-only because glyph rasterization
is not portable, and `Pillow` is pinned exactly for the same reason.
```

- [ ] **Step 5: Run the complete suite**

Run: `cd stitcher && python -m pytest tests/ -v`
Expected: PASS — every test in the project

- [ ] **Step 6: Commit**

```bash
git add stitcher/tests/fixtures/__init__.py stitcher/tests/fixtures/make_fixture.py stitcher/tests/test_e2e.py stitcher/README.md
git commit -m "test(stitcher): end-to-end fixture render gated by the QA report"
```

---

## Plan self-review notes

Run after writing, recorded here so an implementer knows what was already checked.

**Spec coverage.** Every numbered spec section maps to at least one task: §1 module layout → Tasks 1, 14; §2 workspace and naming → Tasks 1, 14 (Step 0); §3 render spec → Task 2, with the six additions (`source_in/out`, per-stem `gain_db`, wrap semantics, per-window `level_db`, `hold_s`/`anchor_start`/`anchor_end`, `captions[]`) each carrying their own test; §4 stage A → Tasks 6, 8; stage B → Task 7; stage C → Tasks 9, 10; stage D → Task 11; stage E → Task 12; stage F → Task 13; §5 caching → Tasks 4, 8, 14; §6 failure handling → Tasks 3, 5, 14; §7 testing → every task, plus Task 15; §8 limitations → enforced in Task 2's validation (canvas, transitions) and documented in Task 15's README.

**One gap found and closed during writing.** `verify.py` (Task 13) reads `work/<mode>/loudnorm_pass2.json`, but `audio.py` (Task 10) asserted linearity in-process without persisting the record — so `verify` run later would have reported `unavailable` forever. Task 13 now opens with Step 0, which adds the write to `audio.py` and a test for it.

**Naming consistency checked across tasks.** `start`/`end` (never `in_`) for every aliased time field; `render_all` not `render_shots`; `build_audio` returning `AudioResult` whose `.mix` is what stage D consumes; `out_master(version)` accepting `None` for draft after Task 14 Step 0; `measure_window` living in `verify` (monkeypatched there in tests) rather than in `ffmpeg`.

**Deliberate deviations from the spec, both stated in the header.** Two extra modules (`motion.py`, `envelope.py`) split pure maths out of their FFmpeg-executing stages so it can be unit-tested without a render.
