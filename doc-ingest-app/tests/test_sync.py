from doc_ingest import sync


def test_sync_inserts_new_files(conn, tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake")
    sync.sync_source_files(conn, tmp_path)
    row = conn.execute("SELECT classification FROM source_files WHERE rel_path = 'a.pdf'").fetchone()
    assert row[0] == "convertible"


def test_sync_marks_previously_seen_file_as_missing(conn, tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    sync.sync_source_files(conn, tmp_path)
    f.unlink()
    sync.sync_source_files(conn, tmp_path)
    row = conn.execute("SELECT classification FROM source_files WHERE rel_path = 'a.pdf'").fetchone()
    assert row[0] == "missing"


def test_sync_reclassifies_a_missing_file_that_reappears(conn, tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    sync.sync_source_files(conn, tmp_path)
    f.unlink()
    sync.sync_source_files(conn, tmp_path)
    f.write_bytes(b"%PDF-1.4 fake again")
    sync.sync_source_files(conn, tmp_path)
    row = conn.execute("SELECT classification FROM source_files WHERE rel_path = 'a.pdf'").fetchone()
    assert row[0] == "convertible"


def test_sync_updates_content_hash_when_file_changes(conn, tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4 version one")
    sync.sync_source_files(conn, tmp_path)
    hash1 = conn.execute("SELECT content_hash FROM source_files WHERE rel_path = 'a.pdf'").fetchone()[0]
    f.write_bytes(b"%PDF-1.4 version two, different content")
    sync.sync_source_files(conn, tmp_path)
    hash2 = conn.execute("SELECT content_hash FROM source_files WHERE rel_path = 'a.pdf'").fetchone()[0]
    assert hash1 != hash2


def test_sync_returns_counts_by_classification(conn, tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "b.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10)
    counts = sync.sync_source_files(conn, tmp_path)
    assert counts["convertible"] == 1
    assert counts["catalog_only"] == 1


def test_sync_never_writes_into_the_input_tree(conn, tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    sync.sync_source_files(conn, tmp_path)
    after = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after
