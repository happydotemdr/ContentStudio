# Local Pipeline Control App — Design

**Status:** Approved, pending final user sign-off on this written spec.
**Date:** 2026-07-25

## Context

Today, ContentStudio's six generic skills (`shorts-ideation` → `shorts-scripting` →
{`voiceover-brief`, `visual-prompts`} → `shorts-assembly` → `social-repurpose`) plus the two
RaisingGoodSports (RGS) brand-specific skills (`rgs-grounding`, `rgs-pairing-review`) are run by
hand, one at a time, in a Claude Code conversation. There is no tracking of what's been done, no
enforced order, no persistent record of which files feed which stage, and no way to see or edit a
skill's own instructions without opening the raw files.

This spec adds a **local-only Python app** (reachable only from the user's own laptop) that turns
that manual process into a guided, stateful pipeline: one project per Short, walked stage by
stage, with enforced ordering, a chat interface per stage, visible input/output files, and a
skill viewer/editor.

**Relationship to `docs/superpowers/specs/2026-07-25-eval-and-io-boundaries-design.md`.** That
spec (approved, not yet implemented) already defines a `runs/<run_id>/NN-<stage>/artifact.vN.md`
layout, a `pipeline.yaml` topology file, and heavier enforcement (a finalize script, a Claude Code
`PreToolUse` hook, and Windows ACL locking) meant to stop an *unattended autonomous agent* from
overwriting an upstream artifact during eval runs with no human watching. This app adopts that
spec's `runs/` layout, versioning convention, and `pipeline.yaml` — one consistent convention for
the directory, not two competing ones. It deliberately does **not** build that spec's
finalize-script/hook/ACL-locking machinery or its eval suite: this app's threat model is different
(a human approves every stage transition through the UI, and the app itself is the only thing
invoking the Claude CLI), so the app's own gating logic is already the guardrail. Building
file-level immutability enforcement on top would solve a problem this app doesn't have.

## Goals

1. Walk the user step-by-step through the pipeline for a given Short, enforcing order (a stage
   can't be started until its upstream dependency is approved), while always making clear where
   they are, where they came from, and what's next — with a per-stage completion-status indicator.
2. Show the real input/output files and folders for every stage, including a standalone inspector
   for reading any properly-formatted Markdown file (frontmatter + body) on disk.
3. Provide a real chat interface per stage — multi-turn, not fire-and-forget — backed by the
   actual `claude` CLI in headless mode, using the user's existing Claude Code subscription login
   (not the Agent SDK, which Anthropic's own docs disallow using subscription auth for
   third-party-built products; not the raw API, which bills separately from the subscription).
4. Let the user view each skill's full definition (`SKILL.md` + `references/`) and a per-stage
   "kickoff" user-prompt template, with the ability to edit both from the UI.
5. Support both the six generic skills and the two RGS-specific skills, including the branching
   pair (`voiceover-brief` / `visual-prompts`) and the RGS-only grounding stage.

## Non-goals

- Not building the eval-and-io-boundaries spec's finalize script, `PreToolUse` hook, or Windows
  ACL locking. Not building its eval suite. Those remain a separate, already-approved, still
  unimplemented spec this app does not depend on.
- Not deploying, hosting, or exposing this app beyond `127.0.0.1` — matches ContentStudio's
  existing "local only" convention.
- Not orchestrating skills automatically (no auto-advance, no meta-skill) — the human always
  drives each stage's conversation and explicitly approves before advancing, same as today's
  manual process, just tracked and gated instead of ad hoc.
- Not modifying the six generic skills' or two RGS skills' actual corpus-grounded content —
  only their kickoff-template wrapper (a new, app-owned file) and whatever direct edits the user
  makes through the skill editor.

## Design

### 1. Architecture

```
Browser (127.0.0.1 only)
   │  htmx (server-rendered HTML, SSE for live chat streaming)
   ▼
FastAPI app — new top-level dir `pipeline-app/` in the ContentStudio repo
   │  asyncio subprocess, one at a time (global lock)
   ▼
claude -p "/skill-name ..." --resume <session_id> --output-format stream-json
   --include-partial-messages --allowedTools "Read,Glob,Grep,Write,Edit"
   │  cwd = ContentStudio repo root; reads/writes real files via its own tools
   ▼
runs/<run_id>/NN-<stage>/artifact.vN.md   (+ rgs-briefs/ for the grounding stage, unchanged)
```

- **`pipeline-app/`** — FastAPI backend, Jinja2 templates, static CSS, `stage_templates/`
  (editable kickoff-prompt text, one per stage — new, app-owned files, distinct from the real
  skill instructions), and `pipeline.db` (SQLite, gitignored).
- **`runs/`** (new top-level dir, gitignored, sibling to `docs/`, `.claude/`, `rgs-briefs/`) — one
  folder per project, named `<slug>-<YYYYMMDD-HHMMSS>` (the run's `run_id`), per the
  eval-and-io-boundaries spec's convention.
- **`pipeline.yaml`** (new, repo root, git-tracked) — static topology: which skill produces which
  stage, each stage's declared upstream dependency, and the directory-number prefix. This app
  creates and owns it (neither `pipeline.yaml` nor the eval suite exists yet); a future
  implementation of the eval-and-io-boundaries spec can read the same file.
- **SQLite** is the single source of truth for all *dynamic* state (project list, per-stage
  status, chat turns). No `project.json`, no `manifest.yaml` — a dual/triple source of truth for
  the same state was flagged as a real risk during design review and deliberately avoided. The
  filesystem (`runs/`) holds the actual artifact content and durable event logs; SQLite holds the
  queryable status index over it.

### 2. Storage layout

```
pipeline.yaml                                # topology (see §3)

runs/2026-07-25-why-kids-quit-travel-sports-20260725-143200/
  00-grounding/                               # only present for RaisingGoodSports-brand projects
    pointer.yaml                              # {rgs_brief_path: "rgs-briefs/2026-07-25-....md"}
  01-ideation/
    input.txt                                 # raw idea text (no upstream artifact — stage 1 only)
    artifact.v1.md                            # concept brief; frontmatter below
    events/<turn_id>.jsonl                    # one per chat turn in this stage
  02-scripting/
    artifact.v1.md
    events/<turn_id>.jsonl
  03-voiceover/                               # parallel with 03-visual — same numeric prefix,
    artifact.v1.md                            # per the eval-and-io-boundaries spec's fan-out note
    events/<turn_id>.jsonl
  03-visual/
    artifact.v1.md
    events/<turn_id>.jsonl
  04-assembly/
    artifact.v1.md
    events/<turn_id>.jsonl
  05-repurpose/
    artifact.v1.md
    events/<turn_id>.jsonl
```

**Artifact frontmatter** (subset of the eval-and-io-boundaries schema — this app only writes the
fields it actually uses; it does not invent `marker_counts`/`source_corpus_docs`/`t_verified`,
which are specific to that spec's eval-suite enforcement):

```yaml
---
schema_version: 1
run_id: why-kids-quit-travel-sports-20260725-143200
stage: shorts-scripting
version: 2
status: final                 # draft while awaiting approval, final once approved
created_at: 2026-07-25T14:47:00Z
finalized_at: 2026-07-25T15:02:00Z
supersedes: artifact.v1.md    # set only on the new file; v1 is never mutated again
depends_on:
  - path: ../01-ideation/artifact.v1.md
    sha256: 3f9a...
---
```

- **Versioning: always a new file, never an in-place edit.** Regenerating a stage (another chat
  turn asking for a revision) or hand-editing the output both produce `artifact.v{N+1}.md` with
  `supersedes` pointing at the prior version. This gives free undo/history with no separate git
  layer needed for `runs/` (which stays gitignored, same precedent as `output/`).
- **"Approve" = stamping, done by the app directly** (no external finalize script, since there's
  no hook/ACL enforcement to coordinate with): set `status: final` + `finalized_at` on the current
  version, flip the stage's SQLite row to `approved`.
- **Staleness detection** falls out of `depends_on`: if stage N is approved and stage N-1 gets a
  new version afterward, stage N's recorded `depends_on` hash no longer matches — the app flags
  stage N `stale` in the UI. Nothing is deleted; the user reviews and re-approves.
- **Grounding stage (RGS only):** the real artifact is written to `rgs-briefs/YYYY-MM-DD-<slug>.md`
  (unchanged existing convention — that file is what `rgs-grounding` itself globs across *all*
  projects for its recency/variety dedup). `00-grounding/pointer.yaml` holds only a reference,
  never a duplicate. Regenerating grounding offers to delete the superseded `rgs-briefs/` file
  (matching that ledger's own "delete if abandoned" convention) so it doesn't pollute future dedup.

### 3. `pipeline.yaml` — topology

```yaml
stages:
  - id: grounding
    skill: rgs-grounding
    dir_prefix: "00"
    depends_on: []
    brand_scope: raisinggoodsports   # only this brand shows this stage at all
  - id: ideation
    skill: shorts-ideation
    dir_prefix: "01"
    depends_on: []
  - id: scripting
    skill: shorts-scripting
    dir_prefix: "02"
    depends_on: [ideation]
  - id: voiceover
    skill: voiceover-brief
    dir_prefix: "03"
    depends_on: [scripting]
  - id: visual
    skill: visual-prompts
    dir_prefix: "03"
    depends_on: [scripting]
  - id: assembly
    skill: shorts-assembly
    dir_prefix: "04"
    depends_on: [voiceover, visual]
  - id: repurpose
    skill: social-repurpose
    dir_prefix: "05"
    depends_on: [assembly]
```

`voiceover` and `visual` share `depends_on: [scripting]` and no dependency on each other — the
app's gating engine reads this as a genuine parallel pair: both unlock together once `scripting`
is approved, and `assembly` unlocks only once **both** are approved.

### 4. Stage state machine

Per stage, per project (SQLite `stages` table):

```
locked → ready → running → awaiting-review → approved
                                                  │
                            (upstream regenerated)▼
                                               stale → running → awaiting-review → approved
```

- `locked`: an entry in `depends_on` (per `pipeline.yaml`) isn't approved yet.
- `ready`: unlocked, no turn started yet.
- `running`: an active Claude CLI turn in progress. **Global single-flight lock across the whole
  app** — only one turn runs at a time, anywhere, since one user only watches one stream. The
  composer is disabled while running; Cancel kills the process tree (not just the shim process —
  Windows requires the tree kill).
- `awaiting-review`: latest artifact version written, not yet approved.
- `approved`: gates dependent stage(s) open.
- `stale`: was approved, but an upstream dependency changed afterward (new version, hash
  mismatch). Output and approval history are kept; re-approve once reviewed.

Startup reconciliation: any `turns` row still `running` after an app restart (crash recovery) is
marked `orphaned`, never left as a phantom in-progress state.

### 5. Claude CLI integration contract

- **Binary resolution:** `shutil.which("claude")`. On Windows this resolves to an npm `.cmd`
  shim, which `asyncio.create_subprocess_exec` cannot exec directly — the app invokes it through
  the shim path with the appropriate Windows-specific handling, isolated to one code path so the
  rest of the app is platform-agnostic.
- **`cwd`** is always the ContentStudio repo root — required for `.claude/skills/` discovery and
  for stable session-directory hashing (an inconsistent cwd silently breaks `--resume`).
- **Permissions:** `--allowedTools "Read,Glob,Grep,Write,Edit"` — **no Bash**. Permission rules
  (via `--settings`) scope Write/Edit to `runs/**` and `rgs-briefs/**` only. A pipeline-stage turn
  can never touch `docs/`, `output/`, or `.claude/skills/` itself — skill-content edits only ever
  happen through the dedicated skill editor (§7), never through a stage run.
- **Output:** `--output-format stream-json --include-partial-messages`, forced UTF-8 I/O
  (`PYTHONIOENCODING=utf-8`) so Windows codepage defaults don't mangle the JSON stream.
- **Skill invocation is explicit**, not description-matched: each stage's kickoff prompt begins
  with `/skill-name`, so the correct skill triggers deterministically every time.
- **Session bookkeeping:** each turn's `system/init` event carries a *new* `session_id` — the app
  persists that as the *next* `--resume` target for the stage (never the original id). If
  `--resume` fails (session pruned — Claude Code prunes old sessions after ~30 days), the app
  starts a fresh session whose kickoff re-injects the stage's current input/output file paths, and
  the UI marks that the chat history reset.
- **Per-stage sessions:** each stage gets its own Claude session line, independent of its
  siblings — this is what makes the `voiceover`/`visual` parallel pair conflict-free (two
  independent sessions, no shared-session contention).
- **Post-turn artifact verification:** after a turn completes, the app checks the expected
  `artifact.v{N}.md` path exists and was actually written during the turn. If not, the stage
  surfaces an explicit "no artifact produced" state with a retry action (or "save the chat's last
  message as the artifact," for skills whose output is chat-only).
- **Preflight:** on startup, the app runs `claude --version` and a trivial `-p` call, surfacing
  "not logged in" / "binary not found" as an explicit diagnostic (§8) instead of failing silently
  mid-pipeline.
- **Grounding pass-through:** every downstream generic stage's kickoff template includes a
  conditional block — *"if this project has an approved grounding artifact, reference it at
  `{grounding_pointer}`"* — matching those skills' own existing "optional companion grounding
  artifact" input convention. Generic-brand projects never populate that block.

### 6. UI / navigation

- **Persistent sidebar:** current project's full pipeline, including the branching pair rendered
  side by side, with a status badge per stage (six distinct states from §4).
- **Header breadcrumb:** `Project name › Stage name`. Prev/Next links respect gating (Next is
  disabled with a tooltip if the current stage isn't approved).
- **Project home:** the same pipeline as a clickable diagram.
- **Top-level "Projects"** list (create — choosing brand at creation time, per §3's
  `brand_scope` — and switch between projects).
- **Top-level "Tools"** section: `rgs-pairing-review` as a standalone, ungated, on-demand action
  (it's corpus-maintenance, not a per-Short pipeline stage), plus the Doctor page (§8).
- **Stage page layout:** Input panel (upstream artifact, rendered, or raw idea text for stage 1;
  for an RGS project, any stage with a populated grounding-pass-through block in §5 also shows the
  grounding artifact as a second input source, linked to its `rgs-briefs/` file) → Chat panel
  (full transcript; SSE-tails only the *currently live* turn — on page load the server renders the
  complete transcript from `events/*.jsonl` directly into HTML, no resumable Last-Event-ID
  complexity needed) → Output panel (rendered markdown + raw/edit toggle, "Regenerate" and "Mark
  Approved" actions).

### 7. Skill editor

One page per skill (8 total: 6 generic + `rgs-grounding` + `rgs-pairing-review`), tabs for
`SKILL.md` / each `references/*.md` file / this stage's kickoff template in `stage_templates/`.

- Edits to `SKILL.md`/`references/` write directly to the real `.claude/skills/<name>/` files —
  single source of truth, same files a normal Claude Code session reads — and **auto-commit** to
  git with a stamped message (e.g. `skill edit: shorts-ideation via pipeline-app, 2026-07-25`),
  giving free undo history.
- Edits to a stage's kickoff template write to `pipeline-app/stage_templates/<stage>.md` (a new,
  app-owned file, not part of `.claude/skills/`).

### 8. MD inspector & Doctor page

- **MD inspector** (standalone tool, not gated to any project): point it at any `.md` file on
  disk; it parses YAML frontmatter (rendered as a table) and the body (rendered), and if the path
  matches a recognized `runs/` artifact convention, cross-references which stage produced it and
  what consumed it.
- **Doctor page:** `claude` binary path + version, auth/login status, ContentStudio repo root,
  skills discovered under `.claude/skills/`, DB path, any `orphaned` turns, and a basic
  filesystem-layout check. Given most failure modes here are environmental (shim resolution,
  login expiry, pruned sessions), this is the cheapest available support tool.

### 9. Error handling

Every failure mode is an explicit UI state, never a generic 500: CLI not found / not logged in
(preflight), rate-limit or usage-cap hit mid-turn, no-artifact-produced, orphaned turn after a
crash, session-resume failure. No silent retries — the user always sees what happened and what to
do next.

### 10. Testing

- Unit tests (pytest) for the stage state machine (transitions, staleness propagation from
  `depends_on` hash mismatches) and the MD/frontmatter parser, against real fixture files.
- A small set of integration tests that run the actual `claude` CLI against a throwaway scratch
  project, verifying the subprocess/SSE/artifact-verification plumbing end to end. These cost
  real usage against the subscription, so they're skipped in CI / when not logged in, and run
  deliberately rather than on every change.

## Out of scope for this spec

- The eval-and-io-boundaries spec's finalize script, `PreToolUse` hook, Windows ACL locking, and
  eval suite (§ Non-goals) — a separate, already-approved, still-unimplemented spec this app does
  not build or depend on beyond sharing the `runs/` layout and `pipeline.yaml` conventions.
- Any change to the six generic skills' or two RGS skills' actual corpus-grounded content.
- Any FamilyBrain integration of any kind — out of scope permanently per ContentStudio's
  `CLAUDE.md` FamilyBrain firewall.
- Deployment, hosting, multi-user access, or anything beyond `127.0.0.1`.
