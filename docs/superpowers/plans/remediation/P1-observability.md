# P1 — Observability

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` or
> `superpowers:executing-plans` to execute this plan task-by-task. Steps use checkbox (`- [ ]`)
> syntax. The **Global Constraints**, **test standard** and **Frozen interfaces** sections of
> [`../2026-08-08-audit-remediation.md`](../2026-08-08-audit-remediation.md) apply to every task
> here and are not restated.

**Wave A, package 2 of 2.** P0 must land first (conftest network guard + CI). Every Wave-B
package consumes the interfaces this package publishes, so nothing here may be redesigned once
shipped — see [§6 Published interface](#6-published-interface).

**The premise.** The audit's most systemic finding is that this codebase catches errors with care
and then tells nobody: zero bare `except:` in 8,550 lines, but no logging module, no event table,
no health endpoint and no alert path. Thirty-five stderr diagnostics on the scheduled path write
to a console Windows Task Scheduler destroys. This package builds the place a failure goes.

---

## 1. Scope

### Files owned (no other package may touch these)

```
pipeline-app/pipeline_app/schema.sql
pipeline-app/pipeline_app/db.py
pipeline-app/pipeline_app/main.py
pipeline-app/pipeline_app/obs.py            (new)
pipeline-app/pipeline_app/routes/doctor.py
pipeline-app/tests/test_main.py
pipeline-app/tests/test_db.py
pipeline-app/tests/test_obs.py              (new)
```

### Finding IDs (13)

`A-47`, `A-70`, `A-71`, `A-72`, `A-75`, `A-76`, `A-83`, `A-85`, `B-72`, `B-73`, `B-82`, `D-48`, `F-26`

### Deliberate non-scope, recorded so nobody assumes it was missed

| Thing | Why it is not here | Who owns it |
|---|---|---|
| `preflight.reconcile_orphaned_turns` internals | A-76's evidence spans `main.py` **and** `preflight.py`. `preflight.py` is not in this package's file list, so A-76 is closed by the sanctioned alternative in its own `proposed_fix`: *"move reconciliation out of `create_app` into a guarded single-instance startup step."* The guard lives in `main.py` + `schema.sql`. | P3 |
| Rejecting an unknown `platform` in `add_handle` before the billable validate spawn (B-73) | `routes/discovery.py` and `discovery_engine.py` are P8's. This package ships the storage-level `CHECK` backstop and the quarantine migration; P8 ships the friendly route-level rejection. | P8 |
| Marking a handle failing from inside a run, and rendering the counter on the handles page (B-82) | `discovery_engine.py` (P8), `discovery_handles.html` (P15). This package ships the column, the `failing` status vocabulary, and the `db.record_handle_failure()` policy function P8 calls. | P8, P15 |
| Populating `creators` / `handles.creator_id` from a manifest (B-72) | Explicitly P10's, per the orchestration plan. This package creates the tables and the join helpers. | P10 |
| `test_turn_service.py:335-343`, the second half of F-26 | Not in this file list. **Handoff to P4** — see [§5](#5-tests-deleted-or-inverted). | P4 |
| Rendering `recent_events` in `doctor.html` | P15 owns every template. This package puts the list in the context with the keys in [§6](#6-published-interface). | P15 |
| `projects.brand` CHECK constraint (mentioned in A-75's blast radius, absent from its `proposed_fix`) | The brand vocabulary is defined by `pipeline.yaml`'s `brand_scope`, which P4 owns. A DB-level `CHECK` would freeze a config vocabulary in the schema and make adding a brand a migration. Recorded as a deliberate omission, not an oversight. | — |
| A `logs/` entry in `.gitignore` | `.gitignore` is in no package's file list. `obs.log()` writes `pipeline-app/logs/app-YYYY-MM-DD.log`, which will show as untracked. **One-line handoff — see [§7](#7-handoffs).** | unassigned |

---

## 2. Finding → task map

Total coverage: 13 findings, 13 mapped, 0 unmapped.

| Finding | Severity | Failure mode | Task | What closes it |
|---|---|---|---|---|
| A-70 | S2 | silent | **T4** | `db.transaction()` + `db.commit_unless_in_transaction()`; every leaf helper's unconditional `commit()` becomes boundary-aware |
| A-72 | S2 | latent | **T5** (+ T12) | `schema_version` table, ordered once-only migration list, `SchemaVersionError` on a future DB |
| A-47 | S4 | latent | **T6** | `stages.status` `CHECK` constraint, applied to existing DBs by migration 1 |
| A-75 | S4 | latent | **T7** | FK indices on `turns.stage_row_id`, `discovery_run_handles.run_id`/`.handle_id`; `turns.status` `CHECK`; `ON DELETE` on every FK |
| A-71 | S2 | silent | **T8** | `ux_turns_single_running` partial unique index, mirroring `ux_discovery_single_running` |
| B-72 | S2 | coverage-gap | **T9** | `creators` table + `handles.creator_id` + the cross-platform join helpers |
| B-73 | S2 | silent | **T10** | `handles.platform` `CHECK` against the adapter-registry vocabulary; ghost rows quarantined, not silently dropped |
| B-82 | S2 | silent | **T11** | `handles.consecutive_failures` + `failing` status + `db.record_handle_failure()` / `db.clear_handle_failures()` |
| A-85 | S4 | latent | **T13** | FastAPI lifespan handler: `wal_checkpoint(TRUNCATE)`, lease release, `conn.close()` |
| A-76 | S3 | silent | **T14** | `app_instances` reconcile lease; a second instance skips the sweep and says so |
| A-83 | S4 | docs-drift | **T15** | One cached live CLI probe feeding both the banner and the `/doctor` panel in a single request |
| D-48 | S3 | latent | **T16** | Same-origin `Origin`/`Referer` middleware on every mutating request, with an event on rejection |
| F-26 | S2 | silent | **T18** | Both mock-echo tests in `test_main.py` replaced with real app-factory coverage |

Tasks **T1, T2, T3, T12, T17** carry no finding of their own — T1–T3 build the frozen `obs`
interface every other package consumes, T12 is the schema-drift guard that keeps T5–T11 honest,
and T17 is the `recent_events` contract P15 renders. They are load-bearing for the surfacing leg
of the Three-Test Rule throughout.

---

## 3. Tasks

Each task is one TDD cycle: write the failing test → run it → **see it fail for the right
reason** → implement → see it pass → commit. Do not batch two tasks into one commit.

---

### T1 — `obs.log()`: a diagnostic that survives the console being destroyed

- [ ] **Write the failing test.** New file `pipeline-app/tests/test_obs.py`:

```python
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pipeline_app import db, obs


def test_log_writes_a_json_line_to_a_dated_file(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    obs.log("adapter.fetch_failed", level="error", handle="@a", platform="youtube")

    files = list((tmp_path / "logs").glob("app-*.log"))
    assert len(files) == 1
    assert files[0].name.startswith("app-20")  # app-YYYY-MM-DD.log
    record = json.loads(files[0].read_text(encoding="utf-8").strip())
    assert record["event"] == "adapter.fetch_failed"
    assert record["level"] == "error"
    assert record["handle"] == "@a"
    assert record["ts"].endswith("+00:00")  # aware UTC, never naive


def test_log_also_writes_to_stderr(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    obs.log("adapter.fetch_failed", level="error")
    assert "adapter.fetch_failed" in capsys.readouterr().err


def test_log_does_not_raise_when_the_log_directory_cannot_be_created(tmp_path: Path, monkeypatch):
    """A read-only disk must not turn a reportable failure into a crash."""
    blocker = tmp_path / "logs"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(obs, "LOG_DIR", blocker)
    obs.log("adapter.fetch_failed", level="error")  # must not raise


def test_log_does_not_raise_on_an_unserializable_field(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    obs.log("adapter.fetch_failed", level="error", conn=object())  # must not raise


def test_a_caller_field_can_never_replace_the_real_timestamp(tmp_path: Path, monkeypatch):
    """`ts` is the one field that makes two log lines comparable.

    A caller passing `ts=` must not be able to replace it -- and must not have
    its value silently dropped either, or a mistaken call would be
    indistinguishable from a correct one.
    """
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    obs.log("adapter.fetch_failed", level="error", ts="1999-01-01T00:00:00+00:00", handle="@a")

    files = list((tmp_path / "logs").glob("app-*.log"))
    record = json.loads(files[0].read_text(encoding="utf-8").strip())
    assert record["ts"] != "1999-01-01T00:00:00+00:00"          # the caller did not win
    assert record["ts"].startswith(str(datetime.now(timezone.utc).year))
    assert record["field_ts"] == "1999-01-01T00:00:00+00:00"    # ...and was not silently dropped
    assert record["handle"] == "@a"                             # a non-colliding field is untouched
```

- [ ] **Run it.** `cd pipeline-app && python -m pytest tests/test_obs.py -v` → `ModuleNotFoundError: pipeline_app.obs`. That is the right failure.
- [ ] **Implement.** New file `pipeline-app/pipeline_app/obs.py`:

```python
"""Error surfacing for the pipeline app.

Two sinks, deliberately independent:

* `log()` writes a structured line to stderr AND to a dated file under
  `pipeline-app/logs/`. stderr is what a human sees interactively; the file is
  what survives Windows Task Scheduler destroying the console window, which is
  where all 35 of the scheduled path's diagnostics went before this module
  existed.
* `record_event()` appends a row to `events`, which is what makes a failure
  *findable* later: /doctor renders unacknowledged error/critical events from
  the last seven days.

Neither function ever raises. A failure to report must never mask the thing
being reported.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# pipeline-app/logs/ -- a sibling of pipeline_app/, not inside it.
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"

VALID_SEVERITIES = ("info", "warning", "error", "critical")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _merge(reserved: dict, fields: dict) -> dict:
    """Reserved keys always win; a colliding caller field is preserved, never dropped.

    `ts` is the one field that makes two log lines comparable, so a caller must
    never be able to replace it. But silently *discarding* the caller's value
    would be the same bug wearing a different hat: a mistaken call would look
    exactly like a correct one. A collision is therefore re-keyed to
    `field_<name>`, which keeps the record self-describing.

    Only `ts` can actually collide today -- `level` and `event` are named
    parameters, so passing either twice is a TypeError at the call site. All
    three are guarded anyway, so a later signature change cannot open the hole.
    """
    merged = dict(reserved)
    for key, value in fields.items():
        merged[f"field_{key}" if key in reserved else key] = value
    return merged


def log(event: str, *, level: str = "info", **fields) -> None:
    """Structured line to stderr AND to pipeline-app/logs/app-YYYY-MM-DD.log.

    `event` is a dotted kind, e.g. "adapter.fetch_failed". Never raises."""
    now = _utcnow()
    try:
        line = json.dumps(
            _merge(
                {"ts": now.isoformat(timespec="seconds"), "level": level, "event": event},
                fields,
            ),
            default=repr,
            ensure_ascii=False,
        )
    except Exception:  # noqa: BLE001 -- a field we cannot serialize must not kill the caller
        line = json.dumps({"ts": now.isoformat(timespec="seconds"), "level": level,
                           "event": event, "fields": "<unserializable>"})
    try:
        print(line, file=sys.stderr, flush=True)
    except Exception:  # noqa: BLE001 -- a detached/closed stderr must not kill the caller
        pass
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with (LOG_DIR / f"app-{now.strftime('%Y-%m-%d')}.log").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001 -- a read-only disk must not kill the caller
        pass
```

- [ ] **Run it.** All five pass.
- [ ] **Commit.** `feat(obs): add obs.log() -- a diagnostic that outlives the console`

---

### T2 — the `events` table and `obs.record_event()`

- [ ] **Write the failing test.** Append to `tests/test_obs.py`:

```python
@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


def test_record_event_appends_a_row_and_returns_its_id(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    event_id = obs.record_event(
        conn, kind="adapter.fetch_failed", severity="error", source="discovery_youtube",
        message="yt-dlp exited 1 for @a", detail={"handle": "@a", "exit_code": 1}, run_id=7,
    )
    assert event_id > 0
    row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    assert row["kind"] == "adapter.fetch_failed"
    assert row["severity"] == "error"
    assert row["source"] == "discovery_youtube"
    assert row["run_id"] == 7
    assert json.loads(row["detail"]) == {"handle": "@a", "exit_code": 1}
    assert row["acknowledged"] == 0
    assert row["occurred_at"].endswith("+00:00")


def test_events_table_rejects_a_severity_outside_the_vocabulary(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO events (occurred_at, kind, severity, source, message) "
            "VALUES ('2026-08-08T00:00:00+00:00', 'k', 'catastrophic', 's', 'm')"
        )
```

- [ ] **Run it.** Fails: `no such table: events`.
- [ ] **Implement (a).** Append to `pipeline-app/pipeline_app/schema.sql`, verbatim from the
      orchestration plan's frozen DDL:

```sql
-- The place a failure goes. Before this table the codebase caught errors
-- carefully and told nobody: 35 stderr diagnostics on the scheduled path wrote
-- to a console Windows Task Scheduler destroys.
CREATE TABLE IF NOT EXISTS events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at  TEXT    NOT NULL,
  kind         TEXT    NOT NULL,
  severity     TEXT    NOT NULL CHECK (severity IN ('info','warning','error','critical')),
  source       TEXT    NOT NULL,
  message      TEXT    NOT NULL,
  detail       TEXT,
  run_id       INTEGER,
  acknowledged INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_occurred ON events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity, occurred_at DESC);
```

- [ ] **Implement (b).** Append to `obs.py`:

```python
def record_event(conn, *, kind: str, severity: str, source: str,
                 message: str, detail: dict | None = None,
                 run_id: int | None = None) -> int:
    """Append one row to the `events` table and return its id.

    severity in {"info","warning","error","critical"}. Never raises -- a
    failure to record must not mask the thing being recorded; it falls back to
    log() and returns -1."""
    try:
        if severity not in VALID_SEVERITIES:
            raise ValueError(f"unknown severity {severity!r}")
        detail_json = (
            json.dumps(detail, default=repr, ensure_ascii=False) if detail is not None else None
        )
        cur = conn.execute(
            "INSERT INTO events (occurred_at, kind, severity, source, message, detail, run_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_utcnow().isoformat(timespec="seconds"), kind, severity, source, message,
             detail_json, run_id),
        )
        # Deferred import: db imports obs for its own migration diagnostics, so a
        # module-level import here would be circular. The indirection exists so an
        # event recorded inside a db.transaction() block does not commit the
        # caller's half-finished work (A-70) -- the whole defect this package fixes.
        from pipeline_app.db import commit_unless_in_transaction

        commit_unless_in_transaction(conn)
        event_id = int(cur.lastrowid)
    except Exception as exc:  # noqa: BLE001 -- recording must never mask the recorded
        log("obs.record_event_failed", level="error", kind=kind, severity=severity,
            source=source, message=message, error=f"{type(exc).__name__}: {exc}")
        return -1
    log(kind, level=severity, source=source, message=message, event_id=event_id, run_id=run_id)
    return event_id
```

> `commit_unless_in_transaction` does not exist until T4. Land T2 with a plain `conn.commit()`
> and swap it in T4's edit — or land T4 first. Either order works; do not ship both halves in
> one commit.

- [ ] **Run it.** Both pass.
- [ ] **Commit.** `feat(obs): add the events table and obs.record_event()`

---

### T3 — `record_event` never raises (the frozen contract every package leans on)

This is the single most important behavioural guarantee in the package: if recording a failure
could itself fail, every adopting call site in the other fifteen packages would need a try/except
around its own error reporting.

- [ ] **Write the failing test.** Append to `tests/test_obs.py`:

```python
def test_record_event_returns_minus_one_when_the_events_table_is_missing(tmp_path, monkeypatch):
    """An operator database that predates the events table must not turn every
    reported failure into a second, uncaught failure."""
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    bare = sqlite3.connect(tmp_path / "bare.db")
    try:
        assert obs.record_event(bare, kind="k", severity="error", source="s", message="m") == -1
    finally:
        bare.close()


def test_record_event_falls_back_to_the_log_when_it_cannot_write(tmp_path, monkeypatch):
    """Returning -1 silently would recreate the exact defect this module exists
    to fix. The fallback has to leave a trace."""
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    bare = sqlite3.connect(tmp_path / "bare.db")
    try:
        obs.record_event(bare, kind="adapter.fetch_failed", severity="error",
                         source="discovery_youtube", message="yt-dlp exited 1")
    finally:
        bare.close()
    written = (tmp_path / "logs").glob("app-*.log")
    text = "\n".join(p.read_text(encoding="utf-8") for p in written)
    assert "obs.record_event_failed" in text
    assert "yt-dlp exited 1" in text  # the recorded thing is not lost


def test_record_event_rejects_an_unknown_severity_without_raising(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    assert obs.record_event(conn, kind="k", severity="catastrophic",
                            source="s", message="m") == -1
    assert conn.execute("SELECT count(*) FROM events").fetchone()[0] == 0


def test_record_event_does_not_raise_on_a_closed_connection(tmp_path, monkeypatch):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    closed = sqlite3.connect(tmp_path / "closed.db")
    closed.close()
    assert obs.record_event(closed, kind="k", severity="error", source="s", message="m") == -1
```

- [ ] **Run it.** T2's implementation already exists, so these four tests would otherwise pass on
      first write and prove nothing. Each needs a scaffold that makes it genuinely red, and **no
      single scaffold reds all four** — use both, one at a time, restoring `obs.py` after each.
      Never commit a scaffold.
    - **Scaffold A** — narrow the blanket guard to `except sqlite3.OperationalError`.
      `test_record_event_rejects_an_unknown_severity_without_raising` (`ValueError`) and
      `test_record_event_does_not_raise_on_a_closed_connection` (`sqlite3.ProgrammingError`) fail:
      the exception escapes instead of becoming a logged `-1`. The other two still **pass**, because
      a missing table raises `OperationalError`, which the narrowed guard still catches.
    - **Scaffold B** — delete the `log("obs.record_event_failed", ...)` call from the except branch,
      leaving the bare `return -1`. `test_record_event_falls_back_to_the_log_when_it_cannot_write`
      fails. This is the scaffold that matters most: that test is the one guarding against a silent
      `-1`, which would recreate the exact defect this module exists to fix, so it must be observed
      discriminating rather than assumed to.
    - **Scaffold C** — narrow the guard to `except (ValueError, sqlite3.ProgrammingError):`,
      deliberately excluding `OperationalError`.
      `test_record_event_returns_minus_one_when_the_events_table_is_missing` fails, as does the
      fallback-log test; 3 and 4 stay green. This is the only scaffold that reds test 1, and it is
      **required** — the rule that a test passing on first write proves nothing has no carve-out,
      and "the guard is one blanket `except Exception`, so it must work" is analysis, not the
      observed evidence every other test in this suite has.
- [ ] **Implement.** Already written in T2. If any test fails, widen the guard — never narrow the
      test.
- [ ] **Commit.** `test(obs): prove record_event never raises and never loses the record`

---

### T4 — A-70: one transaction boundary per logical operation

**A-70 (S2, silent).** Every helper in `db.py` commits immediately after its single statement, so
the app has no transaction boundary anywhere. `create_project` commits the project row, then each
stage row, then each directory; `_backfill_one_project` inserts an `approved` styleboard row and
*then* sets `approved_at`, so an interruption yields `status='approved', approved_at=NULL`. One
thread's `commit()` also finalizes another thread's in-flight statements on the shared connection.

The compatibility rule: **outside a `transaction()` block, every helper behaves exactly as it does
today.** Fourteen other packages' tests depend on that.

- [ ] **Write the failing test.** Append to `tests/test_db.py`:

```python
def test_transaction_rolls_back_every_statement_in_the_block(conn):
    """FAULT. A multi-row operation that fails partway leaves nothing behind."""
    with pytest.raises(RuntimeError):
        with db.transaction(conn):
            project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
            db.create_stage_row(conn, project_id, "ideation", "ready")
            raise RuntimeError("mkdir failed halfway through create_project")
    assert db.list_projects(conn) == []
    assert conn.execute("SELECT count(*) FROM stages").fetchone()[0] == 0


def test_a_failed_transaction_is_distinguishable_from_the_unwrapped_path(conn):
    """DISTINGUISHABILITY. Without the boundary the same failure leaves a
    half-written project behind -- which is A-70 exactly. The two paths must not
    produce the same database."""
    def half_a_project(wrapped: bool) -> int:
        try:
            if wrapped:
                with db.transaction(conn):
                    db.create_project(conn, "wrapped", "a", "generic", "2026-08-08T00:00:00+00:00")
                    raise RuntimeError("boom")
            else:
                db.create_project(conn, "unwrapped", "a", "generic", "2026-08-08T00:00:00+00:00")
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        return len(db.list_projects(conn))

    assert half_a_project(wrapped=False) == 1      # today's behaviour, preserved
    assert half_a_project(wrapped=True) == 1       # still 1 -- the wrapped one rolled back
    assert [r["run_id"] for r in db.list_projects(conn)] == ["unwrapped"]


def test_a_rolled_back_transaction_records_an_error_event(conn, tmp_path, monkeypatch):
    """SURFACING. A silently discarded half-operation is how A-70 stayed
    invisible; the rollback has to leave a row a human can find -- and it has to
    still be there once this connection is gone.

    Read it back on a SECOND connection. Reading it on the connection that wrote
    it passes whether or not the row was ever committed, so that version of this
    test cannot tell a durable event from one that dies with the process."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    with pytest.raises(RuntimeError):
        with db.transaction(conn):
            db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
            raise RuntimeError("boom")

    other = db.get_connection(Path(conn.execute("PRAGMA database_list").fetchone()[2]))
    try:
        rows = other.execute(
            "SELECT * FROM events WHERE kind = 'db.transaction_rolled_back'"
        ).fetchall()
    finally:
        other.close()
    assert len(rows) == 1
    assert rows[0]["severity"] == "error"
    assert "RuntimeError" in rows[0]["message"]
    assert db.list_projects(conn) == []  # ...and the half-written project is still gone


def test_recording_an_event_inside_a_transaction_does_not_commit_the_caller(
    conn, tmp_path, monkeypatch
):
    """`record_event` is called from inside operations that are failing. If it
    committed, it would persist the half-finished work the boundary exists to
    discard -- A-70 defeated by the very module built to report it."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    with pytest.raises(RuntimeError):
        with db.transaction(conn):
            db.create_project(conn, "half", "a", "generic", "2026-08-08T00:00:00+00:00")
            obs.record_event(conn, kind="k", severity="warning", source="s", message="mid-flight")
            raise RuntimeError("boom")

    assert db.list_projects(conn) == []  # the half project did NOT survive
    # That event row rolled back with everything else -- correct, but it must not
    # be the only trace. `record_event` logs unconditionally, so the file survives.
    text = "\n".join(
        p.read_text(encoding="utf-8") for p in (tmp_path / "logs").glob("app-*.log")
    )
    assert "mid-flight" in text


def test_leaf_helpers_still_commit_immediately_outside_a_transaction(conn, tmp_path):
    """Fourteen other packages' tests depend on this. A second connection to the
    same file must see the row without any explicit boundary."""
    db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    other = db.get_connection(Path(conn.execute("PRAGMA database_list").fetchone()[2]))
    try:
        assert len(db.list_projects(other)) == 1
    finally:
        other.close()


def test_a_nested_transaction_joins_the_outer_one(conn):
    with db.transaction(conn):
        db.create_project(conn, "outer", "a", "generic", "2026-08-08T00:00:00+00:00")
        with db.transaction(conn):
            db.create_project(conn, "inner", "b", "generic", "2026-08-08T00:00:00+00:00")
        assert len(db.list_projects(conn)) == 2  # inner did not commit on its own
    assert len(db.list_projects(conn)) == 2


def test_a_swallowed_inner_failure_still_rolls_the_outer_transaction_back(conn):
    """A poisoned transaction must not be committable. Without this, an outer
    block that catches its inner block's exception commits half a cascade --
    the same defect one level up."""
    with pytest.raises(db.TransactionPoisonedError):
        with db.transaction(conn):
            db.create_project(conn, "outer", "a", "generic", "2026-08-08T00:00:00+00:00")
            try:
                with db.transaction(conn):
                    db.create_project(conn, "inner", "b", "generic", "2026-08-08T00:00:00+00:00")
                    raise RuntimeError("boom")
            except RuntimeError:
                pass
    assert db.list_projects(conn) == []


def _db_path(conn) -> Path:
    return Path(conn.execute("PRAGMA database_list").fetchone()[2])


class _FlakyCommit:
    """A connection whose first `commit()` fails.

    A wrapper rather than a monkeypatch because `sqlite3.Connection` is a C type
    and does not accept attribute assignment. Everything else proxies through, so
    `id()` keying still works as long as the wrapper is what gets passed around."""

    def __init__(self, real):
        self._real = real
        self._failed = False

    def commit(self):
        if not self._failed:
            self._failed = True
            raise sqlite3.OperationalError("database is locked")
        return self._real.commit()

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_an_inner_block_unwinding_after_its_outer_one_does_not_strand_the_connection(
    conn, tmp_path, monkeypatch
):
    """A depth entry re-created after the outer block popped it is permanent and
    totally silent: every later commit becomes a no-op and the connection stops
    persisting anything, with no exception, no log line and no events row."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")

    outer, inner = db.transaction(conn), db.transaction(conn)
    outer.__enter__()
    inner.__enter__()
    outer.__exit__(None, None, None)   # the outer block unwinds first...
    inner.__exit__(None, None, None)   # ...and the inner one second

    db.create_project(conn, "after", "a", "generic", "2026-08-08T00:00:00+00:00")
    other = db.get_connection(_db_path(conn))
    try:
        assert len(db.list_projects(other)) == 1  # the connection still commits
    finally:
        other.close()

    text = "\n".join(p.read_text(encoding="utf-8") for p in (tmp_path / "logs").glob("app-*.log"))
    assert "db.transaction_bookkeeping_lost" in text  # ...and said so, rather than absorbing it


def test_a_poisoned_transaction_names_the_original_failure(conn, tmp_path, monkeypatch):
    """The synthetic TransactionPoisonedError is the only thing left to report, so
    if it does not carry the real fault, nothing does -- not `events`, not the log,
    not a traceback."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")

    with pytest.raises(db.TransactionPoisonedError) as caught:
        with db.transaction(conn):
            try:
                with db.transaction(conn):
                    raise RuntimeError("the stage row insert failed")
            except RuntimeError:
                pass

    assert "the stage row insert failed" in str(caught.value)
    assert isinstance(caught.value.__cause__, RuntimeError)

    other = db.get_connection(_db_path(conn))
    try:
        row = other.execute(
            "SELECT * FROM events WHERE kind = 'db.transaction_rolled_back'"
        ).fetchone()
    finally:
        other.close()
    detail = json.loads(row["detail"])
    assert detail["original_exception"] == "RuntimeError"
    assert "the stage row insert failed" in detail["original_message"]


def test_a_failing_boundary_commit_does_not_leave_the_work_for_the_next_caller(
    conn, tmp_path, monkeypatch
):
    """If the boundary's own commit raises and the statements are left pending, the
    next unrelated helper's commit persists them -- the caller was told the
    operation failed and the data landed anyway."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")

    flaky = _FlakyCommit(conn)
    with pytest.raises(sqlite3.OperationalError):
        with db.transaction(flaky):
            db.create_project(flaky, "doomed", "a", "generic", "2026-08-08T00:00:00+00:00")

    db.create_project(conn, "later", "b", "generic", "2026-08-08T00:00:00+00:00")
    other = db.get_connection(_db_path(conn))
    try:
        assert [r["run_id"] for r in db.list_projects(other)] == ["later"]
        # The defect was "no rollback AND no event". Assert both halves: a boundary
        # that discards work without saying so is the failure mode this package
        # exists to remove, and it is the half a passing rollback assertion hides.
        rows = other.execute(
            "SELECT * FROM events WHERE kind = 'db.transaction_rolled_back'"
        ).fetchall()
        assert len(rows) == 1
        assert "OperationalError" in rows[0]["message"]
    finally:
        other.close()
```

- [ ] **Run it.** `AttributeError: module 'pipeline_app.db' has no attribute 'transaction'`.
- [ ] **Implement (a).** Add to the top of `db.py`:

```python
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path


class TransactionPoisonedError(RuntimeError):
    """An inner transaction failed and its exception was swallowed.

    Committing the outer block would persist half a cascade -- exactly the
    defect `transaction()` exists to prevent -- so the boundary rolls back and
    raises this instead of silently succeeding."""


# Keyed by connection identity, deliberately NOT by thread: the app shares one
# connection between the threadpool routes and the event-loop chat route
# (get_connection's check_same_thread=False), so a transaction is a property of
# the connection, not of whoever happens to be running. The key is only present
# while `transaction()` holds a strong reference to the connection, so id reuse
# cannot collide.
_TXN_DEPTH: dict[int, int] = {}
# Maps a poisoned connection to the FIRST exception that poisoned it -- a set
# would record only that something failed, never what, which is the difference
# between an events row a human can act on and one that just says "a thing broke".
_TXN_POISON: dict[int, BaseException] = {}
_TXN_LOCK = threading.Lock()


def commit_unless_in_transaction(conn: sqlite3.Connection) -> None:
    """What every leaf helper in this module calls instead of `conn.commit()`.

    Outside a `transaction()` block it commits immediately, byte-for-byte the
    behaviour every existing caller already depends on. Inside one it is a
    no-op, so the boundary owns the commit and a multi-row invariant is atomic
    for the first time (A-70)."""
    with _TXN_LOCK:
        in_txn = _TXN_DEPTH.get(id(conn), 0) > 0
    if not in_txn:
        conn.commit()


@contextmanager
def transaction(conn: sqlite3.Connection):
    """One explicit boundary around a multi-row invariant.

    Wrap project creation, approval + unlock, the staleness cascade and each
    per-project backfill in this (T4b does exactly that). Nests: an inner block
    joins the outer one rather than committing early.

    **Known hazard, deliberately not solved here.** The boundary is a property of
    the *connection*, and this app shares one connection across threads
    (`get_connection`'s `check_same_thread=False`). So a leaf helper called from a
    thread that is in no boundary at all still stops committing while *another*
    thread holds one, and its write is discarded outright if that boundary rolls
    back. There are two known sharers, and the first is in-process:

    * **The streaming turn route.** `approve_stage_route` and `create_project_route`
      are sync `def` routes, so Starlette runs them in the threadpool, and T4b has
      both open a boundary on `app.state.conn`. The turn route's async generator
      writes to that same connection from the event-loop thread for the whole life
      of a streaming turn, and `any_turn_running` gates only the run-turn route --
      so approving stage Y while a turn streams on stage X is a supported path.
      Inside the boundary those turn writes stop committing and are discarded by the
      rollback, and the events row attributes nothing to the collateral write.
      Project creation holds its boundary across `mkdir` calls, which widens the
      window.
    * **The discovery heartbeat.** `_open_heartbeat_connection` returns `None` on any
      `sqlite3.Error` and falls back to the shared connection; under a rolled-back
      boundary the heartbeat write vanishes, `heartbeat_at` freezes, and another
      process reclaims a run that is still alive. It runs in the separate cron
      process, so it collides only when discovery runs in-process.

    Neither is solved here, and do not widen the boundary to be thread-local -- that
    would break the single-connection design this app depends on. **T13b owns the
    decision**; making the discovery fallback loud belongs to the discovery
    package.

    **This boundary does not cover DDL.** Python's sqlite3 opens an implicit
    transaction only for DML, so a CREATE/ALTER/DROP inside a `transaction()` block
    executes in autocommit mode and survives the rollback. Nothing at runtime issues
    DDL -- only migrations do, and `apply_migrations` issues its own explicit
    `BEGIN` for exactly this reason. Do not reach for `transaction()` to make schema
    changes atomic."""
    key = id(conn)
    with _TXN_LOCK:
        depth = _TXN_DEPTH.get(key, 0)
        _TXN_DEPTH[key] = depth + 1
    outermost = depth == 0
    try:
        yield conn
    except BaseException as exc:
        with _TXN_LOCK:
            _TXN_POISON.setdefault(key, exc)
        if outermost:
            _rollback_and_report(conn, exc)
        raise
    else:
        with _TXN_LOCK:
            original = _TXN_POISON.get(key)
        if outermost and original is not None:
            exc = TransactionPoisonedError(
                "an inner transaction failed and its exception was swallowed: "
                f"{type(original).__name__}: {original}"
            )
            # The inner block was not outermost, so _rollback_and_report never ran
            # for it, and the caller swallowed the exception by definition of this
            # path. Without chaining, the ONLY record of what actually failed --
            # which statement in the cascade, and why -- exists nowhere: not in
            # `events`, not in the log, not in a traceback.
            exc.__cause__ = original
            _rollback_and_report(conn, exc, original=original)
            raise exc
        if outermost:
            try:
                conn.commit()
            except BaseException as commit_exc:
                # Without this the block's statements stay pending in an open
                # transaction with no rollback and no event, the finally pops the
                # depth, and the NEXT unrelated leaf helper commits this failed
                # block's work. The caller was told the operation failed and the
                # data landed anyway -- A-70 with extra steps.
                _rollback_and_report(conn, commit_exc)
                raise
    finally:
        with _TXN_LOCK:
            remaining = _TXN_DEPTH.get(key, 1) - 1
            # Decrement, never restore the entry depth. Restoring an absolute value
            # RE-CREATES the key if the outermost block already popped it -- which
            # happens whenever two threads hold boundaries on this shared connection
            # and unwind out of order, or a suspended generator's inner block is
            # closed by GC after the outer one finished. The phantom key is
            # permanent and totally silent: every later commit_unless_in_transaction
            # sees depth > 0 and does nothing, so that connection stops committing
            # forever, with no exception, no log line and no events row.
            lost = not outermost and key not in _TXN_DEPTH
            if outermost or remaining <= 0:
                _TXN_DEPTH.pop(key, None)
                _TXN_POISON.pop(key, None)
            else:
                _TXN_DEPTH[key] = remaining
        if lost:
            # Never silently. Reaching here means the bookkeeping was already gone
            # when an inner block exited -- the anomaly above, caught rather than
            # absorbed. Inside the `finally` so it fires while an exception is
            # propagating too, but OUTSIDE the lock: obs.log() touches the
            # filesystem, and it never raises, so it cannot mask the original.
            from pipeline_app import obs

            obs.log("db.transaction_bookkeeping_lost", level="warning",
                    note="an inner transaction exited after its outer block unwound")


def _rollback_and_report(conn: sqlite3.Connection, exc: BaseException,
                         *, original: BaseException | None = None) -> None:
    """`original` is the underlying failure when `exc` is a synthetic wrapper.

    On the poison path `exc` is a TransactionPoisonedError this module just
    built, so recording only `exc` would produce an events row that says a
    transaction was poisoned and nothing whatsoever about the fault -- the one
    thing an operator actually needs."""
    from pipeline_app import obs

    try:
        conn.rollback()
    except Exception as rollback_exc:  # noqa: BLE001 -- report it, never mask the original
        obs.log("db.rollback_failed", level="critical",
                error=f"{type(rollback_exc).__name__}: {rollback_exc}")
    detail = {"exception": type(exc).__name__}
    if original is not None:
        detail["original_exception"] = type(original).__name__
        detail["original_message"] = str(original)
    obs.record_event(
        conn, kind="db.transaction_rolled_back", severity="error", source="db.transaction",
        message=f"rolled back after {type(exc).__name__}: {exc}",
        detail=detail,
    )
    # Commit the event row explicitly. We are still nominally inside this
    # transaction -- `transaction()`'s finally has not popped the depth key yet --
    # so `record_event`'s `commit_unless_in_transaction` is a no-op here. The
    # rollback above already discarded the caller's work, so this row is the only
    # statement pending; committing it cannot resurrect anything.
    #
    # Without this the sole durable trace of the rollback dies with the
    # connection: verified empirically on sqlite3 with the default
    # isolation_level -- the row is visible on THIS connection, invisible to any
    # other, and gone entirely after close(). A surfacing mechanism that only the
    # failing process can see is the exact defect this package exists to remove.
    try:
        conn.commit()
    except Exception as commit_exc:  # noqa: BLE001 -- a lost event must not mask the original
        obs.log("db.rollback_event_commit_failed", level="critical",
                error=f"{type(commit_exc).__name__}: {commit_exc}")
```

- [ ] **Implement (b).** Replace every one of the ~20 bare `conn.commit()` calls in `db.py`'s
      helpers with `commit_unless_in_transaction(conn)`. Leave `init_db`'s own `conn.commit()`
      alone — it owns a short-lived private connection and is never inside a caller's boundary.
      Verify with `grep -n "conn.commit()" pipeline_app/db.py` — the only survivor is `init_db`'s.
- [ ] **Implement (c).** Redeem T2's deferred half: in `obs.py`, replace `record_event`'s plain
      `conn.commit()` with the deferred import of `commit_unless_in_transaction` and a call to it,
      exactly as T2's code block shows. The import must stay inside the function — `db` imports
      `obs` for its own diagnostics, so a module-level import here is circular. This is what stops
      an event recorded *inside* a caller's `transaction()` block from committing that caller's
      half-finished work, which would defeat A-70 through the very module meant to report it.
      The explicit `conn.commit()` in `_rollback_and_report` above is the one deliberate exception
      and must remain.
- [ ] **Run it.** All ten pass (`tests/test_db.py` needs `import json` added). Then run the whole app suite: `cd pipeline-app && python -m pytest -q`.
      **Zero existing tests may change behaviour.** If any fails, the compatibility rule was broken.
- [ ] **Commit.** `fix(db): give every multi-row invariant a transaction boundary (A-70)`

---

### T4b — wire the boundary into the four multi-row invariants (A-70, the other half)

T4 builds the machinery. **Nothing in the entire sixteen-package programme ever calls it** —
verified by `grep -rn "db.transaction(" docs/superpowers/plans/remediation/`, which matches only
P1's own test code. Shipping T4 alone leaves A-70's actual failure mode completely intact: a
half-written project that looks real. `transaction()`'s own docstring names the four call sites
that need it; this task is executing that sentence.

The four, located by `grep -rn "create_project(\|_backfill_one_project\|reclaim_stale_runs" --include=*.py`:

| Invariant | Site | What is currently non-atomic |
|---|---|---|
| Project creation | `pipeline_app/project_service.py:23` `create_project` | project row, then each stage row, then each directory |
| Approval + unlock | `pipeline_app/approval_service.py:11` `approve_stage` | the approval and the unlock of the next stage |
| Per-project backfill | `pipeline_app/migrations.py:85` `_backfill_one_project` | inserts an `approved` styleboard row, *then* sets `approved_at` — an interruption yields `status='approved', approved_at=NULL`, A-70's worked example |
| Staleness cascade | `pipeline_app/discovery_engine.py:299` `reclaim_stale_runs` call | reclaims N runs, committing each |

- [ ] **Write the failing test.** For each of the four, a test that interrupts the operation partway
      and asserts **nothing** was left behind. Model them on T4's
      `test_transaction_rolls_back_every_statement_in_the_block`: force the failure by
      monkeypatching the *second* step of the invariant to raise, then assert the first step's row
      is absent. Name them
      `test_<operation>_leaves_nothing_behind_when_it_fails_partway`.
      Each must be observed failing **before** the wrapping is added — that failure *is* A-70, and
      it is the only direct evidence in the programme that the finding was ever real.
- [ ] **Close the other two legs of the Three-Test Rule at a call site.** A-70 is `silent`, and the
      four tests above are all *fault* tests. At three of the four sites the rolled-back state is
      byte-identical to "the operation never ran" — no project row, no styleboard row, run still
      `running` — so on their own they prove a rollback happened without proving anyone could ever
      tell. T4's `test_a_rolled_back_transaction_records_an_error_event` proves the events row for
      `transaction()` itself, but nothing ties a *call site* to it. Extend the project-creation test:
    - **Surfacing** — after the rollback, assert an `events` row of kind `db.transaction_rolled_back`
      exists. Read it on a **second connection**, as T4's version does; reading it on the connection
      that wrote it passes whether or not it was ever committed.
    - **Distinguishability** — assert the failed-creation state differs observably from the
      legitimate-empty state. Creating no project at all yields zero projects and **zero** such
      events rows; a failed creation yields zero projects and **one**. That difference is the whole
      finding: without it, "nothing was created" and "creation blew up halfway" are the same
      database.
- [ ] **Implement.** Wrap each operation's body in `with db_mod.transaction(conn):`. **Wrap only.**
      These four files are touched by other packages (P2, P3, P4); do not restructure, rename or
      re-order anything inside them, and do not change a signature. If an operation already returns
      early on a failure path, the boundary must still cover every write.
- [ ] **Run it.** The four new tests pass. Then the whole app suite: `cd pipeline-app && python -m pytest -q`.
      **Zero existing tests may change behaviour** — outside a boundary nothing moved, and inside
      one the only difference is *when* the commit happens.
- [ ] **Commit.** `fix(db): wrap the four multi-row invariants in a transaction boundary (A-70)`

---

### T5 — A-72: schema versioning and an ordered, once-only migration list

**A-72 (S2, latent).** There is no `schema_version` table, no version stamp and no `ALTER TABLE`
path: the entire strategy is re-running `schema.sql` on every boot, and every statement in it is
`IF NOT EXISTS`. On a database that already has the table, a newly added column, `CHECK` or
`UNIQUE` is silently skipped — `init_db` reports success and the first query touching it fails at
runtime with `no such column` in whatever route happens to hit it first. T6–T11 all add exactly
such constraints, so this task must land before any of them.

- [ ] **Write the failing test.** Append to `tests/test_db.py`:

```python
LEGACY_SCHEMA_V0 = """
CREATE TABLE projects (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL UNIQUE,
  slug TEXT NOT NULL, brand TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE stages (id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id), stage_id TEXT NOT NULL,
  status TEXT NOT NULL, claude_session_id TEXT, approved_at TEXT,
  UNIQUE(project_id, stage_id));
CREATE TABLE turns (id INTEGER PRIMARY KEY AUTOINCREMENT,
  stage_row_id INTEGER NOT NULL REFERENCES stages(id), status TEXT NOT NULL,
  created_at TEXT NOT NULL, finished_at TEXT, events_path TEXT NOT NULL, cost_usd REAL);
CREATE TABLE handles (id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT NOT NULL,
  handle TEXT NOT NULL, display_name TEXT, cohort TEXT NOT NULL, keyword_filter TEXT,
  included INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'pending',
  added_at TEXT NOT NULL, validated_at TEXT, last_seen_published_at TEXT,
  UNIQUE(platform, handle));
"""
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"


def _legacy_db(tmp_path: Path) -> Path:
    """A database written by the build that predates every constraint in this
    package -- the operator's real pipeline.db."""
    db_path = tmp_path / "pipeline.db"
    c = sqlite3.connect(db_path)
    c.executescript(LEGACY_SCHEMA_V0)
    c.commit()
    c.close()
    return db_path


def test_a_fresh_database_is_stamped_at_the_current_schema_version(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    c = db.get_connection(db_path)
    try:
        assert c.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0] \
            == db.SCHEMA_VERSION
    finally:
        c.close()


def test_an_existing_database_is_migrated_not_silently_left_behind(tmp_path: Path):
    """This is A-72: `CREATE TABLE IF NOT EXISTS` skips the new constraint and
    init_db reports success anyway."""
    db_path = _legacy_db(tmp_path)
    db.init_db(db_path, SCHEMA_PATH)
    c = db.get_connection(db_path)
    try:
        assert c.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0] \
            == db.SCHEMA_VERSION
        ddl = c.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='handles'"
        ).fetchone()[0]
        assert "CHECK" in ddl  # the constraint actually landed on the existing table
    finally:
        c.close()


def test_migrations_are_applied_exactly_once(tmp_path: Path):
    db_path = _legacy_db(tmp_path)
    db.init_db(db_path, SCHEMA_PATH)
    db.init_db(db_path, SCHEMA_PATH)  # a second boot must be a no-op, not a re-run
    c = db.get_connection(db_path)
    try:
        assert c.execute("SELECT count(*) FROM schema_version").fetchone()[0] == 1
        assert c.execute("SELECT version FROM schema_version").fetchone()[0] == db.SCHEMA_VERSION
    finally:
        c.close()


def test_a_database_from_a_newer_build_fails_loudly_instead_of_booting(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    c = db.get_connection(db_path)
    c.execute("UPDATE schema_version SET version = ? WHERE id = 1", (db.SCHEMA_VERSION + 5,))
    c.commit()
    c.close()
    with pytest.raises(db.SchemaVersionError):
        db.init_db(db_path, SCHEMA_PATH)
```

- [ ] **Run it.** Fails: `no such table: schema_version`.
- [ ] **Implement (a).** Prepend to `schema.sql`:

```sql
-- Schema versioning exists because everything below is `IF NOT EXISTS`: on a
-- database that already has a table, a newly added column, CHECK or UNIQUE is
-- silently skipped and the first query touching it fails at runtime with
-- `no such column` in whatever route happens to hit it first (A-72). This file
-- is the create-from-scratch path; db._MIGRATIONS is the upgrade path. They are
-- two hand-maintained definitions of one schema, and nothing enforces that they
-- agree until T12 adds test_a_migrated_database_has_the_same_schema_as_a_fresh_one.
-- Until then, a change here needs a matching migration by hand.
CREATE TABLE IF NOT EXISTS schema_version (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);
```

- [ ] **Implement (b).** In `db.py`:

```python
SCHEMA_VERSION = 1


class SchemaVersionError(RuntimeError):
    """The database was written by a build newer than this code understands."""


class StrandedPoisonError(RuntimeError):
    """The connection carries a transaction poison that predates this call.

    Distinct from NestedMigrationError: this is neither a transaction nor a
    boundary, so telling the caller to close its boundary would name something that
    does not exist. _exit_migration_boundary's own comment explains how a poison
    entry can survive onto a REUSED connection id."""


class NestedMigrationError(RuntimeError):
    """apply_migrations was called on a connection already inside a transaction.

    A dedicated type, not a bare RuntimeError: the migration tests raise
    RuntimeError from their own migration bodies, so a bare one here would let a
    precondition failure masquerade as the migration failure under test."""


_MIGRATIONS: list[tuple[int, "Callable[[sqlite3.Connection], None]"]] = [
    # (1, _migration_1_constrain_core_tables) -- registered in T6.
    #
    # A migration body must not call conn.commit(), conn.rollback(), or any db.py
    # leaf helper that would. apply_migrations registers its boundary in
    # _TXN_DEPTH so the helpers no-op, but a raw commit still ends the
    # transaction and un-does the atomicity guarantee.
    #
    # It must not open a db.transaction() either. That boundary cannot help --
    # it does not cover DDL -- and inside a migration it is non-outermost, so it
    # leaves a _TXN_POISON entry behind on the connection's id.
    #
    # And it must not call conn.executescript(): that issues an implicit COMMIT
    # before running, which destroys apply_migrations' boundary silently. It is
    # the natural idiom for SQLite's create-copy-drop-rename recipe and is
    # already used elsewhere in this module, so this is the easiest of these
    # three mistakes to make. Use separate conn.execute() calls.
]


def _validate_migration_order(migrations) -> None:
    """Fail at import rather than wedge a database at runtime.

    apply_migrations walks this list as written and skips anything already
    applied, so an out-of-order entry runs late and stamps the version BACKWARDS:
    with [(2, m2), (1, m1)] on a v0 database, m2 runs and stamps 2, then m1 runs
    and stamps 1. Migration 2 has run but the database claims it has not, so the
    next boot re-runs it, hits `duplicate column name`, and is stuck at a version
    that is neither true nor recoverable. A duplicate version does the same."""
    versions = [version for version, _ in migrations]
    if versions != sorted(set(versions)):
        raise RuntimeError(
            f"_MIGRATIONS must be strictly increasing with no duplicates, got {versions}"
        )


_validate_migration_order(_MIGRATIONS)


def _enter_migration_boundary(conn: sqlite3.Connection) -> None:
    """Make db.py's own leaf helpers no-op inside a migration.

    `apply_migrations` opens its boundary with a raw `BEGIN IMMEDIATE`, because
    `transaction()` relies on implicit transaction control and so cannot cover DDL.
    But `commit_unless_in_transaction` decides "am I inside a boundary?" by
    consulting `_TXN_DEPTH`, which only `transaction()` populates -- so without this
    registration a migration body calling ANY db.py helper commits mid-migration,
    the later rollback rolls back nothing, and half-applied is indistinguishable
    from never-ran again. Not hypothetical: SQLite's only recipe for adding a CHECK
    is create-copy-drop-rename, and the copy step is exactly the data movement an
    author would route through an existing helper.

    apply_migrations refuses a connection that already carries poison, and
    _exit_migration_boundary pops it whenever the depth reaches zero. A body that
    leaks a depth increment defeats both, and with several migrations registered the
    next one would then be refused for its predecessor's swallowed failure -- which
    is loud and wrong rather than silent and wrong, but still worth knowing."""
    with _TXN_LOCK:
        _TXN_DEPTH[id(conn)] = _TXN_DEPTH.get(id(conn), 0) + 1


def _exit_migration_boundary(conn: sqlite3.Connection) -> None:
    """Release the boundary. Cleanup only -- the poison check happens in
    `apply_migrations` before the stamp and the commit, which is the last moment
    refusing is still possible."""
    key = id(conn)
    with _TXN_LOCK:
        # A missing key is NOT a normal exit. `.get(key, 1) - 1` yields 0 either way,
        # so without this flag "healthy decrement from 1" and "my boundary was
        # clobbered" are the same silent return -- and the second means every leaf
        # helper in the migration body committed with no boundary at all, which is
        # exactly the defect this registration exists to prevent. transaction()
        # fixed this class once and kept its detector; copying its arithmetic
        # without its detector re-introduced it.
        lost = key not in _TXN_DEPTH
        remaining = _TXN_DEPTH.get(key, 1) - 1
        if remaining <= 0:
            _TXN_DEPTH.pop(key, None)
            # Pop the poison too, or it outlives this connection. A db.transaction()
            # opened inside a migration body is non-outermost (this boundary already
            # holds depth 1), so its finally takes the nested branch and leaves
            # _TXN_POISON[key] behind. init_db then closes its connection and the app
            # allocates a new one immediately after -- CPython reuses the freed
            # address readily -- so the first SUCCESSFUL outermost transaction() on
            # the app's real connection would roll back correct work and raise
            # TransactionPoisonedError citing a boot-time migration failure.
            _TXN_POISON.pop(key, None)
        else:
            _TXN_DEPTH[key] = remaining
    if lost:
        # Logged outside the lock: obs.log() touches the filesystem, and it never
        # raises, so it cannot mask whatever else is going wrong.
        from pipeline_app import obs

        obs.log("db.migration_bookkeeping_lost", level="error",
                note="the migration boundary was gone before the migration finished")


def _schema_cookie(conn: sqlite3.Connection) -> "int | None":
    """SQLite's schema cookie: it bumps when a schema change COMMITS, and a rollback
    leaves it where it was.

    This exists because every *inferred* answer to "did the migration's changes
    survive?" has been wrong. Whether `rollback()` raised does not tell you (it is a
    silent no-op with no open transaction). Whether `conn.in_transaction` is False
    does not tell you (true both when the body committed and when it rolled itself
    back). A body can commit its boundary with `executescript()` and then open a
    fresh transaction, so the rollback succeeds while the DDL is already durable.

    It is NOT a verdict, and this function deliberately does not present it as one:
    it is blind to DML, and inside an uncommitted write transaction it already shows
    the bumped value. It goes into the failure event's `detail` as a raw reading for
    whoever investigates. Returns None when it cannot be read at all."""
    try:
        return conn.execute("PRAGMA schema_version").fetchone()[0]
    except Exception:  # noqa: BLE001 -- an unreadable cookie is its own reading
        return None


def _swallowed_failure(conn: sqlite3.Connection) -> "BaseException | None":
    """The inner failure a migration body caught and discarded, if there was one.

    Peeks without popping: `_exit_migration_boundary` still owns the cleanup. A
    `db.transaction()` opened inside a migration body is non-outermost, so its
    failure sets `_TXN_POISON` and skips `_rollback_and_report` entirely -- nothing
    reports it. Discarding that quietly would make a migration that swallowed a
    failure indistinguishable from one that ran cleanly, and it would be stamped and
    recorded as applied. `transaction()` refuses exactly this on its outermost exit;
    so does `apply_migrations`."""
    with _TXN_LOCK:
        return _TXN_POISON.get(id(conn))


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def init_db(db_path: Path, schema_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        # A database that already has `projects` predates versioning, so it is
        # stamped 0 and every migration runs. A database that does not is being
        # created right now by schema.sql at the target shape, so it is stamped
        # at the current version and every migration is correctly skipped.
        pre_existing = _table_exists(conn, "projects")
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, ?)",
            (0 if pre_existing else SCHEMA_VERSION,),
        )
        conn.commit()
        apply_migrations(conn)
    finally:
        conn.close()


def apply_migrations(conn: sqlite3.Connection) -> list[int]:
    """Run every registered migration the database has not seen, in order.

    Returns the versions applied. Raises SchemaVersionError rather than booting
    against a database a newer build has already upgraded -- silently running
    old code over a new schema is how data gets destroyed.

    `conn` must not already be inside a transaction: this opens its own with a
    raw `BEGIN IMMEDIATE`, and sqlite3 rejects a nested one.

    **Caller contract on failure:** when this raises, the connection may still hold an
    open write transaction -- deliberately, because committing it would persist a
    partial migration. The caller must CLOSE the connection without committing.
    `init_db` does. A caller that catches and continues will have the partial
    migration committed by the next leaf helper that calls
    `commit_unless_in_transaction`."""
    from pipeline_app import obs

    # Enforced, not merely documented. If the caller's boundary has already done
    # DML, BEGIN IMMEDIATE raises and the failure is loud. If it has NOT, BEGIN
    # succeeds, the depth goes 1->2, and on the failure path it returns to 1 -- so
    # record_event's commit no-ops and the caller's rollback destroys the
    # schema.migration_failed row. The one durable record of the failure, lost,
    # with nothing to indicate it.
    if conn.in_transaction or _TXN_DEPTH.get(id(conn)):
        raise NestedMigrationError(
            "apply_migrations opens its own BEGIN IMMEDIATE and cannot run inside an "
            "existing transaction; commit or close the caller's boundary first"
        )
    with _TXN_LOCK:
        stranded = _TXN_POISON.get(id(conn))
    if stranded is not None:
        # Refusing here is also what lets the swallowed-failure check below be a plain
        # `is not None`: nothing can be inherited past this point, so identity
        # comparison against a pre-existing entry is unnecessary -- and it would have
        # been wrong anyway, since transaction() populates the map with setdefault, so
        # a later genuine failure never replaces an older object.
        raise StrandedPoisonError(
            f"connection carries a stranded transaction poison "
            f"({type(stranded).__name__}: {stranded}); it predates this call. Nothing "
            f"clears it in-process -- restart the app, and if it recurs the boundary "
            f"bookkeeping in db.py is leaking"
        )

    current = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
    if current > SCHEMA_VERSION:
        ahead_id = obs.record_event(
            conn, kind="schema.version_ahead_of_code", severity="critical",
            source="db.apply_migrations",
            message=f"database is at schema version {current}, this build understands "
                    f"{SCHEMA_VERSION}",
            detail={"db_version": current, "code_version": SCHEMA_VERSION},
        )
        if ahead_id == -1:
            obs.log("db.version_ahead_unrecorded", level="critical",
                    db_version=current, code_version=SCHEMA_VERSION,
                    message=f"database is at schema version {current}, this build "
                            f"understands {SCHEMA_VERSION}")
        raise SchemaVersionError(
            f"database schema version {current} is newer than this build's {SCHEMA_VERSION}; "
            f"upgrade the app or restore an older database"
        )
    applied: list[int] = []
    for version, migrate in _MIGRATIONS:
        if version <= current:
            continue
        # Explicit BEGIN IMMEDIATE, not db.transaction(). Python's sqlite3 opens an implicit
        # transaction only for DML, never for DDL -- so under the default
        # transaction control a migration's CREATE/ALTER lands on disk the instant
        # it executes and survives any rollback. Verified: without BEGIN,
        # `in_transaction` is False after a CREATE TABLE and rollback leaves the
        # table; with BEGIN it is True and the table is gone. db.transaction()
        # relies on that same implicit control, so it does NOT make DDL atomic and
        # is the wrong tool here.
        #
        # Without this, a migration that raises halfway leaves its DDL applied and
        # the version stamp untouched -- "partially applied" and "never ran" become
        # the same state. The next boot re-runs it, the already-applied ALTER fails
        # with "duplicate column name", and the database is wedged at that version
        # permanently, with every boot reporting the same error and no way to tell
        # which half already happened.
        #
        # IMMEDIATE rather than deferred: this boundary only ever writes, and on a
        # connection shared across threads under WAL a deferred transaction that
        # upgrades to a write can take SQLITE_BUSY_SNAPSHOT, which busy_timeout does
        # not resolve.
        cookie_before = _schema_cookie(conn)
        conn.execute("BEGIN IMMEDIATE")
        _enter_migration_boundary(conn)
        failure: BaseException | None = None
        rollback_failed = False
        pending_when_it_failed: bool | None = None
        try:
            migrate(conn)
            swallowed = _swallowed_failure(conn)
            if swallowed is not None:
                # Checked BEFORE the stamp and the commit, the last moment refusing is
                # still possible. The body caught an inner transaction()'s failure and
                # carried on; committing now would stamp a half-done migration as
                # applied while that inner failure went unreported by anyone, because
                # non-outermost blocks skip _rollback_and_report entirely.
                raise TransactionPoisonedError(
                    f"migration {version} swallowed an inner transaction failure: "
                    f"{type(swallowed).__name__}: {swallowed}"
                ) from swallowed
            conn.execute("UPDATE schema_version SET version = ? WHERE id = 1", (version,))
            conn.commit()
        except BaseException as exc:
            failure = exc
            # Captured HERE, before rollback() destroys it. This is the one reading
            # that separates "the body committed its work" (False) from "the work was
            # still pending and is about to be discarded" (True) -- and it is the only
            # observation on offer that flips when a body commits DML, which the schema
            # cookie cannot see. It was previously rejected for making a bad VERDICT,
            # which is a category error: this is a raw reading, and the reader draws
            # the conclusion.
            try:
                pending_when_it_failed = conn.in_transaction
            except Exception:  # noqa: BLE001 -- unreadable is its own reading
                pending_when_it_failed = None
            try:
                # Unconditional: rollback() with no open transaction is a harmless no-op.
                conn.rollback()
            except Exception as rollback_exc:  # noqa: BLE001 -- report, never mask
                rollback_failed = True
                obs.log("db.migration_rollback_failed", level="critical", version=version,
                        error=f"{type(rollback_exc).__name__}: {rollback_exc}")
        finally:
            # Leave the boundary BEFORE reporting. record_event commits through
            # commit_unless_in_transaction, which no-ops while the depth is held --
            # so reporting inside would leave the only durable record of the failure
            # uncommitted, and it would die with the process that needed to report it.
            _exit_migration_boundary(conn)
        if failure is not None:
            # Report OBSERVATIONS, not a verdict.
            #
            # Five attempts to state what survived have each been wrong in a different
            # way: whether rollback() raised (a no-op with no open transaction), whether
            # conn.in_transaction is False (true both when the body committed and when
            # it rolled itself back), whether the body returned normally, whether the
            # stamp advanced, and the schema cookie (blind to DML, and already bumped
            # inside an uncommitted transaction). Each new classifier was blind to a
            # migration shape the previous one handled.
            #
            # So this makes no claim it cannot support. The message says what is always
            # true -- the migration failed, a rollback was attempted, the database must
            # be checked -- and `detail` carries the raw readings for whoever looks. A
            # statement that cannot be false cannot conflate "nothing happened" with
            # "half of it is on disk", which is what every verdict here has done.
            cookie_after = _schema_cookie(conn)
            kind = "schema.migration_failed"
            message = (
                f"migration {version} failed and a rollback was "
                f"{'attempted and itself failed' if rollback_failed else 'attempted'}; "
                f"the database may contain partial changes -- verify before restarting: "
                f"{type(failure).__name__}: {failure}"
            )
            detail = {"version": version, "exception": type(failure).__name__,
                      "rollback_failed": rollback_failed,
                      "pending_when_it_failed": pending_when_it_failed,
                      "schema_cookie_before": cookie_before,
                      "schema_cookie_after": cookie_after,
                      "applied_before_failure": applied}
            # Recording COMMITS. If anything is still pending on this connection, that
            # commit would make a partial migration durable -- turning a state SQLite
            # discards on close into permanent corruption. So check first, and when it
            # is not safe, report to the log only. That is not a silent path: `failure`
            # is re-raised below, init_db's caller aborts the boot, and a process that
            # refuses to start is itself a surfacing signal.
            try:
                still_pending = conn.in_transaction
                pending_reading = still_pending
            except Exception:  # noqa: BLE001 -- unreadable means assume the worst
                still_pending = True
                pending_reading = "unreadable"
            if still_pending:
                # NOTE: nothing renders this. /doctor shows `events`, so the worst
                # reachable migration failure currently surfaces on no operator-facing
                # surface -- only in the log file and in the boot abort. Recording it
                # here is not an option: the commit would make the partial migration
                # durable. Raised as a known gap rather than pretended away.
                obs.log("db.migration_failed_unrecoverable", level="critical",
                        version=version, kind=kind, message=message, detail=detail,
                        in_transaction=pending_reading,
                        note="no events row written: a commit here would persist the "
                             "pending work")
            else:
                event_id = obs.record_event(
                    conn, kind=kind, severity="critical", source="db.apply_migrations",
                    message=message, detail=detail,
                )
                if event_id == -1:
                    # record_event never raises; it returns -1. Here the database is the
                    # component that just failed, so this is the likeliest place for the
                    # record itself to be lost -- and a missing record must not look
                    # like a migration that never failed.
                    obs.log("db.migration_failure_unrecorded", level="critical",
                            version=version, kind=kind, message=message)
            raise failure
        # Keep `current` honest inside the loop, so the skip guard above reflects
        # what has actually been applied rather than the state at entry.
        current = version
        applied.append(version)
        applied_id = obs.record_event(
            conn, kind="schema.migration_applied", severity="info", source="db.apply_migrations",
            message=f"applied schema migration {version}", detail={"version": version},
        )
        if applied_id == -1:
            # Without this, a migration that ran and a migration whose success was
            # never recorded look the same in `events` -- and `events` is what an
            # operator reads to reconstruct what a boot actually did.
            obs.log("db.migration_success_unrecorded", level="error", version=version)
    return applied
```

- [ ] **Write one more failing test.** A migration that applies DDL and *then* raises must leave no
      trace of either half, and must be distinguishable from one that never ran:

```python
def test_a_migration_that_fails_partway_leaves_neither_the_ddl_nor_the_stamp(tmp_path, monkeypatch):
    """Half-applied and never-applied must not be the same state. If the DDL
    survives while the stamp does not, the next boot re-runs the migration, the
    already-applied ALTER fails with "duplicate column name", and the database is
    wedged at that version forever."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        def half_a_migration(c):
            c.execute("ALTER TABLE projects ADD COLUMN doomed TEXT")
            raise RuntimeError("the second half failed")

        monkeypatch.setattr(db, "_MIGRATIONS", [(db.SCHEMA_VERSION + 1, half_a_migration)])
        with pytest.raises(RuntimeError, match="the second half failed"):
            db.apply_migrations(conn)

        assert "doomed" not in [r[1] for r in conn.execute("PRAGMA table_info(projects)")]
        assert conn.execute(
            "SELECT version FROM schema_version WHERE id = 1"
        ).fetchone()[0] == db.SCHEMA_VERSION
    finally:
        conn.close()

    # Read the event back on a SECOND connection. Reading it on the one that wrote
    # it passes whether or not the row was ever committed -- and "durable enough to
    # find after the process dies" is the only property that makes it a surfacing
    # test at all.
    other = db.get_connection(db_path)
    try:
        rows = other.execute(
            "SELECT * FROM events WHERE kind = 'schema.migration_failed'"
        ).fetchall()
    finally:
        other.close()
    assert len(rows) == 1          # ...and it said so
    assert rows[0]["severity"] == "critical"


def test_a_migration_body_calling_a_leaf_helper_does_not_commit_mid_migration(
    tmp_path, monkeypatch
):
    """The raw BEGIN is invisible to _TXN_DEPTH unless apply_migrations registers
    it, and commit_unless_in_transaction consults _TXN_DEPTH rather than the
    connection. Without the registration, a migration body that calls any db.py
    helper commits half the migration, the rollback rolls back nothing, and
    half-applied is indistinguishable from never-ran all over again."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        def migration_using_a_helper(c):
            db.create_project(c, "mid-migration", "a", "generic", "2026-08-08T00:00:00+00:00")
            raise RuntimeError("the second half failed")

        monkeypatch.setattr(db, "_MIGRATIONS", [(db.SCHEMA_VERSION + 1, migration_using_a_helper)])
        with pytest.raises(RuntimeError, match="the second half failed"):
            db.apply_migrations(conn)

        assert db.list_projects(conn) == []   # the helper's write rolled back too
        # The boundary must also clean up after itself. Without this, deleting
        # _exit_migration_boundary leaves the whole suite green while every
        # subsequent commit on this connection silently stops.
        assert id(conn) not in db._TXN_DEPTH
        assert id(conn) not in db._TXN_POISON
    finally:
        conn.close()


def test_a_refused_migration_leaves_no_poison_on_the_connection_id(
    tmp_path, monkeypatch
):
    """Bookkeeping cleanup after a refusal. A db.transaction() inside a migration
    body is non-outermost, so its finally takes the nested branch and leaves
    _TXN_POISON behind. init_db then closes this
    connection and the app allocates a new one on the next line -- CPython reuses the
    freed address readily -- so a stranded entry makes the first SUCCESSFUL outermost
    transaction() on the app's real connection roll back correct work and raise
    TransactionPoisonedError blaming a boot-time migration.

    The _MIGRATIONS contract forbids nesting a transaction() here. This proves the
    cleanup holds anyway, because a comment enforces nothing."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        def migration_that_nests(c):
            try:
                with db.transaction(c):
                    raise RuntimeError("inner half failed")
            except RuntimeError:
                pass  # swallowed -- this is what poisons the key

        monkeypatch.setattr(db, "_MIGRATIONS", [(db.SCHEMA_VERSION + 1, migration_that_nests)])
        # The migration is REFUSED -- see
        # test_a_migration_that_swallows_an_inner_failure_is_not_stamped_as_applied.
        # This test's subject is what happens to the bookkeeping afterwards.
        with pytest.raises(db.TransactionPoisonedError):
            db.apply_migrations(conn)

        assert id(conn) not in db._TXN_POISON
        # ...and the next ordinary boundary is not poisoned by it
        with db.transaction(conn):
            db.create_project(conn, "after", "a", "generic", "2026-08-08T00:00:00+00:00")
        assert [r["run_id"] for r in db.list_projects(conn)] == ["after"]
    finally:
        conn.close()


def test_a_migration_that_swallows_an_inner_failure_is_not_stamped_as_applied(
    tmp_path, monkeypatch
):
    """A body that catches an inner transaction()'s failure and carries on has, by
    definition, had that failure reported by nobody -- non-outermost blocks skip
    _rollback_and_report. Committing and stamping it would make a migration that
    swallowed a failure indistinguishable from one that ran cleanly."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        def migration_that_swallows(c):
            try:
                with db.transaction(c):
                    raise RuntimeError("the inner half failed")
            except RuntimeError:
                pass

        target = db.SCHEMA_VERSION + 1
        monkeypatch.setattr(db, "_MIGRATIONS", [(target, migration_that_swallows)])
        with pytest.raises(db.TransactionPoisonedError) as caught:
            db.apply_migrations(conn)

        assert "the inner half failed" in str(caught.value)
        assert isinstance(caught.value.__cause__, RuntimeError)
        assert conn.execute(
            "SELECT version FROM schema_version WHERE id = 1"
        ).fetchone()[0] != target          # NOT stamped as applied
    finally:
        conn.close()

    other = db.get_connection(db_path)
    try:
        rows = other.execute(
            "SELECT * FROM events WHERE kind = 'schema.migration_failed'"
        ).fetchall()
    finally:
        other.close()
    assert len(rows) == 1                  # ...and it was reported


def test_a_failed_rollback_reports_without_committing_the_partial_migration(
    tmp_path, monkeypatch
):
    """record_event commits whatever is still pending, so writing the events row here
    would make the partial migration DURABLE -- turning a state SQLite discards on
    close into permanent corruption. The report has to go somewhere that does not
    touch the database, and the failure has to stay recoverable."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)

    class _RollbackFails:
        """sqlite3.Connection is a C type and rejects attribute assignment."""

        def __init__(self, real):
            self._real = real

        def rollback(self):
            raise sqlite3.OperationalError("disk I/O error")

        def __getattr__(self, name):
            return getattr(self._real, name)

    conn = db.get_connection(db_path)
    wrapped = _RollbackFails(conn)
    try:
        def doomed(c):
            c.execute("ALTER TABLE projects ADD COLUMN doomed TEXT")
            raise RuntimeError("the migration failed")

        monkeypatch.setattr(db, "_MIGRATIONS", [(db.SCHEMA_VERSION + 1, doomed)])
        with pytest.raises(RuntimeError, match="the migration failed"):
            db.apply_migrations(wrapped)
    finally:
        conn.close()   # discards the transaction the failed rollback could not

    # No events row was written, deliberately: writing one would have COMMITTED the
    # half-applied ALTER. Closing the connection discarded it instead, so the
    # database self-heals -- assert that from a second connection.
    other = db.get_connection(db_path)
    try:
        cols = [r[1] for r in other.execute("PRAGMA table_info(projects)")]
        rows = other.execute(
            "SELECT * FROM events WHERE kind LIKE 'schema.%'"
        ).fetchall()
    finally:
        other.close()
    assert "doomed" not in cols
    assert [r["kind"] for r in rows] == []

    # ...and the failure is still on disk, in the sink that does not touch the database.
    text = "\n".join(
        p.read_text(encoding="utf-8") for p in (tmp_path / "logs").glob("app-*.log")
    )
    assert "db.migration_rollback_failed" in text
    assert "db.migration_failed_unrecoverable" in text


def test_a_migration_that_commits_its_own_boundary_is_not_reported_as_undone(
    tmp_path, monkeypatch
):
    """The shape that defeated every classifier. executescript() COMMITs the
    boundary, the following INSERT opens a fresh transaction, so rollback() succeeds
    and conn.in_transaction reads True -- every proxy signal says "rolled back" while
    the DDL is already durable. The record must not make that claim, and must keep
    the readings that show otherwise."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        def commits_then_fails(c):
            # executescript() COMMITs the boundary, then the INSERT opens a FRESH
            # transaction -- so rollback() succeeds and conn.in_transaction reads True.
            # Every proxy signal says "rolled back" here. Only the cookie disagrees,
            # and only the cookie is right.
            c.executescript("ALTER TABLE projects ADD COLUMN half TEXT;")
            c.execute("INSERT INTO projects (run_id, slug, brand, created_at) "
                      "VALUES ('x', 'x', 'generic', '2026-08-08T00:00:00+00:00')")
            raise RuntimeError("the second half failed")

        monkeypatch.setattr(db, "_MIGRATIONS", [(db.SCHEMA_VERSION + 1, commits_then_fails)])
        with pytest.raises(RuntimeError, match="the second half failed"):
            db.apply_migrations(conn)
    finally:
        conn.close()

    other = db.get_connection(db_path)
    try:
        cols = [r[1] for r in other.execute("PRAGMA table_info(projects)")]
        rows = other.execute(
            "SELECT * FROM events WHERE kind LIKE 'schema.migration%'"
        ).fetchall()
    finally:
        other.close()
    assert "half" in cols                    # the DDL really is durable...
    assert len(rows) == 1
    # The record must not claim the changes were undone -- and it must preserve the
    # raw evidence that they were not, since it deliberately renders no verdict.
    assert "may contain partial changes" in rows[0]["message"]
    detail = json.loads(rows[0]["detail"])
    assert detail["schema_cookie_before"] != detail["schema_cookie_after"]


def test_a_failure_that_left_durable_data_is_distinguishable_from_one_that_left_nothing(
    tmp_path, monkeypatch
):
    """The shape every classifier was blind to. executescript() COMMITs the boundary,
    so the INSERT is durable -- but it is DML, so the schema cookie does not move and
    reads identically to a migration that was cleanly rolled back.

    Without a reading that separates them, "nothing happened" and "half of it is on
    disk" produce byte-identical events rows. `pending_when_it_failed` is that
    reading: True when the work was still pending and about to be discarded, False
    when the body had already committed it."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")

    def run(body) -> dict:
        db_path = tmp_path / f"{body.__name__}.db"
        db.init_db(db_path, SCHEMA_PATH)
        conn = db.get_connection(db_path)
        try:
            monkeypatch.setattr(db, "_MIGRATIONS", [(db.SCHEMA_VERSION + 1, body)])
            with pytest.raises(RuntimeError, match="the second half failed"):
                db.apply_migrations(conn)
        finally:
            conn.close()
        other = db.get_connection(db_path)
        try:
            rows = other.execute(
                "SELECT * FROM events WHERE kind = 'schema.migration_failed'"
            ).fetchall()
            survivors = [r["run_id"] for r in db.list_projects(other)]
        finally:
            other.close()
        return {"detail": json.loads(rows[0]["detail"]), "survivors": survivors}

    def commits_its_data(c):
        c.executescript(
            "INSERT INTO projects (run_id, slug, brand, created_at) "
            "VALUES ('survivor', 's', 'generic', '2026-08-08T00:00:00+00:00');"
        )
        raise RuntimeError("the second half failed")

    def leaves_nothing(c):
        c.execute("INSERT INTO projects (run_id, slug, brand, created_at) "
                  "VALUES ('doomed', 'd', 'generic', '2026-08-08T00:00:00+00:00')")
        raise RuntimeError("the second half failed")

    durable, discarded = run(commits_its_data), run(leaves_nothing)

    assert durable["survivors"] == ["survivor"]   # half the migration really is on disk
    assert discarded["survivors"] == []           # ...and here nothing is
    # The cookie cannot tell them apart -- it is blind to DML. That is the point.
    assert (durable["detail"]["schema_cookie_before"]
            == durable["detail"]["schema_cookie_after"])
    # The records must still differ.
    assert durable["detail"] != discarded["detail"]
    assert durable["detail"]["pending_when_it_failed"] is False
    assert discarded["detail"]["pending_when_it_failed"] is True


def test_a_lost_events_row_does_not_look_like_a_migration_that_never_failed(
    tmp_path, monkeypatch
):
    """record_event never raises; it returns -1. Here the database is the component
    that just failed, so this is the likeliest site for the record itself to be lost
    -- and a missing record must not be indistinguishable from a clean boot."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        def doomed(c):
            raise RuntimeError("the second half failed")

        monkeypatch.setattr(db, "_MIGRATIONS", [(db.SCHEMA_VERSION + 1, doomed)])
        monkeypatch.setattr(obs, "record_event", lambda *a, **k: -1)
        with pytest.raises(RuntimeError, match="the second half failed"):
            db.apply_migrations(conn)
    finally:
        conn.close()

    text = "\n".join(
        p.read_text(encoding="utf-8") for p in (tmp_path / "logs").glob("app-*.log")
    )
    assert "db.migration_failure_unrecorded" in text


def test_apply_migrations_refuses_a_connection_carrying_stranded_poison(tmp_path, monkeypatch):
    """Stranded poison is neither a transaction nor a boundary, so refusing it with
    NestedMigrationError's "close the caller's boundary" would name something that
    does not exist and give an unactionable remedy. _exit_migration_boundary's own
    comment explains how such an entry survives onto a REUSED connection id."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        db._TXN_POISON[id(conn)] = RuntimeError("left over from a previous connection")
        try:
            with pytest.raises(db.StrandedPoisonError, match="predates this call"):
                db.apply_migrations(conn)
        finally:
            db._TXN_POISON.pop(id(conn), None)   # never leak module state between tests
    finally:
        conn.close()


def test_apply_migrations_refuses_a_connection_already_inside_a_boundary(tmp_path, monkeypatch):
    """The silent window this closes: with no DML done yet, BEGIN IMMEDIATE succeeds,
    the depth goes 1->2, and on the failure path record_event's commit no-ops so the
    caller's rollback destroys the schema.migration_failed row -- the one durable
    record, gone with nothing to indicate it."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        with pytest.raises(db.NestedMigrationError):
            with db.transaction(conn):          # no DML yet -- the silent window
                db.apply_migrations(conn)
    finally:
        conn.close()


def test_an_out_of_order_or_duplicated_migration_list_is_rejected_at_import():
    """An out-of-order entry stamps the version BACKWARDS: [(2, m2), (1, m1)] on a
    v0 database runs m2, stamps 2, then runs m1 and stamps 1 -- so migration 2 has
    run while the database claims it has not. The next boot re-runs it, hits
    `duplicate column name`, and is stuck at a version that is neither true nor
    recoverable. Failing loudly at import is strictly better."""
    def noop(_conn):
        pass

    with pytest.raises(RuntimeError):
        db._validate_migration_order([(2, noop), (1, noop)])
    with pytest.raises(RuntimeError):
        db._validate_migration_order([(1, noop), (1, noop)])
    db._validate_migration_order([(1, noop), (2, noop)])  # the good case must not raise
```

> Observe this fail against the un-guarded version first: the `doomed` column **survives**, because
> Python's sqlite3 never opens an implicit transaction for DDL. That failure is the nineteenth
> instance of the recurring defect class found in this programme, and it is the reason the explicit
> `BEGIN` above is not optional.

- [ ] **Run it.** All but the second and third pass. **The second *and third* both stay red**, for the same
      root cause: `_MIGRATIONS` is still empty here, so a legacy database has nothing to lift it off
      version 0. They come back at different tasks, so they carry different markers — getting this
      wrong points the next reader at the wrong task:
    - The second needs the `CHECK` in the `handles` DDL, which is **T10**'s job:
      `@pytest.mark.xfail(reason="migration 1 constrains handles in T10", strict=True)`.
    - The third needs only that *some* migration is registered, which happens in **T6**:
      `@pytest.mark.xfail(reason="migration 1 is registered in T6", strict=True)`.
    - `strict=True` on both is not optional. Without it an XPASS is reported and ignored, so a
      tripwire that has served its purpose would sit there forever and a test that started passing
      for the wrong reason would look identical to one still correctly red. With it, the marker
      turns into a hard failure the moment the migration lands, which is what forces its removal.
      Remove each marker in the task its reason names.
- [ ] **Commit.** `feat(db): version the schema and run migrations exactly once (A-72)`

---

### T6 — A-47: `stages.status` accepts any string

> **Blocking hazard, know this before writing the migration.** SQLite's only recipe for adding a
> `CHECK` to an existing table is create-copy-drop-rename, and that recipe normally disables foreign
> keys around itself. **`PRAGMA foreign_keys` is a no-op inside a transaction**, and T5's
> `apply_migrations` opens an explicit `BEGIN IMMEDIATE` before calling the migration body — so the
> pragma cannot be used from inside a migration. `projects` and `stages` are FK targets
> (`stages.project_id REFERENCES projects(id)`), so a naive rebuild will either fail or silently
> orphan children. Resolve this deliberately: use `PRAGMA legacy_alter_table`, rewrite the children,
> or have `apply_migrations` set the pragma before its `BEGIN` — and write down which and why. Do
> not discover it mid-migration.

> **Also remove** `test_migrations_are_applied_exactly_once`'s `xfail` marker here —
> registering migration 1 is exactly what makes it pass. `strict=True` will fail the suite as an
> XPASS if you forget, which is the point of the marker.

**A-47 (S4, latent).** `update_stage_status` takes a bare `str` and the column accepts anything.
Three call sites already pass string literals rather than `StageStatus` members, so a typo would
persist a status no guard recognizes — `is_locked_or_running` returns `False` for it, making the
stage chattable, editable and approvable regardless of what it was meant to mean.

- [ ] **Write the failing test.** Append to `tests/test_db.py`:

```python
def test_stages_status_rejects_a_value_outside_the_enum(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_stage_row(conn, project_id, "ideation", "awaiting_reveiw")  # the typo


def test_update_stage_status_rejects_a_value_outside_the_enum(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    with pytest.raises(sqlite3.IntegrityError):
        db.update_stage_status(conn, stage_row_id, "aproved")
    assert db.get_stage_by_row_id(conn, stage_row_id)["status"] == "ready"


def test_every_StageStatus_member_is_accepted_by_the_check(conn):
    """The constraint must not be narrower than the enum -- a CHECK that rejects
    a legitimate status is worse than none."""
    from pipeline_app.state_machine import StageStatus
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    for i, member in enumerate(StageStatus):
        db.create_stage_row(conn, project_id, f"stage-{i}", member.value)


def test_migration_coerces_a_ghost_stage_status_and_records_it(tmp_path: Path, monkeypatch):
    """A legacy database can already contain the typo. The migration must not
    brick the boot on it, and must not discard it silently either."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = _legacy_db(tmp_path)
    c = sqlite3.connect(db_path)
    c.executescript(
        "INSERT INTO projects (run_id, slug, brand, created_at) "
        "VALUES ('a-1','a','generic','2026-08-08T00:00:00+00:00');"
        "INSERT INTO stages (project_id, stage_id, status) VALUES (1,'ideation','awaiting_reveiw');"
    )
    c.commit()
    c.close()

    db.init_db(db_path, SCHEMA_PATH)

    c = db.get_connection(db_path)
    try:
        assert c.execute("SELECT status FROM stages WHERE id = 1").fetchone()[0] == "no_artifact"
        ev = c.execute(
            "SELECT * FROM events WHERE kind = 'schema.stage_status_coerced'"
        ).fetchall()
        assert len(ev) == 1
        assert "awaiting_reveiw" in ev[0]["message"]
    finally:
        c.close()
```

- [ ] **Run it.** All four fail — no `CHECK` exists.
- [ ] **Implement (a).** In `schema.sql`, replace the `stages` table with:

```sql
CREATE TABLE IF NOT EXISTS stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    stage_id TEXT NOT NULL,
    -- Mirrors state_machine.StageStatus. Without it a typo'd literal (three
    -- call sites already pass bare strings) persists a status no guard
    -- recognizes: is_locked_or_running returns False for it, so the stage stays
    -- chattable, editable and approvable regardless of intent (A-47).
    status TEXT NOT NULL CHECK (status IN
        ('locked','ready','running','awaiting_review','approved','stale','no_artifact')),
    claude_session_id TEXT,
    approved_at TEXT,
    UNIQUE(project_id, stage_id)
);
```

- [ ] **Implement (b).** In `db.py`, add migration 1's first half and register it:

```python
STAGE_STATUSES = ("locked", "ready", "running", "awaiting_review", "approved",
                  "stale", "no_artifact")


def _coerce_unknown_stage_statuses(conn: sqlite3.Connection) -> None:
    """A legacy row can already hold the typo the new CHECK exists to prevent,
    and `INSERT ... SELECT` into the rebuilt table would abort on it -- bricking
    the boot on the very defect being fixed. Coerce to 'no_artifact', which is
    loud in the UI and destroys nothing, and record one event per row."""
    from pipeline_app import obs

    placeholders = ",".join("?" * len(STAGE_STATUSES))
    rows = conn.execute(
        f"SELECT id, project_id, stage_id, status FROM stages "
        f"WHERE status NOT IN ({placeholders})", STAGE_STATUSES
    ).fetchall()
    for row in rows:
        conn.execute("UPDATE stages SET status = 'no_artifact' WHERE id = ?", (row["id"],))
        obs.record_event(
            conn, kind="schema.stage_status_coerced", severity="warning",
            source="db.migration_1",
            message=f"stage {row['stage_id']} held unknown status {row['status']!r}; "
                    f"coerced to 'no_artifact'",
            detail={"stage_row_id": row["id"], "project_id": row["project_id"],
                    "was": row["status"]},
        )
    if rows:
        conn.commit()


_MIGRATION_1_STAGES_SQL = """
CREATE TABLE stages_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    stage_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN
        ('locked','ready','running','awaiting_review','approved','stale','no_artifact')),
    claude_session_id TEXT,
    approved_at TEXT,
    UNIQUE(project_id, stage_id)
);
INSERT INTO stages_new (id, project_id, stage_id, status, claude_session_id, approved_at)
    SELECT id, project_id, stage_id, status, claude_session_id, approved_at FROM stages;
DROP TABLE stages;
ALTER TABLE stages_new RENAME TO stages;
"""


def _migration_1_constrain_core_tables(conn: sqlite3.Connection) -> None:
    """A-47/A-71/A-75/B-72/B-73/B-82 in one 12-step rebuild.

    Every statement in schema.sql is `CREATE TABLE IF NOT EXISTS`, so none of
    these constraints can reach a database that already has the table. This is
    the only path that applies them, and it is why schema_version exists."""
    conn.commit()
    _coerce_unknown_stage_statuses(conn)
    # PRAGMAs are no-ops inside a transaction, and executescript COMMITs first,
    # so both are issued on a clean connection. legacy_alter_table keeps RENAME
    # a pure rename instead of rewriting every referencing table's DDL midway
    # through a rebuild, when half the referenced tables do not exist.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA legacy_alter_table = ON")
    try:
        conn.executescript(_MIGRATION_1_STAGES_SQL)
        conn.commit()
    finally:
        conn.execute("PRAGMA legacy_alter_table = OFF")
        conn.execute("PRAGMA foreign_keys = ON")
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"migration 1 left {len(violations)} foreign key violations")


_MIGRATIONS = [(1, _migration_1_constrain_core_tables)]
```

- [ ] **Run it.** All four pass. Then the full app suite — `create_stage_row` is called with
      literals across many packages' tests; every literal already in the tree is a valid
      `StageStatus` (verified: `approved`, `awaiting_review`, `locked`, `ready`, `running`).
- [ ] **Commit.** `fix(schema): constrain stages.status to the StageStatus enum (A-47)`

---

### T7 — A-75: FK indices, `turns.status` CHECK, `ON DELETE` clauses

**A-75 (S4, latent).** `turns.stage_row_id`, `discovery_run_handles.run_id` and
`discovery_run_handles.handle_id` are declared as foreign keys with no covering index, so
`list_turns` and every FK integrity check are full scans — harmless at current volumes but growing
monotonically, since nothing prunes `turns`. No FK declares `ON DELETE`, so a future delete path
would either fail or orphan rows depending on pragma state.

- [ ] **Write the failing test.** Append to `tests/test_db.py`:

```python
def _indexed_columns(conn) -> set[tuple[str, str]]:
    out = set()
    for tbl, in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        for idx in conn.execute(f"PRAGMA index_list('{tbl}')").fetchall():
            for col in conn.execute(f"PRAGMA index_info('{idx['name']}')").fetchall():
                out.add((tbl, col["name"]))
    return out


def test_every_foreign_key_column_is_covered_by_an_index(conn):
    """An unindexed FK makes both the join and every integrity check a full
    scan, and turns is never pruned."""
    indexed = _indexed_columns(conn)
    for table, column in [("turns", "stage_row_id"),
                          ("discovery_run_handles", "run_id"),
                          ("discovery_run_handles", "handle_id"),
                          ("handles", "creator_id")]:
        assert (table, column) in indexed, f"{table}.{column} is an unindexed foreign key"


def test_turns_status_rejects_a_value_outside_the_vocabulary(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_turn(conn, stage_row_id, "complet", "2026-08-08T00:00:00+00:00", "e/1.jsonl")


def test_every_turn_status_the_app_writes_is_accepted(conn):
    """turn_service writes running/aborted/complete/failed; preflight writes
    orphaned. A CHECK narrower than that would break the app at runtime."""
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    turn_id = db.create_turn(conn, stage_row_id, "running", "2026-08-08T00:00:00+00:00", "e/1.jsonl")
    for status in ("complete", "failed", "aborted", "orphaned"):
        db.update_turn(conn, turn_id, status)


def test_deleting_a_project_cascades_to_its_stages_and_turns(conn):
    """No FK declared ON DELETE, so a future delete path would either fail or
    orphan rows depending on pragma state. Pin the behaviour now."""
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    db.create_turn(conn, stage_row_id, "complete", "2026-08-08T00:00:00+00:00", "e/1.jsonl")
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    assert conn.execute("SELECT count(*) FROM stages").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM turns").fetchone()[0] == 0
```

- [ ] **Run it.** All five fail.
- [ ] **Implement.** In `schema.sql`, replace `turns` and add the FK indices; mirror the same DDL
      into `_MIGRATION_1_TURNS_SQL` in `db.py` and call `_coerce_unknown_turn_statuses` (same
      shape as `_coerce_unknown_stage_statuses`, coercing to `'orphaned'` with kind
      `schema.turn_status_coerced` — a turn whose status cannot be interpreted *is* an orphan):

```sql
CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_row_id INTEGER NOT NULL REFERENCES stages(id) ON DELETE CASCADE,
    -- turn_service writes running/aborted/complete/failed; preflight writes
    -- orphaned. Anything else is a typo that every status comparison in the app
    -- would silently answer False to (A-47's defect, same shape) (A-75).
    status TEXT NOT NULL CHECK (status IN
        ('running','complete','failed','aborted','orphaned')),
    created_at TEXT NOT NULL,
    finished_at TEXT,
    events_path TEXT NOT NULL,
    cost_usd REAL
);
CREATE INDEX IF NOT EXISTS idx_turns_stage_row ON turns(stage_row_id);

CREATE INDEX IF NOT EXISTS idx_drh_run ON discovery_run_handles(run_id);
CREATE INDEX IF NOT EXISTS idx_drh_handle ON discovery_run_handles(handle_id);
```

Also add `ON DELETE CASCADE` to `discovery_run_handles.run_id` and `ON DELETE CASCADE` to
`discovery_run_handles.handle_id` in the same rebuild.

- [ ] **Run it.** The `creator_id` assertion still fails — that is T9's, correct failure. All
      others pass. Full app suite green.
- [ ] **Commit.** `fix(schema): index every FK, constrain turns.status, declare ON DELETE (A-75)`

---

### T8 — A-71: the missing partial unique index on `turns`

**A-71 (S2, silent).** The discovery subsystem enforces its single-running invariant in the schema
(`ux_discovery_single_running`). The pipeline's identical invariant has no such backstop:
`any_turn_running` is a plain `SELECT` followed by an unguarded `INSERT`. Two concurrent chat
POSTs can both read zero running turns and both insert one, launching two Claude subprocesses that
write the same `raw_output.md`.

- [ ] **Write the failing test.** Append to `tests/test_db.py`:

```python
def test_a_second_running_turn_is_rejected_by_the_storage_layer(conn):
    """FAULT. Mirrors test_insert_running_run_then_second_raises for the
    pipeline's identical invariant."""
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    s1 = db.create_stage_row(conn, project_id, "ideation", "running")
    s2 = db.create_stage_row(conn, project_id, "scripting", "running")
    db.create_turn(conn, s1, "running", "2026-08-08T00:00:00+00:00", "e/1.jsonl")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_turn(conn, s2, "running", "2026-08-08T00:00:01+00:00", "e/2.jsonl")


def test_one_running_turn_coexists_with_any_number_of_finished_ones(conn):
    """DISTINGUISHABILITY. The rejected-second-turn state must be different from
    'turns are broken' -- a partial index on the wrong expression would ban the
    second turn outright."""
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    for i in range(5):
        t = db.create_turn(conn, stage_row_id, "running", f"2026-08-08T00:0{i}:00+00:00",
                           f"e/{i}.jsonl")
        db.update_turn(conn, t, "complete", finished_at=f"2026-08-08T00:0{i}:30+00:00")
    db.create_turn(conn, stage_row_id, "running", "2026-08-08T00:06:00+00:00", "e/9.jsonl")
    assert len(db.list_turns(conn, stage_row_id)) == 6
    assert len(db.list_running_turns(conn)) == 1


def test_a_rejected_concurrent_turn_is_visible_as_an_error_event(conn, tmp_path, monkeypatch):
    """SURFACING. A race the storage layer refuses must leave a row -- an
    IntegrityError bubbling into a 500 tells the operator nothing findable."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    s1 = db.create_stage_row(conn, project_id, "ideation", "running")
    s2 = db.create_stage_row(conn, project_id, "scripting", "running")
    db.create_turn(conn, s1, "running", "2026-08-08T00:00:00+00:00", "e/1.jsonl")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_turn(conn, s2, "running", "2026-08-08T00:00:01+00:00", "e/2.jsonl")
    rows = conn.execute(
        "SELECT * FROM events WHERE kind = 'turn.concurrent_start_rejected'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["severity"] == "error"
    assert rows[0]["detail"] is not None and "scripting" not in rows[0]["message"] or True


def test_migration_orphans_all_but_the_newest_running_turn(tmp_path: Path, monkeypatch):
    """A legacy database can already hold two running turns -- the exact race
    this index prevents. The index cannot be created over them, so the migration
    resolves it loudly instead of failing to boot."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = _legacy_db(tmp_path)
    c = sqlite3.connect(db_path)
    c.executescript(
        "INSERT INTO projects (run_id, slug, brand, created_at) "
        "VALUES ('a-1','a','generic','2026-08-08T00:00:00+00:00');"
        "INSERT INTO stages (project_id, stage_id, status) VALUES (1,'ideation','running');"
        "INSERT INTO stages (project_id, stage_id, status) VALUES (1,'scripting','running');"
        "INSERT INTO turns (stage_row_id,status,created_at,events_path) "
        "VALUES (1,'running','2026-08-08T00:00:00+00:00','e/1.jsonl');"
        "INSERT INTO turns (stage_row_id,status,created_at,events_path) "
        "VALUES (2,'running','2026-08-08T00:00:05+00:00','e/2.jsonl');"
    )
    c.commit()
    c.close()

    db.init_db(db_path, SCHEMA_PATH)

    c = db.get_connection(db_path)
    try:
        assert [r["status"] for r in c.execute("SELECT status FROM turns ORDER BY id")] \
            == ["orphaned", "running"]
        assert c.execute(
            "SELECT count(*) FROM events WHERE kind = 'schema.duplicate_running_turn_orphaned'"
        ).fetchone()[0] == 1
    finally:
        c.close()
```

- [ ] **Run it.** All four fail.
- [ ] **Implement (a).** Append to `schema.sql`, immediately after `turns`:

```sql
-- The pipeline's single-running invariant, at the storage layer where discovery
-- already has it (ux_discovery_single_running). Two concurrent chat POSTs can
-- both read zero running turns and both insert one, launching two Claude
-- subprocesses that write the same raw_output.md (A-71).
CREATE UNIQUE INDEX IF NOT EXISTS ux_turns_single_running
    ON turns(status) WHERE status = 'running';
```

- [ ] **Implement (b).** In `db.py`, wrap `create_turn`'s insert:

```python
def create_turn(conn: sqlite3.Connection, stage_row_id: int, status: str,
                created_at: str, events_path: str) -> int:
    from pipeline_app import obs

    try:
        cur = conn.execute(
            "INSERT INTO turns (stage_row_id, status, created_at, events_path) "
            "VALUES (?, ?, ?, ?)",
            (stage_row_id, status, created_at, events_path),
        )
    except sqlite3.IntegrityError as exc:
        # ux_turns_single_running fired: another turn is already running. The
        # application-level checks (route pre-check and run_stage_turn) both
        # read zero -- this is the race they cannot see (A-71).
        obs.record_event(
            conn, kind="turn.concurrent_start_rejected", severity="error",
            source="db.create_turn",
            message=f"refused a second running turn for stage_row_id={stage_row_id}",
            detail={"stage_row_id": stage_row_id, "error": str(exc)},
        )
        raise
    commit_unless_in_transaction(conn)
    return cur.lastrowid
```

- [ ] **Implement (c).** Add `_orphan_all_but_newest_running_turn(conn)` to migration 1, before
      the `turns` rebuild: select `running` turns ordered by `created_at DESC, id DESC`, keep the
      first, `UPDATE ... SET status='orphaned'` on the rest, and `record_event` per row with kind
      `schema.duplicate_running_turn_orphaned`, severity `warning`.
- [ ] **Run it.** All four pass. Tidy the third test's trailing `or True` — it is a placeholder in
      this plan, not shippable; assert on `rows[0]["detail"]` containing the stage row id instead.
- [ ] **Commit.** `fix(schema): enforce one running turn at the storage layer (A-71)`

---

### T9 — B-72: cross-platform creator identity

**B-72 (S2, coverage-gap).** `@jane` on YouTube and `@jane` on X are unrelated rows with no join
key. Per-creator reporting is impossible, dedup is per platform+handle directory, and "did we miss
this creator's new platform" — the operator's actual question — is unanswerable. Adam Grant is
already registered twice, unlinked.

- [ ] **Write the failing test.** Append to `tests/test_db.py`:

```python
def test_one_creator_can_own_handles_on_several_platforms(conn):
    """The join key that does not exist today. Adam Grant is registered on two
    platforms in manifests/brand_sources.json with nothing connecting them."""
    creator_id = db.upsert_creator(conn, slug="adam-grant", display_name="Adam Grant")
    yt = db.create_handle(conn, "youtube", "@bigthink", None, "guru", None,
                          "2026-08-08T00:00:00+00:00")
    x = db.create_handle(conn, "x", "@AdamMGrant", None, "guru", None,
                         "2026-08-08T00:00:00+00:00")
    db.link_handle_to_creator(conn, yt, creator_id)
    db.link_handle_to_creator(conn, x, creator_id)
    rows = db.list_handles_for_creator(conn, creator_id)
    assert {(r["platform"], r["handle"]) for r in rows} == \
        {("youtube", "@bigthink"), ("x", "@AdamMGrant")}


def test_upsert_creator_is_idempotent_and_updates_the_display_name(conn):
    first = db.upsert_creator(conn, slug="adam-grant", display_name="A Grant")
    second = db.upsert_creator(conn, slug="adam-grant", display_name="Adam Grant")
    assert second == first
    assert db.get_creator_by_slug(conn, "adam-grant")["display_name"] == "Adam Grant"


def test_an_unlinked_handle_is_distinguishable_from_a_linked_one(conn):
    """Today every handle is unlinked and there is no way to tell. After P10
    populates creators, an unlinked handle is a coverage gap the operator can
    query for."""
    db.create_handle(conn, "youtube", "@a", None, "guru", None, "2026-08-08T00:00:00+00:00")
    linked = db.create_handle(conn, "x", "@b", None, "guru", None, "2026-08-08T00:00:00+00:00")
    db.link_handle_to_creator(conn, linked,
                              db.upsert_creator(conn, slug="b", display_name="B"))
    assert [r["handle"] for r in db.list_unlinked_handles(conn)] == ["@a"]


def test_deleting_a_creator_does_not_delete_its_handles(conn):
    """ON DELETE SET NULL, not CASCADE: a roster edit must never destroy the
    handle rows that own the downloaded corpus directories."""
    creator_id = db.upsert_creator(conn, slug="a", display_name="A")
    handle_id = db.create_handle(conn, "youtube", "@a", None, "guru", None,
                                 "2026-08-08T00:00:00+00:00")
    db.link_handle_to_creator(conn, handle_id, creator_id)
    conn.execute("DELETE FROM creators WHERE id = ?", (creator_id,))
    conn.commit()
    assert db.get_handle(conn, handle_id)["creator_id"] is None
```

- [ ] **Run it.** `no such table: creators`.
- [ ] **Implement (a).** Append to `schema.sql`, **above** `handles` (the FK target must exist
      first), verbatim from the frozen DDL plus the index:

```sql
-- Cross-platform creator identity. Without it @jane on YouTube and @jane on X
-- are unrelated rows: per-creator reporting is impossible, one creator's
-- cross-post is counted three times in the daily inventory, and "did we miss
-- this creator's new platform" is unanswerable (B-72). P10 populates this from
-- the manifests; this package only creates it.
CREATE TABLE IF NOT EXISTS creators (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  slug         TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_handles_creator ON handles(creator_id);
```

- [ ] **Implement (b).** Add `upsert_creator`, `get_creator_by_slug`, `link_handle_to_creator`,
      `list_handles_for_creator`, `list_unlinked_handles` to `db.py`:

```python
def upsert_creator(conn: sqlite3.Connection, *, slug: str, display_name: str) -> int:
    """One creator, keyed by a stable slug. P10 calls this from the manifests."""
    with transaction(conn):
        conn.execute(
            "INSERT INTO creators (slug, display_name) VALUES (?, ?) "
            "ON CONFLICT(slug) DO UPDATE SET display_name = excluded.display_name",
            (slug, display_name),
        )
    return conn.execute("SELECT id FROM creators WHERE slug = ?", (slug,)).fetchone()["id"]


def get_creator_by_slug(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM creators WHERE slug = ?", (slug,)).fetchone()


def link_handle_to_creator(conn: sqlite3.Connection, handle_id: int, creator_id: int) -> None:
    conn.execute("UPDATE handles SET creator_id = ? WHERE id = ?", (creator_id, handle_id))
    commit_unless_in_transaction(conn)


def list_handles_for_creator(conn: sqlite3.Connection, creator_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM handles WHERE creator_id = ? ORDER BY platform, handle", (creator_id,)
    ).fetchall()


def list_unlinked_handles(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Handles with no creator. After P10's migration this is the coverage gap
    list: every row here is a creator the roster cannot report on."""
    return conn.execute(
        "SELECT * FROM handles WHERE creator_id IS NULL ORDER BY platform, handle"
    ).fetchall()
```

- [ ] **Run it.** These four plus T7's `creator_id` index assertion now pass.
- [ ] **Commit.** `feat(schema): add cross-platform creator identity (B-72)`

---

### T10 — B-73: `handles.platform` is unconstrained free text

> **Also remove** `test_an_existing_database_is_migrated_not_silently_left_behind`'s `xfail`
> marker here — constraining `handles` is what makes it pass. `strict=True` turns a forgotten
> marker into a hard failure.

**B-73 (S2, silent).** `platform` is `TEXT NOT NULL` with no CHECK, no enum and no FK. A value the
adapter registry does not know (`"instgram"`) is stored happily; the spawned validate run then does
`adapters[handle_row["platform"]]` **outside** the guarding try/except, so it raises `KeyError` in a
detached subprocess before `set_handle_status(..., "validating")` ever runs. The row is left
`status='pending', included=1` forever: a ghost platform the operator sees as a tracked handle,
polled indefinitely for a status that will never change, producing an `error` row on every daily run.

- [ ] **Remove** the `xfail` marker added to `test_an_existing_database_is_migrated_not_silently_left_behind` in T5.
- [ ] **Write the failing test.** Append to `tests/test_db.py`:

```python
def test_an_unknown_platform_is_rejected_at_the_storage_layer(conn):
    """FAULT."""
    with pytest.raises(sqlite3.IntegrityError):
        db.create_handle(conn, "instgram", "@a", None, "guru", None, "2026-08-08T00:00:00+00:00")


def test_a_rejected_platform_leaves_no_row_unlike_a_valid_one(conn):
    """DISTINGUISHABILITY. The ghost-platform state -- a row that exists,
    is included, and will never leave 'pending' -- must be impossible, and must
    not be confused with the platform simply having no handles yet."""
    db.create_handle(conn, "instagram", "@real", None, "guru", None, "2026-08-08T00:00:00+00:00")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_handle(conn, "instgram", "@ghost", None, "guru", None,
                         "2026-08-08T00:00:00+00:00")
    assert [r["handle"] for r in db.list_handles(conn)] == ["@real"]
    assert db.list_platform_handles(conn, "instgram") == []


def test_every_platform_the_adapter_registry_knows_is_accepted(conn):
    for platform in ("youtube", "bluesky", "instagram", "linkedin-profile",
                     "linkedin-company", "facebook", "x"):
        db.create_handle(conn, platform, "@a", None, "guru", None, "2026-08-08T00:00:00+00:00")
    assert len(db.list_handles(conn)) == 7


def test_migration_quarantines_a_ghost_platform_row_and_records_it(tmp_path: Path, monkeypatch):
    """SURFACING. A legacy database already contains the ghost the CHECK now
    forbids. Dropping it silently would destroy the operator's only record of
    what they typed; aborting the migration would brick the boot on the very
    defect being fixed."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = _legacy_db(tmp_path)
    c = sqlite3.connect(db_path)
    c.execute(
        "INSERT INTO handles (platform, handle, cohort, added_at) "
        "VALUES ('instgram', '@ghost', 'guru', '2026-08-08T00:00:00+00:00')"
    )
    c.commit()
    c.close()

    db.init_db(db_path, SCHEMA_PATH)

    c = db.get_connection(db_path)
    try:
        assert c.execute("SELECT count(*) FROM handles").fetchone()[0] == 0
        quarantined = c.execute("SELECT * FROM handles_quarantine").fetchall()
        assert [(r["platform"], r["handle"]) for r in quarantined] == [("instgram", "@ghost")]
        ev = c.execute("SELECT * FROM events WHERE kind = 'schema.handle_quarantined'").fetchall()
        assert len(ev) == 1
        assert ev[0]["severity"] == "warning"
        assert "instgram" in ev[0]["message"]
    finally:
        c.close()
```

- [ ] **Run it.** All four fail.
- [ ] **Implement (a).** In `schema.sql`, replace `handles` (keeping it below `creators`):

```sql
CREATE TABLE IF NOT EXISTS handles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id INTEGER REFERENCES creators(id) ON DELETE SET NULL,
    -- The adapter registry's vocabulary. Unconstrained, a mistyped or
    -- hand-posted value is stored happily and then raises KeyError in a
    -- detached validate subprocess, leaving the row 'pending'/included=1
    -- forever: a ghost the handles page polls for a status that never
    -- arrives (B-73).
    platform TEXT NOT NULL CHECK (platform IN
        ('youtube','bluesky','instagram','linkedin-profile','linkedin-company',
         'facebook','x')),
    handle TEXT NOT NULL,
    display_name TEXT,
    cohort TEXT NOT NULL,
    keyword_filter TEXT,
    included INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN
        ('pending','validating','validated','invalid','failing')),
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    added_at TEXT NOT NULL,
    validated_at TEXT,
    last_seen_published_at TEXT,
    UNIQUE(platform, handle)
);

-- Rows migration 1 could not carry across the platform CHECK. Kept, not
-- dropped: this is the only record of what the operator actually typed.
CREATE TABLE IF NOT EXISTS handles_quarantine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quarantined_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    platform TEXT NOT NULL,
    handle TEXT NOT NULL,
    display_name TEXT,
    cohort TEXT,
    keyword_filter TEXT,
    included INTEGER,
    status TEXT,
    added_at TEXT,
    validated_at TEXT,
    last_seen_published_at TEXT
);
```

- [ ] **Implement (b).** In `db.py`, add `KNOWN_PLATFORMS`, `_quarantine_unknown_platforms`, and
      `_MIGRATION_1_HANDLES_SQL`; call the quarantine step from
      `_migration_1_constrain_core_tables` *before* the handles rebuild:

```python
KNOWN_PLATFORMS = ("youtube", "bluesky", "instagram", "linkedin-profile",
                   "linkedin-company", "facebook", "x")


def _quarantine_unknown_platforms(conn: sqlite3.Connection) -> None:
    """Move B-73's ghost rows aside so the rebuild's INSERT ... SELECT is not
    aborted by the very defect the CHECK exists to prevent. Each row is copied
    verbatim and reported -- deleting it silently would destroy the operator's
    only record of the typo, which is the same class of failure."""
    from pipeline_app import obs

    placeholders = ",".join("?" * len(KNOWN_PLATFORMS))
    rows = conn.execute(
        f"SELECT * FROM handles WHERE platform NOT IN ({placeholders})", KNOWN_PLATFORMS
    ).fetchall()
    if not rows:
        return
    now = _utcnow_iso()
    for row in rows:
        conn.execute(
            "INSERT INTO handles_quarantine (quarantined_at, reason, platform, handle, "
            "display_name, cohort, keyword_filter, included, status, added_at, validated_at, "
            "last_seen_published_at) VALUES (?, 'unknown platform', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (now, row["platform"], row["handle"], row["display_name"], row["cohort"],
             row["keyword_filter"], row["included"], row["status"], row["added_at"],
             row["validated_at"], row["last_seen_published_at"]),
        )
        conn.execute("DELETE FROM handles WHERE id = ?", (row["id"],))
        obs.record_event(
            conn, kind="schema.handle_quarantined", severity="warning",
            source="db.migration_1",
            message=f"handle {row['handle']} names unknown platform {row['platform']!r}; "
                    f"moved to handles_quarantine",
            detail={"platform": row["platform"], "handle": row["handle"],
                    "known_platforms": list(KNOWN_PLATFORMS)},
        )
    conn.commit()
```

`_utcnow_iso()` is a two-line helper in `db.py`:
`return datetime.now(timezone.utc).isoformat(timespec="seconds")`.

- [ ] **Run it.** All four pass, plus T5's un-`xfail`ed test. Full app suite green — every
      `create_handle` platform literal in the tree is already in `KNOWN_PLATFORMS` (verified:
      `youtube`, `facebook`, `instagram`; `test_email_render.py`'s `"threads"` is a dict fixture,
      never a DB row).
- [ ] **Commit.** `fix(schema): constrain handles.platform and quarantine ghost rows (B-73)`

---

### T11 — B-82: a handle that dies after registration still looks healthy

**B-82 (S2, silent).** `set_handle_status` is called only inside the one-shot `validate_handle`
branch. A handle that validates at registration and later dies — channel deleted, account renamed,
scraper permanently blocked — raises per-handle errors into `discovery_run_handles` on every run
but keeps `status='validated'`, `included=1` on the handles page indefinitely. On the roster
surface a permanently-broken handle is indistinguishable from a healthy one.

- [ ] **Write the failing test.** Append to `tests/test_db.py`:

```python
def test_a_handle_is_downgraded_to_failing_after_three_consecutive_failures(conn):
    """FAULT."""
    handle_id = db.create_handle(conn, "youtube", "@dead", None, "guru", None,
                                 "2026-08-08T00:00:00+00:00")
    db.set_handle_status(conn, handle_id, "validated", validated_at="2026-08-08T00:01:00+00:00")
    for _ in range(2):
        db.record_handle_failure(conn, handle_id, now_iso="2026-08-08T06:00:00+00:00")
        assert db.get_handle(conn, handle_id)["status"] == "validated"
    assert db.record_handle_failure(conn, handle_id, now_iso="2026-08-08T06:00:00+00:00") \
        == "failing"
    row = db.get_handle(conn, handle_id)
    assert row["status"] == "failing"
    assert row["consecutive_failures"] == 3


def test_a_failing_handle_is_distinguishable_from_an_operator_disabled_one(conn):
    """DISTINGUISHABILITY. The intended distinction already works in the other
    direction -- included=0/validated (operator disabled) vs
    included=0/invalid (auto-excluded at registration). The gap was only for
    handles that break *after* registration, and this closes it without
    collapsing into either existing state."""
    dead = db.create_handle(conn, "youtube", "@dead", None, "guru", None,
                            "2026-08-08T00:00:00+00:00")
    disabled = db.create_handle(conn, "youtube", "@paused", None, "guru", None,
                                "2026-08-08T00:00:00+00:00")
    for h in (dead, disabled):
        db.set_handle_status(conn, h, "validated", validated_at="2026-08-08T00:01:00+00:00")
    for _ in range(3):
        db.record_handle_failure(conn, dead, now_iso="2026-08-08T06:00:00+00:00")
    db.set_handle_included(conn, disabled, False)

    dead_row, disabled_row = db.get_handle(conn, dead), db.get_handle(conn, disabled)
    assert (dead_row["status"], dead_row["included"]) == ("failing", 1)
    assert (disabled_row["status"], disabled_row["included"]) == ("validated", 0)
    assert dead_row["consecutive_failures"] == 3
    assert disabled_row["consecutive_failures"] == 0


def test_downgrading_a_handle_records_an_error_event(conn, tmp_path, monkeypatch):
    """SURFACING."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    handle_id = db.create_handle(conn, "youtube", "@dead", None, "guru", None,
                                 "2026-08-08T00:00:00+00:00")
    db.set_handle_status(conn, handle_id, "validated", validated_at="2026-08-08T00:01:00+00:00")
    for _ in range(3):
        db.record_handle_failure(conn, handle_id, now_iso="2026-08-08T06:00:00+00:00")
    rows = conn.execute("SELECT * FROM events WHERE kind = 'handle.marked_failing'").fetchall()
    assert len(rows) == 1
    assert rows[0]["severity"] == "error"
    assert "@dead" in rows[0]["message"]


def test_a_successful_fetch_lifts_a_failing_handle_back_to_validated(conn):
    """The downgrade has to be reversible: a transient outage must not
    permanently mark a live source dead."""
    handle_id = db.create_handle(conn, "youtube", "@flaky", None, "guru", None,
                                 "2026-08-08T00:00:00+00:00")
    db.set_handle_status(conn, handle_id, "validated", validated_at="2026-08-08T00:01:00+00:00")
    for _ in range(3):
        db.record_handle_failure(conn, handle_id, now_iso="2026-08-08T06:00:00+00:00")
    db.clear_handle_failures(conn, handle_id)
    row = db.get_handle(conn, handle_id)
    assert (row["status"], row["consecutive_failures"]) == ("validated", 0)


def test_clearing_failures_does_not_resurrect_a_handle_the_operator_invalidated(conn):
    """'invalid' is a registration-time verdict, not a failure counter. A
    successful fetch must not overwrite it."""
    handle_id = db.create_handle(conn, "youtube", "@bad", None, "guru", None,
                                 "2026-08-08T00:00:00+00:00")
    db.set_handle_status(conn, handle_id, "invalid")
    db.clear_handle_failures(conn, handle_id)
    assert db.get_handle(conn, handle_id)["status"] == "invalid"
```

- [ ] **Run it.** `no such column: consecutive_failures`.
- [ ] **Implement.** The column and the `failing` status already landed in T10's `handles` DDL.
      Add to `db.py`:

```python
HANDLE_FAILURE_THRESHOLD = 3


def record_handle_failure(conn: sqlite3.Connection, handle_id: int, *, now_iso: str,
                          threshold: int = HANDLE_FAILURE_THRESHOLD) -> str:
    """Count one consecutive per-handle failure; return the handle's status.

    B-82: set_handle_status was only ever called from the one-shot validate
    branch, so a handle that validated at registration and later died kept
    status='validated', included=1 forever while raising an error row into
    discovery_run_handles on every single run. On the roster a permanently
    broken source was indistinguishable from a healthy one.

    At `threshold` consecutive failures the handle is downgraded to 'failing'.
    The counter is the evidence; the status is the signal. P8 calls this from
    the per-handle error branch of discovery_engine."""
    from pipeline_app import obs

    with transaction(conn):
        conn.execute(
            "UPDATE handles SET consecutive_failures = consecutive_failures + 1 WHERE id = ?",
            (handle_id,),
        )
        row = conn.execute(
            "SELECT handle, platform, status, consecutive_failures FROM handles WHERE id = ?",
            (handle_id,),
        ).fetchone()
        if row is None:
            return "unknown"
        status = row["status"]
        if row["consecutive_failures"] >= threshold and status in ("validated", "pending"):
            status = "failing"
            conn.execute("UPDATE handles SET status = 'failing' WHERE id = ?", (handle_id,))
            obs.record_event(
                conn, kind="handle.marked_failing", severity="error",
                source="db.record_handle_failure",
                message=f"{row['platform']} handle {row['handle']} failed "
                        f"{row['consecutive_failures']} consecutive runs; marked failing",
                detail={"handle_id": handle_id, "platform": row["platform"],
                        "handle": row["handle"],
                        "consecutive_failures": row["consecutive_failures"],
                        "since": now_iso},
            )
    return status


def clear_handle_failures(conn: sqlite3.Connection, handle_id: int) -> None:
    """A successful fetch resets the counter and lifts a 'failing' handle back to
    'validated'. 'invalid' is deliberately untouched: that is a registration-time
    verdict, not a failure counter."""
    conn.execute(
        "UPDATE handles SET consecutive_failures = 0, "
        "status = CASE WHEN status = 'failing' THEN 'validated' ELSE status END WHERE id = ?",
        (handle_id,),
    )
    commit_unless_in_transaction(conn)
```

- [ ] **Run it.** All five pass.
- [ ] **Commit.** `feat(db): downgrade a handle that fails N consecutive runs (B-82)`

---

### T12 — the schema-drift guard

Every constraint in T6–T11 exists twice: once in `schema.sql` (create-from-scratch) and once in
migration 1 (upgrade). That duplication is how migration systems silently diverge. One test makes
divergence impossible.

- [ ] **Write the failing test.** Append to `tests/test_db.py`:

```python
def _normalized_schema(conn) -> set[str]:
    return {
        " ".join(row[0].split())
        for row in conn.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    }


def test_a_migrated_database_has_the_same_schema_as_a_fresh_one(tmp_path: Path):
    """schema.sql and the migration list express the same constraints twice.
    A database upgraded from v0 and one created today must be indistinguishable,
    or the next `no such column` at runtime is already written."""
    fresh_path = tmp_path / "fresh.db"
    db.init_db(fresh_path, SCHEMA_PATH)

    migrated_path = _legacy_db(tmp_path)
    db.init_db(migrated_path, SCHEMA_PATH)

    fresh, migrated = db.get_connection(fresh_path), db.get_connection(migrated_path)
    try:
        assert _normalized_schema(migrated) == _normalized_schema(fresh)
    finally:
        fresh.close()
        migrated.close()
```

- [ ] **Run it.** It fails on whatever T6–T11 got subtly wrong — most likely an `IF NOT EXISTS`
      present in one form and absent in the other, or a column order difference. Fix the migration
      SQL (never the assertion) until the two match exactly.
- [ ] **Commit.** `test(db): pin the migrated schema to the fresh schema (A-72)`

---

### T13 — A-85: no lifespan handler, so the connection is never closed

**A-85 (S4, latent).** `create_app` opens the shared connection and registers no shutdown hook, so
it is closed only by process exit — the WAL is never explicitly checkpointed, leaving
`pipeline.db-wal`/`-shm` beside the database after every run. `init_db` correctly opens and closes
its own short-lived connection, which makes the asymmetry a deviation from the module's own
established pattern.

- [ ] **Write the failing test.** Append to `tests/test_main.py`:

```python
def test_app_shutdown_closes_the_connection_and_truncates_the_wal(repo_root: Path):
    from fastapi.testclient import TestClient

    db_path = repo_root / "pipeline.db"
    app = create_app(repo_root=repo_root, db_path=db_path)
    with TestClient(app) as client:
        client.get("/doctor")
        assert (repo_root / "pipeline.db-wal").exists()
    # Shutdown ran: the connection is closed and the WAL was checkpointed away.
    with pytest.raises(sqlite3.ProgrammingError):
        app.state.conn.execute("SELECT 1")
    assert (repo_root / "pipeline.db-wal").stat().st_size == 0 \
        or not (repo_root / "pipeline.db-wal").exists()
```

- [ ] **Run it.** Fails — no lifespan runs, the connection stays open.
- [ ] **Implement.** In `main.py`, build the app with a lifespan:

```python
from contextlib import asynccontextmanager


def create_app(repo_root: Path, db_path: Path) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        # `init_db` already opens and closes its own short-lived connection;
        # the shared one had no shutdown hook at all, so the WAL was never
        # checkpointed and every test that built an app leaked a connection and
        # its -wal/-shm files for the life of the process (A-85).
        _release_reconcile_lease(app.state.conn, app.state.instance_token)
        try:
            app.state.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception as exc:  # noqa: BLE001 -- shutdown must not raise
            obs.log("db.checkpoint_failed", level="warning",
                    error=f"{type(exc).__name__}: {exc}")
        app.state.conn.close()

    app = FastAPI(lifespan=lifespan)
    ...
```

`_release_reconcile_lease` lands in T14; stub it as a no-op here and fill it in there, or land
T14 first.

- [ ] **Run it.** Passes. Full app suite green — no existing test uses `with TestClient(app)`
      (verified: zero occurrences), so no existing test's connection is closed early by this.
- [ ] **Commit.** `fix(main): close the shared connection and checkpoint the WAL on shutdown (A-85)`

---

### T13b — the shared connection makes a transaction boundary unsafe under concurrent routes

**Raised during T4b's review, not in the original audit.** T4 keys a boundary by connection
identity; T4b then opened boundaries inside `approve_stage_route` and `create_project_route`, which
are **sync `def`** routes and therefore run in Starlette's threadpool. The turn route's async
generator writes to the *same* `app.state.conn` from the event-loop thread for the whole life of a
streaming turn, and `any_turn_running` gates only the run-turn route — so approving stage Y while a
turn streams on stage X is a supported path. During that window the turn's writes stop committing,
and on a fault path they are discarded by the boundary's rollback. The `events` row attributes
nothing to the collateral write, so a lost turn write looks exactly like a turn that never wrote:
the recurring defect class, reached through the mechanism built to eliminate it.

Probability is low — one local user, short boundaries, sparse turn writes — and the consequence is
silent data loss, so it does not get to stay unaddressed on probability alone.

**This task needs an architectural decision before it can be executed. Do not dispatch an
implementer until the operator has chosen.** The options, none obviously correct:

1. **A connection per boundary.** `transaction()` opens its own connection, so a boundary can never
   suppress another thread's commit. Costs: the boundary can no longer read the caller's uncommitted
   writes, which `approve_stage` relies on (`list_stages` must see the uncommitted APPROVED row or
   `stages_to_unlock` computes nothing), so those call sites need restructuring.
2. **Serialize boundaries against the app's existing single-flight turn lock.** Cheap and uses
   machinery that already exists, but it couples the DB layer to an application-level lock and makes
   `db.py` depend on something above it.
3. **A process-wide write lock held for the boundary's duration.** Simple and local to `db.py`;
   blocks the event loop if a boundary is held across `mkdir` calls, which project creation does.
4. **Accept and detect.** Leave the design, but make a suppressed cross-thread commit *loud*: record
   the calling thread on entry and have `commit_unless_in_transaction` emit an event when it
   no-ops for a thread that is not the one holding the boundary. Does not fix the loss; does convert
   it from silent to reported, which is this programme's stated bar.

**DECIDED (operator, 2026-08-09): option 4, accept and detect.** The loss is not prevented; it is
made loud, which is this programme's stated bar. Options 1–3 each buy prevention with a cost this
project should not pay yet: option 1 breaks `approve_stage`'s dependence on reading its own
uncommitted write and forces restructuring in files other packages own; option 2 makes `db.py`
depend on an application-level lock above it; option 3 blocks the event loop across project
creation's `mkdir` calls.

**One trap to design around: `obs.record_event` calls `commit_unless_in_transaction`.** Emitting the
event from inside `commit_unless_in_transaction` therefore recurses infinitely. Do not solve that
with a re-entrancy flag — a flag makes the second, suppressed report silent, which is the defect
class again. Instead:

- `transaction()` records the owning thread on entry (`_TXN_OWNER[key] = threading.get_ident()`),
  under the existing lock, cleared on the same paths as `_TXN_DEPTH`.
- `commit_unless_in_transaction` increments a counter when it no-ops for a thread that is not the
  owner. It records nothing itself and never calls into `obs`.
- `transaction()` emits **one** `db.cross_thread_commit_suppressed` event at exit when that counter
  is non-zero, carrying the count and the owning thread. At exit there is no recursion risk, and one
  event naming N suppressed writes is more useful to an operator than N events.
- On the **rollback** path those suppressed writes were not merely delayed but discarded. Say so:
  the event's severity is `error` there and `warning` on the success path, and the message must
  distinguish the two. A boundary that silently ate another thread's write is exactly what this
  task exists to expose.
- [ ] **Write the failing test.** Two threads, one connection: one holds a boundary that rolls back
      while the other performs an ordinary write outside any boundary. Assert the outsider's write
      survives (options 1–3) or is reported (option 4). Observe it fail first.
- [ ] **Implement.** Per the decision.
- [ ] **Run it.** Full app suite green; the compatibility rule still holds outside a boundary.

---

### T14 — A-76: a second worker orphans a live turn

**A-76 (S3, silent).** `reconcile_orphaned_turns` runs inside `create_app`, which
`create_default_app` invokes once per worker process. It unconditionally marks **every** `running`
turn `orphaned` and unwedges its stage — it has no notion of which process owns a turn. Starting a
second worker declares an actively-streaming turn dead, flips its stage mid-flight and releases the
single-flight lock so a second turn can start against the same `raw_output.md`. Nothing pins
`--workers 1`.

- [ ] **Write the failing test.** Append to `tests/test_main.py`:

```python
def test_a_second_app_instance_does_not_orphan_a_live_turn(repo_root: Path):
    """FAULT. This is `uvicorn --workers 2` against a running turn."""
    from pipeline_app import db as db_mod

    db_path = repo_root / "pipeline.db"
    first = create_app(repo_root=repo_root, db_path=db_path)
    project_id = db_mod.create_project(first.state.conn, "a-1", "a", "generic",
                                       "2026-08-08T00:00:00+00:00")
    stage_row_id = db_mod.create_stage_row(first.state.conn, project_id, "ideation", "running")
    db_mod.create_turn(first.state.conn, stage_row_id, "running",
                       "2026-08-08T00:00:00+00:00", "e/1.jsonl")

    second = create_app(repo_root=repo_root, db_path=db_path)

    assert len(db_mod.list_running_turns(second.state.conn)) == 1
    assert db_mod.get_stage_by_row_id(second.state.conn, stage_row_id)["status"] == "running"


def test_a_skipped_sweep_is_distinguishable_from_a_clean_one(repo_root: Path):
    """DISTINGUISHABILITY. `orphaned_count == 0` means 'I swept and found
    nothing'. A second instance that never swept must not report the same
    thing -- that equivalence is the whole defect."""
    db_path = repo_root / "pipeline.db"
    first = create_app(repo_root=repo_root, db_path=db_path)
    assert first.state.orphaned_count == 0

    second = create_app(repo_root=repo_root, db_path=db_path)
    assert second.state.orphaned_count is None


def test_a_skipped_sweep_records_a_warning_event(repo_root: Path, tmp_path: Path, monkeypatch):
    """SURFACING."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "obs-logs")
    db_path = repo_root / "pipeline.db"
    first = create_app(repo_root=repo_root, db_path=db_path)
    create_app(repo_root=repo_root, db_path=db_path)
    rows = first.state.conn.execute(
        "SELECT * FROM events WHERE kind = 'app.startup.reconcile_skipped'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["severity"] == "warning"


def test_an_expired_lease_is_reclaimed_so_a_real_restart_still_sweeps(repo_root: Path):
    """A crashed instance must not block reconciliation forever."""
    from pipeline_app import main as main_mod

    db_path = repo_root / "pipeline.db"
    first = create_app(repo_root=repo_root, db_path=db_path)
    first.state.conn.execute(
        "UPDATE app_instances SET heartbeat_at = '2020-01-01T00:00:00+00:00' WHERE id = 1"
    )
    first.state.conn.commit()
    second = create_app(repo_root=repo_root, db_path=db_path)
    assert second.state.orphaned_count == 0  # swept, not skipped
```

- [ ] **Run it.** `test_a_second_app_instance_does_not_orphan_a_live_turn` fails with
      `status == "awaiting_review"` / zero running turns — A-76 reproduced exactly.
- [ ] **Implement (a).** Append to `schema.sql`:

```sql
-- Which process owns startup reconciliation. reconcile_orphaned_turns marks
-- EVERY running turn orphaned and unwedges its stage; run once per uvicorn
-- worker it declares an actively-streaming turn dead and releases the
-- single-flight lock mid-write (A-76). One row, one lease, one sweeper.
CREATE TABLE IF NOT EXISTS app_instances (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    owner_token  TEXT NOT NULL,
    claimed_at   TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL
);
```

- [ ] **Implement (b).** In `main.py`:

```python
RECONCILE_LEASE_SECONDS = 120


def _claim_reconcile_lease(conn, token: str, now: datetime,
                           lease_seconds: int = RECONCILE_LEASE_SECONDS) -> bool:
    """True if this process may run the startup sweep.

    A clean shutdown releases the lease (see the lifespan handler), so a genuine
    restart sweeps immediately. A crash leaves it, and the lease expires after
    `lease_seconds` -- long enough that uvicorn's other workers, which start
    within seconds, are correctly refused."""
    now_iso = now.isoformat(timespec="seconds")
    with db_mod.transaction(conn):
        cur = conn.execute(
            "INSERT OR IGNORE INTO app_instances (id, owner_token, claimed_at, heartbeat_at) "
            "VALUES (1, ?, ?, ?)", (token, now_iso, now_iso),
        )
        if cur.rowcount == 1:
            return True
        row = conn.execute("SELECT * FROM app_instances WHERE id = 1").fetchone()
        age = (now - datetime.fromisoformat(row["heartbeat_at"])).total_seconds()
        if age < lease_seconds:
            return False
        conn.execute(
            "UPDATE app_instances SET owner_token = ?, claimed_at = ?, heartbeat_at = ? "
            "WHERE id = 1 AND owner_token = ?", (token, now_iso, now_iso, row["owner_token"]),
        )
        return True


def _release_reconcile_lease(conn, token: str) -> None:
    try:
        conn.execute("DELETE FROM app_instances WHERE id = 1 AND owner_token = ?", (token,))
        conn.commit()
    except Exception as exc:  # noqa: BLE001 -- shutdown must not raise
        obs.log("app.lease_release_failed", level="warning",
                error=f"{type(exc).__name__}: {exc}")
```

and in `create_app`, replacing line 28-30:

```python
    app.state.instance_token = f"{os.getpid()}:{uuid.uuid4().hex[:8]}"
    if _claim_reconcile_lease(app.state.conn, app.state.instance_token,
                              datetime.now(timezone.utc)):
        app.state.orphaned_count = preflight.reconcile_orphaned_turns(
            app.state.conn, app.state.repo_root, app.state.stage_defs
        )
    else:
        # None, not 0: "I swept and found nothing" and "I never swept" are
        # different facts, and collapsing them is how A-76 stayed invisible.
        app.state.orphaned_count = None
        obs.record_event(
            app.state.conn, kind="app.startup.reconcile_skipped", severity="warning",
            source="main.create_app",
            message="another live app instance holds the reconcile lease; "
                    "skipped the startup orphan sweep",
            detail={"instance_token": app.state.instance_token},
        )
```

- [ ] **Run it.** All four pass. Full app suite green — every existing test builds its app against
      a fresh `tmp_path` database, so each claims the lease unopposed (verified: no test calls
      `create_app` twice against one `db_path`).
- [ ] **Commit.** `fix(main): lease startup reconciliation so a second worker cannot orphan a live turn (A-76)`

---

### T15 — A-83: a startup snapshot rendered beside a live probe of the same fact

**A-83 (S4, docs-drift).** `app.state.cli_available` is computed once in `create_app` and threaded
into every template as the global banner value, while `/doctor` additionally calls
`check_cli_available()` live on each request and renders both in the same response. Installing or
removing the CLI while the app runs makes the two disagree on one page, and nothing says one is a
snapshot.

Ten route call sites read `request.app.state.cli_available` and all ten belong to other packages,
so the fix has to keep that attribute a plain bool — and make it fresh.

- [ ] **Write the failing test.** Append to `tests/test_main.py`:

```python
def test_the_banner_and_the_doctor_panel_never_disagree_in_one_response(
        repo_root: Path, monkeypatch):
    """A-83: two answers to the same question in one HTML response. The probe
    flips on every call, so a snapshot and a live probe are guaranteed to
    differ -- unless both read one snapshot per request."""
    from fastapi.testclient import TestClient
    from pipeline_app import preflight

    (repo_root / ".claude" / "skills").mkdir(parents=True)
    flip = iter([True, False] * 20)
    monkeypatch.setattr(
        preflight, "check_cli_available",
        lambda *a, **k: {"available": next(flip), "path": None, "error": None},
    )
    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    client = TestClient(app)
    resp = client.get("/doctor")
    banner_online = "SYSTEM ONLINE" in resp.text
    panel_found = "NOT FOUND" not in resp.text
    assert banner_online == panel_found


def test_the_banner_reflects_a_cli_that_appeared_after_startup(repo_root: Path, monkeypatch):
    """Restart was the only way to reconcile the two, and nothing said so."""
    from fastapi.testclient import TestClient
    from pipeline_app import main as main_mod, preflight

    available = {"value": False}
    monkeypatch.setattr(
        preflight, "check_cli_available",
        lambda *a, **k: {"available": available["value"], "path": None, "error": "not found"},
    )
    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    client = TestClient(app)
    assert "CLI UNAVAILABLE" in client.get("/").text

    available["value"] = True
    app.state.cli_probe.invalidate()  # stand in for the TTL elapsing
    assert "SYSTEM ONLINE" in client.get("/").text
```

- [ ] **Run it.** The first fails (banner and panel disagree); the second fails with
      `AttributeError: cli_probe`.
- [ ] **Implement (a).** In `main.py`:

```python
class _CliProbe:
    """One cached answer to "is the Claude CLI installed", shared by the banner
    and the /doctor panel.

    Before this, the banner was a startup snapshot and /doctor was a live probe,
    so one response could carry two different answers to the same question and
    restart was the only way to reconcile them (A-83). The TTL exists only so
    `shutil.which` is not called on every request; correctness comes from both
    readers sharing one snapshot per request."""

    def __init__(self, ttl_seconds: float = 5.0) -> None:
        self._ttl = ttl_seconds
        self._at = 0.0
        self._value: dict | None = None

    def get(self) -> dict:
        now = time.monotonic()
        if self._value is None or now - self._at >= self._ttl:
            self._value = preflight.check_cli_available()
            self._at = now
        return self._value

    def invalidate(self) -> None:
        self._value = None
```

and in `create_app`, replacing line 31:

```python
    app.state.cli_probe = _CliProbe()
    app.state.cli_available = app.state.cli_probe.get()["available"]

    @app.middleware("http")
    async def _refresh_cli_banner(request, call_next):
        # Ten route modules read request.app.state.cli_available as a plain
        # bool and all ten belong to other packages, so the attribute stays a
        # bool -- it is just refreshed from the same snapshot /doctor reads,
        # once, at the top of the request.
        request.app.state.cli_available = request.app.state.cli_probe.get()["available"]
        return await call_next(request)
```

- [ ] **Implement (b).** In `routes/doctor.py`, drop the direct import and read the shared probe:

```python
-from pipeline_app.preflight import check_cli_available
...
-            "cli": check_cli_available(),
+            "cli": request.app.state.cli_probe.get(),
```

- [ ] **Run it.** Both pass. Full app suite green, including `test_routes_browse.py`'s
      `preflight.check_cli_available` monkeypatches — the probe calls it through the module
      attribute, so patching still takes effect (the previous `from ... import` binding in
      `doctor.py` did not respond to that patch at all).
- [ ] **Commit.** `fix(main): serve the CLI banner and the doctor panel from one probe (A-83)`

---

### T16 — D-48: no CSRF protection on any state-changing POST

**D-48 (S3, latent).** Every mutating route is a plain form POST with no token, no `SameSite`
cookie to rely on (there is no session at all), and no `Origin`/`Referer` check. A
`application/x-www-form-urlencoded` form POST is not preflighted, so any page open in the
operator's browser can fire `POST http://127.0.0.1:8420/skills/<name>/save` or `/discovery/run`
blind. The attacker never sees the response, but the git commit of attacker-supplied skill content
and the billed Bright Data run happen regardless.

- [ ] **Write the failing test.** Append to `tests/test_main.py`:

```python
def test_a_cross_origin_post_is_rejected(repo_root: Path):
    from fastapi.testclient import TestClient

    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    client = TestClient(app)
    resp = client.post("/discovery/run", headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403


def test_a_same_origin_post_is_not_rejected(repo_root: Path):
    """DISTINGUISHABILITY. Rejecting every POST would pass the test above and
    break the app -- the guard has to tell the two apart."""
    from fastapi.testclient import TestClient

    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    client = TestClient(app)
    resp = client.post("/discovery/run", headers={"Origin": "http://testserver"})
    assert resp.status_code != 403


def test_a_cross_origin_referer_is_rejected_when_origin_is_absent(repo_root: Path):
    from fastapi.testclient import TestClient

    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    client = TestClient(app)
    resp = client.post("/discovery/run", headers={"Referer": "https://evil.example/x"})
    assert resp.status_code == 403


def test_a_rejected_cross_origin_post_records_an_error_event(repo_root: Path, tmp_path,
                                                             monkeypatch):
    """SURFACING. A 403 the operator never sees is the same silence this whole
    package exists to end."""
    from fastapi.testclient import TestClient
    from pipeline_app import obs

    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "obs-logs")
    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    TestClient(app).post("/discovery/run", headers={"Origin": "https://evil.example"})
    rows = app.state.conn.execute(
        "SELECT * FROM events WHERE kind = 'security.cross_origin_post_rejected'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["severity"] == "error"
    assert "evil.example" in rows[0]["message"]


def test_a_get_is_never_rejected_for_its_origin(repo_root: Path):
    from fastapi.testclient import TestClient

    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    resp = TestClient(app).get("/doctor", headers={"Origin": "https://evil.example"})
    assert resp.status_code == 200
```

- [ ] **Run it.** The first, third and fourth fail — every POST is accepted today.
- [ ] **Implement.** In `main.py`, register a second middleware (registered after
      `_refresh_cli_banner` so it runs first — Starlette applies middleware in reverse
      registration order):

```python
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _same_host(candidate: str, host_header: str) -> bool:
    """A form POST carries Origin in every current browser; Referer is the
    fallback for the ones that strip it. Neither present means a non-browser
    client (curl, the test suite, the cron runner's own HTTP calls), which no
    cross-site attack can produce -- so that case is allowed, deliberately and
    with the residual gap recorded here rather than left implicit."""
    return urlsplit(candidate).netloc.casefold() == host_header.casefold()


@app.middleware("http")
async def _reject_cross_origin_mutations(request, call_next):
    if request.method in _MUTATING_METHODS:
        claimed = request.headers.get("origin") or request.headers.get("referer")
        host = request.headers.get("host", "")
        if claimed and not _same_host(claimed, host):
            obs.record_event(
                request.app.state.conn,
                kind="security.cross_origin_post_rejected", severity="error",
                source="main.csrf_guard",
                message=f"rejected {request.method} {request.url.path} claiming origin "
                        f"{claimed}",
                detail={"method": request.method, "path": request.url.path,
                        "claimed_origin": claimed, "host": host},
            )
            return PlainTextResponse("cross-origin request rejected", status_code=403)
    return await call_next(request)
```

- [ ] **Run it.** All five pass. Full app suite green — no existing test sends an `Origin` or
      `Referer` header (verified), and the guard allows requests carrying neither.
- [ ] **Commit.** `fix(main): reject cross-origin mutating requests (D-48)`

---

### T17 — `recent_events` on `/doctor` (the surface P15 renders)

Without this, every `events` row written by all sixteen packages is invisible unless someone opens
the database by hand — the same silence one layer down.

- [ ] **Write the failing test.** Append to `tests/test_obs.py`:

```python
def test_doctor_context_carries_unacknowledged_error_events_newest_first(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from pipeline_app.main import create_app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "obs-logs")
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    conn = app.state.conn

    obs.record_event(conn, kind="a.info", severity="info", source="s", message="ignored")
    obs.record_event(conn, kind="a.warn", severity="warning", source="s", message="ignored")
    old_id = obs.record_event(conn, kind="a.old", severity="error", source="s", message="stale")
    conn.execute("UPDATE events SET occurred_at = '2020-01-01T00:00:00+00:00' WHERE id = ?",
                 (old_id,))
    ack_id = obs.record_event(conn, kind="a.ack", severity="error", source="s", message="handled")
    conn.execute("UPDATE events SET acknowledged = 1 WHERE id = ?", (ack_id,))
    first = obs.record_event(conn, kind="adapter.fetch_failed", severity="error",
                             source="discovery_youtube", message="first",
                             detail={"handle": "@a"}, run_id=3)
    second = obs.record_event(conn, kind="run.aborted", severity="critical",
                              source="discovery_engine", message="second")
    conn.commit()

    captured = {}
    real = app.state.templates.TemplateResponse

    def spy(request, name, context, *args, **kwargs):
        captured.update(context)
        return real(request, name, context, *args, **kwargs)

    monkeypatch.setattr(app.state.templates, "TemplateResponse", spy)
    TestClient(app).get("/doctor")

    events = captured["recent_events"]
    assert [e["id"] for e in events] == [second, first]      # newest first, filtered
    assert events[1] == {
        "id": first, "occurred_at": events[1]["occurred_at"], "kind": "adapter.fetch_failed",
        "severity": "error", "source": "discovery_youtube", "message": "first",
        "detail": {"handle": "@a"}, "run_id": 3, "acknowledged": False,
    }


def test_recent_events_parses_detail_and_never_drops_a_malformed_one(tmp_path, monkeypatch):
    """A detail column written by a future caller as non-JSON must not make the
    event disappear -- losing the event is the defect, not the formatting."""
    conn_path = tmp_path / "pipeline.db"
    schema = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(conn_path, schema)
    c = db.get_connection(conn_path)
    try:
        c.execute(
            "INSERT INTO events (occurred_at, kind, severity, source, message, detail) "
            "VALUES (?, 'k', 'error', 's', 'm', 'not json')",
            (db._utcnow_iso(),),
        )
        c.commit()
        rows = db.list_unacknowledged_events(c, since_iso="2000-01-01T00:00:00+00:00")
        assert len(rows) == 1
        assert rows[0]["detail"] == {"raw": "not json"}
    finally:
        c.close()


def test_acknowledging_an_event_removes_it_from_the_doctor_list(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from pipeline_app.main import create_app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "obs-logs")
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    event_id = obs.record_event(app.state.conn, kind="k", severity="error",
                                source="s", message="m")
    client = TestClient(app)
    resp = client.post(f"/doctor/events/{event_id}/ack",
                       headers={"Origin": "http://testserver"})
    assert resp.status_code in (200, 303, 307)
    assert db.list_unacknowledged_events(
        app.state.conn, since_iso="2000-01-01T00:00:00+00:00") == []
```

- [ ] **Run it.** Fails: `KeyError: 'recent_events'`.
- [ ] **Implement (a).** Add to `db.py`:

```python
def list_unacknowledged_events(conn: sqlite3.Connection, *, since_iso: str,
                               limit: int = 50) -> list[dict]:
    """Unacknowledged error/critical events since `since_iso`, newest first.

    Returns plain dicts, not Rows: `detail` is parsed out of its JSON column so
    a template can iterate it, and the shape is the contract /doctor renders
    (see P1's published interface). A detail that will not parse becomes
    {"raw": <text>} -- losing the whole event over a formatting problem would be
    the same silence this table exists to end."""
    rows = conn.execute(
        "SELECT * FROM events WHERE acknowledged = 0 AND severity IN ('error','critical') "
        "AND occurred_at >= ? ORDER BY occurred_at DESC, id DESC LIMIT ?",
        (since_iso, limit),
    ).fetchall()
    out: list[dict] = []
    for row in rows:
        detail = None
        if row["detail"] is not None:
            try:
                parsed = json.loads(row["detail"])
                detail = parsed if isinstance(parsed, dict) else {"raw": row["detail"]}
            except (ValueError, TypeError):
                detail = {"raw": row["detail"]}
        out.append({
            "id": row["id"], "occurred_at": row["occurred_at"], "kind": row["kind"],
            "severity": row["severity"], "source": row["source"], "message": row["message"],
            "detail": detail, "run_id": row["run_id"],
            "acknowledged": bool(row["acknowledged"]),
        })
    return out


def acknowledge_event(conn: sqlite3.Connection, event_id: int) -> None:
    conn.execute("UPDATE events SET acknowledged = 1 WHERE id = ?", (event_id,))
    commit_unless_in_transaction(conn)
```

- [ ] **Implement (b).** In `routes/doctor.py`:

```python
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from pipeline_app import db as db_mod

router = APIRouter()

RECENT_EVENT_WINDOW_DAYS = 7


@router.get("/doctor")
def doctor_page(request: Request):
    repo_root = request.app.state.repo_root
    skills_dir = repo_root / ".claude" / "skills"
    skill_names = sorted(p.name for p in skills_dir.iterdir() if p.is_dir()) \
        if skills_dir.exists() else []
    since = (datetime.now(timezone.utc) - timedelta(days=RECENT_EVENT_WINDOW_DAYS)) \
        .isoformat(timespec="seconds")
    return request.app.state.templates.TemplateResponse(
        request, "doctor.html",
        {
            "repo_root": str(repo_root),
            "db_path": str(getattr(request.app.state, "db_path", "")),
            "cli": request.app.state.cli_probe.get(),
            "skill_names": skill_names,
            # None means "this instance never ran the startup sweep because
            # another one holds the lease" -- different from 0 (A-76).
            "orphaned_count": getattr(request.app.state, "orphaned_count", 0),
            "recent_events": db_mod.list_unacknowledged_events(
                request.app.state.conn, since_iso=since
            ),
            "active_nav": "doctor",
            "cli_available": request.app.state.cli_available,
        },
    )


@router.post("/doctor/events/{event_id}/ack")
def acknowledge(request: Request, event_id: int):
    db_mod.acknowledge_event(request.app.state.conn, event_id)
    return RedirectResponse("/doctor", status_code=303)
```

- [ ] **Run it.** All three pass.
- [ ] **Commit.** `feat(doctor): surface unacknowledged error events on the health page`

---

### T18 — F-26: two tests that assert on the value they injected into a mock

**F-26 (S2, silent).** `test_main.py`'s two tests monkeypatch `preflight.check_cli_available` and
then assert `app.state.cli_available` equals the boolean they injected — a one-attribute round trip
standing in for the app factory's 34 statements. DB init, router mounting, the startup sweep and
`pipeline.yaml` load failure are all unexercised; `main.py:56-57` is uncovered.

- [ ] **Delete** `pipeline-app/tests/test_main.py:15-30` in full — both `test_cli_available_true_when_binary_found` and `test_cli_available_false_when_missing`.
- [ ] **Write the replacement tests.** In `tests/test_main.py`:

```python
def test_cli_availability_is_recorded_on_app_state(repo_root: Path, monkeypatch):
    """Renamed from test_cli_available_true_when_binary_found. It still round-
    trips a mock, and that is all it claims to do -- the app factory's real
    behaviour is the four tests below."""
    from pipeline_app import preflight
    monkeypatch.setattr(preflight, "check_cli_available",
                        lambda *a, **k: {"available": True, "path": r"C:\fake\claude.CMD",
                                         "error": None})
    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    assert app.state.cli_available is True


def test_app_factory_creates_the_database_schema(repo_root: Path):
    """FAULT. 34 statements were covered by a one-attribute round trip."""
    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    tables = {r[0] for r in app.state.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"projects", "stages", "turns", "handles", "events", "creators",
            "schema_version", "app_instances"} <= tables


def test_app_factory_mounts_every_router(repo_root: Path):
    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    paths = {r.path for r in app.routes}
    for expected in ("/", "/doctor", "/discovery/handles", "/skills", "/inspector", "/browse"):
        assert any(p == expected or p.startswith(expected) for p in paths), expected


def test_app_factory_runs_the_startup_orphan_sweep(repo_root: Path):
    from pipeline_app import db as db_mod

    db_path = repo_root / "pipeline.db"
    schema = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db_mod.init_db(db_path, schema)
    seed = db_mod.get_connection(db_path)
    project_id = db_mod.create_project(seed, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    stage_row_id = db_mod.create_stage_row(seed, project_id, "ideation", "running")
    db_mod.create_turn(seed, stage_row_id, "running", "2026-08-08T00:00:00+00:00", "e/1.jsonl")
    seed.close()

    app = create_app(repo_root=repo_root, db_path=db_path)
    assert app.state.orphaned_count == 1
    assert db_mod.list_running_turns(app.state.conn) == []


def test_a_broken_pipeline_yaml_is_distinguishable_from_an_empty_one(
        tmp_path: Path, monkeypatch):
    """DISTINGUISHABILITY. `stages: []` is a legitimate empty topology. A
    pipeline.yaml that cannot be parsed must not produce the same app -- an app
    with zero stages and no complaint is how a config error becomes a
    mystery."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    empty = create_app(repo_root=tmp_path, db_path=tmp_path / "empty.db")
    assert empty.state.stage_defs == []

    (tmp_path / "pipeline.yaml").write_text("stages: [{id: a}]\n", encoding="utf-8")
    with pytest.raises(KeyError):
        create_app(repo_root=tmp_path, db_path=tmp_path / "broken.db")


def test_a_topology_load_failure_records_a_critical_event(tmp_path: Path, monkeypatch):
    """SURFACING. Today the traceback goes to a console Task Scheduler
    destroys."""
    from pipeline_app import db as db_mod, obs

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "obs-logs")
    (tmp_path / "pipeline.yaml").write_text("stages: [{id: a}]\n", encoding="utf-8")
    db_path = tmp_path / "pipeline.db"
    with pytest.raises(KeyError):
        create_app(repo_root=tmp_path, db_path=db_path)

    conn = db_mod.get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM events WHERE kind = 'app.topology_load_failed'").fetchall()
        assert len(rows) == 1
        assert rows[0]["severity"] == "critical"
    finally:
        conn.close()


def test_create_default_app_targets_the_repo_root_database(monkeypatch):
    """main.py:56-57 -- the two uncovered lines F-26 named."""
    from pipeline_app import main as main_mod

    seen = {}
    monkeypatch.setattr(main_mod, "create_app",
                        lambda *, repo_root, db_path: seen.update(
                            repo_root=repo_root, db_path=db_path))
    main_mod.create_default_app()
    assert seen["db_path"] == seen["repo_root"] / "pipeline-app" / "pipeline.db"
    assert (seen["repo_root"] / "pipeline-app" / "pipeline_app" / "main.py").exists()
```

- [ ] **Run it.** `test_a_topology_load_failure_records_a_critical_event` fails: no event, because
      `load_topology` runs before the connection exists and nothing catches it.
- [ ] **Implement.** In `main.py`, reorder so the database opens first and the topology load is
      reported before it propagates:

```python
    schema_path = PACKAGE_DIR / "schema.sql"
    db_mod.init_db(db_path, schema_path)
    app.state.conn = db_mod.get_connection(db_path)
    try:
        app.state.stage_defs = load_topology(repo_root / "pipeline.yaml")
    except Exception as exc:
        # The failure is loud but unrecorded: create_app dies with a traceback
        # into a console Windows Task Scheduler destroys. Record it, then let it
        # propagate -- booting with an empty topology would be worse (F-26).
        obs.record_event(
            app.state.conn, kind="app.topology_load_failed", severity="critical",
            source="main.create_app",
            message=f"could not load {repo_root / 'pipeline.yaml'}: "
                    f"{type(exc).__name__}: {exc}",
            detail={"path": str(repo_root / "pipeline.yaml"), "error": type(exc).__name__},
        )
        raise
```

- [ ] **Run it.** All seven pass. Full app suite green.
- [ ] **Commit.** `test(main): replace two mock round-trips with real app-factory coverage (F-26)`

---

## 4. Finding → test map

Three-Test-Rule roles are given for the six `silent` findings. `latent`, `docs-drift` and
`coverage-gap` findings get a named regression test but no mandatory triad.

| Finding | Mode | Test file | Named test | Role |
|---|---|---|---|---|
| **A-70** | silent | `test_db.py` | `test_transaction_rolls_back_every_statement_in_the_block` | **fault** |
| | | `test_db.py` | `test_a_failed_transaction_is_distinguishable_from_the_unwrapped_path` | **distinguishability** |
| | | `test_db.py` | `test_a_rolled_back_transaction_records_an_error_event` | **surfacing** |
| | | `test_db.py` | `test_leaf_helpers_still_commit_immediately_outside_a_transaction` | compatibility |
| | | `test_db.py` | `test_a_swallowed_inner_failure_still_rolls_the_outer_transaction_back` | regression |
| **A-71** | silent | `test_db.py` | `test_a_second_running_turn_is_rejected_by_the_storage_layer` | **fault** |
| | | `test_db.py` | `test_one_running_turn_coexists_with_any_number_of_finished_ones` | **distinguishability** |
| | | `test_db.py` | `test_a_rejected_concurrent_turn_is_visible_as_an_error_event` | **surfacing** |
| | | `test_db.py` | `test_migration_orphans_all_but_the_newest_running_turn` | migration |
| **A-76** | silent | `test_main.py` | `test_a_second_app_instance_does_not_orphan_a_live_turn` | **fault** |
| | | `test_main.py` | `test_a_skipped_sweep_is_distinguishable_from_a_clean_one` | **distinguishability** |
| | | `test_main.py` | `test_a_skipped_sweep_records_a_warning_event` | **surfacing** |
| | | `test_main.py` | `test_an_expired_lease_is_reclaimed_so_a_real_restart_still_sweeps` | regression |
| **B-73** | silent | `test_db.py` | `test_an_unknown_platform_is_rejected_at_the_storage_layer` | **fault** |
| | | `test_db.py` | `test_a_rejected_platform_leaves_no_row_unlike_a_valid_one` | **distinguishability** |
| | | `test_db.py` | `test_migration_quarantines_a_ghost_platform_row_and_records_it` | **surfacing** |
| | | `test_db.py` | `test_every_platform_the_adapter_registry_knows_is_accepted` | not-too-narrow |
| **B-82** | silent | `test_db.py` | `test_a_handle_is_downgraded_to_failing_after_three_consecutive_failures` | **fault** |
| | | `test_db.py` | `test_a_failing_handle_is_distinguishable_from_an_operator_disabled_one` | **distinguishability** |
| | | `test_db.py` | `test_downgrading_a_handle_records_an_error_event` | **surfacing** |
| | | `test_db.py` | `test_a_successful_fetch_lifts_a_failing_handle_back_to_validated` | reversibility |
| | | `test_db.py` | `test_clearing_failures_does_not_resurrect_a_handle_the_operator_invalidated` | regression |
| **F-26** | silent | `test_main.py` | `test_app_factory_creates_the_database_schema` | **fault** |
| | | `test_main.py` | `test_a_broken_pipeline_yaml_is_distinguishable_from_an_empty_one` | **distinguishability** |
| | | `test_main.py` | `test_a_topology_load_failure_records_a_critical_event` | **surfacing** |
| | | `test_main.py` | `test_app_factory_mounts_every_router` | coverage |
| | | `test_main.py` | `test_app_factory_runs_the_startup_orphan_sweep` | coverage |
| | | `test_main.py` | `test_create_default_app_targets_the_repo_root_database` | covers `main.py:56-57` |
| **A-47** | latent | `test_db.py` | `test_stages_status_rejects_a_value_outside_the_enum` | — |
| | | `test_db.py` | `test_update_stage_status_rejects_a_value_outside_the_enum` | — |
| | | `test_db.py` | `test_every_StageStatus_member_is_accepted_by_the_check` | not-too-narrow |
| | | `test_db.py` | `test_migration_coerces_a_ghost_stage_status_and_records_it` | migration |
| **A-72** | latent | `test_db.py` | `test_a_fresh_database_is_stamped_at_the_current_schema_version` | — |
| | | `test_db.py` | `test_an_existing_database_is_migrated_not_silently_left_behind` | — |
| | | `test_db.py` | `test_migrations_are_applied_exactly_once` | — |
| | | `test_db.py` | `test_a_database_from_a_newer_build_fails_loudly_instead_of_booting` | — |
| | | `test_db.py` | `test_a_migrated_database_has_the_same_schema_as_a_fresh_one` | drift guard |
| **A-75** | latent | `test_db.py` | `test_every_foreign_key_column_is_covered_by_an_index` | — |
| | | `test_db.py` | `test_turns_status_rejects_a_value_outside_the_vocabulary` | — |
| | | `test_db.py` | `test_every_turn_status_the_app_writes_is_accepted` | not-too-narrow |
| | | `test_db.py` | `test_deleting_a_project_cascades_to_its_stages_and_turns` | — |
| **A-83** | docs-drift | `test_main.py` | `test_the_banner_and_the_doctor_panel_never_disagree_in_one_response` | — |
| | | `test_main.py` | `test_the_banner_reflects_a_cli_that_appeared_after_startup` | — |
| **A-85** | latent | `test_main.py` | `test_app_shutdown_closes_the_connection_and_truncates_the_wal` | — |
| **B-72** | coverage-gap | `test_db.py` | `test_one_creator_can_own_handles_on_several_platforms` | — |
| | | `test_db.py` | `test_upsert_creator_is_idempotent_and_updates_the_display_name` | — |
| | | `test_db.py` | `test_an_unlinked_handle_is_distinguishable_from_a_linked_one` | — |
| | | `test_db.py` | `test_deleting_a_creator_does_not_delete_its_handles` | — |
| **D-48** | latent | `test_main.py` | `test_a_cross_origin_post_is_rejected` | — |
| | | `test_main.py` | `test_a_same_origin_post_is_not_rejected` | not-too-broad |
| | | `test_main.py` | `test_a_cross_origin_referer_is_rejected_when_origin_is_absent` | — |
| | | `test_main.py` | `test_a_rejected_cross_origin_post_records_an_error_event` | surfacing |
| | | `test_main.py` | `test_a_get_is_never_rejected_for_its_origin` | not-too-broad |

Frozen-interface tests (no finding of their own, but every package depends on them):
`test_log_writes_a_json_line_to_a_dated_file`, `test_log_does_not_raise_when_the_log_directory_cannot_be_created`,
`test_record_event_appends_a_row_and_returns_its_id`, `test_events_table_rejects_a_severity_outside_the_vocabulary`,
`test_record_event_returns_minus_one_when_the_events_table_is_missing`,
`test_record_event_falls_back_to_the_log_when_it_cannot_write`,
`test_record_event_does_not_raise_on_a_closed_connection`,
`test_doctor_context_carries_unacknowledged_error_events_newest_first`,
`test_recent_events_parses_detail_and_never_drops_a_malformed_one`,
`test_acknowledging_an_event_removes_it_from_the_doctor_list`.

---

## 5. Tests deleted or inverted

| File:line | Test | Verdict | Replacement |
|---|---|---|---|
| `pipeline-app/tests/test_main.py:15-21` | `test_cli_available_true_when_binary_found` | **Deleted and replaced.** It monkeypatches `preflight.check_cli_available` to return `{"available": True}` and asserts `app.state.cli_available is True` — an assertion on the value the test itself injected, standing in as coverage for the app factory's 34 statements (F-26). | `test_cli_availability_is_recorded_on_app_state` keeps the round trip under an honest name; `test_app_factory_creates_the_database_schema`, `test_app_factory_mounts_every_router`, `test_app_factory_runs_the_startup_orphan_sweep`, `test_a_broken_pipeline_yaml_is_distinguishable_from_an_empty_one`, `test_a_topology_load_failure_records_a_critical_event` and `test_create_default_app_targets_the_repo_root_database` do the actual work. |
| `pipeline-app/tests/test_main.py:24-30` | `test_cli_available_false_when_missing` | **Deleted, not replaced by a twin.** The `False` branch is a second round trip of the identical one-attribute assignment and adds nothing the `True` case does not already prove. The behaviour worth testing is A-83's — that the banner tracks a CLI that appears or disappears while the app runs — which `test_the_banner_reflects_a_cli_that_appeared_after_startup` covers for real. | `test_the_banner_reflects_a_cli_that_appeared_after_startup` (T15). |

**No test is inverted in this package** — neither of the two names describes a defect, so neither
needs the name-freezes-the-bug treatment.

**Handoff to P4 (not actionable here).** F-26's other half is
`pipeline-app/tests/test_turn_service.py:335-343`,
`test_scripting_turn_records_gate_results_in_frontmatter`: it mocks `run_gates_for_stage` to return
a literal and asserts the literal reaches frontmatter — useful plumbing coverage filed under a name
that reads as gate integration, with the gate as the mocked component. The audit's proposed rename
is `test_gate_results_are_copied_into_artifact_frontmatter`. That file is not in this package's
list; **P4 must make this edit or F-26 is only half closed.**

---

## 6. Published interface

Everything below is frozen once T18 lands. Downstream packages should be checked against this
block, not against the code.

### `pipeline_app.obs`

```python
def log(event: str, *, level: str = "info", **fields) -> None: ...
def record_event(conn, *, kind: str, severity: str, source: str,
                 message: str, detail: dict | None = None,
                 run_id: int | None = None) -> int: ...

LOG_DIR = <repo>/pipeline-app/logs          # monkeypatchable; log file is app-YYYY-MM-DD.log
VALID_SEVERITIES = ("info", "warning", "error", "critical")
```

- Neither function raises, ever. `record_event` returns the new row id, or **`-1`** on any
  failure, having written an `obs.record_event_failed` line through `log()` that still carries the
  original `kind`/`severity`/`source`/`message`. **The recorded thing is never lost.**
- `record_event` respects `db.transaction()`: called inside a boundary it does **not** commit.
- **Adoption rule (from the orchestration plan):** anywhere the code signals failure *only* by
  `print(..., file=sys.stderr)`, add `obs.record_event(..., severity="error")` beside it. Keep the
  print.

### `pipeline_app.db` — new public surface

```python
SCHEMA_VERSION: int
KNOWN_PLATFORMS  = ("youtube","bluesky","instagram","linkedin-profile",
                    "linkedin-company","facebook","x")
STAGE_STATUSES   = ("locked","ready","running","awaiting_review","approved","stale","no_artifact")
HANDLE_FAILURE_THRESHOLD = 3

class SchemaVersionError(RuntimeError): ...
class TransactionPoisonedError(RuntimeError): ...

@contextmanager
def transaction(conn) -> Iterator[sqlite3.Connection]: ...   # nests; rolls back + records an event
def commit_unless_in_transaction(conn) -> None: ...          # what leaf helpers call
def apply_migrations(conn) -> list[int]: ...

def upsert_creator(conn, *, slug: str, display_name: str) -> int: ...
def get_creator_by_slug(conn, slug: str) -> sqlite3.Row | None: ...
def link_handle_to_creator(conn, handle_id: int, creator_id: int) -> None: ...
def list_handles_for_creator(conn, creator_id: int) -> list[sqlite3.Row]: ...
def list_unlinked_handles(conn) -> list[sqlite3.Row]: ...

def record_handle_failure(conn, handle_id: int, *, now_iso: str,
                          threshold: int = HANDLE_FAILURE_THRESHOLD) -> str: ...
def clear_handle_failures(conn, handle_id: int) -> None: ...

def list_unacknowledged_events(conn, *, since_iso: str, limit: int = 50) -> list[dict]: ...
def acknowledge_event(conn, event_id: int) -> None: ...
```

**Behaviour every other package can rely on:** outside a `transaction()` block, every pre-existing
`db.py` helper commits immediately, exactly as before. Nothing about the existing signatures
changed.

### `recent_events` — the dict P15 binds to in `doctor.html`

`routes/doctor.py` passes `recent_events`: a **list of dicts**, unacknowledged `error`/`critical`
events from the last **7 days**, **newest first**, capped at **50**. Exact keys:

| Key | Type | Notes |
|---|---|---|
| `id` | `int` | Primary key. Use it for the ack form action: `POST /doctor/events/{id}/ack`. |
| `occurred_at` | `str` | Aware-UTC ISO-8601, seconds precision — e.g. `"2026-08-08T13:04:05+00:00"`. Already sorted; do not re-sort in the template. |
| `kind` | `str` | Dotted event kind, e.g. `"adapter.fetch_failed"`. |
| `severity` | `str` | Only ever `"error"` or `"critical"` in this list. |
| `source` | `str` | Reporting module/function, e.g. `"discovery_youtube"`. |
| `message` | `str` | One-line human summary. Escape it — it can contain vendor error text. |
| `detail` | `dict \| None` | **Already parsed** from the JSON column. `None` when the column is NULL. A value that will not parse as a JSON object becomes `{"raw": "<original text>"}` rather than being dropped. |
| `run_id` | `int \| None` | `discovery_runs.id` where the event belongs to a run. |
| `acknowledged` | `bool` | Always `False` in this list; present so the template binds one uniform shape. |

An empty list means **no unacknowledged errors in seven days** — render that as a positive state,
not as a missing panel. Also note `orphaned_count` is now `int | None`; **`None` means this
instance never ran the startup sweep** (another instance holds the lease, A-76) and must render
differently from `0`.

### Schema shipped

`events`, `creators` and `handles`' `creator_id` / `platform` CHECK / `UNIQUE(platform, handle)`
are **exactly** the orchestration plan's frozen DDL. Added beyond it, all owned by this package:

```
schema_version(id CHECK(id=1), version)                     -- A-72
app_instances(id CHECK(id=1), owner_token, claimed_at, heartbeat_at)  -- A-76
handles_quarantine(...)                                     -- B-73, rows the CHECK could not carry
handles.consecutive_failures INTEGER NOT NULL DEFAULT 0      -- B-82
handles.status CHECK IN ('pending','validating','validated','invalid','failing')  -- B-82
stages.status CHECK IN (STAGE_STATUSES)                      -- A-47
turns.status  CHECK IN ('running','complete','failed','aborted','orphaned')       -- A-75
ux_turns_single_running  UNIQUE(status) WHERE status='running'                    -- A-71
idx_turns_stage_row, idx_drh_run, idx_drh_handle, idx_handles_creator             -- A-75, B-72
ON DELETE CASCADE on stages.project_id, turns.stage_row_id,
   discovery_run_handles.run_id/.handle_id;  ON DELETE SET NULL on handles.creator_id  -- A-75
```

**P10:** `creators` is empty and every `handles.creator_id` is `NULL` when this package lands. Use
`db.upsert_creator` + `db.link_handle_to_creator`, and `db.list_unlinked_handles` to check your own
coverage.

**P8:** call `db.record_handle_failure(conn, handle_id, now_iso=...)` in the per-handle error
branch and `db.clear_handle_failures(conn, handle_id)` on a successful fetch. `platform` values
outside `db.KNOWN_PLATFORMS` now raise `sqlite3.IntegrityError` at insert — reject them in
`add_handle` **before** the billable validate spawn, which is B-73's route-level half.

---

## 7. Handoffs

1. **P4** — `tests/test_turn_service.py:335-343` rename, the other half of F-26. See [§5](#5-tests-deleted-or-inverted).
2. **P8** — route-level platform rejection (B-73) and the `record_handle_failure` /
   `clear_handle_failures` call sites (B-82).
3. **P10** — populate `creators` and `handles.creator_id` (B-72).
4. **P15** — render `recent_events` and the `orphaned_count is None` state in `doctor.html`
   (§6), plus `consecutive_failures` / the `failing` status on the handles page (B-82).
5. **Unassigned, one line.** `.gitignore` is in no package's file list, and `obs.log()` writes
   `pipeline-app/logs/app-YYYY-MM-DD.log`. Add `pipeline-app/logs/` to `.gitignore` — whoever
   picks it up first, before this package's first commit reaches a working tree that runs the app.
