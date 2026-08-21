"""Wires VO generation, music generation, shot/caption/spec assembly, and
the final render into one sequence. This module -- and only this module in
this package -- calls out to elevenlabs_tooling (via subprocess, its CLI)
and to stitcher's render CLI (also via subprocess). Everything else in
native_pipeline only ever consumes stitcher as an imported library
(spec/vo_alignment/vo_timing/verify/ffmpeg) -- never the reverse.

Neither elevenlabs-tooling nor stitcher is pip-installed in this
environment -- both rely solely on pytest's own `pythonpath = .` ini
option when running their own test suites from inside their own
directory. `python -m <package>` only finds a package via sys.path
entries derived from the subprocess's own cwd (or PYTHONPATH), not from
wherever this process happens to be running -- so every subprocess call
below passes `cwd=` pointing at the invoked package's own root. Because
of that, every path argument handed to these subprocesses must already
be absolute: a relative path would otherwise resolve against the wrong
directory. Callers are responsible for constructing `Workspace` and any
payload/manifest paths from an absolute root (Task 10's CLI entrypoint
must guarantee this)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from stitcher.ffmpeg import measure_loudness
from stitcher.naming import Workspace
from stitcher.vo_alignment import Segment, derive_segments, derive_segments_v3
from stitcher.vo_timing import derive_captions

from native_pipeline import assemble, contracts, music_plan
from native_pipeline.errors import VoModeMismatchError
from native_pipeline.flagging import flag_outliers
from native_pipeline.shots import build_shots

# native-pipeline/native_pipeline/orchestrate.py -> repo root is three
# `.parent`s up (native_pipeline/ -> native-pipeline/ -> repo root).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ELEVENLABS_TOOLING_DIR = _REPO_ROOT / "elevenlabs-tooling"
_STITCHER_DIR = _REPO_ROOT / "stitcher"


def _append_flags(flags: list[dict], log_path: Path) -> None:
    """Read-only telemetry: appends any flags to the plain-text workspace
    log, never acts on them. See native_pipeline.flagging -- flags are
    visibility into whether 'trust the raw output' was warranted for this
    specific render, not a correction mechanism."""
    if not flags:
        return
    with open(log_path, "a", encoding="utf-8") as f:
        for flag in flags:
            f.write(f"FLAG: {flag}\n")


def run_vo_stage(
    ws: Workspace, payload_path: Path, url: str, log_path: Path,
    vo_mode: str = "break", beat_texts: list[str] | None = None,
) -> tuple[Path, list[Segment]]:
    """vo_mode selects which segment-derivation strategy matches the
    payload's own script-composition convention:
      - "break" (default): eleven_multilingual_v2/flash, beats joined by
        SSML <break> tags (elevenlabs_tooling.breaks.compose_break_tagged_text).
        Uses stitcher.vo_alignment.derive_segments.
      - "v3_tags": eleven_v3, beats joined by a blank line with bracket
        audio tags (elevenlabs_tooling.tags.compose_tagged_text). Uses
        stitcher.vo_alignment.derive_segments_v3, which additionally
        requires `beat_texts` (the exact per-beat strings, tag prefix
        included, that compose_tagged_text was given) to recover
        boundaries -- there is no <break> marker to split on.

    Fails loud on a mismatch rather than guessing.
    """
    if vo_mode not in ("break", "v3_tags"):
        raise VoModeMismatchError(f"vo_mode must be 'break' or 'v3_tags', got {vo_mode!r}")
    if vo_mode == "v3_tags" and not beat_texts:
        raise VoModeMismatchError(
            "vo_mode='v3_tags' requires beat_texts (derive_segments_v3 has "
            "no <break> marker to split on)"
        )

    audio_output = ws.asset("single_take.mp3")
    alignment_output = ws.asset("alignment.json")
    subprocess.run(
        [sys.executable, "-m", "elevenlabs_tooling", "generate-vo",
         "--payload", str(payload_path), "--url", url,
         "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
         "--force"],
        check=True,
        cwd=_ELEVENLABS_TOOLING_DIR,
    )
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    alignment = json.loads(alignment_output.read_text(encoding="utf-8"))
    if vo_mode == "v3_tags":
        segments = derive_segments_v3(payload["text"], alignment, beat_texts)
    else:
        segments = derive_segments(payload["text"], alignment)

    spans = [(segment.name, segment.at, segment.duration) for segment in segments]
    flags = flag_outliers(audio_output, spans, log_path)
    _append_flags(flags, log_path)

    return audio_output, segments


def run_music_stage(segments: list[Segment], bed_arc_path: Path, ws: Workspace, url: str, log_path: Path) -> Path:
    bed_arc = contracts.load_bed_arc(bed_arc_path)
    runtime = segments[-1].at + segments[-1].duration
    plan = music_plan.build_music_plan(bed_arc, runtime)

    plan_path = ws.asset("composition_plan.json")
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    bed_output = ws.asset("music_bed.mp3")
    subprocess.run(
        [sys.executable, "-m", "elevenlabs_tooling", "music", "send",
         "--payload", str(plan_path), "--url", url, "--output", str(bed_output), "--force"],
        check=True,
        cwd=_ELEVENLABS_TOOLING_DIR,
    )

    spans = [(m["label"], m["start_s"], m["end_s"] - m["start_s"]) for m in bed_arc]
    flags = flag_outliers(bed_output, spans, log_path)
    _append_flags(flags, log_path)

    return bed_output


def run_assemble_stage(
    ws: Workspace,
    segments: list[Segment],
    asset_manifest_path: Path,
    beat_texts: list[str],
    voice_take: Path,
    music_bed: Path,
    styles: dict,
    captions_style: str,
    log_path: Path,
) -> Path:
    asset_manifest = contracts.load_asset_manifest(asset_manifest_path)
    shots = build_shots(segments, asset_manifest)
    captions = derive_captions(segments, beat_texts)
    runtime = segments[-1].at + segments[-1].duration

    voice_lufs = measure_loudness(voice_take, log_path)["input_i"]
    assemble.check_bed_duration(music_bed, runtime, log_path)

    spec = assemble.assemble_spec(
        slug=ws.slug, shots=shots, captions=captions,
        voice_take=str(voice_take), music_bed=str(music_bed), runtime=runtime,
        voice_lufs=voice_lufs, styles=styles, captions_style=captions_style,
    )

    spec_path = ws.spec_path
    spec_path.write_text(json.dumps(spec.model_dump(by_alias=True, mode="json")), encoding="utf-8")
    return spec_path


def run_render_stage(slug: str, root: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "stitcher", "render", slug, "--root", str(root), "--mode", "final", "--force"],
        check=True,
        cwd=_STITCHER_DIR,
    )
