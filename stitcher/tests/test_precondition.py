from pathlib import Path

import pytest

from stitcher import precondition as pc


def wire(monkeypatch, measurements: list[dict]):
    """Record ffmpeg.run calls; feed measure_loudness from `measurements` in
    order. The first item is the source measurement (step 1 of the
    algorithm); each remaining item is one attempt's measurement of the
    freshly-written temp file (step 3, looped)."""
    calls: list[list[str]] = []
    remaining = list(measurements)

    def fake_run(args, log_path):
        calls.append(args)
        Path(args[-1]).write_bytes(b"wav")
        return ""

    def fake_measure(path, log_path):
        if not remaining:
            raise AssertionError("measure_loudness called more times than scripted")
        return remaining.pop(0)

    monkeypatch.setattr(pc.ffmpeg, "run", fake_run)
    monkeypatch.setattr(pc.ffmpeg, "measure_loudness", fake_measure)
    return calls


def test_clean_path_accepts_on_the_first_attempt(tmp_path, monkeypatch):
    calls = wire(monkeypatch, [
        {"input_i": -20.0, "input_tp": -6.0, "input_lra": 5.0},   # source
        {"input_i": -14.0, "input_tp": -2.5, "input_lra": 4.0},   # attempt 1: both ok
    ])
    source = tmp_path / "raw.wav"
    source.write_bytes(b"x")
    out_path = tmp_path / "conditioned.wav"
    log_path = tmp_path / "log.txt"

    result = pc.condition_clip(source, -14.0, -2.5, out_path, log_path)

    assert len(calls) == 1
    joined = " ".join(calls[0])
    # resample first, then gain, then limiter -- spec §4.1 step 3, order matters
    assert joined.index("aresample=48000") < joined.index("volume=6.00dB")
    assert joined.index("volume=6.00dB") < joined.index("alimiter=")
    expected_limit = 10 ** (-2.5 / 20)
    assert f"alimiter=limit={expected_limit:.6f}" in joined
    assert "level=0" in joined
    assert "latency=1" in joined  # timing-alignment property (spec §7)
    assert calls[0][calls[0].index("-ac") + 1] == "2"  # output-channel-count property (spec §7)
    assert "pcm_s16le" in calls[0]

    assert result.source == source
    assert result.output == out_path
    assert result.input_measurement == {"input_i": -20.0, "input_tp": -6.0, "input_lra": 5.0}
    assert result.output_measurement == {"input_i": -14.0, "input_tp": -2.5, "input_lra": 4.0}
    # (input_tp=-6.0 + applied_gain=6.0) - output_tp=-2.5 = 2.5
    assert result.peak_reduction_db == pytest.approx(2.5)
    assert result.limited is True  # 2.5 > the 0.05 threshold
    assert out_path.is_file()
    assert out_path.read_bytes() == b"wav"


def test_a_clip_that_needed_no_limiting_reports_limited_false(tmp_path, monkeypatch):
    wire(monkeypatch, [
        {"input_i": -20.0, "input_tp": -20.0, "input_lra": 5.0},  # very quiet source
        {"input_i": -14.0, "input_tp": -14.0, "input_lra": 5.0},  # gain alone landed here
    ])
    source = tmp_path / "raw.wav"
    source.write_bytes(b"x")
    result = pc.condition_clip(source, -14.0, -2.5, tmp_path / "out.wav", tmp_path / "log.txt")
    # (input_tp=-20.0 + applied_gain=6.0) - output_tp=-14.0 = 0.0
    assert result.peak_reduction_db == pytest.approx(0.0)
    assert result.limited is False


def test_a_high_true_peak_triggers_a_tightened_ceiling_retry_with_gain_unchanged(tmp_path, monkeypatch):
    calls = wire(monkeypatch, [
        {"input_i": -20.0, "input_tp": -6.0, "input_lra": 5.0},   # source
        {"input_i": -14.0, "input_tp": -2.0, "input_lra": 4.0},   # attempt 1: tp fails (-2.0 > -2.4)
        {"input_i": -14.0, "input_tp": -3.2, "input_lra": 4.0},   # attempt 2: tp passes at tightened ceiling
    ])
    source = tmp_path / "raw.wav"
    source.write_bytes(b"x")
    out_path = tmp_path / "out.wav"
    log_path = tmp_path / "log.txt"

    result = pc.condition_clip(source, -14.0, -2.5, out_path, log_path)

    assert len(calls) == 2
    first, second = calls
    assert "volume=6.00dB" in " ".join(first)
    assert "volume=6.00dB" in " ".join(second)  # gain untouched by a peak-only retry
    expected_ceiling = -2.5 - ((-2.0 - -2.5) + 0.2)
    expected_limit = 10 ** (expected_ceiling / 20)
    assert f"alimiter=limit={expected_limit:.6f}" in " ".join(second)
    assert result.output_measurement["input_tp"] == -3.2
    assert out_path.is_file()


@pytest.mark.e2e
def test_condition_clip_against_real_ffmpeg(tmp_path):
    """Every other test in this file mocks ffmpeg.run/measure_loudness, so
    none of them can catch a command that's syntactically invalid to the
    real binary -- e.g. a temp output filename ffmpeg can't infer a muxer
    from, which is exactly the bug an Opus review of this plan caught by
    actually running condition_clip against real ffmpeg (a mocked-only test
    suite went green while the real thing failed on its first call). This
    test runs the real ffmpeg 9.0 binary once, end to end, no mocking."""
    source = tmp_path / "tone.wav"
    pc.ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-y", "-f", "lavfi",
         "-i", "sine=frequency=220:duration=3", "-ac", "1",
         "-c:a", "pcm_s16le", str(source)],
        tmp_path / "gen_log.txt",
    )
    out_path = tmp_path / "conditioned.wav"
    result = pc.condition_clip(source, -14.0, -2.5, out_path, tmp_path / "log.txt")
    assert result.output.is_file()
    assert abs(result.output_measurement["input_i"] + 14.0) <= pc.LUFS_TOLERANCE
    assert pc.ffmpeg.probe(result.output).duration == pytest.approx(3.0, abs=0.05)
