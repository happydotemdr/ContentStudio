import json
from pathlib import Path

import pytest

from pipeline_app import artifacts
from pipeline_app import discovery_youtube as yt


@pytest.fixture(autouse=True)
def no_data_api_by_default(monkeypatch):
    """Keep these tests off the network.

    download_item/peek_upload_date now consult the Data API first, so without
    this an engineer with YOUTUBE_API_KEY set in their environment would have
    the suite make real HTTP calls. Tests that want API metadata patch
    fetch_one themselves.
    """
    monkeypatch.setattr(yt.youtube_api, "fetch_one", lambda *a, **k: None)


def test_on_disk_ids_matches_id_prefix_before_double_underscore(tmp_path: Path):
    handle_dir = tmp_path / "output" / "brand-intel" / "youtube" / "romayroh"
    handle_dir.mkdir(parents=True)
    (handle_dir / "abc123__original-title.md").write_text("x", encoding="utf-8")
    (handle_dir / "def456__retitled-now.md").write_text("x", encoding="utf-8")
    assert yt.on_disk_ids(tmp_path, "@Romayroh") == {"abc123", "def456"}


def test_on_disk_ids_empty_for_new_handle(tmp_path: Path):
    assert yt.on_disk_ids(tmp_path, "@BrandNew") == set()


def test_enumerate_newest_first_applies_keyword_filter(monkeypatch):
    fake_output = json.dumps({"entries": [
        {"id": "v1", "title": "Adam Grant on focus"},
        {"id": "v2", "title": "Unrelated video"},
        {"id": "v3", "title": "adam grant interview"},
    ]})

    class FakeProc:
        returncode = 0
        stdout = fake_output
        stderr = ""

    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: FakeProc())
    items = yt.enumerate_newest_first("@bigthink", keyword_filter="Adam Grant")
    assert [i["id"] for i in items] == ["v1", "v3"]
    assert all(i["published"] is None for i in items)


def test_enumerate_newest_first_no_filter_returns_all(monkeypatch):
    fake_output = json.dumps({"entries": [{"id": "v1", "title": "A"}, {"id": "v2", "title": "B"}]})

    class FakeProc:
        returncode = 0
        stdout = fake_output
        stderr = ""

    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: FakeProc())
    items = yt.enumerate_newest_first("@a", keyword_filter=None)
    assert [i["id"] for i in items] == ["v1", "v2"]


def test_enumerate_newest_first_returns_empty_on_failure(monkeypatch):
    class FakeProc:
        returncode = 1
        stdout = ""
        stderr = "channel not found"

    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: FakeProc())
    assert yt.enumerate_newest_first("@dead-handle", keyword_filter=None) == []


def test_peek_upload_date_reads_info_json(monkeypatch, tmp_path):
    def fake_run(cmd, capture_output, text):
        # simulate yt-dlp writing the info.json next to -o's stem
        out_flag_index = cmd.index("-o")
        stem = Path(cmd[out_flag_index + 1].replace(".%(ext)s", ""))
        stem.with_suffix(".info.json").write_text(
            json.dumps({"upload_date": "20260415"}), encoding="utf-8"
        )
        class FakeProc:
            returncode = 0
            stdout = ""
            stderr = ""
        return FakeProc()

    monkeypatch.setattr(yt.subprocess, "run", fake_run)
    monkeypatch.chdir(tmp_path)
    assert yt.peek_upload_date("v1") == "2026-04-15"


def test_peek_upload_date_does_not_depend_on_cwd(monkeypatch, tmp_path):
    # peek_upload_date must use its own temp directory (tempfile.mkdtemp)
    # rather than a bare relative path in the process's CWD -- under the
    # registered Windows Scheduled Task there is no explicit working
    # directory, so a scheduled wake could land somewhere unwritable (e.g.
    # C:\Windows\System32). Deliberately do NOT chdir into a writable
    # tmp_path here: if the implementation regresses to a relative path, this
    # test fails wherever pytest's own CWD isn't writable.
    def fake_run(cmd, capture_output, text):
        out_flag_index = cmd.index("-o")
        stem = Path(cmd[out_flag_index + 1].replace(".%(ext)s", ""))
        # Assert the temp file lives in a real temp directory, not a bare
        # relative "_peek_<id>" path resolved against the CWD.
        assert stem.is_absolute()
        stem.with_suffix(".info.json").write_text(
            json.dumps({"upload_date": "20260415"}), encoding="utf-8"
        )
        class FakeProc:
            returncode = 0
            stdout = ""
            stderr = ""
        return FakeProc()

    monkeypatch.setattr(yt.subprocess, "run", fake_run)
    assert yt.peek_upload_date("v1") == "2026-04-15"


def test_peek_upload_date_returns_none_when_no_info_json(monkeypatch, tmp_path):
    class FakeProc:
        returncode = 1
        stdout = ""
        stderr = "error"
    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: FakeProc())
    monkeypatch.chdir(tmp_path)
    assert yt.peek_upload_date("v1") is None


def test_download_item_returns_false_when_ytdlp_fails_and_no_file_written(monkeypatch, tmp_path):
    """When yt-dlp fails (no info.json), download_item returns ok: False
    and does NOT write a .md file, leaving the video eligible for retry."""

    # Mock yt-dlp to fail (no info.json written, no transcript found)
    class FakeProc:
        returncode = 1
        stdout = ""
        stderr = "connection error"

    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: FakeProc())
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)

    result = yt.download_item(tmp_path, "@testhandle", "vid123", "Test Video")

    # Should return ok: False
    assert result["ok"] is False
    assert result["id"] == "vid123"

    # No .md file should be written
    dest_dir = tmp_path / "output" / "brand-intel" / "youtube" / "testhandle"
    md_files = list(dest_dir.glob("vid123__*.md"))
    assert len(md_files) == 0, f"Expected no .md file, but found: {md_files}"


def test_download_item_returns_true_when_ytdlp_succeeds_even_without_transcript(monkeypatch, tmp_path):
    """When yt-dlp succeeds (info.json exists), download_item returns ok: True
    and writes a .md file even if no transcript is available."""

    def fake_run(cmd, capture_output, text):
        # Simulate yt-dlp writing info.json on success
        out_flag_index = cmd.index("-o")
        stem = Path(cmd[out_flag_index + 1].replace(".%(ext)s", ""))
        stem.with_suffix(".info.json").write_text(
            json.dumps({
                "id": "vid456",
                "title": "Test",
                "uploader": "@testhandle",
                "description": "A test video",
                "duration": 120,
                "upload_date": "20260415"
            }),
            encoding="utf-8"
        )
        class FakeProc:
            returncode = 0
            stdout = ""
            stderr = ""
        return FakeProc()

    monkeypatch.setattr(yt.subprocess, "run", fake_run)
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)

    result = yt.download_item(tmp_path, "@testhandle", "vid456", "Test Video")

    # Should return ok: True
    assert result["ok"] is True
    assert result["id"] == "vid456"
    assert result["published"] == "2026-04-15"

    # .md file should be written
    dest_dir = tmp_path / "output" / "brand-intel" / "youtube" / "testhandle"
    md_files = list(dest_dir.glob("vid456__*.md"))
    assert len(md_files) == 1, "Expected exactly one .md file"

    content = md_files[0].read_text(encoding="utf-8")
    assert "# Test Video" in content
    assert "Test Video" in content
    assert "(no transcript available)" in content  # Fallback message


# --------------------------------------------------------------------------- #
# frontmatter + transcript availability

_API_RECORD = {
    "title": "API Title",
    "channel": "Real Channel Name",
    "description": "From the Data API",
    "upload_date": "2026-04-15",
    "duration_s": 384,
    "view_count": 12043,
    "like_count": 502,
    "comment_count": 31,
    "manual_captions": True,
}


def _ytdlp_ok(info: dict):
    def fake_run(cmd, capture_output, text):
        stem = Path(cmd[cmd.index("-o") + 1].replace(".%(ext)s", ""))
        stem.with_suffix(".info.json").write_text(json.dumps(info), encoding="utf-8")
        class FakeProc:
            returncode = 0
            stdout = ""
            stderr = ""
        return FakeProc()
    return fake_run


def _ytdlp_blocked(cmd, capture_output, text):
    """Simulates the bot-block: yt-dlp writes nothing at all."""
    class FakeProc:
        returncode = 1
        stdout = ""
        stderr = "Sign in to confirm you're not a bot"
    return FakeProc()


def _written(tmp_path, video_id):
    dest_dir = tmp_path / "output" / "brand-intel" / "youtube" / "testhandle"
    files = list(dest_dir.glob(f"{video_id}__*.md"))
    assert len(files) == 1, f"expected one .md, found {files}"
    return artifacts.parse_frontmatter(files[0].read_text(encoding="utf-8"))


def test_download_item_writes_yaml_frontmatter(monkeypatch, tmp_path):
    monkeypatch.setattr(yt.subprocess, "run", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "v1", "Test Video")
    meta, body = _written(tmp_path, "v1")
    assert meta["video_id"] == "v1"
    assert meta["url"] == "https://www.youtube.com/watch?v=v1"
    assert body.startswith("# Test Video")


def test_transcript_status_missing_when_no_transcript(monkeypatch, tmp_path):
    monkeypatch.setattr(yt.subprocess, "run", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "v2", "T")
    meta, _ = _written(tmp_path, "v2")
    assert meta["transcript_status"] == "missing"
    assert meta["transcript_source"] == "none"


def test_transcript_status_present_when_fallback_supplies_one(monkeypatch, tmp_path):
    monkeypatch.setattr(yt.subprocess, "run", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: "real transcript text")
    yt.download_item(tmp_path, "@testhandle", "v3", "T")
    meta, body = _written(tmp_path, "v3")
    assert meta["transcript_status"] == "present"
    assert meta["transcript_source"] == "youtube-transcript-api"
    assert "real transcript text" in body


def test_api_metadata_alone_succeeds_when_ytdlp_is_blocked(monkeypatch, tmp_path):
    """The bot-block case: yt-dlp yields nothing, but the Data API still does.

    Must write a real file rather than failing the item forever.
    """
    monkeypatch.setattr(yt.subprocess, "run", _ytdlp_blocked)
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    monkeypatch.setattr(yt.youtube_api, "fetch_one", lambda *a, **k: dict(_API_RECORD))

    result = yt.download_item(tmp_path, "@testhandle", "v4", "T")
    assert result["ok"] is True
    assert result["published"] == "2026-04-15"

    meta, _ = _written(tmp_path, "v4")
    assert meta["metadata_source"] == "youtube-data-api-v3"
    assert meta["channel"] == "Real Channel Name"
    assert meta["view_count"] == 12043
    assert meta["duration_s"] == 384
    assert meta["manual_captions"] is True
    assert meta["transcript_status"] == "missing"


def test_still_fails_when_both_sources_yield_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(yt.subprocess, "run", _ytdlp_blocked)
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    result = yt.download_item(tmp_path, "@testhandle", "v5", "T")
    assert result["ok"] is False
    dest_dir = tmp_path / "output" / "brand-intel" / "youtube" / "testhandle"
    assert list(dest_dir.glob("v5__*.md")) == []


def test_metadata_source_is_ytdlp_when_no_api_key(monkeypatch, tmp_path):
    monkeypatch.setattr(yt.subprocess, "run", _ytdlp_ok({"upload_date": "20260415", "duration": 120}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "v6", "T")
    meta, _ = _written(tmp_path, "v6")
    assert meta["metadata_source"] == "yt-dlp"
    assert meta["duration_s"] == 120
    assert meta["manual_captions"] is None


def test_peek_upload_date_prefers_data_api(monkeypatch, tmp_path):
    def explode(*a, **k):
        raise AssertionError("yt-dlp must not run when the API answered")
    monkeypatch.setattr(yt.youtube_api, "fetch_one", lambda *a, **k: {"upload_date": "2026-01-02"})
    monkeypatch.setattr(yt.subprocess, "run", explode)
    assert yt.peek_upload_date("v1") == "2026-01-02"


def test_missing_transcript_ids_lists_only_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(yt.subprocess, "run", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "gone", "No Transcript")
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: "text")
    yt.download_item(tmp_path, "@testhandle", "have", "Has Transcript")

    missing = yt.missing_transcript_ids(tmp_path, "@testhandle")
    assert [m["id"] for m in missing] == ["gone"]
    assert missing[0]["url"] == "https://www.youtube.com/watch?v=gone"
