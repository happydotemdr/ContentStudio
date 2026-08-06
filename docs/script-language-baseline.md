# Script-Language Baseline

## Purpose

This file is the citation target for the **`[S]` (script-baseline)** provenance marker,
introduced by `docs/superpowers/specs/2026-08-06-script-language-naturalness-design.md`. `[S]`
means *evidenced by an observed failure in this repo's own shipped output, cited by file and
beat* — not corpus-derived (`[C]`), not general craft judgment (`[I]`), and not a web-verified
tool/policy fact (`[T]`). It exists because this project's central rule is that every normative
claim traces to a real source, and a naturalness rule set with no corpus coverage of
spoken-register syntax would otherwise have nothing legitimate to cite.

**The constraint that makes the marker mean anything: an `[S]` rule that cannot name a real
shipped line violating it does not ship — it is marked `[I]` instead.** This is not a hypothetical
guard. The design spec's own first draft broke it immediately: it marked two zero-hit regression
guards (the semicolon/parenthetical check and the unspeakable-token check) `[S]` with no
evidencing line behind either. That was corrected in the spec's revision note before this
document was written, and the correction is carried forward here, against the same document that
introduced the mistake. Every `[S]` citation below points at a specific script, beat, and line
number in the inventory in Section 3. If a rule's evidence row is empty, the rule is not `[S]`.

## Scope and limits

- **27 voiceover lines across 4 scripts.** This is the entire evidence base. No other shipped
  script exists to draw from.
- **n=4 is thin.** Every threshold and every `[S]` rule in this document rests on four scripts.
  They are calibrated against this sample, not validated against a larger one, and they want
  retuning as the corpus of shipped scripts grows.
- **`output/` is absent from this local checkout.** The Nick Nimmin finding
  (`[C] (Nick Nimmin, IF-PD6XMjYY)` — "don't over-polish the VO line into textbook-perfect
  grammar; a little natural cadence is a feature") is cited by the shipped scripts themselves to
  defend two of the constructions in Section 5, but its *original scope* cannot be checked here:
  it is possible the source video's finding concerns only the cut (filler, breath, editing
  choices) and that its extension to written VO-line text is the reference file's own gloss, not
  the corpus's. That question is not resolvable without `output/`'s transcripts, so it is recorded
  as an open gap rather than silently assumed either way.

## Rule index

| Check | Rule | Marker | Evidence |
|---|---|---|---|
| D1 | No em-dash or en-dash in a VO line | **`[S]`** | 7 lines, 3 scripts — see below |
| D2 | No semicolons, parentheticals, or bracketed asides in a VO line | **`[I]`** | zero hits — regression guard, honestly unevidenced |
| D3 | Fingerprint-phrase and buzzword no-list | **`[C]` (Romayroh, ErCV5czVK1g)** | carried forward from the corpus, not this baseline |
| D4 | No unspeakable tokens in a VO line (`&`, `n=142`, `12(3):424–433`, `§`) | **`[I]`** | zero hits — regression guard, honestly unevidenced |
| D5 | No beat exceeds a 170 wpm ceiling (±2 tolerance) | **`[S]`** | 3 beats, 2 scripts — see below |
| D6 | The artifact carries a well-formed `Gate E:` line | **`[I]`** | the honesty lock — no line can evidence the absence of a line |

**D1 and D5 are the only checks with a real shipped violation behind them, and they are the only
checks marked `[S]`. D3 is carried forward from the corpus as `[C]` — it was not derived from this
repo's output at all, and predates Gate D. D2, D4, and D6 have no evidencing line anywhere in the
27-line inventory below and are therefore marked `[I]`, not `[S]`.** This is the same rule stated
in Purpose, applied: the design spec's first draft marked D2 and D4 (there called out as "two
zero-hit regression guards") `[S]` in error, which is exactly the laundering the marker exists to
prevent — treating a rule's *plausibility* as if it were *evidence*. The correction stands here
against the spec's own authorship, not just in the abstract: this document ships D2, D4, and D6 as
`[I]`, and any future edit that upgrades one of them to `[S]` must first add a real evidencing line
to Section 3, not just assert the upgrade.

### D1 evidence — 7 dash-bearing lines

| Script | Beat | Line | Construction |
|---|---|---|---|
| `2026-07-25-let-kids-play-act-script.md` | BUILD/VALUE | 13 | em-dash marking a written parenthetical ("…with a natural stopping point. The other has none — because nothing's actually being made.") |
| `2026-07-25-let-kids-play-act-script.md` | re-hook | 14 | em-dash marking a written aside ("…bought up every oil press in town — but once he had them all, he charged whatever he wanted.") |
| `2026-07-25-let-kids-play-act-script.md` | PAYOFF | 15 | em-dash as a result/contrast pivot ("Because that's the monopoly move — so the proposal counts…") |
| `2026-07-25-let-kids-play-act-script.md` | LOOP/CTA | 16 | em-dash setting off a rhetorical question ("When 'youth sports' means an app — what's really being sold?") |
| `2026-07-25-let-kids-play-act-specialization-script.md` | re-hook | 14 | em-dash as a contrast pivot ("…there's no evidence early specializing is needed for elite success — just extra injury and burnout risk.") |
| `2026-07-28-decline-the-next-level-script.md` | BUILD/VALUE | 75 | em-dash as a written appositive naming three authors ("A 2009 international position stand — Côté, Lidor and Hackfort — reports that…") — the design spec's own headline example |
| `2026-07-28-decline-the-next-level-script.md` | BUILD/VALUE | 77 | em-dash as a contrast pivot ("…isn't more serious play — it's constrained labor.") |

### D5 evidence — 3 over-ceiling beats

| Script | Beat | Line | Rate | Detail |
|---|---|---|---|---|
| `2026-07-25-let-kids-play-act-script.md` | HOOK | 11 | ≈260 wpm | 13 words in a 3s beat |
| `2026-07-25-let-kids-play-act-specialization-script.md` | HOOK | 11 | ≈260 wpm | 13 words in a 3s beat |
| `2026-07-25-let-kids-play-act-specialization-script.md` | SETUP | 12 | ≈228 wpm | 19 words in a 5s beat |

Both HOOK failures compute to the same rate because both scripts open with a 13-word line against
an identical 3-second window — the ceiling violation is structural to the 07-25 pair's opening
beat, not a coincidence of wording.

## Per-script VO-line inventory

All 27 lines below were generated by running `parse_script`, `beat_wpm`, and `word_count` from
`scripts/lint_script_language.py` directly against `tests/fixtures/script_*.md` (see the brief's
Step 1 command). Every line of text is copied verbatim from that output; none is paraphrased or
reconstructed from the shipped scripts' prose. Line numbers refer to the fixture file, which is an
unmodified copy of the shipped script and carries the same line numbers.

### `2026-07-25-let-kids-play-act-script.md` (fixture: `tests/fixtures/script_let_kids_play_act.md`)

6 VO lines, 4 dash-bearing, 1 over-ceiling beat, 1 beat with no computable range.

- **HOOK** (line 11, 13w, 260 wpm) — **fail, D5**: 260 wpm exceeds the 170 ceiling (+2 tolerance); more words than fit in the beat.
  > "Why would a federal proposal count your kid's registration app as 'youth sports'?"
- **SETUP** (line 12, 13w, 156 wpm) — pass.
  > "Because 2,300 years ago, Aristotle named two very different ways to make money."
- **BUILD/VALUE** (line 13, 25w, 75 wpm) — **fail, D1**: em-dash marking a written parenthetical.
  > "One kind earns money by making or trading something people need, with a natural stopping point. The other has none — because nothing's actually being made."
- **re-hook** (line 14, 24w, no range) — **fail, D1**: em-dash marking a written aside. (This beat is also the old-format `[re-hook beat @ ~15s]:` form, which carries no `(range | words)` group — D5 cannot compute a rate for it and reports it as `skipped`, not `pass`.)
  > "His proof: a trader who quietly bought up every oil press in town — but once he had them all, he charged whatever he wanted."
- **PAYOFF** (line 15, 22w, 132 wpm) — **fail, D1**: em-dash as a result/contrast pivot.
  > "Because that's the monopoly move — so the proposal counts leagues, facilities, and apps the same way, with forced sellbacks and fee refunds."
- **LOOP/CTA** (line 16, 10w, 86 wpm) — **fail, D1**: em-dash setting off a rhetorical question.
  > "When 'youth sports' means an app — what's really being sold?"

### `2026-07-25-let-kids-play-act-specialization-script.md` (fixture: `tests/fixtures/script_specialization.md`)

6 VO lines, 1 dash-bearing, 2 over-ceiling beats, 1 beat with no computable range.

- **HOOK** (line 11, 13w, 260 wpm) — **fail, D5**: 260 wpm exceeds the 170 ceiling (+2 tolerance); more words than fit in the beat.
  > "Multi-sport NFL players had longer, safer careers than the ones who specialized early."
- **SETUP** (line 12, 19w, 228 wpm) — **fail, D5**: 228 wpm exceeds the 170 ceiling (+2 tolerance); more words than fit in the beat.
  > "Over 260 years ago, Rousseau warned about trading a kid's present joy for a future that might never come."
- **BUILD/VALUE** (line 13, 19w, 57 wpm) — pass.
  > "That's the exact trade a family makes cutting three sports down to one by age nine, chasing 'the path.'"
- **re-hook** (line 14, 26w, no range) — **fail, D1**: em-dash as a contrast pivot. (Old-format re-hook line with no `(range | words)` group; D5 reports this beat `skipped`, not `pass`.)
  > "But the medical establishment's own position on this is blunt: there's no evidence early specializing is needed for elite success — just extra injury and burnout risk."
- **PAYOFF** (line 15, 18w, 108 wpm) — pass.
  > "A review of six thousand athletes found the twist: early specializing predicts junior success, not senior, world-class success."
- **LOOP/CTA** (line 16, 8w, 69 wpm) — pass.
  > "So does specializing early actually get them there?"

### `2026-07-28-decline-the-next-level-script.md` (fixture: `tests/fixtures/script_decline.md`)

7 VO lines, 2 dash-bearing, 0 over-ceiling beats (the cleanest of the four for D5 — its own
timing table runs the Dewey sub-beat at ~171 wpm, inside the ±2 tolerance, a deliberate pass
rather than an accidental one).

- **HOOK** (line 72, 7w, 140 wpm) — pass.
  > "It won't set him back. Not athletically."
- **SETUP** (line 73, 14w, 168 wpm) — pass. (This line is the contorted-abstraction example discussed in Section 5 — Gate D has no check for it and correctly does not fail it here.)
  > "That offer moves his reason for playing outside the playing. Dewey saw it coming."
- **BUILD/VALUE** (line 75, 28w, 168 wpm) — **fail, D1**: em-dash as a written appositive naming three authors, with no spoken realization.
  > "A 2009 international position stand — Côté, Lidor and Hackfort — reports that kids who sample many sports still tend to reach elite performance. Late focusers tend to catch up."
- **re-hook** (line 76, 8w, 160 wpm) — pass.
  > "But the offer isn't really about your kid."
- **BUILD/VALUE** (line 77, 20w, 171 wpm) — **fail, D1**: em-dash as a contrast pivot. (171 wpm is inside the ±2 ceiling tolerance and does not itself fail D5.)
  > "Dewey named this in 1916. An activity done for a result outside itself isn't more serious play — it's constrained labor."
- **PAYOFF** (line 78, 24w, 144 wpm) — pass. (Contains the negation-fragment closer discussed in Section 5.)
  > "The next tier exists because the industry needs a next tier to sell. Not because he cleared a checkpoint. You're allowed to decline it."
- **LOOP/CTA** (line 79, 12w, 103 wpm) — pass.
  > "You're not taking something away from him. It won't set him back."

### `2026-07-28-nobody-asked-the-kid-script.md` (fixture: `tests/fixtures/script_nobody_asked.md`)

8 VO lines, 0 dash-bearing, 0 over-ceiling beats — the cleanest of the four scripts against
Gate D end to end.

- **HOOK** (line 79, 8w, 160 wpm) — pass.
  > "Best part was the mud. Everybody fell over."
- **SETUP** (line 80, 13w, 156 wpm) — pass.
  > "Kids do that. They come home and hand over the whole account, unprompted."
- **BUILD/VALUE** (line 82, 15w, 150 wpm) — pass.
  > "Charlotte Mason wrote that down in 1886. She called it narration. Every child does it."
- **re-hook** (line 83, 8w, 160 wpm) — pass.
  > "But she also named what happens to it."
- **BUILD/VALUE** (line 84, 22w, 147 wpm) — pass.
  > "Her words: 'we see nothing in this but Bobbie's foolish childish way.' A hundred and forty years old. It was never yours."
- **PAYOFF** (line 86, 30w, 150 wpm) — pass. (Contains the fragment-run example discussed in Section 5.)
  > "A 2015 George Washington University study asked hundreds of young soccer players what makes sport fun. Eighty-one things. Eleven factors. Trying hard came first. Winning isn't one of the eleven."
- **PAYOFF** (line 87, 19w, 163 wpm) — pass. (Contains the negation-fragment closer discussed in Section 5.)
  > "Nothing in the system has a field for that. You were handed a standings sheet. Not a report card."
- **LOOP/CTA** (line 88, 12w, 144 wpm) — pass.
  > "Ask what the best part was. Then believe the answer. It's free."

## Contextual failures — not Gate D's business

The three constructions below appear in the shipped scripts and read as written prose rather than
speech, exactly like the D1/D5 failures above. They are **not** Gate D findings, and no future
edit should add a Gate D check for them. Whether a fragment or an abstraction is a deliberate
authorial choice or the model's default rhythm is a question about *intent*, and intent is not
visible to a regex — a deterministic linter can only ever see the token, never the reason it is
there. That distinction is Gate E's territory (a fresh model critic reading the whole script), not
Gate D's.

- **Negation-fragment closers**, appearing across three of the four scripts:
  - *"Not athletically."* (`2026-07-28-decline-the-next-level-script.md`, HOOK, line 72)
  - *"Not because he cleared a checkpoint."* (`2026-07-28-decline-the-next-level-script.md`, PAYOFF, line 78)
  - *"Not a report card."* (`2026-07-28-nobody-asked-the-kid-script.md`, PAYOFF, line 87)
- **Fragment runs as rhythm**:
  - *"Eighty-one things. Eleven factors."* (`2026-07-28-nobody-asked-the-kid-script.md`, PAYOFF, line 86)
- **Contorted abstraction that reads fine and speaks badly**:
  - *"That offer moves his reason for playing outside the playing."* (`2026-07-28-decline-the-next-level-script.md`, SETUP, line 73)

**The first two of these — the negation-fragment closers and the fragment runs — are already
defended in the shipped scripts themselves**, by name, with a corpus citation:
`references/script-intelligence-and-delivery.md:64-66` instructs *"don't over-polish the VO line
into textbook-perfect grammar; a little natural cadence is a feature"* `[C] (Nick Nimmin,
IF-PD6XMjYY)`, and both `decline-the-next-level-script.md:237-238` and
`nobody-asked-the-kid-script.md:371-373` invoke it by name in their Delivery notes. **This
document does not override that rule**, and no Gate D check should be written that would fail
either of those two constructions — doing so would contradict a citation the shipped output
already carries and relies on. The third construction, the contorted abstraction, is not defended
by that citation anywhere in the shipped scripts; it is simply undefended prose that Gate E is
positioned to catch and Gate D is not built to see.

As noted in Scope and limits, whether `[C] (Nick Nimmin, IF-PD6XMjYY)` was ever meant to cover
*written VO-line text* at all — as opposed to only the cut — cannot be checked from this
checkout, because `output/` is not present locally.
