# Local Pipeline Control App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-only FastAPI/htmx app (`pipeline-app/`) that walks a ContentStudio Short
through the six generic skills plus the RGS grounding stage, with enforced per-stage gating, a
real chat interface backed by headless `claude -p`, versioned artifacts, and a skill viewer/editor.

**Architecture:** FastAPI backend (server-rendered Jinja2 + htmx, no JS build step) drives the
`claude` CLI in headless mode as a subprocess per chat turn, streaming `stream-json` events to the
browser over SSE while durably logging them to `events/*.jsonl`. SQLite is the single source of
truth for project/stage/turn state; the filesystem (`runs/<run_id>/NN-<stage>/artifact.vN.md`)
holds versioned artifact content, per the existing (approved, unimplemented)
`2026-07-25-eval-and-io-boundaries-design.md` layout, minus its ACL-locking/hook/eval machinery.

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, Jinja2, htmx, PyYAML, `markdown`, SQLite
(stdlib `sqlite3`), pytest, pytest-asyncio, httpx (test client only).

## Global Constraints

- The app binds to `127.0.0.1` only — never `0.0.0.0`, never deployed or hosted.
- Every `claude` CLI invocation uses `--allowedTools "Read,Glob,Grep,Write,Edit"` — **Bash is
  never included**, and `cwd` is always the ContentStudio repo root.
- Only one `claude` CLI turn runs at a time, app-wide (global single-flight lock) — matches how a
  single local user actually works.
- Artifact content is **never mutated in place**, with exactly one exception: the one-time
  "approve" stamp (`status: final`, `finalized_at`) on the current version file. Any further
  content change always creates a new `artifact.v{N+1}.md`.
- SQLite (`pipeline-app/pipeline.db`, gitignored) is the single source of truth for all dynamic
  state (projects, stages, turns) — no parallel `project.json` or `manifest.yaml`.
- `runs/` (repo root, gitignored) holds per-project artifacts; `pipeline.yaml` (repo root,
  git-tracked) holds static pipeline topology; `rgs-briefs/` (existing, git-tracked) keeps its
  current convention untouched — the grounding stage never duplicates its content into `runs/`.
- Skill-content edits (`SKILL.md`/`references/`) write directly to `.claude/skills/` and
  auto-commit; kickoff-template edits write to `pipeline-app/stage_templates/` with no commit.
- Every run/read/write path treats Windows as the primary target platform (this project is
  developed on Windows) — no POSIX-only assumptions (e.g. `os.fork`, POSIX-only path separators).

---

## Task 1: Project scaffolding, `pipeline.yaml` topology, and the topology loader

**Files:**
- Create: `pipeline-app/requirements.txt`
- Create: `pipeline-app/README.md`
- Create: `pipeline-app/pipeline_app/__init__.py`
- Create: `pipeline-app/pipeline_app/pipeline_config.py`
- Create: `pipeline.yaml` (repo root)
- Modify: `.gitignore` (repo root)
- Test: `pipeline-app/tests/test_pipeline_config.py`

**Interfaces:**
- Produces: `StageDef` dataclass (`id`, `skill`, `dir_prefix`, `depends_on: list[str]`,
  `brand_scope: str | None`); `load_topology(path: Path) -> list[StageDef]`;
  `stage_dir_name(stage: StageDef) -> str`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_pipeline_config.py`:

```python
from pathlib import Path

from pipeline_app.pipeline_config import load_topology, stage_dir_name

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_load_topology_has_seven_stages():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    assert len(stages) == 7
    ids = [s.id for s in stages]
    assert ids == [
        "grounding", "ideation", "scripting", "voiceover", "visual", "assembly", "repurpose",
    ]


def test_scripting_depends_on_ideation():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    scripting = next(s for s in stages if s.id == "scripting")
    assert scripting.depends_on == ["ideation"]
    assert scripting.skill == "shorts-scripting"


def test_voiceover_and_visual_are_a_parallel_pair():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    voiceover = next(s for s in stages if s.id == "voiceover")
    visual = next(s for s in stages if s.id == "visual")
    assert voiceover.depends_on == ["scripting"]
    assert visual.depends_on == ["scripting"]
    assert voiceover.dir_prefix == visual.dir_prefix == "03"


def test_assembly_depends_on_both_branch_stages():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    assembly = next(s for s in stages if s.id == "assembly")
    assert set(assembly.depends_on) == {"voiceover", "visual"}


def test_grounding_is_brand_scoped_to_raisinggoodsports():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    grounding = next(s for s in stages if s.id == "grounding")
    assert grounding.brand_scope == "raisinggoodsports"
    assert grounding.depends_on == []


def test_ideation_has_no_brand_scope():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    ideation = next(s for s in stages if s.id == "ideation")
    assert ideation.brand_scope is None


def test_stage_dir_name_formats_prefix_and_id():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    scripting = next(s for s in stages if s.id == "scripting")
    assert stage_dir_name(scripting) == "02-scripting"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_pipeline_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline_app'` (or `pipeline.yaml` missing).

- [ ] **Step 3: Create the requirements file, README, package init, and repo-root `pipeline.yaml`**

`pipeline-app/requirements.txt`:

```
fastapi==0.115.*
uvicorn[standard]==0.32.*
jinja2==3.1.*
pyyaml==6.0.*
markdown==3.7.*
python-multipart==0.0.*
pytest==8.3.*
pytest-asyncio==0.24.*
httpx==0.27.*
```

`pipeline-app/README.md`:

```markdown
# ContentStudio Pipeline App

Local-only control app for the ContentStudio six-skill pipeline (plus the RaisingGoodSports
grounding stage). Reachable only from `127.0.0.1` — never deploy this.

## Setup

    cd pipeline-app
    python -m venv .venv
    .venv\Scripts\Activate.ps1   # or: source .venv/bin/activate
    pip install -r requirements.txt
    pip install -e .

## Run

    uvicorn pipeline_app.main:app --host 127.0.0.1 --port 8420

## Test

    python -m pytest
```

`pipeline-app/pipeline_app/__init__.py`:

```python
```

(empty file — marks the package)

Repo-root `pipeline.yaml`:

```yaml
stages:
  - id: grounding
    skill: rgs-grounding
    dir_prefix: "00"
    depends_on: []
    brand_scope: raisinggoodsports
  - id: ideation
    skill: shorts-ideation
    dir_prefix: "01"
    depends_on: []
  - id: scripting
    skill: shorts-scripting
    dir_prefix: "02"
    depends_on: [ideation]
  - id: voiceover
    skill: voiceover-brief
    dir_prefix: "03"
    depends_on: [scripting]
  - id: visual
    skill: visual-prompts
    dir_prefix: "03"
    depends_on: [scripting]
  - id: assembly
    skill: shorts-assembly
    dir_prefix: "04"
    depends_on: [voiceover, visual]
  - id: repurpose
    skill: social-repurpose
    dir_prefix: "05"
    depends_on: [assembly]
```

`pipeline-app/pipeline_app/pipeline_config.py`:

```python
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class StageDef:
    id: str
    skill: str
    dir_prefix: str
    depends_on: list[str] = field(default_factory=list)
    brand_scope: str | None = None


def load_topology(path: Path) -> list[StageDef]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        StageDef(
            id=s["id"],
            skill=s["skill"],
            dir_prefix=s["dir_prefix"],
            depends_on=list(s.get("depends_on", [])),
            brand_scope=s.get("brand_scope"),
        )
        for s in data["stages"]
    ]


def stage_dir_name(stage: StageDef) -> str:
    return f"{stage.dir_prefix}-{stage.id}"
```

- [ ] **Step 4: Update `.gitignore`**

Append to the repo-root `.gitignore`:

```
# Pipeline app (local control app for the six-skill pipeline)
runs/
pipeline-app/pipeline.db
pipeline-app/.venv/
pipeline-app/pipeline_app/__pycache__/
pipeline-app/pipeline_app/**/__pycache__/
pipeline-app/tests/__pycache__/
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_pipeline_config.py -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add pipeline.yaml .gitignore pipeline-app/requirements.txt pipeline-app/README.md pipeline-app/pipeline_app/__init__.py pipeline-app/pipeline_app/pipeline_config.py pipeline-app/tests/test_pipeline_config.py
git commit -m "feat(pipeline-app): add pipeline.yaml topology and loader"
```

---

## Task 2: Artifact frontmatter parsing, versioning, and hashing

**Files:**
- Create: `pipeline-app/pipeline_app/artifacts.py`
- Test: `pipeline-app/tests/test_artifacts.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `parse_frontmatter(text: str) -> tuple[dict, str]`; `render_frontmatter(meta: dict,
  body: str) -> str`; `compute_sha256(path: Path) -> str`; `next_version_number(stage_dir: Path)
  -> int`; `latest_artifact_path(stage_dir: Path) -> Path | None`; `write_artifact(stage_dir:
  Path, version: int, meta: dict, body: str) -> Path`; `stamp_final(path: Path, finalized_at: str)
  -> None`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_artifacts.py`:

```python
from pathlib import Path

import pytest

from pipeline_app.artifacts import (
    compute_sha256,
    latest_artifact_path,
    next_version_number,
    parse_frontmatter,
    render_frontmatter,
    stamp_final,
    write_artifact,
)


def test_render_and_parse_frontmatter_roundtrip():
    meta = {"schema_version": 1, "stage": "shorts-ideation", "depends_on": []}
    text = render_frontmatter(meta, "# Concept Brief\n\nBody text here.")
    parsed_meta, body = parse_frontmatter(text)
    assert parsed_meta["schema_version"] == 1
    assert parsed_meta["stage"] == "shorts-ideation"
    assert "Concept Brief" in body


def test_parse_frontmatter_on_plain_text_returns_empty_meta():
    meta, body = parse_frontmatter("just plain text, no frontmatter")
    assert meta == {}
    assert body == "just plain text, no frontmatter"


def test_next_version_number_empty_dir_is_one(tmp_path: Path):
    assert next_version_number(tmp_path) == 1


def test_next_version_number_increments(tmp_path: Path):
    (tmp_path / "artifact.v1.md").write_text("x", encoding="utf-8")
    (tmp_path / "artifact.v2.md").write_text("x", encoding="utf-8")
    assert next_version_number(tmp_path) == 3


def test_latest_artifact_path_picks_highest_version(tmp_path: Path):
    (tmp_path / "artifact.v1.md").write_text("old", encoding="utf-8")
    (tmp_path / "artifact.v2.md").write_text("new", encoding="utf-8")
    assert latest_artifact_path(tmp_path).name == "artifact.v2.md"


def test_latest_artifact_path_none_when_empty(tmp_path: Path):
    assert latest_artifact_path(tmp_path) is None


def test_write_artifact_creates_versioned_file(tmp_path: Path):
    path = write_artifact(tmp_path, 1, {"stage": "shorts-ideation"}, "hello body")
    assert path.name == "artifact.v1.md"
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["stage"] == "shorts-ideation"
    assert "hello body" in body


def test_compute_sha256_is_stable(tmp_path: Path):
    f = tmp_path / "a.md"
    f.write_text("same content", encoding="utf-8")
    h1 = compute_sha256(f)
    h2 = compute_sha256(f)
    assert h1 == h2
    assert len(h1) == 64


def test_stamp_final_sets_status_and_hash_reflects_stamped_content(tmp_path: Path):
    path = write_artifact(tmp_path, 1, {"status": "draft"}, "content")
    hash_before_stamp = compute_sha256(path)
    stamp_final(path, "2026-07-25T00:00:00+00:00")
    meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["status"] == "final"
    assert meta["finalized_at"] == "2026-07-25T00:00:00+00:00"
    hash_after_stamp = compute_sha256(path)
    # The file's bytes changed because of the stamp, so the hash a downstream
    # stage would record must be taken AFTER stamping, never before.
    assert hash_before_stamp != hash_after_stamp
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_artifacts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_app.artifacts'`.

- [ ] **Step 3: Implement `artifacts.py`**

```python
import hashlib
import re
from pathlib import Path

import yaml

_DELIM = "---"
_VERSION_RE = re.compile(r"artifact\.v(\d+)\.md$")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.split("\n")
    if not lines or lines[0].strip() != _DELIM:
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == _DELIM:
            yaml_text = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1:])
            meta = yaml.safe_load(yaml_text) or {}
            return meta, body.lstrip("\n")
    return {}, text


def render_frontmatter(meta: dict, body: str) -> str:
    yaml_text = yaml.safe_dump(meta, sort_keys=False, default_flow_style=False).strip()
    return f"{_DELIM}\n{yaml_text}\n{_DELIM}\n\n{body.strip()}\n"


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _versions_in(stage_dir: Path) -> list[tuple[int, Path]]:
    versions = []
    for p in stage_dir.glob("artifact.v*.md"):
        m = _VERSION_RE.match(p.name)
        if m:
            versions.append((int(m.group(1)), p))
    return versions


def next_version_number(stage_dir: Path) -> int:
    versions = _versions_in(stage_dir)
    return (max(v for v, _ in versions) if versions else 0) + 1


def latest_artifact_path(stage_dir: Path) -> Path | None:
    versions = _versions_in(stage_dir)
    if not versions:
        return None
    return max(versions, key=lambda t: t[0])[1]


def write_artifact(stage_dir: Path, version: int, meta: dict, body: str) -> Path:
    stage_dir.mkdir(parents=True, exist_ok=True)
    path = stage_dir / f"artifact.v{version}.md"
    path.write_text(render_frontmatter(meta, body), encoding="utf-8")
    return path


def stamp_final(path: Path, finalized_at: str) -> None:
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    meta["status"] = "final"
    meta["finalized_at"] = finalized_at
    path.write_text(render_frontmatter(meta, body), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_artifacts.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/artifacts.py pipeline-app/tests/test_artifacts.py
git commit -m "feat(pipeline-app): add artifact frontmatter, versioning, and hashing"
```

---

## Task 3: Stage state machine (status + staleness)

**Files:**
- Create: `pipeline-app/pipeline_app/state_machine.py`
- Test: `pipeline-app/tests/test_state_machine.py`

**Interfaces:**
- Consumes: nothing from prior tasks directly (pure logic module).
- Produces: `StageStatus` enum (`LOCKED`, `READY`, `RUNNING`, `AWAITING_REVIEW`, `APPROVED`,
  `STALE`, `NO_ARTIFACT`); `compute_initial_status(depends_on: list[str]) -> StageStatus`;
  `stages_to_unlock(all_stage_defs, approved_stage_ids: set[str]) -> list[str]`; `is_stale
  (recorded_depends_on: list[dict], current_hashes: dict[str, str]) -> bool`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_state_machine.py`:

```python
from pipeline_app.pipeline_config import StageDef
from pipeline_app.state_machine import (
    StageStatus,
    compute_initial_status,
    is_stale,
    stages_to_unlock,
)


def test_stage_with_no_dependencies_starts_ready():
    assert compute_initial_status([]) == StageStatus.READY


def test_stage_with_dependencies_starts_locked():
    assert compute_initial_status(["ideation"]) == StageStatus.LOCKED


def test_stages_to_unlock_finds_stage_whose_deps_are_all_approved():
    stages = [
        StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01"),
        StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02", depends_on=["ideation"]),
    ]
    unlocked = stages_to_unlock(stages, approved_stage_ids={"ideation"})
    assert unlocked == ["scripting"]


def test_stages_to_unlock_respects_parallel_pair_needing_both_deps():
    stages = [
        StageDef(id="voiceover", skill="voiceover-brief", dir_prefix="03", depends_on=["scripting"]),
        StageDef(id="visual", skill="visual-prompts", dir_prefix="03", depends_on=["scripting"]),
        StageDef(id="assembly", skill="shorts-assembly", dir_prefix="04", depends_on=["voiceover", "visual"]),
    ]
    unlocked = stages_to_unlock(stages, approved_stage_ids={"scripting", "voiceover"})
    assert "assembly" not in unlocked  # visual not yet approved
    unlocked_both = stages_to_unlock(stages, approved_stage_ids={"scripting", "voiceover", "visual"})
    assert "assembly" in unlocked_both


def test_is_stale_when_hash_no_longer_matches():
    recorded = [{"path": "../01-ideation/artifact.v1.md", "sha256": "abc123"}]
    current_hashes = {"../01-ideation/artifact.v1.md": "different-hash"}
    assert is_stale(recorded, current_hashes) is True


def test_is_stale_false_when_hash_matches():
    recorded = [{"path": "../01-ideation/artifact.v1.md", "sha256": "abc123"}]
    current_hashes = {"../01-ideation/artifact.v1.md": "abc123"}
    assert is_stale(recorded, current_hashes) is False


def test_is_stale_false_for_empty_dependencies():
    assert is_stale([], {}) is False


def test_is_stale_true_when_dependency_missing_from_current_hashes():
    recorded = [{"path": "missing.md", "sha256": "abc123"}]
    assert is_stale(recorded, {}) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_state_machine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_app.state_machine'`.

- [ ] **Step 3: Implement `state_machine.py`**

```python
from enum import Enum

from pipeline_app.pipeline_config import StageDef


class StageStatus(str, Enum):
    LOCKED = "locked"
    READY = "ready"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    STALE = "stale"
    NO_ARTIFACT = "no_artifact"


def compute_initial_status(depends_on: list[str]) -> StageStatus:
    return StageStatus.READY if not depends_on else StageStatus.LOCKED


def stages_to_unlock(all_stage_defs: list[StageDef], approved_stage_ids: set[str]) -> list[str]:
    unlocked = []
    for stage in all_stage_defs:
        if stage.id in approved_stage_ids:
            continue
        if stage.depends_on and all(dep in approved_stage_ids for dep in stage.depends_on):
            unlocked.append(stage.id)
    return unlocked


def is_stale(recorded_depends_on: list[dict], current_hashes: dict[str, str]) -> bool:
    for dep in recorded_depends_on:
        path = dep["path"]
        recorded_hash = dep["sha256"]
        if current_hashes.get(path) != recorded_hash:
            return True
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_state_machine.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/state_machine.py pipeline-app/tests/test_state_machine.py
git commit -m "feat(pipeline-app): add stage state machine and staleness detection"
```

---

## Task 4: SQLite schema and data-access layer

**Files:**
- Create: `pipeline-app/pipeline_app/schema.sql`
- Create: `pipeline-app/pipeline_app/db.py`
- Test: `pipeline-app/tests/test_db.py`

**Interfaces:**
- Produces: `get_connection(db_path) -> sqlite3.Connection`; `init_db(db_path, schema_path) ->
  None`; `create_project`, `get_project`, `list_projects`, `create_stage_row`, `get_stage`,
  `list_stages`, `update_stage_status`, `update_stage_session`, `create_turn`, `update_turn`,
  `list_turns`, `list_running_turns`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_db.py`:

```python
from pathlib import Path

import pytest

from pipeline_app import db


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


def test_create_and_get_project(conn):
    project_id = db.create_project(conn, "abc-20260725-120000", "abc", "generic", "2026-07-25T12:00:00Z")
    row = db.get_project(conn, project_id)
    assert row["run_id"] == "abc-20260725-120000"
    assert row["brand"] == "generic"


def test_list_projects_newest_first(conn):
    db.create_project(conn, "a-1", "a", "generic", "2026-07-25T12:00:00Z")
    db.create_project(conn, "b-2", "b", "generic", "2026-07-25T13:00:00Z")
    rows = db.list_projects(conn)
    assert [r["run_id"] for r in rows] == ["b-2", "a-1"]


def test_create_and_get_stage(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    row = db.get_stage(conn, project_id, "ideation")
    assert row["id"] == stage_row_id
    assert row["status"] == "ready"


def test_update_stage_status_and_approved_at(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "ready")
    stage_row = db.get_stage(conn, project_id, "ideation")
    db.update_stage_status(conn, stage_row["id"], "approved", approved_at="2026-07-25T14:00:00Z")
    updated = db.get_stage(conn, project_id, "ideation")
    assert updated["status"] == "approved"
    assert updated["approved_at"] == "2026-07-25T14:00:00Z"


def test_update_stage_session(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    db.update_stage_session(conn, stage_row_id, "session-123")
    row = db.get_stage(conn, project_id, "ideation")
    assert row["claude_session_id"] == "session-123"


def test_list_stages_returns_all_for_project(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "ready")
    db.create_stage_row(conn, project_id, "scripting", "locked")
    rows = db.list_stages(conn, project_id)
    assert {r["stage_id"] for r in rows} == {"ideation", "scripting"}


def test_create_and_update_turn(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "running")
    turn_id = db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:05:00Z", "events/1.jsonl")
    db.update_turn(conn, turn_id, "complete", finished_at="2026-07-25T12:06:00Z", cost_usd=0.05)
    rows = db.list_turns(conn, stage_row_id)
    assert len(rows) == 1
    assert rows[0]["status"] == "complete"
    assert rows[0]["cost_usd"] == 0.05


def test_list_running_turns(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "running")
    db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:05:00Z", "events/1.jsonl")
    running = db.list_running_turns(conn)
    assert len(running) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_app.db'`.

- [ ] **Step 3: Implement `schema.sql` and `db.py`**

`pipeline-app/pipeline_app/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL,
    brand TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    stage_id TEXT NOT NULL,
    status TEXT NOT NULL,
    claude_session_id TEXT,
    approved_at TEXT,
    UNIQUE(project_id, stage_id)
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_row_id INTEGER NOT NULL REFERENCES stages(id),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    events_path TEXT NOT NULL,
    cost_usd REAL
);
```

`pipeline-app/pipeline_app/db.py`:

```python
import sqlite3
from pathlib import Path


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path, schema_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def create_project(conn: sqlite3.Connection, run_id: str, slug: str, brand: str, created_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO projects (run_id, slug, brand, created_at) VALUES (?, ?, ?, ?)",
        (run_id, slug, brand, created_at),
    )
    conn.commit()
    return cur.lastrowid


def get_project(conn: sqlite3.Connection, project_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()


def list_projects(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()


def create_stage_row(conn: sqlite3.Connection, project_id: int, stage_id: str, status: str) -> int:
    cur = conn.execute(
        "INSERT INTO stages (project_id, stage_id, status) VALUES (?, ?, ?)",
        (project_id, stage_id, status),
    )
    conn.commit()
    return cur.lastrowid


def get_stage(conn: sqlite3.Connection, project_id: int, stage_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM stages WHERE project_id = ? AND stage_id = ?",
        (project_id, stage_id),
    ).fetchone()


def list_stages(conn: sqlite3.Connection, project_id: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM stages WHERE project_id = ?", (project_id,)).fetchall()


def update_stage_status(conn: sqlite3.Connection, stage_row_id: int, status: str, approved_at: str | None = None) -> None:
    if approved_at is not None:
        conn.execute(
            "UPDATE stages SET status = ?, approved_at = ? WHERE id = ?",
            (status, approved_at, stage_row_id),
        )
    else:
        conn.execute("UPDATE stages SET status = ? WHERE id = ?", (status, stage_row_id))
    conn.commit()


def update_stage_session(conn: sqlite3.Connection, stage_row_id: int, session_id: str) -> None:
    conn.execute("UPDATE stages SET claude_session_id = ? WHERE id = ?", (session_id, stage_row_id))
    conn.commit()


def create_turn(conn: sqlite3.Connection, stage_row_id: int, status: str, created_at: str, events_path: str) -> int:
    cur = conn.execute(
        "INSERT INTO turns (stage_row_id, status, created_at, events_path) VALUES (?, ?, ?, ?)",
        (stage_row_id, status, created_at, events_path),
    )
    conn.commit()
    return cur.lastrowid


def update_turn(conn: sqlite3.Connection, turn_id: int, status: str, finished_at: str | None = None, cost_usd: float | None = None) -> None:
    conn.execute(
        "UPDATE turns SET status = ?, finished_at = COALESCE(?, finished_at), cost_usd = COALESCE(?, cost_usd) WHERE id = ?",
        (status, finished_at, cost_usd, turn_id),
    )
    conn.commit()


def list_turns(conn: sqlite3.Connection, stage_row_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM turns WHERE stage_row_id = ? ORDER BY created_at", (stage_row_id,)
    ).fetchall()


def list_running_turns(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM turns WHERE status = 'running'").fetchall()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_db.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/schema.sql pipeline-app/pipeline_app/db.py pipeline-app/tests/test_db.py
git commit -m "feat(pipeline-app): add SQLite schema and data-access layer"
```

---

## Task 5: Project creation service (run_id, directories, brand-scoped stage seeding)

**Files:**
- Create: `pipeline-app/pipeline_app/project_service.py`
- Test: `pipeline-app/tests/test_project_service.py`

**Interfaces:**
- Consumes: `StageDef`, `load_topology` (Task 1); `StageStatus`, `compute_initial_status` (Task
  3); `db.create_project`, `db.create_stage_row` (Task 4).
- Produces: `create_project(conn, repo_root, slug, brand, stage_defs, now=None) -> dict` with keys
  `project_id`, `run_id`, `run_dir`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_project_service.py`:

```python
import datetime
from pathlib import Path

import pytest

from pipeline_app import db
from pipeline_app.pipeline_config import StageDef
from pipeline_app.project_service import create_project

STAGES = [
    StageDef(id="grounding", skill="rgs-grounding", dir_prefix="00", depends_on=[], brand_scope="raisinggoodsports"),
    StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[]),
    StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02", depends_on=["ideation"]),
]


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


def test_generic_project_has_no_grounding_stage_or_directory(conn, tmp_path: Path):
    now = datetime.datetime(2026, 7, 25, 14, 32, 0, tzinfo=datetime.timezone.utc)
    result = create_project(conn, tmp_path, "why-kids-quit", "generic", STAGES, now=now)
    assert result["run_id"] == "why-kids-quit-20260725-143200"
    assert not (result["run_dir"] / "00-grounding").exists()
    assert (result["run_dir"] / "01-ideation").exists()
    rows = db.list_stages(conn, result["project_id"])
    assert {r["stage_id"] for r in rows} == {"ideation", "scripting"}


def test_rgs_project_includes_grounding_stage_and_directory(conn, tmp_path: Path):
    now = datetime.datetime(2026, 7, 25, 14, 32, 0, tzinfo=datetime.timezone.utc)
    result = create_project(conn, tmp_path, "why-kids-quit", "raisinggoodsports", STAGES, now=now)
    assert (result["run_dir"] / "00-grounding").exists()
    rows = db.list_stages(conn, result["project_id"])
    assert {r["stage_id"] for r in rows} == {"grounding", "ideation", "scripting"}


def test_stages_with_no_dependencies_start_ready_others_locked(conn, tmp_path: Path):
    result = create_project(conn, tmp_path, "why-kids-quit", "generic", STAGES)
    ideation = db.get_stage(conn, result["project_id"], "ideation")
    scripting = db.get_stage(conn, result["project_id"], "scripting")
    assert ideation["status"] == "ready"
    assert scripting["status"] == "locked"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_project_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_app.project_service'`.

- [ ] **Step 3: Implement `project_service.py`**

```python
import datetime
import sqlite3
from pathlib import Path

from pipeline_app import db as db_mod
from pipeline_app.pipeline_config import StageDef, stage_dir_name
from pipeline_app.state_machine import compute_initial_status


def create_project(
    conn: sqlite3.Connection,
    repo_root: Path,
    slug: str,
    brand: str,
    stage_defs: list[StageDef],
    now: datetime.datetime | None = None,
) -> dict:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    run_id = f"{slug}-{now.strftime('%Y%m%d-%H%M%S')}"
    project_id = db_mod.create_project(conn, run_id, slug, brand, now.isoformat())

    run_dir = repo_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    applicable = [s for s in stage_defs if s.brand_scope is None or s.brand_scope == brand]
    for stage in applicable:
        status = compute_initial_status(stage.depends_on)
        db_mod.create_stage_row(conn, project_id, stage.id, status.value)
        (run_dir / stage_dir_name(stage)).mkdir(parents=True, exist_ok=True)

    return {"project_id": project_id, "run_id": run_id, "run_dir": run_dir}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_project_service.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/project_service.py pipeline-app/tests/test_project_service.py
git commit -m "feat(pipeline-app): add brand-scoped project creation service"
```

---

## Task 6: Claude CLI runner (binary resolution, argv, stream parsing, result extraction)

**Files:**
- Create: `pipeline-app/pipeline_app/cli_runner.py`
- Test: `pipeline-app/tests/test_cli_runner.py`

**Interfaces:**
- Produces: `TurnResult` dataclass (`session_id`, `result_text`, `cost_usd`, `success`);
  `resolve_claude_binary(which_fn=shutil.which) -> str`; `build_claude_argv(prompt,
  resume_session_id, allowed_tools, settings_path, which_fn=shutil.which) -> list[str]`;
  `parse_stream_json_lines(lines: AsyncIterator[bytes]) -> AsyncIterator[dict]`;
  `extract_turn_result(events: list[dict]) -> TurnResult`; `stream_claude_turn(prompt, cwd,
  resume_session_id, allowed_tools="Read,Glob,Grep,Write,Edit", settings_path=None) ->
  AsyncIterator[dict]`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_cli_runner.py`:

```python
import pytest

from pipeline_app.cli_runner import (
    build_claude_argv,
    extract_turn_result,
    parse_stream_json_lines,
    resolve_claude_binary,
)


def test_resolve_claude_binary_returns_path_when_found():
    path = resolve_claude_binary(which_fn=lambda name: r"C:\fake\claude.CMD")
    assert path == r"C:\fake\claude.CMD"


def test_resolve_claude_binary_raises_when_not_found():
    with pytest.raises(FileNotFoundError):
        resolve_claude_binary(which_fn=lambda name: None)


def test_build_claude_argv_first_turn_has_no_resume():
    argv = build_claude_argv(
        "/shorts-ideation do the thing",
        resume_session_id=None,
        allowed_tools="Read,Glob,Grep,Write,Edit",
        settings_path=None,
        which_fn=lambda name: "claude",
    )
    assert argv[0] == "claude"
    assert "-p" in argv
    assert "/shorts-ideation do the thing" in argv
    assert "--resume" not in argv
    assert "--allowedTools" in argv
    idx = argv.index("--allowedTools")
    assert argv[idx + 1] == "Read,Glob,Grep,Write,Edit"


def test_build_claude_argv_resume_turn_includes_session_id():
    argv = build_claude_argv(
        "continue please",
        resume_session_id="session-abc",
        allowed_tools="Read,Glob,Grep,Write,Edit",
        settings_path=None,
        which_fn=lambda name: "claude",
    )
    idx = argv.index("--resume")
    assert argv[idx + 1] == "session-abc"


@pytest.mark.asyncio
async def test_parse_stream_json_lines_yields_parsed_dicts():
    async def fake_lines():
        for line in [b'{"type": "system", "subtype": "init"}\n', b'  \n', b'{"type": "result", "result": "ok"}\n']:
            yield line

    events = [e async for e in parse_stream_json_lines(fake_lines())]
    assert events == [
        {"type": "system", "subtype": "init"},
        {"type": "result", "result": "ok"},
    ]


@pytest.mark.asyncio
async def test_parse_stream_json_lines_skips_invalid_json():
    async def fake_lines():
        yield b"not json at all\n"
        yield b'{"type": "result", "result": "ok"}\n'

    events = [e async for e in parse_stream_json_lines(fake_lines())]
    assert events == [{"type": "result", "result": "ok"}]


def test_extract_turn_result_finds_session_id_and_result():
    events = [
        {"type": "system", "subtype": "init", "session_id": "session-xyz"},
        {"type": "assistant", "message": {}},
        {"type": "result", "result": "final text", "total_cost_usd": 0.02, "is_error": False},
    ]
    result = extract_turn_result(events)
    assert result.session_id == "session-xyz"
    assert result.result_text == "final text"
    assert result.cost_usd == 0.02
    assert result.success is True


def test_extract_turn_result_marks_failure_on_is_error():
    events = [{"type": "result", "result": "oops", "is_error": True}]
    result = extract_turn_result(events)
    assert result.success is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_cli_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_app.cli_runner'`.

- [ ] **Step 3: Implement `cli_runner.py`**

```python
import asyncio
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Callable


@dataclass
class TurnResult:
    session_id: str | None
    result_text: str | None
    cost_usd: float | None
    success: bool


def resolve_claude_binary(which_fn: Callable[[str], str | None] = shutil.which) -> str:
    path = which_fn("claude")
    if path is None:
        raise FileNotFoundError(
            "claude CLI not found on PATH. Install Claude Code and ensure 'claude' is on PATH."
        )
    return path


def build_claude_argv(
    prompt: str,
    resume_session_id: str | None,
    allowed_tools: str,
    settings_path: str | None,
    which_fn: Callable[[str], str | None] = shutil.which,
) -> list[str]:
    binary = resolve_claude_binary(which_fn)
    argv = [
        binary, "-p", prompt,
        "--output-format", "stream-json",
        "--include-partial-messages",
        "--allowedTools", allowed_tools,
    ]
    if resume_session_id:
        argv += ["--resume", resume_session_id]
    if settings_path:
        argv += ["--settings", settings_path]
    return argv


async def parse_stream_json_lines(lines: AsyncIterator[bytes]) -> AsyncIterator[dict]:
    async for line in lines:
        text = line.decode("utf-8").strip()
        if not text:
            continue
        try:
            yield json.loads(text)
        except json.JSONDecodeError:
            continue


def extract_turn_result(events: list[dict]) -> TurnResult:
    session_id = None
    result_text = None
    cost_usd = None
    success = False
    for event in events:
        if event.get("type") == "system" and event.get("subtype") == "init":
            session_id = event.get("session_id")
        if event.get("type") == "result":
            result_text = event.get("result")
            cost_usd = event.get("total_cost_usd")
            success = not event.get("is_error", False)
    return TurnResult(session_id=session_id, result_text=result_text, cost_usd=cost_usd, success=success)


async def stream_claude_turn(
    prompt: str,
    cwd: Path,
    resume_session_id: str | None,
    allowed_tools: str = "Read,Glob,Grep,Write,Edit",
    settings_path: str | None = None,
) -> AsyncIterator[dict]:
    argv = build_claude_argv(prompt, resume_session_id, allowed_tools, settings_path)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    assert process.stdout is not None
    async for event in parse_stream_json_lines(process.stdout):
        yield event
    await process.wait()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_cli_runner.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/cli_runner.py pipeline-app/tests/test_cli_runner.py
git commit -m "feat(pipeline-app): add claude CLI runner with testable stream parsing"
```

---

## Task 7: Kickoff prompt templates (Jinja2, conditional grounding block)

**Files:**
- Create: `pipeline-app/pipeline_app/prompt_builder.py`
- Create: `pipeline-app/stage_templates/grounding.md`
- Create: `pipeline-app/stage_templates/ideation.md`
- Create: `pipeline-app/stage_templates/scripting.md`
- Create: `pipeline-app/stage_templates/voiceover.md`
- Create: `pipeline-app/stage_templates/visual.md`
- Create: `pipeline-app/stage_templates/assembly.md`
- Create: `pipeline-app/stage_templates/repurpose.md`
- Test: `pipeline-app/tests/test_prompt_builder.py`

**Interfaces:**
- Produces: `render_kickoff_prompt(templates_dir: Path, stage_id: str, context: dict) -> str`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_prompt_builder.py`:

```python
from pathlib import Path

from pipeline_app.prompt_builder import render_kickoff_prompt

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "stage_templates"


def test_ideation_template_starts_with_skill_slash_command():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "ideation", {
        "skill": "shorts-ideation",
        "user_message": "a Short about travel-sport burnout",
        "grounding_pointer": None,
        "input_file": None,
        "raw_output_path": "runs/x/01-ideation/raw_output.md",
    })
    assert prompt.strip().startswith("/shorts-ideation")
    assert "travel-sport burnout" in prompt


def test_ideation_template_omits_grounding_block_when_none():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "ideation", {
        "skill": "shorts-ideation",
        "user_message": "idea",
        "grounding_pointer": None,
        "input_file": None,
        "raw_output_path": "out.md",
    })
    assert "companion grounding artifact" not in prompt


def test_ideation_template_includes_grounding_block_when_present():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "ideation", {
        "skill": "shorts-ideation",
        "user_message": "idea",
        "grounding_pointer": "rgs-briefs/2026-07-25-idea.md",
        "input_file": None,
        "raw_output_path": "out.md",
    })
    assert "rgs-briefs/2026-07-25-idea.md" in prompt


def test_scripting_template_references_input_file():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "scripting", {
        "skill": "shorts-scripting",
        "user_message": "",
        "grounding_pointer": None,
        "input_file": "runs/x/01-ideation/artifact.v1.md",
        "raw_output_path": "runs/x/02-scripting/raw_output.md",
    })
    assert "runs/x/01-ideation/artifact.v1.md" in prompt


def test_visual_template_includes_grounding_block_when_present():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "visual", {
        "skill": "visual-prompts",
        "user_message": "",
        "grounding_pointer": "rgs-briefs/2026-07-25-idea.md",
        "input_file": "runs/x/02-scripting/artifact.v1.md",
        "raw_output_path": "runs/x/03-visual/raw_output.md",
    })
    assert "rgs-briefs/2026-07-25-idea.md" in prompt


def test_grounding_template_has_no_input_file_reference():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "grounding", {
        "skill": "rgs-grounding",
        "user_message": "a Short about travel-sport burnout",
        "grounding_pointer": None,
        "input_file": None,
        "raw_output_path": None,
    })
    assert prompt.strip().startswith("/rgs-grounding")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_prompt_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_app.prompt_builder'`.

- [ ] **Step 3: Implement the templates and `prompt_builder.py`**

`pipeline-app/pipeline_app/prompt_builder.py`:

```python
from pathlib import Path

import jinja2


def _environment(templates_dir: Path) -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_kickoff_prompt(templates_dir: Path, stage_id: str, context: dict) -> str:
    env = _environment(templates_dir)
    template = env.get_template(f"{stage_id}.md")
    return template.render(**context)
```

`pipeline-app/stage_templates/grounding.md`:

```
/{{ skill }}

Topic: {{ user_message }}
```

`pipeline-app/stage_templates/ideation.md`:

```
/{{ skill }}

{% if grounding_pointer %}
A companion grounding artifact for this Short is available at `{{ grounding_pointer }}`. Read it
and prefer an angle consistent with its archetype/angle hint, per shorts-ideation's "Optional
input" section.
{% endif %}
Raw idea: {{ user_message }}

Write your final concept brief to `{{ raw_output_path }}` (overwrite it completely each time you
produce a new draft).
```

`pipeline-app/stage_templates/scripting.md`:

```
/{{ skill }}

Read the concept brief at `{{ input_file }}` and write the shot-ready script per
shorts-scripting.
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}` — carry forward any
citations or constraints it names.
{% endif %}
{{ user_message }}

Write your final script to `{{ raw_output_path }}` (overwrite it completely each time you produce
a new draft).
```

`pipeline-app/stage_templates/voiceover.md`:

```
/{{ skill }}

Read the script at `{{ input_file }}` and produce the ElevenLabs voiceover production brief.

{{ user_message }}

Write your final brief to `{{ raw_output_path }}` (overwrite it completely each time you produce a
new draft).
```

`pipeline-app/stage_templates/visual.md`:

```
/{{ skill }}

Read the script at `{{ input_file }}` and produce the Midjourney prompt sheet.
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}` — carry forward any
citations or constraints it names.
{% endif %}
{{ user_message }}

Write your final prompt sheet to `{{ raw_output_path }}` (overwrite it completely each time you
produce a new draft).
```

`pipeline-app/stage_templates/assembly.md`:

```
/{{ skill }}

Read the script, voiceover brief, and visual prompt sheet at `{{ input_file }}` and produce the
assembly/edit plan.

{{ user_message }}

Write your final edit plan to `{{ raw_output_path }}` (overwrite it completely each time you
produce a new draft).
```

`pipeline-app/stage_templates/repurpose.md`:

```
/{{ skill }}

Read the finished Short's script and edit plan at `{{ input_file }}` and produce the multi-surface
post copy.

{{ user_message }}

Write your final post copy to `{{ raw_output_path }}` (overwrite it completely each time you
produce a new draft).
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_prompt_builder.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/prompt_builder.py pipeline-app/stage_templates pipeline-app/tests/test_prompt_builder.py
git commit -m "feat(pipeline-app): add kickoff prompt templates with grounding pass-through"
```

---

## Task 8: Turn orchestration service (the core integration)

**Files:**
- Create: `pipeline-app/pipeline_app/turn_service.py`
- Test: `pipeline-app/tests/test_turn_service.py`

**Interfaces:**
- Consumes: `db` (Task 4), `artifacts` (Task 2), `state_machine` (Task 3), `cli_runner` (Task 6),
  `prompt_builder` (Task 7), `StageDef`/`stage_dir_name` (Task 1).
- Produces: `TurnAlreadyRunningError`; `any_turn_running(conn) -> bool`; `run_stage_turn(conn,
  repo_root, run_dir, templates_dir, project_id, run_id, stage_def, all_stage_defs, user_message,
  grounding_pointer=None, finalize_artifact=True) -> AsyncIterator[dict]` (an async generator —
  callers drain it with `async for event in run_stage_turn(...)`).

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_turn_service.py`:

```python
import datetime
from pathlib import Path
from typing import AsyncIterator

import pytest

from pipeline_app import artifacts, db
from pipeline_app.pipeline_config import StageDef
from pipeline_app.state_machine import StageStatus
from pipeline_app import turn_service

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "stage_templates"

STAGES = [
    StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[]),
    StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02", depends_on=["ideation"]),
]


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


def _fake_stream(events: list[dict], writes_file: Path | None = None, content: str = "generated body"):
    async def _gen(prompt, cwd, resume_session_id, **kwargs):
        if writes_file is not None:
            writes_file.parent.mkdir(parents=True, exist_ok=True)
            writes_file.write_text(content, encoding="utf-8")
        for event in events:
            yield event
    return _gen


async def _drain(agen: AsyncIterator[dict]) -> list[dict]:
    return [e async for e in agen]


@pytest.fixture
def project(conn, tmp_path: Path):
    project_id = db.create_project(conn, "abc-20260725-120000", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    run_dir = tmp_path / "runs" / "abc-20260725-120000"
    (run_dir / "01-ideation").mkdir(parents=True)
    return {"project_id": project_id, "run_dir": run_dir, "stage_row_id": stage_row_id}


@pytest.mark.asyncio
async def test_first_turn_writes_artifact_v1_and_sets_awaiting_review(conn, project, monkeypatch, tmp_path):
    raw_output = project["run_dir"] / "01-ideation" / "raw_output.md"
    events = [
        {"type": "system", "subtype": "init", "session_id": "session-1"},
        {"type": "result", "result": "done", "total_cost_usd": 0.01, "is_error": False},
    ]
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn", _fake_stream(events, raw_output))

    stage_def = STAGES[0]
    stage_row = db.get_stage(conn, project["project_id"], "ideation")
    collected = await _drain(turn_service.run_stage_turn(
        conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
        project["project_id"], "abc-20260725-120000",
        stage_def, STAGES, "a raw idea",
    ))
    assert len(collected) == 2

    stage_dir = project["run_dir"] / "01-ideation"
    v1 = stage_dir / "artifact.v1.md"
    assert v1.exists()
    meta, body = artifacts.parse_frontmatter(v1.read_text(encoding="utf-8"))
    assert meta["stage"] == "shorts-ideation"
    assert meta["version"] == 1
    assert meta["depends_on"] == []
    assert "generated body" in body

    updated_stage = db.get_stage(conn, project["project_id"], "ideation")
    assert updated_stage["status"] == StageStatus.AWAITING_REVIEW.value
    assert updated_stage["claude_session_id"] == "session-1"


@pytest.mark.asyncio
async def test_no_artifact_written_sets_no_artifact_status(conn, project, monkeypatch, tmp_path):
    events = [{"type": "result", "result": "just chatted, wrote nothing", "is_error": False}]
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn", _fake_stream(events, writes_file=None))

    stage_def = STAGES[0]
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
        project["project_id"], "abc-20260725-120000",
        stage_def, STAGES, "a raw idea",
    ))
    updated_stage = db.get_stage(conn, project["project_id"], "ideation")
    assert updated_stage["status"] == StageStatus.NO_ARTIFACT.value


@pytest.mark.asyncio
async def test_second_turn_on_approved_stage_creates_v2_and_marks_dependent_stale(conn, project, monkeypatch, tmp_path):
    # First turn on ideation -> v1
    raw_output = project["run_dir"] / "01-ideation" / "raw_output.md"
    events = [
        {"type": "system", "subtype": "init", "session_id": "session-1"},
        {"type": "result", "result": "done", "is_error": False},
    ]
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn", _fake_stream(events, raw_output, "v1 body"))
    stage_def = STAGES[0]
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
        project["project_id"], "abc-20260725-120000", stage_def, STAGES, "idea",
    ))

    # Approve ideation
    from pipeline_app import approval_service
    approval_service.approve_stage(conn, tmp_path, project["run_dir"], project["project_id"], STAGES, "ideation")

    # Create + approve scripting depending on ideation v1
    scripting_row_id = db.create_stage_row(conn, project["project_id"], "scripting", "ready")
    scripting_stage_dir = project["run_dir"] / "02-scripting"
    scripting_stage_dir.mkdir(parents=True)
    scripting_events = [
        {"type": "system", "subtype": "init", "session_id": "session-2"},
        {"type": "result", "result": "done", "is_error": False},
    ]
    scripting_raw = scripting_stage_dir / "raw_output.md"
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn", _fake_stream(scripting_events, scripting_raw, "script body"))
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
        project["project_id"], "abc-20260725-120000", STAGES[1], STAGES, "",
    ))
    approval_service.approve_stage(conn, tmp_path, project["run_dir"], project["project_id"], STAGES, "scripting")

    # Regenerate ideation -> v2
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn", _fake_stream(events, raw_output, "v2 body"))
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
        project["project_id"], "abc-20260725-120000", stage_def, STAGES, "idea revised",
    ))

    ideation_dir = project["run_dir"] / "01-ideation"
    assert (ideation_dir / "artifact.v2.md").exists()
    meta_v2, _ = artifacts.parse_frontmatter((ideation_dir / "artifact.v2.md").read_text(encoding="utf-8"))
    assert meta_v2["supersedes"] == "artifact.v1.md"

    scripting_stage = db.get_stage(conn, project["project_id"], "scripting")
    assert scripting_stage["status"] == StageStatus.STALE.value


@pytest.mark.asyncio
async def test_run_stage_turn_rejects_concurrent_turn(conn, project, monkeypatch, tmp_path):
    db.create_turn(conn, project["stage_row_id"], "running", "2026-07-25T12:00:00Z", "events/x.jsonl")
    stage_def = STAGES[0]
    with pytest.raises(turn_service.TurnAlreadyRunningError):
        await _drain(turn_service.run_stage_turn(
            conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
            project["project_id"], "abc-20260725-120000", stage_def, STAGES, "idea",
        ))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_turn_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_app.turn_service'` (and,
transitively, `pipeline_app.approval_service`, built in Task 9 — expected at this point).

- [ ] **Step 3: Implement `turn_service.py`**

```python
import datetime
import json
import sqlite3
import time
from pathlib import Path
from typing import AsyncIterator

from pipeline_app import artifacts, cli_runner, db as db_mod, prompt_builder
from pipeline_app.pipeline_config import StageDef, stage_dir_name
from pipeline_app.state_machine import StageStatus, is_stale


class TurnAlreadyRunningError(Exception):
    pass


def any_turn_running(conn: sqlite3.Connection) -> bool:
    return len(db_mod.list_running_turns(conn)) > 0


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _propagate_staleness(
    conn: sqlite3.Connection,
    run_dir: Path,
    all_stage_defs: list[StageDef],
    project_id: int,
    changed_stage_id: str,
) -> None:
    dependents = [s for s in all_stage_defs if changed_stage_id in s.depends_on]
    for dep_stage in dependents:
        row = db_mod.get_stage(conn, project_id, dep_stage.id)
        if row is None or row["status"] != StageStatus.APPROVED.value:
            continue
        stage_dir = run_dir / stage_dir_name(dep_stage)
        latest = artifacts.latest_artifact_path(stage_dir)
        if latest is None:
            continue
        meta, _ = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))
        recorded = meta.get("depends_on") or []
        current_hashes = {}
        for dep in recorded:
            dep_path = run_dir / dep["path"]
            if dep_path.exists():
                current_hashes[dep["path"]] = artifacts.compute_sha256(dep_path)
        if is_stale(recorded, current_hashes):
            db_mod.update_stage_status(conn, row["id"], StageStatus.STALE.value)


async def run_stage_turn(
    conn: sqlite3.Connection,
    repo_root: Path,
    run_dir: Path,
    templates_dir: Path,
    project_id: int,
    run_id: str,
    stage_def: StageDef,
    all_stage_defs: list[StageDef],
    user_message: str,
    grounding_pointer: str | None = None,
    finalize_artifact: bool = True,
) -> AsyncIterator[dict]:
    if any_turn_running(conn):
        raise TurnAlreadyRunningError("Another stage turn is already running.")

    stage_row = db_mod.get_stage(conn, project_id, stage_def.id)
    stage_dir = run_dir / stage_dir_name(stage_def)
    events_dir = stage_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    events_path = events_dir / f"{int(time.time() * 1000)}.jsonl"

    turn_id = db_mod.create_turn(conn, stage_row["id"], "running", _utcnow(), str(events_path))
    db_mod.update_stage_status(conn, stage_row["id"], StageStatus.RUNNING.value)

    raw_output_path = stage_dir / "raw_output.md"
    upstream_stage_defs = [s for s in all_stage_defs if s.id in stage_def.depends_on]
    upstream_paths = []
    for up in upstream_stage_defs:
        up_dir = run_dir / stage_dir_name(up)
        up_latest = artifacts.latest_artifact_path(up_dir)
        if up_latest is not None:
            upstream_paths.append(up_latest)

    is_first_turn = stage_row["claude_session_id"] is None
    if is_first_turn:
        input_file = str(upstream_paths[0]) if upstream_paths else None
        prompt = prompt_builder.render_kickoff_prompt(templates_dir, stage_def.id, {
            "skill": stage_def.skill,
            "user_message": user_message,
            "grounding_pointer": grounding_pointer,
            "input_file": input_file,
            "raw_output_path": str(raw_output_path),
        })
        resume_id = None
    else:
        prompt = user_message
        resume_id = stage_row["claude_session_id"]

    before_mtime = raw_output_path.stat().st_mtime if raw_output_path.exists() else None

    collected: list[dict] = []
    with events_path.open("a", encoding="utf-8") as f:
        async for event in cli_runner.stream_claude_turn(prompt, repo_root, resume_id):
            collected.append(event)
            f.write(json.dumps(event) + "\n")
            yield event

    result = cli_runner.extract_turn_result(collected)
    db_mod.update_turn(
        conn, turn_id,
        "complete" if result.success else "failed",
        _utcnow(), result.cost_usd,
    )
    if result.session_id:
        db_mod.update_stage_session(conn, stage_row["id"], result.session_id)

    if not finalize_artifact:
        return

    artifact_written = raw_output_path.exists() and (
        before_mtime is None or raw_output_path.stat().st_mtime != before_mtime
    )

    if not artifact_written:
        db_mod.update_stage_status(conn, stage_row["id"], StageStatus.NO_ARTIFACT.value)
        return

    version = artifacts.next_version_number(stage_dir)
    depends_on = [
        {"path": str(p.relative_to(run_dir)).replace("\\", "/"), "sha256": artifacts.compute_sha256(p)}
        for p in upstream_paths
    ]
    body = raw_output_path.read_text(encoding="utf-8")
    meta = {
        "schema_version": 1,
        "run_id": run_id,
        "stage": stage_def.skill,
        "version": version,
        "status": "draft",
        "created_at": _utcnow(),
        "finalized_at": None,
        "supersedes": f"artifact.v{version - 1}.md" if version > 1 else None,
        "depends_on": depends_on,
    }
    artifacts.write_artifact(stage_dir, version, meta, body)
    db_mod.update_stage_status(conn, stage_row["id"], StageStatus.AWAITING_REVIEW.value)
    _propagate_staleness(conn, run_dir, all_stage_defs, project_id, stage_def.id)
```

- [ ] **Step 4: Run test to verify it passes**

This test depends on `approval_service` (Task 9), so implement Task 9 (`approval_service.py`)
before running this test. Once both are implemented, run:

Run: `cd pipeline-app && python -m pytest tests/test_turn_service.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/turn_service.py pipeline-app/tests/test_turn_service.py
git commit -m "feat(pipeline-app): add turn orchestration with versioning and staleness propagation"
```

---

## Task 9: Approval service (stamp-then-hash ordering, unlocking dependents)

**Files:**
- Create: `pipeline-app/pipeline_app/approval_service.py`
- Test: `pipeline-app/tests/test_approval_service.py`

**Interfaces:**
- Consumes: `db`, `artifacts`, `state_machine.stages_to_unlock`, `StageDef`/`stage_dir_name`.
- Produces: `approve_stage(conn, repo_root, run_dir, project_id, stage_defs, stage_id) ->
  list[str]` (newly-unlocked stage ids).

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_approval_service.py`:

```python
from pathlib import Path

import pytest

from pipeline_app import artifacts, db
from pipeline_app.approval_service import approve_stage
from pipeline_app.pipeline_config import StageDef
from pipeline_app.state_machine import StageStatus

STAGES = [
    StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[]),
    StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02", depends_on=["ideation"]),
]


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


def test_approve_stamps_artifact_and_unlocks_dependent(conn, tmp_path: Path):
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "awaiting_review")
    db.create_stage_row(conn, project_id, "scripting", "locked")

    run_dir = tmp_path / "runs" / "abc-1"
    stage_dir = run_dir / "01-ideation"
    artifacts.write_artifact(stage_dir, 1, {"status": "draft", "stage": "shorts-ideation"}, "body")

    unlocked = approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "ideation")
    assert unlocked == ["scripting"]

    meta, _ = artifacts.parse_frontmatter((stage_dir / "artifact.v1.md").read_text(encoding="utf-8"))
    assert meta["status"] == "final"
    assert meta["finalized_at"] is not None

    ideation_row = db.get_stage(conn, project_id, "ideation")
    assert ideation_row["status"] == StageStatus.APPROVED.value
    assert ideation_row["approved_at"] is not None

    scripting_row = db.get_stage(conn, project_id, "scripting")
    assert scripting_row["status"] == StageStatus.READY.value


def test_approve_raises_when_no_artifact_exists(conn, tmp_path: Path):
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "ready")
    run_dir = tmp_path / "runs" / "abc-1"
    (run_dir / "01-ideation").mkdir(parents=True)
    with pytest.raises(ValueError):
        approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "ideation")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_approval_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_app.approval_service'`.

- [ ] **Step 3: Implement `approval_service.py`**

```python
import datetime
import sqlite3
from pathlib import Path

from pipeline_app import artifacts, db as db_mod
from pipeline_app.pipeline_config import StageDef, stage_dir_name
from pipeline_app.state_machine import StageStatus, stages_to_unlock


def approve_stage(
    conn: sqlite3.Connection,
    repo_root: Path,
    run_dir: Path,
    project_id: int,
    stage_defs: list[StageDef],
    stage_id: str,
) -> list[str]:
    stage_row = db_mod.get_stage(conn, project_id, stage_id)
    stage_def = next(s for s in stage_defs if s.id == stage_id)
    stage_dir = run_dir / stage_dir_name(stage_def)

    latest = artifacts.latest_artifact_path(stage_dir)
    if latest is None:
        raise ValueError(f"No artifact to approve for stage '{stage_id}'.")

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    artifacts.stamp_final(latest, now)
    db_mod.update_stage_status(conn, stage_row["id"], StageStatus.APPROVED.value, approved_at=now)

    all_rows = db_mod.list_stages(conn, project_id)
    approved_ids = {r["stage_id"] for r in all_rows if r["status"] == StageStatus.APPROVED.value}
    newly_unlocked = stages_to_unlock(stage_defs, approved_ids)

    for uid in newly_unlocked:
        row = db_mod.get_stage(conn, project_id, uid)
        if row is not None and row["status"] == StageStatus.LOCKED.value:
            db_mod.update_stage_status(conn, row["id"], StageStatus.READY.value)

    return newly_unlocked
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_approval_service.py tests/test_turn_service.py -v`
Expected: 2 passed (approval service) + 4 passed (turn service, now unblocked) = 6 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/approval_service.py pipeline-app/tests/test_approval_service.py
git commit -m "feat(pipeline-app): add approval service with stamp-then-hash ordering"
```

---

## Task 10: Grounding service (rgs-briefs attribution, pointer, supersede-on-regenerate)

**Files:**
- Create: `pipeline-app/pipeline_app/grounding_service.py`
- Test: `pipeline-app/tests/test_grounding_service.py`

**Interfaces:**
- Produces: `snapshot_rgs_briefs(rgs_briefs_dir: Path) -> set[str]`; `identify_new_brief(before,
  after) -> str | None`; `write_pointer(stage_dir, rgs_brief_relpath) -> Path`; `read_pointer
  (stage_dir) -> str | None`; `supersede_previous_brief(repo_root, stage_dir) -> None`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_grounding_service.py`:

```python
from pathlib import Path

from pipeline_app.grounding_service import (
    identify_new_brief,
    read_pointer,
    snapshot_rgs_briefs,
    supersede_previous_brief,
    write_pointer,
)


def test_snapshot_lists_md_files(tmp_path: Path):
    (tmp_path / "2026-07-25-a.md").write_text("x", encoding="utf-8")
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    snap = snapshot_rgs_briefs(tmp_path)
    assert snap == {"2026-07-25-a.md", "README.md"}


def test_identify_new_brief_when_exactly_one_new_file():
    before = {"a.md", "b.md"}
    after = {"a.md", "b.md", "c.md"}
    assert identify_new_brief(before, after) == "c.md"


def test_identify_new_brief_returns_none_when_zero_new_files():
    assert identify_new_brief({"a.md"}, {"a.md"}) is None


def test_identify_new_brief_returns_none_when_ambiguous():
    before = {"a.md"}
    after = {"a.md", "b.md", "c.md"}
    assert identify_new_brief(before, after) is None


def test_write_and_read_pointer_roundtrip(tmp_path: Path):
    stage_dir = tmp_path / "00-grounding"
    write_pointer(stage_dir, "rgs-briefs/2026-07-25-idea.md")
    assert read_pointer(stage_dir) == "rgs-briefs/2026-07-25-idea.md"


def test_read_pointer_none_when_missing(tmp_path: Path):
    assert read_pointer(tmp_path / "00-grounding") is None


def test_supersede_deletes_previously_pointed_file(tmp_path: Path):
    repo_root = tmp_path
    rgs_briefs = repo_root / "rgs-briefs"
    rgs_briefs.mkdir()
    old_brief = rgs_briefs / "2026-07-25-old.md"
    old_brief.write_text("old content", encoding="utf-8")
    stage_dir = repo_root / "runs" / "x" / "00-grounding"
    write_pointer(stage_dir, "rgs-briefs/2026-07-25-old.md")

    supersede_previous_brief(repo_root, stage_dir)

    assert not old_brief.exists()


def test_supersede_is_a_no_op_when_no_pointer(tmp_path: Path):
    stage_dir = tmp_path / "runs" / "x" / "00-grounding"
    stage_dir.mkdir(parents=True)
    supersede_previous_brief(tmp_path, stage_dir)  # should not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_grounding_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_app.grounding_service'`.

- [ ] **Step 3: Implement `grounding_service.py`**

```python
from pathlib import Path

import yaml


def snapshot_rgs_briefs(rgs_briefs_dir: Path) -> set[str]:
    if not rgs_briefs_dir.exists():
        return set()
    return {p.name for p in rgs_briefs_dir.glob("*.md")}


def identify_new_brief(before: set[str], after: set[str]) -> str | None:
    new_files = after - before
    if len(new_files) != 1:
        return None
    return next(iter(new_files))


def write_pointer(stage_dir: Path, rgs_brief_relpath: str) -> Path:
    stage_dir.mkdir(parents=True, exist_ok=True)
    pointer_path = stage_dir / "pointer.yaml"
    pointer_path.write_text(
        yaml.safe_dump({"rgs_brief_path": rgs_brief_relpath}, sort_keys=False),
        encoding="utf-8",
    )
    return pointer_path


def read_pointer(stage_dir: Path) -> str | None:
    pointer_path = stage_dir / "pointer.yaml"
    if not pointer_path.exists():
        return None
    data = yaml.safe_load(pointer_path.read_text(encoding="utf-8")) or {}
    return data.get("rgs_brief_path")


def supersede_previous_brief(repo_root: Path, stage_dir: Path) -> None:
    previous = read_pointer(stage_dir)
    if not previous:
        return
    previous_path = repo_root / previous
    if previous_path.exists():
        previous_path.unlink()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_grounding_service.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/grounding_service.py pipeline-app/tests/test_grounding_service.py
git commit -m "feat(pipeline-app): add grounding-stage rgs-briefs attribution and supersede logic"
```

---

## Task 11: `git_helper.py` — auto-commit for skill-file edits

**Files:**
- Create: `pipeline-app/pipeline_app/git_helper.py`
- Test: `pipeline-app/tests/test_git_helper.py`

**Interfaces:**
- Produces: `commit_skill_edit(repo_root: Path, file_path: Path, skill_name: str, now: str |
  None = None) -> None`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_git_helper.py`:

```python
import subprocess
from pathlib import Path

import pytest

from pipeline_app.git_helper import commit_skill_edit


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    return tmp_path


def test_commit_skill_edit_creates_a_commit(repo: Path):
    skill_file = repo / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("edited content", encoding="utf-8")

    commit_skill_edit(repo, skill_file, "shorts-ideation", now="2026-07-25")

    log = subprocess.run(
        ["git", "log", "--oneline", "-1"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout
    assert "shorts-ideation" in log
    assert "2026-07-25" in log
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_git_helper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_app.git_helper'`.

- [ ] **Step 3: Implement `git_helper.py`**

```python
import datetime
import subprocess
from pathlib import Path


def commit_skill_edit(repo_root: Path, file_path: Path, skill_name: str, now: str | None = None) -> None:
    now = now or datetime.date.today().isoformat()
    rel_path = file_path.relative_to(repo_root)
    message = f"skill edit: {skill_name} via pipeline-app, {now}"
    subprocess.run(["git", "add", str(rel_path)], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo_root, check=True, capture_output=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_git_helper.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/git_helper.py pipeline-app/tests/test_git_helper.py
git commit -m "feat(pipeline-app): add git auto-commit helper for skill-file edits"
```

---

## Task 12: FastAPI app skeleton, base template, and project routes

**Files:**
- Create: `pipeline-app/pipeline_app/main.py`
- Create: `pipeline-app/pipeline_app/routes/__init__.py`
- Create: `pipeline-app/pipeline_app/routes/projects.py`
- Create: `pipeline-app/pipeline_app/templates/base.html`
- Create: `pipeline-app/pipeline_app/templates/project_list.html`
- Create: `pipeline-app/pipeline_app/templates/project_home.html`
- Create: `pipeline-app/pipeline_app/static/style.css`
- Create: `pipeline-app/setup.py`
- Test: `pipeline-app/tests/test_routes_projects.py`

**Interfaces:**
- Consumes: `project_service.create_project` (Task 5), `db.list_projects`/`list_stages` (Task 4),
  `pipeline_config.load_topology` (Task 1).
- Produces: FastAPI `app` object in `pipeline_app.main`, with `app.state.conn`,
  `app.state.stage_defs`, `app.state.repo_root` set at startup; routes `GET /`, `POST /projects`,
  `GET /projects/{project_id}`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/setup.py` (needed so `pipeline_app` installs importable as a package):

```python
from setuptools import find_packages, setup

setup(
    name="pipeline-app",
    version="0.1.0",
    packages=find_packages(include=["pipeline_app", "pipeline_app.*"]),
    package_data={"pipeline_app": ["templates/*.html", "templates/partials/*.html", "static/*.css"]},
)
```

Create `pipeline-app/tests/test_routes_projects.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n    depends_on: [ideation]\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app)


def test_get_root_lists_no_projects_initially(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "No projects yet" in response.text


def test_create_project_then_appears_in_list(client: TestClient):
    response = client.post("/projects", data={"slug": "why-kids-quit", "brand": "generic"})
    assert response.status_code in (200, 303, 307)
    listing = client.get("/")
    assert "why-kids-quit" in listing.text


def test_project_home_shows_stage_names(client: TestClient):
    client.post("/projects", data={"slug": "why-kids-quit", "brand": "generic"})
    listing = client.get("/")
    # extract the project id from the link the template renders
    import re
    match = re.search(r'/projects/(\d+)', listing.text)
    assert match is not None
    project_id = match.group(1)
    home = client.get(f"/projects/{project_id}")
    assert home.status_code == 200
    assert "ideation" in home.text
    assert "scripting" in home.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_routes_projects.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_app.main'`.

- [ ] **Step 3: Implement the app skeleton**

`pipeline-app/pipeline_app/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{% block title %}ContentStudio Pipeline{% endblock %}</title>
  <link rel="stylesheet" href="/static/style.css">
  <script src="https://unpkg.com/htmx.org@2.0.0"></script>
</head>
<body>
  <header><a href="/">ContentStudio Pipeline</a></header>
  <main>{% block content %}{% endblock %}</main>
</body>
</html>
```

`pipeline-app/pipeline_app/templates/project_list.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>Projects</h1>
{% if projects %}
<ul>
  {% for p in projects %}
  <li><a href="/projects/{{ p.id }}">{{ p.run_id }}</a> ({{ p.brand }})</li>
  {% endfor %}
</ul>
{% else %}
<p>No projects yet.</p>
{% endif %}
<form method="post" action="/projects">
  <input name="slug" placeholder="short-topic-slug" required>
  <select name="brand">
    <option value="generic">Generic</option>
    <option value="raisinggoodsports">RaisingGoodSports</option>
  </select>
  <button type="submit">Create project</button>
</form>
{% endblock %}
```

`pipeline-app/pipeline_app/templates/project_home.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>{{ project.run_id }}</h1>
<ul>
  {% for stage in stages %}
  <li>
    <a href="/projects/{{ project.id }}/stages/{{ stage.stage_id }}">{{ stage.stage_id }}</a>
    — <span class="status status-{{ stage.status }}">{{ stage.status }}</span>
  </li>
  {% endfor %}
</ul>
{% endblock %}
```

`pipeline-app/pipeline_app/static/style.css`:

```css
body { font-family: system-ui, sans-serif; margin: 2rem; }
.status { padding: 0.1rem 0.5rem; border-radius: 0.25rem; font-size: 0.85rem; }
.status-locked { background: #ddd; }
.status-ready { background: #cfe8ff; }
.status-running { background: #fff3b0; }
.status-awaiting_review { background: #ffd9a0; }
.status-approved { background: #c6f0c2; }
.status-stale { background: #ffb3b3; }
.status-no_artifact { background: #ffb3b3; }
```

`pipeline-app/pipeline_app/routes/__init__.py`:

```python
```

(empty — marks the package)

`pipeline-app/pipeline_app/routes/projects.py`:

```python
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from pipeline_app import db as db_mod
from pipeline_app.project_service import create_project

router = APIRouter()


@router.get("/")
def list_projects(request: Request):
    conn = request.app.state.conn
    projects = db_mod.list_projects(conn)
    return request.app.state.templates.TemplateResponse(
        request, "project_list.html", {"projects": projects}
    )


@router.post("/projects")
def create_project_route(request: Request, slug: str = Form(...), brand: str = Form(...)):
    conn = request.app.state.conn
    result = create_project(
        conn, request.app.state.repo_root, slug, brand, request.app.state.stage_defs
    )
    return RedirectResponse(url=f"/projects/{result['project_id']}", status_code=303)


@router.get("/projects/{project_id}")
def project_home(request: Request, project_id: int):
    conn = request.app.state.conn
    project = db_mod.get_project(conn, project_id)
    stages = db_mod.list_stages(conn, project_id)
    return request.app.state.templates.TemplateResponse(
        request, "project_home.html", {"project": project, "stages": stages}
    )
```

`pipeline-app/pipeline_app/main.py`:

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pipeline_app import db as db_mod
from pipeline_app.pipeline_config import load_topology
from pipeline_app.routes import projects

PACKAGE_DIR = Path(__file__).resolve().parent


def create_app(repo_root: Path, db_path: Path) -> FastAPI:
    app = FastAPI()
    app.state.repo_root = repo_root
    app.state.stage_defs = load_topology(repo_root / "pipeline.yaml")

    schema_path = PACKAGE_DIR / "schema.sql"
    db_mod.init_db(db_path, schema_path)
    app.state.conn = db_mod.get_connection(db_path)

    app.state.templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static")

    app.include_router(projects.router)
    return app


# Default app instance for `uvicorn pipeline_app.main:app`
_REPO_ROOT = Path(__file__).resolve().parents[2]
app = create_app(repo_root=_REPO_ROOT, db_path=_REPO_ROOT / "pipeline-app" / "pipeline.db")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && pip install -e . && python -m pytest tests/test_routes_projects.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/setup.py pipeline-app/pipeline_app/main.py pipeline-app/pipeline_app/routes pipeline-app/pipeline_app/templates pipeline-app/pipeline_app/static pipeline-app/tests/test_routes_projects.py
git commit -m "feat(pipeline-app): add FastAPI app skeleton with project list/create/home routes"
```

---

## Task 13: Stage page (GET) — input panel, transcript from `events/*.jsonl`, output panel

**Files:**
- Create: `pipeline-app/pipeline_app/routes/stages.py`
- Create: `pipeline-app/pipeline_app/templates/stage.html`
- Modify: `pipeline-app/pipeline_app/main.py`
- Test: `pipeline-app/tests/test_routes_stages.py`

**Interfaces:**
- Consumes: `db.get_stage`, `artifacts.latest_artifact_path`/`parse_frontmatter`,
  `pipeline_config.stage_dir_name`.
- Produces: `GET /projects/{project_id}/stages/{stage_id}`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_routes_stages.py`:

```python
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app import artifacts
from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app), tmp_path, app


def test_stage_page_shows_input_output_and_transcript(client):
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    stage_dir = run_dir / "01-ideation"

    artifacts.write_artifact(stage_dir, 1, {"stage": "shorts-ideation", "status": "draft"}, "concept brief text")

    events_dir = stage_dir / "events"
    events_dir.mkdir()
    (events_dir / "1.jsonl").write_text(
        json.dumps({"type": "result", "result": "here is your concept brief"}) + "\n",
        encoding="utf-8",
    )

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert "concept brief text" in page.text
    assert "here is your concept brief" in page.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_routes_stages.py -v`
Expected: FAIL — `404 Not Found` (route doesn't exist yet).

- [ ] **Step 3: Implement the stage route and template**

`pipeline-app/pipeline_app/templates/stage.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>{{ project.run_id }} — {{ stage_id }}</h1>

<section class="input-panel">
  <h2>Input</h2>
  {% if input_body %}<pre>{{ input_body }}</pre>{% else %}<p>No upstream input.</p>{% endif %}
</section>

<section class="chat-panel">
  <h2>Chat</h2>
  <div id="transcript">
    {% for message in transcript %}
    <p><strong>{{ message.type }}:</strong> {{ message.text }}</p>
    {% endfor %}
  </div>
  <form hx-post="/projects/{{ project.id }}/stages/{{ stage_id }}/chat" hx-target="#transcript" hx-swap="beforeend">
    <textarea name="message"></textarea>
    <button type="submit">Send</button>
  </form>
</section>

<section class="output-panel">
  <h2>Output</h2>
  {% if output_body %}<pre>{{ output_body }}</pre>{% else %}<p>No output yet.</p>{% endif %}
  <form method="post" action="/projects/{{ project.id }}/stages/{{ stage_id }}/approve">
    <button type="submit">Mark Approved</button>
  </form>
</section>
{% endblock %}
```

`pipeline-app/pipeline_app/routes/stages.py`:

```python
import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from pipeline_app import artifacts, db as db_mod
from pipeline_app.pipeline_config import stage_dir_name

router = APIRouter()


def _load_transcript(stage_dir):
    events_dir = stage_dir / "events"
    messages = []
    if not events_dir.exists():
        return messages
    for events_file in sorted(events_dir.glob("*.jsonl")):
        for line in events_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("type") == "result":
                messages.append({"type": "assistant", "text": event.get("result", "")})
    return messages


@router.get("/projects/{project_id}/stages/{stage_id}", response_class=HTMLResponse)
def stage_page(request: Request, project_id: int, stage_id: str):
    conn = request.app.state.conn
    project = db_mod.get_project(conn, project_id)
    stage_defs = request.app.state.stage_defs
    stage_def = next(s for s in stage_defs if s.id == stage_id)
    run_dir = request.app.state.repo_root / "runs" / project["run_id"]
    stage_dir = run_dir / stage_dir_name(stage_def)

    input_body = None
    if stage_def.depends_on:
        up_def = next(s for s in stage_defs if s.id == stage_def.depends_on[0])
        up_dir = run_dir / stage_dir_name(up_def)
        up_latest = artifacts.latest_artifact_path(up_dir)
        if up_latest is not None:
            _, input_body = artifacts.parse_frontmatter(up_latest.read_text(encoding="utf-8"))

    output_body = None
    latest = artifacts.latest_artifact_path(stage_dir)
    if latest is not None:
        _, output_body = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))

    transcript = _load_transcript(stage_dir)

    return request.app.state.templates.TemplateResponse(
        request, "stage.html",
        {
            "project": project, "stage_id": stage_id,
            "input_body": input_body, "output_body": output_body,
            "transcript": transcript,
        },
    )
```

Register the router in `pipeline-app/pipeline_app/main.py` — add the import and
`app.include_router(stages.router)`:

```python
from pipeline_app.routes import projects, stages
```

```python
    app.include_router(projects.router)
    app.include_router(stages.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_routes_stages.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/routes/stages.py pipeline-app/pipeline_app/templates/stage.html pipeline-app/pipeline_app/main.py pipeline-app/tests/test_routes_stages.py
git commit -m "feat(pipeline-app): add stage page with input/transcript/output panels"
```

---

## Task 14: SSE chat endpoint (wires `turn_service` as a streaming response)

**Files:**
- Modify: `pipeline-app/pipeline_app/routes/stages.py`
- Test: `pipeline-app/tests/test_routes_chat_sse.py`

**Interfaces:**
- Consumes: `turn_service.run_stage_turn` (Task 8).
- Produces: `POST /projects/{project_id}/stages/{stage_id}/chat` — `StreamingResponse` with
  `media_type="text/event-stream"`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_routes_chat_sse.py`:

```python
from pathlib import Path
from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from pipeline_app import turn_service
from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app), app


def test_chat_endpoint_streams_sse_events(client, monkeypatch):
    test_client, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    async def fake_run_stage_turn(*args, **kwargs) -> AsyncIterator[dict]:
        yield {"type": "system", "subtype": "init", "session_id": "s1"}
        yield {"type": "result", "result": "concept brief drafted"}

    monkeypatch.setattr(turn_service, "run_stage_turn", fake_run_stage_turn)

    with test_client.stream(
        "POST", f"/projects/{project_id}/stages/ideation/chat",
        data={"message": "a Short about burnout"},
    ) as response:
        body = "".join(response.iter_text())

    assert "concept brief drafted" in body
    assert "data:" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_routes_chat_sse.py -v`
Expected: FAIL — `404 Not Found`.

- [ ] **Step 3: Implement the SSE route**

Add to `pipeline-app/pipeline_app/routes/stages.py`:

```python
import json as _json  # (json is already imported above; reuse the existing import)

from fastapi import Form
from fastapi.responses import StreamingResponse

from pipeline_app import grounding_service, turn_service
```

```python
@router.post("/projects/{project_id}/stages/{stage_id}/chat")
async def stage_chat(request: Request, project_id: int, stage_id: str, message: str = Form(...)):
    conn = request.app.state.conn
    repo_root = request.app.state.repo_root
    stage_defs = request.app.state.stage_defs
    project = db_mod.get_project(conn, project_id)
    stage_def = next(s for s in stage_defs if s.id == stage_id)
    run_dir = repo_root / "runs" / project["run_id"]
    templates_dir = repo_root / "pipeline-app" / "stage_templates"

    grounding_pointer = None
    if project["brand"] == "raisinggoodsports" and stage_id != "grounding":
        grounding_dir = run_dir / "00-grounding"
        grounding_pointer = grounding_service.read_pointer(grounding_dir)

    async def event_stream():
        async for event in turn_service.run_stage_turn(
            conn, repo_root, run_dir, templates_dir,
            project_id, project["run_id"], stage_def, stage_defs, message,
            grounding_pointer=grounding_pointer,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_routes_chat_sse.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/routes/stages.py pipeline-app/tests/test_routes_chat_sse.py
git commit -m "feat(pipeline-app): stream chat turns to the browser over SSE"
```

---

## Task 15: Approve / hand-edit-output routes

**Files:**
- Modify: `pipeline-app/pipeline_app/routes/stages.py`
- Test: `pipeline-app/tests/test_routes_approve_edit.py`

**Interfaces:**
- Consumes: `approval_service.approve_stage` (Task 9), `artifacts.write_artifact`/
  `next_version_number` (Task 2).
- Produces: `POST /projects/{project_id}/stages/{stage_id}/approve`; `POST
  /projects/{project_id}/stages/{stage_id}/edit`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_routes_approve_edit.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app import artifacts
from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app), tmp_path, app


def test_approve_route_stamps_artifact_final(client):
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    stage_dir = tmp_path / "runs" / project["run_id"] / "01-ideation"
    artifacts.write_artifact(stage_dir, 1, {"stage": "shorts-ideation", "status": "draft"}, "body")

    approve_resp = test_client.post(f"/projects/{project_id}/stages/ideation/approve")
    assert approve_resp.status_code in (200, 303, 307)

    meta, _ = artifacts.parse_frontmatter((stage_dir / "artifact.v1.md").read_text(encoding="utf-8"))
    assert meta["status"] == "final"


def test_edit_route_writes_new_version(client):
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    stage_dir = tmp_path / "runs" / project["run_id"] / "01-ideation"
    artifacts.write_artifact(stage_dir, 1, {"stage": "shorts-ideation", "status": "draft"}, "old body")

    edit_resp = test_client.post(
        f"/projects/{project_id}/stages/ideation/edit", data={"body": "hand-edited body"}
    )
    assert edit_resp.status_code in (200, 303, 307)
    assert (stage_dir / "artifact.v2.md").exists()
    meta, body = artifacts.parse_frontmatter((stage_dir / "artifact.v2.md").read_text(encoding="utf-8"))
    assert meta["supersedes"] == "artifact.v1.md"
    assert "hand-edited body" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_routes_approve_edit.py -v`
Expected: FAIL — `404 Not Found` for both routes.

- [ ] **Step 3: Implement the routes**

Add to `pipeline-app/pipeline_app/routes/stages.py`:

```python
import datetime

from fastapi.responses import RedirectResponse

from pipeline_app import approval_service
```

```python
@router.post("/projects/{project_id}/stages/{stage_id}/approve")
def approve_stage_route(request: Request, project_id: int, stage_id: str):
    conn = request.app.state.conn
    repo_root = request.app.state.repo_root
    stage_defs = request.app.state.stage_defs
    project = db_mod.get_project(conn, project_id)
    run_dir = repo_root / "runs" / project["run_id"]
    approval_service.approve_stage(conn, repo_root, run_dir, project_id, stage_defs, stage_id)
    return RedirectResponse(url=f"/projects/{project_id}/stages/{stage_id}", status_code=303)


@router.post("/projects/{project_id}/stages/{stage_id}/edit")
def edit_stage_output_route(request: Request, project_id: int, stage_id: str, body: str = Form(...)):
    conn = request.app.state.conn
    repo_root = request.app.state.repo_root
    stage_defs = request.app.state.stage_defs
    project = db_mod.get_project(conn, project_id)
    stage_def = next(s for s in stage_defs if s.id == stage_id)
    run_dir = repo_root / "runs" / project["run_id"]
    stage_dir = run_dir / stage_dir_name(stage_def)

    latest = artifacts.latest_artifact_path(stage_dir)
    prior_meta = {}
    if latest is not None:
        prior_meta, _ = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))

    version = artifacts.next_version_number(stage_dir)
    meta = {
        "schema_version": 1,
        "run_id": project["run_id"],
        "stage": stage_def.skill,
        "version": version,
        "status": "draft",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "finalized_at": None,
        "supersedes": f"artifact.v{version - 1}.md" if version > 1 else None,
        "depends_on": prior_meta.get("depends_on", []),
    }
    artifacts.write_artifact(stage_dir, version, meta, body)
    return RedirectResponse(url=f"/projects/{project_id}/stages/{stage_id}", status_code=303)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_routes_approve_edit.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/routes/stages.py pipeline-app/tests/test_routes_approve_edit.py
git commit -m "feat(pipeline-app): add approve and hand-edit-output routes"
```

---

## Task 16: Skill editor (view/edit `SKILL.md`, references, and kickoff templates)

**Files:**
- Create: `pipeline-app/pipeline_app/routes/skills.py`
- Create: `pipeline-app/pipeline_app/templates/skill_editor.html`
- Create: `pipeline-app/pipeline_app/templates/skill_list.html`
- Modify: `pipeline-app/pipeline_app/main.py`
- Test: `pipeline-app/tests/test_routes_skills.py`

**Interfaces:**
- Consumes: `git_helper.commit_skill_edit` (Task 11).
- Produces: `GET /skills`, `GET /skills/{skill_name}`, `POST /skills/{skill_name}/save`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_routes_skills.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app import git_helper
from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    skill_dir = tmp_path / ".claude" / "skills" / "shorts-ideation"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("original content", encoding="utf-8")
    (tmp_path / "pipeline-app" / "stage_templates").mkdir(parents=True)
    (tmp_path / "pipeline-app" / "stage_templates" / "ideation.md").write_text("/shorts-ideation", encoding="utf-8")
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app), tmp_path


def test_skill_list_shows_discovered_skill(client):
    test_client, tmp_path = client
    resp = test_client.get("/skills")
    assert resp.status_code == 200
    assert "shorts-ideation" in resp.text


def test_skill_detail_shows_skill_md_content(client):
    test_client, tmp_path = client
    resp = test_client.get("/skills/shorts-ideation")
    assert resp.status_code == 200
    assert "original content" in resp.text


def test_save_skill_md_writes_file_and_commits(client, monkeypatch):
    test_client, tmp_path = client
    calls = []
    monkeypatch.setattr(
        git_helper, "commit_skill_edit",
        lambda repo_root, file_path, skill_name, now=None: calls.append((file_path, skill_name)),
    )
    resp = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "SKILL.md", "content": "edited content"},
    )
    assert resp.status_code in (200, 303, 307)
    saved = (tmp_path / ".claude" / "skills" / "shorts-ideation" / "SKILL.md").read_text(encoding="utf-8")
    assert saved == "edited content"
    assert len(calls) == 1


def test_save_kickoff_template_does_not_commit(client, monkeypatch):
    test_client, tmp_path = client
    calls = []
    monkeypatch.setattr(
        git_helper, "commit_skill_edit",
        lambda *a, **k: calls.append(1),
    )
    resp = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "kickoff_template", "content": "/shorts-ideation new kickoff"},
    )
    assert resp.status_code in (200, 303, 307)
    saved = (tmp_path / "pipeline-app" / "stage_templates" / "ideation.md").read_text(encoding="utf-8")
    assert saved == "/shorts-ideation new kickoff"
    assert calls == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_routes_skills.py -v`
Expected: FAIL — `404 Not Found`.

- [ ] **Step 3: Implement the skill editor**

`pipeline-app/pipeline_app/templates/skill_list.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>Skills</h1>
<ul>
  {% for name in skill_names %}
  <li><a href="/skills/{{ name }}">{{ name }}</a></li>
  {% endfor %}
</ul>
{% endblock %}
```

`pipeline-app/pipeline_app/templates/skill_editor.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>{{ skill_name }}</h1>

<h2>SKILL.md</h2>
<form method="post" action="/skills/{{ skill_name }}/save">
  <input type="hidden" name="target" value="SKILL.md">
  <textarea name="content" rows="20" cols="100">{{ skill_md_content }}</textarea>
  <button type="submit">Save SKILL.md</button>
</form>

<h2>Kickoff template</h2>
<form method="post" action="/skills/{{ skill_name }}/save">
  <input type="hidden" name="target" value="kickoff_template">
  <textarea name="content" rows="10" cols="100">{{ kickoff_template_content }}</textarea>
  <button type="submit">Save kickoff template</button>
</form>
{% endblock %}
```

`pipeline-app/pipeline_app/routes/skills.py`:

```python
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from pipeline_app import git_helper

router = APIRouter()

STAGE_ID_BY_SKILL = {
    "rgs-grounding": "grounding",
    "shorts-ideation": "ideation",
    "shorts-scripting": "scripting",
    "voiceover-brief": "voiceover",
    "visual-prompts": "visual",
    "shorts-assembly": "assembly",
    "social-repurpose": "repurpose",
    "rgs-pairing-review": None,
}


@router.get("/skills")
def skill_list(request: Request):
    skills_dir = request.app.state.repo_root / ".claude" / "skills"
    skill_names = sorted(p.name for p in skills_dir.iterdir() if p.is_dir())
    return request.app.state.templates.TemplateResponse(
        request, "skill_list.html", {"skill_names": skill_names}
    )


@router.get("/skills/{skill_name}")
def skill_detail(request: Request, skill_name: str):
    repo_root = request.app.state.repo_root
    skill_md_path = repo_root / ".claude" / "skills" / skill_name / "SKILL.md"
    skill_md_content = skill_md_path.read_text(encoding="utf-8") if skill_md_path.exists() else ""

    stage_id = STAGE_ID_BY_SKILL.get(skill_name)
    kickoff_template_content = ""
    if stage_id:
        template_path = repo_root / "pipeline-app" / "stage_templates" / f"{stage_id}.md"
        if template_path.exists():
            kickoff_template_content = template_path.read_text(encoding="utf-8")

    return request.app.state.templates.TemplateResponse(
        request, "skill_editor.html",
        {
            "skill_name": skill_name,
            "skill_md_content": skill_md_content,
            "kickoff_template_content": kickoff_template_content,
        },
    )


@router.post("/skills/{skill_name}/save")
def save_skill(request: Request, skill_name: str, target: str = Form(...), content: str = Form(...)):
    repo_root = request.app.state.repo_root
    if target == "SKILL.md":
        path = repo_root / ".claude" / "skills" / skill_name / "SKILL.md"
        path.write_text(content, encoding="utf-8")
        git_helper.commit_skill_edit(repo_root, path, skill_name)
    elif target == "kickoff_template":
        stage_id = STAGE_ID_BY_SKILL.get(skill_name)
        path = repo_root / "pipeline-app" / "stage_templates" / f"{stage_id}.md"
        path.write_text(content, encoding="utf-8")
    return RedirectResponse(url=f"/skills/{skill_name}", status_code=303)
```

Register the router in `main.py`:

```python
from pipeline_app.routes import projects, skills, stages
```

```python
    app.include_router(skills.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_routes_skills.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/routes/skills.py pipeline-app/pipeline_app/templates/skill_editor.html pipeline-app/pipeline_app/templates/skill_list.html pipeline-app/pipeline_app/main.py pipeline-app/tests/test_routes_skills.py
git commit -m "feat(pipeline-app): add skill editor with git auto-commit for SKILL.md edits"
```

---

## Task 17: MD inspector

**Files:**
- Create: `pipeline-app/pipeline_app/routes/inspector.py`
- Create: `pipeline-app/pipeline_app/templates/inspector.html`
- Modify: `pipeline-app/pipeline_app/main.py`
- Test: `pipeline-app/tests/test_routes_inspector.py`

**Interfaces:**
- Consumes: `artifacts.parse_frontmatter` (Task 2), `markdown.markdown`.
- Produces: `GET /inspector`, `POST /inspector`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_routes_inspector.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app), tmp_path


def test_inspector_form_renders(client):
    test_client, _ = client
    resp = test_client.get("/inspector")
    assert resp.status_code == 200


def test_inspector_parses_frontmatter_and_body(client):
    test_client, tmp_path = client
    fixture = tmp_path / "fixture.md"
    fixture.write_text(
        "---\nstage: shorts-ideation\nversion: 1\n---\n\n# Concept Brief\n\nBody text.\n",
        encoding="utf-8",
    )
    resp = test_client.post("/inspector", data={"path": str(fixture)})
    assert resp.status_code == 200
    assert "shorts-ideation" in resp.text
    assert "Concept Brief" in resp.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_routes_inspector.py -v`
Expected: FAIL — `404 Not Found`.

- [ ] **Step 3: Implement the inspector**

`pipeline-app/pipeline_app/templates/inspector.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>MD Inspector</h1>
<form method="post" action="/inspector">
  <input name="path" size="80" placeholder="Absolute or repo-relative path to a .md file" value="{{ path or '' }}">
  <button type="submit">Inspect</button>
</form>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
{% if frontmatter %}
<h2>Frontmatter</h2>
<table>
  {% for key, value in frontmatter.items() %}
  <tr><th>{{ key }}</th><td>{{ value }}</td></tr>
  {% endfor %}
</table>
<h2>Body</h2>
<div>{{ body_html | safe }}</div>
{% endif %}
{% endblock %}
```

`pipeline-app/pipeline_app/routes/inspector.py`:

```python
from pathlib import Path

import markdown
from fastapi import APIRouter, Form, Request

from pipeline_app import artifacts

router = APIRouter()


@router.get("/inspector")
def inspector_form(request: Request):
    return request.app.state.templates.TemplateResponse(request, "inspector.html", {})


@router.post("/inspector")
def inspector_inspect(request: Request, path: str = Form(...)):
    file_path = Path(path)
    if not file_path.exists() or file_path.suffix != ".md":
        return request.app.state.templates.TemplateResponse(
            request, "inspector.html", {"path": path, "error": "Not a valid .md file path."}
        )
    meta, body = artifacts.parse_frontmatter(file_path.read_text(encoding="utf-8"))
    return request.app.state.templates.TemplateResponse(
        request, "inspector.html",
        {"path": path, "frontmatter": meta, "body_html": markdown.markdown(body)},
    )
```

Register in `main.py`:

```python
from pipeline_app.routes import inspector, projects, skills, stages
```

```python
    app.include_router(inspector.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_routes_inspector.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/routes/inspector.py pipeline-app/pipeline_app/templates/inspector.html pipeline-app/pipeline_app/main.py pipeline-app/tests/test_routes_inspector.py
git commit -m "feat(pipeline-app): add standalone MD frontmatter inspector"
```

---

## Task 18: Doctor page, preflight check, and startup reconciliation

**Files:**
- Create: `pipeline-app/pipeline_app/preflight.py`
- Create: `pipeline-app/pipeline_app/routes/doctor.py`
- Create: `pipeline-app/pipeline_app/templates/doctor.html`
- Modify: `pipeline-app/pipeline_app/main.py`
- Test: `pipeline-app/tests/test_preflight.py`
- Test: `pipeline-app/tests/test_routes_doctor.py`

**Interfaces:**
- Consumes: `db.list_running_turns`/`update_turn` (Task 4), `cli_runner.resolve_claude_binary`
  (Task 6).
- Produces: `reconcile_orphaned_turns(conn) -> int` (count marked orphaned); `check_cli_available
  (which_fn=shutil.which) -> dict` with keys `available`, `path`, `error`; `GET /doctor`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_preflight.py`:

```python
from pathlib import Path

import pytest

from pipeline_app import db
from pipeline_app.preflight import check_cli_available, reconcile_orphaned_turns


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


def test_reconcile_marks_running_turns_as_orphaned(conn):
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "running")
    db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:00:00Z", "events/x.jsonl")

    count = reconcile_orphaned_turns(conn)
    assert count == 1
    rows = db.list_turns(conn, stage_row_id)
    assert rows[0]["status"] == "orphaned"


def test_reconcile_is_a_no_op_when_nothing_running(conn):
    assert reconcile_orphaned_turns(conn) == 0


def test_check_cli_available_true_when_binary_found():
    result = check_cli_available(which_fn=lambda name: r"C:\fake\claude.CMD")
    assert result["available"] is True
    assert result["path"] == r"C:\fake\claude.CMD"


def test_check_cli_available_false_when_missing():
    result = check_cli_available(which_fn=lambda name: None)
    assert result["available"] is False
    assert result["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_preflight.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_app.preflight'`.

- [ ] **Step 3: Implement `preflight.py`, the doctor route, and startup reconciliation**

`pipeline-app/pipeline_app/preflight.py`:

```python
import shutil
import sqlite3
from typing import Callable

from pipeline_app import db as db_mod
from pipeline_app.cli_runner import resolve_claude_binary


def reconcile_orphaned_turns(conn: sqlite3.Connection) -> int:
    running = db_mod.list_running_turns(conn)
    for turn in running:
        db_mod.update_turn(conn, turn["id"], "orphaned")
    return len(running)


def check_cli_available(which_fn: Callable[[str], str | None] = shutil.which) -> dict:
    try:
        path = resolve_claude_binary(which_fn)
        return {"available": True, "path": path, "error": None}
    except FileNotFoundError as exc:
        return {"available": False, "path": None, "error": str(exc)}
```

`pipeline-app/pipeline_app/templates/doctor.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>Doctor</h1>
<ul>
  <li>Repo root: {{ repo_root }}</li>
  <li>DB path: {{ db_path }}</li>
  <li>Claude CLI: {% if cli.available %}found at {{ cli.path }}{% else %}NOT FOUND — {{ cli.error }}{% endif %}</li>
  <li>Skills discovered: {{ skill_names | join(", ") }}</li>
  <li>Orphaned turns reconciled at startup: {{ orphaned_count }}</li>
</ul>
{% endblock %}
```

`pipeline-app/pipeline_app/routes/doctor.py`:

```python
from fastapi import APIRouter, Request

from pipeline_app.preflight import check_cli_available

router = APIRouter()


@router.get("/doctor")
def doctor_page(request: Request):
    repo_root = request.app.state.repo_root
    skills_dir = repo_root / ".claude" / "skills"
    skill_names = sorted(p.name for p in skills_dir.iterdir() if p.is_dir()) if skills_dir.exists() else []
    return request.app.state.templates.TemplateResponse(
        request, "doctor.html",
        {
            "repo_root": str(repo_root),
            "db_path": str(getattr(request.app.state, "db_path", "")),
            "cli": check_cli_available(),
            "skill_names": skill_names,
            "orphaned_count": getattr(request.app.state, "orphaned_count", 0),
        },
    )
```

In `pipeline-app/pipeline_app/main.py`, register the doctor router, store `db_path` on
`app.state`, and run reconciliation at startup:

```python
from pipeline_app import preflight
from pipeline_app.routes import doctor, inspector, projects, skills, stages
```

```python
def create_app(repo_root: Path, db_path: Path) -> FastAPI:
    app = FastAPI()
    app.state.repo_root = repo_root
    app.state.db_path = db_path
    app.state.stage_defs = load_topology(repo_root / "pipeline.yaml")

    schema_path = PACKAGE_DIR / "schema.sql"
    db_mod.init_db(db_path, schema_path)
    app.state.conn = db_mod.get_connection(db_path)
    app.state.orphaned_count = preflight.reconcile_orphaned_turns(app.state.conn)

    app.state.templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static")

    app.include_router(projects.router)
    app.include_router(stages.router)
    app.include_router(skills.router)
    app.include_router(inspector.router)
    app.include_router(doctor.router)
    return app
```

- [ ] **Step 4: Run test to verify it passes**

Create `pipeline-app/tests/test_routes_doctor.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app


def test_doctor_page_renders_without_real_claude_installed(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    client = TestClient(app)
    resp = client.get("/doctor")
    assert resp.status_code == 200
    assert "Claude CLI" in resp.text
```

Run: `cd pipeline-app && python -m pytest tests/test_preflight.py tests/test_routes_doctor.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/preflight.py pipeline-app/pipeline_app/routes/doctor.py pipeline-app/pipeline_app/templates/doctor.html pipeline-app/pipeline_app/main.py pipeline-app/tests/test_preflight.py pipeline-app/tests/test_routes_doctor.py
git commit -m "feat(pipeline-app): add doctor page, preflight check, and startup reconciliation"
```

---

## Task 19: Optional end-to-end integration test (real `claude` CLI, skipped by default)

**Files:**
- Create: `pipeline-app/tests/integration/test_real_cli_e2e.py`
- Create: `pipeline-app/tests/integration/__init__.py`

**Interfaces:**
- Consumes: everything above, run against the real `claude` binary.

- [ ] **Step 1: Write the test (already in its final form — this task has no separate "make it pass" step, since it exercises real infrastructure and is gated by an environment variable)**

Create `pipeline-app/tests/integration/__init__.py`:

```python
```

Create `pipeline-app/tests/integration/test_real_cli_e2e.py`:

```python
import os
from pathlib import Path

import pytest

from pipeline_app import artifacts, db, turn_service
from pipeline_app.pipeline_config import StageDef
from pipeline_app.project_service import create_project

pytestmark = pytest.mark.skipif(
    os.environ.get("PIPELINE_APP_RUN_INTEGRATION") != "1",
    reason="Costs real Claude Code subscription usage — set PIPELINE_APP_RUN_INTEGRATION=1 to run.",
)

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES_DIR = REPO_ROOT / "pipeline-app" / "stage_templates"

STAGES = [StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[])]


@pytest.mark.asyncio
async def test_real_ideation_turn_produces_an_artifact(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = REPO_ROOT / "pipeline-app" / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    conn = db.get_connection(db_path)

    result = create_project(conn, REPO_ROOT, "integration-test-topic", "generic", STAGES)

    async for _ in turn_service.run_stage_turn(
        conn, REPO_ROOT, result["run_dir"], TEMPLATES_DIR,
        result["project_id"], result["run_id"], STAGES[0], STAGES,
        "a Short about why beginner runners overtrain",
    ):
        pass

    stage_dir = result["run_dir"] / "01-ideation"
    latest = artifacts.latest_artifact_path(stage_dir)
    assert latest is not None
    conn.close()
```

- [ ] **Step 2: Verify it's skipped by default**

Run: `cd pipeline-app && python -m pytest tests/integration/ -v`
Expected: 1 skipped.

- [ ] **Step 3: Commit**

```bash
git add pipeline-app/tests/integration
git commit -m "test(pipeline-app): add opt-in real-CLI end-to-end integration test"
```

---

## Self-Review

**1. Spec coverage.** Walking `docs/superpowers/specs/2026-07-25-local-pipeline-control-app-design.md`
section by section:
- §1 Architecture → Tasks 6, 8, 12–14.
- §2 Storage layout (`runs/<run_id>/NN-<stage>/artifact.vN.md`, frontmatter, versioning,
  grounding pointer) → Tasks 1, 2, 5, 8, 10.
- §3 `pipeline.yaml` topology → Task 1.
- §4 Stage state machine → Task 3, exercised end-to-end in Task 8.
- §5 Claude CLI integration contract (permissions, cwd, session bookkeeping, per-stage sessions,
  artifact verification, preflight, grounding pass-through) → Tasks 6, 7, 8, 18.
- §6 UI/navigation (sidebar, breadcrumb, project home, stage layout) → Tasks 12–13. *Gap found
  during self-review:* the plan as drafted did not include the persistent sidebar/breadcrumb
  chrome described in the design. Since every route renders through `base.html`, this is folded
  into Task 12 as an addition rather than a new task — see the fix below.
- §7 Skill editor → Task 16.
- §8 MD inspector & Doctor → Tasks 17, 18.
- §9 Error handling → Tasks 8 (`no_artifact` state), 18 (preflight/orphaned turns), all route
  tasks return explicit states rather than uncaught exceptions.
- §10 Testing → every task is TDD; Task 19 is the integration-test tier.

**Fix applied:** `base.html` (Task 12) is extended with a sidebar block placeholder and each
page that has project/stage context (`project_home.html`, `stage.html`) now passes a `stages`
list so the sidebar can render. Concretely, add to `base.html` between `<header>` and `<main>`:

```html
{% block sidebar %}{% endblock %}
```

And in `project_home.html` / `stage.html`, wrap the stage-listing content in `{% block sidebar %}`
instead of `{% block content %}` for the stage list, keeping `{% block content %}` for the
page-specific body. This is a template-only change with no new test required beyond the existing
Task 12/13 assertions (which already check that stage names appear in the response body — the
block a name renders in doesn't change that assertion).

**2. Placeholder scan.** Searched every task for "TBD", "TODO", "similar to Task N", and
"appropriate error handling" — none found. Every code step contains complete, runnable code.

**3. Type/signature consistency.** Verified across tasks:
- `StageDef` (Task 1) fields (`id`, `skill`, `dir_prefix`, `depends_on`, `brand_scope`) are used
  identically in Tasks 3, 5, 8, 9, 13–16.
- `stage_dir_name(stage: StageDef) -> str` (Task 1) is imported and used with the same signature
  in Tasks 8, 9, 13, 15.
- `StageStatus` enum values (Task 3) match the `.value` strings written to SQLite in Tasks 5, 8,
  9, and read back in Task 13's status badges.
- `run_stage_turn(...)` signature is defined once in Task 8 and called identically (same
  positional order) in Tasks 8's own tests, Task 14's route, and Task 19's integration test.
- `TurnResult` fields (`session_id`, `result_text`, `cost_usd`, `success`) are produced in Task 6
  and consumed with the same names in Task 8.
- `approve_stage(conn, repo_root, run_dir, project_id, stage_defs, stage_id)` signature (Task 9)
  matches its call site in Task 8's test and Task 15's route.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-25-local-pipeline-control-app.md`. Two
execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between
tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution
with checkpoints

**Which approach?**
