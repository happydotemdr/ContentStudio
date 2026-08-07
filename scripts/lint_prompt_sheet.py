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
COVER_REUSE_RE = re.compile(r"^\s*Cover\s*=\s*Hook\b", re.IGNORECASE)


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

    Scans line by line and skips anything between a ```text open fence and its
    close, so a stray 'Cover = Hook...' sitting inside a pasted prompt body (i.e.
    describing imagery, not declaring a decision) can't satisfy C19. Deliberately
    NOT confined to a 'COVER / THUMBNAIL' section header: the line is a fixed,
    specific declaration string ('Cover = Hook...') that nothing else in the sheet
    format would produce by accident, and Task 6's fixture carries it at the top
    level with no such section wrapping it.
    """
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
        if COVER_REUSE_RE.match(line):
            return True
    return False


def check_cover_present(text: str) -> list[Finding]:
    """C19: the cover decision is stated, never silently omitted -- and stated once.

    prompt-sheet-format.md §7 already requires this of every emitted sheet `[I]`; until
    now nothing enforced it. A sheet with two '### Cover — ...' headings (a stale draft
    left behind plus the real one) has parse_cover silently linting only the first and
    leaving the second invisible to Gate C, so that ambiguity is reported here rather
    than resolved silently.
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
    if parse_cover(text) is not None or declares_cover_reuse(text):
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


def _pairs(shots: list[Shot]):
    for i, left in enumerate(shots):
        for right in shots[i + 1 :]:
            yield left, right


STYLIZE_RE = re.compile(r"--(?:s|stylize)\s+(\d+)")
REGISTER_BANDS = {"A": (80, 120, True), "B": (400, 700, False)}
# A bare version number like "8.2" -- the only non-URL shape allowed to carry a period.
URL_OR_VERSION_TOKEN_RE = re.compile(r"^\d+\.\d+$")


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


MOODBOARD_FLAG_RE = re.compile(r"--p\b")


def check_style_mechanism(shots: list[Shot]) -> list[Finding]:
    """C17: every non-PLATE shot carries some style mechanism.

    C16 rejects a bad code but says nothing about a shot with no code at all, which is
    the same defect one step removed: the shot renders in whatever default aesthetic
    the model picks, and the Short stops reading as one look.

    PLATE shots are exempt — they are subject-free background plates with no register
    look to lock (visual-registers.md §5).

    Presence is checked with `SREF_FLAG_RE` — the same anchored, word-boundary regex
    C16 uses to find --sref occurrences — rather than a raw `"--sref" in flags"`
    substring test. The two checks answer different questions (C17: is some
    mechanism written at all; C16: is its value real) but must agree on what counts
    as "an --sref is here" so a bare, valueless `--sref` isn't invisible to one
    check while silently satisfying the other.
    """
    findings: list[Finding] = []
    for shot in shots:
        if shot.register == "PLATE":
            continue
        flags = prompt_flags(shot)
        has_mechanism = (
            SREF_FLAG_RE.search(flags) is not None
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

    cover = parse_cover(sheet_text)
    findings = [*check_cover_present(sheet_text), *lint(shots, world, cover=cover)]
    if not findings:
        print(f"Gate C: PASS — {len(shots)} shots, 0 findings.")
        return 0

    print(f"Gate C: FAIL — {len(shots)} shots, {len(findings)} finding(s).")
    for finding in findings:
        if finding.shot_index is None:
            where = "sheet"
        elif finding.shot_index == 0:
            where = "cover"
        else:
            where = f"shot {finding.shot_index}"
        print(f"  [{finding.check}] {where}: {finding.message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
