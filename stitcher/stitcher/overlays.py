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
# A line is its rendered text split into coloured runs, IN ORDER and with no
# separator implied between them: concatenating a Line's run texts reproduces
# the line exactly. Spaces therefore live inside the runs, never between them.
Line = list[Run]
# A whitespace-delimited word, which may itself be several coloured runs when
# an accent span abuts its neighbour. Internal to wrapping.
Token = list[Run]


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


def _tokenize(line: Line) -> list[Token]:
    """Split a line into wrappable tokens, each a list of coloured runs.

    A token is a whitespace-delimited word and the unit wrap_lines is allowed
    to break between; it holds MORE THAN ONE run when an accent span abuts its
    neighbour with no space between them. `BEST[[MUD]]` is one word rendered
    in two colours, not two words: treating it as two tokens is what made
    render_overlay emit `BEST MUD`, silently altering burned-in copy.
    """
    tokens: list[Token] = []
    joined_to_previous = False
    for text, is_accent in line:
        if not text:
            continue
        for index, piece in enumerate(text.split(" ")):
            if index > 0:
                joined_to_previous = False   # a space closed the last token
            if not piece:
                continue
            if joined_to_previous and tokens:
                tokens[-1].append((piece, is_accent))
            else:
                tokens.append([(piece, is_accent)])
            joined_to_previous = True
    return tokens


def _token_text(token: Token) -> str:
    return "".join(text for text, _ in token)


def _runs_for(tokens: list[Token]) -> Line:
    """Flatten wrapped tokens back to runs, with the separating spaces baked in.

    A `Line` is therefore always the exact rendered text of that line, run by
    run and in order, with no separator implied between runs -- so the space
    an accent span does NOT have cannot be reintroduced by the renderer.
    """
    runs: Line = []
    for index, token in enumerate(tokens):
        runs.extend(token)
        if index < len(tokens) - 1:
            text, is_accent = runs[-1]
            runs[-1] = (text + " ", is_accent)
    return runs


def wrap_lines(
    lines: list[Line], font: ImageFont.FreeTypeFont, max_width_px: int
) -> list[Line]:
    """Word-wrap each hard line to max_width_px, preserving accent flags."""
    wrapped: list[Line] = []
    for line in lines:
        current: list[Token] = []
        for token in _tokenize(line):
            candidate = current + [token]
            if current and _measure(font, _tokens_text(candidate)) > max_width_px:
                wrapped.append(_runs_for(current))
                current = [token]
            else:
                current = candidate
        wrapped.append(_runs_for(current) or [("", False)])
    return wrapped


def _tokens_text(tokens: list[Token]) -> str:
    return " ".join(_token_text(token) for token in tokens)


def _line_text(line: Line) -> str:
    return "".join(text for text, _ in line)


def _anchor_origin(anchor: str, canvas: Canvas, block_h: int) -> int:
    if anchor == "upper_third":
        return canvas.height // 3 - block_h // 2
    if anchor == "lower_third":
        return canvas.height * 2 // 3 - block_h // 2
    return canvas.height // 2 - block_h // 2


def _hex_to_rgba(value: str, alpha: int) -> tuple[int, int, int, int]:
    text = value.lstrip("#")
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), alpha)


def fit_error(
    text: str, style: Style, font: ImageFont.FreeTypeFont
) -> str | None:
    """Why `text` cannot be laid out inside `style`'s box, or None if it fits.

    Split out of render_overlay so PREFLIGHT can run the identical check
    before a single frame is encoded (design spec line 227: "exceeding
    max_lines after wrapping is a preflight failure", and line 369, which
    lists it among the things rejected "before any asset is touched"). Left
    inside stage B it only fired after stage A had already burned an encode
    per shot, and reported as a render failure rather than a spec failure.
    Both callers must agree on what "fits" means, so there is exactly one
    implementation of it.
    """
    lines = wrap_lines(parse_accent(text), font, style.max_width_px)

    # wrap_lines only breaks *between* tokens, so a single token with no
    # space to break on (a hashtag, URL, or un-spaced accent span) that is
    # itself wider than max_width_px is placed on its own line unchecked --
    # it must be caught, or it renders wider than the declared box with no
    # error and no signal (spec line 369).
    for line in lines:
        line_w = _measure(font, _line_text(line))
        if line_w > style.max_width_px:
            return (
                f"line {_line_text(line)!r} is {line_w}px wide but "
                f"max_width_px is {style.max_width_px}"
            )

    if len(lines) > style.max_lines:
        return (
            f"text wraps to {len(lines)} lines at {style.max_width_px}px but "
            f"max_lines is {style.max_lines}"
        )
    return None


def render_overlay(
    text: str,
    style: Style,
    canvas: Canvas,
    anchor: str,
    offset_px: tuple[int, int],
    out_png: Path,
) -> RenderedOverlay:
    font = ImageFont.truetype(style.font_file, style.size_px)

    # Preflight has normally rejected this already; this stays as stage B's
    # own guard for any caller that reaches the renderer directly.
    problem = fit_error(text, style, font)
    if problem is not None:
        raise TextOverflowError(f"{problem}: {text!r}")

    lines = wrap_lines(parse_accent(text), font, style.max_width_px)
    line_widths = [_measure(font, _line_text(line)) for line in lines]

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

        # Each run already carries whatever spacing follows it (see Line's
        # definition), so the renderer draws runs verbatim and never inserts a
        # separator of its own.
        for text, is_accent in line:
            draw.text(
                (cursor_x, cursor_y), text, font=font,
                fill=accent if is_accent else body,
                stroke_width=style.stroke_px, stroke_fill=stroke,
            )
            cursor_x += _measure(font, text)

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
