# API payload — endpoints, parameter conflicts, curl templates & cost discipline

> **`[T]` facts in this file were web-verified 2026-08-06** against live ElevenLabs Music documentation
> and have not been re-checked since. Vendor facts go stale fast — re-verify before relying on a
> parameter range, a model id, or a credit rate `[T]`.

Distilled from `docs/elevenlabs-music-runbook.md` §1, §3, §5.

This is the reference for Stage C's **REQUEST PAYLOAD** artifact and Stage D's iteration/credit
discipline. **This skill never calls the API** — everything below is a template the user runs
themselves; nothing here handles a key, renders audio, or spends a credit on its own.

## The three endpoints `[T]`

- **`POST /v1/music`** `[T]` — the compose endpoint. Body takes `prompt` **XOR** `composition_plan`; the
  two are mutually exclusive `[T]`. Query param `output_format`, default `auto`. Confirmed today
  via the GitHub skill reference, the fuller endpoint set is: `compose` (this one), `stream` (audio
  chunks during generation, **paid plans only**), `compose_detailed`, `compose_detailed_stream`
  (Server-Sent Events), `upload` (import audio for inpainting, **enterprise only**), and
  `video_to_music` (generate a bed from a video clip) `[T]`.
- **`POST /v1/music/detailed`** `[T]` — same body as compose, plus `with_timestamps`. Returns a
  multipart response carrying the resolved plan and `song_metadata` alongside the audio `[T]`.
- **Plan creation** `[T]` — exposed in the SDK as
  `music.composition_plan.create(prompt=…, music_length_ms=…, model_id=…)` `[T]`, confirmed today
  directly against the cookbook page, which documents **only the SDK call and shows no REST
  path**. **The REST path is `[T-unverified]`** — a supplied design brief asserted
  `/v1/music/plan`; that path was not confirmed against any live page fetched today, so treat it as
  a hypothesis, not a fact, until reproduced. Also confirmed today: the cookbook page states
  plainly **"The Eleven Music API is only available to paid users"** `[T]` — a plan-tier gate, not
  a per-call price (see Cost & iteration discipline, below).

## Parameter conflicts — the failure mode `[T]` 2026-08-06

These are not independent knobs; several are mutually exclusive or mode-locked, and getting one
wrong either 400s the request or silently no-ops.

| Conflict | Rule `[T]` 2026-08-06 |
|---|---|
| `prompt` vs `composition_plan` | Mutually exclusive. One or the other, never both. |
| `seed` | Plan-only — "cannot be used in conjunction with prompt". |
| `force_instrumental` | Prompt-only. Does **not** apply to composition plans. |
| `music_length_ms` | Prompt-only, 3,000–600,000 ms. With a plan, length comes from the chunks. |
| `model_id` | Default is `music_v1`, **not** the newer model — set it explicitly. Chunk plans require `music_v2`. |

Two more surface parameters, both `[T]` and both easy to forget because they default quietly:
`respect_sections_durations` (default `true`; on `music_v2` chunk durations are always enforced
regardless of the flag — meaningful only on `music_v1`) and `finetune_id` /
`store_for_inpainting` (default `false`) / `sign_with_c2pa` (default `false`, mp3 only) — none of
these three are conflict-prone, they just have defaults worth stating explicitly in the payload
rather than leaving implicit.

## `output_format` by phase `[I]`

`output_format` is a query param, default `auto`. The API doesn't document phase-specific
presets the way the TTS endpoints do, so this skill applies the same draft/master discipline as
`elevenlabs-audio` by inference, not by a documented Eleven-Music-specific default:

| Phase | `output_format` | Why |
|---|---|---|
| `draft` | a lower-bitrate / lower-sample-rate value, or leave `auto` | fast iteration, cheap to discard |
| `master` | the highest-fidelity value the account tier supports | final asset handed to `shorts-assembly` |

State whichever concrete value you pick in the payload — don't leave `auto` unexamined in a
master render just because it's the default `[I]`.

## Curl templates

All three templates below are copy-paste starting points. Replace `$ELEVENLABS_API_KEY` with the
user's own key in their own shell — **this skill never sees or handles that key.**

### Compose from a plan (`music_v2`, chunk-based)

```bash
curl -X POST "https://api.elevenlabs.io/v1/music?output_format=mp3_44100_192" \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "music_v2",
    "composition_plan": {
      "chunks": [
        {
          "text": "<section label or inline direction>",
          "duration_ms": 16000,
          "positive_styles": ["<style tokens>"],
          "negative_styles": ["vocals", "singing", "spoken word", "lyrics"],
          "context_adherence": "high"
        }
      ]
    }
  }'
```

`seed` may be added at the top level alongside `composition_plan` for consistency re-rolls — never
alongside `prompt` (see the conflicts table above).

### Compose from a prompt (`music_v1` or an ungated prompt-mode job)

```bash
curl -X POST "https://api.elevenlabs.io/v1/music?output_format=mp3_44100_192" \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "music_v1",
    "prompt": "<the self-contained UI prompt body from prompt-craft.md>",
    "music_length_ms": 41000,
    "force_instrumental": true
  }'
```

`seed` is never valid in this body — it is plan-only `[T]`. Do not add it here even for
consistency; there is no consistency mechanism documented for prompt mode.

### Plan creation (explore before composing)

The confirmed path is the SDK call, not REST `[T]`:

```python
from elevenlabs.client import ElevenLabs

client = ElevenLabs(api_key="$ELEVENLABS_API_KEY")
plan = client.music.composition_plan.create(
    prompt="<a description of the whole track>",
    music_length_ms=41000,
    model_id="music_v2",
)
```

**A REST equivalent, if the user's tooling requires curl, is offered here only as an unconfirmed
hypothesis — verify the path before relying on it:**

```bash
# [T-unverified] — path not confirmed against any live page as of 2026-08-06
curl -X POST "https://api.elevenlabs.io/v1/music/plan" \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "<a description of the whole track>",
    "music_length_ms": 41000,
    "model_id": "music_v2"
  }'
```

## Cost & iteration discipline

- **Explore with plan creation before composing** `[I]` — inspect the returned plan's chunk
  breakdown and adjust the prompt before spending a compose call on it. The design brief's "plan
  creation costs no credits" claim is **`[T-unverified]`** — it was not confirmed against any live
  page and must be presented to the user as a hypothesis, not a free lunch.
- **Assume every compose call is billed** `[I]`. The credit rate per generation is
  **`[T-unverified]`** — not found in the docs on 2026-08-06. Never quote a specific credit number
  as fact; state the estimate and its unverified status together, every time.
- **`[T]` Seed re-rolls: same seed + same params → more consistent results; exact reproducibility is
  not guaranteed and output may change across system updates** `[T]` — this is the runbook's
  verbatim disclaimer (§5). Never promise a re-render matches a prior one, even with the same
  seed.
- **Draft → master:** `[I]` draft at a low `output_format` and a reduced chunk count covering only the
  movements in question; master at full runtime, full chunk set, full-fidelity `output_format`
  `[I]`. This mirrors `elevenlabs-audio`'s draft/master discipline; nothing about it is Eleven
  Music-specific documentation.
- **`bad_prompt` recovery:** `[T]` catch the error and retry with the vendor's suggested replacement
  prompt `[T]` — read from `detail.data.prompt_suggestion` `[T-unverified]` (the field path itself
  was not independently re-observed in today's fetches; see `prompt-craft.md` for the full
  recovery path and the field-path caveat).
- **Off-length handling:** `respect_sections_durations` defaults to `true` `[T]`. If a render
  still comes back off-length, fix the **plan arithmetic** — recheck the chunk `duration_ms` sum
  against the declared runtime — and **never rate-stretch the audio to force it to fit**, because
  stretching alters pitch `[C] (Roberto Blake, iaTavrWIGDM)`. A composed-to-length bed should not
  need this at all; needing it is a signal the plan's arithmetic was wrong, not that the audio
  needs correcting after the fact.
