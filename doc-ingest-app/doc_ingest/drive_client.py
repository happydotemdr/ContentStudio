"""OAuth, batched metadata lookups, and Docs/Sheets export. Internal-only
OAuth consent screen (see SETUP.md) -- an External/Testing app's refresh
tokens expire after 7 days, which would silently break the 30-minute cron
about a week after setup (spec §9)."""
from __future__ import annotations

import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

from doc_ingest.convert import ConversionResult

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

_RETRYABLE_STATUSES = {429, 500, 502, 503}


def get_credentials(token_path: Path, client_secret_path: Path) -> Credentials:
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _with_retry(fn, cfg):
    last_error = None
    for attempt in range(cfg.drive_retry_max_attempts):
        try:
            return fn()
        except HttpError as exc:
            status = getattr(exc.resp, "status", None)
            if status not in _RETRYABLE_STATUSES:
                raise
            last_error = exc
            time.sleep(cfg.drive_retry_base_delay_s * (2 ** attempt))
    raise last_error


def build_batch_metadata(service, doc_ids: list[str], cfg) -> dict[str, dict]:
    results: dict[str, dict] = {}

    def _callback(request_id, response, exception):
        if exception is None:
            results[response["id"]] = response

    for start in range(0, len(doc_ids), cfg.drive_metadata_batch_size):
        chunk = doc_ids[start:start + cfg.drive_metadata_batch_size]
        # No callback= here: BatchHttpRequest fires the batch-level default
        # callback AND each request's own callback for every completed
        # request, not one-or-the-other. Registering _callback in both
        # places would invoke it twice per doc_id.
        batch = service.new_batch_http_request()
        for doc_id in chunk:
            batch.add(
                service.files().get(fileId=doc_id, fields="id,name,modifiedTime,mimeType"),
                callback=_callback,
            )
        _with_retry(batch.execute, cfg)

    return results


def export_google_doc(service, doc_id: str, dest_path: Path, cfg) -> ConversionResult:
    # cfg.drive_export_size_cap_bytes is not compared against here on
    # purpose: Drive enforces its own ~10MB export cap server-side and
    # returns an HttpError for a document that exceeds it, which this
    # `except Exception` already catches and routes to the docx fallback --
    # there is no client-visible "export size" to check ahead of the
    # attempt. The config value exists to name and tune the fallback
    # trigger's real-world cause in tests and docs, not to gate a
    # client-side pre-check that Drive doesn't expose the data for.
    try:
        content = _with_retry(
            lambda: service.files().export(fileId=doc_id, mimeType="text/markdown").execute(), cfg,
        )
        dest_path.write_bytes(content)
        return ConversionResult(success=True, markdown_body=content.decode("utf-8"), tool="google-docs-export", error=None)
    except Exception:
        pass  # format unavailable OR the doc exceeded Drive's export size cap -- fall back to docx export below

    content = _with_retry(
        lambda: service.files().export(
            fileId=doc_id, mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ).execute(), cfg,
    )
    dest_path.write_bytes(content)
    return ConversionResult(success=True, markdown_body=None, tool="google-docs-export-docx-fallback", error=None)


def export_google_sheet(service, doc_id: str, dest_path: Path, cfg) -> ConversionResult:
    content = _with_retry(
        lambda: service.files().export(
            fileId=doc_id, mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ).execute(), cfg,
    )
    dest_path.write_bytes(content)
    return ConversionResult(success=True, markdown_body=None, tool="google-sheets-export", error=None)
