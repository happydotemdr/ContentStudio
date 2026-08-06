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
    """Text could not be laid out within the style's box (spec line 369):
    either wrapping needed more than max_lines lines, or a single token (no
    space to break on -- a hashtag, URL, or un-spaced accent span) is wider
    than max_width_px on its own and would render outside the declared box.
    """


@dataclass(frozen=True)
class RenderedOverlay:
    png: Path
    bbox: tuple[int, int, int, int]


def parse_accent(text: str) -> list[Line]:
    """Split text into hard-broken lines of (run, is_accent) pairs.

    The outer list is one entry per `\\n`-separated hard line; the inner list
    is the ordered (run_text, is_accent) runs within that line, in the order
    they appear. `[[...]]` marks an accent span (spec `overlays[]`).
    """
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

    # wrap_lines only breaks *between* tokens, so a single token with no
    # space to break on (a hashtag, URL, or un-spaced accent span) that is
    # itself wider than max_width_px is placed on its own line unchecked --
    # it must be caught here, or it renders wider than the declared box with
    # no error and no signal (spec line 369).
    line_widths = [_measure(font, _line_text(line)) for line in lines]
    for line, line_w in zip(lines, line_widths):
        if line_w > style.max_width_px:
            raise TextOverflowError(
                f"line {_line_text(line)!r} is {line_w}px wide but "
                f"max_width_px is {style.max_width_px}: {text!r}"
            )

    if len(lines) > style.max_lines:
        raise TextOverflowError(
            f"text wraps to {len(lines)} lines at {style.max_width_px}px but "
            f"max_lines is {style.max_lines}: {text!r}"
        )

    line_h = int(style.size_px * style.line_spacing)
    block_w = max(line_widths, default=0)
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
    """True iff bbox is a subset of safe_zone (spec §4 stage F: "overlay bbox
    JSON from stage B ⊆ safe_zone"). A subset relation is inclusive of its own
    boundary, so a bbox edge that lands exactly on the safe-zone edge counts
    as inside, not outside -- hence >= / <= rather than strict inequalities.
    """
    left, top, right, bottom = bbox
    return (
        left >= safe_zone.x
        and top >= safe_zone.y
        and right <= safe_zone.x + safe_zone.width
        and bottom <= safe_zone.y + safe_zone.height
    )
