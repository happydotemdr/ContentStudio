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

from pipeline_app import artifacts
from pipeline_app.pipeline_config import StageDef, stage_dir_name

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

    # C20 resolves each slot label against the Style Library. Read it only when the
    # sheet has slots -- a PLATE-only sheet never consults it, and failing such a run
    # for a missing file would be the gate reporting the wrong problem.
    library = None
    if linter.sheet_declares_slots(shots, cover):
        library_path = repo_root / "docs" / "style-library.md"
        if not library_path.is_file():
            raise ValueError(
                f"Style Library not found at {library_path} -- Gate C cannot resolve "
                f"{artifact_path.name}'s slot labels"
            )
        library = linter.parse_style_library(library_path.read_text(encoding="utf-8"))
        if not library:
            # Same reasoning as the empty-styleboard branch above: linting against an
            # empty Library would report every slot as unknown, naming the wrong
            # problem. Fail closed and say which file is empty.
            raise ValueError(
                f"no entries parsed from {library_path} -- Gate C cannot check "
                f"{artifact_path.name}'s slot labels against an empty Library"
            )

    findings = [
        *linter.check_cover_present(sheet_text),
        *linter.lint(shots, world, cover=cover, library=library),
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
    upstream: Mapping[str, Path],
) -> list[dict]:
    """Run every gate registered for this stage. Fail-closed: a linter that
    raises produces status "error", never a silent pass -- a gate whose result
    is unknown must block approval exactly as a failing one does.

    A "skipped" finding (e.g. a beat with no computable time range) is recorded
    but does not fail the gate: it is a known unknown, surfaced rather than
    swallowed.

    `upstream` maps an upstream stage id to its APPROVED-or-latest artifact path
    and is REQUIRED: it used to default to `{}`, and the one caller that took the
    default (the hand-edit route) silently ran a laxer Gate C under the same name
    (A-30/A-62). A caller with genuinely no upstream passes an explicit `{}` and
    says so at the call site.

    Every runner takes (repo_root, artifact_path, upstream). Do not add a
    signature fallback here -- catching TypeError to retry with fewer arguments
    would swallow a genuine TypeError raised inside a linter and report it as a
    signature mismatch."""
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


def _approved_artifact_path(repo_root: Path | None, stage_id: str, stage_dir: Path) -> Path | None:
    """The latest artifact version whose frontmatter status is "final" -- the
    approved_only=True half of resolve_upstream_by_stage (A-32). Walks
    versions newest-first over the raw directory listing (not
    resolve_latest_artifact, which resolves grounding through its
    pointer.yaml and has no notion of "final" at all) and returns the first
    whose frontmatter status is "final"; None if none is.
    """
    for _version, path in reversed(artifacts._versions_in(stage_dir)):
        meta, _body = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
        if meta.get("status") == "final":
            return path
    return None


def resolve_upstream_by_stage(
    run_dir: Path,
    all_stage_defs: list[StageDef],
    stage_def: StageDef,
    *,
    repo_root: Path | None = None,
    approved_only: bool = False,
    include_optional: bool = False,
) -> dict[str, Path]:
    """The `upstream` argument every GateRunner takes, resolved once.

    Keyed by stage id, not a list: a gate may need one SPECIFIC upstream (Gate C
    needs the styleboard's world lock, Gate S nothing at all), and positional
    recovery from a list breaks the moment an upstream has no artifact yet and
    drops out of it. Insertion order follows `stage_def.depends_on` (then
    `optional_depends_on`), so `list(...values())` is the ordered path list
    `artifacts.compute_depends_on` expects.

    Lives here rather than in artifacts.py because the mapping is defined by
    what a gate needs. Both artifact-write paths will eventually call it
    (routes.stages.edit_stage_output_route today; turn_service.run_stage_turn
    in a LATER, separate package -- do not touch turn_service.py). Having two
    of these is A-30/A-62.

    The three keywords exist because two call sites (this route, and a future
    one) need DIFFERENT resolution semantics -- they are not decorative:

      repo_root=       pointer-aware resolution for `grounding`, whose artifact
                       lives in rgs-briefs/ behind a pointer.yaml and which
                       latest_artifact_path cannot see at all.
      approved_only=   resolve the latest artifact whose frontmatter status is
                       "final" rather than merely the highest version, so a gate
                       cannot validate against a draft nobody approved (A-32).
      include_optional= also walk `optional_depends_on`; a future stage may
                       declare one, which supplies input but never gates
                       unlocking.

    Every default reproduces the pre-existing behaviour exactly, so this
    package's own call site is unchanged by their addition.
    """
    upstream: dict[str, Path] = {}
    by_id = {s.id: s for s in all_stage_defs}
    dep_ids = list(stage_def.depends_on)
    if include_optional:
        dep_ids += [d for d in getattr(stage_def, "optional_depends_on", []) or []
                    if d not in dep_ids]
    for dep_id in dep_ids:
        up = by_id.get(dep_id)
        if up is None:
            continue
        stage_dir = run_dir / stage_dir_name(up)
        if approved_only:
            path = _approved_artifact_path(repo_root, up.id, stage_dir)
        elif repo_root is not None:
            path = artifacts.resolve_latest_artifact(repo_root, up.id, stage_dir)
        else:
            path = artifacts.latest_artifact_path(stage_dir)
        if path is not None:
            upstream[dep_id] = path
    return upstream
