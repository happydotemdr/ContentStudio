# coach-prep-app/tests/test_doc_ingest_reader.py
from __future__ import annotations

import sqlite3

import pytest

from coach_prep_app import config, doc_ingest_reader

# Config's doc_ingest_app_root default resolves relative to coach-prep-app's
# own on-disk location (Task 11), so this correctly points at the sibling
# doc-ingest-app in THIS checkout -- the worktree during development, the
# main checkout after merge -- with no override needed.
config.ensure_doc_ingest_importable(config.Config().doc_ingest_app_root)


@pytest.fixture
def doc_ingest_conn(tmp_path):
    from doc_ingest import db as doc_ingest_db
    conn = doc_ingest_db.init_db(tmp_path / "doc_ingest_test.db")
    yield conn
    conn.close()


def test_get_active_clients_matches_doc_ingest_apps_own_shape(doc_ingest_conn):
    from doc_ingest import clients_db
    clients_db.register_client(
        doc_ingest_conn, slug="sean", display_name="Sean", primary_email="sean@example.com",
        session_outlines_dir="Client Session Outlines/Sean", drive_folder_id="folder1",
    )
    active = doc_ingest_reader.get_active_clients(doc_ingest_conn)
    assert active[0]["slug"] == "sean"


def test_get_latest_tagged_meeting_note_returns_the_most_recent(doc_ingest_conn, tmp_path):
    from coach_prep_app.config import Config
    cfg = Config(converted_root=tmp_path / "converted")
    note_dir = cfg.converted_root / "Client Meet Recordings & Notes"
    note_dir.mkdir(parents=True)

    older = note_dir / "older.gdoc.md"
    older.write_text("---\nversion: 1\n---\n\nolder note body", encoding="utf-8")
    newer = note_dir / "newer.gdoc.md"
    newer.write_text("---\nversion: 1\n---\n\nnewer note body", encoding="utf-8")

    doc_ingest_conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, size_bytes, mtime, "
        "content_hash, first_seen_at, last_seen_at) VALUES "
        "('Client Meet Recordings & Notes/older.gdoc', 'gdoc', 'gdoc_pointer', 1, 'm', 'h', 'n', 'n')"
    )
    older_id = doc_ingest_conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    doc_ingest_conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "conversion_tool, converted_at, gauntlet_passed_at, client) VALUES "
        "(?, 1, 'Client Meet Recordings & Notes/older.gdoc.md', 'current', 'gdoc', "
        "'google-docs-export', '2026-08-01T00:00:00+00:00', 'n', 'sean')",
        (older_id,),
    )
    doc_ingest_conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, size_bytes, mtime, "
        "content_hash, first_seen_at, last_seen_at) VALUES "
        "('Client Meet Recordings & Notes/newer.gdoc', 'gdoc', 'gdoc_pointer', 1, 'm', 'h', 'n', 'n')"
    )
    newer_id = doc_ingest_conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    doc_ingest_conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "conversion_tool, converted_at, gauntlet_passed_at, client) VALUES "
        "(?, 1, 'Client Meet Recordings & Notes/newer.gdoc.md', 'current', 'gdoc', "
        "'google-docs-export', '2026-08-10T00:00:00+00:00', 'n', 'sean')",
        (newer_id,),
    )
    doc_ingest_conn.commit()

    result = doc_ingest_reader.get_latest_tagged_meeting_note(doc_ingest_conn, cfg, "sean")
    assert "newer note body" in result["text"]
    assert result["source_label"] == "last-meeting-note"


def test_get_latest_tagged_meeting_note_returns_placeholder_when_none_found(doc_ingest_conn, tmp_path):
    from coach_prep_app.config import Config
    cfg = Config(converted_root=tmp_path / "converted")
    result = doc_ingest_reader.get_latest_tagged_meeting_note(doc_ingest_conn, cfg, "sean")
    assert result["rel_path"] is None
    assert "No tagged meeting note" in result["text"]


def test_get_program_sources_reads_each_allowlisted_file(tmp_path):
    from coach_prep_app.config import Config
    converted_root = tmp_path / "converted"
    program_dir = converted_root / "Offer & Coaching Framework" / "Current finalized documents"
    program_dir.mkdir(parents=True)
    (program_dir / "Vision & Passion.gdoc.md").write_text(
        "---\nversion: 1\n---\n\nvision content", encoding="utf-8"
    )
    allowlist_path = tmp_path / "program_sources.yaml"
    allowlist_path.write_text(
        "paths:\n  - \"Offer & Coaching Framework/Current finalized documents/Vision & Passion.gdoc.md\"\n",
        encoding="utf-8",
    )
    cfg = Config(converted_root=converted_root, program_sources_path=allowlist_path)
    items = doc_ingest_reader.get_program_sources(cfg)
    assert len(items) == 1
    assert "vision content" in items[0]["text"]
    assert items[0]["source_label"] == "vision-passion"


def test_slugify_source_label_strips_both_suffixes_and_special_characters():
    # "Vision & Passion.gdoc.md" has TWO suffixes (the original extension
    # doc-ingest-app preserves, plus ".md") -- Path.stem only strips one, so
    # a naive Path(...).stem-based label would still carry ".gdoc" and "&",
    # neither of which gates.py's citation regex ([a-z0-9-]+) can match.
    assert doc_ingest_reader.slugify_source_label("Vision & Passion.gdoc.md") == "vision-passion"
    assert doc_ingest_reader.slugify_source_label("F2BU_Module_00_The_Judge.docx.md") == "f2bu-module-00-the-judge"


def test_open_readonly_rejects_writes(tmp_path):
    """open_readonly's whole purpose is enforcing that coach-prep-app can
    never write to doc-ingest-app's database -- pin that at the connection
    level, not just by convention, so a future edit that silently drops
    mode=ro (or otherwise weakens this) fails CI instead of shipping."""
    from doc_ingest import db as doc_ingest_db
    db_path = tmp_path / "doc_ingest_test.db"
    doc_ingest_db.init_db(db_path).close()

    ro_conn = doc_ingest_reader.open_readonly(db_path)
    try:
        # Reads must still work.
        ro_conn.execute("SELECT slug FROM clients").fetchall()
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            ro_conn.execute(
                "INSERT INTO clients (slug, display_name, primary_email, alias_emails_json, "
                "session_outlines_dir, drive_folder_id, status, created_at) "
                "VALUES ('x', 'X', 'x@example.com', '[]', 'x', 'y', 'active', 'z')"
            )
    finally:
        ro_conn.close()
