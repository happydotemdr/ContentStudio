#!/usr/bin/env python3
"""Fail-closed pin-freshness check for CI's scheduled run only (finding F-76).

A weekly rerun of this repo's mocked suites cannot detect yt-dlp /
youtube-transcript-api schema drift -- both libraries are pinned exactly and
every consuming test is mocked against a frozen copy (see the comment in
.github/workflows/tests.yml). This script is the real signal: it reads each
manifest's exact `==` pin for each tracked library and compares it against
PyPI's full release list.

Every (manifest, library) pair reaches exactly one of three verdicts --
FRESH, STALE, or UNDETERMINED -- and no pair is ever skipped. UNDETERMINED
covers both "no pin line found at all" and "a pin line exists but is not a
plain `==<digits>` pin" (e.g. `yt-dlp==2026.7.4rc1` after a pre-release
bump, or a compound spec). It is a FAILURE, not a skip: a prior version of
this check (embedded directly in the workflow YAML, where nothing could
unit-test it) returned None from its pin parser and `continue`d past an
unparseable pin, and tracked "did anything parse" per-library-across-all-
manifests rather than per-manifest-per-library -- so one library parsing
anywhere was enough to declare overall success while yt-dlp, pinned to
`2026.7.4rc1` in both manifests, was silently never checked at all. That is
exactly the "nothing here vs. something is wrong" defect this whole audit
exists to remove, reproduced one layer down inside the fix for it.

UNDETERMINED and STALE are surfaced with different exit codes because they
are different problems for a human: one means "the pin is behind," the
other means "this script could not tell" and needs a human to look, not an
automatic bump.

Stdlib only: loaded by file path / `python -m`, no app imports -- the
existing convention for scripts/** (see scripts/lint_prompt_sheet.py).

Usage: python -m scripts.check_pin_freshness
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFESTS: tuple[Path, ...] = (
    REPO_ROOT / "requirements.txt",
    REPO_ROOT / "pipeline-app" / "requirements.txt",
)
LIBRARIES: tuple[str, ...] = ("yt-dlp", "youtube-transcript-api")

NUMERIC_RELEASE_RE = re.compile(r"^\d+(\.\d+)*$")

FRESH = "FRESH"
STALE = "STALE"
UNDETERMINED = "UNDETERMINED"

FetchVersions = Callable[[str], list[str]]


@dataclass(frozen=True)
class Result:
    manifest: str
    library: str
    verdict: str
    message: str


def fetch_versions(library: str) -> list[str]:
    """Real fetcher: PyPI's JSON API, oldest-to-newest plain numeric releases.

    Only ever reached with the default argument in production. Every test
    injects a stub instead -- this parameter is the seam that makes that
    possible. (tests/conftest.py's autouse guard blocks an unstubbed
    urllib.request.urlopen from any test that doesn't opt in, and correctly
    so: a test that forgot to stub this would otherwise hit the real
    network.)
    """
    url = f"https://pypi.org/pypi/{library}/json"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.load(resp)
    versions = [v for v in data["releases"] if NUMERIC_RELEASE_RE.match(v)]
    versions.sort(key=lambda v: tuple(int(part) for part in v.split(".")))
    return versions


def _pin_line(text: str, library: str) -> str | None:
    """Any `<library>==...` line, whatever the spec looks like."""
    pattern = re.compile(rf"^{re.escape(library)}==.*$", re.M)
    match = pattern.search(text)
    return match.group(0) if match else None


def _exact_pin(text: str, library: str) -> str | None:
    """The one spec shape this script can confidently compare: `==<digits>`."""
    pattern = re.compile(rf"^{re.escape(library)}==(\d[\d.]*)$", re.M)
    match = pattern.search(text)
    return match.group(1) if match else None


def check_one(
    manifest_label: str,
    manifest_text: str,
    library: str,
    fetch_versions_fn: FetchVersions = fetch_versions,
) -> Result:
    """Classify one (manifest, library) pair. Always returns a Result --
    never skips the pair, so a caller can never lose one silently."""
    raw_line = _pin_line(manifest_text, library)
    if raw_line is None:
        return Result(
            manifest_label, library, UNDETERMINED,
            f"{manifest_label}: no `{library}==` pin found; freshness undetermined.",
        )

    exact = _exact_pin(manifest_text, library)
    if exact is None:
        return Result(
            manifest_label, library, UNDETERMINED,
            f"{manifest_label}: {library} pin {raw_line!r} is not a plain "
            f"`{library}==<digits>` pin -- cannot compare it to PyPI. "
            f"Re-verify the pin by hand.",
        )

    try:
        versions = fetch_versions_fn(library)
    except Exception as exc:  # noqa: BLE001 - reported as UNDETERMINED, never swallowed
        return Result(
            manifest_label, library, UNDETERMINED,
            f"{manifest_label}: could not fetch {library}'s release list from "
            f"PyPI ({type(exc).__name__}: {exc}); freshness undetermined.",
        )

    if exact not in versions:
        return Result(
            manifest_label, library, UNDETERMINED,
            f"{manifest_label}: {library}=={exact} is not a release PyPI's "
            f"index recognizes; cannot place it. Re-verify the pin by hand.",
        )

    behind = len(versions) - 1 - versions.index(exact)
    if behind > 0:
        return Result(
            manifest_label, library, STALE,
            f"{manifest_label}: {library}=={exact} is {behind} release"
            f"{'s' if behind != 1 else ''} behind PyPI latest ({versions[-1]}); "
            f"re-verify the mocked schema before bumping.",
        )

    return Result(
        manifest_label, library, FRESH, f"{manifest_label}: {library}=={exact} is current."
    )


def run(
    manifests: Sequence[Path] = MANIFESTS,
    libraries: Sequence[str] = LIBRARIES,
    fetch_versions_fn: FetchVersions = fetch_versions,
) -> list[Result]:
    """Every (manifest, library) pair produces exactly one Result -- len(result) ==
    len(manifests) * len(libraries), always."""
    results: list[Result] = []
    for manifest_path in manifests:
        text = manifest_path.read_text(encoding="utf-8")
        label = str(manifest_path)
        for library in libraries:
            results.append(check_one(label, text, library, fetch_versions_fn))
    return results


def main(
    manifests: Sequence[Path] = MANIFESTS,
    libraries: Sequence[str] = LIBRARIES,
    fetch_versions_fn: FetchVersions = fetch_versions,
) -> int:
    results = run(manifests, libraries, fetch_versions_fn)

    for result in results:
        prefix = "" if result.verdict == FRESH else "::error::"
        print(f"{prefix}{result.verdict}: {result.message}")

    undetermined = [r for r in results if r.verdict == UNDETERMINED]
    stale = [r for r in results if r.verdict == STALE]

    # UNDETERMINED and STALE get different exit codes on purpose (see module
    # docstring): "the pin is stale" and "this script could not tell" must
    # never look alike to whoever reads the run.
    if undetermined:
        print(
            f"::error::pin-freshness check could not determine freshness for "
            f"{len(undetermined)} pin(s) -- treat as a failure, not a pass."
        )
        return 2
    if stale:
        print(f"::error::pin-freshness check found {len(stale)} stale pin(s).")
        return 1

    print("Pin freshness check passed: all tracked pins are current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
