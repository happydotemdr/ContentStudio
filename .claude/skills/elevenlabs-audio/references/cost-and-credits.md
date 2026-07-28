# Cost, credits & the two-phase protocol

Distilled from `docs/elevenlabs-production-runbook.md` §8.

## Billing basis `[T]`

Billing is **per character of input text, including spaces and punctuation.** Not per word, not per
second of audio. A 4,000-character script costs the same whether the voice reads it fast or slow.

- Flash and Turbo models are **50% lower per character for API generations** `[T]`
- ElevenLabs quotes Text-to-Speech at roughly **$0.05 per 1,000 characters on Flash/Turbo** `[T]`
- The supplied runbook's per-minute figures ($0.12/min standard, $0.06/min discounted) could **not**
  be confirmed and are **`[T-unverified]`** — quote the per-character basis instead

Estimate cost as `characters × rate`, and show the arithmetic. A user who can see the number can
decide whether the render is worth it `[I]`.

## The two-phase protocol `[I]`

The economic core of this skill. **Iterating on a flagship model is the main way to waste credits.**

### Phase 1 — draft / directional exploration

| Setting | Value |
|---|---|
| Model | `eleven_flash_v2_5` — 50% cost, ~75 ms, 40k cap `[T]` |
| Text | **250–500 characters**, only the passages whose delivery is actually in question |
| Format | `mp3_22050_32` |
| Tags | **stripped** — Flash renders none `[T]` |
| Seed | fixed, so you hear the change and not the variance `[T]` |

Iterate freely here: pacing, punctuation, phrasing, voice fit.

### Phase 2 — master render

| Setting | Value |
|---|---|
| Model | `eleven_v3` (tagged/expressive) or `eleven_multilingual_v2` (long-form stable) `[T]` |
| Text | full, with tags restored |
| Format | `mp3_44100_192` or `pcm_44100` — **tier-gated** `[T]` |
| Seed | fixed |
| Dictionary | `version_id` **pinned** `[I]` |

### The arithmetic

10 iterations × 1,000 characters:

```
Draft on Flash v2.5:  10 × 1,000 × 0.5 =  5,000 billed units
Same 10 on v3:        10 × 1,000 × 1.0 = 10,000 billed units
                                          ─────────────────
Saved by the model discount alone:         5,000 units (50%)
```

**But the model discount is the smaller half of the saving** `[I]`. Drafting on a 250–500 character
excerpt instead of the full script is the bigger lever:

```
10 iterations × 4,000-char full script on v3:   40,000 units
10 iterations × 400-char excerpt on Flash:         2,000 units
Then one 4,000-char master on v3:                  4,000 units
                                                 ──────────
Total:                                             6,000 units  (85% saved)
```

Don't render 4,000 characters to hear whether one line lands.

### Two honest limits of the draft phase — state them, don't bury them `[I]`

1. **Flash v2.5 renders no audio tags and no phonemes** `[T]`. A Flash draft validates text, pacing,
   punctuation, and voice fit. It does **not** validate tag execution or a pronunciation fix. For a
   tag-heavy script, budget **one short v3 probe** — a single 250–500 character pass containing the
   tags you're least sure of — rather than pretending the Flash draft proved something it didn't.
2. **Flash handles numbers less naturally than the larger models** `[T]`. A normalization problem
   heard in the draft may be a Flash artifact, not a script defect. Re-check on the master model
   before rewriting the script around it.

## Free regenerations — website only, **not the API** `[T]`

The supplied enterprise runbook described a payload-hash-matching free-retry workflow for API calls.
It was wrong on nearly every point. What is actually documented:

| | Reality `[T]` |
|---|---|
| How many | Two, for Text-to-Speech and Speech-to-Speech |
| Where | **Website only — explicitly *not* available via the API** |
| Text/voice/model | Must stay the same |
| **Voice settings** | **May be changed** — you keep the free regeneration |
| Time limit | First generation less than **two hours** ago |
| Session | You must **not** have refreshed or left the page |

The runbook's claim that "adjusting stability by 0.01 invalidates the free retry" is the **direct
opposite** of the documented behavior.

### The consequence for this skill `[I]`

**Assume every API call is billed.** There is no free retry to fall back on. This is exactly why the
draft phase exists.

And the corollary, which is genuinely useful advice: **if the user wants free re-rolls while tuning
sliders on a fixed piece of text, tell them to do that tuning in the web UI** — free regenerations
survive slider changes there `[T]` — **then port the settled values into the API payload.** That
inverts the runbook's advice and is the actual money-saving move.

## Determinism and re-rolls

- Fixed `seed` (0–4,294,967,295) gives **best-effort** deterministic sampling `[T]` — it reduces
  variation across identical requests, it does not guarantee identical audio.
- Use it to isolate the effect of one change. Do not promise reproducibility on it `[I]`.
- **Name a re-roll budget** whenever you select v3 Creative mode — "prone to hallucinations" is
  documented behavior `[T]`, so re-rolls are an expected cost, not a failure.

## Chunking and cost `[I]`

Chunk on natural script sections, not just at the character cap. A bad take in a section-aligned
chunk costs one section to re-render; a bad take in an arbitrarily-split chunk may force re-rendering
neighbors to keep the seams consistent.

Stitching context (`previous_text`, `previous_request_ids`) is **not** billed as additional
characters in the way `text` is — but do not assume; if a job is near a quota boundary, verify
current billing behavior before relying on it `[I]`.

## Cost section for the output spec

Always show both, and the basis:

```
COST
  Draft:  420 chars × Flash rate (50% discount)  ≈ [estimate]
  Master: 3,850 chars × standard rate            ≈ [estimate]
  Basis:  per input character, incl. spaces & punctuation [T]
  Note:   API calls are billed — no free regenerations via API [T]
  Re-roll budget: [n] master re-rolls allowed for [reason]
```
