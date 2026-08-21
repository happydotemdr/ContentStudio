from __future__ import annotations

from coach_prep_app import db, manifest

_ROWS = [
    ("gmail_thread", "last-meeting-email", "thread-1", None),
    ("gmail_thread", "sent-email-2", "thread-2", None),
    ("converted_file", "meeting-note-aug", "Client Meet Recordings & Notes/aug.gdoc.md", "1"),
    ("program_source", "freedom2beu-program-structure-v3", "Offer/structure.gdoc.md", None),
    ("book_list", "f2bu-coaching-book-recommendations", "Frameworks/books.gsheet.md", None),
    ("selected_framework", "fear", "Frameworks/Fear.pdf.md", "2"),
]


def test_render_lists_every_input_row():
    """The doc promises a complete list of what it was built from. A source
    silently missing from it is the failure this section exists to prevent."""
    rendered = manifest.render(_ROWS)
    for _, source_label, reference, _ in _ROWS:
        assert source_label in rendered
        assert reference in rendered


def test_render_groups_sources_under_readable_headings():
    rendered = manifest.render(_ROWS)
    for heading in ("Email sent to the client", "Session notes",
                    "Freedom2BeU program material", "Reading list",
                    "Framework activities chosen for this session"):
        assert f"**{heading}**" in rendered


def test_render_shows_the_version_where_one_is_recorded():
    """Which VERSION of a note the draft read matters -- doc-ingest reconverts
    files, and a prep doc built on v1 says something different from one built
    on v3."""
    rendered = manifest.render(_ROWS)
    assert "aug.gdoc.md (v1)" in rendered
    assert "Fear.pdf.md (v2)" in rendered
    assert "structure.gdoc.md\n" in rendered  # no version recorded, no suffix invented


def test_render_carries_the_confidentiality_notice():
    rendered = manifest.render(_ROWS)
    assert manifest.CONFIDENTIAL_HEADING in rendered
    assert "not** to be shared with the client" in rendered


def test_render_of_a_run_that_recorded_nothing_says_so():
    """An empty manifest is information -- it tells Ryan the doc was built on
    nothing. A blank section would just look like a rendering fault."""
    rendered = manifest.render([])
    assert "No source documents were recorded" in rendered
    assert manifest.CONFIDENTIAL_HEADING in rendered


def test_render_lists_a_source_kind_it_has_no_heading_for():
    """'Complete list of every input' has to mean complete. A kind added to
    the schema later must appear under a generic heading rather than vanish
    because this module was not taught about it."""
    rendered = manifest.render([("some_future_kind", "label", "path/to.md", None)])
    assert "**Other sources**" in rendered
    assert "label" in rendered
    assert "some_future_kind" in rendered
    assert "No source documents were recorded" not in rendered


def test_render_uses_only_round_trip_safe_markdown():
    """The published doc becomes a Google Doc and is converted back to
    markdown by the ingest cron. The footer must survive that intact."""
    rendered = manifest.render(_ROWS)
    assert "<" not in rendered
    assert "[^" not in rendered
    for line in rendered.splitlines():
        if line.startswith("#"):
            assert not line.startswith("####"), f"heading too deep: {line}"


def test_append_to_leaves_the_draft_body_untouched():
    draft = "## Part 1 — Check-in\n\n- an item [last-meeting-email]"
    appended = manifest.append_to(draft, _ROWS)
    assert appended.startswith(draft)
    assert manifest.CONFIDENTIAL_HEADING in appended


def test_append_to_separates_the_footer_with_a_rule():
    appended = manifest.append_to("## Part 1", _ROWS)
    assert "\n---\n" in appended


def test_fetch_inputs_returns_rows_in_insertion_order(tmp_path):
    conn = db.init_db(tmp_path / "coach_prep.db")
    try:
        conn.execute(
            "INSERT INTO generation_runs (client_slug, calendar_event_instance_id, "
            "meeting_start_at, status, created_at, updated_at) "
            "VALUES ('sean', 'evt1', 'm', 'assembling', 'n', 'n')"
        )
        run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for source_kind, source_label, reference, version in _ROWS:
            conn.execute(
                "INSERT INTO generation_inputs (run_id, source_label, source_kind, "
                "reference, version_or_hash, captured_at) VALUES (?, ?, ?, ?, ?, 'n')",
                (run_id, source_label, source_kind, reference, version),
            )
        conn.commit()
        assert manifest.fetch_inputs(conn, run_id) == _ROWS
    finally:
        conn.close()


def test_fetch_inputs_is_scoped_to_one_run(tmp_path):
    """Two clients' drafts are generated in the same wake. A manifest that
    picked up another run's rows would name another client's documents on this
    client's page."""
    conn = db.init_db(tmp_path / "coach_prep.db")
    try:
        run_ids = []
        for slug in ("sean", "josh"):
            conn.execute(
                "INSERT INTO generation_runs (client_slug, calendar_event_instance_id, "
                "meeting_start_at, status, created_at, updated_at) "
                "VALUES (?, 'evt1', 'm', 'assembling', 'n', 'n')",
                (slug,),
            )
            run_ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        for run_id, reference in zip(run_ids, ("sean-note.md", "josh-note.md")):
            conn.execute(
                "INSERT INTO generation_inputs (run_id, source_label, source_kind, "
                "reference, captured_at) VALUES (?, 'note', 'converted_file', ?, 'n')",
                (run_id, reference),
            )
        conn.commit()
        rendered = manifest.render(manifest.fetch_inputs(conn, run_ids[0]))
        assert "sean-note.md" in rendered
        assert "josh-note.md" not in rendered
    finally:
        conn.close()
