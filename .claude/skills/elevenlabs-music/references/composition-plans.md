# Composition plans — shapes, beat mapping, and the instrumental technique

Distilled from `docs/elevenlabs-music-runbook.md` §2, §3.

This is the reference for Stage B, **the stage that earns the whole skill**: turning a `music-brief`
Bed Arc's movements into a plan whose chunk arithmetic actually sums to the script's own runtime.

## Two plan shapes, and they are model-specific `[T]`

`model_id` is an enum `music_v1` | `music_v2`, and the API **defaults to `music_v1`** — set it
explicitly whenever you want `music_v2` `[I]`. The how-to guide states, verbatim: "Chunk-based
composition plans require the music_v2 model. Pass model_id='music_v2' when composing." `[T]`

### `music_v2` → `CompositionPlan` (default plan shape this skill emits) `[T]`

| Field | Type / range | Notes |
|---|---|---|
| `chunks[]` | array, **≤30 chunks, total 3s–10min** | ordered; each element is a generation chunk or an `AudioRefChunk` |
| `chunks[].text` | string | section label, lyrics, phonetic sounds, or inline directions — **not** a lyrics-only field |
| `chunks[].duration_ms` | **3,000–120,000** | the bound Gate 1 enforces |
| `chunks[].positive_styles` | array, ≤50 | docs recommend **"at least 6–7 styles in early chunks"** |
| `chunks[].negative_styles` | array, ≤50, optional | the instrumental guard lives here — see below |
| `chunks[].context_adherence` | `low` \| `medium` \| `high`, **default `high`** | how strictly the chunk mirrors surrounding sections |

**Confirmed today, not in the original design brief:** `chunks[]` can also hold `AudioRefChunk`
objects (`song_id` + `{start_ms, end_ms}`), and a generation chunk may itself carry an optional
`conditioning_ref` (an `AudioRefChunk`) plus `condition_strength` ∈ `low`|`medium`|`high`|`xhigh` to
match an existing recording's aesthetic `[T]`. **`chunks[]` supports from-scratch generation and
inpainting-style referencing in the same array — it is not an either/or split, and it is emphatically
not inpainting-only.** This corrects the design brief that seeded this skill, which mistook the
chunk shape for an inpainting-only object `[T]`.

### `music_v1` → `MusicPrompt` (legacy shape, use only when the user asks for it) `[T]`

| Field | Type / range | Notes |
|---|---|---|
| `positive_global_styles[]` / `negative_global_styles[]` | array | apply to the whole track |
| `sections[]` | array | each is one section |
| `sections[].section_name` | 1–100 chars | |
| `sections[].duration_ms` | 3,000–120,000 | same bound as `music_v2` |
| `sections[].lines[]` | ≤30 lines, ≤200 chars each | **lyric lines** — this field does not exist on `music_v2` chunks |
| `sections[].positive_local_styles[]` / `negative_local_styles[]` | array | per-section, layered on top of the globals |
| `sections[].source_from` | — | |

**Both shapes bound `duration_ms` to 3,000–120,000 ms** `[T]` — confirmed for both the `v1` section
schema and the `v2` chunk schema today. This is the bound that makes beat-locking possible and the
one Gate 1 enforces.

## `respect_sections_durations` `[T]`

Default `true`. **For `music_v2`, chunk durations are always enforced regardless of this flag** —
confirmed today, a nuance beyond the original design brief. Setting it `false` only has meaningful
effect on a `music_v1` plan: the model is then free to run a section's rendered length long or short
of the requested `duration_ms`, which is exactly the failure mode Gate 1 exists to catch on the
default `music_v2` path. **Leave it `true` unless the user has a specific `music_v1` reason not to**
`[I]` — turning it off trades beat-lock accuracy for compositional freedom the plan-mode instrumental
guard already gives up nothing to keep.

## `context_adherence` `[T]`

`low` | `medium` | `high`, **default `high`**. Governs how strictly a chunk mirrors the style of its
surrounding sections. Leave it at the default for most chunks — the arc should read as one
continuous piece, not stitched fragments.

**Lower it deliberately for a movement that must feel *different* from its neighbours** `[I]` — the
case the `music-brief` three-movement worked precedent makes concrete: a "narrowing to quiet
gravity" middle movement, sitting between a "warm and light" opener and a "relief" close, is
*supposed* to contrast with both neighbours, not blend into them. A chunk mirroring its neighbours at
`high` adherence undercuts exactly the movement the arc called for. Lowering `context_adherence` on
that chunk is this skill's craft inference from the field's documented purpose, not a documented
per-movement rule `[I]`.

## Beat → chunk mapping, worked as arithmetic `[I]`

This procedure is this skill's own method for turning a Bed Arc into chunk arithmetic — not a
documented vendor workflow. The bounds it must respect (3,000–120,000 ms per chunk, ≤30 chunks) are
`[T]`; the sequencing below is craft.

1. **Start from the fade-in time, not `t=0`, when there's a hook hold-out.** The hold-out is a
   hold-out, not a silent chunk — the plan's total covers only the audio-emitting span, from the
   fade-in timestamp to the script's end. Say so explicitly so the editor does not expect audio for
   the held-out span.
2. **Convert each movement's beat range to milliseconds:** `duration_ms = (end_s − start_s) × 1000`.
3. **Sum every chunk's `duration_ms` and confirm it equals the plan's total runtime** (script end −
   fade-in start, in ms). This sum is what Gate 1 checks and what the SECTION MAP output section
   must show as shown arithmetic, not just a final number.

Worked example — a 45s script, hook hold-out to 4.0s, three movements from the Bed Arc:

```
Fade-in at 4.0s → plan covers 4.0s–45.0s = 41.0s = 41,000 ms

Movement            Beat range     duration_ms
Rising urgency       4.0–20.0s  →  16,000
Quiet gravity       20.0–33.0s  →  13,000
Relief              33.0–45.0s  →  12,000
                                   ───────
                                    41,000  ✓ matches plan total
```

All three chunks land inside the 3,000–120,000 ms bound, so no split or merge is needed here — see
below for when one is.

## The split rule — a beat longer than 120s `[T]`

A single chunk cannot exceed 120,000 ms. A movement running 150s must become at least two chunks.
Split roughly evenly rather than maxing one chunk out and leaving a small remainder — an even split
reads as one continuous movement rather than a long chunk with a short tail-chunk bolted on `[I]`,
though the exact split point is craft judgment, not a documented rule. Example: a 150,000 ms
movement → two chunks of 75,000 ms each, both carrying the same `positive_styles` /
`negative_styles` so the seam is inaudible.

## The merge rule — a beat under 3s `[T]`

A single chunk cannot be shorter than 3,000 ms. A movement or beat under 3s cannot stand as its own
chunk — **it merges into its neighbouring chunk, and the merge is stated explicitly, never silent.**
Name which two movements merged and why in the SECTION MAP output (e.g. "the arc's `Rising
urgency` 4.0–6.5s beat is under the 3,000 ms floor; merged into the following `Quiet gravity` chunk,
which now spans 4.0–33.0s"), so the editor can trace the section map back to the arc's own movement
names without guessing which beats got folded together.

## The instrumental technique — and its verification status, stated plainly

> **`negative_styles` carrying vocal terms is the documented plan-mode instrumental technique**
> `[T]` (2026-08-06) — `force_instrumental` is prompt-only and does not apply to plans, and
> `music_v2` chunks have no `lines` field at all. **Every chunk this skill emits carries
> `["vocals", "singing", "spoken word", "lyrics"]` in `negative_styles`** `[I]`. **Confirmed
> insufficient by a live generation 2026-08-19** (`docs/elevenlabs-music-runbook.md` §3): a real
> two-bed `composition_plan`/`chunks` generation, vocal guard present on every chunk, came back
> with audible words bleeding into the mix, not just vocalise/humming. **Do not offer
> `composition_plan`/`chunks` as sufficient on its own when the bed must guarantee no vocal
> content — route that case to `prompt` mode + `force_instrumental: true` instead** (accepting the
> loss of precise per-chunk duration locking), and say so out loud when a script's bed sits under
> continuous narration, where leaked words are actively harmful, not just a stray artifact.

Two things this corrects from the design brief that seeded this skill, both confirmed today via the
composition-plans how-to guide's own chunk examples `[T]`:

- **Plan-mode instrumental is `negative_styles`, not `lines: []`.** `[T-unverified]` `music_v1`'s `lines[]` being
  empty is **not documented as an instrumental guarantee** — record any reliance on it as
  `[T-unverified]`, and do not use it alone even on a `music_v1` plan.
- **`force_instrumental` is prompt-only.** `[T]` It does not exist as a composition-plan field, and
  setting it on a plan request has no effect — the vocal guard on a plan is `negative_styles`, full
  stop.

The how-to guide's own examples use `"negative_styles": ["vocals", "lyrics", "pop", "electronic",
"bright"]` on one chunk and `"negative_styles": ["vocals"]` on another to keep those sections
instrumental `[T]` — record what was actually seen, not a shorter three-term list quoted elsewhere.
This skill's own default list (`["vocals", "singing", "spoken word", "lyrics"]`) is a craft choice
built from that documented pattern, not a copy of either example verbatim `[I]`.

**Do not present the vocal guard as a guarantee anywhere in the output.** The correct framing,
every time a plan is emitted: "negative_styles carries the vocal guard on every chunk; whether it
actually suppresses vocals in the rendered audio has not been verified — listen to the first render
specifically for vocalise or humming before treating the bed as instrumental."
