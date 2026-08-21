"""CLI entry point: `python -m native_pipeline render <slug> ...`

This is a separate entrypoint from stitcher's own `render` command, not a
new --mode value on it -- stitcher's --mode selects a rendering-quality
variant (final vs draft), threaded into cache keys and workspace paths
throughout audio.py/shots.py/assemble.py. This mode is an alternate
upstream construction path that produces a render-spec.json BEFORE
stitcher's render command ever runs; the two are separate subprocess
invocations (see orchestrate.run_render_stage).

Every path-bearing argument below is resolved to absolute
(`Path(...).resolve()`) before it is used to construct the `Workspace` or
passed into any `orchestrate.run_*_stage` call. orchestrate.py's own
subprocess calls run with `cwd=<sibling-package-dir>` (elevenlabs-tooling
or stitcher's own root), which differs from wherever this CLI itself was
invoked from -- so a relative path handed to those subprocesses would
resolve against the wrong directory. `.resolve()` anchors every such path
against this process's actual cwd at invocation time (a no-op for paths
already absolute), which is the only correct anchor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from stitcher.naming import Workspace
from stitcher.spec import Style

from native_pipeline import contracts, orchestrate

# Distinct from the stage-related exit codes stitcher's own CLI uses
# (EXIT_PREFLIGHT=1, EXIT_RENDER=2, ...) -- this one is native_pipeline's
# own CLI reporting a bad *input* to itself, before any stage (and before
# either billed API call) ever runs. Matches elevenlabs_tooling.cli's
# EXIT_USAGE=2 convention for the same kind of failure.
EXIT_USAGE = 2


def cmd_render(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    vo_payload = Path(args.vo_payload).resolve()
    bed_arc = Path(args.bed_arc).resolve()
    asset_manifest = Path(args.asset_manifest).resolve()
    beat_texts_path = Path(args.beat_texts).resolve()
    styles_path = Path(args.styles).resolve()

    # Pure, structural input validation -- deliberately hoisted ahead of
    # run_vo_stage/run_music_stage, which are real, billed API calls. A
    # malformed --beat-texts/--styles file or an invalid --asset-manifest
    # must be caught here, before either billed generation runs, not after.
    # The beat-name-vs-segments cross-check inside build_shots still can't
    # happen until real VO segments exist, so it stays where it is (inside
    # run_assemble_stage); this only covers what's checkable from the raw
    # input files alone.
    try:
        beat_texts = json.loads(beat_texts_path.read_text(encoding="utf-8"))
        if not isinstance(beat_texts, list) or not all(isinstance(t, str) for t in beat_texts):
            raise ValueError(f"--beat-texts must be a JSON list of strings: {beat_texts_path}")

        raw_styles = json.loads(styles_path.read_text(encoding="utf-8"))
        if not isinstance(raw_styles, dict):
            raise ValueError(f"--styles must be a JSON object of name -> style fields: {styles_path}")
        styles = {name: Style(**fields) for name, fields in raw_styles.items()}

        # Validates the asset manifest's own structure (kind/motion/
        # source_in_s/source_out_s requirements) independent of the real VO
        # segments, which don't exist yet at this point. run_assemble_stage
        # loads this same file again later (Task 9's existing code, left
        # untouched) -- cheap, redundant JSON parsing, not a real cost.
        contracts.load_asset_manifest(asset_manifest)
    except (OSError, ValueError, TypeError) as exc:
        print(f"native_pipeline: invalid input: {exc}", file=sys.stderr)
        return EXIT_USAGE

    vo_beat_texts = None
    if args.vo_mode == "v3_tags":
        if not args.vo_beat_texts:
            print("native_pipeline: --vo-beat-texts is required when --vo-mode v3_tags",
                  file=sys.stderr)
            return EXIT_USAGE
        vo_beat_texts_path = Path(args.vo_beat_texts).resolve()
        try:
            vo_beat_texts = json.loads(vo_beat_texts_path.read_text(encoding="utf-8"))
            if not isinstance(vo_beat_texts, list) or not all(isinstance(t, str) for t in vo_beat_texts):
                raise ValueError(f"--vo-beat-texts must be a JSON list of strings: {vo_beat_texts_path}")
        except (OSError, ValueError) as exc:
            print(f"native_pipeline: invalid input: {exc}", file=sys.stderr)
            return EXIT_USAGE

    ws = Workspace(root=root, slug=args.slug, mode="final")
    ws.ensure_dirs()
    log_path = ws.log_path("native")

    voice_take, segments = orchestrate.run_vo_stage(
        ws, vo_payload, args.vo_url, log_path,
        vo_mode=args.vo_mode, beat_texts=vo_beat_texts,
    )
    music_bed = orchestrate.run_music_stage(segments, bed_arc, ws, args.music_url, log_path)

    orchestrate.run_assemble_stage(
        ws, segments, asset_manifest, beat_texts,
        voice_take, music_bed, styles, args.captions_style, log_path,
    )
    orchestrate.run_render_stage(args.slug, root)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m native_pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    render_parser = subparsers.add_parser("render", help="Run the full native single-generation pipeline")
    render_parser.add_argument("slug")
    render_parser.add_argument("--root", required=True)
    render_parser.add_argument("--vo-payload", required=True)
    render_parser.add_argument("--vo-url", required=True)
    render_parser.add_argument("--bed-arc", required=True)
    render_parser.add_argument("--music-url", required=True)
    render_parser.add_argument("--asset-manifest", required=True)
    render_parser.add_argument("--beat-texts", required=True)
    render_parser.add_argument("--styles", required=True)
    render_parser.add_argument("--captions-style", required=True)
    render_parser.add_argument("--vo-mode", choices=["break", "v3_tags"], default="break")
    render_parser.add_argument(
        "--vo-beat-texts",
        help="Path to a JSON list of the exact per-beat strings (tag prefix "
        "included) submitted to eleven_v3 -- required when --vo-mode v3_tags",
    )
    render_parser.set_defaults(func=cmd_render)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
