# Facebook Bright Data Discovery Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `facebook` platform to the discovery pipeline that captures a Facebook Page's or profile's newest posts (including Reels) via Bright Data's Pages Posts dataset.

**Architecture:** One new module, `pipeline_app/discovery_facebook.py`, structurally identical to `discovery_instagram.py`: a plain module (not a class — there is only one mode) that satisfies `discovery_engine.PlatformAdapter` structurally. It delegates the whole trigger → poll → fetch cycle to the existing `brightdata_job` client and holds only Facebook-specific concerns: dataset id, URL construction, row normalization, and a per-process enumerate cache. Two one-line registrations wire it in.

**Tech Stack:** Python 3.14, `pytest`, `requests` (only via `brightdata_job`), `pyyaml` (only via `artifacts.render_frontmatter`).

**Spec:** [`docs/superpowers/specs/2026-08-08-facebook-brightdata-adapter-design.md`](../specs/2026-08-08-facebook-brightdata-adapter-design.md)

## Global Constraints

Every task's requirements implicitly include this section.

- **Do not modify `pipeline_app/brightdata_job.py`.** It is shared with the Instagram and LinkedIn adapters and needs no change; leaving it untouched makes their suites a regression gate on this work.
- **Do not modify `pipeline_app/discovery_engine.py`.** `BACKFILL_SUPPORTED_PLATFORMS` is a `{"youtube", "bluesky"}` whitelist, so `facebook` is already rejected from backfill before any adapter call. The guard is inherited, not added.
- **The trigger body must never contain `posts_to_not_include`, `start_date`, or `end_date`.** All three are verified working against the vendor and all three are deliberately unused. `posts_to_not_include` in particular turns incremental mode into an unbounded historical walk-back — see the spec's "Rejected on analysis". Task 2 pins this by test.
- **The trigger must send no `type` or `discover_by` query param.** This product has no discovery mode, unlike the Instagram and LinkedIn datasets.
- `DATASET_ID = "gd_lkaxegm826bjpoo9m5"` (Facebook Pages Posts). Not a secret.
- `MAX_ITEMS_PER_RUN = 10`, `POLL_TIMEOUT_S = 300`, `POLL_INTERVAL_S = 5`.
- **Run all tests from the `pipeline-app/` directory**, e.g. `cd pipeline-app && python -m pytest tests/test_discovery_facebook.py -v`. There is no pytest config file; imports resolve from that working directory.
- Every field mapping traces to the five live jobs recorded in the spec's "Live verification". Do not add a mapping the spec does not list.

---

## File Structure

| File | Responsibility |
|---|---|
| `pipeline-app/pipeline_app/discovery_facebook.py` | **Create.** The entire adapter: constants, date parsing, row normalization, URL construction, job cycle, the four `PlatformAdapter` methods. |
| `pipeline-app/tests/test_discovery_facebook.py` | **Create.** Unit tests against a fake HTTP layer. No real Bright Data calls. |
| `pipeline-app/run_discovery_cron.py` | **Modify.** One import, one `build_adapters()` entry. |
| `pipeline-app/pipeline_app/templates/discovery_handles.html` | **Modify.** One `<option>`, one placeholder string. |
| `pipeline-app/tests/test_run_discovery_cron.py` | **Modify.** Assert the new registration. |

The adapter is one file because that is the established shape for this codebase (`discovery_instagram.py` is 298 lines and does the same job). Splitting normalization from transport would break the pattern the other four adapters share for no gain at this size.

---

### Task 1: Date parsing and row normalization

Pure functions, no network, no filesystem. This is where every verified field mapping and every documented trap lives.

**Files:**
- Create: `pipeline-app/pipeline_app/discovery_facebook.py`
- Test: `pipeline-app/tests/test_discovery_facebook.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `PLATFORM: str = "facebook"`
  - `DATASET_ID: str`, `MAX_ITEMS_PER_RUN: int`, `POLL_TIMEOUT_S: int`, `POLL_INTERVAL_S: int`, `KEY_ENV_VAR: str`, `KEY_FILE: Path`
  - `_parse_published(raw: str | None) -> str | None`
  - `_normalize_row(row: dict) -> dict | None` — returns a dict with keys `id, title, published, published_ts, content_type, author, profile_id, is_page, body, url, like_count, comment_count, share_count, view_count, hashtags`
  - `_error_codes(raw_rows: list[dict]) -> list[str]`

- [ ] **Step 1: Write the failing tests**

Create `pipeline-app/tests/test_discovery_facebook.py`:

```python
from pipeline_app import discovery_facebook as fb


def _raw_row(**overrides):
    """A row shaped like the live payload from snapshot sd_mskdsc8e27l3f2p9yn.

    Note there is NO 'hashtags' key: the live Pages Posts rows omit it
    entirely, while the Reels product returns it as null. Both must
    normalize to [].
    """
    row = {
        "post_id": "1479086397353733",
        "date_posted": "2026-07-06T19:01:04.000Z",
        "timestamp": "2026-08-08T13:00:43.704Z",
        "post_type": "Reel",
        "profile_handle": "MrBeast6000",
        "user_username_raw": "MrBeast Gaming",
        "profile_id": "100057571594903",
        "is_page": True,
        "content": "$10,000 Every Boss You Beat",
        "url": "https://www.facebook.com/reel/1157962813213302/",
        "shortcode": "1479086397353733",
        "likes": 2836,
        "num_likes_type": {"type": "Like", "num": 2429},
        "num_comments": 149,
        "num_shares": 70,
        "video_view_count": 88381,
    }
    row.update(overrides)
    return row


def _error_row(url="https://www.facebook.com/NASA", code="dead_page"):
    """With include_errors=true, a failure arrives as a ROW, not an absence."""
    return {
        "timestamp": "2026-08-08T13:00:27.576Z",
        "input": {"url": url, "num_of_posts": 3},
        "error": "Seems page have not reels",
        "error_code": code,
    }


def test_parse_published_accepts_the_verified_iso_format():
    """Live Facebook rows carry real ISO 8601 UTC -- 2026-07-06T19:01:04.000Z
    (verified 2026-08-08), same as LinkedIn and UNLIKE Instagram, which
    returns a US-format local timestamp. The MM-DD-YYYY format in Bright
    Data's snippets is input-only and does not describe output."""
    assert fb._parse_published("2026-07-06T19:01:04.000Z") == "2026-07-06"
    assert fb._parse_published("2026-07-06") == "2026-07-06"


def test_parse_published_rejects_unusable_values():
    assert fb._parse_published("") is None
    assert fb._parse_published(None) is None
    assert fb._parse_published("garbage") is None
    # US-format input is NOT silently reinterpreted: guessing between MM/DD
    # and DD/MM yields silently wrong dates, which is worse than a dropped
    # row -- and drops are counted and logged.
    assert fb._parse_published("07-06-2026") is None


def test_normalize_row_maps_every_verified_field():
    n = fb._normalize_row(_raw_row())
    assert n["id"] == "1479086397353733"
    assert n["published"] == "2026-07-06"
    assert n["content_type"] == "reel"
    assert n["author"] == "MrBeast6000"
    assert n["profile_id"] == "100057571594903"
    assert n["is_page"] is True
    assert n["body"] == "$10,000 Every Boss You Beat"
    assert n["url"] == "https://www.facebook.com/reel/1157962813213302/"
    assert n["comment_count"] == 149
    assert n["share_count"] == 70
    assert n["view_count"] == 88381


def test_like_count_comes_from_likes_not_num_likes_type():
    """`likes` is the reaction TOTAL (2836). `num_likes_type` is a dict
    holding only the 'Like' subtotal (2429) -- a different, smaller number.
    Reading it would understate engagement on every row."""
    n = fb._normalize_row(_raw_row())
    assert n["like_count"] == 2836


def test_timestamp_is_never_used_as_the_post_date():
    """`timestamp` is SCRAPE time, not post time -- 2026-08-08 on a post
    dated 2026-07-06. It reads as a plausible date field and is wrong by
    however long ago the post was made."""
    n = fb._normalize_row(_raw_row())
    assert n["published"] == "2026-07-06"
    assert not n["published_ts"].startswith("2026-08-08")


def test_published_ts_keeps_the_full_timestamp_for_sorting():
    n = fb._normalize_row(_raw_row())
    assert n["published_ts"] == "2026-07-06T19:01:04.000Z"


def test_hashtags_normalize_to_a_list_whether_absent_or_null():
    """VERIFIED LIVE: the key is ABSENT from Pages Posts rows and present-
    but-null on Reels rows. Both shapes are real."""
    assert fb._normalize_row(_raw_row())["hashtags"] == []
    assert fb._normalize_row(_raw_row(hashtags=None))["hashtags"] == []
    assert fb._normalize_row(_raw_row(hashtags=["#a"]))["hashtags"] == ["#a"]


def test_content_type_is_lowercased():
    """Bright Data returns display-cased values: 'Post', 'Reel'."""
    assert fb._normalize_row(_raw_row(post_type="Post"))["content_type"] == "post"
    assert fb._normalize_row(_raw_row(post_type="Reel"))["content_type"] == "reel"


def test_reel_is_preserved_as_a_real_content_type():
    """Reels are captured through this dataset rather than the dedicated
    Reels product; 'reel' is a valid value, not an error to coerce away."""
    assert fb._normalize_row(_raw_row(post_type="Reel"))["content_type"] == "reel"


def test_title_is_the_first_line_of_content():
    n = fb._normalize_row(_raw_row(content="First line.\nSecond line."))
    assert n["title"] == "First line."


def test_title_truncates_to_60_chars():
    n = fb._normalize_row(_raw_row(content="x" * 100))
    assert n["title"] == "x" * 60


def test_title_falls_back_to_post_id_when_content_is_empty():
    """Image-only posts genuinely have empty content -- a real case."""
    n = fb._normalize_row(_raw_row(content=""))
    assert n["title"] == "1479086397353733"


def test_normalize_row_returns_none_without_post_id():
    assert fb._normalize_row(_raw_row(post_id="")) is None


def test_normalize_row_returns_none_with_unusable_date():
    assert fb._normalize_row(_raw_row(date_posted="")) is None
    assert fb._normalize_row(_raw_row(date_posted="garbage")) is None


def test_normalize_row_drops_an_include_errors_error_row():
    """Error rows carry no post_id, so the id check already rejects them."""
    assert fb._normalize_row(_error_row()) is None


def test_normalize_row_tolerates_missing_optional_fields():
    n = fb._normalize_row({"post_id": "1", "date_posted": "2026-07-06T00:00:00.000Z"})
    assert n["body"] == ""
    assert n["author"] == ""
    assert n["hashtags"] == []
    assert n["like_count"] is None
    assert n["view_count"] is None
    assert n["content_type"] == "post"


def test_error_codes_collects_vendor_reasons():
    codes = fb._error_codes([_raw_row(), _error_row(code="dead_page"),
                             _error_row(code="not_found")])
    assert codes == ["dead_page", "not_found"]


def test_error_codes_is_empty_for_a_clean_batch():
    assert fb._error_codes([_raw_row()]) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd pipeline-app && python -m pytest tests/test_discovery_facebook.py -v
```

Expected: collection error — `ModuleNotFoundError: No module named 'pipeline_app.discovery_facebook'`.

- [ ] **Step 3: Write the implementation**

Create `pipeline-app/pipeline_app/discovery_facebook.py`:

```python
"""Facebook platform adapter for the discovery engine, backed by Bright
Data's Facebook Pages Posts dataset.

Despite the product name, this dataset serves BOTH Pages and personal
profiles -- verified live 2026-08-08, where facebook.com/zuck returned rows
with is_page=False. It also returns Reels, tagged post_type='Reel'. Bright
Data's dedicated Reels dataset was evaluated and dropped: every reel it
returned was already returned here, and it reported 'dead_page' for an
account whose reels this dataset was serving in the same minute.

Field names below are from five live jobs on 2026-08-08, not from the
published field list. See docs/superpowers/specs/2026-08-08-facebook-
brightdata-adapter-design.md.
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

from pipeline_app import artifacts, brightdata_job
from pipeline_app.discovery_paths import handle_dir

PLATFORM = "facebook"

# Not a secret -- read off Bright Data's published endpoint index for the
# Facebook Pages Posts product (2026-08-08). This product has no discovery
# mode, so no type/discover_by query params are sent.
DATASET_ID = "gd_lkaxegm826bjpoo9m5"

KEY_ENV_VAR = "BRIGHTDATA_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "brightdata_api_key.txt"

MAX_ITEMS_PER_RUN = 10
POLL_TIMEOUT_S = 300
POLL_INTERVAL_S = 5

TITLE_MAX_CHARS = 60


def _parse_published(raw: str | None) -> str | None:
    """Bright Data's date_posted -> the engine's required YYYY-MM-DD, or None.

    This dataset returns genuine ISO 8601 UTC -- '2026-07-06T19:01:04.000Z'
    (verified 2026-08-08) -- so a 10-character prefix is correct. That is NOT
    true of Bright Data's Instagram product, which returns a US-format local
    timestamp; the datasets disagree, so no format may be inferred from a
    sibling product.

    The MM-DD-YYYY format that appears in Bright Data's Facebook snippets is
    an INPUT format for start_date/end_date and does not describe output.

    US-format input is deliberately NOT accepted. Guessing between MM-DD and
    DD-MM would yield silently wrong dates, which is worse than a dropped row
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


def _normalize_row(row: dict) -> dict | None:
    """One raw Bright Data row -> this adapter's internal shape, or None if
    the row is unusable. The single place to update if the schema changes.

    Three returned fields are deliberately NOT read, each a live trap:
    - `timestamp` is SCRAPE time, not post time (2026-08-08 on a July post).
    - `shortcode` is not a stable identity: for one post the Reels product
      returned '1157962813213302' and this one returned '1479086397353733'.
    - `page_likes` returned 0 on an account reporting 1.4M page_followers.
    """
    post_id = row.get("post_id")
    if not post_id:
        return None
    published = _parse_published(row.get("date_posted"))
    if published is None:
        return None

    body = (row.get("content") or "").strip()
    first_line = body.split("\n", 1)[0].strip()
    title = first_line or str(post_id)

    raw_date_posted = (row.get("date_posted") or "").strip()

    return {
        "id": str(post_id),
        "title": title[:TITLE_MAX_CHARS],
        "published": published,
        # Full ISO 8601 timestamp, used only as the sort key -- 'published'
        # truncates to the date, so same-day rows would otherwise sort in
        # Bright Data's arrival order. Lexicographic comparison is correct
        # for this dataset's real ISO 8601 strings (verified 2026-08-08).
        # raw_date_posted is guaranteed non-empty here (the published check
        # above already required it), but the "or" fallback keeps this key
        # total rather than crashing if that ever stops being true.
        "published_ts": raw_date_posted or f"{published}T00:00:00",
        # Observed values: 'Post', 'Reel' -- display-cased, so lowercase.
        "content_type": (row.get("post_type") or "post").strip().lower(),
        # Recorded, never filtered on: a numeric handle returns the VANITY
        # profile_handle ('NASA'), so comparing it to the tracked handle
        # would discard every row. It is what makes a future regression
        # (this dataset starting to return other accounts) detectable.
        "author": (row.get("profile_handle") or "").strip(),
        "profile_id": row.get("profile_id") or "",
        "is_page": row.get("is_page"),
        "body": body,
        "url": row.get("url") or "",
        # `likes` is the reaction TOTAL. `num_likes_type` is a dict holding
        # only the 'Like' subtotal -- a different, smaller number.
        "like_count": row.get("likes"),
        "comment_count": row.get("num_comments"),
        "share_count": row.get("num_shares"),
        "view_count": row.get("video_view_count"),
        # Absent on Pages Posts rows, null on Reels rows -- both are real.
        "hashtags": row.get("hashtags") or [],
    }


def _error_codes(raw_rows: list[dict]) -> list[str]:
    """Vendor error codes from an include_errors=true batch.

    With include_errors=true a failure arrives as a ROW carrying `error` and
    `error_code` rather than as an absence, so the adapter can log Bright
    Data's own reason ('dead_page') instead of a bare drop count.
    """
    return [r.get("error_code") or "unknown" for r in raw_rows if r.get("error")]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd pipeline-app && python -m pytest tests/test_discovery_facebook.py -v
```

Expected: PASS (18 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_facebook.py pipeline-app/tests/test_discovery_facebook.py
git commit -m "feat(discovery): add Facebook row normalization and date parsing"
```

---

### Task 2: URL construction and the Bright Data job cycle

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_facebook.py` (append)
- Test: `pipeline-app/tests/test_discovery_facebook.py` (append)

**Interfaces:**
- Consumes: `DATASET_ID`, `MAX_ITEMS_PER_RUN`, `POLL_TIMEOUT_S`, `POLL_INTERVAL_S`, `KEY_ENV_VAR`, `KEY_FILE` from Task 1.
- Produces:
  - `BRIGHTDATA_API_BASE: str`, `BrightDataJobTimeout`, `BrightDataJobFailed` (re-exports)
  - `api_key() -> str | None`
  - `profile_url(handle: str) -> str`
  - `_trigger_job(handle: str, key: str) -> str`
  - `_poll_job_status(job_id: str, key: str) -> str`
  - `_fetch_job_results(job_id: str, key: str) -> list[dict]`
  - `_run_collection_job(handle: str) -> list[dict]`

- [ ] **Step 1: Write the failing tests**

Append to `pipeline-app/tests/test_discovery_facebook.py`:

```python
import pytest

from pipeline_app import brightdata_job


def test_profile_url_uses_the_vanity_slug_form_for_named_handles():
    assert fb.profile_url("NASA") == "https://www.facebook.com/NASA"
    assert fb.profile_url("MrBeast6000") == "https://www.facebook.com/MrBeast6000"
    # A pasted @-prefixed handle still resolves.
    assert fb.profile_url("@zuck") == "https://www.facebook.com/zuck"


def test_profile_url_uses_profile_php_for_all_numeric_handles():
    """VERIFIED LIVE: profile.php?id=100044561550831 resolved to NASA. The
    bare facebook.com/<numeric-id> form was NOT tested, so it is not used --
    there is no reason to guess when a verified form exists."""
    assert fb.profile_url("100044561550831") == \
        "https://www.facebook.com/profile.php?id=100044561550831"


def test_trigger_job_sends_the_verified_request_shape(monkeypatch):
    captured = {}

    def fake_trigger(api_base, dataset_id, params, body, key):
        captured.update(api_base=api_base, dataset_id=dataset_id, params=params,
                        body=body, key=key)
        return "snap1"

    monkeypatch.setattr(brightdata_job, "trigger", fake_trigger)
    assert fb._trigger_job("NASA", "the-key") == "snap1"

    assert captured["dataset_id"] == fb.DATASET_ID
    assert captured["key"] == "the-key"
    assert captured["params"]["include_errors"] == "true"
    assert captured["params"]["notify"] == "false"
    # Bare array, not {"input": [...]} -- the object form belongs to the
    # synchronous /scrape endpoint. Verified HTTP 200 with the bare array.
    assert captured["body"] == [{
        "url": "https://www.facebook.com/NASA",
        "num_of_posts": fb.MAX_ITEMS_PER_RUN,
    }]


def test_trigger_job_sends_no_discovery_params(monkeypatch):
    """Unlike the Instagram and LinkedIn datasets, this product has no
    discovery mode. Sending type/discover_by would select a mode that does
    not exist here."""
    captured = {}
    monkeypatch.setattr(brightdata_job, "trigger",
                        lambda a, d, params, b, k: captured.update(params=params) or "s")
    fb._trigger_job("NASA", "the-key")
    assert "type" not in captured["params"]
    assert "discover_by" not in captured["params"]


def test_trigger_job_never_sends_exclusion_or_date_window_keys(monkeypatch):
    """All three of posts_to_not_include / start_date / end_date verified
    WORKING against the vendor and all three are deliberately unused.

    posts_to_not_include is the dangerous one. Excluding on-disk ids
    server-side removes them from the response, which disables BOTH of
    process_handle's termination conditions -- the early-stop counter needs
    on-disk ids to APPEAR (discovery_engine.py:54-57), and the lookback
    cutoff only applies while is_new (:44-45, :61-70). Every later run would
    then download MAX_ITEMS_PER_RUN progressively OLDER posts, daily, until
    the account's whole back-catalogue landed -- in the mode whose only job
    is new content. See the spec's "Rejected on analysis".
    """
    captured = {}
    monkeypatch.setattr(brightdata_job, "trigger",
                        lambda a, d, p, body, k: captured.update(body=body) or "s")
    fb._trigger_job("NASA", "the-key")

    for forbidden in ("posts_to_not_include", "start_date", "end_date"):
        assert forbidden not in captured["body"][0]


def test_run_collection_job_raises_clear_error_when_key_missing(monkeypatch):
    monkeypatch.setattr(fb, "api_key", lambda: None)
    with pytest.raises(RuntimeError, match="Bright Data API key not configured"):
        fb._run_collection_job("NASA")


def test_run_collection_job_drives_full_trigger_poll_fetch_cycle(monkeypatch):
    """Nothing else exercises this wiring -- every other adapter test stubs
    _run_collection_job wholesale. A transposed callable here would survive
    the whole suite and fail on the first live run, after paying for a job.
    Assert the snapshot id trigger() returns is threaded through to
    poll_status() and fetch_results()."""
    monkeypatch.setattr(fb, "api_key", lambda: "the-key")

    poll_calls = []
    fetch_calls = []
    statuses = iter(["running", "ready"])

    monkeypatch.setattr(brightdata_job, "trigger",
                        lambda a, d, p, b, k: "snap-789")
    monkeypatch.setattr(brightdata_job, "poll_status",
                        lambda a, job_id, k: (poll_calls.append(job_id), next(statuses))[1])
    monkeypatch.setattr(brightdata_job, "fetch_results",
                        lambda a, job_id, k: (fetch_calls.append(job_id), [_raw_row()])[1])
    monkeypatch.setattr(brightdata_job.time, "sleep", lambda s: None)

    result = fb._run_collection_job("NASA")

    assert result == [_raw_row()]
    assert poll_calls == ["snap-789", "snap-789"]
    assert fetch_calls == ["snap-789"]


def test_api_key_prefers_env_var_then_file(monkeypatch, tmp_path):
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("from-file", encoding="utf-8")
    monkeypatch.setattr(fb, "KEY_FILE", key_file)

    monkeypatch.setenv(fb.KEY_ENV_VAR, "from-env")
    assert fb.api_key() == "from-env"

    monkeypatch.delenv(fb.KEY_ENV_VAR, raising=False)
    assert fb.api_key() == "from-file"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd pipeline-app && python -m pytest tests/test_discovery_facebook.py -v -k "profile_url or trigger or collection or api_key"
```

Expected: FAIL with `AttributeError: module 'pipeline_app.discovery_facebook' has no attribute 'profile_url'`.

- [ ] **Step 3: Write the implementation**

Append to `pipeline-app/pipeline_app/discovery_facebook.py`:

```python
BRIGHTDATA_API_BASE = brightdata_job.BRIGHTDATA_API_BASE

# Re-exported so `pytest.raises(discovery_facebook.BrightDataJobFailed)` works
# and callers need not know where the exceptions live.
BrightDataJobTimeout = brightdata_job.BrightDataJobTimeout
BrightDataJobFailed = brightdata_job.BrightDataJobFailed


def api_key() -> str | None:
    """The Bright Data API token, or None if not configured. Reads this
    module's KEY_ENV_VAR/KEY_FILE at call time so tests can patch them."""
    return brightdata_job.read_key(KEY_ENV_VAR, KEY_FILE)


def profile_url(handle: str) -> str:
    """The Facebook URL for a tracked handle.

    Two shapes, both verified live 2026-08-08. An all-digit handle is an
    account id and goes through profile.php?id=, which is the form that was
    tested; the bare facebook.com/<numeric-id> form was NOT tested and is
    deliberately not used.
    """
    slug = handle.lstrip("@").strip()
    if slug.isdigit():
        return f"https://www.facebook.com/profile.php?id={slug}"
    return f"https://www.facebook.com/{slug}"


def _trigger_job(handle: str, key: str) -> str:
    return brightdata_job.trigger(
        BRIGHTDATA_API_BASE,
        DATASET_ID,
        {
            # No type/discover_by: this product has no discovery mode. The
            # input URL is the account and the collector walks it.
            "include_errors": "true",
            "notify": "false",
        },
        [{
            # Server-side per-input record cap: the primary cost control.
            # Verified honored exactly -- 3 returned 3, 2 returned 2.
            "url": profile_url(handle),
            "num_of_posts": MAX_ITEMS_PER_RUN,
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
    return brightdata_job.await_results(
        trigger_fn=lambda: _trigger_job(handle, key),
        poll_fn=lambda job_id: _poll_job_status(job_id, key),
        fetch_fn=lambda job_id: _fetch_job_results(job_id, key),
        label=f"for {PLATFORM}/{handle}",
        poll_timeout_s=POLL_TIMEOUT_S,
        poll_interval_s=POLL_INTERVAL_S,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd pipeline-app && python -m pytest tests/test_discovery_facebook.py -v
```

Expected: PASS (26 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_facebook.py pipeline-app/tests/test_discovery_facebook.py
git commit -m "feat(discovery): add Facebook URL construction and job cycle"
```

---

### Task 3: `enumerate_newest_first`

Sorting, drop accounting, the all-dropped warning, the cap, `keyword_filter`, and the cache `download_item` reads.

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_facebook.py` (append)
- Test: `pipeline-app/tests/test_discovery_facebook.py` (append)

**Interfaces:**
- Consumes: `_normalize_row`, `_error_codes`, `_run_collection_job`, `MAX_ITEMS_PER_RUN`, `PLATFORM`.
- Produces:
  - `_ENUMERATE_CACHE: dict[str, dict[str, dict]]`
  - `enumerate_newest_first(handle: str, keyword_filter: str | None) -> list[dict]` — each item has keys `id, title, published, content_type`

- [ ] **Step 1: Write the failing tests**

Append to `pipeline-app/tests/test_discovery_facebook.py`:

```python
def _row(post_id, date, content="hello", post_type="Post"):
    return _raw_row(post_id=post_id, date_posted=f"{date}T00:00:00.000Z",
                    content=content, post_type=post_type)


def _stub_job(monkeypatch, rows):
    monkeypatch.setattr(fb, "_run_collection_job", lambda handle: rows)


def test_enumerate_returns_engine_shaped_items(monkeypatch):
    _stub_job(monkeypatch, [_row("p1", "2026-07-06")])
    items = fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert items == [{"id": "p1", "title": "hello", "published": "2026-07-06",
                      "content_type": "post"}]


def test_enumerate_sorts_newest_first(monkeypatch):
    _stub_job(monkeypatch, [
        _row("older", "2025-08-08"),
        _row("newest", "2026-07-06"),
        _row("middle", "2026-05-28"),
    ])
    items = fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert [i["id"] for i in items] == ["newest", "middle", "older"]


def test_enumerate_sorts_same_day_rows_by_time_not_just_date(monkeypatch):
    """The sort MUST key on the full timestamp. Python's sort is stable, so
    a date-truncated key leaves same-day rows in Bright Data's arrival
    order, which can put a genuinely newer post behind ones already on disk
    and trip discovery_engine's early-stop dedup before reaching it. Both
    sibling adapters carry a published_ts for exactly this reason."""
    _stub_job(monkeypatch, [
        _raw_row(post_id="morning", date_posted="2026-07-06T08:00:00.000Z"),
        _raw_row(post_id="evening", date_posted="2026-07-06T20:00:00.000Z"),
    ])
    items = fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert [i["id"] for i in items] == ["evening", "morning"]


def test_enumerate_caps_retained_items(monkeypatch):
    _stub_job(monkeypatch, [_row(f"p{i}", f"2026-07-{i:02d}") for i in range(1, 21)])
    items = fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert len(items) == fb.MAX_ITEMS_PER_RUN


def test_enumerate_applies_keyword_filter_against_content(monkeypatch):
    _stub_job(monkeypatch, [
        _row("hit", "2026-07-06", content="Artemis launch today"),
        _row("miss", "2026-07-05", content="Something else"),
    ])
    items = fb.enumerate_newest_first("NASA", keyword_filter="artemis")
    assert [i["id"] for i in items] == ["hit"]


def test_enumerate_drops_unusable_rows_and_logs_the_count(monkeypatch, capsys):
    _stub_job(monkeypatch, [_row("good", "2026-07-06"), _raw_row(post_id="")])
    items = fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert [i["id"] for i in items] == ["good"]
    assert "dropped 1" in capsys.readouterr().err


def test_enumerate_logs_the_vendor_error_code_not_just_a_count(monkeypatch, capsys):
    """With include_errors=true Bright Data tells us WHY. Logging
    'dead_page' instead of a bare drop count is the difference between a
    diagnosable dead slug and a mystery."""
    _stub_job(monkeypatch, [_row("good", "2026-07-06"), _error_row(code="dead_page")])
    fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert "dead_page" in capsys.readouterr().err


def test_enumerate_warns_loudly_when_rows_returned_but_none_survive(monkeypatch, capsys):
    """A billed job that captured nothing would otherwise be recorded by
    process_handle as the healthy status 'no_new_content' -- indistinguishable
    from a quiet day."""
    _stub_job(monkeypatch, [_error_row(code="dead_page")])
    assert fb.enumerate_newest_first("NASA", keyword_filter=None) == []
    err = capsys.readouterr().err
    assert "none survived" in err
    assert "dead_page" in err


def test_enumerate_returns_empty_without_warning_for_a_genuinely_empty_job(monkeypatch, capsys):
    _stub_job(monkeypatch, [])
    assert fb.enumerate_newest_first("NASA", keyword_filter=None) == []
    assert "none survived" not in capsys.readouterr().err


def test_enumerate_overwrites_rather_than_merges_the_cache(monkeypatch):
    """A fresh successful enumerate replaces whatever this handle held, so
    download_item never reads a stale id from an earlier run."""
    _stub_job(monkeypatch, [_row("old", "2026-07-01")])
    fb.enumerate_newest_first("NASA", keyword_filter=None)
    _stub_job(monkeypatch, [_row("new", "2026-07-06")])
    fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert set(fb._ENUMERATE_CACHE["NASA"]) == {"new"}


def test_enumerate_caches_per_handle(monkeypatch):
    _stub_job(monkeypatch, [_row("a1", "2026-07-06")])
    fb.enumerate_newest_first("NASA", keyword_filter=None)
    _stub_job(monkeypatch, [_row("b1", "2026-07-06")])
    fb.enumerate_newest_first("zuck", keyword_filter=None)
    assert set(fb._ENUMERATE_CACHE["NASA"]) == {"a1"}
    assert set(fb._ENUMERATE_CACHE["zuck"]) == {"b1"}


def test_enumerate_caches_items_filtered_out_by_keyword(monkeypatch):
    """keyword_filter narrows what the ENGINE walks, not what was collected
    and paid for. The cache must hold the full retained batch."""
    _stub_job(monkeypatch, [
        _row("hit", "2026-07-06", content="Artemis launch"),
        _row("miss", "2026-07-05", content="Other"),
    ])
    fb.enumerate_newest_first("NASA", keyword_filter="artemis")
    assert set(fb._ENUMERATE_CACHE["NASA"]) == {"hit", "miss"}


def test_enumerate_does_not_filter_by_author(monkeypatch):
    """Unlike linkedin-profile, this adapter must NOT drop rows whose
    profile_handle differs from the tracked handle. Across 17 live records
    profile_handle always matched, and filtering would be actively wrong: a
    numeric handle returns the VANITY profile_handle ('NASA'), so the
    comparison would discard every row for handle '100044561550831'."""
    _stub_job(monkeypatch, [_raw_row(post_id="p1", profile_handle="NASA")])
    items = fb.enumerate_newest_first("100044561550831", keyword_filter=None)
    assert [i["id"] for i in items] == ["p1"]
    assert fb._ENUMERATE_CACHE["100044561550831"]["p1"]["author"] == "NASA"


def test_enumerate_propagates_job_timeout(monkeypatch):
    def raise_timeout(handle):
        raise brightdata_job.BrightDataJobTimeout("timed out")

    monkeypatch.setattr(fb, "_run_collection_job", raise_timeout)
    with pytest.raises(brightdata_job.BrightDataJobTimeout):
        fb.enumerate_newest_first("NASA", keyword_filter=None)


def test_enumerate_propagates_job_failure(monkeypatch):
    def raise_failed(handle):
        raise brightdata_job.BrightDataJobFailed("failed")

    monkeypatch.setattr(fb, "_run_collection_job", raise_failed)
    with pytest.raises(brightdata_job.BrightDataJobFailed):
        fb.enumerate_newest_first("NASA", keyword_filter=None)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd pipeline-app && python -m pytest tests/test_discovery_facebook.py -v -k enumerate
```

Expected: FAIL with `AttributeError: module 'pipeline_app.discovery_facebook' has no attribute 'enumerate_newest_first'`.

- [ ] **Step 3: Write the implementation**

Append to `pipeline-app/pipeline_app/discovery_facebook.py`:

```python
# handle -> item_id -> normalized row. Populated by enumerate_newest_first,
# read by download_item. Calling Bright Data again per item would double-pay
# for posts already collected. Per-process: run_discovery_cron is always
# invoked as a subprocess, so no entry outlives a single run.
_ENUMERATE_CACHE: dict[str, dict[str, dict]] = {}


def enumerate_newest_first(handle: str, keyword_filter: str | None) -> list[dict]:
    # Raises BrightDataJobTimeout/BrightDataJobFailed -- never swallowed here.
    # An empty return must mean "the job completed and there was nothing",
    # nothing else.
    raw_rows = _run_collection_job(handle)

    normalized = [_normalize_row(r) for r in raw_rows]
    unusable = sum(1 for n in normalized if n is None)
    kept = [n for n in normalized if n is not None]
    codes = _error_codes(raw_rows)

    if unusable:
        detail = f" ({', '.join(sorted(set(codes)))})" if codes else ""
        print(f"  ! {PLATFORM}/{handle}: dropped {unusable} unusable row(s){detail}",
              file=sys.stderr)

    if raw_rows and not kept:
        # This run was billed and produced nothing, but process_handle will
        # record the healthy status 'no_new_content' -- indistinguishable
        # from a quiet day unless it is loud here.
        detail = f" Bright Data reported: {', '.join(sorted(set(codes)))}." if codes else ""
        print(f"  !! {PLATFORM}/{handle}: Bright Data returned {len(raw_rows)} "
              f"row(s) but none survived filtering. This run was billed and "
              f"captured nothing -- check whether this handle is still valid."
              f"{detail}", file=sys.stderr)

    # Sort on the full timestamp, not the date-truncated 'published': Python's
    # sort is stable, so same-day rows sorted on 'published' alone would keep
    # Bright Data's arrival order, which can put a genuinely newer post behind
    # ones already on disk and trip the early-stop dedup before reaching it.
    # Cap AFTER sorting so it bounds retained items.
    kept.sort(key=lambda n: n["published_ts"], reverse=True)
    kept = kept[:MAX_ITEMS_PER_RUN]

    # Overwrite, not merge: a fresh successful enumerate replaces whatever
    # this handle held, so download_item never reads a stale id. Cached
    # BEFORE keyword_filter -- the filter narrows what the engine walks, not
    # what was collected and paid for.
    _ENUMERATE_CACHE[handle] = {n["id"]: n for n in kept}

    items = kept
    if keyword_filter:
        items = [i for i in items if keyword_filter.lower() in i["body"].lower()]
    return [
        {"id": i["id"], "title": i["title"], "published": i["published"],
         "content_type": i["content_type"]}
        for i in items
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd pipeline-app && python -m pytest tests/test_discovery_facebook.py -v
```

Expected: PASS (41 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_facebook.py pipeline-app/tests/test_discovery_facebook.py
git commit -m "feat(discovery): add Facebook enumerate_newest_first"
```

---

### Task 4: Filesystem methods — `on_disk_ids`, `peek_upload_date`, `download_item`

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_facebook.py` (append)
- Test: `pipeline-app/tests/test_discovery_facebook.py` (append)

**Interfaces:**
- Consumes: `_ENUMERATE_CACHE`, `PLATFORM`, `handle_dir`, `artifacts.render_frontmatter`.
- Produces:
  - `on_disk_ids(repo_root: Path, handle: str) -> set[str]`
  - `peek_upload_date(item_id: str) -> None`
  - `download_item(repo_root: Path, handle: str, item_id: str, title: str, content_type: str | None = None) -> dict`

  After this task the module structurally satisfies `discovery_engine.PlatformAdapter`.

- [ ] **Step 1: Write the failing tests**

Append to `pipeline-app/tests/test_discovery_facebook.py`:

```python
from pipeline_app import artifacts
from pipeline_app.discovery_paths import handle_dir


def test_on_disk_ids_is_empty_for_a_missing_directory(tmp_path):
    assert fb.on_disk_ids(tmp_path, "NASA") == set()


def test_on_disk_ids_reads_md_stems(tmp_path):
    d = handle_dir(tmp_path, "facebook", "NASA")
    d.mkdir(parents=True)
    (d / "1596499905178713.md").write_text("x", encoding="utf-8")
    (d / "1596305355198168.md").write_text("x", encoding="utf-8")
    (d / "notes.txt").write_text("x", encoding="utf-8")
    assert fb.on_disk_ids(tmp_path, "NASA") == {"1596499905178713", "1596305355198168"}


def test_on_disk_ids_matches_the_string_post_id_exactly(tmp_path):
    """post_id is a JSON string and on_disk_ids compares filename stems. A
    numeric id would never match, and every run would re-download and re-pay
    in silence."""
    d = handle_dir(tmp_path, "facebook", "NASA")
    d.mkdir(parents=True)
    (d / "1596499905178713.md").write_text("x", encoding="utf-8")
    assert "1596499905178713" in fb.on_disk_ids(tmp_path, "NASA")


def test_peek_upload_date_is_dead_code_by_design():
    """enumerate_newest_first only ever returns items carrying a normalized
    'published', so process_handle never falls through to this."""
    assert fb.peek_upload_date("anything") is None


def test_download_item_writes_frontmatter_and_body(tmp_path, monkeypatch):
    _stub_job(monkeypatch, [_raw_row()])
    fb.enumerate_newest_first("MrBeast6000", keyword_filter=None)

    result = fb.download_item(tmp_path, "MrBeast6000", "1479086397353733", "ignored")
    assert result == {"id": "1479086397353733", "ok": True, "published": "2026-07-06"}

    dest = handle_dir(tmp_path, "facebook", "MrBeast6000") / "1479086397353733.md"
    meta, body = artifacts.parse_frontmatter(dest.read_text(encoding="utf-8"))

    assert meta["post_id"] == "1479086397353733"
    assert meta["handle"] == "MrBeast6000"
    assert meta["author"] == "MrBeast6000"
    assert meta["profile_id"] == "100057571594903"
    assert meta["is_page"] is True
    assert meta["content_type"] == "reel"
    assert meta["published"] == "2026-07-06"
    assert meta["like_count"] == 2836
    assert meta["comment_count"] == 149
    assert meta["share_count"] == 70
    assert meta["view_count"] == 88381
    assert meta["hashtags"] == []
    assert "fetched_at" in meta
    assert body.strip() == "$10,000 Every Boss You Beat"


def test_download_item_writes_empty_placeholder_for_image_only_posts(tmp_path, monkeypatch):
    """Image-only posts genuinely have empty content -- a real case."""
    _stub_job(monkeypatch, [_raw_row(content="")])
    fb.enumerate_newest_first("MrBeast6000", keyword_filter=None)
    fb.download_item(tmp_path, "MrBeast6000", "1479086397353733", "ignored")

    dest = handle_dir(tmp_path, "facebook", "MrBeast6000") / "1479086397353733.md"
    _, body = artifacts.parse_frontmatter(dest.read_text(encoding="utf-8"))
    assert body.strip() == "(empty)"


def test_download_item_leaves_no_tmp_file(tmp_path, monkeypatch):
    """Write-temp-then-rename: an interrupted write must never leave a
    truncated file at a path on_disk_ids() would treat as captured."""
    _stub_job(monkeypatch, [_raw_row()])
    fb.enumerate_newest_first("MrBeast6000", keyword_filter=None)
    fb.download_item(tmp_path, "MrBeast6000", "1479086397353733", "ignored")

    d = handle_dir(tmp_path, "facebook", "MrBeast6000")
    assert list(d.glob("*.tmp")) == []


def test_download_item_raises_on_cache_miss_rather_than_degrading(tmp_path, monkeypatch):
    """A missing entry is a programming error: every engine call path runs
    enumerate_newest_first for this handle first. KeyError propagates to
    run_discovery's per-handle error path instead of failing silently."""
    _stub_job(monkeypatch, [_raw_row()])
    fb.enumerate_newest_first("MrBeast6000", keyword_filter=None)
    with pytest.raises(KeyError):
        fb.download_item(tmp_path, "MrBeast6000", "nonexistent-id", "ignored")


def test_download_item_makes_no_network_call(tmp_path, monkeypatch):
    """download_item reads the cache. Calling Bright Data once per item
    would double-pay for posts already collected."""
    _stub_job(monkeypatch, [_raw_row()])
    fb.enumerate_newest_first("MrBeast6000", keyword_filter=None)

    def boom(*a, **k):
        raise AssertionError("download_item must not call Bright Data")

    monkeypatch.setattr(fb, "_run_collection_job", boom)
    monkeypatch.setattr(brightdata_job, "trigger", boom)
    assert fb.download_item(tmp_path, "MrBeast6000", "1479086397353733", "x")["ok"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd pipeline-app && python -m pytest tests/test_discovery_facebook.py -v -k "on_disk or peek or download"
```

Expected: FAIL with `AttributeError: module 'pipeline_app.discovery_facebook' has no attribute 'on_disk_ids'`.

- [ ] **Step 3: Write the implementation**

Append to `pipeline-app/pipeline_app/discovery_facebook.py`:

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
    # caught here, so it surfaces as a normal 'error' instead of silently.
    cached = _ENUMERATE_CACHE[handle][item_id]

    out_dir = handle_dir(repo_root, PLATFORM, handle)
    out_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    meta = {
        "post_id": cached["id"],
        "url": cached["url"],
        "handle": handle,
        # Recorded although never filtered on: it is what makes a regression
        # (this dataset starting to return other accounts) detectable after
        # the fact, and profile_id survives a vanity-slug rename.
        "author": cached["author"],
        "profile_id": cached["profile_id"],
        "is_page": cached["is_page"],
        "content_type": cached["content_type"],
        "published": cached["published"],
        "like_count": cached["like_count"],
        "comment_count": cached["comment_count"],
        "share_count": cached["share_count"],
        "view_count": cached["view_count"],
        "hashtags": cached["hashtags"],
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

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd pipeline-app && python -m pytest tests/test_discovery_facebook.py -v
```

Expected: PASS (50 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_facebook.py pipeline-app/tests/test_discovery_facebook.py
git commit -m "feat(discovery): add Facebook on_disk_ids and download_item"
```

---

### Task 5: Register the platform and run the regression gate

**Files:**
- Modify: `pipeline-app/run_discovery_cron.py:23` (import), `:31-41` (`build_adapters`)
- Modify: `pipeline-app/pipeline_app/templates/discovery_handles.html:33-40`
- Modify: `pipeline-app/tests/test_run_discovery_cron.py:170-174` (existing exact-set assertion) and append two tests

**Interfaces:**
- Consumes: the completed `discovery_facebook` module from Tasks 1–4.
- Produces: `build_adapters()["facebook"] is discovery_facebook`.

**Note:** `tests/test_run_discovery_cron.py` already imports `run_discovery_cron as cron` at module level — use that alias rather than a function-local import.

- [ ] **Step 1: Update the existing exact-set test and write the new failing tests**

`test_build_adapters_includes_every_platform` asserts an **exact** key set, so it fails the moment a platform is added. Edit it in place at `tests/test_run_discovery_cron.py:170-174`:

```python
def test_build_adapters_includes_every_platform():
    adapters = cron.build_adapters()
    assert set(adapters.keys()) == {
        "youtube", "bluesky", "instagram", "linkedin-profile", "linkedin-company",
        "facebook",
    }
```

Then append two new tests to the same file:

```python
def test_build_adapters_registers_facebook_as_a_module():
    """One dataset serves both Pages and personal profiles, so unlike
    LinkedIn there is no per-mode instance to construct -- the module itself
    satisfies PlatformAdapter structurally, same as Instagram."""
    from pipeline_app import discovery_facebook

    assert cron.build_adapters()["facebook"] is discovery_facebook


def test_facebook_is_excluded_from_backfill():
    """No engine change is needed: BACKFILL_SUPPORTED_PLATFORMS is a
    whitelist, so facebook is rejected before any adapter call. Backfill IS
    possible for this product (start_date/end_date verified working
    2026-08-08) but needs a PlatformAdapter protocol change, deferred to its
    own spec."""
    from pipeline_app.discovery_engine import BACKFILL_SUPPORTED_PLATFORMS

    assert "facebook" not in BACKFILL_SUPPORTED_PLATFORMS
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd pipeline-app && python -m pytest tests/test_run_discovery_cron.py -v -k "build_adapters or facebook"
```

Expected: `test_build_adapters_includes_every_platform` FAILS on the set comparison (missing `'facebook'`), and `test_build_adapters_registers_facebook_as_a_module` FAILS with `KeyError: 'facebook'`. `test_facebook_is_excluded_from_backfill` passes already — it pins inherited behavior.

- [ ] **Step 3: Wire the platform in**

In `pipeline-app/run_discovery_cron.py`, change the import on line 23:

```python
from pipeline_app import (discovery_bluesky, discovery_facebook, discovery_instagram,
                          discovery_linkedin, discovery_youtube)
```

and add one entry to `build_adapters()`:

```python
def build_adapters():
    # LinkedIn's two modes are separate instances, not one shared object: each
    # keeps its own enumerate cache, and a person and a company can have the
    # same URL slug. Facebook needs no such split -- one dataset serves both
    # Pages and personal profiles.
    return {
        "youtube": discovery_youtube,
        "bluesky": discovery_bluesky,
        "instagram": discovery_instagram,
        "linkedin-profile": discovery_linkedin.profile_adapter(),
        "linkedin-company": discovery_linkedin.company_adapter(),
        "facebook": discovery_facebook,
    }
```

In `pipeline-app/pipeline_app/templates/discovery_handles.html`, add one `<option>` after the LinkedIn entries and update the placeholder:

```html
    <option value="linkedin-company">LinkedIn — company posts</option>
    <option value="facebook">Facebook — page or profile posts</option>
  </select>
  <input name="handle" placeholder="@handle, actor.bsky.social, linkedin slug, or facebook slug/id" required>
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd pipeline-app && python -m pytest tests/test_run_discovery_cron.py -v
```

Expected: PASS.

- [ ] **Step 5: Run the full regression gate**

`brightdata_job.py` and `discovery_engine.py` were not modified, so every sibling suite must still be green.

```bash
cd pipeline-app && python -m pytest tests/ -q
```

Expected: PASS, with no failures in `test_discovery_instagram.py`, `test_discovery_linkedin.py`, `test_brightdata_job.py`, or `test_discovery_engine.py`.

- [ ] **Step 6: Verify the adapter satisfies the protocol in practice**

```bash
cd pipeline-app && python -c "from pipeline_app import discovery_facebook as f; [print(n, callable(getattr(f, n))) for n in ('on_disk_ids','enumerate_newest_first','peek_upload_date','download_item')]"
```

Expected: all four print `True`.

- [ ] **Step 7: Commit**

```bash
git add pipeline-app/run_discovery_cron.py pipeline-app/pipeline_app/templates/discovery_handles.html pipeline-app/tests/test_run_discovery_cron.py
git commit -m "feat(discovery): register the facebook platform"
```

---

## Post-implementation: first live run

Not a task — an operator step, after the plan is complete and merged.

1. **Clear the DNS path.** Bright Data's domains are blocked by DNS-filtering resolvers that categorize proxy/scraping infrastructure — on this machine, Proton VPN's NetShield. Verify with `Resolve-DnsName api.brightdata.com`; every job fails at name resolution before any HTTP call if it is blocked.
2. Register one handle through the UI and let `validate_handle` run.
3. Confirm a `.md` file lands in `output/brand-intel/facebook/<handle>/` with the frontmatter shape from the spec.
4. **Check `date_posted` in the raw response has not changed format.** The whole adapter rests on it being ISO 8601 UTC; if Bright Data switches to the US-format shape its Instagram product uses, every row drops and the engine reports the healthy `no_new_content` for a batch already paid for. That is the exact bug that shipped in the first Instagram adapter.
