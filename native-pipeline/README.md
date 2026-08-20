# native-pipeline

Orchestrates the native single-generation render mode: one continuous ElevenLabs take (unsplit,
unconditioned) as the final voice track, one Eleven Music generation as the bed, both driven by the take's
own `/with-timestamps` alignment data. See
`docs/superpowers/specs/2026-08-20-native-single-generation-render-mode-design.md` for the full design.

**Isolation:** this package is the *only* code that imports both `stitcher` and `elevenlabs_tooling`. Neither
of those two packages imports `native_pipeline` or each other — VO and music generation happen via subprocess
calls to `elevenlabs_tooling`'s CLI, and the final render happens via a subprocess call to `stitcher`'s CLI.
`native_pipeline` never reaches into either package's internals beyond their public, documented functions.

## Running tests

```bash
cd native-pipeline
python -m pytest                      # unit tests only (default; e2e is opt-in)
python -m pytest -m e2e                # the real end-to-end run (costs real API credits)
```
