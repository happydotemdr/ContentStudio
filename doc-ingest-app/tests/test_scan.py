from pathlib import Path

from doc_ingest import scan


def test_sniff_signature_detects_pdf(tmp_path):
    f = tmp_path / "noext"
    f.write_bytes(b"%PDF-1.4\n%rest of a fake pdf body")
    assert scan.sniff_signature(f) == "pdf"


def test_sniff_signature_detects_png(tmp_path):
    f = tmp_path / "noext"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    assert scan.sniff_signature(f) == "png"


def test_sniff_signature_detects_jpeg(tmp_path):
    f = tmp_path / "noext"
    f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
    assert scan.sniff_signature(f) == "jpg"


def test_sniff_signature_detects_mp4_ftyp_box(tmp_path):
    f = tmp_path / "noext"
    f.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20)
    assert scan.sniff_signature(f) == "mp4"


def test_sniff_signature_detects_mov_ftyp_box(tmp_path):
    f = tmp_path / "noext"
    f.write_bytes(b"\x00\x00\x00\x14ftypqt  " + b"\x00" * 20)
    assert scan.sniff_signature(f) == "mov"


def test_sniff_signature_returns_none_for_unrecognized_bytes(tmp_path):
    f = tmp_path / "noext"
    f.write_bytes(b"not a known signature at all")
    assert scan.sniff_signature(f) is None


def test_sniff_signature_never_opens_for_writing(tmp_path, monkeypatch):
    f = tmp_path / "noext"
    f.write_bytes(b"%PDF-1.4")
    real_open = open

    def _guarded_open(path, mode="r", *a, **kw):
        assert "w" not in mode and "a" not in mode and "+" not in mode
        return real_open(path, mode, *a, **kw)

    monkeypatch.setattr("builtins.open", _guarded_open)
    scan.sniff_signature(f)


def test_classify_convertible_extension():
    assert scan.classify("pdf", sniffed=None) == "convertible"
    assert scan.classify("docx", sniffed=None) == "convertible"
    assert scan.classify("xlsx", sniffed=None) == "convertible"
    assert scan.classify("txt", sniffed=None) == "convertible"
    assert scan.classify("md", sniffed=None) == "convertible"
    assert scan.classify("ppt", sniffed=None) == "convertible"


def test_classify_gdoc_and_gsheet_pointers():
    assert scan.classify("gdoc", sniffed=None) == "gdoc_pointer"
    assert scan.classify("gsheet", sniffed=None) == "gdoc_pointer"


def test_classify_catalog_only_images():
    assert scan.classify("png", sniffed=None) == "catalog_only"
    assert scan.classify("jpg", sniffed=None) == "catalog_only"


def test_classify_excluded_media():
    assert scan.classify("mov", sniffed=None) == "excluded_media"
    assert scan.classify("mp4", sniffed=None) == "excluded_media"


def test_classify_desktop_ini_is_blocked():
    assert scan.classify("ini", sniffed=None) == "blocked_unknown"


def test_classify_extensionless_uses_sniffed_signature():
    assert scan.classify("", sniffed="pdf") == "convertible"
    assert scan.classify("", sniffed="png") == "catalog_only"
    assert scan.classify("", sniffed="mp4") == "excluded_media"
    assert scan.classify("", sniffed=None) == "blocked_unknown"


def test_walk_source_tree_yields_every_file(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "sub" / "b.docx").write_bytes(b"fake docx bytes")
    entries = list(scan.walk_source_tree(tmp_path))
    rel_paths = sorted(e.rel_path for e in entries)
    assert rel_paths == ["a.pdf", "sub/b.docx"]


def test_walk_source_tree_never_writes_or_deletes(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake")
    before = (tmp_path / "a.pdf").read_bytes()
    list(scan.walk_source_tree(tmp_path))
    after = (tmp_path / "a.pdf").read_bytes()
    assert before == after
    assert (tmp_path / "a.pdf").exists()


def test_walk_source_tree_computes_a_hash_for_a_convertible_file(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake")
    entries = list(scan.walk_source_tree(tmp_path))
    assert entries[0].content_hash is not None


def test_walk_source_tree_skips_hashing_excluded_media(tmp_path):
    # Hashing every file unconditionally would mean sha256'ing every video
    # in the real corpus -- up to 1.1GB each -- for a value nothing
    # downstream ever reads (excluded_media is never enqueued, spec §2).
    (tmp_path / "a.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20)
    entries = list(scan.walk_source_tree(tmp_path))
    assert entries[0].content_hash is None
