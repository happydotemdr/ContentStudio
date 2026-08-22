"""Executable checks on the repo's own documentation.

Every assertion here corresponds to a claim some README or CLAUDE.md makes about the
code. The audit (2026-08-08) found four such claims false at once, all of them written
once and never checked again. These tests are the checking.

Stdlib + pytest only. No app imports -- the root suite must stay import-free of
pipeline_app, and these read documents as text anyway.
"""

import ast
import importlib.util
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
    # coach-prep-app, added 2026-08-21. It sends client material to Anthropic
    # and mails Ryan a review link, and neither call site was in the roster
    # CLAUDE.md calls complete -- the globs above covered pipeline-app alone.
    "coach-prep-app/coach_prep_app/**/*.py",
    "coach-prep-app/scripts/*.py",
]

# NOT yet scanned, and named here so the gap is measured rather than implied:
# doc-ingest-app reaches Google Drive (drive_client.py) and firecrawl
# (convert.py) on every ingest wake. Neither is caught by the probes above --
# a Drive call is `service.files().export(...).execute()` and a firecrawl one
# is `client.parse(...)`, and no probe matches either shape. Adding the globs
# without adding those probes would look like coverage while measuring
# nothing, so the probes come first. Until then, CLAUDE.md's roster is
# complete for pipeline-app, coach-prep-app and the download scripts only.

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


# `cd <app> && ` for any app directory. This named pipeline-app alone until
# 2026-08-21, which is the third of three places that did -- and the one that
# mattered most: a command block for another suite was not collected at all,
# so the whole check silently skipped it rather than failing.
COMMAND_BLOCK_RE = re.compile(
    r"^\s{4,}((?:cd [\w.-]+ && )?python -m pytest[^\n]*)$", re.MULTILINE
)


def _documented_commands(doc: Path) -> list[str]:
    return [c.strip() for c in COMMAND_BLOCK_RE.findall(doc.read_text(encoding="utf-8"))]


def _claimed_counts(doc: Path) -> dict[str, int]:
    """Maps a documented command to the test count the same doc claims for it."""
    text = doc.read_text(encoding="utf-8")
    # `cd <app> && ` for any app directory, not just pipeline-app. Hardcoding
    # one directory here meant a count claimed for any other suite was never
    # compared against anything: the command mapped to no claim at all, and
    # a deliberately wrong "999 tests" for coach-prep-app passed silently.
    return {
        cmd: int(n)
        for cmd, n in re.findall(
            r"`((?:cd [\w.-]+ && )?python -m pytest[^`]*)`[^\n]*?\b([\d,]+) tests",
            text.replace(",", ""),
        )
    }


# CI's root-suite job installs only the repo-root requirements-dev.txt, by design
# (finding F-63's isolation: root-suite must never depend on any app's own packages).
# Each app's commands can only be verified from an environment that has that app's own
# dependencies. This started as a pipeline-app-only check (pytest-asyncio, required by
# pipeline-app/pytest.ini's `asyncio_mode = strict` -- collecting with that plugin
# absent makes `filterwarnings = error` turn the resulting PytestConfigWarning fatal)
# and stayed that way through the 2026-08-21 generalization to four suites, which is
# exactly how `cd doc-ingest-app && ...` and `cd coach-prep-app && ...` commands ended
# up asserted on unconditionally in root-suite's CI job -- both fail collection there
# because google-auth (both apps) and firecrawl/python-docx (doc-ingest-app) are never
# installed outside their own app directories.
_APP_REQUIRED_MODULES = {
    "pipeline-app": ("pytest_asyncio",),
    "doc-ingest-app": ("google.auth", "firecrawl", "docx"),
    "coach-prep-app": ("google.auth",),
}


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


def _app_env_available(app_dir: str) -> bool:
    """Reports whether the current interpreter has the app's own dependencies, so the
    caller can skip just that app's commands rather than fail on an absence root-suite's
    own CI job was built to have. An app_dir with no entry here (none exist today) is
    treated as always available, matching the pre-2026-08-21 default for every
    non-pipeline-app command."""
    modules = _APP_REQUIRED_MODULES.get(app_dir)
    if modules is None:
        return True
    return all(_module_available(m) for m in modules)


def test_app_env_available_guards_every_app_directory_claude_md_documents(monkeypatch):
    """Regression for the root-suite CI failure of 2026-08-21: `cd doc-ingest-app && ...`
    and `cd coach-prep-app && ...` commands were asserted on unconditionally because only
    pipeline-app had a readiness guard, and root-suite's CI job never installs either
    app's own dependencies (google-auth, firecrawl, python-docx). This is the assertion
    that would have caught it before CI did: every app directory CLAUDE.md documents a
    `cd <app> && python -m pytest` command for must appear in _APP_REQUIRED_MODULES, and
    _app_env_available must report False for it when those modules are absent."""
    documented_app_dirs = {
        m.group(1)
        for m in re.finditer(r"cd ([\w.-]+) && python -m pytest", CLAUDE_MD.read_text(encoding="utf-8"))
    }
    assert documented_app_dirs, "CLAUDE.md must document at least one `cd <app> && ...` suite command"
    assert documented_app_dirs <= _APP_REQUIRED_MODULES.keys(), (
        f"CLAUDE.md documents commands for {documented_app_dirs - _APP_REQUIRED_MODULES.keys()}, "
        "which have no entry in _APP_REQUIRED_MODULES -- their commands would be asserted "
        "on unconditionally in root-suite's CI job, which installs no app's own dependencies"
    )

    real_find_spec = importlib.util.find_spec
    always_missing = {m for mods in _APP_REQUIRED_MODULES.values() for m in mods}

    def fake_find_spec(name, *args, **kwargs):
        if name in always_missing:
            return None
        return real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    for app_dir in documented_app_dirs:
        assert not _app_env_available(app_dir), (
            f"{app_dir} must be treated as unverifiable, not asserted on, when its own "
            "dependencies are absent from the interpreter"
        )


@pytest.mark.allow_subprocess
@pytest.mark.parametrize("doc_name", ["CLAUDE.md", "pipeline-app/README.md"])
def test_documented_test_commands_collect_what_the_docs_claim(doc_name):
    if os.environ.get("DOC_TRUTH_CHILD"):
        pytest.skip("child collection run; do not recurse")
    doc = REPO / doc_name
    commands = _documented_commands(doc)
    assert commands, f"{doc_name} must document its test invocation as an indented command block"
    env = {**os.environ, "DOC_TRUTH_CHILD": "1"}
    unverifiable = []
    for command in commands:
        # `cd <app> && python -m pytest ...` for any app directory, not just
        # pipeline-app. The repo has four suites, each run from its own
        # directory, and hardcoding one of them here is how the other three
        # stayed undocumented and unchecked.
        cd_prefix = re.match(r"cd ([\w.-]+) && (.+)", command)
        if cd_prefix:
            app_dir = cd_prefix.group(1)
            cwd = REPO / app_dir
            pytest_part = cd_prefix.group(2)
        else:
            app_dir = "pipeline-app" if doc_name.startswith("pipeline-app") else None
            cwd = REPO / app_dir if app_dir else REPO
            pytest_part = command
        if app_dir and not _app_env_available(app_dir):
            unverifiable.append(command)
            continue
        argv = [sys.executable, "-m", "pytest", "--collect-only", "-q",
                "-p", "no:cacheprovider", *pytest_part.split()[3:]]
        proc = subprocess.run(argv, cwd=cwd, capture_output=True,
                              encoding="utf-8", errors="replace", env=env)
        assert proc.returncode == 0, (
            f"{doc_name} documents `{command}`, which does not collect cleanly:\n{proc.stdout}\n{proc.stderr}"
        )
        collected = int(re.search(r"(\d+) tests? collected", proc.stdout).group(1))
        claimed = _claimed_counts(doc).get(command)
        assert claimed is not None, (
            f"{doc_name} documents `{command}` but never states its test count in the "
            "`{command}` ... NNN tests` form on the same line -- an unchecked count is the "
            "defect this test exists to catch"
        )
        assert collected == claimed, (
            f"{doc_name} claims `{command}` runs {claimed} tests; it collects {collected}"
        )
    if unverifiable and len(unverifiable) == len(commands):
        pytest.skip(
            f"{doc_name}: none of its documented commands are verifiable in this "
            f"environment (the target apps' own dependencies are not installed here): "
            f"{unverifiable}. Run from an environment with every app's toolchain installed."
        )
    elif unverifiable:
        print(
            f"NOTE: {doc_name} -- skipped verifying {unverifiable} in this environment "
            "(the target apps' own dependencies are not installed here); the rest of this "
            "doc's commands were verified normally."
        )


def test_no_doc_claims_a_bare_pytest_is_sufficient():
    """F-62's exact sentence, pinned dead. Bare `pytest` in pipeline-app/ fails collection
    on four files; at the repo root it silently omits 80% of the suite."""
    for doc in (CLAUDE_MD, REPO / "pipeline-app" / "README.md", REPO / "README.md"):
        text = doc.read_text(encoding="utf-8")
        assert "does the right thing in both places" not in text, (
            f"{doc.name} still carries the retracted bare-pytest claim (F-62)"
        )


SETUP_SCRIPT_RE = re.compile(r"`?(?:python -m |python |bash )([\w./-]+)`?")


def test_pipeline_app_setup_seeds_the_discovery_roster():
    text = (REPO / "pipeline-app" / "README.md").read_text(encoding="utf-8")
    assert "migrate_handles_from_manifest" in text, (
        "pipeline-app/README.md Setup must document the roster-seeding step (B-80): "
        "without it the handles table is empty and every discovery run completes having "
        "fetched nothing."
    )


@pytest.mark.parametrize("doc_name", [
    "README.md", "pipeline-app/README.md", "docs/README.md", "rgs-briefs/README.md", "CLAUDE.md",
])
def test_every_script_path_a_readme_tells_you_to_run_exists(doc_name):
    text = (REPO / doc_name).read_text(encoding="utf-8")
    missing = []
    for token in re.findall(r"`([\w./-]+\.(?:py|sh))`", text):
        if token.startswith(("http", "<")) or "*" in token:
            continue
        candidates = [
            REPO / token, REPO / "pipeline-app" / token, REPO / "scripts" / token,
            REPO / "tests" / token, REPO / "pipeline-app" / "tests" / token,
        ]
        if not any(c.exists() for c in candidates):
            missing.append(token)
    assert not missing, f"{doc_name} names files that do not exist: {sorted(set(missing))}"


FIREWALL_EXEMPT = {
    "CLAUDE.md",                # the firewall + Origin sections themselves
    "tests/test_doc_truth.py",  # this file
}


def _tracked_files_mentioning_familybrain() -> set[str]:
    proc = subprocess.run(
        ["git", "grep", "-l", "-i", "familybrain", "--", ".",
         ":(exclude)docs/audit", ":(exclude)docs/superpowers"],
        cwd=REPO, capture_output=True, encoding="utf-8", errors="replace",
    )
    return {p for p in proc.stdout.split() if p and p not in FIREWALL_EXEMPT}


@pytest.mark.allow_subprocess
def test_every_familybrain_mention_is_accounted_for_in_origin():
    origin = CLAUDE_MD.read_text(encoding="utf-8")
    start = origin.index("## FamilyBrain firewall")
    section = origin[start:origin.index("## Using the skills")]
    unexplained = [
        path for path in sorted(_tracked_files_mentioning_familybrain())
        if Path(path).name not in section and path not in section
        and Path(path).parts[0] not in section
    ]
    assert not unexplained, (
        "tracked files mention FamilyBrain but CLAUDE.md's Origin section does not "
        f"account for them: {unexplained}. Explain them as history or remove them -- "
        "an unexplained mention is indistinguishable from a live dependency (D-53)."
    )


def _pipeline_stage_ids() -> list[str]:
    text = (REPO / "pipeline.yaml").read_text(encoding="utf-8")
    return re.findall(r"^\s*-\s*id:\s*(\S+)", text, re.MULTILINE)


def test_rgs_briefs_readme_enumerates_every_producing_pipeline_stage():
    readme = (REPO / "rgs-briefs" / "README.md").read_text(encoding="utf-8")
    # `grounding` produces a grounding brief, not a `<stage>` artifact; every other
    # stage in pipeline.yaml writes one and must appear in the enumeration.
    missing = [s for s in _pipeline_stage_ids() if s != "grounding" and s not in readme]
    assert not missing, (
        f"rgs-briefs/README.md does not enumerate pipeline stages {missing} (C-52). "
        "A stage the ledger's contract omits will write frontmatter nobody specified."
    )


# `2026-07-25-let-kids-play-act-specialization-visual-prompts.md` carries the one-off
# `kind: visual-prompt-sheet` -- immutable, listed in the README as a known deviation
# rather than a permitted spelling. This allowlist names that one file so it cannot
# silently absorb a second, unrelated `kind:` value.
KNOWN_KIND_DEVIATIONS = {
    "visual-prompt-sheet",  # 2026-07-25-let-kids-play-act-specialization-visual-prompts.md
}


def test_every_kind_value_on_disk_is_enumerated_in_the_readme():
    briefs = REPO / "rgs-briefs"
    readme = (briefs / "README.md").read_text(encoding="utf-8")
    on_disk = set()
    for path in briefs.glob("*.md"):
        if path.name == "README.md":
            continue
        head = path.read_text(encoding="utf-8", errors="replace")[:600]
        found = re.search(r"^kind:\s*(\S+)", head, re.MULTILINE)
        if found:
            on_disk.add(found.group(1))
    on_disk -= KNOWN_KIND_DEVIATIONS
    missing = sorted(k for k in on_disk if f"`{k}`" not in readme)
    assert not missing, (
        f"kind: values written to rgs-briefs/ that the README's vocabulary omits: {missing}"
    )


GROUNDING_FIELDS = ("thinker", "concept", "research_codes")


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}
    block = text.split("---", 2)[1]
    return dict(re.findall(r"^(\w+):\s*(.*)$", block, re.MULTILINE))


# The ten stage artifacts that predate the `kind:` contract. Frozen deliberately:
# they are immutable (.claude/hooks/protect_briefs.py) and this list is what the
# negative rule got wrong.
KIND_LESS_STAGE_ARTIFACTS = 10


def test_the_documented_discriminator_is_positive_not_kind_based():
    readme = (REPO / "rgs-briefs" / "README.md").read_text(encoding="utf-8")
    assert "MUST skip any file with a `kind:` field" not in readme, (
        "rgs-briefs/README.md still tells consumers to discriminate on the absence of "
        "`kind:` -- ten pre-contract stage artifacts have no `kind:` and are not grounding "
        "briefs (C-53)."
    )
    assert all(f"`{field}`" in readme for field in GROUNDING_FIELDS), (
        "the positive rule must name all three required fields"
    )


def test_positive_and_negative_discriminators_disagree_on_exactly_the_known_ten():
    briefs = [p for p in (REPO / "rgs-briefs").glob("*.md") if p.name != "README.md"]
    by_positive = {p.name for p in briefs
                   if all(f in _frontmatter(p) for f in GROUNDING_FIELDS)}
    by_negative = {p.name for p in briefs if "kind" not in _frontmatter(p)}
    difference = by_negative - by_positive
    assert len(difference) == KIND_LESS_STAGE_ARTIFACTS, (
        f"expected exactly {KIND_LESS_STAGE_ARTIFACTS} files that the old kind:-skipping rule "
        f"misclassifies as grounding briefs; found {len(difference)}: {sorted(difference)}"
    )
    assert not by_positive - by_negative, (
        "a file has all three grounding fields AND a kind: -- the two contracts have collided"
    )


def test_the_two_provenance_rules_name_each_others_scope():
    docs_readme = (REPO / "docs" / "README.md").read_text(encoding="utf-8")
    claude = CLAUDE_MD.read_text(encoding="utf-8")
    assert "`docs/*.md`" in docs_readme, (
        "docs/README.md's unmarked-[C] shorthand must name the scope it applies to"
    )
    assert "`docs/*.md`" in claude, (
        "CLAUDE.md's 'no marker is a bug' rule must name the one documented exemption "
        "and its scope, or the two rules read as a contradiction"
    )


def test_claude_md_email_promise_matches_the_pinned_disclosure():
    """P9 pinned the real behaviour in email_render.DISCLOSURE; CLAUDE.md must say the
    same thing. Read as text -- the root suite does not import app code.

    DISCLOSURE is assembled from concatenated string/f-string literals inside
    parentheses, not one quoted string, so a plain quote-to-quote regex can't
    extract its rendered value. Parse just that assignment's expression with
    `ast` and evaluate it with the two size constants it references bound in --
    still text-only: nothing from pipeline_app is imported.
    """
    email_path = REPO / "pipeline-app" / "pipeline_app" / "email_render.py"
    digest_path = REPO / "pipeline-app" / "pipeline_app" / "discovery_digest.py"
    email_source = email_path.read_text(encoding="utf-8")
    digest_source = digest_path.read_text(encoding="utf-8")

    tree = ast.parse(email_source, filename=str(email_path))
    node = next(
        (n for n in tree.body if isinstance(n, ast.Assign)
         and any(isinstance(t, ast.Name) and t.id == "DISCLOSURE" for t in n.targets)),
        None,
    )
    assert node is not None, "email_render.DISCLOSURE not found -- P9's pin is missing"

    title_max = re.search(r"^TITLE_MAX_CHARS\s*=\s*(\d+)", digest_source, re.MULTILINE)
    excerpt_max = re.search(r"^EXCERPT_MAX_CHARS\s*=\s*(\d+)", email_source, re.MULTILINE)
    assert title_max and excerpt_max, (
        "TITLE_MAX_CHARS/EXCERPT_MAX_CHARS constants moved -- update this probe"
    )

    expr = ast.fix_missing_locations(ast.Expression(body=node.value))
    disclosure = eval(
        compile(expr, "<email_render.DISCLOSURE>", "eval"),
        {"__builtins__": {}},
        {
            "TITLE_MAX_CHARS": int(title_max.group(1)),
            "EXCERPT_MAX_CHARS": int(excerpt_max.group(1)),
        },
    )
    disclosure = " ".join(disclosure.split())
    claude = " ".join(CLAUDE_MD.read_text(encoding="utf-8").split())
    assert disclosure in claude, (
        "CLAUDE.md's email privacy paragraph has drifted from email_render.DISCLOSURE. "
        "The doc does not get its own wording for this."
    )


def test_no_doc_repeats_the_unachievable_never_a_full_post_body_promise():
    for doc in (CLAUDE_MD, REPO / "README.md"):
        assert "never a full post body" not in doc.read_text(encoding="utf-8"), (
            f"{doc.name} repeats a promise the code cannot keep: any post shorter than "
            "the excerpt cap is included in full by definition."
        )
