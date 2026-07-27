# Pipeline nav redesign — design spec

Date: 2026-07-27
Status: Approved

## Problem

The pipeline-app's project sidebar (`project_home.html`) renders the seven
pipeline stages as a flat, unordered `<ul>` in whatever order
`db.list_stages()` happens to return them — that query has no `ORDER BY`, so
the order is an accident of SQLite row storage, not a guarantee. The list
gives no visual indication of:

- which stage leads to which (no numbering, no connectors)
- that Voiceover and Visual are a parallel pair (both depend only on
  Scripting, neither depends on the other) rather than sequential steps
- that the Visual and Voiceover stages hand off to the `midjourney-prompting`
  and `elevenlabs-audio` specialist skills respectively (per the top-level
  `CLAUDE.md`'s pipeline-skill/specialist-skill boundary)

Separately, the sidebar is only rendered on the project-home page.
`routes/stages.py`'s stage-page GET handler never passes a `stages` variable
to `stage.html`, and `stage.html` never overrides `{% block sidebar %}`, so
navigating into any individual stage loses the pipeline overview entirely —
exactly when a user most wants to see where they are and what's next.

## Goals

- Render the seven stages in correct pipeline order, with the Voiceover/Visual
  parallel pair visually grouped rather than presented as two sequential steps.
- Show the `midjourney-prompting` / `elevenlabs-audio` specialist relationship
  as a small sub-label under the Visual / Voiceover stages.
- Show the same pipeline nav on both the project-home page and every
  individual stage page, with the current stage highlighted on stage pages.
- Keep styling minimal and low-maintenance: extend the existing ~10-line
  `style.css`, no new files, no build step, no JS, no new dependencies.

## Non-goals

- No change to `pipeline.yaml`'s stage semantics, dependency graph, or the
  state machine (`state_machine.py`).
- No change to how stages are created, approved, or run — purely a
  read/display concern.
- Midjourney and ElevenLabs remain specialist skills invoked *within* the
  Visual/Voiceover stages, not new pipeline stages with their own directory,
  status, or DB row — per `CLAUDE.md`'s explicit boundary ("the pipeline
  skill owns the creative call, the specialist owns the executable output").

## Design

### 1. Ordering & grouping model

`pipeline.yaml`'s existing `dir_prefix` field already encodes step order and
grouping: `00`=grounding, `01`=ideation, `02`=scripting, `03`=voiceover *and*
visual (shared prefix = the parallel pair), `04`=assembly, `05`=repurpose.
The nav's step number is `dir_prefix`; two stages sharing a `dir_prefix`
render as one grouped step.

`pipeline.yaml` gains one new optional field on the `voiceover` and `visual`
stage entries:

```yaml
  - id: voiceover
    skill: voiceover-brief
    specialist: elevenlabs-audio
    dir_prefix: "03"
    depends_on: [scripting]
  - id: visual
    skill: visual-prompts
    specialist: midjourney-prompting
    dir_prefix: "03"
    depends_on: [scripting]
```

All other stage entries omit `specialist` (defaults to absent/`None`).

### 2. Backend wiring

- `pipeline_config.StageDef` gains one new optional field:
  `specialist: str | None = None`, read via `s.get("specialist")` in
  `load_topology()` — same pattern as the existing optional `brand_scope`.
- A new pure function, `build_stage_nav(stage_defs, stage_rows)` in
  `pipeline_config.py`, merges the ordered `StageDef` list (already in
  correct pipeline order, already filtered to what actually applies) with a
  project's DB stage rows (matched by `stage_id`). Stages with no matching
  DB row (e.g. `grounding` on a non-RGS project) are simply omitted, same as
  today. Output: an ordered list of "steps," each step a list of 1–2 stage
  dicts (`id`, `status`, `specialist`, `dir_prefix`).
- `routes/projects.py`'s `project_home` handler and `routes/stages.py`'s
  stage-page GET handler both call `build_stage_nav()` and pass the result as
  `nav` in their template context. This is also the fix for the stage-page
  gap: the stage-page route did not previously pass any stage-list data.
- The stage-page route continues to pass `stage_id` (already does) so the
  template can mark the active step via a `.current` class.

### 3. Template/markup structure

- New partial `templates/_sidebar.html`: renders `nav` as an
  `<ol class="pipeline-nav">`. Each `<li>` is one step — either a single
  stage, or (for the voiceover/visual pair) two stages laid out side-by-side
  inside that one `<li>`. Each stage shows its existing `.status-*` badge and,
  if `specialist` is set, a small `↳ {{ specialist }}` sub-line.
- `base.html`'s `{% block sidebar %}` default content becomes
  `{% if nav %}{% include "_sidebar.html" %}{% endif %}`. Pages that don't
  pass `nav` (`project_list.html`, `skill_list.html`, `skill_editor.html`,
  `doctor.html`, `inspector.html`) render nothing in that block, identical to
  today's behavior.
- `project_home.html` and `stage.html` both drop their own sidebar markup
  (currently only `project_home.html` has any) and rely entirely on the
  shared default block content. `stage.html` needs no sidebar override at
  all now — it just inherits the default, with its route supplying `nav`.
- The current stage's `<li>` gets a `.current` class when rendered on
  `stage.html` (compared against `stage_id` in context), producing no
  highlight on `project_home.html` (no single "current" stage there).

### 4. CSS/styling

All additions live in the existing `pipeline_app/static/style.css`
(estimated +25–30 lines, no new files):

- `.pipeline-nav`: list-style reset, vertical flow layout.
- A connector line between steps via `border-left` on a wrapper element —
  pure CSS, no SVG/JS.
- The parallel pair: the two stages inside one `<li>` laid out with
  `display: flex` side-by-side, sharing the connector segments immediately
  above and below that step.
- `.current`: left accent border + subtle background, for the active-stage
  highlight on stage pages.
- `.specialist`: small, muted-color sub-line under a stage's name/status.
- Existing `.status-*` badge colors are reused unchanged — no new color
  system introduced.

## Testing

- `test_pipeline_config.py`: cover `specialist` field parsing (present,
  absent) and `build_stage_nav()`'s ordering/grouping/filtering logic
  (parallel-pair grouping, brand-scoped stage omission, specialist
  pass-through).
- `test_routes_projects.py` / `test_routes_stages.py`: assert `nav` is present
  in both routes' template context and reflects the expected grouped
  structure.
- No new test infrastructure needed — extends existing test files/patterns.

## Risks / open questions

None blocking. The one behavior change worth calling out explicitly: stage
display order is now driven by `pipeline.yaml`/`dir_prefix` order rather than
incidental DB row order — this is a correctness fix (the DB query never
guaranteed order), not a new invariant being introduced.
