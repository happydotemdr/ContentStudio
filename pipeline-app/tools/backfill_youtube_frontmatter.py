"""Backfill existing YouTube corpus .md files to YAML frontmatter.

Converts the original '## metadata' list format into the frontmatter block
download_item now writes, and enriches each file with Data API fields the
original scrape never captured (view/like/comment counts, manual_captions)
plus the transcript_status flag.

Existing transcripts and descriptions are carried across verbatim -- this
script never re-fetches transcript text and never overwrites one it cannot
re-derive. Files already in frontmatter format are re-enriched in place.

Dry run by default; pass --apply to write.

    python tools/backfill_youtube_frontmatter.py
    python tools/backfill_youtube_frontmatter.py --apply
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
    meta_parsed = bool(meta)

    inferred: list[str] = []
    video_id = meta.get("video_id")
    if not video_id:
        video_id = path.name.split("__", 1)[0]
        inferred.append("video_id")
    handle = meta.get("handle")
    if not handle:
        handle = f"@{path.parent.name}"
        inferred.append("handle")
    for field_name in ("channel", "upload_date", "fetched_at"):
        if not meta.get(field_name):
            inferred.append(field_name)

    return {
        "path": path,
        "video_id": video_id,
        "title": title,
        "handle": handle,
        "channel": meta.get("channel") or "",
        "upload_date": meta.get("upload_date") or "",
        "duration_s": meta.get("duration_s") or None,
        "transcript_source": meta.get("transcript_source") or "none",
        "fetched_at": meta.get("fetched_at") or "",
        "description": description,
        "transcript": transcript,
        "metadata_source": meta.get("metadata_source") or "",
        "view_count": meta.get("view_count"),
        "like_count": meta.get("like_count"),
        "comment_count": meta.get("comment_count"),
        "manual_captions": meta.get("manual_captions"),
        "meta_parsed": meta_parsed,
        "inferred_fields": inferred,
    }


def _coerce_int(value) -> int | None:
    if value in (None, "", "None"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


_SOURCE_RANK = {"": 0, "none": 0, "yt-dlp": 1, "youtube-data-api-v3": 2}


def _keep(api_value, existing_value):
    """API wins when it says anything; otherwise keep what the file already
    held. Never replace a real value with None (D-04)."""
    return existing_value if api_value is None else api_value


def build_meta(existing: dict, api_record: dict | None) -> dict:
    api_record = api_record or {}
    has_transcript = bool(existing["transcript"].strip())
    video_id = existing["video_id"]

    duration = api_record.get("duration_s")
    if duration is None:
        duration = _coerce_int(existing["duration_s"])

    derived_source = "youtube-data-api-v3" if api_record else (
        "yt-dlp" if existing["upload_date"] else "none")
    existing_source = existing["metadata_source"]
    metadata_source = max(
        (derived_source, existing_source),
        key=lambda s: _SOURCE_RANK.get(s, 0),
    )

    out = {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "handle": existing["handle"],
        "channel": api_record.get("channel") or existing["channel"],
        "upload_date": api_record.get("upload_date") or existing["upload_date"] or None,
        "duration_s": duration,
        "view_count": _keep(api_record.get("view_count"), existing["view_count"]),
        "like_count": _keep(api_record.get("like_count"), existing["like_count"]),
        "comment_count": _keep(api_record.get("comment_count"), existing["comment_count"]),
        "manual_captions": _keep(api_record.get("manual_captions"), existing["manual_captions"]),
        "transcript_status": "present" if has_transcript else "missing",
        # A transcript we already hold keeps its original provenance; only a
        # genuinely absent one is downgraded to "none".
        "transcript_source": existing["transcript_source"] if has_transcript else "none",
        "metadata_source": metadata_source,
        "fetched_at": existing["fetched_at"] or None,
    }
    # A plain old-format file with an empty field is a read absence, not an
    # inference -- only surface metadata_inferred when the block itself
    # failed to parse (D-05).
    if not existing["meta_parsed"] and existing["inferred_fields"]:
        out["metadata_inferred"] = sorted(existing["inferred_fields"])
    return out


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
    ap.add_argument("--rewrite-unparsed", action="store_true",
                    help="also rewrite files whose metadata block did not parse; "
                         "their inferred fields are recorded in metadata_inferred")
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
    unparsed = [f for f in files if not f["meta_parsed"]]

    api_records: dict[str, dict] = {}
    if not args.no_api:
        ids = [f["video_id"] for f in files]
        calls = (len(set(ids)) + youtube_api.MAX_IDS_PER_CALL - 1) // youtube_api.MAX_IDS_PER_CALL
        print(f"querying Data API for {len(set(ids))} videos (~{calls} quota units)...")
        api_records = youtube_api.fetch_metadata(ids)
        print(f"  got metadata for {len(api_records)}/{len(set(ids))}")
        unique = len(set(ids))
        if unique and not api_records:
            obs.log("backfill.enrichment_total_miss", level="error", requested=unique)
            print(
                f"! refusing to write: Data API enrichment returned 0 of {unique} "
                "records. A key is configured, so this is an exhausted quota, a "
                "revoked key, or a network failure -- not an empty result.\n"
                "  Nothing has been written. Re-run when the API is reachable, or "
                "pass --no-api to reformat on-disk data only.",
                file=sys.stderr,
            )
            return 2

    missing = enriched = 0
    failed: list[tuple[Path, str]] = []
    for existing in files:
        if not existing["meta_parsed"] and not args.rewrite_unparsed:
            continue                        # counted below, never written
        record = api_records.get(existing["video_id"])
        meta = build_meta(existing, record)
        if record:
            enriched += 1
        if meta["transcript_status"] == "missing":
            missing += 1
        if args.apply:
            path = existing["path"]
            tmp = path.with_name(path.name + ".tmp")
            try:
                tmp.write_text(render(existing, meta), encoding="utf-8")
                tmp.replace(path)
            except Exception as exc:  # noqa: BLE001 -- one bad file must not
                # abandon the corpus half-converted; the counter and the exit
                # code are what make the partial state visible (D-04).
                failed.append((path, f"{type(exc).__name__}: {exc}"))
                tmp.unlink(missing_ok=True)
                obs.log("backfill.file_write_failed", level="error",
                        path=str(path), error=str(exc))
                print(f"  !! {path.name}: {exc}", file=sys.stderr)

    verb = "rewrote" if args.apply else "would rewrite"
    print(f"\n{verb} {len(files)} files")
    print(f"  enriched from Data API : {enriched}")
    print(f"  transcript missing     : {missing}")
    print(f"  transcript present     : {len(files) - missing}")
    print(f"  failed to write        : {len(failed)}")
    print(f"  metadata did not parse : {len(unparsed)}"
          + ("" if args.rewrite_unparsed else "  (skipped; pass --rewrite-unparsed to convert)"))
    if failed:
        for path, why in failed:
            print(f"    - {path}: {why}")
    if not args.apply:
        print("\nDry run -- re-run with --apply to write.")
    unparsed_skipped = 0 if args.rewrite_unparsed else len(unparsed)
    enrichment_incomplete = (not args.no_api) and enriched < len(files)
    if failed or enrichment_incomplete or unparsed_skipped:      # unparsed: T18
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
