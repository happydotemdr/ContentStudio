# Discovery Email Summary — Design

**Status:** Approved, pending final user sign-off on this written spec.
**Date:** 2026-08-01

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
- No AI-generated summaries of transcripts — the raw video title is the headline, full stop.
- No HTML email design system, tracking pixels, or unsubscribe machinery — this is a one-recipient,
  fixed-destination personal notification, not a marketing send.
- No retry/queue for failed sends — a send failure is logged and dropped; tomorrow's run sends its
  own email regardless of whether yesterday's succeeded.
- No new settings-table configuration (recipient, sender, provider) — these are personal, effectively
  static values and belong as module constants / env vars, not UI-editable DB state.

## Architecture

One new module, `pipeline_app/discovery_notify.py`, with no dependency on `discovery_engine.py` and
no changes to it. It is invoked from `run_discovery_cron.py` **after** `run_discovery()` returns,
and only when `args.mode == "scheduled"` **and** the due-check passed (i.e. execution actually
reached `run_discovery()` — the 95-of-96 no-op wakes never reach this code at all).

```python
# run_discovery_cron.py, after run_discovery() returns, inside the `scheduled` branch only
if args.mode == "scheduled":
    try:
        discovery_notify.notify(conn, repo_root, result["run_row_id"])
    except Exception as exc:  # noqa: BLE001 - notification must never affect run status/exit code
        print(f"discovery notification failed: {exc}", file=sys.stderr)
```

### `discovery_notify.py`

Three functions, each independently testable:

- **`build_summary(conn, repo_root, run_row_id) -> dict`**
  Reads `discovery_runs` (via `db.get_run`) for `status`, and `discovery_run_handles` (via
  `db.list_run_handle_results`) joined against `handles` (via `db.get_handle`) for
  `display_name`/`platform`/`handle`. For each handle row with `items_downloaded > 0`, lists that
  handle's directory (`discovery_paths.handle_dir(repo_root, platform, handle)`), sorts the
  markdown files there by their `fetched_at` frontmatter value descending, takes the top
  `items_downloaded` of them, and reads each file's H1 (the title) as its headline. Handles with
  `status == "error"` contribute to an `errored` list (display name only — `error_message` is not
  included in the email body). Returns:

  ```python
  {
      "run_status": "completed_with_errors",
      "has_issues": True,               # run_status != "completed" or errored is non-empty
      "channels": [
          {"name": "Some Channel", "headlines": ["Video Title One", "Video Title Two"]},
          ...
      ],
      "errored": ["@dead-handle"],
  }
  ```

  Channels with zero new items are omitted from `channels` entirely — no "nothing from this
  channel today" noise.

- **`render_email(summary: dict) -> dict`** — returns `{"subject": str, "text": str}`.
  - Subject: `"ContentStudio Discovery: N new video(s)"` (N = total headline count across
    channels), prefixed with `"[ISSUE] "` when `has_issues` is true.
  - Body: one paragraph per channel (`display_name`, then each headline as a `"- "` bullet); if
    `errored` is non-empty, a trailing `"Errors:"` section listing handle names; if `channels` is
    empty and there are no errors, the body is just `"No new content today."`.
  - Plain text only (no HTML part) — matches the "ten seconds on a phone" goal and keeps
    `render_email` trivially snapshot-testable.

- **`send_email(subject: str, text: str) -> bool`**
  POSTs to Resend's `https://api.resend.com/emails` endpoint via `requests` (already a project
  dependency — no new package). Recipient (`brian@happydotemdr.com`) and sender address are module
  constants. Returns `True`/`False`, catching and logging any `requests` exception rather than
  raising — this is the only function in the module that touches the network, which is what makes
  the "never affect run status" guarantee in Goal 5 possible: the caller (`notify`) wraps the whole
  pipeline in `try/except` anyway, but `send_email` itself degrades gracefully rather than throwing.

- **`notify(conn, repo_root, run_row_id) -> bool`** — thin orchestrator: `build_summary` →
  `render_email` → `send_email`. This is the single function `run_discovery_cron.py` calls.

## Credentials

Same lookup pattern as `discovery_youtube_api.py`'s `api_key()`: a `RESEND_API_KEY` environment
variable checked first, falling back to a gitignored `pipeline-app/resend_api_key.txt`. No key
configured → `send_email` returns `False` immediately (logged, not raised) rather than attempting a
request that will 401. `pipeline-app/.gitignore` already excludes `youtube_api_key.txt`'s sibling
pattern; `resend_api_key.txt` is added alongside it.

## Testing

`pipeline-app/tests/test_discovery_notify.py`, following the existing suite's conventions (no real
network calls):

- `build_summary` against a fixture SQLite DB (a `discovery_runs` row + several
  `discovery_run_handles` rows + `handles` rows) and fixture markdown files written to `tmp_path`
  with real frontmatter — asserts correct grouping, headline ordering (newest-`fetched_at`-first),
  omission of zero-item channels, and `errored` population from `status == "error"` rows.
- `render_email` against hand-built `summary` dicts — asserts subject `[ISSUE]` prefixing, headline
  bullet formatting, and the "No new content today." empty-body case.
- `send_email` with `requests.post` monkeypatched to a fake that records the call and returns a
  canned response/raises — asserts the request payload (to/from/subject/text) and that an exception
  from the fake is caught and produces `False`, not a raised exception.
- `notify` with `build_summary`/`render_email`/`send_email` all monkeypatched — asserts the
  orchestration order and that `notify` itself never raises even if a lower-level function does
  (belt-and-suspenders on top of `run_discovery_cron.py`'s own `try/except`).
- A `run_discovery_cron.py`-level test (extending the existing CLI test coverage) asserting
  `discovery_notify.notify` is called for `--mode scheduled` when due, and is **not** called for
  `--mode incremental`/`--mode backfill`/`--mode validate_handle`, nor for a scheduled invocation
  that wasn't due (mocking `discovery_notify.notify` itself, not the network).

## CLAUDE.md exception

Add a short paragraph to `CLAUDE.md`'s **Conventions** section:

> "Local only" governs where this project's compute, data, and corpus live — nothing about the app
> or its corpus runs in the cloud or syncs anywhere. The one deliberate exception is outbound
> notification email (`pipeline_app/discovery_notify.py`, via Resend's API): it sends channel names
> and video titles for the day's scheduled discovery run, and nothing else — never transcripts,
> descriptions, or any other corpus content.

## Error handling

- `send_email` catches all `requests` exceptions internally and returns `False`.
- `notify` (and the call site in `run_discovery_cron.py`) both catch broadly, so a failure at any
  stage — DB read, file scan, malformed frontmatter, network — is logged to stderr and swallowed.
  `run_discovery_cron.py`'s exit code and the persisted `discovery_runs.status` are set entirely by
  `run_discovery()`, before `notify` is ever called; nothing downstream can change them.
- A video file with missing/unparseable `fetched_at` frontmatter is treated as sorting last (oldest)
  rather than raising — so one malformed file doesn't drop the whole handle's headlines from the
  email.
