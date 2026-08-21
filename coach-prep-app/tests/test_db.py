from __future__ import annotations

import pytest

from coach_prep_app import db


def test_init_db_creates_all_tables(tmp_path):
    conn = db.init_db(tmp_path / "coach_prep_test.db")
    try:
        tables = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert {"watermarks", "generation_runs", "generation_inputs"} <= tables
    finally:
        conn.close()


def test_transaction_commits_on_success(tmp_path):
    conn = db.init_db(tmp_path / "coach_prep_test.db")
    try:
        with db.transaction(conn):
            conn.execute(
                "INSERT INTO watermarks (client_slug, calendar_event_instance_id, done_at) "
                "VALUES ('sean', 'evt1', 'n')"
            )
        row = conn.execute("SELECT client_slug FROM watermarks").fetchone()
        assert row[0] == "sean"
    finally:
        conn.close()


def test_transaction_rolls_back_on_exception(tmp_path):
    conn = db.init_db(tmp_path / "coach_prep_test.db")
    try:
        with pytest.raises(RuntimeError):
            with db.transaction(conn):
                conn.execute(
                    "INSERT INTO watermarks (client_slug, calendar_event_instance_id, done_at) "
                    "VALUES ('sean', 'evt1', 'n')"
                )
                raise RuntimeError("boom")
        assert conn.execute("SELECT COUNT(*) FROM watermarks").fetchone()[0] == 0
    finally:
        conn.close()


# --- migrations 2 and 3 -----------------------------------------------------

def test_migrations_create_the_framework_catalog_table(tmp_path):
    conn = db.init_db(tmp_path / "coach_prep_test.db")
    try:
        columns = {
            r[1] for r in conn.execute("PRAGMA table_info(framework_catalog)").fetchall()
        }
        assert {
            "id", "title", "framework", "kind", "rel_path", "anchor", "source_version",
            "source_label", "one_line", "use_when_json", "live_ready", "duration_min",
            "curated", "loaded_at",
        } == columns
    finally:
        conn.close()


def test_generation_inputs_accepts_the_two_new_source_kinds(tmp_path):
    """Migration 3 rebuilds the table to widen its CHECK constraint. Without
    it, persisting a selected framework or the book list raises IntegrityError
    and takes the whole run down at the bundle step."""
    conn = db.init_db(tmp_path / "coach_prep_test.db")
    try:
        conn.execute(
            "INSERT INTO generation_runs (client_slug, calendar_event_instance_id, "
            "meeting_start_at, status, created_at, updated_at) "
            "VALUES ('sean', 'evt1', 'm', 'assembling', 'n', 'n')"
        )
        run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for kind in ("gmail_thread", "converted_file", "program_source",
                     "selected_framework", "book_list"):
            conn.execute(
                "INSERT INTO generation_inputs (run_id, source_label, source_kind, "
                "reference, captured_at) VALUES (?, ?, ?, 'r', 'n')",
                (run_id, f"label-{kind}", kind),
            )
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM generation_inputs").fetchone()[0] == 5
    finally:
        conn.close()


def test_generation_inputs_still_rejects_an_unknown_source_kind(tmp_path):
    """The rebuilt CHECK must still be a CHECK -- a migration that widened it
    into nothing would let any typo through silently."""
    import sqlite3
    conn = db.init_db(tmp_path / "coach_prep_test.db")
    try:
        conn.execute(
            "INSERT INTO generation_runs (client_slug, calendar_event_instance_id, "
            "meeting_start_at, status, created_at, updated_at) "
            "VALUES ('sean', 'evt1', 'm', 'assembling', 'n', 'n')"
        )
        run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO generation_inputs (run_id, source_label, source_kind, "
                "reference, captured_at) VALUES (?, 'l', 'not_a_real_kind', 'r', 'n')",
                (run_id,),
            )
    finally:
        conn.close()


def test_migrations_preserve_existing_generation_inputs_rows(tmp_path):
    """Migration 3 DROPs and rebuilds generation_inputs. A live database has
    real audit rows in it -- losing them would erase the record of which
    sources produced which published draft."""
    db_path = tmp_path / "coach_prep_test.db"
    conn = db.init_db(db_path)
    conn.execute(
        "INSERT INTO generation_runs (client_slug, calendar_event_instance_id, "
        "meeting_start_at, status, created_at, updated_at) "
        "VALUES ('sean', 'evt1', 'm', 'published', 'n', 'n')"
    )
    run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO generation_inputs (run_id, source_label, source_kind, reference, "
        "version_or_hash, captured_at) VALUES (?, 'last-meeting-email', 'gmail_thread', "
        "'thread-1', '3', '2026-08-01T00:00:00+00:00')",
        (run_id,),
    )
    conn.commit()
    # Rewind to before migration 3 and re-apply, as an upgrade of a live db does.
    conn.execute("UPDATE schema_version SET version = 2 WHERE id = 1")
    conn.commit()
    db.apply_migrations(conn)
    try:
        row = conn.execute(
            "SELECT run_id, source_label, source_kind, reference, version_or_hash, captured_at "
            "FROM generation_inputs"
        ).fetchall()
        assert row == [(run_id, "last-meeting-email", "gmail_thread", "thread-1", "3",
                        "2026-08-01T00:00:00+00:00")]
    finally:
        conn.close()
