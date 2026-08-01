# Discovery Email Summary — Design

**Status:** Approved, pending final user sign-off on this written spec.
**Date:** 2026-08-01
**Revision:** incorporates an Opus review pass (see "Review notes" at the bottom) — three blocking
issues (Bluesky headline correlation, a `locked`-run false-alarm email, and a fragile top-N file
selection) are resolved below; the design that follows is the corrected version, not the original.

## Context

The discovery pipeline (see `docs/superpowers/specs/2026-07-30-discovery-cron-automation-design.md`)
already runs unattended once a day at 06:00 `America/Chicago`, finds new videos across the channel
roster, and writes them to `output/brand-intel/youtube/<channel>/` plus a paired run record
(`output/discovery-runs/<run_id>.md`) and DB rows (`discovery_runs`, `discovery_run_handles`). None
of that is visible unless someone opens the app or the filesystem. This spec adds a same-morning
email so the pipeline's daily output is a push, not a pull.

Scope is deliberately narrow: which channels posted, and a headline (the video title) for each new
piece of content. No transcripts, no descriptions, no view counts/durations/metadata — a summary
readable on a phone in ten seconds.

## Goals

1. Every day the scheduled run actually executes, send exactly one email summarizing it — whether
   or not anything new was found.
2. The email is scannable in seconds: channel names, one headline line per new video, grouped by
   channel.
3. A run that errored (any handle `error`, or overall `status` not `completed`) is visibly flagged
   in the same email — not a separate alert, not silence.
4. The discovery engine stays completely unaware of notifications — sending is bolted on after the
   fact, reading only data the engine already persists.
5. A failure to send never affects the recorded run status or the cron script's exit code.
6. Record, explicitly, the one new external-network dependency this introduces against this
   project's "local only" rule.

## Non-goals

- No email for manual "Run Now" or backfill runs — those are runs the user just triggered
  themselves and is already watching.
- No email for a `locked` scheduled wake (the single-flight lock was already held by another run) —
  see "Locked-run gating" below for why, and why this doesn't violate Goal 1.
- No AI-generated summaries of transcripts — the raw video title is the headline, full stop.
- No per-video headline for Bluesky handles in this iteration — see "Bluesky scope" below. Bluesky
  posts are written with no YAML frontmatter and no real title (`discovery_bluesky.py`'s
  `download_item` writes a bare `# bluesky post {rkey}` H1), so the YouTube-only headline mechanism
  below doesn't apply to them at all; teaching it to would mean changing `discovery_bluesky.py`'s
  output format, which is out of scope for a notification feature.
- No HTML email design system, tracking pixels, or unsubscribe machinery — this is a one-recipient,
  fixed-destination personal notification, not a marketing send.
- No retry/queue for failed sends — a send failure is logged and dropped; tomorrow's run sends its
  own email regardless of whether yesterday's succeeded.
- No new settings-table configuration (recipient, sender, provider) — these are personal, effectively
  static values and belong as module constants / env vars, not UI-editable DB state.

## Architecture

One new module, `pipeline_app/discovery_notify.py`, with no dependency on `discovery_engine.py` and
no changes to it. It is invoked from `run_discovery_cron.py` **after** `run_discovery()` returns,
and only when `args.mode == "scheduled"` **and** the run actually executed (see "Locked-run gating"
below for the precise condition — the 95-of-96 no-op wakes never reach this code at all, since they
return from `_is_due_now` before `run_discovery()` is even called).

```python
# run_discovery_cron.py — add `import sys` at the top; import the module (not the
# function) so tests can monkeypatch `discovery_notify.notify` the same way the
# existing suite patches other cron collaborators.
from pipeline_app import discovery_notify
...
if args.mode == "scheduled" and result["status"] != "locked":
    try:
        discovery_notify.notify(conn, repo_root, result["run_row_id"])
    except Exception as exc:  # noqa: BLE001 - notification must never affect run status/exit code
        print(f"discovery notification failed: {exc}", file=sys.stderr)
```

### Locked-run gating

A scheduled wake that loses the single-flight lock (e.g. a manual "Run Now" still executing at
06:00) gets `result["status"] == "locked"` back from `run_discovery` (`discovery_engine.py:292`) —
critically, that return happens **before** `set_last_scheduled_run_date` is called
(`discovery_engine.py:360`), so `last_scheduled_run_date` is left unchanged and `_is_due_now` stays
true for every subsequent 15-minute wake that day. Gating only on `args.mode == "scheduled"` would
therefore fire a `notify()` call — with zero `discovery_run_handles` rows to summarize — on *every*
wake for the rest of the day, each one rendering as a misleading `[ISSUE] 0 new video(s)` / "No new
content today." email. The explicit `result["status"] != "locked"` check above prevents this: a
locked wake did no work and stays silent, and the run that's actually holding the lock (whichever
one that is) is the one that will send an email when it finishes.

### `discovery_notify.py`

Three functions, each independently testable:

- **`build_summary(conn, repo_root, run_row_id) -> dict`**
  Reads `discovery_runs` (via `db.get_run`) for `status` and `started_at`, and
  `discovery_run_handles` (via `db.list_run_handle_results`) joined against `handles` (via
  `db.get_handle`) for `display_name`/`platform`/`handle`. Handles with `status == "error"`
  contribute to an `errored` list, labeled `display_name or handle` (`handles.display_name` is
  nullable — `error_message` itself is not included in the email body, name only).

  **Headline selection (YouTube handles only — see "Bluesky scope" below):** for each `youtube`
  handle row with `items_downloaded > 0`, list that handle's directory
  (`discovery_paths.handle_dir(repo_root, "youtube", handle)`) for files matching the glob
  `*__*.md` (the same convention `discovery_youtube.on_disk_ids` already uses — this also excludes
  the platform's own `_tmp/` scratch subdirectory by construction, since glob doesn't recurse).
  Parse each file's frontmatter and select every file whose `fetched_at >= run_row["started_at"]`
  (both are UTC `isoformat(timespec="seconds")` strings — the run's own start time is a correlation
  key that already exists, needs nothing new written into per-video frontmatter, and is comparable
  as plain strings). This is a **watermark selection**, not a top-N: it self-corrects when
  `items_downloaded` under-reports (e.g. a handle whose `process_handle` raised after some
  downloads had already succeeded — `discovery_engine.py:327` records `items_downloaded=0` for that
  handle even though files exist on disk) and is robust to a concurrent `validate_handle` job
  writing into the same directory with its own, unrelated `fetched_at` (that file's `fetched_at`
  reflects when *it* ran, not this run, so the watermark naturally excludes it whenever the two
  don't overlap, and if they do overlap it's really is new content, just attributed to whichever
  request downloaded it — an acceptable, rare edge case for a single-user local tool). A file with
  missing/unparseable `fetched_at` is excluded from selection entirely (not sorted-last as an
  earlier draft of this spec said) — a headline that appears only when a video's provenance is
  unambiguous. If the count of selected files disagrees with the handle's own
  `items_downloaded`, log a one-line warning to stderr (visible in the scheduled task's captured
  output) but still send the email — headline completeness for one handle is not worth silencing
  the whole run's email. Each selected file's H1 is its headline.

  **Bluesky scope:** a `bluesky` handle row with `items_downloaded > 0` contributes to `channels`
  with an empty `headlines` list and a `count` field instead — the email shows the channel name and
  how many new posts it got, with no per-post headline (see "Bluesky scope" in Non-goals).

  Returns:

  ```python
  {
      "run_status": "completed_with_errors",
      "has_issues": True,               # run_status != "completed" or errored is non-empty
      "channels": [
          {"name": "Some Channel", "headlines": ["Video Title One", "Video Title Two"], "count": 2},
          {"name": "A Bluesky Handle", "headlines": [], "count": 3},
          ...
      ],
      "errored": ["@dead-handle"],
  }
  ```

  `count` is always present (`len(headlines)` for YouTube, the raw post count for Bluesky) so
  `render_email` doesn't need to special-case platform. Channels with zero new items are omitted
  from `channels` entirely — no "nothing from this channel today" noise.

- **`render_email(summary: dict, run_date: str) -> dict`** — returns `{"subject": str, "text": str}`.
  `run_date` is the scheduled run's local calendar date (`YYYY-MM-DD`), passed in by `notify` rather
  than recomputed here, so the subject line is self-sorting in an inbox even on a day with a
  `locked`-then-retry sequence or an unusual manual+scheduled overlap.
  - Subject: `"ContentStudio Discovery {run_date}: N new video(s)"` (N = sum of every channel's
    `count`), prefixed with `"[ISSUE] "` when `has_issues` is true.
  - Body: when `has_issues` is true, the body opens with an explicit `"Run status: {run_status}"`
    line before anything else — so a `failed` run (whose body would otherwise fall through to "No
    new content today.", contradicting its own `[ISSUE]` subject) always states plainly that
    something went wrong, even when `channels`/`errored` are both empty. Then: one paragraph per
    channel (its name, then each headline as a `"- "` bullet, or `"{count} new post(s)"` for a
    Bluesky channel with no headlines); if `errored` is non-empty, a trailing `"Errors:"` section
    listing handle names; if `channels` and `errored` are both empty and `has_issues` is false, the
    body is just `"No new content today."`.
  - Plain text only (no HTML part) — matches the "ten seconds on a phone" goal and keeps
    `render_email` trivially snapshot-testable.

- **`send_email(subject: str, text: str) -> bool`**
  POSTs to Resend's `https://api.resend.com/emails` endpoint via `requests` (already a project
  dependency — no new package), with an explicit `timeout=15` on the request — `requests` has no
  default timeout, and an unbounded call would let a hung connection block the cron process
  indefinitely (harmless to the already-persisted run, but it would sit as a zombie process).
  Recipient (`brian@happydotemdr.com`) and sender (`notify@<verified-sending-domain>` — a concrete
  domain must be picked and verified in the Resend dashboard before the first live send, or Resend
  rejects the request with a 403 and no email ever arrives; this is a deployment prerequisite, not
  a placeholder, and is called out again in "Setup" below) are module constants. Returns
  `True`/`False`: `False` immediately, without attempting a request, if no API key is configured
  (see Credentials); otherwise `True`/`False` based on the response, catching and logging any
  `requests` exception (including `requests.Timeout`) rather than raising. This is the only
  function in the module that touches the network, which is what makes the "never affect run
  status" guarantee in Goal 5 possible: the caller (`notify`) wraps the whole pipeline in
  `try/except` anyway, but `send_email` itself degrades gracefully rather than throwing.

- **`notify(conn, repo_root, run_row_id) -> bool`** — thin orchestrator: `build_summary` →
  compute `run_date` from the run row's `started_at` (converted to the configured timezone via
  `db.get_settings(conn)["timezone"]`, matching how `discovery_engine.py:368` derives the local
  calendar date for `last_scheduled_run_date`) → `render_email` → `send_email`. This is the single
  function `run_discovery_cron.py` calls.

## Credentials

Same lookup pattern as `discovery_youtube_api.py`'s `api_key()`: a `RESEND_API_KEY` environment
variable checked first, falling back to a gitignored `pipeline-app/resend_api_key.txt`. No key
configured → `send_email` returns `False` immediately (logged, not raised) rather than attempting a
request that will 401. `youtube_api_key.txt`'s sibling entry lives in the **repo-root**
`.gitignore` (`pipeline-app/youtube_api_key.txt`, not a `pipeline-app/.gitignore` file, which
doesn't exist) — `pipeline-app/resend_api_key.txt` is added as a new line in that same root
`.gitignore`.

## Setup (one-time, outside this repo)

Before the first scheduled run can actually deliver an email: a Resend account, an API key (set as
`RESEND_API_KEY` in the Windows user environment the Scheduled Task inherits, or written to
`pipeline-app/resend_api_key.txt`), and a verified sending domain for the `from` address in
`send_email`. Until that's done, `notify()` degrades to a logged no-op (`send_email` returns
`False` on the 403/401), never to a crash — the feature is safe to deploy before the account exists,
it just won't deliver anything yet.

## Testing

`pipeline-app/tests/test_discovery_notify.py`, following the existing suite's conventions (no real
network calls):

- `build_summary` against a fixture SQLite DB (a `discovery_runs` row with a known `started_at` +
  several `discovery_run_handles` rows across both platforms + `handles` rows) and fixture markdown
  files written to `tmp_path` with real frontmatter — asserts: correct grouping; the
  `fetched_at >= started_at` watermark selection (including a file with `fetched_at` *before* the
  run's `started_at` being correctly excluded, e.g. left over from a prior run's same handle);
  Bluesky handles producing `headlines: []` with a populated `count`; a file with missing/malformed
  `fetched_at` being excluded rather than raising; omission of zero-item channels; `errored`
  population from `status == "error"` rows using `display_name or handle`; and the
  selected-file-count-vs-`items_downloaded` mismatch producing a logged warning without raising.
- `render_email` against hand-built `summary` dicts — asserts subject `[ISSUE]` prefixing and date
  inclusion, headline vs. Bluesky-count bullet formatting, the "Run status: …" opening line when
  `has_issues` is true (including the all-empty `failed`-run case), and the "No new content today."
  empty-body case.
- `send_email` with `requests.post` monkeypatched to a fake that records the call and returns a
  canned response/raises — asserts the request payload (to/from/subject/text), the `timeout=15`
  kwarg, that an exception from the fake (including a simulated `requests.Timeout`) is caught and
  produces `False` not a raised exception, and — with `monkeypatch.delenv("RESEND_API_KEY")` and no
  key file present — that no request is attempted at all and `False` is returned.
- `notify` with `build_summary`/`render_email`/`send_email` all monkeypatched — asserts the
  orchestration order (including the `run_date` computation feeding into `render_email`) and that
  `notify` itself never raises even if a lower-level function does (belt-and-suspenders on top of
  `run_discovery_cron.py`'s own `try/except`).
- A `run_discovery_cron.py`-level test (extending the existing CLI test coverage,
  `monkeypatch.setattr(cron_module, "discovery_notify", fake_module)` in the style
  `tests/test_run_discovery_cron.py` already uses for its other collaborators) asserting
  `discovery_notify.notify` is called for `--mode scheduled` when due and `result["status"]` isn't
  `"locked"`, and is **not** called for `--mode incremental`/`--mode backfill`/
  `--mode validate_handle`, a scheduled invocation that wasn't due, or a scheduled invocation that
  came back `locked`.

## CLAUDE.md exception

Add a short paragraph to `CLAUDE.md`'s **Conventions** section:

> "Local only" governs where this project's compute, data, and corpus live — nothing about the app
> or its corpus runs in the cloud or syncs anywhere. The one deliberate exception is outbound
> notification email (`pipeline_app/discovery_notify.py`, via Resend's API): it sends channel names
> and video titles for the day's scheduled discovery run, and nothing else — never transcripts,
> descriptions, or any other corpus content.

## Error handling

- `send_email` catches all `requests` exceptions (including timeouts) internally and returns
  `False`.
- `notify` (and the call site in `run_discovery_cron.py`) both catch broadly, so a failure at any
  stage — DB read, file scan, malformed frontmatter, network — is logged to stderr and swallowed.
  `discovery_runs.status` is set entirely by `run_discovery()`, which has already returned and
  whose result is already persisted before `notify` is ever called — nothing downstream can change
  it. `run_discovery_cron.py`'s exit code is actually hardcoded to `0` on every path through `main()`
  regardless (`return 0` at the end of the function), so it was never at risk either way; the
  broad `try/except` around `notify()` exists to guarantee the *behavioral* claim (a notification
  bug can't turn into a stack trace that looks like the discovery run itself failed when read from
  the Scheduled Task's captured output), not to protect an exit code that was already safe.
- A video file with missing/unparseable `fetched_at` frontmatter is excluded from selection
  entirely (see "Headline selection" above) rather than raising — one malformed file drops only its
  own headline, not the whole handle's.
- A known, accepted gap (not addressed by this spec): if `run_discovery()` itself raises before
  returning — either a non-lock `IntegrityError` re-raised at `discovery_engine.py:278`, or an
  exception from `reclaim_stale_runs`/`insert_running_run` before `run_discovery`'s internal
  `try` block — the exception propagates out of `main()` in `run_discovery_cron.py`, `notify()` is
  never reached, and that day gets no email at all, silently. This is rare (it requires a crash
  outside the per-handle loop's own broad `except`, which already covers ordinary handle-level
  failures) and is left as a known limitation rather than solved here, since catching it well would
  mean summarizing a run that produced no `discovery_runs` row at all — a genuinely different
  problem from this spec's scope of "summarize a completed run."

## Review notes

This spec was reviewed by a second model (Opus) against the actual code before implementation.
Three blocking issues were found and are resolved in the design above, not left as follow-ups:

1. **Bluesky headline correlation was broken** — Bluesky posts carry no frontmatter and no real
   title, so the original "read the H1" mechanism would have produced garbage headlines for every
   Bluesky handle. Resolved by scoping per-video headlines to YouTube only; Bluesky channels show a
   name and count instead (see "Bluesky scope").
2. **A `locked` scheduled run would have sent a false-alarm `[ISSUE]` email, repeatedly** — because
   `last_scheduled_run_date` isn't updated on the locked path, every 15-minute wake for the rest of
   that day would have re-triggered `notify()`. Resolved by gating the call site on
   `result["status"] != "locked"` in addition to the mode check (see "Locked-run gating").
3. **"Top N files by `fetched_at`" was fragile** — it could under-select (a handle whose
   `items_downloaded` was recorded as 0 after a partial failure, even though files exist) or
   mis-select (a concurrent `validate_handle` job's own download landing in the top-N window).
   Resolved by switching to a `fetched_at >= run.started_at` watermark, which is self-correcting in
   both cases and needs no new data written anywhere.

Should-fix items also folded in: an explicit request timeout, a `"Run status: …"` line so an
`[ISSUE]`-flagged email never has a contradictory empty body, the corrected `.gitignore` location
(repo-root, not a nonexistent `pipeline-app/.gitignore`), an explicit sender-domain verification
prerequisite, `display_name or handle` fallback throughout, a date in the subject line, and
corresponding test coverage for all of the above. The one item intentionally left as a documented
gap rather than fixed is a hard crash out of `run_discovery()` itself producing a silent day with no
email — see the last bullet under "Error handling."
