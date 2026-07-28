---
name: visual-prompts
description: Storyboards a shot-ready ContentStudio Short script into a visual prompt sheet — mapping each script beat to a shot count at the corpus's ~3-second visual cadence, deciding which beats need real animated motion versus a still, writing the image-to-video (i2v) prompt for any beat that does (Kling, Seedance, Veo, etc.), calling the cover/thumbnail decision, and assembling the whole sheet for handoff. Use this whenever the user has a scripted/timed Short (from shorts-scripting) and asks to "storyboard this script," "build the prompt sheet," "how many shots does this beat need," "which beats need motion/animation," "write the i2v prompt," "give me a Kling/Seedance prompt," or asks how to visualize a faceless Short beat by beat. The actual Midjourney prompt wording and parameter stack is NOT this skill's job — it delegates every still prompt to the `midjourney-prompting` skill, which owns V8.2 prompt craft, the flag stack, and consistency mechanics. Use that skill directly for a one-off image prompt with no Short script behind it.
---

# Visual Prompts (script beats → Midjourney prompt sheet)

## Pipeline position

- **Upstream input:** the shot-ready, timed script from `shorts-scripting` — a beat-by-beat breakdown
  (Hook / Setup / Build / Re-hook / Payoff / Loop-CTA, or whatever beats that skill emits) with a
  duration and VO line per beat. **Optionally**, a companion grounding artifact may also be handed
  to this skill directly (or reached via the script's own upstream chain) — see "Optional input"
  below.
- **This skill's job:** decide how each beat becomes pictures — the shot count per beat at the corpus's
  ~3-second cadence, which beats need real animated motion rather than a still, and whether the cover
  needs its own image — then assemble the sheet. **For any beat that genuinely needs motion, this skill
  writes the image-to-video (i2v) prompt itself** (Kling, Seedance, etc.), built from
  `references/image-to-video.md`. It also decides *which* whole-Short consistency mechanism applies.
- **Delegated to `midjourney-prompting`:** the wording of every still prompt and the parameter stack
  behind it. That skill owns the 9-layer prompt body, V8.2 flags, `--sref`/`--p`/`--oref` mechanics, the
  syntax lint, and GPU-cost discipline. Hand it each beat's visual note plus the stage; take back the
  prompt string. **Do not write Midjourney prompts or pick parameters here** — one copy of that truth,
  and it lives there.
- **Downstream:** the resulting prompt sheet — stills, i2v prompts, and cover prompt — feeds
  `shorts-assembly` **alongside** `voiceover-brief`'s output — assembly is the first skill that sees
  both the visuals and the voice spec together. `shorts-assembly` operates the tools, renders the
  clips/composites, and owns the edit, captions, and the audio side.
- **Not this skill's job:** Midjourney prompt anatomy, parameter selection, V8.2 model mechanics, or the
  consistency *implementation* — all `midjourney-prompting`. Nor actually operating an external i2v
  tool, rendering the video file, editing, captions, or the audio side — those belong to
  `shorts-assembly` and `voiceover-brief` respectively. This skill decides *whether* a beat needs a real
  clip and writes *the i2v prompt* for it; it does not run the render.

## Why this is grounded, not generic

Every prompt-construction rule now lives in the `midjourney-prompting` skill, itself grounded in
`docs/midjourney-prompting-guide.md` (384 findings, 4 dedicated Midjourney channels, dated 2026-07-23)
layered with a V8.2 delta web-verified 2026-07-26. The image-to-video rules (`references/image-to-video.md`) trace to the
same guide's §8 "Video generation & motion (image→video)" — its **largest single theme (79 findings)**,
so animating a beat properly is at least as well-supported as writing the still prompt for it. The
visual-*pacing* rules (how often to change the image, what look to avoid) trace to
`references/faceless-pacing-rules.md`, distilled from `docs/headless-youtube-audit.md` §6 — a **thin
corpus theme (27 findings)**, flagged as such rather than padded with invented "best practices." If you
find yourself about to write a rule with no `[C]`/`[I]`/`[T]` marker, stop — that's the signal you're
inventing instead of sourcing. Say the corpus doesn't cover it and move on.

## Optional input: a companion grounding artifact `[I]`

If a companion grounding artifact is handed to this skill, use its visual motif cue as a
shot-composition input for the beat(s) carrying that citation — fold the cue into step 2's
still-count decision and step 4's prompt anatomy for that beat, the same way any other visual
note is used.

This section does **not** add a quotability/quote-card gate — this skill never renders
on-screen text (every prompt ends "No Text," step 4 below); on-screen text and caption
decisions, including whether a citation is safe to render as a quote card, belong entirely to
`shorts-scripting`'s Delivery notes and `shorts-assembly`'s caption treatment. If no companion
artifact is provided, this section doesn't apply — build the prompt sheet normally.

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

### 3. Decide the whole-Short consistency *situation*, once

You decide **which situation the Short is in**; `midjourney-prompting` decides how to implement it and
what it costs.

| Situation | Hand down as |
|---|---|
| A recurring character/host appears across beats | `consistency: subject-lock` |
| No recurring character, but the Short should read as one look/brand | `consistency: style-lock` |
| Cheap/low-stakes, perfection not required | `consistency: style-lock`, `budget: cheap` |
| Subject-free b-roll/background plates | `consistency: none` |

Only one mechanism is normally active per Short. This "pick one" framing is this skill's own
operational guidance `[I]`, not a distinct corpus claim.

**Expect a pushback on `subject-lock`.** Attaching Omni Reference makes Midjourney run the whole job in
V7 at 2× GPU cost `[T] (verified 2026-07-26)` — so a character-driven Short cannot also have V8.2's
look. `midjourney-prompting` will surface that trade; carry it to the user rather than deciding for
them, because it may change whether the Short wants a recurring character at all.

### 4. Delegate each still prompt to `midjourney-prompting`

For each beat and still, hand down:

```
subject:      [the beat's visual note — what this still shows]
stage:        draft   (or refine / production, per where the Short is)
look:         [photographic | stylized | illustrative — from the packaging direction]
format:       9:16
consistency:  [from step 3, plus the locked --sref/--p code or --oref URL once it exists]
literalism / variance / budget: [defaults unless the beat needs otherwise]
```

Take back the prompt string and its parameters, and drop them into the sheet's row. **Do not rewrite
what comes back** — that skill's Gate A has already linted the syntax, ranges, and flag compatibility,
and re-editing the string here silently breaks that guarantee.

Two things you still own at this step:

- **On-screen text never enters the prompt.** Midjourney cannot reliably render legible text
  `[C] (Tokenized AI, qFYJb0zYztY)`, so a beat's hook card or caption copy passes through to
  `shorts-assembly` as overlay copy. Flag it in the handoff so `midjourney-prompting` appends `No Text.`
- **Beat-to-beat coherence.** Each prompt must stand alone — Midjourney carries no context between
  jobs `[T]` — but the *sheet* should read as one Short. If two adjacent beats come back looking
  unrelated, that's a step-3 problem (wrong consistency situation), not a prompt-wording problem.

### 5. Decide, per beat, whether a still suffices or the beat needs a real animated clip — and if so, write its i2v prompt

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

### 6. Decide the cover/thumbnail image

Read the packaging direction handed down from `shorts-ideation` (focal point, dominant emotion, what
it shows). Two outcomes, and this skill must state which one applies rather than silently skip the
decision:

- **The packaging direction wants something distinct from the Hook beat's still** (a different angle,
  a composed/staged shot built specifically to be a thumbnail rather than a video frame) → delegate a
  dedicated cover prompt to `midjourney-prompting`, handing down the guide's photoreal-thumbnail recipe
  (§13 recipe A) as the **subject/composition brief** `[I]` — close-up of the subject + defining
  feature, one expression/emotion, environment, dramatic rim lighting, shallow depth of field — with
  `look: photographic` and `stage: production` (a cover is a hero image, not a b-roll plate). The
  corpus's realism cue is **DSLR** `[C] (Tao Prompts, 2psBexPkw3I)`; `midjourney-prompting` will render
  that as concrete optics and drop the abstract "Photorealistic" per its buzzword rule. **Set `format`
  to wherever the cover actually renders** (9:16 for a Shorts-feed thumbnail, 16:9 for a separate
  widescreen slot) — this adaptation is this skill's own judgment `[I]`, not a corpus claim, since the
  guide's recipe was written for long-form 16:9 thumbnails, not Shorts.
- **The packaging direction is satisfied by the Hook beat's own still** → state this explicitly in the
  prompt sheet: "Cover = Hook still + `shorts-assembly`'s text overlay, no separate generation." Don't
  leave the decision implicit — an unstated cover is indistinguishable from a forgotten one.

### 7. Emit the prompt sheet

Use this shape (see `references/worked-example.md` for a full run of a real beat table through it):

```
=== VISUAL PROMPT SHEET — [Short ID / title] ===

WHOLE-SHORT SETUP
  Aspect ratio:     --ar 9:16
  Style/params:     [as returned by midjourney-prompting — e.g. --raw --s 95 --c 0]
  Consistency:      [subject-lock via --oref (NOTE: renders in V7) | style-lock via --sref CODE --sw N
                     | mood board --p CODE | fixed --seed N | none — subject-free plates]
  Notes:            [anything beat-specific that overrides the default]

COVER / THUMBNAIL
  [Dedicated prompt from midjourney-prompting — see step 6]
  — or —
  Cover = Hook beat still #1 + shorts-assembly's text overlay. No separate generation.

PER-BEAT PROMPTS
| Beat | Dur | Still # | Midjourney prompt | Params | Motion |
|---|---|---|---|---|---|
| Hook | 0-3s | 1 | [prompt string as returned by midjourney-prompting, ending "No Text."] | [flags as returned] | still |
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

The prompt-anatomy/parameter/consistency rules now live in the `midjourney-prompting` skill, which
carries its own coverage note and its own `[T]` staleness list — point the user there for how solid the
prompt craft is. The visual-*pacing* rules (`references/faceless-pacing-rules.md`) are a genuinely **thin corpus theme
(27 findings)** — say so rather than presenting them as heavily validated, and don't extend them into
specifics the corpus doesn't state (e.g. it doesn't give a precise "ideal" cut count, only "~3 seconds").
The image-to-video rules (`references/image-to-video.md`) rest on the guide's **single largest theme
(79 findings)** — well-supported for the `[C]` prompt-craft/technique rules, but the model-landscape
table (which tool is strong at what) is the part of this skill most likely to go stale fastest, since
external video-gen tools ship new versions far more often than Midjourney itself.

**`[T]` facts most likely to need re-verification before you rely on them:**
- Midjourney model/parameter facts — see `midjourney-prompting`'s own staleness list, which is current
  to 2026-07-26 rather than the corpus's 2026-07-23 snapshot.
- Plan pricing/tiers (Basic/Standard/Pro/Mega) and relax-mode/stealth-mode availability.
- MJ's video generator being capped at ~21s and topping out at 720p HD.
- The i2v model-landscape table in `references/image-to-video.md` (Kling/Veo/Seedance/Sora/Omni/Runway
  tiering, pricing, and per-model limits) — this is the fastest-moving part of the whole corpus.
