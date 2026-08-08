# X.com Bright Data Discovery Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add X.com as a fifth discovery-pipeline platform (`x`), backed by Bright Data's X Posts dataset in `discover_by=profile_url` mode.

**Architecture:** One new module, `pipeline_app/discovery_x.py`, with module-level functions and a module-level enumerate cache — the `discovery_instagram.py` shape, not LinkedIn's bound-instance class, because X has exactly one working mode. It satisfies the structural `PlatformAdapter` protocol and delegates the whole trigger → poll → fetch cycle to the existing `pipeline_app/brightdata_job.py`, which needs no change. Registration is two lines: one entry in `build_adapters()` and one `<option>` in the handles template.

**Tech Stack:** Python 3.14, `requests`, `pyyaml` (via `pipeline_app.artifacts.render_frontmatter`), `pytest`. No new dependencies.

**Source spec:** [`docs/superpowers/specs/2026-08-08-x-brightdata-adapter-design.md`](../specs/2026-08-08-x-brightdata-adapter-design.md)

## Global Constraints

- **Every field mapping in this plan was verified against six live Bright Data jobs on 2026-08-08.** Do not "improve" a mapping to a field that looks better named. If reality disagrees with this plan, stop and report — do not silently adapt.
- **Never return `[]` on failure.** A timed-out or `failed` job must raise. An empty list means "the job completed and there was genuinely nothing", which the engine records as the healthy status `no_new_content`. This is the bug that shipped in the first Instagram adapter.
- **`is_repost` must never be used as a filter.** It was `False` on a post the tracked account did not write. The authorship filter is `user_posted`.
- **Identity is keyed on `id` only, never on `url`.** The dataset returns two different URL shapes for different accounts (`twitter.com/<numeric_id>/status/<id>` and `x.com/<handle>/status/<id>`).
- `DATASET_ID = "gd_lwxkxvnf1cynvib9co"` (X **Posts** dataset — not the Profiles dataset `gd_lwxmeb2u1cniijd7t4`, which was dropped on evidence).
- `MAX_ITEMS_PER_RUN = 10`, `POLL_INTERVAL_S = 5`, `POLL_TIMEOUT_S = 600`, `TITLE_MAX_CHARS = 60`, `PLATFORM = "x"`.
- **`POLL_TIMEOUT_S` is 600, deliberately diverging from Instagram's and LinkedIn's 300.** Measured latency was 243s at `limit_per_input=10`, the production setting. Do not "make the constants consistent".
- No new dependencies. No network calls in tests.
- Run tests from the `pipeline-app/` directory: `python -m pytest tests/ -q`.
- Commit messages end with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

## File Structure

| File | Responsibility |
|---|---|
| `pipeline-app/pipeline_app/discovery_x.py` | **Create.** The whole adapter: constants, row normalization, job cycle wiring, the four `PlatformAdapter` functions, module-level enumerate cache. |
| `pipeline-app/tests/test_discovery_x.py` | **Create.** All adapter tests against a fake HTTP layer. |
| `pipeline-app/run_discovery_cron.py` | **Modify.** Import `discovery_x`; add `"x"` to `build_adapters()`. |
| `pipeline-app/pipeline_app/templates/discovery_handles.html` | **Modify.** One `<option>`. |
| `pipeline-app/tests/test_run_discovery_cron.py` | **Modify.** Registration and backfill-exclusion pins. |

`pipeline_app/brightdata_job.py` and `pipeline_app/discovery_engine.py` are **not modified**. `BACKFILL_SUPPORTED_PLATFORMS` is a whitelist (`{"youtube", "bluesky"}`), so `x` is already rejected from backfill with no code change.

---

### Task 1: Row normalization

The pure functions, with no network and no cache. Doing these first means the field mappings — the part that has historically been wrong — are pinned before any plumbing exists.

**Files:**
- Create: `pipeline-app/pipeline_app/discovery_x.py`
- Test: `pipeline-app/tests/test_discovery_x.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `_parse_published(raw: str | None) -> str | None`; `_video_urls(raw) -> list[str]`; `_normalize_row(row: dict) -> dict | None` returning a dict with keys `id, title, published, published_ts, author, body, url, like_count, comment_count, repost_count, view_count, bookmark_count, quote_count, hashtags, photos, videos, external_url`. Module constants `DATASET_ID, KEY_ENV_VAR, KEY_FILE, MAX_ITEMS_PER_RUN, POLL_TIMEOUT_S, POLL_INTERVAL_S, TITLE_MAX_CHARS, PLATFORM`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_discovery_x.py`:

```python
from pipeline_app import discovery_x as x


def test_parse_published_accepts_the_verified_iso_format():
    """Live X rows carry real ISO 8601 UTC -- 2026-08-08T01:11:45.000Z
    (verified 2026-08-08, snapshot sd_mskd8iv12ivrnbejlz). This matches
    LinkedIn and differs from the Instagram product's US-format local
    timestamp; three Bright Data datasets, two date formats, so none may be
    assumed from another."""
    assert x._parse_published("2026-08-08T01:11:45.000Z") == "2026-08-08"
    assert x._parse_published("2026-08-08") == "2026-08-08"


def test_parse_published_rejects_unusable_values():
    assert x._parse_published("") is None
    assert x._parse_published(None) is None
    assert x._parse_published("not a date") is None
    # A US-format date is NOT silently reinterpreted -- guessing between
    # MM/DD and DD/MM produces wrong dates, which is worse than a dropped
    # row, and dropped rows are counted and logged.
    assert x._parse_published("08/08/2026 01:11:45") is None


def _raw_row(**overrides):
    """A row shaped like the live payload from snapshot sd_mskd8iv12ivrnbejlz."""
    row = {
        "id": "2085896713185714235",
        "date_posted": "2026-08-08T01:11:45.000Z",
        "user_posted": "CNN",
        "name": "CNN",
        "user_id": "759251",
        "description": "A daring mission to rescue one of NASA's observatories.",
        "url": "https://twitter.com/759251/status/2085896713185714235",
        "is_repost": False,
        "likes": 310,
        "replies": 85,
        "reposts": 64,
        "views": 214564,
        "bookmarks": 16,
        "quotes": 6,
        "hashtags": None,
        "photos": ["https://pbs.twimg.com/media/HPKX_XjXUAAxkvS.jpg"],
        "videos": None,
        "external_url": "https://cnn.it/45aXVbJ",
    }
    row.update(overrides)
    return row


def test_normalize_row_maps_every_verified_field():
    n = x._normalize_row(_raw_row())
    assert n["id"] == "2085896713185714235"
    assert n["published"] == "2026-08-08"
    assert n["author"] == "CNN"
    assert n["body"].startswith("A daring mission")
    assert n["like_count"] == 310
    assert n["comment_count"] == 85       # from `replies`
    assert n["repost_count"] == 64
    assert n["view_count"] == 214564
    assert n["bookmark_count"] == 16
    assert n["quote_count"] == 6
    assert n["photos"] == ["https://pbs.twimg.com/media/HPKX_XjXUAAxkvS.jpg"]
    assert n["external_url"] == "https://cnn.it/45aXVbJ"


def test_normalize_row_keeps_media_only_posts_with_an_empty_body():
    """3 of 10 live elonmusk rows had description: null -- media-only posts
    (snapshot sd_mskdghugb6u3685n6). These are KEPT, not dropped: the row
    still carries a date, six engagement counts and the media URLs, and
    dropping them would pay for rows it discards on a video-heavy account."""
    n = x._normalize_row(_raw_row(description=None, photos=None,
                                  videos=[{"video_url": "https://video.twimg.com/a.mp4",
                                           "duration": 6041}]))
    assert n is not None
    assert n["body"] == ""
    assert n["videos"] == ["https://video.twimg.com/a.mp4"]


def test_normalize_row_flattens_the_videos_struct_list_to_urls():
    """videos is a list of structs carrying video_url and duration (verified
    live). Storing the raw structs would put duration integers in the
    frontmatter; only the URL is wanted."""
    n = x._normalize_row(_raw_row(videos=[
        {"video_url": "https://video.twimg.com/a.mp4", "duration": 6041},
        {"video_url": "https://video.twimg.com/b.mp4", "duration": 3761157},
    ]))
    assert n["videos"] == ["https://video.twimg.com/a.mp4",
                           "https://video.twimg.com/b.mp4"]


def test_normalize_row_title_is_the_first_line_then_falls_back_to_id():
    n = x._normalize_row(_raw_row(description="First line.\nSecond line."))
    assert n["title"] == "First line."
    media_only = x._normalize_row(_raw_row(description=None))
    assert media_only["title"] == "2085896713185714235"


def test_normalize_row_truncates_title_to_60_chars():
    n = x._normalize_row(_raw_row(description="y" * 100))
    assert n["title"] == "y" * 60


def test_normalize_row_drops_rows_with_no_id_or_unusable_date():
    assert x._normalize_row(_raw_row(id=None)) is None
    assert x._normalize_row(_raw_row(id="")) is None
    assert x._normalize_row(_raw_row(date_posted="nonsense")) is None
    assert x._normalize_row(_raw_row(date_posted=None)) is None


def test_normalize_row_drops_the_include_errors_error_row():
    """include_errors=true yields rows carrying error/error_code with every
    content field null (verified live, snapshot sd_mskdls3f26klcqyxk9:
    error_code 'dead_page'). They have no id, so the id guard discards them
    with no special-casing -- pin that, so a future 'helpful' fallback that
    invents an id from the url does not resurrect them."""
    error_row = {"error": "No public posts were found in the profile for the "
                          "specified period.",
                 "error_code": "dead_page",
                 "timestamp": "2026-08-08T12:56:25.349Z"}
    assert x._normalize_row(error_row) is None


def test_normalize_row_keeps_the_full_timestamp_as_a_separate_sort_key():
    """'published' truncates to the date, so same-day rows need the time of
    day to sort correctly. Rows arrive unsorted (verified live)."""
    n = x._normalize_row(_raw_row())
    assert n["published_ts"] == "2026-08-08T01:11:45.000Z"


def test_normalize_row_coerces_missing_list_fields_to_empty_lists():
    """hashtags/photos/videos come back as null, not [], on most rows.
    yaml.safe_dump renders None as 'null'; an empty list is the honest shape."""
    n = x._normalize_row(_raw_row(hashtags=None, photos=None, videos=None))
    assert n["hashtags"] == []
    assert n["photos"] == []
    assert n["videos"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_x.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline_app.discovery_x'` (collection error).

- [ ] **Step 3: Write minimal implementation**

Create `pipeline-app/pipeline_app/discovery_x.py`:

```python
"""X.com platform adapter for the discovery engine, backed by Bright Data's
X Posts dataset (discover_by=profile_url).

Field names below come from six live jobs on 2026-08-08, not from the
published field list. See docs/superpowers/specs/2026-08-08-x-brightdata-
adapter-design.md, which also records why two modes Bright Data advertises
are NOT implemented:

  - The X Profiles dataset (gd_lwxmeb2u1cniijd7t4) returns one billed record
    with an embedded posts array, which looked ~20x cheaper. Its depth and
    recency are wildly inconsistent -- CNN returned 20 posts from the last
    two days, elonmusk returned 99 spanning 2018-2025 whose newest was
    eleven months stale, unsorted, with no author field to filter on.
  - start_date/end_date backfill returns an error row (error_code
    'dead_page'), verified. There is no backfill path here.
"""
from __future__ import annotations

import datetime as _dt
import sys
import time  # noqa: F401 -- kept so tests can monkeypatch x.time.sleep/monotonic
from pathlib import Path

import requests  # noqa: F401 -- kept so tests can monkeypatch x.requests.post/get

from pipeline_app import artifacts, brightdata_job
from pipeline_app.discovery_paths import handle_dir

# Not a secret -- read off the Bright Data dashboard's generated API snippet
# for the X Posts product (2026-08-08). The type/discover_by query params
# select the mode; this is the Posts dataset, NOT the Profiles dataset.
DATASET_ID = "gd_lwxkxvnf1cynvib9co"

KEY_ENV_VAR = "BRIGHTDATA_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "brightdata_api_key.txt"

PLATFORM = "x"

MAX_ITEMS_PER_RUN = 10
# 600, NOT the 300 Instagram and LinkedIn use. Measured latency was 243s at
# limit_per_input=10 -- the production setting -- so 300 would leave under a
# minute of margin and turn ordinary slowness into a BrightDataJobTimeout on
# a job that was already billed. Do not "make the constants consistent".
POLL_TIMEOUT_S = 600
POLL_INTERVAL_S = 5

TITLE_MAX_CHARS = 60


def _parse_published(raw: str | None) -> str | None:
    """Bright Data's date_posted -> the engine's required YYYY-MM-DD, or None.

    This dataset returns genuine ISO 8601 UTC -- '2026-08-08T01:11:45.000Z'
    (verified 2026-08-08) -- so a 10-character prefix is correct. That is NOT
    true of Bright Data's Instagram product, which returns a US-format local
    timestamp; the datasets disagree, so no format may be inferred from
    another.

    US-format input is deliberately NOT accepted. Guessing between MM/DD and
    DD/MM would yield silently wrong dates, which is worse than a dropped row
    -- and drops are counted and logged by enumerate_newest_first.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    candidate = raw[:10]
    try:
        _dt.datetime.strptime(candidate, "%Y-%m-%d")
        return candidate
    except ValueError:
        return None


def _video_urls(raw) -> list[str]:
    """The `videos` field is a list of structs -- [{'video_url': ...,
    'duration': ...}] -- verified live. Flatten to URLs; duration is not
    stored. Bare strings are tolerated in case the shape ever simplifies."""
    if not raw:
        return []
    urls = []
    for entry in raw:
        if isinstance(entry, dict):
            url = (entry.get("video_url") or "").strip()
            if url:
                urls.append(url)
        elif isinstance(entry, str) and entry.strip():
            urls.append(entry.strip())
    return urls


def _normalize_row(row: dict) -> dict | None:
    """One raw Bright Data row -> this adapter's internal shape, or None if
    the row is unusable. The single place to update if the schema changes.

    Load-bearing and verified:
    - The body is `description`, and it is NULLABLE -- 3 of 10 live rows for
      one account were media-only posts. A null body is kept, not dropped.
    - Authorship is `user_posted` (the handle), NOT `user_id` (a numeric
      profile id) and NOT `is_repost`, which was False even on a row the
      tracked account did not write.
    - There is no usable content_type field; see enumerate_newest_first.
    """
    post_id = row.get("id")
    if not post_id:
        return None
    published = _parse_published(row.get("date_posted"))
    if published is None:
        return None

    body = (row.get("description") or "").strip()
    first_line = body.split("\n", 1)[0].strip()
    title = first_line or str(post_id)

    raw_date_posted = (row.get("date_posted") or "").strip()

    return {
        "id": str(post_id),
        "title": title[:TITLE_MAX_CHARS],
        "published": published,
        # Full ISO 8601 timestamp, used only as the sort key -- 'published'
        # truncates to the date, so same-day rows would otherwise sort in
        # Bright Data's arbitrary arrival order (verified live: rows are NOT
        # returned newest-first). Lexicographic comparison is correct for
        # this dataset's real ISO 8601 strings.
        "published_ts": raw_date_posted or f"{published}T00:00:00",
        "author": (row.get("user_posted") or "").strip(),
        "body": body,
        # Informational only. The domain varies by account --
        # twitter.com/<numeric_id>/status/<id> for CNN,
        # x.com/<handle>/status/<id> for elonmusk -- so identity is never
        # keyed on it.
        "url": row.get("url") or "",
        "like_count": row.get("likes"),
        "comment_count": row.get("replies"),
        "repost_count": row.get("reposts"),
        "view_count": row.get("views"),
        "bookmark_count": row.get("bookmarks"),
        "quote_count": row.get("quotes"),
        # These come back as null rather than [] on most rows; yaml.safe_dump
        # would render that as 'null', and an empty list is the honest shape.
        "hashtags": row.get("hashtags") or [],
        "photos": row.get("photos") or [],
        "videos": _video_urls(row.get("videos")),
        "external_url": row.get("external_url"),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_x.py -q`
Expected: PASS — 11 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_x.py pipeline-app/tests/test_discovery_x.py
git commit -m "feat(x): normalize Bright Data X Posts rows

Field mappings pinned against the live payloads from six jobs on
2026-08-08. The nullable description and the videos struct list are the
two shapes the published field list does not warn you about.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: The collection job cycle

Credentials and the trigger → poll → fetch wiring. All three network functions stay module-level so tests can monkeypatch them by name, exactly as `discovery_instagram` does.

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_x.py` (append)
- Test: `pipeline-app/tests/test_discovery_x.py` (append)

**Interfaces:**
- Consumes: `DATASET_ID`, `KEY_ENV_VAR`, `KEY_FILE`, `MAX_ITEMS_PER_RUN`, `POLL_TIMEOUT_S`, `POLL_INTERVAL_S` from Task 1.
- Produces: `api_key() -> str | None`; `profile_url(handle: str) -> str`; `_trigger_job(handle: str, key: str) -> str`; `_poll_job_status(job_id: str, key: str) -> str`; `_fetch_job_results(job_id: str, key: str) -> list[dict]`; `_run_collection_job(handle: str) -> list[dict]`. Re-exports `BrightDataJobTimeout` and `BrightDataJobFailed`.

- [ ] **Step 1: Write the failing test**

Append to `pipeline-app/tests/test_discovery_x.py`:

```python
import pytest


def test_api_key_prefers_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv(x.KEY_ENV_VAR, "env-key")
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("file-key", encoding="utf-8")
    monkeypatch.setattr(x, "KEY_FILE", key_file)
    assert x.api_key() == "env-key"


def test_api_key_falls_back_to_file(monkeypatch, tmp_path):
    monkeypatch.delenv(x.KEY_ENV_VAR, raising=False)
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("  file-key\n", encoding="utf-8")
    monkeypatch.setattr(x, "KEY_FILE", key_file)
    assert x.api_key() == "file-key"


def test_api_key_none_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv(x.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(x, "KEY_FILE", tmp_path / "absent.txt")
    assert x.api_key() is None


def test_profile_url_strips_the_at_sign():
    assert x.profile_url("@CNN") == "https://x.com/CNN"
    assert x.profile_url("elonmusk") == "https://x.com/elonmusk"


def _fake_key(monkeypatch, value="test-key"):
    monkeypatch.setattr(x, "api_key", lambda: value)


def test_trigger_job_requests_a_discovery_job_not_a_single_page_collect(monkeypatch):
    """Without type=discover_new/discover_by=profile_url, Bright Data reads
    the input url as a single page to collect -- the wrong product mode
    entirely, and a silently useless one."""
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"snapshot_id": "snap1"}

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["json"] = json
        return _Resp()

    monkeypatch.setattr(x.requests, "post", fake_post)
    assert x._trigger_job("CNN", "test-key") == "snap1"

    assert captured["url"].endswith("/trigger")
    assert captured["params"]["dataset_id"] == "gd_lwxkxvnf1cynvib9co"
    assert captured["params"]["type"] == "discover_new"
    assert captured["params"]["discover_by"] == "profile_url"
    assert captured["params"]["limit_per_input"] == x.MAX_ITEMS_PER_RUN
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    # A bare array, not {"input": [...]} -- the dashboard's object form
    # belongs to the synchronous /scrape endpoint, which no adapter uses.
    assert captured["json"] == [{"url": "https://x.com/CNN"}]


def test_trigger_job_does_not_send_date_filters(monkeypatch):
    """start_date/end_date are PROVEN broken on this dataset -- a two-day
    window against an account posting hundreds of times a day returned a
    single error row, error_code 'dead_page' (snapshot sd_mskdls3f26klcqyxk9).
    Sending empty strings would be harmless but misleading; sending real ones
    would break collection. Pin that neither key is present."""
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"snapshot_id": "snap1"}

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _Resp()

    monkeypatch.setattr(x.requests, "post", fake_post)
    x._trigger_job("CNN", "test-key")
    assert "start_date" not in captured["json"][0]
    assert "end_date" not in captured["json"][0]


def test_run_collection_job_returns_results_on_ready(monkeypatch):
    _fake_key(monkeypatch)
    monkeypatch.setattr(x, "_trigger_job", lambda handle, key: "job1")
    monkeypatch.setattr(x, "_poll_job_status", lambda job_id, key: "ready")
    monkeypatch.setattr(x, "_fetch_job_results", lambda job_id, key: [{"id": "p1"}])
    monkeypatch.setattr(x.time, "sleep", lambda s: None)
    assert x._run_collection_job("CNN") == [{"id": "p1"}]


def test_run_collection_job_polls_until_ready(monkeypatch):
    _fake_key(monkeypatch)
    statuses = iter(["running", "running", "ready"])
    monkeypatch.setattr(x, "_trigger_job", lambda handle, key: "job1")
    monkeypatch.setattr(x, "_poll_job_status", lambda job_id, key: next(statuses))
    monkeypatch.setattr(x, "_fetch_job_results", lambda job_id, key: [{"id": "p1"}])
    monkeypatch.setattr(x.time, "sleep", lambda s: None)
    assert x._run_collection_job("CNN") == [{"id": "p1"}]


def test_run_collection_job_raises_on_failed_status(monkeypatch):
    """A failed job must NEVER return [] -- the engine would record the
    healthy status 'no_new_content' for a job that was billed and failed."""
    _fake_key(monkeypatch)
    monkeypatch.setattr(x, "_trigger_job", lambda handle, key: "job1")
    monkeypatch.setattr(x, "_poll_job_status", lambda job_id, key: "failed")
    monkeypatch.setattr(x.time, "sleep", lambda s: None)
    with pytest.raises(x.BrightDataJobFailed):
        x._run_collection_job("CNN")


def test_run_collection_job_raises_on_timeout(monkeypatch):
    _fake_key(monkeypatch)
    monkeypatch.setattr(x, "_trigger_job", lambda handle, key: "job1")
    monkeypatch.setattr(x, "_poll_job_status", lambda job_id, key: "running")
    monkeypatch.setattr(x.time, "sleep", lambda s: None)
    monkeypatch.setattr(x, "POLL_TIMEOUT_S", 0)
    with pytest.raises(x.BrightDataJobTimeout):
        x._run_collection_job("CNN")


def test_run_collection_job_raises_clear_error_when_key_missing(monkeypatch):
    monkeypatch.setattr(x, "api_key", lambda: None)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("must not trigger a paid job with no key")

    monkeypatch.setattr(x, "_trigger_job", _fail_if_called)
    with pytest.raises(RuntimeError, match="Bright Data API key not configured"):
        x._run_collection_job("CNN")


def test_poll_timeout_is_600_not_the_inherited_300():
    """Deliberate divergence from Instagram and LinkedIn. Measured latency
    was 243s at limit_per_input=10, the production setting, so 300s leaves
    under a minute of margin. This test exists to fail a well-meaning 'make
    the constants consistent' edit."""
    assert x.POLL_TIMEOUT_S == 600
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_x.py -q`
Expected: FAIL — `AttributeError: module 'pipeline_app.discovery_x' has no attribute 'api_key'` and similar for `profile_url`, `_trigger_job`, `_run_collection_job`, `BrightDataJobFailed`.

- [ ] **Step 3: Write minimal implementation**

Append to `pipeline-app/pipeline_app/discovery_x.py`:

```python
BRIGHTDATA_API_BASE = brightdata_job.BRIGHTDATA_API_BASE
REQUEST_TIMEOUT_S = brightdata_job.REQUEST_TIMEOUT_S

# Re-exported so `pytest.raises(discovery_x.BrightDataJobFailed)` works and
# callers need not know where the exceptions live.
BrightDataJobTimeout = brightdata_job.BrightDataJobTimeout
BrightDataJobFailed = brightdata_job.BrightDataJobFailed


def api_key() -> str | None:
    """The Bright Data API token, or None if not configured. Reads this
    module's KEY_ENV_VAR/KEY_FILE at call time so tests can patch them."""
    return brightdata_job.read_key(KEY_ENV_VAR, KEY_FILE)


def profile_url(handle: str) -> str:
    return f"https://x.com/{handle.lstrip('@').strip()}"


def _trigger_job(handle: str, key: str) -> str:
    return brightdata_job.trigger(
        BRIGHTDATA_API_BASE,
        DATASET_ID,
        {
            # A *discovery* job -- "find this account's newest posts".
            # Without type/discover_by, Bright Data reads the input url as a
            # single page to collect, the wrong product mode entirely.
            "type": "discover_new",
            "discover_by": "profile_url",
            # Server-side per-input record cap: the primary cost control.
            "limit_per_input": MAX_ITEMS_PER_RUN,
            "include_errors": "true",
            "notify": "false",
        },
        # No start_date/end_date. Bright Data's snippet accepts them and this
        # dataset does not honor them: a two-day window against an account
        # posting hundreds of times a day returned one error row, error_code
        # 'dead_page' (verified 2026-08-08). There is no backfill path here.
        [{"url": profile_url(handle)}],
        key,
    )


def _poll_job_status(job_id: str, key: str) -> str:
    return brightdata_job.poll_status(BRIGHTDATA_API_BASE, job_id, key)


def _fetch_job_results(job_id: str, key: str) -> list[dict]:
    return brightdata_job.fetch_results(BRIGHTDATA_API_BASE, job_id, key)


def _run_collection_job(handle: str) -> list[dict]:
    key = api_key()
    if key is None:
        raise RuntimeError(
            "Bright Data API key not configured "
            f"(set {KEY_ENV_VAR} or {KEY_FILE.name})"
        )
    # The three lambdas resolve _trigger_job/_poll_job_status/
    # _fetch_job_results through module globals when they run, which is what
    # lets the tests monkeypatch them by name.
    return brightdata_job.await_results(
        trigger_fn=lambda: _trigger_job(handle, key),
        poll_fn=lambda job_id: _poll_job_status(job_id, key),
        fetch_fn=lambda job_id: _fetch_job_results(job_id, key),
        label=f"for {PLATFORM}/{handle}",
        poll_timeout_s=POLL_TIMEOUT_S,
        poll_interval_s=POLL_INTERVAL_S,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_x.py -q`
Expected: PASS — 23 passed.

Note: `test_run_collection_job_raises_on_timeout` monkeypatches `POLL_TIMEOUT_S` to `0`, and `_run_collection_job` reads the module global at call time, so the deadline has already passed on the first poll.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_x.py pipeline-app/tests/test_discovery_x.py
git commit -m "feat(x): wire the Bright Data collection job cycle

Delegates trigger/poll/fetch to brightdata_job, which needs no change.
POLL_TIMEOUT_S is 600 rather than the 300 the other two adapters use, with
a test pinning the divergence: measured latency was 243s at the production
limit_per_input=10.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: `enumerate_newest_first`

The author filter, the sort, the cap, the cache, and the warning that keeps a billed-but-empty run from reading as healthy. This is where both X-specific hazards live.

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_x.py` (append)
- Test: `pipeline-app/tests/test_discovery_x.py` (append)

**Interfaces:**
- Consumes: `_normalize_row`, `_run_collection_job`, `MAX_ITEMS_PER_RUN`, `PLATFORM`.
- Produces: `enumerate_newest_first(handle: str, keyword_filter: str | None) -> list[dict]`, each item `{"id": str, "title": str, "published": str, "content_type": "post"}`; module-level `_ENUMERATE_CACHE: dict[str, dict[str, dict]]` mapping handle → item_id → normalized row.

- [ ] **Step 1: Write the failing test**

Append to `pipeline-app/tests/test_discovery_x.py`:

```python
def _enumerate_with(monkeypatch, rows):
    _fake_key(monkeypatch)
    monkeypatch.setattr(x, "_trigger_job", lambda handle, key: "job1")
    monkeypatch.setattr(x, "_poll_job_status", lambda job_id, key: "ready")
    monkeypatch.setattr(x, "_fetch_job_results", lambda job_id, key: rows)
    monkeypatch.setattr(x.time, "sleep", lambda s: None)


def test_enumerate_drops_posts_written_by_someone_else(monkeypatch):
    """discover_by=profile_url returns the tracked account's TIMELINE, not
    only its authorship. Live job sd_mskdghugb6u3685n6 asked for elonmusk's
    10 newest and returned one authored by arctotherium42. Without this
    filter, output/brand-intel/x/<handle>/ stops meaning 'what this account
    wrote'."""
    _enumerate_with(monkeypatch, [
        _raw_row(id="1", user_posted="elonmusk", date_posted="2026-08-08T04:00:00.000Z"),
        _raw_row(id="2", user_posted="arctotherium42", date_posted="2026-08-07T12:06:57.000Z"),
    ])
    items = x.enumerate_newest_first("elonmusk", None)
    assert [i["id"] for i in items] == ["1"]


def test_enumerate_author_filter_is_case_insensitive(monkeypatch):
    """The handle as registered and user_posted as returned need not agree on
    case -- the live CNN rows carry user_posted 'CNN' while the profile URL
    resolves to x.com/cnn."""
    _enumerate_with(monkeypatch, [_raw_row(id="1", user_posted="CNN")])
    assert [i["id"] for i in x.enumerate_newest_first("cnn", None)] == ["1"]


def test_enumerate_does_not_use_is_repost_as_the_filter(monkeypatch):
    """is_repost was False on the foreign arctotherium42 row, and False on
    all 16 post records observed. It is the field a maintainer will reach for
    and it does not work. This test fails if the filter is 'simplified' to
    is_repost: the foreign row below is explicitly is_repost=False, so an
    is_repost-based filter would keep it."""
    _enumerate_with(monkeypatch, [
        _raw_row(id="1", user_posted="elonmusk", is_repost=False),
        _raw_row(id="2", user_posted="someone_else", is_repost=False),
    ])
    items = x.enumerate_newest_first("elonmusk", None)
    assert [i["id"] for i in items] == ["1"]


def test_enumerate_returns_newest_first_from_unsorted_input(monkeypatch):
    """Rows arrive badly unsorted -- live job 4 returned Aug 6, 8, 7, 6, 7,
    8, 3, 1, 4, 8. The engine's early-stop dedup assumes newest-first."""
    _enumerate_with(monkeypatch, [
        _raw_row(id="old", date_posted="2026-08-01T00:46:44.000Z"),
        _raw_row(id="new", date_posted="2026-08-08T03:54:50.000Z"),
        _raw_row(id="mid", date_posted="2026-08-04T20:57:23.000Z"),
    ])
    items = x.enumerate_newest_first("CNN", None)
    assert [i["id"] for i in items] == ["new", "mid", "old"]


def test_enumerate_sorts_same_day_rows_by_time_of_day(monkeypatch):
    """'published' truncates to the date. Python's sort is stable, so
    same-day rows sorted on the date alone would keep Bright Data's arbitrary
    arrival order -- which can put a genuinely newer post behind ones already
    on disk and trip the early-stop dedup before reaching it."""
    _enumerate_with(monkeypatch, [
        _raw_row(id="early", date_posted="2026-08-08T01:11:45.000Z"),
        _raw_row(id="late", date_posted="2026-08-08T08:54:49.000Z"),
    ])
    items = x.enumerate_newest_first("CNN", None)
    assert [i["id"] for i in items] == ["late", "early"]


def test_enumerate_caps_after_filtering_so_the_cap_bounds_retained_items(monkeypatch):
    rows = [_raw_row(id=str(n), date_posted=f"2026-08-{n:02d}T00:00:00.000Z")
            for n in range(1, 16)]
    _enumerate_with(monkeypatch, rows)
    assert len(x.enumerate_newest_first("CNN", None)) == x.MAX_ITEMS_PER_RUN


def test_enumerate_keeps_media_only_posts(monkeypatch):
    """A media-only post (description: null) is a normal X post, not an
    unusable row. 3 of 10 live rows for one account were media-only."""
    _enumerate_with(monkeypatch, [_raw_row(id="1", description=None)])
    items = x.enumerate_newest_first("CNN", None)
    assert [i["id"] for i in items] == ["1"]
    assert items[0]["title"] == "1"


def test_enumerate_applies_keyword_filter_against_the_body(monkeypatch):
    _enumerate_with(monkeypatch, [
        _raw_row(id="1", description="A daring NASA mission."),
        _raw_row(id="2", description="Senate confirms attorney general."),
    ])
    assert [i["id"] for i in x.enumerate_newest_first("CNN", "nasa")] == ["1"]


def test_enumerate_returns_empty_list_when_the_job_had_nothing(monkeypatch):
    """The one case that honestly means 'nothing to report'."""
    _enumerate_with(monkeypatch, [])
    assert x.enumerate_newest_first("CNN", None) == []


def test_enumerate_warns_when_rows_returned_but_all_filtered(monkeypatch, capsys):
    """A paid batch that yields nothing is recorded by process_handle as the
    healthy status 'no_new_content'. It must be loud here or it is invisible."""
    _enumerate_with(monkeypatch, [
        _raw_row(id="1", user_posted="stranger"),
        _raw_row(id="2", user_posted="another_stranger"),
    ])
    assert x.enumerate_newest_first("CNN", None) == []
    err = capsys.readouterr().err
    assert "none survived filtering" in err
    assert "posts its own content" in err


def test_enumerate_warns_differently_when_all_rows_were_unusable(monkeypatch, capsys):
    """An all-error batch (the include_errors 'dead_page' shape) points at a
    dead or renamed handle, not at authorship. Pointing the operator at the
    wrong cause wastes their time."""
    _enumerate_with(monkeypatch, [
        {"error": "No public posts were found.", "error_code": "dead_page"},
    ])
    assert x.enumerate_newest_first("CNN", None) == []
    err = capsys.readouterr().err
    assert "none survived filtering" in err
    assert "still valid" in err
    assert "posts its own content" not in err


def test_enumerate_caches_rows_for_download_item(monkeypatch):
    _enumerate_with(monkeypatch, [_raw_row(id="1")])
    x.enumerate_newest_first("CNN", None)
    assert x._ENUMERATE_CACHE["CNN"]["1"]["author"] == "CNN"


def test_enumerate_overwrites_rather_than_merges_the_cache(monkeypatch):
    """A fresh successful enumerate replaces whatever the handle held, so
    download_item never reads a stale id from an earlier run in-process."""
    _enumerate_with(monkeypatch, [_raw_row(id="old")])
    x.enumerate_newest_first("CNN", None)
    _enumerate_with(monkeypatch, [_raw_row(id="fresh")])
    x.enumerate_newest_first("CNN", None)
    assert set(x._ENUMERATE_CACHE["CNN"]) == {"fresh"}


def test_enumerate_warns_about_both_causes_when_they_are_mixed(monkeypatch, capsys):
    """A batch that is part error rows and part other people's posts must not
    point the operator at only one cause."""
    _enumerate_with(monkeypatch, [
        {"error": "No public posts were found.", "error_code": "dead_page"},
        _raw_row(id="2", user_posted="stranger"),
    ])
    assert x.enumerate_newest_first("CNN", None) == []
    err = capsys.readouterr().err
    assert "none survived filtering" in err
    assert "valid and posts its own content" in err


def test_enumerate_keys_identity_on_id_not_url(monkeypatch):
    """The dataset returns two different URL shapes -- legacy
    twitter.com/<numeric_profile_id>/status/<id> for CNN and
    x.com/<handle>/status/<id> for elonmusk (both verified live). Anything
    that derived identity from the URL would treat the same account's posts
    as two populations."""
    _enumerate_with(monkeypatch, [
        _raw_row(id="1", url="https://twitter.com/759251/status/1",
                 date_posted="2026-08-08T01:00:00.000Z"),
        _raw_row(id="2", url="https://x.com/CNN/status/2",
                 date_posted="2026-08-08T02:00:00.000Z"),
    ])
    items = x.enumerate_newest_first("CNN", None)
    assert [i["id"] for i in items] == ["2", "1"]
    assert set(x._ENUMERATE_CACHE["CNN"]) == {"1", "2"}


def test_enumerate_returns_a_constant_content_type(monkeypatch):
    """The engine's item shape wants content_type. X's only type-like field
    is is_repost, which is unreliable, so the adapter reports the constant
    'post' and does not write it to disk."""
    _enumerate_with(monkeypatch, [_raw_row(id="1")])
    assert x.enumerate_newest_first("CNN", None)[0]["content_type"] == "post"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_x.py -q`
Expected: FAIL — `AttributeError: module 'pipeline_app.discovery_x' has no attribute 'enumerate_newest_first'`.

- [ ] **Step 3: Write minimal implementation**

Append to `pipeline-app/pipeline_app/discovery_x.py`:

```python
# handle -> item_id -> normalized row. Populated by enumerate_newest_first,
# read by download_item. Calling Bright Data again per item would double-pay
# for posts already collected.
_ENUMERATE_CACHE: dict[str, dict[str, dict]] = {}


def enumerate_newest_first(handle: str, keyword_filter: str | None) -> list[dict]:
    # Raises BrightDataJobTimeout/BrightDataJobFailed -- never swallowed here.
    # An empty return must mean "the job completed and there was nothing".
    raw_rows = _run_collection_job(handle)

    normalized = [_normalize_row(r) for r in raw_rows]
    unusable = sum(1 for n in normalized if n is None)
    kept = [n for n in normalized if n is not None]

    # Authorship filter. discover_by=profile_url returns the account's
    # timeline, including other people's posts (verified live). NOT is_repost,
    # which was False even on the foreign row.
    wanted = handle.lstrip("@").strip().lower()
    before = len(kept)
    kept = [n for n in kept if n["author"].lower() == wanted]
    foreign = before - len(kept)

    if unusable and foreign:
        print(f"  ! {PLATFORM}/{handle}: dropped {unusable} unusable row(s), "
              f"{foreign} row(s) by another author", file=sys.stderr)
    elif unusable:
        print(f"  ! {PLATFORM}/{handle}: dropped {unusable} unusable row(s)",
              file=sys.stderr)
    elif foreign:
        print(f"  ! {PLATFORM}/{handle}: dropped {foreign} row(s) by another author",
              file=sys.stderr)

    if raw_rows and not kept:
        # This run was billed and produced nothing, but process_handle will
        # record the healthy status 'no_new_content' -- indistinguishable from
        # a quiet day unless it is loud here. The advice depends on *why*
        # nothing survived: an all-unusable batch (error rows carrying no id,
        # with include_errors=true) points at a dead or renamed handle, not at
        # authorship.
        if unusable and not foreign:
            advice = "check whether this handle is still valid"
        elif foreign and not unusable:
            advice = "check whether this account posts its own content"
        else:
            advice = "check whether this handle is valid and posts its own content"
        print(f"  !! {PLATFORM}/{handle}: Bright Data returned {len(raw_rows)} "
              f"row(s) but none survived filtering. This run was billed and "
              f"captured nothing -- {advice}.", file=sys.stderr)

    # Rows arrive unsorted (verified live); the engine's early-stop dedup
    # assumes newest-first. Sort on the full timestamp, not the date-truncated
    # 'published': Python's sort is stable, so same-day rows sorted on
    # 'published' alone would keep Bright Data's arbitrary arrival order, which
    # can put a genuinely newer post behind ones already on disk and trip the
    # early-stop dedup before reaching it. Cap AFTER filtering so it bounds
    # retained items.
    kept.sort(key=lambda n: n["published_ts"], reverse=True)
    kept = kept[:MAX_ITEMS_PER_RUN]

    # Overwrite, not merge: a fresh successful enumerate replaces whatever this
    # handle held, so download_item never reads a stale id.
    _ENUMERATE_CACHE[handle] = {n["id"]: n for n in kept}

    items = kept
    if keyword_filter:
        items = [i for i in items if keyword_filter.lower() in i["body"].lower()]
    return [
        # content_type is a constant. X's only type-like field is is_repost,
        # which was False even on a post the account did not write; a field
        # that is always False would be worse than absent, so it is neither
        # reported nor written to disk.
        {"id": i["id"], "title": i["title"], "published": i["published"],
         "content_type": "post"}
        for i in items
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_x.py -q`
Expected: PASS — 39 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_x.py pipeline-app/tests/test_discovery_x.py
git commit -m "feat(x): filter by user_posted, sort newest-first, cache for download

The authorship filter is user_posted, not is_repost -- a live job for
elonmusk returned a post by arctotherium42 with is_repost False. A test
pins that, so simplifying the filter to the obvious field fails loudly.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: On-disk reads and writes

The remaining three `PlatformAdapter` functions.

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_x.py` (append)
- Test: `pipeline-app/tests/test_discovery_x.py` (append)

**Interfaces:**
- Consumes: `_ENUMERATE_CACHE`, `PLATFORM`, `handle_dir`, `artifacts.render_frontmatter`.
- Produces: `on_disk_ids(repo_root: Path, handle: str) -> set[str]`; `peek_upload_date(item_id: str) -> None`; `download_item(repo_root: Path, handle: str, item_id: str, title: str, content_type: str | None = None) -> dict` returning `{"id": str, "ok": True, "published": str}`.

- [ ] **Step 1: Write the failing test**

Append to `pipeline-app/tests/test_discovery_x.py`:

```python
def test_on_disk_ids_reads_filename_stems(tmp_path):
    """The ids Bright Data returns are JSON strings, and on_disk_ids compares
    against filename stems. A numeric id would never match, so every run
    would re-download and re-pay in silence."""
    directory = tmp_path / "output" / "brand-intel" / "x" / "cnn"
    directory.mkdir(parents=True)
    (directory / "2085896713185714235.md").write_text("x", encoding="utf-8")
    (directory / "notes.txt").write_text("x", encoding="utf-8")
    assert x.on_disk_ids(tmp_path, "CNN") == {"2085896713185714235"}


def test_on_disk_ids_empty_when_directory_absent(tmp_path):
    assert x.on_disk_ids(tmp_path, "CNN") == set()


def test_peek_upload_date_is_none():
    """Dead code by design: enumerate_newest_first only ever returns items
    carrying a normalized 'published', so process_handle never falls through
    to this -- same as discovery_bluesky/instagram/linkedin."""
    assert x.peek_upload_date("1") is None


def test_download_item_writes_frontmatter_and_body(monkeypatch, tmp_path):
    _enumerate_with(monkeypatch, [_raw_row()])
    x.enumerate_newest_first("CNN", None)
    result = x.download_item(tmp_path, "CNN", "2085896713185714235", "title")

    assert result == {"id": "2085896713185714235", "ok": True,
                      "published": "2026-08-08"}
    dest = tmp_path / "output" / "brand-intel" / "x" / "cnn" / "2085896713185714235.md"
    text = dest.read_text(encoding="utf-8")
    assert "post_id: '2085896713185714235'" in text
    assert "author: CNN" in text
    assert "published: '2026-08-08'" in text
    assert "like_count: 310" in text
    assert "comment_count: 85" in text
    assert "repost_count: 64" in text
    assert "view_count: 214564" in text
    assert "bookmark_count: 16" in text
    assert "quote_count: 6" in text
    assert "external_url: https://cnn.it/45aXVbJ" in text
    assert "https://pbs.twimg.com/media/HPKX_XjXUAAxkvS.jpg" in text
    assert "A daring mission" in text


def test_download_item_writes_empty_marker_for_media_only_posts(monkeypatch, tmp_path):
    """A media-only post is kept with the '(empty)' body Instagram and
    LinkedIn already use -- the media URLs and engagement counts are what
    make the file worth having."""
    _enumerate_with(monkeypatch, [_raw_row(
        id="1", description=None, photos=None,
        videos=[{"video_url": "https://video.twimg.com/a.mp4", "duration": 6041}])])
    x.enumerate_newest_first("CNN", None)
    x.download_item(tmp_path, "CNN", "1", "title")

    text = (tmp_path / "output" / "brand-intel" / "x" / "cnn" / "1.md").read_text(
        encoding="utf-8")
    assert "(empty)" in text
    assert "https://video.twimg.com/a.mp4" in text


def test_download_item_does_not_write_content_type(monkeypatch, tmp_path):
    """is_repost is unreliable, so no content_type is recorded. A key that
    always said 'post' would assert that the account never reposts."""
    _enumerate_with(monkeypatch, [_raw_row(id="1")])
    x.enumerate_newest_first("CNN", None)
    x.download_item(tmp_path, "CNN", "1", "title", content_type="post")
    text = (tmp_path / "output" / "brand-intel" / "x" / "cnn" / "1.md").read_text(
        encoding="utf-8")
    assert "content_type" not in text


def test_download_item_makes_no_second_network_call(monkeypatch, tmp_path):
    """Calling Bright Data once per item would double-pay for posts already
    collected by enumerate_newest_first."""
    _enumerate_with(monkeypatch, [_raw_row(id="1")])
    x.enumerate_newest_first("CNN", None)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("download_item must read the cache, not the API")

    monkeypatch.setattr(x, "_run_collection_job", _fail_if_called)
    monkeypatch.setattr(x, "_trigger_job", _fail_if_called)
    assert x.download_item(tmp_path, "CNN", "1", "title")["ok"] is True


def test_download_item_raises_on_cache_miss(monkeypatch, tmp_path):
    """A missing handle or id is a programming error. KeyError propagates to
    run_discovery's per-handle error path, surfacing as a normal 'error'
    rather than failing silently."""
    _enumerate_with(monkeypatch, [_raw_row(id="1")])
    x.enumerate_newest_first("CNN", None)
    with pytest.raises(KeyError):
        x.download_item(tmp_path, "CNN", "absent", "title")


def test_download_item_leaves_no_tmp_file(monkeypatch, tmp_path):
    """Write-temp-then-rename: an interrupted write must never leave a
    truncated file at a path on_disk_ids() would treat as captured."""
    _enumerate_with(monkeypatch, [_raw_row(id="1")])
    x.enumerate_newest_first("CNN", None)
    x.download_item(tmp_path, "CNN", "1", "title")
    directory = tmp_path / "output" / "brand-intel" / "x" / "cnn"
    assert [p.name for p in directory.iterdir()] == ["1.md"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_x.py -q`
Expected: FAIL — `AttributeError: module 'pipeline_app.discovery_x' has no attribute 'on_disk_ids'`.

- [ ] **Step 3: Write minimal implementation**

Append to `pipeline-app/pipeline_app/discovery_x.py`:

```python
def on_disk_ids(repo_root: Path, handle: str) -> set[str]:
    directory = handle_dir(repo_root, PLATFORM, handle)
    if not directory.exists():
        return set()
    return {p.stem for p in directory.glob("*.md")}


def peek_upload_date(item_id: str) -> str | None:
    # Dead code by design: enumerate_newest_first only ever returns items
    # carrying a normalized 'published' date, so process_handle's
    # `item.get("published") or adapter.peek_upload_date(...)` never falls
    # through -- same as discovery_bluesky/instagram/linkedin.
    return None


def download_item(repo_root: Path, handle: str, item_id: str, title: str,
                  content_type: str | None = None) -> dict:
    # A missing handle or item_id is a programming error: every engine call
    # path runs enumerate_newest_first for this handle first. KeyError
    # propagates to run_discovery's per-handle error path rather than being
    # caught here, so it surfaces as a normal 'error' instead of failing
    # silently. content_type is accepted to satisfy the protocol and ignored:
    # X has no reliable type field (see enumerate_newest_first).
    cached = _ENUMERATE_CACHE[handle][item_id]

    out_dir = handle_dir(repo_root, PLATFORM, handle)
    out_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    meta = {
        "post_id": cached["id"],
        "url": cached["url"],
        "handle": handle,
        # Recorded even though the filter guarantees it matches the handle:
        # it is what makes a filtering regression detectable after the fact.
        "author": cached["author"],
        "published": cached["published"],
        "like_count": cached["like_count"],
        "comment_count": cached["comment_count"],
        "repost_count": cached["repost_count"],
        "view_count": cached["view_count"],
        "bookmark_count": cached["bookmark_count"],
        "quote_count": cached["quote_count"],
        "hashtags": cached["hashtags"],
        # Pointers, not an archive -- pbs.twimg.com and video.twimg.com URLs
        # expire. No media is downloaded.
        "photos": cached["photos"],
        "videos": cached["videos"],
        "external_url": cached["external_url"],
        "fetched_at": fetched_at,
    }
    body = cached["body"] or "(empty)"

    dest = out_dir / f"{item_id}.md"
    # Write-temp-then-rename, same as every other adapter: an interrupted
    # write must never leave a truncated file at a path on_disk_ids() would
    # treat as already-captured.
    tmp_dest = dest.with_name(dest.name + ".tmp")
    tmp_dest.write_text(artifacts.render_frontmatter(meta, body), encoding="utf-8")
    tmp_dest.replace(dest)
    return {"id": item_id, "ok": True, "published": cached["published"]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_x.py -q`
Expected: PASS — 48 passed.

If a frontmatter assertion fails on quoting, check the actual rendered YAML — `yaml.safe_dump` quotes numeric-looking strings (`post_id: '2085896713185714235'`) but not plain ones (`author: CNN`). Adjust the assertion to the real output; do not change the field values.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_x.py pipeline-app/tests/test_discovery_x.py
git commit -m "feat(x): read on-disk ids and write post artifacts

Frontmatter carries six engagement counts, media URL pointers and the
outbound link, and deliberately omits content_type: X's only type-like
field is is_repost, which is unreliable.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Register the platform

**Files:**
- Modify: `pipeline-app/run_discovery_cron.py:23` (import) and `:31-41` (`build_adapters`)
- Modify: `pipeline-app/pipeline_app/templates/discovery_handles.html:32-39`
- Test: `pipeline-app/tests/test_run_discovery_cron.py` (append)

**Interfaces:**
- Consumes: the `discovery_x` module from Tasks 1–4.
- Produces: `build_adapters()["x"]` is the `discovery_x` module.

- [ ] **Step 1: Write the failing test**

Append to `pipeline-app/tests/test_run_discovery_cron.py`:

```python
def test_x_is_registered_as_an_adapter():
    from pipeline_app import discovery_x

    assert cron.build_adapters()["x"] is discovery_x


def test_x_is_excluded_from_backfill():
    """discovery_engine rejects any platform outside this whitelist before an
    adapter is called, so a backfill request can never trigger a paid X job.
    That matters more here than for LinkedIn: X's start_date/end_date were
    tested and return an error row, so there is no backfill path at all."""
    from pipeline_app.discovery_engine import BACKFILL_SUPPORTED_PLATFORMS

    assert "x" not in BACKFILL_SUPPORTED_PLATFORMS


def test_x_adapter_satisfies_the_platform_adapter_protocol():
    """The protocol is structural, so a missing function surfaces only at
    runtime, mid-run, after a job has been billed."""
    adapter = cron.build_adapters()["x"]
    for name in ("enumerate_newest_first", "on_disk_ids", "peek_upload_date",
                 "download_item"):
        assert callable(getattr(adapter, name)), name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_run_discovery_cron.py -q`
Expected: FAIL — `KeyError: 'x'` in `test_x_is_registered_as_an_adapter`. (`test_x_is_excluded_from_backfill` passes immediately — the whitelist already excludes it, which is the point.)

- [ ] **Step 3: Write minimal implementation**

In `pipeline-app/run_discovery_cron.py`, extend the import on line 23:

```python
from pipeline_app import (discovery_bluesky, discovery_instagram, discovery_linkedin,
                          discovery_x, discovery_youtube)
```

And add the entry in `build_adapters()`:

```python
    return {
        "youtube": discovery_youtube,
        "bluesky": discovery_bluesky,
        "instagram": discovery_instagram,
        "linkedin-profile": discovery_linkedin.profile_adapter(),
        "linkedin-company": discovery_linkedin.company_adapter(),
        # A plain module, not an instance: X has one working mode, so it needs
        # neither LinkedIn's per-instance cache nor its bound-mode class.
        "x": discovery_x,
    }
```

In `pipeline-app/pipeline_app/templates/discovery_handles.html`, add the option after the LinkedIn entries and widen the placeholder:

```html
    <option value="linkedin-company">LinkedIn — company posts</option>
    <option value="x">X (Twitter)</option>
  </select>
  <input name="handle" placeholder="@handle, actor.bsky.social, or linkedin slug" required>
```

becomes:

```html
    <option value="linkedin-company">LinkedIn — company posts</option>
    <option value="x">X (Twitter)</option>
  </select>
  <input name="handle" placeholder="@handle, actor.bsky.social, or linkedin/x slug" required>
```

The stored value is `x`; the label carries "(Twitter)" because a bare "X" is not self-evident in a dropdown.

- [ ] **Step 4: Run the whole suite**

Run: `cd pipeline-app && python -m pytest tests/ -q`
Expected: PASS — all tests, including the 44 pre-existing LinkedIn tests and the 38 Instagram tests, which must not have changed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/run_discovery_cron.py pipeline-app/pipeline_app/templates/discovery_handles.html pipeline-app/tests/test_run_discovery_cron.py
git commit -m "feat(x): register the X platform in the discovery pipeline

discovery_engine is untouched -- BACKFILL_SUPPORTED_PLATFORMS is a
whitelist, so x is already rejected from backfill with a logged skip.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Post-implementation verification

Not a task — an operator step, because it costs money and needs the network.

1. Confirm `BRIGHTDATA_API_KEY` is set and Bright Data's domains resolve. DNS-filtering resolvers that categorize proxy and scraping infrastructure — on this machine, Proton VPN's NetShield — NXDOMAIN them, and every job then fails at name resolution before any HTTP call.
2. Register one handle through the UI and let validation run. Expect a job of roughly 75–250s.
3. Check `output/brand-intel/x/<handle>/` for `.md` files whose `author` matches the handle, and confirm no `.tmp` files remain.
4. Re-run the same handle. The second run should write **no new files** (`on_disk_ids` dedup) while still costing a job — that is the known, accepted re-pay described in the spec's cost model.
5. Check the Bright Data dashboard's usage page against the six verification jobs plus these, to finally settle the `[T-unverified]` billing-granularity question the Instagram, LinkedIn, and X designs have all left open.
