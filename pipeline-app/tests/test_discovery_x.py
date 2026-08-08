from pipeline_app import discovery_x as x


def test_parse_published_accepts_the_verified_iso_format():
    """Live X rows carry real ISO 8601 UTC -- 2026-08-08T01:11:45.000Z
    (verified 2026-08-08, snapshot sd_mskd8iv12ivrnbejlz). This matches
    LinkedIn and differs from the Instagram product's US-format local
    timestamp; three Bright Data datasets, two date formats, so none may be
    assumed from another."""
    assert x._parse_published("2026-08-08T01:11:45.000Z") == "2026-08-08"
    assert x._parse_published("2026-08-08") == "2026-08-08"


def test_parse_published_rejects_unusable_values():
    assert x._parse_published("") is None
    assert x._parse_published(None) is None
    assert x._parse_published("not a date") is None
    # A US-format date is NOT silently reinterpreted -- guessing between
    # MM/DD and DD/MM produces wrong dates, which is worse than a dropped
    # row, and dropped rows are counted and logged.
    assert x._parse_published("08/08/2026 01:11:45") is None


def _raw_row(**overrides):
    """A row shaped like the live payload from snapshot sd_mskd8iv12ivrnbejlz."""
    row = {
        "id": "2085896713185714235",
        "date_posted": "2026-08-08T01:11:45.000Z",
        "user_posted": "CNN",
        "name": "CNN",
        "user_id": "759251",
        "description": "A daring mission to rescue one of NASA's observatories.",
        "url": "https://twitter.com/759251/status/2085896713185714235",
        "is_repost": False,
        "likes": 310,
        "replies": 85,
        "reposts": 64,
        "views": 214564,
        "bookmarks": 16,
        "quotes": 6,
        "hashtags": None,
        "photos": ["https://pbs.twimg.com/media/HPKX_XjXUAAxkvS.jpg"],
        "videos": None,
        "external_url": "https://cnn.it/45aXVbJ",
    }
    row.update(overrides)
    return row


def test_normalize_row_maps_every_verified_field():
    n = x._normalize_row(_raw_row())
    assert n["id"] == "2085896713185714235"
    assert n["published"] == "2026-08-08"
    assert n["author"] == "CNN"
    assert n["body"].startswith("A daring mission")
    assert n["like_count"] == 310
    assert n["comment_count"] == 85       # from `replies`
    assert n["repost_count"] == 64
    assert n["view_count"] == 214564
    assert n["bookmark_count"] == 16
    assert n["quote_count"] == 6
    assert n["photos"] == ["https://pbs.twimg.com/media/HPKX_XjXUAAxkvS.jpg"]
    assert n["external_url"] == "https://cnn.it/45aXVbJ"


def test_normalize_row_keeps_media_only_posts_with_an_empty_body():
    """3 of 10 live elonmusk rows had description: null -- media-only posts
    (snapshot sd_mskdghugb6u3685n6). These are KEPT, not dropped: the row
    still carries a date, six engagement counts and the media URLs, and
    dropping them would pay for rows it discards on a video-heavy account."""
    n = x._normalize_row(_raw_row(description=None, photos=None,
                                  videos=[{"video_url": "https://video.twimg.com/a.mp4",
                                           "duration": 6041}]))
    assert n is not None
    assert n["body"] == ""
    assert n["videos"] == ["https://video.twimg.com/a.mp4"]


def test_normalize_row_flattens_the_videos_struct_list_to_urls():
    """videos is a list of structs carrying video_url and duration (verified
    live). Storing the raw structs would put duration integers in the
    frontmatter; only the URL is wanted."""
    n = x._normalize_row(_raw_row(videos=[
        {"video_url": "https://video.twimg.com/a.mp4", "duration": 6041},
        {"video_url": "https://video.twimg.com/b.mp4", "duration": 3761157},
    ]))
    assert n["videos"] == ["https://video.twimg.com/a.mp4",
                           "https://video.twimg.com/b.mp4"]


def test_normalize_row_title_is_the_first_line_then_falls_back_to_id():
    n = x._normalize_row(_raw_row(description="First line.\nSecond line."))
    assert n["title"] == "First line."
    media_only = x._normalize_row(_raw_row(description=None))
    assert media_only["title"] == "2085896713185714235"


def test_normalize_row_truncates_title_to_60_chars():
    n = x._normalize_row(_raw_row(description="y" * 100))
    assert n["title"] == "y" * 60


def test_normalize_row_drops_rows_with_no_id_or_unusable_date():
    assert x._normalize_row(_raw_row(id=None)) is None
    assert x._normalize_row(_raw_row(id="")) is None
    assert x._normalize_row(_raw_row(date_posted="nonsense")) is None
    assert x._normalize_row(_raw_row(date_posted=None)) is None


def test_normalize_row_drops_the_include_errors_error_row():
    """include_errors=true yields rows carrying error/error_code with every
    content field null (verified live, snapshot sd_mskdls3f26klcqyxk9:
    error_code 'dead_page'). They have no id, so the id guard discards them
    with no special-casing -- pin that, so a future 'helpful' fallback that
    invents an id from the url does not resurrect them."""
    error_row = {"error": "No public posts were found in the profile for the "
                          "specified period.",
                 "error_code": "dead_page",
                 "timestamp": "2026-08-08T12:56:25.349Z"}
    assert x._normalize_row(error_row) is None


def test_normalize_row_keeps_the_full_timestamp_as_a_separate_sort_key():
    """'published' truncates to the date, so same-day rows need the time of
    day to sort correctly. Rows arrive unsorted (verified live)."""
    n = x._normalize_row(_raw_row())
    assert n["published_ts"] == "2026-08-08T01:11:45.000Z"


def test_normalize_row_coerces_missing_list_fields_to_empty_lists():
    """hashtags/photos/videos come back as null, not [], on most rows.
    yaml.safe_dump renders None as 'null'; an empty list is the honest shape."""
    n = x._normalize_row(_raw_row(hashtags=None, photos=None, videos=None))
    assert n["hashtags"] == []
    assert n["photos"] == []
    assert n["videos"] == []
