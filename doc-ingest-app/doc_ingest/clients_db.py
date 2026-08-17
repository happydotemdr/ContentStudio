"""CRUD for the client registry. No matching logic here -- see
client_matching.py for that."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3

from doc_ingest import db


class ClientAlreadyExists(ValueError):
    pass


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def register_client(
    conn: sqlite3.Connection,
    *,
    slug: str,
    display_name: str,
    primary_email: str,
    session_outlines_dir: str,
    drive_folder_id: str,
    alias_emails: list[str] | None = None,
) -> None:
    existing = conn.execute("SELECT 1 FROM clients WHERE slug = ?", (slug,)).fetchone()
    if existing is not None:
        raise ClientAlreadyExists(f"client {slug!r} is already registered")

    normalized_email = primary_email.strip().lower()
    try:
        with db.transaction(conn):
            conn.execute(
                """
                INSERT INTO clients
                    (slug, display_name, primary_email, alias_emails_json,
                     session_outlines_dir, drive_folder_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
                """,
                (
                    slug, display_name, normalized_email,
                    json.dumps(alias_emails or []), session_outlines_dir,
                    drive_folder_id, _now_iso(),
                ),
            )
    except sqlite3.IntegrityError as e:
        # The primary_email unique constraint was violated
        raise ClientAlreadyExists(
            f"email {normalized_email!r} is already registered under a different client"
        ) from e


def get_active_clients(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT slug, display_name, primary_email, alias_emails_json, "
        "session_outlines_dir, drive_folder_id FROM clients WHERE status = 'active'"
    ).fetchall()
    return [
        {
            "slug": r[0], "display_name": r[1], "primary_email": r[2],
            "alias_emails": json.loads(r[3]), "session_outlines_dir": r[4],
            "drive_folder_id": r[5],
        }
        for r in rows
    ]


def deactivate_client(conn: sqlite3.Connection, slug: str) -> bool:
    with db.transaction(conn):
        cur = conn.execute(
            "UPDATE clients SET status = 'inactive' WHERE slug = ? AND status = 'active'", (slug,)
        )
        return cur.rowcount > 0
