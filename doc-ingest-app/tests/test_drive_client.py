# tests/test_drive_client.py
from unittest.mock import MagicMock, call

import pytest

from doc_ingest.config import Config
from doc_ingest import drive_client


def test_build_batch_metadata_adds_one_request_per_doc_id():
    service = MagicMock()
    batch = MagicMock()
    service.new_batch_http_request.return_value = batch

    def _execute():
        # Simulate the batch callback firing for each added request.
        for request_id, doc_id in enumerate(["doc1", "doc2"]):
            callback = batch.add.call_args_list[request_id].kwargs["callback"]
            callback(str(request_id), {"id": doc_id, "name": f"{doc_id}.gdoc", "modifiedTime": "2026-08-01T00:00:00Z", "mimeType": "application/vnd.google-apps.document"}, None)

    batch.execute.side_effect = _execute
    cfg = Config()
    result = drive_client.build_batch_metadata(service, ["doc1", "doc2"], cfg)
    assert result["doc1"]["modifiedTime"] == "2026-08-01T00:00:00Z"
    assert result["doc2"]["name"] == "doc2.gdoc"
    assert batch.add.call_count == 2

    # Prove the request itself was built with the real fileId/fields, not
    # just that *some* mock call happened -- a MagicMock silently accepts a
    # typo'd kwarg name otherwise, so asserting only call_count wouldn't
    # catch e.g. fields="id,name,modifiedTIme,mimeType".
    get_calls = service.files().get.call_args_list
    called_doc_ids = {c.kwargs["fileId"] for c in get_calls}
    assert called_doc_ids == {"doc1", "doc2"}
    for c in get_calls:
        assert c.kwargs["fields"] == "id,name,modifiedTime,mimeType"

    # BatchHttpRequest invokes BOTH a per-request callback (from .add) AND a
    # batch-level default callback (from new_batch_http_request) for every
    # completed request -- not one-or-the-other. Registering the same
    # callback in both places double-invokes it per doc_id, which is exactly
    # the bug this asserts against.
    _, batch_kwargs = service.new_batch_http_request.call_args
    assert "callback" not in batch_kwargs


def test_build_batch_metadata_chunks_over_the_batch_size_cap():
    service = MagicMock()
    batches_created = []

    def _new_batch(callback=None):
        b = MagicMock()
        b.execute.side_effect = lambda: None
        batches_created.append(b)
        return b

    service.new_batch_http_request.side_effect = _new_batch
    cfg = Config(drive_metadata_batch_size=2)
    drive_client.build_batch_metadata(service, ["a", "b", "c"], cfg)
    assert len(batches_created) == 2  # [a,b], [c]


def test_export_google_doc_writes_markdown(tmp_path):
    service = MagicMock()
    service.files().export.return_value.execute.return_value = b"# Exported markdown\n"
    cfg = Config()
    dest = tmp_path / "out.md"
    result = drive_client.export_google_doc(service, "doc123", dest, cfg)
    assert result.success is True
    assert result.tool == "google-docs-export"
    assert dest.read_bytes() == b"# Exported markdown\n"


def test_export_google_doc_falls_back_to_docx_when_markdown_unavailable(tmp_path):
    service = MagicMock()

    def _export(fileId, mimeType):
        exec_mock = MagicMock()
        if mimeType == "text/markdown":
            exec_mock.execute.side_effect = Exception("format not available")
        else:
            exec_mock.execute.return_value = b"fake docx bytes"
        return exec_mock

    service.files().export.side_effect = _export
    cfg = Config()
    dest = tmp_path / "out.docx"
    result = drive_client.export_google_doc(service, "doc123", dest, cfg)
    assert result.success is True
    assert result.tool == "google-docs-export-docx-fallback"


def test_export_google_sheet_writes_xlsx(tmp_path):
    service = MagicMock()
    service.files().export.return_value.execute.return_value = b"fake xlsx bytes"
    cfg = Config()
    dest = tmp_path / "out.xlsx"
    result = drive_client.export_google_sheet(service, "sheet123", dest, cfg)
    assert result.success is True
    assert dest.read_bytes() == b"fake xlsx bytes"


def test_retry_backs_off_and_succeeds_after_a_transient_error():
    from googleapiclient.errors import HttpError

    attempts = {"count": 0}

    def _flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            response = MagicMock(status=429)
            raise HttpError(response, b"rate limited")
        return "success"

    cfg = Config(drive_retry_max_attempts=5, drive_retry_base_delay_s=0.001)
    result = drive_client._with_retry(_flaky, cfg)
    assert result == "success"
    assert attempts["count"] == 3


def test_retry_gives_up_after_max_attempts():
    from googleapiclient.errors import HttpError

    def _always_fails():
        response = MagicMock(status=500)
        raise HttpError(response, b"server error")

    cfg = Config(drive_retry_max_attempts=2, drive_retry_base_delay_s=0.001)
    with pytest.raises(HttpError):
        drive_client._with_retry(_always_fails, cfg)
