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


def test_register_duplicate_email_different_slug_raises(conn):
    clients_db.register_client(
        conn, slug="sean", display_name="Sean", primary_email="shared@example.com",
        session_outlines_dir="x", drive_folder_id="y",
    )
    with pytest.raises(clients_db.ClientAlreadyExists):
        clients_db.register_client(
            conn, slug="frank", display_name="Frank", primary_email="shared@example.com",
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
