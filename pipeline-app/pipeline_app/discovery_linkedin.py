"""LinkedIn platform adapters for the discovery engine, backed by Bright
Data's LinkedIn Posts dataset. Two platforms share this module:

  linkedin-profile  -- a person's own posts   (discover_by=profile_url)
  linkedin-company  -- an organization's posts (discover_by=company_url)

A third mode Bright Data advertises -- discover_by=url against
/today/author/<slug>, nominally "Pulse articles" -- is deliberately NOT
implemented. Live testing on 2026-08-07 against both authors in Bright Data's
own documentation snippet returned unrelated third-party posts and zero
articles, twice. See the design doc's "Broken -- Pulse articles" section.

Field names below are from four live jobs on 2026-08-07, not from the
published field list. See docs/superpowers/specs/2026-08-07-linkedin-
brightdata-adapter-design.md.
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

from pipeline_app import artifacts, brightdata_job
from pipeline_app.discovery_paths import handle_dir

# Not a secret -- read off the Bright Data dashboard's generated API snippet
# for the LinkedIn Posts product (2026-08-07). One dataset serves every mode;
# the type/discover_by query params select between them.
DATASET_ID = "gd_lyy3tktm25m4avu764"

KEY_ENV_VAR = "BRIGHTDATA_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "brightdata_api_key.txt"

MAX_ITEMS_PER_RUN = 10           # the default; override with the env var below
MAX_ITEMS_ENV_VAR = "BRIGHTDATA_MAX_ITEMS_LINKEDIN"
POLL_TIMEOUT_S = 300
POLL_INTERVAL_S = 5

TITLE_MAX_CHARS = 60


def max_items() -> int:
    return brightdata_job.config_int(MAX_ITEMS_ENV_VAR, MAX_ITEMS_PER_RUN)


def poll_timeout_s() -> float:
    return brightdata_job.config_int("BRIGHTDATA_POLL_TIMEOUT_LINKEDIN", POLL_TIMEOUT_S)

# Re-exported so `pytest.raises(discovery_linkedin.BrightDataJobFailed)` works
# and callers need not know the exceptions moved.
BrightDataJobTimeout = brightdata_job.BrightDataJobTimeout
BrightDataJobFailed = brightdata_job.BrightDataJobFailed
BrightDataResponseError = brightdata_job.BrightDataResponseError
BrightDataConfigError = brightdata_job.BrightDataConfigError


def _parse_published(raw: str | None) -> str | None:
    """Bright Data's date_posted -> the engine's required YYYY-MM-DD, or None.

    This dataset returns genuine ISO 8601 UTC -- '2026-07-08T14:00:09.491Z'
    (verified 2026-08-07) -- so a 10-character prefix is correct. That is NOT
    true of Bright Data's Instagram product, which returns a US-format local
    timestamp; the two datasets disagree, so neither format may be inferred
    from the other.

    US-format input is deliberately NOT accepted here. Guessing between MM/DD
    and DD/MM would yield silently wrong dates, which is worse than a dropped
    row -- and drops are counted and logged by enumerate_newest_first.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    candidate = raw[:10]
    try:
        _dt.datetime.strptime(candidate, "%Y-%m-%d")
        return candidate
    except ValueError:
        return None


def _normalize_row(row: dict) -> dict | None:
    """One raw Bright Data row -> this adapter's internal shape, or None if
    the row is unusable. The single place to update if the schema changes.

    Two field choices are load-bearing and verified:
    - The body is `post_text`. `original_post_text` and `post_text_html` are
      longer but carry HTML entities and anchor markup.
    - The title comes from `headline` (the post's first line), NOT the `title`
      field, which is SEO text with hashtags and the author name appended.
    """
    post_id = row.get("id")
    if not post_id:
        return None
    published = _parse_published(row.get("date_posted"))
    if published is None:
        return None

    body = (row.get("post_text") or "").strip()
    headline = (row.get("headline") or "").strip()
    first_line = body.split("\n", 1)[0].strip()
    title = headline or first_line or str(post_id)

    raw_date_posted = (row.get("date_posted") or "").strip()

    return {
        "id": str(post_id),
        "title": title[:TITLE_MAX_CHARS],
        "published": published,
        # Full ISO 8601 timestamp, used only as the sort key -- 'published'
        # truncates to the date, so same-day rows would otherwise sort in
        # Bright Data's arbitrary arrival order (verified live: rows are NOT
        # returned newest-first). Lexicographic comparison is correct for
        # this dataset's real ISO 8601 strings (verified live 2026-08-07).
        # raw_date_posted is guaranteed non-empty here (the published check
        # above already required it), but the "or" fallback keeps this key
        # total rather than crashing if that ever stops being true.
        "published_ts": raw_date_posted or f"{published}T00:00:00",
        # Observed values: 'post', 'repost'. Lowercased defensively -- the
        # Instagram product returns display-cased values for the same concept.
        "content_type": (row.get("post_type") or "post").strip().lower(),
        "account_type": (row.get("account_type") or "").strip().lower(),
        "author": (row.get("user_id") or "").strip(),
        "body": body,
        "url": row.get("url") or "",
        "like_count": row.get("num_likes"),
        "comment_count": row.get("num_comments"),
        "hashtags": row.get("hashtags") or [],
    }


class _Mode:
    """One Bright Data product mode, and how this pipeline uses it."""

    def __init__(self, platform: str, discover_by: str, url_template: str,
                 author_filter: bool):
        self.platform = platform
        self.discover_by = discover_by
        self.url_template = url_template
        self.author_filter = author_filter


# Profile discovery returns the person's profile ACTIVITY, not only their
# authorship -- verified live 2026-08-07, where a query for /in/bettywliu
# returned a post authored by mattwilkerson. author_filter=True restores the
# "this directory holds what this account wrote" contract every other adapter
# has. Company results showed no such contamination, and a company's user_id
# is not guaranteed to equal its URL slug, so filtering there would risk
# discarding legitimate rows.
PROFILE = _Mode("linkedin-profile", "profile_url",
                "https://www.linkedin.com/in/{slug}", author_filter=True)
COMPANY = _Mode("linkedin-company", "company_url",
                "https://www.linkedin.com/company/{slug}", author_filter=False)


class LinkedInAdapter:
    """Satisfies discovery_engine.PlatformAdapter for one LinkedIn mode.

    An instance rather than a module because two platforms share this code and
    each needs its own enumerate cache: a person and a company can have the
    same slug, and a cache keyed by handle alone would let one mode's batch
    serve the other's download_item.
    """

    def __init__(self, mode: _Mode):
        self.mode = mode
        self.platform = mode.platform
        # handle -> item_id -> normalized row. Populated by
        # enumerate_newest_first, read by download_item. Calling Bright Data
        # again per item would double-pay for posts already collected.
        self._cache: dict[str, dict[str, dict]] = {}

    # -- credentials and request shape -----------------------------------

    def api_key(self) -> str | None:
        return brightdata_job.read_key(KEY_ENV_VAR, KEY_FILE)

    def preflight(self) -> str | None:
        """None if this platform can run; one operator-facing message if it
        cannot.

        B-21: the per-job guard in _run_collection_job stays as a backstop,
        but it fires once per handle, so one unset token used to produce
        twenty identical error rows and a run that finished
        'completed_with_errors' rather than refusing to start.
        run_discovery_cron calls this once before the handle loop (P8).
        """
        if self.api_key() is None:
            return (f"{self.platform}: Bright Data API key not configured "
                    f"(set {KEY_ENV_VAR} or {KEY_FILE.name}) -- every "
                    f"{self.platform} handle in this run will fail")
        return None

    def profile_url(self, handle: str) -> str:
        return self.mode.url_template.format(slug=handle.lstrip("@").strip())

    def _trigger_job(self, handle: str, key: str) -> str:
        return brightdata_job.trigger(
            brightdata_job.BRIGHTDATA_API_BASE,
            DATASET_ID,
            {
                # A *discovery* job -- "find this account's newest posts".
                # Without type/discover_by, Bright Data reads the input url as
                # a single page to collect, the wrong product mode entirely.
                "type": "discover_new",
                "discover_by": self.mode.discover_by,
                # Server-side per-input record cap: the primary cost control.
                "limit_per_input": max_items(),
                "include_errors": "true",
                "notify": "false",
            },
            [{"url": self.profile_url(handle)}],
            key,
        )

    def _poll_job_status(self, job_id: str, key: str) -> str:
        return brightdata_job.poll_status(brightdata_job.BRIGHTDATA_API_BASE, job_id, key)

    def _fetch_job_results(self, job_id: str, key: str) -> list[dict]:
        return brightdata_job.fetch_results(brightdata_job.BRIGHTDATA_API_BASE, job_id, key)

    def _run_collection_job(self, handle: str) -> list[dict]:
        key = self.api_key()
        if key is None:
            raise RuntimeError(
                "Bright Data API key not configured "
                f"(set {KEY_ENV_VAR} or {KEY_FILE.name})"
            )
        # self.platform, not a shared platform constant: linkedin-profile and
        # linkedin-company must never share a pending entry for the same
        # handle -- the same reason each adapter instance keeps its own
        # enumerate cache (see the class docstring).
        pending_key = f"{self.platform}/{handle}"
        # Free recovery before any billed call: a snapshot an earlier run paid
        # for and abandoned on timeout (B-19). None means "nothing pending",
        # which is the ordinary case.
        resumed = brightdata_job.resume_pending(
            pending_key,
            poll_fn=lambda job_id: self._poll_job_status(job_id, key),
            fetch_fn=lambda job_id: self._fetch_job_results(job_id, key),
        )
        if resumed is not None:
            return resumed
        return brightdata_job.await_results(
            trigger_fn=lambda: self._trigger_job(handle, key),
            poll_fn=lambda job_id: self._poll_job_status(job_id, key),
            fetch_fn=lambda job_id: self._fetch_job_results(job_id, key),
            label=f"for {self.platform}/{handle}",
            poll_timeout_s=poll_timeout_s(),
            poll_interval_s=POLL_INTERVAL_S,
            pending_key=pending_key,
        )

    # -- PlatformAdapter -------------------------------------------------

    def enumerate_newest_first(self, handle: str, keyword_filter: str | None) -> list[dict]:
        # Raises BrightDataJobTimeout/BrightDataJobFailed -- never swallowed
        # here. An empty return must mean "the job completed and there was
        # nothing", nothing else.
        raw_rows = self._run_collection_job(handle)

        normalized = [_normalize_row(r) for r in raw_rows]
        unusable = sum(1 for n in normalized if n is None)
        kept = [n for n in normalized if n is not None]

        foreign = 0
        if self.mode.author_filter:
            wanted = handle.lstrip("@").strip().lower()
            before = len(kept)
            kept = [n for n in kept if n["author"].lower() == wanted]
            foreign = before - len(kept)

        if unusable and foreign:
            print(f"  ! {self.platform}/{handle}: dropped {unusable} unusable row(s), "
                  f"{foreign} row(s) by another author", file=sys.stderr)
        elif unusable:
            print(f"  ! {self.platform}/{handle}: dropped {unusable} unusable row(s)",
                  file=sys.stderr)
        elif foreign:
            print(f"  ! {self.platform}/{handle}: dropped {foreign} row(s) by another author",
                  file=sys.stderr)

        if raw_rows and not kept:
            # This run was billed and produced nothing, but process_handle will
            # record the healthy status 'no_new_content' -- indistinguishable
            # from a quiet day unless it is loud here. The advice depends on
            # *why* nothing survived: an all-unusable batch (e.g. a dead or
            # renamed slug returning error rows with no id, with
            # include_errors=true) points at a bad handle, not at authorship --
            # pointing the operator at the wrong cause wastes their time.
            if unusable and not foreign:
                advice = "check whether this handle/slug is still valid"
            elif foreign and not unusable:
                advice = "check whether this account posts its own content"
            else:
                advice = "check whether this handle is valid and posts its own content"
            print(f"  !! {self.platform}/{handle}: Bright Data returned "
                  f"{len(raw_rows)} row(s) but none survived filtering. This run "
                  f"was billed and captured nothing -- {advice}.", file=sys.stderr)

        # Rows arrive unsorted (verified live); the engine's early-stop dedup
        # assumes newest-first. Sort on the full timestamp, not the
        # date-truncated 'published': Python's sort is stable, so same-day
        # rows sorted on 'published' alone would keep Bright Data's arbitrary
        # arrival order, which can put a genuinely newer post behind ones
        # already on disk and trip the early-stop dedup before reaching it.
        # Cap AFTER filtering so it bounds retained items.
        kept.sort(key=lambda n: n["published_ts"], reverse=True)

        # B-02 (S1): saturation must be computed on the PRE-cap count, right
        # here before the client-side slice below discards everything past the
        # cap -- once that slice runs, how many rows Bright Data actually
        # returned is gone. None of the four Bright Data platforms support
        # backfill, so a batch that filled the cap is a data-loss event this
        # run made, not a quiet-account day, and process_handle would
        # otherwise report it as the healthy status 'ok'.
        cap = max_items()
        # Measured against raw_rows, NOT kept: kept has already dropped
        # unusable and (in profile mode) foreign-author rows, so a batch that
        # filled the cap but included one such row would otherwise show
        # len(kept) == cap - 1 and never trip the alarm, even though the same
        # cap-truncation data loss occurred (plan correction, T17 task
        # review, 2026-08-16).
        if brightdata_job.is_saturated(len(raw_rows), cap=cap):
            oldest = min((n["published_ts"] for n in kept), default=None)
            brightdata_job.record_diagnostic(
                kind="adapter.batch_saturated", severity="error",
                source="discovery_linkedin",
                message=(f"{self.platform}/{handle}: the batch filled the cap of "
                         f"{cap}. Posts older than {oldest} in this interval were "
                         f"dropped and there is no backfill path for this platform. "
                         f"Raise {MAX_ITEMS_ENV_VAR} (this increases Bright Data "
                         f"spend per run) or shorten the run interval."),
                detail={"platform": self.platform, "handle": handle, "cap": cap,
                        "collected": len(kept), "raw_count": len(raw_rows),
                        "oldest_kept": oldest})
            print(f"  !! {self.platform}/{handle}: batch filled the cap of {cap}; "
                  f"older posts in this interval are unrecoverable", file=sys.stderr)

        kept = kept[:cap]

        # Overwrite, not merge: a fresh successful enumerate replaces whatever
        # this handle held, so download_item never reads a stale id.
        self._cache[handle] = {n["id"]: n for n in kept}

        items = kept
        if keyword_filter:
            items = [i for i in items if keyword_filter.lower() in i["body"].lower()]
        return [
            {"id": i["id"], "title": i["title"], "published": i["published"],
             "content_type": i["content_type"]}
            for i in items
        ]

    def on_disk_ids(self, repo_root: Path, handle: str) -> set[str]:
        directory = handle_dir(repo_root, self.platform, handle)
        if not directory.exists():
            return set()
        return {p.stem for p in directory.glob("*.md")}

    def peek_upload_date(self, item_id: str) -> str | None:
        # Dead code by design: enumerate_newest_first only ever returns items
        # carrying a normalized 'published' date, so process_handle's
        # `item.get("published") or adapter.peek_upload_date(...)` never falls
        # through -- same as discovery_bluesky/discovery_instagram.
        return None

    def download_item(self, repo_root: Path, handle: str, item_id: str, title: str,
                      content_type: str | None = None) -> dict:
        # A missing handle or item_id is a programming error: every engine call
        # path runs enumerate_newest_first for this handle on this instance
        # first. KeyError propagates to run_discovery's per-handle error path
        # rather than being caught here, so it surfaces as a normal 'error'
        # instead of failing silently.
        cached = self._cache[handle][item_id]

        out_dir = handle_dir(repo_root, self.platform, handle)
        out_dir.mkdir(parents=True, exist_ok=True)
        fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        meta = {
            "post_id": cached["id"],
            "url": cached["url"],
            "handle": handle,
            # Recorded even in profile mode, where the filter guarantees it
            # matches: it is what makes a filtering regression detectable
            # after the fact, and it is independently meaningful for companies.
            "author": cached["author"],
            "account_type": cached["account_type"],
            "content_type": cached["content_type"],
            "published": cached["published"],
            "like_count": cached["like_count"],
            "comment_count": cached["comment_count"],
            "hashtags": cached["hashtags"],
            "fetched_at": fetched_at,
        }
        body = cached["body"] or "(empty)"

        dest = out_dir / f"{item_id}.md"
        # Write-temp-then-rename, same as every other adapter: an interrupted
        # write must never leave a truncated file at a path on_disk_ids()
        # would treat as already-captured.
        tmp_dest = dest.with_name(dest.name + ".tmp")
        tmp_dest.write_text(artifacts.render_frontmatter(meta, body), encoding="utf-8")
        tmp_dest.replace(dest)
        return {"id": item_id, "ok": True, "published": cached["published"]}


def profile_adapter() -> LinkedInAdapter:
    return LinkedInAdapter(PROFILE)


def company_adapter() -> LinkedInAdapter:
    return LinkedInAdapter(COMPANY)
