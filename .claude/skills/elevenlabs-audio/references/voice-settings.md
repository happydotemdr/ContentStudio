# Voice settings — ranges, v3 modes, bands, and artifact diagnosis

> **`[T]` facts in this file were web-verified 2026-07-26** against live ElevenLabs documentation
> and have not been re-checked since. Vendor facts go stale fast — re-verify before relying on a
> parameter range, a model id, or a credit rate `[T]`.

Distilled from `docs/elevenlabs-production-runbook.md` §3.1, §4.

## The parameters `[T]`

| Parameter | Range | Default | Notes |
|---|---|---|---|
| `stability` | 0–1 | 0.5 | Lower = wider emotional range. **On v3 this is three discrete modes instead** — see below |
| `similarity_boost` | 0–1 | 0.75 | Adherence to the original voice |
| `style` | **0 and up — not capped at 1** | 0 | Exaggerates speaker style. **Non-zero increases latency** |
| `speed` | **0.7–1.2** | 1.0 | Extreme values degrade quality |
| `use_speaker_boost` | boolean | `true` | Boosts speaker similarity; increases compute |

The supplied enterprise runbook stated `style` was capped at 1.0. It is not `[T]`.

## v3 stability is three discrete modes `[T]`

The single biggest correction to the supplied runbook, which described a 0.30–0.45 float.

| Mode | Documented behavior | Use when |
|---|---|---|
| **Creative** | "More emotional and expressive, but prone to hallucinations" | Maximum tag responsiveness; character work; short payloads you can afford to re-roll |
| **Natural** | "Closest to the original voice recording — balanced and neutral" | **Default for tagged narration** |
| **Robust** | "Highly stable, but less responsive to directional prompts" | Consistency-critical long runs — **but it suppresses audio tags** |

Docs recommend **Creative or Natural for maximum expressiveness with audio tags** `[T]`.

**The hard rule that follows: a tagged script plus Robust mode is a self-cancelling configuration.**
That is the correct, verified form of the runbook's vaguer "high stability prevents dramatic tags."

Creative's "prone to hallucinations" is a real cost, not a caveat `[T]` — if you select Creative,
name a re-roll budget in the output.

On every non-v3 model, `stability` is the continuous 0–1 float, default 0.5 `[T]`.

## Numeric bands — starting points, not facts

These come from the supplied enterprise runbook and **could not be confirmed** against live docs.
They are reasonable, and they are `[T-unverified]`. Present them as starting points and say so.

| Setting | Band | Marker |
|---|---|---|
| `stability`, long-form narration | 0.50–0.65 | `[T-unverified]` |
| `stability`, expressive delivery | 0.30–0.45 | `[T-unverified]` |
| `similarity_boost` | 0.65–0.75; **above ~0.85 risks reproducing noise present in the reference audio** | `[T-unverified]` |
| `style` | 0.30–0.50 for noticeable exaggeration without identity drift | `[T-unverified]` |

Verified, and safe to state plainly: the ranges, the defaults (0.5 / 0.75 / 0 / 1.0 / boost on),
that non-zero `style` increases latency, and that speaker boost increases compute `[T]`.

`expressiveness` → settings mappings live in `control-surface.md` §Mapping 2.

## What each parameter actually trades

| Raise it | You get | You risk |
|---|---|---|
| `stability` | Consistency across a long run | Monotone; **tags suppressed** on v3 `[T]` |
| `similarity_boost` | Closer timbre match to the reference | Reproducing reference-audio noise `[T-unverified]` |
| `style` | Performance, character | Identity drift; **higher latency** `[T]` |
| `speed` | Pace | Quality degradation past 1.2 `[T]` |
| `use_speaker_boost` | Similarity | Compute cost `[T]` |

`similarity_boost` tracks **the voice**, not the performance — it should not move when
`expressiveness` moves `[I]`. If it needs raising past ~0.85 to sound right, the reference audio is
the problem, not the setting (`voice-profiles.md`).

## Artifact → cause → fix

The causal claims below are the supplied runbook's, not ElevenLabs' — directionally sound,
mechanistically unverified. Marked `[T-unverified]` except where noted.

| Symptom | Likely cause | Fix |
|---|---|---|
| Slurring, vocal fry, wild emotional swings | `stability` too low | Raise it; on v3 Creative → Natural `[T]` |
| Flat, monotone, no inflection | `stability` too high | Lower it; on v3 Robust → Natural `[T]` |
| **Audio tags ignored** | Robust mode, or a non-v3 model `[T]` | Switch to Natural/Creative; **confirm the model supports tags** `[T]` |
| Tag ignored on the right model and mode | **The voice can't perform it** `[T]` | Change the voice or the tag — no setting fixes this |
| High-frequency hiss, ringing, metallic edge | `similarity_boost` too high — over-fitting to reference noise | Lower toward 0.65–0.75; **fix the reference audio** |
| Voice drifts from the intended character | `style` too high | Lower `style` |
| Cadence drop or pitch jump at a chunk seam | Missing stitching context | Add `previous_request_ids`, or `previous_text`/`next_text` `[T]` |
| Numbers, dates, URLs read wrong | Text normalization | **Pre-convert in the text** `[T]` |
| Proper nouns / jargon mispronounced | No pronunciation rule | Inline IPA (v3) or a dictionary `[T]` |
| Quality degrades past a certain pace | `speed` outside 0.7–1.2 | Bring it inside the range `[T]` |
| Draft sounds worse than expected on numbers | **Flash artifact, not a script defect** `[T]` | Re-check on the master model before changing the script |

### Check the two free things first `[I]`

Before changing any setting:

1. **Is the model right?** Most "tags aren't working" and "phonemes aren't working" reports are a
   routing error, not a settings error (`model-routing.md`) `[T]`.
2. **Is the text the problem?** Numbers, dates, currencies, URLs, and unit abbreviations are
   documented normalization trouble spots `[T]`. Fixing the text is more reliable than any setting.

Both are free. Settings changes cost a render.

## Tuning without burning credits

- Tune on **`eleven_flash_v2_5`** with a 250–500 character excerpt (`cost-and-credits.md`) `[I]`.
- Fix `seed` while tuning so you're hearing the parameter change, not sampling variance `[T]`.
  Determinism is **best-effort** — it reduces variation, it doesn't eliminate it `[T]`.
- Change **one parameter at a time** `[I]`.
- **Tune sliders in the web UI if you want free re-rolls.** `[T]` The two free regenerations are
  website-only and **explicitly unavailable via the API** `[T]` — and they *do* survive slider
  changes on the website `[T]`. Settle the values there, then port them into the payload.

That last point inverts the supplied runbook's advice, which described free API retries invalidated
by a 0.01 stability change. Both halves of that were wrong (`docs/elevenlabs-production-runbook.md` §8.3).
