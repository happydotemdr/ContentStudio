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


def test_add_duplicate_slug_returns_error(tmp_db_path, capsys):
    register_client.main(
        ["add", "--slug", "sean", "--display-name", "Sean", "--email", "sean@example.com",
         "--session-outlines-dir", "x", "--drive-folder-id", "y"],
        db_path=tmp_db_path,
    )
    rc = register_client.main(
        ["add", "--slug", "sean", "--display-name", "Sean Again", "--email", "other@example.com",
         "--session-outlines-dir", "x", "--drive-folder-id", "y"],
        db_path=tmp_db_path,
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "error:" in err
