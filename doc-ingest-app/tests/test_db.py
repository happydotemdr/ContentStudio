from doc_ingest import db
import pytest


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
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
            "VALUES ('a.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
        )
    conn.close()


def test_transaction_commits_on_success(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    now = "2026-08-13T00:00:00+00:00"
    with db.transaction(conn):
        conn.execute(
            "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
            "VALUES ('a.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
        )
    row = conn.execute("SELECT rel_path FROM source_files WHERE rel_path = 'a.pdf'").fetchone()
    assert row is not None
    conn.close()


def test_transaction_rolls_back_on_exception(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    now = "2026-08-13T00:00:00+00:00"
    with pytest.raises(ValueError):
        with db.transaction(conn):
            conn.execute(
                "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
                "VALUES ('b.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
            )
            raise ValueError("boom")
    row = conn.execute("SELECT rel_path FROM source_files WHERE rel_path = 'b.pdf'").fetchone()
    assert row is None
    conn.close()


def test_transaction_nests_without_committing_early(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    now = "2026-08-13T00:00:00+00:00"
    with db.transaction(conn):
        conn.execute(
            "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
            "VALUES ('c.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
        )
        with db.transaction(conn):
            conn.execute(
                "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
                "VALUES ('d.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
            )
        # inner block exited but must not have committed independently --
        # verified indirectly: both rows exist after the OUTER block exits.
    rows = conn.execute("SELECT rel_path FROM source_files ORDER BY rel_path").fetchall()
    assert [r[0] for r in rows] == ["c.pdf", "d.pdf"]
    conn.close()


def test_apply_migrations_is_a_noop_on_a_fresh_db(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    db.apply_migrations(conn)  # must not raise
    version = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
    assert version == db.SCHEMA_VERSION
    conn.close()


def test_init_db_calls_apply_migrations(tmp_db_path, monkeypatch):
    calls = []
    monkeypatch.setattr(db, "apply_migrations", lambda conn: calls.append(conn))
    conn = db.init_db(tmp_db_path)
    assert len(calls) == 1
    assert calls[0] is conn


def test_transaction_depth_does_not_leak_across_connections(tmp_path):
    """Verify that _TXN_DEPTH entries are cleaned up when a connection's
    transaction completes, preventing id() reuse hazards where a new
    connection could inherit stale depth from an old one."""
    import gc
    db_path_1 = tmp_path / "db1.db"
    db_path_2 = tmp_path / "db2.db"
    now = "2026-08-13T00:00:00+00:00"

    # Create and use first connection
    conn1 = db.init_db(db_path_1)
    with db.transaction(conn1):
        conn1.execute(
            "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
            "VALUES ('file1.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
        )
    # After transaction completes, depth entry should be cleaned from _TXN_DEPTH
    depth_entries_after_first = len(db._TXN_DEPTH)
    conn1.close()

    # Create and use second connection (may reuse an id() from the first)
    conn2 = db.init_db(db_path_2)
    # The second connection must start its transaction correctly (depth==0 case)
    # by issuing BEGIN, not inheriting a stale depth from conn1
    with db.transaction(conn2):
        conn2.execute(
            "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
            "VALUES ('file2.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
        )
    # Verify data was committed (if it inherited a stale nonzero depth, it would be missing)
    row = conn2.execute("SELECT rel_path FROM source_files WHERE rel_path = 'file2.pdf'").fetchone()
    assert row is not None, "Second connection's transaction was not committed (depth leak hazard)"
    conn2.close()

    # After all transactions complete, _TXN_DEPTH should be cleaned up
    gc.collect()  # Force collection to be safe
    assert len(db._TXN_DEPTH) == 0, "Transaction depth entries were not cleaned up"
