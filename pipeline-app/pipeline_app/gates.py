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
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable

# (repo_root, artifact_path, upstream) -> findings. `upstream` maps an upstream
# stage id to its latest artifact, because a gate is not always a function of
# the artifact alone: Gate C's world lock lives in the styleboard, one stage up.
GateRunner = Callable[[Path, Path, Mapping[str, Path]], list[dict]]


def _load_linter(repo_root: Path, module_name: str):
    path = repo_root / "scripts" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load linter at {path}")
    module = importlib.util.module_from_spec(spec)
    # Load-bearing, not cleanup-eligible: on Python 3.14, `@dataclass` resolves
    # its fields' string annotations by looking the defining module up in
    # sys.modules by name. A module loaded by file path (as these
    # standalone-tool linters are, having no package identity) is not in
    # sys.modules unless this line puts it there -- omit it and the linter's
    # own `@dataclass` definitions raise AttributeError before a single check
    # runs.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _as_dicts(findings: list[Any]) -> list[dict]:
    return [asdict(f) if is_dataclass(f) else dict(f) for f in findings]


def run_script_language_gate(
    repo_root: Path, artifact_path: Path, upstream: Mapping[str, Path]
) -> list[dict]:
    linter = _load_linter(repo_root, "lint_script_language")
    text = artifact_path.read_text(encoding="utf-8")
    vo_lines, parse_findings = linter.parse_script(text)
    if not vo_lines:
        raise ValueError(
            f"no voiceover lines parsed from {artifact_path.name} -- check the script format"
        )
    return _as_dicts(linter.lint(vo_lines, text, parse_findings))


def run_prompt_sheet_gate(
    repo_root: Path, artifact_path: Path, upstream: Mapping[str, Path]
) -> list[dict]:
    """Gate C, in the same shape the CLI runs it.

    This must stay equivalent to `lint_prompt_sheet.main`: same world-lock
    source, same cover checks. Two gates wearing one name -- a stricter CLI and
    a laxer app -- is worse than having no app gate at all, because the recorded
    `gates` block would understate what the sheet was actually held to.
    """
    linter = _load_linter(repo_root, "lint_prompt_sheet")
    sheet_text = artifact_path.read_text(encoding="utf-8")
    shots, sheet_world = linter.parse_sheet(sheet_text)
    if not shots:
        raise ValueError(f"no shots parsed from {artifact_path.name} -- check the sheet format")

    # visual-prompts inherits the world lock from the styleboard and is told not
    # to re-emit it, so the sheet's own block is the legacy path, not the
    # primary one.
    styleboard_path = upstream.get("styleboard")
    if styleboard_path is None:
        world = sheet_world
    else:
        world = linter.parse_world_lock(styleboard_path.read_text(encoding="utf-8"))
        if not world:
            # backfill_styleboard_rows writes an honest "not recoverable"
            # styleboard for a project that finished `visual` before the stage
            # existed. Linting against an empty world would emit a wall of
            # C8/C18 findings naming the wrong problem. Fail closed instead, and
            # say which artifact is empty.
            raise ValueError(
                f"styleboard {styleboard_path.name} has no parseable WORLD LOCK block -- "
                f"Gate C cannot check {artifact_path.name} against an empty world"
            )

    cover = linter.parse_cover(sheet_text)
    findings = [
        *linter.check_cover_present(sheet_text),
        *linter.lint(shots, world, cover=cover),
    ]
    return _as_dicts(findings)


GATE_REGISTRY: dict[str, list[tuple[str, GateRunner]]] = {
    "scripting": [("gate_d_script_language", run_script_language_gate)],
    "visual": [("gate_c_prompt_sheet", run_prompt_sheet_gate)],
}


def run_gates_for_stage(
    repo_root: Path,
    stage_id: str,
    artifact_path: Path,
    upstream: Mapping[str, Path] | None = None,
) -> list[dict]:
    """Run every gate registered for this stage. Fail-closed: a linter that
    raises produces status "error", never a silent pass -- a gate whose result
    is unknown must block approval exactly as a failing one does.

    A "skipped" finding (e.g. a beat with no computable time range) is recorded
    but does not fail the gate: it is a known unknown, surfaced rather than
    swallowed.

    `upstream` maps an upstream stage id to its latest artifact path; omitting
    it means "no upstream available", which each runner handles explicitly.

    Every runner takes (repo_root, artifact_path, upstream). Do not add a
    signature fallback here -- catching TypeError to retry with fewer arguments
    would swallow a genuine TypeError raised inside a linter and report it as a
    signature mismatch."""
    upstream = upstream or {}
    results: list[dict] = []
    for name, runner in GATE_REGISTRY.get(stage_id, []):
        try:
            findings = runner(repo_root, artifact_path, upstream)
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
