---
name: shorts-styleboard
description: Locks a ContentStudio Short's two visual worlds before any prompt exists — naming the Register A/present sport and venue, the Register B/source-era thinker and place, the motif that crosses both, and which Style Library entry each register binds to. Emits the styleboard artifact that `visual-prompts` consumes and that Gate C reads its world lock from. Use whenever a Short has a finished script and needs its world locked, when asked to "lock the world," "pick the sport for this Short," "set the registers," "bind the style slots," or when a world has no Library entry yet and needs a discovery request raised. Does NOT write shot prompts — that is `visual-prompts`.
---

# Shorts Styleboard (script → world lock + style bindings)

## Pipeline position

- **Upstream input:** the shot-ready timed script from `shorts-scripting`. Optionally a
  companion grounding artifact, whose thinker/source and motif populate the
  `register_b_*` keys and `motif` directly rather than being invented here `[I]`.
- **This skill's job:** lock the two registers and the world, and declare which Style
  Library entry each register binds to. Nothing about individual shots.
- **Downstream:** `visual-prompts` reads this artifact and storyboards against it.

## Why this is grounded, not generic

The register system, its shot-class taxonomy, and the world-lock block are **this
skill's own operational design `[I]`** — the corpus has nothing to say about pairing a
present-day register with a source-era register. They moved here from `visual-prompts`
unchanged, markers intact; nothing was upgraded to `[C]` by the move. The Midjourney
parameter bands the register file cites are `[T]`, web-verified 2026-07-26. Say so
plainly if asked how solid these rules are.

## Workflow

### 1. Lock the world

Before any per-beat decision or prompt exists, emit the `WORLD LOCK` block per
`references/visual-registers.md` §7 — the twelve-key (11 real keys plus the `WORLD LOCK` heading)
`register_a_*` / `register_b_*` / `motif` block that every downstream prompt inherits from `[I]`:

```
WORLD LOCK
  register_a_sport:              [one sport]
  register_a_venue:              [venue type]
  register_a_signature_objects:  [2-3 objects that make the sport unmistakable]
  register_a_season_time:        [season / time of day]
  register_a_rationale:          [one line tying the sport to the claim's evidence]
  register_b_thinker:            [name]
  register_b_era_place:          [specific era and place]
  register_b_locations:          [2-3 named period locations]
  register_b_artifacts:          [2-3 period objects]
  register_b_figure_archetype:   [role and dress; never a likeness]
  motif:                         [the grounding brief's motif, rendered in BOTH registers]
  slot_register_a:               [Library entry label bound to Register A]
  slot_register_b:               [Library entry label bound to Register B]
```

**The sport is chosen here, with a stated rationale, only if nothing upstream names one.** Check three
places in order — the incoming script, the concept brief, the grounding artifact — before picking a
sport yourself; the sport is part of the argument, not a free aesthetic choice, so `register_a_rationale`
must tie it to the claim's evidence `[I]` (`references/visual-registers.md` §8). Name the choice at the
top of the prompt sheet, not buried in the world-lock block alone. If a grounding artifact was handed to
this skill (see "Optional input" above), its thinker/source and motif populate the `register_b_*` keys
and `motif` directly rather than being invented here `[I]`.

### 2. Decide the whole-Short consistency situation, once

You decide **which situation the Short is in**; `midjourney-prompting` decides how to implement it and
what it costs.

| Situation | Hand down as |
|---|---|
| A recurring character/host appears across beats | `consistency: subject-lock` |
| No recurring character, but the Short should read as one look/brand | `consistency: style-lock` |
| Cheap/low-stakes, perfection not required | `consistency: style-lock`, `budget: cheap` |
| Subject-free b-roll/background plates | `consistency: none` |

**`style-lock` is the default for both registers under the dual-register system, with two `--sref`
codes** — one harvested per Short for Register A, one fixed and harvested once channel-wide for
Register B, reused unchanged on every subsequent Short (`references/visual-registers.md` §3–§4) `[I]`.
Register B's archetype-figure treatment — unnamed, face averted or in shadow, dressed to the role, never
a specific likeness — is precisely what makes `subject-lock` unnecessary there: there is no likeness to
lock `[I]`.

Only one mechanism is normally active per Short (or, under the dual-register system, per register).
This "pick one" framing is this skill's own operational guidance `[I]`, not a distinct corpus claim.

**Expect a pushback on `subject-lock`.** Attaching Omni Reference makes Midjourney run the whole job in
V7 at 2× GPU cost `[T] (verified 2026-07-26)` — so a character-driven Short cannot also have V8.2's
look. `midjourney-prompting` will surface that trade; carry it to the user rather than deciding for
them, because it may change whether the Short wants a recurring character at all.

### 3. Bind each register to a Style Library entry

Name the Library entry each register binds to, as a `slot_*` line in the world lock and
a one-line rationale under `BINDINGS` `[I]`. If a world has no Library entry yet, say so
under `DISCOVERY REQUESTS` rather than inventing a code — an invented `--sref` is the
exact defect this stage exists to eliminate `[I]`.

### 4. Emit the styleboard artifact

Per `references/styleboard-format.md`.

## Reference files

- `references/visual-registers.md` — the two-world system, both register contracts, the
  world-lock block, and how to choose the sport.
- `references/styleboard-format.md` — the exact artifact shape Gate C parses.
