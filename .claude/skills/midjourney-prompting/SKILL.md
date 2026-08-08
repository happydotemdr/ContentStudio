---
name: midjourney-prompting
description: Writes best-in-class Midjourney V8.2 prompts and the parameter stack that goes with them — the 9-layer prompt body, the consistency mechanism (--sref, moodboard --p, Personalization, Omni Reference --oref, fixed seed), and a GPU-cost-aware phase ladder that explores in Draft Mode and only escalates to --hd when composition is locked, with a deterministic syntax lint on every prompt and a fresh-agent art-direction review before any expensive render. Use whenever the user wants a Midjourney image prompt or is working in Midjourney at any stage: "write me a Midjourney prompt," "improve this MJ prompt," "what parameters should I use," "how do I keep this character consistent across images," "build me a moodboard / style code / Personalization profile," "explore visual directions for X," "why does my prompt render generic," "what's --oref / --sref / --sw / --ow / --draft / --hd," "make this production-ready," "how do I stop burning GPU minutes." Covers every stage from moodboard curation and exploratory concepting through draft iteration to final commercial production renders. Works standalone for any image job AND as the prompt-writing specialist for ContentStudio's `visual-prompts` skill, which owns beat mapping and hands each beat's visual note down to this skill. Do not use this for image-to-video / motion prompts or for deciding how many stills a Short beat needs (both `visual-prompts`), or for captions and overlay text (`shorts-assembly`).
---

# Midjourney Prompting (V8.2 craft, parameters & GPU discipline)

Turns an image brief into an **executable Midjourney prompt**: the 9-layer body, the flag stack, the
consistency mechanism, and the phase to run it in — linted every time, and adversarially reviewed
before anything expensive renders.

## Pipeline position — this skill runs in two modes

**Standalone.** Any image job, ContentStudio-related or not: a product still, a brand moodboard, a
character sheet, an architectural visualization, exploratory concept work. Run the full workflow from
Step 0.

**Pipeline (ContentStudio Shorts).** `visual-prompts` (a stage of ContentStudio's eight-skill
pipeline, following `shorts-scripting`) owns the **beat
mapping** — how many stills a beat needs, what each one shows, and which beats need real motion. It
hands down a beat's visual note plus a forced stage, `register`, and `shot_class`; you convert that
into a prompt. **Accept its shot-count, visual-intent, register, and shot-class calls and do not
re-litigate them.**

The boundary, stated once so neither skill drifts into the other:

| `visual-prompts` owns | `midjourney-prompting` owns |
|---|---|
| Reading the script, listing beats, ~3s visual cadence | The 9-layer prompt body for each beat |
| How many stills a beat needs, and what each shows | Parameter selection and the V8.2 flag stack |
| Whether a beat needs a real animated clip, and its i2v prompt | The consistency mechanism and its cost/version trade |
| The cover/thumbnail *decision* | The cover/thumbnail *prompt* |
| The prompt-sheet artifact and its handoff to `shorts-assembly` | Phase ladder, GPU discipline, validation gates |

**Image-to-video and motion stay with `visual-prompts`**
(`.claude/skills/visual-prompts/references/image-to-video.md`) — this skill
is stills-only. Downstream of both: `shorts-assembly`.

## Grounding — read before writing any rule

Two sources, deliberately separate:

- **`references/v82-model-delta.md`** — platform truth. Web-verified against live `docs.midjourney.com`
  on **2026-07-26**, the day after V8.2 became default. **Read this first**; it is the tie-breaker.
- **`docs/midjourney-prompting-guide.md`** — the corpus view. 384 findings across four dedicated
  Midjourney YouTube channels, snapshot 2026-07-23, documenting **V8.1**.

Markers, copied verbatim wherever a rule is repeated:

- **`[T]`** web-verified 2026-07-26 · **`[T-unverified]`** asserted by the supplied V8.2 runbook but
  **not** confirmed — say so out loud when you use one · **`[C]`** corpus-cited `(Channel, video_id)`
  · **`[I]`** general practice or this skill's own judgment.

**Where a `[C]` corpus finding about model behavior conflicts with a verified `[T]` V8.2 fact, the
`[T]` fact wins — and both stay visible, with the reason.** Never silently delete a cited corpus line.

**A normative line with no marker means something was invented instead of sourced.** If the sources
don't cover it, say the gap exists and give a marked `[I]` extrapolation — never a confident unsourced
number. The supplied V8.2 runbook was **wrong in six places** (`references/v82-model-delta.md`); treat
plausible-sounding Midjourney "facts" from memory with the same suspicion.

## The control surface — the only inputs you need

Nine inputs, all defaulted. A bare subject is a valid request. **Infer what you can from the request,
then state every default you assumed** — never choose silently, and never interrogate the user with a
form before doing any work.

| Input | Values | Default | Drives |
|---|---|---|---|
| `subject` | free text | *required* | Layers 1–4 |
| `stage` | `moodboard` · `explore` · `profile` · `draft` · `refine` · `production` | `explore` | The whole phase ladder |
| `look` | `photographic` · `stylized` · `illustrative` | `photographic` | `--raw` on/off, `--s` band |
| `format` | where it renders | `9:16` in pipeline mode, else ask once | `--ar` |
| `consistency` | `none` · `style-lock` · `subject-lock` · `both` | `none` | `--sref` / `--p` vs `--oref` |
| `literalism` | `obey my words` ↔ `use your taste` | balanced | `--s` value |
| `variance` | `tight` · `some` · `wild` | `some` | `--c` |
| `budget` | `cheap` · `normal` · `no limit` | `normal` | `--q`, `--hd`/`--sd`, relax vs fast |
| `register` | `A` (present/photographic) · `B` (source-era/painterly) · `PLATE` · `n/a` | `n/a` | Overrides `look`; forces the parameter band |

Deterministic mappings — same inputs, same prompt, so a user can re-run and reproduce:

| Input value | Emits |
|---|---|
| `look: photographic` | `--raw`, `--s 80–120` |
| `look: stylized` | no `--raw`, `--s 250–400` |
| `look: illustrative` | no `--raw`, `--s 400–700` |
| `register: A` | `--raw`, `--s 80–120` — same as `look: photographic` |
| `register: B` | no `--raw`, `--s 400–700` — same as `look: illustrative`; **never** emit `DSLR`, `shot on 35mm film`, `documentary`, a focal length, or an f-stop |
| `literalism: obey my words` | `--s` toward the bottom of the band; add `--raw` |
| `literalism: use your taste` | `--s` toward the top of the band |
| `variance: tight` | `--c 0` |
| `variance: some` | `--c 3–9` `[C] (Future Tech Pilot, Tv1dfGcOSnA / fMEvMqvzUbc)` |
| `variance: wild` | `--c 25–50` |
| `consistency: style-lock` | `--sref <code>` + `--sw`, or moodboard `--p <code>` |
| `consistency: subject-lock` | `--oref <url> --ow 50–150` — **and the V7 warning below** |
| `budget: cheap` | `--relax`, stay in Draft/SD |
| `budget: no limit` | `--q 2`+ at production |

Full reasoning in `references/prompt-architecture.md` and `references/parameters.md`.

## Workflow

### Step 0 — Resolve the control surface

Infer the eight inputs. Echo them back in one compact block with every assumed default named. Proceed
without waiting for confirmation unless `format` is genuinely unknowable.

### Step 1 — Build the 9-layer prompt body

Read `references/prompt-architecture.md`. Order: medium → subject → action/pose/state → environment →
composition/angle → optics/lens/depth-of-field → lighting mechanics → color/atmosphere → parameters.

- **Front-load what matters** — Midjourney weights earlier words more heavily and words far back often
  fail to appear `[C] (Future Tech Pilot, ioJ6istzwHw)`.
- **Short beats long, standalone** — length dilutes which words get weighted `[C] (Tokenized AI,
  vezJXJGQMoY)`. Nine layers is not nine mandatory clauses; drop a layer that adds nothing. **In
  pipeline mode this changes**: all nine layers are mandatory with concrete content, minimum 10
  clauses and 60 words, enforced by Gate C's C12 (`references/prompt-architecture.md`, "Density, not
  length — the pipeline exception `[I]`").
- **No quality buzzwords** — `photorealistic`, `8k`, `masterpiece`, `ultra-detailed`, `trending on
  ArtStation`. Replace each with the concrete physical detail it was standing in for. *(That these
  actively degrade V8.2 is `[T-unverified]` — the ban stands on craft grounds, not model behavior.)*
- End with `No Text.` if the brief involves on-screen copy `[C] (Tokenized AI, qFYJb0zYztY)`.

### Step 2 — Pick the consistency mechanism, once

Read `references/style-systems.md`. One mechanism per project is normal `[I]`.

**If `consistency: subject-lock`, say this out loud before proceeding:** attaching `--oref` makes
Midjourney **run the whole prompt in V7**, at **2× GPU cost** `[T] (verified 2026-07-26)`. You cannot
have V8.2's aesthetic and subject-identity lock in the same job. If the look matters more than exact
likeness, `--sref` plus a strong text description keeps you in V8.2. Let the user choose knowingly.

### Step 3 — Phase 1, wide exploration (cheap)

`--draft` + `--sref random`, optionally with `{}` permutations to test several hypotheses in one
submission. 24 images at 512px for **0.4 GPU minutes — half the cost of SD**
`[T] (verified 2026-07-26)`. With Draft Mode, **every thumbnail gets a different style code**
`[T] (verified 2026-07-26)`, so one job samples 24 aesthetics for free.

Never `--hd`, never `--q 2`+, never `--oref` here (`--oref` is Draft-incompatible anyway). Emit the
draft command and **stop for their pick**. What happens to that pick depends on
which job this is `[I]`:

- **Style discovery** (`stage: moodboard` / `explore`) — harvest the winning thumbnail's
  style code; it becomes a Style Library entry, and the ladder terminates here.
  **Record it in `docs/style-library.md` before the session closes, in that file's
  `Entry format` shape** `[I]` — a harvested code that lives only in a Midjourney session
  is not recoverable by anyone else, and the pipeline reads the Library, not the session.
- **Asset rendering in the ContentStudio pipeline** — do *not* harvest. The style is
  already bound from the Library via the sheet's `{style:…}` slot and is present from the
  draft onward, so the pick chooses a *composition*, not a style. Drafting off-style would
  make the pick meaningless.

**`stage: moodboard`, `explore`, and `profile` terminate here.** They never escalate. That is the core
token-discipline promise, and Gate A enforces it.

### Step 4 — Phase 2, compositional lock (standard)

Drop `--draft`, stay `--sd`. Carry the same style reference the draft ran under — the harvested `--sref <code>` in a
discovery job, or the Library-bound `{style:…}` slot in a pipeline job. Changing the style
between rungs invalidates the composition you just chose `[I]`. Attach
`--oref --ow 50–150` if subject-lock was chosen. Add optics and lighting specificity. Drop `--c` toward
0. Validate framing and lighting **here**, at 0.8 GPU minutes, not at 1.3.

### Step 5 — Phase 3, production render (expensive)

`--hd` (2048px, 1.3 min) plus `--q 2` for surface detail or `--q 4` for multi-subject complexity.
`--raw` if the look is photographic. Watch two traps `[T] (verified 2026-07-26)`: `--hd` caps `--ar` at
**4:1**, and **`--q 4` is incompatible with `--oref`**. Expect the HD image to **differ from the SD
version even at the same seed** `[C][T] (Future Tech Pilot, Tv1dfGcOSnA / t_xIYKk2ERk)`.

**→ Gate B fires here, and only here.**

### Step 6 — Archive

Emit the reproduction record. Record the resolved `--p code`, **not the `mID`** — moodboard codes
change as the board grows `[T] (verified 2026-07-26)`. Midjourney carries no context between jobs
`[T]`, so the archived string must stand alone.

### Step 7 — Pipeline handoff (pipeline mode only)

Return the prompt and parameters to `visual-prompts` for its per-beat table row. Do not emit a full
production spec — that skill owns the sheet.

## Validation gates

Full checklists and the verbatim dispatch prompt are in `references/validation-gates.md`.

| Gate | Fires | Cost | Checks |
|---|---|---|---|
| **A — syntax & compatibility** | **every prompt, always** | free, inline | flags last / spacing / no punctuation; every value in range; `--oref` ✗ Draft·Fast·`--q 4`; moodboard ✗ `--sv`·`--sw`; `--ar` ≤ 4:1 under `--hd`; no buzzwords; **stage discipline** — no `--hd`/`--q 2`+/`--oref` in an exploratory stage; every line marked |
| **B — adversarial art direction** | **`production` only** | one fresh agent | weakest of the 9 layers; where literal reading bites; what's buried too late to render; flag stack vs stated intent; one concrete rewrite |

In pipeline mode, `visual-prompts` runs a third gate, **Gate C**, over the assembled prompt sheet
(`scripts/lint_prompt_sheet.py`) — this skill does not run it; it only produces prompts that satisfy it.

Gate B dispatches a **fresh `general-purpose` agent** that has **not** seen your authoring rationale —
it judges the artifact, not the reasoning — and is instructed to *find the failure*, not approve.
Fresh-agent validation is a net-new pattern for this repo `[I]`; no corpus finding backs it.

**A failing gate blocks emission** until resolved or explicitly overridden. If Gate B's rewrite touches
parameters, **re-run Gate A on it**. Report gate results in the output; **never claim a gate passed
without running it**, and write `Gate B: n/a — [stage]` rather than omitting the line.

## Output contract

```
=== MIDJOURNEY PROMPT — [job name] — [STAGE] ===

CONTROL SURFACE
  subject / stage / look / format / consistency / literalism / variance / budget
  Assumed defaults: [every value chosen for the user, named]

CONSISTENCY
  [mechanism, why, and its cost/version trade — or "none needed", stated]

PROMPT
  [full prompt string, parameters last]

LAYER BREAKDOWN
  1 medium · 2 subject · 3 state · 4 environment · 5 composition
  6 optics · 7 lighting · 8 color · 9 parameters
  [what each layer contributes; note any deliberately omitted]

PARAMETERS
  [each flag with a one-line why]

COST
  This job: [GPU min]   Ladder so far: [draft → sd → hd]

VALIDATION
  Gate A: [pass | findings]   Gate B: [pass | findings | n/a — stage]

ARCHIVE
  prompt / seed / --sref or --p code / --oref url + --ow / model version / date

NEXT
  [discovery job: harvest a style code → lock composition → production. Pipeline job: no
  harvest — style already bound; proceed to the pipeline handoff.]
```

In pipeline mode, collapse this to the prompt + parameters + one-line why — `visual-prompts` owns
the sheet.

## What this skill does NOT do

- **Render anything.** It emits prompt strings; you run them in Midjourney. It never spends GPU time.
- **Image-to-video, motion, or i2v prompts** — `visual-prompts`
  (`.claude/skills/visual-prompts/references/image-to-video.md`).
- **Decide how many stills a Short beat needs, or the ~3s cadence** — `visual-prompts`.
- **Captions, overlay text, or the edit** — `shorts-assembly`. Midjourney can't render legible text
  anyway `[C] (Tokenized AI, qFYJb0zYztY)`.
- **Voice or audio** — `voiceover-brief`, then `elevenlabs-audio`.

## `[T]` facts most likely to be stale — re-verify before relying on them

V8.2 shipped 2026-07-24 and was verified 2026-07-26. This is a **two-day-old snapshot of a model that
had been default for one day** — the shortest-lived `[T]` layer in this repo.

- Whether `--oref` still falls back to **V7**, or a native V8 Omni Reference has shipped. This single
  fact changes the consistency decision more than any other.
- GPU costs: draft 0.4 / SD 0.8 / HD 1.3 minutes, and the `--q` 2×/4× multipliers.
- Whether a **Global V8 Personalization Profile** now exists (there was none at verification).
- `--sv` behavior in V8 — currently **undocumented**, hence omitted by default.
- Draft Mode remaining web-only, and its 24-image / 512px shape.
- The 4:1 aspect-ratio ceiling under `--hd`.
- Plan tiers and relax-mode availability.

Anything marked **`[T-unverified]`** — V8.2 "prompt literalism," buzzword degradation, wall-clock render
times, moodboard image caps, Style Creator round counts, `--stylize` scaling Personalization, and
cross-account profile sharing — is a starting point, never a fact. State the uncertainty when it matters.

## Reference files

- `references/v82-model-delta.md` — **start here.** V8.1→V8.2 changes, corpus corrections, the
  `[T-unverified]` quarantine, and sources.
- `references/prompt-architecture.md` — the 9 layers, the buzzword ban, `--raw` and the stylize bands.
- `references/parameters.md` — every parameter, its range, and the compatibility matrix.
- `references/style-systems.md` — `--sref`, moodboards, Personalization, Omni Reference, fixed seed.
- `references/render-economics.md` — the cost ladder, the three phases, stages that never escalate.
- `references/validation-gates.md` — Gate A checklist and Gate B's verbatim dispatch prompt.
- `references/worked-example.md` — one job end to end: inputs → draft → lock → gates → production.
