# stitcher/tests/test_stage_cache.py
"""Per-stage caching for stages C and D (design spec sections 4 and 5).

Spec §4: "Each stage ... is independently cacheable." Spec §5's worked
example -- changing one card's copy "re-runs stages B, D, E, F and leaves the
15 shot clips untouched" -- pointedly excludes C, yet stage C used to re-run
its whole ffmpeg chain (stem placement, bed measure/conform/duck, mix, both
loudnorm passes) on every single render, and stage D re-encoded the master
unconditionally.

Every test here proves the SKIP by counting `ffmpeg.run` invocations rather
than by checking the artifact is still correct: an artifact that is correct
because it was silently regenerated proves nothing about caching. And every
"changed input" case is a separate test, because a cache that returns a stale
artifact is far worse than no cache -- omitting something that should
invalidate is the failure mode to fear.
"""

import json
from pathlib import Path

import pytest

from stitcher import assemble as asm, audio as au
from stitcher.cache import Manifest
from stitcher.naming import Workspace
from stitcher.spec import load_spec
from tests.test_audio import PASS2_DYNAMIC, silence_the_voice, wire
from tests.test_spec import MINIMAL, write

FFMPEG_BUILD = "ffmpeg version 9.0"


# --- shared fixtures -----------------------------------------------------


@pytest.fixture
def spec(tmp_path: Path):
    loaded, _ = load_spec(write(tmp_path, MINIMAL))
    return loaded


@pytest.fixture
def workspace(tmp_path: Path):
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    for name in ("vo.wav", "bed.mp3"):
        ws.asset(name).write_bytes(b"x")
    return ws


# =========================================================================
# Stage C
# =========================================================================


def build(spec, ws, mode, missing, manifest):
    return au.build_audio(spec, ws, mode, ws.log_path("t"), missing, manifest)


@pytest.fixture
def stage_c(spec, workspace, monkeypatch):
    """One recorded, completed stage-C run and the call log behind it."""
    monkeypatch.setattr(au.ffmpeg, "ffmpeg_version", lambda: FFMPEG_BUILD)
    calls = wire(monkeypatch)
    first = build(spec, workspace, "final", [], Manifest(workspace.manifest_path))
    assert len(calls) >= 6, "the first run must actually do the ffmpeg work"
    return spec, workspace, calls, first


def rerun_stage_c(spec, ws, missing=()):
    return build(spec, ws, "final", list(missing), Manifest.load(ws.manifest_path))


def test_an_unchanged_stage_c_re_render_runs_no_ffmpeg_at_all(stage_c):
    spec, ws, calls, first = stage_c
    burned = len(calls)

    second = rerun_stage_c(spec, ws)

    # The skip itself, measured: not one further ffmpeg invocation.
    assert len(calls) == burned
    # ...and the whole AudioResult comes back, not a thinner stand-in. Every
    # field is durable somewhere in work/, so a hit reconstructs all of them.
    assert second.mix == first.mix
    assert second.bed_conformed == first.bed_conformed
    assert second.bed_ducked == first.bed_ducked
    assert second.voice_reference_lufs == first.voice_reference_lufs
    assert second.loudnorm == first.loudnorm
    assert second.omitted == first.omitted
    assert second.silent_stems == first.silent_stems


def test_a_changed_stem_file_content_misses_the_stage_c_cache(stage_c):
    """The digest is over CONTENT, not the filename: a re-recorded VO dropped
    in under the same name is the likeliest stale-cache trap in this stage."""
    spec, ws, calls, _ = stage_c
    burned = len(calls)
    ws.asset("vo.wav").write_bytes(b"a different take entirely")

    rerun_stage_c(spec, ws)
    assert len(calls) > burned


def test_a_changed_bed_file_content_misses_the_stage_c_cache(stage_c):
    spec, ws, calls, _ = stage_c
    burned = len(calls)
    ws.asset("bed.mp3").write_bytes(b"different music")

    rerun_stage_c(spec, ws)
    assert len(calls) > burned


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda s: setattr(s.audio.bed, "gain_db", -4.0), id="bed-gain_db"),
        pytest.param(lambda s: setattr(s.audio.bed, "duck_db", -20.0), id="bed-duck_db"),
        pytest.param(
            lambda s: setattr(s.audio.bed, "duck_attack_ms", 250), id="duck_attack_ms"
        ),
        pytest.param(
            lambda s: setattr(s.audio.bed, "duck_release_ms", 900), id="duck_release_ms"
        ),
        pytest.param(lambda s: setattr(s.audio.stems[0], "at", 0.75), id="stem-at"),
        pytest.param(
            lambda s: setattr(s.audio.stems[0], "gain_db", 3.0), id="stem-gain_db"
        ),
        pytest.param(
            lambda s: setattr(s.audio.loudness, "integrated_lufs", -16.0),
            id="integrated_lufs",
        ),
        pytest.param(
            lambda s: setattr(s.audio.loudness, "true_peak_dbtp", -2.5), id="true_peak"
        ),
        pytest.param(lambda s: setattr(s.shots[-1], "end", 9.0), id="runtime"),
    ],
)
def test_a_changed_audio_input_misses_the_stage_c_cache(stage_c, mutate):
    """One case per field that reaches an ffmpeg argument.

    `runtime` is in the list because it comes from the LAST SHOT's `out`, not
    from `spec.audio` at all -- hashing only the audio fragment would let a
    lengthened timeline keep serving a short mix, which stage D's `-shortest`
    then truncates the VIDEO down to.
    """
    spec, ws, calls, _ = stage_c
    burned = len(calls)
    mutate(spec)

    rerun_stage_c(spec, ws)
    assert len(calls) > burned


def test_a_changed_missing_audio_list_misses_the_stage_c_cache(spec, workspace, monkeypatch):
    """`missing_audio` is preflight's judgement about what to omit or
    synthesize as silence, not a property of the files on disk, so it has to
    be in the key in its own right."""
    monkeypatch.setattr(au.ffmpeg, "ffmpeg_version", lambda: FFMPEG_BUILD)
    calls = wire(monkeypatch)
    ws = Workspace(root=workspace.root, slug="demo", mode="draft")
    ws.ensure_dirs()
    for name in ("vo.wav", "bed.mp3"):
        ws.asset(name).write_bytes(b"x")

    build(spec, ws, "draft", [], Manifest(ws.manifest_path))
    burned = len(calls)
    assert burned >= 6

    # Same files, same spec, same mode -- only the omission list moved.
    build(spec, ws, "draft", ["bed.mp3"], Manifest.load(ws.manifest_path))
    assert len(calls) > burned


def test_a_changed_ffmpeg_build_misses_the_stage_c_cache(stage_c, monkeypatch):
    spec, ws, calls, _ = stage_c
    burned = len(calls)
    monkeypatch.setattr(au.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 10.1")

    rerun_stage_c(spec, ws)
    assert len(calls) > burned


def test_the_run_mode_is_in_the_stage_c_key(spec, workspace):
    """Spec §5 names a draft artifact satisfying a final-mode lookup as one of
    "the two worst failures this design could produce". The work/draft vs
    work/final split already prevents it; `mode` in the key is the second
    lock, not a substitute for the first."""
    draft = Workspace(root=workspace.root, slug="demo", mode="draft")
    draft.ensure_dirs()
    for name in ("vo.wav", "bed.mp3"):
        draft.asset(name).write_bytes(b"x")

    assert au.audio_cache_key(spec, workspace, "final", FFMPEG_BUILD, []) != (
        au.audio_cache_key(spec, draft, "draft", FFMPEG_BUILD, [])
    )


def test_a_missing_stage_c_artifact_is_a_cache_miss(stage_c):
    """Manifest.is_fresh already checks the mix survives; stage C additionally
    checks every artifact a later stage reads. A partially cleaned work/ must
    never report a hit that silently downgrades a stage-F check to
    UNAVAILABLE."""
    spec, ws, calls, _ = stage_c
    burned = len(calls)
    ws.audio_step("04b", "bed_ducked").unlink()

    rerun_stage_c(spec, ws)
    assert len(calls) > burned
    assert ws.audio_step("04b", "bed_ducked").is_file()


def test_a_deleted_mix_is_a_cache_miss(stage_c):
    spec, ws, calls, _ = stage_c
    burned = len(calls)
    ws.audio_step("06", "mix_final").unlink()

    rerun_stage_c(spec, ws)
    assert len(calls) > burned
    assert ws.audio_step("06", "mix_final").is_file()


def test_a_corrupt_audio_report_is_a_cache_miss_not_a_partial_hit(stage_c):
    """Every field of the reconstructed AudioResult comes from that record, so
    an unreadable one has to be a miss rather than a hit with holes in it."""
    spec, ws, calls, _ = stage_c
    burned = len(calls)
    ws.audio_report_path.write_text("{ not json at all", encoding="utf-8")

    rerun_stage_c(spec, ws)
    assert len(calls) > burned
    assert json.loads(ws.audio_report_path.read_text(encoding="utf-8"))["mode"] == "final"


def test_a_failed_stage_c_records_no_cache_key(spec, workspace, monkeypatch):
    """The key is written after the linearity gate, so a stage that raised can
    never be replayed from cache as though it had succeeded."""
    monkeypatch.setattr(au.ffmpeg, "ffmpeg_version", lambda: FFMPEG_BUILD)
    wire(monkeypatch, pass2=PASS2_DYNAMIC)
    with pytest.raises(au.LoudnormNotLinearError):
        build(spec, workspace, "final", [], Manifest(workspace.manifest_path))
    assert Manifest.load(workspace.manifest_path).get(au.CACHE_KEY) is None


def test_a_cached_stage_c_still_reports_its_omissions_and_preview_state(
    spec, workspace, monkeypatch
):
    """Wave A made stage C's omission/preview state durable in
    work/<mode>/audio_report.json, because stage F reads it to tell a
    deliberate draft omission apart from a cleaned work/. A cache that skipped
    the write would silently change the QA report on the second draft render.
    It cannot here: the record is one of the artifacts a hit requires, and the
    cached AudioResult is reconstructed FROM it."""
    monkeypatch.setattr(au.ffmpeg, "ffmpeg_version", lambda: FFMPEG_BUILD)
    calls = wire(monkeypatch, pass2=PASS2_DYNAMIC)
    silence_the_voice(monkeypatch)
    ws = Workspace(root=workspace.root, slug="demo", mode="draft")
    ws.ensure_dirs()
    ws.asset("vo.wav").write_bytes(b"x")  # bed.mp3 deliberately absent

    missing = ["bed.mp3", "vo.wav"]
    first = build(spec, ws, "draft", missing, Manifest(ws.manifest_path))
    burned = len(calls)

    second = build(spec, ws, "draft", missing, Manifest.load(ws.manifest_path))
    assert len(calls) == burned

    record = json.loads(ws.audio_report_path.read_text(encoding="utf-8"))
    assert record["preview_audio"] is True
    assert record["omitted"] == [{"file": "bed.mp3", "role": "bed"}]
    assert record["silent_stems"] == ["vo.wav"]
    assert record["bed_built"] is False
    assert second.omitted == first.omitted == [{"file": "bed.mp3", "role": "bed"}]
    assert second.silent_stems == first.silent_stems == ["vo.wav"]
    assert second.bed_ducked is None and first.bed_ducked is None


# =========================================================================
# Stage D
# =========================================================================


@pytest.fixture
def stage_d(tmp_path, spec, monkeypatch):
    """A workspace with stage A/B/C outputs on disk and a recording encoder."""
    monkeypatch.setattr(asm.ffmpeg, "ffmpeg_version", lambda: FFMPEG_BUILD)
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    clips = []
    for index in (1, 2):
        clip = ws.shot_clip(index, f"B-0{index}", "beat")
        clip.write_bytes(f"clip {index}".encode())
        clips.append(clip)
    mix = ws.audio_step("06", "mix_final")
    mix.write_bytes(b"wav")
    png = ws.overlay_png(1, "hook-1", "hello")
    png.write_bytes(b"png")

    calls: list[list[str]] = []

    def fake_run(args, log_path):
        calls.append(args)
        # The real encode writes the master; is_fresh checks it survives.
        Path(args[-1]).write_bytes(b"mp4")
        return ""

    monkeypatch.setattr(asm.ffmpeg, "run", fake_run)
    return spec, ws, clips, {"hook-1": png}, mix, calls


def run_stage_d(spec, ws, clips, pngs, mix, mode="final"):
    return asm.assemble(
        spec, ws, mode, clips, pngs, mix, ws.log_path("t"),
        Manifest.load(ws.manifest_path),
    )


def test_an_unchanged_stage_d_re_render_re_encodes_nothing(stage_d):
    spec, ws, clips, pngs, mix, calls = stage_d
    first = run_stage_d(spec, ws, clips, pngs, mix)
    assert len(calls) == 1

    second = run_stage_d(spec, ws, clips, pngs, mix)
    assert len(calls) == 1          # the skip, measured
    assert second == first == ws.master_path
    # concat.txt and graph_assemble.txt are still rewritten on a hit: spec §2
    # keeps both in work/ as the record of what was assembled, and a stale
    # graph sitting next to a current master would be actively misleading.
    assert ws.concat_path.is_file()
    assert "[vout]" in ws.graph_path.read_text(encoding="utf-8")


def test_a_re_rendered_clip_misses_the_stage_d_cache(stage_d):
    """This is what makes a stage A rebuild cascade: the clip filename is
    unchanged, only its bytes moved."""
    spec, ws, clips, pngs, mix, calls = stage_d
    run_stage_d(spec, ws, clips, pngs, mix)
    clips[0].write_bytes(b"a differently rendered clip")

    run_stage_d(spec, ws, clips, pngs, mix)
    assert len(calls) == 2


def test_a_reordered_clip_list_misses_the_stage_d_cache(stage_d):
    """The clip digests go into the key as an ORDERED list, never a set, so a
    swapped pair of shots -- same files, same names, different concat order --
    invalidates. (Checked by removing the clip names from the key: this test
    still fails on the ordered digest list alone, so the ordering really is
    carried by the digests and not incidentally by the names.)"""
    spec, ws, clips, pngs, mix, calls = stage_d
    run_stage_d(spec, ws, clips, pngs, mix)

    run_stage_d(spec, ws, list(reversed(clips)), pngs, mix)
    assert len(calls) == 2


def test_a_dropped_clip_misses_the_stage_d_cache(stage_d):
    spec, ws, clips, pngs, mix, calls = stage_d
    run_stage_d(spec, ws, clips, pngs, mix)

    run_stage_d(spec, ws, clips[:1], pngs, mix)
    assert len(calls) == 2


def test_a_re_rendered_overlay_png_misses_the_stage_d_cache(stage_d):
    """Spec §5's worked example: changing one card's copy must re-run stage D.
    Stage B rewrites the PNG in place under the same name, so only its content
    digest can carry that."""
    spec, ws, clips, pngs, mix, calls = stage_d
    run_stage_d(spec, ws, clips, pngs, mix)
    pngs["hook-1"].write_bytes(b"a different card entirely")

    run_stage_d(spec, ws, clips, pngs, mix)
    assert len(calls) == 2


def test_a_moved_overlay_window_misses_the_stage_d_cache(stage_d):
    """The overlay's in/out pair IS the `enable=` gate in the filtergraph, so
    a card that only moved in time -- same PNG bytes -- still has to
    invalidate."""
    spec, ws, clips, pngs, mix, calls = stage_d
    run_stage_d(spec, ws, clips, pngs, mix)
    spec.overlays[0].end = spec.overlays[0].end + 0.5

    run_stage_d(spec, ws, clips, pngs, mix)
    assert len(calls) == 2


def test_a_dropped_overlay_misses_the_stage_d_cache(stage_d):
    spec, ws, clips, pngs, mix, calls = stage_d
    run_stage_d(spec, ws, clips, pngs, mix)

    run_stage_d(spec, ws, clips, {}, mix)
    assert len(calls) == 2


def test_a_rebuilt_mix_misses_the_stage_d_cache(stage_d):
    spec, ws, clips, pngs, mix, calls = stage_d
    run_stage_d(spec, ws, clips, pngs, mix)
    mix.write_bytes(b"a remixed mix")

    run_stage_d(spec, ws, clips, pngs, mix)
    assert len(calls) == 2


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda s: setattr(s.delivery, "crf", 21), id="crf"),
        pytest.param(lambda s: setattr(s.delivery, "preset", "medium"), id="preset"),
        pytest.param(lambda s: setattr(s.delivery, "pix_fmt", "yuv422p"), id="pix_fmt"),
        pytest.param(
            lambda s: setattr(s.delivery, "audio_bitrate", "256k"), id="audio_bitrate"
        ),
        pytest.param(lambda s: setattr(s.canvas, "fps", 24), id="canvas-fps"),
    ],
)
def test_a_changed_delivery_setting_misses_the_stage_d_cache(stage_d, mutate):
    spec, ws, clips, pngs, mix, calls = stage_d
    run_stage_d(spec, ws, clips, pngs, mix)
    mutate(spec)

    run_stage_d(spec, ws, clips, pngs, mix)
    assert len(calls) == 2


def test_a_changed_ffmpeg_build_misses_the_stage_d_cache(stage_d, monkeypatch):
    spec, ws, clips, pngs, mix, calls = stage_d
    run_stage_d(spec, ws, clips, pngs, mix)
    monkeypatch.setattr(asm.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 10.1")

    run_stage_d(spec, ws, clips, pngs, mix)
    assert len(calls) == 2


def test_the_run_mode_is_in_the_stage_d_key(stage_d):
    """draft overrides crf/preset and gates the High-profile -x264-params fix,
    so a draft master must never satisfy a final lookup even if a caller
    pointed both modes at one work/ directory."""
    spec, ws, clips, pngs, mix, _ = stage_d
    ordered = [o for o in spec.overlays if o.id in pngs]
    assert asm.assemble_cache_key(
        spec, "final", clips, ordered, pngs, mix, FFMPEG_BUILD
    ) != asm.assemble_cache_key(
        spec, "draft", clips, ordered, pngs, mix, FFMPEG_BUILD
    )


def test_a_promoted_master_leaves_stage_d_with_nothing_to_serve(stage_d):
    """cmd_render moves the master out of work/ on a QA pass, so the next run
    has no artifact behind the key. Manifest.is_fresh already checks the
    artifact exists -- this proves stage D honours that rather than trusting
    the digest alone."""
    spec, ws, clips, pngs, mix, calls = stage_d
    run_stage_d(spec, ws, clips, pngs, mix)
    ws.master_path.unlink()

    run_stage_d(spec, ws, clips, pngs, mix)
    assert len(calls) == 2
    assert ws.master_path.is_file()


def test_a_failed_stage_d_encode_records_no_cache_key(stage_d, monkeypatch):
    spec, ws, clips, pngs, mix, calls = stage_d

    def explode(args, log_path):
        calls.append(args)
        Path(args[-1]).write_bytes(b"half an mp4")
        raise asm.ffmpeg.FFmpegError("encode failed")

    monkeypatch.setattr(asm.ffmpeg, "run", explode)
    with pytest.raises(asm.ffmpeg.FFmpegError):
        run_stage_d(spec, ws, clips, pngs, mix)

    assert Manifest.load(ws.manifest_path).get(asm.CACHE_KEY) is None
