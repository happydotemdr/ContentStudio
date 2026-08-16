# P7 — Bright Data adapters & shared job runner

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` or
> `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. The orchestration plan's
> **Global Constraints**, **test standard** and **Frozen interfaces**
> ([`../2026-08-08-audit-remediation.md`](../2026-08-08-audit-remediation.md)) are binding on
> every task here and are not restated.

**Wave:** B (parallel). Depends on P0 (conftest network/subprocess guard, CI) and P1
(`pipeline_app/obs.py`, `events` table) being merged first.

**Standing rule for this package: Bright Data is billed per record.** Every task below states
its billing consequence. No task in this plan adds a blind retry of a *billing* call. See
[§6 Cost note](#6-cost-note) — the operator approves or declines each item there before
execution starts.

**Standing rule #2: `brightdata_job.py` is the good example in this codebase.** Its module
docstring (`:6-10`) states the "empty ≠ failed" invariant and names the bug it already fixed;
`await_results` raises `BrightDataJobFailed`/`BrightDataJobTimeout` rather than returning `[]`.
This package **extends** that module. Any task that would let a failure return `[]` is wrong
and must be rejected in review.

---

## 1. Scope

### Files owned by P7 (no other package may touch these)

```
pipeline-app/pipeline_app/brightdata_job.py
pipeline-app/pipeline_app/discovery_instagram.py
pipeline-app/pipeline_app/discovery_linkedin.py
pipeline-app/pipeline_app/discovery_facebook.py
pipeline-app/pipeline_app/discovery_x.py
pipeline-app/tests/test_brightdata_job.py
pipeline-app/tests/test_discovery_instagram.py
pipeline-app/tests/test_discovery_instagram_sort.py
pipeline-app/tests/test_discovery_linkedin.py
pipeline-app/tests/test_discovery_facebook.py
pipeline-app/tests/test_discovery_x.py
```

### Finding IDs (14)

`B-01`, `B-02`, `B-03`, `B-18`, `B-19`, `B-20`, `B-21`, `B-22`, `B-23`, `B-24`, `B-25`,
`D-03`, `F-67`, `F-69`.

### Invariants this package must preserve

1. **"Empty ≠ failed."** A transport, vendor or timeout failure raises. `[]` means and only
   means "the job completed and there was genuinely nothing".
2. **LinkedIn stays two adapter instances.** `profile_adapter()` and `company_adapter()`
   each keep their own instance cache (`LinkedInAdapter._cache`) because a person and a
   company can share a URL slug and a handle-keyed shared cache would let one mode's paid
   batch serve the other's `download_item`. Do not collapse them into module globals.
3. **Frontmatter contract.** `fetched_at` mandatory (aware UTC,
   `isoformat(timespec="seconds")`); `url` strongly expected; metrics and `published`
   optional. No task here may make `fetched_at` conditional.
4. **`discovery_x.POLL_TIMEOUT_S = 600`, not 300.** The comment at `discovery_x.py:40-43`
   records the measurement (243 s at the production `limit_per_input`). Do not "make the
   constants consistent".

### Cross-package seams (named, not silently assumed)

| Seam | Who owns the other side | What P7 delivers |
|---|---|---|
| Diagnostics → `events` rows | P8 (`run_discovery_cron.py`, `discovery_engine.py`) | `brightdata_job.drain_diagnostics()` returns records shaped for `obs.record_event(conn, kind=…, severity=…, source=…, message=…, detail=…)`. P8 drains once per handle. |
| Preflight credential check | P8 (`run_discovery_cron.py`) / P3 (`preflight.py`) | `<adapter>.preflight()` returns `None` or one operator-facing message. P7 tests it directly; P8 calls it once before the handle loop. |
| Per-handle item cap | P8 (`discovery_engine.py`, `handles` table) | P7 delivers a **per-platform** env override. A true per-handle cap needs `handle_row` threaded into `enumerate_newest_first`, which is an engine signature change — out of scope here, recorded in §7. |
| `discovery_youtube.USER_AGENT` (part of B-25) | P6 | Out of P7's file list. P7 closes the two `REQUEST_TIMEOUT_S` re-exports; §7 records the remainder for P6. |
| conftest autouse guards (F-67 / F-69 repo-wide) | P0 | P7 adds the public reset/threading hooks the conftest needs **and** belt-and-braces module-local autouse fixtures in its own six test files, so P7's suite is order-independent whether or not P0's fixture is present. |

---

## 2. Finding → task map

Total coverage: all 14 IDs mapped.

| Finding | Severity | Failure mode | Task(s) |
|---|---|---|---|
| D-03 | S1 | silent | T1 |
| B-20 | S3 | loud | T2 |
| B-24 | S4 | latent | T3 |
| B-18 | S2 | loud | T4, T5 |
| B-01 | S2 | silent | T6, T21 |
| B-19 | S2 | loud | T7, T8, T9, T10, T11, T12 |
| B-21 | S3 | loud | T13 |
| B-03 | S4 | latent | T14, T15 |
| B-02 | **S1** | silent | T16, T17 |
| B-22 | S2 | silent | T18 |
| B-23 | S3 | latent | T19, T20 |
| B-25 | S4 | latent | T22 |
| F-67 | S2 | latent | T23, T24 |
| F-69 | S2 | latent | T25 |

---

## 3. Tasks

Every task is: **write the failing test → run it → see it fail for the right reason →
implement → see it pass → commit.** Run the app suite from its own directory:

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app" && python -m pytest tests/test_brightdata_job.py -q
```

**No test in this package may reach `api.brightdata.com`.** Every test either monkeypatches
`bd.requests.post` / `bd.requests.get`, or stubs the adapter's `_trigger_job` /
`_poll_job_status` / `_fetch_job_results` / `_run_collection_job`. P0's autouse guard raises
on any unstubbed `requests.*`; if a task's test trips it, the test is wrong, not the guard.
Retry and poll tests must also monkeypatch `bd.time.sleep` so no wall-clock time passes.

---

### T1 — Lock the "empty ≠ failed" invariant (D-03)

`brightdata_job` already honours the invariant; D-03 is that nothing *pins* it. Two of the
three Three-Test-Rule roles are missing: there is no test that a timeout never fetches, and
no test that the failed state is observably different from the genuinely-empty state.

- [ ] Add to `pipeline-app/tests/test_brightdata_job.py`:

```python
def test_await_results_raises_and_never_fetches_on_timeout(monkeypatch):
    """Fault test. A timeout must raise, not fall through to a fetch whose
    empty result the engine records as the healthy status 'no_new_content'."""
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    monkeypatch.setattr(bd.time, "monotonic", lambda: 10_000.0)

    def _fail_if_called(job_id):
        raise AssertionError("fetch must not run for a timed-out job")

    with pytest.raises(bd.BrightDataJobTimeout):
        bd.await_results(
            trigger_fn=lambda: "job1",
            poll_fn=lambda job_id: "running",
            fetch_fn=_fail_if_called,
            label="for someone", poll_timeout_s=0, poll_interval_s=5,
        )


def test_failed_job_is_distinguishable_from_a_genuinely_empty_one(monkeypatch):
    """Distinguishability test. The whole discipline is that these two
    outcomes must NOT look the same to the caller."""
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)

    empty = bd.await_results(
        trigger_fn=lambda: "job-empty",
        poll_fn=lambda job_id: "ready",
        fetch_fn=lambda job_id: [],
        label="for quiet-account", poll_timeout_s=300, poll_interval_s=5,
    )
    assert empty == []

    with pytest.raises(bd.BrightDataJobFailed):
        bd.await_results(
            trigger_fn=lambda: "job-failed",
            poll_fn=lambda job_id: "failed",
            fetch_fn=lambda job_id: [],
            label="for broken-account", poll_timeout_s=300, poll_interval_s=5,
        )
```

- [ ] Run: the timeout test **fails** today (the current implementation *does* skip the
      fetch, so confirm the assertion fires for the right reason by temporarily changing
      `raise BrightDataJobTimeout(...)` to `return fetch_fn(job_id)` in
      `brightdata_job.py:114`, observing the failure, then reverting). This is a
      characterization test: it fails against the mutation, which is the defect D-03
      describes in the two adapters that do not have this discipline.
- [ ] No production change. Extend the module docstring at `brightdata_job.py:6-10` with:
      `"The tests that pin this invariant are test_brightdata_job.py's *_never_fetches_* and
      *_distinguishable_* pair -- deleting them re-opens D-03."`
- [ ] `git commit -m "test(brightdata): pin the empty-not-failed invariant against mutation"`

---

### T2 — Typed response validation (B-20)

`response.json()["snapshot_id"]` and `["status"]` raise bare `KeyError`; `fetch_results`
returns an unvalidated payload, so a dict response makes every caller iterate key strings and
die inside `_normalize_row` with `AttributeError: 'str' object has no attribute 'get'`.

- [ ] Failing tests in `test_brightdata_job.py`:

```python
def test_trigger_names_the_endpoint_and_the_received_keys_on_a_bad_body(monkeypatch):
    monkeypatch.setattr(bd.requests, "post",
                        lambda *a, **k: _FakeResponse({"error": "bad token"}))
    with pytest.raises(bd.BrightDataResponseError) as exc:
        bd.trigger("https://api.example/v3", "gd_abc", {}, [{"url": "u"}], "k")
    assert "trigger" in str(exc.value)
    assert "snapshot_id" in str(exc.value)
    assert "error" in str(exc.value)          # the keys actually received


def test_fetch_results_rejects_a_dict_payload_instead_of_handing_it_on(monkeypatch):
    """A dict response used to reach _normalize_row, which iterated key
    STRINGS and died with AttributeError naming neither the endpoint nor the
    cause."""
    monkeypatch.setattr(bd.requests, "get",
                        lambda *a, **k: _FakeResponse({"error": "snapshot expired"}))
    with pytest.raises(bd.BrightDataResponseError, match="not a list of rows"):
        bd.fetch_results("https://api.example/v3", "job1", "k")
```

- [ ] Implement in `brightdata_job.py`:

```python
class BrightDataResponseError(Exception):
    """A Bright Data endpoint returned a body this client cannot use.

    Distinct from an HTTP error: the call succeeded, the shape did not. The
    message names the endpoint AND the keys actually received, which is the
    difference between a five-minute and a two-hour diagnosis across four
    platforms (B-20).
    """


def _shape_of(payload) -> str:
    if isinstance(payload, dict):
        return f"keys {sorted(payload)}"
    return type(payload).__name__


def _json_field(response, endpoint: str, field: str):
    try:
        payload = response.json()
    except ValueError as exc:
        raise BrightDataResponseError(
            f"{endpoint} returned a non-JSON body"
        ) from exc
    if not isinstance(payload, dict) or field not in payload:
        raise BrightDataResponseError(
            f"{endpoint} response has no '{field}' -- received {_shape_of(payload)}"
        )
    return payload[field]
```

- [ ] `trigger` returns `_json_field(response, "trigger", "snapshot_id")`;
      `poll_status` returns `_json_field(response, f"progress/{job_id}", "status")`;
      `fetch_results` becomes:

```python
    payload = response.json()
    if not isinstance(payload, list):
        raise BrightDataResponseError(
            f"snapshot/{job_id} returned {type(payload).__name__}, not a list of "
            f"rows -- received {_shape_of(payload)}"
        )
    return payload
```

- [ ] Re-export `BrightDataResponseError` from all four adapters beside the existing
      `BrightDataJobTimeout`/`BrightDataJobFailed` re-exports (`discovery_instagram.py:31-32`,
      `discovery_facebook.py:139-140`, `discovery_x.py:153-154`; LinkedIn has none today —
      add the three there for symmetry).
- [ ] `git commit -m "fix(brightdata): raise a typed error naming the endpoint and received keys"`

---

### T3 — One shared unprovisioned-dataset guard (B-24)

`discovery_instagram.DATASET_ID` is the real provisioned id, so
`DATASET_ID.startswith("gd_REPLACE")` at `:60-62` is dead. It is the only such guard among
the four and reads as an active safety check doing nothing.

- [ ] Failing test in `test_brightdata_job.py`:

```python
def test_trigger_refuses_an_unprovisioned_dataset_id_before_any_http_call(monkeypatch):
    """The guard must live where every adapter passes through, and must fire
    BEFORE requests.post -- an unprovisioned trigger that reached Bright Data
    would be a billed job against a nonexistent dataset."""
    def _fail_if_called(*a, **k):
        raise AssertionError("requests.post must not run for an unprovisioned dataset")

    monkeypatch.setattr(bd.requests, "post", _fail_if_called)
    for bad in ("gd_REPLACE_WITH_REAL_DATASET_ID", "", "   "):
        with pytest.raises(bd.BrightDataConfigError, match="not provisioned"):
            bd.trigger("https://api.example/v3", bad, {}, [{"url": "u"}], "k")
```

- [ ] Implement in `brightdata_job.py`, as the first statement of `trigger()`:

```python
class BrightDataConfigError(Exception):
    """An adapter is configured with a dataset id that cannot be collected."""


def _require_provisioned(dataset_id: str) -> None:
    """B-24: the Instagram adapter carried this check privately, where it was
    unreachable (its DATASET_ID has been real since 2026-08-06). Here it
    covers all four adapters and any future one, and it runs before the POST
    so an unprovisioned id can never start a billed job."""
    if not (dataset_id or "").strip() or dataset_id.startswith("gd_REPLACE"):
        raise BrightDataConfigError(
            f"Bright Data dataset id {dataset_id!r} is not provisioned -- set the "
            "real dataset id for this adapter before triggering a job"
        )
```

- [ ] Delete `discovery_instagram.py:60-65` (the private guard).
- [ ] **Delete** `pipeline-app/tests/test_discovery_instagram.py:147-154`
      (`test_trigger_job_raises_when_dataset_id_still_placeholder`) — it exercised dead code
      via a monkeypatch that no production path can produce. Replaced by the test above.
- [ ] Re-export `BrightDataConfigError` from the four adapters.
- [ ] `git commit -m "fix(brightdata): move the dataset-id guard where all four adapters hit it"`

---

### T4 — Bounded retry on `poll_status` (B-18, part 1)

`poll_status` calls `raise_for_status()` with no retry, so one 429/503 on any of up to 60
polls raises out to the engine's per-handle `except`. The handle records `error`/0 items even
though the job was already triggered, billed, and may well have completed.

**Billing:** polling a snapshot is not a billed record. Retrying a poll costs nothing and
*prevents* the loss of an already-billed job. `trigger` is deliberately excluded — see T5.

- [ ] Failing tests in `test_brightdata_job.py`:

```python
def _http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status}", response=response)


def test_poll_status_retries_a_transient_503_and_then_succeeds(monkeypatch):
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    attempts = iter([_http_error(503), _http_error(429), None])

    def fake_get(url, params=None, headers=None, timeout=None):
        failure = next(attempts)
        if failure is not None:
            raise failure
        return _FakeResponse({"status": "ready"})

    monkeypatch.setattr(bd.requests, "get", fake_get)
    assert bd.poll_status("https://api.example/v3", "job1", "k") == "ready"


def test_poll_status_does_not_retry_a_401(monkeypatch):
    """A bad token is not transient. Retrying it wastes four round-trips and
    delays the one message the operator needs."""
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(url)
        raise _http_error(401)

    monkeypatch.setattr(bd.requests, "get", fake_get)
    with pytest.raises(requests.HTTPError):
        bd.poll_status("https://api.example/v3", "job1", "k")
    assert len(calls) == 1


def test_poll_status_raises_after_the_retry_budget_is_exhausted(monkeypatch):
    """The raise-on-exhaustion contract stays intact: a genuine outage still
    surfaces as a per-handle error, it is not swallowed into a default."""
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    monkeypatch.setattr(bd.requests, "get",
                        lambda *a, **k: (_ for _ in ()).throw(_http_error(503)))
    with pytest.raises(requests.HTTPError):
        bd.poll_status("https://api.example/v3", "job1", "k")
```

- [ ] Implement in `brightdata_job.py`:

```python
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 4
RETRY_BASE_S = 2.0


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    response = getattr(exc, "response", None)
    return response is not None and response.status_code in RETRY_STATUSES


def _with_retry(call, *, what: str):
    """Bounded retry with backoff for a NON-BILLING call.

    B-18: a single transient 429/503 on one of up to 60 polls used to abandon
    a collection job that was already triggered and billed. Polling and
    fetching a snapshot cost nothing, so retrying them is free insurance.
    trigger() is deliberately NOT wrapped -- see the comment there.
    On exhaustion the original exception propagates, so a genuine failure
    still reaches the engine's per-handle error path.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 - re-raised below unless transient
            if attempt == MAX_ATTEMPTS or not _is_transient(exc):
                raise
            time.sleep(RETRY_BASE_S * (2 ** (attempt - 1)))
```

- [ ] Wrap the body of `poll_status` in `_with_retry(lambda: ..., what=f"progress/{job_id}")`.
- [ ] `git commit -m "fix(brightdata): retry transient poll failures instead of losing a billed job"`

---

### T5 — Retry `fetch_results`; document why `trigger` is not retried (B-18, part 2)

- [ ] Failing tests:

```python
def test_fetch_results_retries_a_transient_connection_error(monkeypatch):
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    attempts = iter([requests.ConnectionError("reset by peer"), None])

    def fake_get(url, params=None, headers=None, timeout=None):
        failure = next(attempts)
        if failure is not None:
            raise failure
        return _FakeResponse([{"id": "1"}])

    monkeypatch.setattr(bd.requests, "get", fake_get)
    assert bd.fetch_results("https://api.example/v3", "job1", "k") == [{"id": "1"}]


def test_trigger_is_never_retried_because_a_retried_trigger_double_bills(monkeypatch):
    """Bright Data bills per record. A trigger whose response was lost may
    have started a job anyway; retrying it starts -- and pays for -- a second
    one. This is the one call in the module that must fail fast."""
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    calls = []

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        calls.append(url)
        raise _http_error(503)

    monkeypatch.setattr(bd.requests, "post", fake_post)
    with pytest.raises(requests.HTTPError):
        bd.trigger("https://api.example/v3", "gd_abc", {}, [{"url": "u"}], "k")
    assert len(calls) == 1, "trigger must be attempted exactly once"
```

- [ ] Wrap `fetch_results`' request in `_with_retry(..., what=f"snapshot/{job_id}")`.
- [ ] Add above the `requests.post` in `trigger()`:

```python
    # NOT wrapped in _with_retry. Bright Data bills per record: a trigger whose
    # response is lost in transit may have started a job on the vendor side, so
    # a retry can create -- and pay for -- a second collection of the same
    # posts. Poll and fetch are free and are retried; this one is not (B-18).
```

- [ ] `git commit -m "fix(brightdata): retry snapshot fetch, never the billing trigger"`

---

### T6 — Structured, durable adapter diagnostics (B-01, core)

Every "billed and captured nothing", "N rows dropped" and "no cookies" signal in the adapters
is stderr-only. The registered Scheduled Task command has no redirection, so on the production
path those warnings have no destination at all.

Adapters have no db connection and no `run_id`, so they cannot call `obs.record_event`
directly. They get a sink that (a) writes through P1's `obs.log` — stderr **and**
`pipeline-app/logs/app-YYYY-MM-DD.log`, which survives Task Scheduler destroying the console —
and (b) buffers a record P8's run loop drains into the `events` table.

- [ ] Failing tests in `test_brightdata_job.py`:

```python
def test_record_diagnostic_buffers_a_record_shaped_for_the_events_table():
    bd.drain_diagnostics()
    bd.record_diagnostic(kind="adapter.billed_nothing", severity="error",
                         source="discovery_facebook", message="NASA captured nothing",
                         detail={"platform": "facebook", "handle": "NASA"})
    drained = bd.drain_diagnostics()
    assert len(drained) == 1
    record = drained[0]
    assert record["kind"] == "adapter.billed_nothing"
    assert record["severity"] == "error"
    assert record["source"] == "discovery_facebook"
    assert record["detail"]["handle"] == "NASA"
    # obs.record_event's severity vocabulary -- a record P8 cannot write is useless.
    assert record["severity"] in {"info", "warning", "error", "critical"}


def test_drain_diagnostics_empties_the_buffer_so_a_second_handle_sees_only_its_own():
    bd.drain_diagnostics()
    bd.record_diagnostic(kind="k", severity="warning", source="s", message="m")
    assert len(bd.drain_diagnostics()) == 1
    assert bd.drain_diagnostics() == []


def test_record_diagnostic_writes_through_to_obs_log(monkeypatch):
    """Surfacing. The event row is P8's half; the log FILE is this package's,
    and it is the surface that exists whether or not a run row does."""
    emitted = []
    monkeypatch.setattr(bd.obs, "log",
                        lambda event, **fields: emitted.append((event, fields)))
    bd.record_diagnostic(kind="adapter.billed_nothing", severity="error",
                         source="discovery_x", message="CNN captured nothing",
                         detail={"handle": "CNN"})
    assert emitted == [("adapter.billed_nothing",
                        {"level": "error", "source": "discovery_x",
                         "message": "CNN captured nothing", "handle": "CNN"})]


def test_record_diagnostic_never_masks_the_thing_it_is_reporting(monkeypatch):
    """A broken logger must not turn a reportable degradation into a crash."""
    def _boom(*a, **k):
        raise OSError("log directory is read-only")

    monkeypatch.setattr(bd.obs, "log", _boom)
    bd.record_diagnostic(kind="k", severity="error", source="s", message="m")
    assert bd.drain_diagnostics()[0]["kind"] == "k"
```

The third test asserts the *payload the system produced*, not that a mock was called — the
anti-tautology rule forbids `assert mock.called`, not asserting on emitted data.

- [ ] Implement in `brightdata_job.py`:

```python
from pipeline_app import obs

_DIAGNOSTICS: list[dict] = []


def record_diagnostic(*, kind: str, severity: str, source: str, message: str,
                      detail: dict | None = None) -> dict:
    """One structured, durable adapter diagnostic (B-01).

    Writes through to obs.log -- stderr AND the dated log file, which is the
    surface the scheduled task lacks entirely today -- and buffers a record
    for drain_diagnostics(). Never raises: a failure to report must not mask
    the degradation being reported.
    """
    record = {"kind": kind, "severity": severity, "source": source,
              "message": message, "detail": dict(detail or {})}
    _DIAGNOSTICS.append(record)
    try:
        obs.log(kind, level=severity, source=source, message=message, **record["detail"])
    except Exception:  # noqa: BLE001 - see the docstring; never widened
        pass
    return record


def drain_diagnostics() -> list[dict]:
    """Take and clear the buffered diagnostics.

    P8's run loop calls this once per handle and writes each record with
    obs.record_event(conn, run_id=..., **record). Draining rather than
    accumulating keeps one handle's diagnostics off another handle's row.
    """
    drained = list(_DIAGNOSTICS)
    _DIAGNOSTICS.clear()
    return drained
```

- [ ] `git commit -m "feat(brightdata): structured diagnostics that reach a durable surface"`

---

### T7 — Machine-readable failure detail (B-19, part 1)

The only trace of a timed-out `job_id` is inside an exception *message*, which reaches
`discovery_run_handles.error_message` as free text. Nothing can recover a snapshot from a
string.

- [ ] Failing test:

```python
def test_timeout_exception_carries_the_snapshot_id_as_data_not_only_prose(monkeypatch):
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    monkeypatch.setattr(bd.time, "monotonic", lambda: 10_000.0)
    with pytest.raises(bd.BrightDataJobTimeout) as exc:
        bd.await_results(trigger_fn=lambda: "snap-abc",
                         poll_fn=lambda job_id: "running",
                         fetch_fn=lambda job_id: [],
                         label="for x/CNN", poll_timeout_s=0, poll_interval_s=5)
    assert exc.value.snapshot_id == "snap-abc"
    assert exc.value.label == "for x/CNN"
    assert exc.value.poll_timeout_s == 0
```

- [ ] Implement:

```python
class _BrightDataJobError(Exception):
    """Base for job-level failures. Carries the snapshot id as an ATTRIBUTE,
    not only inside the message: a snapshot the operator paid for must be
    recoverable by code, not by reading prose out of error_message (B-19)."""

    def __init__(self, message: str, *, snapshot_id: str | None = None,
                 label: str = "", poll_timeout_s: float | None = None):
        super().__init__(message)
        self.snapshot_id = snapshot_id
        self.label = label
        self.poll_timeout_s = poll_timeout_s


class BrightDataJobTimeout(_BrightDataJobError):
    """A Bright Data collection job did not reach 'ready' within the deadline."""


class BrightDataJobFailed(_BrightDataJobError):
    """A Bright Data collection job reported status 'failed'."""
```

- [ ] Pass the attributes at both raise sites in `await_results`.
- [ ] `git commit -m "fix(brightdata): carry the snapshot id as data on job failures"`

---

### T8 — Persist an abandoned snapshot (B-19, part 2)

On timeout the loop raises without ever calling `fetch_fn`, so a snapshot that becomes ready
one second later is abandoned with its records paid for and uncollected.

- [ ] Failing tests:

```python
def test_timeout_persists_the_snapshot_for_a_later_free_fetch(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "PENDING_STORE_PATH", tmp_path / "pending.json")
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    monkeypatch.setattr(bd.time, "monotonic", lambda: 10_000.0)
    with pytest.raises(bd.BrightDataJobTimeout):
        bd.await_results(trigger_fn=lambda: "snap-abc",
                         poll_fn=lambda job_id: "running",
                         fetch_fn=lambda job_id: [],
                         label="for x/CNN", poll_timeout_s=0, poll_interval_s=5,
                         pending_key="x/CNN")
    assert bd.load_pending("x/CNN")["snapshot_id"] == "snap-abc"


def test_a_failed_job_is_not_persisted_because_there_is_nothing_to_recover(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "PENDING_STORE_PATH", tmp_path / "pending.json")
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    with pytest.raises(bd.BrightDataJobFailed):
        bd.await_results(trigger_fn=lambda: "snap-dead",
                         poll_fn=lambda job_id: "failed",
                         fetch_fn=lambda job_id: [],
                         label="for x/CNN", poll_timeout_s=300, poll_interval_s=5,
                         pending_key="x/CNN")
    assert bd.load_pending("x/CNN") is None


def test_pending_store_survives_a_corrupt_file(monkeypatch, tmp_path):
    """The store is a recovery aid, never a dependency: a truncated write from
    a killed process must not take the next run down with it."""
    store = tmp_path / "pending.json"
    store.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(bd, "PENDING_STORE_PATH", store)
    assert bd.load_pending("x/CNN") is None
    bd.record_pending("x/CNN", "snap-1")
    assert bd.load_pending("x/CNN")["snapshot_id"] == "snap-1"
```

- [ ] Implement (`import datetime as _dt`, `import json` at module top):

```python
PENDING_STORE_PATH = Path(__file__).resolve().parent.parent / "logs" / "brightdata-pending.json"
PENDING_MAX_AGE_H = 48


def _read_store() -> dict:
    try:
        payload = json.loads(PENDING_STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_store(payload: dict) -> None:
    # Write-temp-then-rename, same as every adapter's download_item: a killed
    # process must never leave a half-written store that reads as valid.
    PENDING_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PENDING_STORE_PATH.with_name(PENDING_STORE_PATH.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(PENDING_STORE_PATH)


def record_pending(key: str, snapshot_id: str) -> None:
    """Remember a snapshot that was paid for and not collected (B-19)."""
    store = _read_store()
    store[key] = {
        "snapshot_id": snapshot_id,
        "recorded_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    }
    _write_store(store)


def load_pending(key: str) -> dict | None:
    """The pending entry for this platform/handle, or None if absent or older
    than PENDING_MAX_AGE_H (Bright Data snapshots do not live forever, and a
    stale entry would cost one wasted poll every run)."""
    entry = _read_store().get(key)
    if not entry:
        return None
    try:
        recorded = _dt.datetime.fromisoformat(entry["recorded_at"])
    except (KeyError, TypeError, ValueError):
        return None
    age_h = (_dt.datetime.now(_dt.timezone.utc) - recorded).total_seconds() / 3600
    return None if age_h > PENDING_MAX_AGE_H else entry


def clear_pending(key: str) -> None:
    store = _read_store()
    if store.pop(key, None) is not None:
        _write_store(store)
```

- [ ] `await_results` gains `pending_key: str | None = None`; the timeout branch calls
      `record_pending(pending_key, job_id)` (guarded by `if pending_key`) and
      `record_diagnostic(kind="brightdata.snapshot_abandoned", severity="error", ...)`
      naming the snapshot id, before raising. The `failed` branch does **not** persist —
      a failed job has no data to recover.
- [ ] `git commit -m "fix(brightdata): persist a timed-out snapshot instead of losing paid data"`

---

### T9 — `resume_pending`, the free re-fetch entry point (B-19, part 3)

- [ ] Failing tests:

```python
def test_resume_pending_collects_a_ready_snapshot_without_triggering_anything(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "PENDING_STORE_PATH", tmp_path / "pending.json")
    bd.record_pending("x/CNN", "snap-abc")
    rows = bd.resume_pending("x/CNN",
                             poll_fn=lambda job_id: "ready",
                             fetch_fn=lambda job_id: [{"id": "1"}])
    assert rows == [{"id": "1"}]
    assert bd.load_pending("x/CNN") is None      # collected, so no longer pending


def test_resume_pending_returns_none_and_keeps_the_entry_while_still_running(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "PENDING_STORE_PATH", tmp_path / "pending.json")
    bd.record_pending("x/CNN", "snap-abc")
    assert bd.resume_pending("x/CNN",
                             poll_fn=lambda job_id: "running",
                             fetch_fn=lambda job_id: [{"id": "1"}]) is None
    assert bd.load_pending("x/CNN")["snapshot_id"] == "snap-abc"


def test_resume_pending_drops_a_failed_snapshot_and_says_so(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "PENDING_STORE_PATH", tmp_path / "pending.json")
    bd.record_pending("x/CNN", "snap-dead")
    bd.drain_diagnostics()
    assert bd.resume_pending("x/CNN",
                             poll_fn=lambda job_id: "failed",
                             fetch_fn=lambda job_id: []) is None
    assert bd.load_pending("x/CNN") is None
    assert [d["kind"] for d in bd.drain_diagnostics()] == ["brightdata.resume_failed"]


def test_resume_pending_is_a_no_op_when_nothing_is_pending(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "PENDING_STORE_PATH", tmp_path / "pending.json")

    def _fail_if_called(job_id):
        raise AssertionError("the happy path must not poll anything")

    assert bd.resume_pending("x/CNN", poll_fn=_fail_if_called,
                             fetch_fn=_fail_if_called) is None
```

- [ ] Implement:

```python
def resume_pending(key: str, poll_fn, fetch_fn) -> list[dict] | None:
    """One free attempt to collect a snapshot a previous run paid for and
    abandoned (B-19).

    Returns the rows if the snapshot is now ready, None otherwise. NEVER
    triggers a new job: the whole point is that this data is already bought.
    A poll error is swallowed into None -- deliberately, because this is a
    best-effort recovery running before the real job, and failing here must
    not fail a run that is otherwise fine. That is the ONE place in this
    module where an error becomes None, and it is why it is loud in the
    diagnostics buffer.
    """
    entry = load_pending(key)
    if not entry:
        return None
    snapshot_id = entry["snapshot_id"]
    try:
        status = poll_fn(snapshot_id)
    except Exception as exc:  # noqa: BLE001 - see the docstring
        record_diagnostic(kind="brightdata.resume_poll_failed", severity="warning",
                          source="brightdata_job",
                          message=f"could not poll abandoned snapshot {snapshot_id}: {exc}",
                          detail={"key": key, "snapshot_id": snapshot_id})
        return None
    if status == "ready":
        rows = fetch_fn(snapshot_id)
        clear_pending(key)
        record_diagnostic(kind="brightdata.resumed", severity="warning",
                          source="brightdata_job",
                          message=(f"recovered {len(rows)} row(s) from snapshot "
                                   f"{snapshot_id}, abandoned by an earlier run"),
                          detail={"key": key, "snapshot_id": snapshot_id, "rows": len(rows)})
        return rows
    if status == "failed":
        clear_pending(key)
        record_diagnostic(kind="brightdata.resume_failed", severity="error",
                          source="brightdata_job",
                          message=(f"abandoned snapshot {snapshot_id} reported 'failed'; "
                                   f"its records are lost"),
                          detail={"key": key, "snapshot_id": snapshot_id})
    return None
```

- [ ] `git commit -m "feat(brightdata): free re-fetch path for an abandoned snapshot"`

---

### T10 — Wire resume into Instagram (B-19, part 4)

- [ ] Failing test in `test_discovery_instagram.py`:

```python
def test_run_collection_job_prefers_a_pending_snapshot_over_a_new_billed_job(monkeypatch, tmp_path):
    """Bright Data bills per record. If the previous run paid for a snapshot
    and timed out before collecting it, this run must take that data rather
    than pay again."""
    monkeypatch.setattr(brightdata_job, "PENDING_STORE_PATH", tmp_path / "pending.json")
    brightdata_job.record_pending("instagram/somehandle", "snap-abc")
    _fake_key(monkeypatch)

    def _fail_if_called(handle, key):
        raise AssertionError("must not trigger a new job while a snapshot is pending")

    monkeypatch.setattr(ig, "_trigger_job", _fail_if_called)
    monkeypatch.setattr(ig, "_poll_job_status", lambda job_id, key: "ready")
    monkeypatch.setattr(ig, "_fetch_job_results", lambda job_id, key: [{"post_id": "p1"}])
    assert ig._run_collection_job("somehandle") == [{"post_id": "p1"}]
```

- [ ] Implement in `discovery_instagram._run_collection_job`, after the key check:

```python
    pending_key = f"instagram/{handle}"
    # Free recovery before any billed call: a snapshot an earlier run paid for
    # and abandoned on timeout (B-19). None means "nothing pending", which is
    # the ordinary case.
    resumed = brightdata_job.resume_pending(
        pending_key,
        poll_fn=lambda job_id: _poll_job_status(job_id, key),
        fetch_fn=lambda job_id: _fetch_job_results(job_id, key),
    )
    if resumed is not None:
        return resumed
```

and pass `pending_key=pending_key` to `await_results`.

- [ ] `git commit -m "fix(instagram): collect an abandoned snapshot before paying for a new one"`

---

### T11 — Wire resume into LinkedIn, Facebook and X (B-19, part 5)

Same shape, three files. Keys: `f"{self.platform}/{handle}"` for LinkedIn (so
`linkedin-profile/acme` and `linkedin-company/acme` never share an entry — invariant 2),
`f"{PLATFORM}/{handle}"` for Facebook and X.

- [ ] Failing test per file, mirroring T10's, plus one LinkedIn-specific test:

```python
def test_profile_and_company_pending_snapshots_never_collide(monkeypatch, tmp_path):
    """A person and a company can share a slug. One pending entry must not
    serve the other mode -- the same reason the two adapters keep separate
    caches."""
    monkeypatch.setattr(brightdata_job, "PENDING_STORE_PATH", tmp_path / "pending.json")
    brightdata_job.record_pending("linkedin-profile/acme", "snap-person")
    person, company = li.profile_adapter(), li.company_adapter()
    monkeypatch.setattr(person, "api_key", lambda: "k")
    monkeypatch.setattr(company, "api_key", lambda: "k")
    monkeypatch.setattr(person, "_poll_job_status", lambda job_id, key: "ready")
    monkeypatch.setattr(person, "_fetch_job_results", lambda job_id, key: [{"id": "c1"}])

    def _fail_if_called(*a, **k):
        raise AssertionError("company mode must not see the profile snapshot")

    monkeypatch.setattr(company, "_poll_job_status", _fail_if_called)
    monkeypatch.setattr(company, "_trigger_job", lambda handle, key: "fresh")
    monkeypatch.setattr(company, "_fetch_job_results", lambda job_id, key: [])
    assert person._run_collection_job("acme") == [{"id": "c1"}]
```

- [ ] Implement in all three.
- [ ] `git commit -m "fix(brightdata): wire snapshot recovery into linkedin, facebook and x"`

---

### T12 — Snapshot cleanup, opt-in and never on a timeout (B-19, part 6)

Nothing in the module ever deletes a snapshot; timed-out, failed and fetched snapshots
accumulate indefinitely on Bright Data's side.

- [ ] Failing tests:

```python
def test_delete_snapshot_is_off_by_default(monkeypatch):
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)

    def _fail_if_called(*a, **k):
        raise AssertionError("no delete request may be made unless opted in")

    monkeypatch.setattr(bd.requests, "delete", _fail_if_called)
    assert bd.await_results(trigger_fn=lambda: "j", poll_fn=lambda i: "ready",
                            fetch_fn=lambda i: [{"id": "1"}], label="l",
                            poll_timeout_s=300, poll_interval_s=5) == [{"id": "1"}]


def test_delete_after_fetch_only_runs_once_the_rows_are_in_hand(monkeypatch):
    """Deleting a snapshot destroys paid data. It may only happen AFTER a
    successful fetch -- never on the timeout path, where the snapshot is the
    only copy of what was bought."""
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    monkeypatch.setattr(bd.time, "monotonic", lambda: 10_000.0)
    monkeypatch.setattr(bd, "DELETE_AFTER_FETCH", True)
    deleted = []
    monkeypatch.setattr(bd, "delete_snapshot",
                        lambda api_base, job_id, key: deleted.append(job_id))
    with pytest.raises(bd.BrightDataJobTimeout):
        bd.await_results(trigger_fn=lambda: "snap-timeout", poll_fn=lambda i: "running",
                         fetch_fn=lambda i: [], label="l",
                         poll_timeout_s=0, poll_interval_s=5)
    assert deleted == []
```

- [ ] Implement `delete_snapshot(api_base, job_id, key)` (a `requests.delete` on
      `{api_base}/snapshot/{job_id}` wrapped in `_with_retry`) plus
      `DELETE_AFTER_FETCH = False` and an optional `cleanup_fn` argument to `await_results`
      invoked only in the `ready` branch, after `fetch_fn` returns. Comment:

```python
# Default OFF. Deleting a snapshot is free but irreversible: run it only once
# the operator is satisfied the fetched rows reached disk. It is NEVER called
# on the timeout path -- that snapshot is the only copy of data already paid
# for, and T8/T9 exist to recover it.
DELETE_AFTER_FETCH = False
```

- [ ] `git commit -m "feat(brightdata): opt-in snapshot cleanup, never on the timeout path"`

---

### T13 — Preflight credential check (B-21)

The credential check lives inside `_run_collection_job`, so an unset token produces one
`RuntimeError` and one error record per handle — twenty rows for one environment fact.

- [ ] Failing test (one per adapter; Instagram shown):

```python
def test_preflight_reports_a_missing_key_once_without_calling_bright_data(monkeypatch, tmp_path):
    monkeypatch.delenv(ig.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(ig, "KEY_FILE", tmp_path / "absent.txt")

    def _fail_if_called(*a, **k):
        raise AssertionError("preflight must not touch the network")

    monkeypatch.setattr(ig.requests, "post", _fail_if_called)
    message = ig.preflight()
    assert message is not None
    assert ig.KEY_ENV_VAR in message
    assert "instagram" in message


def test_preflight_returns_none_when_the_key_is_configured(monkeypatch, tmp_path):
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("k", encoding="utf-8")
    monkeypatch.delenv(ig.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(ig, "KEY_FILE", key_file)
    assert ig.preflight() is None
```

- [ ] Implement in each adapter (LinkedIn as a method on `LinkedInAdapter`):

```python
def preflight() -> str | None:
    """None if this platform can run; one operator-facing message if it cannot.

    B-21: the per-job guard in _run_collection_job stays as a backstop, but it
    fires once per handle, so one unset token used to produce twenty identical
    error rows and a run that finished 'completed_with_errors' rather than
    refusing to start. run_discovery_cron calls this once before the handle
    loop (P8).
    """
    if api_key() is None:
        return (f"instagram: Bright Data API key not configured "
                f"(set {KEY_ENV_VAR} or {KEY_FILE.name}) -- every instagram "
                f"handle in this run will fail")
    return None
```

- [ ] Keep the existing per-job `RuntimeError` guards untouched.
- [ ] `git commit -m "feat(brightdata): per-platform preflight so one missing token is one message"`

---

### T14 — Configurable operational knobs (B-03, part 1)

`MAX_ITEMS_PER_RUN`, `POLL_TIMEOUT_S`, `POLL_INTERVAL_S` and `REQUEST_TIMEOUT_S` all require
a source edit and a redeploy. X already needed a different `POLL_TIMEOUT_S` — direct evidence
that one literal does not fit every platform.

- [ ] Failing tests:

```python
def test_config_int_prefers_an_environment_override(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_TEST_KNOB", "25")
    assert bd.config_int("BRIGHTDATA_TEST_KNOB", 10) == 25


def test_config_int_falls_back_to_the_default_and_reports_a_bad_override(monkeypatch):
    """A typo'd knob must not silently become a different number, and must not
    crash a run either -- it reports and uses the default."""
    monkeypatch.setenv("BRIGHTDATA_TEST_KNOB", "twenty")
    bd.drain_diagnostics()
    assert bd.config_int("BRIGHTDATA_TEST_KNOB", 10) == 10
    assert [d["kind"] for d in bd.drain_diagnostics()] == ["config.bad_override"]


def test_config_int_rejects_a_nonpositive_override(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_TEST_KNOB", "0")
    assert bd.config_int("BRIGHTDATA_TEST_KNOB", 10) == 10
```

- [ ] Implement:

```python
def config_int(name: str, default: int) -> int:
    """An operational knob: environment override, module literal as default.

    B-03: every cap and timeout was a source literal. Overrides are read PER
    PLATFORM and never shared -- discovery_x.py:40-43 records why one number
    does not fit all four. Note that raising an ITEM CAP raises Bright Data
    spend proportionally; raising a TIMEOUT does not.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value <= 0:
        record_diagnostic(kind="config.bad_override", severity="warning",
                          source="brightdata_job",
                          message=f"{name}={raw!r} is not a positive integer; using {default}",
                          detail={"name": name, "raw": raw, "default": default})
        return default
    return value
```

- [ ] `git commit -m "feat(brightdata): environment-overridable operational knobs"`

---

### T15 — Apply the knobs per platform (B-03, part 2)

- [ ] Failing test per adapter (Instagram shown):

```python
def test_max_items_honours_the_per_platform_override(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_MAX_ITEMS_INSTAGRAM", "25")
    assert ig.max_items() == 25
    monkeypatch.delenv("BRIGHTDATA_MAX_ITEMS_INSTAGRAM")
    assert ig.max_items() == ig.MAX_ITEMS_PER_RUN == 10


def test_instagram_override_does_not_change_x(monkeypatch):
    """One knob per platform: raising Instagram's cap must not silently raise
    the spend on an account posting hundreds of times a day."""
    monkeypatch.setenv("BRIGHTDATA_MAX_ITEMS_INSTAGRAM", "50")
    assert x.max_items() == 10
```

- [ ] Implement in each adapter — keep the literal as the default so existing
      `monkeypatch.setattr(ig, "MAX_ITEMS_PER_RUN", …)` tests keep working:

```python
MAX_ITEMS_PER_RUN = 10           # the default; override with the env var below
MAX_ITEMS_ENV_VAR = "BRIGHTDATA_MAX_ITEMS_INSTAGRAM"


def max_items() -> int:
    return brightdata_job.config_int(MAX_ITEMS_ENV_VAR, MAX_ITEMS_PER_RUN)


def poll_timeout_s() -> float:
    return brightdata_job.config_int("BRIGHTDATA_POLL_TIMEOUT_INSTAGRAM", POLL_TIMEOUT_S)
```

- [ ] Replace every `MAX_ITEMS_PER_RUN` / `POLL_TIMEOUT_S` *use site* in the four adapters
      with the function call (`_trigger_job`'s `limit_per_input` and `num_of_posts`, the
      client-side cap in `enumerate_newest_first`, and `await_results`' `poll_timeout_s`).
      Leave `discovery_x.POLL_TIMEOUT_S = 600` and its comment intact as X's default.
- [ ] `git commit -m "feat(brightdata): per-platform caps and timeouts, defaults unchanged"`

---

### T16 — Saturation detection (B-02, part 1) — **S1**

A full-cap batch means the *cap*, not the account, decided where the batch ended. Because
`BACKFILL_SUPPORTED_PLATFORMS` excludes all four platforms and X's own docstring records that
date-ranged backfill returns `dead_page`, the overflow can never be collected later.

- [ ] Failing tests:

```python
def test_a_full_cap_batch_is_saturated():
    assert bd.is_saturated(10, cap=10) is True
    assert bd.is_saturated(11, cap=10) is True


def test_a_short_batch_is_not_saturated():
    """Distinguishability, at the unit level: a genuinely quiet account and a
    truncated one must not compute the same."""
    assert bd.is_saturated(9, cap=10) is False
    assert bd.is_saturated(0, cap=10) is False
```

- [ ] Implement:

```python
def is_saturated(collected: int, *, cap: int) -> bool:
    """True when the cap, not the account, decided where this batch ended.

    B-02 (S1): the four Bright Data platforms fetch at most `cap` posts per
    handle per run and are all excluded from BACKFILL_SUPPORTED_PLATFORMS, so
    anything above the cap is dropped with no recovery path at all. A
    saturated batch is therefore a data-loss event, not a busy day.
    """
    return cap > 0 and collected >= cap
```

- [ ] `git commit -m "feat(brightdata): detect a cap-truncated batch"`

---

### T17 — Escalate saturation in all four adapters (B-02, part 2) — **S1**

- [ ] Failing tests per adapter (Instagram shown; repeat for LinkedIn, Facebook, X):

```python
def test_full_cap_batch_records_a_saturation_error(monkeypatch):
    """Fault test. Ten of ten means posts were dropped that no later run can
    fetch -- the handle still reports 'ok', so this must be reported here."""
    raw = [_raw_row(f"p{i}", "2026-08-01") for i in range(10)]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    brightdata_job.drain_diagnostics()
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    saturation = [d for d in brightdata_job.drain_diagnostics()
                  if d["kind"] == "adapter.batch_saturated"]
    assert len(saturation) == 1
    assert saturation[0]["severity"] == "error"


def test_a_short_batch_records_no_saturation_diagnostic(monkeypatch):
    """Distinguishability. Nine of ten is a quiet account; ten of ten is
    truncation. The two must be observably different."""
    raw = [_raw_row(f"p{i}", "2026-08-01") for i in range(9)]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    brightdata_job.drain_diagnostics()
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    assert [d for d in brightdata_job.drain_diagnostics()
            if d["kind"] == "adapter.batch_saturated"] == []


def test_saturation_diagnostic_names_the_cap_the_override_and_the_lost_window(monkeypatch):
    """Surfacing. The record must be actionable on its own: an operator
    reading it in the log or the events table must know what to change."""
    raw = [_raw_row(f"p{i}", "2026-08-01") for i in range(10)]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    brightdata_job.drain_diagnostics()
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    record = [d for d in brightdata_job.drain_diagnostics()
              if d["kind"] == "adapter.batch_saturated"][0]
    assert record["detail"]["cap"] == 10
    assert record["detail"]["handle"] == "somehandle"
    assert record["detail"]["platform"] == "instagram"
    assert ig.MAX_ITEMS_ENV_VAR in record["message"]
    assert "no backfill" in record["message"]
```

- [ ] Implement in each `enumerate_newest_first`, computed on the pre-truncation count and
      placed immediately before the client-side cap:

```python
    cap = max_items()
    if brightdata_job.is_saturated(len(kept), cap=cap):
        oldest = min((n["published_ts"] for n in kept), default=None)
        brightdata_job.record_diagnostic(
            kind="adapter.batch_saturated", severity="error",
            source="discovery_instagram",
            message=(f"instagram/{handle}: the batch filled the cap of {cap}. Posts "
                     f"older than {oldest} in this interval were dropped and there is "
                     f"no backfill path for this platform. Raise "
                     f"{MAX_ITEMS_ENV_VAR} (this increases Bright Data spend per run) "
                     f"or shorten the run interval."),
            detail={"platform": "instagram", "handle": handle, "cap": cap,
                    "collected": len(kept), "oldest_kept": oldest})
        print(f"  !! instagram/{handle}: batch filled the cap of {cap}; older posts "
              f"in this interval are unrecoverable", file=sys.stderr)
```

- [ ] Rewrite `test_discovery_instagram.py:300-305`
      (`test_enumerate_newest_first_caps_at_max_items_per_run`) — see §5, it currently sets
      the value it asserts.
- [ ] `git commit -m "fix(brightdata): escalate a cap-truncated batch instead of reporting ok"`

---

### T18 — Instagram's billed-and-captured-nothing escalation (B-22)

LinkedIn, Facebook and X each carry an explicit `if raw_rows and not kept:` branch. Instagram
— the adapter whose original bug the whole discipline is named after — has none, and never
inspects `error`/`error_code`, so the vendor's own reason is discarded.

- [ ] Failing tests in `test_discovery_instagram.py`:

```python
def _error_row(code="dead_page"):
    """With include_errors=true a failure arrives as a ROW, not an absence."""
    return {"input": {"url": "https://www.instagram.com/gone/"},
            "error": "Page not found", "error_code": code}


def test_all_error_rows_escalate_billed_and_captured_nothing(monkeypatch, capsys):
    """Fault test. A renamed or deleted handle returns error rows; the run is
    billed, captures nothing, and today records the healthy 'no_new_content'."""
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: [_error_row()])
    brightdata_job.drain_diagnostics()
    assert ig.enumerate_newest_first("gone", keyword_filter=None) == []
    err = capsys.readouterr().err
    assert "billed and captured nothing" in err
    assert "dead_page" in err


def test_a_genuinely_empty_batch_does_not_escalate(monkeypatch, capsys):
    """Distinguishability. Zero rows is a quiet day and must stay quiet;
    N rows of which none survived is a paid-for failure."""
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: [])
    brightdata_job.drain_diagnostics()
    assert ig.enumerate_newest_first("quiet", keyword_filter=None) == []
    assert "billed and captured nothing" not in capsys.readouterr().err
    assert brightdata_job.drain_diagnostics() == []


def test_billed_nothing_records_an_error_diagnostic_carrying_the_vendor_codes(monkeypatch):
    """Surfacing. stderr has no destination on the scheduled path (B-01)."""
    monkeypatch.setattr(ig, "_run_collection_job",
                        lambda handle: [_error_row("dead_page"), _error_row("blocked")])
    brightdata_job.drain_diagnostics()
    ig.enumerate_newest_first("gone", keyword_filter=None)
    record = [d for d in brightdata_job.drain_diagnostics()
              if d["kind"] == "adapter.billed_captured_nothing"][0]
    assert record["severity"] == "error"
    assert record["detail"]["handle"] == "gone"
    assert sorted(record["detail"]["error_codes"]) == ["blocked", "dead_page"]
```

- [ ] Port `_error_codes` from `discovery_facebook.py:125-132` verbatim into
      `discovery_instagram.py`, and add the escalation branch after the drop count,
      mirroring `discovery_facebook.py:231-239` plus the `record_diagnostic` call.
- [ ] `git commit -m "fix(instagram): escalate a billed batch that captured nothing"`

---

### T19 — Instagram records the row's author (B-23, part 1)

X filters on `user_posted` and LinkedIn-profile on `user_id`, both because live testing showed
the vendor returning other accounts' posts. Facebook records `author` deliberately "so a
regression is detectable after the fact". Instagram neither filters nor records.

**Honesty constraint:** the Instagram Posts dataset's owner field name has *not* been verified
against a live snapshot the way Facebook's `profile_handle` and X's `user_posted` were
(2026-08-08). Do not guess one name and write it as fact. Read a candidate list, record which
candidate hit, and say so loudly when none does — one real run then tells the operator the
true field name.

- [ ] Failing tests:

```python
def test_normalize_row_records_the_owner_when_the_row_carries_one():
    row = {"post_id": "p1", "description": "x", "date_posted": "07/23/2026 16:00:22",
           "user_posted": "nike"}
    assert ig._normalize_row(row)["author"] == "nike"


def test_normalize_row_records_an_empty_author_rather_than_dropping_the_row():
    """An unknown owner field must never cost a paid row."""
    row = {"post_id": "p1", "description": "x", "date_posted": "07/23/2026 16:00:22"}
    normalized = ig._normalize_row(row)
    assert normalized is not None
    assert normalized["author"] == ""


def test_an_unresolved_author_field_is_reported_once_with_the_real_row_keys(monkeypatch):
    """The candidate list is a hypothesis, not a verified fact. When it misses,
    the diagnostic must carry the keys the vendor actually sent so the next
    edit is informed rather than another guess."""
    monkeypatch.setattr(ig, "_run_collection_job",
                        lambda handle: [_raw_row("p1", "2026-08-01")])
    brightdata_job.drain_diagnostics()
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    record = [d for d in brightdata_job.drain_diagnostics()
              if d["kind"] == "adapter.author_field_unresolved"][0]
    assert record["severity"] == "warning"
    assert "post_id" in record["detail"]["observed_keys"]


def test_download_item_writes_the_author_to_frontmatter(tmp_path, monkeypatch):
    row = _raw_row("p1", "2026-08-01")
    row["user_posted"] = "nike"
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: [row])
    ig.enumerate_newest_first("nike", keyword_filter=None)
    ig.download_item(tmp_path, "nike", "p1", "t")
    text = (tmp_path / "output" / "brand-intel" / "instagram" / "nike" / "p1.md").read_text(
        encoding="utf-8")
    assert "author: nike" in text
```

- [ ] Implement in `discovery_instagram.py`:

```python
# UNVERIFIED FIELD NAMES. Facebook's `profile_handle` and X's `user_posted`
# were both confirmed against live snapshots on 2026-08-08; this dataset's
# owner field was not. Read the candidates in order and report loudly when
# none is present rather than inventing a name -- B-23 asks for the field to
# be RECORDED (Facebook's rationale: it is what makes "this dataset started
# returning other accounts" detectable after the fact), not filtered on.
# Filtering waits for a live sample.
AUTHOR_FIELD_CANDIDATES = ("user_posted", "profile_name", "owner_username",
                           "user_username_raw", "username")


def _first_present(row: dict, candidates: tuple[str, ...]):
    for name in candidates:
        value = row.get(name)
        if value not in (None, ""):
            return name, value
    return None, None
```

`_normalize_row` gains `"author": str(_first_present(row, AUTHOR_FIELD_CANDIDATES)[1] or "").strip()`;
`enumerate_newest_first` records `adapter.author_field_unresolved` once per batch when every
kept row resolved to `""`, with `detail={"observed_keys": sorted(raw_rows[0])}`;
`download_item`'s `meta` gains `"author": cached["author"]` placed beside `handle`, matching
Facebook's ordering.

- [ ] `git commit -m "fix(instagram): record the row owner so contamination is detectable"`

---

### T20 — Instagram records `view_count` (B-23, part 2)

The appendix records that Instagram Reels carry a view count in this dataset and the adapter
does not map it. The exact field name is, again, unverified — same candidate-list treatment.

LinkedIn is **out of scope here**: neither the appendix nor the LinkedIn design doc records a
view-count field on that dataset, so there is nothing to map and nothing to guess. `view_count`
is an optional contract field; its absence there is not a defect. Recorded in §7.

- [ ] Failing tests:

```python
def test_normalize_row_maps_a_reel_view_count_when_present():
    row = {"post_id": "p1", "description": "x", "date_posted": "07/23/2026 16:00:22",
           "content_type": "Reel", "video_play_count": 88381}
    assert ig._normalize_row(row)["view_count"] == 88381


def test_view_count_is_omitted_not_nulled_when_the_row_has_none():
    """The contract makes view_count optional. A photo post has no views;
    writing 'view_count: null' would assert a measured zero-ish value."""
    row = {"post_id": "p1", "description": "x", "date_posted": "07/23/2026 16:00:22",
           "content_type": "Post"}
    assert ig._normalize_row(row)["view_count"] is None


def test_download_item_omits_view_count_for_a_non_video_post(tmp_path, monkeypatch):
    monkeypatch.setattr(ig, "_run_collection_job",
                        lambda handle: [_raw_row("p1", "2026-08-01")])
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    ig.download_item(tmp_path, "somehandle", "p1", "t")
    text = (tmp_path / "output" / "brand-intel" / "instagram" / "somehandle" / "p1.md"
            ).read_text(encoding="utf-8")
    assert "view_count" not in text
```

- [ ] Implement `VIEW_COUNT_FIELD_CANDIDATES = ("video_play_count", "video_view_count", "views")`,
      map it in `_normalize_row` via `_first_present`, and in `download_item` add the key to
      `meta` only when it is not `None`. Keep `fetched_at` unconditional (contract invariant 3).
- [ ] `git commit -m "fix(instagram): map the reel view count, omitted when absent"`

---

### T21 — Adopt the diagnostics sink across all four adapters (B-01)

The orchestration plan's adoption rule: keep the print, add the event.

- [ ] Failing test per adapter (Facebook shown):

```python
def test_dropped_rows_reach_a_durable_surface_not_only_stderr(monkeypatch, capsys):
    """Fault test. The Scheduled Task command has no redirection, so a stderr
    warning on the production path has no destination at all (B-01)."""
    _stub_job(monkeypatch, [_row("p1", "2026-07-06"), {"no": "id"}])
    brightdata_job.drain_diagnostics()
    fb.enumerate_newest_first("NASA", keyword_filter=None)
    record = [d for d in brightdata_job.drain_diagnostics()
              if d["kind"] == "adapter.rows_dropped"][0]
    assert record["severity"] == "warning"
    assert record["detail"]["dropped"] == 1
    assert record["source"] == "discovery_facebook"
    assert "dropped 1 unusable" in capsys.readouterr().err   # the print stays


def test_a_clean_batch_produces_no_diagnostics_at_all(monkeypatch):
    """Distinguishability. A degraded run must be observably different from a
    healthy one -- 'no diagnostics' is the healthy signal."""
    _stub_job(monkeypatch, [_row("p1", "2026-07-06")])
    brightdata_job.drain_diagnostics()
    fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert brightdata_job.drain_diagnostics() == []


def test_diagnostics_carry_everything_obs_record_event_requires(monkeypatch):
    """Surfacing. P8 writes these straight into the events table; a record
    missing a column is a record that never becomes a row."""
    _stub_job(monkeypatch, [_row("p1", "2026-07-06"), {"no": "id"}])
    brightdata_job.drain_diagnostics()
    fb.enumerate_newest_first("NASA", keyword_filter=None)
    for record in brightdata_job.drain_diagnostics():
        assert set(record) == {"kind", "severity", "source", "message", "detail"}
        assert record["severity"] in {"info", "warning", "error", "critical"}
        assert record["message"]
```

- [ ] Add a `record_diagnostic` call beside every existing stderr `print` in the four
      adapters — `discovery_instagram.py:222-224`, `discovery_facebook.py:226-239`,
      `discovery_x.py:242-267`, `discovery_linkedin.py:224-250` — using kinds
      `adapter.rows_dropped`, `adapter.foreign_rows_dropped`,
      `adapter.billed_captured_nothing`. Keep every print exactly as-is.
- [ ] `git commit -m "fix(brightdata): adapter degradations reach a durable surface"`

---

### T22 — Delete the unused re-exports (B-25)

- [ ] Failing test in `test_brightdata_job.py`:

```python
def test_adapters_do_not_re_export_request_timeout(monkeypatch):
    """REQUEST_TIMEOUT_S was re-exported by instagram and x and read by
    neither them nor any test; facebook and linkedin correctly omit it, so
    the two that had it were the outliers. BRIGHTDATA_API_BASE re-exports ARE
    used and must stay."""
    from pipeline_app import (discovery_facebook, discovery_instagram,
                              discovery_linkedin, discovery_x)
    for module in (discovery_instagram, discovery_x,
                   discovery_facebook, discovery_linkedin):
        assert not hasattr(module, "REQUEST_TIMEOUT_S")
        assert module.__name__.endswith("linkedin") or module.BRIGHTDATA_API_BASE
```

- [ ] Delete `discovery_instagram.py:27` and `discovery_x.py:149`.
- [ ] `git commit -m "chore(brightdata): drop two unused REQUEST_TIMEOUT_S re-exports"`

---

### T23 — Public reset hooks and module-local isolation fixtures (F-67)

Eleven assertions read process-global dictionaries no fixture clears. `pytest-xdist` is
installed; `-n auto`, `-k` or `--lf` changes which globals are warm.

- [ ] Failing test in `test_brightdata_job.py`:

```python
def test_every_bright_data_adapter_exposes_a_cache_reset(monkeypatch, tmp_path):
    """The conftest autouse fixture (P0) needs one hook per adapter. A new
    adapter that forgets it silently re-opens F-67."""
    from pipeline_app import (discovery_facebook, discovery_instagram,
                              discovery_linkedin, discovery_x)
    for module in (discovery_instagram, discovery_facebook, discovery_x):
        module.reset_caches()
        assert module.cached_ids("nobody") == set()
    adapter = discovery_linkedin.profile_adapter()
    adapter.reset_caches()
    assert adapter.cached_ids("nobody") == set()
```

- [ ] Implement in each of the three module adapters:

```python
def reset_caches() -> None:
    """Clear this module's per-process enumerate cache.

    F-67: the cache is a process global that no fixture cleared, so the suite
    passed only because each test file happened to use distinct handle names.
    The repo-wide conftest fixture calls this before every test.
    """
    _ENUMERATE_CACHE.clear()


def cached_ids(handle: str) -> set[str]:
    """The item ids this handle's last enumerate retained. A read-only view so
    tests never reach into _ENUMERATE_CACHE directly."""
    return set(_ENUMERATE_CACHE.get(handle, {}))


def cached_row(handle: str, item_id: str) -> dict:
    """One retained row. KeyError if absent -- same contract download_item has."""
    return _ENUMERATE_CACHE[handle][item_id]
```

and the instance equivalents on `LinkedInAdapter` (`reset_caches`, `cached_ids`,
`cached_row`) operating on `self._cache`.

- [ ] Add `brightdata_job.reset_state()` clearing `_DIAGNOSTICS`.
- [ ] Add a module-local autouse fixture at the top of each of the six test files, so P7's
      suite is order-independent even before P0's conftest lands (Instagram shown):

```python
@pytest.fixture(autouse=True)
def _isolate_instagram_state(monkeypatch, tmp_path):
    """F-67 + F-69, belt and braces with the repo-wide conftest guard (P0).
    Clears the process-global cache and the diagnostics buffer, points the
    pending store at tmp_path, and makes sure no test can see the real
    BRIGHTDATA_API_KEY that is set in this machine's environment."""
    monkeypatch.delenv(ig.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(ig, "KEY_FILE", tmp_path / "no-brightdata_api_key.txt")
    monkeypatch.setattr(brightdata_job, "PENDING_STORE_PATH", tmp_path / "pending.json")
    ig.reset_caches()
    brightdata_job.reset_state()
    yield
    ig.reset_caches()
    brightdata_job.reset_state()
```

- [ ] `git commit -m "test(brightdata): reset hooks and per-file state isolation"`

---

### T24 — Rewrite the private-cache assertions (F-67)

Sixteen assertions reach into `_ENUMERATE_CACHE` / `_cache`. Rewrite each through the public
accessor from T23, and rewrite the two that are better expressed as effects. Full list with
line numbers in §5.

- [ ] `test_discovery_instagram.py:327` becomes an effect assertion — the point of the cache
      is that `download_item` can read the full caption from it:

```python
def test_enumerate_caches_the_full_caption_for_download_item(monkeypatch, tmp_path):
    raw = [_raw_row("p1", "2026-08-01", caption="full caption text")]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    ig.download_item(tmp_path, "somehandle", "p1", "truncated title")
    text = (tmp_path / "output" / "brand-intel" / "instagram" / "somehandle" / "p1.md"
            ).read_text(encoding="utf-8")
    assert "full caption text" in text
```

- [ ] `test_discovery_instagram.py:335-336` → `assert ig.cached_ids("somehandle") == {"new_batch"}`
      (an equality, not two memberships: the old form passed even if the cache had merged).
- [ ] `test_discovery_facebook.py:386,394,395,406,418`,
      `test_discovery_x.py:453,463,493`,
      `test_discovery_linkedin.py:411,420-421,435-436` → `cached_ids(...)` / `cached_row(...)`.
- [ ] `git commit -m "test(brightdata): assert cache behavior through a public view"`

---

### T25 — Thread `repo_root` through credential lookup (F-69)

Tests isolate state by passing `repo_root=tmp_path`, but `KEY_FILE` is anchored to the real
repo, so a "fully sandboxed" test still holds a live production credential.

- [ ] Failing tests:

```python
def test_key_file_honours_the_repo_root_everything_else_uses(monkeypatch, tmp_path):
    (tmp_path / "pipeline-app").mkdir()
    (tmp_path / "pipeline-app" / "brightdata_api_key.txt").write_text("sandbox-key",
                                                                     encoding="utf-8")
    monkeypatch.delenv(ig.KEY_ENV_VAR, raising=False)
    assert ig.api_key(repo_root=tmp_path) == "sandbox-key"


def test_a_sandboxed_root_without_a_key_file_yields_no_key(monkeypatch, tmp_path):
    """The defect F-69 names: repo_root=tmp_path used to be ignored entirely,
    so this returned the real repo's token."""
    monkeypatch.delenv(ig.KEY_ENV_VAR, raising=False)
    assert ig.api_key(repo_root=tmp_path) is None


def test_api_key_without_a_repo_root_still_reads_the_module_key_file(monkeypatch, tmp_path):
    """Existing callers pass nothing; the default must not change."""
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("module-key", encoding="utf-8")
    monkeypatch.delenv(ig.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(ig, "KEY_FILE", key_file)
    assert ig.api_key() == "module-key"
```

- [ ] Implement in each adapter (LinkedIn as a method):

```python
def key_file_for(repo_root: Path | None) -> Path:
    """The credential file, resolved against the same root everything else
    uses. F-69: KEY_FILE was anchored to the real repo, so a test passing
    repo_root=tmp_path was still one env var away from a live token."""
    if repo_root is None:
        return KEY_FILE
    return Path(repo_root) / "pipeline-app" / KEY_FILE.name


def api_key(repo_root: Path | None = None) -> str | None:
    """The Bright Data API token, or None if not configured. Reads this
    module's KEY_ENV_VAR and the repo_root-resolved key file at call time so
    tests can patch them."""
    return brightdata_job.read_key(KEY_ENV_VAR, key_file_for(repo_root))
```

- [ ] Add an optional `repo_root` passthrough on `preflight(repo_root=None)`.
- [ ] Do **not** remove the six existing ad-hoc `KEY_FILE` monkeypatches in the
      `test_api_key_*` tests — they now test the documented default path (third test above).
- [ ] `git commit -m "fix(brightdata): resolve the API key file against repo_root"`

---

## 4. Finding → test map

`silent` findings carry all three Three-Test-Rule roles. Test files are under
`pipeline-app/tests/`.

| Finding | Mode | Test | Role |
|---|---|---|---|
| **D-03** | silent | `test_await_results_raises_and_never_fetches_on_timeout` | fault |
| | | `test_failed_job_is_distinguishable_from_a_genuinely_empty_one` | distinguishability |
| | | `test_timeout_persists_the_snapshot_for_a_later_free_fetch` (T8 — asserts the durable record a failure leaves) | surfacing |
| **B-01** | silent | `test_dropped_rows_reach_a_durable_surface_not_only_stderr` (×4 adapters) | fault |
| | | `test_a_clean_batch_produces_no_diagnostics_at_all` (×4 adapters) | distinguishability |
| | | `test_diagnostics_carry_everything_obs_record_event_requires`, `test_record_diagnostic_writes_through_to_obs_log` | surfacing |
| **B-02** | silent | `test_full_cap_batch_records_a_saturation_error` (×4 adapters) | fault |
| | | `test_a_short_batch_records_no_saturation_diagnostic` (×4), `test_a_short_batch_is_not_saturated` | distinguishability |
| | | `test_saturation_diagnostic_names_the_cap_the_override_and_the_lost_window` | surfacing |
| **B-22** | silent | `test_all_error_rows_escalate_billed_and_captured_nothing` | fault |
| | | `test_a_genuinely_empty_batch_does_not_escalate` | distinguishability |
| | | `test_billed_nothing_records_an_error_diagnostic_carrying_the_vendor_codes` | surfacing |
| B-03 | latent | `test_config_int_prefers_an_environment_override`, `test_config_int_falls_back_to_the_default_and_reports_a_bad_override`, `test_config_int_rejects_a_nonpositive_override`, `test_max_items_honours_the_per_platform_override` (×4), `test_instagram_override_does_not_change_x` | — |
| B-18 | loud | `test_poll_status_retries_a_transient_503_and_then_succeeds`, `test_poll_status_does_not_retry_a_401`, `test_poll_status_raises_after_the_retry_budget_is_exhausted`, `test_fetch_results_retries_a_transient_connection_error`, `test_trigger_is_never_retried_because_a_retried_trigger_double_bills` | — |
| B-19 | loud | `test_timeout_exception_carries_the_snapshot_id_as_data_not_only_prose`, `test_timeout_persists_the_snapshot_for_a_later_free_fetch`, `test_a_failed_job_is_not_persisted_because_there_is_nothing_to_recover`, `test_pending_store_survives_a_corrupt_file`, `test_resume_pending_collects_a_ready_snapshot_without_triggering_anything`, `test_resume_pending_returns_none_and_keeps_the_entry_while_still_running`, `test_resume_pending_drops_a_failed_snapshot_and_says_so`, `test_resume_pending_is_a_no_op_when_nothing_is_pending`, `test_run_collection_job_prefers_a_pending_snapshot_over_a_new_billed_job` (×4), `test_profile_and_company_pending_snapshots_never_collide`, `test_delete_snapshot_is_off_by_default`, `test_delete_after_fetch_only_runs_once_the_rows_are_in_hand` | — |
| B-20 | loud | `test_trigger_names_the_endpoint_and_the_received_keys_on_a_bad_body`, `test_fetch_results_rejects_a_dict_payload_instead_of_handing_it_on` | — |
| B-21 | loud | `test_preflight_reports_a_missing_key_once_without_calling_bright_data` (×4), `test_preflight_returns_none_when_the_key_is_configured` (×4) | — |
| B-23 | latent | `test_normalize_row_records_the_owner_when_the_row_carries_one`, `test_normalize_row_records_an_empty_author_rather_than_dropping_the_row`, `test_an_unresolved_author_field_is_reported_once_with_the_real_row_keys`, `test_download_item_writes_the_author_to_frontmatter`, `test_normalize_row_maps_a_reel_view_count_when_present`, `test_view_count_is_omitted_not_nulled_when_the_row_has_none`, `test_download_item_omits_view_count_for_a_non_video_post` | — |
| B-24 | latent | `test_trigger_refuses_an_unprovisioned_dataset_id_before_any_http_call` | — |
| B-25 | latent | `test_adapters_do_not_re_export_request_timeout` | — |
| F-67 | latent | `test_every_bright_data_adapter_exposes_a_cache_reset`, plus the 16 rewritten assertions in §5 and the six module-local autouse fixtures | — |
| F-69 | latent | `test_key_file_honours_the_repo_root_everything_else_uses`, `test_a_sandboxed_root_without_a_key_file_yields_no_key`, `test_api_key_without_a_repo_root_still_reads_the_module_key_file` (×4 adapters) | — |

---

## 5. Tests deleted or inverted

| File:line | Test | Disposition | Replacement |
|---|---|---|---|
| `pipeline-app/tests/test_discovery_instagram.py:147-154` | `test_trigger_job_raises_when_dataset_id_still_placeholder` | **DELETED** | Exercised unreachable dead code (B-24): `DATASET_ID` has been the real provisioned id since 2026-08-06, and the test only reached the branch by monkeypatching the constant. Replaced by `test_trigger_refuses_an_unprovisioned_dataset_id_before_any_http_call` in `test_brightdata_job.py`, which covers all four adapters and asserts no POST is made. |
| `pipeline-app/tests/test_discovery_instagram.py:300-305` | `test_enumerate_newest_first_caps_at_max_items_per_run` | **INVERTED** | Anti-tautology: line 303 does `monkeypatch.setattr(ig, "MAX_ITEMS_PER_RUN", 10)` and line 305 asserts `len(items) == 10` — it asserts the value it just set. Replaced by `test_full_cap_batch_records_a_saturation_error` + `test_a_short_batch_records_no_saturation_diagnostic` (T17), which assert the *consequence* of truncation rather than echoing the cap. |
| `pipeline-app/tests/test_discovery_instagram.py:125` | `…posts_expected_request…` (`num_of_posts == ig.MAX_ITEMS_PER_RUN`) | **INVERTED** | Echo assertion: compares the request against the module constant, so any wrong constant passes. Becomes `assert captured["json"][0]["num_of_posts"] == 10` with a comment naming 10 as the approved default spend per handle per run. |
| `pipeline-app/tests/test_discovery_instagram.py:144` | `…discovery_job_not_a_single_page_collect…` (`limit_per_input == ig.MAX_ITEMS_PER_RUN`) | **INVERTED** | Same echo defect. Becomes `assert captured["limit_per_input"] == 10`. |
| `pipeline-app/tests/test_discovery_instagram.py:327` | `test_enumerate_newest_first_populates_cache_for_download_item` | **REWRITTEN** | Reads the process global `ig._ENUMERATE_CACHE` (F-67). Replaced by the effect assertion in T24 — the caption reaches the written file. |
| `pipeline-app/tests/test_discovery_instagram.py:335-336` | `test_enumerate_newest_first_overwrites_previous_cache_entry` | **REWRITTEN** | Two membership assertions pass even if the cache merged. Becomes `assert ig.cached_ids("somehandle") == {"new_batch"}`. |
| `pipeline-app/tests/test_discovery_facebook.py:386` | `test_enumerate_overwrites_rather_than_merges_the_cache` | **REWRITTEN** | `fb._ENUMERATE_CACHE["NASA"]` → `fb.cached_ids("NASA")`. |
| `pipeline-app/tests/test_discovery_facebook.py:394-395` | `test_enumerate_caches_per_handle` | **REWRITTEN** | → `fb.cached_ids("NASA")` / `fb.cached_ids("zuck")`. |
| `pipeline-app/tests/test_discovery_facebook.py:406` | `test_enumerate_caches_items_filtered_out_by_keyword` | **REWRITTEN** | → `fb.cached_ids("NASA")`. |
| `pipeline-app/tests/test_discovery_facebook.py:418` | `test_enumerate_does_not_filter_by_author` | **REWRITTEN** | → `fb.cached_row("100044561550831", "p1")["author"]`. |
| `pipeline-app/tests/test_discovery_x.py:453` | `test_enumerate_caches_rows_for_download_item` | **REWRITTEN** | → `x.cached_row("CNN", "1")["author"]`. |
| `pipeline-app/tests/test_discovery_x.py:463` | `test_enumerate_overwrites_rather_than_merges_the_cache` | **REWRITTEN** | → `x.cached_ids("CNN")`. |
| `pipeline-app/tests/test_discovery_x.py:493` | `test_enumerate_keys_identity_on_id_not_url` | **REWRITTEN** | → `x.cached_ids("CNN")`. |
| `pipeline-app/tests/test_discovery_linkedin.py:411` | (caches body for `download_item`) | **REWRITTEN** | → `adapter.cached_row("lanieri", "c1")["body"]`. |
| `pipeline-app/tests/test_discovery_linkedin.py:420-421` | (overwrite, not merge) | **REWRITTEN** | → `assert adapter.cached_ids("lanieri") == {"new_batch"}`. |
| `pipeline-app/tests/test_discovery_linkedin.py:435-436` | (profile vs company isolation) | **REWRITTEN** | → `person.cached_ids("acme")` / `company.cached_ids("acme")`. This test stays — it pins invariant 2. |
| `pipeline-app/tests/test_discovery_instagram_sort.py:12-13` | module docstring | **CORRECTED** | The docstring asserts `test_discovery_instagram.py` "is pinned byte-for-byte by the fix-wave brief and must not be edited." That brief is closed; this plan edits that file under T3/T17/T18/T19/T20/T23/T24. Replace those two lines with a pointer to this plan so the next reader is not blocked by a stale constraint. |

Nothing else in the six files asserts a defective behavior. `test_await_results_never_fetches_when_job_fails`
(`test_brightdata_job.py:118-133`) and `test_enumerate_newest_first_ready_with_empty_results_returns_empty_list`
(`test_discovery_instagram.py:86-92`) are **kept** — they are the correct half of the
"empty ≠ failed" pair and become D-03's and B-22's distinguishability partners.

---

## 6. Cost note

**Bright Data is billed per record.** Every item below is a change in this plan that could
move spend. The operator approves or declines each one before T1 starts.

> **Operator decision recorded 2026-08-16 (P7 kickoff session).** C1, C2, and C3 are all
> **approved**, each at the table's own stated default (C1: knob ships, stays at 10 until an
> operator sets an env var; C2: on by default; C3: on by default). C4-C9 need no approval and
> proceed per plan. Separately, the §7 residual #4 (`discovery_youtube.USER_AGENT`) is approved
> as a tiny flagged exception: T22 (or the final review) may make a one-line unreferenced-string
> removal in P6's `discovery_youtube.py`, called out explicitly in the PR body as an
> out-of-scope-file exception — not a silent scope creep.

### Increases spend — approval required

| # | Change | Task | Effect | Default |
|---|---|---|---|---|
| **C1** | Per-platform item-cap override `BRIGHTDATA_MAX_ITEMS_<PLATFORM>` | T14, T15 | Raising a cap raises records collected per handle per run **proportionally**. Setting Instagram to 50 quintuples Instagram spend. | **Unchanged at 10.** The knob only exists; nothing sets it. Declining C1 means keeping B-02's truncation with no operator-accessible remedy. |
| **C2** | Saturation escalation | T16, T17 | No direct cost. It will surface handles that are being truncated, which is an invitation to raise C1. The message deliberately says *"this increases Bright Data spend per run"* so the prompt carries its own price tag. | On. Reporting-only. |
| **C3** | Resume-pending re-fetch | T9, T10, T11 | **Net saving**: recovers a snapshot already paid for instead of triggering a second billed job. Two caveats: (i) it adds one free poll per handle per run *only when* an entry is pending; (ii) when it resumes, that run returns the older snapshot's rows and does **not** trigger a fresh job, so newer posts wait one interval. Entries expire after `PENDING_MAX_AGE_H = 48`. | On. |

### No billing change — extra API calls only

| # | Change | Task | Note |
|---|---|---|---|
| **C4** | Retry on `poll_status` and `fetch_results` | T4, T5 | Polling and fetching a snapshot are not per-record billed. Up to 4 attempts with 2/4/8 s backoff, only for 429/5xx/connection/timeout. Prevents *losing* an already-billed job to one transient 503. |
| **C5** | `trigger` explicitly **not** retried | T5 | The deliberate omission. A retried trigger whose first attempt reached Bright Data would start and bill a second collection job. Pinned by `test_trigger_is_never_retried_because_a_retried_trigger_double_bills`. |
| **C6** | `delete_snapshot` cleanup | T12 | One extra DELETE per successful job. Not billed per record. **Ships OFF** (`DELETE_AFTER_FETCH = False`) and is never called on the timeout path, where the snapshot is the only copy of paid-for data. |
| **C7** | Unprovisioned-dataset guard | T3 | Prevents a trigger against a placeholder dataset id. Cannot increase spend. |

### Reduces spend

| # | Change | Task | Note |
|---|---|---|---|
| **C8** | Preflight credential check | T13 | Fails the platform before the handle loop, so a missing token no longer triggers N jobs' worth of attempts (they fail before `trigger` today too, so the saving is in operator time rather than dollars — recorded for completeness). |
| **C9** | Longer poll timeout via `BRIGHTDATA_POLL_TIMEOUT_<PLATFORM>` | T15 | A longer timeout collects jobs that would otherwise be abandoned mid-flight. Strictly a saving. |

### Test safety

No test in this package reaches `api.brightdata.com`. Every test stubs `bd.requests.post` /
`bd.requests.get` / `bd.requests.delete` or the adapter's `_trigger_job` /
`_poll_job_status` / `_fetch_job_results` / `_run_collection_job`. The six module-local
autouse fixtures (T23) additionally `delenv` `BRIGHTDATA_API_KEY` and repoint `KEY_FILE` and
`PENDING_STORE_PATH` at `tmp_path`, so P7's suite is safe both with and without P0's
repo-wide guard. `PENDING_STORE_PATH` is never left pointing at
`pipeline-app/logs/brightdata-pending.json` during a test run.

---

## 7. Residuals recorded, not silently dropped

These are inside a P7 finding but outside P7's file list. They are named here so a later
verification pass does not read them as coverage gaps.

1. **B-02, per-handle cap.** A true per-handle cap needs `handle_row` threaded into
   `enumerate_newest_first` — a `PlatformAdapter` protocol change in
   `discovery_engine.py` (P8). P7 delivers the per-platform override and the saturation
   escalation; the per-handle setting is P8's to add if the operator approves C1.
2. **B-02, backfill.** `BACKFILL_SUPPORTED_PLATFORMS` (`discovery_engine.py:29`) is P8's.
   X's dataset genuinely returns `dead_page` for a date range (verified 2026-08-08), so the
   right answer for X is the saturation alarm, not a backfill path.
3. **B-01, events rows.** `drain_diagnostics()` must be called by P8's run loop and written
   with `obs.record_event`. Until that lands, the durable surface is `obs.log`'s dated file.
4. **B-25, `discovery_youtube.USER_AGENT`.** In P6's file. Unreferenced string that looks
   like it configures request identity; yt-dlp is never passed `--user-agent`.
5. **B-23, LinkedIn `view_count`.** Neither the appendix nor the LinkedIn design doc records
   a view-count field on that dataset. Nothing to map, nothing to guess. Not a gap.
6. **Instagram author/view-count field names are unverified.** T19/T20 read candidate lists
   and report the row's real keys when none matches. The next live Instagram run resolves
   them; that follow-up edit is a one-line change to `AUTHOR_FIELD_CANDIDATES` /
   `VIEW_COUNT_FIELD_CANDIDATES` and belongs to whoever reads that diagnostic.

---

## 8. Definition of done

- [ ] All 25 tasks committed, each with its test observed failing first.
- [ ] `cd pipeline-app && python -m pytest tests/test_brightdata_job.py tests/test_discovery_instagram.py tests/test_discovery_instagram_sort.py tests/test_discovery_linkedin.py tests/test_discovery_facebook.py tests/test_discovery_x.py -q` is green.
- [ ] The same six files pass under `-p no:randomly`-free reordering and under
      `python -m pytest tests/ -n auto` (F-67's real acceptance test).
- [ ] `cd pipeline-app && python -m pytest -q` is green (no regression in the other suites).
- [ ] `grep -rn "_ENUMERATE_CACHE\|\._cache\[" pipeline-app/tests/` returns nothing.
- [ ] `grep -rn "gd_REPLACE" pipeline-app/pipeline_app/discovery_instagram.py` returns nothing.
- [ ] `brightdata_job.py`'s module docstring still states the "empty ≠ failed" invariant, and
      the two tests that pin it are present.
- [ ] Every cost-note item C1–C9 has a recorded operator decision.
