import sys
from pathlib import Path

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
    check_vocabulary,
    check_style_reference,
    check_style_mechanism,
    check_slots,
    check_cover_present,
    lint_cover,
    lint,
    main,
)

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
        1, "A", prompt="a club soccer pitch, goal net behind, No Text. --ar 9:16"
    )
    assert "C8" not in codes(check_world_lock([shot], WORLD))


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


def test_c12_flags_too_few_clauses():
    body = ", ".join(f"clause {n} with several extra words here now" for n in range(4))
    shot = make_shot(1, "A", prompt=body + ", No Text. --ar 9:16")
    assert "C12" in codes(check_prompt_quality([shot]))


def test_c12_flags_too_few_words():
    body = ", ".join(f"c{n}" for n in range(12))
    shot = make_shot(1, "A", prompt=body + ", No Text. --ar 9:16")
    assert "C12" in codes(check_prompt_quality([shot]))


def test_c12_passes_a_dense_prompt():
    body = ", ".join(f"clause {n} with several extra descriptive words here" for n in range(12))
    shot = make_shot(1, "A", prompt=body + ", No Text. --ar 9:16")
    assert "C12" not in codes(check_prompt_quality([shot]))


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


def lint_fixture(name):
    shots, world = parse_sheet((FIXTURES / name).read_text(encoding="utf-8"))
    return shots, lint(shots, world)


def test_passing_fixture_parses_five_shots():
    shots, _ = lint_fixture("passing_sheet.md")
    assert len(shots) == 5


def test_passing_fixture_is_clean():
    _, findings = lint_fixture("passing_sheet.md")
    assert findings == [], [f"{f.check}#{f.shot_index}: {f.message}" for f in findings]


def test_failing_fixture_reproduces_the_original_defects():
    _, findings = lint_fixture("failing_sheet.md")
    found = codes(findings)
    for expected in ["C1", "C2", "C3", "C6", "C7", "C9", "C11", "C12"]:
        assert expected in found, f"{expected} not raised; got {found}"


def test_main_returns_zero_for_a_clean_sheet():
    assert main([str(FIXTURES / "passing_sheet.md")]) == 0


def test_main_returns_one_for_a_failing_sheet():
    assert main([str(FIXTURES / "failing_sheet.md")]) == 1


def test_main_returns_two_when_no_shots_parse(tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("nothing here", encoding="utf-8")
    assert main([str(empty)]) == 2


def test_worked_example_sheet_passes_gate_c():
    shots, findings = lint_fixture("worked_example_sheet.md")
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


def test_c16_does_not_crash_on_sref_with_no_value():
    shot = _shot("a strap pulled tight, No Text. --ar 9:16 --raw --s 95 --sref")
    assert check_style_reference([shot]) == []


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
