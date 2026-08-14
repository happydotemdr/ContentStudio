# tests/test_drive_sync.py
import json
from unittest.mock import MagicMock

from doc_ingest import drive_sync, jobs, sync


def _seed_gdoc_stub(input_root, rel_path, doc_id, resource_key="rk1"):
    path = input_root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"doc_id": doc_id, "resource_key": resource_key, "email": "admin@freedom2beu.com"}), encoding="utf-8")


def test_parse_stub_reads_doc_id_and_resource_key(tmp_path):
    stub = tmp_path / "Notes.gdoc"
    stub.write_text(json.dumps({"doc_id": "abc123", "resource_key": "rk1", "email": "x@y.com"}), encoding="utf-8")
    parsed = drive_sync.parse_stub(stub)
    assert parsed == {"doc_id": "abc123", "resource_key": "rk1"}


def test_sync_drive_metadata_updates_source_files(conn, tmp_path, monkeypatch):
    from doc_ingest.config import Config

    input_root = tmp_path / "input"
    _seed_gdoc_stub(input_root, "Notes.gdoc", doc_id="doc-1")
    cfg = Config(input_root=input_root)
    sync.sync_source_files(conn, input_root)

    fake_metadata = {"doc-1": {"id": "doc-1", "modifiedTime": "2026-08-10T00:00:00Z", "mimeType": "application/vnd.google-apps.document"}}
    monkeypatch.setattr("doc_ingest.drive_client.build_batch_metadata", lambda service, doc_ids, cfg_arg: fake_metadata)

    updated = drive_sync.sync_drive_metadata(conn, MagicMock(), cfg)

    assert updated == 1
    row = conn.execute("SELECT doc_id, resource_key, drive_modified_time, drive_mime_type FROM source_files WHERE rel_path = 'Notes.gdoc'").fetchone()
    assert row == ("doc-1", "rk1", "2026-08-10T00:00:00Z", "application/vnd.google-apps.document")


def test_sync_drive_metadata_isolates_a_bad_stub_and_still_syncs_the_rest(conn, tmp_path, monkeypatch):
    """One unreadable stub must not disable the Drive check for the whole
    corpus. Same failure class as resume_unlocked_conversions' per-row
    isolation (Task 15): without a per-row guard the exception escapes
    sync_drive_metadata entirely, run_ingest_cron's outer `except Exception`
    swallows it into a single stderr line, and NONE of the ~100 real
    .gdoc/.gsheet rows get their drive_modified_time updated -- repeating
    every 30 minutes until a human happens to read that line.

    Covers all three per-row failure modes: a stub whose bytes aren't JSON,
    a stub DELETED between the scan and the Drive check (a real race -- the
    cron runs those two steps back to back), and a well-formed stub that
    simply has no doc_id."""
    from doc_ingest.config import Config

    input_root = tmp_path / "input"
    _seed_gdoc_stub(input_root, "A-malformed.gdoc", doc_id="doc-bad")
    _seed_gdoc_stub(input_root, "B-deleted.gdoc", doc_id="doc-gone")
    _seed_gdoc_stub(input_root, "C-no-doc-id.gdoc", doc_id="doc-none")
    _seed_gdoc_stub(input_root, "D-good.gdoc", doc_id="doc-ok")
    cfg = Config(input_root=input_root)
    sync.sync_source_files(conn, input_root)

    # Corrupt/remove AFTER the scan recorded all four rows.
    (input_root / "A-malformed.gdoc").write_text("this is not json at all {{{", encoding="utf-8")
    (input_root / "B-deleted.gdoc").unlink()
    (input_root / "C-no-doc-id.gdoc").write_text(json.dumps({"email": "x@y.com"}), encoding="utf-8")

    seen_doc_ids = {}

    def _fake_batch_metadata(service, doc_ids, cfg_arg):
        seen_doc_ids["value"] = list(doc_ids)
        return {"doc-ok": {"id": "doc-ok", "modifiedTime": "2026-08-12T00:00:00Z", "mimeType": "application/vnd.google-apps.document"}}

    monkeypatch.setattr("doc_ingest.drive_client.build_batch_metadata", _fake_batch_metadata)

    updated = drive_sync.sync_drive_metadata(conn, MagicMock(), cfg)  # must not raise

    assert updated == 1
    # Only the readable stub's doc_id was ever sent to Drive.
    assert seen_doc_ids["value"] == ["doc-ok"]
    good_row = conn.execute(
        "SELECT drive_modified_time FROM source_files WHERE rel_path = 'D-good.gdoc'"
    ).fetchone()
    assert good_row[0] == "2026-08-12T00:00:00Z"

    # The three failures are recorded, not silently dropped.
    failures = conn.execute(
        "SELECT source_file_id FROM events WHERE event_type = 'drive_stub_read_failed'"
    ).fetchall()
    assert len(failures) == 3


def test_regression_enqueue_uses_drive_modified_time_not_local_stub_mtime(conn, tmp_path, monkeypatch):
    """The single correctness issue in this design most worth a standing
    guard (spec §13): a .gdoc stub's own mtime NEVER changes when the real
    document is edited in Drive -- it's a static 176-byte pointer. This
    fixture keeps the stub file completely untouched (same bytes, same
    mtime) across two sync passes and asserts the job still gets enqueued
    the second time, purely because the MOCKED Drive modifiedTime advanced."""
    from doc_ingest.config import Config

    input_root = tmp_path / "input"
    _seed_gdoc_stub(input_root, "Notes.gdoc", doc_id="doc-1")
    stub_path = input_root / "Notes.gdoc"
    stub_bytes_before = stub_path.read_bytes()
    stub_mtime_before = stub_path.stat().st_mtime

    cfg = Config(input_root=input_root)
    sync.sync_source_files(conn, input_root)

    # First Drive check + enqueue: establishes a baseline modifiedTime.
    monkeypatch.setattr(
        "doc_ingest.drive_client.build_batch_metadata",
        lambda service, doc_ids, cfg_arg: {"doc-1": {"id": "doc-1", "modifiedTime": "2026-08-01T00:00:00Z", "mimeType": "application/vnd.google-apps.document"}},
    )
    drive_sync.sync_drive_metadata(conn, MagicMock(), cfg)
    first_created = jobs.enqueue_pending_jobs(conn)
    assert first_created == 1
    job_id = jobs.claim_job(conn, worker_id="w1")
    # Simulate a successful conversion completing, without running the real
    # worker -- this test is about enqueue/Drive-check interaction only.
    now = "2026-08-01T00:05:00+00:00"
    source_id = conn.execute("SELECT id FROM source_files WHERE rel_path = 'Notes.gdoc'").fetchone()[0]
    conn.execute(
        "INSERT INTO conversions (source_file_id, job_id, version_number, output_path, status, source_type, "
        "drive_modified_time_at_conversion, conversion_tool, converted_at) "
        "VALUES (?, ?, 1, 'Notes.gdoc.md', 'current', 'gdoc', '2026-08-01T00:00:00Z', 'google-docs-export', ?)",
        (source_id, job_id, now),
    )
    conn.execute("UPDATE conversion_jobs SET status = 'complete' WHERE id = ?", (job_id,))
    conn.commit()

    # Second pass: re-scan (stub untouched on disk -- proves scan alone
    # cannot detect this change), then a Drive check reporting a NEWER
    # modifiedTime with the exact same local file.
    sync.sync_source_files(conn, input_root)
    assert stub_path.read_bytes() == stub_bytes_before
    assert stub_path.stat().st_mtime == stub_mtime_before

    monkeypatch.setattr(
        "doc_ingest.drive_client.build_batch_metadata",
        lambda service, doc_ids, cfg_arg: {"doc-1": {"id": "doc-1", "modifiedTime": "2026-08-12T00:00:00Z", "mimeType": "application/vnd.google-apps.document"}},
    )
    drive_sync.sync_drive_metadata(conn, MagicMock(), cfg)
    second_created = jobs.enqueue_pending_jobs(conn)

    assert second_created == 1  # enqueued purely because of the mocked Drive modifiedTime


def test_regression_unchanged_drive_modified_time_does_not_reenqueue(conn, tmp_path, monkeypatch):
    """The negative half of the test above -- without it, a version of
    enqueue_pending_jobs that (incorrectly) ALWAYS creates a job for a
    'current'-conversion-less lookup, or that compares the wrong field,
    could make the positive-only test above pass for the wrong reason. This
    proves a Drive check reporting the SAME modifiedTime twice in a row
    does not re-enqueue."""
    from doc_ingest.config import Config

    input_root = tmp_path / "input"
    _seed_gdoc_stub(input_root, "Notes.gdoc", doc_id="doc-1")
    cfg = Config(input_root=input_root)
    sync.sync_source_files(conn, input_root)

    unchanged_metadata = {"doc-1": {"id": "doc-1", "modifiedTime": "2026-08-01T00:00:00Z", "mimeType": "application/vnd.google-apps.document"}}
    monkeypatch.setattr("doc_ingest.drive_client.build_batch_metadata", lambda service, doc_ids, cfg_arg: unchanged_metadata)

    drive_sync.sync_drive_metadata(conn, MagicMock(), cfg)
    first_created = jobs.enqueue_pending_jobs(conn)
    assert first_created == 1
    job_id = jobs.claim_job(conn, worker_id="w1")
    now = "2026-08-01T00:05:00+00:00"
    source_id = conn.execute("SELECT id FROM source_files WHERE rel_path = 'Notes.gdoc'").fetchone()[0]
    conn.execute(
        "INSERT INTO conversions (source_file_id, job_id, version_number, output_path, status, source_type, "
        "drive_modified_time_at_conversion, conversion_tool, converted_at) "
        "VALUES (?, ?, 1, 'Notes.gdoc.md', 'current', 'gdoc', '2026-08-01T00:00:00Z', 'google-docs-export', ?)",
        (source_id, job_id, now),
    )
    conn.execute("UPDATE conversion_jobs SET status = 'complete' WHERE id = ?", (job_id,))
    conn.commit()

    # Re-sync and re-check with the SAME modifiedTime as the conversion already recorded.
    sync.sync_source_files(conn, input_root)
    drive_sync.sync_drive_metadata(conn, MagicMock(), cfg)
    second_created = jobs.enqueue_pending_jobs(conn)

    assert second_created == 0
