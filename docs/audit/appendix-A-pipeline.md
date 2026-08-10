# Appendix A — Pipeline Core

## T1 — Stage graph & handoff correctness

**Scope.** This section audits the declared stage graph and the first-turn handoff machinery
only: `pipeline.yaml` (repo root), `pipeline-app/pipeline_app/turn_service.py`,
`pipeline-app/pipeline_app/prompt_builder.py`, `pipeline-app/pipeline_app/pipeline_config.py`,
and the nine kickoff templates in `pipeline-app/stage_templates/`. Skill `SKILL.md` files,
`routes/`, `gates.py`, `approval_service.py`, `artifacts.py` and `db.py` were read as evidence
but are **not** owned here — issues found in them are handed off rather than filed. Documentation
only; nothing was changed. Findings extend the confirmed seeds SEED-3 and SEED-4 rather than
re-deriving them.

### Q1 — The nine-stage matrix

Legend: **Declared** = the required input each stage's `SKILL.md` states. **Reachable** = what
`turn_service.py:133,139-143,147` can actually place in the prompt, which is exactly
`depends_on`. **Interpolated** = the Jinja variables the stage's kickoff template actually
consumes (verified by AST walk of every template).

| # | Stage | Declared-required input (`SKILL.md`) | Reachable via `depends_on` | Kickoff template interpolates | Agree? |
|---|---|---|---|---|---|
| 1 | `grounding` | none — raw RGS topic (`rgs-grounding/SKILL.md:18`) | none (`pipeline.yaml:5`) | `skill`, `user_message`. No input path, no `raw_output_path`, no `grounding_pointer` | **agree** — output is harvested from `rgs-briefs/` by `routes/stages.py:162-189`, so omitting `raw_output_path` is correct |
| 2 | `ideation` | none; optional companion grounding artifact (`shorts-ideation/SKILL.md:18,25-33`) | none (`pipeline.yaml:10`) | `skill`, `user_message`, `grounding_pointer`, `raw_output_path` | **agree** — the optional input arrives out-of-band |
| 3 | `scripting` | `shorts-ideation` concept brief (`shorts-scripting/SKILL.md:17`) | `ideation` (`pipeline.yaml:14`) | `input_file` (singular), `grounding_pointer`, `raw_output_path` | **agree** |
| 4 | `styleboard` | `shorts-scripting` timed script (`shorts-styleboard/SKILL.md:10`) | `scripting` (`pipeline.yaml:18`) | `input_file` (singular), `grounding_pointer`, `raw_output_path` | **agree** |
| 5 | `voiceover` | `shorts-scripting` timed script (`voiceover-brief/SKILL.md:14`) | `scripting` (`pipeline.yaml:24`) | `input_file` (singular), `grounding_pointer`, `raw_output_path` | **agree** |
| 6 | `visual` | script + styleboard world lock/`slot_*` bindings (`visual-prompts/SKILL.md:10,15-16`) | `scripting`, `styleboard` (`pipeline.yaml:30`) | `input_files` (loop), `grounding_pointer`, `raw_output_path` | **agree** (see A-16 on unlabelled paths) |
| 7 | `music` | script **and** voiceover tone-per-beat call, both required (`music-brief/SKILL.md:18-19`) | `scripting`, `voiceover` (`pipeline.yaml:36`) | `input_files` (loop), `grounding_pointer`, `raw_output_path` | **agree on inputs**; graph leaf — nothing consumes its output (**A-02**) |
| 8 | `assembly` | script (1), voiceover brief (2), visual sheet (3) all required; music bed optional (`shorts-assembly/SKILL.md:16-29`); styleboard `BINDINGS` needed to resolve slot tokens (`shorts-assembly/SKILL.md:31-39`) | `voiceover`, `visual` **only** (`pipeline.yaml:40`) | `input_files` (loop), `raw_output_path`. **No `grounding_pointer`** | **DISAGREE** — script unreachable (**A-01**), bed arc unreachable (**A-02**), styleboard unreachable (**A-03**), grounding dropped (**A-04**) |
| 9 | `repurpose` | finished Short's script + packaging direction from ideation + edit plan (`social-repurpose/SKILL.md:12-13`); must honor a "constraints that survive to publish" line (`social-repurpose/SKILL.md:17`) | `assembly` **only** (`pipeline.yaml:44`) | `input_file` (**singular**), `raw_output_path`. **No `grounding_pointer`** | **DISAGREE** — script and packaging direction unreachable while `repurpose.md:3` asserts both are present (**A-01**), grounding dropped (**A-04**) |

### Q2 — Template variable supply

Context supplied at `turn_service.py:148-155` is exactly six keys: `skill`, `user_message`,
`grounding_pointer`, `input_file`, `input_files`, `raw_output_path`. An AST walk of all nine
templates finds **no template referencing a name outside that set**, so there is no
currently-undefined variable rendering as empty string. The exposure is forward-looking and
real: `prompt_builder._environment` (`prompt_builder.py:7-11`) uses Jinja's default `Undefined`,
and the templates are operator-editable through the app (**A-08**). Separately, `input_file`
is passed as Python `None` rather than left undefined, so it renders as the literal string
`None` rather than empty (**A-07**).

### Q3 — Singular vs plural input templates

Singular `{{ input_file }}`: `scripting.md:3`, `styleboard.md:3`, `voiceover.md:3`,
`repurpose.md:3`. Plural `{% for f in input_files %}`: `visual.md:6-8`, `music.md:4-6`,
`assembly.md:5-7`. No input at all: `grounding.md`, `ideation.md`.

**Count of singular-input templates on a multi-dependency stage today: zero.** All four
singular templates sit on single-dependency stages, so SEED-4's ordering hazard is currently
latent, not live. It is unguarded rather than prevented (**A-09**), and it converts to a live
bug the moment `repurpose` gains the script dependency that SEED-3/A-01 calls for.

### Q4 — `grounding_pointer` reach

Supplied out-of-band at `turn_service.py:151`, sourced at `routes/stages.py:157-160` for any
non-`grounding` stage on a `raisinggoodsports` project. **Consumed by six of nine templates**:
`ideation.md:3-7`, `scripting.md:5-8`, `styleboard.md:9-13`, `voiceover.md:4-7`,
`visual.md:13-16`, `music.md:7-10`. **Not consumed by** `grounding.md` (correct — never passed),
`assembly.md`, and `repurpose.md` (both bugs — **A-04**).

For non-RGS projects the value is `None`, every `{% if grounding_pointer %}` guard is false, and
the block renders as nothing at all — clean, no stray whitespace or literal `None`. That path is
correct.

---

### A-01 · Script unreachable at `assembly`/`repurpose` while both templates assert it is present

- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline.yaml:40`, `pipeline.yaml:44`, `pipeline-app/stage_templates/repurpose.md:3`, `pipeline-app/stage_templates/assembly.md:3-7`, `pipeline-app/pipeline_app/turn_service.py:133`, `pipeline-app/pipeline_app/turn_service.py:147`
- **component**: pipeline
- **failure_mode**: silent
- **blast_radius**: Extends SEED-3 with the template half. `repurpose.md:3` renders "Read the finished Short's script and edit plan at `<one path>`" — a single edit-plan path described as two documents — so the final, publish-facing stage is told the script is in a file that does not contain it. `assembly.md:3-7` lists only the two reachable artifacts under a prose instruction that assumes the script set. Both stages will either write from the edit plan alone or reconstruct script content from memory; hook language, beat timing and AEO specifics in the published copy are then unverifiable against the actual script.
- **trigger**: Every first turn of `assembly` and `repurpose` on every project.
- **proposed_fix**: Add `scripting` to both stages' `depends_on` (and `ideation` to `repurpose`, for the packaging direction its SKILL.md requires), then convert `repurpose.md` to the plural `input_files` form so it stops naming a single path as two documents.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T1
- **detected_by**: manual-trace

### A-02 · `music` is a graph leaf — its bed arc can never reach `assembly`

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline.yaml:31-36`, `pipeline.yaml:37-40`, `pipeline-app/pipeline_app/turn_service.py:133`, `pipeline-app/pipeline_app/turn_service.py:100`
- **component**: pipeline
- **failure_mode**: silent
- **blast_radius**: No stage lists `music` in `depends_on`, so `_dependents_of` returns empty for it and `input_files` at `assembly` never contains the bed arc. `shorts-assembly/SKILL.md:20-25` has a dedicated branch for consuming the bed arc, hook hold-out and asset filename — that branch is dead through the app, and assembly always takes the "absent" path. A regenerated bed arc also never marks `assembly` stale. The stage runs, costs a turn, produces an approved artifact, and influences nothing.
- **trigger**: Any project that runs the `music` stage at all.
- **proposed_fix**: Model the optional edge explicitly — either add `music` to `assembly.depends_on` and let `assembly` tolerate a missing artifact, or introduce an `optional_depends_on` field that `turn_service` folds into `input_files` when an artifact exists and omits otherwise.
- **fix_cost**: M
- **depends_on_finding**: [A-01]
- **owner_task**: T1
- **detected_by**: manual-trace

### A-03 · Styleboard `BINDINGS` unreachable at `assembly`, whose SKILL.md requires them

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline.yaml:30`, `pipeline.yaml:40`, `pipeline-app/stage_templates/assembly.md:3-7`, `pipeline-app/pipeline_app/turn_service.py:133`
- **component**: pipeline
- **failure_mode**: silent
- **blast_radius**: `shorts-assembly/SKILL.md:31-39` instructs the stage to resolve every `{style:...}` / `{char:...}` token in the prompt sheet by reading the styleboard's `BINDINGS` line and looking the label up in `docs/style-library.md`. `assembly.depends_on` is `[voiceover, visual]`, so the styleboard artifact is never in `input_files`. The edit plan is therefore authored with unresolved slot tokens and no binding table; the operator gets an edit plan that silently defers a required lookup, and `shorts-assembly/SKILL.md:39-40`'s own warning ("pasting the token as literal text renders the words 'style register a' into the image") is exactly the failure this omission invites.
- **trigger**: Every `assembly` first turn on a project whose prompt sheet carries slot tokens (i.e. all of them — Gate C rejects literal `--sref` codes).
- **proposed_fix**: Add `styleboard` to `assembly.depends_on` so its `BINDINGS` line travels with the prompt sheet, or have `assembly.md` name the styleboard path explicitly out-of-band the way `grounding_pointer` is passed.
- **fix_cost**: S
- **depends_on_finding**: [A-01]
- **owner_task**: T1
- **detected_by**: manual-trace

### A-04 · `grounding_pointer` is supplied to `assembly`/`repurpose` but neither template uses it

- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/turn_service.py:151`, `pipeline-app/stage_templates/assembly.md:1-11`, `pipeline-app/stage_templates/repurpose.md:1-9`, `pipeline-app/pipeline_app/routes/stages.py:157-160`, `pipeline-app/pipeline_app/routes/stages.py:197`
- **component**: pipeline
- **failure_mode**: silent
- **blast_radius**: The app resolves and passes a valid grounding pointer for every non-`grounding` stage on an RGS project, and six of nine templates render it. `assembly.md` and `repurpose.md` reference no such variable, so the value is computed, passed, and discarded with no log or warning. `social-repurpose/SKILL.md:17` explicitly requires honoring a "constraints that survive to publish" line — e.g. a mandatory safety-resource mention — carried by the grounding brief. That constraint reaches the last stage only if some intermediate artifact happened to copy it forward verbatim. A compliance-shaped constraint can therefore vanish between grounding and published copy with nothing marking its loss.
- **trigger**: Any RaisingGoodSports project reaching the `assembly` or `repurpose` stage.
- **proposed_fix**: Add the same `{% if grounding_pointer %}` block the other six templates carry to `assembly.md` and `repurpose.md`, worded for their stages. Separately, treat a supplied-but-unreferenced context key as a load-time or test-time error so the next template can't silently drop it.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T1
- **detected_by**: manual-trace

### A-05 · Re-run never re-renders kickoff, yet records provenance on the new upstream

- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/turn_service.py:145`, `pipeline-app/pipeline_app/turn_service.py:157-159`, `pipeline-app/pipeline_app/turn_service.py:139-143`, `pipeline-app/pipeline_app/turn_service.py:234-237`
- **component**: pipeline
- **failure_mode**: silent
- **blast_radius**: `is_first_turn` is `claude_session_id is None`, and nothing in the codebase ever clears that column (only `db.update_stage_session` writes it, `db.py:84-85`). Re-running a stage after an upstream regenerated therefore sends only the operator's raw chat message with `--resume`; the session transcript still names `artifact.v1.md`, and the model is never told `artifact.v2.md` exists. Meanwhile `depends_on` in the new artifact's frontmatter is built at `:234-237` from `upstream_paths`, which was recomputed at `:139-143` against the **current** latest artifacts — so the artifact asserts it was built on v2. `state_machine.is_stale` then reports False forever. The staleness system actively launders the mismatch: clicking through a stale stage clears the staleness signal whether or not the model re-read anything.
- **trigger**: Approve a stage, edit or regenerate its upstream, then send any chat message to the now-stale downstream stage.
- **proposed_fix**: On a resumed turn where the upstream artifact set differs from what the session last saw, prepend an explicit change notice naming the new paths — or clear `claude_session_id` when a stage goes stale so the next turn re-renders the kickoff against current paths.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T1
- **detected_by**: manual-trace

### A-06 · An unresumable `claude_session_id` permanently wedges a stage

- **severity**: S2
- **confidence**: probable
- **evidence**: `pipeline-app/pipeline_app/turn_service.py:145`, `pipeline-app/pipeline_app/turn_service.py:159`, `pipeline-app/pipeline_app/turn_service.py:178-183`, `pipeline-app/pipeline_app/turn_service.py:219-220`
- **component**: pipeline
- **failure_mode**: loud
- **blast_radius**: The session id is captured from the `system/init` event and never cleared, including on the abort path. If the CLI's session store is pruned, the machine changes, or the repo is moved so the session no longer resolves, every subsequent turn passes `--resume <dead-id>`, fails, and lands the stage in `no_artifact`. Because `is_first_turn` stays False, the kickoff prompt can never be re-rendered, so there is no in-app recovery — the operator must edit the DB. The turn does fail visibly, so the failure is loud, but the wedge is permanent.
- **trigger**: App restart or environment change after which the recorded CLI session is no longer resumable.
- **proposed_fix**: Detect a resume failure in the result event and clear `claude_session_id` for that stage so the next turn falls back to a fresh kickoff, or expose a "start a new session for this stage" control.
- **fix_cost**: M
- **depends_on_finding**: [A-05]
- **owner_task**: T1
- **detected_by**: manual-trace

### A-07 · Missing upstream artifact renders the literal string `None` into the prompt

- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/turn_service.py:139-143`, `pipeline-app/pipeline_app/turn_service.py:152`, `pipeline-app/stage_templates/scripting.md:3`, `pipeline-app/stage_templates/styleboard.md:3`, `pipeline-app/stage_templates/voiceover.md:3`, `pipeline-app/stage_templates/repurpose.md:3`
- **component**: pipeline
- **failure_mode**: silent
- **blast_radius**: `input_file` is passed as Python `None`, not left undefined, so Jinja stringifies it. A render probe of `scripting.md` with `input_file=None` produces ``Read the concept brief at `None` `` — a plausible-looking path the model will try to read, fail on, and then work around. The plural case degrades differently: `input_files=[]` makes the `{% for %}` body vanish, so `assembly.md`/`music.md`/`visual.md` render "Read the following upstream artifacts:" followed by nothing. The state machine keeps this narrow (a stage is `locked` until every dependency is approved), so it needs an approved-then-deleted or relocated artifact to fire — but nothing in `turn_service` treats an empty `upstream_by_stage` on a stage that declares dependencies as an error.
- **trigger**: Start a turn on a stage whose dependency is approved but whose artifact file is missing from `run_dir` (deleted, moved, or restored from a partial copy).
- **proposed_fix**: Refuse to start a turn when a declared dependency resolves to no artifact, raising the same class of error as `StageNotRunnableError` rather than rendering a prompt that names a nonexistent path.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T1
- **detected_by**: manual-trace

### A-08 · Jinja default `Undefined` makes a typo in an operator-edited template render empty

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/prompt_builder.py:7-11`, `pipeline-app/pipeline_app/prompt_builder.py:14-17`, `pipeline-app/pipeline_app/routes/skills.py:91-94`
- **component**: pipeline
- **failure_mode**: silent
- **blast_radius**: The environment is built with neither `undefined=StrictUndefined` nor a `finalize` hook, so any name not in the six-key context renders as empty string with no exception and no log. Kickoff templates are editable through the app's skill editor and written straight to disk with no validation, so an operator who types `{{ raw_output_path_ }}` or `{{ inputs }}` gets a kickoff prompt that silently omits the write instruction or the input path. The stage then finishes with no artifact, or writes to a location the app never looks at, and the only symptom is a `no_artifact` status with no explanation. Today's nine templates are clean, so this is exposure rather than an active defect.
- **trigger**: Any edit to a kickoff template that misspells a variable name, via the skill editor or directly on disk.
- **proposed_fix**: Construct the environment with `StrictUndefined` so a bad name raises at render time, and validate a saved template by trial-rendering it against a dummy context before writing it to disk.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T1
- **detected_by**: manual-trace

### A-09 · `input_files[0]` ordering is unguarded against a stage gaining a second dependency

- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/turn_service.py:133`, `pipeline-app/pipeline_app/turn_service.py:143`, `pipeline-app/pipeline_app/turn_service.py:152`, `pipeline-app/stage_templates/repurpose.md:3`
- **component**: pipeline
- **failure_mode**: latent
- **blast_radius**: Extends SEED-4 with the exposure map. `upstream_stage_defs` is a filter over `all_stage_defs` (`:133`), so `upstream_paths` — and therefore `input_files[0]` — follows `pipeline.yaml` declaration order, not `depends_on` order, and additionally shifts when an upstream has no artifact and drops out of the dict at `:139-142`. Four templates read `input_file`; all four sit on one-dependency stages today, so nothing is currently mis-wired. Nothing enforces that invariant: the SEED-3/A-01 fix, which adds `scripting` to `repurpose.depends_on`, would immediately hand `repurpose.md:3` whichever of scripting/assembly appears first in the YAML.
- **trigger**: Adding a second `depends_on` entry to any stage whose template uses `input_file`, or reordering `pipeline.yaml`.
- **proposed_fix**: Pass the stage-keyed mapping (`upstream_by_stage`, already built at `:138`) into the template context so templates address upstreams by stage id rather than position, and assert at load time that a template using `input_file` belongs to a single-dependency stage.
- **fix_cost**: M
- **depends_on_finding**: [A-01]
- **owner_task**: T1
- **detected_by**: manual-trace

### A-10 · Topology validation never checks a kickoff template exists for each stage

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/pipeline_config.py:36-66`, `pipeline-app/pipeline_app/prompt_builder.py:16`, `pipeline-app/pipeline_app/turn_service.py:148`
- **component**: pipeline
- **failure_mode**: loud
- **blast_radius**: `_validate_topology` checks duplicate ids, unknown dependencies, cycles, and specialist skill existence — but not that `stage_templates/<id>.md` exists. `render_kickoff_prompt` does `env.get_template(f"{stage_id}.md")`, so a stage added to `pipeline.yaml` without a template raises `TemplateNotFound` at that stage's first turn. That happens inside the SSE body generator (`routes/stages.py:193-199`), by which point a 200 and event-stream headers are already committed, so the operator sees a broken stream rather than a startup error. The gap is covered by a test (`pipeline-app/tests/test_pipeline_config.py:294-301`) whose own docstring names this exact failure — the check exists, just in the wrong place to protect a live run.
- **trigger**: Add a stage to `pipeline.yaml` and run it before creating its template.
- **proposed_fix**: Move the existence check into `_validate_topology` so a missing template fails at app startup, and keep the test as a regression guard.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T1
- **detected_by**: manual-trace

### A-11 · `specialist` is validated against `.claude/skills/`, `skill` is not

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/pipeline_config.py:49-56`, `pipeline-app/pipeline_app/pipeline_config.py:22`, `pipeline.yaml:3`, `pipeline.yaml:8`, `pipeline-app/stage_templates/ideation.md:1`
- **component**: pipeline
- **failure_mode**: silent
- **blast_radius**: The optional `specialist` field gets a hard existence check against `.claude/skills/<name>/SKILL.md`; the mandatory `skill` field — the one every template renders as its first line, `/{{ skill }}` — gets none. A typo or a renamed skill directory therefore produces a kickoff prompt whose first line is a slash command that resolves to nothing, so the stage runs with no skill loaded and answers from general knowledge. That is precisely the failure the project's anti-generic guarantee exists to prevent, and it leaves no marker in the output to detect it by. The asymmetry between the two checks looks unintentional.
- **trigger**: Rename or misspell a skill directory without updating `pipeline.yaml`, or vice versa.
- **proposed_fix**: Apply the same `.claude/skills/<name>/SKILL.md` existence check to `skill` that already guards `specialist`, in the same loop.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T1
- **detected_by**: manual-trace

### A-12 · `brand_scope` is unvalidated free text and invisible to graph validation

- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/pipeline_config.py:13`, `pipeline-app/pipeline_app/pipeline_config.py:26`, `pipeline-app/pipeline_app/pipeline_config.py:36-66`, `pipeline.yaml:6`, `pipeline-app/pipeline_app/project_service.py:45`
- **component**: pipeline
- **failure_mode**: latent
- **blast_radius**: `brand_scope` is read straight from YAML with no check against any known brand set, and `project_service.py:45` materialises a stage row only when `brand_scope is None or brand_scope == brand`. A typo (`raisingoodsports`) silently yields a stage that exists in the topology but has no row on any project — it disappears from nav and is never runnable, with no error. Worse, `_validate_topology` treats the graph as brand-agnostic: nothing forbids an unscoped stage from depending on a scoped one. `stages_to_unlock` requires all declared dependencies approved, so such an edge would leave the dependent permanently `locked` for every out-of-scope project. `migrations.py:166-170` documents that exact wedge as a real incident from the styleboard rollout, which shows the failure shape is not hypothetical.
- **trigger**: Misspell a `brand_scope` value, or add a `depends_on` edge from an unscoped stage to a brand-scoped one.
- **proposed_fix**: Validate `brand_scope` against an explicit allowed-brand set, and reject any dependency from a stage with narrower brand scope onto a stage with narrower-or-different scope during `_validate_topology`.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T1
- **detected_by**: manual-trace

### A-13 · `finalize_artifact=False` skips staleness propagation, and `grounding` has no dependents anyway

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/turn_service.py:222-223`, `pipeline-app/pipeline_app/turn_service.py:256`, `pipeline.yaml:2-6`, `pipeline-app/pipeline_app/routes/stages.py:162-189`
- **component**: pipeline
- **failure_mode**: silent
- **blast_radius**: The grounding stage returns at `:222-223` before `propagate_staleness` at `:256` ever runs, and no stage lists `grounding` in `depends_on`, so `_dependents_of` would return empty even if it did. Re-running grounding therefore writes a new brief into `rgs-briefs/`, repoints the pointer file, and leaves every downstream stage sitting at `approved` with the previous thinker/research pairing baked into script, styleboard and visuals. The stage-page Input panel (`routes/stages.py:80-94`) will show the *new* brief beside artifacts built on the old one, so the UI reads as consistent while the artifacts are not.
- **trigger**: Re-run the `grounding` stage on an RGS project after any downstream stage has been approved.
- **proposed_fix**: Have the grounding branch call `propagate_staleness` after it repoints the pointer, and give staleness a way to see the pointer target's hash — either by modelling grounding as a real dependency edge or by recording the pointer target in each downstream artifact's `depends_on`.
- **fix_cost**: M
- **depends_on_finding**: [A-04]
- **owner_task**: T1
- **detected_by**: manual-trace

### A-14 · Upstream resolution uses `latest_artifact_path`, bypassing pointer indirection

- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/turn_service.py:140`, `pipeline-app/pipeline_app/turn_service.py:46`, `pipeline-app/pipeline_app/turn_service.py:200`
- **component**: pipeline
- **failure_mode**: latent
- **blast_radius**: Two resolution helpers coexist. `artifacts.resolve_latest_artifact(repo_root, stage_id, stage_dir)` understands the grounding pointer indirection and is what `turn_service`'s own abort path (`:200`) and `routes/stages.py:87-89` use; `artifacts.latest_artifact_path(stage_dir)` does not, and is what upstream input collection (`:140`) and `_current_upstream_hashes` (`:46`) use. Nothing depends on `grounding` today, so the two never disagree — but any future `depends_on: [grounding]` edge would resolve to `None`, silently drop grounding from `input_files`, and simultaneously omit it from staleness hashing. The same two lines are also why A-13's fix is not a one-liner.
- **trigger**: Adding any `depends_on` edge onto a stage whose artifact lives behind a pointer.
- **proposed_fix**: Use the pointer-aware resolver in both upstream-collection sites so all four call sites agree, and delete the non-pointer-aware path if nothing else needs it.
- **fix_cost**: S
- **depends_on_finding**: [A-13]
- **owner_task**: T1
- **detected_by**: manual-trace

### A-15 · `run_stage_turn` dereferences a possibly-`None` stage row

- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/turn_service.py:119-120`, `pipeline-app/pipeline_app/turn_service.py:67-68`
- **component**: pipeline
- **failure_mode**: loud
- **blast_radius**: `db_mod.get_stage` returns `None` when a project has no row for that stage — the normal case for a brand-scoped stage on an out-of-scope project, and the case `migrations.py` exists to repair. `run_stage_turn` indexes the result immediately with no guard, yielding a `TypeError` and a 500, whereas the same module's `propagate_staleness` handles the identical case explicitly at `:67-68`. Callers currently validate first, so this is reachability-by-refactor rather than a live crash.
- **trigger**: Invoking `run_stage_turn` for a stage the project has no row for.
- **proposed_fix**: Raise `StageNotRunnableError` with a clear message when the row is `None`, matching the guard style already used in `propagate_staleness`.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T1
- **detected_by**: manual-trace

### A-16 · Multi-input templates list bare paths with no stage labels

- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/stage_templates/visual.md:6-10`, `pipeline-app/stage_templates/assembly.md:5-7`, `pipeline-app/stage_templates/music.md:4-6`, `pipeline-app/pipeline_app/turn_service.py:147`
- **component**: pipeline
- **failure_mode**: latent
- **blast_radius**: `input_files` is a bare list of filesystem paths; the loop renders them as anonymous bullets. `visual.md:10` then says "The styleboard artifact among those inputs owns the WORLD LOCK", leaving the model to identify which bullet is the styleboard purely from the `02b-styleboard` segment of the path. The inference works today only because `stage_dir_name` happens to embed the stage id. Changing `dir_prefix` or the directory naming scheme would silently break the association with no test or gate detecting it, and the same implicit contract governs `assembly.md` and `music.md`.
- **trigger**: Renaming a stage directory scheme, or any change to `pipeline_config.stage_dir_name`.
- **proposed_fix**: Render each input as an explicit `<stage_id>: <path>` pair, sourced from the `upstream_by_stage` mapping already built at `turn_service.py:138`, so the template states the association instead of relying on path parsing.
- **fix_cost**: S
- **depends_on_finding**: [A-09]
- **owner_task**: T1
- **detected_by**: manual-trace

### A-17 · `_validate_topology`'s `repo_root` is actually the YAML file's parent directory

- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/pipeline_config.py:32`, `pipeline-app/pipeline_app/pipeline_config.py:36`, `pipeline-app/pipeline_app/pipeline_config.py:51`
- **component**: pipeline
- **failure_mode**: docs-drift
- **blast_radius**: `load_topology` passes `path.parent` into a parameter named `repo_root`, and the specialist check resolves `.claude/skills/` relative to it. This is correct only because `pipeline.yaml` happens to live at the repo root, and it silently ties skill-existence validation to the topology file's location rather than to the app's configured `repo_root` (which the app tracks separately as `app.state.repo_root`). Loading a topology from anywhere else validates specialists against the wrong tree.
- **trigger**: Moving `pipeline.yaml`, or loading a topology from a path other than the repo root.
- **proposed_fix**: Take `repo_root` as an explicit argument to `load_topology` rather than deriving it from the YAML path, and pass the app's configured root at the call site.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T1
- **detected_by**: manual-trace

## T2 — Gates, approval & the two-callers problem

**Scope.** This section covers the deterministic gate layer and the approval decision it
feeds: `pipeline-app/pipeline_app/gates.py` (the runner, the registry, the fail-closed
handler, the linter loader), `pipeline-app/pipeline_app/approval_service.py` (the
gate-result check, the override path, the unlock cascade),
`pipeline-app/pipeline_app/state_machine.py` (statuses and transitions), the
gate-running and approve **call sites** in `pipeline-app/pipeline_app/routes/stages.py`
(lines 204-227 and 229-290 only — the artifact-write path in that same file belongs to
T3, `turn_service` to T1), and the whole of
`pipeline-app/pipeline_app/routes/skills.py`. Findings that touch `turn_service.py`,
`artifacts.py`, `git_helper.py`, `migrations.py`, `preflight.py` or
`scripts/lint_prompt_sheet.py` do so only where those files determine whether a gate
result is correct or whether an approval is safe; the citation is given so the fix is
locatable, not to claim ownership of those files.

### `run_gates_for_stage` — every call site

| # | Caller | `path:line` | `repo_root` | `stage_id` | `artifact_path` | `upstream` | Result |
|---|---|---|---|---|---|---|---|
| 1 | turn path (chat / regenerate) | `pipeline-app/pipeline_app/turn_service.py:238-240` | `repo_root` | `stage_def.id` | `stage_dir/raw_output.md` | **`upstream_by_stage`** (built at `turn_service.py:138-143` from `stage_def.depends_on`, latest artifact per upstream stage) | written to `meta["gates"]` at `turn_service.py:252` |
| 2 | hand-edit path | `pipeline-app/pipeline_app/routes/stages.py:266` | `repo_root` | `stage_id` | `stage_dir/raw_output.md` | **omitted → `{}`** (`gates.py:155`) | written to `meta["gates"]` at `routes/stages.py:278` |
| 3 | tests only | `pipeline-app/tests/test_gates.py:25,33,46,65,76,87,99` | real `REPO_ROOT` | `"scripting"` / `"ideation"` | fixture path | omitted | assertions |
| 4 | tests only | `pipeline-app/tests/test_gates.py:115` | real `REPO_ROOT` | `"visual"` | fixture sheet | `{"styleboard": ...}` | assertions |
| 5 | tests only (monkeypatched-out) | `pipeline-app/tests/test_turn_service.py:337` | — | — | — | — | patches the symbol |

**There is no third production caller.** The CLI (`python scripts/lint_prompt_sheet.py`,
`scripts/lint_script_language.py`) does **not** go through `run_gates_for_stage` — it
re-implements the same sequence in its own `main()`
(`scripts/lint_prompt_sheet.py:965-1036`), which is the second half of the two-callers
problem (A-31). `migrations.py` writes synthetic styleboard artifacts with **no `gates`
key at all** (`migrations.py:63-82`) and never calls the runner; that is currently safe
only because `styleboard` is absent from `GATE_REGISTRY`.

**Where they diverge:** call site 2 omits `upstream` entirely (A-30). Call site 1 passes
the *latest* upstream artifact, approved or not (A-32). The CLI diverges from both on an
empty world lock (A-31).

### Ungated stages, ranked by downstream gate dependence

`GATE_REGISTRY` (`gates.py:128-131`) covers 2 of the 9 stages declared in
`pipeline.yaml`. Ranked by how much a *downstream* gate's correctness rests on the
ungated artifact:

1. **`styleboard`** — highest, by a wide margin. Gate C's C8 (`lint_prompt_sheet.py:440-460`),
   C18 (`:769-822`) and C20 (`:882-926`) all read the world lock and the `slot_*` values
   **out of the styleboard**, and C20 explicitly reads `world.get(key)` (`:911`) — the
   styleboard's text — while reporting the finding against the *sheet's* shot index. An
   unlinted styleboard is the single largest source of downstream Gate C error. See A-33, A-34.
2. **`voiceover`** — feeds `music-brief`'s tone-contradiction check and `shorts-assembly`'s
   ducking/LUFS targets. No linter exists for it at all, so this is a pure coverage gap,
   not a wiring bug.
3. **`ideation`** — feeds `scripting`, whose Gate D lints only the script body; a
   mis-packaged concept passes through invisibly.
4. **`grounding`** — feeds RGS scripts; the `[REF]` provenance discipline documented in
   `rgs-briefs/` has no mechanical enforcement anywhere in the app.
5. **`assembly`**, **`repurpose`**, **`music`** — terminal or near-terminal; nothing
   downstream gates on them, so the absence costs the least.

### Approval with an unknown gate result — trace of `approval_service.py:52-65`

- `recorded = latest_meta.get("gates") or []` (`:52`) — an absent key and an explicit
  empty list are collapsed to `[]`.
- `failing` (`:53`) keys off `g.get("status") in ("fail","error")`.
- `never_ran` (`:55-58`) is computed from `GATE_REGISTRY.get(stage_id, [])` minus the
  recorded names, so **a registry that gains a stage correctly blocks an old artifact with
  no `gates` key** — that path works as designed and is covered by
  `pipeline-app/tests/test_approval_service.py:377`.
- **A `status` value outside `{pass,fail,error}` is treated as a pass** (A-35).
- A `gates` value that is not a list of dicts raises `AttributeError`, which the route does
  not catch (A-36).

### The override path

`override_reason` is persisted **only** as `gate_override_reason` in the artifact's YAML
frontmatter (`artifacts.py:87`, `artifacts.py:104`). There is no DB column, no append-only
log, no actor, and — on the `record_gate_override` branch — no timestamp at all, because
that branch deliberately leaves `finalized_at` untouched (`artifacts.py:100-105`). The
route strips whitespace before passing it down (`routes/stages.py:219`), but the service
function itself does not (A-38). Nothing renders it back to the operator (A-37), and a
second override overwrites the first (A-38's sibling, A-39... see below).

### State machine — statuses and transitions

Seven statuses (`state_machine.py:6-13`), all reachable, none dead:

| From | To | Where |
|---|---|---|
| (create) | `ready` / `locked` | `state_machine.py:17` via `project_service.py:47-48` |
| (migrate) | `approved` / `ready` / `locked` | `migrations.py:121,145,148-157` |
| `locked` | `ready` | `approval_service.py:83-86` (all deps approved) |
| `ready`\|`awaiting_review`\|`approved`\|`stale`\|`no_artifact` | `running` | `turn_service.py:130` (guarded by `is_locked_or_running`, `:120`) |
| `running` | `awaiting_review` | `turn_service.py:255` (artifact written) |
| `running` | `no_artifact` | `turn_service.py:230` |
| `running` | `awaiting_review` \| `ready` | `turn_service.py:200-204` (abort), `preflight.py:38-40` (startup sweep) |
| `running` | `awaiting_review` \| `no_artifact` | `routes/stages.py:187,189` (grounding only) |
| any non-`locked`/`running` | `approved` | `approval_service.py:77` |
| `approved` | `stale` | `turn_service.py:79,95` |
| any non-`locked`/`running` | `awaiting_review` | `routes/stages.py:288` (hand edit) |

**Reachable but shouldn't be:** `approved → running → awaiting_review` on an aborted turn,
and `stale → running → awaiting_review` on an aborted turn (A-46) — both drop a stage out
of its prior state without producing a new artifact. **Missing entirely:** there is no
transition *into* `locked` after row creation — `LOCKED.value` is never passed to
`update_stage_status` anywhere in the app (A-45).

### `routes/skills.py` — the traversal defense

The set-membership check at `:51-53` and `:83-85` **is sufficient** for the traversal case
it is written for. `skill_name` must compare equal to a name yielded by
`Path.iterdir()`, which is always a single path component and can never be `.` or `..`;
`%2F`-encoded and backslash variants are unquoted by Starlette *before* the comparison and
therefore fail it (proved by `tests/test_routes_skills.py:71-78` and `:95-114`). No
character that survives the check can break the later join, because the surviving strings
are by construction the names of directories that already exist. The one residual escape
is a symlinked skill directory (A-56).

---

### A-30 · Hand-edit Gate C reads an operator-authored world lock, not the styleboard
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/stages.py:266`, `pipeline-app/pipeline_app/gates.py:82-84`, `pipeline-app/pipeline_app/gates.py:66-71`, `scripts/lint_prompt_sheet.py:911`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: Every hand edit of a `visual` artifact. Two distinct outcomes: (a) if the edited sheet carries no `WORLD LOCK` block — the normal modern case, since `visual-prompts` is told not to re-emit it — `world` is `{}`, C18 fires on every slot with a message naming the wrong artifact, and **C20 silently returns no findings** because `world.get(key)` is empty and `check_slot_labels` hits the `continue` at `lint_prompt_sheet.py:912-913`; (b) if the operator pastes a `WORLD LOCK` block into the sheet, C8/C18/C20 all lint the sheet against text the operator just wrote, so the styleboard's real lock is never enforced and a sheet that contradicts the locked world passes Gate C cleanly.
- **trigger**: Saving a `visual` artifact through the stage page's edit form instead of regenerating it via chat.
- **proposed_fix**: The hand-edit call site must build the same `upstream` mapping the turn path builds — resolve the stage's `depends_on` to their latest artifacts and pass them in. Factor that resolution out of `turn_service` so exactly one implementation exists and the two callers cannot drift again.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-31 · CLI and app Gate C disagree on an empty world lock — same name, different diagnosis
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/gates.py:87-96`, `scripts/lint_prompt_sheet.py:989-992`, `pipeline-app/pipeline_app/gates.py:66-71`
- **component**: gates
- **failure_mode**: loud
- **blast_radius**: A styleboard whose `WORLD LOCK` block is unparseable (the backfilled "not recoverable" artifact from `migrations.py:129-144` is exactly this) makes the app raise and record `status:"error"` with a message naming the styleboard, while the CLI proceeds with `world = {}` and prints a wall of per-shot C8/C18 findings naming the sheet. Both block, so no bad sheet ships — but an operator who runs the CLI to reproduce an app failure gets a different report, and the module docstring's equivalence promise is already false.
- **trigger**: Running Gate C against a project whose styleboard was backfilled by `migrations.backfill_styleboard_rows`, or any styleboard with a malformed world lock.
- **proposed_fix**: Move the fail-closed empty-world check into `lint_prompt_sheet` itself so both callers inherit it, and have `gates.run_prompt_sheet_gate` call that instead of re-deciding.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-32 · Gates lint against the latest upstream artifact, which may be an unapproved draft
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/turn_service.py:138-143`, `pipeline-app/pipeline_app/artifacts.py:49-53`, `pipeline-app/pipeline_app/gates.py:82-86`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: `upstream_by_stage` is built with `latest_artifact_path`, which returns the highest version number regardless of whether that version was ever approved. Regenerate an approved styleboard (producing an unapproved `v2` draft), then re-run `visual`: Gate C validates the sheet against the *draft* world lock. The sheet can pass a gate keyed to a world the operator has not accepted, and the recorded `gates` block gives no hint which version it was checked against.
- **trigger**: Regenerating an upstream stage without approving it, then running or re-running a gated downstream stage.
- **proposed_fix**: Resolve upstream gate inputs to the stage's *approved* artifact, and record the resolved upstream path and sha256 inside each gate result so the artifact says what it was checked against.
- **fix_cost**: M
- **depends_on_finding**: [A-30]
- **owner_task**: T2
- **detected_by**: manual-trace

### A-33 · Seven of nine stages are ungated; `styleboard` is the load-bearing omission
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/gates.py:128-131`, `pipeline.yaml` (9 stages), `scripts/lint_prompt_sheet.py:440-460`, `scripts/lint_prompt_sheet.py:882-926`
- **component**: gates
- **failure_mode**: coverage-gap
- **blast_radius**: `GATE_REGISTRY` gates only `scripting` and `visual`. `styleboard` — the artifact Gate C's C8, C18 and C20 all *read from* — is itself never checked, so the input to the strictest gate in the system is the least validated artifact in the system. `voiceover`, `ideation`, `music`, `assembly`, `repurpose` and `grounding` are also ungated, but nothing downstream depends on their structure the way Gate C depends on the styleboard.
- **trigger**: Any run. A malformed or invented styleboard is accepted at `styleboard` and only surfaces one stage later, attributed to the sheet.
- **proposed_fix**: Add a styleboard gate that checks the artifact Gate C will later read from it — a well-formed `WORLD LOCK` block, `slot_*` values matching `VALID_SLOT_VALUE_RE`, and every declared label resolving in `docs/style-library.md`. Register it under `styleboard` so `approval_service`'s `never_ran` check starts covering that stage too.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-34 · C20 blames the sheet for a label the styleboard chose
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:911`, `scripts/lint_prompt_sheet.py:916-925`, `pipeline-app/pipeline_app/gates.py:128-131`
- **component**: gates
- **failure_mode**: latent
- **blast_radius**: `check_slot_labels` resolves the label with `world.get(key)` — the *styleboard's* world lock — but emits the finding with the *sheet's* `shot.index`, and the gate result is stored on the `visual` artifact. A single mistyped label in the styleboard therefore fails the visual stage once per affected shot, and the operator's first instinct is to edit the sheet, which cannot fix it. The docstring at `:890-892` records that this exact class of mismatch already shipped once.
- **trigger**: A styleboard binding a `slot_*` label that names no Style Library entry.
- **proposed_fix**: Catch the bad label at the styleboard stage (see A-33). Until then, have C20's message name the styleboard as the file to edit, not just the shot.
- **fix_cost**: S
- **depends_on_finding**: [A-33]
- **owner_task**: T2
- **detected_by**: manual-trace

### A-35 · A gate result with an unrecognized `status` approves as if it passed
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/approval_service.py:53`, `pipeline-app/pipeline_app/approval_service.py:54-58`, `pipeline-app/pipeline_app/gates.py:161-172`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: The block condition tests `status in ("fail","error")` and the `never_ran` test only asks whether the gate *name* appears. A recorded entry with `status: "skipped"`, `status: null`, a missing `status` key, or a typo is therefore neither failing nor never-ran — it satisfies the registry check and approval proceeds with no override and no message. The design comment at `:47-51` claims an unknown result blocks; an unknown *value* does not.
- **trigger**: A future gate runner adopting a third status word, or a hand-edited artifact frontmatter, or a partially written `gates` block.
- **proposed_fix**: Invert the test — treat only an explicit `pass` as passing and block on everything else, naming the unrecognized value in the error so a vocabulary change fails loudly instead of silently widening the approve path.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-36 · A malformed `gates` frontmatter value 500s the approve route instead of 409-ing
- **severity**: S3
- **confidence**: probable
- **evidence**: `pipeline-app/pipeline_app/approval_service.py:52-54`, `pipeline-app/pipeline_app/routes/stages.py:221-225`, `pipeline-app/pipeline_app/artifacts.py:13-23`
- **component**: gates
- **failure_mode**: loud
- **blast_radius**: `recorded` is whatever `yaml.safe_load` produced. If `gates` is a string, a scalar, or a list of strings, the comprehension at `:53` calls `.get` on a non-mapping and raises `AttributeError`. The route catches only `ValueError`, so the operator gets an unhandled 500 rather than the 409 every other approval conflict produces. Most acute for `grounding`, whose artifact is a hand-written file in `rgs-briefs/` with entirely uncontrolled frontmatter (`artifacts.py:56-69`).
- **trigger**: Approving a stage whose artifact frontmatter carries a `gates` key of the wrong shape.
- **proposed_fix**: Validate the shape of `recorded` before iterating and raise `ValueError` with a message naming the artifact, so a malformed block becomes a blocking conflict rather than a crash.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-37 · `gate_override_reason` is write-only — never rendered back to the operator
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/artifacts.py:87`, `pipeline-app/pipeline_app/artifacts.py:104`, `pipeline-app/pipeline_app/routes/stages.py:96-108`, `pipeline-app/pipeline_app/templates/stage.html:35-62`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: `stage_page` reads only `output_meta.get("gates")`; `gate_override_reason` is never put in the template context and `stage.html` never references it. An operator (or a later reviewer) looking at an approved stage sees a red failing gate and no indication that anyone consciously accepted it, or why. The override is invisible everywhere except by opening the artifact file by hand.
- **trigger**: Viewing any stage that was approved with an override.
- **proposed_fix**: Surface `gate_override_reason` in the gates panel next to the failing gate it excuses, so the artifact's audit trail is visible where the decision is made.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-38 · Overrides are last-write-wins with no actor and, on one path, no timestamp
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/artifacts.py:103-105`, `pipeline-app/pipeline_app/artifacts.py:79-88`, `pipeline-app/pipeline_app/approval_service.py:67-77`, `pipeline-app/pipeline_app/schema.sql` (`stages` has no override column)
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: `record_gate_override` assigns `meta["gate_override_reason"] = ...`, overwriting any prior value; approving the same artifact twice with different reasons leaves only the second. There is no WHO anywhere (the app has no actor concept), and the `record_gate_override` branch deliberately does not touch `finalized_at`, so an override applied to an already-final artifact carries **no timestamp at all** — only `stages.approved_at` moves, and nothing links the two.
- **trigger**: Approving an already-final artifact with an override, or overriding the same artifact more than once.
- **proposed_fix**: Make the override an append-only list of `{reason, at}` entries on the artifact rather than a scalar, and mirror it into a DB row keyed to the stage so the decision survives independent of the file.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-39 · A whitespace-only override reason bypasses the gate block at the service layer
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/approval_service.py:59`, `pipeline-app/pipeline_app/approval_service.py:70`, `pipeline-app/pipeline_app/routes/stages.py:219`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: The stripping that makes an empty reason falsy lives in the route (`override_reason.strip() or None`), not in `approve_stage`. `approve_stage(..., override_reason=" ")` is truthy, so it clears the gate block *and* records a blank reason via `stamp_final`. The invariant is enforced one layer above the function that owns it; any second caller (a script, a future API, a test) reintroduces the hole. Even through the route, a single character like `.` is accepted.
- **trigger**: Calling `approve_stage` directly with a whitespace-only reason.
- **proposed_fix**: Normalize and reject blank reasons inside `approve_stage` itself so the invariant belongs to the service, and let the route pass the raw form value through.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-40 · A `BaseException` from a gate escapes fail-closed and wedges the stage at `running`
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/gates.py:160`, `pipeline-app/pipeline_app/turn_service.py:238-240`, `pipeline-app/pipeline_app/turn_service.py:185-211`
- **component**: gates
- **failure_mode**: latent
- **blast_radius**: The claim at `gates.py:160` holds for everything under `Exception` — `ImportError`, `SyntaxError`, `FileNotFoundError` from a missing linter, `MemoryError` and `RecursionError` are all caught and recorded as `status:"error"`. It does **not** hold for `BaseException` subclasses: `SystemExit` (a linter calling `sys.exit()` at import — note `lint_prompt_sheet.py:1039-1040` guards this only by `__name__`), `KeyboardInterrupt`, and `asyncio.CancelledError`. In the turn path the gate call at `:238` sits *after* the `except BaseException` block closes at `:211`, so such an escape leaves the turn row at `running` and the stage row at `running`, wedging the app's global single-flight lock until a restart runs `preflight.reconcile_orphaned_turns`.
- **trigger**: A linter that calls `sys.exit()` outside its `__main__` guard, or task cancellation landing on the post-stream artifact work.
- **proposed_fix**: Widen the handler to `BaseException` with a re-raise for genuine cancellation, or extend `turn_service`'s existing `except BaseException`/status-recovery block to cover the artifact-and-gate section so no escape can leave a stage `running`.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-41 · The hand-edit gate call is untried; an escape 500s after `raw_output.md` is clobbered
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/stages.py:263-266`, `pipeline-app/pipeline_app/routes/stages.py:280`, `pipeline-app/pipeline_app/gates.py:160`
- **component**: gates
- **failure_mode**: loud
- **blast_radius**: `raw_output.md` is overwritten with the submitted body *before* the gate runs, and neither the gate call nor `write_artifact` is wrapped. Any escape (A-40's `BaseException` class, or an `OSError` from `write_artifact`) returns a 500 with the previous turn's `raw_output.md` already destroyed and no `artifact.v{N+1}.md` minted — the operator's edit exists nowhere the app will show it, and a subsequent turn's `before_mtime` comparison now starts from the clobbered file.
- **trigger**: Any unhandled escape from the gate or artifact write on the hand-edit route.
- **proposed_fix**: Write the gated body to a temporary file, gate it, and only overwrite `raw_output.md` and mint the artifact once both have succeeded; return a 409 with the gate error rather than a 500.
- **fix_cost**: S
- **depends_on_finding**: [A-40]
- **owner_task**: T2
- **detected_by**: manual-trace

### A-42 · `_load_linter` re-executes each linter per gate run and leaves it in `sys.modules`
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/gates.py:28-43`, `pipeline-app/pipeline_app/gates.py:41`
- **component**: gates
- **failure_mode**: latent
- **blast_radius**: The module is inserted into `sys.modules` under its bare name (`lint_prompt_sheet`, `lint_script_language`) before `exec_module` runs and is never removed. A failed exec leaves a half-initialized module registered under a global name until the next gate run replaces it, and any unrelated import of that bare name inside the app process would receive the linter. Re-executing the whole module on every gate run also means module-level state cannot be relied on. Benign today — the insertion is load-bearing for Python 3.14 dataclass annotation resolution (documented at `:34-40`) — but it is a global side effect with no cleanup.
- **trigger**: Any gate run; visible only if an exec fails or a name collides.
- **proposed_fix**: Cache the loaded module per `(repo_root, module_name)` and pop the `sys.modules` entry if `exec_module` raises, so a failed load cannot leave a broken module registered.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-43 · Gate C findings render without a shot number — the template reads a field they lack
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:40-44`, `pipeline-app/pipeline_app/gates.py:46-47`, `pipeline-app/pipeline_app/templates/stage.html:44-47`, `scripts/lint_script_language.py:48-52`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: `lint_script_language.Finding` has `beat` and `kind`; `lint_prompt_sheet.Finding` has `shot_index` and no `kind`. `_as_dicts` passes both through verbatim, and `stage.html` renders `finding.beat` only. Every Gate C finding therefore displays as `[C18]: <message>` with no shot number, while the CLI prints `shot 7:` for the same finding (`lint_prompt_sheet.py:1029-1035`). On a 20-shot sheet the operator is told what is wrong but not where, and must re-run the CLI to find out.
- **trigger**: Any failing Gate C run viewed on the stage page.
- **proposed_fix**: Normalize the two linters' finding shapes in `_as_dicts` (map `shot_index` to the location field the template reads, and default `kind`), so the app and CLI describe a finding the same way.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-44 · Approval never checks staleness, and an unapproved draft is never marked stale
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/turn_service.py:66-68`, `pipeline-app/pipeline_app/approval_service.py:20-31`, `pipeline-app/pipeline_app/state_machine.py:34-40`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: `propagate_staleness` skips any dependent whose status is not `approved` (`:68`), and `approve_stage` never calls `is_stale` at all. So a stage sitting at `awaiting_review` whose upstream has since been regenerated is never flagged: the stale cue in `stage.html:57` is keyed to the `stale` status, which this row never reaches, and approval records the draft's original `depends_on` hashes as if they were current. A Short can ship built on a script that was replaced before the draft was approved, with nothing anywhere saying so.
- **trigger**: Draft a downstream stage, regenerate its upstream, then approve the downstream draft without regenerating it.
- **proposed_fix**: Evaluate `is_stale` against the current upstream hashes at approval time regardless of the row's status, and require the existing override mechanism to approve over a stale input.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-45 · Nothing ever re-locks a stage whose dependency has left `approved`
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/state_machine.py:24-31`, `pipeline-app/pipeline_app/approval_service.py:83-86`, `pipeline-app/pipeline_app/routes/stages.py:288`, `pipeline-app/pipeline_app/turn_service.py:130`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: `stages_to_unlock` is a one-way ratchet and `StageStatus.LOCKED.value` is never passed to `update_stage_status` anywhere in the app. Approve `scripting` (unlocking `styleboard` and `voiceover`), then hand-edit `scripting` — `routes/stages.py:288` drops it back to `awaiting_review` — and the downstream stages stay `ready`, runnable, and approvable even though the dependency the topology requires is no longer approved. The `depends_on` invariant the DAG exists to enforce holds only on the way up.
- **trigger**: Hand-editing or regenerating an already-approved stage after its dependents have been unlocked.
- **proposed_fix**: Make the unlock cascade bidirectional — when a stage leaves `approved`, re-lock any dependent that has no artifact of its own and mark the rest stale — so `locked` reflects the current DAG rather than its high-water mark.
- **fix_cost**: M
- **depends_on_finding**: [A-44]
- **owner_task**: T2
- **detected_by**: manual-trace

### A-46 · An aborted turn launders `stale` into `awaiting_review`, erasing the only staleness cue
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/turn_service.py:200-204`, `pipeline-app/pipeline_app/preflight.py:38-40`, `pipeline-app/pipeline_app/templates/stage.html:57`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: A `stale` stage always has an artifact, so the abort recovery's `latest is not None` branch always resolves to `awaiting_review`. Starting a turn on a stale stage and disconnecting before any output lands therefore clears the `stale` status without producing anything — the artifact on disk is unchanged, but the stage-page warning that it was built on a since-changed input disappears permanently. The same laundering applies to `approved → running → awaiting_review`.
- **trigger**: Opening chat on a stale stage and closing the tab (or any turn abort) before `raw_output.md` is written.
- **proposed_fix**: Have the abort and startup-sweep recovery restore the stage's pre-`running` status rather than re-deriving it from artifact existence; persist that prior status on the turn row so the recovery has something to restore to.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-47 · `stages.status` has no CHECK constraint; any string is a legal status
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/schema.sql` (`stages.status TEXT NOT NULL`), `pipeline-app/pipeline_app/db.py:73-81`, `pipeline-app/pipeline_app/routes/stages.py:187,189,288`
- **component**: gates
- **failure_mode**: latent
- **blast_radius**: `update_stage_status` takes a bare `str` and the column accepts anything. Three call sites already pass string literals (`"awaiting_review"`, `"no_artifact"`) rather than `StageStatus` members, so a typo would persist a status no guard recognizes — `is_locked_or_running` would return `False` for it, making the stage chattable, editable and approvable regardless of what it was meant to mean.
- **trigger**: A typo in any string-literal status write, or a future status added in one place only.
- **proposed_fix**: Add a `CHECK (status IN (...))` constraint to the column and have `update_stage_status` accept `StageStatus` rather than `str`, so the enum is the only way to write the field.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: grep-sweep

### A-48 · `STAGE_ID_BY_SKILL` duplicates `pipeline.yaml` and has already drifted from it
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/skills.py:8-18`, `pipeline.yaml` (`styleboard` / `shorts-styleboard`), `pipeline-app/stage_templates/styleboard.md`, `pipeline-app/tests/test_routes_skills.py:86-92`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: The map is a hand-maintained copy of the `skill → id` pairs already present in `pipeline.yaml` and reachable as `request.app.state.stage_defs`. It is missing `shorts-styleboard`, which is a real pipeline stage with a real template at `pipeline-app/stage_templates/styleboard.md`. Its editor page therefore shows an **empty** kickoff-template box while a populated template sits on disk, and saving that box writes `stage_templates/None.md` (A-50) while the real template is never touched. The existing test asserts only that the three specialists are absent, so the styleboard omission is invisible to the suite.
- **trigger**: Opening `/skills/shorts-styleboard` — and every future stage added to `pipeline.yaml` without a matching hand edit here.
- **proposed_fix**: Derive the mapping from `request.app.state.stage_defs` (`{s.skill: s.id}`) instead of hardcoding it, so a new stage cannot exist in the topology and be missing from the editor.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-49 · An unknown `target` value redirects with a 303 as though the save succeeded
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/skills.py:87-95`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: The `if`/`elif` has no `else`, and the `RedirectResponse` at `:95` is unconditional. A `target` that is neither `SKILL.md` nor `kickoff_template` — a renamed hidden input, a stale bookmarked form, a typo in a future template — writes nothing, commits nothing, and returns the same 303 to the detail page that a successful save returns. The operator sees their edit vanish and has no error to act on.
- **trigger**: Posting to `/skills/{name}/save` with any `target` value outside the two handled cases.
- **proposed_fix**: Add an explicit `else` raising a 400 naming the unrecognized target, so the only 303 the route can produce is one that follows a real write.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-50 · Saving a kickoff template for an unmapped skill writes `stage_templates/None.md`
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/skills.py:91-94`, `pipeline-app/pipeline_app/routes/skills.py:17`, `pipeline-app/pipeline_app/templates/skill_editor.html:12-17`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: `skill_editor.html` renders the kickoff-template form unconditionally, for all 13 discovered skills. For the five with no stage id — `rgs-pairing-review` (mapped to an explicit `None`), `shorts-styleboard` (missing key), and the three specialists — `stage_id` is `None`, the f-string interpolates it, and the route writes `pipeline-app/stage_templates/None.md`, then 303s as if it saved. Repeated use silently overwrites that same junk file; the operator believes they edited a template that does not exist.
- **trigger**: Clicking "Save kickoff template" on any skill without a stage id.
- **proposed_fix**: Have the detail view tell the template whether a kickoff template applies and render the form only when it does, and have the save route reject a `kickoff_template` target for a skill with no stage id.
- **fix_cost**: S
- **depends_on_finding**: [A-48]
- **owner_task**: T2
- **detected_by**: manual-trace

### A-51 · `save_skill` accepts empty content and silently truncates a SKILL.md or template
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/skills.py:78`, `pipeline-app/pipeline_app/routes/skills.py:89`, `pipeline-app/pipeline_app/routes/skills.py:94`, `pipeline-app/pipeline_app/routes/skills.py:56`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: `content: str = Form(...)` is satisfied by an empty string, and both branches call `write_text` with no length, shape or frontmatter validation. Submitting a cleared textarea writes a zero-byte `SKILL.md`, destroying the skill; the route then 303s as a success. A related path makes this easy to hit by accident: `skill_detail` renders `""` when `SKILL.md` is missing (`:56`), so an editor opened on a skill directory without a `SKILL.md` presents an empty box that will write an empty file on save. `SKILL.md` edits are at least recoverable from the commit `commit_skill_edit` makes; kickoff-template edits are not (A-52).
- **trigger**: Saving the editor with an empty or accidentally-cleared textarea.
- **proposed_fix**: Reject a blank or whitespace-only body, and require a `SKILL.md` save to still parse as frontmatter with a `name` and `description`, so the editor cannot write a file the skill loader would reject.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-52 · Kickoff-template saves are never committed, so they have no recovery path
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/skills.py:90`, `pipeline-app/pipeline_app/routes/skills.py:94`, `pipeline-app/tests/test_routes_skills.py:54-68`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: `commit_skill_edit` is called on the `SKILL.md` branch only. A kickoff-template save overwrites a tracked file in `pipeline-app/stage_templates/` with no commit, no backup and no versioning — so a bad or empty save (A-51) is unrecoverable unless the operator happens to commit by hand, and there is no record that the app changed a file that materially determines what every future turn of that stage is asked to do. The asymmetry is currently pinned in place by a test that asserts the absence, with no stated rationale.
- **trigger**: Saving a kickoff template through the skill editor.
- **proposed_fix**: Commit the kickoff template on the same terms as `SKILL.md` — same helper, message naming the stage — so both editable surfaces have identical durability, and update the test to assert the commit rather than its absence.
- **fix_cost**: S
- **depends_on_finding**: [A-51]
- **owner_task**: T2
- **detected_by**: manual-trace

### A-53 · `commit_skill_edit` commits the entire index, not just the skill file
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/git_helper.py:10-20`, `pipeline-app/pipeline_app/routes/skills.py:90`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: `git commit -m message` is issued with no pathspec, so it commits everything already staged. An operator with unrelated staged work who saves a SKILL.md through the app gets that work swept into a commit labelled `skill edit: <name> via pipeline-app`. The same omission corrupts the no-op guard: `git diff --cached --quiet` sees the operator's unrelated staged changes and reports work to commit even when the skill file is byte-identical, producing a "skill edit" commit that contains no skill edit.
- **trigger**: Saving a SKILL.md while any unrelated change is staged in the repo.
- **proposed_fix**: Scope both the staged-change check and the commit to the single file path so the app can only ever commit what it wrote.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-54 · A git failure 500s the save route after the file is already written
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/skills.py:89-90`, `pipeline-app/pipeline_app/git_helper.py:10`, `pipeline-app/pipeline_app/git_helper.py:20`
- **component**: gates
- **failure_mode**: loud
- **blast_radius**: The write happens first, then `commit_skill_edit` runs two `check=True` subprocesses. A failing pre-commit hook, an unavailable `git`, an index lock, or a rebase in progress raises `CalledProcessError` — with `capture_output=True`, so the underlying git message is swallowed — and the route returns a 500. The file on disk is already changed, so the operator sees a failure for a save that in fact succeeded, and a retry produces a no-op that git then reports as nothing to commit.
- **trigger**: Saving a SKILL.md while git cannot commit for any reason.
- **proposed_fix**: Treat commit failure as non-fatal for the save — surface it as a warning on the redirect target naming the git error — or commit before responding but report the two outcomes separately.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-55 · Every browser save doubles carriage returns on Windows
- **severity**: S3
- **confidence**: probable
- **evidence**: `pipeline-app/pipeline_app/routes/skills.py:89`, `pipeline-app/pipeline_app/routes/skills.py:94`, `pipeline-app/pipeline_app/templates/skill_editor.html:8`
- **component**: gates
- **failure_mode**: silent
- **blast_radius**: HTML form submission normalizes a `<textarea>` value to CRLF, and `Path.write_text` opens with `newline=None`, which translates every `\n` to `os.linesep`. On Windows that turns the submitted `\r\n` into `\r\r\n` — verified directly against this interpreter. Every SKILL.md and kickoff template saved through the editor is rewritten with mangled line endings, producing a whole-file diff in the commit `commit_skill_edit` makes and obscuring what actually changed.
- **trigger**: Saving anything through the skill editor on Windows.
- **proposed_fix**: Pass `newline=""` on both writes (or normalize the submitted content to `\n` before writing) so the bytes on disk match what the operator typed.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace

### A-56 · A symlinked skill directory escapes the discovered-set traversal defense
- **severity**: S4
- **confidence**: suspected
- **evidence**: `pipeline-app/pipeline_app/routes/skills.py:21-25`, `pipeline-app/pipeline_app/routes/skills.py:51-53`, `pipeline-app/pipeline_app/routes/skills.py:88`
- **component**: gates
- **failure_mode**: latent
- **blast_radius**: `_discovered_skill_names` accepts any entry for which `p.is_dir()` is true, and `is_dir()` follows symlinks. A symlink placed in `.claude/skills/` therefore becomes a legitimate member of the discovered set, and the save route writes through it to wherever it points — outside the repo if it points there. The set-membership check is otherwise sound and is the right defense; this is the one residual escape, and it requires an attacker who can already write to `.claude/skills/`, which is why it is hygiene rather than a real exposure for a local-only app.
- **trigger**: A symlink present in `.claude/skills/`.
- **proposed_fix**: Reject entries where `p.is_symlink()` during discovery, and resolve the final write path and assert it stays under `.claude/skills/` before writing.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T2
- **detected_by**: manual-trace


## T3 — Artifacts, versioning & staleness

**Scope.** This section audits artifact persistence, version numbering, frontmatter provenance,
crash-safety, the sqlite layer, startup migrations/reconciliation, project creation, and the
grounding pointer indirection: `pipeline-app/pipeline_app/artifacts.py`, `db.py`, `schema.sql`,
`migrations.py`, `preflight.py`, `project_service.py`, `grounding_service.py`, `main.py`, and
**only the artifact-write path** of `routes/stages.py` (`edit_stage_output_route`, versioning,
frontmatter, and the `raw_output.md` write at `:265`) — T2 owns the gate/approve call sites in
that same file. `turn_service.py`, `approval_service.py`, `gates.py`, `state_machine.py`,
`pipeline_config.py`, `routes/projects.py`, `routes/doctor.py` and the templates were read as
evidence but are **not** owned here; defects located purely inside them are handed off, not
filed. Documentation only; nothing was changed. Findings extend confirmed seed SEED-5 rather
than re-deriving it. A grep sweep for `TODO`/`FIXME`/`XXX`/`HACK`/`stub`/`placeholder`/
`NotImplemented` across the owned files returned **zero** hits, and every public helper in
`db.py` has at least one live non-test caller — the only dead surface found is an entire route
with no UI entry point (A-84).

### Q1 trace — the `depends_on` lifecycle

`depends_on` is the *only* provenance record staleness is computed from. `state_machine.is_stale`
iterates the recorded list and returns `True` on the first path/hash mismatch; an **empty list
returns `False` unconditionally** (`state_machine.py:34-40`), and `propagate_staleness` only
enqueues a stage for the second-level cascade when `is_stale` returned `True`
(`turn_service.py:78-80`). An empty `depends_on` therefore does not merely fail to mark one
stage stale — it **terminates the entire cascade at that node**.

It is written in exactly three places:

| Where | How | Result |
|---|---|---|
| Turn path — `turn_service.py:234-237` | Computed: `{path, sha256}` per upstream that currently *has* an artifact | Correct, and the only path that ever recomputes it |
| Edit path — `routes/stages.py:277` | Copied verbatim from the prior artifact's frontmatter | Wrong whenever the prior value is absent or obsolete |
| Migration — `migrations.py:78` | Hardcoded `[]` on the synthetic styleboard artifact | Permanently empty |

Every state in which it ends up empty or stale, and the consequence of each:

1. **First-ever hand edit on a stage with no prior artifact** (SEED-5). `latest is None` →
   `prior_meta = {}` → `depends_on: []`. Consequence: the stage never goes stale, and no
   dependent of it is ever reached by the cascade. Filed as **A-60**.
2. **Sticky propagation of an empty list.** Because the edit path copies rather than computes,
   once `depends_on` is `[]` it stays `[]` through every subsequent hand edit. Only a
   `run_stage_turn` on that stage restores it. Consequence: the hole in (1) is permanent, not
   transient. Filed as part of **A-60**.
3. **Backfilled styleboard** (`migrations.py:78`) — written `[]` *and* set `approved`
   (`migrations.py:145,155-157`). Consequence: on a migrated project, `styleboard` can never be
   marked stale by a `scripting` change. Filed as **A-61**.
4. **Hand edit after an upstream already moved.** The copied entry names the *old* upstream
   version (e.g. `02-scripting/artifact.v1.md`) while `v2` is current. Consequence: the artifact
   asserts a provenance that is false — it claims derivation from content the operator was not
   editing against. Staleness still fires (a permanently-mismatched record always mismatches), so
   the damage is to provenance integrity and to the inspector/audit trail, not to the cascade.
   Filed as part of **A-60**.
5. **Prior artifact with unparseable or absent frontmatter.** `parse_frontmatter` returns `{}`
   silently (`artifacts.py:16,23`), so `prior_meta.get("depends_on", [])` yields `[]` and
   collapses to case (1). Filed as **A-68** / **A-60**.
6. **Turn path where an upstream has no resolvable artifact.** `turn_service.py:140-142` drops
   any upstream whose `latest_artifact_path` is `None`, and that helper does not understand the
   grounding pointer (T1's A-14). The recorded list is then a strict subset of the declared
   dependencies, and a change to the omitted upstream is undetectable. Not reachable today from
   the UI (approval requires an artifact), but reachable by manual file deletion. **Handed to T1**
   — the defect is inside `turn_service`.

### Q2 trace — `propagate_staleness`, and edit sequences that fail to mark a stage stale

`propagate_staleness` (`turn_service.py:52-96`) runs in two phases. Phase 1 is hash-driven over
the *direct* dependents of the changed stage, and skips any dependent whose DB row is not
`approved` (`:68`). Phase 2 is status-driven and cascades only from stages phase 1 actually
flipped. Three structural consequences follow:

- an empty recorded `depends_on` short-circuits phase 1 **and** starves phase 2;
- a dependent sitting in `awaiting_review` (an unapproved draft) is skipped entirely and is never
  enqueued, so nothing downstream of it is reconsidered either;
- `_current_upstream_hashes` keys by the *current* latest path, so deleting an upstream's newest
  artifact file silently rewrites what "current" means.

**Worked sequence (fails to mark stale — the SEED-5 hole, end to end):**

1. `POST /projects` → project created; `ideation` is `ready`, everything else `locked`.
2. `POST .../stages/ideation/chat` → turn writes `01-ideation/artifact.v1.md`. Approve it.
   `scripting` unlocks to `ready`.
3. `POST .../stages/scripting/edit` with the script pasted in — **no turn is ever run on
   `scripting`**. The route's only guard is `is_locked_or_running` (`routes/stages.py:237`), and
   `ready` passes it. `latest_artifact_path` returns `None` → `prior_meta = {}` →
   `02-scripting/artifact.v1.md` is written with `depends_on: []` (`routes/stages.py:248-251,277`).
   Approve it.
4. Run and approve `styleboard`, `voiceover`, `visual`, `music`, `assembly`, `repurpose` normally.
   Each records a real `depends_on` naming `02-scripting/artifact.v1.md` and its hash.
5. `POST .../stages/ideation/edit` (or a regenerate) → `01-ideation/artifact.v2.md`.
6. `propagate_staleness(changed="ideation")` → the only dependent of `ideation` is `scripting`;
   `scripting` is `approved`; its recorded `depends_on` is `[]`;
   `is_stale([], …)` returns `False`. `newly_stale` is empty, so phase 2 never runs.

**Result: not one stage in the project is marked stale.** All nine remain `approved` on top of a
superseded ideation brief, and the UI shows a fully-green pipeline. Filed as **A-60**.

**Second worked sequence (draft-shaped hole, `turn_service`-owned — handed to T1):** with every
stage approved, regenerate `visual` (it becomes `awaiting_review`; `assembly` correctly goes
stale), then edit `scripting`. Phase 1 skips `visual` because it is not `approved`
(`turn_service.py:68`) and never enqueues it. The `visual` draft — built on the superseded
`scripting` — carries no stale marker, and approving it records the obsolete hash as current
provenance.

### Q3 trace — version numbering verdict

`_VERSION_RE` captures `(\d+)` and `_versions_in` calls `int()` on it (`artifacts.py:10,40`), so
both `next_version_number` and `latest_artifact_path` compare **integers, not strings**.
`artifact.v10.md` correctly outranks `artifact.v9.md` — **the string-sort hazard does not exist
here.** What does not hold: monotonicity is derived entirely from the filesystem with no DB
record (A-66), the read-then-write is unlocked and spans a full gate run (A-65), gaps are
tolerated harmlessly but deletion of the *highest* version reuses its number (A-66), and
non-numeric or zero-padded siblings are silently dropped or tie nondeterministically (A-67).

### Q8 trace — `preflight.reconcile_orphaned_turns` verification

The docstring claim at `turn_service.py:194-199` — that an aborted turn is invisible to
preflight's startup sweep — is **verified true**. `reconcile_orphaned_turns` iterates
`db_mod.list_running_turns`, whose SQL is `WHERE status = 'running'` (`db.py:112-113`); a turn the
`except BaseException` handler already stamped `aborted` (`turn_service.py:210`) is never
returned, so `_unwedge_stage` is never invoked for it. The two mechanisms compose correctly: the
in-handler recovery covers soft aborts, the startup sweep covers hard process death where no
handler ran. **Catches:** turns still `running` after a hard kill, and the `running` stage rows
behind them. **Misses:** a stage stuck at `running` with no `running` turn row (`_unwedge_stage`
returns early at `preflight.py:28`); anything wedged in `no_artifact`; a half-written
`raw_output.md` left by the dead turn (A-77); and it actively *mis*fires under multiple uvicorn
workers (A-76).

---

### A-60 · Hand edit copies `depends_on` from the prior artifact; empty on a first edit and sticky forever

- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/stages.py:248-251`, `pipeline-app/pipeline_app/routes/stages.py:277`, `pipeline-app/pipeline_app/state_machine.py:34-40`, `pipeline-app/pipeline_app/turn_service.py:78-80`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: `depends_on` is copied, never recomputed, on the only non-turn artifact-write path. With no prior artifact it is `[]`; `is_stale([], …)` returns `False` unconditionally and `propagate_staleness` never enqueues the stage, so the staleness cascade terminates at that node and every stage below it stays `approved` on superseded input. The value is also sticky — subsequent hand edits copy the empty list forward, so only a full turn on that stage can ever repair it. When a prior value does exist but names a superseded upstream version, the new artifact records a provenance it was not actually derived from.
- **trigger**: A first-ever hand edit on any stage that has not yet run a turn (see the worked sequence in the Q2 trace), or any hand edit made after the stage's upstream has already advanced a version.
- **proposed_fix**: Recompute `depends_on` from the current upstream artifacts on the edit path exactly as `run_stage_turn` does, rather than copying `prior_meta`; the upstream resolution logic already exists and should be factored into a shared helper so the two write paths cannot diverge again.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T3
- **detected_by**: manual-trace

### A-61 · Backfilled styleboard artifacts record `depends_on: []` and are approved, exempting the stage from staleness

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/migrations.py:63-82`, `pipeline-app/pipeline_app/migrations.py:145`, `pipeline-app/pipeline_app/migrations.py:155-157`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: `_write_synthetic_artifact` hardcodes `"depends_on": []` while `_backfill_one_project` sets the row to `approved`. `styleboard` declares `depends_on: [scripting]` in `pipeline.yaml`, so on every migrated project a `scripting` change can never flip `styleboard` stale — the operator sees a green styleboard whose world lock was reconstructed against a script that has since been rewritten, and `visual` is then regenerated against that unflagged world lock. The row is also written directly through `db_mod`, bypassing `approval_service.approve_stage`, so it is the one approved artifact in the app carrying no `gates` key at all.
- **trigger**: Any project that predates the `styleboard` stage having its `scripting` artifact regenerated or hand-edited after the migration has run.
- **proposed_fix**: Compute the synthetic artifact's `depends_on` from the scripting artifact that actually exists on disk at backfill time, so the reconstructed styleboard participates in the cascade like any other artifact; record an explicit `backfilled` gate result rather than omitting the key.
- **fix_cost**: S
- **depends_on_finding**: [A-60]
- **owner_task**: T3
- **detected_by**: manual-trace

### A-62 · Hand-edit path runs Gate C with no upstream map — a different gate recorded under the same name

- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/stages.py:266`, `pipeline-app/pipeline_app/turn_service.py:238-240`, `pipeline-app/pipeline_app/gates.py:82-96`, `pipeline-app/pipeline_app/gates.py:66-72`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: The turn path calls `run_gates_for_stage(..., upstream_by_stage)`; the edit path calls it with the `upstream` argument omitted, so it defaults to `{}`. For `visual`, `run_prompt_sheet_gate` then takes the `styleboard_path is None` branch and lints the sheet against **its own embedded WORLD LOCK** instead of the styleboard's — the legacy path the module's own docstring calls out as the thing that must not happen ("two gates wearing one name — a stricter CLI and a laxer app — is worse than having no app gate at all"). A hand edit can therefore rewrite the sheet's world lock and have Gate C validate the sheet against the rewritten world, recording `gate_c_prompt_sheet: pass`, while the styleboard the shot slots are actually bound to says something else. Conversely, a current-shape sheet (which is instructed not to re-emit the world lock) has an empty `world`, so `check_world_lock` emits a C8 per Register-A shot and the edit is blocked by a gate naming the wrong problem. No test exercises `visual/edit` or `styleboard/edit`.
- **trigger**: `POST /projects/{id}/stages/visual/edit` on any project.
- **proposed_fix**: Build the same `upstream_by_stage` mapping on the edit path that `run_stage_turn` builds and pass it into `run_gates_for_stage`, so both artifact-write paths hold the output to an identical gate. Add edit-path coverage for a gate that consumes upstream.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T3
- **detected_by**: manual-trace

### A-63 · `write_artifact`, `stamp_final` and `record_gate_override` truncate in place — no temp+rename

- **severity**: S0
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/artifacts.py:72-76`, `pipeline-app/pipeline_app/artifacts.py:79-88`, `pipeline-app/pipeline_app/artifacts.py:91-105`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: All three use `Path.write_text`, which opens in `"w"` mode — the existing file is truncated to zero before a byte of new content is written, and there is no `fsync`. `stamp_final` and `record_gate_override` are read-modify-write over the **only copy** of an already-approved artifact, so a crash, a power loss, or a disk-full condition during approval destroys the approved output with nothing to recover from (artifacts are the sole durable record; `runs/` is git-ignored). A partial write typically loses the closing `---`, at which point `parse_frontmatter` reports the wreckage as a legitimate no-frontmatter artifact rather than as damage (see A-68), and `latest_artifact_path` still selects it as the stage's current output.
- **trigger**: Process death, power loss, or a full/failing disk at any instant during an artifact write or an approval stamp.
- **proposed_fix**: Write to a sibling temp file, `fsync` it, then `os.replace` onto the target so the artifact is either the old bytes or the new bytes and never a truncation; apply the same to `grounding_service.write_pointer`.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T3
- **detected_by**: manual-trace

### A-64 · `raw_output.md` is written non-atomically before the artifact, and the crash window loses the edit entirely

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/stages.py:263-266`, `pipeline-app/pipeline_app/routes/stages.py:280`, `pipeline-app/pipeline_app/turn_service.py:161`, `pipeline-app/pipeline_app/turn_service.py:225-231`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: The edit route truncates and rewrites the shared `raw_output.md` at `:265`, then runs the gate, then writes the versioned artifact at `:280`. A crash inside that window (which spans a full linter load and execution) leaves `raw_output.md` holding the new body with **no artifact version recording it** — the operator's edit exists nowhere in the versioned history, and `raw_output.md` now silently disagrees with the stage's latest artifact. The same file is the turn path's change-detection baseline (`before_mtime`), so a subsequent resumed turn that does not rewrite it reports `no_artifact` and regresses the stage's status even though a valid artifact is on disk.
- **trigger**: Process death between the `raw_output.md` write and the `write_artifact` call, or any resumed turn following a hand edit.
- **proposed_fix**: Write `raw_output.md` atomically and mint the artifact version from the same in-memory body rather than re-reading a shared scratch file; give the edit path its own scratch path so it cannot poison the turn path's mtime baseline.
- **fix_cost**: M
- **depends_on_finding**: [A-63]
- **owner_task**: T3
- **detected_by**: manual-trace

### A-65 · `next_version_number` is an unlocked read-then-write spanning a gate run; concurrent writes collide and one is lost

- **severity**: S0
- **confidence**: probable
- **evidence**: `pipeline-app/pipeline_app/artifacts.py:44-46`, `pipeline-app/pipeline_app/artifacts.py:72-76`, `pipeline-app/pipeline_app/routes/stages.py:253`, `pipeline-app/pipeline_app/routes/stages.py:280`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: `next_version_number` globs the directory and returns `max+1` with no lock, no reservation, and no DB-side sequence; `write_artifact` then calls `write_text`, which silently overwrites an existing file. On the edit path the two are separated by the entire gate run (`:253` → `:266` → `:280`), a window wide enough to load and execute a linter. `edit_stage_output_route` is a sync `def`, so Starlette dispatches it into the threadpool — two concurrent POSTs to the same stage both observe a non-`running` status, both compute version N, and the second silently overwrites the first, discarding an artifact version and its recorded gate results with no error surfaced. The two requests also interleave on the same `raw_output.md`, so the gate can execute against a body neither request submitted. Unlike the turn path, the edit path performs no `any_turn_running` check at all.
- **trigger**: Two overlapping `POST .../edit` requests for one stage — a double-submit, a retried request, or two open tabs.
- **proposed_fix**: Make version allocation exclusive — either open the target with `O_EXCL` and retry on collision, or allocate the version from a DB row under the same lock that already serializes turns — and extend the app's single-flight check to the edit path.
- **fix_cost**: M
- **depends_on_finding**: [A-71]
- **owner_task**: T3
- **detected_by**: manual-trace

### A-66 · Version numbers derive from the filesystem alone; deleting the newest artifact silently reuses its number

- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/artifacts.py:35-46`, `pipeline-app/pipeline_app/schema.sql:19-27`, `pipeline-app/pipeline_app/routes/stages.py:276`
- **component**: artifacts
- **failure_mode**: latent
- **blast_radius**: No table records artifact versions, so the sequence is whatever the directory currently contains. Deleting `artifact.v3.md` when v1–v3 exist makes the next write v3 again: the version number, the `supersedes` chain and the `version:` frontmatter field all lie about history, and any dependent whose `depends_on` recorded the old v3 hash now compares against a different file at the same path. A gap in the middle (v2 deleted) is harmless for allocation but leaves `supersedes` naming a file that no longer exists, and the `version:` field in frontmatter is never cross-checked against the filename, so a rename desynchronizes them permanently and silently.
- **trigger**: Any manual deletion, restore, or rename inside a `runs/*/NN-stage/` directory — an ordinary operator action given `runs/` is git-ignored and hand-managed.
- **proposed_fix**: Record each minted version in a `stage_artifacts` table and allocate from it, treating the filesystem as the payload store rather than the sequence of record; validate the frontmatter `version` against the filename on read.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T3
- **detected_by**: manual-trace

### A-67 · Non-numeric `artifact.v*.md` siblings are silently ignored; zero-padded duplicates make `latest_artifact_path` nondeterministic

- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/artifacts.py:10`, `pipeline-app/pipeline_app/artifacts.py:35-41`, `pipeline-app/pipeline_app/artifacts.py:49-53`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: `_versions_in` globs `artifact.v*.md` but keeps only names matching `artifact\.v(\d+)\.md$`, and drops every non-match without a warning — `artifact.vfinal.md`, `artifact.v2b.md`, `artifact.v3 (copy).md` are invisible to both version allocation and latest-artifact resolution, so a rescued or hand-annotated artifact vanishes from the app while sitting in plain sight in the directory. Zero-padding is worse: `artifact.v07.md` and `artifact.v7.md` both parse to `7`, and `max(versions, key=…)` resolves the tie by glob iteration order, so which one the app treats as the stage's output is filesystem-dependent and can change between runs. (Verified non-issue: the comparison is integer, so `v10` correctly outranks `v9`.)
- **trigger**: Any hand-named file placed in a stage directory, including the natural OS-generated copy names.
- **proposed_fix**: Warn (or surface on `/doctor`) when a `artifact.v*.md` file exists that the version regex rejects, and reject duplicate parsed version numbers rather than resolving the tie arbitrarily.
- **fix_cost**: S
- **depends_on_finding**: [A-66]
- **owner_task**: T3
- **detected_by**: manual-trace

### A-68 · `parse_frontmatter` returns `({}, text)` for an unterminated block, masking a truncated artifact as an unversioned one

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/artifacts.py:13-23`, `pipeline-app/pipeline_app/routes/stages.py:251`, `pipeline-app/pipeline_app/turn_service.py:74`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: Three distinct conditions collapse to the same indistinguishable `{}` return: no frontmatter at all (`:16`), an opening `---` with no closing delimiter (`:23` — the fall-through after the loop), and an empty YAML block. The second is precisely the shape a crash-truncated artifact takes (A-63), and the caller cannot tell corruption from a legitimately plain markdown file. Downstream, `prior_meta.get("depends_on", [])` yields `[]` (A-60), `meta.get("gates")` yields `[]`, and `meta.get("status")` yields `None` so an already-final artifact is re-stamped. Nothing anywhere logs that a `---` was opened and never closed.
- **trigger**: Reading any artifact whose frontmatter block was truncated mid-write, or any file placed in a stage directory that opens with `---`.
- **proposed_fix**: Distinguish the three cases — return a sentinel or raise for an opened-but-unterminated block — so a truncated artifact fails loudly instead of degrading into a valid-looking one with no provenance.
- **fix_cost**: S
- **depends_on_finding**: [A-63]
- **owner_task**: T3
- **detected_by**: manual-trace

### A-69 · `parse_frontmatter` neither validates that the YAML is a mapping nor contains `YAMLError`

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/artifacts.py:21`, `pipeline-app/pipeline_app/routes/stages.py:100`, `pipeline-app/pipeline_app/turn_service.py:74`, `pipeline-app/pipeline_app/approval_service.py:43`
- **component**: artifacts
- **failure_mode**: loud
- **blast_radius**: Two uncontained failures share one root. (a) `yaml.safe_load` returns whatever the block parses to — a str, a list, or an int are all possible when a body's leading `---` is mistaken for a frontmatter opener — and every caller immediately calls `.get()` on it, raising `AttributeError` and a bare 500 with no indication of which artifact is at fault. (b) `yaml.YAMLError` propagates uncaught; `migrations.py:39` explicitly catches it, but the route, approval and staleness paths do not. The worst placement is `turn_service.py:74`, inside `propagate_staleness`'s phase-1 loop: one malformed dependent aborts the cascade **mid-iteration**, leaving some dependents flipped to `stale` and the rest silently left `approved`, with the exception surfacing only as a broken SSE stream after the new artifact was already written and the stage status already advanced.
- **trigger**: Any artifact whose frontmatter is malformed YAML or parses to a non-mapping — reachable by hand edit, by partial write, or by a body that begins with a markdown horizontal rule.
- **proposed_fix**: Have `parse_frontmatter` return `{}` (or raise one typed, named error) when the parsed value is not a mapping, and catch `yaml.YAMLError` at the parse boundary so callers get one predictable failure mode naming the offending path.
- **fix_cost**: S
- **depends_on_finding**: [A-68]
- **owner_task**: T3
- **detected_by**: manual-trace

### A-70 · One shared autocommit connection: no transaction boundary around any multi-row invariant

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/db.py:15-20`, `pipeline-app/pipeline_app/main.py:24`, `pipeline-app/pipeline_app/project_service.py:42-49`, `pipeline-app/pipeline_app/migrations.py:155-157`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: `check_same_thread=False` plus WAL and `busy_timeout` make the *connection* usable across threads, and sqlite's own serialization prevents corruption — but every helper in `db.py` commits immediately after its single statement, so the app has no transaction boundary anywhere. Multi-row invariants are therefore never atomic: `create_project` commits the project row, then each stage row, then each directory (`project_service.py:42-49`); `_backfill_one_project` inserts an `approved` styleboard row and *then* sets `approved_at` (`migrations.py:155-157`), so an interruption yields `status='approved', approved_at=NULL`; `approve_stage` commits the approval and each unlock separately; `propagate_staleness` commits each flip separately. Because the same connection is shared by threadpool routes and the event-loop `stage_chat` path, one thread's `commit()` also finalizes another's in-flight statements, and a page render can observe a half-completed cascade.
- **trigger**: Any failure, restart, or concurrent request during a multi-statement operation — a `mkdir` OSError inside `create_project`, or a page load during `propagate_staleness`.
- **proposed_fix**: Wrap each logical operation (project creation, approval + unlock, the staleness cascade, per-project backfill) in one explicit transaction and commit once at its boundary, rather than committing inside every leaf helper.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T3
- **detected_by**: manual-trace

### A-71 · `turns` has no partial unique index on `status='running'`, though `discovery_runs` does

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/schema.sql:58-59`, `pipeline-app/pipeline_app/schema.sql:19-27`, `pipeline-app/pipeline_app/db.py:112-113`, `pipeline-app/pipeline_app/turn_service.py:22-23`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: The discovery subsystem enforces its single-running invariant in the schema (`ux_discovery_single_running`, a partial unique index). The pipeline's identical invariant has no such backstop: `any_turn_running` is a plain `SELECT` followed by an unguarded `INSERT`, checked twice at application level (route pre-check and `run_stage_turn`) but never at the storage level. Two concurrent chat POSTs can both read zero running turns and both insert one, launching two Claude subprocesses that write the same `raw_output.md` and both mint a version through the unlocked allocator (A-65). The asymmetry also means the two subsystems' durability guarantees differ despite reading identically in the code.
- **trigger**: Two overlapping `POST .../chat` requests, or a chat and an edit racing on one stage.
- **proposed_fix**: Add the same partial unique index to `turns` on `status = 'running'` so the storage layer rejects the second insert regardless of what the application-level checks observed. (The race at the call sites is T1/T2's; the missing constraint is the schema's.)
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T3
- **detected_by**: manual-trace

### A-72 · No migration versioning: `CREATE TABLE IF NOT EXISTS` on every boot means a later column change silently never lands

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/schema.sql:1`, `pipeline-app/pipeline_app/schema.sql:9`, `pipeline-app/pipeline_app/schema.sql:19`, `pipeline-app/pipeline_app/db.py:23-29`, `pipeline-app/pipeline_app/main.py:23`
- **component**: artifacts
- **failure_mode**: latent
- **blast_radius**: There is no `schema_migrations` table, no version stamp, and no `ALTER TABLE` path — the entire strategy is "re-run `schema.sql` every boot", and every statement in it is `IF NOT EXISTS`. On a database that already has the table, a newly added column, `CHECK`, or `UNIQUE` constraint is silently skipped: `init_db` reports success, the app boots clean, and the first query touching the new column fails at runtime with `no such column` in whatever route happens to hit it first. `migrations.py` is not a versioned framework either — it is one hardcoded backfill function that re-runs unconditionally (`main.py:25`) and relies on its own per-project guard for idempotence, so there is no place to register a second migration that must run exactly once.
- **trigger**: The next schema change to any existing table, on any developer machine or operator install whose `pipeline.db` predates it.
- **proposed_fix**: Introduce a `schema_version` table and an ordered, once-only migration list applied at startup, keeping `schema.sql` as the create-from-scratch path only; fail loudly when the DB's version exceeds or lags what the code supports.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T3
- **detected_by**: manual-trace

### A-73 · Backfill writes `artifact.v1.md` at a hardcoded version and overwrites unconditionally

- **severity**: S0
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/migrations.py:63-82`, `pipeline-app/pipeline_app/migrations.py:107-120`, `pipeline-app/pipeline_app/migrations.py:191-197`, `pipeline-app/pipeline_app/artifacts.py:72-76`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: `_write_synthetic_artifact` passes a literal `1` to `write_artifact` rather than calling `next_version_number`, and `write_artifact` overwrites without checking. The function is guarded only by "this project has no styleboard **DB row**" (`:193`) — a filesystem check is never made. `runs/` and `pipeline-app/pipeline.db` are independently git-ignored and independently disposable, so resetting or relocating the database while `runs/` persists makes the next boot rewrite every project's real `02b-styleboard/artifact.v1.md` with the synthetic "not recoverable" body, destroying genuine styleboards with no backup and no warning. The same hazard applies within the migration's own retry loop: the disk **write** at `:108`/`:129` precedes the DB write at `:155`, so a failure in between leaves an artifact with no row and the next boot rewrites it with a fresh `now`, changing its sha256 and spuriously staling dependents — the docstring at `:178-181` accounts only for the risky *read* preceding the DB write, not the risky write.
- **trigger**: Deleting, moving, or pointing `--db-path` at a different `pipeline.db` while `runs/` is intact; or any interruption between the synthetic artifact write and `create_stage_row`.
- **proposed_fix**: Refuse to write a synthetic artifact into a stage directory that already contains any `artifact.v*.md`, and allocate the version via `next_version_number` instead of hardcoding 1; order the DB row insert before the disk write, or make the pair transactional.
- **fix_cost**: S
- **depends_on_finding**: [A-63, A-72]
- **owner_task**: T3
- **detected_by**: manual-trace

### A-74 · Backfill failure is stderr-only; the project loses `styleboard` and the UI blames the wrong thing

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/migrations.py:196-205`, `pipeline-app/pipeline_app/main.py:25-27`, `pipeline-app/pipeline_app/routes/stages.py:56-58`, `pipeline-app/pipeline_app/routes/doctor.py:20`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: A per-project `OSError`/`UnicodeDecodeError`/`YAMLError` prints one line to stderr and continues. `app.state.backfilled_projects` records only the projects that *succeeded* — skips are recorded nowhere, and `/doctor` surfaces `orphaned_count` but nothing about backfill at all. The affected project is left with no `styleboard` stage row, which means `stages_to_unlock` can never satisfy `visual`'s dependencies so `visual` is permanently `locked`, and navigating to the styleboard page returns **"Stage not applicable to this project"** — a message that asserts a brand-scoping decision when the real cause is a failed migration. An operator running under a service manager or a detached uvicorn never sees the stderr line at all.
- **trigger**: A locked, unreadable, or non-UTF-8 legacy visual artifact during startup — including a transient Windows file lock from an indexer or antivirus scan.
- **proposed_fix**: Collect skipped projects into app state alongside `backfilled_projects` and render them on `/doctor` with the reason; distinguish "stage not in this project's brand scope" from "stage row missing unexpectedly" in the 404 detail.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T3
- **detected_by**: manual-trace

### A-75 · `schema.sql`: no index on `turns.stage_row_id`, no status `CHECK`s, no `ON DELETE` behavior

- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/schema.sql:19-27`, `pipeline-app/pipeline_app/schema.sql:61-68`, `pipeline-app/pipeline_app/schema.sql:9-17`, `pipeline-app/pipeline_app/db.py:106-109`
- **component**: artifacts
- **failure_mode**: latent
- **blast_radius**: `turns.stage_row_id`, `discovery_run_handles.run_id` and `discovery_run_handles.handle_id` are declared as foreign keys with no covering index, so `list_turns` and every FK integrity check are full scans — harmless at current volumes but it grows monotonically with every turn ever run, since nothing prunes `turns`. No `CHECK` constraint pins `stages.status`, `turns.status`, or `projects.brand` to their enums, so a typo'd status written by any future code path is accepted and then silently fails every `is_locked_or_running`/`is_stale` comparison. No FK declares `ON DELETE`, so a future delete path would either fail or orphan rows depending on the pragma state. (`stages` is adequately indexed by its `UNIQUE(project_id, stage_id)`.)
- **trigger**: Long-running installs (index absence), or any code path or manual `UPDATE` writing a status value outside the enum.
- **proposed_fix**: Add indices on the three unindexed FK columns, `CHECK` constraints mirroring `StageStatus` and the turn-status vocabulary, and explicit `ON DELETE` clauses — folded into the versioned migration path from A-72, since `IF NOT EXISTS` cannot apply them to an existing DB.
- **fix_cost**: S
- **depends_on_finding**: [A-72]
- **owner_task**: T3
- **detected_by**: manual-trace

### A-76 · The startup orphan sweep runs per-process, so a second uvicorn worker orphans a live turn

- **severity**: S3
- **confidence**: probable
- **evidence**: `pipeline-app/pipeline_app/main.py:28-30`, `pipeline-app/pipeline_app/main.py:46-57`, `pipeline-app/pipeline_app/preflight.py:12-18`, `pipeline-app/pipeline_app/preflight.py:38-40`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: `reconcile_orphaned_turns` runs inside `create_app`, which `create_default_app` invokes once per worker process. It unconditionally marks **every** `running` turn `orphaned` and unwedges its stage — it has no notion of which process owns a turn (no PID, no heartbeat, unlike `discovery_runs`, which has `heartbeat_at` and `reclaim_stale_runs`). Starting a second worker, or any process attaching to the same `pipeline.db`, therefore declares an actively-streaming turn dead, flips its stage to `awaiting_review`/`ready` mid-flight, and releases the single-flight lock so a second turn can start against the same `raw_output.md` while the first is still writing to it. Nothing in the code or the run configuration pins `--workers 1`.
- **trigger**: `uvicorn … --workers N` with N>1, or launching a second app instance against the same database while a turn is running.
- **proposed_fix**: Record an owner token and heartbeat on `turns` as `discovery_runs` already does, and reclaim only turns whose heartbeat has gone stale — or move reconciliation out of `create_app` into a guarded single-instance startup step.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T3
- **detected_by**: manual-trace

### A-77 · Orphan recovery is invisible to the operator and leaves the dead turn's `raw_output.md` in place

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/preflight.py:38-40`, `pipeline-app/pipeline_app/main.py:28-30`, `pipeline-app/pipeline_app/routes/doctor.py:20`, `pipeline-app/pipeline_app/turn_service.py:161`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: `_unwedge_stage` restores the stage to `awaiting_review` whenever *any* artifact resolves — but that artifact is the one from a *previous* turn; the killed turn produced nothing. The resulting state is byte-identical to a healthy stage awaiting review, so the operator approves stale output believing the last turn succeeded. `/doctor` shows a bare `orphaned_count` with no project, stage, or turn identity, and the stage page shows nothing at all. Meanwhile the dead turn's partially-written `raw_output.md` is never removed or versioned, and it becomes the `before_mtime` baseline for the next turn — so a resumed turn that rewrites identical content is detected as a change while one that writes nothing is reported `no_artifact`.
- **trigger**: Any hard process kill during a turn, followed by a restart.
- **proposed_fix**: Record on the stage (or surface on the stage page and `/doctor`) that its last turn was orphaned, naming the project/stage, and quarantine or delete the orphaned `raw_output.md` so it cannot masquerade as the next turn's baseline.
- **fix_cost**: S
- **depends_on_finding**: [A-76]
- **owner_task**: T3
- **detected_by**: manual-trace

### A-78 · `create_project` commits the project row before its stage rows and directories, with no repair path

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/project_service.py:42-49`, `pipeline-app/pipeline_app/db.py:32-38`, `pipeline-app/pipeline_app/db.py:49-55`, `pipeline-app/pipeline_app/migrations.py:183-193`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: The project row is inserted and committed, then `run_dir.mkdir`, then each stage row and each stage directory in a loop with a commit per row. Any failure partway — an `OSError` from a path exceeding the Windows limit (nothing bounds the slug length, and the run directory nests to `runs/<slug>-<ts>/02b-styleboard/events/<ms>.jsonl`), a permissions error, a disk-full — leaves a committed project with a partial set of stage rows. Nothing repairs it: `backfill_styleboard_rows` only ever adds the single `styleboard` row, and a stage with no row 404s as "Stage not applicable to this project", so the project is permanently, silently unusable while appearing normally in the project list. The route only catches `ValueError`, so the failure itself surfaces as a bare 500.
- **trigger**: A long slug, a restricted `runs/` directory, or any I/O failure during project creation.
- **proposed_fix**: Create all stage rows in one transaction and create directories before committing (or lazily on first use), so a project either exists completely or not at all; bound the slug length so the deepest run path stays within the platform limit.
- **fix_cost**: M
- **depends_on_finding**: [A-70]
- **owner_task**: T3
- **detected_by**: manual-trace

### A-79 · Distinct project names collapse to one slug; `run_id` uniqueness rests on second resolution and collides as a 500

- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/project_service.py:13-20`, `pipeline-app/pipeline_app/project_service.py:33`, `pipeline-app/pipeline_app/schema.sql:3`, `pipeline-app/pipeline_app/routes/projects.py:26-36`
- **component**: artifacts
- **failure_mode**: loud
- **blast_radius**: `_SLUG_RE` collapses every run of non-`[a-z0-9-]` characters to a single hyphen and lowercases, so `"My Topic"`, `"my_topic"`, `"my.topic"` and `"my/topic"` all become `my-topic`. Path traversal is correctly neutralized (dots are stripped, and `project_service.py:39` re-checks the resolved parent), and `projects.slug` is deliberately non-unique — but that makes `run_id` uniqueness rest **entirely** on a `%Y%m%d-%H%M%S` timestamp. Two projects created with the same sanitized slug inside one second violate the `UNIQUE` constraint on `projects.run_id`; `db_mod.create_project` raises `sqlite3.IntegrityError`, and the route catches only `ValueError`, so the operator gets an unhandled 500 rather than "try again". No directory is orphaned (the `mkdir` follows the insert), but two differently-named projects remain indistinguishable in the project list, which identifies each row only by `run_id` — the shared slug plus a timestamp — and the operator's original wording is never stored.
- **trigger**: Two project creations with names that sanitize identically within the same second, e.g. a double-submitted form.
- **proposed_fix**: Catch `sqlite3.IntegrityError` in the route and return a 409 telling the operator to retry, and either add sub-second resolution to `run_id` or a short random suffix; show the raw entered name alongside `run_id` in the project list.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T3
- **detected_by**: manual-trace

### A-80 · The grounding pointer has no hash or version pinning — the brief can change under an approved stage

- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/grounding_service.py:24-31`, `pipeline-app/pipeline_app/grounding_service.py:11-14`, `pipeline-app/pipeline_app/routes/stages.py:157-160`, `pipeline-app/pipeline_app/artifacts.py:56-69`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: `write_pointer` stores a single key, `rgs_brief_path` — no sha256, no version, no timestamp. The hashing machinery to pin it already exists and is thrown away: `snapshot_rgs_briefs` computes sha256 for every brief and `identify_new_brief` uses them only to work out which filename appeared, then discards them (`routes/stages.py:166,182-186`). Consequences: **edited** — the brief an approved grounding stage points at can be rewritten with no staleness signal whatsoever, and because no stage declares `depends_on: [grounding]` in `pipeline.yaml`, `propagate_staleness` structurally cannot reach it even if a hash were recorded; **deleted or renamed** — `resolve_latest_artifact` returns `None` so approval fails loudly, but the grounding stage row stays `approved` and, critically, `stage_chat` reads the pointer directly at `:160` with **no existence check** and injects the dangling path into every downstream RGS stage's kickoff prompt, so the model is handed a path to a file that is not there.
- **trigger**: Editing, renaming, or deleting a file in `rgs-briefs/` after a grounding turn has written its pointer — the ordinary way a brief gets corrected.
- **proposed_fix**: Record the target's sha256 (and size) in `pointer.yaml` at write time, verify it on read, and surface a mismatch as staleness on the grounding stage and every RGS stage prompted with it; check existence before injecting `grounding_pointer` into a prompt.
- **fix_cost**: M
- **depends_on_finding**: [A-14]
- **owner_task**: T3
- **detected_by**: manual-trace

### A-81 · `identify_new_brief` returns `None` on 0 or ≥2 changed briefs, recording a successful turn as `no_artifact`

- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/grounding_service.py:17-21`, `pipeline-app/pipeline_app/grounding_service.py:11-14`, `pipeline-app/pipeline_app/routes/stages.py:182-189`
- **component**: artifacts
- **failure_mode**: silent
- **blast_radius**: Detection is "exactly one file changed, else nothing happened". If the grounding turn writes its new brief **and** touches any other `rgs-briefs/*.md` — a typo fix, a superseded-marker edit, an index update — `changed` has length 2, the function returns `None`, and the route sets the stage to `no_artifact` (`:189`) despite a perfectly good brief having been produced. The pointer is not written, so the brief is orphaned and every downstream RGS stage runs with `grounding_pointer=None`, silently losing its grounding. `snapshot_rgs_briefs` also globs only the top level (`glob("*.md")`, not `rglob`), so a brief written into a subdirectory is invisible and produces the same false `no_artifact`. The zero-change case correctly reports nothing, but is indistinguishable from these.
- **trigger**: A grounding turn that writes or modifies more than one file under `rgs-briefs/`, or writes into a subdirectory.
- **proposed_fix**: Identify the new brief by set difference on filenames (added files) rather than by change count, fall back to the most-recently-modified added file, and report "produced N briefs, expected 1" explicitly instead of collapsing it to `no_artifact`.
- **fix_cost**: S
- **depends_on_finding**: [A-80]
- **owner_task**: T3
- **detected_by**: manual-trace

### A-82 · `read_pointer` trusts both the YAML shape and the path it contains

- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/grounding_service.py:34-39`, `pipeline-app/pipeline_app/artifacts.py:66-68`
- **component**: artifacts
- **failure_mode**: loud
- **blast_radius**: `yaml.safe_load(...) or {}` guards only the empty case — a `pointer.yaml` containing a bare scalar or a list parses to a non-mapping and the immediate `.get()` raises `AttributeError` (a bare 500), the same class of defect as A-69. Separately, `resolve_latest_artifact` joins the stored value with `repo_root / pointer`; `pathlib` lets an absolute value override the base entirely, so a hand-edited or hand-restored `pointer.yaml` can make the app read and render a file anywhere on the machine. Blast radius is bounded — the app is single-user and local-only, the value is normally derived from `Path.name` inside `rgs-briefs/`, and `write_pointer` is non-atomic (A-63) so a hand-repaired pointer is a realistic operator action rather than a hostile one.
- **trigger**: A truncated, hand-edited, or hand-repaired `pointer.yaml`.
- **proposed_fix**: Validate that the parsed pointer is a mapping with a string `rgs_brief_path`, and reject any value that is absolute or resolves outside `repo_root / "rgs-briefs"` — the same defence-in-depth check `project_service.py:39` already applies to run directories.
- **fix_cost**: S
- **depends_on_finding**: [A-69]
- **owner_task**: T3
- **detected_by**: manual-trace

### A-83 · `cli_available` is a startup snapshot rendered beside a live probe of the same fact

- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/main.py:31`, `pipeline-app/pipeline_app/routes/doctor.py:16-24`, `pipeline-app/pipeline_app/preflight.py:43-48`
- **component**: artifacts
- **failure_mode**: docs-drift
- **blast_radius**: `app.state.cli_available` is computed once in `create_app` and threaded into every template as the global banner value, while `/doctor` additionally calls `check_cli_available()` live on each request and renders both in the same response. Installing or removing the Claude CLI while the app runs makes the two disagree on one page — the banner says unavailable, the doctor panel says available (or the reverse) — and the operator has no indication that one is a snapshot. Restart is the only way to reconcile them, and nothing says so.
- **trigger**: Installing, removing, or changing the `PATH` entry for the Claude CLI while the app is running.
- **proposed_fix**: Compute the banner value from the same live probe (cached briefly if the `shutil.which` cost matters) so a single request cannot report two different answers to the same question.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T3
- **detected_by**: manual-trace

### A-84 · The entire `/edit` artifact-write path has no UI entry point

- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/stages.py:229-290`, `pipeline-app/pipeline_app/templates/stage.html:26`, `pipeline-app/pipeline_app/templates/stage.html:59`
- **component**: artifacts
- **failure_mode**: coverage-gap
- **blast_radius**: `stage.html` renders exactly two forms — chat and approve. A grep across every template and every static asset finds no reference to `/edit` anywhere, so the hand-edit workflow the route implements (and that `routes/stages.py:283-287` cites the design spec for) is unreachable from the running app; only the test suite exercises it. Two opposite costs follow: the documented hand-edit capability does not actually exist for the operator, and a substantial artifact-write path — carrying A-60, A-62, A-64 and A-65 — is maintained, tested, and reachable by direct POST while receiving no real-world exercise that would surface those defects. It also caps the present-day blast radius of those four findings, and uncaps it the moment the UI is added.
- **trigger**: Any attempt to hand-edit a stage output through the app; or adding the edit form, which activates four latent defects at once.
- **proposed_fix**: Decide the route's status explicitly — either render the edit form and fix A-60/A-62/A-64/A-65 first, or remove the route — rather than leaving a second artifact-write path that diverges from the turn path with nothing exercising it.
- **fix_cost**: S
- **depends_on_finding**: [A-60, A-62, A-64, A-65]
- **owner_task**: T3
- **detected_by**: grep-sweep

### A-85 · `app.state.conn` is opened at construction and never closed; no lifespan handler

- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/main.py:16-43`, `pipeline-app/pipeline_app/db.py:5-20`, `pipeline-app/pipeline_app/db.py:23-29`
- **component**: artifacts
- **failure_mode**: latent
- **blast_radius**: `create_app` opens the shared connection and registers no shutdown hook, so it is closed only by process exit — the WAL is never explicitly checkpointed, leaving `pipeline.db-wal`/`-shm` beside the database after every run (all three are git-ignored, so this is invisible in the tree). Each test that builds an app leaks a connection and its WAL files for the life of the test process. `init_db` correctly opens and closes its own short-lived connection, which makes the asymmetry a deviation from the module's own established pattern rather than an oversight of principle.
- **trigger**: Every app shutdown, and every test that constructs an app.
- **proposed_fix**: Register a FastAPI lifespan handler that closes `app.state.conn` (running `PRAGMA wal_checkpoint(TRUNCATE)` first) on shutdown.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T3
- **detected_by**: manual-trace
