# coach-prep-app/tests/test_orchestrator.py
from __future__ import annotations

import datetime as dt

import pytest

from coach_prep_app import config, orchestrator

# Self-sufficient cross-app import setup, mirroring test_doc_ingest_reader.py
# -- without this, `_classify_event`'s deferred `from doc_ingest import
# client_matching` only resolves when this file happens to be collected
# after test_doc_ingest_reader.py (alphabetical collection order), so this
# file fails with ModuleNotFoundError when run in isolation or under
# pytest-xdist's parallel collection.
config.ensure_doc_ingest_importable(config.Config().doc_ingest_app_root)

CLIENT = {
    "slug": "sean", "display_name": "Sean", "primary_email": "sean@example.com",
    "alias_emails": [], "session_outlines_dir": "x", "drive_folder_id": "sean-folder",
}
OTHER_CLIENT = {
    "slug": "josh", "display_name": "Josh", "primary_email": "josh@example.com",
    "alias_emails": [], "session_outlines_dir": "y", "drive_folder_id": "josh-folder",
}


# The shape the real build_bundle returns. Kept in one place and checked
# against the real function by test_sample_bundle_matches_the_real_shape below
# -- an inline stub written by hand is exactly how a suite goes green while
# production raises KeyError, which is what happened when the bundle grew from
# one email and one note to several of each.
SAMPLE_BUNDLE = {
    "client_display_name": "Sean",
    "client_slug": "sean",
    "recent_emails": [
        {"source_label": "last-meeting-email", "thread_id": "t1", "subject": "Follow-up",
         "sent_date": "2026-08-18", "text": "x"},
    ],
    "meeting_notes": [
        {"source_label": "meeting-note-aug", "rel_path": "a.md", "version": 1,
         "meeting_date": "2026-08-04", "text": "y"},
    ],
    "program_sources": [
        {"source_label": "program-source-1", "rel_path": "b.md", "version": None, "text": "z"},
    ],
    "book_list": {"source_label": "f2bu-coaching-book-recommendations", "rel_path": "c.md",
                  "version": None, "text": "| Book | Author |"},
    "selected_frameworks": [],
}


@pytest.fixture
def cfg():
    from coach_prep_app.config import Config
    return Config(pending_review_drive_folder_id="pending-folder")


SAMPLE_ACTIVITY = {
    "id": "examining-fear", "title": "Examining Fear",
    "framework": "ABC's of coaching / Awareness", "kind": "activity",
    "anchor": None, "live_ready": True, "duration_min": 10,
    "why": "the undone call", "source_label": "fear",
    "rel_path": "f/fear.md", "version": 1, "text": "Rate the fear 1-10.",
}


def _patch_pipeline_ok(monkeypatch, selection=None, invented=(), persist_inputs=False):
    from coach_prep_app import bundle as bundle_mod
    from coach_prep_app import framework_catalog, generate, publish, select_frameworks

    monkeypatch.setattr(bundle_mod, "build_bundle", lambda *a, **k: dict(SAMPLE_BUNDLE))
    monkeypatch.setattr(framework_catalog, "load_catalog", lambda path: ["a catalog entry"])
    monkeypatch.setattr(framework_catalog, "render_index", lambda entries: "the index")
    monkeypatch.setattr(
        select_frameworks, "select",
        lambda *a, **k: (
            list(selection if selection is not None else [SAMPLE_ACTIVITY]), list(invented)
        ),
    )
    if not persist_inputs:
        monkeypatch.setattr(bundle_mod, "persist_inputs", lambda *a, **k: None)
    monkeypatch.setattr(generate, "generate_draft", lambda b, timeout_s=180, session_minutes=None: "## Activities\n- x [last-meeting-email]")
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


def test_process_candidate_uses_client_local_meeting_date_not_utc_date(conn, cfg, monkeypatch):
    """event['start_utc'] is the raw UTC calendar date. For
    cfg.timezone_name='America/Chicago' (the default), 2026-08-21 02:00 UTC
    is 2026-08-20 21:00 Central (CDT is UTC-5 in August) -- the evening
    BEFORE, a different calendar date. The draft title (publish.publish_draft)
    and the review email (notify.render_review_email) must both use the
    client-local date, not the UTC date, or a late-evening session gets
    dated one day late."""
    bundle_mod, generate, publish = _patch_pipeline_ok(monkeypatch)
    publish_dates = []
    monkeypatch.setattr(
        publish, "publish_draft",
        lambda drive_service, folder_id, display_name, meeting_date, body: (
            publish_dates.append(meeting_date) or "drive-file-1"
        ),
    )

    from coach_prep_app import notify
    original_render = notify.render_review_email
    review_dates = []

    def capture_render(display_name, meeting_date, file_id):
        review_dates.append(meeting_date)
        return original_render(display_name, meeting_date, file_id)

    monkeypatch.setattr(notify, "render_review_email", capture_render)
    monkeypatch.setattr(notify, "send_email", lambda subject, text, recipient=notify.RECIPIENT: True)

    import coach_prep_app.doc_ingest_reader as reader
    monkeypatch.setattr(reader, "get_active_clients", lambda conn: [CLIENT, OTHER_CLIENT])

    event = {"instance_id": "evt1", "start_utc": dt.datetime(2026, 8, 21, 2, 0, tzinfo=dt.timezone.utc)}
    now = dt.datetime(2026, 8, 20, 20, 0, tzinfo=dt.timezone.utc)  # after ready time, before the meeting

    class _FakeDocIngestConn:
        pass

    result = orchestrator.process_candidate(conn, _FakeDocIngestConn(), None, None, None, cfg, CLIENT, event, now)
    assert result == "published"

    assert publish_dates == [dt.date(2026, 8, 20)]
    assert review_dates == [dt.date(2026, 8, 20)]


def test_process_candidate_gate_failure_never_publishes_and_never_retries(conn, cfg, monkeypatch):
    """Spec: a gate failure is 'a hard stop, never auto-retried silently' --
    not just 'don't publish this once', but 'don't keep re-generating and
    re-alerting on every future wake for this same meeting' either."""
    bundle_mod, generate, publish = _patch_pipeline_ok(monkeypatch)
    # Generated text leaks another client's display name.
    monkeypatch.setattr(generate, "generate_draft", lambda b, timeout_s=180, session_minutes=None: "mentions Josh directly [last-meeting-email]")
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


def test_process_candidate_records_when_the_gate_failure_alert_itself_fails_to_send(conn, cfg, monkeypatch):
    """A gates_failed run is the exact event this isolation system exists
    to catch -- if the ALERT email about it also fails to send, that must
    not make the whole event invisible. Recorded in failure_reason so the
    weekly audit or a human inspecting the DB can still find it."""
    bundle_mod, generate, publish = _patch_pipeline_ok(monkeypatch)
    monkeypatch.setattr(generate, "generate_draft", lambda b, timeout_s=180, session_minutes=None: "mentions Josh directly [last-meeting-email]")

    from coach_prep_app import notify
    monkeypatch.setattr(notify, "send_email", lambda subject, text, recipient=notify.RECIPIENT: False)

    import coach_prep_app.doc_ingest_reader as reader
    monkeypatch.setattr(reader, "get_active_clients", lambda conn: [CLIENT, OTHER_CLIENT])

    event = {"instance_id": "evt1", "start_utc": dt.datetime(2026, 8, 20, 15, 0, tzinfo=dt.timezone.utc)}
    now = dt.datetime(2026, 8, 19, 13, 0, tzinfo=dt.timezone.utc)

    class _FakeDocIngestConn:
        pass

    result = orchestrator.process_candidate(conn, _FakeDocIngestConn(), None, None, None, cfg, CLIENT, event, now)
    assert result == "gate_failed"

    failure_reason = conn.execute("SELECT failure_reason FROM generation_runs").fetchone()[0]
    assert "ALERT EMAIL FAILED" in failure_reason


def test_process_candidate_generation_failure_is_retried_not_terminal(conn, cfg, monkeypatch):
    """The other half of the terminal/retry asymmetry that must never be
    swapped with gate failure's: a transient generation failure leaves the
    watermark unset (retried next wake), writes status='failed' (never
    'gates_failed'), and sends no alert at all."""
    bundle_mod, generate, publish = _patch_pipeline_ok(monkeypatch)
    monkeypatch.setattr(generate, "generate_draft", lambda b, timeout_s=180, session_minutes=None: None)
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
    assert result == "generation_failed"
    assert publish_calls == []
    assert alerts == []  # no alert on a transient failure -- only a gate failure alerts

    run = conn.execute("SELECT status FROM generation_runs").fetchone()
    assert run[0] == "failed"

    # A later wake for the SAME event must retry (watermark deliberately
    # left unset) -- the opposite of gate failure's terminal watermark set.
    later = now + dt.timedelta(hours=4)
    result2 = orchestrator.process_candidate(conn, _FakeDocIngestConn(), None, None, None, cfg, CLIENT, event, later)
    assert result2 == "generation_failed"


def test_process_candidate_retries_notify_only_after_a_publish_that_failed_to_notify(conn, cfg, monkeypatch):
    """A publish that succeeds but whose notification email fails must NOT
    cause the next wake to regenerate and re-publish a second, orphaned
    draft -- it should retry sending the notification for the SAME draft."""
    bundle_mod, generate, publish = _patch_pipeline_ok(monkeypatch)
    generate_calls = []
    original_generate = generate.generate_draft
    monkeypatch.setattr(generate, "generate_draft", lambda b, timeout_s=180, session_minutes=None: generate_calls.append(1) or original_generate(b))
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


def test_run_once_isolates_a_per_client_failure_and_continues(conn, cfg, monkeypatch):
    """Spec: 'API failure mid-run -> log, skip that client this wake.' One
    client's process_candidate raising (e.g. a Calendar/Gmail/Drive
    HttpError) must not abort the whole wake -- every other client's
    candidate must still be attempted."""
    import coach_prep_app.doc_ingest_reader as reader
    monkeypatch.setattr(reader, "get_active_clients", lambda conn: [CLIENT, OTHER_CLIENT])

    far_future_meeting = dt.datetime(2030, 1, 1, 15, 0, tzinfo=dt.timezone.utc)
    now = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)

    def fake_list_events(calendar_service, cfg, now_utc):
        return [
            {"instance_id": "evt-sean", "start_utc": far_future_meeting, "attendees": ["sean@example.com"]},
            {"instance_id": "evt-josh", "start_utc": far_future_meeting, "attendees": ["josh@example.com"]},
        ]

    monkeypatch.setattr(orchestrator, "_list_upcoming_events", fake_list_events)

    calls = []

    def flaky_process_candidate(conn, doc_ingest_conn, calendar_service, gmail_service, drive_service,
                                 cfg, client, event, now_utc):
        calls.append(client["slug"])
        if client["slug"] == "sean":
            raise RuntimeError("simulated Calendar API failure for sean")
        return "not_due"

    monkeypatch.setattr(orchestrator, "process_candidate", flaky_process_candidate)

    results = orchestrator.run_once(conn, None, None, None, None, cfg, now)

    # Both clients were attempted -- josh's candidate wasn't starved by
    # sean's failure -- and the failure surfaces in the results rather
    # than propagating out of run_once.
    assert calls == ["sean", "josh"]
    assert results == ["error: sean", "not_due"]


def test_sample_bundle_matches_the_real_shape():
    """Pins the stub above to what build_bundle actually returns.

    Every orchestrator test runs against SAMPLE_BUNDLE rather than the real
    assembler. When the bundle grew from one email and one note to several of
    each, the old inline stub kept the retired keys -- so the whole suite
    stayed green while process_candidate raised KeyError on the first real
    run. This is the assertion that would have caught it."""
    from coach_prep_app import bundle as bundle_mod
    from coach_prep_app.config import Config

    class _Reader:
        @staticmethod
        def get_recent_meeting_notes(conn, cfg, slug, limit=2):
            return []

        @staticmethod
        def get_program_sources(cfg):
            return []

    class _NoEmail:
        def users(self):
            return self

        def messages(self):
            return self

        def list(self, **kwargs):
            return self

        def execute(self):
            return {"messages": []}

    real = bundle_mod.build_bundle(
        _NoEmail(), _Reader(), None, Config(),
        {"slug": "sean", "display_name": "Sean", "primary_email": "sean@example.com"},
        dt.datetime(2026, 8, 19, tzinfo=dt.timezone.utc),
    )
    assert set(SAMPLE_BUNDLE) == set(real), (
        f"stub drifted: only in stub {set(SAMPLE_BUNDLE) - set(real)}, "
        f"only in real {set(real) - set(SAMPLE_BUNDLE)}"
    )


def test_generate_draft_stubs_match_the_real_signature():
    """Every orchestrator test replaces generate_draft with a lambda whose
    parameters are written out by hand. When the real function gained
    session_minutes, six of them started raising TypeError -- the stubs and
    the thing they stand in for had drifted apart with nothing checking."""
    import inspect
    from coach_prep_app import generate

    real = set(inspect.signature(generate.generate_draft).parameters)
    stubbed = {"b", "timeout_s", "session_minutes"} - {"b"} | {"bundle"}
    assert real == stubbed, (
        f"generate_draft's signature changed to {sorted(real)} -- update the "
        f"lambdas in this file to match"
    )


# --- the two-stage pipeline -------------------------------------------------

_EVENT = {"instance_id": "evt1", "start_utc": dt.datetime(2026, 8, 20, 15, 0, tzinfo=dt.timezone.utc)}
_NOW = dt.datetime(2026, 8, 19, 13, 0, tzinfo=dt.timezone.utc)


class _FakeDocIngestConn:
    pass


def _run(conn, cfg, monkeypatch, event=None, publish_capture=None):
    from coach_prep_app import notify, publish as publish_mod
    import coach_prep_app.doc_ingest_reader as reader
    monkeypatch.setattr(notify, "send_email", lambda *a, **k: True)
    monkeypatch.setattr(reader, "get_active_clients", lambda conn: [CLIENT, OTHER_CLIENT])
    if publish_capture is not None:
        monkeypatch.setattr(
            publish_mod, "publish_draft",
            lambda drive, folder, name, date, body: (
                publish_capture.append(body) or "drive-file-1"
            ),
        )
    return orchestrator.process_candidate(
        conn, _FakeDocIngestConn(), None, None, None, cfg, CLIENT, event or _EVENT, _NOW
    )


def test_selected_activities_reach_the_drafting_bundle(conn, cfg, monkeypatch):
    """Stage 1 picks, stage 2 drafts from the full text of what it picked.
    If the selection never reached the bundle, the prep doc would be built on
    the program material alone and look no different from before."""
    _patch_pipeline_ok(monkeypatch)
    from coach_prep_app import generate
    seen = {}
    monkeypatch.setattr(
        generate, "generate_draft",
        lambda b, timeout_s=180, session_minutes=None: (
            seen.update(b) or "## Summary\n\n- x [last-meeting-email]"
        ),
    )
    assert _run(conn, cfg, monkeypatch) == "published"
    assert [a["id"] for a in seen["selected_frameworks"]] == ["examining-fear"]


def test_selected_activities_are_recorded_as_inputs(conn, cfg, monkeypatch):
    """The closing manifest is rendered from generation_inputs. An activity
    the doc recommends but the manifest omits breaks the completeness promise
    that section makes."""
    _patch_pipeline_ok(monkeypatch, persist_inputs=True)
    assert _run(conn, cfg, monkeypatch) == "published"
    kinds = conn.execute(
        "SELECT source_kind, reference FROM generation_inputs WHERE source_kind = 'selected_framework'"
    ).fetchall()
    assert kinds == [("selected_framework", "f/fear.md")]


def test_a_failed_selection_is_retried_not_terminal(conn, cfg, monkeypatch):
    """Same posture as a failed draft: transient, watermark left unset, the
    next wake tries again. Publishing a prep doc with no framework material
    would be worse than publishing it late."""
    _patch_pipeline_ok(monkeypatch)
    from coach_prep_app import select_frameworks
    monkeypatch.setattr(select_frameworks, "select", lambda *a, **k: None)

    assert _run(conn, cfg, monkeypatch) == "selection_failed"
    assert conn.execute("SELECT COUNT(*) FROM watermarks").fetchone()[0] == 0
    assert conn.execute("SELECT status FROM generation_runs").fetchone()[0] == "failed"


def test_invented_ids_are_reported_but_do_not_sink_the_run(conn, cfg, monkeypatch, capsys):
    """An id absent from the catalog is the model reaching for a tool from its
    own training. The known picks still stand, so the run continues -- but it
    must be visible, not silent."""
    _patch_pipeline_ok(monkeypatch, invented=["johari-window"])
    assert _run(conn, cfg, monkeypatch) == "published"
    assert "johari-window" in capsys.readouterr().err


def test_the_published_body_carries_the_confidentiality_footer(conn, cfg, monkeypatch):
    from coach_prep_app import manifest
    _patch_pipeline_ok(monkeypatch)
    published = []
    assert _run(conn, cfg, monkeypatch, publish_capture=published) == "published"
    assert manifest.CONFIDENTIAL_HEADING in published[0]
    assert "Sources this note was built from" in published[0]


def test_the_footer_is_appended_after_the_gates_have_run(conn, cfg, monkeypatch):
    """The footer names real source labels and file paths. If it were appended
    BEFORE the citation gate, those labels would be scanned as if the model
    had written them -- and worse, a model could satisfy the gate by writing
    its own footer. Gates see the model's output and nothing else."""
    _patch_pipeline_ok(monkeypatch)
    from coach_prep_app import gates
    scanned = []
    real_gate = gates.citation_gate
    monkeypatch.setattr(
        gates, "citation_gate",
        lambda text, allowed: scanned.append(text) or real_gate(text, allowed),
    )
    assert _run(conn, cfg, monkeypatch) == "published"
    from coach_prep_app import manifest
    assert manifest.CONFIDENTIAL_HEADING not in scanned[0]


def test_a_gate_failure_publishes_no_footer_and_no_document(conn, cfg, monkeypatch):
    """A leaked draft must not reach Drive carrying an authoritative-looking
    source manifest that lends it credibility."""
    _patch_pipeline_ok(monkeypatch)
    from coach_prep_app import generate
    monkeypatch.setattr(
        generate, "generate_draft",
        lambda b, timeout_s=180, session_minutes=None: "mentions Josh directly [last-meeting-email]",
    )
    published = []
    assert _run(conn, cfg, monkeypatch, publish_capture=published) == "gate_failed"
    assert published == []


# --- session length ---------------------------------------------------------

def test_event_duration_is_read_from_the_calendar(monkeypatch):
    """The prep doc's time boxes come from how long the session actually is."""
    class _Events:
        def list(self, **kwargs):
            return self

        def execute(self):
            return {"items": [{
                "id": "evt1",
                "start": {"dateTime": "2026-08-20T15:00:00+00:00"},
                "end": {"dateTime": "2026-08-20T16:00:00+00:00"},
                "attendees": [{"email": "sean@example.com"}],
            }]}

    class _Service:
        def events(self):
            return _Events()

    from coach_prep_app.config import Config
    events = orchestrator._list_upcoming_events(_Service(), Config(), _NOW)
    assert events[0]["duration_minutes"] == 60


@pytest.mark.parametrize("end,expected", [
    ({"date": "2026-08-21"}, None),                                  # all-day event
    ({"dateTime": "2026-08-20T15:00:00+00:00"}, None),               # zero length
    ({"dateTime": "2026-08-22T15:00:00+00:00"}, None),               # implausibly long
    ({"dateTime": "not a timestamp"}, None),                         # malformed
    ({}, None),                                                       # absent
])
def test_an_unusable_end_time_leaves_the_duration_unset(end, expected):
    """generate falls back to a default session length rather than printing
    '~0 min' or splitting a two-day all-day event into coaching parts."""
    class _Events:
        def list(self, **kwargs):
            return self

        def execute(self):
            return {"items": [{
                "id": "evt1",
                "start": {"dateTime": "2026-08-20T15:00:00+00:00"},
                "end": end,
                "attendees": [],
            }]}

    class _Service:
        def events(self):
            return _Events()

    from coach_prep_app.config import Config
    events = orchestrator._list_upcoming_events(_Service(), Config(), _NOW)
    assert events[0]["duration_minutes"] is expected
