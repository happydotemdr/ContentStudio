r"""Stage E: the cover image and the caption sidecars.

The sidecars are generated from `captions[]` — authored spoken lines — never
from overlay card copy. Cards are designed copy, not a transcript, and an .srt
built from them would be a caption track that does not match the narration
(spec §3).

Encoding: both sidecars are written as UTF-8 without a byte-order mark
(Python's plain ``"utf-8"`` codec never emits one) and with LF-only (``\n``)
line endings, chosen explicitly via ``newline="\n"`` on every write. Left to
its default, `Path.write_text` on Windows translates '\n' to the platform
line separator ('\r\n'), which would make the sidecar's on-disk bytes depend
on the host OS this pipeline happens to run on. SRT and ASS players (VLC,
YouTube's uploader, etc.) accept bare LF; a BOM is the more common breakage
(some parsers treat it as part of the first cue's text), so avoiding one is
the more load-bearing choice of the two.

Escaping (`.ass` only — `.srt` is plain text and needs none): caption text
may contain `{`, `}`, or `\`, all of which are meaningful to the ASS format.
An unescaped `{...}` run is parsed as an override block and silently
vanishes from the rendered text; an unescaped `\` can accidentally start a
recognised escape (`\N`, `\n`, `\h`) if followed by the right letter. Both
are escaped by prefixing a backslash — `\` -> `\\`, `{` -> `\{`, `}` -> `\}`
— in that order, so a literal backslash in the source text is doubled before
any brace-escaping backslashes are added, and doubled again ahead of the
`\N` this module injects for embedded newlines. A caption is a sidecar, not
a burn-in target (no libass dependency here), but a well-formed sidecar
should not be able to eat itself.
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
    """`HH:MM:SS,mmm` — comma decimal, three-digit milliseconds."""
    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def ass_timestamp(seconds: float) -> str:
    """`H:MM:SS.cc` — single-digit hour, period decimal, two-digit centiseconds."""
    total_cs = int(round(seconds * 100))
    hours, remainder = divmod(total_cs, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, centis = divmod(remainder, 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _ass_colour(hex_value: str) -> str:
    """#RRGGBB -> &H00BBGGRR (ASS stores colours blue-first)."""
    text = hex_value.lstrip("#")
    return f"&H00{text[4:6]}{text[2:4]}{text[0:2]}".upper()


def _ass_escape(text: str) -> str:
    """Escape `\\`, `{`, `}`, then turn embedded newlines into `\\N` hard breaks.

    Order matters: backslashes in the source text are doubled first so the
    brace-escaping backslashes (and the `\\N` line-break marker) added below
    are never themselves mistaken for user text and re-escaped.
    """
    escaped = text.replace("\\", "\\\\")
    escaped = escaped.replace("{", "\\{").replace("}", "\\}")
    return escaped.replace("\n", "\\N")


def write_srt(captions: list[Caption], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    blocks = [
        f"{index}\n{srt_timestamp(caption.start)} --> {srt_timestamp(caption.end)}\n"
        f"{caption.text}\n"
        for index, caption in enumerate(captions, start=1)
    ]
    path.write_text("\n".join(blocks), encoding="utf-8", newline="\n")
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
        f"Default,,0,0,0,,{_ass_escape(caption.text)}"
        for caption in captions
    ]
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def render_cover(
    spec: RenderSpec,
    ws: Workspace,
    overlay_pngs: dict[str, Path],
    out_png: Path,
) -> Path | None:
    """Conform the supplied cover asset and composite its named overlays.

    Never a frame extract: the cover is a standalone asset (`cover.source`)
    that does not appear anywhere in the shot timeline. Conforming is a
    "cover" fit — scale to fill the canvas on the shorter axis, then
    center-crop the overflow on the longer axis — identical for a source
    that is wider than, taller than, or exactly the canvas's aspect ratio.
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
        if name not in overlay_pngs:
            raise KeyError(
                f"cover names overlay {name!r} but no rendered PNG was supplied for it"
            )
        with Image.open(overlay_pngs[name]) as layer:
            cover.alpha_composite(layer.convert("RGBA"))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    cover.convert("RGB").save(out_png)
    return out_png
