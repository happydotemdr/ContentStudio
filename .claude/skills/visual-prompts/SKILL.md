---
name: visual-prompts
description: Turn a shot-ready ContentStudio Short script into a Midjourney prompt sheet — one or more image prompts per script beat, plus the whole-Short consistency and parameter setup (Omni Reference, --sref, mood boards, --ar/--stylize/--chaos). Use this whenever the user has a scripted/timed Short (from shorts-scripting) and needs "Midjourney prompts," "visual prompts," "image prompts for this script," "consistency setup," or asks how to visualize/storyboard a faceless Short in Midjourney. Always trigger before the user hand-writes MJ prompts from scratch — the corpus-grounded prompt anatomy, parameter defaults, and no-text rule in this skill materially change what a good prompt looks like.
---

# Visual Prompts (script beats → Midjourney prompt sheet)

## Pipeline position

- **Upstream input:** the shot-ready, timed script from `shorts-scripting` — a beat-by-beat breakdown
  (Hook / Setup / Build / Re-hook / Payoff / Loop-CTA, or whatever beats that skill emits) with a
  duration and VO line per beat.
- **This skill's job:** turn each beat into one or more Midjourney still-image prompts (and, only where
  a beat calls for simple motion, a light image→video note), plus a single whole-Short setup block
  covering aspect ratio, stylize/chaos defaults, and the consistency mechanism (character sheet +
  Omni Reference, `--sref`/mood board, or fixed seed).
- **Downstream:** the resulting prompt sheet feeds `shorts-assembly` **alongside** `voiceover-brief`'s
  output — assembly is the first skill that sees both the visuals and the voice spec together.
- **Not this skill's job:** actual video generation/animation quality, editing, captions, or the audio
  side — those belong to `shorts-assembly` and `voiceover-brief` respectively.

## Why this is grounded, not generic

Every prompt-construction rule below traces to `references/midjourney-craft.md`, itself distilled from
`docs/midjourney-prompting-guide.md` (384 findings, 4 dedicated Midjourney channels + web-verified
features, dated 2026-07-23). The visual-*pacing* rules (how often to change the image, what look to
avoid) trace to `references/faceless-pacing-rules.md`, distilled from `docs/headless-youtube-audit.md`
§6 — a **thin corpus theme (27 findings)**, flagged as such rather than padded with invented "best
practices." If you find yourself about to write a rule with no `[C]`/`[I]`/`[T]` marker, stop — that's
the signal you're inventing instead of sourcing. Say the corpus doesn't cover it and move on.

## Workflow

### 1. Read the script and list beats

Pull each beat's name, duration, and VO line/visual note from the incoming script. If the script gives
an explicit "visual" column (as the playbook's shot-list template does), start there; if it only gives
VO lines, infer the visual from what's being said.

### 2. Decide how many stills each beat needs

**Change the on-screen visual roughly every 3 seconds — never hold one image too long** `[C] (Make Money Matt, HopTPCLbiiM)`.
A static, unchanging frame reads as "the visual equivalent of dead air" `[C]` — see
`references/faceless-pacing-rules.md`. Concretely: a 3s Hook beat is one still; a 14–20s Build beat
needs 3–5 stills, each matched to the sentence being spoken at that moment (match visual to what's
said sentence-by-sentence, or the mismatch reads as confusing `[C]`, same reference). Don't over-cut
beyond what the VO content actually supports — the rule is "don't let a frame go stale," not "cut for
its own sake" (see the over-editing caution in the same reference file).

### 3. Pick the whole-Short consistency mechanism, once, before writing per-beat prompts

Read `references/midjourney-craft.md` §"Consistency decision" for the full reasoning. Short version:

| Situation | Mechanism |
|---|---|
| A recurring character/host appears across beats | Build a 4-angle character reference sheet once, then drive every later beat with **Omni Reference** (`--oref <url> --ow <0-1000>`) `[C][T]` |
| No recurring character, but the whole Short should read as one consistent look/brand | A style code (`--sref <code>`) or an uploaded **mood board** (`--p <code>`) applied to every prompt `[C][T]` |
| Cheap/low-stakes, perfection not required | A single fixed `--seed` reused across prompts `[C] (Tokenized AI, MfK-WkKUnKQ)` |
| Subject-free b-roll/background plates (no character, no continuity need) | No consistency mechanism needed beyond the shared `--ar`/style — build a subject-free base per §4 |

Only one mechanism is normally active per Short — stacking Omni Reference *and* a mood board *and* a
seed is possible but adds cost/complexity for little gain. This "pick one" framing is this skill's own
operational guidance `[I]`, not a distinct corpus claim — the guide documents each mechanism
independently and doesn't itself rank them against each other.

### 4. Build each prompt with the anatomy in `references/midjourney-craft.md`

Order: **medium → subject + action/pose → environment/context → composition (camera/lens/angle) →
lighting → style → color/mood → parameters** `[C][T] (Tokenized AI, 4DrNl5lNapo)`. Keep it short —
long prompts dilute which words MJ actually weights `[C] (Tokenized AI, vezJXJGQMoY)` — and put whatever
matters most at the front, since MJ weights earlier words more heavily and can drop late ones entirely
`[C] (Tokenized AI, 4DrNl5lNapo)`.

**Every prompt in this skill ends with "No Text."** Midjourney cannot reliably render on-screen text/
captions — the corpus and the playbook both route text-bearing composites to a text-capable tool or a
post-MJ compositing pass, never to MJ itself `[C] (Tokenized AI, qFYJb0zYztY)`. If the beat's script
has on-screen text or a hook card, that text is **not**
part of the MJ prompt — pass it through to `shorts-assembly` as caption/overlay copy, not baked into
the image.

### 5. Set the per-Short parameter defaults

Default for every prompt in the sheet unless the beat needs something different: `--ar 9:16` (Shorts
destination) `[C][T]`, `--style raw` (favors realism, especially people) `[C] (Future Tech Pilot, Tv1dfGcOSnA)`,
`--s 140–185` (sweet-spot stylize range) `[C] (Future Tech Pilot, Tv1dfGcOSnA / ioJ6istzwHw; Tokenized AI, 1GnipTgvLI0)`,
`--c 3–9` if you want gentle grid variety while drafting `[C] (Future Tech Pilot, Tv1dfGcOSnA / fMEvMqvzUbc)`.
Full parameter reference (seed, `--iw`, `--sw`, `--no`, `--hd`, etc.) is in `references/midjourney-craft.md`.

### 6. Only add a video note where the beat genuinely needs motion

MJ's own video generator is **D-tier — jittery, choppy, weak prompt-following** `[C] (Tao Prompts, uCsc0ORcJDo)`.
This skill defaults to **stills**. Where a beat clearly wants simple motion (a slow push-in, a hero
shot breathing), add one line using MJ's `--motion low` image→video path (prefer low motion for
coherence `[C] (Future Tech Pilot, Dkj7Jqejfz0)`); for anything more demanding (multi-shot, dialogue,
big camera moves), say so explicitly and leave the actual video-model choice to `shorts-assembly` —
that decision and its tool-chain live downstream, not here.

### 7. Emit the prompt sheet

Use this shape (see `references/worked-example.md` for a full run of a real beat table through it):

```
=== VISUAL PROMPT SHEET — [Short ID / title] ===

WHOLE-SHORT SETUP
  Aspect ratio:     --ar 9:16
  Style/params:     --style raw --s [value] --c [value]
  Consistency:      [Omni Reference w/ char sheet | --sref CODE --sw N | mood board --p CODE | fixed --seed N | none — subject-free plates]
  Notes:            [anything beat-specific that overrides the default]

PER-BEAT PROMPTS
| Beat | Dur | Still # | Midjourney prompt | Params | Video note (optional) |
|---|---|---|---|---|---|
| Hook | 0-3s | 1 | [medium] of [subject+action], [environment], [composition], [lighting], [style], [mood]. No Text. | --ar 9:16 --style raw --s 160 [--oref/--sref] | — |
| ... | ... | ... | ... | ... | ... |
```

Write each row's prompt to stand alone — Midjourney does not carry context between separate jobs
`[T]`, so a prompt that only makes sense as a continuation of the previous row will not render as
intended.

## Corpus coverage note (state this to the user if asked how solid these rules are)

The prompt-anatomy/parameter/consistency rules (`references/midjourney-craft.md`) rest on a substantial
384-finding corpus across 4 dedicated Midjourney channels — reasonably durable for the `[C]`/`[I]`
fundamentals, though every `[T]` version/pricing/resolution fact is a 2026-07-23 snapshot that **should
be re-verified** at `docs.midjourney.com` before being treated as current (see the flagged list below).
The visual-*pacing* rules (`references/faceless-pacing-rules.md`) are a genuinely **thin corpus theme
(27 findings)** — say so rather than presenting them as heavily validated, and don't extend them into
specifics the corpus doesn't state (e.g. it doesn't give a precise "ideal" cut count, only "~3 seconds").

**`[T]` facts most likely to need re-verification before you rely on them:**
- V8.1 as the default model, native 2K HD, and the `--hd`/`--raw` split (features move fast).
- Omni Reference being V7-only (an improved V8 version was "in training" as of the snapshot).
- Plan pricing/tiers (Basic/Standard/Pro/Mega) and relax-mode/stealth-mode availability.
- MJ's video generator being capped at ~21s and topping out at 720p HD.
