# tests/test_gauntlet_gate2.py
from doc_ingest.config import Config
from doc_ingest import gauntlet


def _seed_conversion(conn, source_file_id, output_path, status="current"):
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "conversion_tool, converted_at) VALUES (?, 1, ?, ?, 'pdf', 'firecrawl-parse', ?)",
        (source_file_id, output_path, status, now),
    )
    conn.commit()


def _seed_source_file(conn, rel_path):
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
        "VALUES (?, 'pdf', 'convertible', ?, ?)", (rel_path, now, now),
    )
    conn.commit()
    return conn.execute("SELECT id FROM source_files WHERE rel_path = ?", (rel_path,)).fetchone()[0]


def test_gate2_resolves_a_clean_destination(conn):
    source_id = _seed_source_file(conn, "Folder/Notes.pdf")
    result, dest = gauntlet.run_gate2(conn, "Folder/Notes.pdf", source_id, version=1, cfg=Config())
    assert result.passed is True
    assert dest == "Folder/Notes.pdf.md"


def test_gate2_measures_the_full_absolute_path_not_just_the_relative_one(conn):
    # A relative path that would need no shortening at all in isolation
    # (naming.build_dest_rel_path with prefix_len=0) still needs MORE
    # shortening once converted_root's own length is accounted for -- proves
    # Gate 2 is actually threading prefix_len through, not just calling
    # naming.py the same way Task 4's own unit tests do.
    from doc_ingest import naming

    cfg = Config(long_path_threshold_chars=150)
    long_rel_path = "/".join([
        "Client Coaching Session Recordings And Notes",
        "2026 Individual Sessions Archive",
        "Very Long Coaching Session Transcript With A Lot Of Detail In The Name.pdf",
    ])
    source_id = _seed_source_file(conn, long_rel_path)

    dest_ignoring_prefix = naming.build_dest_rel_path(long_rel_path, version=1, cfg=cfg, prefix_len=0)
    result, dest = gauntlet.run_gate2(conn, long_rel_path, source_id, version=1, cfg=cfg)

    prefix_len = len(str(cfg.converted_root)) + 1
    assert result.passed is True
    assert prefix_len + len(dest) <= cfg.long_path_threshold_chars
    assert len(dest) <= len(dest_ignoring_prefix)


def test_gate2_rejects_path_traversal_even_if_naming_ever_stopped_stripping_it(conn, monkeypatch):
    # naming.build_dest_rel_path today always neutralizes ".." (a segment of
    # only dots is stripped entirely by sanitize_component's trailing-dot
    # rstrip), so this exercises Gate 2's OWN defense-in-depth check in
    # isolation -- it must reject a traversal-shaped path even if naming.py
    # ever regressed and stopped stripping it.
    from doc_ingest import naming
    source_id = _seed_source_file(conn, "a.pdf")
    monkeypatch.setattr(naming, "build_dest_rel_path", lambda *a, **kw: "../../escape.pdf.md")
    result, dest = gauntlet.run_gate2(conn, "a.pdf", source_id, version=1, cfg=Config())
    assert result.passed is False
    assert result.failure_reason == "path_traversal_rejected"
    assert dest is None


def test_gate2_logs_a_collision_and_appends_a_hash_suffix(conn):
    source_a = _seed_source_file(conn, "Folder/Notes.pdf")
    source_b = _seed_source_file(conn, "Folder/OtherNotes.pdf")
    _seed_conversion(conn, source_a, "Folder/Notes.pdf.md")

    # Force a collision by asserting b's natural dest equals a's (simulated
    # via monkeypatched naming in a real test double, or -- simpler here --
    # by seeding a conversions row directly at b's natural destination under
    # a DIFFERENT source_file_id). Must be a THIRD source file, not source_a
    # again: source_a already occupies its own (source_file_id, version=1)
    # slot above, and conversions.UNIQUE(source_file_id, version_number)
    # would reject a second row for the same pair.
    source_c = _seed_source_file(conn, "Folder/SomeOtherFile.pdf")
    _seed_conversion(conn, source_c, "Folder/OtherNotes.pdf.md", status="superseded")

    result, dest = gauntlet.run_gate2(conn, "Folder/OtherNotes.pdf", source_b, version=1, cfg=Config())
    assert result.passed is True
    assert dest != "Folder/OtherNotes.pdf.md"
    event = conn.execute("SELECT event_type FROM events WHERE event_type = 'naming_collision_resolved'").fetchone()
    assert event is not None


def test_gate2_trims_a_collision_suffix_that_would_exceed_the_threshold(conn):
    # A dest exactly at budget before the collision suffix is appended --
    # the length check earlier in run_gate2 runs BEFORE resolve_collision,
    # so it can't have caught an overage the suffix itself introduces.
    # "OtherNotes.pdf.md" (17 chars) fits; "OtherNotes.pdf~XXXXXXXX.md"
    # (26 chars, after the collision suffix) doesn't -- threshold is set
    # squarely between the two so only the post-collision form overflows.
    prefix_len = len(str(Config().converted_root)) + 1
    threshold = prefix_len + 20
    cfg = Config(long_path_threshold_chars=threshold)

    source_a = _seed_source_file(conn, "Original.pdf")
    source_b = _seed_source_file(conn, "OtherNotes.pdf")
    _seed_conversion(conn, source_a, "OtherNotes.pdf.md")  # occupies b's natural dest

    result, dest = gauntlet.run_gate2(conn, "OtherNotes.pdf", source_b, version=1, cfg=cfg)

    assert result.passed is True
    assert dest != "OtherNotes.pdf.md"
    assert prefix_len + len(dest) <= threshold
    assert dest.endswith(".md")


def test_gate2_does_not_treat_own_prior_versions_as_a_collision(conn):
    source_id = _seed_source_file(conn, "Folder/Notes.pdf")
    _seed_conversion(conn, source_id, "Folder/Notes.pdf.md", status="superseded")
    result, dest = gauntlet.run_gate2(conn, "Folder/Notes.pdf", source_id, version=2, cfg=Config())
    assert result.passed is True
    assert dest == "Folder/Notes.pdf.v2.md"


def test_gate2_rejects_a_path_that_would_resolve_outside_converted_root(conn):
    source_id = _seed_source_file(conn, "a.pdf")
    result, dest = gauntlet.run_gate2(conn, "a.pdf", source_id, version=1, cfg=Config())
    assert ".." not in dest
    assert not dest.startswith("/")
    assert not dest.startswith("\\")
