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

from pipeline_app.discovery_digest import published_rank

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
LINK_TEXT = "Click here to view"
# Middle dot, as an HTML entity. Joined into already-escaped pieces, never
# passed through html.escape itself.
SEPARATOR = " &#183; "
FEATURED_MARKER = "(featured above)"
NO_CONTENT_TEXT = "No new content today."
DRAFTS_UNAVAILABLE = "Comment drafting was unavailable for this run."


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
    spotlight, drafts = summary["spotlight"], summary["drafts"]
    items, errored = summary["items"], summary["errored"]
    lines: list[str] = []

    if summary["has_issues"]:
        lines += [f"Run status: {summary['run_status']}", ""]

    if spotlight is not None:
        lines.append(f"TODAY'S PICK: {_label(spotlight['platform'])}")
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

    if errored:
        lines.append("Errors:")
        lines += [f"- {name}" for name in errored]
        lines.append("")

    # spotlight is in the guard, not just items/errored/has_issues: a spotlight
    # with an empty items list can't arise from select_spotlight, which draws
    # from that same items list, but this renderer must not depend on that
    # upstream invariant holding -- it has to stay correct on its own terms.
    if not items and not errored and not summary["has_issues"] and spotlight is None:
        return NO_CONTENT_TEXT
    return "\n".join(lines).rstrip() + "\n"


def _render_html(summary: dict) -> str:
    spotlight, drafts = summary["spotlight"], summary["drafts"]
    items, errored = summary["items"], summary["errored"]
    esc = _html.escape
    parts: list[str] = []

    if summary["has_issues"]:
        parts.append(f"<p><strong>Run status: {esc(summary['run_status'])}</strong></p>")

    if spotlight is not None:
        # No dash anywhere in the email's own chrome either. The no-dash rule
        # is enforced on drafts, but a template that types one undercuts the
        # point for a reader scanning on a phone.
        parts.append(f"<h2>Today's pick: {esc(_label(spotlight['platform']))}</h2>")
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

    if errored:
        parts.append("<h2>Errors</h2><ul>")
        parts += [f"<li>{esc(name)}</li>" for name in errored]
        parts.append("</ul>")

    if not items and not errored and not summary["has_issues"] and spotlight is None:
        return f"<p>{NO_CONTENT_TEXT}</p>"
    return "\n".join(parts)


def render_email(summary: dict, run_date: str) -> dict:
    """{"subject", "text", "html"} for one finished run."""
    total = len(summary["items"])
    subject = f"ContentStudio Discovery {run_date}: {total} new post(s)"
    if summary["has_issues"]:
        subject = f"[ISSUE] {subject}"
    return {"subject": subject, "text": _render_text(summary),
            "html": _render_html(summary),
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
    """
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
    return {"subject": subject, "text": text, "html": html,
            "unknown_platforms": unknown_platforms(overall["items"])}
