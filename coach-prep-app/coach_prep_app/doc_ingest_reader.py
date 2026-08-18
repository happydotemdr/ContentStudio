# coach-prep-app/coach_prep_app/doc_ingest_reader.py
"""Read-only queries into doc-ingest-app's doc_ingest.db and converted_root.
coach-prep-app NEVER writes to doc-ingest-app's database -- opened via
SQLite's read-only URI mode as a second layer of enforcement beyond just
"don't call .execute() with a write statement".

Imports from doc_ingest are deferred into each function rather than done at
module-import time. The caller (a cron script, or a test) is responsible for
calling config.ensure_doc_ingest_importable(<the actual doc-ingest-app root
on disk>) first -- Task 11's Config.doc_ingest_app_root default now resolves
relative to coach-prep-app's own location (see that task), so in practice
this "just works" without any override, in this worktree during development
and in the main checkout after merge alike."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path


def open_readonly(db_path: Path) -> sqlite3.Connection:
    # busy_timeout and foreign_keys are connection-level PRAGMAs -- neither
    # requires write access to the database file, so both apply cleanly to a
    # read-only URI connection. Matches this plan's own Global Constraint
    # that every new SQLite connection sets both.
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_active_clients(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT slug, display_name, primary_email, alias_emails_json, "
        "session_outlines_dir, drive_folder_id FROM clients WHERE status = 'active'"
    ).fetchall()
    return [
        {"slug": r[0], "display_name": r[1], "primary_email": r[2],
         "alias_emails": json.loads(r[3]), "session_outlines_dir": r[4], "drive_folder_id": r[5]}
        for r in rows
    ]


def get_latest_tagged_meeting_note(conn: sqlite3.Connection, cfg, client_slug: str) -> dict:
    from doc_ingest import frontmatter as doc_ingest_frontmatter

    row = conn.execute(
        "SELECT c.output_path, c.version_number FROM conversions c "
        "JOIN source_files sf ON sf.id = c.source_file_id "
        "WHERE c.status = 'current' AND c.client = ? "
        "AND sf.rel_path LIKE 'Client Meet Recordings & Notes/%' "
        "ORDER BY c.converted_at DESC LIMIT 1",
        (client_slug,),
    ).fetchone()
    if row is None:
        return {
            "source_label": "last-meeting-note", "rel_path": None, "version": None,
            "text": "No tagged meeting note found for this client.",
        }
    output_path, version = row
    final_path = cfg.converted_root / output_path
    _, body = doc_ingest_frontmatter.parse(final_path.read_text(encoding="utf-8"))
    return {"source_label": "last-meeting-note", "rel_path": output_path, "version": version, "text": body}


def slugify_source_label(filename: str) -> str:
    """A citable source label: lowercase letters, digits, and hyphens only
    -- exactly what gates.py's citation regex (`[a-z0-9-]+`) can match.
    Strips ALL suffixes: doc-ingest-app always names a converted file
    "<original name>.<original extension>.md" (e.g. "Vision & Passion.gdoc.md"),
    and Path.stem only strips the last one, leaving ".gdoc" (and any
    punctuation in the original name, e.g. "&") in a naive label -- both of
    which the citation regex would then silently fail to recognize as part
    of the tag at all, defeating the check."""
    stem = filename.split(".", 1)[0]
    slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return slug or "source"


def get_program_sources(cfg) -> list[dict]:
    from doc_ingest import frontmatter as doc_ingest_frontmatter
    from doc_ingest import program_sources as doc_ingest_program_sources

    paths = doc_ingest_program_sources.load_program_sources(cfg.program_sources_path)
    items = []
    for rel_path in paths:
        final_path = cfg.converted_root / rel_path
        if not final_path.exists():
            continue
        _, body = doc_ingest_frontmatter.parse(final_path.read_text(encoding="utf-8"))
        label = slugify_source_label(Path(rel_path).name)
        items.append({"source_label": label, "rel_path": rel_path, "version": None, "text": body})
    return items
