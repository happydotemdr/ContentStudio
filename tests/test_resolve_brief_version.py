import subprocess
import sys
from pathlib import Path

import pytest

from scripts.resolve_brief_version import (
    EXIT_ERROR, EXIT_NONE, EXIT_OK, find_latest, main, next_filename, parse_frontmatter,
)


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


def test_cli_prints_forward_slash_path(tmp_path: Path):
    """The CLI must print a forward-slash path even on Windows, since every skill
    copies this value verbatim into frontmatter pointer fields (script:,
    concept_brief:, supersedes:, ...), which are documented and stored as
    forward-slash paths throughout rgs-briefs/."""
    _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.resolve_brief_version",
            "--dir",
            str(tmp_path),
            "--slug",
            "my-short",
            "--kind",
            "script",
        ],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "\\" not in result.stdout
    printed_path, printed_version = result.stdout.strip().split("\t")
    assert printed_path.endswith("2026-07-28-my-short-script.md")
    assert printed_version == "1"


def test_find_latest_raises_on_a_directory_that_does_not_exist(tmp_path: Path):
    """C-96 fault test. The wrong CWD used to look exactly like an empty repo."""
    missing = tmp_path / "not-here"
    with pytest.raises(FileNotFoundError) as exc:
        find_latest(missing, "my-short", "script")
    assert str(missing) in str(exc.value)


def test_a_missing_dir_is_distinguishable_from_an_empty_one(tmp_path: Path, capsys):
    """C-96 distinguishability test. This is the whole finding: "no briefs here"
    and "I am looking in the wrong place" must not be the same answer."""
    empty = tmp_path / "rgs-briefs"
    empty.mkdir()
    assert main(["--dir", str(empty), "--slug", "s", "--kind", "script"]) == EXIT_NONE
    assert main(["--dir", str(tmp_path / "gone"), "--slug", "s", "--kind", "script"]) == EXIT_ERROR


def test_a_missing_dir_never_proposes_a_next_filename(tmp_path: Path):
    """The S1 half: `--next` against a missing directory used to return
    `<date>-<slug>-<kind>.md`, version 1 -- the exact name of a live v1 brief."""
    rc = main([
        "--dir", str(tmp_path / "gone"), "--slug", "s", "--kind", "script",
        "--next", "--date", "2026-08-08",
    ])
    assert rc == EXIT_ERROR


def test_the_resolved_absolute_directory_is_echoed_on_every_run(tmp_path: Path, capsys):
    """C-96 surfacing test. The operator can see which directory answered."""
    _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    assert main(["--dir", str(tmp_path), "--slug", "my-short", "--kind", "script"]) == EXIT_OK
    err = capsys.readouterr().err
    assert str(tmp_path.resolve()) in err


def test_a_corrupt_brief_and_no_brief_return_different_codes(tmp_path: Path):
    """C-100 distinguishability test. Both used to exit 1, so a caller that read
    exit 1 as "start at v1" turned a corrupt brief into an overwrite."""
    (tmp_path / "2026-07-28-my-short-script.md").write_text("no frontmatter\n", encoding="utf-8")
    corrupt = main(["--dir", str(tmp_path), "--slug", "my-short", "--kind", "script"])
    empty = main(["--dir", str(tmp_path), "--slug", "other-short", "--kind", "script"])
    assert (corrupt, empty) == (EXIT_ERROR, EXIT_NONE)


def test_exit_code_1_is_never_returned(tmp_path: Path):
    """The retired code. A stale caller testing `rc == 1` must find a condition
    that never fires rather than one that quietly means the wrong thing."""
    (tmp_path / "2026-07-28-bad-script.md").write_text("no frontmatter\n", encoding="utf-8")
    codes = {
        main(["--dir", str(tmp_path), "--slug", "bad", "--kind", "script"]),
        main(["--dir", str(tmp_path), "--slug", "absent", "--kind", "script"]),
        main(["--dir", str(tmp_path / "gone"), "--slug", "absent", "--kind", "script"]),
    }
    assert 1 not in codes


def test_none_still_prints_the_documented_stdout_contract(tmp_path: Path, capsys):
    """Ten skills branch on the printed text, not the code. That contract holds."""
    assert main(["--dir", str(tmp_path), "--slug", "absent", "--kind", "script"]) == EXIT_NONE
    assert capsys.readouterr().out.strip() == "NONE\t0"


def test_a_version_tie_raises_and_names_both_paths(tmp_path: Path):
    """C-97 fault test."""
    a = _write(tmp_path, "2026-07-01-my-short-script-v2.md", 2)
    b = _write(tmp_path, "2026-07-28-my-short-script-v3.md", 2)
    with pytest.raises(ValueError) as exc:
        find_latest(tmp_path, "my-short", "script")
    assert a.name in str(exc.value) and b.name in str(exc.value)


def test_a_tie_is_distinguishable_from_a_clean_resolution(tmp_path: Path):
    """C-97 distinguishability test: the tie used to resolve to the earlier
    date and report success, identical in shape to a correct answer."""
    _write(tmp_path, "2026-07-01-my-short-script-v2.md", 2)
    assert main(["--dir", str(tmp_path), "--slug", "my-short", "--kind", "script"]) == EXIT_OK
    _write(tmp_path, "2026-07-28-my-short-script-v3.md", 2)
    assert main(["--dir", str(tmp_path), "--slug", "my-short", "--kind", "script"]) == EXIT_ERROR
