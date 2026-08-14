"""Two independent, purely mechanical gates -- no LLM evaluation anywhere.
A failure records a specific failure_reason and blocks the write; nothing is
silently dropped, matching pipeline_app.db's _quarantine_unknown_platforms
migration's quarantine-don't-discard pattern (spec §8, cited narrowly to
that one precedent, not as a repo-wide convention)."""
from __future__ import annotations

import dataclasses
import re

from doc_ingest import frontmatter

_CODE_FENCE_RE = re.compile(r"^```", re.MULTILINE)
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$", re.MULTILINE)


@dataclasses.dataclass(frozen=True)
class GauntletResult:
    passed: bool
    failure_reason: str | None = None


def _count_output_table_blocks(body: str) -> int:
    """One markdown table == one separator row (the `|---|---|` line). Used
    as a proxy for both 'how many sheets' (xlsx/gsheet) and 'how many
    tables' (docx/gdoc) in firecrawl's markdown output. A heuristic, not
    verified against a real firecrawl conversion sample -- calibrate the
    tolerance bands against real corpus output before trusting this in
    production (spec §15)."""
    return len(_TABLE_SEPARATOR_RE.findall(body))


def _count_output_table_rows(body: str) -> int:
    all_rows = len(_TABLE_ROW_RE.findall(body))
    separators = len(_TABLE_SEPARATOR_RE.findall(body))
    header_rows = separators  # exactly one header row precedes each separator
    return max(all_rows - separators - header_rows, 0)


def _universal_checks(assembled_markdown: str, cfg) -> GauntletResult | None:
    try:
        fm, body = frontmatter.parse(assembled_markdown)
    except Exception:
        return GauntletResult(False, "malformed_frontmatter")

    if not body.strip():
        return GauntletResult(False, "empty_body")

    for field in frontmatter.REQUIRED_BASE_FIELDS:
        if field not in fm:
            return GauntletResult(False, "malformed_frontmatter")

    replacement_ratio = body.count("�") / max(len(body), 1)
    if replacement_ratio > cfg.replacement_char_ratio_max:
        return GauntletResult(False, "encoding_garbled")

    if len(_CODE_FENCE_RE.findall(body)) % 2 != 0:
        return GauntletResult(False, "unbalanced_code_fences")

    return None  # all universal checks passed


def run_gate1(source_type: str, source_size_bytes: int, assembled_markdown: str, independent_metadata: dict, cfg) -> GauntletResult:
    if source_type == "ppt" and "conversion_error" in independent_metadata:
        return GauntletResult(False, independent_metadata["conversion_error"])

    universal_failure = _universal_checks(assembled_markdown, cfg)
    if universal_failure is not None:
        return universal_failure

    _, body = frontmatter.parse(assembled_markdown)

    if source_type in ("docx", "xlsx", "txt", "md"):
        ratio = len(body.encode("utf-8")) / max(source_size_bytes, 1)
        if ratio < cfg.size_ratio_floor:
            return GauntletResult(False, "below_size_ratio_floor")

    if source_type == "pdf":
        page_count = independent_metadata.get("page_count")
        if page_count:
            words_per_page = len(body.split()) / page_count
            if words_per_page < cfg.scanned_pdf_words_per_page_floor:
                return GauntletResult(False, "likely_scanned_no_text_layer")

    if source_type in ("docx", "gdoc"):
        source_wc = independent_metadata.get("source_word_count")
        if source_wc is not None:
            output_wc = len(body.split())
            low = source_wc * (1 - cfg.word_count_tolerance_pct)
            high = source_wc * (1 + cfg.word_count_tolerance_pct)
            if not (low <= output_wc <= high):
                return GauntletResult(False, "word_count_parity_failed")

        source_tables = independent_metadata.get("source_table_count")
        if source_tables is not None:
            if _count_output_table_blocks(body) != source_tables:
                return GauntletResult(False, "table_count_mismatch")

    if source_type in ("xlsx", "gsheet"):
        source_sheets = independent_metadata.get("source_sheet_count")
        if source_sheets is not None:
            output_sheets = _count_output_table_blocks(body)
            if abs(source_sheets - output_sheets) > cfg.sheet_count_tolerance:
                return GauntletResult(False, "sheet_count_mismatch")

        source_rows = independent_metadata.get("source_row_count")
        if source_rows is not None:
            output_rows = _count_output_table_rows(body)
            low = source_rows * (1 - cfg.row_count_tolerance_pct)
            high = source_rows * (1 + cfg.row_count_tolerance_pct)
            if not (low <= output_rows <= high):
                return GauntletResult(False, "row_count_mismatch")

    return GauntletResult(True, None)
