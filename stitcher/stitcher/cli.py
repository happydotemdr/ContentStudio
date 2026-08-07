# stitcher/stitcher/cli.py
"""Command dispatch and stage orchestration.

Stage D writes work/<mode>/master.mp4; only a clean stage-F pass promotes it
into out/ with a freshly allocated version, so a QA failure never consumes a
version number (spec §2 rule 5).

Ordering inside cmd_render is load-bearing: stage E and the reports run
BEFORE `shutil.move` promotes the master, and the move is the last thing that
happens. The move allocates a version number and is not undoable; every step
that can still fail therefore has to precede it, so a failure leaves the
master in work/ and no half-populated version in out/.

Deviation from the task-14 brief's sample code (see task-14-report.md for the
full reasoning): the brief's sample promoted the master into out/ whenever
verify's status was anything other than "fail", including "incomplete", and
only used the incomplete/fail distinction to pick the exit code afterward.
That contradicts spec §2 rule 5's own wording -- "only on a clean pass is it
promoted into out/" -- and the task brief's explicit "out/ contains only
outputs that actually met spec": an incomplete verification has not shown
that. Here, promotion requires status == "pass"; both "fail" and
"incomplete" leave the master in work/, write the QA report to logs/ (never
out/), and burn no version number. They differ only in exit code (3 vs 4)
and in the report's wording, which is exactly what "do not collapse them"
(task brief, "Things to watch") calls for.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import assemble, audio, derive, ffmpeg, preflight, shots, verify
from .cache import Manifest, file_digest, payload_digest
from .naming import Workspace
from .overlays import TextOverflowError, render_overlay
from .spec import RenderSpec, load_spec, validate_spec

EXIT_OK = 0
EXIT_PREFLIGHT = 1
EXIT_RENDER = 2
EXIT_QA = 3
EXIT_INCOMPLETE = 4

DEFAULT_ROOT = Path("renders")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def run_digest(spec: RenderSpec, ws: Workspace, mode: str, ffmpeg_build: str) -> str:
    """Everything that determines the whole run (spec §5)."""
    assets = sorted(
        {shot.source for shot in spec.shots}
        | {stem.file for stem in spec.audio.stems}
        | {item.file for item in spec.audio.sfx}
        | ({spec.audio.bed.file} if spec.audio.bed else set())
        | ({spec.cover.source} if spec.cover else set())
    )
    return payload_digest(
        spec.model_dump(by_alias=True),
        [file_digest(ws.asset(name)) for name in assets],
        [file_digest(Path(style.font_file)) for _, style in sorted(spec.styles.items())],
        ffmpeg_build,
        mode,
    )


def render_overlays(
    spec: RenderSpec, ws: Workspace, manifest: Manifest
) -> dict[str, Path]:
    """Stage B: one full-canvas RGBA PNG per overlay, content-hash cached."""
    rendered: dict[str, Path] = {}
    for index, overlay in enumerate(spec.overlays, start=1):
        style = spec.styles[overlay.style]
        target = ws.overlay_png(index, overlay.id, overlay.text)
        key = f"overlays/{index:03d}"
        digest = payload_digest(
            overlay.model_dump(by_alias=True),
            style.model_dump(),
            file_digest(Path(style.font_file)),
            spec.canvas.model_dump(),
        )
        if not manifest.is_fresh(key, digest, target):
            render_overlay(
                overlay.text, style, spec.canvas, overlay.anchor,
                overlay.offset_px, target,
            )
            manifest.set(key, digest)
        rendered[overlay.id] = target
    manifest.save()
    return rendered


def cmd_validate(spec_path: Path) -> int:
    try:
        spec, warnings = load_spec(spec_path)
    except (ValueError, OSError) as exc:
        print(f"spec is unusable:\n{exc}", file=sys.stderr)
        return EXIT_PREFLIGHT

    for warning in warnings:
        print(f"warning: {warning}")

    errors = validate_spec(spec)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return EXIT_PREFLIGHT
    print(f"{spec_path} is valid ({len(spec.shots)} shots, {len(spec.overlays)} overlays)")
    return EXIT_OK


def cmd_render(slug: str, root: Path, mode: str, force: bool) -> int:
    ws = Workspace(root=root, slug=slug, mode=mode)
    ws.ensure_dirs()
    log_path = ws.log_path(_timestamp())

    try:
        spec, warnings = load_spec(ws.spec_path)
    except (ValueError, OSError) as exc:
        print(f"spec is unusable:\n{exc}", file=sys.stderr)
        return EXIT_PREFLIGHT
    for warning in warnings:
        print(f"warning: {warning}")

    report = preflight.run_preflight(spec, ws, mode)
    for warning in report.warnings:
        print(f"warning: {warning}")
    if not report.ok:
        for error in report.errors:
            print(f"error: {error}", file=sys.stderr)
        return EXIT_PREFLIGHT

    manifest = Manifest.load(ws.manifest_path)
    digest = run_digest(spec, ws, mode, ffmpeg.ffmpeg_version())
    recorded_version = manifest.get("run/version")

    # Total-cache-hit rule (spec §5): every stage hitting cache is
    # represented here by the single aggregate run digest, since run_digest
    # already folds in every input (spec, every asset, every font, the
    # ffmpeg build, and the mode) that any stage could possibly depend on.
    # A matching digest plus a surviving out/ deliverable is exactly "an
    # existing out/ version was produced from an identical run digest" --
    # nothing changed, so report a no-op rather than re-encoding or minting
    # a version. --force bypasses this unconditionally.
    if not force and manifest.get("run") == digest and recorded_version:
        existing = ws.out_master(None if mode == "draft" else int(recorded_version))
        if existing.is_file():
            print(f"no changes; {existing.name} is current (use --force to re-render)")
            return EXIT_OK

    try:
        clips = shots.render_all(spec, ws, mode, manifest, log_path, report.missing_visual)
        overlay_pngs = render_overlays(spec, ws, manifest)
        mix = audio.build_audio(spec, ws, mode, log_path, report.missing_audio)
        master = assemble.assemble(
            spec, ws, mode, clips, overlay_pngs, mix.mix, log_path
        )
    except (ffmpeg.FFmpegError, TextOverflowError, audio.LoudnormNotLinearError) as exc:
        print(f"render failed: {exc}", file=sys.stderr)
        return EXIT_RENDER

    checks = verify.verify(spec, ws, master, log_path)
    status = verify.overall_status(checks)

    if status != "pass":
        # Promotion rule (spec §2 rule 5): ONLY a clean ("pass") stage-F
        # result is promoted into out/ with a freshly allocated version.
        # "fail" and "incomplete" are both left in work/ with their report
        # in logs/ -- "the render is wrong" and "I could not check whether
        # the render is wrong" are different states (task brief, "Things to
        # watch"), so they get different exit codes, but neither one is
        # allowed to consume a version number or land in out/.
        ts = _timestamp()
        verify.write_reports(
            checks, ws.logs_dir / f"{ts}_qa.json", ws.logs_dir / f"{ts}_qa.md",
        )
        label = "QA failed" if status == "fail" else "QA incomplete"
        print(f"{label}; master left at {master} and the report is in {ws.logs_dir}",
              file=sys.stderr)
        for check in checks:
            if check.status != verify.PASS:
                print(f"  {check.status.upper()} {check.name}: {check.detail}",
                      file=sys.stderr)
        return EXIT_QA if status == "fail" else EXIT_INCOMPLETE

    # Promotion is irreversible -- it allocates a version number and moves the
    # only master out of work/ -- so everything that can still fail happens
    # BEFORE it, inside a handler, and anything already written is rolled back
    # on the way out. Stage E used to run after the move and outside every
    # handler, so a failure there left a version-stamped master in out/ with
    # no cover, no sidecars and no QA report, plus an uncaught traceback whose
    # exit code (1) collided with EXIT_PREFLIGHT. That was reachable today:
    # preflight validated cover.source with ffprobe while stage E opened it
    # with Pillow (preflight now performs the Pillow load too).
    version = None if mode == "draft" else ws.next_version()
    target = ws.out_master(version)
    written: list[Path] = []
    try:
        if spec.cover and spec.cover.source not in report.missing_visual:
            written.append(ws.out_cover(version))
            derive.render_cover(spec, ws, overlay_pngs, ws.out_cover(version))
        elif spec.cover:
            print(f"warning: {spec.cover.source} is missing; no cover was derived")
        written.append(ws.out_srt(version))
        derive.write_srt(spec.captions, ws.out_srt(version))
        written.append(ws.out_ass(version))
        derive.write_ass(
            spec.captions, spec.styles[spec.captions_style], spec.canvas,
            ws.out_ass(version),
        )
        written.append(ws.out_contact_sheet(version))
        # Sourced from the work/ master, which has not moved yet.
        verify.contact_sheet(spec, master, ws.out_contact_sheet(version), log_path)
        written += [ws.out_qa_json(version), ws.out_qa_md(version)]
        verify.write_reports(checks, ws.out_qa_json(version), ws.out_qa_md(version))
    except (ffmpeg.FFmpegError, OSError, ValueError) as exc:
        for path in written:
            path.unlink(missing_ok=True)
        print(f"deriving the deliverables failed: {exc}", file=sys.stderr)
        print(f"nothing was promoted; the master is still at {master}", file=sys.stderr)
        return EXIT_RENDER

    shutil.move(str(master), str(target))

    manifest.set("run", digest)
    manifest.set("run/version", str(version) if version is not None else "draft")
    manifest.save()

    print(f"wrote {target}")
    return EXIT_OK


def cmd_verify(slug: str, root: Path, version: int | None) -> int:
    ws = Workspace(root=root, slug=slug, mode="final")
    log_path = ws.log_path(_timestamp())
    try:
        spec, _ = load_spec(ws.spec_path)
    except (ValueError, OSError) as exc:
        print(f"spec is unusable:\n{exc}", file=sys.stderr)
        return EXIT_PREFLIGHT

    resolved = version if version is not None else ws.next_version() - 1
    master = ws.out_master(resolved)
    if not master.is_file():
        print(f"no rendered master at {master}", file=sys.stderr)
        return EXIT_PREFLIGHT

    checks = verify.verify(spec, ws, master, log_path)
    verify.write_reports(checks, ws.out_qa_json(resolved), ws.out_qa_md(resolved))
    status = verify.overall_status(checks)
    print(f"{master.name}: {status}")
    return {"pass": EXIT_OK, "fail": EXIT_QA, "incomplete": EXIT_INCOMPLETE}[status]


def cmd_clean(slug: str, root: Path, mode: str | None) -> int:
    modes = [mode] if mode else ["final", "draft"]
    for one in modes:
        work = Workspace(root=root, slug=slug, mode=one).work_dir
        if work.exists():
            shutil.rmtree(work)
            print(f"removed {work}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stitcher")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="schema and consistency only, no assets")
    validate.add_argument("spec", type=Path)

    render = sub.add_parser("render", help="render one Short")
    render.add_argument("slug")
    render.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    render.add_argument("--mode", choices=("final", "draft"), default="final")
    render.add_argument("--force", action="store_true")

    verify_cmd = sub.add_parser("verify", help="re-run QA against an existing output")
    verify_cmd.add_argument("slug")
    verify_cmd.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    verify_cmd.add_argument("--version", type=int, default=None)

    clean = sub.add_parser("clean", help="delete work/, keep out/ and logs/")
    clean.add_argument("slug")
    clean.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    clean.add_argument("--mode", choices=("final", "draft"), default=None)

    args = parser.parse_args(argv)
    if args.command == "validate":
        return cmd_validate(args.spec)
    if args.command == "render":
        return cmd_render(args.slug, args.root, args.mode, args.force)
    if args.command == "verify":
        return cmd_verify(args.slug, args.root, args.version)
    return cmd_clean(args.slug, args.root, args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
