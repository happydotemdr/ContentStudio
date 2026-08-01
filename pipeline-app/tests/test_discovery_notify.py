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
        f"handle: '{handle}'\n"
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


def test_build_summary_excludes_file_with_invalid_yaml_frontmatter(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn)
    handle_id = _make_handle(conn)
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_youtube_video(repo_root, "@somechannel", "vid1", "Good Video", "2026-08-01T06:01:00+00:00")
    # A file with a --- delimited block but genuinely invalid YAML inside it (unquoted value
    # starting with a reserved indicator character) -- parse_frontmatter's yaml.safe_load call
    # raises for this; build_summary must catch it and drop just this file, not crash the run.
    from pipeline_app import discovery_paths
    out_dir = discovery_paths.handle_dir(repo_root, "youtube", "@somechannel")
    bad_text = (
        "---\n"
        "video_id: vid2\n"
        "fetched_at: @not-quoted-and-invalid\n"
        "---\n\n"
        "# Broken Video\n"
    )
    (out_dir / "vid2__broken-yaml.md").write_text(bad_text, encoding="utf-8")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert summary["channels"][0]["headlines"] == ["Good Video"]


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
