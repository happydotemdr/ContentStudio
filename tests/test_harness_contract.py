"""Regression tests for the P0 harness contract (findings F-01…F-80, B-83, C-105).

This suite reads repo files as data. It is the one suite that legitimately
inspects the whole tree, so the cross-suite drift checks live here.
"""
import configparser
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_INI = REPO_ROOT / "pytest.ini"
APP_INI = REPO_ROOT / "pipeline-app" / "pytest.ini"


def _ini(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(inline_comment_prefixes=None)
    parser.read_string(path.read_text(encoding="utf-8"))
    return parser


def test_both_inis_register_both_opt_in_markers():
    """The two suites are collected independently, so a marker registered in
    one ini does not exist in the other. --strict-markers turns a missing
    registration into a collection error, which would break P5's
    test_git_helper.py and P6's byte-identity round-trip."""
    for path in (ROOT_INI, APP_INI):
        markers = _ini(path)["pytest"]["markers"]
        assert "allow_network" in markers, f"{path.name} does not register allow_network"
        assert "allow_subprocess" in markers, f"{path.name} does not register allow_subprocess"


def test_root_ini_declares_coverage_diagnostic_and_configures_no_gate():
    text = ROOT_INI.read_text(encoding="utf-8")
    assert "Coverage is diagnostic only" in text
    assert "--cov-fail-under" not in text


def test_root_ini_states_that_a_bare_run_is_the_root_suite_only():
    first_lines = ROOT_INI.read_text(encoding="utf-8").splitlines()[:3]
    assert any("ROOT SUITE ONLY" in line for line in first_lines)


def test_root_run_header_names_the_app_suite_command():
    from tests.conftest import pytest_report_header

    lines = pytest_report_header(config=None)
    joined = "\n".join(lines)
    assert "ROOT SUITE ONLY" in joined
    assert "cd pipeline-app && python -m pytest" in joined


GUARD_BEGIN = "# ---------------------------------------------------------------- BEGIN SHARED GUARD"
GUARD_END = "# ------------------------------------------------------------------ END SHARED GUARD"


def _guard_block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.index(GUARD_BEGIN)
    end = text.index(GUARD_END) + len(GUARD_END)
    return text[start:end]


def test_guard_blocks_are_identical_in_both_conftests():
    root = _guard_block(REPO_ROOT / "tests" / "conftest.py")
    app = _guard_block(REPO_ROOT / "pipeline-app" / "tests" / "conftest.py")
    assert root == app, "the two conftest guard blocks have drifted"


def test_root_suite_blocks_an_unstubbed_subprocess():
    from tests.conftest import LiveCallBlocked

    with pytest.raises(LiveCallBlocked):
        subprocess.run([sys.executable, "-c", "pass"])


VENDOR_KEYS = ("BRIGHTDATA_API_KEY", "RESEND_API_KEY", "YOUTUBE_API_KEY")


def test_guard_fires_even_when_every_vendor_key_is_present(monkeypatch):
    """The `no-live-credentials` CI job runs exactly this with canary values in
    the environment. A guard that only works when keys are absent is worthless:
    keys are always present on the operator's machine."""
    import requests

    from tests.conftest import LiveCallBlocked

    for key in VENDOR_KEYS:
        monkeypatch.setenv(key, "ci-canary-must-never-be-used")

    with pytest.raises(LiveCallBlocked):
        requests.post("https://api.brightdata.com/datasets/v3/trigger", json={})
    with pytest.raises(LiveCallBlocked):
        subprocess.run(["curl", "https://api.resend.com/emails"])


def test_both_inis_turn_unexpected_warnings_into_errors():
    for path in (ROOT_INI, APP_INI):
        filters = _ini(path)["pytest"]["filterwarnings"]
        assert filters.strip().splitlines()[0].strip() == "error"


def test_third_party_asyncio_deprecations_are_ignored_by_name():
    filters = _ini(APP_INI)["pytest"]["filterwarnings"]
    assert "ignore::DeprecationWarning:pytest_asyncio" in filters
    assert "ignore::DeprecationWarning:fastapi.routing" in filters


@pytest.mark.allow_subprocess
def test_a_repo_warning_fails_the_run_while_an_ignored_module_one_does_not(tmp_path):
    """Distinguishability: third-party lines are silenced, but the repo's own
    warnings are not -- that was the whole defect (F-70).

    Both halves are required. The single-half form of this test (emit a
    UserWarning, assert the run fails) asserted only that `error` works: it
    passed unchanged with every `ignore::` line deleted from the ini, so it
    proved nothing about whether the ignore list is correctly scoped -- a test
    whose name claims a comparison it never performs.
    """
    ini_text = ROOT_INI.read_text(encoding="utf-8").replace(
        "testpaths = tests", "testpaths = ."
    )
    ini_text += "    ignore::UserWarning:ignorable_mod\n"
    (tmp_path / "pytest.ini").write_text(ini_text, encoding="utf-8")

    (tmp_path / "ignorable_mod.py").write_text(
        "import warnings\n"
        "def warn_here():\n"
        "    warnings.warn('from a module the ignore list names', UserWarning)\n",
        encoding="utf-8",
    )
    (tmp_path / "test_repo_warning.py").write_text(
        "import warnings\n"
        "def test_repo_warning():\n"
        "    warnings.warn('the app started emitting this', UserWarning)\n",
        encoding="utf-8",
    )
    (tmp_path / "test_ignorable_warning.py").write_text(
        "import ignorable_mod\n"
        "def test_ignorable_warning():\n"
        "    ignorable_mod.warn_here()\n",
        encoding="utf-8",
    )

    def _run(test_file):
        return subprocess.run(
            [sys.executable, "-m", "pytest", test_file, "-q", "-p", "no:cacheprovider"],
            capture_output=True, encoding="utf-8", errors="replace", cwd=str(tmp_path),
        )

    repo_result = _run("test_repo_warning.py")
    ignorable_result = _run("test_ignorable_warning.py")

    assert repo_result.returncode != 0
    assert "UserWarning" in repo_result.stdout
    assert ignorable_result.returncode == 0
    assert repo_result.returncode != ignorable_result.returncode


ROOT_REQ = REPO_ROOT / "requirements.txt"
ROOT_DEV = REPO_ROOT / "requirements-dev.txt"
APP_REQ = REPO_ROOT / "pipeline-app" / "requirements.txt"
APP_DEV = REPO_ROOT / "pipeline-app" / "requirements-dev.txt"


def _names(path: Path) -> set[str]:
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            out.add(re.split(r"[<>=!\[]", line, maxsplit=1)[0].strip().lower())
    return out


def test_both_dev_manifests_carry_the_test_toolchain():
    for path in (ROOT_DEV, APP_DEV):
        names = _names(path)
        assert {"pytest", "pytest-cov", "hypothesis"} <= names, f"{path.name} is missing tooling"


def test_runtime_manifests_carry_no_test_only_dependencies():
    for path in (ROOT_REQ, APP_REQ):
        names = _names(path)
        assert not ({"pytest", "pytest-asyncio", "pytest-cov", "httpx", "hypothesis"} & names), (
            f"{path.name} mixes test-only deps into the runtime manifest (F-74)"
        )


def test_shared_libraries_use_one_constraint_style_across_the_two_manifests():
    """F-75: pyyaml>=6.0 vs pyyaml==6.0.*, requests>=2.31 vs requests==2.31.*."""
    def _spec(path: Path, name: str) -> str | None:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line.lower().startswith(name):
                return line
        return None

    for lib in ("pyyaml", "requests", "yt-dlp", "youtube-transcript-api"):
        assert _spec(ROOT_REQ, lib) == _spec(APP_REQ, lib), f"{lib} constraint styles disagree"


def test_yt_dlp_and_transcript_api_are_pinned_exactly_in_both_manifests():
    """F-76: yt-dlp ships frequently and changes --dump-json field names.
    test_discovery_youtube.py:249,309 pin `upload_date` and `duration`; a
    floating requirement means a rename breaks production while the mocked
    tests stay green."""
    for path in (ROOT_REQ, APP_REQ):
        text = path.read_text(encoding="utf-8")
        for library in ("yt-dlp", "youtube-transcript-api"):
            # Fully-anchored and digits/dots only, applied to BOTH libraries.
            # `^<name>==\d` alone was not enough: it matches `yt-dlp==2026.*`,
            # and yt-dlp versions calendar-style, so that wildcard floats
            # across a whole year -- exactly what F-76 forbids. Every sibling
            # in these manifests already uses that wildcard style
            # (`pyyaml==6.0.*`, `fastapi==0.115.*`), so "regularizing" these
            # two to match is a plausible way the pin silently dies. The `$`
            # anchor also rejects a compound spec (`==1.2.4,>=1.0.0`), which
            # the old one-sided `">=" not in ...` check only caught for yt-dlp.
            assert re.search(rf"^{re.escape(library)}==\d[\d.]*$", text, re.M), (
                f"{path.name}: {library} is not pinned to an exact version "
                f"(no wildcard, no range, no compound spec)"
            )


def test_root_scripts_is_not_a_regular_package():
    """C-105: the empty __init__.py is what makes root scripts/ a *regular*
    package, which is what shadows pipeline-app/scripts/ when the app suite is
    collected from here."""
    import importlib.util

    spec = importlib.util.find_spec("scripts")
    assert spec is not None
    assert spec.origin is None, "root scripts/ is still a regular package (C-105)"
    assert not (REPO_ROOT / "scripts" / "__init__.py").exists()


def test_root_scripts_modules_still_import_by_name():
    from scripts.resolve_brief_version import find_latest  # noqa: F401


def test_coverage_artifacts_are_gitignored():
    entries = set((REPO_ROOT / ".gitignore").read_text(encoding="utf-8").split())
    assert {
        ".coverage",
        ".coverage.*",
        "pipeline-app/.coverage",
        "htmlcov/",
        "coverage.xml",
        ".pytest_cache/",
    } <= entries


def test_the_obs_log_directory_is_gitignored():
    """P1's obs.log() writes pipeline-app/logs/app-YYYY-MM-DD.log on every
    structured event. .gitignore is P0's file, so the entry lands here."""
    entries = set((REPO_ROOT / ".gitignore").read_text(encoding="utf-8").split())
    assert "pipeline-app/logs/" in entries


@pytest.mark.allow_subprocess
def test_git_status_is_clean_after_a_coverage_run(tmp_path):
    """Surfacing: the two .coverage files exist untracked in the working tree
    today and a `git add -A` sweeps them into a commit (finding F-79)."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=str(REPO_ROOT), capture_output=True, encoding="utf-8", errors="replace",
    )
    untracked = [line[3:] for line in result.stdout.splitlines() if line.startswith("??")]
    assert not [p for p in untracked if ".coverage" in p or p.startswith("pipeline-app/logs/")]
