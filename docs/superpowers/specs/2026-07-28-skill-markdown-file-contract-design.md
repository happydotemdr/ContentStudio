# Skill markdown file contract — design spec

Date: 2026-07-28
Status: Approved (revised post Opus review — see "Revision notes")

## Revision notes

An Opus-model review of the first draft found four blocking issues, folded
into this version:

1. `pipeline-app`'s `stage_templates/*.md` already instruct each of the six
   skills to overwrite `runs/<run_id>/<stage_dir>/raw_output.md` every turn
   when the app is driving the conversation. §4 now makes the `rgs-briefs/`
   write conditional on standalone use, so app-driven turns are unaffected.
2. `grounding_service.supersede_previous_brief()` (`pipeline_app/
   grounding_service.py:42-51`) renames the previous grounding brief into
   `rgs-briefs/.superseded/` — a mutation outside the `Edit`/`Write` hook's
   visibility, and incompatible with "never mutate an existing file." §3 and
   §7 now retire it in favor of the same versioned-filename convention used
   everywhere else in this spec.
3. The hook (§5) had no concrete input/output contract. Rewritten with the
   actual `PreToolUse` stdin/exit-code contract and its known blind spots.
4. Nothing detected a downstream file's upstream pointer going stale after a
   revision. §4 adds an explicit staleness check to the "resolve upstream
   input" step.

Also folded in: the schema table (§1) was missing fields actually present in
real files (`visual_system`, `motif_family`, `total_runtime_seconds`), and
version resolution is now a tested script rather than something the model
computes by eyeballing a glob.

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
  `PreToolUse` hook (`.claude/hooks/protect_briefs.py`) blocks `Edit` on
  `rgs-briefs/**` and blocks `Write` to a filename that already exists there.
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
`draft`), and `supersedes:` (only present when `version > 1`). `archetype:`
is an optional passthrough from an `rgs-grounding` companion artifact.
`run:` is **not** a generic-skill field — it's stamped by run-level batch
documents (e.g. `2026-07-28-rgs-debut-sparks.md`), not by grounding briefs or
by the six generic skills; omit it unless a run-level document supplied one.
`visual_system:` (script, visual-prompts, assembly), `motif_family:`
(visual-prompts only), and `total_runtime_seconds:` (script, voiceover-brief)
are additional real fields observed in `rgs-briefs/` — carry them through
when the corresponding upstream file has them, but the generic skills never
invent values for them.

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

The prior version is never mutated — no `status: superseded` edit. Version
resolution is **not** left to the model eyeballing a glob: `scripts/
resolve_brief_version.py` (new, §7) is the single source of truth for "what's
the latest version of `<slug>-<stage>`" and "what filename/version number
does the next write use." It reads frontmatter (not filename suffixes —
`-v2` through `-v9` sort before `-v10` lexically, so filename-only sorting is
wrong) and is unit-tested. Skills run it via `Bash` rather than computing the
answer themselves.

**Grounding briefs adopt the same convention**, replacing today's two
different mutation behaviors (overwrite-in-place on a same-day rerun;
rename-to-`.superseded/` on a cross-day rerun — both removed, see §7):
naming becomes `YYYY-MM-DD-<topic-slug>.md` (v1) →
`YYYY-MM-DD-<topic-slug>-v2.md` (v2), regardless of whether the rerun
happens the same day or a later one. `rgs-pairing-review` and
`rgs-grounding`'s own recency/repeat glob (`references/
thinker-corpus-protocol.md`) must resolve to the latest version per
topic-slug — an older version of the same topic must not be double-counted
as a second, separate use of its thinker/concept pairing.

**Race handling:** this is a single-user local tool; no locking is added.
If two writes ever did target the same next-version filename, the hook (§5)
denies the second `Write` outright (the target path already exists by the
time it runs) rather than silently overwriting — a loud failure, not silent
corruption.

### 4. Skill workflow changes

Each of the six `SKILL.md` files gains:

- **A mode check, first.** If the invoking prompt already names an output
  path to write to (this is how `pipeline-app` drives a turn — see
  `pipeline_app/prompt_builder.py`'s `raw_output_path` templating), the
  skill is running **app-driven**: write only to that path, following
  whatever instruction the prompt gives (today: overwrite it each turn).
  Do **not** also write to `rgs-briefs/` in this mode — that stays
  `pipeline-app`'s job via its own `runs/.../artifact.vN.md` convention
  (unchanged, see Non-goals). Otherwise the skill is running **standalone**
  and the steps below apply.
- **A "resolve upstream input" step** (replaces "the user pastes the
  previous output"): run `scripts/resolve_brief_version.py --slug <slug>
  --stage <upstream-stage>` to get the latest file, read it, and follow its
  own pointer fields to resolve anything further upstream it references.
  **Staleness check:** for each resolved pointer field (e.g. a script's
  `concept_brief:` value), re-run the resolver for that file's own
  `<slug>-<stage>` — if a newer version exists than the one named in the
  pointer, flag it to the user ("your concept brief has a newer version
  than the one this script was built from — rebuild against v2, or confirm
  you want to keep this script pinned to v1") rather than silently using
  the stale reference. Chat-pasted content is still accepted as a fallback
  when no file exists yet (e.g. a first standalone run with no prior stage
  file).
- **A "write the output file" step** at the end: construct frontmatter per
  the table in §1, run `scripts/resolve_brief_version.py --slug <slug>
  --stage <this-stage> --next` to get the exact next filename/version, write
  via the `Write` tool.
- **An explicit statement of the file path(s) read and written**, included
  in the skill's final chat output, so the human handoff to the next skill
  names the exact file rather than relying on memory.

`rgs-grounding` and `rgs-pairing-review` get the equivalent update to their
existing file-writing logic: adopt `version`/`supersedes` via the same
resolver script, never edit an existing brief in place (§3, §7).

### 5. Enforcement hook

New `.claude/hooks/protect_briefs.py`, registered as a `PreToolUse` hook in
`.claude/settings.json` (created new — only `settings.local.json` exists
today) matching `Edit|Write`:

**Contract:**
- Claude Code invokes the hook with the tool-call JSON on **stdin**:
  `{"tool_name": "Edit"|"Write", "tool_input": {"file_path": "<absolute
  path>", ...}, ...}`.
- `tool_input.file_path` is **absolute**. Resolve it relative to
  `$CLAUDE_PROJECT_DIR` (the env var Claude Code sets to the session's
  project root — for a worktree session, that's the worktree root, so
  `rgs-briefs/` means `$CLAUDE_PROJECT_DIR/rgs-briefs/`, not the main repo's).
- To **deny**: exit code `2` with the reason on **stderr**. Claude Code
  blocks the tool call and surfaces stderr to the model. To **allow**: exit
  `0` with no stdout/stderr.

**Logic** (pure function, unit-tested separately from the stdin/exit-code
wrapper — see §7):
- `tool_name == "Edit"` and the resolved path is under `rgs-briefs/` → deny.
- `tool_name == "Write"`, the resolved path is under `rgs-briefs/`, and that
  exact path already exists on disk → deny.
- Everything else → allow.

**Known blind spot, accepted as a limitation, not fixed here:** the hook
only sees `Edit`/`Write` tool calls. `Bash` commands that mutate files
directly (`mv`, `sed -i`, shell redirection) are not intercepted by an
`Edit|Write` matcher and bypass this entirely. Closing that would mean
gating all of `Bash`, which is far broader than this spec's scope. The six
`SKILL.md` files and `rgs-grounding`/`rgs-pairing-review` are instructed to
never use `Bash` to write into `rgs-briefs/` — the hook is a backstop against
accidental `Edit`/`Write` clobbers, not a hard sandbox against a
deliberately adversarial actor.

This enforces immutability at the directory/file level regardless of what's
driving the tool call — there's no Claude Code primitive for "only skill X
may write here," so the hook can't distinguish "the `shorts-scripting` skill
is writing its own output" from "something else is trying to write into
`rgs-briefs/`." The practical effect is the same either way for the cases it
does cover: nothing in this directory can be silently clobbered via `Edit`
or an overwrite `Write`.

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

### 7. Version-resolution script and grounding-service retirement

New `scripts/resolve_brief_version.py` (repo root, alongside
`scripts/lint_prompt_sheet.py`): given `rgs-briefs/`, a slug (or topic-slug
for grounding briefs), and a stage (omit for grounding briefs), returns the
latest existing file's path/version, or (with `--next`) the exact
filename/version number the next write should use. Parses frontmatter via
`pyyaml` (already a `pipeline-app` dependency; add to root `requirements.txt`
for standalone-skill use outside `pipeline-app`'s venv). Malformed or
missing frontmatter on a file matching the naming pattern is treated as an
error the script reports, not silently skipped — a broken file in this
ledger should surface immediately, not get quietly ignored by version
resolution.

`pipeline_app/grounding_service.py`'s `supersede_previous_brief()` (lines
42-51) and its call site (`pipeline_app/routes/stages.py:169`) are removed.
Grounding briefs now always get a new versioned filename on regeneration —
same-day or cross-day — so there is nothing left to archive; `write_pointer`
simply points at the new file. `identify_new_brief()` and `snapshot_rgs_briefs()`
are unchanged and remain correct under this scheme (verified: a versioned
write is always exactly one new filename appearing, which is exactly what
`identify_new_brief`'s "len(changed) == 1" check already detects).
`test_supersede_archives_previously_pointed_file` and
`test_supersede_is_a_no_op_when_no_pointer` in `tests/test_grounding_service.py`
are removed along with the function they test.

## Testing

- **`scripts/resolve_brief_version.py`** (`tests/test_resolve_brief_version.py`,
  pytest, no filesystem side effects beyond `tmp_path`): no existing files →
  next is v1; one v1 file → next is v2; v1 and v2 present → latest resolves
  to v2 (not v1, and not lexical-sort-fooled by a hypothetical v10 case);
  malformed frontmatter → raises/reports rather than silently skipping.
- **`.claude/hooks/protect_briefs.py`**: the core decision function
  (`decide(tool_name, resolved_path) -> bool`, or equivalent) gets direct
  pytest unit tests — Edit under rgs-briefs/ → deny; Write to new path under
  rgs-briefs/ → allow; Write to existing path under rgs-briefs/ → deny; any
  tool/path outside rgs-briefs/ → allow. Separately, one end-to-end check
  (documented as a manual step, since it requires actually invoking Claude
  Code's hook runner): trigger an `Edit` on a real `rgs-briefs/*.md` file
  and confirm it's blocked with the expected stderr message.
- **`pipeline_app/grounding_service.py`**: existing `identify_new_brief`/
  `snapshot_rgs_briefs` tests continue to pass unmodified; the two
  `supersede_previous_brief` tests are deleted along with the function.
- **Six skills, end-to-end** (manual, standalone mode): run idea → repurpose
  copy and confirm each stage's file appears in `rgs-briefs/` with correct
  frontmatter, correct upstream pointers, and `version: 1`.
- **Revision case** (manual): re-run one skill against an already-produced
  stage and confirm it writes `-v2` rather than overwriting `-v1`, that
  `supersedes:` points at the right file, and that a downstream file still
  pointing at `-v1` gets flagged as stale the next time it's read.
- **`pipeline-app` markdown rendering**: a route-level test in
  `tests/test_routes_stages.py` (matching the existing pattern in
  `tests/test_routes_inspector.py`) asserts the stage page's response body
  contains rendered HTML (e.g. `<h2>`) for a markdown heading in a fixture
  artifact, not the literal `##` text. Manual: load a stage page with real
  markdown output and visually confirm headers/lists/tables render;
  confirm the MD Inspector page is unaffected (regression check).
