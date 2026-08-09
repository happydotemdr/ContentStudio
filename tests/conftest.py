"""Root-suite conftest: the run banner and the live-call guard.

Sibling: pipeline-app/tests/conftest.py. The guard block between the BEGIN/END
markers below is duplicated there verbatim rather than imported -- the two
suites have separate rootdirs and neither may import from the other's tree
(finding F-64). tests/test_harness_contract.py asserts the two copies stay
byte-identical.
"""
from __future__ import annotations

import asyncio
import subprocess
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Modules whose tests legitimately execute a real child process. Entries name
# the owning package. This list may only shrink. A module-wide entry here
# disables the guard for the whole file, so P0's own negative test
# (tests/test_harness_contract.py::test_root_suite_blocks_an_unstubbed_subprocess)
# deliberately has NO entry -- any P0 test that genuinely needs a real child
# process carries @pytest.mark.allow_subprocess on the test itself instead.
_SUBPROCESS_ALLOWED_MODULES = {
    "tests/test_resolve_brief_version.py": "P12 -- runs the resolver script as a real CLI at :89",
}


def _module_key(request) -> str:
    return Path(str(request.node.fspath)).resolve().relative_to(REPO_ROOT).as_posix()


def pytest_report_header(config):
    return [
        "ROOT SUITE ONLY -- this run collects tests/ (Gate C, Gate D, skill provenance).",
        "The app suite is NOT included. Run it separately:",
        "    cd pipeline-app && python -m pytest",
        "(finding F-61: a bare root run exits 0 having executed 19% of the repo's tests)",
    ]


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
