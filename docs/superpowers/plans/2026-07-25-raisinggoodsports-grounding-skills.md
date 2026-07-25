# RaisingGoodSports Grounding Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Tasks 7 and 9 additionally REQUIRE superpowers:writing-skills** — they create new SKILL.md files and must follow its frontmatter rules, description-writing rules, and RED→GREEN testing methodology (adapted below to a Technique-skill, not a discipline-skill, per that skill's own "Testing All Skill Types" section — see Tasks 8 and 10).

**Goal:** Add two RaisingGoodSports-only skills — `rgs-grounding` (topic → a source-verified Grounding Brief pairing a historical thinker with youth-sports research) and `rgs-pairing-review` (detects corpus growth, proposes curated additions to the pairing map for human approval) — plus the curated pairing map that makes matching quality trustworthy, and the two scope-note corrections this unlocks.

**Architecture:** Two atomic Claude Code skills under `.claude/skills/`, following the existing six-skill house pattern (`SKILL.md` + `references/*.md`, hand-chained, no orchestrator). All state is flat Markdown with YAML front-matter — no database, no server. `rgs-grounding`'s matching is curated-map-first (a hand-authored `pairing-map.md`) with live-glob as a flagged gap-fill fallback only; `rgs-pairing-review` diffs the map's own front-matter ledger against current corpus state and proposes additions, never writing directly to the map.

**Tech Stack:** Markdown, YAML front-matter, Claude Code skills (no code/build step). File operations only (Read/Write/Edit/Glob/Grep).

## Global Constraints

- Both new skills use the `rgs-` name prefix (approved naming convention; distinguishes from the six generic pipeline skills).
- Citation markers are `[THINKER: Name, Work, quotability]` and `[RESEARCH: Author Year, quality rating]` — never reuse the six existing skills' `[C]`/`[I]`/`[T]` markers (different citation disciplines, different sources; reuse would misrepresent provenance).
- `pairing-map.md` rows are at **thinker-concept × research-code** granularity, never thinker × topic.
- `rgs-pairing-review` NEVER writes directly to `pairing-map.md` without an explicit human approval step in the same conversation; the resulting `git diff` on `pairing-map.md` is the approval surface, mirroring the existing corpus refresh workflow in `README.md`.
- Grounding briefs save to `rgs-briefs/YYYY-MM-DD-<topic-slug>.md` (new top-level directory, git-tracked — original editorial output, not regenerable corpus data).
- `rgs-pairing-review` proposals save to `output/pairing-proposals/YYYY-MM-DD-proposal.md` (git-ignored — `output/` already ignores everything per `.gitignore:3`).
- `master-edition-v2.md` is never a citable source, in any file this plan produces.
- `output/raisinggoodsports-brand-definition.md` is read-only reference; no task in this plan edits it.
- No task in this plan modifies the six existing skills (`shorts-ideation`, `shorts-scripting`, `voiceover-brief`, `visual-prompts`, `shorts-assembly`, `social-repurpose`) — that's spec'd follow-on work, out of scope here.
- No cron/scheduling infrastructure — `rgs-pairing-review` is human-triggered only.
- Safety-sensitive research codes are R5 (suicide risk), R11 (eating disorders/RED-S), R12 (safeguarding/abuse), R14 (male eating disorders) — any pairing touching these follows `rgs-meta-verify-policy.md`'s extra rules (help-resource pairing for R5 — 988 Suicide & Crisis Lifeline; non-sensational framing; name the exact construct/population/data-year; never name/imply individuals for R12).

## File Structure

```
rgs-briefs/
  README.md                                    # Task 1 — ledger convention doc

.claude/skills/rgs-grounding/
  SKILL.md                                      # Task 7 — two-phase workflow + templates
  references/
    pairing-map.md                              # Task 2 — curated thinker×research pairings
    thinker-corpus-protocol.md                  # Task 3
    research-corpus-protocol.md                 # Task 4
    safety-sensitive-handling.md                 # Task 5
    brand-voice-and-tone.md                      # Task 6
    worked-example.md                            # Task 8 — written from the GREEN test run

.claude/skills/rgs-pairing-review/
  SKILL.md                                      # Task 9 — diff + propose workflow

CLAUDE.md                                        # Task 11 — scope-note correction
README.md                                        # Task 12 — scope-note correction + refresh-workflow line
```

Reference files are split by concern (matching data, thinker-access protocol, research-access
protocol, safety protocol, tone) rather than one large `SKILL.md`, matching the existing six
skills' pattern of small, single-purpose `references/*.md` files loaded on demand
(progressive disclosure).

---

### Task 1: Create the `rgs-briefs/` ledger directory

**Files:**
- Create: `rgs-briefs/README.md`

**Interfaces:**
- Produces: the `rgs-briefs/` directory (git needs a tracked file inside it to exist) and the
  documented front-matter schema that Task 7 (`rgs-grounding/SKILL.md`) and Task 9
  (`rgs-pairing-review/SKILL.md`) both reference by name.

- [ ] **Step 1: Write `rgs-briefs/README.md`**

```markdown
# rgs-briefs/

Saved Grounding Briefs produced by the `rgs-grounding` skill — one file per RaisingGoodSports
Short that has been through grounding. This directory is the production ledger: `rgs-grounding`
live-globs this directory's front-matter on every invocation to avoid over-repeating the same
thinker or the same concept×code pairing across recent Shorts.

Git-tracked deliberately — these are original editorial decisions, not downloaded/regenerable
corpus data (unlike `output/`, which is git-ignored).

## Naming

`YYYY-MM-DD-<topic-slug>.md` — one file per grounding brief, dated by the day it was produced.

## Front-matter schema

```yaml
---
date: 2026-07-25
topic: "why kids quit travel sports around age 13"
thinker: "Thorstein Veblen"
concept: "Invidious comparison"
research_codes: [F4]
archetype: A1
status: candidate
---
```

- `status` is `candidate` until the Short is actually produced, then hand-edit to `produced` or
  delete the file if the topic was abandoned. `rgs-grounding`'s recency rules apply to files
  regardless of `status` — even an abandoned candidate reflects a recent pairing choice.

## Who reads this

- `rgs-grounding` (soft recency/variety rules — deprioritize a thinker used in the last ~5
  briefs by filename date; flag an exact concept×code repeat within the last ~15).
- `rgs-pairing-review` (greps for a "Gap-fill flag" section — see
  `.claude/skills/rgs-grounding/references/thinker-corpus-protocol.md` — to catch pairings that
  came from the live-glob fallback rather than the curated map, so they enter the next review).
```

- [ ] **Step 2: Verify the directory is tracked**

Run: `git status --short rgs-briefs/`
Expected: `A  rgs-briefs/README.md` (or similar "added" marker) once staged — confirms the
directory isn't caught by any existing `.gitignore` rule (`.gitignore` only lists `output/`,
`*.pyc`, `__pycache__/`, `.venv/`, `cowork-plugin/`, `dist/` — `rgs-briefs/` doesn't match any).

- [ ] **Step 3: Commit**

```bash
git add rgs-briefs/README.md
git commit -m "docs: add rgs-briefs ledger directory for rgs-grounding output"
```

---

### Task 2: Author the curated pairing map

**Files:**
- Create: `.claude/skills/rgs-grounding/references/pairing-map.md`

**Interfaces:**
- Consumes: `output/raisinggoodsports-brand-definition.md`'s 7-thinker table (the starting
  hypothesis list below), `manifests/thinkers.json` (for exact slugs and quotability/
  cautionNote), `output/thinkers/anchorandwave/<slug>/<file>.cleaned.md` (full text to verify
  against), `output/youth-sports/raisinggoodsports/rgs-*.md` (research findings + front-matter
  codes/editions to verify against).
- Produces: the row schema and front-matter ledger schema that Task 3
  (`thinker-corpus-protocol.md`), Task 7 (`rgs-grounding/SKILL.md`), and Task 9
  (`rgs-pairing-review/SKILL.md`) all reference by name (`## <Thinker>` / `### Concept: <name>`
  sections; `last_review` / `thinker_slugs_reviewed` / `research_codes_reviewed` front-matter
  keys).

This is a content-research task, not a mechanical one: **every row must be verified against
actual source text before being written** — this is the exact discipline the whole design
exists to enforce (a pairing "the model already knows" without opening the source is
provenance theater, not grounding). One row below is already fully verified as your template;
the rest follow the identical procedure.

- [ ] **Step 1: Write the front-matter ledger and the file's own framing header**

```markdown
---
last_review: 2026-07-25
thinker_slugs_reviewed: [aristotle-politics, plutarch-morals-on-education, rousseau-emile, james-talks-to-teachers, mason-home-education, mason-parents-and-children, key-century-of-the-child, montessori-the-montessori-method, adler-understanding-human-nature, isaacs-intellectual-growth-in-young-children, froebel-education-of-man, pestalozzi-leonard-and-gertrude, martineau-household-education, veblen-theory-of-the-leisure-class, dewey-democracy-and-education, dewey-how-we-think]
research_codes_reviewed: {B1: v2-2026-07-18, B2: v2-2026-07-18, B3: v2-2026-07-18, B4: v2-2026-07-18, R1: v2-2026-07-18, R2: v2-2026-07-18, R3: v2-2026-07-18, R4: v2-2026-07-18, R5: v2-2026-07-18, R6: v2-2026-07-18, R7: v2-2026-07-18, R8: v2-2026-07-18, R9: v2-2026-07-18, R10: v2-2026-07-18, R11: v2-2026-07-18, R12: v2-2026-07-18, R13: v2-2026-07-18, R14: v2-2026-07-18, S1: v2-2026-07-18, S2: v2-2026-07-18, S3: v2-2026-07-18, S4: v2-2026-07-18, S5: v2-2026-07-18, S6: v2-2026-07-18, S7: v2-2026-07-18, S8: v2-2026-07-18, S9: v2-2026-07-19, F1: v2-2026-07-18, F2: v2-2026-07-18, F3: v2-2026-07-18, F4: v2-2026-07-18, F5: v2-2026-07-18}
---

# RGS Pairing Map

Curated thinker-concept × research-code pairings for `rgs-grounding`. **Rows below are the
only trusted matches** — every row was produced by opening both the thinker's cleaned text and
the research file's actual body (not just front-matter) and confirming the pairing genuinely
holds. Anything a `rgs-grounding` invocation matches outside this map is live-glob gap-fill,
and must be flagged "candidate for brand-book review" per
`references/thinker-corpus-protocol.md` — never treated as equally trustworthy as a map row.

`thinker_slugs_reviewed` is scoped to the union of (a) every `parenting`-pillar thinker in
`manifests/thinkers.json` (13 slugs across 12 thinkers) and (b) the brand's 7 signature
thinkers from `output/raisinggoodsports-brand-definition.md`, since two of those seven — Veblen
and Dewey — don't actually carry the `parenting` tag in the manifest (Veblen is tagged
status/self-development; Dewey is tagged education only) despite being core to the brand's
signature format. That union is 16 slugs across 14 distinct thinkers, listed above — not all 53
works in the manifest. `thinker-corpus-protocol.md`'s live-glob gap-fill path is narrower
(parenting-pillar only, since it's an unreviewed fallback, not a curation pass) — that's a
deliberately safer net than this ledger's broader "considered" scope. Reviewing the other ~39
unrelated works (Adam Smith, Barnum, etc.) would be busywork for a youth-sports-parenting brand
and would never produce a usable row. If a future review deliberately expands into a different
pillar, add those slugs here explicitly at that time — don't silently widen scope.

`research_codes_reviewed` values are the `edition` string recorded in each `rgs-*.md` file's
front-matter at the time this map was last reviewed — `rgs-pairing-review` (see
`.claude/skills/rgs-pairing-review/SKILL.md`) diffs current editions against these to detect
when a theme has been refreshed and any map row citing it needs re-verification. This list
deliberately **excludes the three Meta-section files** (`LANDSCAPE`, `OPENQ`, `VERIFY` codes,
i.e. `rgs-meta-landscape-map.md`, `rgs-meta-open-questions.md`, `rgs-meta-verify-policy.md`) —
they're reference/policy documents, not pairable research themes, and `rgs-pairing-review`'s
diff step excludes `section: Meta` files entirely rather than tracking them as "reviewed."

Pairing links are editorial synthesis — a thematic/mechanism parallel the brand draws between a
decades- or centuries-old text and a modern finding — not a claim that the research paper cites
or proves the thinker's idea. Word every "Why it links" sentence as an interpretive parallel,
never as if the research validates the thinker.
```

- [ ] **Step 2: Add the first row — Veblen, fully verified (use as your template for the rest)**

```markdown
## Thorstein Veblen

### Concept: Invidious comparison (status by display)
- **Work / anchor:** *The Theory of the Leisure Class* —
  `output/thinkers/anchorandwave/thorstein-veblen/veblen-theory-of-the-leisure-class.cleaned.md`.
  Line 47 (Chapter One, "Introductory"): "Wherever the circumstances or traditions of life lead
  to an habitual comparison of one person with another in point of efficiency, the instinct of
  workmanship works out in an emulative or invidious comparison of persons... visible success
  becomes an end sought for its own utility as a basis of esteem." Line 99 (Chapter Two,
  "Pecuniary Emulation," which starts at line 67): "the end sought by accumulation is to rank
  high in comparison with the rest of the community... The invidious comparison can never
  become so favourable to the individual making it that he would not gladly rate himself still
  higher relatively to his competitors."
- **Quotability:** paraphrase-caution. Manifest cautionNote (`manifests/thinkers.json`, exact
  text): "Written as economic satire/irony (\"conspicuous consumption\") — short excerpts
  pulled out of context easily invert Veblen's meaning." Never place on a quote card as a
  direct statement.
- **Pairs with:** F4 (sport-parent burnout & overinvolvement)
- **Why it links:** Veblen's mechanism is esteem gained through comparison-driven display
  relative to one's peers; F4's construct is chronic emotional/physical investment in a child's
  sport career without adequate recovery. The parallel: sport-parent overinvestment is
  plausibly sustained, in part, by exactly the status-comparison dynamic Veblen describes
  (keeping pace with other travel-team families) — an interpretive lens on *why* the investment
  becomes chronic, not a claim F4's cited studies measured Veblen's mechanism directly.
- **Visual motif cue:** a sideline where parents' gear, setup, or effort visibly outcompetes
  their neighbors' — the comparison itself as the shot, not any one family singled out.
```

- [ ] **Step 3: Author the remaining rows, one thinker section at a time**

For each thinker below, open the exact files listed, find a genuine passage supporting the
named concept (a real quote or close paraphrase, with a chapter/section anchor — not a
paraphrase from memory of what the thinker is "known for"), then open the listed candidate
research file(s) and confirm the mechanism-level link actually holds before writing the row in
the Step 2 format. If a candidate research code turns out not to genuinely fit on inspection,
try the next-most-plausible code from the corpus's own theme list (`output/youth-sports/
raisinggoodsports/README.md` and the `rgs-*.md` front-matter `code` fields) rather than forcing
the starting hypothesis — and if nothing fits, write the thinker/concept row with an empty
`Pairs with:` and a one-line note ("no research-corpus pairing found on review") rather than
inventing one. Target 2–4 concepts per thinker (~18–24 rows total across the 7):

1. **Alfred Adler** — `output/thinkers/anchorandwave/alfred-adler/adler-understanding-human-nature.cleaned.md`.
   Concept candidate: the pressured/pampered child, striving for superiority under parental
   ambition. Candidate research codes to check: R3 (burnout & overtraining), R7 (parental
   pressure & sideline behavior), S5 (professionalization).
2. **John Dewey** — `output/thinkers/anchorandwave/john-dewey/dewey-democracy-and-education.cleaned.md`
   and `dewey-how-we-think.cleaned.md`. Concept candidate: play vs. work, intrinsic vs.
   instrumental worth of an activity. Candidate codes: R9 (deliberate play vs. deliberate
   practice), R10 (the science of fun), B3 (psychosocial development).
3. **Charlotte Mason** — `output/thinkers/anchorandwave/charlotte-mason/mason-home-education.cleaned.md`
   and `mason-parents-and-children.cleaned.md`. Concept candidate: play and rest as essential as
   structured lessons; the child's happiness as a legitimate end in itself. Candidate codes: R13
   (sleep and the youth athlete), R3 (burnout & overtraining), B3 (psychosocial development).
4. **William James** — `output/thinkers/anchorandwave/william-james/james-talks-to-teachers.cleaned.md`.
   Concept candidate: worth hidden in "alien lives" — humility about which kids' paths matter.
   Candidate codes: S6 (relative age effect), R8 (attrition & dropout), F3 (identity
   development).
5. **Ellen Key** — `output/thinkers/anchorandwave/ellen-key/key-century-of-the-child.cleaned.md`.
   Concept candidate: prizes/competition as corrosive to genuine engagement; "work for work's
   sake." Candidate codes: R8 (attrition & dropout), R10 (the science of fun), S5
   (professionalization).
6. **Jean-Jacques Rousseau** — `output/thinkers/anchorandwave/jean-jacques-rousseau/rousseau-emile.cleaned.md`
   (per `manifests/thinkers.json`, Book V specifically carries a `paraphrase-caution`
   `cautionNote` — check it before selecting an anchor; prefer an earlier book for a quote-safe
   passage if one supports the concept as well). Concept candidate: holding childhood in
   reverence; the developmental value of unstructured time/idleness. Candidate codes: R2 (early
   specialization vs. multi-sport), R9 (deliberate play vs. deliberate practice), F2 (screens
   vs. sport — only if a genuine "protect unstructured time" link holds up on inspection).

Add each finished row under its own `## <Thinker>` heading, `### Concept: <name>` subheading,
in the exact Step 2 format.

The remaining seven `thinker_slugs_reviewed` entries — Aristotle (`aristotle-politics`),
Plutarch (`plutarch-morals-on-education`), Montessori (`montessori-the-montessori-method`),
Isaacs (`isaacs-intellectual-growth-in-young-children`), Fröbel (`froebel-education-of-man`),
Pestalozzi (`pestalozzi-leonard-and-gertrude`), Martineau (`martineau-household-education`) —
get a lighter pass: skim each `.cleaned.md` file for anything that jumps out as a strong,
specific concept-level match to an uncovered research code. Add a full row only if one
genuinely holds up under the same verification standard as Step 2; otherwise leave them without
a row. This matches the design's stated priority (the brand's 7 signature thinkers first, the
wider pool only when something concrete fits) while still keeping the ledger honest — these
seven are marked "reviewed" because they were actually opened and checked this pass, not
because they were pre-judged unlikely to fit.

- [ ] **Step 4: Read the finished file back and confirm structural correctness**

Run: read `.claude/skills/rgs-grounding/references/pairing-map.md` in full.
Expected: front-matter has all four keys (`last_review`, `thinker_slugs_reviewed`,
`research_codes_reviewed`); every row has all five fields (Work/anchor, Quotability, Pairs
with, Why it links, Visual motif cue) with the anchor pointing to a real file path under
`output/thinkers/anchorandwave/`; no row cites `master-edition-v2.md`; no `quote-ok` claim
lacks a real quoted passage and no `paraphrase-caution` row places quotation marks around
thinker text as if on-screen-safe.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/rgs-grounding/references/pairing-map.md
git commit -m "feat: author curated thinker x research pairing map for rgs-grounding"
```

---

### Task 3: Author `thinker-corpus-protocol.md`

**Files:**
- Create: `.claude/skills/rgs-grounding/references/thinker-corpus-protocol.md`

**Interfaces:**
- Consumes: `pairing-map.md`'s row schema (Task 2), `manifests/thinkers.json`'s `pillars` field.
- Produces: the "map-first, live-glob gap-fill only" procedure and the exact "candidate for
  brand-book review" flag text that Task 7 (`SKILL.md`) and Task 9 (`rgs-pairing-review`) both
  reference verbatim.

- [ ] **Step 1: Write the file**

```markdown
# Thinker Corpus Protocol

How `rgs-grounding` resolves a topic to a thinker citation. Two paths, in strict priority
order — never skip straight to path 2 because it's faster.

## Path 1 — the curated map (always try first)

1. Read `references/pairing-map.md` in full.
2. Look for a row whose concept plausibly fits the current topic.
3. If found: open the row's exact `Work / anchor` file path and confirm the cited
   lines/passage are still there and still say what the row claims (corpus text is static once
   downloaded, but always verify — don't trust the row's paraphrase of itself). This is the
   mandatory source-open step; it is not optional under time pressure. Skipping it because "the
   map already says this row is verified" reintroduces exactly the provenance-theater failure
   the map exists to prevent — the map records that a human verified the SOURCE, not that this
   pairing is trustworthy forever without re-reading it.
4. Use the row's `Quotability` field as-is; restate it in the Grounding Brief per beat (see
   `SKILL.md`), not just once.

## Path 2 — live-glob gap-fill (only when Path 1 has no fitting row)

1. Glob `manifests/thinkers.json`, filter to entries whose `pillars` array includes
   `"parenting"`.
2. Pick the entry that most plausibly fits the topic based on its `pillars` tags and title —
   this is a real judgment call, not a guarantee of fit.
3. Open that thinker's `.cleaned.md` file and search for an actual passage supporting the
   specific claim you're about to make. If nothing in the text actually supports it, this
   thinker is not a fit — try another candidate or report the pillar as thin for this topic
   rather than forcing a citation.
4. Any pairing produced via this path gets a **Gap-fill flag** in the Grounding Brief:

   ```markdown
   ## Gap-fill flag
   This pairing (Thinker: <name>, Concept: <concept>) came from live-glob, not the curated
   pairing map — flagged "candidate for brand-book review." Run `rgs-pairing-review` to
   formally evaluate adding it.
   ```

   `rgs-pairing-review` greps saved briefs in `rgs-briefs/` for this exact heading text
   (`## Gap-fill flag`) to find organically-discovered candidates — keep the heading text
   exact if you ever revise this protocol.

## What never happens

- Never write `[THINKER: ...]` into a brief without having opened the actual `.cleaned.md` file
  in this invocation and confirmed the passage. A thinker being "well known" for an idea is not
  a substitute for reading the specific text.
- Never treat `paraphrase-caution` as a technicality to route around — restate it at every beat
  that uses the citation, not just once at the top of the brief.
```

- [ ] **Step 2: Verify cross-references**

Run: read the file back; confirm it references `references/pairing-map.md`, the exact heading
`## Gap-fill flag`, and the `"parenting"` pillar filter — these three strings must match
verbatim what Task 2's `pairing-map.md`, Task 7's `SKILL.md`, and Task 9's `SKILL.md` also use,
since Task 9 greps for the heading text literally.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/rgs-grounding/references/thinker-corpus-protocol.md
git commit -m "feat: add thinker corpus resolution protocol for rgs-grounding"
```

---

### Task 4: Author `research-corpus-protocol.md`

**Files:**
- Create: `.claude/skills/rgs-grounding/references/research-corpus-protocol.md`

**Interfaces:**
- Consumes: `output/youth-sports/raisinggoodsports/rgs-meta-verify-policy.md` (the citation
  discipline rules), `rgs-*.md` front-matter schema (`slug`, `code`, `section`, `pillars`,
  `quotability`, `edition`).
- Produces: the research-side resolution procedure Task 7's `SKILL.md` references.

- [ ] **Step 1: Read the verify-policy source once more to quote its rules precisely**

Read `output/youth-sports/raisinggoodsports/rgs-meta-verify-policy.md` in full (already read
earlier in this project's design session; re-read now to quote its 8 numbered rules precisely
rather than from memory, since precision here is the entire point of this file).

- [ ] **Step 2: Write the file**

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/rgs-grounding/references/research-corpus-protocol.md
git commit -m "feat: add research corpus resolution protocol for rgs-grounding"
```

---

### Task 5: Author `safety-sensitive-handling.md`

**Files:**
- Create: `.claude/skills/rgs-grounding/references/safety-sensitive-handling.md`

**Interfaces:**
- Consumes: `rgs-r5-suicide-risk.md`, `rgs-r11-eating-disorders-reds.md`, `rgs-r12-safeguarding.md`,
  `rgs-r14-male-eating-disorders.md`, and `rgs-meta-verify-policy.md` rules 5–6.
- Produces: the "Safety handling" brief section content Task 7's Grounding Brief template
  invokes by reference.

- [ ] **Step 1: Read the four safety-sensitive theme files' verify-policy-relevant passages**

Read `output/youth-sports/raisinggoodsports/rgs-meta-verify-policy.md` rule 5 and 6 (already
read in this session's design phase — re-read now for precise quoting) and skim the front-matter
`cautionNote` field of `rgs-r5-suicide-risk.md`, `rgs-r11-eating-disorders-reds.md`,
`rgs-r12-safeguarding.md`, and `rgs-r14-male-eating-disorders.md` to confirm the specific
cautions haven't changed since the design session summarized them.

- [ ] **Step 2: Write the file**

```markdown
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
  number — these are different populations; name which one any statistic refers to.

## R11 / R14 — Eating disorders

- Frame around fueling and bone health, never around weight or appearance.
- Name the specific construct behind any prevalence number — R11's range is genuinely
  5.6%–65% depending on definition (DSM-clinical vs. broad at-risk screening); citing a bare
  percentage without naming which construct it measures is a verify-policy violation, not a
  simplification.
- R14 covers male athletes specifically — screening tools validated on female populations
  under-detect male presentations (weight-cutting, muscle dysmorphia); don't generalize R11
  findings onto a male-athlete claim without checking R14 first.

## R12 — Safeguarding

- Frame around program-level structural safeguards a parent can actually check for (what to
  look for in a program), never around naming or implying specific individuals.
- Prevalence estimates range ~2% to ~84% depending entirely on which construct is measured
  (sexual abuse specifically vs. any interpersonal violence broadly) — always name the
  construct.

## General rule across all four

None of R5/R11/R12/R14 exists to frighten. Each documents a real, well-documented pattern a
parent benefits from recognizing calmly. If a Grounding Brief's tone on one of these themes
reads as alarming rather than reassuring-and-informative, it violates `brand-voice-and-tone.md`
("relief over alarm") as much as it violates verify-policy — fix the framing, don't just soften
individual words.

## Grounding Brief "Safety handling" section — when to omit

If the brief doesn't touch any of these four codes, omit the "Safety handling" section from the
brief entirely — don't force a "not applicable" placeholder into every brief.
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/rgs-grounding/references/safety-sensitive-handling.md
git commit -m "feat: add safety-sensitive citation protocol for rgs-grounding"
```

---

### Task 6: Author `brand-voice-and-tone.md`

**Files:**
- Create: `.claude/skills/rgs-grounding/references/brand-voice-and-tone.md`

**Interfaces:**
- Consumes: `output/raisinggoodsports-brand-definition.md` (voice, lexicon, Do/Don't, archetypes
  sections).
- Produces: the archetype names (A1/A2/A3) and the hook→turn→payoff→reframe spine name Task 7's
  `SKILL.md` and templates reference throughout.

- [ ] **Step 1: Write the file, distilled from `brand-definition.md`**

```markdown
# Brand Voice and Tone

Distilled from `output/raisinggoodsports-brand-definition.md` (last synced 2026-07-25 — that
file is a static reference copy maintained upstream; if it's ever refreshed with a newer
edition, re-sync this file by hand and update this date).

## Voice traits (binding)

Calm, warm, grounded — an ally on the same side of the table as the parent. Evidence + old
wisdom, made plain. One idea at a time, no throat-clearing. Confident, never preachy — reframe,
don't lecture. Relief over alarm — every piece hands back agency, not dread.

**Never:** scoldy, doom-mongering, rage-bait, or parent-shaming. The villain is always the
system (the travel-team economy, scarcity marketing, sideline comparison culture) — never the
parent.

## Lexicon

**Preferred:** "on your side," "we're in this together," "it was never about your kid — that's
the good news," "the system"/"the game"/"the treadmill" (locate the villain in the structure),
"invidious comparison" (Veblen's term — always explain it in plain words when used), reframe,
relief, agency, a saner way, concrete numbers over adjectives.

**Banned:** shame/blame language ("bad parent," "you're ruining your kid," "if you really
cared..."), clickbait absolutes that blame the parent, guru-speak ("hack," "crush it",
"game-changer," "the secret to"), moral-panic doom / fear for fear's sake.

## Production spine (binding)

Every Short follows: **hook → turn → payoff → reframe**. A Grounding Brief is structured around
these same four beats so `shorts-scripting` can lift citations directly into them.

## The three content archetypes

- **A1 — "the thinker who saw it coming."** Thinker-led: open from the historical passage, land
  on the modern parallel.
- **A2 — "the number they don't tell you."** Research-stat-led: open from the surprising
  finding, use the thinker as the framing lens.
- **A3 — "what the kid hears."** Empathy-led, validated by research: open from the child's
  perspective, back it with both pillars.

A Grounding Brief should name which archetype its pairing best fits — this is the primary
signal `shorts-ideation` uses to pick an angle.

## Quotability rule (binding, restated per beat — see `thinker-corpus-protocol.md`)

`quote-ok` thinkers may be quoted verbatim on a quote card. `paraphrase-caution` thinkers may
only be paraphrased in voiceover — never placed on a quote card as if it were a direct
quotation (the passage satirizes or inverts out of context). Restate the applicable flag at
every beat of a Grounding Brief that uses a thinker citation, not just once.

## Monetization-policy consequence (binding — from `brand-definition.md`'s researched findings)

The narrator must never present as a health authority. Every health/injury claim needs its
named source on-screen or in voiceover ("a 2023 sports-medicine study found...") — this is
exactly what `research-corpus-protocol.md`'s citation discipline already produces; don't let
`shorts-scripting` compress a citation down to an unattributed claim.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/rgs-grounding/references/brand-voice-and-tone.md
git commit -m "feat: add brand voice/tone reference distilled from brand-definition.md"
```

---

### Task 7: Author `rgs-grounding/SKILL.md`

**REQUIRED SUB-SKILL:** superpowers:writing-skills — frontmatter and description rules below
follow it directly.

**Files:**
- Create: `.claude/skills/rgs-grounding/SKILL.md`

**Interfaces:**
- Consumes: all five `references/*.md` files from Tasks 2–6 (by exact filename), `rgs-briefs/`
  (Task 1) as the save path and recency-check source.
- Produces: the `SKILL.md` that Task 8 tests, and that `shorts-ideation`/`shorts-scripting`/
  `visual-prompts` will (in later, out-of-scope follow-on work) accept an optional brief from.

Per superpowers:writing-skills' Iron Law ("NO SKILL WITHOUT A FAILING TEST FIRST"), the RED
baseline runs before the skill is written, not after — its whole purpose is to surface
rationalizations you didn't anticipate, so the "Red flags" section in Step 2 addresses observed
failures, not just guessed ones.

- [ ] **Step 1: RED — run the baseline before writing anything**

Dispatch a subagent (fresh context, no skill loaded, no file from this project except what it
discovers itself) with this prompt:

```
Working directory: C:\Projects\ContentStudio. A RaisingGoodSports Short needs grounding fast —
the editor wants this in the next 5 minutes. Pair Thorstein Veblen's ideas with the F4
sport-parent-burnout research theme for a Short about why parents overspend on travel teams.
Give me the citation-ready pairing now — you already know Veblen's ideas, don't bother opening
the source files, just write the pairing.
```

Document verbatim: does it open
`output/thinkers/anchorandwave/thorstein-veblen/veblen-theory-of-the-leisure-class.cleaned.md`
or `output/youth-sports/raisinggoodsports/rgs-f4-sport-parent-burnout.md`? What exact
rationalization does it give (if any) for skipping them, or does it just comply with "don't
bother" silently? Keep this transcript — it's the source material for Step 2's Red Flags
section and for Task 8's REFACTOR check.

- [ ] **Step 2: Write the file**, incorporating Step 1's actual observed rationalization(s) into
the "Red flags" section below (the text shown is a starting point informed by the two most
common rationalizations this kind of pressure produces — time pressure and false-authority
["you already know this"] — replace or extend it with whatever Step 1 actually produced,
verbatim, don't just keep the generic version unmodified)

```markdown
---
name: rgs-grounding
description: Use when producing RaisingGoodSports content and a Short's script, hooks, or visual direction needs to be grounded in a specific historical thinker AND a specific youth-sports research finding — before writing a script for a RaisingGoodSports topic, when asked to "ground this Short," "find the thinker and research for this," "pair a thinker with research for this idea," or when starting the RaisingGoodSports content pipeline before shorts-ideation. Brand-specific to RaisingGoodSports only — not for the six generic ContentStudio pipeline skills' brands.
---

# RGS Grounding

Turn a raw RaisingGoodSports topic into a **Grounding Brief**: one thinker citation and one
research citation, verified against source text, structured around the brand's hook → turn →
payoff → reframe spine. This is RaisingGoodSports's differentiator — "what a 100-year-old
thinker saw coming" — and the entire point is that every claim is earned by actually opening
the source, not recalled from what the model already knows about Veblen or Adler.

## Pipeline position

| | |
|---|---|
| **Upstream** | None — a raw RGS topic, pain point, or a specific thinker/finding already in mind |
| **This skill** | Topic → one verified Grounding Brief, saved to `rgs-briefs/` |
| **Downstream** | Feeds `shorts-ideation` (angle/archetype pick); the same brief also feeds `shorts-scripting` (citation text per beat) and `visual-prompts` (motif cues) — hand it forward at each stage, don't regenerate it |

## Why matching is map-first, not live-glob-first

An earlier draft of this skill live-queried the corpora and let judgment pick a fitting
pairing. That produces provenance theater: proving a thinker's work *exists* in a manifest is
not the same as grounding what you *say about it*. Read `references/pairing-map.md` first,
always — it's the only trusted set of matches. Live-glob (`references/thinker-corpus-protocol.md`
Path 2) is a flagged fallback for topics the map doesn't cover yet, never a first resort taken
for speed.

## Citation markers

`[THINKER: Name, Work, quotability]` and `[RESEARCH: Author Year, quality rating]` — not
`[C]`/`[I]`/`[T]` (those denote the unrelated 14-channel headless-YouTube corpus).

## Workflow

### 1. Confirm the topic is genuinely RGS-relevant

RaisingGoodSports covers youth-sports culture's effect on kids and families — status
competition, specialization/overuse, burnout/dropout, pay-to-play, the case for play/rest/
intrinsic worth. If the topic is generic parenting or generic sports content with no youth-
sports-culture angle, say so rather than forcing a pairing.

### 2. Build the Pairing Slate

Read `references/pairing-map.md`. Find 2–3 rows whose concept plausibly fits the topic (prefer
map rows; only reach for `references/thinker-corpus-protocol.md` Path 2 if nothing fits). For
each candidate, check `references/safety-sensitive-handling.md` if its research code is
R5/R11/R12/R14, and check `rgs-briefs/` (glob the last ~20 files by date) for a recency flag —
deprioritize (don't exclude) a thinker used in the last ~5 briefs; flag an exact concept×code
repeat within the last ~15.

This step is cheap — map + front-matter + brief filenames only, no deep source reading yet.

```markdown
## Pairing Slate: [topic]

1. **[Thinker] × [Research code]** — [one-line mechanism link, from the map's "Why it links"]
   - Archetype: [A1 / A2 / A3 — see references/brand-voice-and-tone.md]
   - Quotability: [quote-ok / paraphrase-caution]
   - Safety flag: [none / R5 / R11 / R12 / R14 — note the extra handling this triggers]
   - Recency flag: [none / "[Thinker] used in the [date] brief"]
2. ...
3. ...

Pick one to proceed to a fully-verified Grounding Brief, or ask for a different topic framing.
```

Present this to the human and wait for a pick. **Non-interactive fallback** (no human available
to pick mid-invocation): proceed with the top-ranked row, and include an "Alternates
considered" appendix (below) in the final brief instead of stopping.

### 3. Verify the chosen pairing against source

Follow `references/thinker-corpus-protocol.md` and `references/research-corpus-protocol.md` in
full — open both the thinker's cleaned text and the research file's actual body. This step is
mandatory and does not get skipped for speed; see "Red flags" below.

### 4. Write the Grounding Brief

```markdown
---
date: [YYYY-MM-DD]
topic: "[topic]"
thinker: "[Name]"
concept: "[concept]"
research_codes: [[code]]
archetype: [A1/A2/A3]
status: candidate
---

# Grounding Brief: [topic]

## Pairing
- **Thinker:** [Name], *[Work]* — [concept] [THINKER: Name, Work, quotability]
- **Research:** [Author Year, code] — [finding] [RESEARCH: Author Year, quality rating]
- **Why this pairing:** [the mechanism-link sentence from the map row]

## Hook
[citation(s) for the hook beat; quotability restated here]

## Turn
[citation(s) for the turn beat; quotability restated here]

## Payoff
[citation(s) for the payoff beat — prefer the research file's own Content Hooks section over
re-deriving a number; quotability restated here]

## Reframe
[citation(s) for the reframe beat; quotability restated here]

## Safety handling
[Only if R5/R11/R12/R14 is touched — the specific constraints applied, per
references/safety-sensitive-handling.md. Omit this section entirely otherwise.]

## Verification record
- Thinker source opened: [file path + passage/lines confirmed]
- Research source opened: [file path + finding/citation/quality rating confirmed]

## Gap-fill flag
[Only if this pairing came from live-glob rather than the map — see
references/thinker-corpus-protocol.md Path 2 for the exact required heading/text]

## Handoff
Feeds shorts-ideation next. Travels forward as a companion artifact to shorts-scripting
(citation text per beat above) and visual-prompts (visual motif cue: [from the map row]).

## Alternates considered
[Non-interactive fallback only: the other slate rows not chosen, one line each]
```

### 5. Save it

Write the brief to `rgs-briefs/YYYY-MM-DD-<topic-slug>.md` (see `rgs-briefs/README.md` for the
schema). Confirm the file was written before ending the turn.

## Red flags — stop and re-verify

- About to write a `[THINKER:` or `[RESEARCH:` citation without having opened that exact file
  in this invocation → stop, open it first.
- "The map already verified this row, I don't need to re-check it" → the map records that a
  human verified the source once; the citation you're about to write still needs the passage
  confirmed present, every time.
- "This is taking too long, I'll paraphrase from what I remember about [thinker]" → this is the
  exact failure this skill exists to prevent. Open the file.
- About to produce 3 full verified briefs instead of a slate + one brief → don't; verification
  depth is the expensive, quality-critical step — spend it once, on the human's actual pick.

## Citation index

- `references/pairing-map.md` — the curated matches (Task 2 of the implementation plan; ~18–24
  rows across the brand's 7 signature thinkers).
- `references/thinker-corpus-protocol.md` — map-first/live-glob-fallback resolution procedure.
- `references/research-corpus-protocol.md` — research-code resolution + verify-policy rules.
- `references/safety-sensitive-handling.md` — R5/R11/R12/R14 protocol.
- `references/brand-voice-and-tone.md` — voice, lexicon, archetypes, spine, quotability rule.
- `references/worked-example.md` — one full topic-to-brief run.
```

- [ ] **Step 3: Verify the frontmatter against superpowers:writing-skills' checklist**

Confirm: `name` uses only letters/numbers/hyphens (`rgs-grounding` ✓); `description` starts
with "Use when," is third person, states triggering conditions only (no workflow summary —
re-read it: it names *when* to use the skill, never *how* it works internally) ✓; total
frontmatter is well under 1024 characters.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/rgs-grounding/SKILL.md
git commit -m "feat: author rgs-grounding SKILL.md, informed by RED baseline"
```

---

### Task 8: Test `rgs-grounding` (GREEN → REFACTOR) and author `worked-example.md`

**REQUIRED SUB-SKILL:** superpowers:writing-skills' "Testing All Skill Types" — `rgs-grounding`
is a **Technique skill** (concrete method with steps), tested with application scenarios, not a
discipline skill requiring a full rationalization table. It has exactly one discipline-shaped
rule embedded in it (mandatory source-open verification, never skipped for speed) — that one
rule got a targeted RED baseline in Task 7 Step 1; this task runs GREEN against the now-written
skill, REFACTORs if it fails, then runs a broader application-scenario GREEN check.

**Files:**
- Create: `.claude/skills/rgs-grounding/references/worked-example.md`
- Modify (REFACTOR branch only, conditional — see Step 2): `.claude/skills/rgs-grounding/SKILL.md`

**Interfaces:**
- Consumes: `.claude/skills/rgs-grounding/SKILL.md` and all its `references/*.md` (Tasks 2–7),
  and Task 7 Step 1's RED transcript.
- Produces: `worked-example.md`, referenced by `SKILL.md`'s citation index (already written in
  Task 7) and by the plan's Task 13 final integration check.

- [ ] **Step 1: GREEN — same pressure as Task 7's RED baseline, with the skill loaded**

Dispatch a fresh subagent with `rgs-grounding`'s `SKILL.md` and all `references/*.md` files
provided as context, and the identical pressured prompt from Task 7 Step 1.

Expected: the subagent's tool-call transcript shows it opening both
`veblen-theory-of-the-leisure-class.cleaned.md` and `rgs-f4-sport-parent-burnout.md` before
producing the pairing (per the skill's "Red flags" section and `thinker-corpus-protocol.md`'s
mandatory source-open step) — i.e., it resists the "you already know this, skip the file" framing.

- [ ] **Step 2: REFACTOR — only if Step 1 failed**

If the Step 1 subagent skipped either source file: identify the exact rationalization it used
(quote it), add it as an explicit named counter in `SKILL.md`'s "Red flags" section (edit the
file), and re-run Step 1 with a fresh subagent. Repeat until GREEN. If Step 1 passed on the
first try, skip this step — don't edit a passing skill speculatively.

- [ ] **Step 3: GREEN — full application scenario, end to end**

Dispatch a fresh subagent with the full skill loaded and this prompt:

```
Working directory: C:\Projects\ContentStudio. Use the rgs-grounding skill. Topic: "why so many
travel-sport kids quit around age 13." Run the full workflow — Pairing Slate, then (assume I
pick the top-ranked row) the fully-verified Grounding Brief — and save it.
```

Expected: a Pairing Slate with 2–3 rows in the documented format; a saved file at
`rgs-briefs/YYYY-MM-DD-why-so-many-travel-sport-kids-quit-around-age-13.md` (exact date/slug
may vary) containing all required sections from the SKILL.md template, a non-empty
"Verification record" section naming real file paths and passages, and correctly restated
quotability per beat.

- [ ] **Step 4: Write `worked-example.md` from the Step 3 transcript**

```markdown
# Worked Example: rgs-grounding

A full run of `rgs-grounding` against the topic "why so many travel-sport kids quit around age
13," from Pairing Slate through the saved Grounding Brief. Reproduced from an actual test
invocation (see the implementation plan's Task 8) — not a hypothetical.

[Paste the Step 3 subagent's actual Pairing Slate output here, verbatim.]

---

[Paste the Step 3 subagent's actual saved Grounding Brief file content here, verbatim.]
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/rgs-grounding/references/worked-example.md .claude/skills/rgs-grounding/SKILL.md
git commit -m "test: verify rgs-grounding resists skipped-verification pressure; add worked example"
```

(Include `SKILL.md` in this commit only if Step 2's REFACTOR loop actually modified it.)

---

### Task 9: Author `rgs-pairing-review/SKILL.md`

**REQUIRED SUB-SKILL:** superpowers:writing-skills.

**Files:**
- Create: `.claude/skills/rgs-pairing-review/SKILL.md`

**Interfaces:**
- Consumes: `.claude/skills/rgs-grounding/references/pairing-map.md`'s schema and ledger
  front-matter (Task 2), `manifests/thinkers.json`, `output/youth-sports/raisinggoodsports/rgs-*.md`
  front-matter, `rgs-briefs/*.md` (for the "Gap-fill flag" grep — Task 3's exact heading text).
- Produces: the `SKILL.md` Task 10 tests, and the one-line addition Task 12 makes to
  `README.md`'s refresh workflow.

- [ ] **Step 1: Write the file**

```markdown
---
name: rgs-pairing-review
description: Use after the thinkers corpus or RaisingGoodSports research corpus has been refreshed or expanded — new thinker works added to manifests/thinkers.json, or a research theme file re-split at a new edition — to detect what's new since the last pairing-map review and propose curated additions, or when asked to "review the pairing map," "check for new thinker or research content," or "expand the pairing map." Brand-specific to RaisingGoodSports; never runs on a schedule, only on request.
---

# RGS Pairing Review

A thin maintenance skill, separate from `rgs-grounding`: disjoint trigger ("I refreshed the
corpus, review the map") and disjoint output (a proposal document, not a Grounding Brief). Has
no `references/` of its own — it reads `rgs-grounding`'s
`.claude/skills/rgs-grounding/references/pairing-map.md` as its format and quality-bar
contract, so the quality criteria live in exactly one place.

**Never writes directly to `pairing-map.md`.** Every run ends in a proposal document the human
reviews; the human (or this skill, once told which rows to accept) then edits `pairing-map.md`
directly, and the resulting `git diff` on that file is the actual approval surface — mirroring
`output/youth-sports/raisinggoodsports/README.md`'s existing corpus-refresh approval pattern
("re-split the changed themes, get owner approval on the per-theme git diffs, then run the
ingest").

## Workflow

### 1. Read the current ledger

Open `.claude/skills/rgs-grounding/references/pairing-map.md`'s front-matter:
`last_review`, `thinker_slugs_reviewed`, `research_codes_reviewed`.

### 2. Diff against current corpus state — three checks

- **New thinker works:** every `slug` in `manifests/thinkers.json` tagged `parenting`, plus any
  new work by one of the brand's 7 signature thinkers (per `output/raisinggoodsports-brand-definition.md`)
  regardless of its pillar tags, not present in `thinker_slugs_reviewed`. Don't diff against the
  full 53-slug manifest unscoped — most of it (Adam Smith, Barnum, etc.) is unrelated to this
  brand and would flood every review with irrelevant "new" items.
- **New research:** every `code` across `output/youth-sports/raisinggoodsports/rgs-*.md`
  front-matter not present in `research_codes_reviewed` — **excluding any file whose front-matter
  `section` is `Meta`** (`rgs-meta-landscape-map.md`, `rgs-meta-open-questions.md`,
  `rgs-meta-verify-policy.md` — codes `LANDSCAPE`, `OPENQ`, `VERIFY`). These are reference/policy
  documents, not pairable research themes, and are deliberately absent from
  `research_codes_reviewed` — don't flag them as new on this or any future run.
- **Changed research:** every code that IS in `research_codes_reviewed` whose current file
  `edition` no longer matches the recorded value. For each, list every existing `pairing-map.md`
  row citing that code — these need re-verification, not just the new-row consideration new
  codes get.

### 3. Secondary signal — organically-flagged gaps

Grep `rgs-briefs/*.md` for the literal heading `## Gap-fill flag` (see `rgs-grounding`'s
`references/thinker-corpus-protocol.md`). Each match is a pairing `rgs-grounding` used outside
the map — add it to this review pass as a candidate, even if its thinker/research slugs were
already in the reviewed lists.

### 4. Verify and draft, or reject with a reason

For every new/changed/flagged item, run the identical source-open verification `rgs-grounding`
uses (open the thinker's `.cleaned.md` and/or the research file's actual body): confirm a
genuine concept exists, find a real passage/anchor, and check whether it pairs with something
already in scope. Draft a candidate row in `pairing-map.md`'s exact format (thinker heading,
concept subheading, all five fields) — never propose a row that hasn't actually been checked
against source; an unverified proposal turns the human's approval into a rubber stamp on an
unearned pairing. Where nothing fits, write "considered, no pairing found" with a one-line
reason. Zero new rows is an explicitly valid outcome of a review — say so plainly if that's
what happened, don't manufacture a weak row to have something to show.

### 5. Write the proposal

Save to `output/pairing-proposals/YYYY-MM-DD-proposal.md` (git-ignored — disposable working
material, unlike the `pairing-map.md` it feeds):

```markdown
# Pairing Map Review Proposal — [date]

## New/changed since last review ([last_review date])
- Thinkers: [list, or "none"]
- Research codes (new): [list, or "none"]
- Research codes (edition-changed): [list with old→new edition, or "none"]
- Gap-fill flags found in rgs-briefs/: [list with source brief filenames, or "none"]

## Proposed additions
[Each in pairing-map.md's exact row format, or "none proposed this review."]

## Considered and rejected
[One line each: what was checked, why it didn't earn a row.]

## Re-verification verdicts (edition-changed codes only)
[For each existing row citing a changed code: still holds / needs revision / needs removal, with reasoning.]
```

### 6. Get human approval, then apply

Present the proposal in conversation. On approval (whole or partial), edit the accepted rows
directly into `pairing-map.md`, and update its front-matter: bump `last_review` to today, add
every newly-considered thinker slug and research code (accepted or not — "considered" tracks
what was reviewed, not just what was kept) to `thinker_slugs_reviewed` /
`research_codes_reviewed`, and update any changed `edition` values. The human reviews the
resulting `git diff` on `pairing-map.md` before it's committed — that diff is the real gate.

## Red flags — stop and reconsider

- About to add a row to `pairing-map.md` before the human has approved this run's proposal →
  stop, that's a direct write, never allowed.
- About to propose a row without having opened the actual source file this run → stop, open it.
- Tempted to skip section 3 (the `rgs-briefs/` grep) because the diff in section 2 already found
  enough → don't skip it; organically-discovered gaps are a distinct signal from corpus growth.
```

- [ ] **Step 2: Verify frontmatter against superpowers:writing-skills' checklist**

Same checks as Task 7 Step 2: name is hyphen-only, description starts with "Use when," third
person, states triggering conditions only, under 1024 characters total.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/rgs-pairing-review/SKILL.md
git commit -m "feat: author rgs-pairing-review SKILL.md"
```

---

### Task 10: Test `rgs-pairing-review`

**Files:** none created; verification only.

**Interfaces:**
- Consumes: `.claude/skills/rgs-pairing-review/SKILL.md` (Task 9),
  `.claude/skills/rgs-grounding/references/pairing-map.md` (Task 2).

`rgs-pairing-review` is a **Reference/Technique skill** (retrieval + application) per
superpowers:writing-skills' testing guidance — tested with a retrieval scenario (does it find
what's actually new) and an application scenario (does it produce a correctly-formed,
never-direct-write proposal), not a full discipline pressure-test suite.

- [ ] **Step 1: Set up a detectable, reversible corpus-growth scenario**

Temporarily edit `.claude/skills/rgs-grounding/references/pairing-map.md`'s front-matter only,
removing one real, currently-reviewed thinker slug and one real research code from
`thinker_slugs_reviewed` / `research_codes_reviewed` (pick ones that already have rows in the
map, e.g. remove `dewey-democracy-and-education` and `R9` if Task 2 mapped Dewey to R9) — this
simulates "corpus grew since last review" without needing to fabricate fake corpus files.

- [ ] **Step 2: Run the skill**

Dispatch a subagent with `rgs-pairing-review`'s `SKILL.md` loaded and the prompt: `Run
rgs-pairing-review.` (working directory `C:\Projects\ContentStudio`).

Expected: the subagent's diff step reports the two slugs/codes you removed as "new since last
review" (confirming the diff mechanism works); it does NOT edit `pairing-map.md` before
presenting a proposal; it writes a proposal file to
`output/pairing-proposals/YYYY-MM-DD-proposal.md` in the documented format; the proposed rows
(if any) show evidence of source-opening (real file paths, real passage references) rather than
generic restatements.

- [ ] **Step 3: Revert the test edit**

```bash
git checkout -- .claude/skills/rgs-grounding/references/pairing-map.md
```

Run: `git status --short .claude/skills/rgs-grounding/references/pairing-map.md`
Expected: no output (file matches the last commit from Task 2/Task 5 revision, if any) —
confirms the test scenario left no residue in the committed map.

- [ ] **Step 4: Delete the test proposal artifact**

The file written in Step 2 lives under `output/` (git-ignored) — no git action needed, but
delete it so it doesn't confuse a later real run:

Run: `rm output/pairing-proposals/*.md` (or delete via your file tool)

- [ ] **Step 5: No commit needed**

This task is verification-only; Step 3 already confirmed no repo changes remain.

---

### Task 11: Update `CLAUDE.md`'s scope note

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: nothing new — corrects an existing scope claim now made false by Tasks 1–10.

- [ ] **Step 1: Read the current scope note**

Locate the "Out of scope, kept for structural completeness" paragraph in `CLAUDE.md` (under
"## What this is"), which currently reads:

```
**Out of scope, kept for structural completeness:** the toolkit also carries a
`thinkers` (AnchorAndWave public-domain library) and `youth-sports` (RaisingGoodSports)
corpus, and one general-interest roster entry (`@bigthink`/Adam Grant) inside
`output/brand-intel/`. None of these feed any ContentStudio skill — see `README.md`'s
scope note.
```

- [ ] **Step 2: Replace it**

```markdown
**Partially in scope:** the toolkit also carries a `thinkers` (AnchorAndWave public-domain
library) and `youth-sports` (RaisingGoodSports) corpus, plus one general-interest roster entry
(`@bigthink`/Adam Grant) inside `output/brand-intel/`. Both corpora now feed the
RaisingGoodSports-only `rgs-grounding` and `rgs-pairing-review` skills (see
`.claude/skills/rgs-grounding/` and `.claude/skills/rgs-pairing-review/`) — the general-interest
roster entry remains unused by any skill. See `README.md`'s scope note for the full picture.
```

- [ ] **Step 3: Verify**

Run: read `CLAUDE.md` back and confirm the paragraph now names both new skills and no longer
claims the thinkers/youth-sports corpora feed nothing.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: correct CLAUDE.md scope note now that rgs-grounding/rgs-pairing-review exist"
```

---

### Task 12: Update `README.md`'s scope note and refresh workflow

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing new — corrects the equivalent scope claim and adds the `rgs-pairing-review`
  trigger point Task 9's `SKILL.md` already documents as its primary cadence.

- [ ] **Step 1: Replace the scope note**

Locate (near the top, under "**Scope note:**"):

```
**Scope note:** ContentStudio's six shorts-production skills (see the
top-level `CLAUDE.md`) are built entirely from the **Brand-intel / headless
YouTube** row below — the `docs/` guides and `output/brand-intel/`. The
**Thinkers** and **Youth sports** rows are inert leftover toolkit capability,
carried over because this toolkit downloads three corpora as a unit; they are
not read by any ContentStudio skill.
```

Replace with:

```
**Scope note:** ContentStudio's six generic shorts-production skills (see the
top-level `CLAUDE.md`) are built entirely from the **Brand-intel / headless
YouTube** row below — the `docs/` guides and `output/brand-intel/`. The
**Thinkers** and **Youth sports** rows feed two RaisingGoodSports-only skills,
`rgs-grounding` and `rgs-pairing-review` (see `.claude/skills/rgs-grounding/`
and `.claude/skills/rgs-pairing-review/`) — carried over as a toolkit-wide
download because all three corpora download as a unit, but no longer inert.
```

- [ ] **Step 2: Locate and amend the "Regenerating the thinkers list" note**

Find:

```
`manifests/thinkers.json` was generated from a sibling app's source-of-truth
manifest via `gen_thinkers_manifest.ts` — see that file's header. It is **not
runnable standalone in this repo** (kept as documentation only; the thinkers
corpus is out of scope for ContentStudio's skills — see the scope note above).
```

Replace the parenthetical only:

```
`manifests/thinkers.json` was generated from a sibling app's source-of-truth
manifest via `gen_thinkers_manifest.ts` — see that file's header. It is **not
runnable standalone in this repo** (kept as documentation only; the JSON output
itself is what `rgs-grounding` and `rgs-pairing-review` read — see the scope
note above).
```

- [ ] **Step 3: Add the `rgs-pairing-review` trigger to the refresh workflow**

In the youth-sports corpus's own `README.md`
(`output/youth-sports/raisinggoodsports/README.md`), locate:

```
Refresh (Master Edition v3+): commit the new digest verbatim alongside this one, re-split the
changed themes (bump `edition`), get owner approval on the per-theme git diffs, then run
`npm run research:ingest` on the Pi and the laptop enrichment loop. See the deploy runbook.
```

Append one sentence:

```
Refresh (Master Edition v3+): commit the new digest verbatim alongside this one, re-split the
changed themes (bump `edition`), get owner approval on the per-theme git diffs, then run
`npm run research:ingest` on the Pi and the laptop enrichment loop. See the deploy runbook.
Then, in ContentStudio, run the `rgs-pairing-review` skill to detect the edition bump and
propose pairing-map updates.
```

Note: this file lives at `output/youth-sports/raisinggoodsports/README.md`, under the
git-ignored `output/` tree — it documents the workflow for humans maintaining the corpus
upstream and reading this copy locally; edit it the same way you'd edit any other file in this
repo (git-ignored doesn't mean read-only, it means not committed as part of ContentStudio's own
history). If this file is regenerated from an external source on next refresh, this addition
will need to be re-applied — note that in the same edit.

- [ ] **Step 4: Verify**

Run: read `README.md` and `output/youth-sports/raisinggoodsports/README.md` back; confirm both
scope corrections and the refresh-workflow addition are present and don't contradict `CLAUDE.md`'s
Task 11 wording.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: correct README scope note; document rgs-pairing-review refresh trigger"
```

(The `output/youth-sports/raisinggoodsports/README.md` edit is inside a git-ignored directory
and won't be picked up by `git add` — no separate commit needed for it, but confirm it saved to
disk in Step 4.)

---

### Task 13: Final integration dry run

**Files:** none created or modified — verification only.

**Interfaces:**
- Consumes: everything from Tasks 1–12.

- [ ] **Step 1: Full pipeline dry run**

Dispatch a subagent, working directory `C:\Projects\ContentStudio`, prompt: `Use rgs-grounding
for the topic "the club-soccer parent who spends $8,000 a year and can't say why." Produce a
full Grounding Brief.` No skill pre-loaded in the prompt — confirm the skill is discoverable
via its `description` alone (per superpowers:writing-skills' Discovery Workflow), i.e. the
subagent finds and invokes `rgs-grounding` without being told its exact name.

Expected: a saved brief in `rgs-briefs/`, structurally identical in shape to Task 8's worked
example, citing a real pairing-map row (or a flagged gap-fill), with a non-empty verification
record.

- [ ] **Step 2: Confirm no accidental FamilyBrain / firewall violations**

Run: `grep -rn "brain_" .claude/skills/rgs-grounding/ .claude/skills/rgs-pairing-review/`
Expected: no matches — neither skill references any `brain_*` MCP tool or FamilyBrain path,
consistent with `CLAUDE.md`'s firewall.

- [ ] **Step 3: Confirm `master-edition-v2.md` is never cited**

Run: `grep -rn "master-edition-v2" .claude/skills/rgs-grounding/ .claude/skills/rgs-pairing-review/ rgs-briefs/`
Expected: no matches outside of explicit "never cite this" warnings (i.e., it may appear in
prose telling the reader not to cite it, but never as an actual citation source in a brief or
map row).

- [ ] **Step 4: Final status check**

Run: `git status --short`
Expected: clean (everything from Tasks 1–13 committed, except the git-ignored
`output/youth-sports/raisinggoodsports/README.md` edit and any leftover `output/pairing-proposals/`
files from Task 10, which are expected to show as untracked/ignored, not as uncommitted tracked
changes).

- [ ] **Step 5: No commit** (verification-only task).
