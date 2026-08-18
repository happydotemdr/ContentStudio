from pathlib import Path

import pytest

from pipeline_app import discovery_notify
from pipeline_app import email_render


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


def _fake_overall(**over):
    """A build_summary()-shaped dict, for tests that mock build_summary.

    Carries every key email_render.render_brand_digest requires, so a fake can
    never drift into a shape the real renderer would reject (T14's guard).
    """
    summary = {"run_status": "completed", "has_issues": False, "items": [],
               "errored": [], "errors": [], "skips": [], "warnings": [],
               "duplicates": [], "mismatches": [],
               "coverage": {"scanned": 0, "with_items": 0, "quiet": 0,
                            "errored": 0, "other": {}}}
    summary.update(over)
    return summary


def _make_run(conn, started_at="2026-08-01T06:00:00+00:00", status="completed",
              run_id="2026-08-01T06-00-00-000000"):
    # run_id is a parameter because discovery_runs.run_id is UNIQUE and a test
    # that inserts two runs into one DB (the T15 pair test) needs two ids.
    run_row_id = db.insert_terminal_run(
        conn, run_id, "scheduled", "incremental", status,
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


def test_notify_orchestrates_build_render_send(monkeypatch, notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T11:00:00+00:00")  # 06:00 America/Chicago (UTC-5)

    calls = {}
    monkeypatch.setattr(discovery_notify, "build_summary",
                         lambda c, r, rid: (calls.setdefault("build_args", (c, r, rid)),
                                             _fake_overall())[1])
    monkeypatch.setattr(discovery_notify.discovery_digest, "select_spotlight_with_rule",
                         lambda items: (None, None))
    monkeypatch.setattr(discovery_notify.email_render, "render_brand_digest",
                         lambda overall, sections, run_date:
                             (calls.setdefault("render_args", (overall, sections, run_date)),
                              {"subject": "s", "text": "t", "html": "h"})[1])
    monkeypatch.setattr(discovery_notify, "send_email",
                         lambda subject, text, html: (calls.setdefault("send_args", (subject, text, html)), True)[1])

    result = discovery_notify.notify(conn, repo_root, run_row_id)

    assert result is True
    assert calls["build_args"] == (conn, repo_root, run_row_id)
    overall, sections, run_date = calls["render_args"]
    assert overall == _fake_overall()
    assert set(sections) == {"freedom2beu", "raisinggoodsports", "guru"}
    # Run-level facts stay on `overall` only -- a section that carried them
    # would have them rendered once per brand (B-95b).
    for section in sections.values():
        assert not set(section) & {"coverage", "skips", "warnings", "duplicates", "mismatches"}
    assert run_date == "2026-08-01"
    assert calls["send_args"] == ("s", "t", "h")


def test_notify_end_to_end_uses_real_build_summary_and_render_email(monkeypatch, notify_db):
    # Locks the real contract between build_summary and render_email by exercising notify()
    # against the real DB/filesystem fixture, mocking only send_email.
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = _make_handle(conn)
    db.set_handle_brands(conn, handle_id, ["guru"])
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_youtube_video(repo_root, "@somechannel", "vid1", "Real Contract Video", "2026-08-01T06:01:00+00:00")

    captured = {}
    monkeypatch.setattr(
        discovery_notify, "send_email",
        lambda subject, text, html: (captured.setdefault("subject", subject), captured.setdefault("text", text), True)[-1],
    )

    result = discovery_notify.notify(conn, repo_root, run_row_id)

    assert result is True
    assert "Some Channel" in captured["text"]
    assert "Real Contract Video" in captured["text"]


def test_notify_never_raises_when_build_summary_fails(monkeypatch, notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn)
    monkeypatch.setattr(discovery_notify, "build_summary", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    # notify() itself doesn't need to catch (the cron call site does, per Task 5),
    # but build_summary/render_email/send_email must be the only things that can raise --
    # this test documents that notify() doesn't add its own extra failure mode.
    with pytest.raises(RuntimeError):
        discovery_notify.notify(conn, repo_root, run_row_id)


def _write_post(repo_root, platform, handle, name, meta_lines, body):
    from pipeline_app import discovery_paths
    out = discovery_paths.handle_dir(repo_root, platform, handle)
    out.mkdir(parents=True, exist_ok=True)
    (out / name).write_text("---\n" + "\n".join(meta_lines) + "\n---\n\n" + body, encoding="utf-8")


def test_build_summary_collects_items_from_every_platform(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    yt = _make_handle(conn, "youtube", "@chan", "Some Channel")
    li = _make_handle(conn, "linkedin-profile", "bettywliu", "Betty Liu")
    db.record_handle_result(conn, run_row_id, yt, "ok", 1)
    db.record_handle_result(conn, run_row_id, li, "ok", 1)
    _write_post(repo_root, "youtube", "@chan", "vid1__slug.md",
                ["url: 'https://youtu.be/vid1'", "view_count: 900",
                 "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "# A Video Title\n\n## transcript\n\nWords here.\n")
    _write_post(repo_root, "linkedin-profile", "bettywliu", "7358.md",
                ["url: 'https://example.com/li'", "like_count: 12",
                 "fetched_at: '2026-08-01T06:02:00+00:00'"],
                "A LinkedIn post body.")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert {i["platform"] for i in summary["items"]} == {"youtube", "linkedin-profile"}
    assert summary["has_issues"] is False
    assert summary["errored"] == []


def test_build_summary_scans_an_errored_handle_that_downloaded_partially(notify_db):
    # discovery_engine records error/0 when process_handle raises AFTER some
    # downloads succeeded. The old status gate discarded exactly this row, so
    # those files reached no email at all.
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, status="completed_with_errors")
    handle_id = _make_handle(conn, "instagram", "someone", "Someone")
    db.record_handle_result(conn, run_row_id, handle_id, "error", 0, "boom")
    _write_post(repo_root, "instagram", "someone", "p1.md",
                ["url: 'https://instagram.com/p/1'",
                 "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "A caption that did land.")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert len(summary["items"]) == 1
    assert summary["errored"] == ["Someone"]
    assert summary["has_issues"] is True


def test_the_errors_list_carries_the_reason_each_handle_failed(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, status="completed_with_errors")
    hid = _make_handle(conn, "instagram", "someone", "Someone")
    db.record_handle_result(conn, run_row_id, hid, "error", 0,
                            "BrightDataError: 401 unauthorized\nat brightdata_job.py:88")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert summary["errors"] == [{"label": "Someone",
                                  "reason": "BrightDataError: 401 unauthorized"}]
    assert summary["errored"] == ["Someone"]          # unchanged, still the name list


def test_build_summary_scans_a_handle_recorded_with_zero_items(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn)
    handle_id = _make_handle(conn, "bluesky", "someone.bsky.social", "Someone BS")
    db.record_handle_result(conn, run_row_id, handle_id, "no_new_content", 0)
    _write_post(repo_root, "bluesky", "someone.bsky.social", "abc.md",
                ["url: 'https://bsky.app/x'", "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "A post that the count missed.")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)
    assert len(summary["items"]) == 1


def test_build_summary_reports_the_denominator_it_was_quiet_against(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn)
    for i in range(3):
        hid = _make_handle(conn, "bluesky", f"a{i}.bsky.social", f"Author {i}")
        db.record_handle_result(conn, run_row_id, hid, "no_new_content", 0)

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert summary["coverage"] == {"scanned": 3, "with_items": 0, "quiet": 3,
                                   "errored": 0, "other": {}}
    assert summary["has_issues"] is False


def test_a_skipped_handle_is_reported_under_its_own_status(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn)
    hid = _make_handle(conn, "bluesky", "someone.bsky.social", "Someone BS")
    db.record_handle_result(conn, run_row_id, hid, "skipped", 0)

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert summary["coverage"]["other"] == {"skipped": ["Someone BS"]}
    assert summary["has_issues"] is True
    text = email_render.render_email(summary | {"spotlight": None, "spotlight_rule": None,
                                                "drafts": []}, "2026-08-01")["text"]
    assert "skipped" in text and "Someone BS" in text


def test_an_empty_roster_is_an_issue_not_a_quiet_day(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn)          # zero handle result rows at all

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert summary["coverage"]["scanned"] == 0
    assert summary["has_issues"] is True


def test_build_summary_warns_on_count_mismatch_but_does_not_raise(notify_db, capsys):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn)
    handle_id = _make_handle(conn, "linkedin-profile", "bettywliu", "Betty Liu")
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 2)
    _write_post(repo_root, "linkedin-profile", "bettywliu", "one.md",
                ["url: 'https://example.com/x'", "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "Only one of the two.")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert len(summary["items"]) == 1
    assert "mismatch" in capsys.readouterr().err.lower()


def test_an_errored_handle_with_partial_downloads_is_informational_not_an_alarm(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, status="completed_with_errors",
                           started_at="2026-08-01T06:00:00+00:00")
    hid = _make_handle(conn, "instagram", "someone", "Someone")
    db.record_handle_result(conn, run_row_id, hid, "error", 0, "boom")
    _write_post(repo_root, "instagram", "someone", "p1.md",
                ["url: 'https://instagram.com/p/1'", "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "A caption that did land.")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)
    mismatch = summary["mismatches"][0]

    assert mismatch["direction"] == "extra"
    assert mismatch["escalated"] is False


def test_a_healthy_handle_that_lost_files_is_escalated_with_an_error_event(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    hid = _make_handle(conn, "linkedin-profile", "bettywliu", "Betty Liu")
    db.record_handle_result(conn, run_row_id, hid, "ok", 2)      # db says 2
    _write_post(repo_root, "linkedin-profile", "bettywliu", "one.md",
                ["url: 'https://example.com/x'", "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "Only one of the two.")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)
    mismatch = summary["mismatches"][0]

    assert mismatch["direction"] == "missing"
    assert mismatch["escalated"] is True
    assert summary["has_issues"] is True
    row = conn.execute(
        "SELECT severity FROM events WHERE kind = 'digest.items_missing'").fetchone()
    assert row["severity"] == "error"


def test_build_summary_uses_handle_fallback_for_errored_handle_without_display_name(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, status="completed_with_errors")
    handle_id = db.create_handle(conn, "youtube", "@dead-handle", None, "guru", None,
                                 "2026-07-01T00:00:00+00:00")
    db.record_handle_result(conn, run_row_id, handle_id, "error", 0, "gone")
    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)
    assert summary["errored"] == ["@dead-handle"]


def test_build_summary_carries_unreadable_files_into_the_summary(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = _make_handle(conn, "linkedin-profile", "bettywliu", "Betty Liu")
    db.record_handle_result(conn, run_row_id, handle_id, "no_new_content", 0)
    out = repo_root  # written directly so the frontmatter is genuinely corrupt
    _write_post(out, "linkedin-profile", "bettywliu", "broken.md",
                [": : not yaml : :"], "Body.")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert summary["items"] == []
    assert summary["skips"] == [
        {"handle": "Betty Liu", "reason": "bad_frontmatter", "name": "broken.md"}]
    assert summary["has_issues"] is True


def test_build_summary_records_an_event_for_every_unreadable_file(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = _make_handle(conn, "linkedin-profile", "bettywliu", "Betty Liu")
    db.record_handle_result(conn, run_row_id, handle_id, "no_new_content", 0)
    _write_post(repo_root, "linkedin-profile", "bettywliu", "broken.md",
                [": : not yaml : :"], "Body.")

    discovery_notify.build_summary(conn, repo_root, run_row_id)

    rows = conn.execute(
        "SELECT kind, severity, message FROM events WHERE kind = 'digest.item_unreadable'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["severity"] == "error"
    assert "broken.md" in rows[0]["message"]


def test_send_email_includes_an_html_part(monkeypatch):
    monkeypatch.setenv(discovery_notify.KEY_ENV_VAR, "test-key")
    captured = {}

    class FakeResponse:
        status_code = 200
        def raise_for_status(self):
            pass

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(discovery_notify.requests, "post", fake_post)
    assert discovery_notify.send_email("Subj", "plain body", "<p>html body</p>") is True
    assert captured["json"]["text"] == "plain body"
    assert captured["json"]["html"] == "<p>html body</p>"


def test_notify_threads_spotlight_and_drafts_into_render(monkeypatch, notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn)
    seen = {}

    item = {"marker": "the-item", "brands": ["guru"], "platform": "youtube", "handle": "@x", "item_id": "i1"}
    spotlight = {"marker": "the-spotlight", "platform": "youtube", "handle": "@x", "item_id": "i1"}
    monkeypatch.setattr(discovery_notify, "build_summary",
                        lambda *a: _fake_overall(items=[item]))
    monkeypatch.setattr(discovery_notify.discovery_digest, "select_spotlight_with_rule",
                        lambda items: (spotlight, discovery_notify.discovery_digest.SPOTLIGHT_RULE_ENGAGEMENT)
                        if items else (None, None))
    monkeypatch.setattr(discovery_notify.comment_draft, "draft_comments",
                        lambda item, **kw: ["d1", "d2", "d3"])

    def fake_render(overall, sections, run_date):
        seen["sections"] = sections
        seen["run_date"] = run_date
        return {"subject": "S", "text": "T", "html": "<p>H</p>"}

    monkeypatch.setattr(discovery_notify.email_render, "render_brand_digest", fake_render)
    monkeypatch.setattr(discovery_notify, "send_email", lambda *a: True)

    assert discovery_notify.notify(conn, repo_root, run_row_id) is True
    # `item` is tagged "guru" only, so only the guru section sees it as a spotlight.
    assert seen["sections"]["guru"]["spotlight"] == spotlight
    assert seen["sections"]["guru"]["drafts"] == ["d1", "d2", "d3"]
    assert seen["sections"]["freedom2beu"]["spotlight"] is None
    assert seen["sections"]["freedom2beu"]["drafts"] == []
    assert seen["run_date"] == "2026-08-01"


def test_notify_reuses_drafts_when_the_same_item_is_spotlighted_in_two_sections(monkeypatch, notify_db):
    # `guru` is a superset of `raisinggoodsports` here, so the identical post
    # is the best spotlight in both sections. draft_comments (a ~90s `claude
    # -p` subprocess call) must run once, not once per section -- High
    # finding #2 from the pre-execution review.
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = _make_handle(conn, "instagram", "aspenprojectplay", "Aspen Project Play")
    db.set_handle_brands(conn, handle_id, ["guru", "raisinggoodsports"])
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_post(repo_root, "instagram", "aspenprojectplay", "p1.md",
                ["url: 'https://instagram.com/p/1'", "like_count: 40",
                 "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "A caption with enough text to be a spotlight candidate.")

    draft_calls = []
    monkeypatch.setattr(discovery_notify.comment_draft, "draft_comments",
                         lambda item, **kw: draft_calls.append(item["item_id"]) or ["d1", "d2", "d3"])
    monkeypatch.setattr(discovery_notify, "send_email", lambda *a: True)

    discovery_notify.notify(conn, repo_root, run_row_id)

    assert len(draft_calls) == 1


def test_notify_partitions_items_by_brand_and_repeats_multi_tagged_items(monkeypatch, notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = _make_handle(conn, "instagram", "aspenprojectplay", "Aspen Project Play")
    db.set_handle_brands(conn, handle_id, ["guru", "raisinggoodsports"])
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_post(repo_root, "instagram", "aspenprojectplay", "p1.md",
                ["url: 'https://instagram.com/p/1'", "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "A caption that mentions youth sports parenting.")

    seen = {}
    monkeypatch.setattr(discovery_notify.comment_draft, "draft_comments", lambda item, **kw: [])
    monkeypatch.setattr(discovery_notify.email_render, "render_brand_digest",
                         lambda overall, sections, run_date:
                             (seen.setdefault("sections", sections),
                              {"subject": "s", "text": "t", "html": "h"})[-1])
    monkeypatch.setattr(discovery_notify, "send_email", lambda *a: True)

    discovery_notify.notify(conn, repo_root, run_row_id)

    assert len(seen["sections"]["guru"]["items"]) == 1
    assert len(seen["sections"]["raisinggoodsports"]["items"]) == 1
    assert len(seen["sections"]["freedom2beu"]["items"]) == 0


def test_notify_skips_drafting_when_there_is_no_spotlight(monkeypatch, notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn)
    calls = []
    monkeypatch.setattr(discovery_notify, "build_summary",
                        lambda *a: _fake_overall())
    monkeypatch.setattr(discovery_notify.discovery_digest, "select_spotlight_with_rule",
                        lambda items: (None, None))
    monkeypatch.setattr(discovery_notify.comment_draft, "draft_comments",
                        lambda item, **kw: calls.append(item) or [])
    monkeypatch.setattr(discovery_notify, "send_email", lambda *a: True)

    assert discovery_notify.notify(conn, repo_root, run_row_id) is True
    assert calls == []


def test_build_summary_attaches_brand_tags_from_the_producing_handle(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = _make_handle(conn, "instagram", "aspenprojectplay", "Aspen Project Play")
    db.set_handle_brands(conn, handle_id, ["guru", "raisinggoodsports"])
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_post(repo_root, "instagram", "aspenprojectplay", "p1.md",
                ["url: 'https://instagram.com/p/1'", "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "A caption.")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert len(summary["items"]) == 1
    assert summary["items"][0]["brands"] == ["guru", "raisinggoodsports"]


def test_notify_end_to_end_warns_on_orphaned_untagged_item(monkeypatch, notify_db):
    # Task 5's original end-to-end test used to exercise an untagged handle
    # through the real notify() pipeline; it was changed to tag its handle
    # with ["guru"], leaving no end-to-end coverage of the orphan-warning
    # banner (email_render.render_brand_digest's "no brand tag" text). This
    # restores that coverage against the real build_summary/render pipeline,
    # mocking only send_email.
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = _make_handle(conn)  # no set_handle_brands call -- stays untagged
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_youtube_video(repo_root, "@somechannel", "vid1", "Untagged Video", "2026-08-01T06:01:00+00:00")

    captured = {}
    monkeypatch.setattr(
        discovery_notify, "send_email",
        lambda subject, text, html: (captured.setdefault("text", text), captured.setdefault("html", html), True)[-1],
    )

    result = discovery_notify.notify(conn, repo_root, run_row_id)

    assert result is True
    assert "no brand tag" in captured["text"].lower()
    assert "no brand tag" in captured["html"].lower()


def test_notify_end_to_end_run_level_facts_render_identically_across_sections(monkeypatch, notify_db):
    # run_status/has_issues/errored are run-wide facts copied verbatim into
    # every brand section (discovery_notify.notify()), not filtered per
    # brand like items are. Exercises that through the real notify()
    # pipeline: one handle tagged with all three brands (so its section
    # membership doesn't hide the shared facts) plus one errored, untagged
    # handle whose error must still show up in all three sections.
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, status="completed_with_errors")
    handle_id = _make_handle(conn, "instagram", "aspenprojectplay", "Aspen Project Play")
    db.set_handle_brands(conn, handle_id, ["guru", "raisinggoodsports", "freedom2beu"])
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_post(repo_root, "instagram", "aspenprojectplay", "p1.md",
                ["url: 'https://instagram.com/p/1'", "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "A caption.")
    errored_handle_id = db.create_handle(conn, "youtube", "@dead-handle", None, "guru", None,
                                         "2026-07-01T00:00:00+00:00")
    db.record_handle_result(conn, run_row_id, errored_handle_id, "error", 0, "gone")

    captured = {}
    monkeypatch.setattr(discovery_notify.comment_draft, "draft_comments", lambda item, **kw: [])
    monkeypatch.setattr(
        discovery_notify, "send_email",
        lambda subject, text, html: (captured.setdefault("text", text), captured.setdefault("html", html), True)[-1],
    )

    result = discovery_notify.notify(conn, repo_root, run_row_id)

    assert result is True
    text, html = captured["text"], captured["html"]
    # Once per brand section (guru, raisinggoodsports, freedom2beu).
    assert text.count("@dead-handle") == 3
    assert html.count("@dead-handle") == 3
    assert text.count("Run status: completed_with_errors") == 3
    assert html.count("Run status: completed_with_errors") == 3


def test_notify_end_to_end_prints_run_level_facts_once_not_once_per_section(monkeypatch, notify_db):
    # The other side of the coin from the test above: run-wide facts that
    # describe the RUN rather than a handle must appear ONCE in the whole
    # email, not once per brand section. Task 12 threaded overall["coverage"]
    # into every sections[brand] dict as an interim measure, which made the
    # real production email print "Handles reported as skipped" three times
    # (B-95b). This exercises the fix through the real notify() pipeline.
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = _make_handle(conn, "instagram", "aspenprojectplay", "Aspen Project Play")
    db.set_handle_brands(conn, handle_id, ["guru", "raisinggoodsports", "freedom2beu"])
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_post(repo_root, "instagram", "aspenprojectplay", "p1.md",
                ["url: 'https://instagram.com/p/1'", "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "A caption.")
    skipped_id = db.create_handle(conn, "youtube", "@quota-handle", "Quota Handle", "guru", None,
                                  "2026-07-01T00:00:00+00:00")
    db.record_handle_result(conn, run_row_id, skipped_id, "skipped", 0)

    captured = {}
    monkeypatch.setattr(discovery_notify.comment_draft, "draft_comments", lambda item, **kw: [])
    monkeypatch.setattr(
        discovery_notify, "send_email",
        lambda subject, text, html: (captured.setdefault("text", text),
                                     captured.setdefault("html", html), True)[-1],
    )

    assert discovery_notify.notify(conn, repo_root, run_row_id) is True
    for part in (captured["text"], captured["html"]):
        assert part.count("Handles reported as skipped") == 1
        assert part.count("Quota Handle") == 1
        assert part.count("Scanned 2 handle(s)") == 1


def test_notify_end_to_end_names_the_linkedin_gate_in_the_sent_email(monkeypatch, notify_db):
    # Task 5 (B-96): the spotlight rule must reach the actual sent email, not
    # just the unit-level select_spotlight_with_rule/render_email tests. This
    # exercises the real build_summary -> notify -> render_brand_digest path
    # with a LinkedIn item present, mocking only send_email and draft_comments.
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = db.create_handle(conn, "linkedin-profile", "bettywliu", "Betty Liu",
                                 "guru", None, "2026-07-01T00:00:00+00:00")
    db.set_handle_brands(conn, handle_id, ["guru"])
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_post(repo_root, "linkedin-profile", "bettywliu", "7358.md",
                ["url: 'https://example.com/li'", "like_count: 12",
                 "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "A LinkedIn post body with enough text to spotlight.")

    captured = {}
    monkeypatch.setattr(discovery_notify.comment_draft, "draft_comments", lambda item, **kw: [])
    monkeypatch.setattr(
        discovery_notify, "send_email",
        lambda subject, text, html: (captured.setdefault("text", text),
                                     captured.setdefault("html", html), True)[-1],
    )

    result = discovery_notify.notify(conn, repo_root, run_row_id)

    assert result is True
    assert "LinkedIn posts are always picked first" in captured["text"]
    assert "LinkedIn posts are always picked first" in captured["html"]


def test_a_slug_collision_does_not_double_the_subject_count(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    for handle in ("john.doe.5", "johndoe5"):
        hid = _make_handle(conn, "linkedin-profile", handle, handle)
        db.record_handle_result(conn, run_row_id, hid, "ok", 1)
    _write_post(repo_root, "linkedin-profile", "john.doe.5", "post1.md",
                ["url: 'https://example.com/p1'", "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "One post, two registered handles.")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert len(summary["items"]) == 1
    assert len(summary["duplicates"]) == 1
    assert summary["has_issues"] is True


def _three_handles(conn, run_row_id, prefix):
    """Three linkedin-profile handles, all scanned, all reporting zero items.

    `prefix` exists because handles has UNIQUE(platform, handle): the two runs
    in the pair test below each need their own three rows.
    """
    handles = []
    for i in range(3):
        hid = _make_handle(conn, "linkedin-profile", f"{prefix}author{i}", f"Author {i}")
        db.record_handle_result(conn, run_row_id, hid, "no_new_content", 0)
        handles.append(f"{prefix}author{i}")
    return handles


def _sent(monkeypatch, conn, repo_root, run_row_id):
    """What an operator's inbox actually receives for this run.

    Deliberately drives the REAL production path -- discovery_notify.notify()
    -> build_summary() -> render_brand_digest() -> send_email() -- and captures
    send_email's own (subject, text, html) arguments. Asserting on
    email_render.render_email() instead would prove nothing: production never
    calls it (render_brand_digest is the entrypoint notify() reaches).
    """
    captured = {}

    def fake_send(subject, text, html=None):
        captured.update(subject=subject, text=text, html=html)
        return True

    monkeypatch.setattr(discovery_notify, "send_email", fake_send)
    assert discovery_notify.notify(conn, repo_root, run_row_id) is True
    return captured


def test_a_quiet_day_and_a_broken_collection_are_not_the_same_email(monkeypatch, notify_db, tmp_path):
    """The single defect this package exists to close.

    Two runs, ZERO items each. One is genuinely quiet: three handles scanned,
    every captured file legitimately older than the run's watermark. One is
    broken: three handles scanned, every captured file inside the watermark and
    unparseable. Before this package both rendered the byte-identical body
    `No new content today.` with no [ISSUE] prefix.
    """
    conn, quiet_root = notify_db
    started = "2026-08-01T06:00:00+00:00"

    quiet_run = _make_run(conn, started_at=started)
    for handle in _three_handles(conn, quiet_run, "quiet-"):
        _write_post(quiet_root, "linkedin-profile", handle, "yesterday.md",
                    ["url: 'https://example.com/old'",
                     "fetched_at: '2026-07-31T06:00:00+00:00'"], "Yesterday's post.")

    broken_root = tmp_path / "broken"
    broken_run = _make_run(conn, started_at=started, run_id="2026-08-01T06-00-00-000001")
    for handle in _three_handles(conn, broken_run, "broken-"):
        _write_post(broken_root, "linkedin-profile", handle, "corrupt.md",
                    [": : not yaml : :"], "Today's post, unreadable.")

    # The premise, checked against build_summary directly -- notify() returns a
    # bool, not the summary, so this assertion cannot ride on the send capture.
    quiet_summary = discovery_notify.build_summary(conn, quiet_root, quiet_run)
    broken_summary = discovery_notify.build_summary(conn, broken_root, broken_run)
    assert len(quiet_summary["items"]) == len(broken_summary["items"]) == 0

    # ...and different emails, as actually sent.
    quiet = _sent(monkeypatch, conn, quiet_root, quiet_run)
    broken = _sent(monkeypatch, conn, broken_root, broken_run)

    assert quiet["subject"] != broken["subject"]
    assert quiet["text"] != broken["text"]
    assert quiet["html"] != broken["html"]

    assert not quiet["subject"].startswith("[ISSUE] ")
    assert broken["subject"].startswith("[ISSUE] ")
    assert "Scanned 3 handle(s)" in quiet["text"]
    assert "could not be read" not in quiet["text"]
    assert "3 captured file(s) could not be read" in broken["text"]
    assert "corrupt.md" in broken["text"]
    # Same facts in the HTML part -- a text-only assertion would let the two
    # emails stay indistinguishable for every client that renders HTML.
    assert "could not be read" not in quiet["html"]
    assert "3 captured file(s) could not be read" in broken["html"]
    # The run-level notices are rendered ONCE, under all three brand sections,
    # not once per section (B-95b).
    for part in (quiet["text"], quiet["html"], broken["text"], broken["html"]):
        assert part.count("Scanned 3 handle(s)") == 1
    for part in (broken["text"], broken["html"]):
        assert part.count("captured file(s) could not be read") == 1


def test_only_the_broken_run_leaves_an_error_event(notify_db, tmp_path):
    conn, quiet_root = notify_db
    started = "2026-08-01T06:00:00+00:00"
    quiet_run = _make_run(conn, started_at=started)
    for handle in _three_handles(conn, quiet_run, "quiet-"):
        _write_post(quiet_root, "linkedin-profile", handle, "yesterday.md",
                    ["url: 'https://example.com/old'",
                     "fetched_at: '2026-07-31T06:00:00+00:00'"], "Yesterday's post.")
    discovery_notify.build_summary(conn, quiet_root, quiet_run)
    assert conn.execute("SELECT COUNT(*) c FROM events WHERE severity = 'error'"
                        ).fetchone()["c"] == 0

    broken_root = tmp_path / "broken"
    broken_run = _make_run(conn, started_at=started, run_id="2026-08-01T06-00-00-000001")
    for handle in _three_handles(conn, broken_run, "broken-"):
        _write_post(broken_root, "linkedin-profile", handle, "corrupt.md",
                    [": : not yaml : :"], "Today's post, unreadable.")
    discovery_notify.build_summary(conn, broken_root, broken_run)
    assert conn.execute("SELECT COUNT(*) c FROM events WHERE severity = 'error'"
                        ).fetchone()["c"] == 3


def test_build_summary_untagged_handle_produces_items_with_no_brands(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = _make_handle(conn)  # no set_handle_brands call -- stays untagged
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_youtube_video(repo_root, "@somechannel", "vid1", "A Video", "2026-08-01T06:01:00+00:00")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert summary["items"][0]["brands"] == []
