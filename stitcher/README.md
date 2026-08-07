# Asset Stitcher

Turns a versioned `render-spec.json` plus a folder of assets into
publication-ready 9:16 Shorts deliverables: a master MP4, a cover image,
caption sidecars, and a QA report that measures rather than asserts.

Standalone: it imports nothing from `pipeline_app`, reads no skill, and never
opens the corpus. Design: `docs/superpowers/specs/2026-08-06-automated-asset-stitcher-design.md`.

## Install

```bash
pip install -r stitcher/requirements.txt
```

`requirements.txt` pins floors, not exact versions (`pydantic>=2.9`,
`Pillow>=11.0`, `pytest>=8.3`) — see the file's own comment for why. Golden
images are therefore generated per-machine, not committed.

FFmpeg and ffprobe 8.x or later must be on `PATH`, built with libx264.

## Use

```bash
python -m stitcher validate renders/<slug>/render-spec.json
```

```bash
python -m stitcher render <slug> --mode draft
```

```bash
python -m stitcher render <slug>
```

`render` exits 0 on success, 1 on preflight or validation failure, 2 on render
failure, 3 on QA failure, 4 when verification could not be completed.

## Workspace

```
renders/<slug>/
  render-spec.json    the input contract
  assets/             inputs, never modified
  work/<mode>/        intermediates: safe to delete, always rebuildable
  out/                deliverables, version-stamped, never overwritten
  logs/               every ffmpeg command line, written before it runs
```

A version is allocated only on a QA pass. A failed render leaves its master in
`work/` and its report in `logs/`, so `out/` contains only outputs that met spec.

## JSON Schema

`schema/render-spec.schema.json` describes `render-spec.json` for external
tools that cannot import Python (design spec §3). Its keys are the on-disk
ones — `in`/`out`, not the Python attributes `start`/`end`.

The pydantic models in `stitcher/spec.py` remain the source of truth; the file
is **generated** from them and committed. After changing a model, regenerate
and commit it:

```bash
cd stitcher && python -m stitcher.spec
```

`tests/test_spec.py` fails if the committed file has drifted from the models,
so it cannot rot silently. It is committed rather than produced on demand
because a file that only exists after a Python run does not deliver
"validate without importing Python".

## Tests

```bash
cd stitcher && python -m pytest tests/ -v
```

The end-to-end test needs real FFmpeg and a usable font; it skips cleanly
without them. Golden-image tests are Windows-only because glyph rasterization
is not portable; `Pillow`'s pin is a floor rather than an exact version for
the same reason (R2), so goldens are generated locally and git-ignored (R3)
rather than committed.
