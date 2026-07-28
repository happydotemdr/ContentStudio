"""Gate C — deterministic shot-variety lint for ContentStudio visual prompt sheets.

Parses the copy-paste sheet format emitted by the `visual-prompts` skill and enforces
the dual-register visual system's variety, world-lock, density and format rules.

Stdlib only. See docs/superpowers/specs/2026-07-28-dual-register-visual-system-design.md
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
