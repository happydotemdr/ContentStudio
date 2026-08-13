from pathlib import Path

from pipeline_app import artifacts
from scripts import backfill_youtube_frontmatter as backfill

OLD_FORMAT = """# AVOID These YouTube Tips At All Costs!!!

## metadata
- url: https://www.youtube.com/watch?v=0l2g3Bujy1Y
- video_id: 0l2g3Bujy1Y
- channel: Nick Nimmin
- upload_date: 2025-08-16
- duration_s: 441
- transcript_source: yt-dlp
- fetched_at: 2026-07-23T17:58:26+00:00

## description

A real description here.

## transcript

first line of transcript
second line of transcript
"""

OLD_FORMAT_NO_TRANSCRIPT = """# Some Blocked Video

## metadata
- url: https://www.youtube.com/watch?v=blocked1
- video_id: blocked1
- channel: @somehandle
- upload_date:
- duration_s:
- transcript_source: none
- fetched_at: 2026-07-30T23:31:02+00:00

## description

(none)

## transcript

(no transcript available)
"""


def _corpus(tmp_path: Path, name: str, text: str) -> Path:
    channel_dir = tmp_path / "nicknimmin"
    channel_dir.mkdir(parents=True, exist_ok=True)
    path = channel_dir / name
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# parsing the old format

def test_parse_existing_reads_old_metadata_block(tmp_path):
    path = _corpus(tmp_path, "0l2g3Bujy1Y__avoid-these.md", OLD_FORMAT)
    rec = backfill.parse_existing(path)
    assert rec["video_id"] == "0l2g3Bujy1Y"
    assert rec["channel"] == "Nick Nimmin"
    assert rec["upload_date"] == "2025-08-16"
    assert rec["transcript_source"] == "yt-dlp"
    assert rec["title"] == "AVOID These YouTube Tips At All Costs!!!"
    assert "first line of transcript" in rec["transcript"]
    assert rec["description"] == "A real description here."


def test_parse_existing_treats_placeholders_as_empty(tmp_path):
    path = _corpus(tmp_path, "blocked1__some-blocked-video.md", OLD_FORMAT_NO_TRANSCRIPT)
    rec = backfill.parse_existing(path)
    assert rec["transcript"] == ""
    assert rec["description"] == ""


def test_parse_existing_falls_back_to_filename_for_video_id(tmp_path):
    path = _corpus(tmp_path, "abc999__no-metadata-at-all.md", "# Just a title\n")
    assert backfill.parse_existing(path)["video_id"] == "abc999"


# --------------------------------------------------------------------------- #
# building the new frontmatter

def test_build_meta_marks_present_transcript(tmp_path):
    rec = backfill.parse_existing(_corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT))
    meta = backfill.build_meta(rec, None)
    assert meta["transcript_status"] == "present"
    assert meta["transcript_source"] == "yt-dlp"


def test_build_meta_marks_missing_transcript(tmp_path):
    rec = backfill.parse_existing(_corpus(tmp_path, "blocked1__x.md", OLD_FORMAT_NO_TRANSCRIPT))
    meta = backfill.build_meta(rec, None)
    assert meta["transcript_status"] == "missing"
    assert meta["transcript_source"] == "none"


def test_build_meta_merges_api_fields(tmp_path):
    rec = backfill.parse_existing(_corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT))
    meta = backfill.build_meta(rec, {
        "channel": "Nick Nimmin", "upload_date": "2025-08-16", "duration_s": 441,
        "view_count": 24013, "like_count": 1184, "comment_count": 97,
        "manual_captions": True,
    })
    assert meta["view_count"] == 24013
    assert meta["manual_captions"] is True
    assert meta["metadata_source"] == "youtube-data-api-v3"


def test_build_meta_without_api_keeps_ytdlp_provenance(tmp_path):
    rec = backfill.parse_existing(_corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT))
    meta = backfill.build_meta(rec, None)
    assert meta["metadata_source"] == "yt-dlp"
    assert meta["view_count"] is None
    assert meta["duration_s"] == 441  # coerced from the old string


# --------------------------------------------------------------------------- #
# round-trip

def test_render_preserves_transcript_and_description(tmp_path):
    rec = backfill.parse_existing(_corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT))
    out = backfill.render(rec, backfill.build_meta(rec, None))
    meta, body = artifacts.parse_frontmatter(out)
    assert meta["video_id"] == "0l2g3Bujy1Y"
    assert "first line of transcript" in body
    assert "second line of transcript" in body
    assert "A real description here." in body
    assert body.startswith("# AVOID These YouTube Tips")


def test_backfilled_file_reparses_cleanly(tmp_path):
    """Running the backfill twice must be a no-op, not a degradation."""
    path = _corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT)
    rec1 = backfill.parse_existing(path)
    path.write_text(backfill.render(rec1, backfill.build_meta(rec1, None)), encoding="utf-8")

    rec2 = backfill.parse_existing(path)
    assert rec2["video_id"] == rec1["video_id"]
    assert rec2["transcript"].strip() == rec1["transcript"].strip()
    assert rec2["title"] == rec1["title"]
    assert rec2["transcript_source"] == "yt-dlp"


# --------------------------------------------------------------------------- #
# main

def test_main_dry_run_does_not_modify_files(tmp_path, capsys):
    path = _corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT)
    before = path.read_text(encoding="utf-8")
    rc = backfill.main(["--corpus-root", str(tmp_path), "--no-api"])
    assert rc == 0
    assert path.read_text(encoding="utf-8") == before
    assert "Dry run" in capsys.readouterr().out


def test_main_apply_rewrites_to_frontmatter(tmp_path, capsys):
    path = _corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT)
    _corpus(tmp_path, "blocked1__y.md", OLD_FORMAT_NO_TRANSCRIPT)

    rc = backfill.main(["--corpus-root", str(tmp_path), "--no-api", "--apply"])
    assert rc == 0

    meta, body = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["transcript_status"] == "present"
    assert "first line of transcript" in body

    out = capsys.readouterr().out
    assert "rewrote 2 files" in out
    assert "transcript missing     : 1" in out


def test_main_reports_missing_corpus_root(tmp_path, capsys):
    assert backfill.main(["--corpus-root", str(tmp_path / "nope"), "--no-api"]) == 1


def test_apply_without_an_api_key_refuses_to_run(tmp_path, monkeypatch, capsys):
    """FAULT: D-04. fetch_metadata returns {} for a missing key, an exhausted
    quota and a dead network alike; the script then wrote nulls over
    everything and exited 0."""
    monkeypatch.setattr(backfill.youtube_api, "api_key", lambda: None)
    path = _corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT)
    before = path.read_text(encoding="utf-8")

    rc = backfill.main(["--corpus-root", str(tmp_path), "--apply"])

    assert rc == 2
    assert path.read_text(encoding="utf-8") == before, "not one byte may be written"
    err = capsys.readouterr().err
    assert "YOUTUBE_API_KEY" in err and "--no-api" in err


def test_no_api_is_the_explicit_escape_hatch(tmp_path, monkeypatch):
    """The refusal is not a wall: --no-api is the deliberate way through, and
    it must never claim API provenance."""
    monkeypatch.setattr(backfill.youtube_api, "api_key", lambda: None)
    path = _corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT)
    assert backfill.main(["--corpus-root", str(tmp_path), "--no-api", "--apply"]) == 0
    meta, _ = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["metadata_source"] == "yt-dlp"
