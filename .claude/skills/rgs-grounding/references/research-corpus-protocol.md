# Research Corpus Protocol

How `rgs-grounding` resolves a pairing-map row's research code to an actual citation.

## Resolution

1. From the map row's `Pairs with:` code (e.g. `F4`), glob
   `output/youth-sports/raisinggoodsports/rgs-*.md` for the file whose front-matter `code`
   matches.
2. Open the FULL file — not just its front-matter. Pull:
   - The actual Finding line(s) for the specific source you're citing (a theme file lists
     multiple sources; cite the one that actually supports your claim, not just the first one).
   - The full citation (author, year, journal/DOI where given).
   - The Quality / Scope / Depth rating.
   - The file's `cautionNote` if present in front-matter.
   - Any relevant line from the file's own "Content Hooks" section — these are pre-verified,
     pre-verify-policy-compliant phrasings the corpus author already wrote; prefer reusing one
     over re-deriving a number yourself.
3. Confirm the file's front-matter `edition` matches what `pairing-map.md`'s
   `research_codes_reviewed` recorded for this code. A mismatch means the theme was refreshed
   since the map was last reviewed — the row may be stale; flag it rather than using it
   silently, and note it for the next `rgs-pairing-review` pass.

## Citation discipline — `rgs-meta-verify-policy.md`'s rules, applied

Every `[RESEARCH: ...]` citation in a Grounding Brief must follow these (paraphrased from the
source file; open it directly if a specific case isn't covered here):

1. Confirm the exact figure and its population before it goes on-screen — don't round or
   generalize a search-snippet number.
2. Match the number to its exact definition and label its data year (e.g. "58%, NSCH 2024 data,
   2026 release" — not just "58%").
3. **S5 (professionalization) and R8 (attrition/dropout, esp. the "70% dropout" figure) cite
   the idea confidently but hedge the number** — these lean journalistic/poll-based, not
   peer-reviewed.
4. Lead with association, not causation — "kids who play sport tend to..." not "sport makes
   kids...". Applies with particular force to R9 (DMSP) and F4 (sport-parent burnout), both
   resting on observational data.
5. R5 (suicide) requires special handling — see `references/safety-sensitive-handling.md`.
6. R11/R14 (eating disorders) and R12 (safeguarding) require special handling — see
   `references/safety-sensitive-handling.md`.
7. Some sources are paywalled ("abstract only") — the abstract is enough to cite the finding
   accurately.
8. Recency matters — the verify-policy file's own recency-check date and figures are as of
   `2026-07-18`; if a Grounding Brief is produced well after that date, note in the brief that
   the cited figures should be spot-checked against the current file before the Short ships,
   since the research corpus itself gets refreshed periodically (see `README.md`'s refresh
   workflow).

## What never happens

- `master-edition-v2.md` is provenance-only — never cite it, ever, for any claim. Only cite the
  individual `rgs-*.md` theme files.
- Never cite a Finding without opening the file it's from in this invocation.
