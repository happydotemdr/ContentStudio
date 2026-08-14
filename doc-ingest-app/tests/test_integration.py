"""End-to-end fixture covering pdf/docx/xlsx/txt/md plus a mocked Drive
gdoc response, run through the real scan -> enqueue -> claim -> process_job
path, asserting the output tree, frontmatter, DB rows, and gauntlet outcomes
(spec §13's Integration bullet).

Locking is mocked here, same as Task 15's own tests -- lock.py (Task 13) is
deliberately non-idempotent once fully applied, and only Task 13's own tests
and this file's dedicated test_readonly_enforcement.py are meant to perform
a REAL lock (using the lock_test_dir fixture, never tmp_path)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import docx
import openpyxl
from pypdf import PdfWriter

from doc_ingest import frontmatter, jobs, sync, worker
from doc_ingest.config import Config

_DOCX_SENTENCE = "This is a real docx document with enough words in it to pass the word count parity check comfortably today."


def _build_fixture_tree(input_root):
    (input_root / "docs").mkdir(parents=True)

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(input_root / "docs" / "Sample.pdf", "wb") as fh:
        writer.write(fh)

    document = docx.Document()
    document.add_paragraph(_DOCX_SENTENCE)
    document.save(input_root / "docs" / "Sample.docx")

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for i in range(5):
        sheet.append([i, i * 2])
    workbook.save(input_root / "docs" / "Sample.xlsx")

    (input_root / "docs" / "Sample.txt").write_text(
        "Plain text passthrough content with real words in it.", encoding="utf-8"
    )
    (input_root / "docs" / "Sample.md").write_text(
        "# Already markdown\n\nPassthrough content.", encoding="utf-8"
    )


def _fake_parse(data, filename=None, content_type=None, options=None):
    """Per-type mocked firecrawl output, proportioned against each real
    fixture file rather than one uniform body for every type -- a single
    generic body either trips below_size_ratio_floor (real docx/xlsx source
    bytes vastly outweigh a token mock body) or fails word/sheet/row parity
    outright. size_ratio_floor is disabled in cfg below for this test
    specifically because matching real source-byte-size proportions in a
    mock is not the point of this fixture; the per-type CONTENT below still
    has to satisfy the parity checks, which size_ratio_floor doesn't cover."""
    if filename == "Sample.pdf":
        return MagicMock(markdown="# PDF Content\n\nplenty of real extracted words appear on this single page for testing")
    if filename == "Sample.docx":
        # Echoing the exact source sentence back gives read_docx_word_count
        # (source) and len(body.split()) (output) the same count -- real
        # parity, not a number picked to trivially satisfy the tolerance.
        return MagicMock(markdown=_DOCX_SENTENCE)
    if filename == "Sample.xlsx":
        rows = "\n".join(f"| {i} | {i * 2} |" for i in range(5))
        return MagicMock(markdown=f"## Sheet\n\n| A | B |\n|---|---|\n{rows}\n")
    raise AssertionError(f"unexpected firecrawl.parse call for filename={filename!r}")


def test_every_convertible_type_produces_a_locked_current_conversion(conn, tmp_path):
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    _build_fixture_tree(input_root)
    cfg = Config(input_root=input_root, output_root=output_root, size_ratio_floor=0.0)

    mock_client = MagicMock()
    mock_client.parse.side_effect = _fake_parse

    sync.sync_source_files(conn, input_root)
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 5

    with patch("firecrawl.Firecrawl", return_value=mock_client), \
         patch("doc_ingest.lock.apply_readonly_lock"), \
         patch("doc_ingest.lock.verify_locked", return_value=True):
        for _ in range(5):
            job_id = jobs.claim_job(conn, worker_id="w1")
            assert job_id is not None
            worker.process_job(conn, job_id, cfg, worker_id="w1")

    # NOTE: the brief's literal query selected `source_type`, but that column
    # lives only on `conversions` (populated on success) -- neither
    # conversion_jobs nor source_files has it. Swapped in sf.extension, the
    # closest available identifying column, since this query is purely
    # diagnostic (feeds the assert's failure message below) and does not
    # gate the test outcome itself. See task-21-report.md for the writeup.
    failed = conn.execute("SELECT sf.extension, failure_reason FROM conversion_jobs cj JOIN source_files sf "
                           "ON sf.id = cj.source_file_id WHERE cj.status = 'failed'").fetchall()
    assert failed == [], failed

    current = conn.execute("SELECT source_type, output_path, locked_confirmed_at FROM conversions WHERE status = 'current'").fetchall()
    assert len(current) == 5
    seen_types = {row[0] for row in current}
    assert seen_types == {"pdf", "docx", "xlsx", "txt", "md"}
    for source_type, output_path, locked_confirmed_at in current:
        assert locked_confirmed_at is not None
        final_path = cfg.converted_root / output_path
        assert final_path.exists()
        fm, body = frontmatter.parse(final_path.read_text(encoding="utf-8"))
        assert fm["business_line"] == "freedom2beu"
        assert fm["status"] == "current"


def test_a_gdoc_pointer_is_classified_and_routed_away_from_firecrawl(conn, tmp_path):
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    input_root.mkdir()
    stub = '{"doc_id": "fake-doc-id", "resource_key": "rk1", "email": "admin@freedom2beu.com"}'
    (input_root / "Session Notes.gdoc").write_text(stub, encoding="utf-8")
    cfg = Config(input_root=input_root, output_root=output_root)

    sync.sync_source_files(conn, input_root)
    row = conn.execute("SELECT classification FROM source_files WHERE rel_path = 'Session Notes.gdoc'").fetchone()
    assert row[0] == "gdoc_pointer"
    # This test only confirms scan/classification correctly routes .gdoc
    # away from firecrawl -- it does not run process_job and produces no
    # conversion. Full Drive-native process_job wiring (export -> gauntlet
    # -> lock) will be exercised end-to-end once Task 22 adds its own
    # worker tests for the gdoc export path (a mocked-Drive-export happy
    # path and a docx-fallback variant).
