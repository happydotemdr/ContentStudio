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


def silence(path: Path, duration: float) -> None:
    """Digital zero. ebur128 measures this as I: -70.0 LUFS / Peak: -inf dBFS
    on the installed 9.0 binary, which is exactly what a draft whose stems
    were all synthesized as silence produces -- and what final mode has to
    refuse."""
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-y", "-f", "lavfi",
         "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{duration}",
         "-c:a", "pcm_s16le", str(path)],
        check=True, capture_output=True,
    )


def _testsrc(path: Path, fps: int, duration: float) -> None:
    """A real encoded video source, deliberately NOT at the canvas frame rate.

    25fps against a 30fps canvas is what makes `trim=start=X` land off the
    source's frame grid for most values of X, which is the condition stage A's
    clip path has to survive (see shots.clip_filters).
    """
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-y", "-f", "lavfi",
         "-i", f"testsrc=size=540x960:rate={fps}:duration={duration}",
         "-c:v", "libx264", "-crf", "28", "-preset", "ultrafast",
         "-pix_fmt", "yuv420p", str(path)],
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


CLIP_SLUG = "clip"
CLIP_SOURCE_FPS = 25
CLIP_SOURCE_IN = 0.5     # 0.5s is NOT on the 25fps grid boundary ffmpeg trims to
CLIP_SOURCE_OUT = 2.0
CLIP_RUNTIME = 3.0
CLIP_VOICE_S = 2.0       # deliberately shorter than the runtime


def build_clip(root: Path) -> Path:
    """A second, deliberately awkward workspace: the shapes the main e2e omits.

    Three things here are outside the main fixture's envelope and each one
    covers a defect that shipped because nothing exercised it against a real
    binary:

    1. A `kind: "clip"` shot at all -- the main fixture is three stills.
       `source_in=0.5` against a 25fps source is the exact case that made
       `trim` snap to the source grid and emit one frame fewer than the
       timeline slot asked for.
    2. No music bed. `audio.bed` is Optional and a bed-less spec is supported,
       but only the bed path had ever been rendered.
    3. A voice stem shorter than the runtime, which is what makes stage D's
       `-shortest` able to truncate the master when the mix is not padded.
    """
    font = find_font()
    if font is None:
        raise RuntimeError("no usable font found for the e2e fixture")

    base = root / CLIP_SLUG
    assets = base / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    Image.new("RGB", (1600, 2400), (120, 90, 160)).save(assets / "still.png")
    Image.new("RGB", (1600, 2400), (30, 30, 40)).save(assets / "cover.png")
    _testsrc(assets / "src.mp4", CLIP_SOURCE_FPS, 4.0)
    _tone(assets / "vo.wav", 220, CLIP_VOICE_S)

    spec = {
        "spec_version": "1.0",
        "slug": CLIP_SLUG,
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
            {"n": 1, "id": "C-01", "beat": "Hook", "in": 0.0, "out": 1.5,
             "source": "src.mp4", "kind": "clip",
             "source_in": CLIP_SOURCE_IN, "source_out": CLIP_SOURCE_OUT,
             "motion": {"kind": "none"}, "transition_in": {"kind": "cut"}},
            {"n": 2, "id": "C-02", "beat": "Payoff", "in": 1.5, "out": CLIP_RUNTIME,
             "source": "still.png", "kind": "still",
             "motion": {"kind": "push_in", "amount_pct": 8},
             "transition_in": {"kind": "cut"}},
        ],
        "overlays": [],
        "captions": [{"in": 0.0, "out": 1.9, "text": "Only spoken line."}],
        "captions_style": "card",
        "audio": {
            "stems": [{"id": "vo", "file": "vo.wav", "at": 0.0, "gain_db": 0.0}],
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
