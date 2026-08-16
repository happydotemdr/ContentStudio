# P5 — Skill editor & git

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` or
> `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. The orchestration plan's
> **Global Constraints**, **test standard** and **Frozen interfaces**
> ([`../2026-08-08-audit-remediation.md`](../2026-08-08-audit-remediation.md)) are binding and are
> not restated here.

**Wave:** B (after P0's conftest/CI and P1's `obs.py` + `events` table land).
**Suite:** app suite only — `cd pipeline-app && python -m pytest`.

---

## 1. Scope

**Files this package owns (no other package may touch these):**

- `pipeline-app/pipeline_app/routes/skills.py`
- `pipeline-app/pipeline_app/git_helper.py`
- `pipeline-app/pipeline_app/routes/projects.py`
- `pipeline-app/pipeline_app/project_service.py`
- `pipeline-app/pipeline_app/routes/inspector.py`
- `pipeline-app/tests/test_routes_skills.py`
- `pipeline-app/tests/test_routes_projects.py`
- `pipeline-app/tests/test_project_service.py`
- `pipeline-app/tests/test_git_helper.py`
- `pipeline-app/tests/test_routes_inspector.py`

**Finding IDs (15):** A-48, A-49, A-50, A-51, A-52, A-53, A-54, A-55, A-56, A-78, A-79,
D-49, D-50, D-51, F-21.

**`routes/inspector.py` carries none of the 15**, and its *error handling* is already the shape this
audit is demanding everywhere else: every failure mode (`:30-39`) becomes a named UI error string
rendered back into `inspector.html`, not a bare 500 and not a silent empty result. Treat that part
as a reference implementation and do not touch it. It has exactly **one** work item, and it comes
from outside this package's finding set: **T20** applies the repo-wide `| safe` rule to
`inspector.py:45`, the last producer site of unsanitized HTML in this package's files. Add nothing
else to this file and do not invent findings for it.

**Files this package reads but must NOT edit** (owned elsewhere — a change there is a merge
collision): `pipeline_app/db.py` and `pipeline_app/schema.sql` (P1), `pipeline_app/obs.py` (P1),
`pipeline_app/pipeline_config.py` and `pipeline.yaml` (P4), `pipeline_app/templates/**` and
`browse_service.py` (P15), `.claude/skills/**` (P13). Where behaviour in this package needs one of
those to change, it is written up in §6 (P4) or §7 (everyone else) — never implemented here.
Importing from them is fine; T20 imports `browse_service.sanitize_html` and does not edit
`browse_service.py`.

**Repo-wide rule adopted here (orchestrator ruling on D-47): `| safe` means "sanitized by its
producer."** P15 publishes `browse_service.sanitize_html(html: str) -> str` — a stdlib
`html.parser` allowlist filter, no new dependency. P3 adopted producer-side sanitization in
`_stage_context`, and this package does the same in `inspector_inspect`. **Do not add a
template-side filter**: a consumer-side filter has to be reapplied at every `| safe` site and fails
open the moment someone forgets one. The producer sanitizes; the template renders `| safe` with no
filter of its own.

**The archetype this package exists to kill.** `save_skill` (`routes/skills.py:87-95`) has an
`if`/`elif` with no `else` and an unconditional `RedirectResponse` at `:95`. A save that wrote
nothing returns the *identical* 303 to a save that wrote everything. Every write path below gets a
**distinguishability test**: the wire response for "wrote and committed", "wrote but did not
commit", and "wrote nothing" must be three observably different things.

---

## 2. Finding → task map

Total coverage: all 15 IDs, each with at least one task.

| Finding | Sev | Failure mode | Task(s) |
|---|---|---|---|
| A-48 · `STAGE_ID_BY_SKILL` duplicates `pipeline.yaml` and has drifted (no `shorts-styleboard`) | S2 | silent | T2, T3, T15, T19 |
| A-49 · Unknown `target` 303s as though the save succeeded | S2 | silent | T4, T15 |
| A-50 · Kickoff save for an unmapped skill writes `stage_templates/None.md` | S2 | silent | T5, T15 |
| A-51 · `save_skill` accepts empty content and truncates a SKILL.md | S1 | silent | T6, T7, T8, T15 |
| A-52 · Kickoff-template saves are never committed | S1 | silent | T14, T15 |
| A-53 · `commit_skill_edit` commits the entire index | S2 | silent | T10 |
| A-54 · A git failure 500s the save after the file is written | S3 | loud | T13 |
| A-55 · Every browser save doubles carriage returns on Windows | S3 | silent | T9 |
| A-56 · A symlinked skill directory escapes the discovered-set defence | S4 | latent | T11 |
| A-78 · `create_project` commits the project row before its stage rows/dirs | S2 | silent | T16, T17 |
| A-79 · Slug collision → `run_id` clash surfaces as a 500 | S3 | loud | T18 |
| D-49 · `commit_skill_edit` commits the whole index, not the file it staged | S2 | silent | T10 |
| D-50 · `git_helper` subprocesses have no timeout | S3 | silent | T12 |
| D-51 · Web commits land on the checked-out branch under ambient identity | S4 | latent | T13 |
| F-21 · `test_save_kickoff_template_does_not_commit` pins a missing recovery path | S2 | silent | T14 |

T1 is fixture groundwork with no finding of its own; T15 is the shared surfacing task; T19 is the
P4 hand-off swap; **T20 carries no finding ID from this package's set** — it is this package's share
of the repo-wide `| safe` producer-side sanitization rule (D-47, owned by P3/P15), applied to the
one producer site that lives in a P5 file, `routes/inspector.py:45`.

---

## 3. Tasks

Every task is: **write the failing test → run it → read the failure and confirm it is the right
failure → implement → run → see green → commit.** Run commands are always from `pipeline-app/`:

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app"
python -m pytest tests/test_routes_skills.py -q
```

**Dependency on P0:** `tests/test_git_helper.py` shells out to real `git`. Once P0's conftest guard
exists, that module needs a module-level opt-in. Add it in T1 and never remove it:

```python
pytestmark = pytest.mark.allow_subprocess
```

**Dependency on P1:** `obs.log` / `obs.record_event` and the `events` table must exist before T15.
T1–T14 can be written against `obs.log` only (it never raises and needs no DB).

---

### T1 — Fixture groundwork: a real topology and a real, non-default-branch git repo

No behaviour change; this is the arrange half of T2–T14 and must land first or every later test
fails for the wrong reason.

- [ ] Replace the `client` fixture in `pipeline-app/tests/test_routes_skills.py:10-20`. The current
      one writes `stages: []`, so *no* skill maps to a stage and the styleboard defect is
      unreachable. Give it the four skills the later tests need, three of which are real stages:

```python
from pathlib import Path
import subprocess

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app

pytestmark = pytest.mark.allow_subprocess

PIPELINE_YAML = (
    "stages:\n"
    "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n"
    "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n"
    "    depends_on: [ideation]\n"
    "  - id: styleboard\n    skill: shorts-styleboard\n    dir_prefix: \"02b\"\n"
    "    depends_on: [scripting]\n"
)

SKILL_MD = "---\nname: {name}\ndescription: A real description.\n---\n\nBody.\n"


def _init_repo(root: Path) -> None:
    # `git init` lands on init.defaultBranch, which is `main` or `master` on
    # most machines -- both PROTECTED_BRANCHES (D-51). The editor's happy path
    # is a working branch, so the fixture models that; the protected-branch
    # refusal gets its own repo in test_git_helper.py.
    subprocess.run(["git", "init", "-b", "skill-edits"], cwd=root, check=True,
                   capture_output=True, encoding="utf-8", errors="replace")
    for key, value in (("user.email", "test@example.com"), ("user.name", "Test User")):
        subprocess.run(["git", "config", key, value], cwd=root, check=True,
                       capture_output=True, encoding="utf-8", errors="replace")
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=root, check=True,
                   capture_output=True, encoding="utf-8", errors="replace")


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(PIPELINE_YAML, encoding="utf-8")
    for name in ("shorts-ideation", "shorts-scripting", "shorts-styleboard",
                 "rgs-pairing-review"):
        skill_dir = tmp_path / ".claude" / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(SKILL_MD.format(name=name), encoding="utf-8")
    templates = tmp_path / "pipeline-app" / "stage_templates"
    templates.mkdir(parents=True)
    (templates / "ideation.md").write_text("/shorts-ideation\n", encoding="utf-8")
    (templates / "styleboard.md").write_text("/shorts-styleboard\n", encoding="utf-8")
    _init_repo(tmp_path)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app), tmp_path


def events(test_client, kind: str | None = None) -> list:
    """Rows P1's obs.record_event appended, newest last."""
    conn = test_client.app.state.conn
    rows = conn.execute("SELECT * FROM events ORDER BY id").fetchall()
    return [r for r in rows if kind is None or r["kind"] == kind]
```

- [ ] Apply the same `git init -b`/`--allow-empty` change to the `repo` fixture in
      `tests/test_git_helper.py:9-14`, and add `pytestmark = pytest.mark.allow_subprocess` there.
      The existing `git init` puts the repo on `main`/`master`, which T13 will start refusing.
- [ ] Run `python -m pytest tests/test_routes_skills.py tests/test_git_helper.py -q`. Expect
      **`test_save_kickoff_template_does_not_commit` and the two `..._unknown_skill_name` tests to
      still pass, and `test_stage_id_by_skill_maps_music_brief_but_not_the_specialist` to still
      pass** — nothing is fixed yet, this is only the arrange.
- [ ] Commit: `test: give the skill-editor fixture a real topology and a working-branch repo`

---

### T2 — A-48 fault: `shorts-styleboard`'s kickoff template is invisible

- [ ] Add to `tests/test_routes_skills.py`:

```python
def test_styleboard_kickoff_template_is_editable(client):
    """shorts-styleboard is a real stage in pipeline.yaml with a real template
    on disk. The hardcoded STAGE_ID_BY_SKILL omitted it, so its editor showed
    an empty box over a populated file (A-48)."""
    test_client, _ = client
    resp = test_client.get("/skills/shorts-styleboard")
    assert resp.status_code == 200
    assert "/shorts-styleboard" in resp.text
```

- [ ] Run it. Expect **fail**: the page renders an empty kickoff textarea because
      `STAGE_ID_BY_SKILL` has no `shorts-styleboard` key.
- [ ] Implement in `routes/skills.py` — delete the module-level dict entirely and derive:

```python
def _stage_id_by_skill(stage_defs) -> dict[str, str]:
    """Skill name -> stage id, derived from the loaded topology.

    Replaces a hand-maintained dict that had already drifted from
    pipeline.yaml (A-48). P4 owns the canonical version of this function --
    see the P4 contract in this package's plan; this private copy exists only
    so P5 is not blocked on P4, and T19 deletes it.
    """
    return {s.skill: s.id for s in stage_defs}
```

  and in `skill_detail`:

```python
    stage_id = _stage_id_by_skill(request.app.state.stage_defs).get(skill_name)
```

- [ ] Run. Green.
- [ ] Commit: `fix(skills): derive the skill->stage map from pipeline.yaml (A-48)`

---

### T3 — A-48 distinguishability: "no template applies" vs "template file is missing" vs "empty"

Three states currently collapse to the same empty textarea. Make them three.

- [ ] Add:

```python
def test_missing_template_file_is_distinguishable_from_no_template_at_all(client):
    """Three states rendered identically as "" before this fix:
      (a) skill has no stage    -> no kickoff form applies
      (b) skill has a stage but the template file is absent
      (c) the template file exists and is genuinely empty
    """
    test_client, tmp_path = client
    (tmp_path / "pipeline-app" / "stage_templates" / "styleboard.md").unlink()

    no_stage = test_client.get("/skills/rgs-pairing-review")
    missing_file = test_client.get("/skills/shorts-styleboard")
    present = test_client.get("/skills/shorts-ideation")

    ctx_a = no_stage.context
    ctx_b = missing_file.context
    ctx_c = present.context
    assert (ctx_a["stage_id"], ctx_a["kickoff_template_applies"]) == (None, False)
    assert (ctx_b["stage_id"], ctx_b["kickoff_template_applies"],
            ctx_b["kickoff_template_missing"]) == ("styleboard", True, True)
    assert (ctx_c["stage_id"], ctx_c["kickoff_template_applies"],
            ctx_c["kickoff_template_missing"]) == ("ideation", True, False)
    assert ctx_b["kickoff_template_content"] == ctx_c["kickoff_template_content"] == "" \
        or ctx_c["kickoff_template_content"] != ""
```

  (`TemplateResponse.context` is Starlette's rendering context; asserting on it keeps the test
  independent of P15's markup.)

- [ ] Run. Expect **fail** — `KeyError: 'kickoff_template_applies'`.
- [ ] Implement `skill_detail`:

```python
    stage_id = _stage_id_by_skill(request.app.state.stage_defs).get(skill_name)
    template_path = _template_path(repo_root, stage_id) if stage_id else None
    kickoff_template_missing = bool(stage_id) and not template_path.is_file()
    kickoff_template_content = (
        template_path.read_text(encoding="utf-8")
        if template_path is not None and template_path.is_file() else ""
    )
    if kickoff_template_missing:
        obs.log("skill_editor.template_file_missing", level="warning",
                skill=skill_name, stage_id=stage_id, path=str(template_path))
```

  with the context gaining `"stage_id": stage_id`, `"kickoff_template_applies": stage_id is not
  None`, `"kickoff_template_missing": kickoff_template_missing`, and the helper:

```python
def _template_path(repo_root: Path, stage_id: str) -> Path:
    # Convention frozen with P4 -- see the P4 contract. T19 replaces this with
    # pipeline_config.stage_template_path().
    return repo_root / "pipeline-app" / "stage_templates" / f"{stage_id}.md"
```

- [ ] Run. Green.
- [ ] Commit: `fix(skills): distinguish absent template file from no-template-applies (A-48)`

---

### T4 — A-49: an unknown `target` must be an error, not a 303

**The archetype test.** A save that wrote nothing must not look like a save.

- [ ] Add:

```python
def test_unknown_target_is_rejected_and_writes_nothing(client):
    test_client, tmp_path = client
    skill_md = tmp_path / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    before = skill_md.read_text(encoding="utf-8")

    resp = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "skill_md", "content": "edited"},   # renamed hidden input
        follow_redirects=False,
    )

    assert resp.status_code == 400
    assert "skill_md" in resp.text          # names the target it refused
    assert skill_md.read_text(encoding="utf-8") == before


def test_a_save_that_wrote_nothing_is_not_the_same_response_as_a_save_that_wrote(client):
    """Distinguishability: the 303 was indistinguishable between a real write
    and a no-op (A-49)."""
    test_client, _ = client
    wrote = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "SKILL.md", "content": SKILL_MD.format(name="shorts-ideation")},
        follow_redirects=False,
    )
    wrote_nothing = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "nonsense", "content": "x"},
        follow_redirects=False,
    )
    assert wrote.status_code == 303
    assert wrote_nothing.status_code != wrote.status_code
```

- [ ] Run. Expect **fail**: both return 303.
- [ ] Implement — restructure `save_skill` so the redirect is reachable only through a real write:

```python
VALID_TARGETS = ("SKILL.md", "kickoff_template")


def _resolve_write_path(request: Request, skill_name: str, target: str) -> Path:
    repo_root = request.app.state.repo_root
    if target == "SKILL.md":
        root = repo_root / ".claude" / "skills"
        path = root / skill_name / "SKILL.md"
    elif target == "kickoff_template":
        stage_id = _stage_id_by_skill(request.app.state.stage_defs).get(skill_name)
        if stage_id is None:
            raise HTTPException(
                status_code=400,
                detail=(f"Skill {skill_name!r} is not bound to a pipeline stage, so it has "
                        f"no kickoff template to save."),
            )
        root = repo_root / "pipeline-app" / "stage_templates"
        path = _template_path(repo_root, stage_id)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unrecognized save target {target!r}; expected one of {VALID_TARGETS}.",
        )
    if not path.resolve().is_relative_to(root.resolve()):
        raise HTTPException(status_code=400, detail="Refusing to write outside the skill tree.")
    return path
```

  and `save_skill` calls it, writes, then returns the 303. There is no code path left that returns
  303 without a preceding `write_text`.

- [ ] Run. Green.
- [ ] Commit: `fix(skills): reject an unrecognized save target instead of 303-ing (A-49)`

---

### T5 — A-50: never write `stage_templates/None.md`

- [ ] Add:

```python
def test_kickoff_save_for_a_stageless_skill_is_rejected_and_creates_no_None_md(client):
    test_client, tmp_path = client
    templates = tmp_path / "pipeline-app" / "stage_templates"

    resp = test_client.post(
        "/skills/rgs-pairing-review/save",
        data={"target": "kickoff_template", "content": "junk"},
        follow_redirects=False,
    )

    assert resp.status_code == 400
    assert "rgs-pairing-review" in resp.text
    assert not (templates / "None.md").exists()
    assert sorted(p.name for p in templates.iterdir()) == ["ideation.md", "styleboard.md"]


def test_stageless_kickoff_rejection_differs_from_a_real_kickoff_save(client):
    test_client, _ = client
    real = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "kickoff_template", "content": "/shorts-ideation v2\n"},
        follow_redirects=False,
    )
    stageless = test_client.post(
        "/skills/rgs-pairing-review/save",
        data={"target": "kickoff_template", "content": "/shorts-ideation v2\n"},
        follow_redirects=False,
    )
    assert (real.status_code, stageless.status_code) == (303, 400)
```

- [ ] Run. Expect **fail**: `stage_templates/None.md` exists and both return 303.
- [ ] Implement: already covered by the `stage_id is None` branch added in T4 — this task's job is
      to prove it and to delete the old `elif` body from `save_skill`. If T4's implementation is in
      place the test goes green with no further code; if it does not, the `f"{stage_id}.md"`
      interpolation is still live somewhere — find and remove it.
- [ ] Run. Green.
- [ ] Commit: `fix(skills): refuse a kickoff save for a skill with no stage (A-50)`

---

### T6 — A-51 fault: a blank body must never overwrite a file

- [ ] Add:

```python
@pytest.mark.parametrize("blank", ["", "   ", "\n\n", "\r\n\t "])
def test_blank_content_never_truncates_a_file(client, blank):
    test_client, tmp_path = client
    skill_md = tmp_path / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    before = skill_md.read_text(encoding="utf-8")

    resp = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "SKILL.md", "content": blank},
        follow_redirects=False,
    )

    assert resp.status_code == 400
    assert skill_md.read_text(encoding="utf-8") == before
    assert skill_md.stat().st_size > 0
```

- [ ] Run. Expect **fail**: 303, and the file is now zero bytes.
- [ ] Implement in `save_skill`, **before** any write:

```python
def _validate_content(target: str, content: str) -> str | None:
    """Return an operator-facing rejection reason, or None if the body is
    safe to write. A blank textarea used to write a zero-byte file and 303 as
    a success, destroying the skill (A-51)."""
    if not content.strip():
        return "Refusing to write an empty file — the editor body was blank."
    ...
```

  and:

```python
    problem = _validate_content(target, content)
    if problem is not None:
        raise HTTPException(status_code=400, detail=problem)
```

- [ ] Run. Green.
- [ ] Commit: `fix(skills): reject a blank editor body instead of truncating (A-51)`

---

### T7 — A-51 fault: a `SKILL.md` save must still be a loadable skill

- [ ] Add:

```python
@pytest.mark.parametrize("body, reason", [
    ("just prose, no frontmatter\n", "frontmatter"),
    ("---\nname: x\n", "not closed"),
    ("---\nname: x\n---\n\nbody\n", "description"),
    ("---\ndescription: y\n---\n\nbody\n", "name"),
    ("---\nname: [oops\n---\n\nbody\n", "valid YAML"),
])
def test_skill_md_save_requires_loadable_frontmatter(client, body, reason):
    test_client, tmp_path = client
    skill_md = tmp_path / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    before = skill_md.read_text(encoding="utf-8")

    resp = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "SKILL.md", "content": body},
        follow_redirects=False,
    )

    assert resp.status_code == 400
    assert reason in resp.text
    assert skill_md.read_text(encoding="utf-8") == before


def test_a_kickoff_template_is_not_held_to_the_frontmatter_rule(client):
    """Distinguishability: the SKILL.md rule must not leak onto templates,
    which are plain slash-command text."""
    test_client, tmp_path = client
    resp = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "kickoff_template", "content": "/shorts-ideation go\n"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert (tmp_path / "pipeline-app" / "stage_templates" / "ideation.md").read_text(
        encoding="utf-8") == "/shorts-ideation go\n"
```

- [ ] Run. Expect **fail**: every malformed body is written and 303s.
- [ ] Implement — extend `_validate_content` (import `yaml`, already a dependency via
      `pipeline_config`; do **not** import `artifacts.parse_frontmatter`, that file is P2's):

```python
    if target != "SKILL.md":
        return None
    if not content.lstrip().startswith("---"):
        return "A SKILL.md must begin with a YAML frontmatter block (`---`)."
    parts = content.lstrip().split("---", 2)
    if len(parts) < 3:
        return "The SKILL.md frontmatter block is not closed with a second `---`."
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        return f"The SKILL.md frontmatter is not valid YAML: {exc}"
    if not isinstance(meta, dict):
        return "The SKILL.md frontmatter must be a YAML mapping."
    missing = [k for k in ("name", "description") if not str(meta.get(k) or "").strip()]
    if missing:
        return (f"The SKILL.md frontmatter is missing required key(s): "
                f"{', '.join(missing)} — the skill loader would reject this file.")
    return None
```

- [ ] Run. Green.
- [ ] Commit: `fix(skills): require loadable frontmatter on a SKILL.md save (A-51)`

---

### T8 — A-51 surfacing: an editor opened on a missing `SKILL.md` says so

`skill_detail:56` renders `""` for a missing file, presenting an empty box that will write a file
from nothing.

- [ ] Add:

```python
def test_detail_flags_a_missing_skill_md_instead_of_rendering_empty(client):
    test_client, tmp_path = client
    (tmp_path / ".claude" / "skills" / "shorts-scripting" / "SKILL.md").unlink()

    present = test_client.get("/skills/shorts-ideation")
    absent = test_client.get("/skills/shorts-scripting")

    assert present.context["skill_md_missing"] is False
    assert absent.context["skill_md_missing"] is True
    assert absent.context["skill_md_content"] == ""
```

- [ ] Run. Expect **fail** — `KeyError: 'skill_md_missing'`.
- [ ] Implement:

```python
    skill_md_exists = skill_md_path.is_file()
    skill_md_content = skill_md_path.read_text(encoding="utf-8") if skill_md_exists else ""
    if not skill_md_exists:
        obs.log("skill_editor.skill_md_missing", level="warning",
                skill=skill_name, path=str(skill_md_path))
```

  and pass `"skill_md_missing": not skill_md_exists` in the context. Rendering the banner is P15's
  (§7).

- [ ] Run. Green.
- [ ] Commit: `fix(skills): flag a missing SKILL.md instead of rendering an empty editor (A-51)`

---

### T9 — A-55: stop doubling carriage returns

- [ ] Add:

```python
@pytest.mark.parametrize("target, rel", [
    ("SKILL.md", (".claude", "skills", "shorts-ideation", "SKILL.md")),
    ("kickoff_template", ("pipeline-app", "stage_templates", "ideation.md")),
])
def test_browser_crlf_is_written_as_lf_not_doubled(client, target, rel):
    """A <textarea> submits CRLF; write_text(newline=None) then translated
    every \\n to os.linesep, producing \\r\\r\\n on Windows (A-55)."""
    test_client, tmp_path = client
    body = ("---\r\nname: shorts-ideation\r\ndescription: d\r\n---\r\n\r\nline one\r\nline two\r\n"
            if target == "SKILL.md" else "/shorts-ideation\r\nline two\r\n")

    resp = test_client.post(f"/skills/shorts-ideation/save",
                            data={"target": target, "content": body}, follow_redirects=False)

    assert resp.status_code == 303
    raw = tmp_path.joinpath(*rel).read_bytes()
    assert b"\r\r\n" not in raw
    assert b"\r" not in raw
    assert raw.decode("utf-8").endswith("line two\n")
```

- [ ] Run. Expect **fail** on Windows: `b"\r\r\n" in raw`.
- [ ] Implement:

```python
def _normalized(content: str) -> str:
    """HTML form submission normalizes a <textarea> to CRLF; combined with
    write_text's newline=None translation that becomes \\r\\r\\n on Windows and
    every save is a whole-file diff (A-55)."""
    return content.replace("\r\n", "\n").replace("\r", "\n")
```

  and both writes become `path.write_text(_normalized(content), encoding="utf-8", newline="")`.
  Validate `_normalized(content)`, not the raw body, so the frontmatter check sees the same bytes
  that reach disk.

- [ ] Run. Green.
- [ ] Commit: `fix(skills): normalize submitted line endings before writing (A-55)`

---

### T10 — A-53 + D-49: scope the commit to the file it staged

- [ ] Add to `tests/test_git_helper.py`:

```python
def test_commit_is_scoped_to_the_file_and_leaves_unrelated_staged_work_alone(repo: Path):
    """A-53/D-49: `git commit -m msg` carried no pathspec, so an operator's
    unrelated staged work was swept into a "skill edit" commit."""
    unrelated = repo / "unrelated.txt"
    unrelated.write_text("operator work in progress\n", encoding="utf-8")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=repo, check=True, capture_output=True)

    skill_file = repo / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("edited content\n", encoding="utf-8")

    result = commit_skill_edit(repo, skill_file, "shorts-ideation", now="2026-07-25")

    assert result.status == "committed"
    files = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:", "HEAD"], cwd=repo,
        check=True, capture_output=True, encoding="utf-8", errors="replace",
    ).stdout.split()
    assert files == [".claude/skills/shorts-ideation/SKILL.md"]
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=repo,
        check=True, capture_output=True, encoding="utf-8", errors="replace",
    ).stdout.split()
    assert staged == ["unrelated.txt"]      # still the operator's, uncommitted


def test_unchanged_content_is_a_no_op_even_with_unrelated_staged_work(repo: Path):
    """The index-wide `git diff --cached --quiet` reported work to commit
    because of the operator's staging, producing a "skill edit" commit
    containing no skill edit (A-53)."""
    skill_file = repo / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("same content\n", encoding="utf-8")
    assert commit_skill_edit(repo, skill_file, "shorts-ideation").status == "committed"

    (repo / "unrelated.txt").write_text("wip\n", encoding="utf-8")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=repo, check=True, capture_output=True)

    second = commit_skill_edit(repo, skill_file, "shorts-ideation")

    assert second.status == "no_change"          # distinguishable from "committed"
    log = subprocess.run(["git", "log", "--oneline"], cwd=repo, check=True,
                         capture_output=True, encoding="utf-8", errors="replace").stdout
    assert log.count("skill edit") == 1
```

- [ ] Run. Expect **fail** on both: the first commit contains `unrelated.txt`; the second creates a
      second "skill edit" commit.
- [ ] Implement — rewrite `git_helper.py` around a result type (this is the shape T11–T14 build on):

```python
import datetime
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pipeline_app import obs

GIT_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class CommitResult:
    """Why the route needs this: the save already wrote the file by the time
    git runs, so "did the commit happen" is a separate outcome from "did the
    save happen" and must be reported separately (A-54)."""
    status: str          # committed | no_change | refused_protected_branch | failed
    branch: str | None = None
    commit_sha: str | None = None
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in ("committed", "no_change")


def _git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True,
        encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT_SECONDS,
    )


def commit_skill_edit(repo_root: Path, file_path: Path, skill_name: str,
                      now: str | None = None) -> CommitResult:
    now = now or datetime.date.today().isoformat()
    rel_path = file_path.relative_to(repo_root).as_posix()
    message = f"skill edit: {skill_name} via pipeline-app, {now}"

    add = _git(repo_root, ["add", "--", rel_path])
    if add.returncode != 0:
        return CommitResult(status="failed", detail=(add.stderr or add.stdout).strip())
    # `-- rel_path` on BOTH commands, so the emptiness check and the commit
    # describe the same single file (A-53/D-49).
    diff = _git(repo_root, ["diff", "--cached", "--quiet", "--", rel_path])
    if diff.returncode == 0:
        return CommitResult(status="no_change")
    commit = _git(repo_root, ["commit", "-m", message, "--", rel_path])
    if commit.returncode != 0:
        detail = (commit.stderr or commit.stdout).strip()
        obs.log("git.commit_failed", level="error", path=rel_path, detail=detail)
        return CommitResult(status="failed", detail=detail)
    sha = _git(repo_root, ["rev-parse", "HEAD"]).stdout.strip() or None
    return CommitResult(status="committed", commit_sha=sha)
```

- [ ] Run `python -m pytest tests/test_git_helper.py -q`. Green. The pre-existing
      `test_commit_skill_edit_is_a_no_op_when_content_is_unchanged` still passes (its
      `commit_skill_edit(...)` return value was unused).
- [ ] Commit: `fix(git): scope the staged-change check and the commit to one path (A-53, D-49)`

---

### T11 — A-56: a symlinked skill directory is not a skill

- [ ] Add to `tests/test_routes_skills.py`:

```python
@pytest.fixture
def symlink_or_skip(tmp_path):
    def make(link: Path, target: Path):
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"symlinks not permitted on this host: {exc}")
    return make


def test_a_symlinked_skill_directory_is_not_discovered(client, symlink_or_skip, tmp_path):
    """is_dir() follows symlinks, so a link in .claude/skills/ joined the
    discovered set and the save route wrote THROUGH it (A-56)."""
    outside = tmp_path.parent / "outside-the-repo"
    outside.mkdir(exist_ok=True)
    (outside / "SKILL.md").write_text("victim\n", encoding="utf-8")
    test_client, root = client
    symlink_or_skip(root / ".claude" / "skills" / "escape", outside)

    listing = test_client.get("/skills")
    detail = test_client.get("/skills/escape")
    save = test_client.post("/skills/escape/save",
                            data={"target": "SKILL.md", "content": "pwned\n"},
                            follow_redirects=False)

    assert "escape" not in listing.text
    assert detail.status_code == 404
    assert save.status_code == 404
    assert (outside / "SKILL.md").read_text(encoding="utf-8") == "victim\n"
```

- [ ] Run. Expect **fail**: `escape` is listed, the detail page renders, and `outside/SKILL.md` now
      reads `pwned`.
- [ ] Implement in `_discovered_skill_names`:

```python
    return {
        p.name for p in skills_dir.iterdir()
        # is_dir() follows symlinks, so without the is_symlink() exclusion a
        # link placed in .claude/skills/ becomes a legitimate member of the
        # discovered set and the save route writes through it to wherever it
        # points, outside the repo included (A-56). The set-membership check
        # is otherwise the right defence and stays exactly as it is.
        if p.is_dir() and not p.is_symlink()
    }
```

  The `is_relative_to` containment assert added in T4 is the second layer — it also catches a
  symlinked `SKILL.md` *file* inside an otherwise-real skill directory, which discovery cannot see.

- [ ] Run. Green.
- [ ] Commit: `fix(skills): exclude symlinked entries from skill discovery (A-56)`

---

### T12 — D-50: git subprocesses get a timeout, and a timeout is a reported failure

- [ ] Add to `tests/test_git_helper.py`:

```python
def test_every_git_call_carries_a_timeout(repo: Path, monkeypatch):
    """All three subprocess.run calls used capture_output with no timeout, so
    a git that prompts (GPG passphrase, an interactive hook) blocked forever
    with its prompt swallowed and wedged the request thread (D-50)."""
    seen = []
    real = subprocess.run

    def spy(args, **kwargs):
        if args and args[0] == "git":
            seen.append(kwargs.get("timeout"))
        return real(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    skill_file = repo / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("edited\n", encoding="utf-8")

    commit_skill_edit(repo, skill_file, "shorts-ideation")

    assert seen and all(t is not None and t > 0 for t in seen)


def test_a_hanging_git_reports_failure_rather_than_hanging(repo: Path, monkeypatch):
    def boom(args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args, timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(subprocess, "run", boom)
    skill_file = repo / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("edited\n", encoding="utf-8")

    result = commit_skill_edit(repo, skill_file, "shorts-ideation")

    assert result.status == "failed"
    assert "timed out" in result.detail
    assert result.ok is False              # distinguishable from no_change, which is also
                                           # "no commit was made" but is NOT a failure


def test_git_missing_from_path_reports_failure_rather_than_raising(repo: Path, monkeypatch):
    def boom(args, **kwargs):
        raise FileNotFoundError(2, "The system cannot find the file specified", "git")

    monkeypatch.setattr(subprocess, "run", boom)
    skill_file = repo / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("edited\n", encoding="utf-8")

    assert commit_skill_edit(repo, skill_file, "shorts-ideation").status == "failed"
```

- [ ] Run. The first fails only if T10's `timeout=` was omitted; the second and third fail with the
      raised exception escaping. Confirm each failure reason before implementing.
- [ ] Implement — wrap the body of `commit_skill_edit` (everything after `message = ...`) in:

```python
    try:
        ...
    except subprocess.TimeoutExpired:
        detail = f"git timed out after {GIT_TIMEOUT_SECONDS}s"
        obs.log("git.timeout", level="error", path=rel_path, detail=detail)
        return CommitResult(status="failed", detail=detail)
    except OSError as exc:                  # git absent from PATH, or unreadable cwd
        obs.log("git.unavailable", level="error", path=rel_path, detail=str(exc))
        return CommitResult(status="failed", detail=str(exc))
```

- [ ] Run. Green.
- [ ] Commit: `fix(git): bound every git call and report a hang as a failure (D-50)`

---

### T13 — A-54 + D-51: a git failure warns, it does not 500; app commits are attributable

- [ ] Add to `tests/test_git_helper.py`:

```python
def test_refuses_to_commit_on_a_protected_branch(tmp_path: Path):
    """No branch guard meant a web save committed straight to main (D-51)."""
    root = tmp_path / "onmain"
    root.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    for k, v in (("user.email", "t@e.com"), ("user.name", "T")):
        subprocess.run(["git", "config", k, v], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=root, check=True,
                   capture_output=True)
    skill_file = root / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("edited\n", encoding="utf-8")

    result = commit_skill_edit(root, skill_file, "shorts-ideation")

    assert result.status == "refused_protected_branch"
    assert result.branch == "main"
    assert "main" in result.detail
    log = subprocess.run(["git", "log", "--oneline"], cwd=root, check=True,
                         capture_output=True, encoding="utf-8", errors="replace").stdout
    assert "skill edit" not in log


def test_app_commits_carry_the_pipeline_app_identity(repo: Path):
    """Nothing distinguished app-authored history from hand-authored history
    beyond a message suffix (D-51)."""
    skill_file = repo / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("edited\n", encoding="utf-8")

    commit_skill_edit(repo, skill_file, "shorts-ideation")

    author = subprocess.run(["git", "log", "-1", "--format=%an <%ae>"], cwd=repo, check=True,
                            capture_output=True, encoding="utf-8", errors="replace").stdout.strip()
    assert author == "pipeline-app <noreply@localhost>"
```

- [ ] Add to `tests/test_routes_skills.py`:

```python
def test_a_failed_commit_still_saves_the_file_and_warns_rather_than_500ing(client, monkeypatch):
    """The write happened first, then two check=True subprocesses; a failing
    hook 500'd a save that had in fact succeeded (A-54)."""
    from pipeline_app import git_helper
    test_client, tmp_path = client
    monkeypatch.setattr(
        git_helper, "commit_skill_edit",
        lambda *a, **k: git_helper.CommitResult(status="failed", detail="pre-commit hook failed"),
    )
    body = SKILL_MD.format(name="shorts-ideation")

    resp = test_client.post("/skills/shorts-ideation/save",
                            data={"target": "SKILL.md", "content": body},
                            follow_redirects=False)

    assert resp.status_code == 303
    assert "warning=" in resp.headers["location"]
    assert (tmp_path / ".claude" / "skills" / "shorts-ideation" / "SKILL.md").read_text(
        encoding="utf-8") == body


def test_the_three_save_outcomes_are_three_different_responses(client, monkeypatch):
    """Distinguishability, the whole point of this package: saved+committed,
    saved-but-not-committed, and wrote-nothing were ONE 303."""
    from pipeline_app import git_helper
    test_client, _ = client
    body = SKILL_MD.format(name="shorts-ideation")

    committed = test_client.post("/skills/shorts-ideation/save",
                                 data={"target": "SKILL.md", "content": body},
                                 follow_redirects=False)
    monkeypatch.setattr(git_helper, "commit_skill_edit",
                        lambda *a, **k: git_helper.CommitResult(status="failed", detail="nope"))
    uncommitted = test_client.post("/skills/shorts-ideation/save",
                                   data={"target": "SKILL.md", "content": body + "# more\n"},
                                   follow_redirects=False)
    nothing = test_client.post("/skills/shorts-ideation/save",
                               data={"target": "bogus", "content": body},
                               follow_redirects=False)

    outcomes = {
        (committed.status_code, "warning=" in committed.headers.get("location", "")),
        (uncommitted.status_code, "warning=" in uncommitted.headers.get("location", "")),
        (nothing.status_code, False),
    }
    assert len(outcomes) == 3
```

- [ ] Run. Expect **fail**: the protected-branch and identity tests fail outright; the route tests
      fail because `commit_skill_edit` returns `None` and the route ignores it.
- [ ] Implement in `git_helper.py`:

```python
PROTECTED_BRANCHES = frozenset({"main", "master"})
APP_COMMITTER_NAME = "pipeline-app"
APP_COMMITTER_EMAIL = "noreply@localhost"


def current_branch(repo_root: Path) -> str | None:
    # symbolic-ref, not rev-parse --abbrev-ref: it also answers correctly on
    # an unborn branch (a freshly-init'd repo), where rev-parse errors.
    proc = _git(repo_root, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    return proc.stdout.strip() or None if proc.returncode == 0 else None
```

  inside the `try`, before `git add`:

```python
        branch = current_branch(repo_root)
        if branch in PROTECTED_BRANCHES:
            detail = (f"refusing to commit to protected branch {branch!r}; the file was saved "
                      f"but is uncommitted")
            obs.log("git.commit_refused_protected_branch", level="warning",
                    branch=branch, path=rel_path)
            return CommitResult(status="refused_protected_branch", branch=branch, detail=detail)
```

  and pin the identity on the commit call:

```python
        commit = _git(repo_root, [
            "-c", f"user.name={APP_COMMITTER_NAME}",
            "-c", f"user.email={APP_COMMITTER_EMAIL}",
            "commit", "-m", message, "--", rel_path,
        ])
```

  Thread `branch=branch` through every `CommitResult` returned after that point.

- [ ] Implement in `routes/skills.py` — `save_skill` ends with:

```python
    result = git_helper.commit_skill_edit(repo_root, path, skill_name)
    if result.ok:
        return RedirectResponse(url=f"/skills/{skill_name}", status_code=303)
    warning = f"Saved, but not committed: {result.detail}"
    return RedirectResponse(
        url=f"/skills/{skill_name}?warning={quote(warning)}", status_code=303,
    )
```

  (`from urllib.parse import quote`), and `skill_detail` gains `warning: str | None = None` as a
  query parameter, passed straight into the template context. Rendering it is P15's (§7).

- [ ] Run. Green.
- [ ] Commit: `fix(git): guard the protected branch, pin the app identity, warn on commit failure (A-54, D-51)`

---

### T14 — A-52 + F-21: kickoff templates are committed too, and the test that pinned the gap is inverted

- [ ] **Delete** `pipeline-app/tests/test_routes_skills.py:54-68`
      (`test_save_kickoff_template_does_not_commit`) and replace it with its inverse:

```python
def test_kickoff_template_save_is_committed_like_skill_md(client):
    """Inverted from test_save_kickoff_template_does_not_commit (F-21), which
    asserted `calls == []` with no rationale and thereby pinned A-52: a bad
    kickoff-template save had no recovery path, while SKILL.md did."""
    test_client, tmp_path = client

    resp = test_client.post("/skills/shorts-ideation/save",
                            data={"target": "kickoff_template",
                                  "content": "/shorts-ideation new kickoff\n"},
                            follow_redirects=False)

    assert resp.status_code == 303
    assert (tmp_path / "pipeline-app" / "stage_templates" / "ideation.md").read_text(
        encoding="utf-8") == "/shorts-ideation new kickoff\n"
    show = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:%s", "HEAD"], cwd=tmp_path,
        check=True, capture_output=True, encoding="utf-8", errors="replace").stdout
    assert "ideation" in show.splitlines()[0]        # the message names the stage
    assert show.split()[-1] == "pipeline-app/stage_templates/ideation.md"


def test_both_editable_surfaces_have_the_same_durability(client):
    """Distinguishability: before the fix, SKILL.md produced a commit and a
    kickoff template produced none — the same UI, two different guarantees."""
    test_client, tmp_path = client
    test_client.post("/skills/shorts-ideation/save",
                     data={"target": "SKILL.md",
                           "content": SKILL_MD.format(name="shorts-ideation") + "edit\n"})
    test_client.post("/skills/shorts-ideation/save",
                     data={"target": "kickoff_template", "content": "/shorts-ideation v2\n"})

    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path, check=True,
                         capture_output=True, encoding="utf-8", errors="replace").stdout
    assert log.count("skill edit") == 2
```

- [ ] Also **replace** `test_save_skill_md_writes_file_and_commits`
      (`tests/test_routes_skills.py:37-51`), which asserts `len(calls) == 1` — asserting a mock was
      called where the real effect is observable (anti-tautology rule 2):

```python
def test_skill_md_save_produces_a_real_scoped_commit(client):
    test_client, tmp_path = client
    body = SKILL_MD.format(name="shorts-ideation") + "edited content\n"

    resp = test_client.post("/skills/shorts-ideation/save",
                            data={"target": "SKILL.md", "content": body},
                            follow_redirects=False)

    assert resp.status_code == 303
    assert (tmp_path / ".claude" / "skills" / "shorts-ideation" / "SKILL.md").read_text(
        encoding="utf-8") == body
    files = subprocess.run(["git", "show", "--name-only", "--pretty=format:", "HEAD"],
                           cwd=tmp_path, check=True, capture_output=True,
                           encoding="utf-8", errors="replace").stdout.split()
    assert files == [".claude/skills/shorts-ideation/SKILL.md"]
```

- [ ] Run. Expect **fail**: the kickoff branch makes no commit, so `git show HEAD` is the fixture's
      empty init commit.
- [ ] Implement — the kickoff branch calls the same helper as `SKILL.md`. After T4's refactor there
      is a single write site, so this is one line: the `commit_skill_edit(repo_root, path,
      skill_name)` call moves out of the `SKILL.md` branch and runs for every successful write.
      Pass a label so the message names the stage:

```python
    label = skill_name if target == "SKILL.md" else f"{skill_name} kickoff ({stage_id})"
    result = git_helper.commit_skill_edit(repo_root, path, label)
```

- [ ] Run. Green.
- [ ] Commit: `fix(skills): commit kickoff-template saves on the same terms as SKILL.md (A-52, F-21)`

---

### T15 — Surfacing: every rejection and every warning leaves an `events` row

**Requires P1.** One parametrized test carries the surfacing role for A-48, A-49, A-50, A-51 and
A-52; each parameter is a distinct test id naming its finding.

- [ ] Add to `tests/test_routes_skills.py`:

```python
@pytest.mark.parametrize("finding, skill, data, kind", [
    ("A-49", "shorts-ideation",
     {"target": "typo", "content": "x"}, "skill_editor.save_rejected"),
    ("A-50", "rgs-pairing-review",
     {"target": "kickoff_template", "content": "x"}, "skill_editor.save_rejected"),
    ("A-51-blank", "shorts-ideation",
     {"target": "SKILL.md", "content": "   "}, "skill_editor.save_rejected"),
    ("A-51-frontmatter", "shorts-ideation",
     {"target": "SKILL.md", "content": "no frontmatter\n"}, "skill_editor.save_rejected"),
])
def test_a_rejected_save_is_findable_afterwards(client, finding, skill, data, kind):
    """Not a print(): a human-reachable row. Asserting a print happened is
    exactly the 35-site defect D-02."""
    test_client, _ = client
    assert events(test_client, kind) == []

    test_client.post(f"/skills/{skill}/save", data=data, follow_redirects=False)

    rows = events(test_client, kind)
    assert len(rows) == 1
    assert rows[0]["severity"] == "warning"
    assert rows[0]["source"] == "routes.skills"
    assert skill in rows[0]["message"] or skill in (rows[0]["detail"] or "")


def test_a_successful_save_is_findable_and_is_a_different_row(client):
    test_client, _ = client
    test_client.post("/skills/shorts-ideation/save",
                     data={"target": "SKILL.md",
                           "content": SKILL_MD.format(name="shorts-ideation") + "x\n"})
    saved = events(test_client, "skill_editor.saved")
    assert len(saved) == 1
    assert saved[0]["severity"] == "info"
    assert events(test_client, "skill_editor.save_rejected") == []


def test_a_failed_commit_is_findable_at_error_severity(client, monkeypatch):
    from pipeline_app import git_helper
    test_client, _ = client
    monkeypatch.setattr(git_helper, "commit_skill_edit",
                        lambda *a, **k: git_helper.CommitResult(status="failed", detail="hook"))
    test_client.post("/skills/shorts-ideation/save",
                     data={"target": "SKILL.md",
                           "content": SKILL_MD.format(name="shorts-ideation") + "x\n"})
    rows = events(test_client, "skill_editor.commit_failed")
    assert len(rows) == 1 and rows[0]["severity"] == "error"


def test_a_stage_with_no_editor_binding_is_findable(client, tmp_path):
    """A-48 surfacing: a stage in pipeline.yaml whose template file is absent
    used to render as a blank box and nothing else."""
    test_client, root = client
    (root / "pipeline-app" / "stage_templates" / "styleboard.md").unlink()
    test_client.get("/skills/shorts-styleboard")
    # obs.log writes to logs/app-YYYY-MM-DD.log; assert the file, not a print.
    logs = sorted((root / "pipeline-app" / "logs").glob("app-*.log"))
    assert logs and "skill_editor.template_file_missing" in logs[-1].read_text(encoding="utf-8")
```

- [ ] Run. Expect **fail**: no `events` rows at all.
- [ ] Implement — centralize rejection in `save_skill` so every 400 records once:

```python
def _reject(request: Request, skill_name: str, reason: str, **detail) -> HTTPException:
    obs.record_event(
        request.app.state.conn, kind="skill_editor.save_rejected", severity="warning",
        source="routes.skills", message=f"{skill_name}: {reason}",
        detail={"skill": skill_name, **detail},
    )
    return HTTPException(status_code=400, detail=reason)
```

  Every `raise HTTPException(400, ...)` added in T4–T7 becomes `raise _reject(request, skill_name,
  ...)`. On success, record `skill_editor.saved` (severity `info`, detail carrying `target`, the
  repo-relative path, `result.status`, `result.branch` and `result.commit_sha`); when
  `not result.ok`, additionally record `skill_editor.commit_failed` at severity `error`.

- [ ] Run. Green.
- [ ] Commit: `feat(skills): record every save outcome as an events row (A-48..A-52)`

---

### T16 — A-78 fault: bound the slug so the deepest run path fits

- [ ] Add to `tests/test_project_service.py`:

```python
def test_an_overlong_slug_is_rejected_before_anything_is_created(conn, tmp_path: Path):
    """Nothing bounded the slug, and the deepest run path is
    runs/<slug>-<ts>/02b-styleboard/events/<ms>.jsonl — an OSError partway
    through left a committed project with a partial set of stage rows (A-78)."""
    from pipeline_app.project_service import MAX_SLUG_LENGTH

    with pytest.raises(ValueError) as exc:
        create_project(conn, tmp_path, "a" * (MAX_SLUG_LENGTH + 1), "generic", STAGES)

    assert str(MAX_SLUG_LENGTH) in str(exc.value)
    assert db.list_projects(conn) == []
    assert not (tmp_path / "runs").exists()


def test_a_slug_at_the_limit_is_still_accepted(conn, tmp_path: Path):
    """Distinguishability: the bound must reject the overlong case only, not
    quietly narrow what a legitimate project may be called."""
    from pipeline_app.project_service import MAX_SLUG_LENGTH

    result = create_project(conn, tmp_path, "a" * MAX_SLUG_LENGTH, "generic", STAGES)
    assert result["run_dir"].is_dir()
    assert len(db.list_projects(conn)) == 1
```

- [ ] Add to `tests/test_routes_projects.py`:

```python
def test_overlong_slug_returns_400_not_500(client: TestClient):
    resp = client.post("/projects", data={"slug": "x" * 200, "brand": "generic"},
                       follow_redirects=False)
    assert resp.status_code == 400
    assert "60" in resp.text
```

- [ ] Run. Expect **fail**: the overlong slug is accepted.
- [ ] Implement in `project_service.py`:

```python
# The deepest path a run directory carries is
#   <repo_root>/runs/<slug>-YYYYmmdd-HHMMSS/02b-styleboard/events/<ms>.jsonl
# ~47 characters below the run directory. Windows' default MAX_PATH is 260,
# so an unbounded slug fails halfway through creation with an OSError and
# leaves a committed project with a partial set of stage rows (A-78).
MAX_SLUG_LENGTH = 60
```

  and in `sanitize_slug`, after the empty check:

```python
    if len(cleaned) > MAX_SLUG_LENGTH:
        raise ValueError(
            f"slug is {len(cleaned)} characters after cleaning; the limit is "
            f"{MAX_SLUG_LENGTH} so the deepest run path stays within the platform limit"
        )
```

- [ ] Run. Green.
- [ ] Commit: `fix(projects): bound the slug length so a run path cannot overflow (A-78)`

---

> **Amendment (P5 kickoff session, verified live against the P5 worktree at origin/main
> `ed93875`):** this task's shown implementation is stale. It assumes `db.py`'s
> `create_project`/`create_stage_row` commit per row with no way to batch them, and has
> `_create_once` bypass `db_mod` entirely with hand-rolled `conn.execute` + `conn.commit()`/
> `conn.rollback()`. That is no longer true. Live `db.py` now ships `db.transaction(conn)` (a
> reentrant context manager, `db.py:70-`) and `commit_unless_in_transaction` (`db.py:42-67`),
> which `create_project`/`create_stage_row` already call instead of a raw `conn.commit()`
> (`db.py:1511-1533`, confirmed). Wrapping the whole per-row sequence in `with
> db_mod.transaction(conn):` already makes the DB half of A-78 atomic — on any exception inside
> the block, `transaction()` itself rolls back and emits its own `db.transaction_rolled_back`
> event, which is strictly better observability than anything this task would add by hand. This
> infrastructure did not exist when this task's code was drafted; it must not be bypassed or
> reimplemented — routes/projects.py and routes/stages.py already rely on the same mechanism for
> other invariants (see `db.py`'s `transaction()` docstring), and hand-rolling a parallel
> commit/rollback path here would fight it, not fix it. **Corrected implementation:** keep calling
> `db_mod.create_project` / `db_mod.create_stage_row` exactly as `project_service.py` already
> does today; do not import `sqlite3` for INSERTs and do not add `conn.commit()`/`conn.rollback()`
> calls. `_create_once`'s only real job is the filesystem half, which `transaction()` cannot see:
>
> ```python
> import shutil
>
> def _create_once(conn, repo_root, cleaned_slug, brand, applicable, now) -> dict:
>     run_id = f"{cleaned_slug}-{now.strftime('%Y%m%d-%H%M%S')}"
>     run_dir = repo_root / "runs" / run_id
>     if run_dir.resolve().parent != (repo_root / "runs").resolve():
>         raise ValueError(f"slug resolves outside the runs directory: {cleaned_slug!r}")
>
>     created_dir = False
>     try:
>         with db_mod.transaction(conn):
>             project_id = db_mod.create_project(conn, run_id, cleaned_slug, brand, now.isoformat())
>             for stage in applicable:
>                 status = compute_initial_status(stage.depends_on)
>                 db_mod.create_stage_row(conn, project_id, stage.id, status.value)
>             run_dir.mkdir(parents=True, exist_ok=False)
>             created_dir = True
>             for stage in applicable:
>                 (run_dir / stage_dir_name(stage)).mkdir(parents=True, exist_ok=True)
>     except BaseException:
>         if created_dir:
>             shutil.rmtree(run_dir, ignore_errors=True)
>         raise
>     return {"project_id": project_id, "run_id": run_id, "run_dir": run_dir}
> ```
>
> `from pipeline_app import db as db_mod` and the `compute_initial_status`/`stage_dir_name`
> imports project_service.py already has stay as they are — do not drop the `db_mod` import, the
> plan body's instruction to "stop using the auto-committing db_mod helpers" no longer applies.
> `exist_ok=False` on `run_dir.mkdir` (not the plan's original omission) matters here:
> `_create_once` is retried by T18's caller with a new `run_id` per attempt, so a stale `run_dir`
> from an earlier partial failure must never be silently reused. The two tests below still exercise
> exactly the failure shape they describe (`Path.mkdir` raising on the 2nd call captures the
> stage-dir loop start today the same as it did against the plan's original code — this is a
> behavior-preserving correction, not a test change).

### T17 — A-78: project creation is all-or-nothing

- [ ] Add to `tests/test_project_service.py`:

```python
def test_a_failure_partway_leaves_no_project_at_all(conn, tmp_path: Path, monkeypatch):
    """The project row was inserted and committed, then run_dir.mkdir, then
    one stage row + one mkdir per stage with a commit per row. A failure
    partway left a committed project with a partial set of stage rows that
    nothing repairs, permanently unusable but normal-looking (A-78)."""
    real_mkdir = Path.mkdir
    calls = {"n": 0}

    def flaky(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:            # run_dir succeeds, the first stage dir does not
            raise OSError(28, "No space left on device")
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", flaky)

    with pytest.raises(OSError):
        create_project(conn, tmp_path, "why-kids-quit", "generic", STAGES)

    monkeypatch.undo()
    assert db.list_projects(conn) == []
    assert list((tmp_path / "runs").iterdir()) == []


def test_a_half_created_project_is_distinguishable_from_a_whole_one(conn, tmp_path, monkeypatch):
    """The distinguishability the audit asks for: 'broken' must not present
    as 'a project'. Before the fix the broken run appeared in the project list
    exactly like the good one, minus stage rows nobody looks at."""
    good = create_project(conn, tmp_path, "good-run", "generic", STAGES)
    assert {r["stage_id"] for r in db.list_stages(conn, good["project_id"])} == \
        {"ideation", "scripting"}

    real_mkdir = Path.mkdir
    calls = {"n": 0}

    def flaky(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError(28, "No space left on device")
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", flaky)
    with pytest.raises(OSError):
        create_project(conn, tmp_path, "bad-run", "generic", STAGES)
    monkeypatch.undo()

    projects = db.list_projects(conn)
    assert [p["slug"] for p in projects] == ["good-run"]
```

- [ ] Add to `tests/test_routes_projects.py` (surfacing):

```python
def test_a_failed_creation_is_a_named_error_and_leaves_an_events_row(client, monkeypatch):
    real_mkdir = Path.mkdir
    monkeypatch.setattr(Path, "mkdir",
                        lambda self, *a, **k: (_ for _ in ()).throw(OSError(28, "no space")))

    resp = client.post("/projects", data={"slug": "why-kids-quit", "brand": "generic"},
                       follow_redirects=False)
    monkeypatch.undo()

    assert resp.status_code == 500
    assert "no space" in resp.text            # not a bare traceback
    rows = client.app.state.conn.execute(
        "SELECT * FROM events WHERE kind = 'project.create_failed'").fetchall()
    assert len(rows) == 1 and rows[0]["severity"] == "error"
```

- [ ] Run. Expect **fail**: a project row survives, and the route raises rather than returning 500
      with a message.
- [ ] Implement in `project_service.py` — stop using the auto-committing `db_mod` helpers
      (`db.py` belongs to P1 and must not change), and do the whole creation in one transaction:

```python
def _create_once(conn, repo_root, cleaned_slug, brand, applicable, now) -> dict:
    run_id = f"{cleaned_slug}-{now.strftime('%Y%m%d-%H%M%S')}"
    run_dir = repo_root / "runs" / run_id
    # Defence in depth, unchanged: refuse a directory that escapes runs/.
    if run_dir.resolve().parent != (repo_root / "runs").resolve():
        raise ValueError(f"slug resolves outside the runs directory: {cleaned_slug!r}")

    # NOT db_mod.create_project / db_mod.create_stage_row: those commit per
    # row, which is precisely how a failure partway left a committed project
    # with a partial set of stage rows (A-78). One implicit transaction, one
    # commit, at the end.
    created_dir = False
    try:
        cur = conn.execute(
            "INSERT INTO projects (run_id, slug, brand, created_at) VALUES (?, ?, ?, ?)",
            (run_id, cleaned_slug, brand, now.isoformat()),
        )
        project_id = cur.lastrowid
        for stage in applicable:
            conn.execute(
                "INSERT INTO stages (project_id, stage_id, status) VALUES (?, ?, ?)",
                (project_id, stage.id, compute_initial_status(stage.depends_on).value),
            )
        run_dir.mkdir(parents=True, exist_ok=False)
        created_dir = True
        for stage in applicable:
            (run_dir / stage_dir_name(stage)).mkdir(parents=True, exist_ok=True)
        conn.commit()
    except BaseException:
        conn.rollback()
        if created_dir:                      # only ever remove what this call made
            shutil.rmtree(run_dir, ignore_errors=True)
        raise
    return {"project_id": project_id, "run_id": run_id, "run_dir": run_dir}
```

  (`import shutil`; drop `from pipeline_app import db as db_mod`.) In `routes/projects.py`:

```python
    except (OSError, sqlite3.DatabaseError) as exc:
        obs.record_event(conn, kind="project.create_failed", severity="error",
                         source="routes.projects", message=str(exc),
                         detail={"slug": slug, "brand": brand})
        return PlainTextResponse(f"Could not create the project: {exc}", status_code=500)
```

- [ ] Run the whole app suite — `create_project`'s signature and return shape are unchanged, but
      confirm `tests/test_migrations.py` and `tests/test_routes_stages.py` still pass.
- [ ] Commit: `fix(projects): create a project atomically or not at all (A-78)`

---

### T18 — A-79: a slug collision retries, then 409s — never a 500

- [ ] Add to `tests/test_project_service.py`:

```python
def test_two_projects_created_in_the_same_second_both_succeed(conn, tmp_path: Path):
    """run_id uniqueness rested entirely on second-resolution, so a
    double-submitted form raised sqlite3.IntegrityError (A-79)."""
    now = datetime.datetime(2026, 7, 25, 14, 32, 0, tzinfo=datetime.timezone.utc)

    first = create_project(conn, tmp_path, "My Topic", "generic", STAGES, now=now)
    second = create_project(conn, tmp_path, "my_topic", "generic", STAGES, now=now)

    assert first["run_id"] == "my-topic-20260725-143200"
    assert second["run_id"] == "my-topic-20260725-143201"      # advanced, not suffixed
    assert first["run_dir"].is_dir() and second["run_dir"].is_dir()
    assert len(db.list_projects(conn)) == 2


def test_run_id_keeps_the_shape_browse_service_anchors_on(conn, tmp_path: Path):
    """browse_service._RUN_ID_TIMESTAMP_RE is `-(\\d{8}-\\d{6})$` — anchored at
    the END. A disambiguating suffix would silently stop /browse dating the
    run, so collisions advance the timestamp instead."""
    import re
    now = datetime.datetime(2026, 7, 25, 14, 32, 0, tzinfo=datetime.timezone.utc)
    for _ in range(3):
        result = create_project(conn, tmp_path, "dup", "generic", STAGES, now=now)
        assert re.search(r"-(\d{8}-\d{6})$", result["run_id"])


def test_an_exhausted_retry_window_raises_a_named_error_not_IntegrityError(conn, tmp_path):
    from pipeline_app.project_service import _MAX_RUN_ID_ATTEMPTS, RunIdCollision
    now = datetime.datetime(2026, 7, 25, 14, 32, 0, tzinfo=datetime.timezone.utc)
    for i in range(_MAX_RUN_ID_ATTEMPTS):
        create_project(conn, tmp_path, "dup", "generic", STAGES,
                       now=now + datetime.timedelta(seconds=i))

    with pytest.raises(RunIdCollision):
        create_project(conn, tmp_path, "dup", "generic", STAGES, now=now)
```

- [ ] Add to `tests/test_routes_projects.py`:

```python
def test_a_run_id_collision_returns_409_with_retry_advice_not_500(client, monkeypatch):
    from pipeline_app import routes
    from pipeline_app.project_service import RunIdCollision

    monkeypatch.setattr(
        routes.projects, "create_project",
        lambda *a, **k: (_ for _ in ()).throw(RunIdCollision("retry in a moment")),
    )
    resp = client.post("/projects", data={"slug": "dup", "brand": "generic"},
                       follow_redirects=False)

    assert resp.status_code == 409
    assert "retry" in resp.text.lower()
```

- [ ] Run. Expect **fail**: `sqlite3.IntegrityError` propagates and the TestClient re-raises it.
- [ ] Implement in `project_service.py`:

```python
# run_id's shape is frozen: browse_service._RUN_ID_TIMESTAMP_RE anchors
# `-(\d{8}-\d{6})$` at the END of the directory name, so a disambiguating
# suffix would silently stop /browse dating the run. Collisions are resolved
# by advancing the timestamp, never by appending to it (A-79).
_MAX_RUN_ID_ATTEMPTS = 5


class RunIdCollision(RuntimeError):
    """Every candidate run_id inside the retry window was already taken."""


def create_project(conn, repo_root, slug, brand, stage_defs, now=None) -> dict:
    cleaned_slug = sanitize_slug(slug)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    applicable = [s for s in stage_defs if s.brand_scope is None or s.brand_scope == brand]
    for attempt in range(_MAX_RUN_ID_ATTEMPTS):
        try:
            return _create_once(conn, repo_root, cleaned_slug, brand, applicable, now)
        except sqlite3.IntegrityError:
            obs.log("project.run_id_collision", level="warning",
                    slug=cleaned_slug, attempt=attempt + 1)
            now = now + datetime.timedelta(seconds=1)
    raise RunIdCollision(
        f"could not allocate a unique run_id for {cleaned_slug!r} after "
        f"{_MAX_RUN_ID_ATTEMPTS} attempts — please retry in a moment"
    )
```

  and in `routes/projects.py`, between the `ValueError` and the catch-all clauses:

```python
    except RunIdCollision as exc:
        obs.record_event(conn, kind="project.run_id_collision", severity="warning",
                         source="routes.projects", message=str(exc), detail={"slug": slug})
        return PlainTextResponse(str(exc), status_code=409)
```

- [ ] Run. Green. Confirm `tests/test_routes_browse.py` still passes — the run_id shape is unchanged
      by design.
- [ ] Commit: `fix(projects): retry a colliding run_id, then 409 instead of 500 (A-79)`

---

### T19 — Adopt P4's canonical mapping (blocked on P4; the plan is complete without it)

Do this only once P4 has landed §6's contract. Nothing here changes behaviour.

- [ ] Add:

```python
def test_the_editor_reads_the_same_mapping_pipeline_config_publishes(client):
    from pipeline_app.pipeline_config import stage_id_by_skill
    test_client, _ = client
    defs = test_client.app.state.stage_defs
    assert stage_id_by_skill(defs) == {"shorts-ideation": "ideation",
                                       "shorts-scripting": "scripting",
                                       "shorts-styleboard": "styleboard"}
```

- [ ] Run — fails with `ImportError` until P4 lands.
- [ ] Delete `_stage_id_by_skill` and `_template_path` from `routes/skills.py`; import
      `stage_id_by_skill` and `stage_template_path` from `pipeline_app.pipeline_config`.
- [ ] Run the full app suite. Green.
- [ ] Commit: `refactor(skills): read the skill->stage map from pipeline_config (A-48)`

---

### T20 — `| safe` producer-side sanitization at `inspector.py:45` (D-47 rule; blocked on P15)

Independent of every other task in this package and of P4 — it needs only P15's
`browse_service.sanitize_html`. `inspector_inspect` hands `markdown.markdown(body)` straight into
the context at `routes/inspector.py:45`, and `inspector.html` renders it `| safe`. The inspector is
deliberately "point it at any `.md` file on disk" (`:21-25`), and the files most worth pointing it
at are the discovery corpus — attacker-authored post bodies captured unattended by the daily cron.
That page has same-origin authority over every mutating route the app exposes, including
`POST /skills/<name>/save`.

- [ ] Add to `pipeline-app/tests/test_routes_inspector.py`:

```python
def test_a_script_tag_in_inspected_markdown_does_not_survive_into_the_page(client):
    """The inspector renders arbitrary on-disk markdown through
    markdown.markdown() into a `| safe` template slot. The files it is
    pointed at include the discovery corpus -- post bodies captured
    unattended from the public web -- and the page has same-origin authority
    over every mutating route. `| safe` means "sanitized by its producer"
    (D-47): the sanitizing happens here, in the route, not in the template.
    """
    test_client, tmp_path = client
    fixture = tmp_path / "hostile.md"
    fixture.write_text(
        "---\nstage: shorts-ideation\n---\n\n"
        "# Heading\n\n"
        "<script>fetch('/skills/shorts-ideation/save',{method:'POST'})</script>\n\n"
        "<img src=x onerror=\"alert(1)\">\n\n"
        "<a href=\"javascript:alert(1)\">click</a>\n\n"
        "Legitimate **bold** body text.\n",
        encoding="utf-8",
    )

    resp = test_client.post("/inspector", data={"path": str(fixture)})

    assert resp.status_code == 200
    assert "<script" not in resp.text
    assert "onerror" not in resp.text
    assert "javascript:" not in resp.text
    # Distinguishability: sanitizing must not be indistinguishable from
    # rendering nothing -- the legitimate markup survives.
    assert "<h1>Heading</h1>" in resp.text
    assert "<strong>bold</strong>" in resp.text
    assert "shorts-ideation" in resp.text          # frontmatter still parsed


def test_sanitization_happens_in_the_route_not_the_template(client):
    """Producer-side, uniformly. A consumer-side filter has to be reapplied at
    every `| safe` site and fails open the moment someone forgets one -- so
    the value in the context is already clean, before any template runs."""
    test_client, tmp_path = client
    fixture = tmp_path / "hostile.md"
    fixture.write_text("---\nstage: x\n---\n\n<script>bad()</script>\n\nok\n", encoding="utf-8")

    resp = test_client.post("/inspector", data={"path": str(fixture)})

    assert "<script" not in resp.context["body_html"]
    assert "ok" in resp.context["body_html"]
```

- [ ] Run `python -m pytest tests/test_routes_inspector.py -q`. Expect **fail**: the `<script>` tag
      and the `onerror` attribute are both present in `resp.text` — `markdown.markdown` passes raw
      HTML through by default and the template's `| safe` renders it verbatim.
- [ ] Implement in `routes/inspector.py` — import the filter and apply it where the value is
      produced:

```python
from pipeline_app.browse_service import sanitize_html
```

  and at `:45`, replace `"body_html": markdown.markdown(body)` with:

```python
                    # `| safe` means "sanitized by its producer" (D-47). The
                    # inspector is a deliberately open "point it at any .md on
                    # disk" tool, and the corpus it is pointed at is captured
                    # unattended from the public web, so the markdown reaching
                    # here is attacker-authored by design. Sanitizing here, not
                    # in inspector.html, is the repo-wide rule: a consumer-side
                    # filter has to be reapplied at every `| safe` site and
                    # fails open the moment one is missed.
                    "body_html": sanitize_html(markdown.markdown(body)),
```

  Leave `inspector.html` alone — P15 owns it, and adding a template-side filter would break the
  rule this task exists to apply.

- [ ] Run. Green.
- [ ] Run the full app suite once more: `python -m pytest -q`.
- [ ] Commit: `fix(inspector): sanitize rendered markdown at the producer (D-47 rule)`

---

## 4. Finding → test map

Every finding, the named test that fails before its fix and passes after, and the Three-Test-Rule
role each test plays for `silent` findings.

| Finding | Mode | Test file | Test | Role |
|---|---|---|---|---|
| A-48 | silent | test_routes_skills.py | `test_styleboard_kickoff_template_is_editable` | fault |
| A-48 | silent | test_routes_skills.py | `test_missing_template_file_is_distinguishable_from_no_template_at_all` | distinguishability |
| A-48 | silent | test_routes_skills.py | `test_a_stage_with_no_editor_binding_is_findable` | surfacing |
| A-48 | — | test_routes_skills.py | `test_the_editor_reads_the_same_mapping_pipeline_config_publishes` (T19) | contract |
| A-49 | silent | test_routes_skills.py | `test_unknown_target_is_rejected_and_writes_nothing` | fault |
| A-49 | silent | test_routes_skills.py | `test_a_save_that_wrote_nothing_is_not_the_same_response_as_a_save_that_wrote` | distinguishability |
| A-49 | silent | test_routes_skills.py | `test_a_rejected_save_is_findable_afterwards[A-49]` | surfacing |
| A-50 | silent | test_routes_skills.py | `test_kickoff_save_for_a_stageless_skill_is_rejected_and_creates_no_None_md` | fault |
| A-50 | silent | test_routes_skills.py | `test_stageless_kickoff_rejection_differs_from_a_real_kickoff_save` | distinguishability |
| A-50 | silent | test_routes_skills.py | `test_a_rejected_save_is_findable_afterwards[A-50]` | surfacing |
| A-51 | silent | test_routes_skills.py | `test_blank_content_never_truncates_a_file` (4 params) | fault |
| A-51 | silent | test_routes_skills.py | `test_skill_md_save_requires_loadable_frontmatter` (5 params) | fault |
| A-51 | silent | test_routes_skills.py | `test_a_kickoff_template_is_not_held_to_the_frontmatter_rule` | distinguishability |
| A-51 | silent | test_routes_skills.py | `test_detail_flags_a_missing_skill_md_instead_of_rendering_empty` | distinguishability |
| A-51 | silent | test_routes_skills.py | `test_a_rejected_save_is_findable_afterwards[A-51-blank, A-51-frontmatter]` | surfacing |
| A-52 | silent | test_routes_skills.py | `test_kickoff_template_save_is_committed_like_skill_md` | fault |
| A-52 | silent | test_routes_skills.py | `test_both_editable_surfaces_have_the_same_durability` | distinguishability |
| A-52 | silent | test_routes_skills.py | `test_a_successful_save_is_findable_and_is_a_different_row` | surfacing |
| A-53 | silent | test_git_helper.py | `test_commit_is_scoped_to_the_file_and_leaves_unrelated_staged_work_alone` | fault |
| A-53 | silent | test_git_helper.py | `test_unchanged_content_is_a_no_op_even_with_unrelated_staged_work` | distinguishability |
| A-53 | silent | test_routes_skills.py | `test_skill_md_save_produces_a_real_scoped_commit` | surfacing (the commit is the record) |
| A-54 | loud | test_routes_skills.py | `test_a_failed_commit_still_saves_the_file_and_warns_rather_than_500ing` | fault |
| A-54 | loud | test_routes_skills.py | `test_the_three_save_outcomes_are_three_different_responses` | distinguishability |
| A-54 | loud | test_routes_skills.py | `test_a_failed_commit_is_findable_at_error_severity` | surfacing |
| A-55 | silent | test_routes_skills.py | `test_browser_crlf_is_written_as_lf_not_doubled[SKILL.md]` | fault |
| A-55 | silent | test_routes_skills.py | `test_browser_crlf_is_written_as_lf_not_doubled[kickoff_template]` | distinguishability (both surfaces, byte-level) |
| A-55 | silent | test_routes_skills.py | `test_skill_md_save_produces_a_real_scoped_commit` | surfacing (a clean diff, not a whole-file rewrite) |
| A-56 | latent | test_routes_skills.py | `test_a_symlinked_skill_directory_is_not_discovered` | fault |
| A-78 | silent | test_project_service.py | `test_an_overlong_slug_is_rejected_before_anything_is_created` | fault |
| A-78 | silent | test_project_service.py | `test_a_failure_partway_leaves_no_project_at_all` | fault |
| A-78 | silent | test_project_service.py | `test_a_half_created_project_is_distinguishable_from_a_whole_one` | distinguishability |
| A-78 | silent | test_project_service.py | `test_a_slug_at_the_limit_is_still_accepted` | distinguishability (bound rejects only the overlong case) |
| A-78 | silent | test_routes_projects.py | `test_a_failed_creation_is_a_named_error_and_leaves_an_events_row` | surfacing |
| A-79 | loud | test_project_service.py | `test_two_projects_created_in_the_same_second_both_succeed` | fault |
| A-79 | loud | test_routes_projects.py | `test_a_run_id_collision_returns_409_with_retry_advice_not_500` | fault |
| A-79 | loud | test_project_service.py | `test_an_exhausted_retry_window_raises_a_named_error_not_IntegrityError` | distinguishability |
| A-79 | loud | test_project_service.py | `test_run_id_keeps_the_shape_browse_service_anchors_on` | regression guard |
| D-49 | silent | test_git_helper.py | `test_commit_is_scoped_to_the_file_and_leaves_unrelated_staged_work_alone` | fault |
| D-49 | silent | test_git_helper.py | `test_unchanged_content_is_a_no_op_even_with_unrelated_staged_work` | distinguishability |
| D-49 | silent | test_routes_skills.py | `test_a_successful_save_is_findable_and_is_a_different_row` | surfacing (detail carries the sha) |
| D-50 | silent | test_git_helper.py | `test_a_hanging_git_reports_failure_rather_than_hanging` | fault |
| D-50 | silent | test_git_helper.py | `test_every_git_call_carries_a_timeout` | fault (structural) |
| D-50 | silent | test_git_helper.py | `test_git_missing_from_path_reports_failure_rather_than_raising` | distinguishability (`failed` vs `no_change`) |
| D-50 | silent | test_routes_skills.py | `test_a_failed_commit_is_findable_at_error_severity` | surfacing |
| D-51 | latent | test_git_helper.py | `test_refuses_to_commit_on_a_protected_branch` | fault |
| D-51 | latent | test_git_helper.py | `test_app_commits_carry_the_pipeline_app_identity` | distinguishability (app vs hand-authored history) |
| F-21 | silent | test_routes_skills.py | `test_kickoff_template_save_is_committed_like_skill_md` | the inversion itself |
| D-47 (P3/P15's; P5 owns the `inspector.py` producer site) | silent | test_routes_inspector.py | `test_a_script_tag_in_inspected_markdown_does_not_survive_into_the_page` | fault + distinguishability (hostile markup stripped, legitimate markup survives) |
| D-47 (as above) | silent | test_routes_inspector.py | `test_sanitization_happens_in_the_route_not_the_template` | producer-side placement |

**No test in this package asserts a value the code hard-codes.** The deleted
`test_stage_id_by_skill_maps_music_brief_but_not_the_specialist` did exactly that; its replacements
assert what the *editor page renders* and what `pipeline.yaml` *declares*.

---

## 5. Tests deleted or inverted

| File:line | Test | Action | Replacement |
|---|---|---|---|
| `pipeline-app/tests/test_routes_skills.py:54-68` | `test_save_kickoff_template_does_not_commit` | **Inverted** (F-21) — it asserted `calls == []` with no rationale, pinning A-52 (S1) so that fixing it presented as breaking a test | `test_kickoff_template_save_is_committed_like_skill_md` + `test_both_editable_surfaces_have_the_same_durability` (T14) |
| `pipeline-app/tests/test_routes_skills.py:86-92` | `test_stage_id_by_skill_maps_music_brief_but_not_the_specialist` | **Deleted** — asserts on a literal the module hard-codes (anti-tautology rule 1), and its docstring calls the registry "a duplicate registry that fails silently" while asserting the duplicate is correct. The symbol it imports ceases to exist in T2 | `test_styleboard_kickoff_template_is_editable`, `test_missing_template_file_is_distinguishable_from_no_template_at_all` (T2/T3), `test_the_editor_reads_the_same_mapping_pipeline_config_publishes` (T19) |
| `pipeline-app/tests/test_routes_skills.py:37-51` | `test_save_skill_md_writes_file_and_commits` | **Replaced** — `assert len(calls) == 1` asserts a mock was called where the real effect (a scoped commit in a real repo) is observable (anti-tautology rule 2) | `test_skill_md_save_produces_a_real_scoped_commit` (T14) |

**Amended, not deleted** (they assert real desired behaviour and stay):

| File:line | Test | Amendment |
|---|---|---|
| `pipeline-app/tests/test_git_helper.py:9-14` | `repo` fixture | `git init -b skill-edits` + an initial `--allow-empty` commit — the bare `git init` lands on `main`/`master`, which T13 starts refusing, and leaves HEAD unborn (T1) |
| `pipeline-app/tests/test_git_helper.py:31-46` | `test_commit_skill_edit_is_a_no_op_when_content_is_unchanged` | Keep; add `assert commit_skill_edit(...).status == "no_change"` so "made no commit because nothing changed" is asserted as distinct from "made no commit because git failed" (T10) |
| `pipeline-app/tests/test_routes_skills.py:10-20` | `client` fixture | Real three-stage `pipeline.yaml`, four skills with valid frontmatter, a `styleboard.md` template, and a git repo (T1) |
| `pipeline-app/tests/test_routes_skills.py:71-78`, `:95-114` | the two traversal tests | Keep verbatim. They prove the set-membership defence runs on the save path, and the audit's own analysis (appendix A, "the residual escape") confirms the defence is sound in shape — A-56 is the one gap and T11 closes it without weakening these |
| `pipeline-app/tests/test_project_service.py:45-63` | the two traversal/unusable-slug tests | Keep verbatim; T16/T17 must not regress them |

**Nothing is deleted or amended in `tests/test_routes_inspector.py`** — its two existing tests
(`:17-33`) assert real behaviour and stay verbatim. T20 only **adds** two tests to that file; in
particular `test_inspector_parses_frontmatter_and_body` must keep passing, which is the guard that
sanitization did not eat legitimate content.

---

## 6. Contract for P4 — where the authoritative skill→stage mapping comes from

`routes/skills.py` must never again hold a hand-maintained copy of `pipeline.yaml`. P4 owns
`pipeline_config.py` and `pipeline.yaml`; P5 owns the route that consumes them. The mapping and the
template-path convention are P4's to publish, not P5's to duplicate.

**P4 adds to `pipeline-app/pipeline_app/pipeline_config.py`:**

```python
def stage_id_by_skill(stage_defs: list[StageDef]) -> dict[str, str]:
    """Skill name -> stage id, derived from the loaded topology.

    Total over pipeline.yaml and containing no key that is not some stage's
    `skill`. The skill editor (routes/skills.py) binds its kickoff-template
    form through this; a hardcoded copy had already lost `shorts-styleboard`
    (A-48). A skill absent from the result HAS NO STAGE -- that is a
    meaningful answer, not a lookup miss, and the editor renders it as
    "no kickoff template applies" rather than writing `None.md` (A-50).
    """
    return {s.skill: s.id for s in stage_defs}


def stage_template_path(repo_root: Path, stage_id: str) -> Path:
    """Canonical on-disk location of a stage's kickoff template.

    P4 owns pipeline-app/stage_templates/; P5 must not reconstruct this path.
    """
    return repo_root / "pipeline-app" / "stage_templates" / f"{stage_id}.md"
```

**P4 adds to `_validate_topology` (`pipeline_config.py:35-66`), alongside the existing duplicate-id
check:** reject two stages declaring the same `skill`.

```python
    seen_skills: dict[str, str] = {}
    for stage in stages:
        if stage.skill in seen_skills:
            raise ValueError(
                f"pipeline.yaml: stages '{seen_skills[stage.skill]}' and '{stage.id}' both "
                f"declare skill '{stage.skill}'; the skill editor's stage binding would be "
                f"ambiguous and it would silently edit one stage's template while showing "
                f"the other's"
            )
        seen_skills[stage.skill] = stage.id
```

Without this, `{s.skill: s.id for s in stage_defs}` last-wins silently and the editor edits the
wrong template — the same class of defect as A-48, one layer down.

**P4 also owns (P5 does not implement, and its tests must not assert it):** that every stage in
`pipeline.yaml` has a template file at `stage_template_path(...)`. P5 handles a missing file
gracefully and distinguishably (T3) but does not decide whether one is required.

**Sequencing.** P5 is not blocked on P4. T2 implements a private `_stage_id_by_skill` with the
identical body and a comment pointing here; T19 deletes it and imports P4's once available. If P4
changes the template naming convention, P4 must land `stage_template_path` **before** doing so — a
convention change with P5's private `_template_path` still in place silently repoints the editor at
files that do not exist.

**What P5 will NOT accept as a substitute:** a mapping that P5 must keep in sync, a mapping keyed by
stage id rather than skill name, or a lookup that raises/defaults on a skill with no stage. The
three tool specialists (`elevenlabs-audio`, `elevenlabs-music`, `midjourney-prompting`) and
`rgs-pairing-review` are legitimately stage-less; `None` is the correct answer for them and the
editor depends on getting it.

---

## 7. Cross-package notes (not implemented here)

These are consequences of this package's changes that land in files P5 does not own. Each is a
one-line ask, recorded so the owning package can pick it up; **none of them blocks P5**, and none
of P5's tests assert on markup.

- **P15 (`templates/skill_editor.html`).** `skill_detail` now supplies four new context keys:
  `stage_id`, `kickoff_template_applies`, `kickoff_template_missing`, `skill_md_missing`, plus a
  `warning` string from the redirect query. The template currently renders the kickoff form
  unconditionally for all 13 skills (`skill_editor.html:12-17`), which is the front half of A-50 —
  it should render that form only `{% if kickoff_template_applies %}`, show a banner when
  `skill_md_missing`, and render `warning` when present. P5's route rejects the bad save regardless,
  so the defect is closed either way; this removes the dead button.
- **P15 (`browse_service.py`) — T20's only blocker.** P5 imports `sanitize_html(html: str) -> str`
  from `browse_service` and calls it at `routes/inspector.py:45`. P5 does not edit `browse_service.py`
  and does not vendor a copy. Two expectations of that filter, both asserted by T20: it strips
  `<script>`, `on*` event attributes and `javascript:` URLs, and it **preserves** ordinary markdown
  output (`<h1>`, `<strong>`, `<a href="https://...">`) — a filter that stripped everything would
  make "sanitized" indistinguishable from "rendered nothing". T20 is the last task to run in this
  package if P15 lands late; nothing else here depends on it.
- **P15 (`browse_service.py`).** `_RUN_ID_TIMESTAMP_RE` (`:45`) anchors `-(\d{8}-\d{6})$` at the end
  of the run directory name. P5 has **frozen** the `run_id` shape because of it (A-79 is fixed by
  advancing the timestamp, not by suffixing). If P15 ever relaxes that regex, say so — P5 would
  prefer a random suffix.
- **P1 (`schema.sql`) + P15 (`project_list.html`).** A-79's remaining half — "two differently-named
  projects remain indistinguishable in the project list" — needs a `projects.display_name` column
  holding the raw entered name (P1) and a template that shows it beside `run_id` (P15). P5 fixes the
  500 and the collision; it cannot fix the display without editing a schema and a template it does
  not own.
- **P1 (`db.py`).** `db_mod.create_project` and `db_mod.create_stage_row` commit per row (`db.py:37`,
  `:54`), which is the mechanism of A-78. P5 stops calling them from `project_service.py` rather than
  changing them. If P1 later adds non-committing variants, P5's `_create_once` should adopt them.
- **P3 (`routes/stages.py`).** A-78's blast radius notes that a stage with no row 404s as "Stage not
  applicable to this project". P5 makes partial projects impossible going forward; P3 owns whether
  that 404 message is honest for projects created before this fix.
