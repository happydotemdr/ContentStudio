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


def test_ass_timestamp_rounds_centiseconds_across_a_second_boundary():
    # 2.999s -> 299.9cs, rounds to 300cs = exactly 3.00s, not 2.100 truncated.
    assert dv.ass_timestamp(2.999) == "0:00:03.00"


def test_ass_timestamp_over_one_hour_keeps_a_single_unpadded_hour_digit():
    assert dv.ass_timestamp(3661.25) == "1:01:01.25"


def test_srt_timestamp_rounds_milliseconds_across_a_second_boundary():
    assert dv.srt_timestamp(2.9995) == "00:00:03,000"


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


def test_write_ass_escapes_braces_but_leaves_a_literal_backslash_alone(tmp_path: Path):
    # Unescaped `{...}` is parsed by libass as an override block and
    # silently dropped from the rendered text, so braces must be escaped.
    # A literal `\` must NOT be doubled: libass never collapses `\\` back
    # to `\`, so doubling would render two backslashes instead of one.
    multi = [Caption.model_validate({"in": 0.0, "out": 1.0, "text": "a{b}c\\d"})]
    body = dv.write_ass(multi, a_style(), CANVAS, tmp_path / "c.ass").read_text("utf-8")
    assert "a\\{b\\}c\\d" in body


def test_write_srt_and_write_ass_use_lf_line_endings_and_no_bom(tmp_path: Path):
    srt_bytes = dv.write_srt(captions(), tmp_path / "c.srt").read_bytes()
    ass_bytes = dv.write_ass(captions(), a_style(), CANVAS, tmp_path / "c.ass").read_bytes()
    assert b"\r" not in srt_bytes
    assert b"\r" not in ass_bytes
    assert not srt_bytes.startswith(b"\xef\xbb\xbf")
    assert not ass_bytes.startswith(b"\xef\xbb\xbf")


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


def test_render_cover_raises_when_a_named_overlay_png_is_missing(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["cover"]["overlays"] = ["hook-1"]
    spec, _ = load_spec(write(tmp_path, payload))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    Image.new("RGB", (1080, 1920), (0, 0, 0)).save(ws.asset("cover.png"))

    with pytest.raises(ValueError):
        dv.render_cover(spec, ws, {}, ws.out_cover(1))


def test_render_cover_conforms_a_source_wider_than_the_canvas_ratio(tmp_path: Path):
    # 1920x1080 is far wider than 1080x1920 (9:16) — the fit must scale to
    # the height and crop the overflowing width, not the other way round.
    payload = json.loads(json.dumps(MINIMAL))
    spec, _ = load_spec(write(tmp_path, payload))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    Image.new("RGB", (1920, 1080), (5, 5, 5)).save(ws.asset("cover.png"))

    out = ws.out_cover(1)
    dv.render_cover(spec, ws, {}, out)
    with Image.open(out) as image:
        assert image.size == (1080, 1920)


def test_render_cover_conforms_a_source_taller_than_the_canvas_ratio(tmp_path: Path):
    # 1000x3000 is far taller than 9:16 — the fit must scale to the width
    # and crop the overflowing height.
    payload = json.loads(json.dumps(MINIMAL))
    spec, _ = load_spec(write(tmp_path, payload))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    Image.new("RGB", (1000, 3000), (5, 5, 5)).save(ws.asset("cover.png"))

    out = ws.out_cover(1)
    dv.render_cover(spec, ws, {}, out)
    with Image.open(out) as image:
        assert image.size == (1080, 1920)
