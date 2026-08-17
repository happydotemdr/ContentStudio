"""Dispatches a staged local file to the firecrawl-py SDK. Reads
FIRECRAWL_API_KEY from the environment automatically (already set as a
Windows user environment variable per SETUP.md) -- run_ingest_cron.py runs
unattended under Task Scheduler, so nothing here can assume an interactive
Claude Code session."""
from __future__ import annotations

import dataclasses
import time
from pathlib import Path

_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
}

# firecrawl.v2.utils.error_handler maps 400/401/402/403/408/429/500 onto typed
# FirecrawlError subclasses with a real .status_code attribute; every other
# status (including 502/503) falls to its `else` branch, which still raises a
# bare FirecrawlError carrying the real status_code. 408/429/500/502/503 are
# transient (timeout, rate limit, server-side, bad gateway, unavailable), so
# worth retrying with backoff -- 502/503 are included for parity with
# drive_client.py's own _RETRYABLE_STATUSES. 400/401/402/403 are not: retrying
# a bad file, a bad key, an exhausted plan, or an unsupported site wastes
# attempts on something that will never succeed. A raw requests-level
# ConnectionError/Timeout (e.g. "An existing connection was forcibly closed by
# the remote host", observed in the first real production run against this
# corpus) never reaches error_handler at all -- it has no .status_code -- so
# it's checked by type, not by attribute, alongside the HTTP-status check.
_RETRYABLE_STATUSES = {408, 429, 500, 502, 503}


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
    import requests
    from firecrawl import Firecrawl
    from firecrawl.v2.types import ParseOptions

    client = Firecrawl()
    content_type = _CONTENT_TYPES.get(source_type)

    parsed = None
    for attempt in range(cfg.firecrawl_retry_max_attempts):
        try:
            parsed = client.parse(
                staged_path.read_bytes(),
                filename=staged_path.name,
                content_type=content_type,
                options=ParseOptions(formats=["markdown"]),
            )
            break
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            transient = status in _RETRYABLE_STATUSES or isinstance(
                exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
            )
            if not transient or attempt == cfg.firecrawl_retry_max_attempts - 1:
                error = str(exc)
                if source_type == "ppt":
                    return ConversionResult(success=False, markdown_body=None, tool="firecrawl-parse",
                                             error=f"unsupported_type: {error}")
                return ConversionResult(success=False, markdown_body=None, tool="firecrawl-parse", error=error)
            time.sleep(cfg.firecrawl_retry_base_delay_s * (2 ** attempt))

    if not parsed.markdown:
        return ConversionResult(success=False, markdown_body=None, tool="firecrawl-parse", error="empty_markdown_returned")

    return ConversionResult(success=True, markdown_body=parsed.markdown, tool="firecrawl-parse", error=None)
