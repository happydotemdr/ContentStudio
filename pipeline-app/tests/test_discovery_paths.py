from pathlib import Path

from pipeline_app.discovery_paths import handle_dir, run_record_path, slugify


def test_slugify_basic():
    assert slugify("Romayroh") == "romayroh"
    assert slugify("@FutureTechPilot") == "futuretechpilot"
    assert slugify("Some Title: With Punctuation!") == "some-title-with-punctuation"


def test_handle_dir_youtube(tmp_path: Path):
    result = handle_dir(tmp_path, "youtube", "@Romayroh")
    assert result == tmp_path / "output" / "brand-intel" / "youtube" / "romayroh"


def test_handle_dir_bluesky(tmp_path: Path):
    result = handle_dir(tmp_path, "bluesky", "adamgrant.bsky.social")
    # slugify strips '.' entirely (not in \w, not whitespace, not '-') rather
    # than replacing it with a hyphen -- "adamgrant.bsky.social" collapses to
    # one run-on word. Verified against the actual regex, not assumed.
    assert result == tmp_path / "output" / "brand-intel" / "bluesky" / "adamgrantbskysocial"


def test_run_record_path(tmp_path: Path):
    result = run_record_path(tmp_path, "2026-07-30T06-00-00-0500")
    assert result == tmp_path / "output" / "discovery-runs" / "2026-07-30T06-00-00-0500.md"
