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
