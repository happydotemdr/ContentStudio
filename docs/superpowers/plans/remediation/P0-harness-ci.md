# P0 — Test harness, CI, and the guards everything else stands on

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Parent: [`../2026-08-08-audit-remediation.md`](../2026-08-08-audit-remediation.md). Its **Global Constraints**, **test standard (Three-Test Rule + anti-tautology rules)** and **Frozen interfaces** sections are binding on every task below and are not restated.

**This is Wave A, package 1 of 2. It blocks all fourteen other packages.** Nothing in this repo runs the 1,034 tests today. Until this package lands, every fix the programme makes is unverified by any machine, and any test that forgets a stub can spawn a real per-record-billed Bright Data job while still reporting green.

---

## 1. Scope

### Files this package owns (no other package may touch these)

| Path | Disposition |
|---|---|
| `pytest.ini` (repo root) | modified |
| `pipeline-app/pytest.ini` | modified — **see scope note below** |
| `requirements.txt` | modified |
| `pipeline-app/requirements.txt` | modified |
| `pipeline-app/setup.py` | modified |
| `scripts/__init__.py` | **deleted** |
| `run_all.sh` | modified |
| `copy_youthsports.sh` | modified |
| `pipeline-app/start_pipeline.bat` | modified |
| `.gitignore` | modified |
| `.github/PULL_REQUEST_TEMPLATE.md` | modified |
| `.github/workflows/tests.yml` | **new** |
| `tests/conftest.py` | **new** |
| `pipeline-app/tests/conftest.py` | **new** |
| `pipeline-app/tests/integration/test_real_cli_e2e.py` | modified + renamed to `test_real_cli_ideation_only.py` |
| `pipeline-app/tests/test_routes_doctor.py` | modified |

New files this package also creates (unclaimed by any package; P0 is their only writer):

| Path | Purpose |
|---|---|
| `requirements-dev.txt` | root test-only deps (F-74) |
| `pipeline-app/requirements-dev.txt` | app test-only deps (F-74) |
| `tests/test_harness_contract.py` | root-suite regression tests for this package |
| `pipeline-app/tests/test_harness_contract.py` | app-suite regression tests for this package |
| `pipeline-app/tests/integration/test_stubbed_cli_e2e.py` | the nine-stage stubbed walk (F-03) |

**Scope note — `pipeline-app/pytest.ini`.** Claimed by P0 and **confirmed by the orchestrator**: no other package owns it, so both `pytest.ini` files are P0's. F-70/F-71 cannot close without the app-level ini.

**Scope note — `.gitignore`.** Also P0's, confirmed by the orchestrator. P1 reported it as unowned; that is incorrect. **P1 must not edit it.** P1's requirement — ignoring the `pipeline-app/logs/` directory that `obs.log()` writes — is delivered by P0 in Task 16, alongside the two `.coverage` files that already sit untracked in the working tree.

### Finding IDs owned (23)

`B-83`, `C-105`, `F-01`, `F-02`, `F-03`, `F-25`, `F-27`, `F-60`, `F-61`, `F-63`, `F-64`, `F-65`, `F-66`, `F-70`, `F-71`, `F-72`, `F-74`, `F-75`, `F-76`, `F-77`, `F-78`, `F-79`, `F-80`

### Explicit non-goals (other packages' work — do not do these here)

- Per-module test depth for any module P0 does not own. F-27 is closed here as a **policy** finding (CI exists; the standard is written down and machine-checked) plus the one consequence assertion on `test_routes_doctor.py`, which is P0's file. Adding tests to `test_git_helper.py` (P5) or `test_discovery_records.py` (P8) is theirs.
- Property-based tests for the two linters (F-25's second half). P0 provisions `hypothesis` and records the requirement; the tests belong to P11 (`lint_prompt_sheet.py`) and P12 (`lint_script_language.py`).
- Renaming `pipeline-app/scripts/` (F-64's full fix). Its three modules are owned by P8 and P10. P0 removes the half of the collision it owns and leaves a machine-checked marker for the rest — see Task 15's **Residual** note.

---

## 2. Finding → task map

Total coverage. Every owned ID appears exactly once as a primary owner; secondary tasks are noted.

| Finding | Sev | Mode | Task(s) | One-line disposition |
|---|---|---|---|---|
| F-60 | S1 | latent | **T22** | `.github/workflows/tests.yml` with `root-suite`, `app-suite`, `no-live-credentials` + weekly schedule |
| F-61 | S1 | silent | **T1**, T3, T22 | Root ini header + a report-header banner on every root run + CI runs both suites explicitly |
| F-63 | S1 | silent | **T4**, T22 | Session-start guard rejects a foreign `pipeline_app`; CI asserts the package is never installed |
| F-02 | S2 | silent | **T24**, T1 | Coverage declared diagnostic-only in both inis; no coverage gate anywhere; PR template demands the finding→test name |
| F-03 | S2 | coverage-gap | **T21** | New nine-stage stubbed-CLI walk |
| F-25 | S2 | coverage-gap | **T12** | `hypothesis` provisioned in both dev manifests; mutation-pass requirement recorded |
| F-27 | S2 | coverage-gap | **T19**, T24 | Doctor's unique reporting asserted; CI + written standard close the policy half |
| F-64 | S2 | latent | **T15**, T14 | Root `scripts` de-packaged; residual (the app-side rename) made machine-visible |
| F-65 | S2 | coverage-gap | **T8** | `conn` + `client` fixtures land in `pipeline-app/tests/conftest.py`; a repo-wide autouse hook now has a home |
| F-70 | S3 | silent | **T10** | `filterwarnings = error` in both inis with three named third-party ignores |
| F-72 | S2 | coverage-gap | **T20**, T21 | Real-CLI test writes to `tmp_path`, renamed to stop claiming e2e; stubbed sibling does the nine-stage walk |
| F-76 | S2 | silent | **T13**, T22 | `yt-dlp` and `youtube-transcript-api` pinned exactly in both manifests; weekly CI surfaces upstream drift |
| F-77 | S2 | loud | **T17** | `run_all.sh` step 2 becomes skippable; step 3 is reachable |
| B-83 | S2 | loud | **T17** | Same change; `copy_youthsports.sh` gains a distinct "source absent" exit code |
| F-01 | S3 | coverage-gap | **T12** | `pytest-cov` in both dev manifests |
| F-66 | S3 | silent | **T9** | Deterministic unclosed-connection detector with a shrink-only allowlist |
| F-71 | S3 | latent | **T11** | `pytest-asyncio` upgraded; `asyncio_mode` and `asyncio_default_fixture_loop_scope` set explicitly |
| F-74 | S3 | coverage-gap | **T12** | `pytest` added to root manifest; test-only deps split into `requirements-dev.txt` at both levels |
| F-75 | S3 | latent | **T14** | `setup.py` gains `install_requires` parsed from the runtime manifest; constraint styles aligned |
| F-78 | S3 | silent | **T18** | `start_pipeline.bat` gates on venv, port, and readiness before opening the browser |
| F-80 | S3 | docs-drift | **T23** | PR template's free-text Verification box replaced by the three CI job names |
| C-105 | S4 | latent | **T15** | Root `scripts/__init__.py` deleted |
| F-79 | S4 | docs-drift | **T16** | `.coverage`, `.coverage.*`, `htmlcov/`, `coverage.xml`, `.pytest_cache/` gitignored |

---

## 3. Tasks

Ordering matters: T1–T11 build the harness the rest of the package's own tests run under. Commit after each task with a conventional-commit message.

Throughout: **root suite** = `python -m pytest tests/ -q` from the repo root; **app suite** = `cd pipeline-app && python -m pytest -q`.

---

### Task 1 — Root `pytest.ini`: register markers, forbid a coverage gate, state the partial-run truth

Closes: **F-61** (primary), **F-02** (partial).

- [ ] **Write the failing test.** Create `tests/test_harness_contract.py`:

```python
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
```

- [ ] **Run it.** `python -m pytest tests/test_harness_contract.py -q` — expect 3 failures: no `markers` key in either ini, no `Coverage is diagnostic only` string, no `ROOT SUITE ONLY` in the first three lines. (`test_both_inis_register_both_opt_in_markers` stays red until Task 2 lands the app ini — that is expected and is the point of asserting both files from the one suite that can read both.)
- [ ] **Implement.** Replace `pytest.ini` with:

```ini
; ROOT SUITE ONLY. A bare `python -m pytest` here collects tests/ -- the Gate C
; and Gate D linters and the skill-provenance checks -- and NOTHING under
; pipeline-app/. That is 201 of the repo's 1,034 tests. It exits 0 having run
; 19% of them (finding F-61). The app suite is a second rootdir:
;
;     cd pipeline-app && python -m pytest
;
; Always `python -m pytest`, never bare `pytest`: only `python -m` prepends the
; cwd to sys.path, and without that an editable install of pipeline-app can
; silently test a different checkout (finding F-63).
;
; Coverage is diagnostic only. 95% line coverage coexisted with 328 confirmed
; defects in the 2026-08-08 audit (finding F-02), so no --cov-fail-under gate is
; configured here and none may be added. The quality bar is the finding->test
; mapping in docs/superpowers/plans/remediation/, not a percentage.
[pytest]
testpaths = tests
addopts = --strict-markers
markers =
    allow_network: this test may make a real outbound request (requests/urllib). Justify in the docstring.
    allow_subprocess: this test may spawn a real child process. Justify in the docstring.
```

- [ ] **Run it.** 2 of 3 pass; `test_both_inis_register_both_opt_in_markers` stays red until Task 2 lands `pipeline-app/pytest.ini` — that is the deliberate T1↔T2 tripwire described in the RED step above, not a regression. Do **not** edit `pipeline-app/pytest.ini` here to make it green; that file is Task 2's. Then run the whole root suite: `python -m pytest tests/ -q` — `--strict-markers` may reject an unregistered marker; if it does, register it here rather than dropping the flag.
- [ ] **Commit.** `test: pin the root pytest.ini contract (F-61, F-02)`

---

### Task 2 — App `pytest.ini`: same contract, plus the run-from-here rule

Closes: **F-61** (app half), **F-02** (app half). Prerequisite for T10 and T11, which add to this file.

- [ ] **Write the failing test.** Create `pipeline-app/tests/test_harness_contract.py`:

```python
"""Regression tests for the P0 harness contract, app-suite half."""
import configparser
import os
import subprocess
import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
APP_INI = APP_ROOT / "pytest.ini"


def _ini(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(inline_comment_prefixes=None)
    parser.read_string(path.read_text(encoding="utf-8"))
    return parser


def test_app_ini_registers_the_two_opt_in_markers():
    markers = _ini(APP_INI)["pytest"]["markers"]
    assert "allow_network" in markers
    assert "allow_subprocess" in markers


def test_app_ini_declares_coverage_diagnostic_and_configures_no_gate():
    text = APP_INI.read_text(encoding="utf-8")
    assert "Coverage is diagnostic only" in text
    assert "--cov-fail-under" not in text
```

- [ ] **Run it.** Both fail (`KeyError: 'markers'`, missing string).
- [ ] **Implement.** Replace `pipeline-app/pytest.ini`'s `[pytest]` block, keeping the existing rootdir explanation and adding:

```ini
[pytest]
testpaths = tests
addopts = --strict-markers
markers =
    allow_network: this test may make a real outbound request (requests/urllib). Justify in the docstring.
    allow_subprocess: this test may spawn a real child process. Justify in the docstring.
```

with this appended to the header comment:

```ini
; Coverage is diagnostic only -- see the repo-root pytest.ini for why no
; --cov-fail-under gate exists here (finding F-02).
```

- [ ] **Run it.** Both pass; then `python -m pytest -q` from `pipeline-app` to confirm `--strict-markers` breaks nothing.
- [ ] **Commit.** `test: pin the app pytest.ini contract (F-61, F-02)`

---

### Task 3 — Root `tests/conftest.py`: a banner on every root run

Closes: **F-61** (the surfacing half).

- [ ] **Write the failing test.** Append to `tests/test_harness_contract.py`:

```python
def test_root_run_header_names_the_app_suite_command():
    from tests.conftest import pytest_report_header

    lines = pytest_report_header(config=None)
    joined = "\n".join(lines)
    assert "ROOT SUITE ONLY" in joined
    assert "cd pipeline-app && python -m pytest" in joined
```

- [ ] **Run it.** `ModuleNotFoundError: No module named 'tests.conftest'`.
- [ ] **Implement.** Create `tests/conftest.py` with the header hook (the guard block arrives in T6):

```python
"""Root-suite conftest: the run banner and the live-call guard.

Sibling: pipeline-app/tests/conftest.py. The guard block between the BEGIN/END
markers below is duplicated there verbatim rather than imported -- the two
suites have separate rootdirs and neither may import from the other's tree
(finding F-64). tests/test_harness_contract.py asserts the two copies stay
byte-identical.
"""
from __future__ import annotations


def pytest_report_header(config):
    return [
        "ROOT SUITE ONLY -- this run collects tests/ (Gate C, Gate D, skill provenance).",
        "The app suite is NOT included. Run it separately:",
        "    cd pipeline-app && python -m pytest",
        "(finding F-61: a bare root run exits 0 having executed 19% of the repo's tests)",
    ]
```

- [ ] **Run it.** Passes. Also run `python -m pytest tests/ -q` and read the header to confirm the banner is visible.
- [ ] **Commit.** `feat(tests): announce that a root run is the root suite only (F-61)`

---

### Task 4 — App conftest: refuse to test a different checkout

Closes: **F-63** (primary).

- [ ] **Write the failing test.** Append to `pipeline-app/tests/test_harness_contract.py`:

```python
def test_session_start_accepts_the_working_tree():
    import conftest

    conftest.pytest_sessionstart(session=None)  # must not raise


def test_session_start_rejects_a_pipeline_app_from_another_checkout(monkeypatch, tmp_path):
    import types

    import conftest

    foreign = tmp_path / "other-checkout" / "pipeline-app" / "pipeline_app"
    foreign.mkdir(parents=True)
    (foreign / "__init__.py").write_text("", encoding="utf-8")
    fake = types.ModuleType("pipeline_app")
    fake.__file__ = str(foreign / "__init__.py")
    monkeypatch.setitem(sys.modules, "pipeline_app", fake)

    with pytest.raises(pytest.UsageError) as excinfo:
        conftest.pytest_sessionstart(session=None)

    message = str(excinfo.value)
    assert str(foreign) in message                       # the wrong tree, named
    assert str(APP_ROOT / "pipeline_app") in message      # the right tree, named
    assert "pip uninstall" in message
```

- [ ] **Run it.** `ModuleNotFoundError: No module named 'conftest'`.
- [ ] **Implement.** Create `pipeline-app/tests/conftest.py`:

```python
"""App-suite conftest: the wrong-tree guard, the live-call guard, the
connection-leak detector, and the shared conn/client fixtures.

Sibling: <repo>/tests/conftest.py. The guard block between the BEGIN/END
markers is duplicated there verbatim, not imported (finding F-64).
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent


def pytest_sessionstart(session):
    """F-63: `pipeline_app` is pip-installed editable against the MAIN checkout.
    Any invocation that does not put this tree first on sys.path tests code the
    author is not editing, and passes or fails on it silently."""
    import pipeline_app

    resolved = Path(pipeline_app.__file__).resolve().parent
    expected = (APP_ROOT / "pipeline_app").resolve()
    if resolved != expected:
        raise pytest.UsageError(
            f"pipeline_app resolves to {resolved}, but this suite is {expected}.\n"
            "An editable install is shadowing the working tree (finding F-63): the "
            "tests would run against a different checkout.\n"
            "Fix: `python -m pip uninstall -y pipeline-app`, then invoke the suite as "
            "`cd pipeline-app && python -m pytest` so python -m's cwd prepend is the "
            "only source of the package."
        )
```

- [ ] **Run it.** Both pass. **Then prove the guard is live.** Note what the guard can and cannot catch, because the original wording of this step was wrong: under `python -m pytest`, Python prepends the cwd to `sys.path`, so from `pipeline-app/` the local `pipeline_app` *always* wins and the guard can never fire — the mandated invocation is safe independently of the guard. The reproducible demonstration is a **bare `pytest`** (no `-m`) run from `pipeline-app/` while a foreign editable install is present: `sys.path` then resolves `pipeline_app` to the other checkout and the suite must abort with the `UsageError` naming both trees, not run. That is the invocation F-63 is actually about — an IDE test runner, a forgotten `-m`, or a misconfigured CI step. Do **not** uninstall a pre-existing machine-wide editable install afterwards; it predates this programme, is shared across checkouts, and leaving it present keeps the guard exercised for real on this machine.
- [ ] **Commit.** `feat(tests): refuse to run the app suite against a foreign checkout (F-63)`

---

### Task 5 — App conftest: the live-call guard

Closes: **F-65** (the "nowhere to put a repo-wide autouse guard" half); it is the mechanism P8 needs for F-68.

- [ ] **Write the failing test.** Append to `pipeline-app/tests/test_harness_contract.py`:

```python
def test_unstubbed_requests_post_is_blocked():
    import requests

    import conftest

    with pytest.raises(conftest.LiveCallBlocked) as excinfo:
        requests.post("https://api.brightdata.com/datasets/v3/trigger", json={})
    assert "BRIGHTDATA_API_KEY" in str(excinfo.value)


def test_unstubbed_urlopen_is_blocked():
    import conftest

    with pytest.raises(conftest.LiveCallBlocked):
        urllib.request.urlopen("https://www.googleapis.com/youtube/v3/search")


def test_unstubbed_subprocess_run_is_blocked():
    import conftest

    with pytest.raises(conftest.LiveCallBlocked):
        subprocess.run(["yt-dlp", "--dump-json", "https://youtube.com/watch?v=x"])


@pytest.mark.allow_subprocess
def test_marked_test_may_spawn_a_real_process():
    result = subprocess.run(
        [sys.executable, "-c", "print('ok')"],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    assert result.stdout.strip() == "ok"


def test_a_stubbed_call_still_wins_over_the_guard(monkeypatch):
    """The guard must never defeat an explicit stub -- 40+ existing tests
    monkeypatch subprocess.run and must keep working."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: "stubbed")
    assert subprocess.run(["anything"]) == "stubbed"
```

(add `import subprocess`, `import sys`, `import urllib.request` to the file's imports)

- [ ] **Run it.** All fail: `AttributeError: module 'conftest' has no attribute 'LiveCallBlocked'`, and the real calls would otherwise attempt the network.
- [ ] **Implement.** Add to `pipeline-app/tests/conftest.py`:

```python
# ---------------------------------------------------------------- BEGIN SHARED GUARD
# Duplicated verbatim in the sibling conftest. Keep the two byte-identical;
# tests/test_harness_contract.py::test_guard_blocks_are_identical asserts it.


class LiveCallBlocked(RuntimeError):
    """A test reached the network or spawned a process without stubbing it."""


_GUARD_MESSAGE = (
    "{what} was called from a test with no stub.\n"
    "BRIGHTDATA_API_KEY, RESEND_API_KEY and YOUTUBE_API_KEY are all present in the "
    "ambient environment on this machine, and Bright Data bills per record: one "
    "forgotten stub spawns a real, billed job and the test still passes (finding F-68).\n"
    "Fix: stub the call. If the test genuinely must be real, mark it "
    "@pytest.mark.{mark} and say why in its docstring.\n"
    "call args: {args!r}"
)


def _blocked(what: str, mark: str):
    def _raise(*args, **kwargs):
        raise LiveCallBlocked(_GUARD_MESSAGE.format(what=what, mark=mark, args=args))

    return _raise


@pytest.fixture(autouse=True)
def _block_live_calls(request, monkeypatch):
    """Autouse: make the outbound seams raise unless the test opts in.

    Runs at setup, so a test's own monkeypatch.setattr in the body or in a
    later fixture overrides it -- an explicit stub always wins.
    """
    module_key = _module_key(request)

    if (
        request.node.get_closest_marker("allow_subprocess") is None
        and module_key not in _SUBPROCESS_ALLOWED_MODULES
    ):
        monkeypatch.setattr(subprocess, "Popen", _blocked("subprocess.Popen", "allow_subprocess"))
        monkeypatch.setattr(subprocess, "run", _blocked("subprocess.run", "allow_subprocess"))
        monkeypatch.setattr(
            asyncio, "create_subprocess_exec",
            _blocked("asyncio.create_subprocess_exec", "allow_subprocess"),
        )

    if request.node.get_closest_marker("allow_network") is None:
        monkeypatch.setattr(
            urllib.request, "urlopen", _blocked("urllib.request.urlopen", "allow_network")
        )
        try:
            import requests
            import requests.sessions
        except ImportError:
            pass
        else:
            for name in ("request", "get", "post", "put", "patch", "delete", "head"):
                monkeypatch.setattr(
                    requests, name, _blocked(f"requests.{name}", "allow_network")
                )
            monkeypatch.setattr(
                requests.sessions.Session, "request",
                _blocked("requests.Session.request", "allow_network"),
            )


# ------------------------------------------------------------------ END SHARED GUARD
```

plus, above the block, the per-suite pieces (these differ between the two files and sit **outside** the markers):

```python
import asyncio

# Modules whose tests legitimately execute a real child process.
#
# KEYED BY OWNING PACKAGE so each remediation agent can find its own entries
# with one grep for its package id and never has to read P0's plan. Add an
# entry only when the child process is the thing under test; everything else
# gets a stub. Entries may be added by the owning package as it needs them --
# unlike _KNOWN_CONNECTION_LEAKS below, this list is not a defect backlog.
#
# There is deliberately NO "P0" entry for tests/test_harness_contract.py. A
# module-level entry disables the guard for the WHOLE file, and that file is
# where the guard's own negative tests live -- with the entry present,
# test_unstubbed_subprocess_run_is_blocked stops asserting a block and instead
# executes the real yt-dlp binary. (Observed during execution: real yt-dlp
# stderr in the test output.) Every P0 test that legitimately spawns a child
# carries @pytest.mark.allow_subprocess on the test itself instead, which is
# the alternative this plan already sanctions in §6.4. Prefer the per-test
# marker over a module entry wherever the file also contains guard tests.
_SUBPROCESS_ALLOWED_BY_PACKAGE: dict[str, dict[str, str]] = {
    "P4": {
        "tests/test_cli_runner.py": "one real asyncio child process at :400",
    },
    "P5": {
        "tests/test_git_helper.py": "builds a fixture repo with a real `git init`",
    },
    "P6": {
        # P6 reported a byte-identity round-trip that spawns sys.executable.
        "tests/test_discovery_youtube.py": "byte-identity round-trip spawns sys.executable",
    },
}

# Flattened once at import; the per-package structure above is the source of truth.
_SUBPROCESS_ALLOWED_MODULES: dict[str, str] = {
    module: f"{package} -- {reason}"
    for package, modules in _SUBPROCESS_ALLOWED_BY_PACKAGE.items()
    for module, reason in modules.items()
}


def _module_key(request) -> str:
    return Path(str(request.node.fspath)).resolve().relative_to(APP_ROOT).as_posix()
```

**P7 note:** P7's Bright Data tests must pass with the network guard *active* — they are stubbed today and must stay stubbed. P7 gets no allowlist entry; if one of its tests fails under the guard, that is the F-68 defect the guard exists to catch, not a guard bug.

- [ ] **Run it.** All five pass. Then run the whole app suite: `python -m pytest -q`. Any newly-failing module is either a missing stub (**fix it if it is P0's file; otherwise add a `_SUBPROCESS_ALLOWED_MODULES` entry naming the owning package and open the follow-up**) or a real allowlist gap.
- [ ] **Commit.** `feat(tests): block unstubbed network and subprocess calls in the app suite (F-65)`

---

### Task 6 — Root conftest: the same guard, plus a drift detector

Closes: **F-65** (root half).

- [ ] **Write the failing test.** Append to `tests/test_harness_contract.py`:

```python
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
```

- [ ] **Run it.** Both fail (`ValueError: substring not found` on the root conftest; no `LiveCallBlocked`).
- [ ] **Implement.** Append the guard block to `tests/conftest.py` **byte-identically**, with the root suite's own per-suite pieces above it:

```python
import asyncio
import subprocess
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Modules whose tests legitimately execute a real child process. Entries name
# the owning package. This list may only shrink.
#
# No entry for tests/test_harness_contract.py, for the same reason the app-side
# conftest has none: that file holds this guard's own negative tests, and a
# module-level entry would exempt them, so the test that proves a subprocess is
# blocked would instead spawn one. The P0 tests that genuinely need a child
# process carry @pytest.mark.allow_subprocess individually.
_SUBPROCESS_ALLOWED_MODULES = {
    "tests/test_resolve_brief_version.py": "P12 -- runs the resolver script as a real CLI at :89",
}


def _module_key(request) -> str:
    return Path(str(request.node.fspath)).resolve().relative_to(REPO_ROOT).as_posix()
```

- [ ] **Run it.** Both pass; then the full root suite. `test_resolve_brief_version.py` must still pass via its allowlist entry.
- [ ] **Commit.** `feat(tests): block unstubbed network and subprocess calls in the root suite (F-65)`

---

### Task 7 — The `no-live-credentials` assertion

Closes: the CI job's payload (feeds **F-60**).

- [ ] **Write the failing test.** Append to `pipeline-app/tests/test_harness_contract.py`:

```python
VENDOR_KEYS = ("BRIGHTDATA_API_KEY", "RESEND_API_KEY", "YOUTUBE_API_KEY")


def test_guard_fires_even_when_every_vendor_key_is_present(monkeypatch):
    """The `no-live-credentials` CI job runs exactly this with canary values in
    the environment. A guard that only works when keys are absent is worthless:
    keys are always present on the operator's machine."""
    import requests

    import conftest

    for key in VENDOR_KEYS:
        monkeypatch.setenv(key, "ci-canary-must-never-be-used")

    with pytest.raises(conftest.LiveCallBlocked):
        requests.post("https://api.brightdata.com/datasets/v3/trigger", json={})
    with pytest.raises(conftest.LiveCallBlocked):
        subprocess.run(["curl", "https://api.resend.com/emails"])
```

Add the mirror in `tests/test_harness_contract.py` using `tests.conftest.LiveCallBlocked`.

- [ ] **Run it.** Passes immediately if T5/T6 landed — this is a *contract* test, not a fault injection, so run it once with the guard temporarily commented out and confirm it fails, then restore. Record that observation in the commit body.
- [ ] **Commit.** `test: prove the live-call guard fires with vendor keys present (F-60)`

---

### Task 8 — Shared `conn` and `client` fixtures

Closes: **F-65** (primary — the 11× / 9× duplication).

- [ ] **Write the failing test.** Append to `pipeline-app/tests/test_harness_contract.py`:

```python
def test_shared_conn_fixture_is_initialised_and_closes(conn):
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stages'").fetchone()
    assert row is not None


def test_shared_client_fixture_serves_the_app(client):
    assert client.get("/doctor").status_code == 200
```

- [ ] **Run it.** `fixture 'conn' not found`.
- [ ] **Implement.** Append to `pipeline-app/tests/conftest.py`:

```python
@pytest.fixture
def conn(tmp_path):
    """The canonical DB fixture. Duplicated in 11 test files today (F-65);
    each package should delete its local copy and use this one.

    yield + unconditional close: 9 of the 11 local copies return without
    closing, which leaks the handle and -- on Windows -- can keep the tmp_path
    file locked through teardown (F-66).
    """
    from pipeline_app import db

    db_path = tmp_path / "pipeline.db"
    schema_path = APP_ROOT / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The canonical FastAPI fixture. Duplicated in 9 test files today (F-65)."""
    from fastapi.testclient import TestClient

    from pipeline_app.main import create_app

    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    with TestClient(app) as test_client:
        yield test_client
```

- [ ] **Run it.** Both pass. Do **not** modify the 11 files that carry local copies — those belong to P2/P3/P4/P5/P10/P15.
- [ ] **Commit.** `feat(tests): add the shared conn and client fixtures (F-65)`

---

### Task 9 — Deterministic unclosed-connection detector

Closes: **F-66** (primary).

- [ ] **Write the failing test.** Append to `pipeline-app/tests/test_harness_contract.py`:

```python
def test_unclosed_detects_an_open_connection(tmp_path):
    import conftest

    connection = sqlite3.connect(tmp_path / "x.db")
    try:
        assert conftest._is_open(connection) is True
    finally:
        connection.close()


def test_unclosed_does_not_flag_a_closed_connection(tmp_path):
    import conftest

    connection = sqlite3.connect(tmp_path / "x.db")
    connection.close()
    assert conftest._is_open(connection) is False


def test_leak_allowlist_entries_all_still_exist():
    """Shrink-only ratchet: an allowlisted module that has been renamed or
    fixed must be removed from the list, not left to rot."""
    import conftest

    for rel in conftest._KNOWN_CONNECTION_LEAKS:
        assert (APP_ROOT / rel).exists(), f"{rel} is allowlisted but does not exist"


def test_both_allowlists_are_keyed_by_owning_package():
    """Every remediation agent must be able to find its own entries with one
    grep for its package id, without reading P0's plan."""
    import conftest
    import re as _re

    for mapping in (conftest._CONNECTION_LEAKS_BY_PACKAGE, conftest._SUBPROCESS_ALLOWED_BY_PACKAGE):
        assert mapping.keys(), "an empty allowlist must be deleted, not left as {}"
        for package in mapping:
            assert _re.fullmatch(r"P\d{1,2}", package), f"{package!r} is not a package id"


@pytest.mark.allow_subprocess
def test_a_leaking_test_fails_with_a_nonzero_exit(tmp_path):
    """Surfacing: the operator-reachable signal is a failed test and a non-zero
    process exit, not a ResourceWarning lost in 58,169 lines (F-70)."""
    (tmp_path / "conftest.py").write_text(
        "import importlib.util\n"
        f"_spec = importlib.util.spec_from_file_location('p0conf', r'{APP_ROOT / 'tests' / 'conftest.py'}')\n"
        "_m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_m)\n"
        "_no_leaked_sqlite_connections = _m._no_leaked_sqlite_connections\n",
        encoding="utf-8",
    )
    (tmp_path / "test_leak.py").write_text(
        "import sqlite3\n"
        "def test_leaks(tmp_path):\n"
        "    sqlite3.connect(tmp_path / 'db.sqlite')\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(tmp_path), "-q", "-p", "no:cacheprovider"],
        capture_output=True, encoding="utf-8", errors="replace", cwd=str(tmp_path),
    )
    assert result.returncode != 0
    assert "sqlite connection" in result.stdout
```

(add `import sqlite3` to the file's imports)

- [ ] **Run it.** All fail — no `_is_open`, no `_KNOWN_CONNECTION_LEAKS`, no `_no_leaked_sqlite_connections`.
- [ ] **Implement.** Add to `pipeline-app/tests/conftest.py` (outside the shared-guard markers):

```python
# Modules that still leak a sqlite connection (finding F-66).
#
# KEYED BY OWNING PACKAGE: grep your package id here to find exactly what you
# own. SHRINK ONLY -- when a package converts its local `conn` fixture to the
# shared yield/close one in this file, it deletes its own entries. A package
# whose dict is empty deletes the dict. Nothing may be ADDED to this list: a
# new leak is a new defect and fails the test that produced it.
_CONNECTION_LEAKS_BY_PACKAGE: dict[str, list[str]] = {
    # populated in the implementation step below by running the suite once,
    # e.g.  "P3": ["tests/test_approval_service.py", "tests/test_preflight.py"],
}

_KNOWN_CONNECTION_LEAKS: dict[str, str] = {
    module: package
    for package, modules in _CONNECTION_LEAKS_BY_PACKAGE.items()
    for module in modules
}


def _is_open(connection: sqlite3.Connection) -> bool:
    try:
        connection.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return False
    return True


@pytest.fixture(autouse=True)
def _no_leaked_sqlite_connections(request, monkeypatch):
    """Deterministic replacement for ResourceWarning, which fires at GC and is
    therefore untestable and unreadable (F-66, F-70)."""
    opened: list[sqlite3.Connection] = []
    real_connect = sqlite3.connect

    def tracking_connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", tracking_connect)
    yield

    leaked = [c for c in opened if _is_open(c)]
    for connection in leaked:
        connection.close()
    if not leaked:
        return
    try:
        module_key = _module_key(request)
    except ValueError:
        # A test file outside APP_ROOT (e.g. the isolated harness spawned by
        # test_a_leaking_test_fails_with_a_nonzero_exit) can never appear in
        # _KNOWN_CONNECTION_LEAKS, which is keyed by paths relative to
        # APP_ROOT. Treat "can't resolve a key" as "not allowlisted" rather
        # than silently skipping the check -- a leak must fail by default.
        # (`return` here made an unresolvable path indistinguishable from a
        # clean test, which is the recurring defect class this programme
        # exists to eliminate, and it defeated this task's own surfacing test.)
        module_key = None
    if module_key in _KNOWN_CONNECTION_LEAKS:
        return
    pytest.fail(
        f"{len(leaked)} sqlite connection(s) left open by {request.node.nodeid}. "
        "Use the shared `conn` fixture from tests/conftest.py, which closes in "
        "teardown (finding F-66). If this module is a known pre-existing leak, "
        "its owning package adds it to _CONNECTION_LEAKS_BY_PACKAGE -- that list "
        "shrinks only; a NEW leak is a new defect."
    )
```

- [ ] **Populate the allowlist.** Run `python -m pytest -q` from `pipeline-app`. Every module that now fails goes into `_CONNECTION_LEAKS_BY_PACKAGE` under its **owning package id**, e.g.

```python
_CONNECTION_LEAKS_BY_PACKAGE: dict[str, list[str]] = {
    "P2": ["tests/test_migrations.py"],
    "P3": ["tests/test_approval_service.py", "tests/test_preflight.py"],
    "P4": ["tests/test_turn_service.py"],
    "P5": ["tests/test_project_service.py"],
    "P10": ["tests/test_migrate_handles.py"],
    "P15": ["tests/test_browse_service.py"],
}
```

  plus any others the run reveals. **P0's own files must not appear** — fix those instead.
- [ ] **Run it.** Suite green; the four new tests pass.
- [ ] **Commit.** `feat(tests): detect leaked sqlite connections deterministically (F-66)`

---

### Task 10 — `filterwarnings = error` in both ini files

Closes: **F-70**.

- [ ] **Write the failing test.** Append to both `test_harness_contract.py` files (root asserts both inis; app asserts its own):

```python
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
```

**Write it as a two-case test, in this shape.** Each ignore line is a hole in the gate, so the test must prove the hole is exactly the shape it claims:

- Build the temp `pytest.ini` from the real one (`testpaths = tests` → `testpaths = .`) **plus one extra line** the test controls: `ignore::UserWarning:ignorable_mod`.
- Write two modules in `tmp_path`: `ignorable_mod.py`, whose function calls `warnings.warn(..., UserWarning)`, and a test file that imports and calls it; plus a second test file that raises the same `UserWarning` from its own module.
- Run pytest once and assert the **repo-module** case fails with a non-zero return code and `UserWarning` in stdout.
- Run pytest again with only the ignorable case collected and assert it **exits 0** — the warning was raised, and the module-scoped ignore is what let it through.
- Assert the two return codes differ. That difference is the whole point: it is what proves a module-scoped ignore distinguishes its own module from every other, rather than the gate being globally on or globally off.

Do **not** try to emit a warning attributable to the real `pytest_asyncio` or `fastapi.routing` modules by shadowing them in `tmp_path`; that fights the plugin loader and is flaky. The three real ignore strings are pinned by `test_third_party_asyncio_deprecations_are_ignored_by_name`, and the zero-warning full-suite run is the empirical evidence they match. This test pins the *mechanism*.

- [ ] **Run it.** All fail — no `filterwarnings` key in either ini.
- [ ] **Implement.** Add to **both** ini files:

```ini
; Unexpected warnings are errors. Before this, 58,169 third-party deprecation
; lines buried the repo's own signal -- the 4 ResourceWarnings for unclosed DB
; connections were invisible inside them (finding F-70). The three ignores below
; are the only third-party sources measured at collection; each names its module
; so a NEW deprecation from the same package still errors.
;
; ResourceWarning stays ignored on purpose, and this is the one bare (module-
; unqualified) ignore here: it fires at GC, so both its timing and the test it
; gets attributed to are nondeterministic, and leaving it as `error` produces
; flaky failures in whichever unrelated test happens to trigger the collection.
;
; Be honest about what that costs. This silences EVERY ResourceWarning in the
; repo -- unclosed files, sockets, and subprocess pipes as well as DB handles.
; The deterministic replacement, _no_leaked_sqlite_connections in
; tests/conftest.py (finding F-66), covers sqlite connections ONLY. For every
; other resource type there is currently no detector, so "no warning" and "a
; non-sqlite handle leaked" are indistinguishable. That residual gap is
; accepted deliberately, not overlooked; narrowing this line by module is not
; possible because GC-time attribution is exactly what is unreliable.
filterwarnings =
    error
    ignore::DeprecationWarning:pytest_asyncio
    ignore::DeprecationWarning:pytest_asyncio.plugin
    ignore::DeprecationWarning:fastapi.routing
    ignore::ResourceWarning
```

- [ ] **Run it.** Run both suites in full. **Every new failure is a real warning.** If it is in a P0 file, fix it. If it is in another package's file, add a targeted `ignore` with a one-line comment naming the module and the owning package, and note it in the commit body as a handoff — never widen to a bare `ignore::DeprecationWarning`.
- [ ] **Commit.** `fix(tests): make unexpected warnings errors in both suites (F-70)`

---

### Task 11 — `pytest-asyncio` upgrade with explicit loop semantics

Closes: **F-71**.

- [ ] **Write the failing test.** Append to `pipeline-app/tests/test_harness_contract.py`:

```python
def test_asyncio_mode_and_loop_scope_are_pinned_explicitly():
    section = _ini(APP_INI)["pytest"]
    assert section["asyncio_mode"] == "strict"
    assert section["asyncio_default_fixture_loop_scope"] == "function"


def test_pytest_asyncio_supports_the_running_interpreter():
    import importlib.metadata

    installed = importlib.metadata.version("pytest-asyncio")
    major = int(installed.split(".")[0])
    assert major >= 1, (
        f"pytest-asyncio {installed} predates Python 3.13; this interpreter is "
        f"{sys.version_info.major}.{sys.version_info.minor} (finding F-71)"
    )
```

- [ ] **Run it.** Both fail (`KeyError: 'asyncio_mode'`; installed 0.24.0).
- [ ] **Implement.**
  1. In `pipeline-app/requirements-dev.txt` (created in T12 — do T12 first if it has not run, or write the line here and let T12 keep it), replace `pytest-asyncio==0.24.*` with `pytest-asyncio==1.2.*`. Verify the pin is real: `python -m pip index versions pytest-asyncio`; if `1.2` is not published, pin the newest release whose metadata lists `Programming Language :: Python :: 3.14`.
  2. `python -m pip install -U -r requirements-dev.txt` in the app venv.
  3. Add to `pipeline-app/pytest.ini`:

```ini
; Set explicitly so a plugin upgrade cannot change event-loop sharing under the
; suite's 17 async tests. 0.24 predates Python 3.13 and was the source of 49,233
; of the warnings in F-70; asyncio.iscoroutinefunction is removed in 3.16, at
; which point the old pin stops working rather than warning (finding F-71).
asyncio_mode = strict
asyncio_default_fixture_loop_scope = function
```

- [ ] **Run it.** Both pass. Then the full app suite — the 17 `@pytest.mark.asyncio` tests in `test_approval_service.py`, `test_cli_runner.py` and `test_turn_service.py` must still pass under strict mode. If pytest-asyncio 1.x removes an API one of them uses, that is P3/P4's fix: record it in the commit body as a handoff rather than editing their files.
- [ ] **Commit.** `chore(deps): upgrade pytest-asyncio and pin loop semantics (F-71)`

---

### Task 12 — Split runtime and test dependencies; add the missing tooling

Closes: **F-74** (primary), **F-01**, **F-25**.

- [ ] **Write the failing test.** Append to `tests/test_harness_contract.py`:

```python
ROOT_REQ = REPO_ROOT / "requirements.txt"
ROOT_DEV = REPO_ROOT / "requirements-dev.txt"
APP_REQ = REPO_ROOT / "pipeline-app" / "requirements.txt"
APP_DEV = REPO_ROOT / "pipeline-app" / "requirements-dev.txt"


def _names(path: Path) -> set[str]:
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            out.add(re.split(r"[<>=!\[]", line, 1)[0].strip().lower())
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
```

- [ ] **Run it.** All three fail (`requirements-dev.txt` does not exist; root manifest has no pytest; `pyyaml>=6.0` vs `pyyaml==6.0.*`).
- [ ] **Implement.**

`requirements.txt` (runtime only, styles aligned with the app manifest):

```
# ContentStudio corpus-archive toolkit — runtime dependencies.
# Install with:  pip install -r requirements.txt
# Test-only dependencies live in requirements-dev.txt (finding F-74).
requests==2.31.*
yt-dlp==2026.7.4
youtube-transcript-api==1.2.4
pyyaml==6.0.*
```

`requirements-dev.txt` (new):

```
# Root-suite test toolchain. CI's `root-suite` job installs this alongside
# requirements.txt. Coverage tooling is here because coverage had never been
# measured on this repo before the 2026-08-08 audit (finding F-01) -- it is
# diagnostic only, never a gate (finding F-02).
-r requirements.txt
pytest==8.3.*
pytest-cov==6.0.*
hypothesis==6.*
```

`pipeline-app/requirements.txt` (runtime only):

```
fastapi==0.115.*
uvicorn[standard]==0.32.*
jinja2==3.1.*
pyyaml==6.0.*
markdown==3.7.*
python-multipart==0.0.*
requests==2.31.*
yt-dlp==2026.7.4
youtube-transcript-api==1.2.4
tzdata>=2024.1
```

`pipeline-app/requirements-dev.txt` (new):

```
# App-suite test toolchain. CI's `app-suite` job installs this alongside
# requirements.txt.
-r requirements.txt
pytest==8.3.*
pytest-asyncio==1.2.*
pytest-cov==6.0.*
httpx==0.27.*
# F-25: no property-based or mutation testing exists anywhere in either suite.
# Provisioned here; the property tests for the two linters belong to P11
# (lint_prompt_sheet.py) and P12 (lint_script_language.py).
hypothesis==6.*
```

- [ ] **Run it.** Three pass. Reinstall both environments from the new files and rerun both suites.
- [ ] **Commit.** `chore(deps): split runtime and test manifests, add coverage and hypothesis (F-74, F-01, F-25)`

---

### Task 13 — Pin the two libraries whose schema the tests freeze

Closes: **F-76**.

- [ ] **Write the failing test.** Append to `tests/test_harness_contract.py`:

```python
def test_yt_dlp_and_transcript_api_are_pinned_exactly_in_both_manifests():
    """F-76: yt-dlp ships frequently and changes --dump-json field names.
    test_discovery_youtube.py:249,309 pin `upload_date` and `duration`; a
    floating requirement means a rename breaks production while the mocked
    tests stay green."""
    for path in (ROOT_REQ, APP_REQ):
        text = path.read_text(encoding="utf-8")
        assert re.search(r"^yt-dlp==\d", text, re.M), f"{path.name}: yt-dlp is not pinned"
        assert re.search(r"^youtube-transcript-api==\d", text, re.M)
        assert ">=" not in re.search(r"^yt-dlp.*$", text, re.M).group(0)
```

- [ ] **Run it.** Fails if T12's manifests were written with `>=`; passes with the exact pins above. If T12 already landed the pins, temporarily revert one line to `yt-dlp>=2025.1.1`, watch the test fail, restore.
- [ ] **Implement.** Already written in T12; this task's job is the test and the weekly-schedule requirement it hands to T22.
- [ ] **Commit.** `test: forbid floating pins on the libraries whose schema tests freeze (F-76)`

---

### Task 14 — `setup.py`: real dependency metadata

Closes: **F-75** (primary), **F-64** (partial).

- [ ] **Write the failing test.** Append to `pipeline-app/tests/test_harness_contract.py`:

```python
def test_setup_py_declares_install_requires_from_the_runtime_manifest():
    import ast

    source = (APP_ROOT / "setup.py").read_text(encoding="utf-8")
    assert "install_requires" in source, "setup.py installs the package and none of its deps (F-75)"

    namespace: dict = {}
    calls: list[dict] = []
    exec(  # noqa: S102 -- executing our own setup.py with setup() stubbed
        source.replace("from setuptools import find_packages, setup",
                       "from setuptools import find_packages"),
        {"setup": lambda **kw: calls.append(kw), "find_packages": lambda **kw: [], "__file__": str(APP_ROOT / "setup.py")},
        namespace,
    )
    # the exec above records the setup() kwargs; assert the dependency list is real
    requires = calls[0]["install_requires"]
    assert "fastapi==0.115.*" in requires
    assert not any(r.startswith("pytest") for r in requires), "test deps must not be install_requires"


def test_setup_py_records_the_unfinished_scripts_rename():
    """F-64 residual: pipeline-app/scripts/ and run_discovery_cron.py are still
    outside the distribution because their modules are owned by P8 and P10."""
    source = (APP_ROOT / "setup.py").read_text(encoding="utf-8")
    assert "F-64" in source
```

- [ ] **Run it.** Both fail.
- [ ] **Implement.** Replace `pipeline-app/setup.py`:

```python
"""Distribution metadata for the pipeline control app.

install_requires is parsed from requirements.txt rather than duplicated, so the
two manifests cannot drift (finding F-75). Test-only dependencies live in
requirements-dev.txt and are deliberately absent here.

RESIDUAL (finding F-64): `scripts/` and `run_discovery_cron.py` sit outside this
distribution and are importable only because `python -m pytest` prepends the
cwd. Bringing them in requires renaming `pipeline-app/scripts/` to
`pipeline_app/scripts/` -- its three modules are owned by other remediation
packages (P8: setup_discovery_task.py; P10: migrate_handles_from_manifest.py,
backfill_youtube_frontmatter.py), so the rename is not P0's to make. Until it
happens the two-suite, two-rootdir rule in CLAUDE.md stands.
"""
from pathlib import Path

from setuptools import find_packages, setup

HERE = Path(__file__).resolve().parent


def _runtime_requirements() -> list[str]:
    out = []
    for raw in (HERE / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            out.append(line)
    return out


setup(
    name="pipeline-app",
    version="0.1.0",
    packages=find_packages(include=["pipeline_app", "pipeline_app.*"]),
    package_data={"pipeline_app": ["templates/*.html", "templates/partials/*.html", "static/*.css"]},
    install_requires=_runtime_requirements(),
    python_requires=">=3.14",
)
```

- [ ] **Run it.** Both pass.
- [ ] **Commit.** `fix(setup): declare install_requires and record the F-64 residual (F-75, F-64)`

---

### Task 15 — Delete the root `scripts` package marker

Closes: **C-105** (primary), **F-64** (partial).

- [ ] **Write the failing test.** Append to `tests/test_harness_contract.py`:

```python
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
```

- [ ] **Run it.** First fails (`spec.origin` is `.../scripts/__init__.py`); second passes.
- [ ] **Implement.** `git rm scripts/__init__.py`. Root `scripts/` becomes a PEP-420 namespace portion: still importable from the repo root (where it is `sys.path[0]`), no longer a regular package that wins the finder race.
- [ ] **Run it.** Both pass. Then the full root suite — `tests/test_resolve_brief_version.py` (P12's file, the only root test that imports `scripts.*`) must still pass unmodified. If it does not, restore `__init__.py` and report the finding as blocked on P12 rather than editing their file.
- [ ] **Commit.** `fix: drop the root scripts package marker that shadows the app's (C-105, F-64)`

---

### Task 16 — Gitignore coverage artifacts

Closes: **F-79**.

- [ ] **Write the failing test.** Append to `tests/test_harness_contract.py`:

```python
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
```

- [ ] **Run it.** All three fail — `.coverage` and `pipeline-app/.coverage` are untracked in the tree right now, and `pipeline-app/logs/` has no entry.
- [ ] **Implement.** Append to `.gitignore`, next to the `__pycache__/` entries:

```gitignore
# Coverage and pytest artifacts. pytest-cov became a standard dependency with
# finding F-74, so a coverage run now leaves these in every working tree; they
# were previously untracked noise a `git add -A` could sweep in (finding F-79).
# Both .coverage paths already exist untracked as of 2026-08-08.
.coverage
.coverage.*
pipeline-app/.coverage
htmlcov/
coverage.xml
.pytest_cache/

# Structured application logs written by pipeline_app/obs.py (P1's error-
# surfacing layer): one app-YYYY-MM-DD.log per day, local diagnostics only.
pipeline-app/logs/
```

- [ ] **Run it.** All three pass. Confirm with `python -m pytest tests/ --cov=scripts -q && git status --porcelain` — no `?? .coverage`.
- [ ] **Note.** `.gitignore` is P0's file. **P1 must not edit it**; the `pipeline-app/logs/` entry above is P0's delivery of P1's requirement.
- [ ] **Commit.** `chore: gitignore coverage artifacts and the obs log directory (F-79)`

---

### Task 17 — Make `run_all.sh` reach step 3

Closes: **F-77** (primary), **B-83**.

- [ ] **Write the failing test.** Append to `tests/test_harness_contract.py`:

```python
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
    brand-intel step must still be announced."""
    for name in ("run_all.sh", "copy_youthsports.sh"):
        (tmp_path / name).write_text((REPO_ROOT / name).read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "download_thinkers.py").write_text("print('thinkers stub')\n", encoding="utf-8")
    (tmp_path / "download_brandintel.py").write_text("print('brandintel stub')\n", encoding="utf-8")
    result = subprocess.run(
        ["bash", "run_all.sh"],
        cwd=str(tmp_path), capture_output=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHON": sys.executable},
    )
    assert result.returncode == 0
    assert "brandintel stub" in result.stdout
    assert "SKIPPED" in result.stdout
```

(add `import os` to the file's imports)

- [ ] **Run it.** All three fail — today the script aborts at step 2 under `set -e` and step 3 never runs.
- [ ] **Implement.**

`copy_youthsports.sh`, replace the `exit 1` branch:

```bash
if [[ ! -d "$SRC" ]]; then
  echo "! Source not found: $SRC" >&2
  echo "  This step needs a sibling checkout with corpus/raisinggoodsports/ present." >&2
  echo "  Not runnable standalone in this repo — see the README's scope note." >&2
  # Exit 3, not 1: run_all.sh treats 3 as "not applicable here, skip and carry
  # on" and any other non-zero as a real failure. With a bare `exit 1` the two
  # were indistinguishable and `set -e` killed the whole run (finding B-83).
  exit 3
fi
```

`run_all.sh`, replace step 2 (lines 25–27):

```bash
echo
echo ">>> [2/3] Youth-sports (RaisingGoodSports research corpus)"
# This corpus's source is a sibling checkout that is absent in this repo by
# design. Under `set -e` a bare call aborted the whole run here and step 3 --
# the brand-intel download, the only corpus-refresh path CLAUDE.md points at --
# was unreachable (findings F-77, B-83).
youth_status=0
bash copy_youthsports.sh || youth_status=$?
if [[ "$youth_status" -eq 3 ]]; then
  echo ">>> [2/3] SKIPPED — sibling corpus/raisinggoodsports/ is not present." >&2
elif [[ "$youth_status" -ne 0 ]]; then
  echo "! [2/3] failed with status $youth_status" >&2
  exit "$youth_status"
fi
```

- [ ] **Run it.** All three pass.
- [ ] **Handoff.** `README.md:55-62` still advertises `./run_all.sh # everything`. `README.md` is **P14's** file. Note in the commit body: "P14 must reconcile the Quick Start's 'everything' claim with the two-of-three reality (B-83)."
- [ ] **Commit.** `fix(scripts): let run_all.sh skip the absent youth-sports corpus (F-77, B-83)`

---

### Task 18 — `start_pipeline.bat` refuses to lie about a successful launch

Closes: **F-78**.

- [ ] **Write the failing test.** Append to `pipeline-app/tests/test_harness_contract.py`:

```python
BAT = APP_ROOT / "start_pipeline.bat"
_windows_only = pytest.mark.skipif(os.name != "nt", reason="Windows batch file")


def _run_bat(tmp_path: Path):
    (tmp_path / "start_pipeline.bat").write_text(BAT.read_text(encoding="utf-8"), encoding="utf-8")
    return subprocess.run(
        ["cmd", "/c", str(tmp_path / "start_pipeline.bat")],
        capture_output=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PIPELINE_APP_LAUNCH_DRYRUN": "1"},
    )


@_windows_only
@pytest.mark.allow_subprocess
def test_missing_venv_exits_nonzero_and_does_not_open_a_browser(tmp_path):
    """Fault: on a missing venv the operator's only signal today is a browser
    connection error while the real message sits in a background window."""
    result = _run_bat(tmp_path)
    assert result.returncode != 0
    assert "venv" in result.stdout.lower()
    assert "OPENING BROWSER" not in result.stdout


@_windows_only
@pytest.mark.allow_subprocess
def test_a_healthy_launch_is_distinguishable_from_a_failed_one(tmp_path):
    """Distinguishability: the two states must not both end in 'browser opens'."""
    scripts = tmp_path / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "activate.bat").write_text("@echo off\r\n", encoding="utf-8")
    ok = _run_bat(tmp_path)

    broken = _run_bat(tmp_path / "no-venv")
    assert ok.returncode == 0
    assert "OPENING BROWSER" in ok.stdout
    assert ok.returncode != broken.returncode
    assert ok.stdout != broken.stdout
```

(create `tmp_path / "no-venv"` inside the test before the second call)

- [ ] **Run it.** Both fail — the current `.bat` has no checks and no dry-run mode.
- [ ] **Implement.** Replace `pipeline-app/start_pipeline.bat`:

```bat
@echo off
setlocal
cd /d "%~dp0"

rem Finding F-78: this script used to `call activate.bat`, sleep 3s, and open the
rem browser unconditionally. A missing venv, a bound port, or a uvicorn crash all
rem still opened a browser, so the operator's foreground signal was a connection
rem error while the real message sat in a background window -- and a second launch
rem opened the browser onto the FIRST instance, possibly against another database.

if not exist ".venv\Scripts\activate.bat" (
  echo [start_pipeline] ERROR: no virtualenv at .venv\Scripts\activate.bat
  echo [start_pipeline] Create it:  python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)
call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo [start_pipeline] ERROR: activating .venv failed with errorlevel %errorlevel%
  exit /b 1
)

netstat -ano -p tcp | findstr /c:"LISTENING" | findstr /c:":8420 " >nul
if not errorlevel 1 (
  echo [start_pipeline] ERROR: port 8420 is already in use.
  echo [start_pipeline] An instance is already running -- refusing to launch a second
  echo [start_pipeline] one that would die silently while the browser opens onto the first.
  exit /b 1
)

if "%PIPELINE_APP_LAUNCH_DRYRUN%"=="1" (
  echo [start_pipeline] DRYRUN: preflight passed. OPENING BROWSER would follow.
  exit /b 0
)

start "ContentStudio Pipeline" cmd /k uvicorn pipeline_app.main:create_default_app --factory --host 127.0.0.1 --port 8420

rem Poll instead of sleeping a fixed 3 seconds: a slow start opened the browser
rem before the server answered, a crashed start opened it anyway.
set /a _tries=0
:waitloop
set /a _tries+=1
curl -s -o nul --max-time 1 http://127.0.0.1:8420/ && goto ready
if %_tries% GEQ 30 (
  echo [start_pipeline] ERROR: server did not answer on 127.0.0.1:8420 after 30s.
  echo [start_pipeline] Read the traceback in the "ContentStudio Pipeline" window.
  exit /b 1
)
timeout /t 1 /nobreak >nul
goto waitloop

:ready
echo [start_pipeline] OPENING BROWSER http://127.0.0.1:8420
start "" http://127.0.0.1:8420
exit /b 0
```

- [ ] **Run it.** Both pass on Windows.
- [ ] **Commit.** `fix(launcher): gate start_pipeline.bat on venv, port, and readiness (F-78)`

---

### Task 19 — Doctor asserts what Doctor uniquely reports

Closes: **F-27** (the one file P0 owns among the five thinnest suites).

`pipeline-app/tests/test_routes_doctor.py` currently holds one test asserting a 200 and the substring `"Claude CLI"` — a string the template hard-codes, so the assertion holds even if every value Doctor reports is wrong.

- [ ] **Write the failing tests.** Replace `pipeline-app/tests/test_routes_doctor.py`:

```python
"""Doctor is the operator's only 'what is this app actually seeing' surface.

Finding F-27: this file held one test asserting a 200 and the substring
"Claude CLI" -- a literal the template hard-codes, true whether or not Doctor
reports anything correctly. These assert the five things Doctor uniquely
reports, each by changing the state and observing the report change.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app


def _app_at(root: Path, monkeypatch, skills: tuple[str, ...] = ()):
    monkeypatch.chdir(root)
    (root / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    skills_dir = root / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    for name in skills:
        (skills_dir / name).mkdir(exist_ok=True)
    return create_app(repo_root=root, db_path=root / "pipeline.db")


def test_doctor_reports_the_repo_root_the_app_is_actually_using(tmp_path, monkeypatch):
    one = tmp_path / "checkout-one"
    one.mkdir()
    resp = TestClient(_app_at(one, monkeypatch)).get("/doctor")
    assert resp.status_code == 200
    assert str(one) in resp.text
    assert str(tmp_path / "checkout-two") not in resp.text


def test_doctor_lists_exactly_the_skills_present_on_disk(tmp_path, monkeypatch):
    app = _app_at(tmp_path, monkeypatch, skills=("shorts-ideation", "voiceover-brief"))
    text = TestClient(app).get("/doctor").text
    assert "shorts-ideation" in text
    assert "voiceover-brief" in text
    assert "music-brief" not in text


def test_doctor_distinguishes_a_missing_cli_from_a_found_one(tmp_path, monkeypatch):
    """Distinguishability: 'CLI absent' and 'CLI present' must not render the
    same page. check_cli_available is the only place the app tells an operator
    the pipeline cannot run at all."""
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: None)
    absent = TestClient(_app_at(tmp_path / "a", monkeypatch)).get("/doctor").text

    monkeypatch.setattr(shutil, "which", lambda name: r"C:\fake\claude.cmd")
    present = TestClient(_app_at(tmp_path / "b", monkeypatch)).get("/doctor").text

    assert "NOT FOUND" in absent
    assert r"C:\fake\claude.cmd" in present
    assert "NOT FOUND" not in present
    assert absent != present


def test_doctor_reports_the_orphaned_turn_count_from_app_state(tmp_path, monkeypatch):
    app = _app_at(tmp_path, monkeypatch)
    app.state.orphaned_count = 7
    assert "7" in TestClient(app).get("/doctor").text
```

(create `tmp_path / "a"` and `tmp_path / "b"` before use)

- [ ] **Run it.** Watch each fail for the right reason first by temporarily breaking `doctor.py`'s corresponding value (change `"repo_root": str(repo_root)` to a literal, then restore). `doctor.py` is **P1's** file — revert every experimental edit before committing; only the test file is P0's to change.
- [ ] **Commit.** `test(doctor): assert what Doctor uniquely reports (F-27)`

---

### Task 20 — Stop the real-CLI test writing into the working tree, and stop it claiming e2e

Closes: **F-72** (the real-CLI half).

- [ ] **Write the failing test.** Append to `pipeline-app/tests/test_harness_contract.py`:

```python
def test_no_test_file_claims_e2e_coverage_it_does_not_have():
    """F-72: test_real_cli_e2e.py covered 1 of 9 stages and asserted only that
    a file existed."""
    integration = APP_ROOT / "tests" / "integration"
    assert not (integration / "test_real_cli_e2e.py").exists()
    assert (integration / "test_real_cli_ideation_only.py").exists()


def test_the_real_cli_test_never_writes_into_the_repo():
    source = (APP_ROOT / "tests" / "integration" / "test_real_cli_ideation_only.py").read_text(
        encoding="utf-8"
    )
    assert "create_project(conn, REPO_ROOT" not in source, (
        "the opt-in test creates <repo>/runs/integration-test-topic-* in the working tree (F-72)"
    )
    assert "create_project(conn, tmp_path" in source
```

- [ ] **Run it.** Both fail.
- [ ] **Implement.** `git mv pipeline-app/tests/integration/test_real_cli_e2e.py pipeline-app/tests/integration/test_real_cli_ideation_only.py`, then edit it:

```python
"""ONE stage, against the real Claude CLI. Not end-to-end -- the nine-stage
walk is test_stubbed_cli_e2e.py. Renamed from test_real_cli_e2e.py because the
old name claimed coverage it did not have (finding F-72).

Still opt-in: it costs real subscription usage.
"""
```

and, in the body:

```python
    result = create_project(conn, tmp_path, "integration-test-topic", "generic", STAGES)
```

with the skills/templates still read from `REPO_ROOT` (the CLI needs the real skills; only the *write* root moves). Add a docstring line to the test:

```python
    # repo_root=tmp_path, not REPO_ROOT: this used to create
    # <repo>/runs/integration-test-topic-<timestamp>/ in the working tree and
    # never clean it up (finding F-72).
```

Strengthen the terminal assertion from `assert latest is not None`:

```python
    assert latest is not None
    body = latest.read_text(encoding="utf-8")
    assert len(body.strip()) > 200, "the CLI produced an artifact with no substance"
    assert not (REPO_ROOT / "runs").exists() or not any(
        p.name.startswith("integration-test-topic") for p in (REPO_ROOT / "runs").iterdir()
    ), "the test wrote into the real working tree"
```

- [ ] **Run it.** Both harness tests pass. The integration test itself stays skipped (`PIPELINE_APP_RUN_INTEGRATION` unset) — that is intended.
- [ ] **Commit.** `test(integration): scope the real-CLI test to tmp_path and rename it (F-72)`

---

### Task 21 — The nine-stage stubbed walk

Closes: **F-03** (primary), **F-72** (the coverage half).

This is the test that catches the class of defect unit tests structurally cannot: a stage not receiving an artifact its `SKILL.md` declares required.

- [ ] **Write the failing test.** Create `pipeline-app/tests/integration/test_stubbed_cli_e2e.py`:

```python
"""The nine-stage walk, with the Claude CLI stubbed at the cli_runner seam.

Finding F-03: the repo's only end-to-end test was opt-in, off by default, and
covered one stage. Finding F-72: nothing in the repo ever walked the chain, and
the handoff defects in Appendix A are exactly what a walk catches.

Stubbed at `cli_runner.stream_claude_turn` rather than with a fake `claude` on
PATH: on Windows `claude` resolves to an npm .cmd shim that platform_argv runs
through `cmd /c`, so a PATH stub tests cmd.exe quoting, not the pipeline. The
seam also hands the test the rendered kickoff prompt, which is the thing worth
asserting on.
"""
import re
from pathlib import Path

import pytest

from pipeline_app import artifacts, cli_runner, db, turn_service
from pipeline_app.pipeline_config import load_stage_defs
from pipeline_app.project_service import create_project

APP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = APP_ROOT.parent
TEMPLATES_DIR = APP_ROOT / "stage_templates"
RAW_OUTPUT_RE = re.compile(r"([A-Za-z]:[^\s`'\"]+raw_output\.md)")


@pytest.fixture
def stub_cli(monkeypatch):
    """Replace the CLI turn with one that writes the artifact the real skill
    would write, and record every prompt it was handed."""
    prompts: list[str] = []

    async def fake_stream(prompt, repo_root, resume_id, settings_path=None):
        prompts.append(prompt)
        match = RAW_OUTPUT_RE.search(prompt)
        assert match, "the kickoff prompt did not name a raw_output path"
        raw = Path(match.group(1))
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text(
            "# Stubbed stage output\n\n"
            "Body written by the stubbed CLI so the next stage has an upstream "
            "artifact to consume.\n",
            encoding="utf-8",
        )
        yield {"type": "system", "subtype": "init", "session_id": f"stub-{len(prompts)}"}
        yield {"type": "result", "subtype": "success", "result": "ok", "total_cost_usd": 0.0}

    monkeypatch.setattr(cli_runner, "stream_claude_turn", fake_stream)
    monkeypatch.setattr(cli_runner, "scoped_permissions_settings", lambda: None)
    return prompts


@pytest.mark.asyncio
async def test_all_nine_stages_run_and_each_receives_its_declared_upstreams(tmp_path, stub_cli):
    stage_defs = load_stage_defs(REPO_ROOT / "pipeline.yaml")
    assert len(stage_defs) == 9, "pipeline.yaml no longer declares nine stages"

    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, APP_ROOT / "pipeline_app" / "schema.sql")
    conn = db.get_connection(db_path)
    try:
        project = create_project(conn, tmp_path, "stubbed-walk", "raisinggoodsports", stage_defs)
        run_dir = project["run_dir"]
        artifact_by_stage: dict[str, Path] = {}

        for stage in stage_defs:
            before = len(stub_cli)
            async for _ in turn_service.run_stage_turn(
                conn, tmp_path, run_dir, TEMPLATES_DIR,
                project["project_id"], project["run_id"], stage, stage_defs,
                f"produce the {stage.id} artifact",
            ):
                pass
            prompt = stub_cli[before]

            for upstream_id in stage.depends_on:
                upstream_path = artifact_by_stage.get(upstream_id)
                assert upstream_path is not None, (
                    f"{stage.id} declares depends_on={upstream_id} but that stage "
                    "produced no artifact"
                )
                assert str(upstream_path) in prompt, (
                    f"{stage.id}'s kickoff prompt does not contain its declared "
                    f"upstream artifact {upstream_path} -- the handoff is broken"
                )

            stage_dir = run_dir / turn_service.stage_dir_name(stage)
            latest = artifacts.latest_artifact_path(stage_dir)
            assert latest is not None, f"{stage.id} produced no artifact"
            artifact_by_stage[stage.id] = latest

        assert set(artifact_by_stage) == {s.id for s in stage_defs}
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_the_walk_writes_nothing_outside_tmp_path(tmp_path, stub_cli):
    """The old integration test created <repo>/runs/... in the working tree
    and never cleaned it up (F-72)."""
    before = {p.name for p in (REPO_ROOT / "runs").iterdir()} if (REPO_ROOT / "runs").exists() else set()
    stage_defs = load_stage_defs(REPO_ROOT / "pipeline.yaml")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, APP_ROOT / "pipeline_app" / "schema.sql")
    conn = db.get_connection(db_path)
    try:
        project = create_project(conn, tmp_path, "isolation-check", "generic", stage_defs)
        async for _ in turn_service.run_stage_turn(
            conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
            project["project_id"], project["run_id"], stage_defs[0], stage_defs,
            "anything",
        ):
            pass
    finally:
        conn.close()
    after = {p.name for p in (REPO_ROOT / "runs").iterdir()} if (REPO_ROOT / "runs").exists() else set()
    assert before == after
```

- [ ] **Run it.** Expect failures on the first pass. Work them one at a time and record which is a **test bug** and which is a **real handoff defect**:
  - `load_stage_defs` may take a different signature — read `pipeline_app/pipeline_config.py` and match it exactly (do not edit that file; it is P4's).
  - `turn_service.stage_dir_name` may be private or named differently — read `turn_service.py` and use the real name.
  - A stage whose gate blocks finalization will have no artifact. If that happens, the assertion is correct and the fix belongs to **P3** (gates) — record it in the commit body as a handoff and mark that stage `xfail(strict=True)` with the finding reference, never delete the assertion.
- [ ] **Run it.** Both pass (or fail only on `xfail(strict=True)` markers naming a handoff).
- [ ] **Commit.** `test(integration): walk all nine stages with a stubbed CLI (F-03, F-72)`

---

### Task 22 — CI

Closes: **F-60** (primary), **F-61**, **F-63**, **F-76** (the weekly-drift half).

- [ ] **Write the failing test.** Append to `tests/test_harness_contract.py`:

```python
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


def test_ci_runs_weekly_so_floating_upstream_changes_surface():
    """F-76: yt-dlp ships frequently; a weekly run turns an ambient break into
    a dated, reviewable one."""
    on = _workflow()[True] if True in _workflow() else _workflow()["on"]
    assert "schedule" in on
    assert on["schedule"][0]["cron"]


def test_ci_configures_no_coverage_gate():
    """F-02: 95% coverage coexisted with 328 defects."""
    assert "--cov-fail-under" not in WORKFLOW.read_text(encoding="utf-8")
```

- [ ] **Run it.** All fail — `.github/workflows/` does not exist.
- [ ] **Implement.** Create `.github/workflows/tests.yml`:

```yaml
# The 1,034 tests in this repo previously ran only when a human remembered, from
# two different directories, with no event that caused them to run (finding F-60).
#
# Three jobs, all windows-latest (the target platform), all `python -m pytest`:
#   root-suite          -- tests/ : Gate C, Gate D, skill provenance
#   app-suite           -- pipeline-app/tests/ : the control app
#   no-live-credentials -- proves the conftest guard fires with vendor keys set
#
# The weekly schedule exists for finding F-76: yt-dlp and youtube-transcript-api
# change their JSON schema, and every test that consumes them is mocked against a
# frozen copy, so the suite stays green while production breaks.
name: tests

on:
  push:
    branches: ["**"]
  pull_request:
  schedule:
    - cron: "17 6 * * 1"
  workflow_dispatch:

concurrency:
  group: tests-${{ github.ref }}
  cancel-in-progress: true

env:
  PYTHONUTF8: "1"
  PIP_DISABLE_PIP_VERSION_CHECK: "1"

jobs:
  root-suite:
    name: root-suite
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - name: Install
        run: python -m pip install -r requirements-dev.txt
      - name: Assert pipeline-app is not installed
        shell: bash
        run: |
          python - <<'PY'
          import importlib.metadata as md, sys
          names = {d.metadata["Name"] for d in md.distributions()}
          if "pipeline-app" in names:
              sys.exit("pipeline-app must not be installed: an editable install can "
                       "shadow the checkout under test (finding F-63)")
          PY
      - name: Root suite
        run: python -m pytest tests/ -q

  app-suite:
    name: app-suite
    runs-on: windows-latest
    defaults:
      run:
        working-directory: pipeline-app
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - name: Install
        run: python -m pip install -r requirements-dev.txt
      - name: Assert pipeline-app is not installed
        shell: bash
        run: |
          python - <<'PY'
          import importlib.metadata as md, sys
          names = {d.metadata["Name"] for d in md.distributions()}
          if "pipeline-app" in names:
              sys.exit("pipeline-app must not be installed: an editable install can "
                       "shadow the checkout under test (finding F-63)")
          PY
      - name: App suite
        run: python -m pytest -q

  no-live-credentials:
    name: no-live-credentials
    runs-on: windows-latest
    env:
      # Canary values. The guard must fire with keys PRESENT -- that is the state
      # on the operator's machine, where one forgotten stub spawns a real,
      # per-record-billed Bright Data job and the test still passes (finding F-68).
      BRIGHTDATA_API_KEY: ci-canary-must-never-be-used
      RESEND_API_KEY: ci-canary-must-never-be-used
      YOUTUBE_API_KEY: ci-canary-must-never-be-used
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - name: Install both toolchains
        run: |
          python -m pip install -r requirements-dev.txt
          python -m pip install -r pipeline-app/requirements-dev.txt
      - name: Root guard
        run: python -m pytest tests/test_harness_contract.py -q -k "guard or blocked or vendor"
      - name: App guard
        working-directory: pipeline-app
        run: python -m pytest tests/test_harness_contract.py -q -k "guard or blocked or vendor"
```

- [ ] **Run it.** The five workflow tests pass. Push the branch and confirm all three jobs go green on GitHub — **this is the verification step; a plan-level green is not enough for F-60.**
- [ ] **Mark all three as required checks** on the default branch's protection rules (repo setting, not a file).
- [ ] **Commit.** `feat(ci): run both suites and the credential guard on every push (F-60, F-61, F-63, F-76)`

---

### Task 23 — PR template names the machine, not the memory

Closes: **F-80**.

- [ ] **Write the failing test.** Append to `tests/test_harness_contract.py`:

```python
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
```

- [ ] **Run it.** Both fail.
- [ ] **Implement.** Replace `.github/PULL_REQUEST_TEMPLATE.md`'s Verification section (lines 13–17) and add the finding row:

```markdown
## Verification

<!-- The three CI jobs in .github/workflows/tests.yml run both suites and the
     credential guard. Confirm the machine ran; do not transcribe its output.
     This box used to accept free text, so "ran the tests, green" satisfied it
     while having run 201 of 1,034 tests (findings F-61, F-80). -->

- [ ] `root-suite` green
- [ ] `app-suite` green
- [ ] `no-live-credentials` green

### Regression test for the defect this fixes

<!-- Required for any change closing an audit finding. Name the finding ID and
     the test you observed FAILING before the fix and passing after. Line
     coverage is diagnostic only and is not evidence (finding F-02). -->

- Finding: <!-- e.g. B-40 -->
- Test: <!-- e.g. pipeline-app/tests/test_discovery_engine.py::test_adapter_fault_exits_nonzero -->

### Manual walkthrough

<!-- Only for things no job can perform. -->
```

- [ ] **Run it.** Both pass.
- [ ] **Commit.** `docs(pr): replace the free-text verification box with the CI job names (F-80)`

---

### Task 24 — Close the policy findings with machine-checked statements

Closes: **F-02** (primary), **F-27** (policy half).

- [ ] **Write the failing test.** Append to `tests/test_harness_contract.py`:

```python
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
```

- [ ] **Run it.** Passes if T1, T2, T22 and T23 landed. Prove it is not vacuous: temporarily add `--cov-fail-under=95` to `requirements-dev.txt`'s comment header, watch the first test fail, remove it.
- [ ] **Run both suites in full, from their own directories.**

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767" && python -m pytest tests/ -q
```
```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app" && python -m pytest -q
```

- [ ] **Commit.** `test: forbid a coverage gate and pin the written test standard (F-02, F-27)`

---

## 4. Finding → test map

Every owned finding, the named test that proves it closed, and — for the seven `silent` findings — which Three-Test-Rule role each test plays.

| Finding | Mode | Test(s) | Role |
|---|---|---|---|
| **F-60** | latent | `tests/test_harness_contract.py::test_ci_defines_the_three_required_jobs` · `::test_ci_runs_both_suites_with_python_m_and_never_a_bare_pytest` | — (plus the live observation that all three jobs go green, recorded in T22) |
| **F-61** | **silent** | `::test_root_run_header_names_the_app_suite_command` | **surfacing** — every root run prints the banner |
| | | `::test_root_ini_states_that_a_bare_run_is_the_root_suite_only` | **fault** — the partial run is declared partial at its source of truth |
| | | `::test_ci_runs_both_suites_with_python_m_and_never_a_bare_pytest` | **distinguishability** — CI's green covers both trees; a local root green provably does not |
| **F-63** | **silent** | `pipeline-app/tests/test_harness_contract.py::test_session_start_rejects_a_pipeline_app_from_another_checkout` | **fault** — a foreign tree aborts the session |
| | | `::test_session_start_accepts_the_working_tree` | **distinguishability** — the legitimate tree is not rejected; the two states differ |
| | | `tests/test_harness_contract.py::test_ci_asserts_pipeline_app_is_never_installed` | **surfacing** — a required CI job fails, non-zero exit |
| **F-02** | **silent** | `::test_no_coverage_gate_exists_anywhere_in_the_harness` | **fault** — a coverage gate anywhere in the harness fails the suite |
| | | `::test_the_quality_bar_is_stated_as_the_finding_to_test_mapping` | **distinguishability** — "covered" and "verified" are named as different things in both inis |
| | | `::test_pr_template_names_the_three_ci_jobs_as_checkboxes` | **surfacing** — every PR renders the requirement |
| **F-03** | coverage-gap | `pipeline-app/tests/integration/test_stubbed_cli_e2e.py::test_all_nine_stages_run_and_each_receives_its_declared_upstreams` | — |
| **F-25** | coverage-gap | `tests/test_harness_contract.py::test_both_dev_manifests_carry_the_test_toolchain` | — |
| **F-27** | coverage-gap | `pipeline-app/tests/test_routes_doctor.py::test_doctor_distinguishes_a_missing_cli_from_a_found_one` · `::test_doctor_lists_exactly_the_skills_present_on_disk` · `::test_doctor_reports_the_repo_root_the_app_is_actually_using` · `::test_doctor_reports_the_orphaned_turn_count_from_app_state` · `tests/test_harness_contract.py::test_the_quality_bar_is_stated_as_the_finding_to_test_mapping` | — |
| **F-64** | latent | `tests/test_harness_contract.py::test_root_scripts_is_not_a_regular_package` · `pipeline-app/tests/test_harness_contract.py::test_setup_py_records_the_unfinished_scripts_rename` | — |
| **F-65** | coverage-gap | `pipeline-app/tests/test_harness_contract.py::test_shared_conn_fixture_is_initialised_and_closes` · `::test_shared_client_fixture_serves_the_app` · `::test_unstubbed_requests_post_is_blocked` · `tests/test_harness_contract.py::test_guard_blocks_are_identical_in_both_conftests` | — |
| **F-66** | **silent** | `pipeline-app/tests/test_harness_contract.py::test_unclosed_detects_an_open_connection` | **fault** — an open connection is detected, deterministically |
| | | `::test_unclosed_does_not_flag_a_closed_connection` | **distinguishability** — leaked ≠ correctly-closed; no false positive |
| | | `::test_a_leaking_test_fails_with_a_nonzero_exit` | **surfacing** — a failed test and non-zero exit, not a GC-time warning |
| **F-70** | **silent** | `::test_a_repo_warning_fails_the_run_while_a_pytest_asyncio_one_does_not` | **fault** + **distinguishability** — a repo warning errors; the 58,169 third-party lines do not |
| | | `tests/test_harness_contract.py::test_both_inis_turn_unexpected_warnings_into_errors` · `::test_third_party_asyncio_deprecations_are_ignored_by_name` | **surfacing** — non-zero exit is configured in both suites |
| **F-71** | latent | `pipeline-app/tests/test_harness_contract.py::test_asyncio_mode_and_loop_scope_are_pinned_explicitly` · `::test_pytest_asyncio_supports_the_running_interpreter` | — |
| **F-72** | coverage-gap | `::test_no_test_file_claims_e2e_coverage_it_does_not_have` · `::test_the_real_cli_test_never_writes_into_the_repo` · `pipeline-app/tests/integration/test_stubbed_cli_e2e.py::test_the_walk_writes_nothing_outside_tmp_path` | — |
| **F-74** | coverage-gap | `tests/test_harness_contract.py::test_both_dev_manifests_carry_the_test_toolchain` · `::test_runtime_manifests_carry_no_test_only_dependencies` | — |
| **F-01** | coverage-gap | `::test_both_dev_manifests_carry_the_test_toolchain` (asserts `pytest-cov` in both) | — |
| **F-75** | latent | `pipeline-app/tests/test_harness_contract.py::test_setup_py_declares_install_requires_from_the_runtime_manifest` · `tests/test_harness_contract.py::test_shared_libraries_use_one_constraint_style_across_the_two_manifests` | — |
| **F-76** | **silent** | `::test_yt_dlp_and_transcript_api_are_pinned_exactly_in_both_manifests` | **fault** — a floating pin fails the suite |
| | | same test's `">=" not in …` assertion | **distinguishability** — an exact pin is textually distinguishable from a floating one |
| | | `::test_ci_runs_weekly_so_floating_upstream_changes_surface` | **surfacing** — a dated, reviewable CI failure instead of a quiet `no_new_content` |
| **F-77** | loud | `::test_run_all_reaches_step_three_when_the_sibling_corpus_is_absent` · `::test_run_all_treats_the_youth_sports_step_as_skippable` | — |
| **B-83** | loud | `::test_copy_youthsports_uses_a_distinct_exit_code_for_a_missing_source` · `::test_run_all_reaches_step_three_when_the_sibling_corpus_is_absent` | — |
| **F-78** | **silent** | `pipeline-app/tests/test_harness_contract.py::test_missing_venv_exits_nonzero_and_does_not_open_a_browser` | **fault** — a missing venv exits non-zero |
| | | `::test_a_healthy_launch_is_distinguishable_from_a_failed_one` | **distinguishability** — success and failure no longer both end in "browser opens" |
| | | the same test's `"OPENING BROWSER" in ok.stdout` / `not in broken.stdout` pair | **surfacing** — the operator's console carries the verdict, in the foreground window |
| **F-79** | docs-drift | `tests/test_harness_contract.py::test_coverage_artifacts_are_gitignored` · `::test_the_obs_log_directory_is_gitignored` · `::test_git_status_is_clean_after_a_coverage_run` | — |
| **F-80** | docs-drift | `::test_pr_template_names_the_three_ci_jobs_as_checkboxes` · `::test_pr_template_job_names_match_the_workflow_exactly` | — |
| **C-105** | latent | `::test_root_scripts_is_not_a_regular_package` · `::test_root_scripts_modules_still_import_by_name` | — |

---

## 5. Tests deleted or inverted

P0 owns no defect-affirming test from the audit's list of six (those are in P6, P7 and P13's files). Two changes to existing tests, both in P0-owned files:

| File:line | Existing test | Disposition | Replacement |
|---|---|---|---|
| `pipeline-app/tests/test_routes_doctor.py:9-17` | `test_doctor_page_renders_without_real_claude_installed` — asserts `resp.status_code == 200` and `"Claude CLI" in resp.text`. The substring is a **literal hard-coded in `doctor.html:7`**, so the assertion holds when every value Doctor reports is wrong. This is the anti-tautology rule's "assert on effect, not on echo". | **Deleted** in Task 19 | Four effect-based tests: `test_doctor_reports_the_repo_root_the_app_is_actually_using`, `test_doctor_lists_exactly_the_skills_present_on_disk`, `test_doctor_distinguishes_a_missing_cli_from_a_found_one`, `test_doctor_reports_the_orphaned_turn_count_from_app_state` |
| `pipeline-app/tests/integration/test_real_cli_e2e.py:22-40` (whole file) | `test_real_ideation_turn_produces_an_artifact` — named and filed as end-to-end; walks 1 of 9 stages, asserts only `latest is not None`, and passes `REPO_ROOT` as the write root so it creates `<repo>/runs/integration-test-topic-<timestamp>/` in the working tree. The **filename** claims coverage the test does not have. | **Renamed + inverted-scope** in Task 20; the coverage claim moves to a real nine-stage test in Task 21 | File → `test_real_cli_ideation_only.py`; `create_project(conn, REPO_ROOT, …)` → `create_project(conn, tmp_path, …)`; `assert latest is not None` gains a substance assertion and a "wrote nothing into the real tree" assertion. New sibling `test_stubbed_cli_e2e.py` carries the nine-stage walk. |

No other existing test is deleted, inverted, or weakened by this package. Task 10's `filterwarnings = error` and Task 9's leak detector are both expected to surface failures in **other packages'** test files; those are recorded as allowlist entries naming the owning package (a shrink-only backlog), never by deleting or weakening the test that failed.

---

## 6. Handoffs to other packages

Recorded here so the orchestrator can route them; **P0 does not act on any of these.**

1. **P1 — `.gitignore` is delivered, not delegated.** `pipeline-app/logs/` is added by Task 16. P1 does not edit `.gitignore`; if `obs.py`'s log path changes, P1 tells P0 rather than editing the file.
2. **P14 — `README.md`.** Lines 55–62 advertise `./run_all.sh # everything`. After Task 17 the script runs two of three corpora in this repo. The Quick Start must say so (B-83).
3. **P8, P10 — `pipeline-app/scripts/`.** F-64's full fix is renaming that package to `pipeline_app/scripts/` so a single root `pytest.ini` can name both trees. The orchestrator is polling both packages. **If both accept:** the rename must land in the *same commit* as their import updates (`tests/test_setup_discovery_task.py:3`, `tests/test_migrate_handles.py:7`, `tests/test_backfill_youtube_frontmatter.py:4`, plus the route/argv call sites) — a split commit leaves the app suite uncollectable — and P0 then adds a task merging the two inis into one `testpaths = tests pipeline-app/tests`. **If either declines:** the partial close in Tasks 14 and 15 stands and the residual stays recorded in `setup.py`, kept visible by `test_setup_py_records_the_unfinished_scripts_rename`.
4. **P5, P6 — the opt-in markers.** `allow_subprocess` and `allow_network` are registered in **both** `pytest.ini` files (Tasks 1 and 2) because the two suites are collected independently. P5's `tests/test_git_helper.py` and P6's byte-identity round-trip (which spawns `sys.executable`) are pre-entered in `_SUBPROCESS_ALLOWED_BY_PACKAGE`; either package may instead mark individual tests `@pytest.mark.allow_subprocess` and delete its module-level entry.
5. **P7 — no allowlist entry, by design.** The Bright Data tests are stubbed today and must pass with the network guard active. A failure there is the F-68 defect the guard exists to catch.
6. **P2, P3, P4, P5, P10, P15 — `_CONNECTION_LEAKS_BY_PACKAGE`.** Keyed by package id in `pipeline-app/tests/conftest.py`: grep your id, convert your local `conn` fixture to the shared one, delete your entry. Shrink only (F-66).
7. **All packages — the duplicated fixtures.** `conn` and `client` now exist in `conftest.py`; the 11 and 9 local copies are each owning package's to delete (F-65).
8. **P11, P12 — property tests.** `hypothesis` is installed and pinned. The property-based checks for `lint_prompt_sheet.py` and `lint_script_language.py`, and the one-off mutation pass over `lint_prompt_sheet.py`, are theirs (F-25).
9. **P3, P4 — anything Task 21 turns up.** Any `xfail(strict=True)` the nine-stage walk needs is a live handoff, not a P0 defect.
