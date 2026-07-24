# The beat-timing model

Source: `docs/headless-shorts-production-playbook.md` §2, "The beat model
(target: ~30–45s Short)". This is the skeleton every script this skill produces
must fill in — read it alongside `hooks-and-openings.md`,
`retention-loops-and-structure.md`, and `endings-and-ctas.md` for the *content*
rules behind each beat; this file is the *timing* scaffold.

## Word-rate assumption

**A ~35s Short runs roughly 90–105 spoken words at a natural 150–170 wpm
narration pace** `[I]` — this pacing figure is an industry-standard TTS/spoken
narration assumption, not a corpus-extracted finding. It sets the word budgets
below. `docs/headless-shorts-production-playbook.md` §5 uses the same 150–170
wpm figure `[I]` for voiceover pacing, so it's consistent with what
`voiceover-brief` expects downstream.

## The beat table (35–45s standard band)

| Beat | Seconds | Word budget | Job | Grounding |
|---|---|---|---|---|
| **Hook** | 0–3s | 8–15 words | Stop the swipe. State the premise as a provocative question OR drop into action already in progress. | `[C]` — see `hooks-and-openings.md` |
| **Setup** | 3–8s | 12–20 words | One sentence of context + the stakes. No "in this video." | `[C]` — see `hooks-and-openings.md` |
| **Build / Value** | 8–28s | 45–60 words | Deliver the single idea in escalating steps, each opening a small new loop. | `[C]` — see `retention-loops-and-structure.md` |
| **Re-hook** (inside Build, ~15s mark) | ~15s | folded into Build's budget | A second curiosity beat right when the opening loop starts to feel answered. | `[I]` placement — see note below |
| **Payoff** | 28–38s | 15–25 words | Resolve the exact question the hook asked. The reveal. | `[C]` — see `endings-and-ctas.md` |
| **Loop / CTA** | 38–45s | 5–12 words | Mirror the hook line so the end feeds the start; earn a comment with a specific question. | `[C]` — see `endings-and-ctas.md` |

**Total ≈ 90–110 words for a 35–45s Short.**

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

- **Setup** to one clause (~6–10 words).
- **Build** to ~30 words, one escalation step instead of several, and the
  re-hook beat can be dropped entirely if the Build itself is short enough that
  a second curiosity beat would feel forced.
- **Hook, Payoff, Loop/CTA** keep roughly the same word budgets — they don't
  compress well without losing their job.

## Using this table

1. Default to the 35–45s standard band unless the concept brief specifies a
   target length or the premise is simple enough to warrant the 20–30s band.
2. Treat the word budgets as a target, not a hard ceiling — a script that runs
   short because the premise is genuinely simple is fine (see the "don't pad"
   note in `retention-loops-and-structure.md`); a script that runs long should
   be tightened, not left over-budget, since bloated setup is the single
   biggest documented cause of mid-video drop.
3. Every beat gets a timestamp range, a word-count in the delivered script, and
   a one-line visual note (for `visual-prompts`) — see the output contract in
   `SKILL.md`.
