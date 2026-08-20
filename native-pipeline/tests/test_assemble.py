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
