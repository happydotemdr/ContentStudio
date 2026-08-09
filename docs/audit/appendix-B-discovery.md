# Appendix B — Discovery, Bright Data, Cron & Email

Part of the ContentStudio pipeline audit, 2026-08-08. Master report:
[`2026-08-08-pipeline-audit.md`](2026-08-08-pipeline-audit.md).

---

## T4 — Platform adapters

**Scope.** This section audits the seven discovery platform adapters and the shared Bright Data
job client: `pipeline-app/pipeline_app/discovery_bluesky.py`, `discovery_facebook.py`,
`discovery_instagram.py`, `discovery_linkedin.py` (which serves two platforms,
`linkedin-profile` and `linkedin-company`), `discovery_x.py`, `discovery_youtube.py`,
`discovery_youtube_api.py`, and `brightdata_job.py`. `discovery_engine.py`,
`discovery_digest.py`, `discovery_notify.py`, `run_discovery_cron.py`, and
`scripts/setup_discovery_task.py` were read for trace context only and are cited as evidence
where an adapter's failure mode lands there; findings against those files belong to T5/T6/T7.
Environment facts used below were verified on the audit machine: Python 3.14.4,
`locale.getencoding()` == `cp1252`, `sys.flags.utf8_mode` == 0. Documentation-only — nothing
was fixed.

### Q1 — Per-platform frontmatter conformance

Contract fields only. "aware-UTC/sec" is whether `fetched_at` is written as
`datetime.now(timezone.utc).isoformat(timespec="seconds")`.

| platform | `fetched_at` | aware-UTC/sec | `url` | `like_count` | `comment_count` | `view_count` | `published` | notes |
|---|---|---|---|---|---|---|---|---|
| youtube | yes `discovery_youtube.py:260,287` | yes | yes `:265` | yes `:276` | yes `:277` | yes `:275` | **no — writes `upload_date` `:272`** | also `channel`, `content_type`, `duration_s`, `manual_captions`, `transcript_status`, `transcript_source`, `metadata_source` |
| bluesky | yes `discovery_bluesky.py:96,108` | yes | yes `:100` | **absent** | **absent** | absent | yes `:107` | getAuthorFeed surfaces no counts, so every Bluesky item scores 0 interactions in the spotlight rank (`discovery_digest.py:265`). Documented as deliberate at `:110-111` |
| instagram | yes `discovery_instagram.py:277,286` | yes | yes `:281` | yes `:284` | yes `:285` | **absent** | yes `:283` | Reels carry a view count in the dataset; not mapped. No `author` field written (see B-23) |
| linkedin-profile | yes `discovery_linkedin.py:299,314` | yes | yes `:302` | yes `:311` | yes `:312` | absent | yes `:310` | also `author`, `account_type`, `content_type`, `hashtags` |
| linkedin-company | yes (same code path) | yes | yes | yes | yes | absent | yes | identical shape; `author_filter=False` (`:136`) |
| facebook | yes `discovery_facebook.py:290,308` | yes | yes `:294` | yes `:302` | yes `:303` | yes `:306` (`video_view_count`) | yes `:301` | also `share_count`, `profile_id`, `is_page`, `hashtags` |
| x | yes `discovery_x.py:324,345` | yes | yes `:328` | yes `:333` | yes `:334` | yes `:336` | yes `:332` | also `repost_count`, `bookmark_count`, `quote_count`, `photos`, `videos`, `external_url` |

**All seven write `fetched_at` in the mandated shape.** The mandatory-field half of the contract
is clean across the board.

**`url` never absent, sometimes empty.** The five Bright Data adapters write
`row.get("url") or ""` (`discovery_instagram.py:205`, `discovery_linkedin.py:108`,
`discovery_facebook.py:117`, `discovery_x.py:132`), so a missing URL reaches disk as an empty
string rather than an absent key. `discovery_digest._as_optional_str` (`:146-153`) normalizes
`""` to `None`, so the "render without a link, warn to stderr" path still fires correctly. No
finding; recorded because the contract's wording ("an item missing it") does not literally
describe what the adapters emit.

**`upload_date` vs `published` — confirmed and assessed.** `discovery_youtube.py:272` writes
`upload_date`, never `published`. Nothing breaks today, for one reason only: the email side
hardcodes a YouTube-shaped fallback, `meta.get("published") or meta.get("upload_date")`, at
`discovery_digest.py:191`. That falsifies the contract's own headline claim — "an adapter that
does this appears in the daily email ... with **no change to any email-side module**"
(`discovery_digest.py:8-10`, restated in `CLAUDE.md`) — since the in-tree reference adapter
required exactly such a change. The date-cutoff logic in `process_handle`
(`discovery_engine.py:62,69`) reads `published` off the *enumerate* dict, not off the file, so
the divergence is confined to the email render. Filed as B-04 (S4, docs-drift), not higher.

### Q2 — Can "zero results" be distinguished from "the fetch failed"?

| platform | distinguishable? | evidence |
|---|---|---|
| bluesky | **NO** | `discovery_bluesky.py:40-43` bare `except Exception: break`. A DNS failure, a 5xx, a timeout, and a genuinely empty feed all produce `[]`, which `discovery_engine.py:365` records as the healthy `no_new_content`. Confirms SEED-7; extended by B-05/B-06/B-07 |
| youtube | **NO** | `discovery_youtube.py:62-68` — any non-zero yt-dlp exit, or empty stdout, returns `[]`; only the `/videos` tab even warns, and only to stderr. `:102-110` drops all Shorts when the Data API has no key (SEED-8). `:242-248` treats "Data API answered, yt-dlp was bot-blocked" as a full success. See B-10..B-14 |
| instagram | **partial** | Job failure/timeout genuinely raises (`brightdata_job.py:112,114`) and reaches the engine's per-handle error path — good. But an all-error batch (`include_errors=true` rows carrying no `post_id`) prints only a low-key `!` drop count at `discovery_instagram.py:223-224` and then returns `[]` → `no_new_content`. Alone among the four Bright Data adapters it has no billed-and-captured-nothing escalation. See B-22 |
| linkedin-profile | **YES** | `discovery_linkedin.py:211` never swallows; `:234-250` escalates a billed-but-empty batch with cause-specific advice |
| linkedin-company | **YES** | same code path (`:234-250`) |
| facebook | **YES** | `discovery_facebook.py:219` never swallows; `:231-239` escalates, including Bright Data's own `error_code` via `_error_codes` (`:125-132`) |
| x | **YES** | `discovery_x.py:228` never swallows; `:252-267` escalates with cause-specific advice |

Two qualifiers apply to every **YES** above. First, the escalation is stderr text only — it
changes no run status, no `discovery_run_handles` row, and no run record; see B-01. Second, on
the production (scheduled) path stderr has no destination at all, so in practice none of these
warnings is ever read; also B-01.

### Q3 — Credentials, per platform

| platform | needs | lookup order | absent ⇒ |
|---|---|---|---|
| youtube (enumeration) | `cookies.txt` at `pipeline-app/cookies.txt` | file only, `discovery_youtube.py:33,36-41` | **partial results / silent skip.** One stderr warning, then yt-dlp runs cookie-less. Channel listing usually survives; per-video fetches hit YouTube's bot-check and fail invisibly (B-12) |
| youtube (metadata) | `YOUTUBE_API_KEY` env, else `pipeline-app/youtube_api_key.txt` | env → file, `discovery_youtube_api.py:51-60` | **silent skip, with two different behaviors.** `fetch_metadata` warns to stderr and returns `{}` (`:151-153`) — once **per video** (B-15). `fetch_upload_dates` returns `{}` with **no warning at all** (`:191-192`); the caller warns only if the channel has Shorts (`discovery_youtube.py:102-110`), so a Shorts-less channel gets no signal whatsoever. Cascades into B-14 |
| bluesky | none (public AppView) | n/a | n/a |
| instagram | `BRIGHTDATA_API_KEY` env, else `pipeline-app/brightdata_api_key.txt` | env → file, `brightdata_job.py:36-47` via `discovery_instagram.py:48-51` | **hard failure, per handle.** `RuntimeError` at `discovery_instagram.py:104-108` → engine per-handle `except` (`discovery_engine.py:373-380`) → status `error`. Correct, but repeated once per handle with no preflight (B-21) |
| linkedin-profile / -company | same token | `discovery_linkedin.py:158-159` | hard failure, per handle, `:191-195` |
| facebook | same token | `discovery_facebook.py:143-146` | hard failure, per handle, `:192-197` |
| x | same token | `discovery_x.py:157-160` | hard failure, per handle, `:200-205` |

The Bright Data token discipline is the good pattern in this file set: absence is a raised
exception, not a degraded run. YouTube is the opposite on both of its credentials — every
missing-credential path there degrades silently.

### Q4 — Hardcoded constants

| constant | value | file:line | should be configurable? |
|---|---|---|---|
| `BLUESKY_API` | public AppView URL | `discovery_bluesky.py:16` | no |
| `USER_AGENT` | fixed string | `discovery_bluesky.py:17`, `discovery_youtube.py:23` | no (and the YouTube one is dead — never passed to yt-dlp) |
| HTTP timeout | `30` | `discovery_bluesky.py:22` | yes — a bare literal, not even a named constant |
| `page_limit` | `5` (× 100 posts) | `discovery_bluesky.py:33` | yes — caps Bluesky history at 500 posts and is re-paid per item (B-07) |
| title truncation | `[:60]` | `discovery_bluesky.py:59` | no, but it is the filter surface (B-08) |
| `DATASET_ID` | `gd_lk5ns7kz21pck8jpis` | `discovery_instagram.py:45` | no — product identity, correctly commented as non-secret |
| `DATASET_ID` | `gd_lyy3tktm25m4avu764` | `discovery_linkedin.py:29` | no |
| `DATASET_ID` | `gd_lkaxegm826bjpoo9m5` | `discovery_facebook.py:29` | no |
| `DATASET_ID` | `gd_lwxkxvnf1cynvib9co` | `discovery_x.py:32` | no |
| `gd_REPLACE` placeholder guard | — | `discovery_instagram.py:60-62` | **unreachable dead code** (B-24) |
| `MAX_ITEMS_PER_RUN` | `10` | `discovery_instagram.py:54`, `discovery_linkedin.py:34`, `discovery_facebook.py:34`, `discovery_x.py:39` | **yes, urgently** — this is the silent truncation cap (B-02) |
| `POLL_TIMEOUT_S` | `300` / `600` (X) | `discovery_instagram.py:55`, `discovery_linkedin.py:35`, `discovery_facebook.py:35`, `discovery_x.py:44` | yes — X already needed a different value, proving one literal does not fit all |
| `POLL_INTERVAL_S` | `5` | `discovery_instagram.py:56`, `discovery_linkedin.py:36`, `discovery_facebook.py:36`, `discovery_x.py:45` | low priority |
| `TITLE_MAX_CHARS` | `60` | `discovery_linkedin.py:38`, `discovery_facebook.py:38`, `discovery_x.py:47` | no |
| `BRIGHTDATA_API_BASE` | v3 API URL | `brightdata_job.py:24` | no |
| `REQUEST_TIMEOUT_S` | `30` | `brightdata_job.py:25` | yes — one value for trigger, poll, and a potentially large snapshot fetch |
| `COOKIES_PATH` | `pipeline-app/cookies.txt` | `discovery_youtube.py:33` | yes |
| yt-dlp `--retries 5`, `--sleep-requests 2` | — | `discovery_youtube.py:214` | low priority |
| `_TABS` | `videos`, `shorts` | `discovery_youtube.py:55` | no |
| `KEY_FILE` paths | `youtube_api_key.txt`, `brightdata_api_key.txt` | `discovery_youtube_api.py:41`, and the four Bright Data adapters | no |
| `MAX_IDS_PER_CALL` | `50` | `discovery_youtube_api.py:43` | no — a vendor limit |
| API URLs | Data API v3 | `discovery_youtube_api.py:36` | no |

`discovery_settings` (`pipeline-app/pipeline_app/schema.sql:70-76`) holds only `frequency`,
`time_of_day`, `timezone`, and `last_scheduled_run_date`. **No cost, cap, or timeout knob is
reachable without a code edit** — see B-03.

### Q5 — `brightdata_job.py` poll loop

- **A transient 429/503 is a whole-handle failure.** `poll_status` (`:75-82`) calls
  `raise_for_status()` with no retry and no status-code discrimination, so `requests.HTTPError`
  escapes `await_results` (`:108`) and lands in the engine's per-handle `except`
  (`discovery_engine.py:373`). The handle records `error`/0 items for a run that had already
  triggered — and been billed for — a collection job. Same for `trigger` (`:71`) and
  `fetch_results` (`:92`). Filed as B-18.
- **A snapshot stuck at `running` loses its data.** After `poll_timeout_s`,
  `BrightDataJobTimeout` is raised (`:113-116`). No `fetch_fn` attempt is made, so if the
  snapshot completes a second later its records are never collected. The `job_id` survives only
  inside the exception message string, which does reach `discovery_run_handles.error_message`
  (`discovery_engine.py:375`) — recoverable by hand, but there is no re-fetch path, no resume,
  and nothing machine-readable. Filed as B-19.
- **The snapshot is never cleaned up.** No `DELETE` or equivalent call exists anywhere in the
  module; timed-out, failed, and successfully-fetched snapshots all persist on Bright Data's side
  indefinitely. Part of B-19.
- **Response shapes are unguarded.** `response.json()["snapshot_id"]` (`:72`) and
  `response.json()["status"]` (`:82`) raise `KeyError` on any shape change or on a 200-with-error
  body; `fetch_results` returns `response.json()` unvalidated (`:93`), so a dict response makes
  the callers' `for r in raw_rows` iterate key strings and fail with `AttributeError` on
  `row.get`. All are loud, but none names the real cause. Filed as B-20.
- The deadline check ordering (`:113`, after the status check, before the sleep) is correct — a
  job that turns `ready` on the final poll is still fetched. No finding.

### Q6 — `discovery_youtube.py` subprocess handling

- **`:61` — return code checked, but the check itself is the crash site.** `subprocess.run(...,
  text=True)` with no `encoding=` decodes yt-dlp's UTF-8 stdout using
  `locale.getencoding()` == `cp1252`. Verified on the audit machine: a title containing an emoji
  whose UTF-8 encoding includes byte `0x81/0x8D/0x8F/0x90/0x9D` (e.g. U+1F60D 😍 → `F0 9F 98 8D`)
  raises `UnicodeDecodeError` inside `subprocess`'s reader **thread**, so `subprocess.run` itself
  returns normally with `returncode == 0` and `stdout is None`. Line `:62` then evaluates
  `proc.stdout.strip()` → `AttributeError: 'NoneType' object has no attribute 'strip'`, which
  escapes `_enumerate_tab` → `enumerate_newest_first` → `process_handle` → the engine's
  per-handle `except` (`discovery_engine.py:373`), recording that channel as `error` with a
  message naming nothing relevant. Emoji that decode cleanly (U+1F525 🔥 → `F0 9F 94 A5`, all
  cp1252-defined) do not crash — they silently mojibake, verified as the 4-character sequence
  `U+00F0 U+0178 U+201D U+00A5`, which then flows into the `.md` filename via `slugify`
  (`:262`), into the body H1 (`:290`), and into the email. Filed as B-10 (S1).
- **`:69` — `json.loads(proc.stdout)` unguarded.** `JSONDecodeError` propagates the same way
  (per-handle `error`). Loud, so lower severity than the decode issue, but note the asymmetry:
  `download_item` guards its `json.loads` (`:222-225`) and `peek_upload_date` does not (`:143`).
  Filed as B-16.
- **`:139` and `:217` — return codes fully ignored.** At `:217` this is the load-bearing one: a
  bot-blocked yt-dlp run produces no `info.json` and no `.vtt`, but if a Data API key is
  configured `api_meta` is non-empty, so the `:243` both-sources-failed guard does not fire and
  the item is written to disk with `transcript_status: "missing"` and `ok: True`. `on_disk_ids`
  (`:44-48`) then treats it as captured forever. Filed as B-12 (S1).
- **`:197-198` — the transcript-fallback bare `except`.** `youtube_transcript_api` raises typed
  errors for IP-block, rate-limiting, disabled transcripts, and unavailable videos; all collapse
  to `return None`, which the caller reads as "this video has no transcript". The module already
  learned this lesson once for `ImportError` (`:181-190`, warn-once) and did not apply it to the
  runtime branch. Filed as B-13.

### Q7 — Pagination and silent truncation

- **bluesky** — the only adapter that paginates: `page_limit=5 × limit=100`
  (`discovery_bluesky.py:33,36,37`), cursor-driven. It can silently truncate at *any* page, not
  just page 1: a mid-pagination exception `break`s (`:42-43`) and returns the partial list as if
  complete. It also runs the full 5-page walk on every enumerate with no early stop, and again
  in full for **every item downloaded** (`:83`) — 10 new posts costs up to 55 HTTP round-trips.
  B-05, B-07.
- **youtube** — no pagination limit; `--flat-playlist` enumerates the entire channel on both
  tabs every run (the module's own measurement: 274 + 603 = 877 items for one channel,
  `:51-55`), then batches every id through the Data API at 50/call
  (`discovery_youtube_api.py:158`) — ~18 quota units per handle per run, daily, to learn nothing
  new. Not truncation, but unbounded growth. B-17.
- **instagram / linkedin / facebook / x** — no pagination at all. A single job capped at
  `limit_per_input`/`num_of_posts` = 10 (`discovery_instagram.py:79,85`,
  `discovery_linkedin.py:175`, `discovery_facebook.py:177`, `discovery_x.py:178`), and the
  result is capped client-side again at `[:MAX_ITEMS_PER_RUN]`. **Yes — these truncate at page 1
  and report success:** eleven new posts since the last run yields ten downloads and a `status:
  ok` handle result. Because `BACKFILL_SUPPORTED_PLATFORMS = {"youtube", "bluesky"}`
  (`discovery_engine.py:29`) and X's own module docstring records that date-ranged backfill
  returns `dead_page` (`discovery_x.py:14-15`), the eleventh post is unrecoverable. B-02 (S1).
  Note also that `keyword_filter` is applied *after* the cap in all four (e.g.
  `discovery_x.py:283-285`), so a filtered handle sees at most 10 candidates before filtering.

### Q8 — Encoding and robustness

Three cases were tested directly against the repo's own code rather than reasoned about:

- **`---` inside a post body: safe, no finding.** `render_frontmatter` (`artifacts.py:26-28`)
  emits the delimiter, the YAML block, the delimiter, then the body; `parse_frontmatter`
  (`:13-23`) scans for the *first* `---` after line 0, which is always the real closing
  delimiter. Verified: a body of `line one\n---\nline two` round-trips with metadata intact, and
  even a body that *opens* with a full fake frontmatter block round-trips correctly. The `---`
  will render as a horizontal rule downstream; cosmetic only.
- **Null byte: safe, no finding.** `yaml.safe_dump` escapes `\x00` in a metadata value as
  `"a\0b"` (double-quoted style) and round-trips it; in the body it passes through
  `write_text(encoding="utf-8")` and `read_text` unchanged. Verified.
- **Emoji on a cp1252 host: two real defects.** See Q6 — this is B-10, and it is the single
  highest-impact finding in this section. Note the blast radius is *enumeration*, not writing:
  every adapter writes its `.md` with an explicit `encoding="utf-8"` (`discovery_bluesky.py:116`,
  `discovery_instagram.py:295`, `discovery_linkedin.py:323`, `discovery_facebook.py:317`,
  `discovery_x.py:355`, `discovery_youtube.py:300`), and `_vtt_to_text`'s reader uses
  `errors="replace"` (`discovery_youtube.py:230`), so the file-writing half is sound.
- **stderr encoding: checked, no finding.** The `!`/`!!` warnings in the owned files interpolate
  only handles, integer counts, Bright Data `error_code` values, and `proc.stderr` — and
  `proc.stderr` has already been round-tripped through cp1252, so it is by construction
  re-encodable. No adapter prints post text to stderr, so no diagnostic can itself raise
  `UnicodeEncodeError` and kill its own handle.

### Q9 — Stubs, dead code, unreachable branches

- `discovery_instagram.py:60-62` — the `gd_REPLACE` guard cannot fire; `DATASET_ID` is a real id
  (`:45`). B-24.
- `discovery_instagram.py:27`, `discovery_x.py:149` — `REQUEST_TIMEOUT_S` re-exported and never
  read, in-module or by any test. B-25. (The sibling `BRIGHTDATA_API_BASE` re-exports *are* used
  and must stay.)
- `discovery_youtube.py:23` — `USER_AGENT` is defined and never used; yt-dlp is never given a
  `--user-agent` flag.
- `peek_upload_date` returns a bare `None` in five adapters. For instagram/linkedin/facebook/x
  the "dead by design" comments are **correct** — `_normalize_row` drops any row whose date fails
  to parse, so `published` is never `None` downstream. For **bluesky the comment is wrong**:
  `discovery_bluesky.py:58` yields `published = None` whenever `createdAt`/`indexedAt` is shorter
  than 10 characters. B-09.
- `discovery_instagram.py:18,21` and `discovery_x.py:21,24` — `import time` / `import requests`
  kept solely for test monkeypatching after the logic moved to `brightdata_job.py`. Checked, not
  filed: `time` and `requests` are singleton module objects, so
  `monkeypatch.setattr(ig.time, "sleep", ...)` (`tests/test_discovery_instagram.py:40`) does
  patch the copy `brightdata_job` sees. The comments are accurate.
- No `TODO`, `FIXME`, `XXX`, `HACK`, or `NotImplementedError` exists in any owned file.

### Findings

---

### B-01 · Adapter failure diagnostics are stderr-only and reach no durable surface
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_facebook.py:236`, `pipeline-app/pipeline_app/discovery_x.py:265`, `pipeline-app/pipeline_app/discovery_linkedin.py:248`, `pipeline-app/pipeline_app/discovery_instagram.py:223`, `pipeline-app/pipeline_app/discovery_youtube.py:107`, `pipeline-app/scripts/setup_discovery_task.py:23`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: Every "this run was billed and captured nothing", "N rows dropped", "Shorts are being skipped", and "no cookies.txt" signal in all seven adapters is emitted only as stderr text. None changes a handle's `status`, its `error_message`, or the run record, so the UI and the daily email show a clean run. The registered Windows Scheduled Task command is `"python" "run_discovery_cron.py" --mode scheduled` with no redirection at all, so on the production path that stderr has no destination and the warnings are never read by anyone.
- **trigger**: Any adapter-level degradation (billed-empty batch, dropped rows, skipped Shorts, missing cookies) during a scheduled run.
- **proposed_fix**: Give the adapters a structured warning channel the engine can persist — return diagnostics alongside the item list, or write them to the run record and `discovery_run_handles` — so a degraded run is visibly degraded. Separately (T6), redirect the scheduled task's stdout/stderr to a rotating log.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: manual-trace

### B-02 · MAX_ITEMS_PER_RUN=10 silently truncates active accounts with no recovery path
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_x.py:39`, `pipeline-app/pipeline_app/discovery_instagram.py:54`, `pipeline-app/pipeline_app/discovery_linkedin.py:34`, `pipeline-app/pipeline_app/discovery_facebook.py:34`, `pipeline-app/pipeline_app/discovery_engine.py:29`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: The four Bright Data platforms fetch at most 10 posts per handle per run, capped both server-side (`limit_per_input`/`num_of_posts`) and client-side. An account that publishes more than 10 items between runs has the overflow dropped with no warning and a `status: ok` handle result. Because `BACKFILL_SUPPORTED_PLATFORMS` excludes all four, and X's own docstring records that date-ranged backfill returns `dead_page`, the missed posts can never be collected later — the corpus is permanently and invisibly incomplete. `discovery_x.py:14` describes tracking an account "posting hundreds of times a day".
- **trigger**: Any tracked X/Instagram/Facebook/LinkedIn account publishes more than 10 posts between two runs — routine for a news or high-volume brand account.
- **proposed_fix**: Detect saturation (a full-cap batch whose oldest item is newer than the handle's `last_seen_published_at`) and escalate it as a distinct, durable handle status rather than `ok`. Make the cap a per-handle setting so a high-volume account can be raised deliberately, with the cost tradeoff stated.
- **fix_cost**: M
- **depends_on_finding**: [B-01]
- **owner_task**: T4
- **detected_by**: manual-trace

### B-03 · Every cost, cap, and timeout knob is a module literal with no configuration surface
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_instagram.py:54`, `pipeline-app/pipeline_app/discovery_x.py:44`, `pipeline-app/pipeline_app/brightdata_job.py:25`, `pipeline-app/pipeline_app/discovery_bluesky.py:22`, `pipeline-app/pipeline_app/schema.sql:70`
- **component**: discovery
- **failure_mode**: latent
- **blast_radius**: `discovery_settings` exposes only frequency, time-of-day and timezone. `MAX_ITEMS_PER_RUN`, `POLL_TIMEOUT_S`, `POLL_INTERVAL_S`, `REQUEST_TIMEOUT_S`, Bluesky's `page_limit` and its bare `timeout=30` all require a source edit and a redeploy to change. X already needed a different `POLL_TIMEOUT_S` (600 vs 300), which is direct evidence that one literal does not fit every platform.
- **trigger**: Any need to raise a cap for one noisy handle, or to extend a timeout for a slow dataset.
- **proposed_fix**: Promote the per-platform operational constants into the settings table (or a small per-platform config record) with the current literals as defaults, keeping the "do not make the constants consistent" rationale at `discovery_x.py:40-43` as documentation on the default.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: grep-sweep

### B-04 · YouTube writes `upload_date`, not the contract's `published`
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_youtube.py:272`, `pipeline-app/pipeline_app/discovery_digest.py:191`, `pipeline-app/pipeline_app/discovery_digest.py:8`
- **component**: discovery
- **failure_mode**: docs-drift
- **blast_radius**: The platform contract names `published` as the optional publish-date field and claims a conforming adapter needs no email-side change. YouTube emits `upload_date` instead, and the email side carries a YouTube-specific `meta.get("published") or meta.get("upload_date")` fallback to compensate. Nothing is broken today; the risk is that the contract as written is demonstrably not what the reference adapter does, so a future adapter author has two contradictory examples.
- **trigger**: Reading the contract to build a new adapter, or removing the `upload_date` fallback as apparent dead code.
- **proposed_fix**: Either have YouTube also write `published` (keeping `upload_date` for backward compatibility with already-captured files) or amend the contract text to name both keys explicitly as the accepted spelling.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: manual-trace

### B-05 · Bluesky enumerate reports every fetch error as an empty feed
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_bluesky.py:40`, `pipeline-app/pipeline_app/discovery_bluesky.py:43`, `pipeline-app/pipeline_app/discovery_engine.py:365`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: Extends SEED-7. The bare `except Exception: break` covers DNS failure, connection reset, HTTP error, timeout and malformed JSON alike, and each yields the same `[]` a genuinely quiet account yields — recorded as the healthy `no_new_content`. It also truncates *mid-pagination*: a failure on page 3 of 5 returns pages 1–2 as if the walk had completed, which for a brand-new handle silently shortens the 90-day lookback window. Bluesky is the one adapter whose module docstring does not carry the "an empty list means nothing was there" discipline that `brightdata_job.py:6-10` was written to enforce.
- **trigger**: Any transient network or AppView failure during a Bluesky enumerate.
- **proposed_fix**: Let the exception propagate to the engine's per-handle error path, as every Bright Data adapter already does. If bounded retry is wanted, add it explicitly around `_http_get` and raise on exhaustion; a partial multi-page walk must be distinguishable from a complete one.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: manual-trace

### B-06 · A transient Bluesky failure during validate_handle permanently disables the handle
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_bluesky.py:40`, `pipeline-app/pipeline_app/discovery_engine.py:110`, `pipeline-app/pipeline_app/discovery_engine.py:255`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: `process_handle_validate` treats an empty enumerate as `ok: False`, and `run_discovery` then sets the handle to `status='invalid'` **and** `included=False`. Because B-05 makes a network blip indistinguishable from an empty feed, a perfectly valid Bluesky account registered during a momentary outage is marked invalid and excluded from all future runs, with the operator-facing reason "enumerate returned no results". Nothing ever re-tries it. The same swallow means an existing handle can also be silently mis-validated on re-validation.
- **trigger**: Registering or re-validating a Bluesky handle while the AppView is briefly unreachable.
- **proposed_fix**: Fix B-05 so the failure raises; the engine's validate path already has a distinct `except` branch (`discovery_engine.py:272`) that records `error`, and the auto-exclude on genuine invalidity can then stay meaningful.
- **fix_cost**: S
- **depends_on_finding**: [B-05]
- **owner_task**: T4
- **detected_by**: manual-trace

### B-07 · Bluesky download_item re-walks the entire paginated feed once per item
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_bluesky.py:83`, `pipeline-app/pipeline_app/discovery_bluesky.py:90`, `pipeline-app/pipeline_app/discovery_bluesky.py:33`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: Unlike every Bright Data adapter, Bluesky caches nothing between enumerate and download. Each `download_item` re-runs the full 5-page, 500-post walk to find one post, so downloading N new posts costs up to 5(N+1) HTTP requests — 55 round-trips for 10 posts against a public unauthenticated endpoint. Worse, when that re-fetch fails (or the item has aged past 500 posts) the function returns `{"ok": False, "published": None}` with **no reason attached anywhere**, and the engine simply drops the item from `downloaded`, so a handle can report `no_new_content` after enumerating real posts it then failed to fetch.
- **trigger**: Any Bluesky handle with new posts, on every run; the failure branch on any rate-limit or transient error during the re-fetch.
- **proposed_fix**: Cache the normalized rows from `enumerate_newest_first` keyed by rkey and have `download_item` read from that cache, matching the pattern already used by all four Bright Data adapters. Make the not-found branch raise or carry a reason rather than a bare `ok: False`.
- **fix_cost**: S
- **depends_on_finding**: [B-05]
- **owner_task**: T4
- **detected_by**: manual-trace

### B-08 · Bluesky keyword_filter matches only the first 60 characters of a post
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_bluesky.py:59`, `pipeline-app/pipeline_app/discovery_bluesky.py:64`, `pipeline-app/pipeline_app/discovery_instagram.py:244`, `pipeline-app/pipeline_app/discovery_x.py:285`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: The Bluesky filter tests `keyword_filter in i["title"]`, and `title` is `text[:60]`. Every other text-bearing adapter filters the full body (`caption` for Instagram, `body` for LinkedIn/Facebook/X). A keyword appearing anywhere past character 60 of a Bluesky post is silently non-matching, so an operator who sets a keyword filter on a Bluesky handle gets a quietly under-populated capture that looks like a low-activity account.
- **trigger**: Setting any `keyword_filter` on a Bluesky handle whose posts are longer than 60 characters — i.e. most of them.
- **proposed_fix**: Filter on the full `text` field, which `enumerate_newest_first` already carries alongside `title`, matching the other adapters.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: manual-trace

### B-09 · Bluesky peek_upload_date's "dead code" comment is false
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_bluesky.py:69`, `pipeline-app/pipeline_app/discovery_bluesky.py:58`, `pipeline-app/pipeline_app/discovery_engine.py:62`
- **component**: discovery
- **failure_mode**: docs-drift
- **blast_radius**: The comment asserts "enumerate_newest_first always populates 'published'", but line 58 assigns `None` whenever `createdAt`/`indexedAt` is shorter than 10 characters. For a brand-new handle, `process_handle` then falls through to `peek_upload_date`, gets `None`, and increments `consecutive_undated`; five such posts in a row abort the whole new-handle walk. The four Bright Data adapters carry the same comment and there it is genuinely true, because `_normalize_row` drops undated rows — Bluesky does not.
- **trigger**: A Bluesky record with a malformed or absent `createdAt`, during first capture of a new handle.
- **proposed_fix**: Either drop undated Bluesky items in `enumerate_newest_first` the way the Bright Data adapters do, which would make the comment true, or correct the comment and accept the fallthrough.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: manual-trace

### B-10 · cp1252 subprocess decoding crashes or corrupts YouTube enumeration on emoji titles
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_youtube.py:61`, `pipeline-app/pipeline_app/discovery_youtube.py:62`, `pipeline-app/pipeline_app/discovery_youtube.py:262`, `pipeline-app/pipeline_app/discovery_youtube.py:290`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: `subprocess.run(..., text=True)` with no `encoding=` decodes yt-dlp's UTF-8 output as cp1252 on this Windows host (verified: `locale.getencoding()` == `cp1252`, `utf8_mode` == 0, and `PYTHONIOENCODING=utf-8` is set only for the unrelated Claude CLI path at `cli_runner.py:238`). Two outcomes, both verified by reproduction. (a) An emoji whose UTF-8 bytes include `0x8D` (U+1F60D) raises `UnicodeDecodeError` in the reader thread; `subprocess.run` returns `returncode=0, stdout=None`, and line 62's `proc.stdout.strip()` then raises `AttributeError: 'NoneType' object has no attribute 'strip'` — the entire channel records `error` with an opaque message, on every run, forever. (b) An emoji whose bytes are all cp1252-defined (U+1F525) decodes to 4 mojibake characters, which flow into the `.md` filename via `slugify`, into the body H1, into the corpus, and into the daily email. One emoji anywhere in a channel's back catalogue is enough for either.
- **trigger**: Any video title on any enumerated channel tab containing an emoji or other non-cp1252 character — near-certain across a 14-channel creator-education roster.
- **proposed_fix**: Pass `encoding="utf-8", errors="replace"` to all three `subprocess.run` calls in this module, and guard line 62 against `stdout is None` so a decode failure can never present as an `AttributeError`.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: manual-trace

### B-11 · A failed YouTube /videos enumeration is reported as a quiet day
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_youtube.py:62`, `pipeline-app/pipeline_app/discovery_youtube.py:68`, `pipeline-app/pipeline_app/discovery_youtube.py:102`, `pipeline-app/pipeline_app/discovery_engine.py:365`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: Extends SEED-8. `_enumerate_tab` returns `[]` on any non-zero yt-dlp exit or empty stdout — yt-dlp missing from PATH, a bot-check, a network failure, a renamed channel — and the caller merges that into a normal item list. If both tabs fail the handle reports `no_new_content`; if only `/videos` fails and the Shorts tab succeeds with Data API dates available, the run silently captures a Shorts-only slice of the channel and still reports `ok`. The only signal is a stderr warning, which B-01 shows nobody sees. Separately (SEED-8) the no-API-key branch at `:102-110` drops every Short with only a stderr line.
- **trigger**: yt-dlp unavailable, rate-limited, or bot-blocked for one tab of one channel.
- **proposed_fix**: Distinguish "tab does not exist" (the legitimate empty case, only expected for `/shorts`) from "the fetch failed", and raise on the latter so the engine records a per-handle `error`. Never merge a failed tab's empty list into a successful tab's results.
- **fix_cost**: M
- **depends_on_finding**: [B-01]
- **owner_task**: T4
- **detected_by**: manual-trace

### B-12 · A bot-blocked YouTube download writes a permanent transcript-less capture
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_youtube.py:217`, `pipeline-app/pipeline_app/discovery_youtube.py:243`, `pipeline-app/pipeline_app/discovery_youtube.py:284`, `pipeline-app/pipeline_app/discovery_youtube.py:48`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: The `subprocess.run` at `:217` ignores its return code entirely. When YouTube's per-video bot-check is active (no valid `cookies.txt`), yt-dlp writes neither `info.json` nor any `.vtt`, but a configured Data API key makes `api_meta` non-empty, so the `:243` both-sources-failed guard does not fire. The item is written with `transcript_status: "missing"`, `ok: True`, and counted as a successful download. `on_disk_ids` keys on the filename, so the video is *never re-attempted* — the transcript, which is the entire point of this corpus, is permanently absent for that video and the run reports success. `missing_transcript_ids` (`:309`) exists as manual triage but nothing schedules or surfaces it.
- **trigger**: An expired or absent `cookies.txt` combined with a working `YOUTUBE_API_KEY` — the exact configuration the module docstring at `:25-33` describes as expected.
- **proposed_fix**: Treat "metadata succeeded but no transcript was obtained by either route" as a retryable outcome rather than a completed capture — either withhold the file, or write it with a status the next run re-attempts, bounded by a retry count so it cannot loop forever on genuinely transcript-less videos.
- **fix_cost**: M
- **depends_on_finding**: [B-13]
- **owner_task**: T4
- **detected_by**: manual-trace

### B-13 · The transcript fallback's bare except hides rate-limiting and IP blocks
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_youtube.py:197`, `pipeline-app/pipeline_app/discovery_youtube.py:198`, `pipeline-app/pipeline_app/discovery_youtube.py:233`, `pipeline-app/pipeline_app/discovery_youtube.py:284`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: `youtube_transcript_api` raises distinct exceptions for IP-block, rate-limiting, disabled transcripts, and video-unavailable; all collapse to `return None`, which the caller writes as `transcript_status: "missing"`. An IP block during a 300-video run therefore produces 300 permanently transcript-less captures that look identical to 300 videos that genuinely have no captions. The module already fixed exactly this class of bug for the `ImportError` case (`:181-190`, with a warn-once flag) and left the runtime branch untouched.
- **trigger**: Any rate-limit or IP block from the transcript API mid-run.
- **proposed_fix**: Catch the library's typed exceptions separately: return `None` only for genuine "no transcript exists" cases, and let block/rate-limit errors propagate or set a run-level degraded flag so the affected items are not written as complete.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: manual-trace

### B-14 · A new YouTube handle with no API key and an active bot-block captures nothing, silently
- **severity**: S2
- **confidence**: probable
- **evidence**: `pipeline-app/pipeline_app/discovery_youtube_api.py:191`, `pipeline-app/pipeline_app/discovery_youtube.py:117`, `pipeline-app/pipeline_app/discovery_youtube.py:143`, `pipeline-app/pipeline_app/discovery_engine.py:65`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: With no Data API key, `fetch_upload_dates` returns `{}` with **no warning at all**, and the caller only warns when the channel has Shorts — a Shorts-less channel produces no signal whatsoever. Every enumerated item then carries `published=None`, so a brand-new handle falls through to `peek_upload_date` per item, which spawns a yt-dlp subprocess each time; under the bot-block those all return `None`, `consecutive_undated` reaches 5, and `process_handle` breaks out with zero downloads and the healthy status `no_new_content`. The operator sees a newly-added channel that simply "had nothing".
- **trigger**: Adding a YouTube handle with `YOUTUBE_API_KEY` unset and `cookies.txt` absent or stale.
- **proposed_fix**: Warn once per process from `fetch_upload_dates` when no key is configured, and have `process_handle`'s undated-abort surface a distinct, durable status rather than reusing `no_new_content`. The latter half is T5's.
- **fix_cost**: S
- **depends_on_finding**: [B-01]
- **owner_task**: T4
- **detected_by**: manual-trace

### B-15 · The "no YouTube Data API key" warning is printed once per video
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_youtube_api.py:151`, `pipeline-app/pipeline_app/discovery_youtube.py:242`, `pipeline-app/pipeline_app/discovery_youtube.py:121`, `pipeline-app/pipeline_app/discovery_youtube.py:173`
- **component**: discovery
- **failure_mode**: latent
- **blast_radius**: `fetch_metadata` warns unconditionally on every call, and `fetch_one` calls it once per video from both `download_item` and `peek_upload_date`. A key-less run over a few hundred videos emits hundreds of identical lines, drowning the `!!` escalations that B-01 already makes hard to notice. The same module's sibling problem was solved correctly in `discovery_youtube.py:173` with a warn-once module flag; that discipline was not applied here.
- **trigger**: Any run with `YOUTUBE_API_KEY` unset.
- **proposed_fix**: Guard the warning with a module-level warn-once flag, matching `_TRANSCRIPT_API_MISSING_WARNED`.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: manual-trace

### B-16 · YouTube subprocess return codes ignored and peek's JSON parse unguarded
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_youtube.py:139`, `pipeline-app/pipeline_app/discovery_youtube.py:143`, `pipeline-app/pipeline_app/discovery_youtube.py:217`, `pipeline-app/pipeline_app/discovery_youtube.py:222`
- **component**: discovery
- **failure_mode**: latent
- **blast_radius**: Neither `peek_upload_date` nor `download_item` inspects its `subprocess.run` result, so a yt-dlp binary that is missing, crashed, or killed is indistinguishable from one that ran and found nothing. `peek_upload_date` then calls `json.loads(info_path.read_text(...))` with no guard at `:143`, so a truncated or partially-written `info.json` raises `JSONDecodeError` that escapes to the engine's per-handle handler — while the structurally identical parse in `download_item` at `:222-225` *is* guarded. The inconsistency means the same corrupt file is fatal on one path and tolerated on the other.
- **trigger**: yt-dlp absent from PATH, or a `info.json` write interrupted by a process kill.
- **proposed_fix**: Check `returncode` on both calls and log the captured stderr when non-zero; wrap `peek_upload_date`'s `json.loads` in the same `try/except json.JSONDecodeError` `download_item` already uses.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: manual-trace

### B-17 · YouTube re-enumerates the entire channel catalogue on every run
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_youtube.py:60`, `pipeline-app/pipeline_app/discovery_youtube.py:51`, `pipeline-app/pipeline_app/discovery_youtube.py:95`, `pipeline-app/pipeline_app/discovery_youtube_api.py:158`
- **component**: discovery
- **failure_mode**: latent
- **blast_radius**: `--flat-playlist` with no bound lists every video on both tabs — the module's own measurement is 877 items for one channel — and every id is then batched through the Data API at 50 per call, ~18 quota units per handle per run, daily, purely to learn dates for items already on disk. The early-stop dedup lives downstream in `process_handle`, so it saves no enumeration cost. This scales linearly with each channel's lifetime back catalogue and with the roster size.
- **trigger**: Every scheduled run, for every YouTube handle.
- **proposed_fix**: Bound the enumeration with yt-dlp's `--playlist-end` to a small multiple of the expected per-run item count, falling back to a full walk only for a brand-new handle, and fetch dates only for ids not already on disk.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: manual-trace

### B-18 · Bright Data poll loop has no HTTP retry, so a transient 429/503 fails a billed handle
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/brightdata_job.py:81`, `pipeline-app/pipeline_app/brightdata_job.py:108`, `pipeline-app/pipeline_app/brightdata_job.py:71`, `pipeline-app/pipeline_app/brightdata_job.py:92`
- **component**: discovery
- **failure_mode**: loud
- **blast_radius**: `poll_status` calls `raise_for_status()` with no retry and no status-code discrimination, and `await_results` does not catch it, so a single 429 or 503 on any one of up to 60 polls raises `requests.HTTPError` straight out to the engine's per-handle `except`. The handle records `error`/0 items even though the collection job was already triggered and billed and may well have completed. The same applies to `trigger` and `fetch_results`. This is the one place where a *transient* condition costs money and yields nothing.
- **trigger**: Any transient 429/503/connection error from `api.brightdata.com` during a poll — likely across four platforms × N handles × 60 polls per job.
- **proposed_fix**: Add bounded retry with backoff around the poll and fetch calls for retryable statuses (429, 5xx) and connection errors, keeping the raise-on-exhaustion contract intact so a genuine failure still surfaces.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: manual-trace

### B-19 · A timed-out Bright Data snapshot loses its paid data and is never cleaned up
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/brightdata_job.py:113`, `pipeline-app/pipeline_app/brightdata_job.py:114`, `pipeline-app/pipeline_app/brightdata_job.py:109`, `pipeline-app/pipeline_app/discovery_x.py:40`
- **component**: discovery
- **failure_mode**: loud
- **blast_radius**: On `poll_timeout_s` expiry the loop raises without ever calling `fetch_fn`, so a snapshot that becomes `ready` one second later is abandoned with its records paid for and uncollected. There is no resume path and no re-fetch entry point: the only trace of the `job_id` is inside the exception message, which reaches `discovery_run_handles.error_message` and the run record as free text. Nothing in the module ever deletes a snapshot either — timed-out, failed and fetched snapshots all accumulate indefinitely on Bright Data's side. The X adapter's comment at `:40-43` shows this has already bitten once (300s left "under a minute of margin" on a job measured at 243s).
- **trigger**: Bright Data latency exceeding `POLL_TIMEOUT_S` — routine under vendor load.
- **proposed_fix**: On timeout, persist the `snapshot_id` in a structured, machine-readable place and attempt one late fetch on the following run before giving up; add an explicit snapshot cleanup call once results are collected or abandoned.
- **fix_cost**: M
- **depends_on_finding**: [B-01]
- **owner_task**: T4
- **detected_by**: manual-trace

### B-20 · Bright Data response shapes are indexed without validation
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/brightdata_job.py:72`, `pipeline-app/pipeline_app/brightdata_job.py:82`, `pipeline-app/pipeline_app/brightdata_job.py:93`, `pipeline-app/pipeline_app/discovery_facebook.py:221`
- **component**: discovery
- **failure_mode**: loud
- **blast_radius**: `response.json()["snapshot_id"]` and `response.json()["status"]` raise bare `KeyError` on any vendor shape change or on a 200-with-error-body, and `fetch_results` returns `response.json()` entirely unvalidated — a dict response makes every caller's `for r in raw_rows` iterate key strings and die with `AttributeError: 'str' object has no attribute 'get'` inside `_normalize_row`. All three surface as per-handle errors, so nothing is hidden, but the recorded `error_message` names none of the actual causes, which is the difference between a five-minute and a two-hour diagnosis across four platforms.
- **trigger**: A Bright Data API shape change, an auth failure returned with a 200, or an unexpected snapshot envelope.
- **proposed_fix**: Validate each response shape and raise a typed error naming the endpoint and the received keys; assert `fetch_results` returned a list before handing it to callers.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: manual-trace

### B-21 · A missing Bright Data token is discovered per handle at job time, not at preflight
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_instagram.py:104`, `pipeline-app/pipeline_app/discovery_linkedin.py:191`, `pipeline-app/pipeline_app/discovery_facebook.py:193`, `pipeline-app/pipeline_app/discovery_x.py:201`
- **component**: discovery
- **failure_mode**: loud
- **blast_radius**: The credential check lives inside `_run_collection_job`, so an unconfigured token is not detected until the first handle of each platform is already being processed. A roster with twenty Bright Data handles produces twenty identical `RuntimeError` rows and twenty error records for one environment fact, and the run finishes `completed_with_errors` rather than refusing to start. The behavior is correct (loud, not silent) but the diagnosis is buried in per-handle noise.
- **trigger**: Running discovery with `BRIGHTDATA_API_KEY` unset and Bright Data handles registered.
- **proposed_fix**: Expose a per-platform credential check the run can call once before the handle loop, failing fast with a single clear message; keep the per-job guard as a backstop.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: manual-trace

### B-22 · Instagram alone lacks the billed-and-captured-nothing escalation
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_instagram.py:222`, `pipeline-app/pipeline_app/discovery_instagram.py:225`, `pipeline-app/pipeline_app/discovery_facebook.py:231`, `pipeline-app/pipeline_app/discovery_x.py:252`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: LinkedIn, Facebook and X each carry an explicit `if raw_rows and not kept:` branch that shouts "this run was billed and captured nothing" with cause-specific advice, and Facebook additionally reports Bright Data's own `error_code`. Instagram — the oldest of the four and the one whose docstring at `brightdata_job.py:9-10` cites as the origin of the whole discipline — has no such branch. A dead or renamed Instagram handle returning nothing but `include_errors` rows prints a low-key `!` drop count and the run records `no_new_content`: paid for, captured nothing, indistinguishable from a quiet day. Instagram also never inspects `error`/`error_code`, so the vendor's own reason is discarded.
- **trigger**: A renamed, private, or deleted Instagram account that is still registered as a handle.
- **proposed_fix**: Port the `raw_rows and not kept` escalation from `discovery_facebook.py:231-239` into the Instagram adapter, including the `_error_codes` extraction so Bright Data's reason is reported.
- **fix_cost**: S
- **depends_on_finding**: [B-01]
- **owner_task**: T4
- **detected_by**: manual-trace

### B-23 · Instagram records no author, so a foreign-account regression is undetectable
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_instagram.py:198`, `pipeline-app/pipeline_app/discovery_instagram.py:278`, `pipeline-app/pipeline_app/discovery_facebook.py:109`, `pipeline-app/pipeline_app/discovery_x.py:330`
- **component**: discovery
- **failure_mode**: latent
- **blast_radius**: X filters on `user_posted` and LinkedIn-profile on `user_id`, both because live testing showed the vendor returning other accounts' posts; Facebook does not filter but deliberately records `author` "so a regression is detectable after the fact". Instagram neither filters nor records — `_normalize_row` has no author field and `download_item` writes none. If the Instagram dataset ever starts returning tagged or suggested posts the way its sibling products do, the contamination lands in the corpus with no evidence of where it came from and no way to identify affected files retroactively. Instagram also omits `view_count` even though the dataset serves Reels.
- **trigger**: A vendor-side change to what `discover_new`/`discover_by=url` returns for an Instagram profile.
- **proposed_fix**: Record the row's account/owner field in the normalized row and in the frontmatter, matching Facebook's rationale; decide filtering separately once a live sample confirms whether contamination occurs.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: manual-trace

### B-24 · The Instagram `gd_REPLACE` placeholder guard is unreachable
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_instagram.py:60`, `pipeline-app/pipeline_app/discovery_instagram.py:45`
- **component**: discovery
- **failure_mode**: latent
- **blast_radius**: `DATASET_ID` is the real provisioned id `gd_lk5ns7kz21pck8jpis`, so `DATASET_ID.startswith("gd_REPLACE")` is always false and the `RuntimeError` can never be raised. It is the only such guard among the four Bright Data adapters, and it reads as an active safety check that is doing nothing. Harmless in itself; it costs a reader's attention and implies a bootstrap state that no longer exists.
- **trigger**: n/a — the branch cannot execute.
- **proposed_fix**: Delete the guard, or move the same idea into a shared validation in `brightdata_job.trigger` that rejects any obviously-unprovisioned dataset id for all four adapters.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: grep-sweep

### B-25 · Unused re-exports and an unused constant
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_instagram.py:27`, `pipeline-app/pipeline_app/discovery_x.py:149`, `pipeline-app/pipeline_app/discovery_youtube.py:23`
- **component**: discovery
- **failure_mode**: latent
- **blast_radius**: `REQUEST_TIMEOUT_S` is re-exported from `brightdata_job` by the Instagram and X adapters and read by neither them nor any test (the sibling `BRIGHTDATA_API_BASE` re-exports *are* used and must stay). `discovery_youtube.USER_AGENT` is defined and never referenced — yt-dlp is never passed a `--user-agent` flag, so the string is inert while looking like it configures request identity. Facebook and LinkedIn correctly omit the timeout re-export, so the two that have it are the outliers.
- **trigger**: n/a — hygiene only.
- **proposed_fix**: Delete the two unused `REQUEST_TIMEOUT_S` re-exports and either wire `USER_AGENT` into the yt-dlp invocations or remove it.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T4
- **detected_by**: grep-sweep

---

## T5 — Orchestration, cron & exit semantics

**Scope.** This section covers the run orchestrator and its scheduling/exit surface:
`pipeline-app/pipeline_app/discovery_engine.py`, `discovery_scheduling.py`,
`discovery_records.py`, `discovery_paths.py`, `pipeline_app/routes/discovery.py`,
`pipeline-app/run_discovery_cron.py`, and `pipeline-app/scripts/setup_discovery_task.py`.
Platform adapters (`discovery_youtube.py`, `discovery_bluesky.py`, the Bright Data
adapters) belong to T4 and the email path (`discovery_notify.py`, `email_render.py`,
`discovery_digest.py`, `comment_draft.py`) belongs to T7 — where the trace crossed those
boundaries it is cited as context and handed off, not filed. Documentation-only audit; no
code was changed.

The dominant theme across these seven files: **the discovery pipeline has no failure
channel.** The run's own outcome is recorded faithfully in SQLite and in a markdown
record, but the two places a human or a machine would actually notice a problem — the
process exit code and a log file — carry no signal at all. The exit code is a compile-time
constant, and there is no log file.

### Q1 — Exit-code truth table

Every terminal state of `python run_discovery_cron.py --mode scheduled` and what Windows
Task Scheduler records in the task's *Last Run Result* column.

| # | Terminal state | Decided at | `discovery_runs.status` | Exit code TS observes |
|---|---|---|---|---|
| 1 | Not due yet today | `run_discovery_cron.py:86-87` | *(no row written)* | **0** |
| 2 | Clean run, all handles ok | `discovery_engine.py:400` | `completed` | **0** |
| 3 | One or more handles raised | `discovery_engine.py:374,400` | `completed_with_errors` | **0** |
| 4 | **Every** handle raised | `discovery_engine.py:374,400` | `completed_with_errors` | **0** |
| 5 | Every handle skipped (backfill on an unsupported platform) | `discovery_engine.py:344-355,400` | `completed` | **0** |
| 6 | Locked — another run holds the single-flight lock | `discovery_engine.py:320-327` | `locked` | **0** |
| 7 | Crash outside the per-handle loop | `discovery_engine.py:390,398` | `failed` | **0** |
| 8 | `validate_handle`: enumerate returned nothing | `discovery_engine.py:257` | `completed_with_errors` | **0** |
| 9 | `validate_handle`: adapter raised | `discovery_engine.py:281` | `failed` | **0** |
| 10 | Email not sent — no `RESEND_API_KEY` | `discovery_notify.py:60-63`, bool dropped at `run_discovery_cron.py:105` | *(run status unchanged)* | **0** |
| 11 | Email send failed — network error / non-2xx | `discovery_notify.py:76-78`, bool dropped at `run_discovery_cron.py:105` | *(unchanged)* | **0** |
| 12 | `notify()` itself raised | `run_discovery_cron.py:106-107` | *(unchanged)* | **0** |
| 13 | Uncaught exception (bad timezone string, `KeyError` on an unknown platform at `discovery_engine.py:242`, re-raised `IntegrityError` at `discovery_engine.py:313`) | *(no handler)* | may remain `running` | **1** |
| 14 | Bad CLI arguments | `argparse` `ap.error` | *(no row)* | **2** |

**Which real failures map to 0: rows 3, 4, 6, 7, 9, 10, 11, 12 — i.e. all of them except
the ones the code never anticipated.** A run in which every tracked handle failed, a run
that crashed before touching a handle, a run whose email was silently dropped for lack of
an API key, and a perfectly clean run are one and the same value to Task Scheduler.
Non-zero is reserved for programmer error and typos in argv. `main()` `return 0` at
`run_discovery_cron.py:110` is the only return statement on the success path, and
`tests/test_run_discovery_cron.py:155-169` locks the behavior in as intended for the
notification case specifically.

### Q2 — Where `completed_with_errors` is visible

Traced to each of the four possible surfaces:

- **Exit code** — no. Row 3/4 of the table above: `0`.
- **Email** — yes, and this is the only working channel. `discovery_notify.py:119` sets
  `has_issues` when status is not `completed`, and `email_render.py:104-105,157-158,211`
  renders `Run status: completed_with_errors` plus a list of errored handle labels. *This
  is T7's surface — noted, not filed.* Note the dependency: it works only if the email
  actually sends (rows 10-11), and whether it sent is itself discarded.
- **UI `/discovery/runs`** — technically present, practically invisible.
  `routes/discovery.py:112-126` lists every run newest-first with no filtering, no
  grouping and no severity ordering; `templates/discovery_runs.html:9` emits
  `class="status status-{{ status }}"`, and `static/style.css:84-90` defines no
  `.status-completed_with_errors`, `.status-completed`, `.status-failed` or
  `.status-abandoned` rule. A failed run and a clean run render as the same neutral grey
  pill, differing only in the literal word, in an unbounded flat list.
- **stderr** — every operational diagnostic goes here (`discovery_engine.py:190,223-227,
  345-347`, `discovery_notify.py:62,77,114-116`) and, under Task Scheduler, into a
  destroyed console (see B-42).

**Plainly stated:** for a scheduled run, the only signal that anything went wrong is an
email that may itself have failed to send without saying so, plus a word in an
undifferentiated web list nobody has a reason to open. This is the textbook
"looks fine but isn't" case.

### Findings

### B-40 · Scheduled run's exit code is a constant; every failure reads as success
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/run_discovery_cron.py:110`, `pipeline-app/run_discovery_cron.py:87`, `pipeline-app/pipeline_app/discovery_engine.py:398-400`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: Task Scheduler's Last Run Result — the single machine-readable health signal for the entire discovery subsystem — is hardcoded to `0x0`. A run where all 30+ handles errored, a run that crashed before enumerating anything, and a clean run are indistinguishable to any monitoring built on it. Extends SEED-6.
- **trigger**: Any scheduled run that does not raise an unhandled exception.
- **proposed_fix**: Map the run's terminal status onto a small set of documented exit codes (0 clean, 1 completed_with_errors, 2 failed, 3 locked/not-due) and return that from `main()`; keep the not-due no-op at 0.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T5
- **detected_by**: manual-trace

### B-41 · `notify()`'s success boolean is discarded — an unsent email exits 0
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/run_discovery_cron.py:103-107`, `pipeline-app/pipeline_app/discovery_notify.py:60-63`, `pipeline-app/pipeline_app/discovery_notify.py:76-78`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: `send_email` returns `False` for a missing API key, a network error, or a non-2xx Resend response, and `notify()` propagates that boolean — which the call site drops on the floor. Since the email is the *only* channel that surfaces `completed_with_errors` (see Q2), a silently unsent email removes the last remaining signal, and the operator reads the absence of mail as "quiet day."
- **trigger**: `RESEND_API_KEY` unset/rotated, or Resend unreachable, on any scheduled day.
- **proposed_fix**: Capture the boolean, print a distinguishable stderr line, and fold it into the process exit code from B-40 so a delivery failure is a non-zero result.
- **fix_cost**: S
- **depends_on_finding**: [B-40, B-42]
- **owner_task**: T5
- **detected_by**: manual-trace

### B-42 · No log file exists for scheduled runs; every stderr diagnostic is destroyed
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/scripts/setup_discovery_task.py:22-27`, `pipeline-app/pipeline_app/discovery_engine.py:190`, `pipeline-app/pipeline_app/discovery_engine.py:223-227`, `pipeline-app/pipeline_app/discovery_engine.py:345-347`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: The registered task command is `"<python>" "<script>" --mode scheduled` with no redirection and no wrapper. Task Scheduler runs it in a non-interactive session, so stdout/stderr go nowhere. Everything the system says about itself — heartbeat write failures, directory-collision warnings naming double-billed handles, backfill skip notices, the notify item-count mismatch, "no RESEND_API_KEY configured" — is written and immediately discarded. Combined with B-40, a scheduled run has literally zero externally observable output beyond DB rows.
- **trigger**: Every scheduled invocation, always.
- **proposed_fix**: Register the task through a small wrapper (`cmd /c ... >> logs\discovery.log 2>&1`) or have `run_discovery_cron.py` install a file handler under `output/discovery-runs/` when not attached to a TTY; rotate by size or day.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T5
- **detected_by**: manual-trace

### B-43 · `completed_with_errors` is visually identical to `completed` in the run history
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/discovery.py:112-126`, `pipeline-app/pipeline_app/templates/discovery_runs.html:9`, `pipeline-app/pipeline_app/static/style.css:84-90`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: `/discovery/runs` renders an unbounded, unfiltered, newest-first list of every run ever, with a status pill whose CSS class (`status-completed_with_errors`, `status-failed`, `status-abandoned`) has no stylesheet rule and therefore falls back to the same neutral grey as a clean run. The route also does no aggregation, so an operator cannot answer "have any of my last seven runs been unhealthy?" without reading every row. `list_runs` (`db.py:266-267`) has no LIMIT, so the page grows without bound.
- **trigger**: Opening `/discovery/runs` after any run that did not fully succeed.
- **proposed_fix**: Add stylesheet rules distinguishing degraded/failed/abandoned statuses, surface a health banner for the most recent run, and paginate or cap `list_runs`.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T5
- **detected_by**: manual-trace

### B-44 · schtasks registration sets no run-level, logon type, working dir, or power policy
- **severity**: S2
- **confidence**: probable
- **evidence**: `pipeline-app/scripts/setup_discovery_task.py:22-27`, `pipeline-app/scripts/setup_discovery_task.py:38`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: The command is exactly `schtasks /Create /TN … /TR … /SC MINUTE /MO 15 /F`. No `/RU`, so the task inherits the interactive-user default and does not run when that user is logged out or the workstation is locked-and-signed-out. No `/RL`, no `/IT`, no `/NP`. `schtasks`-created tasks additionally inherit Task Scheduler's default power conditions (`DisallowStartIfOnBatteries` / `StopIfGoingOnBatteries`), so on a laptop on battery the discovery run simply does not start — and neither omission produces any diagnostic, because there is no log (B-42) and no exit code (B-40). Nothing in the repo documents the "user must stay logged in" precondition.
- **trigger**: Operator signs out, or the machine runs on battery, at the configured `time_of_day`.
- **proposed_fix**: Pass explicit `/RU`/`/NP` (or register from an XML definition), set the working directory, disable the battery conditions, and enable "run task as soon as possible after a missed start"; document the chosen logon model in the script's docstring.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T5
- **detected_by**: manual-trace

### B-45 · Dry-run prints a command string that is not runnable as printed
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/scripts/setup_discovery_task.py:41-44`, `pipeline-app/scripts/setup_discovery_task.py:23`
- **component**: discovery
- **failure_mode**: loud
- **blast_radius**: `build_schtasks_command` puts the whole `"<python>" "<script>" --mode scheduled` payload into a single `/TR` list element; `" ".join(cmd)` then flattens it, so the printed line reads `… /TR "C:\…\python.exe" "C:\…\run_discovery_cron.py" --mode scheduled /SC MINUTE …`. Pasted into a shell — which is exactly what the script tells the operator this is — `/TR` binds only the python path and the script path becomes a stray argument, either erroring or registering a task that launches Python with no script. The default (no `--apply`) code path is therefore the wrong one.
- **trigger**: Operator runs the documented dry run and copies the output.
- **proposed_fix**: Print with `subprocess.list2cmdline(cmd)` (or shell-quote each element) so the emitted line is byte-for-byte executable.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T5
- **detected_by**: manual-trace

### B-46 · `/F` silently overwrites operator customization; no query, verify, or uninstall path
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/scripts/setup_discovery_task.py:26`, `pipeline-app/scripts/setup_discovery_task.py:46-53`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: Re-registration is idempotent only in the sense that `/F` destroys and recreates the task. Any fix applied by hand in the Task Scheduler GUI — the very fixes B-44 calls for — is wiped without warning on the next `--apply`, and the success message asserts registration without a confirming `schtasks /Query`. There is no companion `--remove`, so uninstalling requires knowing the task name out of band.
- **trigger**: Re-running `setup_discovery_task.py --apply` after any manual task edit.
- **proposed_fix**: Detect an existing task and require an explicit `--force` to clobber it; verify with `schtasks /Query /TN` after creation and add a `--remove` flag.
- **fix_cost**: S
- **depends_on_finding**: [B-44]
- **owner_task**: T5
- **detected_by**: manual-trace

### B-47 · Unvalidated timezone / time_of_day settings permanently wedge the scheduler
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/discovery.py:105-109`, `pipeline-app/pipeline_app/discovery_scheduling.py:12`, `pipeline-app/pipeline_app/discovery_scheduling.py:16`, `pipeline-app/pipeline_app/discovery_engine.py:415-416`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: `update_settings` writes the raw `timezone` and `time_of_day` form values with no validation (the timezone field is free text — `discovery_handles.html:66`). `ZoneInfo(timezone_name)` at `discovery_scheduling.py:12` raises `ZoneInfoNotFoundError` for a typo, and `int(part) for part in time_of_day.split(":")` at `:16` raises `ValueError` for any non-`HH:MM` string. Both raise inside `_is_due_now`, uncaught, before any run row exists — so every 15-minute wake for the rest of time dies with a traceback into a destroyed console (B-42), the UI happily shows the saved settings, and discovery stops forever with no email, no run row, and no visible symptom other than mail that stops arriving.
- **trigger**: Operator saves a mistyped timezone (e.g. `America/Chicgo`) or a non-`HH:MM` time on the settings form.
- **proposed_fix**: Validate the timezone against `zoneinfo.available_timezones()` and the time against a strict `HH:MM` parse in the route, returning 400 on failure; additionally wrap `_is_due_now` so a bad stored value degrades to a loud error rather than a permanent silent outage.
- **fix_cost**: S
- **depends_on_finding**: [B-42]
- **owner_task**: T5
- **detected_by**: manual-trace

### B-48 · Changing the timezone setting can fire a second run the same day
- **severity**: S3
- **confidence**: probable
- **evidence**: `pipeline-app/pipeline_app/discovery_scheduling.py:12-17`, `pipeline-app/pipeline_app/discovery_engine.py:408-417`, `pipeline-app/pipeline_app/routes/discovery.py:105-109`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: `last_scheduled_run_date` is a bare local calendar date computed under whatever timezone was configured at write time, and `is_due` compares it against the local date under whatever timezone is configured at read time. Changing the setting in either direction can make `today` differ from the stored string while the same UTC day is still in progress; if local wall-clock is already past `time_of_day`, a full second run fires — a duplicate billable Bright Data pass for every Bright Data handle. (The DST transitions themselves are safe: `is_due` uses `>=`, so a spring-forward that skips over `time_of_day` still fires later that day, and a fall-back repeat is absorbed by the date guard.)
- **trigger**: Operator edits the timezone on `/discovery/handles` after that day's scheduled run has completed.
- **proposed_fix**: Store the watermark as the run's UTC instant (or as date + the timezone it was computed under) and compare instants rather than naked date strings; treat a timezone change as invalidating the watermark deliberately rather than accidentally.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T5
- **detected_by**: manual-trace

### B-49 · Any run longer than 15 minutes manufactures a `locked` row and md file per wake
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_engine.py:408-417`, `pipeline-app/pipeline_app/discovery_engine.py:318-327`, `pipeline-app/scripts/setup_discovery_task.py:26`
- **component**: discovery
- **failure_mode**: latent
- **blast_radius**: `last_scheduled_run_date` is written only after the run finishes (`:417`), so while a run is in flight `is_due` keeps returning True. The 15-minute trigger therefore spawns a fresh cron process every 15 minutes for the duration of a long run; each loses the single-flight lock and writes a `locked` `discovery_runs` row plus a `locked` markdown file under `output/discovery-runs/`. A 90-minute Bright Data run leaves five junk rows and five junk files, drowning the real result in the (already undifferentiated, unpaginated) run history of B-43.
- **trigger**: Any run whose wall-clock duration exceeds 15 minutes — likely with a dozen-plus Bright Data handles.
- **proposed_fix**: Have the scheduled path check for an active `running` row before evaluating `is_due` and exit quietly, or mark the day's watermark optimistically at run start and roll it back on failure; either way stop persisting a record for a no-op lock loss.
- **fix_cost**: S
- **depends_on_finding**: [B-43]
- **owner_task**: T5
- **detected_by**: manual-trace

### B-50 · Sleep/hibernate or a wedged heartbeat lets a live run be reclaimed — two concurrent runs
- **severity**: S1
- **confidence**: probable
- **evidence**: `pipeline-app/pipeline_app/discovery_engine.py:299-300`, `pipeline-app/pipeline_app/discovery_engine.py:180-190`, `pipeline-app/pipeline_app/db.py:237-251`, `pipeline-app/pipeline_app/db.py:254-259`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: The single-flight guarantee rests entirely on the heartbeat thread writing within 600s. Two realistic ways it stops without the process dying: (a) the machine sleeps/hibernates mid-run — a lid close on a laptop freezes the heartbeat thread along with everything else, and on resume the wall clock has jumped past the stale threshold; (b) the heartbeat write keeps failing (locked DB, full disk) — `:184-190` deliberately logs and keeps ticking, so `heartbeat_at` freezes while the run continues. In either case the next wake's `reclaim_stale_runs` flips the *live* run to `abandoned`, freeing the `status='running'` partial index, and inserts its own running row: two processes now enumerate and download the same handles into the same directories, double-billing every Bright Data platform. Worse, `finish_run` (`db.py:254-259`) has no `WHERE status='running'` guard, so when the original process finishes it overwrites its own `abandoned` row back to `completed` and — if it is the scheduled trigger — writes `last_scheduled_run_date`, erasing the evidence.
- **trigger**: Machine sleeps during a run, or heartbeat writes fail for 10 consecutive minutes.
- **proposed_fix**: Make reclaim ownership-aware (record the OS PID and process start time, and only reclaim when that process is provably gone), and guard `finish_run` with a status precondition so a reclaimed run cannot silently resurrect itself.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T5
- **detected_by**: manual-trace

### B-51 · `abandoned` run records report zero work, contradicting their own DB rows
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_engine.py:140-149`, `pipeline-app/pipeline_app/discovery_records.py:40-45`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: `_write_abandoned_records_for_reclaimed_runs` passes `[]` for handle_results by design ("we don't know how far the dead process got"), so the markdown record asserts `handles_processed: 0`, `items_downloaded: 0` and the sentence "Pulled 0 new items across 0 handles." But the dead process *did* commit a `discovery_run_handles` row per completed handle, which `/discovery/runs` renders. The markdown file — the durable artifact, and the one a future reader is most likely to trust — actively contradicts the database for the exact runs where knowing what happened matters most. On a hard reboot mid-run this is the only post-mortem artifact.
- **trigger**: Hard reboot, power loss, or process kill during a run, followed by any later run's reclaim pass.
- **proposed_fix**: Read the reclaimed run's `discovery_run_handles` rows and render them into the abandoned record, marked as "partial — process died, counts are a floor."
- **fix_cost**: S
- **depends_on_finding**: [B-50]
- **owner_task**: T5
- **detected_by**: manual-trace

### B-52 · A stale `running` row is not reclaimed by the scheduled path once the day's run succeeded
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/run_discovery_cron.py:85-87`, `pipeline-app/pipeline_app/discovery_engine.py:299`
- **component**: discovery
- **failure_mode**: latent
- **blast_radius**: Reclaim happens inside `run_discovery`, which the scheduled path never reaches once `is_due` returns False. So a manual Run Now that dies hard *after* the day's scheduled run succeeded leaves a `running` row that no scheduled wake will ever clean up — the 15-minute trigger returns 0 at `:87` for the rest of the day. The UI shows a run permanently in progress until either the operator clicks Run Now again or tomorrow's scheduled run fires, which is itself misleading during exactly the window an operator would be investigating.
- **trigger**: The UI's Run Now or a backfill crashes hard after that day's scheduled run has already set the watermark.
- **proposed_fix**: Run the stale-reclaim sweep unconditionally at cron startup, before the due-check, rather than inside `run_discovery`.
- **fix_cost**: S
- **depends_on_finding**: [B-50]
- **owner_task**: T5
- **detected_by**: manual-trace

### B-53 · No wall-clock cap on a run; a hung adapter wedges discovery indefinitely
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_engine.py:339-380`, `pipeline-app/pipeline_app/discovery_engine.py:180-183`, `pipeline-app/run_discovery_cron.py:96-100`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: Nothing bounds a run's duration: no per-handle timeout, no overall deadline, no watchdog. The heartbeat proves the *thread* is alive, not that the run is making progress, so a network call that blocks forever inside one adapter holds the `status='running'` row — and therefore the single-flight lock — indefinitely. Every subsequent scheduled wake and every UI Run Now records `locked` and does nothing. Discovery stops permanently while the run history shows a run that looks healthy and in progress, and there is no exit code (B-40) or log line (B-42) to say otherwise.
- **trigger**: Any adapter HTTP call without an effective socket timeout hangs (Bright Data poll, yt-dlp subprocess).
- **proposed_fix**: Enforce a per-handle deadline in `_process_one_handle` and an overall run deadline in `run_discovery`, recording a timeout as a per-handle `error` and a terminal run status rather than an open-ended stall.
- **fix_cost**: M
- **depends_on_finding**: [B-49]
- **owner_task**: T5
- **detected_by**: manual-trace

### B-54 · A handle that raises after partial downloads is recorded as 0 items, forever
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_engine.py:373-380`, `pipeline-app/pipeline_app/discovery_engine.py:362-366`, `pipeline-app/pipeline_app/discovery_records.py:16-18`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: `process_handle` accumulates `downloaded` in a local list that is destroyed when it raises, so the except branch hardcodes `items_downloaded=0`. Three consequences, none reconciled anywhere: the DB row and the markdown record's `items_downloaded` total understate real work; `set_handle_last_seen` is skipped, so `last_seen_published_at` stays stale even though newer content is on disk; and the run record's summary line under-reports the day. The disagreement is detected but only printed to stderr (`discovery_notify.py:113-116` — **T7 owns that print**), i.e. into the void of B-42. The `fetched_at` watermark self-corrects the *email*, so email and markdown/UI permanently disagree about the same run.
- **trigger**: Any adapter that raises partway through a multi-item download (rate limit, malformed item, disk error).
- **proposed_fix**: Have `process_handle` raise an exception carrying the partial `downloaded` list (or accept an out-parameter/callback), so the except branch can record the true count and advance `last_seen_published_at`.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T5
- **detected_by**: manual-trace

### B-55 · Per-handle `error_message` is a bare `str(exc)` — no type, no traceback
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_engine.py:375`, `pipeline-app/pipeline_app/discovery_engine.py:379`, `pipeline-app/pipeline_app/discovery_engine.py:286`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: The only durable record of why a handle failed is `str(exc)`, which for whole classes of exception is unusable: a `KeyError('youtub')` from an unknown platform stores the literal `'youtub'`, an `IndexError` stores an empty string, and no exception type or frame is kept anywhere. With no log file (B-42) this string is the entire post-mortem, and it is rendered verbatim in both the UI and the markdown record.
- **trigger**: Any per-handle exception whose `__str__` is uninformative.
- **proposed_fix**: Store `f"{type(exc).__name__}: {exc}"` in the DB row and write the full traceback to the run log once that log exists.
- **fix_cost**: S
- **depends_on_finding**: [B-42]
- **owner_task**: T5
- **detected_by**: manual-trace

### B-56 · `skipped` handles are counted but never surfaced; frontmatter totals do not add up
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_records.py:14`, `pipeline-app/pipeline_app/discovery_records.py:17`, `pipeline-app/pipeline_app/discovery_records.py:34-44`, `pipeline-app/pipeline_app/discovery_engine.py:348-354`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: Confirmed as described. `status_counts` is seeded with four keys purely so the four frontmatter lookups cannot `KeyError`; `.get(status, 0) + 1` at `:17` happily admits a fifth key, `skipped`, which `discovery_engine.py:348` produces for every Bright Data handle in a backfill run. Nothing at `:34-37` or in the summary sentence at `:42-44` emits it. Result: a backfill across a mixed roster writes `handles_processed: 12` while `handles_ok + handles_no_new_content + handles_not_found + handles_errored` sums to 3, with the nine missing handles explained only in the per-handle prose list at `:46-52`. Any tooling that parses the frontmatter silently miscounts. (`abandoned` is a *run* status, never a handle status, so it cannot reach this dict — the SEED note's phrasing is slightly off there.)
- **trigger**: A backfill run with any Instagram / LinkedIn / Facebook / X handle included.
- **proposed_fix**: Emit `handles_skipped` in the frontmatter and mention it in the summary sentence; derive the key set from the observed statuses so a future status cannot silently vanish again.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T5
- **detected_by**: manual-trace

### B-57 · A transient error during validation permanently marks a handle invalid and excluded
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_engine.py:272-281`, `pipeline-app/pipeline_app/routes/discovery.py:69`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: The validate path's blanket `except Exception` sets the handle to `invalid` *and* clears `included`, with no distinction between "this account does not exist" and "the network blipped" or "Bright Data returned 503." A handle added while the VPN was up (see the repo's own known Bright Data/DNS issue) is quietly and permanently removed from every future run; nothing retries, and the only trace is a `failed` run row in the same undifferentiated list as everything else. The operator's mental model — "I added it, it's tracked" — is wrong from then on.
- **trigger**: Any transient network/vendor failure during the validate spawn that follows adding a handle.
- **proposed_fix**: Distinguish a definitive not-found from a transient failure; on transient, leave the handle `pending` with a recorded reason and allow a retry from the handles page rather than auto-excluding.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T5
- **detected_by**: manual-trace

### B-58 · Unvalidated `platform` form field kills the validate subprocess and strands the handle
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/discovery.py:39-70`, `pipeline-app/pipeline_app/discovery_engine.py:241-243`, `pipeline-app/pipeline_app/discovery_engine.py:194`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: `add_handle` accepts `platform` as an unvalidated string — the `<select>` in the template is the *only* constraint, and it is client-side. Any value not in `build_adapters()` is persisted, and then `adapters[handle_row["platform"]]` at `discovery_engine.py:242` raises `KeyError` **outside** the `try` that begins at `:244`, so it escapes `run_discovery` entirely: the fire-and-forget subprocess dies with a traceback nobody sees, no run row is written, and `set_handle_status(…, "validating")` at `:243` never executed — the handle sits at `pending` forever with no explanation. The same class of failure hits `db_mod.get_handle` returning `None` for a deleted id (`TypeError` on the subscript at `:242`). In the incremental path the equivalent lookup at `:194` is inside the per-handle try, so it degrades to a permanent per-handle `error` instead — every run, forever.
- **trigger**: A hand-crafted POST, a renamed platform key, or a stale cached form; also any handle row whose id disappears between spawn and execution.
- **proposed_fix**: Validate `platform` against the adapter registry in the route and reject with 400 before `create_handle`; move the adapter and handle lookups inside the validate path's try so an unknown platform produces a recorded `failed` run instead of a dead process.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T5
- **detected_by**: manual-trace

### B-59 · Run Now has no concurrency guard, and losing the lock race can crash instead
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/discovery.py:91-102`, `pipeline-app/pipeline_app/routes/discovery.py:17-22`, `pipeline-app/pipeline_app/discovery_engine.py:303-327`
- **component**: discovery
- **failure_mode**: latent
- **blast_radius**: Ten clicks spawn ten Python processes. The DB's partial unique index does prevent ten concurrent *downloads*, but each loser persists a `locked` run row and a `locked` markdown file, so impatient clicking is indistinguishable from B-49's junk and buries the real run. There is also a TOCTOU in the lock-loss branch: if the winner finishes between the loser's `IntegrityError` and its `get_running_run(conn) is None` check at `:312`, the loser re-raises — a legitimate lock contention surfaces as an unhandled `IntegrityError`, a dead subprocess, and no run row at all. Separately, `validate_handle` deliberately bypasses the lock, so a validate spawned during a run writes into the same output directory concurrently.
- **trigger**: Two or more Run Now clicks (or a Run Now during the scheduled run) in quick succession.
- **proposed_fix**: Check for an active `running` run in the route and disable/short-circuit Run Now with a message; make the lock-loss branch tolerant of the winner having already finished (re-attempt the insert once) rather than re-raising.
- **fix_cost**: M
- **depends_on_finding**: [B-49]
- **owner_task**: T5
- **detected_by**: manual-trace

### B-60 · Backfill date inputs are unvalidated: inverted ranges bill for guaranteed-zero results
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/discovery.py:97-102`, `pipeline-app/pipeline_app/discovery_engine.py:196-200`, `pipeline-app/pipeline_app/discovery_engine.py:95`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: `start`/`end` go from the form straight into the child's argv with no parse, no ordering check, and no bound. An **inverted range** (`start > end`) passes every check, calls `enumerate_newest_first` for every YouTube and Bluesky handle — the billable step — then filters out 100% of items at `:95`, and reports a healthy `no_new_content` for every handle: paid for, captured nothing, looks like a quiet day. A **malformed** date raises inside `_process_one_handle`'s argument evaluation, which is inside the per-handle try, so it records an identical `error` row for every handle with the message `time data '…' does not match format` instead of a 400. A value beginning with `--` is consumed by the child's `argparse` as a flag, producing exit 2 and total silence in the UI. (No shell injection: `Popen` is called with a list and no `shell=True`.)
- **trigger**: Operator swaps the two date fields, or types a malformed date, on the backfill form.
- **proposed_fix**: Parse both dates and assert `start <= end` (and a sane maximum window) in the route, returning 400; reject argv-like values before spawning.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T5
- **detected_by**: manual-trace

### B-61 · A spawned subprocess that dies is completely invisible to the user who triggered it
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/discovery.py:17-22`, `pipeline-app/pipeline_app/routes/discovery.py:69`, `pipeline-app/pipeline_app/routes/discovery.py:93`, `pipeline-app/pipeline_app/routes/discovery.py:99-101`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: Extends SEED-17. All three spawn sites redirect 303 immediately with no PID retained, no `returncode` checked, and stdout/stderr inherited from the uvicorn process rather than captured. Every failure mode above that kills the child — B-47's bad timezone, B-58's unknown platform, B-60's argparse rejection, an `ImportError`, a wrong `--repo-root` — produces the identical user experience: a clean redirect to a run history page with nothing new on it. The operator's only available inference is "it must still be running." There is also no correlation id tying the redirect to the run the child will eventually create.
- **trigger**: Any spawn whose child exits non-zero or dies before writing a run row.
- **proposed_fix**: Have the route pre-create a queued run row (or a spawn record) with the child's PID, capture the child's output to the log file from B-42, and surface "spawn failed" on `/discovery/runs` when a spawn record never transitions.
- **fix_cost**: M
- **depends_on_finding**: [B-42]
- **owner_task**: T5
- **detected_by**: manual-trace

### B-62 · No traversal risk in path construction; Windows reserved device names are a live hazard
- **severity**: S4
- **confidence**: probable
- **evidence**: `pipeline-app/pipeline_app/discovery_paths.py:13-17`, `pipeline-app/pipeline_app/discovery_paths.py:37`, `pipeline-app/pipeline_app/discovery_paths.py:77-82`
- **component**: discovery
- **failure_mode**: latent
- **blast_radius**: **Traversal is not reachable** — `slugify` strips every character outside `[\w\s-]` before any joining, so `..`, `/`, `\`, `:` and drive letters are erased and a fully-stripped handle degrades to the literal `"untitled"`; `run_record_path`'s `run_id` is machine-generated with `-` in place of `:` and is never operator-supplied. The residual hazard is Windows-specific: `\w` preserves `con`, `aux`, `nul`, `prn`, `com1`…`lpt9`, which cannot exist as directory names on Windows, so a handle slugging to one of those fails `mkdir` on every run and records a per-handle `error` with an opaque OS message. The `"untitled"` fallback is also a shared bucket — two all-punctuation handles would collide there, though `find_slug_collision` catches that at registration.
- **trigger**: Registering a handle whose slug is a Windows reserved device name.
- **proposed_fix**: Suffix reserved names (and the `untitled` fallback) with a stable disambiguator in `handle_slug`, and reject them at registration alongside the existing collision check.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T5
- **detected_by**: manual-trace

### B-63 · The directory-collision guard lives only in the add-handle route; migration bypasses it
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/discovery.py:51-64`, `pipeline-app/pipeline_app/discovery_paths.py:40-58`, `pipeline-app/scripts/migrate_handles_from_manifest.py:58`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: `find_slug_collision` is called from exactly one place — the web form. `migrate_handles_from_manifest.py` writes through `db.upsert_handle_from_migration`, which enforces only `UNIQUE(platform, handle)` and can therefore introduce exactly the collision the route refuses: two handles differing only by punctuation, billed separately every run, whichever runs second reading the other's captures and reporting the healthy `no_new_content`. The runtime warning at `discovery_engine.py:204-227` is the compensating control, and it prints to stderr — into the void of B-42.
- **trigger**: Running the manifest migration with two handles that differ only by punctuation or case.
- **proposed_fix**: Move the collision check into the DB-write layer so every insertion path enforces it, and make the migration script report rejected rows.
- **fix_cost**: S
- **depends_on_finding**: [B-42]
- **owner_task**: T5
- **detected_by**: manual-trace

### B-64 · Hygiene: mid-file imports, an unchecked Protocol signature, unconfigurable tunables, naive-datetime crash
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_engine.py:117-123`, `pipeline-app/pipeline_app/discovery_engine.py:35`, `pipeline-app/pipeline_app/discovery_engine.py:14-29`, `pipeline-app/pipeline_app/discovery_engine.py:234`, `pipeline-app/pipeline_app/db.py:240-244`
- **component**: discovery
- **failure_mode**: latent
- **blast_radius**: Four small items, none individually urgent. (1) `import sqlite3/sys/threading` and the `pipeline_app` imports sit at line 117, halfway down the module, so importing the pure walk functions drags in the DB layer and the file reads as two modules stapled together. (2) `PlatformAdapter.peek_upload_date(self, *args)` type-checks nothing — adapters can and do disagree on arity with no signal. (3) `NEW_HANDLE_LOOKBACK_DAYS=90`, `EXISTING_HANDLE_STOP_GRACE=3`, `NEW_HANDLE_UNDATED_STOP_GRACE=5`, `heartbeat_interval_s=30.0` and `stale_after_s=600` are module/default constants with no settings-table or CLI exposure, so tuning any of them is a code edit. (4) `run_discovery(now=…)` accepts a naive datetime, which makes `make_run_id`'s `%z` render empty and makes `reclaim_stale_runs` subtract a naive from an aware datetime — an uncaught `TypeError`. No production caller passes `now`, so this is latent, but the parameter is public and untyped against it.
- **trigger**: (1)-(3) on maintenance; (4) if any caller ever passes a naive `now`.
- **proposed_fix**: Hoist the imports, give `peek_upload_date` a real signature, promote the tunables to `discovery_settings` or CLI flags, and normalize `now` to aware-UTC at the top of `run_discovery`.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T5
- **detected_by**: grep-sweep

### Handoffs (not filed here)

- **T7 (email)** — `discovery_notify.py:113-116` prints the DB-vs-disk item-count mismatch caused by B-54 to stderr only; it is the sole detector of that bug and its output is destroyed by B-42. Also `discovery_notify.py:33` hardcodes `RECIPIENT`, and `notify()`'s return value being meaningful is the premise of B-41.
- **T4 (adapters)** — B-53's unbounded run duration is only exploitable because adapter HTTP calls may lack effective timeouts; worth confirming per adapter. B-48/B-49 double-runs and B-60 inverted ranges translate directly into duplicate Bright Data billing, whose per-call cost model is T4's to quantify. A skipped day (machine off across `time_of_day`) is *usually* harmless because the incremental walk is on-disk-driven rather than date-driven, but it is lossy for any adapter that only ever returns the newest N items — T4 should confirm which platforms are exposed.

---

## T6 — Roster, identity & creator coverage

**Scope.** This section audits how tracked creators are declared, identified and carried across
the six discovery platforms. Files owned and traced: `manifests/brand_sources.json`,
`manifests/thinkers.json`, `pipeline-app/scripts/migrate_handles_from_manifest.py`, the
`handles`/roster columns of `pipeline-app/pipeline_app/schema.sql`, the data model behind
`pipeline-app/pipeline_app/templates/discovery_handles.html` (presentation is T13's), and the
three roster/corpus acquisition scripts at repo root — `download_brandintel.py`,
`download_thinkers.py`, `copy_youthsports.sh` (plus `gen_thinkers_manifest.ts`, checked for the
FamilyBrain firewall). Read-only supporting traces into `db.py`, `discovery_engine.py`,
`discovery_paths.py`, `routes/discovery.py` and `run_discovery_cron.py` are cited as evidence but
filed as T6 findings only where the roster/identity data model is the root cause.

### The coverage matrix — tracked creator × platform

Creators are enumerated from `manifests/brand_sources.json:3-25`, the only file in the repo that
names social accounts. `manifests/thinkers.json` names 53 public-domain **authors** (Aristotle,
Dewey, Montessori …) — a content corpus with no handles and no platforms; it contributes no rows.
`docs/README.md:64-70` names the same 14 channels by display name and introduces no new creator.
LinkedIn is one column here but two platform values in the system (`linkedin-profile` /
`linkedin-company`, `run_discovery_cron.py:40-41`).

| # | Creator | youtube | bluesky | instagram | linkedin | facebook | x |
|---|---|---|---|---|---|---|---|
| 1 | Adam Grant (`@bigthink`, kw-filtered / `adamgrant.bsky.social`) | tracked | tracked | UNANS-A | UNANS-A | UNANS-A | UNANS-A |
| 2 | Romayroh (`@Romayroh`) | tracked | UNANS-B | UNANS-A | UNANS-A | UNANS-A | UNANS-A |
| 3 | Dan the Creator (`@danthecreatr`) | tracked | UNANS-B | UNANS-A | UNANS-A | UNANS-A | UNANS-A |
| 4 | Make Money Matt (`@makemoneymatt`) | tracked | UNANS-B | UNANS-A | UNANS-A | UNANS-A | UNANS-A |
| 5 | Kallaway (`@kallawaymarketing`) | tracked | UNANS-B | UNANS-A | UNANS-A | UNANS-A | UNANS-A |
| 6 | One Person Business (`@One-Person-Business`) | tracked | UNANS-B | UNANS-A | UNANS-A | UNANS-A | UNANS-A |
| 7 | Jenny Hoyos (`@JennyHoyos`) | tracked | UNANS-B | UNANS-A | UNANS-A | UNANS-A | UNANS-A |
| 8 | Nate Black (`@ThatNateBlack`) | tracked | UNANS-B | UNANS-A | UNANS-A | UNANS-A | UNANS-A |
| 9 | vidIQ (`@vidIQ`) | tracked | UNANS-B | UNANS-A | UNANS-A | UNANS-A | UNANS-A |
| 10 | Nick Nimmin (`@nicknimmin`) | tracked | UNANS-B | UNANS-A | UNANS-A | UNANS-A | UNANS-A |
| 11 | Roberto Blake (`@robertoblake`) | tracked | UNANS-B | UNANS-A | UNANS-A | UNANS-A | UNANS-A |
| 12 | Future Tech Pilot (`@FutureTechPilot`) | tracked | UNANS-B | UNANS-A | UNANS-A | UNANS-A | UNANS-A |
| 13 | Wade McMaster (`@WadeMcMaster`) | tracked | UNANS-B | UNANS-A | UNANS-A | UNANS-A | UNANS-A |
| 14 | Tao Prompts (`@TaoPrompts`) | tracked | UNANS-B | UNANS-A | UNANS-A | UNANS-A | UNANS-A |
| 15 | Tokenized AI (`@tokenizedai`) | tracked | UNANS-B | UNANS-A | UNANS-A | UNANS-A | UNANS-A |
| — | **Any creator not named in `manifests/`** | UNANS-C | UNANS-C | UNANS-C | UNANS-C | UNANS-C | UNANS-C |

**Cell legend — every non-`tracked` cell states exactly why the repo cannot answer:**

- **`tracked`** — a handle for this creator on this platform is declared in
  `manifests/brand_sources.json` (`:4-18` youtube, `:21` bluesky). `download_brandintel.py:394-399`
  reads those entries directly, and `migrate_handles_from_manifest.py:68-83` seeds them into the
  app's `handles` table. Caveat carried in prose, not in the cell: the app path is only tracked
  *if the operator ever ran the seeding script*, which no README or setup doc mentions (B-80).
- **`UNANS-A` — UNANSWERABLE: the platform has no declarative roster source anywhere in the repo.**
  `manifests/brand_sources.json` contains only `youtube`, `bluesky` and `rss` keys (`:3`, `:20`,
  `:23`); `migrate_handles_from_manifest.py:68,76` reads only `youtube` and `bluesky`. Instagram,
  LinkedIn, Facebook and X handles can only be created by hand through the
  `POST /discovery/handles` form (`routes/discovery.py:39-70`, form options at
  `templates/discovery_handles.html:36-40`), which writes rows to `pipeline-app/pipeline.db` — a
  runtime SQLite file that is not in version control. Nothing in the repo can say whether these
  rows exist, so the answer is neither `tracked` nor `not tracked`.
- **`UNANS-B` — UNANSWERABLE: this creator has no entry in the manifest's `bluesky` array, but
  absence there is not evidence of absence in the roster.** The `bluesky` array (`:20-22`) is a
  seed list, not the authority — `handles` rows may also be hand-added via the same form, and
  `migrate_handles_from_manifest.py` never deletes rows the manifest omits (`db.py:186-189`,
  `INSERT OR IGNORE`). The repo can only report "not seeded from the manifest", not "not tracked".
- **`UNANS-C` — UNANSWERABLE: the repo has no enumeration of the live roster at all.** Any handle
  added through the UI since the manifest was written exists only in the git-ignored DB, so the
  set of tracked creators is open-ended and cannot be bounded from source.

**Verdict.** Two of six platforms (youtube, bluesky) have a declarative roster in the repo; four
(instagram, linkedin, facebook, x) are DB-only. 15 creators are tracked on YouTube; exactly one
(Adam Grant) is tracked on a second platform, and even that pairing is not machine-knowable —
`@bigthink` and `adamgrant.bsky.social` are two unrelated rows with no shared identifier. So of
90 creator×platform cells, 16 are answerable (`tracked`) and 74 are UNANSWERABLE. The user's
question — "are we covering all social platforms for our key creators?" — **cannot be answered
from this repository today**, and would not be answerable from the DB either, because the DB has
no notion of "same creator".

**Minimum change that would make every cell answerable.** Two additions, both small:

1. **A `creators` table (or manifest key) with a stable `creator_id`, and a
   `handles.creator_id` foreign key.** One row per human/brand, many `handles` rows pointing at
   it. This is what turns "15 YouTube rows and 1 Bluesky row" into "15 creators, one of whom has
   two platforms", and it is the only change that makes a per-creator coverage report — and the
   "which platform are we missing for this creator" question — computable at all.
2. **Extend `manifests/brand_sources.json` to carry all six platform keys (declaring an empty
   array where nothing is tracked) and make the seeding script read every key the adapter registry
   knows about**, so "no instagram handles" becomes an explicit, reviewable assertion in git
   rather than an unknown. An empty declared array converts every `UNANS-A` cell to `not tracked`;
   a populated one converts it to `tracked`.

With both, every cell in this matrix resolves to `tracked` or `not tracked` from source alone,
with no runtime DB read.

### Findings

### B-70 · Four of six discovery platforms have no declarative roster source
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `manifests/brand_sources.json:3`, `manifests/brand_sources.json:20`, `manifests/brand_sources.json:23`, `pipeline-app/scripts/migrate_handles_from_manifest.py:68`, `pipeline-app/scripts/migrate_handles_from_manifest.py:76`, `pipeline-app/pipeline_app/templates/discovery_handles.html:36-40`, `pipeline-app/run_discovery_cron.py:36-47`
- **component**: discovery
- **failure_mode**: coverage-gap
- **blast_radius**: The live roster for instagram, linkedin-profile, linkedin-company, facebook and x exists only as rows in the git-ignored runtime `pipeline.db`. It cannot be reviewed in a diff, restored from the repo, reproduced on another machine, or reasoned about in an audit — and these are the four Bright Data platforms where every handle costs money per run.
- **trigger**: Any question of the form "which creators are we tracking on platform X" for X in {instagram, linkedin, facebook, x}, or any fresh checkout of the repo.
- **proposed_fix**: Extend `manifests/brand_sources.json` with a key per adapter-registry platform (empty arrays where nothing is tracked, so "we track nobody here" is an explicit committed statement) and have the seeding script iterate the registry rather than two hardcoded keys.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T6
- **detected_by**: manual-trace

### B-71 · A new platform key in brand_sources.json is silently ignored by both consumers
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/scripts/migrate_handles_from_manifest.py:68`, `pipeline-app/scripts/migrate_handles_from_manifest.py:76`, `pipeline-app/scripts/migrate_handles_from_manifest.py:84`, `download_brandintel.py:394-402`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: An operator who adds `"instagram": [...]` (or `linkedin-profile`, `facebook`, `x`) to the manifest gets no error, no warning, and `migrated N handles` counting only the youtube+bluesky rows. Both consumers read fixed key lists, so the new roster is dropped by both and the operator believes those creators are being tracked.
- **trigger**: Adding any platform key to the manifest other than `youtube`, `bluesky` or `rss`.
- **proposed_fix**: Drive both consumers from a shared platform list, and make an unrecognized top-level manifest key a loud error rather than a no-op, so an unsupported platform fails at import time instead of vanishing.
- **fix_cost**: S
- **depends_on_finding**: [B-70]
- **owner_task**: T6
- **detected_by**: manual-trace

### B-72 · No cross-platform creator identity — handles are keyed only by (platform, handle)
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/schema.sql:29-42`, `pipeline-app/pipeline_app/schema.sql:41`, `pipeline-app/pipeline_app/discovery_paths.py:51-52`, `manifests/brand_sources.json:4`, `manifests/brand_sources.json:21`
- **component**: discovery
- **failure_mode**: coverage-gap
- **blast_radius**: `@jane` on YouTube and `@jane` on X are unrelated rows with no join key; `discovery_paths.py:51-52` states the design explicitly ("facebook/nasa and instagram/nasa are distinct"). Four consequences: (a) **dedup** is per platform+handle directory, so one creator cross-posting the same item to LinkedIn, X and Instagram is captured three times and counted three times in the daily inventory; (b) **per-creator reporting** is impossible — no query can total one creator's output across platforms; (c) **"did we miss this creator's new platform"** is unanswerable, which is precisely the user's question; (d) **spotlight fairness** — `discovery_digest.py:283-293` picks one item per day with no per-creator cap, so a prolific cross-poster occupies more of the candidate pool than a single-platform creator with no way to detect or correct it.
- **trigger**: Any tracked creator active on more than one platform; Adam Grant already is (`manifests/brand_sources.json:4` and `:21`), unlinked.
- **proposed_fix**: Add a `creators` table with a stable `creator_id` and a `handles.creator_id` foreign key, populated from a manifest that groups handles under one creator entry. Every coverage, dedup and fairness question above becomes a join.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T6
- **detected_by**: manual-trace

### B-73 · handles.platform is unconstrained free text; a typo strands the row at 'pending'
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/schema.sql:31`, `pipeline-app/pipeline_app/routes/discovery.py:41`, `pipeline-app/pipeline_app/routes/discovery.py:66-69`, `pipeline-app/pipeline_app/discovery_engine.py:242`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: `platform` is `TEXT NOT NULL` with no CHECK, no enum and no FK, and `add_handle` accepts it as an unvalidated form field. A value the adapter registry does not know (`"instgram"`, or a value posted directly to the endpoint) is stored happily; the spawned validate run then does `adapters[handle_row["platform"]]` at `discovery_engine.py:242` — **outside** the try/except that guards the rest of that branch — so it raises `KeyError` in a detached subprocess before `set_handle_status(..., "validating")` ever runs. The row is left `status='pending'`, `included=1` forever: a ghost platform that the operator sees listed as a tracked handle, that the handles page polls indefinitely for a status that will never change, and that produces a per-handle `error` row on every subsequent daily run. `status` and `cohort` are likewise unconstrained free text (`schema.sql:34`, `:37`).
- **trigger**: A mistyped or hand-posted `platform` value on `POST /discovery/handles`.
- **proposed_fix**: Constrain `platform` to the adapter-registry values (CHECK constraint or a `platforms` lookup table), reject an unknown value in `add_handle` before the row is created and before the billable validate spawn, and move the registry lookup at `discovery_engine.py:242` inside the existing try so an unknown platform fails as a recorded run rather than an uncaught subprocess crash.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T6
- **detected_by**: manual-trace

### B-74 · The platform picker is a hardcoded list decoupled from the adapter registry
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/templates/discovery_handles.html:33-41`, `pipeline-app/run_discovery_cron.py:36-47`, `pipeline-app/tests/test_run_discovery_cron.py:171-178`
- **component**: discovery
- **failure_mode**: latent
- **blast_radius**: The seven `<option>` values are the only enumeration of trackable platforms the operator ever sees, and they are duplicated by hand from `build_adapters()`. They agree today, and nothing enforces that. A newly added adapter is invisible in the UI (that platform silently becomes untrackable through the only supported entry point), and a removed adapter leaves an option that produces the B-73 ghost row. The existing test pins the adapter set only, never the template.
- **trigger**: Adding or renaming an adapter in `build_adapters()` without editing the template.
- **proposed_fix**: Render the `<select>` from the adapter registry passed into the template context, or add a test asserting the option values equal `build_adapters().keys()`.
- **fix_cost**: S
- **depends_on_finding**: [B-73]
- **owner_task**: T6
- **detected_by**: manual-trace

### B-75 · The migration marks every seeded handle 'validated' without ever validating it
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/scripts/migrate_handles_from_manifest.py:58-61`, `pipeline-app/pipeline_app/routes/discovery.py:69`, `pipeline-app/pipeline_app/discovery_engine.py:245-249`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: Seeded rows are written with `status="validated", included=True` on the authority of a JSON file alone. A hand-added handle earns `validated` only by a real enumerate-and-download round trip (`discovery_engine.py:245-249`); a manifest-seeded one gets the same badge for free. A channel that has been renamed, deleted or made private since the manifest was written is presented to the operator as a verified live source, and the `status` column on the handles page stops meaning "we checked this".
- **trigger**: Running the seeding script against a manifest containing any stale handle.
- **proposed_fix**: Seed as `status='pending'` and let the normal validate path promote each row, or run the validate pass as part of the migration; either way `validated` should only ever be written by code that actually fetched something.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T6
- **detected_by**: manual-trace

### B-76 · Re-running the migration never applies manifest edits or removals
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/scripts/migrate_handles_from_manifest.py:1-8`, `pipeline-app/scripts/migrate_handles_from_manifest.py:58-61`, `pipeline-app/pipeline_app/db.py:186-189`, `pipeline-app/tests/test_migrate_handles.py:110-121`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: The script is re-runnable and idempotent, but only because `upsert_handle_from_migration` is `INSERT OR IGNORE` — despite the name it never updates. After the first run the manifest stops being a source of truth: correcting a `display_name`, adding or clearing a `keyword_filter`, or deleting a channel outright changes `download_brandintel.py`'s behavior and changes nothing in the app. The repo then holds one roster file describing two divergent rosters, and the divergence is invisible (the script still prints `migrated N handles`, counting rows it did not write). The existing test locks this in: a row manually set to `invalid` survives a re-run unchanged.
- **trigger**: Editing or removing any entry in `manifests/brand_sources.json` after the first seeding run.
- **proposed_fix**: Decide and document which side owns the roster. Either make the manifest authoritative (upsert changed fields, report manifest-absent rows as drift) or state in the file's own `_comment` that it is a one-time seed and the DB owns the roster thereafter.
- **fix_cost**: M
- **depends_on_finding**: [B-80]
- **owner_task**: T6
- **detected_by**: manual-trace

### B-77 · derive_cohort infers cohort from free-text notes and defaults to the out-of-scope label
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/scripts/migrate_handles_from_manifest.py:23-37`, `manifests/brand_sources.json:4-18`, `pipeline-app/pipeline_app/db.py:153-154`
- **component**: discovery
- **failure_mode**: latent
- **blast_radius**: Cohort is derived by ordered substring matching over the manifest's prose `note` field ("shorts specialist", "midjourney", "guru channel", then "teaching"/"tactics"/"monetization"). Rewording a note — or writing a new entry's note in any other style — silently reclassifies or falls through to `general-interest`, which is exactly the label this repo uses to mean "out of scope for ContentStudio". The damage is currently contained because `cohort` is never used to filter anything (only `ORDER BY` at `db.py:153-154` and display in run records), so this is mislabeling rather than misbehavior — but it makes the field untrustworthy as soon as anything starts reading it.
- **trigger**: Adding a manifest entry whose `note` does not contain one of the six magic substrings.
- **proposed_fix**: Make `cohort` an explicit field on each manifest entry rather than inferring it from prose, and keep `derive_cohort` only as a fallback for the legacy entries.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T6
- **detected_by**: manual-trace

### B-78 · The declared out-of-scope roster entry is seeded as an included daily source
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `manifests/brand_sources.json:2`, `manifests/brand_sources.json:4`, `manifests/brand_sources.json:21`, `pipeline-app/scripts/migrate_handles_from_manifest.py:58-61`, `pipeline-app/pipeline_app/db.py:151-154`
- **component**: discovery
- **failure_mode**: coverage-gap
- **blast_radius**: `@bigthink` (keyword-filtered to Adam Grant) and `adamgrant.bsky.social` are declared in the manifest's own `_comment` as a general-interest source unrelated to the corpus, and CLAUDE.md repeats that they are unused by any skill. Both are nonetheless seeded with `included=True` and are pulled by every daily discovery run, appear in the morning email inventory, and are eligible for the spotlight. The `general-interest` cohort that marks them is inert — nothing filters on it — so the only signal distinguishing an out-of-scope source from a corpus channel has no effect on what the system does.
- **trigger**: Every scheduled discovery run.
- **proposed_fix**: Either make `cohort` load-bearing (let a run or the email filter by cohort) or move the general-interest entries to a separate manifest key that the seeding script does not import. Confirmed still present and still unreferenced by any skill.
- **fix_cost**: S
- **depends_on_finding**: [B-77]
- **owner_task**: T6
- **detected_by**: grep-sweep

### B-79 · The manifest's rss key is advertised as live but the discovery path drops it
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `manifests/brand_sources.json:23-25`, `pipeline-app/scripts/migrate_handles_from_manifest.py:65-84`, `pipeline-app/run_discovery_cron.py:36-47`, `download_brandintel.py:400-402`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: The `rss` array's own `_comment` instructs the operator to "Add feed URLs here … to include them". That is true for `download_brandintel.py` (which has a working RSS branch) and false for everything else: the seeding script reads only `youtube` and `bluesky`, and there is no `rss` entry in the adapter registry, so a feed added there never reaches the daily discovery run, never reaches the handles table, and never reaches the morning email. The operator following the file's own instructions gets a half-tracked source with no error.
- **trigger**: Adding a feed URL to the manifest's `rss` array.
- **proposed_fix**: Correct the `_comment` to state that RSS is served only by `download_brandintel.py` and is not part of the daily discovery path, or add an RSS adapter so the instruction becomes true.
- **fix_cost**: S
- **depends_on_finding**: [B-71]
- **owner_task**: T6
- **detected_by**: manual-trace

### B-80 · The roster seeding script is undocumented outside a historical plan doc
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/README.md:6-19`, `README.md:102-113`, `pipeline-app/scripts/migrate_handles_from_manifest.py:7`, `docs/superpowers/plans/2026-07-30-discovery-cron-automation.md:3464`
- **component**: discovery
- **failure_mode**: docs-drift
- **blast_radius**: `pipeline-app/README.md`'s Setup section (venv, pip, run, test) never mentions seeding handles; the root README describes `manifests/brand_sources.json` as "the roster" without saying anything ever imports it into the app; CLAUDE.md does not mention the script. Its only non-test references are the historical implementation plan and its own docstring. A fresh checkout therefore starts the app with an **empty** `handles` table, and a discovery run over zero handles completes with status `completed` and an empty email — the failure looks exactly like a quiet day.
- **trigger**: Setting the app up on a new machine by following the README.
- **proposed_fix**: Add the seeding command to `pipeline-app/README.md`'s Setup section, and have a run over zero included handles report a distinct warning rather than a clean `completed`.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T6
- **detected_by**: grep-sweep

### B-81 · No test exercises the real manifests/brand_sources.json
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/tests/test_migrate_handles.py:34-55`, `pipeline-app/tests/test_migrate_handles.py:59-60`, `manifests/brand_sources.json:1-26`
- **component**: discovery
- **failure_mode**: latent
- **blast_radius**: Every migration test builds a synthetic manifest in `tmp_path`; the shipped file is never parsed by any suite (the root `tests/` directory has no manifest test either). The test named `test_migrate_seeds_all_16_handles_as_validated` in fact seeds three synthetic entries and asserts `count == 3`, so its name asserts a coverage guarantee it does not provide. A JSON syntax error, a renamed key, a dropped channel or a slug collision introduced into the real roster is caught by nothing until someone runs the script by hand.
- **trigger**: Any edit to `manifests/brand_sources.json`.
- **proposed_fix**: Add one test that loads the shipped manifest, asserts it parses, asserts its top-level keys are all recognized, and asserts the expected channel count — and rename the misleading test.
- **fix_cost**: S
- **depends_on_finding**: [B-71]
- **owner_task**: T6
- **detected_by**: manual-trace

### B-82 · handles.status is never downgraded after registration — a dead handle looks healthy
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/schema.sql:36-37`, `pipeline-app/pipeline_app/discovery_engine.py:243-256`, `pipeline-app/pipeline_app/discovery_engine.py:373-380`, `pipeline-app/pipeline_app/db.py:157-165`, `pipeline-app/pipeline_app/templates/discovery_handles.html:16-22`
- **component**: discovery
- **failure_mode**: silent
- **blast_radius**: `set_handle_status` is called only inside the one-shot `validate_handle` branch. A handle that validates at registration and later dies — channel deleted, account renamed, scraper permanently blocked — raises per-handle errors into `discovery_run_handles` on every run but keeps `status='validated'` and `included=1` on the handles page indefinitely. On the roster surface a permanently-broken handle is indistinguishable from a healthy one; only the stale `last_seen_published_at` hints at it. Note the intended distinction *does* work in the other direction: an operator-disabled handle (`included=0`, `status='validated'`, `discovery_handles.html:18-20`) is visibly different from one auto-excluded as invalid (`included=0`, `status='invalid'`, `discovery_engine.py:255-256`). The gap is only for handles that break after registration.
- **trigger**: A tracked account being deleted, renamed or permanently blocked after it was registered.
- **proposed_fix**: Let a run mark a handle `invalid` (or a new `failing` status) after N consecutive per-handle errors, and surface consecutive-failure count on the handles page so a dead source is visibly dead.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T6
- **detected_by**: manual-trace

### B-83 · run_all.sh aborts at the youth-sports step and never reaches the brand-intel download
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `copy_youthsports.sh:11`, `copy_youthsports.sh:14-19`, `run_all.sh:11`, `run_all.sh:27`, `run_all.sh:31`, `README.md:55-62`
- **component**: discovery
- **failure_mode**: loud
- **blast_radius**: `copy_youthsports.sh` sources from `$HERE/../corpus/raisinggoodsports` — a sibling checkout outside this repo — and correctly exits 1 with a clear message when it is absent, which it always is here. `run_all.sh` runs under `set -euo pipefail` and calls it as step 2 of 3, so the documented Quick Start (`./run_all.sh`, README:55-62, advertised as "everything") always dies before step 3 and never downloads the brand-intel corpus. The README acknowledges the script is not runnable standalone (`:37-42`) but still presents `run_all.sh` as the primary path.
- **trigger**: Running the README's Quick Start command in this repository.
- **proposed_fix**: Have `run_all.sh` treat the youth-sports step as skippable (warn and continue when the sibling source is absent) so the two genuinely runnable corpora still download, and correct the Quick Start's "everything" claim.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T6
- **detected_by**: manual-trace

### B-84 · output/raisinggoodsports-brand-definition.md is cited by both RGS skills but produced by nothing
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `.claude/skills/rgs-grounding/references/brand-voice-and-tone.md:3`, `.claude/skills/rgs-grounding/references/pairing-map.md:18`, `.claude/skills/rgs-pairing-review/SKILL.md:31`, `copy_youthsports.sh:12`, `run_all.sh:22-31`
- **component**: discovery
- **failure_mode**: coverage-gap
- **blast_radius**: Both RaisingGoodSports skills treat `output/raisinggoodsports-brand-definition.md` as a live input — `rgs-pairing-review` reads it to enumerate "the brand's 7 signature thinkers". No acquisition script in this repo writes it: `copy_youthsports.sh` writes only `output/youth-sports/raisinggoodsports/`, `download_thinkers.py` writes only `output/thinkers/anchorandwave/`, and `download_brandintel.py` writes only `output/brand-intel/`. The file has no producer, and `output/` is git-ignored and absent from a fresh checkout, so the skill's grounding step either fails or proceeds from the distilled reference alone.
- **trigger**: Invoking `rgs-pairing-review` (or `rgs-grounding`'s brand-voice step) in a checkout where `output/` was never populated by hand.
- **proposed_fix**: Either add the brand-definition file to the youth-sports copy step's inputs, or change the two skills to cite the committed `references/` distillations as the authority and mark the `output/` path as a historical provenance note.
- **fix_cost**: S
- **depends_on_finding**: [B-83]
- **owner_task**: T6
- **detected_by**: grep-sweep

### B-85 · Manifest comment says "six skills"; the repo ships eight pipeline skills
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `manifests/brand_sources.json:2`, `CLAUDE.md:70`
- **component**: discovery
- **failure_mode**: docs-drift
- **blast_radius**: The manifest's `_comment` — the only in-file explanation of what the roster is for and which entries are out of scope — states "ContentStudio's six skills do NOT use it", while CLAUDE.md and `.claude/skills/` describe eight pipeline skills plus three tool specialists. The scope claim it carries is still correct; only the count is stale, so a reader may distrust the rest of a comment that is otherwise the file's sole documentation.
- **trigger**: Reading the manifest to determine which entries are in scope.
- **proposed_fix**: Update the count in the `_comment`, or drop the count and refer to CLAUDE.md's skill table so it cannot go stale again.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T6
- **detected_by**: grep-sweep

### Answers to the remaining posed questions

**Q2 — declarative vs DB-only.** Declarative: `youtube` and `bluesky` (`manifests/brand_sources.json:3,20`). DB-only: `instagram`, `linkedin-profile`, `linkedin-company`, `facebook`, `x`. `rss` is a fourth manifest key with a consumer (`download_brandintel.py`) but no adapter and no seeding path (B-79).

**Q4 — migration script.** Re-runnable and idempotent, but only in the weak sense: `INSERT OR IGNORE` (`db.py:186-189`) means a second run inserts nothing and updates nothing, so manifest edits and deletions never propagate (B-76). It has a `--manifest`/`--db-path` CLI and calls `db.init_db` itself, so it is safe to invoke at any time. A new `instagram` key in the manifest is picked up by **nothing** — the script's two hardcoded loops (`:68`, `:76`) skip it and `download_brandintel.py:394-402` skips it too, both silently (B-71). It is effectively orphaned from operator documentation: referenced only by its own docstring, `pipeline-app/tests/test_migrate_handles.py`, and the historical implementation plan — not by either README nor CLAUDE.md (B-80).

**Q5 — handles table.** Columns: `id`, `platform`, `handle`, `display_name`, `cohort`, `keyword_filter`, `included` (INTEGER, default 1), `status` (TEXT, default `'pending'`), `added_at`, `validated_at`, `last_seen_published_at` (`schema.sql:29-42`). `platform` is free text with no CHECK or FK — a typo creates a ghost platform (B-73); `status` and `cohort` are equally unconstrained. Uniqueness on `(platform, handle)` **does** exist (`schema.sql:41`), and is reinforced by a slug-collision guard at both entry points (`routes/discovery.py:51-64`, `migrate_handles_from_manifest.py:49-57`) that catches near-duplicates the UNIQUE constraint would miss. The enable flag is `included`; a disabled handle *is* visibly different from a broken one at registration time (`included=0, status='validated'` vs `included=0, status='invalid'`), but a handle that breaks *after* registration is never downgraded and stays indistinguishable from a healthy one (B-82).

**Q6 — the three corpora.** `manifests/brand_sources.json` is the roster for `output/brand-intel/` (15 YouTube handles = the 14 corpus channels plus the general-interest `@bigthink`, and 1 Bluesky handle); the 14 names match `docs/README.md:64-70` with no drift. `manifests/thinkers.json` is a 53-work, 41-author content manifest driving `download_thinkers.py` into `output/thinkers/anchorandwave/` — no handles, no platforms, unrelated to discovery. The youth-sports corpus has **no manifest at all**: `copy_youthsports.sh` copies a sibling directory verbatim and cannot run here (B-83). `@bigthink`/`adamgrant.bsky.social` are confirmed still present (`manifests/brand_sources.json:4,21`) and confirmed still unreferenced by any skill under `.claude/skills/` — but they are not inert in the app, since the seeding script imports them as included daily sources (B-78). `output/` does not exist in this worktree, so CLAUDE.md's claim about their presence "inside `output/brand-intel/`" is not verifiable from the repo.

**Q7 — acquisition scripts.** No hardcoded roster in either downloader: `download_brandintel.py:48,387` reads the manifest and `download_thinkers.py:34,130` reads `thinkers.json`, so neither duplicates nor contradicts `manifests/`. No stubs, placeholders or TODO markers in any of the three. The one placeholder-shaped construct is the `rss` array's comment-only entry (`manifests/brand_sources.json:24`), which `download_brandintel.py:401` skips safely via its `startswith("http")` filter but which misdescribes the app path (B-79). `copy_youthsports.sh` is the outlier: no manifest, a hard dependency on a path outside the repo, and it fails loudly rather than silently.

**Q8 — gen_thinkers_manifest.ts.** Confirmed inert and confirmed firewall-clean. It imports `'../src/library/manifest'` — a relative sibling path with no FamilyBrain name, path or MCP reference anywhere in the file. There is no `package.json`, no `tsconfig.json` and no Node toolchain in this repo, so it cannot be executed; `run_all.sh` does not call it, and no Python module imports it. Its status is documented in three places (`gen_thinkers_manifest.ts:1-8`, `README.md:115-121`, `CLAUDE.md:165`), all describing it as historical documentation of how `manifests/thinkers.json` was originally produced. The committed JSON, not the script, is what `rgs-grounding` and `rgs-pairing-review` read. Same pattern in `download_thinkers.py:47` and `:39`, which mention porting `src/library/clean.ts` and matching `acquire.ts` timing — historical provenance comments, not live references. No FamilyBrain remote, submodule or path reference was found in any owned file.

---

## T7 — Digest & daily email

Scope: this section audits the four modules that turn a finished discovery run into the
morning email — `pipeline-app/pipeline_app/discovery_digest.py` (on-disk item collection and
spotlight selection), `pipeline-app/pipeline_app/email_render.py` (the pure text/HTML
renderer), `pipeline-app/pipeline_app/discovery_notify.py` (orchestration plus the Resend
call), and `pipeline-app/pipeline_app/comment_draft.py` (the tool-less `claude -p` drafting
subprocess). `pipeline-app/run_discovery_cron.py` is read but not owned (T5); where a finding's
consequence lands in the cron script it is named as a cross-reference, never filed there.
Both of CLAUDE.md's declared outbound dependencies — the Resend send and the `claude -p`
drafting turn — were verified line by line against the code. The evidence base is manual
tracing plus targeted greps across the adapter set, `discovery_engine.py`,
`scripts/setup_discovery_task.py`, the two design specs
(`docs/superpowers/specs/2026-08-01-discovery-email-summary-design.md` and
`…/2026-08-08-morning-email-social-expansion-design.md`), and the three test suites that
cover these modules.

### Q3 — Is "quiet day" distinguishable from "collection broke" in the email itself?

**Verdict: only when the breakage raised.** A run in which every handle threw is loud and
unmistakable. A run in which every handle returned zero *without raising* — or in which no
handle ran at all — is byte-for-byte identical to a genuinely quiet day, and a run whose
email never sent is indistinguishable from a day the cron never fired.

| | **Quiet day** (12 handles scanned, all `no_new_content`) | **Collection broke** (12 handles, every one raised) |
|---|---|---|
| `run_row["status"]` | `completed` (`discovery_engine.py:400`) | `completed_with_errors` (`discovery_engine.py:400`, `any_error=True`) |
| `summary["errored"]` | `[]` | all 12 display names (`discovery_notify.py:109-110`) |
| `summary["has_issues"]` | `False` (`discovery_notify.py:119`) | `True` |
| **Subject line** | `ContentStudio Discovery 2026-08-08: 0 new post(s)` | `[ISSUE] ContentStudio Discovery 2026-08-08: 0 new post(s)` |
| **Top of the plain-text body** | `No new content today.` — and that string is the *entire* body (`email_render.py:146-147`) | `Run status: completed_with_errors`<br>*(blank)*<br>`Errors:`<br>`- Betty Liu`<br>`- Adam Grant`<br>… (`email_render.py:104-106, 137-140`) |
| **Top of the HTML body** | `<p>No new content today.</p>` — entire body (`email_render.py:202-203`) | `<p><strong>Run status: completed_with_errors</strong></p>` then `<h2>Errors</h2><ul>…` (`email_render.py:157-158, 197-200`) |
| Why each handle produced nothing | not stated | not stated — `error_message` is deliberately excluded (spec §`discovery_notify.py` after the change; see B-112) |
| How many handles were checked | **not stated anywhere** (B-95) | 12, inferable only by counting the `Errors:` list |

**The middle case is the one that defeats the email.** Three distinct real failures all render
as the quiet-day column above, with no `[ISSUE]`, no `Run status:` line, and no `Errors:`
section:

1. **An adapter that swallows its own failure.** `discovery_bluesky.enumerate_newest_first`
   catches bare `Exception` and `break`s (`discovery_bluesky.py:40-43`), so a network outage or
   an AppView schema change yields `[]`, the engine records `status="no_new_content",
   items_downloaded=0` (`discovery_engine.py:365`), `any_error` stays `False`, and the run is
   `completed`. (The Bright Data adapters do raise — `brightdata_job.py:6` states the contract
   explicitly — so this is currently a Bluesky-shaped hole. Root cause belongs to T4.)
2. **An empty or mis-filtered roster.** `db.list_handles(included_only=True)` returning zero
   rows gives `handle_results == []`, therefore `items == []`, `errored == []`,
   `status == "completed"` — the same five words.
3. **Every item silently dropped at parse time.** Five separate `continue` paths in
   `collect_new_items` (`discovery_digest.py:222-235`) discard an item with no log; if they
   discard all of them the email says the day was quiet (B-99).

**And the worst case produces no email at all.** No Resend key, a 4xx, or a 15-second timeout
all end at `send_email` returning `False` (`discovery_notify.py:60-78`), which
`run_discovery_cron.py:105` discards; `main()` returns `0` and Task Scheduler records success.
A day with no email in the inbox is therefore ambiguous between: the cron never fired, the
machine was asleep, `run_discovery()` raised before `notify` was reached, the run was `locked`,
the Resend key expired, and Resend rejected the sandbox sender. There is no heartbeat and no
positive "I ran and found nothing" signal that a missing email would break (B-94).

### Findings

### B-90 · Spotlight excerpt ships the complete post body for any post under 400 chars
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/email_render.py:68-74`, `pipeline-app/pipeline_app/email_render.py:112`, `pipeline-app/pipeline_app/email_render.py:172`
- **component**: digest
- **failure_mode**: docs-drift
- **blast_radius**: CLAUDE.md states the email sends "a ~400 character excerpt" and "never a full post body." `_excerpt` returns `collapsed` unchanged when `len(collapsed) <= EXCERPT_MAX_CHARS`, so any spotlight whose primary text is under 400 characters is emailed in full, verbatim, with no ellipsis. X posts are capped at 280 characters by the platform, so **every** X spotlight is a full-body send; most Bluesky posts and a large share of Instagram/LinkedIn captions are too.
- **trigger**: Any day the spotlight lands on a post whose extracted primary text is ≤400 characters.
- **proposed_fix**: Correct the CLAUDE.md privacy paragraph to say the email sends up to ~400 characters of the spotlighted post, which for a short post is the whole post. Alternatively cap the excerpt below the shortest platform's post limit, but the honest wording change is the smaller and more truthful fix.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T7
- **detected_by**: manual-trace

### B-91 · Derived "title" is the post's first 90 characters, so every inventory row can carry the whole post
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_digest.py:70-87`, `pipeline-app/pipeline_app/discovery_digest.py:188`, `pipeline-app/pipeline_app/email_render.py:128`, `pipeline-app/pipeline_app/email_render.py:187`
- **component**: digest
- **failure_mode**: docs-drift
- **blast_radius**: Only YouTube has a real title (the body H1). For every other adapter `derive_title` returns the first non-empty body line truncated to `TITLE_MAX_CHARS = 90` at a word boundary — i.e. the opening of the post text itself. A one-line post under 90 characters therefore appears in the email *in its entirety*, and unlike the excerpt this applies to **every** item in the inventory, not just the spotlight. CLAUDE.md's "post titles … never a full post body" reads as a much narrower disclosure than what actually ships.
- **trigger**: Any captured post whose first line is the whole post and is ≤90 characters — routine on X, Bluesky, and short LinkedIn posts.
- **proposed_fix**: Restate the CLAUDE.md privacy exception to say the email carries a derived title that, for platforms with no title field, is the first ~90 characters of the post text. The mechanism itself is deliberate and documented in the design spec's normalization table; only the privacy claim is wrong.
- **fix_cost**: S
- **depends_on_finding**: [B-90]
- **owner_task**: T7
- **detected_by**: manual-trace

### B-92 · facebook and x are unranked and unlabelled, sorting the two paid sources below free Bluesky
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/email_render.py:21-30`, `pipeline-app/pipeline_app/email_render.py:43`, `pipeline-app/pipeline_app/email_render.py:78-80`
- **component**: digest
- **failure_mode**: silent
- **blast_radius**: Extends SEED-9. Both platforms are live, registered adapters (`run_discovery_cron.py:45-46`) and both are Bright Data-billed. Falling through `rank.get(p, len(rank))` puts them after every ranked platform and then sorts them alphabetically, so the rendered order is LinkedIn, LinkedIn (Company), YouTube, Instagram, Bluesky, **Facebook, X** — the two platforms the operator pays per-record for land beneath the one free source, in an email whose whole purpose is to surface what was captured. `_label` additionally title-cases, so any future hyphenated platform id renders miscased ("Linkedin Newsletter"). No test covers either platform: `tests/test_email_render.py:85-92` exercises the fallback with an invented `threads` platform, which ratifies the fallback path rather than catching the two real omissions.
- **trigger**: Every run since the Facebook and X adapters shipped.
- **proposed_fix**: Add both ids to `PLATFORM_ORDER` and `PLATFORM_LABELS`, and add a test that asserts every key of `run_discovery_cron.build_adapters()` has an explicit rank and label, so the next adapter cannot ship unranked.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T7
- **detected_by**: manual-trace

### B-93 · Every diagnostic in the email path writes to a stderr the Scheduled Task discards
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_notify.py:62`, `pipeline-app/pipeline_app/discovery_notify.py:77`, `pipeline-app/pipeline_app/discovery_notify.py:114-116`, `pipeline-app/pipeline_app/discovery_digest.py:243-245`, `pipeline-app/pipeline_app/comment_draft.py:213`, `pipeline-app/pipeline_app/comment_draft.py:283`, `pipeline-app/pipeline_app/comment_draft.py:296`, `pipeline-app/pipeline_app/comment_draft.py:301`
- **component**: digest
- **failure_mode**: silent
- **blast_radius**: Ten distinct non-fatal failure signals across the four owned modules — no Resend key, a failed send, an item-count mismatch, a URL-less item, a missing `claude` binary, a drafting timeout, a non-zero exit, unusable drafts — are all delivered by `print(..., file=sys.stderr)` and nothing else. The task registration (`scripts/setup_discovery_task.py:23-27`, T5) builds `/TR "<python>" "<cron>" --mode scheduled` with no redirection, and Windows Task Scheduler does not capture a task's stdout/stderr. Every one of these messages goes to a closed handle. The design spec leans on this channel explicitly ("visible … in the task's captured stderr"), which is not true as registered. Net effect: the email body is the only diagnostic surface that exists, which is precisely why Q3's blind spots matter.
- **trigger**: Any of the ten conditions above, on any scheduled run.
- **proposed_fix**: Redirect the task command's stdout and stderr to a rolling log file under `pipeline-app/`, or replace the `print` calls with a `logging` handler writing to that file. Cross-reference to T5 for the `/TR` change; the sinks themselves are in T7's modules.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T7
- **detected_by**: manual-trace

### B-94 · A failed send is a silent no-op — the bool is discarded and no email is the same as no run
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_notify.py:55-78`, `pipeline-app/pipeline_app/discovery_notify.py:128`, `pipeline-app/pipeline_app/discovery_notify.py:143`
- **component**: digest
- **failure_mode**: silent
- **blast_radius**: `send_email` returns `False` on all three failure paths (no key, `RequestException` including a 15s timeout, non-2xx via `raise_for_status`). `notify` propagates that bool to its own return value, and the sole call site (`run_discovery_cron.py:105`, T5) discards it; `main()` returns `0` regardless. Combined with B-93 the outcome is total silence: no email, no log, exit code 0, task history green. Because there is no heartbeat email on a quiet day either, the recipient's inbox cannot distinguish a send failure from a cron that never fired, a machine that was asleep, a `locked` run, or `run_discovery()` raising before `notify` was reached.
- **trigger**: Resend key rotated or unset, Resend returning 4xx/5xx, or the API call exceeding `REQUEST_TIMEOUT_S = 15`.
- **proposed_fix**: Either make the return value meaningful at the call site (non-zero exit or a written failure marker the operator can see), or accept the bool as decorative and delete it, and add a positive daily heartbeat so an absent email is itself an alarm.
- **fix_cost**: M
- **depends_on_finding**: [B-93]
- **owner_task**: T7
- **detected_by**: manual-trace

### B-95 · The email carries no denominator, so an empty roster reads as a quiet day
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_notify.py:119-125`, `pipeline-app/pipeline_app/email_render.py:146-147`, `pipeline-app/pipeline_app/email_render.py:202-203`
- **component**: digest
- **failure_mode**: silent
- **blast_radius**: `build_summary` returns only `run_status`, `has_issues`, `items`, and `errored`. Nothing counts how many handles were scanned, how many returned zero, or which platforms were represented, so the renderer cannot state a denominator even if it wanted to. On a zero-item clean run the entire body is the five-word string `No new content today.` — no date, no handle count, no per-platform zero rows. This is the direct mechanism behind Q3's middle column: 30 handles all quiet, 30 handles all silently broken, and a roster accidentally emptied to zero rows all produce identical bytes.
- **trigger**: Any scheduled run producing zero items with no raised handle error.
- **proposed_fix**: Add a scanned/quiet/errored handle count to the summary dict and render a one-line coverage footer on every email including the empty case, so the quiet-day body states the denominator it was quiet against.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T7
- **detected_by**: manual-trace

### B-96 · The LinkedIn absolute-priority gate is invisible to the recipient
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_digest.py:250-253`, `pipeline-app/pipeline_app/discovery_digest.py:290-292`, `pipeline-app/pipeline_app/email_render.py:108`, `pipeline-app/pipeline_app/email_render.py:164`
- **component**: digest
- **failure_mode**: docs-drift
- **blast_radius**: The gate discards every non-LinkedIn candidate whenever any LinkedIn item is eligible, so a LinkedIn post with 3 likes outranks a YouTube video with 40,000 views. It is documented in the code comment and in the 2026-08-08 design spec §`select_spotlight`, but it is absent from CLAUDE.md's description of the email, absent from `docs/`, and — most importantly — absent from the email itself. The section is headed only "TODAY'S PICK: LinkedIn" / "Today's pick: LinkedIn", which a reader will reasonably take as "the day's most-engaged post" rather than "the most-engaged LinkedIn post, whenever any LinkedIn post exists." Every day with at least one LinkedIn capture is silently a LinkedIn-only spotlight.
- **trigger**: Any run in which at least one LinkedIn item has non-empty primary text.
- **proposed_fix**: State the gate in the email's spotlight heading or subheading (one clause is enough), and record it in CLAUDE.md alongside the other stated email behaviors so it is a declared editorial policy rather than an implementation detail.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T7
- **detected_by**: manual-trace

### B-97 · On an all-zero-metric day the spotlight falls to alphabetical platform order, favouring Bluesky
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_digest.py:256-265`, `pipeline-app/pipeline_app/discovery_digest.py:268-280`, `pipeline-app/pipeline_app/discovery_bluesky.py:110-111`
- **component**: digest
- **failure_mode**: latent
- **blast_radius**: Bluesky writes no `like_count`/`comment_count` (getAuthorFeed does not surface them), so `_interactions` scores it 0 — indistinguishable from a genuinely zero-engagement post on any other platform. It can therefore win the spotlight, but only through tie-breaks. The design spec claims the all-zero case "resolves through the tie-breaks to the newest post," which is only true when the publish dates differ; when they do not (same-day captures, the normal case) `published_rank` ties and the next key is `platform` **ascending**, so `bluesky` wins by alphabet over `facebook`, `instagram`, `x`, and `youtube`. A structural, undocumented bias toward the one platform whose engagement is never measured.
- **trigger**: A non-LinkedIn day on which every eligible candidate has zero or absent likes+comments and shares a publish date.
- **proposed_fix**: Note the alphabetical fallback in the spec's all-zero paragraph, or replace the `platform` tie-break with something non-arbitrary (e.g. prefer a platform that actually reports metrics) so the deterministic key does not encode a preference nobody chose.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T7
- **detected_by**: manual-trace

### B-98 · The `upload_date` alias is absent from the stated contract; a third field name drops the date silently
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_digest.py:191`, `pipeline-app/pipeline_app/discovery_digest.py:7-18`, `pipeline-app/pipeline_app/discovery_digest.py:146-153`
- **component**: digest
- **failure_mode**: coverage-gap
- **blast_radius**: `meta.get("published") or meta.get("upload_date")` is the only per-platform special case in an otherwise deliberately generic reader, and it is documented in exactly two places a new adapter author will not read: an inline comment above the line, and the design spec's normalization table. The module docstring — which is the contract, and which CLAUDE.md reproduces — names `published` as the optional field and never mentions `upload_date`. An adapter writing a third name (`date_published`, `posted_at`, `created_at`) gets `published = None`, which is *legal* under the contract: the date is omitted from the render with no warning and `published_rank` sorts the item last in both the inventory and the spotlight tie-break. The item still appears, so nothing looks broken; it is just permanently undated and permanently deprioritised.
- **trigger**: A new adapter naming its publish-date field anything other than `published` or `upload_date`.
- **proposed_fix**: Name `upload_date` in the module docstring's contract and in CLAUDE.md's adapter contract paragraph as the one accepted alias, and state that no other name is read. Optionally warn to the log once per handle when an item has neither field.
- **fix_cost**: S
- **depends_on_finding**: [B-93]
- **owner_task**: T7
- **detected_by**: manual-trace

### B-99 · Per-item parse failures are dropped with no log, no counter, and no file identity
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_digest.py:221-240`, `pipeline-app/pipeline_app/discovery_digest.py:243-245`
- **component**: digest
- **failure_mode**: silent
- **blast_radius**: `collect_new_items` has six `continue` paths — `path.stat()` raising `OSError`, `read_text` raising `OSError`/`UnicodeDecodeError`, `yaml.YAMLError`, a non-dict `meta`, a missing or non-`str` `fetched_at`, and a `fetched_at` older than the watermark. Five of the six are entirely silent; only the missing-`url` case prints anything, and that path does not drop the item. The notify docstring's claim that "per-item parse failures are contained inside `collect_new_items`" is accurate about *containment* and silent about *observability*: a corrupt or contract-violating item is not counted, not named, and not surfaced anywhere. A file with a truncated or absent `fetched_at` is excluded from every email forever, which is the mandatory-field rule working as designed and also indistinguishable from the file not existing. The only downstream trace is the aggregate count-mismatch line (B-100), which names no file and goes to a discarded stderr (B-93).
- **trigger**: An adapter that omits `fetched_at`, an unquoted YAML timestamp, a partially-written file, or any non-UTF-8 byte in a captured post.
- **proposed_fix**: Have `collect_new_items` return or log a per-reason skip tally with the offending filenames, and surface a non-zero tally in the email body rather than only on stderr, so a contract violation announces itself the first morning instead of the first time someone audits the corpus.
- **fix_cost**: M
- **depends_on_finding**: [B-93, B-100]
- **owner_task**: T7
- **detected_by**: manual-trace

### B-100 · The item-count mismatch warning conflates one expected condition with three real defects
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_notify.py:112-117`, `pipeline-app/pipeline_app/discovery_digest.py:199-208`
- **component**: digest
- **failure_mode**: silent
- **blast_radius**: The warning fires whenever `len(found) != result["items_downloaded"]`, in either direction, with no indication of which direction or which files. It is routine and expected on the documented case — a handle that errored after partial downloads, which `discovery_engine.py:378` records as `error/0` while files exist on disk — so the signal is noise by design. The same line is also the *only* trace of three genuine defects: an item silently dropped at parse time (B-99), an adapter that never wrote `fetched_at`, and two handles whose slugs collide onto one directory so each reports the other's files (B-101). A mismatch is therefore always a symptom of something, sometimes benign and sometimes serious, and the message cannot tell them apart. It also goes only to the discarded stderr (B-93), so in practice nobody has ever seen one.
- **trigger**: Any run with an errored-partial handle, a dropped item, a slug collision, or a contract-violating adapter.
- **proposed_fix**: Split the message by direction and by whether the handle's recorded status was `error`, so the expected case is downgraded to informational and a `found < items_downloaded` on a healthy handle is escalated with the missing filenames named.
- **fix_cost**: S
- **depends_on_finding**: [B-93]
- **owner_task**: T7
- **detected_by**: manual-trace

### B-101 · Slug-colliding handles produce duplicate inventory entries and an inflated subject count
- **severity**: S3
- **confidence**: probable
- **evidence**: `pipeline-app/pipeline_app/discovery_digest.py:209`, `pipeline-app/pipeline_app/email_render.py:209`, `pipeline-app/pipeline_app/email_render.py:83-88`
- **component**: digest
- **failure_mode**: silent
- **blast_radius**: `collect_new_items` resolves its directory through `discovery_paths.handle_dir`, which is slug-based and deliberately lossy (`john.doe.5` and `johndoe5` collide). Two colliding handles in the same run therefore each glob the *same* directory and each return the *same* files, so every post appears twice in the inventory under two different display names, the subject's `total = len(summary["items"])` is doubled, and the spotlight ranking sees the same post twice at the same score. The `(platform, handle, item_id)` key stays total so nothing crashes, and the duplicate reads as two accounts posting the same thing. Root cause and the registration-time guard belong to T4/T5; the visible damage is in these two modules.
- **trigger**: Two registered handles on one platform whose `handle_slug` values are equal, both included in the same scheduled run.
- **proposed_fix**: Deduplicate `summary["items"]` on `(platform, item_id, url)` before rendering and ranking, and surface a collision warning in the email body rather than only at registration time.
- **fix_cost**: M
- **depends_on_finding**: [B-100]
- **owner_task**: T7
- **detected_by**: manual-trace

### B-102 · The drafting turn's `--disallowedTools` list is not exhaustive, so "every tool denied" overstates the guarantee
- **severity**: S3
- **confidence**: probable
- **evidence**: `pipeline-app/pipeline_app/comment_draft.py:113-122`, `pipeline-app/pipeline_app/comment_draft.py:216-223`
- **component**: digest
- **failure_mode**: latent
- **blast_radius**: Claim 2 in CLAUDE.md says the drafting turn "runs with every tool denied." What the code does is enumerate fifteen tool names, and the in-code comment states plainly that no all-tools wildcard exists and that a tool added by a future CLI release is not covered until the list is updated. Tools shipping in current Claude Code that are not on the list include at least `SlashCommand`, `ExitPlanMode`, and `AskUserQuestion`. The real containment holds — `--allowedTools` is omitted so nothing is pre-approved, `--strict-mcp-config` with no `--mcp-config` loads zero MCP servers, and a headless `-p` turn has no one to grant an approval — but that is a different and weaker statement than "every tool denied," and it is the enumeration that CLAUDE.md's wording implies. Verified positively: `--strict-mcp-config` is present, no `--mcp-config` is passed, no `--dangerously-skip-permissions`, no `--permission-mode`.
- **trigger**: A future CLI release adding a tool that is auto-approved by default, or an audit reading CLAUDE.md's claim as literal.
- **proposed_fix**: Reword CLAUDE.md to match the code's actual two-layer defense (nothing pre-approved plus an enumerated denial list), and add a test that fails when `cli_runner`'s known tool vocabulary grows beyond `DRAFTER_DISALLOWED_TOOLS`.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T7
- **detected_by**: manual-trace

### B-103 · The drafting subprocess inherits the full parent environment and all user-global Claude config
- **severity**: S4
- **confidence**: probable
- **evidence**: `pipeline-app/pipeline_app/comment_draft.py:244-266`, `pipeline-app/pipeline_app/cli_runner.py:237-240`
- **component**: digest
- **failure_mode**: latent
- **blast_radius**: `Popen` is called with no `env=` argument, so the child inherits `os.environ` wholesale — including `RESEND_API_KEY`, any Bright Data credential, and every `CLAUDE_*` variable set for the pipeline app. The sibling async path in `cli_runner.stream_claude_turn` builds an explicit `env` dict for exactly this kind of control. Separately, the empty-scratch-`cwd` reasoning is correct only for *project*-scoped discovery: the scratch directory lives under `%TEMP%`, so walking up from it reaches the user profile, and `claude` loads user-global `~/.claude/CLAUDE.md` and `~/.claude/settings.json` regardless of `cwd`. The turn is therefore not as bare as the spec's "discovers nothing above it" phrasing suggests — it discovers nothing *inside this repo*, which is what the spec literally says and what CLAUDE.md's summary loses.
- **trigger**: Every drafting call.
- **proposed_fix**: Pass an explicit minimal `env` to `Popen` (PATH, TEMP, the Anthropic credential, `PYTHONIOENCODING`) rather than inheriting, and note in the spec that user-global Claude config still applies.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T7
- **detected_by**: manual-trace

### B-104 · The drafting child's stderr is DEVNULL'd, so a persistently draft-less email cannot be diagnosed
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/comment_draft.py:258`, `pipeline-app/pipeline_app/comment_draft.py:295-302`
- **component**: digest
- **failure_mode**: silent
- **blast_radius**: An expired credential, a rate limit, a model error, a bad flag after a CLI upgrade, and a corrupt config all reduce to a single line — `comment_draft: claude exited N` — with the CLI's own explanation thrown away. The email degrades correctly (it renders `DRAFTS_UNAVAILABLE` and still sends), so the operator sees only that drafting is unavailable, every morning, with no way to learn why short of reproducing the subprocess by hand. Compounded by B-93: even that one line goes nowhere.
- **trigger**: Any non-zero exit from the drafting turn.
- **proposed_fix**: Capture the child's stderr with `stderr=subprocess.PIPE` and include its last few hundred characters in the failure log line, so the exit code arrives with its cause attached.
- **fix_cost**: S
- **depends_on_finding**: [B-93]
- **owner_task**: T7
- **detected_by**: manual-trace

### B-105 · The kill-tree result is discarded and a surviving grandchild silently leaks the scratch directory
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/comment_draft.py:245`, `pipeline-app/pipeline_app/comment_draft.py:276-290`, `pipeline-app/pipeline_app/cli_runner.py:185-193`
- **component**: digest
- **failure_mode**: silent
- **blast_radius**: On the grandchild question the design is sound: `platform_argv` wraps the npm `.cmd` shim in `cmd /c`, so `process.pid` is cmd.exe and the real `claude`/node process is a grandchild, and `taskkill /T /F /PID` walks descendants recursively rather than one generation — the grandchild is killed. Two gaps remain. First, `taskkill`'s exit status is never checked and its own failure is swallowed by a bare `except: pass`, so a kill that did not take leaves no trace; the tree walk also depends on the intermediate `cmd.exe` still being alive, since a descendant whose parent already exited is re-parented and unreachable by PID. Second, `ignore_cleanup_errors=True` on the `TemporaryDirectory` is load-bearing and correctly justified (it prevents a `WinError 32` from escaping a function that promises never to raise and costing the whole email), but it also means a scratch directory still held by a surviving process is abandoned silently — an orphaned Anthropic-billed turn plus a permanent `%TEMP%` leak, both invisible.
- **trigger**: A drafting turn exceeding `DEFAULT_TIMEOUT_S = 90`, or `communicate` raising `OSError`.
- **proposed_fix**: Check `taskkill`'s return code and log a distinct warning when the kill did not succeed, and log (not raise) when the scratch directory could not be removed, so an orphan is at least recorded.
- **fix_cost**: S
- **depends_on_finding**: [B-93]
- **owner_task**: T7
- **detected_by**: manual-trace

### B-106 · `RECIPIENT` is hardcoded with no environment override while `SENDER` has one
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_notify.py:33`, `pipeline-app/pipeline_app/discovery_notify.py:37`
- **component**: digest
- **failure_mode**: latent
- **blast_radius**: A personal address is baked into the module as a literal, in a repo that is public-shaped (skills are packaged and shipped as a Cowork plugin). The asymmetry with `SENDER` — which was explicitly given a `RESEND_FROM_ADDRESS` override "to switch senders with no code change" — is the tell that the same reasoning was simply not applied to the destination. Changing who gets the morning email, adding a second recipient, or pointing it at a test inbox all require a code edit and a commit.
- **trigger**: Any change of recipient, or any attempt to test the send path without mailing the owner.
- **proposed_fix**: Read the recipient from `RESEND_TO_ADDRESS` with the current literal as the default, mirroring `SENDER` exactly.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T7
- **detected_by**: grep-sweep

### B-107 · Production sends default to Resend's shared sandbox sender
- **severity**: S3
- **confidence**: probable
- **evidence**: `pipeline-app/pipeline_app/discovery_notify.py:34-37`, `pipeline-app/pipeline_app/discovery_notify.py:64`
- **component**: digest
- **failure_mode**: latent
- **blast_radius**: `onboarding@resend.dev` is Resend's shared onboarding address. It is intended for first-run testing, is heavily spam-filtered at the receiving end, and — the operationally significant part — will only deliver to the address that owns the Resend account. The daily email has been running on it. If `RECIPIENT` and the Resend account owner ever diverge (B-106 makes that a code edit, so it is unlikely but not impossible), every send returns a 4xx that `send_email` swallows into `False` (B-94) and nothing else. The comment correctly documents the intended escape hatch but nothing enforces or checks that it was ever taken. Secondary: `SENDER` is resolved by `os.environ.get` at **import** time, unlike `api_key()` which reads the environment per call, so the two credentials have inconsistent configuration lifetimes.
- **trigger**: Deliverability degradation, a Resend policy change on the shared sender, or any recipient change.
- **proposed_fix**: Verify a real sending domain and set `RESEND_FROM_ADDRESS`; log a one-line warning at send time when the sandbox default is still in force, so the temporary state cannot become permanent unnoticed.
- **fix_cost**: M
- **depends_on_finding**: [B-94, B-106]
- **owner_task**: T7
- **detected_by**: grep-sweep

### B-108 · The spotlight header renders in a different field order in the text and HTML parts
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/email_render.py:108-112`, `pipeline-app/pipeline_app/email_render.py:164-171`
- **component**: digest
- **failure_mode**: latent
- **blast_radius**: The plain-text part emits `display_name | metrics | published` and *then* the title; the HTML part emits the bolded title first and then `display_name · metrics · published`. Both parts carry the same data, so the parity test (`tests/test_email_render.py:159`, which compares title sets) passes either way. It is purely cosmetic, but it means the two parts of the same message read differently to a client that falls back to text, and it makes the two branches harder to keep in step as the section grows.
- **trigger**: Every email with a spotlight.
- **proposed_fix**: Align the two branches on one field order, and extend the parity test to compare the spotlight header's field sequence rather than only the set of titles.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T7
- **detected_by**: manual-trace

### B-109 · `notify` re-reads the run row `build_summary` already fetched
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_notify.py:99`, `pipeline-app/pipeline_app/discovery_notify.py:137`
- **component**: digest
- **failure_mode**: latent
- **blast_radius**: `build_summary` calls `db_mod.get_run(conn, run_row_id)` for `started_at` and `status`; `notify` then calls it again for `started_at` to compute `run_date`. Harmless against SQLite, but it means the email's subject date and the summary's status are read from two separate snapshots of the same row, which is one more thing that has to stay consistent than needs to.
- **trigger**: Every notify call.
- **proposed_fix**: Return `started_at` in the summary dict, or pass the already-fetched row down, so the row is read once.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T7
- **detected_by**: manual-trace

### B-110 · The 12,000-char cap and its `[transcript truncated]` marker apply to every platform, not just YouTube
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/comment_draft.py:88-92`, `pipeline-app/pipeline_app/comment_draft.py:158-171`
- **component**: digest
- **failure_mode**: docs-drift
- **blast_radius**: Claim 2 in CLAUDE.md reads "the spotlighted post's full text, **or** a YouTube transcript truncated to 12,000 characters," which implies non-YouTube bodies go out uncapped. The code caps `item["body"]` unconditionally and appends the literal string `[transcript truncated]` whatever the platform, so a long-form LinkedIn or Facebook post is both truncated and mislabelled as a transcript in the prompt the model reads. The direction is privacy-favourable (less leaves the machine than CLAUDE.md promises), so this is an accuracy issue rather than an exposure one. Verified alongside it: the cap is applied *after* `scrub_delimiter`, so a truncation cannot land mid-delimiter and leave an unclosable fence, and the untrusted text reaches `str.format` as an argument and never as the format string.
- **trigger**: Any spotlight whose extracted primary text exceeds 12,000 characters on a non-YouTube platform.
- **proposed_fix**: Make the marker platform-neutral (`[content truncated]`) and correct CLAUDE.md to say the body is capped at 12,000 characters on every platform.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T7
- **detected_by**: manual-trace

### B-111 · `skipped` handle results are invisible in the email
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_notify.py:105-117`, `pipeline-app/pipeline_app/email_render.py:137-140`
- **component**: digest
- **failure_mode**: latent
- **blast_radius**: `build_summary` populates `errored` from `status == "error"` only. `discovery_engine.py:348` also records `status="skipped"` for a handle whose platform has no backfill support, and that row contributes no items, no error entry, and no mention anywhere in the email — it simply does not exist as far as the recipient is concerned. Not reachable today because scheduled runs are always `mode="incremental"`, which is why this is latent rather than active; it becomes a live blind spot the moment any other code path starts recording a non-`error`, non-`ok` status.
- **trigger**: A scheduled run that ever records a handle status other than `ok`, `no_new_content`, or `error`.
- **proposed_fix**: Report any handle status that is neither `ok` nor `no_new_content` in the email, under its own heading, rather than special-casing the single value `error`.
- **fix_cost**: S
- **depends_on_finding**: [B-95]
- **owner_task**: T7
- **detected_by**: manual-trace

### B-112 · The Errors section names handles but never says why any of them failed
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_notify.py:107-110`, `pipeline-app/pipeline_app/email_render.py:137-140`, `pipeline-app/pipeline_app/email_render.py:197-200`
- **component**: digest
- **failure_mode**: silent
- **blast_radius**: The loud branch of Q3 is loud but uninformative. `error_message` is recorded in the DB (`discovery_engine.py:373`) and deliberately excluded from the email body per the design spec, so the recipient gets a bare list of display names. Given B-93 there is no other channel: stderr is discarded, and reading the reason requires opening `pipeline.db` or the run record under `output/discovery-runs/`. The practical consequence is that "an expired Bright Data token broke all six paid handles" and "one account was renamed" look identical in the inbox, differing only in list length — so the operator cannot triage from the email even in the case the email is *designed* to make visible.
- **trigger**: Any run with at least one errored handle.
- **proposed_fix**: Include a truncated first line of each handle's `error_message` beside its name, or at minimum a distinct-error-count so a single systemic cause is visually separable from many independent ones.
- **fix_cost**: S
- **depends_on_finding**: [B-93]
- **owner_task**: T7
- **detected_by**: manual-trace

### Verified clean (no finding filed)

- **HTML escaping (Q9).** Every interpolated value passes through `html.escape` with `quote=True` — `run_status`, platform labels, spotlight title, header pieces, excerpt, each draft, item display names and titles, metric strings, the featured marker, and errored handle names (`email_render.py:154, 158, 164, 170-172, 178, 181, 185-194, 199`). A title containing `<script>` or `</td>` is neutralized. The middle-dot separator is a pre-escaped entity joined into already-escaped pieces, which is the correct order and is called out in a comment. `href` values are additionally gated by `_safe_url` to `http`/`https` before escaping, so a `javascript:` value in scraped frontmatter cannot become a live anchor. Both behaviors are covered by tests.
- **Watermark comparison safety.** `discovery_engine.now_iso` and every adapter's `fetched_at` both use `datetime.now(timezone.utc).isoformat(timespec="seconds")`, producing fixed-width `+00:00`-suffixed strings, so the lexicographic `fetched_at < run_started_at` comparison at `discovery_digest.py:239` is valid and `_mtime_cutoff`'s `.timestamp()` is not silently reinterpreting a naive datetime as local time.
- **One post per day (Q2).** `notify` selects a single spotlight and calls `draft_comments` exactly once (`discovery_notify.py:131-135`), and the call site fires only on `--mode scheduled` past `is_due` (`run_discovery_cron.py:85-87, 103`).
- **Prompt injection surface (Q2).** The prompt is fed over stdin, never argv (`comment_draft.py:276`), the delimiter is scrubbed case-insensitively from both body and title before the length cap, and the template is a literal with untrusted text passed as `format` arguments.
- **Display-name-vs-handle rule (Q1).** `handle_row["display_name"] or handle_row["handle"]` is applied identically in `_build_item` (`discovery_digest.py:184`) and in the errored list (`discovery_notify.py:107`), and the raw `handle` is used only as a sort and identity key — it is never rendered on its own. CLAUDE.md's parenthetical is accurate.
- **Excerpt length (Q1).** `EXCERPT_MAX_CHARS = 400`, cut at the last word boundary with `...` appended, so the upper bound is ~403 characters. No full transcript reaches `text` or `html`: the only body-derived string in either part is the excerpt.
