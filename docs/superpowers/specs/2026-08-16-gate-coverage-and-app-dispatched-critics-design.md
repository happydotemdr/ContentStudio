# Gate coverage and app-dispatched critics — design

**Date:** 2026-08-16
**Status:** approved (design); implementation plan not yet written
**Scope:** first of four sub-projects from a broader pipeline-architecture evaluation (orchestration
framework, corpus retrieval, gauntlet-loop expansion). This sub-project is the foundation the other
three sit on: auto-advance (sub-project 2), the ElevenLabs one-shot spend lock (sub-project 3), and
the Midjourney render console (sub-project 4, already has its own 2026-08-06 design spec) are all
independent of this one or explicitly blocked on it landing first.

**Revision note:** this design went through one adversarial pass (a fresh Opus review with no
visibility into the author's rationale, dispatched deliberately to mirror the exact pattern the
codebase's own Gate E/B use). That review found five structural defects in the first draft — all
folded into this document, not left as a separate errata. See §7.

---

## 1. Problem

Two of this repo's nine pipeline stages (`scripting`, `visual`) have real deterministic gates
(Gate D, Gate C) plus an adversarial critic pass (Gate E, Gate B). The other seven have nothing:
`styleboard` has a deterministic gate only (Gate S); `grounding`, `ideation`, `voiceover`, `music`,
`assembly`, `repurpose` have none at all. An operator approving any of those seven is trusting the
skill's own self-report with no independent check.

Worse, the two critic gates that do exist are **self-attested**: Gate E and Gate B are dispatched by
the skill itself, mid-turn, via the Task tool — the skill writes its own "Gate E: pass" line into the
artifact it is being judged on. `read-aloud-gates.md`'s own "Known limits" section says this
outright: *"D6 cannot prove Gate E ran... writing a false pass is now the cheapest way past the
lock, and it is still available."* Nothing external verifies the critic ran at all.

This sub-project closes both gaps: gate coverage for the stages that have none, and a real,
app-dispatched critic that a skill cannot fake.

## 2. Constraints from the audit-remediation programme

This repo is mid-way through a 328-finding, 16-package remediation programme (`docs/superpowers/
plans/remediation/P0.md`–`P15.md`), where each unexecuted package claims file-exclusive ownership.
Two facts about that programme directly shape this design, verified against the actual plan
documents rather than assumed:

- **P5 is in flight with another agent right now.** This design touches none of its files
  (`routes/skills.py`, `git_helper.py`, `routes/projects.py`, `project_service.py`,
  `routes/inspector.py`, and their tests) — confirmed by cross-referencing every file this design
  edits against P5's owned-files list.
- **P13 (unexecuted) owns all 13 skills' `SKILL.md` + `references/` directories**, including the two
  files this design must edit: `shorts-scripting/references/read-aloud-gates.md` and
  `midjourney-prompting/references/validation-gates.md`. Checked P13's actual planned tasks against
  both files: P13 touches `read-aloud-gates.md:102-103` (an unrelated citation-wording fix) and adds
  one item to `validation-gates.md`'s Gate A checklist (unrelated to Gate B's dispatch mechanism).
  **P13 does not plan to touch the self-dispatch instructions this design removes.** This design
  therefore makes that one narrow edit directly, staying clear of P13's two target spots, rather than
  writing it up as a deferred handoff.
- **P15 (unexecuted) is a non-issue for this design.** It owns all of `pipeline_app/templates/**` and
  is planned to rebuild `gate_strip.html` — but `gate_view` (the data contract P15 renders) already
  exists and is already rendered today, merged via P3 (`routes/stages.py:306`,
  `templates/stage.html:50-76`). Every gate this design adds — lint or critic — appears in that
  existing block immediately, correctly labeled, with zero changes to any template. P15's later work
  is a pure presentation upgrade on the same data shape; it neither blocks this design nor is blocked
  by it.
- **P6–P9 (discovery, Bright Data, cron, digest email) and P14 (docs truth) have no relevant overlap** —
  confirmed by grep across all four for gate/critic/gauntlet content; nothing found beyond incidental
  word matches (`severity="critical"`, an unrelated "gate" used as a routing metaphor in P8/P9).

## 3. Scope

**In scope — lint gates**, five of the six originally-considered ungated stages:

| Stage | Registry name | What it checks |
|---|---|---|
| `ideation` | `gate_o_ideation_contract` | Required headings present (Angle/take, Hook concept, Packaging direction, Validation, Handoff); `Grounding` section is genuinely conditional per the skill's own instruction and its absence is not a failure |
| `voiceover` | `gate_o_voiceover_contract` | Required headings present: Voice pick, Settings, Script reformatted for TTS, Production & loudness, Downstream — all mandatory |
| `music` | `gate_o_music_contract` | Required headings present: Bed arc, Hook hold-out, Tone-contradiction check, Deferred to elevenlabs-music |
| `assembly` | `gate_o_assembly_nonempty` | No fixed output template exists in the skill to check headings against (verified: `shorts-assembly/SKILL.md` has no `## Output format` block). Deliberately minimal: non-empty body, no unfilled `<…>`/`[…]` slots |
| `repurpose` | `gate_o_repurpose_nonempty` | Same reduced tier — the skill's contract is numbered prose over user-chosen platforms, not a fixed heading set |

Each is its own small function registered normally in `gates.GATE_REGISTRY` — deliberately **not**
one generic table. A first draft of this design proposed a single generic "required sections +
placeholder scan" gate; the review caught two defects in it: (a) a document-wide `[…]` scan would
false-positive on every `[C]`/`[I]`/`[T]` corpus-provenance marker, which every artifact in this
pipeline is required to carry per `CLAUDE.md`'s anti-generic guarantee, and (b) the six stages'
output contracts are not structurally uniform — `assembly` and `repurpose` have no fixed heading
template at all. Five small, individually-correct gates beat one fragile generic one.

**Explicitly out of scope — `grounding`.** Verified: `grounding` runs with `finalize_artifact=False`
(`routes/stages.py:443`), so `run_gates_for_stage` never executes for it at all; its real artifact
lives in `rgs-briefs/` behind a pointer, and the hand-edit route explicitly refuses grounding
(`routes/stages.py:515`). There is no path today that writes a gate result anywhere
`approval_service.approve_stage` would read it. Registering a gate for `grounding` in this design
would make every grounding approval, forever, require a typed override — this needs its own later
design once someone decides how (or whether) gates attach to a pointer-indirected artifact outside
`run_dir`. Not silently forced into this sub-project.

**In scope — critic promotion and one new critic gate:**

- `scripting` — Gate E promoted from skill-self-dispatched to app-dispatched.
- `visual` — Gate B promoted, and **its unit of judgment changes**: today it fires per production
  Midjourney prompt (`validation-gates.md:102`); the promoted version judges the whole prompt sheet
  once per artifact, matching every other stage gate's shape. Per-shot judgment was considered and
  rejected — it would cost roughly N× critic tokens per visual-stage turn (N = shot count, commonly
  12–20), which the operator's explicit cost-sensitivity ruled out.
- `ideation` — new critic gate. Chosen over `grounding`/`repurpose` (also considered) because a weak
  concept brief wastes every downstream stage's spend; a weak caption doesn't.

**Explicitly out of scope for this sub-project:**

- Auto-advance policy (sub-project 2) — depends on this landing first; auto-approving on top of gates
  that don't yet exist would be unsafe.
- ElevenLabs one-shot lock + spend ledger (sub-project 3) — independent, own design.
- Midjourney render console (sub-project 4) — independent, already has a 2026-08-06 design spec.
- Bounded auto-retry loop. Considered and rejected: a critic failure blocks approval and the operator
  resolves it (regenerate, defend in writing, or override) — the same three-path resolution Gate E
  already uses today, just app-enforced instead of self-attested. An automatic multi-round
  regenerate-and-recheck loop would cost 2–4× the skill+critic tokens per gated stage whenever a
  retry fires, with no evidence yet that single-pass quality is insufficient.
- P15's `gate_strip.html` rebuild — confirmed compatible and unnecessary for this design to touch.

## 4. Architecture

### 4.1 Lint gates

No change to the existing pattern: each of the five is a `GateRunner`
(`Callable[[repo_root, artifact_path, upstream], list[dict]]`) registered in
`gates.GATE_REGISTRY`, following Gate C/D/S's existing shape exactly. `run_gates_for_stage`'s
signature and fail-closed wrapper are untouched.

### 4.2 Critic dispatch — a separate step, not a `GateRunner`

The first draft of this design proposed registering critic gates in `GATE_REGISTRY` directly. The
review caught this as mechanically broken: `GateRunner` is synchronous, and `run_gates_for_stage` is
called synchronously from **two** places — the async `turn_service.run_stage_turn` **and** the
plain-`def` (not `async def`) `routes.stages.edit_stage_output_route`
(`routes/stages.py:512`, calling `run_gates_for_stage` at `:541`). A critic dispatch must `await` an
async subprocess turn; making `run_gates_for_stage` async to accommodate that breaks the sync hand-edit
route outright.

Instead: a new module, `pipeline_app/critic_service.py`:

```python
async def dispatch_critic(
    repo_root: Path, stage_id: str, artifact_text: str, rubric_prompt: str,
    timeout_seconds: float,
) -> list[dict]:
    """Spawns a fresh, non-resumed claude -p turn scoped to Read/Glob/Grep only,
    with an explicit timeout, and parses its required verdict block into the
    same finding shape gates.py's linters already produce:
    {check, beat, shot_index, kind, message}."""
```

Called from `turn_service.run_stage_turn` as its own explicit step, **after** the existing synchronous
`gates.run_gates_for_stage` call and **before** the artifact is finalized. Its result list is appended
onto the same `gates:` list that gets written into frontmatter — rendered identically by the existing
`gate_view`/`gate_strip` block, indistinguishable to `classify_gates` from a deterministic gate's
result. `GateRunner`'s contract and `run_gates_for_stage`'s signature never change; `edit_stage_output_route`
is untouched.

`timeout_seconds` defaults to 300 (5 minutes) — a critic turn only reads and judges, it never drafts,
so it should complete well inside the budget an authoring turn needs; 300s is a starting point to
tune against real measured critic-turn duration once this ships, not a value derived from evidence
that doesn't exist yet. The three rubric prompts (`scripting`, `visual`, `ideation`) live in a new,
app-owned location — e.g. `pipeline-app/critic_rubrics/*.md` — authored fresh for app dispatch, not
copied from or pointing back into the P13-owned skill `references/` files. That keeps the rubric
content itself outside P13's exclusive territory the same way the dispatch mechanism is.

**What the critic needs that `artifact_text` alone doesn't carry.** The review's F7 finding is only
half-resolved by the Gate B unit-of-judgment change (§3) — Gate E has a second gap. Today, the
skill's self-dispatched critic receives a **per-line no-touch annotation** (`verbatim-quote`,
`citation`, `uncuttable`, `lexicon-screened`, `free`, `unknown`) that the skill itself produces,
because it is the one that wrote the constraints — see `read-aloud-gates.md`'s "no-touch zones."
An app-dispatched critic reading only the final artifact text cannot reconstruct that classification;
without it, the `unknown → no-touch` fail-safe is lost and a promoted Gate E could propose rewrites
that strip a citation or a verbatim quote. **Resolution:** the no-touch annotation becomes part of the
script's own output contract — the skill writes it inline (one annotation per VO line, in the artifact
body) instead of handing it over as a separate, ephemeral Task-tool dispatch payload. This is a natural
consequence of promotion, not an optional add-on: it is the mechanism by which the annotation channel
survives the move from "skill hands data to its own sub-agent" to "app reads a finished artifact." The
exact inline syntax is implementation-plan detail; the requirement — the annotation must be
recoverable from the artifact text alone — is not.

**Failure handling, added because none of it exists today:**

- **Explicit timeout.** `cli_runner.py` has no timeout anywhere today (the only `timeout=` in the
  file is `taskkill`'s cleanup call, `cli_runner.py:230`) — a hung critic subprocess would block the
  turn indefinitely. `dispatch_critic` takes an explicit `timeout_seconds` and kills the subprocess if
  exceeded.
- **Disconnect/abort safety.** A client disconnect during the critic's subprocess (a real risk — LLM
  turns take real wall-clock time, and this design adds a second one to the same request) must not
  wedge the stage at `RUNNING` forever. Today's fail-closed gate wrapper (`gates.py:28`, `:423`)
  deliberately re-raises `GeneratorExit` rather than swallowing it — correct for a linter, but if a
  critic dispatch used that same wrapper unmodified, a disconnect during the critic would propagate
  past `run_stage_turn`'s own `except BaseException` recovery (which already runs for the skill's own
  turn, restoring `prior_status` — `turn_service.py:425`) in exactly the same way. The critic step
  gets its **own** `except BaseException`, mirroring that same prior-status-restore pattern, invoked
  explicitly around the critic call rather than assumed to inherit it.
- **Errored vs. failed, distinguished.** A critic that times out, returns a malformed verdict block,
  or is refused is recorded as `status: "error"` — the same bucket a crashing linter already uses,
  and already renders distinctly in the UI (`status-errored`, amber-dashed in the never-ran/unknown
  states, red for failed/errored per `P15-ui.md`'s existing CSS). Distinct from `status: "fail"`,
  which means the critic ran successfully and found a real defect. Both block approval; the operator
  can tell which happened from the gate strip.
- **Cost visibility.** `turns.cost_usd` today is written only from the skill turn's own `result` event
  (`turn_service.py:435-439`); a critic subprocess would otherwise be invisible spend. `dispatch_critic`
  creates its own `turns` row so critic cost shows in the same ledger the operator already checks.

### 4.3 Closing self-dispatch structurally

Two changes land together, not sequentially:

1. **Skill-side.** `read-aloud-gates.md` and `validation-gates.md`'s self-dispatch instructions are
   updated to say the app handles this now — mirroring the exact precedent Gate D already set
   ("in app-driven mode record `deferred — app-run`, because the app runs it"). Edits stay narrowly
   scoped to the dispatch-instruction passages, explicitly avoiding `read-aloud-gates.md:102-103` and
   the `validation-gates.md` Gate A checklist item, both of which are P13's own planned targets.
2. **App-side.** `Task` is removed from `cli_runner.PIPELINE_ALLOWED_TOOLS`. Denying the tool makes
   self-dispatch structurally impossible rather than merely discouraged by an instruction a skill
   could ignore, or that a future skill edit could silently reintroduce. Doing both together in one
   change avoids the interim state where markdown says one thing and the mechanism still allows the
   old behavior.

## 5. Data flow, end to end

For a stage with both a lint gate and a critic gate (`scripting`, `visual`, `ideation`):

1. Skill's own turn completes; `raw_output.md` is written (unchanged).
2. `gates.run_gates_for_stage` runs the stage's registered deterministic `GateRunner`(s), synchronously,
   as today.
3. If the stage has a registered critic subject, `turn_service.run_stage_turn` calls
   `critic_service.dispatch_critic` — a fresh, non-resumed, tool-restricted, timeout-bounded turn —
   and appends its findings onto the same list.
4. Combined `gates:` list is written into the artifact's frontmatter, exactly as today.
5. `classify_gates` / `approve_stage` / the existing `gate_view` block see one unified list; no
   awareness that some entries came from a regex and one from an LLM turn.

## 6. Testing approach

Follows the remediation programme's own standard (`docs/superpowers/plans/2026-08-08-audit-
remediation.md`'s Three-Test Rule), since this design extends code that standard already governs:

- Each new lint gate: a fault test (malformed/missing section → blocking finding), a distinguishability
  test (genuinely-empty-but-valid vs. broken are not conflated), and a surfacing test (the finding
  reaches `gate_view`).
- `critic_service.dispatch_critic`: a timeout test (subprocess exceeds `timeout_seconds` → `error`
  status, process killed, stage not wedged), a disconnect test (client disconnect mid-critic → stage
  restored to `prior_status`, not left at `RUNNING`), a malformed-verdict test (`error`, not a silent
  pass), and a real-pass/real-fail pair using a stubbed CLI (matching the existing
  `tests/integration/test_stubbed_cli_e2e.py` pattern).
- Skill-markdown edits: covered by whatever conformance check P13 eventually adds
  (`tests/test_skill_provenance.py`) — not duplicated here, since this design's edits are narrowly
  scoped and P13 owns that file.

## 7. What the adversarial review changed

A fresh Opus review (dispatched with the actual proposal text and told to verify every claim against
the live code, not the proposal's framing) found and this document incorporates:

- **Grounding cannot carry a gate result** (§3) — the first draft included it; dropped.
- **The async/sync contract collision** (§4.2) — the first draft proposed registering the critic in
  `GATE_REGISTRY` directly; redesigned as a separate step specifically to avoid breaking the sync
  hand-edit route.
- **Disconnect handling was unspecified** (§4.2) — added explicitly.
- **The generic lint-gate table was wrong for 4 of 6 stages** (§3) — replaced with five individually-
  scoped gates after reading each stage's actual output contract.
- **Gate B's unit of judgment would silently change** (§3) — surfaced as an explicit decision rather
  than an accidental scope change.
- **Critic spend was invisible** (§4.2) — added its own turn-row/cost accounting.
- **The self-attestation double-signal** (§4.3) — escalated from "defer to P13" to "close it now," once
  it was clear P13 doesn't currently plan to touch these specific lines.
