"""Dispatches a staged local file to the firecrawl-py SDK. Reads
FIRECRAWL_API_KEY from the environment automatically (already set as a
Windows user environment variable per SETUP.md) -- run_ingest_cron.py runs
unattended under Task Scheduler, so nothing here can assume an interactive
Claude Code session."""
from __future__ import annotations

import dataclasses
from pathlib import Path

_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
}


@dataclasses.dataclass(frozen=True)
class ConversionResult:
    success: bool
    markdown_body: str | None
    tool: str
    error: str | None


def convert_local_file(staged_path: Path, source_type: str, cfg) -> ConversionResult:
    size = staged_path.stat().st_size
    if size > cfg.oversized_file_cap_bytes:
        return ConversionResult(success=False, markdown_body=None, tool="firecrawl-parse", error="oversized_unsupported")

    # Imported here, not at module scope, so tests that patch
    # "firecrawl.Firecrawl" via unittest.mock.patch intercept the same
    # attribute this function resolves at call time.
    from firecrawl import Firecrawl
    from firecrawl.v2.types import ParseOptions

    client = Firecrawl()
    content_type = _CONTENT_TYPES.get(source_type)

    try:
        parsed = client.parse(
            staged_path.read_bytes(),
            filename=staged_path.name,
            content_type=content_type,
            options=ParseOptions(formats=["markdown"]),
        )
    except Exception as exc:
        error = str(exc)
        if source_type == "ppt":
            return ConversionResult(success=False, markdown_body=None, tool="firecrawl-parse",
                                     error=f"unsupported_type: {error}")
        return ConversionResult(success=False, markdown_body=None, tool="firecrawl-parse", error=error)

    if not parsed.markdown:
        return ConversionResult(success=False, markdown_body=None, tool="firecrawl-parse", error="empty_markdown_returned")

    return ConversionResult(success=True, markdown_body=parsed.markdown, tool="firecrawl-parse", error=None)
