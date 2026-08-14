from doc_ingest import manifest


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
    conn.commit()


def test_regenerate_writes_csv_and_md(conn, tmp_path):
    _seed(conn)
    csv_path, md_path = manifest.regenerate(conn, tmp_path)
    assert csv_path.exists()
    assert md_path.exists()
    assert "a.pdf.md" in csv_path.read_text(encoding="utf-8")
    assert "a.pdf.md" in md_path.read_text(encoding="utf-8")
