"""YouTube platform adapter for the discovery engine. All yt-dlp/network
calls are isolated here so discovery_engine's core algorithm (Task 9) can be
unit-tested against a fake adapter with no network access. Download logic
(vtt parsing, transcript fallback, .md formatting) is ported from
download_brandintel.py's process_youtube_video (that script stays unmodified
-- see the design spec)."""
from __future__ import annotations

import html
import itertools
import json
import re
import shutil
import subprocess
import sys
import tempfile
import datetime as _dt
from pathlib import Path

from pipeline_app import artifacts
from pipeline_app import discovery_youtube_api as youtube_api
from pipeline_app import obs
from pipeline_app.discovery_paths import handle_dir, slugify

USER_AGENT = "ContentStudio-discovery-engine/1.0 (personal archival; local inspection)"

# YouTube's per-video metadata/subtitle fetch (unlike channel-listing) requires
# an authenticated session or it fails with "Sign in to confirm you're not a
# bot" -- see download_brandintel.py's --cookies-from-browser flag, which this
# port omitted. --cookies-from-browser was tried first but Chrome locks its
# cookie DB while running (yt-dlp/yt-dlp#7271), making it unusable for an
# always-on service -- so this reads a cookies.txt exported once from a
# logged-in browser session instead (Netscape format, e.g. via the "Get
# cookies.txt LOCALLY" extension), which has no such live-process dependency.
COOKIES_PATH = Path(__file__).resolve().parent.parent / "cookies.txt"


def _cookie_args() -> list[str]:
    if COOKIES_PATH.exists():
        return ["--cookies", str(COOKIES_PATH)]
    print(f"  ! no cookies.txt at {COOKIES_PATH} -- per-video yt-dlp fetches will "
          f"likely fail YouTube's bot-check", file=sys.stderr)
    return []


YTDLP_BIN = ["yt-dlp"]


class YtDlpUnavailable(RuntimeError):
    """yt-dlp is not on PATH. Not a quiet channel -- an unusable environment."""


def _run_ytdlp(args: list[str], *, label: str,
               binary: list[str] | None = None) -> subprocess.CompletedProcess:
    """The single place this module spawns yt-dlp.

    encoding="utf-8", errors="replace" is load-bearing on Windows: bare
    text=True decodes yt-dlp's UTF-8 output with the host ANSI codepage
    (cp1252 here), which either kills the reader thread -- leaving
    stdout=None for the caller to trip over -- or silently mojibakes a title
    into the filename, the corpus and the daily email. Both were reproduced;
    see finding B-10.

    stdout/stderr are normalised to "" so no caller can ever face None.
    """
    cmd = [*(binary or YTDLP_BIN), *args]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="replace",
        )
    except FileNotFoundError as exc:
        obs.log("adapter.tool_missing", level="error", platform="youtube",
                tool=cmd[0], label=label)
        raise YtDlpUnavailable(f"yt-dlp not found on PATH (needed for {label})") from exc
    if proc.stdout is None:
        proc.stdout = ""
    if proc.stderr is None:
        proc.stderr = ""
    return proc


def _awaiting_transcript_retry(path: Path) -> bool:
    try:
        meta, _ = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, artifacts.MalformedArtifactError) as exc:
        obs.log("adapter.capture_unreadable", level="warning", platform="youtube",
                path=str(path), error=type(exc).__name__)
        return False
    return meta.get("transcript_status") == TRANSCRIPT_PENDING


def on_disk_ids(repo_root: Path, handle: str) -> set[str]:
    """Video ids already fully captured for `handle`.

    A capture whose transcript is pending_retry is deliberately NOT reported:
    it exists on disk but is incomplete, and returning it here is what made a
    bot-blocked capture permanent (B-12). download_item writes to the same
    dest path, so re-offering is idempotent.
    """
    directory = handle_dir(repo_root, "youtube", handle)
    if not directory.exists():
        return set()
    return {
        path.name.split("__", 1)[0]
        for path in directory.glob("*__*.md")
        if not _awaiting_transcript_retry(path)
    }


# A channel's Shorts live on a separate tab from its long-form uploads, and the
# two listings are DISJOINT -- /videos does not include Shorts. Measured on
# 2026-07-31: @goodinside /videos=274, /shorts=603, overlap=0. Enumerating only
# /videos made every Short on every channel invisible to discovery.
_TABS = (("videos", "video"), ("shorts", "short"))


class YouTubeEnumerationError(RuntimeError):
    """A channel-tab listing could not be fetched.

    Never raised for a tab that genuinely does not exist, and never for a tab
    that exists and is empty -- those return []. brightdata_job.py:6-10 states
    the invariant: an empty list means "the walk completed and there was
    nothing there". Returning [] on a failed fetch made a bot-block, a DNS
    outage and a quiet channel one indistinguishable state, which the engine
    recorded as the healthy 'no_new_content' (B-11).
    """


# yt-dlp exits non-zero both for "this tab does not exist" and for "the fetch
# failed". Only /shorts is legitimately absent -- every channel has /videos --
# and only these stderr shapes mean absence. Anything else is a failure.
_ABSENT_TAB_MARKERS = (
    "does not have a shorts tab",
    "this channel does not have",
    "http error 404",
)


def _is_absent_tab(tab: str, stderr: str) -> bool:
    if tab != "shorts":
        return False
    lowered = stderr.lower()
    return any(marker in lowered for marker in _ABSENT_TAB_MARKERS)


def _enumerate_tab(handle: str, tab: str, content_type: str) -> list[dict]:
    url = f"https://www.youtube.com/{handle}/{tab}"
    proc = _run_ytdlp(
        ["-J", "--flat-playlist", "--ignore-errors", *_cookie_args(), url],
        label=f"enumerate {handle}/{tab}",
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        if _is_absent_tab(tab, proc.stderr):
            return []
        detail = proc.stderr.strip()[:200] or f"exit {proc.returncode}, empty stdout"
        obs.log("adapter.enumerate_failed", level="error", platform="youtube",
                handle=handle, tab=tab, returncode=proc.returncode, stderr=detail)
        print(f"  !! yt-dlp enumerate failed for {handle}/{tab}: {detail}", file=sys.stderr)
        raise YouTubeEnumerationError(f"{handle}/{tab}: {detail}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        obs.log("adapter.enumerate_failed", level="error", platform="youtube",
                handle=handle, tab=tab, returncode=proc.returncode, stderr=str(exc)[:200])
        raise YouTubeEnumerationError(f"{handle}/{tab}: unparseable listing JSON") from exc
    return [
        {"id": e["id"], "title": e.get("title") or e["id"], "published": None,
         "content_type": content_type}
        for e in (data.get("entries") or []) if e and e.get("id")
    ]


def _interleave(videos: list[dict], shorts: list[dict]) -> list[dict]:
    """Merge two independently newest-first tabs with no dates to order by.

    Round-robin, not concatenation. Concatenation puts every Short after every
    video, so process_handle's consecutive-on-disk break ends the walk inside
    the /videos block and no Short is ever reached -- which is why the previous
    code dropped them outright instead. Round-robin is not a true global order
    (that is impossible without dates), so callers get order_confidence
    "approximate" and the condition is reported rather than silently narrowing
    the capture (B-14).
    """
    return [i for pair in itertools.zip_longest(videos, shorts)
            for i in pair if i is not None]


def enumerate_newest_first(handle: str, keyword_filter: str | None) -> list[dict]:
    """Every video AND Short for `handle`, merged into one newest-first list.

    Ordering is load-bearing: process_handle breaks out of the walk on
    consecutive-on-disk and on the date cutoff, so a list that is not globally
    newest-first would silently stop before reaching the second tab's items.
    Each tab is newest-first on its own but --flat-playlist carries no dates,
    so dates are batched from the Data API (1 quota unit per 50 ids) to
    establish a single order.
    """
    per_tab = {ct: _enumerate_tab(handle, tab, ct) for tab, ct in _TABS}
    videos = per_tab["video"]
    items = [i for tab_items in per_tab.values() for i in tab_items]

    # Defensive: dedupe by id in case YouTube ever surfaces an item on both tabs.
    seen: set[str] = set()
    items = [i for i in items if not (i["id"] in seen or seen.add(i["id"]))]

    dates = youtube_api.fetch_upload_dates([i["id"] for i in items])
    if dates:
        for item in items:
            item["published"] = dates.get(item["id"])
            item["order_confidence"] = "exact"
        # Undated items (deleted/private/API miss) sort last rather than
        # masquerading as the newest.
        items.sort(key=lambda i: i["published"] or "", reverse=True)
    else:
        if per_tab["short"]:
            obs.log("adapter.ordering_degraded", level="warning", platform="youtube",
                    handle=handle, shorts=len(per_tab["short"]), videos=len(videos))
            print(f"  ! no Data API dates for {handle}: Shorts and videos cannot be "
                  f"date-ordered, so the merged list is approximate. Set YOUTUBE_API_KEY "
                  f"for an exact order.", file=sys.stderr)
        items = _interleave(videos, per_tab["short"])
        for item in items:
            item["order_confidence"] = "approximate"

    if keyword_filter:
        items = [i for i in items if keyword_filter.lower() in i["title"].lower()]
    return items


def peek_upload_date(video_id: str) -> str | None:
    # Data API first: this is one of the two calls YouTube's per-video bot-block
    # takes out, and the API is key-authenticated rather than bot-gated. yt-dlp
    # remains the fallback for when no key is configured.
    record = youtube_api.fetch_one(video_id)
    if record and record.get("upload_date"):
        return record["upload_date"]

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
        proc = _run_ytdlp(
            ["--skip-download", "--write-info-json", "--no-warnings",
             "--ignore-errors", *_cookie_args(), "-o", str(tmp_stem) + ".%(ext)s", url],
            label=f"peek {video_id}",
        )
        if proc.returncode != 0:
            obs.log("adapter.peek_failed", level="warning", platform="youtube",
                    video_id=video_id, returncode=proc.returncode,
                    stderr=proc.stderr.strip()[:200])
        info_path = tmp_stem.with_suffix(".info.json")
        if not info_path.exists():
            return None
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            # download_item already guards the structurally identical parse;
            # the same corrupt file must not be fatal on one path and tolerated
            # on the other (B-16).
            obs.log("adapter.info_json_unparseable", level="warning",
                    platform="youtube", video_id=video_id, error=type(exc).__name__)
            return None
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


# Warn at most once per process: a missing dependency is a single fact about
# the environment, not a per-video event, and a corpus run processes hundreds
# of videos.
_TRANSCRIPT_API_MISSING_WARNED = False


MAX_TRANSCRIPT_ATTEMPTS = 3

TRANSCRIPT_PRESENT = "present"
TRANSCRIPT_MISSING = "missing"        # terminal: yt-dlp ran clean and there are no captions
TRANSCRIPT_PENDING = "pending_retry"  # transient: the fetch was blocked, try again next run


def _prior_transcript_attempts(dest: Path) -> int:
    if not dest.exists():
        return 0
    try:
        meta, _ = artifacts.parse_frontmatter(dest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    value = meta.get("transcript_attempts")
    return value if isinstance(value, int) and value >= 0 else 0


class TranscriptFetchBlocked(RuntimeError):
    """The transcript API refused or could not be reached.

    Distinct from "this video has no captions". The bare `except Exception:
    return None` collapsed IP-blocks, rate-limits, disabled transcripts and
    video-unavailable into one None, so an IP block during a 300-video run
    produced 300 permanently transcript-less captures indistinguishable from
    300 genuinely caption-free videos (B-13).
    """


# Exceptions that mean "there is no transcript for this video" -- a real,
# terminal answer. Resolved by name because the library's exception surface
# varies across versions and the import is lazy. Anything NOT named here is
# treated as a block: failing toward retryable costs one extra attempt, while
# failing the other way is B-12.
_BENIGN_TRANSCRIPT_ERRORS = (
    "TranscriptsDisabled", "NoTranscriptFound", "NoTranscriptAvailable",
    "VideoUnavailable", "VideoUnplayable",
)


def _is_benign_transcript_error(module, exc: BaseException) -> bool:
    classes = tuple(
        cls for cls in (getattr(module, name, None) for name in _BENIGN_TRANSCRIPT_ERRORS)
        if isinstance(cls, type) and issubclass(cls, BaseException)
    )
    return bool(classes) and isinstance(exc, classes)


def _fetch_transcript_fallback(video_id: str) -> str | None:
    global _TRANSCRIPT_API_MISSING_WARNED
    try:
        import youtube_transcript_api as _yta
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        # Previously this returned None silently, making an uninstalled
        # dependency indistinguishable from "this video has no transcript" --
        # youtube-transcript-api is declared in requirements.txt but was absent
        # from pipeline-app/.venv, so the fallback never ran and never said so.
        if not _TRANSCRIPT_API_MISSING_WARNED:
            _TRANSCRIPT_API_MISSING_WARNED = True
            print("  ! youtube-transcript-api is not installed -- the transcript "
                  "fallback is DISABLED and every video will report no transcript. "
                  "Install it: pip install -r requirements.txt", file=sys.stderr)
        return None
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id)
        parts = [getattr(s, "text", "") for s in fetched]
        text = "\n".join(t for t in (p.strip() for p in parts) if t)
        return text or None
    except Exception as exc:  # noqa: BLE001 - re-classified, not swallowed
        if _is_benign_transcript_error(_yta, exc):
            return None
        obs.log("adapter.transcript_error_unclassified", level="warning",
                platform="youtube", video_id=video_id, error=type(exc).__name__)
        raise TranscriptFetchBlocked(
            f"{type(exc).__name__} while fetching transcript for {video_id}") from exc


def download_item(repo_root: Path, handle: str, video_id: str, title: str,
                  content_type: str | None = None) -> dict:
    out_dir = handle_dir(repo_root, "youtube", handle)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = repo_root / "output" / "brand-intel" / "youtube" / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    url = f"https://www.youtube.com/watch?v={video_id}"
    dest = out_dir / f"{video_id}__{slugify(title)}.md"
    stem = tmp_dir / video_id
    proc = _run_ytdlp(
        ["--skip-download", "--write-info-json",
         "--write-auto-subs", "--write-subs", "--sub-langs", "en.*",
         "--sub-format", "vtt", "--ignore-errors", "--no-warnings",
         "--retries", "5", "--sleep-requests", "2", *_cookie_args(),
         "-o", str(stem) + ".%(ext)s", url],
        label=f"download {video_id}",
    )
    ytdlp_ok = proc.returncode == 0
    if not ytdlp_ok:
        obs.log("adapter.download_tool_failed", level="warning", platform="youtube",
                handle=handle, video_id=video_id, returncode=proc.returncode,
                stderr=proc.stderr.strip()[:200])

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

    transcript_blocked = False
    if not transcript:
        try:
            fb = _fetch_transcript_fallback(video_id)
        except TranscriptFetchBlocked as exc:
            transcript_blocked = True
            obs.log("adapter.transcript_blocked", level="warning", platform="youtube",
                    handle=handle, video_id=video_id, reason=str(exc))
        else:
            if fb:
                transcript, source = fb, "youtube-transcript-api"

    attempts = _prior_transcript_attempts(dest)
    if transcript.strip():
        transcript_status = TRANSCRIPT_PRESENT
    elif transcript_blocked or not ytdlp_ok:
        # Metadata succeeded but no transcript was OBTAINED -- not the same as
        # a video that has none. on_disk_ids() re-offers this item so the next
        # run tries again, bounded by MAX_TRANSCRIPT_ATTEMPTS so a genuinely
        # transcript-less video cannot loop forever (B-12).
        attempts += 1
        transcript_status = (TRANSCRIPT_PENDING if attempts < MAX_TRANSCRIPT_ATTEMPTS
                             else TRANSCRIPT_MISSING)
        obs.log("adapter.transcript_pending_retry", level="warning", platform="youtube",
                handle=handle, video_id=video_id, attempts=attempts, final=transcript_status)
    else:
        transcript_status = TRANSCRIPT_MISSING

    # Metadata comes from the Data API when a key is configured, and falls back
    # to yt-dlp's info.json otherwise. A run counts as successful if EITHER
    # source produced metadata -- when the per-video bot-block is active, the
    # API alone still yields a complete, useful record (minus the transcript),
    # and failing the item would instead retry it forever.
    api_meta = youtube_api.fetch_one(video_id) or {}
    if not api_meta and not info_path.exists():
        # Both sources failed -- clean up and return failure without writing
        # dest, so the video stays eligible for retry on the next run.
        for p in tmp_dir.glob(f"{video_id}*"):
            p.unlink(missing_ok=True)
        return {"id": video_id, "ok": False, "published": None}

    yt_upload_date = info.get("upload_date") or ""
    if yt_upload_date and len(yt_upload_date) == 8:
        yt_upload_date = f"{yt_upload_date[:4]}-{yt_upload_date[4:6]}-{yt_upload_date[6:]}"

    upload_date = api_meta.get("upload_date") or yt_upload_date or ""
    description = api_meta.get("description") or info.get("description") or ""
    channel = api_meta.get("channel") or info.get("uploader") or handle
    duration_s = api_meta.get("duration_s")
    if duration_s is None:
        duration_s = info.get("duration")
    fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")

    meta = {
        "video_id": video_id,
        "url": url,
        "handle": handle,
        "channel": channel,
        # "short" or "video" -- Shorts and long-form are different source
        # material for this project, and the two live on separate channel
        # tabs, so the distinction is recorded rather than inferred.
        "content_type": content_type,
        # Two spellings of one date, deliberately. `published` is the platform
        # contract's field name (CLAUDE.md); `upload_date` is what every file
        # already on disk uses, and discovery_digest's fallback reads it. See
        # the P9 contract note in this plan before removing either.
        "published": upload_date or None,
        "upload_date": upload_date or None,
        "duration_s": duration_s,
        "view_count": api_meta.get("view_count"),
        "like_count": api_meta.get("like_count"),
        "comment_count": api_meta.get("comment_count"),
        # Whether a MANUALLY-UPLOADED caption track exists (contentDetails.
        # caption). Deliberately not named captions_available: auto-generated
        # ASR captions report false here, so False does not mean "no
        # transcript obtainable" -- see discovery_youtube_api's module
        # docstring for the corpus measurement behind that. transcript_status
        # is the field that says whether we actually hold one.
        "manual_captions": api_meta.get("manual_captions"),
        "transcript_status": transcript_status,
        "transcript_attempts": attempts,
        "transcript_source": source,
        "metadata_source": "youtube-data-api-v3" if api_meta else "yt-dlp",
        "fetched_at": fetched_at,
    }
    body = "\n".join([
        f"# {title}", "",
        "## description", "", description.strip() or "(none)", "",
        "## transcript", "", transcript.strip() or "(no transcript available)", "",
    ])
    # Write to a temp path and rename into place (atomic on both POSIX and
    # Windows via Path.replace) rather than writing dest directly -- an
    # interrupted write (process killed mid-download) must never leave a
    # truncated file at a path the next run's on_disk_ids() would treat as
    # already-captured.
    tmp_dest = dest.with_name(dest.name + ".tmp")
    tmp_dest.write_text(artifacts.render_frontmatter(meta, body), encoding="utf-8")
    tmp_dest.replace(dest)

    for p in tmp_dir.glob(f"{video_id}*"):
        p.unlink(missing_ok=True)

    return {"id": video_id, "ok": True, "published": upload_date or None}


def missing_transcript_ids(repo_root: Path, handle: str) -> list[dict]:
    """Videos captured for `handle` whose transcript is still missing.

    Drives the manual-fetch workflow. `manual_captions` is reported for
    triage but is a weak signal: True means a human-uploaded caption track
    exists (fetch it), while False only rules out a manual track, not the
    auto-generated captions most videos actually have.
    """
    directory = handle_dir(repo_root, "youtube", handle)
    if not directory.exists():
        return []
    out: list[dict] = []
    for path in sorted(directory.glob("*__*.md")):
        meta, _ = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
        if meta.get("transcript_status") == "missing":
            out.append({
                "id": meta.get("video_id") or path.name.split("__", 1)[0],
                "url": meta.get("url"),
                "manual_captions": meta.get("manual_captions"),
                "path": path,
            })
    return out
