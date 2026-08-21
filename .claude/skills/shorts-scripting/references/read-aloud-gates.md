# Read-aloud gates — Gate D and Gate E

Two gates on the finished script, deliberately asymmetric. **Gate D** is a free deterministic
linter you run over the artifact. **Gate E** costs an agent round-trip and asks the one question
no regex can answer: *does a person say this out loud?*

They replace step 9's old humanize pass, which was a self-attestation — the same turn, the same
model, and the same context that authored the script graded it, against a no-list of two phrases
and five words. **All four shipped scripts attest to passing it**
`[S] (rgs-briefs/2026-07-25-let-kids-play-act-script.md:29, rgs-briefs/2026-07-25-let-kids-play-act-specialization-script.md:29, rgs-briefs/2026-07-28-decline-the-next-level-script.md:234, rgs-briefs/2026-07-28-nobody-asked-the-kid-script.md:368 — each carries its own "Humanize pass" line)`,
and **all four still carry failures the baseline catalogues: three carry D1 or D5 findings, and the
fourth — clean against D1–D5 — still carries the contextual failures** (all four also fail D6, which
postdates them)
`[S] (docs/script-language-baseline.md, "Per-script VO-line inventory" and "Contextual failures — not Gate D's business")`.

**Both gates block emission** `[I]`. A finding is resolved, defended in writing, or explicitly
overridden with a stated reason — it is never quietly dropped.

---

## The Gate D / Gate E boundary

**Gate D checks what is wrong unconditionally** `[I]`. An em-dash in a spoken line is unspeakable
whatever the author intended; a beat at 260 wpm cannot be performed in its seconds. These are
mechanical facts about the text, so a deterministic checker is the right instrument.

**Gate E judges what is wrong only in context** `[I]`. Fragment rhythm, template sameness, and
contorted abstraction are failures when they are the model's default and features when they are a
choice. Telling those apart means reading the whole script, so it goes to a model.

### Why rhythm and template checks live in Gate E, and must stay there

**Gate D contains no rhythm check and no repeated-template check, and none may be added** `[I]`.
This is not an oversight or a phase-two backlog item — it is the load-bearing constraint of the
whole design, for two independent reasons:

- **Intent is invisible to a regex** `[C] (Nick Nimmin, IF-PD6XMjYY)`. The corpus rule this skill
  already carries is *"don't over-polish the VO line into textbook-perfect grammar; a little
  natural cadence is a feature"* (`references/script-intelligence-and-delivery.md:64-66`). Two
  shipped scripts invoke that citation **by name** to defend their own fragment closers
  (`decline-the-next-level-script.md:237-238`, `nobody-asked-the-kid-script.md:371-373`). A
  deterministic fragment check would fail lines the corpus explicitly licenses.
- **A template check would fire on a mechanic this skill mandates** `[C] (Jenny Hoyos,
  mhVDcqnxxaY)`. `SKILL.md` step 8 **requires** the Loop/CTA to mirror the Hook's phrasing;
  `decline-the-next-level` does exactly that, repeating *"It won't set him back."* verbatim across
  both beats. **A gate that blocks a mandated mechanic is worse than no gate** `[I]`.

Those contextual failures are real and shipped — negation-fragment closers in three of four
scripts, a fragment run at `nobody-asked-the-kid` PAYOFF line 86, the contorted abstraction *"That
offer moves his reason for playing outside the playing."* at `decline-the-next-level` SETUP line 73
`[S] (docs/script-language-baseline.md, "Contextual failures — not Gate D's business")`.
**Assigning them to Gate E rather than Gate D is a design judgment** `[I]`: Gate E can raise them,
and the author can resolve them **by defending them**. The gate forces the choice to be explicit;
it does not make the choice.

---

## Gate D — mechanical, deterministic

**Fires:** on every emitted script, before handoff to `voiceover-brief` and `visual-prompts` `[I]`.
**Blocks:** emission `[I]`.
**Scope:** **voiceover lines only** `[I]`. Prose, Delivery notes, verbatim quote cards, and
on-screen text plates legitimately use written punctuation and are never checked — extraction is
over the quoted spans of beat lines, which is also why the en-dash inside every `(0–3s | N words)`
heading never fires D1.

### Sub-beat lines — the only two legal shapes

A beat that needs more than one timed VO chunk (almost always Build/Value) declares its own total
range and word budget on the heading line, with no inline quote, and delegates to indented
sub-beat lines beneath it. Each sub-beat line is legal in exactly one of two shapes `[P]` (operator
decision, 2026-08-20, `docs/superpowers/plans/remediation/P13-skills-contracts.md` T6's "NEW
FINDING" block, resolving C-88b):

- **Range-first**: the range opens the line — `(8–18s | 20 words): "<VO line>"` `[P]`.
- **Label-first**: a short name opens the line, immediately followed by its range — `mechanism (18–28s | 11 words): "<VO line>"` `[P]`.

The parser (`scripts/lint_script_language.py`) recognises these via `SUBRANGE_RE` and
`LABEL_FIRST_SUBRANGE_RE` respectively — both require the line's own `| N words` budget group,
which is the author's assertion that the line is a beat line at all. **A line matching neither
shape is refused loud, as a blocking PARSE finding naming the line, not silently dropped** `[I]`.
The most common way to write a refused line by accident is a heading whose VO text sits on the
*next* line with no range or label at all — that is not a third legal shape, however natural it
reads; every sub-beat line must open with one of the two shapes above.

### The six checks

| Check | Rule | Provenance |
|---|---|---|
| D1 | No em-dash or en-dash in a VO line | **`[S]`** — 7 lines across 3 scripts; headline case `decline-the-next-level` BUILD/VALUE line 75 (`docs/script-language-baseline.md`, "D1 evidence") |
| D2 | No semicolons, parentheticals, or bracketed asides in a VO line | **`[I]`** — zero hits in the 27-line inventory; a regression guard, honestly unevidenced |
| D3 | Fingerprint-phrase and buzzword no-list | **`[C] (Romayroh, ErCV5czVK1g)`** — carried forward from `references/script-intelligence-and-delivery.md:40-43`, not derived from this repo's output |
| D4 | No unspeakable tokens in a VO line (`&`, `n=142`, `12(3):424–433`, `§`) | **`[I]`** — zero hits in the 27-line inventory; a regression guard, honestly unevidenced |
| D5 | No beat exceeds a **170 wpm ceiling** (words ÷ duration), ±2 tolerance | **`[S]`** — 3 over-ceiling beats across 2 scripts; both 07-25 Hooks at ≈260 wpm, `specialization` Setup at ≈228 (`docs/script-language-baseline.md`, "D5 evidence") |
| D6 | The artifact carries a well-formed `Gate E:` line, **filled in** — a value still wrapped in `<…>`/`[…]`, or still carrying the output contract's `|` bars, is the unfilled slot and is rejected | **`[I]`** — the honesty lock; no line can evidence the absence of a line |

**D1 and D5 are the only two checks marked `[S]`, because they are the only two with a real
shipped line behind them** `[S] (docs/script-language-baseline.md, "Rule index")`. Marking D2, D4,
or D6 `[S]` would treat a rule's plausibility as if it were evidence — exactly the laundering the
marker exists to prevent. **Any future edit that upgrades one of them to `[S]` must first add a
real evidencing line to the baseline's inventory, not just assert the upgrade** `[I]`.

### On D5 — a ceiling, not a band

**Under-running is a legitimate authorial choice; over-running is a production failure** `[C]
(Kallaway, ZM3elcBE48I)`. `decline-the-next-level` runs its Loop/CTA at ~103 wpm on purpose and
justifies the slack as *"deliberate breathing room for the half-second pauses that make a key word
land."* D5 therefore flags only the ceiling. The **script total** is separately checked against the
full 150–170 band `[I]`, where slack is meaningful.

`decline`'s Dewey sub-beat sits at ~171 wpm. The ±2 tolerance makes that a deliberate pass rather
than an accidental one `[S] (docs/script-language-baseline.md, decline BUILD/VALUE line 77)`.

**A beat whose timing cannot be computed is reported as `skipped`, never as a pass** `[I]`. The
old-format `[re-hook beat @ ~15s]: "…"` line carries no `(range | words)` group, so D5 cannot rate
it. Read the skip and decide; an unchecked beat is a known unknown, not a clean one.

**A script where *no* beat is ratable fails outright** `[I]`. One skip is a known unknown; a whole
script of skips is a format failure — D5 read nothing, and a check that read nothing must not
reach the approval boundary looking like a check that passed. The usual cause is colon timestamps
(`(0:00–0:03 | 8 words)`) or `(0–3 sec …)`; the linter only reads whole seconds in the form
`(0–3s | 8 words)`. Fix the headings, do not override the finding.

### Running it — the two-mode rule

```bash
python scripts/lint_script_language.py <path-to-script.md>
```

Exit 0 = pass, 1 = findings, 2 = parse error.

- **Standalone mode** `[I]` (you have `Bash`): run the command and **record the real result** in the
  output contract's `GATES` block `[I]`.
- **Pipeline mode** `[I]` (app-driven): `Bash` is denied on pipeline turns by design, so you cannot run
  it. Record **`deferred — app-run`** `[I]`. The app runs the linter post-turn and folds the
  result into the artifact's frontmatter.

**Never record a pass you did not observe** `[I]`. `deferred — app-run` is the honest third value
and exists precisely so that "I could not run it" never has to be written as "it passed." This is
the failure `visual-prompts`' Gate C shipped with, and it is not repeated here.

**Exit 2 is not a pass** `[I]`. Zero voiceover lines parsed means the linter is not seeing text
that is there — fix the script's format and re-run. A `partial-parse` finding means the same thing
for one beat, and fires in two shapes `[I]`:

- a beat heading that yielded **no** quoted line anywhere under it;
- a beat whose `| N words` declaration is **materially** larger than the words actually extracted
  from it — the dropped-text check. Under-extraction is the danger and it is silent by nature: a
  swallowed sub-beat takes its own dashes and its own word count out of every check at once. The
  threshold is a shortfall of **at least 3 words *and* at least 25% of the declaration**, so an
  author's rounding does not fire and a lost span does. An over-count never fires — a heading
  claiming fewer words than the line speaks is a stale number, not evidence of a parser miss.

**Write the beat's real word count in its heading** `[I]`. That number is the only independent
witness the linter has to how much spoken text a beat should contain; a heading left at a guess
disarms the dropped-text check on that beat.

---

## Gate E — fresh Opus critic

**Fires:** on every emitted script, after Gate D is clean or its findings are resolved `[I]`.
**Blocks:** emission until every finding is resolved, defended, or overridden `[I]`.

Dispatch a **fresh `general-purpose` agent with `model: opus`** `[I]`. It judges the artifact and
not the reasoning, and it is instructed to **find the failure, not approve**. This mirrors
`midjourney-prompting`'s Gate B and is a net-new pattern for this repo — **no corpus finding backs
the dispatch mechanism itself** `[I]`; what it backs is the four judgments below.

### The payload contract

Send the critic **exactly three things per beat** `[I]`: the VO line, its beat timing, and a
**per-line no-touch annotation** from this closed vocabulary:

| Annotation | Meaning | Rewritable? |
|---|---|---|
| `verbatim-quote` | Spoken text quoted word-for-word from a source (e.g. an 1886 Charlotte Mason fragment that is deliberately written prose) | no |
| `citation` | Carries an attribution, date, or study reference that must survive | no |
| `uncuttable` | A line the brief or grounding artifact fixed verbatim | no |
| `lexicon-screened` | Wording already screened against a constraint (e.g. a blame-audit pass that removed a second-person pronoun) | no |
| `free` | No binding constraint; rewrite at will | **yes** |
| `unknown` | The skill could not classify it | no |

**Delivery notes, Alternates, and the grounding beat map are withheld** `[I]`. The critic must see
the **constraints** without seeing the **rationale** — an agent that has read why a choice was made
will rationalize it, and rationale is exactly what makes a written line look justified.

**Annotating is this skill's job, because this skill wrote the constraints into the document**
`[I]`. **A line you cannot confidently classify is annotated `unknown`, and `unknown` is treated as
no-touch** `[I]` — that default makes a mis-annotation fail safe rather than silent.

### No-touch zones

**The critic may not rewrite a line annotated anything other than `free`** `[I]`. A finding on such
a line is **still reported** — the constraint protects the wording, not the line's quality — but
the proposed rewrite must **restructure around** the constraint.

Worked example. The Côté line fails D1 and reads as written prose:

> *"A 2009 international position stand — Côté, Lidor and Hackfort — reports that kids who sample
> many sports still tend to reach elite performance."*
> `[S] (docs/script-language-baseline.md, decline-the-next-level BUILD/VALUE line 75)`

It is annotated `citation`. The fix resequences it into two sentences:

> *"Back in 2009, three sport psychologists put out a position stand. Kids who sample many sports
> still tend to reach elite level."*

**Never by dropping the attribution** `[I]`. A rewrite that resolves a read-aloud finding by
deleting a citation has traded one defect for a worse one.

**If the critic proposes a rewrite that touches a no-touch line, reject that rewrite** `[I]` and
resolve the finding by the defend path below, or leave the gate failing.

### Verbatim dispatch prompt

Substitute the bracketed values. **Do not soften the adversarial framing** `[I]` — a validator told
to "check" returns "looks good."

```
You are reviewing the voiceover lines of a YouTube Short script before it goes to voiceover
production. Your job is to FIND THE FAILURE, not to approve it. Assume it is flawed and locate
the flaw. "Looks good" is a failed review — if you genuinely find nothing, say which specific
checks you ran that came back clean.

The one question you are answering: DOES A PERSON SAY THIS OUT LOUD?

These lines will be spoken by a narrator over B-roll. They are not read on a page. A line that
scans perfectly in text and has no spoken realization is a failure even though nothing is
grammatically wrong with it.

THE SCRIPT — one row per beat: beat, timing, no-touch annotation, VO line.
[for each beat: BEAT NAME (Xs–Ys | N words) [annotation]: "the VO line"]

NO-TOUCH RULE — binding:
  Any line annotated `verbatim-quote`, `citation`, `uncuttable`, `lexicon-screened`, or
  `unknown` carries a constraint you cannot see the reason for. You MAY report a finding on
  such a line. You MAY NOT propose a rewrite that drops, paraphrases, or relocates the
  constrained material — an attribution, a quoted phrase, or a fixed wording. Restructure
  AROUND the constraint instead: resequence into two sentences, move the attribution to the
  front, split the beat. Only a line annotated `free` may be rewritten without restriction.

Judge on exactly these four things:

1. WRITTEN-REGISTER SYNTAX. Appositives, nominalizations, abstract subjects, and any
   construction that exists because it is easy to punctuate rather than easy to say. Quote the
   construction and name what a narrator would have to invent to perform it.
2. FRAGMENT RHYTHM AND TEMPLATE SAMENESS. Read the script as a whole. Is a cadence CHOSEN here,
   or is it the default everywhere? A repeated closer shape across every beat is a tell; the
   same shape used once for emphasis is craft. Say which one you are looking at and why.
   NOTE: this script's Loop/CTA is REQUIRED to mirror the Hook's phrasing. That specific
   repetition is a mandated mechanic, not a finding.
3. PERFORMED VS. REAL IMPERFECTION. Small imperfections are wanted — a manufactured dropped
   article or a bolted-on "look," is not the same thing as natural cadence. Flag imperfection
   that reads as staged.
4. ONE-BREATH SPEAKABILITY. At the stated timing, can each line be spoken in one breath without
   the narrator rushing or running out of air mid-clause? Name the clause that breaks first.

FOR EACH FINDING, RETURN EXACTLY THREE THINGS:
  a. The offending line, quoted.
  b. Why it fails read-aloud — the specific mechanism, not "sounds unnatural."
  c. ONE concrete rewrite: the full replacement line, not a description of changes. If the line
     is annotated no-touch, your rewrite must preserve the constrained material verbatim.

Be specific. "Tighten this" is useless; "the appositive between the dashes has no spoken
realization — a narrator has to invent a pause structure the text does not give them" is useful.

DELIVERABLE FORMAT (hard limit ~1,500 tokens):
- Findings: bulleted facts with file:line citations where applicable
- Recommendation: 1–3 sentences
- Open questions: only if genuinely blocking

DO NOT:
- Paste full file contents or reproduce tool output verbatim
- Restate the task or narrate your process
- Include a preamble, closing summary, or sign-off
```

### Resolution paths

**A Gate E finding is resolved by exactly one of three things** `[I]`:

1. **Accept the rewrite.** Take the critic's replacement line as written.
2. **Author a different fix.** The critic found a real problem and proposed a bad solution.
3. **Defend the line in writing.** State in Delivery notes *why* the construction is deliberate,
   citing either its `[C]` corpus justification (a chosen fragment cadence cites `[C] (Nick Nimmin,
   IF-PD6XMjYY)`) or the binding constraint that fixed the wording. Record it in the `GATES` block
   as `N defended`.

**The third path is not an escape hatch — it is what lets Gate E block without becoming
unresolvable** `[I]`. Without it, a no-touch line with a real read-aloud problem would deadlock the
gate forever. A defence is a written argument with a citation, not the word "intentional."

**Any accepted rewrite is re-checked against the beat's word budget (±2 words) and Gate D is
re-run over the whole script before emitting** `[I]`. A read-aloud fix that adds six words breaks
the wpm ceiling, and a rewrite that introduces an em-dash re-fails D1 — neither is caught unless
you re-run.

**An override is recorded with its reason and the gate result stays failing** `[I]`. Write it as
`overridden: <reason>` in the `GATES` block. An override is a decision on the record, not a pass.

---

## Known limits

**State these when they bear on a call you are making; do not let them fade into the background**
`[I]`.

1. **n=4.** Every `[S]` rule and both numeric thresholds rest on four scripts and 27 voiceover
   lines — the whole evidence base, inventoried in `docs/script-language-baseline.md` ("Scope and
   limits"). **Treat both thresholds as calibrated against that sample, not validated against a
   larger one, and retune them as more scripts ship** `[I]`. (This limit is `[I]`, not `[S]`, on
   purpose: it is a constraint *on* the `[S]` rules, and no shipped line can violate it.)
2. **D6 cannot prove Gate E ran** `[I]`. A skill that skipped Gate E can still write
   `Gate E: pass` — the same self-attestation this whole design exists to replace, reintroduced for
   the more expensive gate. D6 raises the cost of the omission **from silent to deliberate, and no
   further**. Do not treat a present `Gate E:` line as evidence a critic was dispatched. D6's
   placeholder rejection buys exactly one thing on top of that: it removes the *zero-cost* defeat
   in which the output contract is pasted unfilled and the lock is satisfied by a template nobody
   read `[I]`. Writing a false `pass` is now the cheapest way past the lock, and it is still
   available.
3. **The Nick Nimmin extension is unverified** `[C] (Nick Nimmin, IF-PD6XMjYY)`. `output/` is not
   present in this checkout, so the original finding cannot be checked. It is possible it concerns
   only *the cut* — filler, breath, editing choices — and that its extension to written VO-line
   text is `references/script-intelligence-and-delivery.md`'s own gloss. Both gates are built as if
   the extension holds; say so if you lean on it.
4. **Gate E's no-touch annotation is only as good as this skill's self-classification** `[I]`. A
   constraint you fail to annotate is a constraint the critic may rewrite. `unknown` defaults to
   no-touch so that failure is safe rather than silent, but nothing catches a line you confidently
   annotated `free` that was not.
5. **D5 under-counts numerals, and this genre is full of them** `[I]`. The linter counts
   whitespace-separated tokens, so `$1,250,000` is one word and `2009` is one word — spoken, they
   are six and three. A stat-heavy beat therefore rates *slower* than it will actually be
   performed, and D5 systematically under-fires on exactly the lines this brand writes most
   (`"A 2009 international position stand…"`, `"A review of six thousand athletes…"`). **The
   counting is not changed, because the 170 wpm ceiling was calibrated against it** — moving one
   without the other would silently retune the gate. **Say the numeral out loud and count what you
   hear before trusting a passing D5 on a beat carrying figures, dates, or money** `[I]`.
