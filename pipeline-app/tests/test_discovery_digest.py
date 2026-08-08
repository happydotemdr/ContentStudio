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
