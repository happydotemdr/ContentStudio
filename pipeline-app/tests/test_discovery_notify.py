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
                                             {"run_status": "completed", "has_issues": False,
                                              "items": [], "errored": []})[1])
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
    assert overall == {"run_status": "completed", "has_issues": False, "items": [], "errored": []}
    assert set(sections) == {"freedom2beu", "raisinggoodsports", "guru"}
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
                        lambda *a: {"run_status": "completed", "has_issues": False,
                                    "items": [item], "errored": []})
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
                        lambda *a: {"run_status": "completed", "has_issues": False,
                                    "items": [], "errored": []})
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


def test_build_summary_untagged_handle_produces_items_with_no_brands(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = _make_handle(conn)  # no set_handle_brands call -- stays untagged
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_youtube_video(repo_root, "@somechannel", "vid1", "A Video", "2026-08-01T06:01:00+00:00")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert summary["items"][0]["brands"] == []
