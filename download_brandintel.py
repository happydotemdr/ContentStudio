#!/usr/bin/env python3
"""Download the headless YouTube / brand-intel corpus with REAL transcripts.

Reads manifests/brand_sources.json and, for each source, fetches original text
straight from the public platform (no other app or database involved):

  YouTube  -> yt-dlp enumerates a channel's uploads from its @handle, then per
              video writes title + full description + metadata + the actual
              spoken-word TRANSCRIPT (auto/manual captions, VTT -> clean text).
              Falls back to youtube-transcript-api when yt-dlp yields no subs.
  Bluesky  -> public AppView getAuthorFeed; full post text (reposts skipped).
  RSS/Atom -> feed body, HTML-stripped to plain text.

Output:
  output/brand-intel/youtube/<handle>/<videoId>__<title>.md
  output/brand-intel/bluesky/<handle>/<rkey>.md
  output/brand-intel/rss/<feed>/<entry>.md
  output/brand-intel/_manifest.csv   (index of everything pulled)

Resumable: an existing output file for an item is skipped. YouTube soft-limits
~100-200 transcript fetches/hour/IP; this paces requests. If you get throttled,
pass --cookies-from-browser BROWSER (e.g. chrome/firefox) to use your own
logged-in session.

Usage:
  python download_brandintel.py [--limit N] [--full-channel]
                                [--platforms youtube,bluesky,rss]
                                [--cookies-from-browser BROWSER]
                                [--sleep SECONDS] [--force]
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifests" / "brand_sources.json"
OUT = HERE / "output" / "brand-intel"
USER_AGENT = "ContentStudio-corpus-archive/1.0 (personal archival; local inspection)"
BLUESKY_API = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"

MANIFEST_ROWS: list[dict] = []


def slugify(value: str, maxlen: int = 80) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE).strip().lower()
    value = re.sub(r"[\s_-]+", "-", value)
    return (value[:maxlen].rstrip("-")) or "untitled"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# --------------------------------------------------------------------------- #
# YouTube
# --------------------------------------------------------------------------- #
def have_ytdlp() -> bool:
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def ytdlp_enumerate(handle: str, limit: int | None) -> list[dict]:
    """Return [{id, title}] for a channel's uploads via flat-playlist."""
    url = f"https://www.youtube.com/{handle}/videos"
    cmd = ["yt-dlp", "-J", "--flat-playlist", "--ignore-errors"]
    if limit:
        cmd += ["--playlist-end", str(limit)]
    cmd.append(url)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        print(f"  ! yt-dlp enumerate failed for {handle}: {proc.stderr.strip()[:200]}",
              file=sys.stderr)
        return []
    data = json.loads(proc.stdout)
    entries = data.get("entries") or []
    out = []
    for e in entries:
        if e and e.get("id"):
            out.append({"id": e["id"], "title": e.get("title") or e["id"]})
    return out


def vtt_to_text(vtt: str) -> str:
    lines_out: list[str] = []
    prev = None
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line or line == "WEBVTT" or line.startswith(("NOTE", "Kind:", "Language:")):
            continue
        if "-->" in line:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)          # <c>, <00:00:00.000> tags
        line = html.unescape(line).strip()
        if not line or line == prev:                 # dedupe rolling-caption overlap
            continue
        lines_out.append(line)
        prev = line
    return "\n".join(lines_out)


def fetch_transcript_fallback(video_id: str) -> str | None:
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
    except Exception as exc:  # noqa: BLE001 - library raises many specific types
        print(f"    fallback transcript-api failed ({video_id}): {type(exc).__name__}",
              file=sys.stderr)
        return None


def process_youtube_video(vid: dict, handle: str, out_dir: Path, tmp_dir: Path,
                          cookies: list[str], force: bool) -> None:
    video_id = vid["id"]
    title = vid["title"]
    dest = out_dir / f"{video_id}__{slugify(title)}.md"
    if dest.exists() and not force:
        print(f"    = skip {video_id} (exists)")
        return

    url = f"https://www.youtube.com/watch?v={video_id}"
    stem = tmp_dir / video_id
    cmd = [
        "yt-dlp", "--skip-download", "--write-info-json",
        "--write-auto-subs", "--write-subs", "--sub-langs", "en.*",
        "--sub-format", "vtt", "--ignore-errors", "--no-warnings",
        "--retries", "5", "--sleep-requests", "2",
        "-o", str(stem) + ".%(ext)s", url,
    ] + cookies
    subprocess.run(cmd, capture_output=True, text=True)

    info = {}
    info_path = stem.with_suffix(".info.json")
    if info_path.exists():
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            info = {}

    # locate a written .vtt (yt-dlp names it <stem>.<lang>.vtt)
    transcript = ""
    source = "none"
    vtts = sorted(tmp_dir.glob(f"{video_id}*.vtt"))
    if vtts:
        transcript = vtt_to_text(vtts[0].read_text(encoding="utf-8", errors="replace"))
        source = "yt-dlp"
    if not transcript:
        fb = fetch_transcript_fallback(video_id)
        if fb:
            transcript, source = fb, "youtube-transcript-api"

    description = info.get("description") or ""
    upload_date = info.get("upload_date") or ""
    if upload_date and len(upload_date) == 8:
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"

    md = [
        f"# {title}",
        "",
        "## metadata",
        f"- url: {url}",
        f"- video_id: {video_id}",
        f"- channel: {info.get('uploader') or handle}",
        f"- upload_date: {upload_date}",
        f"- duration_s: {info.get('duration') or ''}",
        f"- views: {info.get('view_count') or ''}",
        f"- likes: {info.get('like_count') or ''}",
        f"- transcript_source: {source}",
        f"- fetched_at: {now_iso()}",
        "",
        "## description",
        "",
        description.strip() or "(none)",
        "",
        "## transcript",
        "",
        transcript.strip() or "(no transcript available)",
        "",
    ]
    dest.write_text("\n".join(md), encoding="utf-8")
    MANIFEST_ROWS.append({
        "platform": "youtube", "handle": handle, "id": video_id, "url": url,
        "title": title, "published": upload_date,
        "has_transcript": bool(transcript), "transcript_source": source,
        "file": str(dest.relative_to(OUT.parent.parent)),
    })
    print(f"    + {video_id} [{source}] {title[:60]}")

    # cleanup temp artifacts for this video
    for p in tmp_dir.glob(f"{video_id}*"):
        p.unlink(missing_ok=True)


def do_youtube(sources: list[dict], limit: int | None, cookies: list[str],
               sleep_s: float, force: bool) -> None:
    if not sources:
        return
    if not have_ytdlp():
        print("! yt-dlp not found - skipping YouTube. Install: pip install -r requirements.txt",
              file=sys.stderr)
        return
    tmp_dir = OUT / "youtube" / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for src in sources:
        handle = src["handle"]
        kw = src.get("keyword_filter")
        print(f"\n[youtube] {handle}"
              + (f"  (filter: '{kw}')" if kw else "")
              + (f"  limit={limit}" if limit else "  (full channel)"))
        out_dir = OUT / "youtube" / slugify(handle.lstrip("@"))
        out_dir.mkdir(parents=True, exist_ok=True)
        vids = ytdlp_enumerate(handle, limit)
        if kw:
            vids = [v for v in vids if kw.lower() in (v["title"] or "").lower()]
        print(f"  {len(vids)} videos to process")
        for v in vids:
            process_youtube_video(v, handle, out_dir, tmp_dir, cookies, force)
            time.sleep(sleep_s)
    # remove temp dir if empty
    try:
        tmp_dir.rmdir()
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Bluesky
# --------------------------------------------------------------------------- #
def do_bluesky(sources: list[dict], limit: int | None, force: bool) -> None:
    for src in sources:
        handle = src["handle"]
        print(f"\n[bluesky] {handle}")
        out_dir = OUT / "bluesky" / slugify(handle)
        out_dir.mkdir(parents=True, exist_ok=True)
        cursor = None
        target = limit or 100
        collected = 0
        while collected < target:
            params = {"actor": handle, "limit": str(min(100, target - collected))}
            if cursor:
                params["cursor"] = cursor
            try:
                data = json.loads(http_get(f"{BLUESKY_API}?{urllib.parse.urlencode(params)}"))
            except Exception as exc:  # noqa: BLE001
                print(f"  ! bluesky fetch failed: {type(exc).__name__}: {exc}", file=sys.stderr)
                break
            feed = data.get("feed") or []
            if not feed:
                break
            for item in feed:
                if item.get("reason"):          # skip reposts
                    continue
                post = item.get("post") or {}
                record = post.get("record") or {}
                text = (record.get("text") or "").strip()
                uri = post.get("uri") or ""
                rkey = uri.rsplit("/", 1)[-1] if uri else str(collected)
                created = record.get("createdAt") or post.get("indexedAt") or ""
                purl = f"https://bsky.app/profile/{handle}/post/{rkey}"
                dest = out_dir / f"{rkey}.md"
                collected += 1
                if dest.exists() and not force:
                    continue
                md = [
                    f"# bluesky post {rkey}",
                    "",
                    f"- url: {purl}",
                    f"- author: {handle}",
                    f"- created: {created}",
                    f"- fetched_at: {now_iso()}",
                    "",
                    text or "(empty)",
                    "",
                ]
                dest.write_text("\n".join(md), encoding="utf-8")
                MANIFEST_ROWS.append({
                    "platform": "bluesky", "handle": handle, "id": rkey, "url": purl,
                    "title": text[:60], "published": created,
                    "has_transcript": "", "transcript_source": "",
                    "file": str(dest.relative_to(OUT.parent.parent)),
                })
            cursor = data.get("cursor")
            if not cursor:
                break
        print(f"  {collected} posts")


# --------------------------------------------------------------------------- #
# RSS / Atom
# --------------------------------------------------------------------------- #
def strip_html(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def do_rss(sources: list[dict], force: bool) -> None:
    for src in sources:
        feed_url = src.get("handle")
        if not feed_url or not feed_url.startswith("http"):
            continue
        print(f"\n[rss] {feed_url}")
        out_dir = OUT / "rss" / slugify(urllib.parse.urlparse(feed_url).netloc)
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            root = ET.fromstring(http_get(feed_url))
        except Exception as exc:  # noqa: BLE001
            print(f"  ! rss fetch/parse failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)
        count = 0
        for it in items:
            def get(tag: str) -> str:
                el = it.find(tag) or it.find(f"atom:{tag}", ns)
                return (el.text or "") if el is not None else ""
            title = get("title") or "untitled"
            body = ""
            for tag in ("{http://purl.org/rss/1.0/modules/content/}encoded",
                        "description", "atom:content", "atom:summary"):
                el = it.find(tag, ns) if ":" in tag else it.find(tag)
                if el is not None and el.text:
                    body = el.text
                    break
            link = get("link") or get("guid") or get("id")
            slug = slugify(title)
            dest = out_dir / f"{slug}.md"
            count += 1
            if dest.exists() and not force:
                continue
            dest.write_text(
                f"# {title}\n\n- url: {link}\n- fetched_at: {now_iso()}\n\n{strip_html(body)}\n",
                encoding="utf-8")
            MANIFEST_ROWS.append({
                "platform": "rss", "handle": feed_url, "id": slug, "url": link,
                "title": title[:60], "published": "", "has_transcript": "",
                "transcript_source": "", "file": str(dest.relative_to(OUT.parent.parent)),
            })
        print(f"  {count} entries")


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Download the brand-intel / YouTube corpus.")
    ap.add_argument("--limit", type=int, default=25,
                    help="max videos/posts per source (default 25). Ignored for YouTube with --full-channel.")
    ap.add_argument("--full-channel", action="store_true",
                    help="pull every video in each YouTube channel, not just the recent window")
    ap.add_argument("--platforms", default="youtube,bluesky,rss",
                    help="comma list of platforms to run")
    ap.add_argument("--cookies-from-browser", default="",
                    help="browser to read YouTube cookies from if throttled (e.g. chrome, firefox)")
    ap.add_argument("--sleep", type=float, default=2.0, help="seconds between YouTube videos")
    ap.add_argument("--force", action="store_true", help="re-download items that already exist")
    args = ap.parse_args()

    roster = json.loads(MANIFEST.read_text(encoding="utf-8"))
    platforms = {p.strip() for p in args.platforms.split(",") if p.strip()}
    yt_limit = None if args.full_channel else args.limit
    cookies = (["--cookies-from-browser", args.cookies_from_browser]
               if args.cookies_from_browser else [])
    OUT.mkdir(parents=True, exist_ok=True)

    if "youtube" in platforms:
        do_youtube([s for s in roster.get("youtube", []) if "handle" in s],
                   yt_limit, cookies, args.sleep, args.force)
    if "bluesky" in platforms:
        do_bluesky([s for s in roster.get("bluesky", []) if "handle" in s],
                   args.limit, args.force)
    if "rss" in platforms:
        do_rss([s for s in roster.get("rss", []) if s.get("handle", "").startswith("http")],
               args.force)

    if MANIFEST_ROWS:
        csv_path = OUT / "_manifest.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(MANIFEST_ROWS[0].keys()))
            writer.writeheader()
            writer.writerows(MANIFEST_ROWS)
        print(f"\nbrand-intel: {len(MANIFEST_ROWS)} items -> {OUT}\nindex: {csv_path}")
    else:
        print("\nbrand-intel: no items written (check sources / network / yt-dlp install)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
