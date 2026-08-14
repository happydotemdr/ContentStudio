from doc_ingest.config import Config
from doc_ingest import frontmatter, gauntlet


def _assembled(body="A perfectly ordinary converted document with real words in it."):
    fm = frontmatter.build_frontmatter({
        "source_path": "a.txt", "source_type": "txt", "source_hash": "h",
        "source_modified_at": "2026-08-01T00:00:00+00:00", "converted_at": "2026-08-13T00:00:00+00:00",
        "conversion_tool": "passthrough", "version": 1, "status": "current",
        "business_line": "freedom2beu", "gauntlet_passed_at": "2026-08-13T00:00:01+00:00",
    }, {})
    return frontmatter.serialize(fm, body)


def test_universal_check_rejects_empty_body():
    cfg = Config()
    result = gauntlet.run_gate1("txt", 100, _assembled(body=""), {}, cfg)
    assert result.passed is False
    assert result.failure_reason == "empty_body"


def test_universal_check_rejects_malformed_frontmatter():
    cfg = Config()
    broken = "---\nsource_path: [unterminated\n---\nbody"
    result = gauntlet.run_gate1("txt", 100, broken, {}, cfg)
    assert result.passed is False
    assert result.failure_reason == "malformed_frontmatter"


def test_universal_check_rejects_high_replacement_char_ratio():
    cfg = Config(replacement_char_ratio_max=0.01)
    garbled_body = "�" * 50 + "ok text " * 5
    result = gauntlet.run_gate1("txt", 100, _assembled(body=garbled_body), {}, cfg)
    assert result.passed is False
    assert result.failure_reason == "encoding_garbled"


def test_universal_check_rejects_unbalanced_code_fences():
    body = "```python\nprint('hi')\n" + "more text with no closing fence"
    result = gauntlet.run_gate1("txt", 100, _assembled(body=body), {}, Config())
    assert result.passed is False
    assert result.failure_reason == "unbalanced_code_fences"


def test_universal_checks_pass_for_a_clean_document():
    result = gauntlet.run_gate1("txt", 100, _assembled(), {}, Config())
    assert result.passed is True


def test_size_ratio_floor_applies_to_docx_and_rejects_a_truncated_conversion():
    cfg = Config(size_ratio_floor=0.05)
    tiny_body = "x"
    result = gauntlet.run_gate1("docx", 100000, _assembled(body=tiny_body), {"word_count": 1}, cfg)
    assert result.passed is False
    assert result.failure_reason == "below_size_ratio_floor"


def test_size_ratio_floor_does_not_apply_to_pdf():
    cfg = Config(size_ratio_floor=0.05)
    # A 4MB PDF producing a tiny amount of markdown is normal, not truncation
    # (spec §8). page_count=10 with this body's ~120 words gives ~12
    # words/page, safely above the scanned-PDF floor too, so this test
    # isolates the size-ratio-exemption claim from the scanned-PDF check.
    result = gauntlet.run_gate1(
        "pdf", 4_000_000,
        _assembled(body="short markdown from a dense pdf " * 20),
        {"page_count": 10}, cfg,
    )
    assert result.passed is True


def test_pdf_flags_likely_scanned_no_text_layer():
    # words_per_page is NOT passed in -- Gate 1 computes it itself as
    # len(body.split()) / page_count, from the actual assembled markdown,
    # never from a value the caller hands in (that was the bug: nothing
    # upstream of Gate 1 ever produced a "word_count_per_page" key, so this
    # check silently never fired).
    cfg = Config(scanned_pdf_words_per_page_floor=3.0)
    result = gauntlet.run_gate1(
        "pdf", 500_000, _assembled(body="a few words only"),
        {"page_count": 20}, cfg,
    )
    assert result.passed is False
    assert result.failure_reason == "likely_scanned_no_text_layer"


def test_pdf_passes_with_a_healthy_words_per_page():
    cfg = Config(scanned_pdf_words_per_page_floor=3.0)
    body = " ".join(["word"] * 200)  # 200 words / 5 pages = 40 words/page
    result = gauntlet.run_gate1("pdf", 500_000, _assembled(body=body), {"page_count": 5}, cfg)
    assert result.passed is True


def test_docx_word_count_parity_within_tolerance():
    # size_ratio_floor=0.0 isolates the word-count-parity check from the
    # size-ratio-floor check that ALSO applies to docx (spec §8) -- these
    # tiny synthetic bodies are nowhere near 5% of a real 50000-byte source,
    # and without disabling the floor here every one of these tests fails on
    # below_size_ratio_floor before it ever reaches the check it's named for.
    cfg = Config(word_count_tolerance_pct=0.15, size_ratio_floor=0.0)
    body = " ".join(["word"] * 95)
    result = gauntlet.run_gate1("docx", 50000, _assembled(body=body), {"source_word_count": 100}, cfg)
    assert result.passed is True


def test_docx_word_count_parity_rejects_outside_tolerance():
    cfg = Config(word_count_tolerance_pct=0.15, size_ratio_floor=0.0)
    body = " ".join(["word"] * 40)
    result = gauntlet.run_gate1("docx", 50000, _assembled(body=body), {"source_word_count": 100}, cfg)
    assert result.passed is False
    assert result.failure_reason == "word_count_parity_failed"


def test_docx_table_count_parity_fails_on_mismatch():
    # separator-row count in the OUTPUT markdown is the proxy for "how many
    # tables" (spec §15 flags this as a heuristic needing calibration
    # against a real firecrawl conversion sample -- see gauntlet.py's
    # _count_output_table_blocks docstring).
    cfg = Config(word_count_tolerance_pct=0.15, size_ratio_floor=0.0)
    body = "no tables here at all, just prose " * 5  # 35 words, no "|---|" rows
    result = gauntlet.run_gate1(
        "docx", 50000, _assembled(body=body),
        {"source_word_count": 35, "source_table_count": 2}, cfg,
    )
    assert result.passed is False
    assert result.failure_reason == "table_count_mismatch"


def test_docx_table_count_parity_passes_on_match():
    cfg = Config(word_count_tolerance_pct=0.15, size_ratio_floor=0.0)
    body = "words words words\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
    # len(body.split()) counts every whitespace-separated token, including
    # the pipe/cell tokens inside the table -- 3 prose words + 5 header-row
    # tokens ("|","A","|","B","|") + 1 separator token + 5 data-row tokens
    # ("|","1","|","2","|") = 14. Computed explicitly here rather than
    # guessed, since it's exactly the kind of off-by-a-lot mistake that
    # silently makes a test assert nothing.
    assert len(body.split()) == 14
    result = gauntlet.run_gate1(
        "docx", 50000, _assembled(body=body),
        {"source_word_count": 14, "source_table_count": 1}, cfg,
    )
    assert result.passed is True


def test_xlsx_sheet_and_row_count_parity():
    # One markdown table (one "|---|" separator row) == one sheet; rows are
    # counted from the same table, minus its own header and separator lines.
    # size_ratio_floor=0.0 for the same reason as the docx tests above --
    # xlsx is also in the size-ratio-floor type list (spec §8).
    cfg = Config(row_count_tolerance_pct=0.05, sheet_count_tolerance=0, size_ratio_floor=0.0)
    body = (
        "## Sheet1\n\n| A | B |\n|---|---|\n"
        + "\n".join(f"| {i} | {i * 2} |" for i in range(10))
        + "\n"
    )
    result = gauntlet.run_gate1(
        "xlsx", 20000, _assembled(body=body),
        {"source_sheet_count": 1, "source_row_count": 10}, cfg,
    )
    assert result.passed is True


def test_xlsx_sheet_count_mismatch_fails():
    cfg = Config(size_ratio_floor=0.0)
    body = "## Sheet1\n\n| A |\n|---|\n| 1 |\n"
    result = gauntlet.run_gate1(
        "xlsx", 20000, _assembled(body=body),
        {"source_sheet_count": 3, "source_row_count": 1}, cfg,
    )
    assert result.passed is False
    assert result.failure_reason == "sheet_count_mismatch"


def test_ppt_unsupported_is_a_gate1_failure_not_a_crash():
    result = gauntlet.run_gate1("ppt", 20000, "", {"conversion_error": "unsupported_type: bad format"}, Config())
    assert result.passed is False
    assert result.failure_reason == "unsupported_type: bad format"


def test_txt_md_identity_copy_only_gets_universal_checks():
    # md IS in the size-ratio-floor type list (spec §8's own bullet 2), but
    # since worker.py routes txt/md through a verbatim pass-through (Task 15),
    # the output body is always ~the same size as the source -- the floor
    # is technically active for this type but never the thing that fails it.
    # Proven here with a source_size_bytes deliberately larger than what the
    # floor would tolerate for a truncated conversion, so this test would
    # catch the floor firing if that assumption were ever wrong.
    cfg = Config(size_ratio_floor=0.5)
    result = gauntlet.run_gate1("md", 100, _assembled(), {}, cfg)  # body is ~60 bytes, ratio ~0.6
    assert result.passed is True
