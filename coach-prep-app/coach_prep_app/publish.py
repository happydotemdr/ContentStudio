# coach-prep-app/coach_prep_app/publish.py
"""Creates the draft as a Google Doc in the single, non-client-scoped
Pending Review folder. NEVER writes directly into a client's real Drive
folder -- a human moving it there is the approval step (design spec's
'Publish (draft, not final)')."""
from __future__ import annotations

import datetime as dt


def draft_title(client_display_name: str, meeting_date: dt.date) -> str:
    return f"DRAFT — Coach Prep — {client_display_name} — {meeting_date.isoformat()} — review before use"


def publish_draft(
    drive_service, pending_review_folder_id: str, client_display_name: str,
    meeting_date: dt.date, markdown_body: str,
) -> str:
    from googleapiclient.http import MediaInMemoryUpload

    file_metadata = {
        "name": draft_title(client_display_name, meeting_date),
        "parents": [pending_review_folder_id],
        "mimeType": "application/vnd.google-apps.document",
    }
    # text/markdown, not text/plain. Drive converts a markdown upload into a
    # real Doc -- headings, bold, bullets, tables. Uploaded as text/plain it
    # was stored verbatim, so Ryan opened the draft to literal "## Part 1"
    # characters. The round trip stays symmetric: doc-ingest already exports
    # Docs back OUT as text/markdown (drive_client.export_google_doc), so the
    # ingest cron recovers the same markdown it published.
    media = MediaInMemoryUpload(markdown_body.encode("utf-8"), mimetype="text/markdown")
    created = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    return created["id"]
