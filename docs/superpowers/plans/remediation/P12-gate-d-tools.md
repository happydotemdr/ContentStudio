# P12 — Gate D & tools

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` or
> `superpowers:executing-plans`. Every task below is a checkbox step: failing test → run → see it
> fail for the right reason → implement → see it pass → commit.
>
> Binding context: [`../2026-08-08-audit-remediation.md`](../2026-08-08-audit-remediation.md)
> — its **Global Constraints**, **test standard** (Three-Test Rule, anti-tautology rules) and
> **Frozen interfaces** apply to every task here without restatement.
>
> `scripts/**` is **stdlib-only and must not import app code** — these files are loaded by file
> path by `pipeline_app/gates.py::_load_linter`. `obs.py` is **not available** in this package.
> Failure surfacing here is exit codes + stdout/stderr, nothing else.

---

## 1. Scope

### Files this package owns (no other package may touch them)

```
scripts/lint_script_language.py          (Gate D, checks D1–D6)
scripts/resolve_brief_version.py
scripts/build-cowork-plugin.sh
tests/test_lint_script_language.py
tests/test_resolve_brief_version.py
tests/test_protect_briefs.py
```

### New files this package creates (no other package owns these paths)

```
scripts/cowork_plugin_lock.py            (stdlib helper: roster + content hash, one algorithm)
scripts/cowork-plugin.lock.json          (tracked build stamp; NOT matched by .gitignore's
                                          `cowork-plugin/` directory pattern — verified)
tests/test_build_cowork_plugin.py        (repo-root suite)
```

No new fixture files: the Gate D mutation base lives as a module constant in
`tests/test_lint_script_language.py`, so the four shipped `tests/fixtures/script_*.md` stay
byte-identical and their calibration assertions stay meaningful.

### Files read but never written by this package

`pipeline-app/pipeline_app/gates.py` (P3 owns it — read only, for the drift guard in T8),
`.claude/hooks/protect_briefs.py` (read only — T14 tests it, does not edit it),
`.claude/skills/**` (P13 owns them — read only, for the roster check in T15/T17).

### Findings closed here (15)

C-88, C-89, C-90, C-91, C-92, C-96, C-97, C-98, C-99, C-100, C-101, C-102, C-103, C-104, F-23.

---

## 2. Finding → task map

Total coverage: every one of the 15 IDs has a primary task.

| Finding | Sev | failure_mode | Primary task | Also exercised by |
|---|---|---|---|---|
| C-88 | S1 | silent | **T1** (disguised heading fails closed) + **T2** (five-label cross-check) | T7, T8 |
| **C-88b** | **S1** | **silent** | **T1b** (a refused *sub-beat* line blocks instead of vanishing) | T7 |
| C-89 | S1 | silent | **T3** (`\| N words` is mandatory, not opt-in) | T7 |
| C-90 | S2 | silent | **T4** (ratable-fraction floor; malformed range blocks) | T7, T8 |
| C-91 | S3 | loud | **T5** (template match, not the pipe heuristic; fence scoping) | T7 |
| C-92 | S3 | coverage-gap | **T6** (D3/D4 scope disclosure as an `info` finding) | T8 |
| C-96 | S1 | silent | **T9** (missing `--dir` is an error; echo the resolved absolute dir) | T13, T14 |
| C-97 | S2 | silent | **T10** (version tie is an error naming both paths) | T13 |
| C-98 | S1 | silent | **T11** (`-vN` ↔ frontmatter cross-check; reject an existing proposal) | T13 |
| C-99 | S3 | silent | **T12** (`--date` validated against the resolver's own pattern) | T13 |
| C-100 | S2 | silent | **T9** (three distinct exit codes) | T13 |
| C-101 | S2 | docs-drift | **T15** (eight + three, derived from the copied tree) | T17 |
| C-102 | S2 | silent | **T16** (derived version, roster assertion, JSON validated, copy fails loud) | T17 |
| C-103 | S2 | silent | **T17** (tracked lock stamp + staleness test) | — |
| C-104 | S4 | latent | **T18** (prune junk before packaging; both branches archive one clean tree) | T17 |
| F-23 | S2 | coverage-gap | **T13** (CLI-level tests over `resolve_brief_version.py:68-91`) | T9–T12 |

Structural work is deliberately front-loaded: **T1–T4** are the fail-closed parsing and
mandatory-check fixes; **T7** is the mutation matrix that proves the whole gate cannot be
evaded one edit at a time; **T9** is the exit-code split every other resolver task depends on.

---

## 3. Tasks

### T1 — A line that names a beat but does not parse must block, not vanish

**Finding:** C-88 (part 1). Today `BEAT_LABEL_RE` anchors at the start of the stripped line, so
`**HOOK**`, `## HOOK`, `- HOOK` and `> HOOK` are not beats. `parse_script` `continue`s on them
and every downstream check runs vacuously over the survivors — bolding the HOOK label on
`script_let_kids_play_act.md` took the script from 6 VO lines to 5, emitted **zero** PARSE
findings, and deleted a real 260-wpm D5 violation.

- [ ] **Write the failing test** in `tests/test_lint_script_language.py`:

```python
def test_a_bolded_beat_label_is_a_blocking_parse_finding():
    """C-88 fault test. `**HOOK**` is a heading to every human who reads the
    script and to nobody in the parser. It used to delete the beat and every
    check over it, silently. It must now block."""
    text = (
        '**HOOK**   (0–3s | 8 words): "Best part was the mud today, honestly."\n'
        'SETUP      (3–8s | 6 words): "Kids do that every single time."\n'
    )
    lines, findings = parse_script(text)
    assert [vo.beat for vo in lines] == ["SETUP"]
    assert [(f.check, f.beat, f.kind) for f in findings] == [("PARSE", "HOOK", "fail")]
    assert "not a parseable beat heading" in findings[0].message


def test_a_disguised_heading_is_distinguishable_from_a_script_that_omits_it():
    """C-88 distinguishability test. A script that never had a HOOK and a script
    whose HOOK the parser refused must not produce the same finding set."""
    disguised = '## HOOK (0–3s | 8 words): "Best part was the mud today, honestly."\n'
    absent = 'SETUP (3–8s | 6 words): "Kids do that every single time."\n'
    _, disguised_findings = parse_script(disguised)
    _, absent_findings = parse_script(absent)
    assert disguised_findings != absent_findings
    assert [f.beat for f in disguised_findings] == ["HOOK"]
    assert absent_findings == []


def test_prose_that_merely_mentions_a_beat_label_is_not_a_disguised_heading():
    """The heuristic's guard rail: a notes line reading `- LOOP/CTA mirrors the
    hook` carries no range and no colon, so it is prose, not a refused heading."""
    text = (
        'HOOK (0–3s | 8 words): "Best part was the mud today, honestly."\n'
        "- LOOP/CTA mirrors the hook by design\n"
    )
    _, findings = parse_script(text)
    assert findings == []
```

- [ ] **Run it**, see three failures: `[]` != the expected finding list (the first two), and the
      third passing vacuously. Confirm the first failure is *"no finding emitted"*, not a
      `NameError`.
- [ ] **Implement** in `scripts/lint_script_language.py`, beside `BEAT_LABEL_RE`:

```python
BEAT_LABELS = ("HOOK", "SETUP", "BUILD/VALUE", "PAYOFF", "LOOP/CTA")
BEAT_LABEL_RE = re.compile(r"^(HOOK|SETUP|BUILD/VALUE|PAYOFF|LOOP/CTA)\b")
# Leading markdown furniture a heading can hide behind: blockquote, ATX heading,
# list bullet, bold/italic/underscore emphasis, inline code.
_MARKDOWN_LEAD_RE = re.compile(r"^[\s>#*_+`~-]+")
# After the furniture is stripped, a genuine heading still carries its range or
# its colon. Requiring one of those is what keeps a prose line that merely names
# a beat ("- LOOP/CTA mirrors the hook") from false-failing.
_SUSPECT_HEADING_RE = re.compile(
    r"^(HOOK|SETUP|BUILD/VALUE|PAYOFF|LOOP/CTA)\b[^\n]*[(:]"
)


def _disguised_beat_label(stripped: str) -> str | None:
    """The beat a line NAMES if it is a heading the parser refused, else None.

    This is the fail-closed half of the parser. `_beat_name` answers "is this a
    beat?"; this answers "did something that looks exactly like a beat just fall
    through?". A heading the parser cannot read must be a finding, never a
    deletion -- a deleted beat takes every D-check over it with it, and the
    coverage machinery below can only fire for headings it already recognised.

    Known limit, stated rather than papered over: a disguised heading carrying
    neither a `(` nor a `:` is not detected here. The five-label cross-check in
    `check_beat_set` is the independent second detector for that case."""
    unstyled = _MARKDOWN_LEAD_RE.sub("", stripped).replace("**", "").replace("__", "").lstrip()
    match = _SUSPECT_HEADING_RE.match(unstyled)
    return match.group(1) if match else None
```

and inside `parse_script`'s loop, replacing the bare `continue`:

```python
        beat = _beat_name(stripped)
        if beat is None:
            disguised = _disguised_beat_label(stripped)
            if disguised is not None:
                findings.append(
                    Finding(
                        "PARSE",
                        disguised,
                        f"line {number}: {stripped[:70]!r} names beat {disguised} but is "
                        "not a parseable beat heading -- strip the markdown styling so the "
                        "line begins with the bare label",
                        kind="fail",
                    )
                )
            continue
```

- [ ] **Run**, see all three pass. **Run the whole file** — `python -m pytest tests/test_lint_script_language.py -q` — and confirm the four shipped fixtures still parse to 6/6/7/8 VO lines with zero parse findings (`test_shipped_fixtures_parse_to_expected_counts`, `test_authorial_rounding_on_the_shipped_fixtures_never_fires_the_detector`).
- [ ] **Commit:** `fix(gate-d): a disguised beat heading blocks instead of vanishing (C-88)`

---

### T1b — A refused *sub-beat* line must block, not vanish

> **New finding C-88b, raised in the field on 2026-08-10, not in the original audit.** Filed after
> a real Gate D run on an authored Short. Root-cause and design reports:
> `.superpowers/sdd/2026-08-08-audit-remediation/GATE-D-PARSE-rootcause.md` and
> `-design.md`. **Must land after T1** — it extends the same refused-line branch, so sequencing it
> earlier only creates a conflict.

**C-88b (S1, silent).** `_beat_name()` (`scripts/lint_script_language.py:63-72`) returns `None` for
**both** "this line is prose and ignoring it is correct" **and** "this is a beat line carrying
spoken text in a shape I do not recognise", and the caller `continue`s on that shared value
(`:171`). The refused line is deleted from the lint surface before any state, finding, or its own
`| N words` witness is read — `DECLARED_WORDS_RE` runs at `:173`, *after* the `continue`, so the
one independent witness sitting on the line that broke is discarded in the same statement as the
words. The recurring defect class, in a text-to-structure parser.

**How it presented.** An author wrote a sub-beat label-first — `mechanism: (11–18s | 19 words)` —
which `SUBRANGE_RE = ^\(\d+` does not match because it requires the range to *start* the line. 49
of 62 words vanished. It surfaced only because a parent heading declared a total that then
disagreed with the extracted sum, and the response at the time was to **rewrite the script** to
satisfy the parser. That inverts causation: the parser never asserted the script was malformed, it
merely declined to read part of it.

**Why the existing tasks do not catch it — verified against their proposed implementations, not
assumed.** T1 adds `_disguised_beat_label` *beside* `_beat_name` and never modifies it, and its
detector matches only the five top-level `BEAT_LABELS`, so a sub-beat label names no beat label and
falls straight through. T2's `check_beat_set` is satisfied — all five labels are present. T3
operates on lines that already parsed, which a refused line never reaches. **No existing task
touches `_beat_name` or `SUBRANGE_RE`.**

**Two measurements that decide the design. Both were run; do not re-derive them.**

- **The declared-vs-extracted check is a coincidence, not a backstop.** Its threshold is
  `shortfall >= 3 AND >= 0.25 × declared`, so ~25% of any declared beat can vanish silently; it
  does not fire at all when `declared is None`; and it never fires on over-counts. Proven
  end-to-end with identical script bodies: declaring `62` prints `PASS`/exit 0, declaring `63`
  prints `FAIL` — one word apart. (T3 makes the budget mandatory, which closes the `declared is
  None` half; it does not close the 25% window.)
- **Refusing *every* unrecognised line inside a beat is not viable.** Measured: **100 false
  positives** scoped between headings and **2,186** scoped to EOF, because the format has no
  end-of-beat-block marker and "inside a beat" is therefore undefined after `LOOP/CTA`.

**The design: keep the format strict, and make refusal loud.** A refused line that carries a
parenthesised word budget is the author asserting it is a beat line — that is the signal, and it is
what visual-note lines like `Hook (0–3s): …` lack. Measured **2/2 true positives, 0 false
positives across all 19 real script artifacts**.

**Backward compatibility: zero files invalidated.** 0 hits across the 4 `tests/fixtures/script_*.md`,
0 across the 4 `rgs-briefs/` scripts, 0 under `docs/**`. One of 8 live
`runs/*/02-scripting/artifact.v*.md` gains findings, and it already fails today and is already
superseded by a passing v2.

**Gate C stays convergent.** `lint_prompt_sheet.py:84` has the identical bare skip and today prints
`Gate C: PASS — 10 shots, 0 findings` with a shot deleted (proven, mid-sheet and last-shot). P11's
C-70 gives Gate C a `parse_sheet(...).findings` channel — the same policy this task gives Gate D.
Accepting label-first sub-beats instead would have made the two gates **divergent**, which is why
that option was rejected here rather than merely deferred.

- [ ] **Write the failing tests** in `tests/test_lint_script_language.py`:

| Test | Role | Must prove |
|---|---|---|
| `test_a_label_first_sub_beat_is_a_blocking_parse_finding` | **fault** | `parse_script` returns a `("PARSE", "BUILD/VALUE", …, kind="fail")` finding whose message names the offending line number. Assert on the **emitted finding**, not the VO-line count — the count is the symptom, the finding is the behaviour. |
| `test_a_refused_sub_beat_is_distinguishable_from_a_beat_that_has_none` | **distinguishability** | `parse_script(with_refused)[1] != parse_script(with_none)[1]`, and the second is `[]`. This is the defect exactly: "the author wrote nothing" and "the parser ate what the author wrote" are the same empty list today. |
| `test_a_refused_sub_beat_reaches_the_shell_as_exit_1` | **surfacing** | `main([...]) == 1`. **It must still fail with the parent heading's `\| N words` stripped**, proving the new detector fired and not T3's dropped-text check. Asserting a `print()` happened does not count. |
| `test_a_visual_note_line_carrying_a_time_range_is_not_a_refused_sub_beat` | **calibration** | A `Hook (0–3s): …` line taken verbatim from `tests/fixtures/script_decline.md:189` produces **no** finding. This is the shape separating a 100%-precision detector from a 98%-false-positive one. |
| `test_the_shipped_fixtures_produce_no_refused_sub_beat_finding` | **calibration** | All four `tests/fixtures/script_*.md` yield zero findings from the new detector, pinning it to real artifacts and honouring §1's "fixtures stay byte-identical" guarantee. |

- [ ] **Run them.** Each must fail with `findings == []` — "no finding emitted". A failure that is an
      `ImportError` or `NameError` is not the RED this task needs; re-derive it.
- [ ] **Implement** in `scripts/lint_script_language.py`:
      - `BUDGET_GROUP_RE = re.compile(r"\([^)\n]*\|\s*\d+\s*words[^)\n]*\)")`, sited beside
        `DECLARED_WORDS_RE` (`:35`), with a comment recording **why the anchor is the budget and not
        the range**: measured identical precision (2/2, zero false positives) and it additionally
        catches `mechanism (11-18 sec | 19 words):`, which a `RANGE_RE and DECLARED_WORDS_RE` anchor
        misses.
      - inside the `if beat is None:` branch, **after** T1's `_disguised_beat_label` check and
        before its `continue`: when `current_label is not None` and `BUDGET_GROUP_RE.search(stripped)`,
        append `Finding("PARSE", current_label, …, kind="fail")` naming the line number, a truncated
        `repr` of the line, and the concrete fix.
      - a `parse_script` docstring paragraph stating the **known limit**: a refused line carrying no
        budget group is not detected here, and T3's dropped-text check is the independent second
        detector for that case. State the limit rather than implying coverage the code lacks.
- [ ] **Add one row to T7's mutation matrix** — an addition to T7, not a contradiction of it:
      `("C88b-label-first-subbeat", '  (10–24s | 20 words): "Kids hand over…', '  mechanism (10–24s | 20 words): "Kids hand over…', "PARSE")`.
      `CLEAN_SCRIPT` has no sub-beat, so add one indented sub-beat under `BUILD/VALUE` — the smaller
      change, and it makes the base representative of real scripts, all four of which have one.
- [ ] **Deliberately NOT in this task:** no new `kind` (`NON_BLOCKING_KINDS` stays `{"skipped",
      "info"}` per T6, so P3's contract is untouched); no exit-code or output-format change; **no
      indentation requirement** — `parse_script` does not look at leading whitespace today and must
      not start, since nothing declares that rule and inventing it would add a second undocumented
      one.
- [ ] **Commit.** `fix(gate-d): a refused sub-beat line blocks instead of vanishing (C-88b)`

---

### T2 — Cross-check the parsed beat set against the five expected labels

**Finding:** C-88 (part 2). T1's heuristic is a heuristic. The independent detector is the one
that cannot be evaded by styling at all: all four shipped fixtures carry all five top-level
labels, so a lint whose parsed set is missing one is either a disguised heading T1 missed or a
genuinely truncated script. Both are worth blocking.

- [ ] **Write the failing test:**

```python
def test_a_missing_top_level_beat_blocks_the_lint():
    """C-88 surfacing test. The second, independent detector: whatever styling
    trick hid the heading, the label is absent from the parsed set and that is
    reported at the gate boundary."""
    text = (
        'HOOK        (0–3s  | 8 words): "Best part was the mud today, honestly."\n'
        'SETUP       (3–8s  | 6 words): "Kids do that every single time."\n'
        'BUILD/VALUE (8–20s | 9 words): "They hand over the whole account without a question."\n'
        'PAYOFF      (20–30s| 9 words): "Ask about the mud and you get him back."\n'
    )
    lines, _ = parse_script(text)
    findings = check_beat_set(lines)
    assert [(f.check, f.kind) for f in findings] == [("PARSE", "fail")]
    assert "LOOP/CTA" in findings[0].message


def test_the_shipped_fixtures_all_carry_the_five_beats():
    """Calibration: the check is pinned to what real scripts actually do."""
    for name in (
        "script_let_kids_play_act.md",
        "script_specialization.md",
        "script_decline.md",
        "script_nobody_asked.md",
    ):
        lines, _ = parse_script(_read(name))
        assert check_beat_set(lines) == [], name
```

- [ ] **Run**, see `ImportError: cannot import name 'check_beat_set'`. Add it to the import block
      at the top of the test file first, re-run, confirm the failure is the missing function.
- [ ] **Implement:**

```python
def check_beat_set(vo_lines: list[VOLine]) -> list[Finding]:
    """Every one of the five top-level beats must have produced a spoken line.

    Independent of `_disguised_beat_label`, deliberately: two detectors with
    different failure modes means an evasion has to beat both. All four shipped
    scripts carry all five labels, so this is calibrated on real artifacts, not
    invented."""
    seen = {vo.beat for vo in vo_lines}
    missing = [label for label in BEAT_LABELS if label not in seen]
    if not missing:
        return []
    return [
        Finding(
            "PARSE",
            None,
            f"no voiceover line parsed for beat(s) {', '.join(missing)} -- either the "
            "script is missing them or their headings did not parse; a gate that never "
            "saw a beat did not check it",
            kind="fail",
        )
    ]
```

and add `*check_beat_set(vo_lines),` to `lint()` immediately after the parse findings.

- [ ] **Run**, see both pass. Then run the full file: `test_main_returns_0_on_a_clean_script`
      (`tests/test_lint_script_language.py:611-618`) now fails — it is a one-beat script. That is
      expected and is amended in T7; leave it red for exactly one task and note it in the commit
      body, or amend it now to use `CLEAN_SCRIPT` from T7 if you sequence T7 first.

      > **P12 execution-order amendment, added during this package's own SDD run (2026-08-15).**
      > This package is being executed in strict numeric task order (T1, T1b, T2, T3, T4, T5, T6,
      > then a gates.py mini-fix, then T7, T8, ...) rather than reordering T7 to run immediately
      > after T2. Under that order, "leave it red for exactly one task" is false — the test would
      > stay red across T3, T4, T5 and T6 as well, four tasks, not one, since none of them touch
      > this test either. The plan's own second option applies instead: **amend it now, in T2's own
      > commit** — but using a small inline fix, not the shared `CLEAN_SCRIPT` module constant,
      > because `CLEAN_SCRIPT` does not exist yet (T7 is the task that introduces it) and defining
      > it early would collide with T7 adding the same name later. T2 should replace the test's
      > one-beat script with a minimal five-beat script (all five `BEAT_LABELS`, each with a valid
      > `| N words` budget so T3's not-yet-landed mandatory-budget rule is moot either way) so the
      > test passes standalone under T2's own change, and rename it to
      > `test_main_returns_0_on_a_clean_five_beat_script` so its name matches what it actually
      > asserts. When T7 lands its shared `CLEAN_SCRIPT` constant, T7's implementer should replace
      > this test's inline script with `CLEAN_SCRIPT` (per the plan's original intent) and may
      > rename it back if desired — that is T7's call, not a re-opening of this amendment.
- [ ] **Commit:** `fix(gate-d): cross-check the parsed beat set against the five labels (C-88)`

---

### T3 — Make the dropped-text check mandatory, not opt-in

**Finding:** C-89. The `| N words` declaration is called "the only independent witness" by the
code's own comment, and it is optional. Strip the annotations and move half the HOOK text outside
its quotes: zero PARSE findings, and the buzzwords, parenthetical and `n=142` planted in the
unquoted tail are all unchecked. A gate the audited artifact can switch off is not a gate.

- [ ] **Write the failing test:**

```python
def test_a_top_level_heading_with_no_word_budget_blocks():
    """C-89 fault test. The dropped-text detector's only witness is the
    heading's own declaration. A heading that omits it disables the detector
    for that beat, so the omission itself must block."""
    text = 'HOOK (0–3s): "Best part was the mud today, honestly."\n'
    _, findings = parse_script(text)
    assert [(f.check, f.beat, f.kind) for f in findings] == [("PARSE", "HOOK", "fail")]
    assert "| N words" in findings[0].message


def test_a_sub_beat_with_a_range_but_no_budget_blocks():
    """The same hole one level down: a sub-beat carrying a time range is
    new-format and must declare its budget."""
    text = (
        "BUILD/VALUE (8–28s | 16 words):\n"
        '  (8–18s): "A position stand reports that samplers reach elite level."\n'
    )
    _, findings = parse_script(text)
    assert any(f.kind == "fail" and "| N words" in f.message for f in findings)


def test_the_old_format_rehook_without_a_range_is_still_exempt():
    """Calibration. `script_let_kids_play_act.md:14` is an old-format re-hook
    with neither a range nor a budget; it is a known, shipped shape and must not
    be broken by this rule. The rule is: a beat line that declares a TIME RANGE
    must also declare a WORD BUDGET."""
    text = (
        'HOOK (0–3s | 8 words): "Best part was the mud today, honestly."\n'
        '[re-hook beat @ ~15s]: "His proof, a trader who bought the presses."\n'
    )
    _, findings = parse_script(text)
    assert findings == []


def test_a_declared_zero_budget_is_distinguishable_from_no_declaration():
    """C-89 distinguishability test. `| 0 words` is an author saying "this beat
    speaks nothing"; omitting the annotation is the detector being switched off.
    They are different states and must produce different results."""
    declared = 'HOOK (0–3s | 0 words): "Mud."\n'
    omitted = 'HOOK (0–3s): "Mud."\n'
    assert parse_script(declared)[1] != parse_script(omitted)[1]
    assert parse_script(declared)[1] == []
```

- [ ] **Run**, see the first two fail with `findings == []`.
- [ ] **Implement** inside `parse_script`, right after `declared` is computed:

```python
        carries_range = RANGE_RE.search(stripped) is not None
        if declared is None and (is_top_level or carries_range):
            findings.append(
                Finding(
                    "PARSE",
                    beat if is_top_level else (current_label or beat),
                    f"beat heading at line {number} declares no `| N words` budget -- the "
                    "dropped-text detector has no independent witness to measure the "
                    "extracted text against, so this beat would be linted on trust",
                    kind="fail",
                )
            )
```

Move the `is_top_level` computation above this block. Update the module docstring comment at
`:32-35` — it currently calls the declaration "the only independent witness" without saying the
witness was optional; it now says it is required and why.

- [ ] **Run** the four new tests, then the whole file. All four shipped fixtures declare
      `| N words` on every top-level heading and on every ranged sub-beat (verified), so
      `test_shipped_fixtures_parse_to_expected_counts` and the rounding-calibration test stay
      green.
- [ ] **Commit:** `fix(gate-d): require the word budget the dropped-text check measures against (C-89)`

---

### T4 — D5: a ratable-fraction floor, and a malformed range blocks

**Finding:** C-90. `skipped` is non-blocking in both callers, and the `rated == 0` backstop only
fires when *nothing* was rated. Deleting the ranges from five of six beats left one rated line,
five non-blocking `skipped` findings, and no pace check — removing information made the gate
weaker. A malformed range (`start >= end`) is a defect, not a known unknown.

Measured calibration (run against the shipped fixtures before you start):
`script_let_kids_play_act.md` 5 of 6 ratable, `script_specialization.md` 5 of 6,
`script_decline.md` 7 of 7, `script_nobody_asked.md` 8 of 8. A floor of **strictly more than
half** clears all four with margin.

- [ ] **Write the failing tests:**

```python
def test_d5_blocks_when_most_beats_are_unratable():
    """C-90 fault test. One rated line among six used to disable the ceiling
    entirely -- and the beats whose ranges an over-stuffed script most benefits
    from deleting are exactly the ones that would have failed."""
    text = (
        'HOOK        (0–3s  | 8 words): "Best part was the mud today, honestly."\n'
        'SETUP       (0:03–0:08 | 6 words): "Kids do that every single time."\n'
        'BUILD/VALUE (0:08–0:20 | 9 words): "They hand over the whole account without a question."\n'
    )
    lines, _ = parse_script(text)
    findings = check_pace(lines)
    assert [f.kind for f in findings] == ["skipped", "skipped", "fail"]
    assert "1 of 3" in findings[-1].message


def test_a_partly_unratable_script_is_distinguishable_from_a_fully_rated_one():
    """C-90 distinguishability test. `skipped`-only used to be indistinguishable
    from clean at the approval boundary: both recorded pass."""
    unratable = 'HOOK (0:00–0:03 | 8 words): "Best part was the mud today, honestly."\n'
    rated = 'HOOK (0–3s | 8 words): "Best part was the mud today, honestly."\n'
    unratable_blocking = [f for f in check_pace(parse_script(unratable)[0]) if is_blocking(f)]
    rated_blocking = [f for f in check_pace(parse_script(rated)[0]) if is_blocking(f)]
    assert unratable_blocking != rated_blocking
    assert rated_blocking == []


def test_d5_treats_a_malformed_range_as_blocking_not_skipped():
    """A range whose start is at or past its end is a defect in the artifact,
    not a known unknown about it."""
    lines, _ = parse_script('HOOK (8–3s | 8 words): "Best part was the mud today, honestly."\n')
    findings = check_pace(lines)
    assert [f.kind for f in findings] == ["fail"]
    assert "start >= end" in findings[0].message


def test_d5_still_tolerates_one_unratable_beat_among_several():
    """The companion guard, strengthened: the two fixtures carrying an
    old-format re-hook are 5-of-6 ratable and must stay non-blocking."""
    for name in ("script_let_kids_play_act.md", "script_specialization.md"):
        lines, _ = parse_script(_read(name))
        findings = check_pace(lines)
        assert any(f.kind == "skipped" for f in findings), name
        assert [f for f in findings if f.beat is None] == [], name
```

- [ ] **Run**, see the first and third fail (`["skipped","skipped","skipped"]`, `["skipped"]`).
- [ ] **Implement** in `check_pace`:

```python
# More than half of the voiceover lines must carry a readable range. The four
# shipped scripts run 5/6, 5/6, 7/7 and 8/8, so this floor clears every real
# artifact with margin while refusing the "delete the ranges you cannot meet"
# evasion: 1 of 6 ratable is not a gate that checked pace.
RATABLE_MIN_FRACTION = 0.5
```

```python
        if wpm is None:
            if vo.start_s is not None and vo.end_s is not None and vo.end_s <= vo.start_s:
                # A nonsensical range is a defect in the artifact. Reporting it
                # `skipped` made removing information the cheapest way past D5.
                findings.append(
                    Finding(
                        "D5",
                        vo.beat,
                        f"line {vo.line_number}: malformed time range "
                        f"({vo.start_s}–{vo.end_s}s, start >= end) -- pace cannot be "
                        "checked and the range itself is wrong",
                        kind="fail",
                    )
                )
                continue
            findings.append(
                Finding(
                    "D5",
                    vo.beat,
                    f"line {vo.line_number}: no computable time range; pace unchecked",
                    kind="skipped",
                )
            )
            continue
```

and replace the `rated == 0` backstop:

```python
    if vo_lines and rated * 2 <= len(vo_lines):
        findings.append(
            Finding(
                "D5",
                None,
                f"only {rated} of {len(vo_lines)} voiceover lines carry a readable time "
                f"range, at or below the {RATABLE_MIN_FRACTION:.0%} floor -- the wpm ceiling "
                "was checked on a minority of this script. Every beat heading needs a "
                "`(<start>–<end>s | N words)` range, e.g. `(0–3s | 8 words)`. A gate that "
                "rated almost nothing is not a gate that passed",
            )
        )
```

- [ ] **Run** the new tests, then the full file. Two existing tests need amendment — see §5.
- [ ] **Commit:** `fix(gate-d): floor the ratable fraction and block malformed ranges (C-90)`

---

### T5 — D6: match the template, don't guess from a pipe; scope out fenced blocks

**Finding:** C-91. `_is_unfilled_placeholder` treats any `|` as proof of an unfilled template, so
`Gate E: 2 findings | 1 defended` — a genuine result in the contract's own vocabulary — false-fails.
Conversely `GATE_E_RE` is an unscoped multiline scan, so `Gate E: pass` inside a code fence
satisfies the lock. The sibling linter's `declares_cover_reuse` is fence-aware; D6 is not.

- [ ] **Write the failing tests:**

```python
def test_d6_accepts_a_pipe_separated_genuine_result():
    """C-91. A result written in the contract's own vocabulary, separated with a
    pipe, is a result. The old heuristic called it a template."""
    assert check_gate_e_reported("  Gate E (critic): 2 findings | 1 defended\n") == []


def test_d6_still_rejects_the_unwrapped_template_text():
    """The heuristic the pipe rule was standing in for: the actual template
    alternation, pasted without its angle brackets."""
    text = "  Gate E (critic): pass | N findings | N defended | overridden: reason\n"
    assert [f.check for f in check_gate_e_reported(text)] == ["D6"]


def test_d6_ignores_a_gate_e_line_inside_a_code_fence():
    """A script quoting the output contract in an example must not thereby
    satisfy the lock -- that is a zero-cost defeat, and the sibling linter
    already scopes its equivalent check to unfenced lines."""
    text = "```\nGate E (critic): pass\n```\n\nsome prose\n"
    assert [f.check for f in check_gate_e_reported(text)] == ["D6"]


def test_d6_accepts_a_real_line_outside_a_fence_alongside_a_fenced_example():
    text = "```\nGate E (critic): <pass | N findings>\n```\n  Gate E (critic): pass\n"
    assert check_gate_e_reported(text) == []
```

- [ ] **Run**, see tests 1 and 3 fail.
- [ ] **Implement:**

```python
# The output contract's own alternation, matched as text rather than inferred
# from the presence of a `|`. A genuine result ("2 findings | 1 defended") may
# contain a pipe; only the template contains this sequence.
TEMPLATE_VALUE_RE = re.compile(
    r"^[<\[]?\s*pass\s*\|\s*N\s+findings\s*\|\s*N\s+defended\s*\|\s*overridden\s*:",
    re.IGNORECASE,
)
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _unfenced(text: str) -> str:
    """`text` with every fenced line blanked, line numbering preserved.

    A `Gate E:` line inside an example fence is documentation, not a report."""
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def _is_unfilled_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER_WRAPPED_RE.match(value)) or bool(TEMPLATE_VALUE_RE.match(value))
```

and in `check_gate_e_reported`, scan `_unfenced(text)`:

```python
    values = [m.group(1).strip() for m in GATE_E_RE.finditer(_unfenced(text))]
```

- [ ] **Run** the new tests, then the whole file. `test_d6_accepts_every_genuinely_filled_shape`,
      `test_d6_rejects_the_unfilled_output_contract_placeholder`,
      `test_d6_rejects_a_bracketed_placeholder_too` and
      `test_the_skill_md_output_contract_placeholder_fails_d6` must all still pass — the wrapped
      forms are still caught by `PLACEHOLDER_WRAPPED_RE`, and the SKILL.md contract still fails
      D6 whether its line is fenced (→ "no well-formed line") or not (→ "placeholder").
- [ ] **Commit:** `fix(gate-d): D6 matches the template text and skips fenced examples (C-91)`

---

### T6 — Disclose D3/D4 coverage, and give `kind` a closed set

**Finding:** C-92. D3 covers 3 phrases and 5 corpus lemmas; D4 covers 4 token classes. That
narrowness is *correct* under the anti-generic guarantee — adding a sixth lemma would be
inventing corpus content. What is wrong is that `Gate D: PASS ... 0 findings.` makes the broad
claim while checking the narrow thing. This task also introduces the `kind` vocabulary P3 binds
to (see §6).

- [ ] **Write the failing tests:**

```python
def test_d3_d4_coverage_scope_is_reported_as_a_non_blocking_finding():
    """C-92. A clean D3/D4 means "none of these eight things", not "no AI
    tells". The gate now says which eight, in a finding both callers render."""
    lines, _ = parse_script('HOOK (0–3s | 6 words): "Best part was the mud today."\n')
    scope = [f for f in check_vocabulary(lines) if f.kind == "info"]
    assert len(scope) == 1
    assert scope[0].check == "D3/D4"
    assert "3 fingerprint phrases" in scope[0].message
    assert "5 corpus lemmas" in scope[0].message
    assert "4 unspeakable token classes" in scope[0].message
    assert not is_blocking(scope[0])


def test_the_non_blocking_kinds_are_a_closed_declared_set():
    """The contract pipeline_app/gates.py binds to (see the P12 plan, §6).
    A new kind must be a deliberate edit here, not an accident downstream."""
    assert NON_BLOCKING_KINDS == frozenset({"skipped", "info"})
    assert is_blocking(Finding("D1", "HOOK", "x")) is True
    assert is_blocking(Finding("D5", "HOOK", "x", kind="skipped")) is False
    assert is_blocking(Finding("PARSE", "HOOK", "x", kind="partial-parse")) is True


def test_buzzword_inflections_are_derived_from_the_five_corpus_lemmas():
    """The lemma count in the scope message must be the real one, not a literal
    typed beside it -- anti-tautology rule: assert on effect, not on echo."""
    assert len(BUZZWORD_LEMMAS) == 5
    assert set(BUZZWORDS) == {form for forms in BUZZWORD_LEMMAS.values() for form in forms}
```

- [ ] **Run**, see `ImportError` for `is_blocking` / `NON_BLOCKING_KINDS` / `BUZZWORD_LEMMAS`.
- [ ] **Implement:**

```python
# `kind` is a closed set. Blocking is the default; a kind is non-blocking only
# by being named here. Both callers (this module's main() and
# pipeline_app.gates.run_script_language_gate) MUST derive blocking from
# is_blocking() rather than testing a literal, so the two cannot drift.
NON_BLOCKING_KINDS = frozenset({"skipped", "info"})


def is_blocking(finding: Finding) -> bool:
    return finding.kind not in NON_BLOCKING_KINDS
```

```python
BUZZWORD_LEMMAS = {
    "delve": ("delving", "delved", "delves", "delve"),
    "leverage": ("leveraging", "leveraged", "leverages", "leverage"),
    "comprehensive": ("comprehensiveness", "comprehensively", "comprehensive"),
    "robust": ("robustness", "robustly", "robust"),
    "holistic": ("holistically", "holistic"),
}
BUZZWORDS = tuple(form for forms in BUZZWORD_LEMMAS.values() for form in forms)
```

(keep the existing comment block above it verbatim — the ordering rationale and the
"no sixth lemma" rule are unchanged), and at the end of `check_vocabulary`:

```python
    findings.append(
        Finding(
            "D3/D4",
            None,
            f"scope: checked {len(FINGERPRINT_PHRASES)} fingerprint phrases, "
            f"{len(BUZZWORD_LEMMAS)} corpus lemmas "
            f"({', '.join(sorted(BUZZWORD_LEMMAS))}) and "
            f"{len(UNSPEAKABLE)} unspeakable token classes. A clean D3/D4 means none of "
            "these, not 'no AI tells' -- the no-lists are the corpus's own and are not "
            "extended by guesswork",
            kind="info",
        )
    )
```

Then rewrite `main()`'s partition to use the predicate, and print the info findings:

```python
    findings = lint(vo_lines, text, parse_findings)
    blocking = [f for f in findings if is_blocking(f)]
    notes = [f for f in findings if not is_blocking(f)]

    for finding in notes:
        marker = "skipped" if finding.kind == "skipped" else "info"
        print(f"  [{marker}] {finding.beat or 'script'}: {finding.message}")
```

- [ ] **Run** the new tests. Then fix the fallout: `test_d3_does_not_flag_a_word_that_merely_contains_a_lemma:360` and `test_d3_does_not_flag_hackfort_the_surname:366` assert `check_vocabulary(lines) == []` and now see the `info` finding — amend both to filter to blocking findings (§5). `test_d3_and_d4_are_clean_on_every_shipped_fixture:383` likewise.
- [ ] **Commit:** `fix(gate-d): report D3/D4 coverage scope and close the kind vocabulary (C-92)`

---

### T7 — The mutation matrix: one evasion at a time, every one must fail

**Findings:** C-88, C-89, C-90, C-91, C-92 (integration). This is the test that proves the gate is
a gate: a known-good script, eleven single-edit evasions, every one blocking.

- [ ] **Write the failing test.** Add the base script and the matrix to
      `tests/test_lint_script_language.py`:

```python
CLEAN_SCRIPT = """\
=== SHORT SCRIPT — Gate D mutation base ===

HOOK        (0–4s  | 9 words): "Nobody asked him what the best part was."
SETUP       (4–10s | 12 words): "He came home muddy, and the whole story arrived without a question."
BUILD/VALUE (10–24s | 20 words): "Kids hand over the account when nothing is riding on the answer, and that is the entire trick."
PAYOFF      (24–34s | 18 words): "Ask about the score and you get a score. Ask about the mud and you get him."
LOOP/CTA    (34–40s | 10 words, mirrors hook): "Ask what the best part was. Then believe it."

GATES
  Gate E (fresh Opus critic): 2 findings, 1 defended
"""


def _run(tmp_path, text, name="script.md"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return main([str(path)])


def test_the_mutation_base_passes_gate_d(tmp_path):
    """The control. If this ever fails, every row below is meaningless."""
    assert _run(tmp_path, CLEAN_SCRIPT) == 0


MUTATIONS = [
    # (id, target substring, replacement, the check that must fire)
    ("D1-em-dash", "arrived without a question.",
     "arrived — without a question.", "D1"),
    ("D2-parenthetical", "you get him.", "you get him (again).", "D2"),
    ("D3-buzzword", "Kids hand over", "Kids leveraged and hand over", "D3"),
    ("D4-inline-stat", "you get a score.", "you get n=142 back.", "D4"),
    ("D5-over-stuffed", "HOOK        (0–4s  | 9 words)",
     "HOOK        (0–1s  | 9 words)", "D5"),
    ("D5-malformed-range", "SETUP       (4–10s | 12 words)",
     "SETUP       (10–4s | 12 words)", "D5"),
    ("D6-deleted", "  Gate E (fresh Opus critic): 2 findings, 1 defended\n", "", "D6"),
    ("D6-fenced", "GATES\n", "GATES\n```\n", "D6"),
    ("C88-bolded-label", "HOOK        (0–4s", "**HOOK**    (0–4s", "PARSE"),
    ("C88-deleted-beat",
     'LOOP/CTA    (34–40s | 10 words, mirrors hook): "Ask what the best part was. Then believe it."\n',
     "", "PARSE"),
    ("C89-stripped-budget", "HOOK        (0–4s  | 9 words)", "HOOK        (0–4s)", "PARSE"),
]


@pytest.mark.parametrize("mutation_id,target,replacement,expected_check", MUTATIONS,
                         ids=[m[0] for m in MUTATIONS])
def test_each_single_edit_evasion_still_fails_the_gate(
    tmp_path, mutation_id, target, replacement, expected_check
):
    """The whole point of Gate D. Each row is ONE edit to a passing script, of
    the kind a model actually emits. Every one must block, and must block for
    the named reason -- a gate that fails for the wrong reason is a gate that
    will be 'fixed' into passing."""
    assert target in CLEAN_SCRIPT, mutation_id
    mutated = CLEAN_SCRIPT.replace(target, replacement, 1)
    assert mutated != CLEAN_SCRIPT, mutation_id

    lines, parse_findings = parse_script(mutated)
    findings = [f for f in lint(lines, mutated, parse_findings) if is_blocking(f)]
    assert findings, mutation_id
    assert expected_check in {f.check for f in findings}, (mutation_id, findings)
    assert _run(tmp_path, mutated) == 1, mutation_id
```

Add `import pytest` to the test file's imports if absent.

- [ ] **Run.** Before T1–T6 land, `C88-bolded-label`, `C88-deleted-beat`, `C89-stripped-budget`,
      `D5-malformed-range` and `D6-fenced` fail. After them, all eleven pass. If you sequence T7
      last, run it once with `git stash` over T1–T6 to observe the red rows — the plan's whole
      premise is that these evasions worked.
- [ ] While here, **amend** `test_main_returns_0_on_a_clean_script`
      (`tests/test_lint_script_language.py:611-618`) to use `CLEAN_SCRIPT` — a one-beat script is
      no longer clean under T2/T3, and that is correct.
- [ ] **Commit:** `test(gate-d): mutation matrix -- eleven single-edit evasions all block`

---

### T8 — Lock the two-caller parity property so it cannot drift

**Context:** `main()` and `pipeline_app.gates.run_script_language_gate` are currently identical in
what they compute. That is a property, not an accident, and nothing tests it. This package can
lock the CLI half and the *shape* of the contract; P3 owns the mirror (see §6).

- [ ] **Write the failing test:**

```python
GATES_PY = (
    Path(__file__).resolve().parents[1]
    / "pipeline-app" / "pipeline_app" / "gates.py"
)


def test_the_cli_exit_code_is_exactly_the_blocking_predicate(tmp_path):
    """Parity, CLI half. main()'s exit code is a pure function of
    is_blocking() over lint()'s output -- no second opinion, no extra rule that
    the app-mode caller would not also apply."""
    cases = [
        CLEAN_SCRIPT,
        CLEAN_SCRIPT.replace("you get him.", "you get him (again)."),
        CLEAN_SCRIPT.replace("HOOK        (0–4s  | 9 words)", "HOOK        (0–4s)"),
        _read("script_decline.md"),
        _read("script_nobody_asked.md"),
    ]
    for i, text in enumerate(cases):
        lines, parse_findings = parse_script(text)
        expected_blocking = [f for f in lint(lines, text, parse_findings) if is_blocking(f)]
        assert _run(tmp_path, text, name=f"case{i}.md") == (1 if expected_blocking else 0), i


def test_gates_py_does_not_hardcode_the_blocking_kind():
    """Parity drift guard. pipeline_app/gates.py (P3's file) must derive
    blocking from the linter's own is_blocking()/NON_BLOCKING_KINDS, not from a
    literal `!= "skipped"`. A literal there silently diverges the moment this
    module adds a kind -- which T6 just did. This test is read-only; the fix
    belongs to P3 (see the P12 plan, §6)."""
    source = GATES_PY.read_text(encoding="utf-8")
    assert '!= "skipped"' not in source, (
        'gates.py still tests a kind literal -- it must use the linter\'s '
        "is_blocking()/NON_BLOCKING_KINDS so the CLI and app gates cannot diverge"
    )
```

- [ ] **Run.** The first passes; the second fails today (`gates.py:167` reads
      `f.get("kind") != "skipped"`). **Do not edit `gates.py`** — it belongs to P3. Mark the
      second test `@pytest.mark.xfail(reason="P3 owns gates.py; see P12 plan §6", strict=True)`
      and record the dependency in the commit body. When P3 lands, the `strict=True` xfail turns
      into an `XPASS` failure, which is the signal to delete the marker. That is deliberate: it
      makes the cross-package handoff loud instead of forgettable.
- [ ] **Commit:** `test(gate-d): lock CLI/app blocking parity and guard against kind-literal drift`

---

### T9 — Three distinct exit codes, and a missing `--dir` is an error

**Findings:** C-96 (S1), C-100. Today exit `1` means both "no prior version" (the normal, expected
answer) and "a brief is malformed" (an unhandled `ValueError`, traceback, no stdout). And
`find_latest` returns `(None, 0)` for a directory that does not exist — so a run from
`pipeline-app/` or a worktree subdirectory confidently proposes `v1` **over a live brief**. That
is the data-loss-adjacent defect in this package.

**Exit-code scheme (this package's contract):**

| Code | Meaning | stdout |
|---|---|---|
| `0` | Resolved, or a next filename proposed | `<path>\t<version>` or `<filename>\t<version>` |
| `3` | NONE — no prior version exists (the expected empty case) | `NONE\t0` |
| `2` | Error — unusable input or an unresolvable state | *(nothing; message on stderr)* |
| `1` | **Retired.** Never returned. | — |

`2` is chosen for errors because argparse already exits `2` on a usage error, so "the operator
gave me something I cannot work with" stays one code. `1` is retired rather than reused so a
stale caller testing `rc == 1` gets a condition that never fires instead of a silent misread —
and the stdout text contract (`NONE\t0`) is unchanged, which is what the ten skills actually
branch on.

- [ ] **Write the failing tests** in `tests/test_resolve_brief_version.py`:

```python
import re
from scripts.resolve_brief_version import (
    EXIT_ERROR, EXIT_NONE, EXIT_OK, find_latest, main, next_filename, parse_frontmatter,
)


def test_find_latest_raises_on_a_directory_that_does_not_exist(tmp_path: Path):
    """C-96 fault test. The wrong CWD used to look exactly like an empty repo."""
    missing = tmp_path / "not-here"
    with pytest.raises(FileNotFoundError) as exc:
        find_latest(missing, "my-short", "script")
    assert str(missing) in str(exc.value)


def test_a_missing_dir_is_distinguishable_from_an_empty_one(tmp_path: Path, capsys):
    """C-96 distinguishability test. This is the whole finding: "no briefs here"
    and "I am looking in the wrong place" must not be the same answer."""
    empty = tmp_path / "rgs-briefs"
    empty.mkdir()
    assert main(["--dir", str(empty), "--slug", "s", "--kind", "script"]) == EXIT_NONE
    assert main(["--dir", str(tmp_path / "gone"), "--slug", "s", "--kind", "script"]) == EXIT_ERROR


def test_a_missing_dir_never_proposes_a_next_filename(tmp_path: Path):
    """The S1 half: `--next` against a missing directory used to return
    `<date>-<slug>-<kind>.md`, version 1 -- the exact name of a live v1 brief."""
    rc = main([
        "--dir", str(tmp_path / "gone"), "--slug", "s", "--kind", "script",
        "--next", "--date", "2026-08-08",
    ])
    assert rc == EXIT_ERROR


def test_the_resolved_absolute_directory_is_echoed_on_every_run(tmp_path: Path, capsys):
    """C-96 surfacing test. The operator can see which directory answered."""
    _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    assert main(["--dir", str(tmp_path), "--slug", "my-short", "--kind", "script"]) == EXIT_OK
    err = capsys.readouterr().err
    assert str(tmp_path.resolve()) in err


def test_a_corrupt_brief_and_no_brief_return_different_codes(tmp_path: Path):
    """C-100 distinguishability test. Both used to exit 1, so a caller that read
    exit 1 as "start at v1" turned a corrupt brief into an overwrite."""
    (tmp_path / "2026-07-28-my-short-script.md").write_text("no frontmatter\n", encoding="utf-8")
    corrupt = main(["--dir", str(tmp_path), "--slug", "my-short", "--kind", "script"])
    empty = main(["--dir", str(tmp_path), "--slug", "other-short", "--kind", "script"])
    assert (corrupt, empty) == (EXIT_ERROR, EXIT_NONE)


def test_exit_code_1_is_never_returned(tmp_path: Path):
    """The retired code. A stale caller testing `rc == 1` must find a condition
    that never fires rather than one that quietly means the wrong thing."""
    (tmp_path / "2026-07-28-bad-script.md").write_text("no frontmatter\n", encoding="utf-8")
    codes = {
        main(["--dir", str(tmp_path), "--slug", "bad", "--kind", "script"]),
        main(["--dir", str(tmp_path), "--slug", "absent", "--kind", "script"]),
        main(["--dir", str(tmp_path / "gone"), "--slug", "absent", "--kind", "script"]),
    }
    assert 1 not in codes


def test_none_still_prints_the_documented_stdout_contract(tmp_path: Path, capsys):
    """Ten skills branch on the printed text, not the code. That contract holds."""
    assert main(["--dir", str(tmp_path), "--slug", "absent", "--kind", "script"]) == EXIT_NONE
    assert capsys.readouterr().out.strip() == "NONE\t0"
```

- [ ] **Run**, see `ImportError` for the exit constants; add them, re-run, see the behavioural
      failures (a missing dir returns `(None, 0)`; both cases return 1).
- [ ] **Implement** in `scripts/resolve_brief_version.py`:

```python
EXIT_OK = 0      # a usable answer was printed
EXIT_ERROR = 2   # unusable input or an unresolvable state (argparse also uses 2)
EXIT_NONE = 3    # the expected empty case: no prior version exists
# Exit 1 is deliberately retired. It used to mean BOTH "no prior version" and
# "a brief is malformed", and callers read it as the former -- which turned a
# corrupt brief into "start at v1". Nothing returns 1 now.
```

```python
def find_latest(directory: Path, slug: str, kind: str | None) -> tuple[Path | None, int]:
    if not directory.is_dir():
        raise FileNotFoundError(
            f"{directory} does not exist or is not a directory -- resolve_brief_version "
            "must be run from the repo root, or given an explicit --dir. Returning "
            '"no prior version" here would propose v1 over a live brief.'
        )
```

```python
def main(argv: list[str] | None = None) -> int:
    ...
    directory = Path(args.dir)
    print(f"resolve_brief_version: reading {directory.resolve()}", file=sys.stderr)

    try:
        if args.next:
            if not args.date:
                parser.error("--next requires --date YYYY-MM-DD")
            filename, version = next_filename(directory, args.slug, args.kind, args.date)
            print(f"{filename}\t{version}")
            return EXIT_OK

        path, version = find_latest(directory, args.slug, args.kind)
    except (FileNotFoundError, ValueError) as exc:
        # Deliberately NOT a bare except: these are the two failure classes this
        # resolver can produce, and each is reported with its own message rather
        # than collapsed into the "nothing found" answer.
        print(f"resolve_brief_version: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if path is None:
        print("NONE\t0")
        return EXIT_NONE
    print(f"{path.as_posix()}\t{version}")
    return EXIT_OK
```

Update the module docstring's Usage block with the exit-code table.

- [ ] **Run.** `test_find_latest_returns_none_when_nothing_matches:30` still passes (tmp_path
      exists). The `Path(args.dir)` default `"rgs-briefs"` stays — it is now safe, because a wrong
      CWD errors instead of answering.
- [ ] **Cross-package note for P13:** `.claude/skills/shorts-scripting/SKILL.md:262` documents
      *"prints `NONE\t0` and exits 1"*. That sentence is now false. P13 owns skill text; record
      this in the P13 handoff. The printed contract the other nine skills branch on is unchanged.
- [ ] **Commit:** `fix(resolve): three distinct exit codes; a missing --dir is an error (C-96, C-100)`

---

### T10 — A version tie is an error, not a coin flip

**Finding:** C-97. `if version > best_version` is strict, so among files declaring the same
frontmatter `version` the first in `sorted(glob)` order wins with no warning. Dates are never
compared. The resolver cannot correctly choose, so it must not guess.

- [ ] **Write the failing tests:**

```python
def test_a_version_tie_raises_and_names_both_paths(tmp_path: Path):
    """C-97 fault test."""
    a = _write(tmp_path, "2026-07-01-my-short-script-v2.md", 2)
    b = _write(tmp_path, "2026-07-28-my-short-script-v2b.md", 2)
    with pytest.raises(ValueError) as exc:
        find_latest(tmp_path, "my-short", "script")
    assert a.name in str(exc.value) and b.name in str(exc.value)


def test_a_tie_is_distinguishable_from_a_clean_resolution(tmp_path: Path):
    """C-97 distinguishability test: the tie used to resolve to the earlier
    date and report success, identical in shape to a correct answer."""
    _write(tmp_path, "2026-07-01-my-short-script-v2.md", 2)
    assert main(["--dir", str(tmp_path), "--slug", "my-short", "--kind", "script"]) == EXIT_OK
    _write(tmp_path, "2026-07-28-my-short-script-v2b.md", 2)
    assert main(["--dir", str(tmp_path), "--slug", "my-short", "--kind", "script"]) == EXIT_ERROR
```

Note the second file is named `-v2b` so it still matches `_pattern`'s optional `-v(\d+)` group
only via the tie in frontmatter — adjust to `2026-07-28-my-short-script-v2.md` in a second
directory if the pattern rejects it; the property under test is the frontmatter tie, not the name.

- [ ] **Run**, see `(path_a, 2)` returned instead of a raise.
- [ ] **Implement** in `find_latest`:

```python
        if version == best_version and best_path is not None:
            raise ValueError(
                f"version tie at {version}: {best_path.name} and {path.name} both declare "
                "it. The resolver cannot choose correctly and will not guess -- renumber "
                "one of them."
            )
        if version > best_version:
```

- [ ] **Run**, see both pass, plus the existing 12 tests.
- [ ] **Commit:** `fix(resolve): a frontmatter version tie is an error naming both briefs (C-97)`

---

### T11 — Cross-check the `-vN` suffix, and refuse a proposal that already exists

**Finding:** C-98 (S1). `_pattern` captures the `-vN` suffix and never uses it, so a file named
`-v3` whose frontmatter says `version: 1` is reported as version 1. `next_filename` then computes
N+1 from frontmatter alone and never tests whether the resulting path exists — verified proposing
`-v2` while `-v3` sat on disk. The supersedes chain every stage depends on regresses in silence.

- [ ] **Write the failing tests:**

```python
def test_a_filename_suffix_that_contradicts_frontmatter_raises(tmp_path: Path):
    """C-98 fault test."""
    _write(tmp_path, "2026-07-28-my-short-script-v3.md", 1)
    with pytest.raises(ValueError) as exc:
        find_latest(tmp_path, "my-short", "script")
    assert "-v3" in str(exc.value) and "version: 1" in str(exc.value)


def test_the_unsuffixed_name_means_version_1(tmp_path: Path):
    """Calibration: `<date>-<slug>-<kind>.md` with no suffix is v1 by contract,
    which is what every shipped brief and every existing test relies on."""
    p = _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    assert find_latest(tmp_path, "my-short", "script") == (p, 1)


def test_next_filename_refuses_a_proposal_that_already_exists(tmp_path: Path):
    """C-98's second half. Proposing an existing brief's name is one careless
    Write away from destroying it."""
    _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    _write(tmp_path, "2026-07-28-my-short-script-v3.md", 3)
    # v3's frontmatter now agrees with its name, so resolution succeeds at 3 and
    # the proposal is -v4; plant that file to force the collision.
    _write(tmp_path, "2026-07-28-my-short-script-v4.md", 4)
    with pytest.raises(FileExistsError) as exc:
        next_filename(tmp_path, "my-short", "script", "2026-07-28")
    assert "v5" in str(exc.value) or "already exists" in str(exc.value)


def test_a_collision_and_a_clean_proposal_are_distinguishable(tmp_path: Path):
    """C-98 distinguishability + surfacing test: the collision exits 2 where the
    clean proposal exits 0."""
    _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    args = ["--dir", str(tmp_path), "--slug", "my-short", "--kind", "script",
            "--next", "--date", "2026-07-28"]
    assert main(args) == EXIT_OK
    (tmp_path / "2026-07-28-my-short-script-v2.md").write_text(
        "---\nversion: 2\n---\n\nbody\n", encoding="utf-8")
    assert main(args) == EXIT_ERROR
```

Note the collision path in the last test arises because v2 now resolves and the proposal becomes
v3 — adjust the planted file to `-v3.md` with `version: 2` frontmatter if you want the pure
collision; either way the assertion is *clean → 0, colliding → 2*.

- [ ] **Run**, see the first return `(path, 1)` and the third return a filename.
- [ ] **Implement** in `find_latest`, using the pattern's already-captured group:

```python
        match = pattern.match(path.name)
        if not match:
            continue
        ...
        suffix_version = int(match.group(2)) if match.group(2) else 1
        if suffix_version != version:
            raise ValueError(
                f"{path}: filename says -v{suffix_version} but frontmatter says "
                f"version: {version}. The version chain is what every stage's "
                "`supersedes:` line depends on; it cannot be two numbers."
            )
```

and in `next_filename`:

```python
    filename = f"{date}-{slug}{suffix}{version_suffix}.md"
    proposed = directory / filename
    if proposed.exists():
        raise FileExistsError(
            f"{proposed} already exists -- refusing to propose a name that would "
            "overwrite a brief. The version chain has drifted; resolve it by hand."
        )
    return filename, next_version
```

`main()` already maps `ValueError` to `EXIT_ERROR` (T9); add `FileExistsError` to that
`except` tuple.

- [ ] **Run** the new tests and the full file.
- [ ] **Commit:** `fix(resolve): cross-check the -vN suffix and refuse a colliding proposal (C-98)`

---

### T12 — Validate `--date` against the resolver's own pattern

**Finding:** C-99. `--date banana` returned `banana-do-less-sold-as-win-more-assembly-v4.md` with
exit 0. A brief written under that name can never be found by `find_latest` again, so it drops
out of the version chain permanently and the next `--next` re-proposes a colliding number.

- [ ] **Write the failing tests:**

```python
def test_a_malformed_date_is_rejected(tmp_path: Path):
    """C-99 fault test. The resolver's own _pattern requires \\d{4}-\\d{2}-\\d{2};
    next_filename used to interpolate whatever it was handed."""
    rc = main(["--dir", str(tmp_path), "--slug", "s", "--kind", "script",
               "--next", "--date", "banana"])
    assert rc == EXIT_ERROR


def test_a_malformed_date_is_distinguishable_from_a_valid_one(tmp_path: Path, capsys):
    """C-99 distinguishability test."""
    ok = main(["--dir", str(tmp_path), "--slug", "s", "--kind", "script",
               "--next", "--date", "2026-08-08"])
    out = capsys.readouterr().out
    assert (ok, out.strip()) == (EXIT_OK, "2026-08-08-s-script.md\t1")
    bad = main(["--dir", str(tmp_path), "--slug", "s", "--kind", "script",
                "--next", "--date", "08/08/2026"])
    assert bad == EXIT_ERROR


def test_a_proposed_filename_always_matches_the_pattern_that_finds_it(tmp_path: Path):
    """The invariant behind C-99: anything --next proposes must be findable by
    find_latest afterwards, or the chain breaks permanently."""
    filename, _ = next_filename(tmp_path, "my-short", "script", "2026-08-08")
    from scripts.resolve_brief_version import _pattern
    assert _pattern("my-short", "script").match(filename)
```

- [ ] **Run**, see the malformed dates return `EXIT_OK` with a nonsense filename.
- [ ] **Implement:**

```python
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
```

in `next_filename`, before anything else:

```python
    if not DATE_RE.match(date):
        raise ValueError(
            f"--date {date!r} is not YYYY-MM-DD. A brief named with anything else can "
            "never be found by find_latest again -- it leaves the version chain for good."
        )
```

- [ ] **Run** all three, plus the full file.
- [ ] **Commit:** `fix(resolve): validate --date against the pattern that finds the file (C-99)`

---

### T13 — Cover the CLI surface: `resolve_brief_version.py:68-91`

**Finding:** F-23. 64% coverage, the worst in either suite, and the uncovered block is the entire
CLI: 24 consecutive statements. Eleven of the 12 existing tests call the helpers directly; the
twelfth shells out only to check path separators. T9–T12 added in-process `main()` tests; this
task adds the *process-boundary* tests, because the exit code is what the ten skills read and an
in-process `main()` return does not prove `sys.exit(main())` wires it.

- [ ] **Write the failing test:**

```python
def _cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "scripts.resolve_brief_version", *args],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


@pytest.mark.allow_subprocess
def test_cli_exit_codes_reach_the_shell(tmp_path: Path):
    """F-23 surfacing test. The skills read $? , not a Python return value."""
    _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    ok = _cli(tmp_path, "--dir", str(tmp_path), "--slug", "my-short", "--kind", "script")
    none = _cli(tmp_path, "--dir", str(tmp_path), "--slug", "absent", "--kind", "script")
    gone = _cli(tmp_path, "--dir", str(tmp_path / "gone"), "--slug", "absent", "--kind", "script")
    assert (ok.returncode, none.returncode, gone.returncode) == (0, 3, 2)
    assert none.stdout.strip() == "NONE\t0"
    assert gone.stdout.strip() == ""
    assert "does not exist" in gone.stderr


@pytest.mark.allow_subprocess
def test_cli_reports_a_corrupt_brief_on_stderr_without_a_traceback(tmp_path: Path):
    """C-100's other half: exit 1 used to carry a raw traceback and no stdout."""
    (tmp_path / "2026-07-28-my-short-script.md").write_text("no frontmatter\n", encoding="utf-8")
    result = _cli(tmp_path, "--dir", str(tmp_path), "--slug", "my-short", "--kind", "script")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "no frontmatter block found" in result.stderr
```

- [ ] **Add `@pytest.mark.allow_subprocess`** to the existing
      `test_cli_prints_forward_slash_path` (`tests/test_resolve_brief_version.py:83-109`) — P0's
      autouse conftest guard raises on `subprocess.run` without it — and change its
      `text=True` to `encoding="utf-8", errors="replace"` per Global Constraints (finding B-10).
      Its `check=True` still holds: exit 0 is the resolved case.
- [ ] **Run**, then measure: `python -m pytest tests/test_resolve_brief_version.py
      --cov=scripts.resolve_brief_version --cov-report=term-missing`. The `:68-91` block must show
      no uncovered lines. Coverage is not the bar (Global Constraints), but the *named* uncovered
      block is this finding, so its disappearance is the evidence.
- [ ] **Commit:** `test(resolve): cover the CLI surface at the process boundary (F-23)`

---

### T14 — Pin the mitigation C-96 leans on

**Finding:** C-96 (surfacing half). The audit's blast radius says *"The `.claude/hooks/protect_briefs.py`
Write-deny hook mitigates the overwrite inside Claude Code"*. That mitigation is load-bearing for an
S1 finding and only its `decide()` helper is tested — `main()`, which does the payload parsing,
the `CLAUDE_PROJECT_DIR` resolution and the exit-2 signal, has no test at all.

- [ ] **Write the failing tests** in `tests/test_protect_briefs.py`:

```python
import io
import json


def _hook(monkeypatch, tmp_path, tool_name, file_path) -> int:
    payload = {"tool_name": tool_name, "tool_input": {"file_path": str(file_path)}}
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return protect_briefs.main()


def test_hook_main_denies_a_write_over_an_existing_brief(monkeypatch, tmp_path, capsys):
    """C-96 surfacing test. This hook is the only thing standing between a
    wrong-CWD v1 proposal and a destroyed brief; the deny path must be proven
    end to end, not just in its helper."""
    briefs = tmp_path / "rgs-briefs"
    briefs.mkdir()
    target = briefs / "2026-07-28-my-short-script.md"
    target.write_text("the live brief\n", encoding="utf-8")
    assert _hook(monkeypatch, tmp_path, "Write", target) == 2
    assert "never overwritten" in capsys.readouterr().err


def test_hook_main_accepts_a_relative_path_the_way_the_tool_sends_it(monkeypatch, tmp_path):
    """The wrong-CWD scenario produces a project-relative path. main() resolves
    it against CLAUDE_PROJECT_DIR; if that ever regressed, the mitigation would
    silently stop applying to exactly the case C-96 describes."""
    briefs = tmp_path / "rgs-briefs"
    briefs.mkdir()
    (briefs / "2026-07-28-my-short-script.md").write_text("live\n", encoding="utf-8")
    assert _hook(monkeypatch, tmp_path, "Write",
                 Path("rgs-briefs/2026-07-28-my-short-script.md")) == 2


def test_hook_main_allows_a_genuinely_new_version(monkeypatch, tmp_path):
    """Distinguishability: denying everything would be a different bug."""
    (tmp_path / "rgs-briefs").mkdir()
    assert _hook(monkeypatch, tmp_path, "Write",
                 tmp_path / "rgs-briefs" / "2026-07-28-my-short-script-v2.md") == 0
```

- [ ] **Run**, confirm each fails first for the right reason (they exercise a path with zero
      existing coverage; if one passes immediately, check you actually monkeypatched `sys.stdin`).
- [ ] **Commit:** `test(hooks): prove the rgs-briefs write-deny mitigation end to end (C-96)`

---

### T15 — The plugin ships eight + three, and says so

**Finding:** C-101. `.claude/skills/` holds 13 trees; the script removes 2, shipping 11 = 8
pipeline + 3 specialists. Three strings say "Seven", and the bundled README omits
`shorts-styleboard` from the chain entirely — the stage that produces the world lock Gate C reads.
The shipped documentation describes a pipeline in which Gate C's primary input has no origin.

- [ ] **Write the failing test** in the new `tests/test_build_cowork_plugin.py`:

```python
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "build-cowork-plugin.sh"
EXCLUDED = {"rgs-grounding", "rgs-pairing-review"}


def _skill_dirs() -> set[str]:
    return {p.name for p in (REPO / ".claude" / "skills").iterdir() if p.is_dir()}


def test_the_script_never_calls_the_pipeline_seven_skills():
    """C-101. Three strings said "Seven" while eleven skills shipped."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert not re.search(r"\bseven\b", source, re.IGNORECASE), (
        "build-cowork-plugin.sh still says 'seven'; it ships eight pipeline skills "
        "plus three tool specialists"
    )


def test_the_bundled_readme_chain_names_shorts_styleboard():
    """shorts-styleboard produces the world lock Gate C reads. A chain that
    omits it documents a pipeline whose gate has no input."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "shorts-styleboard" in source


def test_the_expected_shipped_roster_is_exactly_the_tree_minus_the_rgs_skills():
    """Anti-tautology: derived from the real directory, not a literal count."""
    shipped = _skill_dirs() - EXCLUDED
    assert len(shipped) == 11
    assert "shorts-styleboard" in shipped
    assert EXCLUDED & shipped == set()
```

- [ ] **Run**, see the first two fail.
- [ ] **Implement** in `scripts/build-cowork-plugin.sh`: rewrite the header comment
      (`:2-4`), the `plugin.json` `description` (`:34`) and the README body (`:42-43`) to
      *"Eight atomic, corpus-grounded skills … plus three tool-specialist skills"*, and fix the
      README chain to:

```
shorts-ideation -> shorts-scripting -> shorts-styleboard -> {voiceover-brief, visual-prompts}
  -> music-brief -> shorts-assembly -> social-repurpose
```

- [ ] **Run**, see all three pass.
- [ ] **Commit:** `fix(plugin): the bundle ships eight pipeline skills plus three specialists (C-101)`

---

### T16 — Derive the version, assert the roster, validate the JSON, fail loud on a bad copy

**Finding:** C-102. Every build writes `"version": "0.1.0"`, so an installed plugin cannot be told
from one made months and many skill edits ago. Nothing validates the manifest, and the only
post-copy verification is a skill count printed in the closing `echo` and never compared to
anything — a build that copied 9 skills reports success as loudly as one that copied 11.

- [ ] **Write the failing tests:**

```python
def test_the_manifest_version_is_derived_not_pinned():
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"version": "0.1.0"' not in source
    assert "git rev-list" in source or "date -u" in source


def test_the_build_asserts_the_copied_roster_before_packaging():
    """C-102 fault test, at the source level: the count must be COMPARED, not
    merely printed. A build that copied nine skills must fail, not congratulate
    itself."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "cowork_plugin_lock.py" in source
    assert "--check" in source or "--write" in source


def test_the_written_manifest_is_validated_as_json():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "json.load" in source or "json.tool" in source
```

Plus the behavioural test, which runs the real build:

```python
@pytest.mark.allow_subprocess
def test_the_build_produces_a_valid_manifest_and_the_expected_roster(tmp_path):
    """C-102 surfacing test: run the actual script and inspect what it wrote."""
    result = subprocess.run(
        ["bash", str(SCRIPT)], cwd=REPO, capture_output=True,
        encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads(
        (REPO / "cowork-plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert manifest["name"] == "content-studio"
    assert manifest["version"] != "0.1.0"
    shipped = {p.name for p in (REPO / "cowork-plugin" / "skills").iterdir() if p.is_dir()}
    assert shipped == _skill_dirs() - EXCLUDED
```

- [ ] **Run**, see the source-level tests fail.
- [ ] **Implement** in `scripts/build-cowork-plugin.sh`:

```bash
# The version must distinguish today's build from one made months and many skill
# edits ago. Commit count is monotonic and needs no tag discipline; the short sha
# makes the build identifiable in a bug report.
COMMIT_COUNT="$(git rev-list --count HEAD)"
SHORT_SHA="$(git rev-parse --short HEAD)"
VERSION="0.1.${COMMIT_COUNT}+g${SHORT_SHA}"

cat > "$PLUGIN_DIR/.claude-plugin/plugin.json" <<JSON
{
  "name": "content-studio",
  "version": "${VERSION}",
  "description": "Eight atomic, corpus-grounded skills taking a faceless-YouTube-Shorts idea from concept through a produced Short to multi-surface post copy, plus three tool-specialist skills (Midjourney V8.2 prompting, ElevenLabs audio, ElevenLabs Music) usable standalone or as pipeline downstreams.",
  "author": { "name": "ContentStudio" }
}
JSON

# The heredoc is no longer quoted (it interpolates $VERSION), so it can no
# longer be assumed well-formed. Validate before anything is packaged.
python -c "import json,sys; json.load(open(sys.argv[1], encoding='utf-8'))" \
  "$PLUGIN_DIR/.claude-plugin/plugin.json"

# Assert what was actually copied against .claude/skills/ minus the two
# deliberately-excluded RGS skills, and write the tracked build stamp.
python scripts/cowork_plugin_lock.py --write --plugin-dir "$PLUGIN_DIR"
```

`cp -R` failure is already fatal under `set -euo pipefail` (verified at `:16`); add a comment
saying so rather than an unnecessary check, and drop the unverified skill count from the closing
`echo` in favour of the roster the lock file now records.

- [ ] **Run.** The behavioural test needs `bash` (present on the target platform via Git Bash and
      on `windows-latest` runners) and `@pytest.mark.allow_subprocess`.
- [ ] **Commit:** `fix(plugin): derive the version, validate the manifest, assert the roster (C-102)`

---

### T17 — A tracked build stamp makes a stale plugin detectable

**Finding:** C-103. `cowork-plugin/` and `dist/` are git-ignored, there is no CI running the build,
and the only references to the script are prose in `CLAUDE.md`. A Cowork user can be running
skills several revisions behind the repo with nothing anywhere reporting it — and the Gate C/D
rules those skills instruct are exactly the content that goes stale.

The fix is a **tracked** stamp, because the artifact itself cannot be tracked. One algorithm,
written by the build and checked by the test, so the two cannot diverge.

- [ ] **Write the failing test:**

```python
LOCK = REPO / "scripts" / "cowork-plugin.lock.json"


def test_the_lock_file_matches_the_current_skills_tree():
    """C-103 fault test. Editing a skill without rebuilding the plugin used to
    be undetectable. Now it fails here, with the one command that fixes it."""
    from scripts.cowork_plugin_lock import compute_stamp

    assert LOCK.exists(), "run: bash scripts/build-cowork-plugin.sh"
    recorded = json.loads(LOCK.read_text(encoding="utf-8"))
    assert recorded == compute_stamp(REPO), (
        "the shipped plugin is stale relative to .claude/skills/ -- "
        "run: bash scripts/build-cowork-plugin.sh"
    )


def test_a_changed_skill_changes_the_stamp(tmp_path):
    """C-103 distinguishability test. A stamp that did not move when a skill
    moved would be a stamp that certifies nothing."""
    from scripts.cowork_plugin_lock import compute_stamp

    fake = tmp_path / ".claude" / "skills" / "demo"
    fake.mkdir(parents=True)
    (fake / "SKILL.md").write_text("one\n", encoding="utf-8")
    before = compute_stamp(tmp_path)
    (fake / "SKILL.md").write_text("two\n", encoding="utf-8")
    assert compute_stamp(tmp_path) != before


def test_a_locally_built_artifact_is_not_older_than_the_skills_it_ships():
    """The mtime half, for the machine that actually has the artifact. dist/ is
    git-ignored, so this is a no-op in CI and a real check locally -- stated
    plainly rather than dressed up as universal coverage."""
    artifact = REPO / "dist" / "content-studio.plugin"
    if not artifact.exists():
        pytest.skip("no local build artifact; the lock-file check above is the CI gate")
    newest = max(
        p.stat().st_mtime for p in (REPO / ".claude" / "skills").rglob("*") if p.is_file()
    )
    assert artifact.stat().st_mtime >= newest, "run: bash scripts/build-cowork-plugin.sh"
```

- [ ] **Run**, see `ModuleNotFoundError: scripts.cowork_plugin_lock`.
- [ ] **Implement `scripts/cowork_plugin_lock.py`** (stdlib only):

```python
#!/usr/bin/env python3
"""The Cowork plugin's tracked build stamp.

`cowork-plugin/` and `dist/` are git-ignored, so the shipped artifact cannot be
version-tracked and no diff can show that `.claude/skills/` has moved on since
the last build. This file is the tracked witness: a sorted roster plus a content
hash of exactly the tree the plugin ships. The build writes it; the repo-root
test recomputes and compares. One algorithm, two callers, so they cannot drift.

Stdlib only -- scripts/ never imports app code."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

EXCLUDED_SKILLS = ("rgs-grounding", "rgs-pairing-review")
LOCK_PATH = Path("scripts/cowork-plugin.lock.json")


def shipped_skills(repo: Path) -> list[str]:
    root = repo / ".claude" / "skills"
    return sorted(
        p.name for p in root.iterdir() if p.is_dir() and p.name not in EXCLUDED_SKILLS
    )


def compute_stamp(repo: Path) -> dict:
    root = repo / ".claude" / "skills"
    digest = hashlib.sha256()
    for name in shipped_skills(repo):
        for path in sorted((root / name).rglob("*")):
            if not path.is_file():
                continue
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return {
        "skills": shipped_skills(repo),
        "excluded": list(EXCLUDED_SKILLS),
        "sha256": digest.hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--plugin-dir", default=None)
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parents[1]
    stamp = compute_stamp(repo)

    if args.plugin_dir:
        copied = sorted(
            p.name for p in (repo / args.plugin_dir / "skills").iterdir() if p.is_dir()
        )
        if copied != stamp["skills"]:
            print(
                f"copied roster {copied} != expected {stamp['skills']} -- the plugin "
                "tree is not what .claude/skills/ says it should be",
                file=sys.stderr,
            )
            return 1

    lock = repo / LOCK_PATH
    if args.check:
        if not lock.exists() or json.loads(lock.read_text(encoding="utf-8")) != stamp:
            print("plugin lock is stale -- run: bash scripts/build-cowork-plugin.sh",
                  file=sys.stderr)
            return 1
        return 0

    if args.write:
        lock.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Run**, then run `bash scripts/build-cowork-plugin.sh` once to generate the lock, and
      commit the lock file. Confirm `.gitignore`'s `cowork-plugin/` pattern (a directory pattern)
      does **not** match `scripts/cowork-plugin.lock.json` — `git status` must show it as
      untracked-then-staged, not ignored.
- [ ] **Cross-package note:** from now on, any commit that edits `.claude/skills/**` must re-run
      the build so the lock moves with it. That cost is the finding: it is what makes a stale
      plugin detectable. Flag it to **P13** (48 findings across 22 skill files) and **P14**.
- [ ] **Commit:** `feat(plugin): tracked build stamp makes a stale plugin fail the suite (C-103)`

---

### T18 — Both archive branches package one already-clean tree

**Finding:** C-104. The `zip` branch excludes `*.DS_Store`; the PowerShell `Compress-Archive`
branch has no exclusion, so the same source tree yields two different archives depending on the
machine — and `zip` is *not* installed on this operator's machine, so the unexcluded branch is the
live one here.

- [ ] **Write the failing test:**

```python
def test_junk_is_pruned_before_packaging_not_during():
    """C-104. Two branches with two different exclusion rules produce two
    different artifacts from one tree. Prune once, up front, and both branches
    archive the same thing."""
    source = SCRIPT.read_text(encoding="utf-8")
    prune_at = source.index("find") if "find" in source else -1
    zip_at = source.index("Compress-Archive")
    assert re.search(r'-name\s+["\']?\.DS_Store', source), (
        "no pre-packaging prune step; the two archive branches still disagree"
    )
    assert 0 < prune_at < zip_at
    assert '-x "*.DS_Store"' not in source, (
        "the zip branch still carries a branch-local exclusion -- the rule must "
        "live in one place, before either branch runs"
    )


@pytest.mark.allow_subprocess
def test_the_packaged_tree_contains_no_junk_files(tmp_path):
    subprocess.run(["bash", str(SCRIPT)], cwd=REPO, check=True,
                   capture_output=True, encoding="utf-8", errors="replace")
    junk = [p for p in (REPO / "cowork-plugin").rglob("*")
            if p.name in (".DS_Store", "Thumbs.db") or p.suffix == ".pyc"]
    assert junk == []
```

- [ ] **Run**, see the source assertions fail.
- [ ] **Implement** in `scripts/build-cowork-plugin.sh`, immediately after the `rm -rf` of the two
      RGS skills and **before** either archive branch:

```bash
# Prune junk from the copied tree once, so both archive branches package an
# identical, already-clean directory. Putting the rule in the `zip` branch alone
# meant the same source produced two different artifacts depending on which
# packaging tool the machine happened to have.
find "$PLUGIN_DIR" \( -name '.DS_Store' -o -name 'Thumbs.db' -o -name '__pycache__' \) \
  -prune -exec rm -rf {} +
```

and drop `-x "*.DS_Store"` from the `zip` invocation.

- [ ] **Run** both tests.
- [ ] **Commit:** `fix(plugin): prune junk before packaging so both branches agree (C-104)`

---

## 4. Finding → test map

Three-Test-Rule roles are given for every `failure_mode: silent` finding (10 of the 15).

| Finding | Silent? | Named test(s) | Role |
|---|---|---|---|
| **C-88** | yes | `test_a_bolded_beat_label_is_a_blocking_parse_finding` | fault |
| | | `test_a_disguised_heading_is_distinguishable_from_a_script_that_omits_it` | distinguishability |
| | | `test_a_missing_top_level_beat_blocks_the_lint` | surfacing (exit 1 via `check_beat_set` in `lint`) |
| | | `test_each_single_edit_evasion_still_fails_the_gate[C88-bolded-label]`, `[C88-deleted-beat]` | integration |
| | | `test_prose_that_merely_mentions_a_beat_label_is_not_a_disguised_heading`, `test_the_shipped_fixtures_all_carry_the_five_beats` | calibration (anti-false-positive) |
| **C-89** | yes | `test_a_top_level_heading_with_no_word_budget_blocks`, `test_a_sub_beat_with_a_range_but_no_budget_blocks` | fault |
| | | `test_a_declared_zero_budget_is_distinguishable_from_no_declaration` | distinguishability |
| | | `test_each_single_edit_evasion_still_fails_the_gate[C89-stripped-budget]` | surfacing (non-zero exit) |
| | | `test_the_old_format_rehook_without_a_range_is_still_exempt` | calibration |
| **C-90** | yes | `test_d5_blocks_when_most_beats_are_unratable`, `test_d5_treats_a_malformed_range_as_blocking_not_skipped` | fault |
| | | `test_a_partly_unratable_script_is_distinguishable_from_a_fully_rated_one` | distinguishability |
| | | `test_each_single_edit_evasion_still_fails_the_gate[D5-malformed-range]` | surfacing (non-zero exit) |
| | | `test_d5_still_tolerates_one_unratable_beat_among_several` | calibration |
| **C-91** | no (loud) | `test_d6_accepts_a_pipe_separated_genuine_result`, `test_d6_still_rejects_the_unwrapped_template_text`, `test_d6_ignores_a_gate_e_line_inside_a_code_fence`, `test_d6_accepts_a_real_line_outside_a_fence_alongside_a_fenced_example` | — |
| **C-92** | no (coverage-gap) | `test_d3_d4_coverage_scope_is_reported_as_a_non_blocking_finding`, `test_buzzword_inflections_are_derived_from_the_five_corpus_lemmas`, `test_the_non_blocking_kinds_are_a_closed_declared_set` | — |
| **C-96** | yes | `test_find_latest_raises_on_a_directory_that_does_not_exist`, `test_a_missing_dir_never_proposes_a_next_filename` | fault |
| | | `test_a_missing_dir_is_distinguishable_from_an_empty_one` | distinguishability |
| | | `test_the_resolved_absolute_directory_is_echoed_on_every_run`, `test_hook_main_denies_a_write_over_an_existing_brief`, `test_hook_main_accepts_a_relative_path_the_way_the_tool_sends_it` | surfacing |
| **C-97** | yes | `test_a_version_tie_raises_and_names_both_paths` | fault |
| | | `test_a_tie_is_distinguishable_from_a_clean_resolution` | distinguishability + surfacing (exit 2) |
| **C-98** | yes | `test_a_filename_suffix_that_contradicts_frontmatter_raises`, `test_next_filename_refuses_a_proposal_that_already_exists` | fault |
| | | `test_a_collision_and_a_clean_proposal_are_distinguishable` | distinguishability + surfacing (exit 2) |
| | | `test_the_unsuffixed_name_means_version_1` | calibration |
| **C-99** | yes | `test_a_malformed_date_is_rejected` | fault |
| | | `test_a_malformed_date_is_distinguishable_from_a_valid_one` | distinguishability |
| | | `test_a_proposed_filename_always_matches_the_pattern_that_finds_it` | surfacing (invariant) |
| **C-100** | yes | `test_a_corrupt_brief_and_no_brief_return_different_codes` | fault + distinguishability |
| | | `test_cli_reports_a_corrupt_brief_on_stderr_without_a_traceback`, `test_exit_code_1_is_never_returned`, `test_none_still_prints_the_documented_stdout_contract` | surfacing |
| **C-101** | no (docs-drift) | `test_the_script_never_calls_the_pipeline_seven_skills`, `test_the_bundled_readme_chain_names_shorts_styleboard`, `test_the_expected_shipped_roster_is_exactly_the_tree_minus_the_rgs_skills` | — |
| **C-102** | yes | `test_the_build_asserts_the_copied_roster_before_packaging`, `test_the_manifest_version_is_derived_not_pinned`, `test_the_written_manifest_is_validated_as_json` | fault |
| | | `test_the_build_produces_a_valid_manifest_and_the_expected_roster` | distinguishability + surfacing (non-zero build exit) |
| **C-103** | yes | `test_the_lock_file_matches_the_current_skills_tree` | fault |
| | | `test_a_changed_skill_changes_the_stamp` | distinguishability |
| | | `test_a_locally_built_artifact_is_not_older_than_the_skills_it_ships` | surfacing |
| **C-104** | no (latent) | `test_junk_is_pruned_before_packaging_not_during`, `test_the_packaged_tree_contains_no_junk_files` | — |
| **F-23** | no (coverage-gap) | `test_cli_exit_codes_reach_the_shell`, `test_cli_reports_a_corrupt_brief_on_stderr_without_a_traceback` (+ every `main()` test in T9–T12) | — |

---

## 5. Tests deleted, inverted or amended

No test in these files asserts a defect is *correct*, so none is deleted outright. Four are
amended, one is inverted, and one is added as its companion — each by file:line.

| File:line | Test | Action | Why |
|---|---|---|---|
| `tests/test_lint_script_language.py:621-633` | `test_main_returns_0_when_only_finding_is_skipped` | **Inverted** | It froze "a `skipped`-only script exits 0" — the exact property C-90 exploits. Its script is 2 VO lines, 1 rated. Rename to `test_main_returns_0_when_a_minority_of_beats_are_skipped` and give it 4 VO lines with 3 rated (still non-blocking, still the real property worth keeping: one unratable beat is a known unknown). |
| *(new, same file)* | `test_main_returns_1_when_most_beats_are_unratable` | **Added companion** | The inversion's other half: 1 rated of 4 must exit 1. Without it, the amendment would just move the threshold without pinning it. |
| `tests/test_lint_script_language.py:434-445` | `test_d5_skips_a_beat_with_no_range_and_says_so` | **Amended** | 2 VO lines / 1 rated now also trips the ratable-fraction floor, so `[f.kind for f in findings] == ["skipped"]` fails. Add a third ranged beat so the script is 2-of-3 ratable; the per-beat `skipped` semantics it actually tests are unchanged. |
| `tests/test_lint_script_language.py:611-618` | `test_main_returns_0_on_a_clean_script` | **Amended** | Its one-beat script is no longer clean under T2 (five-label cross-check). Replace the inline text with `CLEAN_SCRIPT` from T7 — which is the honest "clean" artifact and is now shared by the whole mutation matrix. |
| `tests/test_lint_script_language.py:360-364`, `:366-369`, `:383-392` | `test_d3_does_not_flag_a_word_that_merely_contains_a_lemma`, `test_d3_does_not_flag_hackfort_the_surname`, `test_d3_and_d4_are_clean_on_every_shipped_fixture` | **Amended** | They assert `check_vocabulary(lines) == []`; T6 adds a non-blocking `info` scope finding. Change each to filter with `is_blocking` — which is a stricter assertion, not a looser one, because it names *why* the remaining finding is acceptable. |
| `tests/test_resolve_brief_version.py:83-109` | `test_cli_prints_forward_slash_path` | **Amended** | Add `@pytest.mark.allow_subprocess` (P0's autouse guard) and replace `text=True` with `encoding="utf-8", errors="replace"` (Global Constraints / finding B-10). Assertions unchanged. |

`tests/test_lint_script_language.py:466-474`
(`test_d5_does_not_block_when_one_beat_among_several_is_unratable`) is **kept and strengthened**,
not inverted: 5-of-6 ratable must stay non-blocking, and that is now the floor's calibration case.
T4 renames it `test_d5_still_tolerates_one_unratable_beat_among_several` and keeps its assertions.

---

## 6. Contract for P3 (`pipeline-app/pipeline_app/gates.py`)

This package does not edit `gates.py`. Two properties must hold on P3's side; T8 leaves a
`strict=True` xfail in the root suite that turns into a loud `XPASS` failure the moment the first
one lands, so the handoff cannot be forgotten.

### 6.1 `skipped` is no longer the only non-blocking kind

`run_gates_for_stage` currently computes, at `gates.py:167`:

```python
blocking = [f for f in findings if f.get("kind") != "skipped"]
```

Gate D's `kind` vocabulary is now a **closed, declared set** owned by the linter:

| kind | Blocking | Meaning |
|---|---|---|
| `fail` | yes | a rule was violated |
| `partial-parse` | yes | the parser is linting less text than the artifact contains |
| `skipped` | **no** | a known unknown (a beat with no computable range) |
| `info` | **no** | disclosure, not judgment (D3/D4 coverage scope, T6) |

**Required of P3:** derive blocking from the linter's own predicate rather than a literal, so a
new kind cannot silently become blocking (or silently stop being):

```python
blocking = [f for f in findings if f.get("kind") not in linter.NON_BLOCKING_KINDS]
```

`lint_script_language` exports both `NON_BLOCKING_KINDS: frozenset[str]` and
`is_blocking(finding) -> bool` as of T6. A literal `!= "skipped"` in `gates.py` after T6 means the
app-mode gate would **fail** on the D3/D4 scope note that the CLI prints as information —
strictly-wrong-in-the-other-direction, and just as much a divergence.

`_as_dicts` must pass `kind` through verbatim. It must not default a missing `kind` to `"skipped"`.

### 6.2 The two callers must stay one gate

`main()` in `scripts/lint_script_language.py` and `run_script_language_gate` in `gates.py` are
currently identical in what they compute. That is a property, and nothing tests it. This package
locks the CLI half (`test_the_cli_exit_code_is_exactly_the_blocking_predicate`) and leaves a
source-level drift guard (`test_gates_py_does_not_hardcode_the_blocking_kind`).

**Required of P3:** a mirror test in the app suite asserting that, for the same artifact,

```python
run_script_language_gate(repo_root, path, {})   # findings, in order, with kinds
```

equals `linter.lint(*linter.parse_script(text), text)` serialized — and that its `status` is
`"fail"` exactly when the CLI's `main()` returns 1. Run it over `CLEAN_SCRIPT` plus at least three
of T7's mutation rows so a divergence is caught by content, not just by shape.

Two other consequences of this package that P3's rendering must tolerate:

- Gate D now emits findings with **`beat is None`** (`check_beat_set`, the ratable-fraction
  finding, the D3/D4 scope note). Anything that assumes a beat string will `KeyError` or render
  `"None"`.
- `run_script_language_gate` still raises `ValueError` when zero VO lines parse, and
  `run_gates_for_stage` still maps that to `status="error"`. Unchanged, and deliberately so:
  fail-closed is correct there.
