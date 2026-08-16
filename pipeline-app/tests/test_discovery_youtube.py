import sys
import json
from pathlib import Path

import pytest

from pipeline_app import artifacts
from pipeline_app import discovery_youtube as yt


def _proc(returncode, stdout, stderr):
    """Factory for fake subprocess.CompletedProcess objects."""
    class FakeProc:
        pass
    FakeProc.returncode = returncode
    FakeProc.stdout = stdout
    FakeProc.stderr = stderr
    return FakeProc()


@pytest.fixture
def logged(monkeypatch):
    """Captures every yt.obs.log() call this test makes, as a list of dicts.

    Each record is {"event": ..., "level": ..., **fields} -- the same shape
    obs.log() takes, minus the timestamp obs.log() would otherwise stamp.
    """
    records: list[dict] = []

    def fake_log(event, *, level="info", **fields):
        records.append({"event": event, "level": level, **fields})

    monkeypatch.setattr(yt.obs, "log", fake_log)
    return records


@pytest.fixture(autouse=True)
def no_data_api_by_default(monkeypatch):
    """Keep these tests off the network.

    download_item/peek_upload_date now consult the Data API first, so without
    this an engineer with YOUTUBE_API_KEY set in their environment would have
    the suite make real HTTP calls. Tests that want API metadata patch
    fetch_one themselves.
    """
    monkeypatch.setattr(yt.youtube_api, "fetch_one", lambda *a, **k: None)
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda *a, **k: {})


def test_on_disk_ids_matches_id_prefix_before_double_underscore(tmp_path: Path):
    handle_dir = tmp_path / "output" / "brand-intel" / "youtube" / "romayroh"
    handle_dir.mkdir(parents=True)
    (handle_dir / "abc123__original-title.md").write_text("x", encoding="utf-8")
    (handle_dir / "def456__retitled-now.md").write_text("x", encoding="utf-8")
    assert yt.on_disk_ids(tmp_path, "@Romayroh") == {"abc123", "def456"}


def test_on_disk_ids_empty_for_new_handle(tmp_path: Path):
    assert yt.on_disk_ids(tmp_path, "@BrandNew") == set()


def test_enumerate_newest_first_applies_keyword_filter(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs([
        {"id": "v1", "title": "Adam Grant on focus"},
        {"id": "v2", "title": "Unrelated video"},
        {"id": "v3", "title": "adam grant interview"},
    ], []))
    items = yt.enumerate_newest_first("@bigthink", keyword_filter="Adam Grant")
    assert [i["id"] for i in items] == ["v1", "v3"]
    assert all(i["published"] is None for i in items)


def test_enumerate_newest_first_no_filter_returns_all(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs(
        [{"id": "v1", "title": "A"}, {"id": "v2", "title": "B"}], []))
    items = yt.enumerate_newest_first("@a", keyword_filter=None)
    assert [i["id"] for i in items] == ["v1", "v2"]


def test_enumerate_raises_when_the_videos_tab_fetch_fails(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp",
                        lambda *a, **k: _proc(1, "", "ERROR: unable to download API page: HTTP Error 429"))
    with pytest.raises(yt.YouTubeEnumerationError) as exc:
        yt.enumerate_newest_first("@dead-handle", keyword_filter=None)
    assert "@dead-handle" in str(exc.value)
    assert "429" in str(exc.value)


def test_a_failed_fetch_is_distinguishable_from_a_channel_with_no_uploads(monkeypatch):
    """The Three-Test Rule's distinguishability case, stated directly."""
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {})
    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(0, json.dumps({"entries": []}), ""))
    genuinely_empty = yt.enumerate_newest_first("@quiet", keyword_filter=None)
    assert genuinely_empty == []

    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(1, "", "HTTP Error 503"))
    with pytest.raises(yt.YouTubeEnumerationError):
        yt.enumerate_newest_first("@quiet", keyword_filter=None)


def test_enumerate_failure_is_surfaced_as_a_structured_error_event(monkeypatch, logged):
    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(1, "", "HTTP Error 503"))
    with pytest.raises(yt.YouTubeEnumerationError):
        yt.enumerate_newest_first("@c", keyword_filter=None)
    (record,) = [r for r in logged if r["event"] == "adapter.enumerate_failed"]
    assert record["level"] == "error"
    assert record["platform"] == "youtube" and record["handle"] == "@c" and record["tab"] == "videos"


def test_empty_stdout_with_a_zero_exit_raises_rather_than_reporting_a_quiet_day(monkeypatch):
    """The B-10(a) aftermath: a dead reader thread now yields "" not None,
    and "" from a supposedly successful run is a failure, not an empty channel."""
    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(0, "", ""))
    with pytest.raises(yt.YouTubeEnumerationError):
        yt.enumerate_newest_first("@c", keyword_filter=None)


def test_unparseable_listing_json_raises_the_typed_error(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(0, "{not json", ""))
    with pytest.raises(yt.YouTubeEnumerationError):
        yt.enumerate_newest_first("@c", keyword_filter=None)


def test_enumeration_is_bounded_by_playlist_end(monkeypatch):
    seen = {}
    monkeypatch.setattr(yt, "_run_ytdlp",
                        lambda args, **k: seen.update(args=args) or _proc(0, json.dumps({"entries": []}), ""))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {})
    yt.enumerate_newest_first("@c", None)
    assert "--playlist-end" in seen["args"]
    assert seen["args"][seen["args"].index("--playlist-end") + 1] == str(yt.ENUMERATE_MAX_ITEMS)


def test_a_full_walk_can_still_be_requested(monkeypatch):
    seen = {}
    monkeypatch.setattr(yt, "_run_ytdlp",
                        lambda args, **k: seen.update(args=args) or _proc(0, json.dumps({"entries": []}), ""))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {})
    yt.enumerate_newest_first("@c", None, max_items=None)
    assert "--playlist-end" not in seen["args"]


def test_peek_upload_date_reads_info_json(monkeypatch, tmp_path):
    def fake_run(args, *, label, binary=None):
        # simulate yt-dlp writing the info.json next to -o's stem
        stem = Path(args[args.index("-o") + 1].replace(".%(ext)s", ""))
        stem.with_suffix(".info.json").write_text(
            json.dumps({"upload_date": "20260415"}), encoding="utf-8"
        )
        return _proc(0, "", "")

    monkeypatch.setattr(yt, "_run_ytdlp", fake_run)
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
    def fake_run(args, *, label, binary=None):
        stem = Path(args[args.index("-o") + 1].replace(".%(ext)s", ""))
        # Assert the temp file lives in a real temp directory, not a bare
        # relative "_peek_<id>" path resolved against the CWD.
        assert stem.is_absolute()
        stem.with_suffix(".info.json").write_text(
            json.dumps({"upload_date": "20260415"}), encoding="utf-8"
        )
        return _proc(0, "", "")

    monkeypatch.setattr(yt, "_run_ytdlp", fake_run)
    assert yt.peek_upload_date("v1") == "2026-04-15"


def test_peek_upload_date_returns_none_when_no_info_json(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(1, "", "error"))
    monkeypatch.chdir(tmp_path)
    assert yt.peek_upload_date("v1") is None


def test_download_item_returns_false_when_ytdlp_fails_and_no_file_written(monkeypatch, tmp_path):
    """When yt-dlp fails (no info.json), download_item returns ok: False
    and does NOT write a .md file, leaving the video eligible for retry."""

    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(1, "", "connection error"))
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

    def fake_run(args, *, label, binary=None):
        # Simulate yt-dlp writing info.json on success
        stem = Path(args[args.index("-o") + 1].replace(".%(ext)s", ""))
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
        return _proc(0, "", "")

    monkeypatch.setattr(yt, "_run_ytdlp", fake_run)
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
# yt-dlp return codes are read, and a truncated info.json cannot escape as an
# unguarded JSONDecodeError (B-16)

def test_peek_upload_date_reports_a_failed_ytdlp_instead_of_returning_none(monkeypatch, logged):
    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(1, "", "HTTP Error 429"))
    assert yt.peek_upload_date("v1") is None
    assert [r for r in logged if r["event"] == "adapter.peek_failed"
            and r["level"] == "warning" and "429" in r["stderr"]]


def test_peek_upload_date_survives_a_truncated_info_json(monkeypatch, logged):
    def fake_run(args, *, label, binary=None):
        stem = Path(args[args.index("-o") + 1].replace(".%(ext)s", ""))
        stem.with_suffix(".info.json").write_text('{"upload_date": "2026', encoding="utf-8")
        return _proc(0, "", "")

    monkeypatch.setattr(yt, "_run_ytdlp", fake_run)
    assert yt.peek_upload_date("v1") is None          # today: JSONDecodeError escapes
    assert [r for r in logged if r["event"] == "adapter.info_json_unparseable"]


def test_download_item_logs_a_nonzero_ytdlp_exit(monkeypatch, tmp_path, logged):
    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(1, "", "Sign in to confirm"))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    monkeypatch.setattr(yt.youtube_api, "fetch_one", lambda *a, **k: dict(_API_RECORD))
    yt.download_item(tmp_path, "@testhandle", "v1", "T")
    assert [r for r in logged if r["event"] == "adapter.download_tool_failed"
            and r["level"] == "warning" and r["video_id"] == "v1"]


def test_download_item_filename_and_h1_carry_the_original_characters(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "v1", _EMOJI_TITLE)

    dest_dir = tmp_path / "output" / "brand-intel" / "youtube" / "testhandle"
    (written,) = list(dest_dir.glob("v1__*.md"))
    # cp1252 corruption of "naïve" is "naÃ¯ve"; slugify keeps the \w chars, so
    # the mojibake is visible in the filename as "naÃve".
    assert "naïve" in written.name
    assert "Ã" not in written.name
    body = written.read_text(encoding="utf-8")
    assert f"# {_EMOJI_TITLE}" in body


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
    def fake_run(args, *, label, binary=None):
        stem = Path(args[args.index("-o") + 1].replace(".%(ext)s", ""))
        stem.with_suffix(".info.json").write_text(json.dumps(info), encoding="utf-8")
        return _proc(0, "", "")
    return fake_run


def _ytdlp_blocked(args, *, label, binary=None):
    """Simulates the bot-block: yt-dlp writes nothing at all."""
    return _proc(1, "", "Sign in to confirm you're not a bot")


def _written(tmp_path, video_id):
    dest_dir = tmp_path / "output" / "brand-intel" / "youtube" / "testhandle"
    files = list(dest_dir.glob(f"{video_id}__*.md"))
    assert len(files) == 1, f"expected one .md, found {files}"
    return artifacts.parse_frontmatter(files[0].read_text(encoding="utf-8"))


def test_download_item_writes_yaml_frontmatter(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "v1", "Test Video")
    meta, body = _written(tmp_path, "v1")
    assert meta["video_id"] == "v1"
    assert meta["url"] == "https://www.youtube.com/watch?v=v1"
    assert body.startswith("# Test Video")


def test_transcript_status_missing_when_no_transcript(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "v2", "T")
    meta, _ = _written(tmp_path, "v2")
    assert meta["transcript_status"] == "missing"
    assert meta["transcript_source"] == "none"


def test_transcript_status_present_when_fallback_supplies_one(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415"}))
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
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_blocked)
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
    # B-12: a blocked/failed yt-dlp run is retryable, not a terminal "missing"
    # -- see test_bot_blocked_download_with_api_metadata_is_marked_retryable.
    assert meta["transcript_status"] == "pending_retry"


def test_bot_blocked_download_with_api_metadata_is_marked_retryable(monkeypatch, tmp_path, logged):
    """The B-12 configuration exactly: stale cookies.txt + a working API key."""
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_blocked)
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    monkeypatch.setattr(yt.youtube_api, "fetch_one", lambda *a, **k: dict(_API_RECORD))

    result = yt.download_item(tmp_path, "@testhandle", "v1", "T")
    assert result["ok"] is True                       # the metadata is real and worth keeping
    meta, _ = _written(tmp_path, "v1")
    assert meta["transcript_status"] == "pending_retry"
    assert meta["transcript_attempts"] == 1
    assert [r for r in logged if r["event"] == "adapter.transcript_pending_retry"]


def test_a_captionless_video_is_terminal_not_retryable(monkeypatch, tmp_path):
    """The distinguishability test: yt-dlp ran clean and the video simply has
    no captions. That is an answer, not a failure."""
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "v2", "T")
    meta, _ = _written(tmp_path, "v2")
    assert meta["transcript_status"] == "missing"
    assert meta["transcript_attempts"] == 0


def test_a_blocked_transcript_api_also_marks_pending_retry(monkeypatch, tmp_path):
    def blocked(*a, **k):
        raise yt.TranscriptFetchBlocked("IpBlocked")

    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", blocked)
    yt.download_item(tmp_path, "@testhandle", "v3", "T")
    meta, _ = _written(tmp_path, "v3")
    assert meta["transcript_status"] == "pending_retry"


def test_attempts_accumulate_and_the_status_becomes_terminal_at_the_cap(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_blocked)
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    monkeypatch.setattr(yt.youtube_api, "fetch_one", lambda *a, **k: dict(_API_RECORD))
    for _ in range(yt.MAX_TRANSCRIPT_ATTEMPTS):
        yt.download_item(tmp_path, "@testhandle", "v4", "T")
    meta, _ = _written(tmp_path, "v4")
    assert meta["transcript_attempts"] == yt.MAX_TRANSCRIPT_ATTEMPTS
    assert meta["transcript_status"] == "missing"      # bounded: never loops forever


def test_prior_transcript_attempts_tolerates_malformed_frontmatter(tmp_path):
    """_awaiting_transcript_retry already tolerates a capture file whose
    frontmatter fails to parse (truncated write, hand-edit, pre-P6 stray
    file) by treating it as unreadable and moving on. _prior_transcript_attempts
    reads the very same on-disk file for the very same retry state machine and
    must be equally tolerant -- not raise artifacts.MalformedArtifactError,
    which only ValueError/OSError were being caught for."""
    dest = tmp_path / "v9__title.md"
    # Opens a frontmatter block but never closes it -- MalformedArtifactError,
    # not a plain ValueError/OSError.
    dest.write_text("---\ntranscript_attempts: 2\n", encoding="utf-8")

    assert yt._prior_transcript_attempts(dest) == 0


def test_download_item_survives_a_malformed_prior_capture(monkeypatch, tmp_path):
    """End-to-end: a malformed capture already on disk for this video must not
    crash download_item via _prior_transcript_attempts."""
    out_dir = tmp_path / "output" / "brand-intel" / "youtube" / "testhandle"
    out_dir.mkdir(parents=True)
    dest = out_dir / f"v9__{yt.slugify('T')}.md"
    dest.write_text("---\ntranscript_attempts: 2\n", encoding="utf-8")

    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_blocked)
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    monkeypatch.setattr(yt.youtube_api, "fetch_one", lambda *a, **k: dict(_API_RECORD))

    result = yt.download_item(tmp_path, "@testhandle", "v9", "T")

    assert result["ok"] is True
    meta, _ = _written(tmp_path, "v9")
    # Treated as a fresh start (attempts=0 before this run), matching the
    # sibling _awaiting_transcript_retry's tolerant fallback.
    assert meta["transcript_attempts"] == 1


def test_a_recovered_transcript_clears_the_pending_state(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_blocked)
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    monkeypatch.setattr(yt.youtube_api, "fetch_one", lambda *a, **k: dict(_API_RECORD))
    yt.download_item(tmp_path, "@testhandle", "v5", "T")
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: "the real transcript")
    yt.download_item(tmp_path, "@testhandle", "v5", "T")
    meta, body = _written(tmp_path, "v5")
    assert meta["transcript_status"] == "present"
    assert "the real transcript" in body


def test_still_fails_when_both_sources_yield_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_blocked)
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    result = yt.download_item(tmp_path, "@testhandle", "v5", "T")
    assert result["ok"] is False
    dest_dir = tmp_path / "output" / "brand-intel" / "youtube" / "testhandle"
    assert list(dest_dir.glob("v5__*.md")) == []


def test_metadata_source_is_ytdlp_when_no_api_key(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415", "duration": 120}))
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
    monkeypatch.setattr(yt, "_run_ytdlp", explode)
    assert yt.peek_upload_date("v1") == "2026-01-02"


def test_missing_transcript_ids_lists_only_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "gone", "No Transcript")
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: "text")
    yt.download_item(tmp_path, "@testhandle", "have", "Has Transcript")

    missing = yt.missing_transcript_ids(tmp_path, "@testhandle")
    assert [m["id"] for m in missing] == ["gone"]
    assert missing[0]["url"] == "https://www.youtube.com/watch?v=gone"


# --------------------------------------------------------------------------- #
# a missing youtube-transcript-api must be loud, not silent

def _simulate_missing_library(monkeypatch):
    """Make `import youtube_transcript_api` raise ImportError.

    Setting a sys.modules entry to None is the documented way to force an
    ImportError for a module that may genuinely be installed.
    """
    monkeypatch.setitem(sys.modules, "youtube_transcript_api", None)
    monkeypatch.setattr(yt, "_TRANSCRIPT_API_MISSING_WARNED", False)


def test_missing_transcript_api_warns_instead_of_failing_silently(monkeypatch, capsys):
    _simulate_missing_library(monkeypatch)
    assert yt._fetch_transcript_fallback("v1") is None
    err = capsys.readouterr().err
    assert "youtube-transcript-api is not installed" in err
    assert "DISABLED" in err


def test_missing_transcript_api_warns_only_once_per_process(monkeypatch, capsys):
    _simulate_missing_library(monkeypatch)
    for _ in range(5):
        yt._fetch_transcript_fallback("v1")
    assert capsys.readouterr().err.count("not installed") == 1


def test_missing_library_is_distinguishable_from_no_transcript(monkeypatch, capsys):
    """The whole point: absent dependency and absent transcript must differ."""
    # library present, but this video genuinely has no transcript -> silent None
    module = type(sys)("youtube_transcript_api")
    module.TranscriptsDisabled = type("TranscriptsDisabled", (Exception,), {})

    class FakeApi:
        def fetch(self, vid):
            raise module.TranscriptsDisabled("no transcript for this video")
    module.YouTubeTranscriptApi = FakeApi
    monkeypatch.setitem(sys.modules, "youtube_transcript_api", module)
    monkeypatch.setattr(yt, "_TRANSCRIPT_API_MISSING_WARNED", False)
    assert yt._fetch_transcript_fallback("v1") is None
    assert "not installed" not in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Shorts enumeration
#
# /videos and /shorts are DISJOINT listings -- measured 2026-07-31,
# @goodinside had /videos=274, /shorts=603, overlap=0. Enumerating only
# /videos made every Short invisible to discovery.

def _fake_tabs(videos, shorts):
    """Fake yt-dlp that answers per channel tab."""
    def fake_run(args, *, label, binary=None):
        url = args[-1]
        entries = shorts if url.endswith("/shorts") else videos
        return _proc(0, json.dumps({"entries": entries}), "")
    return fake_run


def test_enumerate_includes_shorts(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs(
        [{"id": "v1", "title": "long form"}],
        [{"id": "s1", "title": "a short"}],
    ))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates",
                        lambda ids, **k: {"v1": "2026-06-01", "s1": "2026-07-01"})
    items = yt.enumerate_newest_first("@c", None)
    assert {i["id"] for i in items} == {"v1", "s1"}


def test_enumerate_tags_content_type(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs(
        [{"id": "v1", "title": "long form"}],
        [{"id": "s1", "title": "a short"}],
    ))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates",
                        lambda ids, **k: {"v1": "2026-06-01", "s1": "2026-07-01"})
    by_id = {i["id"]: i for i in yt.enumerate_newest_first("@c", None)}
    assert by_id["v1"]["content_type"] == "video"
    assert by_id["s1"]["content_type"] == "short"


def test_merged_list_is_globally_newest_first_not_concatenated(monkeypatch):
    """The ordering trap.

    process_handle breaks out of its walk on consecutive-on-disk and on the
    date cutoff, so a merely concatenated [*videos, *shorts] list would stop
    at the end of the videos block and never reach a single Short. The merged
    list must be sorted by date across both tabs.
    """
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs(
        [{"id": "v_new", "title": "v"}, {"id": "v_old", "title": "v"}],
        [{"id": "s_mid", "title": "s"}],
    ))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {
        "v_new": "2026-07-30", "s_mid": "2026-07-15", "v_old": "2026-06-01",
    })
    order = [i["id"] for i in yt.enumerate_newest_first("@c", None)]
    assert order == ["v_new", "s_mid", "v_old"], (
        "Shorts must be interleaved by date, not appended after all videos"
    )


def test_enumerate_populates_published_so_engine_skips_per_item_peeks(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs(
        [{"id": "v1", "title": "v"}], []))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates",
                        lambda ids, **k: {"v1": "2026-07-01"})
    assert yt.enumerate_newest_first("@c", None)[0]["published"] == "2026-07-01"


def test_undated_items_sort_last_not_first(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs(
        [{"id": "dated", "title": "v"}, {"id": "undated", "title": "v"}], []))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates",
                        lambda ids, **k: {"dated": "2026-07-01"})
    assert [i["id"] for i in yt.enumerate_newest_first("@c", None)] == ["dated", "undated"]


def test_shorts_are_not_dropped_when_no_api_dates_are_available(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs(
        [{"id": "v1", "title": "v"}, {"id": "v2", "title": "v"}],
        [{"id": "s1", "title": "s"}]))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {})
    ids = [i["id"] for i in yt.enumerate_newest_first("@c", None)]
    assert set(ids) == {"v1", "v2", "s1"}, "no Short may be silently dropped (B-14/F-24)"


def test_undated_enumeration_interleaves_rather_than_concatenating(monkeypatch):
    """Concatenation is what makes the drop invisible: process_handle breaks on
    consecutive-on-disk inside the /videos block and never reaches a Short."""
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs(
        [{"id": "v1", "title": "v"}, {"id": "v2", "title": "v"}],
        [{"id": "s1", "title": "s"}, {"id": "s2", "title": "s"}]))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {})
    assert [i["id"] for i in yt.enumerate_newest_first("@c", None)] == ["v1", "s1", "v2", "s2"]


def test_undated_enumeration_marks_its_order_approximate(monkeypatch, logged):
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs(
        [{"id": "v1", "title": "v"}], [{"id": "s1", "title": "s"}]))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {})
    items = yt.enumerate_newest_first("@c", None)
    assert {i["order_confidence"] for i in items} == {"approximate"}
    assert [r for r in logged if r["event"] == "adapter.ordering_degraded"
            and r["level"] == "warning" and r["shorts"] == 1]


def test_dated_enumeration_marks_its_order_exact(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs([{"id": "v1", "title": "v"}], []))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {"v1": "2026-07-01"})
    assert yt.enumerate_newest_first("@c", None)[0]["order_confidence"] == "exact"


def test_absent_shorts_tab_is_still_a_legitimate_empty(monkeypatch, logged):
    def fake_run(args, *, label, binary=None):
        if args[-1].endswith("/shorts"):
            return _proc(1, "", "ERROR: [youtube:tab] @c: This channel does not have a shorts tab")
        return _proc(0, json.dumps({"entries": [{"id": "v1", "title": "v"}]}), "")

    monkeypatch.setattr(yt, "_run_ytdlp", fake_run)
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {"v1": "2026-07-01"})
    assert [i["id"] for i in yt.enumerate_newest_first("@c", None)] == ["v1"]
    assert not [r for r in logged if r["level"] == "error"]


def test_a_failing_shorts_tab_is_not_treated_as_an_absent_one(monkeypatch):
    """A 429 on /shorts must never be laundered into "this channel has no Shorts"."""
    def fake_run(args, *, label, binary=None):
        if args[-1].endswith("/shorts"):
            return _proc(1, "", "ERROR: unable to download API page: HTTP Error 429")
        return _proc(0, json.dumps({"entries": [{"id": "v1", "title": "v"}]}), "")

    monkeypatch.setattr(yt, "_run_ytdlp", fake_run)
    with pytest.raises(yt.YouTubeEnumerationError):
        yt.enumerate_newest_first("@c", None)


_EMOJI_TITLE = "Playa \U0001F60D Ocotal \U0001F525 naïve wins"


def test_on_disk_ids_re_offers_a_pending_retry_capture(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_blocked)
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    monkeypatch.setattr(yt.youtube_api, "fetch_one", lambda *a, **k: dict(_API_RECORD))
    yt.download_item(tmp_path, "@testhandle", "blocked", "T")
    assert yt.on_disk_ids(tmp_path, "@testhandle") == set()


def test_on_disk_ids_keeps_a_terminal_capture(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "captionless", "T")
    assert yt.on_disk_ids(tmp_path, "@testhandle") == {"captionless"}


def test_on_disk_ids_treats_an_unreadable_file_as_captured(tmp_path, logged):
    """Fail toward not re-downloading: an unreadable file is an operator
    problem, not a licence to re-pay for the whole back catalogue."""
    directory = tmp_path / "output" / "brand-intel" / "youtube" / "testhandle"
    directory.mkdir(parents=True)
    (directory / "weird__t.md").write_bytes(b"\xff\xfe not frontmatter")
    assert yt.on_disk_ids(tmp_path, "@testhandle") == {"weird"}
    assert [r for r in logged if r["event"] == "adapter.capture_unreadable"]


def _real_ytdlp_emitting(payload: dict) -> list[str]:
    """A binary substitute that writes real UTF-8 bytes to stdout."""
    script = ("import sys, json;"
              f"sys.stdout.buffer.write(json.dumps({payload!r}, ensure_ascii=False)"
              ".encode('utf-8'))")
    return [sys.executable, "-c", script]


@pytest.mark.allow_subprocess
def test_enumerate_preserves_an_emoji_title_byte_identically(monkeypatch):
    monkeypatch.setattr(yt, "YTDLP_BIN", _real_ytdlp_emitting(
        {"entries": [{"id": "v1", "title": _EMOJI_TITLE}]}))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates",
                        lambda ids, **k: {"v1": "2026-07-01"})
    items = yt.enumerate_newest_first("@c", None)
    assert items[0]["title"] == _EMOJI_TITLE


def test_duplicate_across_tabs_is_deduped(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs(
        [{"id": "x", "title": "v"}], [{"id": "x", "title": "v"}]))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {"x": "2026-07-01"})
    assert len(yt.enumerate_newest_first("@c", None)) == 1


def test_keyword_filter_applies_across_both_tabs(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs(
        [{"id": "v1", "title": "Adam Grant talk"}, {"id": "v2", "title": "other"}],
        [{"id": "s1", "title": "adam grant clip"}, {"id": "s2", "title": "nope"}]))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {
        "v1": "2026-07-04", "v2": "2026-07-03", "s1": "2026-07-02", "s2": "2026-07-01"})
    assert {i["id"] for i in yt.enumerate_newest_first("@c", "Adam Grant")} == {"v1", "s1"}


def test_download_item_records_content_type(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "s9", "A Short", "short")
    meta, _ = _written(tmp_path, "s9")
    assert meta["content_type"] == "short"


def test_frontmatter_carries_both_published_and_upload_date(monkeypatch, tmp_path):
    """The platform contract names `published`; YouTube only wrote upload_date,
    which works solely because discovery_digest carries a YouTube-shaped
    fallback. Emit both: `published` for the contract, `upload_date` so files
    already on disk keep their spelling (B-04)."""
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "v1", "T")
    meta, _ = _written(tmp_path, "v1")
    assert meta["published"] == "2026-04-15"
    assert meta["upload_date"] == "2026-04-15"


def test_both_date_keys_are_none_together_when_no_date_is_known(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "v2", "T")
    meta, _ = _written(tmp_path, "v2")
    assert meta["published"] is None and meta["upload_date"] is None


# --------------------------------------------------------------------------- #
# _run_ytdlp() encoding and None-safety (B-10)

@pytest.mark.allow_subprocess
def test_run_ytdlp_round_trips_a_non_cp1252_title_byte_identically():
    """B-10, the reproduction, as a test.

    U+1F60D's UTF-8 bytes include 0x8D, which is undefined in cp1252: under
    text=True the reader thread dies and subprocess.run returns stdout=None.
    U+1F525's bytes are all cp1252-defined, so it decodes into four mojibake
    characters instead of crashing. Both are in this title, plus a Latin-1
    letter whose corruption is visible in a filename.
    """
    title = "Playa \U0001F60D Ocotal \U0001F525 naïve wins"
    script = (
        "import sys, json;"
        "sys.stdout.buffer.write(json.dumps("
        f"{{'entries': [{{'id': 'v1', 'title': {title!r}}}]}}"
        ", ensure_ascii=False).encode('utf-8'))"
    )
    monkey_bin = [sys.executable, "-c", script]
    proc = yt._run_ytdlp(monkey_bin[1:], binary=monkey_bin[:1], label="test")

    assert proc.returncode == 0
    entry = json.loads(proc.stdout)["entries"][0]
    assert entry["title"] == title
    assert entry["title"].encode("utf-8") == title.encode("utf-8")


def test_run_ytdlp_never_returns_none_stdout(monkeypatch):
    """The AttributeError branch: a dead reader thread yields stdout=None."""
    class DeadReader:
        returncode = 0
        stdout = None
        stderr = None

    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: DeadReader())
    proc = yt._run_ytdlp(["-J"], label="test")
    assert proc.stdout == ""
    assert proc.stderr == ""
    assert proc.stdout.strip() == ""  # would AttributeError today


def test_run_ytdlp_passes_utf8_encoding_not_bare_text_mode(monkeypatch):
    seen = {}
    monkeypatch.setattr(yt.subprocess, "run",
                        lambda *a, **k: seen.update(k) or _proc(0, "{}", ""))
    yt._run_ytdlp(["-J"], label="test")
    assert seen["encoding"] == "utf-8"
    assert seen["errors"] == "replace"
    assert "text" not in seen


def _install_fake_transcript_api(monkeypatch, exc_names, raising):
    """Install a stand-in youtube_transcript_api whose fetch() raises `raising`."""
    module = type(sys)("youtube_transcript_api")
    for name in exc_names:
        setattr(module, name, type(name, (Exception,), {}))

    class FakeApi:
        def fetch(self, vid):
            raise getattr(module, raising)("boom")

    module.YouTubeTranscriptApi = FakeApi
    monkeypatch.setitem(sys.modules, "youtube_transcript_api", module)
    return module


_EXC_NAMES = ("TranscriptsDisabled", "NoTranscriptFound", "VideoUnavailable",
              "IpBlocked", "RequestBlocked", "TooManyRequests", "YouTubeRequestFailed")


def test_a_genuinely_captionless_video_returns_none(monkeypatch):
    _install_fake_transcript_api(monkeypatch, _EXC_NAMES, "TranscriptsDisabled")
    assert yt._fetch_transcript_fallback("v1") is None


@pytest.mark.parametrize("blocked", ["IpBlocked", "RequestBlocked", "TooManyRequests",
                                     "YouTubeRequestFailed"])
def test_a_blocked_transcript_fetch_raises(monkeypatch, blocked):
    _install_fake_transcript_api(monkeypatch, _EXC_NAMES, blocked)
    with pytest.raises(yt.TranscriptFetchBlocked):
        yt._fetch_transcript_fallback("v1")


def test_blocked_is_distinguishable_from_captionless(monkeypatch):
    _install_fake_transcript_api(monkeypatch, _EXC_NAMES, "NoTranscriptFound")
    assert yt._fetch_transcript_fallback("v1") is None
    _install_fake_transcript_api(monkeypatch, _EXC_NAMES, "IpBlocked")
    with pytest.raises(yt.TranscriptFetchBlocked):
        yt._fetch_transcript_fallback("v1")


def test_an_unrecognised_transcript_exception_is_treated_as_blocked(monkeypatch, logged):
    """Fail toward retryable. Mis-classifying a block as "no captions" writes a
    permanent transcript-less capture (B-12); the reverse costs one retry."""
    _install_fake_transcript_api(monkeypatch, (*_EXC_NAMES, "SomeNewLibraryError"),
                                 "SomeNewLibraryError")
    with pytest.raises(yt.TranscriptFetchBlocked):
        yt._fetch_transcript_fallback("v1")
    assert [r for r in logged if r["event"] == "adapter.transcript_error_unclassified"]
