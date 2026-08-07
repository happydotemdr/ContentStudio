"""Deterministic gates the app runs on a stage's output after its turn.

A pipeline turn cannot shell out -- cli_runner denies Bash and PowerShell, and
that denial closes a real Windows cmd-shim quoting escape. So a skill's own
`python scripts/lint_*.py` instruction is unrunnable in app mode. Before this
module existed, visual-prompts' Gate C either failed every app run or recorded
a pass that never happened. The app runs the linters instead.

Linters live in scripts/ and are stdlib-only standalone tools with no package
identity, so they are loaded by file path rather than imported.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable

GateRunner = Callable[[Path, Path], list[dict]]


def _load_linter(repo_root: Path, module_name: str):
    path = repo_root / "scripts" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load linter at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _as_dicts(findings: list[Any]) -> list[dict]:
    return [asdict(f) if is_dataclass(f) else dict(f) for f in findings]


def run_script_language_gate(repo_root: Path, artifact_path: Path) -> list[dict]:
    linter = _load_linter(repo_root, "lint_script_language")
    text = artifact_path.read_text(encoding="utf-8")
    vo_lines, parse_findings = linter.parse_script(text)
    if not vo_lines:
        raise ValueError(
            f"no voiceover lines parsed from {artifact_path.name} -- check the script format"
        )
    return _as_dicts(linter.lint(vo_lines, text, parse_findings))


def run_prompt_sheet_gate(repo_root: Path, artifact_path: Path) -> list[dict]:
    linter = _load_linter(repo_root, "lint_prompt_sheet")
    shots, world = linter.parse_sheet(artifact_path.read_text(encoding="utf-8"))
    if not shots:
        raise ValueError(f"no shots parsed from {artifact_path.name} -- check the sheet format")
    return _as_dicts(linter.lint(shots, world))


GATE_REGISTRY: dict[str, list[tuple[str, GateRunner]]] = {
    "scripting": [("gate_d_script_language", run_script_language_gate)],
    "visual": [("gate_c_prompt_sheet", run_prompt_sheet_gate)],
}


def run_gates_for_stage(repo_root: Path, stage_id: str, artifact_path: Path) -> list[dict]:
    """Run every gate registered for this stage. Fail-closed: a linter that
    raises produces status "error", never a silent pass -- a gate whose result
    is unknown must block approval exactly as a failing one does.

    A "skipped" finding (e.g. a beat with no computable time range) is recorded
    but does not fail the gate: it is a known unknown, surfaced rather than
    swallowed.

    Every runner takes (repo_root, artifact_path). Do not add a signature
    fallback here -- catching TypeError to retry with fewer arguments would
    swallow a genuine TypeError raised inside a linter and report it as a
    signature mismatch."""
    results: list[dict] = []
    for name, runner in GATE_REGISTRY.get(stage_id, []):
        try:
            findings = runner(repo_root, artifact_path)
        except Exception as exc:  # noqa: BLE001 -- fail-closed is the whole point
            results.append({
                "name": name,
                "status": "error",
                "findings": [{"check": "GATE", "beat": None, "message": str(exc), "kind": "error"}],
            })
            continue
        blocking = [f for f in findings if f.get("kind") != "skipped"]
        results.append({
            "name": name,
            "status": "fail" if blocking else "pass",
            "findings": findings,
        })
    return results
