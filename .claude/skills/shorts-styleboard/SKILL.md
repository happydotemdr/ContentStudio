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

## Optional input: a companion grounding artifact `[I]`

If a grounding artifact was produced for this Short (`rgs-grounding`), its thinker/source and its
motif populate the `register_b_thinker`, `register_b_era_place`, `register_b_locations`,
`register_b_artifacts`, `register_b_figure_archetype` and `motif` keys **directly** — they are
inherited, never invented here. Its topic and claim also constrain the Register A sport (step 1).
If no companion artifact was provided, this section doesn't apply — lock the world from the script
alone.

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
`references/visual-registers.md` §7 — **thirteen keys** (5 `register_a_*`, 5 `register_b_*`,
`motif`, `slot_register_a`, `slot_register_b`) under the `WORLD LOCK` heading, the block every
downstream prompt inherits from `[I]`. The block below is the contract; the count is stated only
so a truncated emission is visible:

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
must tie it to the claim's evidence `[I]` (`references/visual-registers.md` §8). State the rationale
under this artifact's own `BINDINGS` section as well as in `register_a_rationale`, so a reader sees
the sport choice without parsing the world-lock block `[I]`. **Do not write into the prompt sheet**
— that artifact belongs to `visual-prompts`, is byte-level linted by Gate C, and its own rule is "do
not re-emit the WORLD LOCK block — one home, no sync rule needed." If a grounding artifact was handed to
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
codes** — one per register (`references/visual-registers.md` §3–§4) `[I]`. **Each code's scope is
whatever its entry in `docs/style-library.md` records, not something to assume** `[I]`: for
RaisingGoodSports both registers are `scope: channel` as of 2026-08-08 — one durable code each,
reused unchanged on every subsequent Short. Register A was originally specified as harvested per
Short; the Library supersedes that.
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

**The Style Library is `docs/style-library.md`. Read it before binding anything** `[I]` — it is
the only record of which worlds already have an entry, so neither decision in this step can be
made without it.

Name the Library entry each register binds to, as a `slot_*` line in the world lock and
a one-line rationale under `BINDINGS` `[I]`. If a world has no Library entry yet, say so
under `DISCOVERY REQUESTS` rather than inventing a code — an invented `--sref` is the
exact defect this stage exists to eliminate `[I]`. A discovery request raised without reading
`docs/style-library.md` first is a guess, not a finding: the world may already be covered `[I]`.

### 4. Emit the styleboard artifact

Per `references/styleboard-format.md`.

## Handoff contract (machine-checked)

```handoff
produces.kind: styleboard
produces.stage: 02b-styleboard
produces.section: WORLD LOCK
produces.section: BINDINGS
produces.section: DISCOVERY REQUESTS
consumes: shorts-scripting#HOOK
consumes: shorts-scripting#Visual notes
consumes: shorts-ideation#Angle / take
consumes: rgs-grounding#Handoff
reads: docs/style-library.md
```

## File I/O contract

**Artifact vocabulary — one table, copied unchanged into every skill.** The resolver matches
filenames literally, so a `--kind` guessed from a stage id or a skill name returns `NONE` and
exit 1 — which this section documents as the benign "upstream hasn't run yet" case. Copy the
literal string from this table; never infer it `[I]`.

| Stage id (`pipeline.yaml`) | `--kind` | `stage:` frontmatter | Owning skill |
|---|---|---|---|
| `grounding` | `grounding` | `00-grounding` | `rgs-grounding` |
| `ideation` | `concept-brief` | `01-ideation` | `shorts-ideation` |
| `scripting` | `script` | `02-scripting` | `shorts-scripting` |
| `styleboard` | `styleboard` | `02b-styleboard` | `shorts-styleboard` |
| `voiceover` | `voiceover-brief` | `03-voiceover` | `voiceover-brief` |
| `visual` | `visual-prompts` | `03-visual` | `visual-prompts` |
| `music` | `music` | `03-music` | `music-brief` |
| `assembly` | `assembly` | `04-assembly` | `shorts-assembly` |
| `repurpose` | `social-repurpose` | `05-repurpose` | `social-repurpose` |
| — (specialist) | `audio-spec` | `03-voiceover` | `elevenlabs-audio` |
| — (specialist) | `music-spec` | `03-music` | `elevenlabs-music` |
| — (specialist) | *none — transcript-only* | — | `midjourney-prompting` |

This skill participates in ContentStudio's file-based pipeline handoff (see
`docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md`). Two modes:

**App-driven** (a `pipeline-app` turn already told you an output path): follow that instruction
exactly — write only to the named path, overwrite it each turn as instructed. Do not also write
to `rgs-briefs/` in this mode.

**Standalone** (no output path was given):

1. Resolve the upstream script: run
   `python scripts/resolve_brief_version.py --slug <slug> --kind script` from the repo root. Read
   the file it reports.
   **Then resolve the two other sources step 1 of the workflow requires you to check before
   picking a sport yourself** `[I]`:
   - the concept brief — `python scripts/resolve_brief_version.py --slug <slug> --kind concept-brief`;
   - the grounding brief — `python scripts/resolve_brief_version.py --slug <slug> --kind grounding`,
     or the path in the script's `grounding:` frontmatter if present.
   `NONE` from either is a legitimate "not produced for this Short" and is not an error — but a
   sport picked without running both resolves is a guess presented as a check.
   **Staleness check:** re-run the resolver for `--kind script` again right before you finish —
   if a newer version now exists than the one you read, tell the user before proceeding.
2. Before writing the styleboard, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind styleboard` from the repo
   root (no `--next`). If it prints a path (not `NONE`), that's the current version being
   superseded — remember its printed path verbatim for the `supersedes:` field below; it's already
   `rgs-briefs/`-relative, don't prepend `rgs-briefs/` again.
3. After emitting the styleboard, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind styleboard --next --date <YYYY-MM-DD>`.
   Write the file at `rgs-briefs/<filename>` via the `Write` tool with this frontmatter (in
   addition to the styleboard's own output format above):

   ```yaml
   ---
   date: <YYYY-MM-DD>
   kind: styleboard
   slug: <slug>
   stage: 02b-styleboard
   version: <version from the resolver>
   supersedes: <path from step 2 above — only if version > 1>
   script: <the script file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative, don't prepend rgs-briefs/ again>
   status: complete
   ---
   ```
4. State the exact file path you wrote in your final chat response — `visual-prompts` needs it
   for its own `--styleboard`/`styleboard:` resolution step.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this.

## Reference files

- `references/visual-registers.md` — the two-world system, both register contracts, the
  world-lock block, and how to choose the sport.
- `references/styleboard-format.md` — the exact artifact shape Gate C parses.
