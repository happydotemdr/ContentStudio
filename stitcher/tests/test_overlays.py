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

# The overlong-single-token overflow test doesn't need Inter's specific
# metrics -- it only needs *some* real font where one word is wider than a
# tiny max_width_px, which is true of any real font. So, unlike every other
# font-dependent test above (Inter-only, by design -- see
# tests/fixtures/fonts/README.md), it falls back to a system font the same
# way Task 15's e2e fixture does, so the fix is actually exercised on a
# machine that lacks Inter-Bold.ttf instead of shipping unverified.
_OVERFLOW_FONT_CANDIDATES = [FONT_PATH, Path("C:/Windows/Fonts/arialbd.ttf")]
_OVERFLOW_FONT = next((p for p in _OVERFLOW_FONT_CANDIDATES if p.is_file()), None)
requires_any_font = pytest.mark.skipif(
    _OVERFLOW_FONT is None,
    reason="no usable font found (tried Inter-Bold.ttf, arialbd.ttf)",
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


def test_bbox_touching_the_safe_zone_edge_counts_as_within():
    """Boundary condition for bbox_within, made explicit (spec §4 stage F: the
    safe-zone check is "overlay bbox JSON from stage B [subset of] safe_zone" --
    a subset relation is inclusive of its own boundary, so a bbox that lands
    exactly on the safe-zone edge must count as inside, not outside. This test
    needs no font since bbox_within is pure tuple/int arithmetic."""
    edge_bbox = (SAFE.x, SAFE.y, SAFE.x + SAFE.width, SAFE.y + SAFE.height)
    assert ov.bbox_within(edge_bbox, SAFE) is True


@requires_font
def test_text_exceeding_max_lines_raises_rather_than_overflowing(tmp_path: Path):
    with pytest.raises(ov.TextOverflowError):
        ov.render_overlay(
            "one two three four five six seven eight nine ten eleven twelve",
            style(max_width_px=300, max_lines=2), CANVAS, "center", (0, 0),
            tmp_path / "card.png",
        )


@requires_any_font
def test_a_single_overlong_token_raises_rather_than_overflowing(tmp_path: Path):
    """wrap_lines cannot break a token with no internal space (a hashtag, a
    URL, an un-spaced accent span) -- it places the whole token on its own
    line even when that token alone is wider than max_width_px. Without a
    per-line width check, render_overlay would silently emit ink wider than
    the declared box (only line *count* was checked, never line *width*).
    max_width_px=50 is small enough that any real font overflows it with a
    long word, so this doesn't depend on Inter's specific metrics."""
    with pytest.raises(ov.TextOverflowError):
        ov.render_overlay(
            "SUPERCALIFRAGILISTICEXPIALIDOCIOUS",
            style(font_file=str(_OVERFLOW_FONT), max_width_px=50, max_lines=4),
            CANVAS, "center", (0, 0), tmp_path / "card.png",
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
