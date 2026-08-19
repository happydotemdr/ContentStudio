# elevenlabs-tooling

Validates and sends a caller-authored ElevenLabs API payload. Standalone: it
imports nothing from `pipeline_app`, reads no skill, and never decides what
to say to ElevenLabs -- that judgment (voice pick, settings-per-beat,
chunking, prompt craft) lives entirely in the `elevenlabs-audio` and
`elevenlabs-music` skills, which each emit a payload + curl template this
tool then executes.

Design: `docs/superpowers/specs/2026-08-18-elevenlabs-tooling-design.md`.

All commands below assume `cd elevenlabs-tooling` first.

## Install

```bash
pip install -r requirements.txt
```

Requires `ELEVENLABS_API_KEY` set in the environment before `send` (not
`validate`, which never touches the network).

## Use

Validate a payload without spending anything:

```bash
python -m elevenlabs_tooling validate \
  --payload payload.json \
  --url "https://api.elevenlabs.io/v1/text-to-speech/VOICE_ID?output_format=mp3_44100_192"
```

Validate and send:

```bash
python -m elevenlabs_tooling send \
  --payload payload.json \
  --url "https://api.elevenlabs.io/v1/text-to-speech/VOICE_ID?output_format=mp3_44100_192" \
  --output out.mp3
```

`--url` is always the complete URL (base path + query string) exactly as the
skill's curl template gives it -- this tool never constructs one.

`send` refuses to overwrite an existing `--output` file; pass `--force` to
allow it. Its parent directory must already exist.

## Exit codes

```
0  EXIT_PASS               validation clean / send succeeded
1  EXIT_FINDINGS           blocking (E#) errors found -- the payload is the problem
2  EXIT_USAGE              argparse only, or a CLI-level problem (e.g. --output exists without --force)
3  EXIT_UNREADABLE_INPUT   payload file missing or unreadable
4  EXIT_UNPARSEABLE        payload file is not valid JSON, or is valid JSON that isn't an object
5  EXIT_SEND_FAILED        validation passed but the live API call failed, or returned an unexpected content-type
6  EXIT_NO_API_KEY         ELEVENLABS_API_KEY not set (checked only after validation passes)
```

## Validation checklist

See the design spec's "Validation" section for the full E1-E14/W1-W2 table
and the reasoning behind each check. `E#` findings block a send; `W#`
findings print but never block.

## Logging

Every attempt -- rejected, sent, succeeded, or failed -- is logged as a JSON
line to stderr and appended to `elevenlabs-tooling/logs/tooling-YYYY-MM-DD.log`,
written *before* the network call fires. Logging never raises.

## Timeouts

Default 300 seconds. Override with `--timeout SECONDS` or the
`ELEVENLABS_TOOLING_TIMEOUT_S` environment variable (`--timeout` wins if
both are set). An invalid override at either level warns and falls back
rather than crashing.

## Out of scope (v1)

Streaming endpoints, `/v1/music/detailed`'s multipart response, batch/
multi-payload orchestration, automatic retries, and cost estimation/dry-run.
See the design spec for the reasoning behind each boundary.

## Tests

```bash
python -m pytest tests/ -v
```

No test makes a real network call -- the HTTP layer is mocked throughout --
and every test's logging is isolated to a throwaway directory via an autouse
fixture in `tests/conftest.py`, never the real `logs/` directory.
