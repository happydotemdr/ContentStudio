# ContentStudio — Eval Suite + Artifact I/O Boundary Design

**Status:** Approved design, ready for implementation planning.
**Scope:** Adds two things to ContentStudio's existing six-skill pipeline
(`shorts-ideation` → `shorts-scripting` → {`voiceover-brief`, `visual-prompts`} →
`shorts-assembly` → `social-repurpose`):

1. A file-based **artifact system** with harness-enforced read/write boundaries between
   pipeline stages, so a skill can't accidentally edit an upstream stage's output.
2. An **eval suite** covering all six skills, testing whether each skill actually grounds
   its output in the corpus rather than falling back on generic content-creation advice.

Both are dev-time / project-infrastructure additions. Neither changes what a skill
produces when a human runs it normally — the artifact system adds a file format and a
locking convention around outputs that already exist today (concept briefs, scripts,
briefs, prompt sheets, edit plans, post copy); the eval suite is a separate harness that
exercises the skills, it is not something an end-user invocation ever triggers.

This spec has no code in it. It is the reference the implementation plan is built from.

---

## 1. Artifact layout, frontmatter, and versioning

### 1.1 Layout

```
runs/<run_id>/NN-<stage>/artifact.vN.md
```

- `run_id` = `<slug>-<YYYYMMDD-HHMMSS>` (e.g. `coffee-bloom-trick-20260724-1142`).
  The run directory name **is** the run_id, so two runs can never collide even if
  started in the same second on the same slug (the timestamp component still
  differentiates by second; a slug collision within the same second is not a
  design concern for a single-human local tool).
- `NN-<stage>` numbers the pipeline stage directories in topological order, e.g.
  `01-ideation/`, `02-scripting/`, `03-voiceover/`, `03-visual/` (both stage 3
  siblings share numeric prefix 03 since they run in parallel off the same
  upstream — see fan-out note in 1.3), `04-assembly/`, `05-repurpose/`.
- `artifact.vN.md` — `N` starts at 1 and increments per revision within a stage
  directory. A stage directory may contain more than one artifact basename if a
  skill's output is naturally split (out of scope to enumerate here; the
  implementation plan's file-structure task decides this per skill).
- `runs/` lives inside the repo root and is **gitignored** — same precedent as the
  existing `output/` corpus-download directory (see `CLAUDE.md`).

### 1.2 Frontmatter

Every artifact file begins with YAML frontmatter:

```yaml
---
schema_version: 1
run_id: coffee-bloom-trick-20260724-1142
stage: shorts-ideation
version: 1
status: draft            # draft while being written, final once locked
created_at: 2026-07-24T11:42:00Z
finalized_at: null
supersedes: null          # set ONLY on the NEW file when creating v2+; the old file is NEVER mutated
depends_on: []             # [{path: "../01-ideation/concept-brief.v1.md", sha256: "..."}] — exact version + hash of upstream inputs actually used
source_corpus_docs: [docs/headless-youtube-audit.md]
marker_counts: {C: 41, I: 0, T: 0}   # separate counts per marker, not one total — so invented [I]/[T] claims are catchable too
t_verified: null           # date [T] facts were last checked; only relevant if T>0
---
```

Field notes:

- `depends_on` records the **exact version and content hash** of every upstream
  artifact this artifact actually drew from — not just "the ideation stage" but
  the specific file (`concept-brief.v1.md`) and its sha256 at the time it was
  read. This is what lets `verify-run.sh` (§2.6) detect drift: if an upstream
  file's current hash no longer matches what a downstream artifact recorded, the
  downstream artifact was built against content that has since changed underneath
  it.
- `marker_counts` is a breakdown, not a total, because the point of counting is to
  cross-check against a real grep of the body (§2.2 step 1) — a single total
  can't catch "this artifact claims 0 `[T]` markers but the body has three."
- `t_verified` is only meaningful when `marker_counts.T > 0`; otherwise it stays
  `null`.

### 1.3 Versioning rules (final, no exceptions)

- **Revision = always a new version file.** Producing a corrected or updated
  artifact means writing `concept-brief.v2.md` with `supersedes:
  concept-brief.v1.md` set **in the new file only**. The old file (`v1`) is never
  mutated again once finalized — no back-editing its frontmatter, no
  `superseded_by` pointer added to it, no unlock mechanism of any kind. An
  earlier draft of this design had a `superseded_by` back-edit exception for the
  old file; it was correctly identified as a loophole (an old "final" file that
  can still be legally written to is not actually final) and removed. Do not
  reintroduce it in any form, including partial variants (e.g. "only the
  `superseded_by` field is unlockable").
- **Static pipeline topology lives once**, in a repo-root `pipeline.yaml`, not
  duplicated into every artifact's frontmatter. It records which skill produces
  which stage and that stage's downstream consumer(s). The real topology has a
  fan-out: `shorts-scripting`'s output is consumed by **both**
  `voiceover-brief` and `visual-prompts` in parallel, and both of those feed
  `shorts-assembly`. This is not a linear chain, and `pipeline.yaml` is the one
  place that shape is recorded — artifact frontmatter only needs to know its own
  `depends_on` list, not the whole graph.

---

## 2. Enforcement mechanics

### 2.1 Manifest

`runs/<run_id>/manifest.yaml` is the single source of truth, serving double duty:

1. **Eval tracking** — stage → artifact → status, used to detect a skipped or
   out-of-order stage during an eval run.
2. **Enforcement** — the hook's "what's locked" lookup (§2.3).

**Single-writer rule:** `manifest.yaml` is written **only** by
`scripts/finalize-artifact.sh` (§2.2), and always atomically (write to a temp
file, then rename over the target — never an in-place partial write). Eval
tooling **reads** the manifest but writes its own separate `eval-report.yaml`;
it never writes into `manifest.yaml`.

Manifest entries are kept in **flow-style YAML**, one line per artifact
(`{path: "...", stage: "...", status: "final", sha256: "..."}`), specifically so
the enforcement hook (§2.3) can `grep`/pattern-match it directly instead of
needing a full YAML parser in a Bash hook.

### 2.2 Finalize script

`scripts/finalize-artifact.sh <path>`:

1. **Validate.**
   - Does `marker_counts` in the frontmatter match a real grep of the artifact
     body (count of `[C]`, `[I]`, `[T]` occurrences)?
   - Do the hashes in `depends_on` actually match the current content of the
     referenced upstream files?
   - Are all required frontmatter fields present?
2. **If valid:**
   1. Stamp `status: final` and `finalized_at: <timestamp>` into the artifact's
      **own** frontmatter.
   2. Compute the artifact's sha256 **after** that stamping step, not before.
      This ordering is load-bearing: a downstream artifact's `depends_on` hash
      check (step 1 above, run against *this* artifact once it becomes someone
      else's upstream input) must match the file's finalized content, hash
      included. Hashing before stamping would mean every downstream
      `depends_on` check fails forever, because the recorded hash would never
      match the actual finalized file on disk.
   3. Apply OS-level locking (§2.4).
   4. Append the manifest entry **last**, after locking succeeds. This ordering
      is also load-bearing: if the script crashes between locking and the
      manifest write, the failure mode is an over-locked-but-unrecorded file
      (annoying, discoverable, safe) — never the reverse (a manifest claiming a
      file is locked when it isn't).
3. **If validation fails:** exit nonzero, nothing locks, nothing is written to
   the manifest.

### 2.3 Hook

`.claude/hooks/protect-finalized.sh` is a `PreToolUse` hook.

- **Matcher** must cover `Write|Edit|MultiEdit|NotebookEdit` **and** the
  filesystem MCP tools `mcp__filesystem__write_file|edit_file|move_file`. A
  matcher scoped only to the three built-in tools has a real coverage gap in
  this environment — the filesystem MCP tools bypass it entirely and must be
  matched explicitly.
- **Path canonicalization is required before comparison.** Tool calls arrive as
  absolute Windows backslash paths; the manifest stores relative forward-slash
  paths. The hook must normalize both representations to a common form before
  checking the target path against the manifest — comparing the raw strings
  will never match and the hook will silently fail to protect anything.
- **Behavior:** if the target path's manifest entry has `status: final`, block
  the write/edit and return a message pointing at the correct fix: *"this
  artifact is finalized — create a new version file instead."*
- **Explicit non-coverage:** the hook does **not** attempt to parse Bash tool
  calls for redirection targets (`>`, `>>`, `cp`, heredocs). That's fragile
  (quoting, variable expansion, heredoc bodies) and is deliberately left to the
  OS-level backstop instead (§2.4).

### 2.4 OS-level backstop — ACLs, not `attrib +R`

**This is the one piece of the design that was empirically tested, not just
reasoned about, and the tested result overrides the more obvious-looking
alternative.**

An earlier draft proposed `attrib +R` (Windows' read-only file attribute) as the
backstop beneath the hook. Live testing on the actual machine showed this is
**not real protection**: `attrib +R` blocks `>>` redirection and `cp`, but plain
`rm` (no `-f` needed), `mv`-over-target, or `sed -i` (which works by
temp-file-then-rename, not in-place write) all silently bypass it. Worse,
`attrib -R` is exactly the reflex an agent has after seeing "Permission
denied" — the "protection" actively invites its own removal.

The verified, working replacement — Windows ACL deny rules via `icacls`:

```bash
MSYS2_ARG_CONV_EXCL="*" icacls "$file" /deny "*S-1-1-0:(DE,WD,AD,WA)"
MSYS2_ARG_CONV_EXCL="*" icacls "$stage_dir" /deny "*S-1-1-0:(DC)"
```

- `S-1-1-0` is the well-known "Everyone" SID — the deny applies regardless of
  which Windows account is running.
- The file-level deny (`DE,WD,AD,WA` = delete, write data, append data, write
  attributes) blocks deleting or modifying the file itself.
- The directory-level deny (`DC` = delete child) blocks deleting the file via
  its parent directory, which is a separate Windows permission from deleting
  the file directly — both are needed or `rm` still succeeds via the parent.
- `MSYS2_ARG_CONV_EXCL="*"` is required. Without it, Git Bash's automatic
  path-mangling rewrites `/deny` into a bogus path and the command fails with
  exit code 87.
- Live-tested and confirmed: `rm`, `mv`-over, `sed -i`, and `attrib` are all
  blocked against the doubly-denied file. New version files and other unlocked
  drafts in the same directory are unaffected — only the specific artifact that
  went through both denies becomes immovable.

**`docs/` gets the same treatment, once, as a repo-setup step (not per-run).**
Static `settings.json` deny rules already protect the corpus permanently, but
they have the identical NotebookEdit/MCP-filesystem blind spot the hook does —
so the same icacls treatment is applied to `docs/` a single time during repo
setup, independent of any per-run artifact locking.

### 2.5 No unlock path — by design, not by omission

There is no unlock/relock mechanism anywhere in this design. Versioning-by-new-
file (§1.3) means there is never a legitimate reason to reopen a locked file —
if content needs to change, a new version file is the answer. This eliminates
the entire class of edge case where boundary-enforcement systems usually
accumulate leaks (a debug escape hatch, an admin override, a "just this once").
Do not add one during implementation, even for testing convenience — the eval
harness's structural-tier teardown (§3.4) resets ACLs on the whole file rather
than unlocking-then-relocking it.

### 2.6 Verification backstop

`scripts/verify-run.sh` re-hashes every artifact the manifest marks `final` and
compares against the recorded hash. This is the honest answer to "what if
something slips past both the hook and the ACLs" — a cheap, explicit,
end-of-run detection layer rather than a claim of prevention.

### 2.7 Explicit non-goal

This system defends against **accidental cross-contamination** — an agent
drifting into "helpfully" editing an upstream artifact instead of flagging that
a re-run is needed. It is **not** a security sandbox against a deliberately
adversarial agent. Nothing stops an agent from hand-editing `manifest.yaml`
directly instead of running `finalize-artifact.sh`, bypassing the whole chain.
That gap is intentional and consistent with how the rest of ContentStudio
already works: the project trusts citation discipline (the `[C]`/`[I]`/`[T]`
marker system) rather than cryptographically enforcing it, and this extends the
same trust model to pipeline boundaries.

### 2.8 Portability caveat

Hooks, `settings.json` deny rules, and OS ACLs are all Claude-Code-specific and
do **not** travel into the Cowork plugin build
(`scripts/build-cowork-plugin.sh` only ships `.claude/skills/` into
`cowork-plugin/skills/`). Cowork users get the same skill instructions as a
soft convention — the artifact format and versioning rules still apply as
guidance in the skill text — but without the technical backstop described in
this section.

---

## 3. Eval suite

### 3.1 Purpose and shape

Tests whether each of the six skills actually grounds its output in the
ContentStudio corpus, rather than quietly falling back on generic
content-creation advice when the corpus is thin or the user pushes back. This
directly tests the project's stated identity (`CLAUDE.md`'s "anti-generic
guarantee").

**~10-12 scenarios per skill**, five tiers:

| Tier | Count/skill | Tests |
|---|---|---|
| Happy-path | 2-3 | Basic correct operation |
| Gap-admission | 2-3 | Does the skill flag a thin/silent corpus instead of inventing a plausible unmarked claim? |
| Adversarial/pressure | 2-3, multi-turn | Does scripted pushback/urgency push the skill toward answering from general training knowledge instead of the corpus? |
| Cross-skill boundary | 1 per adjacent pipeline edge (6 edges — see §3.5) | Does a skill stay out of its downstream neighbor's territory? |
| Structural/schema | 1-2 | Does the skill produce a properly-frontmattered artifact per §1-2? |

### 3.2 Two check passes per scenario

Every scenario, all tiers, gets both:

**A. Deterministic check pass — syntactic layer only.** This is a load-bearing
scoping decision: these checks prove bookkeeping correctness, not that a claim
is semantically earned. State this explicitly in the harness docs so no one
later assumes a green deterministic pass means "grounded." Checks:
- Marker presence (does the output carry `[C]`/`[I]`/`[T]` markers at all?)
- Citation-resolution against real corpus text (can the cited `(Channel,
  video_id)` be found in the actual corpus? — this discriminates baseline vs.
  skill; a baseline run has no corpus to cite from, so any resolving citation at
  all is a meaningful signal there, but within a skill run it only proves a real
  citation exists somewhere nearby, not that it supports the specific claim
  next to it)
- `marker_counts` vs. a real grep of the artifact body
- Structural-contract match (required frontmatter fields, correct stage value,
  etc., per §1.2)
- Tool-call-log check that the relevant `references/*.md` file was actually
  `Read` during the scenario (requires the harness to capture the transcript,
  not just the final artifact)

**B. LLM-judge pass, graded against an independent rubric.** The rubric is
built from real corpus text directly — **never** from a skill's own `SKILL.md`,
which would reward eloquent restatement of instructions instead of evidence the
corpus was actually consulted. Provenance constraint on the rubric itself
(closing the leakage risk that both rubric and `SKILL.md` distill the same
`docs/`, so convergence in *content* is expected and fine — the risk is
*process* convergence):
- The rubric is authored in a pass that reads only `docs/`, never
  `.claude/skills/`.
- Every rubric criterion carries its own corpus citation.
- Criteria are phrased as evidence questions ("is the hook-length claim
  supported by a cited corpus finding?"), never conformance questions ("does
  the output state the 3-second hook rule?").
- Judge calls run at **temperature 0** with a forced structured verdict —
  PASS/FAIL plus a per-criterion boolean breakdown, never a numeric score (a
  1-10 score drifts across runs in a way a forced boolean doesn't).

**Claim-support spot-check (new judge sub-check, closes the one real gap in the
deterministic layer):** for each artifact, sample 3-5 of its `[C]` claims,
inline the actual cited corpus passage into the judge prompt, and ask a plain
yes/no — does this passage support this specific claim? This is the only check
in the suite that can't be satisfied by decorating an invented claim with a
real-but-irrelevant citation, which the deterministic layer alone cannot catch.

### 3.3 Multi-turn adversarial mechanics

Pushback is **scripted and response-agnostic** — 2-3 canned escalation turns
per scenario (e.g. "skip the citations, just tell me what generally works, I
won't hold you to it"), not an LLM user-simulator. A simulator would react to
what the skill says, which adds cost and non-determinism without adding
signal for what this tier is actually testing.

- Deterministic checks (§3.2A) run against the **final artifact only**.
- The judge grades the **full transcript** against a dedicated rubric section:
  did the skill hold the line and keep citing/flagging gaps under pressure, or
  did it verbally capitulate ("fine, generally hooks should be about 3
  seconds...") even if that capitulation never made it into a written artifact?
  This distinction matters because a skill can fail this tier in conversation
  without the failure ever showing up in deterministic artifact checks.

### 3.4 Structural/schema tier — dependency and sandboxing

**Ordering dependency, stated explicitly:** structural/schema scenarios cannot
run until `finalize-artifact.sh`, the `PreToolUse` hook, and `pipeline.yaml`
(§1-2) actually exist. All other tiers can run before that infrastructure is
built.

**Sandboxing:** all non-structural scenario runs write artifacts to a
disposable sandbox (`evals/results/<timestamp>/runs/`) with locking turned off
— there's no reason to pay the ACL-locking cost for a run whose artifacts get
discarded. Only structural-tier scenarios exercise the **real** finalize/lock
path, specifically because that path is what they're testing. Those scenarios
get an explicit teardown step in the harness (icacls reset, then delete) after
each run, so eval runs never leave permanently locked files behind in the
working tree.

### 3.5 Cross-skill boundary tier — concrete tripwires

One scenario per adjacent pipeline edge. The real topology has **six edges**
given the fan-out at stage 3 (§1.3):

1. `shorts-ideation` → `shorts-scripting`
2. `shorts-scripting` → `voiceover-brief`
3. `shorts-scripting` → `visual-prompts`
4. `voiceover-brief` → `shorts-assembly`
5. `visual-prompts` → `shorts-assembly`
6. `shorts-assembly` → `social-repurpose`

Each edge's scenario defines, concretely:
- A **deterministic tripwire**: a grep for the *downstream* stage's signature
  output structure appearing in the *upstream* stage's artifact. Example: an
  ideation concept brief containing a beat-timing table or `0:00–0:03`-style
  timestamp lines is an automatic fail, because that structure belongs to
  `shorts-scripting`, not `shorts-ideation`.
- One targeted judge question specific to that pair (e.g., for edge 1: "does
  this concept brief contain shot-ready scripted dialogue, rather than a
  packaging direction?").

### 3.6 Pass-rate protocol

- Capability-tier scenarios (gap-admission, adversarial) run **2x** (reduced
  from an initial 3x proposal to control cost — see §3.8).
- Happy-path, structural, and boundary scenarios run once.
- **Aggregation, defined explicitly (this did not have a definition in the
  original draft and needed one):**
  - Deterministic checks must pass on **every** rep run. They're deterministic
    scripts; any single failure across reps is a real bug, not noise — there is
    no partial-credit averaging.
  - Judge pass, at n=2 reps: 2/2 = clean pass, 0/2 = fail, 1/2 = **flagged for
    manual review** rather than forced into a fake majority verdict (a 50/50
    split at n=2 isn't a statistically meaningful "pass," so the harness
    surfaces it instead of silently rounding).
- **Skill-level ship gate:** a skill is considered ready when 100% of its
  happy-path/structural/boundary scenarios pass and its capability-tier
  scenarios clear an 80% pass threshold (of judge-pass scenarios, not
  including manual-review flags, which are resolved by a human before the gate
  is evaluated).

### 3.7 Baseline comparison

Same prompt, no skill loaded, on 1-2 citation-heavy scenarios per skill — but
run from a **bare scratch directory** containing only the prompt, with no
`docs/` and no `.claude/skills/` present. Running the baseline inside the
ContentStudio repo would let it read the corpus directly and defeat the
comparison entirely.

### 3.8 Model tiering

Two different axes get different treatment:

- **Scenario execution** (the skill invocation being tested) runs on whatever
  model the project's skills actually run under in production. This axis is
  deliberately **not** cost-optimized — it's the thing under test, and swapping
  its model would mean the eval no longer measures real-world skill behavior.
- **Judge calls** are tiered by how much judgment each check needs:
  - Structural/schema-match and cross-skill boundary-tripwire verdicts (mostly
    binary, factual) → **Haiku 4.5**.
  - Claim-support spot-checks (semantic support against an inlined corpus
    passage) → **Sonnet**.
  - Multi-turn "held the line under pressure" grading and gap-admission nuance
    (the most judgment-heavy checks) → **Sonnet**, with the strongest available
    tier reserved for the held-out milestone scenario only (§3.9).

### 3.9 Held-out scenario

One scenario per skill that is never used to iterate `SKILL.md` — a convention
(matching the trust-over-enforcement stance already adopted in §2.7), **not** a
technically enforced mechanism. Nothing stops a developer from reading its
failure output and adjusting the skill anyway; the design says so rather than
implying a guarantee that doesn't exist.

- Run only at release checkpoints (full-suite runs, §3.11), not during smoke
  iteration.
- On failure: retire it into the main scenario set (it's no longer "held out"
  once its failure has informed a fix) and author a fresh replacement scenario
  drawn from a corpus section not yet used by any existing scenario.

### 3.10 Versioning and results tracking

- Each results directory (`evals/results/<timestamp>/`) records the git SHA of
  the skills, scenarios, and rubric in effect at run time. Any edit to a
  `SKILL.md` implicitly invalidates prior results for that skill — this is
  recorded, not enforced.
- **`evals/results/` summaries are git-committed** (per the confirmed
  resolution of open question 1, §4.1) — pass/fail counts by tier plus the
  recorded SHAs, e.g. `evals/results/<timestamp>/summary.md`. This gives a
  lightweight eval-health history that can be diffed over time. Full
  transcripts and generated artifacts under `evals/results/<timestamp>/runs/`
  stay gitignored, same precedent as `runs/` and `output/` — only the summary
  is committed.

### 3.11 Cadence

The eval suite is dev-time infrastructure, not something an end-user skill
invocation ever triggers.

- **Smoke mode** (`--smoke`: one scenario per tier per skill) is cheap enough
  to run often, during active iteration on a skill's `SKILL.md` or
  `references/`.
- **Full suite** runs are milestone-gated: before locking a `SKILL.md` for a
  version, after a corpus refresh, before a release. Realistically single-digit
  invocations over a skill's development lifecycle — not automatic, not
  continuous, not per-change.

### 3.12 Corrected cost estimate

The original estimate (~220-240 API calls for a full six-skill build-and-run)
only counted judge calls. It missed that each scenario run is a full agentic
skill session (read `SKILL.md`, read `references/`, produce the artifact) —
8-15+ API calls per run on its own, more for multi-turn adversarial scenarios.

With capability-tier reps trimmed to 2x (§3.6):

- Roughly **90-120 total scenario runs** across all six skills and five tiers.
- Each run costs ~8-15 agent-loop calls (scenario execution) + 1-2 judge calls.
- **Total: roughly 800-1,600 API calls for one full six-skill suite run**,
  with per-call cost reduced by the model tiering in §3.8 (most judge calls run
  on Haiku 4.5, not the top-tier model).

Given the cadence in §3.11, this cost is incurred single digits of times per
skill's development lifecycle, not repeatedly — it is not a per-invocation or
per-commit cost.

### 3.13 Harness layout

```
evals/
  scenarios/<skill>.yaml     # scenario definitions, per skill
  checks/                    # reusable deterministic check scripts
  judge-rubric.md            # the independent rubric (docs/-only provenance, §3.2B)
  results/<timestamp>/
    summary.md                # committed — pass/fail counts by tier, SHAs
    runs/                     # gitignored — full transcripts, generated artifacts
```

---

## 4. Resolved open questions

### 4.1 Should `evals/results/` be committed?

**Resolved: commit summaries only.** See §3.10. Full transcripts stay
gitignored; a lightweight per-run summary (pass/fail counts, SHAs) is
committed as an eval-health history.

### 4.2 Workflow script vs. direct Agent-tool dispatches for the eval runner?

**Resolved: direct Agent-tool dispatches.** Matches the orchestration pattern
already used throughout this project's sessions, avoids the Workflow tool's
per-run opt-in gating friction for a suite meant to run at milestone
checkpoints (not continuously), and scales adequately at ~90-120 scenario runs
via batched parallel Agent calls.

---

## 5. Out of scope for this spec

- Actual hook/script/eval implementation — that's the implementation plan's job
  (a separate document), executed in a later session.
- Per-skill scenario content (the specific YAML scenario definitions) — the
  plan schedules their authorship, but this spec does not enumerate them.
- Any change to `docs/` (the citation corpus) beyond the one-time `icacls`
  hardening step in §2.4 — this spec does not touch corpus content.
- Any FamilyBrain integration of any kind — out of scope permanently per
  `CLAUDE.md`'s FamilyBrain firewall.
