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
    def boom(_repo_root, _path):
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
