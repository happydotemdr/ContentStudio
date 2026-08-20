# Control surface — the eight inputs and their deterministic mappings

> **`[T]` facts in this file were web-verified 2026-07-26** against live ElevenLabs documentation
> and have not been re-checked since. Vendor facts go stale fast — re-verify before relying on a
> parameter range, a model id, or a credit rate `[T]`.

Distilled from `docs/elevenlabs-production-runbook.md` §1, §3, §4, §8.

The point of this file: **a user should be able to describe a job in eight short values and get a
complete, correct configuration.** The mappings below are deterministic — the same inputs must
always produce the same output, so a run is reproducible.

## The eight inputs

| Input | Values | If unset, default to |
|---|---|---|
| `phase` | `draft` \| `master` | **`draft`** — always, unless the user has already confirmed a draft |
| `use_case` | `shorts-vo` \| `long-form-narration` \| `character-dialogue` \| `conversational-agent` \| `ad-promo` | infer from the job; state what you inferred |
| `expressiveness` | `1`–`5` | `3` |
| `voice` | `voice_id` \| Voice Profile Card \| `explore` | `explore` |
| `language` | ISO 639-1 | `en` |
| `length` | characters or minutes | count the supplied text |
| `privacy` | `standard` \| `zero-retention` | `standard` |
| `determinism` | `on` \| `off` | `on` for `master`, `off` for `draft` |

**Always print the assumed defaults back to the user** `[I]`. A silent default is indistinguishable
from a considered choice, and the user cannot correct what they cannot see.

## Mapping 1 — `phase` + `use_case` → `model_id`

| `use_case` | `phase: draft` | `phase: master` | Why |
|---|---|---|---|
| `shorts-vo` | `eleven_flash_v2_5` | `eleven_v3` | Shorts VO is short and expressive; tags matter `[T]` |
| `long-form-narration` | `eleven_flash_v2_5` | `eleven_multilingual_v2` | Stability across chapters; 10k cap; no tags needed `[T]` |
| `character-dialogue` | `eleven_flash_v2_5` | `eleven_v3` | Tags + Text-to-Dialogue are v3-only `[T]` |
| `conversational-agent` | `eleven_flash_v2_5` | `eleven_flash_v2_5` | Latency is the requirement; ~75 ms `[T]`. **Master = Flash too** — do not "upgrade" a real-time agent to v3 |
| `ad-promo` | `eleven_flash_v2_5` | `eleven_v3` | Short, performance-heavy, tag-driven `[T]` |

**Three overrides that beat this table** `[T]`:

1. **Non-English phonemes needed** → `eleven_v3` at master, regardless of `use_case`. Phoneme tags
   are English-only on every other path.
2. **English-only + phonemes + tight budget** → `eleven_flash_v2` is the one discounted model that
   honors `<phoneme>`.
3. **`language` outside Multilingual v2's 29** → route to `eleven_v3` (70+) or `eleven_flash_v2_5`
   (32). Also note `language_code` is **unsupported on `eleven_multilingual_v2`**.

Set `model_id` explicitly in every payload. The API default is `eleven_multilingual_v2` — omitting
it silently gives you the stable-but-untagged engine `[T]`.

## Mapping 2 — `expressiveness` → stability and style

**On `eleven_v3`, stability is three discrete modes, not a float** `[T]`:

| `expressiveness` | v3 stability mode | `style` | Reads as |
|---|---|---|---|
| 1 | Robust | 0 | Flat, maximally consistent. **Suppresses audio tags** `[T]` — do not combine with a tagged script |
| 2 | Natural | 0 | Neutral, closest to the source recording `[T]` |
| 3 | **Natural** | 0.30 | **Default.** Balanced, tags land `[T]`/`[T-unverified]` |
| 4 | Creative | 0.40 | Performative; tags land hard |
| 5 | Creative | 0.50 | Maximum performance. "Prone to hallucinations" `[T]` — re-roll budget required |

**On non-v3 models**, stability is the continuous 0–1 float (default 0.5) `[T]`. Audio tags do not
apply on these models at all, so `expressiveness` only moves the float:

| `expressiveness` | `stability` | `style` |
|---|---|---|
| 1 | 0.75 | 0 |
| 2 | 0.65 | 0 |
| 3 | 0.55 | 0.30 |
| 4 | 0.45 | 0.40 |
| 5 | 0.35 | 0.50 |

The specific numeric bands above are **`[T-unverified]`** — the supplied enterprise runbook's
figures, not confirmed against live docs. Verified: the 0–1 range, the 0.5 default, that `style`
starts at 0 and is **uncapped above 1**, and that non-zero `style` increases latency `[T]`. Present
these numbers as starting points and say so.

`similarity_boost` is **not** driven by `expressiveness` — it tracks the voice, not the
performance. Default 0.75 `[T]`; see `voice-settings.md` before moving it.

## Mapping 3 — `phase` → `output_format`

| `phase` | Format | Why |
|---|---|---|
| `draft` | `mp3_22050_32` | Cheap bandwidth; adequate to judge delivery, pacing, and voice fit `[I]` |
| `master` | `mp3_44100_192` — **Creator tier+** `[T]` | High-bitrate delivery master |
| `master`, maximum fidelity | `pcm_44100` or `wav_44100` — **Pro tier+** `[T]` | Uncompressed, for further processing |
| `conversational-agent` / telephony | `ulaw_8000` or `alaw_8000` | Telephony codec `[I]` |

**Check the tier gate before emitting a master format.** If the user's plan is unknown, say the gate
exists and offer `mp3_44100_128` (the API default, ungated) as the safe fallback `[T]`.

## Mapping 4 — `privacy` → `enable_logging`

| `privacy` | `enable_logging` | Consequences |
|---|---|---|
| `standard` | `true` (default) | History retained; request stitching available |
| `zero-retention` | `false` | **Enterprise-only** `[T]`. Disables history **and request stitching** `[T]` |

**The conflict you must check every time:** `zero-retention` + a `length` that requires chunking
means `previous_request_ids` is unavailable. Fall back to `previous_text`/`next_text`, accept
weaker seams, and **say so explicitly** rather than emitting a payload that will degrade or be
rejected `[T]`.

Set it on **every** call in a job — it is a per-request query parameter, not an account setting.

## Mapping 5 — `determinism` → `seed`

| `determinism` | `seed` |
|---|---|
| `on` | A fixed integer in **0–4,294,967,295** `[T]`. Reuse it across the whole job |
| `off` | Omit |

Deterministic sampling is **best-effort** `[T]` — identical seed and identical parameters reduce
variation but do not guarantee byte-identical audio. Use it to isolate the effect of a prompt
change, not to promise reproducibility `[I]`.

## Mapping 6 — `length` → chunking and stitching

| `length` vs. the model's cap | Action |
|---|---|
| Under the cap | Single request. No stitching needed |
| Over the cap | Chunk on natural sentence breaks, never mid-sentence `[I]` |
| Any chunked job | Carry stitching context across **every** seam — see `api-payload.md` |
| `character-dialogue` via Text-to-Dialogue | **≤2,000 characters total across all turns** `[T]` — lower than v3's own 5,000 cap |

Caps: `eleven_v3` 5,000 · `eleven_multilingual_v2` 10,000 · `eleven_flash_v2_5` 40,000 ·
`eleven_flash_v2` 30,000 `[T]`.

For `phase: draft`, `length` is overridden: draft **250–500 characters** covering only the passages
whose delivery is actually in question `[I]`. This is where most of the credit saving comes from —
more than the model discount itself.

## Worked mapping

Input: *"40-minute audiobook chapter, technical jargon, English, needs to be consistent, master."*

```
phase:          master
use_case:       long-form-narration
expressiveness: 2          (assumed — consistency was the stated priority)
voice:          explore    (assumed — none supplied)
language:       en         (assumed)
length:         ~38,000 chars
privacy:        standard   (assumed)
determinism:    on         (assumed — master)

→ model_id:      eleven_multilingual_v2   (long-form; 10k cap; tags not needed)
→ stability:     0.65  style: 0  (non-v3 float path)  [T-unverified] band
→ output_format: mp3_44100_192  (Creator+ gate — flag it)
→ chunking:      ~4 requests at 10k cap, split on sentence breaks
→ stitching:     previous_request_ids (privacy is standard, so available)
→ seed:          fixed
→ pronunciation: multilingual_v2 does NOT support <phoneme> → PLS with <alias>,
                 case variants enumerated
```

Note the last line — it is the whole reason the compatibility check runs before the payload is
written. A jargon-heavy audiobook routed to Multilingual v2 **cannot** use phoneme tags, and a
config that includes them would fail silently `[T]`.
