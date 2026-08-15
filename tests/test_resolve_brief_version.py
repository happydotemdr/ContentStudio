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


def _cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "scripts.resolve_brief_version", *args],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


@pytest.mark.allow_subprocess
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
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    assert "\\" not in result.stdout
    printed_path, printed_version = result.stdout.strip().split("\t")
    assert printed_path.endswith("2026-07-28-my-short-script.md")
    assert printed_version == "1"


@pytest.mark.allow_subprocess
def test_cli_exit_codes_reach_the_shell(tmp_path: Path):
    """F-23 surfacing test. The skills read $? , not a Python return value."""
    _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    ok = _cli(tmp_path, "--dir", str(tmp_path), "--slug", "my-short", "--kind", "script")
    none = _cli(tmp_path, "--dir", str(tmp_path), "--slug", "absent", "--kind", "script")
    gone = _cli(tmp_path, "--dir", str(tmp_path / "gone"), "--slug", "absent", "--kind", "script")
    assert (ok.returncode, none.returncode, gone.returncode) == (0, 3, 2)
    assert none.stdout.strip() == "NONE\t0"
    assert gone.stdout.strip() == ""
    assert "does not exist" in gone.stderr


@pytest.mark.allow_subprocess
def test_cli_reports_a_corrupt_brief_on_stderr_without_a_traceback(tmp_path: Path):
    """C-100's other half: exit 1 used to carry a raw traceback and no stdout."""
    (tmp_path / "2026-07-28-my-short-script.md").write_text("no frontmatter\n", encoding="utf-8")
    result = _cli(tmp_path, "--dir", str(tmp_path), "--slug", "my-short", "--kind", "script")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "no frontmatter block found" in result.stderr


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


def test_a_filename_suffix_that_contradicts_frontmatter_raises(tmp_path: Path):
    """C-98 fault test."""
    _write(tmp_path, "2026-07-28-my-short-script-v3.md", 1)
    with pytest.raises(ValueError) as exc:
        find_latest(tmp_path, "my-short", "script")
    assert "-v3" in str(exc.value) and "version: 1" in str(exc.value)


def test_the_unsuffixed_name_means_version_1(tmp_path: Path):
    """Calibration: `<date>-<slug>-<kind>.md` with no suffix is v1 by contract,
    which is what every shipped brief and every existing test relies on."""
    p = _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    assert find_latest(tmp_path, "my-short", "script") == (p, 1)


def test_next_filename_refuses_a_proposal_that_already_exists(tmp_path: Path, monkeypatch):
    """C-98's second half. Proposing an existing brief's name is one careless
    Write away from destroying it.

    Given find_latest's own -vN/frontmatter cross-check (this same task, above),
    a proposal computed from a fully-scanned, self-consistent directory can never
    collide with a file already on disk: any file sitting at the target path
    would itself have been counted by find_latest and pushed the proposal past
    it. The guard this exercises is therefore for the real hazard -- a write
    landing between find_latest's scan and this function's own directory read --
    which a synchronous test can only reproduce by stubbing find_latest's answer
    and then planting the file its stale answer would collide with.
    """
    monkeypatch.setattr(
        "scripts.resolve_brief_version.find_latest",
        lambda *a, **k: (tmp_path / "2026-07-28-my-short-script-v4.md", 4),
    )
    _write(tmp_path, "2026-07-28-my-short-script-v5.md", 5)
    with pytest.raises(FileExistsError) as exc:
        next_filename(tmp_path, "my-short", "script", "2026-07-28")
    assert "v5" in str(exc.value) or "already exists" in str(exc.value)


def test_a_malformed_date_is_rejected(tmp_path: Path):
    """C-99 fault test. The resolver's own _pattern requires \\d{4}-\\d{2}-\\d{2};
    next_filename used to interpolate whatever it was handed."""
    rc = main(["--dir", str(tmp_path), "--slug", "s", "--kind", "script",
               "--next", "--date", "banana"])
    assert rc == EXIT_ERROR


def test_a_malformed_date_is_distinguishable_from_a_valid_one(tmp_path: Path, capsys):
    """C-99 distinguishability test."""
    ok = main(["--dir", str(tmp_path), "--slug", "s", "--kind", "script",
               "--next", "--date", "2026-08-08"])
    out = capsys.readouterr().out
    assert (ok, out.strip()) == (EXIT_OK, "2026-08-08-s-script.md\t1")
    bad = main(["--dir", str(tmp_path), "--slug", "s", "--kind", "script",
                "--next", "--date", "08/08/2026"])
    assert bad == EXIT_ERROR


def test_a_proposed_filename_always_matches_the_pattern_that_finds_it(tmp_path: Path):
    """The invariant behind C-99: anything --next proposes must be findable by
    find_latest afterwards, or the chain breaks permanently."""
    filename, _ = next_filename(tmp_path, "my-short", "script", "2026-08-08")
    from scripts.resolve_brief_version import _pattern
    assert _pattern("my-short", "script").match(filename)


def test_a_collision_and_a_clean_proposal_are_distinguishable(tmp_path: Path, monkeypatch):
    """C-98 distinguishability + surfacing test: the collision exits 2 where the
    clean proposal exits 0.

    See test_next_filename_refuses_a_proposal_that_already_exists above for why
    the second call must stub find_latest's answer to force the collision: a
    freshly-planted, self-consistent file is picked up by a real scan and simply
    advances the proposal past itself rather than colliding with it.
    """
    _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    args = ["--dir", str(tmp_path), "--slug", "my-short", "--kind", "script",
            "--next", "--date", "2026-07-28"]
    assert main(args) == EXIT_OK
    (tmp_path / "2026-07-28-my-short-script-v2.md").write_text(
        "---\nversion: 2\n---\n\nbody\n", encoding="utf-8")
    monkeypatch.setattr(
        "scripts.resolve_brief_version.find_latest",
        lambda *a, **k: (tmp_path / "2026-07-28-my-short-script.md", 1),
    )
    assert main(args) == EXIT_ERROR
