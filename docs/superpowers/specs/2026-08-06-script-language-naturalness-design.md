# Script Language Naturalness — Gates D & E — Design

**Date:** 2026-08-06
**Status:** approved
**Affects:** `.claude/skills/shorts-scripting/`, `.claude/skills/visual-prompts/`, `scripts/`,
`pipeline-app/pipeline_app/`, `docs/`, `tests/`

## Problem

The scripts `shorts-scripting` produces read as written prose, not as speech. The reported symptom
was em-dashes in voiceover lines. The measured cause is broader: **the skill has no gate on script
language at all.**

### Evidence base

Four scripts have shipped through the pipeline, carrying **25 voiceover lines** between them:

| Script | VO lines | Lines with em/en-dash |
|---|---|---|
| `2026-07-25-let-kids-play-act-script.md` | 5 | 3 |
| `2026-07-25-let-kids-play-act-specialization-script.md` | 5 | 0 |
| `2026-07-28-decline-the-next-level-script.md` | 7 | 2 |
| `2026-07-28-nobody-asked-the-kid-script.md` | 8 | 0 |
| **Total** | **25** | **5** |

Five failures are visible in that set:

1. **Em-dash as a written appositive.** `decline-the-next-level`, Build 8–18s:
   *"A 2009 international position stand — Côté, Lidor and Hackfort — reports that kids who sample
   many sports still tend to reach elite performance."* This is a parenthetical construction from
   written English. It has no spoken realization; a narrator has to invent one.
2. **Em-dash as a contrast pivot.** Same script, Build 21–28s: *"…isn't more serious play — it's
   constrained labor."* Speakable, but it is the model's default pivot rather than a chosen one.
3. **A repeated syntactic template the skill cannot see.** Negation-fragment closers appear across
   three of four scripts: *"Not athletically."* / *"Not because he cleared a checkpoint."* /
   *"Not a report card."* Two of those are in a single script.
4. **Fragment runs as the default rhythm.** `nobody-asked-the-kid`, Payoff 26–38s: *"Eighty-one
   things. Eleven factors. Trying hard came first."* And Build 8–14s: *"Charlotte Mason wrote that
   down in 1886. She called it narration. Every child does it."*
5. **Contorted abstractions that read fine and speak badly.** `decline-the-next-level`, Setup 3–8s:
   *"That offer moves his reason for playing outside the playing."*

### Root cause

`shorts-scripting/SKILL.md:115` step 9 is *"Run the humanize pass."* It is a self-attestation, not a
gate: the same turn, same model, and same context that authored the script grades it, and the record
is a prose bullet in Delivery notes.

What it grades against is two phrases and five words. The complete no-list in
`references/script-intelligence-and-delivery.md:40-43` is *"it's important to note," "some may
argue,"* and *delve, leverage, comprehensive, robust, holistic* — sourced from a single corpus
finding `[C] (Romayroh, ErCV5czVK1g)`. Em-dashes are not on it. Nothing about spoken-register syntax
is on it.

The result is scripts that certify themselves accurately and miss the problem entirely. Every one of
the four shipped scripts states: *"Humanize pass: run… no AI-fingerprint phrases and no buzzwords
appear in any VO line."* True in each case, and orthogonal to the failures above.

By contrast `visual-prompts` runs three gates (A inline syntax, B a fresh adversarial agent, C a
deterministic Python linter, blocking). `shorts-scripting` runs zero.

### A second, pre-existing bug in the same mechanism

`visual-prompts/SKILL.md:317-326` mandates `python scripts/lint_prompt_sheet.py` and states that Gate
C must never be recorded as passed *"without having actually run it and observed exit 0."*

`pipeline-app/pipeline_app/cli_runner.py:39` denies `Bash` and `PowerShell` on every pipeline turn,
and nothing in the app runs the linter. **In pipeline mode Gate C cannot run.** The skill therefore
either fails every app run or records a pass that never happened.

This is not introduced by this change, but the deterministic half of Gate D would inherit it exactly,
so the fix is designed once and applied to both.

## Non-goals

- **Style transfer.** No positive/"golden" sample set is built. The gates catch tells; they do not
  teach a target voice. Deferred deliberately — revisit if the tell-catching proves insufficient.
- **Rewriting the four shipped scripts.** They are published artifacts and a `PreToolUse` hook blocks
  editing `rgs-briefs/*.md`. They are evidence, not a backlog.
- **Other stages.** `voiceover-brief` and `social-repurpose` also emit read-aloud text. Out of scope.
- **Querying gate history across runs.** Gate results live in artifact frontmatter, not a DB table.
  A query like "every script that failed D1" is not supported and is not needed.

## Design

Two gates, mirroring the `midjourney-prompting` Gate A/B split: a cheap deterministic pass for
mechanical tells, an expensive judgment pass for what no regex can see. Both block.

### `[S]` — a new provenance marker

The corpus contains no material on spoken-register syntax. Its entire basis for read-aloud
naturalness is two findings: `[C] (Romayroh, ErCV5czVK1g)` on perplexity/burstiness, and
`[C] (Nick Nimmin, IF-PD6XMjYY)` on leaving small imperfections. A naturalness rule set cannot be
`[C]`, and marking it bare `[I]` would make it indistinguishable from the generic content-creation
advice `CLAUDE.md` exists to refuse.

**`[S]` (script-baseline)** = derived from an observed failure in this repo's own shipped output,
cited by file and beat. The repo already extends its marker vocabulary when a new evidence source
appears (`[REF]` for the ten-video cohort, `[B]` for the brand definition); this is the same move.

**An `[S]` rule that cannot name a real shipped line violating it does not ship.** That constraint is
what keeps the rule set evidenced rather than invented.

`[I]` remains available for rules that are genuine craft judgment with no shipped-line evidence, and
they must be marked as such rather than dressed up as `[S]`.

### `docs/script-language-baseline.md` — the evidence base

All 25 VO lines, each labeled pass/fail with a one-line reason and the rule it evidences. Every `[S]`
citation in the rule set points into this file. Test fixtures derive from it.

### Gate D — mechanical, deterministic

`scripts/lint_script_language.py`. Stdlib only, mirroring `lint_prompt_sheet.py`'s shape (parse →
`Finding` dataclass → exit 0 pass / 1 findings). Runnable by hand, unit-testable, no app dependency.

**Scope: voiceover lines only.** Prose, Delivery notes, verbatim quote cards, and on-screen text
plates legitimately use written punctuation and are never checked.

| Check | Rule | Provenance |
|---|---|---|
| D1 | No em-dash or en-dash in a VO line | `[S]` — 5 lines today; `decline-the-next-level` Build 8–18s |
| D2 | No semicolons, parentheticals, or bracketed asides in a VO line | `[S]` — zero hits; regression guard |
| D3 | No repeated fragment template ≥2× within one script | `[S]` — `decline-the-next-level` Hook + Payoff |
| D4 | Fragment-run density below threshold (a run = ≥3 consecutive sentences under ~6 words) | `[S]` — `nobody-asked-the-kid` Payoff 26–38s, Build 8–14s |
| D5 | Fingerprint-phrase and buzzword no-list | `[C] (Romayroh, ErCV5czVK1g)` — carried forward |
| D6 | No unspeakable tokens in a VO line (`&`, `n=142`, `12(3):424–433`, `§`) | `[S]` — zero hits; regression guard |
| D7 | No beat exceeds a 170 wpm **ceiling** (words ÷ duration) | `[I]` — the band is the skill's own; mechanizing the arithmetic is this design's addition |
| D8 | The artifact carries a well-formed `Gate E:` line | `[I]` — the honesty lock, see below |

**On D3.** Implementable in stdlib as: two or more short sentences (under ~6 words) sharing a leading
token. The three shipped instances are *"Not athletically."*, *"Not because he cleared a
checkpoint."*, *"Not a report card."* — no shared wording beyond the leading `Not`, which is exactly
the signal. Wording-identical repetition is a strict subset and is caught by the same check.

Its limit, stated: this catches **leading-token** templates only. Template sameness that shares a
shape without sharing a first word is Gate E's job, and the two are deliberately split that way.

**On D7 — ceiling, not band.** An earlier draft of this spec required each beat to resolve *inside*
150–170 wpm. That is wrong and would fail nearly every shipped script: `decline-the-next-level`'s own
timing table runs Hook at ~140 and Loop/CTA at ~103, and the script justifies that slack as
*"deliberate breathing room for the half-second pauses that make a key word land"*
`[C] (Kallaway, ZM3elcBE48I)`.

Under-running is a legitimate authorial choice. **Over-running is a production failure** — a beat
with more words than fit in its seconds cannot be spoken at all, and it silently corrupts the timing
`voiceover-brief` and `shorts-assembly` inherit. So D7 flags only the ceiling. The script total is
separately checked against the full 150–170 band, where slack is meaningful.

Calibration note: `decline-the-next-level`'s Dewey sub-beat sits at ~171 wpm, which the script itself
flags as "within rounding." The ceiling is set at 170 with a ±2 wpm tolerance, making that beat a
deliberate pass rather than an accidental one.

**On D4.** Short fragments are legitimate Shorts writing; the failure mode is fragments as the
*default rhythm everywhere*. This is therefore a per-script density check, not a per-instance one.

**Thresholds are calibrated, not principled.** D3's count and D4's density are tuned against the four
labeled scripts so that today's worst fails and today's best passes (see Testing). **n=4 is thin.**
These want retuning once more scripts exist, and the spec records that rather than implying the
numbers are validated.

### Gate E — judgment, fresh Opus critic

Dispatched via `Task` to a fresh `general-purpose` agent with `model: opus`, following Gate B's
contract exactly: it judges the artifact and not the reasoning, and it is instructed to **find the
failure, not approve**.

**Input: the VO lines and their beat timings only.** Not the Delivery notes, not the Alternates, not
the citation rationale. The authoring rationale is what makes a written line look justified; the
critic must not see it. (Shipped scripts run 300–500 lines; the VO payload is ~25.)

The question it answers: **does a person say this out loud?**

- Written-register syntax no regex catches — appositives, nominalizations, abstract subjects.
  Live example: *"That offer moves his reason for playing outside the playing."*
- Template sameness across beats that D3 misses because the shapes differ but the effect repeats.
- Whether an "imperfection" is real cadence or performed. The corpus asks for small imperfections
  `[C] (Nick Nimmin, IF-PD6XMjYY)`; a manufactured dropped article is not the same thing.
- Breath: is each line speakable in one breath at the stated wpm?

**Returns per finding:** the offending line, why it fails read-aloud, and **one concrete rewrite**.

#### No-touch zones

The critic is told, as a hard constraint, that it may not rewrite:

- verbatim quote-card text (`"under no circumstance may the card be paraphrased"`)
- citation attributions — author names, years, journal strings
- any clause the script marks uncuttable (e.g. `"It was never yours."`)
- brand-lexicon-screened wording

A finding on a no-touch line is still reported; the rewrite must restructure *around* the constraint.
The Côté line is fixed by resequencing the sentence — *"Back in 2009, three sport psychologists put
out a position stand. Kids who sample many sports still tend to reach elite level."* — never by
dropping the attribution.

`shorts-scripting` re-checks any accepted rewrite against the beat's word budget (±2 words) and
re-runs Gate D over the result before emitting.

### Where each gate runs

| Mode | Gate D | Gate E |
|---|---|---|
| Standalone (skill invoked directly) | skill runs it via `Bash` | skill dispatches via `Task` |
| Pipeline app | **app runs it post-turn**; skill records `deferred — app-run` | skill dispatches via `Task` |

`Bash` is denied on pipeline turns and that denial is deliberate — `cli_runner.py:39-45` documents a
Windows `cmd` shim quoting escape it closes. It is not reopened. `Task` is left undenied specifically
so Gate B can dispatch, so Gate E works identically in both modes.

`deferred — app-run` is the honest pipeline-mode value for Gate D. It is exactly the line
`visual-prompts` should have carried instead of recording a Gate C pass it never ran.

### The honesty lock

Gate D check D8: **the artifact must carry a well-formed `Gate E:` line.** Missing or malformed is a
Gate D failure.

This cannot prove Gate E ran. It makes silently omitting a skipped gate structurally impossible,
which is the precise hole Gate C fell through.

## Components

### `scripts/lint_script_language.py`

Stdlib only. `python scripts/lint_script_language.py <path-to-script.md>`; exit 0 pass, 1 findings,
2 parse error.

The VO-line parser must tolerate real format drift. The two shipped heading forms already differ:

```
HOOK (0–3s  | 7 words): "It won't set him back. Not athletically."
HOOK (0–3s  | 8 words) — *composite child's voice*: "Best part was the mud."
```

plus indented Build and Payoff sub-ranges:

```
BUILD/VALUE (8–26s | 45 words):
  (8–14s | 15 words): "Charlotte Mason wrote that down in 1886."
  [re-hook beat @ ~14s] (14–17s | 8 words): "But she also named what happens to it."
```

**A parser that matches nothing and reports pass is the critical failure mode.** Zero VO lines parsed
is a hard failure (exit 2) with a parse error naming the file, never a clean exit.

### `.claude/skills/shorts-scripting/references/read-aloud-gates.md`

The D/E rule set with `[S]` citations into `docs/script-language-baseline.md`, plus Gate E's dispatch
prompt verbatim (following `midjourney-prompting/references/validation-gates.md`'s precedent of
carrying the literal dispatch text).

### `.claude/skills/shorts-scripting/SKILL.md`

- Step 9 changes from *"Run the humanize pass"* to *"Run Gate D, then Gate E."*
- A `[S]` entry is added to the provenance-discipline section.
- The output contract gains a GATES block:

```
GATES
  Gate D (scripts/lint_script_language.py): [pass | N findings | deferred — app-run]
  Gate E (fresh Opus critic):               [pass | N findings | overridden: <reason>]
```

- The Delivery-notes "Humanize pass: run" bullet stops being the record. It may remain as prose; it
  is no longer evidence of anything.

### `pipeline-app/pipeline_app/gates.py`

A registry mapping `stage_id → list[GateRunner]`. Each runner returns
`{name, status: pass|fail|error, findings: [...]}`.

Registered at introduction: `scripting → lint_script_language`, `visual → lint_prompt_sheet`.

### `pipeline-app/pipeline_app/turn_service.py`

After `artifact_written` is confirmed (`turn_service.py:221`) and before `write_artifact`
(`turn_service.py:246`), run the stage's registered gates over `raw_output.md` and fold results into
the artifact frontmatter:

```yaml
gates:
  - name: gate_d_script_language
    status: fail
    findings:
      - check: D1
        beat: "BUILD/VALUE 8–18s"
        message: "em-dash in VO line"
```

The artifact is still written and the stage still reaches `awaiting_review` — a failing gate must
never hide the artifact that failed it.

### `pipeline-app/pipeline_app/approval_service.py`

`approve_stage` already parses the latest artifact's frontmatter (`approval_service.py:41`). It gains
a check: refuse approval while any gate is `fail` or `error`, unless an explicit `override_reason` is
supplied, which is recorded.

No schema migration: frontmatter is the source of truth, and pinning the gate result to the artifact
version is correct — a gate result belongs to the thing it graded.

### `.claude/skills/visual-prompts/SKILL.md`

Gate C's mandatory-`Bash` instruction is amended to state the two modes: run it directly in
standalone mode; record `deferred — app-run` in pipeline mode, where the app runs it. The existing
"never record a pass you did not observe" rule is retained and now has a truthful third value.

## Error handling

| Condition | Behavior |
|---|---|
| Linter raises | `status: error`, **fail-closed**. Never a silent pass. |
| Zero VO lines parsed | Exit 2, parse error naming the file. Fails the gate. |
| Gate E `Task` dispatch fails or returns unparseable output | Skill records `Gate E: error` and does not emit. D8 catches an emission that skipped it. |
| Gate E proposes a rewrite touching a no-touch zone | Skill rejects that rewrite, records the finding as unresolved, and keeps the gate failing. |
| Accepted rewrite breaks the word budget or wpm band | Fails D7 on the re-run; the rewrite is not shipped. |
| An override is used | Recorded with its reason on the stage; the gate result stays `fail` in frontmatter. |

## Testing

`tests/test_lint_script_language.py`, mirroring `tests/test_lint_prompt_sheet.py`.

Fixtures are **copies** of the four shipped scripts under `tests/fixtures/`, not reads from
`rgs-briefs/`. Tests must not depend on live pipeline artifacts even though those are hook-protected
against edits — a fixture is a frozen input, and coupling the suite to the briefs directory would
make an unrelated new script able to break it.

**Calibration cases** — these define the thresholds:

| Fixture | Expected |
|---|---|
| `let-kids-play-act` | fail D1 ×3 |
| `decline-the-next-level` | fail D1 ×2, D3 ×2; pass D7 (Dewey beat ~171, inside tolerance) |
| `nobody-asked-the-kid` | pass D1/D2/D3/D7; fail D4 on fragment density |
| `let-kids-play-act-specialization` | pass D1–D4, D7 — the cleanest of the four |

All four fail D8, since none carries a `Gate E:` line. That is correct: they predate the gate, and it
confirms the honesty lock fires rather than passing legacy output by default.

**Behavioral cases:**

- Parser tolerates both heading forms, the `— *composite child's voice*:` interjection, and indented
  Build/Payoff sub-ranges.
- A file with no VO lines exits 2, not 0.
- **Scope containment:** em-dashes in prose, Delivery notes, quote cards, and on-screen text plates
  do not fire D1. This is the check most likely to regress into noise and gets explicit coverage.
- D8 fails a script with no `Gate E:` line, and passes one with a well-formed line.
- D7 catches an over-stuffed beat (above the 170 wpm ceiling + tolerance) and does **not** fire on an
  under-running beat — a synthetic 100 wpm Loop/CTA must pass.

**App-side:**

- A failing gate lands in frontmatter and the stage still reaches `awaiting_review`.
- `approve_stage` raises on a failing gate without an override.
- `approve_stage` succeeds with an `override_reason` and records it.
- A linter that raises produces `status: error` and blocks approval.

## Open items for implementation

1. **`Task` availability on pipeline turns is asserted in code comments, not tested.**
   `cli_runner.py:26-31` states `Task` is deliberately undenied so Gate B can dispatch, but
   `--allowedTools` defaults to `"Read,Glob,Grep,Write,Edit,Skill"`. Verify against a live pipeline
   run that a `Task` dispatch actually succeeds before relying on Gate E in app mode. If it does not,
   Gate E moves to the same app-run treatment as Gate D.
2. **Confirm the `model: opus` override reaches the subagent** in a headless `claude -p` pipeline
   turn, rather than silently inheriting the session model.
