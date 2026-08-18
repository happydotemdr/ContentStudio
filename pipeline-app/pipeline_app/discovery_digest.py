"""Reads a finished discovery run's on-disk output into normalized items for
the daily email, and picks the one item the email spotlights.

Filesystem only -- no network, no DB, no LLM. Deliberately has no dependency
on discovery_engine.py, same as discovery_notify.py.

THE PLATFORM CONTRACT. A discovery adapter's download_item must write YAML
frontmatter containing `fetched_at`, with the post's text as the markdown body.
An adapter that does this appears in the daily email -- inventory entry, link,
title, and spotlight eligibility -- with no change to any email-side module.

`fetched_at` is the one MANDATORY field: it is the watermark, and an item
without it is excluded from the run entirely. `url` is strongly expected but
not required -- an item missing it is still collected and still rendered, just
without a link, and collect_new_items warns to stderr. `like_count`,
`comment_count`, `view_count`, and `published` are optional; each is omitted
from the render when absent.
`fetched_at` must be an aware-UTC isoformat(timespec="seconds") STRING.

`published` is optional. `upload_date` is accepted as its ONE alias, for
YouTube's yt-dlp-shaped frontmatter. No third name is read: an adapter writing
`date_published` or `posted_at` gets published=None, which renders undated and
sorts last, so collect() reports it as a warning rather than letting it pass
for a post that genuinely has no date.

One known exception: download_brandintel.py, the manual toolkit script at repo
root, does not honor this contract and is deliberately left unmodified.
Nothing it writes falls inside a discovery run's watermark, so it never
reaches the email.

See docs/superpowers/specs/2026-08-08-morning-email-social-expansion-design.md.
"""
from __future__ import annotations

import re
import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path

from pipeline_app import artifacts
from pipeline_app.discovery_paths import handle_dir

# Written by the adapters when they have nothing. Treated as empty everywhere:
# an excerpt reading "(no transcript available)" is worse than no excerpt.
PLACEHOLDERS = frozenset({"(none)", "(empty)", "(no transcript available)"})

TITLE_MAX_CHARS = 90

# Seconds of slack on the mtime pre-filter, absorbing filesystem timestamp
# granularity and clock skew between the run's recorded start and the write.
MTIME_SLACK_S = 300

# The publish-date field and its one accepted alias. Nothing else is read; a
# name outside this tuple is reported by collect() (B-98).
PUBLISHED_FIELDS = ("published", "upload_date")

# Preference order when a body is section-structured (YouTube's is: an H1, then
# "## description", then "## transcript" -- discovery_youtube.py:289-293).
_SECTION_PREFERENCE = ("## transcript", "## description")

_H1_PREFIX = "# "


def _clean(text: str) -> str:
    """Stripped text, or "" if it is one of the adapters' placeholder strings."""
    stripped = text.strip()
    return "" if stripped in PLACEHOLDERS else stripped


def _truncate_at_word(text: str, maxlen: int) -> str:
    if len(text) <= maxlen:
        return text
    cut = text[:maxlen]
    space = cut.rfind(" ")
    return (cut[:space] if space > 0 else cut).rstrip()


def derive_title(body: str, fallback: str) -> str:
    """The item's title: a leading markdown H1 if there is one, else the first
    non-empty line truncated.

    The H1 test requires "# " -- hash followed by a SPACE -- and that is
    load-bearing. Social posts routinely open with a hashtag ("#MondayMotivation
    ..."), and a bare startswith("#") would classify that as a heading, then
    strip the line as one and lose the post's first sentence.
    """
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(_H1_PREFIX):
            heading = stripped[len(_H1_PREFIX):].strip()
            return _truncate_at_word(heading, TITLE_MAX_CHARS) or fallback
        return _truncate_at_word(stripped, TITLE_MAX_CHARS)
    return fallback


def _section_text(lines: list[str], heading: str) -> str:
    """The text under `heading` up to the next "## " heading, or ""."""
    for i, line in enumerate(lines):
        if line.strip().lower() != heading:
            continue
        collected: list[str] = []
        for following in lines[i + 1:]:
            if following.strip().lower().startswith("## "):
                break
            collected.append(following)
        return _clean("\n".join(collected))
    return ""


def extract_primary_text(body: str) -> str:
    """The item's primary text -- what the excerpt and the comment drafter read.

    Structural rather than per-platform, so a future adapter writing the same
    sections inherits the behavior: prefer a transcript section, then a
    description section, then the whole remainder.
    """
    lines = body.splitlines()

    # Drop a leading H1 -- and only when it is a real "# " heading, i.e. exactly
    # when derive_title consumed it as the title.
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is not None and lines[first].strip().startswith(_H1_PREFIX):
        lines = lines[first + 1:]

    for heading in _SECTION_PREFERENCE:
        section = _section_text(lines, heading)
        if section:
            return section

    # A sectioned body whose sections were all placeholders has no primary text.
    # Falling through would return the section headers themselves as content.
    if any(line.strip().lower().startswith("## ") for line in lines):
        return ""

    return _clean("\n".join(lines))


def published_rank(published: str | None) -> tuple[int, int]:
    """Sort key giving newest-first under an ASCENDING sort, missing last.

    Returns (missing_flag, negated_yyyymmdd). Negating an int is what lets one
    ascending sorted() key mix descending dates with ascending tie-breaks.
    """
    if not isinstance(published, str):
        return (1, 0)
    digits = re.sub(r"\D", "", published)[:8]
    if len(digits) != 8:
        return (1, 0)
    return (0, -int(digits))


def _as_optional_str(value) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if value is None:
        return None
    # A YAML date/datetime, or an int. str() keeps the item usable rather than
    # dropping it over a formatting detail the adapter got slightly wrong.
    return str(value).strip() or None


def _as_optional_int(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _published(meta: dict) -> str | None:
    """The publish date from meta, reading only the accepted field names.

    Reads PUBLISHED_FIELDS in order; returns the first non-None value or None.
    """
    for field in PUBLISHED_FIELDS:
        value = _as_optional_str(meta.get(field))
        if value is not None:
            return value
    return None


def _mtime_cutoff(run_started_at: str) -> float | None:
    """Epoch seconds below which a file cannot belong to this run, or None to
    disable the pre-filter.

    Returning None on an unparseable run timestamp is a deliberate fail-open:
    the pre-filter is an optimization, and a bad parse must never silently hide
    every item. The frontmatter watermark below is the authority regardless.
    """
    try:
        started = _dt.datetime.fromisoformat(run_started_at)
    except (TypeError, ValueError):
        return None
    return started.timestamp() - MTIME_SLACK_S


def _build_item(handle_row, path: Path, meta: dict, body: str) -> dict:
    return {
        "platform": handle_row["platform"],
        "handle": handle_row["handle"],
        "display_name": handle_row["display_name"] or handle_row["handle"],
        # For YouTube this is "{video_id}__{slug}", not the bare id. It is used
        # only as a stable identity and a final sort tie-break, never parsed.
        "item_id": path.stem,
        "title": derive_title(body, path.stem),
        "url": _as_optional_str(meta.get("url")),
        "published": _published(meta),
        "views": _as_optional_int(meta.get("view_count")),
        "likes": _as_optional_int(meta.get("like_count")),
        "comments": _as_optional_int(meta.get("comment_count")),
        "body": extract_primary_text(body),
    }


# Why an item was dropped. Every one of these is a FAULT: a file the adapter
# wrote that this reader could not honour. Two other `continue` paths -- the
# mtime pre-filter and a fetched_at older than the run -- are the watermark
# working as designed and are deliberately NOT reported (B-99).
SKIP_STAT_FAILED = "stat_failed"
SKIP_UNREADABLE = "unreadable"
SKIP_BAD_FRONTMATTER = "bad_frontmatter"
SKIP_MISSING_FETCHED_AT = "missing_fetched_at"

# Not a skip: the item is still collected, but something about it is off.
SKIP_NO_PUBLISHED_FIELD = "no_published_field"
SKIP_NO_URL = "no_url"


@dataclass(frozen=True)
class Collected:
    """What one handle's directory yielded, INCLUDING what it failed to yield.

    Returning the failures is the whole point: the previous shape was a bare
    list, so an adapter that wrote 30 unparseable files and an adapter that
    wrote nothing were the same value (B-99).
    """
    items: list[dict] = field(default_factory=list)
    skips: list[tuple[str, str]] = field(default_factory=list)      # (reason, filename)
    warnings: list[tuple[str, str]] = field(default_factory=list)   # item kept, but flawed


def collect(repo_root: Path, handle_row, run_started_at: str) -> Collected:
    """Every item this handle captured during the run identified by
    run_started_at, newest-agnostic (the caller orders), plus everything the
    read dropped or flagged along the way.

    Selection is a WATERMARK -- frontmatter fetched_at >= run_started_at -- not
    a top-N. It self-corrects when the DB's items_downloaded under-reports,
    which is what happens when process_handle raises after some downloads
    already succeeded and discovery_engine.py:347 records error/0 for a handle
    that has files on disk.
    """
    directory = handle_dir(repo_root, handle_row["platform"], handle_row["handle"])
    if not directory.exists():
        return Collected()

    cutoff = _mtime_cutoff(run_started_at)
    out = Collected()
    # glob("*.md") is non-recursive and does not match the ".md.tmp"
    # write-temps. YouTube's _tmp/ scratch directory is a SIBLING of the handle
    # directories (output/brand-intel/youtube/_tmp, discovery_youtube.py:205),
    # so it is never reached either way.
    for path in sorted(directory.glob("*.md")):
        if cutoff is not None:
            try:
                if path.stat().st_mtime < cutoff:
                    continue        # outside the run: expected, not a skip
            except OSError:
                out.skips.append((SKIP_STAT_FAILED, path.name))
                continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            out.skips.append((SKIP_UNREADABLE, path.name))
            continue
        try:
            meta, body = artifacts.parse_frontmatter(text)
        except artifacts.MalformedArtifactError:
            out.skips.append((SKIP_BAD_FRONTMATTER, path.name))
            continue
        fetched_at = meta.get("fetched_at")
        # Non-str includes an unquoted YAML timestamp, which parses to a
        # datetime and would raise TypeError on the comparison below.
        if not isinstance(fetched_at, str):
            out.skips.append((SKIP_MISSING_FETCHED_AT, path.name))
            continue
        if fetched_at < run_started_at:
            continue                # outside the run: expected, not a skip
        item = _build_item(handle_row, path, meta, body)
        if item["url"] is None:
            out.warnings.append((SKIP_NO_URL, path.name))
        if item["published"] is None and any(k in meta for k in
                                             ("date_published", "posted_at", "created_at", "date")):
            out.warnings.append((SKIP_NO_PUBLISHED_FIELD, path.name))
        out.items.append(item)
    return out


def collect_new_items(repo_root: Path, handle_row, run_started_at: str) -> list[dict]:
    """collect().items. Kept because the item list is what most callers want;
    anything that needs to know what was DROPPED must call collect()."""
    return collect(repo_root, handle_row, run_started_at).items


# Both LinkedIn modes rank equally against each other and both outrank
# everything else. This gate is absolute, by product decision: a LinkedIn post
# with 3 likes wins over a YouTube video with 40,000.
LINKEDIN_PLATFORMS = ("linkedin-profile", "linkedin-company")


def _interactions(item: dict) -> int:
    """The cross-platform ranking metric: likes + comments.

    Deliberately NOT views. Only YouTube records a view count, so a literal
    cross-platform "most viewed" would need an invented exchange rate between a
    YouTube view and a LinkedIn like. Likes+comments is the only metric YouTube,
    Instagram, and LinkedIn all actually record, so it is the honest common
    currency. Views still break ties, and are still shown in the email.
    """
    return (item["likes"] or 0) + (item["comments"] or 0)


def _metrics_reported(item: dict) -> int:
    """0 when the source reported at least one engagement number, 1 when it
    reported none.

    An item with no like_count and no comment_count scores the same 0
    interactions as an item that genuinely got none, and the old key then
    resolved that tie on `platform` ASCENDING -- handing every all-zero day to
    bluesky, the one platform whose engagement is never measured (B-97). This
    is per-item, not a platform allowlist, so a future adapter that starts
    reporting metrics is picked up with no change here.
    """
    return 0 if (item["likes"] is not None or item["comments"] is not None) else 1


def _spotlight_sort_key(item: dict):
    # Ascending sort; negation carries the descending terms. (platform, handle,
    # item_id) is a filesystem path, so the key is TOTAL -- no two items can
    # collide, which is what makes selection reproducible. handle is required:
    # item_id is a file stem, and two handles on one platform can share one.
    return (
        -_interactions(item),
        -(item["views"] or 0),
        published_rank(item["published"]),
        _metrics_reported(item),
        item["platform"],
        item["handle"],
        item["item_id"],
    )


SPOTLIGHT_RULE_LINKEDIN = "linkedin-priority"
SPOTLIGHT_RULE_ENGAGEMENT = "top-engagement"


def select_spotlight_with_rule(items: list[dict]) -> tuple[dict | None, str | None]:
    """The one item the email features, and the rule that chose it.

    The rule is returned rather than re-derived downstream so the email can
    state the LinkedIn gate instead of leaving a reader to assume the pick is
    the day's most-engaged post (B-96).
    """
    # An item with no primary text gives the drafter nothing to read, so a
    # comment drafted from it would be drafted from the title alone.
    candidates = [i for i in items if i["body"]]
    if not candidates:
        return None, None
    linkedin = [i for i in candidates if i["platform"] in LINKEDIN_PLATFORMS]
    if linkedin:
        return min(linkedin, key=_spotlight_sort_key), SPOTLIGHT_RULE_LINKEDIN
    return min(candidates, key=_spotlight_sort_key), SPOTLIGHT_RULE_ENGAGEMENT


def select_spotlight(items: list[dict]) -> dict | None:
    """The one item the email features, or None."""
    return select_spotlight_with_rule(items)[0]
