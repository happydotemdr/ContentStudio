# API payload — parameters, templates, chunking & stitching

> **`[T]` facts in this file were web-verified 2026-07-26** against live ElevenLabs documentation
> and have not been re-checked since. Vendor facts go stale fast — re-verify before relying on a
> parameter range, a model id, or a credit rate `[T]`.

Distilled from `docs/elevenlabs-production-runbook.md` §3, §7, §9.

This skill **emits** payloads. It does not send them, does not handle API keys, and does not spend
credits. The user runs what it writes.

## Endpoint `[T]`

```
POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}
POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream     # streaming
POST https://api.elevenlabs.io/v1/text-to-dialogue/convert             # multi-speaker, v3 only
```

Auth header: `xi-api-key`.

## Request body `[T]`

| Parameter | Type / range | Default | Notes |
|---|---|---|---|
| `text` | string, **required** | — | Billed per character, **including spaces and punctuation** |
| `model_id` | string | `eleven_multilingual_v2` | **Always set explicitly** — the default is not the flagship |
| `language_code` | ISO 639-1 | — | Ignored by unsupporting models; **unsupported on `eleven_multilingual_v2`** |
| `voice_settings.stability` | 0–1 | 0.5 | v3 uses three discrete modes instead (`voice-settings.md`) |
| `voice_settings.similarity_boost` | 0–1 | 0.75 | |
| `voice_settings.style` | **0 and up** | 0 | **Non-zero increases latency** |
| `voice_settings.speed` | **0.7–1.2** | 1.0 | |
| `voice_settings.use_speaker_boost` | boolean | `true` | Increases compute |
| `seed` | integer **0–4,294,967,295** | — | Best-effort determinism |
| `previous_text` / `next_text` | string | — | Prosodic context across seams |
| `previous_request_ids` / `next_request_ids` | array, **max 3 each** | — | **Stronger** stitching — anchors to real prior audio |
| `pronunciation_dictionary_locators` | array, **max 3** | — | `{pronunciation_dictionary_id, version_id}`; `version_id` optional (latest if omitted) |
| `use_pvc_as_ivc` | boolean | `false` | Substitutes the IVC version of a PVC to cut latency (`voice-profiles.md`) |
| `apply_text_normalization` | `auto` \| `on` \| `off` | `auto` | Number/date/currency spell-out |
| `apply_language_text_normalization` | boolean | `false` | **Japanese only**; significantly increases latency |

**Correction, 2026-08-21** `[T]`: despite the "three discrete modes" framing in the
`voice_settings.stability` row above, the live eleven_v3 request body does not accept a mode name
(`"natural"`, etc.) as `voice_settings.stability` — it returns a 422. Send a float in [0, 1], same
as every other model — see the "Live-API correction, 2026-08-21" callout in `voice-settings.md`.

## Query parameters `[T]`

| Parameter | Values | Default | Notes |
|---|---|---|---|
| `output_format` | `{codec}_{rate}_{bitrate}` | `mp3_44100_128` | **`mp3_44100_192` requires Creator+; PCM/WAV at 44.1 kHz requires Pro+** |
| `optimize_streaming_latency` | 0–4 | 0 | 1 ≈ 50%, 2 ≈ 75%, 3 max, **4 max + text normalizer OFF** |
| `enable_logging` | boolean | `true` | `false` = zero retention. **Enterprise-only**, and **disables request stitching** |

### `output_format` enum `[T]`

`alaw_8000` · `ulaw_8000` ·
`mp3_22050_32` · `mp3_24000_48` · `mp3_44100_32` · `mp3_44100_64` · `mp3_44100_96` ·
`mp3_44100_128` · `mp3_44100_192` ·
`opus_48000_32` · `opus_48000_64` · `opus_48000_96` · `opus_48000_128` · `opus_48000_192` ·
`pcm_8000` · `pcm_16000` · `pcm_22050` · `pcm_24000` · `pcm_32000` · `pcm_44100` · `pcm_48000` ·
`wav_8000` · `wav_16000` · `wav_22050` · `wav_24000` · `wav_32000` · `wav_44100` · `wav_48000`

## Text normalization `[T]`

On by default across all models. Documented trouble spots: **phone numbers, currencies, calendar
events, times, addresses, URLs, unit abbreviations, keyboard shortcuts.**

Mitigations, most reliable first `[T]`:

1. **Pre-convert in the text.** `"$1,000"` → `"one thousand dollars"`; `"555-555-5555"` →
   `"five five five, five five five, five five five five"`.
2. **Use a larger model.** Multilingual v2 handles numbers more naturally than Flash v2.5 — which
   is also why a normalization problem seen in a Flash draft may be a Flash artifact.
3. Regex preprocessing for systematic cases.

**Interaction to catch:** `optimize_streaming_latency: 4` **turns the normalizer off** `[T]`. Push
latency that far and you own normalization in the text.

## Chunking & stitching `[T]`

Splitting a long script produces audible seams: cadence resets, pitch drops, unnatural pauses. Two
mechanisms, ascending strength:

**Weaker — text context.** `previous_text` / `next_text` carry the surrounding copy. Documented only
as "improves continuity across split generations" `[T]`; the supplied runbook's "final/first ~100
characters" heuristic is **`[I]`**, not a documented figure. A sentence or two of real context each
side is a sensible read.

eleven_v3 currently rejects previous_text/next_text outright with a 400
(verified live 2026-08-21) — this is moot for a single continuous
generation, which has no chunk seams to stitch, but blocking if anyone
still chunks a v3 script into multiple requests. [T]

**Stronger — request stitching.** `previous_request_ids` / `next_request_ids` (**max 3 each**)
reference actual prior generations `[T]`. Anchors to rendered audio rather than text. **Prefer this
whenever you have the IDs.** The supplied runbook omitted it entirely.

```
Chunk N-1  ──request_id: abc123──┐
                                 ▼
Chunk N    previous_request_ids: ["abc123"]
           previous_text: "...the last sentence of chunk N-1."
           next_text:     "The first sentence of chunk N+1..."
                                 │
                                 ▼
Chunk N+1  previous_request_ids: ["<chunk N's request_id>"]
```

Chunking rules `[I]`: split on **sentence boundaries**, never mid-sentence; keep each chunk under
the model's cap (`model-routing.md`); prefer chunks that align with natural script sections so a bad
take can be re-rolled without re-rendering the whole job.

### The zero-retention conflict — check this every time `[T]`

**`enable_logging: false` disables request stitching.** You cannot have both zero-retention and
`previous_request_ids`. If a job is zero-retention *and* long enough to chunk:

- Fall back to `previous_text` / `next_text`
- Accept weaker seams
- **Say so explicitly in the output** `[I]` rather than emitting a payload that silently degrades

This is Validation Gate 2's most important single check.

## Payload template — master, v3, tagged

```json
{
  "text": "[confident] Core systems initialized. [sighs] Latency still needs tuning. [excited] Let's run the throughput validation.",
  "model_id": "eleven_v3",
  "voice_settings": {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.3,
    "speed": 1.0,
    "use_speaker_boost": true
  },
  "seed": 42,
  "pronunciation_dictionary_locators": [
    { "pronunciation_dictionary_id": "DICT_ID", "version_id": "VERSION_ID" }
  ],
  "apply_text_normalization": "auto"
}
```

Query: `?output_format=mp3_44100_192&enable_logging=true`

**Live-verified correction, 2026-08-21** `[T]`: eleven_v3 rejects a string
stability mode ("natural") with a 422 — send a float. It also rejects
previous_text/next_text with a 400 — omit them entirely on v3 (this is a
non-issue for a single continuous generation, which needs no chunk-seam
stitching).

## Payload template — draft, Flash

```json
{
  "text": "Core systems initialized. Latency still needs tuning. Let's run the throughput validation.",
  "model_id": "eleven_flash_v2_5",
  "voice_settings": {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0,
    "speed": 1.0,
    "use_speaker_boost": true
  },
  "seed": 42
}
```

Query: `?output_format=mp3_22050_32`

**Tags are stripped from the draft text** — Flash v2.5 does not render them `[T]`, and leaving them
in means the model reads or ignores bracketed literals, muddying exactly the thing you're auditioning.

## curl

```bash
curl -X POST "https://api.elevenlabs.io/v1/text-to-speech/VOICE_ID?output_format=mp3_44100_192&enable_logging=true" -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" -d @payload.json --output master.mp3
```

Write the payload to a file rather than inlining it — a tagged script inlined into a shell string is
a quoting hazard, and `-d @payload.json` keeps the exact bytes you validated `[I]`.

## Pre-emit checklist

1. `model_id` set explicitly `[T]`
2. Every setting in range; `speed` within 0.7–1.2 `[T]`
3. `output_format` matches `phase` and the tier gate is flagged `[T]`
4. `enable_logging` matches `privacy`; zero-retention ↔ stitching conflict resolved `[T]`
5. `seed` present when `determinism: on` `[T]`
6. Every chunk seam carries stitching context `[T]`
7. ≤3 dictionary locators; `version_id` pinned for a master `[T]`/`[I]`
8. Features match the model (`model-routing.md`) `[T]`
9. Numbers, dates, URLs pre-converted `[T]`
