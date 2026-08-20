---
name: elevenlabs-music
description: Builds a complete, ready-to-run Eleven Music setup — a bed profile card, a beat-locked section map, a copy-paste prompt for the elevenlabs.io Music app, a composition-plan JSON pinned to the script's own beat durations, a JSON request payload and curl command, and a cost/iteration plan — with fresh-agent validation gates before anything is generated. Use whenever the user is generating music with ElevenLabs and needs the actual setup rather than creative direction: "generate a track for this," "write me the Eleven Music prompt," "build the composition plan," "how do I make the music match my beat timings," "how do I stop it adding vocals," "my prompt got a bad_prompt error," "the track came back the wrong length," "what does context_adherence do," "how do I not burn credits iterating," "make me an instrumental bed for this Short." Works standalone for any music job (podcast bed, ad, game loop, trailer cue, background track) AND as the downstream specialist for ContentStudio's `music-brief` skill, which hands down the corpus-grounded bed arc and leaves the executable configuration to this skill. Do not use this to decide duck depth or the LUFS target (that is `voiceover-brief`), to design the bed arc or the hook hold-out (that is `music-brief`), or to write the edit plan (that is `shorts-assembly`).
---

# ElevenLabs Music (composition plans, prompt craft & credit discipline)

Turns a music job into an **executable Eleven Music setup**: the bed profile, the section map, the
prompt, the composition plan, the payload, and what it will cost — validated by fresh agents before
a single credit is spent.

## Pipeline position — two modes

**Standalone.** Any music job, ContentStudio-related or not: a podcast bed, an ad cue, a game loop,
a trailer sting, a background track. Run the full four-stage workflow from Stage A, deriving the
bed profile yourself from the job brief.

**Pipeline (ContentStudio Shorts).** `music-brief` hands down the corpus-grounded **creative** call:
the emotional arc, the hook hold-out, and whether the Short gets a bed at all. **Accept that call
and do not re-litigate it.** Your job is to convert it into a working configuration. Enter at
Stage A with the Bed Arc already decided.

The boundary, stated once so neither skill drifts into the other:

| `music-brief` owns | `elevenlabs-music` owns |
|---|---|
| The emotional arc and its movements | The style vocabulary that renders that arc |
| The hook hold-out and pause placements | The chunk boundaries and `duration_ms` arithmetic |
| The tone-contradiction call | `model_id`, plan shape, and the parameter conflicts |
| Whether the Short gets a bed at all | The prompt, payload, and credit spend |

**Loudness and ducking stay with `voiceover-brief`** (`references/production-and-loudness.md`) — do
not duplicate or contradict them here. Downstream of both: `shorts-assembly`.

## Grounding — read before writing any rule

One source: **`docs/elevenlabs-music-runbook.md`** — platform truth, web-verified against live
ElevenLabs docs **2026-08-06**.

Markers, copied verbatim wherever a rule is repeated:

- **`[T]`** web-verified 2026-08-06 · **`[T-unverified]`** asserted by a supplied source but **not**
  confirmed against live docs — say so out loud when you use one · **`[I]`** general practice ·
  **`[C]`** corpus-cited `(Channel, video_id)` — see the honest gap below before reaching for this
  one.

**A normative line with no marker means something was invented instead of sourced.**

**The 420-video ContentStudio corpus contains zero findings on AI music generation.** Nearly every
normative line in this skill is `[T]` or `[I]`, not `[C]`. The corpus's contribution is entirely
upstream — what the bed must *do* — and it arrives here through `music-brief`'s Bed Arc. Do not
dress a vendor fact up as corpus consensus. **The supplied design brief that seeded this skill was
wrong in two places** (`docs/elevenlabs-music-runbook.md` §7); treat plausible-sounding Eleven Music
"facts" from memory with the same suspicion.

## The control surface — the only inputs you need

Seven inputs, everything else derived. **If the user gives none, infer from the job and state every
default you assumed** — never choose silently.

| Input | Values | Drives |
|---|---|---|
| `phase` | `draft` \| `master` | `output_format`, chunk count, spend gate |
| `use_case` | `shorts-bed` \| `podcast-bed` \| `ad` \| `trailer-cue` \| `game-loop` | style vocabulary, energy band |
| `bed_arc` | a `music-brief` Bed Arc, a saved Bed Profile Card, or `derive` | Stage A entry point |
| `runtime` | total seconds + per-beat boundaries | chunk `duration_ms` arithmetic |
| `vocals` | `instrumental` \| `vocal` | the guard on every chunk; `force_instrumental` in prompt mode |
| `plan_shape` | `chunks` (`music_v2`, default) \| `sections` (`music_v1`) | `model_id`, schema, field names |
| `consistency` | `on` \| `off` | `seed` (a consistency aid, **not** determinism `[T]`) |

## Workflow — four stages, gated

### Stage A — Bed profile

Consume the Bed Arc + timed script. When a `music-brief` Bed Arc is supplied, its output contract
has five named sections, and each feeds a specific downstream piece — read `music-brief`'s section,
don't re-derive what it already says `[I]`:

| `music-brief` section | Feeds |
|---|---|
| `## Bed arc` | The movement names, their beat ranges (s), and intended feeling — the Bed Profile Card's movement names, and Stage B's beat→chunk mapping source table |
| `## Hook hold-out` | The fade-in timestamp Stage B's chunk arithmetic starts from (`composition-plans.md`'s beat→chunk method) |
| `## Tone-contradiction check` | Gate 1's confirmation that the tone-contradiction call already resolved, with no unresolved MISMATCH |
| `## Deferred to elevenlabs-music` | The gaps (BPM, key, genre, instrumentation) the corpus doesn't cover and this skill must fill itself, in `prompt-craft.md`'s arc-to-style-vocabulary translation |
| `## Downstream` | Confirms this skill is the next stage — no data to extract, just the handoff pointer |

This mapping only applies when a Bed Arc is on the table. **In standalone mode there is no
`music-brief` upstream at all** — derive the bed profile directly from the job brief instead, and
skip the table above entirely `[I]`.

In pipeline mode the arc is already decided — **accept it and do not re-litigate it.** Emit a
reusable **Bed Profile Card** (mirror `elevenlabs-audio`'s Voice Profile Card pattern) the user can
paste back later to skip straight to Stage C. The card carries: use case, global positive styles,
global negative styles incl. the vocal guard, energy band, and the arc's movement names.

### Stage B — Section map

**This is the stage that earns the whole skill.** Read `references/composition-plans.md`. Map
script beats → plan chunks; `duration_ms` must sum to the exact **audio-emitting runtime**
(script end minus fade-in start — excludes any hold-out); every chunk within
**3,000–120,000 ms** `[T]`; **≤30 chunks, total 3s–10min** `[T]`. Assign per-chunk
`positive_styles`/`negative_styles` and `context_adherence`. A beat longer than 120s splits across
chunks; a beat under 3s **merges with its neighbour** and the merge is stated, not silent. The hook
hold-out is realized as a **hold-out**, not as a silent chunk — the bed simply starts at the fade-in
time and the plan's total runs from there; say so explicitly so the editor does not expect audio for
the held-out span.

**→ Gate 1.**

### Stage C — Prompt + plan + payload

Read `references/prompt-craft.md` and `references/api-payload.md`. Emit the three copy-paste
artifacts: the UI prompt body, the composition-plan JSON, and the API request payload + curl.

**→ Gate 2.**

### Stage D — Iteration & credit discipline

Read `references/api-payload.md` §cost. Explore on the plan-creation endpoint before composing;
seed re-rolls for consistency (**never presented as reproducibility** `[T]`); draft → master;
`bad_prompt` recovery via the response's suggested replacement prompt `[T]` (read from the
response's suggestion field — `[T-unverified]` field path, see `references/prompt-craft.md`);
off-length handling is fixing the **plan arithmetic** — for the default `music_v2` chunk path,
`respect_sections_durations` is a no-op, since chunk durations are always enforced regardless of
the flag `[T]`; the flag only meaningfully governs a `music_v1` plan. **Assume every compose call
is billed** `[I]` — the "plan creation is free" claim is `[T-unverified]`.

**→ Gate 3 (a spend authorization: `AUTHORIZED` / `BLOCKED`, not a correctness check).**

## Fresh-agent validation gates

Each gate dispatches a **fresh `general-purpose` agent** that has not seen your authoring rationale,
so it checks the artifact rather than rubber-stamping the reasoning. The verbatim dispatch prompts
and full checklists are in `references/validation-gates.md` — use them as written; each
already embeds the repo's sub-agent output contract.

| Gate | Fires | Checks |
|---|---|---|
| **1 — Section map** | after Stage B | durations sum to runtime; every chunk within 3,000–120,000 ms; ≤30 chunks; vocal guard present on every chunk; no lyric/vocal content in any `text`; no artist/band/track name in any style string; the Bed Arc's `## Tone-contradiction check` section is present and reports no unresolved MISMATCH |
| **2 — Payload** | after Stage C | `model_id` explicit and matching the plan shape; prompt XOR `composition_plan`; no `seed` with `prompt`; no `force_instrumental` with a plan; no `music_length_ms` with a plan; style arrays ≤50; `output_format` matches phase |
| **3 — Pre-master spend** | before any master render | a draft was emitted and confirmed; cost stated as an estimate with its `[T-unverified]` status named; re-roll budget named; no reliance on unverified free-plan claims |

**Gate 1 never re-runs `music-brief`'s tone call.** The boundary table above assigns the
tone-contradiction call upstream; this gate only confirms that the upstream artifact carries the
section and that it resolved. Reading the voiceover brief here would be re-litigating a decision
this skill declared it accepts `[I]`.

**Gates 1 and 2 are independent — dispatch them in parallel** (single message, two tool calls) once
both artifacts exist. **A gate returning findings blocks emission** until resolved or explicitly
overridden by the user, and **an override is recorded as an override, never as a pass** `[I]`.
**Never claim a gate passed without running it.**

## Output contract

Emit one **MUSIC PRODUCTION SPEC** with these sections, in this order — an in-chat fenced block,
ALL-CAPS unnumbered sections, two-space-indented content. **Omit a section only when it genuinely
does not apply, and say why rather than dropping it silently:**

```
=== MUSIC PRODUCTION SPEC — [short] — [DRAFT | MASTER] ===

CONTROL SURFACE
  phase / use_case / bed_arc / runtime / vocals / plan_shape / consistency
  Assumed defaults: [every value you chose for the user, named explicitly]

BED PROFILE
  use case · global positive styles · global negative styles (incl. vocal guard) · energy band
  · movement names — reusable as a Bed Profile Card

SECTION MAP
  | # | beat | start–end (s) | duration_ms | positive_styles | negative_styles | context_adherence |
  Sum: [arithmetic shown] = [audio-emitting runtime — script end minus fade-in start; excludes
  any hold-out, which is stated separately]

UI PROMPT
  [the prompt body to paste into the elevenlabs.io Music app, verbatim and self-contained]

COMPOSITION PLAN
  [the plan JSON, copy-paste ready]

REQUEST PAYLOAD
  [JSON body + query params]
  [curl command]

MIX HANDOFF
  Duck depth and LUFS target, restated from voiceover-brief — NOT re-decided here.
  Asset filename: S<###>_music.mp3

COST
  [estimate + the [T-unverified] status of the credit rate, stated plainly]

QC CHECKLIST
  [what to listen for, and the parameter fix for each symptom]

VALIDATION GATES
  Gate 1: [pass | findings]   Gate 2: [pass | findings]   Gate 3: [pass | findings | n/a]

NEXT
  [draft → confirm → master, or the handoff to shorts-assembly]
```

**`MIX HANDOFF` has no analogue in `elevenlabs-audio`.** Its whole job is to **restate, never
re-decide**, the duck depth and LUFS target inherited from `voiceover-brief`, plus the
`S<###>_music.mp3` filename, so `shorts-assembly` has everything without a lookup. If this section
ever picks a *different* number from the one upstream chose, that is the drift the boundary exists
to prevent.

## Handoff contract (machine-checked)

```handoff
produces.kind: none
produces.stage: none
produces.section: CONTROL SURFACE
produces.section: BED PROFILE
produces.section: SECTION MAP
produces.section: UI PROMPT
produces.section: COMPOSITION PLAN
produces.section: REQUEST PAYLOAD
produces.section: MIX HANDOFF
produces.section: COST
produces.section: QC CHECKLIST
produces.section: VALIDATION GATES
produces.section: NEXT
consumes: music-brief#Bed arc
consumes: music-brief#Hook hold-out
consumes: music-brief#Tone-contradiction check
consumes: music-brief#Deferred to elevenlabs-music
consumes: voiceover-brief#Production & loudness
```

## What this skill does NOT do

- **Call the Eleven Music API.** It emits payloads and curl commands; you run them. It never handles
  an API key, never renders audio, and never spends credits on its own.
- **Duck depth, LUFS, or the mix** — `voiceover-brief`.
- **The bed arc, the hook hold-out, or whether the Short gets a bed at all** — `music-brief`.
- **The edit plan** — `shorts-assembly`. **The script** — `shorts-scripting`.

## `[T]` facts most likely to be stale

Re-verify before relying on them (`docs/elevenlabs-music-runbook.md` §7): model IDs and whether a
`music_v3` has shipped; the `music_v1` `sections[]` shape's continued support; credit rates; the
plan-creation endpoint's path and cost; per-tier commercial terms; the ≤30-chunk and 3,000–120,000
ms bounds; `context_adherence`'s default. Plus: **everything `[T-unverified]`** — the credit cost,
the free-plan claim, and above all **whether the vocal guard actually suppresses vocals** — is a
starting point, never a fact.

## Reference files

- `references/composition-plans.md` — both plan shapes, the beat→chunk mapping method, the
  split/merge rules, and the instrumental technique with its verification status.
- `references/prompt-craft.md` — the UI prompt body, Include/Exclude Styles, the copyright guard and
  its recovery path, and the arc-to-style-vocabulary translation table.
- `references/api-payload.md` — the endpoint, full parameter surface, JSON/curl templates, and the
  cost section this skill's Stage D reads.
- `references/validation-gates.md` — the three verbatim fresh-agent dispatch prompts.
