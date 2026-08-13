# P2 — Artifact Durability

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. The parent [orchestration plan](../2026-08-08-audit-remediation.md)'s **Global Constraints**, **test standard** and **Frozen interfaces** sections are binding on every task here and are not restated.

**This package carries 3 of the audit's 4 S0 (data-destroying) findings.** Execute it first in Wave B.

**Prerequisite:** Wave A (P0, P1) is complete. This plan calls `obs.log()` and `obs.record_event()` exactly as frozen in the orchestration plan, and relies on `tests/conftest.py` existing.

---

## 0. Pre-review amendments (2026-08-12, before T1 dispatch)

Adversarial pre-review against the actual current source (`artifacts.py`, `grounding_service.py`,
`migrations.py`, and their three test files) plus empirical probes of `os.replace` (with T1's exact
`tempfile.mkstemp` naming scheme) and `O_CREAT|O_EXCL` on this host confirmed both platform claims in
§T1/§T5 hold. `compile_plan.py` baseline for this plan: 42 python blocks, 36 compile, 6 fail — all six
are non-executable fragments (T12's docstring-only snippet, T14's except-clause insert, and §6's
signature-only contract blocks for P3/P4), none inside a standalone "Implement" block. All test/line
citations against the pre-existing three files were verified byte-accurate (e.g. `artifacts.py:88`,
`:105`; `test_grounding_service.py:22-50`).

Five real defects found and fixed here, before any dispatch:

1. **T5 ↔ T6 circular forward-reference.** T5's `reserve_version` reads `candidate = _high_water_mark(stage_dir) + 1`
   and calls `_record_high_water_mark(...)` — both defined only in T6, which runs *after* T5 in this
   plan's strict numeric order. Simultaneously, T6's own tests call `reserve_version(tmp_path)` (T5's
   function). Neither task can be implemented standalone as written. **Fix:** T5's `reserve_version`
   now seeds `candidate = next_version_number(stage_dir)` — the pre-existing helper, not the
   not-yet-defined `_high_water_mark`. `next_version_number` currently does exactly
   `max(existing versions on disk, default 0) + 1`, semantically equivalent for T5's own tests (none
   of which exercise post-deletion HWM survival — that's T6's job). Because T5 calls
   `next_version_number()` rather than reimplementing the max-scan inline, T6's later redefinition of
   `next_version_number` (to route through `_high_water_mark`) upgrades `reserve_version`'s behaviour
   automatically, with **no further edit to `reserve_version` needed** when T6 lands. The
   `_record_high_water_mark(stage_dir, candidate)` call in T5 is satisfied by T2's stub (next point) —
   it no-ops until T6 replaces the stub with the real sidecar-file writer.
2. **T2's `_record_high_water_mark` stub is now REQUIRED, not conditional.** T2's text said "stub it
   ... only if T6 is not executed in the same sitting". This programme executes strictly T1→T18, so T6
   is never immediately after T2. T2 **must** add `def _record_high_water_mark(stage_dir: Path, version: int) -> None: pass`
   (module-level, above or below `write_artifact`) so `write_artifact`'s call to it — and T5's, per
   point 1 — no-ops safely until T6 replaces the stub body outright (same name, same module: T6
   overwrites the stub, it does not add a second definition).
3. **T8's `parse_frontmatter` forward-references T9's `_load_frontmatter_yaml`** via a bare `# T9`
   comment on the line `meta = _load_frontmatter_yaml(yaml_text)`. T8's own acceptance test
   `test_empty_frontmatter_block_is_still_an_empty_mapping` (`"---\n---\n\nbody"`) reaches that exact
   line and would raise `NameError` if dispatched before T9 defines the helper. **Fix:** T8's
   `parse_frontmatter` body uses `meta = yaml.safe_load(yaml_text) or {}` instead — byte-identical to
   what the pre-existing code already does on that line, so T8 needs no new symbol. T9 then replaces
   that one line with `meta = _load_frontmatter_yaml(yaml_text)` and defines the function, exactly as
   T9's own section already shows. This keeps every task's dispatch self-contained and independently
   testable, and removes the plan's own "land together in the body, commit separately" ambiguity.
4. **T14 must add `from pipeline_app import obs` to `migrations.py`'s imports.** Verified against the
   current file: `migrations.py` imports only `artifacts, db as db_mod` — no `obs`. T14's own
   `obs.record_event(...)` call needs it. Not shown in the plan's T14 text; added here so the
   implementer isn't left to discover it via `NameError`.
5. **T15 must add `from pipeline_app import obs` to `grounding_service.py`'s imports.** Same gap:
   current file imports only `hashlib`, `Path`, `yaml`. T15's `verify_pointer` calls
   `obs.log("grounding.pointer_unpinned", ...)`.

T17's path-containment logic (`PureWindowsPath`/`PurePosixPath` absolute-detection plus `".." in parts`
plus the `rgs-briefs` root check) was probed against all 6 of its own test cases on this host and
produces the exact `RAISE`/no-raise verdict the tests expect — no amendment needed there.

**Open finding (filed, not fixed) — found by T11's task review, 2026-08-12:** `_adoptable_synthetic`'s
read (checking whether an existing artifact is our own prior synthetic) and `reserve_version`'s
reservation are not atomic with each other ACROSS PROCESSES. Two separate OS processes both running
`backfill_styleboard_rows` concurrently against the same `stage_dir` (e.g. a multi-worker uvicorn
deployment where both workers race app startup) could both pass the `_adoptable_synthetic` check
before either has written anything, then both proceed to `reserve_version`/write — `reserve_version`'s
`O_CREAT|O_EXCL` exclusivity means only one wins the SAME version number, but the loser does not
retry `_adoptable_synthetic` against the winner's now-present output, so it could reserve and write a
SECOND styleboard artifact at a higher version instead of erroring or adopting. **T12 (A-73, 2/2) does
NOT close this** — T12's own scope (see its section below) is a same-process crash-then-retry test
(`test_a_crash_between_the_artifact_write_and_the_db_row_does_not_churn_the_artifact`), not
cross-process locking; its own text says "the adoption branch from T11 already does the work; this
task adds the reasoning to `_backfill_one_project`'s docstring." Not fixed here: the current
deployment is single-process (no multi-worker uvicorn configuration exists in this repo today), so
this is a narrow, latent gap, not a live S0 — but it is real and currently owned by no task in this
plan. Flag to the final whole-branch review for a decision (accept as a documented limitation of the
lock-free sidecar design, or file a follow-up task).

**Amendment 2 (found by T9's implementer, during T9, not pre-review):** T9 makes `parse_frontmatter`
raise `MalformedArtifactError` for malformed YAML instead of letting `yaml.YAMLError` propagate.
`migrations.py`'s `_PER_PROJECT_RECOVERABLE = (OSError, UnicodeDecodeError, yaml.YAMLError)` — this
package's OWN file, unlike the expected cross-package breakage in `routes/stages.py` et al. — no
longer catches the new exception type, so a malformed legacy artifact now CRASHES the whole backfill
migration instead of being skipped per-project (worse than before this task, not better). This broke
`tests/test_migrations.py::test_backfill_skips_a_broken_legacy_project_without_blocking_others`, a
PRE-EXISTING test that was green before T9. T11's own text already plans to add
`artifacts.MalformedArtifactError` to `_PER_PROJECT_RECOVERABLE` (alongside `BackfillWouldOverwriteError`,
which doesn't exist until T11) — but leaving this package's own file broken for two more tasks
violates the same standard applied everywhere else in this programme (an untracked broken test in a
file this package owns is not acceptable, unlike genuinely cross-package fallout). **Pulled forward
into T9's own task**, since T9 is what caused it: add `artifacts.MalformedArtifactError` to
`_PER_PROJECT_RECOVERABLE` now. T11 still adds `BackfillWouldOverwriteError` to the same tuple when
that class is defined — do not remove or duplicate the earlier addition.

---

## 1. Scope

### Files this package owns (no other package may touch these)

```
pipeline-app/pipeline_app/artifacts.py
pipeline-app/pipeline_app/migrations.py
pipeline-app/pipeline_app/grounding_service.py
pipeline-app/tests/test_artifacts.py
pipeline-app/tests/test_migrations.py
pipeline-app/tests/test_grounding_service.py
```

### Finding IDs (15)

A-37, A-38, A-61, A-63, A-65, A-66, A-67, A-68, A-69, A-73, A-74, A-80, A-81, A-82, F-18

### The three S0s in one line each

| ID | Defect | Closed by |
|---|---|---|
| **A-63** | `write_artifact` / `stamp_final` / `record_gate_override` use `Path.write_text`, which truncates the target to zero before the first new byte lands. `stamp_final` and `record_gate_override` are read-modify-write over the **only copy** of an approved artifact. | T1–T4: `_atomic_write_text` (temp + `fsync` + `os.replace`) |
| **A-65** | `next_version_number` is an unlocked read-then-write and its caller runs the entire gate suite between the read and the write, so two concurrent edits compute the same N and one is silently overwritten. | T5: `reserve_version()` using `O_CREAT\|O_EXCL`, plus `write_artifact` refusing to clobber |
| **A-73** | `migrations._write_synthetic_artifact` writes `artifact.v1.md` at a hardcoded version, overwrites unconditionally, and is guarded only by a DB-row check — so resetting `pipeline.db` while `runs/` persists rewrites every real styleboard. | T11–T12: filesystem-authoritative refuse/adopt guard + `reserve_version` |

### Verified non-issues — do not "fix" these

- Version comparison is **integer**, so `v10` correctly outranks `v9`. `_versions_in` returns `int` keys and `max` is numeric. Leave it.
- `parse_frontmatter` returning `({}, text)` for a file that simply does **not** open with `---` is correct and must keep working (a legitimately plain markdown artifact). Only the *other* three collapsed cases change.

### Design constraints forced by file ownership

Three findings propose fixes that reach outside this package's file list. Each is closed by an equivalent that stays inside it, and the reasoning is recorded at the task:

- **A-66** proposes a `stage_artifacts` table. `schema.sql` and `db.py` belong to **P1**. Closed instead with a filesystem high-water mark inside `artifacts.py` (T6).
- **A-73** proposes ordering the DB row insert before the disk write. `db_mod.create_stage_row` calls `conn.commit()` internally (`db.py:54`), so a deferred-commit transaction is impossible without editing P1's file. Closed instead by **idempotent adoption** (T12), which gives the same property — a crash between the two leaves state the next boot converges on without rewriting bytes.
- **A-74** proposes new `app.state` keys rendered on `/doctor`. `main.py` and `routes/doctor.py` belong to P1. Closed instead by an `events` row (T14), which the orchestration plan names as a valid human-reachable surfacing signal, and which `/doctor` can query with no signature change.

---

## 2. Finding → task map

Every one of the 15 IDs maps to a task. Coverage is total.

| Finding | Sev | Failure mode | Task(s) | What the task does |
|---|---|---|---|---|
| A-63 | **S0** | silent | T1, T2, T3, T4 | `_atomic_write_text`; adopt in `write_artifact`, `stamp_final`, `record_gate_override`, `write_pointer` |
| A-65 | **S0** | silent | T5 | `reserve_version()` / `write_reserved_artifact()` / `release_version()`; `write_artifact` refuses to clobber |
| A-73 | **S0** | silent | T11, T12 | Backfill refuses a populated stage dir; adopts its own prior synthetic; allocates via `reserve_version` |
| A-66 | S3 | latent | T6 | Version high-water mark survives deletion; frontmatter `version` cross-checked against filename |
| A-67 | S3 | silent | T7 | Strict, injective version regex; unparseable siblings warned and enumerable |
| A-68 | S2 | silent | T8 | Unterminated frontmatter block raises `MalformedArtifactError` instead of masquerading as unversioned |
| A-69 | S2 | loud | T9 | Non-mapping frontmatter and `yaml.YAMLError` contained into one typed, path-naming error |
| A-38 | S2 | silent | T10 | Overrides become an append-only list of `{reason, at, actor}`; the no-timestamp path gets one |
| A-37 | S2 | silent | T10 | `read_gate_overrides(path)` — the render-ready accessor P3/P15 call (see §6) |
| A-61 | S2 | silent | T13 | Synthetic artifact's `depends_on` computed from the scripting artifact on disk; `gates` key written explicitly |
| A-74 | S2 | silent | T14 | Per-project backfill skip records an `events` row, not just stderr |
| A-80 | S1 | silent | T15 | `pointer.yaml` records `sha256`/`size`/`written_at`; `verify_pointer()` detects an edited brief |
| A-81 | S2 | silent | T16 | `classify_brief_change()` uses set difference + explicit N-brief reason; snapshot is recursive |
| A-82 | S4 | loud | T17 | `read_pointer` validates shape and refuses any path outside `rgs-briefs/` |
| F-18 | S1 | coverage-gap | T18 | `TestDurabilityContract` — the parametrized crash-injection class over all four writers |

---

## 3. Tasks

Each task is one TDD cycle: write the failing test → run it → confirm it fails **for the stated reason** → implement → run → see it pass → commit. Run the app suite from its own directory every time:

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app" && python -m pytest tests/test_artifacts.py tests/test_migrations.py tests/test_grounding_service.py -q
```

---

### T1 — The atomic write primitive (A-63, part 1 of 4)

- [ ] **Write the failing test** in `pipeline-app/tests/test_artifacts.py`:

```python
import os
import pytest
from pipeline_app import artifacts
from pipeline_app.artifacts import _atomic_write_text


def test_atomic_write_leaves_prior_bytes_intact_when_the_write_dies_midway(tmp_path, monkeypatch):
    """A-63: the whole point. Path.write_text opens "w", truncating the target
    to zero before a byte of new content lands. Kill the write partway and the
    previous content must still be there, in full, and still parseable."""
    target = tmp_path / "artifact.v1.md"
    original = "---\nstatus: final\nversion: 1\n---\n\napproved body\n"
    target.write_text(original, encoding="utf-8")

    real_fsync = os.fsync

    def die_after_partial_write(fd):
        real_fsync(fd)
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "fsync", die_after_partial_write)

    with pytest.raises(OSError):
        _atomic_write_text(target, "---\nstatus: final\nversion: 2\n---\n\nnew body\n")

    assert target.read_text(encoding="utf-8") == original
    meta, body = artifacts.parse_frontmatter(target.read_text(encoding="utf-8"))
    assert meta["status"] == "final"
    assert "approved body" in body


def test_atomic_write_leaves_no_temp_file_behind_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "artifact.v1.md"
    target.write_text("original", encoding="utf-8")
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))

    with pytest.raises(OSError):
        _atomic_write_text(target, "replacement")

    assert target.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.iterdir()) == [target]
```

- [ ] **Run it.** Expect `ImportError: cannot import name '_atomic_write_text'`.
- [ ] **Implement** in `pipeline-app/pipeline_app/artifacts.py`. Add to the imports and define the primitive above `parse_frontmatter`:

```python
import os
import tempfile


class MalformedArtifactError(Exception):
    """An artifact file exists but cannot be read as an artifact.

    One typed error for every way an artifact can be unreadable, always naming
    the offending path. Before this, three distinct conditions -- no
    frontmatter, an unterminated block, and a non-mapping YAML value --
    collapsed into the same indistinguishable ({}, text) return (A-68), and
    yaml.YAMLError propagated uncaught into route, approval and staleness
    paths (A-69).
    """

    def __init__(self, reason: str, path: Path | None = None):
        self.reason = reason
        self.path = path
        super().__init__(f"{path if path is not None else '<text>'}: {reason}")


class ArtifactExistsError(Exception):
    """Refused to overwrite an artifact file that already exists."""


def _atomic_write_text(path: Path, text: str) -> None:
    """Write `text` to `path` such that a crash leaves either the old bytes or
    the new bytes -- never a truncation.

    Path.write_text opens in "w" mode: the existing file is truncated to zero
    before a byte of new content is written, and nothing is fsynced. For
    stamp_final and record_gate_override that target is the ONLY copy of an
    already-approved artifact and runs/ is git-ignored, so a crash mid-write
    destroyed the approved output with nothing to recover from (A-63). Worse,
    a partial write typically loses the closing `---`, and parse_frontmatter
    used to report that wreckage as a legitimate no-frontmatter artifact
    rather than as damage.

    The temp file is named with a leading dot and a .tmp suffix so it can never
    match the `artifact.v*.md` glob, and is unlinked on any failure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
```

- [ ] **Run.** Both tests pass.
- [ ] **Commit:** `fix(artifacts): add atomic temp+fsync+replace write primitive (A-63)`

---

### T2 — `write_artifact` becomes atomic and refuses to clobber (A-63, A-65 partial)

- [ ] **Write the failing test:**

```python
from pipeline_app.artifacts import ArtifactExistsError, write_artifact


def test_write_artifact_refuses_to_overwrite_an_existing_version(tmp_path):
    """A-65/A-73: write_text overwrote silently, so two callers that computed
    the same N discarded one artifact version and its recorded gate results
    with no error surfaced anywhere."""
    write_artifact(tmp_path, 1, {"stage": "shorts-styleboard"}, "the real world lock")

    with pytest.raises(ArtifactExistsError) as exc:
        write_artifact(tmp_path, 1, {"stage": "shorts-styleboard"}, "clobber")

    assert "artifact.v1.md" in str(exc.value)
    assert "the real world lock" in (tmp_path / "artifact.v1.md").read_text(encoding="utf-8")


def test_write_artifact_uses_the_atomic_primitive(tmp_path, monkeypatch):
    calls = []
    real = artifacts._atomic_write_text
    monkeypatch.setattr(
        artifacts, "_atomic_write_text",
        lambda p, t: (calls.append(p), real(p, t))[1],
    )
    write_artifact(tmp_path, 1, {"stage": "x"}, "body")
    assert (tmp_path / "artifact.v1.md") in calls
```

- [ ] **Run.** First fails (`DID NOT RAISE`), second fails (no `_atomic_write_text` call).
- [ ] **Implement:**

```python
def write_artifact(stage_dir: Path, version: int, meta: dict, body: str) -> Path:
    """Mint artifact.v{version}.md. Refuses to overwrite: an existing file at
    that path means the caller's version allocation raced or was hardcoded
    (A-65, A-73), and overwriting silently discarded an artifact version and
    its recorded gate results. Callers that are about to write should allocate
    with reserve_version() rather than next_version_number()."""
    stage_dir.mkdir(parents=True, exist_ok=True)
    path = stage_dir / f"artifact.v{version}.md"
    if path.exists():
        raise ArtifactExistsError(
            f"{path} already exists; refusing to overwrite an artifact. "
            "Allocate a version with reserve_version() instead of reusing one."
        )
    _atomic_write_text(path, render_frontmatter(meta, body))
    _record_high_water_mark(stage_dir, version)
    return path
```

  **§0 amendment (required, not conditional):** this programme executes strictly T1→T18, so T6 never
  lands immediately after T2. Add this stub to `artifacts.py` in this task (T6 will replace its body,
  not add a second definition):

```python
def _record_high_water_mark(stage_dir: Path, version: int) -> None:
    pass  # T6 replaces this body with the real sidecar-file writer.
```

- [ ] **Run.** Pass.
- [ ] **Commit:** `fix(artifacts): write_artifact is atomic and refuses to clobber (A-63, A-65)`

---

### T3 — `stamp_final` and `record_gate_override` become atomic (A-63)

- [ ] **Write the failing test:**

```python
@pytest.mark.parametrize("writer", ["stamp_final", "record_gate_override"])
def test_approval_stamp_does_not_destroy_the_approved_artifact_on_crash(tmp_path, monkeypatch, writer):
    """A-63's sharpest edge: these two are read-modify-write over the ONLY copy
    of an already-approved artifact. A crash here loses the approved output."""
    path = write_artifact(tmp_path, 1, {"status": "final", "version": 1}, "approved content")
    before = path.read_text(encoding="utf-8")

    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("power loss")))

    with pytest.raises(OSError):
        if writer == "stamp_final":
            artifacts.stamp_final(path, "2026-08-08T00:00:00+00:00")
        else:
            artifacts.record_gate_override(path, "accepted", at="2026-08-08T00:00:00+00:00")

    assert path.read_text(encoding="utf-8") == before
    meta, _ = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["status"] == "final"
```

- [ ] **Run.** Fails: the file is truncated/rewritten by `write_text`, and `record_gate_override` has no `at` kwarg yet (T10). Split the parametrize if T10 has not run — run `stamp_final` first.
- [ ] **Implement:** replace both `path.write_text(render_frontmatter(meta, body), encoding="utf-8")` calls (`artifacts.py:88`, `artifacts.py:105`) with `_atomic_write_text(path, render_frontmatter(meta, body))`. Change the read side to `meta, body = read_artifact(path)` once T8/T9 land.
- [ ] **Run.** Pass.
- [ ] **Commit:** `fix(artifacts): stamp_final and record_gate_override write atomically (A-63)`

---

### T4 — `write_pointer` becomes atomic (A-63, grounding half)

- [ ] **Write the failing test** in `pipeline-app/tests/test_grounding_service.py`:

```python
import os
import pytest
from pipeline_app import grounding_service


def test_write_pointer_survives_a_crash_without_destroying_the_prior_pointer(tmp_path, monkeypatch):
    repo_root = tmp_path
    briefs = repo_root / "rgs-briefs"
    briefs.mkdir()
    (briefs / "a.md").write_text("brief a", encoding="utf-8")
    (briefs / "b.md").write_text("brief b", encoding="utf-8")
    stage_dir = repo_root / "runs" / "r1" / "00-grounding"

    grounding_service.write_pointer(stage_dir, "rgs-briefs/a.md", repo_root)
    before = (stage_dir / "pointer.yaml").read_text(encoding="utf-8")

    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("crash")))
    with pytest.raises(OSError):
        grounding_service.write_pointer(stage_dir, "rgs-briefs/b.md", repo_root)

    assert (stage_dir / "pointer.yaml").read_text(encoding="utf-8") == before
    assert grounding_service.read_pointer(stage_dir) == "rgs-briefs/a.md"
```

- [ ] **Run.** Fails — `write_pointer` takes two arguments and uses `write_text`.
- [ ] **Implement.** First break the import cycle: `artifacts.py` currently imports `grounding_service` at module scope, which blocks `grounding_service` from importing the primitive. Move that import into the one function that uses it:

```python
# artifacts.py -- delete the module-level `from pipeline_app import grounding_service`
def resolve_latest_artifact(repo_root: Path, stage_id: str, stage_dir: Path) -> Path | None:
    ...
    if stage_id == "grounding":
        # Deferred: grounding_service imports this module for _atomic_write_text,
        # and this is the only place artifacts needs grounding_service back.
        from pipeline_app import grounding_service
        pointer = grounding_service.read_pointer(stage_dir)
```

  Then in `grounding_service.py` add `from pipeline_app.artifacts import _atomic_write_text` at module scope and rewrite the write. The full signature lands in T15; for this task it is enough to accept `repo_root` and write atomically.

- [ ] **Run.** Pass.
- [ ] **Commit:** `fix(grounding): write_pointer writes atomically (A-63)`

---

### T5 — Exclusive version allocation (A-65) ⭐ S0

- [ ] **Write the failing tests:**

```python
import threading
from pipeline_app.artifacts import release_version, reserve_version, write_reserved_artifact


def test_two_concurrent_callers_get_two_distinct_versions(tmp_path):
    """A-65: next_version_number globs and returns max+1 with no lock, and its
    caller runs the entire gate suite between the read and the write. Two
    overlapping edit POSTs both computed N, and the second silently overwrote
    the first -- an artifact version and its gate results gone, no error."""
    barrier = threading.Barrier(2)
    results: list[int] = []
    lock = threading.Lock()

    def allocate():
        barrier.wait(timeout=5)          # force the two scans to interleave
        res = reserve_version(tmp_path)
        with lock:
            results.append(res.version)

    threads = [threading.Thread(target=allocate) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert sorted(results) == [1, 2], f"lost write: both callers got {results}"


def test_many_concurrent_callers_all_get_distinct_versions(tmp_path):
    n = 12
    barrier = threading.Barrier(n)
    results: list[int] = []
    lock = threading.Lock()

    def allocate():
        barrier.wait(timeout=10)
        res = reserve_version(tmp_path)
        with lock:
            results.append(res.version)

    threads = [threading.Thread(target=allocate) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert len(set(results)) == n
    assert sorted(results) == list(range(1, n + 1))


def test_a_reservation_is_invisible_to_latest_artifact_path(tmp_path):
    """A held reservation must not be selectable as the stage's output --
    latest_artifact_path is what the approval and staleness paths read."""
    write_artifact(tmp_path, 1, {"stage": "x"}, "real")
    res = reserve_version(tmp_path)
    assert res.version == 2
    assert artifacts.latest_artifact_path(tmp_path).name == "artifact.v1.md"
    assert not list(tmp_path.glob("artifact.v2.md"))


def test_write_reserved_artifact_lands_at_the_reserved_version(tmp_path):
    res = reserve_version(tmp_path)
    path = write_reserved_artifact(res, {"stage": "x", "version": res.version}, "body")
    assert path.name == "artifact.v1.md"
    assert not res.reservation_path.exists()


@pytest.mark.xfail(
    strict=True,
    reason="A-66, not A-65: needs T6's real _record_high_water_mark. T2's stub is a "
           "no-op until T6 lands, so a released version's HWM entry is never durably "
           "recorded and the next reserve_version() call reissues it. T6 removes this "
           "marker as part of its own task.",
)
def test_released_version_is_burnt_not_reissued(tmp_path):
    """A released number must never be reissued: anything that observed it --
    a log line, a `supersedes` field, a half-written temp -- must not be able
    to point at different content later (A-66)."""
    res = reserve_version(tmp_path)
    release_version(res)
    assert reserve_version(tmp_path).version == res.version + 1
```

**§0-amendment correction, found by T5's implementer:** this test's own docstring cites A-66,
not A-65 -- it was misplaced in T5's task list. It genuinely cannot pass until T6's real
`_record_high_water_mark` lands (T2's stub is `pass`, so nothing survives a release across a
fresh `reserve_version` call). Marked `xfail(strict=True)` here, per the same pattern the
programme already uses for genuine cross-task tripwires (P1 T5) -- `strict=True` means the
suite goes **red**, not silently green, if T6 forgets to actually fix it (an unexpected pass
reports as a failure). **T6 must remove this xfail marker as part of its own task** and confirm
the test then passes for the real reason (HWM persists past release), not vacuously.

- [ ] **Run.** Every one fails with `ImportError`/`AttributeError` on `reserve_version`.
- [ ] **Implement** in `artifacts.py`:

```python
from dataclasses import dataclass

_RESERVED_RE = re.compile(r"^\.artifact\.v(0|[1-9]\d*)\.reserved$")


@dataclass(frozen=True)
class VersionReservation:
    version: int
    stage_dir: Path
    reservation_path: Path

    @property
    def artifact_path(self) -> Path:
        return self.stage_dir / f"artifact.v{self.version}.md"


def reserve_version(stage_dir: Path, *, max_attempts: int = 256) -> VersionReservation:
    """Exclusively allocate the next artifact version.

    next_version_number is an unlocked read-then-write, and on the edit path
    the read and the write are separated by the whole gate run -- a window wide
    enough to load and execute a linter (A-65). Reservation closes it by making
    the ALLOCATION the exclusive operation: O_CREAT|O_EXCL either creates the
    marker or fails, atomically, at the filesystem. There is no lock to
    acquire, nothing to release on a hard kill, and the worst outcome of a
    crash is a burnt version number -- never a lost artifact.

    The marker is dot-prefixed so it cannot match the artifact.v*.md glob and
    can never be selected as a stage's output.
    """
    stage_dir.mkdir(parents=True, exist_ok=True)
    # §0 amendment: seed from next_version_number(), NOT _high_water_mark() directly --
    # _high_water_mark is defined in T6, which has not run yet at T5. next_version_number
    # is the pre-existing equivalent (max version on disk, default 0, + 1); T6 later
    # redefines next_version_number to route through _high_water_mark, which upgrades
    # this call's behaviour automatically with no further edit here.
    candidate = next_version_number(stage_dir)
    for _ in range(max_attempts):
        marker = stage_dir / f".artifact.v{candidate}.reserved"
        try:
            fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            candidate += 1
            continue
        os.close(fd)
        _record_high_water_mark(stage_dir, candidate)
        return VersionReservation(candidate, stage_dir, marker)
    raise RuntimeError(
        f"could not reserve an artifact version in {stage_dir} after {max_attempts} attempts"
    )


def write_reserved_artifact(reservation: VersionReservation, meta: dict, body: str) -> Path:
    """Write the artifact a reservation holds, then drop the marker."""
    path = reservation.artifact_path
    if path.exists():
        raise ArtifactExistsError(f"{path} already exists; the reservation was not honoured.")
    _atomic_write_text(path, render_frontmatter(meta, body))
    reservation.reservation_path.unlink(missing_ok=True)
    return path


def release_version(reservation: VersionReservation) -> None:
    """Drop a reservation whose write never happened.

    Deliberately does NOT lower the high-water mark. A released number is
    burnt: reissuing it would let two different bodies occupy the same version
    over the life of a stage, which is exactly the history-lying failure A-66
    describes.
    """
    reservation.reservation_path.unlink(missing_ok=True)


def _reserved_versions_in(stage_dir: Path) -> list[int]:
    out = []
    for p in stage_dir.glob(".artifact.v*.reserved"):
        m = _RESERVED_RE.match(p.name)
        if m:
            out.append(int(m.group(1)))
    return out
```

- [ ] **Run.** Pass. Re-run the concurrency test 5× to confirm it is not flaky.
- [ ] **Commit:** `fix(artifacts): exclusive O_EXCL version reservation (A-65)`

---

### T6 — Version numbers survive deletion; filename/frontmatter cross-check (A-66)

- [ ] **Write the failing tests:**

```python
def test_deleting_the_newest_artifact_does_not_reissue_its_version(tmp_path):
    """A-66: the sequence used to be whatever the directory currently contained,
    so deleting artifact.v3.md made the next write v3 again -- the version
    number, the supersedes chain and the `version:` field all lying about
    history, and any dependent whose depends_on recorded the old v3 hash now
    comparing against a different file at the same path."""
    for v in (1, 2, 3):
        write_artifact(tmp_path, v, {"version": v}, f"body {v}")
    (tmp_path / "artifact.v3.md").unlink()

    assert artifacts.next_version_number(tmp_path) == 4
    assert reserve_version(tmp_path).version == 4


def test_high_water_mark_survives_deleting_every_artifact(tmp_path):
    write_artifact(tmp_path, 1, {"version": 1}, "a")
    write_artifact(tmp_path, 2, {"version": 2}, "b")
    for p in tmp_path.glob("artifact.v*.md"):
        p.unlink()
    assert artifacts.next_version_number(tmp_path) == 3


def test_read_artifact_rejects_a_frontmatter_version_that_disagrees_with_the_filename(tmp_path):
    """A rename desynchronizes them permanently and silently -- nothing ever
    cross-checked the two."""
    write_artifact(tmp_path, 1, {"version": 1, "status": "final"}, "body")
    renamed = tmp_path / "artifact.v9.md"
    (tmp_path / "artifact.v1.md").rename(renamed)

    with pytest.raises(artifacts.MalformedArtifactError) as exc:
        artifacts.read_artifact(renamed)
    assert "does not match filename" in str(exc.value)


def test_corrupt_high_water_mark_is_warned_and_ignored_not_fatal(tmp_path, monkeypatch):
    events = []
    monkeypatch.setattr(artifacts.obs, "log", lambda e, **k: events.append((e, k)))
    write_artifact(tmp_path, 1, {"version": 1}, "a")
    (tmp_path / ".artifact-version-hwm").write_text("not a number", encoding="utf-8")

    assert artifacts.next_version_number(tmp_path) == 2
    assert any(e == "artifacts.hwm_unreadable" for e, _ in events)
```

- [ ] **Run.** All four fail. **Also remove the `@pytest.mark.xfail(strict=True, ...)` marker T5 put
  on `test_released_version_is_burnt_not_reissued`** (it cites A-66, was misplaced in T5's task list
  per that task's own §0-amendment correction) — after this task's implementation lands, run it and
  confirm it passes for the real reason (the HWM sidecar file persists past `release_version`), not
  vacuously.
- [ ] **Implement** in `artifacts.py` (add `from pipeline_app import obs` to the imports). §0
  amendment: T2 already added a stub `_record_high_water_mark(stage_dir, version) -> None: pass`.
  **Replace that stub's body** with the real implementation below — do not add a second definition:

```python
_HWM_NAME = ".artifact-version-hwm"


def _high_water_mark(stage_dir: Path) -> int:
    """The highest version number ever ALLOCATED in this stage dir, not the
    highest currently on disk.

    A-66: with no table recording versions, the sequence was whatever the
    directory happened to contain, and runs/ is git-ignored and hand-managed --
    an ordinary operator deletion silently reissued a live version number. A
    sidecar high-water mark keeps allocation monotonic without a schema change
    (schema.sql and db.py belong to P1).
    """
    seen = [v for v, _ in _versions_in(stage_dir)]
    seen += _reserved_versions_in(stage_dir)
    hwm_path = stage_dir / _HWM_NAME
    if hwm_path.exists():
        raw = hwm_path.read_text(encoding="utf-8").strip()
        if raw.isdigit():
            seen.append(int(raw))
        else:
            obs.log(
                "artifacts.hwm_unreadable",
                level="warning",
                stage_dir=str(stage_dir),
                raw=raw[:80],
                detail="version high-water mark is not an integer; falling back to the "
                       "filesystem, which can reissue a deleted version number",
            )
    return max(seen) if seen else 0


def _record_high_water_mark(stage_dir: Path, version: int) -> None:
    if version > _high_water_mark(stage_dir):
        _atomic_write_text(stage_dir / _HWM_NAME, f"{version}\n")


def next_version_number(stage_dir: Path) -> int:
    """Advisory: the version reserve_version() will TRY first.

    This is no longer an allocator -- it is an unlocked read and always was
    (A-65). Kept for read-only introspection and for callers not yet migrated;
    anything about to WRITE must call reserve_version().
    """
    return _high_water_mark(stage_dir) + 1


def read_artifact(path: Path) -> tuple[dict, str]:
    """parse_frontmatter over a file, naming the path in every failure and
    cross-checking the frontmatter `version` against the filename (A-66)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise MalformedArtifactError(f"unreadable: {type(exc).__name__}: {exc}", path=path) from exc
    try:
        meta, body = parse_frontmatter(text)
    except MalformedArtifactError as exc:
        raise MalformedArtifactError(exc.reason, path=path) from exc
    m = _VERSION_RE.match(path.name)
    if m is not None and isinstance(meta.get("version"), int) and meta["version"] != int(m.group(1)):
        raise MalformedArtifactError(
            f"frontmatter version {meta['version']} does not match filename version "
            f"{int(m.group(1))} -- the file was renamed or hand-copied",
            path=path,
        )
    return meta, body
```

- [ ] **Run.** Pass. Confirm the pre-existing `test_next_version_number_empty_dir_is_one` and `test_next_version_number_increments` still pass unchanged.
- [ ] **Commit:** `fix(artifacts): monotonic version high-water mark and filename cross-check (A-66)`

---

### T7 — Strict version regex; unparseable siblings surfaced (A-67)

- [ ] **Write the failing tests:**

```python
def test_zero_padded_duplicate_does_not_make_latest_artifact_nondeterministic(tmp_path):
    """A-67: artifact.v07.md and artifact.v7.md both parsed to 7, and
    max(..., key=...) resolved the tie by glob iteration order -- which one the
    app treated as the stage's output was filesystem-dependent."""
    (tmp_path / "artifact.v7.md").write_text("the real one", encoding="utf-8")
    (tmp_path / "artifact.v07.md").write_text("an OS copy", encoding="utf-8")

    assert artifacts.latest_artifact_path(tmp_path).name == "artifact.v7.md"
    assert [v for v, _ in artifacts._versions_in(tmp_path)] == [7]


def test_unparseable_sibling_is_warned_and_enumerable_not_silently_dropped(tmp_path, monkeypatch):
    """A rescued or hand-annotated artifact used to vanish from the app while
    sitting in plain sight in the directory."""
    events = []
    monkeypatch.setattr(artifacts.obs, "log", lambda e, **k: events.append((e, k)))
    (tmp_path / "artifact.v1.md").write_text("real", encoding="utf-8")
    (tmp_path / "artifact.vfinal.md").write_text("rescued", encoding="utf-8")
    (tmp_path / "artifact.v3 (copy).md").write_text("os copy", encoding="utf-8")

    artifacts._versions_in(tmp_path)
    assert sum(1 for e, _ in events if e == "artifacts.unversioned_sibling") == 2

    names = {p.name for p in artifacts.list_unversioned_siblings(tmp_path)}
    assert names == {"artifact.vfinal.md", "artifact.v3 (copy).md"}


def test_v10_still_outranks_v9(tmp_path):
    """Verified non-issue -- pinned so nobody "fixes" the numeric comparison
    into a string one."""
    (tmp_path / "artifact.v9.md").write_text("nine", encoding="utf-8")
    (tmp_path / "artifact.v10.md").write_text("ten", encoding="utf-8")
    assert artifacts.latest_artifact_path(tmp_path).name == "artifact.v10.md"
```

- [ ] **Run.** The first two fail (`artifact.v07.md` parses to 7; no `list_unversioned_siblings`). The third passes already — that is the point.
- [ ] **Implement:**

```python
# Injective by construction: exactly one filename maps to any given version, so
# a zero-padded duplicate cannot produce an arbitrary tie-break (A-67).
_VERSION_RE = re.compile(r"^artifact\.v(0|[1-9]\d*)\.md$")


def _versions_in(stage_dir: Path) -> list[tuple[int, Path]]:
    versions: list[tuple[int, Path]] = []
    for p in sorted(stage_dir.glob("artifact.v*.md")):
        m = _VERSION_RE.match(p.name)
        if not m:
            obs.log(
                "artifacts.unversioned_sibling",
                level="warning",
                path=str(p),
                detail="matches artifact.v*.md but not artifact.v<N>.md; invisible to "
                       "version allocation and to latest-artifact resolution",
            )
            continue
        versions.append((int(m.group(1)), p))
    return sorted(versions)


def list_unversioned_siblings(stage_dir: Path) -> list[Path]:
    """Files that look like artifacts but that the version regex rejects.

    Exposed so /doctor (P1) can show an operator the rescued or hand-annotated
    file the app is ignoring, instead of it vanishing silently (A-67).
    """
    if not stage_dir.exists():
        return []
    return sorted(
        p for p in stage_dir.glob("artifact.v*.md") if not _VERSION_RE.match(p.name)
    )
```

- [ ] **Run.** Pass.
- [ ] **Commit:** `fix(artifacts): injective version regex, surface unversioned siblings (A-67)`

---

### T8 — An unterminated frontmatter block is damage, not "unversioned" (A-68) ⭐ Three-Test Rule

- [ ] **Write the failing tests:**

```python
def test_unterminated_frontmatter_raises_instead_of_masquerading_as_unversioned(tmp_path):
    """FAULT. A-68: an opening --- with no closing delimiter fell through the
    loop and returned ({}, text) -- exactly the shape a crash-truncated
    artifact takes (A-63), reported as a legitimate plain-markdown file."""
    truncated = "---\nschema_version: 1\nstatus: final\nversion: 1\n"
    with pytest.raises(artifacts.MalformedArtifactError) as exc:
        artifacts.parse_frontmatter(truncated)
    assert "never closed" in str(exc.value)


def test_truncated_artifact_is_distinguishable_from_a_genuinely_plain_one(tmp_path):
    """DISTINGUISHABILITY. Three conditions used to collapse to the same
    indistinguishable ({}, text)."""
    plain = tmp_path / "artifact.v1.md"
    plain.write_text("just a plain markdown artifact, no frontmatter", encoding="utf-8")
    truncated = tmp_path / "artifact.v2.md"
    truncated.write_text("---\nstatus: final\nversion: 2\n", encoding="utf-8")

    plain_result = artifacts.read_artifact(plain)
    assert plain_result == ({}, "just a plain markdown artifact, no frontmatter")

    with pytest.raises(artifacts.MalformedArtifactError):
        artifacts.read_artifact(truncated)


def test_a_truncated_artifact_names_its_own_path_in_the_error(tmp_path):
    """SURFACING. The human-reachable signal is a typed error naming the file;
    an operator (or an obs event recorded by the caller) can act on it. Before,
    nothing anywhere logged that a --- was opened and never closed."""
    bad = tmp_path / "artifact.v1.md"
    bad.write_text("---\nstatus: final\n", encoding="utf-8")
    with pytest.raises(artifacts.MalformedArtifactError) as exc:
        artifacts.read_artifact(bad)
    assert str(bad) in str(exc.value)
    assert exc.value.path == bad


def test_empty_frontmatter_block_is_still_an_empty_mapping(tmp_path):
    """A genuinely empty block is benign and must keep working."""
    assert artifacts.parse_frontmatter("---\n---\n\nbody") == ({}, "body")
```

- [ ] **Run.** The first three fail (`DID NOT RAISE` / no `read_artifact` behavior).
- [ ] **Implement** — replace `parse_frontmatter` wholesale (this task and T9 land together in the body, but commit separately by adding the unterminated raise first):

```python
def parse_frontmatter(text: str) -> tuple[dict, str]:
    """The frontmatter mapping and the body.

    Returns ({}, text) for EXACTLY one condition: the text does not open with a
    `---` delimiter -- i.e. a legitimately plain markdown artifact. Every other
    departure raises MalformedArtifactError.

    Three distinct conditions used to collapse into that same ({}, text)
    return: no frontmatter at all, an opening `---` with no closing delimiter,
    and an empty YAML block (A-68). The middle one is precisely the shape a
    crash-truncated artifact takes (A-63), so returning it as "an artifact with
    no provenance" is how truncation became invisible -- downstream,
    depends_on yielded [], gates yielded [], and status yielded None so an
    already-final artifact was re-stamped.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != _DELIM:
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() != _DELIM:
            continue
        yaml_text = "\n".join(lines[1:i])
        body = "\n".join(lines[i + 1:])
        # §0 amendment: inline the pre-existing load here (byte-identical to what
        # parse_frontmatter already did) rather than forward-referencing T9's
        # _load_frontmatter_yaml, which does not exist yet. T9 replaces this one
        # line with `meta = _load_frontmatter_yaml(yaml_text)` and defines the helper.
        meta = yaml.safe_load(yaml_text) or {}
        return meta, body.lstrip("\n")
    raise MalformedArtifactError(
        "frontmatter block opened with '---' and was never closed -- the file is "
        "truncated, not unversioned"
    )
```

- [ ] **Run.** Pass.
- [ ] **Commit:** `fix(artifacts): unterminated frontmatter raises instead of degrading (A-68)`

---

### T9 — Non-mapping frontmatter and `YAMLError` contained (A-69)

- [ ] **Write the failing tests:**

```python
@pytest.mark.parametrize("block,kind", [
    ("---\njust a string\n---\n\nbody", "str"),
    ("---\n- a\n- b\n---\n\nbody", "list"),
    ("---\n42\n---\n\nbody", "int"),
])
def test_non_mapping_frontmatter_raises_a_named_error_not_attributeerror(block, kind):
    """A-69(a): yaml.safe_load returned whatever the block parsed to, and every
    caller immediately called .get() on it -- AttributeError and a bare 500
    with no indication of which artifact was at fault."""
    with pytest.raises(artifacts.MalformedArtifactError) as exc:
        artifacts.parse_frontmatter(block)
    assert "not a mapping" in str(exc.value)
    assert kind in str(exc.value)


def test_malformed_yaml_is_contained_into_one_predictable_error(tmp_path):
    """A-69(b): yaml.YAMLError propagated uncaught into the route, approval and
    staleness paths. The worst site is propagate_staleness's phase-1 loop,
    where one malformed dependent aborted the cascade MID-ITERATION."""
    bad = tmp_path / "artifact.v1.md"
    bad.write_text("---\nstatus: 'unterminated\nversion: 1\n---\n\nbody", encoding="utf-8")
    with pytest.raises(artifacts.MalformedArtifactError) as exc:
        artifacts.read_artifact(bad)
    assert "not valid YAML" in str(exc.value)
    assert str(bad) in str(exc.value)
    assert isinstance(exc.value.__cause__, yaml.YAMLError)


def test_a_body_starting_with_a_horizontal_rule_is_rejected_not_misparsed():
    """The reachable-by-accident case: a body that begins with a markdown
    horizontal rule was mistaken for a frontmatter opener."""
    with pytest.raises(artifacts.MalformedArtifactError):
        artifacts.parse_frontmatter("---\n\nA heading\n\n---\n\nmore body")
```

- [ ] **Run.** All fail with `AttributeError`/`yaml.YAMLError` rather than `MalformedArtifactError`.
- [ ] **Implement.** T8 left `parse_frontmatter` calling `meta = yaml.safe_load(yaml_text) or {}` inline
  (§0 amendment). Replace that one line with `meta = _load_frontmatter_yaml(yaml_text)` and add the
  helper below:

```python
def _load_frontmatter_yaml(yaml_text: str) -> dict:
    """One predictable failure mode for a frontmatter block that is not a
    mapping. Two uncontained failures shared one root (A-69): safe_load's
    return was used unvalidated, and YAMLError escaped the parse boundary."""
    try:
        meta = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise MalformedArtifactError(f"frontmatter is not valid YAML: {exc}") from exc
    if meta is None:
        return {}
    if not isinstance(meta, dict):
        raise MalformedArtifactError(
            f"frontmatter parsed to {type(meta).__name__}, not a mapping"
        )
    return meta
```

- [ ] **Run.** Pass.
- [ ] **Commit:** `fix(artifacts): contain YAMLError and reject non-mapping frontmatter (A-69)`

---

### T10 — Append-only overrides with timestamp and actor; render accessor (A-38, A-37)

- [ ] **Write the failing tests:**

```python
def test_two_overrides_on_one_artifact_both_survive(tmp_path):
    """A-38: record_gate_override assigned meta["gate_override_reason"] = ...,
    overwriting any prior value -- approving the same artifact twice with
    different reasons left only the second."""
    path = write_artifact(tmp_path, 1, {"status": "final", "version": 1}, "body")
    artifacts.record_gate_override(path, "accepted: known false positive",
                                   at="2026-08-08T10:00:00+00:00", actor="brian")
    artifacts.record_gate_override(path, "accepted again after re-review",
                                   at="2026-08-08T11:00:00+00:00", actor="brian")

    overrides = artifacts.read_gate_overrides(path)
    assert [o["reason"] for o in overrides] == [
        "accepted: known false positive",
        "accepted again after re-review",
    ]


def test_an_override_on_an_already_final_artifact_carries_a_timestamp(tmp_path):
    """A-38: the record_gate_override branch deliberately did not touch
    finalized_at, so an override applied to an already-final artifact carried
    NO timestamp at all -- only stages.approved_at moved, and nothing linked
    the two."""
    path = write_artifact(tmp_path, 1, {"status": "final", "version": 1}, "body")
    artifacts.record_gate_override(path, "accepted", at="2026-08-08T12:00:00+00:00")
    entry = artifacts.read_gate_overrides(path)[0]
    assert entry["at"] == "2026-08-08T12:00:00+00:00"
    assert entry["actor"]


def test_stamp_final_override_lands_in_the_same_append_only_list(tmp_path):
    path = write_artifact(tmp_path, 1, {"status": "draft", "version": 1}, "body")
    artifacts.stamp_final(path, "2026-08-08T09:00:00+00:00",
                          gate_override_reason="accepted at approval")
    entry = artifacts.read_gate_overrides(path)[0]
    assert entry["reason"] == "accepted at approval"
    assert entry["at"] == "2026-08-08T09:00:00+00:00"


def test_a_legacy_scalar_override_is_migrated_forward_not_dropped(tmp_path):
    """The old scalar field is the only record of an override applied before
    this change; it must survive into the list."""
    path = write_artifact(
        tmp_path, 1,
        {"status": "final", "version": 1, "gate_override_reason": "old decision"},
        "body",
    )
    artifacts.record_gate_override(path, "new decision", at="2026-08-08T12:00:00+00:00")
    reasons = [o["reason"] for o in artifacts.read_gate_overrides(path)]
    assert reasons == ["old decision", "new decision"]


def test_read_gate_overrides_is_empty_for_an_artifact_with_none(tmp_path):
    """A-37's render accessor: the gates panel iterates this. An artifact with
    no override must yield [] -- not None, not a KeyError."""
    path = write_artifact(tmp_path, 1, {"status": "final", "version": 1}, "body")
    assert artifacts.read_gate_overrides(path) == []
```

- [ ] **Run.** All fail — no `read_gate_overrides`, no `at`/`actor` kwargs.
- [ ] **Implement:**

```python
_DEFAULT_ACTOR = "operator"


def _append_override(meta: dict, reason: str, at: str | None, actor: str | None) -> None:
    """Append an override rather than assign one.

    A-38: this was `meta["gate_override_reason"] = reason` -- last-write-wins,
    with no actor anywhere and, on the record_gate_override path, no timestamp
    at all. A migrated legacy scalar is carried into the list rather than
    dropped, because it is the only record of an override applied before this
    change.
    """
    history = meta.get("gate_overrides")
    if not isinstance(history, list):
        history = []
    legacy = meta.pop("gate_override_reason", None)
    if isinstance(legacy, str) and legacy.strip():
        history.append({"reason": legacy, "at": None, "actor": None})
    history.append({"reason": reason, "at": at, "actor": actor or _DEFAULT_ACTOR})
    meta["gate_overrides"] = history


def stamp_final(path: Path, finalized_at: str, gate_override_reason: str | None = None,
                *, actor: str | None = None) -> None:
    meta, body = read_artifact(path)
    meta["status"] = "final"
    meta["finalized_at"] = finalized_at
    if gate_override_reason:
        # Recorded alongside the failing gate result, which is deliberately left
        # untouched -- an override says a human accepted the finding, not that
        # the finding was wrong.
        _append_override(meta, gate_override_reason, finalized_at, actor)
    _atomic_write_text(path, render_frontmatter(meta, body))


def record_gate_override(path: Path, gate_override_reason: str, *,
                         at: str, actor: str | None = None) -> None:
    """Record an override on an artifact that is ALREADY stamped final.

    `at` is required and keyword-only: the old signature had no timestamp
    parameter and deliberately did not touch finalized_at, so an override on an
    already-final artifact carried no time anywhere in the file (A-38).
    Writes only the override history: status, finalized_at and the `gates`
    entry itself are left untouched.
    """
    meta, body = read_artifact(path)
    _append_override(meta, gate_override_reason, at, actor)
    _atomic_write_text(path, render_frontmatter(meta, body))


def read_gate_overrides(path: Path) -> list[dict]:
    """Every override recorded on an artifact, oldest first.

    A-37: gate_override_reason was write-only -- stage_page read only
    output_meta.get("gates") and stage.html never referenced the override, so
    an operator saw a red failing gate with no indication that anyone
    consciously accepted it or why. This is the accessor the gates panel
    renders (see the P3/P15 contract in the plan).
    """
    meta, _ = read_artifact(path)
    history = meta.get("gate_overrides")
    if isinstance(history, list):
        return [h for h in history if isinstance(h, dict)]
    legacy = meta.get("gate_override_reason")
    if isinstance(legacy, str) and legacy.strip():
        return [{"reason": legacy, "at": None, "actor": None}]
    return []
```

- [ ] **Run.** Pass, including T3's `record_gate_override` parametrization.
- [ ] **Commit:** `fix(artifacts): append-only gate overrides with timestamp and actor (A-38, A-37)`

---

### T11 — Backfill refuses to overwrite a real styleboard (A-73) ⭐ S0

- [ ] **Write the failing tests** in `pipeline-app/tests/test_migrations.py`:

```python
import pytest
from pipeline_app import migrations
from pipeline_app.migrations import BackfillWouldOverwriteError, backfill_styleboard_rows


def test_backfill_refuses_to_overwrite_a_real_styleboard_artifact(conn, tmp_path):
    """A-73, the S0. runs/ and pipeline.db are independently git-ignored and
    independently disposable. Resetting the DB while runs/ is intact used to
    rewrite every project's real 02b-styleboard/artifact.v1.md with the
    synthetic "not recoverable" body -- no backup, no warning."""
    pid = _legacy_project(conn, tmp_path, "legacy-real", "approved")
    styleboard_dir = tmp_path / "runs" / "legacy-real" / "02b-styleboard"
    styleboard_dir.mkdir(parents=True)
    real = styleboard_dir / "artifact.v1.md"
    real.write_text(
        "---\nschema_version: 1\nversion: 1\nstatus: final\n---\n\n"
        "WORLD LOCK\n  register_a_sport: the real hand-authored world\n",
        encoding="utf-8",
    )
    before = real.read_text(encoding="utf-8")

    touched = backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    assert real.read_text(encoding="utf-8") == before
    assert "the real hand-authored world" in real.read_text(encoding="utf-8")
    assert pid not in touched


def test_refusing_to_overwrite_records_an_error_event(conn, tmp_path, monkeypatch):
    """SURFACING. Destroying a styleboard must never be the quiet outcome, and
    declining to destroy it must not be quiet either."""
    recorded = []
    monkeypatch.setattr(migrations.obs, "record_event",
                        lambda c, **kw: recorded.append(kw) or 1)
    _legacy_project(conn, tmp_path, "legacy-real2", "approved")
    d = tmp_path / "runs" / "legacy-real2" / "02b-styleboard"
    d.mkdir(parents=True)
    (d / "artifact.v1.md").write_text(
        "---\nversion: 1\nstatus: final\n---\n\nreal\n", encoding="utf-8")

    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    assert any(e["severity"] == "error" and "overwrite" in e["message"].lower()
               for e in recorded)


def test_backfill_allocates_its_version_rather_than_hardcoding_one(conn, tmp_path):
    """_write_synthetic_artifact passed a literal 1 to write_artifact rather
    than allocating."""
    _legacy_project(conn, tmp_path, "legacy-v", "approved", sheet=LEGACY_SHEET)
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)
    written = tmp_path / "runs" / "legacy-v" / "02b-styleboard" / "artifact.v1.md"
    meta, _ = artifacts.read_artifact(written)
    assert meta["version"] == 1     # first version in an empty dir, but ALLOCATED
    assert (tmp_path / "runs" / "legacy-v" / "02b-styleboard" / ".artifact-version-hwm").exists()
```

- [ ] **Run.** The first two fail — the real artifact is overwritten with "not recoverable".
- [ ] **Implement** in `migrations.py`:

```python
from pipeline_app import artifacts, db as db_mod, obs


class BackfillWouldOverwriteError(Exception):
    """A real artifact already occupies the styleboard stage directory."""


def _adoptable_synthetic(stage_dir: Path, run_id: str) -> Path | None:
    """This stage dir's current artifact if it is OUR OWN prior synthetic, else
    None -- and a raise if it is anyone else's.

    A-73: the migration was guarded only by "this project has no styleboard DB
    ROW". A filesystem check was never made, and the filesystem is the
    authority on whether an artifact exists -- the DB row is not.
    """
    latest = artifacts.latest_artifact_path(stage_dir)
    if latest is None:
        return None
    meta, _ = artifacts.read_artifact(latest)
    if meta.get("backfilled") is True and meta.get("run_id") == run_id:
        return latest
    raise BackfillWouldOverwriteError(
        f"{latest} already exists and was not written by this migration "
        f"(backfilled={meta.get('backfilled')!r}, run_id={meta.get('run_id')!r}); "
        "refusing to overwrite a real styleboard artifact"
    )


def _write_synthetic_artifact(
    stage_dir: Path, run_id: str, stage_def: StageDef, now: str, body: str,
    depends_on: list[dict],
) -> Path:
    stage_dir.mkdir(parents=True, exist_ok=True)
    adopted = _adoptable_synthetic(stage_dir, run_id)
    if adopted is not None:
        # Idempotent adoption -- see _backfill_one_project's docstring (A-73).
        return adopted
    reservation = artifacts.reserve_version(stage_dir)
    try:
        return artifacts.write_reserved_artifact(
            reservation,
            {
                "schema_version": 1,
                "run_id": run_id,
                "stage": stage_def.skill,
                "version": reservation.version,
                "status": "final",
                "created_at": now,
                "finalized_at": now,
                "supersedes": None,
                "depends_on": depends_on,
                # styleboard registers no gates (gates.GATE_REGISTRY), so [] is
                # the registry-consistent value. Written EXPLICITLY: an absent
                # key is indistinguishable from a clean run to
                # approval_service's never_ran check (A-61).
                "gates": [],
                "backfilled": True,
            },
            body,
        )
    except BaseException:
        artifacts.release_version(reservation)
        raise
```

  Add `BackfillWouldOverwriteError` to `_PER_PROJECT_RECOVERABLE` (§0 amendment 2: `artifacts.MalformedArtifactError` was already added there in T9, pulled forward because T9's own change broke this package's pre-existing test otherwise — do not duplicate it, just confirm it's present), and update both `_write_synthetic_artifact` call sites to pass `depends_on` (T13 computes it; pass `[]` for this task only if T13 has not run).

- [ ] **Run.** Pass.
- [ ] **Commit:** `fix(migrations): backfill refuses to overwrite a real styleboard (A-73)`

---

### T12 — Idempotent adoption closes the write-then-row crash window (A-73, second half)

- [ ] **Write the failing tests:**

```python
def test_a_crash_between_the_artifact_write_and_the_db_row_does_not_churn_the_artifact(
    conn, tmp_path, monkeypatch
):
    """A-73's second hazard: the disk write precedes the DB write, so a failure
    in between left an artifact with no row -- and the next boot rewrote it
    with a fresh `now`, changing its sha256 and spuriously staling every
    dependent."""
    _legacy_project(conn, tmp_path, "legacy-crash", "approved", sheet=LEGACY_SHEET)

    real_create = db_mod.create_stage_row
    def crash_once(*a, **k):
        raise OSError("killed between the disk write and the row insert")
    monkeypatch.setattr(db_mod, "create_stage_row", crash_once)

    with pytest.raises(OSError):
        backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    written = tmp_path / "runs" / "legacy-crash" / "02b-styleboard" / "artifact.v1.md"
    assert written.exists()
    sha_after_crash = artifacts.compute_sha256(written)

    monkeypatch.setattr(db_mod, "create_stage_row", real_create)
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    assert artifacts.compute_sha256(written) == sha_after_crash, \
        "the retry rewrote the artifact with a fresh timestamp and staled its dependents"
    assert len(list((written.parent).glob("artifact.v*.md"))) == 1
```

  Note: `create_stage_row` raising `OSError` escapes `_PER_PROJECT_RECOVERABLE`? It does not — `OSError` is in the tuple, so the project is skipped rather than the migration crashing. Adjust the test to assert on the skip path instead of `pytest.raises` if the implementation keeps that containment; either shape is acceptable **provided** the sha-stability assertion is the one that must hold.

- [ ] **Run.** Fails: the retry rewrites with a new `now` and the sha changes.
- [ ] **Implement.** The adoption branch from T11 already does the work; this task adds the reasoning to `_backfill_one_project`'s docstring and makes the DB-row/status path tolerate an adopted artifact:

```python
def _backfill_one_project(...) -> None:
    """...

    Ordering. A-73 proposes inserting the DB row before the disk write, or
    making the pair transactional. Neither is available here:
    db_mod.create_stage_row calls conn.commit() internally (db.py:54), and db.py
    belongs to package P1. The equivalent property is bought with idempotent
    adoption instead -- _adoptable_synthetic recognises this migration's own
    prior output by (backfilled, run_id) and returns it UNCHANGED, so a crash
    between the disk write and the row insert converges on the next boot
    without rewriting a byte. The artifact's sha256 is stable across the retry,
    so no dependent is spuriously staled.
    """
```

- [ ] **Run.** Pass. Confirm `test_backfill_is_idempotent` (`test_migrations.py:78-81`) still passes.
- [ ] **Commit:** `fix(migrations): idempotent adoption closes the write-then-row window (A-73)`

---

### T13 — Backfilled `depends_on` participates in the staleness cascade (A-61)

- [ ] **Write the failing tests:**

```python
def test_backfilled_styleboard_records_the_scripting_artifact_it_was_built_against(
    conn, tmp_path
):
    """A-61: _write_synthetic_artifact hardcoded depends_on: [] while the row
    was set to approved. styleboard declares depends_on: [scripting], so on
    every migrated project a scripting change could NEVER flip styleboard
    stale -- and `visual` was then regenerated against an unflagged world lock."""
    pid = _legacy_project(conn, tmp_path, "legacy-dep", "approved", sheet=LEGACY_SHEET)
    scripting_dir = tmp_path / "runs" / "legacy-dep" / "02-scripting"
    script = artifacts.write_artifact(
        scripting_dir, 1, {"version": 1, "status": "final"}, "the script")

    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    written = tmp_path / "runs" / "legacy-dep" / "02b-styleboard" / "artifact.v1.md"
    meta, _ = artifacts.read_artifact(written)
    assert meta["depends_on"] == [
        {"path": "02-scripting/artifact.v1.md",
         "sha256": artifacts.compute_sha256(script)},
    ]


def test_a_backfilled_styleboard_goes_stale_when_its_script_is_rewritten(conn, tmp_path):
    """The cascade this was terminating. is_stale must now fire."""
    from pipeline_app.state_machine import is_stale

    _legacy_project(conn, tmp_path, "legacy-dep2", "approved", sheet=LEGACY_SHEET)
    scripting_dir = tmp_path / "runs" / "legacy-dep2" / "02-scripting"
    artifacts.write_artifact(scripting_dir, 1, {"version": 1}, "original script")
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    written = tmp_path / "runs" / "legacy-dep2" / "02b-styleboard" / "artifact.v1.md"
    recorded = artifacts.read_artifact(written)[0]["depends_on"]

    rewritten = artifacts.write_artifact(scripting_dir, 2, {"version": 2}, "REWRITTEN script")
    current = {"02-scripting/artifact.v2.md": artifacts.compute_sha256(rewritten)}
    assert is_stale(recorded, current) is True


def test_backfilled_artifact_records_an_explicit_gates_key(conn, tmp_path):
    """It was the one approved artifact in the app carrying no `gates` key at
    all -- indistinguishable, to approval_service, from a clean run."""
    _legacy_project(conn, tmp_path, "legacy-gates", "approved", sheet=LEGACY_SHEET)
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)
    written = tmp_path / "runs" / "legacy-gates" / "02b-styleboard" / "artifact.v1.md"
    meta, _ = artifacts.read_artifact(written)
    assert "gates" in meta
    assert meta["gates"] == []
    assert meta["backfilled"] is True
```

- [ ] **Run.** The first two fail (`depends_on == []`); the third fails (no `gates` key).
- [ ] **Implement.** In `artifacts.py`, add the canonical helpers both this migration and P3's hand-edit route call (see §6):

```python
def relpath_in_run(path: Path, run_dir: Path) -> str:
    """A run-relative, forward-slashed artifact path -- the exact key shape
    state_machine.is_stale compares against."""
    return str(path.relative_to(run_dir)).replace("\\", "/")


def compute_depends_on(run_dir: Path, upstream_paths: Iterable[Path]) -> list[dict]:
    """The `depends_on` list for a new artifact version, computed from the
    upstream artifacts that exist RIGHT NOW.

    The canonical implementation. Copying a prior artifact's depends_on forward
    is what made staleness sticky (A-61): once a node records [], every later
    version inherits it and the entire downstream cascade terminates there.
    """
    return [
        {"path": relpath_in_run(p, run_dir), "sha256": compute_sha256(p)}
        for p in upstream_paths
    ]
```

  In `migrations.py`:

```python
def _scripting_depends_on(run_dir: Path, stage_defs: list[StageDef]) -> list[dict]:
    """Compute the synthetic styleboard's depends_on from the scripting
    artifact that actually exists at backfill time, so the reconstructed
    styleboard participates in the cascade like any other artifact (A-61)."""
    scripting_def = next((s for s in stage_defs if s.id == "scripting"), None)
    if scripting_def is None:
        return []
    latest = artifacts.latest_artifact_path(run_dir / stage_dir_name(scripting_def))
    if latest is None:
        return []
    return artifacts.compute_depends_on(run_dir, [latest])
```

  Thread `stage_defs` into `_backfill_one_project` and pass the result to both `_write_synthetic_artifact` calls.

- [ ] **Run.** Pass.
- [ ] **Commit:** `fix(migrations): backfilled styleboard records real depends_on (A-61)`

---

### T14 — A skipped project is findable, not stderr-only (A-74) ⭐ Three-Test Rule

- [ ] **Write the failing tests:**

```python
def test_a_skipped_project_records_an_error_event(conn, tmp_path, monkeypatch):
    """SURFACING. A-74: a per-project OSError/UnicodeDecodeError/YAMLError
    printed one line to stderr and continued. backfilled_projects records only
    successes, /doctor surfaces nothing about backfill, and an operator running
    under a service manager or a detached uvicorn never sees the stderr line."""
    recorded = []
    monkeypatch.setattr(migrations.obs, "record_event",
                        lambda c, **kw: recorded.append(kw) or 1)

    pid_bad = _legacy_project(conn, tmp_path, "legacy-bad", "approved")
    (tmp_path / "runs" / "legacy-bad" / "03-visual" / "artifact.v1.md").write_text(
        "---\nschema_version: 1\nstatus: 'unterminated\n---\n\nWORLD LOCK\n  x: y\n",
        encoding="utf-8",
    )
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    skips = [e for e in recorded if e["kind"] == "migration.backfill_skipped"]
    assert len(skips) == 1
    assert skips[0]["severity"] == "error"
    assert skips[0]["detail"]["project_id"] == pid_bad
    assert skips[0]["detail"]["run_id"] == "legacy-bad"
    assert "legacy-bad" in skips[0]["message"]


def test_a_run_with_no_skips_records_no_skip_event(conn, tmp_path, monkeypatch):
    """DISTINGUISHABILITY. A migration that skipped a project must be
    observably different from one that had nothing to do."""
    recorded = []
    monkeypatch.setattr(migrations.obs, "record_event",
                        lambda c, **kw: recorded.append(kw) or 1)
    _legacy_project(conn, tmp_path, "legacy-fine", "locked")
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)
    assert [e for e in recorded if e["kind"] == "migration.backfill_skipped"] == []


def test_a_failure_to_record_the_event_does_not_mask_the_skip(conn, tmp_path, monkeypatch):
    """FAULT. obs.record_event never raises by contract, but the migration must
    not depend on that: the loop still continues and the other project is still
    backfilled."""
    monkeypatch.setattr(migrations.obs, "record_event",
                        lambda c, **kw: (_ for _ in ()).throw(RuntimeError("db gone")))
    _legacy_project(conn, tmp_path, "legacy-bad2", "approved")
    (tmp_path / "runs" / "legacy-bad2" / "03-visual" / "artifact.v1.md").write_text(
        "---\nstatus: 'unterminated\n---\n\nWORLD LOCK\n  x: y\n", encoding="utf-8")
    pid_good = _legacy_project(conn, tmp_path, "legacy-good2", "locked")

    assert backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS) == [pid_good]
```

**§0 amendment 3 (pre-review, before dispatch):** all three tests above mock `obs.record_event`
entirely (`monkeypatch.setattr(migrations.obs, "record_event", lambda c, **kw: ...)`), so NONE of
them proves the event row is actually durably committed and readable using the CORRECT `conn` object
— a bug where the migration passed a stale, wrong, or already-closed connection to `record_event`
would go completely undetected, since the mock intercepts the call regardless of what `conn` argument
was passed. This is exactly the "second-connection idiom" defect class the orchestration prompt
flags as the single most repeated defect in P1 (4 instances). Add a FOURTH test that does NOT mock
`record_event` — it must actually run and read back a real row on a second connection to the same
database file:

```python
def test_a_skip_event_is_durably_committed_and_readable_on_a_second_connection(conn, tmp_path):
    """SURFACING, end-to-end. The other three tests all mock obs.record_event, so none of them
    proves the row survives using the CORRECT connection -- a wrong/stale conn object would pass
    those tests undetected. This test uses no mock: it runs the real migration against a real
    broken project, then reads the events table back on a SEPARATE connection to the same file."""
    import sqlite3

    db_path = tmp_path / "test.db"
    pid_bad = _legacy_project(conn, tmp_path, "legacy-bad3", "approved")
    (tmp_path / "runs" / "legacy-bad3" / "03-visual" / "artifact.v1.md").write_text(
        "---\nschema_version: 1\nstatus: 'unterminated\n---\n\nWORLD LOCK\n  x: y\n",
        encoding="utf-8",
    )
    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)

    second_conn = sqlite3.connect(db_path)
    second_conn.row_factory = sqlite3.Row
    try:
        rows = second_conn.execute(
            "SELECT kind, severity, message, detail FROM events WHERE kind = ?",
            ("migration.backfill_skipped",),
        ).fetchall()
    finally:
        second_conn.close()

    assert len(rows) == 1
    assert rows[0]["severity"] == "error"
    assert "legacy-bad3" in rows[0]["message"]
```

- [ ] **Run.** All four fail — there is no `obs.record_event` call.
- [ ] **Implement.** §0 amendment: `migrations.py` does not import `obs` yet — add
  `from pipeline_app import obs` to its imports (alongside the existing
  `from pipeline_app import artifacts, db as db_mod`). Then, in `backfill_styleboard_rows`'s
  except clause, keep the `print` (the orchestration plan's adoption rule):

```python
        except _PER_PROJECT_RECOVERABLE as exc:
            message = (
                "migrations.backfill_styleboard_rows: skipping project "
                f"{project_id} (run_id={project['run_id']!r}) -- unreadable, "
                f"malformed, or already-occupied styleboard: "
                f"{type(exc).__name__}: {exc}"
            )
            print(message, file=sys.stderr)
            # A-74: the print alone left the project with no styleboard row, so
            # `visual` was permanently locked and the styleboard page returned
            # "Stage not applicable to this project" -- a message asserting a
            # brand-scoping decision when the real cause is a failed migration.
            # The event row is what makes that findable.
            try:
                obs.record_event(
                    conn,
                    kind="migration.backfill_skipped",
                    severity="error",
                    source="migrations.backfill_styleboard_rows",
                    message=message,
                    detail={
                        "project_id": project_id,
                        "run_id": project["run_id"],
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                )
            except Exception:  # noqa: BLE001 -- recording must never mask the skip
                pass
            continue
```

- [ ] **Run.** Pass. Extend the pre-existing `test_backfill_skips_a_broken_legacy_project_without_blocking_others` with an event assertion (see §5).
- [ ] **Commit:** `fix(migrations): record an events row when a project is skipped (A-74)`

---

### T15 — The grounding pointer is pinned to a hash (A-80) ⭐ Three-Test Rule

- [ ] **Write the failing tests:**

```python
from pipeline_app.grounding_service import verify_pointer, write_pointer


def _setup(tmp_path, name="2026-08-08-topic.md", text="the brief as approved"):
    briefs = tmp_path / "rgs-briefs"
    briefs.mkdir(exist_ok=True)
    (briefs / name).write_text(text, encoding="utf-8")
    return tmp_path / "runs" / "r1" / "00-grounding"


def test_pointer_records_the_hash_size_and_time_of_its_target(tmp_path):
    """A-80: write_pointer stored a single key, rgs_brief_path -- no sha256, no
    version, no timestamp -- while snapshot_rgs_briefs computed a sha256 for
    every brief and identify_new_brief threw it away."""
    stage_dir = _setup(tmp_path)
    write_pointer(stage_dir, "rgs-briefs/2026-08-08-topic.md", tmp_path)
    data = yaml.safe_load((stage_dir / "pointer.yaml").read_text(encoding="utf-8"))
    assert data["rgs_brief_path"] == "rgs-briefs/2026-08-08-topic.md"
    assert len(data["sha256"]) == 64
    assert data["size"] == len(b"the brief as approved")
    assert data["written_at"].endswith("+00:00")


def test_editing_the_brief_under_an_approved_stage_is_detected(tmp_path):
    """FAULT. The brief an approved grounding stage points at could be
    rewritten with no staleness signal whatsoever."""
    stage_dir = _setup(tmp_path)
    write_pointer(stage_dir, "rgs-briefs/2026-08-08-topic.md", tmp_path)
    (tmp_path / "rgs-briefs" / "2026-08-08-topic.md").write_text(
        "a corrected brief", encoding="utf-8")

    status = verify_pointer(stage_dir, tmp_path)
    assert status.state == "hash_mismatch"
    assert status.recorded_sha256 != status.actual_sha256


def test_an_edited_brief_is_distinguishable_from_an_unchanged_one(tmp_path):
    """DISTINGUISHABILITY."""
    stage_dir = _setup(tmp_path)
    write_pointer(stage_dir, "rgs-briefs/2026-08-08-topic.md", tmp_path)
    assert verify_pointer(stage_dir, tmp_path).state == "ok"
    (tmp_path / "rgs-briefs" / "2026-08-08-topic.md").write_text("x", encoding="utf-8")
    assert verify_pointer(stage_dir, tmp_path).state == "hash_mismatch"


@pytest.mark.parametrize("state,setup", [
    ("no_pointer", lambda sd, rr: None),
    ("missing_target", lambda sd, rr: (rr / "rgs-briefs" / "2026-08-08-topic.md").unlink()),
])
def test_verify_pointer_names_each_broken_state_distinctly(tmp_path, state, setup):
    """SURFACING. Each state is a distinct, reportable value the caller records
    as an event and renders -- not a shared None."""
    stage_dir = _setup(tmp_path)
    if state != "no_pointer":
        write_pointer(stage_dir, "rgs-briefs/2026-08-08-topic.md", tmp_path)
    else:
        stage_dir.mkdir(parents=True, exist_ok=True)
    setup(stage_dir, tmp_path)
    assert verify_pointer(stage_dir, tmp_path).state == state
```

- [ ] **Run.** All fail — no `verify_pointer`, no hash in the pointer.
- [ ] **Implement** in `grounding_service.py`. §0 amendment: this file does not import `obs` yet —
  add `from pipeline_app import obs` (alongside the existing `hashlib`/`Path`/`yaml` imports).
  `verify_pointer`'s `obs.log(...)` call needs it:

```python
import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class PointerStatus:
    """no_pointer | unpinned | missing_target | hash_mismatch | ok"""
    state: str
    path: str | None = None
    recorded_sha256: str | None = None
    actual_sha256: str | None = None


def write_pointer(stage_dir: Path, rgs_brief_relpath: str, repo_root: Path) -> Path:
    """Point a grounding stage at the brief it produced, pinned to that brief's
    exact bytes.

    A-80: the pointer stored only rgs_brief_path, so the brief under an
    approved grounding stage could be rewritten with no staleness signal at
    all. The hashing machinery already existed -- snapshot_rgs_briefs computes
    a sha256 for every brief -- and was thrown away. `repo_root` is required,
    not optional, so an unmigrated caller fails loudly instead of silently
    writing an unpinned pointer.
    """
    target = repo_root / rgs_brief_relpath
    stage_dir.mkdir(parents=True, exist_ok=True)
    pointer_path = stage_dir / "pointer.yaml"
    _atomic_write_text(
        pointer_path,
        yaml.safe_dump(
            {
                "rgs_brief_path": rgs_brief_relpath,
                "sha256": _hash_file(target),
                "size": target.stat().st_size,
                "written_at": datetime.datetime.now(datetime.timezone.utc)
                .isoformat(timespec="seconds"),
            },
            sort_keys=False,
        ),
    )
    return pointer_path


def verify_pointer(stage_dir: Path, repo_root: Path) -> PointerStatus:
    """Whether a grounding stage's pinned brief is still the brief it approved."""
    pointer_path = stage_dir / "pointer.yaml"
    if not pointer_path.exists():
        return PointerStatus("no_pointer")
    relpath = read_pointer(stage_dir)
    data = yaml.safe_load(pointer_path.read_text(encoding="utf-8")) or {}
    recorded = data.get("sha256")
    target = repo_root / relpath
    if not target.exists():
        return PointerStatus("missing_target", relpath, recorded, None)
    actual = _hash_file(target)
    if not isinstance(recorded, str) or len(recorded) != 64:
        obs.log("grounding.pointer_unpinned", level="warning", pointer=str(pointer_path))
        return PointerStatus("unpinned", relpath, None, actual)
    if recorded != actual:
        return PointerStatus("hash_mismatch", relpath, recorded, actual)
    return PointerStatus("ok", relpath, recorded, actual)
```

- [ ] **Run.** Pass. Update `test_write_and_read_pointer_roundtrip` (`test_grounding_service.py:47-50`) for the new signature.
- [ ] **Commit:** `fix(grounding): pin the brief pointer to a sha256 and verify it (A-80)`

---

### T16 — Brief detection by set difference, with an explicit reason (A-81) ⭐ Three-Test Rule

- [ ] **Write the failing tests:**

```python
from pipeline_app.grounding_service import classify_brief_change


def test_a_new_brief_plus_an_unrelated_edit_still_identifies_the_brief():
    """FAULT. A-81: detection was "exactly one file changed, else nothing
    happened". A grounding turn that wrote its brief AND touched any other
    rgs-briefs/*.md -- a typo fix, a superseded-marker edit, an index update --
    returned None and the route recorded a perfectly good turn as no_artifact,
    orphaning the brief and running every downstream RGS stage with
    grounding_pointer=None."""
    before = {"index.md": "h0", "old.md": "h1"}
    after = {"index.md": "h0-edited", "old.md": "h1", "new-brief.md": "h2"}
    result = classify_brief_change(before, after)
    assert result.brief == "new-brief.md"
    assert result.added == ["new-brief.md"]
    assert result.modified == ["index.md"]


def test_zero_briefs_and_two_briefs_are_distinguishable():
    """DISTINGUISHABILITY. The zero-change case correctly reported nothing but
    was indistinguishable from the ambiguous case."""
    nothing = classify_brief_change({"a.md": "h1"}, {"a.md": "h1"})
    ambiguous = classify_brief_change({"a.md": "h1"},
                                      {"a.md": "h1", "b.md": "h2", "c.md": "h3"})
    assert nothing.brief is None and ambiguous.brief is None
    assert nothing.reason != ambiguous.reason
    assert nothing.reason == "no brief was written"
    assert "expected exactly 1" in ambiguous.reason


def test_the_ambiguous_reason_names_every_file_it_saw():
    """SURFACING. "produced N briefs, expected 1" explicitly, rather than
    collapsing to no_artifact."""
    result = classify_brief_change({}, {"b.md": "h2", "c.md": "h3"})
    assert "b.md" in result.reason and "c.md" in result.reason
    assert "2 added" in result.reason


def test_a_brief_written_into_a_subdirectory_is_seen(tmp_path):
    """snapshot_rgs_briefs globbed only the top level (glob, not rglob), so a
    brief in a subdirectory was invisible and produced the same false
    no_artifact."""
    briefs = tmp_path / "rgs-briefs"
    (briefs / "archive").mkdir(parents=True)
    (briefs / "archive" / "nested.md").write_text("nested", encoding="utf-8")
    (briefs / "top.md").write_text("top", encoding="utf-8")
    snap = grounding_service.snapshot_rgs_briefs(briefs)
    assert set(snap) == {"top.md", "archive/nested.md"}


def test_identify_new_brief_is_gone():
    """The old two-outcome API must not survive alongside the new one -- a
    caller left on it would keep collapsing a real brief to no_artifact."""
    assert not hasattr(grounding_service, "identify_new_brief")
```

- [ ] **Run.** All fail.
- [ ] **Implement:**

```python
@dataclass(frozen=True)
class BriefChange:
    brief: str | None
    added: list[str]
    modified: list[str]
    reason: str


def snapshot_rgs_briefs(rgs_briefs_dir: Path) -> dict[str, str]:
    """Relative posix path -> sha256 for every brief, RECURSIVELY (A-81)."""
    if not rgs_briefs_dir.exists():
        return {}
    return {
        p.relative_to(rgs_briefs_dir).as_posix(): _hash_file(p)
        for p in sorted(rgs_briefs_dir.rglob("*.md"))
        if p.is_file()
    }


def classify_brief_change(before: dict[str, str], after: dict[str, str]) -> BriefChange:
    """Which brief a grounding turn produced, and why the answer is what it is.

    Replaces identify_new_brief, which returned a bare str | None and collapsed
    every non-unit outcome into None (A-81). Renamed rather than re-typed so an
    unmigrated caller fails loudly instead of formatting a dataclass repr into
    a pointer path.
    """
    added = sorted(n for n in after if n not in before)
    modified = sorted(n for n in after if n in before and before[n] != after[n])
    if len(added) == 1:
        extra = f"; {len(modified)} other file(s) also modified" if modified else ""
        return BriefChange(added[0], added, modified, f"one brief added{extra}")
    if not added and len(modified) == 1:
        # A same-day rerun on the same topic overwrites the brief in place --
        # same filename, new content.
        return BriefChange(modified[0], added, modified, "one brief modified in place")
    if not added and not modified:
        return BriefChange(None, [], [], "no brief was written")
    return BriefChange(
        None, added, modified,
        f"expected exactly 1 new brief, found {len(added)} added and "
        f"{len(modified)} modified: " + ", ".join(added + modified),
    )
```

  Delete `identify_new_brief`.

- [ ] **Run.** Pass.
- [ ] **Commit:** `fix(grounding): classify brief changes by set difference with an explicit reason (A-81)`

---

### T17 — `read_pointer` validates shape and containment (A-82)

- [ ] **Write the failing tests:**

```python
from pipeline_app.grounding_service import InvalidPointerError, read_pointer


@pytest.mark.parametrize("content,fragment", [
    ("just a scalar\n", "not a mapping"),
    ("- a\n- b\n", "not a mapping"),
    ("rgs_brief_path: 42\n", "not a string"),
    ("rgs_brief_path: null\n", "not a string"),
    ("other_key: x\n", "not a string"),
    ("rgs_brief_path: 'unterminated\n", "not valid YAML"),
])
def test_a_malformed_pointer_raises_a_named_error_not_attributeerror(tmp_path, content, fragment):
    """A-82: `yaml.safe_load(...) or {}` guarded only the empty case -- a bare
    scalar or a list parsed to a non-mapping and the immediate .get() raised
    AttributeError and a bare 500."""
    stage_dir = tmp_path / "00-grounding"
    stage_dir.mkdir()
    (stage_dir / "pointer.yaml").write_text(content, encoding="utf-8")
    with pytest.raises(InvalidPointerError) as exc:
        read_pointer(stage_dir)
    assert fragment in str(exc.value)


@pytest.mark.parametrize("value", [
    "C:/Windows/System32/drivers/etc/hosts",
    "/etc/passwd",
    "rgs-briefs/../../pipeline-app/pipeline.db",
    "docs/style-library.md",
    "../secrets.md",
])
def test_a_pointer_outside_rgs_briefs_is_refused(tmp_path, value):
    """resolve_latest_artifact joins the stored value with repo_root / pointer,
    and pathlib lets an ABSOLUTE value override the base entirely -- a
    hand-repaired pointer could make the app read and render a file anywhere on
    the machine. write_pointer was non-atomic (A-63), so a hand-repaired
    pointer is a realistic operator action."""
    stage_dir = tmp_path / "00-grounding"
    stage_dir.mkdir()
    (stage_dir / "pointer.yaml").write_text(
        f"rgs_brief_path: {value!r}\n", encoding="utf-8")
    with pytest.raises(InvalidPointerError) as exc:
        read_pointer(stage_dir)
    assert "rgs-briefs" in str(exc.value)


def test_an_absent_pointer_is_distinguishable_from_a_broken_one(tmp_path):
    """DISTINGUISHABILITY: None means "no pointer", never "the pointer is
    garbage"."""
    stage_dir = tmp_path / "00-grounding"
    stage_dir.mkdir()
    assert read_pointer(stage_dir) is None
    (stage_dir / "pointer.yaml").write_text("[]\n", encoding="utf-8")
    with pytest.raises(InvalidPointerError):
        read_pointer(stage_dir)
```

- [ ] **Run.** All fail with `AttributeError` or a returned value.
- [ ] **Implement:**

```python
from pathlib import PurePosixPath, PureWindowsPath

_POINTER_ROOT = "rgs-briefs"


class InvalidPointerError(Exception):
    """pointer.yaml exists but is not a usable pointer."""


def read_pointer(stage_dir: Path) -> str | None:
    """The brief path a grounding stage points at, or None if there is no
    pointer at all. A pointer that EXISTS but is unusable raises -- returning
    None for both would put a hand-broken pointer and an un-run stage in the
    same bucket (A-82)."""
    pointer_path = stage_dir / "pointer.yaml"
    if not pointer_path.exists():
        return None
    try:
        data = yaml.safe_load(pointer_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise InvalidPointerError(f"{pointer_path}: not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise InvalidPointerError(
            f"{pointer_path}: parsed to "
            f"{'nothing' if data is None else type(data).__name__}, not a mapping"
        )
    value = data.get("rgs_brief_path")
    if not isinstance(value, str) or not value.strip():
        raise InvalidPointerError(f"{pointer_path}: rgs_brief_path is missing or not a string")
    normalised = value.replace("\\", "/")
    parts = PureWindowsPath(normalised).parts
    if (
        PureWindowsPath(normalised).is_absolute()
        or PurePosixPath(normalised).is_absolute()
        or ".." in parts
        or parts[:1] != (_POINTER_ROOT,)
    ):
        raise InvalidPointerError(
            f"{pointer_path}: rgs_brief_path {value!r} must be a relative path under "
            f"{_POINTER_ROOT}/ -- refusing to read outside the brief directory"
        )
    return value
```

- [ ] **Run.** Pass. Confirm the three `resolve_latest_artifact` grounding tests in `test_artifacts.py:90-115` still pass.
- [ ] **Commit:** `fix(grounding): validate pointer shape and refuse paths outside rgs-briefs (A-82)`

---

### T18 — The durability contract test class (F-18)

The three S0s are properties of the same module and share one missing test class. T1–T5 and T11–T12 each proved one writer; this task makes the property **uniform and parametrized** so a fourth writer added later cannot skip it.

- [ ] **Write the class** in `pipeline-app/tests/test_artifacts.py`:

```python
class TestDurabilityContract:
    """Every path that rewrites a file an operator can lose must satisfy all
    four clauses. F-18: nothing asserted that a write is atomic, that version
    allocation is exclusive, or that a migration cannot overwrite an existing
    file -- and all three S0s live in that gap.

    Crash injection is done by monkeypatching os.replace / os.fsync rather than
    by killing a subprocess: the failure point is exact and the test is
    deterministic, and the conftest guard (P0) blocks unmarked subprocess use
    anyway. The property under test is "the target is old-bytes or new-bytes,
    never in between", which does not need a real SIGKILL to exercise.
    """

    WRITERS = ["write_artifact", "stamp_final", "record_gate_override", "write_pointer"]

    @staticmethod
    def _prepare(tmp_path, writer):
        """Returns (target_path, invoke_callable) for the named writer."""
        if writer == "write_pointer":
            briefs = tmp_path / "rgs-briefs"
            briefs.mkdir()
            (briefs / "a.md").write_text("a", encoding="utf-8")
            (briefs / "b.md").write_text("b", encoding="utf-8")
            sd = tmp_path / "runs" / "r1" / "00-grounding"
            grounding_service.write_pointer(sd, "rgs-briefs/a.md", tmp_path)
            return sd / "pointer.yaml", lambda: grounding_service.write_pointer(
                sd, "rgs-briefs/b.md", tmp_path)
        path = write_artifact(tmp_path, 1, {"status": "final", "version": 1}, "approved body")
        if writer == "write_artifact":
            return path, lambda: artifacts.write_artifact(
                tmp_path, 2, {"status": "draft", "version": 2}, "v2 body")
        if writer == "stamp_final":
            return path, lambda: artifacts.stamp_final(path, "2026-08-08T00:00:00+00:00")
        return path, lambda: artifacts.record_gate_override(
            path, "accepted", at="2026-08-08T00:00:00+00:00")

    @pytest.mark.parametrize("writer", WRITERS)
    @pytest.mark.parametrize("break_at", ["fsync", "replace"])
    def test_prior_bytes_survive_a_crash_at_any_point(self, tmp_path, monkeypatch,
                                                      writer, break_at):
        target, invoke = self._prepare(tmp_path, writer)
        before = target.read_bytes()
        monkeypatch.setattr(
            os, break_at,
            lambda *a, **k: (_ for _ in ()).throw(OSError(f"crash at {break_at}")),
        )
        with pytest.raises(OSError):
            invoke()
        assert target.read_bytes() == before

    @pytest.mark.parametrize("writer", WRITERS)
    def test_no_temp_file_is_left_behind_or_selectable(self, tmp_path, monkeypatch, writer):
        target, invoke = self._prepare(tmp_path, writer)
        monkeypatch.setattr(os, "replace",
                            lambda *a, **k: (_ for _ in ()).throw(OSError("crash")))
        with pytest.raises(OSError):
            invoke()
        assert not list(target.parent.glob("*.tmp"))
        assert artifacts.latest_artifact_path(target.parent) in (None, target) or \
            target.name == "pointer.yaml"

    @pytest.mark.parametrize("writer", WRITERS)
    def test_the_target_is_never_observed_zero_length(self, tmp_path, monkeypatch, writer):
        """The specific shape truncation takes: a zero-byte or half-written
        target that parse_frontmatter used to report as a legitimate
        no-frontmatter artifact (A-63 -> A-68)."""
        target, invoke = self._prepare(tmp_path, writer)
        sizes = []
        real_replace = os.replace

        def observe(src, dst, *a, **k):
            sizes.append(Path(dst).stat().st_size if Path(dst).exists() else -1)
            return real_replace(src, dst, *a, **k)

        monkeypatch.setattr(os, "replace", observe)
        invoke()
        assert all(s != 0 for s in sizes), "the target was truncated before the rename"
        assert target.stat().st_size > 0
```

- [ ] Add the migration leg to `pipeline-app/tests/test_migrations.py`:

```python
def test_durability_contract_backfill_refuses_a_populated_stage_dir(conn, tmp_path):
    """F-18's third clause: test_migrations.py never placed a real artifact
    where the backfill writes."""
    _legacy_project(conn, tmp_path, "legacy-dur", "approved", sheet=LEGACY_SHEET)
    d = tmp_path / "runs" / "legacy-dur" / "02b-styleboard"
    d.mkdir(parents=True)
    real = d / "artifact.v1.md"
    real.write_text("---\nversion: 1\nstatus: final\n---\n\nreal\n", encoding="utf-8")
    sha = artifacts.compute_sha256(real)

    backfill_styleboard_rows(conn, tmp_path, STAGE_DEFS)
    assert artifacts.compute_sha256(real) == sha
```

- [ ] **Run.** Confirm every parametrization passes and that removing `_atomic_write_text` from any one writer makes exactly that writer's parametrization fail.
- [ ] **Run both suites** to confirm nothing else in the app regressed:

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app" && python -m pytest -q
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767" && python -m pytest tests/ -q
```

  Cross-package failures in `test_routes_stages.py`, `test_routes_approve_edit.py`, `test_turn_service.py`, `test_approval_service.py`, `test_routes_chat_sse.py` and `test_main.py` are **expected** and belong to P3/P4 — see §6. Report them to the orchestrator; do not fix them here.

- [ ] **Commit:** `test(artifacts): durability contract for every artifact writer (F-18)`

---

## 4. Finding → test map

| Finding | Test(s) | File | Three-Test role |
|---|---|---|---|
| **A-63** (S0, silent) | `test_atomic_write_leaves_prior_bytes_intact_when_the_write_dies_midway` | test_artifacts.py | **fault** |
| | `test_the_target_is_never_observed_zero_length[*]` | test_artifacts.py | **distinguishability** (a written target is never the zero-length shape a truncation leaves) |
| | `test_approval_stamp_does_not_destroy_the_approved_artifact_on_crash[*]`, `test_atomic_write_leaves_no_temp_file_behind_on_failure` | test_artifacts.py | **surfacing** (the write raises `OSError` to the caller instead of returning after destroying the file) |
| **A-65** (S0, silent) | `test_two_concurrent_callers_get_two_distinct_versions` | test_artifacts.py | **fault** |
| | `test_many_concurrent_callers_all_get_distinct_versions` | test_artifacts.py | **distinguishability** (N callers → N versions, never N−1) |
| | `test_write_artifact_refuses_to_overwrite_an_existing_version` | test_artifacts.py | **surfacing** (`ArtifactExistsError` naming the path) |
| **A-73** (S0, silent) | `test_backfill_refuses_to_overwrite_a_real_styleboard_artifact` | test_migrations.py | **fault** |
| | `test_a_crash_between_the_artifact_write_and_the_db_row_does_not_churn_the_artifact` | test_migrations.py | **distinguishability** (our own synthetic is adopted; anyone else's is refused) |
| | `test_refusing_to_overwrite_records_an_error_event` | test_migrations.py | **surfacing** |
| | `test_backfill_allocates_its_version_rather_than_hardcoding_one`, `test_durability_contract_backfill_refuses_a_populated_stage_dir` | test_migrations.py | supporting |
| **A-66** (S3, latent) | `test_deleting_the_newest_artifact_does_not_reissue_its_version`, `test_high_water_mark_survives_deleting_every_artifact`, `test_read_artifact_rejects_a_frontmatter_version_that_disagrees_with_the_filename`, `test_corrupt_high_water_mark_is_warned_and_ignored_not_fatal` | test_artifacts.py | n/a (latent) |
| **A-67** (S3, silent) | `test_zero_padded_duplicate_does_not_make_latest_artifact_nondeterministic` | test_artifacts.py | **fault** |
| | `test_v10_still_outranks_v9` | test_artifacts.py | **distinguishability** (the real ordering keeps working while the fake tie is removed) |
| | `test_unparseable_sibling_is_warned_and_enumerable_not_silently_dropped` | test_artifacts.py | **surfacing** (`obs.log` + `list_unversioned_siblings` for /doctor) |
| **A-68** (S2, silent) | `test_unterminated_frontmatter_raises_instead_of_masquerading_as_unversioned` | test_artifacts.py | **fault** |
| | `test_truncated_artifact_is_distinguishable_from_a_genuinely_plain_one`, `test_empty_frontmatter_block_is_still_an_empty_mapping` | test_artifacts.py | **distinguishability** |
| | `test_a_truncated_artifact_names_its_own_path_in_the_error` | test_artifacts.py | **surfacing** |
| **A-69** (S2, loud) | `test_non_mapping_frontmatter_raises_a_named_error_not_attributeerror[str\|list\|int]`, `test_malformed_yaml_is_contained_into_one_predictable_error`, `test_a_body_starting_with_a_horizontal_rule_is_rejected_not_misparsed` | test_artifacts.py | n/a (loud) |
| **A-38** (S2, silent) | `test_two_overrides_on_one_artifact_both_survive` | test_artifacts.py | **fault** |
| | `test_a_legacy_scalar_override_is_migrated_forward_not_dropped`, `test_stamp_final_override_lands_in_the_same_append_only_list` | test_artifacts.py | **distinguishability** (two overrides ≠ one override) |
| | `test_an_override_on_an_already_final_artifact_carries_a_timestamp` | test_artifacts.py | **surfacing** |
| **A-37** (S2, silent) | `test_read_gate_overrides_is_empty_for_an_artifact_with_none` | test_artifacts.py | **distinguishability** (`[]` ≠ an override list) |
| | `test_two_overrides_on_one_artifact_both_survive` (via `read_gate_overrides`) | test_artifacts.py | **fault** + **surfacing** (the accessor the gates panel renders; UI leg is P15's — §6) |
| **A-61** (S2, silent) | `test_backfilled_styleboard_records_the_scripting_artifact_it_was_built_against` | test_migrations.py | **fault** |
| | `test_a_backfilled_styleboard_goes_stale_when_its_script_is_rewritten` | test_migrations.py | **distinguishability** (`is_stale` now returns True where it returned False) |
| | `test_backfilled_artifact_records_an_explicit_gates_key` | test_migrations.py | **surfacing** |
| **A-74** (S2, silent) | `test_a_failure_to_record_the_event_does_not_mask_the_skip` | test_migrations.py | **fault** |
| | `test_a_run_with_no_skips_records_no_skip_event` | test_migrations.py | **distinguishability** |
| | `test_a_skipped_project_records_an_error_event` | test_migrations.py | **surfacing** |
| **A-80** (S1, silent) | `test_editing_the_brief_under_an_approved_stage_is_detected` | test_grounding_service.py | **fault** |
| | `test_an_edited_brief_is_distinguishable_from_an_unchanged_one` | test_grounding_service.py | **distinguishability** |
| | `test_verify_pointer_names_each_broken_state_distinctly[no_pointer\|missing_target]`, `test_pointer_records_the_hash_size_and_time_of_its_target` | test_grounding_service.py | **surfacing** |
| **A-81** (S2, silent) | `test_a_new_brief_plus_an_unrelated_edit_still_identifies_the_brief`, `test_a_brief_written_into_a_subdirectory_is_seen` | test_grounding_service.py | **fault** |
| | `test_zero_briefs_and_two_briefs_are_distinguishable` | test_grounding_service.py | **distinguishability** |
| | `test_the_ambiguous_reason_names_every_file_it_saw`, `test_identify_new_brief_is_gone` | test_grounding_service.py | **surfacing** |
| **A-82** (S4, loud) | `test_a_malformed_pointer_raises_a_named_error_not_attributeerror[6 cases]`, `test_a_pointer_outside_rgs_briefs_is_refused[5 cases]`, `test_an_absent_pointer_is_distinguishable_from_a_broken_one` | test_grounding_service.py | n/a (loud) |
| **F-18** (S1, coverage-gap) | `TestDurabilityContract` (3 methods × 4 writers × 2 crash points), `test_durability_contract_backfill_refuses_a_populated_stage_dir` | test_artifacts.py, test_migrations.py | n/a (coverage-gap) |

---

## 5. Tests deleted, inverted, or rewritten

No test in this package's three files asserts that a defect is correct, so nothing is **inverted**. Four are **rewritten** for changed APIs and one is **extended**; each is listed by file:line against the pre-change file.

| File:line | Test | Action | Replacement |
|---|---|---|---|
| `pipeline-app/tests/test_grounding_service.py:22-25` | `test_identify_new_brief_when_exactly_one_new_file` | **Rewritten** | `test_classify_brief_change_when_exactly_one_new_file` — same input, asserts `result.brief == "c.md"` and `result.added == ["c.md"]`. The function it named no longer exists (T16). |
| `pipeline-app/tests/test_grounding_service.py:28-29` | `test_identify_new_brief_returns_none_when_zero_new_files` | **Rewritten** | Folded into `test_zero_briefs_and_two_briefs_are_distinguishable`, which additionally asserts the two `None` outcomes carry **different reasons** — the distinguishability the old test could not express. |
| `pipeline-app/tests/test_grounding_service.py:32-35` | `test_identify_new_brief_returns_none_when_ambiguous` | **Rewritten** | Folded into the same test plus `test_the_ambiguous_reason_names_every_file_it_saw`. The `None` outcome is still correct for 2 added briefs; what changes is that the reason now names them. |
| `pipeline-app/tests/test_grounding_service.py:38-44` | `test_identify_new_brief_detects_same_filename_changed_content` | **Rewritten** | `test_classify_brief_change_detects_same_filename_changed_content` — same assertion via `result.brief`; its docstring's warning about the "old set-difference check" stays accurate and stays. |
| `pipeline-app/tests/test_grounding_service.py:47-50` | `test_write_and_read_pointer_roundtrip` | **Rewritten** | Same name; gains the required `repo_root` third argument and asserts the pointer's `sha256` round-trips too (T15). |
| `pipeline-app/tests/test_grounding_service.py:11-19` | `test_snapshot_returns_filename_to_content_hash` | **Extended** | Keys are now run-relative posix paths; for top-level files these equal the old `p.name` so the existing assertions stand unchanged. Extended by `test_a_brief_written_into_a_subdirectory_is_seen`. |
| `pipeline-app/tests/test_migrations.py:113-134` | `test_backfill_skips_a_broken_legacy_project_without_blocking_others` | **Extended** | Keeps every current assertion (the skip, the retry, the untouched good project) and gains the A-74 surfacing assertion: exactly one `migration.backfill_skipped` event of severity `error` naming `legacy-bad`. Its "nothing was committed for the broken project" comment stays true — the risky read still precedes every DB write. |
| `pipeline-app/tests/test_artifacts.py:27-30` | `test_parse_frontmatter_on_plain_text_returns_empty_meta` | **Kept, unchanged** | This is the one legitimate `({}, text)` case and must keep passing. Pinned deliberately so T8 cannot over-reach into it. |
| `pipeline-app/tests/test_artifacts.py:33-46` | the four `next_version_number` / `latest_artifact_path` tests | **Kept, unchanged** | They pass against the high-water-mark implementation (T6) with no edit. If any of them requires editing, the implementation is wrong. |

**Nothing in these three files matches the audit's six defect-affirming tests**, and `grep -rn "returns_empty_on_fetch_failure\|scoped_permissions_settings_scopes"` over them returns nothing.

---

## 6. Contract for P3 (and the P4/P15 touchpoints)

Every signature below is **frozen by this package**. Call them as specified.

### 6.1 The A-61 fix P3's hand-edit route must call

`routes/stages.py`'s `edit_stage_output_route` currently writes:

```python
"depends_on": prior_meta.get("depends_on", []),
```

**This is the sticky node.** Copying the prior artifact's `depends_on` forward means that once any version records `[]` — which the backfill did on every migrated project, and which a truncated or hand-edited artifact produces via `parse_frontmatter` — every later hand edit inherits it and the entire downstream staleness cascade terminates at that stage forever. Recompute it. Call:

```python
# pipeline_app/artifacts.py -- FROZEN
def relpath_in_run(path: Path, run_dir: Path) -> str: ...

def compute_depends_on(run_dir: Path, upstream_paths: Iterable[Path]) -> list[dict]:
    """[{"path": "<run-relative posix path>", "sha256": "<64 hex>"}, ...]
    Exactly the shape state_machine.is_stale compares against and
    turn_service.run_stage_turn already records."""
```

The replacement in `edit_stage_output_route`:

```python
upstream_defs = [s for s in stage_defs if s.id in stage_def.depends_on]
upstream_paths = [
    p for p in (
        artifacts.latest_artifact_path(run_dir / stage_dir_name(u)) for u in upstream_defs
    ) if p is not None
]
...
    "depends_on": artifacts.compute_depends_on(run_dir, upstream_paths),
```

P4 should replace `turn_service._current_upstream_hashes`' sibling construction at `turn_service.py:233-236` with the same call so there is one implementation, not two.

### 6.2 Signatures P3 must update (each fails loudly if missed)

```python
# pipeline_app/artifacts.py
def reserve_version(stage_dir: Path, *, max_attempts: int = 256) -> VersionReservation
def write_reserved_artifact(reservation: VersionReservation, meta: dict, body: str) -> Path
def release_version(reservation: VersionReservation) -> None
def write_artifact(stage_dir: Path, version: int, meta: dict, body: str) -> Path
    # UNCHANGED signature; now raises ArtifactExistsError instead of overwriting.
def next_version_number(stage_dir: Path) -> int
    # UNCHANGED signature; now ADVISORY ONLY. Anything about to write must use
    # reserve_version. Leaving the edit route on next_version_number turns the
    # A-65 race from a silent lost write into a 500 -- better, but not closed.

def read_artifact(path: Path) -> tuple[dict, str]           # NEW
def parse_frontmatter(text: str) -> tuple[dict, str]        # now RAISES MalformedArtifactError
def read_gate_overrides(path: Path) -> list[dict]           # NEW
def list_unversioned_siblings(stage_dir: Path) -> list[Path]  # NEW
def stamp_final(path, finalized_at, gate_override_reason=None, *, actor=None) -> None
    # UNCHANGED for approval_service's current call.
def record_gate_override(path: Path, reason: str, *, at: str, actor: str | None = None) -> None
    # `at` is REQUIRED and keyword-only (A-38).

class MalformedArtifactError(Exception):   # .reason, .path
class ArtifactExistsError(Exception): ...
```

```python
# pipeline_app/grounding_service.py
def write_pointer(stage_dir: Path, rgs_brief_relpath: str, repo_root: Path) -> Path
    # repo_root is REQUIRED (A-80).
def read_pointer(stage_dir: Path) -> str | None
    # None ONLY when pointer.yaml is absent; raises InvalidPointerError otherwise (A-82).
def verify_pointer(stage_dir: Path, repo_root: Path) -> PointerStatus
def classify_brief_change(before: dict[str, str], after: dict[str, str]) -> BriefChange
    # REPLACES identify_new_brief, which is deleted (A-81).
def snapshot_rgs_briefs(rgs_briefs_dir: Path) -> dict[str, str]
    # Keys are now run-relative posix paths, recursive (A-81).

class InvalidPointerError(Exception): ...
@dataclass PointerStatus:  state, path, recorded_sha256, actual_sha256
@dataclass BriefChange:    brief, added, modified, reason
```

### 6.3 Required call-site changes in P3's files

1. **`routes/stages.py:186-189`** — the grounding turn's `no_artifact` branch:

```python
change = grounding_service.classify_brief_change(before, after)
if change.brief is not None:
    grounding_service.write_pointer(grounding_dir, f"rgs-briefs/{change.brief}", repo_root)
    db_mod.update_stage_status(conn, stage_row["id"], "awaiting_review")
else:
    obs.record_event(conn, kind="grounding.brief_not_identified", severity="warning",
                     source="routes.stages", message=change.reason,
                     detail={"added": change.added, "modified": change.modified})
    db_mod.update_stage_status(conn, stage_row["id"], "no_artifact")
```

2. **`routes/stages.py:157-160`** — `stage_chat` injects `grounding_pointer` into every downstream RGS kickoff prompt with **no existence check** (A-80). Call `verify_pointer(grounding_dir, repo_root)` and inject only on `state == "ok"`; record an event and surface staleness on `hash_mismatch`/`missing_target`.

3. **`approval_service.py:76`** — `artifacts.record_gate_override(latest, override_reason)` must become `artifacts.record_gate_override(latest, override_reason, at=now)`.

4. **`routes/stages.py:100`, `:251`, `approval_service.py:43`** — wrap `parse_frontmatter` / `read_artifact` in `except artifacts.MalformedArtifactError` and return a 4xx/5xx naming `exc.path`, plus an `obs.record_event`. A `MalformedArtifactError` reaching the user as a bare 500 is a regression, not a fix.

5. **`turn_service.py:74` (P4)** — the highest-value wrap. `propagate_staleness`'s phase-1 loop must catch `MalformedArtifactError` **per dependent** and continue, recording an event, so one malformed dependent no longer aborts the cascade mid-iteration leaving some stages flipped and the rest silently `approved` (A-69).

### 6.4 The A-37 render leg (P15)

`read_gate_overrides(latest)` is the accessor. `stage_page` must put it in the template context and `stage.html` must render each `{reason, at, actor}` next to the failing gate it excuses. Without that leg the override remains write-only in the UI, and A-37 is only half closed — this package closes the data half and provides the accessor; it cannot edit `stage.html`.

---

## 7a. Post-PR-#27 adversarial review findings (2026-08-12) — filed, NOT fixed

After PR #27 (this package's implementation) was opened, 18 independent Opus subagents each
adversarially reviewed one task's shipped diff against its brief, hunting for plan deviations,
hardcoded values, silent failures, and anything else suspicious. Several findings were spot-verified
directly (empirical reproduction, live test runs, not just reasoning) before filing. **Per explicit
instruction, none of these are fixed in this package — they are documented here for a future
remediation task/package to pick up.** IDs below are new (`P2R-nn`), not part of the original 328
`A`/`B`/`C`/`D`/`F`-prefixed audit findings, since they were discovered by a later review pass, not
the original audit.

### P2R-01 (Important) — A-65 is only partially closed: neither production caller uses `reserve_version`, and `ArtifactExistsError` has nowhere to land

§6.2 above already flagged that leaving `routes/stages.py`/`turn_service.py` on `next_version_number`
"turns the A-65 race from a silent lost write into a 500 -- better, but not closed" and deferred the
migration to P3/P4. The review adds detail the plan didn't have: **verified** both call sites are
still unmigrated (`routes/stages.py:253,280`; `turn_service.py:233,254`), `write_artifact`'s own
anti-clobber check (`artifacts.py:214`, `if path.exists()`) is itself a check-then-act race — nothing
stops two concurrent requests from both passing the check before either writes — and **when
`ArtifactExistsError` does fire, nothing catches it in either caller.** In the sync edit route
(`routes/stages.py`) it's a bare 500 after `raw_output.md` has already been overwritten with the
submitted body, orphaned with no artifact version backing it. In the async turn route
(`turn_service.py:254`) it is worse: the raise happens *after* `record_turn(..., "complete",
cost_usd)` (turn billed, marked complete) and *before* `update_stage_status`/`propagate_staleness` —
the SSE stream just silently closes with no error frame, the DB is left half-updated, and there is no
operator-visible signal at all. P3/P4 should not treat "wire up `reserve_version`" as sufficient;
both callers also need a landing place for the exception.

### P2R-02 (Important) — the version regex is still not injective: Unicode decimal digits collide with ASCII ones

`artifacts.py`'s `_VERSION_RE = re.compile(r"^artifact\.v(0|[1-9]\d*)\.md$")` (T7, A-67) claims
"exactly one filename maps to any given version." **Verified empirically on this host:**
`artifact.v1٧.md` (containing U+0667 ARABIC-INDIC DIGIT SEVEN, which `\d` matches in a `str` pattern
and `int()` parses) matches the regex and parses to **17**, colliding with `artifact.v17.md`. Neither
`_versions_in` nor `obs.log`/`list_unversioned_siblings` flags the shadow file. Fix should anchor the
digit class to ASCII (`[0-9]` instead of `\d`) and anchor with `\Z` instead of `$` (a trailing
newline in a caller-supplied filename currently still matches).

### P2R-03 (Important) — `list_unversioned_siblings` (A-67) has zero production callers; its own docstring's claim is fiction

`list_unversioned_siblings`'s docstring says it's "exposed so /doctor (P1) can show an operator" an
unrecognized file. **Verified:** grep across the repo shows the only caller is its own test; `/doctor`
never imports it. `obs.log(...)` (the warning path) writes to stderr and a log file only —
`/doctor`'s events surface renders `events` table rows written by `obs.record_event`, which this path
never calls. Neither channel currently reaches an operator. Not scheduled in any later plan task
(grepped `docs/superpowers/plans/remediation/` and the SDD workspace). Needs a wiring task, or the
docstring should stop claiming behavior that doesn't exist.

### P2R-04 (Important) — `TestDurabilityContract`'s zero-length test (F-18, T18) is non-discriminating for ALL FOUR writers, not just `write_artifact`

The already-known, already-accepted gap ("2 of `write_artifact`'s 3 durability cases don't
discriminate for that writer") turns out to be a symptom of a broader test-design flaw, not a
`write_artifact`-specific one. **Verified by mutation:** reverting `_atomic_write_text` in both
`artifacts.py` and `grounding_service.py` to a naive truncating `write_text` makes 12 of the class's
16 parametrized cases correctly fail — but `test_the_target_is_never_observed_zero_length[*]` passes
for **all four writers**, every time. Root cause: the observer records
`Path(dst).stat().st_size` *before* `os.replace` fires, i.e. the size of whatever the test fixture
already put at that path — for a brand-new target this is `-1` (file doesn't exist yet, so `all(s !=
0 ...)` is vacuously true), for an existing target it's the fixture's own pre-written size, never the
value the primitive is supposed to guard against. The task's own §"Run" verification checklist item —
confirm each writer's parametrization fails independently when its atomic write is removed — appears
to not have actually been carried out against this specific method, since it clearly does not fail
for any of the four. Needs the test rewritten to observe the destination's size *after* a genuine
partial-write injection, not before a successful `os.replace`.

### P2R-05 (Minor) — the migration-side "durability contract" test (T18, F-18) doesn't inject a crash at all

`test_durability_contract_backfill_refuses_a_populated_stage_dir` has no `monkeypatch`, so it tests
no atomicity property — it's a near-duplicate of two pre-existing T11 tests
(`test_backfill_refuses_to_overwrite_a_real_styleboard_artifact`,
`test_refusing_to_overwrite_records_an_error_event`), asserting *strictly less* than either (no
`pid not in touched` check, no error-event check). Net new coverage is close to zero. Either give it
a real crash injection inside `_write_synthetic_artifact`, or drop it as redundant.

### P2R-06 (Important) — the migration's idempotent adoption (A-73, T11/T12) always adopts, never re-checks whether its prior output is still the best available reconstruction

`_adoptable_synthetic` returns the migration's own prior synthetic unconditionally once it recognizes
it (`backfilled=True` + matching `run_id`) — the freshly-recomputed `body`/`depends_on` arguments are
discarded silently, no log, no event. Concrete scenario matching the S0's own crash-recovery premise:
boot 1 finds no liftable `WORLD LOCK`, writes the "not recoverable" placeholder, crashes before the DB
row lands; the operator later re-runs the visual stage so a real `WORLD LOCK` now exists; boot 2
recomputes the real content — and adoption throws it away, permanently pinning the project to the
stale placeholder with no signal anywhere. This also silently defeats T13's `depends_on` computation
for exactly the population it exists to fix (any project already carrying a pre-T13 synthetic).
Adoption should compare the recomputed body/depends_on against the existing artifact and only adopt
when they genuinely match; otherwise reserve a new version.

### P2R-07 (Important) — the per-project skip event (A-74, T14) re-fires unbounded on every app boot, capable of flooding /doctor

A permanently-broken legacy project (or a permanently-refused overwrite, T11's S0 case) is retried —
by design — on every `create_app`, and now writes a fresh `severity="error"` events row each time,
with no dedup and no "already reported" check. One broken project across enough restarts (routine for
a locally-run app) can fill `/doctor`'s entire 50-row unacknowledged-events window with identical
rows, evicting every other genuinely different unacknowledged error. Needs a dedup key (e.g. suppress
if an unacknowledged row with the same `kind` + `detail.project_id` already exists).

### P2R-08 (Important) — `reserve_version`/`write_artifact` can leak a reservation marker or fail an already-durable write if the HWM sidecar write fails

`reserve_version` (`artifacts.py`) calls `_record_high_water_mark` *outside* any try/except, after
the `O_CREAT|O_EXCL` marker already exists on disk; if that call raises (retry exhaustion under
sustained Windows contention, or `ENOSPC`), the marker is never unlinked — a permanent leak that
permanently burns that version number with no operator recourse (no reaper exists anywhere in the
repo). `write_artifact` has the same shape in the other direction: the artifact write succeeds
durably, then `_record_high_water_mark` may raise — the caller sees an exception for a write that
already fully landed, and cannot retry (the next attempt hits `ArtifactExistsError`). The HWM sidecar
was designed as best-effort bookkeeping; it should not be able to fail an already-completed operation
or leak a reservation.

### P2R-09 (Minor) — `_high_water_mark`'s read-retry contradicts its own sibling fallback design

The corrupt-HWM branch (unreadable/non-digit sidecar content) is explicitly "warned and ignored, not
fatal." But if the sidecar is deleted between the `.exists()` check and the read (a real Windows
concurrent-rename window this same function already retries for), the retry loop re-raises
`FileNotFoundError` after 50 attempts instead of falling back the same way. Also: the retry counts
(`range(50)`, `attempt == 49`) are duplicated magic numbers in two separate loops with no shared
constant — changing one without the other could silently convert "always re-raise on exhaustion" into
"silently exit without writing and without raising."

### P2R-10 (Minor) — `write_reserved_artifact` never validates the written version matches the reservation

`write_reserved_artifact` (T5) writes whatever `meta["version"]` the caller supplies without checking
it equals `reservation.version`. `read_artifact` (T6) enforces exactly this invariant on read
(frontmatter-vs-filename cross-check) — so a caller bug here would put the app into a state its own
read path is designed to reject. No live caller trips this today (`migrations.py` always passes
`reservation.version`), but the write path lacks the same-package guarantee its read path enforces.

### P2R-11 (Important) — gate-override append (A-38, T10) has a real concurrent-write data-loss window

`_append_override`'s read-modify-write (`read_artifact` → mutate list → `_atomic_write_text`) has no
lock. Two concurrent approvals of the same artifact (no lock anywhere on the approval path either,
and the DB transaction opens *after* the artifact write) both read the same override history, each
appends, and the second `os.replace` wins — the first override is silently gone. This is the same
last-write-wins class A-38 was filed to close, narrowed from "always" to "a race window," not
eliminated. Separately: `meta.pop("gate_override_reason", None)` unconditionally deletes the legacy
scalar field, but re-migration into the new list is gated on `isinstance(legacy, str) and
legacy.strip()` — a whitespace-only or non-string legacy value is silently dropped with no log,
contradicting the "migrate, never drop" intent the brief itself states.

### P2R-12 (Minor) — the `actor` field on gate overrides carries no real information yet

No production caller (`approval_service.py`) supplies `actor` — every override the app records today
is attributed to the literal constant `"operator"`. The A-38 "no actor anywhere" gap is closed
structurally but not informationally until a caller is wired up. The test asserting on it
(`assert entry["actor"]`) only proves the constant is truthy, not that a real value reaches disk.

### P2R-13 (Important) — `classify_brief_change` (A-81, T16) has new failure shapes distinct from the ones it fixed

Three related issues, all in `grounding_service.py`:
1. The "exactly one added" branch wins unconditionally over a same-day modification. If a grounding
   turn writes its brief *and* incidentally creates any other new `.md` file, the wrong file is
   silently picked as `brief`, and the `reason` string reads as ordinary success — worse than the
   old bug in one respect, since it no longer even returns `None`.
2. Deletions are never computed. A turn that removes every brief reports `"no brief was written"` —
   literally true, actively misleading.
3. `snapshot_rgs_briefs`'s switch to `rglob` (needed to see subdirectory briefs) has no dot-directory
   filter, verified to recurse into hidden/archive subdirectories. Concrete: merely touching an
   archived brief (`rgs-briefs/.superseded/old.md`) with no new brief written reads as
   `"one brief modified in place"`, and `read_pointer`'s containment check (A-82, T17) accepts the
   path (`.superseded` is a normal path component, not `..`) — so a stage can be pinned to a
   superseded brief. And archiving a brief *during* a turn (old path removed, new path added under a
   different top-level directory) now reads as two adds instead of one delete + one add, recreating
   the exact A-81 ambiguity for the archive workflow specifically.

### P2R-14 (Important) — a call site inside this package's own test suite still uses the deleted `identify_new_brief`, contradicting §7's own verification claim

§7 below states the `identify_new_brief` grep "returns nothing outside P3's un-migrated call site" —
**verified false**: `tests/integration/test_stubbed_cli_e2e.py:127` also calls it and fails with
`AttributeError` when run. (It was already red from T15's `write_pointer` signature change, so T16
didn't newly break the app suite — but the specific verification claim in §7 is inaccurate and should
be corrected: there are two known call sites, not one, and one is inside this package's own test tree
via the integration test.)

### P2R-15 (Important) — the grounding pointer's containment check (A-82, T17) doesn't survive symlink/junction resolution, and `UnicodeDecodeError` escapes it

Two related gaps in `grounding_service.py`/`artifacts.py`:
1. **Verified with a live exploit on this host:** `read_pointer` validates the pointer *string* only.
   `resolve_latest_artifact` (`artifacts.py`) then does `repo_root / pointer` and `.exists()` with no
   `resolve()`/`is_relative_to()` re-check. A directory junction placed inside `rgs-briefs/`
   (`mklink /J`, no admin rights needed) pointing outside the repo, referenced by a pointer value like
   `rgs-briefs/esc/secret.md`, is accepted by containment and the target file's contents are returned
   and rendered by `routes/stages.py`. `browse_service.py` already does the resolve-based version of
   this check (`.resolve()` + `is_relative_to()`) for its own file-browsing path; the artifact-pointer
   path does not. Given the brief's own threat model is "a hand-repaired pointer is a realistic
   operator action," this is squarely inside scope, not a theoretical extension of it.
2. `read_pointer`'s except clause catches only `yaml.YAMLError`; `UnicodeDecodeError` from
   `pointer_path.read_text(encoding="utf-8")` escapes uncaught — a torn/truncated `pointer.yaml`
   (exactly the A-63 crash scenario motivating this whole package) can still produce a bare,
   unhandled exception instead of the intended `InvalidPointerError`.

### P2R-16 (Minor) — `verify_pointer`/`write_pointer` (A-80, T15) each do a redundant double-read with a benign TOCTOU

`verify_pointer` reads and parses `pointer.yaml` twice (once via `read_pointer`, once inline for the
hash) — a pointer rewritten between the two reads produces a spurious mismatch against the wrong
target. `write_pointer` reads the target brief twice (once to hash, once to `.stat()` for size) — a
brief rewritten between those two reads records an internally-inconsistent `sha256`/`size` pair, and
nothing downstream ever checks `size` against anything, so the inconsistency is currently undetectable
either way.

### P2R-17 (Important) — `parse_frontmatter`'s new raise (A-68/A-69, T8/T9) breaks graceful degradation in three files outside this package's tracked cross-package-breakage list

**Verified as currently-failing tests, not speculation:** `discovery_digest.py:232` and
`browse_service.py:270` both catch only `yaml.YAMLError` around `parse_frontmatter`; `MalformedArtifactError`
now escapes uncaught. `routes/inspector.py:41` calls `parse_frontmatter` with **no exception handling
at all**, contradicting that file's own header comment ("every expected failure mode … surfaced as an
explicit UI error state … per the design spec's 'no generic 500s'"). Concrete regression, and a
severity *upgrade* from what existed before P2: pre-T8, one malformed discovery item was silently
skipped (`meta == {}` → `fetched_at` absent → filtered); post-T8, `discovery_digest.collect_new_items`
raises and **aborts the entire daily digest email run** over one bad file — replacing "skip one item"
with "lose the whole morning email," which is precisely the class of regression this whole audit
programme exists to eliminate. These three files (plus `test_discovery_digest.py`,
`test_browse_service.py`, `test_routes_browse.py`'s malformed-yaml tests) are **not** named anywhere
in this package's tracked cross-package-breakage list (the tracked list only covers the
`write_pointer`/`record_gate_override`/`identify_new_brief` signature changes) — they are a
*separate*, currently-untracked breaking change from the `parse_frontmatter` behavior change itself,
and should be added to whichever package's queue picks up P2's cross-package fallout.

### P2R-18 (Minor) — a UTF-8 BOM defeats the A-68 truncation check it was designed to close

`parse_frontmatter`'s opening check (`lines[0].strip() != _DELIM`) does not strip a UTF-8 BOM
(`﻿`, category Cf, not whitespace), and every artifact reader in this package uses
`encoding="utf-8"`, not `utf-8-sig`. **Verified:** `parse_frontmatter('﻿---\nx: 1\n')` returns
`({}, text)` with no raise — a BOM'd, truncated artifact (realistic on this Windows-only app: Notepad,
or PowerShell 5.1's `Out-File -Encoding utf8`, both emit a BOM) still masquerades as a legitimate
plain-markdown file, reopening the exact hole A-68 was filed to close for any hand-rescued file
written with a BOM-emitting tool.

### P2R-19 (Minor) — `browse_service.py`'s independent artifact-version regex (already-filed open finding) is worse than previously described

Extending the open finding already filed after T7's review: the divergent regex
(`browse_service.py:198`) is not just looser (accepts zero-padding) but also `re.IGNORECASE`,
widening the gap further, and it has a **visible UI consequence**, not just a classification
mismatch: with both `artifact.v7.md` and `artifact.v07.md` present, `browse_service.py`'s sort key
treats both as version 7 and tie-breaks alphabetically, so the OS-copy file can render *above* the
real artifact in the browse UI as an equally legitimate version.

### P2R-20 (Minor, batch) — tautological or non-discriminating test assertions found across multiple tasks

None of these affect the underlying guarantee, which is separately covered by other tests in the same
file — but each assertion, read on its own, proves less than its name claims:
- `test_artifacts.py` (T3): `assert meta["status"] == "final"` on the crash-injection test for
  `stamp_final` passes regardless of whether the crash actually destroyed the artifact, because the
  test fixture already sets `status: "final"` before the crash. The genuinely discriminating
  assertion is the preceding byte-equality check; this one adds nothing. (`assert "finalized_at" not
  in meta` would actually prove the failed stamp didn't land.)
- `test_artifacts.py` (T2): `test_write_artifact_uses_the_atomic_primitive` only proves
  `_atomic_write_text` was *called*, not that it changed anything — a revert to a plain truncating
  write would still pass it.
- `test_artifacts.py` (T5): `assert not list(tmp_path.glob("artifact.v2.md"))` can never fail — the
  reservation marker's actual name (`.artifact.v2.reserved`) can't match that glob by construction,
  so the assertion is vacuous; the preceding `latest_artifact_path` assertion is the real one.
- `test_migrations.py` (T11): `test_backfill_allocates_its_version_rather_than_hardcoding_one`
  passes unchanged against the *pre-fix* hardcoded-`1` implementation, since an empty stage dir
  allocates `1` either way — it needs a pre-seeded existing version to actually discriminate.
- `test_migrations.py` (T12): the sha-stability assertion is real but not for the reason the test's
  docstring claims — a non-adopting retry in the *current*, versioned implementation would still
  leave `artifact.v1.md`'s sha unchanged (it publishes a new `v2` file instead); only the accompanying
  glob-count assertion actually discriminates the property this task is about.

### Cross-cutting notes

- Several findings above (P2R-01, P2R-04, P2R-08, P2R-11) share the audit's own named root cause:
  a partial fix that closes the common case while leaving a narrower, less-likely-but-real window of
  the same failure class open. None of them are regressions *relative to pre-P2 behavior* — they are
  all either explicitly-deferred-and-now-detailed (P2R-01) or genuinely new gaps introduced by making
  a previously-inert code path live (P2R-04, P2R-08 through P2R-16 mostly fall in this bucket: the
  mechanisms these findings critique did not exist, or were dead code, before this package).
- P2R-17 and P2R-18 are the two findings closest to violating this package's own stated goal (closing
  A-68) rather than merely leaving a narrow residual gap, and are worth prioritizing first in whatever
  package picks this list up.

## 7. Verification

This package is done when all of the following hold:

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app" && python -m pytest tests/test_artifacts.py tests/test_migrations.py tests/test_grounding_service.py -q
```

1. Every test in §4 exists under the name given and was observed **failing before** its fix.
2. The two S0 crash-injection classes pass 5 consecutive runs with no flake:
   `TestDurabilityContract::test_prior_bytes_survive_a_crash_at_any_point` and
   `test_two_concurrent_callers_get_two_distinct_versions`.
3. `grep -rn "write_text" pipeline-app/pipeline_app/artifacts.py pipeline-app/pipeline_app/grounding_service.py pipeline-app/pipeline_app/migrations.py` returns **only** the `_atomic_write_text` implementation.
4. `grep -rn "identify_new_brief" pipeline-app/` returns nothing outside P3's un-migrated call site (reported, not fixed here).
5. Cross-package failures are enumerated and handed to the orchestrator with the §6 contract attached.
