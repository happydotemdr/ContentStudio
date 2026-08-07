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
MARKER_RE = re.compile(r"\[(?:C|I|T|T-unverified)\]")

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
