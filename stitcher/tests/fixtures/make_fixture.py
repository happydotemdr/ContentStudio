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
