# Coach-Prep: Framework Breadth, Doc Structure, and Google Docs Rendering — Design

Supersedes nothing. Extends `2026-08-17-freedom2beu-coach-prep-design.md`, whose
Phase 2 shipped a working but thin generation step.

## Context

`coach-prep-app` builds a private prep note for Ryan before each client session,
publishes it as a Google Doc draft into a Pending Review folder, and emails a review
link. The pipeline worked. The document did not earn its place in the room.

The gold standard is already in the corpus:
`Client Session Outlines/Josh/Josh — Session Plan Introducing Positive Intelligence
(Restart) v3.gdoc.md`. It opens with a summary and an explicit *why this direction*,
runs time-boxed parts, gives numbered "How to run it live" steps and sample framing to
say out loud, and closes on sensitivities to hold. What the app emitted was three flat
sections: activities, agenda, PQ sparks.

Five gaps, each measured against the code and corpus rather than assumed:

1. **Framework breadth.** Generation grounded in the 9 files of
   `program_sources.yaml`. The `Frameworks to consider/` corpus — 43 Jay Shetty
   coaching tools, 9 saboteur modules, CBT worksheets, the Wayfinders field guide,
   Wheel of Life, NLP — was unreachable. The doc could not suggest the right exercise
   because it had never seen it.
2. **Thin inputs.** One sent email and one meeting note.
3. **Google Docs rendering.** `publish_draft` uploaded `text/plain`, so Drive stored
   the markdown verbatim and Ryan opened the draft to literal `## Part 1` characters.
4. **The book list.** `F2BU Coaching Book Recommendations.gsheet` was in the watched
   tree and had *failed conversion*. So had every other gsheet — 0 of 6, ever.
5. **Retrieval at scale.** 712KB of framework body across 92 files, and a generation
   subprocess that is deliberately tool-denied and so cannot fetch anything itself.

## Decisions

### A catalog, not a vector store

The generation subprocess runs `claude -p` with every tool disallowed,
`--strict-mcp-config`, and an empty scratch cwd. That isolation is the app's core
safety property, and an MCP-backed retrieval cannot be reached from inside it without
dismantling it.

So retrieval happens *before* the call, in Python. The corpus is too big for one prompt
but small enough that a distilled index of **all** of it fits in ~12K tokens: one terse
line per activity. Selection therefore sees every option at once rather than whatever a
similarity search surfaced, and the choice is auditable rather than probabilistic.

Rejected: an Obsidian vault (a second source of truth, and unreachable from the
isolated turn), embeddings (an 180K-token corpus does not justify the machinery), a
knowledge graph (nothing here is a graph problem). Revisit past ~500 corpus files.

### Two stages

- **Stage 1, select.** Compact catalog index + this client's last two sessions and
  fortnight of email → 3–5 activity ids with a client-specific reason each.
- **Stage 2, draft.** The same bundle, now carrying the **full text** of only what
  stage 1 picked → the prep doc.

Selection sees everything; drafting reads deeply. Picks are validated against the
catalog mechanically: an id the catalog does not have is the model naming a coaching
tool from its own training rather than from Ryan's library, so it is reported by id,
never quietly dropped. A prep doc built on a half-invented selection is
indistinguishable from one built on the corpus.

### YAML is the catalog; SQLite is a cache

`framework_catalog.yaml` is git-tracked and hand-editable. The build pass gets entries
wrong; a human corrects one and sets `curated: true`, and no rebuild overwrites it.
Entries whose source version has since moved on are named on stdout rather than kept
silently — an entry pinned to text that no longer exists is how a catalog rots.

ids are unique per *document* (each file is indexed by its own isolated turn, which
cannot see the others), so `merge()` disambiguates collisions with a suffix derived
from `rel_path` — derived, not counted, because curated entries are matched by id and
an id that shifted between rebuilds would orphan its edits.

### Provenance: tags in Part 1, manifest at the end

Ryan reads this mid-call. Bracket labels in every sentence cost more in readability
than they buy in traceability. Part 1 — the check-in on what was asked for — keeps
inline tags. The rest reads as prose.

The closing manifest is rendered in Python from the `generation_inputs` rows and
appended **after** the gates run. Two reasons, both load-bearing:

- **Completeness.** The rows are written before generation starts, so they cover every
  source that went in. A model asked to list its sources lists the ones it remembers
  using.
- **Integrity.** Text the model cannot write is text it cannot weaken, and the
  confidentiality notice is the one line that must never be softened. Appending before
  the citation gate would also let a model satisfy that gate by writing its own footer.

## Architecture

```
calendar event
  ↓
build_bundle          emails (14d, ≤5) · notes (2, by MEETING date) · program · book list
  ↓
select_frameworks     stage 1 — catalog index in, 3-5 validated ids out
  ↓
generate              stage 2 — full text of the picks in, prep doc out
  ↓
gates                 citation · leakage · round-trip-safe markdown
  ↓
manifest.append_to    confidentiality + complete source list  (model cannot touch this)
  ↓
publish               text/markdown → a real Google Doc
```

`cli_runner.run_isolated` is the single definition of the isolated turn, shared by all
three callers.
`test_no_module_spawns_claude_outside_run_isolated` makes that structural: any module
under `coach_prep_app/` that spawns its own subprocess fails the suite.

## The document

| Part | Content | Time box |
|---|---|---|
| Summary + Why this direction | Where the client is; the argument for this focus over the alternatives | — |
| Part 1 | Last email's asks, restated as questions Ryan can say out loud. Inline tags. | 20% |
| Part 2 | The program's next step, reinforced by saboteur/Sage material. Chosen activities as other ways in. A reading if genuinely apt. | 45% |
| Part 4 | One live-ready practice, with numbered how-to-run-it steps | 15% |
| Sensitivities | Where this could land badly | — |
| Footer | Confidential notice + complete source manifest | — |

Parts 3 and 5 of the house format are out of scope and are not asked for, so no empty
placeholder headings appear. Time boxes are computed in Python from the calendar
event's real duration — a model doing arithmetic in prose produces boxes that do not
add up, and an all-day or malformed event falls back to a default rather than printing
"~0 min". The shares deliberately do not sum to 100%: a plan timed to the last minute
breaks the moment a client says something real.

## Prerequisite: the gsheet gauntlet

The book list could not become a program source because it could not convert. Nor could
any gsheet — 0 of 6 in production, while the conversions themselves were perfect. Two
counters compared the wrong quantities:

- `read_xlsx_sheet_and_row_counts` counts every non-empty source row, header included;
  `_count_output_table_rows` subtracts each table's header. Output was short by exactly
  one row per sheet, always.
- `_count_output_table_blocks` counts markdown *tables*, but firecrawl starts a new one
  whenever the column structure changes — a 3-sheet workbook rendered as 6. At
  `sheet_count_tolerance = 0` that could never balance.

Fixed by correcting the counters, not by widening the bands. Measured across all six
real exports, the row ratios land at 1.000, 1.000, 0.984, 1.000, 1.000, 1.000.

A second defect surfaced immediately after: `enqueue_pending_jobs` suppresses a retry
when a file already failed at this source version — right, since it stops the cron
burning firecrawl credits on a permanently broken file every wake, but the key is the
*source* version, so a fixed converter could never reach the files it fixed.
`--retry-failed <pattern>` is the operator's escape hatch, targeted so a fix for one
class does not re-attempt files still failing for unrelated reasons.

## Testing

Per CLAUDE.md, every defect fixed here names the assertion that would have caught it
and lands it as a regression test observed failing first. The notable ones:

| Risk | Assertion |
|---|---|
| Invented coaching tools reaching the doc as if corpus-grounded | `test_validate_picks_separates_ids_the_catalog_does_not_have` |
| A rebuild reverting a hand correction | `test_merge_never_overwrites_a_curated_entry` |
| The catalog index outgrowing the budget the design rests on | `test_render_index_of_the_whole_corpus_stays_within_prompt_budget` |
| The footer scanned as model output, or forgeable | `test_the_footer_is_appended_after_the_gates_have_run` |
| A leaked draft published with an authoritative-looking manifest | `test_a_gate_failure_publishes_no_footer_and_no_document` |
| Markdown that will not survive the Google Docs round trip | `test_markdown_that_will_not_survive_google_docs_fails_the_gate` |
| The isolation reimplemented per caller and drifting | `test_no_module_spawns_claude_outside_run_isolated` |
| A hand-written stub drifting from the function it stands in for | `test_sample_bundle_matches_the_real_shape` |
| Notes ordered by ingest time rather than meeting date | `test_notes_order_by_meeting_date_not_converted_at` |
| Gate 1 rejecting every real gsheet | `test_real_gsheet_export_passes_sheet_and_row_checks` |

Two stub-drift bugs were found *by* this work rather than introduced by it. The
orchestrator's `build_bundle` stub kept retired keys, so the suite sat green at 206
passing while `process_candidate` would have raised `KeyError` on the first real run.
Five hand-written `generate_draft` lambdas broke the moment the real signature grew a
parameter. Both now have contract tests.

## Known gaps

- **doc-ingest-app is absent from CLAUDE.md's network roster.** Its Drive and firecrawl
  calls match no existing probe, and adding the globs without the probes would look like
  coverage while measuring nothing. Stated in CLAUDE.md in place; probes and rows belong
  in one commit.
- **Nineteen corpus files still fail conversion** for reasons outside this work —
  word-count parity, unbalanced code fences, one corrupt docx. They are absent from the
  catalog and nothing pretends otherwise.
- **Part 3 and Part 5** of the house format are unimplemented by choice.
