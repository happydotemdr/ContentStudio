"""Gate C — deterministic shot-variety lint for ContentStudio visual prompt sheets.

Parses the copy-paste sheet format emitted by the `visual-prompts` skill and enforces
the dual-register visual system's variety, world-lock, density and format rules.

Stdlib only. See docs/superpowers/specs/2026-07-28-dual-register-visual-system-design.md

Exit codes:
    0  EXIT_PASS               no findings
    1  EXIT_FINDINGS            the gate found findings -- the sheet is the problem
    2  EXIT_USAGE                argparse only (bad CLI invocation)
    3  EXIT_UNREADABLE_INPUT     a named path (sheet/styleboard/Library) could not be read
    4  EXIT_UNPARSEABLE          the sheet was read but yielded no shots
    5  EXIT_MISSING_DEPENDENCY   a required companion artifact is absent or empty
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SHOT_HEADING_RE = re.compile(
    r"^###\s+Shot\s+(\d+)\s+—\s+(.+?)\s+·\s+Register\s+(A|B|PLATE)"
    r"\s+·\s+([A-Z-]+)\s+·\s+([A-Z-]+)\s+·\s+([A-Z]+)\s*$"
)
OPEN_FENCE_RE = re.compile(r"^\s*```text\s*$")
CLOSE_FENCE_RE = re.compile(r"^\s*```\s*$")
WORLD_HEADING_RE = re.compile(r"^\s*WORLD LOCK\s*$")
WORLD_ENTRY_RE = re.compile(r"^\s+([a-z][a-z0-9_]*)\s*:\s*(.+?)\s*$")

# Deliberately loose: anything an author could plausibly have meant as a shot
# heading. A line matching this but NOT SHOT_HEADING_RE is a hard finding, never
# a skipped line -- skipping it removed the shot from all of C1-C20 and Gate C
# printed PASS (finding C-70).
LOOSE_SHOT_HEADING_RE = re.compile(r"^\s*#{2,4}\s*Shot\b", re.IGNORECASE)
LOOSE_COVER_HEADING_RE = re.compile(r"^\s*#{2,4}\s*Cover\b", re.IGNORECASE)
SHOT_COUNT_RE = re.compile(r"^\s*SHOT COUNT:\s*(\d+)\s*$", re.IGNORECASE)

NO_TEXT_MARKER = "No Text."

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
    in_fence = False
    seen_world_block = False

    i = 0
    while i < len(lines):
        line = lines[i]

        if OPEN_FENCE_RE.match(line):
            in_fence = True
            i += 1
            continue
        if in_fence:
            if CLOSE_FENCE_RE.match(line):
                in_fence = False
            i += 1
            continue

        count = SHOT_COUNT_RE.match(line)
        if count:
            declared = int(count.group(1))
            i += 1
            continue

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


def parse_world_lock(text: str) -> dict[str, str]:
    """The WORLD LOCK block from any file that carries one.

    After the styleboard split the block lives in the styleboard artifact rather than
    the prompt sheet, but the block's syntax is identical in both, so parse_sheet's
    world-lock walk is reused rather than duplicated.
    """
    _shots, world = parse_sheet(text)
    return world


COVER_HEADING_RE = re.compile(
    r"^###\s+Cover\s+—\s+(.+?)\s+·\s+Register\s+(A|B|PLATE)"
    r"\s+·\s+([A-Z-]+)\s+·\s+([A-Z-]+)\s+·\s+([A-Z]+)\s*$"
)
# Matched per-line (see declares_cover_reuse), not with re.search over the whole
# document -- a document-wide search would also match this text sitting inside a
# ```text prompt fence or in unrelated prose, silently satisfying C19 with no real
# cover decision made.
# Extended to optionally capture an explicit shot number ("...beat still #1") so
# the reuse declaration can be resolved to a real shot (finding C-86) rather than
# merely detected as present.
COVER_REUSE_RE = re.compile(r"^\s*Cover\s*=\s*Hook\b[^#\n]*(?:#\s*(\d+))?", re.IGNORECASE)


def cover_heading_present(text: str) -> bool:
    """Whether a '### Cover — ...' heading exists anywhere, regardless of whether
    its prompt fence could be read. Distinguishes 'no cover at all' from 'a cover
    heading exists but ships unlinted' (finding C-78)."""
    return any(COVER_HEADING_RE.match(line) for line in text.splitlines())


def _cover_reuse_declaration(text: str) -> re.Match | None:
    """The 'Cover = Hook ...' declaration line, matched outside any prompt fence, or
    None. Same fence-aware scan as declares_cover_reuse, but returns the match
    itself so the caller can resolve which shot is being reused (finding C-86)."""
    in_fence = False
    for line in text.splitlines():
        if OPEN_FENCE_RE.match(line):
            in_fence = True
            continue
        if CLOSE_FENCE_RE.match(line):
            in_fence = False
            continue
        if in_fence:
            continue
        match = COVER_REUSE_RE.match(line)
        if match:
            return match
    return None


def _hook_shot_for_reuse(shots: list[Shot], match: "re.Match[str]") -> Shot | None:
    """The shot a 'Cover = Hook ...' declaration reuses, or None if it names nothing
    real. Tries the explicit shot number first (if the declaration carried one),
    then falls back to any shot whose beat starts with 'Hook'."""
    index_str = match.group(1)
    if index_str is not None:
        named = next((s for s in shots if s.index == int(index_str)), None)
        if named is not None:
            return named
    return next((s for s in shots if s.beat.startswith("Hook")), None)


def parse_cover(text: str) -> Shot | None:
    """The dedicated cover prompt, as a Shot with index 0, or None.

    None means either 'the cover reuses the Hook still' (a legitimate branch — see
    declares_cover_reuse), 'no cover block at all' (C19), or 'more than one cover
    block' -- that last case is deliberately surfaced by check_cover_present, not
    here: parse_cover's return type stays Shot | None so lint_cover and every
    existing caller are unaffected, and only the first block is ever linted for
    format/density/style. Index 0 keeps the cover distinguishable from every real
    shot in a finding message.
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


def _count_cover_headings(text: str) -> int:
    """How many '### Cover — ...' lines the sheet carries, stale drafts included."""
    return sum(1 for line in text.splitlines() if COVER_HEADING_RE.match(line))


def declares_cover_reuse(text: str) -> bool:
    """True if the sheet states, outside any prompt fence, that the cover reuses the Hook.

    Deliberately NOT confined to a 'COVER / THUMBNAIL' section header: the line is a
    fixed, specific declaration string ('Cover = Hook...') that nothing else in the
    sheet format would produce by accident.
    """
    return _cover_reuse_declaration(text) is not None


def check_cover_present(text: str) -> list[Finding]:
    """C19: the cover decision is stated, never silently omitted -- and stated once.

    prompt-sheet-format.md §7 already requires this of every emitted sheet `[I]`. A
    sheet with two '### Cover — ...' headings (a stale draft left behind plus the
    real one) is reported rather than resolved silently. A cover heading whose
    prompt fence cannot be read is reported as present-but-unlinted (C-78), not
    conflated with no cover at all. A 'Cover = Hook ...' reuse declaration must name
    a shot that actually exists (C-86), not just be present as text.
    """
    findings: list[Finding] = []
    heading_count = _count_cover_headings(text)
    if heading_count > 1:
        findings.append(
            Finding(
                "C19",
                None,
                f"{heading_count} '### Cover — ...' blocks found; a sheet must state "
                "exactly one cover decision. Remove the stale draft.",
            )
        )

    if parse_cover(text) is not None:
        return findings

    if cover_heading_present(text):
        findings.append(
            Finding(
                "C19",
                None,
                "a '### Cover — ...' heading is present but its prompt fence is "
                "unreadable (expected ```text); the cover would ship unlinted",
            )
        )
        return findings

    reuse_match = _cover_reuse_declaration(text)
    if reuse_match is not None:
        shots, _world = parse_sheet(text)
        if _hook_shot_for_reuse(shots, reuse_match) is not None:
            return findings
        findings.append(
            Finding(
                "C19",
                None,
                "'Cover = Hook ...' is declared but no Hook shot exists to reuse; "
                "name a real shot or emit a '### Cover — ...' block instead",
            )
        )
        return findings

    findings.append(
        Finding(
            "C19",
            None,
            "no cover decision: emit a '### Cover — ...' block, or state "
            "'Cover = Hook beat still #1' explicitly",
        )
    )
    return findings


def lint_cover(
    cover: Shot, world: dict[str, str], *, library: dict[str, str] | None = None
) -> list[Finding]:
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
        *check_slot_labels(single, world, library),
    ]


def _read_fenced_prompt(lines: list[str], start: int) -> tuple[list[str], int]:
    """Read the next ```text fence after `start`. Returns (non-empty lines, index after it)."""
    i = start
    while i < len(lines) and not OPEN_FENCE_RE.match(lines[i]):
        if (SHOT_HEADING_RE.match(lines[i]) or COVER_HEADING_RE.match(lines[i])
                or LOOSE_COVER_HEADING_RE.match(lines[i])
                or LOOSE_SHOT_HEADING_RE.match(lines[i])):
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


MAX_PLATE_SHARE = 1 / 3


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


REGISTER_A_SHOT_CLASSES = {"ESTABLISHING", "ACTION-ADJACENT", "DETAIL", "HUMAN-COST"}
REGISTER_B_SHOT_CLASSES = {"FIGURE", "WORLD", "ARTIFACT"}
VALID_SCALES = {"XWIDE", "WIDE", "MID-WIDE", "MID", "CLOSE", "MACRO"}
VALID_CAMERA_HEIGHTS = {"LOW", "EYE", "HIGH", "OVERHEAD"}


def check_vocabulary(shots: list[Shot]) -> list[Finding]:
    """C15: shot class, scale and camera height are members of their closed sets.

    A typo (`MIDWIDE` for `MID-WIDE`) doesn't just go unreported here -- left
    unchecked it would silently dodge C2's adjacent-scale-repeat check and inflate
    C4's distinct-scale count, making a monotonous sheet *more* likely to pass.
    """
    findings: list[Finding] = []

    for shot in shots:
        if shot.register == "PLATE":
            if shot.shot_class != "PLATE":
                findings.append(
                    Finding("C15", shot.index, f"PLATE shot class must be 'PLATE', got {shot.shot_class!r}")
                )
        elif shot.register == "A":
            if shot.shot_class not in REGISTER_A_SHOT_CLASSES:
                findings.append(
                    Finding(
                        "C15",
                        shot.index,
                        f"shot class {shot.shot_class!r} is not one of Register A's closed set "
                        f"{sorted(REGISTER_A_SHOT_CLASSES)!r}",
                    )
                )
        elif shot.register == "B":
            if shot.shot_class not in REGISTER_B_SHOT_CLASSES:
                findings.append(
                    Finding(
                        "C15",
                        shot.index,
                        f"shot class {shot.shot_class!r} is not one of Register B's closed set "
                        f"{sorted(REGISTER_B_SHOT_CLASSES)!r}",
                    )
                )

        if shot.scale not in VALID_SCALES:
            findings.append(
                Finding(
                    "C15",
                    shot.index,
                    f"scale {shot.scale!r} is not one of the closed set {sorted(VALID_SCALES)!r}",
                )
            )
        if shot.camera_height not in VALID_CAMERA_HEIGHTS:
            findings.append(
                Finding(
                    "C15",
                    shot.index,
                    f"camera height {shot.camera_height!r} is not one of the closed set "
                    f"{sorted(VALID_CAMERA_HEIGHTS)!r}",
                )
            )

    return findings


# Widened from the two/three literals the audit found (finding C-84). Source: the
# same [I]-marked contract these were drawn from --
# .claude/skills/shorts-styleboard/references/visual-registers.md:47 (Register A
# world lock) and :64 (Register B banned vocabulary). The terms below are synonyms
# of those same two rules, not new craft claims. P13 mirrors this list back into
# that reference; see this plan's cross-package note.
# "empty field" deliberately omitted: tests/fixtures/passing_sheet.md Shot 3 uses
# that exact phrase in a fully-named, fully-detailed Register A venue ("...dwarfed
# by the empty field..." after naming the pitch, goal net, and corner flag) --
# a legitimate atmospheric detail, not the generic/unnamed-venue failure C9 exists
# to catch. The fixture is outside this task's edit scope, so the term is dropped
# rather than the false positive shipped.
BANNED_REGISTER_A_STRINGS = (
    "empty gym", "empty youth gym", "empty pitch", "empty stadium",
    "empty court", "vacant gym", "vacant pitch", "deserted gym", "deserted pitch",
    "abandoned gym", "abandoned pitch", "generic gym", "generic field",
)
MIN_SIGNATURE_OBJECTS = 2
# The two tightest entries in VALID_SCALES: an extreme close-up (framing a face
# or a single detail) cannot credibly hold two named large props in frame. Every
# wider scale in both real MIGRATED_PAIRS fixtures (including their covers)
# names >= MIN_SIGNATURE_OBJECTS; only CLOSE/MACRO shots ever sit at 1. See T21.
TIGHT_SCALES_ONE_OBJECT_FLOOR = frozenset({"CLOSE", "MACRO"})
BANNED_REGISTER_B_STRINGS = (
    "dslr", "shot on 35mm film", "documentary", "photorealistic", "photographic",
    "photograph", "bokeh", "shallow depth of field", "depth of field", "leica",
    "kodachrome", "cinematic still", "film still", "lens flare", "telephoto",
    "wide-angle lens", "macro lens", "iso ",
)
BANNED_REGISTER_B_PATTERNS = (
    re.compile(r"\d+\s*mm"),
    re.compile(r"\bf/\d"),
)


def check_world_lock(shots: list[Shot], world: dict[str, str]) -> list[Finding]:
    """C8-C10: the world lock and the register vocabulary separation.

    C8 is a mention check over the world-lock terms (word-boundary matched,
    plural-tolerant), not a depiction check -- it confirms the sport and at
    least MIN_SIGNATURE_OBJECTS signature objects are named in the prompt
    text. The floor drops to 1 for TIGHT_SCALES_ONE_OBJECT_FLOOR shots
    (CLOSE, MACRO): an extreme close-up can only credibly hold one named
    prop in frame, so a 2-object floor there would demand incoherent prose
    rather than close a real evasion (see the T21 report for the fixture
    evidence behind this carve-out).
    """
    findings: list[Finding] = []
    sport = world.get("register_a_sport", "").strip().lower()
    objects = [o.lower() for o in signature_objects(world)]

    for shot in shots:
        body = prompt_body(shot).lower()
        full_prompt = shot.prompt.lower()

        if shot.register == "A":
            if not sport:
                findings.append(
                    Finding("C8", shot.index, "world lock declares no register_a_sport")
                )
            elif not re.search(rf"\b{re.escape(sport)}\b", body):
                findings.append(
                    Finding("C8", shot.index, f"Register A prompt does not name the sport {sport!r}")
                )
            matched_objects = [obj for obj in objects if re.search(rf"\b{re.escape(obj)}s?\b", body)]
            required_objects = (
                1 if shot.scale in TIGHT_SCALES_ONE_OBJECT_FLOOR else MIN_SIGNATURE_OBJECTS
            )
            if len(matched_objects) < required_objects:
                findings.append(
                    Finding(
                        "C8",
                        shot.index,
                        f"Register A prompt mentions {len(matched_objects)} of the signature "
                        f"objects {objects!r}; needs at least {required_objects}. C8 is a "
                        "mention check over the world-lock terms, not a depiction check.",
                    )
                )
            for banned in BANNED_REGISTER_A_STRINGS:
                if banned in full_prompt:
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
                if banned in full_prompt:
                    findings.append(
                        Finding(
                            "C10",
                            shot.index,
                            f"photographic vocabulary {banned!r} in Register B collapses the "
                            "two registers into one look",
                        )
                    )
            for pattern in BANNED_REGISTER_B_PATTERNS:
                match = pattern.search(full_prompt)
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


MAX_SHARED_CLAUSES = 5
MIN_CLAUSES = 10
MIN_WORDS = 60
MAX_CLAUSE_SIMILARITY = 0.6
MIN_DISTINCT_TOKEN_RATIO = 0.55


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


def check_prompt_clone(shots: list[Shot]) -> list[Finding]:
    """C11: anti-clone. Consistency belongs in --sref, not a copied prompt body.

    Two clauses are "shared" if they are near-duplicates (Jaccard token overlap),
    not byte-identical -- one appended word per clause used to take a 12-clause
    exact clone to 0 shared clauses while changing no visual idea (finding C-82).
    Each of `left`'s clauses can satisfy at most one match, so padding `right` with
    repeats of the same clause cannot inflate the count past `left`'s own clause count.
    """
    findings: list[Finding] = []
    for left, right in _pairs(shots):
        available = list(body_clauses(left))
        shared: list[str] = []
        for r_clause in body_clauses(right):
            for i, l_clause in enumerate(available):
                if _clauses_are_near_duplicates(l_clause, r_clause):
                    shared.append(l_clause)
                    del available[i]
                    break
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
    """C12: the prompt body clears a clause floor, a word floor and a repetition floor.

    Deliberately NOT a nine-layer content check -- nothing here maps a clause to a
    layer, and the previous docstring's claim that it did was false (finding C-83).
    What it does catch is the shape of a padded body: a body whose distinct-token
    ratio falls below MIN_DISTINCT_TOKEN_RATIO is repeating itself to clear the
    floors rather than describing anything.
    """
    findings: list[Finding] = []
    for shot in shots:
        clause_count = len(body_clauses(shot))
        if clause_count < MIN_CLAUSES:
            findings.append(
                Finding(
                    "C12",
                    shot.index,
                    f"{clause_count} clause(s); need >= {MIN_CLAUSES}. The body must carry "
                    "concrete renderable content.",
                )
            )
        words = body_word_count(shot)
        if words < MIN_WORDS:
            findings.append(
                Finding("C12", shot.index, f"{words} words in body; need >= {MIN_WORDS}")
            )
        tokens = re.findall(r"[a-z0-9]+", _body_without_no_text(shot).lower())
        if tokens and len(set(tokens)) / len(tokens) < MIN_DISTINCT_TOKEN_RATIO:
            findings.append(Finding(
                "C12", shot.index,
                f"{len(set(tokens))} distinct tokens in {len(tokens)} words "
                f"(ratio {len(set(tokens)) / len(tokens):.2f}, need >= "
                f"{MIN_DISTINCT_TOKEN_RATIO}); the body is padding to clear the "
                "length floor, not describing the shot.",
            ))
    return findings


def check_prompt_quality(shots: list[Shot]) -> list[Finding]:
    """C11-C12, kept as one entry point for callers that want both."""
    return [*check_prompt_clone(shots), *check_prompt_density(shots)]


def _pairs(shots: list[Shot]):
    for i, left in enumerate(shots):
        for right in shots[i + 1 :]:
            yield left, right


STYLIZE_RE = re.compile(r"--(?:s|stylize)\s+(\d+)")
# PLATE carries no register look, so it has no --raw requirement and no register
# band -- but it is still a render, and a render with no --s is not a specified
# render. The band is wide and low: a plate is a ground, not a stylised image.
REGISTER_BANDS = {"A": (80, 120, True), "B": (400, 700, False), "PLATE": (0, 250, False)}
# A bare version number like "8.2" -- the only non-URL shape allowed to carry a period.
URL_OR_VERSION_TOKEN_RE = re.compile(r"^\d+\.\d+$")
# The format's aspect ratio, as a module constant so a future non-vertical format
# overrides it in one place. C13 previously asserted only that --ar was *present*.
REQUIRED_ASPECT_RATIO = "9:16"
AR_FLAG_RE = re.compile(r"--ar\s+(\S+)")


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
        aspect = AR_FLAG_RE.search(flags)
        if aspect is None:
            findings.append(Finding("C13", shot.index, "no --ar in the parameter block"))
        elif aspect.group(1) != REQUIRED_ASPECT_RATIO:
            findings.append(Finding(
                "C13", shot.index,
                f"--ar {aspect.group(1)} is not the required {REQUIRED_ASPECT_RATIO}; "
                "a Short is vertical and every asset must be generated that way.",
            ))
        for punctuation in (",", ";", "."):
            if punctuation not in flags:
                continue
            # A period is legal inside a URL value (--oref https://.../a1b2.png) or a
            # version number (--v 8.2); only flag periods outside those two shapes.
            if punctuation == "." and all(
                token.lower().startswith("http") or URL_OR_VERSION_TOKEN_RE.fullmatch(token)
                for token in flags.split()
                if punctuation in token
            ):
                continue
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


SREF_FLAG_RE = re.compile(r"--sref\b((?:\s+(?!--)\S+)*)")
P_FLAG_RE = re.compile(r"--p\b((?:\s+(?!--)\S+)*)")
STYLE_SLOT_RE = re.compile(r"\{style:([a-z][a-z0-9_]*)\}")
CHAR_SLOT_RE = re.compile(r"\{char:([a-z][a-z0-9_]*)\}")
VALID_SREF_VALUE_RE = re.compile(r"^(?:\d+|random|https?://\S+)$")
# A legitimate --p value is an opaque pID/mID/resolved code -- alphanumeric, no
# separators (see midjourney-prompting/references/parameters.md:49 and the corpus
# example `--p m72678`). An invented placeholder reads like a human-authored label
# (`mj-INVENTED-01`, hyphens and spelled-out words); real codes don't look like that.
VALID_P_VALUE_RE = re.compile(r"^[A-Za-z0-9]+$")


def _check_style_flag_values(
    shots: list[Shot], flag_re: re.Pattern, valid_value_re: re.Pattern, flag_name: str
) -> list[Finding]:
    """Shared body for the --sref and --p value checks (both C16).

    A flag written with no value at all (`--sref` with nothing after it, or before
    the next flag) fails here too -- it references nothing, which is the same defect
    as an invented placeholder one step removed. `--p` is the one exception: a bare
    `--p` with no value is Midjourney's own syntax for "apply my active personalization
    profile" and is legitimate, so an empty capture for `--p` is not flagged.
    """
    findings: list[Finding] = []
    for shot in shots:
        for match in flag_re.finditer(prompt_flags(shot)):
            stack = match.group(1).strip()
            if not stack:
                if flag_name == "--sref":
                    findings.append(
                        Finding(
                            "C16",
                            shot.index,
                            f"{flag_name} has no value; a bare {flag_name} references "
                            "nothing, the same defect as an invented placeholder code",
                        )
                    )
                continue
            for value in stack.split():
                if STYLE_SLOT_RE.fullmatch(value) or CHAR_SLOT_RE.fullmatch(value):
                    findings.append(
                        Finding(
                            "C16",
                            shot.index,
                            f"slot {value} used as an {flag_name} value; a slot expands to "
                            f"the entire flag group, so write it on its own, not after {flag_name}",
                        )
                    )
                elif not valid_value_re.match(value):
                    findings.append(
                        Finding(
                            "C16",
                            shot.index,
                            f"{flag_name} value {value!r} is not a plausible code. "
                            "A placeholder here means no real style code was ever harvested.",
                        )
                    )
    return findings


def check_style_reference(shots: list[Shot]) -> list[Finding]:
    """C16: every literal --sref/--p value is a real Midjourney style reference.

    Sheets have shipped with invented placeholders (`--sref SREF-RGS-A-DL01`,
    `--p mj-INVENTED-01`) that cannot be pasted into Midjourney -- the identical
    defect one flag over. A --sref code is a number, a URL, or the literal `random`;
    a --p value is an opaque pID/mID/resolved code (alphanumeric, no separators) --
    anything else means no code was ever harvested. Midjourney also supports
    stacking a second code onto an existing --sref (`--sref A B`) -- every
    space-separated value up to the next flag is checked, not just the first. A
    flag written with no value at all also fails (see `_check_style_flag_values`).
    """
    return [
        *_check_style_flag_values(shots, SREF_FLAG_RE, VALID_SREF_VALUE_RE, "--sref"),
        *_check_style_flag_values(shots, P_FLAG_RE, VALID_P_VALUE_RE, "--p"),
    ]


def check_style_mechanism(shots: list[Shot]) -> list[Finding]:
    """C17: every non-PLATE shot carries a {style:...} slot.

    Only a {style:...} slot counts. A literal --sref (however plausible its digits)
    and a --p profile are both unresolvable against the Library, so a sheet carrying
    them declares no slots, C20 never runs, and Gate C passes a Short whose look is
    unrecorded (findings C-79, C-80). The slot is the one mechanism that has a single
    resolution path, and that path is C20.

    C16 still exists alongside this: it validates the *shape* of any literal --sref
    or --p an author writes next to the slot (or in place of it, before this check
    catches that) — a fabricated code, a slot-string misused as a literal value, and
    so on. C16 answers "is this literal well-formed"; C17 answers "is there a
    recorded lock at all". A well-formed literal no longer satisfies C17 on its own.

    PLATE shots are exempt — they are subject-free background plates with no register
    look to lock (visual-registers.md §5).
    """
    findings: list[Finding] = []
    for shot in shots:
        if shot.register == "PLATE":
            continue
        flags = prompt_flags(shot)
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
    return findings


SLOT_KINDS = (
    (STYLE_SLOT_RE, "style", "slot_"),
    (CHAR_SLOT_RE, "char", "slot_char_"),
)
# A legitimate slot_* value is a Style Library entry label -- lowercase kebab-case,
# e.g. `rgs-present-soccer-a` (styleboard-format.md's "why the code is not written
# here" section). The code itself is resolved later, at render time, against the
# Library -- writing it into the styleboard moves the invented-code defect one
# artifact upstream instead of removing it, so anything that looks like a raw
# Midjourney code (numeric, a URL, `random`) or an invented uppercase/hyphenated
# placeholder (`SREF-RGS-A-DL01`, `mj-INVENTED-01`) fails here.
VALID_SLOT_VALUE_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def check_slots(shots: list[Shot], world: dict[str, str]) -> list[Finding]:
    """C18: slot tokens are declared in the world lock, sit in flag position, and
    are bound to a real Style Library label rather than an invented code.

    Position is decided from each match's own offset in shot.prompt, not from whether
    the slot's name happens to appear anywhere in the flags -- a name-membership check
    would silently accept a mis-positioned copy in the body as long as a second,
    correctly-placed copy of the same name also existed in the flags (a plausible
    authoring mistake: slot appended at the end, old copy in the body never deleted).

    prompt_body/prompt_flags split a prompt at the first occurrence of ' --', and a slot
    token does not begin with '--'. A match whose offset falls before that split point
    lands in the prompt BODY, where it would both fail C13's 'No Text. is last' rule and
    be sent to Midjourney as literal prose -- so it is flagged regardless of any other
    occurrence of the same name elsewhere in the prompt.
    """
    findings: list[Finding] = []
    for shot in shots:
        # Recompute the same split point prompt_body/prompt_flags use, rather than
        # re-locating prompt_flags(shot)'s return value inside shot.prompt afterwards:
        # that string is only guaranteed to be *a* suffix of shot.prompt, and searching
        # for it with str.index() would find the first matching span, which need not be
        # the real flag boundary if identical text also occurs earlier (e.g. a stray
        # copy of the same flag text sitting in the body).
        flags_start = shot.prompt.find(" --")
        for pattern, kind, prefix in SLOT_KINDS:
            for match in pattern.finditer(shot.prompt):
                name = match.group(1)
                if flags_start == -1 or match.start() < flags_start:
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
                    continue
                value = world[key].strip()
                if not VALID_SLOT_VALUE_RE.match(value):
                    findings.append(
                        Finding(
                            "C18",
                            shot.index,
                            f"{key!r} = {value!r} looks like a raw Midjourney style code or an "
                            "invented placeholder, not a Style Library entry label. A slot value "
                            "must be a label like 'rgs-present-soccer-a' -- the code itself is "
                            "resolved later, at render time, against the Library.",
                        )
                    )
    return findings


# The Library's `## Entry format` section documents an entry's shape with a literal
# `### <label>` line inside a fence, so a document-wide `^### ` scan would ingest the
# placeholder as a real entry. The walk is scoped to `## Entries` and every heading
# must match VALID_SLOT_VALUE_RE -- the same pattern C18 uses on the styleboard side,
# reused rather than restated so the two halves of "is this a label" cannot drift.
ENTRY_HEADING_RE = re.compile(r"^###\s+(\S+)\s*$")
LIBRARY_CODE_RE = re.compile(r"^\s*code:\s*(.+?)\s*$")


def parse_style_library_checked(text: str) -> tuple[dict[str, str], list[Finding]]:
    """Every entry label in docs/style-library.md, mapped to its harvested code, plus
    the parse layer's own rejects.

    The code is carried for reporting only -- C20 asks whether a label *exists*, not
    whether it has been harvested yet. An entry with `code: UNHARVESTED`, or a
    `scope: per-short` entry whose codes live in a table rather than a `code:` line,
    maps to a falsy code and still counts as present: Gate C runs on the sheet, before
    any render, so binding to a recorded-but-unharvested world is a legitimate
    intermediate state. What C20 catches is a label naming no entry at all.

    An entry heading that fails VALID_SLOT_VALUE_RE (an annotation, capitalization, a
    stray character) used to be silently dropped -- the parse looked complete and C20
    failed every sheet binding the missing label, blaming the sheet for a Library typo
    (finding C-76). An unterminated fence silently dropped every entry after it, the
    same way.
    """
    library: dict[str, str] = {}
    findings: list[Finding] = []
    in_entries = False
    in_fence = False
    label: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            # Inside an entry's own block: take the first `code:` line, so a later
            # commented-out or superseded value cannot overwrite the live one.
            if in_entries and label is not None and not library[label]:
                code = LIBRARY_CODE_RE.match(line)
                if code:
                    library[label] = code.group(1)
            continue
        if stripped.startswith("## "):
            in_entries = stripped == "## Entries"
            label = None
            continue
        if not in_entries:
            continue
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
    return library, findings


def parse_style_library(text: str) -> dict[str, str]:
    """Every entry label in docs/style-library.md, mapped to its harvested code.

    Dict-only wrapper kept for pipeline_app.gates.py:111's existing call site (package
    P3, frozen interface per this plan's §6.1). Use parse_style_library_checked for the
    fail-closed variant that also reports what it had to drop.
    """
    library, _findings = parse_style_library_checked(text)
    return library


def check_slot_labels(
    shots: list[Shot], world: dict[str, str], library: dict[str, str] | None
) -> list[Finding]:
    """C20: each slot's declared value names an entry that actually exists.

    C18 checks that a `slot_*` value *looks* like a Library label. It cannot check that
    the label *exists*, because nothing parsed the Library -- so a typo cleared Gate C
    and failed at paste time, when a human pasted a token that resolved to nothing.
    That was not hypothetical: the Library's Register B entry was created as
    `rgs-source-era-b` while all fourteen consumers, both green fixtures included, bound
    `rgs-sourceera-painterly-b`.

    Deliberately silent on everything C18 already owns -- a slot in body position, an
    undeclared slot, and a value shaped like an invented code all return early. An
    invented code is trivially absent from the Library too, and reporting it twice would
    point the author at the wrong fix: the problem is the invented code, not a missing
    entry.
    """
    if library is None:
        return []
    known = ", ".join(sorted(library)) or "(the Library has no entries)"
    findings: list[Finding] = []
    for shot in shots:
        flags_start = shot.prompt.find(" --")
        for pattern, _kind, prefix in SLOT_KINDS:
            for match in pattern.finditer(shot.prompt):
                if flags_start == -1 or match.start() < flags_start:
                    continue
                key = f"{prefix}{match.group(1)}"
                value = world.get(key, "").strip()
                if not value or not VALID_SLOT_VALUE_RE.match(value):
                    continue
                if value in library:
                    continue
                findings.append(
                    Finding(
                        "C20",
                        shot.index,
                        f"the styleboard's WORLD LOCK binds {key} to {value!r}, which is not "
                        f"an entry in docs/style-library.md — fix the label in the STYLEBOARD, "
                        f"not in this sheet. Known entries: {known}. Fix the label, or harvest "
                        f"the world and add an entry.",
                    )
                )
    return findings


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
        *check_plate_budget(shots),
        *check_sequence(shots),
        *check_register_balance(shots),
        *check_world_lock(shots, world),
        *check_prompt_quality(shots),
        *check_format(shots),
        *check_vocabulary(shots),
        *check_style_reference(shots),
        *check_style_mechanism(shots),
        *check_slots(shots, world),
        *check_slot_labels(shots, world, library),
    ]
    if cover is not None:
        findings.extend(lint_cover(cover, world, library=library))
    return findings


DEFAULT_STYLE_LIBRARY = Path(__file__).resolve().parents[1] / "docs" / "style-library.md"


def sheet_declares_slots(shots: list[Shot], cover: Shot | None = None) -> bool:
    """Whether anything on the sheet needs a Library lookup at all."""
    prompts = [shot.prompt for shot in shots] + ([cover.prompt] if cover else [])
    return any(
        pattern.search(prompt) for prompt in prompts for pattern, _kind, _prefix in SLOT_KINDS
    )


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
    parser.add_argument(
        "--style-library",
        type=Path,
        default=DEFAULT_STYLE_LIBRARY,
        help="path to the Style Library C20 resolves slot labels against "
             f"(default: {DEFAULT_STYLE_LIBRARY}). Only read when the sheet has slots. "
             "A non-default path is recorded in the output as [NON-DEFAULT].",
    )
    args = parser.parse_args(argv)

    sheet_text = _read(args.sheet, "sheet")
    if sheet_text is None:
        return EXIT_UNREADABLE_INPUT
    parse = parse_sheet(sheet_text)
    shots, sheet_world = parse.shots, parse.world

    if args.styleboard is not None:
        styleboard_text = _read(args.styleboard, "styleboard")
        if styleboard_text is None:
            return EXIT_UNREADABLE_INPUT
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
        if sheet_world:
            # A legacy sheet that still carries its own WORLD LOCK block used to have
            # it silently discarded in favor of the styleboard's, with zero indication
            # anything was overridden -- including when the sheet's block had gone
            # stale and now contradicts the styleboard.
            parse.findings.append(Finding(
                "PARSE", None,
                f"the sheet at {args.sheet.name} carries its own WORLD LOCK block, but a "
                f"styleboard was also supplied at {args.styleboard.name}; the sheet's "
                "block is being discarded -- remove it from the sheet if the styleboard "
                "is now authoritative, or drop --styleboard if the sheet's own block "
                "should still apply.",
                kind="parse",
            ))
    else:
        world = sheet_world

    if not shots:
        print(f"Gate C: no shots parsed from {args.sheet}. Check the sheet format.")
        return EXIT_UNPARSEABLE

    cover = parse_cover(sheet_text)

    # Read the Library only when something actually needs resolving: a PLATE-only sheet
    # carries no slots, and failing it for a file it never consults would be a gate
    # reporting the wrong problem.
    library = None
    if sheet_declares_slots(shots, cover):
        if not args.style_library.is_file():
            print(
                f"Gate C: Style Library not found at {args.style_library}. C20 cannot "
                f"resolve this sheet's slot labels. Pass --style-library."
            )
            return EXIT_MISSING_DEPENDENCY
        library_text = _read(args.style_library, "Style Library")
        if library_text is None:
            return EXIT_UNREADABLE_INPUT
        library, library_findings = parse_style_library_checked(library_text)
        if library_findings:
            print(
                f"Gate C: Style Library at {args.style_library} could not be fully parsed:"
            )
            for finding in library_findings:
                print(f"  [{finding.check}] {finding.message}")
            return EXIT_MISSING_DEPENDENCY
        if not library:
            print(
                f"Gate C: no entries parsed from {args.style_library}. C20 cannot check "
                f"this sheet's slot labels against an empty Library."
            )
            return EXIT_MISSING_DEPENDENCY

    if library is not None:
        marker = "" if args.style_library == DEFAULT_STYLE_LIBRARY else " [NON-DEFAULT]"
        print(f"Gate C: Style Library{marker}: {args.style_library} "
              f"({len(library)} entries)")

    findings = [
        *parse.findings,
        *check_cover_present(sheet_text),
        *lint(shots, world, cover=cover, library=library,
              declared_shot_count=parse.declared_shot_count),
    ]
    if not findings:
        print(f"Gate C: PASS — {len(shots)} shots, 0 findings.")
        return EXIT_PASS

    print(f"Gate C: FAIL — {len(shots)} shots, {len(findings)} finding(s).")
    for finding in findings:
        print(f"  [{finding.check}] {finding.beat}: {finding.message}")
    return EXIT_FINDINGS


if __name__ == "__main__":
    sys.exit(main())
