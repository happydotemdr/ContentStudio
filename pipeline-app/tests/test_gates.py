from pathlib import Path

import pytest

from pipeline_app import gates

REPO_ROOT = Path(__file__).resolve().parents[2]

CLEAN_SCRIPT = (
    'HOOK (0–3s | 6 words): "Best part was the mud today."\n'
    "GATES\n  Gate E (fresh Opus critic): pass\n"
)
DASHED_SCRIPT = (
    # 0-5s (not 0-3s): the beat needs enough runway that the em-dash trips D1
    # without also tripping D5's wpm ceiling on this line's 9 spoken words --
    # this test isolates D1, not D5.
    'HOOK (0–5s | 8 words): "It is not more serious play — it is labor."\n'
    "GATES\n  Gate E (fresh Opus critic): pass\n"
)


def test_scripting_stage_passes_a_clean_script(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(CLEAN_SCRIPT, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path)
    assert [r["status"] for r in results] == ["pass"]
    assert results[0]["name"] == "gate_d_script_language"


def test_scripting_stage_fails_a_dashed_script(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(DASHED_SCRIPT, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path)
    assert results[0]["status"] == "fail"
    assert [f["check"] for f in results[0]["findings"]] == ["D1"]


def test_skipped_findings_are_recorded_but_do_not_fail(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(
        'HOOK (0–3s | 6 words): "Best part was the mud today."\n'
        '[re-hook beat @ ~15s]: "His proof, a trader who bought the presses."\n'
        "GATES\n  Gate E (fresh Opus critic): pass\n",
        encoding="utf-8",
    )
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path)
    assert results[0]["status"] == "pass"
    assert any(f["kind"] == "skipped" for f in results[0]["findings"])


def test_a_script_whose_timings_are_all_unreadable_fails_the_gate(tmp_path):
    """Finding 2: `skipped` findings do not block, so a script using colon
    timestamps throughout produced ALL-skipped pace findings and recorded
    `status: "pass"` -- indistinguishable at the approval boundary from a
    script whose every beat D5 actually rated. This is the app-side half of
    the fix: the whole-script finding is an ordinary blocking one, so the gate
    result is `fail`."""
    path = tmp_path / "raw_output.md"
    path.write_text(
        'HOOK (0:00–0:03 | 8 words): "Best part was the mud today, honestly."\n'
        'SETUP (0:03–0:08 | 6 words): "Kids do that every single time."\n'
        "GATES\n  Gate E (fresh Opus critic): pass\n",
        encoding="utf-8",
    )
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path)
    assert results[0]["status"] == "fail"
    assert any(
        f["kind"] == "fail" and "never checked" in f["message"]
        for f in results[0]["findings"]
    )


def test_unparseable_script_is_an_error_not_a_pass(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text("no beats at all\n", encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path)
    assert results[0]["status"] == "error"


def test_a_linter_that_raises_is_an_error_not_a_pass(tmp_path, monkeypatch):
    def boom(_repo_root, _path, _upstream):
        raise RuntimeError("linter exploded")

    monkeypatch.setitem(gates.GATE_REGISTRY, "scripting", [("gate_boom", boom)])
    path = tmp_path / "raw_output.md"
    path.write_text(CLEAN_SCRIPT, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path)
    assert results[0]["status"] == "error"
    assert "linter exploded" in results[0]["findings"][0]["message"]


def test_visual_stage_is_registered():
    assert "visual" in gates.GATE_REGISTRY


def test_unregistered_stage_returns_no_results(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text("anything\n", encoding="utf-8")
    assert gates.run_gates_for_stage(REPO_ROOT, "ideation", path) == []


# --- Gate C: the world lock lives in the styleboard, not the sheet -----------
#
# visual-prompts/SKILL.md instructs the skill NOT to re-emit the WORLD LOCK
# block into its sheet, so a post-styleboard-split sheet carries no world lock
# of its own. A gate that parsed only the sheet resolved an empty world and
# fired C8 on every Register A shot plus C18 on every slot token -- blocking
# approval on every correctly-authored sheet. These tests pin the sheet and the
# styleboard as two separate inputs, exactly as the CLI's --styleboard does.

FIXTURES = REPO_ROOT / "tests" / "fixtures"


def _visual_gate(sheet: Path, upstream: dict[str, Path] | None = None) -> dict:
    results = gates.run_gates_for_stage(REPO_ROOT, "visual", sheet, upstream)
    assert len(results) == 1
    return results[0]


def test_visual_gate_reads_the_world_lock_from_the_styleboard():
    result = _visual_gate(
        FIXTURES / "passing_sheet.md",
        {"styleboard": FIXTURES / "passing_styleboard.md"},
    )
    assert result["status"] == "pass", result["findings"]
    assert result["findings"] == []


def test_visual_gate_without_a_styleboard_uses_a_legacy_sheets_own_world_lock():
    """A pre-split sheet still carries its own WORLD LOCK block. With no
    styleboard upstream, that block is the world -- so C8 must not fire for a
    missing sport. (The sheet still fails on C16's placeholder --sref codes;
    that is the point of C16 and is asserted separately below.)"""
    result = _visual_gate(FIXTURES / "legacy_do_less_sheet.md")
    checks = {f["check"] for f in result["findings"]}
    assert "C8" not in checks, result["findings"]


def test_visual_gate_errors_when_the_styleboard_has_no_recoverable_world_lock(tmp_path):
    """backfill_styleboard_rows writes an honest "not recoverable" styleboard
    for a project that completed `visual` before the stage existed. Linting a
    sheet against an empty world would report a wall of C8/C18 findings that
    name the wrong problem. Fail closed, and say which artifact is empty."""
    styleboard = tmp_path / "artifact.v1.md"
    styleboard.write_text(
        "=== STYLEBOARD — legacy (backfilled) ===\n\n"
        "WORLD LOCK\n  not recoverable — no block could be lifted.\n",
        encoding="utf-8",
    )
    result = _visual_gate(
        FIXTURES / "passing_sheet.md", {"styleboard": styleboard}
    )
    assert result["status"] == "error"
    assert "WORLD LOCK" in result["findings"][0]["message"]


def test_visual_gate_enforces_the_cover_lint():
    """C19 and the cover checks are part of the CLI's Gate C. An app-side gate
    that called lint() without them was a materially weaker gate wearing the
    same name."""
    result = _visual_gate(FIXTURES / "legacy_do_less_sheet.md")
    assert result["status"] == "fail"
    assert "C19" in {f["check"] for f in result["findings"]}


def test_visual_gate_rejects_placeholder_sref_codes():
    """C16 fires once per shot carrying an invented placeholder code. The
    fixture is a two-shot excerpt of the pre-split do-less sheet, whose real
    15-shot original trips C16 fourteen times."""
    result = _visual_gate(FIXTURES / "legacy_do_less_sheet.md")
    c16 = [f for f in result["findings"] if f["check"] == "C16"]
    assert len(c16) == 2, [f["message"] for f in c16]
    assert all("SREF-RGS-" in f["message"] for f in c16)


def test_visual_gate_resolves_slot_labels_against_the_style_library(tmp_path):
    """C20 in app mode. The gate docstring's promise is that the app and the CLI are
    one gate, not a stricter CLI and a laxer app -- so a label typo the CLI fails on
    must fail here too. Before C20, this sheet passed both and failed at paste time,
    when a human pasted a token resolving to no Library entry."""
    text = (FIXTURES / "passing_styleboard.md").read_text(encoding="utf-8")
    styleboard = tmp_path / "artifact.v1.md"
    styleboard.write_text(
        text.replace("rgs-sourceera-painterly-b", "rgs-sourceera-painterly-c"),
        encoding="utf-8",
    )
    result = _visual_gate(FIXTURES / "passing_sheet.md", {"styleboard": styleboard})
    assert result["status"] == "fail"
    c20 = [f for f in result["findings"] if f["check"] == "C20"]
    assert c20, result["findings"]
    assert "rgs-sourceera-painterly-c" in c20[0]["message"]
    assert "docs/style-library.md" in c20[0]["message"]


def test_visual_gate_passes_the_real_fixture_against_the_real_library():
    """C20 must not fire on the fixtures' real labels -- the regression guard for the
    rename that made `rgs-sourceera-painterly-b` resolvable."""
    result = _visual_gate(
        FIXTURES / "passing_sheet.md",
        {"styleboard": FIXTURES / "passing_styleboard.md"},
    )
    assert result["status"] == "pass", result["findings"]
