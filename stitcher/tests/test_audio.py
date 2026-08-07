import json
from pathlib import Path

import pytest

from stitcher import audio as au
from stitcher.naming import Workspace
from stitcher.spec import load_spec, runtime_seconds
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


def test_the_final_mix_is_padded_to_the_runtime_before_it_is_trimmed(
    spec, workspace, monkeypatch
):
    """atrim only shortens. Without a pad in front of it, a mix whose sources
    all end before the runtime stays short, and stage D's `-shortest` then cuts
    the video down to the audio.

    The pad must also be bounded at the source with `whole_dur`, not left
    bare: a bare `apad` is an unbounded generator, and atrim only discards
    the frames it produces past `runtime` rather than signalling EOF
    upstream, so ffmpeg can spin generating and discarding silence forever.
    Reproduced directly against the real 9.0 binary: bare `apad` hung
    intermittently (1/10, also seen 1/3 and 1/15 in other trials) under the
    exact subprocess invocation shape ffmpeg.run() uses; `apad=whole_dur=...`
    hung 0/15."""
    calls = wire(monkeypatch)
    au.build_audio(spec, workspace, "final", workspace.log_path("t"), [])
    pre = [c for c in calls if c[-1].endswith("05_mix_pre-loudnorm.wav")][-1]
    graph = pre[pre.index("-filter_complex") + 1]
    assert f"apad=whole_dur={runtime_seconds(spec):.6f},atrim=0:" in graph


def test_a_dynamic_loudnorm_fallback_is_a_hard_failure(spec, workspace, monkeypatch):
    wire(monkeypatch, pass2=PASS2_DYNAMIC)
    with pytest.raises(au.LoudnormNotLinearError):
        au.build_audio(spec, workspace, "final", workspace.log_path("t"), [])


def test_bed_levels_are_offset_by_the_measured_voice_reference(spec, workspace, monkeypatch):
    calls = wire(monkeypatch)
    result = au.build_audio(spec, workspace, "final", workspace.log_path("t"), [])
    assert result.voice_reference_lufs == pytest.approx(-18.0)
    # Match on the call that WRITES 04a (its last argv element, the output
    # path) rather than any call that merely reads it -- the duck step also
    # names 04a_bed_conformed.wav, as its input, so a plain substring search
    # over the whole argv would ambiguously match both commands.
    conform = [c for c in calls if c[-1].endswith("04a_bed_conformed.wav")][-1]
    # voice -18 LUFS, gain_db -8 -> bed target -26 LUFS, measured -18 -> -8 dB applied
    assert "volume=-8.0dB" in " ".join(conform)


def test_the_duck_envelope_is_applied_as_a_quoted_volume_expression(spec, workspace, monkeypatch):
    calls = wire(monkeypatch)
    au.build_audio(spec, workspace, "final", workspace.log_path("t"), [])
    # Same reasoning as the conform-call lookup above: the final mix step
    # also names 04b_bed_ducked.wav, as its input, so anchor to the call
    # that WRITES it (its output, the last argv element).
    duck = [c for c in calls if c[-1].endswith("04b_bed_ducked.wav")][-1]
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


def test_loudnorm_pass2_record_is_persisted_for_verify(spec, workspace, monkeypatch):
    wire(monkeypatch)
    au.build_audio(spec, workspace, "final", workspace.log_path("t"), [])
    record = workspace.work_dir / "loudnorm_pass2.json"
    assert record.is_file()
    assert json.loads(record.read_text())["normalization_type"] == "linear"


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
