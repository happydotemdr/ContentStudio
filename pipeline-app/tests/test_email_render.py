from pipeline_app import email_render


def _item(platform="youtube", handle="chan", display_name="Some Channel", item_id="vid1",
          title="How To Actually Finish A Video", url="https://youtu.be/vid1",
          published="2026-08-07", views=41203, likes=1890, comments=None,
          body="So the first thing nobody tells you is that finishing is a skill."):
    return {"platform": platform, "handle": handle, "display_name": display_name,
            "item_id": item_id, "title": title, "url": url, "published": published,
            "views": views, "likes": likes, "comments": comments, "body": body}


def _summary(items=None, spotlight=None, drafts=None, errored=None,
             run_status="completed", has_issues=False):
    return {"run_status": run_status, "has_issues": has_issues,
            "items": items if items is not None else [],
            "errored": errored if errored is not None else [],
            "spotlight": spotlight, "drafts": drafts if drafts is not None else []}


def test_subject_counts_posts_not_videos():
    result = email_render.render_email(_summary(items=[_item(), _item(item_id="vid2")]), "2026-08-08")
    assert result["subject"] == "ContentStudio Discovery 2026-08-08: 2 new post(s)"


def test_no_new_content_body():
    result = email_render.render_email(_summary(), "2026-08-08")
    assert result["subject"] == "ContentStudio Discovery 2026-08-08: 0 new post(s)"
    assert result["text"] == "No new content today."
    assert "No new content today." in result["html"]


def test_issue_prefixes_subject_and_opens_body_with_run_status():
    summary = _summary(run_status="failed", has_issues=True)
    result = email_render.render_email(summary, "2026-08-08")
    assert result["subject"].startswith("[ISSUE] ")
    assert result["text"].startswith("Run status: failed")
    assert "Run status: failed" in result["html"]


def test_errors_section_lists_handle_names():
    summary = _summary(errored=["@dead-handle"], has_issues=True)
    result = email_render.render_email(summary, "2026-08-08")
    assert "@dead-handle" in result["text"]
    assert "@dead-handle" in result["html"]


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
    result = email_render.render_email(_summary(items=[spot], spotlight=spot, drafts=drafts),
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
    result = email_render.render_email(_summary(items=[spot], spotlight=spot, drafts=[]),
                                       "2026-08-08")
    assert "unavailable" in result["text"].lower()
    assert "How To Actually Finish A Video" in result["html"]


def test_spotlight_item_still_appears_in_the_inventory_with_a_marker():
    spot = _item()
    result = email_render.render_email(
        _summary(items=[spot], spotlight=spot, drafts=[]), "2026-08-08")
    assert result["text"].count("How To Actually Finish A Video") >= 2
    assert "featured above" in result["text"]


def test_unknown_platform_sorts_last_with_a_titlecased_label():
    known = _item(platform="youtube")
    unknown = _item(platform="threads", handle="t", display_name="T", item_id="th1",
                    title="A Threads Post", url="https://example.com/t")
    result = email_render.render_email(_summary(items=[unknown, known]), "2026-08-08")
    assert "Threads" in result["text"]
    assert result["text"].index("YouTube") < result["text"].index("Threads")


def test_missing_url_renders_the_entry_without_a_link():
    result = email_render.render_email(_summary(items=[_item(url=None)]), "2026-08-08")
    assert "How To Actually Finish A Video" in result["text"]
    assert "Click here to view" not in result["html"]


def test_non_http_url_never_becomes_an_anchor():
    result = email_render.render_email(
        _summary(items=[_item(url="javascript:alert(1)")]), "2026-08-08")
    assert "javascript:" not in result["html"]
    assert "Click here to view" not in result["html"]


def test_html_escapes_untrusted_title_and_excerpt():
    spot = _item(title='A <script>alert("x")</script> & more',
                 body='Body with <b>tags</b> & "quotes".')
    result = email_render.render_email(_summary(items=[spot], spotlight=spot), "2026-08-08")
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
        _summary(items=[], spotlight=spot, drafts=drafts), "2026-08-08")
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
