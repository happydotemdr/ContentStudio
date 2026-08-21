# coach-prep-app/coach_prep_app/manifest.py
"""The prep doc's closing footer: a confidentiality notice and the complete
list of documents the draft was built from.

Rendered in Python from the generation_inputs rows, and appended AFTER the
gates have run on the model's output. Two reasons it works that way rather
than being asked for in the prompt:

  - Completeness. The rows are written before generation starts, so they
    record every source that went in, including ones the model made no use
    of. A model asked to list its sources lists the ones it remembers using.
  - Integrity. Text the model cannot write is text it cannot weaken, and the
    confidentiality notice is the one line on the page that must never be
    softened or dropped.
"""
from __future__ import annotations

CONFIDENTIAL_HEADING = "Private — do not share"

_CONFIDENTIAL_BODY = (
    "This note is prepared for Ryan alone. It draws on session transcripts and "
    "private correspondence, and it is **not** to be shared with the client, "
    "forwarded, or used as a handout. It is a draft: review it before the call "
    "and trust your own read of the room over anything written here."
)

# Ordered so the manifest reads the way the doc was built: what the client and
# coach exchanged, then the program, then what was chosen for this session.
_KIND_HEADINGS = (
    ("gmail_thread", "Email sent to the client"),
    ("converted_file", "Session notes"),
    ("program_source", "Freedom2BeU program material"),
    ("book_list", "Reading list"),
    ("selected_framework", "Framework activities chosen for this session"),
)


def fetch_inputs(conn, run_id: int) -> list[tuple[str, str, str, str | None]]:
    return conn.execute(
        "SELECT source_kind, source_label, reference, version_or_hash "
        "FROM generation_inputs WHERE run_id = ? ORDER BY id",
        (run_id,),
    ).fetchall()


def render(rows: list[tuple[str, str, str, str | None]]) -> str:
    """The footer, as markdown. Kept to headings, bullets and bold so it
    survives the round trip out to Google Docs and back."""
    parts = [
        "---",
        "",
        f"## {CONFIDENTIAL_HEADING}",
        "",
        _CONFIDENTIAL_BODY,
        "",
        "## Sources this note was built from",
        "",
    ]

    by_kind: dict[str, list[tuple[str, str, str | None]]] = {}
    for source_kind, source_label, reference, version in rows:
        by_kind.setdefault(source_kind, []).append((source_label, reference, version))

    listed = 0
    for kind, heading in _KIND_HEADINGS:
        items = by_kind.get(kind)
        if not items:
            continue
        parts.append(f"**{heading}**")
        parts.append("")
        for source_label, reference, version in items:
            suffix = f" (v{version})" if version else ""
            parts.append(f"- `{source_label}` — {reference}{suffix}")
            listed += 1
        parts.append("")

    # Any kind the CHECK constraint allows but this module has no heading for
    # still gets listed. "Complete list of every input" has to mean complete,
    # and a source silently absent from the manifest is worse than one under a
    # generic heading.
    unlisted = {kind: items for kind, items in by_kind.items()
                if kind not in dict(_KIND_HEADINGS)}
    if unlisted:
        parts.append("**Other sources**")
        parts.append("")
        for kind in sorted(unlisted):
            for source_label, reference, version in unlisted[kind]:
                suffix = f" (v{version})" if version else ""
                parts.append(f"- `{source_label}` ({kind}) — {reference}{suffix}")
                listed += 1
        parts.append("")

    if listed == 0:
        parts.append("No source documents were recorded for this run.")
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def append_to(draft: str, rows: list[tuple[str, str, str, str | None]]) -> str:
    return draft.rstrip() + "\n\n" + render(rows)
