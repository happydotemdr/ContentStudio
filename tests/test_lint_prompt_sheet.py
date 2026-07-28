import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lint_prompt_sheet import (  # noqa: E402
    Shot,
    parse_sheet,
    prompt_body,
    prompt_flags,
    body_clauses,
    body_word_count,
    signature_objects,
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
