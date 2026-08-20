"""Conformance suite for the ContentStudio skill set.

Four properties, asserted over all 13 skills and all 64 reference files under
`.claude/skills/`:

  1. Handoff  — every output section one skill consumes by name is declared by the
                skill that produces it (audit C-01, C-04, C-16, C-18, C-21, C-25).
  2. Citation — a bare `references/x.md` citation resolves inside the citing skill;
                a cross-skill citation is skill-qualified; a `§N` anchor exists in the
                file it points at (audit C-12, C-40, C-41, C-55).
  3. Vocabulary — one canonical stage-id / `--kind` / `stage:` registry, agreed across
                every SKILL.md (audit C-22, C-23).
  4. Provenance — every normative block carries `[C]`/`[I]`/`[T]`/`[P]`/`[T-unverified]`,
                an alternative-vocabulary marker its skill declares, or an entry in the
                explicit triage ledger below (audit C-42, C-43, C-48, C-54, F-22).

The narrow regression guards at the bottom of the file predate the suite and are kept
verbatim: they pin the two places the anti-generic guarantee was actually broken.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / ".claude" / "skills"

REGISTERS = SKILLS / "shorts-styleboard" / "references" / "visual-registers.md"
MARKER_RE = re.compile(r"\[(?:C|I|T|P|T-unverified)\]")

# The brief's original pattern (`corpus (has nothing|says nothing|is thin)`) requires the
# phrase to sit *immediately* next to the word "corpus". The file's real wording never does
# that -- "The corpus's own visuals theme (...) is thin" and "it says nothing about register
# systems" both put other words in between.
#
# The disclaimer is really two independent clauses, and both must survive:
#   (a) the generic claim that the corpus's own visuals theme is thin/sparse
#   (b) the register-system-specific claim that the corpus says nothing about it
# A single `A|B` regex is the wrong shape for that: either half can regress to its
# opposite meaning while the other half keeps the whole `search()` passing. Two
# independently-required patterns close that gap and name which clause failed.
GENERIC_THIN_RE = re.compile(
    r"corpus(?:(?!\.\s).){0,300}?\bis thin\b",  # "corpus['s ...] is thin", same sentence
    re.IGNORECASE,
)
REGISTER_SPECIFIC_GAP_RE = re.compile(
    r"\bsays nothing about register systems\b",
    re.IGNORECASE,
)

PIPELINE_SKILLS = (
    "shorts-ideation", "shorts-scripting", "shorts-styleboard", "voiceover-brief",
    "visual-prompts", "music-brief", "shorts-assembly", "social-repurpose",
)
SPECIALIST_SKILLS = ("elevenlabs-audio", "elevenlabs-music", "midjourney-prompting")
RGS_SKILLS = ("rgs-grounding", "rgs-pairing-review")
ALL_SKILLS = PIPELINE_SKILLS + SPECIALIST_SKILLS + RGS_SKILLS


def skill_dir(name: str) -> Path:
    return SKILLS / name


def skill_md(name: str) -> Path:
    return SKILLS / name / "SKILL.md"


def reference_files(name: str) -> list[Path]:
    return sorted((SKILLS / name / "references").glob("*.md"))


def every_markdown_file() -> list[Path]:
    return sorted(SKILLS.rglob("*.md"))


def strip_fences(text: str) -> list[tuple[int, str]]:
    """(1-based line number, line) for every line outside a ``` fence."""
    out, in_fence = [], False
    for n, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append((n, line))
    return out


def fenced_block(text: str, info: str) -> str | None:
    """The body of the first ```<info> fence in `text`, or None."""
    lines, body, capturing = text.splitlines(), [], False
    for line in lines:
        if not capturing and line.strip() == f"```{info}":
            capturing = True
            continue
        if capturing and line.strip().startswith("```"):
            return "\n".join(body)
        if capturing:
            body.append(line)
    return None


def test_marker_re_accepts_the_project_decision_marker():
    """`[P]` is a valid marker (CLAUDE.md's fourth marker). MARKER_RE once omitted it,
    so a correctly-`[P]`-marked bullet inside a guarded slice failed as unmarked."""
    assert MARKER_RE.search("- **Use the pinned narrator voice.** `[P]`")
    assert MARKER_RE.search("- **Draft is half the cost of SD.** `[T-unverified]`")
    assert not MARKER_RE.search("- **Cut every three seconds.**")


def test_the_register_system_still_lives_with_styleboard():
    assert REGISTERS.exists(), "visual-registers.md must live with the skill that owns the world lock"


def test_the_register_system_is_still_marked_as_this_skills_own_design():
    text = REGISTERS.read_text(encoding="utf-8")
    assert "`[I]`" in text
    assert "operational design" in text, (
        "the register system is [I], not [C]; the disclaimer must survive any move"
    )


def test_the_corpus_gap_disclaimer_survives_the_generic_thin_clause():
    """The generic claim -- the corpus's own visuals theme is thin/sparse -- must survive."""
    text = REGISTERS.read_text(encoding="utf-8")
    assert "corpus" in text.lower()
    assert GENERIC_THIN_RE.search(text), (
        "the file must keep stating that the corpus's own visuals theme is thin"
    )


def test_the_corpus_gap_disclaimer_survives_the_register_specific_clause():
    """The specific claim -- the corpus says nothing about register systems -- must survive.

    This is the more load-bearing half: it is the one that names the exact gap the
    register system fills. A single OR'd regex covering both clauses would let this
    half regress to its opposite (e.g. "fully documents register systems") undetected
    as long as the generic "is thin" clause survived -- hence a separate, independently
    required assertion for this clause specifically.
    """
    text = REGISTERS.read_text(encoding="utf-8")
    assert REGISTER_SPECIFIC_GAP_RE.search(text), (
        "the file must keep stating that the corpus says nothing about register systems"
    )


def test_register_contract_bullets_all_carry_a_marker():
    """Every normative bullet under the Register A/B contracts names its provenance."""
    text = REGISTERS.read_text(encoding="utf-8")
    section = text.split("## 3. Register A")[1].split("## 5. PLATE")[0]
    bullets = [
        line.strip()
        for line in section.splitlines()
        if line.strip().startswith("- **")
    ]
    assert bullets, "the split points must still select at least one contract bullet"
    unmarked = [line for line in bullets if not MARKER_RE.search(line)]
    assert unmarked == [], f"unmarked normative lines: {unmarked}"


def test_styleboard_skill_does_not_claim_corpus_backing_for_the_register_system():
    text = (SKILLS / "shorts-styleboard" / "SKILL.md").read_text(encoding="utf-8")
    assert "own operational design `[I]`" in text


def test_every_skill_directory_is_classified():
    """A new skill must be added to one of the three registries, or the suite silently
    stops covering it — which is exactly how C-48 happened."""
    on_disk = {p.parent.name for p in SKILLS.glob("*/SKILL.md")}
    assert on_disk == set(ALL_SKILLS), (
        f"unclassified: {sorted(on_disk - set(ALL_SKILLS))}; "
        f"missing from disk: {sorted(set(ALL_SKILLS) - on_disk)}"
    )
