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
from pathlib import Path

from stitcher.naming import Workspace
from stitcher.spec import Style

from native_pipeline import orchestrate


def cmd_render(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    vo_payload = Path(args.vo_payload).resolve()
    bed_arc = Path(args.bed_arc).resolve()
    asset_manifest = Path(args.asset_manifest).resolve()
    beat_texts_path = Path(args.beat_texts).resolve()
    styles_path = Path(args.styles).resolve()

    ws = Workspace(root=root, slug=args.slug, mode="final")
    ws.ensure_dirs()
    log_path = ws.log_path("native")

    voice_take, segments = orchestrate.run_vo_stage(ws, vo_payload, args.vo_url, log_path)
    music_bed = orchestrate.run_music_stage(segments, bed_arc, ws, args.music_url, log_path)

    beat_texts = json.loads(beat_texts_path.read_text(encoding="utf-8"))
    raw_styles = json.loads(styles_path.read_text(encoding="utf-8"))
    styles = {name: Style(**fields) for name, fields in raw_styles.items()}

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
    render_parser.set_defaults(func=cmd_render)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
