# Freedom2BeU Document Ingest — Design Spec

**Date**: 2026-08-13
**Status**: Approved, ready for implementation planning
**Business line**: Freedom2BeU (coaching), fully partitioned from RaisingGoodSports and the eight-skill Shorts pipeline

## 1. Purpose

Convert the Freedom2BeU coaching business's document archive (Google Drive, mirrored
locally) into a validated, queryable Markdown corpus — the foundation for future
Freedom2BeU features, none of which are built in this phase. This phase is the
conversion pipeline only: no UI, no downstream app features beyond a CLI query and a
flat manifest.

**Input** (read-only, never modified): `C:\Projects\Freedom2BeU_Google_Drive\coaching\`
**Output** (full control): `C:\Projects\ContentStudio\Freedom2BeU\`
**Code**: new standalone app `C:\Projects\ContentStudio\doc-ingest-app\`, sibling to
`pipeline-app/`, decoupled from it — no shared database, no shared code.

Both `ContentStudio/Freedom2BeU/` (converted output + temp staging) and
`doc-ingest-app/doc_ingest.db` (contains extracted client-session text, so it carries
the same sensitivity as the converted files themselves) are added to `.gitignore` —
this corpus contains real client names and private coaching-session content that must
never land in git history, even locally.

## 2. Source data — what's actually in the folder

A read-only scan (2026-08-13, re-verified after an external review caught the first
pass undercounting extensionless files) found:

| Type | Count | Handling |
|---|---|---|
| `.pdf` (extension) + 6 sniffed from extensionless | 105 | firecrawl-parse; scanned/image-only ones flagged, not converted (§8) |
| `.gdoc` | 95 | Google Docs API export (§9) — **not readable as local files** |
| `.gsheet` | 5 | Google Sheets API export (§9) — **not readable as local files** |
| `.docx` | 20 | firecrawl-parse |
| `.xlsx` | 3 | firecrawl-parse |
| `.txt` / `.md` | 3 | pass-through with frontmatter added |
| `.ppt` | 1 | attempt via firecrawl-parse; flag as `unsupported_type` if rejected |
| `.png` / `.jpg` (extension) + 1 sniffed from extensionless | 18 | catalog only, no conversion, no OCR |
| `.mov` / `.mp4` (extension) + 12 sniffed from extensionless | 60 | excluded entirely (video) |
| `desktop.ini` | 61 | excluded, Windows folder metadata |

**19 files have no extension at all**, ranging from 164KB to 1.1GB. A full recursive
scan with magic-byte sniffing (not a spot-check of one subfolder, which is what the
first pass did and got wrong) resolved them as **12 video, 6 PDF, 1 PNG** — meaning
content-signature sniffing isn't just insurance against video slipping past the
exclusion rule, it's load-bearing for correctly *including* 6 real, convertible PDFs
that extension-based classification alone would silently drop entirely. The 6 PDFs
and 1 PNG are folded into the counts above; the 12 videos are folded into the video
row.

**Confirmed empirically, not assumed**: all 100 `.gdoc`/`.gsheet` files are exactly
176 bytes — a JSON pointer stub (`{"doc_id": ..., "resource_key": ..., "email":
"admin@freedom2beu.com"}`), never the document content, regardless of Google Drive
for desktop's sync mode. This is inherent to native Google Workspace file types, not
a sync setting. `resource_key` is captured alongside `doc_id` (§9) — some link-shared
items require it on Drive API calls, not just the file ID.

## 3. Architecture

```
doc-ingest-app/                    (new, sibling to pipeline-app/, own venv)
  doc_ingest.db                    (own SQLite db — no connection to pipeline.db)
  doc_ingest/
    scan.py                        walks input tree read-only; sniffs content-type by magic bytes
    drive_client.py                Google Drive/Docs/Sheets API auth + export
    gauntlet.py                    Gate 1 (content integrity) + Gate 2 (naming/placement)
    naming.py                      pure functions: sanitize, mirror path, hash-shorten
    convert.py                     dispatches to firecrawl-parse or Drive export per type
    lock.py                        applies icacls deny-write + read-only attribute
    db.py                          schema, migrations, transaction() boundary (same
                                    pattern as pipeline_app/db.py: WAL, events table,
                                    versioned apply_migrations — reimplemented here,
                                    not imported, to keep the two apps decoupled)
    query.py                       CLI: search / filter the FTS5 index
  scripts/
    setup_ingest_task.py           registers the Windows Task Scheduler job (mirrors
                                    pipeline-app/scripts/setup_discovery_task.py)
    run_ingest_cron.py             the cron entry point: reclaim -> scan -> enqueue -> drain
  tests/
    ...

ContentStudio/Freedom2BeU/         (output — gitignored)
  converted/                       final, locked .md tree, mirrors source tree
  _tmp/                            ephemeral per-job staging
```

## 4. Data flow

1. **Reclaim** — every worker heartbeats its claimed job (`heartbeat_at` updated
   periodically while it works, the same mechanism `pipeline_app.discovery_engine`
   uses so another process can tell a live run from a dead one). Any job whose
   `heartbeat_at` is older than a timeout gets reset to `pending`. This is
   deliberately **not** modeled on `preflight.reconcile_orphaned_turns` — that
   function unconditionally reclaims *every* row in a `running`-equivalent state at
   startup with no timeout and no liveness signal, which is safe there only because
   `pipeline-app` is single-process. Under this app's concurrent worker pool, a
   startup-sweep clone would reclaim jobs that are still genuinely in progress out
   from under their owning worker. A reclaim pass also removes that job's now-orphaned
   `_tmp/` staging directory, if any, before resetting the row.
2. **Scan** (read-only against the input tree) — walks the whole tree, upserts one
   `source_files` row per entry: path, size, mtime, extension, sniffed content
   signature (magic bytes — required not just to exclude video but to correctly
   classify the extensionless files that are real, convertible PDFs/images, §2), and
   a classification (`convertible` / `catalog_only` / `excluded_media` /
   `gdoc_pointer` / `blocked_unknown` / `missing`). Never opens a file for writing;
   never moves or deletes anything in the input tree. A previously-seen path that no
   longer appears in this scan is marked `missing` (§9a) rather than left as-is.
3. **Drive check** — for every `gdoc_pointer` row, parse its stub's `doc_id` (and
   `resource_key`, where present) and query the Drive API for
   `modifiedTime`/`name`/`mimeType`, batched rather than one call per document (§9).
   **Change detection for these uses the Drive API's `modifiedTime`, never the local
   stub's filesystem mtime** — the stub is a static 176 bytes and does not change
   when the real document is edited (§9, and the regression test in §13 that guards
   this specifically).
4. **Enqueue** — any `source_files` row whose local hash *differs from* (hashes have
   no ordering — this replaces an earlier "newer than" which was imprecise) or whose
   Drive `modifiedTime` is newer than its last successfully-converted version gets a
   new `pending` `conversion_jobs` row. A brand-new file gets its first job the same
   way.
5. **Claim** — a worker atomically does
   `UPDATE conversion_jobs SET status='claimed', worker_id=?, claimed_at=?, heartbeat_at=? WHERE id=? AND status='pending'`
   inside a transaction opened with `BEGIN IMMEDIATE` (not the default deferred
   transaction — a deferred `BEGIN` can hit `SQLITE_BUSY_SNAPSHOT` under concurrent
   writers in a way `busy_timeout` does not resolve). N workers loop concurrently,
   **each on its own SQLite connection** (§5) — the DB row is the sole source of
   truth, so two workers can never claim the same job.
6. **Stage** — local files are copied byte-for-byte into a per-job subdirectory of
   `Freedom2BeU/_tmp/`; Drive-native docs are exported directly into that same temp
   workspace via the Docs/Sheets export API. The input tree is never touched beyond
   the initial read.
7. **Convert** — firecrawl-parse (local files) or the Drive export (native Google
   docs) produces markdown from the staged copy.
8. **Gauntlet** — Gate 1 (content integrity) and Gate 2 (naming/placement), §8, both
   must pass before anything is written to the final location.
9. **Place, lock, index** — a filesystem write and an `icacls` subprocess call are
   both outside SQLite's transaction boundary, so this is an explicit ordered
   sequence, not one atomic operation: (a) write the `.md` and frontmatter to its
   final mirrored path; (b) commit the DB row for this conversion as `current` and
   update the FTS5 index, in one DB transaction; (c) apply `icacls` deny-write + the
   read-only attribute; (d) read back the effective permissions to confirm the lock
   actually took, and record that confirmation on the row. If the process dies
   between (a) and (d), the job is left as "written, not yet confirmed locked" rather
   than `complete` — the next wake's reclaim pass (step 1) re-attempts locking rather
   than re-converting, and re-attempting `icacls` on an already-partially-locked file
   is idempotent. On any Gate 1/Gate 2 failure before (a), the job is marked `failed`
   with a specific `failure_reason`; nothing partial ever reaches the locked output
   tree.

## 5. Concurrency model

A DB-claimed job queue, not a strict single-file-system-wide lock: multiple workers
run the claim loop concurrently (a small fixed pool, default modest — this is
I/O-bound work), each claiming exactly one job at a time via the atomic UPDATE above.
"Single file at a time, parallelization controlled by the database" means *per-file*
exclusivity (no two workers ever touch the same file), not *system-wide* serialization.

**Each worker opens its own SQLite connection** (WAL mode, `busy_timeout` set), rather
than sharing one connection across threads the way `pipeline_app.db` deliberately does.
That sharing is a documented, accepted trade in `pipeline_app/db.py` (its
`transaction()` docstring: the boundary is a property of the *connection*, and a write
from a non-owning thread on a shared connection is silently discarded if that boundary
rolls back) made for a single-process web app with a single owner-of-record. It is not
something to copy into a genuinely concurrent worker pool — one connection per worker
avoids that whole class of cross-thread commit loss outright, at the cost of needing
`BEGIN IMMEDIATE` (not a deferred transaction) on the claim UPDATE so concurrent
writers don't hit `SQLITE_BUSY_SNAPSHOT`.

## 6. Storage & naming

**Filenames**: preserve the original name and casing; sanitize only what's
mechanically required — the 9 characters Windows forbids (`< > : " / \ | ? *`),
trailing spaces/periods, and collapsed whitespace runs. Not a full slugify.

**The full original extension is always kept as part of the stem**, e.g.
`Coaching Agreement Template.docx` → `Coaching Agreement Template.docx.md`, rather
than swapping the extension outright. This isn't cosmetic: this corpus already has a
same-stem collision waiting to happen (`F2BU_12Week_Accelerator_Infographic.pdf` and
`...png` in the same folder), and stripping the source extension would make a `.pdf`
and a `.docx` with the same stem collide on write. Keeping it eliminates that whole
class of cross-type collision by construction.

**Folder structure**: mirrors the source tree 1:1 under `Freedom2BeU/converted/`.
"Where did this come from" is always answerable from the path itself.

**Versioning**: a source file's first conversion is `Name.ext.md`. A reprocess after
the source changes produces `Name.ext.v2.md`, `Name.ext.v3.md`, etc. — never an
in-place overwrite (the prior file is already locked read-only). The `conversions`
table (one-to-many off `source_files`) tracks `version_number` / `output_path` /
`status` (`current` / `superseded`) as the authoritative record, independent of what
got shortened on disk.

**Long-path mitigation**: this is the common case here, not an edge case — the source
tree already has paths past 300 characters before the output root is even added, so
this isn't a rare-fallback rule. Gate 2 (§8) computes the **full** intended
destination path (all mirrored folder segments plus filename), not just the
filename's length. If the full path would exceed a safe threshold under Windows'
~260-char default limit, the deepest offending segment(s) are shortened — filename
first, then folder segments if still needed — each replaced with a truncated form
plus an 8-char hash of the *original full source-relative path* (deterministic,
unique per source item). As defense in depth against a miscalculation, all of
`doc-ingest-app`'s own file I/O uses `\\?\`-prefixed absolute paths internally
(Windows' documented way to address paths beyond MAX_PATH without any system-wide
policy change), so a rare edge case degrades to an oddly-shortened but successfully
written file rather than a crashed run. The DB always stores the true original path
regardless of what was shortened on disk.

**Collision resolution**: if two *different* source files still resolve to the same
destination after the above (e.g. an NTFS case-insensitive match Drive itself would
treat as distinct), the second one to be processed gets an additional short hash
suffix appended before `.md`, and the collision itself is logged as an `events` row —
not silently resolved, since it means Gate 2's normal path-construction produced a
genuine ambiguity worth knowing about.

## 7. Frontmatter

Every converted file carries:

```yaml
source_path: <original path relative to coaching\, verbatim>
source_type: pdf|docx|xlsx|gdoc|gsheet|txt|md|ppt
source_hash: <sha256 of original bytes, or Drive's headRevisionId for native docs>
source_modified_at: <local mtime, or Drive modifiedTime, ISO8601>
converted_at: <ISO8601 UTC>
conversion_tool: firecrawl-parse | google-docs-export | google-sheets-export
version: <int>
status: current|superseded
business_line: freedom2beu
gauntlet_passed_at: <ISO8601 UTC>
```

Plus mechanically-derived, type-specific extras where meaningful: `page_count` (pdf),
`sheet_count` / `row_count_total` (xlsx/gsheet), `word_count` (docx/gdoc). No
domain-specific fields (client name, session category, etc.) in this phase — confirmed
out of scope; mechanical/generic fields only.

**Serialization**: frontmatter is always written via a real YAML library (e.g.
PyYAML's safe dumper), never hand-formatted string interpolation. `source_path`
values in this corpus routinely contain `'`, `&`, `:`, `#`, and non-ASCII characters
(curly apostrophes show up in real folder names here) — a library's dumper quotes/
escapes these correctly by construction; hand-formatting would not, and Gate 1's
"frontmatter parses as well-formed YAML" check exists precisely to catch it if it ever
regressed.

## 8. The gauntlet

Two independent, purely mechanical gates (no LLM evaluation) — a failure at either
records a specific `failure_reason` and blocks the write; nothing is silently dropped,
matching the "quarantine, don't discard" pattern `pipeline_app/db.py` uses in its
`_quarantine_unknown_platforms` migration (one specific precedent, not a
repo-wide convention — cited narrowly here on purpose).

**Gate 1 — Content integrity**:
- Universal: non-empty body; valid UTF-8; frontmatter parses as well-formed YAML with
  all required fields present and correctly typed; replacement-character/control-char
  ratio under a small threshold (catches botched-encoding garbling); balanced
  markdown code fences.
- A size-ratio floor versus the source applies only to DOCX/XLSX/TXT/MD, where
  source-byte-size-to-text-size is a meaningful, roughly-predictable ratio. It's
  explicitly **not** applied to PDF (compressed/binary source size vs. extracted text
  size has no stable ratio — a 4MB PDF producing 8KB of markdown is normal, not a
  truncation signal; the word-count-per-page check below is PDF's real integrity
  check) or to gdoc/gsheet (the "source" on disk is a 176-byte stub with no
  relationship to the real document's size; word-count parity against the Drive
  export is what covers these).
- PDF: page count recorded via an independent page-count read (not derived from the
  firecrawl-parse output — the check has to be independent of the thing it's
  checking); word-count-per-page checked against a floor — near-zero despite real
  page count flags `likely_scanned_no_text_layer`. **These are flagged and cataloged,
  not converted, in this phase** — OCR is explicitly out of scope for now (confirmed
  decision; a deliberate future phase, not silently skipped).
- DOCX/GDOC: word-count parity between source and output within a tolerance band,
  where the source word count comes from an independent reader (e.g. python-docx for
  local `.docx`; the Drive API's own document-length metadata, not a second export,
  for gdoc) rather than re-deriving it from firecrawl-parse's own output. Table-count
  parity if the source has tables.
- XLSX/GSheet: sheet-count and row-count parity between source workbook (read
  independently, e.g. via openpyxl) and output.
- PPT: attempted via firecrawl-parse; an error or unrecognized type fails the job as
  `unsupported_type` rather than crashing the batch.
- TXT/MD: verbatim copy under frontmatter — only the applicable universal checks
  apply (no size-ratio floor needed here either — it's an identity copy).

**Gate 2 — Naming & placement**: destination path is a pure function of source path
(never author-chosen); resolves strictly inside `Freedom2BeU/converted/` (no path
traversal); the full path (all folder segments, not just the filename) respects the
long-path/hash-shortening rule from §6 and is re-verified under the limit afterward;
a collision with a *different* source file's destination is resolved per §6's
collision rule, not left to fail indefinitely.

## 9. Google Drive/Docs API integration

**Setup** (first-time, included as setup guidance in the implementation plan — the
user performs the actual browser consent, this project cannot do it on their behalf):
create a GCP project; enable the Drive, Docs, and Sheets APIs; configure the OAuth
consent screen with **User type = Internal** (available because `admin@freedom2beu.com`
is a Google Workspace account, not a personal Gmail); create a **Desktop app** OAuth
client; download `client_secret.json`. First run opens a browser for one-time consent;
the token is cached under `doc-ingest-app/` (gitignored) and refreshed silently
thereafter.

**Internal, not External/Testing, is a correctness requirement, not a preference**: an
External app left in Testing status issues refresh tokens that expire after 7 days,
which would silently break the 30-minute cron about a week after setup. Internal apps
on a Workspace domain don't carry that restriction and don't need Google's app
verification review, since this is a single-user tool for the domain's own account.

**Discovery**: every local `.gdoc`/`.gsheet` stub's `doc_id` and `resource_key`
(parsed from its 176-byte JSON body — some link-shared items require `resource_key`
on Drive API calls, not just the file ID) are what the Drive API is queried with — the
stub is purely a pointer to *which* documents exist, never a content or timestamp
source (§4 step 3). The ~100 metadata lookups (`modifiedTime`/`name`/`mimeType`) per
cron wake are batched rather than issued as 100 sequential `files.get` calls.

**Export**:
- Google Docs → direct export to `text/markdown` via the Drive API (a real,
  supported export format); fall back to exporting `.docx` bytes and routing through
  the same firecrawl-parse + DOCX gauntlet path if markdown export is unavailable
  *or* the document exceeds Drive's **10MB export size cap** — the fallback needs to
  trigger on size, not just on the format being unsupported.
- Google Sheets → export to `.xlsx`, then reuse the existing XLSX gauntlet path
  (no separate CSV code path); same 10MB-cap fallback consideration.

Quota: ~100 documents checked every 30 minutes, batched, is trivial against Drive's
default limits; basic retry-with-backoff on 429/5xx, no special handling needed.

## 9a. Source deletion

A `source_files` row that a scan no longer finds (§4 step 2) is marked `missing`, not
deleted. Its already-converted, locked `.md` is **not** removed — the read-only
philosophy in §10 applies to files that exist, and a file disappearing from Drive
doesn't retroactively make its historical conversion wrong. It stays in the FTS index
too, but the CLI query (§12) marks `missing`-sourced results distinctly (and excludes
them by default, same as `superseded` versions) so a search doesn't surface content
whose source no longer exists without saying so.

## 10. Read-only enforcement

Two layers, applied per the write→commit→lock→verify sequence in §4 step 9:

1. **Windows ACL deny-write** (`icacls`, shelled out via `subprocess` — the same
   pattern `setup_discovery_task.py` already uses for `schtasks`): denies
   Write/WriteData/WriteAttributes/Delete **and WriteDAC/WriteOwner** on the file for
   the account, plus the read-only attribute as a second signal.

   **The WriteDAC/WriteOwner piece is load-bearing, not belt-and-suspenders**: by
   default, the account that creates a file is its owner, and an owner retains
   `WRITE_DAC` regardless of any deny ACE on the file's *contents* — meaning without
   explicitly also denying WriteDAC/WriteOwner, the same non-elevated account that
   converted the file could simply run `icacls /reset` on its own deny rule and write
   to it anyway, no elevation required. Denying those two rights as well closes that
   specific hole: changing the ACL or taking ownership at that point genuinely
   requires elevation (`SeTakeOwnershipPrivilege`), which is the honest boundary
   stated below.
2. **Claude Code `PreToolUse` hook** (`settings.json`): inspects Edit/Write/
   NotebookEdit calls, and Bash/PowerShell command text, for any path under
   `Freedom2BeU/converted/`, rejecting the call before it reaches the OS. A
   heuristic on command text for the Bash/PowerShell case (not a full parse) — a
   fast, clean rejection layered on top of the ACL, not a replacement for it. This
   hook only applies within Claude Code sessions that load this repo's
   `settings.json`; it has no effect on non-Claude-Code processes, which is exactly
   why layer 1 is the actual backstop and this is the fast-fail UX layer on top of it.

**Stated limit**: with WriteDAC/WriteOwner denied, this resists both accidental
writes *and* the account's own attempt to quietly lift its own restriction — it does
not resist someone deliberately elevating to admin and taking ownership by hand. No
filesystem permission model promises that; "no workarounds or holes" is scoped here
to Claude Code and routine, non-elevated account-level access.

Because versioning always writes a brand-new file (§6) rather than editing in place,
enforcement never needs a "temporarily unlock to rewrite" exception — locking is
one-directional. A partial/interrupted `icacls` call is handled by §4 step 9's
verify-then-record-confirmation step, not assumed to have succeeded.

## 11. Cron

New Windows Task Scheduler task `ContentStudio-DocIngest`, registered by
`doc-ingest-app/scripts/setup_ingest_task.py` (dry-run by default, `--apply` to
register — mirrors `setup_discovery_task.py` exactly). Fixed 30-minute trigger (the
user's stated floor); no additional "is it due" gating layered on top since there's no
daily-once semantic here, unlike the existing discovery cron.

Each wake runs the full data flow in §4 (reclaim → scan → Drive check → enqueue →
drain the queue with a bounded worker pool) against an explicit **run-level time
budget** — the drain loop stops claiming new jobs once the budget's elapsed, finishes
whatever it already claimed, and exits cleanly rather than running unbounded. Task
Scheduler's own default for a task created this way (`schtasks /SC MINUTE`, no
`MultipleInstances` override) is to skip a new trigger if the previous run hasn't
exited — so an over-budget run delays the next wake rather than overlapping it, and
the run-level budget exists specifically to keep that delay bounded instead of
open-ended. Each individual job also has its own timeout (config, §15) so one hung
conversion or API call can't consume the whole run's budget by itself.

## 12. Indexing

An SQLite FTS5 virtual table, built as a **standalone table that stores its own copy
of the markdown text** (not an external-content table referencing the file on disk).
This is a deliberate choice, not the default: an external-content FTS5 table needs the
original text re-supplied to process a delete, which becomes awkward the moment a
version is superseded and its replacement is what's "current" — a standalone table
sidesteps that sync problem entirely, at the cost of storing text once in the
filesystem and once in the index, which is a non-issue at this corpus's size. The
index row for every version — `current`, `superseded`, and `missing`-sourced (§9a) —
is kept, not deleted, since it's cheap to keep and useful for provenance; the CLI
query below instead filters to `status='current'` by default and requires an explicit
flag to include superseded or missing-sourced results.

Standard indexes on `source_type`, `status` (`current`/`superseded`), `converted_at`,
and source folder path. No `business_line` column — this database is
Freedom2BeU-only; the separate db file *is* the partition.

No UI in this phase. "Ease of future use" is delivered as: a CLI query command
(`python -m doc_ingest.query --search "..." --type gdoc --status current`) and a
periodically regenerated flat CSV/markdown manifest — the same pattern this repo
already uses for the YouTube corpus (`_youtube-content-index.md/.csv`).

## 13. Testing

Pytest, run from `doc-ingest-app/` with its own `pytest.ini` (matching the existing
`pipeline-app`/root split convention in this repo).

- **Unit**: naming/path-shortening logic including the long-path edge case; each
  gauntlet check in isolation with synthetic inputs (garbling detection, word-count
  parity math, the scanned-PDF heuristic); a concurrency test racing two simulated
  workers against one `pending` job, asserting exactly one wins the claim.
- **Regression test for the mtime/modifiedTime distinction (§4 step 3, §9)**: a
  fixture where a `.gdoc` stub's own mtime is unchanged but the mocked Drive API
  reports a newer `modifiedTime` — assert the job still gets enqueued. This is the
  single correctness issue in this design most worth a standing guard.
- **Integration**: a fixture folder covering every type (pdf/docx/xlsx/txt/md + a
  mocked Drive response for a fake gdoc), run end-to-end, asserting the output tree,
  frontmatter, DB rows, and gauntlet outcomes.
- **Read-only-input enforcement, tested for real**: the test fixture's source folder
  gets actual read-only/deny-write treatment, so any code path that attempts a write
  against it fails the test with a real OS error rather than relying on review.
- **Read-only-output enforcement**: after a file is placed and locked, attempt a
  write against it and assert it's denied (ACL, and the hook layer where feasible in
  a test harness).

## 14. Explicitly out of scope for this phase

- OCR for scanned/image-only PDFs (flagged and cataloged, not converted; a
  deliberate future phase)
- Any UI
- Domain-specific frontmatter (client name, session category, etc.) beyond
  mechanical/generic fields
- Image (png/jpg) conversion or OCR
- Video/audio transcription

## 15. Open items for the implementation plan

- Exact tolerance bands for the word-count/row-count/sheet-count parity checks (needs
  a small calibration pass against real sample files, not a number invented up front)
- The specific magic-byte signature library/approach for content-sniffing
  extensionless files
- Worker pool size, per-job timeout, the reclaim heartbeat interval/staleness
  threshold, and the run-level time budget (§11) — all config, not hardcoded, and
  none picked yet
- The specific Drive API mechanism for batching the ~100 metadata lookups (§9) —
  named as "batched" in this spec without pinning down the exact API call shape,
  which needs a look at current Drive API v3 batch/list capabilities during
  implementation rather than being asserted here
- Long-path handling (§6) needs verifying in practice that `\\?\`-prefixed paths work
  cleanly through whichever Python libraries `doc-ingest-app` ends up using for file
  I/O (some third-party libraries handle these prefixes inconsistently on Windows)
