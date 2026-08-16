# Gate coverage for ungated pipeline stages — design

**Date:** 2026-08-16
**Status:** approved (design); implemented and merged — see
`docs/superpowers/plans/2026-08-16-gate-coverage.md` (executed via
`superpowers:subagent-driven-development`, [PR #40](https://github.com/happydotemdr/ContentStudio/pull/40)).
Critic promotion (§7) remains a future, unplanned design.
**Scope:** first of four sub-projects from a broader pipeline-architecture evaluation. Originally
scoped to include app-dispatched critic promotion (Gate E/B) as well — **split out** after a second
adversarial review found structural problems specific to that half (§7). This document now covers
deterministic gate coverage only. Critic promotion becomes its own later design, informed by what
this document's §7 preserves from both review passes.

---

## 1. Problem

Two of this repo's nine pipeline stages (`scripting`, `visual`) have real deterministic gates
(Gate D, Gate C); a third (`styleboard`) has one (Gate S). The other five — `ideation`, `voiceover`,
`music`, `assembly`, `repurpose` — have none at all. An operator approving any of them is trusting the
skill's own self-report with no independent check. (A sixth ungated stage, `grounding`, is
structurally different — see §3 — and is out of scope here entirely, not just deferred.)

Separately, `scripting` and `visual` also carry an adversarial "critic" pass (Gate E, Gate B) that is
**self-attested**: the skill dispatches its own critic mid-turn via the Task tool and writes its own
pass/fail line into the artifact it's being judged on. `read-aloud-gates.md`'s own "Known limits"
section says outright: *"D6 cannot prove Gate E ran... writing a false pass is now the cheapest way
past the lock."* Closing that gap is real work, but it turned out to be a meaningfully harder problem
than the deterministic-gate-coverage problem — see §7 for why it was split out rather than solved
here.

## 2. Constraints from the audit-remediation programme

This repo is mid-way through a 328-finding, 16-package remediation programme
(`docs/superpowers/plans/remediation/P0.md`–`P15.md`), where each unexecuted package claims
file-exclusive ownership. Two facts, verified against the actual plan documents:

- **P5 is in flight with another agent right now.** This design touches none of its files
  (`routes/skills.py`, `git_helper.py`, `routes/projects.py`, `project_service.py`,
  `routes/inspector.py`, and their tests) — confirmed against P5's owned-files list
  (`P5-skills-editor.md:16-27`).
- **P15 (unexecuted) is a non-issue for the gate-coverage half of this work.** It owns all of
  `pipeline_app/templates/**` and plans to rebuild `gate_strip.html` — but `gate_view` (the data
  contract P15 renders) already exists and is already rendered today, merged via P3
  (`routes/stages.py:306`, `templates/stage.html:50-69`). Every lint gate this design adds appears in
  that existing block immediately, correctly labeled as blocking/not-blocking, with zero changes to
  any template. (P15's fuller `passed`/`failed`/`errored`/`never_ran`/`unknown` state styling —
  `status-errored` etc. — does not exist in the template yet; today's block only distinguishes
  blocking vs. not. That distinction mattered for critic promotion's errored-vs-failed requirement,
  which is one reason that piece is split out. It does not matter for a deterministic lint gate, which
  only ever produces `pass`/`fail`, both already rendered correctly today.)
- **P6–P9 (discovery, Bright Data, cron, digest email) and P14 (docs truth) have no relevant
  overlap** — confirmed by grep across all four for gate-related content; nothing found beyond
  incidental word matches.
- **P13's relevance to this narrowed scope is minimal.** P13 owns all 13 skills' `SKILL.md` +
  `references/` directories, but this document no longer proposes editing any skill markdown — that
  was specific to the critic-promotion half (removing the Task-tool self-dispatch instructions),
  which is now out of scope here.

## 3. Scope

Five lint gates, individually shaped per stage — verified against each stage's actual current
`SKILL.md` output-contract prose, not assumed uniform:

| Stage | Registry name | What it checks |
|---|---|---|
| `ideation` | `gate_o_ideation_contract` | Required headings present: Angle/take, Hook concept, Packaging direction, Validation, Handoff (`shorts-ideation/SKILL.md:146-175`). `Grounding` is genuinely conditional per the skill's own instruction — its absence is not a failure |
| `voiceover` | `gate_o_voiceover_contract` | Required headings present: Voice pick, Settings, **`Script, reformatted for TTS`** (comma included — the literal heading text, `voiceover-brief/SKILL.md:96`), Production & loudness, Downstream |
| `music` | `gate_o_music_contract` | Required headings present: Bed arc, Hook hold-out, Tone-contradiction check, Deferred to elevenlabs-music, **and Downstream** (`music-brief/SKILL.md:80` — omitted from an earlier draft of this table; five headings, not four) |
| `assembly` | `gate_o_assembly_contract` | No `##`-heading template exists to check presence against, but the skill's "Writing the plan for a real request" section (`shorts-assembly/SKILL.md:72-83`) mandates specific checkable content: an aspect-ratio statement (1080×1920 / 9:16), a stated loudness target (−14 LUFS) and ducking level, both a $0 and a paid tool-stack path, the QA-gate + publish-gate checklist, and the closing hand-off statement to `social-repurpose`. The gate checks for these by keyword/phrase presence, not heading structure |
| `repurpose` | `gate_o_repurpose_contract` | No fixed heading set, but `social-repurpose/SKILL.md:98-101` fixes a real package structure: the YouTube block appears first, followed by one block per requested platform, and every caption carries a provenance marker (`[C]`/`[I]`/`[T]`/`[C→I]`/`[gap]`). The gate checks block ordering and marker presence, not headings |

Each is its own small function registered normally in `gates.GATE_REGISTRY`, following Gate C/D/S's
existing `GateRunner` shape exactly (`Callable[[repo_root, artifact_path, upstream], list[dict]]`).
No shared generic table — an earlier draft tried one generic "required sections + placeholder scan"
gate and it was wrong for four of the five stages (assembly and repurpose have no heading template at
all; a document-wide `[…]` scan would also false-positive on every mandatory `[C]`/`[I]`/`[T]`
citation marker every artifact in this pipeline is required to carry). Five small, stage-correct gates
instead.

**Explicitly out of scope — `grounding`.** Verified: `grounding` runs with `finalize_artifact=False`
(`routes/stages.py:443`, the flag is set at `:446`), so `run_gates_for_stage` never executes for it;
its real artifact lives in `rgs-briefs/` behind a pointer, and the hand-edit route explicitly refuses
grounding (`routes/stages.py:515`). There is no path today that writes a gate result anywhere
`approval_service.approve_stage` would read it. Registering a gate for `grounding` would make every
grounding approval, forever, require a typed override. This needs its own later design once someone
decides how (or whether) gates attach to a pointer-indirected artifact outside `run_dir`.

**A retroactive-blocking consequence to handle explicitly, not silently.** Registering these five gates
means every existing artifact for these stages — approved before this change shipped — instantly
becomes `never_ran`/blocking under `classify_gates`, the same consequence `gates.py:369-377`'s own
comment documents for `styleboard`'s registration. The implementation plan for this design must name
a migration or backfill approach (mirroring whatever P2's `migrations.backfill_styleboard_rows` did for
styleboard), not silently ship a registry change that blocks every existing project.

## 4. Architecture

No new mechanism. Each gate is a plain `GateRunner`, registered in `gates.GATE_REGISTRY`, following
the identical pattern Gate C/D/S already use. `run_gates_for_stage`'s signature, its fail-closed
wrapper, and both call sites (`turn_service.run_stage_turn`, the sync
`routes.stages.edit_stage_output_route`) are completely untouched — this is the one property that
made the deterministic half of the original design survive two adversarial passes unchanged while the
critic half did not.

## 5. Testing approach

Follows the remediation programme's own Three-Test Rule
(`docs/superpowers/plans/2026-08-08-audit-remediation.md`): for each of the five gates, a fault test
(malformed/missing required content → blocking finding), a distinguishability test (genuinely-thin-
but-valid content is not conflated with genuinely broken content), and a surfacing test (the finding
reaches `gate_view` and renders in the existing `stage.html` block). Plus one migration/backfill test
per §3's retroactive-blocking note, confirming pre-existing approved artifacts for these five stages
are not silently blocked by the new registry entries.

## 6. What two adversarial reviews changed

This design went through two independent fresh-Opus reviews (each with no visibility into the
author's rationale, each told to verify claims against the live code rather than trust the document's
framing) — mirroring the same pattern the codebase's own Gate E/B use.

**First pass**, against the original combined (lint + critic) proposal, found and fixed: grounding
cannot carry a gate result; a synchronous/asynchronous contract collision between `run_gates_for_stage`
and the sync hand-edit route; unspecified disconnect handling; one generic lint-gate table that was
wrong for four of six stages; Gate B's unit-of-judgment silently changing; critic spend being
invisible to the cost ledger; the self-attestation double-signal.

**Second pass**, against the resulting document, found the first pass's fixes for the critic half were
themselves incomplete, and found the lint-gate half's stage-contract claims still had three factual
errors (now corrected in §3's table):

- **The critic-dispatch redesign (keeping critics out of `GATE_REGISTRY` to dodge the async
  collision) created a worse hole than the one it closed.** The hand-edit route
  (`routes/stages.py:579`) builds `gates:` from `run_gates_for_stage` alone; because a critic
  wouldn't be in the registry, `classify_gates` could never flag a missing critic result as
  `never_ran` on a hand-edited artifact — a bypass strictly worse than today's self-attestation
  problem.
- **The claimed disconnect-safety pattern doesn't exist at the insertion point.** `turn_service.py`'s
  artifact-finalization block (`:462-506`) contains zero `await`s today — reservation, the sync gate
  call, and the write are one atomic sequence, which is exactly why disconnect risk there is currently
  nil. Its only `except BaseException` (`:501-503`) releases the version reservation and re-raises,
  with no stage-status restore at all. Inserting a real, multi-minute-capable critic `await` there,
  as designed, would wedge a stage at `RUNNING` permanently on any disconnect — and since
  `any_turn_running()` is a single global lock, that blocks every stage in the entire app until manual
  database repair.
- **Gate B promotion was asserted cost-neutral and isn't.** Gate B fires only at the `production`
  stage today (`validation-gates.md:102`), and `visual-prompts` defaults to `draft`
  (`visual-prompts/SKILL.md:160`) — so Gate B costs zero on most turns today. Promoting it to run
  once per artifact, always, is new spend.
- **Removing `Task` from the allowed-tools list would break an existing test**
  (`test_cli_runner.py:577` asserts `"Task" in default`), unmentioned in the prior testing section.
- Three lint-gate contract errors, now corrected in §3: voiceover's heading text (a comma was
  dropped), music's fifth section (`Downstream`, previously omitted), and assembly/repurpose's real
  checkable structure (previously undersold as "no template, minimal non-empty check" when both
  actually have specific checkable content requirements).

**Decision: split, not re-patch a third time.** The reviewer's recommended fix for the critic-dispatch
problem — make critic results genuinely first-class to `classify_gates` (a registry of expected
critic subjects, with explicit carry-forward or forced re-run on hand-edit) rather than a side-channel
— is real, substantive design work, not a wording correction. The five lint gates, by contrast, held
their architecture unchanged across both passes; only their per-stage content specifics needed
correcting. Bundling a harder, still-unresolved problem into the same spec as a comparatively simple,
now twice-verified one serves neither well. Critic promotion becomes its own future design, starting
from the fix direction above rather than from scratch.
