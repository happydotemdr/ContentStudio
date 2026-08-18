"""Renders the daily discovery email. Pure function: no I/O, no clock, no
network, so every case is a snapshot test.

Both a plain-text and an HTML part are produced. The HTML part exists because
"Click here to view" as clickable text is impossible in plain text; the text
part exists so the email survives a client that blocks HTML, and carries raw
URLs in place of anchor text.

See docs/superpowers/specs/2026-08-08-morning-email-social-expansion-design.md.
"""
from __future__ import annotations

import html as _html
import re

from pipeline_app.discovery_digest import (
    published_rank, TITLE_MAX_CHARS, SPOTLIGHT_RULE_LINKEDIN, SPOTLIGHT_RULE_ENGAGEMENT,
)

SPOTLIGHT_RULE_TEXT = {
    SPOTLIGHT_RULE_LINKEDIN: "LinkedIn posts are always picked first, whatever else the day held.",
    SPOTLIGHT_RULE_ENGAGEMENT: "Picked for the most engagement (likes plus comments).",
}

# Fixed display order. Every platform id the handles CHECK constraint accepts
# MUST appear here and in PLATFORM_LABELS -- tests/test_email_render.py reads
# the constraint and fails if one does not. An id that somehow arrives unranked
# sorts last and renders VERBATIM: inventing "Linkedin Newsletter" for
# linkedin-newsletter reads as a real label and hides the omission (B-92).
PLATFORM_ORDER = (
    "linkedin-profile", "linkedin-company", "youtube", "instagram",
    "facebook", "x", "bluesky",
)
PLATFORM_LABELS = {
    "linkedin-profile": "LinkedIn",
    "linkedin-company": "LinkedIn (Company)",
    "youtube": "YouTube",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "x": "X",
    "bluesky": "Bluesky",
}

BRAND_SECTION_ORDER = ("freedom2beu", "raisinggoodsports", "guru")
BRAND_LABELS = {
    "freedom2beu": "Freedom2BeU",
    "raisinggoodsports": "RaisingGoodSports",
    "guru": "Gurus",
}

EXCERPT_MAX_CHARS = 400

# The email's exact disclosure surface, in one string, so CLAUDE.md's privacy
# paragraph has a single source to mirror and a test to fail against. The
# excerpt cap is a CEILING, not a promise of partiality: a post shorter than it
# ships whole (B-90), and a derived title on a platform with no title field is
# the post's own opening (B-91).
DISCLOSURE = (
    "Each item contributes a derived title of at most "
    f"{TITLE_MAX_CHARS} characters, which for a platform with no title "
    "field is the opening of the post text. The spotlight additionally "
    f"contributes up to {EXCERPT_MAX_CHARS} characters of its "
    "primary text, which for a post shorter than that is the whole post."
)

LINK_TEXT = "Click here to view"
# Middle dot, as an HTML entity. Joined into already-escaped pieces, never
# passed through html.escape itself.
SEPARATOR = " &#183; "
FEATURED_MARKER = "(featured above)"
NO_CONTENT_TEXT = "No new content today."
DRAFTS_UNAVAILABLE = "Comment drafting was unavailable for this run."
NO_HANDLES_TEXT = "No handles were scanned. The roster is empty or entirely excluded."

# Facts about the RUN, not about any one brand section. build_summary() puts
# these on its top-level summary; _render_text/_render_html must never read
# them, because they run once PER BRAND SECTION and would print each of these
# up to three times in a single email.
RUN_LEVEL_SUMMARY_KEYS = ("coverage", "skips", "warnings", "duplicates", "mismatches")

# What render_brand_digest needs on `overall`. Deliberately does NOT include
# spotlight/spotlight_rule/drafts: those are per-section, chosen by notify()'s
# per-brand loop, and build_summary()'s overall dict has never carried them.
REQUIRED_OVERALL_KEYS = ("run_status", "has_issues", "items", "started_at") + RUN_LEVEL_SUMMARY_KEYS

# What render_email needs: one summary that is BOTH the section and the run.
REQUIRED_SUMMARY_KEYS = (
    "run_status", "has_issues", "items", "errored", "errors", "spotlight",
    "spotlight_rule", "drafts", "coverage", "skips", "warnings", "duplicates",
    "mismatches",
)


def _require(summary: dict, keys: tuple[str, ...], what: str) -> None:
    """Raise rather than default on an incomplete summary: a missing `coverage`
    used to render as a perfectly healthy-looking quiet day, which is the exact
    confusion this package exists to remove (B-95)."""
    missing = [k for k in keys if k not in summary]
    if missing:
        raise KeyError(f"email_render: {what} is missing {missing}")


def _coverage_line(overall: dict) -> str:
    c = overall["coverage"]
    if c["scanned"] == 0:
        return NO_HANDLES_TEXT
    return (f"Scanned {c['scanned']} handle(s): {c['with_items']} with new posts, "
            f"{c['quiet']} quiet, {c['errored']} errored.")


def _notices(overall: dict) -> list[str]:
    """Everything that went wrong that is not a handle error. Each line names
    the count AND an example, so a reader can act without opening the DB."""
    out = []
    if overall["skips"]:
        names = ", ".join(sorted({s["name"] for s in overall["skips"]})[:5])
        out.append(f"{len(overall['skips'])} captured file(s) could not be read: {names}")
    if overall["duplicates"]:
        out.append(f"{len(overall['duplicates'])} post(s) were reported twice by "
                   f"handles whose directory slugs collide.")
    escalated = [m for m in overall["mismatches"] if m["escalated"]]
    for m in escalated:
        out.append(f"{m['label']}: the run recorded {m['db']} items but only "
                   f"{m['found']} are on disk.")
    for platform in unknown_platforms(overall["items"]):
        out.append(f"Platform '{platform}' has no configured label or display rank.")
    return out


def _run_notice_lines(overall: dict) -> list[str]:
    """The run-level footer, plain text. Called ONCE per email, on the run's
    own summary -- never from _render_text, which runs once per brand."""
    lines: list[str] = []
    for status, names in sorted(overall["coverage"]["other"].items()):
        lines.append(f"Handles reported as {status}:")
        lines += [f"- {name}" for name in names]
        lines.append("")
    lines.append(_coverage_line(overall))
    lines += _notices(overall)
    return lines


def _run_notice_html(overall: dict) -> list[str]:
    """The run-level footer, HTML. Same contract as _run_notice_lines."""
    esc = _html.escape
    parts: list[str] = []
    for status, names in sorted(overall["coverage"]["other"].items()):
        parts.append(f"<h2>Handles reported as {esc(status)}</h2><ul>")
        parts += [f"<li>{esc(name)}</li>" for name in names]
        parts.append("</ul>")
    parts.append(f"<p>{esc(_coverage_line(overall))}</p>")
    parts += [f"<p>{esc(n)}</p>" for n in _notices(overall)]
    return parts


def _append_run_notices_text(body: str, overall: dict) -> str:
    tail = "\n".join(_run_notice_lines(overall)).rstrip()
    head = body.rstrip()
    return (f"{head}\n\n{tail}" if head else tail).rstrip() + "\n"


def _append_run_notices_html(body: str, overall: dict) -> str:
    return "\n".join([body, *_run_notice_html(overall)])


def _label(platform: str) -> str:
    return PLATFORM_LABELS.get(platform, platform)


def unknown_platforms(items: list[dict]) -> list[str]:
    """Every platform id in `items` with no rank and no label, sorted."""
    return sorted({i["platform"] for i in items} - set(PLATFORM_LABELS))


def _safe_url(url) -> str | None:
    """The URL, or None if it is absent or not an http(s) address.

    Scraped frontmatter is untrusted: a malformed or `javascript:` value must
    never become a live anchor in an email.
    """
    if not isinstance(url, str):
        return None
    stripped = url.strip()
    return stripped if stripped.startswith(("http://", "https://")) else None


def _metric_bits(item: dict) -> list[str]:
    """Present metrics as display strings. None is omitted; 0 is shown."""
    bits = []
    for value, noun in ((item["views"], "views"), (item["likes"], "likes"),
                        (item["comments"], "comments")):
        if value is not None:
            bits.append(f"{value:,} {noun}")
    return bits


def _excerpt(body: str) -> str:
    collapsed = re.sub(r"\s+", " ", body or "").strip()
    if len(collapsed) <= EXCERPT_MAX_CHARS:
        return collapsed
    cut = collapsed[:EXCERPT_MAX_CHARS]
    space = cut.rfind(" ")
    return (cut[:space] if space > 0 else cut).rstrip() + "..."


def _grouped(items: list[dict]) -> list[tuple[str, list[dict]]]:
    rank = {platform: i for i, platform in enumerate(PLATFORM_ORDER)}
    platforms = sorted({i["platform"] for i in items},
                       key=lambda p: (rank.get(p, len(rank)), p))
    groups = []
    for platform in platforms:
        group = [i for i in items if i["platform"] == platform]
        # handle is in the key for the same totality reason as in
        # select_spotlight, and because two handles can share a display_name.
        group.sort(key=lambda i: (i["display_name"], i["handle"],
                                  published_rank(i["published"]), i["item_id"]))
        groups.append((platform, group))
    return groups


def _is_spotlight(item: dict, spotlight: dict | None) -> bool:
    if spotlight is None:
        return False
    return (item["platform"], item["handle"], item["item_id"]) == (
        spotlight["platform"], spotlight["handle"], spotlight["item_id"])


def _render_text(summary: dict) -> str:
    """ONE section's body. Runs once per brand in render_brand_digest, so it
    reads only per-section keys -- items, errored, errors, spotlight,
    spotlight_rule, drafts. Run-level facts live in _run_notice_lines()."""
    spotlight, drafts = summary["spotlight"], summary["drafts"]
    items = summary["items"]
    lines: list[str] = []

    if summary["has_issues"]:
        lines += [f"Run status: {summary['run_status']}", ""]

    if spotlight is not None:
        lines.append(f"TODAY'S PICK: {_label(spotlight['platform'])}")
        lines.append(SPOTLIGHT_RULE_TEXT[summary["spotlight_rule"]])
        header = [spotlight["display_name"], *_metric_bits(spotlight)]
        if spotlight["published"]:
            header.append(spotlight["published"])
        # Title FIRST in both parts. The two branches previously disagreed on
        # field order, so a text-fallback client read a different message from
        # the same email (B-108).
        lines += [spotlight["title"], " | ".join(header), "",
                  _excerpt(spotlight["body"]), ""]
        url = _safe_url(spotlight["url"])
        if url:
            lines += [url, ""]
        if drafts:
            lines.append("Comment drafts (review before posting):")
            lines += [f"{n}. {d}" for n, d in enumerate(drafts, start=1)]
        else:
            lines.append(DRAFTS_UNAVAILABLE)
        # Underscores, not hyphens: the no-dash rule applies to the email's own
        # chrome too, and "---" here would contradict it in the plain-text part.
        lines += ["", "___", ""]

    for platform, group in _grouped(items):
        lines.append(_label(platform))
        for item in group:
            bits = [item["display_name"], item["title"], *_metric_bits(item)]
            if _is_spotlight(item, spotlight):
                bits.append(FEATURED_MARKER)
            lines.append("- " + " | ".join(bits))
            url = _safe_url(item["url"])
            if url:
                lines.append(f"  {url}")
        lines.append("")

    if summary["errors"]:
        causes = {e["reason"] for e in summary["errors"]}
        lines.append(f"Errors ({len(summary['errors'])} handle(s), "
                     f"{len(causes)} distinct cause(s)):")
        lines += [f"- {e['label']}: {e['reason']}" for e in summary["errors"]]
        lines.append("")

    # spotlight is in the guard, not just items: a spotlight with an empty items
    # list can't arise from select_spotlight, which draws from that same items
    # list, but this renderer must not depend on that upstream invariant
    # holding -- it has to stay correct on its own terms. `errored`/`has_issues`
    # left the guard with B-95b: the body no longer ENDS here (a coverage footer
    # always follows), so "nothing to show" is now a line, not a whole email.
    if not items and spotlight is None:
        lines.append(NO_CONTENT_TEXT)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_html(summary: dict) -> str:
    """ONE section's body. Same per-section-only contract as _render_text."""
    spotlight, drafts = summary["spotlight"], summary["drafts"]
    items = summary["items"]
    esc = _html.escape
    parts: list[str] = []

    if summary["has_issues"]:
        parts.append(f"<p><strong>Run status: {esc(summary['run_status'])}</strong></p>")

    if spotlight is not None:
        # No dash anywhere in the email's own chrome either. The no-dash rule
        # is enforced on drafts, but a template that types one undercuts the
        # point for a reader scanning on a phone.
        parts.append(f"<h2>Today's pick: {esc(_label(spotlight['platform']))}</h2>")
        parts.append(f"<p><em>{esc(SPOTLIGHT_RULE_TEXT[summary['spotlight_rule']])}</em></p>")
        header = [spotlight["display_name"], *_metric_bits(spotlight)]
        if spotlight["published"]:
            header.append(spotlight["published"])
        # Escape each piece, THEN join with a literal entity separator. Escaping
        # the joined string would turn the separator's "&" into "&amp;".
        parts.append(f"<p><strong>{esc(spotlight['title'])}</strong><br>"
                     + SEPARATOR.join(esc(h) for h in header) + "</p>")
        parts.append(f"<p><em>{esc(_excerpt(spotlight['body']))}</em></p>")
        url = _safe_url(spotlight["url"])
        if url:
            parts.append(f'<p><a href="{esc(url, quote=True)}">{LINK_TEXT}</a></p>')
        if drafts:
            parts.append("<h3>Comment drafts (review before posting)</h3><ol>")
            parts += [f"<li>{esc(d)}</li>" for d in drafts]
            parts.append("</ol>")
        else:
            parts.append(f"<p><em>{esc(DRAFTS_UNAVAILABLE)}</em></p>")
        parts.append("<hr>")

    for platform, group in _grouped(items):
        parts.append(f"<h2>{esc(_label(platform))}</h2><ul>")
        for item in group:
            bits = [esc(item["display_name"]), f"<em>{esc(item['title'])}</em>"]
            bits += [esc(b) for b in _metric_bits(item)]
            url = _safe_url(item["url"])
            if url:
                bits.append(f'<a href="{esc(url, quote=True)}">{LINK_TEXT}</a>')
            if _is_spotlight(item, spotlight):
                bits.append(esc(FEATURED_MARKER))
            parts.append("<li>" + SEPARATOR.join(bits) + "</li>")
        parts.append("</ul>")

    if summary["errors"]:
        causes = {e["reason"] for e in summary["errors"]}
        parts.append(f"<h2>Errors ({len(summary['errors'])} handle(s), "
                     f"{len(causes)} distinct cause(s))</h2><ul>")
        parts += [f"<li>{esc(e['label'])}: {esc(e['reason'])}</li>" for e in summary["errors"]]
        parts.append("</ul>")

    if not items and spotlight is None:
        parts.append(f"<p>{NO_CONTENT_TEXT}</p>")
    return "\n".join(parts)


def render_email(summary: dict, run_date: str) -> dict:
    """{"subject", "text", "html", "unknown_platforms"} for one finished run.

    Single-section entrypoint: `summary` is BOTH the only section and the run,
    so the run-level footer is built from that same dict. Production uses
    render_brand_digest instead; this stays a real, directly-tested entrypoint.

    Raises on an incomplete summary rather than defaulting: a missing
    `coverage` used to render as a perfectly healthy-looking quiet day, which
    is the exact confusion this package exists to remove (B-95).
    """
    _require(summary, REQUIRED_SUMMARY_KEYS, "summary")
    total = len(summary["items"])
    subject = f"ContentStudio Discovery {run_date}: {total} new post(s)"
    if summary["has_issues"]:
        subject = f"[ISSUE] {subject}"
    return {"subject": subject,
            "text": _append_run_notices_text(_render_text(summary), summary),
            "html": _append_run_notices_html(_render_html(summary), summary),
            "unknown_platforms": unknown_platforms(summary["items"])}


def render_brand_digest(overall: dict, sections: dict, run_date: str) -> dict:
    """{"subject", "text", "html"} for one finished run, split into per-brand
    sections in BRAND_SECTION_ORDER.

    `overall` is build_summary()'s pre-partition summary -- its `items` is what
    the subject line counts. Brand sections deliberately overlap (multi-tag: an
    item tagged both `raisinggoodsports` and `guru` renders in both sections),
    so summing section sizes would double-count it; `overall["items"]` is the
    one place a post is counted exactly once. `overall["has_issues"]` likewise
    drives the [ISSUE] prefix for the same reason -- it is a run-wide fact, not
    a per-brand one.

    `sections` maps brand -> a summary shaped exactly like render_email's
    parameter, already restricted to that brand's items/spotlight/drafts. A
    brand absent from `sections` is omitted from the email entirely.

    An item in `overall["items"]` that no section's `items` list contains
    (an untagged handle, or one tagged with something outside
    BRAND_SECTION_ORDER) would otherwise vanish from the email silently
    while the subject's count still included it -- Critical finding #1 from
    the pre-execution review. A warning banner makes that discoverable
    instead of silent.

    Run-level facts (coverage, skips, duplicates, escalated mismatches, unranked
    platforms) are read off `overall` ONLY and rendered once, as a footer under
    all the sections. They used to be threaded into every `sections[brand]` dict
    and rendered by the per-section renderers, which printed each of them up to
    three times in one email (B-95b).

    The missing-key guard lives here as well as on render_email because THIS is
    the entrypoint production calls: a guard only on render_email would protect
    a function notify() never reaches.
    """
    _require(overall, REQUIRED_OVERALL_KEYS, "overall summary")
    total = len(overall["items"])
    subject = f"ContentStudio Discovery {run_date}: {total} new post(s)"
    if overall["has_issues"]:
        subject = f"[ISSUE] {subject}"

    def _identity(item):
        return (item["platform"], item["handle"], item["item_id"])

    covered = {_identity(i) for s in sections.values() for i in s["items"]}
    orphan_count = sum(1 for i in overall["items"] if _identity(i) not in covered)
    warning_text = warning_html = ""
    if orphan_count:
        message = (f"{orphan_count} new post(s) came from handle(s) with no brand tag "
                   f"(or a tag outside {', '.join(BRAND_SECTION_ORDER)}) and do not "
                   f"appear in any section below. Tag them at /discovery/handles.")
        warning_text = f"WARNING: {message}\n\n"
        warning_html = f"<p><strong>WARNING:</strong> {_html.escape(message)}</p>\n"

    text_parts: list[str] = []
    html_parts: list[str] = []
    for brand in BRAND_SECTION_ORDER:
        summary = sections.get(brand)
        if summary is None:
            continue
        label = BRAND_LABELS.get(brand, brand.title())
        text_parts.append(f"===== {label.upper()} =====\n\n{_render_text(summary)}")
        html_parts.append(f"<h1>{_html.escape(label)}</h1>\n{_render_html(summary)}")

    text = warning_text + (
        "\n\n".join(text_parts).rstrip() + "\n" if text_parts else NO_CONTENT_TEXT + "\n"
    )
    html = warning_html + (
        "\n<hr>\n".join(html_parts) if html_parts else f"<p>{NO_CONTENT_TEXT}</p>"
    )
    text = _append_run_notices_text(text, overall)
    html = _append_run_notices_html(html, overall)
    return {"subject": subject, "text": text, "html": html,
            "unknown_platforms": unknown_platforms(overall["items"])}
