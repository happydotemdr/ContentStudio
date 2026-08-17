"""Writes the paired output/discovery-runs/<run_id>.md record for a
finished discovery run. Never includes extracted transcript/description
text -- only counts, statuses, and handle identifiers."""
from __future__ import annotations

from pathlib import Path

import yaml

from pipeline_app.discovery_paths import run_record_path


def write_run_record(repo_root: Path, run_row: dict, handle_results: list[dict],
                      partial: bool = False) -> Path:
    KNOWN = ("ok", "no_new_content", "handle_not_found", "error", "skipped")
    status_counts = dict.fromkeys(KNOWN, 0)
    items_downloaded = 0
    for r in handle_results:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        items_downloaded += r["items_downloaded"]

    backfill_range = None
    if run_row.get("backfill_start"):
        backfill_range = {"start": run_row["backfill_start"], "end": run_row["backfill_end"]}

    frontmatter = {
        "run_id": run_row["run_id"],
        "trigger": run_row["trigger"],
        "mode": run_row["mode"],
        "status": run_row["status"],
        "started_at": run_row["started_at"],
        "finished_at": run_row["finished_at"],
        "backfill_range": backfill_range,
        "handles_processed": len(handle_results),
        "items_downloaded": items_downloaded,
    }
    # Two statuses publish under legacy frontmatter key names (existing parsers
    # depend on "handles_not_found"/"handles_errored", not the raw status text)
    # -- every other status, known or future, publishes as "handles_<status>".
    LEGACY_KEY_NAMES = {"handle_not_found": "not_found", "error": "errored"}
    frontmatter.update({
        f"handles_{LEGACY_KEY_NAMES.get(status, status)}": count
        for status, count in status_counts.items()
    })

    summary_prefix = "Partial -- the process died; these counts are a floor. " if partial else ""
    lines = ["---", yaml.safe_dump(frontmatter, sort_keys=False).rstrip("\n"), "---", "",
              "## Summary", "",
              f"{summary_prefix}Pulled {items_downloaded} new items across {status_counts['ok']} handles with "
              f"new content. {status_counts['handle_not_found']} handle(s) not found, "
              f"{status_counts['error']} errored, {status_counts['skipped']} skipped.", "",
              "## Per-handle results", ""]
    for r in handle_results:
        detail = f"{r['items_downloaded']} new items" if r["status"] == "ok" else r["status"]
        if r.get("last_seen_published_at"):
            detail += f", last_seen now {r['last_seen_published_at']}"
        if r.get("error_message"):
            detail += f": {r['error_message']}"
        lines.append(f"- {r['handle']} ({r['platform']}, {r['cohort']}) — {detail}")

    dest = run_record_path(repo_root, run_row["run_id"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest
