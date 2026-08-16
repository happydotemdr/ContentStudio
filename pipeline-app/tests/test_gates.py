import ast
import asyncio
import shutil
import sys
from pathlib import Path

import pytest

from pipeline_app import artifacts, gates
from pipeline_app.pipeline_config import StageDef

REPO_ROOT = Path(__file__).resolve().parents[2]

# Genuinely five-beat, fully-compliant scripts (T2 requires all five top-level
# beats; T4 requires a >50%-ratable pace floor). Both are reused unmodified by
# three other tests below (test_a_linter_that_raises_is_an_error_not_a_pass,
# test_a_linter_calling_sys_exit_is_an_error_not_an_escape,
# test_genuine_cancellation_is_re_raised_not_swallowed) that never actually
# parse CLEAN_SCRIPT's content -- only that it is valid UTF-8 text.
CLEAN_SCRIPT = (
    'HOOK (0–3s | 6 words): "Best part was the mud today."\n'
    'SETUP (3–8s | 6 words): "Kids do that every single time."\n'
    'BUILD/VALUE (8–18s | 10 words): "A position stand reports that kids still reach elite level."\n'
    'PAYOFF (18–28s | 10 words): "The next tier exists because someone needs it sold now."\n'
    'LOOP/CTA (28–33s | 5 words): "Best part was the mud."\n'
    "GATES\n  Gate E (fresh Opus critic): pass\n"
)
DASHED_SCRIPT = (
    # 0-5s (not 0-3s): the beat needs enough runway that the em-dash trips D1
    # without also tripping D5's wpm ceiling on this line's 9 spoken words --
    # this test isolates D1, not D5. The other four beats are otherwise
    # identical to CLEAN_SCRIPT's, so this script's only defect is the
    # HOOK line's em-dash.
    'HOOK (0–5s | 8 words): "It is not more serious play — it is labor."\n'
    'SETUP (5–10s | 6 words): "Kids do that every single time."\n'
    'BUILD/VALUE (10–20s | 10 words): "A position stand reports that kids still reach elite level."\n'
    'PAYOFF (20–30s | 10 words): "The next tier exists because someone needs it sold now."\n'
    'LOOP/CTA (30–35s | 5 words): "Best part was the mud."\n'
    "GATES\n  Gate E (fresh Opus critic): pass\n"
)


def test_scripting_stage_passes_a_clean_script(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(CLEAN_SCRIPT, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path, {})
    assert [r["status"] for r in results] == ["pass"]
    assert results[0]["name"] == "gate_d_script_language"


def test_scripting_stage_fails_a_dashed_script(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(DASHED_SCRIPT, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path, {})
    assert results[0]["status"] == "fail"
    # D1 is the script's only defect; D3/D4 also always reports its scope-disclosure
    # `info` finding (see check_vocabulary), which is non-blocking and must not be
    # mistaken for a second real violation.
    assert [f["check"] for f in results[0]["findings"]] == ["D1", "D3/D4"]
    assert [f["check"] for f in results[0]["findings"] if f["kind"] not in ("skipped", "info")] == ["D1"]


def test_skipped_findings_are_recorded_but_do_not_fail(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(
        # Five real, budgeted beats (clears T2's beat-set requirement and T4's
        # >50%-ratable floor: 5 of 6 VO lines carry a computable range) plus one
        # still-unratable old-format re-hook line, mirroring
        # tests/test_lint_script_language.py's test_d5_skips_a_beat_with_no_range_and_says_so.
        'HOOK (0–3s | 6 words): "Best part was the mud today."\n'
        'SETUP (3–8s | 6 words): "Kids do that every single time."\n'
        'BUILD/VALUE (8–18s | 10 words): "A position stand reports that kids still reach elite level."\n'
        '[re-hook beat @ ~15s]: "His proof, a trader who bought the presses."\n'
        'PAYOFF (18–28s | 10 words): "The next tier exists because someone needs it sold now."\n'
        'LOOP/CTA (28–33s | 5 words): "Best part was the mud."\n'
        "GATES\n  Gate E (fresh Opus critic): pass\n",
        encoding="utf-8",
    )
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path, {})
    assert results[0]["status"] == "pass"
    assert any(f["kind"] == "skipped" for f in results[0]["findings"])


# P3's §6.2 contract: run_script_language_gate's findings must be exactly what
# the CLI linter itself produces for the same text, and the gate's overall
# blocking judgement must agree with what the CLI's main() would return. A
# hardcoded literal in run_gates_for_stage (Part 1's bug) does not show up as a
# wrong finding -- the findings list is identical either way -- it shows up
# only as a status/exit-code disagreement, which is what this test's second
# assertion catches.
MISSING_BEAT_SCRIPT = (
    'HOOK (0–3s | 6 words): "Best part was the mud today."\n'
    'SETUP (3–8s | 6 words): "Kids do that every single time."\n'
    'BUILD/VALUE (8–18s | 10 words): "A position stand reports that kids still reach elite level."\n'
    'PAYOFF (18–28s | 10 words): "The next tier exists because someone needs it sold now."\n'
    "GATES\n  Gate E (fresh Opus critic): pass\n"
)
MALFORMED_RANGE_SCRIPT = (
    'HOOK (8–3s | 6 words): "Best part was the mud today."\n'
    'SETUP (3–8s | 6 words): "Kids do that every single time."\n'
    'BUILD/VALUE (8–18s | 10 words): "A position stand reports that kids still reach elite level."\n'
    'PAYOFF (18–28s | 10 words): "The next tier exists because someone needs it sold now."\n'
    'LOOP/CTA (28–33s | 5 words): "Best part was the mud."\n'
    "GATES\n  Gate E (fresh Opus critic): pass\n"
)


def test_gates_py_mirrors_the_cli_linter(tmp_path):
    scripts_dir = REPO_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import lint_script_language as linter

    for text in (CLEAN_SCRIPT, DASHED_SCRIPT, MISSING_BEAT_SCRIPT, MALFORMED_RANGE_SCRIPT):
        path = tmp_path / "raw_output.md"
        path.write_text(text, encoding="utf-8")

        gate_findings = gates.run_script_language_gate(REPO_ROOT, path, {})
        vo_lines, parse_findings = linter.parse_script(text)
        expected_findings = [
            {"check": f.check, "beat": f.beat, "message": f.message, "kind": f.kind}
            for f in linter.lint(vo_lines, text, parse_findings)
        ]
        assert gate_findings == expected_findings

        cli_rc = linter.main([str(path)])
        results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path, {})
        assert (results[0]["status"] == "fail") == (cli_rc == 1)


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
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path, {})
    assert results[0]["status"] == "fail"
    assert any(
        f["kind"] == "fail" and "never checked" in f["message"]
        for f in results[0]["findings"]
    )


def test_unparseable_script_is_an_error_not_a_pass(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text("no beats at all\n", encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path, {})
    assert results[0]["status"] == "error"


def test_the_zero_vo_lines_error_names_the_specific_parse_findings(tmp_path):
    """Final-review finding #1, app-side half. When every beat heading is
    disguised, `parse_script` already worked out precisely why -- naming the
    line and the defect -- before concluding there were zero VO lines. The
    ValueError run_script_language_gate raises on that path used to carry
    only the generic "no voiceover lines parsed" sentence; it must now also
    carry the specific parse-finding text, since that message becomes the
    lone finding on the `status: "error"` result (run_gates_for_stage's
    existing exception handler, unchanged by this fix)."""
    path = tmp_path / "raw_output.md"
    path.write_text(
        '**HOOK** (0–3s | 6 words): "Best part was the mud today."\n'
        '**SETUP** (3–8s | 6 words): "Kids do that every single time."\n',
        encoding="utf-8",
    )
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path, {})
    assert results[0]["status"] == "error"
    message = results[0]["findings"][0]["message"]
    assert "no voiceover lines parsed" in message
    assert "not a parseable beat heading" in message
    assert "HOOK" in message and "SETUP" in message


def test_a_linter_that_raises_is_an_error_not_a_pass(tmp_path, monkeypatch):
    def boom(_repo_root, _path, _upstream):
        raise RuntimeError("linter exploded")

    monkeypatch.setitem(gates.GATE_REGISTRY, "scripting", [("gate_boom", boom)])
    path = tmp_path / "raw_output.md"
    path.write_text(CLEAN_SCRIPT, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path, {})
    assert results[0]["status"] == "error"
    assert "linter exploded" in results[0]["findings"][0]["message"]


def test_a_linter_calling_sys_exit_is_an_error_not_an_escape(tmp_path, monkeypatch):
    """A-40: the fail-closed claim held for everything under Exception but not
    for BaseException. A linter calling sys.exit() at import (lint_prompt_sheet
    guards this only by __name__) raised SystemExit straight through the handler.
    In the turn path that call sits AFTER turn_service's own except BaseException
    block closes, so the escape left the turn AND the stage at `running`, wedging
    the app's single-flight lock until a restart."""
    def exiting(_repo_root, _path, _upstream):
        raise SystemExit(2)

    monkeypatch.setitem(gates.GATE_REGISTRY, "scripting", [("gate_exit", exiting)])
    path = tmp_path / "raw_output.md"
    path.write_text(CLEAN_SCRIPT, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "scripting", path, {})
    assert results[0]["status"] == "error"
    assert "SystemExit" in results[0]["findings"][0]["message"]


@pytest.mark.parametrize("exc", [KeyboardInterrupt, asyncio.CancelledError])
def test_genuine_cancellation_is_re_raised_not_swallowed(tmp_path, monkeypatch, exc):
    """The other half, and the reason this is not a widened BLE001: cancellation
    must still propagate. Nothing NEW is swallowed -- only SystemExit-class
    escapes that previously wedged a stage become recorded errors."""
    def cancelling(_repo_root, _path, _upstream):
        raise exc()

    monkeypatch.setitem(gates.GATE_REGISTRY, "scripting", [("gate_cancel", cancelling)])
    path = tmp_path / "raw_output.md"
    path.write_text(CLEAN_SCRIPT, encoding="utf-8")
    with pytest.raises(exc):
        gates.run_gates_for_stage(REPO_ROOT, "scripting", path, {})


def test_visual_stage_is_registered():
    assert "visual" in gates.GATE_REGISTRY


def test_unregistered_stage_returns_no_results(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text("anything\n", encoding="utf-8")
    assert gates.run_gates_for_stage(REPO_ROOT, "grounding", path, {}) == []


IDEATION_HEADINGS = (
    "## Angle / take\n[body]\n\n"
    "## Hook concept\n[body]\n\n"
    "## Packaging direction\n[body]\n\n"
    "## Validation\n[body]\n\n"
    "## Handoff\n[body]\n"
)


def test_ideation_stage_is_registered():
    assert "ideation" in gates.GATE_REGISTRY


def test_ideation_gate_passes_a_complete_brief(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(IDEATION_HEADINGS, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "ideation", path, {})
    assert len(results) == 1
    assert results[0]["name"] == "gate_o_ideation_contract"
    assert results[0]["status"] == "pass"
    assert results[0]["findings"] == []


def test_ideation_gate_flags_a_missing_required_heading(tmp_path):
    path = tmp_path / "raw_output.md"
    text = IDEATION_HEADINGS.replace("## Validation\n[body]\n\n", "")
    path.write_text(text, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "ideation", path, {})
    assert results[0]["status"] == "fail"
    checks = [f["check"] for f in results[0]["findings"]]
    assert "OI1" in checks or "OI2" in checks or "OI3" in checks or "OI4" in checks
    assert any("Validation" in f["message"] for f in results[0]["findings"])


def test_ideation_gate_does_not_require_the_conditional_grounding_section(tmp_path):
    """IDEATION_HEADINGS already omits '## Grounding' entirely -- confirms
    its absence alone, with every required heading present, still passes."""
    path = tmp_path / "raw_output.md"
    path.write_text(IDEATION_HEADINGS, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "ideation", path, {})
    assert results[0]["status"] == "pass"


VOICEOVER_HEADINGS = (
    "## Voice pick\n[body]\n\n"
    "## Settings\n[body]\n\n"
    "## Script, reformatted for TTS\n[body]\n\n"
    "## Production & loudness\n[body]\n\n"
    "## Downstream\n[body]\n"
)


def test_voiceover_stage_is_registered():
    assert "voiceover" in gates.GATE_REGISTRY


def test_voiceover_gate_passes_a_complete_brief(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(VOICEOVER_HEADINGS, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "voiceover", path, {})
    assert len(results) == 1
    assert results[0]["name"] == "gate_o_voiceover_contract"
    assert results[0]["status"] == "pass"


def test_voiceover_gate_requires_the_literal_comma_in_the_tts_heading(tmp_path):
    """The heading is '## Script, reformatted for TTS' with a comma -- a
    brief that drops it must fail, not silently pass on a near-miss."""
    path = tmp_path / "raw_output.md"
    text = VOICEOVER_HEADINGS.replace(
        "## Script, reformatted for TTS", "## Script reformatted for TTS"
    )
    path.write_text(text, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "voiceover", path, {})
    assert results[0]["status"] == "fail"
    assert any("reformatted for TTS" in f["message"] for f in results[0]["findings"])


def test_voiceover_gate_flags_a_missing_downstream_section(tmp_path):
    path = tmp_path / "raw_output.md"
    text = VOICEOVER_HEADINGS.replace("## Downstream\n[body]\n", "")
    path.write_text(text, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "voiceover", path, {})
    assert results[0]["status"] == "fail"


def test_voiceover_gate_does_not_require_non_empty_section_bodies(tmp_path):
    """The gate checks structure (all five headings present), not content
    quality -- a thin body under a present heading is legitimately valid,
    not a fault, and must not be conflated with a missing section."""
    path = tmp_path / "raw_output.md"
    thin = (
        "## Voice pick\n\n## Settings\n\n## Script, reformatted for TTS\n\n"
        "## Production & loudness\n\n## Downstream\n"
    )
    path.write_text(thin, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "voiceover", path, {})
    assert results[0]["status"] == "pass"


# --- Gate C: the world lock lives in the styleboard, not the sheet -----------
#
# visual-prompts/SKILL.md instructs the skill NOT to re-emit the WORLD LOCK
# block into its sheet, so a post-styleboard-split sheet carries no world lock
# of its own. A gate that parsed only the sheet resolved an empty world and
# fired C8 on every Register A shot plus C18 on every slot token -- blocking
# approval on every correctly-authored sheet. These tests pin the sheet and the
# styleboard as two separate inputs, exactly as the CLI's --styleboard does.

FIXTURES = REPO_ROOT / "tests" / "fixtures"


def _visual_gate(sheet: Path, upstream: dict[str, Path] = {}) -> dict:
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


def test_a_legacy_sheet_with_no_styleboard_upstream_uses_its_own_world_lock():
    """A pre-split sheet still carries its own WORLD LOCK block. With no
    styleboard upstream, that block is the world -- so C8's sport-naming
    sub-check must not fire for a missing sport. (The sheet still fails on
    C16's placeholder --sref codes; that is the point of C16 and is asserted
    separately below.)

    Narrowed to the sport sub-check specifically: C8 also runs an unrelated
    object-count sub-check (>=2 named register_a_signature_objects per
    Register-A shot, relaxed to 1 for CLOSE/MACRO scale), which legitimately
    fires on this fixture's MID-WIDE Hook shot (only 1 of 3 declared objects
    named) for a real, already-correct reason unrelated to what this test
    covers. A blanket `"C8" not in checks` conflated the two sub-checks."""
    result = _visual_gate(FIXTURES / "legacy_do_less_sheet.md", {})
    sport_findings = [
        f for f in result["findings"]
        if f["check"] == "C8"
        and ("does not name the sport" in f["message"] or "declares no register_a_sport" in f["message"])
    ]
    assert sport_findings == [], result["findings"]


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


def test_the_empty_world_error_names_the_styleboard_and_carries_a_check_id(tmp_path):
    """A-31: the app raises and records status "error" naming the styleboard;
    the CLI prints a wall of per-shot C8/C18 naming the sheet. Both block, so
    nothing bad ships -- but an operator reproducing an app failure on the CLI
    gets a different report. The app's finding must carry a real check id and
    say, in words, what the CLI will print instead."""
    styleboard = tmp_path / "artifact.v1.md"
    styleboard.write_text("WORLD LOCK\n  not recoverable\n", encoding="utf-8")
    result = _visual_gate(FIXTURES / "passing_sheet.md", {"styleboard": styleboard})
    assert result["status"] == "error"
    finding = result["findings"][0]
    assert finding["check"] == "C0"
    assert finding["kind"] == "error"
    assert "WORLD LOCK" in finding["message"]
    assert "lint_prompt_sheet" in finding["message"]


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


# --- T1: the parity guard -----------------------------------------------------

APP_PKG = Path(__file__).resolve().parents[1] / "pipeline_app"


def _gate_call_sites() -> list[tuple[Path, ast.Call]]:
    """Every `run_gates_for_stage(...)` call in production app code, by AST.

    Deliberately static, not behavioural: a third caller added tomorrow is caught
    the moment it is written, not the first time someone runs it against a
    `visual` stage with a real styleboard upstream."""
    sites: list[tuple[Path, ast.Call]] = []
    for py in sorted(APP_PKG.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name == "run_gates_for_stage":
                sites.append((py, node))
    return sites


def test_every_production_gate_call_site_passes_a_resolved_upstream_map():
    """A-30/A-62: routes/stages.py called run_gates_for_stage WITHOUT `upstream`,
    so a hand-edited visual sheet was linted against its own legacy world lock
    instead of the styleboard's -- the exact 'stricter CLI, laxer app' split
    gates.py's own docstring forbids. Two callers, identical strictness, enforced
    statically so a third cannot drift."""
    sites = _gate_call_sites()
    assert len(sites) == 2, [f"{p.name}:{c.lineno}" for p, c in sites]
    for path, call in sites:
        positional = call.args[3:]
        keyword = [kw.value for kw in call.keywords if kw.arg == "upstream"]
        supplied = positional or keyword
        assert supplied, f"{path.name}:{call.lineno} omits `upstream`"
        arg = supplied[0]
        assert not (isinstance(arg, ast.Dict) and not arg.keys), (
            f"{path.name}:{call.lineno} passes a literal empty upstream map -- "
            "that is the defect wearing a passing test"
        )
        assert isinstance(arg, (ast.Name, ast.Attribute, ast.Call)), (
            f"{path.name}:{call.lineno} passes {ast.dump(arg)} as `upstream`; "
            "it must be a resolved mapping, not a literal"
        )


def test_run_gates_for_stage_refuses_to_be_called_without_an_upstream_map():
    """Fail-closed at the signature: the default `upstream=None` was what let the
    edit path silently run a different Gate C under the same name."""
    with pytest.raises(TypeError):
        gates.run_gates_for_stage(REPO_ROOT, "visual", FIXTURES / "passing_sheet.md")


# --- T2: resolve_upstream_by_stage -------------------------------------------


def test_resolve_upstream_by_stage_omits_a_dependency_with_no_artifact(tmp_path):
    """An upstream with nothing on disk must be ABSENT from the map, not present
    with a None value -- run_prompt_sheet_gate branches on `upstream.get(...) is
    None` and a None value would take the legacy-sheet path silently."""
    stages = [
        StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02"),
        StageDef(id="styleboard", skill="shorts-styleboard", dir_prefix="02b",
                 depends_on=["scripting"]),
        StageDef(id="visual", skill="visual-prompts", dir_prefix="03",
                 depends_on=["scripting", "styleboard"]),
    ]
    artifacts.write_artifact(tmp_path / "02-scripting", 1, {"stage": "shorts-scripting"}, "s")
    resolved = gates.resolve_upstream_by_stage(tmp_path, stages, stages[2])
    assert list(resolved) == ["scripting"]


def test_resolve_upstream_by_stage_preserves_depends_on_order(tmp_path):
    """compute_depends_on takes `list(resolved.values())`, and the recorded
    `depends_on` order must match downstream consumers so write paths produce
    consistent frontmatter. Write both scripting and styleboard artifacts,
    resolve against the `visual` stage_def above, and assert
    `list(resolved) == ["scripting", "styleboard"]` (declaration order)."""
    stages = [
        StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02"),
        StageDef(id="styleboard", skill="shorts-styleboard", dir_prefix="02b",
                 depends_on=["scripting"]),
        StageDef(id="visual", skill="visual-prompts", dir_prefix="03",
                 depends_on=["scripting", "styleboard"]),
    ]
    artifacts.write_artifact(tmp_path / "02-scripting", 1, {"stage": "shorts-scripting"}, "s")
    artifacts.write_artifact(tmp_path / "02b-styleboard", 1, {"stage": "shorts-styleboard"}, "b")
    resolved = gates.resolve_upstream_by_stage(tmp_path, stages, stages[2])
    assert list(resolved) == ["scripting", "styleboard"]


def test_every_keyword_defaults_to_the_pre_widening_behaviour(tmp_path):
    """The three keywords exist because different call sites need different
    resolution semantics. Their DEFAULTS are what keep P3's own call site
    unchanged -- so the defaults are the contract."""
    stages = [
        StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02"),
        StageDef(id="styleboard", skill="shorts-styleboard", dir_prefix="02b",
                 depends_on=["scripting"]),
    ]
    # a DRAFT upstream: visible by default, invisible under approved_only
    artifacts.write_artifact(
        tmp_path / "02-scripting", 1,
        {"stage": "shorts-scripting", "status": "draft"}, "draft script",
    )
    assert list(gates.resolve_upstream_by_stage(tmp_path, stages, stages[1])) == ["scripting"]
    assert gates.resolve_upstream_by_stage(
        tmp_path, stages, stages[1], repo_root=tmp_path, approved_only=True
    ) == {}


def test_approved_only_skips_a_non_final_draft_in_favour_of_an_older_final_version(tmp_path):
    """approved_only=True must not just return {} when nothing is final -- it
    must specifically prefer an OLDER final version over a NEWER draft, proving
    it actually inspects each version's status rather than only the latest."""
    stages = [
        StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02"),
        StageDef(id="styleboard", skill="shorts-styleboard", dir_prefix="02b",
                 depends_on=["scripting"]),
    ]
    artifacts.write_artifact(
        tmp_path / "02-scripting", 1, {"stage": "shorts-scripting", "status": "final"}, "v1 final",
    )
    artifacts.write_artifact(
        tmp_path / "02-scripting", 2, {"stage": "shorts-scripting", "status": "draft"}, "v2 draft",
    )
    resolved = gates.resolve_upstream_by_stage(
        tmp_path, stages, stages[1], repo_root=tmp_path, approved_only=True
    )
    assert resolved["scripting"] == tmp_path / "02-scripting" / "artifact.v1.md"


def test_include_optional_is_off_by_default(tmp_path):
    """A stage may declare optional_depends_on (supplies input but never gates
    unlocking); it must not appear unless asked for. StageDef may not accept an
    optional_depends_on kwarg yet in this repo -- if the dataclass rejects it,
    add the field to StageDef in pipeline_config.py as
    `optional_depends_on: list[str] = field(default_factory=list)` first (this
    is the one place outside gates.py/test_gates.py/routes/stages.py this task
    may touch, since resolve_upstream_by_stage's own `getattr(..., "optional_depends_on", [])`
    already defends against the field not existing -- but this test needs it to
    exist to exercise the include_optional=True branch meaningfully)."""
    stages = [
        StageDef(id="music", skill="music-brief", dir_prefix="03"),
        StageDef(id="voiceover", skill="voiceover-brief", dir_prefix="03"),
        StageDef(id="assembly", skill="shorts-assembly", dir_prefix="04",
                 depends_on=["voiceover"], optional_depends_on=["music"]),
    ]
    for d, s in (("03-music", "music-brief"), ("03-voiceover", "voiceover-brief")):
        artifacts.write_artifact(tmp_path / d, 1, {"stage": s, "status": "final"}, "b")
    assert list(gates.resolve_upstream_by_stage(tmp_path, stages, stages[2])) == ["voiceover"]
    assert list(gates.resolve_upstream_by_stage(
        tmp_path, stages, stages[2], include_optional=True
    )) == ["voiceover", "music"]


# --- T2B: three-state upstream resolution -- absent, resolved, excluded ------


def test_the_three_upstream_states_are_three_distinguishable_outcomes(tmp_path):
    """'No styleboard' and 'a styleboard nobody approved' must not share one
    representation -- that conflation is the defect class this whole
    programme is about, and here it would arrive inside the fix for A-32."""
    stages = [
        StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02"),
        StageDef(id="styleboard", skill="shorts-styleboard", dir_prefix="02b",
                 depends_on=["scripting"]),
        StageDef(id="visual", skill="visual-prompts", dir_prefix="03",
                 depends_on=["scripting", "styleboard"]),
    ]
    artifacts.write_artifact(tmp_path / "02-scripting", 1,
                             {"stage": "shorts-scripting", "status": "final"}, "s")
    artifacts.write_artifact(tmp_path / "02b-styleboard", 1,
                             {"stage": "shorts-styleboard", "status": "draft"}, "sb")
    resolved = gates.resolve_upstream_by_stage(
        tmp_path, stages, stages[2], repo_root=tmp_path, approved_only=True
    )

    # (2) resolved -- an ordinary lookup
    assert resolved.get("scripting") == tmp_path / "02-scripting" / "artifact.v1.md"
    # (1) absent -- there is no `music` dependency at all
    assert resolved.get("music") is None
    # (3) excluded -- present on disk, filtered out, and NOT silently None
    with pytest.raises(gates.UpstreamExcludedError) as excinfo:
        resolved.get("styleboard")
    assert "not approved" in str(excinfo.value)
    assert "artifact.v1.md" in str(excinfo.value)
    # ...and the three are distinguishable without catching anything
    assert resolved.state_of("scripting") == "resolved"
    assert resolved.state_of("music") == "absent"
    assert resolved.state_of("styleboard") == "excluded"
    # values() carries only what was actually read, so compute_depends_on
    # records provenance for the artifacts the gate really saw
    assert list(resolved.values()) == [tmp_path / "02-scripting" / "artifact.v1.md"]


def test_an_unapproved_styleboard_makes_gate_c_error_rather_than_use_the_sheets_own_lock(tmp_path):
    """Fail closed, exactly like the empty-WORLD-LOCK guard beside it. Falling
    back to the sheet's own world lock because the styleboard was filtered is
    A-30 wearing A-32's clothes: Gate C would record `pass` against a world the
    operator never approved."""
    styleboard = tmp_path / "02b-styleboard" / "artifact.v1.md"
    styleboard.parent.mkdir(parents=True)
    styleboard.write_text(
        (FIXTURES / "passing_styleboard.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    upstream = gates.UpstreamMap(
        {},
        excluded={"styleboard": gates.ExcludedUpstream(
            stage_id="styleboard", path=styleboard, reason="not approved"
        )},
    )
    result = gates.run_gates_for_stage(REPO_ROOT, "visual", FIXTURES / "passing_sheet.md",
                                       upstream)[0]
    assert result["status"] == "error"
    finding = result["findings"][0]
    assert finding["check"] == "C0"
    assert "styleboard" in finding["message"]
    assert "not approved" in finding["message"]
    assert "own world lock" in finding["message"]


# --- F-19: the CLI and the app must agree on Gate C -------------------------


def _cli_findings(sheet: Path, styleboard: Path | None, library: Path) -> set[tuple]:
    """Reproduce lint_prompt_sheet.main's own pipeline (not its printing), so the
    comparison is against the CLI's decisions rather than a paraphrase of them."""
    linter = gates._load_linter(REPO_ROOT, "lint_prompt_sheet")
    sheet_text = sheet.read_text(encoding="utf-8")
    parse = linter.parse_sheet(sheet_text)
    shots, sheet_world = parse.shots, parse.world
    if styleboard is not None:
        world = linter.parse_world_lock(styleboard.read_text(encoding="utf-8"))
        if sheet_world:
            parse.findings.append(linter.Finding(
                "PARSE", None,
                f"the sheet at {sheet.name} carries its own WORLD LOCK block, but a "
                f"styleboard was also supplied at {styleboard.name}; the sheet's "
                "block is being discarded -- remove it from the sheet if the styleboard "
                "is now authoritative, or drop --styleboard if the sheet's own block "
                "should still apply.",
                kind="parse",
            ))
    else:
        world = sheet_world
    cover = linter.parse_cover(sheet_text)
    lib = (
        linter.parse_style_library_checked(library.read_text(encoding="utf-8"))[0]
        if linter.sheet_declares_slots(shots, cover) else None
    )
    findings = [
        *parse.findings,
        *linter.check_cover_present(sheet_text),
        *linter.lint(shots, world, cover=cover, library=lib,
                     declared_shot_count=parse.declared_shot_count),
    ]
    return {(f.check, f.shot_index, f.message) for f in findings}


def _app_findings(sheet: Path, styleboard: Path | None) -> set[tuple]:
    upstream = {"styleboard": styleboard} if styleboard is not None else {}
    result = gates.run_gates_for_stage(REPO_ROOT, "visual", sheet, upstream)[0]
    return {(f["check"], f.get("shot_index"), f["message"]) for f in result["findings"]}


DIFFERENTIAL_CASES = [
    ("passing", FIXTURES / "passing_sheet.md", FIXTURES / "passing_styleboard.md"),
    ("failing", FIXTURES / "failing_sheet.md", FIXTURES / "passing_styleboard.md"),
    ("legacy",  FIXTURES / "legacy_do_less_sheet.md", None),
    ("worked",  FIXTURES / "worked_example_sheet.md", FIXTURES / "worked_example_styleboard.md"),
]


def _normalize_stray_world_lock_wording(findings: set[tuple]) -> set[tuple]:
    """P3-6's stray-WORLD-LOCK finding is, by design, worded differently on each
    side -- the CLI says '--styleboard' (a real flag it has); the app says 'the
    styleboard input' (it has no command line). That is the one documented,
    intentional wording split, so normalize just this finding's message before
    the byte-for-byte comparison below -- every other check id still compares
    exactly as it did before."""
    return {
        (check, shot_index, message.replace("the styleboard input", "--styleboard"))
        for check, shot_index, message in findings
    }


@pytest.mark.parametrize("label,sheet,styleboard", DIFFERENTIAL_CASES,
                         ids=[c[0] for c in DIFFERENTIAL_CASES])
def test_app_and_cli_gate_c_report_identical_findings(label, sheet, styleboard):
    """F-19: gates.py's docstring promises one gate, not a stricter CLI and a
    laxer app -- and nothing tested it. C-74, C-75 and A-31 are all divergences
    the two suites could not see because each tested its own side."""
    library = REPO_ROOT / "docs" / "style-library.md"
    app = _normalize_stray_world_lock_wording(_app_findings(sheet, styleboard))
    cli = _normalize_stray_world_lock_wording(_cli_findings(sheet, styleboard, library))
    assert app == cli


def test_the_only_gate_c_divergence_is_the_empty_world_lock_input_error(tmp_path):
    """The enumerated exception to the test above, and the ledger that bounds it.

    The app raises GateInputError on an unparseable styleboard WORLD LOCK; the
    CLI has no such guard and lints against world={} (A-31). The root fix moves
    the guard into lint_prompt_sheet -- P11's file, not this package's. When P11
    lands it, THIS TEST FAILS and the ledger entry must be deleted. It is a
    tripwire on a known gap, not a licence for it."""
    styleboard = tmp_path / "artifact.v1.md"
    styleboard.write_text("WORLD LOCK\n  not recoverable\n", encoding="utf-8")
    app = _app_findings(FIXTURES / "passing_sheet.md", styleboard)
    cli = _cli_findings(FIXTURES / "passing_sheet.md", styleboard,
                        REPO_ROOT / "docs" / "style-library.md")
    assert {c for c, _i, _m in app} == {"C0"}
    assert {c for c, _i, _m in cli} <= {"C8", "C18"}


# --- T7B: closing the four remaining CLI/app Gate C parity gaps --------------


def test_a_malformed_shot_heading_produces_the_same_parse_finding_on_both_sides(tmp_path):
    """P3-1 / C-70: a heading close enough to look intentional but missing its
    trailing camera-height field used to be silently skipped, dropping that
    shot from every check C1-C20 on the app side while the CLI recorded a
    blocking PARSE finding naming the line."""
    original = (FIXTURES / "passing_sheet.md").read_text(encoding="utf-8")
    corrupted = original.replace(
        "### Shot 2 — Setup (3–8s) · Register B · WORLD · XWIDE · EYE",
        "### Shot 2 — Setup (3–8s) · Register B · WORLD · XWIDE",
    )
    assert corrupted != original
    sheet = tmp_path / "sheet.md"
    sheet.write_text(corrupted, encoding="utf-8")
    styleboard = FIXTURES / "passing_styleboard.md"
    library = REPO_ROOT / "docs" / "style-library.md"

    app = _app_findings(sheet, styleboard)
    cli = _cli_findings(sheet, styleboard, library)
    assert app == cli
    assert any(
        check == "PARSE" and shot_index is None and "line 12" in message
        for check, shot_index, message in cli
    ), cli


def test_a_wrong_declared_shot_count_is_flagged_identically_on_both_sides(tmp_path):
    """P3-2 / C-71: `declared_shot_count` must reach `lint()` on both sides so
    `check_shot_count`'s C21 mismatch finding fires identically, not only on
    the CLI."""
    original = (FIXTURES / "passing_sheet.md").read_text(encoding="utf-8")
    mutated = original.replace(
        "PER-SHOT PROMPTS\n", "PER-SHOT PROMPTS\nSHOT COUNT: 6\n", 1
    )
    assert mutated != original
    sheet = tmp_path / "sheet.md"
    sheet.write_text(mutated, encoding="utf-8")
    styleboard = FIXTURES / "passing_styleboard.md"
    library = REPO_ROOT / "docs" / "style-library.md"

    app = _app_findings(sheet, styleboard)
    cli = _cli_findings(sheet, styleboard, library)
    assert app == cli
    assert any(
        check == "C21" and "declares 6 shot(s) but 5 parsed" in message
        for check, _shot_index, message in cli
    ), cli


def test_a_malformed_style_library_entry_makes_the_app_error_like_the_clis_early_exit(tmp_path):
    """P3-3 / C-76: a `### ` entry heading that fails the kebab-case shape used
    to be silently dropped by the unchecked `parse_style_library`, so a sheet
    binding that exact label failed C20 one stage later, naming the sheet for
    a defect that lives in the Library. `parse_style_library_checked` surfaces
    the malformed heading as a `library_findings` entry; the CLI exits
    EXIT_MISSING_DEPENDENCY on it (confirmed directly below), and the app must
    now raise/record the equivalent `status: "error"` naming the Library file,
    rather than deferring to a confusing C20 failure."""
    library_text = (REPO_ROOT / "docs" / "style-library.md").read_text(encoding="utf-8")
    corrupted_library = library_text.replace(
        "### rgs-present-soccer-a", "### RGS-present-soccer-a"
    )
    assert corrupted_library != library_text

    linter = gates._load_linter(REPO_ROOT, "lint_prompt_sheet")
    _library, library_findings = linter.parse_style_library_checked(corrupted_library)
    assert library_findings, "the mutation must actually break parse_style_library_checked"

    fake_repo = tmp_path / "repo"
    (fake_repo / "scripts").mkdir(parents=True)
    shutil.copy(
        REPO_ROOT / "scripts" / "lint_prompt_sheet.py",
        fake_repo / "scripts" / "lint_prompt_sheet.py",
    )
    (fake_repo / "docs").mkdir()
    (fake_repo / "docs" / "style-library.md").write_text(corrupted_library, encoding="utf-8")

    upstream = {"styleboard": FIXTURES / "passing_styleboard.md"}
    result = gates.run_gates_for_stage(
        fake_repo, "visual", FIXTURES / "passing_sheet.md", upstream
    )[0]
    assert result["status"] == "error"
    assert "style-library.md" in result["findings"][0]["message"]


def test_a_stray_sheet_world_lock_alongside_a_styleboard_is_flagged_identically(tmp_path):
    """P3-6: a legacy sheet that still carries its own WORLD LOCK block, now
    also fed a styleboard, has that block silently discarded unless both sides
    record the discard. Message wording differs only in "--styleboard" (CLI)
    vs. "the styleboard input" (app); assert on the shared substring, not full
    equality."""
    original = (FIXTURES / "passing_sheet.md").read_text(encoding="utf-8")
    stray_world = "WORLD LOCK\n  register_a_sport: club soccer\n\n"
    mutated = stray_world + original
    assert mutated != original
    sheet = tmp_path / "sheet.md"
    sheet.write_text(mutated, encoding="utf-8")
    styleboard = FIXTURES / "passing_styleboard.md"
    library = REPO_ROOT / "docs" / "style-library.md"

    app = _app_findings(sheet, styleboard)
    cli = _cli_findings(sheet, styleboard, library)

    for findings in (app, cli):
        stray = [
            (check, shot_index, message) for check, shot_index, message in findings
            if check == "PARSE" and shot_index is None and "own WORLD LOCK block" in message
        ]
        assert len(stray) == 1, findings


def test_a_styleboard_with_no_world_lock_fails_its_own_gate(tmp_path):
    """A-33: styleboard is the artifact C8/C18/C20 READ FROM, and it was the
    least validated artifact in the system. A malformed one surfaced one stage
    later as a wall of findings blaming the sheet."""
    path = tmp_path / "artifact.v1.md"
    path.write_text("=== STYLEBOARD ===\n\nBINDINGS\n  none\n", encoding="utf-8")
    result = gates.run_gates_for_stage(REPO_ROOT, "styleboard", path, {})[0]
    assert result["name"] == "gate_s_styleboard"
    assert result["status"] == "fail"
    assert "S1" in {f["check"] for f in result["findings"]}


def test_a_styleboard_missing_a_key_gate_c_reads_fails_its_own_gate(tmp_path):
    path = tmp_path / "artifact.v1.md"
    path.write_text(
        "WORLD LOCK\n  register_a_venue: a pitch\n  register_b_thinker: Plutarch\n",
        encoding="utf-8",
    )
    result = gates.run_gates_for_stage(REPO_ROOT, "styleboard", path, {})[0]
    s2 = [f for f in result["findings"] if f["check"] == "S2"]
    assert {"register_a_sport", "register_a_signature_objects"} <= {
        m for f in s2 for m in ("register_a_sport", "register_a_signature_objects")
        if m in f["message"]
    }


def test_the_passing_styleboard_fixture_passes_its_own_gate():
    result = gates.run_gates_for_stage(
        REPO_ROOT, "styleboard", FIXTURES / "passing_styleboard.md", {}
    )[0]
    assert result["status"] == "pass", result["findings"]


def _world_lock(**overrides) -> str:
    linter = gates._load_linter(REPO_ROOT, "lint_prompt_sheet")
    base = linter.parse_world_lock(
        (FIXTURES / "passing_styleboard.md").read_text(encoding="utf-8")
    )
    merged = {**base, **overrides}
    return "WORLD LOCK\n" + "".join(f"  {k}: {v}\n" for k, v in merged.items())


def test_a_styleboard_slot_value_shaped_like_an_invented_code_fails(tmp_path):
    path = tmp_path / "artifact.v1.md"
    path.write_text(_world_lock(slot_register_a="SREF-RGS-A-DL01"), encoding="utf-8")
    result = gates.run_gates_for_stage(REPO_ROOT, "styleboard", path, {})[0]
    assert "S3" in {f["check"] for f in result["findings"]}


def test_a_malformed_style_library_entry_errors_gate_s_naming_the_library(tmp_path):
    """I2: `_check_styleboard_slots` used the unchecked `parse_style_library`,
    reintroducing the exact defect T7B fixed for Gate C (P3-3/C-76) -- a
    `### ` entry heading that fails the kebab-case shape is silently dropped,
    so a styleboard slot bound to that exact label failed S4 as if the label
    were simply unknown, naming the styleboard for a defect that lives in the
    Library. `parse_style_library_checked` surfaces the malformed heading as a
    `library_findings` entry; Gate S must now raise/record `status: "error"`
    naming the Library file instead of a confusing S4."""
    library_text = (REPO_ROOT / "docs" / "style-library.md").read_text(encoding="utf-8")
    corrupted_library = library_text.replace(
        "### rgs-present-soccer-a", "### RGS-present-soccer-a"
    )
    assert corrupted_library != library_text

    linter = gates._load_linter(REPO_ROOT, "lint_prompt_sheet")
    _library, library_findings = linter.parse_style_library_checked(corrupted_library)
    assert library_findings, "the mutation must actually break parse_style_library_checked"

    fake_repo = tmp_path / "repo"
    (fake_repo / "scripts").mkdir(parents=True)
    shutil.copy(
        REPO_ROOT / "scripts" / "lint_prompt_sheet.py",
        fake_repo / "scripts" / "lint_prompt_sheet.py",
    )
    (fake_repo / "docs").mkdir()
    (fake_repo / "docs" / "style-library.md").write_text(corrupted_library, encoding="utf-8")

    path = tmp_path / "artifact.v1.md"
    path.write_text(_world_lock(slot_register_b="rgs-sourceera-painterly-c"), encoding="utf-8")
    result = gates.run_gates_for_stage(fake_repo, "styleboard", path, {})[0]
    assert result["status"] == "error"
    assert "style-library.md" in result["findings"][0]["message"]
    assert "S4" not in {f["check"] for f in result["findings"]}


def test_a_styleboard_label_naming_no_library_entry_fails_here_not_downstream(tmp_path):
    """A-33/A-34's real fix: C20 blamed the sheet for a label the STYLEBOARD
    chose, once per affected shot. Catch it where it was written."""
    path = tmp_path / "artifact.v1.md"
    path.write_text(_world_lock(slot_register_b="rgs-sourceera-painterly-c"), encoding="utf-8")
    result = gates.run_gates_for_stage(REPO_ROOT, "styleboard", path, {})[0]
    s4 = [f for f in result["findings"] if f["check"] == "S4"]
    assert len(s4) == 1, "one finding per bad label, not one per downstream shot"
    assert "docs/style-library.md" in s4[0]["message"]


# --- T14: _load_linter caches and cleans up after itself --------------------


def test_a_linter_is_loaded_once_per_repo_root_and_module():
    gates._LINTER_CACHE.clear()
    first = gates._load_linter(REPO_ROOT, "lint_prompt_sheet")
    second = gates._load_linter(REPO_ROOT, "lint_prompt_sheet")
    assert first is second


def test_a_failed_linter_exec_does_not_leave_a_broken_module_registered(tmp_path):
    """A-42: the module is inserted into sys.modules under its BARE name before
    exec_module runs and is never removed, so a failed exec left a
    half-initialized module registered globally until the next gate run."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "lint_broken.py").write_text("raise RuntimeError('bad module')\n", encoding="utf-8")
    sys.modules.pop("lint_broken", None)
    with pytest.raises(RuntimeError):
        gates._load_linter(tmp_path, "lint_broken")
    assert "lint_broken" not in sys.modules
    assert (tmp_path, "lint_broken") not in gates._LINTER_CACHE


# --- F-73: declare repo-root dependencies ------------------------------------


REPO_ROOT_DEPENDENCIES = (
    Path("tests") / "fixtures",          # the Gate C sheet/styleboard fixtures
    Path("docs") / "style-library.md",   # C20 and Gate S resolve labels against it
    Path("scripts") / "lint_prompt_sheet.py",
    Path("scripts") / "lint_script_language.py",
)


def test_the_app_suite_declares_the_repo_root_paths_it_reads():
    """F-73: this file resolves parents[2] and reads four paths OUTSIDE
    pipeline-app/, so the app suite is not independently relocatable and editing
    docs/style-library.md -- a documentation file nobody associates with the app
    suite -- breaks app tests. The coupling is real; make it declared and
    self-describing rather than latent, so a missing path fails with the reason
    instead of a confusing gate error."""
    missing = [str(p) for p in REPO_ROOT_DEPENDENCIES if not (REPO_ROOT / p).exists()]
    assert not missing, (
        "the pipeline-app suite reads these repo-root paths and cannot run without "
        f"them: {missing}. See F-73 -- this suite is not independently relocatable."
    )
