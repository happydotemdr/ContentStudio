import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lint_prompt_sheet import (  # noqa: E402
    Shot,
    Finding,
    parse_sheet,
    parse_world_lock,
    parse_cover,
    declares_cover_reuse,
    prompt_body,
    prompt_flags,
    body_clauses,
    body_word_count,
    signature_objects,
    check_sequence,
    check_register_balance,
    check_world_lock,
    check_prompt_quality,
    check_prompt_clone,
    check_prompt_density,
    check_format,
    REQUIRED_ASPECT_RATIO,
    check_vocabulary,
    check_style_reference,
    check_style_mechanism,
    sheet_declares_slots,
    check_slots,
    check_slot_labels,
    parse_style_library,
    parse_style_library_checked,
    check_cover_present,
    check_shot_count,
    check_plate_budget,
    lint_cover,
    lint,
    main,
    DEFAULT_STYLE_LIBRARY,
    EXIT_PASS,
    EXIT_FINDINGS,
    EXIT_USAGE,
    EXIT_UNREADABLE_INPUT,
    EXIT_UNPARSEABLE,
    EXIT_MISSING_DEPENDENCY,
)

from dataclasses import asdict


def test_finding_defaults_to_a_blocking_kind():
    """gates.py blocks on `kind != "skipped"`. Gate C must never emit "skipped":
    the blocking rule has to be contractual, not an accident of a missing key."""
    finding = Finding("C1", 3, "shot class repeats")
    assert finding.kind == "fail"
    assert asdict(finding)["kind"] == "fail"


def test_finding_carries_a_beat_the_stage_template_can_render():
    """stage.html renders finding.beat. A Gate C finding without one displays as
    '[C18]: <message>' with no shot number, while the CLI prints 'shot 7:'."""
    assert asdict(Finding("C1", 7, "m"))["beat"] == "shot 7"
    assert asdict(Finding("C19", None, "m"))["beat"] == "sheet"
    assert asdict(Finding("C16", 0, "m"))["beat"] == "cover"


def test_no_gate_c_check_can_emit_a_skipped_kind():
    """Distinguishability: Gate C has no known-unknown concept. If one is ever added,
    gates.py's blocking rule silently stops blocking it — so assert it cannot exist."""
    shots, world = parse_sheet(SHEET.replace("--s 95", "--s 9500"))
    assert {f.kind for f in lint(shots, world)} <= {"fail", "parse"}


def test_a_broken_shot_heading_produces_a_blocking_parse_finding():
    """C-70, the flagship. Breaking Shot 4's em-dash to a hyphen made the shot
    invisible to all of C1-C20 and Gate C printed PASS."""
    text = WORKED.read_text(encoding="utf-8").replace(
        "### Shot 4 — Build", "### Shot 4 - Build", 1
    )
    parse = parse_sheet(text)
    assert [f.check for f in parse.findings] == ["PARSE"]
    assert "Shot 4" in parse.findings[0].message
    assert parse.findings[0].kind == "parse"


def test_a_broken_heading_is_distinguishable_from_a_sheet_that_has_that_shot():
    """Distinguishability: the broken sheet must not present as the good sheet
    minus one shot -- it must present as a sheet that failed to parse."""
    good = WORKED.read_text(encoding="utf-8")
    broken = good.replace("### Shot 4 — Build", "### Shot 4 - Build", 1)
    assert parse_sheet(good).findings == []
    assert parse_sheet(broken).findings != []


def test_parse_sheet_still_unpacks_as_the_two_tuple_every_caller_expects():
    """pipeline_app/gates.py does `shots, sheet_world = linter.parse_sheet(text)`.
    That call site belongs to P3 and must keep working untouched."""
    shots, world = parse_sheet(SHEET)
    assert len(shots) == 2
    assert world["register_a_sport"] == "club soccer"


SHEET = """\
=== VISUAL PROMPT SHEET — demo ===

WORLD LOCK
  register_a_sport: club soccer
  register_a_venue: municipal club soccer complex
  register_a_signature_objects: goal net, corner flag, painted touchline
  register_b_thinker: Plutarch
  slot_register_a: rgs-present-soccer-a
  slot_register_b: rgs-sourceera-painterly-b

PER-SHOT PROMPTS

### Shot 1 — Hook (0–3s) · Register A · DETAIL · MACRO · LOW
Changes vs. previous: opening frame.

```text
documentary sports photography, a strap being pulled tight, on cropped winter turf, No Text. --ar 9:16 --raw --s 95 {style:register_a}
```

### Shot 2 — Setup (3–8s) · Register B · WORLD · XWIDE · EYE
Changes vs. previous: register switch to the source era.

```text
luminous oil painting on aged linen, a colonnade at dawn, olive branches beyond, No Text. --ar 9:16 --s 520 {style:register_b}
```
"""


def test_parse_sheet_returns_two_shots():
    shots, world = parse_sheet(SHEET)
    assert len(shots) == 2


def test_parse_sheet_reads_shot_metadata():
    shots, _ = parse_sheet(SHEET)
    first = shots[0]
    assert first.index == 1
    assert first.beat == "Hook (0–3s)"
    assert first.register == "A"
    assert first.shot_class == "DETAIL"
    assert first.scale == "MACRO"
    assert first.camera_height == "LOW"
    assert first.prompt_line_count == 1


def test_parse_sheet_reads_prompt_text():
    shots, _ = parse_sheet(SHEET)
    assert shots[0].prompt.startswith("documentary sports photography,")
    assert shots[0].prompt.endswith("--ar 9:16 --raw --s 95 {style:register_a}")


def test_parse_sheet_reads_world_lock():
    _, world = parse_sheet(SHEET)
    assert world["register_a_sport"] == "club soccer"
    assert world["register_b_thinker"] == "Plutarch"


def test_signature_objects_splits_on_commas():
    _, world = parse_sheet(SHEET)
    assert signature_objects(world) == ["goal net", "corner flag", "painted touchline"]


def test_prompt_body_and_flags_split_at_first_flag():
    shots, _ = parse_sheet(SHEET)
    assert prompt_flags(shots[0]) == "--ar 9:16 --raw --s 95 {style:register_a}"
    assert "--ar" not in prompt_body(shots[0])
    assert prompt_body(shots[0]).endswith("No Text.")


def test_body_clauses_excludes_no_text_marker():
    shots, _ = parse_sheet(SHEET)
    clauses = body_clauses(shots[0])
    assert clauses == [
        "documentary sports photography",
        "a strap being pulled tight",
        "on cropped winter turf",
    ]


def test_body_word_count_ignores_no_text_marker():
    shot = Shot(
        index=1,
        beat="Hook",
        register="A",
        shot_class="DETAIL",
        scale="MACRO",
        camera_height="LOW",
        prompt="alpha beta gamma, delta epsilon, No Text. --ar 9:16",
        prompt_line_count=1,
    )
    assert body_word_count(shot) == 5


def make_shot(index, register="A", shot_class="DETAIL", scale="MACRO",
              camera_height="LOW", prompt="alpha, beta, No Text. --ar 9:16"):
    return Shot(
        index=index,
        beat=f"Beat {index}",
        register=register,
        shot_class=shot_class,
        scale=scale,
        camera_height=camera_height,
        prompt=prompt,
        prompt_line_count=1,
    )


def codes(findings):
    return sorted({f.check for f in findings})


VARIED = [
    make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
    make_shot(2, "B", "WORLD", "XWIDE", "EYE"),
    make_shot(3, "A", "ESTABLISHING", "WIDE", "HIGH"),
    make_shot(4, "B", "FIGURE", "MID", "EYE"),
    make_shot(5, "A", "HUMAN-COST", "CLOSE", "LOW"),
]


def test_c1_flags_repeated_adjacent_shot_class():
    shots = [
        make_shot(1, "A", "HUMAN-COST", "MID", "LOW"),
        make_shot(2, "B", "HUMAN-COST", "WIDE", "EYE"),
        make_shot(3, "A", "DETAIL", "MACRO", "HIGH"),
    ]
    assert "C1" in codes(check_sequence(shots))


def test_c2_flags_repeated_adjacent_scale():
    shots = [
        make_shot(1, "A", "DETAIL", "MID", "LOW"),
        make_shot(2, "B", "WORLD", "MID", "EYE"),
        make_shot(3, "A", "ESTABLISHING", "WIDE", "HIGH"),
    ]
    assert "C2" in codes(check_sequence(shots))


def test_c3_flags_run_of_three_in_same_register():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "A", "HUMAN-COST", "MID", "EYE"),
        make_shot(3, "A", "ESTABLISHING", "WIDE", "HIGH"),
        make_shot(4, "B", "WORLD", "XWIDE", "EYE"),
    ]
    assert "C3" in codes(check_sequence(shots))


def test_c3_treats_plate_as_transparent():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "PLATE", "PLATE", "MID", "EYE"),
        make_shot(3, "A", "ESTABLISHING", "WIDE", "HIGH"),
        make_shot(4, "A", "WORLD", "XWIDE", "EYE"),
    ]
    assert "C3" in codes(check_sequence(shots))


def test_c4_flags_fewer_than_three_scales():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "B", "WORLD", "WIDE", "EYE"),
        make_shot(3, "A", "ESTABLISHING", "MACRO", "HIGH"),
    ]
    assert "C4" in codes(check_sequence(shots))


def test_c5_flags_single_camera_height():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "B", "WORLD", "XWIDE", "LOW"),
        make_shot(3, "A", "ESTABLISHING", "WIDE", "LOW"),
    ]
    assert "C5" in codes(check_sequence(shots))


def test_varied_sheet_passes_all_sequence_checks():
    assert check_sequence(VARIED) == []


def test_c6_flags_too_few_register_b_shots():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "B", "WORLD", "XWIDE", "EYE"),
        make_shot(3, "A", "ESTABLISHING", "WIDE", "HIGH"),
        make_shot(4, "A", "HUMAN-COST", "MID", "LOW"),
    ]
    assert "C6" in codes(check_register_balance(shots))


def test_c6_flags_too_few_register_a_shots():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "B", "WORLD", "XWIDE", "EYE"),
        make_shot(3, "B", "FIGURE", "MID", "HIGH"),
    ]
    assert "C6" in codes(check_register_balance(shots))


def test_c7_flags_bookended_registers():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "A", "ESTABLISHING", "WIDE", "EYE"),
        make_shot(3, "B", "WORLD", "XWIDE", "HIGH"),
        make_shot(4, "B", "FIGURE", "MID", "LOW"),
    ]
    findings = check_register_balance(shots)
    assert "C7" in codes(findings)


def test_c7_passes_when_registers_alternate_twice():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "B", "WORLD", "XWIDE", "EYE"),
        make_shot(3, "A", "ESTABLISHING", "WIDE", "HIGH"),
        make_shot(4, "B", "FIGURE", "MID", "LOW"),
        make_shot(5, "A", "HUMAN-COST", "CLOSE", "LOW"),
    ]
    assert "C7" not in codes(check_register_balance(shots))


def test_varied_sheet_passes_register_balance():
    assert check_register_balance(VARIED) == []


WORLD = {
    "register_a_sport": "club soccer",
    "register_a_signature_objects": "goal net, corner flag, painted touchline",
    "register_b_thinker": "Plutarch",
}


def test_c8_flags_register_a_without_the_sport():
    shot = make_shot(1, "A", prompt="a child in a room, near a goal net, No Text. --ar 9:16")
    assert "C8" in codes(check_world_lock([shot], WORLD))


def test_c8_flags_register_a_without_a_signature_object():
    shot = make_shot(1, "A", prompt="a club soccer player standing, in a room, No Text. --ar 9:16")
    assert "C8" in codes(check_world_lock([shot], WORLD))


def test_c8_passes_with_sport_and_signature_object():
    shot = make_shot(
        1, "A",
        prompt="a club soccer pitch, goal net behind, corner flag, No Text. --ar 9:16",
    )
    assert "C8" not in codes(check_world_lock([shot], WORLD))


def test_c8_does_not_match_the_sport_inside_a_larger_word():
    shot = make_shot(1, "A", prompt="a clubsoccerboot on turf, goal net, corner flag, "
                                    "No Text. --ar 9:16 --raw --s 95")
    assert "C8" in codes(check_world_lock([shot], WORLD))


def test_c8_requires_two_signature_objects_not_one():
    # Non-MACRO scale: the 2-object floor applies at full strength here (see
    # test_c8_macro_shots_get_a_one_object_floor for the MACRO carve-out).
    shot = make_shot(1, "A", scale="WIDE",
                      prompt="club soccer, a goal net alone in fog, "
                             "No Text. --ar 9:16 --raw --s 95")
    findings = check_world_lock([shot], WORLD)
    assert "C8" in codes(findings)
    assert "at least 2" in [f.message for f in findings if f.check == "C8"][0]


def test_c8_passes_a_prompt_that_actually_depicts_the_world():
    shot = make_shot(1, "A", scale="WIDE",
                      prompt="club soccer, a goal net, a corner flag, "
                             "No Text. --ar 9:16 --raw --s 95")
    assert "C8" not in codes(check_world_lock([shot], WORLD))


def test_c8_macro_shots_get_a_one_object_floor():
    """T21 deviation from the literal brief: both real MIGRATED_PAIRS fixtures'
    MACRO 'Hook'/'Payoff' close-ups (and passing_sheet.md's CLOSE-scale cover)
    name the sport plus exactly one signature object -- an extreme close-up
    cannot credibly hold two named large props in frame -- and fixtures are
    off-limits to this task. A flat floor of 2 broke both currently-green
    fixtures with no per-shot signal available to tell a genuine single-prop
    tight shot apart from the degenerate case C-87 describes. CLOSE/MACRO
    shots keep the pre-T21 floor of 1; every other scale gets the full
    MIN_SIGNATURE_OBJECTS. See the T21 report for the fixture evidence."""
    for scale in ("MACRO", "CLOSE"):
        one_object = make_shot(1, "A", scale=scale,
                                prompt="club soccer, a goal net alone in fog, "
                                       "No Text. --ar 9:16 --raw --s 95")
        assert "C8" not in codes(check_world_lock([one_object], WORLD)), scale

        zero_objects = make_shot(1, "A", scale=scale,
                                  prompt="club soccer, No Text. --ar 9:16 --raw --s 95")
        assert "C8" in codes(check_world_lock([zero_objects], WORLD)), scale


def test_c8_object_matching_is_plural_tolerant():
    """The other half of the T21 deviation: worked_example_sheet.md Shot 2 (WIDE,
    not MACRO) writes 'corner flags' (plural) where the world lock declares the
    singular 'corner flag'. A strictly singular \\b...\\b match would undercount
    a real mention as zero, which is a matching bug, not a depiction question."""
    shot = make_shot(1, "A", scale="WIDE",
                      prompt="club soccer, a goal net and a row of corner flags, "
                             "No Text. --ar 9:16 --raw --s 95")
    assert "C8" not in codes(check_world_lock([shot], WORLD))


def test_both_green_fixtures_still_satisfy_the_stricter_c8():
    for sheet, board in MIGRATED_PAIRS:
        _shots, findings = lint_fixture(sheet, board)
        assert "C8" not in codes(findings), sheet


def test_c9_flags_banned_generic_venue():
    shot = make_shot(
        1, "A", prompt="a club soccer bag in an empty gym, goal net behind, No Text. --ar 9:16"
    )
    assert "C9" in codes(check_world_lock([shot], WORLD))


def test_c10_flags_optics_vocabulary_in_register_b():
    shot = make_shot(
        1, "B", prompt="oil painting of a colonnade, 85mm lens, DSLR, No Text. --ar 9:16"
    )
    assert "C10" in codes(check_world_lock([shot], WORLD))


def test_c10_flags_f_stop_in_register_b():
    shot = make_shot(1, "B", prompt="oil painting of a terrace, f/2.8, No Text. --ar 9:16")
    assert "C10" in codes(check_world_lock([shot], WORLD))


def test_c10_passes_for_painterly_register_b():
    shot = make_shot(
        1,
        "B",
        prompt="luminous oil painting on aged linen, a colonnade at dawn, No Text. --ar 9:16",
    )
    assert check_world_lock([shot], WORLD) == []


def test_plate_shots_are_exempt_from_world_lock():
    shot = make_shot(
        1, "PLATE", "PLATE", prompt="a dark gradient plate in an empty gym, No Text. --ar 9:16"
    )
    assert check_world_lock([shot], WORLD) == []


@pytest.mark.parametrize("venue", ["vacant gym", "deserted gym", "empty pitch",
                                   "empty stadium", "abandoned pitch"])
def test_c9_flags_generic_venue_synonyms(venue):
    # "empty field" excluded: it collides with legitimate, fully-named-venue prose
    # in tests/fixtures/passing_sheet.md Shot 3 -- see the BANNED_REGISTER_A_STRINGS
    # comment in scripts/lint_prompt_sheet.py.
    shot = make_shot(1, "A", prompt=f"{venue}, club soccer, goal net, No Text. --ar 9:16")
    assert "C9" in codes(check_world_lock([shot], WORLD))


@pytest.mark.parametrize("term", ["photorealistic", "photographic", "bokeh",
                                  "shallow depth of field", "leica", "kodachrome",
                                  "cinematic still"])
def test_c10_flags_photographic_vocabulary_synonyms(term):
    shot = make_shot(1, "B", prompt=f"a colonnade, {term}, No Text. --ar 9:16 --s 520")
    assert "C10" in codes(check_world_lock([shot], WORLD))


def test_c9_and_c10_scan_the_flag_block_too():
    """Both were scoped to prompt_body, so the same vocabulary written after the
    first flag was unreachable."""
    shot = make_shot(1, "B", prompt="a colonnade, No Text. --ar 9:16 --s 520 --style dslr")
    assert "C10" in codes(check_world_lock([shot], WORLD))


def test_both_green_fixtures_stay_clean_under_the_widened_lists():
    for sheet, board in MIGRATED_PAIRS:
        _shots, findings = lint_fixture(sheet, board)
        assert not [f for f in findings if f.check in ("C9", "C10")], sheet


def build_prompt(unique_head, shared_count=12, filler_word="alpha"):
    """Build a body with `shared_count` shared clauses plus a unique head clause."""
    shared = [f"shared clause {n} {filler_word} beta gamma delta epsilon" for n in range(shared_count)]
    return ", ".join([unique_head, *shared]) + ", No Text. --ar 9:16 --raw --s 95"


def test_c11_flags_two_prompts_sharing_six_clauses():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW", build_prompt("first head")),
        make_shot(2, "A", "HUMAN-COST", "MID", "EYE", build_prompt("second head")),
    ]
    assert "C11" in codes(check_prompt_quality(shots))


def test_c11_passes_when_prompts_are_genuinely_different():
    a = ", ".join(f"alpha clause {n} beta gamma delta epsilon" for n in range(12))
    b = ", ".join(f"zeta clause {n} eta theta iota kappa" for n in range(12))
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW", a + ", No Text. --ar 9:16"),
        make_shot(2, "A", "HUMAN-COST", "MID", "EYE", b + ", No Text. --ar 9:16"),
    ]
    assert "C11" not in codes(check_prompt_quality(shots))


def test_c11_still_flags_an_exact_clone():
    a = build_prompt("unique head one")
    b = build_prompt("unique head two")
    assert "C11" in codes(check_prompt_clone([make_shot(1, prompt=a), make_shot(3, prompt=a)]))


def test_c11_flags_a_clone_disguised_by_one_appended_word_per_clause():
    """C-82, confirmed by execution: one word per clause took 12 shared clauses to 0."""
    original = build_prompt("unique head one")
    disguised = ", ".join(f"{c} here" for c in original.split(", "))
    findings = check_prompt_clone([make_shot(1, prompt=original), make_shot(3, prompt=disguised)])
    assert "C11" in codes(findings)


def test_c11_is_silent_on_genuinely_different_prompts():
    """Distinguishability, and the anti-tautology guard: a similarity threshold that
    fires on everything is not a check."""
    _shots, findings = lint_fixture("worked_example_sheet.md", "worked_example_styleboard.md")
    assert "C11" not in codes(findings)


def test_c12_flags_too_few_clauses():
    body = ", ".join(f"clause {n} with several extra words here now" for n in range(4))
    shot = make_shot(1, "A", prompt=body + ", No Text. --ar 9:16")
    assert "C12" in codes(check_prompt_quality([shot]))


def test_c12_flags_too_few_words():
    body = ", ".join(f"c{n}" for n in range(12))
    shot = make_shot(1, "A", prompt=body + ", No Text. --ar 9:16")
    assert "C12" in codes(check_prompt_quality([shot]))


def test_c12_passes_a_dense_prompt():
    # Genuinely varied clauses, not "clause N" repeated with an index swapped in --
    # that shape is itself padding and (correctly, post-C-83) now trips the new
    # repetition floor. This fixture clears clause/word/repetition floors alike.
    clauses = [
        "weathered oak bleachers under harsh midday sun",
        "scuffed leather soccer ball resting on damp grass",
        "chalk-lined penalty box catching low golden light",
        "rust-streaked goalpost anchored in packed clay soil",
        "torn corner flag snapping in a stiff breeze",
        "muddy cleats abandoned beside a wooden bench",
        "faded number seven jersey draped over a fence",
        "cracked asphalt walkway leading toward the pitch",
        "dented water bottle rolling near the sideline chalk",
        "frayed net swaying gently from a missed shot",
        "sun-bleached scoreboard frozen at a tied match",
        "worn whistle dangling from a coach's weathered hand",
    ]
    body = ", ".join(clauses)
    shot = make_shot(1, "A", prompt=body + ", No Text. --ar 9:16")
    assert "C12" not in codes(check_prompt_quality([shot]))


def test_c12_flags_a_body_padded_with_repeated_filler():
    """C-83, confirmed by execution: the docstring promised a nine-layer content
    check; the implementation was a length floor, and padding is exactly what a
    model produces against a length target."""
    body = ", ".join(f"w{n} filler token phrase alpha beta gamma" for n in range(10))
    shot = make_shot(1, "A", prompt=body + ", club soccer goal net, No Text. --ar 9:16")
    assert "C12" in codes(check_prompt_density([shot]))


def test_c12_is_silent_on_a_real_dense_prompt():
    """Anti-tautology: the repetition check must separate padding from density."""
    shots, _ = parse_sheet(WORKED.read_text(encoding="utf-8"))
    assert check_prompt_density(shots) == []


def test_c12_docstring_does_not_claim_a_nine_layer_content_check():
    assert "nine layers" not in check_prompt_density.__doc__


DENSE_A = ", ".join(f"clause {n} with several extra descriptive words here" for n in range(12))


def test_c13_flags_multiline_prompt():
    shot = Shot(1, "Hook", "A", "DETAIL", "MACRO", "LOW",
                DENSE_A + ", No Text. --ar 9:16 --raw --s 95", 2)
    assert "C13" in codes(check_format([shot]))


def test_c13_flags_missing_no_text():
    shot = make_shot(1, "A", prompt=DENSE_A + " --ar 9:16 --raw --s 95")
    assert "C13" in codes(check_format([shot]))


def test_c13_flags_missing_aspect_ratio():
    shot = make_shot(1, "A", prompt=DENSE_A + ", No Text. --raw --s 95")
    assert "C13" in codes(check_format([shot]))


def test_c13_flags_a_landscape_aspect_ratio():
    """F-13/C-81: the old test covered --ar absence only, never its value. A Short
    is vertical; --ar 16:9 passed the whole gate."""
    shot = make_shot(1, "A", prompt=DENSE_A + ", No Text. --ar 16:9 --raw --s 95")
    findings = check_format([shot])
    assert "C13" in codes(findings)
    assert any("16:9" in f.message and REQUIRED_ASPECT_RATIO in f.message for f in findings)


def test_c13_accepts_the_required_aspect_ratio():
    shot = make_shot(1, "A", prompt=DENSE_A + ", No Text. --ar 9:16 --raw --s 95")
    assert "C13" not in codes(check_format([shot]))


def test_c13_flags_punctuation_in_flag_block():
    shot = make_shot(1, "A", prompt=DENSE_A + ", No Text. --ar 9:16, --raw --s 95")
    assert "C13" in codes(check_format([shot]))


def test_c13_allows_url_and_version_periods_in_flag_block():
    shot = make_shot(
        1,
        "A",
        prompt=DENSE_A + ", No Text. --ar 9:16 --raw --s 95 --v 8.2 "
        "--oref https://cdn.midjourney.com/a1b2.png --ow 100",
    )
    assert "C13" not in codes(check_format([shot]))


def test_c14_flags_register_a_without_raw():
    shot = make_shot(1, "A", prompt=DENSE_A + ", No Text. --ar 9:16 --s 95")
    assert "C14" in codes(check_format([shot]))


def test_c14_flags_register_a_stylize_out_of_band():
    shot = make_shot(1, "A", prompt=DENSE_A + ", No Text. --ar 9:16 --raw --s 400")
    assert "C14" in codes(check_format([shot]))


def test_c14_flags_register_b_with_raw():
    shot = make_shot(1, "B", "WORLD", "XWIDE", "EYE",
                     DENSE_A + ", No Text. --ar 9:16 --raw --s 520")
    assert "C14" in codes(check_format([shot]))


def test_c14_flags_register_b_stylize_out_of_band():
    shot = make_shot(1, "B", "WORLD", "XWIDE", "EYE",
                     DENSE_A + ", No Text. --ar 9:16 --s 95")
    assert "C14" in codes(check_format([shot]))


def test_c14_passes_correct_bands():
    a = make_shot(1, "A", prompt=DENSE_A + ", No Text. --ar 9:16 --raw --s 95")
    b = make_shot(2, "B", "WORLD", "XWIDE", "EYE",
                  DENSE_A + ", No Text. --ar 9:16 --s 520")
    assert check_format([a, b]) == []


def test_c22_caps_the_share_of_plate_shots():
    """Relabelling an awkward shot 'Register PLATE' removed its every register check.
    Nothing bounded how many shots could take that exit."""
    shots = [make_shot(i, "PLATE", "PLATE", "MACRO", "LOW") for i in range(1, 5)] + \
            [make_shot(5, "A", "DETAIL", "CLOSE", "EYE")]
    findings = check_plate_budget(shots)
    assert [f.check for f in findings] == ["C22"]
    assert "4 of 5" in findings[0].message


def test_c22_allows_a_single_plate_in_a_normal_sheet():
    shots = [make_shot(1, "PLATE", "PLATE", "MACRO", "LOW")] + \
            [make_shot(i, "A", "DETAIL", "CLOSE", "EYE") for i in range(2, 7)]
    assert check_plate_budget(shots) == []


def test_a_plate_shot_must_still_carry_a_stylize_value():
    """C14's bands were skipped entirely for PLATE because REGISTER_BANDS.get
    returned None and the loop hit `continue`."""
    shot = make_shot(1, "PLATE", "PLATE", prompt=DENSE_A + ", No Text. --ar 9:16")
    assert "C14" in codes(check_format([shot]))


def test_the_plate_exemptions_that_remain_are_the_register_specific_ones():
    """Distinguishability: PLATE is still exempt from C8/C9/C10/C17 by design --
    it is a subject-free background plate with no register look to lock. The audit
    finding is that it was *also* exempt from everything else."""
    shot = make_shot(1, "PLATE", "PLATE", prompt=DENSE_A + ", No Text. --ar 9:16 --s 200")
    assert codes(check_world_lock([shot], WORLD)) == []
    assert check_style_mechanism([shot]) == []
    assert check_format([shot]) == []


def test_c15_flags_register_a_shot_class_typo():
    # "MIDWIDE" for "MID-WIDE" would otherwise dodge C2 and inflate C4's scale count.
    shot = make_shot(1, "A", "DETAIL", "MIDWIDE", "LOW")
    assert "C15" in codes(check_vocabulary([shot]))


def test_c15_flags_shot_class_outside_register_a_closed_set():
    shot = make_shot(1, "A", "WORLD", "MID", "LOW")  # WORLD is a Register B class
    assert "C15" in codes(check_vocabulary([shot]))


def test_c15_flags_shot_class_outside_register_b_closed_set():
    shot = make_shot(1, "B", "DETAIL", "MID", "LOW")  # DETAIL is a Register A class
    assert "C15" in codes(check_vocabulary([shot]))


def test_c15_flags_plate_shot_class_not_literally_plate():
    shot = make_shot(1, "PLATE", "GRADIENT", "MID", "EYE")
    assert "C15" in codes(check_vocabulary([shot]))


def test_c15_flags_invalid_camera_height():
    shot = make_shot(1, "A", "DETAIL", "MID", "LOWISH")
    assert "C15" in codes(check_vocabulary([shot]))


def test_c15_passes_valid_vocabulary():
    shots = [
        make_shot(1, "A", "DETAIL", "MACRO", "LOW"),
        make_shot(2, "B", "WORLD", "XWIDE", "EYE"),
        make_shot(3, "PLATE", "PLATE", "MID", "HIGH"),
    ]
    assert check_vocabulary(shots) == []


FIXTURES = Path(__file__).resolve().parent / "fixtures"
WORKED = FIXTURES / "worked_example_sheet.md"


def lint_fixture(name, styleboard_name=None):
    """Lint a fixture sheet. Pass styleboard_name for a migrated sheet whose world
    lock now lives in a separate styleboard artifact rather than the sheet itself."""
    shots, sheet_world = parse_sheet((FIXTURES / name).read_text(encoding="utf-8"))
    if styleboard_name is not None:
        world = parse_world_lock((FIXTURES / styleboard_name).read_text(encoding="utf-8"))
    else:
        world = sheet_world
    return shots, lint(shots, world)


def test_passing_fixture_parses_five_shots():
    shots, _ = lint_fixture("passing_sheet.md")
    assert len(shots) == 5


def test_passing_fixture_is_clean():
    _, findings = lint_fixture("passing_sheet.md", "passing_styleboard.md")
    assert findings == [], [f"{f.check}#{f.shot_index}: {f.message}" for f in findings]


def test_failing_fixture_reproduces_the_original_defects():
    _, findings = lint_fixture("failing_sheet.md")
    found = codes(findings)
    for expected in ["C1", "C2", "C3", "C6", "C7", "C9", "C11", "C12"]:
        assert expected in found, f"{expected} not raised; got {found}"


def test_main_returns_zero_for_a_clean_sheet():
    assert main(
        [
            str(FIXTURES / "passing_sheet.md"),
            "--styleboard",
            str(FIXTURES / "passing_styleboard.md"),
        ]
    ) == 0


def test_main_returns_one_for_a_failing_sheet():
    assert main([str(FIXTURES / "failing_sheet.md")]) == 1


def test_a_missing_sheet_exits_with_its_own_code_not_the_failing_gate_code(tmp_path, capsys):
    code = main([str(tmp_path / "nope.md")])
    out = capsys.readouterr().out
    assert code == EXIT_UNREADABLE_INPUT
    assert code != EXIT_FINDINGS
    assert "nope.md" in out


def test_a_missing_styleboard_names_the_styleboard_not_the_sheet(tmp_path, capsys):
    code = main([str(FIXTURES / "passing_sheet.md"), "--styleboard", str(tmp_path / "no.md")])
    assert code == EXIT_UNREADABLE_INPUT
    assert "no.md" in capsys.readouterr().out


def test_the_exit_codes_are_all_distinct():
    """Surfacing: an automated caller branches on these. Four operator actions
    collapsing into `2` is what C-95 records."""
    assert len({EXIT_PASS, EXIT_FINDINGS, EXIT_USAGE, EXIT_UNREADABLE_INPUT,
                EXIT_UNPARSEABLE, EXIT_MISSING_DEPENDENCY}) == 6


def test_an_unparseable_sheet_no_longer_shares_a_code_with_argparse(tmp_path, capsys):
    empty = tmp_path / "empty.md"
    empty.write_text("nothing here", encoding="utf-8")
    assert main([str(empty)]) == EXIT_UNPARSEABLE


def test_worked_example_sheet_passes_gate_c():
    shots, findings = lint_fixture("worked_example_sheet.md", "worked_example_styleboard.md")
    assert len(shots) >= 8, f"worked example has only {len(shots)} shots"
    assert findings == [], [f"{f.check}#{f.shot_index}: {f.message}" for f in findings]


def test_worked_example_uses_all_four_register_a_shot_classes():
    shots, _ = lint_fixture("worked_example_sheet.md")
    classes = {s.shot_class for s in shots if s.register == "A"}
    assert classes == {"ESTABLISHING", "ACTION-ADJACENT", "DETAIL", "HUMAN-COST"}


def test_worked_example_uses_all_three_register_b_shot_classes():
    shots, _ = lint_fixture("worked_example_sheet.md")
    classes = {s.shot_class for s in shots if s.register == "B"}
    assert classes == {"FIGURE", "WORLD", "ARTIFACT"}


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


def test_c16_treats_a_numeric_sref_as_valid_syntax_but_c17_still_requires_a_slot():
    """F-13/C-79. The old test asserted a fabricated `--sref 1122334455` produced no
    findings -- an S1 defect as a green test. A number is valid *syntax*; what it is
    not is a *recorded* lock, and only a {style:...} slot resolves against the
    Library. C16 stays silent (it checks shape); C17 fires (it requires a lock)."""
    for value in ("1122334455", "https://cdn.midjourney.com/a1b2.png", "random"):
        shot = _shot(f"a strap pulled tight, No Text. --ar 9:16 --raw --s 95 --sref {value}")
        assert check_style_reference([shot]) == []
        assert [f.check for f in check_style_mechanism([shot])] == ["C17"]


def test_c17_accepts_a_style_slot():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 {style:register_a}")
    assert check_style_mechanism([shot]) == []


def test_an_invented_numeric_sref_can_no_longer_make_c20_vacuous():
    """The compounding half of C-79: with no slot on the sheet,
    sheet_declares_slots() returned False and the Library was never even read."""
    shots, _ = parse_sheet(SHEET.replace("{style:register_a}", "--sref 11111111")
                                .replace("{style:register_b}", "--sref 22222222"))
    assert sheet_declares_slots(shots) is False
    assert "C17" in codes(check_style_mechanism(shots))


def test_c16_rejects_slot_used_as_an_sref_value():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 --sref {style:register_a}")
    findings = check_style_reference([shot])
    assert [f.check for f in findings] == ["C16"]
    assert "entire flag group" in findings[0].message


def test_c16_runs_as_part_of_lint():
    shots, world = parse_sheet(SHEET.replace("--s 95", "--s 95 --sref NOT-A-CODE"))
    assert any(f.check == "C16" for f in lint(shots, world))


def test_c16_rejects_second_value_in_a_stacked_sref():
    """Midjourney supports stacking a second code onto --sref (`--sref A B`); the
    second value must be checked exactly like the first, not silently skipped."""
    shot = _shot(
        "a strap pulled tight, No Text. --ar 9:16 --raw --s 95 --sref 2481950736 SREF-INVENTED-02"
    )
    findings = check_style_reference([shot])
    assert [f.check for f in findings] == ["C16"]
    assert "SREF-INVENTED-02" in findings[0].message


def test_c16_ignores_a_following_flag_as_an_sref_value():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --sref 2481950736 --s 95")
    assert check_style_reference([shot]) == []


def test_c16_rejects_sref_with_no_value():
    """A bare --sref (no value at all, end of prompt) references nothing -- the
    same defect as an invented placeholder, one step further. It must not slip
    through silently just because it never reaches VALID_SREF_VALUE_RE."""
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 --sref")
    findings = check_style_reference([shot])
    assert [f.check for f in findings] == ["C16"]
    assert "no value" in findings[0].message


def test_c16_rejects_a_dangling_sref_followed_by_another_flag():
    """The exact repro from the finding: `--sref` immediately followed by another
    flag, with nothing in between. Neither the old SREF_FLAG_RE (required >=1
    value) nor C17's old substring test caught this -- it passed everything."""
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --s 95 --sref --ar 9:16")
    findings = check_style_reference([shot])
    assert [f.check for f in findings] == ["C16"]
    assert "no value" in findings[0].message


def test_c17_and_c16_both_fail_a_dangling_sref():
    """C17 used to treat any --sref token, dangling value or not, as "a mechanism is
    present" -- a literal --sref no longer satisfies C17 at all (C-79), so this shot
    fails both checks now: C17 because there is no {style:...} slot, C16 because the
    --sref it does carry has no valid value. Gate C fails the sheet either way, but
    for two independent reasons instead of one masking the other."""
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --s 95 --sref --ar 9:16")
    assert [f.check for f in check_style_mechanism([shot])] == ["C17"]
    assert check_style_reference([shot]) != []


def test_c16_accepts_a_legitimate_p_value():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 --p m72678")
    assert check_style_reference([shot]) == []


def test_c16_accepts_a_bare_p_flag():
    """A bare --p (no value) is Midjourney's own syntax for 'apply my active
    personalization profile' -- legitimate, unlike a bare --sref."""
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 --p")
    assert check_style_reference([shot]) == []


def test_c16_rejects_an_invented_p_placeholder():
    """The identical invented-code defect one flag over: --p takes a pID/mID/code
    (parameters.md:49), not a hand-authored label. `mj-INVENTED-01` is exactly the
    shape of an invented placeholder, not a real Midjourney personalization/
    moodboard code."""
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --s 95 --p mj-INVENTED-01")
    findings = check_style_reference([shot])
    assert [f.check for f in findings] == ["C16"]
    assert "mj-INVENTED-01" in findings[0].message


def test_c16_full_repro_ar_s_p_invented():
    """The exact repro string from the finding."""
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --s 95 --p mj-INVENTED-01")
    assert any(f.check == "C16" for f in check_style_reference([shot]))


def test_c16_fires_on_the_real_legacy_sheet():
    """The do-less sheet shipped with two invented codes. Gate C must now reject it."""
    text = (FIXTURES / "legacy_do_less_sheet.md").read_text(encoding="utf-8")
    shots, _world = parse_sheet(text)
    findings = check_style_reference(shots)
    assert findings, "the legacy sheet's placeholder codes must be rejected"
    assert all(f.check == "C16" for f in findings)
    assert any("SREF-RGS-A-DL01" in f.message for f in findings)


def test_c17_fires_when_a_shot_has_no_style_mechanism():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95")
    findings = check_style_mechanism([shot])
    assert [f.check for f in findings] == ["C17"]


def test_c17_accepts_only_a_style_slot_not_literal_sref_or_moodboard():
    """C-79/C-80: a literal --sref or --p used to satisfy C17 on its own -- neither
    resolves against the Style Library, so only the {style:...} slot may satisfy C17
    now. This is the same fixture set the old (now-inverted) test used, with the
    assertion flipped for the two literal cases."""
    for flags in ("--sref 1122334455", "--p m72678"):
        shot = _shot(f"a strap pulled tight, No Text. --ar 9:16 --raw --s 95 {flags}")
        assert [f.check for f in check_style_mechanism([shot])] == ["C17"]
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 {style:register_a}")
    assert check_style_mechanism([shot]) == []


def test_c17_rejects_a_bare_p_as_a_style_lock():
    """F-13/C-80. The old test enumerated C17's accepted mechanisms without
    distinguishing a recorded lock from an unrecorded one -- exactly the
    distinction the finding turns on. `--p` with no value is legitimate Midjourney
    syntax ('apply my active personalization profile') and stays legal for C16, but
    the look then depends on whichever operator's profile is active at paste time:
    unrecorded, unreproducible, invisible to the Library. Two characters used to
    defeat both style checks at once."""
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 --p")
    assert check_style_reference([shot]) == []          # C16: legal syntax
    assert [f.check for f in check_style_mechanism([shot])] == ["C17"]


def test_c17_rejects_a_valued_p_as_a_style_lock_too():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 --p m72678")
    assert [f.check for f in check_style_mechanism([shot])] == ["C17"]


def test_c17_exempts_plate_shots():
    shot = _shot(
        "a flat teal gradient ground, no people, No Text. --ar 9:16 --s 200",
        register="PLATE",
    )
    assert check_style_mechanism([shot]) == []


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


def test_c18_rejects_a_body_copy_even_when_a_correct_copy_also_exists_in_flags():
    """A name-membership check (does 'register_a' appear anywhere in the flags?) would
    silently accept the stray body copy below because a second, correctly-placed copy
    of the same name also sits in the flags. Position must be decided per-occurrence,
    from that occurrence's own offset in shot.prompt -- not from set membership."""
    shot = _shot(
        "a strap pulled tight {style:register_a}, No Text. "
        "--ar 9:16 --raw --s 95 {style:register_a}"
    )
    findings = check_slots([shot], SLOT_WORLD)
    assert [f.check for f in findings] == ["C18"]
    assert "after at least one literal flag" in findings[0].message


def test_c18_accepts_two_correctly_placed_declared_slots_without_over_firing():
    """Guard against the position-offset rewrite over-firing: two different slot kinds,
    both after the split point and both declared, must still produce zero findings."""
    shot = _shot(
        "a coach lowering a medal, No Text. "
        "--ar 9:16 --raw --s 95 {style:register_a} {char:coach}"
    )
    assert check_slots([shot], SLOT_WORLD) == []


def test_c18_rejects_an_invented_style_code_as_the_declared_slot_value():
    """A styleboard writing `slot_register_a: SREF-RGS-A-DL01` moves the invented-code
    defect one artifact upstream -- styleboard-format.md forbids it in prose but C18
    never checked the declared *value*, only that the slot *name* was declared."""
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 {style:register_a}")
    world = {**SLOT_WORLD, "slot_register_a": "SREF-RGS-A-DL01"}
    findings = check_slots([shot], world)
    assert [f.check for f in findings] == ["C18"]
    assert "SREF-RGS-A-DL01" in findings[0].message


def test_c18_accepts_a_real_style_library_label_as_the_declared_slot_value():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 {style:register_a}")
    world = {**SLOT_WORLD, "slot_register_a": "rgs-present-soccer-a"}
    assert check_slots([shot], world) == []


def test_c18_rejects_both_fixtures_slot_values_do_not_regress():
    """Sanity check against the two real green fixtures' actual slot_* values --
    the new value check must not fire on real Library labels."""
    for fixture in ("passing_styleboard.md", "worked_example_styleboard.md"):
        world = parse_world_lock((FIXTURES / fixture).read_text(encoding="utf-8"))
        for key in ("slot_register_a", "slot_register_b"):
            shot = _shot(
                f"a strap pulled tight, No Text. --ar 9:16 --raw --s 95 "
                f"{{{'style'}:{key.removeprefix('slot_')}}}"
            )
            assert check_slots([shot], world) == [], (fixture, key, world[key])


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
    """C-86: the reuse branch only passes when the declaration resolves to a real
    Hook shot -- SHEET's Shot 1 is 'Hook (0-3s)', so this is a backed declaration,
    not the bare-text tautology the old version of this test asserted."""
    assert check_cover_present(COVER_BLOCK) == []
    assert check_cover_present(
        SHEET + "\nCover = Hook beat still #1, no separate generation.\n"
    ) == []


def test_lint_cover_applies_format_and_style_checks_but_not_sequence():
    cover = parse_cover(COVER_BLOCK)
    findings = lint_cover(cover, SLOT_WORLD)
    assert all(f.check not in {"C1", "C2", "C3", "C4", "C5", "C6", "C7", "C11"} for f in findings)


def test_lint_cover_catches_a_bad_cover_sref():
    bad = COVER_BLOCK.replace("{style:register_a}", "--sref SREF-RGS-A-DL01")
    findings = lint_cover(parse_cover(bad), SLOT_WORLD)
    assert any(f.check == "C16" for f in findings)


TWO_COVER_BLOCKS = COVER_BLOCK + "\n" + COVER_BLOCK.replace("HUMAN-COST", "DETAIL")


def test_c19_fires_when_multiple_cover_blocks_are_present():
    """A stale draft cover left behind next to the real one must not be silently
    dropped -- parse_cover only ever returns the first match, so the second block
    is otherwise invisible to Gate C."""
    findings = check_cover_present(TWO_COVER_BLOCKS)
    assert [f.check for f in findings] == ["C19"]
    assert "2 '### Cover" in findings[0].message
    assert "exactly one cover decision" in findings[0].message


def test_declares_cover_reuse_ignores_a_match_inside_a_fenced_prompt():
    """A 'Cover = Hook' line inside a ```text prompt fence is prompt content, not a
    declaration, and must not silently satisfy C19."""
    text = (
        "PER-SHOT PROMPTS\n\n"
        "### Shot 1 — Hook (0–3s) · Register A · DETAIL · MACRO · LOW\n\n"
        "```text\n"
        "Cover = Hook shaped shadow falling across the pitch, No Text. --ar 9:16\n"
        "```\n"
    )
    assert declares_cover_reuse(text) is False
    findings = check_cover_present(text)
    assert [f.check for f in findings] == ["C19"]
    assert "no cover decision" in findings[0].message


def test_main_labels_a_cover_finding_as_cover_not_shot_0_or_sheet(tmp_path, capsys):
    bad_cover = COVER_BLOCK.replace("{style:register_a}", "--sref SREF-RGS-A-DL01")
    sheet = tmp_path / "sheet.md"
    sheet.write_text(SHEET + "\n" + bad_cover, encoding="utf-8")

    code = main([str(sheet)])
    out = capsys.readouterr().out
    assert code == 1
    assert "[C16] cover: " in out
    assert "[C16] shot 0:" not in out


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
    assert "declares no register_a_sport" not in out, (
        "the sport must resolve from the styleboard, not go missing"
    )
    assert code in (0, 1)


def test_main_falls_back_to_the_sheets_own_world_lock(tmp_path, capsys):
    sheet = tmp_path / "sheet.md"
    sheet.write_text(SHEET, encoding="utf-8")
    main([str(sheet)])
    assert "declares no register_a_sport" not in capsys.readouterr().out


def test_main_reports_a_missing_world_lock_when_no_styleboard_is_given(tmp_path, capsys):
    """Control for the two tests above: without --styleboard, a sheet stripped of its own
    WORLD LOCK block must resolve to an empty world dict, and C8 must say so. Without this
    control, the two tests above would still pass even if --styleboard silently did nothing."""
    sheet = tmp_path / "sheet.md"
    sheet.write_text(SHEET.split("WORLD LOCK")[0] + SHEET.split("PER-SHOT PROMPTS")[1],
                     encoding="utf-8")

    main([str(sheet)])
    assert "declares no register_a_sport" in capsys.readouterr().out


def test_the_cli_fails_closed_on_an_empty_styleboard_naming_the_styleboard(tmp_path, capsys):
    """gates.py:87-96 raises here, with a comment saying linting against an empty
    world 'would emit a wall of C8/C18 findings naming the wrong problem'. main()
    had no such branch and emitted 14 findings, none naming the styleboard."""
    empty = tmp_path / "styleboard.md"
    empty.write_text("=== STYLEBOARD — backfilled, not recoverable ===\n", encoding="utf-8")
    code = main([str(FIXTURES / "passing_sheet.md"), "--styleboard", str(empty)])
    out = capsys.readouterr().out
    assert code == EXIT_MISSING_DEPENDENCY
    assert "styleboard.md" in out
    assert "C8" not in out, "the wall of wrong-problem findings must not be emitted"


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


def test_a_cover_heading_with_an_unreadable_fence_is_a_finding_not_silence():
    """C-78: ```markdown instead of ```text made parse_cover return None, which is
    the same value as 'this sheet has no cover'."""
    text = SHEET + "\n### Cover — Hook · Register A · DETAIL · MACRO · LOW\n\n```markdown\nx\n```\n"
    findings = check_cover_present(text)
    assert [f.check for f in findings] == ["C19"]
    assert "unreadable" in findings[0].message


def test_an_unreadable_cover_is_distinguishable_from_no_cover_at_all():
    unreadable = SHEET + "\n### Cover — Hook · Register A · DETAIL · MACRO · LOW\n\n```markdown\nx\n```\n"
    absent = SHEET
    assert check_cover_present(unreadable)[0].message != check_cover_present(absent)[0].message


def test_c19_requires_the_reused_hook_shot_to_exist():
    """C-86: the literal text 'cover = hook' on its own line satisfied C19 for any
    sheet, with nothing checking that a hook shot existed."""
    text = "PER-SHOT PROMPTS\n\nCover = Hook beat still #1\n"
    assert "C19" in codes(check_cover_present(text))


def test_c19_accepts_a_reuse_declaration_backed_by_a_real_hook_shot():
    """Anti-tautology control."""
    assert check_cover_present(WORKED.read_text(encoding="utf-8")) == []


def test_a_mistyped_shot_fence_cannot_swallow_the_cover_prompt():
    """_read_fenced_prompt broke on SHOT_HEADING_RE but not COVER_HEADING_RE."""
    text = SHEET.replace("```text\nluminous", "```txt\nluminous") + \
        "\n### Cover — Hook · Register A · DETAIL · MACRO · LOW\n\n```text\ncover body here\n```\n"
    cover = parse_cover(text)
    assert cover is not None and cover.prompt.startswith("cover body")


# --- C20: the slot label must exist in the Style Library ----------------------
#
# C18 checks that a slot_* value *looks* like a Library label. It cannot check
# that the label *exists*, because nothing parsed docs/style-library.md. A typo
# cleared Gate C and failed at paste time -- and that was not hypothetical: the
# Library's Register B entry was created as `rgs-source-era-b` while all fourteen
# consumers, both green fixtures included, bound `rgs-sourceera-painterly-b`.

REPO_ROOT = Path(__file__).resolve().parents[1]
STYLE_LIBRARY = REPO_ROOT / "docs" / "style-library.md"
LIBRARY_TEXT = STYLE_LIBRARY.read_text(encoding="utf-8")

LIBRARY_DOC = """\
# Style Library

## Entry format

```
### <label>                       kebab-case; this is the styleboard slot_* value
  code:         <value> | UNHARVESTED
```

## Entries

### rgs-present-soccer-a

```
brand:        raisinggoodsports
code:         832507909
```

### rgs-unharvested-world-b

```
brand:        raisinggoodsports
code:         UNHARVESTED
```

## Open questions

### a stray subsection heading
"""


def test_parse_style_library_reads_the_entry_labels():
    library = parse_style_library(LIBRARY_DOC)
    assert set(library) == {"rgs-present-soccer-a", "rgs-unharvested-world-b"}
    assert library["rgs-present-soccer-a"] == "832507909"


def test_parse_style_library_ignores_the_placeholder_inside_the_entry_format_fence():
    """`## Entry format` documents the shape with a literal `### <label>` line. A
    naive `^### ` scan ingests it as an entry, so the walk is scoped to `## Entries`
    and every heading must match the kebab-case label pattern C18 already uses."""
    library = parse_style_library(LIBRARY_DOC)
    assert "<label>" not in library
    assert not any("<" in label for label in library)


def test_parse_style_library_stops_at_the_next_top_level_heading():
    """A `###` under `## Open questions` is prose structure, not an entry."""
    assert "a stray subsection heading" not in parse_style_library(LIBRARY_DOC)


def test_parse_style_library_reads_the_real_file():
    library = parse_style_library(STYLE_LIBRARY.read_text(encoding="utf-8"))
    assert "rgs-present-soccer-a" in library
    assert "rgs-sourceera-painterly-b" in library


def test_an_annotated_entry_heading_is_reported_not_dropped():
    library, findings = parse_style_library_checked(
        LIBRARY_DOC.replace("### rgs-present-soccer-a", "### rgs-present-soccer-a (channel)")
    )
    assert "rgs-present-soccer-a" not in library
    assert [f.check for f in findings] == ["PARSE"]
    assert "(channel)" in findings[0].message


def test_an_unterminated_fence_in_the_library_is_reported():
    doc = LIBRARY_DOC.replace("code:         832507909\n```", "code:         832507909\n")
    _library, findings = parse_style_library_checked(doc)
    assert any("unterminated" in f.message for f in findings)


def test_a_partially_parsed_library_is_distinguishable_from_a_complete_one():
    """The whole defect: a partial parse presented exactly like a complete one, and
    C20 then failed the sheet with an incomplete 'Known entries' list."""
    good, good_findings = parse_style_library_checked(LIBRARY_DOC)
    bad, bad_findings = parse_style_library_checked(
        LIBRARY_DOC.replace("### rgs-present-soccer-a", "### RGS-Present-Soccer-A")
    )
    assert good_findings == [] and bad_findings != []
    assert set(good) != set(bad)


def test_parse_style_library_keeps_its_original_signature():
    """P3's gates.py:111 calls linter.parse_style_library(text) and expects a dict."""
    assert isinstance(parse_style_library(LIBRARY_DOC), dict)


def test_c20_rejects_a_label_that_is_not_in_the_library():
    """The typo case: a value shaped like a label but naming no entry. This is what
    cleared Gate C and failed at paste time."""
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 {style:register_a}")
    world = {**SLOT_WORLD, "slot_register_a": "rgs-present-socer-a"}
    findings = check_slot_labels([shot], world, {"rgs-present-soccer-a": "832507909"})
    assert [f.check for f in findings] == ["C20"]
    assert "rgs-present-socer-a" in findings[0].message
    assert "docs/style-library.md" in findings[0].message


def test_c20_names_the_styleboard_as_the_file_to_edit():
    """A-34: the label comes from the styleboard's WORLD LOCK, but the finding was
    reported against the sheet's shot index, so the operator edited the sheet."""
    shot = _shot("x, No Text. --ar 9:16 --raw --s 95 {style:register_a}")
    findings = check_slot_labels([shot], {"slot_register_a": "typo-label"},
                                 {"rgs-present-soccer-a": "832507909"})
    assert [f.check for f in findings] == ["C20"]
    assert "styleboard" in findings[0].message
    assert "slot_register_a" in findings[0].message


def test_c20_still_reports_the_shot_so_the_operator_knows_which_binding_bit():
    shot = _shot("x, No Text. --ar 9:16 --raw --s 95 {style:register_a}", index=7)
    findings = check_slot_labels([shot], {"slot_register_a": "typo-label"}, {"a": ""})
    assert findings[0].shot_index == 7
    assert findings[0].beat == "shot 7"


def test_c20_accepts_a_label_that_is_in_the_library():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 {style:register_a}")
    world = {**SLOT_WORLD, "slot_register_a": "rgs-present-soccer-a"}
    assert check_slot_labels([shot], world, {"rgs-present-soccer-a": "832507909"}) == []


def test_c20_accepts_an_entry_whose_code_is_unharvested():
    """An entry with no code yet still *exists*. Gate C runs on the sheet, before any
    render, so binding to a recorded-but-unharvested world is a legitimate
    intermediate state -- that is what DISCOVERY REQUESTS carries forward. C20's job
    is to catch labels that name nothing at all."""
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 {style:register_a}")
    world = {**SLOT_WORLD, "slot_register_a": "rgs-unharvested-world-b"}
    library = parse_style_library(LIBRARY_DOC)
    assert check_slot_labels([shot], world, library) == []


def test_c20_stays_silent_on_a_value_c18_already_rejected():
    """`SREF-RGS-A-DL01` is not a label, so it is trivially absent from the Library.
    Reporting it under C20 as well would name one defect twice and point the author
    at the wrong fix -- the problem is the invented code, not a missing entry."""
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 {style:register_a}")
    world = {**SLOT_WORLD, "slot_register_a": "SREF-RGS-A-DL01"}
    library = {"rgs-present-soccer-a": "832507909"}
    assert [f.check for f in check_slots([shot], world)] == ["C18"]
    assert check_slot_labels([shot], world, library) == []


def test_c20_is_skipped_when_no_library_is_supplied():
    """lint(..., library=None) must behave exactly as it did before C20 existed."""
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 {style:register_a}")
    world = {**SLOT_WORLD, "slot_register_a": "rgs-not-in-any-library"}
    assert check_slot_labels([shot], world, None) == []


def test_c20_ignores_a_slot_sitting_in_the_prompt_body():
    """Position is C18's finding. A body-position slot must not also draw a C20."""
    shot = _shot("{style:register_a} a strap pulled tight, No Text. --ar 9:16 --raw --s 95")
    world = {**SLOT_WORLD, "slot_register_a": "rgs-not-in-the-library"}
    assert check_slot_labels([shot], world, {"rgs-present-soccer-a": "832507909"}) == []


@pytest.mark.parametrize("styleboard_name", ["passing_styleboard.md", "worked_example_styleboard.md"])
def test_every_fixture_slot_value_exists_in_the_real_style_library(styleboard_name):
    """The regression that would have caught the live mismatch. Both fixtures bound
    `rgs-sourceera-painterly-b` while the Library's entry was `rgs-source-era-b`."""
    world = parse_world_lock((FIXTURES / styleboard_name).read_text(encoding="utf-8"))
    library = parse_style_library(STYLE_LIBRARY.read_text(encoding="utf-8"))
    declared = {key: value for key, value in world.items() if key.startswith("slot_")}
    assert declared, "the fixture must still declare at least one slot"
    missing = {key: value for key, value in declared.items() if value not in library}
    assert missing == {}, f"{styleboard_name} binds labels absent from the Library: {missing}"


def test_c21_flags_a_gap_in_the_shot_indices():
    """A shot lost to a bad heading leaves indices 1,2,3,5,... The gate must say so
    rather than report 'PASS - 10 shots'."""
    shots = [make_shot(1), make_shot(2), make_shot(3), make_shot(5)]
    findings = check_shot_count(shots)
    assert [f.check for f in findings] == ["C21"]
    assert "4" in findings[0].message


def test_c21_flags_a_duplicated_shot_index():
    assert "C21" in codes(check_shot_count([make_shot(1), make_shot(2), make_shot(2)]))


def test_c21_flags_a_declared_count_that_disagrees_with_the_parse():
    findings = check_shot_count([make_shot(1), make_shot(2)], declared=3)
    assert "C21" in codes(findings)
    assert "declares 3" in findings[0].message


def test_c21_runs_inside_lint_so_both_gate_c_callers_get_it():
    """gates.py calls lint() but not parse_sheet().findings. Putting the invariant
    in lint() is what closes C-70 on the app path with no change to gates.py."""
    shots = [make_shot(1, "A"), make_shot(2, "B", "WORLD", "XWIDE", "EYE"),
             make_shot(4, "A", "ESTABLISHING", "WIDE", "HIGH")]
    assert "C21" in codes(lint(shots, {}))


def test_c21_is_silent_on_every_green_fixture():
    """Distinguishability: the invariant must separate a dropped shot from a
    legitimately short sheet, not fire on both."""
    for name in ("passing_sheet.md", "failing_sheet.md", "worked_example_sheet.md"):
        shots, _ = parse_sheet((FIXTURES / name).read_text(encoding="utf-8"))
        assert check_shot_count(shots) == [], name


FENCED_EXAMPLE = SHEET + """
Format reminder for authors:

```text
### Shot 99 — Demo · Register A · DETAIL · MACRO · LOW
```
"""


def test_a_heading_inside_a_fence_is_not_a_real_shot():
    shots, _ = parse_sheet(FENCED_EXAMPLE)
    assert [s.index for s in shots] == [1, 2]


def test_a_fenced_heading_produces_no_parse_finding_either():
    """Distinguishability: documented-example (ignore) must not be conflated with
    malformed-heading (report). declares_cover_reuse was already fence-aware for
    exactly this reason; the shot walk was not."""
    assert parse_sheet(FENCED_EXAMPLE).findings == []


def test_a_fenced_example_does_not_pollute_the_sequence_checks():
    shots, world = parse_sheet(FENCED_EXAMPLE)
    assert "C21" not in codes(lint(shots, world))


def _typoed_styleboard(tmp_path):
    """The real passing styleboard with one character removed from a slot label."""
    text = (FIXTURES / "passing_styleboard.md").read_text(encoding="utf-8")
    typoed = text.replace("rgs-sourceera-painterly-b", "rgs-sourceera-painterly-c")
    assert typoed != text
    path = tmp_path / "typoed_styleboard.md"
    path.write_text(typoed, encoding="utf-8")
    return path


def test_main_passes_the_real_fixture_against_the_real_library(capsys):
    """The end-to-end green path: a correct sheet, its styleboard, and the Library
    the labels actually resolve against."""
    exit_code = main([
        str(FIXTURES / "passing_sheet.md"),
        "--styleboard", str(FIXTURES / "passing_styleboard.md"),
    ])
    assert exit_code == 0, capsys.readouterr().out


def test_main_fails_a_sheet_whose_styleboard_names_an_unknown_label(tmp_path, capsys):
    """The defect C20 exists for: a label typo that C18 waves through because it is
    still shaped like a label. Before C20 this exited 0 and failed at paste time."""
    exit_code = main([
        str(FIXTURES / "passing_sheet.md"),
        "--styleboard", str(_typoed_styleboard(tmp_path)),
    ])
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "C20" in out
    assert "rgs-sourceera-painterly-c" in out
    assert "docs/style-library.md" in out


def test_main_fails_closed_when_the_library_is_missing(tmp_path, capsys):
    """A sheet with slots and no Library is unresolvable. Passing it would record a
    check that never ran."""
    exit_code = main([
        str(FIXTURES / "passing_sheet.md"),
        "--styleboard", str(FIXTURES / "passing_styleboard.md"),
        "--style-library", str(tmp_path / "absent.md"),
    ])
    assert exit_code == EXIT_MISSING_DEPENDENCY
    assert "Style Library not found" in capsys.readouterr().out


def test_main_fails_closed_when_the_library_has_no_entries(tmp_path, capsys):
    empty = tmp_path / "empty-library.md"
    empty.write_text("# Style Library\n\n## Entries\n\nNothing harvested yet.\n", encoding="utf-8")
    exit_code = main([
        str(FIXTURES / "passing_sheet.md"),
        "--styleboard", str(FIXTURES / "passing_styleboard.md"),
        "--style-library", str(empty),
    ])
    assert exit_code == EXIT_MISSING_DEPENDENCY
    assert "no entries parsed" in capsys.readouterr().out


SPLIT_WORLD = """\
WORLD LOCK
  register_a_sport: club soccer
  register_a_signature_objects: goal net, corner flag

  slot_register_a: rgs-present-soccer-a
"""


def test_a_blank_line_does_not_truncate_the_world_lock_block():
    parse = parse_sheet(SPLIT_WORLD)
    assert parse.world["slot_register_a"] == "rgs-present-soccer-a"


def test_a_malformed_world_lock_entry_is_reported_not_skipped():
    parse = parse_sheet("WORLD LOCK\n  register_a_sport: club soccer\n  not an entry\n")
    assert [f.check for f in parse.findings] == ["PARSE"]
    assert "not an entry" in parse.findings[0].message


def test_a_second_world_lock_block_is_rejected_rather_than_last_win():
    """A superseded block left above the live one silently overwrote it."""
    text = SPLIT_WORLD + "\nWORLD LOCK\n  register_a_sport: hockey\n"
    parse = parse_sheet(text)
    assert any("second 'WORLD LOCK'" in f.message for f in parse.findings)


def test_an_unindented_world_lock_body_is_reported_not_silently_empty():
    """Distinguishability: 'the styleboard has no world lock' and 'the styleboard's
    world lock is unindented' must not both render as {}."""
    flat = parse_sheet("WORLD LOCK\nregister_a_sport: club soccer\n")
    absent = parse_sheet("nothing here\n")
    assert flat.world == {} and absent.world == {}
    assert flat.findings != absent.findings


# --- Mutation testing: take a green sheet, break one thing, assert Gate C fails --
#
# F-14: the suite bypassed the parser, so the largest hole in the gate was
# structurally unreachable by any existing test. Each case below is an evasion the
# audit confirmed by execution against these same fixtures. `expected` is the check
# that must fire; `""` means "any finding at all, but never a pass".

MUTATIONS = [
    # id,                       find,                        replace,                     expected
    ("heading-hyphen",          "### Shot 4 — Build",        "### Shot 4 - Build",        "PARSE"),
    ("heading-endash",          "### Shot 4 — Build",        "### Shot 4 – Build",        "PARSE"),
    ("heading-no-middot",       "· Register B · ARTIFACT",   "- Register B · ARTIFACT",   "PARSE"),
    ("heading-lowercase-scale", "· ARTIFACT · CLOSE ·",      "· ARTIFACT · Close ·",      "PARSE"),
    ("heading-underscore-scale","· WORLD · MID-WIDE ·",      "· WORLD · MID_WIDE ·",      "PARSE"),
    ("heading-lowercase-reg",   "· Register B · WORLD",      "· register B · WORLD",      "PARSE"),
    ("heading-two-hashes",      "### Shot 7 —",              "## Shot 7 —",               "PARSE"),
    ("heading-deleted",         "### Shot 4 — Build",        "Shot 4 — Build",            "C21"),
    ("index-duplicated",        "### Shot 5 —",              "### Shot 4 —",              "C21"),
    ("index-renumbered",        "### Shot 11 —",             "### Shot 12 —",             "C21"),
    ("declared-count-mismatch", "PER-SHOT PROMPTS",          "SHOT COUNT: 12\n\nPER-SHOT PROMPTS", "C21"),
    ("sref-invented-number",    "{style:register_a}",        "--sref 11111111",           "C17"),
    ("sref-bare-p",             "{style:register_a}",        "--p",                       "C17"),
    ("ar-landscape",            "--ar 9:16",                 "--ar 16:9",                 "C13"),
    ("plate-relabel",           "· Register B · WORLD ·",    "· Register PLATE · PLATE ·","C14"),
    ("venue-synonym",           "a municipal club soccer",   "a vacant gym, a municipal club soccer", "C9"),
    ("registerb-photographic",  "luminous oil painting",     "photorealistic bokeh render", "C10"),
    ("fenced-heading",          "PER-SHOT PROMPTS",          "PER-SHOT PROMPTS\n\n```text\n### Shot 99 — X · Register A · DETAIL · MACRO · LOW\n```", ""),
    ("world-blank-line",        "  register_b_thinker:",     "\n  register_b_thinker:",   ""),
    ("world-second-block",      "PER-SHOT PROMPTS",          "WORLD LOCK\n  register_a_sport: hockey\n\nPER-SHOT PROMPTS", "PARSE"),
    ("cover-fence-markdown",    "```text",                   "```markdown",               ""),
    ("sport-compound-only",     "club soccer boot",          "clubsoccerboot",            "C8"),
]


@pytest.mark.parametrize("case", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_a_single_mutation_of_a_green_sheet_always_fails_gate_c(case, tmp_path, capsys):
    """The gate is fail-closed or it is not a gate. Each of these was confirmed by
    execution to pass the pre-remediation gate."""
    _id, find, replace, expected = case
    original = WORKED.read_text(encoding="utf-8")
    assert find in original, f"{_id}: mutation anchor no longer present in the fixture"
    sheet = tmp_path / "mutated.md"
    sheet.write_text(original.replace(find, replace, 1), encoding="utf-8")

    code = main([str(sheet), "--styleboard", str(FIXTURES / "worked_example_styleboard.md")])
    out = capsys.readouterr().out

    assert code != 0, f"{_id}: Gate C passed a mutated sheet\n{out}"
    assert "PASS" not in out, f"{_id}: {out}"
    if expected:
        assert f"[{expected}]" in out, f"{_id}: expected {expected}, got:\n{out}"


def test_the_unmutated_fixture_is_the_control(capsys):
    """Without this, every mutation test above would pass on a gate that failed
    everything -- the tautology the mutation class exists to avoid."""
    code = main([
        str(WORKED), "--styleboard", str(FIXTURES / "worked_example_styleboard.md")
    ])
    assert code == 0, capsys.readouterr().out


# --- C-77: the Library warns its own headings are load-bearing ---------------
#
# The coupling between docs/style-library.md's `## Entries` heading shape and
# scripts/lint_prompt_sheet.py:parse_style_library was previously documented
# only in `Open questions` §2 -- an editor tidying `## Entries` has no local
# signal at the point they would break it.


def test_the_library_warns_at_the_headings_the_parser_depends_on():
    """C-77: the coupling was documented only in Open questions §2. An editor
    reformatting the file reads Entry format and ## Entries, not the appendix."""
    text = STYLE_LIBRARY.read_text(encoding="utf-8")
    before_entries = text.split("## Entries")[0]
    assert "lint_prompt_sheet.py" in before_entries.split("## Entry format")[1]
    heading_at, _rest = text.split("## Entries", 1)
    assert "MACHINE-READ" in heading_at[-400:]


def test_the_libraryS_own_entries_still_parse_after_the_warning_edits():
    library, findings = parse_style_library_checked(STYLE_LIBRARY.read_text(encoding="utf-8"))
    assert findings == []
    assert {"rgs-present-soccer-a", "rgs-sourceera-painterly-b"} <= set(library)


LIBRARY_MUTATIONS = [
    ("entry-annotated",  "### rgs-present-soccer-a", "### rgs-present-soccer-a (channel)"),
    ("entry-capitalised","### rgs-present-soccer-a", "### RGS-Present-Soccer-A"),
    ("section-renamed",  "## Entries\n\n### rgs-sourceera-painterly-b", "## Library entries\n\n### rgs-sourceera-painterly-b"),
]


@pytest.mark.parametrize("case", LIBRARY_MUTATIONS, ids=[m[0] for m in LIBRARY_MUTATIONS])
def test_a_reformatted_style_library_fails_loudly_naming_the_library(case, tmp_path, capsys):
    """C-76: a partially-parsed Library made C20 blame the sheet for a typo the
    sheet does not have."""
    _id, find, replace = case
    library = tmp_path / "style-library.md"
    library.write_text(
        STYLE_LIBRARY.read_text(encoding="utf-8").replace(find, replace, 1), encoding="utf-8"
    )
    code = main([
        str(WORKED),
        "--styleboard", str(FIXTURES / "worked_example_styleboard.md"),
        "--style-library", str(library),
    ])
    out = capsys.readouterr().out
    assert code != 0, f"{_id}: {out}"
    assert "style-library" in out, f"{_id}: the Library must be named as the file at fault\n{out}"


def test_the_resolved_style_library_path_is_printed_on_a_pass(capsys):
    """C-75: a run against the default Library must name it in the transcript,
    on a pass and not only on a failure."""
    main([str(WORKED), "--styleboard", str(FIXTURES / "worked_example_styleboard.md")])
    assert str(STYLE_LIBRARY) in capsys.readouterr().out


def test_a_non_default_style_library_is_named_in_the_output(tmp_path, capsys):
    """Distinguishability: a run against a hand-written stub must be visibly
    different in the transcript from a run against the repo Library."""
    stub = tmp_path / "stub.md"
    stub.write_text("# x\n\n## Entries\n\n### anything-goes\n", encoding="utf-8")
    main([str(WORKED), "--styleboard", str(FIXTURES / "worked_example_styleboard.md"),
          "--style-library", str(stub)])
    out = capsys.readouterr().out
    assert "NON-DEFAULT" in out
    assert str(stub) in out


def test_the_cli_default_library_is_the_exact_path_the_app_path_hard_codes():
    """Surfacing/parity: gates.py computes repo_root/'docs'/'style-library.md'.
    Two gates wearing one name is worse than one gate."""
    assert DEFAULT_STYLE_LIBRARY == Path(__file__).resolve().parents[1] / "docs" / "style-library.md"


# --- C-49/C-50/C-51: the Library's own provenance is repaired -----------------


def test_the_library_uses_no_invented_provenance_marker():
    """C-49: `[run owner, 2026-08-08]` is a sixth marker CLAUDE.md does not define.
    A grep for [P] to enumerate operator decisions missed both of this file's."""
    assert "[run owner" not in LIBRARY_TEXT
    assert LIBRARY_TEXT.count("[P]") >= 2


def test_every_library_entry_carries_every_field_the_entry_format_declares():
    """C-50: rgs-present-soccer-a omitted `seed:` -- the only record of how a
    channel-wide durable code was produced, and unrecoverable by re-running the
    session (this file's own [T] note says a re-entry stacks rather than replaces)."""
    entries = LIBRARY_TEXT.split("## Entries", 1)[1].split("\n### ")[1:]
    for entry in entries:
        label = entry.splitlines()[0].strip()
        for field in ("brand:", "register:", "scope:", "mechanism:", "world:",
                      "seed:", "code:", "harvested_at:"):
            assert field in entry, f"{label} omits {field}"


def test_every_T_marker_in_the_library_carries_a_verification_date():
    """C-51: two undated Midjourney platform claims, one of which is the reason the
    file gives for never re-entering a locked session. The header's `**Markers:**`
    legend paragraph (added by T12's Edit 1) also names `[T]` while defining what the
    marker means -- that is vocabulary, not a claim, so it is excluded from this scan."""
    for line_no, line in enumerate(LIBRARY_TEXT.splitlines(), 1):
        if "[T]" in line and not line.startswith("**Markers:**"):
            assert "verified 20" in line, f"style-library.md:{line_no} has an undated [T]"
