from pipeline_app import discovery_digest as digest

YOUTUBE_BODY = (
    "# How To Actually Finish A Video\n\n"
    "## description\n\nSubscribe for more.\n\n"
    "## transcript\n\nSo the first thing nobody tells you is that finishing is a skill.\n"
)


def test_derive_title_reads_h1():
    assert digest.derive_title(YOUTUBE_BODY, "fallback") == "How To Actually Finish A Video"


def test_derive_title_treats_leading_hashtag_as_text_not_heading():
    body = "#MondayMotivation the only rep that counts is the one you did not want to do"
    title = digest.derive_title(body, "fallback")
    assert title.startswith("#MondayMotivation")


def test_derive_title_truncates_long_first_line_at_word_boundary():
    body = "word " * 60
    title = digest.derive_title(body, "fallback")
    assert len(title) <= 90
    assert not title.endswith("wor")


def test_derive_title_falls_back_on_empty_body():
    assert digest.derive_title("   \n\n  ", "vid1__some-slug") == "vid1__some-slug"


def test_extract_primary_text_prefers_transcript_over_description():
    text = digest.extract_primary_text(YOUTUBE_BODY)
    assert text.startswith("So the first thing")
    assert "## description" not in text
    assert "Subscribe for more" not in text


def test_extract_primary_text_falls_back_to_description_when_transcript_is_placeholder():
    body = (
        "# Title\n\n## description\n\nThe real description.\n\n"
        "## transcript\n\n(no transcript available)\n"
    )
    assert digest.extract_primary_text(body) == "The real description."


def test_extract_primary_text_returns_empty_when_all_sections_are_placeholders():
    body = "# Title\n\n## description\n\n(none)\n\n## transcript\n\n(no transcript available)\n"
    assert digest.extract_primary_text(body) == ""


def test_extract_primary_text_passes_flat_body_through():
    body = "We keep telling founders to move fast.\n\nBut the teams that shipped did not."
    text = digest.extract_primary_text(body)
    assert text.startswith("We keep telling founders")
    assert "But the teams that shipped" in text


def test_extract_primary_text_keeps_leading_hashtag_line():
    body = "#MondayMotivation the only rep that counts.\n\nMore text."
    assert digest.extract_primary_text(body).startswith("#MondayMotivation")


def test_extract_primary_text_treats_bare_empty_placeholder_as_empty():
    assert digest.extract_primary_text("(empty)") == ""


def test_published_rank_orders_newest_first_with_missing_last():
    ranks = [digest.published_rank(p) for p in ("2026-08-01", "2026-08-07", None)]
    assert ranks[1] < ranks[0] < ranks[2]


import os

from pipeline_app import discovery_paths

RUN_START = "2026-08-01T06:00:00+00:00"


def _write(repo_root, platform, handle, name, meta_lines, body):
    out = discovery_paths.handle_dir(repo_root, platform, handle)
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    path.write_text("---\n" + "\n".join(meta_lines) + "\n---\n\n" + body, encoding="utf-8")
    return path


def _handle_row(platform="linkedin-profile", handle="bettywliu", display_name="Betty Liu"):
    return {"platform": platform, "handle": handle, "display_name": display_name}


def test_collect_new_items_normalizes_a_linkedin_post(tmp_path):
    _write(tmp_path, "linkedin-profile", "bettywliu", "7358.md", [
        "url: 'https://www.linkedin.com/posts/7358'",
        "published: '2026-08-07'",
        "like_count: 214",
        "comment_count: 37",
        f"fetched_at: '{RUN_START}'",
    ], "We keep telling founders to move fast.")

    items = digest.collect_new_items(tmp_path, _handle_row(), RUN_START)

    assert len(items) == 1
    item = items[0]
    assert item["platform"] == "linkedin-profile"
    assert item["handle"] == "bettywliu"
    assert item["display_name"] == "Betty Liu"
    assert item["item_id"] == "7358"
    assert item["title"] == "We keep telling founders to move fast."
    assert item["url"] == "https://www.linkedin.com/posts/7358"
    assert item["published"] == "2026-08-07"
    assert item["views"] is None
    assert item["likes"] == 214
    assert item["comments"] == 37
    assert item["body"] == "We keep telling founders to move fast."


def test_collect_new_items_excludes_file_fetched_before_the_run(tmp_path):
    _write(tmp_path, "linkedin-profile", "bettywliu", "old.md", [
        "url: 'https://example.com/old'",
        "fetched_at: '2026-07-31T06:00:00+00:00'",
    ], "Yesterday's post.")
    assert digest.collect_new_items(tmp_path, _handle_row(), RUN_START) == []


def test_collect_new_items_zero_metric_survives_as_zero_not_none(tmp_path):
    _write(tmp_path, "youtube", "@chan", "vid1__slug.md", [
        "url: 'https://youtu.be/vid1'",
        "view_count: 0",
        "like_count: 0",
        f"fetched_at: '{RUN_START}'",
    ], "# A Title\n\n## transcript\n\nWords.\n")
    item = digest.collect_new_items(tmp_path, _handle_row("youtube", "@chan", "Chan"), RUN_START)[0]
    assert item["views"] == 0
    assert item["likes"] == 0
    assert item["comments"] is None


def test_collect_new_items_falls_back_to_upload_date_for_youtube(tmp_path):
    _write(tmp_path, "youtube", "@chan", "vid1__slug.md", [
        "url: 'https://youtu.be/vid1'",
        "upload_date: '2026-08-05'",
        f"fetched_at: '{RUN_START}'",
    ], "# A Title\n\n## transcript\n\nWords.\n")
    item = digest.collect_new_items(tmp_path, _handle_row("youtube", "@chan", "Chan"), RUN_START)[0]
    assert item["published"] == "2026-08-05"


def test_collect_new_items_excludes_non_string_fetched_at(tmp_path):
    # Unquoted YAML timestamps parse to datetime; comparing one to a str raises
    # TypeError, which must be contained to this item.
    _write(tmp_path, "linkedin-profile", "bettywliu", "bad.md", [
        "url: 'https://example.com/x'",
        "fetched_at: 2026-08-01T06:01:00+00:00",
    ], "Body.")
    assert digest.collect_new_items(tmp_path, _handle_row(), RUN_START) == []


def test_collect_new_items_excludes_malformed_yaml_without_raising(tmp_path):
    out = discovery_paths.handle_dir(tmp_path, "linkedin-profile", "bettywliu")
    out.mkdir(parents=True, exist_ok=True)
    (out / "broken.md").write_text("---\n: : not yaml : :\n---\n\nBody.", encoding="utf-8")
    (out / "no-frontmatter.md").write_text("just text", encoding="utf-8")
    assert digest.collect_new_items(tmp_path, _handle_row(), RUN_START) == []


def test_collect_new_items_missing_url_yields_none_not_a_dropped_item(tmp_path):
    _write(tmp_path, "linkedin-profile", "bettywliu", "nourl.md", [
        f"fetched_at: '{RUN_START}'",
    ], "Body text here.")
    items = digest.collect_new_items(tmp_path, _handle_row(), RUN_START)
    assert len(items) == 1
    assert items[0]["url"] is None


def test_collect_new_items_ignores_tmp_files_and_missing_directory(tmp_path):
    out = discovery_paths.handle_dir(tmp_path, "linkedin-profile", "bettywliu")
    out.mkdir(parents=True, exist_ok=True)
    (out / "partial.md.tmp").write_text("---\nurl: x\n---\n\nBody", encoding="utf-8")
    assert digest.collect_new_items(tmp_path, _handle_row(), RUN_START) == []
    assert digest.collect_new_items(tmp_path, _handle_row(handle="nobody"), RUN_START) == []


def test_mtime_prefilter_skips_old_files_but_is_never_the_authority(tmp_path):
    # Old mtime + fresh fetched_at: the pre-filter skips it. It is an
    # optimization, so this is a deliberate, documented consequence.
    stale = _write(tmp_path, "linkedin-profile", "bettywliu", "stale.md", [
        "url: 'https://example.com/a'", f"fetched_at: '{RUN_START}'",
    ], "Body.")
    os.utime(stale, (1_600_000_000, 1_600_000_000))

    # Fresh mtime + old fetched_at: the watermark rejects it anyway, proving
    # the pre-filter cannot admit anything on its own.
    _write(tmp_path, "linkedin-profile", "bettywliu", "touched.md", [
        "url: 'https://example.com/b'", "fetched_at: '2026-07-01T00:00:00+00:00'",
    ], "Body.")

    assert digest.collect_new_items(tmp_path, _handle_row(), RUN_START) == []


def test_mtime_prefilter_disabled_when_run_started_at_is_unparseable(tmp_path):
    # Fail open: a bad run timestamp must not silently hide every item.
    stale = _write(tmp_path, "linkedin-profile", "bettywliu", "x.md", [
        "url: 'https://example.com/a'", "fetched_at: 'zzz'",
    ], "Body.")
    os.utime(stale, (1_600_000_000, 1_600_000_000))
    # 'zzz' >= 'not-a-timestamp' lexicographically, so the watermark admits it
    # only because the pre-filter was skipped entirely.
    items = digest.collect_new_items(tmp_path, _handle_row(), "not-a-timestamp")
    assert len(items) == 1


def _item(platform="youtube", handle="h", item_id="i", likes=0, comments=0,
          views=0, published="2026-08-01", body="Some body text.", display_name="D"):
    return {"platform": platform, "handle": handle, "display_name": display_name,
            "item_id": item_id, "title": "T", "url": "https://example.com/x",
            "published": published, "views": views, "likes": likes,
            "comments": comments, "body": body}


def test_select_spotlight_returns_none_for_empty_input():
    assert digest.select_spotlight([]) is None


def test_select_spotlight_linkedin_beats_a_far_bigger_youtube_item():
    linkedin = _item(platform="linkedin-profile", item_id="li", likes=3, views=None)
    youtube = _item(platform="youtube", item_id="yt", likes=40000, views=1_000_000)
    assert digest.select_spotlight([youtube, linkedin])["item_id"] == "li"


def test_select_spotlight_treats_both_linkedin_modes_as_eligible():
    company = _item(platform="linkedin-company", item_id="co", likes=90)
    profile = _item(platform="linkedin-profile", item_id="pr", likes=10)
    assert digest.select_spotlight([profile, company])["item_id"] == "co"


def test_select_spotlight_ranks_by_likes_plus_comments():
    a = _item(item_id="a", likes=100, comments=0)
    b = _item(item_id="b", likes=60, comments=50)
    assert digest.select_spotlight([a, b])["item_id"] == "b"


def test_select_spotlight_breaks_interaction_tie_on_views():
    a = _item(item_id="a", likes=10, views=5)
    b = _item(item_id="b", likes=10, views=500)
    assert digest.select_spotlight([a, b])["item_id"] == "b"


def test_select_spotlight_breaks_view_tie_on_newest_published():
    a = _item(item_id="a", published="2026-08-01")
    b = _item(item_id="b", published="2026-08-07")
    assert digest.select_spotlight([a, b])["item_id"] == "b"


def test_select_spotlight_sorts_missing_published_last():
    a = _item(item_id="a", published=None)
    b = _item(item_id="b", published="2026-01-01")
    assert digest.select_spotlight([a, b])["item_id"] == "b"


def test_select_spotlight_key_is_total_across_same_stem_on_different_handles():
    a = _item(handle="alpha", item_id="same")
    b = _item(handle="beta", item_id="same")
    assert digest.select_spotlight([b, a])["handle"] == "alpha"
    assert digest.select_spotlight([a, b])["handle"] == "alpha"


def test_select_spotlight_all_zero_metrics_resolves_to_newest():
    a = _item(platform="bluesky", item_id="a", likes=None, comments=None,
              views=None, published="2026-08-01")
    b = _item(platform="bluesky", item_id="b", likes=None, comments=None,
              views=None, published="2026-08-06")
    assert digest.select_spotlight([a, b])["item_id"] == "b"


def test_select_spotlight_excludes_empty_bodied_items():
    linkedin = _item(platform="linkedin-profile", item_id="li", likes=500, body="")
    youtube = _item(platform="youtube", item_id="yt", likes=1)
    assert digest.select_spotlight([linkedin, youtube])["item_id"] == "yt"


def test_select_spotlight_returns_none_when_every_item_is_empty_bodied():
    assert digest.select_spotlight([_item(body=""), _item(item_id="b", body="")]) is None
