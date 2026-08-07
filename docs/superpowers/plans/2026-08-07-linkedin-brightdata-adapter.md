# LinkedIn Bright Data Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two LinkedIn discovery platforms — `linkedin-profile` (a person's own posts) and `linkedin-company` (an organization's posts) — backed by Bright Data, over a shared job client extracted from the existing Instagram adapter.

**Architecture:** A new `brightdata_job.py` owns everything Bright Data-generic (key lookup, the trigger/poll/fetch HTTP calls, the poll loop with timeout and failure semantics, the two exception classes). `discovery_instagram.py` is refactored to delegate to it with zero behavior change. A new `discovery_linkedin.py` exposes a `LinkedInAdapter` class bound to a mode at construction; `build_adapters()` registers one instance per mode. `discovery_engine.py` is not modified.

**Tech Stack:** Python 3, `requests`, `pytest`, `PyYAML` (via `pipeline_app.artifacts.render_frontmatter`), SQLite.

**Spec:** [`docs/superpowers/specs/2026-08-07-linkedin-brightdata-adapter-design.md`](../specs/2026-08-07-linkedin-brightdata-adapter-design.md)

## Global Constraints

- All commands run from `pipeline-app/` unless stated otherwise. Test command: `python -m pytest tests/ -v`.
- Bright Data LinkedIn dataset id: `gd_lyy3tktm25m4avu764`. Not a secret; a module constant.
- `MAX_ITEMS_PER_RUN = 10` for both LinkedIn modes.
- `POLL_TIMEOUT_S = 300`, `POLL_INTERVAL_S = 5`, `REQUEST_TIMEOUT_S = 30`.
- API key lookup order: `BRIGHTDATA_API_KEY` env var, then the gitignored `brightdata_api_key.txt`. Already gitignored — do not add it again.
- **Never make a real Bright Data call from a test.** Every test stubs the HTTP layer or the job cycle. Real calls cost money.
- **A failed or timed-out job must raise, never return `[]`.** An empty return means "the job completed and there was genuinely nothing", which the engine records as the healthy status `no_new_content`. This distinction is the whole reason the adapter has custom exceptions.
- **Extraction gate (Task 1):** all 38 existing tests in `tests/test_discovery_instagram.py` must pass **unchanged**. Do not edit that file. If a change there seems necessary, the refactor is wrong — fix the refactor.
- Field names below come from four live Bright Data jobs on 2026-08-07 (snapshots `sd_msizuwoz1sxczzt49`, `sd_msizuxvm1zh3lphp44`, `sd_msizuz58ydxnt505b`, `sd_msizymmw2pq7uwbs0v`). They are observed, not documented. Do not "correct" them against Bright Data's published field list.

## File Structure

| File | Responsibility |
|---|---|
| `pipeline_app/brightdata_job.py` | **Create.** Bright Data-generic: key lookup, trigger/poll/fetch HTTP, the poll loop, `BrightDataJobTimeout` / `BrightDataJobFailed`. Knows nothing about Instagram or LinkedIn. |
| `pipeline_app/discovery_instagram.py` | **Modify.** Keeps every public and private name it has today; the bodies delegate to `brightdata_job`. |
| `pipeline_app/discovery_linkedin.py` | **Create.** LinkedIn-only: dataset id, the two modes, URL templates, author filter, row normalization, `LinkedInAdapter`. |
| `run_discovery_cron.py` | **Modify.** `build_adapters()` gains two entries. |
| `pipeline_app/templates/discovery_handles.html` | **Modify.** Two new `<option>` values. |
| `tests/test_brightdata_job.py` | **Create.** Covers the shared client directly. |
| `tests/test_discovery_linkedin.py` | **Create.** Covers normalization, enumerate, and file writing. |
| `tests/test_run_discovery_cron.py` | **Modify.** One existing assertion on the adapter-registry key set. |

---

### Task 1: Extract the shared Bright Data job client

`discovery_instagram.py`'s trigger → poll → fetch cycle is the part that was expensive to get right, and its error discipline is what keeps a paid failure from reading as healthy. Move it somewhere both adapters can use, proving nothing changed by leaving the Instagram tests untouched.

The refactor works because the Instagram tests monkeypatch *module attributes looked up at call time* (`ig._trigger_job`, `ig.POLL_TIMEOUT_S`) and *shared stdlib modules* (`ig.requests.post`, `ig.time.sleep` — the same module objects `brightdata_job` imports). Keep every one of those names on `discovery_instagram` and the patches keep biting.

**Files:**
- Create: `pipeline-app/pipeline_app/brightdata_job.py`
- Modify: `pipeline-app/pipeline_app/discovery_instagram.py`
- Test: `pipeline-app/tests/test_brightdata_job.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces, all importable as `from pipeline_app import brightdata_job`:
  - `BRIGHTDATA_API_BASE: str` — `"https://api.brightdata.com/datasets/v3"`
  - `REQUEST_TIMEOUT_S: int` — `30`
  - `class BrightDataJobTimeout(Exception)`
  - `class BrightDataJobFailed(Exception)`
  - `read_key(env_var: str, key_file: Path) -> str | None`
  - `trigger(api_base: str, dataset_id: str, params: dict, body: list[dict], key: str) -> str` — returns `snapshot_id`
  - `poll_status(api_base: str, job_id: str, key: str) -> str`
  - `fetch_results(api_base: str, job_id: str, key: str) -> list[dict]`
  - `await_results(trigger_fn, poll_fn, fetch_fn, *, label: str, poll_timeout_s: float, poll_interval_s: float) -> list[dict]` where `trigger_fn() -> str`, `poll_fn(job_id) -> str`, `fetch_fn(job_id) -> list[dict]`

- [ ] **Step 1: Write the failing tests**

Create `pipeline-app/tests/test_brightdata_job.py`:

```python
from pathlib import Path

import pytest

from pipeline_app import brightdata_job as bd


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_read_key_prefers_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("SOME_KEY", "env-key")
    key_file = tmp_path / "key.txt"
    key_file.write_text("file-key", encoding="utf-8")
    assert bd.read_key("SOME_KEY", key_file) == "env-key"


def test_read_key_falls_back_to_file_and_strips(monkeypatch, tmp_path):
    monkeypatch.delenv("SOME_KEY", raising=False)
    key_file = tmp_path / "key.txt"
    key_file.write_text("  file-key\n", encoding="utf-8")
    assert bd.read_key("SOME_KEY", key_file) == "file-key"


def test_read_key_none_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv("SOME_KEY", raising=False)
    assert bd.read_key("SOME_KEY", tmp_path / "absent.txt") is None


def test_trigger_posts_dataset_id_with_extra_params_and_returns_snapshot_id(monkeypatch):
    captured = {}

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        captured.update(url=url, params=params, headers=headers, json=json, timeout=timeout)
        return _FakeResponse({"snapshot_id": "snap123"})

    monkeypatch.setattr(bd.requests, "post", fake_post)
    result = bd.trigger("https://api.example/v3", "gd_abc",
                        {"type": "discover_new"}, [{"url": "u"}], "the-key")

    assert result == "snap123"
    assert captured["url"] == "https://api.example/v3/trigger"
    assert captured["params"] == {"dataset_id": "gd_abc", "type": "discover_new"}
    assert captured["headers"]["Authorization"] == "Bearer the-key"
    assert captured["json"] == [{"url": "u"}]
    assert captured["timeout"] == bd.REQUEST_TIMEOUT_S


def test_poll_status_returns_status_field(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured.update(url=url, headers=headers)
        return _FakeResponse({"status": "ready"})

    monkeypatch.setattr(bd.requests, "get", fake_get)
    assert bd.poll_status("https://api.example/v3", "job1", "the-key") == "ready"
    assert captured["url"] == "https://api.example/v3/progress/job1"
    assert captured["headers"]["Authorization"] == "Bearer the-key"


def test_fetch_results_requests_json_format(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured.update(url=url, params=params)
        return _FakeResponse([{"id": "1"}])

    monkeypatch.setattr(bd.requests, "get", fake_get)
    assert bd.fetch_results("https://api.example/v3", "job1", "the-key") == [{"id": "1"}]
    assert captured["url"] == "https://api.example/v3/snapshot/job1"
    assert captured["params"] == {"format": "json"}


def test_await_results_returns_rows_once_ready(monkeypatch):
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    statuses = iter(["running", "running", "ready"])
    rows = bd.await_results(
        trigger_fn=lambda: "job1",
        poll_fn=lambda job_id: next(statuses),
        fetch_fn=lambda job_id: [{"id": "1"}],
        label="for someone", poll_timeout_s=300, poll_interval_s=5,
    )
    assert rows == [{"id": "1"}]


def test_await_results_raises_on_failed_status(monkeypatch):
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    with pytest.raises(bd.BrightDataJobFailed, match="job1 for someone failed"):
        bd.await_results(
            trigger_fn=lambda: "job1",
            poll_fn=lambda job_id: "failed",
            fetch_fn=lambda job_id: [],
            label="for someone", poll_timeout_s=300, poll_interval_s=5,
        )


def test_await_results_raises_on_timeout(monkeypatch):
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    monkeypatch.setattr(bd.time, "monotonic", lambda: 10_000.0)
    with pytest.raises(bd.BrightDataJobTimeout, match="timed out"):
        bd.await_results(
            trigger_fn=lambda: "job1",
            poll_fn=lambda job_id: "running",  # never ready
            fetch_fn=lambda job_id: [],
            label="for someone", poll_timeout_s=0, poll_interval_s=5,
        )


def test_await_results_never_fetches_when_job_fails(monkeypatch):
    """A failed job must raise, not fall through to an empty fetch -- an empty
    return would be recorded by the engine as the healthy status
    'no_new_content' for a batch that was billed."""
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)

    def _fail_if_called(job_id):
        raise AssertionError("fetch must not run for a failed job")

    with pytest.raises(bd.BrightDataJobFailed):
        bd.await_results(
            trigger_fn=lambda: "job1",
            poll_fn=lambda job_id: "failed",
            fetch_fn=_fail_if_called,
            label="for someone", poll_timeout_s=300, poll_interval_s=5,
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_brightdata_job.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'pipeline_app.brightdata_job'`

- [ ] **Step 3: Create the shared client**

Create `pipeline-app/pipeline_app/brightdata_job.py`:

```python
"""Bright Data Web Scraper API v3 job client, shared by every Bright
Data-backed discovery adapter (discovery_instagram, discovery_linkedin).

Bright Data's API is asynchronous -- trigger -> poll -> fetch -- and bills per
job/record. The error discipline in await_results is the load-bearing part: a
job that times out or reports 'failed' MUST raise, never return []. An empty
list means "the job completed and there was genuinely nothing", which
discovery_engine records as the healthy status 'no_new_content'. Returning []
on failure would make a paid, failed job indistinguishable from a quiet day --
the exact bug that shipped in the first Instagram adapter.

This module knows nothing about any particular dataset. Callers supply the
dataset id, the query params that select the product mode, and the request
body.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests

BRIGHTDATA_API_BASE = "https://api.brightdata.com/datasets/v3"
REQUEST_TIMEOUT_S = 30


class BrightDataJobTimeout(Exception):
    """A Bright Data collection job did not reach 'ready' within the deadline."""


class BrightDataJobFailed(Exception):
    """A Bright Data collection job reported status 'failed'."""


def read_key(env_var: str, key_file: Path) -> str | None:
    """The Bright Data API token, or None if not configured. Env var first --
    the scheduled task inherits the User environment -- then a gitignored
    file for convenience, matching discovery_youtube_api.api_key()."""
    env_key = os.environ.get(env_var, "").strip()
    if env_key:
        return env_key
    if key_file.exists():
        file_key = key_file.read_text(encoding="utf-8").strip()
        if file_key:
            return file_key
    return None


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def trigger(api_base: str, dataset_id: str, params: dict, body: list[dict], key: str) -> str:
    """Start a collection job; returns its snapshot id.

    `params` carries the product-mode selectors (type, discover_by,
    limit_per_input, ...) and is merged over dataset_id. `body` is a bare
    array -- /trigger's documented shape, verified live. The dashboard's
    {"input": [...]} object form belongs to the synchronous /scrape endpoint,
    which no adapter uses: a discovery job takes minutes and would hang an
    HTTP call.
    """
    response = requests.post(
        f"{api_base}/trigger",
        params={"dataset_id": dataset_id, **params},
        headers=_auth(key),
        json=body,
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()["snapshot_id"]


def poll_status(api_base: str, job_id: str, key: str) -> str:
    response = requests.get(
        f"{api_base}/progress/{job_id}",
        headers=_auth(key),
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()["status"]


def fetch_results(api_base: str, job_id: str, key: str) -> list[dict]:
    response = requests.get(
        f"{api_base}/snapshot/{job_id}",
        params={"format": "json"},
        headers=_auth(key),
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()


def await_results(trigger_fn, poll_fn, fetch_fn, *, label: str,
                  poll_timeout_s: float, poll_interval_s: float) -> list[dict]:
    """Run one full trigger -> poll -> fetch cycle.

    The three callables are injected rather than called directly so each
    adapter keeps its own module-level trigger/poll/fetch functions -- which
    is what lets adapter tests monkeypatch them. `label` is interpolated into
    error messages (e.g. "for nike") so a failure names the handle.
    """
    job_id = trigger_fn()
    deadline = time.monotonic() + poll_timeout_s
    while True:
        status = poll_fn(job_id)
        if status == "ready":
            return fetch_fn(job_id)
        if status == "failed":
            raise BrightDataJobFailed(f"Bright Data job {job_id} {label} failed")
        if time.monotonic() >= deadline:
            raise BrightDataJobTimeout(
                f"Bright Data job {job_id} {label} timed out after {poll_timeout_s}s"
            )
        time.sleep(poll_interval_s)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_brightdata_job.py -v`
Expected: 10 passed

- [ ] **Step 5: Refactor `discovery_instagram.py` to delegate**

In `pipeline-app/pipeline_app/discovery_instagram.py`, replace the import block, the two exception classes, `api_key`, and the bodies of the four job functions. Everything else in the file stays exactly as it is — including these, which tests read or patch by name and which keep their current definitions and values: `KEY_ENV_VAR`, `KEY_FILE`, `DATASET_ID`, `MAX_ITEMS_PER_RUN`, `POLL_TIMEOUT_S`, `POLL_INTERVAL_S`, `_parse_published`, `_normalize_row`, `_ENUMERATE_CACHE`, `enumerate_newest_first`, `on_disk_ids`, `peek_upload_date`, `download_item`.

Replace the imports and the `BRIGHTDATA_API_BASE` / `REQUEST_TIMEOUT_S` constants (`os` is no longer needed; `time` and `requests` are kept unused so the existing tests can still patch through them):

```python
import datetime as _dt
import sys
import time  # noqa: F401 -- kept so tests can monkeypatch ig.time.sleep/monotonic
from pathlib import Path

import requests  # noqa: F401 -- kept so tests can monkeypatch ig.requests.post/get

from pipeline_app import artifacts, brightdata_job
from pipeline_app.discovery_paths import handle_dir

BRIGHTDATA_API_BASE = brightdata_job.BRIGHTDATA_API_BASE
REQUEST_TIMEOUT_S = brightdata_job.REQUEST_TIMEOUT_S

# Re-exported so `pytest.raises(discovery_instagram.BrightDataJobFailed)` keeps
# working and callers need not know the exceptions moved.
BrightDataJobTimeout = brightdata_job.BrightDataJobTimeout
BrightDataJobFailed = brightdata_job.BrightDataJobFailed
```

Delete the two `class BrightDataJob...(Exception)` definitions. Replace `api_key` and the four job functions:

```python
def api_key() -> str | None:
    """The Bright Data API token, or None if not configured. Reads this
    module's KEY_ENV_VAR/KEY_FILE at call time so tests can patch them."""
    return brightdata_job.read_key(KEY_ENV_VAR, KEY_FILE)


def _trigger_job(handle: str, key: str) -> str:
    if DATASET_ID.startswith("gd_REPLACE"):
        raise RuntimeError(
            "Instagram adapter DATASET_ID is still a placeholder -- provision the "
            "Bright Data Instagram Posts Scraper API product and set the real "
            "dataset id in discovery_instagram.py"
        )
    profile_url = f"https://www.instagram.com/{handle.lstrip('@')}/"
    return brightdata_job.trigger(
        BRIGHTDATA_API_BASE,
        DATASET_ID,
        {
            # This is a *discovery* job -- "find this profile's newest posts".
            # Without type/discover_by, Bright Data reads the input url as a
            # single post page to collect, which is the wrong product mode for
            # a profile URL. Values from the dashboard's generated snippet.
            "type": "discover_new",
            "discover_by": "url",
            # Server-side per-input record cap: the primary cost control, and
            # the one that binds even if the dataset ignores num_of_posts.
            "limit_per_input": MAX_ITEMS_PER_RUN,
            "include_errors": "true",
            "notify": "false",
        },
        [{
            "url": profile_url,
            "num_of_posts": MAX_ITEMS_PER_RUN,
            "start_date": "",
            "end_date": "",
            "post_type": "",
        }],
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
    # The three lambdas resolve _trigger_job/_poll_job_status/_fetch_job_results
    # through module globals when they run, which is what keeps the existing
    # monkeypatch-based tests working after the extraction.
    return brightdata_job.await_results(
        trigger_fn=lambda: _trigger_job(handle, key),
        poll_fn=lambda job_id: _poll_job_status(job_id, key),
        fetch_fn=lambda job_id: _fetch_job_results(job_id, key),
        label=f"for {handle}",
        poll_timeout_s=POLL_TIMEOUT_S,
        poll_interval_s=POLL_INTERVAL_S,
    )
```

- [ ] **Step 6: Run the extraction gate**

Run: `python -m pytest tests/test_discovery_instagram.py -v`
Expected: **38 passed**, with `tests/test_discovery_instagram.py` unmodified. If any test fails, fix `discovery_instagram.py` — do not edit the test file.

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest tests/ -v`
Expected: all pass (524 passed / 3 skipped before this task, plus the 10 new `test_brightdata_job.py` tests)

- [ ] **Step 8: Commit**

```bash
git add pipeline-app/pipeline_app/brightdata_job.py pipeline-app/pipeline_app/discovery_instagram.py pipeline-app/tests/test_brightdata_job.py
git commit -m "refactor: extract shared Bright Data job client from Instagram adapter"
```

---

### Task 2: LinkedIn row normalization

Pure functions turning one raw Bright Data row into the shape the adapter works with. Every mapping is pinned to a live-observed value, because the Instagram adapter's worst bug was a field assumption that looked right and silently dropped everything.

**Files:**
- Create: `pipeline-app/pipeline_app/discovery_linkedin.py`
- Test: `pipeline-app/tests/test_discovery_linkedin.py`

**Interfaces:**
- Consumes: nothing from Task 1 yet.
- Produces:
  - `DATASET_ID: str`, `MAX_ITEMS_PER_RUN: int`, `KEY_ENV_VAR: str`, `KEY_FILE: Path`
  - `_parse_published(raw: str | None) -> str | None`
  - `_normalize_row(row: dict) -> dict | None` returning keys `id, title, published, content_type, author, account_type, body, url, like_count, comment_count, hashtags`

- [ ] **Step 1: Write the failing tests**

Create `pipeline-app/tests/test_discovery_linkedin.py`:

```python
from pipeline_app import discovery_linkedin as li


def test_parse_published_accepts_the_verified_iso_format():
    """Live LinkedIn rows carry real ISO 8601 UTC -- 2026-07-08T14:00:09.491Z
    (verified 2026-08-07). Note this DIFFERS from the Instagram product, which
    returns a US-format local timestamp; the two Bright Data datasets do not
    agree, which is why neither may be assumed from the other."""
    assert li._parse_published("2026-07-08T14:00:09.491Z") == "2026-07-08"
    assert li._parse_published("2026-07-08") == "2026-07-08"


def test_parse_published_rejects_unusable_values():
    assert li._parse_published("") is None
    assert li._parse_published(None) is None
    assert li._parse_published("not a date") is None
    # A US-format date is NOT silently reinterpreted -- guessing between
    # MM/DD and DD/MM would produce wrong dates, which is worse than a
    # dropped row, and dropped rows are logged.
    assert li._parse_published("07/08/2026 14:00:09") is None


def _raw_row(**overrides):
    """A row shaped like the live payload from snapshot sd_msizuwoz1sxczzt49."""
    row = {
        "id": "7480621754537701376",
        "date_posted": "2026-07-08T14:00:09.491Z",
        "post_type": "post",
        "account_type": "Person",
        "user_id": "bettywliu",
        "user_name": "Betty Liu",
        "headline": "Your personal brand isn't your resume.",
        "title": "#personalbrand #leadership #careeradvice | Betty Liu",
        "post_text": "Your personal brand isn't your resume.\n\nIt's what people say.",
        "original_post_text": "Your personal brand isn&apos;t your resume.",
        "post_text_html": "<a class=\"link\">markup</a>",
        "url": "https://www.linkedin.com/posts/bettywliu_personalbrand-activity-748",
        "num_likes": 74,
        "num_comments": 9,
        "hashtags": ["#personalbrand", "#leadership"],
    }
    row.update(overrides)
    return row


def test_normalize_row_maps_every_verified_field():
    n = li._normalize_row(_raw_row())
    assert n["id"] == "7480621754537701376"
    assert n["published"] == "2026-07-08"
    assert n["content_type"] == "post"
    assert n["account_type"] == "person"
    assert n["author"] == "bettywliu"
    assert n["like_count"] == 74
    assert n["comment_count"] == 9
    assert n["hashtags"] == ["#personalbrand", "#leadership"]


def test_normalize_row_body_comes_from_post_text_not_the_markup_fields():
    """post_text is the clean body -- entities decoded, links flattened.
    original_post_text and post_text_html are LONGER but carry &apos; and
    <a class="link"> markup. Reading the longer field would quietly fill the
    corpus with HTML for posts already paid for."""
    n = li._normalize_row(_raw_row())
    assert n["body"].startswith("Your personal brand isn't your resume.")
    assert "&apos;" not in n["body"]
    assert "<a" not in n["body"]


def test_normalize_row_title_prefers_headline_over_the_seo_title_field():
    """The `title` field is SEO text with hashtags and the author appended.
    `headline` is the post's own first line."""
    n = li._normalize_row(_raw_row())
    assert n["title"] == "Your personal brand isn't your resume."
    assert "#personalbrand" not in n["title"]


def test_normalize_row_title_falls_back_to_first_line_then_id():
    no_headline = li._normalize_row(_raw_row(headline="", post_text="First line.\nSecond line."))
    assert no_headline["title"] == "First line."
    nothing = li._normalize_row(_raw_row(headline="", post_text=""))
    assert nothing["title"] == "7480621754537701376"


def test_normalize_row_truncates_title_to_60_chars():
    n = li._normalize_row(_raw_row(headline="x" * 100))
    assert n["title"] == "x" * 60


def test_normalize_row_preserves_repost_as_a_content_type():
    """post_type='repost' was observed live alongside 'post'. It is a real
    value, not an error -- do not coerce it to 'post'."""
    assert li._normalize_row(_raw_row(post_type="repost"))["content_type"] == "repost"


def test_normalize_row_lowercases_content_type_and_account_type():
    n = li._normalize_row(_raw_row(post_type="Post", account_type="Organization"))
    assert n["content_type"] == "post"
    assert n["account_type"] == "organization"


def test_normalize_row_returns_none_without_id():
    assert li._normalize_row(_raw_row(id="")) is None


def test_normalize_row_returns_none_with_unusable_date():
    assert li._normalize_row(_raw_row(date_posted="")) is None
    assert li._normalize_row(_raw_row(date_posted="garbage")) is None


def test_normalize_row_tolerates_missing_optional_fields():
    n = li._normalize_row({"id": "1", "date_posted": "2026-07-08T00:00:00.000Z"})
    assert n["body"] == ""
    assert n["author"] == ""
    assert n["hashtags"] == []
    assert n["like_count"] is None
    assert n["content_type"] == "post"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_discovery_linkedin.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'pipeline_app.discovery_linkedin'`

- [ ] **Step 3: Create the module with normalization only**

Create `pipeline-app/pipeline_app/discovery_linkedin.py`:

```python
"""LinkedIn platform adapters for the discovery engine, backed by Bright
Data's LinkedIn Posts dataset. Two platforms share this module:

  linkedin-profile  -- a person's own posts   (discover_by=profile_url)
  linkedin-company  -- an organization's posts (discover_by=company_url)

A third mode Bright Data advertises -- discover_by=url against
/today/author/<slug>, nominally "Pulse articles" -- is deliberately NOT
implemented. Live testing on 2026-08-07 against both authors in Bright Data's
own documentation snippet returned unrelated third-party posts and zero
articles, twice. See the design doc's "Broken -- Pulse articles" section.

Field names below are from four live jobs on 2026-08-07, not from the
published field list. See docs/superpowers/specs/2026-08-07-linkedin-
brightdata-adapter-design.md.
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

from pipeline_app import artifacts, brightdata_job
from pipeline_app.discovery_paths import handle_dir

# Not a secret -- read off the Bright Data dashboard's generated API snippet
# for the LinkedIn Posts product (2026-08-07). One dataset serves every mode;
# the type/discover_by query params select between them.
DATASET_ID = "gd_lyy3tktm25m4avu764"

KEY_ENV_VAR = "BRIGHTDATA_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "brightdata_api_key.txt"

MAX_ITEMS_PER_RUN = 10
POLL_TIMEOUT_S = 300
POLL_INTERVAL_S = 5

TITLE_MAX_CHARS = 60


def _parse_published(raw: str | None) -> str | None:
    """Bright Data's date_posted -> the engine's required YYYY-MM-DD, or None.

    This dataset returns genuine ISO 8601 UTC -- '2026-07-08T14:00:09.491Z'
    (verified 2026-08-07) -- so a 10-character prefix is correct. That is NOT
    true of Bright Data's Instagram product, which returns a US-format local
    timestamp; the two datasets disagree, so neither format may be inferred
    from the other.

    US-format input is deliberately NOT accepted here. Guessing between MM/DD
    and DD/MM would yield silently wrong dates, which is worse than a dropped
    row -- and drops are counted and logged by enumerate_newest_first.
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


def _normalize_row(row: dict) -> dict | None:
    """One raw Bright Data row -> this adapter's internal shape, or None if
    the row is unusable. The single place to update if the schema changes.

    Two field choices are load-bearing and verified:
    - The body is `post_text`. `original_post_text` and `post_text_html` are
      longer but carry HTML entities and anchor markup.
    - The title comes from `headline` (the post's first line), NOT the `title`
      field, which is SEO text with hashtags and the author name appended.
    """
    post_id = row.get("id")
    if not post_id:
        return None
    published = _parse_published(row.get("date_posted"))
    if published is None:
        return None

    body = (row.get("post_text") or "").strip()
    headline = (row.get("headline") or "").strip()
    first_line = body.split("\n", 1)[0].strip()
    title = headline or first_line or str(post_id)

    return {
        "id": str(post_id),
        "title": title[:TITLE_MAX_CHARS],
        "published": published,
        # Observed values: 'post', 'repost'. Lowercased defensively -- the
        # Instagram product returns display-cased values for the same concept.
        "content_type": (row.get("post_type") or "post").strip().lower(),
        "account_type": (row.get("account_type") or "").strip().lower(),
        "author": (row.get("user_id") or "").strip(),
        "body": body,
        "url": row.get("url") or "",
        "like_count": row.get("num_likes"),
        "comment_count": row.get("num_comments"),
        "hashtags": row.get("hashtags") or [],
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_discovery_linkedin.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_linkedin.py pipeline-app/tests/test_discovery_linkedin.py
git commit -m "feat(linkedin): row normalization pinned to verified live schema"
```

---

### Task 3: The `LinkedInAdapter` class and enumeration

The mode-bound adapter: job cycle, author filter, sort, cap, keyword filter, per-instance cache, and the all-filtered warning that keeps a billed-but-empty run from reading as a quiet day.

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_linkedin.py`
- Test: `pipeline-app/tests/test_discovery_linkedin.py`

**Interfaces:**
- Consumes: `brightdata_job.read_key/trigger/poll_status/fetch_results/await_results`, `BrightDataJobTimeout`, `BrightDataJobFailed` (Task 1); `_normalize_row`, `_parse_published`, `MAX_ITEMS_PER_RUN` (Task 2).
- Produces:
  - `class _Mode` with fields `platform: str`, `discover_by: str`, `url_template: str`, `author_filter: bool`
  - `PROFILE: _Mode`, `COMPANY: _Mode`
  - `class LinkedInAdapter` with `__init__(self, mode: _Mode)`, attributes `mode`, `platform`, `_cache: dict[str, dict[str, dict]]`, and methods `api_key()`, `profile_url(handle)`, `_trigger_job(handle, key)`, `_poll_job_status(job_id, key)`, `_fetch_job_results(job_id, key)`, `_run_collection_job(handle)`, `enumerate_newest_first(handle, keyword_filter)`
  - `profile_adapter() -> LinkedInAdapter`, `company_adapter() -> LinkedInAdapter`

- [ ] **Step 1: Write the failing tests**

Append to `pipeline-app/tests/test_discovery_linkedin.py`:

```python
import pytest

from pipeline_app import brightdata_job


def _profile():
    return li.profile_adapter()


def _company():
    return li.company_adapter()


def _row(post_id, date, author="bettywliu", text="hello", post_type="post"):
    return _raw_row(id=post_id, date_posted=f"{date}T00:00:00.000Z",
                    user_id=author, post_text=text, headline=text,
                    post_type=post_type)


def _stub_job(adapter, rows, monkeypatch):
    monkeypatch.setattr(adapter, "_run_collection_job", lambda handle: rows)


def test_profile_and_company_adapters_report_their_platform():
    assert _profile().platform == "linkedin-profile"
    assert _company().platform == "linkedin-company"


def test_profile_url_templates_differ_per_mode():
    assert _profile().profile_url("bettywliu") == "https://www.linkedin.com/in/bettywliu"
    assert _company().profile_url("lanieri") == "https://www.linkedin.com/company/lanieri"
    # A pasted @-prefixed handle still resolves.
    assert _profile().profile_url("@bettywliu") == "https://www.linkedin.com/in/bettywliu"


def test_trigger_job_sends_the_mode_specific_discovery_params(monkeypatch):
    captured = {}

    def fake_trigger(api_base, dataset_id, params, body, key):
        captured.update(api_base=api_base, dataset_id=dataset_id, params=params,
                        body=body, key=key)
        return "snap1"

    monkeypatch.setattr(brightdata_job, "trigger", fake_trigger)
    assert _profile()._trigger_job("bettywliu", "the-key") == "snap1"

    assert captured["dataset_id"] == li.DATASET_ID
    assert captured["params"]["type"] == "discover_new"
    assert captured["params"]["discover_by"] == "profile_url"
    # Server-side per-input record cap -- the primary cost control.
    assert captured["params"]["limit_per_input"] == li.MAX_ITEMS_PER_RUN
    assert captured["body"] == [{"url": "https://www.linkedin.com/in/bettywliu"}]


def test_trigger_job_uses_company_url_discovery_for_the_company_mode(monkeypatch):
    captured = {}

    def fake_trigger(api_base, dataset_id, params, body, key):
        captured.update(params=params, body=body)
        return "snap1"

    monkeypatch.setattr(brightdata_job, "trigger", fake_trigger)
    _company()._trigger_job("lanieri", "the-key")
    assert captured["params"]["discover_by"] == "company_url"
    assert captured["body"] == [{"url": "https://www.linkedin.com/company/lanieri"}]


def test_run_collection_job_raises_clear_error_when_key_missing(monkeypatch):
    adapter = _profile()
    monkeypatch.setattr(adapter, "api_key", lambda: None)
    with pytest.raises(RuntimeError, match="Bright Data API key not configured"):
        adapter._run_collection_job("bettywliu")


def test_enumerate_propagates_job_timeout(monkeypatch):
    adapter = _profile()

    def raise_timeout(handle):
        raise brightdata_job.BrightDataJobTimeout("timed out")

    monkeypatch.setattr(adapter, "_run_collection_job", raise_timeout)
    with pytest.raises(brightdata_job.BrightDataJobTimeout):
        adapter.enumerate_newest_first("bettywliu", keyword_filter=None)


def test_profile_mode_drops_posts_written_by_other_people(monkeypatch, capsys):
    """VERIFIED LIVE: discover_by=profile_url returns the person's profile
    ACTIVITY, including posts authored by others. Querying /in/bettywliu
    returned a row authored by mattwilkerson. Without this filter those land
    in her folder and any downstream reader misattributes them."""
    adapter = _profile()
    _stub_job(adapter, [
        _row("own1", "2026-07-08", author="bettywliu"),
        _row("foreign", "2026-07-14", author="mattwilkerson"),
        _row("own2", "2026-07-03", author="bettywliu"),
    ], monkeypatch)

    items = adapter.enumerate_newest_first("bettywliu", keyword_filter=None)

    assert [i["id"] for i in items] == ["own1", "own2"]
    assert "other author" in capsys.readouterr().err


def test_profile_mode_author_match_is_case_insensitive_and_ignores_at_prefix(monkeypatch):
    adapter = _profile()
    _stub_job(adapter, [_row("p1", "2026-07-08", author="BettyWLiu")], monkeypatch)
    items = adapter.enumerate_newest_first("@bettywliu", keyword_filter=None)
    assert [i["id"] for i in items] == ["p1"]


def test_company_mode_does_not_filter_by_author(monkeypatch):
    """Company results were clean in live testing -- every row was authored by
    the queried org -- and a company's user_id need not equal its URL slug, so
    filtering here would risk discarding legitimate rows."""
    adapter = _company()
    _stub_job(adapter, [_row("c1", "2026-04-01", author="lanieri-official")], monkeypatch)
    items = adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    assert [i["id"] for i in items] == ["c1"]


def test_enumerate_sorts_newest_first(monkeypatch):
    """VERIFIED LIVE: rows arrive unsorted (Jul 8, Jul 14, Jul 3). The engine's
    early-stop dedup assumes newest-first order."""
    adapter = _company()
    _stub_job(adapter, [
        _row("mid", "2026-07-08"), _row("new", "2026-07-14"), _row("old", "2026-07-03"),
    ], monkeypatch)
    items = adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    assert [i["id"] for i in items] == ["new", "mid", "old"]


def test_enumerate_caps_at_max_items_per_run(monkeypatch):
    adapter = _company()
    _stub_job(adapter, [_row(f"p{i}", "2026-07-08") for i in range(25)], monkeypatch)
    monkeypatch.setattr(li, "MAX_ITEMS_PER_RUN", 10)
    assert len(adapter.enumerate_newest_first("lanieri", keyword_filter=None)) == 10


def test_enumerate_drops_unusable_rows_and_logs(monkeypatch, capsys):
    adapter = _company()
    _stub_job(adapter, [
        _row("good", "2026-07-08"),
        {"post_text": "no id"},
        {"id": "no_date", "post_text": "x", "date_posted": ""},
    ], monkeypatch)
    items = adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    assert [i["id"] for i in items] == ["good"]
    assert "unusable" in capsys.readouterr().err


def test_enumerate_warns_loudly_when_rows_returned_but_none_survive(monkeypatch, capsys):
    """The silent-failure door the author filter opens: a billed job returns
    rows, the filter drops them all, enumerate returns [], and process_handle
    records the HEALTHY status 'no_new_content'. Returning [] is correct --
    it can happen legitimately -- but it must be loud in the log."""
    adapter = _profile()
    _stub_job(adapter, [
        _row("f1", "2026-07-08", author="someone-else"),
        _row("f2", "2026-07-09", author="another-person"),
    ], monkeypatch)

    assert adapter.enumerate_newest_first("bettywliu", keyword_filter=None) == []
    err = capsys.readouterr().err
    assert "none survived" in err
    assert "billed" in err


def test_enumerate_does_not_warn_when_the_job_genuinely_returned_nothing(monkeypatch, capsys):
    adapter = _company()
    _stub_job(adapter, [], monkeypatch)
    assert adapter.enumerate_newest_first("lanieri", keyword_filter=None) == []
    assert "none survived" not in capsys.readouterr().err


def test_enumerate_applies_keyword_filter_to_post_text(monkeypatch):
    adapter = _company()
    _stub_job(adapter, [
        _row("a", "2026-07-08", text="talks about gardens"),
        _row("b", "2026-07-08", text="talks about cars"),
    ], monkeypatch)
    items = adapter.enumerate_newest_first("lanieri", keyword_filter="GARDEN")
    assert [i["id"] for i in items] == ["a"]


def test_enumerate_returns_only_the_engine_facing_keys(monkeypatch):
    adapter = _company()
    _stub_job(adapter, [_row("c1", "2026-07-08")], monkeypatch)
    items = adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    assert set(items[0]) == {"id", "title", "published", "content_type"}


def test_enumerate_populates_the_cache_before_the_keyword_filter(monkeypatch):
    """download_item reads the cache, and process_handle only ever asks for
    ids enumerate returned -- but caching the pre-filter batch matches the
    Instagram adapter and costs nothing."""
    adapter = _company()
    _stub_job(adapter, [_row("c1", "2026-07-08", text="full body text")], monkeypatch)
    adapter.enumerate_newest_first("lanieri", keyword_filter="nomatch")
    assert adapter._cache["lanieri"]["c1"]["body"] == "full body text"


def test_enumerate_overwrites_a_previous_cache_entry(monkeypatch):
    adapter = _company()
    _stub_job(adapter, [_row("old_batch", "2026-07-01")], monkeypatch)
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    _stub_job(adapter, [_row("new_batch", "2026-08-01")], monkeypatch)
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    assert "old_batch" not in adapter._cache["lanieri"]
    assert "new_batch" in adapter._cache["lanieri"]


def test_two_adapters_sharing_a_handle_slug_do_not_share_cache(monkeypatch):
    """A person and a company can have the same slug. A module-level cache
    keyed by handle alone would let one mode's batch serve the other's
    download_item."""
    person, company = _profile(), _company()
    _stub_job(person, [_row("person_post", "2026-07-08", author="acme")], monkeypatch)
    _stub_job(company, [_row("company_post", "2026-07-08", author="acme")], monkeypatch)

    person.enumerate_newest_first("acme", keyword_filter=None)
    company.enumerate_newest_first("acme", keyword_filter=None)

    assert set(person._cache["acme"]) == {"person_post"}
    assert set(company._cache["acme"]) == {"company_post"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_discovery_linkedin.py -v`
Expected: FAIL — `AttributeError: module 'pipeline_app.discovery_linkedin' has no attribute 'profile_adapter'`

- [ ] **Step 3: Add the mode definitions and the adapter class**

Append to `pipeline-app/pipeline_app/discovery_linkedin.py`:

```python
class _Mode:
    """One Bright Data product mode, and how this pipeline uses it."""

    def __init__(self, platform: str, discover_by: str, url_template: str,
                 author_filter: bool):
        self.platform = platform
        self.discover_by = discover_by
        self.url_template = url_template
        self.author_filter = author_filter


# Profile discovery returns the person's profile ACTIVITY, not only their
# authorship -- verified live 2026-08-07, where a query for /in/bettywliu
# returned a post authored by mattwilkerson. author_filter=True restores the
# "this directory holds what this account wrote" contract every other adapter
# has. Company results showed no such contamination, and a company's user_id
# is not guaranteed to equal its URL slug, so filtering there would risk
# discarding legitimate rows.
PROFILE = _Mode("linkedin-profile", "profile_url",
                "https://www.linkedin.com/in/{slug}", author_filter=True)
COMPANY = _Mode("linkedin-company", "company_url",
                "https://www.linkedin.com/company/{slug}", author_filter=False)


class LinkedInAdapter:
    """Satisfies discovery_engine.PlatformAdapter for one LinkedIn mode.

    An instance rather than a module because two platforms share this code and
    each needs its own enumerate cache: a person and a company can have the
    same slug, and a cache keyed by handle alone would let one mode's batch
    serve the other's download_item.
    """

    def __init__(self, mode: _Mode):
        self.mode = mode
        self.platform = mode.platform
        # handle -> item_id -> normalized row. Populated by
        # enumerate_newest_first, read by download_item. Calling Bright Data
        # again per item would double-pay for posts already collected.
        self._cache: dict[str, dict[str, dict]] = {}

    # -- credentials and request shape -----------------------------------

    def api_key(self) -> str | None:
        return brightdata_job.read_key(KEY_ENV_VAR, KEY_FILE)

    def profile_url(self, handle: str) -> str:
        return self.mode.url_template.format(slug=handle.lstrip("@").strip())

    def _trigger_job(self, handle: str, key: str) -> str:
        return brightdata_job.trigger(
            brightdata_job.BRIGHTDATA_API_BASE,
            DATASET_ID,
            {
                # A *discovery* job -- "find this account's newest posts".
                # Without type/discover_by, Bright Data reads the input url as
                # a single page to collect, the wrong product mode entirely.
                "type": "discover_new",
                "discover_by": self.mode.discover_by,
                # Server-side per-input record cap: the primary cost control.
                "limit_per_input": MAX_ITEMS_PER_RUN,
                "include_errors": "true",
                "notify": "false",
            },
            [{"url": self.profile_url(handle)}],
            key,
        )

    def _poll_job_status(self, job_id: str, key: str) -> str:
        return brightdata_job.poll_status(brightdata_job.BRIGHTDATA_API_BASE, job_id, key)

    def _fetch_job_results(self, job_id: str, key: str) -> list[dict]:
        return brightdata_job.fetch_results(brightdata_job.BRIGHTDATA_API_BASE, job_id, key)

    def _run_collection_job(self, handle: str) -> list[dict]:
        key = self.api_key()
        if key is None:
            raise RuntimeError(
                "Bright Data API key not configured "
                f"(set {KEY_ENV_VAR} or {KEY_FILE.name})"
            )
        return brightdata_job.await_results(
            trigger_fn=lambda: self._trigger_job(handle, key),
            poll_fn=lambda job_id: self._poll_job_status(job_id, key),
            fetch_fn=lambda job_id: self._fetch_job_results(job_id, key),
            label=f"for {self.platform}/{handle}",
            poll_timeout_s=POLL_TIMEOUT_S,
            poll_interval_s=POLL_INTERVAL_S,
        )

    # -- PlatformAdapter -------------------------------------------------

    def enumerate_newest_first(self, handle: str, keyword_filter: str | None) -> list[dict]:
        # Raises BrightDataJobTimeout/BrightDataJobFailed -- never swallowed
        # here. An empty return must mean "the job completed and there was
        # nothing", nothing else.
        raw_rows = self._run_collection_job(handle)

        normalized = [_normalize_row(r) for r in raw_rows]
        unusable = sum(1 for n in normalized if n is None)
        kept = [n for n in normalized if n is not None]

        foreign = 0
        if self.mode.author_filter:
            wanted = handle.lstrip("@").strip().lower()
            before = len(kept)
            kept = [n for n in kept if n["author"].lower() == wanted]
            foreign = before - len(kept)

        if unusable or foreign:
            print(f"  ! {self.platform}/{handle}: dropped {unusable} unusable row(s), "
                  f"{foreign} row(s) by another author", file=sys.stderr)

        if raw_rows and not kept:
            # This run was billed and produced nothing, but process_handle will
            # record the healthy status 'no_new_content' -- indistinguishable
            # from a quiet day unless it is loud here.
            print(f"  !! {self.platform}/{handle}: Bright Data returned "
                  f"{len(raw_rows)} row(s) but none survived filtering. This run "
                  f"was billed and captured nothing -- check whether this account "
                  f"posts its own content.", file=sys.stderr)

        # Rows arrive unsorted (verified live); the engine's early-stop dedup
        # assumes newest-first. Cap AFTER filtering so it bounds retained items.
        kept.sort(key=lambda n: n["published"], reverse=True)
        kept = kept[:MAX_ITEMS_PER_RUN]

        # Overwrite, not merge: a fresh successful enumerate replaces whatever
        # this handle held, so download_item never reads a stale id.
        self._cache[handle] = {n["id"]: n for n in kept}

        items = kept
        if keyword_filter:
            items = [i for i in items if keyword_filter.lower() in i["body"].lower()]
        return [
            {"id": i["id"], "title": i["title"], "published": i["published"],
             "content_type": i["content_type"]}
            for i in items
        ]


def profile_adapter() -> LinkedInAdapter:
    return LinkedInAdapter(PROFILE)


def company_adapter() -> LinkedInAdapter:
    return LinkedInAdapter(COMPANY)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_discovery_linkedin.py -v`
Expected: 31 passed (12 from Task 2 + 19 new)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_linkedin.py pipeline-app/tests/test_discovery_linkedin.py
git commit -m "feat(linkedin): mode-bound adapter with author filter and all-filtered warning"
```

---

### Task 4: On-disk state and file writing

The remaining three `PlatformAdapter` methods. `download_item` reads the cache rather than calling Bright Data again — a second call would re-pay for posts already collected.

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_linkedin.py`
- Test: `pipeline-app/tests/test_discovery_linkedin.py`

**Interfaces:**
- Consumes: `LinkedInAdapter`, `self._cache`, `self.platform` (Task 3); `handle_dir` and `artifacts.render_frontmatter` (existing).
- Produces on `LinkedInAdapter`:
  - `on_disk_ids(self, repo_root: Path, handle: str) -> set[str]`
  - `peek_upload_date(self, item_id: str) -> None`
  - `download_item(self, repo_root: Path, handle: str, item_id: str, title: str, content_type: str | None = None) -> dict` returning `{"id": str, "ok": True, "published": str}`

- [ ] **Step 1: Write the failing tests**

Append to `pipeline-app/tests/test_discovery_linkedin.py`:

```python
def test_on_disk_ids_empty_when_directory_missing(tmp_path):
    assert _profile().on_disk_ids(tmp_path, "bettywliu") == set()


def test_on_disk_ids_reads_stems_of_md_files(tmp_path):
    out_dir = tmp_path / "output" / "brand-intel" / "linkedin-profile" / "bettywliu"
    out_dir.mkdir(parents=True)
    (out_dir / "p1.md").write_text("x", encoding="utf-8")
    (out_dir / "p2.md").write_text("x", encoding="utf-8")
    assert _profile().on_disk_ids(tmp_path, "bettywliu") == {"p1", "p2"}


def test_on_disk_ids_is_scoped_per_platform(tmp_path):
    """A person and a company sharing a slug must not see each other's files."""
    person_dir = tmp_path / "output" / "brand-intel" / "linkedin-profile" / "acme"
    person_dir.mkdir(parents=True)
    (person_dir / "person_post.md").write_text("x", encoding="utf-8")
    assert _profile().on_disk_ids(tmp_path, "acme") == {"person_post"}
    assert _company().on_disk_ids(tmp_path, "acme") == set()


def test_peek_upload_date_always_none():
    assert _profile().peek_upload_date("anything") is None


def test_download_item_writes_frontmatter_and_body_from_cache(tmp_path, monkeypatch):
    adapter = _profile()
    _stub_job(adapter, [_row("p1", "2026-07-08", author="bettywliu",
                             text="the body text")], monkeypatch)
    adapter.enumerate_newest_first("bettywliu", keyword_filter=None)

    result = adapter.download_item(tmp_path, "bettywliu", "p1", "the body text",
                                   content_type="post")

    assert result == {"id": "p1", "ok": True, "published": "2026-07-08"}
    out_path = (tmp_path / "output" / "brand-intel" / "linkedin-profile"
                / "bettywliu" / "p1.md")
    text = out_path.read_text(encoding="utf-8")
    assert "post_id: p1" in text
    assert "author: bettywliu" in text
    assert "account_type: person" in text
    assert "content_type: post" in text
    # yaml.safe_dump quotes date-like strings -- this is NOT bare 2026-07-08.
    assert "published: '2026-07-08'" in text
    assert "the body text" in text
    # write-temp-then-rename must leave no partial file behind
    assert not out_path.with_name("p1.md.tmp").exists()


def test_download_item_records_engagement_and_hashtags(tmp_path, monkeypatch):
    adapter = _company()
    _stub_job(adapter, [_raw_row(id="c1", date_posted="2026-04-01T00:00:00.000Z",
                                 num_likes=18, num_comments=0,
                                 hashtags=["#wool", "#tailoring"])], monkeypatch)
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    adapter.download_item(tmp_path, "lanieri", "c1", "t")

    text = (tmp_path / "output" / "brand-intel" / "linkedin-company" / "lanieri"
            / "c1.md").read_text(encoding="utf-8")
    assert "like_count: 18" in text
    assert "comment_count: 0" in text
    assert "- '#wool'" in text


def test_download_item_empty_body_writes_placeholder(tmp_path, monkeypatch):
    adapter = _company()
    _stub_job(adapter, [_row("c1", "2026-07-08", text="")], monkeypatch)
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    adapter.download_item(tmp_path, "lanieri", "c1", "c1")
    out = tmp_path / "output" / "brand-intel" / "linkedin-company" / "lanieri" / "c1.md"
    assert "(empty)" in out.read_text(encoding="utf-8")


def test_download_item_raises_on_cache_miss(tmp_path, monkeypatch):
    """A missing id is a programming error, not a degraded write. KeyError
    propagates to run_discovery's per-handle handler and is recorded as a
    normal 'error' -- safe-fail rather than an empty file that on_disk_ids
    would then treat as captured."""
    adapter = _company()
    _stub_job(adapter, [_row("c1", "2026-07-08")], monkeypatch)
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    with pytest.raises(KeyError):
        adapter.download_item(tmp_path, "lanieri", "not_in_cache", "title")


def test_download_item_makes_no_network_call(tmp_path, monkeypatch):
    adapter = _company()
    _stub_job(adapter, [_row("c1", "2026-07-08")], monkeypatch)
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)

    def _fail(*args, **kwargs):
        raise AssertionError("download_item must read the cache, not re-collect")

    monkeypatch.setattr(adapter, "_run_collection_job", _fail)
    monkeypatch.setattr(brightdata_job, "trigger", _fail)
    assert adapter.download_item(tmp_path, "lanieri", "c1", "t")["ok"] is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_discovery_linkedin.py -v`
Expected: FAIL — `AttributeError: 'LinkedInAdapter' object has no attribute 'on_disk_ids'`

- [ ] **Step 3: Add the three methods**

Append inside `class LinkedInAdapter`, after `enumerate_newest_first`:

```python
    def on_disk_ids(self, repo_root: Path, handle: str) -> set[str]:
        directory = handle_dir(repo_root, self.platform, handle)
        if not directory.exists():
            return set()
        return {p.stem for p in directory.glob("*.md")}

    def peek_upload_date(self, item_id: str) -> str | None:
        # Dead code by design: enumerate_newest_first only ever returns items
        # carrying a normalized 'published' date, so process_handle's
        # `item.get("published") or adapter.peek_upload_date(...)` never falls
        # through -- same as discovery_bluesky/discovery_instagram.
        return None

    def download_item(self, repo_root: Path, handle: str, item_id: str, title: str,
                      content_type: str | None = None) -> dict:
        # A missing handle or item_id is a programming error: every engine call
        # path runs enumerate_newest_first for this handle on this instance
        # first. KeyError propagates to run_discovery's per-handle error path
        # rather than being caught here, so it surfaces as a normal 'error'
        # instead of failing silently.
        cached = self._cache[handle][item_id]

        out_dir = handle_dir(repo_root, self.platform, handle)
        out_dir.mkdir(parents=True, exist_ok=True)
        fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        meta = {
            "post_id": cached["id"],
            "url": cached["url"],
            "handle": handle,
            # Recorded even in profile mode, where the filter guarantees it
            # matches: it is what makes a filtering regression detectable
            # after the fact, and it is independently meaningful for companies.
            "author": cached["author"],
            "account_type": cached["account_type"],
            "content_type": cached["content_type"],
            "published": cached["published"],
            "like_count": cached["like_count"],
            "comment_count": cached["comment_count"],
            "hashtags": cached["hashtags"],
            "fetched_at": fetched_at,
        }
        body = cached["body"] or "(empty)"

        dest = out_dir / f"{item_id}.md"
        # Write-temp-then-rename, same as every other adapter: an interrupted
        # write must never leave a truncated file at a path on_disk_ids()
        # would treat as already-captured.
        tmp_dest = dest.with_name(dest.name + ".tmp")
        tmp_dest.write_text(artifacts.render_frontmatter(meta, body), encoding="utf-8")
        tmp_dest.replace(dest)
        return {"id": item_id, "ok": True, "published": cached["published"]}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_discovery_linkedin.py -v`
Expected: 40 passed (31 + 9 new)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_linkedin.py pipeline-app/tests/test_discovery_linkedin.py
git commit -m "feat(linkedin): on-disk dedup and cached file writing"
```

---

### Task 5: Wire both platforms into the pipeline

Register the adapters, add the dropdown options, and pin the fact that backfill is already rejected for both platforms by the existing whitelist — no engine change needed, unlike Instagram.

**Files:**
- Modify: `pipeline-app/run_discovery_cron.py:31-32`
- Modify: `pipeline-app/pipeline_app/templates/discovery_handles.html:33-37`
- Modify: `pipeline-app/tests/test_run_discovery_cron.py:170-172`
- Test: `pipeline-app/tests/test_run_discovery_cron.py`

**Interfaces:**
- Consumes: `discovery_linkedin.profile_adapter()`, `discovery_linkedin.company_adapter()` (Task 3).
- Produces: `build_adapters()` returns a dict with keys `{"youtube", "bluesky", "instagram", "linkedin-profile", "linkedin-company"}`.

- [ ] **Step 1: Update the existing registry test and add the new ones**

In `pipeline-app/tests/test_run_discovery_cron.py`, replace the existing `test_build_adapters_includes_all_three_platforms` (line 170) with:

```python
def test_build_adapters_includes_every_platform():
    adapters = cron.build_adapters()
    assert set(adapters.keys()) == {
        "youtube", "bluesky", "instagram", "linkedin-profile", "linkedin-company",
    }


def test_build_adapters_gives_each_linkedin_mode_its_own_instance():
    """Separate instances, so their enumerate caches stay separate -- a person
    and a company can share a slug."""
    adapters = cron.build_adapters()
    profile, company = adapters["linkedin-profile"], adapters["linkedin-company"]
    assert profile is not company
    assert profile.platform == "linkedin-profile"
    assert company.platform == "linkedin-company"


def test_linkedin_platforms_are_excluded_from_backfill():
    """discovery_engine rejects any platform outside this whitelist before an
    adapter is called, so a backfill request can never trigger a paid LinkedIn
    job that would return nothing useful. Instagram needed this guard added;
    LinkedIn inherits it -- pin that it still holds."""
    from pipeline_app.discovery_engine import BACKFILL_SUPPORTED_PLATFORMS

    assert "linkedin-profile" not in BACKFILL_SUPPORTED_PLATFORMS
    assert "linkedin-company" not in BACKFILL_SUPPORTED_PLATFORMS
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_run_discovery_cron.py -v -k "build_adapters or backfill"`
Expected: FAIL — the key-set assertion fails because `build_adapters()` still returns three keys

- [ ] **Step 3: Register the adapters**

In `pipeline-app/run_discovery_cron.py`, update the import (line 23) and `build_adapters` (lines 31-32):

```python
from pipeline_app import discovery_bluesky, discovery_instagram, discovery_linkedin, discovery_youtube
```

```python
def build_adapters():
    # LinkedIn's two modes are separate instances, not one shared object: each
    # keeps its own enumerate cache, and a person and a company can have the
    # same URL slug.
    return {
        "youtube": discovery_youtube,
        "bluesky": discovery_bluesky,
        "instagram": discovery_instagram,
        "linkedin-profile": discovery_linkedin.profile_adapter(),
        "linkedin-company": discovery_linkedin.company_adapter(),
    }
```

- [ ] **Step 4: Add the dropdown options**

In `pipeline-app/pipeline_app/templates/discovery_handles.html`, extend the platform `<select>` (line 33):

```html
  <select name="platform">
    <option value="youtube">YouTube</option>
    <option value="bluesky">Bluesky</option>
    <option value="instagram">Instagram</option>
    <option value="linkedin-profile">LinkedIn — person's posts</option>
    <option value="linkedin-company">LinkedIn — company posts</option>
  </select>
```

Update the handle input's placeholder (line 38) so the expected format is obvious — LinkedIn handles are bare slugs, not URLs:

```html
  <input name="handle" placeholder="@handle, actor.bsky.social, or linkedin slug" required>
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_run_discovery_cron.py -v`
Expected: all pass, including the three registry/backfill tests

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest tests/ -v`
Expected: all pass. Confirm `tests/test_discovery_instagram.py` still reports **38 passed** and that file remains unmodified (`git diff --stat pipeline-app/tests/test_discovery_instagram.py` must be empty).

- [ ] **Step 7: Commit**

```bash
git add pipeline-app/run_discovery_cron.py pipeline-app/pipeline_app/templates/discovery_handles.html pipeline-app/tests/test_run_discovery_cron.py
git commit -m "feat(linkedin): register both platforms in the discovery pipeline"
```

---

## After the plan

Two things are deliberately **not** tasks, because both cost real money and are the user's call:

1. **A live end-to-end run through the adapter.** Every test above stubs the network. The four verification jobs on 2026-08-07 went through a standalone script, not this code. One real `--mode validate_handle` run against a registered handle would close that gap.
2. **Registering handles.** Registration fires a billed `validate_handle` job, and a transient failure permanently excludes the handle. For `linkedin-profile`, so does an account whose recent activity is all other people's posts — see the spec's "Named limitation".

Also still open from the spec: `[T-unverified, 2026-08-07]` billing granularity. Check the dashboard's usage page against the four verification jobs before registering many handles.

Operational reminder: Bright Data's domains are DNS-blocked by Proton VPN's NetShield on this machine. Any live run needs it off.
