from pathlib import Path

import pytest

from scripts.resolve_brief_version import find_latest, next_filename, parse_frontmatter


def _write(dir_: Path, name: str, version: int, extra: str = "") -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    path = dir_ / name
    path.write_text(
        f"---\ndate: 2026-07-28\nversion: {version}\n{extra}---\n\nbody\n",
        encoding="utf-8",
    )
    return path


def test_parse_frontmatter_returns_mapping():
    text = "---\nversion: 1\nkind: script\n---\n\nbody text\n"
    assert parse_frontmatter(text) == {"version": 1, "kind": "script"}


def test_parse_frontmatter_raises_on_missing_block():
    with pytest.raises(ValueError):
        parse_frontmatter("no frontmatter here\n")


def test_find_latest_returns_none_when_nothing_matches(tmp_path: Path):
    assert find_latest(tmp_path, "my-short", "script") == (None, 0)


def test_find_latest_returns_only_version(tmp_path: Path):
    p = _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    assert find_latest(tmp_path, "my-short", "script") == (p, 1)


def test_find_latest_prefers_higher_version_over_v1(tmp_path: Path):
    _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    p2 = _write(tmp_path, "2026-07-28-my-short-script-v2.md", 2)
    assert find_latest(tmp_path, "my-short", "script") == (p2, 2)


def test_find_latest_ignores_other_slugs_and_kinds(tmp_path: Path):
    _write(tmp_path, "2026-07-28-other-short-script.md", 1)
    _write(tmp_path, "2026-07-28-my-short-voiceover-brief.md", 1)
    assert find_latest(tmp_path, "my-short", "script") == (None, 0)


def test_find_latest_grounding_brief_has_no_kind(tmp_path: Path):
    p = _write(tmp_path, "2026-07-28-my-short.md", 1)
    assert find_latest(tmp_path, "my-short", None) == (p, 1)


def test_find_latest_raises_on_malformed_frontmatter(tmp_path: Path):
    tmp_path.mkdir(exist_ok=True)
    bad = tmp_path / "2026-07-28-my-short-script.md"
    bad.write_text("no frontmatter\n", encoding="utf-8")
    with pytest.raises(ValueError):
        find_latest(tmp_path, "my-short", "script")


def test_next_filename_first_write_is_v1_with_no_suffix(tmp_path: Path):
    filename, version = next_filename(tmp_path, "my-short", "script", "2026-07-28")
    assert filename == "2026-07-28-my-short-script.md"
    assert version == 1


def test_next_filename_second_write_is_v2(tmp_path: Path):
    _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    filename, version = next_filename(tmp_path, "my-short", "script", "2026-07-28")
    assert filename == "2026-07-28-my-short-script-v2.md"
    assert version == 2


def test_next_filename_grounding_brief_has_no_kind_suffix(tmp_path: Path):
    filename, version = next_filename(tmp_path, "my-topic", None, "2026-07-28")
    assert filename == "2026-07-28-my-topic.md"
    assert version == 1
