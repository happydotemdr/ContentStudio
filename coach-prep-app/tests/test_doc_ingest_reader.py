# coach-prep-app/tests/test_doc_ingest_reader.py
from __future__ import annotations

import sqlite3

import pytest

from coach_prep_app import config, doc_ingest_reader

# Config's doc_ingest_app_root default resolves relative to coach-prep-app's
# own on-disk location (Task 11), so this correctly points at the sibling
# doc-ingest-app in THIS checkout -- the worktree during development, the
# main checkout after merge -- with no override needed.
config.ensure_doc_ingest_importable(config.Config().doc_ingest_app_root)


@pytest.fixture
def doc_ingest_conn(tmp_path):
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
    assert items[0]["source_label"] == "vision-passion"


def test_slugify_source_label_strips_both_suffixes_and_special_characters():
    # "Vision & Passion.gdoc.md" has TWO suffixes (the original extension
    # doc-ingest-app preserves, plus ".md") -- Path.stem only strips one, so
    # a naive Path(...).stem-based label would still carry ".gdoc" and "&",
    # neither of which gates.py's citation regex ([a-z0-9-]+) can match.
    assert doc_ingest_reader.slugify_source_label("Vision & Passion.gdoc.md") == "vision-passion"
    assert doc_ingest_reader.slugify_source_label("F2BU_Module_00_The_Judge.docx.md") == "f2bu-module-00-the-judge"


def test_open_readonly_rejects_writes(tmp_path):
    """open_readonly's whole purpose is enforcing that coach-prep-app can
    never write to doc-ingest-app's database -- pin that at the connection
    level, not just by convention, so a future edit that silently drops
    mode=ro (or otherwise weakens this) fails CI instead of shipping."""
    from doc_ingest import db as doc_ingest_db
    db_path = tmp_path / "doc_ingest_test.db"
    doc_ingest_db.init_db(db_path).close()

    ro_conn = doc_ingest_reader.open_readonly(db_path)
    try:
        # Reads must still work.
        ro_conn.execute("SELECT slug FROM clients").fetchall()
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            ro_conn.execute(
                "INSERT INTO clients (slug, display_name, primary_email, alias_emails_json, "
                "session_outlines_dir, drive_folder_id, status, created_at) "
                "VALUES ('x', 'X', 'x@example.com', '[]', 'x', 'y', 'active', 'z')"
            )
    finally:
        ro_conn.close()


# --- meeting-date ordering and the two-note fetch ---------------------------
#
# get_latest_tagged_meeting_note ordered by converted_at -- when a file was
# INGESTED, not when the meeting happened. Joanne's real corpus rows show the
# two diverging: her July 22 note was re-converted on 2026-08-14T18:25:53 and
# her August 4 note on 2026-08-14T18:25:40, so "most recent note" returned the
# July session. Ryan would prep off a transcript two weeks stale with nothing
# on the page to say so.

def _seed_note(conn, cfg, filename, converted_at, client="joanne", body=None):
    note_dir = cfg.converted_root / "Client Meet Recordings & Notes"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / f"{filename}.md").write_text(
        f"---\nversion: 1\n---\n\n{body or filename}", encoding="utf-8"
    )
    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, size_bytes, mtime, "
        "content_hash, first_seen_at, last_seen_at) VALUES (?, 'gdoc', 'gdoc_pointer', 1, 'm', 'h', 'n', 'n')",
        (f"Client Meet Recordings & Notes/{filename}",),
    )
    source_file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "conversion_tool, converted_at, gauntlet_passed_at, client) VALUES "
        "(?, 1, ?, 'current', 'gdoc', 'google-docs-export', ?, 'n', ?)",
        (source_file_id, f"Client Meet Recordings & Notes/{filename}.md", converted_at, client),
    )
    conn.commit()


@pytest.mark.parametrize("filename,expected", [
    ("1 1 Coaching with Joanne - 2026 08 04 10 01 CST - Notes by Gemini.gdoc", "2026-08-04"),
    ("Josh - 2026 08 20 07 54 CST - Notes by Gemini.gdoc.v3", "2026-08-20"),
    ("Sean and Ryan Coaching Session - 2026 07 29 08 09 CST - Notes by Gemini.gdoc", "2026-07-29"),
    ("Joanne and Ryan Chat - 2026 07 22 09 57 CST - Notes by Gemini V3.gdoc", "2026-07-22"),
])
def test_meeting_date_is_read_from_the_real_filename_shapes(filename, expected):
    """Every one of these is a real corpus filename. Gemini names its notes
    '<title> - YYYY MM DD HH MM TZ - Notes by Gemini'."""
    assert doc_ingest_reader.meeting_date_from_filename(filename) == expected


@pytest.mark.parametrize("filename", [
    "joanne-topic-backlog.md.gdoc",
    "1 1 coaching joanne-ryan 8-6-26 .md",
    "notes.md",
    "",
])
def test_meeting_date_is_none_when_the_filename_carries_no_date(filename):
    """A hand-named file has no parseable date. It must fall back to
    converted_at rather than being dropped or crashing the run."""
    assert doc_ingest_reader.meeting_date_from_filename(filename) is None


def test_notes_order_by_meeting_date_not_converted_at(doc_ingest_conn, tmp_path):
    """Joanne's exact production shape: the July note ingested LAST."""
    from coach_prep_app.config import Config
    cfg = Config(converted_root=tmp_path / "converted")
    _seed_note(doc_ingest_conn, cfg,
               "1 1 Coaching with Joanne - 2026 08 04 10 01 CST - Notes by Gemini.gdoc",
               "2026-08-14T18:25:40.170476+00:00", body="the August session")
    _seed_note(doc_ingest_conn, cfg,
               "Joanne and Ryan Chat - 2026 07 22 09 57 CST - Notes by Gemini V3.gdoc",
               "2026-08-14T18:25:53.496056+00:00", body="the July session")

    notes = doc_ingest_reader.get_recent_meeting_notes(doc_ingest_conn, cfg, "joanne", limit=2)

    assert [n["text"].strip() for n in notes] == ["the August session", "the July session"]


def test_get_recent_meeting_notes_returns_two_most_recent(doc_ingest_conn, tmp_path):
    from coach_prep_app.config import Config
    cfg = Config(converted_root=tmp_path / "converted")
    for day, body in (("01", "oldest"), ("08", "middle"), ("15", "newest")):
        _seed_note(doc_ingest_conn, cfg,
                   f"Chat - 2026 08 {day} 10 00 CST - Notes by Gemini.gdoc",
                   "2026-08-20T00:00:00+00:00", body=body)

    notes = doc_ingest_reader.get_recent_meeting_notes(doc_ingest_conn, cfg, "joanne", limit=2)

    assert [n["text"].strip() for n in notes] == ["newest", "middle"]


def test_recent_notes_get_distinct_source_labels(doc_ingest_conn, tmp_path):
    """Both notes are cited in Part 1 of the prep doc, and the citation gate
    validates each tag against the allowlist. Two notes sharing one label
    would make it impossible to tell which session a check-in item came from."""
    from coach_prep_app.config import Config
    cfg = Config(converted_root=tmp_path / "converted")
    for day in ("01", "08"):
        _seed_note(doc_ingest_conn, cfg,
                   f"Chat - 2026 08 {day} 10 00 CST - Notes by Gemini.gdoc",
                   "2026-08-20T00:00:00+00:00")

    labels = [n["source_label"] for n in
              doc_ingest_reader.get_recent_meeting_notes(doc_ingest_conn, cfg, "joanne", limit=2)]

    assert len(set(labels)) == 2
    assert all(label.replace("-", "").isalnum() for label in labels), labels


def test_recent_notes_carry_the_meeting_date_for_the_prep_doc(doc_ingest_conn, tmp_path):
    """Ryan needs to see WHICH session each note is, and the summary says how
    long it has been since the last one."""
    from coach_prep_app.config import Config
    cfg = Config(converted_root=tmp_path / "converted")
    _seed_note(doc_ingest_conn, cfg,
               "Chat - 2026 08 04 10 00 CST - Notes by Gemini.gdoc", "2026-08-20T00:00:00+00:00")

    note, = doc_ingest_reader.get_recent_meeting_notes(doc_ingest_conn, cfg, "joanne", limit=2)
    assert note["meeting_date"] == "2026-08-04"


def test_get_recent_meeting_notes_returns_empty_when_none_found(doc_ingest_conn, tmp_path):
    from coach_prep_app.config import Config
    cfg = Config(converted_root=tmp_path / "converted")
    assert doc_ingest_reader.get_recent_meeting_notes(doc_ingest_conn, cfg, "sean", limit=2) == []


def test_undated_notes_sort_below_dated_ones(doc_ingest_conn, tmp_path):
    """A hand-named file with no parseable date must not outrank a real recent
    session just because it happened to be ingested later."""
    from coach_prep_app.config import Config
    cfg = Config(converted_root=tmp_path / "converted")
    _seed_note(doc_ingest_conn, cfg,
               "Chat - 2026 08 04 10 00 CST - Notes by Gemini.gdoc",
               "2026-08-01T00:00:00+00:00", body="a real dated session")
    _seed_note(doc_ingest_conn, cfg,
               "joanne-topic-backlog.md.gdoc", "2026-08-30T00:00:00+00:00", body="undated")

    notes = doc_ingest_reader.get_recent_meeting_notes(doc_ingest_conn, cfg, "joanne", limit=2)
    assert notes[0]["text"].strip() == "a real dated session"


# --- source labels must identify ONE document -------------------------------
#
# slugify_source_label did filename.split(".", 1)[0] to strip doc-ingest's
# "<name>.<ext>.md" suffixes. Real corpus filenames carry dots in the NAME --
# JSCCCoachingToolA3.2ExaminingFear.pdf.md -- so it truncated at "A3" and
# collapsed 43 distinct Jay Shetty coaching tools onto 10 labels. Measured
# 2026-08-21 across the built catalog.
#
# That is a safety defect, not a cosmetic one. The label IS the citation gate's
# allowlist entry, so a draft could cite [jscccoachingtoola3] having been given
# "To-Be List" while appearing to cite "Examining Fear", and the gate would
# pass it. It is also what the closing manifest prints, so Ryan could not tell
# which of four tools the note actually drew on.

@pytest.mark.parametrize("filename,expected", [
    ("JSCCCoachingToolA3.2ExaminingFear.pdf.md", "jscccoachingtoola3-2examiningfear"),
    ("JSCCCoachingToolA3.1To-BeList.pdf.md", "jscccoachingtoola3-1to-belist"),
    ("JSCCCoachingToolC2.3ThoughtTrapChallenge.pdf.md", "jscccoachingtoolc2-3thoughttrapchallenge"),
    ("Vision & Passion.gdoc.md", "vision-passion"),
    ("F2BU_Module_00_The_Judge.docx.md", "f2bu-module-00-the-judge"),
    ("Josh - 2026 08 20 07 54 CST - Notes by Gemini.gdoc.v3.md",
     "josh-2026-08-20-07-54-cst-notes-by-gemini"),
    ("Wheel of Life.xlsx.md", "wheel-of-life"),
])
def test_source_label_keeps_what_distinguishes_a_document(filename, expected):
    assert doc_ingest_reader.slugify_source_label(filename) == expected


def test_every_jay_shetty_tool_gets_its_own_label():
    """The four C2 tools are four different exercises. One shared label makes
    them indistinguishable to the citation gate and to Ryan reading the
    manifest."""
    names = [
        "JSCCCoachingToolC2.1ChallengingComfortZone.pdf.md",
        "JSCCCoachingToolC2.2DiscoverLimitingBeliefs.pdf.md",
        "JSCCCoachingToolC2.3ThoughtTrapChallenge.pdf.md",
        "JSCCCoachingToolC2.4ConflictResolution.pdf.md",
    ]
    labels = [doc_ingest_reader.slugify_source_label(n) for n in names]
    assert len(set(labels)) == 4, labels


def test_source_label_is_still_matchable_by_the_citation_gate():
    """gates.citation_gate's regex only recognises [a-z0-9-]. A label carrying
    anything else is a tag the gate cannot see."""
    import re
    for filename in (
        "JSCCCoachingToolA3.2ExaminingFear.pdf.md",
        "Vision & Passion.gdoc.md",
        "Josh - 2026 08 20 07 54 CST - Notes by Gemini.gdoc.v3.md",
    ):
        label = doc_ingest_reader.slugify_source_label(filename)
        assert re.fullmatch(r"[a-z0-9-]+", label), label


def test_meeting_note_labels_are_short_enough_to_read_mid_call():
    """Part 1's bullets carry these inline, and Ryan reads them out loud while
    talking. The full Gemini filename ran to 48 characters in the middle of a
    question."""
    note_label = doc_ingest_reader.meeting_note_label(
        "Josh - 2026 08 20 07 54 CST - Notes by Gemini.gdoc.v3.md"
    )
    assert note_label == "session-2026-08-20"


def test_meeting_note_labels_stay_distinct_across_sessions():
    labels = {
        doc_ingest_reader.meeting_note_label(n)
        for n in ("Josh - 2026 08 20 07 54 CST - Notes by Gemini.gdoc.v3.md",
                  "Josh - 2026 08 04 10 02 CST - Notes by Gemini.gdoc.md")
    }
    assert labels == {"session-2026-08-20", "session-2026-08-04"}


def test_an_undated_meeting_note_falls_back_to_its_filename():
    """A hand-named note has no date to build a short label from. It must
    still get a citable label rather than a collision-prone constant."""
    label = doc_ingest_reader.meeting_note_label("joanne-topic-backlog.md.gdoc.md")
    assert label.startswith("session-")
    assert "joanne-topic-backlog" in label
