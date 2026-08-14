"""Parses .gdoc/.gsheet stub JSON (read-only against the input tree) and
queries the Drive API in batches for modifiedTime/mimeType. The stub is
purely a pointer to WHICH document exists -- its own bytes and mtime are
never a content or timestamp source (spec §4 step 3, §9); only the Drive
API's modifiedTime drives change detection for these rows."""
from __future__ import annotations

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
    for source_file_id, rel_path in rows:
        stub = parse_stub(cfg.input_root / rel_path)
        doc_id = stub["doc_id"]
        if doc_id is None:
            continue
        doc_ids.append(doc_id)
        source_by_doc_id[doc_id] = source_file_id
        resource_key_by_doc_id[doc_id] = stub["resource_key"]

    metadata = drive_client.build_batch_metadata(service, doc_ids, cfg)

    updated = 0
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
    return updated
