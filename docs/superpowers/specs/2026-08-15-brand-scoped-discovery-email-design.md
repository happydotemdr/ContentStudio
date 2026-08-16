# Brand-scoped discovery email — design note

**Status:** approved for implementation, 2026-08-15.

## Problem

The daily discovery email (`discovery_notify.notify`) renders one undifferentiated
inventory of every monitored handle's new content. All 15 currently-registered
handles carry `cohort='guru'` in the `handles` table — there is no concept of
"brand" anywhere in the schema. The operator runs three distinct content brands
(RaisingGoodSports, Freedom2BeU, and a general "gurus" inspiration roundup) and
wants the morning email split into three sections, one per brand, each in the
exact format the single email uses today (run-status banner, spotlight post with
three AI-drafted comments, grouped inventory).

## What the corpus assessment found

- `docs/` + `output/brand-intel/youtube/{14 craft channels}` and
  `manifests/thinkers.json` + `output/youth-sports/raisinggoodsports/` are both
  **static, one-time-extracted reference corpora** consumed by the Shorts
  production skills (`rgs-grounding` etc.). Neither is live and neither feeds
  the daily email.
- The **live** discovery roster (`handles` table, 15 rows) was never seeded from
  `manifests/brand_sources.json` — that manifest only declares the 14 static
  craft-corpus channels, all with empty `instagram`/`linkedin-profile`/
  `linkedin-company` arrays. The 15 live "guru" handles were added directly
  through the `/discovery/handles` UI, independently of the manifest. The
  manifest is therefore **not** the right place to add brand tags for this
  roster; the DB (managed through the app, per existing convention) is.
- Of the 15 live handles, 4 are youth-sports-parenting accounts (Aspen Institute
  Project Play, Changing the Game Project ×2, Positive Coaching Alliance) and 10
  are general self-development/parenting-psychology accounts that line up with
  Freedom2BeU's documented "high-functioning neuroqueer cycle breaker" niche
  (Dr. Becky/Good Inside, Nir Eyal, Daniel Pink, Dr. Dan Siegel, Positive
  Intelligence, Impact Parents). One (Next Big Idea Club) fits neither
  specifically and stays guru-only.
- `Freedom2BeU/converted/` (the operator's own coaching-practice Google Drive
  mirror — client session notes, business documents) is **not** a candidate
  source for this email. It is private client data with no public posts to
  monitor, and piping it through `comment_draft.py` (built to draft comments for
  posting on public social content) would be a scope/privacy violation. The
  Freedom2BeU section is sourced from re-tagging existing/new **public**
  discovery handles, same as the other two brands.

## Decisions (confirmed with the operator)

1. **Freedom2BeU sourcing:** re-tag existing handles only, no new handles added
   in this pass.
2. **Tagging model:** multi-tag. One handle can carry more than one brand, and
   its items render once per section it belongs to (duplication across sections
   is expected and accepted, not deduplicated).

## Data model

New table `handle_brands` (handle_id, brand) — many-to-many, **no CHECK
constraint** on `brand`. Every other closed vocabulary in this schema
(`platform`, `status`) is CHECK-constrained because those values gate adapter
dispatch and a bad value is a startup-crashing defect (B-73). `brand` is
different: it is an open, growing taxonomy the operator controls test-free
(literally more brands are expected as the business grows), and this schema's
own documented cost of a CHECK is a full create-copy-drop-rename rebuild to
widen it later (see `_MIGRATION_1_HANDLES_STEPS`'s comment block in `db.py`).
An unrecognized brand tag just means that handle's content renders in no
section — a soft, discoverable failure, not a boot-time crash — so the
open-text tradeoff is the right one here, matching the existing precedent of
`cohort` (also unconstrained, also UI-suggested only).

`guru` becomes a **real, explicit** `handle_brands` row rather than an implicit
reading of `handles.cohort == 'guru'`. This keeps brand membership single-source
(`handle_brands` alone answers "which sections does this handle's content
appear in"), and keeps `cohort` doing only what it always did (a roster
category, unrelated to which brand's email section a handle serves).

## Email structure

One email, one send, three stacked sections in this order: **Freedom2BeU →
RaisingGoodSports → Gurus**. Each section is internally identical to today's
single-email body (run-status line when relevant, spotlight + 3 comment drafts,
grouped inventory, errors) computed from that brand's item subset.

**Run status and the errored-handle list are shown identically in every
section, not brand-filtered.** They are the pipeline's operational signal ("did
today's run have problems"), not brand content — the only reader of this email
is the operator, who already knows the full roster, so repeating the same
"Errors: @handle" line under all three sections is more useful than silently
deciding it does not belong to a given brand.

**The subject line's post count is the distinct-item count from the
pre-partition summary**, not a sum of the three sections' sizes — since a
handle tagged both `raisinggoodsports` and `guru` renders in two sections, a
naive sum would double-count it.

**Cost note:** because each section computes its own spotlight, a run where
all three sections have a *distinct* spotlight makes up to three `claude -p`
subprocess calls instead of one (up to ~4.5 minutes combined at the existing
90s timeout, plus 3× the Claude usage this feature already costs). In
practice this is the worst case, not the typical one: `guru` is a superset of
the other two brands, so its spotlight is frequently the same post as
`raisinggoodsports`'s or `freedom2beu`'s best-within-brand pick.
`discovery_notify.notify` caches drafts by `(platform, handle, item_id)` and
reuses them across sections rather than re-drafting an identical post, so the
common case is one or two calls, not three (see the pre-execution review's
finding #2, folded into the plan).

## Initial tagging

Applied once via `pipeline-app/scripts/tag_handle_brands_2026_08.py`
(idempotent — safe to re-run):

| Platform | Handle | Brands |
|---|---|---|
| instagram | aspenprojectplay | guru, raisinggoodsports |
| instagram | ctgprojecthq | guru, raisinggoodsports |
| linkedin-company | positive-coaching-alliance | guru, raisinggoodsports |
| linkedin-profile | coachjohnosullivan | guru, raisinggoodsports |
| instagram | drbeckyatgoodinside | guru, freedom2beu |
| linkedin-profile | drbecky | guru, freedom2beu |
| linkedin-profile | danielpink | guru, freedom2beu |
| linkedin-profile | nireyal | guru, freedom2beu |
| youtube | @ImpactParents | guru, freedom2beu |
| youtube | @danielpinktv | guru, freedom2beu |
| youtube | @drdansiegel | guru, freedom2beu |
| youtube | @goodinside | guru, freedom2beu |
| youtube | @nirandfar | guru, freedom2beu |
| youtube | @positive-intelligence | guru, freedom2beu |
| youtube | @NextBigIdeaClub | guru |

## Open classification question (confirm before running Task 7)

The pre-execution review flagged the mapping above as directionally sound but
not unanimous:

- **Daniel Pink and Nir Eyal** (4 of the 15 rows, once each on two platforms)
  are general behavioral-science/business authors — *Drive*, *When*,
  *Indistractable* — not parenting or neurodivergence-specific. They are the
  weakest fit for `freedom2beu`'s "high-functioning neuroqueer cycle breaker"
  niche in the table.
- **Dr. Becky and Dr. Dan Siegel** are parenting-first and arguably belong in
  `raisinggoodsports` too (youth-sports parenting is still parenting) — the
  multi-tag model supports adding a second brand to these rows and the
  mapping currently doesn't.

Neither point blocks implementation — the table is a reasonable starting
point and every tag is changeable later through the Task 6 UI with no code
change. Revisit it once, deliberately, before or shortly after Task 7 runs.

## Out of scope for this pass

- Onboarding new Freedom2BeU- or RaisingGoodSports-specific handles.
- Any read of `Freedom2BeU/converted/` from the discovery/email pipeline.
- A fourth brand or a general "which brands exist" registry beyond the two new
  section labels `email_render.py` knows about.
