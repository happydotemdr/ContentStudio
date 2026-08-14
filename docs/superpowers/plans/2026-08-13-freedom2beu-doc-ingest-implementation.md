# Freedom2BeU Document Ingest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `doc-ingest-app/`, a standalone cron-driven pipeline that converts the Freedom2BeU coaching document archive into a validated, versioned, read-only-locked Markdown corpus with a queryable FTS5 index, per `docs/superpowers/specs/2026-08-13-freedom2beu-doc-ingest-design.md`.

**Architecture:** A DB-claimed job queue (own SQLite db, own connection per worker) drives reclaim → scan → Drive-check → enqueue → claim → stage → convert → gauntlet → place/lock/index, run every 30 minutes by Windows Task Scheduler. Two independent mechanical gates (no LLM) validate content integrity and naming/placement before anything is written to the locked output tree.

**Tech Stack:** Python 3.14, stdlib `sqlite3` (WAL, own connection per worker), `firecrawl-py` SDK for local-file conversion (PDF/DOCX/XLSX/PPT only — TXT/MD pass through verbatim), `google-api-python-client` for Drive/Docs/Sheets export, `pypdf`/`python-docx`/`openpyxl` for independent (non-firecrawl) integrity metadata, `PyYAML` for frontmatter, Windows `icacls` via `subprocess` for read-only enforcement, `pytest` for tests.

## Global Constraints

- Input root `C:\Projects\Freedom2BeU_Google_Drive\coaching\` is **never written to** — read-only at every layer, verified by a real OS-level test (spec §13).
- Output root `C:\Projects\ContentStudio\Freedom2BeU\` — `converted/` (locked) + `_tmp/` (ephemeral staging), full app control.
- `doc-ingest-app/` is a standalone sibling to `pipeline-app/`: own venv, own `doc_ingest.db`, no shared code or DB with `pipeline_app`. Patterns are reimplemented, not imported (spec §3).
- No LLM-based validation anywhere in the gauntlet — every check is mechanical.
- Single file converted at a time per worker; parallelism is DB-claimed, never filesystem-level locking.
- A validated `.md` is never edited in place — new source content always produces a new version; the prior file stays locked.
- Cron floor is 30 minutes — `setup_ingest_task.py` registers exactly that, no faster.
- No UI in this phase — CLI query + regenerated flat manifest only.
- Every normative default below (tolerances, timeouts, pool size) is a **named config value**, not a hardcoded literal — see Task 1.
- `Freedom2BeU/` and `doc-ingest-app/doc_ingest.db*` are gitignored (spec §1) — this corpus contains real client names and private session content.

---

## File Structure

```
doc-ingest-app/
  pytest.ini
  setup.py
  requirements.txt
  requirements-dev.txt
  SETUP.md                      manual one-time setup: firecrawl-py auth, Google OAuth
  doc_ingest/
    __init__.py
    config.py                   Config dataclass, YAML + env loading, all tunables
    db.py                       schema, get_connection, transaction(), apply_migrations
    naming.py                   pure functions: sanitize, dest path, long-path shortening, collisions
    scan.py                     read-only tree walk, magic-byte sniff, classification
    sync.py                     bridges scan.py into source_files, tracks missing
    metadata_readers.py         independent (non-firecrawl) page/word/sheet/row counters
    convert.py                  firecrawl-py SDK dispatch for local files (pdf/docx/xlsx/ppt only)
    drive_client.py             OAuth, batched metadata, Docs/Sheets export, retry/backoff
    drive_sync.py                parses .gdoc/.gsheet stubs, syncs Drive modifiedTime into source_files
    frontmatter.py               build + YAML-safe serialize
    gauntlet.py                  Gate 1 (content integrity) + Gate 2 (naming/placement)
    lock.py                      icacls deny-write (account + OWNER RIGHTS) + read-only attribute, verify
    jobs.py                      enqueue / claim / heartbeat / reclaim
    worker.py                    orchestrates one job: stage -> convert -> gauntlet -> place/lock/index
    query.py                     CLI: search the FTS5 index
    manifest.py                  regenerate flat CSV/Markdown manifest
  scripts/
    setup_ingest_task.py        registers ContentStudio-DocIngest (mirrors setup_discovery_task.py)
    run_ingest_cron.py          cron entry point: reclaim -> resume -> scan -> drive-check -> enqueue -> drain -> manifest
  tests/
    conftest.py                 (includes the lock_test_dir fixture, Task 13)
    .lock_test_scratch/         gitignored -- real icacls-locked test fixtures, Task 13
    test_config.py
    test_db.py
    test_naming.py
    test_scan.py
    test_sync.py
    test_metadata_readers.py
    test_convert.py
    test_drive_client.py
    test_drive_sync.py
    test_frontmatter.py
    test_gauntlet_gate1.py
    test_gauntlet_gate2.py
    test_lock.py
    test_jobs.py
    test_worker.py
    test_query.py
    test_manifest.py
    test_setup_ingest_task.py
    test_run_ingest_cron.py
    test_integration.py
    test_readonly_enforcement.py

ContentStudio/Freedom2BeU/       (gitignored, created at runtime)
  converted/
  _tmp/

.claude/
  hooks/
    protect_freedom2beu_output.py
  settings.json                  (modified: new PreToolUse entry)

tests/                           (repo ROOT suite, not doc-ingest-app/tests/)
  test_protect_freedom2beu_output.py   loaded via importlib.util.spec_from_file_location,
                                        same convention as the existing test_protect_briefs.py
```

**Interfaces contract used throughout this plan** (so later tasks can be read standalone; this is the corrected, final version of every signature — earlier task sections cite these by task number where they're introduced):
- `Config` (config.py): frozen dataclass, one field per tunable in Task 1's table.
- `db.get_connection(db_path: Path) -> sqlite3.Connection` — WAL, `isolation_level=None`, `busy_timeout=5000`.
- `db.transaction(conn)` — context manager, nests, explicit `BEGIN`/`COMMIT`/`ROLLBACK` (not sqlite3's implicit control, since `isolation_level=None`).
- `naming.build_dest_rel_path(source_rel_path: str, version: int, cfg: Config, prefix_len: int = 0) -> str`, `naming.resolve_collision(dest_rel_path: str, is_taken) -> tuple[str, bool]`
- `scan.classify(extension: str, sniffed: str | None) -> str` — one of `convertible`/`catalog_only`/`excluded_media`/`gdoc_pointer`/`blocked_unknown`
- `sync.sync_source_files(conn, input_root: Path) -> dict` — counts by classification; marks previously-seen-now-absent rows `missing`
- `convert.convert_local_file(staged_path: Path, source_type: str, cfg: Config) -> ConversionResult` — no `output_tmp_path`; the SDK returns markdown in memory
- `metadata_readers.read_pdf_page_count`, `read_docx_word_count`, `read_docx_table_count`, `read_xlsx_sheet_and_row_counts` — no single `read_independent_metadata` entry point; `worker._independent_metadata` composes these per source type
- `gauntlet.run_gate1(source_type: str, source_size_bytes: int, assembled_markdown: str, independent_metadata: dict, cfg: Config) -> GauntletResult` — computes every OUTPUT-side count itself from `assembled_markdown`
- `gauntlet.run_gate2(conn, source_rel_path: str, source_file_id: int, version: int, cfg: Config) -> tuple[GauntletResult, str | None]` — second element is the resolved dest path on success; internally threads `prefix_len` through to `naming.build_dest_rel_path`
- `lock.apply_readonly_lock(path: Path) -> None` (idempotent at the call level via an internal `verify_locked()` check, not at the icacls-call level), `lock.verify_locked(path: Path) -> bool`
- `jobs.claim_job(conn, worker_id: str) -> int | None`, `jobs.heartbeat(conn, job_id: int, worker_id: str) -> None`, `jobs.reclaim_stale_jobs(conn, cfg: Config, tmp_root: Path) -> list[int]`, `jobs.enqueue_pending_jobs(conn) -> int` (Task 22 extends the last two: `classification IN ('convertible','gdoc_pointer')`)
- `drive_client.build_batch_metadata(service, doc_ids: list[str], cfg) -> dict[str, dict]`, `export_google_doc(service, doc_id, dest_path, cfg) -> ConversionResult`, `export_google_sheet(...)`, `build_default_service(cfg)` (Task 22)
- `drive_sync.sync_drive_metadata(conn, service, cfg) -> int` (Task 22)
- `worker.process_job(conn, job_id: int, cfg: Config, worker_id: str, drive_service_factory=None) -> None`, `worker.resume_unlocked_conversions(conn, cfg) -> list[int]`

---

## Task 0: Scaffold `doc-ingest-app`

**Files:**
- Create: `doc-ingest-app/pytest.ini`, `doc-ingest-app/setup.py`, `doc-ingest-app/requirements.txt`, `doc-ingest-app/requirements-dev.txt`
- Create: `doc-ingest-app/doc_ingest/__init__.py`
- Create: `doc-ingest-app/tests/__init__.py`, `doc-ingest-app/tests/conftest.py`
- Create: `doc-ingest-app/tests/test_smoke.py`
- Modify: `.gitignore` (repo root)

**Interfaces:**
- Produces: a working `pytest` invocation from `doc-ingest-app/`, and the guard fixtures (`allow_subprocess`, `allow_network` markers) every later test task relies on.

- [ ] **Step 1: Create directory skeleton**

```bash
mkdir -p doc-ingest-app/doc_ingest doc-ingest-app/scripts doc-ingest-app/tests
```

- [ ] **Step 2: Write `requirements.txt`**

```
pyyaml==6.0.*
pypdf==6.10.*
python-docx==1.1.*
openpyxl==3.1.*
firecrawl-py==2.*
google-api-python-client==2.*
google-auth==2.*
google-auth-oauthlib==1.*
google-auth-httplib2==0.*
tzdata>=2024.1
```

- [ ] **Step 3: Write `requirements-dev.txt`**

```
-r requirements.txt
pytest==8.3.*
pytest-cov==7.1.*
hypothesis==6.*
```

- [ ] **Step 4: Write `setup.py`**

```python
"""Distribution metadata for doc-ingest-app.

install_requires is parsed from requirements.txt so the two manifests cannot
drift, mirroring pipeline-app/setup.py's rationale. This app is standalone --
no dependency on pipeline_app, no shared install."""
from pathlib import Path

from setuptools import find_packages, setup

HERE = Path(__file__).resolve().parent


def _runtime_requirements() -> list[str]:
    out = []
    for raw in (HERE / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            out.append(line)
    return out


setup(
    name="doc-ingest-app",
    version="0.1.0",
    packages=find_packages(include=["doc_ingest", "doc_ingest.*"]),
    install_requires=_runtime_requirements(),
    python_requires=">=3.14",
)
```

- [ ] **Step 5: Write `pytest.ini`**

```ini
; App suite. Run from this directory: `cd doc-ingest-app && python -m pytest`.
; This file makes doc-ingest-app its own rootdir, mirroring the pipeline-app /
; repo-root split documented in CLAUDE.md.
[pytest]
testpaths = tests
addopts = --strict-markers
markers =
    allow_network: this test may make a real outbound request. Justify in the docstring.
    allow_subprocess: this test may spawn a real child process (icacls). Justify in the docstring.

filterwarnings =
    error
    ignore::ResourceWarning
```

- [ ] **Step 6: Write `doc_ingest/__init__.py`** (empty) and `tests/__init__.py` (empty)

- [ ] **Step 7: Write `tests/conftest.py`**

```python
"""doc-ingest-app suite conftest: subprocess/network guards + shared fixtures."""
from __future__ import annotations

import subprocess
import sqlite3
import urllib.request
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1]

_real_subprocess_run = subprocess.run
_real_urlopen = urllib.request.urlopen


@pytest.fixture(autouse=True)
def _block_unmarked_subprocess(request, monkeypatch):
    if request.node.get_closest_marker("allow_subprocess"):
        yield
        return

    def _blocked_run(*args, **kwargs):
        raise RuntimeError(
            "subprocess.run called from an unmarked test -- add "
            "@pytest.mark.allow_subprocess with a docstring justification, "
            "or stub the call."
        )

    monkeypatch.setattr(subprocess, "run", _blocked_run)
    yield
    monkeypatch.setattr(subprocess, "run", _real_subprocess_run)


@pytest.fixture(autouse=True)
def _block_unmarked_network(request, monkeypatch):
    """Blocks urllib AND requests/httpx -- urllib alone (an earlier version
    of this guard) doesn't cover what this app's own dependencies actually
    use: firecrawl-py and google-auth's credential refresh are both built on
    `requests`, not urllib, so a forgotten mock there would make a real,
    possibly billed, call while the test still passes silently. Mirrors
    pipeline-app/tests/conftest.py's guard shape."""
    if request.node.get_closest_marker("allow_network"):
        yield
        return

    def _blocked(what: str):
        def _raise(*args, **kwargs):
            raise RuntimeError(
                f"{what} called from a test with no stub -- add "
                "@pytest.mark.allow_network with a docstring justification, "
                "or mock the call (firecrawl.Firecrawl, the Drive `service` "
                "object, etc.)."
            )
        return _raise

    monkeypatch.setattr(urllib.request, "urlopen", _blocked("urllib.request.urlopen"))

    try:
        import requests
        import requests.sessions
    except ImportError:
        pass
    else:
        for name in ("request", "get", "post", "put", "patch", "delete", "head"):
            if hasattr(requests, name):
                monkeypatch.setattr(requests, name, _blocked(f"requests.{name}"))
        monkeypatch.setattr(requests.sessions.Session, "request", _blocked("requests.Session.request"))

    try:
        import httpx
    except ImportError:
        pass
    else:
        monkeypatch.setattr(httpx.Client, "request", _blocked("httpx.Client.request"))
        monkeypatch.setattr(httpx, "request", _blocked("httpx.request"))

    yield
    monkeypatch.setattr(urllib.request, "urlopen", _real_urlopen)


@pytest.fixture
def tmp_db_path(tmp_path) -> Path:
    return tmp_path / "doc_ingest_test.db"


@pytest.fixture
def conn(tmp_db_path):
    from doc_ingest import db

    connection = db.init_db(tmp_db_path)
    yield connection
    connection.close()
```

- [ ] **Step 8: Write a smoke test, `tests/test_smoke.py`**

```python
def test_suite_runs():
    assert True
```

- [ ] **Step 9: Run the suite**

```bash
cd doc-ingest-app && python -m pytest -v
```

Expected: `test_smoke.py::test_suite_runs PASSED` (conftest fixtures load without error even though `doc_ingest.db` doesn't exist yet — `conn` fixture isn't used by this test).

- [ ] **Step 10: Update `.gitignore`** (repo root) — add a new section

```gitignore
# Freedom2BeU document-ingest app (converted output + own db -- real client
# names and private coaching-session content, must never land in git history)
Freedom2BeU/
doc-ingest-app/doc_ingest.db
doc-ingest-app/doc_ingest.db-wal
doc-ingest-app/doc_ingest.db-shm
doc-ingest-app/.venv/
doc-ingest-app/doc_ingest/__pycache__/
doc-ingest-app/doc_ingest/**/__pycache__/
doc-ingest-app/tests/__pycache__/
doc-ingest-app/doc_ingest_app.egg-info/
doc-ingest-app/client_secret.json
doc-ingest-app/token.json
doc-ingest-app/.coverage
```

- [ ] **Step 11: Commit**

```bash
git add doc-ingest-app/pytest.ini doc-ingest-app/setup.py doc-ingest-app/requirements.txt doc-ingest-app/requirements-dev.txt doc-ingest-app/doc_ingest/__init__.py doc-ingest-app/tests/__init__.py doc-ingest-app/tests/conftest.py doc-ingest-app/tests/test_smoke.py .gitignore
git commit -m "chore(doc-ingest): scaffold standalone app, own venv/test suite"
```

---

## Task 1: Config module

**Files:**
- Create: `doc-ingest-app/doc_ingest/config.py`
- Test: `doc-ingest-app/tests/test_config.py`

**Interfaces:**
- Produces: `Config` frozen dataclass and `load_config(path: Path | None = None) -> Config`, imported by every module from Task 6 onward.

Every tunable the spec's §15 "Open items" flagged as config-not-hardcoded gets a field here, with a calibrated default and a one-line rationale. All are overridable via a YAML file or env var (env wins, matching `pipeline_config`'s precedent of explicit, inspectable config rather than magic numbers buried in call sites).

| Field | Default | Rationale |
|---|---|---|
| `input_root` | `C:\Projects\Freedom2BeU_Google_Drive\coaching\` | spec §1 |
| `output_root` | `C:\Projects\ContentStudio\Freedom2BeU\` | spec §1 |
| `worker_pool_size` | 4 | I/O-bound work (spec §5); modest fixed pool |
| `job_timeout_s` | 600 | one hung conversion can't stall a whole run (spec §11) |
| `reclaim_heartbeat_interval_s` | 30 | mirrors `discovery_engine`'s heartbeat cadence |
| `reclaim_staleness_threshold_s` | 180 | 6 missed heartbeats before reclaim (spec §4 step 1) |
| `run_time_budget_s` | 1500 | 25 min, leaves headroom under the 30-min cron floor (spec §11) |
| `long_path_threshold_chars` | 240 | safety margin under Windows' 260-char MAX_PATH (spec §6) |
| `oversized_file_cap_bytes` | 52428800 (50 MiB) | firecrawl's documented per-file upload cap (SDK, same limit as the CLI) |
| `drive_export_size_cap_bytes` | 10485760 (10 MiB) | Drive API's export size cap (spec §9) |
| `word_count_tolerance_pct` | 0.15 | DOCX/GDOC word-count parity band (spec §8) |
| `row_count_tolerance_pct` | 0.05 | XLSX/GSheet row-count parity band (spec §8) |
| `sheet_count_tolerance` | 0 | sheet counts must match exactly |
| `size_ratio_floor` | 0.05 | DOCX/XLSX/TXT/MD only (spec §8) — markdown must be >=5% of source bytes |
| `scanned_pdf_words_per_page_floor` | 3.0 | below this, flag `likely_scanned_no_text_layer` (spec §8) |
| `replacement_char_ratio_max` | 0.01 | botched-encoding detector (spec §8) |
| `drive_metadata_batch_size` | 100 | Google batch API's per-batch request cap (spec §9, §15) |
| `drive_retry_max_attempts` | 5 | 429/5xx backoff (spec §9) |
| `drive_retry_base_delay_s` | 2.0 | exponential backoff base |

`firecrawl_binary` from the original draft of this table is gone — Task 9 switched from shelling out to the `firecrawl` CLI to the `firecrawl-py` Python SDK, which resolves its own credential (`FIRECRAWL_API_KEY` in the environment) and needs no binary path.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from pathlib import Path

from doc_ingest.config import Config, load_config


def test_defaults_are_populated_without_a_config_file(tmp_path):
    cfg = load_config(tmp_path / "nonexistent.yaml")
    assert cfg.worker_pool_size == 4
    assert cfg.reclaim_staleness_threshold_s == 180
    assert cfg.oversized_file_cap_bytes == 52428800


def test_yaml_file_overrides_defaults(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("worker_pool_size: 8\njob_timeout_s: 120\n", encoding="utf-8")
    cfg = load_config(cfg_path)
    assert cfg.worker_pool_size == 8
    assert cfg.job_timeout_s == 120
    assert cfg.reclaim_staleness_threshold_s == 180  # untouched field keeps default


def test_env_var_overrides_yaml(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("worker_pool_size: 8\n", encoding="utf-8")
    monkeypatch.setenv("DOC_INGEST_WORKER_POOL_SIZE", "2")
    cfg = load_config(cfg_path)
    assert cfg.worker_pool_size == 2


def test_config_is_frozen():
    cfg = load_config(Path("nonexistent.yaml"))
    with pytest.raises(Exception):
        cfg.worker_pool_size = 99
```

Add `import pytest` at the top of the file.

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'doc_ingest.config'`

- [ ] **Step 3: Write `doc_ingest/config.py`**

```python
"""All doc-ingest-app tunables in one place -- see the implementation plan's
Task 1 table for the rationale behind each default. Precedence: env var >
YAML file > default."""
from __future__ import annotations

import dataclasses
import os
import typing
from pathlib import Path

import yaml

_ENV_PREFIX = "DOC_INGEST_"


@dataclasses.dataclass(frozen=True)
class Config:
    input_root: Path = Path(r"C:\Projects\Freedom2BeU_Google_Drive\coaching")
    output_root: Path = Path(r"C:\Projects\ContentStudio\Freedom2BeU")
    worker_pool_size: int = 4
    job_timeout_s: int = 600
    reclaim_heartbeat_interval_s: int = 30
    reclaim_staleness_threshold_s: int = 180
    run_time_budget_s: int = 1500
    long_path_threshold_chars: int = 240
    oversized_file_cap_bytes: int = 52428800
    drive_export_size_cap_bytes: int = 10485760
    word_count_tolerance_pct: float = 0.15
    row_count_tolerance_pct: float = 0.05
    sheet_count_tolerance: int = 0
    size_ratio_floor: float = 0.05
    scanned_pdf_words_per_page_floor: float = 3.0
    replacement_char_ratio_max: float = 0.01
    drive_metadata_batch_size: int = 100
    drive_retry_max_attempts: int = 5
    drive_retry_base_delay_s: float = 2.0

    @property
    def converted_root(self) -> Path:
        return self.output_root / "converted"

    @property
    def tmp_root(self) -> Path:
        return self.output_root / "_tmp"


# NOTE: this module keeps `from __future__ import annotations` for consistency
# with the rest of the codebase (see pipeline_app/*.py), which means
# `dataclasses.fields(Config)[i].type` is the *string* "int"/"float"/"Path",
# not the real type object -- `f.type is int` is never true under PEP 563.
# typing.get_type_hints() is the one API that actually resolves those strings
# back to real type objects (it re-evaluates each annotation against the
# defining module's globals), so it's used here instead of a plain
# dataclasses.fields() walk.
_FIELD_TYPES = typing.get_type_hints(Config)


def _coerce(name: str, raw: str):
    field_type = _FIELD_TYPES[name]
    if field_type is int:
        return int(raw)
    if field_type is float:
        return float(raw)
    if field_type is Path:
        return Path(raw)
    return raw


def load_config(path: Path | None = None) -> Config:
    values: dict = {}
    if path is not None and path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for key, value in raw.items():
            if key in _FIELD_TYPES:
                values[key] = _coerce(key, str(value)) if not isinstance(value, (int, float)) or _FIELD_TYPES[key] is Path else value

    for field_name in _FIELD_TYPES:
        env_key = _ENV_PREFIX + field_name.upper()
        if env_key in os.environ:
            values[field_name] = _coerce(field_name, os.environ[env_key])

    return Config(**values)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_config.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/config.py doc-ingest-app/tests/test_config.py
git commit -m "feat(doc-ingest): add Config with every tunable named and defaulted"
```

---

## Task 2: DB schema + connection factory

**Files:**
- Create: `doc-ingest-app/doc_ingest/db.py`
- Test: `doc-ingest-app/tests/test_db.py`

**Interfaces:**
- Consumes: nothing yet (this is the foundation).
- Produces: `get_connection(db_path) -> sqlite3.Connection`, `init_db(db_path) -> sqlite3.Connection`, the full schema. Every later task's tests use the `conn` fixture from Task 0, which calls `init_db`.

**Schema** (full, all five tables — this is the authoritative reference for every column name used in later tasks):

```sql
CREATE TABLE IF NOT EXISTS schema_version (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS source_files (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    rel_path            TEXT NOT NULL UNIQUE,   -- relative to input_root, verbatim
    extension           TEXT NOT NULL,          -- lowercased; '' if none
    sniffed_signature   TEXT,                   -- 'pdf'|'png'|'jpg'|'mov'|'mp4'|'unknown'|NULL
    classification       TEXT NOT NULL CHECK (classification IN
        ('convertible','catalog_only','excluded_media','gdoc_pointer','blocked_unknown','missing')),
    size_bytes          INTEGER,
    mtime               TEXT,                   -- local files only, ISO8601
    content_hash        TEXT,                   -- sha256, local files only
    doc_id              TEXT,                   -- gdoc/gsheet stub only
    resource_key        TEXT,
    drive_modified_time TEXT,                   -- ISO8601, from Drive API (never the stub's mtime)
    drive_mime_type     TEXT,
    first_seen_at       TEXT NOT NULL,
    last_seen_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source_files_classification ON source_files(classification);

CREATE TABLE IF NOT EXISTS conversion_jobs (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_id              INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
    status                      TEXT NOT NULL CHECK (status IN
        ('pending','claimed','converting','placing','complete','failed')),
    worker_id                   TEXT,
    claimed_at                  TEXT,
    heartbeat_at                TEXT,
    finished_at                 TEXT,
    failure_reason              TEXT,
    tmp_dir                     TEXT,            -- per-job staging subdir under _tmp/
    -- Recorded at claim time from source_files' current values, so enqueue can
    -- tell "already failed at exactly this version" from "source changed since
    -- the last failure" without a second table (Task 8).
    source_hash_at_attempt      TEXT,
    drive_modified_time_at_attempt TEXT,
    created_at                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversion_jobs_status ON conversion_jobs(status);
CREATE INDEX IF NOT EXISTS idx_conversion_jobs_source_file ON conversion_jobs(source_file_id);

CREATE TABLE IF NOT EXISTS conversions (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_id                  INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
    job_id                          INTEGER REFERENCES conversion_jobs(id) ON DELETE SET NULL,
    version_number                  INTEGER NOT NULL,
    output_path                     TEXT NOT NULL,   -- relative to converted/
    status                          TEXT NOT NULL CHECK (status IN ('current','superseded')),
    source_type                     TEXT NOT NULL CHECK (source_type IN
        ('pdf','docx','xlsx','gdoc','gsheet','txt','md','ppt')),
    source_hash_at_conversion       TEXT,             -- sha256, or Drive headRevisionId for gdoc/gsheet
    drive_modified_time_at_conversion TEXT,            -- gdoc/gsheet only; drives the newer-than check
    conversion_tool                 TEXT NOT NULL CHECK (conversion_tool IN
        ('firecrawl-parse','google-docs-export','google-docs-export-docx-fallback',
         'google-sheets-export','passthrough')),
    converted_at                    TEXT NOT NULL,
    gauntlet_passed_at              TEXT,
    locked_confirmed_at             TEXT,             -- NULL until step 9(d) verified (spec §4)
    page_count                      INTEGER,
    word_count                      INTEGER,
    sheet_count                     INTEGER,
    row_count_total                 INTEGER,
    UNIQUE(source_file_id, version_number)
);
CREATE INDEX IF NOT EXISTS idx_conversions_status ON conversions(status);
CREATE INDEX IF NOT EXISTS idx_conversions_converted_at ON conversions(converted_at);
CREATE INDEX IF NOT EXISTS idx_conversions_source_type ON conversions(source_type);

CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    source_file_id  INTEGER REFERENCES source_files(id) ON DELETE SET NULL,
    conversion_id   INTEGER REFERENCES conversions(id) ON DELETE SET NULL,
    details_json    TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS conversions_fts USING fts5(
    conversion_id UNINDEXED,
    source_rel_path,
    output_path UNINDEXED,
    body
);
```

Note on "source folder path" indexing (spec §12): `source_files.rel_path` is already `UNIQUE`-indexed, which SQLite can use for a `LIKE 'folder/%'` prefix scan — no separate folder-path index needed.

Note on `conversion_tool`: `'google-docs-export-docx-fallback'` is a distinct value from `'google-docs-export'`, not a variant recorded some other way — Task 14's `export_google_doc` returns exactly that string when the markdown export is unavailable or over Drive's size cap and it falls back to a `.docx` export routed through the DOCX gauntlet path (spec §9). Leaving it out of the `CHECK` would make every such fallback conversion fail its own `INSERT`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db.py
from doc_ingest import db


def test_init_db_creates_all_tables(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
        ).fetchall()
    }
    assert {"schema_version", "source_files", "conversion_jobs", "conversions", "events"} <= tables
    version = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
    assert version == 1
    conn.close()


def test_init_db_creates_fts5_virtual_table(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    conn.execute("INSERT INTO conversions_fts (conversion_id, source_rel_path, output_path, body) VALUES (1, 'a/b.pdf', 'a/b.pdf.md', 'hello world')")
    row = conn.execute("SELECT source_rel_path FROM conversions_fts WHERE conversions_fts MATCH 'hello'").fetchone()
    assert row[0] == "a/b.pdf"
    conn.close()


def test_get_connection_uses_wal_and_explicit_isolation(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"
    assert conn.isolation_level is None
    conn.close()


def test_source_files_rel_path_is_unique(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
        "VALUES ('a.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
    )
    conn.commit()
    import sqlite3
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
            "VALUES ('a.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
        )
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_db.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'doc_ingest.db'`

- [ ] **Step 3: Write `doc_ingest/db.py`** (schema + connection factory only — `transaction()` and migrations land in Task 3)

```python
"""doc-ingest-app's own schema, connection factory, and transaction boundary.
Reimplemented rather than imported from pipeline_app/db.py, deliberately: the
two apps share no database and no code (spec §3), and this app's concurrency
model -- one SQLite connection per worker, never shared across threads -- is
simpler than pipeline_app's shared-connection design and does not need its
cross-thread commit-suppression machinery. See db.transaction (Task 3) for
the one-paragraph version of that reasoning."""
from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS source_files (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    rel_path            TEXT NOT NULL UNIQUE,
    extension           TEXT NOT NULL,
    sniffed_signature   TEXT,
    classification      TEXT NOT NULL CHECK (classification IN
        ('convertible','catalog_only','excluded_media','gdoc_pointer','blocked_unknown','missing')),
    size_bytes          INTEGER,
    mtime               TEXT,
    content_hash        TEXT,
    doc_id              TEXT,
    resource_key        TEXT,
    drive_modified_time TEXT,
    drive_mime_type     TEXT,
    first_seen_at       TEXT NOT NULL,
    last_seen_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source_files_classification ON source_files(classification);

CREATE TABLE IF NOT EXISTS conversion_jobs (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_id                  INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
    status                          TEXT NOT NULL CHECK (status IN
        ('pending','claimed','converting','placing','complete','failed')),
    worker_id                       TEXT,
    claimed_at                      TEXT,
    heartbeat_at                    TEXT,
    finished_at                     TEXT,
    failure_reason                  TEXT,
    tmp_dir                         TEXT,
    source_hash_at_attempt          TEXT,
    drive_modified_time_at_attempt  TEXT,
    created_at                      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversion_jobs_status ON conversion_jobs(status);
CREATE INDEX IF NOT EXISTS idx_conversion_jobs_source_file ON conversion_jobs(source_file_id);

CREATE TABLE IF NOT EXISTS conversions (
    id                                 INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_id                     INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
    job_id                             INTEGER REFERENCES conversion_jobs(id) ON DELETE SET NULL,
    version_number                     INTEGER NOT NULL,
    output_path                        TEXT NOT NULL,
    status                             TEXT NOT NULL CHECK (status IN ('current','superseded')),
    source_type                        TEXT NOT NULL CHECK (source_type IN
        ('pdf','docx','xlsx','gdoc','gsheet','txt','md','ppt')),
    source_hash_at_conversion          TEXT,
    drive_modified_time_at_conversion  TEXT,
    conversion_tool                    TEXT NOT NULL CHECK (conversion_tool IN
        ('firecrawl-parse','google-docs-export','google-docs-export-docx-fallback',
         'google-sheets-export','passthrough')),
    converted_at                       TEXT NOT NULL,
    gauntlet_passed_at                 TEXT,
    locked_confirmed_at                TEXT,
    page_count                         INTEGER,
    word_count                         INTEGER,
    sheet_count                        INTEGER,
    row_count_total                    INTEGER,
    UNIQUE(source_file_id, version_number)
);
CREATE INDEX IF NOT EXISTS idx_conversions_status ON conversions(status);
CREATE INDEX IF NOT EXISTS idx_conversions_converted_at ON conversions(converted_at);
CREATE INDEX IF NOT EXISTS idx_conversions_source_type ON conversions(source_type);

CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    source_file_id  INTEGER REFERENCES source_files(id) ON DELETE SET NULL,
    conversion_id   INTEGER REFERENCES conversions(id) ON DELETE SET NULL,
    details_json    TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS conversions_fts USING fts5(
    conversion_id UNINDEXED,
    source_rel_path,
    output_path UNINDEXED,
    body
);
"""

SCHEMA_VERSION = 1


def get_connection(db_path: Path) -> sqlite3.Connection:
    """One connection per caller, never shared across threads (spec §5) --
    check_same_thread stays at its default (True) on purpose, so an accidental
    cross-thread use raises immediately instead of silently corrupting a
    boundary the way a shared connection would."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, ?)",
        (SCHEMA_VERSION,),
    )
    return conn
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_db.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/db.py doc-ingest-app/tests/test_db.py
git commit -m "feat(doc-ingest): add schema and per-worker connection factory"
```

---

## Task 3: `transaction()` boundary + migrations scaffold

**Files:**
- Modify: `doc-ingest-app/doc_ingest/db.py`
- Test: `doc-ingest-app/tests/test_db.py` (append)

**Interfaces:**
- Consumes: `get_connection` (Task 2).
- Produces: `transaction(conn)` context manager (used by every DB-writing task from here on), `apply_migrations(conn)` (empty today, ready for a future schema change).

Because each connection has exactly one owner (spec §5), this is deliberately simpler than `pipeline_app.db.transaction`: no cross-thread suppression tracking is needed, just a per-connection nesting depth so an inner `transaction()` call joins the outer one instead of committing early.

- [ ] **Step 1: Write the failing test** (append to `tests/test_db.py`)

```python
def test_transaction_commits_on_success(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    now = "2026-08-13T00:00:00+00:00"
    with db.transaction(conn):
        conn.execute(
            "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
            "VALUES ('a.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
        )
    row = conn.execute("SELECT rel_path FROM source_files WHERE rel_path = 'a.pdf'").fetchone()
    assert row is not None
    conn.close()


def test_transaction_rolls_back_on_exception(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    now = "2026-08-13T00:00:00+00:00"
    with pytest.raises(ValueError):
        with db.transaction(conn):
            conn.execute(
                "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
                "VALUES ('b.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
            )
            raise ValueError("boom")
    row = conn.execute("SELECT rel_path FROM source_files WHERE rel_path = 'b.pdf'").fetchone()
    assert row is None
    conn.close()


def test_transaction_nests_without_committing_early(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    now = "2026-08-13T00:00:00+00:00"
    with db.transaction(conn):
        conn.execute(
            "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
            "VALUES ('c.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
        )
        with db.transaction(conn):
            conn.execute(
                "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
                "VALUES ('d.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
            )
        # inner block exited but must not have committed independently --
        # verified indirectly: both rows exist after the OUTER block exits.
    rows = conn.execute("SELECT rel_path FROM source_files ORDER BY rel_path").fetchall()
    assert [r[0] for r in rows] == ["c.pdf", "d.pdf"]
    conn.close()


def test_apply_migrations_is_a_noop_on_a_fresh_db(tmp_db_path):
    conn = db.init_db(tmp_db_path)
    db.apply_migrations(conn)  # must not raise
    version = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
    assert version == db.SCHEMA_VERSION
    conn.close()
```

Add `import pytest` at the top of `test_db.py` if not already present from Task 2.

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_db.py -v
```

Expected: FAIL with `AttributeError: module 'doc_ingest.db' has no attribute 'transaction'`

- [ ] **Step 3: Add `transaction()` and `apply_migrations()` to `doc_ingest/db.py`**

```python
from contextlib import contextmanager

_TXN_DEPTH: dict[int, int] = {}

_MIGRATIONS: list[tuple[int, str]] = []  # (target_version, DDL/DML) -- empty until schema changes


@contextmanager
def transaction(conn: sqlite3.Connection):
    """One explicit boundary around a multi-row invariant. Nests: an inner
    block joins the outer one rather than committing early.

    Unlike pipeline_app.db.transaction, this does not need cross-thread
    commit-suppression tracking, because each connection here has exactly one
    owning worker for its whole life (spec §5) -- there is no other thread
    that could observe a boundary it doesn't own."""
    key = id(conn)
    depth = _TXN_DEPTH.get(key, 0)
    if depth == 0:
        conn.execute("BEGIN")
    _TXN_DEPTH[key] = depth + 1
    try:
        yield conn
    except BaseException:
        _TXN_DEPTH[key] = depth
        if depth == 0:
            conn.execute("ROLLBACK")
        raise
    else:
        _TXN_DEPTH[key] = depth
        if depth == 0:
            conn.execute("COMMIT")


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Runs any migration whose target version is above the DB's current
    schema_version, in order, each in its own BEGIN IMMEDIATE (DDL commits
    immediately regardless, same caveat as pipeline_app.db.apply_migrations).
    Empty today -- Task 2's schema is version 1 and this app has shipped
    nothing yet to migrate away from. Add entries here, never edit _SCHEMA's
    already-shipped shape in place."""
    current = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
    for target_version, ddl in _MIGRATIONS:
        if target_version <= current:
            continue
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.executescript(ddl)
            conn.execute("UPDATE schema_version SET version = ? WHERE id = 1", (target_version,))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
```

- [ ] **Step 4: Wire `apply_migrations` into `init_db`** (Task 2) — otherwise a future migration entry added to `_MIGRATIONS` never actually runs on an existing database

```python
# Change init_db (Task 2, above) to call apply_migrations before returning:
def init_db(db_path: Path) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, ?)",
        (SCHEMA_VERSION,),
    )
    apply_migrations(conn)
    return conn
```

Add a test proving this to `tests/test_db.py`:

```python
def test_init_db_calls_apply_migrations(tmp_db_path, monkeypatch):
    calls = []
    monkeypatch.setattr(db, "apply_migrations", lambda conn: calls.append(conn))
    conn = db.init_db(tmp_db_path)
    assert len(calls) == 1
    assert calls[0] is conn
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_db.py -v
```

Expected: 9 passed

- [ ] **Step 6: Commit**

```bash
git add doc-ingest-app/doc_ingest/db.py doc-ingest-app/tests/test_db.py
git commit -m "feat(doc-ingest): add transaction() boundary and migrations scaffold"
```

---

## Task 4: `naming.py` — pure naming/path functions

**Files:**
- Create: `doc-ingest-app/doc_ingest/naming.py`
- Test: `doc-ingest-app/tests/test_naming.py`

**Interfaces:**
- Consumes: `Config` (Task 1) for `long_path_threshold_chars`.
- Produces: `sanitize_component(name: str) -> str`, `build_dest_rel_path(source_rel_path: str, version: int, cfg: Config, prefix_len: int = 0) -> str`, `resolve_collision(dest_rel_path: str, is_taken) -> tuple[str, bool]` (second element: whether a collision suffix was applied), used by Task 12 (Gate 2) and Task 15 (worker).

No I/O in this module at all — every function is pure, which is what makes it exhaustively unit-testable including the long-path edge case (spec §13's first bullet).

**`prefix_len`**: spec §6 measures the **full** destination path — `str(cfg.converted_root)` plus a separator plus the relative path this function returns — not the relative path alone. `prefix_len` is the length of that absolute prefix; the shortening budget used internally is `cfg.long_path_threshold_chars - prefix_len`. It defaults to `0` so this task's own unit tests can reason about the relative path in isolation; Task 12 (Gate 2) is the caller that passes the real prefix length, since only Gate 2 knows `cfg.converted_root`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_naming.py
from doc_ingest.config import Config
from doc_ingest import naming


def test_sanitize_strips_forbidden_windows_characters():
    assert naming.sanitize_component('a<b>c:d"e/f\\g|h?i*j') == "abcdefghij"


def test_sanitize_strips_trailing_spaces_and_periods():
    assert naming.sanitize_component("Report. . ") == "Report"


def test_sanitize_collapses_whitespace_runs():
    assert naming.sanitize_component("Coaching   Agreement") == "Coaching Agreement"


def test_sanitize_preserves_ordinary_characters_and_casing():
    assert naming.sanitize_component("Client's Notes & Plan #2") == "Client's Notes & Plan #2"


def test_build_dest_rel_path_preserves_full_extension_as_stem():
    cfg = Config()
    dest = naming.build_dest_rel_path("Folder/Coaching Agreement Template.docx", version=1, cfg=cfg)
    assert dest == "Folder/Coaching Agreement Template.docx.md"


def test_build_dest_rel_path_versions_beyond_v1():
    cfg = Config()
    dest = naming.build_dest_rel_path("Folder/Notes.pdf", version=3, cfg=cfg)
    assert dest == "Folder/Notes.pdf.v3.md"


def test_build_dest_rel_path_eliminates_cross_type_stem_collision():
    cfg = Config()
    pdf_dest = naming.build_dest_rel_path("F2BU_12Week_Accelerator_Infographic.pdf", version=1, cfg=cfg)
    png_dest = naming.build_dest_rel_path("F2BU_12Week_Accelerator_Infographic.png", version=1, cfg=cfg)
    assert pdf_dest != png_dest
    assert pdf_dest == "F2BU_12Week_Accelerator_Infographic.pdf.md"
    assert png_dest == "F2BU_12Week_Accelerator_Infographic.png.md"


def _realistic_long_source():
    # Deliberately not single-character folder segments: a segment that's
    # already shorter than its own shortened form must never be "shortened"
    # into something longer (that was the exact bug this fixture caught).
    # Modeled on real corpus paths, which are already 300+ chars before the
    # output root is even added (spec §6).
    return "/".join([
        "Client Coaching Session Recordings And Notes",
        "2026 Individual Sessions Archive",
        "Very Long Coaching Session Transcript With A Lot Of Detail In The Name.docx",
    ])


def test_build_dest_rel_path_shortens_when_over_threshold():
    cfg = Config(long_path_threshold_chars=120)
    dest = naming.build_dest_rel_path(_realistic_long_source(), version=1, cfg=cfg)
    assert len(dest) <= cfg.long_path_threshold_chars
    assert dest.endswith(".md")


def test_build_dest_rel_path_shortening_never_makes_a_path_longer():
    # The regression case: a folder tree of already-short segments must not
    # come out longer than it went in just because the shortener touched it.
    cfg = Config(long_path_threshold_chars=10)  # unreachably tight on purpose
    long_source = "A/" * 20 + "B.docx"
    unshortened_len = len(long_source.replace(".docx", ".docx.md"))
    dest = naming.build_dest_rel_path(long_source, version=1, cfg=cfg)
    assert len(dest) <= unshortened_len


def test_build_dest_rel_path_shortening_is_deterministic():
    cfg = Config(long_path_threshold_chars=120)
    source = _realistic_long_source()
    dest1 = naming.build_dest_rel_path(source, version=1, cfg=cfg)
    dest2 = naming.build_dest_rel_path(source, version=1, cfg=cfg)
    assert dest1 == dest2


def test_build_dest_rel_path_honors_prefix_len_for_the_full_absolute_path():
    # A relative path that fits cfg.long_path_threshold_chars on its own can
    # still push the FULL path (converted_root + separator + relative path)
    # over the limit -- prefix_len is how the caller (Gate 2) accounts for
    # that (spec §6). threshold=200 is picked so prefix_len=0 needs no
    # shortening at all but prefix_len=60 does -- otherwise both branches
    # could trivially agree without the parameter having done anything.
    cfg = Config(long_path_threshold_chars=200)
    source = _realistic_long_source()
    dest_no_prefix = naming.build_dest_rel_path(source, version=1, cfg=cfg, prefix_len=0)
    dest_with_prefix = naming.build_dest_rel_path(source, version=1, cfg=cfg, prefix_len=60)
    assert len(dest_with_prefix) < len(dest_no_prefix)
    assert len(dest_with_prefix) + 60 <= cfg.long_path_threshold_chars


def test_resolve_collision_returns_unchanged_when_not_taken():
    dest, collided = naming.resolve_collision("Folder/Notes.pdf.md", is_taken=lambda p: False)
    assert dest == "Folder/Notes.pdf.md"
    assert collided is False


def test_resolve_collision_appends_hash_suffix_when_taken():
    taken = {"Folder/Notes.pdf.md"}
    dest, collided = naming.resolve_collision("Folder/Notes.pdf.md", is_taken=lambda p: p in taken)
    assert dest != "Folder/Notes.pdf.md"
    assert dest.endswith(".md")
    assert collided is True


def test_long_path_prefixes_an_absolute_path(tmp_path):
    target = tmp_path / "a.md"
    result = naming.long_path(target)
    assert result.startswith("\\\\?\\")
    assert str(target.resolve()) in result


def test_long_path_is_idempotent_on_an_already_prefixed_path(tmp_path):
    target = tmp_path / "a.md"
    once = naming.long_path(target)
    twice = naming.long_path(once)
    assert once == twice
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_naming.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'doc_ingest.naming'`

- [ ] **Step 3: Write `doc_ingest/naming.py`**

```python
"""Pure naming/path functions -- no filesystem or DB access anywhere in this
module except long_path's Path.resolve() call (which touches the filesystem
to resolve cwd/symlinks but never reads or writes file content). Gate 2
(Task 12) and worker.py (Task 15) are the callers."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

FORBIDDEN_CHARS = '<>:"/\\|?*'
_FORBIDDEN_RE = re.compile("[" + re.escape(FORBIDDEN_CHARS) + "]")
_WHITESPACE_RUN_RE = re.compile(r"\s+")


def sanitize_component(name: str) -> str:
    """Strips only what Windows mechanically forbids -- not a slugify. The 9
    forbidden characters, trailing spaces/periods, and collapsed whitespace
    runs (spec §6)."""
    stripped = _FORBIDDEN_RE.sub("", name)
    stripped = _WHITESPACE_RUN_RE.sub(" ", stripped)
    return stripped.rstrip(" .")


def _hash8(source_rel_path: str) -> str:
    return hashlib.sha256(source_rel_path.encode("utf-8")).hexdigest()[:8]


def _version_suffix(version: int) -> str:
    return "" if version == 1 else f".v{version}"


def _stem_filename(source_rel_path: str, version: int) -> str:
    filename = source_rel_path.rsplit("/", 1)[-1]
    return f"{sanitize_component(filename)}{_version_suffix(version)}.md"


_SEGMENT_SHORTEN_HEAD = 12
_STEM_SHORTEN_HEAD = 40


def _shorten_if_it_helps(segment: str, digest: str, head: int) -> str:
    """Returns a truncated-head + hash form ONLY if that form is actually
    shorter than the segment as given -- a short segment (e.g. a 1-char
    folder name, or a filename stem under 40 chars) truncated-then-hashed is
    routinely LONGER than the original, since the hash suffix itself is 9
    characters ("~" + 8 hex digits). Applying the shortened form
    unconditionally was the original bug: it grew exactly the paths spec §6
    calls "the common case here, not an edge case" instead of shrinking
    them."""
    shortened = f"{segment[:head]}~{digest}"
    return shortened if len(shortened) < len(segment) else segment


def build_dest_rel_path(source_rel_path: str, version: int, cfg, prefix_len: int = 0) -> str:
    """Mirrors the source tree 1:1 under converted/, preserving the full
    original extension as part of the stem (spec §6) -- Name.docx becomes
    Name.docx.md, never Name.md, so a same-stem .pdf and .docx never collide
    on write. Shortens the deepest segments with a deterministic hash suffix
    if the full path would exceed cfg.long_path_threshold_chars, accounting
    for prefix_len (the absolute-path prefix the caller will prepend)."""
    budget = cfg.long_path_threshold_chars - prefix_len
    parts = source_rel_path.split("/")
    folders = [sanitize_component(p) for p in parts[:-1]]
    filename = _stem_filename(source_rel_path, version)
    candidate = "/".join(folders + [filename])

    if len(candidate) <= budget:
        return candidate

    digest = _hash8(source_rel_path)

    stem, sep, ext_chain = filename.partition(".")
    shortened_stem = _shorten_if_it_helps(stem, digest, _STEM_SHORTEN_HEAD)
    short_filename = f"{shortened_stem}{sep}{ext_chain}" if sep else shortened_stem
    candidate = "/".join(folders + [short_filename])

    if len(candidate) <= budget:
        return candidate

    # Still too long: shorten folder segments, deepest first, skipping any
    # segment a shortened form would not actually make smaller. The \\?\-
    # prefixed I/O in lock.py/worker.py (Task 13/15) is the defense-in-depth
    # backstop for the residual case where nothing left to shorten still
    # doesn't fit (spec §6).
    idx = len(folders) - 1
    while len(candidate) > budget and idx >= 0:
        shortened = _shorten_if_it_helps(folders[idx], digest, _SEGMENT_SHORTEN_HEAD)
        if shortened != folders[idx]:
            folders[idx] = shortened
            candidate = "/".join(folders + [short_filename])
        idx -= 1

    return candidate


def resolve_collision(dest_rel_path: str, is_taken) -> tuple[str, bool]:
    """If dest_rel_path is already occupied by a DIFFERENT source file's
    output, appends a short hash suffix before the final .md and reports the
    collision so the caller can log an events row (spec §6) -- collisions are
    resolved, never left to fail indefinitely, but never silent either."""
    if not is_taken(dest_rel_path):
        return dest_rel_path, False
    digest = hashlib.sha256(dest_rel_path.encode("utf-8")).hexdigest()[:8]
    stem, _, suffix = dest_rel_path.rpartition(".md")
    candidate = f"{stem}~{digest}.md"
    return candidate, True


def long_path(path) -> str:
    """Windows' documented mechanism for addressing paths beyond the
    ~260-char MAX_PATH default without any system-wide policy change: an
    ALREADY-ABSOLUTE path prefixed with \\\\?\\. This is the defense-in-depth
    backstop spec §6 describes for the residual case where naming.py's own
    shortening still couldn't bring a path under
    cfg.long_path_threshold_chars -- Python's open()/os-level file I/O on
    Windows honors this prefix (it maps directly to CreateFileW), so it's
    applied at the one call site that matters most: worker.py's final write
    of the locked output file (Task 15). Deliberately NOT applied to the
    icacls subprocess calls in lock.py -- external command-line tools doing
    their own path parsing are not guaranteed to honor \\\\?\\ the same way,
    and getting that wrong risks a worse failure (icacls misinterpreting the
    prefix as part of the filename) than the rare long-path case it would be
    trying to guard against. A no-op on non-Windows, or for a path that's
    already \\\\?\\-prefixed. Checks the incoming string for that prefix
    BEFORE calling Path.resolve() on it -- feeding an already-prefixed
    string back into pathlib's resolver is its own source of inconsistent
    behavior across Python versions, so the idempotent case short-circuits
    before ever reaching that call."""
    text = str(path)
    if text.startswith("\\\\?\\"):
        return text
    resolved = str(Path(path).resolve())
    if os.name != "nt" or resolved.startswith("\\\\?\\"):
        return resolved
    return "\\\\?\\" + resolved
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_naming.py -v
```

Expected: 15 passed

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/naming.py doc-ingest-app/tests/test_naming.py
git commit -m "feat(doc-ingest): add pure naming/long-path/collision functions"
```

---

## Task 5: `scan.py` — magic-byte sniffing and classification

**Files:**
- Create: `doc-ingest-app/doc_ingest/scan.py`
- Test: `doc-ingest-app/tests/test_scan.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `sniff_signature(path: Path) -> str | None`, `classify(extension: str, sniffed: str | None) -> str`, `walk_source_tree(root: Path) -> Iterator[ScannedEntry]` — `ScannedEntry` is a small dataclass (`rel_path`, `extension`, `sniffed_signature`, `size_bytes`, `mtime_iso`, `content_hash`). Used by Task 6.

Magic-byte signatures needed (spec §2's real corpus): PDF (`%PDF-`), PNG (8-byte PNG signature), JPEG (`\xff\xd8\xff`), MP4/MOV (an `ftyp` box a few bytes into the file — both share the ISO base media container format).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scan.py
from pathlib import Path

from doc_ingest import scan


def test_sniff_signature_detects_pdf(tmp_path):
    f = tmp_path / "noext"
    f.write_bytes(b"%PDF-1.4\n%rest of a fake pdf body")
    assert scan.sniff_signature(f) == "pdf"


def test_sniff_signature_detects_png(tmp_path):
    f = tmp_path / "noext"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    assert scan.sniff_signature(f) == "png"


def test_sniff_signature_detects_jpeg(tmp_path):
    f = tmp_path / "noext"
    f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
    assert scan.sniff_signature(f) == "jpg"


def test_sniff_signature_detects_mp4_ftyp_box(tmp_path):
    f = tmp_path / "noext"
    f.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20)
    assert scan.sniff_signature(f) == "mp4"


def test_sniff_signature_detects_mov_ftyp_box(tmp_path):
    f = tmp_path / "noext"
    f.write_bytes(b"\x00\x00\x00\x14ftypqt  " + b"\x00" * 20)
    assert scan.sniff_signature(f) == "mov"


def test_sniff_signature_returns_none_for_unrecognized_bytes(tmp_path):
    f = tmp_path / "noext"
    f.write_bytes(b"not a known signature at all")
    assert scan.sniff_signature(f) is None


def test_sniff_signature_never_opens_for_writing(tmp_path, monkeypatch):
    f = tmp_path / "noext"
    f.write_bytes(b"%PDF-1.4")
    real_open = open

    def _guarded_open(path, mode="r", *a, **kw):
        assert "w" not in mode and "a" not in mode and "+" not in mode
        return real_open(path, mode, *a, **kw)

    monkeypatch.setattr("builtins.open", _guarded_open)
    scan.sniff_signature(f)


def test_classify_convertible_extension():
    assert scan.classify("pdf", sniffed=None) == "convertible"
    assert scan.classify("docx", sniffed=None) == "convertible"
    assert scan.classify("xlsx", sniffed=None) == "convertible"
    assert scan.classify("txt", sniffed=None) == "convertible"
    assert scan.classify("md", sniffed=None) == "convertible"
    assert scan.classify("ppt", sniffed=None) == "convertible"


def test_classify_gdoc_and_gsheet_pointers():
    assert scan.classify("gdoc", sniffed=None) == "gdoc_pointer"
    assert scan.classify("gsheet", sniffed=None) == "gdoc_pointer"


def test_classify_catalog_only_images():
    assert scan.classify("png", sniffed=None) == "catalog_only"
    assert scan.classify("jpg", sniffed=None) == "catalog_only"


def test_classify_excluded_media():
    assert scan.classify("mov", sniffed=None) == "excluded_media"
    assert scan.classify("mp4", sniffed=None) == "excluded_media"


def test_classify_desktop_ini_is_blocked():
    assert scan.classify("ini", sniffed=None) == "blocked_unknown"


def test_classify_extensionless_uses_sniffed_signature():
    assert scan.classify("", sniffed="pdf") == "convertible"
    assert scan.classify("", sniffed="png") == "catalog_only"
    assert scan.classify("", sniffed="mp4") == "excluded_media"
    assert scan.classify("", sniffed=None) == "blocked_unknown"


def test_walk_source_tree_yields_every_file(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "sub" / "b.docx").write_bytes(b"fake docx bytes")
    entries = list(scan.walk_source_tree(tmp_path))
    rel_paths = sorted(e.rel_path for e in entries)
    assert rel_paths == ["a.pdf", "sub/b.docx"]


def test_walk_source_tree_never_writes_or_deletes(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake")
    before = (tmp_path / "a.pdf").read_bytes()
    list(scan.walk_source_tree(tmp_path))
    after = (tmp_path / "a.pdf").read_bytes()
    assert before == after
    assert (tmp_path / "a.pdf").exists()


def test_walk_source_tree_computes_a_hash_for_a_convertible_file(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake")
    entries = list(scan.walk_source_tree(tmp_path))
    assert entries[0].content_hash is not None


def test_walk_source_tree_skips_hashing_excluded_media(tmp_path):
    # Hashing every file unconditionally would mean sha256'ing every video
    # in the real corpus -- up to 1.1GB each -- for a value nothing
    # downstream ever reads (excluded_media is never enqueued, spec §2).
    (tmp_path / "a.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20)
    entries = list(scan.walk_source_tree(tmp_path))
    assert entries[0].content_hash is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_scan.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'doc_ingest.scan'`

- [ ] **Step 3: Write `doc_ingest/scan.py`**

```python
"""Read-only tree walk + magic-byte content sniffing. Never opens a file for
writing; never moves or deletes anything under the input root (spec §4 step
2). Sniffing exists not just to keep video out but to correctly *include* the
6 real PDFs and 1 PNG hiding among this corpus's 19 extensionless files
(spec §2) -- extension-based classification alone silently drops them."""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
from pathlib import Path
from typing import Iterator

_CONVERTIBLE_EXTENSIONS = {"pdf", "docx", "xlsx", "txt", "md", "ppt"}
_GDOC_EXTENSIONS = {"gdoc", "gsheet"}
_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
_VIDEO_EXTENSIONS = {"mov", "mp4"}

_SNIFF_SIZE = 32


def sniff_signature(path: Path) -> str | None:
    with open(path, "rb") as fh:
        head = fh.read(_SNIFF_SIZE)
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12]
        # 'qt  ' is QuickTime/.mov's own brand; everything else with an
        # ftyp box at this offset is an ISO-base-media (mp4-family) file.
        return "mov" if brand == b"qt  " else "mp4"
    return None


def classify(extension: str, sniffed: str | None) -> str:
    ext = extension.lower()
    if ext == "" :
        if sniffed == "pdf":
            return "convertible"
        if sniffed in ("png", "jpg"):
            return "catalog_only"
        if sniffed in ("mov", "mp4"):
            return "excluded_media"
        return "blocked_unknown"
    if ext in _CONVERTIBLE_EXTENSIONS:
        return "convertible"
    if ext in _GDOC_EXTENSIONS:
        return "gdoc_pointer"
    if ext in _IMAGE_EXTENSIONS:
        return "catalog_only"
    if ext in _VIDEO_EXTENSIONS:
        return "excluded_media"
    return "blocked_unknown"


@dataclasses.dataclass(frozen=True)
class ScannedEntry:
    rel_path: str
    extension: str
    sniffed_signature: str | None
    size_bytes: int
    mtime_iso: str
    content_hash: str | None  # None for catalog_only/excluded_media/blocked_unknown -- see walk_source_tree


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def walk_source_tree(root: Path) -> Iterator[ScannedEntry]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(root).as_posix()
        extension = path.suffix[1:].lower() if path.suffix else ""
        sniffed = sniff_signature(path) if extension == "" else None
        stat = path.stat()
        mtime_iso = dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc).isoformat()
        # Only hash what change-detection actually needs: 'convertible'
        # local files (content_hash drives their enqueue comparison) and
        # 'gdoc_pointer' stubs (always 176 bytes regardless, so hashing them
        # is free even though drive_modified_time, not this hash, drives
        # their change detection). Hashing everything unconditionally would
        # mean sha256'ing all 60 video files in the real corpus -- up to
        # 1.1GB each -- on every 30-minute wake, for a value nothing
        # downstream ever reads (excluded_media is never enqueued, spec §2).
        classification = classify(extension, sniffed)
        content_hash = _sha256_file(path) if classification in ("convertible", "gdoc_pointer") else None
        yield ScannedEntry(
            rel_path=rel_path,
            extension=extension,
            sniffed_signature=sniffed,
            size_bytes=stat.st_size,
            mtime_iso=mtime_iso,
            content_hash=content_hash,
        )
```

Note: `.gdoc`/`.gsheet` stubs get hashed too (they're tiny, 176 bytes) even though their `content_hash` is never used for change detection (Drive's `modifiedTime` is, per spec §4 step 3) — Task 6 simply doesn't read that column for gdoc rows. `desktop.ini` and any other unrecognized extension fall through to `blocked_unknown`, matching spec §2's exclusion of Windows folder metadata.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_scan.py -v
```

Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/scan.py doc-ingest-app/tests/test_scan.py
git commit -m "feat(doc-ingest): add read-only tree walk with magic-byte sniffing"
```

---

## Task 6: Scan → DB sync (`source_files` upsert + `missing` detection)

**Files:**
- Create: `doc-ingest-app/doc_ingest/sync.py`
- Test: `doc-ingest-app/tests/test_sync.py`

**Interfaces:**
- Consumes: `scan.walk_source_tree`, `scan.classify` (Task 5); `db.transaction` (Task 3).
- Produces: `sync_source_files(conn, input_root: Path) -> dict` (counts by classification, for the cron's log line). Used by `run_ingest_cron.py` (Task 18).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sync.py
from doc_ingest import sync


def test_sync_inserts_new_files(conn, tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake")
    sync.sync_source_files(conn, tmp_path)
    row = conn.execute("SELECT classification FROM source_files WHERE rel_path = 'a.pdf'").fetchone()
    assert row[0] == "convertible"


def test_sync_marks_previously_seen_file_as_missing(conn, tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    sync.sync_source_files(conn, tmp_path)
    f.unlink()
    sync.sync_source_files(conn, tmp_path)
    row = conn.execute("SELECT classification FROM source_files WHERE rel_path = 'a.pdf'").fetchone()
    assert row[0] == "missing"


def test_sync_reclassifies_a_missing_file_that_reappears(conn, tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    sync.sync_source_files(conn, tmp_path)
    f.unlink()
    sync.sync_source_files(conn, tmp_path)
    f.write_bytes(b"%PDF-1.4 fake again")
    sync.sync_source_files(conn, tmp_path)
    row = conn.execute("SELECT classification FROM source_files WHERE rel_path = 'a.pdf'").fetchone()
    assert row[0] == "convertible"


def test_sync_updates_content_hash_when_file_changes(conn, tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4 version one")
    sync.sync_source_files(conn, tmp_path)
    hash1 = conn.execute("SELECT content_hash FROM source_files WHERE rel_path = 'a.pdf'").fetchone()[0]
    f.write_bytes(b"%PDF-1.4 version two, different content")
    sync.sync_source_files(conn, tmp_path)
    hash2 = conn.execute("SELECT content_hash FROM source_files WHERE rel_path = 'a.pdf'").fetchone()[0]
    assert hash1 != hash2


def test_sync_returns_counts_by_classification(conn, tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "b.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10)
    counts = sync.sync_source_files(conn, tmp_path)
    assert counts["convertible"] == 1
    assert counts["catalog_only"] == 1


def test_sync_never_writes_into_the_input_tree(conn, tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    sync.sync_source_files(conn, tmp_path)
    after = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_sync.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'doc_ingest.sync'`

- [ ] **Step 3: Write `doc_ingest/sync.py`**

```python
"""Bridges scan.py's read-only walk to source_files. A path that was
previously seen and no longer appears is marked 'missing', never deleted
(spec §4 step 2, §9a)."""
from __future__ import annotations

import collections
import datetime as dt
from pathlib import Path

from doc_ingest import db, scan


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sync_source_files(conn, input_root: Path) -> dict:
    now = _now_iso()
    seen_rel_paths: set[str] = set()
    counts: collections.Counter = collections.Counter()

    with db.transaction(conn):
        for entry in scan.walk_source_tree(input_root):
            seen_rel_paths.add(entry.rel_path)
            classification = scan.classify(entry.extension, entry.sniffed_signature)
            counts[classification] += 1
            conn.execute(
                """
                INSERT INTO source_files
                    (rel_path, extension, sniffed_signature, classification,
                     size_bytes, mtime, content_hash, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(rel_path) DO UPDATE SET
                    extension = excluded.extension,
                    sniffed_signature = excluded.sniffed_signature,
                    classification = excluded.classification,
                    size_bytes = excluded.size_bytes,
                    mtime = excluded.mtime,
                    content_hash = excluded.content_hash,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    entry.rel_path, entry.extension, entry.sniffed_signature, classification,
                    entry.size_bytes, entry.mtime_iso, entry.content_hash, now, now,
                ),
            )

        previously_seen = {
            row[0]
            for row in conn.execute(
                "SELECT rel_path FROM source_files WHERE classification != 'missing'"
            ).fetchall()
        }
        newly_missing = previously_seen - seen_rel_paths
        for rel_path in newly_missing:
            conn.execute(
                "UPDATE source_files SET classification = 'missing', last_seen_at = ? WHERE rel_path = ?",
                (now, rel_path),
            )
            counts["missing"] += 1

    return dict(counts)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_sync.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/sync.py doc-ingest-app/tests/test_sync.py
git commit -m "feat(doc-ingest): sync scan results into source_files, tracking missing"
```

---

## Task 7: `jobs.py` — enqueue, claim, heartbeat, reclaim

**Files:**
- Create: `doc-ingest-app/doc_ingest/jobs.py`
- Test: `doc-ingest-app/tests/test_jobs.py`

**Interfaces:**
- Consumes: `db.get_connection`, `db.transaction` (Tasks 2–3).
- Produces: `enqueue_pending_jobs(conn) -> int`, `claim_job(conn, worker_id: str) -> int | None`, `heartbeat(conn, job_id: int, worker_id: str) -> None`, `reclaim_stale_jobs(conn, cfg, tmp_root: Path) -> list[int]`. Used by `run_ingest_cron.py` (Task 16) and `worker.py` (Task 15).

**`claim_job` correctness note**: uses a raw `BEGIN IMMEDIATE` (not `db.transaction()`), the same deliberate bypass `pipeline_app.db` documents — a deferred transaction can hit `SQLITE_BUSY_SNAPSHOT` under concurrent writers in a way `busy_timeout` doesn't resolve, and `BEGIN IMMEDIATE` acquires the write lock immediately so the SELECT-then-UPDATE inside it is atomic: no other connection can claim the same row between them.

**Enqueue skip-if-already-failed-at-this-version note**: without this, a deterministic gauntlet failure (e.g. a scanned PDF) would get a fresh `pending` job every 30-minute wake forever, since "no `current` conversion exists" stays true after every failed attempt. `conversion_jobs.source_hash_at_attempt` / `drive_modified_time_at_attempt` (recorded at claim time, Task 7 Step 3) let enqueue tell "already tried and failed at exactly this version" from "the source changed since the last failure" and only re-enqueue the latter.

**`gdoc_pointer` rows are included from the start, not deferred to Task 22.** `enqueue_pending_jobs` branches on `source_files.classification`: a `convertible` (local-file) row's change signal is `content_hash`; a `gdoc_pointer` row's is `drive_modified_time` — **never both, never either-or**. An earlier version of this function checked "does `content_hash` differ OR does `drive_modified_time` differ," which for a `gdoc_pointer` row compares a sha256 hex digest (of the row's own 176-byte stub, spec §4 step 3) against `source_hash_at_conversion` — a value that, for a Drive-native conversion, holds an ISO timestamp, not a hash. A hex digest is never equal to an ISO timestamp, so that comparison was unconditionally true and every `.gdoc`/`.gsheet` would get a new job — and a new locked version — on every single 30-minute wake, forever. Branching by classification instead of OR-ing two unrelated signals together is what keeps them from cross-contaminating.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_jobs.py
import datetime as dt
import threading
import time

import pytest

from doc_ingest import jobs
from doc_ingest.config import Config


def _seed_source_file(conn, rel_path="a.pdf", content_hash="hash1"):
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, content_hash, first_seen_at, last_seen_at) "
        "VALUES (?, 'pdf', 'convertible', ?, ?, ?)",
        (rel_path, content_hash, now, now),
    )
    conn.commit()
    return conn.execute("SELECT id FROM source_files WHERE rel_path = ?", (rel_path,)).fetchone()[0]


def test_enqueue_creates_a_pending_job_for_a_brand_new_file(conn):
    _seed_source_file(conn)
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 1
    row = conn.execute("SELECT status FROM conversion_jobs").fetchone()
    assert row[0] == "pending"


def test_enqueue_does_not_duplicate_an_already_pending_job(conn):
    _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    created_again = jobs.enqueue_pending_jobs(conn)
    assert created_again == 0
    count = conn.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0]
    assert count == 1


def test_enqueue_skips_a_source_file_with_a_current_matching_conversion(conn):
    source_id = _seed_source_file(conn, content_hash="hash1")
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "source_hash_at_conversion, conversion_tool, converted_at) "
        "VALUES (?, 1, 'a.pdf.md', 'current', 'pdf', 'hash1', 'firecrawl-parse', ?)",
        (source_id, now),
    )
    conn.commit()
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 0


def test_enqueue_creates_a_new_job_when_content_hash_changed(conn):
    source_id = _seed_source_file(conn, content_hash="hash1")
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "source_hash_at_conversion, conversion_tool, converted_at) "
        "VALUES (?, 1, 'a.pdf.md', 'current', 'pdf', 'hash1', 'firecrawl-parse', ?)",
        (source_id, now),
    )
    conn.execute("UPDATE source_files SET content_hash = 'hash2' WHERE id = ?", (source_id,))
    conn.commit()
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 1


def test_enqueue_skips_a_source_file_already_failed_at_this_exact_version(conn):
    source_id = _seed_source_file(conn, content_hash="hash1")
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO conversion_jobs (source_file_id, status, source_hash_at_attempt, created_at) "
        "VALUES (?, 'failed', 'hash1', ?)",
        (source_id, now),
    )
    conn.commit()
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 0


def test_enqueue_retries_after_a_failure_once_the_source_changes(conn):
    source_id = _seed_source_file(conn, content_hash="hash1")
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO conversion_jobs (source_file_id, status, source_hash_at_attempt, created_at) "
        "VALUES (?, 'failed', 'hash1', ?)",
        (source_id, now),
    )
    conn.execute("UPDATE source_files SET content_hash = 'hash2' WHERE id = ?", (source_id,))
    conn.commit()
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 1


def _seed_gdoc_source_file(conn, rel_path="a.gdoc", drive_modified_time="2026-08-01T00:00:00Z"):
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, drive_modified_time, "
        "first_seen_at, last_seen_at) VALUES (?, 'gdoc', 'gdoc_pointer', ?, ?, ?)",
        (rel_path, drive_modified_time, now, now),
    )
    conn.commit()
    return conn.execute("SELECT id FROM source_files WHERE rel_path = ?", (rel_path,)).fetchone()[0]


def test_enqueue_includes_gdoc_pointer_rows(conn):
    _seed_gdoc_source_file(conn)
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 1


def test_enqueue_ignores_content_hash_for_a_gdoc_row(conn):
    """The bug this guards: a .gdoc source_files row's content_hash is the
    sha256 of its own static 176-byte stub -- NEVER meaningful for change
    detection (spec §4 step 3). If enqueue ever compared it against
    source_hash_at_conversion for a gdoc row (a hex digest never equals an
    ISO timestamp), every gdoc would re-enqueue on every single wake
    forever, even with an unchanged Drive modifiedTime."""
    source_id = _seed_gdoc_source_file(conn, drive_modified_time="2026-08-01T00:00:00Z")
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "drive_modified_time_at_conversion, conversion_tool, converted_at) "
        "VALUES (?, 1, 'a.gdoc.md', 'current', 'gdoc', '2026-08-01T00:00:00Z', 'google-docs-export', ?)",
        (source_id, now),
    )
    conn.commit()
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 0  # unchanged Drive modifiedTime -- must NOT re-enqueue


def test_enqueue_creates_a_new_gdoc_job_when_drive_modified_time_advances(conn):
    source_id = _seed_gdoc_source_file(conn, drive_modified_time="2026-08-12T00:00:00Z")
    now = "2026-08-01T00:05:00+00:00"
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "drive_modified_time_at_conversion, conversion_tool, converted_at) "
        "VALUES (?, 1, 'a.gdoc.md', 'current', 'gdoc', '2026-08-01T00:00:00Z', 'google-docs-export', ?)",
        (source_id, now),
    )
    conn.commit()
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 1  # Drive modifiedTime advanced -- must re-enqueue


def test_claim_job_returns_none_when_nothing_pending(conn):
    assert jobs.claim_job(conn, worker_id="w1") is None


def test_claim_job_claims_a_pending_job_and_stamps_ownership(conn):
    source_id = _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")
    assert job_id is not None
    row = conn.execute(
        "SELECT status, worker_id, claimed_at, heartbeat_at, source_hash_at_attempt FROM conversion_jobs WHERE id = ?",
        (job_id,),
    ).fetchone()
    assert row[0] == "claimed"
    assert row[1] == "w1"
    assert row[2] is not None
    assert row[3] is not None
    assert row[4] == "hash1"


def test_claim_deterministically_excludes_a_second_connection(tmp_db_path):
    """Deterministic version of the concurrency guarantee: connection A opens
    a manual BEGIN IMMEDIATE and claims the only pending job WITHOUT
    committing yet; connection B's claim_job runs concurrently on a second
    thread. B's BEGIN IMMEDIATE must block until A releases the write lock
    (busy_timeout=5000 on both connections, set in db.get_connection), and
    once it does, B must see the job already claimed and return None -- not
    race for it. This forces the exact contention window regardless of OS
    thread scheduling, unlike a bare threading.Barrier, which only
    synchronizes entry and can let one thread finish before the other starts."""
    from doc_ingest import db

    setup_conn = db.init_db(tmp_db_path)
    _seed_source_file(setup_conn)
    jobs.enqueue_pending_jobs(setup_conn)
    setup_conn.close()

    conn_a = db.get_connection(tmp_db_path)
    conn_b = db.get_connection(tmp_db_path)
    a_holds_lock = threading.Event()
    a_can_commit = threading.Event()
    b_result: dict = {}

    def _claim_a():
        conn_a.execute("BEGIN IMMEDIATE")
        row = conn_a.execute("SELECT id FROM conversion_jobs WHERE status = 'pending' LIMIT 1").fetchone()
        conn_a.execute("UPDATE conversion_jobs SET status = 'claimed', worker_id = 'a' WHERE id = ?", (row[0],))
        a_holds_lock.set()
        a_can_commit.wait(timeout=5)
        conn_a.execute("COMMIT")

    def _claim_b():
        a_holds_lock.wait(timeout=5)
        try:
            b_result["job_id"] = jobs.claim_job(conn_b, worker_id="b")
        except Exception as exc:
            b_result["error"] = exc

    t_a = threading.Thread(target=_claim_a)
    t_b = threading.Thread(target=_claim_b)
    t_a.start()
    t_b.start()
    time.sleep(0.05)  # give B time to enter its (blocked) BEGIN IMMEDIATE before A commits
    a_can_commit.set()
    t_a.join(timeout=5)
    t_b.join(timeout=5)
    conn_a.close()
    conn_b.close()

    assert "error" not in b_result, f"claim_job raised: {b_result.get('error')}"
    assert b_result["job_id"] is None  # A already claimed the only pending job before B's transaction opened


def test_two_connections_racing_one_pending_job_only_one_wins(tmp_db_path):
    """Closer-to-production shape than the deterministic test above: two
    real workers hitting claim_job concurrently with no artificial ordering.
    Exceptions are captured rather than left to escape the thread silently,
    so a broken claim implementation fails this test loudly instead of just
    producing a confusing wrong count."""
    from doc_ingest import db

    setup_conn = db.init_db(tmp_db_path)
    _seed_source_file(setup_conn)
    jobs.enqueue_pending_jobs(setup_conn)
    setup_conn.close()

    results = []
    barrier = threading.Barrier(2)

    def _race(worker_id):
        conn = db.get_connection(tmp_db_path)
        try:
            barrier.wait()
            results.append(jobs.claim_job(conn, worker_id=worker_id))
        except Exception as exc:
            results.append(exc)
        finally:
            conn.close()

    t1 = threading.Thread(target=_race, args=("w1",))
    t2 = threading.Thread(target=_race, args=("w2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not any(isinstance(r, Exception) for r in results), results
    winners = [r for r in results if r is not None]
    assert len(winners) == 1
    assert results.count(None) == 1


def test_heartbeat_updates_the_timestamp(conn):
    _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")
    first = conn.execute("SELECT heartbeat_at FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()[0]
    time.sleep(0.01)
    jobs.heartbeat(conn, job_id, worker_id="w1")
    second = conn.execute("SELECT heartbeat_at FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()[0]
    assert second >= first


def test_heartbeat_is_a_noop_for_a_job_this_worker_no_longer_owns(conn):
    _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")
    jobs.heartbeat(conn, job_id, worker_id="an-impostor")
    row = conn.execute("SELECT worker_id FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert row[0] == "w1"


def test_reclaim_resets_a_job_whose_heartbeat_is_stale(conn, tmp_path):
    cfg = Config(reclaim_staleness_threshold_s=1)
    _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")
    stale_time = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=10)).isoformat()
    conn.execute("UPDATE conversion_jobs SET heartbeat_at = ? WHERE id = ?", (stale_time, job_id))
    conn.commit()
    reclaimed = jobs.reclaim_stale_jobs(conn, cfg, tmp_path)
    assert job_id in reclaimed
    row = conn.execute("SELECT status, worker_id FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert row[0] == "pending"
    assert row[1] is None


def test_reclaim_leaves_a_live_job_alone(conn, tmp_path):
    cfg = Config(reclaim_staleness_threshold_s=600)
    _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")
    reclaimed = jobs.reclaim_stale_jobs(conn, cfg, tmp_path)
    assert job_id not in reclaimed
    row = conn.execute("SELECT status FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert row[0] == "claimed"


def test_reclaim_removes_the_orphaned_tmp_dir(conn, tmp_path):
    cfg = Config(reclaim_staleness_threshold_s=1)
    _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")
    job_tmp_dir = tmp_path / f"job-{job_id}"
    job_tmp_dir.mkdir()
    (job_tmp_dir / "staged.pdf").write_bytes(b"partial")
    conn.execute("UPDATE conversion_jobs SET tmp_dir = ?, heartbeat_at = ? WHERE id = ?",
                 (str(job_tmp_dir), "2020-01-01T00:00:00+00:00", job_id))
    conn.commit()
    jobs.reclaim_stale_jobs(conn, cfg, tmp_path)
    assert not job_tmp_dir.exists()


def test_reclaim_does_not_reprocess_a_placing_job_whose_conversion_already_landed(conn, tmp_path):
    """A job stuck at 'placing' with a stale heartbeat because the lock step
    (Task 15) hasn't been confirmed yet must NOT be reset to 'pending' --
    that would trigger a wasted reconversion of a source that already has a
    valid 'current' conversion; only its lock confirmation is outstanding,
    which worker.resume_unlocked_conversions retries independently every
    wake (spec §4 step 9)."""
    cfg = Config(reclaim_staleness_threshold_s=1)
    source_id = _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")
    stale_time = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=10)).isoformat()
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "UPDATE conversion_jobs SET status = 'placing', heartbeat_at = ? WHERE id = ?",
        (stale_time, job_id),
    )
    conn.execute(
        "INSERT INTO conversions (source_file_id, job_id, version_number, output_path, status, "
        "source_type, conversion_tool, converted_at) "
        "VALUES (?, ?, 1, 'a.pdf.md', 'current', 'pdf', 'firecrawl-parse', ?)",
        (source_id, job_id, now),
    )
    conn.commit()

    reclaimed = jobs.reclaim_stale_jobs(conn, cfg, tmp_path)

    assert job_id not in reclaimed
    row = conn.execute("SELECT status FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert row[0] == "placing"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_jobs.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'doc_ingest.jobs'`

- [ ] **Step 3: Write `doc_ingest/jobs.py`**

```python
"""The DB-claimed job queue: enqueue, atomic claim, heartbeat, and
heartbeat-based reclaim (spec §4 steps 1, 4, 5). Deliberately NOT modeled on
pipeline_app.preflight.reconcile_orphaned_turns' unconditional startup sweep
-- that is safe only because pipeline-app is single-process; this app's
concurrent worker pool needs a liveness signal, not a blind reset."""
from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

from doc_ingest import db


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def enqueue_pending_jobs(conn) -> int:
    """Local files (classification='convertible') and Drive-native files
    (classification='gdoc_pointer') use CONSISTENTLY SEPARATE change-detection
    signals -- never mixed. A local file's content_hash is meaningless for a
    176-byte .gdoc/.gsheet stub (spec §4 step 3: the stub never changes when
    the real document does), and a gdoc's drive_modified_time_at_conversion
    is never set for a local file. Branching on classification, rather than
    checking "if either signal differs," is what keeps these two comparisons
    from cross-contaminating each other."""
    created = 0
    now = _now_iso()
    with db.transaction(conn):
        rows = conn.execute(
            "SELECT id, classification, content_hash, drive_modified_time FROM source_files "
            "WHERE classification IN ('convertible', 'gdoc_pointer')"
        ).fetchall()
        for source_file_id, classification, content_hash, drive_modified_time in rows:
            in_flight = conn.execute(
                "SELECT 1 FROM conversion_jobs WHERE source_file_id = ? "
                "AND status IN ('pending','claimed','converting','placing')",
                (source_file_id,),
            ).fetchone()
            if in_flight:
                continue

            current = conn.execute(
                "SELECT source_hash_at_conversion, drive_modified_time_at_conversion "
                "FROM conversions WHERE source_file_id = ? AND status = 'current'",
                (source_file_id,),
            ).fetchone()

            needs_job = current is None
            if not needs_job:
                if classification == "gdoc_pointer":
                    prior_modified = current[1]
                    needs_job = drive_modified_time is not None and (
                        prior_modified is None or drive_modified_time > prior_modified
                    )
                else:
                    needs_job = content_hash is not None and content_hash != current[0]

            if needs_job:
                last_failed = conn.execute(
                    "SELECT source_hash_at_attempt, drive_modified_time_at_attempt "
                    "FROM conversion_jobs WHERE source_file_id = ? AND status = 'failed' "
                    "ORDER BY id DESC LIMIT 1",
                    (source_file_id,),
                ).fetchone()
                if last_failed is not None:
                    if classification == "gdoc_pointer":
                        already_failed_this_version = (
                            drive_modified_time is not None and drive_modified_time == last_failed[1]
                        )
                    else:
                        already_failed_this_version = (
                            content_hash is not None and content_hash == last_failed[0]
                        )
                    if already_failed_this_version:
                        continue  # already failed at exactly this version -- don't retry every wake

                conn.execute(
                    "INSERT INTO conversion_jobs (source_file_id, status, created_at) VALUES (?, 'pending', ?)",
                    (source_file_id, now),
                )
                created += 1
    return created


def claim_job(conn, worker_id: str) -> int | None:
    now = _now_iso()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT cj.id, sf.content_hash, sf.drive_modified_time FROM conversion_jobs cj "
            "JOIN source_files sf ON sf.id = cj.source_file_id "
            "WHERE cj.status = 'pending' ORDER BY cj.id LIMIT 1"
        ).fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            return None
        job_id, content_hash, drive_modified_time = row
        cursor = conn.execute(
            "UPDATE conversion_jobs SET status = 'claimed', worker_id = ?, claimed_at = ?, "
            "heartbeat_at = ?, source_hash_at_attempt = ?, drive_modified_time_at_attempt = ? "
            "WHERE id = ? AND status = 'pending'",
            (worker_id, now, now, content_hash, drive_modified_time, job_id),
        )
        # BEGIN IMMEDIATE already made the SELECT-then-UPDATE atomic (no other
        # connection can hold the write lock at the same time), so rowcount
        # should always be 1 here -- checked anyway as the last line of
        # defense, not because the reasoning above is expected to be wrong.
        if cursor.rowcount != 1:
            conn.execute("ROLLBACK")
            return None
        conn.execute("COMMIT")
        return job_id
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def heartbeat(conn, job_id: int, worker_id: str) -> None:
    with db.transaction(conn):
        conn.execute(
            "UPDATE conversion_jobs SET heartbeat_at = ? WHERE id = ? AND worker_id = ? "
            "AND status IN ('claimed','converting','placing')",
            (_now_iso(), job_id, worker_id),
        )


def reclaim_stale_jobs(conn, cfg, tmp_root: Path) -> list[int]:
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=cfg.reclaim_staleness_threshold_s)).isoformat()
    reclaimed: list[int] = []
    with db.transaction(conn):
        rows = conn.execute(
            "SELECT id, tmp_dir, status FROM conversion_jobs "
            "WHERE status IN ('claimed','converting','placing') AND heartbeat_at < ?",
            (cutoff,),
        ).fetchall()
        for job_id, tmp_dir, status in rows:
            if status == "placing":
                already_written = conn.execute(
                    "SELECT 1 FROM conversions WHERE job_id = ? AND status = 'current'", (job_id,)
                ).fetchone()
                if already_written:
                    # The write + DB commit (spec §4 step 9(a)/(b)) already
                    # landed -- only the lock confirmation (9(c)/(d)) is
                    # outstanding, and worker.resume_unlocked_conversions
                    # retries that independently on every wake. Resetting to
                    # 'pending' here would trigger a wasted reconversion of a
                    # source that already has a valid current conversion.
                    continue
            if tmp_dir:
                tmp_path = Path(tmp_dir)
                if tmp_path.exists():
                    shutil.rmtree(tmp_path, ignore_errors=True)
            conn.execute(
                "UPDATE conversion_jobs SET status = 'pending', worker_id = NULL, "
                "claimed_at = NULL, heartbeat_at = NULL, tmp_dir = NULL WHERE id = ?",
                (job_id,),
            )
            reclaimed.append(job_id)
    return reclaimed
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_jobs.py -v
```

Expected: 19 passed. If the concurrency tests are ever flaky, re-check that `get_connection` truly sets `isolation_level=None` and that `claim_job` issues a raw `BEGIN IMMEDIATE` rather than going through `db.transaction()` — a deferred transaction here is the classic way this class of test goes flaky under load. `test_claim_deterministically_excludes_a_second_connection` should never be flaky (it forces the contention window explicitly rather than hoping for it); if that one fails, trust it over the barrier-based test.

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/jobs.py doc-ingest-app/tests/test_jobs.py
git commit -m "feat(doc-ingest): add DB-claimed job queue with heartbeat-based reclaim"
```

---

## Task 8: `metadata_readers.py` — independent integrity metadata

**Files:**
- Create: `doc-ingest-app/doc_ingest/metadata_readers.py`
- Test: `doc-ingest-app/tests/test_metadata_readers.py`

**Interfaces:**
- Consumes: `pypdf`, `python-docx` (`docx`), `openpyxl`.
- Produces: `read_pdf_page_count(path) -> int`, `read_docx_word_count(path) -> int`, `read_docx_table_count(path) -> int`, `read_xlsx_sheet_and_row_counts(path) -> tuple[int, int]`. Used by Gate 1 (Task 11) — **never** by `convert.py`, so the integrity check is independent of the thing it's checking (spec §8).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_metadata_readers.py
import docx
import openpyxl
from pypdf import PdfWriter

from doc_ingest import metadata_readers


def test_read_pdf_page_count(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    pdf_path = tmp_path / "three_pages.pdf"
    with open(pdf_path, "wb") as fh:
        writer.write(fh)
    assert metadata_readers.read_pdf_page_count(pdf_path) == 3


def test_read_docx_word_count(tmp_path):
    document = docx.Document()
    document.add_paragraph("one two three four five")
    document.add_paragraph("six seven")
    docx_path = tmp_path / "sample.docx"
    document.save(docx_path)
    assert metadata_readers.read_docx_word_count(docx_path) == 7


def test_read_docx_word_count_includes_table_cell_text(tmp_path):
    document = docx.Document()
    document.add_paragraph("one two three")  # 3 paragraph words
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "four five"    # 2 table words
    table.rows[0].cells[1].text = "six seven eight"  # 3 table words
    docx_path = tmp_path / "sample.docx"
    document.save(docx_path)
    assert metadata_readers.read_docx_word_count(docx_path) == 8  # 3 + 2 + 3


def test_read_docx_table_count(tmp_path):
    document = docx.Document()
    document.add_paragraph("intro")
    document.add_table(rows=2, cols=2)
    document.add_table(rows=1, cols=3)
    docx_path = tmp_path / "with_tables.docx"
    document.save(docx_path)
    assert metadata_readers.read_docx_table_count(docx_path) == 2


def test_read_xlsx_sheet_and_row_counts(tmp_path):
    workbook = openpyxl.Workbook()
    sheet1 = workbook.active
    sheet1.title = "Sheet1"
    for i in range(5):
        sheet1.append([i, i * 2])
    sheet2 = workbook.create_sheet("Sheet2")
    for i in range(3):
        sheet2.append([i])
    xlsx_path = tmp_path / "sample.xlsx"
    workbook.save(xlsx_path)
    sheet_count, row_count = metadata_readers.read_xlsx_sheet_and_row_counts(xlsx_path)
    assert sheet_count == 2
    assert row_count == 8
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_metadata_readers.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'doc_ingest.metadata_readers'`

- [ ] **Step 3: Write `doc_ingest/metadata_readers.py`**

```python
"""Independent (non-firecrawl) readers for the gauntlet's integrity checks
(spec §8) -- page/word/table/row counts computed from the source file
directly, never re-derived from firecrawl-parse's own output, so the check
is independent of the thing it's checking."""
from __future__ import annotations

from pathlib import Path

import docx
import openpyxl
from pypdf import PdfReader


def read_pdf_page_count(path: Path) -> int:
    return len(PdfReader(str(path)).pages)


def read_docx_word_count(path: Path) -> int:
    """Includes table cell text, not just paragraph text -- Gate 1's parity
    check (Task 11) compares this against len(output_body.split()), and the
    OUTPUT markdown's word count includes every pipe/cell token in a
    rendered table. Counting only paragraphs here would systematically
    undercount any docx with a substantial table, producing a false
    word_count_parity_failed rejection on a perfectly good conversion."""
    document = docx.Document(str(path))
    word_count = sum(len(paragraph.text.split()) for paragraph in document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                word_count += len(cell.text.split())
    return word_count


def read_docx_table_count(path: Path) -> int:
    return len(docx.Document(str(path)).tables)


def read_xlsx_sheet_and_row_counts(path: Path) -> tuple[int, int]:
    workbook = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    try:
        sheet_count = len(workbook.sheetnames)
        row_count_total = 0
        for name in workbook.sheetnames:
            sheet = workbook[name]
            row_count_total += sum(
                1 for row in sheet.iter_rows() if any(cell.value is not None for cell in row)
            )
        return sheet_count, row_count_total
    finally:
        workbook.close()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_metadata_readers.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/metadata_readers.py doc-ingest-app/tests/test_metadata_readers.py
git commit -m "feat(doc-ingest): add independent page/word/sheet/row-count readers"
```

---

## Task 9: `convert.py` — firecrawl SDK dispatch for local files

**Files:**
- Create: `doc-ingest-app/doc_ingest/convert.py`
- Test: `doc-ingest-app/tests/test_convert.py`
- Modify: `doc-ingest-app/requirements.txt` (Task 0)

**Interfaces:**
- Consumes: `Config.oversized_file_cap_bytes`, the `firecrawl-py` package's `Firecrawl` client.
- Produces: `ConversionResult` dataclass (`success`, `markdown_body`, `tool`, `error`), `convert_local_file(staged_path: Path, source_type: str, cfg: Config) -> ConversionResult`. Used by `worker.py` (Task 15).

**Uses the `firecrawl-py` Python SDK, not the CLI.** `run_ingest_cron.py` runs unattended under Task Scheduler, so nothing here can assume an interactive Claude Code session or the firecrawl-parse `SKILL.md`'s Bash-tool convention either way — but the SDK is also simply the better fit here: `Firecrawl().parse(bytes, filename=..., content_type=..., options=ParseOptions(formats=["markdown"]))` returns the converted markdown directly in memory (no intermediate output file to manage), and picks up `FIRECRAWL_API_KEY` from the environment automatically with no separate "is the CLI installed and on PATH" failure mode. firecrawl's documented cap is 50MB per file (`cfg.oversized_file_cap_bytes`); anything over that short-circuits without ever constructing a client.

**Only PDF/DOCX/XLSX/PPT go through this module.** TXT/MD are NOT routed through firecrawl at all — the format isn't in firecrawl's supported list (PDF/DOCX/DOC/ODT/RTF/XLSX/XLS/HTML), and spec §2/§8 call for a verbatim pass-through with frontmatter added, not a parse. `worker.py` (Task 15) branches before ever calling `convert_local_file` for those two types.

`firecrawl-py` is already in `requirements.txt` from Task 0 — no dependency change needed here.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_convert.py
from unittest.mock import MagicMock, patch

from doc_ingest.config import Config
from doc_ingest import convert


def test_oversized_file_short_circuits_without_constructing_a_client(tmp_path):
    cfg = Config(oversized_file_cap_bytes=10)
    staged = tmp_path / "huge.pdf"
    staged.write_bytes(b"x" * 100)

    with patch("firecrawl.Firecrawl") as mock_firecrawl_cls:
        result = convert.convert_local_file(staged, "pdf", cfg)
        mock_firecrawl_cls.assert_not_called()

    assert result.success is False
    assert result.error == "oversized_unsupported"


def test_successful_conversion_returns_the_parsed_markdown(tmp_path):
    cfg = Config()
    staged = tmp_path / "sample.pdf"
    staged.write_bytes(b"%PDF-1.4 fake")

    mock_client = MagicMock()
    mock_client.parse.return_value = MagicMock(markdown="# Converted body\n")
    with patch("firecrawl.Firecrawl", return_value=mock_client):
        result = convert.convert_local_file(staged, "pdf", cfg)

    assert result.success is True
    assert result.markdown_body == "# Converted body\n"
    assert result.tool == "firecrawl-parse"
    mock_client.parse.assert_called_once()
    _, kwargs = mock_client.parse.call_args
    assert kwargs["filename"] == "sample.pdf"
    assert kwargs["content_type"] == "application/pdf"


def test_parse_exception_is_a_failure_not_a_crash(tmp_path):
    cfg = Config()
    staged = tmp_path / "sample.pdf"
    staged.write_bytes(b"%PDF-1.4 fake")

    mock_client = MagicMock()
    mock_client.parse.side_effect = RuntimeError("parse failed")
    with patch("firecrawl.Firecrawl", return_value=mock_client):
        result = convert.convert_local_file(staged, "pdf", cfg)

    assert result.success is False
    assert "parse failed" in result.error


def test_ppt_rejection_is_flagged_unsupported_type_not_a_crash(tmp_path):
    cfg = Config()
    staged = tmp_path / "sample.ppt"
    staged.write_bytes(b"fake ppt bytes")

    mock_client = MagicMock()
    mock_client.parse.side_effect = RuntimeError("unsupported format")
    with patch("firecrawl.Firecrawl", return_value=mock_client):
        result = convert.convert_local_file(staged, "ppt", cfg)

    assert result.success is False
    assert result.error == "unsupported_type: unsupported format"


def test_empty_markdown_is_reported_as_a_failure_not_a_silent_pass(tmp_path):
    cfg = Config()
    staged = tmp_path / "sample.pdf"
    staged.write_bytes(b"%PDF-1.4 fake")

    mock_client = MagicMock()
    mock_client.parse.return_value = MagicMock(markdown="")
    with patch("firecrawl.Firecrawl", return_value=mock_client):
        result = convert.convert_local_file(staged, "pdf", cfg)

    assert result.success is False
    assert result.error == "empty_markdown_returned"


def test_content_type_is_selected_by_source_type(tmp_path):
    cfg = Config()
    staged = tmp_path / "sample.xlsx"
    staged.write_bytes(b"fake xlsx bytes")

    mock_client = MagicMock()
    mock_client.parse.return_value = MagicMock(markdown="body")
    with patch("firecrawl.Firecrawl", return_value=mock_client):
        convert.convert_local_file(staged, "xlsx", cfg)

    _, kwargs = mock_client.parse.call_args
    assert kwargs["content_type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
```

None of these need `@pytest.mark.allow_subprocess` or `@pytest.mark.allow_network` — the SDK client is mocked at the `firecrawl.Firecrawl` constructor, so no process is spawned and no real HTTP call is made.

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_convert.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'doc_ingest.convert'`

- [ ] **Step 3: Write `doc_ingest/convert.py`**

```python
"""Dispatches a staged local file to the firecrawl-py SDK. Reads
FIRECRAWL_API_KEY from the environment automatically (already set as a
Windows user environment variable per SETUP.md) -- run_ingest_cron.py runs
unattended under Task Scheduler, so nothing here can assume an interactive
Claude Code session."""
from __future__ import annotations

import dataclasses
from pathlib import Path

_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
}


@dataclasses.dataclass(frozen=True)
class ConversionResult:
    success: bool
    markdown_body: str | None
    tool: str
    error: str | None


def convert_local_file(staged_path: Path, source_type: str, cfg) -> ConversionResult:
    size = staged_path.stat().st_size
    if size > cfg.oversized_file_cap_bytes:
        return ConversionResult(success=False, markdown_body=None, tool="firecrawl-parse", error="oversized_unsupported")

    # Imported here, not at module scope, so tests that patch
    # "firecrawl.Firecrawl" via unittest.mock.patch intercept the same
    # attribute this function resolves at call time.
    from firecrawl import Firecrawl
    from firecrawl.v2.types import ParseOptions

    client = Firecrawl()
    content_type = _CONTENT_TYPES.get(source_type)

    try:
        parsed = client.parse(
            staged_path.read_bytes(),
            filename=staged_path.name,
            content_type=content_type,
            options=ParseOptions(formats=["markdown"]),
        )
    except Exception as exc:
        error = str(exc)
        if source_type == "ppt":
            return ConversionResult(success=False, markdown_body=None, tool="firecrawl-parse",
                                     error=f"unsupported_type: {error}")
        return ConversionResult(success=False, markdown_body=None, tool="firecrawl-parse", error=error)

    if not parsed.markdown:
        return ConversionResult(success=False, markdown_body=None, tool="firecrawl-parse", error="empty_markdown_returned")

    return ConversionResult(success=True, markdown_body=parsed.markdown, tool="firecrawl-parse", error=None)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_convert.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/convert.py doc-ingest-app/tests/test_convert.py
git commit -m "feat(doc-ingest): dispatch local-file conversion to the firecrawl-py SDK"
```

---

## Task 10: `frontmatter.py` — build + YAML-safe serialize

**Files:**
- Create: `doc-ingest-app/doc_ingest/frontmatter.py`
- Test: `doc-ingest-app/tests/test_frontmatter.py`

**Interfaces:**
- Consumes: `yaml` (PyYAML).
- Produces: `build_frontmatter(base: dict, extras: dict) -> dict`, `serialize(frontmatter: dict, body: str) -> str`, `parse(assembled_markdown: str) -> tuple[dict, str]` (frontmatter dict + body, or raises `yaml.YAMLError`/`ValueError` — used by Gate 1's "parses as well-formed YAML" check, Task 11). Used by `worker.py` (Task 15).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_frontmatter.py
import pytest
import yaml

from doc_ingest import frontmatter


def _base(source_path="Folder/Notes.docx"):
    return {
        "source_path": source_path,
        "source_type": "docx",
        "source_hash": "abc123",
        "source_modified_at": "2026-08-01T00:00:00+00:00",
        "converted_at": "2026-08-13T00:00:00+00:00",
        "conversion_tool": "firecrawl-parse",
        "version": 1,
        "status": "current",
        "business_line": "freedom2beu",
        "gauntlet_passed_at": "2026-08-13T00:00:01+00:00",
    }


def test_build_frontmatter_merges_base_and_extras():
    fm = frontmatter.build_frontmatter(_base(), {"word_count": 42})
    assert fm["word_count"] == 42
    assert fm["business_line"] == "freedom2beu"


def test_serialize_round_trips_through_a_real_yaml_parser():
    fm = frontmatter.build_frontmatter(_base(), {"word_count": 42})
    assembled = frontmatter.serialize(fm, "# Body\n\ncontent here")
    parsed_fm, body = frontmatter.parse(assembled)
    assert parsed_fm["word_count"] == 42
    assert parsed_fm["source_path"] == "Folder/Notes.docx"
    assert body.strip() == "# Body\n\ncontent here"


def test_serialize_handles_special_characters_from_real_source_paths():
    special_path = "Client's Notes & Session #3: Recap.docx"
    fm = frontmatter.build_frontmatter(_base(source_path=special_path), {})
    assembled = frontmatter.serialize(fm, "body")
    parsed_fm, _ = frontmatter.parse(assembled)
    assert parsed_fm["source_path"] == special_path


def test_serialize_uses_a_real_yaml_library_not_string_interpolation():
    fm = frontmatter.build_frontmatter(_base(), {})
    assembled = frontmatter.serialize(fm, "body")
    header = assembled.split("---")[1]
    reparsed = yaml.safe_load(header)
    assert reparsed["source_path"] == fm["source_path"]


def test_parse_raises_on_malformed_yaml():
    broken = "---\nsource_path: [unterminated\n---\nbody"
    with pytest.raises(yaml.YAMLError):
        frontmatter.parse(broken)


def test_parse_raises_on_missing_frontmatter_delimiters():
    with pytest.raises(ValueError):
        frontmatter.parse("just a body, no frontmatter at all")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_frontmatter.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'doc_ingest.frontmatter'`

- [ ] **Step 3: Write `doc_ingest/frontmatter.py`**

```python
"""Frontmatter is always built as a dict and serialized via PyYAML's safe
dumper -- never hand-formatted string interpolation. Real source_path values
in this corpus contain curly apostrophes, '&', ':', '#' (spec §7); a dumper
quotes/escapes these correctly by construction, hand-formatting would not."""
from __future__ import annotations

import yaml

REQUIRED_BASE_FIELDS = (
    "source_path", "source_type", "source_hash", "source_modified_at",
    "converted_at", "conversion_tool", "version", "status", "business_line",
    "gauntlet_passed_at",
)


def build_frontmatter(base: dict, extras: dict) -> dict:
    merged = dict(base)
    merged.update(extras)
    return merged


def serialize(fm: dict, body: str) -> str:
    header = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{header}---\n\n{body}"


def parse(assembled_markdown: str) -> tuple[dict, str]:
    if not assembled_markdown.startswith("---\n"):
        raise ValueError("no frontmatter delimiter at start of file")
    _, _, rest = assembled_markdown.partition("---\n")
    header, sep, body = rest.partition("\n---\n")
    if not sep:
        raise ValueError("no closing frontmatter delimiter found")
    fm = yaml.safe_load(header)
    if not isinstance(fm, dict):
        raise ValueError("frontmatter did not parse to a mapping")
    return fm, body.lstrip("\n")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_frontmatter.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/frontmatter.py doc-ingest-app/tests/test_frontmatter.py
git commit -m "feat(doc-ingest): add YAML-safe frontmatter build/serialize/parse"
```

---

## Task 11: `gauntlet.py` Gate 1 — content integrity

**Files:**
- Create: `doc-ingest-app/doc_ingest/gauntlet.py`
- Test: `doc-ingest-app/tests/test_gauntlet_gate1.py`

**Interfaces:**
- Consumes: `frontmatter.parse` (Task 10), `Config` tolerance fields (Task 1).
- Produces: `GauntletResult` dataclass (`passed: bool`, `failure_reason: str | None`), `run_gate1(source_type: str, source_size_bytes: int, assembled_markdown: str, independent_metadata: dict, cfg) -> GauntletResult`. Used by `worker.py` (Task 15).

**`independent_metadata` carries only SOURCE-side values** — `page_count` (pdf), `source_word_count`/`source_table_count` (docx/gdoc), `source_sheet_count`/`source_row_count` (xlsx/gsheet) — from `metadata_readers.py` (Task 8), reading the source file directly. Gate 1 computes every OUTPUT-side count itself, from `assembled_markdown`'s body, rather than expecting the caller to supply it:
- PDF words-per-page: `len(body.split()) / page_count`.
- XLSX/GDOC table & sheet counts: one markdown table (one `|---|` separator row) is treated as one table/sheet — see `_count_output_table_blocks` below. This is a heuristic against firecrawl's actual markdown table structure, not verified against a real conversion sample; calibrate before trusting the tolerance bands (spec §15).

This keeps Gate 1 the single owner of "what does the output actually contain" — no other module needs to agree on a shared vocabulary of output-side metadata keys, which is what let the original mismatch (Gate 1 reading keys nothing ever wrote) happen silently.

Every check is mechanical (no LLM). A failure returns a specific `failure_reason` string; nothing is silently dropped (spec §8's "quarantine, don't discard").

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gauntlet_gate1.py
from doc_ingest.config import Config
from doc_ingest import frontmatter, gauntlet


def _assembled(body="A perfectly ordinary converted document with real words in it."):
    fm = frontmatter.build_frontmatter({
        "source_path": "a.txt", "source_type": "txt", "source_hash": "h",
        "source_modified_at": "2026-08-01T00:00:00+00:00", "converted_at": "2026-08-13T00:00:00+00:00",
        "conversion_tool": "passthrough", "version": 1, "status": "current",
        "business_line": "freedom2beu", "gauntlet_passed_at": "2026-08-13T00:00:01+00:00",
    }, {})
    return frontmatter.serialize(fm, body)


def test_universal_check_rejects_empty_body():
    cfg = Config()
    result = gauntlet.run_gate1("txt", 100, _assembled(body=""), {}, cfg)
    assert result.passed is False
    assert result.failure_reason == "empty_body"


def test_universal_check_rejects_malformed_frontmatter():
    cfg = Config()
    broken = "---\nsource_path: [unterminated\n---\nbody"
    result = gauntlet.run_gate1("txt", 100, broken, {}, cfg)
    assert result.passed is False
    assert result.failure_reason == "malformed_frontmatter"


def test_universal_check_rejects_high_replacement_char_ratio():
    cfg = Config(replacement_char_ratio_max=0.01)
    garbled_body = "�" * 50 + "ok text " * 5
    result = gauntlet.run_gate1("txt", 100, _assembled(body=garbled_body), {}, cfg)
    assert result.passed is False
    assert result.failure_reason == "encoding_garbled"


def test_universal_check_rejects_unbalanced_code_fences():
    body = "```python\nprint('hi')\n" + "more text with no closing fence"
    result = gauntlet.run_gate1("txt", 100, _assembled(body=body), {}, Config())
    assert result.passed is False
    assert result.failure_reason == "unbalanced_code_fences"


def test_universal_checks_pass_for_a_clean_document():
    result = gauntlet.run_gate1("txt", 100, _assembled(), {}, Config())
    assert result.passed is True


def test_size_ratio_floor_applies_to_docx_and_rejects_a_truncated_conversion():
    cfg = Config(size_ratio_floor=0.05)
    tiny_body = "x"
    result = gauntlet.run_gate1("docx", 100000, _assembled(body=tiny_body), {"word_count": 1}, cfg)
    assert result.passed is False
    assert result.failure_reason == "below_size_ratio_floor"


def test_size_ratio_floor_does_not_apply_to_pdf():
    cfg = Config(size_ratio_floor=0.05)
    # A 4MB PDF producing a tiny amount of markdown is normal, not truncation
    # (spec §8). page_count=10 with this body's ~120 words gives ~12
    # words/page, safely above the scanned-PDF floor too, so this test
    # isolates the size-ratio-exemption claim from the scanned-PDF check.
    result = gauntlet.run_gate1(
        "pdf", 4_000_000,
        _assembled(body="short markdown from a dense pdf " * 20),
        {"page_count": 10}, cfg,
    )
    assert result.passed is True


def test_pdf_flags_likely_scanned_no_text_layer():
    # words_per_page is NOT passed in -- Gate 1 computes it itself as
    # len(body.split()) / page_count, from the actual assembled markdown,
    # never from a value the caller hands in (that was the bug: nothing
    # upstream of Gate 1 ever produced a "word_count_per_page" key, so this
    # check silently never fired).
    cfg = Config(scanned_pdf_words_per_page_floor=3.0)
    result = gauntlet.run_gate1(
        "pdf", 500_000, _assembled(body="a few words only"),
        {"page_count": 20}, cfg,
    )
    assert result.passed is False
    assert result.failure_reason == "likely_scanned_no_text_layer"


def test_pdf_passes_with_a_healthy_words_per_page():
    cfg = Config(scanned_pdf_words_per_page_floor=3.0)
    body = " ".join(["word"] * 200)  # 200 words / 5 pages = 40 words/page
    result = gauntlet.run_gate1("pdf", 500_000, _assembled(body=body), {"page_count": 5}, cfg)
    assert result.passed is True


def test_docx_word_count_parity_within_tolerance():
    # size_ratio_floor=0.0 isolates the word-count-parity check from the
    # size-ratio-floor check that ALSO applies to docx (spec §8) -- these
    # tiny synthetic bodies are nowhere near 5% of a real 50000-byte source,
    # and without disabling the floor here every one of these tests fails on
    # below_size_ratio_floor before it ever reaches the check it's named for.
    cfg = Config(word_count_tolerance_pct=0.15, size_ratio_floor=0.0)
    body = " ".join(["word"] * 95)
    result = gauntlet.run_gate1("docx", 50000, _assembled(body=body), {"source_word_count": 100}, cfg)
    assert result.passed is True


def test_docx_word_count_parity_rejects_outside_tolerance():
    cfg = Config(word_count_tolerance_pct=0.15, size_ratio_floor=0.0)
    body = " ".join(["word"] * 40)
    result = gauntlet.run_gate1("docx", 50000, _assembled(body=body), {"source_word_count": 100}, cfg)
    assert result.passed is False
    assert result.failure_reason == "word_count_parity_failed"


def test_docx_table_count_parity_fails_on_mismatch():
    # separator-row count in the OUTPUT markdown is the proxy for "how many
    # tables" (spec §15 flags this as a heuristic needing calibration
    # against a real firecrawl conversion sample -- see gauntlet.py's
    # _count_output_table_blocks docstring).
    cfg = Config(word_count_tolerance_pct=0.15, size_ratio_floor=0.0)
    body = "no tables here at all, just prose " * 5  # 35 words, no "|---|" rows
    result = gauntlet.run_gate1(
        "docx", 50000, _assembled(body=body),
        {"source_word_count": 35, "source_table_count": 2}, cfg,
    )
    assert result.passed is False
    assert result.failure_reason == "table_count_mismatch"


def test_docx_table_count_parity_passes_on_match():
    cfg = Config(word_count_tolerance_pct=0.15, size_ratio_floor=0.0)
    body = "words words words\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
    # len(body.split()) counts every whitespace-separated token, including
    # the pipe/cell tokens inside the table -- 3 prose words + 5 header-row
    # tokens ("|","A","|","B","|") + 1 separator token + 5 data-row tokens
    # ("|","1","|","2","|") = 14. Computed explicitly here rather than
    # guessed, since it's exactly the kind of off-by-a-lot mistake that
    # silently makes a test assert nothing.
    assert len(body.split()) == 14
    result = gauntlet.run_gate1(
        "docx", 50000, _assembled(body=body),
        {"source_word_count": 14, "source_table_count": 1}, cfg,
    )
    assert result.passed is True


def test_xlsx_sheet_and_row_count_parity():
    # One markdown table (one "|---|" separator row) == one sheet; rows are
    # counted from the same table, minus its own header and separator lines.
    # size_ratio_floor=0.0 for the same reason as the docx tests above --
    # xlsx is also in the size-ratio-floor type list (spec §8).
    cfg = Config(row_count_tolerance_pct=0.05, sheet_count_tolerance=0, size_ratio_floor=0.0)
    body = (
        "## Sheet1\n\n| A | B |\n|---|---|\n"
        + "\n".join(f"| {i} | {i * 2} |" for i in range(10))
        + "\n"
    )
    result = gauntlet.run_gate1(
        "xlsx", 20000, _assembled(body=body),
        {"source_sheet_count": 1, "source_row_count": 10}, cfg,
    )
    assert result.passed is True


def test_xlsx_sheet_count_mismatch_fails():
    cfg = Config(size_ratio_floor=0.0)
    body = "## Sheet1\n\n| A |\n|---|\n| 1 |\n"
    result = gauntlet.run_gate1(
        "xlsx", 20000, _assembled(body=body),
        {"source_sheet_count": 3, "source_row_count": 1}, cfg,
    )
    assert result.passed is False
    assert result.failure_reason == "sheet_count_mismatch"


def test_ppt_unsupported_is_a_gate1_failure_not_a_crash():
    result = gauntlet.run_gate1("ppt", 20000, "", {"conversion_error": "unsupported_type: bad format"}, Config())
    assert result.passed is False
    assert result.failure_reason == "unsupported_type: bad format"


def test_txt_md_identity_copy_only_gets_universal_checks():
    # md IS in the size-ratio-floor type list (spec §8's own bullet 2), but
    # since worker.py routes txt/md through a verbatim pass-through (Task 15),
    # the output body is always ~the same size as the source -- the floor
    # is technically active for this type but never the thing that fails it.
    # Proven here with a source_size_bytes deliberately larger than what the
    # floor would tolerate for a truncated conversion, so this test would
    # catch the floor firing if that assumption were ever wrong.
    cfg = Config(size_ratio_floor=0.5)
    result = gauntlet.run_gate1("md", 100, _assembled(), {}, cfg)  # body is ~60 bytes, ratio ~0.6
    assert result.passed is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_gauntlet_gate1.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'doc_ingest.gauntlet'`

- [ ] **Step 3: Write `doc_ingest/gauntlet.py`** (Gate 1 only — Gate 2 is Task 12, appended to this same file)

```python
"""Two independent, purely mechanical gates -- no LLM evaluation anywhere.
A failure records a specific failure_reason and blocks the write; nothing is
silently dropped, matching pipeline_app.db's _quarantine_unknown_platforms
migration's quarantine-don't-discard pattern (spec §8, cited narrowly to
that one precedent, not as a repo-wide convention)."""
from __future__ import annotations

import dataclasses
import re

from doc_ingest import frontmatter

_CODE_FENCE_RE = re.compile(r"^```", re.MULTILINE)
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$", re.MULTILINE)


@dataclasses.dataclass(frozen=True)
class GauntletResult:
    passed: bool
    failure_reason: str | None = None


def _count_output_table_blocks(body: str) -> int:
    """One markdown table == one separator row (the `|---|---|` line). Used
    as a proxy for both 'how many sheets' (xlsx/gsheet) and 'how many
    tables' (docx/gdoc) in firecrawl's markdown output. A heuristic, not
    verified against a real firecrawl conversion sample -- calibrate the
    tolerance bands against real corpus output before trusting this in
    production (spec §15)."""
    return len(_TABLE_SEPARATOR_RE.findall(body))


def _count_output_table_rows(body: str) -> int:
    all_rows = len(_TABLE_ROW_RE.findall(body))
    separators = len(_TABLE_SEPARATOR_RE.findall(body))
    header_rows = separators  # exactly one header row precedes each separator
    return max(all_rows - separators - header_rows, 0)


def _universal_checks(assembled_markdown: str, cfg) -> GauntletResult | None:
    try:
        fm, body = frontmatter.parse(assembled_markdown)
    except Exception:
        return GauntletResult(False, "malformed_frontmatter")

    if not body.strip():
        return GauntletResult(False, "empty_body")

    for field in frontmatter.REQUIRED_BASE_FIELDS:
        if field not in fm:
            return GauntletResult(False, "malformed_frontmatter")

    replacement_ratio = body.count("�") / max(len(body), 1)
    if replacement_ratio > cfg.replacement_char_ratio_max:
        return GauntletResult(False, "encoding_garbled")

    if len(_CODE_FENCE_RE.findall(body)) % 2 != 0:
        return GauntletResult(False, "unbalanced_code_fences")

    return None  # all universal checks passed


def run_gate1(source_type: str, source_size_bytes: int, assembled_markdown: str, independent_metadata: dict, cfg) -> GauntletResult:
    if source_type == "ppt" and "conversion_error" in independent_metadata:
        return GauntletResult(False, independent_metadata["conversion_error"])

    universal_failure = _universal_checks(assembled_markdown, cfg)
    if universal_failure is not None:
        return universal_failure

    _, body = frontmatter.parse(assembled_markdown)

    if source_type in ("docx", "xlsx", "txt", "md"):
        ratio = len(body.encode("utf-8")) / max(source_size_bytes, 1)
        if ratio < cfg.size_ratio_floor:
            return GauntletResult(False, "below_size_ratio_floor")

    if source_type == "pdf":
        page_count = independent_metadata.get("page_count")
        if page_count:
            words_per_page = len(body.split()) / page_count
            if words_per_page < cfg.scanned_pdf_words_per_page_floor:
                return GauntletResult(False, "likely_scanned_no_text_layer")

    if source_type in ("docx", "gdoc"):
        source_wc = independent_metadata.get("source_word_count")
        if source_wc:
            output_wc = len(body.split())
            low = source_wc * (1 - cfg.word_count_tolerance_pct)
            high = source_wc * (1 + cfg.word_count_tolerance_pct)
            if not (low <= output_wc <= high):
                return GauntletResult(False, "word_count_parity_failed")

        source_tables = independent_metadata.get("source_table_count")
        if source_tables is not None:
            if _count_output_table_blocks(body) != source_tables:
                return GauntletResult(False, "table_count_mismatch")

    if source_type in ("xlsx", "gsheet"):
        source_sheets = independent_metadata.get("source_sheet_count")
        if source_sheets is not None:
            output_sheets = _count_output_table_blocks(body)
            if abs(source_sheets - output_sheets) > cfg.sheet_count_tolerance:
                return GauntletResult(False, "sheet_count_mismatch")

        source_rows = independent_metadata.get("source_row_count")
        if source_rows:
            output_rows = _count_output_table_rows(body)
            low = source_rows * (1 - cfg.row_count_tolerance_pct)
            high = source_rows * (1 + cfg.row_count_tolerance_pct)
            if not (low <= output_rows <= high):
                return GauntletResult(False, "row_count_mismatch")

    return GauntletResult(True, None)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_gauntlet_gate1.py -v
```

Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/gauntlet.py doc-ingest-app/tests/test_gauntlet_gate1.py
git commit -m "feat(doc-ingest): add Gate 1 mechanical content-integrity checks"
```

---

## Task 12: `gauntlet.py` Gate 2 — naming & placement

**Files:**
- Modify: `doc-ingest-app/doc_ingest/gauntlet.py`
- Test: `doc-ingest-app/tests/test_gauntlet_gate2.py`

**Interfaces:**
- Consumes: `naming.build_dest_rel_path`, `naming.resolve_collision` (Task 4); `db.transaction` (Task 3).
- Produces: `run_gate2(conn, source_rel_path: str, source_file_id: int, version: int, cfg) -> tuple[GauntletResult, str | None]` — second element is the final (possibly collision-suffixed) dest path on success. Used by `worker.py` (Task 15).

**Full-path length, not relative-path length**: spec §6 measures the full destination path (`str(cfg.converted_root)` + separator + the relative path), not the relative path alone. Gate 2 computes `prefix_len = len(str(cfg.converted_root)) + 1` and passes it through to `naming.build_dest_rel_path` (Task 4), then re-verifies the actual absolute length afterward — a relative path that individually fits `cfg.long_path_threshold_chars` can still push the real file path over Windows' limit once `C:\Projects\ContentStudio\Freedom2BeU\converted\` is prepended.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gauntlet_gate2.py
from doc_ingest.config import Config
from doc_ingest import gauntlet


def _seed_conversion(conn, source_file_id, output_path, status="current"):
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "conversion_tool, converted_at) VALUES (?, 1, ?, ?, 'pdf', 'firecrawl-parse', ?)",
        (source_file_id, output_path, status, now),
    )
    conn.commit()


def _seed_source_file(conn, rel_path):
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
        "VALUES (?, 'pdf', 'convertible', ?, ?)", (rel_path, now, now),
    )
    conn.commit()
    return conn.execute("SELECT id FROM source_files WHERE rel_path = ?", (rel_path,)).fetchone()[0]


def test_gate2_resolves_a_clean_destination(conn):
    source_id = _seed_source_file(conn, "Folder/Notes.pdf")
    result, dest = gauntlet.run_gate2(conn, "Folder/Notes.pdf", source_id, version=1, cfg=Config())
    assert result.passed is True
    assert dest == "Folder/Notes.pdf.md"


def test_gate2_measures_the_full_absolute_path_not_just_the_relative_one(conn):
    # A relative path that would need no shortening at all in isolation
    # (naming.build_dest_rel_path with prefix_len=0) still needs MORE
    # shortening once converted_root's own length is accounted for -- proves
    # Gate 2 is actually threading prefix_len through, not just calling
    # naming.py the same way Task 4's own unit tests do.
    from doc_ingest import naming

    cfg = Config(long_path_threshold_chars=150)
    long_rel_path = "/".join([
        "Client Coaching Session Recordings And Notes",
        "2026 Individual Sessions Archive",
        "Very Long Coaching Session Transcript With A Lot Of Detail In The Name.pdf",
    ])
    source_id = _seed_source_file(conn, long_rel_path)

    dest_ignoring_prefix = naming.build_dest_rel_path(long_rel_path, version=1, cfg=cfg, prefix_len=0)
    result, dest = gauntlet.run_gate2(conn, long_rel_path, source_id, version=1, cfg=cfg)

    prefix_len = len(str(cfg.converted_root)) + 1
    assert result.passed is True
    assert prefix_len + len(dest) <= cfg.long_path_threshold_chars
    assert len(dest) <= len(dest_ignoring_prefix)


def test_gate2_rejects_path_traversal_even_if_naming_ever_stopped_stripping_it(conn, monkeypatch):
    # naming.build_dest_rel_path today always neutralizes ".." (a segment of
    # only dots is stripped entirely by sanitize_component's trailing-dot
    # rstrip), so this exercises Gate 2's OWN defense-in-depth check in
    # isolation -- it must reject a traversal-shaped path even if naming.py
    # ever regressed and stopped stripping it.
    from doc_ingest import naming
    source_id = _seed_source_file(conn, "a.pdf")
    monkeypatch.setattr(naming, "build_dest_rel_path", lambda *a, **kw: "../../escape.pdf.md")
    result, dest = gauntlet.run_gate2(conn, "a.pdf", source_id, version=1, cfg=Config())
    assert result.passed is False
    assert result.failure_reason == "path_traversal_rejected"
    assert dest is None


def test_gate2_logs_a_collision_and_appends_a_hash_suffix(conn):
    source_a = _seed_source_file(conn, "Folder/Notes.pdf")
    source_b = _seed_source_file(conn, "Folder/OtherNotes.pdf")
    _seed_conversion(conn, source_a, "Folder/Notes.pdf.md")

    # Force a collision by asserting b's natural dest equals a's (simulated
    # via monkeypatched naming in a real test double, or -- simpler here --
    # by seeding a conversions row directly at b's natural destination under
    # a DIFFERENT source_file_id):
    _seed_conversion(conn, source_a, "Folder/OtherNotes.pdf.md", status="superseded")

    result, dest = gauntlet.run_gate2(conn, "Folder/OtherNotes.pdf", source_b, version=1, cfg=Config())
    assert result.passed is True
    assert dest != "Folder/OtherNotes.pdf.md"
    event = conn.execute("SELECT event_type FROM events WHERE event_type = 'naming_collision_resolved'").fetchone()
    assert event is not None


def test_gate2_trims_a_collision_suffix_that_would_exceed_the_threshold(conn):
    # A dest exactly at budget before the collision suffix is appended --
    # the length check earlier in run_gate2 runs BEFORE resolve_collision,
    # so it can't have caught an overage the suffix itself introduces.
    # "OtherNotes.pdf.md" (17 chars) fits; "OtherNotes.pdf~XXXXXXXX.md"
    # (26 chars, after the collision suffix) doesn't -- threshold is set
    # squarely between the two so only the post-collision form overflows.
    prefix_len = len(str(Config().converted_root)) + 1
    threshold = prefix_len + 20
    cfg = Config(long_path_threshold_chars=threshold)

    source_a = _seed_source_file(conn, "Original.pdf")
    source_b = _seed_source_file(conn, "OtherNotes.pdf")
    _seed_conversion(conn, source_a, "OtherNotes.pdf.md")  # occupies b's natural dest

    result, dest = gauntlet.run_gate2(conn, "OtherNotes.pdf", source_b, version=1, cfg=cfg)

    assert result.passed is True
    assert dest != "OtherNotes.pdf.md"
    assert prefix_len + len(dest) <= threshold
    assert dest.endswith(".md")


def test_gate2_does_not_treat_own_prior_versions_as_a_collision(conn):
    source_id = _seed_source_file(conn, "Folder/Notes.pdf")
    _seed_conversion(conn, source_id, "Folder/Notes.pdf.md", status="superseded")
    result, dest = gauntlet.run_gate2(conn, "Folder/Notes.pdf", source_id, version=2, cfg=Config())
    assert result.passed is True
    assert dest == "Folder/Notes.pdf.v2.md"


def test_gate2_rejects_a_path_that_would_resolve_outside_converted_root(conn):
    source_id = _seed_source_file(conn, "a.pdf")
    result, dest = gauntlet.run_gate2(conn, "a.pdf", source_id, version=1, cfg=Config())
    assert ".." not in dest
    assert not dest.startswith("/")
    assert not dest.startswith("\\")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_gauntlet_gate2.py -v
```

Expected: FAIL with `AttributeError: module 'doc_ingest.gauntlet' has no attribute 'run_gate2'`

- [ ] **Step 3: Append to `doc_ingest/gauntlet.py`**

```python
import datetime as dt
import json

from doc_ingest import db, naming


def _is_dest_taken(conn, dest_rel_path: str, exclude_source_file_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM conversions WHERE output_path = ? AND source_file_id != ? LIMIT 1",
        (dest_rel_path, exclude_source_file_id),
    ).fetchone()
    return row is not None


def run_gate2(conn, source_rel_path: str, source_file_id: int, version: int, cfg):
    # +1 for the path separator between converted_root and the relative path
    # this returns -- naming.build_dest_rel_path (Task 4) needs this to
    # shorten against the FULL destination path, not just the relative
    # portion (spec §6).
    prefix_len = len(str(cfg.converted_root)) + 1
    dest = naming.build_dest_rel_path(source_rel_path, version, cfg, prefix_len=prefix_len)

    normalized = dest.replace("\\", "/")
    if ".." in normalized.split("/") or normalized.startswith("/"):
        return GauntletResult(False, "path_traversal_rejected"), None

    if prefix_len + len(dest) > cfg.long_path_threshold_chars:
        return GauntletResult(False, "path_still_over_threshold_after_shortening"), None

    resolved_dest, collided = naming.resolve_collision(
        dest, is_taken=lambda p: _is_dest_taken(conn, p, source_file_id)
    )
    if collided:
        # resolve_collision appends a ~8-char hash suffix, which can push a
        # dest that was exactly at budget over cfg.long_path_threshold_chars
        # -- the length check above ran BEFORE this suffix existed, so it
        # can't have caught this. Trim the overage off the end of the stem,
        # immediately before the collision suffix, rather than failing a job
        # whose only real problem was a naming collision that got resolved.
        overage = prefix_len + len(resolved_dest) - cfg.long_path_threshold_chars
        if overage > 0:
            stem, sep, suffix = resolved_dest.rpartition("~")
            resolved_dest = f"{stem[:-overage] if overage < len(stem) else ''}{sep}{suffix}"
        with db.transaction(conn):
            conn.execute(
                "INSERT INTO events (ts, event_type, source_file_id, details_json) VALUES (?, ?, ?, ?)",
                (
                    dt.datetime.now(dt.timezone.utc).isoformat(),
                    "naming_collision_resolved",
                    source_file_id,
                    json.dumps({"original_dest": dest, "resolved_dest": resolved_dest}),
                ),
            )

    return GauntletResult(True, None), resolved_dest
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_gauntlet_gate2.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/gauntlet.py doc-ingest-app/tests/test_gauntlet_gate2.py
git commit -m "feat(doc-ingest): add Gate 2 naming/placement checks with collision logging"
```

---

## Task 13: `lock.py` — read-only enforcement (Windows ACL)

**Files:**
- Create: `doc-ingest-app/doc_ingest/lock.py`
- Test: `doc-ingest-app/tests/test_lock.py`
- Modify: `doc-ingest-app/tests/conftest.py` (add the `lock_test_dir` fixture)
- Modify: `.gitignore` (repo root)

**Interfaces:**
- Consumes: `subprocess` (icacls), `os`/`stat` (read-only attribute).
- Produces: `apply_readonly_lock(path: Path) -> None`, `verify_locked(path: Path) -> bool`. Used by `worker.py` (Task 15).

**Two ACL calls, not one — and why.** Windows grants an object's *owner* implicit `READ_CONTROL`/`WRITE_DAC` regardless of the file's own DACL, unless the special **OWNER RIGHTS** principal (well-known SID `S-1-3-4`) is *also* given an explicit entry — that second entry is what actually overrides the implicit grant. Denying only the account's own SID (as an earlier draft of this task did) leaves that implicit-owner hole open: the same non-elevated account that created the file could still `icacls /reset` it, because the account-level deny never touched the implicit owner grant in the first place. `apply_readonly_lock` therefore issues the account-level deny *and* an OWNER RIGHTS deny; only the second one is what spec §10 means by "closes the hole."

**This makes true idempotency at the icacls-call level impossible, on purpose.** Once the OWNER RIGHTS deny has landed, `WRITE_DAC` really is denied to the owner — including for a second `icacls /deny` call, which itself needs `WRITE_DAC` to modify the DACL. A file that is fully locked cannot be "re-locked": that failure *is* the security property working. `apply_readonly_lock` is idempotent at the **call** level instead: it checks `verify_locked()` first and returns immediately if the lock has already fully landed, so it never attempts a second icacls call against an already-locked file. This is also exactly what makes `worker.resume_unlocked_conversions` (Task 15) safe to call repeatedly — a *partially* locked file (crashed between the two icacls calls) still has `WRITE_DAC` available to finish the job; a *fully* locked file is left alone.

**Test hygiene tradeoff, stated plainly.** A file this module fully locks genuinely cannot be deleted afterward by the same non-elevated account (`DE` is denied at both the account and OWNER RIGHTS level) — that is the feature. Tests that perform a real lock therefore use a dedicated `lock_test_dir` fixture (below), **not** `tmp_path`: pytest's `tmp_path` retention cleanup would hit a real, expected `PermissionError` on every old run. `lock_test_dir` is a stable, gitignored directory that accumulates locked fixtures over time; clear it periodically from an elevated shell. Every other task that needs "a locked file" (Task 15's worker tests, Task 21's integration test) mocks `lock.apply_readonly_lock`/`lock.verify_locked` instead of performing a real lock, precisely to avoid multiplying this cost across the suite — this task and Task 21's two dedicated real-enforcement tests are the only places a real lock happens.

- [ ] **Step 1: Add the `lock_test_dir` fixture to `tests/conftest.py`**

```python
# add to tests/conftest.py, alongside the existing fixtures
@pytest.fixture
def lock_test_dir():
    """Real icacls locking is intentionally one-way and the same non-elevated
    account cannot undo it (spec §10) -- files created here are NOT
    guaranteed deletable after a test locks them. Deliberately NOT tmp_path:
    pytest's retention cleanup of old tmp_path runs would hit a real
    PermissionError. Gitignored; accumulates over time; clear from an
    elevated shell periodically."""
    d = Path(__file__).resolve().parent / ".lock_test_scratch"
    d.mkdir(exist_ok=True)
    return d
```

`conftest.py`'s existing `from pathlib import Path` import already covers this; no new imports needed.

- [ ] **Step 2: Add `.lock_test_scratch/` to `.gitignore`**

```gitignore
# Real icacls-locked test fixtures (Task 13) -- not guaranteed deletable by
# the same non-elevated account that created them; accumulates over time.
doc-ingest-app/tests/.lock_test_scratch/
```

- [ ] **Step 3: Write the failing test**

```python
# tests/test_lock.py
import getpass
import subprocess
import uuid

import pytest

from doc_ingest import lock


def _fresh_target(lock_test_dir):
    # A unique filename per test run -- an already-locked leftover from a
    # prior run must never collide with this run's fixture.
    return lock_test_dir / f"locked-{uuid.uuid4().hex}.md"


@pytest.mark.allow_subprocess
def test_apply_readonly_lock_denies_a_real_write(lock_test_dir):
    target = _fresh_target(lock_test_dir)
    target.write_text("original content", encoding="utf-8")
    lock.apply_readonly_lock(target)
    with pytest.raises(PermissionError):
        target.write_text("attempted overwrite", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "original content"


@pytest.mark.allow_subprocess
def test_verify_locked_confirms_the_lock_took(lock_test_dir):
    target = _fresh_target(lock_test_dir)
    target.write_text("content", encoding="utf-8")
    lock.apply_readonly_lock(target)
    assert lock.verify_locked(target) is True


@pytest.mark.allow_subprocess
def test_verify_locked_returns_false_for_an_unlocked_file(lock_test_dir):
    target = _fresh_target(lock_test_dir)
    target.write_text("content", encoding="utf-8")
    assert lock.verify_locked(target) is False
    target.unlink()  # never locked -- safe to clean up normally


@pytest.mark.allow_subprocess
def test_apply_readonly_lock_is_a_noop_the_second_time(lock_test_dir):
    # NOT "icacls runs twice successfully" -- once OWNER RIGHTS denies
    # WRITE_DAC, a second icacls /deny call against the same file would
    # itself be denied. Idempotency lives at the call level: verify_locked()
    # short-circuits the second call entirely.
    target = _fresh_target(lock_test_dir)
    target.write_text("content", encoding="utf-8")
    lock.apply_readonly_lock(target)
    lock.apply_readonly_lock(target)  # must not raise
    assert lock.verify_locked(target) is True


@pytest.mark.allow_subprocess
def test_apply_readonly_lock_completes_a_partial_lock_without_raising(lock_test_dir):
    """Simulates the exact state a crash between the two icacls calls in
    apply_readonly_lock leaves behind (spec §4 step 9's resume scenario,
    Task 15): read-only attribute set and the account-level deny applied,
    but the OWNER RIGHTS deny never landed. verify_locked() must report this
    as NOT fully locked, and a subsequent apply_readonly_lock() call must
    complete it -- not raise PermissionError trying to re-run os.chmod on an
    attribute that's already set."""
    import getpass
    import os
    import stat
    import subprocess

    target = _fresh_target(lock_test_dir)
    target.write_text("content", encoding="utf-8")
    os.chmod(target, stat.S_IREAD)
    account = getpass.getuser()
    subprocess.run(
        ["icacls", str(target), "/deny", f"{account}:(WD,WA,WEA,DE,WDAC,WO)"],
        capture_output=True, text=True, check=True,
    )

    assert lock.verify_locked(target) is False  # partially locked, not fully

    lock.apply_readonly_lock(target)  # must not raise

    assert lock.verify_locked(target) is True


@pytest.mark.allow_subprocess
def test_owner_rights_deny_actually_closes_the_self_reset_hole(lock_test_dir):
    # The empirical claim spec §10 makes: the SAME non-elevated account that
    # created and locked the file cannot reset its own deny rule. Proven
    # here by actually attempting the bypass, not by re-reading our own
    # icacls output back.
    target = _fresh_target(lock_test_dir)
    target.write_text("content", encoding="utf-8")
    lock.apply_readonly_lock(target)

    reset_result = subprocess.run(
        ["icacls", str(target), "/reset"], capture_output=True, text=True,
    )
    assert reset_result.returncode != 0
    assert lock.verify_locked(target) is True  # still locked -- the reset did not take


@pytest.mark.allow_subprocess
def test_icacls_output_shows_the_owner_rights_deny_entry(lock_test_dir):
    target = _fresh_target(lock_test_dir)
    target.write_text("content", encoding="utf-8")
    lock.apply_readonly_lock(target)
    result = subprocess.run(["icacls", str(target)], capture_output=True, text=True)
    assert "S-1-3-4" in result.stdout
    assert "DENY" in result.stdout.upper()
```

- [ ] **Step 4: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_lock.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'doc_ingest.lock'`

- [ ] **Step 5: Write `doc_ingest/lock.py`**

```python
"""Two-layer Windows read-only enforcement: an icacls deny-ACE (the real
backstop, spec §10) plus the read-only file attribute (a second signal).
Denies Write/WriteData/WriteAttributes/Delete AND WriteDAC/WriteOwner, on
BOTH the account's own SID and the well-known OWNER RIGHTS SID (S-1-3-4) --
the account-only deny leaves Windows' implicit owner WRITE_DAC grant intact,
which is what would let the same non-elevated account reset its own deny
rule with no elevation. Locking is one-directional and NOT idempotent at the
icacls-call level once fully applied (a fully denied WRITE_DAC means a
second icacls call would itself be denied -- that's the point);
apply_readonly_lock is idempotent at the call level by checking
verify_locked() first."""
from __future__ import annotations

import getpass
import os
import stat
import subprocess
from pathlib import Path

_DENY_RIGHTS = "WD,WA,WEA,DE,WDAC,WO"
_OWNER_RIGHTS_SID = "*S-1-3-4"


def apply_readonly_lock(path: Path) -> None:
    if verify_locked(path):
        return  # already fully locked -- a second icacls call would itself be denied

    # Skip if the read-only ATTRIBUTE bit is already set. os.chmod uses
    # SetFileAttributes under the hood, which needs WriteAttributes
    # regardless of whether the call would actually change anything -- so on
    # the RESUME path (first icacls call already landed, denying WA to the
    # account, but the OWNER RIGHTS call below hasn't run yet), a second
    # unconditional os.chmod call here would itself raise PermissionError,
    # even though there's nothing left for it to do. This is exactly the
    # partial-lock state Task 15's resume_unlocked_conversions calls this
    # function to finish.
    if not (path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY):
        os.chmod(path, stat.S_IREAD)

    # Adding this deny ACE a second time (the resume path) is harmless --
    # icacls appends a redundant entry rather than erroring, and at this
    # point the account still has implicit WRITE_DAC (the OWNER RIGHTS deny
    # below hasn't landed yet), so modifying its own DACL still succeeds.
    account = getpass.getuser()
    subprocess.run(
        ["icacls", str(path), "/deny", f"{account}:({_DENY_RIGHTS})"],
        capture_output=True, text=True, check=True,
    )
    # The entry that actually closes the self-reset hole -- see module
    # docstring. Applied second and separately: if the process dies between
    # this call and the one above, verify_locked() still correctly reports
    # "not yet fully locked" and a later retry (Task 15's
    # resume_unlocked_conversions) can still complete it, because the
    # account-only deny above does not yet block WRITE_DAC on its own.
    subprocess.run(
        ["icacls", str(path), "/deny", f"{_OWNER_RIGHTS_SID}:({_DENY_RIGHTS})"],
        capture_output=True, text=True, check=True,
    )


def verify_locked(path: Path) -> bool:
    if not path.exists():
        return False
    if os.access(path, os.W_OK):
        return False
    result = subprocess.run(["icacls", str(path)], capture_output=True, text=True, check=True)
    output = result.stdout
    # icacls sometimes resolves the well-known OWNER RIGHTS SID to its
    # display name ("OWNER RIGHTS") rather than printing the raw "S-1-3-4"
    # string, depending on Windows version/locale -- match either form, or
    # this would never report True on a build that resolves it, and every
    # job would stall at 'placing' forever.
    has_owner_rights_entry = "S-1-3-4" in output or "OWNER RIGHTS" in output.upper()
    return has_owner_rights_entry and "DENY" in output.upper()
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_lock.py -v
```

Expected: 7 passed. If `test_owner_rights_deny_actually_closes_the_self_reset_hole` fails (i.e. `/reset` succeeds), that means this Windows build doesn't honor a **deny** ACE on the OWNER RIGHTS SID the way this task assumes — Microsoft's own documentation for `S-1-3-4` describes it as a mechanism for *replacing* the implicit owner grant via an **allow** ACE with a restricted right set, not as a target for an explicit deny. If the deny form doesn't hold empirically, the fallback design is `icacls <path> /grant *S-1-3-4:(RX)` (grant OWNER RIGHTS read-and-execute only, which as the *only* OWNER RIGHTS entry replaces the implicit full grant rather than trying to deny on top of it) in place of the second `/deny` call above, with `verify_locked` checking for that grant instead. Re-verify by hand (`icacls <file>` before and after a manual `/reset` attempt) before proceeding to Task 15 either way — this is a real finding requiring a design change, not a test to loosen.

- [ ] **Step 7: Commit**

```bash
git add doc-ingest-app/doc_ingest/lock.py doc-ingest-app/tests/test_lock.py doc-ingest-app/tests/conftest.py .gitignore
git commit -m "feat(doc-ingest): add icacls lock with OWNER RIGHTS deny closing the self-reset hole"
```

---

## Task 14: `drive_client.py` — OAuth, batched metadata, export

**Files:**
- Create: `doc-ingest-app/doc_ingest/drive_client.py`
- Test: `doc-ingest-app/tests/test_drive_client.py`

**Interfaces:**
- Consumes: `google-api-python-client`, `google-auth-oauthlib`.
- Produces: `get_credentials(token_path: Path, client_secret_path: Path) -> Credentials`, `build_batch_metadata(service, doc_ids: list[str], cfg) -> dict[str, dict]` (`doc_id -> {name, modifiedTime, mimeType}`), `export_google_doc(service, doc_id: str, dest_path: Path, cfg) -> ConversionResult`, `export_google_sheet(service, doc_id: str, dest_path: Path, cfg) -> ConversionResult`. Used by `run_ingest_cron.py` (Task 16) and `worker.py` (Task 15). Every test in this task mocks the `service` object — none makes a real Drive call.

**Batching mechanism** (resolves spec §15's open item): `googleapiclient.http.BatchHttpRequest`, Google's documented per-batch cap of 100 requests — `cfg.drive_metadata_batch_size` chunks the ~100 doc_ids accordingly, one `files().get(fileId=..., fields="id,name,modifiedTime,mimeType")` request added per doc_id, executed as one HTTP round trip per batch of up to 100.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_drive_client.py
from unittest.mock import MagicMock, call

import pytest

from doc_ingest.config import Config
from doc_ingest import drive_client


def test_build_batch_metadata_adds_one_request_per_doc_id():
    service = MagicMock()
    batch = MagicMock()
    service.new_batch_http_request.return_value = batch

    def _execute():
        # Simulate the batch callback firing for each added request.
        for request_id, doc_id in enumerate(["doc1", "doc2"]):
            callback = batch.add.call_args_list[request_id].kwargs["callback"]
            callback(str(request_id), {"id": doc_id, "name": f"{doc_id}.gdoc", "modifiedTime": "2026-08-01T00:00:00Z", "mimeType": "application/vnd.google-apps.document"}, None)

    batch.execute.side_effect = _execute
    cfg = Config()
    result = drive_client.build_batch_metadata(service, ["doc1", "doc2"], cfg)
    assert result["doc1"]["modifiedTime"] == "2026-08-01T00:00:00Z"
    assert result["doc2"]["name"] == "doc2.gdoc"
    assert batch.add.call_count == 2

    # Prove the request itself was built with the real fileId/fields, not
    # just that *some* mock call happened -- a MagicMock silently accepts a
    # typo'd kwarg name otherwise, so asserting only call_count wouldn't
    # catch e.g. fields="id,name,modifiedTIme,mimeType".
    get_calls = service.files().get.call_args_list
    called_doc_ids = {c.kwargs["fileId"] for c in get_calls}
    assert called_doc_ids == {"doc1", "doc2"}
    for c in get_calls:
        assert c.kwargs["fields"] == "id,name,modifiedTime,mimeType"

    # BatchHttpRequest invokes BOTH a per-request callback (from .add) AND a
    # batch-level default callback (from new_batch_http_request) for every
    # completed request -- not one-or-the-other. Registering the same
    # callback in both places double-invokes it per doc_id, which is exactly
    # the bug this asserts against.
    _, batch_kwargs = service.new_batch_http_request.call_args
    assert "callback" not in batch_kwargs


def test_build_batch_metadata_chunks_over_the_batch_size_cap():
    service = MagicMock()
    batches_created = []

    def _new_batch(callback=None):
        b = MagicMock()
        b.execute.side_effect = lambda: None
        batches_created.append(b)
        return b

    service.new_batch_http_request.side_effect = _new_batch
    cfg = Config(drive_metadata_batch_size=2)
    drive_client.build_batch_metadata(service, ["a", "b", "c"], cfg)
    assert len(batches_created) == 2  # [a,b], [c]


def test_export_google_doc_writes_markdown(tmp_path):
    service = MagicMock()
    service.files().export.return_value.execute.return_value = b"# Exported markdown\n"
    cfg = Config()
    dest = tmp_path / "out.md"
    result = drive_client.export_google_doc(service, "doc123", dest, cfg)
    assert result.success is True
    assert result.tool == "google-docs-export"
    assert dest.read_bytes() == b"# Exported markdown\n"


def test_export_google_doc_falls_back_to_docx_when_markdown_unavailable(tmp_path):
    service = MagicMock()

    def _export(fileId, mimeType):
        exec_mock = MagicMock()
        if mimeType == "text/markdown":
            exec_mock.execute.side_effect = Exception("format not available")
        else:
            exec_mock.execute.return_value = b"fake docx bytes"
        return exec_mock

    service.files().export.side_effect = _export
    cfg = Config()
    dest = tmp_path / "out.docx"
    result = drive_client.export_google_doc(service, "doc123", dest, cfg)
    assert result.success is True
    assert result.tool == "google-docs-export-docx-fallback"


def test_export_google_sheet_writes_xlsx(tmp_path):
    service = MagicMock()
    service.files().export.return_value.execute.return_value = b"fake xlsx bytes"
    cfg = Config()
    dest = tmp_path / "out.xlsx"
    result = drive_client.export_google_sheet(service, "sheet123", dest, cfg)
    assert result.success is True
    assert dest.read_bytes() == b"fake xlsx bytes"


def test_retry_backs_off_and_succeeds_after_a_transient_error():
    from googleapiclient.errors import HttpError

    attempts = {"count": 0}

    def _flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            response = MagicMock(status=429)
            raise HttpError(response, b"rate limited")
        return "success"

    cfg = Config(drive_retry_max_attempts=5, drive_retry_base_delay_s=0.001)
    result = drive_client._with_retry(_flaky, cfg)
    assert result == "success"
    assert attempts["count"] == 3


def test_retry_gives_up_after_max_attempts():
    from googleapiclient.errors import HttpError

    def _always_fails():
        response = MagicMock(status=500)
        raise HttpError(response, b"server error")

    cfg = Config(drive_retry_max_attempts=2, drive_retry_base_delay_s=0.001)
    with pytest.raises(HttpError):
        drive_client._with_retry(_always_fails, cfg)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_drive_client.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'doc_ingest.drive_client'`

- [ ] **Step 3: Write `doc_ingest/drive_client.py`**

```python
"""OAuth, batched metadata lookups, and Docs/Sheets export. Internal-only
OAuth consent screen (see SETUP.md) -- an External/Testing app's refresh
tokens expire after 7 days, which would silently break the 30-minute cron
about a week after setup (spec §9)."""
from __future__ import annotations

import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

from doc_ingest.convert import ConversionResult

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

_RETRYABLE_STATUSES = {429, 500, 502, 503}


def get_credentials(token_path: Path, client_secret_path: Path) -> Credentials:
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _with_retry(fn, cfg):
    last_error = None
    for attempt in range(cfg.drive_retry_max_attempts):
        try:
            return fn()
        except HttpError as exc:
            status = getattr(exc.resp, "status", None)
            if status not in _RETRYABLE_STATUSES:
                raise
            last_error = exc
            time.sleep(cfg.drive_retry_base_delay_s * (2 ** attempt))
    raise last_error


def build_batch_metadata(service, doc_ids: list[str], cfg) -> dict[str, dict]:
    results: dict[str, dict] = {}

    def _callback(request_id, response, exception):
        if exception is None:
            results[response["id"]] = response

    for start in range(0, len(doc_ids), cfg.drive_metadata_batch_size):
        chunk = doc_ids[start:start + cfg.drive_metadata_batch_size]
        # No callback= here: BatchHttpRequest fires the batch-level default
        # callback AND each request's own callback for every completed
        # request, not one-or-the-other. Registering _callback in both
        # places would invoke it twice per doc_id.
        batch = service.new_batch_http_request()
        for doc_id in chunk:
            batch.add(
                service.files().get(fileId=doc_id, fields="id,name,modifiedTime,mimeType"),
                callback=_callback,
            )
        _with_retry(batch.execute, cfg)

    return results


def export_google_doc(service, doc_id: str, dest_path: Path, cfg) -> ConversionResult:
    # cfg.drive_export_size_cap_bytes is not compared against here on
    # purpose: Drive enforces its own ~10MB export cap server-side and
    # returns an HttpError for a document that exceeds it, which this
    # `except Exception` already catches and routes to the docx fallback --
    # there is no client-visible "export size" to check ahead of the
    # attempt. The config value exists to name and tune the fallback
    # trigger's real-world cause in tests and docs, not to gate a
    # client-side pre-check that Drive doesn't expose the data for.
    try:
        content = _with_retry(
            lambda: service.files().export(fileId=doc_id, mimeType="text/markdown").execute(), cfg,
        )
        dest_path.write_bytes(content)
        return ConversionResult(success=True, markdown_body=content.decode("utf-8"), tool="google-docs-export", error=None)
    except Exception:
        pass  # format unavailable OR the doc exceeded Drive's export size cap -- fall back to docx export below

    content = _with_retry(
        lambda: service.files().export(
            fileId=doc_id, mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ).execute(), cfg,
    )
    dest_path.write_bytes(content)
    return ConversionResult(success=True, markdown_body=None, tool="google-docs-export-docx-fallback", error=None)


def export_google_sheet(service, doc_id: str, dest_path: Path, cfg) -> ConversionResult:
    content = _with_retry(
        lambda: service.files().export(
            fileId=doc_id, mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ).execute(), cfg,
    )
    dest_path.write_bytes(content)
    return ConversionResult(success=True, markdown_body=None, tool="google-sheets-export", error=None)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_drive_client.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/drive_client.py doc-ingest-app/tests/test_drive_client.py
git commit -m "feat(doc-ingest): add Drive OAuth, batched metadata, Docs/Sheets export"
```

---

## Task 15: `worker.py` — process one claimed job end to end

**Files:**
- Create: `doc-ingest-app/doc_ingest/worker.py`
- Test: `doc-ingest-app/tests/test_worker.py`

**Interfaces:**
- Consumes: everything from Tasks 4, 8–14 (`db`, `naming`, `scan.classify`, `metadata_readers`, `convert`, `frontmatter`, `gauntlet`, `lock`, `jobs.heartbeat`).
- Produces: `process_job(conn, job_id: int, cfg, worker_id: str) -> None`. Used by `run_ingest_cron.py` (Task 16). Handles local files only (pdf/docx/xlsx/txt/md/ppt) — Task 22 extends this with the `.gdoc`/`.gsheet` Drive-export branch once `drive_client.py`'s consumer side exists.

Implements spec §4 steps 6–9: stage → convert → gauntlet → **write → commit-as-current → lock → verify**, as an explicit ordered sequence (a filesystem write and an `icacls` subprocess call cannot share a SQLite transaction). A job that dies between the write and the lock-verify is left with `locked_confirmed_at IS NULL` on its `conversions` row; the associated `conversion_jobs` row is left at `'placing'`, **not** `'complete'` — the next wake's `resume_unlocked_conversions` re-attempts only the lock step and flips the job to `'complete'` once it lands, never a full reconversion.

**TXT/MD bypass `convert.py` entirely.** firecrawl's supported format list is PDF/DOCX/DOC/ODT/RTF/XLSX/XLS/HTML — TXT and MD aren't in it, and spec §2/§8 call for a verbatim pass-through with frontmatter added, not a parse. `_convert` below branches before ever calling `convert.convert_local_file` for those two types, reading the staged file directly.

**Extensionless files derive `source_type` from `sniffed_signature`, not `extension`.** The 6 real PDFs among this corpus's 19 extensionless files (spec §2) have `extension == ""` — deriving `source_type` from extension alone raises `KeyError` on every one of them, exactly the files sniffing exists to correctly include.

**Locking is mocked in this task's own tests.** `lock.py` (Task 13) is deliberately non-idempotent once fully applied and its tests use a dedicated non-`tmp_path` scratch directory for that reason — this task's tests patch `lock.apply_readonly_lock`/`lock.verify_locked` to verify the *orchestration* (right path passed, `locked_confirmed_at` recorded correctly), leaving the real OS-level guarantee to Task 13's own tests and Task 21's dedicated real-enforcement test.

**A real heartbeat thread runs for the life of the job.** `jobs.heartbeat` (Task 7) exists specifically so `reclaim_stale_jobs` can tell a live worker from a dead one — but a `heartbeat_at` that's only ever stamped once, at claim time, goes stale the moment a real conversion takes longer than `cfg.reclaim_staleness_threshold_s` (180s default), and `reclaim_stale_jobs` would then reset a job that's still genuinely running, out from under its own worker. `process_job` starts a heartbeat thread on its **own** SQLite connection (never sharing `conn` across threads, spec §5 — mirrors `pipeline_app.discovery_engine`'s heartbeat-thread precedent) immediately after marking the job `'converting'`, and stops it in a `finally` block that covers every return path.

**Not yet using `naming.long_path`.** The final-file write below uses plain `final_path.write_text`. Task 22's full rewrite of this module switches that one call to `naming.long_path`-prefixed `open()` (spec §6's defense-in-depth for the residual long-path case, Task 4) — mentioned here so this version isn't mistaken for the final word on it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_worker.py
from unittest.mock import patch

import pytest

from doc_ingest.config import Config
from doc_ingest import jobs, sync, worker


def _seed_pending_job(conn, tmp_input_root, rel_path="Folder/Notes.txt", content=b"hello world this is real text"):
    (tmp_input_root / "Folder").mkdir(parents=True, exist_ok=True)
    (tmp_input_root / rel_path).write_bytes(content)
    sync.sync_source_files(conn, tmp_input_root)
    jobs.enqueue_pending_jobs(conn)
    return jobs.claim_job(conn, worker_id="w1")


def test_process_job_happy_path_writes_commits_locks_and_indexes(conn, tmp_path):
    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root)
    job_id = _seed_pending_job(conn, input_root)

    with patch("doc_ingest.lock.apply_readonly_lock") as mock_lock, \
         patch("doc_ingest.lock.verify_locked", return_value=True):
        worker.process_job(conn, job_id, cfg, worker_id="w1")

    job_row = conn.execute("SELECT status FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row[0] == "complete"

    conversion = conn.execute(
        "SELECT status, locked_confirmed_at, output_path, conversion_tool FROM conversions WHERE job_id = ?", (job_id,)
    ).fetchone()
    assert conversion[0] == "current"
    assert conversion[1] is not None
    assert conversion[3] == "passthrough"  # .txt bypasses firecrawl entirely

    output_file = output_root / "converted" / conversion[2]
    assert output_file.exists()
    assert "hello world" in output_file.read_text(encoding="utf-8")
    mock_lock.assert_called_once_with(output_file)

    fts_row = conn.execute(
        "SELECT body FROM conversions_fts WHERE conversions_fts MATCH 'hello'"
    ).fetchone()
    assert fts_row is not None


def test_process_job_handles_an_extensionless_pdf_via_sniffed_signature(conn, tmp_path):
    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root)
    job_id = _seed_pending_job(conn, input_root, rel_path="Folder/report", content=b"%PDF-1.4 fake pdf bytes")

    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_client.parse.return_value = MagicMock(markdown="# Parsed from a sniffed PDF\n\nreal words here")
    with patch("firecrawl.Firecrawl", return_value=mock_client), \
         patch("doc_ingest.metadata_readers.read_pdf_page_count", return_value=1), \
         patch("doc_ingest.lock.apply_readonly_lock"), \
         patch("doc_ingest.lock.verify_locked", return_value=True):
        worker.process_job(conn, job_id, cfg, worker_id="w1")

    job_row = conn.execute("SELECT status, failure_reason FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row[0] == "complete", job_row[1]
    conversion = conn.execute("SELECT source_type FROM conversions WHERE job_id = ?", (job_id,)).fetchone()
    assert conversion[0] == "pdf"


def test_process_job_marks_failed_on_gauntlet_rejection(conn, tmp_path):
    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root, size_ratio_floor=0.9)
    job_id = _seed_pending_job(conn, input_root, content=b"a source file with plenty of real bytes in it, much more than the tiny converted output below")

    def _fake_convert(staged_path, source_type, cfg_arg):
        from doc_ingest.convert import ConversionResult
        return ConversionResult(success=True, markdown_body="x", tool="firecrawl-parse", error=None)

    with patch("doc_ingest.worker._convert", side_effect=_fake_convert), \
         patch("doc_ingest.lock.apply_readonly_lock"), \
         patch("doc_ingest.lock.verify_locked", return_value=True):
        worker.process_job(conn, job_id, cfg, worker_id="w1")

    job_row = conn.execute("SELECT status, failure_reason FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row[0] == "failed"
    assert job_row[1] == "below_size_ratio_floor"
    assert not (output_root / "converted").exists() or not any((output_root / "converted").rglob("*.md"))


def test_process_job_supersedes_the_prior_current_version(conn, tmp_path):
    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root)

    with patch("doc_ingest.lock.apply_readonly_lock"), patch("doc_ingest.lock.verify_locked", return_value=True):
        job_id_1 = _seed_pending_job(conn, input_root, content=b"version one text content")
        worker.process_job(conn, job_id_1, cfg, worker_id="w1")

        (input_root / "Folder" / "Notes.txt").write_bytes(b"version two, different text content entirely")
        sync.sync_source_files(conn, input_root)
        jobs.enqueue_pending_jobs(conn)
        job_id_2 = jobs.claim_job(conn, worker_id="w1")
        worker.process_job(conn, job_id_2, cfg, worker_id="w1")

    statuses = conn.execute(
        "SELECT version_number, status FROM conversions ORDER BY version_number"
    ).fetchall()
    assert statuses == [(1, "superseded"), (2, "current")]


def test_process_job_leaves_the_job_at_placing_when_lock_confirmation_fails(conn, tmp_path):
    """verify_locked() returning False (no exception -- icacls "succeeded"
    but the read-back didn't confirm it) must NOT mark the job complete,
    per spec §4 step 9: a conversion with locked_confirmed_at unset is not
    done yet, whether or not an exception was involved."""
    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root)
    job_id = _seed_pending_job(conn, input_root)

    with patch("doc_ingest.lock.apply_readonly_lock"), patch("doc_ingest.lock.verify_locked", return_value=False):
        worker.process_job(conn, job_id, cfg, worker_id="w1")

    job_row = conn.execute("SELECT status FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row[0] == "placing"
    conversion = conn.execute("SELECT locked_confirmed_at FROM conversions WHERE job_id = ?", (job_id,)).fetchone()
    assert conversion[0] is None


def test_process_job_resumes_lock_only_after_a_simulated_crash(conn, tmp_path):
    """A job whose .md was written and committed as 'current' but never
    confirmed locked (process died between step 9(b) and 9(d)) must be
    re-locked on the next pass, not re-converted -- and the job itself must
    move to 'complete' only once resume actually succeeds."""
    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root)
    job_id = _seed_pending_job(conn, input_root)

    with patch("doc_ingest.lock.apply_readonly_lock", side_effect=RuntimeError("simulated crash")):
        with pytest.raises(RuntimeError):
            worker.process_job(conn, job_id, cfg, worker_id="w1")

    conversion = conn.execute(
        "SELECT status, locked_confirmed_at, output_path FROM conversions WHERE job_id = ?", (job_id,)
    ).fetchone()
    assert conversion[0] == "current"
    assert conversion[1] is None  # written, not yet confirmed locked
    job_row = conn.execute("SELECT status FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row[0] == "placing"  # NOT complete -- the lock never confirmed
    output_file = output_root / "converted" / conversion[2]
    assert output_file.exists()  # the write already happened

    with patch("doc_ingest.lock.apply_readonly_lock"), patch("doc_ingest.lock.verify_locked", return_value=True):
        worker.resume_unlocked_conversions(conn, cfg)

    conversion_after = conn.execute(
        "SELECT locked_confirmed_at FROM conversions WHERE job_id = ?", (job_id,)
    ).fetchone()
    assert conversion_after[0] is not None
    job_row_after = conn.execute("SELECT status FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row_after[0] == "complete"


def test_process_job_updates_heartbeat_while_converting(conn, tmp_path):
    """Without a running heartbeat thread, heartbeat_at is stamped once at
    claim time and never again -- a slow real conversion would eventually
    look stale to reclaim_stale_jobs (Task 7) and get reclaimed out from
    under its own still-running worker. A short interval keeps this test
    fast (~0.15s) and non-flaky rather than waiting through the real
    30-second default."""
    import time

    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root, reclaim_heartbeat_interval_s=0.02)
    job_id = _seed_pending_job(conn, input_root)

    claimed_heartbeat = conn.execute(
        "SELECT heartbeat_at FROM conversion_jobs WHERE id = ?", (job_id,)
    ).fetchone()[0]

    observed = {}
    real_convert = worker._convert

    def _slow_convert(staged_path, source_type, cfg_arg):
        time.sleep(0.15)  # several heartbeat ticks at the 0.02s interval above
        observed["mid_run"] = conn.execute(
            "SELECT heartbeat_at FROM conversion_jobs WHERE id = ?", (job_id,)
        ).fetchone()[0]
        return real_convert(staged_path, source_type, cfg_arg)

    with patch("doc_ingest.worker._convert", side_effect=_slow_convert), \
         patch("doc_ingest.lock.apply_readonly_lock"), \
         patch("doc_ingest.lock.verify_locked", return_value=True):
        worker.process_job(conn, job_id, cfg, worker_id="w1")

    assert observed["mid_run"] is not None
    assert observed["mid_run"] > claimed_heartbeat  # a heartbeat tick landed on the heartbeat thread's own connection during the slow step
    job_row = conn.execute("SELECT status FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row[0] == "complete"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_worker.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'doc_ingest.worker'`

- [ ] **Step 3: Write `doc_ingest/worker.py`**

```python
"""Orchestrates one claimed job end to end (spec §4 steps 6-9): stage,
convert, gauntlet, then an explicit write -> commit-as-current -> lock ->
verify sequence -- not one atomic operation, because a filesystem write and
an icacls subprocess call cannot share a SQLite transaction. A job that dies
-- or whose lock simply doesn't confirm -- between the write and the lock-
verify is left with locked_confirmed_at NULL and its conversion_jobs row at
'placing', not 'complete'; resume_unlocked_conversions re-attempts only the
lock and flips the job to 'complete' once it lands, never a reconversion.

A heartbeat thread runs on its own connection for the life of the job (spec
§5: never share conn across threads) so reclaim_stale_jobs (Task 7) can tell
a live worker from a dead one even when the actual conversion step takes
longer than the reclaim staleness threshold."""
from __future__ import annotations

import datetime as dt
import shutil
import threading
from pathlib import Path

from doc_ingest import convert, db, frontmatter, gauntlet, jobs, lock, metadata_readers

_LOCAL_EXTENSIONS = {"pdf": "pdf", "docx": "docx", "xlsx": "xlsx", "txt": "txt", "md": "md", "ppt": "ppt"}


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _db_path_of(conn) -> Path:
    """The heartbeat thread needs its own connection (spec §5) but
    process_job only receives an already-open one -- PRAGMA database_list's
    third column is the file path SQLite actually resolved from the
    connection string, which is how the heartbeat thread gets there without
    process_job's signature needing a separate db_path parameter."""
    row = conn.execute("PRAGMA database_list").fetchone()
    return Path(row[2])


def _run_heartbeat_loop(db_path: Path, job_id: int, worker_id: str, interval_s: float, stop_event: threading.Event) -> None:
    heartbeat_conn = db.get_connection(db_path)
    try:
        while not stop_event.wait(interval_s):
            try:
                jobs.heartbeat(heartbeat_conn, job_id, worker_id)
            except Exception:
                pass  # best-effort -- a missed tick risks an earlier reclaim, not a crash
    finally:
        heartbeat_conn.close()


def _source_type_for(extension: str, sniffed_signature: str | None) -> str:
    if extension:
        return _LOCAL_EXTENSIONS[extension]
    if sniffed_signature == "pdf":
        return "pdf"
    raise ValueError(f"cannot determine source_type for an extensionless file (sniffed_signature={sniffed_signature!r})")


def _convert(staged_path, source_type: str, cfg):
    """TXT/MD bypass firecrawl entirely -- it's not in firecrawl's supported
    format list, and spec §2/§8 call for a verbatim pass-through with
    frontmatter added, not a parse."""
    if source_type in ("txt", "md"):
        try:
            body = staged_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            return convert.ConversionResult(success=False, markdown_body=None, tool="passthrough", error=f"invalid_utf8: {exc}")
        return convert.ConversionResult(success=True, markdown_body=body, tool="passthrough", error=None)
    return convert.convert_local_file(staged_path, source_type, cfg)


def _independent_metadata(staged_path, source_type: str) -> dict:
    """SOURCE-side values only, read independently of firecrawl's own
    output -- Gate 1 (Task 11) computes every OUTPUT-side count itself from
    the assembled markdown."""
    if source_type == "pdf":
        return {"page_count": metadata_readers.read_pdf_page_count(staged_path)}
    if source_type == "docx":
        return {
            "source_word_count": metadata_readers.read_docx_word_count(staged_path),
            "source_table_count": metadata_readers.read_docx_table_count(staged_path),
        }
    if source_type == "xlsx":
        sheet_count, row_count = metadata_readers.read_xlsx_sheet_and_row_counts(staged_path)
        return {"source_sheet_count": sheet_count, "source_row_count": row_count}
    return {}


def _frontmatter_extras(independent_metadata: dict) -> dict:
    """Maps this module's internal source_*-prefixed metadata keys onto the
    exact field names spec §7 sanctions in frontmatter (page_count,
    word_count, sheet_count, row_count_total) -- source_table_count is
    gauntlet-only and deliberately excluded, since table_count isn't a
    frontmatter field spec §7 lists."""
    extras = {}
    if "page_count" in independent_metadata:
        extras["page_count"] = independent_metadata["page_count"]
    if "source_word_count" in independent_metadata:
        extras["word_count"] = independent_metadata["source_word_count"]
    if "source_sheet_count" in independent_metadata:
        extras["sheet_count"] = independent_metadata["source_sheet_count"]
    if "source_row_count" in independent_metadata:
        extras["row_count_total"] = independent_metadata["source_row_count"]
    return extras


def _fail_job(conn, job_id: int, reason: str) -> None:
    with db.transaction(conn):
        conn.execute(
            "UPDATE conversion_jobs SET status = 'failed', failure_reason = ?, finished_at = ? WHERE id = ?",
            (reason, _now_iso(), job_id),
        )


def process_job(conn, job_id: int, cfg, worker_id: str) -> None:
    job = conn.execute(
        "SELECT source_file_id FROM conversion_jobs WHERE id = ?", (job_id,)
    ).fetchone()
    source_file_id = job[0]
    source = conn.execute(
        "SELECT rel_path, extension, size_bytes, sniffed_signature, mtime, content_hash "
        "FROM source_files WHERE id = ?", (source_file_id,)
    ).fetchone()
    rel_path, extension, size_bytes, sniffed_signature, source_mtime, source_hash = source
    source_type = _source_type_for(extension, sniffed_signature)

    tmp_dir = cfg.tmp_root / f"job-{job_id}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with db.transaction(conn):
        conn.execute(
            "UPDATE conversion_jobs SET status = 'converting', tmp_dir = ? WHERE id = ?",
            (str(tmp_dir), job_id),
        )

    stop_heartbeat = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_run_heartbeat_loop,
        args=(_db_path_of(conn), job_id, worker_id, cfg.reclaim_heartbeat_interval_s, stop_heartbeat),
        daemon=True,
    )
    heartbeat_thread.start()
    try:
        staged_path = tmp_dir / rel_path.rsplit("/", 1)[-1]
        shutil.copy2(cfg.input_root / rel_path, staged_path)

        conversion_result = _convert(staged_path, source_type, cfg)
        if not conversion_result.success:
            _fail_job(conn, job_id, conversion_result.error)
            return

        independent_metadata = _independent_metadata(staged_path, source_type)

        prior_version = conn.execute(
            "SELECT MAX(version_number) FROM conversions WHERE source_file_id = ?", (source_file_id,)
        ).fetchone()[0]
        version = (prior_version or 0) + 1

        gate2_result, dest_rel_path = gauntlet.run_gate2(conn, rel_path, source_file_id, version, cfg)
        if not gate2_result.passed:
            _fail_job(conn, job_id, gate2_result.failure_reason)
            return

        frontmatter_extras = _frontmatter_extras(independent_metadata)
        base_fm = {
            "source_path": rel_path, "source_type": source_type, "source_hash": source_hash,
            "source_modified_at": source_mtime, "converted_at": _now_iso(),
            "conversion_tool": conversion_result.tool, "version": version, "status": "current",
            "business_line": "freedom2beu", "gauntlet_passed_at": _now_iso(),
        }
        fm = frontmatter.build_frontmatter(base_fm, frontmatter_extras)
        assembled = frontmatter.serialize(fm, conversion_result.markdown_body)

        gate1_result = gauntlet.run_gate1(source_type, size_bytes or 0, assembled, independent_metadata, cfg)
        if not gate1_result.passed:
            _fail_job(conn, job_id, gate1_result.failure_reason)
            return

        # --- 9(a): write the final file ---
        final_path = cfg.converted_root / dest_rel_path
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_text(assembled, encoding="utf-8")

        # --- 9(b): commit the DB row as current + FTS, one transaction ---
        with db.transaction(conn):
            conn.execute(
                "UPDATE conversions SET status = 'superseded' WHERE source_file_id = ? AND status = 'current'",
                (source_file_id,),
            )
            conn.execute(
                """
                INSERT INTO conversions
                    (source_file_id, job_id, version_number, output_path, status, source_type,
                     source_hash_at_conversion, conversion_tool, converted_at, gauntlet_passed_at,
                     page_count, word_count, sheet_count, row_count_total)
                VALUES (?, ?, ?, ?, 'current', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_file_id, job_id, version, dest_rel_path, source_type,
                    source_hash, conversion_result.tool, _now_iso(), _now_iso(),
                    frontmatter_extras.get("page_count"),
                    frontmatter_extras.get("word_count"),
                    frontmatter_extras.get("sheet_count"),
                    frontmatter_extras.get("row_count_total"),
                ),
            )
            conversion_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO conversions_fts (conversion_id, source_rel_path, output_path, body) VALUES (?, ?, ?, ?)",
                (conversion_id, rel_path, dest_rel_path, assembled),
            )
            conn.execute(
                "UPDATE conversion_jobs SET status = 'placing' WHERE id = ?", (job_id,),
            )

        # --- 9(c)/(d): lock and verify -- may raise; a caller-visible crash
        # here, or a False from verify_locked with no exception at all, both
        # leave the job at 'placing' rather than 'complete' --
        # resume_unlocked_conversions is what advances it from here.
        lock.apply_readonly_lock(final_path)
        confirmed = lock.verify_locked(final_path)

        with db.transaction(conn):
            if confirmed:
                conn.execute(
                    "UPDATE conversions SET locked_confirmed_at = ? WHERE id = ?", (_now_iso(), conversion_id),
                )
                conn.execute(
                    "UPDATE conversion_jobs SET status = 'complete', finished_at = ? WHERE id = ?",
                    (_now_iso(), job_id),
                )
            # else: leave status = 'placing'. reclaim_stale_jobs (Task 7)
            # already knows not to reset a 'placing' job back to 'pending'
            # once its conversion has landed -- only
            # resume_unlocked_conversions advances it further from here.
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=5)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def resume_unlocked_conversions(conn, cfg) -> list[int]:
    """Re-attempts lock+verify for any 'current' conversion whose write
    completed but whose lock was never confirmed -- never reconverts. Also
    advances the associated conversion_jobs row to 'complete' once the lock
    actually lands, since process_job deliberately left it at 'placing'."""
    rows = conn.execute(
        "SELECT id, output_path, job_id FROM conversions WHERE status = 'current' AND locked_confirmed_at IS NULL"
    ).fetchall()
    resumed = []
    for conversion_id, output_path, job_id in rows:
        final_path = cfg.converted_root / output_path
        if not final_path.exists():
            continue
        lock.apply_readonly_lock(final_path)
        if lock.verify_locked(final_path):
            now = dt.datetime.now(dt.timezone.utc).isoformat()
            with db.transaction(conn):
                conn.execute(
                    "UPDATE conversions SET locked_confirmed_at = ? WHERE id = ?", (now, conversion_id),
                )
                if job_id is not None:
                    conn.execute(
                        "UPDATE conversion_jobs SET status = 'complete', finished_at = ? "
                        "WHERE id = ? AND status != 'complete'",
                        (now, job_id),
                    )
            resumed.append(conversion_id)
    return resumed
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_worker.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/doc_ingest/worker.py doc-ingest-app/tests/test_worker.py
git commit -m "feat(doc-ingest): add end-to-end job worker with crash-safe lock resume"
```

---

## Task 16: `scripts/run_ingest_cron.py` — the cron entry point

**Files:**
- Create: `doc-ingest-app/scripts/run_ingest_cron.py`
- Test: `doc-ingest-app/tests/test_run_ingest_cron.py`

**Interfaces:**
- Consumes: `db.init_db`, `jobs.reclaim_stale_jobs`/`enqueue_pending_jobs`/`claim_job`/`heartbeat`, `sync.sync_source_files`, `worker.process_job`/`resume_unlocked_conversions`, `config.load_config`.
- Produces: a standalone CLI, invoked by Task Scheduler (Task 17), mirroring `pipeline-app/run_discovery_cron.py`'s "always a subprocess, never imported into a running web process" convention (this app has no web process at all, so that distinction is moot here, but the standalone-subprocess shape is kept for consistency).

Drives spec §4's full flow each wake: reclaim → resume-unlocked → scan/sync → Drive check → enqueue → drain with a bounded worker pool, respecting `cfg.run_time_budget_s` (stop claiming new jobs once the budget elapses; finish whatever's already claimed; exit cleanly). Workers run in a `ThreadPoolExecutor` since this is I/O-bound work (spec §5) — each thread opens its own connection via `db.get_connection`, never sharing the main connection.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_run_ingest_cron.py
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]


def test_module_exposes_a_main_function():
    sys.path.insert(0, str(HERE / "scripts"))
    import run_ingest_cron
    assert callable(run_ingest_cron.main)


def test_run_once_reclaims_scans_enqueues_and_drains(tmp_path, monkeypatch):
    sys.path.insert(0, str(HERE / "scripts"))
    import importlib
    import run_ingest_cron
    importlib.reload(run_ingest_cron)

    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "a.txt").write_bytes(b"some real text content for the doc")
    output_root = tmp_path / "output"
    db_path = tmp_path / "doc_ingest.db"

    from doc_ingest.config import Config
    cfg = Config(input_root=input_root, output_root=output_root, worker_pool_size=1)

    calls = {"process_job": 0}
    real_process_job = run_ingest_cron.worker.process_job

    def _counting_process_job(conn, job_id, cfg_arg, worker_id):
        calls["process_job"] += 1
        return real_process_job(conn, job_id, cfg_arg, worker_id)

    monkeypatch.setattr(run_ingest_cron.worker, "process_job", _counting_process_job)
    run_ingest_cron.run_once(db_path, cfg)
    assert calls["process_job"] == 1


def test_run_once_respects_the_time_budget(tmp_path, monkeypatch):
    sys.path.insert(0, str(HERE / "scripts"))
    import importlib
    import run_ingest_cron
    importlib.reload(run_ingest_cron)

    input_root = tmp_path / "input"
    input_root.mkdir()
    for i in range(5):
        (input_root / f"f{i}.txt").write_bytes(b"content " * 20)
    output_root = tmp_path / "output"
    db_path = tmp_path / "doc_ingest.db"

    from doc_ingest.config import Config
    cfg = Config(input_root=input_root, output_root=output_root, worker_pool_size=1, run_time_budget_s=0)

    calls = {"count": 0}

    def _fake_process_job(conn, job_id, cfg_arg, worker_id):
        calls["count"] += 1

    monkeypatch.setattr(run_ingest_cron.worker, "process_job", _fake_process_job)
    run_ingest_cron.run_once(db_path, cfg)
    assert calls["count"] == 0  # budget already elapsed -- nothing claimed
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_run_ingest_cron.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'run_ingest_cron'`

- [ ] **Step 3: Write `scripts/run_ingest_cron.py`**

```python
"""Standalone CLI entry point for doc-ingest-app, invoked by Windows Task
Scheduler every 30 minutes (scripts/setup_ingest_task.py) or by hand for a
manual run. Mirrors pipeline-app/run_discovery_cron.py's shape.

Usage:
  python scripts/run_ingest_cron.py
  python scripts/run_ingest_cron.py --config path/to/config.yaml
"""
from __future__ import annotations

import argparse
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from doc_ingest import db, jobs, sync, worker
from doc_ingest.config import load_config


def _run_one_worker(db_path: Path, cfg) -> None:
    conn = db.get_connection(db_path)
    try:
        worker_id = f"{uuid.uuid4()}"
        job_id = jobs.claim_job(conn, worker_id)
        if job_id is None:
            return
        try:
            worker.process_job(conn, job_id, cfg, worker_id)
        except Exception as exc:
            print(f"job {job_id} raised: {exc}", file=sys.stderr)
    finally:
        conn.close()


def run_once(db_path: Path, cfg) -> None:
    conn = db.init_db(db_path)
    try:
        reclaimed = jobs.reclaim_stale_jobs(conn, cfg, cfg.tmp_root)
        if reclaimed:
            print(f"reclaimed {len(reclaimed)} stale job(s)")

        resumed = worker.resume_unlocked_conversions(conn, cfg)
        if resumed:
            print(f"resumed lock-verify for {len(resumed)} conversion(s)")

        counts = sync.sync_source_files(conn, cfg.input_root)
        print(f"scan: {counts}")

        created = jobs.enqueue_pending_jobs(conn)
        print(f"enqueued {created} job(s)")
    finally:
        conn.close()

    deadline = time.monotonic() + cfg.run_time_budget_s
    with ThreadPoolExecutor(max_workers=cfg.worker_pool_size) as pool:
        while time.monotonic() < deadline:
            probe_conn = db.get_connection(db_path)
            pending_exists = probe_conn.execute(
                "SELECT 1 FROM conversion_jobs WHERE status = 'pending' LIMIT 1"
            ).fetchone()
            probe_conn.close()
            if not pending_exists:
                break
            futures = [pool.submit(_run_one_worker, db_path, cfg) for _ in range(cfg.worker_pool_size)]
            for future in futures:
                future.result()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None, help="path to a YAML config overriding defaults")
    args = ap.parse_args(argv)

    cfg = load_config(Path(args.config) if args.config else None)
    db_path = HERE.parent / "doc_ingest.db"
    run_once(db_path, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_run_ingest_cron.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/scripts/run_ingest_cron.py doc-ingest-app/tests/test_run_ingest_cron.py
git commit -m "feat(doc-ingest): add the cron entry point -- reclaim, scan, enqueue, drain"
```

---

## Task 17: `scripts/setup_ingest_task.py` — Task Scheduler registration

**Files:**
- Create: `doc-ingest-app/scripts/setup_ingest_task.py`
- Test: `doc-ingest-app/tests/test_setup_ingest_task.py`

**Interfaces:**
- Mirrors `pipeline-app/scripts/setup_discovery_task.py` exactly, at a 30-minute fixed interval and a different task name.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_setup_ingest_task.py
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))

from setup_ingest_task import TASK_NAME, build_schtasks_command


def test_task_name():
    assert TASK_NAME == "ContentStudio-DocIngest"


def test_build_schtasks_command_uses_30_minute_interval():
    cmd = build_schtasks_command(Path("python.exe"), Path("run_ingest_cron.py"))
    assert cmd[:4] == ["schtasks", "/Create", "/TN", "ContentStudio-DocIngest"]
    assert "/SC" in cmd
    assert cmd[cmd.index("/SC") + 1] == "MINUTE"
    assert cmd[cmd.index("/MO") + 1] == "30"


def test_build_schtasks_command_quotes_the_python_invocation():
    cmd = build_schtasks_command(Path("C:/some path/python.exe"), Path("C:/repo/run_ingest_cron.py"))
    tr_index = cmd.index("/TR")
    assert "some path" in cmd[tr_index + 1]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_setup_ingest_task.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'setup_ingest_task'`

- [ ] **Step 3: Write `scripts/setup_ingest_task.py`**

```python
"""One-time registration of the ContentStudio-DocIngest Windows Task
Scheduler task. Registers a fixed 30-minute trigger -- the user's stated
floor (spec §11); no "is it due" gating on top, unlike the discovery cron,
since there's no daily-once semantic here. Mirrors
pipeline-app/scripts/setup_discovery_task.py exactly.

Usage:
  python scripts/setup_ingest_task.py            # dry run: prints the command
  python scripts/setup_ingest_task.py --apply     # actually registers the task
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TASK_NAME = "ContentStudio-DocIngest"


def build_schtasks_command(python_exe: Path, cron_script: Path) -> list[str]:
    task_command = f'"{python_exe}" "{cron_script}"'
    return [
        "schtasks", "/Create", "/TN", TASK_NAME,
        "/TR", task_command, "/SC", "MINUTE", "/MO", "30", "/F",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually register the task (default: dry run / print only)")
    args = ap.parse_args(argv)

    app_root = Path(__file__).resolve().parents[1]
    python_exe = Path(sys.executable)
    cron_script = app_root / "scripts" / "run_ingest_cron.py"
    cmd = build_schtasks_command(python_exe, cron_script)

    if not args.apply:
        print("Dry run -- this is the command that would register the scheduled task:")
        print(" ".join(cmd))
        print("\nRe-run with --apply to actually register it.")
        return 0

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode
    print(f"Registered task '{TASK_NAME}': fires every 30 minutes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_setup_ingest_task.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/scripts/setup_ingest_task.py doc-ingest-app/tests/test_setup_ingest_task.py
git commit -m "feat(doc-ingest): register the 30-minute ContentStudio-DocIngest task"
```

---

## Task 18: `query.py` CLI + `manifest.py` regeneration

**Files:**
- Create: `doc-ingest-app/doc_ingest/query.py`
- Create: `doc-ingest-app/doc_ingest/manifest.py`
- Test: `doc-ingest-app/tests/test_query.py`
- Test: `doc-ingest-app/tests/test_manifest.py`

**Interfaces:**
- `query.search(conn, text: str | None, source_type: str | None, status: str, limit: int) -> list[dict]`, `query.main(argv) -> int` (CLI).
- `manifest.regenerate(conn, output_root: Path) -> tuple[Path, Path]` — writes `_freedom2beu-content-index.csv`/`.md`, mirroring `output/brand-intel/youtube/_youtube-content-index.csv/.md`'s pattern already in this repo.

Both are the "ease of future use" delivery for this phase — no UI, per spec §12.

**`missing`-sourced results, per spec §9a**: a `source_files` row a scan no longer finds is marked `classification = 'missing'`, not deleted, and its already-converted `.md` stays locked and indexed. The default `status="current"` query excludes these (same as `superseded`) and marks any result it does return with `source_missing: bool`; `status="all"` includes them.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_query.py
from doc_ingest import query


def _seed(conn):
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
        "VALUES ('a.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
    )
    source_id = conn.execute("SELECT id FROM source_files WHERE rel_path = 'a.pdf'").fetchone()[0]
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "conversion_tool, converted_at) VALUES (?, 1, 'a.pdf.md', 'current', 'pdf', 'firecrawl-parse', ?)",
        (source_id, now),
    )
    conversion_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO conversions_fts (conversion_id, source_rel_path, output_path, body) "
        "VALUES (?, 'a.pdf', 'a.pdf.md', 'coaching session about goal setting')",
        (conversion_id,),
    )
    conn.commit()


def test_search_matches_body_text(conn):
    _seed(conn)
    results = query.search(conn, text="goal setting", source_type=None, status="current", limit=10)
    assert len(results) == 1
    assert results[0]["output_path"] == "a.pdf.md"


def test_search_filters_by_source_type(conn):
    _seed(conn)
    results = query.search(conn, text=None, source_type="docx", status="current", limit=10)
    assert results == []


def test_search_excludes_superseded_by_default(conn):
    _seed(conn)
    conn.execute("UPDATE conversions SET status = 'superseded'")
    conn.commit()
    results = query.search(conn, text=None, source_type=None, status="current", limit=10)
    assert results == []
    all_results = query.search(conn, text=None, source_type=None, status="all", limit=10)
    assert len(all_results) == 1


def test_search_excludes_missing_sourced_results_by_default(conn):
    _seed(conn)
    conn.execute("UPDATE source_files SET classification = 'missing' WHERE rel_path = 'a.pdf'")
    conn.commit()
    results = query.search(conn, text=None, source_type=None, status="current", limit=10)
    assert results == []
    all_results = query.search(conn, text=None, source_type=None, status="all", limit=10)
    assert len(all_results) == 1
    assert all_results[0]["source_missing"] is True


def test_search_marks_a_present_source_as_not_missing(conn):
    _seed(conn)
    results = query.search(conn, text=None, source_type=None, status="current", limit=10)
    assert results[0]["source_missing"] is False
```

```python
# tests/test_manifest.py
from doc_ingest import manifest


def _seed(conn):
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, first_seen_at, last_seen_at) "
        "VALUES ('a.pdf', 'pdf', 'convertible', ?, ?)", (now, now),
    )
    source_id = conn.execute("SELECT id FROM source_files WHERE rel_path = 'a.pdf'").fetchone()[0]
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "conversion_tool, converted_at) VALUES (?, 1, 'a.pdf.md', 'current', 'pdf', 'firecrawl-parse', ?)",
        (source_id, now),
    )
    conn.commit()


def test_regenerate_writes_csv_and_md(conn, tmp_path):
    _seed(conn)
    csv_path, md_path = manifest.regenerate(conn, tmp_path)
    assert csv_path.exists()
    assert md_path.exists()
    assert "a.pdf.md" in csv_path.read_text(encoding="utf-8")
    assert "a.pdf.md" in md_path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_query.py tests/test_manifest.py -v
```

Expected: FAIL with `ModuleNotFoundError` for both

- [ ] **Step 3: Write `doc_ingest/query.py`**

```python
"""CLI query over the FTS5 index -- the entirety of "ease of future use" for
this phase (spec §12). No UI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def search(conn, text: str | None, source_type: str | None, status: str, limit: int) -> list[dict]:
    clauses = []
    params: list = []

    if text:
        base = (
            "SELECT c.output_path, c.source_type, c.status, sf.rel_path, c.converted_at, sf.classification "
            "FROM conversions_fts f JOIN conversions c ON c.id = f.conversion_id "
            "JOIN source_files sf ON sf.id = c.source_file_id "
            "WHERE f MATCH ?"
        )
        params.append(text)
    else:
        base = (
            "SELECT c.output_path, c.source_type, c.status, sf.rel_path, c.converted_at, sf.classification "
            "FROM conversions c JOIN source_files sf ON sf.id = c.source_file_id WHERE 1=1"
        )

    if status != "all":
        clauses.append("c.status = ?")
        params.append(status)
        # 'missing'-sourced results are excluded by default, same as
        # 'superseded' -- a search shouldn't surface content whose source no
        # longer exists without saying so (spec §9a).
        clauses.append("sf.classification != 'missing'")
    if source_type:
        clauses.append("c.source_type = ?")
        params.append(source_type)

    query_sql = base + ("".join(f" AND {c}" for c in clauses)) + " ORDER BY c.converted_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query_sql, params).fetchall()
    return [
        {
            "output_path": r[0], "source_type": r[1], "status": r[2], "source_rel_path": r[3],
            "converted_at": r[4], "source_missing": r[5] == "missing",
        }
        for r in rows
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--search")
    ap.add_argument("--type")
    ap.add_argument("--status", default="current", choices=["current", "superseded", "all"])
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--db", default=None)
    args = ap.parse_args(argv)

    from doc_ingest import db as db_mod
    db_path = Path(args.db) if args.db else Path(__file__).resolve().parents[1] / "doc_ingest.db"
    conn = db_mod.get_connection(db_path)
    results = search(conn, args.search, args.type, args.status, args.limit)
    conn.close()
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Write `doc_ingest/manifest.py`**

```python
"""Regenerates a flat CSV/Markdown manifest, mirroring
output/brand-intel/youtube/_youtube-content-index.csv/.md's existing pattern
in this repo (spec §12)."""
from __future__ import annotations

import csv
from pathlib import Path

_HEADER = ["source_rel_path", "output_path", "source_type", "status", "converted_at"]


def _rows(conn) -> list[dict]:
    query = (
        "SELECT sf.rel_path, c.output_path, c.source_type, c.status, c.converted_at "
        "FROM conversions c JOIN source_files sf ON sf.id = c.source_file_id "
        "ORDER BY sf.rel_path, c.version_number"
    )
    return [dict(zip(_HEADER, row)) for row in conn.execute(query).fetchall()]


def regenerate(conn, output_root: Path) -> tuple[Path, Path]:
    rows = _rows(conn)
    csv_path = output_root / "_freedom2beu-content-index.csv"
    md_path = output_root / "_freedom2beu-content-index.md"
    output_root.mkdir(parents=True, exist_ok=True)

    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_HEADER)
        writer.writeheader()
        writer.writerows(rows)

    lines = ["# Freedom2BeU Document Index\n", f"\n- **Conversions indexed:** {len(rows)}\n\n"]
    lines.append("| Source | Output | Type | Status | Converted |\n")
    lines.append("|---|---|---|---|---|\n")
    for row in rows:
        lines.append(
            f"| {row['source_rel_path']} | {row['output_path']} | {row['source_type']} | "
            f"{row['status']} | {row['converted_at']} |\n"
        )
    md_path.write_text("".join(lines), encoding="utf-8")

    return csv_path, md_path
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd doc-ingest-app && python -m pytest tests/test_query.py tests/test_manifest.py -v
```

Expected: 6 passed

- [ ] **Step 6: Wire manifest regeneration into `run_ingest_cron.py`'s `run_once`** (Task 16) — otherwise "periodically regenerated" (spec §12) never actually happens

**After the drain loop, not inside the setup block.** `run_once`'s setup phase (reclaim/resume/scan/enqueue) runs and closes its connection *before* the drain loop claims and processes any jobs — regenerating the manifest there would always be one run stale, missing every conversion the run itself just produced. It needs its own connection, opened after the drain loop completes.

```python
# Add this import to scripts/run_ingest_cron.py
from doc_ingest import manifest

# Add after the `with ThreadPoolExecutor(...) as pool:` block, as the last
# thing run_once does:
    manifest_conn = db.get_connection(db_path)
    try:
        manifest.regenerate(manifest_conn, cfg.output_root)
    finally:
        manifest_conn.close()
```

- [ ] **Step 7: Commit**

```bash
git add doc-ingest-app/doc_ingest/query.py doc-ingest-app/doc_ingest/manifest.py doc-ingest-app/tests/test_query.py doc-ingest-app/tests/test_manifest.py doc-ingest-app/scripts/run_ingest_cron.py
git commit -m "feat(doc-ingest): add FTS5 CLI query, flat manifest regeneration, and wire it into the cron"
```

---

## Task 19: Claude Code `PreToolUse` hook — fast-fail UX layer

**Files:**
- Create: `.claude/hooks/protect_freedom2beu_output.py`
- Create: `tests/test_protect_freedom2beu_output.py` (repo-root suite — see below, **not** `.claude/hooks/tests/`)
- Modify: `.claude/settings.json`

**Interfaces:**
- Produces: a second `PreToolUse` entry alongside the existing `protect_briefs.py` one. This is layer 2 of spec §10 — the icacls deny-ACE (Task 13) is the real backstop; this hook only fast-fails *inside Claude Code sessions* before the OS is even asked.

Extends `protect_briefs.py`'s Edit/Write-path-check pattern (already in this repo) with the one thing that pattern doesn't cover: a heuristic scan of Bash/PowerShell command text for a write-ish verb plus a path under `Freedom2BeU/converted/` (spec §10 explicitly calls for this — a full shell parse is out of scope, a heuristic layered on top of the ACL is what's asked for).

**Test location and loading convention**: this repo's existing hook test, `tests/test_protect_briefs.py`, lives in the **root** pytest suite (CLAUDE.md's root + `pipeline-app` two-suite split — there is no separate `.claude/hooks` suite) and loads the hook via `importlib.util.spec_from_file_location`, not `sys.path.insert` + a plain `import`. This task's test follows that exact pattern so it actually runs as part of `python -m pytest` from the repo root, rather than living in a third, undiscovered test location.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_protect_freedom2beu_output.py
import importlib.util
from pathlib import Path

_HOOK_PATH = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "protect_freedom2beu_output.py"
_spec = importlib.util.spec_from_file_location("protect_freedom2beu_output", _HOOK_PATH)
protect_freedom2beu_output = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(protect_freedom2beu_output)
decide = protect_freedom2beu_output.decide
looks_like_a_write_command = protect_freedom2beu_output.looks_like_a_write_command


def test_edit_under_converted_is_denied(tmp_path):
    project_root = tmp_path
    target = project_root / "Freedom2BeU" / "converted" / "a.pdf.md"
    reason = decide("Edit", target, project_root)
    assert reason is not None


def test_write_to_a_new_file_under_converted_is_denied(tmp_path):
    project_root = tmp_path
    target = project_root / "Freedom2BeU" / "converted" / "new.md"
    reason = decide("Write", target, project_root)
    assert reason is not None


def test_edit_outside_freedom2beu_is_allowed(tmp_path):
    project_root = tmp_path
    target = project_root / "docs" / "something.md"
    reason = decide("Edit", target, project_root)
    assert reason is None


def test_edit_under_freedom2beu_tmp_staging_is_allowed(tmp_path):
    project_root = tmp_path
    target = project_root / "Freedom2BeU" / "_tmp" / "job-1" / "staged.md"
    reason = decide("Edit", target, project_root)
    assert reason is None


def test_looks_like_a_write_command_flags_redirection_into_converted():
    assert looks_like_a_write_command('echo "x" > Freedom2BeU/converted/a.pdf.md') is True
    assert looks_like_a_write_command('Remove-Item Freedom2BeU/converted/a.pdf.md') is True


def test_looks_like_a_write_command_allows_a_read_only_command():
    assert looks_like_a_write_command('cat Freedom2BeU/converted/a.pdf.md') is False
    assert looks_like_a_write_command('python doc_ingest/query.py --search "x"') is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_protect_freedom2beu_output.py -v
```

Expected: FAIL — the hook file doesn't exist yet, so `_spec.loader.exec_module` raises `FileNotFoundError`.

- [ ] **Step 3: Write `.claude/hooks/protect_freedom2beu_output.py`**

```python
#!/usr/bin/env python3
"""PreToolUse hook: fast-fail layer for Freedom2BeU/converted/ immutability.

This is layer 2 of the design's two-layer read-only enforcement (spec §10) --
the Windows ACL deny-write (doc-ingest-app/doc_ingest/lock.py) is the real
backstop; this hook only rejects the call before it reaches the OS, and only
inside Claude Code sessions that load this repo's settings.json. Extends
protect_briefs.py's Edit/Write-path pattern with a heuristic scan of
Bash/PowerShell command text, since those tools aren't caught by a
file_path-based check alone.
"""
import json
import os
import re
import sys
from pathlib import Path

_PROTECTED_PREFIX = ("Freedom2BeU", "converted")

_WRITE_VERB_RE = re.compile(
    r"(^|\s)(>|>>|Remove-Item|del|rm|move|Move-Item|copy|Copy-Item|Set-Content|Add-Content|ren|Rename-Item)\b",
    re.IGNORECASE,
)
_CONVERTED_PATH_RE = re.compile(r"Freedom2BeU[\\/]converted", re.IGNORECASE)


def decide(tool_name: str, resolved_path: Path, project_root: Path) -> str | None:
    try:
        rel = resolved_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return None
    if rel.parts[:2] != _PROTECTED_PREFIX:
        return None
    if tool_name in ("Edit", "Write", "NotebookEdit"):
        return (
            f"{rel} is under Freedom2BeU/converted/ -- validated conversions are "
            f"read-only by design (spec §10); write a new version through the "
            f"doc-ingest-app pipeline instead"
        )
    return None


def looks_like_a_write_command(command_text: str) -> bool:
    if not _CONVERTED_PATH_RE.search(command_text):
        return False
    return bool(_WRITE_VERB_RE.search(command_text))


def main() -> int:
    payload = json.load(sys.stdin)
    tool_name = payload.get("tool_name")
    project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()

    if tool_name in ("Edit", "Write", "NotebookEdit"):
        file_path = payload.get("tool_input", {}).get("file_path")
        if not file_path:
            return 0
        resolved_path = Path(file_path)
        if not resolved_path.is_absolute():
            resolved_path = (project_root / resolved_path).resolve()
        reason = decide(tool_name, resolved_path, project_root)
        if reason:
            print(reason, file=sys.stderr)
            return 2
        return 0

    if tool_name in ("Bash", "PowerShell"):
        command_text = payload.get("tool_input", {}).get("command", "")
        if looks_like_a_write_command(command_text):
            print(
                "This command looks like it writes to Freedom2BeU/converted/ -- "
                "validated conversions are read-only by design (spec §10)",
                file=sys.stderr,
            )
            return 2
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_protect_freedom2beu_output.py -v
```

Expected: 6 passed. Also re-run the full root suite (`python -m pytest tests/ -v`) to confirm this new file is picked up as part of it, not a fourth, silently-uncollected test location.

- [ ] **Step 5: Modify `.claude/settings.json`** — add a second `PreToolUse` entry (do not remove the existing `protect_briefs.py` one)

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/protect_briefs.py\""
          }
        ]
      },
      {
        "matcher": "Edit|Write|NotebookEdit|Bash|PowerShell",
        "hooks": [
          {
            "type": "command",
            "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/protect_freedom2beu_output.py\""
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 6: Commit**

```bash
git add .claude/hooks/protect_freedom2beu_output.py tests/test_protect_freedom2beu_output.py .claude/settings.json
git commit -m "feat(doc-ingest): add PreToolUse fast-fail hook for Freedom2BeU/converted/"
```

---

## Task 20: `SETUP.md` — manual one-time setup guide

**Files:**
- Create: `doc-ingest-app/SETUP.md`

**Interfaces:**
- No code — a required deliverable per spec §9 ("the user performs the actual browser consent, this project cannot do it on their behalf"). No test; verification is the two manual command checks at the end.

- [ ] **Step 1: Write `doc-ingest-app/SETUP.md`**

```markdown
# doc-ingest-app — one-time setup

Two external credentials need manual, one-time setup before the cron can run:
a `FIRECRAWL_API_KEY` for the `firecrawl-py` SDK, and a Google Drive/Docs/Sheets
OAuth client. Both are per-machine setup, not part of the app's code.

## 1. Firecrawl API key

```bash
cd doc-ingest-app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

`firecrawl-py` (in `requirements.txt`) reads `FIRECRAWL_API_KEY` from the environment
automatically — set it as a Windows user environment variable (get a key at
firecrawl.dev). Verify the key and the install both work:

```bash
python -c "from firecrawl import Firecrawl; from firecrawl.v2.types import ParseOptions; c = Firecrawl(); r = c.parse(b'<html><body>hello world</body></html>', filename='test.html', content_type='text/html', options=ParseOptions(formats=['markdown'])); print('ok:', bool(r.markdown))"
```

(HTML, not plain text, deliberately — `text/plain` isn't in firecrawl's supported format list, so a plain-text smoke test would fail with "unsupported format" and look like a broken setup when it isn't.)

If this raises an authentication error, double-check the environment variable is set
in the same shell/session that will run the cron (a system-level env var set via the
Windows GUI requires a fresh shell, or a reboot for a Task Scheduler run, to take
effect).

## 2. Google Drive/Docs/Sheets API (for `.gdoc`/`.gsheet` export)

1. In the Google Cloud Console, create a new project (or reuse an existing one) under
   the `admin@freedom2beu.com` Workspace account.
2. Enable three APIs for that project: **Google Drive API**, **Google Docs API**,
   **Google Sheets API**.
3. Configure the OAuth consent screen:
   - **User type: Internal.** This is a correctness requirement, not a preference —
     an External app left in Testing status issues refresh tokens that expire after
     7 days, which would silently break the 30-minute cron about a week after setup.
     Internal is available because `admin@freedom2beu.com` is a Workspace account, and
     it doesn't need Google's app-verification review since this is a single-user tool
     for the domain's own account.
4. Create an OAuth client of type **Desktop app**.
5. Download the client secret JSON and save it as `doc-ingest-app/client_secret.json`
   (already gitignored — never commit this file).
6. Run the app once by hand to complete the one-time browser consent:

   ```bash
   cd doc-ingest-app
   python -c "from pathlib import Path; from doc_ingest.drive_client import get_credentials; get_credentials(Path('token.json'), Path('client_secret.json'))"
   ```

   This opens a browser for one-time consent. The resulting token is cached at
   `doc-ingest-app/token.json` (gitignored) and refreshed silently thereafter.

## 3. Verify both are ready

```bash
python -c "from firecrawl import Firecrawl; from firecrawl.v2.types import ParseOptions; c = Firecrawl(); r = c.parse(b'<html><body>hello world</body></html>', filename='test.html', content_type='text/html', options=ParseOptions(formats=['markdown'])); print('ok:', bool(r.markdown))"
```

```bash
cd doc-ingest-app && python -c "from pathlib import Path; from doc_ingest.drive_client import get_credentials; c = get_credentials(Path('token.json'), Path('client_secret.json')); print('valid:', c.valid)"
```

Both must succeed before registering the cron task (`python scripts/setup_ingest_task.py --apply`).
```

- [ ] **Step 2: Commit**

```bash
git add doc-ingest-app/SETUP.md
git commit -m "docs(doc-ingest): add manual firecrawl/Drive OAuth setup guide"
```

---

## Task 21: Integration test + real read-only-enforcement tests

**Files:**
- Create: `doc-ingest-app/tests/test_integration.py`
- Create: `doc-ingest-app/tests/test_readonly_enforcement.py`

**Interfaces:**
- Consumes: everything built so far.
- Produces: the spec §13 "Integration" and "tested for real" bullets — a fixture folder covering every convertible type run end-to-end, and two tests that assert real OS-level write denial rather than relying on code review.

- [ ] **Step 1: Write `tests/test_integration.py`**

```python
"""End-to-end fixture covering pdf/docx/xlsx/txt/md plus a mocked Drive
gdoc response, run through the real scan -> enqueue -> claim -> process_job
path, asserting the output tree, frontmatter, DB rows, and gauntlet outcomes
(spec §13's Integration bullet).

Locking is mocked here, same as Task 15's own tests -- lock.py (Task 13) is
deliberately non-idempotent once fully applied, and only Task 13's own tests
and this file's dedicated test_readonly_enforcement.py are meant to perform
a REAL lock (using the lock_test_dir fixture, never tmp_path)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import docx
import openpyxl
from pypdf import PdfWriter

from doc_ingest import frontmatter, jobs, sync, worker
from doc_ingest.config import Config

_DOCX_SENTENCE = "This is a real docx document with enough words in it to pass the word count parity check comfortably today."


def _build_fixture_tree(input_root):
    (input_root / "docs").mkdir(parents=True)

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(input_root / "docs" / "Sample.pdf", "wb") as fh:
        writer.write(fh)

    document = docx.Document()
    document.add_paragraph(_DOCX_SENTENCE)
    document.save(input_root / "docs" / "Sample.docx")

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for i in range(5):
        sheet.append([i, i * 2])
    workbook.save(input_root / "docs" / "Sample.xlsx")

    (input_root / "docs" / "Sample.txt").write_text(
        "Plain text passthrough content with real words in it.", encoding="utf-8"
    )
    (input_root / "docs" / "Sample.md").write_text(
        "# Already markdown\n\nPassthrough content.", encoding="utf-8"
    )


def _fake_parse(data, filename=None, content_type=None, options=None):
    """Per-type mocked firecrawl output, proportioned against each real
    fixture file rather than one uniform body for every type -- a single
    generic body either trips below_size_ratio_floor (real docx/xlsx source
    bytes vastly outweigh a token mock body) or fails word/sheet/row parity
    outright. size_ratio_floor is disabled in cfg below for this test
    specifically because matching real source-byte-size proportions in a
    mock is not the point of this fixture; the per-type CONTENT below still
    has to satisfy the parity checks, which size_ratio_floor doesn't cover."""
    if filename == "Sample.pdf":
        return MagicMock(markdown="# PDF Content\n\nplenty of real extracted words appear on this single page for testing")
    if filename == "Sample.docx":
        # Echoing the exact source sentence back gives read_docx_word_count
        # (source) and len(body.split()) (output) the same count -- real
        # parity, not a number picked to trivially satisfy the tolerance.
        return MagicMock(markdown=_DOCX_SENTENCE)
    if filename == "Sample.xlsx":
        rows = "\n".join(f"| {i} | {i * 2} |" for i in range(5))
        return MagicMock(markdown=f"## Sheet\n\n| A | B |\n|---|---|\n{rows}\n")
    raise AssertionError(f"unexpected firecrawl.parse call for filename={filename!r}")


def test_every_convertible_type_produces_a_locked_current_conversion(conn, tmp_path):
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    _build_fixture_tree(input_root)
    cfg = Config(input_root=input_root, output_root=output_root, size_ratio_floor=0.0)

    mock_client = MagicMock()
    mock_client.parse.side_effect = _fake_parse

    sync.sync_source_files(conn, input_root)
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 5

    with patch("firecrawl.Firecrawl", return_value=mock_client), \
         patch("doc_ingest.lock.apply_readonly_lock"), \
         patch("doc_ingest.lock.verify_locked", return_value=True):
        for _ in range(5):
            job_id = jobs.claim_job(conn, worker_id="w1")
            assert job_id is not None
            worker.process_job(conn, job_id, cfg, worker_id="w1")

    failed = conn.execute("SELECT source_type, failure_reason FROM conversion_jobs cj JOIN source_files sf "
                           "ON sf.id = cj.source_file_id WHERE cj.status = 'failed'").fetchall()
    assert failed == [], failed

    current = conn.execute("SELECT source_type, output_path, locked_confirmed_at FROM conversions WHERE status = 'current'").fetchall()
    assert len(current) == 5
    seen_types = {row[0] for row in current}
    assert seen_types == {"pdf", "docx", "xlsx", "txt", "md"}
    for source_type, output_path, locked_confirmed_at in current:
        assert locked_confirmed_at is not None
        final_path = cfg.converted_root / output_path
        assert final_path.exists()
        fm, body = frontmatter.parse(final_path.read_text(encoding="utf-8"))
        assert fm["business_line"] == "freedom2beu"
        assert fm["status"] == "current"


def test_mocked_gdoc_export_produces_a_current_conversion(conn, tmp_path):
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    input_root.mkdir()
    stub = '{"doc_id": "fake-doc-id", "resource_key": "rk1", "email": "admin@freedom2beu.com"}'
    (input_root / "Session Notes.gdoc").write_text(stub, encoding="utf-8")
    cfg = Config(input_root=input_root, output_root=output_root)

    sync.sync_source_files(conn, input_root)
    row = conn.execute("SELECT classification FROM source_files WHERE rel_path = 'Session Notes.gdoc'").fetchone()
    assert row[0] == "gdoc_pointer"
    # Full Drive-native process_job wiring (export -> gauntlet -> lock) is
    # exercised end-to-end by Task 22's own worker tests
    # (test_process_job_handles_a_gdoc_via_mocked_drive_export and the
    # docx-fallback variant); this integration test only confirms
    # scan/classification correctly routes .gdoc away from firecrawl.
```

- [ ] **Step 2: Write `tests/test_readonly_enforcement.py`**

```python
"""Tests the read-only guarantees for real -- an actual OS-level write
attempt must fail, not a code-review assumption (spec §13)."""
from __future__ import annotations

import getpass
import subprocess

import pytest

from doc_ingest import lock, sync


@pytest.mark.allow_subprocess
def test_a_readonly_input_folder_makes_any_write_attempt_fail_with_a_real_os_error(conn, tmp_path):
    input_root = tmp_path / "input"
    input_root.mkdir()
    target = input_root / "a.pdf"
    target.write_bytes(b"%PDF-1.4 fake")

    account = getpass.getuser()
    subprocess.run(
        ["icacls", str(target), "/deny", f"{account}:(WD,WA,WEA,DE)"],
        capture_output=True, text=True, check=True,
    )
    try:
        sync.sync_source_files(conn, input_root)  # must not raise -- read-only scan
        with pytest.raises(PermissionError):
            target.write_bytes(b"an attempted mutation of the read-only input tree")
    finally:
        subprocess.run(["icacls", str(target), "/reset"], capture_output=True, text=True)


@pytest.mark.allow_subprocess
def test_a_locked_output_file_rejects_a_write_from_the_same_account(lock_test_dir):
    # lock_test_dir (Task 13), NOT tmp_path -- lock.apply_readonly_lock's
    # deny includes Delete at the OWNER RIGHTS level, so a file it fully
    # locks is not guaranteed deletable by the same non-elevated account
    # afterward, which would leave pytest's tmp_path cleanup hitting a real
    # PermissionError on every subsequent run.
    import uuid

    target = lock_test_dir / f"locked-{uuid.uuid4().hex}.pdf.md"
    target.write_text("locked content", encoding="utf-8")
    lock.apply_readonly_lock(target)
    with pytest.raises(PermissionError):
        target.write_text("attempted overwrite", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "locked content"
```

- [ ] **Step 3: Run all tests to verify they pass**

```bash
cd doc-ingest-app && python -m pytest tests/test_integration.py tests/test_readonly_enforcement.py -v
```

Expected: 4 passed. (`test_a_readonly_input_folder_makes_any_write_attempt_fail_with_a_real_os_error` cleans up its own ACL change in a `finally` block, restoring the fixture's own tmp file to normal before pytest tears it down.)

- [ ] **Step 4: Run the full suite**

```bash
cd doc-ingest-app && python -m pytest -v
```

Expected: every test from Tasks 0–21 passes.

- [ ] **Step 5: Commit**

```bash
git add doc-ingest-app/tests/test_integration.py doc-ingest-app/tests/test_readonly_enforcement.py
git commit -m "test(doc-ingest): add end-to-end fixture and real read-only-enforcement tests"
```

---

## Task 22: Drive metadata sync + `.gdoc`/`.gsheet` export wiring

**Files:**
- Create: `doc-ingest-app/doc_ingest/drive_sync.py`
- Test: `doc-ingest-app/tests/test_drive_sync.py`
- Modify: `doc-ingest-app/doc_ingest/drive_client.py` (Task 14) — add `build_default_service`
- Modify: `doc-ingest-app/doc_ingest/worker.py` (Task 15) — add the Drive-native branch to `process_job`
- Modify: `doc-ingest-app/scripts/run_ingest_cron.py` (Task 16) — wire the Drive-check step into `run_once`
- Test: `doc-ingest-app/tests/test_worker.py`, `doc-ingest-app/tests/test_run_ingest_cron.py` (additions)

**Every earlier task built the local-file half of this pipeline and left the Drive half unwired** — this is the task that closes that gap: nothing ever populated `source_files.drive_modified_time`, and `worker.process_job` had no branch for a Drive-native source at all. Without this task, all ~100 `.gdoc`/`.gsheet` files in the real corpus (spec §2) would sit in `source_files` forever, correctly classified but never converted.

**`jobs.py`'s `enqueue_pending_jobs` no longer needs a change here.** Task 7's implementation already includes `gdoc_pointer` in its candidate query and branches change-detection by classification — `convertible` rows compare `content_hash`, `gdoc_pointer` rows compare `drive_modified_time_at_conversion` only, never both. (An earlier draft of this plan deferred that branching to this task and got it wrong: it OR'd `content_hash != source_hash_at_conversion` together with the `drive_modified_time` comparison, which for a Drive-native row compares a sha256 hex digest against an ISO timestamp — always unequal, so every `.gdoc`/`.gsheet` would have re-enqueued, and gotten a new locked version, on every 30-minute wake forever. Fixed at the source in Task 7, not patched here.) This task only needs to make sure `source_files.drive_modified_time` actually gets populated (`drive_sync.py`, below) and that a claimed Drive-native job gets exported and converted (`worker.py`'s new branch, Step 8).

**Interfaces:**
- Produces: `drive_sync.parse_stub(stub_path: Path) -> dict` (`{"doc_id", "resource_key"}`), `drive_sync.sync_drive_metadata(conn, service, cfg) -> int`.
- `drive_client.build_default_service(cfg)` — lazily builds a real `googleapiclient` Drive service from cached credentials (`token.json`/`client_secret.json`, both gitignored per SETUP.md); only called when a Drive-native job actually needs it, never at import time or for local-file jobs.
- `worker.process_job(conn, job_id, cfg, worker_id, drive_service_factory=None)` — the new optional 5th parameter lets tests inject a mock factory; production code omits it and gets `drive_client.build_default_service`.

**Two open items, stated rather than silently glossed over** (spec §15 already sets this precedent for tolerance bands — this task adds two more in the same spirit):
1. **`source_hash` for a direct-markdown gdoc export** uses `drive_modified_time` as a practical stand-in for Drive's `headRevisionId` (spec §7 calls for the latter). `build_batch_metadata`'s `fields` parameter would need `headRevisionId` added and a `Files: get` scope capable of returning it — not verified against live Drive API v3 behavior in this plan; a one-line change to `drive_client.build_batch_metadata`'s `fields` string once confirmed.
2. **Word-count parity for a direct-markdown gdoc export has no independent check** — spec §8 asks for "the Drive API's own document-length metadata, not a second export," which this plan doesn't implement (Drive's `documents.get` from the Docs API, not the Drive API, would be the real source — a second API surface this plan doesn't wire up). A docx-fallback export (§9's size/format fallback) *does* get full independent-reader coverage, since it becomes a real local `.docx` file. Only the direct-markdown path is missing this check; Gate 1 simply skips the docx/gdoc word-count check when `source_word_count` isn't present, which is what happens today for this one path.

- [ ] **Step 1: Write the failing test for `drive_sync.py`**

```python
# tests/test_drive_sync.py
import json
from unittest.mock import MagicMock

from doc_ingest import drive_sync, jobs, sync


def _seed_gdoc_stub(input_root, rel_path, doc_id, resource_key="rk1"):
    path = input_root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"doc_id": doc_id, "resource_key": resource_key, "email": "admin@freedom2beu.com"}), encoding="utf-8")


def test_parse_stub_reads_doc_id_and_resource_key(tmp_path):
    stub = tmp_path / "Notes.gdoc"
    stub.write_text(json.dumps({"doc_id": "abc123", "resource_key": "rk1", "email": "x@y.com"}), encoding="utf-8")
    parsed = drive_sync.parse_stub(stub)
    assert parsed == {"doc_id": "abc123", "resource_key": "rk1"}


def test_sync_drive_metadata_updates_source_files(conn, tmp_path, monkeypatch):
    from doc_ingest.config import Config

    input_root = tmp_path / "input"
    _seed_gdoc_stub(input_root, "Notes.gdoc", doc_id="doc-1")
    cfg = Config(input_root=input_root)
    sync.sync_source_files(conn, input_root)

    fake_metadata = {"doc-1": {"id": "doc-1", "modifiedTime": "2026-08-10T00:00:00Z", "mimeType": "application/vnd.google-apps.document"}}
    monkeypatch.setattr("doc_ingest.drive_client.build_batch_metadata", lambda service, doc_ids, cfg_arg: fake_metadata)

    updated = drive_sync.sync_drive_metadata(conn, MagicMock(), cfg)

    assert updated == 1
    row = conn.execute("SELECT doc_id, resource_key, drive_modified_time, drive_mime_type FROM source_files WHERE rel_path = 'Notes.gdoc'").fetchone()
    assert row == ("doc-1", "rk1", "2026-08-10T00:00:00Z", "application/vnd.google-apps.document")


def test_regression_enqueue_uses_drive_modified_time_not_local_stub_mtime(conn, tmp_path, monkeypatch):
    """The single correctness issue in this design most worth a standing
    guard (spec §13): a .gdoc stub's own mtime NEVER changes when the real
    document is edited in Drive -- it's a static 176-byte pointer. This
    fixture keeps the stub file completely untouched (same bytes, same
    mtime) across two sync passes and asserts the job still gets enqueued
    the second time, purely because the MOCKED Drive modifiedTime advanced."""
    from doc_ingest.config import Config

    input_root = tmp_path / "input"
    _seed_gdoc_stub(input_root, "Notes.gdoc", doc_id="doc-1")
    stub_path = input_root / "Notes.gdoc"
    stub_bytes_before = stub_path.read_bytes()
    stub_mtime_before = stub_path.stat().st_mtime

    cfg = Config(input_root=input_root)
    sync.sync_source_files(conn, input_root)

    # First Drive check + enqueue: establishes a baseline modifiedTime.
    monkeypatch.setattr(
        "doc_ingest.drive_client.build_batch_metadata",
        lambda service, doc_ids, cfg_arg: {"doc-1": {"id": "doc-1", "modifiedTime": "2026-08-01T00:00:00Z", "mimeType": "application/vnd.google-apps.document"}},
    )
    drive_sync.sync_drive_metadata(conn, MagicMock(), cfg)
    first_created = jobs.enqueue_pending_jobs(conn)
    assert first_created == 1
    job_id = jobs.claim_job(conn, worker_id="w1")
    # Simulate a successful conversion completing, without running the real
    # worker -- this test is about enqueue/Drive-check interaction only.
    now = "2026-08-01T00:05:00+00:00"
    source_id = conn.execute("SELECT id FROM source_files WHERE rel_path = 'Notes.gdoc'").fetchone()[0]
    conn.execute(
        "INSERT INTO conversions (source_file_id, job_id, version_number, output_path, status, source_type, "
        "drive_modified_time_at_conversion, conversion_tool, converted_at) "
        "VALUES (?, ?, 1, 'Notes.gdoc.md', 'current', 'gdoc', '2026-08-01T00:00:00Z', 'google-docs-export', ?)",
        (source_id, job_id, now),
    )
    conn.execute("UPDATE conversion_jobs SET status = 'complete' WHERE id = ?", (job_id,))
    conn.commit()

    # Second pass: re-scan (stub untouched on disk -- proves scan alone
    # cannot detect this change), then a Drive check reporting a NEWER
    # modifiedTime with the exact same local file.
    sync.sync_source_files(conn, input_root)
    assert stub_path.read_bytes() == stub_bytes_before
    assert stub_path.stat().st_mtime == stub_mtime_before

    monkeypatch.setattr(
        "doc_ingest.drive_client.build_batch_metadata",
        lambda service, doc_ids, cfg_arg: {"doc-1": {"id": "doc-1", "modifiedTime": "2026-08-12T00:00:00Z", "mimeType": "application/vnd.google-apps.document"}},
    )
    drive_sync.sync_drive_metadata(conn, MagicMock(), cfg)
    second_created = jobs.enqueue_pending_jobs(conn)

    assert second_created == 1  # enqueued purely because of the mocked Drive modifiedTime


def test_regression_unchanged_drive_modified_time_does_not_reenqueue(conn, tmp_path, monkeypatch):
    """The negative half of the test above -- without it, a version of
    enqueue_pending_jobs that (incorrectly) ALWAYS creates a job for a
    'current'-conversion-less lookup, or that compares the wrong field,
    could make the positive-only test above pass for the wrong reason. This
    proves a Drive check reporting the SAME modifiedTime twice in a row
    does not re-enqueue."""
    from doc_ingest.config import Config

    input_root = tmp_path / "input"
    _seed_gdoc_stub(input_root, "Notes.gdoc", doc_id="doc-1")
    cfg = Config(input_root=input_root)
    sync.sync_source_files(conn, input_root)

    unchanged_metadata = {"doc-1": {"id": "doc-1", "modifiedTime": "2026-08-01T00:00:00Z", "mimeType": "application/vnd.google-apps.document"}}
    monkeypatch.setattr("doc_ingest.drive_client.build_batch_metadata", lambda service, doc_ids, cfg_arg: unchanged_metadata)

    drive_sync.sync_drive_metadata(conn, MagicMock(), cfg)
    first_created = jobs.enqueue_pending_jobs(conn)
    assert first_created == 1
    job_id = jobs.claim_job(conn, worker_id="w1")
    now = "2026-08-01T00:05:00+00:00"
    source_id = conn.execute("SELECT id FROM source_files WHERE rel_path = 'Notes.gdoc'").fetchone()[0]
    conn.execute(
        "INSERT INTO conversions (source_file_id, job_id, version_number, output_path, status, source_type, "
        "drive_modified_time_at_conversion, conversion_tool, converted_at) "
        "VALUES (?, ?, 1, 'Notes.gdoc.md', 'current', 'gdoc', '2026-08-01T00:00:00Z', 'google-docs-export', ?)",
        (source_id, job_id, now),
    )
    conn.execute("UPDATE conversion_jobs SET status = 'complete' WHERE id = ?", (job_id,))
    conn.commit()

    # Re-sync and re-check with the SAME modifiedTime as the conversion already recorded.
    sync.sync_source_files(conn, input_root)
    drive_sync.sync_drive_metadata(conn, MagicMock(), cfg)
    second_created = jobs.enqueue_pending_jobs(conn)

    assert second_created == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd doc-ingest-app && python -m pytest tests/test_drive_sync.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'doc_ingest.drive_sync'`

- [ ] **Step 3: Write `doc_ingest/drive_sync.py`**

```python
"""Parses .gdoc/.gsheet stub JSON (read-only against the input tree) and
queries the Drive API in batches for modifiedTime/mimeType. The stub is
purely a pointer to WHICH document exists -- its own bytes and mtime are
never a content or timestamp source (spec §4 step 3, §9); only the Drive
API's modifiedTime drives change detection for these rows."""
from __future__ import annotations

import json
from pathlib import Path

from doc_ingest import db, drive_client


def parse_stub(stub_path: Path) -> dict:
    payload = json.loads(stub_path.read_text(encoding="utf-8"))
    return {"doc_id": payload.get("doc_id"), "resource_key": payload.get("resource_key")}


def sync_drive_metadata(conn, service, cfg) -> int:
    rows = conn.execute(
        "SELECT id, rel_path FROM source_files WHERE classification = 'gdoc_pointer'"
    ).fetchall()
    if not rows:
        return 0

    doc_ids: list[str] = []
    source_by_doc_id: dict[str, int] = {}
    resource_key_by_doc_id: dict[str, str | None] = {}
    for source_file_id, rel_path in rows:
        stub = parse_stub(cfg.input_root / rel_path)
        doc_id = stub["doc_id"]
        if doc_id is None:
            continue
        doc_ids.append(doc_id)
        source_by_doc_id[doc_id] = source_file_id
        resource_key_by_doc_id[doc_id] = stub["resource_key"]

    metadata = drive_client.build_batch_metadata(service, doc_ids, cfg)

    updated = 0
    with db.transaction(conn):
        for doc_id, info in metadata.items():
            conn.execute(
                "UPDATE source_files SET doc_id = ?, resource_key = ?, drive_modified_time = ?, "
                "drive_mime_type = ? WHERE id = ?",
                (
                    doc_id, resource_key_by_doc_id.get(doc_id), info.get("modifiedTime"),
                    info.get("mimeType"), source_by_doc_id[doc_id],
                ),
            )
            updated += 1
    return updated
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_drive_sync.py -v
```

Expected: 4 passed

- [ ] **Step 5: Add `build_default_service` to `drive_client.py`** (Task 14)

```python
# Append to doc_ingest/drive_client.py
def build_default_service(cfg):
    """Lazily builds a real Drive service from cached credentials -- called
    only when a Drive-native job actually needs one (worker.py), never at
    import time and never for local-file jobs. Token/client-secret paths are
    fixed relative to the app root per SETUP.md.

    Deliberately does NOT fall through to get_credentials' interactive
    browser flow when token.json is missing: run_ingest_cron.py runs
    unattended under Task Scheduler, and InstalledAppFlow.run_local_server
    blocks indefinitely waiting for a browser that will never appear there --
    wedging every subsequent 30-minute wake under Task Scheduler's
    skip-if-running default (spec §11). The one-time interactive consent
    belongs to SETUP.md step 6, run by hand, not to an unattended cron wake."""
    from googleapiclient.discovery import build

    app_root = Path(__file__).resolve().parents[1]
    token_path = app_root / "token.json"
    if not token_path.exists():
        raise RuntimeError(
            "doc-ingest-app has no cached Drive token -- run SETUP.md step 6 "
            "(one-time interactive consent) before the cron can process "
            "gdoc/gsheet files"
        )
    creds = get_credentials(token_path, app_root / "client_secret.json")
    return build("drive", "v3", credentials=creds)
```

Add a test to `tests/test_drive_client.py`:

```python
def test_build_default_service_fails_fast_without_a_cached_token(tmp_path, monkeypatch):
    """The empirical claim: a missing token.json must raise immediately, not
    reach InstalledAppFlow.run_local_server -- which would open an
    interactive browser flow and hang the unattended cron indefinitely.
    Points the function's own __file__ at a fresh tmp_path so app_root
    resolves somewhere token.json provably doesn't exist."""
    import doc_ingest.drive_client as dc_module

    fake_module_path = tmp_path / "fake_app" / "doc_ingest" / "drive_client.py"
    monkeypatch.setattr(dc_module, "__file__", str(fake_module_path))

    with pytest.raises(RuntimeError, match="SETUP.md step 6"):
        drive_client.build_default_service(Config())
```

- [ ] **Step 5b: Run the drive_client suite to verify the addition passes**

```bash
cd doc-ingest-app && python -m pytest tests/test_drive_client.py -v
```

Expected: 8 passed

- [ ] **Step 6: Extend `worker.py`'s `process_job`** (Task 15) — add the Drive-native branch

This replaces the **entire** `doc_ingest/worker.py` module with the version below (add the `drive_client` import; add `_convert_drive_native`; `process_job` gains the Drive-native branch, real `drive_modified_time_at_conversion` handling, and the correct-format export filename — everything else, including the heartbeat thread from Task 15, is unchanged from the version Task 15 left it in):

```python
"""Orchestrates one claimed job end to end (spec §4 steps 6-9): stage,
convert, gauntlet, then an explicit write -> commit-as-current -> lock ->
verify sequence -- not one atomic operation, because a filesystem write and
an icacls subprocess call cannot share a SQLite transaction. A job that dies
-- or whose lock simply doesn't confirm -- between the write and the lock-
verify is left with locked_confirmed_at NULL and its conversion_jobs row at
'placing', not 'complete'; resume_unlocked_conversions re-attempts only the
lock and flips the job to 'complete' once it lands, never a reconversion.

A heartbeat thread runs on its own connection for the life of the job (spec
§5: never share conn across threads) so reclaim_stale_jobs (Task 7) can tell
a live worker from a dead one even when the actual conversion step takes
longer than the reclaim staleness threshold.

Handles both local files (pdf/docx/xlsx/txt/md/ppt) and Drive-native sources
(.gdoc/.gsheet, classification='gdoc_pointer') -- the latter export via
drive_client (Task 14) instead of copying from cfg.input_root."""
from __future__ import annotations

import datetime as dt
import shutil
import threading
from pathlib import Path

from doc_ingest import convert, db, drive_client, frontmatter, gauntlet, jobs, lock, metadata_readers, naming

_LOCAL_EXTENSIONS = {"pdf": "pdf", "docx": "docx", "xlsx": "xlsx", "txt": "txt", "md": "md", "ppt": "ppt"}


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _db_path_of(conn) -> Path:
    """The heartbeat thread needs its own connection (spec §5) but
    process_job only receives an already-open one -- PRAGMA database_list's
    third column is the file path SQLite actually resolved from the
    connection string, which is how the heartbeat thread gets there without
    process_job's signature needing a separate db_path parameter."""
    row = conn.execute("PRAGMA database_list").fetchone()
    return Path(row[2])


def _run_heartbeat_loop(db_path: Path, job_id: int, worker_id: str, interval_s: float, stop_event: threading.Event) -> None:
    heartbeat_conn = db.get_connection(db_path)
    try:
        while not stop_event.wait(interval_s):
            try:
                jobs.heartbeat(heartbeat_conn, job_id, worker_id)
            except Exception:
                pass  # best-effort -- a missed tick risks an earlier reclaim, not a crash
    finally:
        heartbeat_conn.close()


def _source_type_for(extension: str, sniffed_signature: str | None) -> str:
    if extension:
        return _LOCAL_EXTENSIONS[extension]
    if sniffed_signature == "pdf":
        return "pdf"
    raise ValueError(f"cannot determine source_type for an extensionless file (sniffed_signature={sniffed_signature!r})")


def _convert(staged_path, source_type: str, cfg):
    """TXT/MD bypass firecrawl entirely -- it's not in firecrawl's supported
    format list, and spec §2/§8 call for a verbatim pass-through with
    frontmatter added, not a parse."""
    if source_type in ("txt", "md"):
        try:
            body = staged_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            return convert.ConversionResult(success=False, markdown_body=None, tool="passthrough", error=f"invalid_utf8: {exc}")
        return convert.ConversionResult(success=True, markdown_body=body, tool="passthrough", error=None)
    return convert.convert_local_file(staged_path, source_type, cfg)


def _convert_drive_native(service, doc_id: str, source_type: str, tmp_dir, cfg):
    """Drive export first, then -- for anything that came back as raw bytes
    rather than markdown (the docx/xlsx fallback paths, spec §9) -- the same
    local conversion + independent-reader path a real local file of that
    type would get. tool is preserved from the EXPORT step (google-docs-
    export / google-docs-export-docx-fallback / google-sheets-export), not
    overwritten with 'firecrawl-parse', so the record correctly shows the
    file came via Drive.

    export_google_doc doesn't know ahead of time whether it'll get markdown
    or docx bytes, so it writes to whatever path it's given -- if the docx
    fallback happened, the file at that path IS docx content but is still
    named export.md at that point. It's renamed to export.docx before being
    treated as a real .docx (read by metadata_readers, sent to firecrawl
    with a matching filename) rather than left as a .md-named file holding
    binary docx bytes."""
    if source_type == "gdoc":
        dest = tmp_dir / "export.md"
        export_result = drive_client.export_google_doc(service, doc_id, dest, cfg)
        if not export_result.success:
            return export_result, None, {}
        if export_result.tool == "google-docs-export":
            return export_result, dest, {}  # direct markdown -- see Task 22's open item 2

        docx_path = tmp_dir / "export.docx"
        dest.rename(docx_path)
        metadata = {
            "source_word_count": metadata_readers.read_docx_word_count(docx_path),
            "source_table_count": metadata_readers.read_docx_table_count(docx_path),
        }
        converted = _convert(docx_path, "docx", cfg)
        merged = convert.ConversionResult(
            success=converted.success, markdown_body=converted.markdown_body,
            tool=export_result.tool, error=converted.error,
        )
        return merged, docx_path, metadata

    dest = tmp_dir / "export.xlsx"
    export_result = drive_client.export_google_sheet(service, doc_id, dest, cfg)
    if not export_result.success:
        return export_result, None, {}
    sheet_count, row_count = metadata_readers.read_xlsx_sheet_and_row_counts(dest)
    converted = _convert(dest, "xlsx", cfg)
    merged = convert.ConversionResult(
        success=converted.success, markdown_body=converted.markdown_body,
        tool=export_result.tool, error=converted.error,
    )
    return merged, dest, {"source_sheet_count": sheet_count, "source_row_count": row_count}


def _independent_metadata(staged_path, source_type: str) -> dict:
    """SOURCE-side values only, read independently of firecrawl's own
    output -- Gate 1 (Task 11) computes every OUTPUT-side count itself from
    the assembled markdown."""
    if source_type == "pdf":
        return {"page_count": metadata_readers.read_pdf_page_count(staged_path)}
    if source_type == "docx":
        return {
            "source_word_count": metadata_readers.read_docx_word_count(staged_path),
            "source_table_count": metadata_readers.read_docx_table_count(staged_path),
        }
    if source_type == "xlsx":
        sheet_count, row_count = metadata_readers.read_xlsx_sheet_and_row_counts(staged_path)
        return {"source_sheet_count": sheet_count, "source_row_count": row_count}
    return {}


def _frontmatter_extras(independent_metadata: dict) -> dict:
    """Maps this module's internal source_*-prefixed metadata keys onto the
    exact field names spec §7 sanctions in frontmatter (page_count,
    word_count, sheet_count, row_count_total) -- source_table_count is
    gauntlet-only and deliberately excluded, since table_count isn't a
    frontmatter field spec §7 lists."""
    extras = {}
    if "page_count" in independent_metadata:
        extras["page_count"] = independent_metadata["page_count"]
    if "source_word_count" in independent_metadata:
        extras["word_count"] = independent_metadata["source_word_count"]
    if "source_sheet_count" in independent_metadata:
        extras["sheet_count"] = independent_metadata["source_sheet_count"]
    if "source_row_count" in independent_metadata:
        extras["row_count_total"] = independent_metadata["source_row_count"]
    return extras


def _fail_job(conn, job_id: int, reason: str) -> None:
    with db.transaction(conn):
        conn.execute(
            "UPDATE conversion_jobs SET status = 'failed', failure_reason = ?, finished_at = ? WHERE id = ?",
            (reason, _now_iso(), job_id),
        )


def process_job(conn, job_id: int, cfg, worker_id: str, drive_service_factory=None) -> None:
    job = conn.execute(
        "SELECT source_file_id FROM conversion_jobs WHERE id = ?", (job_id,)
    ).fetchone()
    source_file_id = job[0]
    source = conn.execute(
        "SELECT rel_path, extension, size_bytes, sniffed_signature, mtime, content_hash, "
        "classification, doc_id, drive_modified_time FROM source_files WHERE id = ?",
        (source_file_id,),
    ).fetchone()
    (rel_path, extension, size_bytes, sniffed_signature, source_mtime, local_content_hash,
     classification, doc_id, drive_modified_time) = source
    is_drive_native = classification == "gdoc_pointer"

    tmp_dir = cfg.tmp_root / f"job-{job_id}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with db.transaction(conn):
        conn.execute(
            "UPDATE conversion_jobs SET status = 'converting', tmp_dir = ? WHERE id = ?",
            (str(tmp_dir), job_id),
        )

    stop_heartbeat = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_run_heartbeat_loop,
        args=(_db_path_of(conn), job_id, worker_id, cfg.reclaim_heartbeat_interval_s, stop_heartbeat),
        daemon=True,
    )
    heartbeat_thread.start()
    try:
        if is_drive_native:
            source_type = "gdoc" if extension == "gdoc" else "gsheet"
            service = (drive_service_factory or drive_client.build_default_service)(cfg)
            conversion_result, staged_path, independent_metadata = _convert_drive_native(
                service, doc_id, source_type, tmp_dir, cfg,
            )
            # source_hash for frontmatter/conversions -- see Task 22's open
            # item 1 (a real headRevisionId isn't fetched yet;
            # drive_modified_time is a practical stand-in with the same "did
            # the content change" purpose).
            source_hash = drive_modified_time
            # source_modified_at must be the actual Drive edit time, NOT the
            # local stub's filesystem mtime -- the stub is a static 176-byte
            # pointer that never changes when the real document is edited
            # (spec §4 step 3, §7). Using the stub's mtime here would be
            # exactly the conflation the mtime-vs-modifiedTime regression
            # test (Task 22) exists to catch, just moved into frontmatter
            # instead of into enqueue's change detection.
            source_modified_at = drive_modified_time
        else:
            source_type = _source_type_for(extension, sniffed_signature)
            staged_path = tmp_dir / rel_path.rsplit("/", 1)[-1]
            shutil.copy2(cfg.input_root / rel_path, staged_path)
            conversion_result = _convert(staged_path, source_type, cfg)
            independent_metadata = _independent_metadata(staged_path, source_type) if conversion_result.success else {}
            source_hash = local_content_hash
            source_modified_at = source_mtime

        if not conversion_result.success:
            _fail_job(conn, job_id, conversion_result.error)
            return

        prior_version = conn.execute(
            "SELECT MAX(version_number) FROM conversions WHERE source_file_id = ?", (source_file_id,)
        ).fetchone()[0]
        version = (prior_version or 0) + 1

        gate2_result, dest_rel_path = gauntlet.run_gate2(conn, rel_path, source_file_id, version, cfg)
        if not gate2_result.passed:
            _fail_job(conn, job_id, gate2_result.failure_reason)
            return

        frontmatter_extras = _frontmatter_extras(independent_metadata)
        base_fm = {
            "source_path": rel_path, "source_type": source_type, "source_hash": source_hash,
            "source_modified_at": source_modified_at, "converted_at": _now_iso(),
            "conversion_tool": conversion_result.tool, "version": version, "status": "current",
            "business_line": "freedom2beu", "gauntlet_passed_at": _now_iso(),
        }
        fm = frontmatter.build_frontmatter(base_fm, frontmatter_extras)
        assembled = frontmatter.serialize(fm, conversion_result.markdown_body)

        gate1_result = gauntlet.run_gate1(source_type, size_bytes or 0, assembled, independent_metadata, cfg)
        if not gate1_result.passed:
            _fail_job(conn, job_id, gate1_result.failure_reason)
            return

        # --- 9(a): write the final file ---
        final_path = cfg.converted_root / dest_rel_path
        final_path.parent.mkdir(parents=True, exist_ok=True)
        # \\?\-prefixed open(), not final_path.write_text(): the defense-in-
        # depth backstop spec §6 describes for a path that's still over
        # cfg.long_path_threshold_chars despite naming.py's shortening --
        # applied at this one call site because Python's open() on Windows
        # honors the prefix reliably, which icacls (lock.py) is not
        # guaranteed to (naming.long_path's docstring, Task 4).
        with open(naming.long_path(final_path), "w", encoding="utf-8") as fh:
            fh.write(assembled)

        # --- 9(b): commit the DB row as current + FTS, one transaction ---
        drive_modified_time_at_conversion = drive_modified_time if is_drive_native else None
        with db.transaction(conn):
            conn.execute(
                "UPDATE conversions SET status = 'superseded' WHERE source_file_id = ? AND status = 'current'",
                (source_file_id,),
            )
            conn.execute(
                """
                INSERT INTO conversions
                    (source_file_id, job_id, version_number, output_path, status, source_type,
                     source_hash_at_conversion, drive_modified_time_at_conversion, conversion_tool,
                     converted_at, gauntlet_passed_at,
                     page_count, word_count, sheet_count, row_count_total)
                VALUES (?, ?, ?, ?, 'current', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_file_id, job_id, version, dest_rel_path, source_type,
                    source_hash, drive_modified_time_at_conversion, conversion_result.tool,
                    _now_iso(), _now_iso(),
                    frontmatter_extras.get("page_count"),
                    frontmatter_extras.get("word_count"),
                    frontmatter_extras.get("sheet_count"),
                    frontmatter_extras.get("row_count_total"),
                ),
            )
            conversion_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO conversions_fts (conversion_id, source_rel_path, output_path, body) VALUES (?, ?, ?, ?)",
                (conversion_id, rel_path, dest_rel_path, assembled),
            )
            conn.execute(
                "UPDATE conversion_jobs SET status = 'placing' WHERE id = ?", (job_id,),
            )

        # --- 9(c)/(d): lock and verify -- may raise; a caller-visible crash
        # here, or a False from verify_locked with no exception at all, both
        # leave the job at 'placing' rather than 'complete' --
        # resume_unlocked_conversions is what advances it from here.
        lock.apply_readonly_lock(final_path)
        confirmed = lock.verify_locked(final_path)

        with db.transaction(conn):
            if confirmed:
                conn.execute(
                    "UPDATE conversions SET locked_confirmed_at = ? WHERE id = ?", (_now_iso(), conversion_id),
                )
                conn.execute(
                    "UPDATE conversion_jobs SET status = 'complete', finished_at = ? WHERE id = ?",
                    (_now_iso(), job_id),
                )
            # else: leave status = 'placing'. reclaim_stale_jobs (Task 7)
            # already knows not to reset a 'placing' job back to 'pending'
            # once its conversion has landed -- only
            # resume_unlocked_conversions advances it further from here.
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=5)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def resume_unlocked_conversions(conn, cfg) -> list[int]:
    """Re-attempts lock+verify for any 'current' conversion whose write
    completed but whose lock was never confirmed -- never reconverts. Also
    advances the associated conversion_jobs row to 'complete' once the lock
    actually lands, since process_job deliberately left it at 'placing'."""
    rows = conn.execute(
        "SELECT id, output_path, job_id FROM conversions WHERE status = 'current' AND locked_confirmed_at IS NULL"
    ).fetchall()
    resumed = []
    for conversion_id, output_path, job_id in rows:
        final_path = cfg.converted_root / output_path
        if not final_path.exists():
            continue
        lock.apply_readonly_lock(final_path)
        if lock.verify_locked(final_path):
            now = dt.datetime.now(dt.timezone.utc).isoformat()
            with db.transaction(conn):
                conn.execute(
                    "UPDATE conversions SET locked_confirmed_at = ? WHERE id = ?", (now, conversion_id),
                )
                if job_id is not None:
                    conn.execute(
                        "UPDATE conversion_jobs SET status = 'complete', finished_at = ? "
                        "WHERE id = ? AND status != 'complete'",
                        (now, job_id),
                    )
            resumed.append(conversion_id)
    return resumed
```

Note the local-file branch now reads `source_hash`/`source_modified_at` from `local_content_hash`/`source_mtime` (renamed from the plain `source_hash`/`source_mtime` Task 15 used, since this version needs to choose between two different sources depending on branch) — this is the one behavior-preserving rename in the whole function; every local-file code path is otherwise identical to Task 15's version.

- [ ] **Step 7: Add a Drive-native worker test to `tests/test_worker.py`**

```python
def test_process_job_handles_a_gdoc_via_mocked_drive_export(conn, tmp_path):
    from unittest.mock import MagicMock

    from doc_ingest import frontmatter as frontmatter_mod
    from doc_ingest.config import Config

    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root)

    stub_path = input_root / "Session Notes.gdoc"
    stub_path.write_text('{"doc_id": "doc-1", "resource_key": "rk1", "email": "admin@freedom2beu.com"}', encoding="utf-8")
    sync.sync_source_files(conn, input_root)
    # Simulates drive_sync.sync_drive_metadata (Task 22) having already
    # populated this -- exercised directly by test_drive_sync.py; this test
    # only needs the column populated to prove process_job uses it, not the
    # full sync flow again.
    conn.execute("UPDATE source_files SET drive_modified_time = '2026-08-10T00:00:00Z' WHERE rel_path = 'Session Notes.gdoc'")
    conn.commit()
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")

    def _fake_export_google_doc(service, doc_id, dest_path, cfg_arg):
        from doc_ingest.convert import ConversionResult
        dest_path.write_bytes(b"# Exported directly as markdown\n\nplenty of real words here")
        return ConversionResult(success=True, markdown_body="# Exported directly as markdown\n\nplenty of real words here", tool="google-docs-export", error=None)

    mock_service_factory = lambda cfg_arg: MagicMock()
    with patch("doc_ingest.drive_client.export_google_doc", side_effect=_fake_export_google_doc), \
         patch("doc_ingest.lock.apply_readonly_lock"), \
         patch("doc_ingest.lock.verify_locked", return_value=True):
        worker.process_job(conn, job_id, cfg, worker_id="w1", drive_service_factory=mock_service_factory)

    job_row = conn.execute("SELECT status, failure_reason FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row[0] == "complete", job_row[1]
    conversion = conn.execute(
        "SELECT source_type, conversion_tool, drive_modified_time_at_conversion, output_path "
        "FROM conversions WHERE job_id = ?", (job_id,)
    ).fetchone()
    assert conversion[:3] == ("gdoc", "google-docs-export", "2026-08-10T00:00:00Z")

    # source_modified_at must be the Drive edit time, NOT the static local
    # stub's own filesystem mtime (spec §4 step 3, §7).
    output_file = output_root / "converted" / conversion[3]
    fm, _ = frontmatter_mod.parse(output_file.read_text(encoding="utf-8"))
    assert fm["source_modified_at"] == "2026-08-10T00:00:00Z"


def test_process_job_handles_a_gdoc_docx_fallback_export(conn, tmp_path):
    """Proves the docx-fallback filename fix: export_google_doc writes docx
    bytes to a path initially named export.md (it doesn't know the format
    ahead of time); _convert_drive_native must rename it to export.docx
    before treating it as a real docx (independent word-count reader, and
    the file/content-type sent to firecrawl must agree)."""
    from unittest.mock import MagicMock

    import docx as docx_lib

    from doc_ingest.config import Config

    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root)

    stub_path = input_root / "Long Session Notes.gdoc"
    stub_path.write_text('{"doc_id": "doc-2", "resource_key": "rk2", "email": "admin@freedom2beu.com"}', encoding="utf-8")
    sync.sync_source_files(conn, input_root)
    conn.execute("UPDATE source_files SET drive_modified_time = '2026-08-10T00:00:00Z' WHERE rel_path = 'Long Session Notes.gdoc'")
    conn.commit()
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")

    def _fake_export_google_doc(service, doc_id, dest_path, cfg_arg):
        from doc_ingest.convert import ConversionResult
        document = docx_lib.Document()
        document.add_paragraph("word " * 50)
        document.save(dest_path)  # written to a path still named export.md
        return ConversionResult(success=True, markdown_body=None, tool="google-docs-export-docx-fallback", error=None)

    def _fake_convert(staged_path, source_type, cfg_arg):
        from doc_ingest.convert import ConversionResult
        assert staged_path.suffix == ".docx"  # the rename must have already happened
        assert source_type == "docx"
        return ConversionResult(success=True, markdown_body="word " * 50, tool="firecrawl-parse", error=None)

    mock_service_factory = lambda cfg_arg: MagicMock()
    with patch("doc_ingest.drive_client.export_google_doc", side_effect=_fake_export_google_doc), \
         patch("doc_ingest.worker._convert", side_effect=_fake_convert), \
         patch("doc_ingest.lock.apply_readonly_lock"), \
         patch("doc_ingest.lock.verify_locked", return_value=True):
        worker.process_job(conn, job_id, cfg, worker_id="w1", drive_service_factory=mock_service_factory)

    job_row = conn.execute("SELECT status, failure_reason FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row[0] == "complete", job_row[1]
    conversion = conn.execute(
        "SELECT source_type, conversion_tool, word_count FROM conversions WHERE job_id = ?", (job_id,)
    ).fetchone()
    assert conversion == ("gdoc", "google-docs-export-docx-fallback", 50)
```

Run the worker suite to verify both new tests pass:

```bash
cd doc-ingest-app && python -m pytest tests/test_worker.py -v
```

Expected: 9 passed (Task 15's 7 plus these 2).

- [ ] **Step 8: Wire the Drive-check step into `run_ingest_cron.py`'s `run_once`** (Task 16)

```python
# Add this import to scripts/run_ingest_cron.py
from doc_ingest import drive_client, drive_sync

# Insert between the "scan" and "enqueue" blocks inside run_once's try block:
        try:
            service = drive_client.build_default_service(cfg)
            drive_updated = drive_sync.sync_drive_metadata(conn, service, cfg)
            print(f"drive check: updated {drive_updated} gdoc/gsheet row(s)")
        except Exception as exc:
            # Missing/expired Drive credentials (e.g. SETUP.md's one-time
            # consent hasn't been done yet on this machine) must not block
            # local-file processing -- log and continue with whatever
            # local-file jobs are ready.
            print(f"drive check skipped: {exc}", file=sys.stderr)
```

- [ ] **Step 9: Run the full app-level suite**

```bash
cd doc-ingest-app && python -m pytest -v
```

Expected: every test from Tasks 0–22 passes.

- [ ] **Step 10: Commit**

```bash
git add doc-ingest-app/doc_ingest/drive_sync.py doc-ingest-app/tests/test_drive_sync.py doc-ingest-app/doc_ingest/jobs.py doc-ingest-app/tests/test_jobs.py doc-ingest-app/doc_ingest/drive_client.py doc-ingest-app/doc_ingest/worker.py doc-ingest-app/tests/test_worker.py doc-ingest-app/scripts/run_ingest_cron.py
git commit -m "feat(doc-ingest): wire Drive metadata sync and gdoc/gsheet export into the worker and cron"
```

---

## Self-Review

**This is the third pass.** Two prior review rounds found defects in this plan; both sets were fixed in place, and the fixes are part of the tasks above, not a separate patch list.

**Round 1** (12 blocking defects) covered: `config.py`'s type coercion being dead code under `from __future__ import annotations` (fixed with `typing.get_type_hints`, Task 1); the long-path shortener growing paths instead of shrinking them for short segments (Task 4); `lock.py` applying the read-only attribute after an ACL deny that blocks that very operation, and denying only the account's own SID rather than also the OWNER RIGHTS SID (Task 13); Gate 1 reading output-side metadata keys nothing produced (Task 11); `worker.py` `KeyError`-ing on every extensionless PDF (Task 15); the entire Google Drive path being unwired (Task 22, new); and `convert.py` shelling out to a `firecrawl` CLI that isn't installed on this machine (switched to the `firecrawl-py` SDK, Task 9).

**Round 2**, run after round 1's fixes landed, found that several of those fixes had their own bugs, plus gaps round 1 didn't reach:

- Six of Gate 1's own docx/xlsx tests (Task 11) couldn't pass — the size-ratio-floor check added in round 1 fired before the parity checks those tests were named for, on tiny synthetic bodies against a large `source_size_bytes`. Fixed by disabling the floor (`size_ratio_floor=0.0`) in each test's own `Config(...)`, isolating the check actually under test.
- Task 22's Drive-native branch set `source_hash = drive_modified_time` for the frontmatter field, but `enqueue_pending_jobs` still compared that same DB column (`source_hash_at_conversion`) against a sha256 hex digest for local files — for a gdoc row, a hex digest is never equal to an ISO timestamp, so `needs_job` was unconditionally `True` and every `.gdoc`/`.gsheet` would get a new locked version on every 30-minute wake, forever. Fixed by branching `enqueue_pending_jobs` on `classification` (Task 7): `convertible` rows compare `content_hash`, `gdoc_pointer` rows compare `drive_modified_time_at_conversion` only, never both. The regression test this bug hid behind (seeded a `conversions` row with `source_hash_at_conversion` left `NULL`, so a `None`-comparison masked the real defect) was rewritten with a genuine negative case.
- `jobs.heartbeat` (Task 7) was fully implemented and tested in isolation but never actually called from `process_job` — a real conversion running longer than `cfg.reclaim_staleness_threshold_s` (180s) would have been reclaimed by `reclaim_stale_jobs` out from under its own still-running worker. Fixed with a real heartbeat thread, on its own connection, wrapped in a `try`/`finally` that covers every return path (Task 15).
- `lock.py`'s own crash-recovery path was broken by its own round-1 fix: `apply_readonly_lock`'s resume case re-ran `os.chmod`, which the already-applied account-level `WriteAttributes` deny then blocked. Fixed by skipping the chmod when the read-only attribute bit is already set (Task 13).
- `drive_client.build_default_service` (Task 22) would have opened an interactive OAuth browser flow if called with no cached token — inside the unattended cron, wedging every subsequent 30-minute wake under Task Scheduler's skip-if-running default. Fixed to raise immediately instead, pointing at `SETUP.md`'s one-time manual step.
- The Drive docx-fallback export wrote real DOCX bytes to a file named `export.md` (Task 22) before handing it to firecrawl with a mismatched filename/content-type pairing. Fixed by renaming to `export.docx` once the fallback is known to have happened.
- Task 21's integration test hadn't been updated for any of round 1's changes — still patched `subprocess` (dead since Task 9's SDK switch), performed real ACL locks under `tmp_path` (which Task 13's own design says only Task 13's and Task 21's dedicated real-lock tests may do), and used fixture bodies that would trip Gate 1's own checks. Rewritten to mock `firecrawl.Firecrawl` and `lock.*`, and to size per-type mock output against each real fixture file. The dedicated real-lock test in `test_readonly_enforcement.py` was switched from `tmp_path` to `lock_test_dir`.
- Smaller fixes: `gdoc` frontmatter's `source_modified_at` now uses `drive_modified_time`, not the static local stub's mtime (Task 22); `naming.long_path` implements the `\\?\`-prefix backstop spec §6 describes, wired into the one call site where Python's `open()` reliably honors it (Task 4/22); the conftest network guard now blocks `requests`/`httpx`, not just `urllib` (Task 0); `manifest.regenerate` now runs after the drain loop, not before it, so it isn't always one run stale (Task 18); Gate 2 re-verifies path length after a collision suffix is appended, in case the suffix itself pushed it over budget (Task 12); `scan.walk_source_tree` no longer hashes `catalog_only`/`excluded_media`/`blocked_unknown` files, so the 60 videos (up to 1.1GB each) in the real corpus aren't sha256'd every wake for a value nothing reads (Task 5); `init_db` now calls `apply_migrations` (Task 3); `read_docx_word_count` now includes table cell text, matching what the output-side parity check actually counts (Task 8).

**Spec coverage** — every numbered spec section maps to a task:

| Spec section | Task(s) |
|---|---|
| §1 Purpose, gitignore | Task 0 |
| §2 Source data (sniffing, census) | Task 5 |
| §3 Architecture | File Structure (all tasks) |
| §4 Data flow steps 1–9 | Tasks 6, 7, 15, 16, 22 |
| §5 Concurrency model | Tasks 2, 7 |
| §6 Storage & naming | Task 4, Task 12 (full absolute-path threading) |
| §7 Frontmatter | Task 10, Task 15 (`_frontmatter_extras`) |
| §8 The gauntlet | Tasks 11, 12 |
| §9 Google Drive/Docs API | Tasks 14, 20, 22 |
| §9a Source deletion | Task 6 (`missing` classification), Task 18 (`query.py` default exclusion) |
| §10 Read-only enforcement | Tasks 13, 19 |
| §11 Cron | Tasks 16, 17 |
| §12 Indexing | Tasks 2 (FTS5 schema), 18 |
| §13 Testing | every task's own test + Task 21; the mtime-vs-modifiedTime regression test spec §13 names explicitly is Task 22 |
| §14 Out of scope | no task implements OCR, UI, domain frontmatter, image/video conversion — confirmed absent by design |
| §15 Open items | resolved concretely where possible: Task 1 (tolerances/timeouts as config), Task 5 (magic-byte approach), Task 22 (Drive batch mechanism — `BatchHttpRequest`), Task 4 (long-path shortening implementation, including the `\\?\` backstop). Two items are resolved as far as this plan can take them and explicitly left open rather than faked: Task 22's `source_hash`-via-`headRevisionId` stand-in and the direct-markdown gdoc word-count check (see that task's "two open items" note) — both need a live Drive API check this plan can't perform. Neither is load-bearing for correctness as of round 2's fixes: `source_hash_at_conversion` is no longer read for `gdoc_pointer` rows at all (`enqueue_pending_jobs` branches on classification and uses `drive_modified_time_at_conversion` instead), so the stand-in's imprecision no longer risks the infinite-reconversion bug round 2 found and fixed — it only means the frontmatter's displayed `source_hash` field is a timestamp rather than a true content hash for this one source type. |

**Placeholder scan** — no `TBD`/`TODO`/"add appropriate handling" strings appear anywhere above; every step has real code or a real command. Task 22's two explicitly-named open items are a documented gap, not a placeholder — they state exactly what's missing and why, per the "honestly flagged as a gap" standard this repo's own CLAUDE.md sets for the corpus skills.

**Type consistency** — re-verified end to end this pass, after the first pass's version of this claim turned out to be wrong (the file structure section's `run_gate1`/`run_gate2` signatures didn't match what Tasks 11/12 actually defined, and `metadata_readers.read_independent_metadata` was cited but never existed). The File Structure section's "Interfaces contract" block above is now the corrected, authoritative version — every signature there was copied from the task that defines it, not paraphrased. Cross-checked this pass: `Config` field names (Task 1) against every later usage, including the removal of `firecrawl_binary` after Task 9's SDK switch; `naming.build_dest_rel_path`'s new `prefix_len` parameter (Task 4) against its one caller (Task 12); `convert.convert_local_file`'s signature change (dropped `output_tmp_path`, Task 9) against its callers in Task 15 and Task 22; `GauntletResult`/`ConversionResult` used identically everywhere they're returned or consumed; `jobs.enqueue_pending_jobs`'s classification filter (Task 7, extended by Task 22) against `sync.py`'s classification vocabulary (Task 5/6); `worker.process_job`'s new `drive_service_factory` parameter (Task 22) against its test call sites.

**One implementation-level addition beyond the spec's literal text**, flagged here for visibility rather than buried in a task: `conversion_jobs.source_hash_at_attempt` / `drive_modified_time_at_attempt` (Task 2's schema, used by Task 7's enqueue skip-logic) prevent a deterministic gauntlet failure (e.g. a scanned PDF) from being re-enqueued and re-attempted every 30 minutes forever. The spec's §8 "quarantine, don't discard" principle covers *what* happens to a failure (it's recorded, queryable, never silently dropped); this addition covers *how often* a failure that can't succeed gets retried, which the spec didn't address directly. Also worth surfacing again here: Task 7's `reclaim_stale_jobs` was extended (during this pass, prompted by Task 15's crash-recovery design) to skip resetting a `'placing'` job back to `'pending'` when its conversion has already landed — otherwise a slow lock-confirmation would trigger a wasted reconversion of a source that's already correctly converted.

---

## Execution Deviations (subagent-driven-development runtime)

Findings surfaced by task reviewers during actual execution, where the defect traced
back to this plan's own verbatim prescribed code (not implementer judgment). Per the
runtime process: Critical/Important findings that conflict with plan text are fixed
in place rather than shipped as documented, and logged here before and after
resolution so the delivered code and this plan don't silently diverge.

**Task 1 (Config module) — `load_config`'s YAML-merge line (originally this plan's
own Step 3, line ~162: `values[key] = _coerce(key, str(value)) if not
isinstance(value, (int, float)) or _FIELD_TYPES[key] is Path else value`) had two
bugs:** an unknown/typo'd YAML key was silently dropped with no error, and a YAML
numeric scalar whose native type didn't match the field's declared type (e.g.
`worker_pool_size: 8.5` for an int field) was never coerced, leaving `Config` with a
wrongly-typed field. Both are load-bearing since `Config` is imported by every module
from Task 6 onward. **Resolved:** unknown keys now raise `ValueError` naming the file
and key; every present key is routed through `_coerce()` unconditionally (dropping
the isinstance branch that bypassed coercion for already-numeric YAML values). Fix
commit: `846f651`. Reviewed clean in the scoped re-review (both findings ADDRESSED,
no new Critical/Important breakage — one Minor note: `int(float(raw))` has a
precision-loss ceiling above 2^53 that no current field's range approaches).

**Task 3 (`transaction()` boundary) — the `_TXN_DEPTH` dict (originally this plan's
own Step 3, keyed by `id(conn)`, entries reset to 0 but never deleted) has a latent
commit-skipping hazard:** if a connection is ever abandoned mid-transaction (depth >
0) and CPython later reuses that exact `id()` for a new `sqlite3.Connection`, the new
connection would silently inherit the stale nonzero depth and skip `BEGIN`/`COMMIT`
on its first `transaction()` call — writes would go through uncommitted, with no
error. Not reachable by any call site this plan defines today, but `transaction()` is
used by every DB-writing task from here on. **Resolved:** `sqlite3.Connection` turned out not to be weak-referenceable in Python
3.14 (`weakref.ref()` raises `TypeError`), so the fix uses explicit `del
_TXN_DEPTH[key]` on both the success and exception exit paths, guarded to fire only
when nesting depth returns to 0 (nested exits still skip it, preserving the join
behavior `test_transaction_nests_without_committing_early` checks). Fix commit:
`0dae079`. Reviewed clean in the scoped re-review (finding ADDRESSED, no new
Critical/Important breakage — two Low test-quality nitpicks: an unused local in the
new regression test, and the test's "id() reuse" framing doesn't actually force a
recycled id() since `conn1` stays in scope, though it still correctly proves the
core defect — permanent dict-entry accumulation — is fixed).

**Task 7 (`jobs.py`) — `test_claim_deterministically_excludes_a_second_connection`
(originally this plan's own Step 1 test code) created `conn_a`/`conn_b` in the main
thread but used each inside a separate worker thread (`_claim_a`/`_claim_b`).**
`db.get_connection` deliberately keeps `check_same_thread=True` (Task 2/3's own
documented choice — this app's concurrency model is DB-claimed via `BEGIN IMMEDIATE`,
so cross-thread connection reuse should fail loudly, not be silently permitted), so
the test's own connections hit `sqlite3.ProgrammingError` at the first cross-thread
`execute()` call — a deterministic failure, not flakiness, caught by the implementer
before review. The sibling test in the same file
(`test_two_connections_racing_one_pending_job_only_one_wins`) already used the
correct pattern (create/use/close the connection entirely inside its owning thread).
**Resolved:** restructured the one test to match — `conn_a`/`conn_b` are now created
and closed entirely inside `_claim_a`/`_claim_b`, never touched from the main thread
or the other thread. No change to `db.py` or `jobs.py` production code; this was a
test-only bug in the plan's own prescribed test. Fix commit: `4500130` (same commit
as Task 7's implementation — the bug was caught before the first commit, not in a
post-review fix round). 19/19 `test_jobs.py` passed across 3 consecutive runs, no
flakiness; full suite 76/76.

**Task 0/9 (`requirements.txt`'s `firecrawl-py` pin) — Task 0 pinned `firecrawl-py==2.*`,
but Task 9's entire brief (`Firecrawl` class, `.parse()` method,
`firecrawl.v2.types.ParseOptions`) is written against an API that does not exist in
the 2.x line at all.** Confirmed empirically before dispatching Task 9: the installed
2.16.5 has no `Firecrawl` attribute (`from firecrawl import Firecrawl` raises
`ImportError`), no `firecrawl.v2` submodule, and its top-level API is the older
`FirecrawlApp`/`ScrapeOptions`-shaped surface. Side-loaded `firecrawl-py==4.35.0` into
an isolated scratch directory to confirm the brief's exact imports
(`Firecrawl`, `firecrawl.v2.types.ParseOptions`, `Firecrawl.parse(..., options=...)`,
`Document.markdown`) all exist and match from 4.x onward — `ParseOptions` is a
`ScrapeOptions` subclass, so it satisfies `parse()`'s declared parameter type.
Every one of Task 9's own tests would have failed immediately regardless of
implementation quality, since `mock.patch("firecrawl.Firecrawl")` itself raises
`AttributeError` against a package with no such class. Also surfaced in the same
investigation: the plan's Global Constraint that `doc-ingest-app/` gets its "own
venv" was never actually honored by Task 0 — there is no `doc-ingest-app/.venv`, so
every dependency in `requirements.txt` installs into this machine's shared,
non-project-scoped Python environment. **Resolved:** per the human partner's explicit
choice (bump the shared environment rather than retroactively create an isolated
venv), `requirements.txt`'s pin was changed to `firecrawl-py==4.*` and the shared
environment's installed package was upgraded via `pip install --upgrade
"firecrawl-py==4.35.*"` to 4.35.0, verified importable (`Firecrawl`, `ParseOptions`)
before Task 9 was dispatched. No other part of this repo depends on the `firecrawl-py`
pip package (confirmed by a repo-wide grep) — `pipeline-app`'s own Firecrawl usage
goes through a separate MCP server, not this pip package, so this upgrade's blast
radius stays contained to `doc-ingest-app` in practice, even without an isolated venv.
The "own venv" gap itself remains open — noted here rather than silently left
undiscovered, but out of scope to retroactively fix under this decision.

**Task 11 (`gauntlet.py` Gate 1) — the word-count-parity and row-count-parity checks
(originally this plan's own Step 3 code) used truthy guards (`if source_wc:`,
`if source_rows:`) instead of `is not None`,** silently SKIPPING the check whenever
the source-side value from `independent_metadata` is legitimately `0` — a docx with
`source_word_count: 0` or an xlsx with `source_row_count: 0` would pass Gate 1's
parity check as a no-op rather than being evaluated. `source_table_count`/
`source_sheet_count` in the same function already used `is not None` correctly, so
this was an inconsistency within the brief's own code, not a wholesale design choice.
`page_count`'s truthy guard was deliberately left unchanged — it gates a division
(`len(body.split()) / page_count`), so a legitimate `page_count == 0` would raise
`ZeroDivisionError` if the guard were simply widened; that guard was already correct
for its own reason. **Resolved:** `source_wc`'s and `source_rows`'s guards changed to
`is not None`; two new tests added proving a literal `0` source value now correctly
triggers `word_count_parity_failed`/`row_count_mismatch` instead of silently passing.
Fix commit: `df862a1`. Reviewed clean in the scoped re-review (finding ADDRESSED,
`page_count` confirmed untouched, no new breakage; 19/19 gate1 tests, 112/112 full
suite).

**Task 12 (`gauntlet.py` Gate 2) — `test_gate2_logs_a_collision_and_appends_a_hash_suffix`
(originally this plan's own Step 1 test code) seeded two `conversions` rows for the
SAME `(source_a, version=1)` pair,** violating the schema's
`UNIQUE(source_file_id, version_number)` constraint — and directly contradicting the
test's own comment, which says the collision-occupying row should be seeded "under a
DIFFERENT source_file_id" but the code as written reused `source_a` for both rows.
Caught by the implementer before committing, not by review. **Resolved:** the
collision-occupying row is now seeded under a third, distinct source file
(`source_c`), matching the comment's stated intent and the working pattern already
used by the adjacent threshold test. `run_gate2` production code is untouched by this
fix — the bug was entirely in the brief's own test fixture. Same commit as Task 12's
implementation (`7a5ee5f`), since the bug was caught before the first commit, not in
a post-review fix round.

**Task 13 (`lock.py`) — the plan's own flagged empirical unknown resolved cleanly.**
Task 13's Step 6 explicitly flagged that the OWNER RIGHTS (`S-1-3-4`) deny-ACE
mechanism (denying `WRITE_DAC` to the well-known OWNER RIGHTS SID, closing the
"same account resets its own lock via `icacls /reset`" hole) was unverified on a real
machine — Microsoft's own documentation describes `S-1-3-4` as a target for an
**allow** ACE with restricted rights, not an explicit **deny**, so it was genuinely
uncertain whether the deny form would actually hold. Verified empirically during this
task's execution: it does. `test_owner_rights_deny_actually_closes_the_self_reset_hole`
passed on the first run — `icacls /reset` against a fully-locked file returns exit
code 5 ("Access is denied"), the ACL is left unchanged, and a direct write attempt
raises `PermissionError`, confirmed both via pytest and by hand. The documented
fallback (`icacls <path> /grant *S-1-3-4:(RX)`) was NOT needed — the deny-form
mechanism as originally specified in Task 13's Step 5 code shipped unchanged.
Separately, one test's assertion (`test_icacls_output_shows_the_owner_rights_deny_entry`)
hardcoded a literal `"S-1-3-4"` string match, but this Windows build's `icacls` output
resolves that SID to its display name `"OWNER RIGHTS"` instead — widened to accept
either form, mirroring `verify_locked()`'s own pre-existing dual-form logic. Caught
and fixed before committing, not a review finding; unrelated to the flagged empirical
unknown itself.

**Task 18 (`query.py`) — an environment-dependent SQL bug in the brief's own code.**
`query.search`'s text-search branch used `WHERE f MATCH ?`, referencing the
`conversions_fts` table's FROM-clause alias `f` inside the `MATCH` clause. On this
environment's SQLite (3.50.4), that raises `sqlite3.OperationalError: no such column:
f` — FTS5's `MATCH` operator needs the real (unaliased) virtual-table name in this
version, not an alias assigned elsewhere in the same query. Caught by the implementer
before committing, not by review. **Resolved:** changed to `WHERE conversions_fts
MATCH ?` (the real table name). Independently reproduced and verified correct by the
task reviewer using a throwaway in-memory SQLite DB with the exact join shape:
`EXPLAIN QUERY PLAN` confirmed the fixed query still resolves against the same
FROM-clause table instance (aliased `f` elsewhere in the query) via the FTS index —
correct join selectivity, no cartesian-product risk, no silent wrong-result behavior.
Also consistent with the bare-`conversions_fts MATCH` idiom already used elsewhere in
this codebase (`tests/test_db.py`, `tests/test_worker.py`). Same commit as Task 18's
implementation (`4fd96f7`), since the bug was caught before the first commit.

**Task 19 (Claude Code `PreToolUse` hook) — two rounds of findings, both plan-mandated,
both traced to the brief's own verbatim `.claude/hooks/protect_freedom2beu_output.py`.**

*Caught by the implementer before the first commit:* `_WRITE_VERB_RE`'s trailing `\b`
never matches immediately after the symbolic operators `>`/`>>`, since both the
operator and what follows (whitespace or end-of-string) are non-word characters —
there's no word/non-word transition for `\b` to anchor on. `test_looks_like_a_write_
command_flags_redirection_into_converted`'s `>` case failed. Fixed to a trailing
`(\s|$)` boundary (works uniformly for symbolic and word-like verbs), `>>` reordered
before `>` in the alternation, and a regression test for the `>>` (append) case added.

*Found by the task reviewer:* three further Important gaps in the same file.
1. NotebookEdit protection was dead code — `main()` only ever read `tool_input.
file_path`, but the real `NotebookEdit` tool's payload uses `notebook_path`, so the
check always saw `None` and silently allowed every NotebookEdit call regardless of
path, even though `decide()` and the `.claude/settings.json` matcher both name
`NotebookEdit` as in scope.
2. `decide()`'s path-prefix comparison (`rel.parts[:2] != _PROTECTED_PREFIX`) was
case-sensitive, but `Path.relative_to()` itself is case-insensitive on this Windows
machine — so a differently-cased path (`Freedom2BeU/CONVERTED/x.md`) resolved fine
but then silently failed the literal tuple compare and was allowed. Inconsistent with
the Bash/PowerShell regex path, which already correctly used `re.IGNORECASE`.
3. `_WRITE_VERB_RE` omitted `cp`/`mv` — PowerShell's own default aliases for the
already-in-scope `Copy-Item`/`Move-Item` — in a repo whose actual shell environment is
PowerShell-primary.

**Resolved:** (1) `file_path` resolution now falls back to `tool_input.notebook_path`
when `file_path` is absent; verified end-to-end via two new tests that invoke the
hook script as a real subprocess with a JSON payload piped to stdin (the hook's
actual real-world invocation contract), asserting the correct exit code for both a
protected and an unprotected `NotebookEdit` path. (2) the path-prefix comparison now
lowercases both sides before comparing. (3) `cp`/`mv` added to the verb alternation,
verified by hand-trace that the existing `(^|\s)...(\s|$)` boundary structure
correctly rejects a substring false-positive like `cpu_report.md` (the `cp` inside it
is preceded by no word/start boundary the pattern accepts). Fix commit: `98c16f5`
(building on `b5de57e`). Reviewed clean in the scoped re-review — all three findings
ADDRESSED, no new Critical/Important breakage; one Low-severity test-intent nit noted
(a test comment claims to exercise the `mv`-substring boundary but its fixture string
doesn't actually contain that substring — the regex logic itself was independently
verified correct, so this is a documentation mismatch in the test, not a functional
gap) — deferred to the ledger, non-blocking.

**Task 15 (`worker.py`) — a dedicated integration review (Opus) found two Important,
plan-mandated findings, both robustness gaps at the module's exception boundaries.**
1. `process_job` (originally this plan's own Step 3 code) had NO exception handling
anywhere in its pre-write section (staging, `_convert`, independent metadata, Gate 2,
frontmatter build, Gate 1) — only the outer `finally` (heartbeat stop, tmp_dir
cleanup) wrapped it, with no `except`. Any uncaught exception there (a corrupt/
encrypted source file that `metadata_readers` can't parse, an unmapped extension's
`KeyError`, a staging I/O error) left the job stuck at `'converting'` forever:
`reclaim_stale_jobs` resets it to `'pending'`, it's re-claimed, crashes identically —
an unbounded poison-pill loop that burns a real, billed firecrawl `.parse()` call
every iteration (since `_convert` runs before the failure point in most triggers),
and the job never reaches `'failed'`, so `enqueue_pending_jobs`'s already-failed-at-
this-version guard — the only backstop against retry loops in the whole design —
never engages.
2. `resume_unlocked_conversions` had no per-row error isolation — `lock.
apply_readonly_lock`'s `check=True` means any icacls failure raises `CalledProcessError`,
which escaped the `for` loop entirely, aborting the whole sweep and permanently
disabling crash-recovery for every OTHER unlocked conversion (not just the failing
one) until manual intervention. This is the module that exists specifically to BE
the crash-recovery mechanism, so one poisoned row taking down recovery for
everything else was disproportionate to the mandate.

**Resolved, both scoped carefully to preserve existing test semantics:** (1) a new
inner `try/except Exception` wraps ONLY the pre-write section (from source-type
resolution through Gate 1), converting any unexpected exception to a clean
`_fail_job(conn, job_id, f"unexpected_error: {exc}")` call — the post-write (write →
commit → lock → verify) section's behavior is UNCHANGED: an exception from `lock.
apply_readonly_lock` still propagates out of `process_job` uncaught, exactly as
`test_process_job_resumes_lock_only_after_a_simulated_crash` already required and
continues to require (a regression tripwire duplicating this assertion was also
added). (2) each row's lock attempt in `resume_unlocked_conversions` is now isolated
in its own `try/except`, logging an `events` row (`event_type='resume_lock_failed'`)
on failure and continuing to the next row rather than aborting the sweep. Fix commit:
`c41506e`. Reviewed clean in the scoped re-review (both findings ADDRESSED — the
re-review specifically hand-traced the exception-boundary indentation to confirm the
post-write section is genuinely outside the new handler, and confirmed a second row
genuinely succeeds after the first raises — no new Critical/Important breakage).

Two Low/non-blocking notes from the re-review, both inherent trade-offs of the
mandated fix shape rather than defects, deferred to the ledger for final-review
triage: (a) a *transient* pre-write error (e.g. a momentary `database is locked` past
the busy_timeout under concurrent workers) is now also permanently marked `'failed'`
at that source-file version rather than being retried on the next wake — this
trade is inherent to closing the unbounded-retry hole, and a future refinement could
carve out known-retryable exception types; (b) `resume_lock_failed` events accrue
unboundedly on a persistently-broken lock (one row per wake, no backoff/dedup) — this
is exactly what the finding specified ("log and continue"), noted only as an
operational consequence for whoever eventually owns events-table retention. The
re-review also flagged one out-of-scope observation for Task 22, not a defect in this
fix: `.gdoc`/`.gsheet` files still get a fresh `'failed'` `conversion_jobs` row every
30-minute wake until Task 22 wires Drive metadata sync (since `drive_modified_time`
stays NULL until then, so the already-failed-this-version guard's gdoc branch never
matches) — costly in DB-row accumulation but NOT in billed API calls, since
`_source_type_for` raises before `_convert` is ever reached.

**Task 13 (`lock.py`) — a dedicated security-focused review (Opus) found two Important,
plan-mandated findings in `verify_locked()` (originally this plan's own Step 5 code).**
1. `verify_locked()` scanned the WHOLE icacls stdout — including the echoed file path
itself, before any ACE line — for two completely uncorrelated substrings
(`"S-1-3-4"`/`"OWNER RIGHTS"` and `"DENY"`, matched anywhere, not required on the same
line). A real, user-controlled Drive document title containing both substrings could
false-positive `verify_locked()` as `True` on the crash-resume path (read-only
attribute set, no ACL call has actually landed yet) — silently recording a file as
locked while it carries zero real ACL protection. Silent UNDER-locking of real client
data is the dangerous direction of this class of bug.
2. No test in the 7-test suite pinned the mandated ACCOUNT-level deny call (the first
of the two required icacls calls) — a regression that deleted it would have passed
every existing test, since the OWNER RIGHTS deny alone satisfies every assertion in
the brief's own test file.

**Resolved:** `verify_locked()` now strips the echoed path prefix from icacls output
before scanning, then requires the OWNER-RIGHTS token and a parenthesized `(DENY)`
marker to co-occur on the SAME line (not just anywhere in the output) — closing the
uncorrelated-substring hole. One deviation from the reviewer's literal suggested
implementation ("skip the first output line"): real icacls output concatenates the
echoed path and the FIRST real ACE onto one line, so naive line-skipping would have
discarded that ACE and produced a permanent false-negative instead of fixing the
false-positive; prefix-stripping achieves the same correlation guarantee without
losing ACE coverage — verified correct by the re-review's own hand-trace of the
adversarial scenario (a path containing both an OWNER-RIGHTS-like token and a
`(DENY)`-like substring). A new test assertion pins the account-level deny (`assert
f"{account.upper()}:(DENY)" in result.stdout.upper()`). Fix commit: `53f6501`.
Reviewed clean in the scoped re-review (both findings ADDRESSED, no new
Critical/Important breakage). Two Low/non-blocking notes deferred to the SDD ledger
for the final whole-branch review to triage: (a) the prefix-strip fails *open* (falls
back toward the old broad-scan behavior) if the echoed path doesn't byte-match
`str(path)` — realistically triggerable only by an OEM/ANSI codepage mismatch on a
non-ASCII filename, not by content; a cheap structural fix exists (match the
contiguous substring `"OWNER RIGHTS:(DENY)"`/`"S-1-3-4:(DENY)"` directly, since `:` is
one of the nine characters `naming.sanitize_component` always strips, so no real
filename can ever contain it — this would remove the prefix-strip dependency
entirely); (b) the fix report's own adversarial-filename repro doesn't actually
exercise the new code path it's offered as evidence for (evidence-quality gap only,
not a code defect — the re-review's own independent hand-trace is what actually
confirms the fix).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-13-freedom2beu-doc-ingest-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
