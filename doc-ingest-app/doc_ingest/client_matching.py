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
