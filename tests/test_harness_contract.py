"""Regression tests for the P0 harness contract (findings F-01…F-80, B-83, C-105).

This suite reads repo files as data. It is the one suite that legitimately
inspects the whole tree, so the cross-suite drift checks live here.
"""
import configparser
import os
import re
import shutil
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
        rel = path.relative_to(REPO_ROOT)
        assert "allow_network" in markers, f"{rel} does not register allow_network"
        assert "allow_subprocess" in markers, f"{rel} does not register allow_subprocess"


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


def test_filterwarnings_no_longer_carries_the_dead_pytest_asyncio_ignores():
    """pytest-asyncio 1.2.0 (pipeline-app/requirements-dev.txt) plus the
    asyncio_mode / asyncio_default_fixture_loop_scope pins in the app ini
    fixed the deprecation noise both suites used to ignore by name, at its
    source (F-70, F-71). A module-scoped ignore that outlives the warning it
    targeted is not inert: it keeps silencing every *future*
    DeprecationWarning from that module too, which is exactly the signal
    `filterwarnings = error` exists to surface. Both
    `ignore::DeprecationWarning:pytest_asyncio[.plugin]` lines were removed
    for that reason -- from BOTH pytest.ini files, in the same commit -- so
    this pins the remaining list exactly for each one, the way
    test_both_inis_turn_unexpected_warnings_into_errors above does. The root
    ini gets no async tests of its own, so a re-add there has no other
    signal to surface it; this is the one test standing between that and
    silence.
    """
    for path in (ROOT_INI, APP_INI):
        filters = [
            line.strip()
            for line in _ini(path)["pytest"]["filterwarnings"].splitlines()
            if line.strip()
        ]
        # ROOT_INI and APP_INI are both literally named "pytest.ini" --
        # path.name alone would make a root-ini failure and an app-ini
        # failure produce byte-identical messages, which is exactly the
        # indistinguishable-representations defect this test exists to
        # catch. relative_to(REPO_ROOT) renders "pytest.ini" vs
        # "pipeline-app/pytest.ini", so the two are never confusable.
        rel = path.relative_to(REPO_ROOT)
        assert filters == [
            "error",
            "ignore::DeprecationWarning:fastapi.routing",
            "ignore::ResourceWarning",
        ], f"{rel}: filterwarnings no longer matches the expected post-removal ignore list"
        assert "ignore::DeprecationWarning:pytest_asyncio" not in filters, (
            f"{rel}: the dead ignore::DeprecationWarning:pytest_asyncio line has crept back in"
        )
        assert "ignore::DeprecationWarning:pytest_asyncio.plugin" not in filters, (
            f"{rel}: the dead ignore::DeprecationWarning:pytest_asyncio.plugin line has crept back in"
        )


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


COPY_SH = REPO_ROOT / "copy_youthsports.sh"
RUN_ALL_SH = REPO_ROOT / "run_all.sh"


def test_copy_youthsports_uses_a_distinct_exit_code_for_a_missing_source():
    """B-83: `exit 1` is indistinguishable from a copy that genuinely failed,
    so run_all.sh cannot tell 'not applicable here' from 'broken'."""
    assert "exit 3" in COPY_SH.read_text(encoding="utf-8")


def test_run_all_treats_the_youth_sports_step_as_skippable():
    text = RUN_ALL_SH.read_text(encoding="utf-8")
    assert "|| youth_status=$?" in text
    assert "brand-intel" in text.split("youth_status")[-1], (
        "step 3 must still be reachable after step 2 fails (F-77)"
    )


@pytest.mark.allow_subprocess
def test_run_all_reaches_step_three_when_the_sibling_corpus_is_absent(tmp_path):
    """Fault + distinguishability in one run: with the sibling checkout absent
    (always, in this repo), the script must warn and continue, and the
    brand-intel step must still be announced.

    Resolves bash to an absolute path via shutil.which before invoking it.
    A bare "bash" handed to subprocess lets Windows CreateProcess resolve it
    against System32 -- where the WSL launcher stub ships on essentially
    every Windows 10/11 install with WSL enabled -- before it ever consults
    PATH, regardless of PATH's own ordering. That stub then fails immediately
    with an unrelated WSL relay error, which has nothing to do with whether
    this fix is correct. If no bash is found at all, skip with a reason
    instead of silently passing: "no interpreter available" and "the script
    behaved correctly" must never share an outcome -- that is exactly the
    indistinguishable-representations defect this task's exit-code fix
    exists to remove.
    """
    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("no bash interpreter found on PATH")
    for name in ("run_all.sh", "copy_youthsports.sh"):
        (tmp_path / name).write_text((REPO_ROOT / name).read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "download_thinkers.py").write_text("print('thinkers stub')\n", encoding="utf-8")
    (tmp_path / "download_brandintel.py").write_text("print('brandintel stub')\n", encoding="utf-8")
    result = subprocess.run(
        [bash_path, "run_all.sh"],
        cwd=str(tmp_path), capture_output=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHON": sys.executable},
    )
    assert result.returncode == 0
    assert "brandintel stub" in result.stdout
    assert "SKIPPED" in result.stdout


@pytest.mark.allow_subprocess
def test_run_all_stops_loudly_when_the_youth_sports_copy_genuinely_fails(tmp_path):
    """Distinguishability, the other half. Every test above exercises only
    the "source absent -> skip" path. Without this one, widening the `-eq 3`
    branch condition to `-ge 1` (or deleting the `elif ... exit
    "$youth_status"` branch outright) makes every other test in this file
    still pass, while run_all.sh silently swallows a genuine step-2 failure
    and marches on to step 3 -- exactly the defect this task exists to
    remove (B-83)."""
    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("no bash interpreter found on PATH")
    (tmp_path / "run_all.sh").write_text(RUN_ALL_SH.read_text(encoding="utf-8"), encoding="utf-8")
    # A genuine failure, distinct from both success (0) and "source absent"
    # (3): copy_youthsports.sh is stubbed out entirely here, so this proves
    # run_all.sh's own branching, not the real script's -d check.
    (tmp_path / "copy_youthsports.sh").write_text("exit 2\n", encoding="utf-8")
    (tmp_path / "download_thinkers.py").write_text("print('thinkers stub')\n", encoding="utf-8")
    (tmp_path / "download_brandintel.py").write_text("print('brandintel stub')\n", encoding="utf-8")
    result = subprocess.run(
        [bash_path, "run_all.sh"],
        cwd=str(tmp_path), capture_output=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHON": sys.executable},
    )
    assert result.returncode != 0, "a genuine step-2 failure must fail the run, not succeed"
    assert "SKIPPED" not in result.stdout and "SKIPPED" not in result.stderr, (
        "a real failure must not be misreported as an absent source"
    )
    assert "brandintel stub" not in result.stdout, "step 3 must not run after a genuine step-2 failure"
    assert result.returncode == 2, "the propagated code should be the stub's own, not flattened to 1"


WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"


def _workflow() -> dict:
    import yaml

    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_ci_defines_the_three_required_jobs():
    assert set(_workflow()["jobs"]) == {"root-suite", "app-suite", "no-live-credentials"}


def test_ci_runs_both_suites_with_python_m_and_never_a_bare_pytest():
    """F-61 + F-63: bare `pytest` omits the app suite silently and does not
    prepend the cwd, so it can test a different checkout."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python -m pytest tests/" in text
    assert re.search(r"working-directory:\s*pipeline-app", text)
    assert not re.search(r"run:\s*pytest\b", text), "a bare `pytest` invocation is in the workflow"


def test_ci_asserts_pipeline_app_is_never_installed():
    """F-63: CI must never install the package, so python -m's cwd prepend is
    its only source."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pipeline-app must not be installed" in text
    assert "pip install -e" not in text


def test_ci_runs_weekly_and_covers_both_suites():
    """Renamed from a claim CI cannot back up (fix round 1, Important 1): a
    mocked weekly rerun cannot detect yt-dlp / youtube-transcript-api schema
    drift -- both libraries are pinned exactly, every consuming test is
    mocked, and the autouse guard blocks any unstubbed network call (no test
    anywhere carries allow_network). This asserts only what the schedule
    trigger and workflow structure actually guarantee: a weekly run exists,
    and it still exercises both suites -- neither job opts itself out of the
    schedule event. The real F-76 signal is the pin-freshness step, covered
    by test_ci_pin_freshness_step_checks_pypi_only_on_the_scheduled_run."""
    workflow = _workflow()
    on = workflow[True] if True in workflow else workflow["on"]
    assert "schedule" in on
    assert on["schedule"][0]["cron"]
    for job_name in ("root-suite", "app-suite"):
        assert "if" not in workflow["jobs"][job_name], (
            f"{job_name} must still run on the weekly schedule, not opt out of it"
        )


def test_ci_weekly_comment_states_environment_drift_not_vendor_schema_detection():
    """Fix round 1, Important 1: the old comment claimed the weekly rerun
    itself surfaces yt-dlp / youtube-transcript-api schema drift -- a claim
    the suite structurally cannot back up (everything is mocked, and the
    autouse guard blocks any unstubbed network call). This locks in the
    correction: the comment must own what the weekly run actually catches
    (environment drift) and must point at the extracted pin-freshness script
    as the real F-76 signal, not the rerun itself."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "environment drift" in text
    assert "structurally cannot" in text
    assert "check_pin_freshness" in text


def test_ci_pin_freshness_step_invokes_the_extracted_script_only_on_schedule():
    """Fix round 2: the pin-freshness logic used to live inline in this YAML,
    where nothing could unit-test it -- that is how the vacuous-pass bug (a
    pin like `yt-dlp==2026.7.4rc1` was silently never checked) shipped in the
    first place. It is now scripts/check_pin_freshness.py, covered by
    tests/test_check_pin_freshness.py; this test only checks the thin
    invocation left behind: exactly one step, in root-suite, gated to
    `schedule`, running the extracted module and nothing else embedded."""
    workflow = _workflow()
    steps = workflow["jobs"]["root-suite"]["steps"]
    freshness = [s for s in steps if "pin freshness" in s.get("name", "").lower()]
    assert len(freshness) == 1, "expected exactly one pin-freshness step in root-suite"
    step = freshness[0]
    assert step.get("if") == "github.event_name == 'schedule'"
    assert step["run"].strip() == "python -m scripts.check_pin_freshness"
    for job_name, job in workflow["jobs"].items():
        if job_name == "root-suite":
            continue
        assert not any(
            "pin freshness" in s.get("name", "").lower() for s in job.get("steps", [])
        ), f"{job_name} must not also run the pin-freshness check"


def test_check_pin_freshness_script_exists_checks_pypi_and_is_stdlib_only():
    """The workflow step above only names a module by import path; this
    confirms the module actually exists, references PyPI and both tracked
    libraries, and -- per CONSTRAINTS.md's rule for repo-root scripts/**,
    which are loaded by file path/`python -m` and must stay free of
    third-party or app imports -- imports nothing beyond the standard
    library. CI installs only requirements-dev.txt for the scheduled job;
    a third-party import here would ImportError at runtime, not just violate
    a convention."""
    script = REPO_ROOT / "scripts" / "check_pin_freshness.py"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "pypi.org" in text
    for library in ("yt-dlp", "youtube-transcript-api"):
        assert library in text

    import ast

    stdlib_top_level = {
        "json", "re", "sys", "urllib", "dataclasses", "pathlib", "typing", "__future__",
    }
    tree = ast.parse(text, filename=str(script))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in stdlib_top_level, f"non-stdlib import: {alias.name}"
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            assert top in stdlib_top_level, f"non-stdlib import: {node.module}"


def test_no_live_credentials_selects_by_node_id_not_a_fragile_dash_k():
    """Fix round 1, Important 2: `-k "guard or blocked or vendor"` selects the
    right tests today, but a rename that drops those substrings would just
    silently narrow the match while the job still exits 0 -- pytest's
    exit-5-on-zero-match only catches losing every match, never a partial
    one. Explicit node IDs turn a rename into a collection error instead:
    handed a node ID that no longer exists, pytest exits 4 with "ERROR: not
    found", not 0 (verified by hand against both live suites)."""
    workflow = _workflow()
    job = workflow["jobs"]["no-live-credentials"]
    run_steps = [s["run"] for s in job["steps"] if "run" in s]
    combined = "\n".join(run_steps)
    assert "-k" not in combined, "a `-k` substring filter can silently narrow on an unrelated rename"
    assert "::test_guard_fires_even_when_every_vendor_key_is_present" in combined


def test_ci_configures_no_coverage_gate():
    """F-02: 95% coverage coexisted with 328 defects."""
    assert "--cov-fail-under" not in WORKFLOW.read_text(encoding="utf-8")


TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"


def test_pr_template_names_the_three_ci_jobs_as_checkboxes():
    text = TEMPLATE.read_text(encoding="utf-8")
    for job in ("root-suite", "app-suite", "no-live-credentials"):
        assert f"- [ ] `{job}`" in text


def test_pr_template_job_names_match_the_workflow_exactly():
    """A checkbox naming a job that does not exist is worse than no checkbox."""
    jobs = set(_workflow()["jobs"])
    text = TEMPLATE.read_text(encoding="utf-8")
    named = set(re.findall(r"- \[ \] `([a-z-]+)`", text))
    assert named == jobs


def test_no_coverage_gate_exists_anywhere_in_the_harness():
    """F-02: 95% line coverage coexisted with 328 defects. A --cov-fail-under
    gate would re-establish the number as the quality bar."""
    for path in (ROOT_INI, APP_INI, WORKFLOW, ROOT_DEV, APP_DEV):
        assert "--cov-fail-under" not in path.read_text(encoding="utf-8"), path


def test_the_quality_bar_is_stated_as_the_finding_to_test_mapping():
    """F-27 policy half: the standard has to be written somewhere a machine
    can check, or it is not a standard."""
    assert "Coverage is diagnostic only" in ROOT_INI.read_text(encoding="utf-8")
    assert "Coverage is diagnostic only" in APP_INI.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    assert "Regression test for the defect this fixes" in template
    assert "observed FAILING before the fix" in template
