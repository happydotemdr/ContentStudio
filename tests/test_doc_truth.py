"""Executable checks on the repo's own documentation.

Every assertion here corresponds to a claim some README or CLAUDE.md makes about the
code. The audit (2026-08-08) found four such claims false at once, all of them written
once and never checked again. These tests are the checking.

Stdlib + pytest only. No app imports -- the root suite must stay import-free of
pipeline_app, and these read documents as text anyway.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CLAUDE_MD = REPO / "CLAUDE.md"

# Each probe is (regex, destination-label). A match is an outbound call site.
# Adding a network dependency means adding its probe here AND its row to
# CLAUDE.md -- the test below fails until both exist.
#
# The CDN probe should match nothing: P15 vendored htmx to static/ and deleted the
# unpkg.com reference. It stays as a reintroduction guard, redundant with -- not a
# replacement for -- P15's own templates/** check.
OUTBOUND_PROBES = [
    (re.compile(r"""<script[^>]+src=["']https?://"""), "third-party CDN"),
    (re.compile(r"\brequests\.(?:get|post|put|patch|delete)\s*\("), "requests"),
    (re.compile(r"\burllib\.request\.urlopen\s*\("), "urllib"),
    (re.compile(r"""\[\s*["']yt-dlp["']|["']yt-dlp["']\s*,\s*["']"""), "yt-dlp subprocess (inline argv)"),
    (re.compile(r"(?<!def )\b_run_ytdlp\s*\("), "yt-dlp subprocess (centralized helper)"),
    (re.compile(r"\bYouTubeTranscriptApi\s*\("), "youtube-transcript-api"),
    (re.compile(r"(?<!def )\bplatform_argv\s*\("), "claude subprocess"),
    (re.compile(r"\bsession\.get\s*\("), "requests session"),
    (re.compile(r"(?<!def )\bhttp_get\s*\("), "download_brandintel.py http_get() helper (shared by bsky + rss)"),
]

SCANNED = [
    "pipeline-app/pipeline_app/**/*.py",
    "pipeline-app/pipeline_app/templates/*.html",
    "pipeline-app/tools/*.py",    # post-F-64 rename of pipeline-app/scripts/
    "download_*.py",
]

# A table row cites one path and one or more line numbers:
#   `pipeline_app/brightdata_job.py:64` (trigger), `:76` (poll), `:86` (fetch)
ROW_PATH_RE = re.compile(r"`([\w./-]+\.(?:py|html)):(\d+)`")
ROW_EXTRA_LINE_RE = re.compile(r"`:(\d+)`")


def _measured_call_sites() -> set[str]:
    found = set()
    for pattern in SCANNED:
        for path in REPO.glob(pattern):
            if "test" in path.parts or path.name.startswith("test_"):
                continue
            rel = path.relative_to(REPO).as_posix()
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if line.lstrip().startswith("#"):
                    continue
                if any(rx.search(line) for rx, _ in OUTBOUND_PROBES):
                    found.add(f"{rel}:{lineno}")
    return found


def _network_section() -> str:
    text = CLAUDE_MD.read_text(encoding="utf-8")
    return text[text.index("- **Local only**"): text.index("- **Adding a discovery platform.**")]


def _normalise(path_token: str) -> str:
    """CLAUDE.md cites app modules as `pipeline_app/x.py`; make it repo-relative."""
    if not (REPO / path_token).exists() and (REPO / "pipeline-app" / path_token).exists():
        return f"pipeline-app/{path_token}"
    return path_token


def _documented_call_sites() -> set[str]:
    cited = set()
    for row in _network_section().splitlines():
        anchors = ROW_PATH_RE.findall(row)
        if not anchors:
            continue
        rel = _normalise(anchors[0][0])
        linenos = {lineno for _, lineno in anchors} | set(ROW_EXTRA_LINE_RE.findall(row))
        cited |= {f"{rel}:{lineno}" for lineno in linenos}
    return cited


def _documented_destinations() -> set[str]:
    """First cell of every table row that carries a call-site citation."""
    return {
        row.split("|")[1].strip()
        for row in _network_section().splitlines()
        if row.lstrip().startswith("|") and ROW_PATH_RE.search(row)
    }


def test_claude_md_lists_every_outbound_call_site():
    measured = _measured_call_sites()
    documented = _documented_call_sites()
    undocumented = sorted(measured - documented)
    phantom = sorted(documented - measured)
    assert not undocumented, (
        "outbound call sites in the code but not in CLAUDE.md's network table:\n  "
        + "\n  ".join(undocumented)
        + "\nAdd a row, or remove the dependency."
    )
    assert not phantom, (
        "CLAUDE.md's network table cites call sites that no longer exist:\n  "
        + "\n  ".join(phantom)
    )


COUNT_RE = re.compile(
    r"\*\*(\d+)\*\*\s+outbound call sites? across\s+\*\*(\d+)\*\*\s+destinations"
)


def test_claude_md_network_counts_match_its_own_table():
    text = CLAUDE_MD.read_text(encoding="utf-8")
    match = COUNT_RE.search(text)
    assert match, "CLAUDE.md must state the call-site and destination counts in the documented form"
    claimed_sites, claimed_dests = int(match.group(1)), int(match.group(2))
    assert claimed_sites == len(_measured_call_sites()), (
        "CLAUDE.md's call-site count disagrees with the measured code"
    )
    rows = _documented_destinations()  # distinct values in the table's first column
    assert claimed_dests == len(rows), "CLAUDE.md's destination count disagrees with its own table"


APPENDIX_F = REPO / "docs" / "audit" / "appendix-F-tests.md"
COUNT_CLAIM_RE = re.compile(r"`(test_\w+\.py)`\s*\|\s*\*{0,2}(\d+)\*{0,2}\s*\|")


def test_appendix_f_does_not_repeat_the_retracted_turn_service_count():
    text = APPENDIX_F.read_text(encoding="utf-8")
    stale = re.findall(r"\b2[- ]test\b[^\n]*turn_service", text)
    assert not stale, f"appendix-F still asserts the retracted 2-test count (F-29): {stale}"


@pytest.mark.allow_subprocess
def test_appendix_f_test_counts_match_collection():
    if os.environ.get("DOC_TRUTH_CHILD"):
        pytest.skip("child collection run; do not recurse")
    text = APPENDIX_F.read_text(encoding="utf-8")
    env = {**os.environ, "DOC_TRUTH_CHILD": "1"}
    wrong = []
    for filename, claimed in COUNT_CLAIM_RE.findall(text):
        for cwd, sub in ((REPO, "tests"), (REPO / "pipeline-app", "tests")):
            target = cwd / sub / filename
            if not target.exists():
                continue
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "--collect-only", "-q",
                 "-p", "no:cacheprovider", f"{sub}/{filename}"],
                cwd=cwd, capture_output=True, encoding="utf-8", errors="replace", env=env,
            )
            found = re.search(r"(\d+) tests? collected", proc.stdout)
            if found and int(found.group(1)) != int(claimed):
                wrong.append(f"{filename}: appendix says {claimed}, collects {found.group(1)}")
    assert not wrong, (
        "appendix-F test counts are stale -- `grep -c 'def test_'` is not a test count "
        f"(F-29): {wrong}"
    )


AUDIT = REPO / "docs" / "audit"
PLANS = REPO / "docs" / "superpowers" / "plans" / "remediation"
FINDING_HEADING_RE = re.compile(r"^###\s+([A-F]-\d{2,3})\s+·", re.MULTILINE)
FINDING_REF_RE = re.compile(r"\b([A-F]-\d{2,3})\b")
TASK_MAP_HEADING_RE = re.compile(
    r"^##\s+\d+\.\s*Finding\s*(?:→|->)\s*task map", re.MULTILINE | re.IGNORECASE
)
NEXT_H2_RE = re.compile(r"^##\s+\S", re.MULTILINE)

# Verified by hand against the live tree (2026-08-21): the finding's real, sole
# owner is the OTHER plan in the pair. The plan named here mentions the finding
# only inside its own "Finding -> task map" section as a documented
# cross-package dependency/handoff note (e.g. a "tracked separately" sub-table
# naming the true owner in the same row), and that plan's own text disclaims
# ownership. Shrink this dict as plans merge with cleaner cross-references;
# never grow it without re-reading the disclaiming plan's own words.
EXCLUDE_AS_MENTION = {
    "B-01": "P8-engine-cron.md",
    "B-06": "P8-engine-cron.md",
    "B-21": "P8-engine-cron.md",
    "B-72": "P10-roster.md",
    "B-73": "P8-engine-cron.md",
    "B-82": "P8-engine-cron.md",
    "D-47": "P5-skills-editor.md",
    "E-05": "P15-ui.md",
    "E-07": "P15-ui.md",
    "F-64": "P8-engine-cron.md",
}
# Verified by hand: genuinely split and closed by two real, separately-tasked
# halves, each recorded as its own row in each plan's own task map (P1's T18,
# P4's T19).
KNOWN_SPLIT_FINDINGS = {"F-26"}


def test_every_audit_finding_is_claimed_by_exactly_one_remediation_plan():
    findings = set()
    for appendix in AUDIT.glob("appendix-*.md"):
        findings |= set(FINDING_HEADING_RE.findall(appendix.read_text(encoding="utf-8")))
    assert findings, "no findings parsed -- the heading format changed"

    claims: dict[str, list[str]] = {}
    for plan in PLANS.glob("P*.md"):
        text = plan.read_text(encoding="utf-8")
        heading = TASK_MAP_HEADING_RE.search(text)
        assert heading, f"{plan.name} has no '## N. Finding -> task map' section"
        rest = text[heading.end():]
        next_h2 = NEXT_H2_RE.search(rest)
        scope = rest[: next_h2.start()] if next_h2 else rest
        for fid in set(FINDING_REF_RE.findall(scope)) & findings:
            if EXCLUDE_AS_MENTION.get(fid) == plan.name:
                continue
            claims.setdefault(fid, []).append(plan.name)

    unclaimed = sorted(findings - claims.keys())
    contested = sorted(
        f for f, owners in claims.items()
        if len(owners) > 1 and f not in KNOWN_SPLIT_FINDINGS
    )
    assert not unclaimed, f"audit findings no remediation plan claims: {unclaimed}"
    assert not contested, f"audit findings claimed by more than one plan: {contested}"


def test_claude_md_requires_a_failing_assertion_per_defect():
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert "which assertion would have failed" in text.lower(), (
        "CLAUDE.md must carry the standing rule F-10 exists to install"
    )


def test_docs_readme_accounts_for_every_committed_doc():
    docs = REPO / "docs"
    readme = (docs / "README.md").read_text(encoding="utf-8")
    unlisted = sorted(
        p.name for p in docs.glob("*.md")
        if p.name != "README.md" and p.name not in readme
    )
    assert not unlisted, (
        f"docs/ holds committed documents docs/README.md never mentions: {unlisted}"
    )


COMMAND_BLOCK_RE = re.compile(r"^\s{4,}(python -m pytest[^\n]*)$", re.MULTILINE)


def _documented_commands(doc: Path) -> list[str]:
    return [c.strip() for c in COMMAND_BLOCK_RE.findall(doc.read_text(encoding="utf-8"))]


def _claimed_counts(doc: Path) -> dict[str, int]:
    """Maps a documented command to the test count the same doc claims for it."""
    text = doc.read_text(encoding="utf-8")
    return {
        cmd: int(n)
        for cmd, n in re.findall(
            r"`(python -m pytest[^`]*)`[^\n]*?\b([\d,]+) tests", text.replace(",", "")
        )
    }


@pytest.mark.allow_subprocess
@pytest.mark.parametrize("doc_name", ["CLAUDE.md", "pipeline-app/README.md"])
def test_documented_test_commands_collect_what_the_docs_claim(doc_name):
    if os.environ.get("DOC_TRUTH_CHILD"):
        pytest.skip("child collection run; do not recurse")
    doc = REPO / doc_name
    commands = _documented_commands(doc)
    assert commands, f"{doc_name} must document its test invocation as an indented command block"
    env = {**os.environ, "DOC_TRUTH_CHILD": "1"}
    for command in commands:
        cwd = REPO / "pipeline-app" if doc_name.startswith("pipeline-app") else REPO
        argv = [sys.executable, "-m", "pytest", "--collect-only", "-q",
                "-p", "no:cacheprovider", *command.split()[3:]]
        proc = subprocess.run(argv, cwd=cwd, capture_output=True,
                              encoding="utf-8", errors="replace", env=env)
        assert proc.returncode == 0, (
            f"{doc_name} documents `{command}`, which does not collect cleanly:\n{proc.stdout}\n{proc.stderr}"
        )
        collected = int(re.search(r"(\d+) tests? collected", proc.stdout).group(1))
        claimed = _claimed_counts(doc).get(command)
        if claimed is not None:
            assert collected == claimed, (
                f"{doc_name} claims `{command}` runs {claimed} tests; it collects {collected}"
            )


def test_no_doc_claims_a_bare_pytest_is_sufficient():
    """F-62's exact sentence, pinned dead. Bare `pytest` in pipeline-app/ fails collection
    on four files; at the repo root it silently omits 80% of the suite."""
    for doc in (CLAUDE_MD, REPO / "pipeline-app" / "README.md", REPO / "README.md"):
        text = doc.read_text(encoding="utf-8")
        assert "does the right thing in both places" not in text, (
            f"{doc.name} still carries the retracted bare-pytest claim (F-62)"
        )
