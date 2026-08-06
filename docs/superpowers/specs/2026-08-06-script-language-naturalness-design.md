# Script Language Naturalness — Gates D & E — Design

**Date:** 2026-08-06
**Status:** approved
**Affects:** `.claude/skills/shorts-scripting/`, `.claude/skills/visual-prompts/`, `scripts/`,
`pipeline-app/pipeline_app/`, `docs/`, `tests/`

**Revision note (2026-08-06, post-review):** an adversarial review of the first draft found the
evidence table undercounted, the wpm calibration wrong, two rules marked `[S]` with no evidence, one
rule that would block a `[C]`-mandated mechanic, and a `Task`-availability assumption that the code
contradicts. All are corrected below; the corrections are recorded rather than quietly absorbed
because several of them changed the design, not just the numbers.

## Problem

The scripts `shorts-scripting` produces read as written prose, not as speech. The reported symptom
was em-dashes in voiceover lines. The measured cause is broader: **the skill has no gate on script
language at all.**

### Evidence base

Four scripts have shipped through the pipeline, carrying **27 voiceover lines** between them:

| Script | VO lines | Lines with em/en-dash |
|---|---|---|
| `2026-07-25-let-kids-play-act-script.md` | 6 | 4 |
| `2026-07-25-let-kids-play-act-specialization-script.md` | 6 | 1 |
| `2026-07-28-decline-the-next-level-script.md` | 7 | 2 |
| `2026-07-28-nobody-asked-the-kid-script.md` | 8 | 0 |
| **Total** | **27** | **7** |

**Counting caveat, stated because it already bit once.** A first pass at this table read 25 lines and
5 dashes. It used an extraction pattern requiring a `(range | words)` group, which the older
`[re-hook beat @ ~15s]: "…"` form does not carry — so two VO lines were silently dropped, one of them
dash-bearing. That is precisely the parser failure mode this spec elsewhere calls critical, and it is
why the linter's parser must fail loudly on a zero/partial parse rather than report a clean count.

### Failures visible in that set

**Unconditional — these are wrong regardless of intent:**

1. **Em-dash as a written appositive.** `decline-the-next-level`, Build 8–18s:
   *"A 2009 international position stand — Côté, Lidor and Hackfort — reports that kids who sample
   many sports still tend to reach elite performance."* A parenthetical construction from written
   English with no spoken realization; a narrator has to invent one.
2. **Em-dash as a contrast pivot.** Same script, Build 21–28s: *"…isn't more serious play — it's
   constrained labor."* Speakable, but the model's default pivot rather than a chosen one.
3. **Over-stuffed beats.** Both 07-25 scripts open at 13 words in 3 seconds — **~260 wpm**, against
   the skill's own 150–170 band. `specialization`'s Setup runs 19 words in 5s (~228). These beats
   cannot be spoken in their stated time, and the error propagates into `voiceover-brief` and
   `shorts-assembly` unchallenged. Neither script carries a timing-reconciliation table; the two
   07-28 scripts do, and both are clean.

**Contextual — wrong only when they are the default rather than a choice:**

4. **A repeated fragment template.** Negation-fragment closers appear across three of four scripts:
   *"Not athletically."* / *"Not because he cleared a checkpoint."* / *"Not a report card."*
5. **Fragment runs as rhythm.** `nobody-asked-the-kid`, Payoff 26–38s: *"Eighty-one things. Eleven
   factors. Trying hard came first."*
6. **Contorted abstractions that read fine and speak badly.** `decline-the-next-level`, Setup 3–8s:
   *"That offer moves his reason for playing outside the playing."*

**Failures 4 and 5 are defended in the shipped scripts with a `[C]` citation**, and the defence is
not freelancing —
`references/script-intelligence-and-delivery.md:64-66` instructs it: *"don't over-polish the VO line
into textbook-perfect grammar; a little natural cadence is a feature"* `[C] (Nick Nimmin,
IF-PD6XMjYY)`. `nobody-asked-the-kid-script.md:371-373` and `decline-the-next-level-script.md:237-238`
both invoke it by name.

**This design does not override that rule.** Whether a fragment is deliberate cadence or the model's
default rhythm is a question about intent, and no regex can see intent. Failures 4–6 are therefore
Gate E's territory, not Gate D's — see "The Gate D / Gate E boundary" below.

*Unverifiable caveat:* `output/` is not present locally, so the original Nick Nimmin finding cannot
be checked. It is possible that it concerns *the cut* (filler, breath, editing) and that the
extension to written VO lines is the reference file's own gloss. Not resolvable here; recorded so a
future reader can settle it against the corpus.

### Root cause

`shorts-scripting/SKILL.md:115` step 9 is *"Run the humanize pass."* It is a self-attestation, not a
gate: the same turn, same model, and same context that authored the script grades it, and the record
is a prose bullet in Delivery notes.

What it grades against is two phrases and five words. The complete no-list in
`references/script-intelligence-and-delivery.md:40-43` is *"it's important to note," "some may
argue,"* and *delve, leverage, comprehensive, robust, holistic* — sourced from a single corpus
finding `[C] (Romayroh, ErCV5czVK1g)`. Em-dashes are not on it. Nothing about spoken-register syntax
is on it, and nothing checks the timing arithmetic.

Every one of the four shipped scripts states: *"Humanize pass: run… no AI-fingerprint phrases and no
buzzwords appear in any VO line."* True in each case, and orthogonal to every failure above.

By contrast `visual-prompts` runs three gates (A inline syntax, B a fresh adversarial agent, C a
deterministic Python linter, blocking). `shorts-scripting` runs zero.

### A second, pre-existing bug in the same mechanism

`visual-prompts/SKILL.md:317-326` mandates `python scripts/lint_prompt_sheet.py` and states that Gate
C must never be recorded as passed *"without having actually run it and observed exit 0."*

`cli_runner.py:39-45` denies `Bash` and `PowerShell` on every pipeline turn, and nothing under
`pipeline-app/` references the linter. **In pipeline mode Gate C cannot run.** The skill therefore
either fails every app run or records a pass that never happened.

Not introduced by this change, but the deterministic half of Gate D would inherit it exactly, so the
fix is designed once and applied to both.

## Non-goals

- **Style transfer.** No positive/"golden" sample set is built. The gates catch tells; they do not
  teach a target voice. Deferred deliberately.
- **Rewriting the four shipped scripts.** They are published artifacts and a `PreToolUse` hook blocks
  editing `rgs-briefs/*.md`. They are evidence, not a backlog.
- **Other stages.** `voiceover-brief` and `social-repurpose` also emit read-aloud text. Out of scope.
- **Querying gate history across runs.** Gate results live in artifact frontmatter, not a DB table.

## Design

Two gates, mirroring the `midjourney-prompting` Gate A/B split.

### The Gate D / Gate E boundary

**Gate D checks what is wrong unconditionally.** An em-dash in a spoken line is unspeakable whatever
the author intended. A beat at 260 wpm cannot be performed. These are mechanical facts, and a
deterministic checker is the right instrument.

**Gate E judges what is wrong only in context.** Fragment rhythm, template sameness, and contorted
abstraction are failures when they are the model's default and features when they are a choice. That
distinction requires reading the script as a whole, so it goes to a model, not a regex.

This boundary is what keeps the design from overriding `[C] (Nick Nimmin, IF-PD6XMjYY)`. A Gate E
rhythm finding is **resolvable by defending it**: if the author states in Delivery notes why a
fragment run is deliberate, citing the corpus rule, that resolves the finding. The gate forces the
choice to be explicit; it does not decide it.

### `[S]` — a new provenance marker

The corpus contains no material on spoken-register syntax. Its entire basis for read-aloud
naturalness is two findings: `[C] (Romayroh, ErCV5czVK1g)` on perplexity/burstiness, and
`[C] (Nick Nimmin, IF-PD6XMjYY)` on leaving small imperfections. A naturalness rule set cannot be
`[C]`, and marking it bare `[I]` would make it indistinguishable from the generic content-creation
advice `CLAUDE.md` exists to refuse.

**`[S]` (script-baseline)** = derived from an observed failure in this repo's own shipped output,
cited by file and beat. The repo already extends its marker vocabulary when a new evidence source
appears (`[REF]` for the ten-video cohort, `[B]` for the brand definition); this is the same move.

**An `[S]` rule that cannot name a real shipped line violating it does not ship.** The first draft
broke this rule immediately — it marked two zero-hit regression guards `[S]` — which is exactly the
laundering the marker exists to prevent. Those are `[I]` below. The constraint is only worth anything
if it is enforced against its own author.

### Gate D — mechanical, deterministic

`scripts/lint_script_language.py`. Stdlib only, mirroring `lint_prompt_sheet.py`'s shape (parse →
`Finding` dataclass → exit 0 pass / 1 findings / 2 parse error). Runnable by hand, unit-testable, no
app dependency.

**Scope: voiceover lines only.** Prose, Delivery notes, verbatim quote cards, and on-screen text
plates legitimately use written punctuation and are never checked.

| Check | Rule | Provenance |
|---|---|---|
| D1 | No em-dash or en-dash in a VO line | `[S]` — 7 lines across 3 scripts; `decline` Build 8–18s |
| D2 | No semicolons, parentheticals, or bracketed asides in a VO line | `[I]` — zero hits; regression guard, honestly unevidenced |
| D3 | Fingerprint-phrase and buzzword no-list | `[C] (Romayroh, ErCV5czVK1g)` — carried forward |
| D4 | No unspeakable tokens in a VO line (`&`, `n=142`, `12(3):424–433`, `§`) | `[I]` — zero hits; regression guard, honestly unevidenced |
| D5 | No beat exceeds a 170 wpm **ceiling** (words ÷ duration), ±2 tolerance | `[S]` — both 07-25 Hooks at ~260 wpm; `specialization` Setup at ~228 |
| D6 | The artifact carries a well-formed `Gate E:` line | `[I]` — the honesty lock, see below |

**On D5 — ceiling, not band.** An earlier draft required each beat to resolve *inside* 150–170 wpm.
That is wrong: `decline-the-next-level`'s own timing table runs Hook at ~140 and Loop/CTA at ~103,
and the script justifies that slack as *"deliberate breathing room for the half-second pauses that
make a key word land"* `[C] (Kallaway, ZM3elcBE48I)`.

Under-running is a legitimate authorial choice. **Over-running is a production failure.** So D5 flags
only the ceiling. The script total is separately checked against the full 150–170 band, where slack
is meaningful.

`decline`'s Dewey sub-beat sits at ~171, which the script flags as "within rounding" — the ±2
tolerance makes that a deliberate pass rather than an accidental one.

**D5 cannot compute on old-format re-hook lines**, which carry no `(range | words)` group. Those are
skipped and the skip is **reported as a finding of kind `skipped`**, never silently omitted. A beat
whose timing cannot be checked is a known unknown, not a pass.

**Rhythm checks are deliberately absent from Gate D.** The first draft carried a repeated-template
check and a fragment-density check here. Both were removed: the template check would have fired on
`decline`'s Hook/Loop pair (*"It won't set him back."* repeated verbatim), which `SKILL.md:108-110`
**requires** — mirroring the Hook is a `[C]`-cited mechanic `(Jenny Hoyos, mhVDcqnxxaY)`. A gate that
blocks a mandated mechanic is worse than no gate.

### Gate E — judgment, fresh Opus critic

Dispatched via `Task` to a fresh `general-purpose` agent with `model: opus`, following Gate B's
contract: it judges the artifact and not the reasoning, and is instructed to **find the failure, not
approve**.

The question it answers: **does a person say this out loud?**

- **Written-register syntax** no regex catches — appositives, nominalizations, abstract subjects.
  Live example: *"That offer moves his reason for playing outside the playing."*
- **Fragment rhythm and template sameness** — is this cadence chosen, or is it the default everywhere?
  Moved here from Gate D precisely because that question needs the whole script.
- **Whether an "imperfection" is real cadence or performed.** The corpus asks for small imperfections
  `[C] (Nick Nimmin, IF-PD6XMjYY)`; a manufactured dropped article is not the same thing.
- **Breath:** is each line speakable in one breath at the stated wpm?

**Returns per finding:** the offending line, why it fails read-aloud, and **one concrete rewrite**.

#### Input, and how no-touch metadata reaches the critic

The first draft said the critic receives "VO lines and beat timings only." That is unworkable: every
binding constraint lives in the prose that framing withholds — the uncuttable *"It was never yours."*
(`nobody-asked-the-kid-script.md:264,437`), the spoken verbatim Mason fragment (lines 204-208, a VO
line that is deliberately 1886 written prose and Gate E's prime false-positive target), the
association-not-causation hedges (`decline:166-173`), and the A3 blame-audit wordings
(`nobody:258-267`, where a draft was rewritten specifically to remove a second-person pronoun).

**Corrected input contract:** the skill assembles a Gate E payload of the VO lines, their beat
timings, and **an explicit per-line no-touch annotation** — `verbatim-quote`, `citation`,
`uncuttable`, `lexicon-screened`, or `free`. The critic sees constraints without seeing the
*rationale* that would make a written line look justified. Delivery notes, Alternates, and the
grounding beat map are still withheld.

Annotation is the skill's job because the skill already knows: it wrote the constraints into the
document. A line the skill cannot classify is annotated `unknown` and treated as no-touch.

#### No-touch zones

The critic may not rewrite a line annotated `verbatim-quote`, `citation`, `uncuttable`,
`lexicon-screened`, or `unknown`. A finding on such a line is still reported; the rewrite must
restructure *around* the constraint.

The Côté line is fixed by resequencing — *"Back in 2009, three sport psychologists put out a position
stand. Kids who sample many sports still tend to reach elite level."* — never by dropping the
attribution.

`shorts-scripting` re-checks any accepted rewrite against the beat's word budget (±2 words) and
re-runs Gate D over the result before emitting.

#### Resolution paths

A Gate E finding is resolved by exactly one of: **accepting the rewrite**, **authoring a different
fix**, or **defending the line in writing** with its justification (a `[C]` citation for a deliberate
cadence, or the binding constraint for a no-touch line). The third path is what prevents the
constraint-deadlock the first draft would have produced, and it is why Gate E can block without
becoming unresolvable.

### Where each gate runs

| Mode | Gate D | Gate E |
|---|---|---|
| Standalone | skill runs it via `Bash` | skill dispatches via `Task` |
| Pipeline app | **app runs it post-turn**; skill records `deferred — app-run` | skill dispatches via `Task` |

`Bash` is denied on pipeline turns and that denial is deliberate — `cli_runner.py:39-45` documents a
Windows `cmd` shim quoting escape it closes. It is not reopened.

**`Task` availability is a required change, not an assumption.** `cli_runner.py:26-31` asserts `Task`
is deliberately undenied so Gate B can dispatch — but `allowed_tools` defaults to
`"Read,Glob,Grep,Write,Edit,Skill"` (`cli_runner.py:224`), which does not include it. Under headless
`-p` there is no one to approve an unlisted tool. **`Task` is added to that default string** as part
of this change. This also repairs `midjourney-prompting`'s Gate B, which is very likely failing
silently today for the same reason — verify that against a live run while implementing, since the
current behavior is asserted in comments and not tested.

`deferred — app-run` is the honest pipeline-mode value for Gate D — the line `visual-prompts` should
have carried instead of recording a Gate C pass it never ran.

### The honesty lock, and its limit

Gate D check D6: **the artifact must carry a well-formed `Gate E:` line.** Missing or malformed is a
Gate D failure.

**Stated plainly: this does not prove Gate E ran.** A skill that skipped it can still write
`Gate E: pass` — the same self-attestation this spec diagnoses as the root cause, reintroduced for
the more expensive gate. D6 raises the cost of the omission from silent to deliberate, and no
further. A real proof would require the app to run Gate E itself, which is out of scope here; if
Gate E's findings turn out to be suspiciously sparse in practice, that is the escalation.

## Components

### `scripts/lint_script_language.py`

Stdlib only. `python scripts/lint_script_language.py <path>`; exit 0 pass, 1 findings, 2 parse error.

The parser must handle all three shipped VO-line forms:

```
HOOK        (0–3s  | 7 words): "It won't set him back. Not athletically."
HOOK        (0–3s  | 8 words) — *composite child's voice*: "Best part was the mud."
[re-hook beat @ ~15s]: "His proof: a trader who quietly bought up every oil press in town…"
```

plus indented Build and Payoff sub-ranges. Extraction is over **quoted spans**, which also avoids
false-positive dash hits on the en-dash inside every `(0–3s | N words)` heading.

**A parser that matches nothing and reports pass is the critical failure mode** — and the one that
already produced a wrong evidence table for this very spec. Zero VO lines parsed is exit 2 with a
parse error naming the file. A file yielding fewer VO lines than it has beat headings emits a
`partial-parse` finding rather than passing quietly.

### `.claude/skills/shorts-scripting/references/read-aloud-gates.md`

The D/E rule set with `[S]` citations into `docs/script-language-baseline.md`, the Gate E dispatch
prompt verbatim (following `midjourney-prompting/references/validation-gates.md`'s precedent), and
the no-touch annotation vocabulary.

### `docs/script-language-baseline.md`

All 27 VO lines, each labeled pass/fail with a one-line reason and the rule it evidences. Every `[S]`
citation points here. Test fixtures derive from it.

### `.claude/skills/shorts-scripting/SKILL.md`

- Step 9 changes from *"Run the humanize pass"* to *"Run Gate D, then Gate E."*
- An `[S]` entry is added to the provenance-discipline section.
- The output contract gains a GATES block:

```
GATES
  Gate D (scripts/lint_script_language.py): [pass | N findings | deferred — app-run]
  Gate E (fresh Opus critic):               [pass | N findings | N defended | overridden: <reason>]
```

### `pipeline-app/pipeline_app/gates.py`

A registry mapping `stage_id → list[GateRunner]`, each returning
`{name, status: pass|fail|error, findings: [...]}`. Registered: `scripting → lint_script_language`,
`visual → lint_prompt_sheet`.

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
supplied, which is recorded. No schema migration.

### `.claude/skills/visual-prompts/SKILL.md`

Gate C's mandatory-`Bash` instruction is amended to state both modes: run it directly standalone;
record `deferred — app-run` in pipeline mode, where the app runs it. The "never record a pass you did
not observe" rule is retained and now has a truthful third value.

## Error handling

| Condition | Behavior |
|---|---|
| Linter raises | `status: error`, **fail-closed**. Never a silent pass. |
| Zero VO lines parsed | Exit 2, parse error naming the file. |
| Fewer VO lines than beat headings | `partial-parse` finding; gate fails. |
| Beat timing uncomputable (old-format re-hook) | `skipped` finding, reported not omitted. |
| Gate E `Task` dispatch fails or returns unparseable output | Skill records `Gate E: error` and does not emit. D6 catches an emission that skipped it. |
| Gate E proposes a rewrite touching a no-touch line | Skill rejects that rewrite and resolves the finding by the defend path, or the gate stays failing. |
| Accepted rewrite breaks the word budget or wpm ceiling | Fails D5 on the re-run; the rewrite is not shipped. |
| An override is used | Recorded with its reason; the gate result stays `fail` in frontmatter. |

## Testing

`tests/test_lint_script_language.py`, mirroring `tests/test_lint_prompt_sheet.py`.

Fixtures are **copies** of the four shipped scripts under `tests/fixtures/`, not reads from
`rgs-briefs/` — a fixture is a frozen input, and coupling the suite to the briefs directory would let
an unrelated new script break it.

**Calibration cases**, derived from the actual script text rather than asserted:

| Fixture | Expected |
|---|---|
| `let-kids-play-act` | fail D1 ×4; fail D5 ×1 (Hook 13w/3s ≈ 260 wpm); 1 `skipped` (re-hook, no range) |
| `let-kids-play-act-specialization` | fail D1 ×1 (re-hook); fail D5 ×2 (Hook ≈ 260, Setup 19w/5s ≈ 228); 1 `skipped` |
| `decline-the-next-level` | fail D1 ×2; **pass D5** (Dewey beat ≈ 171, inside ±2 tolerance) |
| `nobody-asked-the-kid` | **pass D1–D5** — the cleanest of the four |

All four fail D6, since none carries a `Gate E:` line. Correct: they predate the gate, and it
confirms the honesty lock fires rather than passing legacy output by default.

**Behavioral cases:**

- Parser handles all three VO-line forms, including the bare `[re-hook beat @ ~15s]: "…"` with no
  range group, and indented Build/Payoff sub-ranges.
- A file with no VO lines exits 2. A file with fewer VO lines than beat headings emits
  `partial-parse`.
- **Scope containment:** em-dashes in prose, Delivery notes, quote cards, and on-screen text plates
  do not fire D1 — the check most likely to regress into noise.
- **Heading en-dashes do not fire D1** (`(0–3s | 8 words)` is not a VO line).
- D5 fires on an over-stuffed beat and does **not** fire on an under-running one — a synthetic
  100 wpm Loop/CTA must pass.
- D5 emits `skipped`, not `pass`, for a beat with no computable range.
- D6 fails a script with no `Gate E:` line and passes one with a well-formed line.
- **Regression guard for the removed rhythm checks:** `decline`'s Hook/Loop mirror
  (*"It won't set him back."* twice) must produce **no** Gate D finding.

**App-side:**

- A failing gate lands in frontmatter and the stage still reaches `awaiting_review`.
- `approve_stage` raises on a failing gate without an override; succeeds with `override_reason` and
  records it.
- A linter that raises produces `status: error` and blocks approval.
- `Task` is present in the pipeline's `allowed_tools` default.

## Known limits

1. **n=4.** Every `[S]` rule and both numeric thresholds rest on four scripts and 27 lines. They want
   retuning as the corpus of shipped scripts grows. Calibrated, not validated.
2. **D6 cannot prove Gate E ran** (see above).
3. **The Nick Nimmin extension is unverified** — whether the corpus finding covers written VO lines
   or only the cut cannot be checked without `output/`.
4. **Gate E's no-touch annotation is only as good as the skill's self-classification.** A constraint
   the skill fails to annotate is a constraint the critic may rewrite. `unknown` defaults to
   no-touch to make that fail safe rather than silent.
