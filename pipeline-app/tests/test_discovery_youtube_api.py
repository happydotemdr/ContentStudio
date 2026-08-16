import json
import urllib.error

import pytest

from pipeline_app import discovery_youtube_api as api


@pytest.fixture
def logged(monkeypatch):
    """Captures every api.obs.log() call this test makes, as a list of dicts.

    Each record is {"event": ..., "level": ..., **fields} -- the same shape
    obs.log() takes, minus the timestamp obs.log() would otherwise stamp.
    """
    records: list[dict] = []

    def fake_log(event, *, level="info", **fields):
        records.append({"event": event, "level": level, **fields})

    monkeypatch.setattr(api.obs, "log", fake_log)
    return records


# --------------------------------------------------------------------------- #
# key resolution

def test_api_key_prefers_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv(api.KEY_ENV_VAR, "env-key")
    key_file = tmp_path / "youtube_api_key.txt"
    key_file.write_text("file-key", encoding="utf-8")
    monkeypatch.setattr(api, "KEY_FILE", key_file)
    assert api.api_key() == "env-key"


def test_api_key_falls_back_to_file(monkeypatch, tmp_path):
    monkeypatch.delenv(api.KEY_ENV_VAR, raising=False)
    key_file = tmp_path / "youtube_api_key.txt"
    key_file.write_text("  file-key\n", encoding="utf-8")
    monkeypatch.setattr(api, "KEY_FILE", key_file)
    assert api.api_key() == "file-key"


def test_api_key_none_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv(api.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(api, "KEY_FILE", tmp_path / "absent.txt")
    assert api.api_key() is None


def test_api_key_ignores_empty_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv(api.KEY_ENV_VAR, "   ")
    monkeypatch.setattr(api, "KEY_FILE", tmp_path / "absent.txt")
    assert api.api_key() is None


# --------------------------------------------------------------------------- #
# ISO-8601 duration parsing

@pytest.mark.parametrize("iso,expected", [
    ("PT4M13S", 253),
    ("PT1H2M3S", 3723),
    ("PT45S", 45),
    ("PT2H", 7200),
    ("P1DT2H", 93600),
    ("P0D", 0),          # live / upcoming broadcasts
    ("", None),
    (None, None),
    ("garbage", None),
])
def test_parse_duration(iso, expected):
    assert api.parse_duration(iso) == expected


# --------------------------------------------------------------------------- #
# normalization

def _api_item(**overrides):
    item = {
        "id": "vid1",
        "snippet": {
            "title": "A Title",
            "channelTitle": "A Channel",
            "description": "Body text",
            "publishedAt": "2025-08-16T14:03:11Z",
            "tags": ["x", "y"],
        },
        "contentDetails": {"duration": "PT7M21S", "caption": "true"},
        "statistics": {"viewCount": "24013", "likeCount": "1184", "commentCount": "97"},
    }
    item.update(overrides)
    return item


def test_normalize_maps_all_fields():
    rec = api._normalize(_api_item())
    assert rec["title"] == "A Title"
    assert rec["channel"] == "A Channel"
    assert rec["upload_date"] == "2025-08-16"
    assert rec["duration_s"] == 441
    assert rec["view_count"] == 24013
    assert rec["like_count"] == 1184
    assert rec["comment_count"] == 97
    assert rec["manual_captions"] is True
    assert rec["tags"] == ["x", "y"]


def test_normalize_caption_false_is_false_not_none():
    rec = api._normalize(_api_item(contentDetails={"duration": "PT1M", "caption": "false"}))
    assert rec["manual_captions"] is False


def test_normalize_caption_absent_is_unknown():
    rec = api._normalize(_api_item(contentDetails={"duration": "PT1M"}))
    assert rec["manual_captions"] is None


def test_normalize_hidden_like_count_is_none_not_zero():
    # Uploaders can hide likes; the field is then omitted entirely. Absent must
    # not be recorded as a real count of 0.
    rec = api._normalize(_api_item(statistics={"viewCount": "10"}))
    assert rec["view_count"] == 10
    assert rec["like_count"] is None


# --------------------------------------------------------------------------- #
# fetch_metadata

def test_no_key_warning_is_printed_once_per_process(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv(api.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(api, "KEY_FILE", tmp_path / "absent.txt")
    monkeypatch.setattr(api, "_NO_KEY_WARNED", False)
    for _ in range(50):
        api.fetch_metadata(["v1"])
    assert capsys.readouterr().err.count("no YouTube Data API key") == 1


def test_fetch_metadata_returns_empty_without_key(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv(api.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(api, "KEY_FILE", tmp_path / "absent.txt")
    monkeypatch.setattr(api, "_NO_KEY_WARNED", False)
    assert api.fetch_metadata(["v1"]) == {}
    assert "no YouTube Data API key" in capsys.readouterr().err


def test_fetch_metadata_keys_result_by_video_id(monkeypatch):
    monkeypatch.setattr(api, "_http_get_json",
                        lambda url: {"items": [_api_item(id="v1"), _api_item(id="v2")]})
    out = api.fetch_metadata(["v1", "v2"], key="k")
    assert set(out) == {"v1", "v2"}
    assert out["v1"]["upload_date"] == "2025-08-16"


def test_fetch_metadata_batches_at_50(monkeypatch):
    calls = []

    def fake_get(url):
        calls.append(url)
        return {"items": []}

    monkeypatch.setattr(api, "_http_get_json", fake_get)
    api.fetch_metadata([f"v{i}" for i in range(120)], key="k")
    assert len(calls) == 3  # 50 + 50 + 20


def test_fetch_metadata_dedupes_ids(monkeypatch):
    seen = []

    def fake_get(url):
        seen.append(url)
        return {"items": []}

    monkeypatch.setattr(api, "_http_get_json", fake_get)
    api.fetch_metadata(["v1", "v1", "v1"], key="k")
    assert len(seen) == 1
    assert seen[0].count("v1") == 1


def test_fetch_metadata_omits_ids_the_api_did_not_return(monkeypatch):
    # deleted/private videos simply do not come back in items
    monkeypatch.setattr(api, "_http_get_json", lambda url: {"items": [_api_item(id="v1")]})
    out = api.fetch_metadata(["v1", "deleted_video"], key="k")
    assert set(out) == {"v1"}


def test_fetch_metadata_survives_a_failed_batch(monkeypatch):
    responses = [None, {"items": [_api_item(id="v99")]}]
    monkeypatch.setattr(api, "_http_get_json", lambda url: responses.pop(0))
    out = api.fetch_metadata([f"v{i}" for i in range(60)], key="k")
    # first batch failed, second still landed
    assert set(out) == {"v99"}


def test_http_get_json_reports_403_quota(monkeypatch, capsys):
    def raise_403(url, timeout):
        raise urllib.error.HTTPError(
            url, 403, "Forbidden", {},
            __import__("io").BytesIO(json.dumps(
                {"error": {"message": "quotaExceeded"}}).encode()),
        )

    monkeypatch.setattr(api.urllib.request, "urlopen", raise_403)
    assert api._http_get_json("https://example.test") is None
    assert "403" in capsys.readouterr().err


def test_fetch_one_returns_single_record(monkeypatch):
    monkeypatch.setattr(api, "_http_get_json", lambda url: {"items": [_api_item(id="v1")]})
    assert api.fetch_one("v1", key="k")["title"] == "A Title"


def test_fetch_one_none_when_absent(monkeypatch):
    monkeypatch.setattr(api, "_http_get_json", lambda url: {"items": []})
    assert api.fetch_one("gone", key="k") is None


def test_manual_captions_is_not_a_transcript_availability_signal():
    """Locks in a measured fact, not an assumption.

    Against this repo's corpus on 2026-07-30, 388 of the 411 videos we hold a
    transcript for reported contentDetails.caption == "false" -- the field
    tracks manually-uploaded caption tracks only, and auto-generated (ASR)
    captions report false. The field name must therefore never imply general
    caption availability, or downstream triage will discard fetchable videos.
    """
    rec = api._normalize(_api_item(contentDetails={"duration": "PT1M", "caption": "false"}))
    assert "captions_available" not in rec, (
        "field must not be named captions_available -- false does not mean "
        "no transcript is obtainable"
    )
    assert rec["manual_captions"] is False


# --------------------------------------------------------------------------- #
# fetch_upload_dates

def test_fetch_upload_dates_reports_a_missing_key_instead_of_returning_silently(
        monkeypatch, tmp_path, logged):
    monkeypatch.delenv(api.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(api, "KEY_FILE", tmp_path / "absent.txt")
    monkeypatch.setattr(api, "_NO_KEY_WARNED", False)
    assert api.fetch_upload_dates(["v1"]) == {}
    (record,) = [r for r in logged if r["event"] == "adapter.api_key_missing"]
    assert record["level"] == "warning" and record["caller"] == "fetch_upload_dates"


def test_fetch_upload_dates_maps_ids_to_dates(monkeypatch):
    monkeypatch.setattr(api, "_http_get_json",
                        lambda url, key=None: {"items": [_api_item(id="v1"), _api_item(id="v2")]})
    assert api.fetch_upload_dates(["v1", "v2"], key="k") == {
        "v1": "2025-08-16", "v2": "2025-08-16"}


def test_fetch_upload_dates_batches_at_50(monkeypatch):
    calls = []
    monkeypatch.setattr(api, "_http_get_json",
                        lambda url, key=None: calls.append(url) or {"items": []})
    api.fetch_upload_dates([f"v{i}" for i in range(120)], key="k")
    assert len(calls) == 3


def test_fetch_upload_dates_omits_ids_with_a_malformed_publishedAt(monkeypatch):
    monkeypatch.setattr(api, "_http_get_json", lambda url, key=None: {"items": [
        {"id": "good", "snippet": {"publishedAt": "2026-07-01T00:00:00Z"}},
        {"id": "short", "snippet": {"publishedAt": "2026"}},
        {"id": "none", "snippet": {}},
    ]})
    assert api.fetch_upload_dates(["good", "short", "none"], key="k") == {"good": "2026-07-01"}


def test_fetch_upload_dates_survives_a_failed_batch(monkeypatch):
    responses = [None, {"items": [{"id": "v99", "snippet": {"publishedAt": "2026-07-01T00:00:00Z"}}]}]
    monkeypatch.setattr(api, "_http_get_json", lambda url, key=None: responses.pop(0))
    assert api.fetch_upload_dates([f"v{i}" for i in range(60)], key="k") == {"v99": "2026-07-01"}
