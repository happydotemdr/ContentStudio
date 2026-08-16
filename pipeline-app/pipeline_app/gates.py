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

import asyncio
import importlib.util
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Callable

from pipeline_app import artifacts, obs
from pipeline_app.pipeline_config import StageDef, stage_dir_name

# Re-raised, never recorded: these are the process or the caller saying stop, and
# converting them into a recorded gate result would swallow a real cancellation.
_CANCELLATION = (KeyboardInterrupt, asyncio.CancelledError, GeneratorExit)

# (repo_root, artifact_path, upstream) -> findings. `upstream` maps an upstream
# stage id to its latest artifact, because a gate is not always a function of
# the artifact alone: Gate C's world lock lives in the styleboard, one stage up.
GateRunner = Callable[[Path, Path, Mapping[str, Path]], list[dict]]


class GateInputError(ValueError):
    """A gate's INPUT is unusable (empty world lock, missing Library), as
    opposed to the artifact under test being wrong. Recorded with check "C0"
    so the operator can tell 'your styleboard is broken' from 'your sheet is'."""

    check = "C0"


@dataclass(frozen=True)
class ExcludedUpstream:
    """An upstream artifact that EXISTS but was filtered out of the map."""
    stage_id: str
    path: Path
    reason: str          # e.g. "not approved"


class UpstreamExcludedError(GateInputError):
    """Raised on any lookup of an excluded upstream. A GateInputError, so
    run_gates_for_stage records it with check "C0" and status "error" -- the
    gate's INPUT is unusable, which is a different fact from the artifact under
    test being wrong."""

    def __init__(self, excluded: ExcludedUpstream):
        self.excluded = excluded
        super().__init__(
            f"{excluded.stage_id} {excluded.path.name} exists but is {excluded.reason} -- "
            f"the gate will not fall back to the sheet's own world lock. Approve "
            f"{excluded.stage_id}, or regenerate it."
        )


class UpstreamMap(dict):
    """`dict[str, Path]` with a third state.

    Absent means NO ARTIFACT EXISTS. Present means resolved. A stage whose
    artifact exists but was filtered out (unapproved, under approved_only=True)
    is neither: it is `excluded`, and every lookup of it RAISES.

    Lookups raise on purpose. The alternative -- returning None and trusting
    each runner to check a companion mapping first -- is precisely the shape
    that made `upstream.get("styleboard") is None` take the laxer legacy branch
    for a styleboard nobody approved. A runner cannot forget a check that is
    enforced by the read itself. Iteration, values() and items() see only
    resolved entries, so `list(map.values())` remains the ordered path list
    compute_depends_on expects.
    """

    def __init__(self, resolved=None, *, excluded=None):
        super().__init__(resolved or {})
        self.excluded: dict[str, ExcludedUpstream] = dict(excluded or {})

    def _guard(self, key):
        found = self.excluded.get(key)
        if found is not None:
            raise UpstreamExcludedError(found)

    def get(self, key, default=None):
        self._guard(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self._guard(key)
        return super().__getitem__(key)

    def __contains__(self, key):
        self._guard(key)
        return super().__contains__(key)

    def state_of(self, key: str) -> str:
        """'resolved' | 'excluded' | 'absent' -- the three states, nameable
        without catching an exception."""
        if key in self.excluded:
            return "excluded"
        return "resolved" if super().__contains__(key) else "absent"


_LINTER_CACHE: dict[tuple[Path, str], Any] = {}


def _load_linter(repo_root: Path, module_name: str):
    key = (repo_root, module_name)
    cached = _LINTER_CACHE.get(key)
    if cached is not None:
        return cached
    path = repo_root / "scripts" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load linter at {path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(module_name)
    # Load-bearing, not cleanup-eligible: on Python 3.14, `@dataclass` resolves
    # its fields' string annotations by looking the defining module up in
    # sys.modules by name. A module loaded by file path (as these
    # standalone-tool linters are, having no package identity) is not in
    # sys.modules unless this line puts it there -- omit it and the linter's
    # own `@dataclass` definitions raise AttributeError before a single check
    # runs.
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        # A-42: a failed exec used to leave a half-initialized module registered
        # under a global bare name until the next gate run replaced it.
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
    _LINTER_CACHE[key] = module
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
        detail = "; ".join(f"[{f.check}] {f.beat or 'script'}: {f.message}" for f in parse_findings)
        message = f"no voiceover lines parsed from {artifact_path.name} -- check the script format"
        if detail:
            message = f"{message}: {detail}"
        raise ValueError(message)
    return _as_dicts(linter.lint(vo_lines, text, parse_findings))


def run_prompt_sheet_gate(
    repo_root: Path, artifact_path: Path, upstream: Mapping[str, Path]
) -> list[dict]:
    """Gate C, in the same shape the CLI runs it.

    This must stay equivalent to `lint_prompt_sheet.main`: same world-lock
    source, same cover checks. Two gates wearing one name -- a stricter CLI and
    a laxer app -- is worse than having no app gate at all, because the recorded
    `gates` block would understate what the sheet was actually held to.

    `upstream.get("styleboard")` below deliberately has no explicit excluded-
    upstream guard: `UpstreamMap.get` already raises `UpstreamExcludedError` for
    a styleboard that exists but was filtered out (unapproved), and that error
    is a `GateInputError` that `run_gates_for_stage` records as `status:
    "error"`, check "C0" -- the same fail-closed path as the empty-WORLD-LOCK
    branch just below. No added branch is a decision, not an omission.
    """
    linter = _load_linter(repo_root, "lint_prompt_sheet")
    sheet_text = artifact_path.read_text(encoding="utf-8")
    parse = linter.parse_sheet(sheet_text)
    shots, sheet_world = parse.shots, parse.world
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
            raise GateInputError(
                f"styleboard {styleboard_path.name} has no parseable WORLD LOCK block -- "
                f"Gate C cannot check {artifact_path.name} against an empty world. "
                f"`python scripts/lint_prompt_sheet.py {artifact_path.name} "
                f"--styleboard {styleboard_path.name}` reports the same defect as a "
                f"per-shot C8/C18 wall naming the sheet; the defect is in the styleboard."
            )
        if sheet_world:
            # A legacy sheet that still carries its own WORLD LOCK block, mirrored
            # from lint_prompt_sheet.main -- the sheet's block is discarded in
            # favor of the styleboard's, and that discard is recorded rather than
            # silent (finding P3-6).
            parse.findings.append(linter.Finding(
                "PARSE", None,
                f"the sheet at {artifact_path.name} carries its own WORLD LOCK block, but a "
                f"styleboard was also supplied at {styleboard_path.name}; the sheet's "
                "block is being discarded -- remove it from the sheet if the styleboard "
                "is now authoritative, or drop the styleboard input if the sheet's own "
                "block should still apply.",
                kind="parse",
            ))

    cover = linter.parse_cover(sheet_text)

    # C20 resolves each slot label against the Style Library. Read it only when the
    # sheet has slots -- a PLATE-only sheet never consults it, and failing such a run
    # for a missing file would be the gate reporting the wrong problem.
    library = None
    if linter.sheet_declares_slots(shots, cover):
        library_path = repo_root / "docs" / "style-library.md"
        if not library_path.is_file():
            raise GateInputError(
                f"Style Library not found at {library_path} -- Gate C cannot resolve "
                f"{artifact_path.name}'s slot labels"
            )
        library, library_findings = linter.parse_style_library_checked(
            library_path.read_text(encoding="utf-8")
        )
        if library_findings:
            # Mirrors main()'s early EXIT_MISSING_DEPENDENCY: a Library with a
            # malformed entry heading looks complete but silently drops that
            # entry, so a sheet binding it fails C20 one stage later naming the
            # wrong problem (finding P3-3). Fail closed here instead, naming the
            # Library file and what was wrong with it.
            detail = "; ".join(f"[{f.check}] {f.message}" for f in library_findings)
            raise GateInputError(
                f"Style Library at {library_path} could not be fully parsed: {detail}"
            )
        if not library:
            # Same reasoning as the empty-styleboard branch above: linting against an
            # empty Library would report every slot as unknown, naming the wrong
            # problem. Fail closed and say which file is empty.
            raise GateInputError(
                f"no entries parsed from {library_path} -- Gate C cannot check "
                f"{artifact_path.name}'s slot labels against an empty Library"
            )

    findings = [
        *parse.findings,
        *linter.check_cover_present(sheet_text),
        *linter.lint(shots, world, cover=cover, library=library,
                     declared_shot_count=parse.declared_shot_count),
    ]
    return _as_dicts(findings)


# The world-lock keys Gate C actually reads, each traced to the function that
# reads it, so this list cannot drift from the gate it exists to feed:
#   register_a_sport             -> lint_prompt_sheet.check_world_lock (C8)
#   register_a_signature_objects -> lint_prompt_sheet.signature_objects (C8)
#   register_a_venue             -> named by C9's banned-generic-venue message
#   register_b_thinker           -> the Register B world the sheet is held to
REQUIRED_WORLD_KEYS = (
    "register_a_sport",
    "register_a_venue",
    "register_a_signature_objects",
    "register_b_thinker",
)


def _check_styleboard_slots(repo_root, linter, artifact_path: Path, world: dict) -> list[dict]:
    slots = {k: v.strip() for k, v in world.items() if k.startswith("slot_") and v.strip()}
    findings: list[dict] = []
    malformed = set()
    for key, value in sorted(slots.items()):
        if not linter.VALID_SLOT_VALUE_RE.match(value):
            malformed.add(key)
            findings.append({
                "check": "S3", "beat": None, "shot_index": None, "kind": "fail",
                "message": (
                    f"{key!r} = {value!r} is not a Style Library label (lowercase "
                    "kebab-case). Raw Midjourney codes and invented placeholders belong "
                    "nowhere in a styleboard -- the code is resolved at render time."
                ),
            })
    resolvable = {k: v for k, v in slots.items() if k not in malformed}
    if not resolvable:
        return findings
    library_path = repo_root / "docs" / "style-library.md"
    if not library_path.is_file():
        raise GateInputError(
            f"Style Library not found at {library_path} -- Gate S cannot resolve "
            f"{artifact_path.name}'s slot labels"
        )
    library, library_findings = linter.parse_style_library_checked(
        library_path.read_text(encoding="utf-8")
    )
    if library_findings:
        # Mirrors run_prompt_sheet_gate's identical fix (T7B): a malformed
        # Library entry heading looks complete but silently drops that entry,
        # so parse_style_library (unchecked) would make Gate S blame the
        # styleboard's slot label with a confusing S4 instead of naming the
        # Library-side typo that's the real problem.
        detail = "; ".join(f"[{f.check}] {f.message}" for f in library_findings)
        raise GateInputError(
            f"Style Library at {library_path} could not be fully parsed: {detail}"
        )
    if not library:
        raise GateInputError(
            f"no entries parsed from {library_path} -- Gate S cannot check "
            f"{artifact_path.name}'s slot labels against an empty Library"
        )
    known = ", ".join(sorted(library))
    findings.extend({
        "check": "S4", "beat": None, "shot_index": None, "kind": "fail",
        "message": (
            f"{key!r} = {value!r} is not an entry in docs/style-library.md. Every shot "
            f"bound to this slot will fail Gate C's C20. Known entries: {known}."
        ),
    } for key, value in sorted(resolvable.items()) if value not in library)
    return findings


def run_styleboard_gate(
    repo_root: Path, artifact_path: Path, upstream: Mapping[str, Path]
) -> list[dict]:
    """Gate S: check the styleboard as the INPUT Gate C will later read from it.

    A-33: C8, C18 and C20 all resolve their world from this artifact, and until
    this gate existed nothing checked it. A mistyped slot label here failed the
    NEXT stage, once per affected shot, pointing the operator at a sheet they
    could not fix. This gate has no CLI twin -- there is exactly one
    implementation, so the equivalence promise in run_prompt_sheet_gate's
    docstring does not apply to it."""
    linter = _load_linter(repo_root, "lint_prompt_sheet")
    text = artifact_path.read_text(encoding="utf-8")
    world = linter.parse_world_lock(text)
    if not world:
        return [{
            "check": "S1", "beat": None, "shot_index": None, "kind": "fail",
            "message": (
                f"{artifact_path.name} has no parseable WORLD LOCK block. Gate C reads "
                "the world from this artifact, so an empty block blocks the visual stage "
                "with findings that name the wrong file."
            ),
        }]
    findings = [{
        "check": "S2", "beat": None, "shot_index": None, "kind": "fail",
        "message": f"WORLD LOCK is missing {key!r}, which Gate C reads.",
    } for key in REQUIRED_WORLD_KEYS if not world.get(key, "").strip()]
    findings.extend(_check_styleboard_slots(repo_root, linter, artifact_path, world))
    return findings


# P2's migrations.py backfill (out of this package's file ownership) writes
# synthetic styleboard artifacts with `gates: []`, on the strength of its own
# comment there: "styleboard registers no gates (gates.GATE_REGISTRY), so []
# is the registry-consistent value." Registering "styleboard" below makes
# that comment false -- classify_gates("styleboard", []) now synthesizes a
# never_ran (blocking) gate for every backfilled artifact, requiring an
# override to approve. This is a cross-package handoff to flag for P2, not
# something to silently patch around from gates.py, approval_service.py, or
# anywhere else in this package.
GATE_REGISTRY: dict[str, list[tuple[str, GateRunner]]] = {
    "scripting": [("gate_d_script_language", run_script_language_gate)],
    "visual": [("gate_c_prompt_sheet", run_prompt_sheet_gate)],
    "styleboard": [("gate_s_styleboard", run_styleboard_gate)],
}


# Mirrors scripts/lint_script_language.py's NON_BLOCKING_KINDS -- deliberately a
# SEPARATE definition, not a shared import, because run_gates_for_stage judges
# already-returned dict findings generically across every gate registered for a
# stage (Gate C, Gate D, Gate S), with no linter module handle in scope to read
# a per-linter NON_BLOCKING_KINDS from. If a future gate introduces a new
# non-blocking `kind`, BOTH this constant and the linter's own must be updated --
# that is exactly the drift this comment exists to call out, not paper over.
_NON_BLOCKING_KINDS = frozenset({"skipped", "info"})


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
        except _CANCELLATION:
            raise
        except BaseException as exc:  # noqa: BLE001 -- fail-closed is the whole point
            # Widened from Exception deliberately (A-40): SystemExit from a linter
            # calling sys.exit() outside its __main__ guard used to escape into
            # turn_service AFTER its own recovery block had closed, leaving the
            # turn and the stage wedged at `running`. Nothing new is silenced --
            # cancellation is re-raised above and every catch is reported below.
            obs.log("gate.failed_closed", level="error", gate=name, stage=stage_id,
                    artifact=str(artifact_path), error=f"{type(exc).__name__}: {exc}")
            results.append({
                "name": name,
                "status": "error",
                "findings": [{
                    "check": getattr(exc, "check", "GATE"), "beat": None, "shot_index": None,
                    "kind": "error", "message": f"{type(exc).__name__}: {exc}",
                }],
            })
            continue
        blocking = [f for f in findings if f.get("kind") not in _NON_BLOCKING_KINDS]
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
) -> UpstreamMap:
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
    package's own call site is unchanged by their addition. The return type is
    `UpstreamMap`, not a bare dict: a dependency that resolve_latest_artifact
    or approved-filtering rejects, but that HAS an artifact on disk, must not
    collapse into the same "absent" representation as a dependency with no
    artifact at all -- that conflation is what let a filtered-out upstream take
    the laxer no-upstream branch in a gate (A-32's own hazard).
    """
    resolved: dict[str, Path] = {}
    excluded: dict[str, ExcludedUpstream] = {}
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
        latest = artifacts.latest_artifact_path(stage_dir)
        if approved_only:
            path = _approved_artifact_path(repo_root, up.id, stage_dir)
        elif repo_root is not None:
            path = artifacts.resolve_latest_artifact(repo_root, up.id, stage_dir)
        else:
            path = artifacts.latest_artifact_path(stage_dir)
        if path is not None:
            resolved[dep_id] = path
        elif latest is not None:
            # State (3): it exists, we filtered it. Say so -- do not let it read
            # as state (1).
            excluded[dep_id] = ExcludedUpstream(dep_id, latest, "not approved")
    return UpstreamMap(resolved, excluded=excluded)
