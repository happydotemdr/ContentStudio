# coach-prep-app/tests/test_orchestrator.py
from __future__ import annotations

import datetime as dt

import pytest

from coach_prep_app import orchestrator

CLIENT = {
    "slug": "sean", "display_name": "Sean", "primary_email": "sean@example.com",
    "alias_emails": [], "session_outlines_dir": "x", "drive_folder_id": "sean-folder",
}
OTHER_CLIENT = {
    "slug": "josh", "display_name": "Josh", "primary_email": "josh@example.com",
    "alias_emails": [], "session_outlines_dir": "y", "drive_folder_id": "josh-folder",
}


@pytest.fixture
def cfg():
    from coach_prep_app.config import Config
    return Config(pending_review_drive_folder_id="pending-folder")


def _patch_pipeline_ok(monkeypatch):
    from coach_prep_app import bundle as bundle_mod
    from coach_prep_app import generate, publish

    monkeypatch.setattr(
        bundle_mod, "build_bundle",
        lambda *a, **k: {
            "client_display_name": "Sean", "client_slug": "sean",
            "last_meeting_email": {"source_label": "last-meeting-email", "thread_id": "t1", "text": "x"},
            "last_meeting_note": {"source_label": "last-meeting-note", "rel_path": "a.md", "version": 1, "text": "y"},
            "program_sources": [{"source_label": "program-source-1", "rel_path": "b.md", "version": None, "text": "z"}],
        },
    )
    monkeypatch.setattr(bundle_mod, "persist_inputs", lambda *a, **k: None)
    monkeypatch.setattr(generate, "generate_draft", lambda b, timeout_s=180: "## Activities\n- x [last-meeting-email]")
    monkeypatch.setattr(publish, "publish_draft", lambda *a, **k: "drive-file-1")
    return bundle_mod, generate, publish


def test_process_candidate_not_due_short_circuits(conn, cfg, monkeypatch):
    event = {"instance_id": "evt1", "start_utc": dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)}
    now = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)  # far before ready time
    result = orchestrator.process_candidate(conn, None, None, None, None, cfg, CLIENT, event, now)
    assert result == "not_due"


def test_process_candidate_happy_path_publishes_and_notifies(conn, cfg, monkeypatch):
    _patch_pipeline_ok(monkeypatch)
    from coach_prep_app import notify
    sent = {}
    monkeypatch.setattr(notify, "send_email", lambda subject, text, recipient=notify.RECIPIENT: sent.setdefault("ok", True) or True)

    event = {"instance_id": "evt1", "start_utc": dt.datetime(2026, 8, 20, 15, 0, tzinfo=dt.timezone.utc)}
    now = dt.datetime(2026, 8, 19, 13, 0, tzinfo=dt.timezone.utc)  # after 7am Chicago the day before

    class _FakeDocIngestConn:
        pass

    import coach_prep_app.doc_ingest_reader as reader
    monkeypatch.setattr(reader, "get_active_clients", lambda conn: [CLIENT, OTHER_CLIENT])

    result = orchestrator.process_candidate(
        conn, _FakeDocIngestConn(), None, None, None, cfg, CLIENT, event, now
    )
    assert result == "published"
    assert sent["ok"] is True

    run = conn.execute("SELECT status, draft_drive_file_id FROM generation_runs").fetchone()
    assert run == ("notified", "drive-file-1")


def test_process_candidate_gate_failure_never_publishes_and_never_retries(conn, cfg, monkeypatch):
    """Spec: a gate failure is 'a hard stop, never auto-retried silently' --
    not just 'don't publish this once', but 'don't keep re-generating and
    re-alerting on every future wake for this same meeting' either."""
    bundle_mod, generate, publish = _patch_pipeline_ok(monkeypatch)
    # Generated text leaks another client's display name.
    monkeypatch.setattr(generate, "generate_draft", lambda b, timeout_s=180: "mentions Josh directly [last-meeting-email]")
    publish_calls = []
    monkeypatch.setattr(publish, "publish_draft", lambda *a, **k: publish_calls.append(1) or "should-not-happen")

    from coach_prep_app import notify
    alerts = []
    monkeypatch.setattr(notify, "send_email", lambda subject, text, recipient=notify.RECIPIENT: alerts.append(subject) or True)

    import coach_prep_app.doc_ingest_reader as reader
    monkeypatch.setattr(reader, "get_active_clients", lambda conn: [CLIENT, OTHER_CLIENT])

    event = {"instance_id": "evt1", "start_utc": dt.datetime(2026, 8, 20, 15, 0, tzinfo=dt.timezone.utc)}
    now = dt.datetime(2026, 8, 19, 13, 0, tzinfo=dt.timezone.utc)

    class _FakeDocIngestConn:
        pass

    result = orchestrator.process_candidate(conn, _FakeDocIngestConn(), None, None, None, cfg, CLIENT, event, now)
    assert result == "gate_failed"
    assert publish_calls == []
    assert len(alerts) == 1
    assert "ALERT" in alerts[0]

    run = conn.execute("SELECT status FROM generation_runs").fetchone()
    assert run[0] == "gates_failed"

    # A later wake for the SAME event must not re-generate or re-alert --
    # the watermark is set on gate failure specifically to make this true.
    later = now + dt.timedelta(hours=4)
    result2 = orchestrator.process_candidate(conn, _FakeDocIngestConn(), None, None, None, cfg, CLIENT, event, later)
    assert result2 == "not_due"
    assert len(alerts) == 1  # unchanged -- no second ALERT


def test_process_candidate_retries_notify_only_after_a_publish_that_failed_to_notify(conn, cfg, monkeypatch):
    """A publish that succeeds but whose notification email fails must NOT
    cause the next wake to regenerate and re-publish a second, orphaned
    draft -- it should retry sending the notification for the SAME draft."""
    bundle_mod, generate, publish = _patch_pipeline_ok(monkeypatch)
    generate_calls = []
    original_generate = generate.generate_draft
    monkeypatch.setattr(generate, "generate_draft", lambda b, timeout_s=180: generate_calls.append(1) or original_generate(b))
    publish_calls = []
    monkeypatch.setattr(publish, "publish_draft", lambda *a, **k: publish_calls.append(1) or "drive-file-1")

    from coach_prep_app import notify
    send_results = [False, True]  # first attempt fails, second succeeds
    sent_subjects = []
    monkeypatch.setattr(
        notify, "send_email",
        lambda subject, text, recipient=notify.RECIPIENT: sent_subjects.append(subject) or send_results.pop(0),
    )

    import coach_prep_app.doc_ingest_reader as reader
    monkeypatch.setattr(reader, "get_active_clients", lambda conn: [CLIENT, OTHER_CLIENT])

    event = {"instance_id": "evt1", "start_utc": dt.datetime(2026, 8, 20, 15, 0, tzinfo=dt.timezone.utc)}
    now = dt.datetime(2026, 8, 19, 13, 0, tzinfo=dt.timezone.utc)

    class _FakeDocIngestConn:
        pass

    result1 = orchestrator.process_candidate(conn, _FakeDocIngestConn(), None, None, None, cfg, CLIENT, event, now)
    assert result1 == "publish_ok_notify_failed"
    assert len(publish_calls) == 1

    later = now + dt.timedelta(hours=4)
    result2 = orchestrator.process_candidate(conn, _FakeDocIngestConn(), None, None, None, cfg, CLIENT, event, later)
    assert result2 == "published"

    # The second wake must reuse the existing draft -- not regenerate or republish it.
    assert len(generate_calls) == 1
    assert len(publish_calls) == 1
    assert len(sent_subjects) == 2

    run = conn.execute("SELECT status, draft_drive_file_id FROM generation_runs").fetchone()
    assert run == ("notified", "drive-file-1")


def test_run_once_classifies_events_and_skips_unmatched(conn, cfg, monkeypatch):
    import coach_prep_app.doc_ingest_reader as reader
    monkeypatch.setattr(reader, "get_active_clients", lambda conn: [CLIENT])

    now = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
    far_future_meeting = dt.datetime(2030, 1, 1, 15, 0, tzinfo=dt.timezone.utc)  # well past the 7am-day-before threshold

    def fake_list_events(calendar_service, cfg, now_utc):
        return [
            {"instance_id": "evt1", "start_utc": far_future_meeting, "attendees": ["sean@example.com"]},
            {"instance_id": "evt2", "start_utc": far_future_meeting, "attendees": ["stranger@example.com"]},
        ]

    monkeypatch.setattr(orchestrator, "_list_upcoming_events", fake_list_events)
    results = orchestrator.run_once(conn, None, None, None, None, cfg, now)
    assert results == ["not_due"]  # evt1 (Sean, far future) is not yet due; evt2 (unmatched) skipped entirely
