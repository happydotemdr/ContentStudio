# coach-prep-app/tests/test_audit.py
from __future__ import annotations

from coach_prep_app import audit

CLIENTS = [
    {"slug": "sean", "display_name": "Sean", "primary_email": "sean@example.com",
     "alias_emails": [], "session_outlines_dir": "x", "drive_folder_id": "sean-folder"},
    {"slug": "josh", "display_name": "Josh", "primary_email": "josh@example.com",
     "alias_emails": [], "session_outlines_dir": "y", "drive_folder_id": "josh-folder"},
]


class _FakeDocIngestConn:
    def __init__(self, client_by_output_path):
        self._map = client_by_output_path

    def execute(self, sql, params=()):
        if "FROM conversions WHERE output_path" in sql:
            client = self._map.get(params[0])
            return _Row(client)
        if "COUNT(*)" in sql:
            unmatched = sum(1 for v in self._map.values() if v == "unmatched")
            return _Row((unmatched,))
        raise NotImplementedError(sql)


class _Row:
    def __init__(self, value):
        self._value = value

    def fetchone(self):
        if self._value is None:
            return None
        return self._value if isinstance(self._value, tuple) else (self._value,)


SINCE = "2026-08-12T00:00:00+00:00"


def _seed_run(conn, client_slug, status="notified", draft_id="file1", created_at="2026-08-15T00:00:00+00:00"):
    conn.execute(
        "INSERT INTO generation_runs (client_slug, calendar_event_instance_id, meeting_start_at, "
        "status, draft_drive_file_id, created_at, updated_at) VALUES (?, 'evt1', 'n', ?, ?, ?, 'n')",
        (client_slug, status, draft_id, created_at),
    )
    run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    return run_id


def test_mechanical_scan_flags_a_run_whose_input_belongs_to_another_client(conn):
    run_id = _seed_run(conn, "sean")
    conn.execute(
        "INSERT INTO generation_inputs (run_id, source_label, source_kind, reference, captured_at) "
        "VALUES (?, 'last-meeting-note', 'converted_file', 'josh-note.md', 'n')",
        (run_id,),
    )
    conn.commit()
    doc_ingest_conn = _FakeDocIngestConn({"josh-note.md": "josh"})
    problems = audit.mechanical_scan(conn, doc_ingest_conn, SINCE)
    assert len(problems) == 1
    assert problems[0]["expected"] == "sean"
    assert problems[0]["found"] == "josh"


def test_mechanical_scan_is_clean_when_inputs_match(conn):
    run_id = _seed_run(conn, "sean")
    conn.execute(
        "INSERT INTO generation_inputs (run_id, source_label, source_kind, reference, captured_at) "
        "VALUES (?, 'last-meeting-note', 'converted_file', 'sean-note.md', 'n')",
        (run_id,),
    )
    conn.commit()
    doc_ingest_conn = _FakeDocIngestConn({"sean-note.md": "sean"})
    assert audit.mechanical_scan(conn, doc_ingest_conn, SINCE) == []


def test_mechanical_scan_excludes_runs_created_before_since_iso(conn):
    run_id = _seed_run(conn, "sean", created_at="2026-08-01T00:00:00+00:00")
    conn.execute(
        "INSERT INTO generation_inputs (run_id, source_label, source_kind, reference, captured_at) "
        "VALUES (?, 'last-meeting-note', 'converted_file', 'josh-note.md', 'n')",
        (run_id,),
    )
    conn.commit()
    doc_ingest_conn = _FakeDocIngestConn({"josh-note.md": "josh"})
    assert audit.mechanical_scan(conn, doc_ingest_conn, SINCE) == []


class _FakeDriveExec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _FakeDriveFiles:
    def __init__(self, content_by_file_id):
        self._content = content_by_file_id

    def export(self, fileId, mimeType):
        assert mimeType == "text/plain"
        return _FakeDriveExec(self._content[fileId])


class _FakeDriveService:
    def __init__(self, content_by_file_id):
        self._files = _FakeDriveFiles(content_by_file_id)

    def files(self):
        return self._files


def test_content_scan_flags_leaked_content_referencing_another_client(conn, monkeypatch):
    run_id = _seed_run(conn, "sean", draft_id="file1")
    monkeypatch.setattr(audit.doc_ingest_reader, "get_active_clients", lambda doc_ingest_conn: CLIENTS)
    drive_service = _FakeDriveService(
        {"file1": b"Like we discussed with Josh, try the same exercise [last-meeting-email]"}
    )
    problems = audit.content_scan(conn, doc_ingest_conn=None, drive_service=drive_service, since_iso=SINCE)
    assert len(problems) == 1
    assert problems[0]["run_id"] == run_id
    assert problems[0]["leaked"] == ["josh"]


def test_content_scan_is_clean_when_no_leakage(conn, monkeypatch):
    _seed_run(conn, "sean", draft_id="file1")
    monkeypatch.setattr(audit.doc_ingest_reader, "get_active_clients", lambda doc_ingest_conn: CLIENTS)
    drive_service = _FakeDriveService({"file1": b"Sean should reflect on his own goals [last-meeting-email]"})
    assert audit.content_scan(conn, doc_ingest_conn=None, drive_service=drive_service, since_iso=SINCE) == []


def test_content_scan_excludes_runs_created_before_since_iso(conn, monkeypatch):
    _seed_run(conn, "sean", draft_id="file1", created_at="2026-08-01T00:00:00+00:00")
    monkeypatch.setattr(audit.doc_ingest_reader, "get_active_clients", lambda doc_ingest_conn: CLIENTS)
    drive_service = _FakeDriveService(
        {"file1": b"Like we discussed with Josh, try the same exercise [last-meeting-email]"}
    )
    assert audit.content_scan(conn, doc_ingest_conn=None, drive_service=drive_service, since_iso=SINCE) == []


def test_unmatched_count_reads_from_doc_ingest_conn(conn):
    doc_ingest_conn = _FakeDocIngestConn({"a.md": "unmatched", "b.md": "sean", "c.md": "unmatched"})
    assert audit.unmatched_count(doc_ingest_conn) == 2


def test_content_scan_isolates_a_single_runs_fetch_failure(conn, monkeypatch):
    """One deleted/inaccessible draft must not raise out of content_scan
    and kill the whole weekly audit scan -- same per-item isolation
    lesson orchestrator.run_once already applies (Task 21). The failure
    is recorded as its own problem entry; the next run is still scanned."""
    failing_run_id = _seed_run(conn, "sean", draft_id="file-missing")
    leaking_run_id = _seed_run(conn, "sean", draft_id="file-leaks")
    monkeypatch.setattr(audit.doc_ingest_reader, "get_active_clients", lambda doc_ingest_conn: CLIENTS)

    class _FakeDriveFilesMixed:
        def export(self, fileId, mimeType):
            if fileId == "file-missing":
                class _Boom:
                    def execute(self):
                        raise RuntimeError("simulated Drive HttpError: file not found")
                return _Boom()
            return _FakeDriveExec(b"Like we discussed with Josh [last-meeting-email]")

    class _FakeDriveServiceMixed:
        def files(self):
            return _FakeDriveFilesMixed()

    problems = audit.content_scan(conn, doc_ingest_conn=None, drive_service=_FakeDriveServiceMixed(), since_iso=SINCE)
    by_run = {p["run_id"]: p for p in problems}
    assert by_run[failing_run_id]["error"] is not None
    assert by_run[leaking_run_id]["leaked"] == ["josh"]


def test_placement_check_isolates_a_single_runs_lookup_failure(conn, monkeypatch):
    monkeypatch.setattr(audit.doc_ingest_reader, "get_active_clients", lambda doc_ingest_conn: CLIENTS)
    failing_run_id = _seed_run(conn, "sean", status="notified", draft_id="file-missing")
    ok_run_id = _seed_run(conn, "sean", status="notified", draft_id="file-ok")

    class _FakeDriveFilesMixed:
        def get(self, fileId, fields):
            if fileId == "file-missing":
                class _Boom:
                    def execute(self):
                        raise RuntimeError("simulated Drive HttpError: file not found")
                return _Boom()

            class _Ok:
                def execute(self):
                    return {"parents": ["pending-folder"]}
            return _Ok()

    class _FakeDriveServiceMixed:
        def files(self):
            return _FakeDriveFilesMixed()

    results = audit.placement_check(
        conn, doc_ingest_conn=None, drive_service=_FakeDriveServiceMixed(),
        pending_review_folder_id="pending-folder", since_iso=SINCE,
    )
    by_run = {r["run_id"]: r for r in results}
    assert by_run[failing_run_id]["status"] == "placement_check_failed"
    assert by_run[ok_run_id]["status"] == "still_pending_review"


def test_failed_runs_summary_includes_gates_failed_and_failed_and_stale_assembling(conn):
    _seed_run(conn, "sean", status="gates_failed", draft_id=None)
    _seed_run(conn, "sean", status="failed", draft_id=None)
    _seed_run(conn, "sean", status="assembling", draft_id=None)
    _seed_run(conn, "sean", status="notified")  # not a failure -- must be excluded
    rows = audit.failed_runs_summary(conn, SINCE)
    statuses = {r["status"] for r in rows}
    assert statuses == {"gates_failed", "failed", "assembling"}


def test_failed_runs_summary_excludes_runs_created_before_since_iso(conn):
    _seed_run(conn, "sean", status="failed", draft_id=None, created_at="2026-08-01T00:00:00+00:00")
    assert audit.failed_runs_summary(conn, SINCE) == []


def test_render_report_email_reports_clean_when_no_problems():
    report = {
        "mechanical_problems": [], "content_problems": [], "placement": [],
        "unmatched_count": 0, "failed_runs": [],
    }
    subject, text = audit.render_report_email(report)
    assert "clean" in subject.lower()
    assert "No problems" in text


def test_render_report_email_flags_issues_in_the_subject():
    report = {
        "mechanical_problems": [{"run_id": 1, "expected": "sean", "found": "josh", "reference": "x.md"}],
        "content_problems": [], "placement": [], "unmatched_count": 0, "failed_runs": [],
    }
    subject, text = audit.render_report_email(report)
    assert "ISSUES" in subject
    assert "run 1" in text


def test_render_report_email_reports_failed_runs_as_an_issue():
    report = {
        "mechanical_problems": [], "content_problems": [], "placement": [], "unmatched_count": 0,
        "failed_runs": [{
            "run_id": 5, "client_slug": "sean", "status": "gates_failed",
            "failure_reason": "gate_failed: leaked=['josh'] | ALERT EMAIL FAILED", "created_at": "n",
        }],
    }
    subject, text = audit.render_report_email(report)
    assert "ISSUES" in subject
    assert "run 5" in text
    assert "gates_failed" in text
