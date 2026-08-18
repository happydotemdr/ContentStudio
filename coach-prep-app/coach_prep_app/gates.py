# coach-prep-app/coach_prep_app/gates.py
"""Mechanical, non-LLM gates run on generated text before publish. Defense
in depth -- NOT the sole safety mechanism. The draft always lands in the
shared Pending Review folder (Task 19), never directly in a client's real
folder, regardless of what these gates find."""
from __future__ import annotations

import re

_CITATION_RE = re.compile(r"\[([a-z0-9\-]+)\](?!\()")


def citation_gate(generated_text: str, allowed_labels: set[str]) -> list[str]:
    found = set(_CITATION_RE.findall(generated_text))
    return sorted(found - allowed_labels)


def leakage_scan(generated_text: str, other_clients: list[dict]) -> list[str]:
    lowered = generated_text.lower()
    hits = []
    for client in other_clients:
        needles = [client["display_name"], client["primary_email"], *client["alias_emails"]]
        first_name = client["display_name"].split()[0] if client["display_name"] else ""
        matched = any(needle and needle.lower() in lowered for needle in needles)
        if not matched and first_name:
            matched = bool(re.search(rf"\b{re.escape(first_name)}\b", generated_text))
        if matched:
            hits.append(client["slug"])
    return hits
