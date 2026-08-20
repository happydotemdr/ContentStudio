# P13 — Skill contracts

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` or
> `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. The orchestration plan's
> **Global Constraints** and **test standard**
> ([`../2026-08-08-audit-remediation.md`](../2026-08-08-audit-remediation.md)) are binding and are
> not restated here.

**Wave C.** This package is written after the code is true. Its subject matter is markdown —
skill definitions — so "no behavior change without a failing test first" means: **add the
conformance check, run it, watch it name the real offenders, then edit the markdown until it is
green.** Every task below is ordered that way.

**The centre of this package is `tests/test_skill_provenance.py`.** Today it has 6 tests covering
1 skill of 13, 1 reference file of 64, and 13 normative blocks of 655 (2.0%). Tasks T1, T2, T13,
T14, T15, T16 and T18 turn it into a data-driven conformance suite over all 13 skills asserting
four properties:

1. every declared output field another skill consumes **by name** exists in the producer;
2. every **bare** `references/x.md` citation resolves inside its own skill;
3. every `§`-anchor citation resolves in the file it points at;
4. every normative block carries a marker **or** an explicit, recorded triage exemption.

That suite is what stops all 48 findings recurring. The markdown edits without it are a one-time
cleanup that drifts back within two sessions.

---

## 1. Scope

### Files this package owns (no other package may touch these)

```
.claude/skills/elevenlabs-audio/SKILL.md
.claude/skills/elevenlabs-audio/references/api-payload.md
.claude/skills/elevenlabs-audio/references/control-surface.md
.claude/skills/elevenlabs-audio/references/cost-and-credits.md
.claude/skills/elevenlabs-audio/references/directorial-prompting.md
.claude/skills/elevenlabs-audio/references/model-routing.md
.claude/skills/elevenlabs-audio/references/pronunciation-dictionaries.md
.claude/skills/elevenlabs-audio/references/validation-gates.md
.claude/skills/elevenlabs-audio/references/voice-profiles.md
.claude/skills/elevenlabs-audio/references/voice-settings.md
.claude/skills/elevenlabs-audio/references/worked-example.md
.claude/skills/elevenlabs-music/SKILL.md
.claude/skills/elevenlabs-music/references/api-payload.md
.claude/skills/elevenlabs-music/references/composition-plans.md
.claude/skills/elevenlabs-music/references/prompt-craft.md
.claude/skills/elevenlabs-music/references/validation-gates.md
.claude/skills/midjourney-prompting/SKILL.md
.claude/skills/midjourney-prompting/references/parameters.md
.claude/skills/midjourney-prompting/references/prompt-architecture.md
.claude/skills/midjourney-prompting/references/render-economics.md
.claude/skills/midjourney-prompting/references/style-systems.md
.claude/skills/midjourney-prompting/references/v82-model-delta.md
.claude/skills/midjourney-prompting/references/validation-gates.md
.claude/skills/midjourney-prompting/references/worked-example.md
.claude/skills/music-brief/SKILL.md
.claude/skills/music-brief/references/bed-arc.md
.claude/skills/rgs-grounding/SKILL.md
.claude/skills/rgs-grounding/references/brand-voice-and-tone.md
.claude/skills/rgs-grounding/references/pairing-map.md
.claude/skills/rgs-grounding/references/research-corpus-protocol.md
.claude/skills/rgs-grounding/references/safety-sensitive-handling.md
.claude/skills/rgs-grounding/references/scripting-beat-mapping.md
.claude/skills/rgs-grounding/references/thinker-corpus-protocol.md
.claude/skills/rgs-grounding/references/worked-example.md
.claude/skills/rgs-pairing-review/SKILL.md
.claude/skills/shorts-assembly/SKILL.md
.claude/skills/shorts-assembly/references/caption-overlay-system.md
.claude/skills/shorts-assembly/references/loudness-and-mix.md
.claude/skills/shorts-assembly/references/pacing-and-editing.md
.claude/skills/shorts-assembly/references/tool-stack.md
.claude/skills/shorts-assembly/references/worked-example.md
.claude/skills/shorts-ideation/SKILL.md
.claude/skills/shorts-ideation/references/angle-selection.md
.claude/skills/shorts-ideation/references/hook-concepts.md
.claude/skills/shorts-ideation/references/packaging-direction.md
.claude/skills/shorts-ideation/references/validation-gate.md
.claude/skills/shorts-ideation/references/worked-example.md
.claude/skills/shorts-scripting/SKILL.md
.claude/skills/shorts-scripting/references/beat-timing-model.md
.claude/skills/shorts-scripting/references/endings-and-ctas.md
.claude/skills/shorts-scripting/references/hooks-and-openings.md
.claude/skills/shorts-scripting/references/read-aloud-gates.md
.claude/skills/shorts-scripting/references/retention-loops-and-structure.md
.claude/skills/shorts-scripting/references/script-intelligence-and-delivery.md
.claude/skills/shorts-scripting/references/worked-example.md
.claude/skills/shorts-styleboard/SKILL.md
.claude/skills/shorts-styleboard/references/styleboard-format.md
.claude/skills/shorts-styleboard/references/visual-registers.md
.claude/skills/social-repurpose/SKILL.md
.claude/skills/social-repurpose/references/cross-platform-captions.md
.claude/skills/social-repurpose/references/worked-example.md
.claude/skills/social-repurpose/references/youtube-description-hashtags.md
.claude/skills/social-repurpose/references/youtube-title-rules.md
.claude/skills/visual-prompts/SKILL.md
.claude/skills/visual-prompts/references/faceless-pacing-rules.md
.claude/skills/visual-prompts/references/image-to-video.md
.claude/skills/visual-prompts/references/prompt-sheet-format.md
.claude/skills/visual-prompts/references/visual-arc.md
.claude/skills/visual-prompts/references/visual-registers.md   ← deleted by T14 (tombstone)
.claude/skills/visual-prompts/references/worked-example.md
.claude/skills/voiceover-brief/SKILL.md
.claude/skills/voiceover-brief/references/channel-voice.md
.claude/skills/voiceover-brief/references/production-and-loudness.md
.claude/skills/voiceover-brief/references/scripting-for-tts.md
.claude/skills/voiceover-brief/references/settings-by-content-type.md
.claude/skills/voiceover-brief/references/voice-selection.md
.claude/skills/voiceover-brief/references/worked-example.md
tests/test_skill_provenance.py
```

**Not owned, read-only from here:** `pipeline.yaml` (P4), `docs/style-library.md` (P11),
`scripts/lint_prompt_sheet.py` (P11), `scripts/resolve_brief_version.py` (P12),
`CLAUDE.md` / `docs/README.md` (P14), `rgs-briefs/**` (P14),
`cowork-plugin/skills/**` (build artifact, git-ignored, regenerated by P12's build script).

### Finding IDs (48)

`B-84`, `C-01`–`C-35`, `C-40`–`C-48`, `C-54`, `C-55`, `F-22`.

---

## 2. Finding → task map

Total coverage: 48/48. `T1` and `T2` are test infrastructure; every other task pairs one
conformance check (or one already-added check) with the file edits that turn it green.

| Finding | Sev | Task | What the task does |
|---|---|---|---|
| C-48 | S2 | T1 | `MARKER_RE` gains `[P]`; module docstring stops implying whole-set coverage |
| — | — | T2 | Handoff-contract block machinery + the two handoff conformance tests (red) |
| C-01 | S2 | T3 | `voiceover-brief` gains a declared `## Tone per beat` output section |
| C-24 | S3 | T3 | `voiceover-brief` step 1 narrowed; transitive pointer-chase deleted |
| C-16 | S3 | T4 | `elevenlabs-music` Gate 1 reads only the declared Bed Arc section |
| C-25 | S4 | T4 | `music-brief` reads two named sections, not two whole artifacts |
| C-03 | S2 | T5 | `shorts-assembly` script dependency reconciled with the stage graph |
| C-08 | S4 | T5 | "five things" → "six things" |
| C-18 | S3 | T5 | Input 2 restated as the fields the VO brief actually emits |
| C-21 | S2 | T5 | `shorts-assembly` gains a named-section output contract |
| C-35 | S3 | T5 | Description states all three required inputs + the optional fourth |
| C-04 | S2 | T6 | `social-repurpose` collapses to one input list in all three places |
| C-05 | S3 | T7 | `shorts-scripting` Downstream lists all four consumers |
| C-11 | S4 | T7 | "five workflow steps" → "six" |
| C-06 | S3 | T8 | `shorts-styleboard` gains the "Optional input" section it cites |
| C-07 | S2 | T8 | WORLD LOCK stated as 13 keys in all three places that count it |
| C-26 | S3 | T8 | Styleboard File I/O gains the concept-brief and grounding resolves |
| C-27 | S3 | T8 | "top of the prompt sheet" retargeted at the styleboard's own artifact |
| C-10 | S4 | T9 | "Two things you still own" → "Three things" |
| C-15 | S3 | T9 | "lock the world/registers" deleted from `visual-prompts`' triggers |
| C-28 | S3 | T9 | Register-system ownership credited to `shorts-styleboard` |
| C-30 | S4 | T9 | "step 4's prompt anatomy" → "step 4's delegation block" |
| C-31 | S4 | T9 | Gate B relabelled in the sheet's VALIDATION block |
| C-09 | S4 | T10 | "eight inputs" → "nine"; `register` added to CONTROL SURFACE |
| C-17 | S2 | T10 | Pipeline-mode `{style:…}` row added to the mapping table + Gate A |
| C-13 | S2 | T11 | `elevenlabs-audio` boundary table records the three upstream inputs it must compatibility-check |
| C-14 | S3 | T11 | Disjoint verbs + reciprocal negative scope in both descriptions |
| C-19 | S3 | T11 | AUDIO PRODUCTION SPEC named as `shorts-assembly` input 2b |
| C-20 | S2 | T11 | Two ElevenLabs specialists get a File I/O contract + resolver kind |
| C-02 | S2 | T12 | `rgs-grounding` Downstream + brief Handoff name `shorts-styleboard` |
| C-32 | S4 | T12 | Citation index names the plan path instead of "the implementation plan" |
| C-33 | S4 | T12 | Reciprocal pointers between `rgs-grounding` and `rgs-pairing-review` |
| B-84 | S2 | T12 | `output/raisinggoodsports-brand-definition.md` demoted to a provenance note |
| C-22 | S3 | T13 | One canonical kind registry, published in every skill, test-enforced |
| C-23 | S3 | T13 | Grounding brief gains `kind:`, `slug:`, `stage:` and `--kind grounding` |
| C-12 | S3 | T14 | The three `production-and-loudness.md` citations qualified |
| C-40 | S3 | T14 | All six bare cross-skill citations qualified; resolver test added |
| C-41 | S3 | T14 | 14 tombstone citations requalified; the tombstone file deleted |
| C-55 | S4 | T14 | Cross-skill citations must be skill-qualified — enforced |
| C-42 | S2 | T15 | Three-category provenance triage + the marker conformance test |
| C-43 | S3 | T15 | RGS alternative vocabulary declared in a machine-readable registry |
| C-54 | S3 | T15 | One worked-example policy applied to all nine files |
| C-48 | S2 | T15 | The suite actually covers 13 skills / 64 reference files |
| F-22 | S2 | T15 | Same; the filename's promise becomes true |
| C-44 | S3 | T16 | 33 uncited `[C]` blocks backfilled; `(Channel, id)` form enforced |
| C-45 | S3 | T16 | `image-to-video.md`'s bare/malformed ids get their channels back |
| C-46 | S2 | T16 | Dated verification header on every `[T]`-carrying reference file |
| C-47 | S3 | T16 | `[T]` dropped from the branding assertion in two files |
| C-34 | S3 | T17 | `docs/style-library.md` declared as a read (and a write) in the I/O sections |
| C-29 | S4 | T18 | Four descriptions gain their body's existing negative-scope sentence |

---

## 0. Amendment — pre-flight check before starting (2026-08-19)

Checked before this package's Task 1 is ever dispatched, per this programme's established
discipline (every prior package that landed between a plan's authoring and its execution has
been the norm, not the exception — see P9's and P15's own §0/§8 for precedent).

**P13's own owned scope (every file under §1 — all of `.claude/skills/**` plus
`tests/test_skill_provenance.py`) is untouched.** `git log 634bb2e..HEAD -- .claude/skills/
tests/test_skill_provenance.py` (634bb2e is this plan file's own authoring commit,
2026-08-10) returns **zero commits**. `tests/test_skill_provenance.py` still has exactly the 6
tests this plan's own intro paragraph describes. Nothing has drifted inside P13's actual file
list.

**`pipeline.yaml` (P4's file, read-only reference for P13, explicitly named in §6.2) changed on
2026-08-15 — five days after this plan was authored — in exactly the way §6.2's own "one open
item P4 must decide" anticipated.** Commit `28d1862` ("declare the script, styleboard and
bed-arc edges assembly and repurpose actually need"):

```diff
   - id: assembly
     skill: shorts-assembly
     dir_prefix: "04"
-    depends_on: [voiceover, visual]
+    depends_on: [scripting, styleboard, voiceover, visual]
+    optional_depends_on: [music]
   - id: repurpose
     skill: social-repurpose
     dir_prefix: "05"
-    depends_on: [assembly]
+    depends_on: [ideation, scripting, assembly]
```

§6.2 predicted precisely this: "If P4 instead adds `scripting` to `assembly`'s `depends_on`,
T5's 'Input 2 in app-driven mode' paragraph becomes wrong and must be simplified to a direct
read." P4 took that route. **Two concrete, confirmed task impacts:**

1. **T5 (C-03)** — the plan's fix routes `shorts-assembly`'s script input through the voiceover
   brief's `script:` pointer, because at authoring time `assembly` had no direct `scripting`
   edge. That workaround is now unnecessary and, per §6.2's own words, **wrong**: `assembly` now
   declares `scripting` directly, so T5 should have `shorts-assembly` read the script directly
   rather than routing through voiceover's pointer. Simplify T5's "Input 2 in app-driven mode"
   paragraph before dispatching it — do not implement the pointer-chase workaround as originally
   written.
2. **T7 (C-05)** — `test_downstream_list_matches_the_stage_graph` (§4) asserts
   `shorts-scripting`'s Downstream bullet names every stage whose `depends_on` contains
   `scripting`. At authoring time that was 4 stages (`styleboard`, `voiceover`, `visual`,
   `music`) — T7's row literally says "lists all **four** consumers." The live graph now has
   **six**: those four plus `assembly` and `repurpose` (both gained a direct `scripting` edge in
   the same commit). T7's task text needs the same correction before dispatch — the test itself
   is graph-driven and will assert the true count regardless of what the task's prose claims, but
   the prose is now wrong and would mislead whoever implements it.

**Not yet checked, and worth a narrower verification pass before dispatching each — not a full
re-audit, just confirming each task's own specific claim still holds against the current
`pipeline.yaml`/skill files:** T2's `KIND_REGISTRY` (must mirror the current 9-stage graph, not
the 8-stage one implied by the old `depends_on` shapes); C-08/C-09/C-10/C-11's "N things → N+1
things" counts in T5/T7/T9 (these read like prose-list corrections unrelated to `depends_on`
counts, but verify each against its own file before assuming so); §6.2's `repurpose` edge, which
also changed (`[assembly]` → `[ideation, scripting, assembly]`) and is not analyzed above — check
whether any C-0x finding about `social-repurpose`'s stated inputs (C-04, T6) needs the same
treatment as T5/T7. (`assembly`'s new `optional_depends_on: [music]`, shown in the diff above, is
relevant if T2's `KIND_REGISTRY` distinguishes required from optional dependencies.)

**Two inbound cross-package handoffs, found by this amendment's own reviewer, not by the pre-flight
pass above (both are the same class of gap: a sibling package's plan recording a note FOR P13
that nothing in P13's own scope-diff check could ever surface, since the drift is in the sibling's
file, not P13's):**

1. **From P11 (§6.4, `P11-gate-c.md:1880-1887`, "not a blocker"):** P11's own T18 (not this
   plan's T18 — a different task in a different package) widened
   `BANNED_REGISTER_A_STRINGS`/`BANNED_REGISTER_B_STRINGS` in `scripts/lint_prompt_sheet.py`
   (confirmed live: `lint_prompt_sheet.py:743-747` bans `"empty gym", "empty youth gym", "empty
   pitch", "empty stadium"` and more). Their declared `[I]`-marked source of truth is
   `.claude/skills/shorts-styleboard/references/visual-registers.md:47` and `:64` — confirmed
   still only banning `empty gym`/`empty youth gym`. Mirror the widened lists into those two
   lines so the skill instruction and the gate agree. P11 already classified this as non-blocking
   (the gate is stricter than the instruction, which is the safe direction), so this is a
   should-fix, not a must-fix-first — but it belongs on a task list somewhere in this package
   (none of T1–T18 currently covers it).
2. **From P12 (`P12-gate-d-tools.md:1068-1071`):** `shorts-scripting/SKILL.md:262` states
   `resolve_brief_version.py` "prints `NONE\t0` and exits **1**" for the no-prior-version case.
   Confirmed false against the live script (`scripts/resolve_brief_version.py:28-30,142-143`):
   it now has three distinct exit codes (`EXIT_OK=0`, `EXIT_ERROR=2` for an actual failure,
   `EXIT_NONE=3` for the expected empty case) — the no-prior-version case still prints `NONE\t0`
   but exits **3**, not 1, and a genuine error (e.g. a malformed directory) now exits 2 instead of
   being collapsed into the same code. Correct the sentence at `SKILL.md:262`; the printed
   `<path>\t<version>` contract the other nine skills branch on is otherwise unchanged.

Neither handoff has an assigned task above. Fold each into whichever task already touches its
file (T8 touches `visual-registers.md` for C-06/C-07/C-26/C-27; no current task touches
`shorts-scripting/SKILL.md:262` specifically — T7 is the closest, for `shorts-scripting`
generally) or add a one-line addendum task before dispatching T7/T8.

**Everything else in this plan (all 48 findings' task assignments, the six kept/generalised
existing tests in §5, the P14 contract in §6.1) shows no sign of drift from what THIS package's
own file-list check can see** — the `pipeline.yaml` change and the two inbound handoffs above are
the only three discrepancies found. That check only covers drift *inside* P13's own scope or
explicitly flagged by a sibling package's plan; it cannot rule out a sibling package's *silent*
drift the same way the P11/P12 handoffs above were caught by having been recorded somewhere. Full
finding-by-finding re-verification of all 48 findings was not performed.

**Update, 2026-08-20 — a second pre-flight pass, prompted by a large unrelated backlog landing on
`origin/main` since the check above.** This worktree (`worktree-p15-docs-followup`, HEAD `dccfe11`)
is 77 commits behind `origin/main` — an entire standalone `elevenlabs-tooling` package (PR #57),
plus stitcher/native-pipeline/audio-preconditioning/single-take-VO-architecture work, none of it
related to this remediation programme. **This time the claim "P13's own owned scope is untouched"
no longer holds — it is now stale from the check above and must be re-run against `origin/main`
before P13's Task 1 is dispatched from a fresh worktree, not just trusted from this entry.**

`git diff dccfe11 origin/main -- .claude/skills/ tests/test_skill_provenance.py` shows exactly
7 files changed, across 3 commits (`56523c0`, `55000b5`, `3a928c0`), all inside `voiceover-brief`
and `elevenlabs-audio`/`elevenlabs-music` (the pinned narrator voice was re-cloned from IVC to
PVC, and a channel-specific single-take VO architecture decision was recorded):

- `.claude/skills/elevenlabs-audio/references/directorial-prompting.md` — new `[pause]`-vs-`<break>`
  subsection appended near the end of the tag catalog. No P13 task cites this file by line or
  quotes its text — unaffected.
- `.claude/skills/elevenlabs-audio/references/model-routing.md` — new `<break>` feature-matrix row
  and subsection appended before "## Routing decisions". No P13 task cites this file by line or
  quotes its text — unaffected.
- `.claude/skills/elevenlabs-audio/references/voice-profiles.md` — the IVC-specific caveat
  paragraph was rewritten to describe the new PVC pin instead. No P13 task cites this file by line
  or quotes its text — unaffected.
- `.claude/skills/elevenlabs-music/references/composition-plans.md` — the `[T-unverified]` vocal-
  guard caveat was strengthened to "confirmed insufficient by a live generation." No P13 task
  cites this file by line or quotes its text — unaffected.
- `.claude/skills/voiceover-brief/references/channel-voice.md` — `voice_id` changed
  `5kVvcrJnhhULT5LdbshJ` → `eDwT8Vhp2yxJzAMmuuPA`, plus a new "Supersedes" paragraph inserted
  after the line range **C-47 (T16)** cites. **Checked directly: C-47's citation
  (`channel-voice.md:14-17`, the "That voice *is* the channel's identity" replacement) is
  unaffected** — the insertion lands after line 17, not before it. `voice-selection.md` (T16's
  other C-47 citation) is untouched entirely.
- `.claude/skills/voiceover-brief/references/single-take-architecture.md` — **new file**, not in
  §1's owned-file list because it didn't exist when this plan was authored. It is inside
  `voiceover-brief/**`, which the owned-file list already covers as a directory glob, so no scope
  amendment is needed — flagging only so nobody is surprised by an untracked-in-§1 file appearing
  under a package's own owned directory.
- `.claude/skills/voiceover-brief/SKILL.md` — **this one is load-bearing for T3.** Step 4
  ("Reformat the script text for TTS") gained two sentences pointing at the new
  `single-take-architecture.md` file, and the "## Reference files" list gained a new bullet for
  it. Concrete impact on **T3**:
  1. T3's citation `` (`:89-105`) `` for the Output format template is now stale — the live line
     range on `origin/main` is **`:91-107`** (shifted +2 by step 4's growth).
  2. T3's citation `` `:135-138` `` for the File I/O sentence is now stale — the live line range
     is **`:140-143`** (shifted +5: +2 from step 4, +3 from the new Reference-files bullet).
  3. **A genuine content bug, not just a line-number shift:** T3 inserts a new step 3 between the
     current steps 2 and 3, renumbering the old steps 3-6 to 4-7. The old step 4 (TTS reformatting)
     becomes step 5 after that renumbering — but its own newly-landed text ends "...read it before
     applying this step here" (self-referencing "this step") and the new Reference-files bullet
     says "which changes how step 4 below applies". Neither says "step 4" by number in the
     self-reference (it says "this step"), but the **Reference-files bullet does**, and will read
     wrong once renumbering makes TTS-reformatting step 5. T3's dispatch must update that bullet's
     "step 4" to "step 5" as part of the same edit — otherwise it silently ships a wrong
     cross-reference the moment T3 lands.

  Both line-number fixes and the "step 4"→"step 5" bullet correction should be folded into T3's
  own task text before dispatch, the same way the `pipeline.yaml` corrections above were folded
  into T5/T7 — not fixed silently once T3 is underway.

No other P13-owned or P13-adjacent file changed: `pipeline.yaml`, `docs/style-library.md`,
`scripts/lint_prompt_sheet.py`, `scripts/resolve_brief_version.py`, `CLAUDE.md`, `docs/README.md`,
`rgs-briefs/**`, `tests/test_skill_provenance.py`, and `tests/test_build_cowork_plugin.py` are all
identical between `dccfe11` and `origin/main` — the two inbound cross-package handoffs recorded
above (P11's banned-vocabulary mirror, P12's exit-code sentence) are unaffected and still current.
`test_skill_provenance.py` still has exactly the 6 tests this plan's intro describes.

This check, like the one above it, only covers drift inside P13's own scope plus the files this
plan explicitly reads — it is not a re-audit of the 77 unrelated commits themselves (they belong
to no package in this remediation programme and were not reviewed for their own correctness here).

---

## 3. Tasks

### T1 — Make the provenance module a suite, not a guard

**Keep the filename.** C-48 proposes renaming `tests/test_skill_provenance.py` because its name
over-promises. Once T15 lands, the name is accurate — and a rename would force an edit to
`CLAUDE.md:236-241`, which belongs to P14. Fix the docstring instead.

- [ ] **Red.** Append this test to `tests/test_skill_provenance.py` and run
      `python -m pytest tests/test_skill_provenance.py -q` from the repo root. It fails:
      `MARKER_RE` at `:16` omits `[P]`.

```python
def test_marker_re_accepts_the_project_decision_marker():
    """`[P]` is a valid marker (CLAUDE.md's fourth marker). MARKER_RE once omitted it,
    so a correctly-`[P]`-marked bullet inside a guarded slice failed as unmarked."""
    assert MARKER_RE.search("- **Use the pinned narrator voice.** `[P]`")
    assert MARKER_RE.search("- **Draft is half the cost of SD.** `[T-unverified]`")
    assert not MARKER_RE.search("- **Cut every three seconds.**")
```

- [ ] **Green.** Replace line 16:

```python
MARKER_RE = re.compile(r"\[(?:C|I|T|P|T-unverified)\]")
```

- [ ] Replace the module docstring (`:1-7`) with one that describes the suite it is becoming:

```python
"""Conformance suite for the ContentStudio skill set.

Four properties, asserted over all 13 skills and all 64 reference files under
`.claude/skills/`:

  1. Handoff  — every output section one skill consumes by name is declared by the
                skill that produces it (audit C-01, C-04, C-16, C-18, C-21, C-25).
  2. Citation — a bare `references/x.md` citation resolves inside the citing skill;
                a cross-skill citation is skill-qualified; a `§N` anchor exists in the
                file it points at (audit C-12, C-40, C-41, C-55).
  3. Vocabulary — one canonical stage-id / `--kind` / `stage:` registry, agreed across
                every SKILL.md (audit C-22, C-23).
  4. Provenance — every normative block carries `[C]`/`[I]`/`[T]`/`[P]`/`[T-unverified]`,
                an alternative-vocabulary marker its skill declares, or an entry in the
                explicit triage ledger below (audit C-42, C-43, C-48, C-54, F-22).

The narrow regression guards at the bottom of the file predate the suite and are kept
verbatim: they pin the two places the anti-generic guarantee was actually broken.
"""
```

- [ ] Insert the discovery layer directly after the constants. Stdlib only; no PyYAML.

```python
PIPELINE_SKILLS = (
    "shorts-ideation", "shorts-scripting", "shorts-styleboard", "voiceover-brief",
    "visual-prompts", "music-brief", "shorts-assembly", "social-repurpose",
)
SPECIALIST_SKILLS = ("elevenlabs-audio", "elevenlabs-music", "midjourney-prompting")
RGS_SKILLS = ("rgs-grounding", "rgs-pairing-review")
ALL_SKILLS = PIPELINE_SKILLS + SPECIALIST_SKILLS + RGS_SKILLS


def skill_dir(name: str) -> Path:
    return SKILLS / name


def skill_md(name: str) -> Path:
    return SKILLS / name / "SKILL.md"


def reference_files(name: str) -> list[Path]:
    return sorted((SKILLS / name / "references").glob("*.md"))


def every_markdown_file() -> list[Path]:
    return sorted(SKILLS.rglob("*.md"))


def strip_fences(text: str) -> list[tuple[int, str]]:
    """(1-based line number, line) for every line outside a ``` fence."""
    out, in_fence = [], False
    for n, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append((n, line))
    return out


def fenced_block(text: str, info: str) -> str | None:
    """The body of the first ```<info> fence in `text`, or None."""
    lines, body, capturing = text.splitlines(), [], False
    for line in lines:
        if not capturing and line.strip() == f"```{info}":
            capturing = True
            continue
        if capturing and line.strip().startswith("```"):
            return "\n".join(body)
        if capturing:
            body.append(line)
    return None


def test_every_skill_directory_is_classified():
    """A new skill must be added to one of the three registries, or the suite silently
    stops covering it — which is exactly how C-48 happened."""
    on_disk = {p.parent.name for p in SKILLS.glob("*/SKILL.md")}
    assert on_disk == set(ALL_SKILLS), (
        f"unclassified: {sorted(on_disk - set(ALL_SKILLS))}; "
        f"missing from disk: {sorted(set(ALL_SKILLS) - on_disk)}"
    )
```

- [ ] `python -m pytest tests/ -q` green. Commit: `test: widen the skill provenance module into a conformance suite skeleton`.

---

### T2 — Handoff-contract blocks: the machinery and the two checks

The handoff contract is a fenced ```` ```handoff ```` block under a `## Handoff contract
(machine-checked)` heading in every `SKILL.md`. Format: one `key: value` per line, repeated keys
allowed, no nesting. It is deliberately not YAML — a 20-line stdlib parser reads it, and P4's
stage-graph conformance test can bind to the same block.

```
produces.kind:      <the resolve_brief_version.py --kind string, or `none` for a transcript-only skill>
produces.stage:     <the `stage:` frontmatter value, or `none`>
produces.section:   <one line per declared output section, verbatim as it appears in the output template>
consumes:           <producer-skill>#<section name declared by that skill>
reads:              <a repo path this skill reads but does not produce>
writes:             <a repo path this skill mutates but does not own>
```

**Section resolution rule** (this is the contract; implement it exactly): a declared section name
`S` resolves in a producer if the producer's output-format fenced block contains a line whose
text, after stripping leading `#` characters and whitespace, **starts with** `S` and is then
followed by end-of-line, `:`, `(`, or whitespace. That accepts `## Tone per beat`,
`HOOK        (0–3s | N words): "<VO line>"`, `MIX HANDOFF`, and
`Visual notes (for visual-prompts downstream):` without forcing any skill to change the shape of
an output contract another package's linter already parses (Gate D, P12; Gate C, P11).

- [ ] **Red.** Add the parser and both tests. All 13 skills fail: no skill has a handoff block yet.

```python
HANDOFF_KEYS = {"produces.kind", "produces.stage", "produces.section",
                "consumes", "reads", "writes"}


def handoff(skill: str) -> dict[str, list[str]]:
    body = fenced_block(skill_md(skill).read_text(encoding="utf-8"), "handoff")
    assert body is not None, (
        f"{skill}/SKILL.md has no ```handoff block; every skill declares its contract"
    )
    parsed: dict[str, list[str]] = {k: [] for k in HANDOFF_KEYS}
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        assert key in HANDOFF_KEYS, f"{skill}: unknown handoff key {key!r}"
        assert value, f"{skill}: handoff key {key!r} has no value"
        parsed[key].append(value)
    return parsed


OUTPUT_HEADING_RE = re.compile(r"^##+\s+Output (format|contract)\s*$", re.IGNORECASE)


def output_template(skill: str) -> list[str]:
    """Every line of the first fenced block after the skill's Output format/contract heading."""
    text = skill_md(skill).read_text(encoding="utf-8")
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if OUTPUT_HEADING_RE.match(ln.strip())), None)
    assert start is not None, f"{skill}/SKILL.md has no '## Output format' heading"
    body, in_fence = [], False
    for ln in lines[start + 1:]:
        if ln.lstrip().startswith("```"):
            if in_fence:
                break
            in_fence = True
            continue
        if in_fence:
            body.append(ln)
    assert body, f"{skill}/SKILL.md's Output format heading is not followed by a fenced template"
    return body


def section_resolves(skill: str, section: str) -> bool:
    for line in output_template(skill):
        head = line.strip().lstrip("#").strip()
        if not head.startswith(section):
            continue
        rest = head[len(section):]
        if rest == "" or rest[0] in ":( \t":
            return True
    return False


@pytest.mark.parametrize("skill", ALL_SKILLS)
def test_declared_output_sections_appear_in_the_output_template(skill):
    """A skill may not advertise a section its own output template does not contain."""
    missing = [s for s in handoff(skill)["produces.section"] if not section_resolves(skill, s)]
    assert missing == [], f"{skill} declares sections absent from its output template: {missing}"


@pytest.mark.parametrize("skill", ALL_SKILLS)
def test_every_consumed_section_resolves_to_a_declared_producer_section(skill):
    """C-01: `music-brief`, `elevenlabs-audio` and `elevenlabs-music` all consumed
    'the tone-per-beat call' by name from a skill that never declared it."""
    problems = []
    for edge in handoff(skill)["consumes"]:
        producer, _, section = edge.partition("#")
        if producer not in ALL_SKILLS:
            problems.append(f"{edge}: no such skill")
            continue
        if not section:
            problems.append(f"{edge}: no '#<section>' named")
            continue
        if section not in handoff(producer)["produces.section"]:
            problems.append(f"{edge}: {producer} does not declare that section")
    assert problems == [], f"{skill} consumes undeclared fields: {problems}"
```

- [ ] Add `import pytest` at the top of the module.
- [ ] Leave the tests red. T3–T12 close them skill by skill; do not add all 13 blocks here — a
      13-file diff is exactly the shape this plan avoids.
- [ ] Commit the test-only change: `test: assert skill handoff contracts declare what downstream consumes`.

---

### T3 — `voiceover-brief`: declare the tone-per-beat call, stop reading the world

Closes **C-01** (the flagship handoff hole) and **C-24**.

- [ ] Insert a new workflow step between the current steps 2 and 3, renumbering 3–6 to 4–7:

```markdown
3. **Call the tone per beat.** For every beat the script declares, name the tone and the
   delivery intent in one line each. This is the section three downstream skills read by name
   — `music-brief` designs its arc against it, `elevenlabs-music`'s Gate 1 checks the arc for
   contradiction with it, and `elevenlabs-audio` converts each row into tag syntax. Emit a row
   for **every** beat; a missing row is a blocked downstream stage, not a defaulted one `[I]`.
```

- [ ] Add the section to the Output format template (`:89-105`), between `## Voice pick` and
      `## Settings` — settings are derived per beat from it, so it must precede them:

```
## Tone per beat
[One row per script beat: beat | timestamp range (s) | tone | delivery intent.
 One row for every beat the script declares — never omit a beat. Read by name by
 music-brief, elevenlabs-audio and elevenlabs-music.]
```

- [ ] Update the Downstream line of the template:

```
## Downstream
[One line: feeds shorts-assembly alongside visual-prompts' output; the Tone per beat
 section feeds music-brief, elevenlabs-audio and elevenlabs-music]
```

- [ ] **C-24.** Replace step 1 (`:58-60`) with a bounded read:

```markdown
1. **Read the script's beat table** — for each beat: the VO line, its timestamp range, and its
   word count. That, plus the Delivery notes field, is everything this skill needs. Note where
   the tone shifts (hook vs. body vs. CTA); it drives both step 3's tone call and step 4's
   settings.

   **Do not read further upstream.** The voice is already pinned (step 2), so neither the
   concept brief nor the grounding brief informs any decision here `[I]`. Follow the script's
   `grounding:` pointer **only** if its Delivery notes carry a "constraints that survive to
   publish" line — then read that line alone, and carry it verbatim into the brief.
```

- [ ] Replace the corresponding File I/O sentence at `:135-138`:

```markdown
1. Resolve the upstream script: run
   `python scripts/resolve_brief_version.py --slug <slug> --kind script` from the repo root.
   Read its beat table and its Delivery notes field — not the whole file, and not its
   `concept_brief:`/`grounding:` chain (see workflow step 1).
   **Staleness check:** re-run the resolver for `--kind script` again right before you finish —
   if a newer version now exists than the one you read, tell the user before proceeding.
```

- [ ] Add the handoff block under a new `## Handoff contract (machine-checked)` heading placed
      immediately after `## Output format`:

````markdown
## Handoff contract (machine-checked)

```handoff
produces.kind: voiceover-brief
produces.stage: 03-voiceover
produces.section: Voice pick
produces.section: Tone per beat
produces.section: Settings
produces.section: Script, reformatted for TTS
produces.section: Production & loudness
produces.section: Downstream
consumes: shorts-scripting#HOOK
consumes: shorts-scripting#SETUP
consumes: shorts-scripting#BUILD/VALUE
consumes: shorts-scripting#PAYOFF
consumes: shorts-scripting#LOOP/CTA
consumes: shorts-scripting#Total word count
consumes: shorts-scripting#Delivery notes
```
````

- [ ] Run `python -m pytest tests/test_skill_provenance.py -q -k handoff`. `voiceover-brief`'s
      *produces* test goes green; its *consumes* test stays red until T7 gives `shorts-scripting`
      a block. That is expected and is the point of the check.
- [ ] Commit: `fix(voiceover-brief): declare the tone-per-beat section three skills consume`.

---

### T4 — `music-brief` and `elevenlabs-music`: read the declared section, not the whole artifact

Closes **C-25** and **C-16**.

- [ ] **C-25.** Replace `music-brief/SKILL.md:44-47`:

```markdown
1. **Read the timed script's beat table** — beat name and boundary in seconds, nothing else.
   The bed arc needs boundaries, not prose `[I]`.
2. **Read the voiceover brief's `## Tone per beat` section** — that section by name, not the
   whole brief. If the section is absent, stop and ask for it rather than inferring tone from
   the script; inferring is exactly the tone contradiction this skill exists to prevent.
```

- [ ] Replace `music-brief/SKILL.md:103-105`:

```markdown
1. Resolve the two upstream inputs: run `python scripts/resolve_brief_version.py --slug <slug>
   --kind script` and `... --kind voiceover-brief` from the repo root. From the script read the
   beat/timestamp table; from the voiceover brief read the `## Tone per beat` section. Nothing
   else in either file is an input to this skill `[I]`.
   **Staleness check:** re-run both resolver calls again right before you finish — if a newer
   version now exists for either of them than the one you read, tell the user before proceeding.
```

- [ ] Add `music-brief`'s handoff block after `## Output format`:

````markdown
## Handoff contract (machine-checked)

```handoff
produces.kind: music
produces.stage: 03-music
produces.section: Bed arc
produces.section: Hook hold-out
produces.section: Tone-contradiction check
produces.section: Deferred to elevenlabs-music
produces.section: Downstream
consumes: shorts-scripting#HOOK
consumes: shorts-scripting#SETUP
consumes: shorts-scripting#BUILD/VALUE
consumes: shorts-scripting#PAYOFF
consumes: shorts-scripting#LOOP/CTA
consumes: voiceover-brief#Tone per beat
```
````

- [ ] **C-16.** Replace the Gate 1 tone clause in `elevenlabs-music/SKILL.md:139`. Current text
      ends `...; arc does not contradict the voiceover brief's tone-per-beat call`. Replace that
      final clause with:

```
the Bed Arc's `## Tone-contradiction check` section is present and reports no unresolved MISMATCH
```

- [ ] Add one sentence directly beneath the gate table in `elevenlabs-music/SKILL.md`:

```markdown
**Gate 1 never re-runs `music-brief`'s tone call.** The boundary table above assigns the
tone-contradiction call upstream; this gate only confirms that the upstream artifact carries the
section and that it resolved. Reading the voiceover brief here would be re-litigating a decision
this skill declared it accepts `[I]`.
```

- [ ] Add `elevenlabs-music`'s handoff block after `## Output contract` (`produces.kind` filled
      by T11; write it as `none` here and let T11 change it, or defer this bullet to T11 — the
      task order is T11-after-T4, so write `none` now):

````markdown
## Handoff contract (machine-checked)

```handoff
produces.kind: none
produces.stage: none
produces.section: CONTROL SURFACE
produces.section: BED PROFILE
produces.section: SECTION MAP
produces.section: UI PROMPT
produces.section: COMPOSITION PLAN
produces.section: REQUEST PAYLOAD
produces.section: MIX HANDOFF
produces.section: COST
produces.section: QC CHECKLIST
produces.section: VALIDATION GATES
produces.section: NEXT
consumes: music-brief#Bed arc
consumes: music-brief#Hook hold-out
consumes: music-brief#Tone-contradiction check
consumes: music-brief#Deferred to elevenlabs-music
consumes: voiceover-brief#Production & loudness
```
````

- [ ] Commit: `fix(music): read the declared tone section instead of re-deriving the tone call`.

---

### T5 — `shorts-assembly`: inputs that exist, an output with named sections

Closes **C-03**, **C-08**, **C-18**, **C-21**, **C-35**.

- [ ] **C-03.** `pipeline.yaml`'s `assembly` stage is `depends_on: [voiceover, visual]` — no
      `scripting`. Two ways to reconcile; take the one that does not require a P4 edit, and state
      the alternative as a contract (see §6). Replace `:27-29`:

```markdown
If input 1 or 3 is missing, ask for it rather than inventing shot content — this skill assembles
what upstream produced, it doesn't re-derive the visuals. **The fourth is genuinely optional and
its absence is never a blocker.**

**Input 2 in app-driven mode.** The `scripting` stage is not one of this stage's `depends_on`, so
the script is not among `input_files`. Reach it through the voiceover brief's `script:`
frontmatter pointer — read the beat table and the `Total word count` line, which is where wpm and
runtime actually live `[I]`. If that pointer is absent, say so and ask for the script rather than
building the plan from the voiceover brief's paraphrase.
```

- [ ] **C-18.** Replace input 2 (`:18`):

```markdown
2. The voiceover brief — its `## Voice pick`, `## Tone per beat`, `## Settings`,
   `## Script, reformatted for TTS`, and `## Production & loudness` sections. It does **not**
   carry pacing wpm or a take count: wpm and total runtime come from the script's
   `Total word count: ~N words (150–170 wpm)` line, and no skill in the pipeline emits a take
   count at all `[I]`.
```

- [ ] Renumber input 3's parenthetical unchanged; add input 2b for **C-19** (T11 writes the text,
      but the slot is created here so T11 is a one-line diff):

```markdown
2b. **Optional — the `elevenlabs-audio` AUDIO PRODUCTION SPEC**, if the VO was rendered through
   that specialist. Use its `DIRECTORIAL SCRIPT` chunk boundaries and its rendered-asset filename
   in the shot table and the mix section. Absent, treat the VO as one continuous take `[I]`.
```

- [ ] **C-08.** Replace `:49`:

```markdown
**Output:** a single edit plan covering six things, every one gated by a corpus rule, not convention:
```

- [ ] **C-21.** Replace `:70` and add an explicit output contract immediately after it:

````markdown
Then produce the plan itself under these six headings, in this order. `references/worked-example.md`
(a full worked run using the corpus's own S042 "coffee trick" script) shows each heading filled in
— copy the *content depth* from it, and the *headings* from here. A downstream skill parses these
headings by name; renaming one breaks `social-repurpose` `[I]`.

```
## Shot table
[One row per cut: # | beat | time range | visual source (sheet shot #) | on-screen text | duration]

## Caption & overlay treatment
[Caption style, hook/re-hook card timing, safe-zone map, and the explicit call on the
 full-duration vs. front-loaded caption split with the reason]

## Aspect ratio & safe zones
[1080×1920, 9:16, plus the safe-zone insets and any runtime-eligibility caveat]

## Loudness & mix
[-14 LUFS integrated, ducking depth, voice-peak range, phone-speaker QA step, bed asset
 filename if a music brief was supplied]

## Tool stack
[The $0 path and the paid path, each as concrete named steps ending in the publish sequence:
 upload unlisted → let it process → add metadata → schedule public]

## QA gate & publish gate
[The checklist from tool-stack.md, every item marked pass/fail — never omitted]

## Constraints that survive to publish
[Any constraint line carried verbatim from the script's or grounding brief's Delivery notes,
 or the literal word "none". Never blank — social-repurpose reads this section by name.]
```
````

- [ ] **C-35.** Replace the description's trigger sentence (`:3`). New sentence, inserted in place
      of `Use this whenever the user has a finished Short script (from shorts-scripting) and wants
      to know how to actually cut it together`:

```
Use this once three inputs exist — the timed script, the voiceover brief, and the visual prompt
sheet — plus an optional fourth, the music-brief bed arc; it blocks rather than guesses if any of
the three is missing.
```

- [ ] Add the handoff block after the new output contract:

````markdown
## Handoff contract (machine-checked)

```handoff
produces.kind: assembly
produces.stage: 04-assembly
produces.section: Shot table
produces.section: Caption & overlay treatment
produces.section: Aspect ratio & safe zones
produces.section: Loudness & mix
produces.section: Tool stack
produces.section: QA gate & publish gate
produces.section: Constraints that survive to publish
consumes: shorts-scripting#Total word count
consumes: shorts-scripting#Visual notes
consumes: shorts-scripting#Delivery notes
consumes: voiceover-brief#Voice pick
consumes: voiceover-brief#Tone per beat
consumes: voiceover-brief#Settings
consumes: voiceover-brief#Script, reformatted for TTS
consumes: voiceover-brief#Production & loudness
consumes: visual-prompts#WHOLE-SHORT SETUP
consumes: visual-prompts#COVER / THUMBNAIL
consumes: music-brief#Bed arc
consumes: music-brief#Hook hold-out
reads: docs/style-library.md
```
````

- [ ] Commit: `fix(shorts-assembly): name the six output sections and the inputs that exist`.

---

### T6 — `social-repurpose`: one input list, stated three times identically

Closes **C-04**. The three divergent statements are `:3` (four artifacts), `:12-13` (three), and
`:128-131` (two resolvable). Collapse to the two the skill can actually reach.

- [ ] Replace the description clause at `:3` — `use it after a Short has been assembled (script +
      voiceover brief + visual prompts + edit plan from shorts-assembly)` becomes:

```
use it after a Short has been assembled, with exactly two inputs: the timed script (for hook
language and any publish constraint) and shorts-assembly's edit plan
```

- [ ] Replace `:12-13`'s upstream paragraph opening:

```markdown
**Upstream input — two artifacts, no more.** The timed script from `shorts-scripting` (hook
language, AEO specifics, and the `Delivery notes` constraint line) and the edit plan from
`shorts-assembly` (which carries the packaging direction forward, plus its
`## Constraints that survive to publish` section). Thumbnail *design* is not re-derived here —
that is `shorts-ideation`/`shorts-assembly` territory; this skill writes the **text** that
accompanies the finished video.
```

- [ ] Replace the "constraints" sentence in the same paragraph so it names the section:

```markdown
**Read `shorts-assembly`'s `## Constraints that survive to publish` section** `[I]`. It is never
blank — it carries the literal word "none" when nothing applies. If it names a constraint (e.g. a
mandatory safety-resource mention, or a quotability restriction), honor it in the post copy; this
skill does not need to know what produced the constraint, only that it is flagged.
```

- [ ] The File I/O step at `:128-131` already resolves `--kind script` and `--kind assembly` —
      that is now correct. Delete its trailing clause `, and follow the script's
      `concept_brief:`/`grounding:` pointer fields if you need packaging direction or citation
      constraints to carry forward` and replace with:

```markdown
   Packaging direction and any publish constraint arrive through the edit plan's own sections —
   do not chase the script's `concept_brief:`/`grounding:` pointers `[I]`.
```

- [ ] Add the handoff block after `**Output contract:**`'s numbered list:

````markdown
## Handoff contract (machine-checked)

```handoff
produces.kind: social-repurpose
produces.stage: 05-repurpose
produces.section: A **YouTube package**
produces.section: **Cross-platform caption variants**
consumes: shorts-scripting#HOOK
consumes: shorts-scripting#Delivery notes
consumes: shorts-assembly#Constraints that survive to publish
consumes: shorts-assembly#Shot table
```
````

> The two `produces.section` values are the literal first tokens of the numbered output-contract
> items. If T5's reviewers prefer `## Headings` here too, convert the numbered list to headings and
> update both lines — the test enforces whichever form is chosen.

- [ ] Commit: `fix(social-repurpose): state one input list in all three places`.

---

#### NEW FINDING raised in the field 2026-08-10 — AWAITING OPERATOR VALIDATION, not yet a task

**The script format Gate D enforces is authoritatively defined nowhere, and the skill's own worked
example does not parse under its own gate.**

Raised while root-causing a real Gate D failure on an authored Short. Full evidence:
`.superpowers/sdd/2026-08-08-audit-remediation/GATE-D-PARSE-design.md` §0/§1. The parser-side defect
is filed separately as **C-88b → P12 T1b**; this is the larger, documentation-side half, and every
file it touches is already in this package's §1 scope.

**Four partial definitions, and they disagree:**

| Where | What it defines |
|---|---|
| `shorts-scripting/SKILL.md:162-201` | the format, inline |
| `shorts-scripting/references/worked-example.md:49-75` | a *continuation* form |
| `shorts-scripting/references/read-aloud-gates.md:102-103` | a third partial statement |
| the design spec `:288-297` | "indented sub-ranges" |

**The sub-beat grammar exists only in `SUBRANGE_RE` (`scripts/lint_script_language.py:26`) plus six
fixture lines.** Authors and the parser are therefore two hand-maintained copies of one contract
with no round-trip check — the same shape this programme has already found three times in status
and platform vocabularies, and the reason C-88b was writable in the first place.

**Measured, not asserted: the skill's own worked example produces 1 VO line and 5 `PARSE` findings
when run through Gate D.** The same continuation form appears in two live
`runs/*/02-scripting/artifact.v*.md`. So a script written by faithfully following the documented
example is mis-parsed by the gate that judges it — and, before C-88b lands, mis-parsed *silently*.

**Why this is filed rather than fixed:** it is a documentation-and-format question this package
owns, it is larger than the parser defect, and one part of it is an operator decision (below). It
should become a task here after validation, sequenced **after** P12 T1b so the documented grammar
and the enforced grammar are reconciled in one direction rather than two.

> **OPERATOR DECISION REQUIRED — do not decide this inside a package.**
> Should **label-first sub-beats** (`mechanism: (11–18s | 19 words)`) become **legal**?
> Making them legal is a ~4-line parser change with **zero measured collateral** across all 19 real
> script artifacts. Keeping them illegal is the status quo and is what P12 T1b enforces loudly.
> This is a format decision to be made once and written down — **not** a parser fix, and not P12's
> to take. Either answer is coherent; what is incoherent is the present state, where the rule
> exists only as a regex and the documentation contradicts it.

---

### T7 — `shorts-scripting` and `shorts-ideation`

Closes **C-05** and **C-11**.

- [ ] **C-05.** Replace `shorts-scripting/SKILL.md:23-30`:

```markdown
- **Downstream output feeds four skills:**
  - **`shorts-styleboard`** (**required next** — `visual-prompts` hard-stops without its
    artifact) — needs the beat list and the claim each beat rests on, to lock the two registers.
  - **`voiceover-brief`** (required) — needs each beat's VO line, timestamp range, and word
    count to build the ElevenLabs production brief.
  - **`visual-prompts`** (required, and requires the styleboard first) — needs each beat's
    timestamp range and visual note to build the Midjourney prompt sheet.
  - **`music-brief`** (optional, and runs *after* `voiceover-brief`) — needs the beat boundaries
    in seconds; its tone input comes from the voiceover brief, not from here.
  All four are authored separately — this skill's job ends at a complete, self-contained script;
  don't reach ahead into voice-setting or image-prompt territory (see "What this skill does NOT
  do" below).
```

- [ ] Amend step 11 (`:137-138`) so the reproduced handoff line stays accurate:

```markdown
11. **Fill the output contract exactly** (below) and state the up/downstream handoff explicitly
    at the end of the response, naming all four downstream consumers and which are required for
    the next stage to run.
```

- [ ] **C-11.** Replace `shorts-ideation/SKILL.md:182-183`:

```markdown
See `references/worked-example.md` for a full worked run — a raw idea taken through all six
workflow steps to the finished concept brief handed off to `shorts-scripting`.
```

- [ ] Add `shorts-scripting`'s handoff block after `## Output contract`'s fenced template:

````markdown
## Handoff contract (machine-checked)

```handoff
produces.kind: script
produces.stage: 02-scripting
produces.section: HOOK
produces.section: SETUP
produces.section: BUILD/VALUE
produces.section: PAYOFF
produces.section: LOOP/CTA
produces.section: Comment-bait question
produces.section: Next-video bridge
produces.section: Total word count
produces.section: GATES
produces.section: Visual notes
produces.section: Delivery notes
consumes: shorts-ideation#Angle / take
consumes: shorts-ideation#Hook concept
consumes: shorts-ideation#Packaging direction
consumes: rgs-grounding#Handoff
consumes: rgs-grounding#Constraints that survive to publish
```
````

- [ ] Add `shorts-ideation`'s handoff block after `## Concept brief template`:

````markdown
## Handoff contract (machine-checked)

```handoff
produces.kind: concept-brief
produces.stage: 01-ideation
produces.section: Angle / take
produces.section: Hook concept
produces.section: Packaging direction
produces.section: Validation
produces.section: Grounding
produces.section: Handoff
```
````

- [ ] Commit: `fix(scripting,ideation): correct the downstream list and the step count`.

---

### T8 — `shorts-styleboard`

Closes **C-06**, **C-07** (styleboard half), **C-26**, **C-27**.

- [ ] **C-06.** Add the missing section immediately after `## Pipeline position`, matching the
      three sibling skills that carry one:

```markdown
## Optional input: a companion grounding artifact `[I]`

If a grounding artifact was produced for this Short (`rgs-grounding`), its thinker/source and its
motif populate the `register_b_thinker`, `register_b_era_place`, `register_b_locations`,
`register_b_artifacts`, `register_b_figure_archetype` and `motif` keys **directly** — they are
inherited, never invented here. Its topic and claim also constrain the Register A sport (step 1).
If no companion artifact was provided, this section doesn't apply — lock the world from the script
alone.
```

- [ ] **C-07.** Replace `:30-32`:

```markdown
Before any per-beat decision or prompt exists, emit the `WORLD LOCK` block per
`references/visual-registers.md` §7 — **thirteen keys** (5 `register_a_*`, 5 `register_b_*`,
`motif`, `slot_register_a`, `slot_register_b`) under the `WORLD LOCK` heading, the block every
downstream prompt inherits from `[I]`. The block below is the contract; the count is stated only
so a truncated emission is visible:
```

- [ ] Replace `references/styleboard-format.md:12` (inside the "Exact shape" fence):

```
WORLD LOCK
  [all 13 keys: the 11 world keys from visual-registers.md §7, plus slot_register_a and
   slot_register_b — one slot_* line per slot the sheet uses]
```

- [ ] **C-27.** Replace `:54-55` (`Name the choice at the top of the prompt sheet, not buried in
      the world-lock block alone.`):

```markdown
State the rationale under this artifact's own `BINDINGS` section as well as in
`register_a_rationale`, so a reader sees the sport choice without parsing the world-lock block
`[I]`. **Do not write into the prompt sheet** — that artifact belongs to `visual-prompts`, is
byte-level linted by Gate C, and its own rule is "do not re-emit the WORLD LOCK block — one home,
no sync rule needed."
```

- [ ] Replace the trailing pointer in the same paragraph (`see "Optional input" above`) — it now
      resolves, so keep it verbatim; verify with T14's anchor test.
- [ ] **C-26.** Replace the File I/O standalone step 1:

```markdown
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
```

- [ ] Add the handoff block after `### 4. Emit the styleboard artifact`:

````markdown
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
````

> `produces.section` resolves against `references/styleboard-format.md`'s "Exact shape" fence, not
> a fence in `SKILL.md`. Extend `output_template()` in T2 with: if `SKILL.md` has no
> `## Output format` heading, fall back to the first fenced block under an
> `## Exact shape` heading in the file named by the skill's `references/*-format.md`. Implement
> that fallback here, driven by this task's red test.

- [ ] Commit: `fix(shorts-styleboard): thirteen keys, three reachable inputs, one artifact to write`.

---

### T9 — `visual-prompts`

Closes **C-07** (its half), **C-10**, **C-15**, **C-28**, **C-30**, **C-31**.

- [ ] **C-15.** In the description (`:3`), delete the string `"lock the world/registers," ` from
      the trigger list. The final disclaimer sentence stays exactly as written.
- [ ] **C-07.** Replace `:97-100`:

```markdown
The world lock is `shorts-styleboard`'s output, not yours. Read the styleboard artifact handed to
you and inherit **all thirteen keys** unchanged `[I]` — the 11 `register_a_*` / `register_b_*` /
`motif` world keys **and** the two `slot_register_a` / `slot_register_b` declarations, which are
the lines Gate C's C20 resolves against the Style Library. **Do not re-emit the `WORLD LOCK` block
into your sheet** — one home, no sync rule needed.
```

- [ ] **C-10.** Replace `:174`:

```markdown
Three things you still own at this step:
```

- [ ] **C-30.** Replace `:63-65`:

```markdown
If a companion grounding artifact is handed to this skill, its motif cue still informs
shot-composition for the beat(s) carrying that citation — fold it into step 2's still-count
decision and into the `subject:` field of step 4's delegation block for that beat, the same way
any other visual note is used. **Not into prompt anatomy** — step 4 delegates prompt wording
entirely to `midjourney-prompting`.
```

- [ ] **C-28.** Replace `:53-59`:

```markdown
The register system and its shot-class taxonomy are **`shorts-styleboard`'s operational design
`[I]`**, read here and never redefined — see
`shorts-styleboard/references/visual-registers.md`. What this skill owns is the arc-first
sequencing discipline (`references/visual-arc.md`), Gate C's checks, and the sheet format
(`references/prompt-sheet-format.md`) — also `[I]`, also not corpus-derived: the corpus has
nothing to say about sequencing a shot table before writing prompts. The thin `[C]` §6 pacing
theme cited above backs the cautions those files guard against (stale frames, uncanny-valley
motion), and the `[T]` Midjourney parameter bands they cite are web-verified against
`docs.midjourney.com` — but the arc/Gate C system itself is not presented as corpus-derived.
```

- [ ] Replace the second ownership paragraph at `:337-344` with the same attribution:

```markdown
The arc-first sequencing discipline (`references/visual-arc.md`) and the copy-paste output
contract (`references/prompt-sheet-format.md`) are **this skill's own operational design `[I]`**,
not corpus findings; the dual-register system they build on is `shorts-styleboard`'s
(`shorts-styleboard/references/visual-registers.md`), also `[I]`. The corpus's thin §6 visuals
theme (27 findings) says nothing about registers, shot-class taxonomies, arc sequencing, or a
machine-parseable output format. Say so plainly if asked how solid these files are: the pacing
cautions they build on (`[C]`) and the Midjourney parameter bands they cite (`[T]`, verified
2026-07-26) are sourced; the register system, the shot classes, the arc discipline, Gate C's
checks, and the sheet format itself are not.
```

- [ ] **C-31.** Replace the VALIDATION line at `:289`:

```
  Gate B (midjourney-prompting adversarial art direction — production-stage prompts only): [pass/fail/n/a]
```

- [ ] Add the handoff block after the sheet skeleton fence:

````markdown
## Handoff contract (machine-checked)

```handoff
produces.kind: visual-prompts
produces.stage: 03-visual
produces.section: WHOLE-SHORT SETUP
produces.section: COVER / THUMBNAIL
produces.section: I2V PROMPTS
produces.section: OVERLAY COPY HANDOFF
produces.section: VALIDATION
consumes: shorts-scripting#Visual notes
consumes: shorts-scripting#HOOK
consumes: shorts-styleboard#WORLD LOCK
consumes: shorts-styleboard#BINDINGS
```
````

- [ ] Commit: `fix(visual-prompts): thirteen keys, correct ownership, disjoint triggers`.

---

### T10 — `midjourney-prompting`

Closes **C-09** and **C-17**.

- [ ] **C-09.** Replace `:105`:

```markdown
Infer the nine inputs. Echo them back in one compact block with every assumed default named.
Proceed without waiting for confirmation unless `format` is genuinely unknowable.
```

- [ ] Replace the CONTROL SURFACE line in the output contract (`:212`):

```
  subject / stage / look / format / consistency / literalism / variance / budget / register
```

- [ ] **C-17.** Replace the `consistency: style-lock` row of the deterministic mapping table
      (`:94`) with two rows:

```
| `consistency: style-lock` (standalone) | `--sref <code>` + `--sw`, or moodboard `--p <code>` |
| `consistency: style-lock` (**pipeline mode**) | the inherited `{style:register_a}` / `{style:register_b}` / `{char:<name>}` slot token handed down by `visual-prompts`, placed **last in the flag block** — **never** a literal code. Gate C's C16 rejects an invented code and C18 rejects a slot placed before the first ` --` |
```

- [ ] Add the matching item to Gate A's checklist row (`:192`), appended to the existing cell text:

```
; **pipeline mode** — the consistency flag is an unresolved `{style:…}`/`{char:…}` slot, not a literal code, and it sits after `--ar`/`--raw`/`--s`
```

- [ ] Add the same item verbatim to `references/validation-gates.md`'s Gate A checklist so the
      dispatched agent actually checks it (the SKILL.md table is a summary of that file).
- [ ] Add the handoff block after `## Output contract`:

````markdown
## Handoff contract (machine-checked)

```handoff
produces.kind: none
produces.stage: none
produces.section: CONTROL SURFACE
produces.section: CONSISTENCY
produces.section: PROMPT
produces.section: LAYER BREAKDOWN
produces.section: PARAMETERS
produces.section: COST
produces.section: VALIDATION
produces.section: ARCHIVE
produces.section: NEXT
consumes: visual-prompts#WHOLE-SHORT SETUP
consumes: shorts-styleboard#BINDINGS
reads: docs/style-library.md
writes: docs/style-library.md
```
````

- [ ] Commit: `fix(midjourney-prompting): nine inputs, and a pipeline-mode style slot row`.

---

### T11 — The three specialists: boundary, descriptions, and a durable artifact

Closes **C-13**, **C-14**, **C-19**, **C-20**.

- [ ] **C-13.** The audit offers two fixes. Take the second — amending the boundary table — because
      moving model routing and tag placement out of `voiceover-brief` would strip the creative
      brief of the fields `shorts-assembly` and `elevenlabs-audio` both already read. Replace
      `elevenlabs-audio/SKILL.md:25-33`:

```markdown
| `voiceover-brief` owns (the call) | `elevenlabs-audio` owns (the execution) |
|---|---|
| Which voice, and why (the shadowban/default-voice reasoning) | The feature-compatibility check that confirms the voice/model pairing renders |
| Tone and delivery intent per beat | The tag syntax that actually produces that delivery |
| Content-type framing | The settings floats / stability mode |
| −14 LUFS target, music ducking, the mix | The request payload, dictionaries, chunking, credit spend |

**Three of those rows arrive partly filled, and you must compatibility-check them rather than
accept them blind** `[I]`. `voiceover-brief` step 2 names a model, step 3 sets the four settings
plus speaker boost, and step 4 places v3 audio tags and phonetic respellings. Treat each as an
**upstream input under review**, not a decided call:

- **Model.** If the named `model_id` cannot render a feature the brief also asks for (a v3-only
  tag on a v2 model, a dictionary on an engine that ignores it), say so and route to the model
  that can. Name the override in `MODEL ROUTING`.
- **Settings.** If a float is out of range for the routed model, or a stability *mode* is named
  where the model takes a float (or vice versa), convert it and say what you converted.
- **Tags.** If a placed tag is not in the routed model's tag catalog, replace it with the nearest
  supported tag or fold the intent into the settings, and say which.

**Do not re-litigate the voice, the tone per beat, the content type, or the mix.** Those four
rows are decided upstream, full stop — that is the "accept the call" rule, and it is scoped to
exactly those four. Loudness and ducking stay with `voiceover-brief`
(`.claude/skills/voiceover-brief/references/production-and-loudness.md`) — do not duplicate or
contradict them here. Downstream of both: `shorts-assembly`.
```

- [ ] Mirror one sentence into `voiceover-brief/SKILL.md:18-25`, replacing `It accepts the voice
      and tone decided here without re-litigating them`:

```markdown
It accepts the voice, the tone per beat, the content type and the mix target without
re-litigating them, and it **compatibility-checks** the model, the settings floats and the tag
placement this brief names — those three are inputs under review there, not final calls `[I]`.
```

- [ ] **C-14.** Give the two descriptions disjoint verbs and reciprocal negative scope.
      In `voiceover-brief/SKILL.md:3`, replace `pick or clone an ElevenLabs voice, set
      TTS/ElevenLabs settings, prep a script for text-to-speech generation` with:

```
decide which voice a Short should use and why, call the tone per beat, or set the loudness and
music-ducking target
```

and replace the final sentence with:

```
Do not use this for the executable ElevenLabs configuration — model routing, settings floats, tag
syntax, pronunciation dictionaries, the JSON payload or a credit estimate are all
`elevenlabs-audio`. Nor for visuals/B-roll (`visual-prompts`) or post copy (`social-repurpose`).
```

In `elevenlabs-audio/SKILL.md:3`, replace the final sentence with:

```
Do not use this to make the creative call — which voice a ContentStudio Short should use and why,
the tone per beat, the content-type framing, or the loudness/ducking mix are all
`voiceover-brief`; this skill converts those into an executable configuration and
compatibility-checks the model, settings and tags it is handed. Nor to write the script's content
(that is `shorts-scripting`).
```

- [ ] **C-19.** T5 already created the input-2b slot in `shorts-assembly`. Complete the round trip
      by replacing `elevenlabs-audio`'s output-contract `NEXT` line (`:224-226`):

```
NEXT
  [draft → confirm → master. Then hand this spec to `shorts-assembly` as its optional input 2b:
   it reads the DIRECTORIAL SCRIPT's chunk boundaries and the rendered asset filename.]
```

- [ ] **C-20.** Give both ElevenLabs specialists a File I/O contract. `midjourney-prompting` gets
      an explicit transcript-only statement instead — its output is absorbed into the prompt sheet.

Append to `elevenlabs-audio/SKILL.md`:

````markdown
## File I/O contract

**App-driven** (a `pipeline-app` turn already told you an output path): follow that instruction
exactly — write only to the named path, overwrite it each turn as instructed.

**Standalone** (no output path was given): run
`python scripts/resolve_brief_version.py --slug <slug> --kind audio-spec --next --date <YYYY-MM-DD>`
and write the AUDIO PRODUCTION SPEC at `rgs-briefs/<filename>` with this frontmatter:

```yaml
---
date: <YYYY-MM-DD>
kind: audio-spec
slug: <slug>
stage: 03-voiceover
version: <version from the resolver>
supersedes: <path from the plain (non---next) resolver call — only if version > 1>
voiceover_brief: <the voiceover brief's path, exactly as the resolver printed it>
status: complete
---
```

State the exact file path in your final chat response. **Outside a ContentStudio Short there is no
slug and no `rgs-briefs/`** — emit the spec in chat and say so explicitly, so the operator knows
it is transcript-only and must be pasted into whatever record they keep `[I]`.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this.
````

Append the same section to `elevenlabs-music/SKILL.md` with `kind: music-spec`, `stage: 03-music`,
and `music_brief:` in place of `voiceover_brief:`, and update its handoff block's
`produces.kind`/`produces.stage` from `none` to `music-spec` / `03-music`. Set
`elevenlabs-audio`'s to `audio-spec` / `03-voiceover`.

Append to `midjourney-prompting/SKILL.md`, under `## Output contract`:

```markdown
**This skill writes no file, by design** `[I]`. In pipeline mode its output is absorbed into
`visual-prompts`' prompt sheet, which is the durable artifact; in standalone mode the spec is
transcript-only and must be pasted into whatever record the operator keeps. The one thing that
**does** persist is a harvested style code — record it in `docs/style-library.md` before the
session closes (step 3).
```

- [ ] Commit: `fix(specialists): a checked boundary, disjoint descriptions, and a durable spec`.

---

### T12 — The two RGS skills

Closes **C-02**, **C-32**, **C-33**, **B-84**.

- [ ] **C-02.** Replace the Downstream cell in `rgs-grounding/SKILL.md:20`:

```
| **Downstream** | Feeds `shorts-ideation` (angle/archetype pick, via the concept brief's Grounding reference line). The same brief then travels forward to `shorts-scripting` (citation text per beat, mapped per `references/scripting-beat-mapping.md`), to **`shorts-styleboard`** (thinker/source and motif, which populate the world lock's `register_b_*` keys and `motif` directly), and to `visual-prompts` (**motif cue for shot composition only** — the register keys are the styleboard's job). Hand it forward at each stage; don't regenerate it |
```

- [ ] Replace the brief template's `## Handoff` block (`:130-132`):

```markdown
## Handoff
Feeds shorts-ideation next. Travels forward as a companion artifact to shorts-scripting
(citation text per beat above, mapped per `references/scripting-beat-mapping.md`),
shorts-styleboard (thinker/source and motif → the world lock's `register_b_*` keys and `motif`),
and visual-prompts (motif cue for shot composition only: [from the map row]).
```

- [ ] **C-32.** Replace `rgs-grounding/SKILL.md:178`:

```markdown
- `references/pairing-map.md` — the curated matches, built per
  `docs/superpowers/plans/2026-07-25-raisinggoodsports-grounding-skills.md` Task 2 (~18–24 rows
  across the brand's 7 signature thinkers).
```

- [ ] **C-33.** Append to `rgs-grounding`'s pairing-map paragraph (after "never a first resort
      taken for speed."):

```markdown
The map itself is maintained by `rgs-pairing-review` — a maintenance skill outside the staged
pipeline. When a run finds no fitting row, the right move is to raise it there (its Gap-fill flag
sweep picks up every `## Gap-fill flag` heading in `rgs-briefs/`), not to normalise the live-glob
fallback.
```

Add to `rgs-pairing-review/SKILL.md`, directly under the H1:

```markdown
**Outside the staged pipeline.** Nothing in `pipeline.yaml` feeds this skill and it feeds no
stage; it mutates `rgs-grounding/references/pairing-map.md` through a human-approved edit and
nothing else. It is invoked on request only — never on a schedule, never as part of a Short's run.
```

- [ ] **B-84.** No acquisition script in this repo writes
      `output/raisinggoodsports-brand-definition.md`, and `output/` is git-ignored and absent from
      a fresh checkout. Demote it to a provenance note in all three citing places; the committed
      `references/` distillations become the authority.

`rgs-grounding/references/brand-voice-and-tone.md:3`:

```markdown
**This file is the authority for the brand's voice, lexicon, archetypes and signature thinkers.**
It was distilled by hand from `output/raisinggoodsports-brand-definition.md` on 2026-07-25 — a
historical provenance note only. No script in this repo produces that path, `output/` is
git-ignored, and a fresh checkout will not have it: do not read it, and do not treat its absence
as a failure `[I]`.
```

`rgs-grounding/references/pairing-map.md:18` — replace `the brand's 7 signature thinkers from
`output/raisinggoodsports-brand-definition.md`` with:

```
the brand's 7 signature thinkers as listed in `brand-voice-and-tone.md`
```

`rgs-pairing-review/SKILL.md:31` — replace `(per `output/raisinggoodsports-brand-definition.md`)`
with:

```
(per `.claude/skills/rgs-grounding/references/brand-voice-and-tone.md`)
```

- [ ] Add handoff blocks. `rgs-grounding` publishes the section names its brief template uses:

````markdown
## Handoff contract (machine-checked)

```handoff
produces.kind: grounding
produces.stage: 00-grounding
produces.section: Handoff
produces.section: Constraints that survive to publish
produces.section: Alternates considered
```
````

`rgs-pairing-review`:

````markdown
## Handoff contract (machine-checked)

```handoff
produces.kind: none
produces.stage: none
produces.section: Proposal
writes: .claude/skills/rgs-grounding/references/pairing-map.md
```
````

> `rgs-pairing-review` has no `## Output format` heading today. Add one whose fenced template
> contains a single `## Proposal` line plus the proposal's existing shape, or the T2 test fails.
> Reuse the workflow's existing proposal description verbatim rather than inventing a new format.

- [ ] Commit: `fix(rgs): name the styleboard downstream and drop the unproduced brand-definition dependency`.

---

### T13 — One artifact vocabulary, enforced

Closes **C-22** and **C-23**.

**Do not rename the existing `--kind` strings.** `resolve_brief_version.py` matches filenames
literally and `rgs-briefs/` already holds ~40 artifacts named `-concept-brief`, `-script`,
`-voiceover-brief`, `-visual-prompts`, `-assembly`, `-social-repurpose`. A rename is a silent
corpus-loss event of exactly the kind P10 is fixing elsewhere. The fix is a **single published
registry**, agreed across all four vocabularies and machine-checked, plus the one genuinely
missing kind (`grounding`, C-23).

- [ ] **Red.** Add the registry and its test:

```python
# stage id (pipeline.yaml) -> (--kind string, `stage:` frontmatter value, owning skill)
KIND_REGISTRY = {
    "grounding": ("grounding", "00-grounding", "rgs-grounding"),
    "ideation": ("concept-brief", "01-ideation", "shorts-ideation"),
    "scripting": ("script", "02-scripting", "shorts-scripting"),
    "styleboard": ("styleboard", "02b-styleboard", "shorts-styleboard"),
    "voiceover": ("voiceover-brief", "03-voiceover", "voiceover-brief"),
    "visual": ("visual-prompts", "03-visual", "visual-prompts"),
    "music": ("music", "03-music", "music-brief"),
    "assembly": ("assembly", "04-assembly", "shorts-assembly"),
    "repurpose": ("social-repurpose", "05-repurpose", "social-repurpose"),
}
# specialists write beside a stage rather than owning one
SPECIALIST_KINDS = {
    "elevenlabs-audio": ("audio-spec", "03-voiceover"),
    "elevenlabs-music": ("music-spec", "03-music"),
    "midjourney-prompting": (None, None),
}
KIND_FLAG_RE = re.compile(r"--kind\s+([a-z][a-z0-9-]*)")


def test_every_kind_flag_in_every_skill_is_in_the_registry():
    """A `--kind` typo returns NONE/exit 1, which every File I/O section documents as the
    benign 'upstream hasn't run yet' case. A vocabulary slip is therefore invisible."""
    known = {k for k, _, _ in KIND_REGISTRY.values()}
    known |= {k for k, _ in SPECIALIST_KINDS.values() if k}
    bad = []
    for path in every_markdown_file():
        for lineno, line in strip_fences(path.read_text(encoding="utf-8")):
            for m in KIND_FLAG_RE.finditer(line):
                if m.group(1) not in known:
                    bad.append(f"{path}:{lineno}: --kind {m.group(1)}")
    assert bad == [], f"unregistered --kind values: {bad}"


@pytest.mark.parametrize("stage,spec", sorted(KIND_REGISTRY.items()))
def test_the_owning_skill_declares_the_registry_kind_and_stage(stage, spec):
    kind, stage_value, skill = spec
    block = handoff(skill)
    assert block["produces.kind"] == [kind], f"{skill} must declare produces.kind: {kind}"
    assert block["produces.stage"] == [stage_value], f"{skill} must declare produces.stage: {stage_value}"


def test_the_registry_matches_the_declared_stage_graph():
    """Cross-check against pipeline.yaml so the two cannot drift. Read-only: pipeline.yaml
    belongs to P4."""
    text = (REPO / "pipeline.yaml").read_text(encoding="utf-8")
    ids = re.findall(r"^\s*-\s*id:\s*(\S+)\s*$", text, re.MULTILINE)
    assert set(ids) == set(KIND_REGISTRY), (
        f"pipeline.yaml stage ids {sorted(ids)} != registry {sorted(KIND_REGISTRY)}"
    )
```

- [ ] **Green, part 1 — publish the registry in the skills.** Add this table verbatim to every
      `SKILL.md`'s `## File I/O contract` section, directly under the heading (specialists get it
      too, under the section T11 added):

```markdown
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
```

- [ ] **Green, part 2 — C-23.** Give the grounding brief the three fields every other artifact
      carries. Replace `rgs-grounding/SKILL.md:85-95`:

```markdown
---
date: [YYYY-MM-DD]
kind: grounding
slug: [topic-slug]
stage: 00-grounding
topic: "[topic]"
thinker: "[Name]"
concept: "[concept]"
research_codes: [[code]]
archetype: [A1/A2/A3]
version: [from `resolve_brief_version.py --next`, below]
supersedes: [previous version's path, from resolve_brief_version.py's plain (non-"--next") call, below -- omit this line entirely if version is 1]
status: candidate
---
```

- [ ] Replace `rgs-grounding/SKILL.md:149` and `:154` so the resolver is called with the kind:

```markdown
First, run `python scripts/resolve_brief_version.py --slug <topic-slug> --kind grounding` from
the repo root. If it prints a path (not `NONE`), that's the current version being superseded —
remember its printed path verbatim for the `supersedes:` field below; it's already
`rgs-briefs/`-relative, don't prepend `rgs-briefs/` again.

Then run
`python scripts/resolve_brief_version.py --slug <topic-slug> --kind grounding --next --date <YYYY-MM-DD>`
to get the exact filename and version number to write.
```

- [ ] **Migration note, stated in the plan, executed by the task.** Adding `--kind grounding`
      changes the filename pattern from `<date>-<slug>.md` to `<date>-<slug>-grounding.md`. The
      ~7 existing kindless grounding briefs in `rgs-briefs/` are **P14's files** — do not rename
      them here. Add this sentence under the resolver instructions so old briefs stay findable:

```markdown
**Briefs written before 2026-08-08 carry no `--kind` suffix.** If `--kind grounding` prints
`NONE` but a bare `<date>-<slug>.md` exists, that is the prior version — name it in `supersedes:`
and write the new one with the suffix. Do not rename the old file `[I]`.
```

- [ ] Delete the stale parenthetical at `rgs-grounding/SKILL.md:10` (`no --kind — grounding briefs
      don't have one`) wherever it appears; the T13 test's `--kind` sweep will not catch a
      *missing* flag, so grep for `no \`--kind\`` across `.claude/skills/` and remove each.
- [ ] Commit: `fix(skills): publish one artifact vocabulary and give the grounding brief a kind`.

---

### T14 — Citations that resolve

Closes **C-12**, **C-40**, **C-41**, **C-55**.

- [ ] **Red.** Add the two resolver tests:

```python
CITE_RE = re.compile(
    r"`(?:\.claude/skills/)?(?:(?P<skill>[a-z0-9-]+)/)?references/(?P<file>[a-z0-9.-]+\.md)`"
    r"(?:\s*(?P<anchor>§[0-9]+(?:[–-]§?[0-9]+)?))?"
)
DUPLICATED_BASENAMES = {"worked-example.md", "validation-gates.md",
                        "api-payload.md", "visual-registers.md"}


def test_every_bare_reference_citation_resolves_inside_its_own_skill():
    """A bare `references/x.md` can only mean 'in this skill' — that is the only path a
    reader of that file can resolve (audit C-40, six broken; C-12, three of them)."""
    broken = []
    for path in every_markdown_file():
        owner = path.relative_to(SKILLS).parts[0]
        for lineno, line in strip_fences(path.read_text(encoding="utf-8")):
            for m in CITE_RE.finditer(line):
                if m.group("skill"):
                    continue  # qualified: checked below
                if not (SKILLS / owner / "references" / m.group("file")).exists():
                    broken.append(f"{path}:{lineno}: references/{m.group('file')}")
    assert broken == [], f"bare citations that do not resolve in their own skill: {broken}"


def test_a_duplicated_reference_filename_is_never_cited_bare_across_skills():
    """C-55: `worked-example.md` exists in 9 skills. A bare citation to a duplicated
    basename always *looks* plausible — that is the mechanism behind C-41."""
    offences = []
    for path in every_markdown_file():
        owner = path.relative_to(SKILLS).parts[0]
        for lineno, line in strip_fences(path.read_text(encoding="utf-8")):
            for m in CITE_RE.finditer(line):
                name = m.group("file")
                if m.group("skill") or name not in DUPLICATED_BASENAMES:
                    continue
                if not (SKILLS / owner / "references" / name).exists():
                    offences.append(f"{path}:{lineno}: {name}")
    assert offences == [], f"unqualified citation of a duplicated filename: {offences}"


ANCHOR_HEADING_RE = re.compile(r"^##+\s*(?:§\s*)?(\d+)[.)]?\s")


def test_every_section_anchor_resolves_in_the_file_it_points_at():
    """C-41: ten citations named §-anchors that existed only in the styleboard copy.
    They *resolved* as files, so no existence check caught them."""
    missing = []
    for path in every_markdown_file():
        owner = path.relative_to(SKILLS).parts[0]
        for lineno, line in strip_fences(path.read_text(encoding="utf-8")):
            for m in CITE_RE.finditer(line):
                if not m.group("anchor"):
                    continue
                target = SKILLS / (m.group("skill") or owner) / "references" / m.group("file")
                if not target.exists():
                    continue  # reported by the tests above
                have = set(ANCHOR_HEADING_RE.findall(target.read_text(encoding="utf-8")))
                want = set(re.findall(r"\d+", m.group("anchor")))
                if not want <= have:
                    missing.append(f"{path}:{lineno}: {m.group('anchor')} not in {target.name}")
    assert missing == [], f"section anchors that do not exist in their target: {missing}"
```

- [ ] **Green — C-12 and C-40, six qualifications.** In each of these six lines, replace the bare
      path with the skill-qualified path (matching how `midjourney-prompting/SKILL.md:36` already
      does it):

| File:line | Replace | With |
|---|---|---|
| `music-brief/SKILL.md:25` | `` `references/production-and-loudness.md` `` | `` `.claude/skills/voiceover-brief/references/production-and-loudness.md` `` |
| `elevenlabs-audio/SKILL.md:32` | same | same |
| `elevenlabs-music/SKILL.md:32` | same | same |
| `shorts-scripting/SKILL.md:76` | `` `references/scripting-beat-mapping.md` `` | `` `.claude/skills/rgs-grounding/references/scripting-beat-mapping.md` `` |
| `rgs-pairing-review/SKILL.md:49` | `` `references/thinker-corpus-protocol.md` `` | `` `.claude/skills/rgs-grounding/references/thinker-corpus-protocol.md` `` |
| `visual-prompts/references/prompt-sheet-format.md:120` | `` `references/prompt-architecture.md` `` | `` `.claude/skills/midjourney-prompting/references/prompt-architecture.md` `` |

- [ ] **Green — C-41, fourteen requalifications then a deletion.** Rewrite every citation of
      `visual-registers.md` inside `visual-prompts/` to the qualified path
      `` `.claude/skills/shorts-styleboard/references/visual-registers.md` ``, keeping each
      citation's existing `§` anchor unchanged:

```
visual-prompts/references/prompt-sheet-format.md:3     (no anchor)
visual-prompts/references/prompt-sheet-format.md:182   §2
visual-prompts/references/visual-arc.md:3              (no anchor)
visual-prompts/references/visual-arc.md:50             §3–§5
visual-prompts/references/visual-arc.md:120            §2, §4
visual-prompts/references/visual-arc.md:164            §2
visual-prompts/references/worked-example.md:6          (no anchor)
visual-prompts/references/worked-example.md:65         §8
visual-prompts/references/worked-example.md:74         §3–§4
visual-prompts/references/worked-example.md:116        §6
visual-prompts/references/worked-example.md:214        §3
visual-prompts/references/worked-example.md:238        §2
visual-prompts/SKILL.md:53                             (rewritten by T9)
visual-prompts/SKILL.md:337                            (rewritten by T9)
```

- [ ] Then **delete `.claude/skills/visual-prompts/references/visual-registers.md`** — the 13-line
      tombstone. With every citation qualified, a bare `visual-registers.md` in `visual-prompts/`
      must now fail loudly rather than land on a redirect. Removing the file is what makes the
      C-55 test meaningful for that basename.
- [ ] Confirm the anchor test passes: `shorts-styleboard/references/visual-registers.md` must
      contain `## 2.`…`## 8.` headings. If a cited anchor genuinely does not exist there, that is
      a real gap — fix the citation to the anchor that does, never add an empty heading to satisfy
      the test.
- [ ] Commit: `fix(skills): qualify every cross-skill citation and delete the registers tombstone`.

---

### T15 — Provenance: triage first, then enforce

Closes **C-42**, **C-43**, **C-48**, **C-54**, **F-22**. **This is the task that must not become a
mass edit.**

#### The triage, done before any marker is added

`docs/README.md:56` says `[C]` is the default and "usually unmarked", scoped to the corpus
document. `CLAUDE.md:53` says a skill rule with no marker is a bug, scoped to skills. Those two
sentences are in genuine conflict; resolving the wording is P14's (see §6). What P13 can do is
stop treating one number as one bug count.

Measured over `.claude/skills/**` with the definition the test will use — a line outside a fence
whose stripped form starts with `- **` — there are **533 blocks, 367 of them unmarked**. (The
audit's broader definition gives 655/329; the two agree in shape.) Triaged:

| Category | Blocks | Disposition |
|---|---|---|
| **3 — declared alternative vocabulary** (both RGS skills) | **113** | Exempt via a declared-vocabulary registry, not by silence. `rgs-grounding/SKILL.md:32-33` already declares `[THINKER:]`/`[RESEARCH:]`; `social-repurpose` declares `[C→I]` and `[gap]`. Record both in the test. |
| **2a — illustrative worked examples** (9 files) | **27** | One header disclaimer per file (C-54 policy below); no per-line markers. |
| **2b — structural pointers** (bullets under `## Reference files`, `## Citation index`, `## Pipeline position`, `## File I/O contract`) | **12** | Not normative claims. Exempt by section, recorded in the test. |
| **1 — genuine skill-side gaps** | **215** | Real. Split in two tiers below. |

**215 is the real bug count** — consistent with the audit's stated upper bound of ≤213 once RGS's
declared vocabulary is subtracted. It splits:

- **~48 modal craft rules** (contain must / never / always / only / instead / default). These need
  a *sourced* marker: `[C]` with a `(Channel, video_id)`, `[T]` with a date, or `[I]` — and if
  none applies, the rule is deleted or rewritten as an explicit gap flag. Concentrations:
  `midjourney-prompting/references/v82-model-delta.md` (5),
  `shorts-scripting/references/{endings-and-ctas,retention-loops-and-structure}.md` (3 each),
  `visual-prompts/references/faceless-pacing-rules.md` (3).
- **~167 definition / taxonomy / format lines** (e.g. `visual-arc.md:48-74`'s column definitions,
  `prompt-sheet-format.md`'s field list). These take `[I]` by policy — they are this skill's own
  operational design, which is exactly what `[I]` means. This tier is a mechanical pass and is
  safe to do file by file.

**Never bulk-apply `[I]` across the whole 215.** Do tier 2 first (mechanical, per file, allowlist
shrinks by one file per commit), then tier 1 by hand.

- [ ] **Red.** Add the triage ledger and the marker test. The ledger starts holding every
      currently-unmarked file, so the suite is green on day one and the gap is *recorded* rather
      than hidden — then each subsequent commit deletes one line from it.

```python
# --- Provenance triage (audit C-42/C-43/C-54) -------------------------------
# Three categories, decided once, recorded here. Shrink TIER_1_PENDING; never grow it.

ALTERNATIVE_VOCABULARY = {
    # skill -> the marker tokens it declares in place of [C]/[I]/[T]
    "rgs-grounding": (r"\[THINKER:", r"\[RESEARCH:", r"\[REF\]", r"\[B\]"),
    "rgs-pairing-review": (r"\[THINKER:", r"\[RESEARCH:", r"\[REF\]", r"\[B\]"),
    "social-repurpose": (r"\[C→I\]", r"\[gap\]"),
}

STRUCTURAL_SECTIONS = (
    "reference files", "citation index", "pipeline position",
    "file i/o contract", "handoff contract (machine-checked)", "reference map",
)

WORKED_EXAMPLE_DISCLAIMER = (
    "This example illustrates rules already marked in this skill's other reference files "
    "and carries no independent normative weight."
)

# Files whose tier-1 blocks are not yet marked. One line deleted per commit.
# Format: relative posix path -> (unmarked block count at triage time, note)
TIER_1_PENDING: dict[str, tuple[int, str]] = {
    # seeded from the T15 measurement run; see the plan's triage table
}
```

```python
def _vocabulary_re(skill: str) -> re.Pattern:
    extra = ALTERNATIVE_VOCABULARY.get(skill, ())
    return re.compile("|".join((MARKER_RE.pattern, *extra)))


def normative_blocks(path: Path) -> list[tuple[int, str]]:
    """A normative block is a `- **…` bullet outside a fence and outside a structural section."""
    blocks, section = [], ""
    for lineno, line in strip_fences(path.read_text(encoding="utf-8")):
        stripped = line.strip()
        if stripped.startswith("#"):
            section = stripped.lstrip("#").strip().lower()
            continue
        if section in STRUCTURAL_SECTIONS:
            continue
        if stripped.startswith("- **"):
            blocks.append((lineno, stripped))
    return blocks


@pytest.mark.parametrize("skill", ALL_SKILLS)
def test_every_normative_block_carries_a_marker_or_a_recorded_exemption(skill):
    """CLAUDE.md: 'a skill rule with no marker is a bug'. This test makes that true, or
    makes the exemption explicit and countable."""
    pattern = _vocabulary_re(skill)
    failures = []
    for path in [skill_md(skill), *reference_files(skill)]:
        rel = path.relative_to(REPO).as_posix()
        if path.name == "worked-example.md":
            continue  # covered by the disclaimer test below
        unmarked = [f"{rel}:{n}" for n, text in normative_blocks(path)
                    if not pattern.search(text)]
        if not unmarked:
            assert rel not in TIER_1_PENDING, (
                f"{rel} is clean — delete its TIER_1_PENDING entry"
            )
            continue
        if rel in TIER_1_PENDING:
            continue
        failures.extend(unmarked)
    assert failures == [], f"unmarked normative blocks with no recorded exemption: {failures}"


@pytest.mark.parametrize("skill", ALL_SKILLS)
def test_every_worked_example_states_its_normative_status(skill):
    """C-54: shorts-assembly instructs copying the worked example's structure verbatim, so
    an unmarked example is the template every emitted artifact inherits."""
    example = SKILLS / skill / "references" / "worked-example.md"
    if not example.exists():
        return
    assert WORKED_EXAMPLE_DISCLAIMER in example.read_text(encoding="utf-8"), (
        f"{skill}/references/worked-example.md must carry the worked-example disclaimer verbatim"
    )


@pytest.mark.parametrize("skill", RGS_SKILLS)
def test_rgs_skills_do_not_carry_stray_corpus_markers(skill):
    """C-43: five stray [C]/[I]/[T] tokens survive inside skills that declare they use a
    different vocabulary, so the boundary is not clean either."""
    allowed_lines = {
        # the disclaimer that *names* the corpus markers, and cross-references to another
        # skill's marked rule, are legitimate. Everything else is a leak.
        ".claude/skills/rgs-grounding/SKILL.md": {34},
        ".claude/skills/rgs-grounding/references/scripting-beat-mapping.md": {18, 19},
    }
    stray = []
    for path in [skill_md(skill), *reference_files(skill)]:
        rel = path.relative_to(REPO).as_posix()
        ok = allowed_lines.get(rel, set())
        for lineno, line in strip_fences(path.read_text(encoding="utf-8")):
            if MARKER_RE.search(line) and lineno not in ok:
                stray.append(f"{rel}:{lineno}")
    assert stray == [], f"stray corpus markers in an alternative-vocabulary skill: {stray}"
```

- [ ] **Green, step 1 — C-54.** Add this line immediately under the H1 of all nine
      `references/worked-example.md` files (`shorts-ideation`, `shorts-scripting`,
      `social-repurpose`, `visual-prompts`, `voiceover-brief`, `shorts-assembly`, `rgs-grounding`,
      `midjourney-prompting`, `elevenlabs-audio`):

```markdown
> This example illustrates rules already marked in this skill's other reference files and carries
> no independent normative weight. Where a line here restates a rule, the marker lives on the
> rule, not on the illustration — do not copy an unmarked line out of this file into a real brief
> as if it were sourced `[I]`.
```

- [ ] **Green, step 2 — seed `TIER_1_PENDING`.** Run the marker test, capture the per-file failure
      list, and paste it into `TIER_1_PENDING` with each file's count. The suite is green and the
      debt is a countable constant in version control, not a vibe.
- [ ] **Green, step 3 — shrink it, tier 2 first.** One commit per file, largest first. For each:
      apply `[I]` to definition/taxonomy/format lines, hand-source the modal craft lines, delete
      the file's `TIER_1_PENDING` entry, run the suite. Suggested order (unmarked count):
      `rgs-grounding/references/pairing-map.md` is category 3 and needs **no** edit — verify the
      vocabulary regex covers it and it never enters the ledger. Then
      `shorts-scripting/references/retention-loops-and-structure.md` (23),
      `visual-prompts/references/visual-arc.md` (22),
      `shorts-scripting/references/hooks-and-openings.md` (14),
      `midjourney-prompting/references/v82-model-delta.md` (13),
      `shorts-scripting/references/script-intelligence-and-delivery.md` (13),
      `midjourney-prompting/SKILL.md` (11), and so on down.
- [ ] **C-48/F-22 close when `TIER_1_PENDING` is a recorded, shrinking constant and the suite runs
      over 13 skills and 64 reference files** — not when the dict is empty. An empty dict is the
      goal; a *recorded* dict is the fix, because it is what makes the gap impossible to
      reintroduce silently.
- [ ] Commit per file: `docs(<skill>): mark the normative blocks in <file>`.

---

### T16 — Citation form and vendor dating

Closes **C-44**, **C-45**, **C-46**, **C-47**.

- [ ] **Red.** Add three tests:

```python
CORPUS_CITE_RE = re.compile(r"\(([^()]*?,\s*[A-Za-z0-9_-]{6,})\)")
CHANNEL_CITE_RE = re.compile(r"\(\s*[A-Z][A-Za-z0-9 .&'-]+,\s*[A-Za-z0-9_-]{6,}")
VERIFIED_HEADER_RE = re.compile(r"verified\s+20\d\d-\d\d-\d\d", re.IGNORECASE)


def test_every_corpus_marked_normative_block_carries_a_channel_and_video_id():
    """CLAUDE.md defines [C] as 'extracted from a transcript, cited (Channel, video_id)' —
    the citation is constitutive. An uncitable [C] passes a marker-presence test, which is
    worse than being unmarked (audit C-44, 33 blocks; C-45, 26 in one file)."""
    bad = []
    for path in every_markdown_file():
        rel = path.relative_to(REPO).as_posix()
        if rel in C_CITATION_PENDING:
            continue
        for lineno, line in normative_blocks(path):
            if "[C]" not in line:
                continue
            if not CHANNEL_CITE_RE.search(line):
                bad.append(f"{rel}:{lineno}")
    assert bad == [], f"[C] blocks with no (Channel, video_id): {bad}"


def test_every_reference_file_with_tool_facts_carries_a_verification_date():
    """CLAUDE.md defines [T] as 'web-verified, dated'. elevenlabs-audio carries 187 [T]
    lines and a date in 2 of 11 files (audit C-46)."""
    undated = []
    for path in every_markdown_file():
        text = path.read_text(encoding="utf-8")
        if "[T]" not in text:
            continue
        head = "\n".join(text.splitlines()[:12])
        if not VERIFIED_HEADER_RE.search(head):
            undated.append(path.relative_to(REPO).as_posix())
    assert undated == [], f"[T]-carrying files with no dated verification header: {undated}"
```

- [ ] **C-46, the mechanical half.** Add a dated header as line 3 of every `[T]`-carrying
      reference file that lacks one — the nine `elevenlabs-audio/references/*.md` files, the
      `voiceover-brief` files, and `visual-prompts/references/image-to-video.md`. Use the skill's
      own verification date, not today's:

```markdown
> **`[T]` facts in this file were web-verified 2026-07-26** against live ElevenLabs documentation
> and have not been re-checked since. Vendor facts go stale fast — re-verify before relying on a
> parameter range, a model id, or a credit rate `[T]`.
```

For `voiceover-brief/references/*.md` use `2026-07-23`; for
`visual-prompts/references/image-to-video.md` use `2026-07-23` and add that its model-landscape
table is the fastest-staling content in the skill.

- [ ] **C-47.** In `voiceover-brief/references/voice-selection.md:10-12` and
      `channel-voice.md:14-17`, replace `` That voice *is* the channel's identity `[T]` `[I]` ``
      with:

```
That voice *is* the channel's identity `[I]` — a branding judgment, not a platform fact; neither
ElevenLabs nor YouTube publishes it.
```

Both occurrences. The `[C]`-cited default-voice/shadowban finding directly beneath is untouched —
that one is genuinely sourced, and the point of the fix is to stop the branding claim borrowing
its credibility.

- [ ] **C-44 and C-45.** These are backfills, not rewrites, and the corpus index they need
      (`output/brand-intel/`) is git-ignored. Add `C_CITATION_PENDING` beside `TIER_1_PENDING`,
      seeded with the two files that carry the bulk, and close them the same way — one file per
      commit, deleting its ledger entry:
  - `midjourney-prompting/references/prompt-architecture.md:116-119` — the three stylize bands are
    already cited at `parameters.md:36`; copy that citation
    `` `[C] (Future Tech Pilot, Tv1dfGcOSnA / ioJ6istzwHw; Tokenized AI, 1GnipTgvLI0)` `` onto each.
  - `midjourney-prompting/references/parameters.md:43` — `--iw` halving ladder is marked
    `` `[C][T]` `` with neither channel nor date. Either cite it or downgrade to `[I]`; do not
    leave a `[C]` that cannot be checked.
  - `visual-prompts/references/image-to-video.md:96-103` — the model-landscape table's rows cite
    bare ids (`uCsc0ORcJDo`, `4tpDAX23RL0`, `elCv87a4iK4`, `RUAuMD5hUBw`, `gpkbPCrGF6g`,
    `j8ImtURt9-0`, `vezJXJGQMoY`, `MfK-WkKUnKQ`). `prompt-sheet-format.md:123` proves
    `vezJXJGQMoY` is Tokenized AI. Look the rest up in the content index; where a channel cannot
    be recovered, downgrade the row to `[I]` and say the id could not be resolved — never leave a
    `[C]` standing on an id alone.
  - `visual-prompts/references/image-to-video.md:69,85` — `(Tao Prompts)` with no id; the same
    file cites `(Tao Prompts, zzBmvzR-URg)` and five other Tao Prompts ids, so pick the one the
    claim actually comes from or downgrade.
- [ ] Commit: `fix(skills): date every [T] file and give [C] blocks a checkable citation`.

---

### T17 — `docs/style-library.md` is declared state

Closes **C-34**. Three skills share a mutable registry that appears in no declared I/O.
`docs/style-library.md` itself is P11's file — this task changes only the skills' declarations,
which T5/T8/T10's handoff blocks already carry as `reads:`/`writes:` lines.

- [ ] **Red.** Add:

```python
def test_style_library_users_declare_it_in_their_handoff_block():
    """C-34: shorts-styleboard binds slots from it, shorts-assembly resolves slots against
    it at paste time, and midjourney-prompting writes harvested codes into it — with no
    declared owner in any I/O contract and no staleness rule."""
    readers = {"shorts-styleboard", "shorts-assembly", "midjourney-prompting"}
    for skill in readers:
        assert "docs/style-library.md" in handoff(skill)["reads"], (
            f"{skill} reads docs/style-library.md and must declare it"
        )
    assert "docs/style-library.md" in handoff("midjourney-prompting")["writes"], (
        "midjourney-prompting harvests codes into the Library and must declare the write"
    )
```

- [ ] **Green.** The `reads:`/`writes:` lines were added in T5, T8 and T10. Then state the
      staleness rule, which is the substantive half of the finding. Add to
      `shorts-styleboard/SKILL.md` step 3, after the `DISCOVERY REQUESTS` paragraph:

```markdown
**The binding is a label, not a code, and it re-resolves at paste time** `[I]`. A styleboard
records `slot_register_a: <Library entry label>`; `shorts-assembly` looks that label up in
`docs/style-library.md`'s `Entries` section when the prompt is actually pasted. That means a code
harvested *after* this styleboard was approved will be the one that renders. If a Short must pin
the exact code it was approved against, say so explicitly under `BINDINGS` and record the code
there — otherwise the Library is the live authority and the styleboard defers to it.
```

- [ ] Add the mirror sentence to `shorts-assembly/SKILL.md`'s slot-resolution paragraph (`:31-40`),
      after "Pasting the token as literal text renders the words…":

```markdown
**Resolve against the Library at paste time, not against a code copied into the styleboard**
`[I]` — unless that styleboard's `BINDINGS` section explicitly pinned a code, in which case use
the pinned code and say you did.
```

- [ ] Commit: `fix(skills): declare docs/style-library.md as shared state with a resolution rule`.

---

### T18 — Four descriptions that state no negative scope

Closes **C-29**. Nine of thirteen descriptions carry a "Do not use this for X" clause; four do
not, even though all four have a body section stating exactly that boundary.

- [ ] **Red.**

```python
NEGATIVE_SCOPE_RE = re.compile(
    r"(do not use|don't use|does not|doesn't|not for|never use) ", re.IGNORECASE
)


@pytest.mark.parametrize("skill", ALL_SKILLS)
def test_every_description_states_a_negative_scope(skill):
    """Trigger text is what routing matches on, so a boundary stated only in the body is
    invisible at selection time (audit C-29)."""
    text = skill_md(skill).read_text(encoding="utf-8")
    front = text.split("---")[1]
    description = front.split("description:", 1)[1]
    assert NEGATIVE_SCOPE_RE.search(description), (
        f"{skill}'s description states no negative scope; its body already does"
    )
```

- [ ] **Green.** Append to each of the four descriptions, drawn from the body section named:

`shorts-ideation` (from `:58-72`):
```
Do not use this to write opening lines, retention structure, or any scripting mechanic — that is
`shorts-scripting`; this skill hands off a promise and a direction, not a draft.
```

`shorts-scripting` (from `:213-223`):
```
Do not use this to decide the concept, title or thumbnail (that is `shorts-ideation`, upstream),
to set ElevenLabs voice/model settings (`voiceover-brief`), to write image or video prompts
(`visual-prompts`), or to write descriptions, hashtags or chapters (`social-repurpose`).
```

`shorts-assembly` (from `:8`) — appended after T5's replacement trigger sentence:
```
Do not use this for ideation, scripting, voice specs, or visual-asset generation — those are
separate upstream skills — and not for post copy, which is `social-repurpose`, next.
```

`social-repurpose` (from `:15-16`):
```
Do not use this to design a thumbnail or re-derive packaging (that is
`shorts-ideation`/`shorts-assembly`), and do not fill the corpus's cross-platform gap with
invented social-media best practices — mark it and say so.
```

- [ ] Run both suites. Commit: `fix(skills): state the negative scope in all thirteen descriptions`.

---

## 4. Finding → test map

`silent` findings carry the Three-Test roles. For a documentation package the roles read as:
**fault** = the check names the specific broken line; **distinguishability** = the check
separates "declared and absent" from "legitimately not applicable"; **surfacing** = the failing
assertion prints the `file:line` a human can act on. Every test below is in
`tests/test_skill_provenance.py` and runs in the root suite (`python -m pytest tests/ -v`).

| Finding | Mode | Test | Role |
|---|---|---|---|
| C-01 | silent | `test_every_consumed_section_resolves_to_a_declared_producer_section[music-brief]` | fault |
| C-01 | silent | `test_declared_output_sections_appear_in_the_output_template[voiceover-brief]` | distinguishability — a declared-but-absent section fails; a section a skill simply does not produce is never declared |
| C-01 | silent | Same assertion message prints `voiceover-brief#Tone per beat` | surfacing |
| C-02 | docs-drift | `test_every_consumed_section_resolves_to_a_declared_producer_section[shorts-styleboard]` (`consumes: rgs-grounding#Handoff`) | — |
| C-03 | loud | `test_every_consumed_section_resolves_to_a_declared_producer_section[shorts-assembly]` (`shorts-scripting#Total word count` reachable via the VO brief's pointer) | — |
| C-04 | silent | `test_social_repurpose_states_one_input_list` — asserts the description, the body paragraph and the File I/O step each name exactly `script` and `assembly` and nothing else | fault |
| C-04 | silent | Same test asserts the three lists are **equal**, not merely non-empty | distinguishability |
| C-04 | silent | Failure prints all three lists side by side | surfacing |
| C-05 | docs-drift | `test_downstream_list_matches_the_stage_graph` — `shorts-scripting`'s Downstream bullet names every stage whose `depends_on` contains `scripting` in `pipeline.yaml` | — |
| C-06 | docs-drift | `test_every_section_pointer_resolves_in_the_citing_file` — asserts each `see "<Section>" above/below` string is an actual heading in that file | — |
| C-07 | silent | `test_world_lock_key_count_agrees_everywhere` — counts `[a-z_]+:` lines in the styleboard's WORLD LOCK template and asserts every prose statement of the count matches (13) | fault |
| C-07 | silent | Same test asserts `slot_register_a` and `slot_register_b` are both inside the counted block | distinguishability |
| C-07 | silent | Failure names each file:line stating a wrong number | surfacing |
| C-08 | docs-drift | `test_stated_counts_match_the_lists_they_introduce` — parametrized over `(file, line, spelled number, list length)` | — |
| C-09 | docs-drift | `test_stated_counts_match_the_lists_they_introduce[midjourney control surface]` + asserts `register` appears in the CONTROL SURFACE output line | — |
| C-10 | docs-drift | `test_stated_counts_match_the_lists_they_introduce[visual-prompts step 4]` | — |
| C-11 | docs-drift | `test_stated_counts_match_the_lists_they_introduce[shorts-ideation worked example]` | — |
| C-12 | loud | `test_every_bare_reference_citation_resolves_inside_its_own_skill` | — |
| C-13 | silent | `test_elevenlabs_audio_boundary_table_records_the_upstream_inputs` — asserts the three review rows exist and that "do not re-litigate" is scoped to the four decided rows | fault |
| C-13 | silent | Same test asserts `voiceover-brief`'s mirror sentence names the same three | distinguishability |
| C-13 | silent | Failure names the missing row | surfacing |
| C-14 | silent | `test_every_description_states_a_negative_scope` + `test_voiceover_and_audio_descriptions_are_disjoint` — asserts no phrase of ≥4 words appears in both descriptions | fault |
| C-14 | silent | The disjointness assertion distinguishes overlap from mere topical similarity | distinguishability |
| C-14 | silent | Failure prints the shared phrase | surfacing |
| C-15 | silent | `test_no_description_advertises_a_trigger_it_disclaims` — for each skill, no trigger-list phrase may also appear in its "Does NOT" sentence | fault / distinguishability / surfacing |
| C-16 | latent | `test_every_consumed_section_resolves_to_a_declared_producer_section[elevenlabs-music]` + a substring assertion that Gate 1's tone item names `## Tone-contradiction check` | — |
| C-17 | loud | `test_pipeline_mode_style_lock_emits_a_slot_not_a_code` — asserts the mapping table has a pipeline row naming `{style:` and that Gate A's checklist mentions it | — |
| C-18 | silent | `test_every_consumed_section_resolves_to_a_declared_producer_section[shorts-assembly]` (would fail on `voiceover-brief#pacing wpm`) | fault |
| C-18 | silent | Distinguishes "section absent" from "section present but empty" — declaration is structural, not content-based | distinguishability |
| C-18 | silent | Failure prints the edge | surfacing |
| C-19 | latent | `test_every_declared_downstream_names_a_reciprocal_input` — if A declares B downstream, B's handoff must `consumes: A#<section>` | — |
| C-20 | latent | `test_the_owning_skill_declares_the_registry_kind_and_stage` for `audio-spec`/`music-spec`; `test_transcript_only_skills_say_so` for `midjourney-prompting` | — |
| C-21 | silent | `test_declared_output_sections_appear_in_the_output_template[shorts-assembly]` | fault |
| C-21 | silent | `test_every_consumed_section_resolves_to_a_declared_producer_section[social-repurpose]` — proves the section `social-repurpose` parses actually exists | distinguishability |
| C-21 | silent | Failure names the missing heading | surfacing |
| C-22 | loud | `test_every_kind_flag_in_every_skill_is_in_the_registry` + `test_the_registry_matches_the_declared_stage_graph` | — |
| C-23 | latent | `test_the_owning_skill_declares_the_registry_kind_and_stage[grounding]` | — |
| C-24 | latent | `test_voiceover_brief_does_not_chase_upstream_pointers` — asserts the unconditional pointer-chase string is gone and the conditional replacement is present | — |
| C-25 | latent | `test_every_consumed_section_resolves_to_a_declared_producer_section[music-brief]` — the edge is `voiceover-brief#Tone per beat`, not the whole artifact | — |
| C-26 | silent | `test_styleboard_can_resolve_every_source_step_1_requires` — every source named in step 1 has a resolve step in the File I/O contract | fault |
| C-26 | silent | Asserts `NONE` is documented as legitimate, so "not produced" ≠ "not checked" | distinguishability |
| C-26 | silent | Failure names the unreachable source | surfacing |
| C-27 | docs-drift | `test_no_skill_instructs_writing_into_another_skills_artifact` — grep for "prompt sheet" in `shorts-styleboard` outside its Pipeline-position section | — |
| C-28 | docs-drift | `test_every_bare_reference_citation_resolves_inside_its_own_skill` (the tombstone is gone, so the old claim cannot be restated) + a substring assertion that the ownership paragraph names `shorts-styleboard` | — |
| C-29 | silent | `test_every_description_states_a_negative_scope` | fault / distinguishability / surfacing |
| C-30 | docs-drift | `test_every_section_pointer_resolves_in_the_citing_file` (the pointer now names "step 4's delegation block", which exists) | — |
| C-31 | docs-drift | `test_gate_labels_agree_across_skills` — the VALIDATION block's Gate B label must contain `midjourney-prompting` and `production` | — |
| C-32 | docs-drift | `test_every_plan_reference_names_a_path` — a citation index entry may not say "the implementation plan" without a `docs/superpowers/plans/` path | — |
| C-33 | coverage-gap | `test_rgs_pairing_review_is_reachable` — `rgs-grounding` must name `rgs-pairing-review`, and `rgs-pairing-review` must state it is outside the staged pipeline | — |
| C-34 | latent | `test_style_library_users_declare_it_in_their_handoff_block` | — |
| C-35 | silent | `test_description_names_every_hard_required_input` — every input the body hard-blocks on must appear in the description | fault |
| C-35 | silent | Asserts the optional fourth is described as optional, distinguishing it from the three | distinguishability |
| C-35 | silent | Failure prints the missing input | surfacing |
| C-40 | docs-drift | `test_every_bare_reference_citation_resolves_inside_its_own_skill` | — |
| C-41 | silent | `test_every_section_anchor_resolves_in_the_file_it_points_at` | fault |
| C-41 | silent | Distinguishes "file exists but anchor does not" from "file missing" — the exact gap that let 10 citations resolve into a tombstone | distinguishability |
| C-41 | silent | Failure prints `citing_file:line: §N not in target.md` | surfacing |
| C-42 | silent | `test_every_normative_block_carries_a_marker_or_a_recorded_exemption` | fault |
| C-42 | silent | `TIER_1_PENDING` makes "unmarked and known" different from "unmarked and undetected"; the `assert rel not in TIER_1_PENDING` branch fails when a file is cleaned but its entry survives | distinguishability |
| C-42 | silent | Failure prints every `file:line` | surfacing |
| C-43 | docs-drift | `test_rgs_skills_do_not_carry_stray_corpus_markers` + `ALTERNATIVE_VOCABULARY` covering both RGS skills | — |
| C-44 | latent | `test_every_corpus_marked_normative_block_carries_a_channel_and_video_id` | — |
| C-45 | latent | Same test; `image-to-video.md` leaves `C_CITATION_PENDING` when its rows are fixed | — |
| C-46 | silent | `test_every_reference_file_with_tool_facts_carries_a_verification_date` | fault |
| C-46 | silent | Distinguishes "undated" from "no `[T]` facts at all" — the test skips files with no `[T]` | distinguishability |
| C-46 | silent | Failure lists every undated file | surfacing |
| C-47 | latent | `test_branding_claims_are_not_marked_as_tool_facts` — asserts `channel's identity` never appears on a line carrying `[T]` | — |
| C-48 | coverage-gap | `test_every_skill_directory_is_classified` + the parametrized marker test over all 13 skills | — |
| C-54 | silent | `test_every_worked_example_states_its_normative_status` | fault |
| C-54 | silent | Nine parametrized cases distinguish per-file compliance from a single global claim | distinguishability |
| C-54 | silent | Failure names the file | surfacing |
| C-55 | latent | `test_a_duplicated_reference_filename_is_never_cited_bare_across_skills` | — |
| B-84 | coverage-gap | `test_no_skill_reads_an_unproduced_output_path` — no `.claude/skills/**` file may cite `output/raisinggoodsports-brand-definition.md` outside a line containing the words "historical provenance" | — |
| F-22 | docs-drift | `test_every_skill_directory_is_classified` + the suite's own parametrization count (13 skills × the marker test, 64 reference files × the citation tests) | — |

---

## 5. Tests deleted or inverted

**None deleted. None inverted.** Checked all six existing tests in
`tests/test_skill_provenance.py` against the anti-tautology rules:

| file:line | Verdict | Reason |
|---|---|---|
| `tests/test_skill_provenance.py:39-40` `test_the_register_system_still_lives_with_styleboard` | **Kept** | Asserts an effect (file location), not an echoed literal. Still correct after T14 deletes the *other* skill's tombstone — and becomes load-bearing, since the qualified citations all target this path. |
| `tests/test_skill_provenance.py:43-48` `test_the_register_system_is_still_marked_as_this_skills_own_design` | **Kept** | Asserts the `[I]` disclaimer survives; C-28's fix makes the same claim in `visual-prompts`, so this now pins one half of a two-file invariant. |
| `tests/test_skill_provenance.py:51-57` `test_the_corpus_gap_disclaimer_survives_the_generic_thin_clause` | **Kept** | Independently-required clause; the docstring at `:18-36` already explains why an `A|B` regex would be the wrong shape. Good test. |
| `tests/test_skill_provenance.py:60-72` `test_the_corpus_gap_disclaimer_survives_the_register_specific_clause` | **Kept** | Same. |
| `tests/test_skill_provenance.py:75-86` `test_register_contract_bullets_all_carry_a_marker` | **Kept, and generalised** | Not defect-affirming — it is correct but narrow (13 of 655 blocks). T15's parametrized `test_every_normative_block_carries_a_marker_or_a_recorded_exemption` subsumes it. Keep it: it pins the specific `## 3. Register A` → `## 5. PLATE` slice by its split points, which the general test does not, and it is the named regression for the design-document claim in the module docstring. |
| `tests/test_skill_provenance.py:89-91` `test_styleboard_skill_does_not_claim_corpus_backing_for_the_register_system` | **Kept** | Asserts an exact substring in `shorts-styleboard/SKILL.md`. T9's C-28 fix adds the reciprocal claim in `visual-prompts`; add a sibling assertion there rather than replacing this one. |

**One defect changed in place, not a test:** `tests/test_skill_provenance.py:16` — `MARKER_RE`
omits `[P]`, so a correctly-`[P]`-marked bullet inside the guarded slice would fail. Fixed in T1
under a new test (`test_marker_re_accepts_the_project_decision_marker`) that fails first.

**Nothing renamed.** C-48 proposes renaming the module. Rejected: once T15 lands the name is
accurate, and a rename would force an edit to `CLAUDE.md:236-241`, which is P14's file.

---

## 6. Contracts

### 6.1 Contract for P14 — the provenance-wording conflict

Two sentences in two P14-owned files contradict each other, and P13 cannot resolve it because it
owns neither file.

- **`docs/README.md:56`** — `[C]` is the "default; **usually unmarked** in the audit".
- **`CLAUDE.md:53`** — "a skill rule with no marker is a bug: it means something was invented
  instead of sourced."

They are individually correct and differently scoped: the first to `docs/` (the corpus document,
where `[C]` genuinely is the default), the second to `.claude/skills/**`. Nothing says so. The
audit's 329-of-655 number is the cost of that ambiguity: it reads as 329 bugs under CLAUDE.md and
as ~0 under `docs/README.md`, and neither reading is true.

**P13 asks P14 for three edits. P13 will not make them.**

1. **Scope both sentences explicitly.** In `docs/README.md`, change the provenance-key line to say
   the unmarked-`[C]` default applies **to `docs/*.md` only**, and that skills under
   `.claude/skills/**` require an explicit marker on every normative block. In `CLAUDE.md`, add
   the reciprocal half-sentence so a reader of either file learns the boundary from that file.

2. **Name the alternative vocabularies.** `CLAUDE.md`'s marker section scopes the anti-generic
   guarantee to "the eight pipeline skills" and "the tool-specialist skills" and never mentions
   the two RGS skills. Add a sentence naming `rgs-grounding` and `rgs-pairing-review` and their
   `[THINKER:]` / `[RESEARCH:]` / `[REF]` / `[B]` / `[C→I]` vocabulary as a declared substitute,
   not an exemption. P13 encodes the same list in `ALTERNATIVE_VOCABULARY` in
   `tests/test_skill_provenance.py` — the two must agree, and the test is the machine-readable
   copy. `social-repurpose`'s `[C→I]` and `[gap]` markers need the same treatment.

3. **Record the worked-example policy.** P13's T15 applies one policy to all nine
   `references/worked-example.md` files: a header disclaimer, no per-line markers. `CLAUDE.md`'s
   marker section should state it in one sentence so the next skill author does not re-litigate
   it. The exact disclaimer string lives in `WORKED_EXAMPLE_DISCLAIMER` in the test module.

**P14 should also note** that `tests/test_skill_provenance.py` is deliberately **not** renamed
(C-48 proposed it), so `CLAUDE.md:236-241`'s "the linters and skill provenance" phrasing stays
correct — and becomes true rather than aspirational once T15 lands.

### 6.2 Contract for P4 — the stage graph binds to the handoff block

P4 owns `pipeline.yaml` and the stage graph, and may need SKILL.md input/output declarations to
change so the declared graph matches the reachable one. P13 makes that machine-checkable:

- Every `SKILL.md` carries a ```` ```handoff ```` fenced block under
  `## Handoff contract (machine-checked)`. Format and parser are specified in **T2**; the parser
  (`handoff()` in `tests/test_skill_provenance.py`) is stdlib-only and importable.
- `KIND_REGISTRY` in `tests/test_skill_provenance.py` is the single mapping between
  `pipeline.yaml` stage ids, `--kind` strings, `stage:` frontmatter values and owning skills.
  `test_the_registry_matches_the_declared_stage_graph` reads `pipeline.yaml` **read-only** and
  fails if P4 adds, removes or renames a stage without updating the registry. P4 should update
  `KIND_REGISTRY` in the same commit as any stage-graph change — that is the only P13-owned line
  P4 needs to touch, and it is the intended coupling point.
- **P13 does not rename any `--kind` string** (T13's rationale: the resolver matches filenames
  literally and ~40 artifacts already exist under the current names). If P4 concludes the
  vocabulary must be unified on stage ids, that is a filename migration of `rgs-briefs/` — P14's
  files — and needs its own task in P4's plan, not a P13 edit.
- **One open item P4 must decide (C-03):** `assembly` is `depends_on: [voiceover, visual]`, so the
  script is not in `input_files`. T5 resolves it on the skill side by routing the script through
  the voiceover brief's `script:` pointer. If P4 instead adds `scripting` to `assembly`'s
  `depends_on`, T5's "Input 2 in app-driven mode" paragraph becomes wrong and must be simplified
  to a direct read. P13 should be re-run on that one paragraph if P4 takes that route.

---

## 7. Verification

The package is done when all of these hold:

```bash
python -m pytest tests/ -q
```

(This section originally hardcoded a specific worktree path in the `cd`, which the master plan's
own §Verification explicitly warns against — worktrees are created and torn down per package and
that path is long gone. Run this from whatever worktree's repo root you're actually in.)

1. `tests/test_skill_provenance.py` is parametrized over **13 skills** and sweeps **all 64
   reference files** (63 after T14 deletes the tombstone) — verified by
   `test_every_skill_directory_is_classified` and the citation tests' file sweep.
2. Every `SKILL.md` carries a ```` ```handoff ```` block, and both handoff tests are green for all
   13 skills.
3. `grep -rn "references/production-and-loudness.md" .claude/skills/` returns only
   skill-qualified paths.
4. `.claude/skills/visual-prompts/references/visual-registers.md` does not exist, and
   `grep -rn "visual-registers.md" .claude/skills/visual-prompts/` returns only qualified paths.
5. `TIER_1_PENDING` and `C_CITATION_PENDING` are present, non-hidden, and strictly smaller than
   their seeded values; every entry that reaches zero unmarked blocks has been deleted (the test
   fails if a clean file keeps its entry).
6. `python scripts/lint_prompt_sheet.py` (P11) and `python scripts/lint_script_language.py` (P12)
   still pass on the committed `rgs-briefs/` artifacts — no skill edit here changes a format either
   linter parses.
7. `bash scripts/build-cowork-plugin.sh` (P12) runs clean, since `.claude/skills/` is its input.
