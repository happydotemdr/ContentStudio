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

import pytest

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
                    continue  # reported by the tests above
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

# Files whose tier-1 blocks are not yet marked. One line deleted per commit.
# Format: relative posix path -> (unmarked block count at triage time, note)
TIER_1_PENDING: dict[str, tuple[int, str]] = {
    ".claude/skills/rgs-grounding/references/pairing-map.md": (95, "category-3 file per brief, but its field-label bullets (Work/anchor, Quotability, Pairs with, Why it links, Visual motif cue) carry no [THINKER:]/[RESEARCH:]/[REF]/[B] token, so the vocabulary regex does not actually reach them (brief's own expectation was stale); explicitly out of scope to edit this dispatch (do-not-touch), flagged not fixed"),
    ".claude/skills/shorts-scripting/references/retention-loops-and-structure.md": (23, "corpus craft rules; needs [C] (Channel, video_id) sourcing from output/, absent in this worktree"),
    ".claude/skills/shorts-scripting/references/hooks-and-openings.md": (14, "corpus craft rules; needs [C] (Channel, video_id) sourcing from output/, absent in this worktree"),
    ".claude/skills/shorts-scripting/references/script-intelligence-and-delivery.md": (13, "corpus craft rules; needs [C] (Channel, video_id) sourcing from output/, absent in this worktree"),
    ".claude/skills/midjourney-prompting/references/v82-model-delta.md": (13, "vendor-fact deltas; needs [T]/[T-unverified] re-verification against docs.midjourney.com, not attempted this dispatch"),
    ".claude/skills/elevenlabs-audio/SKILL.md": (11, "modal craft rules over ElevenLabs config; needs [T] verification against ElevenLabs docs, not attempted this dispatch"),
    ".claude/skills/midjourney-prompting/SKILL.md": (11, "modal craft rules; needs [T]/[T-unverified] verification against docs.midjourney.com, not attempted this dispatch"),
    ".claude/skills/visual-prompts/references/faceless-pacing-rules.md": (10, "corpus pacing claims; needs [C] (Channel, video_id) sourcing from output/, absent in this worktree"),
    ".claude/skills/midjourney-prompting/references/style-systems.md": (10, "vendor-fact style-system rules; needs [T] verification against docs.midjourney.com, not attempted this dispatch"),
    ".claude/skills/shorts-scripting/references/endings-and-ctas.md": (9, "corpus craft rules; needs [C] (Channel, video_id) sourcing from output/, absent in this worktree"),
    ".claude/skills/shorts-ideation/SKILL.md": (7, "corpus craft rules; needs [C] (Channel, video_id) sourcing from output/, absent in this worktree"),
    ".claude/skills/elevenlabs-music/references/api-payload.md": (6, "vendor payload-field facts; needs [T] verification against Eleven Music docs, not attempted this dispatch"),
    ".claude/skills/shorts-scripting/SKILL.md": (5, "corpus craft rules; needs [C] (Channel, video_id) sourcing from output/, absent in this worktree"),
    ".claude/skills/rgs-grounding/references/safety-sensitive-handling.md": (5, "RGS operational-design bullets, but RGS's declared vocabulary has no [I]-equivalent token for this skill's own design (only citation tokens); using bare [I]/[C]/[T] here would fail the stray-marker test. Needs a P14 decision on an RGS-side design marker, not attempted this dispatch"),
    ".claude/skills/visual-prompts/references/image-to-video.md": (4, "corpus i2v-motion claims; needs [C] (Channel, video_id) sourcing from output/, absent in this worktree"),
    ".claude/skills/elevenlabs-music/SKILL.md": (4, "vendor-fact rules; needs [T] verification against Eleven Music docs, not attempted this dispatch"),
    ".claude/skills/rgs-grounding/references/scripting-beat-mapping.md": (4, "structural beat-mapping bullets are this skill's own design, but RGS's declared vocabulary has no [I]-equivalent design token (see safety-sensitive-handling.md note); needs a P14 decision, not attempted this dispatch"),
    ".claude/skills/shorts-scripting/references/beat-timing-model.md": (3, "corpus timing claims; needs [C] (Channel, video_id) sourcing from output/, absent in this worktree"),
    ".claude/skills/voiceover-brief/SKILL.md": (3, "corpus voice-selection claims; needs [C] (Channel, video_id) sourcing from output/, absent in this worktree"),
    ".claude/skills/voiceover-brief/references/scripting-for-tts.md": (3, "corpus TTS-formatting claims; needs [C] (Channel, video_id) sourcing from output/, absent in this worktree"),
    ".claude/skills/shorts-assembly/references/loudness-and-mix.md": (3, "corpus loudness/ducking claims; needs [C] (Channel, video_id) sourcing from output/, absent in this worktree"),
    ".claude/skills/elevenlabs-audio/references/directorial-prompting.md": (3, "vendor-fact audio-tag rules; needs [T] verification against ElevenLabs docs, not attempted this dispatch"),
    ".claude/skills/elevenlabs-audio/references/model-routing.md": (3, "vendor-fact model-routing rules; needs [T] verification against ElevenLabs docs, not attempted this dispatch"),
    ".claude/skills/elevenlabs-audio/references/validation-gates.md": (3, "vendor-fact gate rules; needs [T] verification against ElevenLabs docs, not attempted this dispatch"),
    ".claude/skills/elevenlabs-music/references/validation-gates.md": (3, "vendor-fact gate rules; needs [T] verification against Eleven Music docs, not attempted this dispatch"),
    ".claude/skills/midjourney-prompting/references/render-economics.md": (3, "vendor-fact GPU/credit rules; needs [T] verification against docs.midjourney.com, not attempted this dispatch"),
    ".claude/skills/rgs-grounding/references/brand-voice-and-tone.md": (3, "brand-voice bullets distilled from an operator source document, not this skill's design and not the 14-channel corpus; RGS's declared vocabulary has no token for this provenance class, needs a P14 decision, not attempted this dispatch"),
    ".claude/skills/rgs-pairing-review/SKILL.md": (3, "RGS operational-design bullets; RGS's declared vocabulary has no [I]-equivalent design token (see rgs-grounding/references/safety-sensitive-handling.md note), needs a P14 decision, not attempted this dispatch"),
    ".claude/skills/shorts-scripting/references/read-aloud-gates.md": (2, "corpus read-aloud-gate claims; needs [C] (Channel, video_id) sourcing from output/, absent in this worktree"),
    ".claude/skills/voiceover-brief/references/channel-voice.md": (2, "pinned-voice-id operational bullets; already [P]-adjacent but the specific unmarked lines need a deliberate [P]/[I] call rather than a blind pass, not attempted this dispatch"),
    ".claude/skills/elevenlabs-audio/references/voice-profiles.md": (2, "vendor-fact voice-profile rules; needs [T] verification against ElevenLabs docs, not attempted this dispatch"),
    ".claude/skills/elevenlabs-music/references/composition-plans.md": (2, "vendor-fact composition-plan rules; needs [T] verification against Eleven Music docs, not attempted this dispatch"),
    ".claude/skills/midjourney-prompting/references/validation-gates.md": (2, "vendor-fact gate rules; needs [T] verification against docs.midjourney.com, not attempted this dispatch"),
    ".claude/skills/voiceover-brief/references/production-and-loudness.md": (1, "corpus loudness claim; needs [C] (Channel, video_id) sourcing from output/, absent in this worktree"),
    ".claude/skills/shorts-assembly/references/caption-overlay-system.md": (1, "corpus caption/overlay claim; needs [C] (Channel, video_id) sourcing from output/, absent in this worktree"),
    ".claude/skills/elevenlabs-audio/references/api-payload.md": (1, "vendor-fact payload rule; needs [T] verification against ElevenLabs docs, not attempted this dispatch"),
    ".claude/skills/elevenlabs-audio/references/cost-and-credits.md": (1, "vendor-fact credit-cost rule; needs [T] verification against ElevenLabs docs, not attempted this dispatch"),
    ".claude/skills/elevenlabs-audio/references/voice-settings.md": (1, "vendor-fact voice-settings rule; needs [T] verification against ElevenLabs docs, not attempted this dispatch"),
    ".claude/skills/midjourney-prompting/references/prompt-architecture.md": (1, "vendor-fact prompt-architecture rule; needs [T] verification against docs.midjourney.com, not attempted this dispatch"),
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
        ".claude/skills/rgs-grounding/SKILL.md": {39},
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
