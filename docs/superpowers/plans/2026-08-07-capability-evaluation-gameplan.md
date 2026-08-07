# ContentStudio — End-to-End Capability Evaluation Game Plan

**Date:** 2026-08-07 · **Scope:** everything merged in PRs #12–#18 (last 48h)

---

## Context

Seven PRs merged in 48 hours added three genuinely new capabilities and rebuilt two
existing ones. None of them have been exercised together, and two of them have never
been exercised *at all* on real content:

- The **stitcher** (`stitcher/`, PR #18, +17,132 lines) has never rendered anything.
  `stitcher/renders/` does not exist.
- The **Bright Data Instagram and LinkedIn adapters** (PRs #12/#14/#16) have never
  produced a single file. `output/brand-intel/` contains only `bluesky/` and `youtube/`.
- The **styleboard split** (PR #17) moved the world lock into a new stage and replaced
  literal `--sref` codes with slot tokens. Zero `styleboard` rows exist in `pipeline.db`.
- **Read-aloud Gates D and E** (PR #15) replaced shorts-scripting's humanize pass. No
  script artifact in the repo carries a `Gate D:`/`Gate E:` line.

The goal is to evaluate each capability end to end while producing real output: one
publishable MP4 from assets that already exist, a working IG/LinkedIn corpus of creators
worth following, and one brand-new Short carried from idea to finished video through all
nine pipeline stages.

**A blocker was found during research and must be fixed first — see Track 0.2.**

---

## What shipped (the evaluation surface)

| PR | Capability | Never exercised? |
|---|---|---|
| #18 | Stitcher: `render-spec.json` + assets → QA-gated 1080×1920 master, cover, caption sidecars | **Yes — zero runs** |
| #17 | `shorts-styleboard` stage; slot tokens; Gate C checks C16–C19 | **Yes — zero styleboard rows** |
| #16 | LinkedIn profile + company adapters on a shared Bright Data client | **Yes — zero files** |
| #15 | Read-aloud Gates D (deterministic linter) and E (fresh-Opus critic) | **Yes — no gated script** |
| #14/#12 | Instagram adapter (Bright Data) | **Yes — zero files** |
| #13 | `music-brief` stage + `elevenlabs-music` specialist | **Yes — never run for any slug** |

**Current 9-stage `pipeline.yaml`:**
`grounding` → `ideation` → `scripting` *(Gate D)* → `styleboard` → { `voiceover`, `visual` *(Gate C)*, `music` } → `assembly` → `repurpose`

---

## Decisions taken

| Decision | Choice |
|---|---|
| Gate C blocker | **Fix `gates.py` first.** Track C is gated on it landing. |
| New-Short spend | **Full new Short (~$60–120)** — real Midjourney renders, real ElevenLabs VO + music, final stitcher render. |
| IG/LinkedIn handles | **I propose candidates, you approve** before anything is registered. |
| New-Short topic | **Reuse a shelved rgs-brief.** Recommendation below. |

**Recommended topic: `rgs-briefs/2026-07-25-8000-a-year-club-soccer-parent.md`** — Alfred
Adler × S5, archetype **A2**. Three reasons: Adler is a fresh thinker (do-less used Ellen
Key, and reusing her would trip the recency ledger); **A2 is a different archetype from
do-less's A1**, so the script and visual structure exercise different code paths; and
Adler's Vienna consulting room is a strong Register B world that contrasts hard against a
present-day club-soccer complex — a real test of the dual-register slot system rather than
a soft one. Confirm at kickoff or swap for `why-parents-overspend-on-travel-teams` (Veblen
× F4, A1).

---

## Track 0 — Preconditions and the Gate C fix

*~2 hours, $0. Everything else depends on this.*

### 0.1 Run the styleboard backfill migration

`migrations.backfill_styleboard_rows` is called from `create_app`
([`main.py:25`](pipeline-app/pipeline_app/main.py:25)) and only runs when uvicorn invokes
the factory. It has not run since #17 merged.

```bash
cd C:/Projects/ContentStudio/pipeline-app && .venv/Scripts/python.exe -m uvicorn pipeline_app.main:create_default_app --factory --host 127.0.0.1 --port 8420
```

**Pass:** all three hold —
- `runs/do-less-20260728-190724/02b-styleboard/` exists
- `select count(*) from stages where stage_id='styleboard'` returns **4**
- stderr contains **no** `backfill_styleboard_rows: skipping project` line

**Trap:** the migration is deliberately non-fatal per project. A skip message means a
legacy artifact was unreadable and *that project's `visual` stage stays locked forever*
until the artifact is fixed. A silent partial backfill looks exactly like success — check
for the message explicitly.

### 0.2 Fix app-mode Gate C — **BLOCKER**

**Verified failure.** The same prompt sheet gives two different answers:

| Path | Result |
|---|---|
| CLI: `lint_prompt_sheet.py passing_sheet.md --styleboard passing_styleboard.md` | `Gate C: PASS — 5 shots, 0 findings` |
| App: [`gates.py:59`](pipeline-app/pipeline_app/gates.py:59) `parse_sheet(artifact)` only | `world keys: []` → **11 blocking C8 findings** |

[`run_prompt_sheet_gate`](pipeline-app/pipeline_app/gates.py:57) reads the world lock out
of the prompt sheet, but [`visual-prompts/SKILL.md:99`](.claude/skills/visual-prompts/SKILL.md:99)
instructs the skill **not to re-emit the WORLD LOCK block**. So on any post-#17 sheet
`world = {}` → `check_world_lock` fires C8 on every Register A shot and `check_slots`
fires C18 on every slot token → Gate C `fail` →
[`approval_service.py:52`](pipeline-app/pipeline_app/approval_service.py:52) blocks
approval → `visual` never approves → `assembly` never unlocks. **Track C dies at stage 6
of 9.**

Second defect in the same function: it calls `lint()` but never `check_cover_present` /
`parse_cover` / `lint_cover`, so **C19 and the entire cover lint are silently unenforced
in app mode** while enforced on the CLI. App-Gate-C and CLI-Gate-C are two different gates.

**The fix:**

1. Widen the `GateRunner` signature ([`gates.py:21`](pipeline-app/pipeline_app/gates.py:21))
   to accept the upstream artifact paths. `turn_service.py` already has them — it builds
   `depends_on` from `upstream_paths` immediately above the `run_gates_for_stage` call at
   [`turn_service.py:234`](pipeline-app/pipeline_app/turn_service.py:234), and `visual`
   already declares `depends_on: [scripting, styleboard]` in `pipeline.yaml`.
2. In `run_prompt_sheet_gate`, resolve the styleboard artifact from those paths and parse
   its world lock, mirroring the CLI's `--styleboard` branch in
   [`scripts/lint_prompt_sheet.py:859`](scripts/lint_prompt_sheet.py:859). Keep the legacy
   fallback: if the sheet carries its own WORLD LOCK, use it.
3. Add the cover checks so app-Gate-C == CLI-Gate-C.
4. Respect the standing comment at [`gates.py:80`](pipeline-app/pipeline_app/gates.py:80) —
   **do not** add a TypeError signature fallback. Update `run_script_language_gate` to the
   new signature too.

**Pass:** a new test in `pipeline-app/tests/test_gates.py` asserts that
`run_prompt_sheet_gate` on `tests/fixtures/passing_sheet.md` with
`tests/fixtures/passing_styleboard.md` as upstream returns **zero blocking findings**, and
that the legacy `tests/fixtures/legacy_do_less_sheet.md` with no styleboard still parses
its own world lock. Both existing suites stay green.

### 0.3 Baseline both test suites

Two interpreters with divergent dependencies. **`pipeline-app/.venv` has no Pillow** — the
stitcher cannot run inside it.

```bash
cd C:/Projects/ContentStudio/stitcher && C:/Python314/python.exe -m pytest tests/ -q
```
```bash
cd C:/Projects/ContentStudio/pipeline-app && .venv/Scripts/python.exe -m pytest tests/ -q
```
```bash
cd C:/Projects/ContentStudio && C:/Python314/python.exe -m pytest tests/ -q
```

**Pass:** all three green. Watch two specific things:
- `stitcher/tests/test_spec.py::test_the_committed_json_schema_matches_the_models` — if it
  fails, the committed `stitcher/schema/render-spec.schema.json` no longer describes what
  actually validates. Regenerate with `cd stitcher && python -m stitcher.spec` before
  authoring any spec against it.
- Whether `test_e2e.py` **skipped**. A skip means the golden render path is unproven on
  this machine, and Track A is the first real test of it.

**Confirmed present:** ffmpeg/ffprobe 9.0 with libx264, claude CLI 2.1.212,
`BRIGHTDATA_API_KEY`, `YOUTUBE_API_KEY`, `RESEND_API_KEY`.
**Confirmed missing:** Montserrat/Poppins fonts (only `arialbd.ttf`, `impact.ttf`,
`bahnschrift.ttf` are installed) — install Montserrat now if Track A is to be on-brand.

---

## Track A — Stitcher retrofit of the do-less Short

*~3–4 hours, $0. Highest value per hour. Produces a real publishable MP4 today.*

Every asset already exists. `Generated Assets/do-less-20260728-190724/` holds 15 stills at
1632×2912, a cover, 7 VO mp3s, and a 55.000s music bed — and
[`rgs-briefs/2026-08-05-do-less-sold-as-win-more-assembly-v3.md`](rgs-briefs/2026-08-05-do-less-sold-as-win-more-assembly-v3.md)
is a complete 16-cut build sheet with frame-exact timings.

**Run this before Track C, not after.** The stitcher's constraints are severe and
non-obvious (§A.6), and they need to reach the new Short's styleboard and visual stages as
*inputs*, not as a post-mortem after you've paid for 14 Midjourney renders. Track A is also
the concrete specification for the missing adapter: the diff between what `shorts-assembly`
emits and what `render-spec.json` needs *is* the requirements doc.

### A.1 Build the workspace

Slug must equal the directory name (`preflight._check_slug`), and `--root` defaults to the
**relative** `Path("renders")` resolved against CWD. Both are satisfied by always running
from `stitcher/`.

```
C:/Projects/ContentStudio/stitcher/renders/do-less-sold-as-win-more/
    render-spec.json
    assets/
```

Never run with `pipeline-app/.venv` activated (no Pillow). Never run from the repo root —
it silently creates `C:/Projects/ContentStudio/renders/` and then fails preflight with a
confusing "asset not found".

### A.2 Copy assets and apply the mandatory crop

Copy — never move — from `Generated Assets/`, so the build sheet's provenance survives.

Then apply §0.2's crop. `Shot 2_HD.png` renders Ellen Key's face fully lit and legible; the
world lock forbids a likeness, and the brief marks this **"not optional… the only thing
standing between the ship-as-rendered decision and a breached publish constraint"** `[G]`.
**The render-spec has no per-shot crop field** — a `Shot` has `source`/`source_in`/
`source_out`/`motion` and nothing else — so it must be baked into the asset:

```bash
ffmpeg -i "Shot 2_HD.png" -vf "crop=1632:1893:0:1019" assets/shot02_cropped.png
```

**Pass:** `ffprobe` reports `1632x1893` and no face is visible. **This gates the whole
track.** The stitcher's QA will report `pass` on an unpublishable video — it cannot check
this.

*Not a trap:* 1632×2912 → 1080×1920 conform is automatic and free.
`shots.py:140` scales with `force_original_aspect_ratio=increase` then crops; the aspect
delta is 0.56044 vs 0.5625, costing **7 pixels of height total**.

### A.3 Author `render-spec.json`

No adapter exists — hand-author from the build sheet. Use §1's authoritative VO timeline:

| stem | file | `at` | out |
|---|---|---|---|
| vo1 | VO_1.mp3 | 0.000 | 5.486 |
| vo2 | VO_2.mp3 | 5.836 | 14.117 |
| vo3 | VO_3.mp3 | 14.117 | 25.846 |
| vo4 | VO_4.mp3 | 26.046 | 28.397 |
| vo5 | VO_5.mp3 | 28.547 | 40.668 |
| vo6 | VO_6.mp3 | 41.068 | 47.677 |
| vo7 | VO_7.mp3 | 47.927 | 54.275 |

Runtime 54.800 with a 0.500s visual tail. Shots come straight from §2's 16-cut table.

**Field-level traps, in order of how quietly they bite:**

- **A pure "drift" renders motionless.** Cuts 3, 5, 9, 13 specify drift with no zoom. In
  `motion.crop_exprs`, `kind: "none"` makes the conform size equal the crop size, so
  `scale_w - crop_w == 0` and the anchor has zero room to move. A drift **must** be
  authored as `kind: "scale_up"` with a non-zero `amount_pct` plus differing
  `anchor_start`/`anchor_end`. **No error, no warning — it just renders static.**
- **Cut 14's rack-focus substitute is impossible.** No blur filter exists anywhere in
  `stitcher/`. Degrade to a push-in and record the deviation.
- **Captions are not burned in.** `assemble.py` composites `overlay_pngs` only;
  `derive.write_srt`/`write_ass` emit sidecars. §5's full-duration karaoke track — the one
  justified by the 80–85%-muted corpus finding — **will not be in the master.** Author §5's
  ~12 overlay cards as `overlays` (they burn in and exercise the safe-zone check) and put
  the caption track in `captions` as a sidecar. Keep overlays ≤ ~15: each becomes a separate
  input to one `filter_complex` call.
- **No colour grading exists.** §4's grade spec is the mechanism the ship-as-rendered
  decision relies on to carry the register split. The v01 master will be **ungraded**, and
  cuts 11 and 13 will read as near-twins — the exact failure §4 exists to prevent. Decide
  up front: ship ungraded as a renderer proof, or treat the stitcher output as an
  intermediate and grade in CapCut. **Recommended: ship ungraded as the proof, note the
  gap, grade separately for actual publication.**
- **Bed `gain_db` and `duck_db` are relative to the measured voice reference**, not
  absolute. §6's "−21 to −22 dB under the voice" → `duck_db: -21`, `gain_db: ~-14`.
  Authoring these as absolute dB is the most likely cause of a `duck_depth` QA failure.
- **`font_file` must be an absolute path to a font Pillow can load.** `preflight._check_fonts`
  calls `ImageFont.truetype` and `_check_text_fit` pre-wraps against real metrics — an
  overlay overflowing `max_lines` is a **preflight error**, not a render surprise. §5 wants
  Montserrat ExtraBold, which is not installed. Install it, or substitute
  `C:/Windows/Fonts/arialbd.ttf` and record a brand deviation. Budget one preflight
  round-trip on `max_lines` either way.
- `spec_version: "1.0"` is the only accepted value. `canvas` must be 1080×1920. Shots must
  start at exactly `0` and be contiguous (`shot[n].in == shot[n-1].out`) — §2's table
  already is; verify by differencing.
- Loudness per §6: `integrated_lufs: -14`, `true_peak_dbtp: -1.5`. Tolerance ±1.0 LU.

### A.4 Validate → draft → final

```bash
cd C:/Projects/ContentStudio/stitcher && C:/Python314/python.exe -m stitcher validate renders/do-less-sold-as-win-more/render-spec.json
```
**Pass:** exit 0, prints `… is valid (16 shots, N overlays)`. Any frame-alignment `warning:`
is an authoring error — fix the time, don't ignore it.

```bash
cd C:/Projects/ContentStudio/stitcher && C:/Python314/python.exe -m stitcher render do-less-sold-as-win-more --mode draft
```
**Pass:** exit 0 and a draft MP4 in `out/`. **Then read the QA markdown** — if it carries
the `PREVIEW AUDIO` banner, your stems didn't resolve and the whole dB model was bypassed.
That is a failure even though it exits 0.

```bash
cd C:/Projects/ContentStudio/stitcher && C:/Python314/python.exe -m stitcher render do-less-sold-as-win-more --mode final
```
**Pass:** exit **0** and `renders/do-less-sold-as-win-more/out/do-less-sold-as-win-more_v01_1080x1920.mp4`
exists. Only a QA `pass` promotes. Exit 3 = measured and wrong; exit 4 = could not measure
(usually a cleaned `work/` — re-run rather than debug).

**Budget real wall-clock.** `SUPERSAMPLE_FINAL = 4` scales each still to 4320×7680 under
lanczos before cropping, at `-preset slow`, for 55s at 30fps.

**Anticipated first-pass failures** (expected, not bugs):
1. `overlay '<id>' does not fit style '<name>'` — Arial Bold metrics vs Montserrat's. Exit 1.
2. `safe_zone` FAIL — §5 declares top 12% / bottom 20% / right 12% off-limits, so
   `safe_zone` = `{x:0, y:230, width:950, height:1306}`. Overlay bboxes must sit inside it.
3. `duck_depth` FAIL — absolute vs voice-relative dB.

### A.5 Cache sanity

Re-run the identical final command. **Pass:** `no changes; …_v01_1080x1920.mp4 is current`,
exit 0, no new version minted. Then change one overlay's text and re-run. **Pass:** stages
B/D/E/F re-render and `v02` appears alongside `v01`.

If you ever change stitcher *code* and get "no changes", bump `CACHE_EPOCH` in
[`stitcher/stitcher/cache.py`](stitcher/stitcher/cache.py) (currently `1`).

### A.6 Write the capability boundary doc

The deliverable that makes Track C cheaper. One page in
`docs/superpowers/specs/` recording what the renderer **cannot** do — per-shot crop, any
blur, colour grading, burned-in captions, pan-without-zoom — so `shorts-assembly` and
`shorts-styleboard` stop specifying them.

---

## Track B — Bright Data Instagram + LinkedIn

*~1 hour active, small Bright Data spend. Fully parallel to A and C.*

### B.0 Disconnect Proton VPN — do this first

NetShield NXDOMAINs `brightdata.com`. **Pass:** `nslookup api.brightdata.com` resolves to a
real address. An NXDOMAIN presents downstream as an opaque connection failure that looks
exactly like a bad API key.

### B.1 Approve the handle roster

The form at `GET /discovery/handles` offers exactly five platform keys: `youtube`,
`bluesky`, `instagram`, `linkedin-profile`, `linkedin-company`. **Register at least one of
each of the three new ones** — the two LinkedIn modes are genuinely different adapters
(`discover_by=profile_url` vs `company_url`, with `author_filter=True` only on profile,
added because a live 2026-08-07 query returned a post authored by someone else). Testing
one mode tests half the PR.

**Handle format is the URL slug, not the URL** — `PROFILE.url_template` is
`https://www.linkedin.com/in/{slug}` and the adapter does `handle.lstrip("@").strip()`.
Enter `danielpink`, not the full URL.

**Candidates for your approval** — chosen to extend your existing 7-channel YouTube guru
roster onto the two new platforms, plus the youth-sports voices your corpus already cites.
*Exact slugs must be confirmed at registration; the `validate_handle` run is the
verification mechanism.*

| Platform | Target | Why |
|---|---|---|
| `instagram` | Becky Kennedy / Good Inside | Already on your YouTube roster (`@goodinside`); IG is her primary short-form surface |
| `instagram` | Changing the Game Project (John O'Sullivan) | Directly on-brand for RaisingGoodSports; not yet in any corpus |
| `instagram` | Aspen Institute Project Play | Cited as a research source in the R8 grounding brief — following the primary source |
| `linkedin-profile` | Daniel Pink | On your YouTube roster (`@danielpintv`); LinkedIn is where his long-form thinking lands |
| `linkedin-profile` | Nir Eyal | On your roster (`@nirandfar`); tests profile mode + author_filter |
| `linkedin-company` | Positive Coaching Alliance | Youth-sports org, company mode, distinct content shape from a personal profile |

Swap or add freely — the point is that these are people you'd actually read.

**Pass:** for each registered handle, `GET /discovery/handles/{id}/status` shows a completed
validation, **and** `output/brand-intel/instagram/<slug>/`,
`output/brand-intel/linkedin-profile/<slug>/`, `output/brand-intel/linkedin-company/<slug>/`
each contain ≥1 `.md`. None of those three directories exist today — their first appearance
*is* the proof.

### B.2 Manual run and dedup check

`POST /discovery/run-now`. **Pass:** each new handle produced ≤ `MAX_ITEMS_PER_RUN = 10`
records (the server-side `limit_per_input` is the primary cost control — confirm it held),
files are named `<item_id>.md`, and a second immediate run produces **zero** new files.

### B.3 Confirm backfill is correctly refused

`discovery_engine.py:29` sets `BACKFILL_SUPPORTED_PLATFORMS = {"youtube", "bluesky"}`.
`POST /discovery/run-now-backfill` will skip every IG/LI handle. **Pass:** the warning
`! backfill not supported for platform '…'` appears. Assert the message and move on — this
is correct behaviour, not a gap to fix.

**Cost note:** Bright Data bills per record. 6 handles × 10 records × 2 runs (validate +
run-now) is your exposure. Confirm the record count matches the file count —
`enumerate_newest_first` caches per handle per run specifically so `download_item` doesn't
double-pay.

---

## Track C — New Short, idea to finished video

*~6–10 hours across sessions, ~$60–120. **Gated on Track 0.2 landing.** Read Track A.6 first.*

Topic: `rgs-briefs/2026-07-25-8000-a-year-club-soccer-parent.md` (Adler × S5, archetype A2).
Create a fresh project in the app; do not reuse an existing run.

### C.1 Stages 1–3: grounding → ideation → scripting

Free, unblocked. **Gate D fires on scripting.**

Expect **D6 to fail the first turn** — it requires a filled-in `Gate E:` line, and Gate E is
a separate fresh-Opus critic round-trip the skill must actually run. No script artifact in
the repo has one today.

**Pass per turn:** read `meta["gates"]` in the artifact frontmatter and require
`{"name": "gate_d_script_language", "status": "pass"}`.

**Do not use `override_reason` on D6.** Overriding the honesty lock defeats the entire point
of #15, and finding out whether the gate holds is why you're running this.

Cross-check on the CLI:
```bash
cd C:/Projects/ContentStudio && python scripts/lint_script_language.py runs/<run>/02-scripting/artifact.v1.md
```

### C.2 Stage 4: styleboard

Brand-new skill, **no registered gate** — `approval_service` will not block it, so a bad
world lock sails through and only surfaces as a wall of C8/C18 at the visual stage.

**Manual pass criteria:** the artifact carries a `WORLD LOCK` block with `register_a_sport`
populated, plus one `slot_*` line per slot the sheet will reference, each valued as a
kebab-case Style Library label (e.g. `rgs-present-soccer-a`) — **never** a raw code or an
invented placeholder. `VALID_SLOT_VALUE_RE` in `check_slots` rejects the latter. Also
confirm `BINDINGS` and `DISCOVERY REQUESTS` blocks exist per
[`styleboard-format.md`](.claude/skills/shorts-styleboard/references/styleboard-format.md).

**This is where Track A.6 pays off** — the world lock should not commit to anything the
renderer can't deliver.

### C.3 Stage 5–7: voiceover, visual, music

`voiceover` and `visual` both depend only on scripting (+ styleboard for visual), so they
run in parallel. `music` depends on `[scripting, voiceover]`.

**Visual — the Gate C proof.** Once 0.2 has landed, cross-check the app against the CLI:
```bash
cd C:/Projects/ContentStudio && python scripts/lint_prompt_sheet.py runs/<run>/03-visual/artifact.v1.md --styleboard runs/<run>/02b-styleboard/artifact.v1.md
```
**Pass:** `Gate C: PASS — N shots, 0 findings` **and** the app-recorded `meta["gates"]`
agrees. A disagreement between the two is itself the finding.

**Positive regression test — run this deliberately:**
```bash
cd C:/Projects/ContentStudio && python scripts/lint_prompt_sheet.py rgs-briefs/2026-08-05-do-less-sold-as-win-more-visual-prompts-v2.md
```
**Pass = it FAILS**, with 14× C16 on `SREF-RGS-A-DL01`/`SREF-RGS-B-01` plus C19 on the
missing cover decision. *(Already verified: `Gate C: FAIL — 15 shots, 15 finding(s)`.)* C16
exists precisely to reject those placeholders. This is the new gates working.

**Voiceover and music** are `specialist_mode: manual` — the stage emits a brief, and you
execute it by hand in the ElevenLabs UI. No `ELEVENLABS_API_KEY` is needed unless you script
the API.

**Relief valve:** `assembly` depends on `[voiceover, visual]`, **not music**. If Track C runs
long, music-brief can be left unapproved without blocking anything downstream.

### C.4 Generate the real assets (~$60–120)

- **Midjourney:** resolve every `{style:…}` / `{char:…}` slot against the styleboard's
  `BINDINGS` before pasting — [`shorts-assembly/SKILL.md:36`](.claude/skills/shorts-assembly/SKILL.md:36)
  documents this as manual until a render console exists. **This is the only step that tests
  whether the #17 slot system produces a coherent *look*** — no linter can measure that.
  Judge it explicitly: do Register A and Register B read as two distinct worlds?
- **ElevenLabs:** execute the voiceover brief and the music brief in the web UI.

### C.5 Stages 8–9: assembly → repurpose, then render

`assembly` emits an edit plan, not a render-spec — same gap as Track A. Hand-author the
second `render-spec.json`, this time with the Track A.6 boundary doc in hand, and render:

```bash
cd C:/Projects/ContentStudio/stitcher && C:/Python314/python.exe -m stitcher render <new-slug> --mode final
```

**Definition of done for the whole plan:** two files exist —
`renders/do-less-sold-as-win-more/out/…_v01_1080x1920.mp4` and
`renders/<new-slug>/out/…_v01_1080x1920.mp4` — both promoted by a QA `pass`, plus
`repurpose` post copy for the new Short.

**Note whether the second render-spec took materially less time than the first.** If it
didn't, the adapter is worth building before Short #3.

---

## Verification summary

| Track | Command | Pass |
|---|---|---|
| 0.1 | start uvicorn, query `stages` | 4 styleboard rows, no skip message |
| 0.2 | `pipeline-app` pytest | new gate test green; `passing_sheet` → 0 blocking findings |
| 0.3 | 3× pytest | all green; note any e2e skip |
| A.4 | `python -m stitcher render … --mode final` | exit 0, `_v01_` MP4 in `out/` |
| A.5 | re-run identical | `no changes; … is current` |
| B.1 | `GET /discovery/handles/{id}/status` | 3 new platform dirs appear under `output/brand-intel/` |
| B.2 | second `run-now` | zero new files |
| B.3 | `run-now-backfill` | `! backfill not supported` warning |
| C.1 | `meta["gates"]` on scripting | `gate_d_script_language: pass`, no override |
| C.3 | CLI Gate C + app gates | both PASS and agree |
| C.3 | legacy do-less sheet | **FAILS** on 14× C16 + C19 |
| C.5 | stitcher final render | exit 0, `_v01_` MP4 |

---

## Predicted findings (ranked)

1. **App-mode Gate C can't load the styleboard** — blocks every new Short at the visual
   stage; also drops C19/cover lint so app-Gate-C ≠ CLI-Gate-C. *Highest severity, smallest
   fix. Fixed in Track 0.2.*
2. **No `shorts-assembly` → `render-spec.json` adapter.** Two hand-authored specs by the end
   of this plan; Track A.6 is its requirements doc.
3. **The stitcher cannot do three things the edit plans routinely specify** — colour
   grading, any blur, burned-in captions. Not bugs; an unwritten scope boundary the assembly
   skill has no knowledge of.
4. **No per-shot crop in the render-spec**, so a `[G]` grounding constraint (the Ellen Key
   crop) is enforceable only by pre-modifying an asset. Nowhere to record that it was
   required, and QA cannot check it.
5. **`styleboard` has no registered gate** — a defective world lock is invisible until it
   detonates as a wall of C8/C18 downstream.
6. **Pure `drift` motion silently renders static.** No error, no warning, no QA signal —
   exactly the "subtly wrong video" class the stitcher design says it exists to prevent.
7. **Operational:** two Python environments with divergent deps (`.venv` has no Pillow),
   `--root` CWD-relative by default, `MAX_PATH_LEN=255` unchecked by `validate`,
   `CACHE_EPOCH` hand-bumped, Montserrat not installed.
8. **Bright Data has no in-app diagnostic for the VPN conflict** — a NetShield NXDOMAIN
   presents as an opaque request failure. A `/doctor` check would be cheap.

---

## Suggested order

**Session 1** — Track 0 complete (backfill, Gate C fix + test, baseline suites). Then B.0–B.3
while the VPN is off.
**Session 2** — Track A end to end, ending with the A.6 boundary doc and a real MP4.
**Session 3** — Track C stages 1–4 (through styleboard), gates green.
**Session 4** — Track C asset generation and final render.
