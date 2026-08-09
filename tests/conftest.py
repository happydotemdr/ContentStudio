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
