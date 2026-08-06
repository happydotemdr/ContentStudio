# Instagram Discovery Adapter via Bright Data — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Instagram as a third discovery-pipeline platform (alongside YouTube and Bluesky), using Bright Data's Instagram Posts Scraper API, satisfying the existing `PlatformAdapter` protocol.

**Architecture:** A new `pipeline_app/discovery_instagram.py` module mirrors `discovery_bluesky.py`'s shape (no subprocess, single external API). Because Bright Data's API is asynchronous (trigger → poll → fetch) and bills per record, the module runs one collection job per handle per run inside `enumerate_newest_first`, caches the parsed results in a module-level dict, and has `download_item` read from that cache rather than re-calling the API. `discovery_engine.py` gains a small, explicit guard so backfill mode — which this adapter's newest-N-only design can't serve — is skipped for Instagram rather than silently wasting a paid job.

**Tech Stack:** Python 3, `requests` (already a project dependency, used the same way in `discovery_notify.py`), `pytest` + `monkeypatch` for tests (matching `test_discovery_bluesky.py`'s fake-HTTP-layer pattern).

## Global Constraints

- Credential lookup order: `BRIGHTDATA_API_KEY` env var, then gitignored `brightdata_api_key.txt` — exact pattern of `discovery_youtube_api.api_key()`.
- `MAX_ITEMS_PER_RUN = 10` (per handle per run) — from the design doc's cost reconciliation: `10 × 30 days ≈ 300 items/month/handle`, fitting ~3 handles inside the cost-comparison doc's 1,000/month-per-platform assumption.
- `POLL_TIMEOUT_S = 300` (5 minutes), `POLL_INTERVAL_S = 5` — bounded polling; a job that hasn't reached `ready`/`failed` by the timeout raises rather than returning an empty result.
- Publish dates MUST be truncated to `YYYY-MM-DD` before being returned from `enumerate_newest_first` — `discovery_engine.py` does a strict `strptime(published, "%Y-%m-%d")` and an unnormalized value crashes it.
- A poll timeout or a job reporting `failed` status MUST raise an exception from `enumerate_newest_first`, never return `[]` — an empty list reads as "handle posted nothing new" (`no_new_content`, a *healthy* status) or, in `validate_handle` mode, permanently excludes the handle. Only a successfully-completed job with zero usable rows returns `[]`.
- Backfill mode is unsupported for Instagram — `discovery_engine.py` gains a `BACKFILL_SUPPORTED_PLATFORMS = {"youtube", "bluesky"}` guard so a backfill run skips Instagram handles without calling the adapter at all. The skipped handle is recorded with a distinct `"skipped"` status (not `"no_new_content"`) — per the design's gap-1 principle, a non-result must never be indistinguishable from a healthy "nothing new today" result.
- Bright Data raw response field names used below (`post_id`, `caption`, `date_posted`, `content_type`, `url`, `likes`, `num_comments`) are this design's best-available assumption, not confirmed against a live Bright Data response — flagged `[T-unverified, 2026-08-06]` in the design doc. `_normalize_row` (Task 3) is the single place that would need updating if the real schema differs.

---

## File Structure

- **Create** `pipeline-app/pipeline_app/discovery_instagram.py` — the adapter: credentials, Bright Data job cycle, row normalization, and the four `PlatformAdapter` functions.
- **Create** `pipeline-app/tests/test_discovery_instagram.py` — unit tests against a fake HTTP layer, no real network calls.
- **Modify** `pipeline-app/pipeline_app/discovery_engine.py` — add `BACKFILL_SUPPORTED_PLATFORMS` and a guard in `run_discovery`'s per-handle loop that records a `"skipped"` status.
- **Modify** `pipeline-app/tests/test_discovery_engine.py` — one new test covering the backfill guard.
- **Modify** `pipeline-app/run_discovery_cron.py` — register the new adapter in `build_adapters()`.
- **Modify** `pipeline-app/pipeline_app/templates/discovery_handles.html` — add the Instagram `<option>`.
- **Modify** `pipeline-app/.gitignore` — add `brightdata_api_key.txt`.

---

### Task 1: Credential lookup

**Files:**
- Create: `pipeline-app/pipeline_app/discovery_instagram.py`
- Modify: `pipeline-app/.gitignore`
- Test: `pipeline-app/tests/test_discovery_instagram.py`

**Interfaces:**
- Produces: `api_key() -> str | None`, module constants `KEY_ENV_VAR = "BRIGHTDATA_API_KEY"`, `KEY_FILE: Path`, `DATASET_ID: str`.

- [ ] **Step 1: Write the failing tests**

```python
# pipeline-app/tests/test_discovery_instagram.py
from pathlib import Path

from pipeline_app import discovery_instagram as ig


def test_api_key_prefers_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv(ig.KEY_ENV_VAR, "env-key")
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("file-key", encoding="utf-8")
    monkeypatch.setattr(ig, "KEY_FILE", key_file)
    assert ig.api_key() == "env-key"


def test_api_key_falls_back_to_file(monkeypatch, tmp_path):
    monkeypatch.delenv(ig.KEY_ENV_VAR, raising=False)
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("  file-key\n", encoding="utf-8")
    monkeypatch.setattr(ig, "KEY_FILE", key_file)
    assert ig.api_key() == "file-key"


def test_api_key_none_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv(ig.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(ig, "KEY_FILE", tmp_path / "absent.txt")
    assert ig.api_key() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_instagram.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_app.discovery_instagram'`

- [ ] **Step 3: Write the module with credential lookup**

```python
# pipeline-app/pipeline_app/discovery_instagram.py
"""Instagram platform adapter for the discovery engine, backed by Bright
Data's Instagram Posts Scraper API. Isolates the Bright Data HTTP calls so
discovery_engine's core algorithm can be unit-tested with no network access,
the same isolation discovery_bluesky.py and discovery_youtube.py use.

Bright Data's API is asynchronous (trigger -> poll -> fetch) and bills per
record, unlike YouTube's Data API or Bluesky's AppView which answer
synchronously. See docs/superpowers/specs/2026-08-06-instagram-brightdata-
adapter-design.md for the full design, including why enumerate_newest_first
runs the whole job cycle once per handle per run and caches results for
download_item to read from -- calling Bright Data once per item would
double-pay for the same posts.
"""
from __future__ import annotations

import datetime as _dt
import os
import sys
import time
from pathlib import Path

import requests

from pipeline_app import artifacts
from pipeline_app.discovery_paths import handle_dir

BRIGHTDATA_API_BASE = "https://api.brightdata.com/datasets/v3"

# Key lookup order: env var first (works for the scheduled task, which
# inherits the User environment), then a gitignored file for convenience --
# same pattern as discovery_youtube_api.api_key() / discovery_notify.api_key().
KEY_ENV_VAR = "BRIGHTDATA_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "brightdata_api_key.txt"

# Bright Data dataset id for the Instagram Posts Scraper API product. Not a
# secret -- a one-time value from the Bright Data dashboard when the product
# is provisioned. Placeholder until that provisioning step happens; replace
# before the first real run.
DATASET_ID = "gd_REPLACE_WITH_REAL_DATASET_ID"

REQUEST_TIMEOUT_S = 30


def api_key() -> str | None:
    """The Bright Data API token, or None if not configured."""
    env_key = os.environ.get(KEY_ENV_VAR, "").strip()
    if env_key:
        return env_key
    if KEY_FILE.exists():
        file_key = KEY_FILE.read_text(encoding="utf-8").strip()
        if file_key:
            return file_key
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_instagram.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Add the gitignore entry**

Add this line to `pipeline-app/.gitignore`, alongside the existing `youtube_api_key.txt` / `resend_api_key.txt` / `cookies.txt` entries:

```
brightdata_api_key.txt
```

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_instagram.py pipeline-app/tests/test_discovery_instagram.py pipeline-app/.gitignore
git commit -m "feat(discovery): add Instagram adapter credential lookup"
```

---

### Task 2: Bright Data job cycle (trigger / poll / fetch)

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_instagram.py`
- Test: `pipeline-app/tests/test_discovery_instagram.py`

**Interfaces:**
- Consumes: `api_key() -> str | None` (Task 1).
- Produces: `BrightDataJobTimeout(Exception)`, `BrightDataJobFailed(Exception)`, `_run_collection_job(handle: str) -> list[dict]` (raw Bright Data rows, raises on timeout/failure). Internal helpers `_trigger_job`, `_poll_job_status`, `_fetch_job_results` are patched directly in tests, matching how `discovery_bluesky.py` tests patch `_http_get`.

- [ ] **Step 1: Write the failing tests**

```python
# append to pipeline-app/tests/test_discovery_instagram.py
import pytest


def test_run_collection_job_returns_results_on_ready(monkeypatch):
    monkeypatch.setattr(ig, "_trigger_job", lambda handle: "job1")
    monkeypatch.setattr(ig, "_poll_job_status", lambda job_id: "ready")
    monkeypatch.setattr(ig, "_fetch_job_results", lambda job_id: [{"post_id": "p1"}])
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    assert ig._run_collection_job("somehandle") == [{"post_id": "p1"}]


def test_run_collection_job_raises_on_failed_status(monkeypatch):
    monkeypatch.setattr(ig, "_trigger_job", lambda handle: "job1")
    monkeypatch.setattr(ig, "_poll_job_status", lambda job_id: "failed")
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    with pytest.raises(ig.BrightDataJobFailed):
        ig._run_collection_job("somehandle")


def test_run_collection_job_raises_on_timeout(monkeypatch):
    monkeypatch.setattr(ig, "_trigger_job", lambda handle: "job1")
    monkeypatch.setattr(ig, "_poll_job_status", lambda job_id: "running")  # never ready
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    # Force the deadline to have already passed on the very first check.
    monkeypatch.setattr(ig.time, "monotonic", lambda: 10_000.0)
    monkeypatch.setattr(ig, "POLL_TIMEOUT_S", 0)
    with pytest.raises(ig.BrightDataJobTimeout):
        ig._run_collection_job("somehandle")


def test_run_collection_job_polls_until_ready(monkeypatch):
    statuses = iter(["running", "running", "ready"])
    monkeypatch.setattr(ig, "_trigger_job", lambda handle: "job1")
    monkeypatch.setattr(ig, "_poll_job_status", lambda job_id: next(statuses))
    monkeypatch.setattr(ig, "_fetch_job_results", lambda job_id: [{"post_id": "p1"}])
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    assert ig._run_collection_job("somehandle") == [{"post_id": "p1"}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_instagram.py -v`
Expected: FAIL with `AttributeError: module 'pipeline_app.discovery_instagram' has no attribute '_run_collection_job'`

- [ ] **Step 3: Implement the job cycle**

Add to `pipeline-app/pipeline_app/discovery_instagram.py`:

```python
MAX_ITEMS_PER_RUN = 10
POLL_TIMEOUT_S = 300
POLL_INTERVAL_S = 5


class BrightDataJobTimeout(Exception):
    """A Bright Data collection job did not reach 'ready' within POLL_TIMEOUT_S."""


class BrightDataJobFailed(Exception):
    """A Bright Data collection job reported status 'failed'."""


def _trigger_job(handle: str) -> str:
    profile_url = f"https://www.instagram.com/{handle.lstrip('@')}/"
    response = requests.post(
        f"{BRIGHTDATA_API_BASE}/trigger",
        params={"dataset_id": DATASET_ID, "include_errors": "true"},
        headers={"Authorization": f"Bearer {api_key()}"},
        # num_of_posts as a request-time limit is this design's best-available
        # assumption about Bright Data's trigger API -- UNVERIFIED, see the
        # design doc's "Verification needed before implementation". If the API
        # doesn't honor it, enumerate_newest_first's post-fetch slice (Task 4)
        # still bounds cost on this side.
        json=[{"url": profile_url, "num_of_posts": MAX_ITEMS_PER_RUN}],
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()["snapshot_id"]


def _poll_job_status(job_id: str) -> str:
    response = requests.get(
        f"{BRIGHTDATA_API_BASE}/progress/{job_id}",
        headers={"Authorization": f"Bearer {api_key()}"},
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()["status"]


def _fetch_job_results(job_id: str) -> list[dict]:
    response = requests.get(
        f"{BRIGHTDATA_API_BASE}/snapshot/{job_id}",
        params={"format": "json"},
        headers={"Authorization": f"Bearer {api_key()}"},
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()


def _run_collection_job(handle: str) -> list[dict]:
    job_id = _trigger_job(handle)
    deadline = time.monotonic() + POLL_TIMEOUT_S
    while True:
        status = _poll_job_status(job_id)
        if status == "ready":
            return _fetch_job_results(job_id)
        if status == "failed":
            raise BrightDataJobFailed(f"Bright Data job {job_id} for {handle} failed")
        if time.monotonic() >= deadline:
            raise BrightDataJobTimeout(
                f"Bright Data job {job_id} for {handle} timed out after {POLL_TIMEOUT_S}s"
            )
        time.sleep(POLL_INTERVAL_S)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_instagram.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_instagram.py pipeline-app/tests/test_discovery_instagram.py
git commit -m "feat(discovery): add Bright Data trigger/poll/fetch job cycle for Instagram"
```

---

### Task 3: Row normalization

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_instagram.py`
- Test: `pipeline-app/tests/test_discovery_instagram.py`

**Interfaces:**
- Produces: `_normalize_row(row: dict) -> dict | None` — returns `{"id", "title", "published", "content_type", "caption", "url", "like_count", "comment_count"}`, or `None` if the row has no usable id or no usable publish date.

- [ ] **Step 1: Write the failing tests**

```python
# append to pipeline-app/tests/test_discovery_instagram.py
def test_normalize_row_truncates_date_to_yyyy_mm_dd():
    row = {
        "post_id": "p1", "caption": "hello world", "date_posted": "2026-08-01T12:34:56.000Z",
        "content_type": "post", "url": "https://instagram.com/p/p1", "likes": 10, "num_comments": 2,
    }
    normalized = ig._normalize_row(row)
    assert normalized["id"] == "p1"
    assert normalized["published"] == "2026-08-01"
    assert normalized["content_type"] == "post"
    assert normalized["caption"] == "hello world"
    assert normalized["like_count"] == 10
    assert normalized["comment_count"] == 2


def test_normalize_row_title_is_truncated_caption():
    long_caption = "x" * 100
    row = {"post_id": "p1", "caption": long_caption, "date_posted": "2026-08-01T00:00:00Z", "content_type": "reel"}
    normalized = ig._normalize_row(row)
    assert normalized["title"] == long_caption[:60]
    assert normalized["content_type"] == "reel"


def test_normalize_row_returns_none_without_id():
    row = {"caption": "x", "date_posted": "2026-08-01T00:00:00Z", "content_type": "post"}
    assert ig._normalize_row(row) is None


def test_normalize_row_returns_none_without_usable_date():
    row = {"post_id": "p1", "caption": "x", "date_posted": "", "content_type": "post"}
    assert ig._normalize_row(row) is None


def test_normalize_row_empty_caption_still_normalizes():
    row = {"post_id": "p1", "caption": None, "date_posted": "2026-08-01T00:00:00Z", "content_type": "post"}
    normalized = ig._normalize_row(row)
    assert normalized["caption"] == ""
    assert normalized["title"] == "p1"  # falls back to id when caption is empty
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_instagram.py -v`
Expected: FAIL with `AttributeError: module 'pipeline_app.discovery_instagram' has no attribute '_normalize_row'`

- [ ] **Step 3: Implement normalization**

Add to `pipeline-app/pipeline_app/discovery_instagram.py`:

```python
def _normalize_row(row: dict) -> dict | None:
    """Maps one raw Bright Data Instagram row into the shape this adapter
    works with internally. Field names (post_id, caption, date_posted,
    content_type, url, likes, num_comments) are this design's best-available
    assumption about Bright Data's response schema -- UNVERIFIED, see the
    design doc's "Verification needed before implementation". This is the
    single place to update if the real schema differs.
    """
    post_id = row.get("post_id")
    if not post_id:
        return None
    published_raw = row.get("date_posted") or ""
    published = published_raw[:10] if len(published_raw) >= 10 else None
    if published is None:
        return None
    caption = (row.get("caption") or "").strip()
    return {
        "id": post_id,
        "title": caption[:60] if caption else post_id,
        "published": published,
        "content_type": row.get("content_type") or "post",
        "caption": caption,
        "url": row.get("url") or "",
        "like_count": row.get("likes"),
        "comment_count": row.get("num_comments"),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_instagram.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_instagram.py pipeline-app/tests/test_discovery_instagram.py
git commit -m "feat(discovery): normalize Bright Data Instagram rows"
```

---

### Task 4: enumerate_newest_first (cache, cap, filter)

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_instagram.py`
- Test: `pipeline-app/tests/test_discovery_instagram.py`

**Interfaces:**
- Consumes: `_run_collection_job(handle) -> list[dict]` (Task 2), `_normalize_row(row) -> dict | None` (Task 3).
- Produces: `enumerate_newest_first(handle: str, keyword_filter: str | None) -> list[dict]` — each item `{"id", "title", "published", "content_type"}`, newest-first. Populates module-level `_ENUMERATE_CACHE: dict[str, dict[str, dict]]` (handle -> item_id -> full normalized row), which Task 5's `download_item` reads from.

- [ ] **Step 1: Write the failing tests**

```python
# append to pipeline-app/tests/test_discovery_instagram.py
def _raw_row(post_id, date, caption="hello", content_type="post"):
    return {"post_id": post_id, "caption": caption, "date_posted": f"{date}T00:00:00Z",
            "content_type": content_type, "url": f"https://instagram.com/p/{post_id}",
            "likes": 1, "num_comments": 1}


def test_enumerate_newest_first_sorts_newest_first(monkeypatch):
    raw = [_raw_row("old", "2026-07-01"), _raw_row("new", "2026-08-01"), _raw_row("mid", "2026-07-15")]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    items = ig.enumerate_newest_first("somehandle", keyword_filter=None)
    assert [i["id"] for i in items] == ["new", "mid", "old"]


def test_enumerate_newest_first_caps_at_max_items_per_run(monkeypatch):
    raw = [_raw_row(f"p{i}", "2026-08-01") for i in range(25)]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    monkeypatch.setattr(ig, "MAX_ITEMS_PER_RUN", 10)
    items = ig.enumerate_newest_first("somehandle", keyword_filter=None)
    assert len(items) == 10


def test_enumerate_newest_first_drops_undated_and_idless_rows(monkeypatch):
    raw = [_raw_row("good", "2026-08-01"), {"caption": "no id"}, {"post_id": "no_date", "caption": "x", "date_posted": ""}]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    items = ig.enumerate_newest_first("somehandle", keyword_filter=None)
    assert [i["id"] for i in items] == ["good"]


def test_enumerate_newest_first_applies_keyword_filter_to_caption(monkeypatch):
    raw = [_raw_row("a", "2026-08-01", caption="talks about gardens"), _raw_row("b", "2026-08-01", caption="talks about cars")]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    items = ig.enumerate_newest_first("somehandle", keyword_filter="garden")
    assert [i["id"] for i in items] == ["a"]


def test_enumerate_newest_first_populates_cache_for_download_item(monkeypatch):
    raw = [_raw_row("p1", "2026-08-01", caption="full caption text")]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    assert ig._ENUMERATE_CACHE["somehandle"]["p1"]["caption"] == "full caption text"


def test_enumerate_newest_first_overwrites_previous_cache_entry(monkeypatch):
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: [_raw_row("old_batch", "2026-07-01")])
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: [_raw_row("new_batch", "2026-08-01")])
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    assert "old_batch" not in ig._ENUMERATE_CACHE["somehandle"]
    assert "new_batch" in ig._ENUMERATE_CACHE["somehandle"]


def test_enumerate_newest_first_propagates_timeout(monkeypatch):
    def raise_timeout(handle):
        raise ig.BrightDataJobTimeout("timed out")
    monkeypatch.setattr(ig, "_run_collection_job", raise_timeout)
    with pytest.raises(ig.BrightDataJobTimeout):
        ig.enumerate_newest_first("somehandle", keyword_filter=None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_instagram.py -v`
Expected: FAIL with `AttributeError: module 'pipeline_app.discovery_instagram' has no attribute 'enumerate_newest_first'`

- [ ] **Step 3: Implement enumerate_newest_first**

Add to `pipeline-app/pipeline_app/discovery_instagram.py`:

```python
# handle -> item_id -> normalized row. Populated by enumerate_newest_first,
# read by download_item. Per-process, per-run cache -- see the design doc's
# "Cache concurrency" section for the documented, accepted race with
# validate_handle mode.
_ENUMERATE_CACHE: dict[str, dict[str, dict]] = {}


def enumerate_newest_first(handle: str, keyword_filter: str | None) -> list[dict]:
    raw_rows = _run_collection_job(handle)  # raises BrightDataJobTimeout/Failed -- never swallowed here
    normalized = [_normalize_row(r) for r in raw_rows]
    dropped = sum(1 for n in normalized if n is None)
    if dropped:
        print(f"  ! {dropped} Bright Data row(s) for {handle} dropped (missing id or unusable date)",
              file=sys.stderr)
    normalized = [n for n in normalized if n is not None]
    normalized.sort(key=lambda n: n["published"], reverse=True)
    # Client-side backstop cap, independent of whether Bright Data's trigger
    # actually honors num_of_posts (see Task 2's comment) -- bounds cost
    # regardless of that unverified assumption.
    normalized = normalized[:MAX_ITEMS_PER_RUN]

    # Overwrite, not merge: a fresh successful enumerate replaces whatever
    # this handle's cache held before, so download_item never reads a stale
    # id from a previous run in the same process.
    _ENUMERATE_CACHE[handle] = {n["id"]: n for n in normalized}

    items = normalized
    if keyword_filter:
        items = [i for i in items if keyword_filter.lower() in i["caption"].lower()]
    return [
        {"id": i["id"], "title": i["title"], "published": i["published"], "content_type": i["content_type"]}
        for i in items
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_instagram.py -v`
Expected: PASS (19 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_instagram.py pipeline-app/tests/test_discovery_instagram.py
git commit -m "feat(discovery): add Instagram enumerate_newest_first with cache and cap"
```

---

### Task 5: on_disk_ids, peek_upload_date, download_item

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_instagram.py`
- Test: `pipeline-app/tests/test_discovery_instagram.py`

**Interfaces:**
- Consumes: `_ENUMERATE_CACHE` (Task 4), `discovery_paths.handle_dir(repo_root, platform, handle) -> Path`, `artifacts.render_frontmatter(meta: dict, body: str) -> str`.
- Produces: `on_disk_ids(repo_root: Path, handle: str) -> set[str]`, `peek_upload_date(item_id: str) -> str | None`, `download_item(repo_root: Path, handle: str, item_id: str, title: str, content_type: str | None = None) -> dict`. This completes the `PlatformAdapter` protocol — the module is now a valid adapter.

- [ ] **Step 1: Write the failing tests**

```python
# append to pipeline-app/tests/test_discovery_instagram.py
def test_on_disk_ids_empty_when_directory_missing(tmp_path):
    assert ig.on_disk_ids(tmp_path, "somehandle") == set()


def test_on_disk_ids_reads_stems_of_md_files(tmp_path):
    out_dir = tmp_path / "output" / "brand-intel" / "instagram" / "somehandle"
    out_dir.mkdir(parents=True)
    (out_dir / "p1.md").write_text("x", encoding="utf-8")
    (out_dir / "p2.md").write_text("x", encoding="utf-8")
    assert ig.on_disk_ids(tmp_path, "somehandle") == {"p1", "p2"}


def test_peek_upload_date_always_none():
    assert ig.peek_upload_date("anything") is None


def test_download_item_writes_frontmatter_and_caption_from_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: [_raw_row("p1", "2026-08-01", caption="the caption")])
    ig.enumerate_newest_first("somehandle", keyword_filter=None)

    result = ig.download_item(tmp_path, "somehandle", "p1", "the caption", content_type="post")

    assert result == {"id": "p1", "ok": True, "published": "2026-08-01"}
    out_path = tmp_path / "output" / "brand-intel" / "instagram" / "somehandle" / "p1.md"
    text = out_path.read_text(encoding="utf-8")
    assert "post_id: p1" in text
    assert "content_type: post" in text
    # yaml.safe_dump (used by artifacts.render_frontmatter) quotes date-like
    # strings -- this is NOT "published: 2026-08-01", it's single-quoted.
    assert "published: '2026-08-01'" in text
    assert "the caption" in text
    assert not out_path.with_name("p1.md.tmp").exists()


def test_download_item_empty_caption_writes_placeholder(tmp_path, monkeypatch):
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: [_raw_row("p1", "2026-08-01", caption="")])
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    ig.download_item(tmp_path, "somehandle", "p1", "p1")
    out_path = tmp_path / "output" / "brand-intel" / "instagram" / "somehandle" / "p1.md"
    assert "(empty)" in out_path.read_text(encoding="utf-8")


def test_download_item_raises_on_cache_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: [_raw_row("p1", "2026-08-01")])
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    with pytest.raises(KeyError):
        ig.download_item(tmp_path, "somehandle", "not_in_cache", "title")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_instagram.py -v`
Expected: FAIL with `AttributeError: module 'pipeline_app.discovery_instagram' has no attribute 'on_disk_ids'`

- [ ] **Step 3: Implement the three functions**

Add to `pipeline-app/pipeline_app/discovery_instagram.py`:

```python
def on_disk_ids(repo_root: Path, handle: str) -> set[str]:
    directory = handle_dir(repo_root, "instagram", handle)
    if not directory.exists():
        return set()
    return {p.stem for p in directory.glob("*.md")}


def peek_upload_date(item_id: str) -> str | None:
    # Dead code by design: enumerate_newest_first only ever returns items
    # with a normalized 'published' date (Task 3/4), so process_handle's
    # `item.get("published") or adapter.peek_upload_date(item_id)` never
    # falls through to this -- same as discovery_bluesky.peek_upload_date.
    return None


def download_item(repo_root: Path, handle: str, item_id: str, title: str,
                  content_type: str | None = None) -> dict:
    # A missing handle or item_id here is a programming error (every engine
    # call path calls enumerate_newest_first for this handle in this process
    # before calling download_item) -- KeyError propagates to the per-handle
    # error path in discovery_engine.py rather than being caught here, so it
    # surfaces as a normal 'error' result instead of failing silently.
    cached = _ENUMERATE_CACHE[handle][item_id]

    out_dir = handle_dir(repo_root, "instagram", handle)
    out_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    meta = {
        "post_id": cached["id"],
        "url": cached["url"],
        "handle": handle,
        "content_type": cached["content_type"],
        "published": cached["published"],
        "like_count": cached["like_count"],
        "comment_count": cached["comment_count"],
        "fetched_at": fetched_at,
    }
    body = cached["caption"] or "(empty)"

    dest = out_dir / f"{item_id}.md"
    # Write-temp-then-rename, same as discovery_youtube.download_item and
    # discovery_bluesky.download_item: an interrupted write must never leave
    # a truncated file at a path on_disk_ids() would treat as already-captured.
    tmp_dest = dest.with_name(dest.name + ".tmp")
    tmp_dest.write_text(artifacts.render_frontmatter(meta, body), encoding="utf-8")
    tmp_dest.replace(dest)
    return {"id": item_id, "ok": True, "published": cached["published"]}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_instagram.py -v`
Expected: PASS (25 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_instagram.py pipeline-app/tests/test_discovery_instagram.py
git commit -m "feat(discovery): complete Instagram adapter (on_disk_ids, peek_upload_date, download_item)"
```

---

### Task 6: Backfill guard in discovery_engine.py

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_engine.py:184-192` (`_process_one_handle`, left unchanged) and `discovery_engine.py:301-332` (`run_discovery`'s per-handle loop)
- Test: `pipeline-app/tests/test_discovery_engine.py`

**Interfaces:**
- Produces: `BACKFILL_SUPPORTED_PLATFORMS: set[str]` (module-level constant in `discovery_engine.py`).
- Note: the design doc originally proposed this guard at the `run_discovery_cron.py` CLI layer. Planning found that's architecturally wrong — backfill mode processes *all* included handles across *all* platforms in a single `run_discovery` call (see `discovery_engine.py:305-306`'s `db_mod.list_handles(conn, included_only=True)`), not one handle at a time, so there is no single "target handle" at the CLI entry point to gate. A second revision (this one) also moves the guard out of `_process_one_handle` and into `run_discovery`'s per-handle loop directly — that's the one place that already decides each handle's recorded `status` string, and a skipped handle needs its own distinct status (`"skipped"`), not the `"ok"`/`"no_new_content"` computed from `_process_one_handle`'s return value. Recording a skip as `"no_new_content"` would reintroduce a milder version of gap 1 (a non-result reading as a healthy result) — the whole reason `enumerate_newest_first` was changed to raise instead of returning `[]` on failure.

- [ ] **Step 1: Write the failing test**

```python
# append to pipeline-app/tests/test_discovery_engine.py

def test_backfill_skips_unsupported_platform_without_calling_adapter(engine_conn, tmp_path):
    db.create_handle(engine_conn, "instagram", "@ig_handle", "IG", "guru", None, now_iso())

    class ExplodingAdapter:
        def on_disk_ids(self, repo_root, handle):
            raise AssertionError("must not be called for a backfill-unsupported platform")

        def enumerate_newest_first(self, handle, keyword_filter):
            raise AssertionError("must not be called for a backfill-unsupported platform")

        def peek_upload_date(self, item_id):
            raise AssertionError("must not be called for a backfill-unsupported platform")

        def download_item(self, repo_root, handle, item_id, title, content_type=None):
            raise AssertionError("must not be called for a backfill-unsupported platform")

    result = run_discovery(
        engine_conn, tmp_path, {"instagram": ExplodingAdapter()},
        trigger="manual", mode="backfill",
        backfill_start="2026-06-01", backfill_end="2026-06-30",
    )
    assert result["status"] == "completed"
    results = db.list_run_handle_results(engine_conn, result["run_row_id"])
    assert len(results) == 1
    assert results[0]["status"] == "skipped"
    assert results[0]["items_downloaded"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_engine.py -v -k backfill_skips_unsupported`
Expected: FAIL — the `ExplodingAdapter`'s `AssertionError` propagates (nothing currently short-circuits before `_process_one_handle` calls the adapter), is caught by `run_discovery`'s per-handle `except Exception`, and `results[0]["status"] == "error"`, not `"skipped"` as asserted.

- [ ] **Step 3: Add the constant**

In `pipeline-app/pipeline_app/discovery_engine.py`, add this near the top of the file (after the existing `NEW_HANDLE_UNDATED_STOP_GRACE` constant, around line 21):

```python
# Platforms whose adapter can serve process_handle_backfill's date-ranged
# fetch. Instagram's adapter only ever fetches the newest MAX_ITEMS_PER_RUN
# items (see discovery_instagram.py / the design doc's "Backfill support"),
# so a backfill request for it would trigger a paid Bright Data job and
# silently return nothing for any window older than that cutoff -- rejected
# here before the adapter is ever called.
BACKFILL_SUPPORTED_PLATFORMS = {"youtube", "bluesky"}
```

Leave `_process_one_handle` (currently at line 184) exactly as it is — the guard goes in the caller, not here.

- [ ] **Step 4: Add the guard in run_discovery's per-handle loop**

In `pipeline-app/pipeline_app/discovery_engine.py`, find the per-handle `for` loop inside `run_discovery` (currently lines 306-324):

```python
        for handle_row in handles:
            try:
                downloaded = _process_one_handle(adapters, repo_root, handle_row, mode, backfill_start, backfill_end, now)
```

Change it to check the backfill-support guard first, before calling `_process_one_handle` at all:

```python
        for handle_row in handles:
            try:
                if mode == "backfill" and handle_row["platform"] not in BACKFILL_SUPPORTED_PLATFORMS:
                    print(f"  ! backfill not supported for platform '{handle_row['platform']}' "
                          f"(handle {handle_row['handle']}) -- skipping, no adapter call made",
                          file=sys.stderr)
                    status = "skipped"
                    db_mod.record_handle_result(conn, run_row_id, handle_row["id"], status, 0)
                    handle_results.append({
                        "handle": handle_row["handle"], "platform": handle_row["platform"],
                        "cohort": handle_row["cohort"], "status": status, "items_downloaded": 0,
                        "last_seen_published_at": None, "error_message": None,
                    })
                    continue
                downloaded = _process_one_handle(adapters, repo_root, handle_row, mode, backfill_start, backfill_end, now)
```

The rest of the `try` block (the `published_dates = [...]` line through the end of the `except Exception` handler) is unchanged — leave it exactly as it is; the `continue` above skips it only for the guarded case. `sys` is already imported in this file.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_engine.py -v`
Expected: PASS (all tests, including the new one)

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_engine.py pipeline-app/tests/test_discovery_engine.py
git commit -m "feat(discovery): skip backfill for platforms the adapter can't serve"
```

---

### Task 7: Wire the adapter into the app

**Files:**
- Modify: `pipeline-app/run_discovery_cron.py:22-32`
- Modify: `pipeline-app/pipeline_app/templates/discovery_handles.html:34-35`
- Modify: `pipeline-app/tests/test_run_discovery_cron.py` — **this file already exists** (14 tests as of this plan, importing `run_discovery_cron as cron` directly, no `sys.path.insert` — pytest is run via `python -m pytest` from `pipeline-app/`, which puts that directory on `sys.path` itself). Append the new test to it; do not create or overwrite it.

**Interfaces:**
- Consumes: `discovery_instagram` module (Tasks 1-5), `build_adapters() -> dict[str, PlatformAdapter]` (existing function in `run_discovery_cron.py`).
- Produces: `build_adapters()` now includes `"instagram": discovery_instagram`.

- [ ] **Step 1: Append a new test to the existing file**

Open `pipeline-app/tests/test_run_discovery_cron.py` and add this test, matching the file's existing import style (`import run_discovery_cron as cron` at the top — do not add a second import or a `sys.path.insert`):

```python
# append to pipeline-app/tests/test_run_discovery_cron.py
def test_build_adapters_includes_all_three_platforms():
    adapters = cron.build_adapters()
    assert set(adapters.keys()) == {"youtube", "bluesky", "instagram"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_run_discovery_cron.py -v`
Expected: FAIL — `assert {'youtube', 'bluesky'} == {'youtube', 'bluesky', 'instagram'}`

- [ ] **Step 3: Register the adapter**

In `pipeline-app/run_discovery_cron.py`, change:

```python
from pipeline_app import discovery_bluesky, discovery_youtube
```

to:

```python
from pipeline_app import discovery_bluesky, discovery_instagram, discovery_youtube
```

and change:

```python
def build_adapters():
    return {"youtube": discovery_youtube, "bluesky": discovery_bluesky}
```

to:

```python
def build_adapters():
    return {"youtube": discovery_youtube, "bluesky": discovery_bluesky, "instagram": discovery_instagram}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_run_discovery_cron.py -v`
Expected: PASS

- [ ] **Step 5: Add the UI option**

In `pipeline-app/pipeline_app/templates/discovery_handles.html`, change:

```html
    <option value="youtube">YouTube</option>
    <option value="bluesky">Bluesky</option>
```

to:

```html
    <option value="youtube">YouTube</option>
    <option value="bluesky">Bluesky</option>
    <option value="instagram">Instagram</option>
```

- [ ] **Step 6: Run the full test suite**

Run: `cd pipeline-app && python -m pytest tests/ -v`
Expected: PASS (all tests, no regressions)

- [ ] **Step 7: Commit**

```bash
git add pipeline-app/run_discovery_cron.py pipeline-app/pipeline_app/templates/discovery_handles.html pipeline-app/tests/test_run_discovery_cron.py
git commit -m "feat(discovery): wire Instagram adapter into cron entry point and handle-registration UI"
```

---

## Post-implementation setup (not a code task)

Before this adapter can run against real data, two manual, non-code steps are required — called out here so they aren't lost:

1. Provision the Instagram Posts Scraper API product in the Bright Data dashboard, obtain its dataset ID, and replace the `DATASET_ID = "gd_REPLACE_WITH_REAL_DATASET_ID"` placeholder in `discovery_instagram.py` with the real value.
2. Trigger one real collection job by hand (e.g. via `curl` or the Bright Data dashboard's test UI) against a known public Instagram handle, and diff the actual response against `_normalize_row`'s assumed field names (`post_id`, `caption`, `date_posted`, `content_type`, `url`, `likes`, `num_comments`). Update `_normalize_row` if they differ — this is the one place in the codebase that assumption lives.
