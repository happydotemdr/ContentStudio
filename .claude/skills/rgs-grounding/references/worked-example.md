# Worked Example: rgs-grounding

> This example illustrates rules already marked in this skill's other reference files and carries no independent normative weight. Where a line here restates a rule, the marker lives
> on the rule, not on the illustration — do not copy an unmarked line out of this file into a
> real brief as if it were sourced `[I]`.

A full run of `rgs-grounding` against the topic "why so many travel-sport kids quit around age
13," from Pairing Slate through the saved Grounding Brief. Reproduced from an actual test
invocation (see the implementation plan's Task 8) — not a hypothetical.

## Pairing Slate: why so many travel-sport kids quit around age 13

1. **Ellen Key × R8 (attrition & dropout)** — Key's "soul murder" mechanism (over-structuring extinguishes the native desire it was meant to cultivate) maps directly onto R8's finding that declining enjoyment is the field's strongest, most-cited dropout driver.
   - Archetype: A1
   - Quotability: paraphrase-caution
   - Safety flag: none
   - Recency flag: none (Key not used in any prior brief; only 1 prior brief exists, using Veblen × F4)

2. **Alfred Adler × R8 (attrition & dropout)** — Adler's "pampered child, unprepared for real difficulty" mechanism (a child never conditioned to tolerate setbacks quits rather than push through) also pairs with R8, closer to the "social pressure" leg of the finding than the "lack of enjoyment" leg.
   - Archetype: A1
   - Quotability: paraphrase-caution
   - Safety flag: none
   - Recency flag: none

3. **Plutarch (attributed) × R3 (burnout & overtraining)** — R8's own synthesis names burnout (R3) as an upstream driver of dropout; Plutarch's "rest is the sauce of labour" gives an exhaustion-based alternative to the boredom-based framing above, and is quote-ok (a real tonal/archetype alternative).
   - Archetype: A1
   - Quotability: quote-ok
   - Safety flag: none
   - Recency flag: none

Non-interactive fallback applied: proceeding with row 1 (Ellen Key × R8) as instructed, with rows 2–3 carried into the brief's "Alternates considered" appendix.

---

---
date: 2026-07-25
topic: "why so many travel-sport kids quit around age 13"
thinker: "Ellen Key"
concept: "Soul murder — excessive structured demand extinguishes the desire it means to cultivate"
research_codes: [R8]
archetype: A1
status: candidate
---

# Grounding Brief: why so many travel-sport kids quit around age 13

## Pairing
- **Thinker:** Ellen Key, *The Century of the Child* (1900) — "soul murder" [THINKER: Ellen Key,
  The Century of the Child, paraphrase-caution]
- **Research:** "Determining factors of sports dropout of young scholars" (2024, ages 8–13) /
  Changing the Game Project–Aspen Institute synthesis, R8 (attrition & dropout) — psychosocial
  factors (social pressure, parental expectations, lack of enjoyment) as the strongest
  predictors of quitting, dropout clustering in the early teens [RESEARCH: 2024 cross-sectional
  cohort (PMC11300246) / Aspen Institute Project Play, Quality: Medium (peer-reviewed driver) /
  Low–Medium (the "70%" figure specifically)]
- **Why this pairing:** Key's core claim is that a system built to instill a love of learning can,
  through overstructuring, extinguish the very appetite it was meant to build. R8's research
  finds declining enjoyment ("not fun anymore") is the field's most robust driver of youth sport
  dropout. The parallel: Key's "soul murder" mechanism — structure destroying the native desire
  it was supposed to cultivate — is a plausible century-old naming of the same process R8
  documents in sport: a system that over-structures a child's early experience can be the thing
  that kills the enjoyment it depended on, not an outside threat to it — an interpretive echo,
  not a claim R8's sources cite Key.

## Hook
Open on Key's 1900 image, paraphrased in voiceover (paraphrase-caution — do not put on a quote
card): a child arrives with a natural "desire for knowledge, the capacity for acting by oneself"
— and by the end of years spent inside a rigid, adult-run system, that native appetite has, in
Key's words, simply "disappeared... the annihilation of once existent matter." Key was writing
about schools, not sport — but land the same image on a travel-sport career: a kid who showed up
at six wanting nothing but to play, run through years of adult-directed practices, drills, and
standings, and arrives at thirteen with the desire itself gone, not just the schedule.

## Turn
Name it plainly: this isn't the kid "losing interest" out of nowhere, and it isn't about talent
running out — it's the same "soul murder" mechanism Key named over a century ago, now running on
travel-team practice plans instead of school curricula. The system (the structured,
adult-directed training pipeline) is what wears down the appetite it depends on — not an
outside distraction pulling the kid away from it.

## Payoff
Use R8's own Content Hooks rather than re-deriving a number: "The #1 reason kids quit sports
isn't talent or time — it's that it stopped being fun. That one's rock-solid." Per this file's
own cautionNote and the research-corpus-protocol's hedging rule for R8: lead with the driver
(declining enjoyment, social pressure, and parental expectations — the peer-reviewed finding
from the 2024 ages-8–13 cross-sectional cohort), and hedge the famous "~70% quit sports by 13"
number explicitly on-screen — it traces to a National Alliance for Youth Sports poll, not a
peer-reviewed longitudinal cohort, and Aspen Institute Project Play treats it as approximate/
overstated. Second available hook if a beat needs it: "You've heard '70% quit by 13.' The reason
(not fun) holds up. The exact number? Researchers say it's shakier than it sounds." Frame as
association, not causation — these are cross-sectional/poll-based findings, not a controlled
trial of what causes dropout.

## Reframe
It was never about your kid losing talent, drive, or commitment — that's the good news. What
actually wears a kid's love of the game down is the structure itself, running the same
appetite-destroying process Key named in schools 125 years ago. Naming it is what breaks its
grip: the fix isn't a pep talk about grit, it's protecting the parts of the experience — play,
autonomy, low-stakes fun — that the structure has been quietly squeezing out since age six.

## Verification record
- Thinker source opened:
  `output/thinkers/anchorandwave/ellen-key/key-century-of-the-child.cleaned.md`, Chapter V
  ("Soul Murder In The Schools"), lines 687–691 — confirmed present, text matches the
  pairing-map row exactly: "The desire for knowledge, the capacity for acting by oneself, the
  gift of observation, all qualities children bring with them to school, have, as a rule, at the
  close of the school period disappeared... their mental appetite and mental digestion are so
  destroyed that they for ever lack capacity for taking real nourishment." Preceding sentence
  (line 687) also confirmed: "the annihilation of once existent matter."
- Research source opened: `output/youth-sports/raisinggoodsports/rgs-r8-attrition-dropout.md` in
  full — confirmed Source 1 (2024 cross-sectional cohort, ages 8–13, PMC11300246) finding
  (psychosocial factors — social pressure, parental expectations, lack of enjoyment — as
  strongest predictors), Source 2/3 (the "70% by 13" figure's NAYS-poll origin and Aspen
  Institute's contested-figure framing), the file's `cautionNote` ("The '70% quit by 13' figure
  is a NAYS poll, not a peer-reviewed cohort — lead with the driver (fun), hedge the
  percentage."), the Synthesis line ("Dropout is the downstream endpoint of R2 (specialization)
  and R3 (burnout)"), and both Content Hooks. Confirmed `edition: v2-2026-07-18` matches
  `pairing-map.md`'s `research_codes_reviewed` entry for R8 (`R8: v2-2026-07-18`) — no staleness.

## Handoff
Feeds shorts-ideation next. Travels forward as a companion artifact to shorts-scripting
(citation text per beat above) and visual-prompts (visual motif cue: a young child joyfully
kicking a ball alone, cut against a teenager sitting on a bench, disengaged, during a drill).

## Alternates considered
1. **Alfred Adler × R8** — "the pampered child, unprepared for real difficulty" (a child who's
   had every difficulty removed, unprepared for the "hothouse" outside, suffers "defeats almost
   of necessity"). Also pairs directly with R8, but its mechanism (avoidance of adversity/
   resilience) fits the "social pressure" leg of R8's finding better than the "lack of enjoyment"
   leg, which the field's own synthesis names as the stronger driver — a close second, not the
   top pick.
2. **Plutarch (attributed) × R3** — "overwork unhinges the mind, rest is the sauce of labour"
   (burnout/overtraining). Offers a distinct causal chain: R8's own synthesis line names R3
   (burnout) as one of dropout's upstream drivers, so this row could frame "why kids quit at 13"
   through exhaustion rather than boredom. Quote-ok (unlike the paraphrase-caution picks above),
   which would allow an on-screen quote card — a real tonal alternative if a future pass wants
   that archetype instead.
