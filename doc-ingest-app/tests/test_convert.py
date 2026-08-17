# tests/test_convert.py
from unittest.mock import MagicMock, call, patch

import requests
from firecrawl.v2.utils.error_handler import BadRequestError, FirecrawlError, RateLimitError

from doc_ingest.config import Config
from doc_ingest import convert


def test_oversized_file_short_circuits_without_constructing_a_client(tmp_path):
    cfg = Config(oversized_file_cap_bytes=10)
    staged = tmp_path / "huge.pdf"
    staged.write_bytes(b"x" * 100)

    with patch("firecrawl.Firecrawl") as mock_firecrawl_cls:
        result = convert.convert_local_file(staged, "pdf", cfg)
        mock_firecrawl_cls.assert_not_called()

    assert result.success is False
    assert result.error == "oversized_unsupported"


def test_successful_conversion_returns_the_parsed_markdown(tmp_path):
    cfg = Config()
    staged = tmp_path / "sample.pdf"
    staged.write_bytes(b"%PDF-1.4 fake")

    mock_client = MagicMock()
    mock_client.parse.return_value = MagicMock(markdown="# Converted body\n")
    with patch("firecrawl.Firecrawl", return_value=mock_client) as mock_firecrawl_cls:
        result = convert.convert_local_file(staged, "pdf", cfg)

    assert result.success is True
    assert result.markdown_body == "# Converted body\n"
    assert result.tool == "firecrawl-parse"
    mock_client.parse.assert_called_once()
    _, kwargs = mock_client.parse.call_args
    assert kwargs["filename"] == "sample.pdf"
    assert kwargs["content_type"] == "application/pdf"
    # max_retries=1 disables the SDK's own internal retry/backoff so it can't
    # stack invisibly under our own retry loop's attempts and delays.
    mock_firecrawl_cls.assert_called_once_with(max_retries=1)


def test_parse_exception_is_a_failure_not_a_crash(tmp_path):
    cfg = Config()
    staged = tmp_path / "sample.pdf"
    staged.write_bytes(b"%PDF-1.4 fake")

    mock_client = MagicMock()
    mock_client.parse.side_effect = RuntimeError("parse failed")
    with patch("firecrawl.Firecrawl", return_value=mock_client):
        result = convert.convert_local_file(staged, "pdf", cfg)

    assert result.success is False
    assert "parse failed" in result.error


def test_ppt_rejection_is_flagged_unsupported_type_not_a_crash(tmp_path):
    cfg = Config()
    staged = tmp_path / "sample.ppt"
    staged.write_bytes(b"fake ppt bytes")

    mock_client = MagicMock()
    mock_client.parse.side_effect = RuntimeError("unsupported format")
    with patch("firecrawl.Firecrawl", return_value=mock_client):
        result = convert.convert_local_file(staged, "ppt", cfg)

    assert result.success is False
    assert result.error == "unsupported_type: unsupported format"


def test_empty_markdown_is_reported_as_a_failure_not_a_silent_pass(tmp_path):
    cfg = Config()
    staged = tmp_path / "sample.pdf"
    staged.write_bytes(b"%PDF-1.4 fake")

    mock_client = MagicMock()
    mock_client.parse.return_value = MagicMock(markdown="")
    with patch("firecrawl.Firecrawl", return_value=mock_client):
        result = convert.convert_local_file(staged, "pdf", cfg)

    assert result.success is False
    assert result.error == "empty_markdown_returned"


def test_rate_limit_error_is_retried_then_succeeds(tmp_path):
    cfg = Config(firecrawl_retry_max_attempts=3, firecrawl_retry_base_delay_s=0)
    staged = tmp_path / "sample.pdf"
    staged.write_bytes(b"%PDF-1.4 fake")

    mock_client = MagicMock()
    mock_client.parse.side_effect = [
        RateLimitError("Rate Limit Exceeded", status_code=429),
        MagicMock(markdown="# body\n"),
    ]
    with patch("firecrawl.Firecrawl", return_value=mock_client):
        result = convert.convert_local_file(staged, "pdf", cfg)

    assert result.success is True
    assert result.markdown_body == "# body\n"
    assert mock_client.parse.call_count == 2


def test_rate_limit_error_gives_up_after_max_attempts(tmp_path):
    cfg = Config(firecrawl_retry_max_attempts=3, firecrawl_retry_base_delay_s=0)
    staged = tmp_path / "sample.pdf"
    staged.write_bytes(b"%PDF-1.4 fake")

    mock_client = MagicMock()
    mock_client.parse.side_effect = RateLimitError("Rate Limit Exceeded", status_code=429)
    with patch("firecrawl.Firecrawl", return_value=mock_client):
        result = convert.convert_local_file(staged, "pdf", cfg)

    assert result.success is False
    assert "Rate Limit Exceeded" in result.error
    assert mock_client.parse.call_count == 3


def test_retry_backoff_delays_double_each_attempt(tmp_path):
    cfg = Config(firecrawl_retry_max_attempts=3, firecrawl_retry_base_delay_s=2.0)
    staged = tmp_path / "sample.pdf"
    staged.write_bytes(b"%PDF-1.4 fake")

    mock_client = MagicMock()
    mock_client.parse.side_effect = RateLimitError("Rate Limit Exceeded", status_code=429)
    with patch("firecrawl.Firecrawl", return_value=mock_client), \
            patch("doc_ingest.convert.time.sleep") as mock_sleep:
        convert.convert_local_file(staged, "pdf", cfg)

    assert mock_sleep.call_args_list == [call(2.0), call(4.0)]


def test_connection_reset_is_retried_then_succeeds(tmp_path):
    cfg = Config(firecrawl_retry_max_attempts=3, firecrawl_retry_base_delay_s=0)
    staged = tmp_path / "sample.pdf"
    staged.write_bytes(b"%PDF-1.4 fake")

    mock_client = MagicMock()
    mock_client.parse.side_effect = [
        requests.exceptions.ConnectionError("Connection aborted."),
        MagicMock(markdown="# body\n"),
    ]
    with patch("firecrawl.Firecrawl", return_value=mock_client):
        result = convert.convert_local_file(staged, "pdf", cfg)

    assert result.success is True
    assert mock_client.parse.call_count == 2


def test_service_unavailable_is_retried_then_succeeds(tmp_path):
    cfg = Config(firecrawl_retry_max_attempts=3, firecrawl_retry_base_delay_s=0)
    staged = tmp_path / "sample.pdf"
    staged.write_bytes(b"%PDF-1.4 fake")

    mock_client = MagicMock()
    mock_client.parse.side_effect = [
        FirecrawlError("Service Unavailable", status_code=503),
        MagicMock(markdown="# body\n"),
    ]
    with patch("firecrawl.Firecrawl", return_value=mock_client):
        result = convert.convert_local_file(staged, "pdf", cfg)

    assert result.success is True
    assert mock_client.parse.call_count == 2


def test_non_transient_error_is_not_retried(tmp_path):
    cfg = Config(firecrawl_retry_max_attempts=3, firecrawl_retry_base_delay_s=0)
    staged = tmp_path / "sample.pdf"
    staged.write_bytes(b"%PDF-1.4 fake")

    mock_client = MagicMock()
    mock_client.parse.side_effect = BadRequestError("Bad Request", status_code=400)
    with patch("firecrawl.Firecrawl", return_value=mock_client):
        result = convert.convert_local_file(staged, "pdf", cfg)

    assert result.success is False
    assert mock_client.parse.call_count == 1


def test_content_type_is_selected_by_source_type(tmp_path):
    cfg = Config()
    staged = tmp_path / "sample.xlsx"
    staged.write_bytes(b"fake xlsx bytes")

    mock_client = MagicMock()
    mock_client.parse.return_value = MagicMock(markdown="body")
    with patch("firecrawl.Firecrawl", return_value=mock_client):
        convert.convert_local_file(staged, "xlsx", cfg)

    _, kwargs = mock_client.parse.call_args
    assert kwargs["content_type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
