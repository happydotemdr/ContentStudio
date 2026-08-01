# Discovery Email Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After each scheduled discovery run that actually executes, send one plain-text email
summarizing which channels posted new content and each new YouTube video's title — nothing else.

**Architecture:** A new, engine-independent module (`pipeline_app/discovery_notify.py`) reads what
`discovery_engine.py` already persisted (DB rows + files on disk) after `run_discovery()` returns,
builds a summary dict, renders it to a subject/body, and POSTs it to Resend's HTTP API. It is wired
into `run_discovery_cron.py` behind a broad `try/except` so a notification bug can never affect the
recorded run status or the cron process's exit code.

**Tech Stack:** Python 3.14, `requests` (already a dependency, no new package), `pyyaml` (already a
dependency, via `pipeline_app.artifacts.parse_frontmatter`), `sqlite3`, `zoneinfo`, `pytest` +
`pytest`'s `monkeypatch` fixture.

## Global Constraints

- No changes to `pipeline_app/discovery_engine.py` — notification reads only already-persisted
  state (DB rows via `pipeline_app/db.py`, files via `pipeline_app/discovery_paths.py` +
  `pipeline_app/artifacts.py`).
- Only `trigger='scheduled'` runs that are not `status='locked'` send an email — never manual
  incremental, never backfill, never validate_handle.
- Headlines (per-video titles) are YouTube-only. Bluesky handles appear by name + post count, no
  per-post headline (Bluesky's on-disk files have no frontmatter and no real title).
- Email body is plain text only — no HTML part.
- A failure anywhere in the notification path is logged to stderr and swallowed — it must never
  raise out of `run_discovery_cron.py`'s `main()`, must never change `discovery_runs.status`
  (already persisted before notification runs), and must never change the cron process's exit code.
- Credentials follow the existing `YOUTUBE_API_KEY` pattern exactly: an environment variable
  (`RESEND_API_KEY`) checked first, falling back to a gitignored file
  (`pipeline-app/resend_api_key.txt`).
- Tests never make real network calls — `requests.post` is monkeypatched in every test that would
  otherwise reach it, and `RESEND_API_KEY` is explicitly unset (`monkeypatch.delenv`) in every test
  where its ambient presence in a developer's shell would change behavior.
- Run `pipeline-app/.venv/Scripts/python.exe -m pytest tests/ -q` from `pipeline-app/` after every
  task; all existing tests plus new ones must pass.

---

## File Structure

- **Create** `pipeline-app/pipeline_app/discovery_notify.py` — the whole feature: credential lookup,
  `build_summary`, `render_email`, `send_email`, `notify`. Kept as one file (not split further)
  because the four functions are small, share no state beyond simple parameters, and splitting them
  across files would force three intermodule imports for ~150 lines of code — following this
  project's existing pattern where `discovery_youtube_api.py` similarly bundles credential lookup +
  one HTTP concern into a single small module.
- **Create** `pipeline-app/tests/test_discovery_notify.py` — unit tests for all four functions.
- **Modify** `pipeline-app/run_discovery_cron.py` — import `discovery_notify`, call
  `discovery_notify.notify(...)` after a due, non-locked scheduled run.
- **Modify** `pipeline-app/tests/test_run_discovery_cron.py` — add tests asserting when `notify` is
  and isn't called.
- **Modify** `.gitignore` (repo root) — add `pipeline-app/resend_api_key.txt`.
- **Modify** `CLAUDE.md` (repo root) — add the "local only" exception paragraph under Conventions.

---

## Task 1: Credential lookup + `send_email`

**Files:**
- Create: `pipeline-app/pipeline_app/discovery_notify.py`
- Test: `pipeline-app/tests/test_discovery_notify.py`

**Interfaces:**
- Produces: `api_key() -> str | None`; `send_email(subject: str, text: str) -> bool`; module
  constants `RESEND_API_URL = "https://api.resend.com/emails"`,
  `KEY_ENV_VAR = "RESEND_API_KEY"`,
  `KEY_FILE = Path(__file__).resolve().parent.parent / "resend_api_key.txt"`,
  `RECIPIENT = "brian@happydotemdr.com"`,
  `SENDER = os.environ.get("RESEND_FROM_ADDRESS", "onboarding@resend.dev")` — Resend's shared
  sandbox sender that works out of the box for accounts with no verified domain yet; once a domain
  is verified, setting `RESEND_FROM_ADDRESS` in the environment switches the sender with no code
  change.

- [ ] **Step 1: Write the failing tests for `api_key()` and `send_email()`**

```python
# pipeline-app/tests/test_discovery_notify.py
from pathlib import Path

import pytest

from pipeline_app import discovery_notify


@pytest.fixture(autouse=True)
def _clean_credential_env(monkeypatch):
    # Every test starts with no ambient credential, matching the "tests never
    # depend on the developer's real environment" constraint.
    monkeypatch.delenv(discovery_notify.KEY_ENV_VAR, raising=False)


def test_api_key_reads_env_var_first(monkeypatch):
    monkeypatch.setenv(discovery_notify.KEY_ENV_VAR, "env-key-123")
    assert discovery_notify.api_key() == "env-key-123"


def test_api_key_falls_back_to_file(monkeypatch, tmp_path):
    key_file = tmp_path / "resend_api_key.txt"
    key_file.write_text("file-key-456\n", encoding="utf-8")
    monkeypatch.setattr(discovery_notify, "KEY_FILE", key_file)
    assert discovery_notify.api_key() == "file-key-456"


def test_api_key_returns_none_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.setattr(discovery_notify, "KEY_FILE", tmp_path / "missing.txt")
    assert discovery_notify.api_key() is None


def test_send_email_returns_false_without_key(monkeypatch, tmp_path):
    monkeypatch.setattr(discovery_notify, "KEY_FILE", tmp_path / "missing.txt")
    calls = []
    monkeypatch.setattr(discovery_notify.requests, "post", lambda *a, **k: calls.append((a, k)))
    assert discovery_notify.send_email("subject", "body") is False
    assert calls == []  # no request attempted at all


def test_send_email_posts_expected_payload(monkeypatch):
    monkeypatch.setenv(discovery_notify.KEY_ENV_VAR, "test-key")
    captured = {}

    class FakeResponse:
        status_code = 200
        def raise_for_status(self):
            pass

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(discovery_notify.requests, "post", fake_post)
    result = discovery_notify.send_email("Test Subject", "Test body text")

    assert result is True
    assert captured["url"] == discovery_notify.RESEND_API_URL
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["to"] == [discovery_notify.RECIPIENT]
    assert captured["json"]["from"] == discovery_notify.SENDER
    assert captured["json"]["subject"] == "Test Subject"
    assert captured["json"]["text"] == "Test body text"
    assert captured["timeout"] == 15


def test_send_email_catches_request_exception(monkeypatch):
    monkeypatch.setenv(discovery_notify.KEY_ENV_VAR, "test-key")

    def raising_post(*a, **k):
        raise discovery_notify.requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr(discovery_notify.requests, "post", raising_post)
    assert discovery_notify.send_email("subject", "body") is False


def test_send_email_catches_timeout(monkeypatch):
    monkeypatch.setenv(discovery_notify.KEY_ENV_VAR, "test-key")

    def timing_out_post(*a, **k):
        raise discovery_notify.requests.exceptions.Timeout("too slow")

    monkeypatch.setattr(discovery_notify.requests, "post", timing_out_post)
    assert discovery_notify.send_email("subject", "body") is False


def test_send_email_catches_non_2xx_response(monkeypatch):
    monkeypatch.setenv(discovery_notify.KEY_ENV_VAR, "test-key")

    class FailingResponse:
        status_code = 403
        def raise_for_status(self):
            raise discovery_notify.requests.exceptions.HTTPError("403 forbidden")

    monkeypatch.setattr(discovery_notify.requests, "post", lambda *a, **k: FailingResponse())
    assert discovery_notify.send_email("subject", "body") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `pipeline-app/`): `.venv/Scripts/python.exe -m pytest tests/test_discovery_notify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_app.discovery_notify'` (or
`ImportError`).

- [ ] **Step 3: Write `discovery_notify.py` with credential lookup and `send_email`**

```python
# pipeline-app/pipeline_app/discovery_notify.py
"""Post-run email notification for the discovery pipeline. Deliberately has
no dependency on discovery_engine.py -- it reads only what a finished run
already persisted (DB rows via db.py, files via discovery_paths.py /
artifacts.py) and is invoked by run_discovery_cron.py after run_discovery()
returns. See docs/superpowers/specs/2026-08-01-discovery-email-summary-design.md.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

RESEND_API_URL = "https://api.resend.com/emails"
KEY_ENV_VAR = "RESEND_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "resend_api_key.txt"

RECIPIENT = "brian@happydotemdr.com"
# Resend's shared sandbox sender -- works with no domain verification. Once a
# real sending domain is verified in the Resend dashboard, set
# RESEND_FROM_ADDRESS in the environment to switch senders with no code change.
SENDER = os.environ.get("RESEND_FROM_ADDRESS", "onboarding@resend.dev")

REQUEST_TIMEOUT_S = 15


def api_key() -> str | None:
    """The Resend API key, or None if not configured. Same lookup order as
    discovery_youtube_api.api_key(): env var first, then a gitignored file."""
    env_key = os.environ.get(KEY_ENV_VAR, "").strip()
    if env_key:
        return env_key
    if KEY_FILE.exists():
        file_key = KEY_FILE.read_text(encoding="utf-8").strip()
        if file_key:
            return file_key
    return None


def send_email(subject: str, text: str) -> bool:
    """POST one email via Resend's HTTP API. Never raises -- returns False on
    any failure (no key configured, network error, non-2xx response) so a
    caller can log and move on rather than letting a notification failure
    propagate as an exception."""
    key = api_key()
    if not key:
        print("discovery_notify: no RESEND_API_KEY configured, skipping send", file=sys.stderr)
        return False
    try:
        response = requests.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={"from": SENDER, "to": [RECIPIENT], "subject": subject, "text": text},
            timeout=REQUEST_TIMEOUT_S,
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as exc:
        print(f"discovery_notify: send_email failed: {exc}", file=sys.stderr)
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_discovery_notify.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_notify.py pipeline-app/tests/test_discovery_notify.py
git commit -m "feat(discovery): add Resend credential lookup and send_email"
```

---

## Task 2: `build_summary`

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_notify.py`
- Modify: `pipeline-app/tests/test_discovery_notify.py`

**Interfaces:**
- Consumes (from `pipeline_app/db.py`): `get_run(conn, run_row_id) -> sqlite3.Row | None` (columns
  include `status`, `started_at`); `list_run_handle_results(conn, run_row_id) -> list[sqlite3.Row]`
  (columns: `handle_id`, `status`, `items_downloaded`, `error_message`); `get_handle(conn, handle_id)
  -> sqlite3.Row | None` (columns: `platform`, `handle`, `display_name`).
- Consumes (from `pipeline_app/discovery_paths.py`): `handle_dir(repo_root, platform, handle) ->
  Path`.
- Consumes (from `pipeline_app/artifacts.py`): `parse_frontmatter(text: str) -> tuple[dict, str]`
  (returns `({}, text)` when the file has no `---` frontmatter block at all, as Bluesky's files do).
- Produces: `build_summary(conn, repo_root: Path, run_row_id: int) -> dict` shaped exactly as:

  ```python
  {
      "run_status": str,       # discovery_runs.status verbatim, e.g. "completed_with_errors"
      "has_issues": bool,      # run_status != "completed" or errored is non-empty
      "channels": [
          {"name": str, "headlines": list[str], "count": int},  # count == len(headlines) for
                                                                  # youtube; raw post count for bluesky
          ...
      ],
      "errored": list[str],    # display_name or handle, for every handle with status == "error"
  }
  ```

- [ ] **Step 1: Write the failing tests**

```python
# append to pipeline-app/tests/test_discovery_notify.py
import datetime as _dt

from pipeline_app import db


def _make_run(conn, started_at="2026-08-01T06:00:00+00:00", status="completed"):
    run_row_id = db.insert_terminal_run(
        conn, "2026-08-01T06-00-00-000000", "scheduled", "incremental", status,
        started_at, "2026-08-01T06:05:00+00:00",
    )
    return run_row_id


def _make_handle(conn, platform="youtube", handle="@somechannel", display_name="Some Channel"):
    return db.create_handle(conn, platform, handle, display_name, "guru", None, "2026-07-01T00:00:00+00:00")


def _write_youtube_video(repo_root, handle, video_id, title, fetched_at):
    from pipeline_app import discovery_paths
    out_dir = discovery_paths.handle_dir(repo_root, "youtube", handle)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = title.lower().replace(" ", "-")
    text = (
        "---\n"
        f"video_id: {video_id}\n"
        f"handle: {handle}\n"
        f"fetched_at: '{fetched_at}'\n"
        "---\n\n"
        f"# {title}\n\n"
        "## description\n\n(none)\n"
    )
    (out_dir / f"{video_id}__{slug}.md").write_text(text, encoding="utf-8")


@pytest.fixture
def notify_db(tmp_path):
    db_path = tmp_path / "pipeline-app" / "pipeline.db"
    db_path.parent.mkdir(parents=True)
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    conn = db.get_connection(db_path)
    yield conn, tmp_path
    conn.close()


def test_build_summary_includes_headlines_within_watermark(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = _make_handle(conn)
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 2)
    _write_youtube_video(repo_root, "@somechannel", "vid1", "First New Video", "2026-08-01T06:01:00+00:00")
    _write_youtube_video(repo_root, "@somechannel", "vid2", "Second New Video", "2026-08-01T06:02:00+00:00")
    # Left over from a prior run's same handle -- must be excluded by the watermark.
    _write_youtube_video(repo_root, "@somechannel", "vid0", "Old Video From Yesterday", "2026-07-31T06:01:00+00:00")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert summary["run_status"] == "completed"
    assert summary["has_issues"] is False
    assert len(summary["channels"]) == 1
    channel = summary["channels"][0]
    assert channel["name"] == "Some Channel"
    assert channel["count"] == 2
    assert set(channel["headlines"]) == {"First New Video", "Second New Video"}
    assert summary["errored"] == []


def test_build_summary_excludes_file_with_no_fetched_at(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn)
    handle_id = _make_handle(conn)
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_youtube_video(repo_root, "@somechannel", "vid1", "Good Video", "2026-08-01T06:01:00+00:00")
    # A malformed file with no frontmatter at all -- must be silently excluded, not crash the run.
    from pipeline_app import discovery_paths
    out_dir = discovery_paths.handle_dir(repo_root, "youtube", "@somechannel")
    (out_dir / "vid2__broken.md").write_text("no frontmatter here", encoding="utf-8")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    headlines = summary["channels"][0]["headlines"]
    assert headlines == ["Good Video"]


def test_build_summary_bluesky_handle_has_no_headlines_but_has_count(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn)
    handle_id = _make_handle(conn, platform="bluesky", handle="did:plc:abc", display_name="A Bluesky Handle")
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 3)

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    channel = summary["channels"][0]
    assert channel["name"] == "A Bluesky Handle"
    assert channel["headlines"] == []
    assert channel["count"] == 3


def test_build_summary_omits_channels_with_zero_new_items(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn)
    handle_id = _make_handle(conn)
    db.record_handle_result(conn, run_row_id, handle_id, "no_new_content", 0)

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert summary["channels"] == []


def test_build_summary_collects_errored_handles_with_display_name_fallback(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, status="completed_with_errors")
    handle_id = db.create_handle(conn, "youtube", "@dead-handle", None, "guru", None, "2026-07-01T00:00:00+00:00")
    db.record_handle_result(conn, run_row_id, handle_id, "error", 0, "enumerate returned no results")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert summary["has_issues"] is True
    assert summary["errored"] == ["@dead-handle"]  # display_name is None -> falls back to handle


def test_build_summary_warns_on_count_mismatch_but_does_not_raise(notify_db, capsys):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn)
    handle_id = _make_handle(conn)
    # DB says 2 items downloaded but only 1 file actually matches the watermark.
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 2)
    _write_youtube_video(repo_root, "@somechannel", "vid1", "Only One Video", "2026-08-01T06:01:00+00:00")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert summary["channels"][0]["headlines"] == ["Only One Video"]
    assert "mismatch" in capsys.readouterr().err.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_discovery_notify.py -v`
Expected: FAIL — `AttributeError: module 'pipeline_app.discovery_notify' has no attribute
'build_summary'`.

- [ ] **Step 3: Implement `build_summary`**

```python
# add to pipeline-app/pipeline_app/discovery_notify.py

from pipeline_app import db as db_mod
from pipeline_app import discovery_paths
from pipeline_app import artifacts


def _youtube_headlines_for_handle(repo_root, platform_handle: str, started_at: str) -> list[str]:
    directory = discovery_paths.handle_dir(repo_root, "youtube", platform_handle)
    if not directory.exists():
        return []
    headlines = []
    for path in sorted(directory.glob("*__*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = artifacts.parse_frontmatter(text)
        fetched_at = meta.get("fetched_at")
        if not fetched_at or fetched_at < started_at:
            continue
        first_line = next((line for line in body.splitlines() if line.strip()), "")
        title = first_line.lstrip("#").strip() if first_line.startswith("#") else None
        if title:
            headlines.append(title)
    return headlines


def build_summary(conn, repo_root: Path, run_row_id: int) -> dict:
    run_row = db_mod.get_run(conn, run_row_id)
    handle_results = db_mod.list_run_handle_results(conn, run_row_id)

    channels = []
    errored = []
    for result in handle_results:
        handle_row = db_mod.get_handle(conn, result["handle_id"])
        label = handle_row["display_name"] or handle_row["handle"]

        if result["status"] == "error":
            errored.append(label)
            continue

        if result["items_downloaded"] <= 0:
            continue

        if handle_row["platform"] == "youtube":
            headlines = _youtube_headlines_for_handle(repo_root, handle_row["handle"], run_row["started_at"])
            if len(headlines) != result["items_downloaded"]:
                print(
                    f"discovery_notify: headline count mismatch for {label}: "
                    f"db says {result['items_downloaded']}, found {len(headlines)} on disk",
                    file=sys.stderr,
                )
            channels.append({"name": label, "headlines": headlines, "count": len(headlines)})
        else:
            channels.append({"name": label, "headlines": [], "count": result["items_downloaded"]})

    has_issues = run_row["status"] != "completed" or bool(errored)
    return {
        "run_status": run_row["status"],
        "has_issues": has_issues,
        "channels": channels,
        "errored": errored,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_discovery_notify.py -v`
Expected: PASS (14 tests total)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_notify.py pipeline-app/tests/test_discovery_notify.py
git commit -m "feat(discovery): add build_summary with YouTube watermark headline selection"
```

---

## Task 3: `render_email`

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_notify.py`
- Modify: `pipeline-app/tests/test_discovery_notify.py`

**Interfaces:**
- Consumes: a `summary` dict shaped exactly as `build_summary`'s return value (Task 2); a
  `run_date: str` in `YYYY-MM-DD` form.
- Produces: `render_email(summary: dict, run_date: str) -> dict` returning
  `{"subject": str, "text": str}`.

- [ ] **Step 1: Write the failing tests**

```python
# append to pipeline-app/tests/test_discovery_notify.py

def test_render_email_no_new_content():
    summary = {"run_status": "completed", "has_issues": False, "channels": [], "errored": []}
    result = discovery_notify.render_email(summary, "2026-08-01")
    assert result["subject"] == "ContentStudio Discovery 2026-08-01: 0 new video(s)"
    assert result["text"] == "No new content today."


def test_render_email_with_headlines_and_bluesky_count():
    summary = {
        "run_status": "completed",
        "has_issues": False,
        "channels": [
            {"name": "Some Channel", "headlines": ["Video One", "Video Two"], "count": 2},
            {"name": "A Bluesky Handle", "headlines": [], "count": 3},
        ],
        "errored": [],
    }
    result = discovery_notify.render_email(summary, "2026-08-01")
    assert result["subject"] == "ContentStudio Discovery 2026-08-01: 5 new video(s)"
    assert "Some Channel" in result["text"]
    assert "- Video One" in result["text"]
    assert "- Video Two" in result["text"]
    assert "A Bluesky Handle" in result["text"]
    assert "3 new post(s)" in result["text"]


def test_render_email_issue_prefixes_subject_and_lists_errors():
    summary = {
        "run_status": "completed_with_errors",
        "has_issues": True,
        "channels": [],
        "errored": ["@dead-handle"],
    }
    result = discovery_notify.render_email(summary, "2026-08-01")
    assert result["subject"].startswith("[ISSUE] ")
    assert "Run status: completed_with_errors" in result["text"]
    assert "Errors:" in result["text"]
    assert "@dead-handle" in result["text"]


def test_render_email_failed_run_states_status_even_with_empty_body():
    # A failed run with no handle results at all must never silently render
    # as "No new content today." under an [ISSUE] subject.
    summary = {"run_status": "failed", "has_issues": True, "channels": [], "errored": []}
    result = discovery_notify.render_email(summary, "2026-08-01")
    assert result["subject"].startswith("[ISSUE] ")
    assert "Run status: failed" in result["text"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_discovery_notify.py -v`
Expected: FAIL — `AttributeError: ... has no attribute 'render_email'`.

- [ ] **Step 3: Implement `render_email`**

```python
# add to pipeline-app/pipeline_app/discovery_notify.py

def render_email(summary: dict, run_date: str) -> dict:
    total = sum(c["count"] for c in summary["channels"])
    subject = f"ContentStudio Discovery {run_date}: {total} new video(s)"
    if summary["has_issues"]:
        subject = f"[ISSUE] {subject}"

    lines: list[str] = []
    if summary["has_issues"]:
        lines.append(f"Run status: {summary['run_status']}")
        lines.append("")

    for channel in summary["channels"]:
        lines.append(channel["name"])
        if channel["headlines"]:
            for headline in channel["headlines"]:
                lines.append(f"- {headline}")
        else:
            lines.append(f"- {channel['count']} new post(s)")
        lines.append("")

    if summary["errored"]:
        lines.append("Errors:")
        for name in summary["errored"]:
            lines.append(f"- {name}")
        lines.append("")

    if not summary["channels"] and not summary["errored"]:
        if summary["has_issues"]:
            text = "\n".join(lines).rstrip() + "\n"
        else:
            text = "No new content today."
    else:
        text = "\n".join(lines).rstrip() + "\n"

    return {"subject": subject, "text": text}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_discovery_notify.py -v`
Expected: PASS (18 tests total)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_notify.py pipeline-app/tests/test_discovery_notify.py
git commit -m "feat(discovery): add render_email"
```

---

## Task 4: `notify` orchestrator

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_notify.py`
- Modify: `pipeline-app/tests/test_discovery_notify.py`

**Interfaces:**
- Consumes: `build_summary`, `render_email`, `send_email` (Tasks 1–3); `db.get_run(conn,
  run_row_id)`; `db.get_settings(conn) -> sqlite3.Row` (column `timezone`, e.g.
  `"America/Chicago"`).
- Produces: `notify(conn, repo_root: Path, run_row_id: int) -> bool` — the single function
  `run_discovery_cron.py` (Task 5) calls.

- [ ] **Step 1: Write the failing tests**

```python
# append to pipeline-app/tests/test_discovery_notify.py

def test_notify_orchestrates_build_render_send(monkeypatch, notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T11:00:00+00:00")  # 06:00 America/Chicago (UTC-5)

    calls = {}
    monkeypatch.setattr(discovery_notify, "build_summary",
                         lambda c, r, rid: calls.setdefault("build_args", (c, r, rid)) or {"fake": "summary"})
    monkeypatch.setattr(discovery_notify, "render_email",
                         lambda summary, run_date: calls.setdefault("render_args", (summary, run_date)) or
                         {"subject": "s", "text": "t"})
    monkeypatch.setattr(discovery_notify, "send_email",
                         lambda subject, text: calls.setdefault("send_args", (subject, text)) or True)

    result = discovery_notify.notify(conn, repo_root, run_row_id)

    assert result is True
    assert calls["build_args"] == (conn, repo_root, run_row_id)
    assert calls["render_args"] == ({"fake": "summary"}, "2026-08-01")
    assert calls["send_args"] == ("s", "t")


def test_notify_never_raises_when_build_summary_fails(monkeypatch, notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn)
    monkeypatch.setattr(discovery_notify, "build_summary", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    # notify() itself doesn't need to catch (the cron call site does, per Task 5),
    # but build_summary/render_email/send_email must be the only things that can raise --
    # this test documents that notify() doesn't add its own extra failure mode.
    with pytest.raises(RuntimeError):
        discovery_notify.notify(conn, repo_root, run_row_id)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_discovery_notify.py -v`
Expected: FAIL — `AttributeError: ... has no attribute 'notify'`.

- [ ] **Step 3: Implement `notify`**

```python
# add to pipeline-app/pipeline_app/discovery_notify.py

from zoneinfo import ZoneInfo


def notify(conn, repo_root: Path, run_row_id: int) -> bool:
    summary = build_summary(conn, repo_root, run_row_id)
    run_row = db_mod.get_run(conn, run_row_id)
    timezone_name = db_mod.get_settings(conn)["timezone"]
    started_at = _dt.datetime.fromisoformat(run_row["started_at"])
    run_date = started_at.astimezone(ZoneInfo(timezone_name)).date().isoformat()
    rendered = render_email(summary, run_date)
    return send_email(rendered["subject"], rendered["text"])
```

Add `import datetime as _dt` to the module's imports at the top (alongside the existing `os`,
`sys`, `Path`, `requests` imports from Task 1).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_discovery_notify.py -v`
Expected: PASS (20 tests total)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_notify.py pipeline-app/tests/test_discovery_notify.py
git commit -m "feat(discovery): add notify orchestrator"
```

---

## Task 5: Wire `notify` into `run_discovery_cron.py`

**Files:**
- Modify: `pipeline-app/run_discovery_cron.py`
- Modify: `pipeline-app/tests/test_run_discovery_cron.py`

**Interfaces:**
- Consumes: `discovery_notify.notify(conn, repo_root, run_row_id) -> bool` (Task 4).

- [ ] **Step 1: Write the failing tests**

```python
# append to pipeline-app/tests/test_run_discovery_cron.py

def test_scheduled_due_run_calls_notify(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda repo_root_arg: True)
    monkeypatch.setattr(cron, "run_discovery",
                         lambda *a, **k: {"run_row_id": 1, "status": "completed"})
    calls = []
    monkeypatch.setattr(cron, "notify", lambda conn, repo_root_arg, run_row_id: calls.append(run_row_id) or True)

    exit_code = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])

    assert exit_code == 0
    assert calls == [1]


def test_scheduled_locked_run_does_not_call_notify(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda repo_root_arg: True)
    monkeypatch.setattr(cron, "run_discovery",
                         lambda *a, **k: {"run_row_id": 2, "status": "locked"})
    calls = []
    monkeypatch.setattr(cron, "notify", lambda *a, **k: calls.append(1) or True)

    exit_code = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])

    assert exit_code == 0
    assert calls == []


def test_scheduled_not_due_does_not_call_notify(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda repo_root_arg: False)
    calls = []
    monkeypatch.setattr(cron, "notify", lambda *a, **k: calls.append(1) or True)

    exit_code = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])

    assert exit_code == 0
    assert calls == []


def test_incremental_mode_does_not_call_notify(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "run_discovery",
                         lambda *a, **k: {"run_row_id": 3, "status": "completed"})
    calls = []
    monkeypatch.setattr(cron, "notify", lambda *a, **k: calls.append(1) or True)

    exit_code = cron.main(["--mode", "incremental", "--repo-root", str(repo_root)])

    assert exit_code == 0
    assert calls == []


def test_backfill_mode_does_not_call_notify(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "run_discovery",
                         lambda *a, **k: {"run_row_id": 4, "status": "completed"})
    calls = []
    monkeypatch.setattr(cron, "notify", lambda *a, **k: calls.append(1) or True)

    exit_code = cron.main([
        "--mode", "backfill", "--backfill-start", "2026-06-01", "--backfill-end", "2026-06-30",
        "--repo-root", str(repo_root),
    ])

    assert exit_code == 0
    assert calls == []


def test_notify_exception_does_not_propagate_or_change_exit_code(monkeypatch, repo_root, capsys):
    monkeypatch.setattr(cron, "_is_due_now", lambda repo_root_arg: True)
    monkeypatch.setattr(cron, "run_discovery",
                         lambda *a, **k: {"run_row_id": 5, "status": "completed"})

    def raising_notify(*a, **k):
        raise RuntimeError("resend is down")

    monkeypatch.setattr(cron, "notify", raising_notify)

    exit_code = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])

    assert exit_code == 0
    assert "discovery notification failed" in capsys.readouterr().err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_run_discovery_cron.py -v`
Expected: FAIL — `AttributeError: module 'run_discovery_cron' has no attribute 'notify'` (or
`AssertionError` on the "not called" tests, since `notify` doesn't exist yet to be called at all).

- [ ] **Step 3: Modify `run_discovery_cron.py`**

Add `import sys` to the top-level imports, and `from pipeline_app.discovery_notify import notify`
alongside the existing `from pipeline_app.discovery_engine import run_discovery` import. Then, in
`main()`, immediately after the existing block:

```python
        result = run_discovery(
            conn, repo_root, build_adapters(), trigger=trigger, mode=mode,
            backfill_start=args.backfill_start, backfill_end=args.backfill_end,
            handle_id=args.handle_id,
        )
        print(f"run {result['run_row_id']}: {result['status']}")
```

add:

```python
        if args.mode == "scheduled" and result["status"] != "locked":
            try:
                notify(conn, repo_root, result["run_row_id"])
            except Exception as exc:  # noqa: BLE001 - notification must never affect run status/exit code
                print(f"discovery notification failed: {exc}", file=sys.stderr)
```

(both inserted before the existing `finally: conn.close()`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_run_discovery_cron.py -v`
Expected: PASS (all tests, including the 5 pre-existing ones and the 6 new ones)

Then run the full suite to confirm nothing else broke:

Run (from `pipeline-app/`): `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all tests pass (previous count + 26 new tests across Tasks 1–5).

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/run_discovery_cron.py pipeline-app/tests/test_run_discovery_cron.py
git commit -m "feat(discovery): send email summary after scheduled discovery runs"
```

---

## Task 6: Credential file ignore rule + CLAUDE.md exception paragraph

**Files:**
- Modify: `.gitignore` (repo root)
- Modify: `CLAUDE.md` (repo root)

**Interfaces:** None — documentation/config only, no code.

- [ ] **Step 1: Add the credential file to `.gitignore`**

In the repo-root `.gitignore`, find the existing block:

```
# YouTube Data API key (never commit)
pipeline-app/youtube_api_key.txt
```

and add directly beneath it:

```
# Resend API key for discovery email notifications (never commit)
pipeline-app/resend_api_key.txt
```

- [ ] **Step 2: Verify the ignore rule works**

```bash
touch pipeline-app/resend_api_key.txt
git status --porcelain pipeline-app/resend_api_key.txt
```

Expected: no output (the file does not appear as untracked). Then remove the test file:

```bash
rm pipeline-app/resend_api_key.txt
```

- [ ] **Step 3: Add the CLAUDE.md exception paragraph**

In the repo-root `CLAUDE.md`, find the `## Conventions` section's first bullet:

```markdown
- Local only. No deploying, no external hosting, no cloud sync.
```

and add a new bullet directly after it:

```markdown
- **Exception to "local only":** outbound notification email
  (`pipeline-app/pipeline_app/discovery_notify.py`, via Resend's HTTP API) sends channel names and
  video titles for each day's scheduled discovery run, and nothing else — never transcripts,
  descriptions, or any other corpus content. This is the one deliberate outbound network dependency
  in the project; see `docs/superpowers/specs/2026-08-01-discovery-email-summary-design.md` for the
  full rationale.
```

- [ ] **Step 4: Verify the docs render sensibly**

```bash
git diff .gitignore CLAUDE.md
```

Expected: a clean two-line addition to `.gitignore` and a clean one-bullet addition to `CLAUDE.md`,
no other changes.

- [ ] **Step 5: Commit**

```bash
git add .gitignore CLAUDE.md
git commit -m "docs: record local-only exception for discovery email notifications"
```

---

## Task 7: Manual end-to-end smoke check (no code changes)

**Files:** None modified — verification only.

**Interfaces:** None.

This task exists because every prior task tests `discovery_notify` and `run_discovery_cron` in
isolation with mocks; nothing so far has proven the pieces actually fit together against a real
SQLite DB and real files, nor exercised the credential-missing path end-to-end the way it will
actually run in production (no `RESEND_API_KEY` yet, since the Resend account doesn't exist until
the user sets it up per the spec's "Setup" section).

- [ ] **Step 1: Run the full test suite one more time from a clean state**

```bash
cd pipeline-app
.venv/Scripts/python.exe -m pytest tests/ -q
```

Expected: all tests pass, 0 failures, 0 errors.

- [ ] **Step 2: Exercise `notify()` against a real (throwaway) SQLite DB with no credential configured**

```bash
cd pipeline-app
.venv/Scripts/python.exe -c "
import tempfile, datetime, sys
from pathlib import Path
sys.path.insert(0, '.')
from pipeline_app import db, discovery_notify

tmp = Path(tempfile.mkdtemp())
db_path = tmp / 'pipeline-app' / 'pipeline.db'
db_path.parent.mkdir(parents=True)
db.init_db(db_path, Path('pipeline_app/schema.sql'))
conn = db.get_connection(db_path)

run_row_id = db.insert_terminal_run(
    conn, '2026-08-01T06-00-00-000000', 'scheduled', 'incremental', 'completed',
    '2026-08-01T11:00:00+00:00', '2026-08-01T11:05:00+00:00',
)
handle_id = db.create_handle(conn, 'youtube', '@smoketest', 'Smoke Test Channel', 'guru', None, '2026-07-01T00:00:00+00:00')
db.record_handle_result(conn, run_row_id, handle_id, 'ok', 1)

from pipeline_app import discovery_paths
out_dir = discovery_paths.handle_dir(tmp, 'youtube', '@smoketest')
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / 'vid1__smoke-test-video.md').write_text(
    '---\nvideo_id: vid1\nfetched_at: \'2026-08-01T11:01:00+00:00\'\n---\n\n# Smoke Test Video\n',
    encoding='utf-8',
)

result = discovery_notify.notify(conn, tmp, run_row_id)
print('notify() returned:', result)
conn.close()
"
```

Expected output ends with `notify() returned: False` (no `RESEND_API_KEY` set in this shell), and a
line on stderr reading `discovery_notify: no RESEND_API_KEY configured, skipping send` — confirming
the whole pipeline (DB read → file scan → headline extraction → render → the credential-missing
short-circuit in `send_email`) runs cleanly end-to-end without crashing, exactly as it will on a
machine before the Resend account is set up.

- [ ] **Step 3: Confirm no test step or smoke check left stray files in the repo**

```bash
git status --porcelain
```

Expected: no output (the smoke check ran entirely inside a temp directory; nothing here touches the
real repo tree).

No commit for this task — it's verification only, with nothing to check in.
