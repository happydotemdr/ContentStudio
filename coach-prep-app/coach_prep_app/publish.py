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
    media = MediaInMemoryUpload(markdown_body.encode("utf-8"), mimetype="text/plain")
    created = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    return created["id"]
