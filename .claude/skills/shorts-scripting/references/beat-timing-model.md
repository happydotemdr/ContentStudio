# The beat-timing model — adaptation detail

Source: `docs/headless-shorts-production-playbook.md` §2, "The beat model
(target: ~30–45s Short)". **The standard-band beat table (seconds, word
budgets, per-beat job, grounding) lives in `SKILL.md`'s "Beat-timing model"
section — read it there; it is the single copy of those numbers.** This file
holds only what doesn't fit in that quick-reference: the reasoning behind the
`[I]`-marked word-rate assumption, the 20–30s compressed band, and the
re-hook-timing caveat in full. Read it alongside `hooks-and-openings.md`,
`retention-loops-and-structure.md`, and `endings-and-ctas.md` for the *content*
rules behind each beat.

## Word-rate assumption — why it's `[I]`

**A ~35s Short runs roughly 90–105 spoken words at a natural 150–170 wpm
narration pace** `[I]` — this pacing figure is an industry-standard TTS/spoken
narration assumption, not a corpus-extracted finding. It sets the word budgets
in `SKILL.md`'s table. `docs/headless-shorts-production-playbook.md` §5 uses
the same 150–170 wpm figure `[I]` for voiceover pacing, so it's consistent with
what `voiceover-brief` expects downstream.

### On the re-hook's timing being `[I]`

The corpus establishes the *re-hook cadence* as `[C]` (re-hook every 20–30
seconds on short-form, sourced across six channels — see
`retention-loops-and-structure.md`) and separately establishes that Shorts lose
50–60% of leavers in the first 3 seconds, meaning the *opening* loop's tension
peaks and needs resolving/renewing somewhere in the middle third of a 35–45s
Short. The playbook places the re-hook specifically at "~15s" as its own
synthesis of those two facts, not a directly stated "put the re-hook at 15
seconds" rule from any single channel — so this skill flags it `[I]` even
though the underlying mechanic is `[C]`. Treat 15s as a reasonable midpoint
default, not a rule to defend if a Short's natural Build rhythm wants the
re-hook a few seconds earlier or later.

## Shorter band (20–30s)

For a punchier Short — the corpus default when reviving a dead/random channel
`[C] (Nate Black, wqjiXKKqek4)`, or whenever the concept brief's premise is
simple enough not to need the full arc — compress:

- **Setup** `[I]` to one clause (~6–10 words).
- **Build** `[I]` to ~30 words, one escalation step instead of several, and the
  re-hook beat can be dropped entirely if the Build itself is short enough that
  a second curiosity beat would feel forced.
- **Hook, Payoff, Loop/CTA** `[I]` keep roughly the same word budgets — they don't
  compress well without losing their job.

## Word budgets are a target, not a hard ceiling

Treat the word budgets as a target, not a hard ceiling — a script that runs
short because the premise is genuinely simple is fine (see the "don't pad"
note in `retention-loops-and-structure.md`); a script that runs long should be
tightened, not left over-budget, since bloated setup is the single biggest
documented cause of mid-video drop.
