"""Backfill existing YouTube corpus .md files to YAML frontmatter.

Converts the original '## metadata' list format into the frontmatter block
download_item now writes, and enriches each file with Data API fields the
original scrape never captured (view/like/comment counts, manual_captions)
plus the transcript_status flag.

Existing transcripts and descriptions are carried across verbatim -- this
script never re-fetches transcript text and never overwrites one it cannot
re-derive. Files already in frontmatter format are re-enriched in place.

Dry run by default; pass --apply to write.

    python scripts/backfill_youtube_frontmatter.py
    python scripts/backfill_youtube_frontmatter.py --apply
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline_app import artifacts  # noqa: E402
from pipeline_app import discovery_youtube_api as youtube_api  # noqa: E402
from pipeline_app import obs  # noqa: E402

CORPUS_ROOT = Path(__file__).resolve().parents[2] / "output" / "brand-intel" / "youtube"

_SECTION_RE = re.compile(r"^##\s+(\w+)\s*$", re.MULTILINE)
_OLD_META_RE = re.compile(r"^-\s*([a-z_]+):\s*(.*)$", re.MULTILINE)
_PLACEHOLDER_TRANSCRIPT = "(no transcript available)"
_PLACEHOLDER_DESCRIPTION = "(none)"


def split_sections(text: str) -> dict[str, str]:
    """Split a corpus .md body into its '## <name>' sections."""
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(text))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[match.group(1).lower()] = text[match.end():end].strip()
    return sections


def parse_existing(path: Path) -> dict:
    """Read a corpus file in EITHER format into a common shape."""
    raw = path.read_text(encoding="utf-8")
    meta, body = artifacts.parse_frontmatter(raw)

    title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem.split("__", 1)[-1]

    sections = split_sections(body)
    description = sections.get("description", "")
    transcript = sections.get("transcript", "")
    if transcript == _PLACEHOLDER_TRANSCRIPT:
        transcript = ""
    if description == _PLACEHOLDER_DESCRIPTION:
        description = ""

    if not meta:
        # Old format: metadata lived in a '## metadata' section as a list.
        meta = {k: v.strip() for k, v in _OLD_META_RE.findall(sections.get("metadata", ""))}

    return {
        "path": path,
        "video_id": meta.get("video_id") or path.name.split("__", 1)[0],
        "title": title,
        "handle": meta.get("handle") or f"@{path.parent.name}",
        "channel": meta.get("channel") or "",
        "upload_date": meta.get("upload_date") or "",
        "duration_s": meta.get("duration_s") or None,
        "transcript_source": meta.get("transcript_source") or "none",
        "fetched_at": meta.get("fetched_at") or "",
        "description": description,
        "transcript": transcript,
    }


def _coerce_int(value) -> int | None:
    if value in (None, "", "None"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_meta(existing: dict, api_record: dict | None) -> dict:
    api_record = api_record or {}
    has_transcript = bool(existing["transcript"].strip())
    video_id = existing["video_id"]

    duration = api_record.get("duration_s")
    if duration is None:
        duration = _coerce_int(existing["duration_s"])

    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "handle": existing["handle"],
        "channel": api_record.get("channel") or existing["channel"],
        "upload_date": api_record.get("upload_date") or existing["upload_date"] or None,
        "duration_s": duration,
        "view_count": api_record.get("view_count"),
        "like_count": api_record.get("like_count"),
        "comment_count": api_record.get("comment_count"),
        "manual_captions": api_record.get("manual_captions"),
        "transcript_status": "present" if has_transcript else "missing",
        # A transcript we already hold keeps its original provenance; only a
        # genuinely absent one is downgraded to "none".
        "transcript_source": existing["transcript_source"] if has_transcript else "none",
        "metadata_source": "youtube-data-api-v3" if api_record else (
            "yt-dlp" if existing["upload_date"] else "none"),
        "fetched_at": existing["fetched_at"] or None,
    }


def render(existing: dict, meta: dict) -> str:
    body = "\n".join([
        f"# {existing['title']}", "",
        "## description", "", existing["description"].strip() or _PLACEHOLDER_DESCRIPTION, "",
        "## transcript", "", existing["transcript"].strip() or _PLACEHOLDER_TRANSCRIPT, "",
    ])
    return artifacts.render_frontmatter(meta, body)


def collect(corpus_root: Path) -> list[dict]:
    return [parse_existing(p) for p in sorted(corpus_root.glob("*/*__*.md"))]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="actually rewrite the files (default: dry run)")
    ap.add_argument("--corpus-root", type=Path, default=CORPUS_ROOT)
    ap.add_argument("--no-api", action="store_true",
                    help="skip Data API enrichment; only reformat what is already on disk")
    args = ap.parse_args(argv)

    if not args.no_api and youtube_api.api_key() is None:
        obs.log("backfill.preflight_failed", level="error", reason="no_api_key")
        print(
            "! refusing to run: Data API enrichment was requested but no key is "
            f"configured ({youtube_api.KEY_ENV_VAR} env var or "
            f"{youtube_api.KEY_FILE.name}).\n"
            "  Without a key every record would be rewritten with null view/like/"
            "comment counts and a downgraded metadata_source, over a git-ignored "
            "corpus with no recovery path.\n"
            "  Set the key, or pass --no-api to reformat on-disk data only.",
            file=sys.stderr,
        )
        return 2

    if not args.corpus_root.exists():
        print(f"! corpus root not found: {args.corpus_root}", file=sys.stderr)
        return 1

    files = collect(args.corpus_root)
    if not files:
        print(f"no corpus files under {args.corpus_root}")
        return 0

    api_records: dict[str, dict] = {}
    if not args.no_api:
        ids = [f["video_id"] for f in files]
        calls = (len(set(ids)) + youtube_api.MAX_IDS_PER_CALL - 1) // youtube_api.MAX_IDS_PER_CALL
        print(f"querying Data API for {len(set(ids))} videos (~{calls} quota units)...")
        api_records = youtube_api.fetch_metadata(ids)
        print(f"  got metadata for {len(api_records)}/{len(set(ids))}")

    missing = enriched = 0
    for existing in files:
        record = api_records.get(existing["video_id"])
        meta = build_meta(existing, record)
        if record:
            enriched += 1
        if meta["transcript_status"] == "missing":
            missing += 1
        if args.apply:
            path = existing["path"]
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(render(existing, meta), encoding="utf-8")
            tmp.replace(path)

    verb = "rewrote" if args.apply else "would rewrite"
    print(f"\n{verb} {len(files)} files")
    print(f"  enriched from Data API : {enriched}")
    print(f"  transcript missing     : {missing}")
    print(f"  transcript present     : {len(files) - missing}")
    if not args.apply:
        print("\nDry run -- re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
