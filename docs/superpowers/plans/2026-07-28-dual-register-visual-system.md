# Dual-Register Visual System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ContentStudio's repetitive single-register visual prompt generation with a two-register visual storytelling system (present-day photographic + source-era painterly), enforced by a runnable shot-variety linter, emitting comprehensive 9-layer prompts in a copy-paste-ready sheet format.

**Architecture:** A new Python linter (`scripts/lint_prompt_sheet.py`) makes Gate C deterministic and testable — it parses an emitted prompt sheet and enforces 14 checks covering shot variety, register separation, world lock, prompt density, and copy-paste format. Three new reference files in the `visual-prompts` skill carry the register contracts, the arc discipline, and the output contract; `SKILL.md` gains two workflow steps that plan the whole sheet as a sequence before any prompt is written. `midjourney-prompting` gains a `register` input and a 9-layer density gate.

**Tech Stack:** Python 3.14 (stdlib only — `re`, `dataclasses`, `argparse`, `pathlib`), pytest 8.3.5, Markdown skill files.

## Global Constraints

- **Provenance markers are mandatory.** Every normative line added to any skill file carries `[C]` (corpus-cited, with `(Channel, video_id)`), `[I]` (industry practice / this skill's own judgment), `[T]` (web-verified tool fact, dated), or `[T-unverified]`. An unmarked normative line is a bug.
- **Never delete a cited `[C]` line to resolve a conflict.** Keep both lines visible with the reason. This applies specifically to "Short usually beats long" `[C] (Tokenized AI, vezJXJGQMoY)` vs. the new density rule.
- **The linter is stdlib-only.** Do not add dependencies to `requirements.txt`.
- **Registers are named generically in skill prose** (`present` / `source-era`, register A / register B). RaisingGoodSports specifics (sport, thinker) appear only as worked examples, never as hardcoded rules.
- **Every prompt ends `No Text.` before its flags** `[C] (Tokenized AI, qFYJb0zYztY)`.
- **Register A parameter band:** `--raw` present, `--s` 80–120. **Register B:** no `--raw`, `--s` 400–700. Both are the documented bands in `midjourney-prompting/references/prompt-architecture.md` `[T] (verified 2026-07-26)`.
- **Banned Register B vocabulary:** `DSLR`, `shot on 35mm film`, `documentary`, any `<n>mm`, any `f/<n>`.
- **Banned Register A vocabulary:** `empty gym`, `empty youth gym`.
- **Shot class vocabulary is closed.** Register A: `ESTABLISHING`, `ACTION-ADJACENT`, `DETAIL`, `HUMAN-COST`. Register B: `FIGURE`, `WORLD`, `ARTIFACT`. Neither: `PLATE`.
- **Scale vocabulary is closed:** `XWIDE`, `WIDE`, `MID-WIDE`, `MID`, `CLOSE`, `MACRO`.
- **Camera height vocabulary is closed:** `LOW`, `EYE`, `HIGH`, `OVERHEAD`.
- **Do not hand-edit `cowork-plugin/skills/`** — regenerate via `scripts/build-cowork-plugin.sh`.
- **Commit after every task.** Conventional commit prefixes (`feat:`, `test:`, `docs:`, `chore:`).

---

## File Structure

| Path | Responsibility |
|---|---|
| `scripts/lint_prompt_sheet.py` | **Create.** Parses a prompt sheet; runs the 14 Gate C checks; CLI entry point. |
| `tests/test_lint_prompt_sheet.py` | **Create.** Unit tests for parsing and every check. |
| `tests/fixtures/failing_sheet.md` | **Create.** Regression fixture distilled from the known-bad run. Must fail. |
| `tests/fixtures/passing_sheet.md` | **Create.** Minimal valid sheet. Must pass. |
| `.claude/skills/visual-prompts/references/visual-registers.md` | **Create.** The two register contracts, shot classes, world lock, motif bridge. |
| `.claude/skills/visual-prompts/references/visual-arc.md` | **Create.** Arc-first discipline, scale/height/optics rotation, the Gate C table. |
| `.claude/skills/visual-prompts/references/prompt-sheet-format.md` | **Create.** The copy-paste output contract the linter parses. |
| `.claude/skills/visual-prompts/SKILL.md` | **Modify.** New steps 2.5 and 3; register in delegation; delete shared-style-vocabulary; Gate C on emit. |
| `.claude/skills/visual-prompts/references/worked-example.md` | **Rewrite.** A full dual-register sheet that passes the linter. |
| `.claude/skills/midjourney-prompting/SKILL.md` | **Modify.** `register` input, density rule, Gate A4b. |
| `.claude/skills/midjourney-prompting/references/prompt-architecture.md` | **Modify.** Density-not-length section resolving the `[C]` conflict. |
| `.claude/skills/midjourney-prompting/references/validation-gates.md` | **Modify.** Gate A4b — all 9 layers in pipeline mode. |
| `CLAUDE.md` | **Modify.** One line in the skills table noting the dual-register output. |

---

## Task 1: Linter scaffold — data model and sheet parser

**Files:**
- Create: `scripts/lint_prompt_sheet.py`
- Create: `tests/test_lint_prompt_sheet.py`
- Create: `tests/__init__.py` (empty)

**Interfaces:**
- Consumes: nothing (first task)
- Produces:
  - `Shot` frozen dataclass: `index: int`, `beat: str`, `register: str`, `shot_class: str`, `scale: str`, `camera_height: str`, `prompt: str`, `prompt_line_count: int`
  - `Finding` frozen dataclass: `check: str`, `shot_index: int | None`, `message: str`
  - `parse_sheet(text: str) -> tuple[list[Shot], dict[str, str]]`
  - `prompt_body(shot: Shot) -> str`
  - `prompt_flags(shot: Shot) -> str`
  - `body_clauses(shot: Shot) -> list[str]`
  - `body_word_count(shot: Shot) -> int`
  - `signature_objects(world: dict[str, str]) -> list[str]`

- [ ] **Step 1: Write the failing test**

Create `tests/__init__.py` as an empty file, then create `tests/test_lint_prompt_sheet.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lint_prompt_sheet import (  # noqa: E402
    Shot,
    parse_sheet,
    prompt_body,
    prompt_flags,
    body_clauses,
    body_word_count,
    signature_objects,
)

SHEET = """\
=== VISUAL PROMPT SHEET — demo ===

WORLD LOCK
  register_a_sport: club soccer
  register_a_venue: municipal club soccer complex
  register_a_signature_objects: goal net, corner flag, painted touchline
  register_b_thinker: Plutarch

PER-SHOT PROMPTS

### Shot 1 — Hook (0–3s) · Register A · DETAIL · MACRO · LOW
Changes vs. previous: opening frame.

```text
documentary sports photography, a strap being pulled tight, on cropped winter turf, No Text. --ar 9:16 --raw --s 95
```

### Shot 2 — Setup (3–8s) · Register B · WORLD · XWIDE · EYE
Changes vs. previous: register switch to the source era.

```text
luminous oil painting on aged linen, a colonnade at dawn, olive branches beyond, No Text. --ar 9:16 --s 520
```
"""


def test_parse_sheet_returns_two_shots():
    shots, world = parse_sheet(SHEET)
    assert len(shots) == 2


def test_parse_sheet_reads_shot_metadata():
    shots, _ = parse_sheet(SHEET)
    first = shots[0]
    assert first.index == 1
    assert first.beat == "Hook (0–3s)"
    assert first.register == "A"
    assert first.shot_class == "DETAIL"
    assert first.scale == "MACRO"
    assert first.camera_height == "LOW"
    assert first.prompt_line_count == 1


def test_parse_sheet_reads_prompt_text():
    shots, _ = parse_sheet(SHEET)
    assert shots[0].prompt.startswith("documentary sports photography,")
    assert shots[0].prompt.endswith("--ar 9:16 --raw --s 95")


def test_parse_sheet_reads_world_lock():
    _, world = parse_sheet(SHEET)
    assert world["register_a_sport"] == "club soccer"
    assert world["register_b_thinker"] == "Plutarch"


def test_signature_objects_splits_on_commas():
    _, world = parse_sheet(SHEET)
    assert signature_objects(world) == ["goal net", "corner flag", "painted touchline"]


def test_prompt_body_and_flags_split_at_first_flag():
    shots, _ = parse_sheet(SHEET)
    assert prompt_flags(shots[0]) == "--ar 9:16 --raw --s 95"
    assert "--ar" not in prompt_body(shots[0])
    assert prompt_body(shots[0]).endswith("No Text.")


def test_body_clauses_excludes_no_text_marker():
    shots, _ = parse_sheet(SHEET)
    clauses = body_clauses(shots[0])
    assert clauses == [
        "documentary sports photography",
        "a strap being pulled tight",
        "on cropped winter turf",
    ]


def test_body_word_count_ignores_no_text_marker():
    shot = Shot(
        index=1,
        beat="Hook",
        register="A",
        shot_class="DETAIL",
        scale="MACRO",
        camera_height="LOW",
        prompt="alpha beta gamma, delta epsilon, No Text. --ar 9:16",
        prompt_line_count=1,
    )
    assert body_word_count(shot) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -v
```

Expected: collection error — `ModuleNotFoundError: No module named 'lint_prompt_sheet'`.

- [ ] **Step 3: Write minimal implementation**

Create `scripts/lint_prompt_sheet.py`:

```python
"""Gate C — deterministic shot-variety lint for ContentStudio visual prompt sheets.

Parses the copy-paste sheet format emitted by the `visual-prompts` skill and enforces
the dual-register visual system's variety, world-lock, density and format rules.

Stdlib only. See docs/superpowers/specs/2026-07-28-dual-register-visual-system-design.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SHOT_HEADING_RE = re.compile(
    r"^###\s+Shot\s+(\d+)\s+—\s+(.+?)\s+·\s+Register\s+(A|B|PLATE)"
    r"\s+·\s+([A-Z-]+)\s+·\s+([A-Z-]+)\s+·\s+([A-Z]+)\s*$"
)
OPEN_FENCE_RE = re.compile(r"^\s*```text\s*$")
CLOSE_FENCE_RE = re.compile(r"^\s*```\s*$")
WORLD_HEADING_RE = re.compile(r"^\s*WORLD LOCK\s*$")
WORLD_ENTRY_RE = re.compile(r"^\s+([a-z][a-z0-9_]*)\s*:\s*(.+?)\s*$")

NO_TEXT_MARKER = "No Text."


@dataclass(frozen=True)
class Shot:
    index: int
    beat: str
    register: str
    shot_class: str
    scale: str
    camera_height: str
    prompt: str
    prompt_line_count: int


@dataclass(frozen=True)
class Finding:
    check: str
    shot_index: int | None
    message: str


def parse_sheet(text: str) -> tuple[list[Shot], dict[str, str]]:
    """Return (shots in sheet order, world-lock key/value pairs)."""
    lines = text.splitlines()
    shots: list[Shot] = []
    world: dict[str, str] = {}

    i = 0
    while i < len(lines):
        if WORLD_HEADING_RE.match(lines[i]):
            i += 1
            while i < len(lines):
                entry = WORLD_ENTRY_RE.match(lines[i])
                if not entry:
                    break
                world[entry.group(1)] = entry.group(2)
                i += 1
            continue

        heading = SHOT_HEADING_RE.match(lines[i])
        if heading:
            prompt_lines, next_i = _read_fenced_prompt(lines, i + 1)
            shots.append(
                Shot(
                    index=int(heading.group(1)),
                    beat=heading.group(2),
                    register=heading.group(3),
                    shot_class=heading.group(4),
                    scale=heading.group(5),
                    camera_height=heading.group(6),
                    prompt=" ".join(prompt_lines).strip(),
                    prompt_line_count=len(prompt_lines),
                )
            )
            i = next_i
            continue

        i += 1

    return shots, world


def _read_fenced_prompt(lines: list[str], start: int) -> tuple[list[str], int]:
    """Read the next ```text fence after `start`. Returns (non-empty lines, index after it)."""
    i = start
    while i < len(lines) and not OPEN_FENCE_RE.match(lines[i]):
        if SHOT_HEADING_RE.match(lines[i]):
            return [], i
        i += 1
    if i >= len(lines):
        return [], i
    i += 1
    collected: list[str] = []
    while i < len(lines) and not CLOSE_FENCE_RE.match(lines[i]):
        if lines[i].strip():
            collected.append(lines[i].strip())
        i += 1
    return collected, i + 1


def prompt_body(shot: Shot) -> str:
    """Everything before the first flag."""
    marker = shot.prompt.find(" --")
    return shot.prompt.strip() if marker == -1 else shot.prompt[:marker].strip()


def prompt_flags(shot: Shot) -> str:
    """The flag block, or "" if there is none."""
    marker = shot.prompt.find(" --")
    return "" if marker == -1 else shot.prompt[marker:].strip()


def _body_without_no_text(shot: Shot) -> str:
    body = prompt_body(shot)
    if body.endswith(NO_TEXT_MARKER):
        body = body[: -len(NO_TEXT_MARKER)].strip()
    return body.rstrip(",").strip()


def body_clauses(shot: Shot) -> list[str]:
    """Lowercased, comma-separated clauses of the body, excluding the No Text. marker."""
    return [c.strip().lower() for c in _body_without_no_text(shot).split(",") if c.strip()]


def body_word_count(shot: Shot) -> int:
    return len(_body_without_no_text(shot).split())


def signature_objects(world: dict[str, str]) -> list[str]:
    raw = world.get("register_a_signature_objects", "")
    return [o.strip() for o in raw.split(",") if o.strip()]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_prompt_sheet.py tests/__init__.py tests/test_lint_prompt_sheet.py
git commit -m "feat(lint): prompt-sheet parser and data model for Gate C"
```

---

## Task 2: Gate C sequence checks (C1–C5)

**Files:**
- Modify: `scripts/lint_prompt_sheet.py`
- Modify: `tests/test_lint_prompt_sheet.py`

**Interfaces:**
- Consumes: `Shot`, `Finding` from Task 1
- Produces: `check_sequence(shots: list[Shot]) -> list[Finding]` emitting checks `C1`–`C5`

C1 no two consecutive shots share a shot class · C2 no two consecutive shots share a scale · C3 no run of more than 2 in the same register, `PLATE` transparent · C4 ≥3 distinct scales · C5 ≥2 distinct camera heights.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lint_prompt_sheet.py`. Add `check_sequence` and `Finding` to the import list at the top of the file first:

```python
def make_shot(index, register="A", shot_class="DETAIL", scale="MACRO",
              camera_height="LOW", prompt="alpha, beta, No Text. --ar 9:16"):
    return Shot(
        index=index,
        beat=f"Beat {index}",
        register=register,
        shot_class=shot_class,
        scale=scale,
        camera_height=camera_height,
        prompt=prompt,
        prompt_line_count=1,
    )


def codes(findings):
    return sorted({f.check for f in findings})


VARIED = [
    make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
    make_shot(2, "B", "WORLD", "XWIDE", "EYE"),
    make_shot(3, "A", "ESTABLISHING", "WIDE", "HIGH"),
    make_shot(4, "B", "FIGURE", "MID", "EYE"),
    make_shot(5, "A", "HUMAN-COST", "CLOSE", "LOW"),
]


def test_c1_flags_repeated_adjacent_shot_class():
    shots = [
        make_shot(1, "A", "HUMAN-COST", "MID", "LOW"),
        make_shot(2, "B", "HUMAN-COST", "WIDE", "EYE"),
        make_shot(3, "A", "DETAIL", "MACRO", "HIGH"),
    ]
    assert "C1" in codes(check_sequence(shots))


def test_c2_flags_repeated_adjacent_scale():
    shots = [
        make_shot(1, "A", "DETAIL", "MID", "LOW"),
        make_shot(2, "B", "WORLD", "MID", "EYE"),
        make_shot(3, "A", "ESTABLISHING", "WIDE", "HIGH"),
    ]
    assert "C2" in codes(check_sequence(shots))


def test_c3_flags_run_of_three_in_same_register():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "A", "HUMAN-COST", "MID", "EYE"),
        make_shot(3, "A", "ESTABLISHING", "WIDE", "HIGH"),
        make_shot(4, "B", "WORLD", "XWIDE", "EYE"),
    ]
    assert "C3" in codes(check_sequence(shots))


def test_c3_treats_plate_as_transparent():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "PLATE", "PLATE", "MID", "EYE"),
        make_shot(3, "A", "ESTABLISHING", "WIDE", "HIGH"),
        make_shot(4, "B", "WORLD", "XWIDE", "EYE"),
    ]
    assert "C3" in codes(check_sequence(shots))


def test_c4_flags_fewer_than_three_scales():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "B", "WORLD", "WIDE", "EYE"),
        make_shot(3, "A", "ESTABLISHING", "MACRO", "HIGH"),
    ]
    assert "C4" in codes(check_sequence(shots))


def test_c5_flags_single_camera_height():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "B", "WORLD", "XWIDE", "LOW"),
        make_shot(3, "A", "ESTABLISHING", "WIDE", "LOW"),
    ]
    assert "C5" in codes(check_sequence(shots))


def test_varied_sheet_passes_all_sequence_checks():
    assert check_sequence(VARIED) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -v
```

Expected: `ImportError: cannot import name 'check_sequence'`.

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/lint_prompt_sheet.py`:

```python
def check_sequence(shots: list[Shot]) -> list[Finding]:
    """C1-C5: adjacency and whole-sheet spread."""
    findings: list[Finding] = []

    for previous, current in zip(shots, shots[1:]):
        if previous.shot_class == current.shot_class:
            findings.append(
                Finding(
                    "C1",
                    current.index,
                    f"shot class {current.shot_class!r} repeats from shot {previous.index}",
                )
            )
        if previous.scale == current.scale:
            findings.append(
                Finding(
                    "C2",
                    current.index,
                    f"scale {current.scale!r} repeats from shot {previous.index}",
                )
            )

    non_plate = [s for s in shots if s.register != "PLATE"]
    run_register: str | None = None
    run_length = 0
    for shot in non_plate:
        run_length = run_length + 1 if shot.register == run_register else 1
        run_register = shot.register
        if run_length > 2:
            findings.append(
                Finding(
                    "C3",
                    shot.index,
                    f"register {shot.register} runs for {run_length} consecutive shots (max 2)",
                )
            )

    scales = {s.scale for s in shots}
    if len(scales) < 3:
        findings.append(
            Finding("C4", None, f"only {len(scales)} distinct scale(s) across the sheet; need >= 3")
        )

    heights = {s.camera_height for s in shots}
    if len(heights) < 2:
        findings.append(
            Finding("C5", None, f"only {len(heights)} camera height(s) across the sheet; need >= 2")
        )

    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -v
```

Expected: 15 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_prompt_sheet.py tests/test_lint_prompt_sheet.py
git commit -m "feat(lint): Gate C sequence checks C1-C5"
```

---

## Task 3: Gate C register balance (C6–C7)

**Files:**
- Modify: `scripts/lint_prompt_sheet.py`
- Modify: `tests/test_lint_prompt_sheet.py`

**Interfaces:**
- Consumes: `Shot`, `Finding`, `make_shot` test helper
- Produces: `check_register_balance(shots: list[Shot]) -> list[Finding]` emitting `C6`, `C7`

C6 ≥3 Register A and ≥2 Register B · C7 the non-PLATE register sequence changes at least twice.

- [ ] **Step 1: Write the failing test**

Add `check_register_balance` to the import list, then append:

```python
def test_c6_flags_too_few_register_b_shots():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "B", "WORLD", "XWIDE", "EYE"),
        make_shot(3, "A", "ESTABLISHING", "WIDE", "HIGH"),
        make_shot(4, "A", "HUMAN-COST", "MID", "LOW"),
    ]
    assert "C6" in codes(check_register_balance(shots))


def test_c6_flags_too_few_register_a_shots():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "B", "WORLD", "XWIDE", "EYE"),
        make_shot(3, "B", "FIGURE", "MID", "HIGH"),
    ]
    assert "C6" in codes(check_register_balance(shots))


def test_c7_flags_bookended_registers():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "A", "ESTABLISHING", "WIDE", "EYE"),
        make_shot(3, "B", "WORLD", "XWIDE", "HIGH"),
        make_shot(4, "B", "FIGURE", "MID", "LOW"),
    ]
    findings = check_register_balance(shots)
    assert "C7" in codes(findings)


def test_c7_passes_when_registers_alternate_twice():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "B", "WORLD", "XWIDE", "EYE"),
        make_shot(3, "A", "ESTABLISHING", "WIDE", "HIGH"),
        make_shot(4, "B", "FIGURE", "MID", "LOW"),
        make_shot(5, "A", "HUMAN-COST", "CLOSE", "LOW"),
    ]
    assert "C7" not in codes(check_register_balance(shots))


def test_varied_sheet_passes_register_balance():
    assert check_register_balance(VARIED) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -v
```

Expected: `ImportError: cannot import name 'check_register_balance'`.

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/lint_prompt_sheet.py`:

```python
MIN_REGISTER_A = 3
MIN_REGISTER_B = 2
MIN_ALTERNATIONS = 2


def check_register_balance(shots: list[Shot]) -> list[Finding]:
    """C6-C7: register quota and intercut rhythm."""
    findings: list[Finding] = []

    count_a = sum(1 for s in shots if s.register == "A")
    count_b = sum(1 for s in shots if s.register == "B")
    if count_a < MIN_REGISTER_A:
        findings.append(
            Finding("C6", None, f"{count_a} Register A shot(s); need >= {MIN_REGISTER_A}")
        )
    if count_b < MIN_REGISTER_B:
        findings.append(
            Finding("C6", None, f"{count_b} Register B shot(s); need >= {MIN_REGISTER_B}")
        )

    sequence = [s.register for s in shots if s.register != "PLATE"]
    alternations = sum(1 for a, b in zip(sequence, sequence[1:]) if a != b)
    if alternations < MIN_ALTERNATIONS:
        findings.append(
            Finding(
                "C7",
                None,
                f"registers alternate {alternations} time(s); need >= {MIN_ALTERNATIONS}. "
                "Bookending the source era at the open and close is not an intercut rhythm.",
            )
        )

    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -v
```

Expected: 20 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_prompt_sheet.py tests/test_lint_prompt_sheet.py
git commit -m "feat(lint): Gate C register balance checks C6-C7"
```

---

## Task 4: Gate C world lock and register vocabulary (C8–C10)

**Files:**
- Modify: `scripts/lint_prompt_sheet.py`
- Modify: `tests/test_lint_prompt_sheet.py`

**Interfaces:**
- Consumes: `Shot`, `Finding`, `signature_objects`, `prompt_body`
- Produces: `check_world_lock(shots: list[Shot], world: dict[str, str]) -> list[Finding]` emitting `C8`, `C9`, `C10`

C8 every Register A body names the locked sport and ≥1 signature object · C9 no Register A body contains a banned generic-venue string · C10 no Register B body contains photographic-optics vocabulary. `PLATE` shots are exempt from all three.

- [ ] **Step 1: Write the failing test**

Add `check_world_lock` to the import list, then append:

```python
WORLD = {
    "register_a_sport": "club soccer",
    "register_a_signature_objects": "goal net, corner flag, painted touchline",
    "register_b_thinker": "Plutarch",
}


def test_c8_flags_register_a_without_the_sport():
    shot = make_shot(1, "A", prompt="a child in a room, near a goal net, No Text. --ar 9:16")
    assert "C8" in codes(check_world_lock([shot], WORLD))


def test_c8_flags_register_a_without_a_signature_object():
    shot = make_shot(1, "A", prompt="a club soccer player standing, in a room, No Text. --ar 9:16")
    assert "C8" in codes(check_world_lock([shot], WORLD))


def test_c8_passes_with_sport_and_signature_object():
    shot = make_shot(
        1, "A", prompt="a club soccer pitch, goal net behind, No Text. --ar 9:16"
    )
    assert "C8" not in codes(check_world_lock([shot], WORLD))


def test_c9_flags_banned_generic_venue():
    shot = make_shot(
        1, "A", prompt="a club soccer bag in an empty gym, goal net behind, No Text. --ar 9:16"
    )
    assert "C9" in codes(check_world_lock([shot], WORLD))


def test_c10_flags_optics_vocabulary_in_register_b():
    shot = make_shot(
        1, "B", prompt="oil painting of a colonnade, 85mm lens, DSLR, No Text. --ar 9:16"
    )
    assert "C10" in codes(check_world_lock([shot], WORLD))


def test_c10_flags_f_stop_in_register_b():
    shot = make_shot(1, "B", prompt="oil painting of a terrace, f/2.8, No Text. --ar 9:16")
    assert "C10" in codes(check_world_lock([shot], WORLD))


def test_c10_passes_for_painterly_register_b():
    shot = make_shot(
        1,
        "B",
        prompt="luminous oil painting on aged linen, a colonnade at dawn, No Text. --ar 9:16",
    )
    assert check_world_lock([shot], WORLD) == []


def test_plate_shots_are_exempt_from_world_lock():
    shot = make_shot(
        1, "PLATE", "PLATE", prompt="a dark gradient plate in an empty gym, No Text. --ar 9:16"
    )
    assert check_world_lock([shot], WORLD) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -v
```

Expected: `ImportError: cannot import name 'check_world_lock'`.

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/lint_prompt_sheet.py`:

```python
BANNED_REGISTER_A_STRINGS = ("empty gym", "empty youth gym")
BANNED_REGISTER_B_STRINGS = ("dslr", "shot on 35mm film", "documentary")
BANNED_REGISTER_B_PATTERNS = (
    re.compile(r"\d+\s*mm"),
    re.compile(r"\bf/\d"),
)


def check_world_lock(shots: list[Shot], world: dict[str, str]) -> list[Finding]:
    """C8-C10: the world lock and the register vocabulary separation."""
    findings: list[Finding] = []
    sport = world.get("register_a_sport", "").strip().lower()
    objects = [o.lower() for o in signature_objects(world)]

    for shot in shots:
        body = prompt_body(shot).lower()

        if shot.register == "A":
            if not sport:
                findings.append(
                    Finding("C8", shot.index, "world lock declares no register_a_sport")
                )
            elif sport not in body:
                findings.append(
                    Finding("C8", shot.index, f"Register A prompt does not name the sport {sport!r}")
                )
            if not any(obj in body for obj in objects):
                findings.append(
                    Finding(
                        "C8",
                        shot.index,
                        "Register A prompt contains none of the signature objects "
                        f"{objects!r}; the sport will not read",
                    )
                )
            for banned in BANNED_REGISTER_A_STRINGS:
                if banned in body:
                    findings.append(
                        Finding(
                            "C9",
                            shot.index,
                            f"banned generic-venue string {banned!r}; name the venue and its "
                            "signature objects instead",
                        )
                    )

        if shot.register == "B":
            for banned in BANNED_REGISTER_B_STRINGS:
                if banned in body:
                    findings.append(
                        Finding(
                            "C10",
                            shot.index,
                            f"photographic vocabulary {banned!r} in Register B collapses the "
                            "two registers into one look",
                        )
                    )
            for pattern in BANNED_REGISTER_B_PATTERNS:
                match = pattern.search(body)
                if match:
                    findings.append(
                        Finding(
                            "C10",
                            shot.index,
                            f"camera optics {match.group(0)!r} in Register B; use painterly "
                            "vocabulary (ground, glaze, brushwork, light quality)",
                        )
                    )

    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -v
```

Expected: 28 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_prompt_sheet.py tests/test_lint_prompt_sheet.py
git commit -m "feat(lint): Gate C world-lock and register-vocabulary checks C8-C10"
```

---

## Task 5: Gate C anti-clone and density (C11–C12)

**Files:**
- Modify: `scripts/lint_prompt_sheet.py`
- Modify: `tests/test_lint_prompt_sheet.py`

**Interfaces:**
- Consumes: `Shot`, `Finding`, `body_clauses`, `body_word_count`
- Produces: `check_prompt_quality(shots: list[Shot]) -> list[Finding]` emitting `C11`, `C12`

C11 no two prompts share 6 or more identical clauses · C12 every body has ≥10 clauses and ≥60 words.

This is the check that catches the original failure: six near-identical rows.

- [ ] **Step 1: Write the failing test**

Add `check_prompt_quality` to the import list, then append:

```python
def build_prompt(unique_head, shared_count=12, filler_word="alpha"):
    """Build a body with `shared_count` shared clauses plus a unique head clause."""
    shared = [f"shared clause {n} {filler_word} beta gamma delta epsilon" for n in range(shared_count)]
    return ", ".join([unique_head, *shared]) + ", No Text. --ar 9:16 --raw --s 95"


def test_c11_flags_two_prompts_sharing_six_clauses():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW", build_prompt("first head")),
        make_shot(2, "A", "HUMAN-COST", "MID", "EYE", build_prompt("second head")),
    ]
    assert "C11" in codes(check_prompt_quality(shots))


def test_c11_passes_when_prompts_are_genuinely_different():
    a = ", ".join(f"alpha clause {n} beta gamma delta epsilon" for n in range(12))
    b = ", ".join(f"zeta clause {n} eta theta iota kappa" for n in range(12))
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW", a + ", No Text. --ar 9:16"),
        make_shot(2, "A", "HUMAN-COST", "MID", "EYE", b + ", No Text. --ar 9:16"),
    ]
    assert "C11" not in codes(check_prompt_quality(shots))


def test_c12_flags_too_few_clauses():
    body = ", ".join(f"clause {n} with several extra words here now" for n in range(4))
    shot = make_shot(1, "A", prompt=body + ", No Text. --ar 9:16")
    assert "C12" in codes(check_prompt_quality([shot]))


def test_c12_flags_too_few_words():
    body = ", ".join(f"c{n}" for n in range(12))
    shot = make_shot(1, "A", prompt=body + ", No Text. --ar 9:16")
    assert "C12" in codes(check_prompt_quality([shot]))


def test_c12_passes_a_dense_prompt():
    body = ", ".join(f"clause {n} with several extra descriptive words here" for n in range(12))
    shot = make_shot(1, "A", prompt=body + ", No Text. --ar 9:16")
    assert "C12" not in codes(check_prompt_quality([shot]))
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -v
```

Expected: `ImportError: cannot import name 'check_prompt_quality'`.

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/lint_prompt_sheet.py`:

```python
MAX_SHARED_CLAUSES = 5
MIN_CLAUSES = 10
MIN_WORDS = 60


def check_prompt_quality(shots: list[Shot]) -> list[Finding]:
    """C11-C12: anti-clone and prompt density."""
    findings: list[Finding] = []

    for left, right in _pairs(shots):
        shared = set(body_clauses(left)) & set(body_clauses(right))
        if len(shared) > MAX_SHARED_CLAUSES:
            findings.append(
                Finding(
                    "C11",
                    right.index,
                    f"shots {left.index} and {right.index} share {len(shared)} identical clauses "
                    f"(max {MAX_SHARED_CLAUSES}). Consistency belongs in --sref, not in a cloned "
                    f"prompt body. Shared: {sorted(shared)[:3]}",
                )
            )

    for shot in shots:
        clause_count = len(body_clauses(shot))
        if clause_count < MIN_CLAUSES:
            findings.append(
                Finding(
                    "C12",
                    shot.index,
                    f"{clause_count} clause(s); need >= {MIN_CLAUSES}. All 9 layers must carry "
                    "concrete renderable content.",
                )
            )
        words = body_word_count(shot)
        if words < MIN_WORDS:
            findings.append(
                Finding("C12", shot.index, f"{words} words in body; need >= {MIN_WORDS}")
            )

    return findings


def _pairs(shots: list[Shot]):
    for i, left in enumerate(shots):
        for right in shots[i + 1 :]:
            yield left, right
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -v
```

Expected: 33 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_prompt_sheet.py tests/test_lint_prompt_sheet.py
git commit -m "feat(lint): Gate C anti-clone and density checks C11-C12"
```

---

## Task 6: Gate C format and parameter bands (C13–C14)

**Files:**
- Modify: `scripts/lint_prompt_sheet.py`
- Modify: `tests/test_lint_prompt_sheet.py`

**Interfaces:**
- Consumes: `Shot`, `Finding`, `prompt_flags`, `prompt_body`
- Produces: `check_format(shots: list[Shot]) -> list[Finding]` emitting `C13`, `C14`

C13 single contiguous line, `No Text.` present and before the flags, flags present, `--ar` present, no punctuation in the flag block · C14 Register A carries `--raw` with `--s` 80–120; Register B carries no `--raw` with `--s` 400–700. `PLATE` is exempt from C14 only.

- [ ] **Step 1: Write the failing test**

Add `check_format` to the import list, then append:

```python
DENSE_A = ", ".join(f"clause {n} with several extra descriptive words here" for n in range(12))


def test_c13_flags_multiline_prompt():
    shot = Shot(1, "Hook", "A", "DETAIL", "MACRO", "LOW",
                DENSE_A + ", No Text. --ar 9:16 --raw --s 95", 2)
    assert "C13" in codes(check_format([shot]))


def test_c13_flags_missing_no_text():
    shot = make_shot(1, "A", prompt=DENSE_A + " --ar 9:16 --raw --s 95")
    assert "C13" in codes(check_format([shot]))


def test_c13_flags_missing_aspect_ratio():
    shot = make_shot(1, "A", prompt=DENSE_A + ", No Text. --raw --s 95")
    assert "C13" in codes(check_format([shot]))


def test_c13_flags_punctuation_in_flag_block():
    shot = make_shot(1, "A", prompt=DENSE_A + ", No Text. --ar 9:16, --raw --s 95")
    assert "C13" in codes(check_format([shot]))


def test_c14_flags_register_a_without_raw():
    shot = make_shot(1, "A", prompt=DENSE_A + ", No Text. --ar 9:16 --s 95")
    assert "C14" in codes(check_format([shot]))


def test_c14_flags_register_a_stylize_out_of_band():
    shot = make_shot(1, "A", prompt=DENSE_A + ", No Text. --ar 9:16 --raw --s 400")
    assert "C14" in codes(check_format([shot]))


def test_c14_flags_register_b_with_raw():
    shot = make_shot(1, "B", "WORLD", "XWIDE", "EYE",
                     DENSE_A + ", No Text. --ar 9:16 --raw --s 520")
    assert "C14" in codes(check_format([shot]))


def test_c14_flags_register_b_stylize_out_of_band():
    shot = make_shot(1, "B", "WORLD", "XWIDE", "EYE",
                     DENSE_A + ", No Text. --ar 9:16 --s 95")
    assert "C14" in codes(check_format([shot]))


def test_c14_passes_correct_bands():
    a = make_shot(1, "A", prompt=DENSE_A + ", No Text. --ar 9:16 --raw --s 95")
    b = make_shot(2, "B", "WORLD", "XWIDE", "EYE",
                  DENSE_A + ", No Text. --ar 9:16 --s 520")
    assert check_format([a, b]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -v
```

Expected: `ImportError: cannot import name 'check_format'`.

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/lint_prompt_sheet.py`:

```python
STYLIZE_RE = re.compile(r"--(?:s|stylize)\s+(\d+)")
REGISTER_BANDS = {"A": (80, 120, True), "B": (400, 700, False)}


def check_format(shots: list[Shot]) -> list[Finding]:
    """C13-C14: copy-paste format and the register parameter bands."""
    findings: list[Finding] = []

    for shot in shots:
        flags = prompt_flags(shot)
        body = prompt_body(shot)

        if shot.prompt_line_count != 1:
            findings.append(
                Finding(
                    "C13",
                    shot.index,
                    f"prompt spans {shot.prompt_line_count} lines; it must be one contiguous "
                    "line so it can be copied in a single action",
                )
            )
        if NO_TEXT_MARKER not in shot.prompt:
            findings.append(Finding("C13", shot.index, f"missing {NO_TEXT_MARKER!r} before the flags"))
        elif not body.endswith(NO_TEXT_MARKER):
            findings.append(
                Finding("C13", shot.index, f"{NO_TEXT_MARKER!r} must be the last thing before the flags")
            )
        if not flags:
            findings.append(Finding("C13", shot.index, "no parameter block"))
            continue
        if "--ar" not in flags:
            findings.append(Finding("C13", shot.index, "no --ar in the parameter block"))
        for punctuation in (",", ";", "."):
            if punctuation in flags:
                findings.append(
                    Finding("C13", shot.index, f"punctuation {punctuation!r} inside the parameter block")
                )

        band = REGISTER_BANDS.get(shot.register)
        if band is None:
            continue
        low, high, needs_raw = band
        has_raw = "--raw" in flags
        if needs_raw and not has_raw:
            findings.append(Finding("C14", shot.index, "Register A requires --raw"))
        if not needs_raw and has_raw:
            findings.append(
                Finding("C14", shot.index, "Register B must not carry --raw; it is not a photograph")
            )
        match = STYLIZE_RE.search(flags)
        if not match:
            findings.append(Finding("C14", shot.index, "no --s in the parameter block"))
        elif not low <= int(match.group(1)) <= high:
            findings.append(
                Finding(
                    "C14",
                    shot.index,
                    f"--s {match.group(1)} outside Register {shot.register}'s band {low}-{high}",
                )
            )

    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -v
```

Expected: 42 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_prompt_sheet.py tests/test_lint_prompt_sheet.py
git commit -m "feat(lint): Gate C format and parameter-band checks C13-C14"
```

---

## Task 7: CLI entry point and regression fixtures

**Files:**
- Modify: `scripts/lint_prompt_sheet.py`
- Modify: `tests/test_lint_prompt_sheet.py`
- Create: `tests/fixtures/failing_sheet.md`
- Create: `tests/fixtures/passing_sheet.md`

**Interfaces:**
- Consumes: every `check_*` function from Tasks 2–6
- Produces:
  - `lint(shots: list[Shot], world: dict[str, str]) -> list[Finding]` — runs all checks in order
  - `main(argv: list[str] | None = None) -> int` — exit 0 clean, exit 1 findings, exit 2 no shots parsed

The failing fixture is distilled from `runs/letkidsplay-20260727-005326/03-visual/artifact.v1.md` and locks in the regression.

- [ ] **Step 1: Write the failing test**

Create `tests/fixtures/failing_sheet.md` — three shots reproducing the original defects (same class, same scale, three-shot Register A run, no sport, banned venue string, cloned bodies, thin prompts, no Register B at all):

```markdown
=== VISUAL PROMPT SHEET — regression fixture (known bad) ===

WORLD LOCK
  register_a_sport: club soccer
  register_a_signature_objects: goal net, corner flag, painted touchline

PER-SHOT PROMPTS

### Shot 1 — Hook (0–3s) · Register A · HUMAN-COST · MID · LOW
Changes vs. previous: opening frame.

```text
documentary sports photography, an eight-year-old child seen from behind, empty youth gym softly out of focus behind, low rear angle, 35mm lens f2.8 shallow depth of field, dim overcast light, muted desaturated palette, DSLR, shot on 35mm film, No Text. --ar 9:16 --raw --s 95
```

### Shot 2 — Build (8–15s) · Register A · HUMAN-COST · MID · LOW
Changes vs. previous: more gear.

```text
documentary sports photography, an eight-year-old child seen from behind, empty youth gym softly out of focus behind, low rear angle, 35mm lens f2.8 shallow depth of field, dim overcast light, muted desaturated palette, DSLR, shot on 35mm film, No Text. --ar 9:16 --raw --s 95
```

### Shot 3 — Payoff (28–38s) · Register A · HUMAN-COST · MID · LOW
Changes vs. previous: even more gear.

```text
documentary sports photography, an eight-year-old child seen from behind, empty youth gym softly out of focus behind, low rear angle, 35mm lens f2.8 shallow depth of field, dim overcast light, muted desaturated palette, DSLR, shot on 35mm film, No Text. --ar 9:16 --raw --s 95
```
```

Create `tests/fixtures/passing_sheet.md` — five shots, all checks satisfied:

```markdown
=== VISUAL PROMPT SHEET — minimal valid sheet ===

WORLD LOCK
  register_a_sport: club soccer
  register_a_venue: municipal club soccer complex
  register_a_signature_objects: goal net, corner flag, painted touchline
  register_b_thinker: Plutarch

PER-SHOT PROMPTS

### Shot 1 — Hook (0–3s) · Register A · DETAIL · MACRO · LOW
Changes vs. previous: opening frame.

```text
documentary sports photography, extreme close-up of a child's small hands pulling a nylon shin-guard strap tight over a club soccer sock, knuckles whitening against the webbing, a scuffed cleat and a mud-flecked ball resting behind on cropped winter turf, a goal net dissolving into unfocused background, low three-quarter angle from knee height, 100mm macro lens at f/2.8, razor-thin focal plane on the buckle, flat blue-grey dawn light from an overcast sky, desaturated palette of turf green and cold slate, fine grain, DSLR, No Text. --ar 9:16 --raw --s 95
```

### Shot 2 — Setup (3–8s) · Register B · WORLD · XWIDE · EYE
Changes vs. previous: register switch to the source era; widest frame so far.

```text
luminous oil painting on aged linen, a first-century Greek colonnade opening onto a sun-bleached terrace at dawn, worn limestone steps and terracotta roof tiles, olive branches shifting at the edge of the portico, a distant terraced hillside falling away beyond the columns, wide frontal view from the level of the stone floor, deep receding perspective through the column line, warm low Mediterranean sun raking in from the left casting long hard shadows, ochre and umber and olive-green palette, cracked varnish and visible brush texture, No Text. --ar 9:16 --s 520
```

### Shot 3 — Build (8–15s) · Register A · ESTABLISHING · WIDE · HIGH
Changes vs. previous: back to the present; the venue reads in full.

```text
documentary sports photography, a full club soccer pitch at dawn seen across the touchline, goal net and corner flag anchoring the far end, painted white lines bright against frost-bitten grass, one small figure alone in the centre circle dwarfed by the empty field, elevated wide view from the top of a spectator bank, 24mm wide lens at f/8, deep focus holding the whole pitch sharp, cold flat overcast light with no shadow, muted green and grey palette under a colourless sky, No Text. --ar 9:16 --raw --s 90
```

### Shot 4 — Build (15–22s) · Register B · ARTIFACT · CLOSE · OVERHEAD
Changes vs. previous: register switch; the motif carried into the source era.

```text
luminous oil painting on aged linen, a terracotta watering vessel tipped over a small clay pot on a sun-warmed stone ledge, water spilling past the rim and darkening the dust in a widening stain, a seedling bent under the weight of the flood, scattered olive leaves and a coarse woven cloth beside the pot, close overhead view looking straight down onto the ledge, compressed flat composition, warm afternoon light pooling from the upper left, ochre and terracotta and deep green palette, thick impasto ridges catching the light, No Text. --ar 9:16 --s 560
```

### Shot 5 — Loop (38–45s) · Register A · ACTION-ADJACENT · MID · EYE
Changes vs. previous: back to the present; the load set down.

```text
documentary sports photography, a child's hands lowering a single kit bag onto the painted touchline of a club soccer pitch, the strap slackening as the weight settles, a corner flag stirring just beyond in the morning air, goal net catching thin early light at the frame edge, eye-level three-quarter view from a crouch, 50mm lens at f/4, moderate depth holding both hands and flag legible, a warm shaft of sun breaking the overcast from behind, palette warming from cold slate toward pale gold, No Text. --ar 9:16 --raw --s 105
```
```

Add `lint` and `main` to the import list in the test file, add `from pathlib import Path` if absent, then append:

```python
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def lint_fixture(name):
    shots, world = parse_sheet((FIXTURES / name).read_text(encoding="utf-8"))
    return shots, lint(shots, world)


def test_passing_fixture_parses_five_shots():
    shots, _ = lint_fixture("passing_sheet.md")
    assert len(shots) == 5


def test_passing_fixture_is_clean():
    _, findings = lint_fixture("passing_sheet.md")
    assert findings == [], [f"{f.check}#{f.shot_index}: {f.message}" for f in findings]


def test_failing_fixture_reproduces_the_original_defects():
    _, findings = lint_fixture("failing_sheet.md")
    found = codes(findings)
    for expected in ["C1", "C2", "C3", "C6", "C7", "C9", "C11", "C12"]:
        assert expected in found, f"{expected} not raised; got {found}"


def test_main_returns_zero_for_a_clean_sheet():
    assert main([str(FIXTURES / "passing_sheet.md")]) == 0


def test_main_returns_one_for_a_failing_sheet():
    assert main([str(FIXTURES / "failing_sheet.md")]) == 1


def test_main_returns_two_when_no_shots_parse(tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("nothing here", encoding="utf-8")
    assert main([str(empty)]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -v
```

Expected: `ImportError: cannot import name 'lint'`.

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/lint_prompt_sheet.py`:

```python
import argparse
import sys
from pathlib import Path


def lint(shots: list[Shot], world: dict[str, str]) -> list[Finding]:
    """Run every Gate C check, in check order."""
    return [
        *check_sequence(shots),
        *check_register_balance(shots),
        *check_world_lock(shots, world),
        *check_prompt_quality(shots),
        *check_format(shots),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lint_prompt_sheet",
        description="Gate C — shot-variety lint for ContentStudio visual prompt sheets.",
    )
    parser.add_argument("sheet", type=Path, help="path to an emitted prompt sheet (.md)")
    args = parser.parse_args(argv)

    shots, world = parse_sheet(args.sheet.read_text(encoding="utf-8"))
    if not shots:
        print(f"Gate C: no shots parsed from {args.sheet}. Check the sheet format.")
        return 2

    findings = lint(shots, world)
    if not findings:
        print(f"Gate C: PASS — {len(shots)} shots, 0 findings.")
        return 0

    print(f"Gate C: FAIL — {len(shots)} shots, {len(findings)} finding(s).")
    for finding in findings:
        where = f"shot {finding.shot_index}" if finding.shot_index else "sheet"
        print(f"  [{finding.check}] {where}: {finding.message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

Move the `import argparse`, `import sys` and `from pathlib import Path` lines up to join the existing imports at the top of the file, keeping them alphabetised.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -v
```

Expected: 48 passed.

Then confirm the CLI works end to end:

```bash
python scripts/lint_prompt_sheet.py tests/fixtures/failing_sheet.md
```

Expected: `Gate C: FAIL — 3 shots, ...` followed by the finding list, exit code 1.

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_prompt_sheet.py tests/test_lint_prompt_sheet.py tests/fixtures/
git commit -m "feat(lint): Gate C CLI entry point and regression fixtures"
```

---

## Task 8: `visual-registers.md` reference

**Files:**
- Create: `.claude/skills/visual-prompts/references/visual-registers.md`

**Interfaces:**
- Consumes: nothing in code; cites `midjourney-prompting/references/prompt-architecture.md` bands
- Produces: the reference `SKILL.md` step 2.5 and step 3 will point at

- [ ] **Step 1: Write the reference file**

Create `.claude/skills/visual-prompts/references/visual-registers.md` containing, in this order:

1. **Header note on grounding.** State plainly: the corpus's §6 visuals theme is thin (27 findings) and says nothing about register systems or shot classes. The register system is this skill's own operational design `[I]`; only the parameter bands and Midjourney mechanics are `[T]`, and the AI-slop/pacing cautions are `[C]`. Do not present the register system as corpus-derived.

2. **Why two registers `[I]`.** A Short that pairs a present-day situation with an external or historical source has two worlds in it. If both are rendered in one visual language, the contrast is inaudible. Register separation makes the "then vs. now" cut legible in half a second, without a caption.

3. **The vocabulary-disjunction rule `[I]`** — the load-bearing mechanism. The registers share no medium, no optics language, no palette family, and no parameter band. Sharing any of these collapses them back into one look. This is enforced by Gate C's C10.

4. **Register A — PRESENT.** Full contract:
   - medium `documentary sports photography` (or the present-day equivalent for a non-sports brand)
   - world lock: one sport per Short, named in every A prompt; ≥1 signature object in frame; banned string `empty gym`
   - parameters `--raw`, `--s 80–120` — the documented photographic band `[T] (verified 2026-07-26)`
   - consistency: one `--sref` code harvested per Short
   - shot classes `ESTABLISHING` / `ACTION-ADJACENT` / `DETAIL` / `HUMAN-COST`, with one sentence each on what the class is for and a worked example line
   - the note that a sheet made entirely of `HUMAN-COST` is the failure mode this system exists to prevent

5. **Register B — SOURCE ERA.** Full contract:
   - medium: one fixed painterly signature, channel-wide, era-varied only in content
   - parameters: no `--raw`, `--s 400–700` — the documented fine-art/illustrative band `[T] (verified 2026-07-26)`
   - consistency: one `--sref` code harvested **once** and stored as a repo-level channel asset, reused every Short; record the resolved code, never a moodboard `mID` `[T] (verified 2026-07-26)`
   - banned vocabulary list, verbatim: `DSLR`, `shot on 35mm film`, `documentary`, any `<n>mm`, any `f/<n>`
   - figure treatment: archetype only — unnamed, face averted or lost in shadow, dressed and posed to the role, never a likeness attempt. Note the consequence `[T]`: because no likeness is being locked, `--oref` is unnecessary, so the Short stays in V8.2 instead of dropping to V7 at 2× GPU cost `[T] (verified 2026-07-26)`.
   - shot classes `FIGURE` / `WORLD` / `ARTIFACT`, one sentence each plus a worked example line

6. **PLATE.** Subject-free background plates are neither register. Generate with `no people, no animals and creatures` so the plate composites cleanly `[C] (Tokenized AI, lCFzMnBDqEc)`. Exempt from the world lock, the register vocabularies and the parameter bands; **not** exempt from density or format.

7. **The motif bridge `[I]`.** If a grounding artifact supplies a motif, render it in **both** registers. A motif that crosses eras welds the two registers into one story instead of two intercut slideshows. Worked example: a watering can as a modern object and as a terracotta vessel on a period terrace.

8. **The world-lock block**, verbatim in the format the linter parses (the twelve `register_a_*` / `register_b_*` / `motif` keys from the spec), with a filled-in RaisingGoodSports example beneath it.

9. **Choosing the sport `[I]`.** This skill picks it and states a one-line rationale tying it to the claim's evidence. Check the script, the concept brief and the grounding artifact first; only pick if none names one. Name the choice at the top of the sheet — an unstated sport lock is indistinguishable from a forgotten one.

- [ ] **Step 2: Verify every normative line carries a marker**

Run:

```bash
grep -nE '^\s*[-*] ' .claude/skills/visual-prompts/references/visual-registers.md | grep -vE '\[C\]|\[I\]|\[T\]' 
```

Expected: no output, or only non-normative descriptive bullets. Any normative line without a marker is a bug — fix it before committing.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/visual-prompts/references/visual-registers.md
git commit -m "docs(visual-prompts): add dual-register visual system reference"
```

---

## Task 9: `visual-arc.md` reference

**Files:**
- Create: `.claude/skills/visual-prompts/references/visual-arc.md`

**Interfaces:**
- Consumes: shot-class/scale/height vocabularies from `visual-registers.md`
- Produces: the arc table shape and the Gate C documentation `SKILL.md` step 3 will point at

- [ ] **Step 1: Write the reference file**

Create `.claude/skills/visual-prompts/references/visual-arc.md` containing:

1. **The failure this prevents `[I]`.** State it concretely, with the evidence: the sheet at `runs/letkidsplay-20260727-005326/03-visual/artifact.v1.md` rendered six of nine stills as the same photograph, varying only the amount of gear, because prompts were written one beat at a time and consistency was achieved by cloning the prompt body. Name the root cause explicitly so nobody reintroduces it.

2. **Arc before prompts `[I]`.** The whole sheet is laid out as a sequence *before* any prompt string exists. Fixing a repetitive arc means editing a table row, not eleven prompt strings, and it happens before any GPU minute is spent.

3. **The arc table shape**, with the exact columns: `# | Beat | Register | Shot class | Scale | Camera height | What changes vs. previous`. State that the last column is mandatory and must name a *visual* change — "more gear" is not a visual change of frame, it is the same frame with a different prop count.

4. **The scale ladder** — `XWIDE`, `WIDE`, `MID-WIDE`, `MID`, `CLOSE`, `MACRO` — with one line each on what it does for a Short, and the rule that ≥3 distinct scales must appear `[I]`.

5. **Camera height** — `LOW`, `EYE`, `HIGH`, `OVERHEAD` — and the ≥2 rule `[I]`.

6. **Optics rotation (Register A only) `[I]`.** A sheet where every prompt says `35mm f2.8` has no visual grammar. Give a starting ladder tied to shot class: `ESTABLISHING` → wide 24mm at deep aperture; `ACTION-ADJACENT` → 50mm at moderate aperture; `HUMAN-COST` → 35mm shallow; `DETAIL` → 100mm macro shallow. Mark clearly that these specific pairings are this skill's judgment, not a corpus finding.

7. **Pacing interaction `[C]`.** Restate that the ~3s cadence rule `[C] (Make Money Matt, HopTPCLbiiM)` sets the *shot count* and this file sets the *shot variety* — they are different problems. Repeat the over-editing caution: cut because the VO content changed, not for its own sake `[C] (Kallaway, i7upRL4H1FM; Nate Black, J8LrrCpDNJI)`.

8. **The Gate C table**, all 14 checks copied verbatim from the spec, each with its check ID, so a reader can map a linter finding straight back to the rule.

9. **How to run Gate C**, verbatim:

   ```bash
   python scripts/lint_prompt_sheet.py <path-to-sheet.md>
   ```

   Exit 0 clean · exit 1 findings · exit 2 nothing parsed (usually a format error — see `prompt-sheet-format.md`). A failing gate **blocks emission**. Never report Gate C as passed without running it.

- [ ] **Step 2: Verify the documented checks match the implementation**

Run:

```bash
grep -oE '\bC1[0-4]\b|\bC[1-9]\b' .claude/skills/visual-prompts/references/visual-arc.md | sort -u
```

Expected: exactly `C1` through `C14`, no more and no fewer. Cross-check each ID appears in `scripts/lint_prompt_sheet.py`:

```bash
grep -oE 'Finding\(\s*"C[0-9]+"' scripts/lint_prompt_sheet.py | grep -oE 'C[0-9]+' | sort -u
```

Expected: the same set.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/visual-prompts/references/visual-arc.md
git commit -m "docs(visual-prompts): add visual-arc discipline and Gate C reference"
```

---

## Task 10: `prompt-sheet-format.md` reference

**Files:**
- Create: `.claude/skills/visual-prompts/references/prompt-sheet-format.md`

**Interfaces:**
- Consumes: the parser contract in `scripts/lint_prompt_sheet.py` (`SHOT_HEADING_RE`, `WORLD_HEADING_RE`, `WORLD_ENTRY_RE`, ` ```text ` fences)
- Produces: the output contract `SKILL.md` step 7 emits

- [ ] **Step 1: Write the reference file**

Create `.claude/skills/visual-prompts/references/prompt-sheet-format.md` containing:

1. **Why the format changed `[I]`.** Two reasons, both concrete. (a) The user must be able to copy one block and paste it straight into Midjourney; the old table put the prompt in one column and the parameters in another, so no prompt was ever copyable in a single action. (b) A machine-parseable sheet is what lets Gate C run against emitted artifacts rather than being a checklist an agent may skip.

2. **The world-lock block**, exact format the parser accepts — heading `WORLD LOCK` at column 0, then two-space-indented `snake_case_key: value` lines, terminated by the first non-matching line. List all twelve keys with a one-line description each. Warn that `register_a_signature_objects` is comma-split and its values are matched case-insensitively as substrings of Register A prompt bodies — so keep them short and literal (`goal net`, not `a regulation goal net with white netting`).

3. **The per-shot block**, exact format:

   ```
   ### Shot <N> — <Beat> (<time range>) · Register <A|B|PLATE> · <SHOT CLASS> · <SCALE> · <CAMERA HEIGHT>
   Changes vs. previous: <one line naming the visual change>

   ```text
   <the entire prompt on ONE line: 9-layer body, then "No Text.", then every flag>
   ```
   ```

   Spell out the separators: the em-dash after `Shot <N>`, the middot `·` between metadata fields, and that all metadata values are uppercase except the beat. Note that a heading the parser cannot match is silently skipped, which is why exit code 2 means "check the format."

4. **The one-line rule `[I]`.** The prompt inside the fence must be a single line. Wrapping it across lines breaks copy-paste, which is the entire point of the block. Gate C's C13 enforces this.

5. **Prompt density `[I]`, with the conflict stated openly.** The prompt body must carry all 9 layers with concrete renderable content — minimum 10 clauses and 60 words, enforced by C12. State the tension in full: `midjourney-prompting/references/prompt-architecture.md` carries **"Short usually beats long"** `[C] (Tokenized AI, vezJXJGQMoY)`. That finding concerns padding and abstract quality claims diluting which words get weighted — not the number of distinct visual attributes specified. Naming a lens, a light direction, a palette and a background separation is denser, not more diluted. **Density, not length** — the buzzword ban and the padding ban both still stand. Label this an `[I]` adaptation. Do not delete the `[C]` line.

6. **A full worked shot block**, copied verbatim from `tests/fixtures/passing_sheet.md` Shot 1, so a reader sees the standard rather than a description of it.

7. **The remaining sheet sections** that sit outside the parser's interest but still travel to `shorts-assembly`: the whole-Short setup (aspect ratio, the two `--sref` codes, phase ladder), the cover/thumbnail decision, the I2V block, the overlay-copy handoff, and the validation line reporting Gate A, Gate B and Gate C results.

8. **The i2v inheritance rule `[I]`.** An i2v prompt inherits its source still's register and must not import the other register's vocabulary — an i2v clip built from a Register B still stays painterly.

- [ ] **Step 2: Verify the documented format actually parses**

Extract the worked shot block from the new file into a scratch sheet and confirm the parser reads it. Run:

```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from pathlib import Path
from lint_prompt_sheet import parse_sheet
shots, world = parse_sheet(Path('tests/fixtures/passing_sheet.md').read_text(encoding='utf-8'))
print(len(shots), 'shots;', len(world), 'world keys')
"
```

Expected: `5 shots; 4 world keys`. If the format documented in the reference differs from what the parser accepts, fix the reference — the parser is the contract.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/visual-prompts/references/prompt-sheet-format.md
git commit -m "docs(visual-prompts): add copy-paste prompt-sheet output contract"
```

---

## Task 11: Rewrite `visual-prompts/SKILL.md`

**Files:**
- Modify: `.claude/skills/visual-prompts/SKILL.md`

**Interfaces:**
- Consumes: `visual-registers.md`, `visual-arc.md`, `prompt-sheet-format.md`
- Produces: the delegation block `midjourney-prompting` consumes in Task 12 — fields `subject`, `stage`, `look`, `format`, `consistency`, `register`, `shot_class`, `literalism`, `variance`, `budget`

- [ ] **Step 1: Make the edits**

Apply these changes to `.claude/skills/visual-prompts/SKILL.md`:

1. **Frontmatter `description`:** add the register system, the sport/world lock and Gate C to the trigger phrases, and the phrase "dual-register visual storytelling." Keep the existing delegation sentence about `midjourney-prompting` intact.

2. **"This skill's job" bullet (around line 16):** add that it locks the Short's two visual registers and its world, and plans the whole sheet as an arc before any prompt is written.

3. **"Why this is grounded, not generic" section:** add a sentence naming the register system, the shot classes and the arc discipline as this skill's own operational design `[I]`, backed by the thin `[C]` §6 pacing theme and the `[T]` parameter bands — explicitly *not* presented as corpus-derived.

4. **Optional-input section:** extend so a companion grounding artifact's thinker/source and motif feed the world lock (step 2.5), not just a single beat's composition.

5. **Insert new step 2.5 "Lock the world"** immediately after step 2, per `references/visual-registers.md`. It emits the twelve-key `WORLD LOCK` block. Include the rule that the sport is chosen here, with a stated rationale, only if nothing upstream names one.

6. **Renumber the existing step 3 (consistency) to step 3a**, and change its table so `style-lock` is the default for both registers with **two** `--sref` codes — one per register, Register B's harvested once and reused channel-wide. Keep the existing `subject-lock`/V7 pushback text verbatim, and add that the archetype-figure treatment in Register B is what makes subject-lock unnecessary.

7. **Insert new step 3b "Build the visual arc"** per `references/visual-arc.md`: emit the arc table, then run Gate C on it before writing any prompt.

8. **Step 4 (delegation):** add `register:` and `shot_class:` to the handoff block. **Delete the "Beat-to-beat coherence" bullet's current wording** and replace it with a pointer to Gate C — the sheet-level question is now mechanical, not a judgment call. Add an explicit prohibition: *do not achieve consistency by repeating a shared style-vocabulary string across prompts; that is what produced six identical stills in the reference failure. Consistency lives in `--sref`.*

9. **Step 7 (emit):** replace the whole output-shape block with a pointer to `references/prompt-sheet-format.md` plus a short skeleton, and add the Gate C run as a mandatory closing step with its command and the rule that a failing gate blocks emission.

10. **Coverage note:** add `visual-registers.md`, `visual-arc.md` and `prompt-sheet-format.md` to the reference list, each with its grounding stated honestly.

- [ ] **Step 2: Verify no stale references remain**

Run:

```bash
grep -niE "shared style vocabulary|beat-to-beat coherence" .claude/skills/visual-prompts/SKILL.md
```

Expected: no output.

Run:

```bash
grep -cE "register|Gate C" .claude/skills/visual-prompts/SKILL.md
```

Expected: a non-zero count.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/visual-prompts/SKILL.md
git commit -m "feat(visual-prompts): arc-first workflow with world lock and Gate C"
```

---

## Task 12: `midjourney-prompting` — register input and density gate

**Files:**
- Modify: `.claude/skills/midjourney-prompting/SKILL.md`
- Modify: `.claude/skills/midjourney-prompting/references/prompt-architecture.md`
- Modify: `.claude/skills/midjourney-prompting/references/validation-gates.md`

**Interfaces:**
- Consumes: the delegation block from Task 11 — including `register: A | B | PLATE` and `shot_class`
- Produces: prompt strings satisfying Gate C's C12, C13 and C14

- [ ] **Step 1: Edit `SKILL.md`**

1. In the control-surface table, add a ninth input:

   | `register` | `A` (present/photographic) · `B` (source-era/painterly) · `PLATE` · `n/a` | `n/a` | Overrides `look`; forces the parameter band |

2. In the deterministic-mappings table, add:

   | `register: A` | `--raw`, `--s 80–120` — same as `look: photographic` |
   | `register: B` | no `--raw`, `--s 400–700` — same as `look: illustrative`; **never** emit `DSLR`, `shot on 35mm film`, `documentary`, a focal length, or an f-stop |

3. In the "Pipeline (ContentStudio Shorts)" section, add `register` and `shot_class` to the list of calls handed down that this skill accepts and does not re-litigate.

4. In Step 1, replace the "Short beats long" bullet with a version that keeps the `[C]` citation and adds the pipeline density rule — see step 2 below for the exact resolution text, and keep the two consistent.

- [ ] **Step 2: Edit `prompt-architecture.md`**

In the "Three rules that govern the stack" section, keep the existing **"Short usually beats long"** paragraph and its `[C] (Tokenized AI, vezJXJGQMoY)` citation exactly as written. Immediately after it, add a subsection titled **"Density, not length — the pipeline exception `[I]`"** stating:

- The `[C]` finding concerns **padding and abstract quality claims** diluting which words get weighted — not the number of distinct visual attributes specified.
- A prompt that names its lens, its light direction, its palette and its background separation is **denser**, not more diluted. A prompt that says `beautiful, striking, cinematic` is padding, and remains banned.
- **In pipeline mode all nine layers are mandatory** with concrete renderable content in each; minimum 10 clauses and 60 words, enforced by Gate C's C12 (`scripts/lint_prompt_sheet.py`).
- Standalone mode is unchanged — the `[C]` default still governs.
- Label the whole subsection `[I]`. State that it does not supersede or delete the `[C]` line, per the skill's own conflict rule.

- [ ] **Step 3: Edit `validation-gates.md`**

In Gate A section A4, keep the existing bullets and add:

```markdown
### A4b. Pipeline density `[I]` — pipeline mode only

- [ ] **All nine layers present** with concrete renderable content — medium, subject, action/state,
      environment, composition/angle, optics *(Register A only)*, lighting, color/atmosphere, parameters
- [ ] Body is **>= 10 comma-separated clauses and >= 60 words** (Gate C's C12)
- [ ] Prompt is a **single contiguous line**, `No Text.` last before the flags (Gate C's C13)
- [ ] `register: A` carries `--raw` with `--s` 80-120; `register: B` carries no `--raw` with
      `--s` 400-700 (Gate C's C14)
- [ ] `register: B` contains **no** `DSLR`, `shot on 35mm film`, `documentary`, focal length or
      f-stop (Gate C's C10)

This section is an `[I]` adaptation for pipeline mode and does **not** apply to standalone jobs,
where "Short usually beats long" `[C] (Tokenized AI, vezJXJGQMoY)` still governs.
```

Also add one line to the gate table in `SKILL.md`'s "Validation gates" section noting that in pipeline mode `visual-prompts` runs a third gate, **Gate C**, over the assembled sheet — this skill does not run it.

- [ ] **Step 4: Verify the conflict is documented, not resolved by deletion**

Run:

```bash
grep -n "vezJXJGQMoY" .claude/skills/midjourney-prompting/references/prompt-architecture.md .claude/skills/midjourney-prompting/references/validation-gates.md .claude/skills/midjourney-prompting/SKILL.md
```

Expected: at least three hits — the original `[C]` line survives in `prompt-architecture.md` and is re-cited in the new A4b block and in `SKILL.md`'s Step 1.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/midjourney-prompting/
git commit -m "feat(midjourney-prompting): register input and pipeline density gate A4b"
```

---

## Task 13: Rewrite `visual-prompts/references/worked-example.md`

**Files:**
- Modify: `.claude/skills/visual-prompts/references/worked-example.md`
- Create: `tests/fixtures/worked_example_sheet.md`
- Modify: `tests/test_lint_prompt_sheet.py`

**Interfaces:**
- Consumes: everything from Tasks 8–12
- Produces: the end-to-end acceptance artifact — the worked example's sheet must pass Gate C

This is the acceptance test for the whole plan. The current file is a second source of the disease: lines 38-40 explicitly teach *"a shared style vocabulary repeated in every prompt"* and every prompt in it is a single thin sentence.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lint_prompt_sheet.py`:

```python
def test_worked_example_sheet_passes_gate_c():
    shots, findings = lint_fixture("worked_example_sheet.md")
    assert len(shots) >= 8, f"worked example has only {len(shots)} shots"
    assert findings == [], [f"{f.check}#{f.shot_index}: {f.message}" for f in findings]


def test_worked_example_uses_all_four_register_a_shot_classes():
    shots, _ = lint_fixture("worked_example_sheet.md")
    classes = {s.shot_class for s in shots if s.register == "A"}
    assert classes == {"ESTABLISHING", "ACTION-ADJACENT", "DETAIL", "HUMAN-COST"}


def test_worked_example_uses_all_three_register_b_shot_classes():
    shots, _ = lint_fixture("worked_example_sheet.md")
    classes = {s.shot_class for s in shots if s.register == "B"}
    assert classes == {"FIGURE", "WORLD", "ARTIFACT"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -k worked_example -v
```

Expected: `FileNotFoundError` — `tests/fixtures/worked_example_sheet.md` does not exist.

- [ ] **Step 3: Write the worked example**

Rewrite `.claude/skills/visual-prompts/references/worked-example.md` end to end, running the reference Short (the `letkidsplay` Plutarch/youth-sports script) through the new workflow. Sections, in order:

1. **Input** — the five-beat script table with durations, VO lines and the `[THINKER: Plutarch]` / `[RESEARCH: ...]` markers.
2. **Step 2 — shot counts** at the ~3s cadence `[C] (Make Money Matt, HopTPCLbiiM)`.
3. **Step 2.5 — the world lock**, filled in: `club soccer` with its stated rationale (the `$5,000/yr` + no-free-weekends + scholarship framing is club-soccer economics), venue, signature objects, and the Plutarch-side era, locations, artifacts and figure archetype. Motif: the watering vessel, in both registers.
4. **Step 3a — consistency**: two `--sref` codes, one per register, and one sentence on why archetype treatment makes `--oref` unnecessary `[T] (verified 2026-07-26)`.
5. **Step 3b — the arc table**, all eleven rows with the `What changes vs. previous` column filled in. Use the arc from the design spec (Hook DETAIL/MACRO → Setup WORLD/XWIDE → Setup ARTIFACT/CLOSE → Build ESTABLISHING/XWIDE → Build HUMAN-COST/MID → Build FIGURE/MID-WIDE → Build ACTION-ADJACENT/MID-LOW → Re-hook PLATE → Payoff DETAIL/MACRO → Payoff HUMAN-COST/WIDE → Loop ARTIFACT/CLOSE), adjusting scales as needed so C1, C2 and C4 pass.
6. **Step 4 — the per-shot blocks**, in the exact format from `prompt-sheet-format.md`, every prompt comprehensive (all 9 layers, ≥10 clauses, ≥60 words) and on a single line with its flags.
7. **Step 5 — the i2v decision**, kept as the watering-vessel overflow, now rendered in Register B and inheriting its painterly vocabulary.
8. **Step 6 — the cover decision.**
9. **Step 7 — Gate A / Gate B / Gate C results**, with the actual Gate C command and its output.

Then copy the world-lock block and all per-shot blocks verbatim into `tests/fixtures/worked_example_sheet.md` so the linter can assert on them.

**Delete** the shared-style-vocabulary passage at the old lines 38-40 and its `Consistency: none ... shared style vocabulary per prompt` example block. Replace with the two-`--sref` setup.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_lint_prompt_sheet.py -v
```

Expected: 51 passed.

Then run Gate C directly on the fixture and confirm a clean pass:

```bash
python scripts/lint_prompt_sheet.py tests/fixtures/worked_example_sheet.md
```

Expected: `Gate C: PASS — 11 shots, 0 findings.`

Confirm the disease is gone:

```bash
grep -niE "shared style vocabulary" .claude/skills/visual-prompts/references/worked-example.md
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/visual-prompts/references/worked-example.md tests/fixtures/worked_example_sheet.md tests/test_lint_prompt_sheet.py
git commit -m "docs(visual-prompts): rewrite worked example as a dual-register sheet passing Gate C"
```

---

## Task 14: Repo wiring — CLAUDE.md and the Cowork plugin build

**Files:**
- Modify: `CLAUDE.md`
- Regenerate: `cowork-plugin/skills/`, `dist/content-studio.plugin`

**Interfaces:**
- Consumes: all prior tasks
- Produces: nothing downstream — this is the closing task

- [ ] **Step 1: Update `CLAUDE.md`**

In the six-skills table, change the `visual-prompts` row's Output cell to read:

`dual-register prompt sheet (present-day photographic + source-era painterly), copy-paste ready, Gate C linted`

Then, in the "Conventions" section, add:

```markdown
- The `visual-prompts` output format is machine-parseable and enforced by
  `scripts/lint_prompt_sheet.py` (Gate C). Run it on any emitted sheet before handing off to
  `shorts-assembly`; a failing gate blocks emission. Tests: `python -m pytest tests/ -v`.
```

- [ ] **Step 2: Run the full test suite**

Run:

```bash
python -m pytest tests/ -v
```

Expected: 51 passed, 0 failed.

- [ ] **Step 3: Rebuild the Cowork plugin**

Run:

```bash
bash scripts/build-cowork-plugin.sh
```

Expected: the script completes and writes `dist/content-studio.plugin`. Confirm the new reference files were carried across:

```bash
ls cowork-plugin/skills/visual-prompts/references/
```

Expected: `faceless-pacing-rules.md`, `image-to-video.md`, `prompt-sheet-format.md`, `visual-arc.md`, `visual-registers.md`, `worked-example.md`.

- [ ] **Step 4: Confirm the regression is locked in**

Run Gate C against the original failing artifact to demonstrate the system catches the real-world failure it was built for:

```bash
python scripts/lint_prompt_sheet.py runs/letkidsplay-20260727-005326/03-visual/artifact.v1.md
```

Expected: exit code 2 (`no shots parsed`) — the old sheet predates the parseable format. This is the correct result and confirms old-format sheets cannot silently pass. The distilled `tests/fixtures/failing_sheet.md` is what locks in the content-level regression, and it must exit 1:

```bash
python scripts/lint_prompt_sheet.py tests/fixtures/failing_sheet.md
```

Expected: exit code 1 with C1, C2, C3, C6, C7, C9, C11 and C12 findings.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md cowork-plugin dist
git commit -m "chore: wire Gate C into repo conventions and rebuild Cowork plugin"
```

---

## Self-Review

**Spec coverage.** Every spec section maps to a task: dual-register contracts → Task 8; arc-first workflow → Tasks 9, 11; Gate C's 14 checks → Tasks 2–7; prompt density and the `[C]` conflict resolution → Tasks 10, 12; copy-paste output format → Tasks 6, 10; world/sport lock → Tasks 4, 8; motif bridge → Tasks 8, 13; PLATE exemptions → Tasks 4, 6, 8; regression fixture → Tasks 7, 14; non-goals respected (no new skill, no `shorts-assembly` change, no re-run of the reference Short).

**Placeholder scan.** No `TBD`/`TODO`. Every code step carries complete runnable code. Tasks 8–11 and 13 are markdown-authoring tasks, so their steps specify exact section content and ordering plus a mechanical verification command rather than a code block — the content is enumerated, not deferred.

**Type consistency.** `Shot` and `Finding` field names are identical across Tasks 1–7 and the tests. Every `check_*` function takes `list[Shot]` and returns `list[Finding]`; only `check_world_lock` also takes `world: dict[str, str]`, consistently in its definition, its call in `lint()`, and its tests. Check IDs `C1`–`C14` match between the spec, `visual-arc.md` (Task 9), Gate A4b (Task 12) and the implementation. The `make_shot` / `codes` / `lint_fixture` test helpers are defined once (Tasks 2 and 7) and reused thereafter. Cumulative test counts run 8 → 15 → 20 → 28 → 33 → 42 → 48 → 51.
