# stitcher/stitcher/verify.py
"""Stage F: measure the render and report, never assert without evidence.

Checks that depend on work/ artifacts report UNAVAILABLE when those artifacts
are gone rather than silently passing, which is what distinguishes "could not
fully verify" (exit 4) from "verified and failed" (exit 3).

Three measurement choices here are load-bearing, not stylistic (spec §4
stage F):

1. Duck depth differences the two bed intermediates (04a_bed_conformed.wav,
   04b_bed_ducked.wav) over identical windows, never ducked-inside-voice
   against ducked-outside-voice. The naive comparison measures the envelope
   PLUS the music's own dynamics, which routinely swing past the 1.5 dB
   tolerance and would false-fail a correct render. Ramp regions (the
   attack/release either side of a voice span) are excluded from the
   windows, and windows shorter than MIN_DUCK_WINDOW_S are skipped outright:
   verified empirically against the real 9.0 binary that an ebur128 window
   below its ~400ms gating block reports a meaningless "I: -70.0 LUFS" floor
   rather than a real measurement, so a sub-400ms window would silently
   corrupt the comparison rather than just being imprecise. What each window
   is compared AGAINST comes from the same shifted breakpoints stage C
   rendered, never from the constant duck_db - gain_db -- see duck_windows().
2. True peak is measured on 06_mix_final.wav, before AAC encoding, not on
   the master. AAC decode can overshoot its input by 0.3-1 dB, so a mix
   correctly normalized to -1.5 dBTP would spuriously fail if measured on
   the master.
3. Timeline integrity allows one frame of slack. AAC priming and padding
   shift container duration by 20-45ms; zero tolerance would fail every
   correct render.

Frame checksums are deliberately absent -- libx264 output varies by build
and thread count, so a checksum produces false failures rather than
evidence. Do not add one.
"""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

from . import envelope, ffmpeg
from .naming import Workspace
from .overlays import bbox_within
from .spec import RenderSpec, runtime_seconds, shot_frame_bounds

LOUDNESS_TOLERANCE_LU = 1.0
DUCK_TOLERANCE_DB = 1.5
MIN_DUCK_WINDOW_S = 0.4
AAC_PADDING_SLACK_S = 0.05

# ebur128 reports a flat "I: -70.0 LUFS" for anything at or below its gating
# floor, so a window the envelope pushes down there yields no measurement at
# all -- not a small one. The margin keeps a window that merely approaches the
# floor out of the comparison too, since its reading is already dominated by
# the floor rather than by the envelope.
EBUR128_FLOOR_DB = -70.0
FLOOR_MARGIN_DB = 10.0

# How flat a sub-window must be, end to end, for a single expected value to be
# comparable against one integrated measurement of it. A fade (or any other
# ramp) crossing a voice span exceeds this and is excluded, exactly as the
# duck's own attack/release ramps already are.
FLAT_ENVELOPE_TOLERANCE_DB = 0.5

PASS = "pass"
FAIL = "fail"
UNAVAILABLE = "unavailable"

# Leads the preview_audio check's detail when the mix IS a preview, and is what
# write_reports keys the report banner off. A preview passes its checks by
# design (spec goal 6 needs the draft to render), so "pass" alone would be an
# invisible downgrade -- the banner is what stops a preview reading as a
# conforming render at a glance.
PREVIEW_BANNER = "PREVIEW AUDIO"


@dataclass
class Check:
    name: str
    status: str
    detail: str


def overall_status(checks: list[Check]) -> str:
    if any(check.status == FAIL for check in checks):
        return "fail"
    if any(check.status == UNAVAILABLE for check in checks):
        return "incomplete"
    return "pass"


# Same pattern as ffmpeg._I, and for the same reason: a window ebur128 reports
# as -inf is a reading, not a parse failure. duck_windows' own floor guards
# then discard it, which is the honest outcome -- previously it raised out of
# the whole verification pass instead.
_WINDOW_I = re.compile(rf"^\s*I:\s*({ffmpeg.EBUR128_NUMBER})\s*LUFS", re.MULTILINE)


def load_audio_record(ws: Workspace) -> dict | None:
    """Stage C's own account of what it built, or None if it is not there.

    Stage F cannot infer "the bed was deliberately omitted in draft" from the
    filesystem: an absent 04a/04b pair looks identical whether stage C chose
    not to build a bed or `stitcher clean` removed it afterwards. Only stage C
    knows which, so it says so in writing (spec §6) and this reads it back.
    """
    path = ws.audio_report_path
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def _omitted_files(record: dict | None) -> set[str]:
    if not record:
        return set()
    return {entry.get("file") for entry in record.get("omitted", [])}


def measure_window(path: Path, start: float, duration: float, log_path: Path) -> float:
    """Integrated loudness over one window of a file.

    Input-seeking (-ss/-t before -i) rather than output-seeking: verified
    against the real 9.0 binary on a PCM WAV that this lands sample-accurate
    windows and still produces the ebur128 "Summary:" block with its I: line
    at true line-start, matching ffmpeg.measure_loudness's own regex
    approach.
    """
    stderr = ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{start:.6f}",
         "-t", f"{duration:.6f}", "-i", str(path),
         "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
        log_path,
    )
    matches = _WINDOW_I.findall(stderr)
    if not matches:
        raise ffmpeg.FFmpegError(f"no integrated loudness in window of {path}")
    return float(matches[-1])


def _check_container(spec: RenderSpec, probed: ffmpeg.ProbeResult) -> Check:
    problems = []
    if (probed.width, probed.height) != (spec.canvas.width, spec.canvas.height):
        problems.append(f"resolution {probed.width}x{probed.height}")
    if probed.fps is None or abs(probed.fps - spec.canvas.fps) > 0.01:
        problems.append(f"fps {probed.fps}")
    if probed.pix_fmt != spec.delivery.pix_fmt:
        problems.append(f"pix_fmt {probed.pix_fmt}")
    if probed.video_codec != "h264":
        problems.append(f"video codec {probed.video_codec}")
    if probed.profile and probed.profile.lower() != spec.delivery.profile.lower():
        problems.append(f"profile {probed.profile}")
    detail = (
        f"{probed.width}x{probed.height} @ {probed.fps}fps, {probed.pix_fmt}, "
        f"{probed.video_codec}"
    )
    return Check("container", FAIL if problems else PASS,
                 "; ".join(problems) if problems else detail)


def _check_audio_stream(spec: RenderSpec, probed: ffmpeg.ProbeResult) -> Check:
    problems = []
    if probed.audio_codec != "aac":
        problems.append(f"audio codec {probed.audio_codec}")
    if probed.sample_rate != spec.delivery.audio_rate:
        problems.append(f"sample rate {probed.sample_rate}")
    return Check(
        "audio_stream", FAIL if problems else PASS,
        "; ".join(problems) if problems else f"{probed.audio_codec} @ {probed.sample_rate}Hz",
    )


def _check_colour_tagging(probed: ffmpeg.ProbeResult) -> Check:
    """Design spec line 503: "colorspace/primaries/trc != bt709" -- gates on
    all three ffprobe-visible fields, not colorspace alone. Verified against
    the real 9.0 binary: colour tags applied only as output-level flags
    (-colorspace/-color_primaries/-color_trc) do NOT reliably surface as
    color_primaries/color_transfer in `ffprobe -show_streams` (only
    color_space landed); the frame-level `setparams` filter stage A actually
    uses is what lands all three. A file probed with only colour_space set
    genuinely has incomplete tagging by this gate's own observable, so it
    must fail here too, not silently pass on one field out of three.
    """
    fields = (probed.colorspace, probed.color_primaries, probed.color_transfer)
    ok = all(field == "bt709" for field in fields)
    return Check(
        "colour_tagging", PASS if ok else FAIL,
        f"colorspace={probed.colorspace!r}, primaries={probed.color_primaries!r}, "
        f"transfer={probed.color_transfer!r}",
    )


def duck_windows(
    shifted: list[envelope.Breakpoint],
    spans: list[tuple[float, float]],
    attack: float,
) -> list[tuple[float, float, float]]:
    """(start, length, expected_db) for every comparable sub-window.

    The expectation is read off the SAME shifted breakpoints stage C rendered
    (audio.py `_build_bed`), never off the constant `duck_db - gain_db`. Those
    two agree only when nothing but the duck is acting: design spec §3 gives an
    explicit `bed.windows` entry precedence over the duck outright ("bed held
    out entirely for 0-3s while the child speaks"), and `bed.fades` attenuate
    on top of whatever is underneath. Against the constant, either of those
    turns a perfectly correct render into a duck_depth FAIL -- for the spec's
    own canonical example, by roughly 48 dB.

    Each voice span is therefore cut at every breakpoint that falls inside it,
    so each sub-window is one linear segment of the envelope, and only the
    segments the envelope holds flat across their whole length are kept: an
    integrated measurement of a ramp is not comparable to any single value.
    The duck's own attack ramp is excluded the same way it always was, by
    starting the first sub-window at `span start + attack`.
    """
    edges = sorted({point.t for point in shifted})
    windows: list[tuple[float, float, float]] = []
    for start, end in spans:
        first = start + attack
        cuts = [first] + [t for t in edges if first < t < end] + [end]
        for left, right in zip(cuts, cuts[1:]):
            if right - left < MIN_DUCK_WINDOW_S:
                continue
            low = envelope.level_at(shifted, left)
            high = envelope.level_at(shifted, right)
            if abs(high - low) > FLAT_ENVELOPE_TOLERANCE_DB:
                continue
            windows.append((left, right - left, (low + high) / 2))
    return windows


def _check_duck(
    spec: RenderSpec, ws: Workspace, log_path: Path, record: dict | None
) -> Check:
    conformed = ws.audio_step("04a", "bed_conformed")
    ducked = ws.audio_step("04b", "bed_ducked")
    if not spec.audio.bed:
        return Check("duck_depth", PASS, "no music bed in this spec")
    if spec.audio.bed.file in _omitted_files(record):
        # Spec §6: "A missing music bed or SFX file is simply omitted in
        # draft." There is no envelope because there is no bed, which is a
        # correct draft mix rather than an unverifiable one -- so this must
        # not block promotion. Before this branch existed, a draft with a
        # missing bed reported UNAVAILABLE with a diagnosis ("run with an
        # intact work/ directory") that was actively wrong: work/ was intact,
        # and the run exited 4 having produced no deliverable at all.
        return Check("duck_depth", PASS,
                     f"no music bed in this mix; {spec.audio.bed.file} was omitted "
                     "from the draft (see audio_omissions)")
    if not (conformed.is_file() and ducked.is_file()):
        return Check("duck_depth", UNAVAILABLE,
                     "bed intermediates absent; run with an intact work/ directory")

    bed = spec.audio.bed
    attack = bed.duck_attack_ms / 1000.0

    durations = {stem.file: stem.duration_s for stem in spec.audio.stems
                 if stem.duration_s is not None}
    for stem in spec.audio.stems:
        source = ws.asset(stem.file)
        if source.is_file():
            durations[stem.file] = ffmpeg.probe(source).duration

    try:
        spans = envelope.stem_spans(spec.audio.stems, durations)
    except ValueError as exc:
        # A stem whose file is gone and which declares no duration_s: report
        # rather than crash the whole verification pass.
        return Check("duck_depth", UNAVAILABLE, f"stem durations unknown: {exc}")

    points = envelope.build_breakpoints(bed, spans, runtime_seconds(spec))
    shifted = [
        envelope.Breakpoint(point.t, point.db - bed.gain_db) for point in points
    ]

    worst: tuple[float, float] | None = None   # (expected, measured)
    unmeasurable = 0
    for start, length, expected in duck_windows(shifted, spans, attack):
        # A window the envelope silences (design spec's `mode: "out"`) is not
        # a window that measures -100 dB; it is a window ebur128 cannot report
        # on at all. Skipping it is the only honest reading -- comparing the
        # floor against the expectation would fail every correct hold-out.
        if expected + bed.gain_db <= envelope.SILENCE_DB + 1.0:
            unmeasurable += 1
            continue
        base = measure_window(conformed, start, length, log_path)
        if base + expected <= EBUR128_FLOOR_DB + FLOOR_MARGIN_DB:
            unmeasurable += 1
            continue
        measured = measure_window(ducked, start, length, log_path) - base
        if worst is None or abs(measured - expected) > abs(worst[1] - worst[0]):
            worst = (expected, measured)

    if worst is None:
        detail = (
            f"{unmeasurable} window(s) sit at or below ebur128's "
            f"{EBUR128_FLOOR_DB:.0f} dB floor and nothing else is long enough "
            "to measure outside the ramps"
            if unmeasurable
            else "no voice span long enough to measure outside the ramps"
        )
        return Check("duck_depth", UNAVAILABLE, detail)

    expected, measured = worst
    ok = abs(measured - expected) <= DUCK_TOLERANCE_DB
    skipped = f", {unmeasurable} window(s) below the measurement floor" if unmeasurable else ""
    return Check(
        "duck_depth", PASS if ok else FAIL,
        f"expected {expected:.1f} dB, worst measured {measured:.1f} dB "
        f"(tolerance {DUCK_TOLERANCE_DB} dB){skipped}",
    )


def _check_safe_zone(spec: RenderSpec, ws: Workspace) -> Check:
    sidecars = sorted(ws.overlays_dir.glob("*.json"))
    if not sidecars:
        if not spec.overlays:
            return Check("safe_zone", PASS, "no overlays in this spec")
        return Check("safe_zone", UNAVAILABLE,
                     "overlay bbox sidecars absent; run with an intact work/ directory")

    escaped = []
    for sidecar in sidecars:
        bbox = tuple(json.loads(sidecar.read_text(encoding="utf-8"))["bbox"])
        if not bbox_within(bbox, spec.safe_zone):
            escaped.append(f"{sidecar.stem} {bbox}")
    return Check("safe_zone", FAIL if escaped else PASS,
                 "; ".join(escaped) if escaped else f"{len(sidecars)} overlays inside")


def _check_linearity(ws: Workspace, preview: bool) -> Check:
    record = ws.work_dir / "loudnorm_pass2.json"
    if not record.is_file():
        return Check("loudnorm_linearity", UNAVAILABLE,
                     "loudnorm pass 2 record absent; run with an intact work/ directory")
    kind = json.loads(record.read_text(encoding="utf-8")).get("normalization_type")
    if preview:
        # Reported, not gated. Linearity is what makes the voice-relative
        # solve deterministic; a preview has no such solve, so a `dynamic`
        # fallback here is a property of the preview rather than a defect.
        # The measured value is still printed -- nothing is hidden -- and the
        # preview_audio check states outright that this is not a conforming
        # mix.
        return Check("loudnorm_linearity", PASS,
                     f"normalization_type = {kind!r}; not gated (preview audio)")
    return Check("loudnorm_linearity", PASS if kind == "linear" else FAIL,
                 f"normalization_type = {kind!r}")


def _check_preview_audio(record: dict | None) -> Check:
    """States, in the report itself, that a preview is not a conforming mix.

    Spec goal 6 wants a draft renderable before any VO exists, and spec §6
    already synthesizes a missing stem as silence -- so a draft whose voice
    track is entirely silence is an intended state, not an error. But it is a
    state in which the entire voice-relative dB model is void, so the report
    has to say so out loud rather than pass quietly: the point of this check
    is that nobody can mistake a preview for a conforming render.
    """
    if record is None:
        return Check("preview_audio", UNAVAILABLE,
                     "stage C's audio record is absent; whether this mix is a "
                     "preview cannot be established")
    if not record.get("preview_audio"):
        reference = record.get("voice_reference_lufs")
        measured = f"{reference:.1f} LUFS" if isinstance(reference, (int, float)) \
            else "unrecorded"
        return Check("preview_audio", PASS,
                     f"no; the mix is levelled against a voice reference of {measured}")
    return Check("preview_audio", PASS, PREVIEW_BANNER + " — the assembled voice "
                 "track is digital silence, so there is no voice reference: the bed "
                 "was mixed at its literal gain_db, and the loudness target and the "
                 "loudnorm linearity gate were reported but not enforced. Draft only "
                 "— this is a pacing/legibility preview, not a conforming mix.")


def _check_placeholders(ws: Workspace) -> Check:
    """Design spec line 536 names placeholder detection among the checks that
    report `unavailable` when their work/ artifacts are absent.

    An empty glob on a cleaned workspace is not evidence that no placeholder
    was used; it is the absence of evidence either way. Reporting PASS there
    would be an assertion nothing measured -- the same class of defect as
    ProbeResult's colour fields defaulting to the passing value.
    """
    if not ws.work_dir.is_dir():
        return Check("placeholders", UNAVAILABLE,
                     "work/ directory absent; placeholder use cannot be established")

    found = sorted((ws.work_dir / "placeholders").glob("*.png")) \
        if (ws.work_dir / "placeholders").is_dir() else []
    if not found:
        return Check("placeholders", PASS, "none")
    names = ", ".join(path.stem for path in found)
    status = FAIL if ws.mode == "final" else PASS
    return Check("placeholders", status, f"{len(found)} placeholder(s): {names}")


def _check_audio_omissions(ws: Workspace, record: dict | None) -> Check:
    """Spec §6: a bed or SFX file omitted in draft is "listed as omitted in
    the QA report". Nothing did that before this check existed.

    Deliberately a SIBLING of `placeholders` rather than an extension of it,
    for three reasons. A placeholder is a substitution -- a magenta slate that
    is present in the output and visible in the frame -- whereas an omission
    is content that is simply not there, so folding them together would make
    one detail string mean two different things. `placeholders` reads a
    directory of PNGs that stage A wrote; this reads stage C's record, a
    different artifact with a different absence story. And spec §4 stage F
    tabulates its checks one row per observable, so a second observable earns
    a second row.

    A stem synthesized as silence is reported here too, under its own label:
    §6 treats it as the audio analogue of a placeholder (a substitution with a
    known duration), not as an omission, and conflating the two would hide
    which half of §6's draft contract actually fired.
    """
    if record is None:
        return Check("audio_omissions", UNAVAILABLE,
                     "stage C's audio record is absent; what the mix left out "
                     "cannot be established")

    omitted = record.get("omitted", [])
    silent = record.get("silent_stems", [])
    if not omitted and not silent:
        return Check("audio_omissions", PASS, "none")

    parts = []
    if omitted:
        parts.append("omitted: " + ", ".join(
            f"{entry.get('file')} ({entry.get('role')})" for entry in omitted
        ))
    if silent:
        parts.append("synthesized as silence: " + ", ".join(silent))
    # Unreachable through preflight, which aborts a final run on any missing
    # audio file -- but stated rather than assumed, exactly as `placeholders`
    # states it: an omission that somehow reached a final render is a defect,
    # not a pass.
    status = FAIL if ws.mode == "final" else PASS
    return Check("audio_omissions", status, "; ".join(parts))


def contact_sheet(
    spec: RenderSpec, master: Path, out_png: Path, log_path: Path
) -> Path | None:
    """One frame from each shot's midpoint, tiled. Informational only.

    The per-shot frames are scratch, so they go in a real temporary directory
    that is removed on the way out -- including when a frame extraction
    raises, which is a reachable path (cli.py rolls a contact-sheet failure
    back). They used to be written to `out_png.parent / "_contact"`, i.e.
    straight into the DELIVERABLES directory, and were never removed: spec §2
    makes out/ versioned deliverables only and names work/ and logs/ as the
    safe-to-delete directories, and `stitcher clean` removes only work/ -- so
    every successful render left an out/_contact/ behind. Those frames also
    survived across runs, so a later spec with fewer shots left orphans the
    next contact sheet could pick up.

    Each frame is opened inside a `with` block and converted to a fresh
    in-memory image before the block exits. On Windows an Image still holding
    its file handle would keep a lock on the frame and make the directory
    removal below fail, so the handles are closed explicitly rather than left
    to the garbage collector.
    """
    frames: list[Image.Image] = []
    with tempfile.TemporaryDirectory(prefix="stitcher-contact-") as scratch:
        temp_dir = Path(scratch)
        for index, shot in enumerate(spec.shots, start=1):
            midpoint = (shot.start + shot.end) / 2
            frame = temp_dir / f"{index:03d}.png"
            ffmpeg.run(
                ["ffmpeg", "-hide_banner", "-y", "-ss", f"{midpoint:.3f}",
                 "-i", str(master), "-frames:v", "1", "-update", "1",
                 "-vf", "scale=216:384", str(frame)],
                log_path,
            )
            if frame.is_file():
                with Image.open(frame) as opened:
                    frames.append(opened.convert("RGB"))
    if not frames:
        return None

    columns = min(5, len(frames))
    rows = (len(frames) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 216, rows * 384), (0, 0, 0))
    for position, frame in enumerate(frames):
        sheet.paste(frame, ((position % columns) * 216, (position // columns) * 384))
    sheet.save(out_png)
    return out_png


def verify(
    spec: RenderSpec, ws: Workspace, master: Path, log_path: Path
) -> list[Check]:
    record = load_audio_record(ws)
    preview = bool(record and record.get("preview_audio"))
    probed = ffmpeg.probe(master)
    checks = [_check_container(spec, probed), _check_audio_stream(spec, probed)]
    checks.append(_check_colour_tagging(probed))

    integrated = ffmpeg.measure_loudness(master, log_path)["input_i"]
    target = spec.audio.loudness.integrated_lufs
    if preview:
        # Reported, not gated, for the same reason as loudnorm_linearity: the
        # target is a level for a mix built around a voice, and a preview has
        # no voice. A bed-less preview is digital silence end to end and would
        # measure the -70 LUFS floor here -- failing QA, blocking promotion,
        # and defeating spec goal 6 outright.
        checks.append(Check("integrated_loudness", PASS,
                            f"{integrated:.1f} LUFS against a target of {target} LUFS; "
                            "not gated (preview audio)"))
    else:
        loud_ok = abs(integrated - target) <= LOUDNESS_TOLERANCE_LU
        checks.append(Check("integrated_loudness", PASS if loud_ok else FAIL,
                            f"{integrated:.1f} LUFS against a target of {target} LUFS"))

    mix = ws.audio_step("06", "mix_final")
    if mix.is_file():
        # Measured pre-AAC: the codec can overshoot its input by 0.3-1 dB.
        peak = ffmpeg.measure_loudness(mix, log_path)["input_tp"]
        peak_ok = peak <= spec.audio.loudness.true_peak_dbtp + 1e-6
        checks.append(Check("true_peak", PASS if peak_ok else FAIL,
                            f"{peak:.1f} dBTP against a ceiling of "
                            f"{spec.audio.loudness.true_peak_dbtp} dBTP"))
    else:
        checks.append(Check("true_peak", UNAVAILABLE,
                            "06_mix_final.wav absent; true peak cannot be measured pre-AAC"))

    # true_peak is deliberately still gated in preview: "do not hand back
    # something that clips" means the same thing with or without a voice, and
    # a blanket bypass is exactly what preview mode must not become.
    checks.append(_check_linearity(ws, preview))
    checks.append(_check_duck(spec, ws, log_path, record))
    checks.append(_check_safe_zone(spec, ws))

    # Difference the bounds rather than reading the last END frame: the two
    # agree only when the timeline starts at 0. validate_spec now requires
    # that, but this check exists to measure what was rendered, so it must not
    # depend on the thing it is checking -- the rendered master is the concat
    # of the shot clips, whose length is the SPAN of the bounds.
    bounds = shot_frame_bounds(spec)
    total_frames = bounds[-1][1] - bounds[0][0]
    expected_seconds = total_frames / spec.canvas.fps
    # One frame is 33ms at 30fps, but AAC priming/padding can shift container
    # duration by up to ~45ms -- so the floor is whichever is larger.
    slack = max(1.0 / spec.canvas.fps, AAC_PADDING_SLACK_S)
    timeline_ok = abs(probed.duration - expected_seconds) <= slack
    checks.append(Check(
        "timeline_integrity", PASS if timeline_ok else FAIL,
        f"container {probed.duration:.3f}s against {expected_seconds:.3f}s "
        f"({total_frames} frames), slack {slack * 1000:.0f}ms",
    ))

    checks.append(_check_placeholders(ws))
    checks.append(_check_audio_omissions(ws, record))
    checks.append(_check_preview_audio(record))
    return checks


def is_preview_audio(checks: list[Check]) -> bool:
    """Whether this check set describes a preview mix, for report banners."""
    return any(
        check.name == "preview_audio" and check.detail.startswith(PREVIEW_BANNER)
        for check in checks
    )


def write_reports(checks: list[Check], json_path: Path, md_path: Path) -> None:
    status = overall_status(checks)
    preview = is_preview_audio(checks)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(
            {"status": status, "preview_audio": preview,
             "checks": [asdict(c) for c in checks]},
            indent=2,
        ),
        encoding="utf-8",
    )

    symbols = {PASS: "PASS", FAIL: "FAIL", UNAVAILABLE: "N/A "}
    lines = [f"# QA report — {status.upper()}", ""]
    if preview:
        # Above the table, not buried in a row: a preview passes by design, so
        # the one thing a reader must not miss is that it passed as a preview.
        lines += [
            f"> **{PREVIEW_BANNER}** — the voice track is silent, so this mix "
            "was not levelled against a voice reference and its loudness "
            "target and linearity were reported rather than enforced. Preview "
            "the pacing and the cards from it; do not publish it.",
            "",
        ]
    lines += ["| Check | Result | Detail |", "|---|---|---|"]
    lines += [
        f"| `{check.name}` | {symbols[check.status]} | {check.detail} |"
        for check in checks
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
