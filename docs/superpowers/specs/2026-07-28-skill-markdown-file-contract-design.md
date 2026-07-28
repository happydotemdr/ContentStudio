# Skill markdown file contract — design spec

Date: 2026-07-28
Status: Approved

## Problem

The six generic pipeline skills (`shorts-ideation`, `shorts-scripting`,
`voiceover-brief`, `visual-prompts`, `shorts-assembly`, `social-repurpose`)
produce their output as markdown text inside the chat response only. Nothing
gets written to disk. Handoff between stages currently depends on the human
copy-pasting one skill's chat output into the next skill's prompt — there is
no file on disk that later skills, `pipeline-app`, or a future session can
read.

`rgs-briefs/` already holds real, well-formatted examples of what this output
*should* look like — e.g.
`rgs-briefs/2026-07-28-decline-the-next-level-concept-brief.md` through
`...-social-repurpose.md` — but that file family is currently produced only
by the RGS-specific `rgs-grounding` skill (for grounding briefs) and by
`pipeline-app`'s own internal orchestration, not by the six generic skills
themselves. Running any of the six generic skills standalone in a Claude Code
session today writes nothing to disk.

Separately, `pipeline-app`'s stage page
(`pipeline_app/routes/stages.py` → `templates/stage.html`) renders artifact
bodies as raw text inside `<pre>` tags, so markdown syntax (`#`, `-`, etc.)
shows up literally instead of rendering as headers/lists. The app's own MD
Inspector (`pipeline_app/routes/inspector.py`) already renders markdown
correctly via the `markdown` library (already a dependency) — the stage page
just never adopted the same call.

## Goals

- Every one of the six generic pipeline skills writes its output to
  `rgs-briefs/` as a well-formed markdown file with frontmatter, matching the
  schema `pipeline-app` already produces.
- Files in `rgs-briefs/` are **immutable once written**. A skill never edits
  an existing file — including its own prior output. Revising a stage's
  output produces a new, explicitly versioned file; the old one is left
  untouched.
- Downstream skills read the upstream skill's **file**, not chat-pasted text,
  as their primary input path. Chat-pasted text remains a fallback for
  standalone use.
- Immutability is enforced technically, not just by prose instruction: a
  `PreToolUse` hook blocks `Edit` on `rgs-briefs/**` and blocks `Write` to a
  filename that already exists there.
- The two RGS-specific skills (`rgs-grounding`, `rgs-pairing-review`) adopt
  the same version/supersedes convention, so the whole directory has one rule
  for "updating a file."
- `pipeline-app`'s stage page renders markdown as HTML instead of raw text.

## Non-goals

- No change to `pipeline-app`'s separate internal `runs/<run_id>/<stage_dir>/
  artifact.vN.md` convention (`pipeline_app/artifacts.py`). That schema
  belongs to the app's own turn/approval state machine and is out of scope
  here — this spec only touches `rgs-briefs/`, which is a distinct file
  family read by `rgs-grounding`, `rgs-pairing-review`, and now the six
  generic skills.
- No generalizing `rgs-briefs/` into a brand-neutral directory name (e.g.
  `briefs/<brand>/`). RGS is the only active brand today; revisit if/when a
  second brand needs the pipeline.
- No per-skill-identity permission scoping. Claude Code hooks match on tool
  name and file path, not "which skill is currently active" — there is no
  primitive for that, so enforcement is directory-level and applies uniformly
  regardless of what's driving the tool call (a skill or a manual edit).
- No change to `midjourney-prompting` or `elevenlabs-audio` (the tool
  specialist skills) — they're invoked *within* `visual-prompts` and
  `voiceover-brief` and don't independently touch `rgs-briefs/`.

## Design

### 1. Frontmatter schema per stage

Extends the schema already visible in real `rgs-briefs/` files, adding
`version`/`supersedes` for the versioning rule (§3):

| Skill | `kind` | `stage` | Upstream pointer fields |
|---|---|---|---|
| `shorts-ideation` | `concept-brief` | `01-ideation` | `grounding:` (optional — only if a companion grounding artifact was used) |
| `shorts-scripting` | `script` | `02-scripting` | `concept_brief:`, `grounding:` (carried through if present) |
| `voiceover-brief` | `voiceover-brief` | `03-voiceover` | `script:`, `concept_brief:`, `grounding:` |
| `visual-prompts` | `visual-prompts` | `03-visual` | `script:`, `concept_brief:` |
| `shorts-assembly` | `assembly` | `04-assembly` | `script:`, `voiceover_brief:`, `visual_prompts:` |
| `social-repurpose` | `social-repurpose` | `05-repurpose` | `script:`, `assembly:`, `concept_brief:` |

Every file also carries `date`, `slug`, `version`, `status` (`complete` or
`draft`), and `supersedes:` (only present when `version > 1`). `run:` and
`archetype:` remain optional passthroughs from an `rgs-grounding` companion
artifact — the generic skills never invent them.

Voiceover and visual share `stage: 03-*` because both depend only on the
script and can run in parallel — matches the existing pipeline-nav model
(`pipeline.yaml`'s `dir_prefix` grouping, see
`docs/superpowers/specs/2026-07-27-pipeline-nav-redesign-design.md`).

### 2. Naming

`YYYY-MM-DD-<slug>-<stage>.md`, e.g.
`2026-07-28-decline-the-next-level-script.md` — matches the existing
`rgs-briefs/README.md` convention exactly, no changes needed there.

### 3. Versioning (new)

Files are immutable. A skill asked to revise an existing stage output writes
a new file instead of overwriting:

- First write: `YYYY-MM-DD-<slug>-<stage>.md`, frontmatter `version: 1`, no
  `supersedes:` field.
- A revision: `YYYY-MM-DD-<slug>-<stage>-v2.md` (then `-v3`, …), frontmatter
  `version: 2`, `supersedes: rgs-briefs/YYYY-MM-DD-<slug>-<stage>.md`.

The prior version is never mutated — no `status: superseded` edit. Any
consumer resolves "current" for a given `<slug>-<stage>` by globbing
`rgs-briefs/YYYY-MM-DD-<slug>-<stage>*.md` and taking the highest `version:`
found in frontmatter (not by filename sort alone, since `-v2` through `-v9`
sort before `-v10` lexically — parse the frontmatter field).

This same rule extends to `rgs-grounding` (grounding briefs) and
`rgs-pairing-review`'s writes — one immutability/versioning rule for the
whole directory.

### 4. Skill workflow changes

Each of the six `SKILL.md` files gains:

- **A "resolve upstream input" step** (replaces "the user pastes the
  previous output"): glob `rgs-briefs/` for the highest-version file matching
  the expected upstream `<slug>-<stage>`, read it, and follow its own
  pointer fields to resolve anything further upstream it references. Chat-
  pasted content is still accepted as a fallback when no file exists yet
  (e.g. a first standalone run with no prior stage file).
- **A "write the output file" step** at the end: construct frontmatter per
  the table in §1, determine the next version number per §3, write via the
  `Write` tool.
- **An explicit statement of the file path(s) read and written**, included
  in the skill's final chat output, so the human handoff to the next skill
  names the exact file rather than relying on memory.

`rgs-grounding` and `rgs-pairing-review` get the equivalent update to their
existing file-writing logic: adopt `version`/`supersedes`, never edit an
existing brief in place.

### 5. Enforcement hook

New `.claude/hooks/protect-briefs.py`, registered as a `PreToolUse` hook in
`.claude/settings.json` matching `Edit|Write`:

- `Edit` targeting any path under `rgs-briefs/**` → deny. Files in this
  directory are never edited in place, by a skill or by hand.
- `Write` targeting a path under `rgs-briefs/**` that already exists on disk
  → deny. A write must target a new, not-yet-existing filename (i.e. the
  next version).
- Any other tool call, or any path outside `rgs-briefs/**` → pass through
  unchanged.

This enforces immutability at the directory/file level regardless of what's
driving the tool call — there's no Claude Code primitive for "only skill X
may write here," so the hook can't distinguish "the `shorts-scripting` skill
is writing its own output" from "something else is trying to write into
`rgs-briefs/`." The practical effect is the same either way: nothing in this
directory can be silently clobbered.

### 6. `pipeline-app` markdown rendering fix

`pipeline_app/routes/stages.py`: run `input_body`/`output_body` through
`markdown.markdown(...)` before passing to the template (same call already
used correctly in `pipeline_app/routes/inspector.py`).

`pipeline_app/templates/stage.html`: replace
`<pre>{{ input_body }}</pre>` / `<pre>{{ output_body }}</pre>` with
`{{ input_html | safe }}` / `{{ output_html | safe }}`, wrapped in a plain
`<div>` instead of `<pre>`.

No new dependency — `markdown==3.7.*` is already in
`pipeline-app/requirements.txt`.

## Testing

- Each of the six skills: run standalone end-to-end (idea → repurpose copy)
  and confirm each stage's file appears in `rgs-briefs/` with correct
  frontmatter, correct upstream pointers, and `version: 1`.
- Revision case: re-run one skill against an already-produced stage and
  confirm it writes `-v2` rather than overwriting `-v1`, and that
  `supersedes:` points at the right file.
- Hook: attempt an `Edit` on an existing `rgs-briefs/*.md` file and confirm
  it's denied; attempt a `Write` to an already-existing filename and confirm
  it's denied; confirm a `Write` to a new filename succeeds.
- `pipeline-app`: load a stage page for a stage with existing markdown output
  and visually confirm headers/lists/tables render as HTML, not literal
  `#`/`-` characters. Confirm the MD Inspector page still renders correctly
  (regression check — it already worked, shouldn't change).
