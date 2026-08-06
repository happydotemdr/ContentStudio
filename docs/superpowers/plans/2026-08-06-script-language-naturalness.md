# Script Language Naturalness (Gates D & E) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `shorts-scripting` two blocking quality gates on script language — a deterministic linter (Gate D) and a fresh Opus critic (Gate E) — and an app-run gate registry that also repairs `visual-prompts`' silently-broken Gate C.

**Architecture:** `scripts/lint_script_language.py` is a stdlib-only linter over voiceover lines, mirroring `scripts/lint_prompt_sheet.py`'s shape exactly (parse → `Finding` dataclass → `lint()` → `main()` with exit 0/1/2). `pipeline-app/pipeline_app/gates.py` loads linters by file path and runs them post-turn, folding results into artifact frontmatter; `approval_service` refuses approval on a failing gate without a recorded override. Gate E lives in the skill's markdown, dispatched via `Task` with `model: opus`.

**Tech Stack:** Python 3 (stdlib only for `scripts/`), pytest, FastAPI + SQLite (pipeline app), Jinja2 templates, Claude Code skills as markdown.

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-08-06-script-language-naturalness-design.md` is the authority. Where this plan and the spec disagree, the spec wins — stop and flag it.
- **`scripts/` is stdlib only.** No third-party imports in `lint_script_language.py`. `lint_prompt_sheet.py` is the precedent to match.
- **Provenance markers are mandatory.** Every normative line added to any `.claude/skills/**` file needs a `[C]`, `[I]`, `[T]`, or `[S]` marker. An unmarked normative line is a bug (root `CLAUDE.md`).
- **`[S]` rules must cite a real failing line.** An `[S]` rule that cannot name a shipped script line violating it must be marked `[I]` instead.
- **Never edit `rgs-briefs/*.md`.** A `PreToolUse` hook blocks it. Copy them into `tests/fixtures/` instead.
- **`output/` does not exist locally** and must not be fetched. Nothing in this plan reads it.
- **FamilyBrain firewall:** no reference to `C:\Projects\FamilyBrain\` or any `brain_*` tool.
- **wpm ceiling: 170, tolerance ±2** → a beat fails D5 only above **172 wpm**.
- **Word counting:** a "word" is a whitespace-separated token containing at least one alphanumeric character. This excludes standalone `—`.
- Run the full suite with `python -m pytest tests/ -v` (repo root) and `python -m pytest pipeline-app/tests/ -v` (app).

---

## File Structure

**Create:**
- `scripts/lint_script_language.py` — Gate D linter. Parser + six checks + CLI.
- `tests/test_lint_script_language.py` — Gate D tests.
- `tests/fixtures/script_*.md` — frozen copies of the four shipped scripts.
- `docs/script-language-baseline.md` — the 27-line labeled evidence base; `[S]` citations point here.
- `.claude/skills/shorts-scripting/references/read-aloud-gates.md` — the D/E rule set, the Gate E dispatch prompt, the no-touch annotation vocabulary.
- `pipeline-app/pipeline_app/gates.py` — gate registry and runner.
- `pipeline-app/tests/test_gates.py` — registry tests.

**Modify:**
- `.claude/skills/shorts-scripting/SKILL.md` — step 9, provenance section, output contract.
- `.claude/skills/visual-prompts/SKILL.md` — Gate C's two modes.
- `pipeline-app/pipeline_app/turn_service.py:221-246` — run gates, write into frontmatter.
- `pipeline-app/pipeline_app/approval_service.py:10-45` — block on failing gates, accept override.
- `pipeline-app/pipeline_app/artifacts.py:79-83` — `stamp_final` records an override reason.
- `pipeline-app/pipeline_app/routes/stages.py:195-209` — thread `override_reason` from the form.
- `pipeline-app/pipeline_app/cli_runner.py:224` — add `Task` to `allowed_tools`.

---

### Task 1: VO-line parser and fixtures

**Files:**
- Create: `scripts/lint_script_language.py`
- Create: `tests/test_lint_script_language.py`
- Create: `tests/fixtures/script_let_kids_play_act.md`, `script_specialization.md`, `script_decline.md`, `script_nobody_asked.md`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `VOLine(beat: str, line_number: int, text: str, start_s: int|None, end_s: int|None)`, `Finding(check: str, beat: str|None, message: str, kind: str = "fail")`, `parse_script(text: str) -> tuple[list[VOLine], list[Finding]]`, `word_count(text: str) -> int`. Every later task builds on these.

- [ ] **Step 1: Copy the four shipped scripts into fixtures**

These are read-only inputs frozen at copy time. Do not edit them afterward.

```bash
cd "$(git rev-parse --show-toplevel)"
cp rgs-briefs/2026-07-25-let-kids-play-act-script.md tests/fixtures/script_let_kids_play_act.md
cp rgs-briefs/2026-07-25-let-kids-play-act-specialization-script.md tests/fixtures/script_specialization.md
cp rgs-briefs/2026-07-28-decline-the-next-level-script.md tests/fixtures/script_decline.md
cp rgs-briefs/2026-07-28-nobody-asked-the-kid-script.md tests/fixtures/script_nobody_asked.md
```

- [ ] **Step 2: Write the failing parser tests**

Create `tests/test_lint_script_language.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lint_script_language import (  # noqa: E402
    VOLine,
    Finding,
    parse_script,
    word_count,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


SCRIPT = """\
=== SHORT SCRIPT — demo ===

HOOK        (0–3s  | 7 words): "It won't set him back. Not athletically."
SETUP       (3–8s  | 8 words) — *narrator enters*: "Kids do that, every single time."
BUILD/VALUE (8–28s | 20 words):
  (8–18s | 12 words): "A position stand reports that samplers still reach elite level."
  [re-hook beat @ ~18s] (18–21s | 8 words): "But the offer isn't really about your kid."
[re-hook beat @ ~15s]: "His proof: a trader who bought every oil press in town."
LOOP/CTA    (38–45s | 5 words, mirrors hook): "It won't set him back."
Comment-bait question: "What tier were you offered?"
"""


def test_parses_every_vo_line_form():
    lines, _ = parse_script(SCRIPT)
    assert [vo.text for vo in lines] == [
        "It won't set him back. Not athletically.",
        "Kids do that, every single time.",
        "A position stand reports that samplers still reach elite level.",
        "But the offer isn't really about your kid.",
        "His proof: a trader who bought every oil press in town.",
        "It won't set him back.",
    ]


def test_comment_bait_is_not_a_vo_line():
    lines, _ = parse_script(SCRIPT)
    assert all("What tier" not in vo.text for vo in lines)


def test_reads_beat_ranges():
    lines, _ = parse_script(SCRIPT)
    assert (lines[0].beat, lines[0].start_s, lines[0].end_s) == ("HOOK", 0, 3)
    assert (lines[3].beat, lines[3].start_s, lines[3].end_s) == ("re-hook", 18, 21)


def test_old_format_rehook_has_no_range():
    lines, _ = parse_script(SCRIPT)
    old = lines[4]
    assert old.beat == "re-hook"
    assert old.start_s is None and old.end_s is None


def test_word_count_ignores_standalone_dashes():
    assert word_count("isn't more serious play — it's constrained labor") == 8


def test_shipped_fixtures_parse_to_expected_counts():
    expected = {
        "script_let_kids_play_act.md": 6,
        "script_specialization.md": 6,
        "script_decline.md": 7,
        "script_nobody_asked.md": 8,
    }
    for name, count in expected.items():
        lines, _ = parse_script(_read(name))
        assert len(lines) == count, f"{name}: got {len(lines)}"


def test_zero_vo_lines_yields_no_lines():
    lines, findings = parse_script("just prose, no beats at all\n")
    assert lines == []
    assert findings == []


def test_beat_heading_with_no_quoted_line_anywhere_is_partial_parse():
    text = 'HOOK        (0–3s  | 7 words):\nSETUP (3–8s | 4 words): "A real spoken line."\n'
    _, findings = parse_script(text)
    assert [f.kind for f in findings] == ["partial-parse"]
    assert findings[0].beat == "HOOK"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_lint_script_language.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lint_script_language'`

- [ ] **Step 4: Write the parser**

Create `scripts/lint_script_language.py`:

```python
"""Gate D — deterministic read-aloud lint for ContentStudio Short scripts.

Parses the voiceover lines out of the script format emitted by the
`shorts-scripting` skill and enforces the rules that are wrong unconditionally,
whatever the author intended: unspeakable punctuation, unspeakable tokens, and
beats with more words than fit in their seconds.

Rhythm and template judgments are deliberately NOT here -- whether a fragment
run is deliberate cadence or the model's default needs the whole script in view,
so it belongs to Gate E. See
docs/superpowers/specs/2026-08-06-script-language-naturalness-design.md.

Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

BEAT_LABELS = ("HOOK", "SETUP", "BUILD/VALUE", "PAYOFF", "LOOP/CTA")
BEAT_LABEL_RE = re.compile(r"^(HOOK|SETUP|BUILD/VALUE|PAYOFF|LOOP/CTA)\b")
REHOOK_RE = re.compile(r"^\[re-hook\b")
SUBRANGE_RE = re.compile(r"^\(\d+")
RANGE_RE = re.compile(r"\((\d+)\s*[–—-]\s*(\d+)s")
QUOTED_RE = re.compile(r'"([^"]+)"')


@dataclass(frozen=True)
class VOLine:
    beat: str
    line_number: int
    text: str
    start_s: int | None
    end_s: int | None


@dataclass(frozen=True)
class Finding:
    check: str
    beat: str | None
    message: str
    kind: str = "fail"


def word_count(text: str) -> int:
    """Whitespace tokens carrying at least one alphanumeric character.

    Excludes a standalone em-dash, which is punctuation the narrator does not
    speak -- counting it would inflate every wpm figure on a dashed line."""
    return sum(1 for token in text.split() if any(c.isalnum() for c in token))


def _beat_name(stripped: str) -> str | None:
    """The beat this line belongs to, or None if it is not a beat line at all."""
    label = BEAT_LABEL_RE.match(stripped)
    if label:
        return label.group(1)
    if REHOOK_RE.match(stripped):
        return "re-hook"
    if SUBRANGE_RE.match(stripped):
        return "sub-beat"
    return None


def parse_script(text: str) -> tuple[list[VOLine], list[Finding]]:
    """Return (VO lines in script order, coverage findings).

    A beat heading may legitimately carry no quoted text of its own -- BUILD and
    PAYOFF often delegate to indented sub-ranges beneath them. So coverage is
    tracked per top-level beat: a heading is satisfied by its own quoted span or
    by any beat line before the next top-level heading. A heading satisfied by
    neither means the parser is not seeing text that is there, which must fail
    loudly rather than silently shrink the linted surface."""
    vo_lines: list[VOLine] = []
    findings: list[Finding] = []

    current_label: str | None = None
    current_label_line = 0
    label_covered = True

    def close_label() -> None:
        if current_label is not None and not label_covered:
            findings.append(
                Finding(
                    "PARSE",
                    current_label,
                    f"beat heading at line {current_label_line} yielded no voiceover line",
                    kind="partial-parse",
                )
            )

    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        beat = _beat_name(stripped)
        if beat is None:
            continue

        is_top_level = BEAT_LABEL_RE.match(stripped) is not None
        if is_top_level:
            close_label()
            current_label = beat
            current_label_line = number
            label_covered = False

        quoted = QUOTED_RE.search(stripped)
        if quoted is None:
            continue

        label_covered = True
        span = RANGE_RE.search(stripped)
        vo_lines.append(
            VOLine(
                beat=current_label if beat == "sub-beat" and current_label else beat,
                line_number=number,
                text=quoted.group(1),
                start_s=int(span.group(1)) if span else None,
                end_s=int(span.group(2)) if span else None,
            )
        )

    close_label()
    return vo_lines, findings
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_lint_script_language.py -v`
Expected: PASS — 8 passed

If `test_shipped_fixtures_parse_to_expected_counts` fails, the parser is missing a real VO-line form. Print the parsed texts for the failing fixture and compare against its beat block before adjusting the regexes — do **not** adjust the expected counts, which were measured against the real files.

- [ ] **Step 6: Commit**

```bash
git add scripts/lint_script_language.py tests/test_lint_script_language.py tests/fixtures/script_*.md
git commit -m "feat(gate-d): VO-line parser with fixtures from the four shipped scripts

Handles all three shipped forms, including the old-format re-hook with no
range group -- the form whose omission produced a wrong evidence table in
the first draft of the spec.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: D1 and D2 — unspeakable punctuation

**Files:**
- Modify: `scripts/lint_script_language.py`
- Modify: `tests/test_lint_script_language.py`

**Interfaces:**
- Consumes: `VOLine`, `Finding`, `parse_script` from Task 1.
- Produces: `check_punctuation(vo_lines: list[VOLine]) -> list[Finding]` emitting checks `D1` and `D2`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lint_script_language.py` (add `check_punctuation` to the import block at the top):

```python
def test_d1_flags_em_dash_in_vo_line():
    lines, _ = parse_script(
        'HOOK (0–3s | 9 words): "An activity done for a result — constrained labor."\n'
    )
    findings = check_punctuation(lines)
    assert [f.check for f in findings] == ["D1"]


def test_d1_flags_en_dash_in_vo_line():
    lines, _ = parse_script('HOOK (0–3s | 5 words): "It won\'t – set him back."\n')
    assert [f.check for f in check_punctuation(lines)] == ["D1"]


def test_d1_ignores_the_en_dash_in_the_beat_heading():
    lines, _ = parse_script('HOOK (0–3s | 5 words): "It won\'t set him back."\n')
    assert check_punctuation(lines) == []


def test_d1_allows_hyphens():
    lines, _ = parse_script('HOOK (0–3s | 6 words): "Multi-sport players had longer careers."\n')
    assert check_punctuation(lines) == []


def test_d2_flags_semicolons_and_brackets():
    lines, _ = parse_script(
        'HOOK (0–3s | 8 words): "He signed; then he quit (again)."\n'
    )
    checks = sorted(f.check for f in check_punctuation(lines))
    assert checks == ["D2", "D2"]


def test_d1_counts_on_shipped_fixtures():
    expected = {
        "script_let_kids_play_act.md": 4,
        "script_specialization.md": 1,
        "script_decline.md": 2,
        "script_nobody_asked.md": 0,
    }
    for name, count in expected.items():
        lines, _ = parse_script(_read(name))
        d1 = [f for f in check_punctuation(lines) if f.check == "D1"]
        assert len(d1) == count, f"{name}: got {len(d1)}"


def test_d2_is_clean_on_every_shipped_fixture():
    for name in (
        "script_let_kids_play_act.md",
        "script_specialization.md",
        "script_decline.md",
        "script_nobody_asked.md",
    ):
        lines, _ = parse_script(_read(name))
        assert [f for f in check_punctuation(lines) if f.check == "D2"] == [], name


def test_scope_containment_prose_and_notes_never_fire_d1():
    """The check most likely to regress into noise.

    A shipped script's prose, Delivery notes, quote cards, and on-screen plates
    are written English and legitimately full of em-dashes. Only the quoted
    spoken text is in scope. script_nobody_asked.md has dozens of em-dashes in
    its prose and exactly zero in its voiceover lines -- if D1 ever fires on it,
    the parser has leaked out of the VO lines."""
    text = _read("script_nobody_asked.md")
    assert text.count("—") > 20, "fixture no longer exercises the containment case"
    lines, _ = parse_script(text)
    assert [f for f in check_punctuation(lines) if f.check == "D1"] == []


def test_a_verbatim_quote_card_in_prose_never_fires_d1():
    text = (
        "### The one quote card, verbatim\n\n"
        "> \"it becomes constrained labor when the consequences are outside\"\n"
        "> — John Dewey, *Democracy and Education*, 1916\n\n"
        'HOOK (0–3s | 5 words): "It will not set him back."\n'
    )
    lines, _ = parse_script(text)
    assert check_punctuation(lines) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_lint_script_language.py -v -k "d1 or d2"`
Expected: FAIL — `ImportError: cannot import name 'check_punctuation'`

- [ ] **Step 3: Implement the check**

Append to `scripts/lint_script_language.py`:

```python
DASH_RE = re.compile(r"[–—]")
WRITTEN_PUNCT_RE = re.compile(r"[;()\[\]]")


def check_punctuation(vo_lines: list[VOLine]) -> list[Finding]:
    """D1-D2: punctuation that exists only in written English.

    Scoped to the quoted spoken text, never the heading -- every beat heading
    carries an en-dash inside its own `(0–3s | N words)` range, which is not
    something anyone speaks aloud and not something to flag."""
    findings: list[Finding] = []
    for vo in vo_lines:
        if DASH_RE.search(vo.text):
            findings.append(
                Finding(
                    "D1",
                    vo.beat,
                    f"line {vo.line_number}: em/en-dash in a spoken line -- "
                    "a written parenthetical with no spoken realization",
                )
            )
        for match in WRITTEN_PUNCT_RE.finditer(vo.text):
            findings.append(
                Finding(
                    "D2",
                    vo.beat,
                    f"line {vo.line_number}: {match.group(0)!r} is written-register "
                    "punctuation in a spoken line",
                )
            )
    return findings
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_lint_script_language.py -v`
Expected: PASS — 15 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_script_language.py tests/test_lint_script_language.py
git commit -m "feat(gate-d): D1/D2 unspeakable punctuation in voiceover lines

D1 is calibrated against the real counts: 4/1/2/0 across the four shipped
scripts. D2 is a zero-hit regression guard, marked [I] not [S].

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: D3 and D4 — buzzword no-list and unspeakable tokens

**Files:**
- Modify: `scripts/lint_script_language.py`
- Modify: `tests/test_lint_script_language.py`

**Interfaces:**
- Consumes: `VOLine`, `Finding`, `parse_script` from Task 1.
- Produces: `check_vocabulary(vo_lines: list[VOLine]) -> list[Finding]` emitting checks `D3` and `D4`.

- [ ] **Step 1: Write the failing tests**

Append (and add `check_vocabulary` to the imports):

```python
def test_d3_flags_fingerprint_phrases():
    lines, _ = parse_script(
        'HOOK (0–3s | 9 words): "It\'s important to note that some may argue otherwise."\n'
    )
    assert sorted(f.check for f in check_vocabulary(lines)) == ["D3", "D3"]


def test_d3_flags_buzzwords_and_their_inflections():
    lines, _ = parse_script(
        'HOOK (0–3s | 8 words): "We leveraged a comprehensive and robust approach."\n'
    )
    assert len([f for f in check_vocabulary(lines) if f.check == "D3"]) == 3


def test_d3_does_not_flag_hackfort_the_surname():
    lines, _ = parse_script('HOOK (0–3s | 5 words): "Côté, Lidor and Hackfort reported."\n')
    assert check_vocabulary(lines) == []


def test_d4_flags_unspeakable_tokens():
    lines, _ = parse_script(
        'HOOK (0–3s | 7 words): "The study had n=142 kids & 37 coaches."\n'
    )
    assert len([f for f in check_vocabulary(lines) if f.check == "D4"]) == 2


def test_d4_flags_a_journal_citation_string():
    lines, _ = parse_script('HOOK (0–3s | 4 words): "See 12(3):424–433 for details."\n')
    assert [f.check for f in check_vocabulary(lines) if f.check == "D4"] == ["D4"]


def test_d3_and_d4_are_clean_on_every_shipped_fixture():
    for name in (
        "script_let_kids_play_act.md",
        "script_specialization.md",
        "script_decline.md",
        "script_nobody_asked.md",
    ):
        lines, _ = parse_script(_read(name))
        assert check_vocabulary(lines) == [], name
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_lint_script_language.py -v -k "d3 or d4"`
Expected: FAIL — `ImportError: cannot import name 'check_vocabulary'`

- [ ] **Step 3: Implement the check**

Append to `scripts/lint_script_language.py`:

```python
# Carried forward verbatim from the corpus's own no-list
# [C] (Romayroh, ErCV5czVK1g) via
# .claude/skills/shorts-scripting/references/script-intelligence-and-delivery.md
FINGERPRINT_PHRASES = (
    "it's important to note",
    "it is important to note",
    "some may argue",
)
BUZZWORDS = (
    "delve", "delves", "delving",
    "leverage", "leverages", "leveraged", "leveraging",
    "comprehensive", "comprehensively",
    "robust", "robustly",
    "holistic", "holistically",
)
BUZZWORD_RE = re.compile(r"\b(" + "|".join(BUZZWORDS) + r")\b", re.IGNORECASE)

# Tokens a text-to-speech voice cannot render as speech. These belong on an
# on-screen citation plate, never in a voiceover line.
UNSPEAKABLE = (
    (re.compile(r"&"), "ampersand"),
    (re.compile(r"§"), "section sign"),
    (re.compile(r"\b\w+\s*=\s*\d"), "an inline statistic like n=142"),
    (re.compile(r"\d+\(\d+\):\d+"), "a journal citation string"),
)


def check_vocabulary(vo_lines: list[VOLine]) -> list[Finding]:
    """D3-D4: the corpus buzzword no-list, and tokens TTS cannot speak."""
    findings: list[Finding] = []
    for vo in vo_lines:
        lowered = vo.text.lower()
        for phrase in FINGERPRINT_PHRASES:
            if phrase in lowered:
                findings.append(
                    Finding("D3", vo.beat, f"line {vo.line_number}: AI-fingerprint phrase {phrase!r}")
                )
        for match in BUZZWORD_RE.finditer(vo.text):
            findings.append(
                Finding("D3", vo.beat, f"line {vo.line_number}: buzzword {match.group(0)!r}")
            )
        for pattern, label in UNSPEAKABLE:
            if pattern.search(vo.text):
                findings.append(
                    Finding(
                        "D4",
                        vo.beat,
                        f"line {vo.line_number}: {label} in a spoken line -- "
                        "belongs on an on-screen plate",
                    )
                )
    return findings
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_lint_script_language.py -v`
Expected: PASS — 21 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_script_language.py tests/test_lint_script_language.py
git commit -m "feat(gate-d): D3 buzzword no-list and D4 unspeakable tokens

D3 carries the corpus no-list forward [C] (Romayroh, ErCV5czVK1g). D4 is a
zero-hit regression guard, marked [I]. Both verified clean against all four
shipped scripts, including the Hackfort false-positive the decline script
warns about.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: D5 — the wpm ceiling

**Files:**
- Modify: `scripts/lint_script_language.py`
- Modify: `tests/test_lint_script_language.py`

**Interfaces:**
- Consumes: `VOLine`, `Finding`, `word_count`, `parse_script` from Task 1.
- Produces: `beat_wpm(vo: VOLine) -> float | None` and `check_pace(vo_lines: list[VOLine]) -> list[Finding]` emitting check `D5` with `kind="fail"` or `kind="skipped"`.

- [ ] **Step 1: Write the failing tests**

Append (and add `check_pace`, `beat_wpm`, `WPM_CEILING` to the imports):

```python
def test_d5_flags_an_over_stuffed_beat():
    lines, _ = parse_script(
        'HOOK (0–3s | 13 words): "Why would a federal proposal count your kid registration app '
        'as youth sports?"\n'
    )
    findings = [f for f in check_pace(lines) if f.kind == "fail"]
    assert [f.check for f in findings] == ["D5"]
    assert "260" in findings[0].message


def test_d5_does_not_flag_an_under_running_beat():
    lines, _ = parse_script('LOOP/CTA (38–45s | 12 words): "You are not taking something away."\n')
    assert [f for f in check_pace(lines) if f.kind == "fail"] == []


def test_d5_tolerance_passes_a_beat_at_171_wpm():
    # 20 words in 7s = 171.4 wpm -- the Dewey sub-beat, "within rounding"
    text = (
        'BUILD/VALUE (21–28s | 20 words): "Dewey named this in 1916 an activity done for a '
        'result outside itself is constrained labor."\n'
    )
    lines, _ = parse_script(text)
    assert beat_wpm(lines[0]) > 170
    assert [f for f in check_pace(lines) if f.kind == "fail"] == []


def test_d5_skips_a_beat_with_no_range_and_says_so():
    lines, _ = parse_script('[re-hook beat @ ~15s]: "His proof, a trader who bought the presses."\n')
    findings = check_pace(lines)
    assert [f.kind for f in findings] == ["skipped"]
    assert findings[0].check == "D5"


def test_d5_counts_on_shipped_fixtures():
    expected = {
        "script_let_kids_play_act.md": 1,
        "script_specialization.md": 2,
        "script_decline.md": 0,
        "script_nobody_asked.md": 0,
    }
    for name, count in expected.items():
        lines, _ = parse_script(_read(name))
        fails = [f for f in check_pace(lines) if f.kind == "fail"]
        assert len(fails) == count, f"{name}: got {len(fails)}"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_lint_script_language.py -v -k d5`
Expected: FAIL — `ImportError: cannot import name 'check_pace'`

- [ ] **Step 3: Implement the check**

Append to `scripts/lint_script_language.py`:

```python
WPM_CEILING = 170
WPM_TOLERANCE = 2


def beat_wpm(vo: VOLine) -> float | None:
    """Words per minute implied by this beat, or None if it carries no range."""
    if vo.start_s is None or vo.end_s is None:
        return None
    duration = vo.end_s - vo.start_s
    if duration <= 0:
        return None
    return word_count(vo.text) / duration * 60


def check_pace(vo_lines: list[VOLine]) -> list[Finding]:
    """D5: a ceiling, not a band.

    Under-running is a legitimate authorial choice -- the corpus asks for
    breathing room so a key word lands [C] (Kallaway, ZM3elcBE48I), and shipped
    scripts run a Loop/CTA at ~103 wpm on purpose. Over-running is a production
    failure: the line cannot be spoken in its seconds, and the bad timing
    propagates into voiceover-brief and shorts-assembly unchallenged."""
    limit = WPM_CEILING + WPM_TOLERANCE
    findings: list[Finding] = []
    for vo in vo_lines:
        wpm = beat_wpm(vo)
        if wpm is None:
            findings.append(
                Finding(
                    "D5",
                    vo.beat,
                    f"line {vo.line_number}: no computable time range; pace unchecked",
                    kind="skipped",
                )
            )
            continue
        if wpm > limit:
            findings.append(
                Finding(
                    "D5",
                    vo.beat,
                    f"line {vo.line_number}: {wpm:.0f} wpm exceeds the {WPM_CEILING} ceiling "
                    f"(+{WPM_TOLERANCE} tolerance) -- more words than fit in the beat",
                )
            )
    return findings
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_lint_script_language.py -v`
Expected: PASS — 26 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_script_language.py tests/test_lint_script_language.py
git commit -m "feat(gate-d): D5 wpm ceiling with skipped-not-passed for untimed beats

A ceiling rather than a band: deliberate slack is a corpus-cited choice
[C] (Kallaway, ZM3elcBE48I), over-stuffing is a production failure. Catches
both 07-25 Hooks at ~260 wpm; passes the Dewey beat at ~171 inside tolerance.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: D6 honesty lock, `lint()`, and the CLI

**Files:**
- Modify: `scripts/lint_script_language.py`
- Modify: `tests/test_lint_script_language.py`

**Interfaces:**
- Consumes: everything from Tasks 1-4.
- Produces: `check_gate_e_reported(text: str) -> list[Finding]`, `lint(vo_lines: list[VOLine], text: str, parse_findings: list[Finding]) -> list[Finding]`, `main(argv: list[str] | None = None) -> int`. `gates.py` (Task 8) calls `parse_script` + `lint`; the skill calls `main` via CLI.

- [ ] **Step 1: Write the failing tests**

Append (and add `check_gate_e_reported`, `lint`, `main` to the imports):

```python
def test_d6_passes_a_well_formed_gate_e_line():
    text = "GATES\n  Gate E (fresh Opus critic):               pass\n"
    assert check_gate_e_reported(text) == []


def test_d6_fails_a_missing_gate_e_line():
    findings = check_gate_e_reported("GATES\n  Gate D (linter): pass\n")
    assert [f.check for f in findings] == ["D6"]


def test_d6_fails_an_empty_gate_e_value():
    assert [f.check for f in check_gate_e_reported("  Gate E (critic):   \n")] == ["D6"]


def test_d6_fails_on_every_shipped_fixture_because_they_predate_the_gate():
    for name in (
        "script_let_kids_play_act.md",
        "script_specialization.md",
        "script_decline.md",
        "script_nobody_asked.md",
    ):
        assert [f.check for f in check_gate_e_reported(_read(name))] == ["D6"], name


def test_decline_hook_loop_mirror_produces_no_gate_d_finding():
    """SKILL.md:108 requires the Loop/CTA to mirror the Hook, and the corpus
    cites it [C] (Jenny Hoyos, mhVDcqnxxaY). A gate that blocks a mandated
    mechanic is worse than no gate -- this is the regression guard for the
    repeated-template check that was removed from Gate D."""
    text = _read("script_decline.md")
    lines, parse_findings = parse_script(text)
    mirrored = [vo for vo in lines if vo.text.strip() == "It won't set him back."]
    assert len(mirrored) >= 1
    findings = lint(lines, text, parse_findings)
    assert [f for f in findings if f.check in ("D2", "D3", "D4")] == []


def test_main_returns_2_on_a_file_with_no_vo_lines(tmp_path):
    path = tmp_path / "empty.md"
    path.write_text("no beats here at all\n", encoding="utf-8")
    assert main([str(path)]) == 2


def test_main_returns_1_on_a_failing_fixture(tmp_path):
    path = tmp_path / "bad.md"
    path.write_text(_read("script_decline.md"), encoding="utf-8")
    assert main([str(path)]) == 1


def test_main_returns_0_on_a_clean_script(tmp_path):
    path = tmp_path / "clean.md"
    path.write_text(
        'HOOK (0–3s | 6 words): "Best part was the mud today."\n'
        "GATES\n  Gate E (fresh Opus critic): pass\n",
        encoding="utf-8",
    )
    assert main([str(path)]) == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_lint_script_language.py -v -k "d6 or main or mirror"`
Expected: FAIL — `ImportError: cannot import name 'check_gate_e_reported'`

- [ ] **Step 3: Implement the lock, aggregator, and CLI**

Append to `scripts/lint_script_language.py`:

```python
GATE_E_RE = re.compile(r"^\s*Gate E\b[^:]*:\s*(\S.*)$", re.MULTILINE)


def check_gate_e_reported(text: str) -> list[Finding]:
    """D6 -- the honesty lock.

    This cannot prove Gate E ran; a skill that skipped it can still write
    `Gate E: pass`. It raises the cost of the omission from silent to
    deliberate, and no further. See the spec's "Known limits"."""
    if GATE_E_RE.search(text):
        return []
    return [
        Finding(
            "D6",
            None,
            "no well-formed `Gate E: <result>` line in the artifact -- "
            "a gate that was not reported is a gate that was not run",
        )
    ]


def lint(vo_lines: list[VOLine], text: str, parse_findings: list[Finding] | None = None) -> list[Finding]:
    """Run every Gate D check, in check order."""
    return [
        *(parse_findings or []),
        *check_punctuation(vo_lines),
        *check_vocabulary(vo_lines),
        *check_pace(vo_lines),
        *check_gate_e_reported(text),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lint_script_language",
        description="Gate D -- read-aloud lint for ContentStudio Short scripts.",
    )
    parser.add_argument("script", type=Path, help="path to an emitted Short script (.md)")
    args = parser.parse_args(argv)

    text = args.script.read_text(encoding="utf-8")
    vo_lines, parse_findings = parse_script(text)
    if not vo_lines:
        print(f"Gate D: no voiceover lines parsed from {args.script}. Check the script format.")
        return 2

    findings = lint(vo_lines, text, parse_findings)
    blocking = [f for f in findings if f.kind != "skipped"]
    skipped = [f for f in findings if f.kind == "skipped"]

    for finding in skipped:
        print(f"  [skipped] {finding.beat or 'script'}: {finding.message}")

    if not blocking:
        print(f"Gate D: PASS -- {len(vo_lines)} voiceover lines, 0 findings.")
        return 0

    print(f"Gate D: FAIL -- {len(vo_lines)} voiceover lines, {len(blocking)} finding(s).")
    for finding in blocking:
        print(f"  [{finding.check}] {finding.beat or 'script'}: {finding.message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the full Gate D suite**

Run: `python -m pytest tests/ -v`
Expected: PASS — all tests, including the pre-existing `test_lint_prompt_sheet.py` and `test_resolve_brief_version.py`

- [ ] **Step 5: Run the linter by hand against all four fixtures**

Run:
```bash
for f in tests/fixtures/script_*.md; do echo "== $f"; python scripts/lint_script_language.py "$f"; done
```
Expected: every file reports `Gate D: FAIL` (all four predate D6). `script_nobody_asked.md` must show **only** a `D6` finding — it is the cleanest of the four and any other check firing on it means a false positive to fix before continuing.

- [ ] **Step 6: Commit**

```bash
git add scripts/lint_script_language.py tests/test_lint_script_language.py
git commit -m "feat(gate-d): D6 honesty lock, lint() aggregator, and CLI

Exit 0 pass / 1 findings / 2 parse error, matching lint_prompt_sheet.py.
Skipped findings print but never block. Includes the regression guard proving
the mandated Hook/Loop mirror produces no Gate D finding.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: The labeled evidence base

**Files:**
- Create: `docs/script-language-baseline.md`

**Interfaces:**
- Consumes: `scripts/lint_script_language.py` (to generate the raw line list).
- Produces: the citation target for every `[S]` marker written in Task 7.

- [ ] **Step 1: Generate the raw line inventory**

Run:
```bash
python - <<'PY'
import sys, pathlib
sys.path.insert(0, "scripts")
from lint_script_language import parse_script, beat_wpm, word_count
for p in sorted(pathlib.Path("tests/fixtures").glob("script_*.md")):
    print(f"\n## {p.name}")
    lines, _ = parse_script(p.read_text(encoding="utf-8"))
    for vo in lines:
        wpm = beat_wpm(vo)
        print(f"- [{vo.beat} L{vo.line_number}] {word_count(vo.text)}w "
              f"{'%.0f wpm' % wpm if wpm else 'no range'} :: {vo.text}")
PY
```

- [ ] **Step 2: Write the baseline document**

Create `docs/script-language-baseline.md`. It must contain, in this order:

1. A **purpose** paragraph stating that this file is the citation target for the `[S]` provenance marker, that `[S]` means "evidenced by this repo's own shipped output," and that an `[S]` rule which cannot name a line here must be marked `[I]` instead.
2. A **scope and limits** section stating: 27 VO lines across 4 scripts; n=4 is thin; the thresholds derived here are calibrated, not validated; and that `output/` is absent so the Nick Nimmin finding's original scope (the cut vs. written VO lines) could not be verified.
3. **One section per script**, listing every VO line from Step 1 with:
   - the beat and word count,
   - the computed wpm (or `no range`),
   - a **verdict**: `pass` or `fail`,
   - if `fail`, the check it evidences (`D1`/`D5`) and a one-line reason,
   - if `pass`, nothing further.
4. A **rule index** mapping each `[S]` rule to its evidencing lines:
   - `D1` → the 7 dash-bearing lines, by script and beat.
   - `D5` → the 3 over-ceiling beats (`let_kids_play_act` Hook ≈260, `specialization` Hook ≈260, `specialization` Setup ≈228).
   - A closing note that **`D2`, `D4`, and `D6` have no evidencing line and are therefore marked `[I]`, not `[S]`** — with a sentence explaining that this constraint was violated by the spec's first draft and is enforced here against its own author.
5. A **contextual failures** section listing the constructions that are *not* Gate D's business — the negation-fragment closers (`"Not athletically."` / `"Not because he cleared a checkpoint."` / `"Not a report card."`), the fragment runs (`"Eighty-one things. Eleven factors."`), and the contorted abstraction (`"That offer moves his reason for playing outside the playing."`). State that these are Gate E's territory because intent is not visible to a regex, and that the shipped scripts defend the first two with `[C] (Nick Nimmin, IF-PD6XMjYY)` — a rule this design does not override.

- [ ] **Step 3: Verify the document against the linter**

Run:
```bash
python - <<'PY'
import sys, pathlib
sys.path.insert(0, "scripts")
from lint_script_language import parse_script, check_punctuation, check_pace
d1 = d5 = 0
for p in sorted(pathlib.Path("tests/fixtures").glob("script_*.md")):
    lines, _ = parse_script(p.read_text(encoding="utf-8"))
    d1 += len([f for f in check_punctuation(lines) if f.check == "D1"])
    d5 += len([f for f in check_pace(lines) if f.kind == "fail"])
print("D1 total:", d1, "expected 7")
print("D5 total:", d5, "expected 3")
PY
```
Expected: `D1 total: 7 expected 7` and `D5 total: 3 expected 3`. If either differs, the document's rule index is wrong — fix the document, not the linter.

- [ ] **Step 4: Commit**

```bash
git add docs/script-language-baseline.md
git commit -m "docs: labeled script-language evidence base (27 VO lines, 4 scripts)

The citation target for the [S] provenance marker. Records which rules have
evidencing lines (D1, D5) and which do not and are therefore [I] (D2, D4, D6),
plus the contextual failures that belong to Gate E rather than Gate D.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: `shorts-scripting` skill — Gate D and Gate E

**Files:**
- Create: `.claude/skills/shorts-scripting/references/read-aloud-gates.md`
- Modify: `.claude/skills/shorts-scripting/SKILL.md` (step 9 at line 115; provenance section at lines 32-57; output contract at lines 146-181; reference-file list at lines 199-215)

**Interfaces:**
- Consumes: `scripts/lint_script_language.py` CLI from Task 5; `docs/script-language-baseline.md` from Task 6.
- Produces: the `GATES` output-contract block that Task 5's `check_gate_e_reported` (D6) matches, and the no-touch annotation vocabulary Gate E consumes.

- [ ] **Step 1: Write `references/read-aloud-gates.md`**

The file must contain these sections. Every normative line carries a marker; cite `[S]` lines into `docs/script-language-baseline.md`.

1. **The Gate D / Gate E boundary.** Gate D checks what is wrong unconditionally; Gate E judges what is wrong only in context. State explicitly that rhythm and template checks live in Gate E, and that this is what keeps the design from overriding `[C] (Nick Nimmin, IF-PD6XMjYY)`.
2. **Gate D — the six checks**, as a table matching the spec's exactly: D1 em/en-dash `[S]`, D2 written punctuation `[I]`, D3 buzzword no-list `[C] (Romayroh, ErCV5czVK1g)`, D4 unspeakable tokens `[I]`, D5 wpm ceiling `[S]`, D6 Gate E reported `[I]`. Include the run command and the two-mode rule:
   - Standalone: `python scripts/lint_script_language.py <path>`, record the real result.
   - Pipeline (app-driven): record `deferred — app-run`. **Never record a pass you did not observe.**
3. **Gate E — the dispatch, verbatim.** A fresh `general-purpose` agent, `model: opus`, told to find the failure and not to approve. The prompt must state the four judgments (written-register syntax; fragment rhythm and template sameness; performed vs. real imperfection; one-breath speakability) and require per finding: the line, why it fails read-aloud, one concrete rewrite.
4. **The Gate E payload contract.** The skill sends VO lines + beat timings + **a per-line no-touch annotation** from this vocabulary: `verbatim-quote`, `citation`, `uncuttable`, `lexicon-screened`, `free`, `unknown`. Delivery notes, Alternates, and the grounding beat map are withheld — the rationale is what makes a written line look justified. **A line the skill cannot classify is `unknown`, and `unknown` is treated as no-touch.**
5. **No-touch zones.** The critic may not rewrite a line annotated anything other than `free`. A finding on such a line is still reported; the rewrite must restructure around the constraint. Include the worked example: the Côté line is fixed by resequencing into two sentences, never by dropping the attribution.
6. **Resolution paths.** A finding is resolved by exactly one of: accepting the rewrite, authoring a different fix, or **defending the line in writing** with its `[C]` citation or binding constraint. Any accepted rewrite is re-checked against the beat's word budget (±2 words) and Gate D is re-run.
7. **Known limits**, copied from the spec: n=4; D6 cannot prove Gate E ran; the Nick Nimmin extension is unverified; the annotation is only as good as the skill's self-classification.

- [ ] **Step 2: Replace step 9 in `SKILL.md`**

Replace the existing step 9 (currently *"Run the humanize pass. Vary sentence length, cut any AI-fingerprint phrase or buzzword, fact-check any specific claim"*) with:

```markdown
9. **Run Gate D, then Gate E.** Gate D is the deterministic linter
   (`scripts/lint_script_language.py`) — run it directly in standalone mode; in
   app-driven mode record `deferred — app-run`, because the app runs it. Gate E
   dispatches a fresh Opus critic that has not seen your authoring rationale.
   **A failing gate blocks emission** until resolved or explicitly overridden,
   and a Gate E finding may be resolved by defending the line in writing rather
   than changing it. Fact-check any specific claim while you are here
   (`references/script-intelligence-and-delivery.md`). Full rules, the verbatim
   dispatch prompt, and the no-touch annotation vocabulary are in
   `references/read-aloud-gates.md` — read it before running either gate.
```

- [ ] **Step 3: Add `[S]` to the provenance section**

In the "Provenance discipline" list (after the `[T]` bullet at lines 52-53), add:

```markdown
- **`[S]`** script-baseline — derived from an observed failure in this repo's
  own shipped output, cited by file and beat in
  `docs/script-language-baseline.md`. Used only by the read-aloud gates. **An
  `[S]` rule that cannot name a real shipped line violating it is a bug — mark
  it `[I]` instead.**
```

- [ ] **Step 4: Add the GATES block to the output contract**

In the output contract fenced block, immediately before the `Visual notes` line, insert:

```
GATES
  Gate D (scripts/lint_script_language.py): <pass | N findings | deferred — app-run>
  Gate E (fresh Opus critic):               <pass | N findings | N defended | overridden: reason>
```

Then add `references/read-aloud-gates.md` to the reference-file list at the end of `SKILL.md` with a one-line description.

- [ ] **Step 5: Verify the GATES block satisfies D6**

Run:
```bash
python - <<'PY'
import sys, re, pathlib
sys.path.insert(0, "scripts")
from lint_script_language import check_gate_e_reported
skill = pathlib.Path(".claude/skills/shorts-scripting/SKILL.md").read_text(encoding="utf-8")
assert "read-aloud-gates.md" in skill, "reference file not linked from SKILL.md"
assert "`[S]`" in skill, "[S] marker not documented in SKILL.md"
# The contract's own template line must be the shape D6 accepts.
template = "  Gate E (fresh Opus critic):               <pass | N findings>"
assert check_gate_e_reported(template) == [], "output contract template would fail D6"
print("OK")
PY
```
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/shorts-scripting/
git commit -m "feat(shorts-scripting): replace the humanize pass with Gates D and E

Step 9 was a self-attestation graded by the turn that wrote the script,
against a no-list of two phrases and five buzzwords. It is now two blocking
gates. Adds the [S] provenance marker and the no-touch annotation vocabulary
that lets Gate E see constraints without seeing the rationale.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: The app-run gate registry

**Files:**
- Create: `pipeline-app/pipeline_app/gates.py`
- Create: `pipeline-app/tests/test_gates.py`
- Modify: `pipeline-app/pipeline_app/turn_service.py:221-246`
- Modify: `pipeline-app/tests/test_turn_service.py`

**Interfaces:**
- Consumes: `scripts/lint_script_language.py` (Task 5) and the existing `scripts/lint_prompt_sheet.py`.
- Produces: `run_gates_for_stage(repo_root: Path, stage_id: str, artifact_path: Path) -> list[dict]` returning `[{"name": str, "status": "pass"|"fail"|"error", "findings": [{"check": str, "beat": str|None, "message": str, "kind": str}]}]`. Task 9 reads this list out of artifact frontmatter under the key `gates`.

- [ ] **Step 1: Write the failing tests**

Create `pipeline-app/tests/test_gates.py`:

```python
from pathlib import Path

import pytest

from pipeline_app import gates

REPO_ROOT = Path(__file__).resolve().parents[2]

CLEAN_SCRIPT = (
    'HOOK (0–3s | 6 words): "Best part was the mud today."\n'
    "GATES\n  Gate E (fresh Opus critic): pass\n"
)
DASHED_SCRIPT = (
    'HOOK (0–3s | 8 words): "It is not more serious play — it is labor."\n'
    "GATES\n  Gate E (fresh Opus critic): pass\n"
)


def test_scripting_stage_passes_a_clean_script(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(CLEAN_SCRIPT, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path)
    assert [r["status"] for r in results] == ["pass"]
    assert results[0]["name"] == "gate_d_script_language"


def test_scripting_stage_fails_a_dashed_script(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(DASHED_SCRIPT, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path)
    assert results[0]["status"] == "fail"
    assert [f["check"] for f in results[0]["findings"]] == ["D1"]


def test_skipped_findings_are_recorded_but_do_not_fail(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(
        'HOOK (0–3s | 6 words): "Best part was the mud today."\n'
        '[re-hook beat @ ~15s]: "His proof, a trader who bought the presses."\n'
        "GATES\n  Gate E (fresh Opus critic): pass\n",
        encoding="utf-8",
    )
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path)
    assert results[0]["status"] == "pass"
    assert any(f["kind"] == "skipped" for f in results[0]["findings"])


def test_unparseable_script_is_an_error_not_a_pass(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text("no beats at all\n", encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path)
    assert results[0]["status"] == "error"


def test_a_linter_that_raises_is_an_error_not_a_pass(tmp_path, monkeypatch):
    def boom(_repo_root, _path):
        raise RuntimeError("linter exploded")

    monkeypatch.setitem(gates.GATE_REGISTRY, "scripting", [("gate_boom", boom)])
    path = tmp_path / "raw_output.md"
    path.write_text(CLEAN_SCRIPT, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path)
    assert results[0]["status"] == "error"
    assert "linter exploded" in results[0]["findings"][0]["message"]


def test_visual_stage_is_registered():
    assert "visual" in gates.GATE_REGISTRY


def test_unregistered_stage_returns_no_results(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text("anything\n", encoding="utf-8")
    assert gates.run_gates_for_stage(REPO_ROOT, "ideation", path) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest pipeline-app/tests/test_gates.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline_app.gates'`

- [ ] **Step 3: Implement the registry**

Create `pipeline-app/pipeline_app/gates.py`:

```python
"""Deterministic gates the app runs on a stage's output after its turn.

A pipeline turn cannot shell out -- cli_runner denies Bash and PowerShell, and
that denial closes a real Windows cmd-shim quoting escape. So a skill's own
`python scripts/lint_*.py` instruction is unrunnable in app mode. Before this
module existed, visual-prompts' Gate C either failed every app run or recorded
a pass that never happened. The app runs the linters instead.

Linters live in scripts/ and are stdlib-only standalone tools with no package
identity, so they are loaded by file path rather than imported.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable

GateRunner = Callable[[Path, Path], list[dict]]


def _load_linter(repo_root: Path, module_name: str):
    path = repo_root / "scripts" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load linter at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _as_dicts(findings: list[Any]) -> list[dict]:
    return [asdict(f) if is_dataclass(f) else dict(f) for f in findings]


def run_script_language_gate(repo_root: Path, artifact_path: Path) -> list[dict]:
    linter = _load_linter(repo_root, "lint_script_language")
    text = artifact_path.read_text(encoding="utf-8")
    vo_lines, parse_findings = linter.parse_script(text)
    if not vo_lines:
        raise ValueError(
            f"no voiceover lines parsed from {artifact_path.name} -- check the script format"
        )
    return _as_dicts(linter.lint(vo_lines, text, parse_findings))


def run_prompt_sheet_gate(repo_root: Path, artifact_path: Path) -> list[dict]:
    linter = _load_linter(repo_root, "lint_prompt_sheet")
    shots, world = linter.parse_sheet(artifact_path.read_text(encoding="utf-8"))
    if not shots:
        raise ValueError(f"no shots parsed from {artifact_path.name} -- check the sheet format")
    return _as_dicts(linter.lint(shots, world))


GATE_REGISTRY: dict[str, list[tuple[str, GateRunner]]] = {
    "scripting": [("gate_d_script_language", run_script_language_gate)],
    "visual": [("gate_c_prompt_sheet", run_prompt_sheet_gate)],
}


def run_gates_for_stage(repo_root: Path, stage_id: str, artifact_path: Path) -> list[dict]:
    """Run every gate registered for this stage. Fail-closed: a linter that
    raises produces status "error", never a silent pass -- a gate whose result
    is unknown must block approval exactly as a failing one does.

    A "skipped" finding (e.g. a beat with no computable time range) is recorded
    but does not fail the gate: it is a known unknown, surfaced rather than
    swallowed.

    Every runner takes (repo_root, artifact_path). Do not add a signature
    fallback here -- catching TypeError to retry with fewer arguments would
    swallow a genuine TypeError raised inside a linter and report it as a
    signature mismatch."""
    results: list[dict] = []
    for name, runner in GATE_REGISTRY.get(stage_id, []):
        try:
            findings = runner(repo_root, artifact_path)
        except Exception as exc:  # noqa: BLE001 -- fail-closed is the whole point
            results.append({
                "name": name,
                "status": "error",
                "findings": [{"check": "GATE", "beat": None, "message": str(exc), "kind": "error"}],
            })
            continue
        blocking = [f for f in findings if f.get("kind") != "skipped"]
        results.append({
            "name": name,
            "status": "fail" if blocking else "pass",
            "findings": findings,
        })
    return results
```

- [ ] **Step 4: Run the gate tests to verify they pass**

Run: `python -m pytest pipeline-app/tests/test_gates.py -v`
Expected: PASS — 7 passed

- [ ] **Step 5: Wire the registry into `turn_service`**

In `pipeline-app/pipeline_app/turn_service.py`, add `gates` to the import on line 9:

```python
from pipeline_app import artifacts, cli_runner, db as db_mod, gates, prompt_builder
```

Then, between the `depends_on` list comprehension and the `meta = {` assignment (around lines 230-245), insert:

```python
    gate_results = gates.run_gates_for_stage(repo_root, stage_def.id, raw_output_path)
```

and add to the `meta` dict, after `"depends_on": depends_on,`:

```python
        "gates": gate_results,
```

- [ ] **Step 6: Write the turn_service integration test**

Append to `pipeline-app/tests/test_turn_service.py`:

Add `gates` to that file's `pipeline_app` import line, then append. Seeding is inline, matching
the style of `test_approve_stamps_artifact_and_unlocks_dependent` in `test_approval_service.py`
— `test_turn_service.py`'s own `project` fixture only creates the `ideation` row, and this test
needs `scripting`:

```python
@pytest.mark.asyncio
async def test_scripting_turn_records_gate_results_in_frontmatter(conn, tmp_path, monkeypatch):
    """A failing gate must not hide the artifact that failed it -- the stage
    still reaches awaiting_review with the file on disk."""
    project_id = db.create_project(conn, "gate-1", "gate", "generic", "2026-08-06T00:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "approved")
    db.create_stage_row(conn, project_id, "scripting", "ready")

    run_dir = tmp_path / "runs" / "gate-1"
    stage_dir = run_dir / "02-scripting"
    raw = stage_dir / "raw_output.md"

    monkeypatch.setattr(
        turn_service.cli_runner,
        "stream_claude_turn",
        _fake_stream(
            [{"type": "result", "result": "ok", "total_cost_usd": 0.1, "is_error": False}],
            writes_file=raw,
            content=(
                'HOOK (0–3s | 8 words): "It is not more serious play — it is labor."\n'
                "GATES\n  Gate E (fresh Opus critic): pass\n"
            ),
        ),
    )
    monkeypatch.setattr(
        turn_service.gates,
        "run_gates_for_stage",
        lambda root, sid, path: [{
            "name": "gate_d_script_language",
            "status": "fail",
            "findings": [{"check": "D1", "beat": "HOOK", "message": "em-dash", "kind": "fail"}],
        }],
    )

    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "gate-1",
        STAGES[1], STAGES, "go",
    ))

    latest = artifacts.latest_artifact_path(stage_dir)
    assert latest is not None
    meta, _ = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))
    assert meta["gates"][0]["status"] == "fail"
    assert db.get_stage(conn, project_id, "scripting")["status"] == StageStatus.AWAITING_REVIEW.value
```

`STAGES` in `test_turn_service.py` must contain a `scripting` entry with `dir_prefix="02"` for
the `02-scripting` path above to resolve. Read the file's `STAGES` list first; if it has only
`ideation`, define a module-level `GATE_STAGES` list alongside it holding both stage defs and use
that in this test rather than mutating the shared one.

- [ ] **Step 7: Run the app suite**

Run: `python -m pytest pipeline-app/tests/ -v`
Expected: PASS — all tests

- [ ] **Step 8: Commit**

```bash
git add pipeline-app/pipeline_app/gates.py pipeline-app/pipeline_app/turn_service.py pipeline-app/tests/test_gates.py pipeline-app/tests/test_turn_service.py
git commit -m "feat(app): run stage gates post-turn and record them in frontmatter

Pipeline turns cannot shell out, so a skill's own 'python scripts/lint_*.py'
instruction is unrunnable in app mode -- visual-prompts' Gate C has been
silently unsatisfiable. The app runs the linters instead. Fail-closed: a
linter that raises is 'error', never a silent pass.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: Block approval on a failing gate

**Files:**
- Modify: `pipeline-app/pipeline_app/approval_service.py:10-45`
- Modify: `pipeline-app/pipeline_app/artifacts.py:79-83`
- Modify: `pipeline-app/pipeline_app/routes/stages.py:195-209`
- Modify: `pipeline-app/tests/test_approval_service.py`

**Interfaces:**
- Consumes: the `gates` frontmatter key from Task 8.
- Produces: `approve_stage(..., override_reason: str | None = None)` — raises `ValueError` on a failing gate with no override; `stamp_final(path, finalized_at, gate_override_reason=None)`.

- [ ] **Step 1: Write the failing tests**

Append to `pipeline-app/tests/test_approval_service.py`:

```python
def _write_artifact_with_gates(stage_dir: Path, status: str) -> Path:
    meta = {
        "schema_version": 1, "run_id": "r1", "stage": "shorts-scripting", "version": 1,
        "status": "draft", "created_at": "2026-08-06T00:00:00+00:00", "finalized_at": None,
        "supersedes": None, "depends_on": [],
        "gates": [{
            "name": "gate_d_script_language", "status": status,
            "findings": [{"check": "D1", "beat": "HOOK", "message": "em-dash", "kind": "fail"}],
        }],
    }
    return artifacts.write_artifact(stage_dir, 1, meta, "body")


def test_approve_raises_on_a_failing_gate_without_an_override(conn, tmp_path):
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    _write_artifact_with_gates(stage_dir, "fail")
    with pytest.raises(ValueError, match="gate"):
        approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting")


def test_approve_raises_on_an_errored_gate_without_an_override(conn, tmp_path):
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    _write_artifact_with_gates(stage_dir, "error")
    with pytest.raises(ValueError, match="gate"):
        approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting")


def test_approve_succeeds_with_an_override_and_records_the_reason(conn, tmp_path):
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    path = _write_artifact_with_gates(stage_dir, "fail")
    approve_stage(
        conn, tmp_path, run_dir, project_id, STAGES, "scripting",
        override_reason="dash is inside a verbatim 1886 quote",
    )
    meta, _ = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["status"] == "final"
    assert meta["gate_override_reason"] == "dash is inside a verbatim 1886 quote"
    assert meta["gates"][0]["status"] == "fail"  # the record is not rewritten


def test_approve_succeeds_normally_on_a_passing_gate(conn, tmp_path):
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    _write_artifact_with_gates(stage_dir, "pass")
    approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting")
    assert db.get_stage(conn, project_id, "scripting")["status"] == StageStatus.APPROVED.value
```

Add the seeding helper as a module-level function in the same file, matching the inline style of
`test_approve_stamps_artifact_and_unlocks_dependent`:

```python
def _seed_scripting_awaiting_review(conn, tmp_path: Path) -> tuple[int, Path, Path]:
    project_id = db.create_project(conn, "gate-1", "gate", "generic", "2026-08-06T00:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "approved")
    db.create_stage_row(conn, project_id, "scripting", "awaiting_review")
    run_dir = tmp_path / "runs" / "gate-1"
    stage_dir = run_dir / "02-scripting"
    stage_dir.mkdir(parents=True, exist_ok=True)
    return project_id, run_dir, stage_dir
```

This requires `STAGES` in `test_approval_service.py` to carry `dir_prefix="02"` on its `scripting`
entry — it already does (see the file's `STAGES` at the top). `import pytest` is already present.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest pipeline-app/tests/test_approval_service.py -v -k gate`
Expected: FAIL — `TypeError: approve_stage() got an unexpected keyword argument 'override_reason'`

- [ ] **Step 3: Extend `stamp_final`**

In `pipeline-app/pipeline_app/artifacts.py`, replace `stamp_final`:

```python
def stamp_final(path: Path, finalized_at: str, gate_override_reason: str | None = None) -> None:
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    meta["status"] = "final"
    meta["finalized_at"] = finalized_at
    if gate_override_reason:
        # Recorded alongside the failing gate result, which is deliberately left
        # untouched -- an override says a human accepted the finding, not that
        # the finding was wrong.
        meta["gate_override_reason"] = gate_override_reason
    path.write_text(render_frontmatter(meta, body), encoding="utf-8")
```

- [ ] **Step 4: Add the gate check to `approve_stage`**

In `pipeline-app/pipeline_app/approval_service.py`, change the signature to accept `override_reason: str | None = None`, and insert after `latest_meta, _ = artifacts.parse_frontmatter(...)`:

```python
    failing = [
        g for g in (latest_meta.get("gates") or [])
        if g.get("status") in ("fail", "error")
    ]
    if failing and not override_reason:
        names = ", ".join(f"{g['name']} ({g['status']})" for g in failing)
        raise ValueError(
            f"Stage '{stage_id}' has a failing gate: {names}. "
            "Fix the findings and regenerate, or approve with an override reason."
        )
```

Then pass the reason through to the stamp:

```python
    if stage_id != "grounding" and not already_final:
        artifacts.stamp_final(latest, now, gate_override_reason=override_reason)
```

- [ ] **Step 5: Thread the reason through the route**

In `pipeline-app/pipeline_app/routes/stages.py`, change the approve route to accept an optional form field and pass it on:

```python
@router.post("/projects/{project_id}/stages/{stage_id}/approve")
def approve_stage_route(
    request: Request,
    project_id: int,
    stage_id: str,
    override_reason: str = Form(""),
):
    project, _stage_def, _stage_row = _resolve_project_stage(request, project_id, stage_id)
    conn = request.app.state.conn
    repo_root = request.app.state.repo_root
    stage_defs = request.app.state.stage_defs
    run_dir = repo_root / "runs" / project["run_id"]
    try:
        approval_service.approve_stage(
            conn, repo_root, run_dir, project_id, stage_defs, stage_id,
            override_reason=override_reason.strip() or None,
        )
    except ValueError as exc:
        # Nothing to approve yet, the locked/running invariant, or a failing
        # gate -- approval_service raises for all three; an explicit conflict
        # state, never a 500.
        return PlainTextResponse(str(exc), status_code=409)
    return RedirectResponse(url=f"/projects/{project_id}/stages/{stage_id}", status_code=303)
```

- [ ] **Step 6: Run the app suite**

Run: `python -m pytest pipeline-app/tests/ -v`
Expected: PASS — all tests. Existing `approve_stage` callers pass no `override_reason` and keep working because it defaults to `None`.

- [ ] **Step 7: Commit**

```bash
git add pipeline-app/pipeline_app/approval_service.py pipeline-app/pipeline_app/artifacts.py pipeline-app/pipeline_app/routes/stages.py pipeline-app/tests/test_approval_service.py
git commit -m "feat(app): block approval on a failing gate unless overridden

A failing or errored gate raises ValueError -> 409, the same conflict path as
the locked/running invariant. An override records its reason in frontmatter
and deliberately leaves the failing gate result intact: an override says a
human accepted the finding, not that the finding was wrong.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 10: `Task` in the sandbox, and Gate C's two modes

**Files:**
- Modify: `pipeline-app/pipeline_app/cli_runner.py:224`
- Modify: `pipeline-app/tests/test_cli_runner.py`
- Modify: `.claude/skills/visual-prompts/SKILL.md:317-327`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: no code interface. This is the change that makes Gate E dispatchable at all.

- [ ] **Step 1: Write the failing test**

Append to `pipeline-app/tests/test_cli_runner.py`:

```python
def test_default_allowed_tools_includes_task():
    """Gate E (shorts-scripting) and Gate B (midjourney-prompting) both dispatch
    a fresh reviewing agent via Task. cli_runner's comments say Task is
    deliberately undenied, but the allowed_tools default never listed it, and
    headless -p has no one to approve an unlisted tool -- so Gate B has very
    likely been failing silently."""
    import inspect

    signature = inspect.signature(cli_runner.stream_claude_turn)
    default = signature.parameters["allowed_tools"].default
    assert "Task" in default.split(",")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest pipeline-app/tests/test_cli_runner.py -v -k task`
Expected: FAIL — `AssertionError`

- [ ] **Step 3: Add `Task` to the default**

In `pipeline-app/pipeline_app/cli_runner.py`, change the `stream_claude_turn` default (line 224):

```python
    # Task is required, not optional: midjourney-prompting's Gate B and
    # shorts-scripting's Gate E both dispatch a fresh reviewing agent through
    # it. PIPELINE_DISALLOWED_TOOLS deliberately does not deny Task, but
    # --allowedTools is the auto-approve list and headless -p has nobody to
    # approve anything absent from it -- so omitting Task here silently
    # degraded Gate B rather than surfacing an error.
    allowed_tools: str = "Read,Glob,Grep,Write,Edit,Skill,Task",
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest pipeline-app/tests/test_cli_runner.py -v`
Expected: PASS

- [ ] **Step 5: Fix Gate C's instruction in `visual-prompts/SKILL.md`**

Replace the mandatory-Bash block (around lines 317-327) so it states both modes. It must keep the existing "never record a pass you did not observe" rule and add the third truthful value:

```markdown
**Before emitting the sheet, run Gate C — this is mandatory, not optional.**

**Standalone** (you were not given an output path by the pipeline app):

```bash
python scripts/lint_prompt_sheet.py <path-to-sheet.md>
```

Record the observed result.

**App-driven** (a `pipeline-app` turn gave you an output path): a pipeline turn
cannot shell out — `Bash` is denied — so record `Gate C: deferred — app-run`.
The app runs `scripts/lint_prompt_sheet.py` over your output after the turn and
blocks approval on its findings. `[I]`

Never state or record Gate C as "passed" without having actually run it and
observed exit 0 `[I]`. `deferred — app-run` is the honest value when you could
not run it; it is not a pass and must not be written as one.
```

- [ ] **Step 6: Verify the whole thing end to end**

Run:
```bash
python -m pytest tests/ -v && python -m pytest pipeline-app/tests/ -v
```
Expected: PASS — both suites green.

Then confirm the linter still behaves on a real script:
```bash
python scripts/lint_script_language.py tests/fixtures/script_nobody_asked.md
```
Expected: `Gate D: FAIL` with exactly one finding, `[D6]` — the cleanest of the four scripts, failing only the honesty lock it predates.

- [ ] **Step 7: Commit**

```bash
git add pipeline-app/pipeline_app/cli_runner.py pipeline-app/tests/test_cli_runner.py .claude/skills/visual-prompts/SKILL.md
git commit -m "fix: add Task to pipeline allowed_tools and give Gate C two honest modes

Task was absent from the allowed_tools default while the code comments
asserted it was available, so midjourney-prompting's Gate B has very likely
been failing silently -- and Gate E could not have dispatched at all.

Gate C now records 'deferred — app-run' in pipeline mode instead of claiming
a pass it never ran.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Post-implementation verification

Not a task — run these once the plan is complete, before calling the work done.

1. **`Task` actually dispatches in a live pipeline turn.** The spec flags this as asserted-in-comments, not tested. Start the app, run a scripting stage, and confirm from the turn's event stream that a `Task` tool use appears and completes. If it does not, Gate E cannot block in app mode and the spec's fallback (app-run Gate E) becomes a new, unscoped subsystem — stop and report rather than improvising it.
2. **`model: opus` reaches the subagent** rather than silently inheriting the session model. Check the subagent's init event in the recorded `events/*.jsonl`.
3. **Gate E findings are not suspiciously sparse.** D6 cannot prove Gate E ran (spec, "Known limits"). If the first several scripts all report `Gate E: pass` with zero findings, treat that as evidence the gate is being skipped, not as evidence the scripts are clean.
