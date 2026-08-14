"""Bridges scan.py's read-only walk to source_files. A path that was
previously seen and no longer appears is marked 'missing', never deleted
(spec §4 step 2, §9a)."""
from __future__ import annotations

import collections
import datetime as dt
from pathlib import Path

from doc_ingest import db, scan


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sync_source_files(conn, input_root: Path) -> dict:
    now = _now_iso()
    seen_rel_paths: set[str] = set()
    counts: collections.Counter = collections.Counter()

    with db.transaction(conn):
        for entry in scan.walk_source_tree(input_root):
            seen_rel_paths.add(entry.rel_path)
            classification = scan.classify(entry.extension, entry.sniffed_signature)
            counts[classification] += 1
            conn.execute(
                """
                INSERT INTO source_files
                    (rel_path, extension, sniffed_signature, classification,
                     size_bytes, mtime, content_hash, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(rel_path) DO UPDATE SET
                    extension = excluded.extension,
                    sniffed_signature = excluded.sniffed_signature,
                    classification = excluded.classification,
                    size_bytes = excluded.size_bytes,
                    mtime = excluded.mtime,
                    content_hash = excluded.content_hash,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    entry.rel_path, entry.extension, entry.sniffed_signature, classification,
                    entry.size_bytes, entry.mtime_iso, entry.content_hash, now, now,
                ),
            )

        previously_seen = {
            row[0]
            for row in conn.execute(
                "SELECT rel_path FROM source_files WHERE classification != 'missing'"
            ).fetchall()
        }
        newly_missing = previously_seen - seen_rel_paths
        for rel_path in newly_missing:
            conn.execute(
                "UPDATE source_files SET classification = 'missing', last_seen_at = ? WHERE rel_path = ?",
                (now, rel_path),
            )
            counts["missing"] += 1

    return dict(counts)
