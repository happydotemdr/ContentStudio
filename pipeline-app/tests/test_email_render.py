import re
from pathlib import Path

import pytest

from pipeline_app import email_render


def _item(platform="youtube", handle="chan", display_name="Some Channel", item_id="vid1",
          title="How To Actually Finish A Video", url="https://youtu.be/vid1",
          published="2026-08-07", views=41203, likes=1890, comments=None,
          body="So the first thing nobody tells you is that finishing is a skill."):
    return {"platform": platform, "handle": handle, "display_name": display_name,
            "item_id": item_id, "title": title, "url": url, "published": published,
            "views": views, "likes": likes, "comments": comments, "body": body}


def _summary(items=None, spotlight=None, spotlight_rule=None, drafts=None, errored=None,
             errors=None, run_status="completed", has_issues=False, coverage=None,
             skips=None, warnings=None, duplicates=None, mismatches=None):
    return {"run_status": run_status, "has_issues": has_issues,
            "items": items if items is not None else [],
            "errored": errored if errored is not None else [],
            "errors": errors if errors is not None else [],
            "spotlight": spotlight, "spotlight_rule": spotlight_rule,
            "drafts": drafts if drafts is not None else [],
            "coverage": coverage or {"scanned": 3, "with_items": 0, "quiet": 3,
                                     "errored": 0, "other": {}},
            "skips": skips or [], "warnings": warnings or [],
            "duplicates": duplicates or [], "mismatches": mismatches or []}


def _section(items=None, spotlight=None, spotlight_rule=None, drafts=None, errored=None,
             errors=None, run_status="completed", has_issues=False):
    """A per-brand section dict, carrying ONLY genuinely per-section keys.

    Deliberately narrower than _summary(): run-level facts (coverage, skips,
    warnings, duplicates, mismatches) live on `overall` and are rendered once
    by render_brand_digest, never once per section.
    """
    return {"run_status": run_status, "has_issues": has_issues,
            "items": items if items is not None else [],
            "errored": errored if errored is not None else [],
            "errors": errors if errors is not None else [],
            "spotlight": spotlight, "spotlight_rule": spotlight_rule,
            "drafts": drafts if drafts is not None else []}


SCHEMA = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"


def _schema_platforms() -> set[str]:
    check = re.search(r"platform\s+IN\s*\(([^)]*)\)", SCHEMA.read_text(encoding="utf-8"))
    if check is None:
        raise AssertionError(
            "handles has no platform CHECK constraint; this guard needs package P1's schema change")
    return set(re.findall(r"'([^']+)'", check.group(1)))


def test_subject_counts_posts_not_videos():
    result = email_render.render_email(_summary(items=[_item(), _item(item_id="vid2")]), "2026-08-08")
    assert result["subject"] == "ContentStudio Discovery 2026-08-08: 2 new post(s)"


def test_no_new_content_body():
    result = email_render.render_email(_summary(), "2026-08-08")
    assert result["subject"] == "ContentStudio Discovery 2026-08-08: 0 new post(s)"
    # No longer the WHOLE body: the coverage footer now follows it (B-95b).
    assert "No new content today." in result["text"]
    assert "No new content today." in result["html"]


def test_a_quiet_day_states_the_denominator_it_was_quiet_against():
    result = email_render.render_email(_summary(), "2026-08-08")
    assert result["text"] != "No new content today."          # inverts the old assertion
    assert "No new content today." in result["text"]
    assert "Scanned 3 handle(s)" in result["text"]
    assert "3 quiet" in result["text"]
    assert "Scanned 3 handle(s)" in result["html"]


def test_an_empty_roster_says_so_instead_of_reading_as_a_quiet_day():
    coverage = {"scanned": 0, "with_items": 0, "quiet": 0, "errored": 0, "other": {}}
    result = email_render.render_email(
        _summary(coverage=coverage, has_issues=True, run_status="completed"), "2026-08-08")
    assert result["subject"].startswith("[ISSUE] ")
    assert "No handles were scanned" in result["text"]
    assert "No handles were scanned" in result["html"]


def test_render_email_refuses_a_summary_missing_a_required_key():
    summary = _summary()
    del summary["coverage"]
    with pytest.raises(KeyError, match="coverage"):
        email_render.render_email(summary, "2026-08-08")


def test_unreadable_files_are_named_in_the_body():
    skips = [{"handle": "Betty Liu", "reason": "bad_frontmatter", "name": "broken.md"}]
    text = email_render.render_email(_summary(skips=skips, has_issues=True), "2026-08-08")["text"]
    assert "1 captured file(s) could not be read" in text
    assert "broken.md" in text


def test_issue_prefixes_subject_and_opens_body_with_run_status():
    summary = _summary(run_status="failed", has_issues=True)
    result = email_render.render_email(summary, "2026-08-08")
    assert result["subject"].startswith("[ISSUE] ")
    assert result["text"].startswith("Run status: failed")
    assert "Run status: failed" in result["html"]


def test_errors_section_lists_handle_names():
    summary = _summary(errored=["@dead-handle"],
                        errors=[{"label": "@dead-handle", "reason": "boom"}],
                        has_issues=True)
    result = email_render.render_email(summary, "2026-08-08")
    assert "@dead-handle" in result["text"]
    assert "@dead-handle" in result["html"]


def test_one_systemic_cause_is_visually_separable_from_many_independent_ones():
    same = [{"label": f"Handle {i}", "reason": "BrightDataError: 401 unauthorized"}
            for i in range(6)]
    summary = _summary(errored=[e["label"] for e in same], errors=same, has_issues=True)
    text = email_render.render_email(summary, "2026-08-08")["text"]
    assert "401 unauthorized" in text
    assert "1 distinct cause" in text


def test_an_error_reason_is_html_escaped():
    errors = [{"label": "Someone", "reason": '<img src=x onerror="alert(1)">'}]
    html = email_render.render_email(
        _summary(errored=["Someone"], errors=errors, has_issues=True), "2026-08-08")["html"]
    assert "<img" not in html
    assert "&lt;img" in html


def test_click_here_to_view_is_the_anchor_text_in_html_and_a_raw_url_in_text():
    result = email_render.render_email(_summary(items=[_item()]), "2026-08-08")
    assert '<a href="https://youtu.be/vid1">Click here to view</a>' in result["html"]
    assert "https://youtu.be/vid1" in result["text"]
    assert "Click here to view" not in result["text"]


def test_spotlight_renders_excerpt_metrics_and_drafts():
    spot = _item(platform="linkedin-profile", display_name="Betty Liu", item_id="7358",
                 title="Moving fast", url="https://example.com/li", views=None,
                 likes=214, comments=37, body="We keep telling founders to move fast.")
    drafts = ["Draft one is here.", "Draft two is here.", "Draft three is here."]
    result = email_render.render_email(
        _summary(items=[spot], spotlight=spot,
                spotlight_rule=email_render.SPOTLIGHT_RULE_LINKEDIN, drafts=drafts),
        "2026-08-08")
    assert "Betty Liu" in result["html"]
    assert "We keep telling founders" in result["html"]
    assert "214 likes" in result["html"]
    assert "37 comments" in result["html"]
    for draft in drafts:
        assert draft in result["html"]
        assert draft in result["text"]


def test_spotlight_notes_when_drafting_was_unavailable():
    spot = _item()
    result = email_render.render_email(
        _summary(items=[spot], spotlight=spot,
                spotlight_rule=email_render.SPOTLIGHT_RULE_ENGAGEMENT, drafts=[]),
        "2026-08-08")
    assert "unavailable" in result["text"].lower()
    assert "How To Actually Finish A Video" in result["html"]


def test_spotlight_item_still_appears_in_the_inventory_with_a_marker():
    spot = _item()
    result = email_render.render_email(
        _summary(items=[spot], spotlight=spot,
                spotlight_rule=email_render.SPOTLIGHT_RULE_ENGAGEMENT, drafts=[]),
        "2026-08-08")
    assert result["text"].count("How To Actually Finish A Video") >= 2
    assert "featured above" in result["text"]


def test_facebook_and_x_rank_above_no_platform_and_carry_real_labels():
    items = [_item(platform="bluesky", handle="b", item_id="b1", title="Bluesky Post"),
             _item(platform="facebook", handle="f", item_id="f1", title="Facebook Post"),
             _item(platform="x", handle="x", item_id="x1", title="X Post")]
    text = email_render.render_email(_summary(items=items), "2026-08-08")["text"]
    assert "Facebook" in text and "\nX\n" in text
    assert text.index("Facebook") < text.index("Bluesky")
    assert text.index("X\n") < text.index("Bluesky")


def test_an_unranked_platform_is_reported_rather_than_silently_titlecased():
    # Replaces test_unknown_platform_sorts_last_with_a_titlecased_label, which
    # ratified the fallback instead of catching the two real omissions (B-92).
    unknown = _item(platform="linkedin-newsletter", handle="n", item_id="n1", title="A Newsletter")
    result = email_render.render_email(_summary(items=[unknown]), "2026-08-08")
    assert "Linkedin Newsletter" not in result["text"]      # never invent a label
    assert "linkedin-newsletter" in result["text"]          # show the id verbatim
    assert result["unknown_platforms"] == ["linkedin-newsletter"]


def test_missing_url_renders_the_entry_without_a_link():
    result = email_render.render_email(_summary(items=[_item(url=None)]), "2026-08-08")
    assert "How To Actually Finish A Video" in result["text"]
    assert "Click here to view" not in result["html"]


def test_non_http_url_never_becomes_an_anchor():
    result = email_render.render_email(
        _summary(items=[_item(url="javascript:alert(1)")]), "2026-08-08")
    assert "javascript:" not in result["html"]
    assert "Click here to view" not in result["html"]


def test_href_escapes_quotes_and_cannot_break_out_of_the_attribute():
    # Pins quote=True on the href escape. A URL is scraped frontmatter, so a
    # raw double quote in it would close the attribute and let the rest of the
    # string become markup.
    hostile = 'https://example.com/a?b="c onmouseover="alert(1)'
    result = email_render.render_email(_summary(items=[_item(url=hostile)]), "2026-08-08")
    assert 'href="https://example.com/a?b=&quot;c onmouseover=&quot;alert(1)"' in result["html"]
    assert 'b="c' not in result["html"]
    assert "onmouseover=\"alert" not in result["html"]


def test_html_escapes_untrusted_title_and_excerpt():
    spot = _item(title='A <script>alert("x")</script> & more',
                 body='Body with <b>tags</b> & "quotes".')
    result = email_render.render_email(
        _summary(items=[spot], spotlight=spot,
                spotlight_rule=email_render.SPOTLIGHT_RULE_ENGAGEMENT), "2026-08-08")
    assert "<script>" not in result["html"]
    assert "&lt;script&gt;" in result["html"]
    assert "&amp;" in result["html"]


def test_metrics_omit_absent_values_and_keep_zero():
    result = email_render.render_email(
        _summary(items=[_item(views=0, likes=None, comments=None)]), "2026-08-08")
    assert "0 views" in result["text"]
    assert "likes" not in result["text"]


def test_inventory_groups_by_handle_then_newest_first():
    items = [
        _item(handle="b", display_name="Beta", item_id="b1", title="Beta Old", published="2026-08-01"),
        _item(handle="a", display_name="Alpha", item_id="a1", title="Alpha Old", published="2026-08-01"),
        _item(handle="a", display_name="Alpha", item_id="a2", title="Alpha New", published="2026-08-07"),
    ]
    text = email_render.render_email(_summary(items=items), "2026-08-08")["text"]
    assert text.index("Alpha New") < text.index("Alpha Old") < text.index("Beta Old")


def test_spotlight_survives_an_empty_inventory():
    spot = _item()
    drafts = ["Draft one is here."]
    result = email_render.render_email(
        _summary(items=[], spotlight=spot,
                spotlight_rule=email_render.SPOTLIGHT_RULE_ENGAGEMENT, drafts=drafts),
        "2026-08-08")
    assert result["text"] != "No new content today."
    assert "How To Actually Finish A Video" in result["text"]
    assert "Draft one is here." in result["text"]
    assert "No new content today." not in result["html"]
    assert "How To Actually Finish A Video" in result["html"]
    assert "Draft one is here." in result["html"]


def test_text_and_html_list_the_same_titles():
    items = [_item(), _item(item_id="vid2", title="Second Video", url="https://youtu.be/vid2")]
    result = email_render.render_email(_summary(items=items), "2026-08-08")
    for title in ("How To Actually Finish A Video", "Second Video"):
        assert title in result["text"]
        assert title in result["html"]


def test_spotlight_header_uses_the_same_field_order_in_both_parts():
    spot = _item(platform="linkedin-profile", display_name="Betty Liu", item_id="7358",
                 title="Moving fast", views=None, likes=214, comments=37,
                 published="2026-08-07")
    result = email_render.render_email(
        _summary(items=[spot], spotlight=spot,
                spotlight_rule=email_render.SPOTLIGHT_RULE_LINKEDIN), "2026-08-08")
    text, html = result["text"], result["html"]
    order = ("Moving fast", "Betty Liu", "214 likes", "37 comments", "2026-08-07")
    for part in (text, html):
        positions = [part.index(field) for field in order]
        assert positions == sorted(positions), f"field order broke in:\n{part}"


def test_render_brand_digest_orders_sections_freedom2beu_then_rgs_then_guru():
    sections = {
        "guru": _summary(items=[_item(item_id="g1", title="Guru Post")]),
        "raisinggoodsports": _summary(items=[_item(item_id="r1", title="RGS Post")]),
        "freedom2beu": _summary(items=[_item(item_id="f1", title="F2BU Post")]),
    }
    overall = _summary(items=[_item(item_id="g1"), _item(item_id="r1"), _item(item_id="f1")])
    result = email_render.render_brand_digest(overall, sections, "2026-08-15")
    text = result["text"]
    assert text.index("F2BU Post") < text.index("RGS Post") < text.index("Guru Post")
    html = result["html"]
    assert html.index("F2BU Post") < html.index("RGS Post") < html.index("Guru Post")


def test_render_brand_digest_labels_each_section():
    sections = {"freedom2beu": _summary(items=[_item()]), "raisinggoodsports": _summary(),
                "guru": _summary()}
    overall = _summary(items=[_item()])
    result = email_render.render_brand_digest(overall, sections, "2026-08-15")
    assert "Freedom2BeU" in result["html"]
    assert "RaisingGoodSports" in result["html"]
    assert "Gurus" in result["html"]


def test_render_brand_digest_omits_a_brand_missing_from_sections():
    # This exercises render_brand_digest's own defensive contract in
    # isolation. notify() (Task 5) always populates all three keys in
    # `sections`, so this branch is not reachable from the real pipeline
    # today -- it exists so render_brand_digest stays correct if ever called
    # with a partial `sections` dict directly (e.g. from a future script or
    # a test), which is exactly what this test does.
    sections = {"guru": _summary(items=[_item()])}
    overall = _summary(items=[_item()])
    result = email_render.render_brand_digest(overall, sections, "2026-08-15")
    assert "Freedom2BeU" not in result["html"]
    assert "RaisingGoodSports" not in result["html"]
    assert "Gurus" in result["html"]


def test_render_brand_digest_subject_counts_distinct_items_not_section_sum():
    # The same post can render under two sections (multi-tag). The subject
    # must count it once, from `overall`, not twice from summing sections.
    shared = _item(item_id="shared1")
    sections = {
        "guru": _summary(items=[shared]),
        "raisinggoodsports": _summary(items=[shared]),
    }
    overall = _summary(items=[shared])
    result = email_render.render_brand_digest(overall, sections, "2026-08-08")
    assert result["subject"] == "ContentStudio Discovery 2026-08-08: 1 new post(s)"


def test_render_brand_digest_issue_prefix_comes_from_overall_not_sections():
    sections = {"guru": _summary(has_issues=False)}
    overall = _summary(run_status="failed", has_issues=True)
    result = email_render.render_brand_digest(overall, sections, "2026-08-08")
    assert result["subject"].startswith("[ISSUE] ")


def test_render_brand_digest_each_section_keeps_its_own_spotlight_and_drafts():
    f2bu_spot = _item(item_id="f1", title="F2BU Spotlight")
    rgs_spot = _item(item_id="r1", title="RGS Spotlight")
    sections = {
        "freedom2beu": _summary(items=[f2bu_spot], spotlight=f2bu_spot,
                                spotlight_rule=email_render.SPOTLIGHT_RULE_ENGAGEMENT,
                                drafts=["F2BU draft one.", "F2BU draft two.", "F2BU draft three."]),
        "raisinggoodsports": _summary(items=[rgs_spot], spotlight=rgs_spot,
                                      spotlight_rule=email_render.SPOTLIGHT_RULE_ENGAGEMENT,
                                      drafts=["RGS draft one.", "RGS draft two.", "RGS draft three."]),
    }
    overall = _summary(items=[f2bu_spot, rgs_spot])
    result = email_render.render_brand_digest(overall, sections, "2026-08-15")
    assert "F2BU draft one." in result["text"]
    assert "RGS draft one." in result["text"]


def test_render_brand_digest_falls_back_to_no_content_when_every_section_is_empty():
    result = email_render.render_brand_digest(_summary(), {}, "2026-08-15")
    assert "No new content today." in result["text"]
    assert "No new content today." in result["html"]


def test_render_brand_digest_warns_about_items_covered_by_no_section():
    # An untagged handle's items pass through build_summary but match no
    # brand in BRAND_SECTION_ORDER, so no section's `items` list contains
    # them. Without this warning they vanish from the email while the
    # subject's count (drawn from `overall`) still includes them --
    # Critical finding #1 from the pre-execution review.
    orphan = _item(item_id="orphan1", title="Orphan Post")
    overall = _summary(items=[orphan])
    result = email_render.render_brand_digest(overall, {}, "2026-08-15")
    assert result["subject"] == "ContentStudio Discovery 2026-08-15: 1 new post(s)"
    assert "no brand tag" in result["text"].lower()
    assert "no brand tag" in result["html"].lower()


def test_render_brand_digest_no_warning_when_every_item_is_covered():
    covered = _item(item_id="c1")
    sections = {"guru": _summary(items=[covered])}
    overall = _summary(items=[covered])
    result = email_render.render_brand_digest(overall, sections, "2026-08-15")
    assert "no brand tag" not in result["text"].lower()
    assert "no brand tag" not in result["html"].lower()


def test_render_brand_digest_includes_unknown_platforms_in_return_dict():
    # Parity with render_email: unknown platforms are surfaced for monitoring.
    unknown = _item(platform="linkedin-newsletter", handle="n", item_id="n1", title="A Newsletter")
    sections = {"guru": _summary(items=[unknown])}
    overall = _summary(items=[unknown])
    result = email_render.render_brand_digest(overall, sections, "2026-08-15")
    assert result["unknown_platforms"] == ["linkedin-newsletter"]


def test_the_email_states_that_linkedin_always_wins_the_spotlight():
    spot = _item(platform="linkedin-profile", item_id="li")
    result = email_render.render_email(
        _summary(items=[spot], spotlight=spot,
                 spotlight_rule=email_render.SPOTLIGHT_RULE_LINKEDIN), "2026-08-08")
    for part in (result["text"], result["html"]):
        assert "LinkedIn posts are always picked first" in part


def test_a_non_linkedin_spotlight_is_labelled_as_the_most_engaged():
    spot = _item(platform="youtube", item_id="yt")
    result = email_render.render_email(
        _summary(items=[spot], spotlight=spot,
                 spotlight_rule=email_render.SPOTLIGHT_RULE_ENGAGEMENT), "2026-08-08")
    assert "most engagement" in result["text"]
    assert "always picked first" not in result["text"]


def _three_brand_sections():
    return {
        "freedom2beu": _section(items=[_item(item_id="f1", title="F2BU Post")]),
        "raisinggoodsports": _section(items=[_item(item_id="r1", title="RGS Post")]),
        "guru": _section(items=[_item(item_id="g1", title="Guru Post")]),
    }


def test_render_brand_digest_prints_run_level_facts_once_not_once_per_section():
    # Task 12 threaded overall["coverage"] into every sections[brand] dict as an
    # interim step, so a run with a non-empty other_statuses printed the
    # "Handles reported as ..." block THREE times in one email -- once per brand
    # section. Run-level facts belong to the run, not to any brand.
    overall = _summary(
        items=[_item(item_id="f1"), _item(item_id="r1"), _item(item_id="g1")],
        has_issues=True,
        coverage={"scanned": 4, "with_items": 3, "quiet": 0, "errored": 0,
                  "other": {"skipped": ["Someone BS"]}},
        skips=[{"handle": "Betty Liu", "reason": "bad_frontmatter", "name": "broken.md"}],
        duplicates=[{"item_id": "dupe1"}],
        mismatches=[{"label": "Aspen", "db": 3, "found": 1, "direction": "missing",
                     "escalated": True}],
    )
    result = email_render.render_brand_digest(overall, _three_brand_sections(), "2026-08-15")

    for part in (result["text"], result["html"]):
        assert part.count("Scanned 4 handle(s)") == 1
        assert part.count("Handles reported as skipped") == 1
        assert part.count("Someone BS") == 1
        assert part.count("1 captured file(s) could not be read") == 1
        assert part.count("broken.md") == 1
        assert part.count("reported twice") == 1
        assert part.count("but only 1 are on disk") == 1
    # ...while genuinely per-section content still renders once per section.
    assert result["text"].count("F2BU Post") == 1
    assert result["text"].count("RGS Post") == 1
    assert result["text"].count("Guru Post") == 1


def test_render_brand_digest_reports_an_unranked_platform_once_for_the_whole_run():
    unknown = _item(platform="linkedin-newsletter", handle="n", item_id="n1",
                    title="A Newsletter")
    sections = {"freedom2beu": _section(items=[unknown]),
                "raisinggoodsports": _section(items=[unknown])}
    overall = _summary(items=[unknown])
    result = email_render.render_brand_digest(overall, sections, "2026-08-15")
    assert result["text"].count("no configured label or display rank") == 1
    assert result["html"].count("no configured label or display rank") == 1


def test_render_brand_digest_sections_need_no_run_level_keys():
    # _section() carries no coverage/skips/warnings/duplicates/mismatches at
    # all. The per-section renderers must not reach for them (this is what lets
    # notify() stop copying overall["coverage"] into every section).
    overall = _summary(items=[_item(item_id="g1")])
    result = email_render.render_brand_digest(
        overall, {"guru": _section(items=[_item(item_id="g1", title="Guru Post")])},
        "2026-08-15")
    assert "Guru Post" in result["text"]
    assert "Scanned 3 handle(s)" in result["text"]


def test_render_brand_digest_refuses_an_overall_missing_a_run_level_key():
    # The guard has to live here too: production calls render_brand_digest, never
    # render_email, so a guard only on render_email protects nothing real.
    for key in ("coverage", "skips", "duplicates", "mismatches"):
        overall = _summary()
        del overall[key]
        with pytest.raises(KeyError, match=key):
            email_render.render_brand_digest(overall, {}, "2026-08-15")


def test_render_brand_digest_puts_the_coverage_footer_on_the_empty_email_too():
    result = email_render.render_brand_digest(_summary(), {}, "2026-08-15")
    assert "No new content today." in result["text"]
    assert "Scanned 3 handle(s)" in result["text"]
    assert "Scanned 3 handle(s)" in result["html"]


def test_every_accepted_platform_has_a_rank_and_a_label():
    platforms = _schema_platforms()
    assert platforms, "the CHECK constraint parsed to an empty vocabulary"
    assert platforms - set(email_render.PLATFORM_ORDER) == set()
    assert platforms - set(email_render.PLATFORM_LABELS) == set()
    assert set(email_render.PLATFORM_ORDER) == set(email_render.PLATFORM_LABELS)
