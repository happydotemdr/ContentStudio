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

Four new tables added to `pipeline-app/pipeline_app/schema.sql`, alongside the existing
`projects`/`stages`/`turns` tables, using the same shared-connection/WAL-mode SQLite setup.

```sql
CREATE TABLE IF NOT EXISTS handles (
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

CREATE TABLE IF NOT EXISTS discovery_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,            -- e.g. 2026-07-30T06-00-00-0500
    trigger TEXT NOT NULL,                  -- 'scheduled' | 'manual'
                                             -- (mode carries the backfill/validate_handle distinction)
    mode TEXT NOT NULL,                     -- 'incremental' | 'backfill' | 'validate_handle'
    backfill_start TEXT,                    -- ISO date, backfill mode only
    backfill_end TEXT,
    status TEXT NOT NULL,                   -- 'running' | 'locked' | 'completed'
                                             -- | 'completed_with_errors' | 'failed' | 'abandoned'
    heartbeat_at TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    md_path TEXT                            -- NULL until the run reaches a terminal status
);

-- Enforces the single-flight lock without a check-then-insert race: a second
-- concurrent INSERT with status='running' fails with IntegrityError, which
-- IS the "locked" rejection (see "Concurrency" below). validate_handle runs
-- are exempt from this lock entirely (see "Concurrency" below) and so never
-- attempt this insert.
CREATE UNIQUE INDEX IF NOT EXISTS ux_discovery_single_running
    ON discovery_runs(status) WHERE status = 'running';

CREATE TABLE IF NOT EXISTS discovery_run_handles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES discovery_runs(id),
    handle_id INTEGER NOT NULL REFERENCES handles(id),
    status TEXT NOT NULL,                   -- 'ok' | 'no_new_content' | 'handle_not_found' | 'error'
    items_downloaded INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

-- Singleton settings row (id is always 1) backing the UI's schedule form.
CREATE TABLE IF NOT EXISTS discovery_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    frequency TEXT NOT NULL DEFAULT 'daily',   -- 'daily' only for now (see Non-goals)
    time_of_day TEXT NOT NULL DEFAULT '06:00', -- HH:MM, local to `timezone`
    timezone TEXT NOT NULL DEFAULT 'America/Chicago',
    last_scheduled_run_date TEXT               -- ISO date (not datetime) of the last date a
                                                -- scheduled run actually fired; used for the
                                                -- once-per-day due-check, see "Scheduling"
);
INSERT OR IGNORE INTO discovery_settings (id) VALUES (1);
```

`db.py`'s connection setup gains `PRAGMA busy_timeout=5000` (currently unset), since this feature
introduces a second SQLite *writer process* (the cron subprocess) for the first time — WAL mode
alone only removes reader/writer blocking, not writer/writer contention between the app and a
running job.

### One-time migration

A one-off script seeds `handles` from `manifests/brand_sources.json`'s 16 existing entries (15
YouTube + 1 Bluesky): `platform`/`handle`/`display_name`/`keyword_filter` map directly; `cohort` is
derived from each entry's freeform `note` text — `"guru channel"` → `guru`; `"shorts specialist"`
(JennyHoyos, ThatNateBlack) → `shorts-specialist`; `"Midjourney..."` (FutureTechPilot, WadeMcMaster,
TaoPrompts, tokenizedai) → `midjourney-source`; the algorithm/packaging-teaching notes on vidIQ,
nicknimmin, and robertoblake also map to `guru` (they're creator-education channels like the other
guru entries, not shorts exemplars or MJ sources); bigthink/adamgrant (the one entry explicitly
flagged as unrelated general-interest content in the manifest's own comment) → `general-interest`.
`status` is seeded as `validated` (these handles already have real downloaded content on disk) with
`included=1`. The migration is idempotent — it upserts on `UNIQUE(platform, handle)`, so re-running
it after manually editing a cohort doesn't clobber the edit. It only reads the JSON file and writes
new DB rows — it never touches `output/brand-intel/`.

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
  later needs no migration). Submitting inserts the row as `status='pending'`, then immediately
  starts a `validate_handle` job which flips it to `status='validating'` the moment the job
  actually begins running; the roster page shows a "validating…" state and polls until the row
  reaches `validated` or `invalid`. This avoids blocking the HTTP request for the 30–90 seconds a
  real `yt-dlp` enumerate + download can take.

## Handle validation (`mode='validate_handle'`)

Runs through the same subprocess job machinery as any other discovery run (one row in
`discovery_runs`, `trigger='manual'`, `mode='validate_handle'`), but is **exempt from the
single-flight lock** (see "Concurrency" below) — it only touches its own handle's directory, so it
can run concurrently with a full roster run instead of getting rejected as `locked` and leaving the
new handle stuck in `pending` for the duration of a multi-minute cron job:

1. Set `handles.status='validating'`.
2. Enumerate the handle via the shared extraction module (see below). Zero results (channel not
   found / handle typo'd / deleted) → `handles.status='invalid'` **and `included` is set to 0**,
   so an invalid handle is automatically excluded from every future run rather than erroring
   forever; error surfaced on the roster page, and the user can flip `included` back on after
   fixing the handle string. (A handle that was previously `validated` and only goes bad later —
   e.g. the creator deletes the channel — is a different, later-lifecycle case: it stays
   `included` and keeps surfacing `handle_not_found` on each run, which is the intended signal for
   the user to notice and act on, not something auto-suppressed.)
3. On success, download that handle's single most recent post through the real per-item extraction
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
- Enumerate the handle's current post IDs, **newest-first** (this is yt-dlp's natural
  `--flat-playlist` order for YouTube; Bluesky's `getAuthorFeed` is also reverse-chronological by
  default). This enumeration call does **not** return publish dates for YouTube (`--flat-playlist`
  intentionally avoids the per-video metadata fetch that would make enumeration slow) — so the
  stop condition below is deliberately ID/disk-based, not date-based, for existing handles.
- Each platform adapter exposes an `on_disk_ids(handle) -> set[str]` function rather than a single
  shared filename glob, since the two platforms' filename schemes differ: YouTube is
  `<videoId>__<slug>.md` (glob `<videoId>__*`, not a full-path equality check — this also fixes a
  latent bug in the current script, where a creator retitling a video would change the filename
  and cause a silent re-download); Bluesky is `<rkey>.md` directly (no separator — a full basename
  match on `<rkey>.md`, not the YouTube-style glob). `keyword_filter`, where set (today only used
  to reduce `@bigthink` to Adam Grant videos), is applied to enumerated titles **before** either
  the on-disk check or the lookback/early-stop walk below — matching how the current script
  filters — so a filtered-out video is never evaluated at all, not perpetually retried.
- Walk the newest-first enumerated (and keyword-filtered) ID list and stop once a stop condition is
  hit, downloading each ID that isn't already on disk along the way:
  - **Existing handle** (`on_disk_ids(handle)` non-empty): stop after 3 consecutive IDs that are
    already on disk (a small grace window, not 1, to tolerate the rare case of an out-of-order
    publish). This needs no date fetching at all for the stop decision — only a cheap disk-set
    lookup per enumerated ID — and is naturally bounded: a handle with no new content stops after
    3 items, a handle with 40 new uploads since the last run downloads all 40 and then stops.
  - **New handle** (`on_disk_ids(handle)` empty — brand new to the roster): there's nothing on
    disk yet to early-stop against, so the walk instead downloads each video in order (the full
    per-video fetch used for download already reveals its publish date) and stops the first time
    it hits one published more than 3 months ago. That video is discarded, not saved.
- This bounds every run's work by "how much is actually new" rather than "how large the channel's
  full back-catalogue is" — critical for the first incremental run after migration, since the
  on-disk corpus today only reflects a recent-window pull, not full history; without an early-stop
  a naive ID-set diff against the *entire* channel history would try to download hundreds of older
  videos per channel on day one.
- Robust to late-surfacing content (e.g. an unlisted video going public days after upload) within
  the 3-consecutive-hit grace window; content that surfaces even later than that is caught by an
  explicit backfill run instead (see "Run Now / backfill" below), not silently missed forever the
  way a plain date watermark would.
- After processing, `handles.last_seen_published_at` is updated to the newest publish date seen
  among items downloaded (or left unchanged if nothing new was downloaded) — display metadata only
  (shown on the roster page), never read by the dedup logic itself.

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
  `mode='backfill'`, `backfill_start`/`backfill_end` recorded. Backfill is the one mode that
  legitimately needs full-history enumeration and a per-candidate date check (there's no on-disk
  boundary to early-stop against — the whole point is checking a specific past window regardless
  of what's already been pulled): for each included handle, enumerate the full ID list, fetch
  metadata for candidates whose date could fall in `[start, end]`, and download only those that do
  **and** aren't already in `on_disk_ids(handle)` — same per-platform dedup check as incremental
  mode. This is the one mode where the existing script's throttling concerns (below) matter most,
  since it isn't bounded by an early-stop.
- Bluesky's public `getAuthorFeed` has a practical pagination depth limit; a backfill range that
  reaches further back than the API will page through is reported per-handle as
  `no_new_content`/partial rather than silently claiming full coverage — the history record notes
  this rather than implying the entire requested range was checked.
- The shared engine carries over `download_brandintel.py`'s existing pacing (`--sleep` between
  downloads, YouTube's documented ~100–200 transcript-fetches/hour/IP soft limit) so the unattended
  cron path doesn't get throttled the way an unpaced burst would; the optional
  `--cookies-from-browser` escape hatch stays a manual-run-only option, not something the
  unattended cron invokes automatically.

## Concurrency and execution model

- **Execution model: subprocess**, not a thread. Both the scheduled cron and every UI-triggered
  run invoke `run_discovery_cron.py` as a child process. This keeps a multi-minute `yt-dlp` job
  from sharing `pipeline-app`'s single long-lived `app.state.conn` (which every route handler
  commits against) and means a hung/crashed extraction can't wedge the web UI.
- **Locking applies to `incremental` and `backfill` runs only.** `validate_handle` jobs (from
  handle validation, above) never attempt the `INSERT ... status='running'` lock row at all — they
  run concurrently with whatever else is in progress. This is a deliberate, accepted trade-off for
  a single-user local tool: the only real risk is validating a handle that's *also* being touched
  by a concurrent full-roster run, which is rare and, worst case, just means that one handle's
  `on_disk_ids()` check races (both processes independently conclude "not on disk yet" and each
  download the same new item once — no duplicate is ever kept, since both write to the same
  deterministic filename and the second write simply overwrites the first with identical content).
- **Locking (incremental/backfill)**: the `ux_discovery_single_running` partial unique index (see
  Data model) is the actual lock — a run starts by attempting
  `INSERT INTO discovery_runs (..., status='running', ...)`; if that insert fails with
  `IntegrityError`, a run is already in progress, and this attempt immediately inserts its own row
  with `status='locked'` instead. No read-then-write race window.
- **Heartbeat**: the running process runs a dedicated background thread (separate from the main
  per-handle processing loop, which blocks on sequential `subprocess.run` yt-dlp calls and could
  easily go 30+ seconds without returning control) that updates `heartbeat_at` on a fixed interval
  (e.g. every 30s) for the duration of the run.
- **Stale-lock recovery**: before any new run attempts its `INSERT`, it first checks for a
  `running` row whose `heartbeat_at` is older than a threshold (e.g. 10 minutes), and if found,
  flips that row to `abandoned` and writes its paired `.md` record before proceeding — so a killed
  process or reboot doesn't permanently wedge every future run behind a phantom lock. Staleness is
  judged purely by heartbeat recency, not by checking whether the recorded PID is still alive:
  Windows can reuse a PID quickly enough that a liveness check could report a genuinely-dead run as
  alive. This does mean a run that's legitimately still working past the staleness threshold (e.g.
  a very slow network) can get reclaimed and have a second run start concurrently — an accepted
  risk for a local single-user tool given the heartbeat interval is 20x shorter than the staleness
  threshold, making a false reclaim of a healthy run very unlikely in practice.

## Scheduling (Windows Task Scheduler)

- **Setup (one-time)**: a small `schtasks /Create` call registers a single per-user task
  (`ContentStudio-Discovery`, no admin rights needed) with a fixed **15-minute** trigger, pointed
  at `run_discovery_cron.py`. This is shown to the user before it's run the first time, since it's
  the first thing in this repo that touches OS state outside the filesystem.
- **No further `schtasks` calls from the running app.** The UI's schedule form writes directly to
  the `discovery_settings` singleton row (frequency + `time_of_day` + `timezone`, defaulting to
  daily / `06:00` / `America/Chicago`). On each 15-minute wake, `run_discovery_cron.py` reads that
  row and applies a simple once-per-day due-check, entirely in terms of local wall-clock dates —
  not elapsed-seconds arithmetic, so it isn't sensitive to DST transitions: due if
  `today's date in <timezone> != last_scheduled_run_date` **and** the current local time is at or
  past `time_of_day`. If due, it proceeds to attempt the run (and, on success, sets
  `last_scheduled_run_date` to today's date so it doesn't fire again today). If not due, it exits
  immediately without attempting the lock or touching `discovery_runs` at all.
  - **Catch-up semantics**: if the machine is off at 6am and boots at 2pm, the next 15-minute wake
    after boot sees `last_scheduled_run_date` is still yesterday (or earlier) and the current time
    is past `06:00`, so it runs once, immediately, on wake — not repeatedly, and not skipped.
    Multiple missed days collapse to exactly one catch-up run (the date comparison only cares
    whether *today's* run has happened, not how many days were missed).
  - A manual "Run Now" does **not** update `last_scheduled_run_date` — only a `trigger='scheduled'`
    run does, so an ad hoc manual pull earlier in the day doesn't suppress that day's real
    scheduled run.
  - This satisfies "configurable frequency/time via the UI" without the app ever shelling out to
    `schtasks` from an HTTP request handler, and without any drift between what the UI displays and
    what's actually registered in Task Scheduler (there is exactly one registered trigger, and it
    never changes).
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
trigger: scheduled          # scheduled | manual
mode: incremental           # incremental | backfill | validate_handle
status: completed_with_errors
started_at: 2026-07-30T06:00:00-05:00
finished_at: 2026-07-30T06:04:12-05:00
backfill_range: null        # {start, end} when mode=backfill
handles_processed: 16
items_downloaded: 7
handles_ok: 14
handles_no_new_content: 1
handles_not_found: 1
handles_errored: 0
---

## Summary

Pulled 7 new items across 14 handles with new content. 1 handle not found.

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
- No code path in the discovery engine calls `unlink`/`rmtree`/`shutil.move` against any
  **persisted content** under `output/brand-intel/` — i.e. anything outside the existing
  `output/brand-intel/youtube/_tmp/` scratch directory, which the current script already uses for
  transient per-video working files (`.vtt`, `.info.json`) and cleans up as it goes; that scratch
  cleanup is unaffected by this invariant. Persisted downloads write to a temp path and rename into
  place, so an interrupted download can't leave (or overwrite with) a truncated file at the real
  destination.
- The discovery engine does **not** read or write `output/brand-intel/_manifest.csv`. That file is
  specific to `download_brandintel.py`'s own manual-run bookkeeping (and today gets overwritten
  with only the current invocation's rows on every run) — reusing that behavior from an unattended
  incremental cron job would truncate it down to a handful of rows on the very first scheduled run.
  The new engine's own history (`discovery_runs`/`discovery_run_handles` plus the paired `.md`
  records) is the complete audit trail for anything the cron/UI path downloads; `_manifest.csv`
  remains solely an artifact of manual `download_brandintel.py` invocations.

## Testing

Following `pipeline-app/tests/`'s existing conventions (pytest, `tmp_path` + a fresh SQLite db per
test, no real network calls — the current suite already isolates CLI/subprocess calls the same
way `test_cli_runner.py` does for the pipeline's Claude CLI invocations):

- `test_discovery_service.py` — the newest-first early-stop walk (3-consecutive-on-disk stop for
  existing handles; 3-month-old stop for new handles), per-platform `on_disk_ids()` matching
  (YouTube `<id>__*` glob vs. Bluesky exact `<rkey>.md` match, including the retitled-video case),
  `keyword_filter` applied before the walk, per-handle error isolation, `last_seen_published_at`
  display-metadata update, against mocked enumerate/download functions (no real `yt-dlp`/Bluesky
  calls).
- `test_routes_discovery.py` — roster CRUD, include/exclude toggle, auto-exclude on failed
  validation, validation-job kickoff and polling (including while an incremental run holds the
  lock), run-now/backfill form handling, schedule form writing to `discovery_settings`, history
  page rendering.
- Additions to `test_db.py` for the four new tables, including a test that a second concurrent
  `INSERT ... status='running'` raises `IntegrityError` (locking), that a `validate_handle` insert
  never attempts that lock, and that a stale `heartbeat_at` is correctly reclaimed as `abandoned`.
- A test for the scheduler due-check: same-day no-op, next-day-after-time-of-day fires once,
  multi-day-missed catch-up fires exactly once (not once per missed day), manual runs don't update
  `last_scheduled_run_date`.
- A test asserting no discovery code path invokes a delete/move filesystem call against any
  persisted path under `output/brand-intel/` (excluding `_tmp/`), and that `_manifest.csv` is never
  written by the discovery engine.
