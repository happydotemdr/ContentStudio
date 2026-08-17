# Freedom2BeU Coach-Prep Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate Ryan's pre-session coach-prep doc: detect an upcoming client meeting, assemble a single-client input bundle, generate a draft via an isolated `claude -p` subprocess, publish it to a shared review folder in Drive, and email Brian a link — with mechanical client-isolation guarantees, full traceability, and a weekly audit.

**Architecture:** Two phases. Phase 1 extends `doc-ingest-app` with a client registry and deterministic (non-LLM) client tagging of the Freedom2BeU corpus, storing the tag as a DB column (never rewriting an already-locked converted file). Phase 2 is a new sibling app, `coach-prep-app`, with its own Windows Task Scheduler cron (4-hourly), its own OAuth credentials, and a pipeline that never auto-publishes to a client-facing location — a human moving the draft out of a shared review folder is the approval step.

**Tech Stack:** Python 3.14, sqlite3 (stdlib), PyYAML, google-api-python-client / google-auth-oauthlib (Calendar/Gmail/Drive), requests (Resend), pytest.

## Global Constraints

- `doc-ingest-app`'s existing `client_secret.json`/`token.json` (Drive/Docs/Sheets, read-only) is never modified, widened, or re-consented as part of this plan.
- Every new Google API credential is additive and independently scoped: `doc-ingest-app` gets a second, calendar-only pair; `coach-prep-app` gets its own pair (`calendar.readonly`, `gmail.readonly`, `drive.file`).
- No code path may auto-register a client. Registration is always an explicit `register_client.py add` invocation.
- No already-converted, already-locked `.md` file under `Freedom2BeU/converted/` is ever rewritten. The `client` tag is a DB column (`conversions.client`), not a frontmatter rewrite, for any file that predates this plan's rollout. New conversions may still bake `client:` into frontmatter at write time, before the file is locked.
- Phase 2 never creates or writes into a client's real Drive folder. It only ever writes into one shared "Pending Review" folder. Moving a draft into a client's folder is a manual, human action.
- All new SQLite access follows the existing per-app pattern: one connection per caller, WAL mode, `busy_timeout=5000`, `foreign_keys=ON`, and an explicit `db.transaction(conn)` boundary around every multi-statement write.
- Tests follow each app's existing `conftest.py` guards: any test that makes a real subprocess or network call must carry `@pytest.mark.allow_subprocess` / `@pytest.mark.allow_network` with a docstring justification, or (preferred) mock the call.
- Run doc-ingest-app's suite from `doc-ingest-app/` (`python -m pytest`); run coach-prep-app's suite from `coach-prep-app/` once it exists, for the same rootdir reason documented in this repo's `CLAUDE.md`.

---

## Part 1 — `doc-ingest-app`: Client Identity Foundation

### Task 1: `clients` table + `conversions.client` column

**Files:**
- Modify: `doc-ingest-app/doc_ingest/db.py` (`_MIGRATIONS` list only — never edit `_SCHEMA` or `SCHEMA_VERSION`)
- Test: `doc-ingest-app/tests/test_db_migrations.py`

**Interfaces:**
- Produces: a `clients` table (`slug` PK, `display_name`, `primary_email`, `alias_emails_json`, `session_outlines_dir`, `drive_folder_id`, `status`, `created_at`) and a nullable `conversions.client TEXT` column, both reachable via any `conn` returned by `db.init_db`/`db.get_connection`.

- [ ] **Step 1: Write the failing test**

```python
# doc-ingest-app/tests/test_db_migrations.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `doc-ingest-app/`): `python -m pytest tests/test_db_migrations.py -v`
Expected: FAIL — `sqlite3.OperationalError: no such table: clients`

- [ ] **Step 3: Add the migration**

In `doc_ingest/db.py`, replace the empty migrations list:

```python
_MIGRATIONS: list[tuple[int, str]] = [
    (2, """
        CREATE TABLE IF NOT EXISTS clients (
            slug                  TEXT PRIMARY KEY,
            display_name          TEXT NOT NULL,
            primary_email         TEXT NOT NULL,
            alias_emails_json     TEXT NOT NULL DEFAULT '[]',
            session_outlines_dir  TEXT NOT NULL,
            drive_folder_id       TEXT NOT NULL,
            status                TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
            created_at            TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_primary_email ON clients(primary_email);
        ALTER TABLE conversions ADD COLUMN client TEXT;
        CREATE INDEX IF NOT EXISTS idx_conversions_client ON conversions(client);
    """),
]
```

Leave `_SCHEMA` and the module-level `SCHEMA_VERSION = 1` untouched — `apply_migrations` runs this migration on both a brand-new db (which bootstraps at version 1 via `_SCHEMA`, then advances to 2) and an existing db already at version 1.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db_migrations.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/db.py doc-ingest-app/tests/test_db_migrations.py
git commit -m "feat(doc-ingest): add clients table and conversions.client column"
```

### Task 2: Client registry CRUD

**Files:**
- Create: `doc-ingest-app/doc_ingest/clients_db.py`
- Test: `doc-ingest-app/tests/test_clients_db.py`

**Interfaces:**
- Consumes: `doc_ingest.db.transaction(conn)` (Task 1's schema)
- Produces: `register_client(conn, *, slug, display_name, primary_email, session_outlines_dir, drive_folder_id, alias_emails=None) -> None`, `get_active_clients(conn) -> list[dict]` (each dict: `slug`, `display_name`, `primary_email`, `alias_emails`, `session_outlines_dir`, `drive_folder_id`), `deactivate_client(conn, slug) -> bool`, exception `ClientAlreadyExists(ValueError)`. This is the shape every later task (matcher, tagging, CLI, coach-prep-app's reader) relies on.

- [ ] **Step 1: Write the failing test**

```python
# doc-ingest-app/tests/test_clients_db.py
from __future__ import annotations

import pytest

from doc_ingest import clients_db


def test_register_and_list_active_clients(conn):
    clients_db.register_client(
        conn, slug="sean", display_name="Sean", primary_email="Sean.Carl.Tinsley@gmail.com",
        session_outlines_dir="Client Session Outlines/Sean", drive_folder_id="folder123",
    )
    active = clients_db.get_active_clients(conn)
    assert len(active) == 1
    assert active[0]["slug"] == "sean"
    assert active[0]["primary_email"] == "sean.carl.tinsley@gmail.com"
    assert active[0]["alias_emails"] == []


def test_register_client_with_aliases(conn):
    clients_db.register_client(
        conn, slug="joanne", display_name="Joanne", primary_email="jnnbryant77@gmail.com",
        session_outlines_dir="Client Session Outlines/Joanne", drive_folder_id="folder456",
        alias_emails=["joanne.bryant@schwab.com"],
    )
    active = clients_db.get_active_clients(conn)
    assert active[0]["alias_emails"] == ["joanne.bryant@schwab.com"]


def test_register_duplicate_slug_raises(conn):
    clients_db.register_client(
        conn, slug="sean", display_name="Sean", primary_email="sean@example.com",
        session_outlines_dir="x", drive_folder_id="y",
    )
    with pytest.raises(clients_db.ClientAlreadyExists):
        clients_db.register_client(
            conn, slug="sean", display_name="Sean Again", primary_email="other@example.com",
            session_outlines_dir="x", drive_folder_id="y",
        )


def test_deactivate_client_removes_it_from_active_list(conn):
    clients_db.register_client(
        conn, slug="sean", display_name="Sean", primary_email="sean@example.com",
        session_outlines_dir="x", drive_folder_id="y",
    )
    assert clients_db.deactivate_client(conn, "sean") is True
    assert clients_db.get_active_clients(conn) == []
    assert clients_db.deactivate_client(conn, "sean") is False  # already inactive
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_clients_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doc_ingest.clients_db'`

- [ ] **Step 3: Write the implementation**

```python
# doc-ingest-app/doc_ingest/clients_db.py
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
    with db.transaction(conn):
        conn.execute(
            """
            INSERT INTO clients
                (slug, display_name, primary_email, alias_emails_json,
                 session_outlines_dir, drive_folder_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
            """,
            (
                slug, display_name, primary_email.strip().lower(),
                json.dumps(alias_emails or []), session_outlines_dir,
                drive_folder_id, _now_iso(),
            ),
        )


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_clients_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/clients_db.py doc-ingest-app/tests/test_clients_db.py
git commit -m "feat(doc-ingest): add client registry CRUD"
```

### Task 3: `register_client.py` CLI

**Files:**
- Create: `doc-ingest-app/scripts/register_client.py`
- Test: `doc-ingest-app/tests/test_register_client.py`

**Interfaces:**
- Consumes: `doc_ingest.clients_db.register_client/get_active_clients/deactivate_client` (Task 2), `doc_ingest.db.init_db` (existing)
- Produces: `main(argv: list[str] | None = None, db_path: Path | None = None) -> int` — the `db_path` override exists solely for testability; the real cron/CLI path defaults to `doc-ingest-app/doc_ingest.db`.

- [ ] **Step 1: Write the failing test**

```python
# doc-ingest-app/tests/test_register_client.py
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import register_client  # noqa: E402


def test_add_then_list(tmp_db_path, capsys):
    rc = register_client.main(
        ["add", "--slug", "sean", "--display-name", "Sean", "--email", "sean@example.com",
         "--session-outlines-dir", "Client Session Outlines/Sean", "--drive-folder-id", "folder1"],
        db_path=tmp_db_path,
    )
    assert rc == 0
    capsys.readouterr()

    rc = register_client.main(["list"], db_path=tmp_db_path)
    assert rc == 0
    out = capsys.readouterr().out
    assert "sean" in out
    assert "sean@example.com" in out


def test_add_with_alias_emails(tmp_db_path, capsys):
    register_client.main(
        ["add", "--slug", "joanne", "--display-name", "Joanne", "--email", "jnnbryant77@gmail.com",
         "--session-outlines-dir", "Client Session Outlines/Joanne", "--drive-folder-id", "folder2",
         "--alias-email", "joanne.bryant@schwab.com"],
        db_path=tmp_db_path,
    )
    from doc_ingest import clients_db, db as db_mod
    conn = db_mod.init_db(tmp_db_path)
    try:
        active = clients_db.get_active_clients(conn)
    finally:
        conn.close()
    assert active[0]["alias_emails"] == ["joanne.bryant@schwab.com"]


def test_deactivate(tmp_db_path, capsys):
    register_client.main(
        ["add", "--slug", "sean", "--display-name", "Sean", "--email", "sean@example.com",
         "--session-outlines-dir", "x", "--drive-folder-id", "y"],
        db_path=tmp_db_path,
    )
    rc = register_client.main(["deactivate", "--slug", "sean"], db_path=tmp_db_path)
    assert rc == 0
    out = capsys.readouterr().out
    assert "deactivated" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_register_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'register_client'`

- [ ] **Step 3: Write the implementation**

```python
# doc-ingest-app/scripts/register_client.py
"""One-time-per-client registration CLI.

Usage:
  python scripts/register_client.py add --slug sean --display-name "Sean" \
      --email sean.carl.tinsley@gmail.com \
      --session-outlines-dir "Client Session Outlines/Sean" \
      --drive-folder-id <id> [--alias-email other@example.com ...]
  python scripts/register_client.py list
  python scripts/register_client.py deactivate --slug sean
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from doc_ingest import clients_db, db


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add")
    add.add_argument("--slug", required=True)
    add.add_argument("--display-name", required=True)
    add.add_argument("--email", required=True)
    add.add_argument("--session-outlines-dir", required=True)
    add.add_argument("--drive-folder-id", required=True)
    add.add_argument("--alias-email", action="append", default=[])

    sub.add_parser("list")

    deact = sub.add_parser("deactivate")
    deact.add_argument("--slug", required=True)

    return ap


def main(argv: list[str] | None = None, db_path: Path | None = None) -> int:
    args = build_parser().parse_args(argv)
    resolved_db_path = db_path or (HERE.parent / "doc_ingest.db")
    conn = db.init_db(resolved_db_path)
    try:
        if args.command == "add":
            clients_db.register_client(
                conn, slug=args.slug, display_name=args.display_name,
                primary_email=args.email, session_outlines_dir=args.session_outlines_dir,
                drive_folder_id=args.drive_folder_id, alias_emails=args.alias_email,
            )
            print(f"registered client {args.slug!r}")
        elif args.command == "list":
            for c in clients_db.get_active_clients(conn):
                print(f"{c['slug']}: {c['display_name']} <{c['primary_email']}> -> {c['session_outlines_dir']}")
        elif args.command == "deactivate":
            ok = clients_db.deactivate_client(conn, args.slug)
            print("deactivated" if ok else f"no active client {args.slug!r} found")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_register_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/scripts/register_client.py doc-ingest-app/tests/test_register_client.py
git commit -m "feat(doc-ingest): add register_client CLI"
```

### Task 4: Pure attendee matcher

**Files:**
- Create: `doc-ingest-app/doc_ingest/client_matching.py`
- Test: `doc-ingest-app/tests/test_client_matching.py`

**Interfaces:**
- Consumes: nothing (pure function, no DB/network — matches `naming.py`'s style)
- Produces: `UNMATCHED = "unmatched"`, `match_attendees_to_client(attendee_emails: list[str], clients: list[dict], coach_email: str) -> str` — `clients` is `clients_db.get_active_clients`'s return shape. This is the shared logic Task 7 (doc-ingest-app's historical classifier) and coach-prep-app's live classifier (Part 3) both call, each having fetched `attendee_emails` with its own credentials.

- [ ] **Step 1: Write the failing test**

```python
# doc-ingest-app/tests/test_client_matching.py
from __future__ import annotations

from doc_ingest import client_matching

SEAN = {"slug": "sean", "primary_email": "sean.carl.tinsley@gmail.com", "alias_emails": []}
JOANNE = {
    "slug": "joanne", "primary_email": "jnnbryant77@gmail.com",
    "alias_emails": ["joanne.bryant@schwab.com"],
}
CLIENTS = [SEAN, JOANNE]
COACH_EMAIL = "admin@freedom2beu.com"


def test_matches_a_single_registered_client():
    result = client_matching.match_attendees_to_client(
        ["sean.carl.tinsley@gmail.com", "admin@freedom2beu.com"], CLIENTS, COACH_EMAIL
    )
    assert result == "sean"


def test_matches_via_an_alias_email():
    result = client_matching.match_attendees_to_client(
        ["joanne.bryant@schwab.com", "admin@freedom2beu.com"], CLIENTS, COACH_EMAIL
    )
    assert result == "joanne"


def test_costa_rica_case_no_registered_client_is_unmatched():
    result = client_matching.match_attendees_to_client(
        ["jake.m.lockwood@gmail.com", "admin@freedom2beu.com"], CLIENTS, COACH_EMAIL
    )
    assert result == client_matching.UNMATCHED


def test_chris_griswold_case_no_registered_client_is_unmatched():
    result = client_matching.match_attendees_to_client(
        ["cgris68@gmail.com", "admin@freedom2beu.com"], CLIENTS, COACH_EMAIL
    )
    assert result == client_matching.UNMATCHED


def test_investor_meeting_case_empty_attendee_list_is_unmatched():
    result = client_matching.match_attendees_to_client([], CLIENTS, COACH_EMAIL)
    assert result == client_matching.UNMATCHED


def test_two_distinct_clients_on_one_event_is_unmatched():
    result = client_matching.match_attendees_to_client(
        ["sean.carl.tinsley@gmail.com", "jnnbryant77@gmail.com"], CLIENTS, COACH_EMAIL
    )
    assert result == client_matching.UNMATCHED


def test_coach_own_address_alone_is_unmatched_never_a_client():
    result = client_matching.match_attendees_to_client(["admin@freedom2beu.com"], CLIENTS, COACH_EMAIL)
    assert result == client_matching.UNMATCHED


def test_matching_is_case_insensitive():
    result = client_matching.match_attendees_to_client(
        ["Sean.Carl.Tinsley@GMAIL.com"], CLIENTS, COACH_EMAIL
    )
    assert result == "sean"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_client_matching.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doc_ingest.client_matching'`

- [ ] **Step 3: Write the implementation**

```python
# doc-ingest-app/doc_ingest/client_matching.py
"""Pure attendee-list -> client-slug matching. No DB, no network -- given an
already-fetched attendee list and an already-loaded client roster, decide
which single client (if any) it belongs to."""
from __future__ import annotations

UNMATCHED = "unmatched"


def match_attendees_to_client(attendee_emails: list[str], clients: list[dict], coach_email: str) -> str:
    coach_lower = coach_email.strip().lower()
    candidates = {e.strip().lower() for e in attendee_emails if e.strip().lower() != coach_lower}
    if not candidates:
        return UNMATCHED

    matched_slugs = set()
    for client in clients:
        client_emails = {client["primary_email"].lower(), *(a.lower() for a in client["alias_emails"])}
        if candidates & client_emails:
            matched_slugs.add(client["slug"])

    if len(matched_slugs) == 1:
        return matched_slugs.pop()
    return UNMATCHED
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_client_matching.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/client_matching.py doc-ingest-app/tests/test_client_matching.py
git commit -m "feat(doc-ingest): add pure attendee-to-client matcher"
```

### Task 5: `eid` extraction and decoding

**Files:**
- Create: `doc-ingest-app/doc_ingest/eid.py`
- Test: `doc-ingest-app/tests/test_eid.py`

**Interfaces:**
- Produces: `extract_eid(markdown_body: str) -> str | None`, `decode_eid(eid: str) -> tuple[str, str]` returning `(event_id, calendar_id)`, raising `ValueError` on an unparseable eid.

- [ ] **Step 1: Write the failing test**

The eid and its decoded form below are a real value from the Freedom2BeU corpus (Sean's Aug 12 coaching-session note), decoded and verified with `base64.b64decode` during design.

```python
# doc-ingest-app/tests/test_eid.py
from __future__ import annotations

import pytest

from doc_ingest import eid as eid_mod

REAL_EID = (
    "Mjg3cjI4M2hsaXF2dDhkdXZnYTdrODdzcnNfMjAyNjA4MTFUMTQwMDAwWiBhZG1pbkBmcmVlZG9tMmJldS5jb20"
)
REAL_EVENT_ID = "287r283hliqvt8duvga7k87srs_20260811T140000Z"
REAL_CALENDAR_ID = "admin@freedom2beu.com"

BODY_WITH_EID = (
    "Attachments [Sean and Ryan Coaching Session]"
    f"(https://calendar.google.com/calendar/event?eid={REAL_EID}) "
    "[Notes by Gemini](https://docs.google.com/document/d/abc/edit)"
)

BODY_WITHOUT_EID = "# Notes\n\nInvestor Operator Meeting\n\nNo attachments line here."


def test_extract_eid_finds_the_real_corpus_eid():
    assert eid_mod.extract_eid(BODY_WITH_EID) == REAL_EID


def test_extract_eid_returns_none_when_absent():
    assert eid_mod.extract_eid(BODY_WITHOUT_EID) is None


def test_decode_eid_matches_the_verified_real_value():
    event_id, calendar_id = eid_mod.decode_eid(REAL_EID)
    assert event_id == REAL_EVENT_ID
    assert calendar_id == REAL_CALENDAR_ID


def test_decode_eid_rejects_garbage():
    with pytest.raises(ValueError):
        eid_mod.decode_eid("not-valid-base64-at-all-!!!")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_eid.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doc_ingest.eid'`

- [ ] **Step 3: Write the implementation**

```python
# doc-ingest-app/doc_ingest/eid.py
"""Decodes a Google Calendar `eid` URL parameter into (event_id, calendar_id).
Format confirmed by decoding a real Freedom2BeU corpus eid during design:
base64 of "{event_id} {calendar_id}". Standard alphabet was what the real
sample used; urlsafe is tried as a fallback since Google's exact encoding
choice is undocumented."""
from __future__ import annotations

import base64
import binascii
import re

_EID_RE = re.compile(r"calendar\.google\.com/calendar/event\?eid=([A-Za-z0-9+/=_-]+)")


def extract_eid(markdown_body: str) -> str | None:
    match = _EID_RE.search(markdown_body)
    return match.group(1) if match else None


def decode_eid(eid: str) -> tuple[str, str]:
    padded = eid + "=" * (-len(eid) % 4)
    try:
        decoded = base64.b64decode(padded, validate=False).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        try:
            decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise ValueError(f"could not base64-decode eid {eid!r}") from exc
    event_id, sep, calendar_id = decoded.partition(" ")
    if not sep or not calendar_id:
        raise ValueError(f"unexpected eid decode result: {decoded!r}")
    return event_id, calendar_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_eid.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/eid.py doc-ingest-app/tests/test_eid.py
git commit -m "feat(doc-ingest): decode Google Calendar eid URL parameters"
```

### Task 6: doc-ingest-app's own calendar-only OAuth credential

**Files:**
- Create: `doc-ingest-app/doc_ingest/calendar_client.py`
- Modify: `doc-ingest-app/.gitignore` (add `calendar_client_secret.json`, `calendar_token.json` — check they aren't already covered by an existing broad pattern first)
- Modify: `doc-ingest-app/SETUP.md` (new section)
- Test: `doc-ingest-app/tests/test_calendar_client.py`

**Interfaces:**
- Produces: `SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]`, `get_credentials(token_path, client_secret_path) -> Credentials`, `build_default_service(cfg=None)`, `get_event_attendees(service, event_id: str, calendar_id: str) -> list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# doc-ingest-app/tests/test_calendar_client.py
from __future__ import annotations

from doc_ingest import calendar_client


class _FakeExecute:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _FakeEvents:
    def __init__(self, result):
        self._result = result

    def get(self, calendarId, eventId):
        assert calendarId == "admin@freedom2beu.com"
        assert eventId == "287r283hliqvt8duvga7k87srs_20260811T140000Z"
        return _FakeExecute(self._result)


class _FakeService:
    def __init__(self, result):
        self._result = result

    def events(self):
        return _FakeEvents(self._result)


def test_get_event_attendees_extracts_emails():
    service = _FakeService({
        "attendees": [
            {"email": "sean.carl.tinsley@gmail.com"},
            {"email": "admin@freedom2beu.com"},
            {"displayName": "no email here"},
        ]
    })
    attendees = calendar_client.get_event_attendees(
        service, "287r283hliqvt8duvga7k87srs_20260811T140000Z", "admin@freedom2beu.com"
    )
    assert attendees == ["sean.carl.tinsley@gmail.com", "admin@freedom2beu.com"]


def test_get_event_attendees_handles_no_attendees_key():
    service = _FakeService({})
    attendees = calendar_client.get_event_attendees(
        service, "287r283hliqvt8duvga7k87srs_20260811T140000Z", "admin@freedom2beu.com"
    )
    assert attendees == []


def test_build_default_service_raises_clearly_with_no_cached_token(tmp_path, monkeypatch):
    import doc_ingest.calendar_client as cc
    monkeypatch.setattr(cc.Path, "resolve", cc.Path.resolve)  # no-op, keeps real behavior
    # Point app_root resolution at an empty tmp dir with no calendar_token.json.
    monkeypatch.setattr(
        cc, "build_default_service",
        lambda cfg=None: (_ for _ in ()).throw(
            RuntimeError("doc-ingest-app has no cached Calendar token")
        ),
    )
    import pytest
    with pytest.raises(RuntimeError, match="Calendar token"):
        cc.build_default_service()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_calendar_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doc_ingest.calendar_client'`

- [ ] **Step 3: Write the implementation**

```python
# doc-ingest-app/doc_ingest/calendar_client.py
"""Calendar API access for doc-ingest-app's meeting-note classifier. Uses its
OWN credential pair (calendar_client_secret.json / calendar_token.json),
scoped to calendar.readonly only -- deliberately separate from
client_secret.json/token.json (Drive/Docs/Sheets), so adding this can never
invalidate the credential the running ingest cron already depends on.
Mirrors drive_client.py's shape; see that module and SETUP.md for the
one-time interactive consent this cron-unfriendly flow requires."""
from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def get_credentials(token_path: Path, client_secret_path: Path) -> Credentials:
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def build_default_service(cfg=None):
    from googleapiclient.discovery import build

    app_root = Path(__file__).resolve().parents[1]
    token_path = app_root / "calendar_token.json"
    if not token_path.exists():
        raise RuntimeError(
            "doc-ingest-app has no cached Calendar token -- run the one-time "
            "interactive consent documented in SETUP.md's Calendar section "
            "before the classifier can resolve meeting-note attendees"
        )
    creds = get_credentials(token_path, app_root / "calendar_client_secret.json")
    return build("calendar", "v3", credentials=creds)


def get_event_attendees(service, event_id: str, calendar_id: str) -> list[str]:
    event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
    return [a["email"] for a in event.get("attendees", []) if "email" in a]
```

Simplify the third test in Step 1 once the module exists — it was written to fail cleanly before the module exists; once `calendar_client.py` is real, replace that monkeypatch test with a direct one:

```python
def test_build_default_service_raises_clearly_with_no_cached_token(monkeypatch, tmp_path):
    from doc_ingest import calendar_client as cc
    monkeypatch.setattr(cc, "__file__", str(tmp_path / "doc_ingest" / "calendar_client.py"))
    # app_root resolves from __file__'s parents[1]; tmp_path has no calendar_token.json.
    import pytest
    with pytest.raises(RuntimeError, match="Calendar token"):
        cc.build_default_service()
```

Add to `doc-ingest-app/.gitignore`:

```
calendar_client_secret.json
calendar_token.json
```

Add to `doc-ingest-app/SETUP.md` a new "## 4. Calendar API (for meeting-note client tagging)" section mirroring the existing Drive section's structure: create/reuse the Cloud project, enable the Calendar API, add scope `calendar.readonly`, create a **second** Desktop OAuth client (or reuse the existing one and just request the new scope in a separate consent — either way the resulting token MUST be saved as `calendar_token.json`, never overwriting `token.json`), and run the one-time consent:

```bash
cd doc-ingest-app
python -c "from pathlib import Path; from doc_ingest.calendar_client import get_credentials; get_credentials(Path('calendar_token.json'), Path('calendar_client_secret.json'))"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_calendar_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/calendar_client.py doc-ingest-app/tests/test_calendar_client.py doc-ingest-app/.gitignore doc-ingest-app/SETUP.md
git commit -m "feat(doc-ingest): add separate calendar-only OAuth credential and client"
```

### Task 7: Classification orchestration

**Files:**
- Create: `doc-ingest-app/doc_ingest/client_tagging.py`
- Test: `doc-ingest-app/tests/test_client_tagging.py`

**Interfaces:**
- Consumes: `clients_db.get_active_clients` (Task 2), `client_matching.match_attendees_to_client`/`UNMATCHED` (Task 4), `eid.extract_eid`/`decode_eid` (Task 5), `calendar_client.get_event_attendees` (Task 6)
- Produces: `TagResult` (`.frontmatter_extra: dict`, `.event_type: str | None`, `.event_details: dict`), `classify(conn, rel_path: str, markdown_body: str, calendar_service_factory) -> TagResult`, constants `SESSION_OUTLINES_PREFIX`, `MEETING_NOTES_PREFIX`, `COACH_EMAIL`. `calendar_service_factory` is a zero-arg callable returning a Calendar service (lazy — only called when a meeting note actually needs classifying, mirroring `worker.py`'s existing `drive_service_factory` pattern). Task 8 wires this into `worker.py`; Task 10's backfill script and coach-prep-app's live classifier (Part 3) both call `classify`/its collaborators too.

- [ ] **Step 1: Write the failing test**

```python
# doc-ingest-app/tests/test_client_tagging.py
from __future__ import annotations

from doc_ingest import client_matching, client_tagging, clients_db

SEAN_EID = (
    "Mjg3cjI4M2hsaXF2dDhkdXZnYTdrODdzcnNfMjAyNjA4MTFUMTQwMDAwWiBhZG1pbkBmcmVlZG9tMmJldS5jb20"
)


def _register_sean(conn):
    clients_db.register_client(
        conn, slug="sean", display_name="Sean", primary_email="sean.carl.tinsley@gmail.com",
        session_outlines_dir="Client Session Outlines/Sean", drive_folder_id="folder1",
    )


def test_session_outlines_folder_matches_by_folder_name(conn):
    _register_sean(conn)
    result = client_tagging.classify(
        conn, "Client Session Outlines/Sean/Some Doc.gdoc", "irrelevant body", lambda: None
    )
    assert result.frontmatter_extra == {"client": "sean"}
    assert result.event_type is None


def test_session_outlines_folder_with_no_registered_client_is_flagged(conn):
    result = client_tagging.classify(
        conn, "Client Session Outlines/Unknown Person/Doc.gdoc", "irrelevant body", lambda: None
    )
    assert result.frontmatter_extra == {"client": client_matching.UNMATCHED}
    assert result.event_type == "client_outline_folder_unregistered"


def test_meeting_note_resolves_via_eid_and_calendar_lookup(conn):
    _register_sean(conn)
    body = (
        f"Attachments [x](https://calendar.google.com/calendar/event?eid={SEAN_EID}) "
    )

    class FakeService:
        def events(self):
            class E:
                def get(self, calendarId, eventId):
                    class Exec:
                        def execute(self):
                            return {"attendees": [
                                {"email": "sean.carl.tinsley@gmail.com"},
                                {"email": "admin@freedom2beu.com"},
                            ]}
                    return Exec()
            return E()

    result = client_tagging.classify(conn, "Client Meet Recordings & Notes/Sean.gdoc", body, lambda: FakeService())
    assert result.frontmatter_extra == {"client": "sean"}
    assert result.event_type is None


def test_meeting_note_with_no_eid_is_unmatched(conn):
    result = client_tagging.classify(
        conn, "Client Meet Recordings & Notes/Investor Operator Meeting.gdoc",
        "# Notes\n\nno eid here", lambda: None,
    )
    assert result.frontmatter_extra == {"client": client_matching.UNMATCHED}
    assert result.event_type == "client_meeting_note_no_eid"


def test_meeting_note_whose_attendees_match_no_client_is_unmatched(conn):
    _register_sean(conn)
    body = f"Attachments [x](https://calendar.google.com/calendar/event?eid={SEAN_EID})"

    class FakeService:
        def events(self):
            class E:
                def get(self, calendarId, eventId):
                    class Exec:
                        def execute(self):
                            return {"attendees": [{"email": "jake.m.lockwood@gmail.com"}]}
                    return Exec()
            return E()

    result = client_tagging.classify(conn, "Client Meet Recordings & Notes/x.gdoc", body, lambda: FakeService())
    assert result.frontmatter_extra == {"client": client_matching.UNMATCHED}
    assert result.event_type == "client_meeting_note_unmatched"


def test_meeting_note_whose_calendar_lookup_fails_is_unmatched(conn):
    body = f"Attachments [x](https://calendar.google.com/calendar/event?eid={SEAN_EID})"

    def failing_factory():
        raise RuntimeError("no cached Calendar token")

    result = client_tagging.classify(conn, "Client Meet Recordings & Notes/x.gdoc", body, failing_factory)
    assert result.frontmatter_extra == {"client": client_matching.UNMATCHED}
    assert result.event_type == "client_meeting_note_lookup_failed"


def test_non_client_file_gets_no_tag_at_all(conn):
    result = client_tagging.classify(
        conn, "Offer & Coaching Framework/Current finalized documents/Vision.gdoc", "body", lambda: None
    )
    assert result.frontmatter_extra == {}
    assert result.event_type is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_client_tagging.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doc_ingest.client_tagging'`

- [ ] **Step 3: Write the implementation**

```python
# doc-ingest-app/doc_ingest/client_tagging.py
"""Per-file client classification, called from worker.py right before
frontmatter is assembled (and by scripts/backfill_client_tags.py for
already-converted files). Deterministic, never LLM-guessed."""
from __future__ import annotations

from doc_ingest import calendar_client, client_matching, clients_db, eid as eid_mod

COACH_EMAIL = "admin@freedom2beu.com"
SESSION_OUTLINES_PREFIX = "Client Session Outlines/"
MEETING_NOTES_PREFIX = "Client Meet Recordings & Notes/"


class TagResult:
    def __init__(self, frontmatter_extra: dict, event_type: str | None = None, event_details: dict | None = None):
        self.frontmatter_extra = frontmatter_extra
        self.event_type = event_type
        self.event_details = event_details or {}


def classify(conn, rel_path: str, markdown_body: str, calendar_service_factory) -> TagResult:
    if rel_path.startswith(SESSION_OUTLINES_PREFIX):
        return _classify_outline_folder(conn, rel_path)
    if rel_path.startswith(MEETING_NOTES_PREFIX):
        return _classify_meeting_note(conn, markdown_body, calendar_service_factory)
    return TagResult({})


def _classify_outline_folder(conn, rel_path: str) -> TagResult:
    remainder = rel_path[len(SESSION_OUTLINES_PREFIX):]
    folder_name = remainder.split("/", 1)[0]
    for client in clients_db.get_active_clients(conn):
        if client["display_name"] == folder_name:
            return TagResult({"client": client["slug"]})
    return TagResult(
        {"client": client_matching.UNMATCHED},
        event_type="client_outline_folder_unregistered",
        event_details={"folder_name": folder_name, "rel_path": rel_path},
    )


def _classify_meeting_note(conn, markdown_body: str, calendar_service_factory) -> TagResult:
    eid = eid_mod.extract_eid(markdown_body)
    if eid is None:
        return TagResult({"client": client_matching.UNMATCHED}, event_type="client_meeting_note_no_eid")

    try:
        event_id, calendar_id = eid_mod.decode_eid(eid)
        service = calendar_service_factory()
        attendees = calendar_client.get_event_attendees(service, event_id, calendar_id)
    except Exception as exc:
        return TagResult(
            {"client": client_matching.UNMATCHED},
            event_type="client_meeting_note_lookup_failed",
            event_details={"error": str(exc)},
        )

    clients = clients_db.get_active_clients(conn)
    slug = client_matching.match_attendees_to_client(attendees, clients, COACH_EMAIL)
    if slug == client_matching.UNMATCHED:
        return TagResult(
            {"client": client_matching.UNMATCHED},
            event_type="client_meeting_note_unmatched",
            event_details={"attendees": attendees},
        )
    return TagResult({"client": slug})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_client_tagging.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/client_tagging.py doc-ingest-app/tests/test_client_tagging.py
git commit -m "feat(doc-ingest): add per-file client classification orchestration"
```

### Task 8: Wire client tagging into `worker.py`

**Files:**
- Modify: `doc-ingest-app/doc_ingest/worker.py` (import line ~26; inside `process_job`, after `frontmatter_extras = _frontmatter_extras(independent_metadata)`, ~line 265; the `conversions` INSERT, ~lines 302-320)
- Test: `doc-ingest-app/tests/test_worker.py` (add new tests; existing tests keep passing unchanged)

**Interfaces:**
- Consumes: `client_tagging.classify` (Task 7), `calendar_client.build_default_service` (Task 6)
- Produces: `process_job(conn, job_id, cfg, worker_id, drive_service_factory=None, calendar_service_factory=None)` — new optional parameter, same lazy-factory pattern as the existing `drive_service_factory`. A converted file under either client folder now gets a `client` frontmatter field AND a `conversions.client` DB column value from the same classification call; a file outside those folders gets neither, unchanged from today.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_worker.py` (reuses that file's existing `conn`/`tmp_path` fixtures and `worker.process_job` call shape — see `test_process_job_happy_path_writes_commits_locks_and_indexes` for the staging pattern this mirrors):

```python
@pytest.mark.allow_subprocess  # process_job's write path reaches lock.apply_readonly_lock's real icacls call
def test_process_job_tags_a_session_outlines_file_with_its_client(conn, tmp_path):
    from doc_ingest import clients_db, worker
    clients_db.register_client(
        conn, slug="sean", display_name="Sean", primary_email="sean.carl.tinsley@gmail.com",
        session_outlines_dir="Client Session Outlines/Sean", drive_folder_id="folder1",
    )
    input_root = tmp_path / "input"
    (input_root / "Client Session Outlines" / "Sean").mkdir(parents=True)
    source = input_root / "Client Session Outlines" / "Sean" / "note.txt"
    source.write_text("some session content", encoding="utf-8")

    from doc_ingest.config import Config
    cfg = Config(input_root=input_root, output_root=tmp_path / "output")

    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, size_bytes, mtime, "
        "content_hash, first_seen_at, last_seen_at) VALUES "
        "('Client Session Outlines/Sean/note.txt', 'txt', 'convertible', 20, 'm', 'h', 'n', 'n')"
    )
    source_file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO conversion_jobs (source_file_id, status, created_at) VALUES (?, 'pending', 'n')",
        (source_file_id,),
    )
    job_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()

    worker.process_job(conn, job_id, cfg, "w1", calendar_service_factory=lambda: None)

    row = conn.execute("SELECT client FROM conversions WHERE source_file_id = ?", (source_file_id,)).fetchone()
    assert row[0] == "sean"

    output_files = list((cfg.converted_root / "Client Session Outlines" / "Sean").glob("*.md"))
    assert len(output_files) == 1
    content = output_files[0].read_text(encoding="utf-8")
    assert "client: sean" in content


@pytest.mark.allow_subprocess  # process_job's write path reaches lock.apply_readonly_lock's real icacls call
def test_process_job_does_not_tag_a_non_client_file(conn, tmp_path):
    from doc_ingest import worker
    input_root = tmp_path / "input"
    (input_root / "Offer & Coaching Framework" / "Current finalized documents").mkdir(parents=True)
    source = input_root / "Offer & Coaching Framework" / "Current finalized documents" / "Vision.txt"
    source.write_text("vision content", encoding="utf-8")

    from doc_ingest.config import Config
    cfg = Config(input_root=input_root, output_root=tmp_path / "output")

    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, size_bytes, mtime, "
        "content_hash, first_seen_at, last_seen_at) VALUES "
        "('Offer & Coaching Framework/Current finalized documents/Vision.txt', 'txt', 'convertible', "
        "14, 'm', 'h', 'n', 'n')"
    )
    source_file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO conversion_jobs (source_file_id, status, created_at) VALUES (?, 'pending', 'n')",
        (source_file_id,),
    )
    job_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()

    worker.process_job(conn, job_id, cfg, "w1", calendar_service_factory=lambda: None)

    row = conn.execute("SELECT client FROM conversions WHERE source_file_id = ?", (source_file_id,)).fetchone()
    assert row[0] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_worker.py -k "tags_a_session_outlines or does_not_tag_a_non_client" -v`
Expected: FAIL — `TypeError: process_job() got an unexpected keyword argument 'calendar_service_factory'`

- [ ] **Step 3: Modify `worker.py`**

Change the import line:

```python
from doc_ingest import calendar_client, client_tagging, convert, db, drive_client, frontmatter, gauntlet, jobs, lock, metadata_readers, naming
```

Change `process_job`'s signature:

```python
def process_job(conn, job_id: int, cfg, worker_id: str, drive_service_factory=None, calendar_service_factory=None) -> None:
```

Immediately after `frontmatter_extras = _frontmatter_extras(independent_metadata)`, insert:

```python
            tag_result = client_tagging.classify(
                conn, rel_path, conversion_result.markdown_body,
                calendar_service_factory or calendar_client.build_default_service,
            )
            frontmatter_extras.update(tag_result.frontmatter_extra)
            client_value = tag_result.frontmatter_extra.get("client")
            if tag_result.event_type:
                with db.transaction(conn):
                    conn.execute(
                        "INSERT INTO events (ts, event_type, source_file_id, details_json) VALUES (?, ?, ?, ?)",
                        (_now_iso(), tag_result.event_type, source_file_id, json.dumps(tag_result.event_details)),
                    )
```

Extend the `conversions` INSERT to carry `client`:

```python
            conn.execute(
                """
                INSERT INTO conversions
                    (source_file_id, job_id, version_number, output_path, status, source_type,
                     source_hash_at_conversion, drive_modified_time_at_conversion, conversion_tool,
                     converted_at, gauntlet_passed_at, client,
                     page_count, word_count, sheet_count, row_count_total)
                VALUES (?, ?, ?, ?, 'current', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_file_id, job_id, version, dest_rel_path, source_type,
                    source_hash, drive_modified_time_at_conversion, conversion_result.tool,
                    _now_iso(), _now_iso(), client_value,
                    frontmatter_extras.get("page_count"),
                    frontmatter_extras.get("word_count"),
                    frontmatter_extras.get("sheet_count"),
                    frontmatter_extras.get("row_count_total"),
                ),
            )
```

- [ ] **Step 4: Run tests to verify they pass, and nothing else broke**

Run: `python -m pytest tests/test_worker.py -v`
Expected: PASS — the two new tests, and every pre-existing test in this file (which never passes `calendar_service_factory`, so the default `calendar_client.build_default_service` lazy-binds but is never actually called for non-client-folder fixtures used elsewhere in this file).

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/worker.py doc-ingest-app/tests/test_worker.py
git commit -m "feat(doc-ingest): tag client files during conversion"
```

### Task 9: `program_sources` allowlist + drift check

**Files:**
- Create: `doc-ingest-app/doc_ingest/program_sources.py`
- Create: `doc-ingest-app/program_sources.yaml` (seed data)
- Modify: `doc-ingest-app/doc_ingest/worker.py` (drift-check call site, right after `dest_rel_path` is known from `gauntlet.run_gate2`)
- Test: `doc-ingest-app/tests/test_program_sources.py`, extend `tests/test_worker.py`

**Interfaces:**
- Produces: `WATCHED_PREFIXES`, `load_program_sources(path: Path) -> list[str]`, `check_drift(dest_rel_path: str, allowlist: list[str]) -> str | None`. Task 13 (coach-prep-app's `doc_ingest_reader.py`) calls `load_program_sources` too, via its cross-app import of `doc_ingest`.

- [ ] **Step 1: Write the failing test**

```python
# doc-ingest-app/tests/test_program_sources.py
from __future__ import annotations

from doc_ingest import program_sources


def test_load_program_sources_reads_the_paths_list(tmp_path):
    yaml_path = tmp_path / "program_sources.yaml"
    yaml_path.write_text(
        "paths:\n  - \"Offer & Coaching Framework/Current finalized documents/Vision & Passion.gdoc.md\"\n",
        encoding="utf-8",
    )
    paths = program_sources.load_program_sources(yaml_path)
    assert paths == ["Offer & Coaching Framework/Current finalized documents/Vision & Passion.gdoc.md"]


def test_load_program_sources_returns_empty_list_when_file_missing(tmp_path):
    assert program_sources.load_program_sources(tmp_path / "does-not-exist.yaml") == []


def test_check_drift_flags_a_watched_file_not_in_the_allowlist():
    allowlist = ["Offer & Coaching Framework/Current finalized documents/Vision & Passion.gdoc.md"]
    warning = program_sources.check_drift(
        "Offer & Coaching Framework/Current finalized documents/New Doc.gdoc.md", allowlist
    )
    assert warning is not None
    assert "New Doc.gdoc.md" in warning


def test_check_drift_is_silent_for_an_allowlisted_file():
    allowlist = ["Offer & Coaching Framework/Current finalized documents/Vision & Passion.gdoc.md"]
    assert program_sources.check_drift(allowlist[0], allowlist) is None


def test_check_drift_is_silent_outside_watched_prefixes():
    allowlist: list[str] = []
    assert program_sources.check_drift("Client Session Outlines/Sean/note.gdoc.md", allowlist) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_program_sources.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doc_ingest.program_sources'`

- [ ] **Step 3: Write the implementation**

```python
# doc-ingest-app/doc_ingest/program_sources.py
"""Loads the human-maintained allowlist of exact converted-file paths Phase 2
generation may treat as current program/framework/PQ grounding. Deliberately
NOT derived from `status: current`, which duplicate/archived files in the
real corpus have already been shown to falsify (design spec, 'Freshness')."""
from __future__ import annotations

from pathlib import Path

import yaml

WATCHED_PREFIXES = (
    "Offer & Coaching Framework/Current finalized documents/",
    "Frameworks to consider/Sabatoures/",
)


def load_program_sources(path: Path) -> list[str]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(raw.get("paths", []))


def check_drift(dest_rel_path: str, allowlist: list[str]) -> str | None:
    for prefix in WATCHED_PREFIXES:
        if dest_rel_path.startswith(prefix) and dest_rel_path not in allowlist:
            return f"{dest_rel_path} is under a watched folder but not in program_sources.yaml"
    return None
```

Seed `doc-ingest-app/program_sources.yaml`:

```yaml
# Human-maintained allowlist of exact converted-file paths Phase 2 generation
# may use as global (non-client) program/framework/PQ grounding. Update this
# whenever a program doc is superseded or a new one is finalized -- do not
# rely on status:current, which duplicate/archived files have already shown
# to be an unreliable freshness signal (see design spec).
paths:
  - "Offer & Coaching Framework/Current finalized documents/Executive_Coaching_Offer_Architecture_v2.pdf.md"
  - "Offer & Coaching Framework/Current finalized documents/F2BU_12Week_Accelerator_Infographic.pdf.md"
  - "Offer & Coaching Framework/Current finalized documents/Four Content Pillars.gdoc.md"
  - "Offer & Coaching Framework/Current finalized documents/Freedom2BeU_Program_Structure_V3.gdoc.md"
  - "Offer & Coaching Framework/Current finalized documents/Freedom2BeU_Question_Bank.docx.md"
  - "Offer & Coaching Framework/Current finalized documents/Freedom2BeU_Webinar_Guide_V2.gdoc.md"
  - "Offer & Coaching Framework/Current finalized documents/Journal what is radical agency .pdf.md"
  - "Offer & Coaching Framework/Current finalized documents/Vision & Passion.gdoc.md"
  # Two near-duplicate Judge files exist in the corpus; this picks the
  # non-"(1)" filename as canonical. CONFIRM with Brian/Ryan before relying
  # on this in production -- see Task 24.
  - "Frameworks to consider/Sabatoures/F2BU_Module_00_The_Judge.docx.md"
```

In `worker.py`, right after `gate2_result, dest_rel_path = gauntlet.run_gate2(...)` succeeds, add the drift check (log-only, never fails the job). `worker.py` already has `from pathlib import Path` at module scope, so the only new import needed is `program_sources`, added to the top-level import line alongside the others from Task 8:

```python
from doc_ingest import calendar_client, client_tagging, convert, db, drive_client, frontmatter, gauntlet, jobs, lock, metadata_readers, naming, program_sources
```

Call site, immediately after `gate2_result, dest_rel_path = gauntlet.run_gate2(...)`:

```python
            app_root = Path(__file__).resolve().parents[1]
            allowlist = program_sources.load_program_sources(app_root / "program_sources.yaml")
            drift_warning = program_sources.check_drift(dest_rel_path, allowlist)
            if drift_warning:
                with db.transaction(conn):
                    conn.execute(
                        "INSERT INTO events (ts, event_type, source_file_id, details_json) VALUES (?, ?, ?, ?)",
                        (_now_iso(), "program_source_drift", source_file_id, json.dumps({"warning": drift_warning})),
                    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_program_sources.py -v`
Expected: PASS

Also add one worker-level regression test to `tests/test_worker.py`:

```python
@pytest.mark.allow_subprocess  # process_job's write path reaches lock.apply_readonly_lock's real icacls call
def test_process_job_logs_drift_for_an_unlisted_program_doc(conn, tmp_path):
    from doc_ingest import worker
    input_root = tmp_path / "input"
    (input_root / "Offer & Coaching Framework" / "Current finalized documents").mkdir(parents=True)
    source = input_root / "Offer & Coaching Framework" / "Current finalized documents" / "Brand New Doc.txt"
    source.write_text("new doc content", encoding="utf-8")

    from doc_ingest.config import Config
    cfg = Config(input_root=input_root, output_root=tmp_path / "output")

    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, size_bytes, mtime, "
        "content_hash, first_seen_at, last_seen_at) VALUES "
        "('Offer & Coaching Framework/Current finalized documents/Brand New Doc.txt', 'txt', "
        "'convertible', 16, 'm', 'h', 'n', 'n')"
    )
    source_file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO conversion_jobs (source_file_id, status, created_at) VALUES (?, 'pending', 'n')",
        (source_file_id,),
    )
    job_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()

    worker.process_job(conn, job_id, cfg, "w1", calendar_service_factory=lambda: None)

    event = conn.execute(
        "SELECT event_type FROM events WHERE source_file_id = ? AND event_type = 'program_source_drift'",
        (source_file_id,),
    ).fetchone()
    assert event is not None
```

Run: `python -m pytest tests/test_worker.py -v`
Expected: PASS (this fixture's file is genuinely absent from the seeded `program_sources.yaml`, so drift is expected to fire)

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/program_sources.py doc-ingest-app/program_sources.yaml doc-ingest-app/doc_ingest/worker.py doc-ingest-app/tests/test_program_sources.py doc-ingest-app/tests/test_worker.py
git commit -m "feat(doc-ingest): add program_sources allowlist with drift detection"
```

### Task 10: Backfill script for existing meeting-note files

**Files:**
- Create: `doc-ingest-app/scripts/backfill_client_tags.py`
- Test: `doc-ingest-app/tests/test_backfill_client_tags.py`

**Interfaces:**
- Consumes: `client_tagging.classify` (Task 7), `frontmatter.parse` (existing)
- Produces: `build_report(conn, cfg, calendar_service_factory) -> list[dict]` (each dict: `conversion_id`, `rel_path`, `current_client`, `classified_client`, `event_type`), `apply_report(conn, report: list[dict]) -> int`. **DB-only** — never rewrites a converted file, because `lock.py`'s read-only lock is deliberately one-directional (see `lock.py`'s module docstring: "NOT idempotent... a second icacls call would itself be denied — that's the point"). The `client` tag for already-converted files lives solely in `conversions.client`.

- [ ] **Step 1: Write the failing test**

```python
# doc-ingest-app/tests/test_backfill_client_tags.py
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import backfill_client_tags  # noqa: E402


def _seed_conversion(conn, cfg, rel_path: str, output_path: str, body_with_fm: str, current_client=None):
    final_path = cfg.converted_root / output_path
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(body_with_fm, encoding="utf-8")
    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, size_bytes, mtime, "
        "content_hash, first_seen_at, last_seen_at) VALUES (?, 'gdoc', 'gdoc_pointer', 10, 'm', 'h', 'n', 'n')",
        (rel_path,),
    )
    source_file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "conversion_tool, converted_at, gauntlet_passed_at, client) "
        "VALUES (?, 1, ?, 'current', 'gdoc', 'google-docs-export', 'n', 'n', ?)",
        (source_file_id, output_path, current_client),
    )
    conn.commit()


def test_build_report_classifies_a_session_outlines_file(conn, tmp_path):
    from doc_ingest import clients_db
    from doc_ingest.config import Config
    clients_db.register_client(
        conn, slug="sean", display_name="Sean", primary_email="sean@example.com",
        session_outlines_dir="Client Session Outlines/Sean", drive_folder_id="folder1",
    )
    cfg = Config(output_root=tmp_path / "output")
    _seed_conversion(
        conn, cfg, "Client Session Outlines/Sean/note.gdoc",
        "Client Session Outlines/Sean/note.gdoc.md",
        "---\nversion: 1\n---\n\nsome content",
    )
    report = backfill_client_tags.build_report(conn, cfg, lambda: None)
    assert len(report) == 1
    assert report[0]["classified_client"] == "sean"
    assert report[0]["current_client"] is None


def test_build_report_skips_non_client_files(conn, tmp_path):
    from doc_ingest.config import Config
    cfg = Config(output_root=tmp_path / "output")
    _seed_conversion(
        conn, cfg, "Offer & Coaching Framework/Current finalized documents/Vision.gdoc",
        "Offer & Coaching Framework/Current finalized documents/Vision.gdoc.md",
        "---\nversion: 1\n---\n\nvision content",
    )
    report = backfill_client_tags.build_report(conn, cfg, lambda: None)
    assert report == []


def test_apply_report_updates_only_changed_rows(conn, tmp_path):
    from doc_ingest import clients_db
    from doc_ingest.config import Config
    clients_db.register_client(
        conn, slug="sean", display_name="Sean", primary_email="sean@example.com",
        session_outlines_dir="Client Session Outlines/Sean", drive_folder_id="folder1",
    )
    cfg = Config(output_root=tmp_path / "output")
    _seed_conversion(
        conn, cfg, "Client Session Outlines/Sean/note.gdoc",
        "Client Session Outlines/Sean/note.gdoc.md", "---\nversion: 1\n---\n\ncontent",
        current_client=None,
    )
    conversion_id = conn.execute("SELECT id FROM conversions").fetchone()[0]

    report = backfill_client_tags.build_report(conn, cfg, lambda: None)
    updated = backfill_client_tags.apply_report(conn, report)
    assert updated == 1

    row = conn.execute("SELECT client FROM conversions WHERE id = ?", (conversion_id,)).fetchone()
    assert row[0] == "sean"

    # Re-running with nothing changed applies zero updates.
    report2 = backfill_client_tags.build_report(conn, cfg, lambda: None)
    assert backfill_client_tags.apply_report(conn, report2) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_backfill_client_tags.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backfill_client_tags'`

- [ ] **Step 3: Write the implementation**

```python
# doc-ingest-app/scripts/backfill_client_tags.py
"""One-time (re-runnable) backfill of `client` tags onto already-converted
meeting-note and session-outline files. DB-ONLY -- never rewrites a
converted file, because lock.py's read-only lock is deliberately
one-directional (see that module's docstring). Re-running is always safe: it
re-derives the tag from the exact same classifier worker.py now runs on
every new/changed file, so backfill and ongoing tagging can never diverge.

Usage:
  python scripts/backfill_client_tags.py --dry-run
  python scripts/backfill_client_tags.py --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from doc_ingest import calendar_client, client_tagging, config, db, frontmatter


def _candidate_conversions(conn):
    return conn.execute(
        "SELECT c.id, c.output_path, c.client, sf.rel_path FROM conversions c "
        "JOIN source_files sf ON sf.id = c.source_file_id WHERE c.status = 'current'"
    ).fetchall()


def build_report(conn, cfg, calendar_service_factory) -> list[dict]:
    report = []
    for conversion_id, output_path, current_client, rel_path in _candidate_conversions(conn):
        if not (rel_path.startswith(client_tagging.SESSION_OUTLINES_PREFIX)
                or rel_path.startswith(client_tagging.MEETING_NOTES_PREFIX)):
            continue
        final_path = cfg.converted_root / output_path
        _, body = frontmatter.parse(final_path.read_text(encoding="utf-8"))
        tag_result = client_tagging.classify(conn, rel_path, body, calendar_service_factory)
        report.append({
            "conversion_id": conversion_id,
            "rel_path": rel_path,
            "current_client": current_client,
            "classified_client": tag_result.frontmatter_extra.get("client"),
            "event_type": tag_result.event_type,
        })
    return report


def apply_report(conn, report: list[dict]) -> int:
    updated = 0
    with db.transaction(conn):
        for row in report:
            new_client = row["classified_client"]
            if new_client is None or new_client == row["current_client"]:
                continue
            conn.execute("UPDATE conversions SET client = ? WHERE id = ?", (new_client, row["conversion_id"]))
            updated += 1
    return updated


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    cfg = config.load_config()
    conn = db.init_db(HERE.parent / "doc_ingest.db")
    try:
        report = build_report(conn, cfg, calendar_client.build_default_service)
        for row in report:
            suffix = f" ({row['event_type']})" if row["event_type"] else ""
            print(f"{row['rel_path']}: {row['current_client']!r} -> {row['classified_client']!r}{suffix}")
        unmatched = sum(1 for r in report if r["classified_client"] == "unmatched")
        print(f"\n{len(report)} client-scoped file(s) scanned, {unmatched} unmatched")
        if args.apply:
            updated = apply_report(conn, report)
            print(f"applied {updated} tag update(s)")
        else:
            print("dry run -- re-run with --apply to write these tags")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_backfill_client_tags.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/scripts/backfill_client_tags.py doc-ingest-app/tests/test_backfill_client_tags.py
git commit -m "feat(doc-ingest): add DB-only client-tag backfill script"
```

---

## Part 2 — `coach-prep-app`: Scaffold & Credentials

### Task 11: App scaffold — config, schema, packaging, test harness

**Files:**
- Create: `coach-prep-app/coach_prep_app/__init__.py` (empty)
- Create: `coach-prep-app/coach_prep_app/config.py`
- Create: `coach-prep-app/coach_prep_app/db.py`
- Create: `coach-prep-app/setup.py`, `coach-prep-app/requirements.txt`, `coach-prep-app/requirements-dev.txt`, `coach-prep-app/pytest.ini`
- Create: `coach-prep-app/tests/__init__.py`, `coach-prep-app/tests/conftest.py`
- Create: `coach-prep-app/.gitignore`
- Test: `coach-prep-app/tests/test_config.py`, `coach-prep-app/tests/test_db.py`

**Interfaces:**
- Produces: `Config` dataclass (fields listed below) and `load_config(path: Path | None = None) -> Config` (env var > YAML > default, mirroring `doc_ingest/config.py`'s `_coerce` precedence exactly); `ensure_doc_ingest_importable(doc_ingest_app_root: Path) -> None` (idempotent `sys.path` insert so `from doc_ingest import ...` works from coach-prep-app); `db.init_db(db_path) -> sqlite3.Connection`, `db.get_connection`, `db.transaction(conn)` (same shape as `doc_ingest/db.py`). Every later coach-prep-app task imports `coach_prep_app.config`/`coach_prep_app.db`.

- [ ] **Step 1: Write the failing tests**

```python
# coach-prep-app/tests/test_config.py
from __future__ import annotations

import os
from pathlib import Path

import pytest

from coach_prep_app import config


def test_default_config_has_expected_fields():
    cfg = config.Config()
    assert cfg.coach_email == "admin@freedom2beu.com"
    assert cfg.lookahead_hours == 48
    assert cfg.daily_ready_hour_local == 7
    assert cfg.timezone_name == "America/Chicago"
    assert cfg.last_meeting_email_staleness_days == 30


def test_load_config_from_yaml_overrides_default(tmp_path):
    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text("lookahead_hours: 72\n", encoding="utf-8")
    cfg = config.load_config(yaml_path)
    assert cfg.lookahead_hours == 72


def test_load_config_env_var_overrides_yaml(tmp_path, monkeypatch):
    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text("lookahead_hours: 72\n", encoding="utf-8")
    monkeypatch.setenv("COACH_PREP_LOOKAHEAD_HOURS", "10")
    cfg = config.load_config(yaml_path)
    assert cfg.lookahead_hours == 10


def test_load_config_rejects_unknown_yaml_key(tmp_path):
    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text("not_a_real_field: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown config key"):
        config.load_config(yaml_path)


def test_ensure_doc_ingest_importable_adds_to_sys_path(tmp_path):
    import sys
    fake_root = tmp_path / "doc-ingest-app"
    fake_root.mkdir()
    config.ensure_doc_ingest_importable(fake_root)
    assert str(fake_root) in sys.path
    # Idempotent -- calling twice does not duplicate the entry.
    config.ensure_doc_ingest_importable(fake_root)
    assert sys.path.count(str(fake_root)) == 1
```

```python
# coach-prep-app/tests/test_db.py
from __future__ import annotations

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
```

(`test_transaction_rolls_back_on_exception` needs `import pytest` at the top of `test_db.py` alongside the `db` import.)

- [ ] **Step 2: Run tests to verify they fail**

Run (from `coach-prep-app/`, which does not exist yet as a runnable pytest root until this step's implementation lands): `python -m pytest tests/test_config.py tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coach_prep_app'`

- [ ] **Step 3: Write the implementation**

```python
# coach-prep-app/coach_prep_app/config.py
"""All coach-prep-app tunables in one place. Precedence: env var > YAML file
> default -- mirrors doc_ingest/config.py's pattern exactly."""
from __future__ import annotations

import dataclasses
import os
import sys
import typing
from pathlib import Path

import yaml

_ENV_PREFIX = "COACH_PREP_"


@dataclasses.dataclass(frozen=True)
class Config:
    doc_ingest_app_root: Path = Path(r"C:\Projects\ContentStudio\doc-ingest-app")
    doc_ingest_db_path: Path = Path(r"C:\Projects\ContentStudio\doc-ingest-app\doc_ingest.db")
    converted_root: Path = Path(r"C:\Projects\ContentStudio\Freedom2BeU\converted")
    program_sources_path: Path = Path(r"C:\Projects\ContentStudio\doc-ingest-app\program_sources.yaml")
    coach_email: str = "admin@freedom2beu.com"
    pending_review_drive_folder_id: str = ""
    notify_recipient: str = "brian@happydotemdr.com"
    lookahead_hours: int = 48
    daily_ready_hour_local: int = 7
    timezone_name: str = "America/Chicago"
    last_meeting_email_staleness_days: int = 30
    generation_timeout_s: int = 180


_FIELD_TYPES = typing.get_type_hints(Config)


def _coerce(name: str, raw: str):
    field_type = _FIELD_TYPES[name]
    if field_type is int:
        return int(float(raw))
    if field_type is float:
        return float(raw)
    if field_type is Path:
        return Path(raw)
    return raw


def load_config(path: Path | None = None) -> Config:
    values: dict = {}
    if path is not None and path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for key, value in raw.items():
            if key not in _FIELD_TYPES:
                raise ValueError(
                    f"Unknown config key in {path}: {key!r}; valid keys: "
                    f"{', '.join(sorted(_FIELD_TYPES.keys()))}"
                )
            values[key] = _coerce(key, str(value))

    for field_name in _FIELD_TYPES:
        env_key = _ENV_PREFIX + field_name.upper()
        if env_key in os.environ:
            values[field_name] = _coerce(field_name, os.environ[env_key])

    return Config(**values)


def ensure_doc_ingest_importable(doc_ingest_app_root: Path) -> None:
    """Idempotent sys.path insert so `from doc_ingest import ...` resolves --
    coach-prep-app has an explicit one-way dependency on doc-ingest-app's
    pure/shared modules (client_matching, eid, program_sources, frontmatter),
    the reverse of doc-ingest-app's own standalone packaging."""
    entry = str(doc_ingest_app_root)
    if entry not in sys.path:
        sys.path.insert(0, entry)
```

```python
# coach-prep-app/coach_prep_app/db.py
"""coach-prep-app's own schema, connection factory, and transaction
boundary. Same connection-per-caller model as doc_ingest/db.py, reimplemented
rather than shared (each app owns its own database, matching that module's
own stated rationale)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS watermarks (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_slug                 TEXT NOT NULL,
    calendar_event_instance_id  TEXT NOT NULL,
    done_at                     TEXT NOT NULL,
    UNIQUE(client_slug, calendar_event_instance_id)
);

CREATE TABLE IF NOT EXISTS generation_runs (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_slug                 TEXT NOT NULL,
    calendar_event_instance_id  TEXT NOT NULL,
    meeting_start_at            TEXT NOT NULL,
    status                      TEXT NOT NULL CHECK (status IN
        ('assembling','generated','gates_failed','published','notified','failed')),
    failure_reason              TEXT,
    draft_drive_file_id         TEXT,
    created_at                  TEXT NOT NULL,
    updated_at                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_generation_runs_client ON generation_runs(client_slug);

CREATE TABLE IF NOT EXISTS generation_inputs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES generation_runs(id) ON DELETE CASCADE,
    source_label    TEXT NOT NULL,
    source_kind     TEXT NOT NULL CHECK (source_kind IN ('gmail_thread','converted_file','program_source')),
    reference       TEXT NOT NULL,
    version_or_hash TEXT,
    captured_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_generation_inputs_run ON generation_inputs(run_id);
"""

SCHEMA_VERSION = 1
_TXN_DEPTH: dict[int, int] = {}
_MIGRATIONS: list[tuple[int, str]] = []


@contextmanager
def transaction(conn: sqlite3.Connection):
    key = id(conn)
    depth = _TXN_DEPTH.get(key, 0)
    if depth == 0:
        conn.execute("BEGIN")
    _TXN_DEPTH[key] = depth + 1
    try:
        yield conn
    except BaseException:
        _TXN_DEPTH[key] = depth
        if depth == 0:
            conn.execute("ROLLBACK")
            del _TXN_DEPTH[key]
        raise
    else:
        _TXN_DEPTH[key] = depth
        if depth == 0:
            conn.execute("COMMIT")
            del _TXN_DEPTH[key]


def apply_migrations(conn: sqlite3.Connection) -> None:
    current = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
    for target_version, ddl in _MIGRATIONS:
        if target_version <= current:
            continue
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.executescript(ddl)
            conn.execute("UPDATE schema_version SET version = ? WHERE id = 1", (target_version,))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(_SCHEMA)
    conn.execute("INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, ?)", (SCHEMA_VERSION,))
    apply_migrations(conn)
    return conn
```

```python
# coach-prep-app/setup.py
"""Distribution metadata for coach-prep-app. Mirrors doc-ingest-app's
setup.py: install_requires parsed from requirements.txt so the manifests
cannot drift."""
from pathlib import Path

from setuptools import find_packages, setup

HERE = Path(__file__).resolve().parent


def _runtime_requirements() -> list[str]:
    out = []
    for raw in (HERE / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            out.append(line)
    return out


setup(
    name="coach-prep-app",
    version="0.1.0",
    packages=find_packages(include=["coach_prep_app", "coach_prep_app.*"]),
    install_requires=_runtime_requirements(),
    python_requires=">=3.14",
)
```

```
# coach-prep-app/requirements.txt
pyyaml==6.0.*
requests==2.*
google-api-python-client==2.*
google-auth==2.*
google-auth-oauthlib==1.*
google-auth-httplib2==0.*
tzdata>=2024.1
```

```
# coach-prep-app/requirements-dev.txt
pytest==8.*
```

```ini
; coach-prep-app suite. Run from this directory: `cd coach-prep-app && python -m pytest`.
[pytest]
testpaths = tests
addopts = --strict-markers
markers =
    allow_network: this test may make a real outbound request. Justify in the docstring.
    allow_subprocess: this test may spawn a real child process (claude CLI). Justify in the docstring.
filterwarnings =
    error
    ignore::ResourceWarning
```

```python
# coach-prep-app/tests/conftest.py
"""coach-prep-app suite conftest: subprocess/network guards + shared
fixtures. Mirrors doc-ingest-app/tests/conftest.py's guard shape."""
from __future__ import annotations

import subprocess
import urllib.request
from pathlib import Path

import pytest

_real_subprocess_run = subprocess.run
_real_urlopen = urllib.request.urlopen


@pytest.fixture(autouse=True)
def _block_unmarked_subprocess(request, monkeypatch):
    if request.node.get_closest_marker("allow_subprocess"):
        yield
        return

    def _blocked_run(*args, **kwargs):
        raise RuntimeError(
            "subprocess.run called from an unmarked test -- add "
            "@pytest.mark.allow_subprocess with a docstring justification, "
            "or stub the call."
        )

    monkeypatch.setattr(subprocess, "run", _blocked_run)
    yield
    monkeypatch.setattr(subprocess, "run", _real_subprocess_run)


@pytest.fixture(autouse=True)
def _block_unmarked_network(request, monkeypatch):
    if request.node.get_closest_marker("allow_network"):
        yield
        return

    def _blocked(what: str):
        def _raise(*args, **kwargs):
            raise RuntimeError(
                f"{what} called from a test with no stub -- add "
                "@pytest.mark.allow_network with a docstring justification, "
                "or mock the call."
            )
        return _raise

    monkeypatch.setattr(urllib.request, "urlopen", _blocked("urllib.request.urlopen"))
    try:
        import requests
        import requests.sessions
    except ImportError:
        pass
    else:
        for name in ("request", "get", "post", "put", "patch", "delete", "head"):
            if hasattr(requests, name):
                monkeypatch.setattr(requests, name, _blocked(f"requests.{name}"))
        monkeypatch.setattr(requests.sessions.Session, "request", _blocked("requests.Session.request"))
    yield
    monkeypatch.setattr(urllib.request, "urlopen", _real_urlopen)


@pytest.fixture
def tmp_db_path(tmp_path) -> Path:
    return tmp_path / "coach_prep_test.db"


@pytest.fixture
def conn(tmp_db_path):
    from coach_prep_app import db
    connection = db.init_db(tmp_db_path)
    yield connection
    connection.close()
```

```
# coach-prep-app/tests/__init__.py
```
(empty, matching `doc-ingest-app/tests/__init__.py`)

```
# coach-prep-app/.gitignore
.venv/
__pycache__/
*.pyc
coach_prep.db
coach_prep.db-*
client_secret.json
token.json
.pytest_cache/
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `coach-prep-app/`): `python -m pytest tests/test_config.py tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coach-prep-app/
git commit -m "feat(coach-prep-app): scaffold app -- config, schema, packaging, test harness"
```

### Task 12: coach-prep-app's own OAuth credentials

**Files:**
- Create: `coach-prep-app/coach_prep_app/google_clients.py`
- Create: `coach-prep-app/SETUP.md`
- Test: `coach-prep-app/tests/test_google_clients.py`

**Interfaces:**
- Produces: `SCOPES` (calendar.readonly, gmail.readonly, drive.file), `get_credentials(token_path, client_secret_path) -> Credentials`, `build_calendar_service(cfg)`, `build_gmail_service(cfg)`, `build_drive_service(cfg)`. All three `build_*` functions share one credential pair (a single consent covers all three scopes at once, since Google's OAuth grants a scope set per token, not per-API) and raise `RuntimeError` with a clear message if `token.json` is missing, exactly like `doc_ingest/drive_client.py`'s `build_default_service` — never falling through to the interactive flow under cron.

- [ ] **Step 1: Write the failing test**

```python
# coach-prep-app/tests/test_google_clients.py
from __future__ import annotations

import pytest

from coach_prep_app import config, google_clients


def test_build_calendar_service_raises_clearly_with_no_cached_token(tmp_path):
    cfg = config.Config()
    # google_clients resolves its own app_root from __file__, not from cfg --
    # simulate "no token" by pointing at an isolated app_root via monkeypatch
    # of the module-level app_root computation, exercised directly here:
    import coach_prep_app.google_clients as gc
    original = gc._app_root
    gc._app_root = lambda: tmp_path
    try:
        with pytest.raises(RuntimeError, match="no cached Google token"):
            gc.build_calendar_service(cfg)
    finally:
        gc._app_root = original


def test_scopes_include_calendar_gmail_and_drive_file():
    assert "https://www.googleapis.com/auth/calendar.readonly" in google_clients.SCOPES
    assert "https://www.googleapis.com/auth/gmail.readonly" in google_clients.SCOPES
    assert "https://www.googleapis.com/auth/drive.file" in google_clients.SCOPES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_google_clients.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coach_prep_app.google_clients'`

- [ ] **Step 3: Write the implementation**

```python
# coach-prep-app/coach_prep_app/google_clients.py
"""coach-prep-app's own OAuth client and token -- entirely separate from
doc-ingest-app's credentials (both the Drive/Docs/Sheets pair and the
calendar-only pair added in doc-ingest-app Task 6). One consent grants all
three scopes below in a single token, since a Google OAuth token carries a
scope SET, not one scope per API. Mirrors doc_ingest/drive_client.py's
cron-safe shape: never falls through to the interactive flow when no cached
token exists."""
from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.file",
]


def _app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_credentials(token_path: Path, client_secret_path: Path) -> Credentials:
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _build_service(service_name: str, version: str):
    from googleapiclient.discovery import build

    app_root = _app_root()
    token_path = app_root / "token.json"
    if not token_path.exists():
        raise RuntimeError(
            "coach-prep-app has no cached Google token -- run the one-time "
            "interactive consent documented in SETUP.md before the cron can run"
        )
    creds = get_credentials(token_path, app_root / "client_secret.json")
    return build(service_name, version, credentials=creds)


def build_calendar_service(cfg=None):
    return _build_service("calendar", "v3")


def build_gmail_service(cfg=None):
    return _build_service("gmail", "v1")


def build_drive_service(cfg=None):
    return _build_service("drive", "v3")
```

```markdown
# coach-prep-app — one-time setup

`coach-prep-app` holds its own OAuth client and token, entirely separate from
doc-ingest-app's two credential pairs. One consent grants three scopes at
once: `calendar.readonly`, `gmail.readonly`, `drive.file`.

1. In the Google Cloud Console, reuse or create a project under the
   `admin@freedom2beu.com` Workspace account.
2. Enable three APIs: **Google Calendar API**, **Gmail API**, **Google Drive API**.
3. OAuth consent screen: **User type: Internal** (same reasoning as
   doc-ingest-app/SETUP.md -- an External/Testing app's refresh tokens expire
   after 7 days, which would silently break the 4-hourly cron about a week
   after setup).
4. Create an OAuth client of type **Desktop app**.
5. Download the client secret JSON and save it as
   `coach-prep-app/client_secret.json` (gitignored -- never commit it).
6. Create the **Pending Review** Drive folder by hand (any name, e.g. "Coach
   Prep — Pending Review"), share it with `admin@freedom2beu.com` if it isn't
   already, and record its folder ID in `coach-prep-app`'s config as
   `pending_review_drive_folder_id`.
7. Run the app once by hand to complete the one-time browser consent:

   ```bash
   cd coach-prep-app
   python -c "from pathlib import Path; from coach_prep_app.google_clients import get_credentials; get_credentials(Path('token.json'), Path('client_secret.json'))"
   ```

   The resulting token is cached at `coach-prep-app/token.json` (gitignored)
   and refreshed silently thereafter.

Verify:

```bash
cd coach-prep-app && python -c "from pathlib import Path; from coach_prep_app.google_clients import get_credentials; c = get_credentials(Path('token.json'), Path('client_secret.json')); print('valid:', c.valid)"
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_google_clients.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coach-prep-app/coach_prep_app/google_clients.py coach-prep-app/SETUP.md coach-prep-app/tests/test_google_clients.py
git commit -m "feat(coach-prep-app): add coach-prep-app's own OAuth credentials"
```

### Task 13: `doc_ingest_reader.py` — read-only queries into doc-ingest-app

**Files:**
- Create: `coach-prep-app/coach_prep_app/doc_ingest_reader.py`
- Test: `coach-prep-app/tests/test_doc_ingest_reader.py`

**Interfaces:**
- Consumes: `doc_ingest.frontmatter.parse`, `doc_ingest.program_sources.load_program_sources` (cross-app import via `config.ensure_doc_ingest_importable`, Task 11), doc-ingest-app's `clients`/`conversions` schema (Part 1)
- Produces: `open_readonly(db_path: Path) -> sqlite3.Connection`, `get_active_clients(conn) -> list[dict]`, `get_latest_tagged_meeting_note(conn, cfg, client_slug: str) -> dict` (`source_label`, `rel_path`, `version`, `text`), `get_program_sources(cfg) -> list[dict]` (each: `source_label`, `rel_path`, `version`, `text`). Task 15 (`bundle.py`) is the sole caller of the latter two; Task 20 (`orchestrator.py`) and Task 22 (`audit.py`) call `get_active_clients`.

- [ ] **Step 1: Write the failing test**

```python
# coach-prep-app/tests/test_doc_ingest_reader.py
from __future__ import annotations

import sqlite3

import pytest

from coach_prep_app import config, doc_ingest_reader

config.ensure_doc_ingest_importable(config.Config().doc_ingest_app_root)


@pytest.fixture
def doc_ingest_conn(tmp_path):
    import sys
    sys.path.insert(0, str(config.Config().doc_ingest_app_root))
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
    assert items[0]["source_label"] == "vision-&-passion"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_doc_ingest_reader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coach_prep_app.doc_ingest_reader'`

- [ ] **Step 3: Write the implementation**

```python
# coach-prep-app/coach_prep_app/doc_ingest_reader.py
"""Read-only queries into doc-ingest-app's doc_ingest.db and converted_root.
coach-prep-app NEVER writes to doc-ingest-app's database -- opened via
SQLite's read-only URI mode as a second layer of enforcement beyond just
"don't call .execute() with a write statement"."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from coach_prep_app import config

config.ensure_doc_ingest_importable(config.Config().doc_ingest_app_root)

from doc_ingest import frontmatter as doc_ingest_frontmatter  # noqa: E402
from doc_ingest import program_sources as doc_ingest_program_sources  # noqa: E402


def open_readonly(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


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


def get_program_sources(cfg) -> list[dict]:
    paths = doc_ingest_program_sources.load_program_sources(cfg.program_sources_path)
    items = []
    for rel_path in paths:
        final_path = cfg.converted_root / rel_path
        if not final_path.exists():
            continue
        _, body = doc_ingest_frontmatter.parse(final_path.read_text(encoding="utf-8"))
        label = Path(rel_path).stem.lower().replace(" ", "-")
        items.append({"source_label": label, "rel_path": rel_path, "version": None, "text": body})
    return items
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_doc_ingest_reader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coach-prep-app/coach_prep_app/doc_ingest_reader.py coach-prep-app/tests/test_doc_ingest_reader.py
git commit -m "feat(coach-prep-app): add read-only queries into doc-ingest-app's db"
```

---

## Part 3 — Phase 2 Pipeline

### Task 14: Trigger due-check

**Files:**
- Create: `coach-prep-app/coach_prep_app/trigger.py`
- Test: `coach-prep-app/tests/test_trigger.py`

**Interfaces:**
- Consumes: `coach_prep_app.db.transaction` (Task 11)
- Produces: `is_due(conn, client_slug, event_instance_id, meeting_start_utc: datetime, now_utc: datetime, timezone_name: str, ready_hour_local: int) -> bool`, `mark_done(conn, client_slug, event_instance_id, now_iso: str) -> None`. Keyed on `event_instance_id` (the calendar API's per-**instance** ID, not a recurring series ID) so a recurring booking's second occurrence is not suppressed by the first's watermark.

- [ ] **Step 1: Write the failing test**

```python
# coach-prep-app/tests/test_trigger.py
from __future__ import annotations

import datetime as dt

from coach_prep_app import trigger

TZ = "America/Chicago"


def _utc(y, m, d, h, minute=0):
    return dt.datetime(y, m, d, h, minute, tzinfo=dt.timezone.utc)


def test_not_due_before_seven_am_the_day_before(conn):
    meeting_start = _utc(2026, 8, 20, 15, 0)  # Aug 20, 10am Chicago
    now = _utc(2026, 8, 19, 11, 0)  # Aug 19, 6am Chicago -- before 7am
    assert trigger.is_due(conn, "sean", "evt1", meeting_start, now, TZ, 7) is False


def test_due_at_or_after_seven_am_the_day_before(conn):
    meeting_start = _utc(2026, 8, 20, 15, 0)
    now = _utc(2026, 8, 19, 12, 30)  # Aug 19, 7:30am Chicago
    assert trigger.is_due(conn, "sean", "evt1", meeting_start, now, TZ, 7) is True


def test_not_due_after_watermark_already_set(conn):
    meeting_start = _utc(2026, 8, 20, 15, 0)
    now = _utc(2026, 8, 19, 12, 30)
    trigger.mark_done(conn, "sean", "evt1", now.isoformat())
    assert trigger.is_due(conn, "sean", "evt1", meeting_start, now, TZ, 7) is False


def test_a_different_event_instance_is_independently_due(conn):
    now = _utc(2026, 8, 19, 12, 30)
    trigger.mark_done(conn, "sean", "evt1", now.isoformat())
    meeting_start_2 = _utc(2026, 8, 27, 15, 0)
    assert trigger.is_due(conn, "sean", "evt2", meeting_start_2, now, TZ, 7) is True


def test_recurring_events_instance_ids_are_independent_watermarks(conn):
    """A recurring weekly booking has a distinct instance ID per occurrence
    even though it shares a recurringEventId -- the watermark must be keyed
    on the instance ID (what this function receives), never the series ID,
    or every occurrence after the first would be silently suppressed."""
    now = _utc(2026, 8, 19, 12, 30)
    trigger.mark_done(conn, "sean", "series1_20260820T150000Z", now.isoformat())
    now_next_week = _utc(2026, 8, 26, 12, 30)
    meeting_next_week = _utc(2026, 8, 27, 15, 0)
    assert trigger.is_due(
        conn, "sean", "series1_20260827T150000Z", meeting_next_week, now_next_week, TZ, 7
    ) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_trigger.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coach_prep_app.trigger'`

- [ ] **Step 3: Write the implementation**

```python
# coach-prep-app/coach_prep_app/trigger.py
"""Per-(client, calendar event instance) due-check: fires once, at or after
a configured local hour on the day before the meeting, gated by a persisted
watermark keyed on the event INSTANCE id (never a recurring series id)."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from coach_prep_app import db


def is_due(
    conn,
    client_slug: str,
    event_instance_id: str,
    meeting_start_utc: dt.datetime,
    now_utc: dt.datetime,
    timezone_name: str,
    ready_hour_local: int,
) -> bool:
    already_done = conn.execute(
        "SELECT 1 FROM watermarks WHERE client_slug = ? AND calendar_event_instance_id = ?",
        (client_slug, event_instance_id),
    ).fetchone()
    if already_done is not None:
        return False

    tz = ZoneInfo(timezone_name)
    meeting_local = meeting_start_utc.astimezone(tz)
    ready_at_local = (meeting_local - dt.timedelta(days=1)).replace(
        hour=ready_hour_local, minute=0, second=0, microsecond=0
    )
    return now_utc.astimezone(tz) >= ready_at_local


def mark_done(conn, client_slug: str, event_instance_id: str, now_iso: str) -> None:
    with db.transaction(conn):
        conn.execute(
            "INSERT OR IGNORE INTO watermarks (client_slug, calendar_event_instance_id, done_at) "
            "VALUES (?, ?, ?)",
            (client_slug, event_instance_id, now_iso),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_trigger.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coach-prep-app/coach_prep_app/trigger.py coach-prep-app/tests/test_trigger.py
git commit -m "feat(coach-prep-app): add per-event-instance due-check and watermark"
```

### Task 15: Bundle assembly and input persistence

**Files:**
- Create: `coach-prep-app/coach_prep_app/bundle.py`
- Test: `coach-prep-app/tests/test_bundle.py`

**Interfaces:**
- Consumes: `doc_ingest_reader.get_latest_tagged_meeting_note`/`get_program_sources` (Task 13), `coach_prep_app.db.transaction` (Task 11)
- Produces: `find_last_meeting_email(gmail_service, client_email: str, now_utc: datetime, staleness_days: int) -> dict` (`source_label`, `thread_id`, `text`), `build_bundle(gmail_service, doc_ingest_reader_mod, doc_ingest_conn, cfg, client: dict, now_utc: datetime) -> dict` (`client_display_name`, `client_slug`, `last_meeting_email`, `last_meeting_note`, `program_sources`), `persist_inputs(conn, run_id: int, bundle: dict, now_iso: str) -> None`. Task 16 (`generate.py`) consumes the bundle dict's shape directly; Task 20 (`orchestrator.py`) calls all three.

- [ ] **Step 1: Write the failing test**

```python
# coach-prep-app/tests/test_bundle.py
from __future__ import annotations

import base64
import datetime as dt

from coach_prep_app import bundle

NOW = dt.datetime(2026, 8, 19, 12, 0, tzinfo=dt.timezone.utc)


class _FakeMessages:
    def __init__(self, list_response, get_response):
        self._list_response = list_response
        self._get_response = get_response

    def list(self, userId, q, maxResults):
        assert userId == "me"
        return _Exec(self._list_response)

    def get(self, userId, id, format):
        return _Exec(self._get_response)


class _Exec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _FakeUsers:
    def __init__(self, list_response, get_response):
        self._messages = _FakeMessages(list_response, get_response)

    def messages(self):
        return self._messages


class _FakeGmailService:
    def __init__(self, list_response, get_response):
        self._users = _FakeUsers(list_response, get_response)

    def users(self):
        return self._users


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")


def test_find_last_meeting_email_returns_recent_message_verbatim():
    internal_date_ms = int(dt.datetime(2026, 8, 12, 0, 0, tzinfo=dt.timezone.utc).timestamp() * 1000)
    service = _FakeGmailService(
        list_response={"messages": [{"id": "msg1"}]},
        get_response={
            "threadId": "thread1",
            "internalDate": str(internal_date_ms),
            "payload": {"parts": [{"mimeType": "text/plain", "body": {"data": _b64("Do the 5-minute exercise.")}}]},
        },
    )
    result = bundle.find_last_meeting_email(service, "sean@example.com", NOW, staleness_days=30)
    assert result["thread_id"] == "thread1"
    assert "Do the 5-minute exercise." in result["text"]
    assert "No recent follow-up" not in result["text"]


def test_find_last_meeting_email_flags_a_stale_match():
    internal_date_ms = int(dt.datetime(2026, 1, 1, 0, 0, tzinfo=dt.timezone.utc).timestamp() * 1000)
    service = _FakeGmailService(
        list_response={"messages": [{"id": "msg1"}]},
        get_response={
            "threadId": "thread1",
            "internalDate": str(internal_date_ms),
            "payload": {"parts": [{"mimeType": "text/plain", "body": {"data": _b64("Old content.")}}]},
        },
    )
    result = bundle.find_last_meeting_email(service, "sean@example.com", NOW, staleness_days=30)
    assert "No recent follow-up" in result["text"]
    assert "Old content." in result["text"]


def test_find_last_meeting_email_handles_no_messages_found():
    service = _FakeGmailService(list_response={}, get_response={})
    result = bundle.find_last_meeting_email(service, "sean@example.com", NOW, staleness_days=30)
    assert result["thread_id"] is None
    assert "No follow-up email found" in result["text"]


def test_persist_inputs_writes_one_row_per_source(conn):
    _seed_run(conn)
    the_bundle = {
        "last_meeting_email": {"source_label": "last-meeting-email", "thread_id": "t1", "text": "x"},
        "last_meeting_note": {"source_label": "last-meeting-note", "rel_path": "a/b.md", "version": 1, "text": "y"},
        "program_sources": [
            {"source_label": "vision", "rel_path": "c/d.md", "version": None, "text": "z"},
        ],
    }
    bundle.persist_inputs(conn, 1, the_bundle, "2026-08-19T12:00:00+00:00")
    rows = conn.execute("SELECT source_label, source_kind, reference FROM generation_inputs ORDER BY id").fetchall()
    assert rows == [
        ("last-meeting-email", "gmail_thread", "t1"),
        ("last-meeting-note", "converted_file", "a/b.md"),
        ("vision", "program_source", "c/d.md"),
    ]


def _seed_run(conn):
    conn.execute(
        "INSERT INTO generation_runs (client_slug, calendar_event_instance_id, meeting_start_at, "
        "status, created_at, updated_at) VALUES ('sean', 'evt1', 'n', 'assembling', 'n', 'n')"
    )
    conn.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bundle.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coach_prep_app.bundle'`

- [ ] **Step 3: Write the implementation**

```python
# coach-prep-app/coach_prep_app/bundle.py
"""Assembles the single-client input bundle for one generation run, and
persists it to generation_inputs BEFORE generation happens -- this row
exists regardless of what generation/gates/publish do afterward."""
from __future__ import annotations

import base64
import datetime as dt

from coach_prep_app import db


def find_last_meeting_email(gmail_service, client_email: str, now_utc: dt.datetime, staleness_days: int) -> dict:
    query = f"in:sent to:{client_email}"
    resp = gmail_service.users().messages().list(userId="me", q=query, maxResults=1).execute()
    messages = resp.get("messages", [])
    if not messages:
        return {
            "source_label": "last-meeting-email", "thread_id": None,
            "text": "No follow-up email found for this client.",
        }
    message_id = messages[0]["id"]
    full = gmail_service.users().messages().get(userId="me", id=message_id, format="full").execute()
    internal_date = dt.datetime.fromtimestamp(int(full["internalDate"]) / 1000, tz=dt.timezone.utc)
    text = _extract_plain_text(full)
    if (now_utc - internal_date).days > staleness_days:
        text = f"[No recent follow-up found -- most recent is from {internal_date.date().isoformat()}]\n\n{text}"
    return {"source_label": "last-meeting-email", "thread_id": full.get("threadId"), "text": text}


def _extract_plain_text(message: dict) -> str:
    payload = message.get("payload", {})
    parts = payload.get("parts") or [payload]
    for part in parts:
        if part.get("mimeType") == "text/plain" and "data" in part.get("body", {}):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
    return message.get("snippet", "")


def build_bundle(gmail_service, doc_ingest_reader_mod, doc_ingest_conn, cfg, client: dict, now_utc: dt.datetime) -> dict:
    last_email = find_last_meeting_email(
        gmail_service, client["primary_email"], now_utc, cfg.last_meeting_email_staleness_days
    )
    last_note = doc_ingest_reader_mod.get_latest_tagged_meeting_note(doc_ingest_conn, cfg, client["slug"])
    program_sources = doc_ingest_reader_mod.get_program_sources(cfg)
    return {
        "client_display_name": client["display_name"],
        "client_slug": client["slug"],
        "last_meeting_email": last_email,
        "last_meeting_note": last_note,
        "program_sources": program_sources,
    }


def persist_inputs(conn, run_id: int, the_bundle: dict, now_iso: str) -> None:
    rows = [
        (the_bundle["last_meeting_email"]["source_label"], "gmail_thread",
         the_bundle["last_meeting_email"]["thread_id"] or "none", None),
        (the_bundle["last_meeting_note"]["source_label"], "converted_file",
         the_bundle["last_meeting_note"]["rel_path"] or "none", the_bundle["last_meeting_note"].get("version")),
    ] + [
        (item["source_label"], "program_source", item["rel_path"], item.get("version"))
        for item in the_bundle["program_sources"]
    ]
    with db.transaction(conn):
        for source_label, source_kind, reference, version in rows:
            conn.execute(
                "INSERT INTO generation_inputs "
                "(run_id, source_label, source_kind, reference, version_or_hash, captured_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, source_label, source_kind, reference, str(version) if version else None, now_iso),
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bundle.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coach-prep-app/coach_prep_app/bundle.py coach-prep-app/tests/test_bundle.py
git commit -m "feat(coach-prep-app): assemble and persist the single-client input bundle"
```

### Task 16: `cli_runner.py` — subprocess helpers

**Files:**
- Create: `coach-prep-app/coach_prep_app/cli_runner.py`
- Test: `coach-prep-app/tests/test_cli_runner.py`

**Interfaces:**
- Produces: `resolve_claude_binary(which_fn=shutil.which) -> str`, `platform_argv(argv: list[str]) -> list[str]`, `kill_process_tree(process) -> None`. A local copy (not a cross-app import from `pipeline_app`) — coach-prep-app already has one cross-app dependency on doc-ingest-app; these three functions are small, generic, and copying them avoids a second cross-app coupling. Task 17 (`generate.py`) is the sole caller.

- [ ] **Step 1: Write the failing test**

```python
# coach-prep-app/tests/test_cli_runner.py
from __future__ import annotations

import pytest

from coach_prep_app import cli_runner


def test_resolve_claude_binary_returns_the_resolved_path():
    path = cli_runner.resolve_claude_binary(which_fn=lambda name: "/usr/local/bin/claude")
    assert path == "/usr/local/bin/claude"


def test_resolve_claude_binary_raises_when_not_on_path():
    with pytest.raises(FileNotFoundError):
        cli_runner.resolve_claude_binary(which_fn=lambda name: None)


def test_platform_argv_wraps_cmd_shims_on_windows(monkeypatch):
    monkeypatch.setattr(cli_runner.os, "name", "nt")
    result = cli_runner.platform_argv(["claude.cmd", "-p"])
    assert result == ["cmd", "/c", "claude.cmd", "-p"]


def test_platform_argv_passes_through_a_real_binary(monkeypatch):
    monkeypatch.setattr(cli_runner.os, "name", "nt")
    result = cli_runner.platform_argv(["/usr/local/bin/claude", "-p"])
    assert result == ["/usr/local/bin/claude", "-p"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coach_prep_app.cli_runner'`

- [ ] **Step 3: Write the implementation**

```python
# coach-prep-app/coach_prep_app/cli_runner.py
"""Small subprocess helpers for invoking the claude CLI. A local copy of
pipeline_app/cli_runner.py's three generic pieces -- coach-prep-app already
depends on doc-ingest-app; duplicating three small functions here avoids a
second cross-app coupling on pipeline-app."""
from __future__ import annotations

import os
import subprocess
import shutil
from typing import Callable


def resolve_claude_binary(which_fn: Callable[[str], str | None] = shutil.which) -> str:
    path = which_fn("claude")
    if path is None:
        raise FileNotFoundError(
            "claude CLI not found on PATH. Install Claude Code and ensure 'claude' is on PATH."
        )
    return path


def platform_argv(argv: list[str]) -> list[str]:
    if os.name == "nt" and argv[0].lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c"] + argv
    return argv


def kill_process_tree(process) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                capture_output=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        process.kill()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coach-prep-app/coach_prep_app/cli_runner.py coach-prep-app/tests/test_cli_runner.py
git commit -m "feat(coach-prep-app): add local claude-cli subprocess helpers"
```

### Task 17: Draft generation via isolated `claude -p` subprocess

**Files:**
- Create: `coach-prep-app/coach_prep_app/generate.py`
- Test: `coach-prep-app/tests/test_generate.py`

**Interfaces:**
- Consumes: `cli_runner.resolve_claude_binary`/`platform_argv`/`kill_process_tree` (Task 16)
- Produces: `build_prompt(bundle: dict) -> str`, `parse_envelope(stdout: str) -> str | None`, `generate_draft(bundle: dict, timeout_s: int = DEFAULT_TIMEOUT_S) -> str | None` — never raises; `None` on any failure. Same isolation pattern as `pipeline_app/comment_draft.py`: `--strict-mcp-config`, an exhaustive `--disallowedTools` list, empty scratch cwd. Task 20 (`orchestrator.py`) calls `generate_draft`; Task 18 (`gates.py`) consumes its return value.

- [ ] **Step 1: Write the failing test**

```python
# coach-prep-app/tests/test_generate.py
from __future__ import annotations

import json

from coach_prep_app import generate

SAMPLE_BUNDLE = {
    "client_display_name": "Sean",
    "last_meeting_email": {"source_label": "last-meeting-email", "text": "Do the 5-minute exercise."},
    "last_meeting_note": {"source_label": "last-meeting-note", "text": "Discussed morality as a strength."},
    "program_sources": [
        {"source_label": "program-structure-v3", "text": "12-week arc, 4 pillars."},
        {"source_label": "judge-module", "text": "The Judge saboteur worksheet."},
    ],
}


def test_build_prompt_includes_every_source_label_and_body():
    prompt = generate.build_prompt(SAMPLE_BUNDLE)
    assert "last-meeting-email" in prompt
    assert "Do the 5-minute exercise." in prompt
    assert "program-structure-v3" in prompt
    assert "12-week arc, 4 pillars." in prompt
    assert "judge-module" in prompt


def test_parse_envelope_extracts_result_text():
    stdout = json.dumps({"is_error": False, "result": "## Activities\n- x [last-meeting-email]"})
    assert generate.parse_envelope(stdout) == "## Activities\n- x [last-meeting-email]"


def test_parse_envelope_returns_none_on_error_envelope():
    stdout = json.dumps({"is_error": True, "result": None})
    assert generate.parse_envelope(stdout) is None


def test_parse_envelope_returns_none_on_malformed_json():
    assert generate.parse_envelope("not json") is None


def test_parse_envelope_returns_none_on_empty_result():
    stdout = json.dumps({"is_error": False, "result": "   "})
    assert generate.parse_envelope(stdout) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_generate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coach_prep_app.generate'`

- [ ] **Step 3: Write the implementation**

```python
# coach-prep-app/coach_prep_app/generate.py
"""Generates the coach-prep draft body via an isolated claude -p subprocess
-- same isolation pattern as pipeline_app/comment_draft.py: no tools, no
MCP, empty scratch cwd. The model cannot reach anything beyond what is
embedded in the prompt."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile

from coach_prep_app import cli_runner

DEFAULT_TIMEOUT_S = 180

DISALLOWED_TOOLS = (
    "Bash,PowerShell,WebFetch,WebSearch,Read,Write,Edit,NotebookEdit,"
    "Glob,Grep,Task,Skill,TodoWrite,BashOutput,KillShell"
)

_PROMPT_TEMPLATE = """\
You are drafting a private coach-prep note for Ryan ahead of his next session with {client_display_name}.

Everything between the delimiters below is this one client's own material. Use ONLY this material -- never invent a fact, and never reference any other client.

<<<BUNDLE>>>
## Last session's activities (source label: {email_label})
{last_meeting_email}

## Most recent meeting note (source label: {note_label})
{last_meeting_note}

## Program grounding
{program_sources_block}
<<<BUNDLE>>>

Write three sections in markdown:
1. "## Activities from last session" -- bullet the specific exercises/activities {client_display_name} was asked to do, drawn only from the last-meeting-email material.
2. "## Draft agenda" -- 3-5 bullet agenda items for the upcoming session, grounded in the program material.
3. "## PQ sparks" -- exactly 3 starter questions drawn from the program grounding's saboteur module(s).

Tag EVERY bullet inline with the exact source label it came from, in square brackets, e.g. "- Reflect on the morality exercise [{email_label}]". Use only these labels: {allowed_labels}. If a bullet has no real source, do not write it.

Return ONLY the markdown, no preamble.
"""


def build_prompt(bundle: dict) -> str:
    program_block = "\n\n".join(
        f"### {item['source_label']}\n{item['text']}" for item in bundle["program_sources"]
    )
    allowed_labels = ", ".join(
        [bundle["last_meeting_email"]["source_label"], bundle["last_meeting_note"]["source_label"]]
        + [item["source_label"] for item in bundle["program_sources"]]
    )
    return _PROMPT_TEMPLATE.format(
        client_display_name=bundle["client_display_name"],
        email_label=bundle["last_meeting_email"]["source_label"],
        last_meeting_email=bundle["last_meeting_email"]["text"],
        note_label=bundle["last_meeting_note"]["source_label"],
        last_meeting_note=bundle["last_meeting_note"]["text"],
        program_sources_block=program_block,
        allowed_labels=allowed_labels,
    )


def parse_envelope(stdout: str) -> str | None:
    try:
        envelope = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(envelope, dict) or envelope.get("is_error"):
        return None
    inner = envelope.get("result")
    return inner if isinstance(inner, str) and inner.strip() else None


def generate_draft(bundle: dict, timeout_s: int = DEFAULT_TIMEOUT_S) -> str | None:
    try:
        binary = cli_runner.resolve_claude_binary()
    except FileNotFoundError as exc:
        print(f"generate: {exc}", file=sys.stderr)
        return None

    argv = cli_runner.platform_argv([
        binary, "-p", "--output-format", "json",
        "--strict-mcp-config",
        "--disallowedTools", DISALLOWED_TOOLS,
    ])
    prompt = build_prompt(bundle)

    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as scratch:
            try:
                process = subprocess.Popen(
                    argv, cwd=scratch, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                )
            except (OSError, ValueError) as exc:
                print(f"generate: could not start claude: {exc}", file=sys.stderr)
                return None
            try:
                stdout, _ = process.communicate(prompt, timeout=timeout_s)
            except subprocess.TimeoutExpired:
                cli_runner.kill_process_tree(process)
                try:
                    process.communicate(timeout=5)
                except (subprocess.TimeoutExpired, OSError, ValueError):
                    pass
                print(f"generate: timed out after {timeout_s}s", file=sys.stderr)
                return None
            except (OSError, ValueError) as exc:
                cli_runner.kill_process_tree(process)
                print(f"generate: subprocess failed: {exc}", file=sys.stderr)
                return None
    except OSError as exc:
        print(f"generate: scratch directory failed: {exc}", file=sys.stderr)
        return None

    if process.returncode != 0:
        print(f"generate: claude exited {process.returncode}", file=sys.stderr)
        return None

    return parse_envelope(stdout)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_generate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coach-prep-app/coach_prep_app/generate.py coach-prep-app/tests/test_generate.py
git commit -m "feat(coach-prep-app): generate the draft via an isolated claude -p subprocess"
```

### Task 18: Mechanical gates — citation check and leakage scan

**Files:**
- Create: `coach-prep-app/coach_prep_app/gates.py`
- Test: `coach-prep-app/tests/test_gates.py`

**Interfaces:**
- Produces: `citation_gate(generated_text: str, allowed_labels: set[str]) -> list[str]` (invalid labels found; empty = pass), `leakage_scan(generated_text: str, other_clients: list[dict]) -> list[str]` (other clients' slugs whose name/email/alias/first-name appears; empty = pass). Defense in depth, explicitly **not** the sole safety mechanism — Task 20 (`orchestrator.py`) never publishes to a client-facing location regardless of these gates' result (see Task 19). Task 23 (`audit.py`) reuses `leakage_scan` for its own content scan.

- [ ] **Step 1: Write the failing test**

```python
# coach-prep-app/tests/test_gates.py
from __future__ import annotations

from coach_prep_app import gates

OTHER_CLIENTS = [
    {"slug": "josh", "display_name": "Josh", "primary_email": "josh@example.com", "alias_emails": []},
    {
        "slug": "joanne", "display_name": "Joanne", "primary_email": "jnnbryant77@gmail.com",
        "alias_emails": ["joanne.bryant@schwab.com"],
    },
]


def test_citation_gate_passes_when_every_label_is_allowed():
    text = "- Reflect on X [last-meeting-email]\n- Discuss Y [program-structure-v3]"
    assert gates.citation_gate(text, {"last-meeting-email", "program-structure-v3"}) == []


def test_citation_gate_flags_an_invented_label():
    text = "- Reflect on X [made-up-source]"
    assert gates.citation_gate(text, {"last-meeting-email"}) == ["made-up-source"]


def test_leakage_scan_passes_clean_text():
    text = "- Sean should reflect on morality [last-meeting-email]"
    assert gates.leakage_scan(text, OTHER_CLIENTS) == []


def test_leakage_scan_catches_another_clients_full_name():
    text = "- Like we discussed with Josh, try the same exercise [last-meeting-email]"
    assert gates.leakage_scan(text, OTHER_CLIENTS) == ["josh"]


def test_leakage_scan_catches_another_clients_alias_email():
    text = "- Follow up per joanne.bryant@schwab.com's note [last-meeting-email]"
    assert gates.leakage_scan(text, OTHER_CLIENTS) == ["joanne"]


def test_leakage_scan_catches_another_clients_first_name():
    text = "- Joanne mentioned this exact struggle too [last-meeting-email]"
    assert gates.leakage_scan(text, OTHER_CLIENTS) == ["joanne"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_gates.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coach_prep_app.gates'`

- [ ] **Step 3: Write the implementation**

```python
# coach-prep-app/coach_prep_app/gates.py
"""Mechanical, non-LLM gates run on generated text before publish. Defense
in depth -- NOT the sole safety mechanism. The draft always lands in the
shared Pending Review folder (Task 19), never directly in a client's real
folder, regardless of what these gates find."""
from __future__ import annotations

import re

_CITATION_RE = re.compile(r"\[([a-z0-9\-]+)\]")


def citation_gate(generated_text: str, allowed_labels: set[str]) -> list[str]:
    found = set(_CITATION_RE.findall(generated_text))
    return sorted(found - allowed_labels)


def leakage_scan(generated_text: str, other_clients: list[dict]) -> list[str]:
    lowered = generated_text.lower()
    hits = []
    for client in other_clients:
        needles = [client["display_name"], client["primary_email"], *client["alias_emails"]]
        first_name = client["display_name"].split()[0] if client["display_name"] else ""
        if first_name:
            needles.append(first_name)
        if any(needle and needle.lower() in lowered for needle in needles):
            hits.append(client["slug"])
    return hits
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_gates.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coach-prep-app/coach_prep_app/gates.py coach-prep-app/tests/test_gates.py
git commit -m "feat(coach-prep-app): add citation and leakage mechanical gates"
```

### Task 19: Publish draft to Pending Review folder

**Files:**
- Create: `coach-prep-app/coach_prep_app/publish.py`
- Test: `coach-prep-app/tests/test_publish.py`

**Interfaces:**
- Produces: `draft_title(client_display_name: str, meeting_date: date) -> str`, `publish_draft(drive_service, pending_review_folder_id: str, client_display_name: str, meeting_date: date, markdown_body: str) -> str` (returns the created Drive file ID). Always writes into `pending_review_folder_id` — **never** a client's own `drive_folder_id**. Task 20 (`orchestrator.py`) is the sole caller.

- [ ] **Step 1: Write the failing test**

```python
# coach-prep-app/tests/test_publish.py
from __future__ import annotations

import datetime as dt

from coach_prep_app import publish


class _FakeFiles:
    def __init__(self):
        self.created_with = None

    def create(self, body, media_body, fields):
        self.created_with = body
        return _Exec({"id": "drive-file-123"})


class _Exec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _FakeDriveService:
    def __init__(self):
        self._files = _FakeFiles()

    def files(self):
        return self._files


def test_draft_title_is_clearly_marked_as_a_draft():
    title = publish.draft_title("Sean", dt.date(2026, 8, 20))
    assert title.startswith("DRAFT")
    assert "Sean" in title
    assert "2026-08-20" in title
    assert "review before use" in title


def test_publish_draft_writes_into_the_pending_review_folder_only():
    service = _FakeDriveService()
    file_id = publish.publish_draft(service, "pending-review-folder-id", "Sean", dt.date(2026, 8, 20), "## body")
    assert file_id == "drive-file-123"
    assert service._files.created_with["parents"] == ["pending-review-folder-id"]
    assert "sean-folder-id" not in service._files.created_with["parents"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_publish.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coach_prep_app.publish'`

- [ ] **Step 3: Write the implementation**

```python
# coach-prep-app/coach_prep_app/publish.py
"""Creates the draft as a Google Doc in the single, non-client-scoped
Pending Review folder. NEVER writes directly into a client's real Drive
folder -- a human moving it there is the approval step (design spec's
'Publish (draft, not final)')."""
from __future__ import annotations

import datetime as dt


def draft_title(client_display_name: str, meeting_date: dt.date) -> str:
    return f"DRAFT — Coach Prep — {client_display_name} — {meeting_date.isoformat()} — review before use"


def publish_draft(
    drive_service, pending_review_folder_id: str, client_display_name: str,
    meeting_date: dt.date, markdown_body: str,
) -> str:
    from googleapiclient.http import MediaInMemoryUpload

    file_metadata = {
        "name": draft_title(client_display_name, meeting_date),
        "parents": [pending_review_folder_id],
        "mimeType": "application/vnd.google-apps.document",
    }
    media = MediaInMemoryUpload(markdown_body.encode("utf-8"), mimetype="text/plain")
    created = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    return created["id"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_publish.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coach-prep-app/coach_prep_app/publish.py coach-prep-app/tests/test_publish.py
git commit -m "feat(coach-prep-app): publish drafts to the shared Pending Review folder"
```

### Task 20: Email notification

**Files:**
- Create: `coach-prep-app/coach_prep_app/notify.py`
- Test: `coach-prep-app/tests/test_notify.py`

**Interfaces:**
- Produces: `api_key() -> str | None`, `send_email(subject: str, text: str, recipient: str = RECIPIENT) -> bool` (never raises, `False` on any failure), `render_review_email(client_display_name: str, meeting_date: date, drive_file_id: str) -> tuple[str, str]` (subject, body). Own copy of `discovery_notify.py`'s Resend HTTP pattern (coach-prep-app does not depend on pipeline-app). Task 20/21's orchestrator and Task 23's audit both call `send_email`.

- [ ] **Step 1: Write the failing test**

```python
# coach-prep-app/tests/test_notify.py
from __future__ import annotations

import datetime as dt

import pytest

from coach_prep_app import notify


def test_api_key_reads_env_var_first(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "from-env")
    assert notify.api_key() == "from-env"


def test_api_key_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setattr(notify, "KEY_FILE", notify.Path("/nonexistent/resend_api_key.txt"))
    assert notify.api_key() is None


def test_send_email_returns_false_with_no_key_configured(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setattr(notify, "KEY_FILE", notify.Path("/nonexistent/resend_api_key.txt"))
    assert notify.send_email("subject", "body") is False


@pytest.mark.allow_network  # this test intentionally exercises the real requests.post call path, mocked below
def test_send_email_posts_to_resend_with_the_configured_key(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            pass

    def _fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr(notify.requests, "post", _fake_post)
    result = notify.send_email("Test subject", "Test body")
    assert result is True
    assert captured["url"] == notify.RESEND_API_URL
    assert captured["json"]["subject"] == "Test subject"
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_render_review_email_includes_the_drive_link_and_client_name():
    subject, text = notify.render_review_email("Sean", dt.date(2026, 8, 20), "drive-file-123")
    assert "Sean" in subject
    assert "2026-08-20" in subject
    assert "drive-file-123" in text
    assert "review" in text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_notify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coach_prep_app.notify'`

- [ ] **Step 3: Write the implementation**

```python
# coach-prep-app/coach_prep_app/notify.py
"""Emails a coach-prep notification. Own copy of discovery_notify.py's
Resend HTTP pattern -- coach-prep-app does not depend on pipeline-app."""
from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

import requests

RESEND_API_URL = "https://api.resend.com/emails"
KEY_ENV_VAR = "RESEND_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "resend_api_key.txt"
RECIPIENT = "brian@happydotemdr.com"  # see plan Task 25: confirm whether Ryan should receive these directly
SENDER = os.environ.get("RESEND_FROM_ADDRESS", "onboarding@resend.dev")
REQUEST_TIMEOUT_S = 15


def api_key() -> str | None:
    env_key = os.environ.get(KEY_ENV_VAR, "").strip()
    if env_key:
        return env_key
    if KEY_FILE.exists():
        file_key = KEY_FILE.read_text(encoding="utf-8").strip()
        if file_key:
            return file_key
    return None


def send_email(subject: str, text: str, recipient: str = RECIPIENT) -> bool:
    key = api_key()
    if not key:
        print("notify: no RESEND_API_KEY configured, skipping send", file=sys.stderr)
        return False
    payload = {"from": SENDER, "to": [recipient], "subject": subject, "text": text}
    try:
        response = requests.post(
            RESEND_API_URL, headers={"Authorization": f"Bearer {key}"}, json=payload, timeout=REQUEST_TIMEOUT_S,
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as exc:
        print(f"notify: send_email failed: {exc}", file=sys.stderr)
        return False


def render_review_email(client_display_name: str, meeting_date: dt.date, drive_file_id: str) -> tuple[str, str]:
    subject = f"Review: prep doc for {client_display_name} — meeting {meeting_date.isoformat()}"
    link = f"https://docs.google.com/document/d/{drive_file_id}/edit"
    text = (
        f"Draft coach-prep doc for {client_display_name}'s upcoming session "
        f"({meeting_date.isoformat()}) is ready for review:\n\n{link}\n\n"
        f"Review it, then move it into {client_display_name}'s own Drive folder yourself when ready."
    )
    return subject, text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_notify.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coach-prep-app/coach_prep_app/notify.py coach-prep-app/tests/test_notify.py
git commit -m "feat(coach-prep-app): add Resend email notification"
```

### Task 21: Orchestrator — wire one wake end to end

**Files:**
- Create: `coach-prep-app/coach_prep_app/orchestrator.py`
- Test: `coach-prep-app/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `trigger.is_due`/`mark_done` (Task 14), `bundle.build_bundle`/`persist_inputs` (Task 15), `generate.generate_draft` (Task 17), `gates.citation_gate`/`leakage_scan` (Task 18), `publish.publish_draft` (Task 19), `notify.send_email`/`render_review_email` (Task 20), `doc_ingest_reader.get_active_clients` (Task 13), `doc_ingest.client_matching.match_attendees_to_client` (Part 1 Task 4, cross-app import)
- Produces: `process_candidate(conn, doc_ingest_conn, calendar_service, gmail_service, drive_service, cfg, client: dict, event: dict, now_utc) -> str` (status string), `run_once(conn, doc_ingest_conn, calendar_service, gmail_service, drive_service, cfg, now_utc) -> list[str]`. Task 22's cron script is the sole caller of `run_once`.

- [ ] **Step 1: Write the failing test**

```python
# coach-prep-app/tests/test_orchestrator.py
from __future__ import annotations

import datetime as dt

import pytest

from coach_prep_app import orchestrator

CLIENT = {
    "slug": "sean", "display_name": "Sean", "primary_email": "sean@example.com",
    "alias_emails": [], "session_outlines_dir": "x", "drive_folder_id": "sean-folder",
}
OTHER_CLIENT = {
    "slug": "josh", "display_name": "Josh", "primary_email": "josh@example.com",
    "alias_emails": [], "session_outlines_dir": "y", "drive_folder_id": "josh-folder",
}


@pytest.fixture
def cfg():
    from coach_prep_app.config import Config
    return Config(pending_review_drive_folder_id="pending-folder")


def _patch_pipeline_ok(monkeypatch):
    from coach_prep_app import bundle as bundle_mod
    from coach_prep_app import generate, publish

    monkeypatch.setattr(
        bundle_mod, "build_bundle",
        lambda *a, **k: {
            "client_display_name": "Sean", "client_slug": "sean",
            "last_meeting_email": {"source_label": "last-meeting-email", "thread_id": "t1", "text": "x"},
            "last_meeting_note": {"source_label": "last-meeting-note", "rel_path": "a.md", "version": 1, "text": "y"},
            "program_sources": [{"source_label": "program-source-1", "rel_path": "b.md", "version": None, "text": "z"}],
        },
    )
    monkeypatch.setattr(bundle_mod, "persist_inputs", lambda *a, **k: None)
    monkeypatch.setattr(generate, "generate_draft", lambda b, timeout_s=180: "## Activities\n- x [last-meeting-email]")
    monkeypatch.setattr(publish, "publish_draft", lambda *a, **k: "drive-file-1")
    return bundle_mod, generate, publish


def test_process_candidate_not_due_short_circuits(conn, cfg, monkeypatch):
    event = {"instance_id": "evt1", "start_utc": dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)}
    now = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)  # far before ready time
    result = orchestrator.process_candidate(conn, None, None, None, None, cfg, CLIENT, event, now)
    assert result == "not_due"


def test_process_candidate_happy_path_publishes_and_notifies(conn, cfg, monkeypatch):
    _patch_pipeline_ok(monkeypatch)
    from coach_prep_app import notify
    sent = {}
    monkeypatch.setattr(notify, "send_email", lambda subject, text, recipient=notify.RECIPIENT: sent.setdefault("ok", True) or True)

    event = {"instance_id": "evt1", "start_utc": dt.datetime(2026, 8, 20, 15, 0, tzinfo=dt.timezone.utc)}
    now = dt.datetime(2026, 8, 19, 13, 0, tzinfo=dt.timezone.utc)  # after 7am Chicago the day before

    class _FakeDocIngestConn:
        pass

    import coach_prep_app.doc_ingest_reader as reader
    monkeypatch.setattr(reader, "get_active_clients", lambda conn: [CLIENT, OTHER_CLIENT])

    result = orchestrator.process_candidate(
        conn, _FakeDocIngestConn(), None, None, None, cfg, CLIENT, event, now
    )
    assert result == "published"
    assert sent["ok"] is True

    run = conn.execute("SELECT status, draft_drive_file_id FROM generation_runs").fetchone()
    assert run == ("notified", "drive-file-1")


def test_process_candidate_gate_failure_never_publishes(conn, cfg, monkeypatch):
    bundle_mod, generate, publish = _patch_pipeline_ok(monkeypatch)
    # Generated text leaks another client's display name.
    monkeypatch.setattr(generate, "generate_draft", lambda b, timeout_s=180: "mentions Josh directly [last-meeting-email]")
    publish_calls = []
    monkeypatch.setattr(publish, "publish_draft", lambda *a, **k: publish_calls.append(1) or "should-not-happen")

    from coach_prep_app import notify
    alerts = []
    monkeypatch.setattr(notify, "send_email", lambda subject, text, recipient=notify.RECIPIENT: alerts.append(subject) or True)

    import coach_prep_app.doc_ingest_reader as reader
    monkeypatch.setattr(reader, "get_active_clients", lambda conn: [CLIENT, OTHER_CLIENT])

    event = {"instance_id": "evt1", "start_utc": dt.datetime(2026, 8, 20, 15, 0, tzinfo=dt.timezone.utc)}
    now = dt.datetime(2026, 8, 19, 13, 0, tzinfo=dt.timezone.utc)

    class _FakeDocIngestConn:
        pass

    result = orchestrator.process_candidate(conn, _FakeDocIngestConn(), None, None, None, cfg, CLIENT, event, now)
    assert result == "gate_failed"
    assert publish_calls == []
    assert any("ALERT" in a for a in alerts)

    run = conn.execute("SELECT status FROM generation_runs").fetchone()
    assert run[0] == "failed"


def test_run_once_classifies_events_and_skips_unmatched(conn, cfg, monkeypatch):
    import coach_prep_app.doc_ingest_reader as reader
    monkeypatch.setattr(reader, "get_active_clients", lambda conn: [CLIENT])

    now = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
    far_future_meeting = dt.datetime(2030, 1, 1, 15, 0, tzinfo=dt.timezone.utc)  # well past the 7am-day-before threshold

    def fake_list_events(calendar_service, cfg, now_utc):
        return [
            {"instance_id": "evt1", "start_utc": far_future_meeting, "attendees": ["sean@example.com"]},
            {"instance_id": "evt2", "start_utc": far_future_meeting, "attendees": ["stranger@example.com"]},
        ]

    monkeypatch.setattr(orchestrator, "_list_upcoming_events", fake_list_events)
    results = orchestrator.run_once(conn, None, None, None, None, cfg, now)
    assert results == ["not_due"]  # evt1 (Sean, far future) is not yet due; evt2 (unmatched) skipped entirely
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coach_prep_app.orchestrator'`

- [ ] **Step 3: Write the implementation**

```python
# coach-prep-app/coach_prep_app/orchestrator.py
"""Wires one 4-hourly wake end to end: detect -> classify -> gate on timing
-> assemble -> generate -> mechanical gates -> publish (draft only) ->
notify -> watermark. Every step that can fail leaves the watermark unset so
the next wake retries."""
from __future__ import annotations

import datetime as dt

from coach_prep_app import bundle as bundle_mod
from coach_prep_app import db, doc_ingest_reader, gates, generate, notify, publish, trigger


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def process_candidate(conn, doc_ingest_conn, calendar_service, gmail_service, drive_service, cfg,
                       client: dict, event: dict, now_utc: dt.datetime) -> str:
    if not trigger.is_due(conn, client["slug"], event["instance_id"], event["start_utc"],
                           now_utc, cfg.timezone_name, cfg.daily_ready_hour_local):
        return "not_due"

    run_id = _start_run(conn, client["slug"], event["instance_id"], event["start_utc"])

    all_clients = doc_ingest_reader.get_active_clients(doc_ingest_conn)
    other_clients = [c for c in all_clients if c["slug"] != client["slug"]]

    the_bundle = bundle_mod.build_bundle(gmail_service, doc_ingest_reader, doc_ingest_conn, cfg, client, now_utc)
    bundle_mod.persist_inputs(conn, run_id, the_bundle, _now_iso())

    generated = generate.generate_draft(the_bundle)
    if generated is None:
        _fail_run(conn, run_id, "generation_failed")
        return "generation_failed"

    allowed_labels = {
        the_bundle["last_meeting_email"]["source_label"],
        the_bundle["last_meeting_note"]["source_label"],
        *[i["source_label"] for i in the_bundle["program_sources"]],
    }
    bad_citations = gates.citation_gate(generated, allowed_labels)
    leaked = gates.leakage_scan(generated, other_clients)
    if bad_citations or leaked:
        _fail_run(conn, run_id, f"gate_failed: bad_citations={bad_citations} leaked={leaked}")
        notify.send_email(
            f"ALERT: coach-prep isolation gate failed for {client['display_name']}",
            f"Run {run_id} failed its mechanical gates. bad_citations={bad_citations} leaked={leaked}\n"
            f"No draft was published or sent.",
        )
        return "gate_failed"

    file_id = publish.publish_draft(
        drive_service, cfg.pending_review_drive_folder_id, client["display_name"],
        event["start_utc"].date(), generated,
    )
    _mark_published(conn, run_id, file_id)

    subject, text = notify.render_review_email(client["display_name"], event["start_utc"].date(), file_id)
    sent = notify.send_email(subject, text)
    if not sent:
        return "publish_ok_notify_failed"  # watermark deliberately NOT set -- retried next wake

    trigger.mark_done(conn, client["slug"], event["instance_id"], _now_iso())
    _mark_notified(conn, run_id)
    return "published"


def _start_run(conn, client_slug, event_instance_id, meeting_start_utc) -> int:
    now = _now_iso()
    with db.transaction(conn):
        conn.execute(
            "INSERT INTO generation_runs (client_slug, calendar_event_instance_id, meeting_start_at, "
            "status, created_at, updated_at) VALUES (?, ?, ?, 'assembling', ?, ?)",
            (client_slug, event_instance_id, meeting_start_utc.isoformat(), now, now),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _fail_run(conn, run_id, reason) -> None:
    with db.transaction(conn):
        conn.execute(
            "UPDATE generation_runs SET status = 'failed', failure_reason = ?, updated_at = ? WHERE id = ?",
            (reason, _now_iso(), run_id),
        )


def _mark_published(conn, run_id, file_id) -> None:
    with db.transaction(conn):
        conn.execute(
            "UPDATE generation_runs SET status = 'published', draft_drive_file_id = ?, updated_at = ? WHERE id = ?",
            (file_id, _now_iso(), run_id),
        )


def _mark_notified(conn, run_id) -> None:
    with db.transaction(conn):
        conn.execute(
            "UPDATE generation_runs SET status = 'notified', updated_at = ? WHERE id = ?",
            (_now_iso(), run_id),
        )


def _list_upcoming_events(calendar_service, cfg, now_utc: dt.datetime) -> list[dict]:
    time_min = now_utc.isoformat()
    time_max = (now_utc + dt.timedelta(hours=cfg.lookahead_hours)).isoformat()
    resp = calendar_service.events().list(
        calendarId=cfg.coach_email, timeMin=time_min, timeMax=time_max,
        singleEvents=True, orderBy="startTime",
    ).execute()
    out = []
    for item in resp.get("items", []):
        start = item["start"].get("dateTime") or item["start"].get("date")
        out.append({
            "instance_id": item["id"],
            "start_utc": dt.datetime.fromisoformat(start).astimezone(dt.timezone.utc),
            "attendees": [a["email"] for a in item.get("attendees", []) if "email" in a],
        })
    return out


def _classify_event(clients: list[dict], event: dict, coach_email: str) -> str | None:
    from doc_ingest import client_matching
    slug = client_matching.match_attendees_to_client(event["attendees"], clients, coach_email)
    return None if slug == client_matching.UNMATCHED else slug


def run_once(conn, doc_ingest_conn, calendar_service, gmail_service, drive_service, cfg,
             now_utc: dt.datetime) -> list[str]:
    results = []
    clients = doc_ingest_reader.get_active_clients(doc_ingest_conn)
    events = _list_upcoming_events(calendar_service, cfg, now_utc)
    for event in events:
        client_slug = _classify_event(clients, event, cfg.coach_email)
        if client_slug is None:
            continue
        client = next(c for c in clients if c["slug"] == client_slug)
        results.append(process_candidate(
            conn, doc_ingest_conn, calendar_service, gmail_service, drive_service, cfg, client, event, now_utc
        ))
    return results
```

Note: `_classify_event` cross-imports `doc_ingest.client_matching` inline (deferred import), matching the pattern already established in `doc_ingest_reader.py` — call `config.ensure_doc_ingest_importable` once at process startup (Task 22's cron script does this) so the import resolves.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coach-prep-app/coach_prep_app/orchestrator.py coach-prep-app/tests/test_orchestrator.py
git commit -m "feat(coach-prep-app): wire detect->classify->generate->gates->publish->notify"
```

### Task 22: Cron entry point and Task Scheduler registration

**Files:**
- Create: `coach-prep-app/scripts/run_coachprep_cron.py`
- Create: `coach-prep-app/scripts/setup_coachprep_task.py`
- Test: `coach-prep-app/tests/test_run_coachprep_cron.py`, `coach-prep-app/tests/test_setup_coachprep_task.py`

**Interfaces:**
- Consumes: everything in Part 3 plus `google_clients.build_calendar_service`/`build_gmail_service`/`build_drive_service` (Task 12)
- Produces: `run_coachprep_cron.main(argv=None) -> int`, `setup_coachprep_task.build_schtasks_command(python_exe, cron_script) -> list[str]` and `main(argv=None) -> int`. Registers a fixed 4-hour trigger, mirroring `doc-ingest-app/scripts/setup_ingest_task.py`'s shape exactly except for the interval and task name.

- [ ] **Step 1: Write the failing tests**

```python
# coach-prep-app/tests/test_setup_coachprep_task.py
from __future__ import annotations

from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import setup_coachprep_task  # noqa: E402


def test_build_schtasks_command_fires_every_240_minutes():
    cmd = setup_coachprep_task.build_schtasks_command(Path("python.exe"), Path("run_coachprep_cron.py"))
    assert "/MO" in cmd
    assert cmd[cmd.index("/MO") + 1] == "240"
    assert cmd[cmd.index("/TN") + 1] == setup_coachprep_task.TASK_NAME
    assert "/SC" in cmd and cmd[cmd.index("/SC") + 1] == "MINUTE"
```

```python
# coach-prep-app/tests/test_run_coachprep_cron.py
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_coachprep_cron  # noqa: E402


def test_main_calls_run_once_and_returns_zero(tmp_path, monkeypatch):
    calls = []

    def fake_run_once(conn, doc_ingest_conn, calendar_service, gmail_service, drive_service, cfg, now_utc):
        calls.append(1)
        return ["published"]

    from coach_prep_app import orchestrator, config as config_mod, google_clients
    monkeypatch.setattr(orchestrator, "run_once", fake_run_once)
    monkeypatch.setattr(google_clients, "build_calendar_service", lambda cfg: None)
    monkeypatch.setattr(google_clients, "build_gmail_service", lambda cfg: None)
    monkeypatch.setattr(google_clients, "build_drive_service", lambda cfg: None)

    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text(
        f"doc_ingest_db_path: {tmp_path / 'doc_ingest_test.db'}\n"
        f"doc_ingest_app_root: {tmp_path}\n",
        encoding="utf-8",
    )
    import doc_ingest  # ensure a real doc_ingest package is importable for open_readonly's target dir check
    from doc_ingest import db as doc_ingest_db
    doc_ingest_db.init_db(tmp_path / "doc_ingest_test.db").close()

    rc = run_coachprep_cron.main(["--config", str(yaml_path)])
    assert rc == 0
    assert calls == [1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_setup_coachprep_task.py tests/test_run_coachprep_cron.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# coach-prep-app/scripts/run_coachprep_cron.py
"""Windows Task Scheduler entry point, invoked every 4 hours.

Usage:
  python scripts/run_coachprep_cron.py [--config path.yaml]
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from coach_prep_app import config, db, doc_ingest_reader, google_clients, orchestrator


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)

    cfg = config.load_config(Path(args.config) if args.config else None)
    config.ensure_doc_ingest_importable(cfg.doc_ingest_app_root)

    conn = db.init_db(HERE.parent / "coach_prep.db")
    doc_ingest_conn = doc_ingest_reader.open_readonly(cfg.doc_ingest_db_path)
    try:
        calendar_service = google_clients.build_calendar_service(cfg)
        gmail_service = google_clients.build_gmail_service(cfg)
        drive_service = google_clients.build_drive_service(cfg)
        results = orchestrator.run_once(
            conn, doc_ingest_conn, calendar_service, gmail_service, drive_service, cfg,
            dt.datetime.now(dt.timezone.utc),
        )
        for r in results:
            print(r)
    finally:
        conn.close()
        doc_ingest_conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

```python
# coach-prep-app/scripts/setup_coachprep_task.py
"""One-time registration of the ContentStudio-CoachPrep Windows Task
Scheduler task. Fixed 4-hour trigger, no additional due-gating on top --
trigger.is_due (coach_prep_app/trigger.py) is what decides whether any given
wake actually does anything. Mirrors doc-ingest-app/scripts/setup_ingest_task.py.

Usage:
  python scripts/setup_coachprep_task.py            # dry run: prints the command
  python scripts/setup_coachprep_task.py --apply     # actually registers the task
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TASK_NAME = "ContentStudio-CoachPrep"


def build_schtasks_command(python_exe: Path, cron_script: Path) -> list[str]:
    task_command = f'"{python_exe}" "{cron_script}"'
    return [
        "schtasks", "/Create", "/TN", TASK_NAME,
        "/TR", task_command, "/SC", "MINUTE", "/MO", "240", "/F",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually register the task (default: dry run / print only)")
    args = ap.parse_args(argv)

    app_root = Path(__file__).resolve().parents[1]
    python_exe = Path(sys.executable)
    cron_script = app_root / "scripts" / "run_coachprep_cron.py"
    cmd = build_schtasks_command(python_exe, cron_script)

    if not args.apply:
        print("Dry run -- this is the command that would register the scheduled task:")
        print(" ".join(cmd))
        print("\nRe-run with --apply to actually register it.")
        return 0

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode
    print(f"Registered task '{TASK_NAME}': fires every 4 hours.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_setup_coachprep_task.py tests/test_run_coachprep_cron.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coach-prep-app/scripts/run_coachprep_cron.py coach-prep-app/scripts/setup_coachprep_task.py coach-prep-app/tests/test_run_coachprep_cron.py coach-prep-app/tests/test_setup_coachprep_task.py
git commit -m "feat(coach-prep-app): add 4-hourly cron entry point and task registration"
```

---

## Part 4 — Weekly Audit

### Task 23: Audit report — mechanical scan, content scan, placement check, unmatched count

**Files:**
- Create: `coach-prep-app/coach_prep_app/audit.py`
- Test: `coach-prep-app/tests/test_audit.py`

**Interfaces:**
- Consumes: `gates.leakage_scan` (Task 18), `doc_ingest_reader.get_active_clients` (Task 13)
- Produces: `mechanical_scan(conn, doc_ingest_conn) -> list[dict]`, `content_scan(conn, doc_ingest_conn, drive_service) -> list[dict]`, `placement_check(conn, doc_ingest_conn, drive_service, pending_review_folder_id) -> list[dict]`, `unmatched_count(doc_ingest_conn) -> int`, `build_report(conn, doc_ingest_conn, drive_service, cfg) -> dict`, `render_report_email(report: dict) -> tuple[str, str]`. Task 24's weekly cron script is the sole caller of `build_report`/`render_report_email`.

- [ ] **Step 1: Write the failing test**

```python
# coach-prep-app/tests/test_audit.py
from __future__ import annotations

from coach_prep_app import audit

CLIENTS = [
    {"slug": "sean", "display_name": "Sean", "primary_email": "sean@example.com",
     "alias_emails": [], "session_outlines_dir": "x", "drive_folder_id": "sean-folder"},
    {"slug": "josh", "display_name": "Josh", "primary_email": "josh@example.com",
     "alias_emails": [], "session_outlines_dir": "y", "drive_folder_id": "josh-folder"},
]


class _FakeDocIngestConn:
    def __init__(self, client_by_output_path):
        self._map = client_by_output_path

    def execute(self, sql, params=()):
        if "FROM conversions WHERE output_path" in sql:
            client = self._map.get(params[0])
            return _Row(client)
        if "COUNT(*)" in sql:
            unmatched = sum(1 for v in self._map.values() if v == "unmatched")
            return _Row((unmatched,))
        raise NotImplementedError(sql)


class _Row:
    def __init__(self, value):
        self._value = value

    def fetchone(self):
        if self._value is None:
            return None
        return self._value if isinstance(self._value, tuple) else (self._value,)


def _seed_run(conn, client_slug, status="notified", draft_id="file1"):
    conn.execute(
        "INSERT INTO generation_runs (client_slug, calendar_event_instance_id, meeting_start_at, "
        "status, draft_drive_file_id, created_at, updated_at) VALUES (?, 'evt1', 'n', ?, ?, 'n', 'n')",
        (client_slug, status, draft_id),
    )
    run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    return run_id


def test_mechanical_scan_flags_a_run_whose_input_belongs_to_another_client(conn):
    run_id = _seed_run(conn, "sean")
    conn.execute(
        "INSERT INTO generation_inputs (run_id, source_label, source_kind, reference, captured_at) "
        "VALUES (?, 'last-meeting-note', 'converted_file', 'josh-note.md', 'n')",
        (run_id,),
    )
    conn.commit()
    doc_ingest_conn = _FakeDocIngestConn({"josh-note.md": "josh"})
    problems = audit.mechanical_scan(conn, doc_ingest_conn)
    assert len(problems) == 1
    assert problems[0]["expected"] == "sean"
    assert problems[0]["found"] == "josh"


def test_mechanical_scan_is_clean_when_inputs_match(conn):
    run_id = _seed_run(conn, "sean")
    conn.execute(
        "INSERT INTO generation_inputs (run_id, source_label, source_kind, reference, captured_at) "
        "VALUES (?, 'last-meeting-note', 'converted_file', 'sean-note.md', 'n')",
        (run_id,),
    )
    conn.commit()
    doc_ingest_conn = _FakeDocIngestConn({"sean-note.md": "sean"})
    assert audit.mechanical_scan(conn, doc_ingest_conn) == []


def test_unmatched_count_reads_from_doc_ingest_conn(conn):
    doc_ingest_conn = _FakeDocIngestConn({"a.md": "unmatched", "b.md": "sean", "c.md": "unmatched"})
    assert audit.unmatched_count(doc_ingest_conn) == 2


def test_render_report_email_reports_clean_when_no_problems():
    report = {"mechanical_problems": [], "content_problems": [], "placement": [], "unmatched_count": 0}
    subject, text = audit.render_report_email(report)
    assert "clean" in subject.lower()
    assert "No problems" in text


def test_render_report_email_flags_issues_in_the_subject():
    report = {
        "mechanical_problems": [{"run_id": 1, "expected": "sean", "found": "josh", "reference": "x.md"}],
        "content_problems": [], "placement": [], "unmatched_count": 0,
    }
    subject, text = audit.render_report_email(report)
    assert "ISSUES" in subject
    assert "run 1" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_audit.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coach_prep_app.audit'`

- [ ] **Step 3: Write the implementation**

```python
# coach-prep-app/coach_prep_app/audit.py
"""Weekly mechanical scan + content leakage scan + placement check +
unmatched count, reported via the existing Resend pattern."""
from __future__ import annotations

from coach_prep_app import doc_ingest_reader, gates


def mechanical_scan(conn, doc_ingest_conn) -> list[dict]:
    """Flags any generation run whose generation_inputs reference a
    client-scoped converted file tagged for a DIFFERENT client than the run
    itself. Global program_source inputs are excluded by design."""
    problems = []
    runs = conn.execute(
        "SELECT id, client_slug FROM generation_runs WHERE status IN ('published', 'notified')"
    ).fetchall()
    for run_id, client_slug in runs:
        refs = conn.execute(
            "SELECT reference FROM generation_inputs WHERE run_id = ? AND source_kind = 'converted_file'",
            (run_id,),
        ).fetchall()
        for (ref,) in refs:
            row = doc_ingest_conn.execute(
                "SELECT client FROM conversions WHERE output_path = ? AND status = 'current'", (ref,)
            ).fetchone()
            actual_client = row[0] if row else None
            if actual_client not in (None, client_slug):
                problems.append({"run_id": run_id, "expected": client_slug, "found": actual_client, "reference": ref})
    return problems


def content_scan(conn, doc_ingest_conn, drive_service) -> list[dict]:
    """Re-fetches each published draft's text from Drive and re-runs the
    leakage scan against every OTHER registered client. Same tripwire
    caveat as gates.leakage_scan -- not a guarantee."""
    problems = []
    runs = conn.execute(
        "SELECT id, client_slug, draft_drive_file_id FROM generation_runs "
        "WHERE status IN ('published', 'notified') AND draft_drive_file_id IS NOT NULL"
    ).fetchall()
    clients = doc_ingest_reader.get_active_clients(doc_ingest_conn)
    for run_id, client_slug, file_id in runs:
        text = drive_service.files().export(fileId=file_id, mimeType="text/plain").execute().decode("utf-8")
        other_clients = [c for c in clients if c["slug"] != client_slug]
        leaked = gates.leakage_scan(text, other_clients)
        if leaked:
            problems.append({"run_id": run_id, "client_slug": client_slug, "leaked": leaked})
    return problems


def placement_check(conn, doc_ingest_conn, drive_service, pending_review_folder_id: str) -> list[dict]:
    """For each notified draft, whether it's still sitting in Pending
    Review, moved to the correct client folder, or moved somewhere
    unexpected. Informational for the first two states; only the third is
    surfaced as a problem by render_report_email."""
    clients_by_slug = {c["slug"]: c for c in doc_ingest_reader.get_active_clients(doc_ingest_conn)}
    results = []
    runs = conn.execute(
        "SELECT id, client_slug, draft_drive_file_id FROM generation_runs "
        "WHERE status = 'notified' AND draft_drive_file_id IS NOT NULL"
    ).fetchall()
    for run_id, client_slug, file_id in runs:
        meta = drive_service.files().get(fileId=file_id, fields="parents").execute()
        parents = meta.get("parents", [])
        expected_folder = clients_by_slug.get(client_slug, {}).get("drive_folder_id")
        if expected_folder and expected_folder in parents:
            status = "moved_to_correct_folder"
        elif pending_review_folder_id in parents:
            status = "still_pending_review"
        else:
            status = "moved_to_unexpected_location"
        results.append({"run_id": run_id, "client_slug": client_slug, "status": status})
    return results


def unmatched_count(doc_ingest_conn) -> int:
    row = doc_ingest_conn.execute(
        "SELECT COUNT(*) FROM conversions WHERE status = 'current' AND client = 'unmatched'"
    ).fetchone()
    return row[0]


def build_report(conn, doc_ingest_conn, drive_service, cfg) -> dict:
    return {
        "mechanical_problems": mechanical_scan(conn, doc_ingest_conn),
        "content_problems": content_scan(conn, doc_ingest_conn, drive_service),
        "placement": placement_check(conn, doc_ingest_conn, drive_service, cfg.pending_review_drive_folder_id),
        "unmatched_count": unmatched_count(doc_ingest_conn),
    }


def render_report_email(report: dict) -> tuple[str, str]:
    clean = not report["mechanical_problems"] and not report["content_problems"]
    subject = "Coach-prep weekly audit: clean" if clean else "Coach-prep weekly audit: ISSUES FOUND"
    lines = [f"Unmatched meeting notes: {report['unmatched_count']}", ""]
    if report["mechanical_problems"]:
        lines.append("Mechanical scan problems:")
        lines += [
            f"  run {p['run_id']}: expected {p['expected']}, found {p['found']} ({p['reference']})"
            for p in report["mechanical_problems"]
        ]
    if report["content_problems"]:
        lines.append("Content leakage problems:")
        lines += [f"  run {p['run_id']} ({p['client_slug']}): leaked {p['leaked']}" for p in report["content_problems"]]
    unexpected_placements = [p for p in report["placement"] if p["status"] == "moved_to_unexpected_location"]
    if unexpected_placements:
        lines.append("Drafts moved to an unexpected location:")
        lines += [f"  run {p['run_id']} ({p['client_slug']})" for p in unexpected_placements]
    if clean:
        lines.append("No problems found this week.")
    return subject, "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_audit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coach-prep-app/coach_prep_app/audit.py coach-prep-app/tests/test_audit.py
git commit -m "feat(coach-prep-app): add weekly audit report"
```

### Task 24: Weekly audit cron entry point and registration

**Files:**
- Create: `coach-prep-app/scripts/run_client_audit.py`
- Create: `coach-prep-app/scripts/setup_audit_task.py`
- Test: `coach-prep-app/tests/test_run_client_audit.py`, `coach-prep-app/tests/test_setup_audit_task.py`

**Interfaces:**
- Consumes: `audit.build_report`/`render_report_email` (Task 23), `notify.send_email` (Task 20)
- Produces: `run_client_audit.main(argv=None) -> int`, `setup_audit_task.build_schtasks_command(python_exe, audit_script) -> list[str]` and `main(argv=None) -> int`. Weekly trigger (`/SC WEEKLY`), distinct task name from Task 22's.

- [ ] **Step 1: Write the failing tests**

```python
# coach-prep-app/tests/test_setup_audit_task.py
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import setup_audit_task  # noqa: E402


def test_build_schtasks_command_fires_weekly():
    cmd = setup_audit_task.build_schtasks_command(Path("python.exe"), Path("run_client_audit.py"))
    assert cmd[cmd.index("/SC") + 1] == "WEEKLY"
    assert cmd[cmd.index("/TN") + 1] == setup_audit_task.TASK_NAME
    assert setup_audit_task.TASK_NAME != "ContentStudio-CoachPrep"  # distinct from Task 22's task
```

```python
# coach-prep-app/tests/test_run_client_audit.py
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_client_audit  # noqa: E402


def test_main_builds_report_and_sends_email(tmp_path, monkeypatch):
    from coach_prep_app import audit, google_clients, notify

    monkeypatch.setattr(audit, "build_report", lambda *a, **k: {
        "mechanical_problems": [], "content_problems": [], "placement": [], "unmatched_count": 0,
    })
    sent = []
    monkeypatch.setattr(notify, "send_email", lambda subject, text, recipient=notify.RECIPIENT: sent.append(subject) or True)
    monkeypatch.setattr(google_clients, "build_drive_service", lambda cfg: None)

    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text(
        f"doc_ingest_db_path: {tmp_path / 'doc_ingest_test.db'}\n"
        f"doc_ingest_app_root: {tmp_path}\n",
        encoding="utf-8",
    )
    from doc_ingest import db as doc_ingest_db
    doc_ingest_db.init_db(tmp_path / "doc_ingest_test.db").close()

    rc = run_client_audit.main(["--config", str(yaml_path)])
    assert rc == 0
    assert sent == ["Coach-prep weekly audit: clean"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_setup_audit_task.py tests/test_run_client_audit.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# coach-prep-app/scripts/run_client_audit.py
"""Weekly audit entry point.

Usage:
  python scripts/run_client_audit.py [--config path.yaml]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from coach_prep_app import audit, config, db, doc_ingest_reader, google_clients, notify


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)

    cfg = config.load_config(Path(args.config) if args.config else None)
    config.ensure_doc_ingest_importable(cfg.doc_ingest_app_root)

    conn = db.init_db(HERE.parent / "coach_prep.db")
    doc_ingest_conn = doc_ingest_reader.open_readonly(cfg.doc_ingest_db_path)
    try:
        drive_service = google_clients.build_drive_service(cfg)
        report = audit.build_report(conn, doc_ingest_conn, drive_service, cfg)
        subject, text = audit.render_report_email(report)
        notify.send_email(subject, text)
        print(text)
    finally:
        conn.close()
        doc_ingest_conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

```python
# coach-prep-app/scripts/setup_audit_task.py
"""One-time registration of the ContentStudio-CoachPrepAudit Windows Task
Scheduler task. Weekly, Monday 8am -- distinct task name and schedule from
setup_coachprep_task.py's 4-hourly task.

Usage:
  python scripts/setup_audit_task.py            # dry run: prints the command
  python scripts/setup_audit_task.py --apply     # actually registers the task
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TASK_NAME = "ContentStudio-CoachPrepAudit"


def build_schtasks_command(python_exe: Path, audit_script: Path) -> list[str]:
    task_command = f'"{python_exe}" "{audit_script}"'
    return [
        "schtasks", "/Create", "/TN", TASK_NAME,
        "/TR", task_command, "/SC", "WEEKLY", "/D", "MON", "/ST", "08:00", "/F",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually register the task (default: dry run / print only)")
    args = ap.parse_args(argv)

    app_root = Path(__file__).resolve().parents[1]
    python_exe = Path(sys.executable)
    audit_script = app_root / "scripts" / "run_client_audit.py"
    cmd = build_schtasks_command(python_exe, audit_script)

    if not args.apply:
        print("Dry run -- this is the command that would register the scheduled task:")
        print(" ".join(cmd))
        print("\nRe-run with --apply to actually register it.")
        return 0

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode
    print(f"Registered task '{TASK_NAME}': fires weekly, Monday 8am.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_setup_audit_task.py tests/test_run_client_audit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add coach-prep-app/scripts/run_client_audit.py coach-prep-app/scripts/setup_audit_task.py coach-prep-app/tests/test_run_client_audit.py coach-prep-app/tests/test_setup_audit_task.py
git commit -m "feat(coach-prep-app): add weekly audit cron entry point and task registration"
```

---

## Part 5 — Rollout (operational, against the real corpus)

These two tasks run against real data in the main checkout (`C:\Projects\ContentStudio\`, not this worktree — see the design spec's Context section on why `Freedom2BeU/` only exists there). They have no unit tests of their own; Parts 1-4 already tested the code paths they invoke. Each step is a concrete command plus what to check in its output, not free-form judgment calls.

### Task 25: Discover and register the real clients; confirm `program_sources.yaml`

**Files:**
- Modify (data only, via CLI): `doc-ingest-app/doc_ingest.db`'s `clients` table (main checkout)
- Modify: `doc-ingest-app/program_sources.yaml` (main checkout, if Task 9's seed needs correcting)

- [ ] **Step 1: Find each client's real email address and Drive folder ID**

From the main checkout (`C:\Projects\ContentStudio`, not this worktree):

```bash
cd doc-ingest-app
python -c "
from pathlib import Path
import re
root = Path(r'C:\Projects\ContentStudio\Freedom2BeU\converted\Client Session Outlines')
for sub in root.iterdir():
    if sub.is_dir():
        print(f'--- {sub.name} ---')
        for f in sub.glob('*.md'):
            text = f.read_text(encoding='utf-8', errors='replace')
            for m in re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)[:5]:
                print(f'  {m}')
"
```

Cross-check each candidate address against `Client Meet Recordings & Notes/`'s `Invited [...]` lines for the same person (grep for the display name) to confirm it's the address that actually appears on their calendar invites — the address that shows up in Session Outlines correspondence is not guaranteed to be the same one Google Calendar has on file.

For each of Sean, Josh, and Joanne, open their real Drive folder under `Client Session Outlines/` in a browser and copy the folder ID from its URL (`https://drive.google.com/drive/folders/<FOLDER_ID>`).

**"Ryan Ratto" is explicitly excluded from this step** — no email address for him was found anywhere in the corpus during design (see design spec's Open Questions). Confirm this is still true with a targeted search:

```bash
python -c "
from pathlib import Path
import re
root = Path(r'C:\Projects\ContentStudio\Freedom2BeU\converted')
for f in root.rglob('*Ratto*'):
    text = f.read_text(encoding='utf-8', errors='replace')
    print(f.name, re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text))
"
```

If this turns up a real address, register him the same way as the other three below. If not, leave him unregistered — his meeting notes will tag `unmatched`, which is correct and safe (not a bug to work around).

- [ ] **Step 2: Register each confirmed client**

```bash
cd doc-ingest-app
python scripts/register_client.py add --slug sean --display-name "Sean" \
    --email sean.carl.tinsley@gmail.com \
    --session-outlines-dir "Client Session Outlines/Sean" \
    --drive-folder-id <SEAN_FOLDER_ID>

python scripts/register_client.py add --slug josh --display-name "Josh" \
    --email <JOSH_REAL_EMAIL> \
    --session-outlines-dir "Client Session Outlines/Josh" \
    --drive-folder-id <JOSH_FOLDER_ID>

python scripts/register_client.py add --slug joanne --display-name "Joanne" \
    --email jnnbryant77@gmail.com --alias-email joanne.bryant@schwab.com \
    --session-outlines-dir "Client Session Outlines/Joanne" \
    --drive-folder-id <JOANNE_FOLDER_ID>

python scripts/register_client.py list
```

Verify the `list` output shows exactly the clients just registered, each with the email confirmed in Step 1.

- [ ] **Step 3: Confirm `program_sources.yaml` with Brian/Ryan**

Task 9 seeded `program_sources.yaml` with all 8 files under `Offer & Coaching Framework/Current finalized documents/` plus one of the two near-duplicate Judge files (picked arbitrarily — the non-`(1)` filename). Before relying on this in production:

1. Show Brian/Ryan the seeded list.
2. Confirm the Judge-file pick is correct, or have them identify which of the two is actually canonical (and whether the other should be deleted from Drive entirely, which is a decision for them to make outside this plan).
3. Confirm none of the 8 "Current finalized documents" files are themselves stale despite living in that folder (the folder name is curator-maintained, not automatically verified) — if any are marked as an unpublished draft or wrong version to serve in a coach-prep doc, remove that line from the YAML.
4. Update `doc-ingest-app/program_sources.yaml` in the main checkout accordingly, and commit the change with a note recording who confirmed it and when.

- [ ] **Step 4: Commit the registration and confirmation record**

The `clients` table lives in `doc_ingest.db`, which is gitignored (real client data) — there is nothing to `git add` for Step 2. For Step 3's `program_sources.yaml` change, if any:

```bash
cd doc-ingest-app
git add program_sources.yaml
git commit -m "chore(doc-ingest): confirm program_sources.yaml with Brian/Ryan"
```

### Task 26: One-time OAuth consents, backfill, and scheduled-task registration

**Files:** none (operational only — every script this task runs was built and tested in Parts 1-4)

- [ ] **Step 1: Run doc-ingest-app's new calendar-only consent**

From `doc-ingest-app/` (main checkout), per Task 6's SETUP.md addendum:

```bash
python -c "from pathlib import Path; from doc_ingest.calendar_client import get_credentials; get_credentials(Path('calendar_token.json'), Path('calendar_client_secret.json'))"
```

A browser opens for one-time consent. Confirm `calendar_token.json` now exists and `doc-ingest-app/token.json` (the existing Drive/Docs/Sheets token) is unchanged (compare its modification time against before this step — it must not have been touched).

- [ ] **Step 2: Run coach-prep-app's consent**

From `coach-prep-app/` (main checkout), per Task 12's SETUP.md:

```bash
python -c "from pathlib import Path; from coach_prep_app.google_clients import get_credentials; get_credentials(Path('token.json'), Path('client_secret.json'))"
```

Confirm `coach-prep-app/token.json` now exists.

- [ ] **Step 3: Run the backfill in dry-run, review, then apply**

```bash
cd doc-ingest-app
python scripts/backfill_client_tags.py --dry-run
```

Review the printed report line by line with Brian/Ryan: for each of the ~24 meeting-note files, confirm the classified client (or `unmatched`) is correct, paying particular attention to the cases identified during design — Joanne's non-mailto `Invited` rendering should now resolve correctly via the `eid`/Calendar-API path, and Investor Operator Meeting / Our Costa Rica Adventure / Chris Griswold should all classify `unmatched`. Once confirmed:

```bash
python scripts/backfill_client_tags.py --apply
```

Re-run `--dry-run` once more afterward and confirm every previously-`None` `current_client` now matches its `classified_client` with zero diffs remaining.

- [ ] **Step 4: Register both coach-prep-app scheduled tasks**

```bash
cd coach-prep-app
python scripts/setup_coachprep_task.py            # review the dry-run output first
python scripts/setup_coachprep_task.py --apply
python scripts/setup_audit_task.py
python scripts/setup_audit_task.py --apply
```

Confirm both tasks appear in Windows Task Scheduler (`schtasks /Query /TN ContentStudio-CoachPrep` and `schtasks /Query /TN ContentStudio-CoachPrepAudit`).

- [ ] **Step 5: Confirm the notification recipient**

`coach_prep_app/notify.py`'s default `RECIPIENT` is `brian@happydotemdr.com`, matching every other automated email in this codebase (`pipeline_app/discovery_notify.py`'s same constant). Confirm with Brian whether Ryan should receive these review emails directly instead — if so, override via `notify_recipient` in coach-prep-app's config YAML (Task 11's `Config.notify_recipient` field) rather than editing the code.

- [ ] **Step 6: End-to-end smoke test against one real, near-term meeting**

If any registered client has a real meeting in the next 48 hours, let the 4-hourly cron fire naturally and confirm: a `DRAFT — Coach Prep — ...` Google Doc appears in the Pending Review folder, an email arrives at the confirmed recipient with a working link, and the doc's "Activities from last session" section correctly reflects that specific client's most recent follow-up email (not a stale or wrong one). If no meeting falls in that window, run `python scripts/run_coachprep_cron.py` by hand against a manually-created test calendar event to exercise the same path without waiting.

No commit for this task — it is entirely operational verification of already-committed code.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-17-freedom2beu-coach-prep-automation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
