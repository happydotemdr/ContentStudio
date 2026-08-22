# coach-prep-app/tests/test_publish.py
from __future__ import annotations

import datetime as dt

from coach_prep_app import publish


class _FakeFiles:
    def __init__(self):
        self.created_with = None

    def create(self, body, media_body, fields):
        self.created_with = body
        return _Exec({"id": "drive-file-123"})


class _Exec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _FakeDriveService:
    def __init__(self):
        self._files = _FakeFiles()

    def files(self):
        return self._files


def test_draft_title_is_clearly_marked_as_a_draft():
    title = publish.draft_title("Sean", dt.date(2026, 8, 20))
    assert title.startswith("DRAFT")
    assert "Sean" in title
    assert "2026-08-20" in title
    assert "review before use" in title


def test_publish_draft_writes_into_the_pending_review_folder_only():
    service = _FakeDriveService()
    file_id = publish.publish_draft(service, "pending-review-folder-id", "Sean", dt.date(2026, 8, 20), "## body")
    assert file_id == "drive-file-123"
    assert service._files.created_with["parents"] == ["pending-review-folder-id"]
    assert "sean-folder-id" not in service._files.created_with["parents"]


# --- markdown rendering in Google Docs --------------------------------------

def test_publish_uploads_as_markdown_so_drive_renders_real_headings():
    """The body went up as text/plain, so Drive stored it verbatim and Ryan
    opened the doc to literal '## Part 1 — Check-in' characters instead of a
    heading. text/markdown makes Drive convert it into a real Doc -- headings,
    bold, bullets, tables. doc-ingest already exports Docs back OUT as
    text/markdown (drive_client.export_google_doc), so the round trip through
    the ingest cron stays symmetric."""
    captured = {}

    class _Files:
        def create(self, body, media_body, fields):
            captured["body"] = body
            captured["media"] = media_body
            return _Exec({"id": "file-1"})

    class _Drive:
        def files(self):
            return _Files()

    publish.publish_draft(_Drive(), "folder-1", "Sean", dt.date(2026, 8, 20), "## Part 1\n\n- a bullet")

    assert captured["media"].mimetype() == "text/markdown"
    assert captured["body"]["mimeType"] == "application/vnd.google-apps.document"
