"""Post-run email notification for the discovery pipeline. Deliberately has
no dependency on discovery_engine.py -- it reads only what a finished run
already persisted (DB rows via db.py, files via discovery_digest.py) and is
invoked by run_discovery_cron.py after run_discovery() returns.

This module does NOT catch. tests/test_discovery_notify.py documents that
contract: the cron call site (run_discovery_cron.py:100) is the single catch
point, and notify() adding its own would be a second, redundant failure
boundary. The collaborators carry the burden instead -- comment_draft never
raises, and per-item parse failures are contained inside discovery_digest.collect
(never raised) -- build_summary now also surfaces them, as "skips"/"warnings" in
the returned summary and as events/log lines, rather than only counting them.

notify() now fans out per brand internally (one select_spotlight call per
entry in email_render.BRAND_SECTION_ORDER, and one draft_comments call per
DISTINCT spotlighted item -- a post spotlighted in two sections is drafted
once and reused), but that fan-out is still inside notify()'s own no-catch
contract: any of those calls raising propagates exactly like the
single-brand path did.

See docs/superpowers/specs/2026-08-08-morning-email-social-expansion-design.md.
"""
from __future__ import annotations

import datetime as _dt
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from pipeline_app import comment_draft
from pipeline_app import db as db_mod
from pipeline_app import discovery_digest
from pipeline_app import email_render
from pipeline_app import obs

RESEND_API_URL = "https://api.resend.com/emails"
KEY_ENV_VAR = "RESEND_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "resend_api_key.txt"

TO_ENV_VAR = "RESEND_TO_ADDRESS"
FROM_ENV_VAR = "RESEND_FROM_ADDRESS"
DEFAULT_RECIPIENT = "brian@happydotemdr.com"
# Resend's shared sandbox sender. It delivers ONLY to the address that owns the
# Resend account, so it silently 4xx's the moment the recipient diverges.
SANDBOX_SENDER = "onboarding@resend.dev"

REQUEST_TIMEOUT_S = 15

KNOWN_HEALTHY_STATUSES = ("ok", "no_new_content")

ERROR_REASON_MAX_CHARS = 160


def _truncate(text: str, maxlen: int) -> str:
    return text if len(text) <= maxlen else text[:maxlen].rstrip()


def _first_line(message) -> str:
    """The first line of an error message, truncated -- what actually broke,
    not the full traceback-shaped string discovery_engine records (B-112)."""
    if not isinstance(message, str):
        return "no reason recorded"
    line = message.strip().splitlines()[0] if message.strip() else ""
    return _truncate(line, ERROR_REASON_MAX_CHARS) or "no reason recorded"


def api_key() -> str | None:
    """The Resend API key, or None if not configured. Same lookup order as
    discovery_youtube_api.api_key(): env var first, then a gitignored file."""
    env_key = os.environ.get(KEY_ENV_VAR, "").strip()
    if env_key:
        return env_key
    if KEY_FILE.exists():
        file_key = KEY_FILE.read_text(encoding="utf-8").strip()
        if file_key:
            return file_key
    return None


def recipient() -> str:
    """Where the digest goes. Read per call, exactly like sender() and
    api_key(): the destination had no override at all while the sender did,
    which made pointing the digest at a test inbox a code edit (B-106)."""
    return os.environ.get(TO_ENV_VAR, "").strip() or DEFAULT_RECIPIENT


def sender() -> str:
    return os.environ.get(FROM_ENV_VAR, "").strip() or SANDBOX_SENDER


def send_email(subject: str, text: str, html: str | None = None) -> bool:
    """POST one email via Resend's HTTP API. Never raises -- returns False on
    any failure (no key configured, network error, non-2xx response) so a
    caller can log and move on rather than letting a notification failure
    propagate as an exception."""
    key = api_key()
    if not key:
        print("discovery_notify: no RESEND_API_KEY configured, skipping send", file=sys.stderr)
        return False
    from_address = sender()
    if from_address == SANDBOX_SENDER:
        obs.log("email.sandbox_sender", level="warning", sender=SANDBOX_SENDER,
                recipient=recipient())
        print(f"discovery_notify: sending from the shared sandbox address "
              f"{SANDBOX_SENDER}; set {FROM_ENV_VAR} once a domain is verified",
              file=sys.stderr)
    payload = {"from": from_address, "to": [recipient()], "subject": subject, "text": text}
    if html:
        payload["html"] = html
    try:
        response = requests.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
            timeout=REQUEST_TIMEOUT_S,
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as exc:
        print(f"discovery_notify: send_email failed: {exc}", file=sys.stderr)
        return False


def build_summary(conn, repo_root: Path, run_row_id: int) -> dict:
    """The run's new items, flat, plus its status and errored handles.

    EVERY handle in the run is scanned, regardless of its recorded status or
    items_downloaded. Both gates this function used to apply are deliberately
    gone: discovery_engine.py:347 records error/0 for a handle whose
    process_handle raised AFTER some downloads succeeded, which is precisely
    the case the fetched_at watermark exists to self-correct. Keeping the gates
    and keeping the watermark's rationale are mutually exclusive.

    An errored handle with partial downloads therefore appears BOTH in `items`
    and in `errored`. That is intended: "this handle broke, and here are the
    three posts it got before it broke" beats either half alone.

    `items` is flat rather than pre-grouped -- select_spotlight needs the flat
    list, and email_render owns grouping so that adding a platform never
    requires a second place to be taught about it.

    Each item also carries a `brands` list -- the tags of the handle that
    produced it (db.get_handle_brands), attached here rather than in
    discovery_digest.collect because that module is deliberately
    DB-free. notify() reads this key to partition items by brand.

    `brand_coverage` folds into this same per-handle loop (not a second pass):
    {brand: {"scanned": N, "with_items": N}} for every brand in
    email_render.BRAND_SECTION_ORDER. It exists so a brand section with zero
    items can be told apart from "this brand's handles were genuinely quiet"
    (scanned > 0, with_items == 0) versus "no handle carries this brand's tag
    at all" (scanned == 0) -- the same defect class as the whole-roster
    `coverage` dict above, reproduced at brand scope (B-113).

    Every item collect() drops or flags is surfaced too, never just silently
    counted: a hard drop (`skips`) also gets an `events` row (kind
    "digest.item_unreadable", severity "error") so it is queryable after the
    email is gone, and a soft flaw (`warnings`) gets an obs.log() line (kind
    "digest.item_flawed") -- the item itself still ships in `items`.
    """
    run_row = db_mod.get_run(conn, run_row_id)
    handle_results = db_mod.list_run_handle_results(conn, run_row_id)
    started_at = run_row["started_at"]

    items: list[dict] = []
    errored: list[str] = []
    errors: list[dict] = []
    skips: list[dict] = []
    warnings: list[dict] = []
    mismatches: list[dict] = []
    other_statuses: dict[str, list[str]] = {}
    brand_coverage = {brand: {"scanned": 0, "with_items": 0}
                      for brand in email_render.BRAND_SECTION_ORDER}
    for result in handle_results:
        handle_row = db_mod.get_handle(conn, result["handle_id"])
        label = handle_row["display_name"] or handle_row["handle"]
        brands = db_mod.get_handle_brands(conn, handle_row["id"])

        if result["status"] == "error":
            reason = _first_line(result["error_message"])
            errors.append({"label": label, "reason": reason})
            errored.append(label)
        elif result["status"] not in KNOWN_HEALTHY_STATUSES:
            # NOT a special case for the single value "skipped": any status this
            # module has never been taught about must be visible rather than
            # silently absent from the email (B-111).
            other_statuses.setdefault(result["status"], []).append(label)

        collected = discovery_digest.collect(repo_root, handle_row, started_at)
        for reason, name in collected.skips:
            skips.append({"handle": label, "reason": reason, "name": name})
            obs.record_event(
                conn, kind="digest.item_unreadable", severity="error",
                source="discovery_notify",
                message=f"{label}: {name} was dropped ({reason})",
                detail={"handle": handle_row["handle"], "platform": handle_row["platform"],
                        "file": name, "reason": reason},
                run_id=run_row_id,
            )
        for reason, name in collected.warnings:
            warnings.append({"handle": label, "reason": reason, "name": name})
            obs.log("digest.item_flawed", level="warning",
                    handle=handle_row["handle"], file=name, reason=reason)
        found = collected.items
        if len(found) != result["items_downloaded"]:
            missing = len(found) < result["items_downloaded"]
            # `found > db` is ROUTINE: discovery_engine records error/0 for a
            # handle that raised after some downloads succeeded, which is the
            # exact case the watermark exists to self-correct. `found < db` on a
            # handle the engine called healthy is not routine -- files the run
            # says it wrote are not on disk (B-100).
            escalated = missing and result["status"] not in ("error", "skipped")
            mismatches.append({"label": label, "db": result["items_downloaded"],
                               "found": len(found),
                               "direction": "missing" if missing else "extra",
                               "escalated": escalated})
            print(f"discovery_notify: item count mismatch for {label}: "
                  f"db says {result['items_downloaded']}, found {len(found)} on disk",
                  file=sys.stderr)
            if escalated:
                obs.record_event(
                    conn, kind="digest.items_missing", severity="error",
                    source="discovery_notify",
                    message=(f"{label}: the run recorded {result['items_downloaded']} items "
                             f"but only {len(found)} are on disk"),
                    detail={"handle": handle_row["handle"], "status": result["status"],
                            "db": result["items_downloaded"], "found": len(found)},
                    run_id=run_row_id)
            else:
                obs.log("digest.items_extra", level="info", handle=handle_row["handle"],
                        db=result["items_downloaded"], found=len(found))
        for item in found:
            item["brands"] = brands
        items.extend(found)
        for brand in brands:
            if brand in brand_coverage:
                brand_coverage[brand]["scanned"] += 1
                if found:
                    brand_coverage[brand]["with_items"] += 1

    items, duplicates = discovery_digest.dedupe_items(items)
    for dupe in duplicates:
        obs.record_event(
            conn, kind="digest.handle_slug_collision", severity="warning",
            source="discovery_notify",
            message=f"{dupe['display_name']} re-reported {dupe['item_id']} from a colliding slug",
            detail={"platform": dupe["platform"], "handle": dupe["handle"],
                    "item_id": dupe["item_id"]},
            run_id=run_row_id,
        )

    coverage = {
        "scanned": len(handle_results),
        "with_items": sum(1 for r in handle_results if r["items_downloaded"] > 0),
        "quiet": sum(1 for r in handle_results
                     if r["status"] == "no_new_content" or
                     (r["status"] == "ok" and r["items_downloaded"] == 0)),
        "errored": len(errored),
        "other": other_statuses,          # {status: [labels]}, any status not in KNOWN_HEALTHY_STATUSES/errored
    }
    # An empty roster produced zero items with nothing wrong, which is exactly
    # what a genuinely quiet day produces. Scanning nothing is never OK (B-95).
    has_issues = (
        run_row["status"] != "completed"
        or bool(errored)
        or coverage["scanned"] == 0
        or bool(skips)
        or bool(duplicates)
        or bool(other_statuses)
        or any(m["escalated"] for m in mismatches)  # escalated mismatches only (B-100)
    )
    if coverage["scanned"] == 0:
        obs.record_event(
            conn, kind="digest.empty_roster", severity="error", source="discovery_notify",
            message=f"run {run_row_id} scanned zero handles",
            detail={"run_status": run_row["status"]}, run_id=run_row_id)
    return {
        "run_status": run_row["status"],
        "has_issues": has_issues,
        "items": items,
        "errored": errored,
        "errors": errors,
        "skips": skips,
        "warnings": warnings,
        "duplicates": duplicates,
        "mismatches": mismatches,
        "coverage": coverage,
        "brand_coverage": brand_coverage,
        "started_at": started_at,
    }


def notify(conn, repo_root: Path, run_row_id: int) -> bool:
    overall = build_summary(conn, repo_root, run_row_id)

    # Cache keyed by (platform, handle, item_id): `guru` is a superset of the
    # other brands' items, so the same post is frequently the best spotlight
    # both globally and within its specific brand. Without this cache,
    # comment_draft.draft_comments -- a ~90s `claude -p` subprocess call --
    # would run twice for identical input (High finding #2, pre-execution
    # review).
    draft_cache: dict[tuple, list[str]] = {}

    def _drafts_for(spotlight):
        if spotlight is None:
            return []
        key = (spotlight["platform"], spotlight["handle"], spotlight["item_id"])
        if key not in draft_cache:
            draft_cache[key] = comment_draft.draft_comments(spotlight)
        return draft_cache[key]

    sections = {}
    for brand in email_render.BRAND_SECTION_ORDER:
        brand_items = [i for i in overall["items"] if brand in i["brands"]]
        spotlight, spotlight_rule = discovery_digest.select_spotlight_with_rule(brand_items)
        # draft_comments never raises and returns [] on every failure path, so a
        # drafting problem costs three drafts for this post, never the
        # section's inventory or the other two sections.
        drafts = _drafts_for(spotlight)
        if overall["brand_coverage"][brand]["scanned"] == 0:
            obs.record_event(
                conn, kind="digest.brand_untagged", severity="warning", source="discovery_notify",
                message=f"no handle is tagged '{brand}'; the section below cannot distinguish "
                        f"quiet from untagged",
                detail={"brand": brand}, run_id=run_row_id)
        sections[brand] = {
            "run_status": overall["run_status"],
            "has_issues": overall["has_issues"],
            "items": brand_items,
            "errored": overall["errored"],
            "errors": overall["errors"],
            "spotlight": spotlight,
            "spotlight_rule": spotlight_rule,
            "drafts": drafts,
            # Deliberately NO coverage/skips/warnings/duplicates/mismatches
            # here. Those are run-level facts; email_render renders them once,
            # off `overall`. Copying overall["coverage"] in (T12's interim fix)
            # made the per-section renderers print the "Handles reported as X"
            # block once per brand -- up to three times in one email (B-95b).
            # errored/errors DO stay: they are per-section by construction, and
            # every section deliberately shows the run's full error list.
        }

    timezone_name = db_mod.get_settings(conn)["timezone"]
    started_at = _dt.datetime.fromisoformat(overall["started_at"])
    run_date = started_at.astimezone(ZoneInfo(timezone_name)).date().isoformat()

    rendered = email_render.render_brand_digest(overall, sections, run_date)
    sent = send_email(rendered["subject"], rendered["text"], rendered["html"])
    if sent:
        obs.record_event(
            conn, kind="email.sent", severity="info", source="discovery_notify",
            message=rendered["subject"],
            detail={"items": len(overall["items"]), "coverage": overall["coverage"]},
            run_id=run_row_id)
    else:
        # The email is the only diagnostic surface this pipeline has, so a send
        # that failed cannot announce itself in the usual place. An absent
        # inbox message is otherwise identical to a cron that never fired, a
        # sleeping machine, or a locked run (B-94).
        obs.record_event(
            conn, kind="email.send_failed", severity="error", source="discovery_notify",
            message=f"the digest for run {run_row_id} was not delivered",
            detail={"subject": rendered["subject"], "recipient": recipient(),
                    "sender": sender(), "items": len(overall["items"])},
            run_id=run_row_id)
    return sent
