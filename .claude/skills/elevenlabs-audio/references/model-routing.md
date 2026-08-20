# Model routing & the feature-compatibility matrix

Distilled from `docs/elevenlabs-production-runbook.md` §1.

## The models `[T]`

| `model_id` | Max chars | Languages | Latency | Price | Use for |
|---|---|---|---|---|---|
| `eleven_v3` | 5,000 | 70+ | not published | standard | **Flagship.** Tags, expressive delivery, multi-speaker dialogue |
| `eleven_multilingual_v2` | 10,000 | 29 | not published | standard | Long-form narration, audiobooks, stable continuous VO |
| `eleven_flash_v2_5` | 40,000 | 32 | ~75 ms | **50% lower** | Real-time agents, telephony, **and every draft** |
| `eleven_flash_v2` | 30,000 | English only | ~75 ms | 50% lower | Budget English; **the only non-v3 model that honors `<phoneme>`** |
| `eleven_multilingual_sts_v2` | 10,000 | 29 | not published | standard | Speech-to-Speech (voice changer) |
| `eleven_english_sts_v2` | 10,000 | English only | not published | standard | Speech-to-Speech, English |

`eleven_turbo_v2_5` is referenced in ElevenLabs' pricing material as a discounted model `[T]` but
was **absent from the models overview page** at verification (2026-07-26). Its commonly-quoted
250–300 ms latency is **`[T-unverified]`**. Prefer Flash v2.5; re-verify before quoting Turbo.

Latency figures other than Flash's ~75 ms are **`[T-unverified]`** — live docs publish none of them.
Say what is documented instead: v3 is the most expressive and least suited to real-time; Flash is
the low-latency option `[T]`.

**The API default `model_id` is `eleven_multilingual_v2`** `[T]`. Omitting it does not give you the
flagship — it gives you the model that silently ignores every tag you wrote. Always set it.

## The feature-compatibility matrix `[T]`

**Read this before writing tags, phonemes, or a dialogue script.** These features do not error when
sent to a model that lacks them — they are **dropped**, and the audio comes back subtly wrong. It is
the most common and most expensive silent failure on the platform.

| Feature | `eleven_v3` | `eleven_multilingual_v2` | `eleven_flash_v2_5` | `eleven_flash_v2` |
|---|---|---|---|---|
| Audio tags `[whispers]` etc. | **yes** | no | no | no |
| SSML `<break time="Xs" />` | no — use audio tags/punctuation instead | **yes** | **yes** | **yes** |
| PLS `<phoneme>` | **yes** | no — alias only | **no** — alias only | **yes** (English) |
| PLS `<alias>` | yes | yes | yes | yes |
| Inline IPA `/ˌkuːbərˈnɛtɪs/` | **yes** | no | no | no |
| Multi-speaker dialogue | yes (separate endpoint) | no | no | no |
| `language_code` enforcement | yes | **not supported** | yes | yes |
| Discrete stability modes | **yes** | no — 0–1 float | no — 0–1 float | no — 0–1 float |

### The two rows that trip people up

**Phoneme tags are `eleven_v3` + `eleven_flash_v2` only — *not* `eleven_flash_v2_5`** `[T]`. The
supplied enterprise runbook claimed Flash v2.5 supported them; it does not. Flash v2.5 is the
draft and real-time workhorse, and it cannot do phonemes. Phoneme tags are also **English-only by
default** — for IPA or CMU in another language you must be on `eleven_v3` `[T]`.

**`eleven_multilingual_v2` ignores `language_code`** `[T]`. The parameter is accepted and dropped.

### A third row, easy to miss the other direction: `<break>` is NOT a `eleven_v3` feature `[T]`

Unlike every other row in this matrix, `<break time="Xs" />` runs backwards from the rest of the
table: it works on `eleven_multilingual_v2`, `eleven_flash_v2`, and `eleven_flash_v2_5`, and does
**not** work on `eleven_v3` (v3 replaces it with bracketed audio tags and punctuation-based
pacing instead — a different, incompatible mechanism). Verified against ElevenLabs' own
help-center docs, 2026-08-19: max ~3s per break; a large number of breaks in one generation risks
documented instability (speech speeding up, added noise) — not observed at 7 breaks across ~950
characters in practice (`docs/superpowers/plans/2026-08-19-vo-architecture-test-plan.md` §6c).

No duration guarantee is documented, and none should be assumed: real measurement (same doc,
`/with-timestamps` ground truth) shows every break running long by roughly 50-210ms versus the
requested value, consistently in one direction. Confirm actual timing via `/with-timestamps`
rather than trusting the requested duration for anything timing-sensitive (shot cuts, caption
sync).

## Routing decisions

### Draft vs. master

Every job drafts on `eleven_flash_v2_5` `[I]` — 50% cheaper, ~75 ms, 40k cap `[T]`. See
`cost-and-credits.md`.

**But state the draft's two blind spots** rather than overselling it `[I]`:
1. Flash v2.5 renders **no tags and no phonemes**. A Flash draft validates text, pacing, punctuation,
   and voice fit — **not tag execution.** Tag behavior can only be verified on v3. For a tag-heavy
   script, budget one short v3 probe.
2. Flash handles numbers less naturally than the larger models `[T]` — a normalization problem seen
   in the draft may be a Flash artifact, not a script defect.

### When the master is *not* an upgrade

`conversational-agent` masters stay on `eleven_flash_v2_5`. Latency is the product requirement;
moving a live agent to v3 trades the thing that makes it work for expressiveness it cannot use in
real time `[I]`. v3 is documented as expressive-first, not real-time `[T]`.

Similarly, Text-to-Dialogue is **explicitly not intended for real-time applications like
conversational agents** `[T]` — do not route an agent through it for multi-voice effects.

### v3 vs. Multilingual v2 for long content

| Signal | Route |
|---|---|
| Script carries audio tags, emotional swings, character work | `eleven_v3` — nothing else renders tags `[T]` |
| Consistency across many chapters matters more than performance | `eleven_multilingual_v2` `[T]` |
| Script exceeds 5,000 chars per natural section | Multilingual v2's 10,000 cap means fewer seams `[I]` |
| Non-English phonemes required | `eleven_v3` — the only path `[T]` |
| PVC voice, fidelity critical | `eleven_multilingual_v2` — PVCs are "not fully optimized for v3" `[T]` |

That last row is a real trade-off, not a footnote: a PVC on v3 gets tags but degraded fidelity; on
Multilingual v2 it gets full fidelity but no tags. Name the trade-off and let the user choose `[I]`.

### Multi-speaker

Not a model setting — a **different endpoint** `[T]`:

- `/v1/text-to-dialogue/convert`
- **`eleven_v3` exclusively** `[T]`
- Input is a **JSON array of turns, each with `text` and `voice_id`** — no inline `Speaker A:` labels
- **≤2,000 characters total across all inputs** `[T]` — lower than v3's own 5,000 TTS cap
- Audio tags go inside each turn's `text`
- **Not for real-time** `[T]`

If a script has two voices and the user asked for a standard TTS payload, that is a routing error to
surface, not a formatting detail to paper over.

## Quick routing check before any payload

1. Does the script contain audio tags? → **v3 or nothing** `[T]`
2. Does it contain inline `/IPA/`? → **v3 or nothing** `[T]`
3. Does it need `<phoneme>`? → **v3 or `eleven_flash_v2`**, and English unless v3 `[T]`
4. Multiple speakers? → **Text-to-Dialogue, v3, ≤2,000 chars** `[T]`
5. Non-English? → check the language count; Multilingual v2 covers 29 and ignores `language_code` `[T]`
6. Real-time? → **Flash v2.5, and it stays Flash at master** `[I]`
7. Text longer than the chosen model's cap? → chunk + stitch (`api-payload.md`)

Any "no" that contradicts the chosen model is a **blocking finding**, not a warning.
