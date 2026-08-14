# tests/test_convert.py
from unittest.mock import MagicMock, patch

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
    with patch("firecrawl.Firecrawl", return_value=mock_client):
        result = convert.convert_local_file(staged, "pdf", cfg)

    assert result.success is True
    assert result.markdown_body == "# Converted body\n"
    assert result.tool == "firecrawl-parse"
    mock_client.parse.assert_called_once()
    _, kwargs = mock_client.parse.call_args
    assert kwargs["filename"] == "sample.pdf"
    assert kwargs["content_type"] == "application/pdf"


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
