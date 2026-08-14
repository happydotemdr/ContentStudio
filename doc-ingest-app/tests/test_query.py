from doc_ingest import query


def _seed(conn):
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
        "VALUES ('a.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
    )
    source_id = conn.execute("SELECT id FROM source_files WHERE rel_path = 'a.pdf'").fetchone()[0]
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "conversion_tool, converted_at) VALUES (?, 1, 'a.pdf.md', 'current', 'pdf', 'firecrawl-parse', ?)",
        (source_id, now),
    )
    conversion_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO conversions_fts (conversion_id, source_rel_path, output_path, body) "
        "VALUES (?, 'a.pdf', 'a.pdf.md', 'coaching session about goal setting')",
        (conversion_id,),
    )
    conn.commit()


def test_search_matches_body_text(conn):
    _seed(conn)
    results = query.search(conn, text="goal setting", source_type=None, status="current", limit=10)
    assert len(results) == 1
    assert results[0]["output_path"] == "a.pdf.md"


def test_search_filters_by_source_type(conn):
    _seed(conn)
    results = query.search(conn, text=None, source_type="docx", status="current", limit=10)
    assert results == []


def test_search_excludes_superseded_by_default(conn):
    _seed(conn)
    conn.execute("UPDATE conversions SET status = 'superseded'")
    conn.commit()
    results = query.search(conn, text=None, source_type=None, status="current", limit=10)
    assert results == []
    all_results = query.search(conn, text=None, source_type=None, status="all", limit=10)
    assert len(all_results) == 1


def test_search_excludes_missing_sourced_results_by_default(conn):
    _seed(conn)
    conn.execute("UPDATE source_files SET classification = 'missing' WHERE rel_path = 'a.pdf'")
    conn.commit()
    results = query.search(conn, text=None, source_type=None, status="current", limit=10)
    assert results == []
    all_results = query.search(conn, text=None, source_type=None, status="all", limit=10)
    assert len(all_results) == 1
    assert all_results[0]["source_missing"] is True


def test_search_marks_a_present_source_as_not_missing(conn):
    _seed(conn)
    results = query.search(conn, text=None, source_type=None, status="current", limit=10)
    assert results[0]["source_missing"] is False
