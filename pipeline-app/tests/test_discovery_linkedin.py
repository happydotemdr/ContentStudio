from pipeline_app import discovery_linkedin as li


def test_parse_published_accepts_the_verified_iso_format():
    """Live LinkedIn rows carry real ISO 8601 UTC -- 2026-07-08T14:00:09.491Z
    (verified 2026-08-07). Note this DIFFERS from the Instagram product, which
    returns a US-format local timestamp; the two Bright Data datasets do not
    agree, which is why neither may be assumed from the other."""
    assert li._parse_published("2026-07-08T14:00:09.491Z") == "2026-07-08"
    assert li._parse_published("2026-07-08") == "2026-07-08"


def test_parse_published_rejects_unusable_values():
    assert li._parse_published("") is None
    assert li._parse_published(None) is None
    assert li._parse_published("not a date") is None
    # A US-format date is NOT silently reinterpreted -- guessing between
    # MM/DD and DD/MM would produce wrong dates, which is worse than a
    # dropped row, and dropped rows are logged.
    assert li._parse_published("07/08/2026 14:00:09") is None


def _raw_row(**overrides):
    """A row shaped like the live payload from snapshot sd_msizuwoz1sxczzt49."""
    row = {
        "id": "7480621754537701376",
        "date_posted": "2026-07-08T14:00:09.491Z",
        "post_type": "post",
        "account_type": "Person",
        "user_id": "bettywliu",
        "user_name": "Betty Liu",
        "headline": "Your personal brand isn't your resume.",
        "title": "#personalbrand #leadership #careeradvice | Betty Liu",
        "post_text": "Your personal brand isn't your resume.\n\nIt's what people say.",
        "original_post_text": "Your personal brand isn&apos;t your resume.",
        "post_text_html": "<a class=\"link\">markup</a>",
        "url": "https://www.linkedin.com/posts/bettywliu_personalbrand-activity-748",
        "num_likes": 74,
        "num_comments": 9,
        "hashtags": ["#personalbrand", "#leadership"],
    }
    row.update(overrides)
    return row


def test_normalize_row_maps_every_verified_field():
    n = li._normalize_row(_raw_row())
    assert n["id"] == "7480621754537701376"
    assert n["published"] == "2026-07-08"
    assert n["content_type"] == "post"
    assert n["account_type"] == "person"
    assert n["author"] == "bettywliu"
    assert n["like_count"] == 74
    assert n["comment_count"] == 9
    assert n["hashtags"] == ["#personalbrand", "#leadership"]


def test_normalize_row_body_comes_from_post_text_not_the_markup_fields():
    """post_text is the clean body -- entities decoded, links flattened.
    original_post_text and post_text_html are LONGER but carry &apos; and
    <a class="link"> markup. Reading the longer field would quietly fill the
    corpus with HTML for posts already paid for."""
    n = li._normalize_row(_raw_row())
    assert n["body"].startswith("Your personal brand isn't your resume.")
    assert "&apos;" not in n["body"]
    assert "<a" not in n["body"]


def test_normalize_row_title_prefers_headline_over_the_seo_title_field():
    """The `title` field is SEO text with hashtags and the author appended.
    `headline` is the post's own first line."""
    n = li._normalize_row(_raw_row())
    assert n["title"] == "Your personal brand isn't your resume."
    assert "#personalbrand" not in n["title"]


def test_normalize_row_title_falls_back_to_first_line_then_id():
    no_headline = li._normalize_row(_raw_row(headline="", post_text="First line.\nSecond line."))
    assert no_headline["title"] == "First line."
    nothing = li._normalize_row(_raw_row(headline="", post_text=""))
    assert nothing["title"] == "7480621754537701376"


def test_normalize_row_truncates_title_to_60_chars():
    n = li._normalize_row(_raw_row(headline="x" * 100))
    assert n["title"] == "x" * 60


def test_normalize_row_preserves_repost_as_a_content_type():
    """post_type='repost' was observed live alongside 'post'. It is a real
    value, not an error -- do not coerce it to 'post'."""
    assert li._normalize_row(_raw_row(post_type="repost"))["content_type"] == "repost"


def test_normalize_row_lowercases_content_type_and_account_type():
    n = li._normalize_row(_raw_row(post_type="Post", account_type="Organization"))
    assert n["content_type"] == "post"
    assert n["account_type"] == "organization"


def test_normalize_row_returns_none_without_id():
    assert li._normalize_row(_raw_row(id="")) is None


def test_normalize_row_returns_none_with_unusable_date():
    assert li._normalize_row(_raw_row(date_posted="")) is None
    assert li._normalize_row(_raw_row(date_posted="garbage")) is None


def test_normalize_row_tolerates_missing_optional_fields():
    n = li._normalize_row({"id": "1", "date_posted": "2026-07-08T00:00:00.000Z"})
    assert n["body"] == ""
    assert n["author"] == ""
    assert n["hashtags"] == []
    assert n["like_count"] is None
    assert n["content_type"] == "post"
