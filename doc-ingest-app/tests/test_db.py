from doc_ingest import db


def test_init_db_creates_all_tables(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
        ).fetchall()
    }
    assert {"schema_version", "source_files", "conversion_jobs", "conversions", "events"} <= tables
    version = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
    assert version == 1
    conn.close()


def test_init_db_creates_fts5_virtual_table(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    conn.execute("INSERT INTO conversions_fts (conversion_id, source_rel_path, output_path, body) VALUES (1, 'a/b.pdf', 'a/b.pdf.md', 'hello world')")
    row = conn.execute("SELECT source_rel_path FROM conversions_fts WHERE conversions_fts MATCH 'hello'").fetchone()
    assert row[0] == "a/b.pdf"
    conn.close()


def test_get_connection_uses_wal_and_explicit_isolation(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"
    assert conn.isolation_level is None
    conn.close()


def test_source_files_rel_path_is_unique(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
        "VALUES ('a.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
    )
    conn.commit()
    import sqlite3
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
            "VALUES ('a.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
        )
    conn.close()
