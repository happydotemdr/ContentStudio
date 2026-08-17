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
