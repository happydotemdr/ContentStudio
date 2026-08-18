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
