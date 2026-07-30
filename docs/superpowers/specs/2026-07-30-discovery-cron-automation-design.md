# Discovery Cron Automation — Design

**Status:** Approved, pending final user sign-off on this written spec.
**Date:** 2026-07-30

## Context

Today, pulling new content from ContentStudio's ~15 YouTube/Bluesky brand-intel handles is a
manual, all-or-nothing operation: `python download_brandintel.py` reads `manifests/brand_sources.json`
(a flat, hand-edited JSON list) and downloads everything it finds, deduplicating only by checking
whether a destination filename already exists. There's no way to include/exclude a handle for
future runs without editing JSON by hand, no incremental "just the new stuff" mode, no history of
what ran and when, and no way to schedule it — it only runs when someone remembers to run it.

This spec adds:

1. A handle roster page in `pipeline-app` (include/exclude, cohort grouping, add-with-validation).
2. A shared extraction engine (used by both a CLI cron entry point and the UI) that pulls only
   content not already on disk, using a 3-month lookback for brand-new handles and an
   ID-set-difference diff for existing ones — never re-downloading anything.
3. A Windows Task Scheduler–backed daily cron (default: 6am `America/Chicago`), configurable from
   the UI, plus a "Run Now" button and a date-range "Run Now (backfill)" mode.
4. A job history page showing every run (running/locked/completed/completed_with_errors/failed/
   abandoned), with a paired Markdown record per run.

It does **not** touch the `thinkers` or `youth-sports` corpora, which have a fundamentally
different shape (static texts / a sibling-repo copy, not "new posts since last time" discovery)
and keep using their existing standalone scripts untouched.

## Goals

1. Manage which handles are pulled by future cron/manual runs from a dedicated page, grouped by a
   fixed cohort taxonomy (`guru`, `shorts-specialist`, `midjourney-source`, `general-interest`),
   without ever touching already-downloaded files.
2. Validate a newly added handle end-to-end (the real extraction pipeline can find it and pull its
   most recent post) before it's trusted by any future automated run.
3. Guarantee no duplicate downloads, ever — dedup must survive retitled videos, a fresh DB, and
   partial/interrupted runs.
4. Let the schedule (frequency/time) be configured from the UI; support both a normal daily
   incremental pull and an on-demand backfill over an explicit date range.
5. Make every run fully auditable: a live status while running, a permanent history entry
   afterward, and a paired `.md` record with frontmatter — without ever storing extracted
   transcript/description text in that record.
6. Never let one bad handle (renamed, deleted, no new content) abort the rest of a run.

## Non-goals

- No changes to `thinkers`/`youth-sports` corpora or their scripts.
- No cloud/remote scheduling — this is a local, single-user, single-machine tool (matches the
  rest of ContentStudio: "Local only. No deploying, no external hosting, no cloud sync.").
- No multi-schedule support (e.g. different cadences per cohort) — one global schedule, "Run Now"
  covers ad hoc needs.
- No RSS support in this iteration — `manifests/brand_sources.json`'s RSS section is currently
  empty (no feeds seeded); the roster/engine can be extended to RSS later without a redesign, but
  building it now against zero real feeds isn't worth the surface area.
- `download_brandintel.py` and `manifests/brand_sources.json` are not deleted or rewritten to be
  DB-backed — they remain available for manual/ad hoc use exactly as today, now decoupled from the
  cron/UI path (see "Relationship to the existing manual script" below).

## Data model

Three new tables added to `pipeline-app/pipeline_app/schema.sql`, alongside the existing
`projects`/`stages`/`turns` tables, using the same shared-connection/WAL-mode SQLite setup.

```sql
CREATE TABLE handles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,                 -- 'youtube' | 'bluesky'
    handle TEXT NOT NULL,
    display_name TEXT,
    cohort TEXT NOT NULL,                   -- freeform, UI offers: guru | shorts-specialist
                                             -- | midjourney-source | general-interest
    keyword_filter TEXT,
    included INTEGER NOT NULL DEFAULT 1,    -- 0 = excluded from future runs, files untouched
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending' | 'validating' | 'validated' | 'invalid'
    added_at TEXT NOT NULL,
    validated_at TEXT,
    last_seen_published_at TEXT,            -- display metadata only, NOT the dedup mechanism
    UNIQUE(platform, handle)
);

CREATE TABLE discovery_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,            -- e.g. 2026-07-30T06-00-00-0500
    trigger TEXT NOT NULL,                  -- 'scheduled' | 'manual' | 'backfill'
    mode TEXT NOT NULL,                     -- 'incremental' | 'backfill' | 'validate_handle'
    backfill_start TEXT,                    -- ISO date, backfill mode only
    backfill_end TEXT,
    status TEXT NOT NULL,                   -- 'running' | 'locked' | 'completed'
                                             -- | 'completed_with_errors' | 'failed' | 'abandoned'
    pid INTEGER,
    heartbeat_at TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    md_path TEXT NOT NULL
);

-- Enforces the single-flight lock without a check-then-insert race: a second
-- concurrent INSERT with status='running' fails with IntegrityError, which
-- IS the "locked" rejection (see "Concurrency" below).
CREATE UNIQUE INDEX ux_discovery_single_running
    ON discovery_runs(status) WHERE status = 'running';

CREATE TABLE discovery_run_handles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES discovery_runs(id),
    handle_id INTEGER NOT NULL REFERENCES handles(id),
    status TEXT NOT NULL,                   -- 'ok' | 'no_new_content' | 'handle_not_found' | 'error'
    items_downloaded INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);
```

`db.py`'s connection setup gains `PRAGMA busy_timeout=5000` (currently unset), since this feature
introduces a second SQLite *writer process* (the cron subprocess) for the first time — WAL mode
alone only removes reader/writer blocking, not writer/writer contention between the app and a
running job.

### One-time migration

A one-off script seeds `handles` from `manifests/brand_sources.json`'s 15 existing youtube/bluesky
entries: `platform`/`handle`/`display_name`/`keyword_filter` map directly; `cohort` is derived from
each entry's freeform `note` text (`"guru channel"` → `guru`, `"shorts specialist"` →
`shorts-specialist`, `"Midjourney..."` → `midjourney-source`, ambiguous entries like
bigthink/adamgrant → `general-interest`); `status` is seeded as `validated` (these handles already
have real downloaded content on disk) with `included=1`. This migration only reads the JSON file
and writes new DB rows — it never touches `output/brand-intel/`.

### Relationship to the existing manual script

`manifests/brand_sources.json` and `download_brandintel.py` are **not** deleted, rewritten, or made
DB-backed. After migration, the JSON file is simply no longer the operative roster for cron/UI
purposes — `download_brandintel.py` remains exactly as it is today for manual, ad hoc pulls (e.g.
re-running the full back-catalogue, or one-off debugging), reading the JSON file as it always has.
The two paths (JSON-driven manual script vs. DB-driven cron/UI engine) intentionally diverge from
migration day forward; there is no dual-write or reconciliation between them.

## Handle roster page (`pipeline-app`, `/discovery/handles`)

A new page reachable from the existing nav sidebar, following `project_list.html`'s conventions.

- **Table**, filterable/grouped by cohort, columns: platform, handle, display name, cohort,
  status, included toggle, last-seen date.
- **Include/exclude toggle** — instant, no validation re-run. Excluding a handle only removes it
  from future run handle-selection; it never touches files already on disk (goal 1 / requirement 2).
- **Add handle** form: platform, handle string, display name, cohort (free-text field with the
  four values above offered as suggestions — no DB `CHECK` constraint, so adding a fifth cohort
  later needs no migration). Submitting creates a `pending` row and starts a `validate_handle`
  job (see below); the row shows a "validating…" state and the page polls until it flips to
  `validated` or `invalid`. This avoids blocking the HTTP request for the 30–90 seconds a real
  `yt-dlp` enumerate + download can take.

## Handle validation (`mode='validate_handle'`)

Runs through the same subprocess job machinery as any other discovery run (one row in
`discovery_runs`, `trigger='manual'`, `mode='validate_handle'`):

1. Enumerate the handle via the shared extraction module (see below). Zero results (channel not
   found / handle typo'd / deleted) → `handles.status='invalid'`, `included` stays whatever it
   was set to (default stays included=1, but a permanently-invalid handle simply never finds
   content in any future run — no separate suppression needed), error surfaced on the roster page.
2. On success, download that handle's single most recent post through the real per-item extraction
   path — the exact code path a normal run uses — so the file lands in `output/brand-intel/...`
   exactly as it would from any other run. `handles.status='validated'`, `last_seen_published_at`
   set from that item, `validated_at` stamped.

Because that first post is now genuinely on disk, the very next incremental run's ID-set diff
correctly sees it as already-downloaded and won't re-pull it.

## Extraction engine (shared module)

Refactored out of `download_brandintel.py`'s per-platform enumerate/download functions into an
importable module (e.g. `pipeline-app/pipeline_app/discovery_service.py`) used by both:

- `run_discovery_cron.py` — the standalone entry script Task Scheduler invokes.
- The UI's "Run Now" / "Run Now (backfill)" / handle-validation actions, invoked as a subprocess
  (not a thread — see "Concurrency and execution model" below).

**Per-handle dedup and incremental logic:**

- Skip any handle with `included=0`.
- Enumerate the handle's current post IDs (YouTube video IDs via `yt-dlp -J --flat-playlist`;
  Bluesky post rkeys via `getAuthorFeed`). This enumeration call does **not** return publish
  dates for YouTube (`--flat-playlist` intentionally avoids the per-video metadata fetch that
  would make enumeration slow) — so dedup cannot be date-based.
- Compute **which enumerated IDs are not already on disk** for that handle, matching by ID prefix
  on the existing `<id>__<slug>.md` filename pattern (glob `<id>__*`, not a full-path equality
  check — this also fixes a latent bug in the current script, where a creator retitling a video
  would change the filename and cause a silent re-download).
- **New handle** (no files on disk yet for it): before diffing, filter the enumerated ID list to
  only those from the last 3 months (requires one metadata fetch per candidate ID to read its
  date — acceptable one-time cost for a brand-new handle, not paid on every subsequent run).
- **Existing handle**: no lookback filter — every enumerated ID not already on disk is downloaded,
  full stop. This is what makes the design robust to late-surfacing content (e.g. an unlisted
  video going public days after upload): a date watermark would silently miss it forever; ID-set
  difference does not.
- After processing, `handles.last_seen_published_at` is updated to the newest publish date now on
  disk for that handle — display metadata only (shown on the roster page), never read by the dedup
  logic itself.

**Resiliency (goal 6):** each handle is processed inside its own try/except. A failed enumeration
("handle not found"), a download error, or zero new IDs is recorded as
`handle_not_found`/`error`/`no_new_content` respectively in `discovery_run_handles`, and the loop
continues to the next handle. The run's own `discovery_runs.status` is:

- `completed` — every handle processed, none errored.
- `completed_with_errors` — every handle processed, at least one `error`/`handle_not_found`
  (distinct from `completed` so a run where everything failed doesn't read as a clean success).
- `failed` — the run process itself crashed (e.g. couldn't open the DB, uncaught exception outside
  the per-handle loop).
- `abandoned` — reclaimed by a later run after this one's heartbeat went stale (process killed,
  machine rebooted mid-run).

## Run Now / backfill

- **"Run Now"** button (roster or history page): starts a `trigger='manual'`,
  `mode='incremental'` run — identical logic to the scheduled job, fired on demand.
- **"Run Now (backfill)"**: a form with start/end date pickers. `trigger='manual'`,
  `mode='backfill'`, `backfill_start`/`backfill_end` recorded. For each included handle: enumerate
  IDs, fetch metadata for candidates in `[start, end]`, download only those **not already on
  disk** — same ID-based dedup as incremental mode, but ignoring `last_seen_published_at`
  entirely, since backfill exists specifically to catch gaps the normal watermark-free diff might
  still miss (e.g. a handle that was excluded for a period, or added to the roster after content
  it should have captured was already published).
- Bluesky's public `getAuthorFeed` has a practical pagination depth limit; a backfill range that
  reaches further back than the API will page through is reported per-handle as
  `no_new_content`/partial rather than silently claiming full coverage — the history record notes
  this rather than implying the entire requested range was checked.

## Concurrency and execution model

- **Execution model: subprocess**, not a thread. Both the scheduled cron and every UI-triggered
  run invoke `run_discovery_cron.py` as a child process. This keeps a multi-minute `yt-dlp` job
  from sharing `pipeline-app`'s single long-lived `app.state.conn` (which every route handler
  commits against) and means a hung/crashed extraction can't wedge the web UI.
- **Locking**: the `ux_discovery_single_running` partial unique index (see Data model) is the
  actual lock — a run starts by attempting `INSERT INTO discovery_runs (..., status='running', ...)`;
  if that insert fails with `IntegrityError`, a run is already in progress, and this attempt
  immediately inserts its own row with `status='locked'` instead. No read-then-write race window.
- **Stale-lock recovery**: the running process updates `heartbeat_at` periodically (e.g. every 30s
  while processing handles). Before any new run attempts its insert, it first checks for a
  `running` row whose `heartbeat_at` is older than a threshold (e.g. 10 minutes) or whose `pid` is
  no longer alive, and if found, flips that row to `abandoned` and writes its paired `.md` record
  before proceeding — so a killed process or reboot doesn't permanently wedge every future run
  behind a phantom lock.

## Scheduling (Windows Task Scheduler)

- **Setup (one-time)**: a small `schtasks /Create` call registers a single per-user task
  (`ContentStudio-Discovery`, no admin rights needed) with a fixed **15-minute** trigger, pointed
  at `run_discovery_cron.py`. This is shown to the user before it's run the first time, since it's
  the first thing in this repo that touches OS state outside the filesystem.
- **No further `schtasks` calls from the running app.** The UI's schedule form (frequency + time +
  timezone, defaulting to daily / 6:00 / `America/Chicago`) is saved purely to SQLite. On each
  15-minute wake, `run_discovery_cron.py` reads that config and checks whether it's actually due
  (has enough time elapsed since the last scheduled run, and are we past the configured
  time-of-day) — if not due, it exits immediately without attempting the lock or touching
  `discovery_runs` at all. This satisfies "configurable frequency/time via the UI" without the app
  ever shelling out to `schtasks` from an HTTP request handler, and without any drift between what
  the UI displays and what's actually registered in Task Scheduler (there is exactly one
  registered trigger, and it never changes).
- Timezone is explicit (`America/Chicago`), not the ambiguous "CST", so the 6am target stays
  correct across DST transitions.

## Job history page (`/discovery/runs`)

Lists `discovery_runs` newest-first: status badge (`running`/`locked`/`completed`/
`completed_with_errors`/`failed`/`abandoned`), trigger, mode, start/finish time, and a per-handle
drill-down (`discovery_run_handles`: status, items downloaded, error message). Manual refresh
(not auto-polling) — a single local user checking in on a run doesn't need a live-polling route
adding load during exactly the window write contention is highest.

## Paired Markdown record

Written to `output/discovery-runs/<run_id>.md` when a run reaches any terminal status
(`completed`/`completed_with_errors`/`failed`/`abandoned`/`locked`) — including the reclaim path
for an abandoned run, so a killed process still leaves an auditable record.

```markdown
---
run_id: 2026-07-30T06-00-00-0500
trigger: scheduled          # scheduled | manual | backfill
mode: incremental           # incremental | backfill | validate_handle
status: completed_with_errors
started_at: 2026-07-30T06:00:00-05:00
finished_at: 2026-07-30T06:04:12-05:00
backfill_range: null        # {start, end} when mode=backfill
handles_processed: 15
items_downloaded: 7
handles_ok: 13
handles_no_new_content: 1
handles_not_found: 1
handles_errored: 0
---

## Summary

Pulled 7 new items across 13 handles with new content. 1 handle not found.

## Per-handle results

- @Romayroh (youtube, guru) — ok, 2 new items, last_seen now 2026-07-28
- @ThatNateBlack (youtube, shorts-specialist) — no_new_content
- @dead-handle (youtube, guru) — handle_not_found: yt-dlp enumerate returned empty
```

Per requirement 5 (the paired record excludes extracted content), this contains only counts,
statuses, and handle identifiers — never transcript or description text, which stays exclusively
in the normal `output/brand-intel/...` files as it does today.

## Error handling

- Per-handle failures never abort a run (see Resiliency above) — this is the core requirement and
  is enforced at the loop level, not left to individual adapter functions to get right.
- A crash inside the run process itself (outside the per-handle loop — e.g. can't write to the DB
  at all) marks the run `failed` and still attempts to write the paired `.md` with whatever partial
  per-handle data was recorded before the crash.
- No code path in the discovery engine calls `unlink`/`rmtree`/`shutil.move` against
  `output/brand-intel/` — the only filesystem writes are new-file creation. Downloads write to a
  temp path and rename into place, so an interrupted download can't leave (or overwrite with) a
  truncated file at the real destination.

## Testing

Following `pipeline-app/tests/`'s existing conventions (pytest, `tmp_path` + a fresh SQLite db per
test, no real network calls — the current suite already isolates CLI/subprocess calls the same
way `test_cli_runner.py` does for the pipeline's Claude CLI invocations):

- `test_discovery_service.py` — ID-set diff logic, 3-month lookback filtering for new handles,
  per-handle error isolation, watermark display-metadata update, against mocked enumerate/download
  functions (no real `yt-dlp`/Bluesky calls).
- `test_routes_discovery.py` — roster CRUD, include/exclude toggle, validation-job kickoff and
  polling, run-now/backfill form handling, history page rendering.
- Additions to `test_db.py` for the three new tables, including a test that a second concurrent
  `INSERT ... status='running'` raises `IntegrityError` (locking) and a test that a stale
  `heartbeat_at` is correctly reclaimed as `abandoned`.
- A test asserting no discovery code path invokes a delete/move filesystem call against
  `output/brand-intel/`.
