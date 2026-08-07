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

# The brief's original pattern (`corpus (has nothing|says nothing|is thin)`) requires the
# phrase to sit *immediately* next to the word "corpus". The file's real wording never does
# that -- "The corpus's own visuals theme (...) is thin" and "it says nothing about register
# systems" both put other words in between. This pattern instead requires "corpus" to be
# followed, within the same sentence (no ". " sentence break in between -- a bare "." inside
# a filename like "audit.md" doesn't count), by "is thin"; or accepts the file's exact
# "says nothing about register systems" clause directly. Either branch is specific enough
# that it cannot pass against arbitrary text -- see the mutation checks in task-12-report.md.
GAP_DISCLAIMER_RE = re.compile(
    r"corpus(?:(?!\.\s).){0,300}?\bis thin\b|\bsays nothing about register systems\b",
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


def test_the_corpus_gap_disclaimer_survives():
    text = REGISTERS.read_text(encoding="utf-8")
    assert "corpus" in text.lower()
    assert GAP_DISCLAIMER_RE.search(text), (
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
