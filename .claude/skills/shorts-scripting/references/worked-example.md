# Worked example: concept brief → timed script

> This example illustrates rules already marked in this skill's other reference files and carries no independent normative weight. Where a line here restates a rule, the marker lives
> on the rule, not on the illustration — do not copy an unmarked line out of this file into a
> real brief as if it were sourced `[I]`.

This shows the full path from an upstream `shorts-ideation` concept brief to this
skill's output contract, with inline notes on which corpus rule drove each
choice. The premise (a home coffee-bloom trick) is the same one used in
`docs/headless-shorts-production-playbook.md`'s own Template (1)/(2) worked
examples, extended here into the concept-brief → beat-timed-script pipeline this
skill owns.

## Input: concept brief (from `shorts-ideation`)

```
=== CONCEPT BRIEF (from shorts-ideation) ===
Angle:              Home coffee tastes flat because people skip the "bloom"
                     step cafes always do — a fixable, unglamorous mistake.
Hook concept:        Provocative claim that the beans aren't the problem.
Packaging direction: Title frame = transformation ("the $2 fix"); cover text =
                     "NOT THE BEANS"; access-frame alt title available.
Target avatar:       Home coffee drinkers who assume better beans = better cup.
```

## Applying the process

1. **Net-information-gain check** `[C] (One Person Business, MP7JYOm25-g)`: most
   home-coffee content blames beans/grind/water temp. The angle's actual claim —
   that a *skipped step*, not equipment or ingredient quality, causes the flat
   taste — is the differentiator. Worth scripting as-is.
2. **Target length band**: no length specified in the brief and the premise has
   two sequential fixes (bloom, then water temp), so the standard 35–45s band
   fits better than the 20–30s punchy band (`beat-timing-model.md`).
3. **Hook (0–3s)**: packaging direction says "transformation" + "not the beans"
   — write the hook as the provocative claim itself, matching the promised
   packaging exactly (`hooks-and-openings.md`, promise-breaker rule).
4. **Setup (3–8s)**: name the stake (cheap, fast fix) without over-explaining.
5. **Build (8–28s)**: escalating steps rule — bloom first, named consequence,
   then the re-hook opens a second, unresolved mistake at ~15s
   (`retention-loops-and-structure.md`).
6. **Payoff (28–38s)**: resolves the *second* loop (the re-hook's mistake), and
   lands a concrete proof detail — "smooth, not sharp" (proof-density rule).
7. **Loop/CTA (38–45s)**: mirrors the hook's exact claim ("never the beans") per
   the loop-to-start rule, then a specific comment-bait question.
8. **Humanize pass**: checked against the AI-fingerprint block-list (no "it's
   important to note," no "delve/leverage/robust"); sentence lengths vary
   (9 / 14 / mixed-length Build / 22 / 13 words) rather than uniform AI-typical
   sentences (`script-intelligence-and-delivery.md`).

## Output: the timed script

```
=== SHORT SCRIPT — S101 ===
Concept brief source: shorts-ideation — "home coffee bloom trick" angle
Working title:   The $2 coffee trick baristas won't tell you
Single premise:  A cheap home step makes drip coffee taste like a cafe pour-over
Constraint/stake: Under $2, no machine, one extra step
Net-info-gain check: Most home-coffee content blames beans/grind/water temp;
  this says the problem is a skipped *step*, not an ingredient — genuinely
  different from the top existing videos on this topic. [C]

HOOK        (0–3s  | 8 words): "Your drip coffee's flat. It's not the beans."
SETUP       (3–8s  | 13 words): "Cafes do one thing at home you skip. It costs about two dollars."
BUILD/VALUE (8–28s | 44 words):
  (8–15s | 19 words): "Bloom the grounds first. Pour just enough hot water to soak them, wait thirty seconds, then finish the pour."
  [re-hook beat @ ~15s] (15–21s | 8 words): "But there's a second mistake almost everyone makes..."
  mechanism (21–28s | 17 words): "That gas escaping is what made your cup bitter. Same beans, same machine. One pause changes everything."
PAYOFF      (28–38s | 20 words): "The second fix: water off the boil, ninety seconds after. Now taste it, smooth, not sharp. That's the cafe difference."
LOOP/CTA    (38–45s | 13 words): "So it was never the beans. What flat cup are you fixing tonight?"
Comment-bait question: "Drip, French press, or pour-over — which do you run?"
Total word count: ~98 words (150–170 wpm band)

GATES
  Gate D (scripts/lint_script_language.py): pass
  Gate E (fresh Opus critic): pass

Visual notes (for visual-prompts downstream):
  Hook:     Close-up flat black coffee, slow push-in (signals "something's
            coming" per the muted-autoplay hook rule).
  Setup:    Cafe counter B-roll — establishes the "cafes do this" contrast.
  Build:    Grounds blooming, bubbles/gas visibly rising — this is a spoken
            mechanism, so render it visually, don't just narrate it.
  Re-hook:  Kettle/steam — visually signals "something else is coming" ahead
            of the verbal re-hook line.
  Payoff:   Pour into a clear mug with a visible taste-reaction cue.
  Loop/CTA: Return to the hero mug shot from Hook — the visual must match, not
            just the VO line, for the loop to read as a loop.

Delivery notes:
  - Muted-friendly: every beat's key claim is also carried by the visual note
    above, not just the VO (script-intelligence-and-delivery.md).
  - No talking head — Build's visual demonstration layer (grounds blooming)
    carries the load a talking-head Short would otherwise put on delivery
    energy (Nate Black, UjeOJb6lk5M).
  - No Jenny Hoyos medium-confidence techniques used in this example — a
    straightforward stated-rule hook (promise-breaker + mid-action) covered it;
    flag when one *is* used in a real script (see hooks-and-openings.md).
```

## What feeds forward

- **`voiceover-brief`** takes the Hook/Setup/Build/Payoff/Loop-CTA VO lines above
  plus their second-ranges and word counts — it doesn't need the visual notes.
- **`visual-prompts`** takes the per-beat visual notes plus the same
  second-ranges — it doesn't need the VO line wording verbatim, only what's
  happening on screen and when.
