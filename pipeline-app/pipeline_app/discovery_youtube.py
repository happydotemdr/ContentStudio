"""YouTube platform adapter for the discovery engine. All yt-dlp/network
calls are isolated here so discovery_engine's core algorithm (Task 9) can be
unit-tested against a fake adapter with no network access. Download logic
(vtt parsing, transcript fallback, .md formatting) is ported from
download_brandintel.py's process_youtube_video (that script stays unmodified
-- see the design spec)."""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import datetime as _dt
from pathlib import Path

from pipeline_app.discovery_paths import handle_dir, slugify

USER_AGENT = "ContentStudio-discovery-engine/1.0 (personal archival; local inspection)"


def on_disk_ids(repo_root: Path, handle: str) -> set[str]:
    directory = handle_dir(repo_root, "youtube", handle)
    if not directory.exists():
        return set()
    return {p.name.split("__", 1)[0] for p in directory.glob("*__*.md")}


def enumerate_newest_first(handle: str, keyword_filter: str | None) -> list[dict]:
    url = f"https://www.youtube.com/{handle}/videos"
    cmd = ["yt-dlp", "-J", "--flat-playlist", "--ignore-errors", url]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        print(f"  ! yt-dlp enumerate failed for {handle}: {proc.stderr.strip()[:200]}", file=sys.stderr)
        return []
    data = json.loads(proc.stdout)
    entries = data.get("entries") or []
    items = [
        {"id": e["id"], "title": e.get("title") or e["id"], "published": None}
        for e in entries if e and e.get("id")
    ]
    if keyword_filter:
        items = [i for i in items if keyword_filter.lower() in i["title"].lower()]
    return items


def peek_upload_date(video_id: str) -> str | None:
    # Use a dedicated temp directory rather than a bare relative path in the
    # process's CWD: under a UI-triggered run _spawn_cron sets cwd=repo_root,
    # but the registered Windows Scheduled Task has no explicit working
    # directory, so a scheduled wake could run from an arbitrary directory
    # (e.g. C:\Windows\System32) where a relative write may be denied,
    # silently breaking new-handle discovery.
    tmp_dir = Path(tempfile.mkdtemp(prefix="discovery_peek_"))
    try:
        tmp_stem = tmp_dir / f"_peek_{video_id}"
        url = f"https://www.youtube.com/watch?v={video_id}"
        cmd = [
            "yt-dlp", "--skip-download", "--write-info-json", "--no-warnings",
            "--ignore-errors", "-o", str(tmp_stem) + ".%(ext)s", url,
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        info_path = tmp_stem.with_suffix(".info.json")
        if not info_path.exists():
            return None
        info = json.loads(info_path.read_text(encoding="utf-8"))
        upload_date = info.get("upload_date")
        if not upload_date or len(upload_date) != 8:
            return None
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _vtt_to_text(vtt: str) -> str:
    lines_out: list[str] = []
    prev = None
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line or line == "WEBVTT" or line.startswith(("NOTE", "Kind:", "Language:")):
            continue
        if "-->" in line or re.fullmatch(r"\d+", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = html.unescape(line).strip()
        if not line or line == prev:
            continue
        lines_out.append(line)
        prev = line
    return "\n".join(lines_out)


def _fetch_transcript_fallback(video_id: str) -> str | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
        parts = [getattr(s, "text", "") for s in fetched]
        text = "\n".join(t for t in (p.strip() for p in parts) if t)
        return text or None
    except Exception:
        return None


def download_item(repo_root: Path, handle: str, video_id: str, title: str) -> dict:
    out_dir = handle_dir(repo_root, "youtube", handle)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = repo_root / "output" / "brand-intel" / "youtube" / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    url = f"https://www.youtube.com/watch?v={video_id}"
    stem = tmp_dir / video_id
    cmd = [
        "yt-dlp", "--skip-download", "--write-info-json",
        "--write-auto-subs", "--write-subs", "--sub-langs", "en.*",
        "--sub-format", "vtt", "--ignore-errors", "--no-warnings",
        "--retries", "5", "--sleep-requests", "2",
        "-o", str(stem) + ".%(ext)s", url,
    ]
    subprocess.run(cmd, capture_output=True, text=True)

    info = {}
    info_path = stem.with_suffix(".info.json")
    if info_path.exists():
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            info = {}

    transcript, source = "", "none"
    vtts = sorted(tmp_dir.glob(f"{video_id}*.vtt"))
    if vtts:
        transcript = _vtt_to_text(vtts[0].read_text(encoding="utf-8", errors="replace"))
        source = "yt-dlp"
    if not transcript:
        fb = _fetch_transcript_fallback(video_id)
        if fb:
            transcript, source = fb, "youtube-transcript-api"

    # Determine actual download success: info.json must exist (yt-dlp must have
    # succeeded in getting metadata). Without it, the download truly failed.
    if not info_path.exists():
        # Clean up temp files and return failure without writing dest, so the
        # video stays eligible for retry on the next run.
        for p in tmp_dir.glob(f"{video_id}*"):
            p.unlink(missing_ok=True)
        return {"id": video_id, "ok": False, "published": None}

    description = info.get("description") or ""
    upload_date = info.get("upload_date") or ""
    if upload_date and len(upload_date) == 8:
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")

    dest = out_dir / f"{video_id}__{slugify(title)}.md"
    md = [
        f"# {title}", "", "## metadata",
        f"- url: {url}", f"- video_id: {video_id}",
        f"- channel: {info.get('uploader') or handle}",
        f"- upload_date: {upload_date}",
        f"- duration_s: {info.get('duration') or ''}",
        f"- transcript_source: {source}", f"- fetched_at: {fetched_at}", "",
        "## description", "", description.strip() or "(none)", "",
        "## transcript", "", transcript.strip() or "(no transcript available)", "",
    ]
    # Write to a temp path and rename into place (atomic on both POSIX and
    # Windows via Path.replace) rather than writing dest directly -- an
    # interrupted write (process killed mid-download) must never leave a
    # truncated file at a path the next run's on_disk_ids() would treat as
    # already-captured.
    tmp_dest = dest.with_name(dest.name + ".tmp")
    tmp_dest.write_text("\n".join(md), encoding="utf-8")
    tmp_dest.replace(dest)

    for p in tmp_dir.glob(f"{video_id}*"):
        p.unlink(missing_ok=True)

    return {"id": video_id, "ok": True, "published": upload_date or None}
