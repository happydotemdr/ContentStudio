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
