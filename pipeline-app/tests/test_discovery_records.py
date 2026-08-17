from pathlib import Path

import yaml

from pipeline_app.discovery_records import write_run_record


def _run_row():
    return {
        "run_id": "2026-07-30T06-00-00-0500", "trigger": "scheduled", "mode": "incremental",
        "status": "completed_with_errors", "started_at": "2026-07-30T06:00:00-05:00",
        "finished_at": "2026-07-30T06:04:12-05:00", "backfill_start": None, "backfill_end": None,
    }


def _r():
    return {
        "handle": "@h", "platform": "instagram", "cohort": "guru", "status": "ok",
        "items_downloaded": 0, "last_seen_published_at": None, "error_message": None,
    }


def test_write_run_record_creates_file_with_frontmatter_and_summary(tmp_path: Path):
    run_row = {
        "run_id": "2026-07-30T06-00-00-0500", "trigger": "scheduled", "mode": "incremental",
        "status": "completed_with_errors", "started_at": "2026-07-30T06:00:00-05:00",
        "finished_at": "2026-07-30T06:04:12-05:00", "backfill_start": None, "backfill_end": None,
    }
    handle_results = [
        {"handle": "@Romayroh", "platform": "youtube", "cohort": "guru", "status": "ok",
         "items_downloaded": 2, "last_seen_published_at": "2026-07-28", "error_message": None},
        {"handle": "@ThatNateBlack", "platform": "youtube", "cohort": "shorts-specialist",
         "status": "no_new_content", "items_downloaded": 0, "last_seen_published_at": None, "error_message": None},
        {"handle": "@dead-handle", "platform": "youtube", "cohort": "guru", "status": "handle_not_found",
         "items_downloaded": 0, "last_seen_published_at": None,
         "error_message": "yt-dlp enumerate returned empty"},
    ]
    path = write_run_record(tmp_path, run_row, handle_results)
    assert path == tmp_path / "output" / "discovery-runs" / "2026-07-30T06-00-00-0500.md"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    frontmatter_text = text.split("---\n")[1]
    frontmatter = yaml.safe_load(frontmatter_text)
    assert frontmatter["handles_processed"] == 3
    assert frontmatter["items_downloaded"] == 2
    assert frontmatter["handles_ok"] == 1
    assert frontmatter["handles_no_new_content"] == 1
    assert frontmatter["handles_not_found"] == 1
    assert frontmatter["handles_errored"] == 0
    assert "@Romayroh" in text
    assert "yt-dlp enumerate returned empty" in text
    # never includes actual transcript/description content:
    assert "no transcript available" not in text


def test_write_run_record_creates_parent_directory(tmp_path: Path):
    run_row = {
        "run_id": "r1", "trigger": "manual", "mode": "backfill", "status": "completed",
        "started_at": "2026-07-30T06:00:00Z", "finished_at": "2026-07-30T06:01:00Z",
        "backfill_start": "2026-06-01", "backfill_end": "2026-06-30",
    }
    path = write_run_record(tmp_path, run_row, [])
    assert path.exists()
    frontmatter = yaml.safe_load(path.read_text(encoding="utf-8").split("---\n")[1])
    assert frontmatter["backfill_range"] == {"start": "2026-06-01", "end": "2026-06-30"}


def test_frontmatter_status_counts_always_sum_to_handles_processed(tmp_path):
    """B-56: status_counts was seeded with four keys so four lookups could not
    KeyError; .get(status, 0) + 1 happily admitted a fifth, 'skipped', which a
    backfill produces for every Bright Data handle -- and nothing emitted it.
    handles_processed: 12 with the four published counters summing to 3."""
    results = [
        {"handle": f"@h{i}", "platform": "instagram", "cohort": "guru", "status": status,
         "items_downloaded": 0, "last_seen_published_at": None, "error_message": None}
        for i, status in enumerate(["ok", "no_new_content", "skipped", "skipped",
                                    "handle_not_found", "error"])
    ]
    path = write_run_record(tmp_path, _run_row(), results)
    fm = yaml.safe_load(path.read_text(encoding="utf-8").split("---\n")[1])
    counters = {k: v for k, v in fm.items() if k.startswith("handles_") and k != "handles_processed"}
    assert sum(counters.values()) == fm["handles_processed"] == 6
    assert fm["handles_skipped"] == 2


def test_a_future_handle_status_cannot_silently_vanish_from_the_frontmatter(tmp_path):
    """The key set is derived from the observed statuses, so a status added
    later is emitted rather than dropped."""
    results = [{**_r(), "status": "quarantined"}]
    fm = yaml.safe_load(write_run_record(tmp_path, _run_row(), results)
                        .read_text(encoding="utf-8").split("---\n")[1])
    assert fm["handles_quarantined"] == 1


def test_the_summary_sentence_mentions_skipped_handles(tmp_path):
    results = [{**_r(), "status": "skipped"}, {**_r(), "status": "skipped"},
               {**_r(), "status": "ok"}]
    path = write_run_record(tmp_path, _run_row(), results)
    text = path.read_text(encoding="utf-8")
    summary = text.split("## Summary")[1].split("## Per-handle results")[0]
    assert "2 skipped" in summary
