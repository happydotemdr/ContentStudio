# Plan A — Contract and Topology Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the world lock out of `visual-prompts` into a new `styleboard` pipeline stage, replace invented `--sref` placeholders with declared slot tokens, and extend Gate C to enforce the new contract — so that Plan B's render console has a sheet format it can resolve against.

**Architecture:** Gate C (`scripts/lint_prompt_sheet.py`, stdlib-only) gains four checks and learns to read its world lock from a second file. The prompt sheet stops carrying `WORLD LOCK` and starts carrying `{style:…}` / `{char:…}` slot tokens in flag position. A new `shorts-styleboard` skill owns the world lock; `visual-prompts` consumes it. `pipeline.yaml` gains a `styleboard` stage, and a startup migration backfills a `styleboard` row into every pre-existing project so `visual` can still unlock.

**Tech Stack:** Python 3.11+ · stdlib-only for `scripts/lint_prompt_sheet.py` · FastAPI + Jinja2 + SQLite for `pipeline-app` · pytest · Markdown for skills

## Global Constraints

- **Every normative line in a skill or reference file carries a `[C]` / `[I]` / `[T]` / `[T-unverified]` marker.** An unmarked normative line is a bug (`CLAUDE.md`).
- **Never upgrade a marker during a move.** The world-lock and register material is `[I]` — the skill's own operational design. It must arrive in `shorts-styleboard` still marked `[I]`, with its "the corpus has nothing to say about pairing a present-day register with a source-era register" disclaimer intact. This is the exact error the spec review caught; Task 11 tests for it.
- **`scripts/lint_prompt_sheet.py` is stdlib-only.** No new dependencies.
- **FamilyBrain firewall:** no reference to `C:\Projects\FamilyBrain\`, any `brain_*` MCP tool, or a FamilyBrain remote (`CLAUDE.md`).
- **Local only.** Nothing in this plan makes a network call.
- **Gate C check IDs are append-only.** Existing checks are C1–C15; this plan adds C16, C17, C18, C19. Never renumber an existing check — findings are quoted in artifacts on disk.
- **Existing tests must stay green at every commit.** `tests/test_lint_prompt_sheet.py` (502 lines) calls `parse_sheet(text)` returning a 2-tuple and `lint(shots, world)` with two positional arguments. Both signatures are preserved throughout; new capability arrives via new functions and keyword-only arguments.
- Run repo-root linter tests with `python -m pytest tests/ -v` from the repo root. Run app tests with `python -m pytest pipeline-app/tests/ -v`.

---

## File Structure

**Modified — Gate C linter and its tests**
- `scripts/lint_prompt_sheet.py` — four new check functions, a cover parser, a world-lock resolver, a split of C11 from C12, and a `--styleboard` CLI flag.
- `tests/test_lint_prompt_sheet.py` — tests for each new check.
- `tests/fixtures/passing_sheet.md` — migrated to the new format (slots, no `WORLD LOCK`, parseable cover).
- `tests/fixtures/worked_example_sheet.md` — same migration.

**Created — Gate C fixtures**
- `tests/fixtures/passing_styleboard.md` — the world lock the migrated sheets resolve against.
- `tests/fixtures/legacy_do_less_sheet.md` — the real old-format sheet, for the C16 regression.

**Created — the new skill**
- `.claude/skills/shorts-styleboard/SKILL.md`
- `.claude/skills/shorts-styleboard/references/visual-registers.md` — moved from `visual-prompts`, markers intact.
- `.claude/skills/shorts-styleboard/references/styleboard-format.md` — the world-lock + slot-declaration output contract.

**Modified — existing skills**
- `.claude/skills/visual-prompts/SKILL.md` — drop step 2.5, rewrite the description and step 7 skeleton.
- `.claude/skills/visual-prompts/references/prompt-sheet-format.md` — §2 becomes slot declarations, §7 drops the two-literal-codes mandate.
- `.claude/skills/visual-prompts/references/visual-registers.md` — reduced to a pointer at the moved file.
- `.claude/skills/visual-prompts/references/worked-example.md` — literal codes become slots.
- `.claude/skills/midjourney-prompting/SKILL.md` — Phase 2's harvest-and-substitute becomes discovery-only.

**Modified — pipeline app**
- `pipeline.yaml` — the `styleboard` stage; `visual.depends_on` gains it.
- `pipeline-app/stage_templates/styleboard.md` — created.
- `pipeline-app/stage_templates/visual.md` — `{{ input_file }}` → `{{ input_files }}`.
- `pipeline-app/pipeline_app/migrations.py` — created; the backfill.
- `pipeline-app/pipeline_app/main.py` — call the backfill at startup.
- `pipeline-app/tests/test_migrations.py` — created.

**Created — provenance guard**
- `tests/test_skill_provenance.py`

**Modified — repo docs**
- `CLAUDE.md`, `README.md`, `.gitignore`

---

### Task 1: Gate C — reject invented `--sref` values (C16)

This is the check that makes `--sref SREF-RGS-A-DL01` — the defect that motivated the whole project — impossible to reintroduce.

**Files:**
- Modify: `scripts/lint_prompt_sheet.py`
- Test: `tests/test_lint_prompt_sheet.py`
- Create: `tests/fixtures/legacy_do_less_sheet.md`

**Interfaces:**
- Consumes: existing `Shot`, `Finding`, `prompt_flags(shot)`.
- Produces: `check_style_reference(shots: list[Shot]) -> list[Finding]`, emitting check id `"C16"`. Registered in `lint()`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lint_prompt_sheet.py`:

```python
def _shot(prompt: str, index: int = 1, register: str = "A") -> Shot:
    """A minimal Shot carrying only what flag-level checks read."""
    return Shot(
        index=index,
        beat="Hook (0–3s)",
        register=register,
        shot_class="DETAIL",
        scale="MACRO",
        camera_height="LOW",
        prompt=prompt,
        prompt_line_count=1,
    )


def test_c16_rejects_invented_sref_placeholder():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 --sref SREF-RGS-A-DL01")
    findings = check_style_reference([shot])
    assert [f.check for f in findings] == ["C16"]
    assert "SREF-RGS-A-DL01" in findings[0].message


def test_c16_accepts_numeric_url_and_random_sref():
    for value in ("1122334455", "https://cdn.midjourney.com/a1b2.png", "random"):
        shot = _shot(f"a strap pulled tight, No Text. --ar 9:16 --raw --s 95 --sref {value}")
        assert check_style_reference([shot]) == []


def test_c16_rejects_slot_used_as_an_sref_value():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 --sref {style:register_a}")
    findings = check_style_reference([shot])
    assert [f.check for f in findings] == ["C16"]
    assert "entire flag group" in findings[0].message


def test_c16_runs_as_part_of_lint():
    shots, world = parse_sheet(SHEET.replace("--s 95", "--s 95 --sref NOT-A-CODE"))
    assert any(f.check == "C16" for f in lint(shots, world))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_lint_prompt_sheet.py -k c16 -v`
Expected: FAIL with `ImportError: cannot import name 'check_style_reference'` (the module-level import list at the top of the test file does not yet include it).

- [ ] **Step 3: Add `check_style_reference` to the linter**

In `scripts/lint_prompt_sheet.py`, insert after the `check_format` function and before `def lint(`:

```python
SREF_FLAG_RE = re.compile(r"--sref\s+(\S+)")
STYLE_SLOT_RE = re.compile(r"\{style:([a-z][a-z0-9_]*)\}")
CHAR_SLOT_RE = re.compile(r"\{char:([a-z][a-z0-9_]*)\}")
VALID_SREF_VALUE_RE = re.compile(r"^(?:\d+|random|https?://\S+)$")


def check_style_reference(shots: list[Shot]) -> list[Finding]:
    """C16: every literal --sref value is a real Midjourney style reference.

    Sheets have shipped with invented placeholders (`--sref SREF-RGS-A-DL01`) that
    cannot be pasted into Midjourney. A style code is a number, a URL, or the literal
    `random`; anything else means no code was ever harvested.
    """
    findings: list[Finding] = []
    for shot in shots:
        for value in SREF_FLAG_RE.findall(prompt_flags(shot)):
            if STYLE_SLOT_RE.fullmatch(value) or CHAR_SLOT_RE.fullmatch(value):
                findings.append(
                    Finding(
                        "C16",
                        shot.index,
                        f"slot {value} used as an --sref value; a slot expands to the "
                        "entire flag group, so write it on its own, not after --sref",
                    )
                )
            elif not VALID_SREF_VALUE_RE.match(value):
                findings.append(
                    Finding(
                        "C16",
                        shot.index,
                        f"--sref value {value!r} is not a numeric code, a URL, or 'random'. "
                        "A placeholder here means no real style code was ever harvested.",
                    )
                )
    return findings
```

Then add it to `lint()`'s list, after `*check_format(shots),`:

```python
        *check_style_reference(shots),
```

And add `check_style_reference` to the import list at the top of `tests/test_lint_prompt_sheet.py`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_lint_prompt_sheet.py -v`
Expected: PASS, all tests including the pre-existing ones.

- [ ] **Step 5: Add the real-world regression fixture**

Copy the first two shot blocks and the world lock out of the real sheet into a committed fixture — `runs/` is git-ignored, so the fixture must be self-contained:

```bash
mkdir -p tests/fixtures
python - <<'PY'
from pathlib import Path
src = Path("runs/do-less-20260728-190724/03-visual/artifact.v1.md")
text = src.read_text(encoding="utf-8")
start = text.index("WORLD LOCK")
end = text.index("### Shot 3")
Path("tests/fixtures/legacy_do_less_sheet.md").write_text(text[start:end], encoding="utf-8")
PY
```

Then append the regression test to `tests/test_lint_prompt_sheet.py`:

```python
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_c16_fires_on_the_real_legacy_sheet():
    """The do-less sheet shipped with two invented codes. Gate C must now reject it."""
    text = (FIXTURES / "legacy_do_less_sheet.md").read_text(encoding="utf-8")
    shots, _world = parse_sheet(text)
    findings = check_style_reference(shots)
    assert findings, "the legacy sheet's placeholder codes must be rejected"
    assert all(f.check == "C16" for f in findings)
    assert any("SREF-RGS-A-DL01" in f.message for f in findings)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/test_lint_prompt_sheet.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/lint_prompt_sheet.py tests/test_lint_prompt_sheet.py tests/fixtures/legacy_do_less_sheet.md
git commit -m "feat(gate-c): reject invented --sref placeholder values (C16)"
```

---

### Task 2: Gate C — require a style mechanism on every shot (C17)

C16 rejects a *bad* code. Without C17, a sheet carrying no style reference at all still passes everything — the same defect class, one step removed.

**Files:**
- Modify: `scripts/lint_prompt_sheet.py`
- Test: `tests/test_lint_prompt_sheet.py`

**Interfaces:**
- Consumes: `STYLE_SLOT_RE`, `prompt_flags` from Task 1.
- Produces: `check_style_mechanism(shots: list[Shot]) -> list[Finding]`, emitting `"C17"`. Registered in `lint()`.

- [ ] **Step 1: Write the failing test**

```python
def test_c17_fires_when_a_shot_has_no_style_mechanism():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95")
    findings = check_style_mechanism([shot])
    assert [f.check for f in findings] == ["C17"]


def test_c17_accepts_literal_sref_moodboard_or_slot():
    for flags in ("--sref 1122334455", "--p m72678", "{style:register_a}"):
        shot = _shot(f"a strap pulled tight, No Text. --ar 9:16 --raw --s 95 {flags}")
        assert check_style_mechanism([shot]) == []


def test_c17_exempts_plate_shots():
    shot = _shot(
        "a flat teal gradient ground, no people, No Text. --ar 9:16 --s 200",
        register="PLATE",
    )
    assert check_style_mechanism([shot]) == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_lint_prompt_sheet.py -k c17 -v`
Expected: FAIL with `ImportError: cannot import name 'check_style_mechanism'`.

- [ ] **Step 3: Add `check_style_mechanism`**

Insert into `scripts/lint_prompt_sheet.py` directly after `check_style_reference`:

```python
MOODBOARD_FLAG_RE = re.compile(r"--p\b")


def check_style_mechanism(shots: list[Shot]) -> list[Finding]:
    """C17: every non-PLATE shot carries some style mechanism.

    C16 rejects a bad code but says nothing about a shot with no code at all, which is
    the same defect one step removed: the shot renders in whatever default aesthetic
    the model picks, and the Short stops reading as one look.

    PLATE shots are exempt — they are subject-free background plates with no register
    look to lock (visual-registers.md §5).
    """
    findings: list[Finding] = []
    for shot in shots:
        if shot.register == "PLATE":
            continue
        flags = prompt_flags(shot)
        has_mechanism = (
            "--sref" in flags
            or MOODBOARD_FLAG_RE.search(flags) is not None
            or STYLE_SLOT_RE.search(flags) is not None
        )
        if not has_mechanism:
            findings.append(
                Finding(
                    "C17",
                    shot.index,
                    "no style mechanism in the parameter block; every non-PLATE shot needs "
                    "a literal --sref/--p or a {style:...} slot, or it renders off-look",
                )
            )
    return findings
```

Register in `lint()` after `*check_style_reference(shots),`:

```python
        *check_style_mechanism(shots),
```

Add `check_style_mechanism` to the test file's import list.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_lint_prompt_sheet.py -v`
Expected: The C17 tests PASS. Pre-existing tests using `SHEET` (whose shots carry no `--sref`) will now FAIL with C17 findings.

- [ ] **Step 5: Update the in-test `SHEET` constant**

In `tests/test_lint_prompt_sheet.py`, add a slot to both shot prompts in the module-level `SHEET` string, and declare them in its world lock. Change the `WORLD LOCK` block to add two lines after `register_b_thinker: Plutarch`:

```
  slot_register_a: rgs-present-soccer-a
  slot_register_b: rgs-sourceera-painterly-b
```

And append the slot to each prompt's flag block:

```
... --ar 9:16 --raw --s 95 {style:register_a}
... --ar 9:16 --s 520 {style:register_b}
```

- [ ] **Step 6: Run the full linter suite**

Run: `python -m pytest tests/ -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/lint_prompt_sheet.py tests/test_lint_prompt_sheet.py
git commit -m "feat(gate-c): require a style mechanism on every non-PLATE shot (C17)"
```

---

### Task 3: Gate C — resolve the world lock from a separate styleboard file

The world lock moves out of the sheet (Task 7). Gate C must read it from the styleboard artifact, while still accepting a sheet that carries its own block so no existing test or artifact breaks.

**Files:**
- Modify: `scripts/lint_prompt_sheet.py`
- Test: `tests/test_lint_prompt_sheet.py`

**Interfaces:**
- Consumes: existing `parse_sheet`.
- Produces: `parse_world_lock(text: str) -> dict[str, str]`, and a `main()` that accepts `--styleboard PATH`. `parse_sheet` and `lint` signatures are unchanged.

- [ ] **Step 1: Write the failing test**

```python
STYLEBOARD = """\
=== STYLEBOARD — demo ===

WORLD LOCK
  register_a_sport: club soccer
  register_a_venue: municipal club soccer complex
  register_a_signature_objects: goal net, corner flag, painted touchline
  register_b_thinker: Plutarch
  slot_register_a: rgs-present-soccer-a
  slot_register_b: rgs-sourceera-painterly-b
"""


def test_parse_world_lock_reads_a_styleboard_artifact():
    world = parse_world_lock(STYLEBOARD)
    assert world["register_a_sport"] == "club soccer"
    assert world["slot_register_a"] == "rgs-present-soccer-a"


def test_main_resolves_the_world_lock_from_the_styleboard_flag(tmp_path, capsys):
    sheet = tmp_path / "sheet.md"
    # A sheet with NO world lock of its own — the new format.
    sheet.write_text(SHEET.split("WORLD LOCK")[0] + SHEET.split("PER-SHOT PROMPTS")[1],
                     encoding="utf-8")
    styleboard = tmp_path / "styleboard.md"
    styleboard.write_text(STYLEBOARD, encoding="utf-8")

    code = main([str(sheet), "--styleboard", str(styleboard)])
    out = capsys.readouterr().out
    assert "[C8]" not in out, "the sport must resolve from the styleboard, not go missing"
    assert code in (0, 1)


def test_main_falls_back_to_the_sheets_own_world_lock(tmp_path, capsys):
    sheet = tmp_path / "sheet.md"
    sheet.write_text(SHEET, encoding="utf-8")
    main([str(sheet)])
    assert "[C8]" not in capsys.readouterr().out
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_lint_prompt_sheet.py -k world_lock -v`
Expected: FAIL with `ImportError: cannot import name 'parse_world_lock'`.

- [ ] **Step 3: Add the resolver and the CLI flag**

Add after `parse_sheet` in `scripts/lint_prompt_sheet.py`:

```python
def parse_world_lock(text: str) -> dict[str, str]:
    """The WORLD LOCK block from any file that carries one.

    After the styleboard split the block lives in the styleboard artifact rather than
    the prompt sheet, but the block's syntax is identical in both, so parse_sheet's
    world-lock walk is reused rather than duplicated.
    """
    _shots, world = parse_sheet(text)
    return world
```

Replace `main()`'s body up to the `lint` call with:

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lint_prompt_sheet",
        description="Gate C — shot-variety lint for ContentStudio visual prompt sheets.",
    )
    parser.add_argument("sheet", type=Path, help="path to an emitted prompt sheet (.md)")
    parser.add_argument(
        "--styleboard",
        type=Path,
        default=None,
        help="path to the styleboard artifact holding the WORLD LOCK block. Omit for a "
             "legacy sheet that still carries its own block.",
    )
    args = parser.parse_args(argv)

    sheet_text = args.sheet.read_text(encoding="utf-8")
    shots, sheet_world = parse_sheet(sheet_text)
    if args.styleboard is not None:
        world = parse_world_lock(args.styleboard.read_text(encoding="utf-8"))
    else:
        world = sheet_world

    if not shots:
        print(f"Gate C: no shots parsed from {args.sheet}. Check the sheet format.")
        return 2

    findings = lint(shots, world)
```

The remainder of `main()` (the print loop and return codes) is unchanged.

Add `parse_world_lock` to the test file's import list.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_prompt_sheet.py tests/test_lint_prompt_sheet.py
git commit -m "feat(gate-c): resolve the world lock from a --styleboard artifact"
```

---

### Task 4: Gate C — slot tokens, position and declaration (C18)

**Files:**
- Modify: `scripts/lint_prompt_sheet.py`
- Test: `tests/test_lint_prompt_sheet.py`

**Interfaces:**
- Consumes: `STYLE_SLOT_RE`, `CHAR_SLOT_RE` (Task 1), `prompt_flags`, `prompt_body`.
- Produces: `check_slots(shots: list[Shot], world: dict[str, str]) -> list[Finding]`, emitting `"C18"`. Registered in `lint()` — note this is the first new check that takes `world`.

- [ ] **Step 1: Write the failing test**

```python
SLOT_WORLD = {
    "register_a_sport": "club soccer",
    "register_a_signature_objects": "goal net, corner flag, painted touchline",
    "slot_register_a": "rgs-present-soccer-a",
    "slot_char_coach": "rgs-coach-01",
}


def test_c18_accepts_a_declared_slot_in_flag_position():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 {style:register_a}")
    assert check_slots([shot], SLOT_WORLD) == []


def test_c18_rejects_an_undeclared_style_slot():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 {style:register_z}")
    findings = check_slots([shot], SLOT_WORLD)
    assert [f.check for f in findings] == ["C18"]
    assert "slot_register_z" in findings[0].message


def test_c18_rejects_a_slot_before_the_first_flag():
    """Before the first ' --' the token is parsed as prompt body, not flags."""
    shot = _shot("a strap pulled tight {style:register_a}, No Text. --ar 9:16 --raw --s 95")
    findings = check_slots([shot], SLOT_WORLD)
    assert [f.check for f in findings] == ["C18"]
    assert "after at least one literal flag" in findings[0].message


def test_c18_checks_character_slots_too():
    shot = _shot("a coach lowering a medal, No Text. --ar 9:16 --raw --s 95 {char:coach}")
    assert check_slots([shot], SLOT_WORLD) == []
    missing = _shot("a coach lowering a medal, No Text. --ar 9:16 --raw --s 95 {char:parent}")
    assert [f.check for f in check_slots([missing], SLOT_WORLD)] == ["C18"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_lint_prompt_sheet.py -k c18 -v`
Expected: FAIL with `ImportError: cannot import name 'check_slots'`.

- [ ] **Step 3: Add `check_slots`**

Insert after `check_style_mechanism`:

```python
SLOT_KINDS = (
    (STYLE_SLOT_RE, "style", "slot_"),
    (CHAR_SLOT_RE, "char", "slot_char_"),
)


def check_slots(shots: list[Shot], world: dict[str, str]) -> list[Finding]:
    """C18: slot tokens are declared in the world lock and sit in flag position.

    Position is load-bearing, not cosmetic. prompt_body/prompt_flags split a prompt at
    the first occurrence of ' --', and a slot token does not begin with '--'. Placed
    before the first literal flag it lands in the prompt BODY, where it would both fail
    C13's 'No Text. is last' rule and be sent to Midjourney as literal prose.
    """
    findings: list[Finding] = []
    for shot in shots:
        flags = prompt_flags(shot)
        for pattern, kind, prefix in SLOT_KINDS:
            in_flags = set(pattern.findall(flags))
            for name in pattern.findall(shot.prompt):
                if name not in in_flags:
                    findings.append(
                        Finding(
                            "C18",
                            shot.index,
                            f"{{{kind}:{name}}} must sit after at least one literal flag "
                            "(put it last, after --ar/--s); before the first ' --' it is "
                            "parsed as prompt body",
                        )
                    )
                    continue
                key = f"{prefix}{name}"
                if key not in world:
                    findings.append(
                        Finding(
                            "C18",
                            shot.index,
                            f"{{{kind}:{name}}} is not declared; add a {key!r} line to the "
                            "styleboard's WORLD LOCK block naming the Library entry it binds to",
                        )
                    )
    return findings
```

Register in `lint()` after `*check_style_mechanism(shots),`:

```python
        *check_slots(shots, world),
```

Add `check_slots` to the test file's import list.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_prompt_sheet.py tests/test_lint_prompt_sheet.py
git commit -m "feat(gate-c): validate {style:...} and {char:...} slot tokens (C18)"
```

---

### Task 5: Gate C — lint the cover as a first-class asset (C19)

The cover has never been linted: `parse_sheet` matches only `### Shot` headings and walks past the `COVER / THUMBNAIL` block. It must be linted for density, format, register bands, and style mechanism — but **excluded from C1–C7 and C11**, which are whole-sequence checks. Appending it to the shot list would corrupt every one of them.

**Files:**
- Modify: `scripts/lint_prompt_sheet.py`
- Test: `tests/test_lint_prompt_sheet.py`

**Interfaces:**
- Consumes: `Shot`, `Finding`, all check functions.
- Produces: `parse_cover(text: str) -> Shot | None`; `declares_cover_reuse(text: str) -> bool`; `lint_cover(cover: Shot, world: dict[str, str]) -> list[Finding]`; `check_cover_present(text: str) -> list[Finding]` emitting `"C19"`. `lint()` gains a keyword-only `cover` parameter defaulting to `None`, so `lint(shots, world)` keeps working.

- [ ] **Step 1: Write the failing test**

```python
COVER_BLOCK = """\
COVER / THUMBNAIL

### Cover — Thumbnail · Register A · HUMAN-COST · CLOSE · EYE

```text
documentary sports photography, tight close-up of a determined young club soccer player mid-effort framed right of centre, jaw set and eyes fixed off-camera, sweat and pitch mud on one cheek, a goal net blurred far behind, low three-quarter angle, 85mm lens at f1.8, shallow focal plane holding the face sharp, warm amber rim light against a cold teal ground, the left third kept dark and empty for a title overlay, muted palette of teal-ink amber and off-white, fine film grain, DSLR, No Text. --ar 9:16 --raw --s 110 {style:register_a}
```
"""


def test_parse_cover_reads_the_cover_block():
    cover = parse_cover(COVER_BLOCK)
    assert cover is not None
    assert cover.index == 0
    assert cover.register == "A"
    assert cover.shot_class == "HUMAN-COST"
    assert cover.scale == "CLOSE"
    assert cover.camera_height == "EYE"


def test_parse_cover_returns_none_when_the_cover_reuses_the_hook():
    text = "COVER / THUMBNAIL\n  Cover = Hook beat still #1 + shorts-assembly's overlay.\n"
    assert parse_cover(text) is None
    assert declares_cover_reuse(text) is True


def test_c19_fires_when_no_cover_decision_is_stated():
    assert [f.check for f in check_cover_present("=== SHEET ===\n\nno cover here\n")] == ["C19"]


def test_c19_passes_for_either_cover_branch():
    assert check_cover_present(COVER_BLOCK) == []
    assert check_cover_present("Cover = Hook beat still #1, no separate generation.") == []


def test_lint_cover_applies_format_and_style_checks_but_not_sequence():
    cover = parse_cover(COVER_BLOCK)
    findings = lint_cover(cover, SLOT_WORLD)
    assert all(f.check not in {"C1", "C2", "C3", "C4", "C5", "C6", "C7", "C11"} for f in findings)


def test_lint_cover_catches_a_bad_cover_sref():
    bad = COVER_BLOCK.replace("{style:register_a}", "--sref SREF-RGS-A-DL01")
    findings = lint_cover(parse_cover(bad), SLOT_WORLD)
    assert any(f.check == "C16" for f in findings)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_lint_prompt_sheet.py -k cover -v`
Expected: FAIL with `ImportError: cannot import name 'parse_cover'`.

- [ ] **Step 3: Split C11 from C12 so the cover can use density without anti-clone**

`check_prompt_quality` currently emits both C11 (anti-clone across pairs) and C12 (density). The cover deliberately resembles the Hook still, so it must get C12 without C11. Replace `check_prompt_quality` in `scripts/lint_prompt_sheet.py` with two functions plus a wrapper that preserves the existing name and behaviour:

```python
def check_prompt_clone(shots: list[Shot]) -> list[Finding]:
    """C11: anti-clone. Consistency belongs in --sref, not a copied prompt body."""
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
    return findings


def check_prompt_density(shots: list[Shot]) -> list[Finding]:
    """C12: every prompt carries concrete renderable content in all nine layers."""
    findings: list[Finding] = []
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


def check_prompt_quality(shots: list[Shot]) -> list[Finding]:
    """C11-C12, kept as one entry point for callers that want both."""
    return [*check_prompt_clone(shots), *check_prompt_density(shots)]
```

- [ ] **Step 4: Add the cover parser and linter**

Insert after `parse_world_lock`:

```python
COVER_HEADING_RE = re.compile(
    r"^###\s+Cover\s+—\s+(.+?)\s+·\s+Register\s+(A|B|PLATE)"
    r"\s+·\s+([A-Z-]+)\s+·\s+([A-Z-]+)\s+·\s+([A-Z]+)\s*$"
)
COVER_REUSE_RE = re.compile(r"^\s*Cover\s*=\s*Hook\b", re.IGNORECASE | re.MULTILINE)


def parse_cover(text: str) -> Shot | None:
    """The dedicated cover prompt, as a Shot with index 0, or None.

    None means either 'the cover reuses the Hook still' (a legitimate branch — see
    declares_cover_reuse) or 'no cover block at all' (C19). Index 0 keeps the cover
    distinguishable from every real shot in a finding message.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        heading = COVER_HEADING_RE.match(line)
        if not heading:
            continue
        prompt_lines, _next = _read_fenced_prompt(lines, i + 1)
        if not prompt_lines:
            return None
        return Shot(
            index=0,
            beat=heading.group(1),
            register=heading.group(2),
            shot_class=heading.group(3),
            scale=heading.group(4),
            camera_height=heading.group(5),
            prompt=" ".join(prompt_lines).strip(),
            prompt_line_count=len(prompt_lines),
        )
    return None


def declares_cover_reuse(text: str) -> bool:
    return COVER_REUSE_RE.search(text) is not None


def check_cover_present(text: str) -> list[Finding]:
    """C19: the cover decision is stated, never silently omitted.

    prompt-sheet-format.md §7 already requires this of every emitted sheet `[I]`; until
    now nothing enforced it.
    """
    if parse_cover(text) is not None or declares_cover_reuse(text):
        return []
    return [
        Finding(
            "C19",
            None,
            "no cover decision: emit a '### Cover — ...' block, or state "
            "'Cover = Hook beat still #1' explicitly",
        )
    ]


def lint_cover(cover: Shot, world: dict[str, str]) -> list[Finding]:
    """Every per-shot check, and none of the whole-sequence ones.

    C1-C7 are adjacency, scale-spread and register-balance checks over an ordered arc;
    the cover has no position in that arc, so folding it into the shot list would
    corrupt all seven. C11 is excluded for a different reason: the cover is *supposed*
    to resemble the Hook still, so anti-clone would fire by design.
    """
    single = [cover]
    return [
        *check_world_lock(single, world),
        *check_prompt_density(single),
        *check_format(single),
        *check_vocabulary(single),
        *check_style_reference(single),
        *check_style_mechanism(single),
        *check_slots(single, world),
    ]
```

Now extend `lint()` to accept the cover, keyword-only so the existing two-positional-argument call sites keep working:

```python
def lint(
    shots: list[Shot],
    world: dict[str, str],
    *,
    cover: Shot | None = None,
) -> list[Finding]:
    """Run every Gate C check, in check order."""
    findings = [
        *check_sequence(shots),
        *check_register_balance(shots),
        *check_world_lock(shots, world),
        *check_prompt_quality(shots),
        *check_format(shots),
        *check_vocabulary(shots),
        *check_style_reference(shots),
        *check_style_mechanism(shots),
        *check_slots(shots, world),
    ]
    if cover is not None:
        findings.extend(lint_cover(cover, world))
    return findings
```

And wire it into `main()` — replace the `findings = lint(shots, world)` line with:

```python
    cover = parse_cover(sheet_text)
    findings = [*check_cover_present(sheet_text), *lint(shots, world, cover=cover)]
```

Add `parse_cover`, `declares_cover_reuse`, `check_cover_present`, `lint_cover`, `check_prompt_clone`, and `check_prompt_density` to the test file's import list.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: The cover tests PASS. Existing `main()` tests over fixtures with no cover block will now FAIL with a C19 finding — that is correct and is fixed in Task 6.

- [ ] **Step 6: Commit**

```bash
git add scripts/lint_prompt_sheet.py tests/test_lint_prompt_sheet.py
git commit -m "feat(gate-c): lint the cover as a first-class asset (C19)"
```

---

### Task 6: Migrate the Gate C fixtures to the new sheet format

Tasks 1–5 changed the contract. The two fixture sheets still speak the old one, so they now fail. This task is what makes the suite green again and demonstrates the target format end to end.

**Files:**
- Modify: `tests/fixtures/passing_sheet.md`, `tests/fixtures/worked_example_sheet.md`
- Create: `tests/fixtures/passing_styleboard.md`, `tests/fixtures/worked_example_styleboard.md`
- Test: `tests/test_lint_prompt_sheet.py`

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces: two styleboard fixtures — the canonical examples of the artifact format Task 7's skill must emit. Between them they exercise **both** cover branches: `passing_sheet.md` gets a dedicated `### Cover —` block, `worked_example_sheet.md` gets the `Cover = Hook` reuse line.

- [ ] **Step 1: Read the current fixtures to see exactly what must change**

Run: `python -m pytest tests/ -v`
Expected: FAIL. Record every finding id and shot number — this list is the task's work queue.

```bash
python scripts/lint_prompt_sheet.py tests/fixtures/passing_sheet.md
```

- [ ] **Step 2: Create the styleboard fixture**

Create `tests/fixtures/passing_styleboard.md`. Copy the `WORLD LOCK` block **verbatim** out of `tests/fixtures/passing_sheet.md`, then append the two slot declarations:

```markdown
=== STYLEBOARD — passing-fixture ===

WORLD LOCK
  register_a_sport:              club soccer
  register_a_venue:              municipal club soccer complex
  register_a_signature_objects:  goal net, corner flag, painted touchline
  register_a_season_time:        winter dawn
  register_a_rationale:          club soccer's early-specialization pipeline is the sharpest present-day analogue to the claim's evidence on burnout
  register_b_thinker:            Plutarch
  register_b_era_place:          first-century Greece, a hillside estate near Chaeronea
  register_b_locations:          colonnaded terrace, olive-terraced hillside, stone courtyard
  register_b_artifacts:          terracotta watering vessel, wax writing tablet, olive branch
  register_b_figure_archetype:   an unnamed tutor, plain wool himation, face turned into shadow
  motif:                         a watering can — modern plastic in Register A, terracotta vessel in Register B
  slot_register_a:               rgs-present-soccer-a
  slot_register_b:               rgs-sourceera-painterly-b
```

If the values in the real fixture differ from the above, **use the real fixture's values** — the point is that the block moves unchanged, not that it matches this plan's example.

- [ ] **Step 3: Migrate `passing_sheet.md`**

This fixture has 5 shots and carries `--sref 1122334455` on its three Register A shots and `--sref 5544332211` on its two Register B shots. Three edits:
1. Delete the entire `WORLD LOCK` block and its heading (lines 3 onward, through the last `key: value` line).
2. Replace every `--sref 1122334455` with `{style:register_a}` and every `--sref 5544332211` with `{style:register_b}`, keeping the token **last** in the flag block.
3. Add a cover block before the first shot — this sheet has no cover section today, so C19 fires without it:

```markdown
COVER / THUMBNAIL

### Cover — Thumbnail · Register A · HUMAN-COST · CLOSE · EYE

```text
documentary sports photography, tight close-up of a determined young club soccer player mid-effort framed right of centre, jaw set and eyes fixed off-camera, sweat and pitch mud drying on one cheek, a goal net dissolved into deep bokeh far behind, low three-quarter angle from chest height, 85mm lens at f1.8, a shallow focal plane holding the face sharp while the net melts away, warm amber rim light carving the face from a cold teal-grey ground, the left third kept dark and empty for a title overlay, muted palette of teal-ink amber and off-white, crisp skin and fabric texture, fine film grain, DSLR, No Text. --ar 9:16 --raw --s 110 {style:register_a}
```
```

- [ ] **Step 4: Verify the migrated fixture passes**

Run: `python scripts/lint_prompt_sheet.py tests/fixtures/passing_sheet.md --styleboard tests/fixtures/passing_styleboard.md`
Expected: `Gate C: PASS — <n> shots, 0 findings.`

If C8 fires, the sport or a signature object is missing from a prompt body — fix the prompt, not the check. If C12 fires on the cover, the cover prompt is under 10 clauses or 60 words.

- [ ] **Step 5: Migrate `worked_example_sheet.md` the same way**

This fixture has its own world lock and its own pair of codes (`2481950736` for Register A, `9057261843` for Register B, across 11 shots), so it needs **its own styleboard** — do not point it at `passing_styleboard.md`.

Create `tests/fixtures/worked_example_styleboard.md` by copying that sheet's `WORLD LOCK` block verbatim and appending:

```
  slot_register_a:               rgs-present-soccer-a
  slot_register_b:               rgs-sourceera-painterly-b
```

Then apply edits 1 and 2 from Step 3 to the sheet (delete `WORLD LOCK`; every `--sref 2481950736` → `{style:register_a}`, every `--sref 9057261843` → `{style:register_b}`).

For the cover: this sheet has **no** cover section at all, so C19 will fire. Because it is the *worked example* — the file a reader copies from — give it the explicit reuse branch rather than a second full cover prompt, so both branches appear across the two fixtures. Add before the first shot heading:

```markdown
COVER / THUMBNAIL
  Cover = Hook beat still #1 + shorts-assembly's text overlay. No separate generation.
```

The line must begin exactly `Cover = Hook` for `COVER_REUSE_RE` to match.

Run: `python scripts/lint_prompt_sheet.py tests/fixtures/worked_example_sheet.md --styleboard tests/fixtures/worked_example_styleboard.md`
Expected: `Gate C: PASS`.

- [ ] **Step 6: Add a fixture-level test asserting the new format passes**

```python
import pytest

MIGRATED_PAIRS = [
    ("passing_sheet.md", "passing_styleboard.md"),
    ("worked_example_sheet.md", "worked_example_styleboard.md"),
]


@pytest.mark.parametrize("sheet_name, styleboard_name", MIGRATED_PAIRS)
def test_migrated_fixture_is_clean_against_its_styleboard(sheet_name, styleboard_name):
    sheet = (FIXTURES / sheet_name).read_text(encoding="utf-8")
    world = parse_world_lock((FIXTURES / styleboard_name).read_text(encoding="utf-8"))
    shots, _ = parse_sheet(sheet)
    findings = [*check_cover_present(sheet), *lint(shots, world, cover=parse_cover(sheet))]
    assert findings == [], [f"[{f.check}] shot {f.shot_index}: {f.message}" for f in findings]


@pytest.mark.parametrize("sheet_name, _styleboard_name", MIGRATED_PAIRS)
def test_migrated_sheet_carries_no_world_lock_of_its_own(sheet_name, _styleboard_name):
    """The world lock has exactly one home now. Two copies with no sync rule is the
    failure this split exists to prevent."""
    assert "WORLD LOCK" not in (FIXTURES / sheet_name).read_text(encoding="utf-8")


def test_the_two_fixtures_cover_both_cover_branches():
    """One dedicated cover prompt, one Hook-reuse declaration — so a regression in
    either branch of parse_cover/declares_cover_reuse fails a test."""
    assert parse_cover((FIXTURES / "passing_sheet.md").read_text(encoding="utf-8")) is not None
    worked = (FIXTURES / "worked_example_sheet.md").read_text(encoding="utf-8")
    assert parse_cover(worked) is None
    assert declares_cover_reuse(worked) is True
```

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest tests/ -v`
Expected: PASS. Any remaining failure is an old test asserting on the pre-migration fixture contents — update its expectation to the new format.

- [ ] **Step 8: Commit**

```bash
git add tests/fixtures/ tests/test_lint_prompt_sheet.py
git commit -m "test(gate-c): migrate fixtures to the slotted sheet + styleboard format"
```

---

### Task 7: Create the `shorts-styleboard` skill

**Files:**
- Create: `.claude/skills/shorts-styleboard/SKILL.md`
- Create: `.claude/skills/shorts-styleboard/references/visual-registers.md`
- Create: `.claude/skills/shorts-styleboard/references/styleboard-format.md`

**Interfaces:**
- Consumes: nothing in code.
- Produces: a skill whose emitted artifact is the file Task 3's `--styleboard` flag reads and Task 6's `passing_styleboard.md` exemplifies.

- [ ] **Step 1: Move `visual-registers.md` with git history preserved**

```bash
mkdir -p .claude/skills/shorts-styleboard/references
git mv .claude/skills/visual-prompts/references/visual-registers.md .claude/skills/shorts-styleboard/references/visual-registers.md
```

- [ ] **Step 2: Verify the moved file's provenance markers survived**

The single most important check in this plan. Run:

```bash
grep -c "\[I\]" .claude/skills/shorts-styleboard/references/visual-registers.md
grep -n "operational design" .claude/skills/shorts-styleboard/references/visual-registers.md
```

Expected: a non-zero `[I]` count, and §0's grounding note still present. **Do not edit any marker.** The file moves byte-identical except for the §7 change in Step 3.

- [ ] **Step 3: Add slot declarations to §7's world-lock block**

In the moved `references/visual-registers.md`, §7, add two rows to the template block after `motif:` and to the filled-in example:

```
  slot_register_a:               [Library entry label bound to Register A]
  slot_register_b:               [Library entry label bound to Register B]
```

And append this paragraph to §7:

```markdown
**Slot declarations `[I]`.** Every `{style:…}` or `{char:…}` token a downstream prompt
sheet uses must be declared here as a `slot_<name>:` line whose value names the Style
Library entry it binds to. Gate C's **C18** rejects an undeclared slot. The literal
`--sref` code is deliberately *not* written here — it is resolved at generate time from
the Library, so re-locking a Short's look is one binding change rather than a sheet
regeneration.
```

- [ ] **Step 4: Write `references/styleboard-format.md`**

Create `.claude/skills/shorts-styleboard/references/styleboard-format.md`:

```markdown
# Styleboard format — the artifact Gate C reads

The styleboard artifact is the **single home of the world lock**. The prompt sheet no
longer carries one; `scripts/lint_prompt_sheet.py --styleboard <this file>` resolves
every world-lock check (C8–C10) and every slot declaration (C18) against it `[I]`.

## Exact shape

```
=== STYLEBOARD — [Short ID / title] ===

WORLD LOCK
  [the 11 keys from visual-registers.md §7, plus one slot_* line per slot the sheet uses]

BINDINGS
  [one line per slot: which Style Library entry it binds to, and why]

DISCOVERY REQUESTS
  [one line per world with no Library entry yet — or "none"]
```

The `WORLD LOCK` block's syntax is byte-identical to the block that used to live in the
prompt sheet: heading on its own line, two-space-indented `snake_case_key: value` pairs,
block ends at the first line that doesn't match `[a-z][a-z0-9_]*: value` `[I]`.

`BINDINGS` and `DISCOVERY REQUESTS` sit outside the parser — Gate C never reads them —
but they travel downstream to the render console and must always be present `[I]`.

## Why the code is not written here `[I]`

Writing a literal `--sref` code into this artifact would recreate the defect this split
exists to remove: a code invented before any image was rendered. The slot names a
*binding*; the render console resolves it against the Style Library at generate time.
An artifact that names `slot_register_a: rgs-present-soccer-a` is honest about what it
knows; one that names `--sref SREF-RGS-A-DL01` is not.
```

- [ ] **Step 5: Write `SKILL.md`**

Create `.claude/skills/shorts-styleboard/SKILL.md`. Copy the frontmatter shape from `visual-prompts/SKILL.md`, and copy **step 2.5 (Lock the world) and step 3a (Decide the consistency situation) verbatim** out of `visual-prompts/SKILL.md` — including every `[I]` and `[T]` marker — as the workflow body.

```markdown
---
name: shorts-styleboard
description: Locks a ContentStudio Short's two visual worlds before any prompt exists — naming the Register A/present sport and venue, the Register B/source-era thinker and place, the motif that crosses both, and which Style Library entry each register binds to. Emits the styleboard artifact that `visual-prompts` consumes and that Gate C reads its world lock from. Use whenever a Short has a finished script and needs its world locked, when asked to "lock the world," "pick the sport for this Short," "set the registers," "bind the style slots," or when a world has no Library entry yet and needs a discovery request raised. Does NOT write shot prompts — that is `visual-prompts`.
---

# Shorts Styleboard (script → world lock + style bindings)

## Pipeline position

- **Upstream input:** the shot-ready timed script from `shorts-scripting`. Optionally a
  companion grounding artifact, whose thinker/source and motif populate the
  `register_b_*` keys and `motif` directly rather than being invented here `[I]`.
- **This skill's job:** lock the two registers and the world, and declare which Style
  Library entry each register binds to. Nothing about individual shots.
- **Downstream:** `visual-prompts` reads this artifact and storyboards against it.

## Why this is grounded, not generic

The register system, its shot-class taxonomy, and the world-lock block are **this
skill's own operational design `[I]`** — the corpus has nothing to say about pairing a
present-day register with a source-era register. They moved here from `visual-prompts`
unchanged, markers intact; nothing was upgraded to `[C]` by the move. The Midjourney
parameter bands the register file cites are `[T]`, web-verified 2026-07-26. Say so
plainly if asked how solid these rules are.

## Workflow

### 1. Lock the world

[Copy step 2.5 from visual-prompts/SKILL.md verbatim, markers intact, then add the two
slot_* lines to the block template per references/visual-registers.md §7.]

### 2. Decide the whole-Short consistency situation, once

[Copy step 3a from visual-prompts/SKILL.md verbatim, markers intact.]

### 3. Bind each register to a Style Library entry

Name the Library entry each register binds to, as a `slot_*` line in the world lock and
a one-line rationale under `BINDINGS` `[I]`. If a world has no Library entry yet, say so
under `DISCOVERY REQUESTS` rather than inventing a code — an invented `--sref` is the
exact defect this stage exists to eliminate `[I]`.

### 4. Emit the styleboard artifact

Per `references/styleboard-format.md`.

## Reference files

- `references/visual-registers.md` — the two-world system, both register contracts, the
  world-lock block, and how to choose the sport.
- `references/styleboard-format.md` — the exact artifact shape Gate C parses.
```

- [ ] **Step 6: Verify the fixture styleboard matches the documented format**

Run: `python scripts/lint_prompt_sheet.py tests/fixtures/passing_sheet.md --styleboard tests/fixtures/passing_styleboard.md`
Expected: `Gate C: PASS`.

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/shorts-styleboard/ .claude/skills/visual-prompts/
git commit -m "feat(skills): add shorts-styleboard, moving the world lock out of visual-prompts"
```

---

### Task 8: Update `visual-prompts` to consume the world lock

**Files:**
- Modify: `.claude/skills/visual-prompts/SKILL.md`
- Modify: `.claude/skills/visual-prompts/references/prompt-sheet-format.md`
- Create: `.claude/skills/visual-prompts/references/visual-registers.md` (a pointer stub)
- Modify: `.claude/skills/visual-prompts/references/worked-example.md`

**Interfaces:**
- Consumes: the styleboard artifact format from Task 7.
- Produces: a skill that emits the slotted, world-lock-free sheet Task 6's fixtures exemplify.

- [ ] **Step 1: Replace step 2.5 with a consume-don't-decide instruction**

In `.claude/skills/visual-prompts/SKILL.md`, replace the whole of `### 2.5. Lock the world` with:

```markdown
### 2.5. Read the world lock — do not decide it

The world lock is `shorts-styleboard`'s output, not yours. Read the styleboard artifact
handed to you and inherit its 11 `register_a_*` / `register_b_*` / `motif` keys and its
`slot_*` declarations unchanged `[I]`. **Do not re-emit the `WORLD LOCK` block into your
sheet** — one home, no sync rule needed.

If no styleboard artifact was supplied, stop and say so rather than inventing a world:
an invented world lock produces invented `--sref` codes, which is the defect this split
removed `[I]`.

Every `--sref` in your prompts is a **slot**, never a literal code: `{style:register_a}`
for Register A shots, `{style:register_b}` for Register B, `{char:<name>}` where the
styleboard declares a character binding. Slots go **last in the flag block**, after
`--ar`/`--raw`/`--s` — before the first ` --` they are parsed as prompt body and Gate C's
**C18** rejects them `[I]`.
```

- [ ] **Step 2: Update the frontmatter description**

The description currently leads with "locking a Register A/present and Register B/source-era world plus a per-Short sport/world lock". Replace that clause with:

```
consuming the world lock from `shorts-styleboard`,
```

and append to the end of the description:

```
Does NOT lock the world or pick the sport — that is `shorts-styleboard`, which runs before this skill.
```

- [ ] **Step 3: Update step 7's sheet skeleton**

In `### 7. Emit the prompt sheet`, delete these lines from the skeleton:

```
WORLD LOCK
  [11 keys — see references/visual-registers.md §7 and step 2.5]

```

and replace the two `--sref` lines under `WHOLE-SHORT SETUP` with:

```
  Register A style: {style:register_a}   [resolved from the styleboard's binding at generate time]
  Register B style: {style:register_b}   [resolved from the styleboard's binding at generate time]
  Styleboard:       [path to the styleboard artifact this sheet was built against]
```

- [ ] **Step 4: Replace the moved reference with a pointer stub**

Create `.claude/skills/visual-prompts/references/visual-registers.md`:

```markdown
# Visual registers — moved

The dual-register system, both register contracts, the world-lock block, and the
sport-choice rule now live with the skill that owns them:

`.claude/skills/shorts-styleboard/references/visual-registers.md`

They moved unchanged, `[I]` markers intact — the register system is `shorts-styleboard`'s
own operational design, not a corpus finding, and the move did not upgrade it.

This skill still **reads** everything in that file: the Register A and Register B
prompt contracts (medium, banned vocabulary, parameter bands, shot classes) govern every
prompt written here. Only the *decision* moved, not the constraints.
```

- [ ] **Step 5: Update `prompt-sheet-format.md`**

Two edits:

In §2, replace the section body with a pointer plus the slot rule:

```markdown
## 2. The world-lock block — moved to the styleboard

The prompt sheet no longer carries a `WORLD LOCK` block. It lives in the styleboard
artifact (`shorts-styleboard/references/styleboard-format.md`), and Gate C reads it via
`python scripts/lint_prompt_sheet.py <sheet> --styleboard <styleboard>` `[I]`.

What the sheet carries instead is **slot tokens**, in flag position:

- `{style:register_a}` / `{style:register_b}` — the register's style binding.
- `{char:<name>}` — a character binding, where the styleboard declares one.

Each must be declared in the styleboard's world lock as `slot_register_a:`,
`slot_char_<name>:`, etc., or Gate C's **C18** fires. Slots sit **after at least one
literal flag** — `prompt_body`/`prompt_flags` split at the first ` --`, so a slot placed
earlier lands in the prompt body `[I]`.

The `register_a_signature_objects` substring-matching warning below still applies, and
still bites — it is now a property of the styleboard's block, not the sheet's.
```

Keep the existing warning paragraph about mechanical substring matching; move it under the new §2 text.

In §7, replace the `WHOLE-SHORT SETUP` bullet's parenthetical about two `--sref` codes with:

```markdown
- **`WHOLE-SHORT SETUP`** — aspect ratio (`--ar 9:16`), the **two style slots**
  (`{style:register_a}`, `{style:register_b}`) and the path to the styleboard artifact
  they resolve against, and the **phase ladder** — the ordered list of script beats this
  sheet covers, so a reader can see the whole arc before reading a single shot block.
  "Phase ladder" is this skill's own name for that list, not a corpus or parser term `[I]`.
```

Also update §7's cover bullet to name the new parseable form:

```markdown
- **The cover/thumbnail decision** (`SKILL.md` step 6) — either a `### Cover — <Beat> ·
  Register <A|B> · <SHOT CLASS> · <SCALE> · <CAMERA HEIGHT>` block with its own fenced
  prompt, or a line beginning exactly `Cover = Hook` stating the Hook still doubles as
  the cover. Gate C's **C19** rejects a sheet that states neither `[I]`.
```

And in §6's worked shot block, change the trailing `--sref 1122334455` to `{style:register_a}`.

- [ ] **Step 6: Update `worked-example.md`**

Replace every literal `--sref <digits>` in the emitted-sheet examples with `{style:register_a}` or `{style:register_b}` per the shot's register, and delete any `WORLD LOCK` block shown as part of the *sheet* output (keeping it only if the example explicitly labels it as the styleboard's output).

- [ ] **Step 7: Verify no stale literal codes remain**

```bash
grep -rn -- "--sref [0-9]" .claude/skills/visual-prompts/ || echo "clean"
grep -rn "WORLD LOCK" .claude/skills/visual-prompts/ || echo "clean"
```

Expected: `clean` for both, or only matches inside text explicitly describing the styleboard.

- [ ] **Step 8: Commit**

```bash
git add .claude/skills/visual-prompts/
git commit -m "refactor(visual-prompts): consume the styleboard world lock, emit slots"
```

---

### Task 9: Update `midjourney-prompting`'s harvest flow

`midjourney-prompting`'s Phase 2 tells the reader to harvest a style code from a winning draft and substitute it. That is now the **discovery** flow only; asset renders bind from the Style Library from rung 1.

**Files:**
- Modify: `.claude/skills/midjourney-prompting/SKILL.md`

- [ ] **Step 1: Find the harvest instructions**

```bash
grep -n "harvest" .claude/skills/midjourney-prompting/SKILL.md
```

- [ ] **Step 2: Rewrite Step 3's harvest sentence**

In `### Step 3 — Phase 1, wide exploration (cheap)`, replace the sentence beginning "Emit the draft command, tell the user to harvest the winning thumbnail's style code, and **stop for their pick**." with:

```markdown
Emit the draft command and **stop for their pick**. What happens to that pick depends on
which job this is `[I]`:

- **Style discovery** (`stage: moodboard` / `explore`) — harvest the winning thumbnail's
  style code; it becomes a Style Library entry, and the ladder terminates here.
- **Asset rendering in the ContentStudio pipeline** — do *not* harvest. The style is
  already bound from the Library via the sheet's `{style:…}` slot and is present from the
  draft onward, so the pick chooses a *composition*, not a style. Drafting off-style would
  make the pick meaningless.
```

- [ ] **Step 3: Rewrite Step 4's substitution sentence**

In `### Step 4 — Phase 2, compositional lock (standard)`, replace "Substitute the harvested `--sref <code>` or moodboard `--p <code>`." with:

```markdown
Carry the same style reference the draft ran under — the harvested `--sref <code>` in a
discovery job, or the Library-bound `{style:…}` slot in a pipeline job. Changing the style
between rungs invalidates the composition you just chose `[I]`.
```

- [ ] **Step 4: Verify the pipeline-mode boundary table still reads true**

```bash
grep -n "visual-prompts owns" -A 10 .claude/skills/midjourney-prompting/SKILL.md
```

Confirm no row claims this skill owns the world lock. If one does, change its owner column to `shorts-styleboard`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/midjourney-prompting/
git commit -m "docs(midjourney-prompting): scope code harvesting to discovery jobs only"
```

---

### Task 10: Add the `styleboard` stage and its templates

**Files:**
- Modify: `pipeline.yaml`
- Create: `pipeline-app/stage_templates/styleboard.md`
- Modify: `pipeline-app/stage_templates/visual.md`
- Test: `pipeline-app/tests/test_pipeline_config.py`

**Interfaces:**
- Consumes: `StageDef` from `pipeline_config.py`.
- Produces: a `styleboard` stage id with `dir_prefix: "02b"` → run directory `02b-styleboard`; `visual.depends_on == ["scripting", "styleboard"]`.

- [ ] **Step 1: Write the failing test**

Append to `pipeline-app/tests/test_pipeline_config.py`:

```python
def test_real_topology_has_styleboard_between_scripting_and_visual():
    repo_root = Path(__file__).resolve().parents[2]
    stages = load_topology(repo_root / "pipeline.yaml")
    by_id = {s.id: s for s in stages}

    assert "styleboard" in by_id
    assert by_id["styleboard"].depends_on == ["scripting"]
    assert by_id["styleboard"].dir_prefix == "02b"
    assert by_id["visual"].depends_on == ["scripting", "styleboard"]

    ids = [s.id for s in stages]
    assert ids.index("styleboard") < ids.index("visual")


def test_every_stage_has_a_kickoff_template():
    """render_kickoff_prompt does env.get_template(f'{stage_id}.md'); a stage with no
    template raises TemplateNotFound on its first turn, not at startup."""
    repo_root = Path(__file__).resolve().parents[2]
    stages = load_topology(repo_root / "pipeline.yaml")
    templates_dir = repo_root / "pipeline-app" / "stage_templates"
    missing = [s.id for s in stages if not (templates_dir / f"{s.id}.md").exists()]
    assert missing == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest pipeline-app/tests/test_pipeline_config.py -k styleboard -v`
Expected: FAIL with `AssertionError` — `'styleboard' not in by_id`.

- [ ] **Step 3: Add the stage to `pipeline.yaml`**

Insert between the `scripting` and `voiceover` entries:

```yaml
  - id: styleboard
    skill: shorts-styleboard
    dir_prefix: "02b"
    depends_on: [scripting]
```

And change the `visual` entry's `depends_on`:

```yaml
    depends_on: [scripting, styleboard]
```

`dir_prefix: "02b"` is deliberate: nav order comes from `stage_defs` order, not the prefix (`build_stage_nav`), so `02b` sorts correctly and no existing run directory is renumbered.

- [ ] **Step 4: Create the kickoff template**

Create `pipeline-app/stage_templates/styleboard.md`:

```jinja
/{{ skill }}

Read the script at `{{ input_file }}` and lock this Short's two visual worlds: the
Register A/present world, the Register B/source-era world, the motif that crosses both,
and which Style Library entry each register binds to.
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}` — its thinker,
source and motif populate the register_b_* keys and `motif` directly rather than being
invented here.
{% endif %}
{{ user_message }}

Do NOT write any shot prompts and do NOT invent an `--sref` code. If a world has no
Style Library entry yet, raise it under DISCOVERY REQUESTS.

Write your final styleboard to `{{ raw_output_path }}` (overwrite it completely each time
you produce a new draft).
```

- [ ] **Step 5: Rewrite `visual.md` for two upstreams**

`visual.md` currently renders `{{ input_file }}` — the *first* upstream only — so the styleboard artifact would be hashed into frontmatter and never shown to the model. Follow the pattern `assembly.md` already uses. Replace the whole file with:

```jinja
/{{ skill }}

Read the following upstream artifacts and produce the visual prompt sheet: per-beat
Midjourney stills, any i2v (image-to-video) prompts for beats that need real motion, and
the cover/thumbnail decision.
{% for f in input_files %}
- `{{ f }}`
{% endfor %}

The styleboard artifact among those inputs owns the WORLD LOCK and the slot declarations.
Inherit them; do not re-emit the WORLD LOCK block into your sheet, and write every style
reference as a `{style:...}` slot rather than a literal `--sref` code.
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}` — carry forward
any citations or constraints it names.
{% endif %}
{{ user_message }}

Write your final prompt sheet to `{{ raw_output_path }}` (overwrite it completely each
time you produce a new draft).
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest pipeline-app/tests/ -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pipeline.yaml pipeline-app/stage_templates/ pipeline-app/tests/test_pipeline_config.py
git commit -m "feat(pipeline): add the styleboard stage and its kickoff templates"
```

---

### Task 11: Backfill `styleboard` rows into pre-existing projects

Without this, every project created before Task 10 is wedged: `create_project` materializes stage rows once, so those projects have no `styleboard` row, and `stages_to_unlock` requires **all** declared dependencies approved — so `visual` can never leave `locked`.

**Files:**
- Create: `pipeline-app/pipeline_app/migrations.py`
- Modify: `pipeline-app/pipeline_app/main.py`
- Test: `pipeline-app/tests/test_migrations.py`

**Interfaces:**
- Consumes: `db_mod.list_projects`, `db_mod.get_stage`, `db_mod.create_stage_row`, `artifacts.latest_artifact_path`, `artifacts.write_artifact`, `pipeline_config.stage_dir_name`, `state_machine.StageStatus`.
- Produces: `backfill_styleboard_rows(conn, repo_root, stage_defs) -> list[int]` returning the project ids it touched. Idempotent.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_migrations.py`:

```python
import sqlite3
from pathlib import Path

import pytest

from pipeline_app import db as db_mod
from pipeline_app.migrations import backfill_styleboard_rows
from pipeline_app.pipeline_config import StageDef

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "pipeline_app"

STAGE_DEFS = [
    StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02", depends_on=[]),
    StageDef(id="styleboard", skill="shorts-styleboard", dir_prefix="02b", depends_on=["scripting"]),
    StageDef(id="visual", skill="visual-prompts", dir_prefix="03",
             depends_on=["scripting", "styleboard"]),
]

LEGACY_SHEET = """\
=== VISUAL PROMPT SHEET — legacy ===

WORLD LOCK
  register_a_sport: club soccer
  register_a_signature_objects: goal net, corner flag

WHOLE-SHORT SETUP
  Aspect ratio: --ar 9:16
"""


@pytest.fixture
def conn(tmp_path):
    connection = sqlite3.connect(tmp_path / "test.db")
    connection.row_factory = sqlite3.Row
    connection.executescript((PACKAGE_DIR / "schema.sql").read_text(encoding="utf-8"))
    connection.commit()
    yield connection
    connection.close()


def _legacy_project(conn, repo_root, run_id, visual_status, sheet=None):
    project_id = db_mod.create_project(conn, run_id, "slug", "generic", "2026-07-01T00:00:00+00:00")
    db_mod.create_stage_row(conn, project_id, "scripting", "approved")
    db_mod.create_stage_row(conn, project_id, "visual", visual_status)
    visual_dir = repo_root / "runs" / run_id / "03-visual"
    visual_dir.mkdir(parents=True, exist_ok=True)
    if sheet is not None:
        (visual_dir / "artifact.v1.md").write_text(
            "---\nschema_version: 1\nstatus: final\n---\n\n" + sheet, encoding="utf-8"
        )
    return project_id


def test_backfill_inserts_a_styleboard_row_for_a_legacy_project(conn, tmp_path):
    pid = _legacy_project(conn, tmp_path, "legacy-1", "locked")
    assert backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS) == [pid]
    assert db_mod.get_stage(conn, pid, "styleboard") is not None


def test_backfill_approves_styleboard_when_a_world_lock_can_be_lifted(conn, tmp_path):
    pid = _legacy_project(conn, tmp_path, "legacy-2", "approved", sheet=LEGACY_SHEET)
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    row = db_mod.get_stage(conn, pid, "styleboard")
    assert row["status"] == "approved"

    written = tmp_path / "runs" / "legacy-2" / "02b-styleboard" / "artifact.v1.md"
    assert written.exists()
    assert "register_a_sport: club soccer" in written.read_text(encoding="utf-8")


def test_backfill_leaves_styleboard_ready_when_there_is_no_world_lock_to_lift(conn, tmp_path):
    pid = _legacy_project(conn, tmp_path, "legacy-3", "locked")
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)
    assert db_mod.get_stage(conn, pid, "styleboard")["status"] == "ready"


def test_backfill_is_idempotent(conn, tmp_path):
    _legacy_project(conn, tmp_path, "legacy-4", "locked")
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)
    assert backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS) == []


def test_backfilled_project_can_unlock_visual(conn, tmp_path):
    """The whole point: without the row, stages_to_unlock can never satisfy visual."""
    from pipeline_app.state_machine import stages_to_unlock

    pid = _legacy_project(conn, tmp_path, "legacy-5", "locked", sheet=LEGACY_SHEET)
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    rows = db_mod.list_stages(conn, pid)
    approved = {r["stage_id"] for r in rows if r["status"] == "approved"}
    assert "visual" in stages_to_unlock(STAGE_DEFS, approved)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest pipeline-app/tests/test_migrations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_app.migrations'`.

- [ ] **Step 3: Write the migration**

Create `pipeline-app/pipeline_app/migrations.py`:

```python
"""One-shot, idempotent schema/state migrations run at app startup.

Kept separate from db.py: db.py holds the durable query surface, this holds
corrections that exist only because the topology changed under projects that
were already on disk.
"""

import datetime
import re
import sqlite3
from pathlib import Path

from pipeline_app import artifacts, db as db_mod
from pipeline_app.pipeline_config import StageDef, stage_dir_name
from pipeline_app.state_machine import StageStatus

_WORLD_HEADING_RE = re.compile(r"^\s*WORLD LOCK\s*$")
_WORLD_ENTRY_RE = re.compile(r"^\s+([a-z][a-z0-9_]*)\s*:\s*(.+?)\s*$")

# Statuses meaning "this project already got past visual", so a styleboard row
# inserted now must be `approved` or visual would regress to unreachable.
_PAST_VISUAL = {
    StageStatus.APPROVED.value,
    StageStatus.AWAITING_REVIEW.value,
    StageStatus.STALE.value,
    StageStatus.NO_ARTIFACT.value,
}


def extract_world_lock_block(text: str) -> str | None:
    """The verbatim WORLD LOCK block from a legacy sheet, or None.

    Deliberately re-implemented here rather than imported from
    scripts/lint_prompt_sheet.py: that module returns a parsed dict, and this needs the
    original lines byte-for-byte so the synthetic artifact is a faithful copy of what the
    project actually rendered against.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not _WORLD_HEADING_RE.match(line):
            continue
        block = [line.strip()]
        for entry in lines[i + 1:]:
            if not _WORLD_ENTRY_RE.match(entry):
                break
            block.append(entry.rstrip())
        return "\n".join(block) if len(block) > 1 else None
    return None


def backfill_styleboard_rows(
    conn: sqlite3.Connection,
    repo_root: Path,
    stage_defs: list[StageDef],
) -> list[int]:
    """Give every pre-existing project the styleboard row the new topology requires.

    create_project materialises stage rows once, at creation, so a project made before
    styleboard existed has no row for it -- and stages_to_unlock requires ALL declared
    dependencies approved, so `visual` could never leave `locked` for that project.

    Where the project already produced a visual sheet, its WORLD LOCK block is lifted
    into a synthetic styleboard artifact and the row is approved, preserving the
    project's real world lock rather than blanking it.
    """
    stage_def = next((s for s in stage_defs if s.id == "styleboard"), None)
    if stage_def is None:
        return []

    visual_def = next((s for s in stage_defs if s.id == "visual"), None)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    touched: list[int] = []

    for project in db_mod.list_projects(conn):
        project_id = project["id"]
        if db_mod.get_stage(conn, project_id, "styleboard") is not None:
            continue

        run_dir = repo_root / "runs" / project["run_id"]
        world_block = None
        if visual_def is not None:
            visual_latest = artifacts.latest_artifact_path(run_dir / stage_dir_name(visual_def))
            if visual_latest is not None:
                _meta, body = artifacts.parse_frontmatter(
                    visual_latest.read_text(encoding="utf-8")
                )
                world_block = extract_world_lock_block(body)

        visual_row = db_mod.get_stage(conn, project_id, "visual")
        got_past_visual = visual_row is not None and visual_row["status"] in _PAST_VISUAL

        if world_block is not None:
            stage_dir = run_dir / stage_dir_name(stage_def)
            artifacts.write_artifact(
                stage_dir,
                1,
                {
                    "schema_version": 1,
                    "run_id": project["run_id"],
                    "stage": stage_def.skill,
                    "version": 1,
                    "status": "final",
                    "created_at": now,
                    "finalized_at": now,
                    "supersedes": None,
                    "depends_on": [],
                    "backfilled": True,
                },
                f"=== STYLEBOARD — {project['run_id']} (backfilled) ===\n\n"
                f"{world_block}\n\n"
                "BINDINGS\n"
                "  none — this styleboard was reconstructed from an existing prompt sheet's\n"
                "  WORLD LOCK block. Its shots carry literal --sref codes, not slots.\n\n"
                "DISCOVERY REQUESTS\n"
                "  none\n",
            )
            status = StageStatus.APPROVED.value
        elif got_past_visual:
            # Past visual but no liftable world lock: approve anyway rather than wedge a
            # project that is already finished. There is nothing to reconstruct.
            status = StageStatus.APPROVED.value
        else:
            scripting_row = db_mod.get_stage(conn, project_id, "scripting")
            status = (
                StageStatus.READY.value
                if scripting_row is not None
                and scripting_row["status"] == StageStatus.APPROVED.value
                else StageStatus.LOCKED.value
            )

        row_id = db_mod.create_stage_row(conn, project_id, "styleboard", status)
        if status == StageStatus.APPROVED.value:
            db_mod.update_stage_status(conn, row_id, status, approved_at=now)
        (run_dir / stage_dir_name(stage_def)).mkdir(parents=True, exist_ok=True)
        touched.append(project_id)

    return touched
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest pipeline-app/tests/test_migrations.py -v`
Expected: PASS.

- [ ] **Step 5: Wire the migration into startup**

In `pipeline-app/pipeline_app/main.py`, add the import:

```python
from pipeline_app import migrations
```

and call it in `create_app`, immediately after `app.state.conn` is assigned and **before** `reconcile_orphaned_turns` (which walks stage rows and must see a complete set):

```python
    app.state.backfilled_projects = migrations.backfill_styleboard_rows(
        app.state.conn, app.state.repo_root, app.state.stage_defs
    )
```

- [ ] **Step 6: Run the whole app suite**

Run: `python -m pytest pipeline-app/tests/ -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pipeline-app/pipeline_app/migrations.py pipeline-app/pipeline_app/main.py pipeline-app/tests/test_migrations.py
git commit -m "fix(pipeline): backfill styleboard rows so legacy projects can unlock visual"
```

---

### Task 12: Guard the provenance markers with a test

The spec review caught a false `[I]`→`[C]` upgrade in prose. Nothing in the repo would have caught it. This test would have.

**Files:**
- Create: `tests/test_skill_provenance.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing importable; a standalone guard.

- [ ] **Step 1: Write the test**

Create `tests/test_skill_provenance.py`:

```python
"""Guards CLAUDE.md's anti-generic guarantee at the two places it was actually broken.

The register system is `shorts-styleboard`'s own operational design `[I]`, not a corpus
finding. A design document in this repo once claimed it was `[C]`-cited and moved "with
its citations intact" -- there are no citations to keep. These tests make that class of
claim fail loudly rather than survive review.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / ".claude" / "skills"

REGISTERS = SKILLS / "shorts-styleboard" / "references" / "visual-registers.md"
MARKER_RE = re.compile(r"`\[(?:C|I|T|T-unverified)\]`|\[(?:C|I|T|T-unverified)\]")


def test_the_register_system_still_lives_with_styleboard():
    assert REGISTERS.exists(), "visual-registers.md must live with the skill that owns the world lock"


def test_the_register_system_is_still_marked_as_this_skills_own_design():
    text = REGISTERS.read_text(encoding="utf-8")
    assert "`[I]`" in text
    assert "operational design" in text, (
        "the register system is [I], not [C]; the disclaimer must survive any move"
    )


def test_the_corpus_gap_disclaimer_survives():
    text = REGISTERS.read_text(encoding="utf-8")
    assert "corpus" in text.lower()
    assert re.search(r"corpus (has nothing|says nothing|is thin)", text, re.IGNORECASE), (
        "the file must keep stating what the corpus does NOT cover"
    )


def test_register_contract_bullets_all_carry_a_marker():
    """Every normative bullet under the Register A/B contracts names its provenance."""
    text = REGISTERS.read_text(encoding="utf-8")
    section = text.split("## 3. Register A")[1].split("## 5. PLATE")[0]
    unmarked = [
        line.strip()
        for line in section.splitlines()
        if line.strip().startswith("- **") and not MARKER_RE.search(line)
    ]
    assert unmarked == [], f"unmarked normative lines: {unmarked}"


def test_styleboard_skill_does_not_claim_corpus_backing_for_the_register_system():
    text = (SKILLS / "shorts-styleboard" / "SKILL.md").read_text(encoding="utf-8")
    assert "own operational design `[I]`" in text
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/test_skill_provenance.py -v`
Expected: PASS. If `test_register_contract_bullets_all_carry_a_marker` fails, a bullet lost its marker during Task 7's move — restore it rather than relaxing the test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_skill_provenance.py
git commit -m "test: guard the register system's [I] provenance markers"
```

---

### Task 13: Update repo documentation and `.gitignore`

**Files:**
- Modify: `CLAUDE.md`, `README.md`, `.gitignore`

- [ ] **Step 1: Find every "six skills" claim**

```bash
grep -rn "six skills\|six-skill\|six atomic" CLAUDE.md README.md .claude/skills/ | grep -v cowork-plugin
```

- [ ] **Step 2: Update `CLAUDE.md`**

Change the opening line "using six atomic Claude Code skills" to "using seven atomic Claude Code skills", and add a row to the skills table between `shorts-scripting` and `voiceover-brief`:

```markdown
| `shorts-styleboard` | Script → world lock | the script | world lock + Style Library bindings (Gate C reads its `WORLD LOCK`) |
```

Then update the `visual-prompts` row's Input column from `the script` to `the script + the styleboard`.

In the "Conventions" section, update the Gate C bullet to name the new invocation:

```markdown
- The `visual-prompts` output format is machine-parseable and enforced by
  `scripts/lint_prompt_sheet.py` (Gate C). Run it as
  `python scripts/lint_prompt_sheet.py <sheet> --styleboard <styleboard>` on any emitted sheet
  before handing off to `shorts-assembly`; a failing gate blocks emission. The sheet carries
  `{style:...}` slots, never literal `--sref` codes — C16 rejects an invented code and C17
  rejects a shot with no style mechanism at all. Tests: `python -m pytest tests/ -v`.
```

- [ ] **Step 3: Update `README.md`**

Apply the same six→seven correction wherever the pipeline is enumerated.

- [ ] **Step 4: Add `Generated Assets/` to `.gitignore`**

Plan B's console writes hundreds of PNGs there. The directory is currently untracked but *not* ignored, so one `git add .` would commit them. Append to `.gitignore`, after the `runs/` block:

```gitignore
# Rendered Midjourney assets for each Short — large binaries, local only.
# Untracked but previously un-ignored, so a stray `git add .` would have committed them.
Generated Assets/
```

- [ ] **Step 5: Verify nothing is newly ignored that was tracked**

```bash
git status --short
git ls-files "Generated Assets" | head
```

Expected: the second command prints nothing (the directory was never tracked).

- [ ] **Step 6: Run every suite one final time**

```bash
python -m pytest tests/ -v
python -m pytest pipeline-app/tests/ -v
```

Expected: PASS for both.

- [ ] **Step 7: Commit**

```bash
git add CLAUDE.md README.md .gitignore
git commit -m "docs: seven-stage pipeline, new Gate C invocation, ignore Generated Assets"
```

---

## Done when

- `python -m pytest tests/ -v` and `python -m pytest pipeline-app/tests/ -v` both pass.
- Both migrated fixtures print `Gate C: PASS`:
  - `python scripts/lint_prompt_sheet.py tests/fixtures/passing_sheet.md --styleboard tests/fixtures/passing_styleboard.md`
  - `python scripts/lint_prompt_sheet.py tests/fixtures/worked_example_sheet.md --styleboard tests/fixtures/worked_example_styleboard.md`
- `python scripts/lint_prompt_sheet.py tests/fixtures/legacy_do_less_sheet.md` fails with C16 findings naming `SREF-RGS-A-DL01`.
- No file under `.claude/skills/visual-prompts/` contains a literal `--sref <digits>` or emits a `WORLD LOCK` block.
- Starting the app against the existing `pipeline.db` inserts a `styleboard` row for all five pre-existing projects and leaves `visual` unlockable.
