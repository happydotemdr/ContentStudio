"""Tests for scripts/check_pin_freshness.py (finding F-76, CI fix round 2).

Every test injects a stub `fetch_versions_fn` -- the module's real
`fetch_versions` calls `urllib.request.urlopen`, which tests/conftest.py's
autouse guard blocks unless a test opts in with @pytest.mark.allow_network.
Injecting a stub instead of relying on that opt-in is the whole point of the
seam this module was extracted to have: nothing embedded in workflow YAML
could be unit-tested at all, which is how the vacuous-pass bug this file
guards against shipped in the first place.
"""
from pathlib import Path

from scripts.check_pin_freshness import (
    FRESH,
    STALE,
    UNDETERMINED,
    check_one,
    main,
    run,
)


def _stub(versions: list[str]):
    def _fetch(library: str) -> list[str]:
        return versions

    return _fetch


def _stub_by_library(versions_by_library: dict[str, list[str]]):
    def _fetch(library: str) -> list[str]:
        return versions_by_library[library]

    return _fetch


def _write_manifest(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# check_one: the per-(manifest, library) classifier.
# ---------------------------------------------------------------------------


def test_fresh_pin_is_fresh():
    result = check_one(
        "requirements.txt", "yt-dlp==2026.7.4\n", "yt-dlp",
        fetch_versions_fn=_stub(["2026.6.9", "2026.7.4"]),
    )
    assert result.verdict == FRESH


def test_stale_pin_names_the_library_and_how_far_behind():
    result = check_one(
        "requirements.txt", "yt-dlp==2026.6.9\n", "yt-dlp",
        fetch_versions_fn=_stub(["2026.2.21", "2026.6.9", "2026.7.4"]),
    )
    assert result.verdict == STALE
    assert "yt-dlp" in result.message
    assert "1 release" in result.message
    assert "2026.7.4" in result.message


def test_malformed_pin_is_undetermined_not_silently_skipped():
    """Regression test for the re-reviewer's finding. A pre-release-style pin
    (`yt-dlp==2026.7.4rc1`, a realistic pin after a pre-release bump) must
    fail as UNDETERMINED, not disappear.

    Confirmed by direct reproduction that the prior, embedded-in-YAML
    version of this check does NOT do this: run against both manifests
    pinned to `yt-dlp==2026.7.4rc1`, it printed "Pin freshness check passed:
    all pins match PyPI latest." and exited 0 -- yt-dlp was never checked,
    because that version's pin parser returned None and `continue`d past it,
    and its "did anything parse" tracking was per-library-across-every-
    manifest rather than per-(manifest, library) pair, so youtube-transcript-
    api parsing anywhere was enough to call the whole run a pass."""
    result = check_one(
        "requirements.txt", "yt-dlp==2026.7.4rc1\n", "yt-dlp",
        fetch_versions_fn=_stub(["2026.6.9", "2026.7.4"]),
    )
    assert result.verdict == UNDETERMINED
    assert "yt-dlp" in result.message
    assert "requirements.txt" in result.message
    assert "2026.7.4rc1" in result.message


def test_fetch_failure_is_undetermined_not_a_silent_pass():
    def _raise(library: str) -> list[str]:
        raise TimeoutError("PyPI did not respond")

    result = check_one("requirements.txt", "yt-dlp==2026.7.4\n", "yt-dlp", fetch_versions_fn=_raise)
    assert result.verdict == UNDETERMINED
    assert "yt-dlp" in result.message
    assert "TimeoutError" in result.message


def test_missing_pin_line_is_undetermined_not_skipped():
    """Dead in practice today (a sibling harness test in
    tests/test_harness_contract.py pins both libraries in both manifests
    exactly), but the contract this module promises is that every
    (manifest, library) pair reaches a verdict -- never a silent `continue`.
    This is the pair with no pin line at all, exercised directly."""
    result = check_one(
        "requirements.txt", "requests==2.31.*\n", "yt-dlp",
        fetch_versions_fn=_stub(["2026.7.4"]),
    )
    assert result.verdict == UNDETERMINED
    assert "yt-dlp" in result.message


# ---------------------------------------------------------------------------
# run(): every (manifest, library) pair, never merged, never dropped.
# ---------------------------------------------------------------------------


def test_run_produces_one_result_per_manifest_times_library_pair(tmp_path):
    root_req = _write_manifest(
        tmp_path, "requirements.txt", "yt-dlp==2026.7.4rc1\nyoutube-transcript-api==1.2.4\n"
    )
    app_dir = tmp_path / "pipeline-app"
    app_dir.mkdir()
    app_req = _write_manifest(
        app_dir, "requirements.txt", "yt-dlp==2026.7.4rc1\nyoutube-transcript-api==1.2.4\n"
    )

    results = run(
        manifests=(root_req, app_req),
        fetch_versions_fn=_stub_by_library(
            {"yt-dlp": ["2026.7.4"], "youtube-transcript-api": ["1.2.4"]}
        ),
    )

    assert len(results) == 4, "2 manifests x 2 libraries must yield 4 verdicts, none dropped"
    verdicts = {(r.manifest, r.library): r.verdict for r in results}
    # The malformed yt-dlp pin is undetermined in BOTH manifests independently
    # -- the bug this module replaces let one manifest's failure hide behind
    # the other manifest's success for the SAME library.
    assert verdicts[(str(root_req), "yt-dlp")] == UNDETERMINED
    assert verdicts[(str(app_req), "yt-dlp")] == UNDETERMINED
    assert verdicts[(str(root_req), "youtube-transcript-api")] == FRESH
    assert verdicts[(str(app_req), "youtube-transcript-api")] == FRESH


# ---------------------------------------------------------------------------
# main(): the entry point CI actually invokes. Exit status and message
# content, not "was the stub called" -- effect, not echo.
# ---------------------------------------------------------------------------


def test_main_exits_0_and_reports_fresh_when_every_pin_is_current(tmp_path, capsys):
    req = _write_manifest(tmp_path, "requirements.txt", "yt-dlp==2026.7.4\n")

    code = main(manifests=(req,), libraries=("yt-dlp",), fetch_versions_fn=_stub(["2026.7.4"]))

    assert code == 0
    out = capsys.readouterr().out
    assert "FRESH" in out
    assert "Pin freshness check passed" in out


def test_main_exits_1_on_a_stale_pin(tmp_path, capsys):
    req = _write_manifest(tmp_path, "requirements.txt", "yt-dlp==2026.6.9\n")

    code = main(
        manifests=(req,), libraries=("yt-dlp",),
        fetch_versions_fn=_stub(["2026.6.9", "2026.7.4"]),
    )

    assert code == 1
    out = capsys.readouterr().out
    assert "STALE" in out
    assert "yt-dlp" in out


def test_main_exits_2_on_a_malformed_pin_and_the_exit_code_differs_from_stale(tmp_path, capsys):
    req = _write_manifest(tmp_path, "requirements.txt", "yt-dlp==2026.7.4rc1\n")

    code = main(
        manifests=(req,), libraries=("yt-dlp",),
        fetch_versions_fn=_stub(["2026.6.9", "2026.7.4"]),
    )

    assert code == 2
    assert code != 1, "an unreadable pin and a stale pin must not look alike to a human reading exit codes"
    out = capsys.readouterr().out
    assert "UNDETERMINED" in out
    assert "2026.7.4rc1" in out


def test_main_exits_2_when_the_pypi_fetch_raises(tmp_path, capsys):
    req = _write_manifest(tmp_path, "requirements.txt", "yt-dlp==2026.7.4\n")

    def _raise(library: str) -> list[str]:
        raise TimeoutError("PyPI did not respond")

    code = main(manifests=(req,), libraries=("yt-dlp",), fetch_versions_fn=_raise)

    assert code == 2
    out = capsys.readouterr().out
    assert "UNDETERMINED" in out
    assert "yt-dlp" in out
