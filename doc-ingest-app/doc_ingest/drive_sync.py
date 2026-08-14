"""Parses .gdoc/.gsheet stub JSON (read-only against the input tree) and
queries the Drive API in batches for modifiedTime/mimeType. The stub is
purely a pointer to WHICH document exists -- its own bytes and mtime are
never a content or timestamp source (spec §4 step 3, §9); only the Drive
API's modifiedTime drives change detection for these rows."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from doc_ingest import db, drive_client


def parse_stub(stub_path: Path) -> dict:
    payload = json.loads(stub_path.read_text(encoding="utf-8"))
    return {"doc_id": payload.get("doc_id"), "resource_key": payload.get("resource_key")}


def sync_drive_metadata(conn, service, cfg) -> int:
    rows = conn.execute(
        "SELECT id, rel_path FROM source_files WHERE classification = 'gdoc_pointer'"
    ).fetchall()
    if not rows:
        return 0

    doc_ids: list[str] = []
    source_by_doc_id: dict[str, int] = {}
    resource_key_by_doc_id: dict[str, str | None] = {}
    # Each stub read is isolated: a stub DELETED between the scan and this
    # Drive check (the cron runs those two steps back to back, so this is a
    # real race), a zero-byte or non-JSON stub, or one with no doc_id must
    # cost only that row. Without this guard the exception escapes the whole
    # function, run_ingest_cron's outer `except Exception` swallows it into
    # one stderr line, and NONE of the ~100 real .gdoc/.gsheet rows get their
    # drive_modified_time updated -- every wake, until a human notices. Same
    # failure class as worker.resume_unlocked_conversions' per-row isolation.
    stub_failures: list[tuple[int, str]] = []
    for source_file_id, rel_path in rows:
        try:
            stub = parse_stub(cfg.input_root / rel_path)
            doc_id = stub["doc_id"]
        except Exception as exc:
            stub_failures.append((source_file_id, f"{type(exc).__name__}: {exc}"))
            continue
        if doc_id is None:
            stub_failures.append((source_file_id, "stub contains no doc_id"))
            continue
        doc_ids.append(doc_id)
        source_by_doc_id[doc_id] = source_file_id
        resource_key_by_doc_id[doc_id] = stub["resource_key"]

    metadata = drive_client.build_batch_metadata(service, doc_ids, cfg)

    updated = 0
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    with db.transaction(conn):
        for doc_id, info in metadata.items():
            conn.execute(
                "UPDATE source_files SET doc_id = ?, resource_key = ?, drive_modified_time = ?, "
                "drive_mime_type = ? WHERE id = ?",
                (
                    doc_id, resource_key_by_doc_id.get(doc_id), info.get("modifiedTime"),
                    info.get("mimeType"), source_by_doc_id[doc_id],
                ),
            )
            updated += 1
        # Recorded rather than silently dropped, mirroring the events rows
        # gauntlet.run_gate2 and worker.resume_unlocked_conversions already
        # write -- a queryable row outlives the one stderr line the caller
        # would otherwise emit for a whole failed wake.
        for source_file_id, error in stub_failures:
            conn.execute(
                "INSERT INTO events (ts, event_type, source_file_id, details_json) VALUES (?, ?, ?, ?)",
                (now, "drive_stub_read_failed", source_file_id, json.dumps({"error": error})),
            )
    return updated
