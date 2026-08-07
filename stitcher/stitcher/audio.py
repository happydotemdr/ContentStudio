# stitcher/stitcher/audio.py
"""Stage C: stem placement, ducking, and two-pass loudness normalization.

04a_bed_conformed.wav exists solely so stage F can measure the envelope in
isolation: once voice and bed are summed they cannot be separated, so duck
depth is verified by differencing the two bed intermediates (spec §4 stage F).

Two assertions this stage makes about real FFmpeg behaviour rather than
assuming (spec §4 stage C), both verified against the installed 9.0 binary:

1. `loudnorm` resamples its working stream to 192 kHz internally. Confirmed
   with `ffprobe` on a pass-2 output written WITHOUT a trailing resample:
   the file came back as 192000 Hz even though the input was 48000 Hz.
   An explicit `aresample=48000` placed AFTER `loudnorm` in the same `-af`
   chain (never before, and never as a separate command) is mandatory on
   every pass-2 run, or the mix silently ships at 192 kHz.

2. `linear=true` silently falls back to dynamic mode when the requested
   linear gain would be unsafe to apply as a flat multiply -- and this
   fallback fires more often than "true-peak limiting is required" alone
   would suggest. Confirmed with a plain 440Hz sine tone (zero measured
   LRA): even with generous true-peak headroom (measured TP well below
   target TP after the required gain), pass 2 still reported
   `normalization_type: dynamic`. Only a signal with actual loudness-range
   variation (a synthetic loud/quiet alternating tone, LRA ~3) produced
   `normalization_type: linear`. Since this stage's determinism guarantee
   depends on linear mode, pass 2's reported `normalization_type` is
   checked and a fallback is treated as a hard failure rather than a
   silently-accepted approximation.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import envelope, ffmpeg
from .naming import Workspace
from .spec import RenderSpec, runtime_seconds

LRA_TARGET = 11.0

# Deviation from the plan's regex (see task-10-report.md for detail): the
# plan anchored the match to the end of the string (`\s*$`), reasoning that
# loudnorm's JSON block is the last thing ffmpeg writes to stderr. Verified
# against the real 9.0 binary that this is false even with `-nostats`: ffmpeg
# always appends a muxer summary line (and, on file outputs, a final
# size/time/bitrate/speed line) AFTER the JSON block, so the anchored
# pattern never matches real stderr -- only the tests' synthetic strings,
# which happen to end right after the JSON. The un-anchored form below finds
# every brace-delimited object (loudnorm's JSON has no nested braces) and
# takes the last one, which is robust to whatever ffmpeg prints afterward.
_JSON_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


class LoudnormNotLinearError(RuntimeError):
    """loudnorm fell back to dynamic mode, voiding the determinism claim."""


class SilentVoiceError(RuntimeError):
    """The assembled voice track is digital silence outside draft mode.

    Every bed level in a spec is expressed relative to the MEASURED voice
    track (spec §4 stage C), so a silent voice leaves the whole dB model with
    no reference to solve against. Draft mode renders that as preview audio;
    final mode refuses, loudly, rather than shipping a mix whose levels were
    solved against ebur128's -70 LUFS floor artifact.
    """


@dataclass
class AudioResult:
    mix: Path
    bed_conformed: Path | None
    bed_ducked: Path | None
    voice_reference_lufs: float
    loudnorm: dict
    # What this stage left OUT, and why. Spec §6 requires a bed or SFX file
    # that draft mode omitted to be "listed as omitted in the QA report", and
    # stage F additionally has to tell a deliberate omission apart from a
    # cleaned work/ directory. Defaulted so an AudioResult built positionally
    # by an older caller stays valid.
    omitted: list[dict] = field(default_factory=list)
    silent_stems: list[str] = field(default_factory=list)


def audio_omissions(spec: RenderSpec, missing_audio: list[str]) -> tuple[list[dict], list[str]]:
    """(omitted bed/sfx, stems synthesized as silence) for this run.

    Spec §6 draws the line here, not at "missing audio": a stem that declares
    duration_s is SUBSTITUTED with silence and still occupies its slot in the
    timeline, while a bed or SFX file is simply dropped. They are different
    facts about the mix and the QA report reports them as such.
    """
    omitted: list[dict] = []
    if spec.audio.bed and spec.audio.bed.file in missing_audio:
        omitted.append({"file": spec.audio.bed.file, "role": "bed"})
    for item in spec.audio.sfx:
        if item.file in missing_audio:
            omitted.append({"file": item.file, "role": "sfx"})
    silent = [stem.file for stem in spec.audio.stems if stem.file in missing_audio]
    return omitted, silent


def parse_loudnorm_json(stderr: str) -> dict:
    matches = _JSON_RE.findall(stderr)
    if not matches:
        raise ffmpeg.FFmpegError(f"no loudnorm JSON found in output:\n{stderr[-2000:]}")
    return json.loads(matches[-1])


def _place_stems(
    spec: RenderSpec, ws: Workspace, log_path: Path, missing_audio: list[str]
) -> tuple[Path, dict[str, float]]:
    """Gain each stem, place it at its absolute time, and sum them."""
    inputs: list[str] = []
    chains: list[str] = []
    durations: dict[str, float] = {}

    for index, stem in enumerate(spec.audio.stems):
        source = ws.asset(stem.file)
        if stem.file in missing_audio:
            length = stem.duration_s or 0.0
            inputs += ["-f", "lavfi", "-t", f"{length:.6f}",
                       "-i", "anullsrc=r=48000:cl=stereo"]
        else:
            length = ffmpeg.probe(source).duration
            inputs += ["-i", str(source)]
        durations[stem.file] = length

        delay = int(round(stem.at * 1000))
        chains.append(
            f"[{index}:a]volume={stem.gain_db}dB,"
            f"adelay={delay}|{delay},aresample=48000[s{index}]"
        )

    labels = "".join(f"[s{i}]" for i in range(len(spec.audio.stems)))
    graph = ";".join(chains) + (
        f";{labels}amix=inputs={len(spec.audio.stems)}:normalize=0:"
        "dropout_transition=0[vo]"
    )

    target = ws.audio_step("03", "vo_assembled")
    ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-y", *inputs,
         "-filter_complex", graph, "-map", "[vo]",
         "-c:a", "pcm_s16le", "-ar", "48000", str(target)],
        log_path,
    )
    return target, durations


def _build_bed(
    spec: RenderSpec,
    ws: Workspace,
    runtime: float,
    voice_lufs: float,
    durations: dict[str, float],
    log_path: Path,
    preview: bool,
) -> tuple[Path, Path]:
    bed = spec.audio.bed
    source = ws.asset(bed.file)

    if preview:
        # No voice, so no reference: the relative solve is skipped outright
        # rather than fed ebur128's floor artifact, which would place the bed
        # (gain_db - 70) LUFS below its own level and render an inaudible
        # preview. The bed is mixed at its literal gain_db instead. The
        # envelope below still subtracts gain_db, so it lands relative to this
        # conformed level exactly as it does on a normal run and duck_depth
        # still measures the real envelope.
        conform_gain = bed.gain_db
    else:
        # Conform: trim/loop to runtime and shift so the bed sits gain_db
        # below the voice. Levels in the spec are voice-relative, never
        # absolute.
        measured = ffmpeg.measure_loudness(source, log_path)["input_i"]
        conform_gain = (voice_lufs + bed.gain_db) - measured

    conformed = ws.audio_step("04a", "bed_conformed")
    ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-y", "-stream_loop", "-1", "-i", str(source),
         "-t", f"{runtime:.6f}",
         "-af", f"volume={conform_gain:.1f}dB,aresample=48000",
         "-c:a", "pcm_s16le", "-ar", "48000", str(conformed)],
        log_path,
    )

    spans = envelope.stem_spans(spec.audio.stems, durations)
    breakpoints = envelope.build_breakpoints(bed, spans, runtime)
    # The envelope is voice-relative; conform already applied gain_db, so
    # subtract it here to avoid applying the baseline twice: at a baseline
    # breakpoint this nets to volume=0dB (already-conformed level stands),
    # and at a duck breakpoint it applies (duck_db - gain_db) on top of the
    # conformed level, landing exactly on duck_db relative to voice.
    shifted = [
        envelope.Breakpoint(point.t, point.db - bed.gain_db) for point in breakpoints
    ]
    expression = envelope.volume_expr(shifted)

    ducked = ws.audio_step("04b", "bed_ducked")
    ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-y", "-i", str(conformed),
         "-af", f"volume=volume='{expression}':eval=frame",
         "-c:a", "pcm_s16le", "-ar", "48000", str(ducked)],
        log_path,
    )
    return conformed, ducked


def build_audio(
    spec: RenderSpec,
    ws: Workspace,
    mode: str,
    log_path: Path,
    missing_audio: list[str],
) -> AudioResult:
    runtime = runtime_seconds(spec)
    voice, durations = _place_stems(spec, ws, log_path, missing_audio)
    voice_measured = ffmpeg.measure_loudness(voice, log_path)
    voice_lufs = voice_measured["input_i"]

    # PREVIEW MODE (spec goal 6: "preview pacing and card legibility BEFORE
    # spending Midjourney or ElevenLabs credits"). Spec §6 already provides
    # for every stem being synthesized as silence in draft, and validate_spec
    # rejects a zero-stem spec -- so a draft before any VO exists is the
    # intended authoring path, and it made 03_vo_assembled.wav digital
    # silence. There is then no voice reference, so the relative dB model has
    # nothing to be relative to and is bypassed rather than solved against
    # ebur128's floor. DRAFT ONLY: in final mode a silent voice is a loud
    # failure, never a silent downgrade.
    preview = ffmpeg.is_digital_silence(voice_measured)
    if preview and mode != "draft":
        raise SilentVoiceError(
            f"{voice.name} is digital silence "
            f"(integrated {voice_lufs} LUFS, true peak "
            f"{voice_measured['input_tp']} dBFS). Every bed level in this spec is "
            "expressed relative to the measured voice track, so there is no "
            "reference level to solve against. Supply real voice stems, or use "
            "--mode draft, which renders this as preview audio."
        )

    conformed = ducked = None
    if spec.audio.bed and spec.audio.bed.file not in missing_audio:
        conformed, ducked = _build_bed(
            spec, ws, runtime, voice_lufs, durations, log_path, preview
        )

    # Written BEFORE the loudnorm passes, not after: it is the only record of
    # what this stage chose to leave out, and stage F needs it even on a run
    # that dies later. See Workspace.audio_report_path for why it is durable
    # rather than passed in memory.
    omitted, silent_stems = audio_omissions(spec, missing_audio)
    ws.audio_report_path.parent.mkdir(parents=True, exist_ok=True)
    ws.audio_report_path.write_text(
        json.dumps(
            {
                "mode": mode,
                "preview_audio": preview,
                # None rather than a non-finite literal: json.dumps would
                # write bare `-Infinity`, which round-trips in Python but is
                # not valid JSON for anything else that reads this file.
                "voice_reference_lufs": (
                    voice_lufs if math.isfinite(voice_lufs) else None
                ),
                "bed_built": ducked is not None,
                "omitted": omitted,
                "silent_stems": silent_stems,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Sum voice, ducked bed, and sfx. Inputs are separate argv elements (never
    # embedded in the filtergraph string), and the graph itself refers to them
    # only by ffmpeg input index ([0:a], [1:a], ...) -- it never names a
    # filesystem path, so this stays inline rather than going through
    # -filter_complex_script.
    inputs = ["-i", str(voice)]
    chains = ["[0:a]anull[m0]"]
    count = 1
    if ducked:
        inputs += ["-i", str(ducked)]
        chains.append(f"[{count}:a]anull[m{count}]")
        count += 1
    for item in spec.audio.sfx:
        if item.file in missing_audio:
            continue
        inputs += ["-i", str(ws.asset(item.file))]
        delay = int(round(item.at * 1000))
        chains.append(
            f"[{count}:a]volume={item.gain_db}dB,adelay={delay}|{delay}[m{count}]"
        )
        count += 1

    # `apad` before `atrim` is what makes the mix exactly `runtime` long
    # rather than "at most runtime". atrim only ever SHORTENS: verified
    # against the real 9.0 binary that a 2.0s input through
    # `amix=inputs=1,atrim=0:6.0` comes back 2.000000s, not 6. A bed-less
    # spec (audio.bed is Optional and a supported shape) whose voice ends
    # before the last shot therefore produced a short mix, and stage D's
    # `-shortest` then truncated the VIDEO to it -- confirmed on the same
    # binary: 3.000000s of video plus 1s of audio muxes to a 1.000000s
    # master. With a bed present the bed already runs the full runtime, which
    # is why only the bed-less path could show this.
    # apad must be bounded at the source with whole_dur, not left bare and
    # relying on the downstream atrim to cut it off. Bare `apad` is
    # unbounded -- it is a generator, not a filter with a natural end -- so
    # atrim only ever discards the frames it produces past `runtime` rather
    # than signalling EOF upstream. ffmpeg can then spin generating and
    # discarding silence forever. Reproduced directly against the real 9.0
    # binary under subprocess.run(..., capture_output=True) (exactly how
    # ffmpeg.run invokes it): bare `apad` hung 1/10 (also seen 1/3 and 1/15
    # in other trials) on identical inputs, and adding `-t` instead did not
    # help (hung 3/15). `apad=whole_dur={runtime:.6f}` hung 0/15 with output
    # duration exactly `runtime` every time.
    labels = "".join(f"[m{i}]" for i in range(count))
    graph = ";".join(chains) + (
        f";{labels}amix=inputs={count}:normalize=0:dropout_transition=0,"
        f"apad=whole_dur={runtime:.6f},atrim=0:{runtime:.6f},aresample=48000[mix]"
    )

    pre = ws.audio_step("05", "mix_pre-loudnorm")
    ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-y", *inputs,
         "-filter_complex", graph, "-map", "[mix]",
         "-c:a", "pcm_s16le", "-ar", "48000", str(pre)],
        log_path,
    )

    loudness = spec.audio.loudness
    common = (
        f"I={loudness.integrated_lufs}:TP={loudness.true_peak_dbtp}:LRA={LRA_TARGET}"
    )

    pass1 = parse_loudnorm_json(
        ffmpeg.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", str(pre),
             "-af", f"loudnorm={common}:print_format=json", "-f", "null", "-"],
            log_path,
        )
    )
    (ws.audio_dir / "loudnorm_pass1.json").write_text(
        json.dumps(pass1, indent=2), encoding="utf-8"
    )

    final = ws.audio_step("06", "mix_final")
    measured = (
        f"measured_I={pass1['input_i']}:measured_TP={pass1['input_tp']}"
        f":measured_LRA={pass1['input_lra']}:measured_thresh={pass1['input_thresh']}"
        f":offset={pass1['target_offset']}:linear=true:print_format=json"
    )
    pass2 = parse_loudnorm_json(
        ffmpeg.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(pre),
             # aresample MUST follow loudnorm in this same -af chain: loudnorm
             # resamples internally to 192kHz (verified against ffmpeg 9.0;
             # see module docstring assertion 1), and a downstream resample
             # is the only way to land back on 48kHz.
             "-af", f"loudnorm={common}:{measured},aresample=48000",
             "-c:a", "pcm_s16le", "-ar", "48000", str(final)],
            log_path,
        )
    )

    (ws.work_dir / "loudnorm_pass2.json").write_text(
        json.dumps(pass2, indent=2), encoding="utf-8"
    )

    # Not gated in preview mode. The linearity guarantee is what makes the
    # voice-relative solve deterministic, and in preview there is no solve to
    # be deterministic about -- so a `dynamic` fallback here is a fact about a
    # preview, not a broken render. It is reported in the QA report either way
    # (verify's loudnorm_linearity check keeps printing the real value), and
    # the preview_audio check states plainly that the mix does not conform.
    if pass2.get("normalization_type") != "linear" and not preview:
        raise LoudnormNotLinearError(
            "loudnorm fell back to "
            f"{pass2.get('normalization_type')!r} mode instead of linear, which voids "
            "the determinism guarantee. Lower the true-peak target or reduce input "
            "level so limiting is not required."
        )

    return AudioResult(
        final, conformed, ducked, voice_lufs, pass2, omitted, silent_stems
    )
