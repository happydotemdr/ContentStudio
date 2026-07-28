import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lint_prompt_sheet import (  # noqa: E402
    Shot,
    Finding,
    parse_sheet,
    prompt_body,
    prompt_flags,
    body_clauses,
    body_word_count,
    signature_objects,
    check_sequence,
    check_register_balance,
    check_world_lock,
)

SHEET = """\
=== VISUAL PROMPT SHEET — demo ===

WORLD LOCK
  register_a_sport: club soccer
  register_a_venue: municipal club soccer complex
  register_a_signature_objects: goal net, corner flag, painted touchline
  register_b_thinker: Plutarch

PER-SHOT PROMPTS

### Shot 1 — Hook (0–3s) · Register A · DETAIL · MACRO · LOW
Changes vs. previous: opening frame.

```text
documentary sports photography, a strap being pulled tight, on cropped winter turf, No Text. --ar 9:16 --raw --s 95
```

### Shot 2 — Setup (3–8s) · Register B · WORLD · XWIDE · EYE
Changes vs. previous: register switch to the source era.

```text
luminous oil painting on aged linen, a colonnade at dawn, olive branches beyond, No Text. --ar 9:16 --s 520
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
    assert shots[0].prompt.endswith("--ar 9:16 --raw --s 95")


def test_parse_sheet_reads_world_lock():
    _, world = parse_sheet(SHEET)
    assert world["register_a_sport"] == "club soccer"
    assert world["register_b_thinker"] == "Plutarch"


def test_signature_objects_splits_on_commas():
    _, world = parse_sheet(SHEET)
    assert signature_objects(world) == ["goal net", "corner flag", "painted touchline"]


def test_prompt_body_and_flags_split_at_first_flag():
    shots, _ = parse_sheet(SHEET)
    assert prompt_flags(shots[0]) == "--ar 9:16 --raw --s 95"
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
