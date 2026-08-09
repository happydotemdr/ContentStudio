# P11 — Gate C: make the deterministic gate fail closed

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`)
> syntax for tracking. The parent plan's **Global Constraints**, **test standard** and
> **Frozen interfaces** sections (`docs/superpowers/plans/2026-08-08-audit-remediation.md`)
> are binding and are not repeated here.

**The one-sentence problem.** Gate C is one of only two deterministic quality controls in the
system, and it is **fail-open at the parse layer**: a line that looks like a shot heading but
does not match `SHOT_HEADING_RE` is skipped, the shot vanishes from the `shots` list, and every
one of C1–C20 iterates that list — so a one-character typo deletes a shot from all twenty checks
and the gate prints `PASS — 10 shots, 0 findings`.

**The two structural fixes, in order.** Everything else in this package is hardening; these two
are the package.

1. **Fail-closed parsing** (T2, T4, T5, T10) — any line that *looks like* a structural token but
   does not fully match produces a blocking `PARSE` finding. `parse_sheet` returns its rejects
   alongside its shots.
2. **A reconciliation invariant** (T3) — parsed shot indices must be exactly `1..N`, and must
   equal the sheet's declared count when one is written. This lives in `lint()`, which **both**
   callers already invoke, so it closes C-70 on the app path with zero changes to
   `pipeline_app/gates.py`.

---

## 1. Scope

**Files this package owns. No other package may touch these.**

```
scripts/lint_prompt_sheet.py        (~1040 lines, checks C1–C20)
tests/test_lint_prompt_sheet.py     (118 tests)
docs/style-library.md
```

**Files this package reads but must never edit:**

- `pipeline-app/pipeline_app/gates.py` — package **P3**. §6 states the parity contract as a
  requirement *on P3*.
- `pipeline-app/pipeline_app/templates/stage.html` — package **P15**.
- `.claude/skills/shorts-styleboard/references/visual-registers.md` — package **P13**. T18
  widens a banned-vocabulary list that this file is the `[I]`-marked source for; §6 carries the
  mirror note P13 must action.
- `tests/fixtures/*.md` — **not owned by this package**. Every mutation test in T6 builds its
  input by reading a fixture and rewriting it into `tmp_path`. **No task in this plan edits a
  fixture file on disk.** All fixture shot indices are already contiguous `1..N`
  (passing 1–5, failing 1–3, worked_example 1–11, legacy_do_less 1–2), so T3's invariant does
  not break a green fixture.

**Finding IDs (28):**
A-34, A-43, C-49, C-50, C-51, C-70, C-71, C-72, C-73, C-74, C-75, C-76, C-77, C-78, C-79, C-80,
C-81, C-82, C-83, C-84, C-85, C-86, C-87, C-93, C-94, C-95, F-13, F-14

---

## 2. Finding → task map

Total coverage: 28 of 28.

| Finding | Sev | Failure mode | Task | What the task does |
|---|---|---|---|---|
| C-93 | S3 | latent | **T1** | `Finding` gains `kind="fail"` and a derived `beat` location field |
| A-43 | S3 | silent | **T1** | the derived `beat` is what `stage.html` already renders |
| C-70 | **S1** | silent | **T2** | loose heading match → blocking `PARSE` finding; `parse_sheet` returns rejects |
| C-71 | S2 | silent | **T3** | C21 reconciliation: indices are exactly `1..N`, and equal a declared count |
| C-72 | S3 | silent | **T4** | `parse_sheet`'s main loop tracks fence state |
| C-73 | S3 | silent | **T5** | world-lock walk consumes the whole block; duplicate block rejected |
| C-94 | S2 | silent | **T7** | `OSError` on any read → exit 3, named path, no traceback |
| C-95 | S3 | latent | **T7** | exit-code table: 0/1/2/3/4/5, documented in the module docstring |
| C-74 | S2 | loud | **T8** | CLI gains the empty-world fail-closed guard `gates.py` has |
| C-75 | **S1** | silent | **T9** | resolved Library path printed on every run; default pinned to the app's path |
| C-76 | S2 | silent | **T10** | `parse_style_library` reports bad `### ` headings and an unterminated fence |
| C-77 | S3 | docs-drift | **T11** | machine-coupling warning above `## Entries` and in `## Entry format` |
| C-49 | S4 | docs-drift | **T12** | the two ad-hoc decision markers become `[P]`; marker legend added |
| C-50 | S4 | latent | **T12** | `rgs-present-soccer-a` gains the `seed:` field its own format declares |
| C-51 | S4 | docs-drift | **T12** | the two `[T]` lines get their verification date |
| C-81 | **S1** | silent | **T13** | C13 parses the `--ar` value and requires `9:16` |
| F-13 | **S1** | silent | **T13** | the three defect-affirming tests inverted (also T14, T15) |
| C-79 | **S1** | silent | **T14** | C17 accepts only a `{style:…}` slot — C20 becomes the single resolution path |
| C-80 | **S1** | silent | **T15** | a valueless `--p` is legitimate syntax but not a recorded lock |
| C-82 | S2 | silent | **T16** | C11 compares clauses by token-set overlap, not byte equality |
| C-83 | S2 | silent | **T17** | C12 gains a layer-marker structural check; docstring stops overclaiming |
| C-84 | S2 | coverage-gap | **T18** | C9/C10 no-lists widened and scanned over the whole prompt |
| C-85 | S2 | silent | **T19** | C22 caps PLATE shots; PLATE gains a `--s` band |
| C-78 | S2 | silent | **T20** | "cover present but unreadable" ≠ "no cover"; cover heading breaks the fence read |
| C-86 | S3 | coverage-gap | **T20** | `Cover = Hook` must name a shot that exists, and that shot is linted |
| C-87 | S3 | coverage-gap | **T21** | C8 matches the sport at word boundaries and requires ≥2 signature objects |
| A-34 | S2 | latent | **T22** | C20's message names the styleboard as the file to edit |
| F-14 | **S1** | coverage-gap | **T6** | the parse-layer mutation test class (22 cases) |

---

## 3. Tasks

Each task is one TDD cycle: **write the failing test → run it → see it fail for the right reason
→ implement → see it pass → commit.** Run the root suite from the repo root:

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767" && python -m pytest tests/test_lint_prompt_sheet.py -q
```

---

### T1 — `Finding` gets a contract: `kind` and a location field (C-93, A-43)

Gate D's `Finding` is `(check, beat, message, kind)`; Gate C's is `(check, shot_index, message)`.
`gates.py` blocks on `f.get("kind") != "skipped"`, which is correct for Gate C only because a
missing key yields `None` — correct **by accident**. `stage.html` renders `finding.beat`, which
Gate C findings do not have, so every Gate C finding shows up in the app with no shot number.

Both are fixed by adding the two fields, with `beat` **derived** so all ~60 existing
construction sites keep working unchanged.

- [ ] **Write the failing test** in `tests/test_lint_prompt_sheet.py` (new section, top of file
      after the imports):

```python
from dataclasses import asdict


def test_finding_defaults_to_a_blocking_kind():
    """gates.py blocks on `kind != "skipped"`. Gate C must never emit "skipped":
    the blocking rule has to be contractual, not an accident of a missing key."""
    finding = Finding("C1", 3, "shot class repeats")
    assert finding.kind == "fail"
    assert asdict(finding)["kind"] == "fail"


def test_finding_carries_a_beat_the_stage_template_can_render():
    """stage.html renders finding.beat. A Gate C finding without one displays as
    '[C18]: <message>' with no shot number, while the CLI prints 'shot 7:'."""
    assert asdict(Finding("C1", 7, "m"))["beat"] == "shot 7"
    assert asdict(Finding("C19", None, "m"))["beat"] == "sheet"
    assert asdict(Finding("C16", 0, "m"))["beat"] == "cover"


def test_no_gate_c_check_can_emit_a_skipped_kind():
    """Distinguishability: Gate C has no known-unknown concept. If one is ever added,
    gates.py's blocking rule silently stops blocking it — so assert it cannot exist."""
    shots, world = parse_sheet(SHEET.replace("--s 95", "--s 9500"))
    assert {f.kind for f in lint(shots, world)} <= {"fail", "parse"}
```

- [ ] **Run it.** `AttributeError: 'Finding' object has no attribute 'kind'`.
- [ ] **Implement** in `scripts/lint_prompt_sheet.py`, replacing the `Finding` dataclass:

```python
def location_label(shot_index: int | None) -> str:
    """The human name for a finding's position — the single source of truth for
    both the CLI's printed prefix and the `beat` field the app template renders."""
    if shot_index is None:
        return "sheet"
    if shot_index == 0:
        return "cover"
    return f"shot {shot_index}"


@dataclass(frozen=True)
class Finding:
    """One Gate C finding.

    `kind` exists so `pipeline_app.gates.run_gates_for_stage`'s blocking rule
    (`f.get("kind") != "skipped"`) is contractual rather than accidental. Gate C
    emits only "fail" and "parse", both blocking; it has no known-unknown concept
    and must not grow one without changing that rule first.

    `beat` is derived from `shot_index` at construction, not passed in, so every
    existing `Finding(check, index, message)` call site is unchanged. It exists
    because templates/stage.html renders `finding.beat` and Gate D's record has
    one — without it every Gate C finding rendered in the app with no location.
    """

    check: str
    shot_index: int | None
    message: str
    kind: str = "fail"
    beat: str | None = None

    def __post_init__(self) -> None:
        if self.beat is None:
            object.__setattr__(self, "beat", location_label(self.shot_index))
```

- [ ] Replace `main()`'s inline `where = ...` ladder (`:1029-1034`) with `location_label`:

```python
    for finding in findings:
        print(f"  [{finding.check}] {finding.beat}: {finding.message}")
```

- [ ] **Run.** Green, including `test_main_labels_a_cover_finding_as_cover_not_shot_0_or_sheet`.
- [ ] Commit: `fix(gate-c): give Finding a blocking kind and a renderable location`

---

### T2 — Fail-closed parsing: a near-miss heading is a blocking finding (C-70) **[flagship]**

- [ ] **Write the failing test:**

```python
WORKED = FIXTURES / "worked_example_sheet.md"


def test_a_broken_shot_heading_produces_a_blocking_parse_finding():
    """C-70, the flagship. Breaking Shot 4's em-dash to a hyphen made the shot
    invisible to all of C1-C20 and Gate C printed PASS."""
    text = WORKED.read_text(encoding="utf-8").replace(
        "### Shot 4 — Build", "### Shot 4 - Build", 1
    )
    parse = parse_sheet(text)
    assert [f.check for f in parse.findings] == ["PARSE"]
    assert "Shot 4" in parse.findings[0].message
    assert parse.findings[0].kind == "parse"


def test_a_broken_heading_is_distinguishable_from_a_sheet_that_has_that_shot():
    """Distinguishability: the broken sheet must not present as the good sheet
    minus one shot -- it must present as a sheet that failed to parse."""
    good = WORKED.read_text(encoding="utf-8")
    broken = good.replace("### Shot 4 — Build", "### Shot 4 - Build", 1)
    assert parse_sheet(good).findings == []
    assert parse_sheet(broken).findings != []


def test_parse_sheet_still_unpacks_as_the_two_tuple_every_caller_expects():
    """pipeline_app/gates.py does `shots, sheet_world = linter.parse_sheet(text)`.
    That call site belongs to P3 and must keep working untouched."""
    shots, world = parse_sheet(SHEET)
    assert len(shots) == 2
    assert world["register_a_sport"] == "club soccer"
```

- [ ] **Run it.** `AttributeError: 'tuple' object has no attribute 'findings'`.
- [ ] **Implement.** Add near the other patterns:

```python
# Deliberately loose: anything an author could plausibly have meant as a shot
# heading. A line matching this but NOT SHOT_HEADING_RE is a hard finding, never
# a skipped line -- skipping it removed the shot from all of C1-C20 and Gate C
# printed PASS (finding C-70).
LOOSE_SHOT_HEADING_RE = re.compile(r"^\s*#{2,4}\s*Shot\b", re.IGNORECASE)
LOOSE_COVER_HEADING_RE = re.compile(r"^\s*#{2,4}\s*Cover\b", re.IGNORECASE)
SHOT_COUNT_RE = re.compile(r"^\s*SHOT COUNT:\s*(\d+)\s*$", re.IGNORECASE)


class SheetParse(tuple):
    """(shots, world), plus the parse layer's own findings.

    A tuple subclass rather than a dataclass so `shots, world = parse_sheet(text)`
    keeps working verbatim in pipeline_app/gates.py (package P3) and in the 11
    existing tests. `.findings` is the new fail-closed channel; `main()` consumes
    it today and gates.py adopts it per this plan's P3 contract.
    """

    def __new__(cls, shots, world, findings, declared_shot_count):
        obj = super().__new__(cls, (shots, world))
        obj.findings = findings
        obj.declared_shot_count = declared_shot_count
        return obj

    @property
    def shots(self) -> list["Shot"]:
        return self[0]

    @property
    def world(self) -> dict[str, str]:
        return self[1]
```

- [ ] Rewrite `parse_sheet`'s main loop so a loose match that fails the strict pattern is
      recorded instead of skipped:

```python
def parse_sheet(text: str) -> SheetParse:
    """Return (shots in sheet order, world-lock key/value pairs).

    Fail-closed: a line that looks like a shot or cover heading but does not fully
    match its strict pattern is reported as a PARSE finding rather than skipped.
    The old behaviour deleted the shot from every check C1-C20 (finding C-70).
    """
    lines = text.splitlines()
    shots: list[Shot] = []
    world: dict[str, str] = {}
    findings: list[Finding] = []
    declared: int | None = None

    i = 0
    while i < len(lines):
        line = lines[i]

        count = SHOT_COUNT_RE.match(line)
        if count:
            declared = int(count.group(1))
            i += 1
            continue

        heading = SHOT_HEADING_RE.match(line)
        if heading:
            prompt_lines, next_i = _read_fenced_prompt(lines, i + 1)
            shots.append(Shot(
                index=int(heading.group(1)),
                beat=heading.group(2),
                register=heading.group(3),
                shot_class=heading.group(4),
                scale=heading.group(5),
                camera_height=heading.group(6),
                prompt=" ".join(prompt_lines).strip(),
                prompt_line_count=len(prompt_lines),
            ))
            i = next_i
            continue

        if LOOSE_SHOT_HEADING_RE.match(line) or (
            LOOSE_COVER_HEADING_RE.match(line) and not COVER_HEADING_RE.match(line)
        ):
            findings.append(Finding(
                "PARSE", None,
                f"line {i + 1} looks like a shot/cover heading but does not match the "
                f"required format, so it would be skipped and its shot linted by "
                f"nothing: {line.strip()!r}. Required: "
                f"'### Shot <n> — <beat> · Register <A|B|PLATE> · <CLASS> · <SCALE> "
                f"· <HEIGHT>' with em-dash and middle-dot separators and uppercase "
                f"vocabulary tokens.",
                kind="parse",
            ))
            i += 1
            continue

        i += 1

    return SheetParse(shots, world, findings, declared)
```

> The world-lock branch is deliberately absent here — T5 replaces it with `_read_world_block`
> and reinstates it at the top of this loop. Implement T2 with the existing world-lock branch
> left in place, then T5 swaps it.

- [ ] `parse_world_lock` keeps working unchanged (`_shots, world = parse_sheet(text)`).
- [ ] **Run.** Green.
- [ ] Commit: `fix(gate-c): reject a near-miss shot heading instead of deleting the shot`

---

### T3 — The reconciliation invariant, C21 (C-71) **[the invariant that makes C-70 unrepeatable]**

`Shot.index` is parsed from every heading and used only in finding messages. This is the check
that makes a silently-dropped shot impossible **regardless of cause** — and because it reads
only the `shots` list, it runs on the app path today with no `gates.py` change.

- [ ] **Write the failing test:**

```python
def test_c21_flags_a_gap_in_the_shot_indices():
    """A shot lost to a bad heading leaves indices 1,2,3,5,... The gate must say so
    rather than report 'PASS - 10 shots'."""
    shots = [make_shot(1), make_shot(2), make_shot(3), make_shot(5)]
    findings = check_shot_count(shots)
    assert [f.check for f in findings] == ["C21"]
    assert "4" in findings[0].message


def test_c21_flags_a_duplicated_shot_index():
    assert "C21" in codes(check_shot_count([make_shot(1), make_shot(2), make_shot(2)]))


def test_c21_flags_a_declared_count_that_disagrees_with_the_parse():
    findings = check_shot_count([make_shot(1), make_shot(2)], declared=3)
    assert "C21" in codes(findings)
    assert "declares 3" in findings[0].message


def test_c21_runs_inside_lint_so_both_gate_c_callers_get_it():
    """gates.py calls lint() but not parse_sheet().findings. Putting the invariant
    in lint() is what closes C-70 on the app path with no change to gates.py."""
    shots = [make_shot(1, "A"), make_shot(2, "B", "WORLD", "XWIDE", "EYE"),
             make_shot(4, "A", "ESTABLISHING", "WIDE", "HIGH")]
    assert "C21" in codes(lint(shots, {}))


def test_c21_is_silent_on_every_green_fixture():
    """Distinguishability: the invariant must separate a dropped shot from a
    legitimately short sheet, not fire on both."""
    for name in ("passing_sheet.md", "failing_sheet.md", "worked_example_sheet.md"):
        shots, _ = parse_sheet((FIXTURES / name).read_text(encoding="utf-8"))
        assert check_shot_count(shots) == [], name
```

- [ ] **Run it.** `NameError: name 'check_shot_count' is not defined` (add it to the import list
      at `tests/test_lint_prompt_sheet.py:8-37`).
- [ ] **Implement:**

```python
def check_shot_count(shots: list[Shot], declared: int | None = None) -> list[Finding]:
    """C21: parsed shots reconcile against what the sheet says it contains.

    This is the invariant that makes C-70 unrepeatable. Every other check iterates
    `shots`, so a shot that never parsed is a shot no check can fail. Indices are
    the sheet's own declaration of how many shots it has: if they do not form a
    contiguous 1..N run, one was dropped, duplicated or misnumbered, and the gate
    says so instead of reporting a clean pass over the survivors.
    """
    findings: list[Finding] = []
    if not shots:
        return findings

    indices = [s.index for s in shots]
    expected = list(range(1, len(shots) + 1))
    if indices != expected:
        missing = sorted(set(expected) - set(indices))
        duplicated = sorted({i for i in indices if indices.count(i) > 1})
        detail = []
        if missing:
            detail.append(f"missing {missing}")
        if duplicated:
            detail.append(f"duplicated {duplicated}")
        findings.append(Finding(
            "C21", None,
            f"parsed {len(shots)} shot(s) with indices {indices}, which is not a "
            f"contiguous 1..{len(shots)} run"
            + (f" ({'; '.join(detail)})" if detail else "")
            + ". A shot heading was dropped, duplicated or misnumbered -- every "
            "check C1-C20 iterates the parsed shots, so a shot that did not parse "
            "is a shot nothing linted.",
        ))

    if declared is not None and declared != len(shots):
        findings.append(Finding(
            "C21", None,
            f"the sheet declares {declared} shot(s) but {len(shots)} parsed.",
        ))
    return findings
```

- [ ] Wire it into `lint()` and let `main()` pass the declared count through:

```python
def lint(
    shots: list[Shot],
    world: dict[str, str],
    *,
    cover: Shot | None = None,
    library: dict[str, str] | None = None,
    declared_shot_count: int | None = None,
) -> list[Finding]:
    """Run every Gate C check, in check order."""
    findings = [
        *check_shot_count(shots, declared_shot_count),
        *check_sequence(shots),
        # ... unchanged ...
    ]
```

- [ ] **Run.** Green.
- [ ] Commit: `feat(gate-c): C21 -- reconcile parsed shots against the sheet's own indices`

---

### T4 — `parse_sheet` becomes fence-aware (C-72)

- [ ] **Write the failing test:**

```python
FENCED_EXAMPLE = SHEET + """
Format reminder for authors:

```text
### Shot 99 — Demo · Register A · DETAIL · MACRO · LOW
```
"""


def test_a_heading_inside_a_fence_is_not_a_real_shot():
    shots, _ = parse_sheet(FENCED_EXAMPLE)
    assert [s.index for s in shots] == [1, 2]


def test_a_fenced_heading_produces_no_parse_finding_either():
    """Distinguishability: documented-example (ignore) must not be conflated with
    malformed-heading (report). declares_cover_reuse was already fence-aware for
    exactly this reason; the shot walk was not."""
    assert parse_sheet(FENCED_EXAMPLE).findings == []


def test_a_fenced_example_does_not_pollute_the_sequence_checks():
    shots, world = parse_sheet(FENCED_EXAMPLE)
    assert "C21" not in codes(lint(shots, world))
```

- [ ] **Run it.** `assert [1, 2, 99] == [1, 2]`.
- [ ] **Implement.** At the top of `parse_sheet`'s `while` body, before any other branch:

```python
        if OPEN_FENCE_RE.match(line):
            in_fence = True
            i += 1
            continue
        if in_fence:
            if CLOSE_FENCE_RE.match(line):
                in_fence = False
            i += 1
            continue
```

with `in_fence = False` initialised beside `declared`. (`_read_fenced_prompt` already consumes a
shot's own fence and returns the index after it, so this branch only sees fences the shot walk
did not open — which is precisely the documented-example case.)

- [ ] **Run.** Green.
- [ ] Commit: `fix(gate-c): ignore shot headings inside a fenced example block`

---

### T5 — The world-lock walk stops guessing (C-73)

- [ ] **Write the failing test:**

```python
SPLIT_WORLD = """\
WORLD LOCK
  register_a_sport: club soccer
  register_a_signature_objects: goal net, corner flag

  slot_register_a: rgs-present-soccer-a
"""


def test_a_blank_line_does_not_truncate_the_world_lock_block():
    parse = parse_sheet(SPLIT_WORLD)
    assert parse.world["slot_register_a"] == "rgs-present-soccer-a"


def test_a_malformed_world_lock_entry_is_reported_not_skipped():
    parse = parse_sheet("WORLD LOCK\n  register_a_sport: club soccer\n  not an entry\n")
    assert [f.check for f in parse.findings] == ["PARSE"]
    assert "not an entry" in parse.findings[0].message


def test_a_second_world_lock_block_is_rejected_rather_than_last_win():
    """A superseded block left above the live one silently overwrote it."""
    text = SPLIT_WORLD + "\nWORLD LOCK\n  register_a_sport: hockey\n"
    parse = parse_sheet(text)
    assert any("second 'WORLD LOCK'" in f.message for f in parse.findings)


def test_an_unindented_world_lock_body_is_reported_not_silently_empty():
    """Distinguishability: 'the styleboard has no world lock' and 'the styleboard's
    world lock is unindented' must not both render as {}."""
    flat = parse_sheet("WORLD LOCK\nregister_a_sport: club soccer\n")
    absent = parse_sheet("nothing here\n")
    assert flat.world == {} and absent.world == {}
    assert flat.findings != absent.findings
```

- [ ] **Run it.** `KeyError: 'slot_register_a'`.
- [ ] **Implement** `_read_world_block`, and replace `parse_sheet`'s world branch with a call to
      it:

```python
def _read_world_block(
    lines: list[str], start: int
) -> tuple[dict[str, str], list[Finding], int]:
    """Consume a WORLD LOCK block to the next unindented non-blank line.

    The old walk broke at the first line that failed WORLD_ENTRY_RE, so a blank
    line mid-block silently truncated it and an unindented body yielded {} --
    which then surfaced downstream as a wall of C8/C18 findings blaming the sheet
    for a styleboard formatting problem (finding C-73).
    """
    entries: dict[str, str] = {}
    findings: list[Finding] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if not line[:1].isspace():
            break
        entry = WORLD_ENTRY_RE.match(line)
        if entry:
            entries[entry.group(1)] = entry.group(2)
        else:
            findings.append(Finding(
                "PARSE", None,
                f"line {i + 1} sits inside the WORLD LOCK block but is not a "
                f"'<key>: <value>' entry, so it would be dropped: {line.strip()!r}",
                kind="parse",
            ))
        i += 1
    if not entries:
        findings.append(Finding(
            "PARSE", None,
            "a WORLD LOCK heading is present but no indented '<key>: <value>' "
            "entries followed it; the world lock resolves to nothing.",
            kind="parse",
        ))
    return entries, findings, i
```

and in `parse_sheet`:

```python
        if WORLD_HEADING_RE.match(line):
            if seen_world_block:
                findings.append(Finding(
                    "PARSE", None,
                    f"line {i + 1} opens a second 'WORLD LOCK' block; the later one "
                    "silently overwrote the earlier. Delete the superseded block.",
                    kind="parse",
                ))
            seen_world_block = True
            entries, block_findings, i = _read_world_block(lines, i + 1)
            world.update(entries)
            findings.extend(block_findings)
            continue
```

- [ ] **Run.** Green.
- [ ] Commit: `fix(gate-c): consume the whole WORLD LOCK block and report its rejects`

---

### T6 — The mutation test class (F-14) **[the test class that was missing]**

~90 of the 118 existing tests build `Shot` objects through `make_shot()`/`_shot()`, starting
*downstream* of the text→`Shot` transition where C-70 lives. `parse_sheet`'s 98% coverage comes
from 11 calls against sheets that always parse. This task adds the class that mutates a
known-good sheet one edit at a time and asserts the gate **fails every time**.

- [ ] **Write the failing test.** Add a new section at the end of the file:

```python
# --- Mutation testing: take a green sheet, break one thing, assert Gate C fails --
#
# F-14: the suite bypassed the parser, so the largest hole in the gate was
# structurally unreachable by any existing test. Each case below is an evasion the
# audit confirmed by execution against these same fixtures. `expected` is the check
# that must fire; `""` means "any finding at all, but never a pass".

MUTATIONS = [
    # id,                       find,                        replace,                     expected
    ("heading-hyphen",          "### Shot 4 — Build",        "### Shot 4 - Build",        "PARSE"),
    ("heading-endash",          "### Shot 4 — Build",        "### Shot 4 – Build",        "PARSE"),
    ("heading-no-middot",       "· Register B · ARTIFACT",   "- Register B · ARTIFACT",   "PARSE"),
    ("heading-lowercase-scale", "· ARTIFACT · CLOSE ·",      "· ARTIFACT · Close ·",      "PARSE"),
    ("heading-underscore-scale","· WORLD · MID-WIDE ·",      "· WORLD · MID_WIDE ·",      "PARSE"),
    ("heading-lowercase-reg",   "· Register B · WORLD",      "· register B · WORLD",      "PARSE"),
    ("heading-two-hashes",      "### Shot 7 —",              "## Shot 7 —",               "PARSE"),
    ("heading-deleted",         "### Shot 4 — Build",        "Shot 4 — Build",            "C21"),
    ("index-duplicated",        "### Shot 5 —",              "### Shot 4 —",              "C21"),
    ("index-renumbered",        "### Shot 11 —",             "### Shot 12 —",             "C21"),
    ("declared-count-mismatch", "PER-SHOT PROMPTS",          "SHOT COUNT: 12\n\nPER-SHOT PROMPTS", "C21"),
    ("sref-invented-number",    "{style:register_a}",        "--sref 11111111",           "C17"),
    ("sref-bare-p",             "{style:register_a}",        "--p",                       "C17"),
    ("ar-landscape",            "--ar 9:16",                 "--ar 16:9",                 "C13"),
    ("plate-relabel",           "· Register B · WORLD ·",    "· Register PLATE · PLATE ·","C15"),
    ("venue-synonym",           "a municipal club soccer",   "a vacant gym, a municipal club soccer", "C9"),
    ("registerb-photographic",  "luminous oil painting",     "photorealistic bokeh render", "C10"),
    ("fenced-heading",          "PER-SHOT PROMPTS",          "PER-SHOT PROMPTS\n\n```text\n### Shot 99 — X · Register A · DETAIL · MACRO · LOW\n```", ""),
    ("world-blank-line",        "  register_b_thinker:",     "\n  register_b_thinker:",   ""),
    ("world-second-block",      "PER-SHOT PROMPTS",          "WORLD LOCK\n  register_a_sport: hockey\n\nPER-SHOT PROMPTS", "PARSE"),
    ("cover-fence-markdown",    "```text",                   "```markdown",               ""),
    ("sport-compound-only",     "club soccer boot",          "clubsoccerboot",            "C8"),
]


@pytest.mark.parametrize("case", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_a_single_mutation_of_a_green_sheet_always_fails_gate_c(case, tmp_path, capsys):
    """The gate is fail-closed or it is not a gate. Each of these was confirmed by
    execution to pass the pre-remediation gate."""
    _id, find, replace, expected = case
    original = WORKED.read_text(encoding="utf-8")
    assert find in original, f"{_id}: mutation anchor no longer present in the fixture"
    sheet = tmp_path / "mutated.md"
    sheet.write_text(original.replace(find, replace, 1), encoding="utf-8")

    code = main([str(sheet), "--styleboard", str(FIXTURES / "worked_example_styleboard.md")])
    out = capsys.readouterr().out

    assert code != 0, f"{_id}: Gate C passed a mutated sheet\n{out}"
    assert "PASS" not in out, f"{_id}: {out}"
    if expected:
        assert f"[{expected}]" in out, f"{_id}: expected {expected}, got:\n{out}"


def test_the_unmutated_fixture_is_the_control(capsys):
    """Without this, every mutation test above would pass on a gate that failed
    everything -- the tautology the mutation class exists to avoid."""
    code = main([
        str(WORKED), "--styleboard", str(FIXTURES / "worked_example_styleboard.md")
    ])
    assert code == 0, capsys.readouterr().out


LIBRARY_MUTATIONS = [
    ("entry-annotated",  "### rgs-present-soccer-a", "### rgs-present-soccer-a (channel)"),
    ("entry-capitalised","### rgs-present-soccer-a", "### RGS-Present-Soccer-A"),
    ("section-renamed",  "## Entries",               "## Library entries"),
]


@pytest.mark.parametrize("case", LIBRARY_MUTATIONS, ids=[m[0] for m in LIBRARY_MUTATIONS])
def test_a_reformatted_style_library_fails_loudly_naming_the_library(case, tmp_path, capsys):
    """C-76: a partially-parsed Library made C20 blame the sheet for a typo the
    sheet does not have."""
    _id, find, replace = case
    library = tmp_path / "style-library.md"
    library.write_text(
        STYLE_LIBRARY.read_text(encoding="utf-8").replace(find, replace, 1), encoding="utf-8"
    )
    code = main([
        str(WORKED),
        "--styleboard", str(FIXTURES / "worked_example_styleboard.md"),
        "--style-library", str(library),
    ])
    out = capsys.readouterr().out
    assert code != 0, f"{_id}: {out}"
    assert "style-library" in out, f"{_id}: the Library must be named as the file at fault\n{out}"
```

- [ ] **Run it.** Expect several red cases at this point — they go green as T13–T21 land. Record
      which ones are red in the commit message; the class is the acceptance criterion for the
      rest of the package.
- [ ] **Implement:** nothing. This task's deliverable is the failing table.
- [ ] Commit: `test(gate-c): mutation-test a green sheet against every confirmed evasion`

---

### T7 — Exit codes stop lying (C-94, C-95)

Today a nonexistent sheet exits **1** with a traceback — indistinguishable from "the gate found
findings". And `2` means four different things.

- [ ] **Write the failing test:**

```python
def test_a_missing_sheet_exits_with_its_own_code_not_the_failing_gate_code(tmp_path, capsys):
    code = main([str(tmp_path / "nope.md")])
    out = capsys.readouterr().out
    assert code == EXIT_UNREADABLE_INPUT
    assert code != EXIT_FINDINGS
    assert "nope.md" in out


def test_a_missing_styleboard_names_the_styleboard_not_the_sheet(tmp_path, capsys):
    code = main([str(FIXTURES / "passing_sheet.md"), "--styleboard", str(tmp_path / "no.md")])
    assert code == EXIT_UNREADABLE_INPUT
    assert "no.md" in capsys.readouterr().out


def test_the_exit_codes_are_all_distinct():
    """Surfacing: an automated caller branches on these. Four operator actions
    collapsing into `2` is what C-95 records."""
    assert len({EXIT_PASS, EXIT_FINDINGS, EXIT_USAGE, EXIT_UNREADABLE_INPUT,
                EXIT_UNPARSEABLE, EXIT_MISSING_DEPENDENCY}) == 6


def test_an_unparseable_sheet_no_longer_shares_a_code_with_argparse(tmp_path, capsys):
    empty = tmp_path / "empty.md"
    empty.write_text("nothing here", encoding="utf-8")
    assert main([str(empty)]) == EXIT_UNPARSEABLE
```

- [ ] **Run it.** `NameError: EXIT_UNREADABLE_INPUT` (and add the constants to the test import).
- [ ] **Implement.** Constants plus a docstring table:

```python
# Exit codes. argparse owns 2 unconditionally, so nothing else may use it.
EXIT_PASS = 0                 # no findings
EXIT_FINDINGS = 1             # the gate found findings -- the sheet is the problem
EXIT_USAGE = 2                # argparse only
EXIT_UNREADABLE_INPUT = 3     # a named path could not be read
EXIT_UNPARSEABLE = 4          # the artifact was read but yielded no shots
EXIT_MISSING_DEPENDENCY = 5   # a required companion artifact is absent or empty


def _read(path: Path, label: str) -> str | None:
    """Read a path, or print which one failed and why. Returns None on failure.

    read_text was called before any error handling, so a mistyped path exited 1
    with a traceback -- the same code as a failing gate, sending the author to fix
    a sheet that was never read (finding C-94).
    """
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Gate C: cannot read {label} at {path}: {exc.strerror or exc}")
        return None
```

Route all three reads in `main()` through `_read`, returning `EXIT_UNREADABLE_INPUT` on `None`,
and change the existing returns: no-shots → `EXIT_UNPARSEABLE`; Library missing/empty →
`EXIT_MISSING_DEPENDENCY`. Add the table to the module docstring.

- [ ] **Run.** Green. `test_main_returns_two_when_no_shots_parse` fails — see §5.
- [ ] Commit: `fix(gate-c): distinct exit codes for unreadable, unparseable and missing input`

---

### T8 — The CLI gets the fail-closed guard the app path already has (C-74)

- [ ] **Write the failing test:**

```python
def test_the_cli_fails_closed_on_an_empty_styleboard_naming_the_styleboard(tmp_path, capsys):
    """gates.py:87-96 raises here, with a comment saying linting against an empty
    world 'would emit a wall of C8/C18 findings naming the wrong problem'. main()
    had no such branch and emitted 14 findings, none naming the styleboard."""
    empty = tmp_path / "styleboard.md"
    empty.write_text("=== STYLEBOARD — backfilled, not recoverable ===\n", encoding="utf-8")
    code = main([str(FIXTURES / "passing_sheet.md"), "--styleboard", str(empty)])
    out = capsys.readouterr().out
    assert code == EXIT_MISSING_DEPENDENCY
    assert "styleboard.md" in out
    assert "C8" not in out, "the wall of wrong-problem findings must not be emitted"
```

- [ ] **Run it.** `assert 1 == 5`, and `C8` is all over the output.
- [ ] **Implement** in `main()`, immediately after the styleboard is parsed:

```python
    if args.styleboard is not None:
        world = parse_world_lock(styleboard_text)
        if not world:
            # Parity with pipeline_app.gates.run_prompt_sheet_gate:86-96. Linting
            # against an empty world emits a wall of C8/C18 findings naming the
            # wrong artifact. Fail closed and say which file is empty.
            print(
                f"Gate C: styleboard {args.styleboard.name} has no parseable WORLD LOCK "
                f"block -- Gate C cannot check {args.sheet.name} against an empty world."
            )
            return EXIT_MISSING_DEPENDENCY
```

- [ ] **Run.** Green.
- [ ] Commit: `fix(gate-c): CLI fails closed on an empty world lock, matching the app path`

---

### T9 — `--style-library` stops being an invisible escape hatch (C-75)

A four-line hand-written file containing `## Entries` / `### anything-goes` turned a C20-failing
sheet into `PASS — 5 shots, 0 findings`. The app path hard-codes the repo Library; the CLI
accepts any path, and nothing in the output said which was used.

- [ ] **Write the failing test:**

```python
def test_the_resolved_style_library_path_is_printed_on_a_pass(capsys):
    main([str(WORKED), "--styleboard", str(FIXTURES / "worked_example_styleboard.md")])
    assert str(STYLE_LIBRARY) in capsys.readouterr().out


def test_a_non_default_style_library_is_named_in_the_output(tmp_path, capsys):
    """Distinguishability: a run against a hand-written stub must be visibly
    different in the transcript from a run against the repo Library."""
    stub = tmp_path / "stub.md"
    stub.write_text("# x\n\n## Entries\n\n### anything-goes\n", encoding="utf-8")
    main([str(WORKED), "--styleboard", str(FIXTURES / "worked_example_styleboard.md"),
          "--style-library", str(stub)])
    out = capsys.readouterr().out
    assert "NON-DEFAULT" in out
    assert str(stub) in out


def test_the_cli_default_library_is_the_exact_path_the_app_path_hard_codes():
    """Surfacing/parity: gates.py computes repo_root/'docs'/'style-library.md'.
    Two gates wearing one name is worse than one gate."""
    assert DEFAULT_STYLE_LIBRARY == Path(__file__).resolve().parents[1] / "docs" / "style-library.md"
```

- [ ] **Run it.** The path appears nowhere in stdout.
- [ ] **Implement.** In `main()`, once the Library is resolved, print a provenance line before
      the verdict — on **both** the pass and fail paths:

```python
    if library is not None:
        marker = "" if args.style_library == DEFAULT_STYLE_LIBRARY else " [NON-DEFAULT]"
        print(f"Gate C: Style Library{marker}: {args.style_library} "
              f"({len(library)} entries)")
```

Keep the flag (the mutation tests in T6 need it) but make its use impossible to miss in a
transcript. Update `--style-library`'s help text to say a non-default path is recorded in the
output.

- [ ] **Run.** Green.
- [ ] Commit: `fix(gate-c): record the resolved Style Library path in every run`

---

### T10 — `parse_style_library` stops dropping entries silently (C-76)

- [ ] **Write the failing test:**

```python
def test_an_annotated_entry_heading_is_reported_not_dropped():
    library, findings = parse_style_library_checked(
        LIBRARY_DOC.replace("### rgs-present-soccer-a", "### rgs-present-soccer-a (channel)")
    )
    assert "rgs-present-soccer-a" not in library
    assert [f.check for f in findings] == ["PARSE"]
    assert "(channel)" in findings[0].message


def test_an_unterminated_fence_in_the_library_is_reported():
    doc = LIBRARY_DOC.replace("code:         832507909\n```", "code:         832507909\n")
    _library, findings = parse_style_library_checked(doc)
    assert any("unterminated" in f.message for f in findings)


def test_a_partially_parsed_library_is_distinguishable_from_a_complete_one():
    """The whole defect: a partial parse presented exactly like a complete one, and
    C20 then failed the sheet with an incomplete 'Known entries' list."""
    good, good_findings = parse_style_library_checked(LIBRARY_DOC)
    bad, bad_findings = parse_style_library_checked(
        LIBRARY_DOC.replace("### rgs-present-soccer-a", "### RGS-Present-Soccer-A")
    )
    assert good_findings == [] and bad_findings != []
    assert set(good) != set(bad)


def test_parse_style_library_keeps_its_original_signature():
    """P3's gates.py:111 calls linter.parse_style_library(text) and expects a dict."""
    assert isinstance(parse_style_library(LIBRARY_DOC), dict)
```

- [ ] **Run it.** `NameError: parse_style_library_checked`.
- [ ] **Implement.** Rename the body to `parse_style_library_checked(text) -> tuple[dict, list[Finding]]`,
      keep `parse_style_library(text) -> dict` as the dict-only wrapper `gates.py` calls, and add
      the two rejects:

```python
        heading = ENTRY_HEADING_RE.match(stripped)
        if stripped.startswith("### "):
            if heading and VALID_SLOT_VALUE_RE.match(heading.group(1)):
                label = heading.group(1)
                library[label] = ""
            else:
                findings.append(Finding(
                    "PARSE", None,
                    f"'{stripped}' sits under '## Entries' but is not a bare kebab-case "
                    "label, so the entry is invisible to C20 and every sheet binding it "
                    "fails against a Library that looks complete. Required: "
                    "'### <lowercase-kebab-label>' and nothing else on the line.",
                    kind="parse",
                ))
            continue
    if in_fence:
        findings.append(Finding(
            "PARSE", None,
            "unterminated ``` fence in the Style Library; every entry after it was "
            "dropped.",
            kind="parse",
        ))
```

In `main()`, print any Library `PARSE` findings and return `EXIT_MISSING_DEPENDENCY` — a Library
that cannot be fully read is a missing dependency, not a sheet defect.

- [ ] **Run.** Green, including T6's `LIBRARY_MUTATIONS` cases.
- [ ] Commit: `fix(gate-c): report a Style Library entry the parser had to drop`

---

### T11 — The Library says its headings are load-bearing (C-77)

The coupling is stated once, buried in "Open questions §2" as prose about a resolved question.
An editor tidying `## Entries` has no local signal.

- [ ] **Write the failing test:**

```python
def test_the_library_warns_at_the_headings_the_parser_depends_on():
    """C-77: the coupling was documented only in Open questions §2. An editor
    reformatting the file reads Entry format and ## Entries, not the appendix."""
    text = STYLE_LIBRARY.read_text(encoding="utf-8")
    before_entries = text.split("## Entries")[0]
    assert "lint_prompt_sheet.py" in before_entries.split("## Entry format")[1]
    heading_at, _rest = text.split("## Entries", 1)
    assert "MACHINE-READ" in heading_at[-400:]


def test_the_libraryS_own_entries_still_parse_after_the_warning_edits():
    library, findings = parse_style_library_checked(STYLE_LIBRARY.read_text(encoding="utf-8"))
    assert findings == []
    assert {"rgs-present-soccer-a", "rgs-sourceera-painterly-b"} <= set(library)
```

- [ ] **Run it.** Both assertions fail.
- [ ] **Implement** in `docs/style-library.md`. Inside `## Entry format`, immediately under the
      fence, and again immediately above `## Entries`:

> **MACHINE-READ — do not reformat.** `scripts/lint_prompt_sheet.py:parse_style_library` walks
> this file to resolve Gate C's **C20**. It requires the section heading to be exactly
> `## Entries`, and every entry heading to be exactly `### <lowercase-kebab-label>` with nothing
> else on the line — no parenthetical, no capitals. Every ``` fence must be closed. Renaming the
> section, annotating a heading or leaving a fence open drops entries and makes C20 fail every
> sheet that binds them, naming the *sheet* as the problem.

- [ ] **Run.** Green.
- [ ] Commit: `docs(style-library): warn that the Entries headings are parsed by Gate C`

---

### T12 — The Library's own provenance is repaired (C-49, C-50, C-51)

- [ ] **Write the failing test:**

```python
LIBRARY_TEXT = STYLE_LIBRARY.read_text(encoding="utf-8")


def test_the_library_uses_no_invented_provenance_marker():
    """C-49: `[run owner, 2026-08-08]` is a sixth marker CLAUDE.md does not define.
    A grep for [P] to enumerate operator decisions missed both of this file's."""
    assert "[run owner" not in LIBRARY_TEXT
    assert LIBRARY_TEXT.count("[P]") >= 2


def test_every_library_entry_carries_every_field_the_entry_format_declares():
    """C-50: rgs-present-soccer-a omitted `seed:` -- the only record of how a
    channel-wide durable code was produced, and unrecoverable by re-running the
    session (this file's own [T] note says a re-entry stacks rather than replaces)."""
    entries = LIBRARY_TEXT.split("## Entries", 1)[1].split("\n### ")[1:]
    for entry in entries:
        label = entry.splitlines()[0].strip()
        for field in ("brand:", "register:", "scope:", "mechanism:", "world:",
                      "seed:", "code:", "harvested_at:"):
            assert field in entry, f"{label} omits {field}"


def test_every_T_marker_in_the_library_carries_a_verification_date():
    """C-51: two undated Midjourney platform claims, one of which is the reason the
    file gives for never re-entering a locked session."""
    for line_no, line in enumerate(LIBRARY_TEXT.splitlines(), 1):
        if "[T]" in line:
            assert "verified 20" in line, f"style-library.md:{line_no} has an undated [T]"
```

- [ ] **Run it.** All three fail.
- [ ] **Implement** in `docs/style-library.md`:
  - `:149` — `**Medium: artistic, not photographic** [P] (run owner, 2026-08-08).`
  - `:174` — `**[P] DECIDED 2026-08-08 (run owner): keep the bands unchanged for now.**`
  - Add a marker legend to the header, in the shape `channel-voice.md:7-10` uses, naming
    `[C]`/`[I]`/`[T]`/`[P]` and stating that `[P]` records *what was decided*, never *why it is
    correct*.
  - `:67` and `:69-71` — append `(verified 2026-07-26)` to each `[T]`, citing
    `.claude/skills/midjourney-prompting/references/` as the dated source.
  - `rgs-present-soccer-a` (`:126-138`) — add a `seed:` line. If no seeded session produced the
    code, record exactly that: `seed:  none -- code supplied directly by the run owner,
    2026-08-08; no Style Creator session was seeded.` **Do not invent a seed description.**
  - The entry-fields test must not break `parse_style_library` — `seed:` sits inside the fence
    and is ignored by the walk. T11's second test is the guard.
- [ ] **Run.** Green.
- [ ] Commit: `docs(style-library): mark the operator decisions [P], date the [T] claims, record the seed`

---

### T13 — C13 checks what `--ar` *says* (C-81) + first F-13 inversion

`if "--ar" not in flags` is the entire assertion. Rewriting every `--ar 9:16` to `--ar 16:9`
produced `PASS — 5 shots, 0 findings` — every asset in a vertical Short rendering landscape.

- [ ] **Invert** `test_c13_flags_missing_aspect_ratio` (`tests/test_lint_prompt_sheet.py:380-382`)
      and add the value case:

```python
def test_c13_flags_missing_aspect_ratio():
    shot = make_shot(1, "A", prompt=DENSE_A + ", No Text. --raw --s 95")
    assert "C13" in codes(check_format([shot]))


def test_c13_flags_a_landscape_aspect_ratio():
    """F-13/C-81: the old test covered --ar absence only, never its value. A Short
    is vertical; --ar 16:9 passed the whole gate."""
    shot = make_shot(1, "A", prompt=DENSE_A + ", No Text. --ar 16:9 --raw --s 95")
    findings = check_format([shot])
    assert "C13" in codes(findings)
    assert any("16:9" in f.message and REQUIRED_ASPECT_RATIO in f.message for f in findings)


def test_c13_accepts_the_required_aspect_ratio():
    shot = make_shot(1, "A", prompt=DENSE_A + ", No Text. --ar 9:16 --raw --s 95")
    assert "C13" not in codes(check_format([shot]))
```

- [ ] **Run it.** The landscape case fails.
- [ ] **Implement:**

```python
# The format's aspect ratio, as a module constant so a future non-vertical format
# overrides it in one place. C13 previously asserted only that --ar was *present*.
REQUIRED_ASPECT_RATIO = "9:16"
AR_FLAG_RE = re.compile(r"--ar\s+(\S+)")
```

and in `check_format`, replacing the `"--ar" not in flags` branch:

```python
        aspect = AR_FLAG_RE.search(flags)
        if aspect is None:
            findings.append(Finding("C13", shot.index, "no --ar in the parameter block"))
        elif aspect.group(1) != REQUIRED_ASPECT_RATIO:
            findings.append(Finding(
                "C13", shot.index,
                f"--ar {aspect.group(1)} is not the required {REQUIRED_ASPECT_RATIO}; "
                "a Short is vertical and every asset must be generated that way.",
            ))
```

- [ ] **Run.** Green, and T6's `ar-landscape` case goes green.
- [ ] Commit: `fix(gate-c): C13 requires --ar 9:16, not merely an --ar`

---

### T14 — C17 accepts only a recorded style lock (C-79) + second F-13 inversion

`VALID_SREF_VALUE_RE` is `^(?:\d+|random|https?://\S+)$`, so `--sref 11111111` passes C16 —
and because the sheet then declares no slots, `sheet_declares_slots` returns False, the Library
is never loaded and **C20 is skipped entirely**. The audit's first proposed fix is the one to
take: require a `{style:…}` slot on every non-PLATE shot, making C20 the single resolution path.
This kills the numeric-`--sref` and bare-`--p` evasions with one rule.

- [ ] **Invert** `test_c16_accepts_numeric_url_and_random_sref`
      (`tests/test_lint_prompt_sheet.py:554-557`):

```python
def test_c16_treats_a_numeric_sref_as_valid_syntax_but_c17_still_requires_a_slot():
    """F-13/C-79. The old test asserted a fabricated `--sref 1122334455` produced no
    findings -- an S1 defect as a green test. A number is valid *syntax*; what it is
    not is a *recorded* lock, and only a {style:...} slot resolves against the
    Library. C16 stays silent (it checks shape); C17 fires (it requires a lock)."""
    for value in ("1122334455", "https://cdn.midjourney.com/a1b2.png", "random"):
        shot = _shot(f"a strap pulled tight, No Text. --ar 9:16 --raw --s 95 --sref {value}")
        assert check_style_reference([shot]) == []
        assert [f.check for f in check_style_mechanism([shot])] == ["C17"]


def test_c17_accepts_a_style_slot():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 {style:register_a}")
    assert check_style_mechanism([shot]) == []


def test_an_invented_numeric_sref_can_no_longer_make_c20_vacuous():
    """The compounding half of C-79: with no slot on the sheet,
    sheet_declares_slots() returned False and the Library was never even read."""
    shots, _ = parse_sheet(SHEET.replace("{style:register_a}", "--sref 11111111")
                                .replace("{style:register_b}", "--sref 22222222"))
    assert sheet_declares_slots(shots) is False
    assert "C17" in codes(check_style_mechanism(shots))
```

- [ ] **Run it.** `assert [] == ['C17']`.
- [ ] **Implement** in `check_style_mechanism`, replacing the `has_mechanism` expression:

```python
        # Only a {style:...} slot counts. A literal --sref (however plausible its
        # digits) and a --p profile are both unresolvable against the Library, so a
        # sheet carrying them declares no slots, C20 never runs, and Gate C passes a
        # Short whose look is unrecorded (findings C-79, C-80). The slot is the one
        # mechanism that has a single resolution path, and that path is C20.
        if STYLE_SLOT_RE.search(flags) is None:
            findings.append(Finding(
                "C17", shot.index,
                "no {style:...} slot in the parameter block. A literal --sref or --p "
                "is not a recorded style lock: it resolves against nothing, so C20 "
                "cannot check it and the Short's look is not written down anywhere. "
                "Bind the register to a Style Library entry in the styleboard and "
                "write its slot here.",
            ))
```

Update the docstring to state the new rule and why C16 still exists (it validates any literal an
author writes alongside the slot).

- [ ] **Run.** Green; T6's `sref-invented-number` goes green.
- [ ] Commit: `fix(gate-c): C17 requires a {style:...} slot so C20 is the only resolution path`

---

### T15 — A bare `--p` is syntax, not a lock (C-80) + third F-13 inversion

- [ ] **Invert** `test_c17_accepts_literal_sref_moodboard_or_slot`
      (`tests/test_lint_prompt_sheet.py:664-667`):

```python
def test_c17_rejects_a_bare_p_as_a_style_lock():
    """F-13/C-80. The old test enumerated C17's accepted mechanisms without
    distinguishing a recorded lock from an unrecorded one -- exactly the
    distinction the finding turns on. `--p` with no value is legitimate Midjourney
    syntax ('apply my active personalization profile') and stays legal for C16, but
    the look then depends on whichever operator's profile is active at paste time:
    unrecorded, unreproducible, invisible to the Library. Two characters used to
    defeat both style checks at once."""
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 --p")
    assert check_style_reference([shot]) == []          # C16: legal syntax
    assert [f.check for f in check_style_mechanism([shot])] == ["C17"]


def test_c17_rejects_a_valued_p_as_a_style_lock_too():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 --p m72678")
    assert [f.check for f in check_style_mechanism([shot])] == ["C17"]
```

- [ ] **Run it.** Fails if T14's implementation left `MOODBOARD_FLAG_RE` in the mechanism test.
- [ ] **Implement.** Delete `MOODBOARD_FLAG_RE` and its use (T14 already removed the disjunction;
      this task removes the dead constant and records the reasoning in the docstring). Keep
      `test_c16_accepts_a_bare_p_flag` — C16's acceptance of the syntax is still correct.
- [ ] **Run.** Green; T6's `sref-bare-p` goes green.
- [ ] Commit: `fix(gate-c): a --p profile is not a recorded style lock`

---

### T16 — C11 compares meaning, not bytes (C-82)

An exact clone of Shot 1 pasted as Shot 3 fires C11 with 12 shared clauses; appending the single
word "here" to each clause takes it to 0 and the sheet passes.

- [ ] **Write the failing test:**

```python
def test_c11_still_flags_an_exact_clone():
    a = build_prompt("unique head one")
    b = build_prompt("unique head two")
    assert "C11" in codes(check_prompt_clone([make_shot(1, prompt=a), make_shot(3, prompt=a)]))


def test_c11_flags_a_clone_disguised_by_one_appended_word_per_clause():
    """C-82, confirmed by execution: one word per clause took 12 shared clauses to 0."""
    original = build_prompt("unique head one")
    disguised = ", ".join(f"{c} here" for c in original.split(", "))
    findings = check_prompt_clone([make_shot(1, prompt=original), make_shot(3, prompt=disguised)])
    assert "C11" in codes(findings)


def test_c11_is_silent_on_genuinely_different_prompts():
    """Distinguishability, and the anti-tautology guard: a similarity threshold that
    fires on everything is not a check."""
    _shots, findings = lint_fixture("worked_example_sheet.md", "worked_example_styleboard.md")
    assert "C11" not in codes(findings)
```

- [ ] **Run it.** The disguised case fails.
- [ ] **Implement:**

```python
MAX_CLAUSE_SIMILARITY = 0.6


def _clause_tokens(clause: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", clause))


def _clauses_are_near_duplicates(left: str, right: str) -> bool:
    """Jaccard overlap of the two clauses' token sets.

    Byte equality per clause was the old test, and one appended word per clause
    defeated it while changing no visual idea (finding C-82).
    """
    a, b = _clause_tokens(left), _clause_tokens(right)
    if not a or not b:
        return False
    return len(a & b) / len(a | b) >= MAX_CLAUSE_SIMILARITY
```

and in `check_prompt_clone`, count a shared clause when any clause of `right` is a near-duplicate
of a clause of `left` (each `left` clause consumed at most once), keeping `MAX_SHARED_CLAUSES`
and the existing message shape.

- [ ] **Run.** Green, and both green fixtures stay clean.
- [ ] Commit: `fix(gate-c): C11 compares clause token sets, not exact strings`

---

### T17 — C12 stops claiming to check nine layers (C-83)

The docstring says C12 verifies "every prompt carries concrete renderable content in all nine
layers"; the implementation counts commas and words. Ten repetitions of
`wN filler token phrase alpha beta gamma` passed the entire gate.

- [ ] **Write the failing test:**

```python
def test_c12_flags_a_body_padded_with_repeated_filler():
    """C-83, confirmed by execution: the docstring promised a nine-layer content
    check; the implementation was a length floor, and padding is exactly what a
    model produces against a length target."""
    body = ", ".join(f"w{n} filler token phrase alpha beta gamma" for n in range(10))
    shot = make_shot(1, "A", prompt=body + ", club soccer goal net, No Text. --ar 9:16")
    assert "C12" in codes(check_prompt_density([shot]))


def test_c12_is_silent_on_a_real_dense_prompt():
    """Anti-tautology: the repetition check must separate padding from density."""
    shots, _ = parse_sheet(WORKED.read_text(encoding="utf-8"))
    assert check_prompt_density(shots) == []


def test_c12_docstring_does_not_claim_a_nine_layer_content_check():
    assert "nine layers" not in check_prompt_density.__doc__
```

- [ ] **Run it.** The padded prompt passes.
- [ ] **Implement.** Add a repetition floor beside the two existing counts, and rewrite the
      docstring to state honestly what C12 is:

```python
MIN_DISTINCT_TOKEN_RATIO = 0.55


def check_prompt_density(shots: list[Shot]) -> list[Finding]:
    """C12: the prompt body clears a clause floor, a word floor and a repetition floor.

    Deliberately NOT a nine-layer content check -- nothing here maps a clause to a
    layer, and the previous docstring's claim that it did was false (finding C-83).
    What it does catch is the shape of a padded body: a body whose distinct-token
    ratio falls below MIN_DISTINCT_TOKEN_RATIO is repeating itself to clear the
    floors rather than describing anything.
    """
```

with the new branch:

```python
        tokens = re.findall(r"[a-z0-9]+", _body_without_no_text(shot).lower())
        if tokens and len(set(tokens)) / len(tokens) < MIN_DISTINCT_TOKEN_RATIO:
            findings.append(Finding(
                "C12", shot.index,
                f"{len(set(tokens))} distinct tokens in {len(tokens)} words "
                f"(ratio {len(set(tokens)) / len(tokens):.2f}, need >= "
                f"{MIN_DISTINCT_TOKEN_RATIO}); the body is padding to clear the "
                "length floor, not describing the shot.",
            ))
```

- [ ] **Run.** Green. If a green fixture trips the ratio, lower the constant until it does not
      **and** the padded case still fires — record the chosen value in the commit message.
- [ ] Commit: `fix(gate-c): C12 catches padded bodies and stops overclaiming`

---

### T18 — C9 and C10 stop being five strings (C-84)

C9 bans `"empty gym"` and `"empty youth gym"`; "vacant gym", "deserted gym", "empty field",
"empty pitch" all pass. C10 bans three strings plus two optics patterns; "photorealistic",
"bokeh", "shallow depth of field", "Leica", "Kodachrome", "cinematic still" all pass. Both are
scoped to `prompt_body`, so the same vocabulary in the flag block is unreachable.

- [ ] **Write the failing test:**

```python
@pytest.mark.parametrize("venue", ["vacant gym", "deserted gym", "empty field", "empty pitch",
                                   "empty stadium", "abandoned pitch"])
def test_c9_flags_generic_venue_synonyms(venue):
    shot = make_shot(1, "A", prompt=f"{venue}, club soccer, goal net, No Text. --ar 9:16")
    assert "C9" in codes(check_world_lock([shot], WORLD))


@pytest.mark.parametrize("term", ["photorealistic", "photographic", "bokeh",
                                  "shallow depth of field", "leica", "kodachrome",
                                  "cinematic still"])
def test_c10_flags_photographic_vocabulary_synonyms(term):
    shot = make_shot(1, "B", prompt=f"a colonnade, {term}, No Text. --ar 9:16 --s 520")
    assert "C10" in codes(check_world_lock([shot], WORLD))


def test_c9_and_c10_scan_the_flag_block_too():
    """Both were scoped to prompt_body, so the same vocabulary written after the
    first flag was unreachable."""
    shot = make_shot(1, "B", prompt="a colonnade, No Text. --ar 9:16 --s 520 --style dslr")
    assert "C10" in codes(check_world_lock([shot], WORLD))


def test_both_green_fixtures_stay_clean_under_the_widened_lists():
    for sheet, board in MIGRATED_PAIRS:
        _shots, findings = lint_fixture(sheet, board)
        assert not [f for f in findings if f.check in ("C9", "C10")], sheet
```

- [ ] **Run it.** Most parametrized cases fail. **Note:** `passing_sheet.md:Shot 1` contains the
      literal `DSLR` in a Register **A** body — legal, and it must stay legal; C10 is
      Register B-scoped and stays that way.
- [ ] **Implement.** Widen both tuples, scanning `shot.prompt.lower()` rather than
      `prompt_body(shot).lower()`, and carry the provenance comment:

```python
# Widened from the two/three literals the audit found (finding C-84). Source: the
# same [I]-marked contract these were drawn from --
# .claude/skills/shorts-styleboard/references/visual-registers.md:47 (Register A
# world lock) and :64 (Register B banned vocabulary). The terms below are synonyms
# of those same two rules, not new craft claims. P13 mirrors this list back into
# that reference; see this plan's cross-package note.
BANNED_REGISTER_A_STRINGS = (
    "empty gym", "empty youth gym", "empty field", "empty pitch", "empty stadium",
    "empty court", "vacant gym", "vacant pitch", "deserted gym", "deserted pitch",
    "abandoned gym", "abandoned pitch", "generic gym", "generic field",
)
BANNED_REGISTER_B_STRINGS = (
    "dslr", "shot on 35mm film", "documentary", "photorealistic", "photographic",
    "photograph", "bokeh", "shallow depth of field", "depth of field", "leica",
    "kodachrome", "cinematic still", "film still", "lens flare", "telephoto",
    "wide-angle lens", "macro lens", "iso ",
)
```

- [ ] **Run.** Green; T6's `venue-synonym` and `registerb-photographic` go green.
- [ ] Commit: `fix(gate-c): widen C9/C10 vocabulary and scan the whole prompt`

---

### T19 — `Register PLATE` stops being a free pass (C-85)

A PLATE shot is skipped by C3's run computation, excluded from C6/C7 counts, exempt from C14's
bands, exempt from C17 and never touched by C8/C9/C10. Its only obligation is
`shot_class == "PLATE"`. Nothing bounds how many shots may be PLATE.

- [ ] **Write the failing test:**

```python
def test_c22_caps_the_share_of_plate_shots():
    """Relabelling an awkward shot 'Register PLATE' removed its every register check.
    Nothing bounded how many shots could take that exit."""
    shots = [make_shot(i, "PLATE", "PLATE", "MACRO", "LOW") for i in range(1, 5)] + \
            [make_shot(5, "A", "DETAIL", "CLOSE", "EYE")]
    findings = check_plate_budget(shots)
    assert [f.check for f in findings] == ["C22"]
    assert "4 of 5" in findings[0].message


def test_c22_allows_a_single_plate_in_a_normal_sheet():
    shots = [make_shot(1, "PLATE", "PLATE", "MACRO", "LOW")] + \
            [make_shot(i, "A", "DETAIL", "CLOSE", "EYE") for i in range(2, 7)]
    assert check_plate_budget(shots) == []


def test_a_plate_shot_must_still_carry_a_stylize_value():
    """C14's bands were skipped entirely for PLATE because REGISTER_BANDS.get
    returned None and the loop hit `continue`."""
    shot = make_shot(1, "PLATE", "PLATE", prompt=DENSE_A + ", No Text. --ar 9:16")
    assert "C14" in codes(check_format([shot]))


def test_the_plate_exemptions_that_remain_are_the_register_specific_ones():
    """Distinguishability: PLATE is still exempt from C8/C9/C10/C17 by design --
    it is a subject-free background plate with no register look to lock. The audit
    finding is that it was *also* exempt from everything else."""
    shot = make_shot(1, "PLATE", "PLATE", prompt=DENSE_A + ", No Text. --ar 9:16 --s 200")
    assert codes(check_world_lock([shot], WORLD)) == []
    assert check_style_mechanism([shot]) == []
    assert check_format([shot]) == []
```

- [ ] **Run it.** `NameError: check_plate_budget`.
- [ ] **Implement:**

```python
MAX_PLATE_SHARE = 1 / 3
# PLATE carries no register look, so it has no --raw requirement and no register
# band -- but it is still a render, and a render with no --s is not a specified
# render. The band is wide and low: a plate is a ground, not a stylised image.
REGISTER_BANDS = {"A": (80, 120, True), "B": (400, 700, False), "PLATE": (0, 250, False)}


def check_plate_budget(shots: list[Shot]) -> list[Finding]:
    """C22: PLATE is an exemption, so it needs a ceiling.

    A PLATE shot is exempt from C3's run computation, C6/C7's register counts, and
    C8/C9/C10/C17 -- every rule that makes the dual-register system a system. Those
    exemptions are correct for a subject-free background plate and catastrophic as
    an unbounded escape hatch: relabelling a failing Register B shot as PLATE
    cleared its every register check (finding C-85).
    """
    plates = [s for s in shots if s.register == "PLATE"]
    if not plates or len(plates) <= max(1, int(len(shots) * MAX_PLATE_SHARE)):
        return []
    return [Finding(
        "C22", None,
        f"{len(plates)} of {len(shots)} shots are Register PLATE (max "
        f"{MAX_PLATE_SHARE:.0%}). PLATE is exempt from C3/C6/C7/C8/C9/C10/C17, so a "
        "sheet made mostly of plates is a sheet mostly unchecked.",
    )]
```

Wire `check_plate_budget` into `lint()` beside `check_shot_count`.

- [ ] **Run.** Green; T6's `plate-relabel` case fails on C15 as expected (the relabelled shot
      keeps its non-PLATE `shot_class`), which is the correct signal.
- [ ] Commit: `feat(gate-c): C22 caps PLATE shots and gives them a stylize band`

---

### T20 — The cover cannot ship unlinted (C-78, C-86)

`parse_cover` returns `None` when `prompt_lines` is empty, collapsing "no cover" and "cover
present but unreadable" into one state — and if the sheet also carries `Cover = Hook`, C19 is
satisfied and `lint_cover` never runs. The thumbnail, the highest-leverage asset in the Short,
ships with zero checks. Separately, `COVER_REUSE_RE` matches the bare literal `cover = hook`
with nothing verifying a hook shot exists.

- [ ] **Write the failing test:**

```python
def test_a_cover_heading_with_an_unreadable_fence_is_a_finding_not_silence():
    """C-78: ```markdown instead of ```text made parse_cover return None, which is
    the same value as 'this sheet has no cover'."""
    text = SHEET + "\n### Cover — Hook · Register A · DETAIL · MACRO · LOW\n\n```markdown\nx\n```\n"
    findings = check_cover_present(text)
    assert [f.check for f in findings] == ["C19"]
    assert "unreadable" in findings[0].message


def test_an_unreadable_cover_is_distinguishable_from_no_cover_at_all():
    unreadable = SHEET + "\n### Cover — Hook · Register A · DETAIL · MACRO · LOW\n\n```markdown\nx\n```\n"
    absent = SHEET
    assert check_cover_present(unreadable)[0].message != check_cover_present(absent)[0].message


def test_c19_requires_the_reused_hook_shot_to_exist():
    """C-86: the literal text 'cover = hook' on its own line satisfied C19 for any
    sheet, with nothing checking that a hook shot existed."""
    text = "PER-SHOT PROMPTS\n\nCover = Hook beat still #1\n"
    assert "C19" in codes(check_cover_present(text))


def test_c19_accepts_a_reuse_declaration_backed_by_a_real_hook_shot():
    """Anti-tautology control."""
    assert check_cover_present(WORKED.read_text(encoding="utf-8")) == []


def test_a_mistyped_shot_fence_cannot_swallow_the_cover_prompt():
    """_read_fenced_prompt broke on SHOT_HEADING_RE but not COVER_HEADING_RE."""
    text = SHEET.replace("```text\nluminous", "```txt\nluminous") + \
        "\n### Cover — Hook · Register A · DETAIL · MACRO · LOW\n\n```text\ncover body here\n```\n"
    cover = parse_cover(text)
    assert cover is not None and cover.prompt.startswith("cover body")
```

- [ ] **Run it.** Four of the five fail.
- [ ] **Implement:**
  - Add `COVER_HEADING_RE` and `LOOSE_COVER_HEADING_RE` to `_read_fenced_prompt`'s break
    condition, beside `SHOT_HEADING_RE`.
  - Split `parse_cover`'s two `None` returns: add
    `cover_heading_present(text) -> bool` (a `COVER_HEADING_RE` line exists) and have
    `check_cover_present` emit
    `"a '### Cover — ...' heading is present but its prompt fence is unreadable (expected ```text); the cover would ship unlinted"`
    when the heading exists and `parse_cover` returns `None`.
  - When the reuse branch is taken, resolve it: `COVER_REUSE_RE` already captures nothing, so
    extend it to `^\s*Cover\s*=\s*Hook\b.*?#?(\d+)?` and require that either a shot whose `beat`
    starts with `Hook` exists, or the named index exists; then run that shot's prompt through
    `lint_cover`, re-tagged at index 0. Emit C19 naming the missing hook shot otherwise.
- [ ] **Run.** Green; T6's `cover-fence-markdown` goes green.
- [ ] Commit: `fix(gate-c): an unreadable or unbacked cover is a finding, not silence`

---

### T21 — C8 is a depiction check, or says it is not (C-87)

`sport not in body` and `any(obj in body for obj in objects)` are the whole assertion. The sport
named once anywhere in a 60-word body plus one object noun satisfies C8 — and it matches inside
larger words.

- [ ] **Write the failing test:**

```python
def test_c8_does_not_match_the_sport_inside_a_larger_word():
    shot = make_shot(1, "A", prompt="a clubsoccerboot on turf, goal net, corner flag, "
                                    "No Text. --ar 9:16 --raw --s 95")
    assert "C8" in codes(check_world_lock([shot], WORLD))


def test_c8_requires_two_signature_objects_not_one():
    shot = make_shot(1, "A", prompt="club soccer, a goal net alone in fog, "
                                    "No Text. --ar 9:16 --raw --s 95")
    findings = check_world_lock([shot], WORLD)
    assert "C8" in codes(findings)
    assert "at least 2" in [f.message for f in findings if f.check == "C8"][0]


def test_c8_passes_a_prompt_that_actually_depicts_the_world():
    shot = make_shot(1, "A", prompt="club soccer, a goal net, a corner flag, "
                                    "No Text. --ar 9:16 --raw --s 95")
    assert "C8" not in codes(check_world_lock([shot], WORLD))


def test_both_green_fixtures_still_satisfy_the_stricter_c8():
    for sheet, board in MIGRATED_PAIRS:
        _shots, findings = lint_fixture(sheet, board)
        assert "C8" not in codes(findings), sheet
```

- [ ] **Run it.** The first two fail.
- [ ] **Implement:** match the sport and each object with
      `re.search(rf"\b{re.escape(term)}\b", body)`, require
      `MIN_SIGNATURE_OBJECTS = 2` matches, and state in the message that C8 is a **mention**
      check over the world-lock terms, not a depiction check — so the docstring stops promising
      more than the code delivers.
- [ ] **Run.** Green; T6's `sport-compound-only` goes green. If a green fixture trips the
      two-object floor, the fixture is the evidence the floor is too high — record that and drop
      to `MIN_SIGNATURE_OBJECTS = 2` only for sheets whose world lock declares ≥3 objects.
- [ ] Commit: `fix(gate-c): C8 matches at word boundaries and requires two signature objects`

---

### T22 — C20 names the file the author must edit (A-34)

`check_slot_labels` resolves the label from the **styleboard's** world lock but emits the finding
with the **sheet's** `shot.index`, and the result is stored on the `visual` artifact. One
mistyped label in the styleboard fails the visual stage once per affected shot, and the
operator's first instinct is to edit the sheet — which cannot fix it.

- [ ] **Write the failing test:**

```python
def test_c20_names_the_styleboard_as_the_file_to_edit():
    """A-34: the label comes from the styleboard's WORLD LOCK, but the finding was
    reported against the sheet's shot index, so the operator edited the sheet."""
    shot = _shot("x, No Text. --ar 9:16 --raw --s 95 {style:register_a}")
    findings = check_slot_labels([shot], {"slot_register_a": "typo-label"},
                                 {"rgs-present-soccer-a": "832507909"})
    assert [f.check for f in findings] == ["C20"]
    assert "styleboard" in findings[0].message
    assert "slot_register_a" in findings[0].message


def test_c20_still_reports_the_shot_so_the_operator_knows_which_binding_bit():
    shot = _shot("x, No Text. --ar 9:16 --raw --s 95 {style:register_a}", index=7)
    findings = check_slot_labels([shot], {"slot_register_a": "typo-label"}, {"a": ""})
    assert findings[0].shot_index == 7
    assert findings[0].beat == "shot 7"
```

- [ ] **Run it.** `assert "styleboard" in ...` fails.
- [ ] **Implement:** prepend to C20's message
      `"the styleboard's WORLD LOCK binds {key} to {value!r}, which is not an entry in
      docs/style-library.md — fix the label in the STYLEBOARD, not in this sheet. "`, keeping the
      known-entries list and the shot index.
- [ ] **Run.** Green.
- [ ] Commit: `fix(gate-c): C20 points the operator at the styleboard, not the sheet`

---

## 4. Finding → test map

Three-Test-Rule roles are given for every `failure_mode: silent` finding (16 of the 28).

| Finding | Silent | Named test(s) | Role |
|---|---|---|---|
| C-70 | ● | `test_a_broken_shot_heading_produces_a_blocking_parse_finding` | fault |
| | | `test_a_broken_heading_is_distinguishable_from_a_sheet_that_has_that_shot` | distinguishability |
| | | `test_a_single_mutation_of_a_green_sheet_always_fails_gate_c[heading-hyphen]` (asserts non-zero exit) | surfacing |
| C-71 | ● | `test_c21_flags_a_gap_in_the_shot_indices`, `test_c21_flags_a_duplicated_shot_index`, `test_c21_flags_a_declared_count_that_disagrees_with_the_parse` | fault |
| | | `test_c21_is_silent_on_every_green_fixture` | distinguishability |
| | | `test_c21_runs_inside_lint_so_both_gate_c_callers_get_it` | surfacing |
| C-72 | ● | `test_a_heading_inside_a_fence_is_not_a_real_shot` | fault |
| | | `test_a_fenced_heading_produces_no_parse_finding_either` | distinguishability |
| | | `test_a_fenced_example_does_not_pollute_the_sequence_checks` | surfacing |
| C-73 | ● | `test_a_blank_line_does_not_truncate_the_world_lock_block`, `test_a_malformed_world_lock_entry_is_reported_not_skipped`, `test_a_second_world_lock_block_is_rejected_rather_than_last_win` | fault |
| | | `test_an_unindented_world_lock_body_is_reported_not_silently_empty` | distinguishability |
| | | `test_a_single_mutation_of_a_green_sheet_always_fails_gate_c[world-second-block]` | surfacing |
| C-74 | | `test_the_cli_fails_closed_on_an_empty_styleboard_naming_the_styleboard` | — (loud) |
| C-75 | ● | `test_a_non_default_style_library_is_named_in_the_output` | fault |
| | | `test_the_resolved_style_library_path_is_printed_on_a_pass` | distinguishability |
| | | `test_the_cli_default_library_is_the_exact_path_the_app_path_hard_codes` | surfacing |
| C-76 | ● | `test_an_annotated_entry_heading_is_reported_not_dropped`, `test_an_unterminated_fence_in_the_library_is_reported` | fault |
| | | `test_a_partially_parsed_library_is_distinguishable_from_a_complete_one` | distinguishability |
| | | `test_a_reformatted_style_library_fails_loudly_naming_the_library[*]` (3 cases, exit code + named file) | surfacing |
| C-77 | | `test_the_library_warns_at_the_headings_the_parser_depends_on`, `test_the_libraryS_own_entries_still_parse_after_the_warning_edits` | — (docs) |
| C-78 | ● | `test_a_cover_heading_with_an_unreadable_fence_is_a_finding_not_silence`, `test_a_mistyped_shot_fence_cannot_swallow_the_cover_prompt` | fault |
| | | `test_an_unreadable_cover_is_distinguishable_from_no_cover_at_all` | distinguishability |
| | | `test_a_single_mutation_of_a_green_sheet_always_fails_gate_c[cover-fence-markdown]` | surfacing |
| C-79 | ● | `test_c16_treats_a_numeric_sref_as_valid_syntax_but_c17_still_requires_a_slot` | fault |
| | | `test_an_invented_numeric_sref_can_no_longer_make_c20_vacuous` | distinguishability |
| | | `test_a_single_mutation_of_a_green_sheet_always_fails_gate_c[sref-invented-number]` | surfacing |
| C-80 | ● | `test_c17_rejects_a_bare_p_as_a_style_lock`, `test_c17_rejects_a_valued_p_as_a_style_lock_too` | fault |
| | | `test_c16_accepts_a_bare_p_flag` (retained: legal syntax ≠ recorded lock) | distinguishability |
| | | `test_a_single_mutation_of_a_green_sheet_always_fails_gate_c[sref-bare-p]` | surfacing |
| C-81 | ● | `test_c13_flags_a_landscape_aspect_ratio` | fault |
| | | `test_c13_accepts_the_required_aspect_ratio` | distinguishability |
| | | `test_a_single_mutation_of_a_green_sheet_always_fails_gate_c[ar-landscape]` | surfacing |
| C-82 | ● | `test_c11_flags_a_clone_disguised_by_one_appended_word_per_clause` | fault |
| | | `test_c11_is_silent_on_genuinely_different_prompts` | distinguishability |
| | | `test_c11_still_flags_an_exact_clone` | surfacing |
| C-83 | ● | `test_c12_flags_a_body_padded_with_repeated_filler` | fault |
| | | `test_c12_is_silent_on_a_real_dense_prompt` | distinguishability |
| | | `test_c12_docstring_does_not_claim_a_nine_layer_content_check` | surfacing |
| C-84 | | `test_c9_flags_generic_venue_synonyms[*]` (6), `test_c10_flags_photographic_vocabulary_synonyms[*]` (7), `test_c9_and_c10_scan_the_flag_block_too`, `test_both_green_fixtures_stay_clean_under_the_widened_lists` | — (coverage-gap) |
| C-85 | ● | `test_c22_caps_the_share_of_plate_shots`, `test_a_plate_shot_must_still_carry_a_stylize_value` | fault |
| | | `test_the_plate_exemptions_that_remain_are_the_register_specific_ones` | distinguishability |
| | | `test_c22_allows_a_single_plate_in_a_normal_sheet` | surfacing |
| C-86 | | `test_c19_requires_the_reused_hook_shot_to_exist`, `test_c19_accepts_a_reuse_declaration_backed_by_a_real_hook_shot` | — (coverage-gap) |
| C-87 | | `test_c8_does_not_match_the_sport_inside_a_larger_word`, `test_c8_requires_two_signature_objects_not_one`, `test_c8_passes_a_prompt_that_actually_depicts_the_world`, `test_both_green_fixtures_still_satisfy_the_stricter_c8` | — (coverage-gap) |
| C-93 | | `test_finding_defaults_to_a_blocking_kind`, `test_no_gate_c_check_can_emit_a_skipped_kind` | — (latent) |
| C-94 | ● | `test_a_missing_sheet_exits_with_its_own_code_not_the_failing_gate_code` | fault |
| | | `test_a_missing_styleboard_names_the_styleboard_not_the_sheet` | distinguishability |
| | | `test_the_exit_codes_are_all_distinct` | surfacing |
| C-95 | | `test_an_unparseable_sheet_no_longer_shares_a_code_with_argparse`, `test_the_exit_codes_are_all_distinct` | — (latent) |
| A-34 | | `test_c20_names_the_styleboard_as_the_file_to_edit`, `test_c20_still_reports_the_shot_so_the_operator_knows_which_binding_bit` | — (latent) |
| A-43 | ● | `test_finding_carries_a_beat_the_stage_template_can_render` | fault |
| | | `test_finding_defaults_to_a_blocking_kind` (the record differs from Gate D's only in field names now) | distinguishability |
| | | `test_main_labels_a_cover_finding_as_cover_not_shot_0_or_sheet` (existing, retained; now shares `location_label` with the app path) | surfacing |
| C-49 | | `test_the_library_uses_no_invented_provenance_marker` | — (docs) |
| C-50 | | `test_every_library_entry_carries_every_field_the_entry_format_declares` | — (latent) |
| C-51 | | `test_every_T_marker_in_the_library_carries_a_verification_date` | — (docs) |
| F-13 | ● | `test_c13_flags_a_landscape_aspect_ratio`, `test_c16_treats_a_numeric_sref_as_valid_syntax_but_c17_still_requires_a_slot`, `test_c17_rejects_a_bare_p_as_a_style_lock` (the three inversions) | fault |
| | | `test_c13_accepts_the_required_aspect_ratio`, `test_c17_accepts_a_style_slot`, `test_c16_accepts_a_bare_p_flag` | distinguishability |
| | | the three mutation cases `ar-landscape`, `sref-invented-number`, `sref-bare-p` | surfacing |
| F-14 | | `test_a_single_mutation_of_a_green_sheet_always_fails_gate_c[*]` (22 cases), `test_the_unmutated_fixture_is_the_control`, `test_a_reformatted_style_library_fails_loudly_naming_the_library[*]` (3 cases) | — (coverage-gap) |

**Mutation-case count: 22 sheet mutations + 3 Style Library mutations + 1 unmutated control = 26
parametrized assertions**, every one of them entering through `main()` and text, not through a
`Shot` factory.

---

## 5. Tests deleted or inverted

Three tests assert the defective behavior is correct (F-13); one asserts an exit code that is
being re-assigned (C-95). All four are **inverted**, none deleted — the input each covers stays
covered, the assertion changes from "this passes" to "this is rejected for the right reason".

| File:line | Test | Disposition | Replacement |
|---|---|---|---|
| `tests/test_lint_prompt_sheet.py:554-557` | `test_c16_accepts_numeric_url_and_random_sref` — asserts `--sref 1122334455` produces **no findings**, i.e. C-79 (S1) frozen as a green test | **Inverted** (T14) | `test_c16_treats_a_numeric_sref_as_valid_syntax_but_c17_still_requires_a_slot`: same three values, now asserting C16 silent **and** C17 firing. Keeps the syntax coverage, adds the intent. |
| `tests/test_lint_prompt_sheet.py:664-667` | `test_c17_accepts_literal_sref_moodboard_or_slot` — enumerates C17's accepted mechanisms without distinguishing a recorded lock from an unrecorded one, the distinction C-80 (S1) turns on | **Inverted** (T15) | `test_c17_rejects_a_bare_p_as_a_style_lock` + `test_c17_rejects_a_valued_p_as_a_style_lock_too` + `test_c17_accepts_a_style_slot`. The slot case survives as the positive; the two literal cases flip. |
| `tests/test_lint_prompt_sheet.py:380-382` | `test_c13_flags_missing_aspect_ratio` — covers `--ar` **absence** only, never its value; under C-81 (S1) every asset renders landscape and Gate C prints PASS | **Kept, and joined** (T13) | The test itself is correct and stays verbatim. `test_c13_flags_a_landscape_aspect_ratio` and `test_c13_accepts_the_required_aspect_ratio` are added beside it; the *name* is no longer the whole story of C13. |
| `tests/test_lint_prompt_sheet.py:509-512` | `test_main_returns_two_when_no_shots_parse` — asserts the overloaded exit code C-95 records | **Inverted** (T7) | `test_an_unparseable_sheet_no_longer_shares_a_code_with_argparse`: same input, asserts `EXIT_UNPARSEABLE` (4) and that it is not `EXIT_USAGE` (2). |

**Not deleted, explicitly retained:**

- `tests/test_lint_prompt_sheet.py:624-628` `test_c16_accepts_a_bare_p_flag` — still correct.
  `--p` with no value **is** legal Midjourney syntax; C-80 is about C17, not C16. This test
  becomes the distinguishability partner to `test_c17_rejects_a_bare_p_as_a_style_lock`.
- `tests/test_lint_prompt_sheet.py:608-616` `test_c17_now_agrees_with_c16_on_a_dangling_sref` —
  its assertion `check_style_mechanism([shot]) == []` **inverts under T14** (a bare `--sref` is
  no longer a mechanism). Update the assertion to `!= []` and rewrite the docstring; the
  agreement it guards still matters.
- `tests/test_lint_prompt_sheet.py:670-675` `test_c17_exempts_plate_shots` — the PLATE exemption
  from C17 survives T19 by design. T19's
  `test_the_plate_exemptions_that_remain_are_the_register_specific_ones` states which exemptions
  are deliberate so the next reader does not mistake one for the bug.
- `tests/test_lint_prompt_sheet.py:1049-1054` `test_c20_is_skipped_when_no_library_is_supplied` —
  correct in-unit behavior (`library is None` → C20 silent). The fail-closed guarantee lives at
  the `main()`/`gates.py` boundary, where a missing Library is `EXIT_MISSING_DEPENDENCY`, and
  T7/T9 assert that.

---

## 6. Contract for P3 (`pipeline-app/pipeline_app/gates.py`)

`run_prompt_sheet_gate`'s own docstring says it "must stay equivalent to
`lint_prompt_sheet.main`", and the audit found four live divergences. **P11 does not edit
`gates.py`.** These are the parity requirements P11's changes create, stated as a contract P3
implements.

### 6.1 What P11 guarantees to P3 (no change required on P3's side)

1. **`parse_sheet(text)` still unpacks as a 2-tuple.** `shots, sheet_world = linter.parse_sheet(text)`
   at `gates.py:75` keeps working verbatim. The return is a `tuple` subclass.
2. **`parse_style_library(text) -> dict` keeps its signature.** `gates.py:111` is unaffected.
   The new fail-closed variant is `parse_style_library_checked(text) -> (dict, list[Finding])`.
3. **`lint(shots, world, *, cover=..., library=...)` keeps its signature.** The new
   `declared_shot_count` is keyword-only with a `None` default.
4. **C-70 is closed on the app path with no `gates.py` change.** The reconciliation invariant
   (C21) and the PLATE cap (C22) live inside `lint()`, which `gates.py:123` already calls.
5. **Gate C emits only `kind="fail"` and `kind="parse"`, both blocking.** `gates.py:167`'s
   `f.get("kind") != "skipped"` therefore remains correct — and is now correct **by contract**
   rather than by the accident of a missing key (C-93). If Gate C ever needs a non-blocking
   kind, that rule must change first.
6. **Every Gate C finding dict now carries `beat`** (`"sheet"` / `"cover"` / `"shot 7"`), so
   `templates/stage.html:44-47` renders a location without `_as_dicts` doing any mapping (A-43).
   `_as_dicts` must keep passing findings through verbatim — **do not** strip or rename `beat`
   or `kind`.

### 6.2 What P3 must change for full parity

| # | Requirement | Why |
|---|---|---|
| **P3-1** | **Consume `parse_sheet(...).findings`.** Change `gates.py:75-77` to `parse = linter.parse_sheet(sheet_text)` and prepend `parse.findings` to the findings list returned at `:121-125`. Without this the app path still silently skips a malformed heading — it is protected only by C21's index gap, which does not fire when the *last* shot's heading breaks. | C-70 on the app path, completely |
| **P3-2** | **Pass the declared shot count through:** `linter.lint(shots, world, cover=cover, library=library, declared_shot_count=parse.declared_shot_count)`. | C-71 |
| **P3-3** | **Consume the Library's parse findings.** Change `gates.py:111` to `library, library_findings = linter.parse_style_library_checked(...)` and `raise ValueError` naming the Library file if `library_findings` is non-empty — matching the CLI's `EXIT_MISSING_DEPENDENCY`. | C-76 |
| **P3-4** | **Keep the Library path hard-coded** at `repo_root/"docs"/"style-library.md"` (`gates.py:105`). The CLI's `--style-library` remains, but P11 prints the resolved path and marks a non-default one `[NON-DEFAULT]`. The app path must not grow an override. | C-75 |
| **P3-5** | **Do not add a `skipped` kind to Gate C's blocking rule's exemption set** beyond what `gates.py:167` already has, and do not special-case `kind="parse"` — parse findings are blocking. | C-93 |

### 6.3 The exit-code ⇄ exception correspondence P3 must preserve

Every CLI condition that is not "pass" or "the sheet has findings" corresponds to a `ValueError`
in `gates.py`, which `run_gates_for_stage:160-166` turns into `status: "error"` — blocking.
The two paths must never disagree about which side of that line a condition falls on.

| Condition | `lint_prompt_sheet.main()` | `gates.run_prompt_sheet_gate` |
|---|---|---|
| No findings | `EXIT_PASS` (0) | `status: "pass"` |
| Findings (incl. `PARSE`, C21, C22) | `EXIT_FINDINGS` (1) | `status: "fail"` |
| argparse usage error | `EXIT_USAGE` (2) | n/a |
| Sheet / styleboard / Library unreadable | `EXIT_UNREADABLE_INPUT` (3) | `OSError` → `status: "error"` |
| No shots parsed | `EXIT_UNPARSEABLE` (4) | `ValueError` (`:76-77`) → `"error"` |
| Styleboard yields an empty world | `EXIT_MISSING_DEPENDENCY` (5) **[new, T8]** | `ValueError` (`:87-96`) → `"error"` |
| Library missing or empty | `EXIT_MISSING_DEPENDENCY` (5) | `ValueError` (`:106-119`) → `"error"` |
| Library partially unparseable | `EXIT_MISSING_DEPENDENCY` (5) **[new, T10]** | `ValueError` **[P3-3]** → `"error"` |

### 6.4 Cross-package note for P13 (not a blocker)

T18 widens `BANNED_REGISTER_A_STRINGS` and `BANNED_REGISTER_B_STRINGS` in the linter. Their
`[I]`-marked source of truth is
`.claude/skills/shorts-styleboard/references/visual-registers.md:47` and `:64`, which **P13
owns**. P13 should mirror the widened lists into those two lines so the skill instruction and the
gate agree on the vocabulary. Until it does, the gate is stricter than the instruction — the
safe direction, and it fails loudly rather than silently.

---

## 7. Package verification

The package is done when all of these hold:

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767" && python -m pytest tests/test_lint_prompt_sheet.py -q
```

1. All 26 mutation assertions pass, and `test_the_unmutated_fixture_is_the_control` passes —
   the gate rejects every confirmed evasion **and** still accepts the real sheet.
2. `python scripts/lint_prompt_sheet.py tests/fixtures/worked_example_sheet.md --styleboard tests/fixtures/worked_example_styleboard.md`
   exits **0** and prints the resolved Style Library path.
3. The same command with Shot 4's em-dash replaced by a hyphen exits **1** and prints
   `[PARSE]`, not `PASS`.
4. `python scripts/lint_prompt_sheet.py does-not-exist.md` exits **3** with no traceback.
5. `grep -n "kind" scripts/lint_prompt_sheet.py` shows no `"skipped"` anywhere.
6. `docs/style-library.md` carries a `[P]` marker on both operator decisions, a dated `[T]` on
   both platform claims, a `seed:` line in every entry, and the MACHINE-READ warning in two
   places — and `parse_style_library_checked` returns **zero** findings against it.
