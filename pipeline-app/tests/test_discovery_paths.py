from pathlib import Path

from pipeline_app.discovery_paths import (
    find_slug_collision,
    group_slug_collisions,
    handle_dir,
    handle_slug,
    run_owner_path,
    run_record_path,
    slugify,
    spawn_log_path,
)


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


def test_slugify_mapping_for_existing_handles_is_frozen():
    """Load-bearing, not cosmetic: output/brand-intel/bluesky/adamgrantbskysocial
    already holds captured content. Any change to this mapping repoints the
    handle at a new directory, on_disk_ids() returns an empty set, and the engine
    re-downloads and re-pays for the entire back-catalogue. The collision fix
    therefore GUARDS this mapping rather than changing it."""
    assert slugify("adamgrant.bsky.social") == "adamgrantbskysocial"
    assert slugify("@FutureTechPilot") == "futuretechpilot"
    assert handle_dir(Path("/r"), "bluesky", "adamgrant.bsky.social").name == "adamgrantbskysocial"


def test_handle_slug_is_the_component_handle_dir_actually_uses():
    """handle_slug must BE the path component, not a parallel reimplementation of
    it. A guard computing the slug even slightly differently from handle_dir would
    report no collision while two handles still shared a directory."""
    for handle in ("@Romayroh", "adamgrant.bsky.social", "john.doe.5", "NASA", "a b"):
        assert handle_dir(Path("/r"), "facebook", handle).name == handle_slug(handle)


def test_handle_slug_strips_a_leading_at_like_handle_dir_does():
    assert handle_slug("@NASA") == "nasa"
    assert handle_slug("NASA") == "nasa"


def test_find_slug_collision_catches_punctuation_only_differences():
    """Facebook vanity slugs commonly carry periods and slugify strips them, so
    two distinct registered handles land in one directory."""
    assert find_slug_collision("john.doe.5", ["johndoe5"]) == "johndoe5"
    assert (find_slug_collision("adam.grant.bsky.social", ["adamgrant.bsky.social"])
            == "adamgrant.bsky.social")


def test_find_slug_collision_catches_case_and_separator_differences():
    assert find_slug_collision("nasa", ["NASA"]) == "NASA"
    assert find_slug_collision("john-doe", ["john_doe"]) == "john_doe"


def test_find_slug_collision_catches_truncation_past_the_length_cap():
    """slugify truncates at 80 characters, so two long handles differing only
    past the cap share a directory."""
    other = "a" * 85 + "Y"
    assert find_slug_collision("a" * 85 + "X", [other]) == other


def test_find_slug_collision_ignores_an_exact_repeat_of_the_same_handle():
    """An exact duplicate is a different error with its own message (the route's
    own check, backed by UNIQUE(platform, handle)). This function reports only
    handles that DIFFER as strings yet share a directory."""
    assert find_slug_collision("NASA", ["NASA"]) is None
    assert find_slug_collision("@NASA", ["@NASA", "other"]) is None


def test_find_slug_collision_returns_none_when_slugs_are_distinct():
    assert find_slug_collision("nasa", ["spacex", "esa"]) is None
    assert find_slug_collision("nasa", []) is None


def test_find_slug_collision_reports_the_first_colliding_handle():
    assert find_slug_collision("na.sa", ["esa", "NASA", "nasa"]) == "NASA"


def test_group_slug_collisions_returns_only_groups_of_two_or_more():
    assert group_slug_collisions(["NASA", "nasa", "spacex"]) == {"nasa": ["NASA", "nasa"]}


def test_group_slug_collisions_groups_a_three_way_collision():
    assert group_slug_collisions(["john.doe.5", "johndoe5", "JohnDoe5"]) == {
        "johndoe5": ["john.doe.5", "johndoe5", "JohnDoe5"],
    }


def test_group_slug_collisions_is_empty_when_every_slug_is_unique():
    assert group_slug_collisions(["nasa", "spacex", "esa"]) == {}
    assert group_slug_collisions([]) == {}


def test_group_slug_collisions_does_not_report_an_exactly_repeated_handle():
    """A repeated identical string cannot happen per platform (UNIQUE constraint)
    and is not a directory collision between two accounts -- it is one account."""
    assert group_slug_collisions(["NASA", "NASA"]) == {}


def test_run_owner_path_is_namespaced_and_does_not_collide_with_run_records(tmp_path: Path):
    assert run_owner_path(tmp_path, 7) == tmp_path / "output" / "discovery-runs" / ".owners" / "7.json"


def test_spawn_log_path_is_namespaced_under_discovery_runs(tmp_path: Path):
    assert (spawn_log_path(tmp_path, "abc123")
            == tmp_path / "output" / "discovery-runs" / "spawn-logs" / "abc123.log")
