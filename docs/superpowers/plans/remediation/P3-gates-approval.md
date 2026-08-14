# P3 — Gates & Approval

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` or
> `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. The orchestration plan's
> **Global Constraints**, **test standard** and **Frozen interfaces**
> ([`../2026-08-08-audit-remediation.md`](../2026-08-08-audit-remediation.md)) are binding and are
> not restated here.

**One-line goal:** make the two artifact-write paths run *the same* gates against *the same*
inputs, make an unknown gate result impossible to approve through, and make an ungated
styleboard impossible to hand to Gate C.

---

## 1. Scope

### Files this package owns (no other package may touch these)

```
pipeline-app/pipeline_app/routes/stages.py
pipeline-app/pipeline_app/gates.py
pipeline-app/pipeline_app/approval_service.py
pipeline-app/pipeline_app/state_machine.py
pipeline-app/pipeline_app/preflight.py
pipeline-app/tests/test_gates.py
pipeline-app/tests/test_routes_approve_edit.py
pipeline-app/tests/test_routes_stages.py
pipeline-app/tests/test_approval_service.py
pipeline-app/tests/test_state_machine.py
pipeline-app/tests/test_preflight.py
```

Nothing else. In particular this package **does not** edit `turn_service.py` (P4),
`artifacts.py` / `migrations.py` (P2), `scripts/lint_prompt_sheet.py` (P11),
`templates/**` or `browse_service.py` (P15), or `pytest.ini` (P0).

### Finding IDs (22)

`A-30`, `A-31`, `A-33`, `A-35`, `A-36`, `A-39`, `A-40`, `A-41`, `A-42`, `A-45`, `A-60`,
`A-62`, `A-64`, `A-77`, `A-84`, `E-04`, `E-05`, `E-07`, `F-17`, `F-19`, `F-28`, `F-73`

### Cross-package interfaces this package consumes

| Interface | Owner | How P3 uses it |
|---|---|---|
| `obs.log(event, *, level, **fields)` | P1 | Every fail-closed branch in `gates.py` (no `conn` there) |
| `obs.record_event(conn, *, kind, severity, source, message, detail, run_id)` | P1 | `approval_service`, `preflight`, `routes/stages.py` |
| `artifacts.compute_depends_on(run_dir, upstream_paths) -> list[dict]` | **P2** §6.1 | Task 3 — the edit route's `depends_on` |
| `artifacts.reserve_version` / `write_reserved_artifact` / `release_version` | **P2** §6.2 | Task 4 — exclusive version allocation; `next_version_number` is advisory only |
| `artifacts.parse_frontmatter` raises `MalformedArtifactError` | **P2** §6.2 | Task 23 — handlers at all three P3 call sites |
| `artifacts.record_gate_override(path, reason, *, at, actor=None)` | **P2** §6.2 | Task 23 — `at` is required |
| `artifacts.read_gate_overrides(path) -> list[dict]` | **P2** §6.2/§6.4 | Task 23 — the `gate_override` / `gate_overrides` context keys |
| `grounding_service.write_pointer(stage_dir, relpath, repo_root)` | **P2** §6.2 | Task 24 — `repo_root` is required |
| `grounding_service.classify_brief_change` (replaces `identify_new_brief`) | **P2** §6.2 | Task 24 |
| `grounding_service.verify_pointer(stage_dir, repo_root) -> PointerStatus` | **P2** §6.2 | Task 24 — inject the pointer only on `state == "ok"` |
| `lint_prompt_sheet.parse_world_lock` / `parse_style_library` / `VALID_SLOT_VALUE_RE` | P11 (read-only) | Task 8/9 — the styleboard gate loads them via `_load_linter` |

> **Assumption A1 — RESOLVED against P2's frozen §6 (was: two invented function names).**
> An earlier draft of this plan called `artifacts.resolve_upstream_by_stage` and
> `artifacts.depends_on_records`. **Neither exists.** P2 provides `compute_depends_on(run_dir,
> upstream_paths)` — a *list of paths* in, `[{path, sha256}]` out — and provides no
> stage-id-keyed mapping at all. The two are different objects and both are needed:
>
> - `run_gates_for_stage` needs `dict[stage_id, Path]` (Gate C looks up `"styleboard"` by name);
> - `compute_depends_on` needs `Iterable[Path]`.
>
> **Resolution, requiring nothing new from P2:** the stage-id-keyed mapping is a *gate* concept —
> `gates.GateRunner`'s own type comment is what defines it — so it is defined **in `gates.py`,
> this package's file**, as `gates.resolve_upstream_by_stage(run_dir, all_stage_defs, stage_def)`
> (Task 2). The edit route then calls
> `artifacts.compute_depends_on(run_dir, list(upstream_by_stage.values()))` (Task 3). One
> implementation of each, both owned by a package that has the file.

> **Handoff H1 (to P11, documentation only).** A-31's root fix — moving the empty-world
> fail-closed check *into* `lint_prompt_sheet` so both callers inherit it — lives in P11's file.
> P3 closes the app half and installs a bounded divergence ledger (Task 6/7) that fails the moment
> the divergence set changes in either direction, so P11's landing is detected, not assumed.

> **Handoff H1b (from P11, now landed — two things to check before trusting T6/T7 as written).**
> P11 shipped (PR #29) with two changes discovered *after* this plan's own text was written, so
> neither is reflected in T6/T7's shown code above:
>
> 1. **A fifth CLI/app divergence, `P3-6` in P11's own plan §6.2**, beyond the four this plan's
>    §"Cross-package interfaces" already lists: the CLI's `main()` now emits a blocking `PARSE`
>    finding when a sheet carries its own stray `WORLD LOCK` block *and* `--styleboard` is also
>    supplied — previously (and still, in `gates.py` today) that block is silently discarded with
>    no signal on the app side. `_cli_findings` (T7, above) will NOT reproduce this on its own:
>    it manually re-derives `lint_prompt_sheet.main`'s pipeline rather than calling `main()`
>    itself, and none of `DIFFERENTIAL_CASES`' four fixtures happen to carry a stray sheet-side
>    world lock, so `test_the_only_gate_c_divergence_is_the_empty_world_lock_input_error`'s
>    "bounded to one" assumption is now stale without T7's own test yet knowing it. Before
>    executing T6/T7: either add a fifth `DIFFERENTIAL_CASES` fixture exercising a stray world
>    lock, or update `_cli_findings` to call `linter.main`'s logic (not just its pieces) so this
>    divergence is caught mechanically rather than needing to be separately remembered.
> 2. **A confirmed regression in this package's own `pipeline-app/tests/test_gates.py`**, caused
>    by an unrelated P11 change (C8 now requires 2 signature-object mentions per Register A shot,
>    down to 1 only for `CLOSE`/`MACRO` scale): `test_visual_gate_without_a_styleboard_uses_a_
>    legacy_sheets_own_world_lock` — which lints `legacy_do_less_sheet.md`, the same fixture
>    T7's `"legacy"` case above uses — now fails, because that fixture's `MID-WIDE` Hook shot
>    names only one of its three declared signature objects and the test's blanket
>    `assert "C8" not in checks` was written for an unrelated concern (that C8's *sport* half
>    doesn't fire without a styleboard) but also catches this new, unrelated finding. This was
>    P11's own S0 policy trade-off (filed as `T21R-01` in P11's plan, not resolved there — P11
>    does not own this fixture or test file). Resolve it as part of this package's own work, not
>    by assuming it was someone else's problem: either narrow that test's assertion to the C8
>    sub-check it actually cares about, or add a second signature-object mention to the fixture's
>    Hook shot body.

> **Pre-review amendment PR1 (found before any task was dispatched, this session).** P11's own
> plan (`P11-gate-c.md` §6.2, "What P3 must change for full parity") lists **six** requirements
> for `gates.py`, labelled `P3-1` through `P3-6`. Handoff H1b above (added the same session as
> this amendment) only carried `P3-6` forward into this plan's text. `P3-1`, `P3-2` and `P3-3`
> were verified empirically against the live `gates.py` and confirmed still missing:
>
> | # | Requirement | Confirmed still missing, empirically | Consequence if left unfixed |
> |---|---|---|---|
> | `P3-1` | Consume `parse_sheet(...).findings` | `gates.py` still does `shots, sheet_world = linter.parse_sheet(sheet_text)` — a 2-tuple unpack that discards `.findings` entirely | **The app-side Gate C still has the exact flagship fail-open defect P11's PR advertises as fixed** (a malformed shot heading is silently dropped from every check, C-70) — but only on the CLI path. The pipeline app never calls the CLI; it calls `run_prompt_sheet_gate` directly (see this file's own module docstring: "the app runs the linters instead"). Every real project turn is still exposed. |
> | `P3-2` | Pass `declared_shot_count` into `linter.lint(...)` | `gates.py` calls `linter.lint(shots, world, cover=cover, library=library)` with no `declared_shot_count` — confirmed `lint()`'s signature accepts it (default `None`, feeding `check_shot_count`) | C-71 (a sheet's declared shot count silently drifting from its actual shot count) is unchecked app-side. |
> | `P3-3` | Consume `parse_style_library_checked` and fail closed on its findings | `gates.py:111` still calls the unchecked `parse_style_library`, which `lint_prompt_sheet.py`'s own docstring for that function now calls "kept for `pipeline_app.gates.py`'s existing call site" — a compatibility shim, not silent approval to skip the checked variant | C-76 (a malformed Library entry heading silently dropped, then every sheet binding that label fails at C20 blaming the sheet for a Library typo) is unchecked app-side. |
> | `P3-4` | Keep the Library path hard-coded, no override | **Already compliant** — `gates.py:105`'s `library_path = repo_root / "docs" / "style-library.md"` has no override parameter. Nothing to do. |
> | `P3-5` | Don't loosen the blocking-kind exemption set | **Already compliant** — `run_gates_for_stage`'s `blocking = [f for f in findings if f.get("kind") != "skipped"]` already treats `"parse"` (and everything else but `"skipped"`) as blocking, once `P3-1` actually feeds parse findings into the list. |
> | `P3-6` | Flag a stray sheet-carried `WORLD LOCK` block when a styleboard is also supplied | Confirmed missing — `run_prompt_sheet_gate` silently discards `sheet_world` the moment `styleboard_path is not None`, with no equivalent to the CLI's new blocking `PARSE` finding (added in P11's own final-review fix wave, commit `75df69e`) | Already covered by Handoff H1b above; folded into the same fix below rather than handled separately. |
>
> None of `P3-1`/`P3-2`/`P3-3`/`P3-6` is in this plan's own 22-finding list (§2) — they carry no
> `A-*`/`E-*`/`F-*` ID, the same "adopt a frozen/updated neighbour-package interface, close no new
> finding" shape as T23/T24. But `P3-1` is not cosmetic: it is a live S0-class silent-failure gap
> in the exact file this package exists to fix, and T1/T2/T6/T7's whole point is that "the app and
> the CLI are one gate, not a stricter CLI and a laxer app" (`run_prompt_sheet_gate`'s own
> docstring). Leaving it unfixed while landing T1/T2/T6/T7 would make this package's own parity
> claim false on day one. **Resolution:** folded into T7, which already anticipated finding and
> fixing "any real divergence... on the app side" — see T7's amended text below, which absorbs
> all four items instead of only `P3-6`.

> **Handoff H2 (to P4) — REVISED after P4's counter-contract; P4 was right.** An earlier draft
> asked P4 to adopt `gates.resolve_upstream_by_stage()` **verbatim** at
> `turn_service.py:138-143`. P4 read the body first and found that doing so would reintroduce
> **A-32** (the resolver used `latest_artifact_path`, so a gate could read an unapproved draft),
> **A-02** (it walked `depends_on` only, so P4's new `optional_depends_on: [music]` edge on
> `assembly` vanished) and **A-14** (grounding, whose artifact sits behind a `pointer.yaml`,
> resolved to `None`). Three findings P4 had just closed. "One implementation" was the right
> instinct applied without checking that the two call sites need *different resolution
> semantics*.
>
> **Resolution:** Task 2 widens the resolver with three keyword-only parameters —
> `repo_root=None`, `approved_only=False`, `include_optional=False` — matching P4 §7.1's
> signature exactly. **Every default reproduces today's behaviour, so no task in this plan
> changes.** P4 passes the non-default values, and hands P3 its `_approved_artifact_path` body
> to move into `gates.py` so there is still exactly one approved-artifact lookup, not two.
> P4's T5/T6/T10 are the acceptance criteria for the keywords.
>
> **What this fixes on P3's side too:** Task 1's static parity test can only see that both sites
> call the same function — it cannot see the two *maps' contents* drifting. P4's T17 adds a
> contents-level parity test that closes exactly that gap. Task 5's behavioural parity test
> remains P3's own cover.

> **Open decision D1 — `approved_only` on the hand-edit call site.** P4 §7.1 notes P3 "will
> probably want `approved_only=True` on its hand-edit call too — A-32 covers both writers." P3
> keeps the **default (`False`)** for now, deliberately:
>
> 1. **A-32 is not in P3's finding set.** Flipping it here would close someone else's finding
>    with no failing test of P3's observed first, against the programme's own rule.
> 2. **It would silently re-point every fixture in Tasks 3 and 5.** Those upstreams are written
>    as drafts; under `approved_only=True` they resolve to nothing.
> 3. **There is a real hazard in the flip that A-32's owner must design for.** An upstream that
>    exists but is *unapproved* resolves to an **absent key**, indistinguishable from "no
>    upstream at all" — and `run_prompt_sheet_gate` branches on `upstream.get("styleboard") is
>    None`, taking the laxer legacy-sheet path. That is A-30's failure mode returning through a
>    different door. Closing A-32 on either writer needs the resolver to distinguish *missing*
>    from *unapproved*, or the gate to fail closed on the latter.
>
> Routed to A-32's owner. The resolver supports the flip today; only the call-site argument and
> that third point are outstanding.

> **Assumption A2 (P2 breaking changes land first).** P2 §6.2 freezes four signature changes
> that break P3's files on contact: `record_gate_override`'s required `at=`, `parse_frontmatter`
> raising `MalformedArtifactError`, `write_pointer`'s required `repo_root`, and
> `identify_new_brief` → `classify_brief_change`. Tasks 23 and 24 adopt them. They close **no
> new finding** — they are the mechanical cost of P2's fixes landing in P3's files — and are
> sequenced last so the finding work is not blocked on P2's merge.

---

## 2. Finding → task map

| Finding | Severity | Failure mode | Task(s) |
|---|---|---|---|
| A-30 · hand-edit Gate C reads the wrong world lock | S1 | silent | **T1**, **T2** |
| A-31 · CLI and app disagree on an empty world lock | S3 | loud | **T6** |
| A-33 · `styleboard` is ungated | S2 | coverage-gap | **T8**, **T9** |
| A-35 · unrecognized gate `status` approves as a pass | S2 | silent | **T10** |
| A-36 · malformed `gates` value 500s instead of 409 | S3 | loud | **T11** |
| A-39 · whitespace-only override bypasses the block | S3 | silent | **T12** |
| A-40 · `BaseException` escapes fail-closed | S2 | latent | **T13** |
| A-41 · hand-edit gate call untried; 500 after clobber | S3 | loud | **T4** |
| A-42 · `_load_linter` re-executes and leaks `sys.modules` | S4 | latent | **T14** |
| A-45 · nothing re-locks a stage whose dep left `approved` | S2 | silent | **T15**, **T16** |
| A-60 · hand edit copies `depends_on`; empty and sticky | S1 | silent | **T3** |
| A-62 · hand-edit path runs Gate C with no upstream map | S1 | silent | **T2** |
| A-64 · `raw_output.md` written non-atomically before the artifact | S2 | silent | **T4** |
| A-77 · orphan recovery invisible; dead `raw_output.md` left | S2 | silent | **T17** |
| A-84 · the `/edit` path has no UI entry point | S3 | coverage-gap | **T20** |
| E-04 · every expected failure returns bare `PlainTextResponse` | S2 | loud | **T19** |
| E-05 · missing upstream artifact silently dropped from Input | S2 | silent | **T21** |
| E-07 · hand-edit route has no UI | S3 | latent | **T20** |
| F-17 · no test exercises `visual/edit` or `styleboard/edit` | S1 | coverage-gap | **T5** |
| F-19 · no test asserts CLI and app Gate C agree | S1 | coverage-gap | **T7** |
| F-28 · `preflight._unwedge_stage`'s three returns untested | S3 | silent | **T18** |
| F-73 · app suite reads repo-root files | S3 | latent | **T22** |

22 findings, 22 mapped. No finding is unowned.

**T23 and T24 close no finding.** They adopt P2's frozen `artifacts` / `grounding_service`
signatures (Assumption A2) inside P3's files. They are listed as tasks because they are real
TDD work with real tests, but they do not appear in this table and do not change the 22/22
count. Sequence them last, after P2 merges.

---

## 3. Tasks

Each task is one TDD cycle: **write the failing test → run it → read the failure → implement →
run again → commit.** Run the app suite from `pipeline-app/`:

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app" && python -m pytest -q
```

---

### T1 — The parity guard: every production gate call site must pass a real upstream map

*Closes the reintroduction path for A-30/A-62. This is the test that would have caught A-30.*

- [ ] **Write the failing test.** Append to `pipeline-app/tests/test_gates.py`:

```python
import ast

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
```

- [ ] **Run it.** `python -m pytest tests/test_gates.py::test_every_production_gate_call_site_passes_a_resolved_upstream_map -q`
      → fails: `routes/stages.py:266 omits \`upstream\``.
- [ ] **Do not implement yet.** T2 makes it pass. Commit the red test on its own branchless
      step is not possible under "commit after each task", so T1 and T2 share one commit —
      run T2 now and commit both.

---

### T2 — `upstream` becomes required; the edit route resolves and passes it

*Closes A-30, A-62.*

- [ ] **Write the failing test.** Append to `pipeline-app/tests/test_gates.py`:

```python
def test_run_gates_for_stage_refuses_to_be_called_without_an_upstream_map():
    """Fail-closed at the signature: the default `upstream=None` was what let the
    edit path silently run a different Gate C under the same name."""
    with pytest.raises(TypeError):
        gates.run_gates_for_stage(REPO_ROOT, "visual", FIXTURES / "passing_sheet.md")
```

- [ ] **Run it** → fails (no `TypeError`; the call returns results).
- [ ] **Implement, `gates.py`:**

```python
def run_gates_for_stage(
    repo_root: Path,
    stage_id: str,
    artifact_path: Path,
    upstream: Mapping[str, Path],
) -> list[dict]:
    """...
    `upstream` maps an upstream stage id to its APPROVED-or-latest artifact path
    and is REQUIRED: it used to default to `{}`, and the one caller that took the
    default (the hand-edit route) silently ran a laxer Gate C under the same name
    (A-30/A-62). A caller with genuinely no upstream passes an explicit `{}` and
    says so at the call site.
    """
```

  Delete the `upstream = upstream or {}` line.

- [ ] **Implement, `gates.py`** — the one resolver both write paths use (see Assumption A1;
      P2 does **not** provide this, and it is a gate concept, not an artifact one):

```python
from pipeline_app.pipeline_config import StageDef, stage_dir_name


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
    what a gate needs (see GateRunner above). Both artifact-write paths call it:
    routes.stages.edit_stage_output_route and turn_service.run_stage_turn.
    Having two of these is A-30/A-62.

    The three keywords exist because the two call sites need DIFFERENT
    resolution semantics, not because either is optional (P4 §7.1). Adopting
    the plain body at the turn path would have reintroduced three findings P4
    had just closed:

      repo_root=       pointer-aware resolution for `grounding`, whose artifact
                       lives in rgs-briefs/ behind a pointer.yaml and which
                       latest_artifact_path cannot see at all (A-14).
      approved_only=   resolve the latest artifact whose frontmatter status is
                       "final" rather than merely the highest version, so a gate
                       cannot validate against a draft nobody approved (A-32).
      include_optional= also walk `optional_depends_on`; `assembly` declares
                       `optional_depends_on: [music]`, which supplies input but
                       never gates unlocking, so stages_to_unlock is untouched
                       (A-02).

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
```

  > **Amendment (pre-review, this session): "lifted verbatim from P4's T6" is not executable
  > as written.** This session executes P3 alone, before P4 (per the landing order and this
  > session's own resume prompt); `turn_service.py` has no `_approved_artifact_path` today —
  > confirmed empirically, `grep` returns nothing. There is nothing to lift. **Write it fresh in
  > `gates.py`** (P3's own file) instead, to the semantic the resolver's docstring already
  > commits to — "resolve the latest artifact whose frontmatter status is `final`, not merely the
  > highest version":
  >
  > ```python
  > def _approved_artifact_path(repo_root: Path | None, stage_id: str, stage_dir: Path) -> Path | None:
  >     """The latest artifact version whose frontmatter status is "final" -- the
  >     approved_only=True half of resolve_upstream_by_stage (A-32). Walks
  >     versions newest-first over the *raw* directory listing (not
  >     resolve_latest_artifact, which resolves grounding through its
  >     pointer.yaml and has no notion of "final" at all) and returns the first
  >     whose frontmatter status is "final"; None if none is.
  >     """
  > ```
  >
  > Base it on `artifacts._versions_in(stage_dir)` (returns `list[tuple[int, Path]]`, already
  > sorted) and `artifacts.parse_frontmatter`, walking newest-first (`reversed(...)` or
  > `sorted(..., reverse=True)`) and returning the first path whose parsed `meta.get("status")
  > == "final"`. When P4 lands later, it decides for itself whether to import this from `gates.py`
  > or keep its own — that is P4's call to make with the code actually in front of it, not
  > something P3 can pre-resolve today. P4's T5/T6/T10 tests (when P4 runs) are the acceptance
  > criteria for the three keywords generally; the tests below cover P3's own defaults, plus a new
  > one asserting `approved_only=True` actually skips a non-final draft in favour of an older final
  > version (not just returning `{}` when nothing is final at all, which
  > `test_every_keyword_defaults_to_the_pre_widening_behaviour` already covers).

- [ ] **Implement, `routes/stages.py`** — replace line 266:

```python
    upstream_by_stage = gates.resolve_upstream_by_stage(run_dir, stage_defs, stage_def)
    gate_results = gates.run_gates_for_stage(
        repo_root, stage_id, gate_input_path, upstream_by_stage
    )
```

  (`gate_input_path` is still `raw_output_path` at this point; T4 changes it.)

- [ ] **Add the resolver's own test** to `test_gates.py`:

```python
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
    `depends_on` order must match turn_service's so the two paths produce
    byte-identical frontmatter."""
    ...  # both upstreams present -> list(resolved) == ["scripting", "styleboard"]


def test_every_keyword_defaults_to_the_pre_widening_behaviour(tmp_path):
    """P4 §7.1: the three keywords exist because the two call sites need
    different resolution semantics. Their DEFAULTS are what keep P3's own call
    site unchanged -- so the defaults are the contract, and a later change to
    one of them silently re-points every gate in the hand-edit path."""
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


def test_include_optional_is_off_by_default(tmp_path):
    """`assembly` declares optional_depends_on: [music] (P4's A-02). It supplies
    input but never gates unlocking, so it must not appear unless asked for."""
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
```

- [ ] **Update the seven 3-arg calls in `test_gates.py`** (lines 25, 33, 46, 65, 76, 87, 99 — the
      plan's own earlier count of "six" undercounts by one; verify by grep before editing rather
      than trusting either number) to pass an explicit `{}`, and `_visual_gate`'s default from
      `None` to `{}`.
- [ ] **Handoff H1b item 2 / the confirmed `test_gates.py` regression** — in the same commit,
      rename and fix `test_visual_gate_without_a_styleboard_uses_a_legacy_sheets_own_world_lock`
      per §5's table entry below. Verified this session: the fixture's Shot 1 (Hook, MID-WIDE
      scale — not exempted by P11's CLOSE/MACRO 1-object floor) names only 1 of its 3 declared
      `register_a_signature_objects` ("goal net, corner flag, soccer ball" — only "soccer ball"
      appears in the prompt body), so P11's object-count sub-check now correctly fires C8 on this
      fixture. That is real, unrelated to this test's actual concern (that C8's *sport*-naming
      sub-check does not fire when the sheet's own world lock is used). The blanket
      `assert "C8" not in checks` conflates the two. Narrow the assertion to the sport-naming
      sub-check specifically — assert no `C8` finding's `message` matches
      `"does not name the sport"` / `"declares no register_a_sport"` (the two message strings
      `check_world_lock` emits for that sub-check, confirmed against the live linter this
      session) — rather than asserting `C8` is absent altogether. Do **not** edit the fixture
      file; it is shared with T7's `"legacy"` differential case and other tests in this file that
      assert specific `C16` counts against it.
- [ ] **Run the app suite** → T1 and T2 green, and the previously-failing regression now passes
      for the right reason (confirm by temporarily reverting only the assertion narrowing and
      observing the original failure, then reapplying).
- [ ] **Commit:** `fix(gates): require an upstream map at every run_gates_for_stage call site`

---

### T2B — Three-state upstream resolution: absent, resolved, *excluded*

*Closes the hazard raised in Open decision D1.* Runs immediately after T2, before T4/T5.

> **Amendment (pre-review, this session): T2B has an undeclared forward dependency on T6 — run
> T6 before T2B.** Confirmed by `grep`: `UpstreamExcludedError(GateInputError)` below references
> a class that does not exist until T6 defines it (`class GateInputError(ValueError): ... check =
> "C0"`), and T2B's own `test_an_unapproved_styleboard_makes_gate_c_error_rather_than_use_the_sheets_own_lock`
> asserts `finding["check"] == "C0"`, which requires `run_gates_for_stage`'s exception handler to
> already read `getattr(exc, "check", "GATE")` instead of the hardcoded `"GATE"` string — also a
> T6 change. Executing T2B before T6 as textually ordered would leave the implementer stuck on a
> `NameError` for a class the plan hasn't introduced yet. T6 has no dependency on T2B, T3, T4 or
> T5 (it only touches `run_prompt_sheet_gate`'s two existing raise sites and
> `run_gates_for_stage`'s handler, both already in place after T1/T2) so reordering is safe in
> both directions. **Corrected execution order for the remainder of this package: T6, T2B, T3,
> T4, T5, T7, T7B, T8, T9, ..., T24** — i.e. pull T6 forward to run immediately after T2, before
> T2B, leaving every other task's relative order unchanged. Do not renumber the tasks themselves;
> only their dispatch order changes.

The audit's single most common defect class is "nothing found" and "something went wrong"
sharing one representation — Bluesky returned `[]` for both, the cron exited `0` for both, the
digest rendered the same email for both. `approved_only=True` would have added the gate
resolver to that list: an upstream that **exists but is unapproved** would resolve to an absent
key, `run_prompt_sheet_gate` would read `upstream.get("styleboard") is None`, and it would take
the laxer legacy branch and lint the sheet against **its own** world lock. That is A-30's
failure mode reintroduced *by* the fix for A-32.

Three states, three outcomes:

| State | Meaning | Representation |
|---|---|---|
| 1 | no artifact exists | key **absent** — legitimately "no upstream" (today's meaning, unchanged) |
| 2 | artifact exists and satisfies the filter | key **present**, mapped to its path |
| 3 | artifact exists but was **filtered out** | key **excluded** — any lookup raises; never looks like (1) |

- [ ] **Write the two failing tests** in `test_gates.py`:

```python
def test_the_three_upstream_states_are_three_distinguishable_outcomes(tmp_path):
    """D1's hazard. 'No styleboard' and 'a styleboard nobody approved' must not
    share one representation -- that conflation is the defect class this whole
    audit is about, and here it would arrive inside the fix for A-32."""
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
```

- [ ] **Run** → fails (`AttributeError: module 'gates' has no attribute 'UpstreamMap'`).
- [ ] **Implement, `gates.py`:**

```python
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
```

  `resolve_upstream_by_stage` returns `UpstreamMap(resolved, excluded=excluded)`, recording an
  `ExcludedUpstream` whenever a filter rejected a path that `latest_artifact_path` did find:

```python
        latest = artifacts.latest_artifact_path(stage_dir)
        path = ... # as in T2, subject to the filters
        if path is not None:
            resolved[dep_id] = path
        elif latest is not None:
            # State (3): it exists, we filtered it. Say so -- do not let it read
            # as state (1).
            excluded[dep_id] = ExcludedUpstream(dep_id, latest, "not approved")
```

  `run_prompt_sheet_gate` needs **no new branch**: its existing
  `styleboard_path = upstream.get("styleboard")` now raises for an excluded styleboard, and
  `run_gates_for_stage`'s fail-closed handler records it as `status: "error"`, `check: "C0"`.
  Add one line to its docstring saying so, so the absence of an explicit guard is legible as a
  decision rather than an omission.

- [ ] **Run** → green. **Commit:** `fix(gates): make a filtered-out upstream a third state, not an absent one`

---

### T3 — The edit route recomputes `depends_on` instead of copying it

*Closes A-60.*

- [ ] **Write three failing tests** (Three-Test Rule; A-60 is `silent`) in
      `pipeline-app/tests/test_routes_approve_edit.py`:

```python
def test_first_ever_hand_edit_records_a_real_depends_on(two_stage_client):
    """A-60 FAULT: with no prior artifact, prior_meta was {} and depends_on was
    written as []. is_stale([], ...) is False unconditionally, so the staleness
    cascade terminated at that node and every stage below stayed green on
    superseded input."""
    test_client, tmp_path, app = two_stage_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    ideation_dir = run_dir / "01-ideation"
    artifacts.write_artifact(ideation_dir, 1, {"stage": "shorts-ideation"}, "concept v1")
    _install_real_script_linter(tmp_path)
    assert test_client.post(f"/projects/{project_id}/stages/ideation/approve").status_code == 303

    resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/edit", data={"body": CLEAN_SCRIPT}
    )
    assert resp.status_code == 303
    meta, _ = artifacts.parse_frontmatter(
        (run_dir / "02-scripting" / "artifact.v1.md").read_text(encoding="utf-8")
    )
    assert meta["depends_on"] == [{
        "path": "01-ideation/artifact.v1.md",
        "sha256": artifacts.compute_sha256(ideation_dir / "artifact.v1.md"),
    }]


def test_a_hand_edited_stage_with_no_prior_artifact_still_goes_stale(two_stage_client):
    """A-60 DISTINGUISHABILITY: the empty list and a correct list are not merely
    different values -- they produce different cascade outcomes. A hand-edited
    stage must be indistinguishable from a turn-produced one at the cascade."""
    test_client, tmp_path, app = two_stage_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    _install_real_script_linter(tmp_path)
    artifacts.write_artifact(run_dir / "01-ideation", 1, {"stage": "shorts-ideation"}, "concept v1")
    test_client.post(f"/projects/{project_id}/stages/ideation/approve")
    test_client.post(f"/projects/{project_id}/stages/scripting/edit", data={"body": CLEAN_SCRIPT})
    test_client.post(f"/projects/{project_id}/stages/scripting/approve")

    test_client.post(f"/projects/{project_id}/stages/ideation/edit", data={"body": "concept v2"})

    assert db.get_stage(app.state.conn, project_id, "scripting")["status"] == "stale"


def test_a_hand_edit_after_the_upstream_advanced_records_the_current_version(two_stage_client):
    """A-60 SURFACING: the copied value named artifact.v1.md while v2 was current,
    so the artifact asserted a provenance it was never derived from. The recorded
    path is the human-reachable signal -- it must name the file actually read."""
    test_client, tmp_path, app = two_stage_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    _install_real_script_linter(tmp_path)
    ideation_dir = run_dir / "01-ideation"
    artifacts.write_artifact(ideation_dir, 1, {"stage": "shorts-ideation"}, "concept v1")
    test_client.post(f"/projects/{project_id}/stages/ideation/approve")
    test_client.post(f"/projects/{project_id}/stages/scripting/edit", data={"body": CLEAN_SCRIPT})
    artifacts.write_artifact(ideation_dir, 2, {"stage": "shorts-ideation"}, "concept v2")

    test_client.post(f"/projects/{project_id}/stages/scripting/edit", data={"body": CLEAN_SCRIPT})

    meta, _ = artifacts.parse_frontmatter(
        (run_dir / "02-scripting" / "artifact.v2.md").read_text(encoding="utf-8")
    )
    assert [d["path"] for d in meta["depends_on"]] == ["01-ideation/artifact.v2.md"]
```

  Add the shared helpers at the top of the file (real code, used by every later task):

```python
CLEAN_SCRIPT = (
    'HOOK (0–3s | 6 words): "Best part was the mud today."\n'
    "GATES\n  Gate E (fresh Opus critic): pass\n"
)


def _new_project(test_client, app, tmp_path: Path, slug="abc", brand="generic"):
    resp = test_client.post("/projects", data={"slug": slug, "brand": brand})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    return project_id, tmp_path / "runs" / project["run_id"]
```

- [ ] **Run** → all three fail (`depends_on == []`).
- [ ] **Implement, `routes/stages.py`** — delete the `latest` / `prior_meta` block at 248–251
      (this is P2 §6.1's "sticky node": copying the prior value forward means one `[]` is
      inherited forever and the whole cascade terminates at that stage) and set:

```python
    meta = {
        ...
        # P2 §6.1's frozen signature: a list of PATHS in, [{path, sha256}] out.
        # turn_service.run_stage_turn records the same shape from the same helper,
        # so the two write paths cannot produce different provenance (A-60).
        "depends_on": artifacts.compute_depends_on(run_dir, list(upstream_by_stage.values())),
        "gates": gate_results,
    }
```

- [ ] **Run** → green. **Commit:** `fix(stages): recompute depends_on on the hand-edit path`

---

### T4 — The edit route gates a private scratch file and mints from memory

*Closes A-41, A-64.*

- [ ] **Write the failing tests** in `test_routes_approve_edit.py`:

```python
def test_a_hand_edit_does_not_touch_the_turn_paths_raw_output(two_stage_client):
    """A-64 FAULT: the edit route truncated the SHARED raw_output.md before
    gating. A crash in that window left the new body in raw_output.md with no
    artifact version recording it, and poisoned the turn path's before_mtime
    baseline."""
    test_client, tmp_path, app = two_stage_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    _install_real_script_linter(tmp_path)
    artifacts.write_artifact(run_dir / "01-ideation", 1, {"stage": "shorts-ideation"}, "concept v1")
    test_client.post(f"/projects/{project_id}/stages/ideation/approve")
    scripting_dir = run_dir / "02-scripting"
    scripting_dir.mkdir(parents=True, exist_ok=True)
    (scripting_dir / "raw_output.md").write_text("previous turn output", encoding="utf-8")

    test_client.post(f"/projects/{project_id}/stages/scripting/edit", data={"body": CLEAN_SCRIPT})

    assert (scripting_dir / "raw_output.md").read_text(encoding="utf-8") == "previous turn output"


def test_a_failed_gate_run_leaves_no_scratch_file_behind(two_stage_client, monkeypatch):
    """A-41 DISTINGUISHABILITY: an escape from the gate must be observably
    different from a clean edit -- no half-written artifact, no orphan scratch,
    and a 409 rather than a 500."""
    test_client, tmp_path, app = two_stage_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    artifacts.write_artifact(run_dir / "01-ideation", 1, {"stage": "shorts-ideation"}, "concept v1")
    test_client.post(f"/projects/{project_id}/stages/ideation/approve")

    def boom(_repo_root, _stage_id, _path, _upstream):
        raise OSError("disk gone")

    monkeypatch.setattr("pipeline_app.routes.stages.gates.run_gates_for_stage", boom)
    resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/edit", data={"body": CLEAN_SCRIPT}
    )
    assert resp.status_code == 409
    assert "disk gone" in resp.text
    scripting_dir = run_dir / "02-scripting"
    assert not list(scripting_dir.glob(".edit_scratch*"))
    assert not list(scripting_dir.glob("artifact.v*.md"))


def test_an_edit_whose_gate_escapes_is_recorded_as_an_event(two_stage_client, monkeypatch):
    """A-41 SURFACING."""
    ...  # same setup; assert one events row with severity="error", kind="gate.escaped"
```

- [ ] **Run** → fails (raw_output clobbered; escape yields 500).
- [ ] **Implement, `routes/stages.py`**, replacing lines 263–280:

```python
    stage_dir.mkdir(parents=True, exist_ok=True)
    # The edit path gets its OWN scratch file, never the turn path's shared
    # raw_output.md (A-64): that file is turn_service's before_mtime baseline,
    # and truncating it here made a hand edit look like a turn's output. The
    # extension is deliberately not `.md` so browse_service's stage listing
    # (which shows every *.md except raw_output.md) never surfaces it.
    scratch = stage_dir / ".edit_scratch.tmp"
    try:
        scratch.write_text(body, encoding="utf-8")
        upstream_by_stage = gates.resolve_upstream_by_stage(run_dir, stage_defs, stage_def)
        gate_results = gates.run_gates_for_stage(repo_root, stage_id, scratch, upstream_by_stage)
    except Exception as exc:  # noqa: BLE001 -- an escaped gate is a conflict, not a 500
        obs.log("gate.escaped", level="error", stage=stage_id, project_id=project_id,
                error=str(exc))
        obs.record_event(
            conn, kind="gate.escaped", severity="error", source="routes.stages",
            message=f"hand edit of '{stage_id}' aborted: {exc}",
            detail={"project_id": project_id, "stage_id": stage_id},
        )
        return _stage_conflict(request, project_id, stage_id, str(exc))
    finally:
        scratch.unlink(missing_ok=True)

    # Version allocation is EXCLUSIVE and taken after the gate, not before it
    # (P2 §6.2 / A-65): next_version_number is advisory only now, and a
    # read-then-write spanning a full linter load and run is exactly the window
    # two concurrent edit POSTs collide in. Reserve, write, or release.
    reservation = artifacts.reserve_version(stage_dir)
    try:
        meta = {
            "schema_version": 1,
            "run_id": project["run_id"],
            "stage": stage_def.skill,
            "version": reservation.version,
            "status": "draft",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(
                timespec="seconds"
            ),
            "finalized_at": None,
            "supersedes": (
                f"artifact.v{reservation.version - 1}.md" if reservation.version > 1 else None
            ),
            "depends_on": artifacts.compute_depends_on(
                run_dir, list(upstream_by_stage.values())
            ),
            "gates": gate_results,
        }
        artifacts.write_reserved_artifact(reservation, meta, body)
    except BaseException:
        artifacts.release_version(reservation)
        raise
```

  Note the artifact body is the in-memory `body`, never a re-read of a shared scratch file.
  `_stage_conflict` arrives in T19; until then return `PlainTextResponse(str(exc), 409)` and
  T19 swaps it. The old `version = artifacts.next_version_number(stage_dir)` at line 253 is
  deleted — leaving the edit route on it would turn A-65 from a silent lost write into a 500.

- [ ] **Add the concurrency test** to `test_routes_approve_edit.py`:

```python
def test_two_overlapping_hand_edits_produce_two_versions_not_one(two_stage_client):
    """A-65's edit-path call site: reserve_version is exclusive, so the second
    writer gets v2, never a lost write over v1."""
    ...  # two sequential POSTs with a reserve_version spy asserting distinct versions
```

- [ ] **Run** → green. **Commit:** `fix(stages): gate hand edits on a private scratch file`

---

### T5 — `visual` / `styleboard` edit fixtures and the behavioural parity assertion

*Closes F-17. This is the behavioural half of the A-30 guard.*

- [ ] **Write the failing tests** in `test_routes_approve_edit.py`:

```python
def _install_gate_c_inputs(tmp_path: Path) -> None:
    """Gate C in app mode reads scripts/lint_prompt_sheet.py and
    docs/style-library.md relative to repo_root, so an isolated tmp_path repo
    needs both."""
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "scripts" / "lint_prompt_sheet.py",
                tmp_path / "scripts" / "lint_prompt_sheet.py")
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "docs" / "style-library.md", tmp_path / "docs" / "style-library.md")


@pytest.fixture
def visual_client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n"
        "    depends_on: []\n"
        "  - id: styleboard\n    skill: shorts-styleboard\n    dir_prefix: \"02b\"\n"
        "    depends_on: [scripting]\n"
        "  - id: visual\n    skill: visual-prompts\n    dir_prefix: \"03\"\n"
        "    depends_on: [scripting, styleboard]\n",
        encoding="utf-8",
    )
    _install_gate_c_inputs(tmp_path)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app, follow_redirects=False), tmp_path, app


def test_hand_editing_a_visual_sheet_is_gated_against_the_styleboards_world_lock(visual_client):
    """A-30/A-62 FAULT, F-17 coverage. The sheet body is byte-identical in both
    halves; only the styleboard's slot label differs. Before the fix the edit
    path resolved world={} and C20 returned NOTHING (world.get(key) empty ->
    `continue`), so a typo'd label passed the gate and failed at paste time."""
    test_client, tmp_path, app = visual_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    sheet_body = (FIXTURES / "passing_sheet.md").read_text(encoding="utf-8")
    styleboard_body = (FIXTURES / "passing_styleboard.md").read_text(encoding="utf-8").replace(
        "rgs-sourceera-painterly-b", "rgs-sourceera-painterly-c"
    )
    artifacts.write_artifact(run_dir / "02-scripting", 1, {"stage": "shorts-scripting"}, "script")
    artifacts.write_artifact(
        run_dir / "02b-styleboard", 1, {"stage": "shorts-styleboard"}, styleboard_body
    )

    resp = test_client.post(
        f"/projects/{project_id}/stages/visual/edit", data={"body": sheet_body}
    )
    assert resp.status_code == 303
    meta, _ = artifacts.parse_frontmatter(
        (run_dir / "03-visual" / "artifact.v1.md").read_text(encoding="utf-8")
    )
    assert meta["gates"][0]["status"] == "fail"
    c20 = [f for f in meta["gates"][0]["findings"] if f["check"] == "C20"]
    assert c20 and "rgs-sourceera-painterly-c" in c20[0]["message"]


def test_the_edit_path_and_a_direct_gate_run_produce_identical_results(visual_client):
    """THE PARITY TEST. The hand-edit route must record exactly what
    run_gates_for_stage produces when handed the resolved upstream map -- the
    same map turn_service builds. Any future divergence between the two write
    paths is a diff on this equality, not a subtle behavioural drift nobody
    notices."""
    test_client, tmp_path, app = visual_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    sheet_body = (FIXTURES / "passing_sheet.md").read_text(encoding="utf-8")
    styleboard_path = artifacts.write_artifact(
        run_dir / "02b-styleboard", 1, {"stage": "shorts-styleboard"},
        (FIXTURES / "passing_styleboard.md").read_text(encoding="utf-8"),
    )
    artifacts.write_artifact(run_dir / "02-scripting", 1, {"stage": "shorts-scripting"}, "script")

    test_client.post(f"/projects/{project_id}/stages/visual/edit", data={"body": sheet_body})
    recorded, _ = artifacts.parse_frontmatter(
        (run_dir / "03-visual" / "artifact.v1.md").read_text(encoding="utf-8")
    )

    reference_sheet = tmp_path / "reference_sheet.md"
    reference_sheet.write_text(sheet_body, encoding="utf-8")
    expected = gates.run_gates_for_stage(
        tmp_path, "visual", reference_sheet, {"styleboard": styleboard_path}
    )
    assert recorded["gates"] == expected


def test_hand_editing_a_styleboard_runs_the_styleboard_gate(visual_client):
    """F-17's second half: `styleboard` edits were as untested as `visual` ones,
    and after T9 the styleboard has a gate of its own to run."""
    ...  # asserts meta["gates"][0]["name"] == "gate_s_styleboard"
```

  (`FIXTURES = REPO_ROOT / "tests" / "fixtures"` at module top.)

- [ ] **Run** → the first two fail before T2/T3 land; after them they pass, and the third fails
      until T9. Sequence T5's third assertion after T9 if executing strictly in order.
- [ ] **Commit:** `test(stages): cover the visual and styleboard hand-edit paths`

---

### T6 — Gate C's empty-world diagnosis is comparable to the CLI's

*Closes A-31 (app half; see Handoff H1).*

- [ ] **Write the failing test** in `test_gates.py`:

```python
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
```

- [ ] **Run** → fails (`check` is `"GATE"`, no CLI cross-reference).
- [ ] **Implement, `gates.py`** — introduce a dedicated exception so the fail-closed handler can
      label it, rather than flattening every cause into `"GATE"`:

```python
class GateInputError(ValueError):
    """A gate's INPUT is unusable (empty world lock, missing Library), as
    opposed to the artifact under test being wrong. Recorded with check "C0"
    so the operator can tell 'your styleboard is broken' from 'your sheet is'."""

    check = "C0"
```

  Raise `GateInputError` at the two existing `raise ValueError` input branches in
  `run_prompt_sheet_gate`, and extend the empty-world message:

```python
            raise GateInputError(
                f"styleboard {styleboard_path.name} has no parseable WORLD LOCK block -- "
                f"Gate C cannot check {artifact_path.name} against an empty world. "
                f"`python scripts/lint_prompt_sheet.py {artifact_path.name} "
                f"--styleboard {styleboard_path.name}` reports the same defect as a "
                f"per-shot C8/C18 wall naming the sheet; the defect is in the styleboard."
            )
```

  In `run_gates_for_stage`'s handler, use `getattr(exc, "check", "GATE")` for the finding's
  `check`.

- [ ] **Run** → green. **Commit:** `fix(gates): give Gate C's input errors a check id and a CLI cross-reference`

---

### T7 — CLI ↔ app Gate C differential test with a bounded divergence ledger

*Closes F-19.*

- [ ] **Write the failing test** in `test_gates.py`:

```python
def _cli_findings(sheet: Path, styleboard: Path | None, library: Path) -> set[tuple]:
    """Reproduce lint_prompt_sheet.main's own pipeline (not its printing), so the
    comparison is against the CLI's decisions rather than a paraphrase of them."""
    linter = gates._load_linter(REPO_ROOT, "lint_prompt_sheet")
    sheet_text = sheet.read_text(encoding="utf-8")
    shots, sheet_world = linter.parse_sheet(sheet_text)
    world = (
        linter.parse_world_lock(styleboard.read_text(encoding="utf-8"))
        if styleboard is not None else sheet_world
    )
    cover = linter.parse_cover(sheet_text)
    lib = (
        linter.parse_style_library(library.read_text(encoding="utf-8"))
        if linter.sheet_declares_slots(shots, cover) else None
    )
    findings = [
        *linter.check_cover_present(sheet_text),
        *linter.lint(shots, world, cover=cover, library=lib),
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


@pytest.mark.parametrize("label,sheet,styleboard", DIFFERENTIAL_CASES,
                         ids=[c[0] for c in DIFFERENTIAL_CASES])
def test_app_and_cli_gate_c_report_identical_findings(label, sheet, styleboard):
    """F-19: gates.py's docstring promises one gate, not a stricter CLI and a
    laxer app -- and nothing tested it. C-74, C-75 and A-31 are all divergences
    the two suites could not see because each tested its own side."""
    library = REPO_ROOT / "docs" / "style-library.md"
    assert _app_findings(sheet, styleboard) == _cli_findings(sheet, styleboard, library)


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
```

- [ ] **Run** → the parametrized case(s) reveal any real divergence; fix only the app side
      (`gates.py`) and record anything CLI-side in Handoff H1.
- [ ] **Commit:** `test(gates): assert the CLI and app Gate C agree, and bound the one exception`

> **Amendment (T7B dispatch, this session): `test_app_and_cli_gate_c_report_identical_findings`
> needs a by-design carve-out for the P3-6 stray-world-lock message, or the `"failing"` case
> breaks the moment T7B closes P3-6.** Confirmed empirically: `tests/fixtures/failing_sheet.md`
> (paired with `passing_styleboard.md` in `DIFFERENTIAL_CASES`) carries its own stray `WORLD LOCK`
> block. Before T7B, P3-6 was an unclosed gap and neither side emitted the stray-world-lock
> finding for that pairing, so the full `(check, shot_index, message)` tuple equality this test
> asserts never exercised it. Once T7B lands (correctly making both sides emit the finding), the
> two messages differ **by design** — the CLI's says `"drop --styleboard"`, the app's says `"drop
> the styleboard input"` (T7B's own brief mandates this wording split, since the app has no CLI
> flag) — and the test's strict equality now fails on exactly the wording T7B was told to
> introduce. This is not a real behavioral divergence; it is a test written before the wording
> split existed. **Resolution:** normalize both sides' `PARSE`/stray-world-lock message before
> comparing in `test_app_and_cli_gate_c_report_identical_findings` — e.g. `message.replace("the
> styleboard input", "--styleboard")` (or an equivalent substring normalization) applied to both
> `_app_findings` and `_cli_findings` output before the set equality check, so every other finding
> still compares byte-for-byte and only this one documented wording split is tolerated. Do **not**
> weaken the comparison for any other check id, and do not touch the new P3-6-specific test's own
> substring assertion (already correctly scoped). T7B's own implementer found this and correctly
> stopped rather than loosening the assertion unilaterally — this amendment is what unblocks it.

---

### T7B — Close the four confirmed parity gaps: PR1 / P3-1, P3-2, P3-3, P3-6

*Closes no new finding in this plan's own §2 (none of the four carries an `A-*`/`E-*`/`F-*`
ID — see Pre-review amendment PR1 above). Sequenced immediately after T7 because it depends on
T7's harness and closes the exact class of divergence T7 exists to catch. Do not skip this task
or fold it silently into T7's commit — it is real, separately-reviewable TDD work.*

`_cli_findings` (T7) currently **manually re-derives** `main()`'s pipeline rather than calling
into it, and it was missing the same four pieces `run_prompt_sheet_gate` is missing — so T7's
parametrized comparison could pass while both sides silently agreed on the *wrong* thing. Fix
`_cli_findings` and `run_prompt_sheet_gate` **together**, in the same commit, so the fixed CLI
side is the oracle the fixed app side is tested against — not two independent guesses that
happen to match.

**What `main()` actually does today (verified against the live `scripts/lint_prompt_sheet.py`,
this session)**, which both `_cli_findings` and `run_prompt_sheet_gate` must match line for line:

```python
parse = parse_sheet(sheet_text)                     # SheetParse: .shots, .world, .findings,
                                                      # .declared_shot_count (a tuple subclass;
                                                      # `shots, world = parse_sheet(...)` still
                                                      # works, which is why gates.py's existing
                                                      # 2-tuple unpack silently compiles while
                                                      # dropping `.findings`)
# ... world resolution (styleboard vs sheet's own block; on both branches present, main()
#     appends a `Finding("PARSE", None, <message below>, kind="parse")` to parse.findings
#     rather than raising -- it is a blocking finding, not a fatal error)
library, library_findings = parse_style_library_checked(library_text)   # NOT parse_style_library
if library_findings:                                 # any malformed Library entry heading
    return EXIT_MISSING_DEPENDENCY                    # (an early exit, not folded into `findings`)
findings = [
    *parse.findings,
    *check_cover_present(sheet_text),
    *lint(shots, world, cover=cover, library=library, declared_shot_count=parse.declared_shot_count),
]
```

The stray-world-lock finding's exact CLI text (append to `parse.findings` — or, in
`run_prompt_sheet_gate`'s case, to whatever list feeds the returned findings — whenever
`styleboard_path is not None and sheet_world` is truthy):

```
the sheet at {sheet_name} carries its own WORLD LOCK block, but a styleboard was also supplied
at {styleboard_name}; the sheet's block is being discarded -- remove it from the sheet if the
styleboard is now authoritative, or drop --styleboard if the sheet's own block should still apply.
```

(App-side wording may say "the styleboard input" in place of "--styleboard", since the app has
no command-line flag. The differential test's assertion on this message should check for the
shared substring "own WORLD LOCK block", not full equality — see the fourth test below.)

- [ ] **Write four failing tests** in `test_gates.py`, each asserting `_app_findings(...) ==
      _cli_findings(...)` (reuse T7's helpers) or, where the CLI path takes an early exit,
      asserting `_app_findings` raises/records the equivalent `status: "error"` the way T6's own
      empty-world-lock test does:
  1. **P3-1 / C-70** — a sheet whose second shot heading is malformed (e.g. missing its trailing
     scale/height field, or a stray character breaking `SHOT_HEADING_RE`). Before this task, the
     app path silently drops that shot from every check (C-70's exact mechanism) while the CLI
     records a blocking `PARSE` finding naming the line. Build the sheet inline in the test
     (start from `passing_sheet.md`'s text and corrupt one heading line), not as a new fixture
     file.
  2. **P3-2 / C-71** — a sheet whose `Shots: N` declared count does not match its actual shot
     count. Confirm `check_shot_count` is the function that fires (it is already called by
     `lint()` when `declared_shot_count` is not `None`; before this task the app path always
     passes `None`, so the check can never fire there).
  3. **P3-3 / C-76** — a Style Library text with one malformed `### ` entry heading (e.g. missing
     the required lowercase-kebab shape). CLI: `EXIT_MISSING_DEPENDENCY`, printing the library
     finding. App: before this task, `parse_style_library` (the unchecked variant) silently drops
     the entry and Gate C blames the *sheet* the first time something binds the missing label —
     assert the app now raises a `ValueError`/records `status: "error"` naming the Library file,
     matching the CLI's early exit rather than deferring to a confusing C20 failure one stage
     later.
  4. **P3-6** — a sheet that still carries its own `WORLD LOCK` block, with a styleboard also
     supplied. Assert both sides report the same `PARSE` finding (message may differ only in the
     `--styleboard`-vs-"the styleboard input" wording noted above; check id, shot_index
     (`None`), and the substring "own WORLD LOCK block" must match).
- [ ] **Run** → confirm all four fail for the stated reason (the app path silently omits the
      finding, or the CLI/app pair produce different results) before touching implementation.
- [ ] **Implement, `gates.py`** — in `run_prompt_sheet_gate`, mirror `main()`'s pipeline above:
      switch to `parse = linter.parse_sheet(sheet_text)` and read `parse.shots`, `parse.world`,
      `parse.findings`, `parse.declared_shot_count` from it; append the stray-world-lock finding
      exactly as `main()` does when both a styleboard and a sheet-side world lock are present;
      switch `parse_style_library` to `parse_style_library_checked` and raise `ValueError` naming
      the Library file when `library_findings` is non-empty (same shape as the existing two
      empty-Library/empty-world `ValueError`s beside it); pass `declared_shot_count=` into
      `linter.lint(...)`; prepend `parse.findings` (as dicts, via the existing `_as_dicts`) to the
      returned findings list. Do **not** change `_load_linter`, `GATE_REGISTRY`, or anything in
      `run_gates_for_stage` — this task is scoped to `run_prompt_sheet_gate`'s body only.
- [ ] **Update `_cli_findings`** (T7) to the corrected pipeline shown above, so it is a complete
      mirror rather than a partial one — this is what keeps `test_app_and_cli_gate_c_report_identical_findings`
      and the four new tests honest against each other rather than against two independently
      wrong guesses.
- [ ] **Re-run T7's existing parametrized cases** (`passing`, `failing`, `legacy`, `worked`) —
      confirm they still pass now that both sides changed. If any of the four now diverges for a
      reason specific to that fixture, treat it as a fifth real finding and stop to investigate
      rather than loosening either side's assertion to make it pass.
- [ ] **Run the full app suite** → green.
- [ ] **Commit:** `fix(gates): close the four remaining CLI/app Gate C parity gaps (parse findings, declared count, checked library, stray world lock)`

---

### T8 — A styleboard gate: the world lock Gate C will later read

*Closes A-33 (part 1).*

- [ ] **Write the failing tests** in `test_gates.py`:

```python
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
```

- [ ] **Run** → fails (`styleboard` unregistered → `[]`, `IndexError`).
- [ ] **Implement, `gates.py`:**

```python
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
```

  `_check_styleboard_slots` arrives in T9 — stub it as `return []` for this task only if the
  suite is being run mid-task; do not commit a stub.

- [ ] Register it: `GATE_REGISTRY["styleboard"] = [("gate_s_styleboard", run_styleboard_gate)]`.
- [ ] **Run** → green. **Commit:** `feat(gates): gate the styleboard Gate C reads its world from`

---

### T9 — The styleboard gate resolves its own slot labels

*Closes A-33 (part 2).*

- [ ] **Write the failing tests** in `test_gates.py`:

```python
def test_a_styleboard_slot_value_shaped_like_an_invented_code_fails(tmp_path):
    path = tmp_path / "artifact.v1.md"
    path.write_text(_world_lock(slot_register_a="SREF-RGS-A-DL01"), encoding="utf-8")
    result = gates.run_gates_for_stage(REPO_ROOT, "styleboard", path, {})[0]
    assert "S3" in {f["check"] for f in result["findings"]}


def test_a_styleboard_label_naming_no_library_entry_fails_here_not_downstream(tmp_path):
    """A-33/A-34's real fix: C20 blamed the sheet for a label the STYLEBOARD
    chose, once per affected shot. Catch it where it was written."""
    path = tmp_path / "artifact.v1.md"
    path.write_text(_world_lock(slot_register_b="rgs-sourceera-painterly-c"), encoding="utf-8")
    result = gates.run_gates_for_stage(REPO_ROOT, "styleboard", path, {})[0]
    s4 = [f for f in result["findings"] if f["check"] == "S4"]
    assert len(s4) == 1, "one finding per bad label, not one per downstream shot"
    assert "docs/style-library.md" in s4[0]["message"]
```

  with a `_world_lock(**overrides)` helper that renders a valid block from
  `passing_styleboard.md`'s values and applies overrides.

- [ ] **Run** → fails.
- [ ] **Implement, `gates.py`:**

```python
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
    library = linter.parse_style_library(library_path.read_text(encoding="utf-8"))
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
```

- [ ] **Run** → green, including T5's third test. **Commit:** `feat(gates): resolve styleboard slot labels at the styleboard stage`

---

### T10 — Only an explicit `pass` passes

*Closes A-35.*

- [ ] **Write three failing tests** in `test_approval_service.py`:

```python
@pytest.mark.parametrize("status", ["skipped", None, "PASS", "", "passs"])
def test_an_unrecognized_gate_status_blocks_approval(conn, tmp_path, status):
    """A-35 FAULT: the block condition tested `status in ("fail","error")` and
    the never-ran test only asked whether the NAME appeared, so `skipped`, null,
    a missing key or a typo satisfied both and approved with no override and no
    message."""
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    _write_artifact_with_gates(stage_dir, status)
    with pytest.raises(ValueError, match="unrecognized"):
        approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting")


def test_an_unrecognized_status_is_distinguishable_from_a_failure(conn, tmp_path):
    """A-35 DISTINGUISHABILITY: 'the gate failed', 'the gate never ran' and 'the
    gate recorded a word we do not know' are three different facts with three
    different fixes."""
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    _write_artifact_with_gates(stage_dir, "skipped")
    with pytest.raises(ValueError) as excinfo:
        approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting")
    message = str(excinfo.value)
    assert "'skipped'" in message
    assert "never ran" not in message


def test_an_unrecognized_status_records_an_event(conn, tmp_path):
    """A-35 SURFACING: a vocabulary change must be findable after the fact, not
    only in the 409 the operator dismissed."""
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    _write_artifact_with_gates(stage_dir, "skipped")
    with pytest.raises(ValueError):
        approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting")
    rows = conn.execute(
        "SELECT kind, severity FROM events WHERE kind = 'gate.unknown_status'"
    ).fetchall()
    assert [(r["kind"], r["severity"]) for r in rows] == [("gate.unknown_status", "warning")]
```

- [ ] **Run** → fails (approval succeeds).
- [ ] **Write the cross-surface invariant test** (P15's question 1) in `test_routes_stages.py`:

```python
GATE_MATRIX = [
    ("passing",     [{"name": "gate_d_script_language", "status": "pass", "findings": []}]),
    ("failing",     [{"name": "gate_d_script_language", "status": "fail", "findings": []}]),
    ("errored",     [{"name": "gate_d_script_language", "status": "error", "findings": []}]),
    ("never_ran",   []),
    ("wrong_gate",  [{"name": "gate_c_prompt_sheet", "status": "pass", "findings": []}]),
    ("unknown",     [{"name": "gate_d_script_language", "status": "skipped", "findings": []}]),
    ("no_status",   [{"name": "gate_d_script_language", "findings": []}]),
    ("skipped_only", [{"name": "gate_d_script_language", "status": "pass",
                      "findings": [{"check": "D5", "beat": "SETUP", "kind": "skipped",
                                    "message": "no computable time range"}]}]),
]


@pytest.mark.parametrize("label,gates_block", GATE_MATRIX, ids=[c[0] for c in GATE_MATRIX])
def test_the_page_flag_the_per_gate_tag_and_the_approve_decision_never_disagree(
    tmp_path, monkeypatch, label, gates_block
):
    """E-03's real mechanism, closed structurally. has_failing_gate did not
    disagree with itself -- it disagreed with approve_stage: a never-ran gate
    rendered as a clean pass, the approve form rendered WITHOUT the override
    field, and clicking Approve returned a bare 409 with no path forward from
    inside the UI. P15 now renders gate_view[].blocking as a per-gate tag and
    has_blocking_gate as the page-level flag, so there are three surfaces that
    must agree. They all read one classifier; this asserts it."""
    test_client, tmp_path, app = _scripting_client(tmp_path, monkeypatch)
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    artifacts.write_artifact(
        run_dir / "02-scripting", 1,
        {"schema_version": 1, "stage": "shorts-scripting", "version": 1,
         "status": "draft", "gates": gates_block},
        "script body",
    )

    ctx = test_client.get(f"/projects/{project_id}/stages/scripting").context
    page_flag = ctx["has_blocking_gate"]

    # 1. the page-level flag is the per-gate tags and nothing else
    assert page_flag == any(g["blocking"] for g in ctx["gate_view"])
    # 2. ...and it agrees with what the approve route actually does
    approve = test_client.post(f"/projects/{project_id}/stages/scripting/approve")
    assert (approve.status_code == 409) == page_flag, (
        f"{label}: page says blocking={page_flag} but approve returned "
        f"{approve.status_code}"
    )
    # 3. ...and the override field is offered exactly when it is needed
    assert ('name="override_reason"' in test_client.get(
        f"/projects/{project_id}/stages/scripting"
    ).text) == page_flag
```

- [ ] **Implement, `approval_service.py`** — invert the test **and** extract the single
      classifier both surfaces read (P15's question 1). `approve_stage` and
      `routes/stages._stage_context` must never judge a gate independently again:

```python
PASSING = "pass"
KNOWN_STATUSES = frozenset({"pass", "fail", "error"})


def classify_gates(stage_id: str, recorded: list[dict]) -> list[dict]:
    """One entry per gate, carrying `state` and the `blocking` verdict.

    The ONE place a gate result is judged. approve_stage used to consult
    GATE_REGISTRY for a never-ran gate while stage_page's has_failing_gate only
    looked for fail/error, so the page and the 409 disagreed -- that disagreement
    IS E-03. Every surface reads this list: the approve decision, gate_view, and
    has_blocking_gate. Only an explicit "pass" is not blocking (A-35).
    """
    reported = {g.get("name") for g in recorded}
    classified = []
    for g in recorded:
        status = g.get("status")
        state = {
            "pass": "passed", "fail": "failed", "error": "errored",
        }.get(status, "unknown")
        classified.append({
            "name": g.get("name"), "state": state, "status_raw": status,
            "blocking": state != "passed", "findings": g.get("findings") or [],
        })
    classified.extend({
        "name": name, "state": "never_ran", "status_raw": None,
        "blocking": True, "findings": [],
    } for name, _runner in GATE_REGISTRY.get(stage_id, []) if name not in reported)
    return classified
```

  `approve_stage` then reads `blocking = [g for g in classify_gates(stage_id, recorded)
  if g["blocking"]]` and raises when `blocking and not override_reason`, building its message
  from each entry's `state`. The three lists below are derived from `classify_gates`'s output
  for the message wording only — never re-derived from `recorded`:

```python
    failing = [g for g in recorded if g.get("status") in ("fail", "error")]
    unknown = [g for g in recorded if g.get("status") not in KNOWN_STATUSES]
    for g in unknown:
        obs.record_event(
            conn, kind="gate.unknown_status", severity="warning", source="approval_service",
            message=(
                f"gate {g.get('name')!r} on stage '{stage_id}' recorded status "
                f"{g.get('status')!r}, which is not one of {sorted(KNOWN_STATUSES)}"
            ),
            detail={"project_id": project_id, "stage_id": stage_id},
        )
    ...
    if (failing or never_ran or unknown) and not override_reason:
        problems = [f"{g['name']} ({g['status']})" for g in failing]
        problems += [f"{name} (never ran -- no result in the artifact)" for name in never_ran]
        problems += [
            f"{g.get('name')} (unrecognized status {g.get('status')!r} -- only 'pass' passes)"
            for g in unknown
        ]
```

  Update `_write_artifact_with_gates` to accept a `status` that may be `None` (omit the key).

- [ ] **Run** → green. **Commit:** `fix(approval): treat any status other than "pass" as blocking`

> **Amendment (T10 dispatch, this session): the cross-surface invariant test
> (`test_the_page_flag_the_per_gate_tag_and_the_approve_decision_never_disagree`) has THREE
> undeclared forward dependencies and must be deferred, not written as part of T10.** Confirmed
> empirically against the live repo:
> 1. `_stage_context` does not exist as a standalone function yet — today `stage_page`'s logic is
>    inline, and `_stage_context` is only extracted out in **T19** (`_stage_conflict` calls it).
> 2. `gate_view` and `has_blocking_gate` do not exist anywhere in `routes/stages.py` yet — the
>    current inline logic only computes `has_failing_gate = any(g.get("status") in ("fail",
>    "error") for g in output_gates)` and passes `output_gates` (the raw list) to the template.
>    Neither T19's nor T20's own shown code snippets actually add the line wiring
>    `gate_view = classify_gates(stage_id, output_gates)` / `has_blocking_gate = any(g["blocking"]
>    for g in gate_view)` into `_stage_context` — §6's "Contract for P15" prose describes the end
>    state but no numbered task's shown code performs the wiring. **T19 must perform it** (see the
>    amendment inserted at T19 below) — it is the natural point, since T19 is where
>    `_stage_context` is extracted from `stage_page` in the first place, and `has_failing_gate` is
>    exactly the value `gate_view`/`has_blocking_gate` replace.
> 3. `_scripting_client` (used by this test) is referenced nowhere else in this plan — it is not
>    defined anywhere in `test_routes_stages.py` or any other task's text. It needs to be written
>    (or an existing equivalent fixture substituted) at the point this test actually runs.
>
> **Resolution:** T10 itself (`classify_gates`, `approve_stage`'s three fail-closed tests) has no
> forward dependency and is dispatched as-is, in full. The **cross-surface invariant test is
> deferred** to run immediately after T19 lands (see T19's own amendment below), once
> `_stage_context`, `gate_view`, and `has_blocking_gate` all exist. Do not write it as part of
> T10's own dispatch.

---

### T11 — A malformed `gates` value is a 409, not a 500

*Closes A-36.*

- [ ] **Write the failing tests** in `test_approval_service.py` and `test_routes_approve_edit.py`:

```python
@pytest.mark.parametrize("value", ["pass", 1, ["gate_d_script_language"], {"name": "x"}])
def test_a_malformed_gates_frontmatter_value_raises_valueerror(conn, tmp_path, value):
    """A-36: `recorded` is whatever yaml.safe_load produced. A string, scalar or
    list-of-strings made the comprehension call .get on a non-mapping and raise
    AttributeError -- an unhandled 500, not the 409 every other approval
    conflict produces. Most acute for `grounding`, whose frontmatter is
    hand-written and entirely uncontrolled."""
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    artifacts.write_artifact(
        stage_dir, 1,
        {"schema_version": 1, "stage": "shorts-scripting", "status": "draft", "gates": value},
        "body",
    )
    with pytest.raises(ValueError, match="artifact.v1.md"):
        approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting")


def test_approve_route_returns_409_not_500_for_a_malformed_gates_block(client):
    ...  # writes gates: "pass" then asserts approve_resp.status_code == 409
```

- [ ] **Run** → fails with `AttributeError` (and a 500 through the route).
- [ ] **Implement, `approval_service.py`**, immediately after `recorded = ...`:

```python
    if not isinstance(recorded, list) or any(not isinstance(g, dict) for g in recorded):
        raise ValueError(
            f"Stage '{stage_id}': the `gates` block in {latest.name} is not a list of "
            f"gate results (found {type(recorded).__name__}). Fix the artifact's "
            "frontmatter, or regenerate the stage."
        )
```

- [ ] **Run** → green. **Commit:** `fix(approval): reject a malformed gates block as a conflict`

---

### T12 — A blank override reason is rejected by the service, not the route

*Closes A-39.*

- [ ] **Write three failing tests** in `test_approval_service.py`:

```python
@pytest.mark.parametrize("reason", ["   ", "\t", "\n", ""])
def test_a_blank_override_reason_does_not_release_a_failing_gate(conn, tmp_path, reason):
    """A-39 FAULT: the stripping that makes an empty reason falsy lived in the
    ROUTE, not in approve_stage. approve_stage(..., override_reason=" ") is
    truthy, so it cleared the block AND recorded a blank reason. Any second
    caller -- a script, a future API, a test -- reintroduces the hole."""
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    _write_artifact_with_gates(stage_dir, "fail")
    with pytest.raises(ValueError, match="gate"):
        approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting",
                      override_reason=reason)


def test_a_blank_override_reason_is_never_recorded_on_the_artifact(conn, tmp_path):
    """A-39 DISTINGUISHABILITY: a blank reason must be indistinguishable from no
    reason at all on disk -- not a `gate_override_reason: ' '` key that reads as
    a decision someone made."""
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    path = _write_artifact_with_gates(stage_dir, "pass")
    approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting",
                  override_reason="   ")
    meta, _ = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    assert "gate_override_reason" not in meta


def test_an_override_reason_is_stored_stripped(conn, tmp_path):
    """A-39 SURFACING: the recorded reason is the audit trail; leading and
    trailing whitespace in it is noise the reviewer has to see through."""
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    path = _write_artifact_with_gates(stage_dir, "fail")
    approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting",
                  override_reason="  dash is inside a verbatim 1886 quote  ")
    meta, _ = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["gate_override_reason"] == "dash is inside a verbatim 1886 quote"
```

- [ ] **Run** → fails.
- [ ] **Implement, `approval_service.py`**, as the first statement of `approve_stage`:

```python
    # The invariant belongs to the service that owns the decision, not to one of
    # its callers (A-39). The route now passes the raw form value through.
    override_reason = (override_reason or "").strip() or None
```

- [ ] **Implement, `routes/stages.py`:** pass `override_reason=override_reason` (drop the
      `.strip() or None`), and keep `test_approve_route_blank_override_field_does_not_count_as_override`
      green as the end-to-end proof.
- [ ] **Run** → green. **Commit:** `fix(approval): normalize and reject blank override reasons in the service`

---

### T13 — `BaseException` cannot escape fail-closed

*Closes A-40.*

- [ ] **Write the failing tests** in `test_gates.py`:

```python
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
```

- [ ] **Run** → fails (`SystemExit` propagates).
- [ ] **Implement, `gates.py`:**

```python
# Re-raised, never recorded: these are the process or the caller saying stop, and
# converting them into a recorded gate result would swallow a real cancellation.
_CANCELLATION = (KeyboardInterrupt, asyncio.CancelledError, GeneratorExit)
        ...
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
```

  Note `test_a_linter_that_raises_is_an_error_not_a_pass` asserts `"linter exploded" in message`
  — still true with the `RuntimeError: ` prefix.

- [ ] **Run** → green. **Commit:** `fix(gates): fail closed on BaseException, re-raise cancellation`

---

### T14 — `_load_linter` caches and cleans up after itself

*Closes A-42.*

- [ ] **Write the failing tests** in `test_gates.py`:

```python
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
```

- [ ] **Run** → fails (`lint_broken` still in `sys.modules`; two distinct module objects).
- [ ] **Implement, `gates.py`:**

```python
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
    # sys.modules by name. (unchanged rationale)
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
```

- [ ] **Run** → green. **Commit:** `fix(gates): cache loaded linters and unregister a failed exec`

---

### T15 — `state_machine.stages_to_relock`

*Closes A-45 (part 1).*

- [ ] **Write the failing tests** in `test_state_machine.py`:

```python
def test_stages_to_relock_finds_a_dependent_whose_dependency_left_approved():
    """A-45: stages_to_unlock is a one-way ratchet and LOCKED is never passed to
    update_stage_status anywhere in the app. Approve scripting (unlocking
    styleboard and voiceover), then hand-edit scripting -- the dependents stay
    ready, runnable and approvable on a dependency that is no longer approved."""
    stages = [
        StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02"),
        StageDef(id="styleboard", skill="shorts-styleboard", dir_prefix="02b",
                 depends_on=["scripting"]),
    ]
    assert stages_to_relock(stages, approved_stage_ids=set()) == ["styleboard"]
    assert stages_to_relock(stages, approved_stage_ids={"scripting"}) == []


def test_stages_to_relock_is_the_exact_inverse_of_stages_to_unlock():
    """The DAG invariant must hold in both directions or `locked` records a
    high-water mark rather than the current topology."""
    stages = [
        StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02"),
        StageDef(id="voiceover", skill="voiceover-brief", dir_prefix="03",
                 depends_on=["scripting"]),
        StageDef(id="visual", skill="visual-prompts", dir_prefix="03",
                 depends_on=["scripting"]),
        StageDef(id="assembly", skill="shorts-assembly", dir_prefix="04",
                 depends_on=["voiceover", "visual"]),
    ]
    for approved in ({"scripting"}, {"scripting", "voiceover"}, set()):
        unlockable = set(stages_to_unlock(stages, approved))
        relockable = set(stages_to_relock(stages, approved))
        assert not (unlockable & relockable)


def test_stages_to_relock_never_relocks_an_approved_stage():
    stages = [
        StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02"),
        StageDef(id="styleboard", skill="shorts-styleboard", dir_prefix="02b",
                 depends_on=["scripting"]),
    ]
    assert stages_to_relock(stages, approved_stage_ids={"styleboard"}) == []
```

- [ ] **Run** → `ImportError`.
- [ ] **Implement, `state_machine.py`:**

```python
def stages_to_relock(all_stage_defs: list[StageDef], approved_stage_ids: set[str]) -> list[str]:
    """The inverse of stages_to_unlock: dependents whose dependencies are no
    longer all approved (A-45).

    An already-approved stage is never relocked -- it has an artifact of its
    own and the right treatment is staleness, not a lock that would hide it.
    """
    relock = []
    for stage in all_stage_defs:
        if stage.id in approved_stage_ids:
            continue
        if stage.depends_on and not all(dep in approved_stage_ids for dep in stage.depends_on):
            relock.append(stage.id)
    return relock
```

- [ ] **Run** → green. **Commit:** `feat(state-machine): add the inverse of stages_to_unlock`

---

### T16 — Wire the re-lock cascade into the edit path

*Closes A-45 (part 2).*

- [ ] **Write three failing tests** in `test_routes_approve_edit.py`:

```python
def test_hand_editing_an_approved_stage_relocks_a_dependent_with_no_artifact(visual_client):
    """A-45 FAULT."""
    ...  # approve scripting -> styleboard becomes ready; edit scripting;
         # assert styleboard is back to "locked"


def test_a_dependent_that_has_its_own_artifact_goes_stale_rather_than_locked(visual_client):
    """A-45 DISTINGUISHABILITY: 'you cannot start this yet' and 'what you already
    made is out of date' are different states and must not collapse into one.
    Locking a stage that has output would hide the output."""
    ...  # assert styleboard is "stale", not "locked", and its artifact still exists


def test_a_relock_is_recorded_as_an_event(visual_client):
    """A-45 SURFACING: a stage silently reverting to `locked` under the operator
    is exactly the kind of state change that needs a row."""
    ...  # assert an events row kind="stage.relocked", severity="info"
```

- [ ] **Run** → fails (dependents stay `ready`).
- [ ] **Implement, `approval_service.py`:**

```python
def relock_unsatisfied_dependents(
    conn: sqlite3.Connection,
    run_dir: Path,
    stage_defs: list[StageDef],
    project_id: int,
) -> list[str]:
    """Bring `locked` back in line with the current DAG (A-45).

    stages_to_unlock is a one-way ratchet: once a dependent is unlocked nothing
    ever locks it again, so hand-editing an approved stage left its dependents
    runnable and approvable on a dependency that is no longer approved. A
    dependent that already has an artifact is left alone -- propagate_staleness
    owns that case, and locking it would hide output the operator can see.
    """
    rows = db_mod.list_stages(conn, project_id)
    approved = {r["stage_id"] for r in rows if r["status"] == StageStatus.APPROVED.value}
    by_id = {r["stage_id"]: r for r in rows}
    relocked = []
    for sid in stages_to_relock(stage_defs, approved):
        row = by_id.get(sid)
        if row is None or row["status"] in (
            StageStatus.LOCKED.value, StageStatus.RUNNING.value
        ):
            continue
        stage_def = next(s for s in stage_defs if s.id == sid)
        stage_dir = run_dir / stage_dir_name(stage_def)
        if artifacts.latest_artifact_path(stage_dir) is not None:
            continue
        db_mod.update_stage_status(conn, row["id"], StageStatus.LOCKED.value)
        relocked.append(sid)
        obs.record_event(
            conn, kind="stage.relocked", severity="info", source="approval_service",
            message=f"stage '{sid}' relocked: dependency no longer approved",
            detail={"project_id": project_id, "stage_id": sid},
        )
    return relocked
```

- [ ] **Implement, `routes/stages.py`** — after `update_stage_status(..., "awaiting_review")`:

```python
    approval_service.relock_unsatisfied_dependents(conn, run_dir, stage_defs, project_id)
```

- [ ] **Run** → green. **Commit:** `fix(approval): re-lock dependents when a stage leaves approved`

---

### T17 — Orphan recovery is visible and quarantines the dead turn's scratch

*Closes A-77.*

- [ ] **Write three failing tests** in `test_preflight.py`:

```python
def test_reconcile_records_an_event_naming_the_project_and_stage(conn, tmp_path):
    """A-77 FAULT + SURFACING: _unwedge_stage restores awaiting_review whenever
    ANY artifact resolves -- but that artifact came from a PREVIOUS turn; the
    killed turn produced nothing. The resulting state is byte-identical to a
    healthy stage awaiting review, so the operator approves stale output
    believing the last turn succeeded. /doctor shows a bare orphaned_count."""
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "running")
    db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:00:00Z", "events/x.jsonl")
    artifacts.write_artifact(
        tmp_path / "runs" / "abc-1" / "01-ideation", 1, {"stage": "shorts-ideation"}, "body"
    )

    reconcile_orphaned_turns(conn, tmp_path, STAGE_DEFS)

    row = conn.execute("SELECT * FROM events WHERE kind = 'turn.orphaned'").fetchone()
    assert row is not None
    assert row["severity"] == "warning"
    assert "abc-1" in row["message"] and "ideation" in row["message"]


def test_an_orphaned_stage_is_distinguishable_from_a_healthy_awaiting_review(conn, tmp_path):
    """A-77 DISTINGUISHABILITY: the whole defect is that the two states are
    byte-identical. A healthy stage produces no turn.orphaned event."""
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "awaiting_review")
    reconcile_orphaned_turns(conn, tmp_path, STAGE_DEFS)
    assert conn.execute("SELECT COUNT(*) c FROM events "
                        "WHERE kind = 'turn.orphaned'").fetchone()["c"] == 0


def test_the_dead_turns_raw_output_is_quarantined_not_left_as_the_next_baseline(conn, tmp_path):
    """A-77: the dead turn's partially-written raw_output.md became the NEXT
    turn's before_mtime baseline, so a resumed turn writing identical content
    was detected as a change and one writing nothing was reported no_artifact."""
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "running")
    db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:00:00Z", "events/x.jsonl")
    stage_dir = tmp_path / "runs" / "abc-1" / "01-ideation"
    stage_dir.mkdir(parents=True)
    (stage_dir / "raw_output.md").write_text("half a turn", encoding="utf-8")

    reconcile_orphaned_turns(conn, tmp_path, STAGE_DEFS)

    assert not (stage_dir / "raw_output.md").exists()
    quarantined = list(stage_dir.glob("raw_output.orphaned-*.md"))
    assert len(quarantined) == 1
    assert quarantined[0].read_text(encoding="utf-8") == "half a turn"
```

- [ ] **Run** → fails.
- [ ] **Implement, `preflight.py`** — `_unwedge_stage` gains the quarantine + event, and
      `reconcile_orphaned_turns` passes the turn id through:

```python
    if latest is not None:
        # A-77: the artifact that resolves here belongs to a PREVIOUS turn. Say
        # so, or an operator approves it believing the killed turn produced it.
        obs.record_event(
            conn, kind="turn.orphaned", severity="warning", source="preflight",
            message=(
                f"turn {turn_id} on {project['run_id']}/{stage_def.id} was orphaned; "
                f"the stage is showing {latest.name} from an earlier turn"
            ),
            detail={"project_id": project["id"], "stage_id": stage_def.id,
                    "turn_id": turn_id, "artifact": latest.name},
        )
    _quarantine_raw_output(stage_dir)


def _quarantine_raw_output(stage_dir: Path) -> Path | None:
    """Move a dead turn's scratch aside so it cannot masquerade as the next
    turn's before_mtime baseline (A-77). Renamed, never deleted -- a partial
    turn's output is sometimes the only record of what went wrong."""
    raw = stage_dir / "raw_output.md"
    if not raw.is_file():
        return None
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = stage_dir / f"raw_output.orphaned-{stamp}.md"
    raw.replace(target)
    return target
```

- [ ] **Run** → green. **Commit:** `fix(preflight): surface and quarantine orphaned turns`

---

### T18 — The three defensive early returns report instead of no-op'ing

*Closes F-28.*

- [ ] **Write three failing tests** in `test_preflight.py`:

```python
def test_a_stage_id_no_longer_in_pipeline_yaml_is_reported(conn, tmp_path):
    """F-28 FAULT: the three early returns each return None with no log. A stage
    whose id was renamed or removed from pipeline.yaml stays wedged at RUNNING
    across every restart, and the sweep reports nothing."""
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "removed-stage", "running")
    db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:00:00Z", "events/x.jsonl")

    reconcile_orphaned_turns(conn, tmp_path, STAGE_DEFS)

    row = conn.execute(
        "SELECT * FROM events WHERE kind = 'preflight.unwedge_skipped'"
    ).fetchone()
    assert row["severity"] == "error"
    assert "removed-stage" in row["message"]
    assert db.get_stage_by_row_id(conn, stage_row_id)["status"] == "running"


def test_an_unwedge_skip_is_distinguishable_from_a_successful_unwedge(conn, tmp_path):
    """F-28 DISTINGUISHABILITY: a swept stage and a stage the sweep could not
    touch both left the function returning None."""
    ...  # healthy case produces zero preflight.unwedge_skipped rows


@pytest.mark.parametrize("reason", ["stage-row-missing", "stage-def-missing", "project-missing"])
def test_each_defensive_return_names_which_one_fired(conn, tmp_path, reason):
    """F-28 SURFACING: three different causes, three different fixes."""
    ...  # each asserts detail["reason"] == reason
```

- [ ] **Run** → fails.
- [ ] **Implement, `preflight.py`** — replace each bare `return` with a
      `_skip(conn, reason, ...)` helper that records
      `kind="preflight.unwedge_skipped", severity="error"` (and `"info"` for the benign
      not-RUNNING case, which is the sweep's normal idempotency path) and then returns.
      `reconcile_orphaned_turns` continues to return the running-turn count.
- [ ] **Run** → green. **Commit:** `fix(preflight): report every unwedge that could not run`

---

### T19 — Expected failures re-render the page instead of destroying it

*Closes E-04.*

- [ ] **Write the failing tests** in `test_routes_stages.py`:

```python
def test_a_gate_block_re_renders_the_stage_page_with_a_banner(tmp_path, monkeypatch):
    """E-04: eight operator-reachable error states navigated the browser to an
    unstyled text document with no header, no nav, no back link and no form to
    retry from. Recovery was browser-back in every case. Keep the status codes;
    return the page."""
    ...
    resp = test_client.post(f"/projects/{project_id}/stages/scripting/approve")
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("text/html")
    assert "gate_d_script_language" in resp.text        # the page, not a text file
    assert 'name="override_reason"' in resp.text        # a way forward from here
    assert "error-banner" in resp.text


def test_a_locked_stage_edit_re_renders_with_a_banner(two_stage_client):
    ...  # 409 + text/html + "error-banner"


def test_the_grounding_edit_refusal_keeps_its_message(tmp_path, monkeypatch):
    ...  # 409 + "rgs-briefs" still present in the rendered page
```

- [ ] **Run** → fails (`text/plain`).
- [ ] **Implement, `routes/stages.py`** — factor `stage_page`'s body into
      `_stage_context(request, project_id, stage_id, *, error_banner=None) -> dict` and add:

```python
def _stage_conflict(request, project_id: int, stage_id: str, message: str,
                    *, kind: str = "conflict", status_code: int = 409):
    """E-04: an expected failure returns the page it came from, with a banner --
    same status code, recoverable UI. PlainTextResponse threw away the header,
    the nav, the form and any typed content."""
    context = _stage_context(request, project_id, stage_id,
                             error_banner={"kind": kind, "message": message})
    return request.app.state.templates.TemplateResponse(
        request, "stage.html", context, status_code=status_code
    )
```

  Replace all five `PlainTextResponse` returns in this file (chat locked, chat busy, approve
  409, edit grounding, edit locked) with `_stage_conflict(...)`. Status codes unchanged.
  `projects.py` and `discovery.py` are **not** this package's — E-04's other three sites
  belong to P5/P8.

- [ ] **Run** → green (P15 adds the `error-banner` markup; until then add the minimal
      `{% if error_banner %}` block **is P15's**, so coordinate: this task asserts the context
      key and status code, and the markup assertions move green when P15 lands).
- [ ] **Commit:** `fix(stages): return the stage page with a banner instead of plain text`

> **Amendment (deferred from T10, this session): wire `gate_view`/`has_blocking_gate` into
> `_stage_context` as part of this task's own extraction, and add the deferred cross-surface
> invariant test here.** T10 (already landed) added `classify_gates` to `approval_service.py` but
> could not wire it into `routes/stages.py` because `_stage_context` did not exist as a
> standalone function until this task extracts it. Since this task is already replacing
> `stage_page`'s inline body with `_stage_context`, do the replacement in the same motion:
>
> - Delete the current `has_failing_gate = any(g.get("status") in ("fail", "error") for g in
>   output_gates)` line.
> - Add `from pipeline_app.approval_service import classify_gates` (or wherever `classify_gates`
>   actually lives after T10 — confirm by `grep -n "def classify_gates" pipeline_app/*.py` before
>   writing the import).
> - Add `gate_view = classify_gates(stage_id, output_gates)` and `has_blocking_gate =
>   any(g["blocking"] for g in gate_view)`, and put both in the context dict returned by
>   `_stage_context`. Keep `output_gates` in the context too for one release (per §6's own note);
>   do not delete it here — T23/T24 or a later cleanup removes it.
> - Update every existing test in `test_routes_stages.py` (and any other file) that currently
>   asserts on `has_failing_gate` to use `has_blocking_gate/gate_view` instead — grep for
>   `has_failing_gate` across `pipeline-app/tests/` before implementing, so no test is left
>   asserting on a key you just deleted.
>
> Then, **now that `_stage_context`, `gate_view`, and `has_blocking_gate` all exist**, add T10's
> deferred cross-surface invariant test to `test_routes_stages.py`:
>
> ```python
> GATE_MATRIX = [
>     ("passing",     [{"name": "gate_d_script_language", "status": "pass", "findings": []}]),
>     ("failing",     [{"name": "gate_d_script_language", "status": "fail", "findings": []}]),
>     ("errored",     [{"name": "gate_d_script_language", "status": "error", "findings": []}]),
>     ("never_ran",   []),
>     ("wrong_gate",  [{"name": "gate_c_prompt_sheet", "status": "pass", "findings": []}]),
>     ("unknown",     [{"name": "gate_d_script_language", "status": "skipped", "findings": []}]),
>     ("no_status",   [{"name": "gate_d_script_language", "findings": []}]),
>     ("skipped_only", [{"name": "gate_d_script_language", "status": "pass",
>                       "findings": [{"check": "D5", "beat": "SETUP", "kind": "skipped",
>                                     "message": "no computable time range"}]}]),
> ]
>
>
> @pytest.mark.parametrize("label,gates_block", GATE_MATRIX, ids=[c[0] for c in GATE_MATRIX])
> def test_the_page_flag_the_per_gate_tag_and_the_approve_decision_never_disagree(
>     tmp_path, monkeypatch, label, gates_block
> ):
>     """E-03's real mechanism, closed structurally. A never-ran gate rendered as
>     a clean pass; the approve form rendered WITHOUT the override field; clicking
>     Approve returned a bare 409 with no path forward. P15 now renders
>     gate_view[].blocking as a per-gate tag and has_blocking_gate as the
>     page-level flag, so there are three surfaces that must agree. They all read
>     one classifier; this asserts it."""
>     test_client, tmp_path, app = _scripting_client(tmp_path, monkeypatch)
>     project_id, run_dir = _new_project(test_client, app, tmp_path)
>     artifacts.write_artifact(
>         run_dir / "02-scripting", 1,
>         {"schema_version": 1, "stage": "shorts-scripting", "version": 1,
>          "status": "draft", "gates": gates_block},
>         "script body",
>     )
>
>     ctx = test_client.get(f"/projects/{project_id}/stages/scripting").context
>     page_flag = ctx["has_blocking_gate"]
>
>     assert page_flag == any(g["blocking"] for g in ctx["gate_view"])
>     approve = test_client.post(f"/projects/{project_id}/stages/scripting/approve")
>     assert (approve.status_code == 409) == page_flag, (
>         f"{label}: page says blocking={page_flag} but approve returned "
>         f"{approve.status_code}"
>     )
>     assert ('name="override_reason"' in test_client.get(
>         f"/projects/{project_id}/stages/scripting"
>     ).text) == page_flag
> ```
>
> `_scripting_client` does not exist anywhere in this plan or the live repo — write it as a
> fixture mirroring `two_stage_client`'s shape (a `pipeline.yaml` with an `ideation -> scripting`
> pipeline, `create_app(repo_root=tmp_path, ...)`, returning `(TestClient(app,
> follow_redirects=False), tmp_path, app)`), or substitute `two_stage_client` directly if its
> existing pipeline.yaml already satisfies this test's needs (it declares exactly `ideation ->
> scripting` — check whether that's sufficient before writing a near-duplicate fixture). Run this
> test after the `_stage_context`/`gate_view` wiring above, confirm all 8 parametrized cases pass,
> and include it in this task's own commit (or a separate `test(stages): assert the page flag,
> gate tag and approve decision never disagree` commit — your call).

---

### T20 — The `/edit` route's status is decided, and the page publishes its contract

*Closes A-84, E-07.*

- [ ] **Write the failing test** in `test_routes_stages.py`:

```python
def test_the_stage_page_publishes_the_hand_edit_contract(client):
    """A-84/E-07: `POST .../edit` mints a version, re-gates the body, propagates
    staleness and resets the stage -- 60 lines of carefully-reasoned behavior
    with no template posting to it anywhere in the repo. The route is KEPT (its
    four latent defects are closed by T2/T3/T4), so the server must hand the
    template everything it needs to render the form."""
    test_client, tmp_path, app = client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    artifacts.write_artifact(run_dir / "01-ideation", 1, {"stage": "shorts-ideation"}, "body")
    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    ctx = page.context  # TemplateResponse context, exposed by starlette's TestClient
    assert ctx["edit_allowed"] is True
    assert ctx["edit_action"] == f"/projects/{project_id}/stages/ideation/edit"
    assert ctx["edit_field"] == "body"


def test_grounding_never_offers_the_hand_edit_form(client):
    """The route already refuses grounding (its output lives in rgs-briefs/), so
    the page must not offer a form that can only 409."""
    ...  # assert ctx["edit_allowed"] is False and ctx["edit_blocked_reason"]


PUBLISHED_CONTEXT_KEYS = frozenset({
    "gate_view", "has_blocking_gate", "gate_override", "gate_overrides",
    "artifact_version", "artifact_created_at", "artifact_finalized_at",
    "inputs", "edit_allowed", "edit_blocked_reason", "edit_action", "edit_field",
    "error_banner",
})


@pytest.mark.parametrize("with_artifact", [True, False])
def test_every_published_context_key_is_present_on_every_render(client, with_artifact):
    """The contract test for §6. P15 binds templates to these names and Jinja
    renders a missing key as EMPTY -- so an absent key is not a crash, it is a
    blank panel. That is exactly how the first draft of this contract and P15's
    would have silently reimplemented E-03 (a never-ran gate rendering as a
    clean pass). A key that is sometimes absent is the same defect in slower
    motion, so this asserts presence on BOTH the has-artifact and no-artifact
    renders."""
    test_client, tmp_path, app = client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    if with_artifact:
        artifacts.write_artifact(
            run_dir / "01-ideation", 1,
            {"stage": "shorts-ideation", "version": 1, "status": "draft",
             "created_at": "2026-08-08T00:00:00+00:00", "finalized_at": None},
            "body",
        )
    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert PUBLISHED_CONTEXT_KEYS <= set(page.context)


def test_the_conflict_render_carries_the_same_context_keys_as_the_normal_one(two_stage_client):
    """The 409 body is the same template with the same keys -- differing only in
    error_banner being non-None. P15 binds to that unconditionally."""
    test_client, tmp_path, app = two_stage_client
    project_id, _run_dir = _new_project(test_client, app, tmp_path)
    resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/edit", data={"body": "sneaky edit"}
    )
    assert resp.status_code == 409
    assert PUBLISHED_CONTEXT_KEYS <= set(resp.context)
    assert resp.context["error_banner"]["kind"] == "conflict"


def test_the_stage_page_reports_which_artifact_version_is_on_screen(client):
    """P15's E-06: stage_page parsed the frontmatter into output_meta and then
    discarded it, so an operator could not tell v1 from v7, or whether the body
    had been regenerated since they last looked."""
    test_client, tmp_path, app = client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    artifacts.write_artifact(
        run_dir / "01-ideation", 1,
        {"stage": "shorts-ideation", "version": 1, "status": "draft",
         "created_at": "2026-08-08T00:00:00+00:00", "finalized_at": None},
        "v1 body",
    )
    artifacts.write_artifact(
        run_dir / "01-ideation", 2,
        {"stage": "shorts-ideation", "version": 2, "status": "final",
         "created_at": "2026-08-08T01:00:00+00:00",
         "finalized_at": "2026-08-08T02:00:00+00:00"},
        "v2 body",
    )
    ctx = test_client.get(f"/projects/{project_id}/stages/ideation").context
    assert ctx["artifact_version"] == 2
    assert ctx["artifact_created_at"] == "2026-08-08T01:00:00+00:00"
    assert ctx["artifact_finalized_at"] == "2026-08-08T02:00:00+00:00"
```

- [ ] **Run** → `KeyError`.
- [ ] **Implement, `routes/stages.py`** in `_stage_context`:

```python
    edit_blocked_reason = None
    if stage_id == "grounding":
        edit_blocked_reason = ("Grounding's output lives in rgs-briefs/ -- edit that file "
                               "directly, not through this app.")
    elif is_locked_or_running(stage_row["status"]):
        edit_blocked_reason = f"Stage is {stage_row['status']} and cannot be edited yet."
    ...
        "edit_allowed": edit_blocked_reason is None and output_body is not None,
        "edit_blocked_reason": edit_blocked_reason,
        "edit_action": f"/projects/{project_id}/stages/{stage_id}/edit",
        "edit_field": "body",
        # P15's E-06: these three were parsed into output_meta at :100 and then
        # thrown away, so the page could not say whether the body on screen was
        # v1 or v7. Lifted verbatim -- None means the key was absent, and
        # artifact_finalized_at is None is the reliable "still a draft" signal
        # (stage_status moves independently of it).
        "artifact_version": output_meta.get("version"),
        "artifact_created_at": output_meta.get("created_at"),
        "artifact_finalized_at": output_meta.get("finalized_at"),
        # Append-only per P2's A-38 fix; the singular is the most recent entry.
        "gate_overrides": overrides,
        "gate_override": overrides[-1] if overrides else None,
```

  where `overrides = artifacts.read_gate_overrides(latest) if latest is not None else []`
  (P2 §6.2). Before P2 lands, derive the same shape from `output_meta.get(
  "gate_override_reason")` as a single-entry list with `at=None`, and delete that shim in T23 —
  the key names and the `gate_override.reason` binding do not change either way, so P15 is
  never blocked on P2.

- [ ] **Run** → green. **Commit:** `feat(stages): publish the hand-edit form contract to the template`

---

### T21 — One input card per declared dependency, missing ones marked

*Closes E-05.*

- [ ] **Write three failing tests** in `test_routes_stages.py`:

```python
def test_a_missing_upstream_artifact_is_reported_not_dropped(tmp_path, monkeypatch):
    """E-05 FAULT: the `if up_latest is not None` guard skipped an absent
    dependency and the panel rendered the rest with no gap indicated. 'No
    upstream input.' appeared only when EVERY dependency was missing, so the
    operator reviewed a partial input believing it complete -- and the same
    partial context is what the turn was actually given."""
    ...  # assembly depends_on [voiceover, visual]; only voiceover has an artifact
    ctx = page.context
    assert [i["stage_id"] for i in ctx["inputs"]] == ["voiceover", "visual"]
    assert [i["present"] for i in ctx["inputs"]] == [True, False]


def test_a_missing_upstream_is_distinguishable_from_an_empty_one(tmp_path, monkeypatch):
    """E-05 DISTINGUISHABILITY: an upstream artifact with an empty body and an
    upstream artifact that does not exist are different facts."""
    ...  # write an artifact with body "" -> present is True, body is ""
         # assert the two cards differ on `present`, not only on `body`


def test_every_declared_dependency_appears_even_when_all_are_missing(tmp_path, monkeypatch):
    """E-05 SURFACING: the human-reachable signal is one card per declared
    dependency, always."""
    ...  # assert len(ctx["inputs"]) == 2 and all(not i["present"] for i in ctx["inputs"])
```

- [ ] **Run** → `KeyError: 'inputs'`.
- [ ] **Implement, `routes/stages.py`** in `_stage_context`, replacing lines 69–78:

```python
    # One card per DECLARED dependency, present or not (E-05). Concatenating only
    # the ones that resolved made a partial input look complete.
    inputs = []
    for dep_id in stage_def.depends_on:
        up_def = next(s for s in stage_defs if s.id == dep_id)
        up_latest = artifacts.latest_artifact_path(run_dir / stage_dir_name(up_def))
        body = None
        if up_latest is not None:
            _, body = artifacts.parse_frontmatter(up_latest.read_text(encoding="utf-8"))
        inputs.append({
            "stage_id": dep_id,
            "present": up_latest is not None,
            "malformed": False,          # set by T23's MalformedArtifactError handler
            "artifact": up_latest.name if up_latest is not None else None,
            "body": body,                # raw source text -- never rendered via `| safe`
            "html": _render(body),       # sanitized at the producer; see §6
        })
```

  `_render` is the markdown→`sanitize_html` helper defined in §6. Apply it to `output_html`
  and `grounding_input_html` in the same task — all four `_html` keys leave this module
  sanitized, so P15's `| safe` is safe by construction.

  Keep `input_body`/`input_html` populated from the present cards for one release so P15's
  template can migrate; both are removed by P15's task and this package's tests do not assert
  on them.

- [ ] **Run** → green. **Commit:** `fix(stages): render one input card per declared dependency`

---

### T22 — The app suite declares the repo-root paths it depends on

*Closes F-73.*

- [ ] **Write the failing test** in `test_gates.py`:

```python
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
```

- [ ] **Run** → passes immediately in a healthy checkout; prove it fails by temporarily
      renaming `docs/style-library.md` and confirming the message names the file, then
      rename it back. Record that observation in the commit body.
- [ ] **Commit:** `test(gates): declare the repo-root paths the app suite reads`

---

### T23 — Adopt P2's frozen `artifacts` API

*Closes no new finding.* Mechanical adoption of P2 §6.2/§6.3, sequenced after the finding work
so nothing above is blocked on P2's merge. Run **after** P2 lands.

- [ ] **Write the failing tests** in `test_approval_service.py` and `test_routes_stages.py`:

```python
def test_an_override_on_an_already_final_artifact_is_timestamped(conn, tmp_path):
    """P2 A-38: record_gate_override's `at` is required and keyword-only. The
    already-final branch deliberately skips stamp_final, so before this the
    override carried NO timestamp at all -- only stages.approved_at moved, and
    nothing linked the two."""
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    path = _write_artifact_with_gates(stage_dir, "fail")
    meta, body = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    meta["status"] = "final"
    path.write_text(artifacts.render_frontmatter(meta, body), encoding="utf-8")

    approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting",
                  override_reason="verified by hand")

    overrides = artifacts.read_gate_overrides(path)
    assert len(overrides) == 1
    assert overrides[0]["reason"] == "verified by hand"
    assert overrides[0]["at"].endswith("+00:00")


def test_a_malformed_artifact_is_a_409_naming_the_file_not_a_500(client):
    """P2 A-68/A-69: parse_frontmatter RAISES MalformedArtifactError now instead
    of returning ({}, text) and masking a truncated artifact as an unversioned
    one. A MalformedArtifactError reaching the operator as a bare 500 is a
    regression, not a fix."""
    test_client, tmp_path, app = client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    stage_dir = run_dir / "01-ideation"
    stage_dir.mkdir(parents=True)
    (stage_dir / "artifact.v1.md").write_text("---\nstage: x\nbody with no closing fence\n",
                                              encoding="utf-8")

    resp = test_client.post(f"/projects/{project_id}/stages/ideation/approve")
    assert resp.status_code == 409
    assert "artifact.v1.md" in resp.text
    row = app.state.conn.execute(
        "SELECT * FROM events WHERE kind = 'artifact.malformed'"
    ).fetchone()
    assert row["severity"] == "error"


def test_a_malformed_artifact_renders_the_stage_page_rather_than_blanking_it(client):
    """The GET path: stage_page:100 parses the same file. A malformed artifact
    must show as an explicit banner, not as a stage with no output -- which is
    indistinguishable from a stage that never ran."""
    ...  # GET returns 200 with error_banner["kind"] == "malformed_artifact"
```

- [ ] **Run** → fails (`TypeError: record_gate_override() missing 'at'`; 500s on the malformed
      artifact).
- [ ] **Implement:**
  - `approval_service.py:76` → `artifacts.record_gate_override(latest, override_reason, at=now)`.
  - `approval_service.py:43` → wrap the `parse_frontmatter` call:

```python
    try:
        latest_meta, _ = artifacts.read_artifact(latest)
    except artifacts.MalformedArtifactError as exc:
        obs.record_event(
            conn, kind="artifact.malformed", severity="error", source="approval_service",
            message=f"cannot approve '{stage_id}': {exc.path.name} is malformed ({exc.reason})",
            detail={"project_id": project_id, "stage_id": stage_id, "path": str(exc.path)},
        )
        raise ValueError(
            f"Stage '{stage_id}': {exc.path.name} is not a readable artifact ({exc.reason}). "
            "Fix the file or regenerate the stage."
        ) from exc
```

  - `routes/stages.py:100` (the output read) and the `inputs` loop from T21 → catch
    `MalformedArtifactError` per artifact, set `error_banner={"kind": "malformed_artifact", ...}`
    for the output and mark the input card `{"present": True, "malformed": True}` rather than
    dropping it (the E-05 rule applies to unreadable upstreams too).
  - Add `"malformed": bool` to the `inputs` card contract in §6.
- [ ] **Run** → green. **Commit:** `fix(stages): adopt P2's artifact API — timestamped overrides, malformed-artifact handling`

---

### T24 — Adopt P2's frozen `grounding_service` API

*Closes no new finding.* P2 §6.2/§6.3 items 1 and 2. Run **after** P2 lands.

- [ ] **Write the failing tests** in `test_routes_stages.py`:

```python
def test_a_grounding_turn_that_identifies_no_brief_records_why(client):
    """P2 A-81: identify_new_brief is deleted; classify_brief_change returns a
    BriefChange carrying `reason`, `added` and `modified`. The no_artifact branch
    used to discard all of it, so 'the skill wrote nothing' and 'the skill
    modified an existing brief in place' were the same silent outcome."""
    ...  # assert an events row kind="grounding.brief_not_identified", severity="warning",
         # whose message is change.reason and whose detail carries added/modified


def test_a_downstream_rgs_stage_does_not_inject_a_stale_grounding_pointer(client):
    """P2 A-80: stage_chat injected grounding_pointer into every downstream RGS
    kickoff with NO existence check. verify_pointer's state gates it."""
    ...  # write a pointer whose target is deleted; assert the kickoff prompt omits it
         # and an events row kind="grounding.pointer_invalid" exists
```

- [ ] **Run** → fails (`AttributeError: identify_new_brief`; `TypeError: write_pointer()`).
- [ ] **Implement, `routes/stages.py`** exactly as P2 §6.3 items 1 and 2 specify: swap
      `identify_new_brief` for `classify_brief_change`, pass `repo_root` to `write_pointer`, and
      gate the `grounding_pointer` injection at `:157-160` on
      `verify_pointer(grounding_dir, repo_root).state == "ok"`, recording an event and surfacing
      staleness on `hash_mismatch` / `missing_target`.
- [ ] **Adopt P4 §7.4's two one-line asks in the same file** (both are P4 findings whose call
      site is P3's; neither changes P3's finding count):
  - `routes/stages.py:287` — `propagate_staleness(...)` gained an optional `repo_root=`.
    Pass `repo_root=repo_root`; that is what closes **A-14** on the hand-edit path.
  - the grounding branch (≈`:186`) — after `write_pointer(...)`, call
    `turn_service.propagate_grounding_staleness(conn, repo_root, run_dir, stage_defs, project_id)`
    so a re-pointed brief invalidates downstream immediately rather than one turn late.
- [ ] **Run** → green. **Commit:** `fix(stages): adopt P2's grounding_service API and P4's staleness keywords`

> **Not adopted here:** P4 §7.4 also flags that `preflight.py:38-40` re-derives status from
> artifact existence and so launders `stale` (A-46's other half), needing a persisted
> pre-`running` status on the turn row. **A-46 is not in P3's finding set** and the fix requires
> a turn-row schema change P3 does not own. Task 17 leaves that re-derivation exactly as it
> found it and adds only the event and the quarantine. Routed back to A-46's owner.

---

## 4. Finding → test map

`Silent` findings carry all three Three-Test-Rule roles. `F` = fault, `D` = distinguishability,
`S` = surfacing.

| Finding | Mode | Test(s) | Role |
|---|---|---|---|
| A-30 | silent | `test_every_production_gate_call_site_passes_a_resolved_upstream_map` | F (static) |
| | | `test_hand_editing_a_visual_sheet_is_gated_against_the_styleboards_world_lock` | F |
| | | `test_the_edit_path_and_a_direct_gate_run_produce_identical_results` | D |
| | | `test_run_gates_for_stage_refuses_to_be_called_without_an_upstream_map` | S (TypeError at the call) |
| A-31 | loud | `test_the_empty_world_error_names_the_styleboard_and_carries_a_check_id` | — |
| A-33 | coverage-gap | `test_a_styleboard_with_no_world_lock_fails_its_own_gate`, `test_a_styleboard_missing_a_key_gate_c_reads_fails_its_own_gate`, `test_the_passing_styleboard_fixture_passes_its_own_gate`, `test_a_styleboard_slot_value_shaped_like_an_invented_code_fails`, `test_a_styleboard_label_naming_no_library_entry_fails_here_not_downstream` | — |
| A-35 | silent | `test_an_unrecognized_gate_status_blocks_approval` | F |
| | | `test_an_unrecognized_status_is_distinguishable_from_a_failure` | D |
| | | `test_an_unrecognized_status_records_an_event` | S |
| A-36 | loud | `test_a_malformed_gates_frontmatter_value_raises_valueerror`, `test_approve_route_returns_409_not_500_for_a_malformed_gates_block` | — |
| A-39 | silent | `test_a_blank_override_reason_does_not_release_a_failing_gate` | F |
| | | `test_a_blank_override_reason_is_never_recorded_on_the_artifact` | D |
| | | `test_an_override_reason_is_stored_stripped` | S |
| A-40 | latent | `test_a_linter_calling_sys_exit_is_an_error_not_an_escape`, `test_genuine_cancellation_is_re_raised_not_swallowed` | — |
| A-41 | loud | `test_a_failed_gate_run_leaves_no_scratch_file_behind`, `test_an_edit_whose_gate_escapes_is_recorded_as_an_event` | — |
| A-42 | latent | `test_a_linter_is_loaded_once_per_repo_root_and_module`, `test_a_failed_linter_exec_does_not_leave_a_broken_module_registered` | — |
| A-45 | silent | `test_hand_editing_an_approved_stage_relocks_a_dependent_with_no_artifact` | F |
| | | `test_a_dependent_that_has_its_own_artifact_goes_stale_rather_than_locked` | D |
| | | `test_a_relock_is_recorded_as_an_event` | S |
| A-60 | silent | `test_first_ever_hand_edit_records_a_real_depends_on` | F |
| | | `test_a_hand_edited_stage_with_no_prior_artifact_still_goes_stale` | D |
| | | `test_a_hand_edit_after_the_upstream_advanced_records_the_current_version` | S |
| A-62 | silent | `test_hand_editing_a_visual_sheet_is_gated_against_the_styleboards_world_lock` | F |
| | | `test_the_edit_path_and_a_direct_gate_run_produce_identical_results` | D |
| | | `test_every_production_gate_call_site_passes_a_resolved_upstream_map` | S (static, names file:line) |
| A-64 | silent | `test_a_hand_edit_does_not_touch_the_turn_paths_raw_output` | F |
| | | `test_a_failed_gate_run_leaves_no_scratch_file_behind` | D |
| | | `test_an_edit_whose_gate_escapes_is_recorded_as_an_event` | S |
| A-77 | silent | `test_reconcile_records_an_event_naming_the_project_and_stage` | F |
| | | `test_an_orphaned_stage_is_distinguishable_from_a_healthy_awaiting_review` | D |
| | | `test_the_dead_turns_raw_output_is_quarantined_not_left_as_the_next_baseline` | S |
| A-84 | coverage-gap | `test_the_stage_page_publishes_the_hand_edit_contract`, `test_grounding_never_offers_the_hand_edit_form` | — |
| E-04 | loud | `test_a_gate_block_re_renders_the_stage_page_with_a_banner`, `test_a_locked_stage_edit_re_renders_with_a_banner`, `test_the_grounding_edit_refusal_keeps_its_message` | — |
| E-05 | silent | `test_a_missing_upstream_artifact_is_reported_not_dropped` | F |
| | | `test_a_missing_upstream_is_distinguishable_from_an_empty_one` | D |
| | | `test_every_declared_dependency_appears_even_when_all_are_missing` | S |
| E-07 | latent | `test_the_stage_page_publishes_the_hand_edit_contract` | — |
| F-17 | coverage-gap | `test_hand_editing_a_visual_sheet_is_gated_against_the_styleboards_world_lock`, `test_the_edit_path_and_a_direct_gate_run_produce_identical_results`, `test_hand_editing_a_styleboard_runs_the_styleboard_gate` | — |
| F-19 | coverage-gap | `test_app_and_cli_gate_c_report_identical_findings` (4 params), `test_the_only_gate_c_divergence_is_the_empty_world_lock_input_error` | — |
| F-28 | silent | `test_a_stage_id_no_longer_in_pipeline_yaml_is_reported` | F |
| | | `test_an_unwedge_skip_is_distinguishable_from_a_successful_unwedge` | D |
| | | `test_each_defensive_return_names_which_one_fired` (3 params) | S |
| F-73 | latent | `test_the_app_suite_declares_the_repo_root_paths_it_reads` | — |

---

## 5. Tests deleted or inverted

| File:line | Test | Action | Replacement |
|---|---|---|---|
| `pipeline-app/tests/test_gates.py:129-137` | `test_visual_gate_without_a_styleboard_uses_a_legacy_sheets_own_world_lock` | **Rewritten, not deleted.** F-19 records that it "sanctions the empty-upstream branch A-30/A-62 show every hand edit silently takes" — the branch is legitimate for a genuine pre-split sheet and illegitimate for a hand edit. **Also carries the confirmed Handoff-H1b/T21R-01 regression** (P11's C8 object-count floor now legitimately fires on this fixture's Hook shot) — see T2's own step for the narrowed assertion. | Rename to `test_a_legacy_sheet_with_no_styleboard_upstream_uses_its_own_world_lock`; pass `{}` **explicitly** (T2 makes the default impossible); narrow the `"C8" not in checks` assertion to the sport-naming sub-check only (see T2); and add to the docstring: "Legitimate only for a pre-split sheet. The hand-edit path may never reach this branch — `test_every_production_gate_call_site_passes_a_resolved_upstream_map` is what forbids it. The object-count sub-check of C8 is a separate, unrelated concern (T21R-01) and is not asserted here." |
| `pipeline-app/tests/test_gates.py:25,33,46,65,76,87,99` | seven 3-argument `run_gates_for_stage` calls | **Amended.** Each currently exercises the `upstream=None` default that T2 deletes. | Pass an explicit `{}`; the scripting gate genuinely has no upstream and now says so at the call site. |
| `pipeline-app/tests/test_gates.py:114` | `_visual_gate(sheet, upstream=None)` | **Amended.** Default changes `None` → `{}`. | Same signature, no `None` path. |
| `pipeline-app/tests/test_routes_approve_edit.py:50-110` | `test_hand_edit_flips_stage_to_awaiting_review_and_dependent_to_stale` | **Amended.** It hand-writes `depends_on` into scripting's frontmatter to make the cascade fire — a workaround for A-60 that T3 removes the need for. | Drop the hand-written `depends_on` block and let the edit route compute it; the assertion (`scripting` → `stale`) is unchanged and now proves the real path. |
| `pipeline-app/tests/test_routes_stages.py:389-430` | `test_approve_route_blank_override_field_does_not_count_as_override` | **Kept, re-anchored.** Its docstring credits the route's `.strip() or None`, which T12 moves into `approve_stage`. | Update the docstring to name `approve_stage` as the owner of the invariant; keep the end-to-end assertions as the proof that the route still honours it. |
| `pipeline-app/tests/test_approval_service.py:300-332` | `_write_artifact_with_gates(stage_dir, status)` helper | **Amended.** It cannot express an absent or non-string `status`, which is exactly A-35/A-36's input space. | Accept `status: str \| None` and a `gates_value` escape hatch that writes the raw frontmatter value. |

No test in this package's files asserts a defect is correct outright, so nothing is deleted
wholesale. The `grep -rn "returns_empty_on_fetch_failure\|scoped_permissions_settings_scopes"`
check in the programme's verification section does not touch these files.

---

## 6. Contract for P15 (stage page)

P3 owns the server-side state and the HTTP semantics; P15 owns the markup. These are the keys
`stage.html` may bind to. They are produced by `_stage_context()` in
`pipeline-app/pipeline_app/routes/stages.py` and are present on **every** stage-page render,
including the 409 re-renders.

> **Naming is settled by orchestrator ruling.** P15's first draft bound to `gate_states`,
> `approval_blocked`, `approval_block_reasons`, `approval_error` and ad-hoc `output_meta`
> lookups — zero overlap with the names below. Jinja renders a missing key as empty, so that
> mismatch would have rendered **nothing** for gate state and reimplemented E-03: a never-ran
> gate looking like a clean pass, with no override field and no way forward from inside the UI.
> The names in this section are canonical; P15 conforms to them. None of them is optional and
> none is ever absent from the context.

### Gate state

```python
gate_view: list[dict]        # one entry per gate, in registry order, never empty when
                             # the stage has registered gates
```

Each entry:

| Key | Type | Values |
|---|---|---|
| `name` | `str` | e.g. `gate_c_prompt_sheet`, `gate_d_script_language`, `gate_s_styleboard` |
| `state` | `str` | exactly one of `"passed"`, `"failed"`, `"errored"`, `"never_ran"`, `"unknown"` |
| `status_raw` | `str \| None` | the literal value recorded in frontmatter; `None` when the gate never ran. Render it verbatim for `state == "unknown"` |
| `blocking` | `bool` | `True` for every state except `"passed"`. This is the flag the approve form keys on |
| `findings` | `list[dict]` | each `{check, beat, shot_index, kind, message}`; `kind == "skipped"` is a known unknown, styled distinctly, **not** blocking |

Derivation, so P15 never has to recompute it:

- `"passed"` — recorded `status == "pass"`.
- `"failed"` — recorded `status == "fail"`.
- `"errored"` — recorded `status == "error"` (the gate could not run; `findings[0].check` is
  `"C0"` when the *input* was unusable and `"GATE"` otherwise).
- `"never_ran"` — the gate is in `GATE_REGISTRY[stage_id]` and no entry with that `name`
  appears in the artifact's `gates` block. **This is the case that previously rendered as a
  clean pass** (nothing at all was shown) while `approve_stage` blocked on it — the E-03 dead
  end. It must render as blocking.
- `"unknown"` — an entry exists with a `status` outside `{pass, fail, error}` (A-35).

```python
has_blocking_gate: bool      # LITERALLY any(g["blocking"] for g in gate_view) -- see below
```

**Answer to P15's question 1: yes, and it is stronger than that.** `has_blocking_gate` is
computed as `any(g["blocking"] for g in gate_view)` and from nothing else — one expression, one
line, no second reading of the frontmatter. But two flags derived from one list can still drift
from the *approval decision*, which is the actual E-03 mechanism: `has_failing_gate` did not
disagree with itself, it disagreed with `approve_stage`. So all three come from a single
classifier:

```python
# pipeline_app/approval_service.py -- the ONE place a gate result is judged.
def classify_gates(stage_id: str, recorded: list[dict]) -> list[dict]:
    """One entry per gate, carrying the `state` and the `blocking` verdict.

    Both the approve decision (approve_stage) and the stage page (gate_view) call
    this. They used to decide independently -- approve_stage consulted
    GATE_REGISTRY for a never-ran gate while stage_page's has_failing_gate only
    looked for fail/error -- so a never-ran gate rendered as a clean pass with no
    override field, and clicking Approve produced a 409 with no way forward from
    inside the UI (E-03). A per-gate tag that disagrees with a page-level flag,
    or with the 409, is the same bug wearing a different name. There is one
    judgement here and everything else reads it.
    """
```

`approve_stage` blocks iff `any(g["blocking"] for g in classify_gates(...))` and no override is
supplied; `_stage_context` sets `gate_view = classify_gates(...)` and
`has_blocking_gate = any(...)` over that same list. The invariant is asserted directly, not
inferred — see `test_the_page_flag_the_per_gate_tag_and_the_approve_decision_never_disagree`
(T10), which sweeps a matrix of recorded `gates` blocks and asserts all three agree on every
one.

**Replaces `has_failing_gate`, which is removed.** `has_failing_gate` only saw `fail`/`error`,
so on a never-ran or unknown gate the approve form rendered *without* the override field: click
Approve, get a 409, go back, repeat, with no path forward from inside the UI. Bind the override
input to `has_blocking_gate`. `output_gates` (the raw list) stays available for one release and
is then removed; prefer `gate_view`.

### Override state

```python
gate_overrides: list[dict]   # every recorded override, oldest first; [] when none.
                             # Each: {"reason": str, "at": str, "actor": str | None}
gate_override: dict | None   # the MOST RECENT entry, or None when the list is empty.
                             # P15 binds gate_override.reason / .at / .actor
```

Sourced from P2's `artifacts.read_gate_overrides(latest)` (P2 §6.2/§6.4), which is why the
list is authoritative and the singular is a convenience: A-38 made overrides **append-only**,
so an artifact overridden twice with different reasons keeps both. Render `gate_override`
next to the failing gate it excuses; render the full `gate_overrides` list wherever history
matters. Both keys are present on every render — `gate_override` is `None`, never missing.
`at` is always an aware-UTC ISO 8601 string (P2's `record_gate_override` requires `at=`; the
old untimestamped already-final path is gone).

### Artifact identity

```python
artifact_version: int | None        # e.g. 7; None when the stage has no artifact yet
artifact_created_at: str | None     # aware-UTC ISO 8601, from the artifact's frontmatter
artifact_finalized_at: str | None   # aware-UTC ISO 8601; None while the artifact is a draft
```

Added at P15's request (its E-06): `stage_page` already parsed the artifact's frontmatter into
`output_meta` and then **discarded** it, so the heading read `run_id — stage_id` and an
operator could not tell whether the body on screen was v1 or v7, or whether it had been
regenerated since they last looked. These three are lifted straight from the parsed
frontmatter (`version`, `created_at`, `finalized_at`) with no reinterpretation; a `None` means
the key was absent, not that it was empty. `artifact_finalized_at is None` is the reliable
"this is still a draft" signal — do not infer it from `stage_status`, which moves
independently.

`output_meta` itself is **not** published. P15 must not re-derive fields from it; if something
else is needed from the frontmatter, P3 adds a named key rather than exposing the raw dict —
that is how the `gates`-shape bugs (A-35, A-36) got in.

### Input panel

```python
inputs: list[dict]           # one entry per DECLARED dependency, in pipeline.yaml order,
                             # present or not
```

Each: `{"stage_id": str, "present": bool, "malformed": bool, "artifact": str | None,
"body": str | None, "html": str | None}`. Render an explicitly "missing" card when
`present is False` and an explicitly "unreadable" card when `malformed is True` (T23 — a
dependency whose artifact raises `MalformedArtifactError` is present-but-unusable, a third
state that must not collapse into either of the other two). The old `input_body` /
`input_html` pair silently omitted every absent dependency. Both legacy keys remain populated
from the present cards for one release and then go.

### Hand-edit form

```python
edit_allowed: bool           # render the form only when True
edit_blocked_reason: str | None
edit_action: str             # "/projects/{id}/stages/{sid}/edit"
edit_field: str              # "body" — the single form field name the route reads
```

`edit_allowed` is `False` for `grounding` (its output lives in `rgs-briefs/`), for a
locked/running stage, and when the stage has no output yet. Posting anything else to
`edit_action` is a 409, so the form must not be rendered in those states.

### HTML sanitization — the producer sanitizes (P15's question 2, answer: **(a)**)

**Every `_html` key P3 puts in the context is already sanitized. P15 renders it through
`| safe` directly and adds no filter of its own.**

`_stage_context` passes each markdown-rendered string through P15's published
`browse_service.sanitize_html(html: str) -> str` (stdlib `html.parser` allowlist, no new
dependency — `requirements.txt` is P0's and gains nothing) before it enters the context. That
covers all four producers in `routes/stages.py`: `inputs[].html`, `output_html`,
`grounding_input_html`, and `input_html` for as long as the legacy key survives.

```python
from pipeline_app.browse_service import sanitize_html

def _render(body: str | None) -> str | None:
    """Markdown -> sanitized HTML. Artifact bodies are model-generated and
    hand-editable, so `markdown.markdown` output is untrusted by construction:
    a raw <script> or an onerror= attribute in a pasted prompt sheet reaches the
    template's `| safe` otherwise. Sanitizing at the PRODUCER means a new
    consumer (an htmx fragment, a partial, a future panel) cannot forget."""
    return sanitize_html(markdown.markdown(body)) if body else None
```

**Why (a) and not (b).** A consumer-side filter has to be reapplied at every `| safe` site, and
a missed one fails open and silently — the same shape as every other finding in this audit. The
producer side has a bounded, greppable set of sites. It also makes the rule uniform: P15 lists
`routes/inspector.py:45` (**P5**) as the other `| safe` producer, so **P5 follows the same
rule** — sanitize before the context, and `| safe` in a template means "this value was
sanitized by whoever produced it," with no exceptions. Nothing in this repo may put unsanitized
HTML behind `| safe`.

Test, in `test_routes_stages.py` (T21):

```python
def test_a_script_tag_in_an_upstream_artifact_does_not_reach_the_context(tmp_path, monkeypatch):
    """Artifact bodies are model-generated and hand-editable; stage.html renders
    inputs[].html through `| safe`. Sanitize at the producer so no consumer has
    to remember."""
    ...  # upstream body: '<script>alert(1)</script>\n\nnormal text'
    assert "<script>" not in ctx["inputs"][0]["html"]
    assert "normal text" in ctx["inputs"][0]["html"]
    assert "<script>" not in ctx["output_html"]
```

`inputs[].body` is the **unsanitized** source text and is not for rendering as HTML — it exists
for `<pre>`/textarea use and for tests. Do not put `body` behind `| safe`.

### Error banner

```python
error_banner: dict | None    # {"kind": str, "message": str}; None on a normal GET
```

`kind` is one of `"conflict"` (locked/running/busy), `"gate_block"`, `"grounding_refused"`,
`"malformed_artifact"` (T23), `"grounding_pointer_invalid"` (T24). Render it at the top of the
page; the message is operator-facing prose and is safe to show verbatim.

**Confirmed for P15, explicitly:** a blocked approve POST returns **`409` by re-rendering
`stage.html`** through `_stage_conflict()` — full page, full context, `error_banner`
populated, `has_blocking_gate` `True`. It is **not** a `PlainTextResponse`; every
`PlainTextResponse` in `routes/stages.py` is deleted by T19 and the verification step greps to
prove it. P15 may bind to that unconditionally: the 409 body is the same template with the
same context keys as the 200, differing only in `error_banner` being non-`None`.

### HTTP status codes P15 can rely on

| Route | Success | Failure | Body on failure |
|---|---|---|---|
| `GET /projects/{id}/stages/{sid}` | `200` | `404` unknown project / unknown stage / stage not applicable to brand | FastAPI `HTTPException` detail |
| `POST .../approve` | `303` → the stage page | **`409`** for: no artifact, stage locked or running, failing gate, errored gate, gate that never ran, gate with an unrecognized status, malformed `gates` block, blank override supplied against a block | **`text/html`** — the full stage page re-rendered with `error_banner` and `has_blocking_gate=True`, status `409` |
| `POST .../edit` | `303` → the stage page | **`409`** for: `grounding`, stage locked or running, a gate that escaped | `text/html`, same shape |
| `POST .../chat` | `200` SSE | **`409`** for: stage locked or running, another turn already running | `text/html`, same shape |

There is **no `500`** on any of these paths after this package lands: A-36 (malformed `gates`)
and A-41 (an escaped gate) were the two that produced one, and both are now `409`. A `500` from
these routes is a bug, not a state P15 needs to design for.

---

## 7. Verification

- [ ] `cd pipeline-app && python -m pytest -q` — green.
- [ ] `cd .. && python -m pytest tests/ -q` — green (this package touches no root-suite file,
      but T6/T8/T9 change how `scripts/lint_prompt_sheet.py` is *called*, never what it does).
- [ ] `python - <<'PY'` sanity: `ast`-scan proves exactly two production
      `run_gates_for_stage` call sites, both passing a resolved map.
- [ ] `grep -rn "PlainTextResponse" pipeline-app/pipeline_app/routes/stages.py` returns nothing —
      this is what P15 binds its 409 handling to.
- [ ] `grep -rn "has_failing_gate" pipeline-app/` returns only P15's template migration.
- [ ] `grep -n "markdown.markdown" pipeline-app/pipeline_app/routes/stages.py` returns nothing
      outside `_render` — every markdown render in this module goes through `sanitize_html`.
- [ ] `has_blocking_gate` appears exactly once in `routes/stages.py`, as
      `any(g["blocking"] for g in gate_view)`. A second derivation is the E-03 mechanism.
- [ ] `grep -rn "next_version_number\|identify_new_brief" pipeline-app/pipeline_app/routes/ pipeline-app/pipeline_app/approval_service.py`
      returns nothing — both are superseded by P2's frozen API (T4, T24).
- [ ] `grep -rn "resolve_upstream_by_stage\|depends_on_records" pipeline-app/pipeline_app/artifacts.py`
      returns nothing — those two names were never P2's; the resolver lives in `gates.py`
      (Assumption A1) and the `depends_on` builder is `artifacts.compute_depends_on`.
- [ ] Every key in §6 is asserted present by at least one test: `gate_view`,
      `has_blocking_gate`, `gate_override`, `gate_overrides`, `artifact_version`,
      `artifact_created_at`, `artifact_finalized_at`, `inputs`, `edit_allowed`,
      `edit_blocked_reason`, `edit_action`, `edit_field`, `error_banner`. A key P15 binds to
      that no P3 test asserts is how mismatch 1 happened; do not reintroduce it.
- [ ] Every finding in §2 has at least one test in §4 observed failing before its fix.
