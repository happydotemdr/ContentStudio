# Morning Email — Social Expansion and Comment Spotlight — Design

**Status:** Approved in brainstorming, pending final user sign-off on this written spec.
**Date:** 2026-08-08
**Supersedes in part:** `docs/superpowers/specs/2026-08-01-discovery-email-summary-design.md` — that
spec's YouTube-only headline mechanism, plain-text-only body, and "no AI-generated summaries"
non-goal are all replaced here. Its locked-run gating, credential lookup, and
never-affect-run-status guarantees survive unchanged.

## Context

The daily discovery email (`pipeline_app/discovery_notify.py`) was designed when the roster was
YouTube plus a handful of Bluesky handles. Since then the engine has grown to five platforms —
`youtube`, `bluesky`, `instagram`, `linkedin-profile`, `linkedin-company`
(`run_discovery_cron.py:35`) — and more are planned within the week.

The email did not grow with it. `discovery_notify.build_summary` reads per-item titles for
`youtube` only (`discovery_notify.py:114`); every other platform falls through to a bare
`"{count} new post(s)"` line. Instagram and LinkedIn are being scraped daily and under-reported
daily. No platform gets a link to the post it is describing.

This spec does three things: makes the inventory platform-agnostic and cheap to extend, adds a
per-post link, and adds a spotlight section at the top of the body that picks one post and drafts
three comments for the user to review and copy.

### What the adapters write today

| Platform | Frontmatter | `url` | Metrics | Title source |
|---|---|---|---|---|
| `youtube` | yes | yes | `view_count`, `like_count`, `comment_count` | H1 in body |
| `instagram` | yes | yes | `like_count`, `comment_count` | none — derive from caption |
| `linkedin-profile` / `linkedin-company` | yes | yes | `like_count`, `comment_count` | none — derive from post text |
| `bluesky` | **no** — bare markdown list | in body text | none | none |

Two facts drive most of the design below: only YouTube records a view count, and Bluesky is the
one adapter that writes no frontmatter.

## Goals

1. Every platform the engine captures appears in the email with per-post titles, not a bare count.
2. A platform added later appears in the email with **no change to any email-side module**,
   provided its adapter honors a stated on-disk contract.
3. Every listed post carries a direct link to that specific post, rendered as the text
   "Click here to view".
4. The body opens with a spotlight: one selected post, its excerpt and metrics, and three drafted
   comments the user can review and copy.
5. Drafted comments never contain an em dash, are short, and are presented as drafts for review,
   not as ready-to-send copy.
6. Every new failure mode degrades to something narrower than "no email today."
7. The privacy claim in `CLAUDE.md` remains true after this change.

## Non-goals

- No change to when the email sends. Scheduled runs only, still gated on
  `args.mode == "scheduled" and result["status"] != "locked"` in `run_discovery_cron.py:97`.
- No posting, no drafting into any platform's UI, no automation of the comment itself. The email
  produces text the user copies by hand.
- No styled HTML. Minimal semantic markup only, plus a plain-text part.
- No new settings-table rows or UI configuration. Same reasoning as the 2026-08-01 spec.
- No retry or queue for a failed send, and no retry for a failed comment draft.
- No per-handle historical baselines for the ranking (see "Ranking" for why raw interactions is
  the deliberate choice).
- No change to `discovery_engine.py`. Notification remains bolted on after a finished run.

## Architecture

Four modules, replacing one. This mirrors how the discovery code is already factored —
`discovery_paths`, `discovery_records`, `discovery_scheduling` are each one small focused thing —
and it keeps the two pieces most likely to need debugging (the renderer and the disk reader)
testable with zero network and zero subprocess.

| Module | Responsibility | I/O |
|---|---|---|
| `discovery_digest.py` (new) | a run's new items off disk → normalized `Item` dicts; spotlight selection | filesystem only |
| `comment_draft.py` (new) | one `Item` → three sanitized comment drafts | `claude` subprocess only |
| `email_render.py` (new) | summary dict → `{subject, text, html}` | none — pure function |
| `discovery_notify.py` (existing, shrinks) | orchestration + `send_email` | DB read, Resend HTTP |

The call site in `run_discovery_cron.py` is unchanged.

### Rejected alternatives

- **Extend `discovery_notify.py` in place.** Smallest diff, but it puts disk parsing, ranking,
  subprocess management, and template rendering behind one `notify()` in a 500+ line file. Rejected
  on testability: a renderer that cannot be exercised without a subprocess is a renderer nobody
  tests.
- **Per-platform reader registry inside the email module.** Keeps Bluesky's current on-disk format
  and gives each platform a bespoke parser. Rejected because it makes Goal 2 false — every platform
  added next week would need a reader written and tested here before it showed up in the email.

## `discovery_digest.py`

### `collect_new_items(repo_root, handle_row, run_started_at) -> list[Item]`

Globs `discovery_paths.handle_dir(repo_root, handle_row["platform"], handle_row["handle"])` for
`*.md`. Non-recursive, which also excludes the `.md.tmp` write-temps by construction. YouTube's
`_tmp/` scratch directory is a *sibling* of the handle directories
(`output/brand-intel/youtube/_tmp`, `discovery_youtube.py:205`), not a child of one, so it is never
reached either way.

Selection is the same **watermark** the current YouTube path uses: keep files whose frontmatter
`fetched_at >= run_started_at`. Both are aware-UTC `isoformat(timespec="seconds")` strings — the
engine's at `discovery_engine.py:126,210`, each adapter's at its `download_item` — so both are
fixed-width with a `+00:00` suffix and lexicographic comparison is valid. A `fetched_at` that is
missing, non-`str` (an unquoted YAML timestamp parses to a `datetime`, which would raise `TypeError`
on comparison), or otherwise unparseable means the file is **excluded**, not sorted last: an item
appears only when its provenance is unambiguous.

### Which handles get scanned, and why both current gates are dropped

`build_summary` today skips a handle when `status == "error"` and again when `items_downloaded <= 0`
(`discovery_notify.py:107-112`). Both gates are removed; every included handle's directory is
scanned regardless of its recorded status or count.

This is not tidiness. The watermark's entire justification is that it self-corrects when
`items_downloaded` under-reports — and the case where that happens is a handle whose
`process_handle` raised *after* some downloads already succeeded, which
`discovery_engine.py:346` records as `status="error", items_downloaded=0`. That is precisely the row
the `status == "error"` gate discards. Keeping the gates and keeping the self-correction rationale
are mutually exclusive; the rationale is the one worth keeping, because the alternative is files on
disk that no email ever mentions.

**Consequence, intended:** a handle that errored mid-run appears in *both* the inventory (with the
posts it did capture) and the `Errors:` list. "This handle broke, and here are the three posts it
got before it broke" is strictly more useful than either half alone.

**Cost control.** Dropping the gates means globbing every included handle's directory every morning.
The corpus is 740 files today and 645 of those are YouTube, growing daily — parsing all of them to
find roughly ten new ones is waste that compounds for as long as this cron runs. So the watermark
gets a filesystem pre-filter: skip any file whose `st_mtime` is older than
`run_started_at - 300 seconds` without opening it. A file written during the run necessarily has an
mtime inside that window (the write-temp-then-rename preserves the temp's write time), and the
five-minute slack absorbs filesystem timestamp granularity and clock skew.

The pre-filter is **an optimization only**. Frontmatter `fetched_at` remains the sole authority for
whether an item belongs to this run, so a file that is merely touched or copied cannot enter the
email. Any file passing the mtime pre-filter is still parsed and still checked against the watermark.

If the count of selected files disagrees with the handle's `items_downloaded`, log one line to
stderr and continue — per-handle inventory completeness is not worth silencing the whole run's
email. This warning is expected, not exceptional, on an errored handle with partial downloads.

### The `Item` shape

```python
{
    "platform": "linkedin-profile",   # from handle_row
    "handle": "bettywliu",            # from handle_row
    "display_name": "Betty Liu",      # handle_row["display_name"] or handle_row["handle"]
    "item_id": "7358...",             # file stem — for YouTube this is
                                      # "{video_id}__{slug}", not the bare id
    "title": "We keep telling founders to move fast",
    "url": "https://www.linkedin.com/posts/...",
    "published": "2026-08-07",
    "views": None,
    "likes": 214,
    "comments": 37,
    "body": "We keep telling founders...",
}
```

Normalization rules, all reading fields the adapters already write:

| Field | Source | Missing → |
|---|---|---|
| `title` | body H1 if the first non-empty body line matches `# ` — **hash followed by a space** — else that first non-empty line truncated to 90 chars at a word boundary | file stem |
| `url` | frontmatter `url` | `None` — entry renders with no link, one stderr line |
| `published` | frontmatter `published`, else `upload_date` | `None` — omitted from render |
| `views` | frontmatter `view_count` | `None` — omitted from render |
| `likes` / `comments` | frontmatter `like_count` / `comment_count` | `None` — omitted from render |
| `body` | the item's primary text — see "Primary text extraction" below | `""` |

`None` and `0` are distinct throughout: `None` means the platform does not report this metric and
the render omits the segment; `0` means the platform reported zero and the render shows `0`.

**The hash-space requirement in the title rule is load-bearing.** Social posts routinely open with
a hashtag — `#MondayMotivation ...` — and a bare "starts with `#`" test would classify that as a
markdown H1, then strip the line as a heading and lose the post's first sentence. Only `# ` counts,
and only a line that was actually consumed as the title is eligible for stripping in step 1 of
primary text extraction below.

### Primary text extraction

Instagram, LinkedIn, and Bluesky bodies are the post text and nothing else. YouTube bodies are
**structured** (`discovery_youtube.py:290`): an H1 title, then a `## description` section, then a
`## transcript` section. Taking the raw body would put the literal text `## description` at the head
of every YouTube excerpt and feed section headers to the drafter as content.

The rule is structural rather than per-platform, so any future adapter writing the same sections
inherits it:

1. Strip a leading H1 line if it supplied the title.
2. If the remainder contains a `## transcript` section with non-placeholder content, `body` is that
   section's text.
3. Else if it contains a `## description` section with non-placeholder content, `body` is that
   section's text.
4. Else `body` is the whole remainder.

**Placeholder strings** written by the adapters when they have nothing —
`(no transcript available)`, `(none)`, `(empty)` — are treated as empty at every step above. A
YouTube video with no transcript therefore falls through to its description rather than producing
an excerpt reading "(no transcript available)".

An item whose `body` resolves to empty is still listed in the inventory. It is **excluded from
spotlight candidacy**: there is nothing for the drafter to read, so a comment drafted from it would
be drafted from the title alone.

### The platform contract (Goal 2)

Stated as a `discovery_digest.py` module docstring and repeated in `CLAUDE.md`:

> A discovery adapter's `download_item` must write YAML frontmatter containing at minimum `url` and
> `fetched_at`, with the post's text as the markdown body. An adapter that does this appears in the
> daily email — inventory entry, link, title, and spotlight eligibility — with no change to any
> email-side module. `like_count`, `comment_count`, `view_count`, and `published` are optional; each
> is omitted from the render when absent. `fetched_at` must be an aware-UTC
> `isoformat(timespec="seconds")` **string**, matching every existing adapter.
>
> One known exception: `download_brandintel.py`, the manual toolkit script at repo root, does not
> honor this contract and is deliberately left unmodified. Nothing it writes falls inside a
> discovery run's watermark, so it never reaches the email.

### Bluesky format change

`discovery_bluesky.download_item` currently writes a bare markdown list with a
`# bluesky post {rkey}` H1 (`discovery_bluesky.py:97-103`). It changes to write frontmatter via
`artifacts.render_frontmatter`, matching Instagram and LinkedIn:

```python
meta = {
    "post_id": rkey,
    "url": purl,
    "handle": handle,
    "author": handle,
    "published": published,
    "fetched_at": fetched_at,
}
body = full_text or "(empty)"
```

The write-temp-then-rename pattern is preserved exactly as-is.

**No legacy fallback is written.** An earlier draft of this spec specified one, for the ~25 Bluesky
files already on disk in the old bare-markdown format. That code would be unreachable: the watermark
selects only files whose `fetched_at >= run_started_at`, and every pre-change file was necessarily
fetched before the first run of the new code. A legacy parser would be dead on the day it shipped,
exercised by nothing but its own test. Those files stay on disk, remain readable by the browse UI,
and simply never appear in an email — which is already true of every file from every previous run.

**Known gap, accepted.** The Bluesky adapter's `app.bsky.feed.getAuthorFeed` call does not surface
like or comment counts, so Bluesky items always score `0` on interactions. In practice that means
Bluesky wins the spotlight only against other zero-metric items, where the `published`-descending
tie-break decides — not literally "only when nothing else was captured," since a YouTube video with
`likes: 0, views: 0` ties it. This is a data-availability limit, not a defect to fix in this spec.

**One out-of-scope writer stays non-conforming.** `download_brandintel.py:295` — the manual toolkit
script at repo root, which `CLAUDE.md` records as deliberately unmodified — still writes Bluesky
files in the old format. Harmless here, since nothing it writes falls inside a run's watermark, but
the platform contract text should note that it is a known exception rather than an oversight.

### `select_spotlight(items) -> Item | None`

Pure function over `summary["items"]`, the flattened list of every new item in the run.

0. **Eligibility.** Discard items whose `body` is empty (see "Primary text extraction"). If that
   leaves nothing, return `None` — the inventory still renders, the spotlight does not.
1. **LinkedIn gate.** If any remaining item's platform is `linkedin-profile` or `linkedin-company`,
   discard every other item. Both LinkedIn modes rank equally against each other. This is absolute: a
   LinkedIn post with 3 likes outranks a YouTube video with 40,000 views.
2. **Rank** by `interactions = (likes or 0) + (comments or 0)`, descending.
3. **Tie-break**, in order: `views or 0` descending, `published` descending (missing sorts last),
   `platform` ascending, `handle` ascending, `item_id` ascending. `handle` is required for the key
   to be **total**: `item_id` is the file stem, and two different handles on the same platform can
   hold the same stem, so platform+item_id alone is not unique. With `handle` included the key is
   unique by construction — `(platform, handle, item_id)` is a filesystem path — and the same set of
   items always yields the same spotlight.
4. **Empty input** → `None`. The spotlight section is omitted and the rest of the email renders as
   it does today.

#### Why interactions, not views

The user's requirement was "the most viewed." Only YouTube records a view count. A literal
cross-platform "most viewed" would require an invented exchange rate between a YouTube view and a
LinkedIn like, and any constant chosen for that would be fabricated rather than measured.

Likes + comments is the only metric that YouTube, Instagram, and LinkedIn all actually record, so
it is the honest common currency: the ranking is "most engaged with." YouTube's real `view_count`
is still displayed in the email and still breaks ties within YouTube. Per-handle historical
baselines (scoring a post against its own channel's median) would be more defensible still, but
require history this schema does not keep and are explicitly out of scope.

The all-zero case — every candidate lacking metrics, e.g. a Bluesky-only day — resolves through the
tie-breaks to the newest post. The spotlight still renders rather than vanishing.

## `comment_draft.py`

### `draft_comments(item, timeout_s=90) -> list[str]`

Returns exactly three sanitized drafts, or `[]`. Never raises.

**Invocation.** Reuses `cli_runner`'s `resolve_claude_binary`, `_platform_argv`, and
`_kill_process_tree` — the Windows npm `.cmd`-shim handling (`cli_runner.py:157`) and the
process-tree kill (`cli_runner.py:167`) are both empirically-derived and must not be re-invented.
Both are currently underscore-private; since this is a second in-package consumer, they are renamed
to `platform_argv` and `kill_process_tree` and their existing call sites updated. Two modules
depending on a name means it is not private.

**`subprocess.Popen` + `communicate(timeout=...)`, not `subprocess.run`.** This is a correctness
requirement, not a preference. `subprocess.run` handles its own `TimeoutExpired` by calling
`process.kill()` internally and never exposes the pid to the caller — and `cli_runner.py:167`
records, from empirical observation, that `process.kill()` on Windows terminates only the `cmd.exe`
shim and orphans the real `claude`/node descendant to run to completion. A `subprocess.run` design
and a `taskkill /T /F` guarantee are mutually exclusive. `Popen` keeps the pid, so the `except
subprocess.TimeoutExpired` branch can call `kill_process_tree(process)` and then `communicate()`
again to reap.

**`encoding="utf-8"` is mandatory on the pipe.** Python's default text encoding on Windows is
cp1252; social post text contains emoji as a matter of course, so the default would raise
`UnicodeEncodeError` writing the prompt to stdin and silently produce `[]` drafts every single day.
`cli_runner.py:238` already sets `PYTHONIOENCODING` for the same reason on the async path.

**Argv:** `claude -p --output-format json --strict-mcp-config --disallowedTools <enumerated list>`.
`--strict-mcp-config` with no `--mcp-config` loads zero MCP servers, which keeps `CLAUDE.md`'s
FamilyBrain firewall intact for this subprocess.

There is **no all-tools wildcard** for `--disallowedTools`, so the list is enumerated explicitly
(mirroring `cli_runner.PIPELINE_DISALLOWED_TOOLS`, but denying every entry rather than path-scoping
writes) and carries an in-code note that a tool added by a future CLI release would not be covered
until the list is updated. Omitting `--allowedTools` entirely already means nothing is
pre-approved, so an un-enumerated tool would still require an approval that a `-p` run cannot
obtain — the enumeration is defense in depth, not the only defense.

**`cwd` must be pinned to an empty scratch directory** (a `tempfile.TemporaryDirectory()` for the
call's lifetime). A Windows Scheduled Task inherits no meaningful working directory — the same trap
`discovery_youtube.py:126-131` already documents — and `claude` discovers `CLAUDE.md`, `.claude/`
settings, and skills by walking up from `cwd`. Launched at the repo root, every comment draft would
load ContentStudio's `CLAUDE.md` and all eight pipeline skills into a turn that needs none of them:
slower, more expensive, and liable to trigger a skill on a prompt containing scraped social copy.
An empty temp dir discovers nothing above it inside this repo.

**The prompt goes over stdin, not argv.** This is a security requirement, not a style choice.
`cli_runner.build_claude_argv`'s docstring records that on Windows the prompt reaches `cmd.exe`,
which does not honor Python's `\"` escaping — a `"` inside a scraped post would break out of quoting
and let the remainder run as shell commands. Post text is untrusted third-party content, so argv
placement would be a shell-injection hole. `claude -p` with no positional prompt reads stdin.

**Prompt input.** Platform, author/handle, title, and the body: full post text for
Instagram/LinkedIn/Bluesky, full transcript for YouTube, truncated at 12,000 characters with an
explicit `[transcript truncated]` marker appended. The cap bounds latency and cost on a long video
without silently pretending the whole transcript was read.

**Prompt injection.** The body is written by a stranger and may contain text addressed to the model.
It is wrapped in a delimited block with an instruction stating that content inside the block is
material to comment on and never instructions to follow. This reduces the risk; it does not
eliminate it. The real containment is structural: the turn has no tools, and its only output path
is three short strings the user reads before using.

**Requested output.** A JSON array of three strings, in three distinct registers — affirming,
curious question, specific-detail callback — so parsing does not depend on prose formatting.

### Parsing is two layers, not one

`claude -p --output-format json` does **not** print the model's text on stdout. It prints a result
*envelope* object — the same shape `cli_runner.extract_turn_result` reads, where the model's output
is the `result` field. A naive `json.loads(stdout)` expecting an array would get a dict on every
successful run, return `[]` every time, and the spotlight would silently never carry drafts while
looking perfectly healthy. Parsing is therefore:

1. `json.loads(stdout)` → envelope dict. Treat a non-dict, a missing `result`, or a truthy
   `is_error` as failure.
2. Take `envelope["result"]`, strip a surrounding ```` ``` ````/```` ```json ```` fence if present
   (the model may fence its array despite instructions), then `json.loads` that.
3. Require a `list` of three `str`. Anything else is failure.

`--verbose` is **not** required here. `cli_runner.py:83-88` scopes that requirement specifically to
`--output-format stream-json`; plain `json` with `-p` does not need it. This should still be
re-verified against `claude --help` during implementation, since CLI flag behavior changes between
releases.

### Guarantees enforced in code

The prompt asks for all of the constraints below. The code then enforces the mechanical ones,
because a prompt instruction is a request and the em-dash rule was specified as absolute.

- **No em dash.** After generation, U+2014 (em dash), U+2013 (en dash), and `--` are removed from
  every draft and replaced with a comma or a period as surrounding grammar allows, with whitespace
  collapsed afterward. Unconditional — the rule cannot leak regardless of what the model returns.
- **Length cap.** 300 characters per draft. An over-length draft is truncated at the last sentence
  boundary within the cap; if that leaves fewer than 40 characters, the draft is dropped.
- **Shape.** Non-JSON output, fewer than three usable drafts after sanitizing, or an empty result
  → return `[]`. Partial results are not rendered; three or nothing.

### Enforced by prompt only

"Positive, nothing negative or derogatory" cannot be verified programmatically. A keyword blocklist
would be theater: it would miss real negativity and false-positive on ordinary words. The prompt
states the constraint firmly, and `email_render` labels the section as drafts for review rather than
ready-to-send copy. The user is the check on tone. This limit is stated here rather than papered
over.

### Failure modes, all non-fatal

Timeout, missing `claude` binary, non-zero exit, an unparseable envelope, an unparseable inner
array, or fewer than three surviving drafts all return `[]`. On timeout the `TimeoutExpired` branch
calls `kill_process_tree(process)` and then reaps with a second `communicate()` — see the
`Popen`-not-`run` requirement above for why this cannot be delegated to `subprocess.run`.

When `draft_comments` returns `[]`, the spotlight section still renders with the post, metrics,
excerpt, and link, plus one line noting drafting was unavailable. **The email always sends.**

## `email_render.py`

### `render_email(summary, run_date) -> {"subject", "text", "html"}`

Pure function. No I/O, no clock, no network — every case is a snapshot test.

**Subject.** `ContentStudio Discovery {run_date}: {N} new post(s)`, where N is the total item count,
prefixed `"[ISSUE] "` when `has_issues` is true. "video(s)" becomes "post(s)" now that four
platforms feed it.

**Body order:** spotlight, then inventory grouped by platform, then errors. When `has_issues` is
true the body still opens with `"Run status: {run_status}"` above everything else, preserving the
2026-08-01 spec's guarantee that an `[ISSUE]`-flagged email never has a contradictory empty body.

**Platform ordering** is the fixed list `["linkedin-profile", "linkedin-company", "youtube",
"instagram", "bluesky"]`, with any platform not on that list appended in alphabetical order. A
platform added later renders correctly with no change here; it simply sorts to the bottom until
someone gives it a rank. Display labels come from a small dict with a title-cased fallback for
unknown platforms.

**Spotlight section** renders: platform label, `display_name`, metrics, `published`, a 400-character
excerpt of the body (whitespace-collapsed, cut at a word boundary, ellipsis appended), the
"Click here to view" link, and the three drafts as a numbered list under a heading marking them as
drafts for review.

**Inventory ordering.** Within a platform group, items sort by `display_name` ascending, then
`handle` ascending, then `published` descending (missing last), then `item_id` ascending — so one
account's posts stay together and its newest is first. `handle` is in the key for the same totality
reason as in `select_spotlight`, and additionally because two handles can share a `display_name`.

**Inventory entries** render: `display_name`, title, the metrics that are present, and the
"Click here to view" link. The spotlight post is **not** removed from its platform group — it would
otherwise be silently missing from the day's inventory — and its entry carries a `(featured above)`
marker.

**HTML part** uses `<h2>`, `<ul>`/`<li>`, `<a>`, `<em>`, `<strong>` and nothing else. No inline CSS,
no tables, no images. All interpolated values — titles, excerpts, handles, drafts — are HTML-escaped
via `html.escape`; scraped post text is untrusted and must not reach the body unescaped. URLs are
escaped and emitted only when the scheme is `http` or `https`, so a malformed or `javascript:` value
in frontmatter cannot become a live link.

**Plain-text part** carries the same content with the URL on its own line instead of anchor text,
since "Click here to view" is meaningless without a link behind it.

**Degradation is per-field, never per-post.** No `url` → entry renders without a link; no metrics →
segment omitted; no title → file stem. A post with nothing but a filename still appears.

**Empty case.** Zero items and zero errors and `has_issues` false → the body is `"No new content
today."`, as today, with no spotlight section.

## `discovery_notify.py` after the change

Shrinks to orchestration plus the network call.

- `build_summary(conn, repo_root, run_row_id) -> dict` — reads `discovery_runs` and
  `discovery_run_handles` as it does now, but calls `discovery_digest.collect_new_items` for **every**
  handle regardless of platform instead of branching on `platform == "youtube"`. Handles with zero
  items contribute nothing; `errored` is still populated from `status == "error"` rows using
  `display_name or handle`, with `error_message` still excluded from the email body. Shape:

  ```python
  {
      "run_status": "completed_with_errors",
      "has_issues": True,          # run_status != "completed" or errored is non-empty
      "items": [Item, ...],        # every new item across every platform, flat
      "errored": ["@dead-handle"],
  }
  ```

  `items` is flat rather than pre-grouped: `select_spotlight` needs the flat list, and
  `email_render` owns grouping and ordering so that adding a platform never requires a second place
  to be taught about it.
- `notify(conn, repo_root, run_row_id) -> bool` — `build_summary` → `select_spotlight` →
  `draft_comments` → compute `run_date` in the configured timezone → `render_email` → `send_email`.
- `send_email(subject, text, html) -> bool` — gains an `html` field in the Resend payload alongside
  `text`. Everything else about it is unchanged: same key lookup, same `timeout=15`, same
  catch-and-return-`False` behavior.

## Error handling

The 2026-08-01 invariant holds: a notification failure never affects `discovery_runs.status` or the
cron script's exit code. `run_discovery()` has already returned and persisted its result before
`notify` is called, and `main()` returns `0` on every path.

**`notify` still does not catch, and that stays deliberate.** The existing contract — documented in
`tests/test_discovery_notify.py:377-385`, which asserts `notify` *propagates* a `build_summary`
failure — is that `notify` adds no failure handling of its own; the cron call site
(`run_discovery_cron.py:100`) is the single catch point. This spec does not change that. An earlier
draft's failure table said "caught by `notify`'s and the cron's `try/except`", which would have
quietly inverted a tested contract; the cron's catch alone is what makes the guarantee hold, and
that test is left exactly as it is. The new modules take the burden instead: `draft_comments` never
raises by construction, and per-item parse failures are contained inside `collect_new_items`.

New failure modes, each degrading to something narrower than "no email":

| Failure | Blast radius |
|---|---|
| One file's frontmatter malformed, or `fetched_at` missing / non-`str` / unparseable | that item only |
| One item missing `url` | that item's link only; stderr line |
| Selected-file count ≠ `items_downloaded` | stderr warning; email sends |
| A handle errored mid-run with partial downloads | nothing — items listed *and* handle named under `Errors:` |
| `claude` binary missing, timeout, bad exit, envelope or array unparseable | three drafts; spotlight still renders with a note |
| Prompt contains characters unencodable on the pipe | nothing — `encoding="utf-8"` is set explicitly |
| `build_summary` or `render_email` or Resend raises | whole email — propagates out of `notify` to the cron's `try/except` (`run_discovery_cron.py:100`), logged to stderr |

The known gap from the 2026-08-01 spec is unchanged and still accepted: if `run_discovery()` itself
raises before returning, `notify()` is never reached and that day gets no email.

## Testing

New file `pipeline-app/tests/test_discovery_digest.py`:

- Watermark inclusion and exclusion, including a file `fetched_at` before `run_started_at`.
- Title derivation per platform: YouTube H1, LinkedIn/Instagram first-body-line truncation at a word
  boundary, file-stem fallback.
- Missing `url` / metrics / `published` producing `None`, and `0` surviving as `0`.
- Primary text extraction: a YouTube-shaped body yielding the transcript section, not `## description`
  text; a YouTube body whose transcript is `(no transcript available)` falling through to the
  description; a body where both are placeholders yielding `""`; a flat Instagram/LinkedIn body
  passing through whole.
- Title rule: a body opening `#MondayMotivation` treated as text, not an H1, and its first line
  surviving into `body`; a body opening `# Real Title` consumed as the title and stripped.
- Malformed YAML excluded without raising; a non-`str` `fetched_at` (unquoted YAML timestamp →
  `datetime`) excluded without raising `TypeError`.
- mtime pre-filter: an old file with a fresh `fetched_at` still requires the watermark to pass, and
  a file whose mtime is inside the window but whose `fetched_at` predates the run is excluded —
  asserting the pre-filter is an optimization and never the authority.
- Both dropped gates: an `items_downloaded == 0` handle and a `status == "error"` handle each still
  scanned, with an errored handle's partial downloads appearing as items.
- `items_downloaded` mismatch logging without raising.
- `select_spotlight`: LinkedIn gate beating a higher-metric YouTube item; both LinkedIn modes
  eligible; ranking by likes+comments; each tie-break level exercised in isolation; all-zero input
  resolving to newest; empty input → `None`; an empty-`body` LinkedIn item excluded so a YouTube
  item wins instead; every candidate empty-bodied → `None`.

New file `pipeline-app/tests/test_comment_draft.py`, `subprocess.Popen` monkeypatched, no real
process spawned:

- Happy path: three drafts parsed out of the **result envelope**, i.e. stdout is
  `{"type":"result","result":"[\"a\",\"b\",\"c\"]","is_error":false}` — the test fixture must be the
  envelope, not a bare array, or it would pass against the exact bug this design is avoiding.
- A fenced inner payload (```` ```json ... ``` ````) parsed correctly.
- Envelope not a dict, `result` missing, `is_error` true, inner text not a JSON array, array of two,
  empty array, and an over-length-then-dropped draft each → `[]`.
- Timeout: `communicate` raising `TimeoutExpired` asserts `kill_process_tree` is called with the
  process and the result is `[]`.
- `FileNotFoundError` from `resolve_claude_binary` and a non-zero exit each → `[]`.
- `Popen` is constructed with `encoding="utf-8"` and a `cwd` that is not the repo root — asserted
  directly, since both are silent-daily-failure modes rather than visible ones.
- **Em-dash guarantee:** a fake returning drafts containing U+2014, U+2013, and `--` asserts none
  survive in the output.
- Length cap: a 500-character draft truncated at a sentence boundary.
- Prompt is passed via the `input=` kwarg, never in argv — asserted directly, since this is the
  injection defense.
- Transcript truncation at 12,000 characters with the marker present.

New file `pipeline-app/tests/test_email_render.py`, snapshot-style over hand-built summaries:

- Spotlight present; spotlight absent; drafts empty producing the unavailable note.
- `[ISSUE]` prefixing and the `Run status:` opening line, including the all-empty failed-run case.
- Unknown platform sorting to the bottom with a title-cased label.
- Missing-URL entry rendering without a link in both parts.
- `(featured above)` marker on the spotlight's inventory entry.
- Inventory ordering: two handles on one platform interleaved in input, asserted grouped by
  `display_name` with newest-first inside each.
- HTML escaping of a title and an excerpt containing `<`, `&`, and `"`.
- A `javascript:` URL in frontmatter not becoming an anchor.
- Text/HTML parity: both parts list the same set of item titles.
- `"No new content today."` empty case.

Updated `pipeline-app/tests/test_discovery_bluesky.py`:

- `download_item` writes frontmatter that round-trips through `artifacts.parse_frontmatter` with
  `url` and `fetched_at` present.

Updated `pipeline-app/tests/test_discovery_notify.py`:

- `build_summary` calls the digest for every platform, not just YouTube, and for handles the old
  gates would have skipped.
- `send_email` payload includes `html` alongside `text`.
- `notify` orchestration order, including `select_spotlight` → `draft_comments` feeding
  `render_email`.
- `test_notify_never_raises_when_build_summary_fails` is **left unchanged**. Despite its name it
  asserts `notify` propagates, which is the contract this spec preserves; touching it would be
  changing a contract under cover of a refactor.

Updated `pipeline-app/tests/test_cli_runner.py`:

- Call sites renamed for `platform_argv` / `kill_process_tree` losing their underscore prefixes. No
  behavior change.

Existing `run_discovery_cron.py`-level coverage is unchanged — the call site does not change.

## Documentation changes

Both are required, not optional.

**1. `CLAUDE.md` privacy exception is now false and must be rewritten.** It currently reads that the
email sends channel names and video titles "and nothing else — never transcripts, descriptions, or
any other corpus content." After this change, two things leave the machine that did not before: post
text and transcripts go to Anthropic via the `claude` CLI subprocess, and post excerpts plus derived
comment drafts go out in the email body. The paragraph is rewritten to state both accurately.
Leaving a knowingly false privacy claim in `CLAUDE.md` would be worse than the change itself.

**2. `CLAUDE.md` gains the platform contract** from "The platform contract" above, so adapters added
later inherit the email without anyone rediscovering the requirement.

## Setup

None. No new API key, no new dependency, no new external account. `comment_draft` uses the `claude`
binary already required by the pipeline app, and `send_email` uses the Resend key already
configured.

One operational note: the `claude` binary must resolve on `PATH` inside the Windows Task Scheduler
environment the 06:00 run inherits. If it does not, `draft_comments` returns `[]` and the email
sends without drafts — visible in the email itself as the unavailable note, and in the task's
captured stderr.

## Review notes

Reviewed by a second model (Fable) against the actual code before implementation, following the
same practice as the 2026-08-01 spec. Three blocking issues were found; all are resolved above
rather than deferred.

1. **The `build_summary` gates contradicted the watermark's own rationale.** The spec inherited the
   "self-corrects when `items_downloaded` under-reports" argument while leaving in place the
   `status == "error"` and `items_downloaded <= 0` gates that skip exactly the handle that argument
   describes. Two implementers would have built different things. Resolved by dropping both gates,
   stating the intended consequence (an errored handle appears in the inventory *and* under
   `Errors:`), and adding an mtime pre-filter so scanning every directory daily does not grow
   unbounded against a corpus already at 740 files. (The inherited line citation was also stale —
   the record happens at `discovery_engine.py:346`, not `:327`.)
2. **`subprocess.run` cannot deliver the timeout guarantee the spec claimed.** It handles
   `TimeoutExpired` with an internal `process.kill()` and never exposes the pid, and
   `cli_runner.py:167` records empirically that `process.kill()` on Windows orphans the real
   `claude` process behind the `cmd.exe` shim. Resolved by respecifying as `Popen` +
   `communicate(timeout=...)` + caller-side `kill_process_tree`.
3. **`--output-format json` returns a result envelope, not the model's text.** A single
   `json.loads(stdout)` expecting an array would have returned `[]` on every successful run — the
   spotlight would have silently never carried drafts while appearing healthy. Resolved with an
   explicit two-layer parse plus fence-stripping, and a test fixture required to be the envelope
   shape so the test cannot pass against the bug.

Should-fix items also folded in: the Bluesky legacy fallback deleted as unreachable-by-construction
(the watermark can never select a pre-change file); the title rule tightened to `# ` so a post
opening with a hashtag does not lose its first line; `encoding="utf-8"` mandated on the subprocess
pipe against cp1252 versus emoji; `--disallowedTools` specified as an enumerated list with a note
that no wildcard exists; `cwd` pinned to an empty temp directory so drafting turns do not load this
repo's `CLAUDE.md` and eight skills; `handle` added to both sort keys to make them total;
non-`str` `fetched_at` folded into "unparseable"; `cli_runner`'s `_platform_argv` and
`_kill_process_tree` promoted out of underscore-private now that a second module consumes them; and
the `notify` try/except contract corrected back to "does not catch," since an earlier draft would
have inverted a tested and deliberately-documented behavior.

Corrected NITs: `_tmp` is a sibling of the handle directories, not a child (the conclusion held, the
justification did not); the Bluesky spotlight claim overstated the gap, since a zero-metric YouTube
item ties rather than outranks; and `download_brandintel.py` is noted in the platform contract as a
known non-conforming writer rather than being silently non-compliant.
