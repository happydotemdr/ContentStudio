# P8 — Engine & Cron

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or
> `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. The orchestration plan's
> **Global Constraints**, **test standard** and **Frozen interfaces**
> ([`../2026-08-08-audit-remediation.md`](../2026-08-08-audit-remediation.md)) are binding and are
> not restated here.

**The defect this package exists to kill:** a scheduled discovery run exits `0` in **eight
distinct real-failure states**. `run_discovery_cron.py:110` is an unconditional `return 0`;
non-zero is reserved for argparse typos and unanticipated exceptions. Windows Task Scheduler's
*Last Run Result* — the only machine-readable health signal the discovery subsystem has — is a
compile-time constant. The test suite contains **12 assertions of `exit_code == 0` and zero
assertions of any other value**, one of them named for the defect.

Everything else in this package is downstream of two amplifiers: that constant exit code
(B-40/D-01) and the registered `schtasks` action's total lack of output redirection (D-02),
which destroys all 35 stderr diagnostics on the scheduled path.

---

## 1. Scope

### Files owned (no other package may touch these)

```
pipeline-app/pipeline_app/discovery_engine.py
pipeline-app/pipeline_app/discovery_scheduling.py
pipeline-app/pipeline_app/discovery_records.py
pipeline-app/pipeline_app/discovery_paths.py
pipeline-app/pipeline_app/routes/discovery.py
pipeline-app/run_discovery_cron.py
pipeline-app/scripts/setup_discovery_task.py
pipeline-app/tests/test_discovery_engine.py
pipeline-app/tests/test_discovery_scheduling.py
pipeline-app/tests/test_discovery_records.py
pipeline-app/tests/test_discovery_paths.py
pipeline-app/tests/test_routes_discovery.py
pipeline-app/tests/test_run_discovery_cron.py
pipeline-app/tests/test_setup_discovery_task.py
```

### Findings (31)

B-40, B-41, B-42, B-43, B-44, B-45, B-46, B-47, B-48, B-49, B-50, B-51, B-52, B-53, B-54,
B-55, B-56, B-57, B-58, B-59, B-60, B-61, B-62, B-63, B-64, D-01, D-02, D-06, E-11, F-16, F-68.

### Boundary notes — fixes that must stay inside these files

Three audit-proposed fixes name files owned by other packages. Each is re-planned to land inside
P8's file list, with the residual handed off explicitly rather than silently dropped:

| Finding | Audit's proposed fix | Why it cannot land as written | P8's equivalent, in-scope fix | Residual handoff |
|---|---|---|---|---|
| **B-50** | Guard `db.finish_run` with a status precondition | `db.py` is **P1**'s | `_finish_run_guarded()` wrapper in `discovery_engine.py` — read-then-write | The atomic `WHERE status='running'` belongs to P1; the wrapper leaves a narrow race, documented in Task 15 |
| **B-50** | Record OS PID + process start time on the run row | `schema.sql` is **P1**'s | A run-owner sidecar file under `output/discovery-runs/.owners/`, written by the engine, path from `discovery_paths.py` | none — the sidecar is complete on its own |
| **B-63** | Move the collision check into the DB-write layer | `db.py` (**P1**) and `migrate_handles_from_manifest.py` (**P10**) | `discovery_paths.assert_no_slug_collision()` as the single callable both paths must use, plus a **durable** runtime detector (events row, not stderr) so a migration-introduced collision is findable | P1/P10 must call the helper; P8 proves the detector fires for rows inserted by the non-route path |
| **B-43** | Style the status pills; paginate | `templates/`, `static/style.css` are **P15**'s | Route-side: cap + filter `list_runs`, compute a `health` summary into the template context | P15 renders the health banner and the `.status-*` rules |
| **E-11** | Auto-refresh the runs page | template is **P15**'s | Route-side: durable spawn record (PID + captured child output + events row) surfaced in the context as `pending_spawns` | P15 renders `pending_spawns` and the poll |

`platform` validation (B-58) is planned to **complement** P1's `CHECK (platform IN (...))`, not
duplicate it: P1's constraint is the durable backstop; P8 validates against the *runtime adapter
registry* (`discovery_engine.SUPPORTED_PLATFORMS`), which is the thing `adapters[platform]`
actually indexes, and returns a 400 with a message naming the valid set.

### Inbound seam obligations — other packages' findings whose closing half lands here

These are **not** P8 findings and do not change the 31-ID count. They are work P8 owes another
package, without which that package's finding stays open no matter what it ships. Each has a
task and a named test.

| Owner | Finding | What P8 must do | Task |
|---|---|---|---|
| **P6** | **B-06** (S1) — a transient Bluesky blip permanently disables a valid handle | `BlueskyFetchError` (and every other typed adapter error) must reach `discovery_engine.py:272`'s error branch and **must not** be converted by `:255` into `status='invalid'` + `included=False`. P6's plan records this at its `T15` note. | **36** |
| **P7** | **B-01** — Bright Data diagnostics have no durable surface | Call `brightdata_job.drain_diagnostics()` inside the run loop and write each record with `obs.record_event`. Until P8 does, P7's only surface is `obs.log`'s dated file (P7 §7 residual 3). | **37** |
| **P7** | **B-21** — missing credentials fail N times instead of once | Call each adapter's `preflight()` **once per run**, before the handle loop. P7 tests `preflight()` standalone; it has no effect until called here. | **38** |
| **P1** | **B-73** (S2) — `handles.platform` is unconstrained free text | The **route-level** rejection with a usable message, ahead of P1's storage `CHECK`. Already P8's Task 27; amended there with the complementarity test. | **27** |
| **P1** | **B-82** (S2) — a handle that dies after registration still looks healthy | Call `db.record_handle_failure()` from the per-handle error branch and `db.clear_handle_failures()` on success. P1 ships the column, the `failing` status and the policy function; nothing increments the counter until P8 calls it. | **39** |
| **P0** | **F-64** (S2) — two packages both named `scripts` | Move `setup_discovery_task.py` into `pipeline-app/tools/` (orchestrator's target; P8's `pipeline_app/scripts/` proposal withdrawn because `tools/` preserves module depth). **Accepted**, one atomic commit with P10 — see Task 40. | **40** |

---

## 2. Finding → task map

Total coverage: 31 owned findings, 40 tasks, no finding unmapped. Tasks 36-40 close the five
inbound seam obligations listed in §1 (other packages' finding IDs — not counted in the 31).

| Finding | Sev | Mode | Task(s) |
|---|---|---|---|
| **B-40** Exit code is a constant | S2 | silent | 1, 2, 3, 4, 8 |
| **B-41** `notify()`'s bool discarded | S2 | silent | 5 |
| **B-42** No log file for scheduled runs | S2 | silent | 9, 10, 12 |
| **B-43** `completed_with_errors` looks like `completed` | S2 | silent | 32 |
| **B-44** schtasks sets no run-level / logon / workdir / power policy | S2 | silent | 9, 10 |
| **B-45** Dry-run prints an unrunnable command | S3 | loud | 11 |
| **B-46** `/F` clobbers; no query/verify/uninstall | S4 | silent | 10 |
| **B-47** Unvalidated tz / `time_of_day` wedge the scheduler | **S1** | silent | 7, 29 |
| **B-48** Timezone change can fire a second run the same day | S3 | silent | 18, 19 |
| **B-49** Long run manufactures a `locked` row + md per wake | S3 | latent | 17 |
| **B-50** Sleep / wedged heartbeat → two concurrent runs | **S1** | silent | 13, 14, 15 |
| **B-51** `abandoned` records contradict their own DB rows | S3 | silent | 23 |
| **B-52** Stale `running` row never reclaimed once the day succeeded | S3 | latent | 16 |
| **B-53** No wall-clock cap on a run | S2 | silent | 20 |
| **B-54** Partial downloads recorded as 0 items, forever | S2 | silent | 21 |
| **B-55** `error_message` is a bare `str(exc)` | S3 | silent | 22 |
| **B-56** `skipped` counted but never surfaced | S3 | silent | 24 |
| **B-57** Transient validate error permanently excludes a handle | S2 | silent | 25 |
| **B-58** Unvalidated `platform` kills the validate subprocess | S2 | silent | 27 |
| **B-59** Run Now has no concurrency guard; lock-loss can crash | S3 | latent | 30 |
| **B-60** Backfill dates unvalidated; inverted ranges bill for nothing | S2 | silent | 28 |
| **B-61** A dead spawned subprocess is invisible | S2 | silent | 31 |
| **B-62** Windows reserved device names | S4 | latent | 33 |
| **B-63** Collision guard only in the add-handle route | S3 | silent | 34 |
| **B-64** Hygiene: imports, Protocol, tunables, naive datetime | S4 | latent | 35 |
| **D-01** Notification failure unobservable | S2 | silent | 5 |
| **D-02** No centralized error surface; 35 stderr signals discarded | S2 | silent | 9, 12 |
| **D-06** A run dying before its first DB write leaves no trace | S2 | silent | 6, 19 |
| **E-11** Run Now redirects to a page showing no evidence | S3 | silent | 31 |
| **F-16** No test asserts a nonzero exit on any unattended path | **S1** | silent | 8 |
| **F-68** The suite can spawn a real, billed Bright Data run | **S1** | latent | 26 |

**Inbound obligations (other packages' IDs, tracked separately):**

| Finding | Owner | Task |
|---|---|---|
| B-06 | P6 | 36 |
| B-01 (events half) | P7 | 37 |
| B-21 (call site) | P7 | 38 |
| B-73 (route half) | P1 | 27 |
| B-82 (call sites) | P1 | 39 |
| F-64 (app-side rename) | P0 | 40 |

---

## 3. The exit-code contract

This is the deliverable an operator and Task Scheduler can rely on. It replaces the 14-row
truth table in which eight real-failure states all read `0`.

### Codes

Defined once, in `run_discovery_cron.py`, as the single source of truth:

```python
class Exit(enum.IntEnum):
    """Exit codes for run_discovery_cron. Windows Task Scheduler shows these in
    the task's *Last Run Result* column, in hex. 1 and 2 are NOT reused: 1 is
    CPython's unhandled-exception code and 2 is argparse's usage code, so the
    contract starts at 10 to keep "the code crashed" and "the operator typed
    the arguments wrong" distinguishable from every state below."""
    OK                  = 0    # 0x0
    LOCKED              = 10   # 0xA
    NO_WORK             = 11   # 0xB
    NOTIFY_FAILED       = 12   # 0xC
    HANDLES_ERRORED     = 13   # 0xD
    ALL_HANDLES_ERRORED = 14   # 0xE
    RUN_FAILED          = 15   # 0xF
    SCHEDULER_WEDGED    = 16   # 0x10
    STARTUP_FAILED      = 17   # 0x11
```

**Precedence rule (one line, so it is testable):** when several conditions hold, the exit code is
the **numeric maximum** of every condition's code. The enum's values are ordered by severity
precisely so that `max()` is the whole rule.

### The table

| # | Terminal state | Decided at | `discovery_runs.status` | Exit | Hex |
|---|---|---|---|---|---|
| 1 | Not due yet today | cron due-check | *(no row)* | `OK` | 0x0 |
| 2 | Clean run — every handle `ok` / `no_new_content` | engine | `completed` | `OK` | 0x0 |
| 3 | Another run is already active (cron short-circuit, no row written) | cron, pre-engine | *(no row)* | `LOCKED` | 0xA |
| 4 | Lock lost inside the engine | engine | `locked` | `LOCKED` | 0xA |
| 5 | Every included handle `skipped` — zero adapter calls made | engine | `completed` | `NO_WORK` | 0xB |
| 6 | Email not sent — no `RESEND_API_KEY` | cron, from `notify()`'s bool | *(unchanged)* | `NOTIFY_FAILED` | 0xC |
| 7 | Email send failed — network / non-2xx | cron, from `notify()`'s bool | *(unchanged)* | `NOTIFY_FAILED` | 0xC |
| 8 | `notify()` itself raised | cron `except` | *(unchanged)* | `NOTIFY_FAILED` | 0xC |
| 9 | One or more handles errored (not all) | engine | `completed_with_errors` | `HANDLES_ERRORED` | 0xD |
| 10 | **Every** attempted handle errored | engine | `completed_with_errors` | `ALL_HANDLES_ERRORED` | 0xE |
| 11 | `validate_handle`: enumerate returned nothing | engine | `completed_with_errors` | `ALL_HANDLES_ERRORED` | 0xE |
| 12 | Crash outside the per-handle loop | engine outer handler | `failed` | `RUN_FAILED` | 0xF |
| 13 | `validate_handle`: adapter raised | engine validate handler | `failed` | `RUN_FAILED` | 0xF |
| 14 | Run exceeded its wall-clock deadline | engine deadline check | `failed` | `RUN_FAILED` | 0xF |
| 15 | Stored `timezone` / `time_of_day` unparseable — due-check impossible | cron, `ScheduleConfigError` | *(no row)* | `SCHEDULER_WEDGED` | 0x10 |
| 16 | Startup failed before any DB write (`init_db`, missing schema, corrupt DB) | cron, pre-engine | *(no row)* | `STARTUP_FAILED` | 0x11 |
| 17 | Unhandled exception | *(no handler)* | may remain `running` | `1` | 0x1 |
| 18 | Bad CLI arguments | argparse `ap.error` | *(no row)* | `2` | 0x2 |
| — | *combination:* clean run + unsent email | `max(OK, NOTIFY_FAILED)` | `completed` | `NOTIFY_FAILED` | 0xC |
| — | *combination:* errored handles + unsent email | `max(HANDLES_ERRORED, NOTIFY_FAILED)` | `completed_with_errors` | `HANDLES_ERRORED` | 0xD |

Every row is asserted by the data-driven test in **Task 8**.

---

## 4. Tasks

Each task is one TDD cycle: write the failing test → run it → see it fail for the right reason →
implement → see it pass → commit. Every task names the exact commands.

```bash
# the only two commands used below
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app" && python -m pytest tests/<file> -q
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app" && python -m pytest -q
```

---

### Group A — the exit-code spine (B-40, B-41, D-01, D-06, B-47a, F-16)

#### - [ ] Task 1 — Publish the exit-code contract as code

**Test** (`tests/test_run_discovery_cron.py`, new):

```python
def test_every_exit_code_is_unique_and_documented():
    """The contract table in docs/superpowers/plans/remediation/P8-engine-cron.md
    is only as good as its enforcement. Two states sharing a code, or a code
    with no operator-facing reason string, silently re-creates B-40."""
    values = [member.value for member in cron.Exit]
    assert len(values) == len(set(values)), "two terminal states share one exit code"
    assert cron.Exit.OK == 0
    assert {1, 2} & set(values) == set(), "1 and 2 belong to CPython and argparse"
    for member in cron.Exit:
        assert cron.EXIT_REASON[member], f"{member.name} has no reason string"
```

**Run:** `python -m pytest tests/test_run_discovery_cron.py -q` → `AttributeError: module 'run_discovery_cron' has no attribute 'Exit'`.

**Implement** in `run_discovery_cron.py` (add `import enum`):

```python
class Exit(enum.IntEnum):
    OK                  = 0
    LOCKED              = 10
    NO_WORK             = 11
    NOTIFY_FAILED       = 12
    HANDLES_ERRORED     = 13
    ALL_HANDLES_ERRORED = 14
    RUN_FAILED          = 15
    SCHEDULER_WEDGED    = 16
    STARTUP_FAILED      = 17


EXIT_REASON: dict[Exit, str] = {
    Exit.OK: "clean run, or nothing was due",
    Exit.LOCKED: "another discovery run holds the single-flight lock",
    Exit.NO_WORK: "every included handle was skipped -- no adapter call was made",
    Exit.NOTIFY_FAILED: "the run finished but the notification email was not sent",
    Exit.HANDLES_ERRORED: "one or more handles errored",
    Exit.ALL_HANDLES_ERRORED: "every handle this run attempted errored",
    Exit.RUN_FAILED: "the run crashed or exceeded its deadline",
    Exit.SCHEDULER_WEDGED: "the stored schedule settings cannot be evaluated",
    Exit.STARTUP_FAILED: "startup failed before any run could be recorded",
}
```

**Commit:** `feat(cron): publish the discovery exit-code contract as an enum`

---

#### - [ ] Task 2 — `run_discovery` reports per-status counts

`classify_exit` cannot tell "one handle errored" from "every handle errored" without counts.

**Test** (`tests/test_discovery_engine.py`):

```python
def test_run_discovery_result_carries_per_status_counts(engine_conn, tmp_path):
    db.create_handle(engine_conn, "youtube", "@good", "G", "guru", None, now_iso())
    db.create_handle(engine_conn, "youtube", "@bad", "B", "guru", None, now_iso())
    adapter = SingleFakeAdapter({"@good": [{"id": "v1", "title": "x", "published": None}]},
                                fail_handles={"@bad"})
    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter},
                           trigger="manual", mode="incremental")
    assert result["counts"]["total"] == 2
    assert result["counts"]["attempted"] == 2
    assert result["counts"]["failed"] == 1
    assert result["counts"]["skipped"] == 0
```

**Run** → `KeyError: 'counts'`.

**Implement** in `discovery_engine.py` — one helper plus its use at all four `return` sites:

```python
def _summarize(handle_results: list[dict]) -> dict:
    """Counts the exit-code contract is computed from. `attempted` excludes
    'skipped' handles: a backfill that skipped every handle made zero adapter
    calls, which is a different outcome from a run in which everything failed."""
    by_status: dict[str, int] = {}
    for r in handle_results:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    skipped = by_status.get("skipped", 0)
    failed = by_status.get("error", 0) + by_status.get("handle_not_found", 0)
    return {
        "total": len(handle_results),
        "attempted": len(handle_results) - skipped,
        "skipped": skipped,
        "failed": failed,
        "by_status": by_status,
    }
```

Return `{"run_row_id": ..., "status": ..., "counts": _summarize(handle_results)}` from the
incremental/backfill path, the locked path (`_summarize([])`), and both validate paths
(`_summarize([handle_result])`).

**Commit:** `feat(engine): return per-status handle counts from run_discovery`

---

#### - [ ] Task 3 — `classify_exit`, the pure mapping

**Test** (`tests/test_run_discovery_cron.py`):

```python
def _result(status, **counts):
    base = {"total": 0, "attempted": 0, "skipped": 0, "failed": 0, "by_status": {}}
    return {"run_row_id": 1, "status": status, "counts": {**base, **counts}}


def test_classify_exit_distinguishes_a_partial_failure_from_a_total_one():
    partial = cron.classify_exit(_result("completed_with_errors", total=3, attempted=3, failed=1))
    total = cron.classify_exit(_result("completed_with_errors", total=3, attempted=3, failed=3))
    assert partial != total
    assert partial == cron.Exit.HANDLES_ERRORED
    assert total == cron.Exit.ALL_HANDLES_ERRORED
```

**Run** → `AttributeError: ... 'classify_exit'`.

**Implement** in `run_discovery_cron.py`:

```python
def classify_exit(result: dict | None, *, notify_ok: bool = True) -> Exit:
    """Map one terminal run outcome onto the documented exit-code contract.

    Pure -- no DB, no clock, no I/O -- so the contract table is testable as
    data. When several conditions hold the code is the numeric maximum, and
    Exit's values are ordered by severity precisely so that max() is the rule.
    """
    codes = [Exit.OK]
    if result is not None:
        status = result["status"]
        counts = result.get("counts") or {}
        attempted, failed = counts.get("attempted", 0), counts.get("failed", 0)
        if status == "locked":
            codes.append(Exit.LOCKED)
        elif status == "failed":
            codes.append(Exit.RUN_FAILED)
        elif failed and attempted and failed >= attempted:
            codes.append(Exit.ALL_HANDLES_ERRORED)
        elif failed:
            codes.append(Exit.HANDLES_ERRORED)
        elif attempted == 0 and counts.get("skipped", 0):
            codes.append(Exit.NO_WORK)
    if not notify_ok:
        codes.append(Exit.NOTIFY_FAILED)
    return Exit(max(codes))
```

**Commit:** `feat(cron): add classify_exit, the pure terminal-state -> exit-code map`

---

#### - [ ] Task 4 — `main()` returns the contracted code (B-40)

**Test** (`tests/test_run_discovery_cron.py`), and in the same commit **invert `:101`** and
**retarget the eight surviving `== 0` assertions to `cron.Exit.OK`** (see §6):

```python
def test_a_run_with_errored_handles_exits_nonzero(monkeypatch, repo_root):
    """B-40: Task Scheduler's Last Run Result was 0x0 for a run in which every
    tracked handle failed. That is the whole defect, in one assertion."""
    monkeypatch.setattr(cron, "_is_due_now", lambda conn: True)
    monkeypatch.setattr(cron, "notify", lambda *a, **k: True)
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result(
        "completed_with_errors", total=3, attempted=3, failed=3))
    assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) == cron.Exit.ALL_HANDLES_ERRORED


def test_a_broken_run_and_a_clean_run_do_not_share_an_exit_code(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda conn: True)
    monkeypatch.setattr(cron, "notify", lambda *a, **k: True)
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result("completed", total=3, attempted=3))
    clean = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result("failed", total=0))
    broken = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    assert clean != broken
```

**Run** → both fail: `assert 0 == <Exit.ALL_HANDLES_ERRORED: 14>`.

**Implement** in `run_discovery_cron.py` — replace the final `return 0`:

```python
        result = run_discovery(...)
        print(f"run {result['run_row_id']}: {result['status']}")
        obs.log("discovery.run_finished", level="info", status=result["status"],
                run_row_id=result["run_row_id"], counts=result["counts"])
        ...
    finally:
        conn.close()
    code = classify_exit(result, notify_ok=notify_ok)
    if code is not Exit.OK:
        print(f"exit {int(code)} ({code.name}): {EXIT_REASON[code]}", file=sys.stderr)
    return code
```

(`notify_ok` defaults to `True` and is set in Task 5; `result` is `None` on the not-due path.)

**Commit:** `fix(cron): map the run's terminal status onto the exit-code contract (B-40)`

---

#### - [ ] Task 5 — An unsent email is a non-zero exit and an event row (B-41, D-01)

Delete `test_notify_exception_does_not_propagate_or_change_exit_code`
(`tests/test_run_discovery_cron.py:155-168`) **first** — it is named for the defect.

**Test** (three, per the Three-Test Rule):

```python
def test_a_failed_send_exits_notify_failed(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda conn: True)
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result("completed", total=1, attempted=1))
    monkeypatch.setattr(cron, "notify", lambda *a, **k: False)   # send_email's documented False
    assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) == cron.Exit.NOTIFY_FAILED


def test_a_sent_and_an_unsent_email_do_not_share_an_exit_code(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda conn: True)
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result("completed", total=1, attempted=1))
    monkeypatch.setattr(cron, "notify", lambda *a, **k: True)
    sent = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    monkeypatch.setattr(cron, "notify", lambda *a, **k: False)
    unsent = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    assert sent != unsent


def test_a_notify_exception_does_not_propagate_but_does_change_the_exit_code(monkeypatch, repo_root):
    """Replaces test_notify_exception_does_not_propagate_or_change_exit_code.
    The 'does not propagate' half was right; the 'does not change the exit
    code' half was the defect (B-41/D-01)."""
    monkeypatch.setattr(cron, "_is_due_now", lambda conn: True)
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result("completed", total=1, attempted=1))
    def raising_notify(*a, **k):
        raise RuntimeError("resend is down")
    monkeypatch.setattr(cron, "notify", raising_notify)
    assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) == cron.Exit.NOTIFY_FAILED


def test_an_unsent_email_leaves_an_error_event(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda conn: True)
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result("completed", total=1, attempted=1))
    monkeypatch.setattr(cron, "notify", lambda *a, **k: False)
    cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    conn = db.get_connection(repo_root / "pipeline-app" / "pipeline.db")
    rows = conn.execute(
        "SELECT kind, severity FROM events WHERE kind = 'discovery.notify_failed'").fetchall()
    assert [r["severity"] for r in rows] == ["error"]
```

**Run** → `assert 0 == <Exit.NOTIFY_FAILED: 12>`, and an empty `events` result.

**Implement** in `run_discovery_cron.py` (add `from pipeline_app import obs`):

```python
    notify_ok = True
    if args.mode == "scheduled" and result["status"] != "locked":
        try:
            notify_ok = bool(notify(conn, repo_root, result["run_row_id"]))
            if not notify_ok:
                message = "notification email was not sent (no API key, or the send failed)"
        except Exception as exc:  # noqa: BLE001 - notification must never abort the run,
            # but it must not be invisible either: the email is the only push
            # channel this system has, so a failure to send is exactly the
            # failure that cannot announce itself (D-01).
            notify_ok = False
            message = f"notification raised: {type(exc).__name__}: {exc}"
        if not notify_ok:
            print(f"discovery notification failed: {message}", file=sys.stderr)
            obs.record_event(conn, kind="discovery.notify_failed", severity="error",
                             source="run_discovery_cron", message=message,
                             run_id=result["run_row_id"])
```

**Commit:** `fix(cron): a notification that never sent is no longer exit 0 (B-41, D-01)`

---

#### - [ ] Task 6 — A run that dies before its first DB write leaves a trace (D-06)

**Test:**

```python
def test_a_startup_failure_exits_startup_failed_and_is_not_confused_with_not_due(monkeypatch, repo_root):
    monkeypatch.setattr(cron.db, "init_db", lambda *a, **k: (_ for _ in ()).throw(
        sqlite3.OperationalError("database is locked")))
    wedged = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    assert wedged == cron.Exit.STARTUP_FAILED

    monkeypatch.undo()
    monkeypatch.setattr(cron, "_is_due_now", lambda conn: False)
    assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) != wedged


def test_a_wake_is_logged_before_the_database_is_touched(monkeypatch, repo_root, tmp_path):
    """D-06: everything the recovery machinery does is downstream of
    insert_running_run. The attempt marker has to be written before init_db
    can fail, which means the log file, not the events table."""
    monkeypatch.setattr(cron.db, "init_db", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    logs = sorted((Path(cron.__file__).resolve().parent / "logs").glob("app-*.log"))
    text = logs[-1].read_text(encoding="utf-8")
    assert "discovery.wake" in text
    assert "discovery.startup_failed" in text
```

**Implement** at the top of `main()`, before `db.init_db`:

```python
    obs.log("discovery.wake", level="info", mode=args.mode, repo_root=str(repo_root))
    try:
        db.init_db(db_path, schema_path)
        conn = db.get_connection(db_path)
    except Exception as exc:  # noqa: BLE001 - a corrupt/locked pipeline.db, a
        # missing schema.sql or a broken venv kills the run before any row
        # exists, which is otherwise indistinguishable from "the scheduler
        # never fired" (D-06).
        obs.log("discovery.startup_failed", level="error",
                error=f"{type(exc).__name__}: {exc}", db_path=str(db_path))
        print(f"discovery startup failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return Exit.STARTUP_FAILED
    obs.record_event(conn, kind="discovery.wake", severity="info",
                     source="run_discovery_cron", message=f"wake: mode={args.mode}")
```

**Commit:** `fix(cron): record the wake before init_db can fail (D-06)`

---

#### - [ ] Task 7 — A wedged schedule setting degrades loudly (B-47, engine half)

**Test** (`tests/test_discovery_scheduling.py` + `tests/test_run_discovery_cron.py`):

```python
# test_discovery_scheduling.py
def test_is_due_rejects_an_unknown_timezone_as_a_schedule_config_error():
    now = _dt.datetime(2026, 7, 30, 11, 0, tzinfo=_dt.timezone.utc)
    with pytest.raises(ScheduleConfigError):
        is_due(now, "America/Chicgo", "06:00", last_scheduled_run_date=None)


def test_is_due_rejects_a_non_hhmm_time_of_day():
    now = _dt.datetime(2026, 7, 30, 11, 0, tzinfo=_dt.timezone.utc)
    with pytest.raises(ScheduleConfigError):
        is_due(now, "America/Chicago", "6am", last_scheduled_run_date=None)


# test_run_discovery_cron.py
def test_a_stored_bad_timezone_exits_scheduler_wedged_not_a_traceback(monkeypatch, repo_root):
    """B-47 (S1): a mistyped timezone made every 15-minute wake for the rest of
    time die with a traceback into a console Task Scheduler destroys."""
    conn = db.get_connection(repo_root / "pipeline-app" / "pipeline.db")
    db.update_settings(conn, "daily", "06:00", "America/Chicgo")
    conn.commit()
    assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) == cron.Exit.SCHEDULER_WEDGED
    rows = conn.execute("SELECT severity FROM events WHERE kind = 'discovery.scheduler_wedged'").fetchall()
    assert [r["severity"] for r in rows] == ["critical"]
```

**Implement** in `discovery_scheduling.py`:

```python
class ScheduleConfigError(ValueError):
    """The stored schedule settings cannot be evaluated. Raised in place of
    ZoneInfoNotFoundError / ValueError so the caller can report a wedged
    scheduler as its own terminal state (B-47) instead of dying with a
    traceback into a console Task Scheduler discards (B-42)."""


_HHMM = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")


def parse_time_of_day(time_of_day: str) -> _dt.time:
    match = _HHMM.fullmatch(time_of_day or "")
    if match is None:
        raise ScheduleConfigError(f"time_of_day must be HH:MM (24-hour), got {time_of_day!r}")
    return _dt.time(int(match.group(1)), int(match.group(2)))


def resolve_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except Exception as exc:  # ZoneInfoNotFoundError, ValueError, TypeError
        raise ScheduleConfigError(f"unknown timezone {timezone_name!r}") from exc
```

and rewrite `is_due` to use them. In `run_discovery_cron.main()`:

```python
        if args.mode == "scheduled":
            try:
                due = _is_due_now(conn)
            except ScheduleConfigError as exc:
                obs.record_event(conn, kind="discovery.scheduler_wedged", severity="critical",
                                 source="run_discovery_cron", message=str(exc))
                print(f"discovery scheduler is wedged: {exc}", file=sys.stderr)
                return Exit.SCHEDULER_WEDGED
            if not due:
                return Exit.OK
```

**Commit:** `fix(scheduling): a bad stored timezone is a reported state, not a traceback (B-47)`

---

#### - [ ] Task 8 — **The data-driven exit-code contract test** (F-16, B-40 capstone)

One table. Every terminal state in §3, driven through the real `main()`. This is the test that
makes the always-zero defect impossible to reintroduce.

**Test** (`tests/test_run_discovery_cron.py`):

```python
def _stub(monkeypatch, *, due=True, result=None, notify=None, init_db_error=None, tz=None):
    if init_db_error is not None:
        monkeypatch.setattr(cron.db, "init_db",
                            lambda *a, **k: (_ for _ in ()).throw(init_db_error))
        return
    if tz is not None:
        monkeypatch.setattr(cron, "_is_due_now",
                            lambda conn: (_ for _ in ()).throw(ScheduleConfigError(tz)))
    else:
        monkeypatch.setattr(cron, "_is_due_now", lambda conn: due)
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: result)
    monkeypatch.setattr(cron, "notify", notify if notify is not None else (lambda *a, **k: True))


# (state label, stub kwargs, expected Exit)  -- one row per row of the contract table
EXIT_CONTRACT = [
    ("not due",                 dict(due=False),                                                          cron.Exit.OK),
    ("clean run",               dict(result=_result("completed", total=3, attempted=3)),                  cron.Exit.OK),
    ("lock lost in engine",     dict(result=_result("locked")),                                           cron.Exit.LOCKED),
    ("every handle skipped",    dict(result=_result("completed", total=4, attempted=0, skipped=4)),       cron.Exit.NO_WORK),
    ("no api key",              dict(result=_result("completed", total=1, attempted=1),
                                     notify=lambda *a, **k: False),                                       cron.Exit.NOTIFY_FAILED),
    ("send failed",             dict(result=_result("completed", total=1, attempted=1),
                                     notify=lambda *a, **k: False),                                       cron.Exit.NOTIFY_FAILED),
    ("notify raised",           dict(result=_result("completed", total=1, attempted=1),
                                     notify=_raise(RuntimeError("resend is down"))),                      cron.Exit.NOTIFY_FAILED),
    ("one handle errored",      dict(result=_result("completed_with_errors", total=3, attempted=3, failed=1)),
                                                                                                          cron.Exit.HANDLES_ERRORED),
    ("every handle errored",    dict(result=_result("completed_with_errors", total=3, attempted=3, failed=3)),
                                                                                                          cron.Exit.ALL_HANDLES_ERRORED),
    ("validate: not found",     dict(result=_result("completed_with_errors", total=1, attempted=1, failed=1)),
                                                                                                          cron.Exit.ALL_HANDLES_ERRORED),
    ("crash outside the loop",  dict(result=_result("failed", total=0)),                                  cron.Exit.RUN_FAILED),
    ("validate: adapter raised",dict(result=_result("failed", total=1, attempted=1, failed=1)),           cron.Exit.RUN_FAILED),
    ("run deadline exceeded",   dict(result=_result("failed", total=5, attempted=5, failed=2)),           cron.Exit.RUN_FAILED),
    ("scheduler wedged",        dict(tz="unknown timezone 'America/Chicgo'"),                             cron.Exit.SCHEDULER_WEDGED),
    ("startup failed",          dict(init_db_error=sqlite3.OperationalError("database is locked")),       cron.Exit.STARTUP_FAILED),
    ("clean + unsent email",    dict(result=_result("completed", total=1, attempted=1),
                                     notify=lambda *a, **k: False),                                       cron.Exit.NOTIFY_FAILED),
    ("errored + unsent email",  dict(result=_result("completed_with_errors", total=3, attempted=3, failed=1),
                                     notify=lambda *a, **k: False),                                       cron.Exit.HANDLES_ERRORED),
]


@pytest.mark.parametrize("label,kwargs,expected", EXIT_CONTRACT, ids=[r[0] for r in EXIT_CONTRACT])
def test_exit_code_contract(monkeypatch, repo_root, label, kwargs, expected):
    """The whole of B-40/F-16 in one table. Before the fix, 8 of these 17 rows
    returned 0 and were indistinguishable from a clean run."""
    _stub(monkeypatch, **kwargs)
    assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) == expected


def test_exit_contract_covers_every_declared_exit_code():
    """A new Exit member with no contract row is a state nobody can observe."""
    covered = {expected for _, _, expected in EXIT_CONTRACT}
    assert covered == set(cron.Exit)


def test_bad_cli_arguments_still_exit_two():
    with pytest.raises(SystemExit) as excinfo:
        cron.main(["--mode", "nonsense"])
    assert excinfo.value.code == 2
```

**Run:** the parametrised test must be observed **green** here (Tasks 1-7 built it); the two
guard tests fail first if any `Exit` member is uncovered. Re-run the whole app suite.

**Commit:** `test(cron): data-driven exit-code contract over every terminal state (F-16)`

---

### Group B — the scheduled path's transcript (D-02, B-42, B-44, B-45, B-46)

#### - [ ] Task 9 — The registered task captures its own output (D-02, B-42, B-44)

`schtasks /Create /TR ...` cannot express `DisallowStartIfOnBatteries`, `StartWhenAvailable` or
a working directory. Register from an XML definition instead — one artifact closes D-02's
redirection, B-42's log and all four of B-44's omissions.

**Test** (`tests/test_setup_discovery_task.py`):

```python
def test_task_xml_redirects_stdout_and_stderr_to_a_log_file():
    """D-02: the registered action captured no output, so all 35 stderr
    diagnostics on the scheduled path were written and immediately discarded."""
    xml = build_task_xml(Path("C:/venv/Scripts/python.exe"),
                         Path("C:/repo/pipeline-app/run_discovery_cron.py"),
                         log_path=Path("C:/repo/pipeline-app/logs/discovery-task.log"),
                         run_as="DOMAIN\\bking")
    assert ">>" in xml and "2>&1" in xml
    assert "discovery-task.log" in xml


def test_task_xml_runs_on_battery_and_catches_up_a_missed_start():
    """B-44: schtasks-created tasks inherit DisallowStartIfOnBatteries, so on a
    laptop on battery the run simply does not start, with no diagnostic."""
    xml = _xml()
    assert "<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>" in xml
    assert "<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>" in xml
    assert "<StartWhenAvailable>true</StartWhenAvailable>" in xml


def test_task_xml_pins_the_logon_model_and_working_directory():
    xml = _xml()
    root = ElementTree.fromstring(xml)
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    assert root.find(".//t:Principal/t:LogonType", ns).text == "S4U"
    assert root.find(".//t:Exec/t:WorkingDirectory", ns).text.endswith("pipeline-app")
    assert root.find(".//t:Repetition/t:Interval", ns).text == "PT15M"
```

**Implement** in `setup_discovery_task.py`:

```python
TASK_NAME = "ContentStudio-Discovery"
LOG_NAME = "discovery-task.log"


def default_log_path(pipeline_app_root: Path) -> Path:
    return pipeline_app_root / "logs" / LOG_NAME


def build_task_action(python_exe: Path, cron_script: Path, log_path: Path) -> str:
    """The command Task Scheduler actually runs. Wrapped in `cmd /c` purely for
    the redirection: without it the child's stdout and stderr go to a console
    that does not exist, which is D-02. The doubled outer quotes are cmd.exe's
    rule for a command line that itself starts with a quote."""
    return (f'/c ""{python_exe}" "{cron_script}" --mode scheduled '
            f'>> "{log_path}" 2>&1"')


def build_task_xml(python_exe: Path, cron_script: Path, *, log_path: Path,
                   run_as: str, working_dir: Path | None = None) -> str:
    working_dir = working_dir or cron_script.parent
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>ContentStudio discovery wake (15-minute trigger; run_discovery_cron.py decides per wake whether a run is due).</Description></RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <StartBoundary>2026-01-01T00:00:00</StartBoundary>
      <Repetition><Interval>PT15M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals><Principal id="Author">
    <UserId>{run_as}</UserId><LogonType>S4U</LogonType><RunLevel>LeastPrivilege</RunLevel>
  </Principal></Principals>
  <Settings>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <ExecutionTimeLimit>PT4H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author"><Exec>
    <Command>cmd.exe</Command>
    <Arguments>{escape(build_task_action(python_exe, cron_script, log_path))}</Arguments>
    <WorkingDirectory>{working_dir}</WorkingDirectory>
  </Exec></Actions>
</Task>
"""
```

(`from xml.sax.saxutils import escape`. `LogonType S4U` is the "runs whether the user is logged
on or not, without storing a password" model B-44 asks to be chosen and documented — state it in
the module docstring.)

**Commit:** `fix(setup): register the discovery task from XML with output redirection (D-02, B-42, B-44)`

---

#### - [ ] Task 10 — Verify, refuse to clobber, and uninstall (B-46, B-44)

**Test:**

```python
def test_apply_refuses_to_overwrite_an_existing_task_without_force(monkeypatch, capsys):
    """B-46: /F destroyed and recreated the task, wiping any fix applied by
    hand in the Task Scheduler GUI -- the very fixes B-44 calls for."""
    monkeypatch.setattr("scripts.setup_discovery_task.subprocess.run",
                        _fake_run({("schtasks", "/Query"): 0}))
    assert main(["--apply"]) != 0
    assert "--force" in capsys.readouterr().err


def test_apply_verifies_registration_with_a_query_before_reporting_success(monkeypatch):
    calls = _record_calls(monkeypatch)
    main(["--apply", "--force"])
    assert any("/Query" in c for c in calls[-1])


def test_apply_reports_failure_when_the_verifying_query_finds_nothing(monkeypatch, capsys):
    monkeypatch.setattr("scripts.setup_discovery_task.subprocess.run",
                        _fake_run({("schtasks", "/Create"): 0, ("schtasks", "/Query"): 1}))
    assert main(["--apply", "--force"]) != 0
    assert "could not be verified" in capsys.readouterr().err


def test_remove_deletes_the_task(monkeypatch):
    calls = _record_calls(monkeypatch)
    assert main(["--remove"]) == 0
    assert "/Delete" in calls[0]
```

**Implement:** `--force`, `--remove`; write the XML to a temp file and
`schtasks /Create /TN … /XML <file> /F` only under `--force` or when `/Query` shows no task;
after creation run `schtasks /Query /TN <name>` and return non-zero if it does not confirm.
Every `subprocess.run` passes `encoding="utf-8", errors="replace"` (Global Constraint /
finding B-10), never bare `text=True`. Mark these tests `@pytest.mark.allow_subprocess`.

**Commit:** `feat(setup): verify registration, require --force to clobber, add --remove (B-46)`

---

#### - [ ] Task 11 — The dry run prints a runnable command (B-45)

**Test:**

```python
def test_dry_run_prints_a_command_that_survives_a_round_trip_through_the_shell_parser():
    """B-45: ' '.join(cmd) flattened the /TR payload, so pasting the printed
    line bound /TR to the python path alone and left the script as a stray
    argument. The printed line must be byte-for-byte executable."""
    cmd = ["schtasks", "/Create", "/TN", "ContentStudio-Discovery",
           "/XML", r"C:\repo\pipeline-app\logs\task.xml", "/F"]
    printed = subprocess.list2cmdline(cmd)
    assert printed != " ".join(cmd)
    assert shlex.split(printed, posix=False)[4].strip('"') == r"C:\repo\pipeline-app\logs\task.xml"


def test_dry_run_tells_the_operator_where_the_log_will_be(monkeypatch, capsys):
    main([])
    assert "discovery-task.log" in capsys.readouterr().out
```

**Implement:** `print(subprocess.list2cmdline(cmd))` in place of `print(" ".join(cmd))`, and
print `default_log_path(...)` plus the XML's destination in the dry-run block.

**Commit:** `fix(setup): print the registration command with list2cmdline (B-45)`

---

#### - [ ] Task 12 — The engine's three stderr sites become durable events (D-02)

Per the adoption rule: **keep the print, add the event.** Never widen the `# noqa: BLE001`.

**Test** (`tests/test_discovery_engine.py`):

```python
def test_a_heartbeat_write_failure_leaves_an_event_not_only_a_print(engine_conn, tmp_path, monkeypatch):
    """D-02: this print is the sole detector of the condition that lets B-50's
    double-run happen, and on the scheduled path it goes nowhere."""
    monkeypatch.setattr(db, "update_run_heartbeat",
                        lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("locked")))
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = SlowFakeAdapter({"@a": [{"id": "v1", "title": "x", "published": None}]}, sleep_s=0.2)
    run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual",
                  mode="incremental", heartbeat_interval_s=0.05)
    rows = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.heartbeat_failed'").fetchall()
    assert rows and rows[0]["severity"] == "error"


def test_a_directory_collision_leaves_an_event_naming_both_handles(engine_conn, tmp_path):
    db.create_handle(engine_conn, "youtube", "john.doe.5", "A", "guru", None, now_iso())
    db.create_handle(engine_conn, "youtube", "johndoe5", "B", "guru", None, now_iso())
    run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                  trigger="manual", mode="incremental")
    row = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.slug_collision'").fetchone()
    assert row is not None
    assert "john.doe.5" in row["message"] and "johndoe5" in row["message"]


def test_a_backfill_skip_leaves_an_event(engine_conn, tmp_path):
    ...  # kind = "discovery.backfill_unsupported", severity = "warning"
```

The existing `capsys` assertions at `tests/test_discovery_engine.py:298-301` and `:315` stay
green — the prints are kept, not replaced.

**Implement:** three `obs.record_event(...)` calls beside the existing prints in
`_run_heartbeat_loop`, `_warn_on_directory_collisions` (which now takes `conn`) and the
backfill-skip branch.

**Commit:** `fix(engine): give the three scheduled-path diagnostics a durable surface (D-02)`

---

### Group C — the lock and the watermark (B-48, B-49, B-50, B-52, B-53)

#### - [ ] Task 13 — Run ownership: a sidecar and a Windows-safe liveness probe (B-50)

**Test** (`tests/test_discovery_paths.py` + `tests/test_discovery_engine.py`):

```python
def test_run_owner_path_is_namespaced_and_does_not_collide_with_run_records(tmp_path):
    assert run_owner_path(tmp_path, 7) == tmp_path / "output" / "discovery-runs" / ".owners" / "7.json"


def test_process_is_alive_reports_true_for_this_process_and_false_for_a_dead_pid():
    """NOT os.kill(pid, 0): on Windows os.kill calls TerminateProcess for any
    signal other than CTRL_C_EVENT/CTRL_BREAK_EVENT, so the POSIX idiom would
    kill the very run being checked on."""
    assert _process_is_alive(os.getpid()) is True
    assert _process_is_alive(0x7FFFFFFE) is False


def test_a_run_writes_an_owner_file_and_removes_it_when_it_finishes(engine_conn, tmp_path):
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({"@a": []})},
                           trigger="manual", mode="incremental")
    assert not run_owner_path(tmp_path, result["run_row_id"]).exists()
```

**Implement** — `discovery_paths.py`:

```python
def run_owner_path(repo_root: Path, run_row_id: int) -> Path:
    """Sidecar recording which OS process owns a 'running' row. Lives on disk
    rather than on the row because discovery_runs' schema belongs to another
    package; the reclaim sweep reads it to answer "is that process actually
    gone?" instead of trusting a heartbeat that a sleeping machine freezes."""
    return repo_root / "output" / "discovery-runs" / ".owners" / f"{run_row_id}.json"
```

`discovery_engine.py`:

```python
def _process_is_alive(pid: int) -> bool:
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True     # exists, owned by someone else
        return True
    import ctypes
    SYNCHRONIZE, WAIT_TIMEOUT = 0x00100000, 0x00000102
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
    finally:
        kernel32.CloseHandle(handle)


def _claim_run_ownership(repo_root: Path, run_row_id: int, started_at: str) -> None:
    path = run_owner_path(repo_root, run_row_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pid": os.getpid(), "started_at": started_at,
                                "host": platform.node()}), encoding="utf-8")


def _release_run_ownership(repo_root: Path, run_row_id: int) -> None:
    run_owner_path(repo_root, run_row_id).unlink(missing_ok=True)
```

Call `_claim_run_ownership` immediately after `insert_running_run`, `_release_run_ownership` in
the `finally` beside the heartbeat teardown.

**Commit:** `feat(engine): record which process owns a running run (B-50)`

---

#### - [ ] Task 14 — Reclaim refuses to steal a live run (B-50)

**Test:**

```python
def test_a_stale_heartbeat_does_not_reclaim_a_run_whose_owner_is_still_alive(engine_conn, tmp_path):
    """B-50 (S1): a laptop lid-close freezes the heartbeat thread while the run
    survives; on resume the next wake reclaimed the LIVE run, freeing the
    single-flight index and starting a second, concurrently-billing run."""
    stale_id = db.insert_running_run(engine_conn, "live-run", "manual", "incremental",
                                     "2026-07-30T05:00:00+00:00")
    _claim_run_ownership(tmp_path, stale_id, "2026-07-30T05:00:00+00:00")  # this process: alive
    now = _dt.datetime(2026, 7, 30, 6, 0, 0, tzinfo=_dt.timezone.utc)
    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                           trigger="manual", mode="incremental", now=now)
    assert db.get_run(engine_conn, stale_id)["status"] == "running"   # not stolen
    assert result["status"] == "locked"                                # and we backed off


def test_a_stale_run_whose_owner_is_gone_is_still_reclaimed(engine_conn, tmp_path):
    stale_id = db.insert_running_run(engine_conn, "dead-run", "manual", "incremental",
                                     "2026-07-30T05:00:00+00:00")
    _claim_run_ownership(tmp_path, stale_id, "2026-07-30T05:00:00+00:00")
    run_owner_path(tmp_path, stale_id).write_text(json.dumps({"pid": 0x7FFFFFFE, "started_at": "x"}),
                                                  encoding="utf-8")
    ...
    assert db.get_run(engine_conn, stale_id)["status"] == "abandoned"


def test_a_refused_reclaim_leaves_a_warning_event(engine_conn, tmp_path):
    ...  # kind = "discovery.reclaim_refused", severity = "warning"
```

**Implement** — replace the bare `db_mod.reclaim_stale_runs(...)` call site with:

```python
def reclaim_stale_runs_owned(conn, repo_root: Path, now: _dt.datetime, stale_after_s: int) -> list[int]:
    """db.reclaim_stale_runs decides purely on heartbeat age. A sleeping machine
    and a locked-DB heartbeat both freeze that clock while the run is very much
    alive, so ask the OS before stealing the lock (B-50)."""
    protected: list[int] = []
    for row in conn.execute("SELECT id FROM discovery_runs WHERE status = 'running'").fetchall():
        owner = _read_run_owner(repo_root, row["id"])
        if owner and _process_is_alive(owner["pid"]):
            protected.append(row["id"])
            obs.record_event(conn, kind="discovery.reclaim_refused", severity="warning",
                             source="discovery_engine",
                             message=f"run {row['id']} looks stale but pid {owner['pid']} is alive",
                             detail=owner, run_id=row["id"])
    if protected:
        return []      # a live owner exists: back off entirely, do not reclaim
    return db_mod.reclaim_stale_runs(conn, now_iso(now), stale_after_s)
```

**Commit:** `fix(engine): reclaim only when the owning process is provably gone (B-50)`

---

#### - [ ] Task 15 — A reclaimed run cannot resurrect itself (B-50)

**Test:**

```python
def test_finish_run_cannot_resurrect_an_abandoned_run(engine_conn, tmp_path):
    """B-50's evidence-erasing half: db.finish_run has no status precondition,
    so the original process overwrote its own 'abandoned' row back to
    'completed' and -- if scheduled -- wrote the watermark, erasing the only
    evidence that two runs had been live at once."""
    run_row_id = db.insert_running_run(engine_conn, "r", "scheduled", "incremental", now_iso())
    engine_conn.execute("UPDATE discovery_runs SET status = 'abandoned' WHERE id = ?", (run_row_id,))
    engine_conn.commit()
    assert _finish_run_guarded(engine_conn, run_row_id, "completed", now_iso(), "x.md") is False
    assert db.get_run(engine_conn, run_row_id)["status"] == "abandoned"


def test_a_refused_finish_leaves_an_error_event(engine_conn, tmp_path):
    ...  # kind = "discovery.finish_run_refused", severity = "error"
```

**Implement:**

```python
TERMINAL_RUN_STATUSES = frozenset({"completed", "completed_with_errors", "failed",
                                   "abandoned", "locked"})


def _finish_run_guarded(conn, run_row_id: int, status: str, finished_at: str, md_path: str) -> bool:
    """Status precondition db.finish_run lacks. Read-then-write, not atomic:
    the durable fix is a `WHERE status = 'running'` inside db.finish_run, which
    belongs to P1. This closes the realistic case (minutes apart, not
    microseconds) and reports the refusal instead of silently overwriting."""
    current = db_mod.get_run(conn, run_row_id)
    if current is not None and current["status"] in TERMINAL_RUN_STATUSES and current["status"] != status:
        obs.record_event(conn, kind="discovery.finish_run_refused", severity="error",
                         source="discovery_engine",
                         message=(f"run {run_row_id} is already {current['status']}; refusing to "
                                  f"overwrite it with {status} -- it was reclaimed while still live"),
                         run_id=run_row_id)
        return False
    db_mod.finish_run(conn, run_row_id, status, finished_at, md_path)
    return True
```

Route **every** `db_mod.finish_run` call in `discovery_engine.py` through it, and skip the
watermark write when it returns `False`.

**Commit:** `fix(engine): a reclaimed run can no longer overwrite its own abandoned row (B-50)`

---

#### - [ ] Task 16 — Reclaim runs before the due-check (B-52)

**Test:**

```python
def test_a_stale_run_is_reclaimed_even_when_today_is_not_due(monkeypatch, repo_root):
    """B-52: reclaim lived inside run_discovery, which the scheduled path never
    reaches once is_due returns False -- so a Run Now that died hard after the
    day's scheduled run left a row 'in progress' until tomorrow."""
    conn = db.get_connection(repo_root / "pipeline-app" / "pipeline.db")
    stale_id = db.insert_running_run(conn, "dead", "manual", "incremental", "2026-07-30T05:00:00+00:00")
    conn.commit()
    monkeypatch.setattr(cron, "_is_due_now", lambda c: False)
    assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) == cron.Exit.OK
    assert db.get_run(conn, stale_id)["status"] == "abandoned"
```

**Implement** in `run_discovery_cron.main()`, immediately after the connection opens and
**before** the due-check:

```python
        reclaimed = sweep_stale_runs(conn, repo_root, stale_after_s=args.stale_after_s)
        if reclaimed:
            obs.record_event(conn, kind="discovery.runs_reclaimed", severity="warning",
                             source="run_discovery_cron",
                             message=f"reclaimed {len(reclaimed)} stale run(s): {reclaimed}")
```

`sweep_stale_runs` is `discovery_engine`'s `reclaim_stale_runs_owned` +
`_write_abandoned_records_for_reclaimed_runs`, exported so the cron can call it without
starting a run.

**Commit:** `fix(cron): sweep stale runs before the due-check, not inside run_discovery (B-52)`

---

#### - [ ] Task 17 — A long run stops manufacturing junk (B-49)

**Test** — the engine test at `tests/test_discovery_engine.py:391` is **inverted** here:

```python
def test_a_lost_lock_does_not_write_a_markdown_record(engine_conn, tmp_path):
    """Inverts test_run_discovery_second_concurrent_call_is_locked:391
    ('locked runs still get a paired record'). B-49: a 90-minute Bright Data
    run left five locked rows and five junk files, burying the real result."""
    db.insert_running_run(engine_conn, "already-running", "manual", "incremental", now_iso())
    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                           trigger="manual", mode="incremental")
    assert result["status"] == "locked"
    assert db.get_run(engine_conn, result["run_row_id"])["md_path"] is None
    assert list((tmp_path / "output" / "discovery-runs").glob("*.md")) == []


def test_the_scheduled_path_short_circuits_when_a_run_is_already_active(monkeypatch, repo_root):
    conn = db.get_connection(repo_root / "pipeline-app" / "pipeline.db")
    db.insert_running_run(conn, "in-flight", "manual", "incremental", now_iso())
    conn.commit()
    monkeypatch.setattr(cron, "_is_due_now", lambda c: True)
    monkeypatch.setattr(cron, "run_discovery",
                        lambda *a, **k: pytest.fail("the engine must not be reached"))
    assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) == cron.Exit.LOCKED
    assert len(db.list_runs(conn)) == 1     # no junk 'locked' row was added
```

**Implement:** drop the `write_run_record` call from the engine's lock-loss branch (keep the DB
row — it is the honest record that a call was refused); in the cron, after the stale sweep, if
`db.get_running_run(conn)` is not `None`, record `discovery.run_already_active` and return
`Exit.LOCKED` without calling `run_discovery`.

**Commit:** `fix(engine,cron): stop persisting a record for a no-op lock loss (B-49)`

---

#### - [ ] Task 18 — A timezone change cannot fire a second run the same day (B-48)

**Test** (`tests/test_discovery_scheduling.py`):

```python
def test_a_timezone_change_cannot_fire_a_second_run_the_same_day():
    """B-48: last_scheduled_run_date was a bare local date computed under the
    timezone configured at WRITE time and compared under the one configured at
    READ time. Changing the setting made today's date differ from the stored
    string while the same day was still in progress -- a full second run, a
    duplicate billable Bright Data pass for every handle."""
    ran_at = _dt.datetime(2026, 7, 30, 12, 0, tzinfo=_dt.timezone.utc)   # 07:00 Chicago
    watermark = encode_watermark("2026-07-30", "America/Chicago", ran_at.isoformat(timespec="seconds"))
    two_hours_later = _dt.datetime(2026, 7, 30, 14, 0, tzinfo=_dt.timezone.utc)
    assert is_due(two_hours_later, "Pacific/Auckland", "06:00", watermark) is False


def test_a_legacy_bare_date_watermark_still_works():
    now = _dt.datetime(2026, 7, 30, 12, 0, tzinfo=_dt.timezone.utc)
    assert is_due(now, "America/Chicago", "06:00", "2026-07-30") is False


def test_the_next_day_still_fires_after_the_minimum_interval():
    ran_at = _dt.datetime(2026, 7, 30, 11, 0, tzinfo=_dt.timezone.utc)
    watermark = encode_watermark("2026-07-30", "America/Chicago", ran_at.isoformat(timespec="seconds"))
    tomorrow = _dt.datetime(2026, 7, 31, 11, 30, tzinfo=_dt.timezone.utc)
    assert is_due(tomorrow, "America/Chicago", "06:00", watermark) is True
```

The five existing `is_due` tests (`:6-28`) keep passing unchanged — they pass bare dates.

**Implement** in `discovery_scheduling.py`:

```python
WATERMARK_SEP = "|"
MIN_RUN_INTERVAL_H = 20     # < 24 so a schedule time change still fires; > 12 so no
                            # timezone edit, DST shift or clock skew can double-fire


def encode_watermark(local_date: str, timezone_name: str, run_instant_utc: str) -> str:
    return WATERMARK_SEP.join([local_date, timezone_name, run_instant_utc])


def decode_watermark(raw: str | None) -> tuple[str | None, _dt.datetime | None]:
    """Returns (local_date, run_instant). Accepts the legacy bare 'YYYY-MM-DD'
    form so an existing install does not re-fire on the first upgraded wake."""
    if not raw:
        return None, None
    parts = raw.split(WATERMARK_SEP)
    if len(parts) != 3:
        return parts[0], None
    try:
        return parts[0], _dt.datetime.fromisoformat(parts[2])
    except ValueError:
        return parts[0], None
```

`is_due` gains, before the local-date comparison:

```python
    last_date, last_instant = decode_watermark(last_scheduled_run_date)
    if last_instant is not None and (now - last_instant) < _dt.timedelta(hours=MIN_RUN_INTERVAL_H):
        return False
```

and `discovery_engine.py` writes `set_last_scheduled_run_date(conn, encode_watermark(local_date,
timezone_name, now_iso(now)))`. The engine tests at `:503`, `:518` assert the bare date and are
**extended** to `assert decode_watermark(stored)[0] == "2026-07-30"`.

**Commit:** `fix(scheduling): watermark carries its instant, so a timezone edit cannot double-fire (B-48)`

---

#### - [ ] Task 19 — A skipped day is visible as a gap (B-48, D-06)

**Test:**

```python
def test_a_machine_that_was_off_for_two_days_records_a_gap_warning(monkeypatch, repo_root):
    """D-06's proposed fix: surface 'last successful scheduled run' so a gap is
    visible AS a gap rather than as silence. A machine asleep across
    time_of_day skips the day with no signal whatsoever today."""
    conn = db.get_connection(repo_root / "pipeline-app" / "pipeline.db")
    db.set_last_scheduled_run_date(conn, encode_watermark(
        "2026-07-28", "America/Chicago", "2026-07-28T11:00:00+00:00"))
    conn.commit()
    monkeypatch.setattr(cron, "_is_due_now", lambda c: True)
    monkeypatch.setattr(cron, "notify", lambda *a, **k: True)
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result("completed", total=1, attempted=1))
    cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    row = conn.execute("SELECT * FROM events WHERE kind = 'discovery.days_skipped'").fetchone()
    assert row is not None and row["severity"] == "warning"
    assert "2026-07-28" in row["message"]
```

**Implement:** in the cron, once a run is confirmed due, compare `decode_watermark(...)[1]` to
`now`; if the gap exceeds `_dt.timedelta(hours=44)`, record `discovery.days_skipped`.

**Commit:** `feat(cron): report a skipped scheduled day instead of silently catching up (B-48, D-06)`

---

#### - [ ] Task 20 — Deadlines: a hung adapter no longer wedges discovery (B-53)

**Test:**

```python
def test_a_handle_that_never_returns_is_recorded_as_an_error_and_the_run_finishes(engine_conn, tmp_path):
    """B-53: nothing bounded a run's duration, so one blocking network call held
    the status='running' row -- and the single-flight lock -- forever, while the
    run history showed a run that looked healthy and in progress."""
    class HangingAdapter(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter):
            time.sleep(30)
    db.create_handle(engine_conn, "youtube", "@hang", "H", "guru", None, now_iso())
    result = run_discovery(engine_conn, tmp_path, {"youtube": HangingAdapter({})},
                           trigger="manual", mode="incremental", per_handle_deadline_s=0.2)
    assert result["status"] == "completed_with_errors"
    row = db.list_run_handle_results(engine_conn, result["run_row_id"])[0]
    assert "TimeoutError" in row["error_message"]
    assert db.get_running_run(engine_conn) is None          # the lock was released


def test_a_run_that_blows_its_overall_deadline_ends_failed_not_running(engine_conn, tmp_path):
    ...  # run_deadline_s=0.0 with two handles -> status 'failed', event kind
         # 'discovery.run_deadline_exceeded', severity 'error'
```

**Implement** in `discovery_engine.py`: `run_discovery` gains `per_handle_deadline_s: float =
900.0` and `run_deadline_s: float = 5400.0`. Each handle runs through a one-worker
`ThreadPoolExecutor` with `future.result(timeout=per_handle_deadline_s)`; a
`concurrent.futures.TimeoutError` is recorded as a per-handle `error` reading
`TimeoutError: handle exceeded its {n}s deadline`. Between handles, if
`now_utc() - run_started >= run_deadline_s`, stop the loop, set `outer_crash` to a
`RunDeadlineExceeded`, and let the existing outer handler produce `failed`.

Document the honest caveat in the docstring: the abandoned worker thread is a daemon and may
still be blocked on the socket — the run is unwedged, the thread is not, and the durable fix is
socket timeouts inside the adapters (T4 / packages P6-P7).

**Commit:** `feat(engine): per-handle and overall run deadlines (B-53)`

---

### Group D — per-handle truth (B-51, B-54, B-55, B-56, B-57)

#### - [ ] Task 21 — Partial downloads survive a raising handle (B-54)

**Test:**

```python
def test_a_handle_that_raises_after_two_downloads_records_two_not_zero(engine_conn, tmp_path):
    """B-54: process_handle accumulated `downloaded` in a local destroyed on
    raise, so the except branch hardcoded items_downloaded=0 -- the DB row, the
    markdown record and last_seen_published_at all under-reported real work
    that is on disk, permanently."""
    class FailsOnThird(SingleFakeAdapter):
        def download_item(self, repo_root, handle, item_id, title, content_type=None):
            if item_id == "v3":
                raise RuntimeError("rate limited")
            return {"id": item_id, "ok": True, "published": "2026-07-29"}
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = FailsOnThird({"@a": [{"id": f"v{i}", "title": "x", "published": "2026-07-29"}
                                    for i in (1, 2, 3)]})
    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter},
                           trigger="manual", mode="incremental")
    row = db.list_run_handle_results(engine_conn, result["run_row_id"])[0]
    assert row["status"] == "error"
    assert row["items_downloaded"] == 2


def test_a_partly_downloaded_handle_still_advances_last_seen(engine_conn, tmp_path):
    ...  # assert get_handle(...)["last_seen_published_at"] == "2026-07-29"
```

**Implement:**

```python
class HandleFailure(Exception):
    """Carries the items already written to disk when a walk fails partway, so
    the run records real work instead of 0 (B-54). The engine's per-handle
    except branch reads .downloaded and .cause."""
    def __init__(self, cause: BaseException, downloaded: list[dict]):
        super().__init__(f"{type(cause).__name__}: {cause}")
        self.cause, self.downloaded = cause, downloaded
```

Wrap the bodies of `process_handle` and `process_handle_backfill`:

```python
    downloaded: list[dict] = []
    try:
        ...existing walk...
    except HandleFailure:
        raise
    except Exception as exc:
        raise HandleFailure(exc, downloaded) from exc
    return downloaded
```

and in the engine's per-handle `except`, read `getattr(exc, "downloaded", [])`, advance
`set_handle_last_seen` from it, and pass `len(partial)` to `record_handle_result`.

**Commit:** `fix(engine): a handle that fails partway records the items it actually got (B-54)`

---

#### - [ ] Task 22 — `error_message` names the exception type (B-55)

**Test:**

```python
def test_an_unknown_platform_error_message_names_the_exception_type(engine_conn, tmp_path):
    """B-55: str(KeyError('youtub')) stores the literal 'youtub'; str(IndexError())
    stores an empty string. With no log file that string is the entire
    post-mortem, and it is rendered verbatim in the UI and the record."""
    db.create_handle(engine_conn, "youtub", "@a", "A", "guru", None, now_iso())
    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                           trigger="manual", mode="incremental")
    row = db.list_run_handle_results(engine_conn, result["run_row_id"])[0]
    assert row["error_message"].startswith("KeyError:")


def test_an_empty_str_exception_is_still_identifiable(engine_conn, tmp_path):
    ...  # IndexError() -> "IndexError: " -- never the empty string


def test_the_full_traceback_reaches_the_event_detail(engine_conn, tmp_path):
    ...  # detail["traceback"] contains "Traceback (most recent call last)"
```

**Implement:** `message = f"{type(cause).__name__}: {cause}"` at both per-handle sites and both
validate sites; `traceback.format_exc()` into the `discovery.handle_failed` event's `detail`.

**Commit:** `fix(engine): per-handle error messages carry the exception type (B-55)`

---

#### - [ ] Task 23 — Abandoned records stop contradicting their own DB rows (B-51)

**Test:**

```python
def test_an_abandoned_record_reports_the_work_its_db_rows_prove(engine_conn, tmp_path):
    """B-51: _write_abandoned_records_for_reclaimed_runs passed [] by design, so
    the markdown record -- the durable artifact a future reader trusts -- said
    'Pulled 0 new items across 0 handles' while discovery_run_handles held a row
    per completed handle. On a hard reboot mid-run it is the only post-mortem."""
    handle_id = db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    dead_id = db.insert_running_run(engine_conn, "dead", "manual", "incremental",
                                    "2026-07-30T05:00:00+00:00")
    db.record_handle_result(engine_conn, dead_id, handle_id, "ok", 4)
    now = _dt.datetime(2026, 7, 30, 6, 0, tzinfo=_dt.timezone.utc)
    run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                  trigger="manual", mode="incremental", now=now)
    record = Path(db.get_run(engine_conn, dead_id)["md_path"]).read_text(encoding="utf-8")
    assert "items_downloaded: 4" in record
    assert "partial" in record.lower()
```

**Implement:** `_write_abandoned_records_for_reclaimed_runs` reads
`db_mod.list_run_handle_results(conn, reclaimed_id)`, joins each to its handle row, and passes
the reconstructed results with `partial=True`; `write_run_record` gains
`partial: bool = False` and prefixes the summary with
`"Partial -- the process died; these counts are a floor."`.

**Commit:** `fix(engine): abandoned records report the work their DB rows prove (B-51)`

---

#### - [ ] Task 24 — Frontmatter totals reconcile (B-56)

**Test** (`tests/test_discovery_records.py` — the existing suite asserts counters against a
literal it wrote and never that they reconcile):

```python
def test_frontmatter_status_counts_always_sum_to_handles_processed(tmp_path):
    """B-56: status_counts was seeded with four keys so four lookups could not
    KeyError; .get(status, 0) + 1 happily admitted a fifth, 'skipped', which a
    backfill produces for every Bright Data handle -- and nothing emitted it.
    handles_processed: 12 with the four published counters summing to 3."""
    results = [
        {"handle": f"@h{i}", "platform": "instagram", "cohort": "guru", "status": status,
         "items_downloaded": 0, "last_seen_published_at": None, "error_message": None}
        for i, status in enumerate(["ok", "no_new_content", "skipped", "skipped",
                                    "handle_not_found", "error"])
    ]
    path = write_run_record(tmp_path, _run_row(), results)
    fm = yaml.safe_load(path.read_text(encoding="utf-8").split("---\n")[1])
    counters = {k: v for k, v in fm.items() if k.startswith("handles_") and k != "handles_processed"}
    assert sum(counters.values()) == fm["handles_processed"] == 6
    assert fm["handles_skipped"] == 2


def test_a_future_handle_status_cannot_silently_vanish_from_the_frontmatter(tmp_path):
    """The key set is derived from the observed statuses, so a status added
    later is emitted rather than dropped."""
    results = [{**_r(), "status": "quarantined"}]
    fm = yaml.safe_load(write_run_record(tmp_path, _run_row(), results)
                        .read_text(encoding="utf-8").split("---\n")[1])
    assert fm["handles_quarantined"] == 1


def test_the_summary_sentence_mentions_skipped_handles(tmp_path):
    ...  # "2 skipped" appears in the '## Summary' body
```

**Implement** in `discovery_records.py`:

```python
    KNOWN = ("ok", "no_new_content", "handle_not_found", "error", "skipped")
    status_counts = dict.fromkeys(KNOWN, 0)
    for r in handle_results:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        items_downloaded += r["items_downloaded"]
    ...
    frontmatter.update({f"handles_{status}": count for status, count in status_counts.items()})
```

Keep the four legacy key names (`handles_ok`, `handles_no_new_content`, `handles_not_found`,
`handles_errored`) as explicit aliases so any existing parser keeps working — the existing test
at `:29-34` must stay green.

**Commit:** `fix(records): emit every handle status so the frontmatter totals reconcile (B-56)`

---

#### - [ ] Task 25 — A transient failure no longer permanently excludes a handle (B-57)

The engine tests at `tests/test_discovery_engine.py:423-432` and `:435-445` assert the defective
behaviour and are **inverted** here.

**Test:**

```python
def test_a_transient_validate_failure_leaves_the_handle_pending_and_included(engine_conn, tmp_path):
    """Inverts test_run_discovery_validate_handle_sets_invalid_and_excludes_on_crash:435.
    B-57: the blanket except set 'invalid' AND cleared 'included' with no
    distinction between 'this account does not exist' and 'the VPN was up' --
    quietly and permanently removing a valid handle from every future run."""
    handle_id = db.create_handle(engine_conn, "youtube", "@crashy", "C", "guru", None, now_iso())
    adapter = SingleFakeAdapter({}, fail_handles={"@crashy"})
    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter},
                           trigger="manual", mode="validate_handle", handle_id=handle_id)
    row = db.get_handle(engine_conn, handle_id)
    assert result["status"] == "failed"           # the run still reports the failure
    assert row["status"] == "pending"             # ...but the handle is retryable
    assert row["included"] == 1


def test_an_empty_enumeration_is_not_treated_as_proof_of_non_existence(engine_conn, tmp_path):
    """Inverts ..._sets_invalid_and_excludes_on_empty_enumeration:423. An empty
    result is D-03's ambiguity: a dead handle and a failed fetch look alike."""
    handle_id = db.create_handle(engine_conn, "youtube", "@dead", "D", "guru", None, now_iso())
    run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({"@dead": []})},
                  trigger="manual", mode="validate_handle", handle_id=handle_id)
    assert db.get_handle(engine_conn, handle_id)["included"] == 1


def test_a_definitive_not_found_does_exclude_the_handle(engine_conn, tmp_path):
    class GoneAdapter(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter):
            raise HandleNotFound("account does not exist")
    ...
    assert db.get_handle(engine_conn, handle_id)["status"] == "invalid"
    assert db.get_handle(engine_conn, handle_id)["included"] == 0


def test_a_transient_validate_failure_leaves_a_warning_event(engine_conn, tmp_path):
    ...  # kind = "discovery.validate_transient_failure", severity = "warning"
```

**Implement:**

```python
class HandleNotFound(Exception):
    """The account provably does not exist. Only this excludes a handle (B-57).
    Adapters (packages P6/P7) must raise it for a definitive 404/'no such
    account'; until they do, nothing is auto-excluded -- the safe direction,
    since B-57's damage is a VALID handle silently dropped from every run."""
```

Validate path: `HandleNotFound` → `invalid` + excluded, as today. Any other exception, and an
empty enumeration → leave `status='pending'` and `included` untouched, record the reason in the
run row and an event, return `failed` / `completed_with_errors` respectively.

**Commit:** `fix(engine): only a definitive not-found excludes a handle (B-57)`

---

### Group E — the routes (F-68, B-58, B-60, B-47b, B-59, B-61, E-11, B-43)

#### - [ ] Task 26 — The spawn seam, so a forgotten stub fails instead of billing (F-68)

Seven hand-rolled `Popen` stubs (`tests/test_routes_discovery.py:35, 53-55, 128, 142, 155, 168,
179`) are the *only* thing standing between the suite and a real, per-record-billed Bright Data
job. Replace all seven with one seam plus one module fixture.

**Test:**

```python
@pytest.fixture
def spawns(monkeypatch):
    """The single spawn stub for this module. Replaces routes.discovery._popen,
    NOT subprocess.Popen, so the repo-wide conftest guard stays armed for
    everything else -- and a route test that forgets this fixture hits the real
    Popen, trips the guard, and FAILS instead of launching a billed job (F-68)."""
    recorded: list[list[str]] = []
    monkeypatch.setattr("pipeline_app.routes.discovery._popen",
                        lambda cmd, **kw: recorded.append(cmd) or _FakeProc())
    return recorded


def test_a_discovery_post_without_the_spawn_stub_raises_instead_of_billing(client):
    """The guard, asserted. Without it this POST launches a detached, live,
    per-record-billed collection job and the test still passes, because the
    spawn is fire-and-forget and nothing asserts on it."""
    with pytest.raises(RuntimeError, match="subprocess"):
        client.post("/discovery/run-now")


def test_every_spawn_site_goes_through_the_single_seam():
    source = Path(discovery_routes.__file__).read_text(encoding="utf-8")
    assert source.count("subprocess.Popen") == 1     # only inside _popen
```

**Implement** in `routes/discovery.py`:

```python
def _popen(cmd: list[str], **kwargs) -> subprocess.Popen:
    """The single process-spawn seam for this module. Tests replace THIS, so
    the repo-wide conftest guard on subprocess.Popen stays armed and a route
    test that forgets to stub fails loudly instead of billing (F-68)."""
    return subprocess.Popen(cmd, **kwargs)
```

`_spawn_cron` calls `_popen`. Every existing route test switches to the `spawns` fixture.

**Commit:** `test(routes): route every spawn through one seam so the network guard stays armed (F-68)`

---

#### - [ ] Task 27 — `platform` is validated against the adapter registry (B-58)

**Test:**

```python
def test_add_handle_rejects_a_platform_no_adapter_serves(client, spawns):
    """B-58: an unvalidated platform was persisted, then adapters[platform]
    raised KeyError OUTSIDE run_discovery's try -- the fire-and-forget child
    died with a traceback nobody saw, no run row was written, and the handle
    sat at 'pending' forever with no explanation."""
    response = client.post("/discovery/handles", data={
        "platform": "youtub", "handle": "@a", "display_name": "",
        "cohort": "guru", "keyword_filter": ""})
    assert response.status_code == 400
    assert "youtub" in response.text and "youtube" in response.text   # names the valid set


def test_a_rejected_platform_is_neither_stored_nor_spawned(client, spawns):
    client.post("/discovery/handles", data={"platform": "youtub", "handle": "@a",
                                            "display_name": "", "cohort": "guru", "keyword_filter": ""})
    assert spawns == []
    assert "@a" not in client.get("/discovery/handles").text


def test_the_adapter_registry_and_the_declared_platform_set_agree():
    """The route's gate and the engine's lookup must not drift: build_adapters
    is what adapters[platform] indexes."""
    assert set(cron.build_adapters()) == discovery_engine.SUPPORTED_PLATFORMS


def test_the_declared_platform_set_matches_the_storage_constraint():
    """B-73 (P1) complementarity. P1's schema CHECK and P8's route gate must
    carry ONE vocabulary; two lists drift, and a drifted route gate rejects a
    platform the storage layer would have accepted (or vice versa)."""
    schema = (Path(db_mod.__file__).parent / "schema.sql").read_text(encoding="utf-8")
    declared = set(re.findall(r"'([a-z-]+)'", schema.split("platform TEXT NOT NULL CHECK")[1]
                                                     .split(")")[0]))
    assert declared == discovery_engine.SUPPORTED_PLATFORMS


def test_a_bad_platform_is_rejected_before_the_storage_constraint_can_fire(client, spawns, monkeypatch):
    """B-73's two halves are complementary, not duplicated. P1's CHECK is the
    durable backstop that also covers the migration path; this gate exists so
    the operator gets a message naming the valid set instead of a 500 carrying
    'CHECK constraint failed: handles'."""
    def explode(*a, **k):
        raise AssertionError("the route must reject before reaching create_handle")
    monkeypatch.setattr(db_mod, "create_handle", explode)
    response = client.post("/discovery/handles", data={
        "platform": "youtub", "handle": "@a", "display_name": "",
        "cohort": "guru", "keyword_filter": ""})
    assert response.status_code == 400
    assert "CHECK constraint" not in response.text
```

**Implement:** `SUPPORTED_PLATFORMS: frozenset[str]` in `discovery_engine.py` (the canonical
set); the route validates against it before `create_handle` and returns 400 naming the valid
values. Complements P1's schema `CHECK` (B-73): the CHECK is the durable backstop that also
covers the migration path P8 cannot reach; this is the fast, message-bearing gate keyed to the
runtime registry, and the drift test above is what keeps the two vocabularies identical. Also
move the `adapters[...]` and `get_handle(...)` lookups in the validate path **inside** the
`try`, so an unknown platform produces a recorded `failed` run instead of a dead process.

**Commit:** `fix(routes,engine): validate platform against the adapter registry (B-58, B-73)`

---

#### - [ ] Task 28 — Backfill dates are validated (B-60)

**Test:**

```python
def test_backfill_rejects_an_inverted_date_range(client, spawns):
    """B-60: start > end passed every check, called enumerate_newest_first for
    every YouTube and Bluesky handle -- the BILLABLE step -- then filtered out
    100% of items and reported a healthy 'no_new_content' for every handle.
    Paid for, captured nothing, looks like a quiet day."""
    response = client.post("/discovery/run-now-backfill",
                           data={"start": "2026-06-30", "end": "2026-06-01"})
    assert response.status_code == 400
    assert spawns == []


def test_backfill_rejects_a_malformed_date(client, spawns):
    assert client.post("/discovery/run-now-backfill",
                       data={"start": "June 1st", "end": "2026-06-30"}).status_code == 400
    assert spawns == []


def test_backfill_rejects_an_argv_like_value(client, spawns):
    """A value beginning with '--' was consumed by the child's argparse as a
    flag, producing exit 2 and total silence in the UI."""
    assert client.post("/discovery/run-now-backfill",
                       data={"start": "--repo-root", "end": "2026-06-30"}).status_code == 400


def test_backfill_rejects_an_absurd_window(client, spawns):
    assert client.post("/discovery/run-now-backfill",
                       data={"start": "1970-01-01", "end": "2026-06-30"}).status_code == 400
```

**Implement:** a `_parse_backfill_dates(start, end)` helper returning `(date, date)` or raising
a `ValueError` the route turns into a 400: strict `%Y-%m-%d`, `start <= end`, window
`<= MAX_BACKFILL_DAYS = 730`, and a rejection of any value starting with `-`.

**Commit:** `fix(routes): validate backfill dates before spawning a billable pass (B-60)`

---

#### - [ ] Task 29 — Schedule settings are validated at the form (B-47, route half)

**Test:**

```python
def test_settings_route_rejects_an_unknown_timezone(client):
    response = client.post("/discovery/settings",
                           data={"time_of_day": "06:00", "timezone": "America/Chicgo"})
    assert response.status_code == 400
    assert "America/Chicgo" in response.text


def test_settings_route_rejects_a_non_hhmm_time(client):
    assert client.post("/discovery/settings",
                       data={"time_of_day": "6am", "timezone": "America/Chicago"}).status_code == 400


def test_a_rejected_setting_is_not_persisted(client):
    client.post("/discovery/settings", data={"time_of_day": "06:00", "timezone": "America/Chicago"})
    client.post("/discovery/settings", data={"time_of_day": "06:00", "timezone": "America/Chicgo"})
    assert db_mod.get_settings(client.app.state.conn)["timezone"] == "America/Chicago"
```

**Implement:** the route calls `discovery_scheduling.resolve_timezone` and
`parse_time_of_day` — the *same* functions `is_due` uses, so the 400 and the runtime check can
never drift — and returns `PlainTextResponse(..., 400)` on `ScheduleConfigError`.

**Commit:** `fix(routes): validate schedule settings against the same parser is_due uses (B-47)`

---

#### - [ ] Task 30 — Run Now stops stacking, and a lost race stops crashing (B-59)

**Test:**

```python
def test_run_now_refuses_to_spawn_while_a_run_is_active(client, spawns):
    db_mod.insert_running_run(client.app.state.conn, "in-flight", "manual", "incremental", _now())
    response = client.post("/discovery/run-now")
    assert response.status_code == 409
    assert spawns == []


def test_a_lock_loss_retries_once_instead_of_re_raising(engine_conn, tmp_path, monkeypatch):
    """B-59's TOCTOU: if the winner finished between the loser's IntegrityError
    and its get_running_run() is None check, the loser RE-RAISED -- legitimate
    lock contention surfaced as an unhandled IntegrityError, a dead subprocess,
    and no run row at all."""
    calls = {"n": 0}
    real_insert = db.insert_running_run
    def flaky(conn, *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise sqlite3.IntegrityError("UNIQUE constraint failed")
        return real_insert(conn, *a, **k)
    monkeypatch.setattr(db, "insert_running_run", flaky)
    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                           trigger="manual", mode="incremental")
    assert result["status"] == "completed"     # not an escaped IntegrityError
```

**Implement:** the route checks `db_mod.get_running_run(conn)` and returns 409 with a message
before spawning; the engine's lock-loss branch retries `insert_running_run` **once** when
`get_running_run(conn) is None` (the winner finished in the gap) before re-raising.

**Commit:** `fix(routes,engine): guard Run Now and make the lock-loss branch race-tolerant (B-59)`

---

#### - [ ] Task 31 — A dead spawn is visible (B-61, E-11)

**Test:**

```python
def test_a_spawn_is_recorded_with_its_pid_and_a_captured_output_path(client, spawns, tmp_path):
    """B-61: all three spawn sites redirected 303 immediately with no PID
    retained, no returncode checked and stdout/stderr inherited from uvicorn.
    Every failure that kills the child produced the identical experience: a
    clean redirect to a page with nothing new on it."""
    client.post("/discovery/run-now")
    row = client.app.state.conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.spawn_requested'").fetchone()
    assert row is not None
    detail = json.loads(row["detail"])
    assert detail["pid"] == 1
    assert detail["log_path"].endswith(".log")


def test_the_child_s_stdout_and_stderr_are_captured_to_a_file(client, monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr("pipeline_app.routes.discovery._popen",
                        lambda cmd, **kw: captured.update(kw) or _FakeProc())
    client.post("/discovery/run-now")
    assert captured["stdout"] is not None and captured["stderr"] is not None


def test_the_runs_page_context_names_a_spawn_that_never_produced_a_run(client, spawns):
    """E-11: the redirected page almost always rendered the PREVIOUS state, so
    the operator's honest read was 'nothing happened' and the natural response
    was to click Run Now again."""
    client.post("/discovery/run-now")
    response = client.get("/discovery/runs")
    assert response.status_code == 200
    assert response.context["pending_spawns"]
```

**Implement:** `discovery_paths.spawn_log_path(repo_root, spawn_id)` →
`output/discovery-runs/spawn-logs/<spawn_id>.log`; `_spawn_cron` opens it, passes it as
`stdout=`/`stderr=`, and records `discovery.spawn_requested` with `{spawn_id, pid, argv,
log_path, requested_at}`. `discovery_runs_page` selects recent `discovery.spawn_requested`
events with no run started after them and passes them as `pending_spawns`. (P15 renders it.)

**Commit:** `feat(routes): capture and record every spawn so a dead child is visible (B-61, E-11)`

---

#### - [ ] Task 32 — The runs page can answer "is anything unhealthy?" (B-43, route half)

**Test:**

```python
def test_the_runs_page_is_capped_and_does_not_grow_without_bound(client):
    for i in range(60):
        db_mod.insert_terminal_run(client.app.state.conn, f"r{i}", "scheduled", "incremental",
                                    "completed", _now(), _now())
    assert len(client.get("/discovery/runs").context["runs_with_results"]) == 25


def test_the_runs_page_exposes_a_health_summary_of_the_recent_window(client):
    """B-43: the route did no aggregation, so an operator could not answer 'have
    any of my last seven runs been unhealthy?' without reading every row."""
    conn = client.app.state.conn
    db_mod.insert_terminal_run(conn, "ok1", "scheduled", "incremental", "completed", _now(), _now())
    db_mod.insert_terminal_run(conn, "bad1", "scheduled", "incremental",
                                "completed_with_errors", _now(), _now())
    health = client.get("/discovery/runs").context["health"]
    assert health["unhealthy_recent"] == 1
    assert health["latest_status"] == "completed_with_errors"


def test_the_runs_page_can_be_filtered_to_unhealthy_runs_only(client):
    ...  # GET /discovery/runs?status=unhealthy returns only the degraded rows
```

**Implement:** `discovery_runs_page(request, limit: int = 25, status: str | None = None)`;
slice `db_mod.list_runs(conn)` (a DB-level `LIMIT` in `list_runs` is P1's to add — noted, not
duplicated); compute `health = {"latest_status", "unhealthy_recent", "last_successful_at"}` over
the window with `UNHEALTHY = {"completed_with_errors", "failed", "abandoned"}`.

**Commit:** `feat(routes): cap, filter and summarise the discovery run history (B-43)`

---

### Group F — paths and hygiene (B-62, B-63, B-64)

#### - [ ] Task 33 — Windows reserved device names (B-62)

**Test** (`tests/test_discovery_paths.py`):

```python
@pytest.mark.parametrize("handle", ["con", "AUX", "@nul", "com1", "lpt9", "prn"])
def test_a_handle_slugging_to_a_windows_device_name_gets_a_disambiguator(handle):
    """B-62: \\w preserves con/aux/nul/prn/com1..lpt9, which cannot exist as
    directory names on Windows -- mkdir fails on every run and records a
    per-handle error with an opaque OS message."""
    slug = handle_slug(handle)
    assert slug not in WINDOWS_RESERVED
    assert slug.startswith(handle.lstrip("@").lower())


def test_two_all_punctuation_handles_no_longer_share_the_untitled_bucket():
    assert handle_slug("!!!") != handle_slug("???")


def test_the_frozen_mapping_for_existing_handles_is_unchanged():
    """The suffix must not repoint a directory that already holds captured
    content -- on_disk_ids() would return empty and the engine would re-download
    and re-pay for each account's whole back-catalogue."""
    assert handle_slug("adamgrant.bsky.social") == "adamgrantbskysocial"
    assert handle_slug("@Romayroh") == "romayroh"
```

**Implement:**

```python
WINDOWS_RESERVED = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}
)


def handle_slug(handle: str) -> str:
    slug = slugify(handle.lstrip("@"))
    if slug in WINDOWS_RESERVED or slug == "untitled":
        slug = f"{slug}-{hashlib.sha1(handle.encode('utf-8')).hexdigest()[:8]}"
    return slug
```

The audit's second half — *also* reject reserved names at registration — is deliberately **not**
implemented: disambiguating makes the handle work, so a 400 would refuse a registration that is
now perfectly serviceable. The two are alternatives; this is the better one. Record the choice
in the function's docstring.

**Commit:** `fix(paths): disambiguate Windows reserved device names and the untitled bucket (B-62)`

---

#### - [ ] Task 34 — One collision gate, and a durable detector for the paths that bypass it (B-63)

**Test:**

```python
def test_assert_no_slug_collision_is_the_single_enforcement_point(client, spawns):
    """B-63: find_slug_collision was called from exactly one place -- the web
    form. migrate_handles_from_manifest writes through upsert_handle_from_migration,
    which enforces only UNIQUE(platform, handle) and can introduce exactly the
    collision the route refuses."""
    with pytest.raises(SlugCollisionError) as excinfo:
        assert_no_slug_collision("john.doe.5", ["johndoe5"])
    assert "johndoe5" in str(excinfo.value)
    # the route's 400 message is produced from the same exception
    assert _add(client, "facebook", "johndoe5").status_code in (200, 303, 307)
    assert _add(client, "facebook", "john.doe.5").status_code == 400


def test_a_collision_introduced_by_the_migration_path_is_reported_durably(engine_conn, tmp_path):
    """The migration bypasses the route entirely, so the runtime detector is the
    compensating control -- and it printed to stderr, into the void of B-42."""
    db.upsert_handle_from_migration(engine_conn, "youtube", "john.doe.5", "A", "guru", None, now_iso())
    db.upsert_handle_from_migration(engine_conn, "youtube", "johndoe5", "B", "guru", None, now_iso())
    run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                  trigger="manual", mode="incremental")
    row = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.slug_collision'").fetchone()
    assert row is not None and row["severity"] == "warning"
```

**Implement:** `SlugCollisionError` + `assert_no_slug_collision(handle, existing)` in
`discovery_paths.py` (wrapping the existing `find_slug_collision`, carrying the full operator
message); the route raises/catches it. **Handoff, stated in the docstring:** P1's `db.py` and
P10's `migrate_handles_from_manifest.py` must call this same helper — P8 cannot reach either
file, so it closes the detection half durably (Task 12's event) and publishes the gate.

**Commit:** `refactor(paths): publish one collision gate and make the runtime detector durable (B-63)`

---

#### - [ ] Task 35 — Engine hygiene (B-64)

Four independent items, one commit each if they are easier that way.

**Test:**

```python
def test_the_engine_module_has_no_mid_file_imports():
    """B-64(1): import sqlite3/sys/threading and the pipeline_app imports sat at
    line 117, so importing the pure walk functions dragged in the DB layer."""
    tree = ast.parse(Path(discovery_engine.__file__).read_text(encoding="utf-8"))
    import_lines = [n.lineno for n in ast.walk(tree)
                    if isinstance(n, (ast.Import, ast.ImportFrom)) and n.col_offset == 0]
    first_def = min(n.lineno for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)))
    assert max(import_lines) < first_def


def test_peek_upload_date_has_a_real_signature():
    """B-64(2): (self, *args) type-checks nothing -- adapters can and do
    disagree on arity with no signal."""
    sig = inspect.signature(PlatformAdapter.peek_upload_date)
    assert list(sig.parameters) == ["self", "item_id"]


def test_run_discovery_normalizes_a_naive_now_to_aware_utc(engine_conn, tmp_path):
    """B-64(4): a naive `now` made make_run_id's %z render empty and made
    reclaim_stale_runs subtract a naive from an aware datetime -- an uncaught
    TypeError. No production caller passes it; the parameter is public."""
    naive = _dt.datetime(2026, 7, 30, 6, 0, 0)
    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                           trigger="manual", mode="incremental", now=naive)
    assert result["status"] == "completed"
    assert db.get_run(engine_conn, result["run_row_id"])["run_id"].endswith("+0000")


def test_every_tunable_is_reachable_from_the_command_line():
    """B-64(3): five module/default constants with no settings or CLI exposure,
    so tuning any of them was a code edit."""
    parser_flags = {a.dest for a in cron._build_parser()._actions}
    assert {"heartbeat_interval_s", "stale_after_s", "per_handle_deadline_s",
            "run_deadline_s", "new_handle_lookback_days"} <= parser_flags
```

**Implement:** hoist the imports to the top; `def peek_upload_date(self, item_id: str) -> str |
None: ...`; `now = (now or _dt.datetime.now(_dt.timezone.utc))` followed by
`if now.tzinfo is None: now = now.replace(tzinfo=_dt.timezone.utc)`; five new
`--*` flags on the cron parser threaded into `run_discovery`.

**Commit:** `refactor(engine): hoist imports, type the Protocol, expose tunables, normalize now (B-64)`

---

### Group G — inbound seams (P6 B-06, P7 B-01/B-21, P1 B-82, P0 F-64)

These close another package's finding. Each ships only after its owner's side has landed; each
is independently testable against a locally-defined stand-in for the owner's type, so P8 is not
blocked on merge order.

#### - [ ] Task 36 — A typed adapter error never marks a handle invalid (P6's B-06)

P6 is changing the native adapters so a failure **raises** and `[]` means only "the walk
completed and found nothing" — the two states stop sharing a return value. That invariant dies
at `discovery_engine.py:255` unless the validate path stops treating every exception as proof of
non-existence. Task 25 established the rule (`HandleNotFound` alone excludes); this task pins it
against P6's actual type and its sibling errors.

**Test** (`tests/test_discovery_engine.py`):

```python
@pytest.mark.parametrize("error_name", [
    "BlueskyFetchError", "YouTubeEnumerationError", "TranscriptFetchBlocked", "YtDlpUnavailable",
])
def test_a_typed_adapter_fetch_error_never_marks_a_handle_invalid(engine_conn, tmp_path, error_name):
    """P6's B-06 (S1): a valid handle added while the VPN was up was quietly and
    permanently removed from every future run. P6 makes the failure raise; this
    asserts P8 does not then convert the raise into 'invalid' + included=0. The
    error types are constructed locally by name so this test does not depend on
    P6's merge landing first."""
    Boom = type(error_name, (RuntimeError,), {})

    class RaisingAdapter(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter):
            raise Boom("transport failed")

    handle_id = db.create_handle(engine_conn, "bluesky", "adamgrant.bsky.social", "AG",
                                 "guru", None, now_iso())
    db.set_handle_status(engine_conn, handle_id, "validated")
    result = run_discovery(engine_conn, tmp_path, {"bluesky": RaisingAdapter({})},
                           trigger="manual", mode="validate_handle", handle_id=handle_id)
    row = db.get_handle(engine_conn, handle_id)
    assert result["status"] == "failed"        # the run reports the failure...
    assert row["status"] != "invalid"          # ...without condemning the handle
    assert row["included"] == 1


P6_ERROR_NAMES = ("BlueskyFetchError", "YouTubeEnumerationError",
                  "TranscriptFetchBlocked", "YtDlpUnavailable")


def test_the_local_stand_in_names_match_p6s_real_exported_errors():
    """The test above constructs P6's error types by NAME so P8 is not blocked
    on P6's merge order -- which means a rename on P6's side would leave this
    suite green against types that no longer exist, i.e. an except clause that
    silently never matches. Assert the names against the real modules the
    moment they are importable, so a rename is a failure rather than a
    disappearance."""
    from pipeline_app import discovery_bluesky, discovery_youtube
    exported = set(dir(discovery_bluesky)) | set(dir(discovery_youtube))
    missing = [name for name in P6_ERROR_NAMES if name not in exported]
    assert not missing, (
        f"P6 no longer exports {missing}; the parametrised stand-ins above are "
        f"testing types nothing raises. Update P6_ERROR_NAMES and EXCLUDING_ERRORS together."
    )
    for name in P6_ERROR_NAMES:
        error_type = getattr(discovery_bluesky, name, None) or getattr(discovery_youtube, name)
        assert issubclass(error_type, Exception)
        assert not issubclass(error_type, discovery_engine.EXCLUDING_ERRORS), (
            f"{name} is a transport failure, not proof the account is gone (B-06)")


def test_only_handle_not_found_survives_as_an_excluding_error(engine_conn, tmp_path):
    """The whitelist is the contract: if a future adapter error type is added and
    nobody updates this set, the default is 'retryable', never 'delete it from
    the roster'."""
    assert discovery_engine.EXCLUDING_ERRORS == (discovery_engine.HandleNotFound,)


def test_a_transient_validate_failure_names_the_error_type_in_its_event(engine_conn, tmp_path):
    ...  # discovery.validate_transient_failure detail["error_type"] == "BlueskyFetchError"
```

**Implement** in `discovery_engine.py` — make the whitelist explicit rather than implicit in an
`isinstance` call, so the "everything else is retryable" default is visible:

```python
EXCLUDING_ERRORS: tuple[type[BaseException], ...] = (HandleNotFound,)
"""The ONLY errors that mark a handle invalid and clear `included`.

Everything else -- BlueskyFetchError, YouTubeEnumerationError,
TranscriptFetchBlocked, YtDlpUnavailable, a socket timeout, a 503 -- is
transient by default and leaves the handle retryable (P6's B-06, S1). The
default direction matters: the damage in B-06 is a VALID handle silently
dropped from every future run, which nothing retries and nothing reports.
"""
```

The validate `except` branch becomes `if isinstance(exc, EXCLUDING_ERRORS): ...invalid...` and
otherwise records the transient event with `detail={"error_type": type(exc).__name__}`.

**Commit:** `fix(engine): a typed adapter fetch error leaves the handle retryable (P6 B-06)`

---

#### - [ ] Task 37 — Bright Data diagnostics become `events` rows (P7's B-01)

P7's `brightdata_job.drain_diagnostics()` returns records already shaped for
`obs.record_event`. Nothing calls it (P7 §7, residual 3).

**Test:**

```python
def test_brightdata_diagnostics_are_drained_into_event_rows(engine_conn, tmp_path, monkeypatch):
    """P7's B-01: the diagnostics sink is written on every Bright Data call and
    read by nobody, so a job that retried three times and truncated its results
    leaves no durable trace."""
    drained = [{"kind": "brightdata.truncated", "severity": "warning",
                "source": "discovery_instagram",
                "message": "instagram/@nasa returned exactly limit_per_input=10 items",
                "detail": {"platform": "instagram", "records": 10}}]
    monkeypatch.setattr(discovery_engine.brightdata_job, "drain_diagnostics",
                        lambda: drained.pop(0) if drained else [])
    db.create_handle(engine_conn, "instagram", "@nasa", "N", "guru", None, now_iso())
    run_discovery(engine_conn, tmp_path, {"instagram": SingleFakeAdapter({"@nasa": []})},
                  trigger="manual", mode="incremental")
    row = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'brightdata.truncated'").fetchone()
    assert row is not None and row["severity"] == "warning"
    assert json.loads(row["detail"])["records"] == 10


def test_the_sink_is_drained_even_when_the_handle_errored(engine_conn, tmp_path, monkeypatch):
    """The truncation/retry evidence matters MOST on the failing handle, so the
    drain lives in a finally, not on the success path."""
    ...


def test_a_diagnostics_drain_failure_never_aborts_the_run(engine_conn, tmp_path, monkeypatch):
    monkeypatch.setattr(discovery_engine.brightdata_job, "drain_diagnostics",
                        lambda: (_ for _ in ()).throw(RuntimeError("sink is broken")))
    ...  # run still reaches a terminal status
```

**Implement** in `discovery_engine.py`, in the per-handle `finally`:

```python
def _drain_adapter_diagnostics(conn, run_row_id: int) -> None:
    """P7 owns the sink; P8 owns the durable surface. Drained per handle, in a
    finally, so a handle that failed still yields its retry/truncation record --
    that is exactly when the evidence is worth having."""
    try:
        records = brightdata_job.drain_diagnostics()
    except Exception as exc:  # noqa: BLE001 - reporting must never take down the run
        obs.log("discovery.diagnostics_drain_failed", level="error",
                error=f"{type(exc).__name__}: {exc}")
        return
    for record in records:
        obs.record_event(conn, run_id=run_row_id, **record)
```

**Commit:** `feat(engine): drain Bright Data diagnostics into events rows (P7 B-01)`

---

#### - [ ] Task 38 — `preflight()` runs once per run, not once per handle (P7's B-21)

**Test:**

```python
def test_preflight_runs_once_per_run_not_once_per_handle(engine_conn, tmp_path):
    """P7's B-21: a missing credential failed N times, once per handle, with N
    identical unhelpful errors. One check, before the loop, one message."""
    calls = {"n": 0}
    class PreflightAdapter(SingleFakeAdapter):
        def preflight(self):
            calls["n"] += 1
            return None
    for handle in ("@a", "@b", "@c"):
        db.create_handle(engine_conn, "instagram", handle, handle, "guru", None, now_iso())
    run_discovery(engine_conn, tmp_path, {"instagram": PreflightAdapter({})},
                  trigger="manual", mode="incremental")
    assert calls["n"] == 1


def test_a_failed_preflight_skips_that_platform_and_reports_once(engine_conn, tmp_path):
    class Unconfigured(SingleFakeAdapter):
        def preflight(self):
            return "BRIGHTDATA_API_KEY is not set; instagram cannot run"
        def enumerate_newest_first(self, handle, keyword_filter):
            raise AssertionError("must not be reached when preflight failed")
    ...
    assert results[0]["status"] == "error"
    assert "BRIGHTDATA_API_KEY" in results[0]["error_message"]
    row = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.preflight_failed'").fetchone()
    assert row is not None and row["severity"] == "error"


def test_an_adapter_without_preflight_is_not_an_error(engine_conn, tmp_path):
    """preflight() is optional -- the native adapters have no credentials to
    check. getattr, not hasattr-then-call."""
    ...
```

**Implement** in `run_discovery`, before the handle loop: for each distinct platform among the
included handles, call `getattr(adapter, "preflight", None)`; a returned message is recorded
once as `discovery.preflight_failed` (severity `error`) and every handle on that platform is
recorded `error` with that message **without an adapter call** — a missing credential must not
buy N failed attempts.

**Commit:** `feat(engine): run each adapter's preflight once per run (P7 B-21)`

---

#### - [ ] Task 39 — A handle that keeps failing stops looking healthy (P1's B-82)

P1 ships `handles.consecutive_failures`, the `failing` status and
`db.record_handle_failure()` / `db.clear_handle_failures()`. Nothing increments the counter
until the engine calls them.

**Test:**

```python
def test_three_consecutive_failing_runs_downgrade_the_handle(engine_conn, tmp_path):
    """P1's B-82: set_handle_status was called only from the one-shot validate
    branch, so a handle that validated at registration and later died kept
    status='validated', included=1 forever while raising an error row on every
    single run. A permanently broken source was indistinguishable from a healthy
    one on the roster."""
    handle_id = db.create_handle(engine_conn, "youtube", "@dead", "D", "guru", None, now_iso())
    db.set_handle_status(engine_conn, handle_id, "validated")
    adapter = SingleFakeAdapter({}, fail_handles={"@dead"})
    for _ in range(3):
        run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual", mode="incremental")
    row = db.get_handle(engine_conn, handle_id)
    assert row["consecutive_failures"] == 3
    assert row["status"] == "failing"


def test_one_successful_run_clears_the_failure_counter(engine_conn, tmp_path):
    """The counter must be CONSECUTIVE, or a handle that fails once a month for
    a year is eventually condemned for being popular."""
    ...
    assert db.get_handle(engine_conn, handle_id)["consecutive_failures"] == 0
    assert db.get_handle(engine_conn, handle_id)["status"] == "validated"


def test_a_failing_handle_is_still_included_in_the_run(engine_conn, tmp_path):
    """'failing' is a signal, not an exclusion -- B-57's lesson. Only a
    definitive not-found removes a handle from the roster."""
    ...
    assert db.get_handle(engine_conn, handle_id)["included"] == 1


def test_a_skipped_handle_does_not_count_as_a_failure(engine_conn, tmp_path):
    """A backfill skip is 'this platform has no backfill path', not 'this handle
    is broken'. Counting it would condemn every Bright Data handle after three
    backfills."""
    ...
```

**Implement:** `db_mod.record_handle_failure(conn, handle_row["id"], now_iso=...)` in the
per-handle `error` branch; `db_mod.clear_handle_failures(conn, handle_row["id"])` on `ok` and
`no_new_content`; neither on `skipped`. Both calls are `getattr`-guarded for one release so P8
is not hard-blocked on P1's merge:

```python
        record_failure = getattr(db_mod, "record_handle_failure", None)
        if record_failure is not None:            # P1's B-82 column may not have landed yet
            record_failure(conn, handle_row["id"], now_iso=now_iso())
```

**Commit:** `feat(engine): count consecutive per-handle failures and downgrade the handle (P1 B-82)`

---

#### - [ ] Task 40 — `pipeline-app/scripts/` → `pipeline-app/tools/` (P0's F-64)

**Answer to P0: accepted.** Both directories are regular packages named `scripts`
(`__init__.py` verified present in each), which is the whole of F-64 — collecting the app suite
from the repo root shadows one with the other and raises `ModuleNotFoundError` on four modules
that are not broken. P0 de-packaging the root half leaves the name collision itself intact;
renaming is the fix.

**Target, chosen by the orchestrator: `pipeline-app/tools/`**, import path `tools.*`. P8
originally proposed `pipeline_app/scripts/` and **withdraws it** — `tools/` is strictly better
for two reasons P8 accepts:

1. **It preserves module depth.** `pipeline-app/tools/setup_discovery_task.py` keeps
   `parents[1] == pipeline-app`, exactly as today. P8's own objection to its proposal — that a
   changed depth makes the registered task point at a nonexistent script, registering cleanly
   and then failing forever and invisibly (B-40/B-42) — simply never arises here.
2. **These are operator entry points, not library code.** `pipeline_app/scripts/` would ship
   one-off migrations inside the installed package.

**`pipeline_app_root()` is kept regardless.** Replacing a bare `parents[N]` with a named,
tested function is right even when N does not change: it states the depth once, gives the test
something to assert, and makes the *next* move safe. The index is `1`, unchanged.

**Atomicity.** P10 has accepted, so the conditional is satisfied and the move is ON. P8's file
move, P10's six file updates, and the directory move are **one commit** — a half-moved
directory keeps both the package and the collision.

**Test** (`tests/test_setup_discovery_task.py`):

```python
from tools.setup_discovery_task import build_task_xml, main   # was: from scripts...


def test_the_app_no_longer_ships_a_package_named_scripts():
    """F-64: two importable packages both named `scripts` -- the repo root's and
    the app's -- so a bare pytest from the root shadows one with the other."""
    assert not (Path(pipeline_app.__file__).parents[1] / "scripts").exists()


def test_the_cron_script_path_survives_the_move():
    """A move that changes this module's depth would make pipeline_app_root()
    resolve one directory too deep, and the registered task would point at a
    file that is not there -- registering cleanly and failing forever,
    invisibly (B-40/B-42). tools/ keeps the depth; this test is what proves it
    rather than assuming it."""
    from tools import setup_discovery_task as sut
    assert sut.pipeline_app_root().name == "pipeline-app"
    assert (sut.pipeline_app_root() / "run_discovery_cron.py").exists()
```

**Run** the second test **before** moving the file — this ordering is kept. It passes at the
current depth and must still pass after the move; if it ever fails, the move changed the depth
and the registered task is pointing at nothing.

**Implement (one commit, with P10's changes):**
1. `git mv pipeline-app/scripts/setup_discovery_task.py pipeline-app/tools/setup_discovery_task.py`; `tools/__init__.py` (P10 moves its two modules in the same commit; the old `scripts/` directory, including its `__init__.py`, is gone when the commit lands).
2. Replace the inline `Path(__file__).resolve().parents[1]` with a named function:
   ```python
   def pipeline_app_root() -> Path:
       """The `pipeline-app/` directory, which holds run_discovery_cron.py.

       A function rather than an inline parents[1] so the depth is stated once
       and a test can assert it: get this wrong and setup registers a task
       against a path that does not exist, which succeeds and then fails
       silently forever. The F-64 move to tools/ deliberately preserved this
       depth (pipeline_app/scripts/ would not have).
       """
       return Path(__file__).resolve().parents[1]
   ```
3. Update the three `monkeypatch.setattr("scripts.setup_discovery_task.subprocess.run", ...)`
   targets (`tests/test_setup_discovery_task.py:25,40`, plus Task 10's) to
   `tools.setup_discovery_task.subprocess.run`.
4. Update the two usage lines in the module docstring (`:9-10`) to
   `python tools/setup_discovery_task.py`.

**Doc handoff to P14:** `README.md` / `CLAUDE.md` references to
`python scripts/setup_discovery_task.py` must follow. P8 cannot edit them.

**Commit:** `refactor: move pipeline-app/scripts to pipeline-app/tools (F-64)`

---

#### - [ ] Task 41 — The per-handle Bright Data cap seam, opt-in (P7's C1, operator-approved)

> **Plan amendment, P8 kickoff session.** The résumé brief for this session records that the
> operator approved P7's cost item C1 during the P7 session (`P7-brightdata.md` §6's amendment
> blockquote, and commit `55109b8`). Verified against the live plan text this session: C1 itself
> is the **per-platform** item-cap override (`BRIGHTDATA_MAX_ITEMS_<PLATFORM>`), which P7 already
> shipped (its T14/T15) — C1's approval did not by itself add a task anywhere. What C1's approval
> unlocks is P7's own residual #1 (§7): *"A true per-handle cap needs `handle_row` threaded into
> `enumerate_newest_first` — a `PlatformAdapter` protocol change in `discovery_engine.py` (P8)...
> the per-handle setting is P8's to add if the operator approves C1."* C1 is approved, so this
> residual is now in scope.
>
> **What is safe to build in this session, and what is not.** `PlatformAdapter` is declared in
> `discovery_engine.py`, which P8 owns. But grep against the live repo (this session) shows the
> three real adapter functions — `discovery_bluesky.enumerate_newest_first`,
> `discovery_youtube.enumerate_newest_first`, `discovery_instagram.enumerate_newest_first` — take
> exactly `(handle, keyword_filter[, ...])` with **no `**kwargs`**, and all three files belong to
> **P6/P7**, not P8. If the engine's call site started passing a new `handle_row=` keyword
> unconditionally, every one of those adapters would raise `TypeError: unexpected keyword
> argument` on the very next run — a P8 change silently breaking P6/P7-owned files, which is
> exactly the cross-package boundary this programme's per-package file ownership exists to
> prevent. A blind protocol-signature change is therefore **not** implemented here.
>
> **What this task ships instead:** the seam only — `discovery_engine.py` offers `handle_row` to
> an adapter's `enumerate_newest_first` **only when that adapter's own signature declares the
> parameter** (checked via `inspect.signature`, not `hasattr`/`try`/`except TypeError`, so a
> genuine `TypeError` raised *inside* an opted-in adapter is never mistaken for "this adapter
> hasn't opted in yet"). An adapter that has not been updated to accept `handle_row` is called
> exactly as it is today — zero behavior change for P6/P7's current adapters. Actually reading a
> per-handle cap value out of `handle_row` needs a DB column (P1's `schema.sql`, not shipped) and
> adapter-side cap logic (P6/P7's files) — both stay explicitly out of scope and are named as open
> handoffs below, not silently implied as "done" by this task's name.

**Test** (`tests/test_discovery_engine.py`):

```python
def test_an_adapter_that_declares_handle_row_receives_it(engine_conn, tmp_path):
    """C1 (operator-approved 2026-08-16, P7-brightdata.md Sec 6 / commit 55109b8):
    the true per-handle cap needs handle_row threaded into enumerate_newest_first.
    The adapters that would read it are P6/P7-owned files P8 cannot edit, so this
    only proves the engine offers the row to an adapter that opts in."""
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    received = {}

    class OptedInAdapter(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter, handle_row=None):
            received["handle_row"] = handle_row
            return []

    run_discovery(engine_conn, tmp_path, {"youtube": OptedInAdapter({})},
                  trigger="manual", mode="incremental")
    assert received["handle_row"] is not None
    assert received["handle_row"]["handle"] == "@a"


def test_an_adapter_that_has_not_opted_in_is_called_exactly_as_before(engine_conn, tmp_path):
    """Zero behavior change for discovery_bluesky/discovery_youtube/discovery_instagram
    until each is updated on its own package's side to declare the parameter."""
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    calls = []

    class LegacyAdapter(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter):
            calls.append((handle, keyword_filter))
            return []

    result = run_discovery(engine_conn, tmp_path, {"youtube": LegacyAdapter({})},
                           trigger="manual", mode="incremental")
    assert result["status"] == "completed"
    assert calls == [("@a", None)]


def test_the_seam_is_offered_at_every_enumerate_call_site(engine_conn, tmp_path):
    """process_handle, process_handle_backfill and process_handle_validate all
    call enumerate_newest_first -- the seam must not be wired into only one."""
    handle_id = db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    seen = []

    class OptedInAdapter(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter, handle_row=None):
            seen.append(handle_row["handle"] if handle_row else None)
            return []

    run_discovery(engine_conn, tmp_path, {"youtube": OptedInAdapter({})},
                  trigger="manual", mode="validate_handle", handle_id=handle_id)
    assert seen == ["@a"]


def test_a_real_typeerror_inside_an_opted_in_adapter_still_propagates(engine_conn, tmp_path):
    """Detection is by signature introspection, not by catching TypeError --
    a bug inside an adapter that HAS opted in must not be swallowed and
    misread as 'this adapter doesn't take handle_row'."""
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())

    class BuggyOptedInAdapter(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter, handle_row=None):
            raise TypeError("unrelated bug inside the adapter")

    result = run_discovery(engine_conn, tmp_path, {"youtube": BuggyOptedInAdapter({})},
                           trigger="manual", mode="incremental")
    row = db.list_run_handle_results(engine_conn, result["run_row_id"])[0]
    assert row["status"] == "error"
    assert "unrelated bug inside the adapter" in row["error_message"]
```

**Implement** in `discovery_engine.py`:

```python
def _call_enumerate(adapter: PlatformAdapter, handle: str, keyword_filter: str | None,
                    handle_row) -> list[dict]:
    """Calls adapter.enumerate_newest_first, passing handle_row only when the
    adapter's own signature declares it. The true per-handle Bright Data item
    cap (operator-approved cost item C1, P7-brightdata.md Sec 6) needs the row
    threaded through, but the adapters that would read it are P6/P7-owned
    files P8 cannot edit -- introspection (not hasattr/try-except) keeps every
    adapter that has not opted in working exactly as before, and never mistakes
    a real bug inside an opted-in adapter for "hasn't opted in"."""
    if "handle_row" in inspect.signature(adapter.enumerate_newest_first).parameters:
        return adapter.enumerate_newest_first(handle, keyword_filter, handle_row=handle_row)
    return adapter.enumerate_newest_first(handle, keyword_filter)
```

(`import inspect` alongside the module's other imports -- Task 35 hoists all of them to the top
in the same pass if it has not already run.) Update `PlatformAdapter`'s declared signature to
`def enumerate_newest_first(self, handle: str, keyword_filter: str | None, handle_row: dict |
None = None) -> list[dict]: ...` (documentation for type checkers only -- `PlatformAdapter` is
never used as a runtime `isinstance` check, so this is not a breaking change by itself). Replace
all three call sites (`process_handle`, `process_handle_backfill`, `process_handle_validate`)
with `_call_enumerate(adapter, handle, keyword_filter, handle_row)`.

**Open handoffs from this task, stated so they are not later assumed done:**
- **P1** — a per-handle cap override needs a `handles` column (e.g. `max_items_override`) to
  populate `handle_row` with; none exists today. Until it does, an opted-in adapter's
  `handle_row` carries only the columns `handle_row` already has (handle, keyword_filter, cohort,
  etc.) — no cap value.
- **P6/P7** — each adapter's own file must add `handle_row=None` to its
  `enumerate_newest_first` signature and read a cap override from it before this seam does
  anything observable end to end. P8 cannot make that edit; those files are not in P8's scope.

**Commit:** `feat(engine): offer handle_row to adapters that opt in, the per-handle cap seam (P7 C1)`

---

## 5. Finding → test map

Three-Test-Rule roles are given for every `failure_mode: silent` finding (24 of the 31). The
seven non-silent findings (B-45 loud; B-49, B-52, B-59, B-62, B-64, F-68 latent) get a single
behavioural test each.

| Finding | Fault test | Distinguishability test | Surfacing test |
|---|---|---|---|
| **B-40** | `test_a_run_with_errored_handles_exits_nonzero` | `test_a_broken_run_and_a_clean_run_do_not_share_an_exit_code` | `test_exit_code_contract` (17 rows) |
| **B-41** | `test_a_failed_send_exits_notify_failed` | `test_a_sent_and_an_unsent_email_do_not_share_an_exit_code` | `test_an_unsent_email_leaves_an_error_event` |
| **B-42** | `test_task_xml_redirects_stdout_and_stderr_to_a_log_file` | `test_a_wake_is_logged_before_the_database_is_touched` | `test_dry_run_tells_the_operator_where_the_log_will_be` |
| **B-43** | `test_the_runs_page_is_capped_and_does_not_grow_without_bound` | `test_the_runs_page_can_be_filtered_to_unhealthy_runs_only` | `test_the_runs_page_exposes_a_health_summary_of_the_recent_window` |
| **B-44** | `test_task_xml_runs_on_battery_and_catches_up_a_missed_start` | `test_task_xml_pins_the_logon_model_and_working_directory` | `test_apply_verifies_registration_with_a_query_before_reporting_success` |
| **B-45** | *(loud)* `test_dry_run_prints_a_command_that_survives_a_round_trip_through_the_shell_parser` | — | — |
| **B-46** | `test_apply_refuses_to_overwrite_an_existing_task_without_force` | `test_remove_deletes_the_task` | `test_apply_reports_failure_when_the_verifying_query_finds_nothing` |
| **B-47** | `test_is_due_rejects_an_unknown_timezone_as_a_schedule_config_error`, `test_settings_route_rejects_an_unknown_timezone` | `test_a_rejected_setting_is_not_persisted` | `test_a_stored_bad_timezone_exits_scheduler_wedged_not_a_traceback` |
| **B-48** | `test_a_timezone_change_cannot_fire_a_second_run_the_same_day` | `test_the_next_day_still_fires_after_the_minimum_interval` | `test_a_machine_that_was_off_for_two_days_records_a_gap_warning` |
| **B-49** | *(latent)* `test_the_scheduled_path_short_circuits_when_a_run_is_already_active` | — | `test_a_lost_lock_does_not_write_a_markdown_record` |
| **B-50** | `test_a_stale_heartbeat_does_not_reclaim_a_run_whose_owner_is_still_alive` | `test_a_stale_run_whose_owner_is_gone_is_still_reclaimed` | `test_a_refused_reclaim_leaves_a_warning_event`, `test_a_refused_finish_leaves_an_error_event` |
| **B-51** | `test_an_abandoned_record_reports_the_work_its_db_rows_prove` | *(record vs `discovery_run_handles` rows reconcile — same test's second assertion)* | `test_finish_run_cannot_resurrect_an_abandoned_run` |
| **B-52** | *(latent)* `test_a_stale_run_is_reclaimed_even_when_today_is_not_due` | — | `discovery.runs_reclaimed` event asserted in the same test |
| **B-53** | `test_a_handle_that_never_returns_is_recorded_as_an_error_and_the_run_finishes` | `test_a_run_that_blows_its_overall_deadline_ends_failed_not_running` | `discovery.run_deadline_exceeded` event, asserted in the same test |
| **B-54** | `test_a_handle_that_raises_after_two_downloads_records_two_not_zero` | *(2 ≠ 0: the recorded count differs from the pre-fix hardcoded 0)* | `test_a_partly_downloaded_handle_still_advances_last_seen` |
| **B-55** | `test_an_unknown_platform_error_message_names_the_exception_type` | `test_an_empty_str_exception_is_still_identifiable` | `test_the_full_traceback_reaches_the_event_detail` |
| **B-56** | `test_frontmatter_status_counts_always_sum_to_handles_processed` | `test_a_future_handle_status_cannot_silently_vanish_from_the_frontmatter` | `test_the_summary_sentence_mentions_skipped_handles` |
| **B-57** | `test_a_transient_validate_failure_leaves_the_handle_pending_and_included` | `test_a_definitive_not_found_does_exclude_the_handle` | `test_a_transient_validate_failure_leaves_a_warning_event` |
| **B-58** | `test_add_handle_rejects_a_platform_no_adapter_serves` | `test_the_adapter_registry_and_the_declared_platform_set_agree` | `test_a_rejected_platform_is_neither_stored_nor_spawned` |
| **B-59** | *(latent)* `test_run_now_refuses_to_spawn_while_a_run_is_active` | — | `test_a_lock_loss_retries_once_instead_of_re_raising` |
| **B-60** | `test_backfill_rejects_an_inverted_date_range` | `test_backfill_rejects_a_malformed_date`, `test_backfill_rejects_an_argv_like_value` | 400 body + `spawns == []`, asserted in each |
| **B-61** | `test_the_child_s_stdout_and_stderr_are_captured_to_a_file` | `test_the_runs_page_context_names_a_spawn_that_never_produced_a_run` | `test_a_spawn_is_recorded_with_its_pid_and_a_captured_output_path` |
| **B-62** | *(latent)* `test_a_handle_slugging_to_a_windows_device_name_gets_a_disambiguator` | — | `test_the_frozen_mapping_for_existing_handles_is_unchanged` |
| **B-63** | `test_assert_no_slug_collision_is_the_single_enforcement_point` | `test_a_directory_collision_leaves_an_event_naming_both_handles` | `test_a_collision_introduced_by_the_migration_path_is_reported_durably` |
| **B-64** | *(latent)* `test_the_engine_module_has_no_mid_file_imports`, `test_peek_upload_date_has_a_real_signature`, `test_run_discovery_normalizes_a_naive_now_to_aware_utc`, `test_every_tunable_is_reachable_from_the_command_line` | — | — |
| **D-01** | `test_a_failed_send_exits_notify_failed` | `test_a_sent_and_an_unsent_email_do_not_share_an_exit_code` | `test_an_unsent_email_leaves_an_error_event` |
| **D-02** | `test_task_xml_redirects_stdout_and_stderr_to_a_log_file` | `test_a_heartbeat_write_failure_leaves_an_event_not_only_a_print` | `test_a_directory_collision_leaves_an_event_naming_both_handles`, `test_a_backfill_skip_leaves_an_event` |
| **D-06** | `test_a_startup_failure_exits_startup_failed_and_is_not_confused_with_not_due` | *(same test's second half: wedged ≠ not-due)* | `test_a_wake_is_logged_before_the_database_is_touched` |
| **E-11** | `test_a_spawn_is_recorded_with_its_pid_and_a_captured_output_path` | `test_the_runs_page_context_names_a_spawn_that_never_produced_a_run` | same — `pending_spawns` in the route context |
| **F-16** | `test_exit_code_contract` (parametrised, 17 rows) | `test_exit_contract_covers_every_declared_exit_code` | `test_bad_cli_arguments_still_exit_two` |
| **F-68** | *(latent)* `test_a_discovery_post_without_the_spawn_stub_raises_instead_of_billing` | — | `test_every_spawn_site_goes_through_the_single_seam` |

### Inbound seam obligations (other packages' finding IDs)

| Finding | Owner | Fault test | Distinguishability test | Surfacing test |
|---|---|---|---|---|
| **B-06** | P6 | `test_a_typed_adapter_fetch_error_never_marks_a_handle_invalid` (×4 error types) | `test_only_handle_not_found_survives_as_an_excluding_error`, `test_the_local_stand_in_names_match_p6s_real_exported_errors` | `test_a_transient_validate_failure_names_the_error_type_in_its_event` |
| **B-01** | P7 | `test_brightdata_diagnostics_are_drained_into_event_rows` | `test_the_sink_is_drained_even_when_the_handle_errored` | same — the `events` row is the surface |
| **B-21** | P7 | `test_a_failed_preflight_skips_that_platform_and_reports_once` | `test_preflight_runs_once_per_run_not_once_per_handle` | `discovery.preflight_failed` event, asserted in the fault test |
| **B-73** | P1 | `test_a_bad_platform_is_rejected_before_the_storage_constraint_can_fire` | `test_the_declared_platform_set_matches_the_storage_constraint` | 400 body naming the valid set |
| **B-82** | P1 | `test_three_consecutive_failing_runs_downgrade_the_handle` | `test_one_successful_run_clears_the_failure_counter`, `test_a_skipped_handle_does_not_count_as_a_failure` | `handle.marked_failing` event (P1's) + `test_a_failing_handle_is_still_included_in_the_run` |
| **F-64** | P0 | *(latent)* `test_the_app_no_longer_ships_a_package_named_scripts` | — | `test_the_cron_script_path_survives_the_move` |

---

## 6. Tests deleted or inverted

### `pipeline-app/tests/test_run_discovery_cron.py` — the 12 `exit_code == 0` assertions

The audit cites them at `:24, 33, 42, 59, 74, 88, 101, 112, 124, 139, 151, 167`. Disposition,
one by one:

| Line | Test | Disposition | Replacement |
|---|---|---|---|
| `:24` | `test_scheduled_mode_skips_when_not_due` | **kept, retargeted** | `assert exit_code == cron.Exit.OK` — not-due is genuinely contract row 1. Asserting the literal `0` is asserting a value the function hard-codes; asserting the named constant asserts the contract. |
| `:33` | `test_scheduled_mode_runs_when_due` | **kept, retargeted** | `== cron.Exit.OK` (stub returns `completed`) |
| `:42` | `test_incremental_mode_always_runs` | **kept, retargeted** | `== cron.Exit.OK` |
| `:59` | `test_backfill_mode_passes_dates_through` | **kept, retargeted** | `== cron.Exit.OK` |
| `:74` | `test_validate_handle_mode_passes_handle_id_through` | **kept, retargeted** | `== cron.Exit.OK` |
| `:88` | `test_scheduled_due_run_calls_notify` | **rewritten** | Exit assertion retargeted to `Exit.OK`; `assert calls == [1]` **removed** — it asserts a mock was called. Replaced by `test_a_successful_send_leaves_no_error_event` asserting the system's effect (no `discovery.notify_failed` row) rather than the double's bookkeeping. |
| `:101` | `test_scheduled_locked_run_does_not_call_notify` | **inverted** | `assert exit_code == cron.Exit.LOCKED`. Renamed `test_a_locked_run_does_not_notify_and_exits_locked`. The `calls == []` assertion is **kept** — asserting a side-effectful call did *not* happen is a behaviour assertion, not a mock assertion. |
| `:112` | `test_scheduled_not_due_does_not_call_notify` | **kept, retargeted** | `== cron.Exit.OK` |
| `:124` | `test_incremental_mode_does_not_call_notify` | **kept, retargeted** | `== cron.Exit.OK` |
| `:139` | `test_backfill_mode_does_not_call_notify` | **kept, retargeted** | `== cron.Exit.OK` |
| `:151` | `test_validate_handle_mode_does_not_call_notify` | **kept, retargeted** | `== cron.Exit.OK` |
| `:167` | `test_notify_exception_does_not_propagate_or_change_exit_code` (whole function, `:155-168`) | **DELETED** | The test's name describes the defect and the test freezes it — the audit's own example of the anti-pattern. Replaced in Task 5 by `test_a_notify_exception_does_not_propagate_but_does_change_the_exit_code`, which keeps the true half (no propagation) and inverts the false half. |

**Net:** 1 test function deleted, 2 assertions inverted, 1 test rewritten to drop a mock
assertion, 8 assertions retargeted from a hard-coded literal to the contract constant. After
Task 8 the file contains a 17-row parametrised assertion of *non-zero* codes, against zero
today.

### `pipeline-app/tests/test_discovery_engine.py`

| Line | Test | Disposition | Replacement |
|---|---|---|---|
| `:391` | `test_run_discovery_second_concurrent_call_is_locked` — `assert locked_row["md_path"] is not None  # locked runs still get a paired record` | **inverted** | `assert ... is None`, plus `assert list((tmp_path/"output"/"discovery-runs").glob("*.md")) == []`. The comment states the B-49 defect as intent. (Task 17) |
| `:423-432` | `test_run_discovery_validate_handle_sets_invalid_and_excludes_on_empty_enumeration` | **inverted** | `test_an_empty_enumeration_is_not_treated_as_proof_of_non_existence` — asserts `included == 1`. An empty result is D-03's ambiguity, not proof. (Task 25) |
| `:435-445` | `test_run_discovery_validate_handle_sets_invalid_and_excludes_on_crash` | **inverted** | `test_a_transient_validate_failure_leaves_the_handle_pending_and_included`. The name pins B-57 exactly: "on crash" is the transient case. (Task 25) |
| `:406` | `..._reclaims_stale_run_and_writes_abandoned_record` — `assert stale_row["md_path"] is not None` | **extended** | keep, and add the B-51 assertions on the record's contents (Task 23) |
| `:553` | `test_backfill_skips_unsupported_platform_without_calling_adapter` — `assert result["status"] == "completed"` | **extended** | status stays `completed` (it is honest); add `assert result["counts"]["attempted"] == 0` and `["skipped"] == 1`, which is what makes the cron exit `NO_WORK` instead of `OK` (Tasks 2, 8) |
| `:298-301`, `:315`, `:328` | the three `capsys` collision assertions | **kept** | the prints stay per the adoption rule; Task 12 adds event assertions beside them |

### `pipeline-app/tests/test_setup_discovery_task.py`

| Line | Test | Disposition | Replacement |
|---|---|---|---|
| `:6-20` | `test_build_schtasks_command_shape` — asserts `/TR`, `/SC MINUTE`, `/MO 15` | **rewritten** | `/XML` registration replaces `/TR`; the shape assertions move to `test_task_xml_*` (Task 9). The old test asserts the exact structure D-02 and B-44 identify as the defect. |
| `:23-31` | `test_main_dry_run_does_not_execute` | **extended** | keep the "does not execute" half; add `test_dry_run_prints_a_command_that_survives_a_round_trip_through_the_shell_parser` (B-45) and the log-path assertion |
| `:34-44` | `test_main_apply_executes_schtasks` | **extended** | keep; add the `--force` refusal, the `/Query` verification and `--remove` (Task 10). Marked `@pytest.mark.allow_subprocess` under P0's guard. |
| `:3`, `:25`, `:40` | `from scripts.setup_discovery_task import ...` and the two `monkeypatch.setattr("scripts.setup_discovery_task.subprocess.run", ...)` targets | **retargeted** | `tools.setup_discovery_task` after Task 40's move (F-64). P10 has accepted, so these land in the same atomic commit as P10's six file updates. |

### `pipeline-app/tests/test_routes_discovery.py`

| Lines | Disposition | Replacement |
|---|---|---|
| `:35`, `:53-55`, `:128`, `:142`, `:155`, `:168`, `:179` — seven hand-rolled `subprocess.Popen` stubs | **replaced** | one module-level `spawns` fixture patching `routes.discovery._popen` (Task 26). Nine independent copy-pastes were the only guard against a live billed job; after this, forgetting the fixture trips P0's `subprocess.Popen` guard and the test **fails**. |

### `pipeline-app/tests/test_discovery_records.py`

| Lines | Disposition | Replacement |
|---|---|---|
| `:29-34` — counters asserted against a literal the test wrote | **extended** | kept green (the four legacy keys survive as aliases); Task 24 adds `test_frontmatter_status_counts_always_sum_to_handles_processed`, the contract-shaped assertion the suite lacked |

### `pipeline-app/tests/test_discovery_scheduling.py`

All five existing tests pass bare-date watermarks and stay green unchanged — Task 18's
`decode_watermark` accepts the legacy form deliberately, so an existing install does not re-fire
on its first upgraded wake.

---

## 7. Verification

The package is done when all of the following hold.

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app" && python -m pytest -q
```

1. `tests/test_run_discovery_cron.py` contains **zero** assertions of a bare literal `0` exit
   code and at least 17 parametrised assertions of contracted codes.
2. `grep -rn "does_not_propagate_or_change_exit_code" pipeline-app/tests/` returns nothing.
3. `grep -rn "subprocess.Popen" pipeline-app/pipeline_app/routes/discovery.py` returns exactly
   one line, inside `_popen`.
4. Programme-level check 6 passes: *a scheduled discovery run with an injected adapter fault
   exits non-zero and leaves an `events` row of severity `error`* — this is
   `test_exit_code_contract["every handle errored"]` plus
   `test_a_heartbeat_write_failure_leaves_an_event_not_only_a_print`.
5. Every S1 in this package (B-47, B-50, F-16, and F-68's guard) has a named test observed
   failing before its fix.
6. The exit-code table in §3 and `EXIT_REASON` agree — enforced by
   `test_exit_contract_covers_every_declared_exit_code`.
7. Every inbound seam obligation in §1 has a passing named test:
   `EXCLUDING_ERRORS == (HandleNotFound,)` (B-06), a `brightdata.*` `events` row (B-01), one
   `preflight()` call per run (B-21), route rejection ahead of the storage `CHECK` (B-73), and
   a `consecutive_failures` counter that moves (B-82).

### Sequencing note

Tasks 36-39 are written against locally-constructed stand-ins (a `type(name, (RuntimeError,),
{})` for P6's error types, a monkeypatched `drain_diagnostics`, a `getattr`-guarded
`record_handle_failure`), so **P8 is not blocked on P6/P7/P1 merge order**. The one cost of that
independence is that a rename on the owner's side could leave the stand-ins testing types
nothing raises — `test_the_local_stand_in_names_match_p6s_real_exported_errors` closes it by
asserting the four names against the real modules. Task 40 ships in **one commit** with P10's
six file updates and the directory move.

### Open handoffs (not blockers)

- **P1** — atomic `WHERE status='running'` inside `db.finish_run`; a `LIMIT` on `db.list_runs`;
  `assert_no_slug_collision` called from `db.upsert_handle_from_migration`. Received from P1:
  B-73's route half (Task 27) and B-82's call sites (Task 39).
- **P10** — `migrate_handles_from_manifest.py` must call `assert_no_slug_collision` and report
  rejected rows. **F-64:** P10 has accepted `pipeline-app/tools/`; P8's `setup_discovery_task.py`
  move goes in the same commit as P10's six file updates and the directory move.
- **P0** — F-64 answer is **accept**, target `pipeline-app/tools/` (Task 40). P8's route tests
  are written against the `subprocess.Popen` guard staying armed (Task 26's `_popen` seam),
  not around it.
- **P15** — render `health`, `pending_spawns`, and `.status-*` rules for
  `completed_with_errors` / `failed` / `abandoned` (B-43, E-11's UI halves); P1's
  `consecutive_failures` / `failing` counter on the handles page (B-82's UI half).
- **P14** — `README.md` / `CLAUDE.md` say `python scripts/setup_discovery_task.py`; after
  Task 40 that is `python tools/setup_discovery_task.py`.
- **P6** — raise `discovery_engine.HandleNotFound` for a definitive 404/"no such account", so
  B-57's auto-exclude fires for genuinely dead handles; until then nothing is auto-excluded,
  which is the safe direction. Received from P6: B-06's engine half (Task 36).
- **P7** — add socket timeouts so B-53's leaked worker thread has an upper bound. The per-handle
  item cap: C1 is operator-approved, and Task 41 ships the non-breaking opt-in seam
  (`_call_enumerate`, introspection-gated `handle_row`) in `discovery_engine.py`; P7 still owns
  wiring each adapter's own file to declare `handle_row=None` and read a cap override from it
  (no observable behavior until that lands — see Task 41's "open handoffs"). Received from P7:
  B-01's events half (Task 37) and B-21's call site (Task 38).
