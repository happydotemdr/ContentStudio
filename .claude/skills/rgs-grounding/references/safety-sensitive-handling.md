# Safety-Sensitive Handling

Four research codes require handling beyond the standard `research-corpus-protocol.md` rules:
**R5** (suicide risk), **R11** (eating disorders/RED-S), **R12** (safeguarding/abuse), **R14**
(male eating disorders). This file is the binding protocol whenever a Grounding Brief cites any
of them — apply it in full, don't summarize it away under time pressure.

## Before you cite R5, R11, R12, or R14 at all

Flag it at the **Pairing Slate stage** (see `SKILL.md`), before the human commits to the
pairing — not after the full brief is written. R5 in particular carries a real production-time
cost: a mandatory help-resource line in a sub-60-second Short. The slate row should let the
human weigh whether the format even suits the topic before they pick it.

## R5 — Suicide risk

- Pair any suicide-related content with a help resource: **988 Suicide & Crisis Lifeline (US)**.
  This line goes in the Grounding Brief's "Safety handling" section AND must be flagged as a
  required element for `shorts-scripting` to actually include on-screen/in voiceover — it is
  not optional framing.
- Keep the framing non-sensational — no dramatic hooks built on this theme.
- Never collapse "protective for general youth" and "rising in elite/college athletes" into one
  number — these are different populations; name which one any statistic refers to. Concretely:
  the 2025 YRBS analysis (800k+ students) shows sport participation is protective against
  suicidal ideation/behavior in the general middle/high-school population; separately, the NCAA
  20-year analysis shows the *proportion of athlete deaths* attributable to suicide roughly
  doubled (~7.6% to ~15.3%) — but that same study found athlete suicide *incidence* is lower
  than the general college population. A proportion-of-deaths trend and a population-incidence
  rate are not interchangeable; don't let one stand in for the other on-screen.

## R11 / R14 — Eating disorders

- Frame around fueling and bone health, never around weight or appearance.
- Name the specific construct behind any prevalence number. R11 spans **three** distinct
  constructs, not two — collapsing them into a single range is exactly the error this rule
  exists to prevent:
  - **~5.6–7%** — DSM-IV clinical eating-disorder diagnosis (scoping review, ages 12–18).
  - **~19%** (Ghazzawi et al. 2024 meta-analysis, self-reported disordered eating) — the most
    defensible figure for on-screen use.
  - **up to ~65%** — a single small screening study (LEAF-Q, N=34, youth female soccer);
    screening-at-risk is not diagnosed prevalence, and this figure should be used only as a
    caveat about how screening thresholds inflate estimates, never as the headline number.
  Citing a bare percentage without naming which of these three it measures is a verify-policy
  violation, not a simplification.
- R14 covers male athletes specifically — screening tools validated on female populations
  under-detect male presentations (weight-cutting, muscle dysmorphia); don't generalize R11
  findings onto a male-athlete claim without checking R14 first.

## R12 — Safeguarding

- Frame around program-level structural safeguards a parent can actually check for (what to
  look for in a program), never around naming or implying specific individuals.
- Prevalence estimates depend entirely on which construct is measured, and the two constructs
  do not form one continuous range — treat them as separate figures, not two ends of a scale:
  - **~2–48%** — sexual abuse specifically (coach-athlete scoping review range).
  - **~65–84%** — any interpersonal violence broadly (the CASES study construct: psychological,
    physical, and sexual combined), rising with competitive level (68% recreational to 84%
    international).
  Always name the construct. Also flag, when citing SafeSport 2024 survey figures (e.g., 10.9%
  unwanted sexual contact, 78.4% emotional-harm indicators), that these describe **adults
  recalling their sport experience**, not a rate measured on today's minors.

## General rule across all four

None of R5/R11/R12/R14 exists to frighten. Each documents a real, well-documented pattern a
parent benefits from recognizing calmly. If a Grounding Brief's tone on one of these themes
reads as alarming rather than reassuring-and-informative, it violates `brand-voice-and-tone.md`
("relief over alarm") as much as it violates verify-policy — fix the framing, don't just soften
individual words.

## Grounding Brief "Safety handling" section — when to omit

If the brief doesn't touch any of these four codes, omit the "Safety handling" section from the
brief entirely — don't force a "not applicable" placeholder into every brief.
