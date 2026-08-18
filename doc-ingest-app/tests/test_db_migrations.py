from __future__ import annotations

from doc_ingest import db


def test_fresh_db_has_clients_table_and_conversions_client_column(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    try:
        conn.execute(
            "INSERT INTO clients (slug, display_name, primary_email, alias_emails_json, "
            "session_outlines_dir, drive_folder_id, status, created_at) "
            "VALUES ('sean', 'Sean', 'sean@example.com', '[]', "
            "'Client Session Outlines/Sean', 'folder123', 'active', '2026-08-17T00:00:00+00:00')"
        )
        conn.commit()
        row = conn.execute("SELECT slug FROM clients").fetchone()
        assert row[0] == "sean"

        cols = {r[1] for r in conn.execute("PRAGMA table_info(conversions)").fetchall()}
        assert "client" in cols
    finally:
        conn.close()


def test_clients_primary_email_is_unique(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    try:
        conn.execute(
            "INSERT INTO clients (slug, display_name, primary_email, alias_emails_json, "
            "session_outlines_dir, drive_folder_id, status, created_at) "
            "VALUES ('sean', 'Sean', 'sean@example.com', '[]', 'x', 'y', 'active', 'z')"
        )
        conn.commit()
        import sqlite3
        import pytest
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO clients (slug, display_name, primary_email, alias_emails_json, "
                "session_outlines_dir, drive_folder_id, status, created_at) "
                "VALUES ('sean2', 'Sean Two', 'sean@example.com', '[]', 'x', 'y', 'active', 'z')"
            )
    finally:
        conn.close()


def test_apply_migrations_advances_schema_version_without_raising(tmp_db_path):
    """Direct regression test for the apply_migrations bug this task fixes:
    a migration DDL running through executescript inside an explicit
    BEGIN/COMMIT must not raise 'cannot commit - no transaction is active'."""
    conn = db.init_db(tmp_db_path)
    try:
        version = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
        assert version == 2  # SCHEMA_VERSION (1) + this task's one migration to 2
    finally:
        conn.close()
