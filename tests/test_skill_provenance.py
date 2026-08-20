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

The narrow regression guards in the middle of the file predate the suite and are kept
verbatim: they pin the two places the anti-generic guarantee was actually broken.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / ".claude" / "skills"

REGISTERS = SKILLS / "shorts-styleboard" / "references" / "visual-registers.md"
MARKER_RE = re.compile(r"\[(?:C|I|T|P|T-unverified)\]")

CHANNEL_CITE_RE = re.compile(r"\(\s*[A-Za-z][A-Za-z0-9 .&'-]+,\s*[A-Za-z0-9_-]{6,}")
VERIFIED_HEADER_RE = re.compile(r"verified\s+20\d\d-\d\d-\d\d", re.IGNORECASE)

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

# stage id (pipeline.yaml) -> (--kind string, `stage:` frontmatter value, owning skill)
KIND_REGISTRY = {
    "grounding": ("grounding", "00-grounding", "rgs-grounding"),
    "ideation": ("concept-brief", "01-ideation", "shorts-ideation"),
    "scripting": ("script", "02-scripting", "shorts-scripting"),
    "styleboard": ("styleboard", "02b-styleboard", "shorts-styleboard"),
    "voiceover": ("voiceover-brief", "03-voiceover", "voiceover-brief"),
    "visual": ("visual-prompts", "03-visual", "visual-prompts"),
    "music": ("music", "03-music", "music-brief"),
    "assembly": ("assembly", "04-assembly", "shorts-assembly"),
    "repurpose": ("social-repurpose", "05-repurpose", "social-repurpose"),
}
# specialists write beside a stage rather than owning one
SPECIALIST_KINDS = {
    "elevenlabs-audio": ("audio-spec", "03-voiceover"),
    "elevenlabs-music": ("music-spec", "03-music"),
    "midjourney-prompting": (None, None),
}
KIND_FLAG_RE = re.compile(r"--kind\s+([a-z][a-z0-9-]*)")


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


CITE_RE = re.compile(
    r"`(?:\.claude/skills/)?(?:(?P<skill>[a-z0-9-]+)/)?references/(?P<file>[a-z0-9.-]+\.md)`"
    r"(?:\s*(?P<anchor>§[0-9]+(?:[–-]§?[0-9]+)?))?"
)
DUPLICATED_BASENAMES = {"worked-example.md", "validation-gates.md",
                        "api-payload.md", "visual-registers.md"}


def test_every_bare_reference_citation_resolves_inside_its_own_skill():
    """A bare `references/x.md` can only mean 'in this skill' — that is the only path a
    reader of that file can resolve (audit C-40, six broken; C-12, three of them)."""
    broken = []
    for path in every_markdown_file():
        owner = path.relative_to(SKILLS).parts[0]
        for lineno, line in strip_fences(path.read_text(encoding="utf-8")):
            for m in CITE_RE.finditer(line):
                if m.group("skill"):
                    continue  # qualified: checked below
                if not (SKILLS / owner / "references" / m.group("file")).exists():
                    broken.append(f"{path}:{lineno}: references/{m.group('file')}")
    assert broken == [], f"bare citations that do not resolve in their own skill: {broken}"


def test_every_qualified_reference_citation_resolves():
    """The qualified counterpart to the bare-citation check above: a `skill/references/x.md`
    citation must resolve to a real file inside the named skill, not just look plausible."""
    broken = []
    for path in every_markdown_file():
        for lineno, line in strip_fences(path.read_text(encoding="utf-8")):
            for m in CITE_RE.finditer(line):
                if not m.group("skill"):
                    continue  # bare: checked above
                if not (SKILLS / m.group("skill") / "references" / m.group("file")).exists():
                    broken.append(f"{path}:{lineno}: {m.group('skill')}/references/{m.group('file')}")
    assert broken == [], f"qualified citations that do not resolve: {broken}"


def test_a_duplicated_reference_filename_is_never_cited_bare_across_skills():
    """C-55: `worked-example.md` exists in 9 skills. A bare citation to a duplicated
    basename always *looks* plausible — that is the mechanism behind C-41."""
    offences = []
    for path in every_markdown_file():
        owner = path.relative_to(SKILLS).parts[0]
        for lineno, line in strip_fences(path.read_text(encoding="utf-8")):
            for m in CITE_RE.finditer(line):
                name = m.group("file")
                if m.group("skill") or name not in DUPLICATED_BASENAMES:
                    continue
                if not (SKILLS / owner / "references" / name).exists():
                    offences.append(f"{path}:{lineno}: {name}")
    assert offences == [], f"unqualified citation of a duplicated filename: {offences}"


ANCHOR_HEADING_RE = re.compile(r"^##+\s*(?:§\s*)?(\d+)[.)]?\s", re.MULTILINE)


def test_every_section_anchor_resolves_in_the_file_it_points_at():
    """C-41: ten citations named §-anchors that existed only in the styleboard copy.
    They *resolved* as files, so no existence check caught them."""
    missing = []
    for path in every_markdown_file():
        owner = path.relative_to(SKILLS).parts[0]
        for lineno, line in strip_fences(path.read_text(encoding="utf-8")):
            for m in CITE_RE.finditer(line):
                if not m.group("anchor"):
                    continue
                target = SKILLS / (m.group("skill") or owner) / "references" / m.group("file")
                if not target.exists():
                    # A missing target is reported by test_every_bare_reference_citation_
                    # resolves_inside_its_own_skill (unqualified) or
                    # test_every_qualified_reference_citation_resolves (qualified) above.
                    continue
                have = set(ANCHOR_HEADING_RE.findall(target.read_text(encoding="utf-8")))
                want = set(re.findall(r"\d+", m.group("anchor")))
                if not want <= have:
                    missing.append(f"{path}:{lineno}: {m.group('anchor')} not in {target.name}")
    assert missing == [], f"section anchors that do not exist in their target: {missing}"


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


HANDOFF_KEYS = {"produces.kind", "produces.stage", "produces.section",
                "consumes", "reads", "writes"}


def handoff(skill: str) -> dict[str, list[str]]:
    body = fenced_block(skill_md(skill).read_text(encoding="utf-8"), "handoff")
    assert body is not None, (
        f"{skill}/SKILL.md has no ```handoff block; every skill declares its contract"
    )
    parsed: dict[str, list[str]] = {k: [] for k in HANDOFF_KEYS}
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        assert key in HANDOFF_KEYS, f"{skill}: unknown handoff key {key!r}"
        assert value, f"{skill}: handoff key {key!r} has no value"
        parsed[key].append(value)
    return parsed


OUTPUT_HEADING_RE = re.compile(r"^##+\s+Output (format|contract)\s*$", re.IGNORECASE)
EXACT_SHAPE_HEADING_RE = re.compile(r"^##+\s+Exact shape\s*$", re.IGNORECASE)


def _fenced_block_after_heading(lines: list[str], heading_re: re.Pattern) -> list[str] | None:
    """Every line of the first fenced block after the first line matching `heading_re`,
    or None if no such heading, or no fence follows it."""
    start = next((i for i, ln in enumerate(lines) if heading_re.match(ln.strip())), None)
    if start is None:
        return None
    body, in_fence = [], False
    for ln in lines[start + 1:]:
        if ln.lstrip().startswith("```"):
            if in_fence:
                break
            in_fence = True
            continue
        if in_fence:
            body.append(ln)
    return body or None


def output_template(skill: str) -> list[str]:
    """Every line of the first fenced block after the skill's Output format/contract
    heading in its own SKILL.md.

    Not every skill's output template lives in SKILL.md itself -- shorts-styleboard's
    WORLD LOCK block lives under an '## Exact shape' heading in
    references/styleboard-format.md instead. If SKILL.md has no Output format/contract
    heading, fall back to the first fenced block under an '## Exact shape' heading in
    the skill's references/*-format.md file.
    """
    text = skill_md(skill).read_text(encoding="utf-8")
    body = _fenced_block_after_heading(text.splitlines(), OUTPUT_HEADING_RE)
    if body is not None:
        return body

    format_files = sorted((SKILLS / skill / "references").glob("*-format.md"))
    for format_file in format_files:
        ref_body = _fenced_block_after_heading(
            format_file.read_text(encoding="utf-8").splitlines(), EXACT_SHAPE_HEADING_RE
        )
        if ref_body is not None:
            return ref_body

    assert False, (
        f"{skill}/SKILL.md has no '## Output format' heading, and no "
        f"references/*-format.md file has a fenced block under an '## Exact shape' "
        f"heading to fall back to (checked: {[f.name for f in format_files]})"
    )


def section_resolves(skill: str, section: str) -> bool:
    for line in output_template(skill):
        head = line.strip().lstrip("#").strip()
        if not head.startswith(section):
            continue
        rest = head[len(section):]
        if rest == "" or rest[0] in ":( \t":
            return True
    return False


@pytest.mark.parametrize("skill", ALL_SKILLS)
def test_declared_output_sections_appear_in_the_output_template(skill):
    """A skill may not advertise a section its own output template does not contain."""
    missing = [s for s in handoff(skill)["produces.section"] if not section_resolves(skill, s)]
    assert missing == [], f"{skill} declares sections absent from its output template: {missing}"


@pytest.mark.parametrize("skill", ALL_SKILLS)
def test_every_consumed_section_resolves_to_a_declared_producer_section(skill):
    """C-01: `music-brief`, `elevenlabs-audio` and `elevenlabs-music` all consumed
    'the tone-per-beat call' by name from a skill that never declared it."""
    problems = []
    for edge in handoff(skill)["consumes"]:
        producer, _, section = edge.partition("#")
        if producer not in ALL_SKILLS:
            problems.append(f"{edge}: no such skill")
            continue
        if not section:
            problems.append(f"{edge}: no '#<section>' named")
            continue
        if section not in handoff(producer)["produces.section"]:
            problems.append(f"{edge}: {producer} does not declare that section")
    assert problems == [], f"{skill} consumes undeclared fields: {problems}"


def test_marker_re_accepts_the_project_decision_marker():
    """`[P]` is a valid marker (CLAUDE.md's fourth marker). MARKER_RE once omitted it,
    so a correctly-`[P]`-marked bullet inside a guarded slice failed as unmarked."""
    assert MARKER_RE.search("- **Use the pinned narrator voice.** `[P]`")
    assert MARKER_RE.search("- **Draft is half the cost of SD.** `[T-unverified]`")
    assert not MARKER_RE.search("- **Cut every three seconds.**")


def test_output_template_falls_back_to_the_reference_format_files_exact_shape():
    """shorts-styleboard's WORLD LOCK template lives under an '## Exact shape'
    heading in references/styleboard-format.md, not under an
    '## Output format'/'## Output contract' heading in its own SKILL.md (it has
    neither). output_template() must fall back to the reference file's fenced
    block instead of raising 'no Output format heading'."""
    body = output_template("shorts-styleboard")
    text = "\n".join(body)
    assert "WORLD LOCK" in text
    assert "slot_register_a" in text
    assert "slot_register_b" in text


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


def test_every_kind_flag_in_every_skill_is_in_the_registry():
    """A `--kind` typo returns NONE/exit 1, which every File I/O section documents as the
    benign 'upstream hasn't run yet' case. A vocabulary slip is therefore invisible."""
    known = {k for k, _, _ in KIND_REGISTRY.values()}
    known |= {k for k, _ in SPECIALIST_KINDS.values() if k}
    bad = []
    for path in every_markdown_file():
        for lineno, line in strip_fences(path.read_text(encoding="utf-8")):
            for m in KIND_FLAG_RE.finditer(line):
                if m.group(1) not in known:
                    bad.append(f"{path}:{lineno}: --kind {m.group(1)}")
    assert bad == [], f"unregistered --kind values: {bad}"


@pytest.mark.parametrize("stage,spec", sorted(KIND_REGISTRY.items()))
def test_the_owning_skill_declares_the_registry_kind_and_stage(stage, spec):
    kind, stage_value, skill = spec
    block = handoff(skill)
    assert block["produces.kind"] == [kind], f"{skill} must declare produces.kind: {kind}"
    assert block["produces.stage"] == [stage_value], f"{skill} must declare produces.stage: {stage_value}"


def test_the_registry_matches_the_declared_stage_graph():
    """Cross-check against pipeline.yaml so the two cannot drift. Read-only: pipeline.yaml
    belongs to P4."""
    text = (REPO / "pipeline.yaml").read_text(encoding="utf-8")
    ids = re.findall(r"^\s*-\s*id:\s*(\S+)\s*$", text, re.MULTILINE)
    assert set(ids) == set(KIND_REGISTRY), (
        f"pipeline.yaml stage ids {sorted(ids)} != registry {sorted(KIND_REGISTRY)}"
    )


# --- Provenance triage (audit C-42/C-43/C-54) -------------------------------
# Three categories, decided once, recorded here. Shrink TIER_1_PENDING; never grow it.

ALTERNATIVE_VOCABULARY = {
    # skill -> the marker tokens it declares in place of [C]/[I]/[T]
    "rgs-grounding": (r"\[THINKER:", r"\[RESEARCH:", r"\[REF\]", r"\[B\]"),
    "rgs-pairing-review": (r"\[THINKER:", r"\[RESEARCH:", r"\[REF\]", r"\[B\]"),
    "social-repurpose": (r"\[C→I\]", r"\[gap\]"),
}

STRUCTURAL_SECTIONS = (
    "reference files", "citation index", "pipeline position",
    "file i/o contract", "handoff contract (machine-checked)", "reference map",
)

WORKED_EXAMPLE_DISCLAIMER = (
    "This example illustrates rules already marked in this skill's other reference files "
    "and carries no independent normative weight."
)

# Files with [C] blocks whose citation cannot yet be checked. One line deleted per commit.
# Format: relative posix path -> (uncitable block count at triage time, note)
#
# Every entry below was verified by hand (each flagged line's full multi-line bullet was read,
# not just the single line the test inspects) to confirm the block genuinely carries a
# `(Channel, video_id)` citation — this ledger is not standing in for missing citations, it is
# standing in for one remaining mechanical blind spot in the verbatim T16 line-scan: the
# citation sits on the bullet's markdown continuation line, one or more physical lines below the
# `- **...**` line normative_blocks() actually inspects. (CHANNEL_CITE_RE originally required an
# uppercase-initial channel name too, which wrongly excluded same-line citations to stylized-
# lowercase channels like `vidIQ` -- that regex bug is fixed above; every entry that was pending
# ONLY for that reason, e.g. shorts-assembly's four reference files, has been removed from this
# ledger since the fix. What remains below is genuinely wrapped, unaffected by the regex fix.)
# Reformatting every wrapped bullet across the skill set is out of scope for T16 (which targets
# the specific C-44/C-45 items enumerated in the task brief) — flagged here, not fixed, per this
# ledger's own precedent in TIER_1_PENDING above.
C_CITATION_PENDING: dict[str, tuple[int, str]] = {
    ".claude/skills/midjourney-prompting/SKILL.md": (2, "wrapped: both blocks' (Channel, video_id) citations sit on the bullet's continuation line, not the flagged `- **` line"),
    ".claude/skills/shorts-ideation/references/angle-selection.md": (20, "wrapped: all 20 blocks' (Channel, video_id) citations sit on the bullet's continuation line"),
    ".claude/skills/shorts-ideation/references/hook-concepts.md": (4, "wrapped: all four blocks' (Channel, video_id) citations sit on the bullet's continuation line"),
    ".claude/skills/shorts-ideation/references/packaging-direction.md": (13, "wrapped: all 13 blocks' (Channel, video_id) citations sit on the bullet's continuation line"),
    ".claude/skills/shorts-ideation/references/validation-gate.md": (4, "wrapped: all four blocks' (Channel, video_id) citations sit on the bullet's continuation line"),
    ".claude/skills/shorts-scripting/references/endings-and-ctas.md": (9, "wrapped: all nine blocks' (Channel, video_id) citations sit on the bullet's continuation line"),
    ".claude/skills/shorts-scripting/references/hooks-and-openings.md": (17, "wrapped: all 17 blocks' (Channel, video_id) citations sit on the bullet's continuation line"),
    ".claude/skills/shorts-scripting/references/read-aloud-gates.md": (1, "wrapped: the block's (Channel, video_id) citation sits on the bullet's continuation line"),
    ".claude/skills/shorts-scripting/references/retention-loops-and-structure.md": (24, "wrapped: all 24 blocks' (Channel, video_id) citations sit on the bullet's continuation line"),
    ".claude/skills/shorts-scripting/references/script-intelligence-and-delivery.md": (14, "wrapped: all 14 blocks' (Channel, video_id) citations sit on the bullet's continuation line"),
    ".claude/skills/social-repurpose/references/cross-platform-captions.md": (7, "wrapped: all seven blocks' (Channel, video_id) citations sit on the bullet's continuation line"),
    ".claude/skills/social-repurpose/references/youtube-description-hashtags.md": (9, "wrapped: all nine blocks' (Channel, video_id) citations sit on the bullet's continuation line"),
    ".claude/skills/visual-prompts/SKILL.md": (1, "wrapped: the block's (Channel, video_id) citation sits on the bullet's continuation line"),
    ".claude/skills/visual-prompts/references/faceless-pacing-rules.md": (9, "wrapped: all nine blocks' (Channel, video_id) citations sit on the bullet's continuation line (down from 11 -- two more resolved by the CHANNEL_CITE_RE lowercase-channel fix)"),
    ".claude/skills/visual-prompts/references/image-to-video.md": (4, "wrapped: the file's C-44/C-45 items (model-landscape table :96-103, bare `(Tao Prompts)` at :69/:85 pre-header-insertion) are resolved via in-repo cross-reference (docs/midjourney-prompting-guide.md, prompt-sheet-format.md:123) — see the fixed model-landscape table and the two [I]-downgraded lines above. The 4 remaining flagged blocks are a separate, pre-existing wrapped-citation artifact: each cites (Channel, video_id) on the bullet's continuation line"),
    ".claude/skills/voiceover-brief/references/production-and-loudness.md": (1, "wrapped: the block's (Channel, video_id) citation sits on the bullet's continuation line"),
    ".claude/skills/voiceover-brief/references/scripting-for-tts.md": (2, "wrapped: both blocks' (Channel, video_id) citations sit on the bullet's continuation line"),
}

# Files whose tier-1 blocks are not yet marked. One line deleted per commit.
# Format: relative posix path -> (unmarked block count at triage time, note)
TIER_1_PENDING: dict[str, tuple[int, str]] = {
    ".claude/skills/rgs-grounding/references/pairing-map.md": (95, "category-3 file per brief, but its field-label bullets (Work/anchor, Quotability, Pairs with, Why it links, Visual motif cue) carry no [THINKER:]/[RESEARCH:]/[REF]/[B] token, so the vocabulary regex does not actually reach them (brief's own expectation was stale); explicitly out of scope to edit this dispatch (do-not-touch), flagged not fixed"),
    ".claude/skills/midjourney-prompting/references/v82-model-delta.md": (6, "remaining lines are Omni-Reference/Draft-Mode/--q vendor facts (compatibility lists, the literalism-claim refutation, and the quality-buzzwords-degrade-output unverified claim); needs [T]/[T-unverified] re-verification against docs.midjourney.com, not attempted this dispatch"),
    ".claude/skills/rgs-grounding/references/safety-sensitive-handling.md": (5, "RGS operational-design bullets, but RGS's declared vocabulary has no [I]-equivalent token for this skill's own design (only citation tokens); using bare [I]/[C]/[T] here would fail the stray-marker test. Needs a P14 decision on an RGS-side design marker, not attempted this dispatch"),
    ".claude/skills/midjourney-prompting/references/style-systems.md": (3, "Omni Reference vendor facts (image-count limit, GPU-time multiplier, incompatibility list); needs [T] verification against docs.midjourney.com, not attempted this dispatch"),
    ".claude/skills/rgs-grounding/references/brand-voice-and-tone.md": (3, "brand-voice bullets distilled from an operator source document, not this skill's design and not the 14-channel corpus; RGS's declared vocabulary has no token for this provenance class, needs a P14 decision, not attempted this dispatch"),
    ".claude/skills/rgs-grounding/references/scripting-beat-mapping.md": (4, "the four fixed-mapping bullets (Hook->Hook, Turn->Setup+early-Build, Payoff->proof beat or Payoff, Reframe->split) are this skill's own design, but RGS's declared vocabulary has no [I]-equivalent design token (see safety-sensitive-handling.md note); needs a P14 decision, not attempted this dispatch"),
    ".claude/skills/rgs-pairing-review/SKILL.md": (3, "the diff-check taxonomy (new/changed thinker and research definitions) is this skill's own operational design, but RGS's declared vocabulary has no [I]-equivalent design token (see rgs-grounding/references/safety-sensitive-handling.md note), needs a P14 decision, not attempted this dispatch"),
    ".claude/skills/elevenlabs-audio/references/directorial-prompting.md": (2, "eleven_v3 text-to-dialogue vendor facts (model requirement, the <=2,000-char cap); needs [T] verification against ElevenLabs docs, not attempted this dispatch"),
    ".claude/skills/elevenlabs-audio/references/voice-profiles.md": (1, "the `use_pvc_as_ivc` request-parameter vendor fact (name, default, effect); needs [T] verification against ElevenLabs docs, not attempted this dispatch"),
}


def _vocabulary_re(skill: str) -> re.Pattern:
    extra = ALTERNATIVE_VOCABULARY.get(skill, ())
    return re.compile("|".join((MARKER_RE.pattern, *extra)))


def normative_blocks(path: Path) -> list[tuple[int, str]]:
    """A normative block is a `- **…` bullet outside a fence and outside a structural section."""
    blocks, section = [], ""
    for lineno, line in strip_fences(path.read_text(encoding="utf-8")):
        stripped = line.strip()
        if stripped.startswith("#"):
            section = stripped.lstrip("#").strip().lower()
            continue
        if section in STRUCTURAL_SECTIONS:
            continue
        if stripped.startswith("- **"):
            blocks.append((lineno, stripped))
    return blocks


def test_every_corpus_marked_normative_block_carries_a_channel_and_video_id():
    """CLAUDE.md defines [C] as 'extracted from a transcript, cited (Channel, video_id)' —
    the citation is constitutive. An uncitable [C] passes a marker-presence test, which is
    worse than being unmarked (audit C-44, 33 blocks; C-45, 26 in one file)."""
    bad = []
    for path in every_markdown_file():
        rel = path.relative_to(REPO).as_posix()
        uncited = [f"{rel}:{lineno}" for lineno, line in normative_blocks(path)
                   if "[C]" in line and not CHANNEL_CITE_RE.search(line)]
        if not uncited:
            assert rel not in C_CITATION_PENDING, (
                f"{rel} is clean — delete its C_CITATION_PENDING entry"
            )
            continue
        if rel in C_CITATION_PENDING:
            assert len(uncited) <= C_CITATION_PENDING[rel][0], (
                f"{rel}: pending count {C_CITATION_PENDING[rel][0]} is stale, "
                f"actual is {len(uncited)} -- update the ledger"
            )
            continue
        bad.extend(uncited)
    assert bad == [], f"[C] blocks with no (Channel, video_id): {bad}"


def test_every_reference_file_with_tool_facts_carries_a_verification_date():
    """CLAUDE.md defines [T] as 'web-verified, dated'. elevenlabs-audio carries 187 [T]
    lines and a date in 2 of 11 files (audit C-46)."""
    undated = []
    for path in every_markdown_file():
        text = path.read_text(encoding="utf-8")
        if "[T]" not in text:
            continue
        head = "\n".join(text.splitlines()[:12])
        if not VERIFIED_HEADER_RE.search(head):
            undated.append(path.relative_to(REPO).as_posix())
    assert undated == [], f"[T]-carrying files with no dated verification header: {undated}"


@pytest.mark.parametrize("skill", ALL_SKILLS)
def test_every_normative_block_carries_a_marker_or_a_recorded_exemption(skill):
    """CLAUDE.md: 'a skill rule with no marker is a bug'. This test makes that true, or
    makes the exemption explicit and countable."""
    pattern = _vocabulary_re(skill)
    failures = []
    for path in [skill_md(skill), *reference_files(skill)]:
        rel = path.relative_to(REPO).as_posix()
        if path.name == "worked-example.md":
            continue  # covered by the disclaimer test below
        unmarked = [f"{rel}:{n}" for n, text in normative_blocks(path)
                    if not pattern.search(text)]
        if not unmarked:
            assert rel not in TIER_1_PENDING, (
                f"{rel} is clean — delete its TIER_1_PENDING entry"
            )
            continue
        if rel in TIER_1_PENDING:
            assert len(unmarked) <= TIER_1_PENDING[rel][0], (
                f"{rel}: pending count {TIER_1_PENDING[rel][0]} is stale, "
                f"actual is {len(unmarked)} -- update the ledger"
            )
            continue
        failures.extend(unmarked)
    assert failures == [], f"unmarked normative blocks with no recorded exemption: {failures}"


@pytest.mark.parametrize("skill", ALL_SKILLS)
def test_every_worked_example_states_its_normative_status(skill):
    """C-54: shorts-assembly instructs copying the worked example's structure verbatim, so
    an unmarked example is the template every emitted artifact inherits."""
    example = SKILLS / skill / "references" / "worked-example.md"
    if not example.exists():
        return
    assert WORKED_EXAMPLE_DISCLAIMER in example.read_text(encoding="utf-8"), (
        f"{skill}/references/worked-example.md must carry the worked-example disclaimer verbatim"
    )


@pytest.mark.parametrize("skill", RGS_SKILLS)
def test_rgs_skills_do_not_carry_stray_corpus_markers(skill):
    """C-43: five stray [C]/[I]/[T] tokens survive inside skills that declare they use a
    different vocabulary, so the boundary is not clean either."""
    allowed_lines = {
        # the disclaimer that *names* the corpus markers, and cross-references to another
        # skill's marked rule, are legitimate. Everything else is a leak.
        ".claude/skills/rgs-grounding/SKILL.md": {44},
        ".claude/skills/rgs-grounding/references/scripting-beat-mapping.md": {18, 19},
        # the mandatory, verbatim C-54 worked-example disclaimer (added by T15) names `[I]`
        # as prose, same as the citation-markers disclaimer above.
        ".claude/skills/rgs-grounding/references/worked-example.md": {5},
    }
    stray = []
    for path in [skill_md(skill), *reference_files(skill)]:
        rel = path.relative_to(REPO).as_posix()
        ok = allowed_lines.get(rel, set())
        for lineno, line in strip_fences(path.read_text(encoding="utf-8")):
            if MARKER_RE.search(line) and lineno not in ok:
                stray.append(f"{rel}:{lineno}")
    assert stray == [], f"stray corpus markers in an alternative-vocabulary skill: {stray}"


def test_style_library_users_declare_it_in_their_handoff_block():
    """C-34: shorts-styleboard binds slots from it, shorts-assembly resolves slots against
    it at paste time, and midjourney-prompting writes harvested codes into it — with no
    declared owner in any I/O contract and no staleness rule."""
    readers = {"shorts-styleboard", "shorts-assembly", "midjourney-prompting"}
    for skill in readers:
        assert "docs/style-library.md" in handoff(skill)["reads"], (
            f"{skill} reads docs/style-library.md and must declare it"
        )
    assert "docs/style-library.md" in handoff("midjourney-prompting")["writes"], (
        "midjourney-prompting harvests codes into the Library and must declare the write"
    )


NEGATIVE_SCOPE_RE = re.compile(
    r"(do not use|don't use|does not|doesn't|not for|never use) ", re.IGNORECASE
)


@pytest.mark.parametrize("skill", ALL_SKILLS)
def test_every_description_states_a_negative_scope(skill):
    """Trigger text is what routing matches on, so a boundary stated only in the body is
    invisible at selection time (audit C-29)."""
    text = skill_md(skill).read_text(encoding="utf-8")
    front = text.split("---")[1]
    description = front.split("description:", 1)[1]
    assert NEGATIVE_SCOPE_RE.search(description), (
        f"{skill}'s description states no negative scope; its body already does"
    )
