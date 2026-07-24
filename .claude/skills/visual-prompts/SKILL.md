---
name: visual-prompts
description: Turn a shot-ready ContentStudio Short script into a Midjourney prompt sheet — one or more image prompts per script beat, the whole-Short consistency and parameter setup (Omni Reference, --sref, mood boards, --ar/--stylize/--chaos), a dedicated cover/thumbnail image prompt when the packaging direction calls for one, and — for any beat that needs real animated motion, not just a still — the image-to-video (i2v) prompt for the external tool (Kling, Seedance, etc.) that will render it. Use this whenever the user has a scripted/timed Short (from shorts-scripting) and needs "Midjourney prompts," "visual prompts," "image prompts for this script," "consistency setup," an "i2v prompt," a "Kling/Seedance prompt," help deciding whether a beat needs an animated clip, a cover/thumbnail image prompt, or asks how to visualize/storyboard/animate a faceless Short. Always trigger before the user hand-writes MJ or video-gen prompts from scratch — the corpus-grounded prompt anatomy, parameter defaults, no-text rule, and image-to-video rules in this skill materially change what a good prompt looks like.
---

# Visual Prompts (script beats → Midjourney prompt sheet)

## Pipeline position

- **Upstream input:** the shot-ready, timed script from `shorts-scripting` — a beat-by-beat breakdown
  (Hook / Setup / Build / Re-hook / Payoff / Loop-CTA, or whatever beats that skill emits) with a
  duration and VO line per beat.
- **This skill's job:** turn each beat into one or more Midjourney still-image prompts, **plus — for any
  beat that genuinely needs real animated motion, not just a still with `--motion low` — the
  image-to-video (i2v) prompt for the external tool that will render that clip** (Kling, Seedance,
  etc.), built from `references/image-to-video.md`. Stills-and-clips are the same prompt-authoring job
  continued one step further, so this skill owns both. It also owns a single whole-Short setup block
  covering aspect ratio, stylize/chaos defaults, and the consistency mechanism (character sheet + Omni
  Reference, `--sref`/mood board, or fixed seed), and, when the packaging direction calls for it, a
  dedicated cover/thumbnail image prompt (workflow step 7).
- **Downstream:** the resulting prompt sheet — stills, i2v prompts, and cover prompt — feeds
  `shorts-assembly` **alongside** `voiceover-brief`'s output — assembly is the first skill that sees
  both the visuals and the voice spec together. `shorts-assembly` operates the tools, renders the
  clips/composites, and owns the edit, captions, and the audio side.
- **Not this skill's job:** actually operating an external i2v tool, rendering the video file, editing,
  captions, or the audio side — those belong to `shorts-assembly` and `voiceover-brief` respectively.
  This skill decides *whether* a beat needs a real clip and writes *the prompt* for it; it does not run
  the render.

## Why this is grounded, not generic

Every prompt-construction rule below traces to `references/midjourney-craft.md`, itself distilled from
`docs/midjourney-prompting-guide.md` (384 findings, 4 dedicated Midjourney channels + web-verified
features, dated 2026-07-23). The image-to-video rules (`references/image-to-video.md`) trace to the
same guide's §8 "Video generation & motion (image→video)" — its **largest single theme (79 findings)**,
so animating a beat properly is at least as well-supported as writing the still prompt for it. The
visual-*pacing* rules (how often to change the image, what look to avoid) trace to
`references/faceless-pacing-rules.md`, distilled from `docs/headless-youtube-audit.md` §6 — a **thin
corpus theme (27 findings)**, flagged as such rather than padded with invented "best practices." If you
find yourself about to write a rule with no `[C]`/`[I]`/`[T]` marker, stop — that's the signal you're
inventing instead of sourcing. Say the corpus doesn't cover it and move on.

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

### 6. Decide, per beat, whether a still suffices or the beat needs a real animated clip — and if so, write its i2v prompt

This skill defaults to **stills** — the corpus's cited "AI slideshow" format (stills + slow pans,
scenes changing every 1–5s) is cheap and currently performing well, per `faceless-pacing-rules.md`.
Don't reach for animation just because it's possible. Work through three tiers, per beat, using the
decision table in `references/image-to-video.md`:

1. **Visual variety over ~3s spans** → additional stills (step 2's cadence rule already covers this;
   no video note needed).
2. **A hero/product still should breathe slightly** (a slow push-in, gentle steam/water motion) → add
   one line using MJ's own `--motion low` image→video path — prefer low motion for coherence, since
   MJ's own video generator is **D-tier: jittery, choppy, weak prompt-following**
   `[C] (Tao Prompts, uCsc0ORcJDo)`; `[C] (Future Tech Pilot, Dkj7Jqejfz0)`.
3. **The beat's VO describes continuous action, a camera move, or a transformation a static image can't
   sell** (a reveal, an orbit, motion mid-process) → this is a real i2v beat. Do not just flag it for
   `shorts-assembly` to figure out — **write the actual prompt here**, using
   `references/image-to-video.md`:
   - Name the **source still** (which beat/still number is the start frame).
   - Name the **target tool** (Kling, Seedance 2.0, Veo 3, etc. — pick from the model-landscape table
     in `image-to-video.md` based on what the beat needs; a one-line reason why).
   - Write the **i2v prompt text** itself using the motion-prompt techniques in that file (state speed
     explicitly, restate framing, "in a single shot, no cuts," "no subtitles and no music," etc.).
   - If the tool needs a distinct **end frame** (a keyframed transformation, not simple breathing),
     note what the end frame shows and how it's produced (typically: edit the start-frame still in an
     external image editor for a new angle/pose/lighting, per the start/end-frame section of
     `image-to-video.md`).

`shorts-assembly` still chooses how the rendered clip fits the edit and owns actually running the tool
— but the prompt it receives should already be a complete, usable one, not a placeholder note.

### 7. Decide the cover/thumbnail image

Read the packaging direction handed down from `shorts-ideation` (focal point, dominant emotion, what
it shows). Two outcomes, and this skill must state which one applies rather than silently skip the
decision:

- **The packaging direction wants something distinct from the Hook beat's still** (a different angle,
  a composed/staged shot built specifically to be a thumbnail rather than a video frame) → generate a
  dedicated cover-image MJ prompt. Use the guide's photoreal-thumbnail recipe (§13 recipe A) as a
  **structural template** `[I]` — close-up portrait of the subject + defining feature, one
  expression/emotion, environment, dramatic rim lighting, shallow depth of field — ending
  "Photorealistic, DSLR, muted colors, shot on 35mm film. No Text.," the same DSLR realism cue used
  throughout this skill `[C] (Tao Prompts, 2psBexPkw3I)`. That recipe defaults to `--ar 16:9` for a
  traditional thumbnail slot; **adapt the aspect ratio to wherever the cover actually renders** (9:16
  if it's a Shorts-feed thumbnail, 16:9 if it's a separate widescreen upload slot) — this adaptation is
  this skill's own judgment `[I]`, not a corpus claim, since the guide's recipe was written for
  long-form 16:9 thumbnails, not Shorts specifically.
- **The packaging direction is satisfied by the Hook beat's own still** → state this explicitly in the
  prompt sheet: "Cover = Hook still + `shorts-assembly`'s text overlay, no separate generation." Don't
  leave the decision implicit — an unstated cover is indistinguishable from a forgotten one.

### 8. Emit the prompt sheet

Use this shape (see `references/worked-example.md` for a full run of a real beat table through it):

```
=== VISUAL PROMPT SHEET — [Short ID / title] ===

WHOLE-SHORT SETUP
  Aspect ratio:     --ar 9:16
  Style/params:     --style raw --s [value] --c [value]
  Consistency:      [Omni Reference w/ char sheet | --sref CODE --sw N | mood board --p CODE | fixed --seed N | none — subject-free plates]
  Notes:            [anything beat-specific that overrides the default]

COVER / THUMBNAIL
  [Dedicated MJ prompt (recipe A shape, aspect ratio adapted to the render slot) — see step 7]
  — or —
  Cover = Hook beat still #1 + shorts-assembly's text overlay. No separate generation.

PER-BEAT PROMPTS
| Beat | Dur | Still # | Midjourney prompt | Params | Motion |
|---|---|---|---|---|---|
| Hook | 0-3s | 1 | [medium] of [subject+action], [environment], [composition], [lighting], [style], [mood]. No Text. | --ar 9:16 --style raw --s 160 [--oref/--sref] | still |
| ... | ... | ... | ... | ... | still / --motion low / see I2V block below |

I2V PROMPTS (only for beats marked "see I2V block" above — omit this section if none)
| Beat | Source still | Target tool | I2V prompt | Start/end-frame notes |
|---|---|---|---|---|
| [Beat name] | [Beat/still # this clip animates] | [Kling / Seedance 2.0 / Veo 3 / etc. — one-line why] | [full motion prompt: framing, action, speed, "in a single shot, no cuts," "no subtitles and no music"] | [end frame description + how it was produced, or "single frame, no end-keyframe needed"] |
```

Write each row's still prompt to stand alone — Midjourney does not carry context between separate jobs
`[T]`, so a prompt that only makes sense as a continuation of the previous row will not render as
intended. An i2v prompt is the one exception that's *allowed* to depend on another row — it explicitly
names its source still as the start frame, per `references/image-to-video.md`.

## Corpus coverage note (state this to the user if asked how solid these rules are)

The prompt-anatomy/parameter/consistency rules (`references/midjourney-craft.md`) rest on a substantial
384-finding corpus across 4 dedicated Midjourney channels — reasonably durable for the `[C]`/`[I]`
fundamentals, though every `[T]` version/pricing/resolution fact is a 2026-07-23 snapshot that **should
be re-verified** at `docs.midjourney.com` before being treated as current (see the flagged list below).
The visual-*pacing* rules (`references/faceless-pacing-rules.md`) are a genuinely **thin corpus theme
(27 findings)** — say so rather than presenting them as heavily validated, and don't extend them into
specifics the corpus doesn't state (e.g. it doesn't give a precise "ideal" cut count, only "~3 seconds").
The image-to-video rules (`references/image-to-video.md`) rest on the guide's **single largest theme
(79 findings)** — well-supported for the `[C]` prompt-craft/technique rules, but the model-landscape
table (which tool is strong at what) is the part of this skill most likely to go stale fastest, since
external video-gen tools ship new versions far more often than Midjourney itself.

**`[T]` facts most likely to need re-verification before you rely on them:**
- V8.1 as the default model, native 2K HD, and the `--hd`/`--raw` split (features move fast).
- Omni Reference being V7-only (an improved V8 version was "in training" as of the snapshot).
- Plan pricing/tiers (Basic/Standard/Pro/Mega) and relax-mode/stealth-mode availability.
- MJ's video generator being capped at ~21s and topping out at 720p HD.
- The i2v model-landscape table in `references/image-to-video.md` (Kling/Veo/Seedance/Sora/Omni/Runway
  tiering, pricing, and per-model limits) — this is the fastest-moving part of the whole corpus.
