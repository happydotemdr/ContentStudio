---
name: visual-prompts
description: Storyboards a shot-ready ContentStudio Short script into a visual prompt sheet using dual-register visual storytelling — consuming the world lock from `shorts-styleboard`, mapping each script beat to a shot count at the corpus's ~3-second visual cadence, building the whole shot sequence as an arc and passing it through Gate C before any prompt is written, deciding which beats need real animated motion versus a still, writing the image-to-video (i2v) prompt for any beat that does (Kling, Seedance, Veo, etc.), calling the cover/thumbnail decision, and assembling the whole sheet for handoff. Use this whenever the user has a scripted/timed Short (from shorts-scripting) and asks to "storyboard this script," "build the prompt sheet," "lock the world/registers," "how many shots does this beat need," "which beats need motion/animation," "write the i2v prompt," "give me a Kling/Seedance prompt," "run Gate C," or asks how to visualize a faceless Short beat by beat. The actual Midjourney prompt wording and parameter stack is NOT this skill's job — it delegates every still prompt to the `midjourney-prompting` skill, which owns V8.2 prompt craft, the flag stack, and consistency mechanics. Use that skill directly for a one-off image prompt with no Short script behind it. Does NOT lock the world or pick the sport — that is `shorts-styleboard`, which runs before this skill.
---

# Visual Prompts (script beats → Midjourney prompt sheet)

## Pipeline position

- **Upstream input:** the shot-ready, timed script from `shorts-scripting` — a beat-by-beat breakdown
  (Hook / Setup / Build / Re-hook / Payoff / Loop-CTA, or whatever beats that skill emits) with a
  duration and VO line per beat. **Optionally**, a companion grounding artifact may also be handed
  to this skill directly (or reached via the script's own upstream chain) — see "Optional input"
  below.
- **This skill's job:** read the world lock `shorts-styleboard` already decided — Register A/present,
  Register B/source-era, the sport, and the `slot_*` bindings, per step 2.5 below — then plan the whole
  sheet as a shot-by-shot arc (scale, camera height, shot class, register) per `references/visual-arc.md`,
  and only then decide how each beat becomes pictures: the shot count per beat at the corpus's ~3-second
  cadence, which beats need real animated motion rather than a still, and whether the cover needs its own
  image `[I]`. **For any beat that genuinely needs motion, this skill writes the image-to-video (i2v)
  prompt itself** (Kling, Seedance, etc.), built from `references/image-to-video.md`.
- **Delegated to `midjourney-prompting`:** the wording of every still prompt and the parameter stack
  behind it. That skill owns the 9-layer prompt body, V8.2 flags, `--sref`/`--p`/`--oref` mechanics, the
  syntax lint, and GPU-cost discipline. Hand it each beat's visual note plus the stage; take back the
  prompt string. **Do not write Midjourney prompts or pick parameters here** — one copy of that truth,
  and it lives there.
- **Downstream:** the resulting prompt sheet — stills, i2v prompts, and cover prompt — feeds
  `shorts-assembly` **alongside** `voiceover-brief`'s output — assembly is the first skill that sees
  both the visuals and the voice spec together. `shorts-assembly` operates the tools, renders the
  clips/composites, and owns the edit, captions, and the audio side.
- **Not this skill's job:** locking the world, picking the sport, or deciding the whole-Short consistency
  situation (`subject-lock` / `style-lock` / `none`) — all `shorts-styleboard`, which runs before this
  skill and hands its decisions down in the styleboard artifact `[I]`. Nor Midjourney prompt anatomy,
  parameter selection, V8.2 model mechanics, or the consistency *implementation* — all
  `midjourney-prompting`. Nor actually operating an external i2v tool, rendering the video file, editing,
  captions, or the audio side — those belong to `shorts-assembly` and `voiceover-brief` respectively. This
  skill decides *whether* a beat needs a real clip and writes *the i2v prompt* for it; it does not run the
  render.

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

The register system (`references/visual-registers.md`), its shot-class taxonomy, and the arc-first
sequencing discipline (`references/visual-arc.md`) are **this skill's own operational design `[I]`** —
the corpus has nothing to say about pairing a present-day register with a source-era register, or about
sequencing a shot table before writing prompts. The thin `[C]` §6 pacing theme cited above backs the
cautions those files guard against (stale frames, uncanny-valley motion), and the `[T]` Midjourney
parameter bands they cite are web-verified against `docs.midjourney.com` — but the register/arc/Gate C
system itself is not presented as corpus-derived, and neither file should be read as if it were.

## Optional input: a companion grounding artifact `[I]`

If a companion grounding artifact is handed to this skill, its motif cue still informs
shot-composition for the beat(s) carrying that citation — fold it into step 2's still-count
decision and step 4's prompt anatomy for that beat, the same way any other visual note is used.
The artifact's thinker/source and motif populating the `register_b_*` keys and `motif` key
themselves is `shorts-styleboard`'s job, not this skill's (see step 2.5) — `shorts-styleboard`
is fed the same grounding artifact upstream, so the world lock you read at step 2.5 should
already reflect it `[I]`.

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

### 2.5. Read the world lock — do not decide it

The world lock is `shorts-styleboard`'s output, not yours. Read the styleboard artifact
handed to you and inherit its 11 `register_a_*` / `register_b_*` / `motif` keys and its
`slot_*` declarations unchanged `[I]`. **Do not re-emit the `WORLD LOCK` block into your
sheet** — one home, no sync rule needed.

If no styleboard artifact was supplied, stop and say so rather than inventing a world:
an invented world lock produces invented `--sref` codes, which is the defect this split
removed `[I]`.

Every `--sref` in your prompts is a **slot**, never a literal code: `{style:register_a}`
for Register A shots, `{style:register_b}` for Register B, `{char:<name>}` where the
styleboard declares a character binding. Slots go **last in the flag block**, after
`--ar`/`--raw`/`--s` — before the first ` --` they are parsed as prompt body and Gate C's
**C18** rejects them `[I]`.

### 3a. Read the consistency situation the styleboard chose — do not decide it

Which situation the Short is in — `subject-lock`, `style-lock` (with or without
`budget: cheap`), or `none` — is `shorts-styleboard`'s decision
(`shorts-styleboard/SKILL.md` step 2), not yours `[I]`. Read whatever it hands down in
the styleboard artifact and carry it unchanged into every `midjourney-prompting`
delegation (step 4 below); `midjourney-prompting` decides how to implement it and what
it costs.

`style-lock` is the styleboard's default for both registers, resolved through the two
`slot_register_a` / `slot_register_b` bindings it declares rather than a literal code
`[I]`. Register B's archetype-figure treatment — unnamed, face averted or in shadow,
dressed to the role, never a specific likeness — is precisely what makes `subject-lock`
unnecessary there: there is no likeness to lock `[I]`.

**Expect a pushback on `subject-lock`.** Attaching Omni Reference makes Midjourney run the whole job in
V7 at 2× GPU cost `[T] (verified 2026-07-26)` — so a character-driven Short cannot also have V8.2's
look. `midjourney-prompting` will surface that trade; carry it to the user rather than deciding for
them, because it may change whether the Short wants a recurring character at all.

### 3b. Build the visual arc

Before writing a single prompt string, lay out the whole shot sequence as a table — one row per shot,
columns `# | Beat | Register | Shot class | Scale | Camera height | What changes vs. previous` — per
`references/visual-arc.md` §3 `[I]`. This is not cosmetic: fixing a repetitive arc later means editing a
table row, not rewriting prompt strings that were written under the wrong plan, and it happens before
any GPU minute is spent `[I]`.

**Check the table by eye against the sequence/balance rules now — this is a manual pre-check, not a tool
run.** Rotate scale (at least 3 distinct values), camera height (at least 2 distinct values), shot class,
and register across the table, and make sure no run of more than 2 consecutive shots shares the same
register, per `references/visual-arc.md` §4–§7. This is the primary instruction for this step: read down
the table and confirm it, row by row, before a single prompt string is written. There is no tool to run
against a plain arc table at this stage — `scripts/lint_prompt_sheet.py` parses the `### Shot N — ...`
heading-plus-fenced-prompt format that only exists once prompts have been written (step 7), so it cannot
be run here; catch repetition and imbalance by eye against the rules above instead.

The **mechanical, mandatory** Gate C run — the actual `scripts/lint_prompt_sheet.py` command, which
blocks emission on failure — happens once at step 7, after the sheet has real shot headings and prompts
to parse. This step's eyeball check exists to make that later run pass on the first try, not to replace
it.

### 4. Delegate each still prompt to `midjourney-prompting`

For each beat and still, hand down:

```
subject:      [the beat's visual note — what this still shows]
stage:        draft   (or refine / production, per where the Short is)
look:         [photographic | stylized | illustrative — from the packaging direction]
format:       9:16
consistency:  [from step 3a, plus the register's {style:register_a}/{style:register_b} slot
              (or {char:<name>} slot) from the styleboard]
register:     [A | B | PLATE — from the arc table row (step 3b)]
shot_class:   [the register's own taxonomy value for this row, e.g. DETAIL / FIGURE / ESTABLISHING]
literalism / variance / budget: [defaults unless the beat needs otherwise]
```

Take back the prompt string and its parameters, and drop them into the sheet's row. **Do not rewrite
what comes back** — that skill's Gate A has already linted the syntax, ranges, and flag compatibility,
and re-editing the string here silently breaks that guarantee.

Two things you still own at this step:

- **On-screen text never enters the prompt.** Midjourney cannot reliably render legible text
  `[C] (Tokenized AI, qFYJb0zYztY)`, so a beat's hook card or caption copy passes through to
  `shorts-assembly` as overlay copy. Flag it in the handoff so `midjourney-prompting` appends `No Text.`
- **Sheet-level coherence is Gate C's job, not a judgment call.** Whether the sheet reads as one Short
  with real shot-to-shot variety is a mechanical question at emission — `scripts/lint_prompt_sheet.py`
  runs mandatorily at step 7 against the finished sheet, rather than eyeballing whether two adjacent
  beats "look related" `[I]`. Step 3b's by-eye check of the arc table exists to catch the same
  repetition/imbalance earlier, while it's still a one-cell table edit, but it is a manual check, not a
  tool run — the CLI itself only becomes runnable once the sheet has real shot headings and prompts
  (step 7). If Gate C fails at step 7, the fix is almost always the arc table's sequencing (revisit
  step 3b's rules), not individual prompt wording.
- **Do not achieve consistency by repeating a shared style-vocabulary string across prompts.** Cloning a
  style phrase (or an entire prompt body with a noun swapped) into every prompt is exactly what produced
  six near-identical stills in a real production run — see `references/visual-arc.md` §1. Consistency
  lives in the register's style slot, not in the prompt body. Gate C's **C11** enforces this mechanically
  (no two shots may share more than 5 identical prompt-body clauses) `[I]`.

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

The exact, byte-level output shape — the `{style:...}`/`{char:...}` slot-token rule, the per-shot heading
and fence syntax, the one-line prompt rule, and the remaining sheet sections (`WHOLE-SHORT SETUP`,
cover/thumbnail, I2V block, overlay-copy handoff, validation line) — now lives in
`references/prompt-sheet-format.md`.
Read it before emitting; it is the literal format `scripts/lint_prompt_sheet.py`'s parser accepts, and a
sheet that drifts from it (wrong dash, wrong case, a missing field) has shots silently skipped by the
parser, not flagged. See `references/worked-example.md` for a full run of a real beat table through it.

Skeleton (see `references/prompt-sheet-format.md` §2–§7 for the exact syntax of every piece below):

```
=== VISUAL PROMPT SHEET — [Short ID / title] ===

WHOLE-SHORT SETUP
  Aspect ratio:     --ar 9:16
  Register A style: {style:register_a}   [resolved from the styleboard's binding at generate time]
  Register B style: {style:register_b}   [resolved from the styleboard's binding at generate time]
  Styleboard:       [path to the styleboard artifact this sheet was built against]
  Phase ladder:      [the ordered beat list this sheet covers]
  Notes:             [anything beat-specific that overrides the default]

COVER / THUMBNAIL
  [Dedicated prompt from midjourney-prompting — see step 6]
  — or —
  Cover = Hook beat still #1 + shorts-assembly's text overlay. No separate generation.

### Shot <N> — <Beat> (<time range>) · Register <A|B|PLATE> · <SHOT CLASS> · <SCALE> · <CAMERA HEIGHT>
Changes vs. previous: <one line naming the visual change>

```text
<the entire prompt on ONE line>
```

I2V PROMPTS (only for beats marked "see I2V block" above — omit this section if none)
| Beat | Source still | Target tool | I2V prompt | Start/end-frame notes |
|---|---|---|---|---|
| [Beat name] | [Beat/still # this clip animates] | [Kling / Seedance 2.0 / Veo 3 / etc. — one-line why] | [full motion prompt: framing, action, speed, "in a single shot, no cuts," "no subtitles and no music"] | [end frame description + how it was produced, or "single frame, no end-keyframe needed"] |

OVERLAY COPY HANDOFF
  [any on-screen text/hook-card copy kept out of the Midjourney prompt — step 4]

VALIDATION
  Gate A (midjourney-prompting syntax lint): [pass/fail]
  Gate B (upstream visual-quality check, if applicable): [pass/fail]
  Gate C (scripts/lint_prompt_sheet.py):     [pass/fail — see below]
```

Write each row's still prompt to stand alone — Midjourney does not carry context between separate jobs
`[T]`, so a prompt that only makes sense as a continuation of the previous row will not render as
intended. An i2v prompt is the one exception that's *allowed* to depend on another row — it explicitly
names its source still as the start frame, per `references/image-to-video.md`.

**Before emitting the sheet, run Gate C — this is mandatory, not optional:**

```bash
python scripts/lint_prompt_sheet.py <path-to-sheet.md>
```

**A failing gate blocks emission.** Exit 0 is the only outcome that allows handing the sheet downstream;
exit 1 (findings) or exit 2 (nothing parsed — almost always a format error, see
`references/prompt-sheet-format.md`) means fix the sheet and re-run, not report it as done anyway. Never
state or record Gate C as "passed" without having actually run it and observed exit 0 `[I]`
(`references/visual-arc.md` §9).

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

The dual-register system (`references/visual-registers.md`), the arc-first sequencing discipline
(`references/visual-arc.md`), and the copy-paste output contract (`references/prompt-sheet-format.md`)
are **this skill's own operational design `[I]`**, not corpus findings — the corpus's thin §6 visuals
theme (27 findings) says nothing about registers, shot-class taxonomies, arc sequencing, or a
machine-parseable output format. Say so plainly if asked how solid these three files are: the pacing
cautions they build on (`[C]`) and the Midjourney parameter bands they cite (`[T]`, verified 2026-07-26)
are sourced; the register system, the shot classes, the arc discipline, Gate C's checks, and the sheet
format itself are not — they are this skill's answer to a gap the corpus leaves open.

**`[T]` facts most likely to need re-verification before you rely on them:**
- Midjourney model/parameter facts — see `midjourney-prompting`'s own staleness list, which is current
  to 2026-07-26 rather than the corpus's 2026-07-23 snapshot.
- Plan pricing/tiers (Basic/Standard/Pro/Mega) and relax-mode/stealth-mode availability.
- MJ's video generator being capped at ~21s and topping out at 720p HD.
- The i2v model-landscape table in `references/image-to-video.md` (Kling/Veo/Seedance/Sora/Omni/Runway
  tiering, pricing, and per-model limits) — this is the fastest-moving part of the whole corpus.

## File I/O contract

This skill participates in ContentStudio's file-based pipeline handoff (see
`docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md`). Two modes:

**App-driven** (a `pipeline-app` turn already told you an output path): follow that instruction
exactly — write only to the named path, overwrite it each turn as instructed. Do not also write
to `rgs-briefs/` in this mode.

**Standalone** (no output path was given):

1. Resolve the upstream script: run
   `python scripts/resolve_brief_version.py --slug <slug> --kind script` from the repo root. Read
   the file it reports, and follow its `concept_brief:` pointer field if you need packaging
   direction.
   **Staleness check:** re-run the resolver for `--kind script` again right before you finish —
   if a newer version now exists than the one you read, tell the user before proceeding.
2. Before writing the prompt sheet, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind visual-prompts` from the repo
   root (no `--next`). If it prints a path (not `NONE`), that's the current version being
   superseded — remember its printed path verbatim for the `supersedes:` field below; it's already
   `rgs-briefs/`-relative, don't prepend `rgs-briefs/` again.
3. After emitting the prompt sheet, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind visual-prompts --next --date <YYYY-MM-DD>`.
   Write the file at `rgs-briefs/<filename>` via the `Write` tool with this frontmatter (in
   addition to the prompt sheet's own output format above):

   ```yaml
   ---
   date: <YYYY-MM-DD>
   kind: visual-prompts
   slug: <slug>
   stage: 03-visual
   version: <version from the resolver>
   supersedes: <path from step 2 above — only if version > 1>
   script: <the script file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative, don't prepend rgs-briefs/ again>
   concept_brief: <carried through from the script, if present>
   archetype: <carried through from the script / concept brief, if present>
   visual_system: <path to a run-level visual-system document, if one was provided>
   motif_family: <the visual motif family this Short uses, if you named one while building the sheet>
   status: complete
   ---
   ```
4. State the exact file path you wrote in your final chat response.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this.
