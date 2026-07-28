# Skill Markdown File Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the six generic ContentStudio pipeline skills (and the two
RGS-specific skills) a real, versioned, immutable file handoff through
`rgs-briefs/`, enforced by a hook — and fix `pipeline-app`'s stage page so it
renders markdown instead of dumping raw `#`/`-` text.

**Architecture:** A new pure-Python resolver script
(`scripts/resolve_brief_version.py`) is the single source of truth for "what's
the latest version of this artifact" and "what's the next version's filename"
— skills call it via `Bash` instead of eyeballing a glob. A new `PreToolUse`
hook (`.claude/hooks/protect_briefs.py`) blocks `Edit` on `rgs-briefs/**` and
blocks `Write` to an already-existing path there, enforcing immutability
independent of which skill (or human) is driving the tool call. Each of the
eight skill `SKILL.md` files gets a "File I/O contract" section describing how
to resolve upstream input and write output through this system, conditional on
whether `pipeline-app` already gave the turn an output path (app-driven mode,
unchanged) or not (standalone mode, the new behavior). `pipeline-app`'s
`grounding_service.py` loses its rename-based `supersede_previous_brief()` in
favor of the same versioned-filename convention, and its stage page renders
markdown to HTML using the `markdown` library already proven in
`inspector.py`.

**Tech Stack:** Python 3, `pyyaml`, `pytest`, FastAPI/Jinja2 (`pipeline-app`),
Claude Code `PreToolUse` hooks, Markdown-formatted Claude Code skills.

## Global Constraints

- Files under `rgs-briefs/` are immutable once written — never `Edit`, never
  overwrite via `Write`. A revision is always a new, higher-version file.
- Naming: `YYYY-MM-DD-<slug>-<kind>.md` for stage artifacts (`<kind>` ∈
  `concept-brief, script, voiceover-brief, visual-prompts, assembly,
  social-repurpose`); `YYYY-MM-DD-<topic-slug>.md` for grounding briefs. A
  revision appends `-v2`, `-v3`, … before `.md`.
- Frontmatter always carries an integer `version:` field; `supersedes:` is
  present only when `version > 1`, pointing at the immediately-prior file's
  `rgs-briefs/...` relative path.
- Version resolution reads the frontmatter `version:` field, never sorts by
  filename alone (`-v2`..`-v9` sort before `-v10` lexically).
- `pipeline-app`'s separate `runs/<run_id>/<stage_dir>/artifact.vN.md`
  convention (`pipeline_app/artifacts.py`) is untouched by this plan — it's a
  distinct file family from `rgs-briefs/`.
- Every new Python module gets pytest coverage; run tests from the correct
  directory (repo root for `scripts/`/`tests/`, `pipeline-app/` for
  `pipeline_app/`/`pipeline-app/tests/` — they are two separate test suites
  with separate `requirements.txt`).
- **Every existing file this plan edits is CRLF-terminated (`\r\n`), and this
  plan's code fences are LF.** For every task below that modifies an
  existing file via the `Edit` tool: `Read` the live file immediately before
  editing and build the `old_string` from what `Read` actually returns, not
  by retyping the markdown shown in a task's steps. Two tasks (3 and 9) call
  this out explicitly because a prior draft of this plan quoted those two
  files' content incorrectly (wrong dash character; wrong tail anchor) — the
  same discipline applies to every other file-modifying task even where it
  isn't repeated inline.
- **`scripts/resolve_brief_version.py` without `--next` exits 1 and prints
  `NONE\t0` when nothing matches.** Every "resolve the upstream input" step in
  Tasks 8-13's `SKILL.md` edits treats that as the expected "no file yet, fall
  back to chat-pasted input" case (per the design spec §4), not an error the
  skill should surface as a failure — a `Bash` tool call returning exit 1
  here is normal, not a bug to fix.
- Reference spec: `docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md`.

---

## File Structure

| File | Change |
|---|---|
| `requirements.txt` (root) | Add `pyyaml` |
| `scripts/resolve_brief_version.py` | New — version resolution CLI |
| `tests/test_resolve_brief_version.py` | New |
| `.claude/hooks/protect_briefs.py` | New — `PreToolUse` enforcement hook |
| `tests/test_protect_briefs.py` | New |
| `.claude/settings.json` | New — wires the hook |
| `rgs-briefs/README.md` | Modify — versioned schema + resolver mention |
| `pipeline-app/pipeline_app/grounding_service.py` | Modify — remove `supersede_previous_brief` |
| `pipeline-app/pipeline_app/routes/stages.py` | Modify — remove supersede call site; render markdown |
| `pipeline-app/pipeline_app/templates/stage.html` | Modify — render HTML instead of `<pre>` |
| `pipeline-app/tests/test_grounding_service.py` | Modify — remove 2 obsolete tests |
| `pipeline-app/tests/test_routes_stages.py` | Modify — add markdown-rendering test |
| `.claude/skills/rgs-grounding/SKILL.md` | Modify — versioned write |
| `.claude/skills/rgs-pairing-review/SKILL.md` | Modify — latest-version-only scan |
| `.claude/skills/shorts-ideation/SKILL.md` | Modify — File I/O contract |
| `.claude/skills/shorts-scripting/SKILL.md` | Modify — File I/O contract |
| `.claude/skills/voiceover-brief/SKILL.md` | Modify — File I/O contract |
| `.claude/skills/visual-prompts/SKILL.md` | Modify — File I/O contract |
| `.claude/skills/shorts-assembly/SKILL.md` | Modify — File I/O contract |
| `.claude/skills/social-repurpose/SKILL.md` | Modify — File I/O contract |

---

### Task 1: `scripts/resolve_brief_version.py` — version resolution

**Files:**
- Create: `scripts/resolve_brief_version.py`
- Test: `tests/test_resolve_brief_version.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `find_latest(directory: Path, slug: str, kind: str | None) -> tuple[Path | None, int]`
  — highest-version `(path, version)` matching `slug`/`kind`, or `(None, 0)`.
  `kind=None` matches a grounding brief (`YYYY-MM-DD-<slug>.md`, no kind
  suffix).
- Produces: `next_filename(directory: Path, slug: str, kind: str | None, date: str) -> tuple[str, int]`
  — `(filename, version)` for the next write.
- Produces: `parse_frontmatter(text: str) -> dict` — raises `ValueError` on
  missing/malformed frontmatter.
- CLI: `python scripts/resolve_brief_version.py --dir rgs-briefs --slug <slug> [--kind <kind>] [--next --date YYYY-MM-DD]`.
  Prints `<path>\t<version>` (or `NONE\t0` with exit 1 if nothing found and
  `--next` wasn't given). Downstream tasks (skills) call this exact CLI shape.

- [ ] **Step 1: Add `pyyaml` to root `requirements.txt`**

Read the current file first, then edit:

```
# ContentStudio corpus-archive toolkit — laptop dependencies.
# Install with:  pip install -r requirements.txt
requests>=2.31
yt-dlp>=2025.1.1
youtube-transcript-api>=1.0
pyyaml>=6.0
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_resolve_brief_version.py`:

```python
from pathlib import Path

import pytest

from scripts.resolve_brief_version import find_latest, next_filename, parse_frontmatter


def _write(dir_: Path, name: str, version: int, extra: str = "") -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    path = dir_ / name
    path.write_text(
        f"---\ndate: 2026-07-28\nversion: {version}\n{extra}---\n\nbody\n",
        encoding="utf-8",
    )
    return path


def test_parse_frontmatter_returns_mapping():
    text = "---\nversion: 1\nkind: script\n---\n\nbody text\n"
    assert parse_frontmatter(text) == {"version": 1, "kind": "script"}


def test_parse_frontmatter_raises_on_missing_block():
    with pytest.raises(ValueError):
        parse_frontmatter("no frontmatter here\n")


def test_find_latest_returns_none_when_nothing_matches(tmp_path: Path):
    assert find_latest(tmp_path, "my-short", "script") == (None, 0)


def test_find_latest_returns_only_version(tmp_path: Path):
    p = _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    assert find_latest(tmp_path, "my-short", "script") == (p, 1)


def test_find_latest_prefers_higher_version_over_v1(tmp_path: Path):
    _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    p2 = _write(tmp_path, "2026-07-28-my-short-script-v2.md", 2)
    assert find_latest(tmp_path, "my-short", "script") == (p2, 2)


def test_find_latest_ignores_other_slugs_and_kinds(tmp_path: Path):
    _write(tmp_path, "2026-07-28-other-short-script.md", 1)
    _write(tmp_path, "2026-07-28-my-short-voiceover-brief.md", 1)
    assert find_latest(tmp_path, "my-short", "script") == (None, 0)


def test_find_latest_grounding_brief_has_no_kind(tmp_path: Path):
    p = _write(tmp_path, "2026-07-28-my-short.md", 1)
    assert find_latest(tmp_path, "my-short", None) == (p, 1)


def test_find_latest_raises_on_malformed_frontmatter(tmp_path: Path):
    tmp_path.mkdir(exist_ok=True)
    bad = tmp_path / "2026-07-28-my-short-script.md"
    bad.write_text("no frontmatter\n", encoding="utf-8")
    with pytest.raises(ValueError):
        find_latest(tmp_path, "my-short", "script")


def test_next_filename_first_write_is_v1_with_no_suffix(tmp_path: Path):
    filename, version = next_filename(tmp_path, "my-short", "script", "2026-07-28")
    assert filename == "2026-07-28-my-short-script.md"
    assert version == 1


def test_next_filename_second_write_is_v2(tmp_path: Path):
    _write(tmp_path, "2026-07-28-my-short-script.md", 1)
    filename, version = next_filename(tmp_path, "my-short", "script", "2026-07-28")
    assert filename == "2026-07-28-my-short-script-v2.md"
    assert version == 2


def test_next_filename_grounding_brief_has_no_kind_suffix(tmp_path: Path):
    filename, version = next_filename(tmp_path, "my-topic", None, "2026-07-28")
    assert filename == "2026-07-28-my-topic.md"
    assert version == 1
```

- [ ] **Step 3: Run tests to verify they fail**

From the repo root:

```bash
python -m pytest tests/test_resolve_brief_version.py -v
```

Expected: `ModuleNotFoundError: No module named 'scripts.resolve_brief_version'`
(or similar — the module doesn't exist yet).

- [ ] **Step 4: Create `scripts/__init__.py` if it doesn't already make `scripts` importable**

Check first:

```bash
ls scripts/__init__.py 2>/dev/null || echo "MISSING"
```

If missing, create an empty `scripts/__init__.py`.

- [ ] **Step 5: Write the implementation**

Create `scripts/resolve_brief_version.py`:

```python
#!/usr/bin/env python3
"""Resolve the latest version of an rgs-briefs/ artifact, or compute the
filename/version the next write should use.

Version resolution reads the frontmatter `version:` field -- never sorts by
filename alone, since "-v2".."-v9" sort before "-v10" lexically.

Usage:
  resolve_brief_version.py --slug <slug> --kind <kind>            # stage artifact
  resolve_brief_version.py --slug <topic-slug>                    # grounding brief (no --kind)
  resolve_brief_version.py --slug <slug> --kind <kind> --next --date YYYY-MM-DD
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def parse_frontmatter(text: str) -> dict:
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("no frontmatter block found")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("frontmatter did not parse to a mapping")
    return data


def _pattern(slug: str, kind: str | None) -> re.Pattern:
    suffix = f"-{re.escape(kind)}" if kind else ""
    return re.compile(rf"^\d{{4}}-\d{{2}}-\d{{2}}-{re.escape(slug)}{suffix}(-v(\d+))?\.md$")


def find_latest(directory: Path, slug: str, kind: str | None) -> tuple[Path | None, int]:
    if not directory.exists():
        return None, 0
    pattern = _pattern(slug, kind)
    best_path: Path | None = None
    best_version = 0
    for path in sorted(directory.glob("*.md")):
        if not pattern.match(path.name):
            continue
        try:
            meta = parse_frontmatter(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from exc
        version = meta.get("version")
        if not isinstance(version, int):
            raise ValueError(f"{path}: frontmatter missing an integer 'version' field")
        if version > best_version:
            best_version = version
            best_path = path
    return best_path, best_version


def next_filename(directory: Path, slug: str, kind: str | None, date: str) -> tuple[str, int]:
    _, best_version = find_latest(directory, slug, kind)
    next_version = best_version + 1
    suffix = f"-{kind}" if kind else ""
    version_suffix = "" if next_version == 1 else f"-v{next_version}"
    return f"{date}-{slug}{suffix}{version_suffix}.md", next_version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default="rgs-briefs")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--kind", default=None, help="omit for a grounding brief")
    parser.add_argument("--next", action="store_true")
    parser.add_argument("--date", default=None, help="required with --next, e.g. 2026-07-28")
    args = parser.parse_args(argv)

    directory = Path(args.dir)

    if args.next:
        if not args.date:
            parser.error("--next requires --date YYYY-MM-DD")
        filename, version = next_filename(directory, args.slug, args.kind, args.date)
        print(f"{filename}\t{version}")
        return 0

    path, version = find_latest(directory, args.slug, args.kind)
    if path is None:
        print("NONE\t0")
        return 1
    print(f"{path}\t{version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest tests/test_resolve_brief_version.py -v
```

Expected: all PASS. Fix the deliberately-mis-indented test from Step 2 if you
copied it as-is.

- [ ] **Step 7: Manual CLI smoke test**

```bash
mkdir -p /tmp/rgs-briefs-smoke
printf -- "---\ndate: 2026-07-28\nversion: 1\n---\n\nbody\n" > /tmp/rgs-briefs-smoke/2026-07-28-demo-script.md
python scripts/resolve_brief_version.py --dir /tmp/rgs-briefs-smoke --slug demo --kind script
python scripts/resolve_brief_version.py --dir /tmp/rgs-briefs-smoke --slug demo --kind script --next --date 2026-07-28
rm -rf /tmp/rgs-briefs-smoke
```

Expected: first command prints
`/tmp/rgs-briefs-smoke/2026-07-28-demo-script.md	1`; second prints
`2026-07-28-demo-script-v2.md	2`.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt scripts/resolve_brief_version.py scripts/__init__.py tests/test_resolve_brief_version.py
git commit -m "feat: add rgs-briefs version resolution script"
```

---

### Task 2: `.claude/hooks/protect_briefs.py` — immutability enforcement hook

**Files:**
- Create: `.claude/hooks/protect_briefs.py`
- Test: `tests/test_protect_briefs.py`
- Create: `.claude/settings.json`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `decide(tool_name: str, resolved_path: Path, project_root: Path) -> str | None`
  — returns a deny-reason string, or `None` to allow. Pure function, no I/O
  beyond `Path.exists()`. `rgs-briefs/README.md` is explicitly exempt — it's
  directory documentation, not a versioned artifact, and Task 5 needs to be
  able to edit it normally.
- Produces: `main() -> int` — reads the hook JSON from stdin, resolves
  `tool_input.file_path` against `$CLAUDE_PROJECT_DIR`, calls `decide()`,
  prints the reason to stderr and returns `2` on deny, else returns `0`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_protect_briefs.py`:

```python
from pathlib import Path

from claude_hooks.protect_briefs import decide


def test_edit_under_rgs_briefs_is_denied(tmp_path: Path):
    root = tmp_path
    target = root / "rgs-briefs" / "2026-07-28-my-short-script.md"
    reason = decide("Edit", target, root)
    assert reason is not None
    assert "rgs-briefs" in reason


def test_write_to_new_path_under_rgs_briefs_is_allowed(tmp_path: Path):
    root = tmp_path
    (root / "rgs-briefs").mkdir()
    target = root / "rgs-briefs" / "2026-07-28-my-short-script-v2.md"
    assert decide("Write", target, root) is None


def test_write_to_existing_path_under_rgs_briefs_is_denied(tmp_path: Path):
    root = tmp_path
    briefs = root / "rgs-briefs"
    briefs.mkdir()
    target = briefs / "2026-07-28-my-short-script.md"
    target.write_text("existing", encoding="utf-8")
    reason = decide("Write", target, root)
    assert reason is not None


def test_edit_outside_rgs_briefs_is_allowed(tmp_path: Path):
    root = tmp_path
    target = root / "docs" / "notes.md"
    assert decide("Edit", target, root) is None


def test_write_outside_rgs_briefs_is_allowed_even_if_existing(tmp_path: Path):
    root = tmp_path
    (root / "docs").mkdir()
    target = root / "docs" / "notes.md"
    target.write_text("existing", encoding="utf-8")
    assert decide("Write", target, root) is None


def test_path_outside_project_root_is_allowed(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "elsewhere" / "2026-07-28-my-short-script.md"
    assert decide("Edit", outside, root) is None


def test_edit_of_rgs_briefs_readme_is_allowed(tmp_path: Path):
    root = tmp_path
    target = root / "rgs-briefs" / "README.md"
    assert decide("Edit", target, root) is None
```

Note the import: `from claude_hooks.protect_briefs import decide`. This
requires the hook module to live somewhere importable by that name — Step 2
below creates `.claude/hooks/` as a plain directory (Claude Code hooks are
invoked as scripts, not imported as a package by Claude Code itself), so the
test file needs a small shim. Use `sys.path` manipulation in the test instead
of a package import, since `.claude/hooks/` is not on the default Python
path and shouldn't need to be for the hook to function standalone. Replace
the import line with:

```python
import importlib.util
import sys
from pathlib import Path

_HOOK_PATH = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "protect_briefs.py"
_spec = importlib.util.spec_from_file_location("protect_briefs", _HOOK_PATH)
protect_briefs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(protect_briefs)
decide = protect_briefs.decide
```

(Put this at the top of `tests/test_protect_briefs.py` in place of the
plain import shown above.)

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_protect_briefs.py -v
```

Expected: FAIL — `.claude/hooks/protect_briefs.py` doesn't exist yet
(`FileNotFoundError` or `spec is None` from the loader).

- [ ] **Step 3: Write the implementation**

Create `.claude/hooks/protect_briefs.py`:

```python
#!/usr/bin/env python3
"""PreToolUse hook: enforce rgs-briefs/ immutability.

Denies (exit 2, reason on stderr):
  - any Edit whose file_path resolves under <project_root>/rgs-briefs/
  - any Write whose file_path resolves under <project_root>/rgs-briefs/ and
    already exists on disk

Allows (exit 0) everything else. See
docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md #5
for the full contract and known limitations (Bash-based mutation is not
intercepted by this hook).
"""
import json
import os
import sys
from pathlib import Path


def decide(tool_name: str, resolved_path: Path, project_root: Path) -> str | None:
    """Return a deny reason, or None to allow."""
    try:
        rel = resolved_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return None  # outside the project entirely -- not this hook's concern
    if rel.parts[:1] != ("rgs-briefs",):
        return None
    if rel.name == "README.md":
        return None  # directory documentation, not a versioned artifact
    if tool_name == "Edit":
        return (
            f"rgs-briefs/ files are immutable -- write a new version instead "
            f"of editing {rel}"
        )
    if tool_name == "Write" and resolved_path.exists():
        return (
            f"{rel} already exists -- rgs-briefs/ files are never "
            f"overwritten, write the next version instead"
        )
    return None


def main() -> int:
    payload = json.load(sys.stdin)
    tool_name = payload.get("tool_name")
    if tool_name not in ("Edit", "Write"):
        return 0
    file_path = payload.get("tool_input", {}).get("file_path")
    if not file_path:
        return 0

    project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
    resolved_path = Path(file_path)
    if not resolved_path.is_absolute():
        resolved_path = (project_root / resolved_path).resolve()

    reason = decide(tool_name, resolved_path, project_root)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_protect_briefs.py -v
```

Expected: all PASS.

- [ ] **Step 5: Wire the hook into `.claude/settings.json`**

`.claude/settings.json` doesn't exist yet (only `settings.local.json`
does). Create it:

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
      }
    ]
  }
}
```

- [ ] **Step 6: Manual end-to-end check**

This step can't be automated by pytest — it exercises Claude Code's actual
hook runner, not just the Python function. In a Claude Code session in this
repo: create `rgs-briefs/2026-07-28-hook-smoke-test.md` with the `Write`
tool (should succeed), then attempt to `Edit` it (should be denied with the
stderr reason surfaced), then attempt to `Write` to the same path again
(should be denied). Delete the smoke-test file afterward with `Bash rm`
(the hook doesn't intercept `Bash`, per its documented limitation) — this is
a manual verification step, note the outcome in the task's completion notes
rather than skipping it.

- [ ] **Step 7: Commit**

```bash
git add .claude/hooks/protect_briefs.py tests/test_protect_briefs.py .claude/settings.json
git commit -m "feat: add PreToolUse hook enforcing rgs-briefs/ immutability"
```

---

### Task 3: Retire `grounding_service.supersede_previous_brief()`

**Files:**
- Modify: `pipeline-app/pipeline_app/grounding_service.py`
- Modify: `pipeline-app/pipeline_app/routes/stages.py:141-174`
- Modify: `pipeline-app/tests/test_grounding_service.py`

**Interfaces:**
- Consumes: none from Tasks 1-2 (independent; pipeline-app has its own venv).
- Produces: no change to `snapshot_rgs_briefs`, `identify_new_brief`,
  `write_pointer`, `read_pointer` signatures — only `supersede_previous_brief`
  is removed. Task 6 (rgs-grounding SKILL.md) relies on this removal: it
  writes versioned filenames instead of relying on the app to archive the
  old one.

- [ ] **Step 1: Confirm current behavior with the existing test suite**

From `pipeline-app/`:

```bash
python -m pytest tests/test_grounding_service.py -v
```

Expected: all PASS (this is a baseline check before removing anything).

- [ ] **Step 2: Remove the two obsolete tests**

Open `pipeline-app/tests/test_grounding_service.py`. Remove
`test_supersede_archives_previously_pointed_file` and
`test_supersede_is_a_no_op_when_no_pointer` (the last two functions in the
file), and remove `supersede_previous_brief` from the import list at the top:

```python
from pipeline_app.grounding_service import (
    identify_new_brief,
    read_pointer,
    snapshot_rgs_briefs,
    write_pointer,
)
```

- [ ] **Step 3: Run tests to verify the remaining ones still pass and the removed ones are gone**

```bash
python -m pytest tests/test_grounding_service.py -v
```

Expected: PASS, and the two removed test names no longer appear in the
output.

- [ ] **Step 4: Remove `supersede_previous_brief` from `grounding_service.py`**

Delete this function (lines 42-51):

```python
def supersede_previous_brief(repo_root: Path, stage_dir: Path) -> None:
    previous = read_pointer(stage_dir)
    if not previous:
        return
    previous_path = repo_root / previous
    if not previous_path.exists():
        return
    archive_dir = previous_path.parent / ".superseded"
    archive_dir.mkdir(parents=True, exist_ok=True)
    previous_path.rename(archive_dir / previous_path.name)
```

- [ ] **Step 5: Remove its call site in `routes/stages.py`**

**Before editing, `Read` this file's actual current lines 141-174 and
diff them against the block quoted below.** The comment in the live file uses
an em dash (`—`), not a double-hyphen (`--`) — build your `old_string` from
what `Read` returns, not by retyping the plan's markdown (this file, like
every other file this plan touches, is CRLF-terminated).

Current code (verify against the live file — approximately lines 159-173):

```python
            # The grounding skill's real artifact lands in rgs-briefs/, not
            # runs/ — finalize_artifact=False above skips turn_service's
            # normal artifact/status handling so this stage-specific path can
            # take over: identify which file appeared, supersede whichever
            # brief this project pointed at before (if regenerating), and
            # point at the new one.
            after = grounding_service.snapshot_rgs_briefs(rgs_briefs_dir)
            new_brief = grounding_service.identify_new_brief(before, after)
            stage_row = db_mod.get_stage(conn, project_id, "grounding")
            if new_brief is not None:
                grounding_service.supersede_previous_brief(repo_root, grounding_dir)
                grounding_service.write_pointer(grounding_dir, f"rgs-briefs/{new_brief}")
                db_mod.update_stage_status(conn, stage_row["id"], "awaiting_review")
            else:
                db_mod.update_stage_status(conn, stage_row["id"], "no_artifact")
```

Replace with (keep the file's existing em-dash convention in the comment,
don't introduce `--`):

```python
            # The grounding skill's real artifact lands in rgs-briefs/, not
            # runs/ — finalize_artifact=False above skips turn_service's
            # normal artifact/status handling so this stage-specific path can
            # take over: identify which file appeared and point at it. The
            # grounding skill always writes a new versioned filename (see
            # rgs-grounding's SKILL.md), so there is nothing to archive —
            # the previous version is simply no longer the pointer target.
            after = grounding_service.snapshot_rgs_briefs(rgs_briefs_dir)
            new_brief = grounding_service.identify_new_brief(before, after)
            stage_row = db_mod.get_stage(conn, project_id, "grounding")
            if new_brief is not None:
                grounding_service.write_pointer(grounding_dir, f"rgs-briefs/{new_brief}")
                db_mod.update_stage_status(conn, stage_row["id"], "awaiting_review")
            else:
                db_mod.update_stage_status(conn, stage_row["id"], "no_artifact")
```

- [ ] **Step 6: Run the full pipeline-app test suite**

```bash
python -m pytest -v
```

Expected: all PASS — this confirms nothing else referenced
`supersede_previous_brief`.

- [ ] **Step 7: Commit**

```bash
git add pipeline-app/pipeline_app/grounding_service.py pipeline-app/pipeline_app/routes/stages.py pipeline-app/tests/test_grounding_service.py
git commit -m "refactor: retire rename-based brief superseding for versioned filenames"
```

---

### Task 4: `pipeline-app` stage page renders markdown as HTML

**Files:**
- Modify: `pipeline-app/pipeline_app/routes/stages.py:61-110`
- Modify: `pipeline-app/pipeline_app/templates/stage.html`
- Modify: `pipeline-app/tests/test_routes_stages.py`

**Interfaces:**
- Consumes: none from prior tasks — independent change.
- Produces: template context gains `input_html`, `grounding_input_html`,
  `output_html` (rendered) alongside the existing `input_body`,
  `grounding_input_body`, `output_body` (kept for now — nothing else in the
  codebase reads them, but removing them isn't this task's job; only the
  template's rendering changes).

- [ ] **Step 1: Write the failing test**

Add to `pipeline-app/tests/test_routes_stages.py` (append near the other
`test_stage_page_*` tests):

```python
def test_stage_page_renders_markdown_as_html_not_raw_text(client):
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    stage_dir = run_dir / "01-ideation"

    artifacts.write_artifact(
        stage_dir, 1, {"stage": "shorts-ideation", "status": "draft"},
        "## Concept Brief\n\n- angle: contrarian\n- avatar: youth coach\n",
    )

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert "<h2>Concept Brief</h2>" in page.text
    assert "<li>angle: contrarian</li>" in page.text
    assert "## Concept Brief" not in page.text
```

- [ ] **Step 2: Run test to verify it fails**

From `pipeline-app/`:

```bash
python -m pytest tests/test_routes_stages.py::test_stage_page_renders_markdown_as_html_not_raw_text -v
```

Expected: FAIL — the current page contains the literal `## Concept Brief`
text inside a `<pre>` tag, not `<h2>Concept Brief</h2>`.

- [ ] **Step 3: Render markdown in `routes/stages.py`**

Add the import at the top of the file:

```python
import markdown
```

In `stage_page` (currently lines 61-110), compute HTML alongside each body
variable. Replace:

```python
    input_body = "\n\n---\n\n".join(input_sections) if input_sections else None
```

with:

```python
    input_body = "\n\n---\n\n".join(input_sections) if input_sections else None
    input_html = markdown.markdown(input_body) if input_body else None
```

Replace:

```python
        if grounding_path is not None:
            _, grounding_input_body = artifacts.parse_frontmatter(
                grounding_path.read_text(encoding="utf-8")
            )
```

with:

```python
        if grounding_path is not None:
            _, grounding_input_body = artifacts.parse_frontmatter(
                grounding_path.read_text(encoding="utf-8")
            )
    grounding_input_html = markdown.markdown(grounding_input_body) if grounding_input_body else None
```

(Note the dedent on the new line — it belongs after the `if project[...]`
block closes, not nested inside it, since it must run even when that block
was skipped and `grounding_input_body` stayed `None`.)

Replace:

```python
    output_body = None
    latest = artifacts.resolve_latest_artifact(request.app.state.repo_root, stage_id, stage_dir)
    if latest is not None:
        _, output_body = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))
```

with:

```python
    output_body = None
    latest = artifacts.resolve_latest_artifact(request.app.state.repo_root, stage_id, stage_dir)
    if latest is not None:
        _, output_body = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))
    output_html = markdown.markdown(output_body) if output_body else None
```

Update the `TemplateResponse` context dict:

```python
    return request.app.state.templates.TemplateResponse(
        request, "stage.html",
        {
            "project": project, "stage_id": stage_id, "stage_status": stage_row["status"],
            "input_body": input_body, "input_html": input_html,
            "grounding_input_body": grounding_input_body, "grounding_input_html": grounding_input_html,
            "output_body": output_body, "output_html": output_html,
            "transcript": transcript, "nav": nav,
        },
    )
```

- [ ] **Step 4: Update `templates/stage.html`**

Replace:

```html
<section class="input-panel">
  <h2>Input</h2>
  {% if grounding_input_body %}
  <h3>Grounding companion</h3>
  <pre>{{ grounding_input_body }}</pre>
  {% endif %}
  {% if input_body %}<pre>{{ input_body }}</pre>{% elif not grounding_input_body %}<p>No upstream input.</p>{% endif %}
</section>
```

with:

```html
<section class="input-panel">
  <h2>Input</h2>
  {% if grounding_input_html %}
  <h3>Grounding companion</h3>
  <div class="rendered-markdown">{{ grounding_input_html | safe }}</div>
  {% endif %}
  {% if input_html %}<div class="rendered-markdown">{{ input_html | safe }}</div>{% elif not grounding_input_html %}<p>No upstream input.</p>{% endif %}
</section>
```

Replace:

```html
  {% if output_body %}<pre>{{ output_body }}</pre>{% else %}<p>No output yet.</p>{% endif %}
```

with:

```html
  {% if output_html %}<div class="rendered-markdown">{{ output_html | safe }}</div>{% else %}<p>No output yet.</p>{% endif %}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_routes_stages.py::test_stage_page_renders_markdown_as_html_not_raw_text -v
```

Expected: PASS.

- [ ] **Step 6: Run the full pipeline-app suite for regressions**

```bash
python -m pytest -v
```

Expected: all PASS, including the pre-existing `test_stage_page_shows_*`
tests (they assert substrings like `"concept brief text" in page.text`,
which still holds true whether the text is inside a `<pre>` or a rendered
`<div>` — no update needed there) and
`tests/test_routes_inspector.py` (unaffected — different route).

- [ ] **Step 7: Manual visual check**

Use the `run` skill or start `pipeline-app` per its README
(`uvicorn pipeline_app.main:create_default_app --factory --host 127.0.0.1
--port 8420`) and load a stage page for a stage with real markdown output
(e.g. one of the `rgs-briefs/*.md` fixtures, pointed at via a real project).
Confirm headers/lists/tables render as HTML, and that `/inspector` still
renders correctly (regression check).

- [ ] **Step 8: Commit**

```bash
git add pipeline-app/pipeline_app/routes/stages.py pipeline-app/pipeline_app/templates/stage.html pipeline-app/tests/test_routes_stages.py
git commit -m "fix: render markdown as HTML on the pipeline-app stage page"
```

---

### Task 5: `rgs-briefs/README.md` — document the versioned schema

**Files:**
- Modify: `rgs-briefs/README.md`

**Interfaces:** None (documentation only).

- [ ] **Step 1: Update the front-matter schema section**

Replace the existing front-matter schema block (currently showing only the
grounding-brief shape) with a version that documents both shapes plus the
new fields:

```markdown
## Front-matter schema

Grounding brief:

```yaml
---
date: 2026-07-25
topic: "why kids quit travel sports around age 13"
thinker: "Thorstein Veblen"
concept: "Invidious comparison"
research_codes: [F4]
archetype: A1
version: 1
status: candidate
---
```

Stage artifact (concept-brief, script, voiceover-brief, visual-prompts,
assembly, social-repurpose):

```yaml
---
date: 2026-07-28
kind: script
slug: decline-the-next-level
stage: 02-scripting
version: 1
concept_brief: rgs-briefs/2026-07-28-decline-the-next-level-concept-brief.md
grounding: rgs-briefs/2026-07-28-decline-the-next-level.md
status: complete
---
```

- `version` is a required integer on every file in this directory, starting
  at `1`. `supersedes: rgs-briefs/<path>` is added only when `version > 1`,
  pointing at the immediately-prior version's path.
- Files here are **immutable once written** — a revision always produces a
  new, higher-version file (`...-v2.md`, `...-v3.md`, …), never an edit to
  an existing one. This is enforced by a `PreToolUse` hook
  (`.claude/hooks/protect_briefs.py`), not just by convention.
- `scripts/resolve_brief_version.py` is the canonical way to find the latest
  version of a given slug/kind, or to compute the next version's filename —
  consumers should use it rather than re-implementing glob-and-sort logic.
- `status` is `candidate` until the Short is actually produced. Marking a
  Short produced is a new version write like any other change — write a
  `-v2` with `status: produced` and a `supersedes:` pointer back at the
  `candidate` version, rather than hand-editing the existing file. There is
  no exception to immutability here or anywhere else in this directory
  (`rgs-briefs/README.md` itself is the one file in this directory that
  isn't a versioned artifact and can be edited normally).
```

- [ ] **Step 2: Update the naming section**

Replace:

```markdown
`YYYY-MM-DD-<topic-slug>.md` — one file per grounding brief, dated by the day it was produced.
```

with:

```markdown
`YYYY-MM-DD-<topic-slug>.md` for a grounding brief's first version (`v1`,
implicit — no `-v1` suffix). A regenerated grounding brief for the same
topic — whether the rerun happens the same day or a later one — gets
`YYYY-MM-DD-<topic-slug>-v2.md` (then `-v3`, …), never an overwrite of the
existing file, and the date in the filename is always the day *that
version* was written (so a `-v2` produced on a later date carries that
later date, not the `v1` file's original date).
```

- [ ] **Step 3: Add a note to "Who reads this" about latest-version resolution**

Append to the "Who reads this" bullet list:

```markdown
- Any consumer scanning this directory for "the current state of topic X" or
  "the current state of Short Y's stage Z" must resolve to the **latest
  version** (via `scripts/resolve_brief_version.py`, or by parsing
  frontmatter `version:` directly) — an older version of the same
  topic/slug/kind must never be double-counted as a second, separate entry.
```

- [ ] **Step 4: Commit**

```bash
git add rgs-briefs/README.md
git commit -m "docs: document versioned rgs-briefs/ schema"
```

---

### Task 6: `rgs-grounding` SKILL.md — versioned writes

**Files:**
- Modify: `.claude/skills/rgs-grounding/SKILL.md`

**Interfaces:**
- Consumes: `scripts/resolve_brief_version.py` CLI (Task 1).

- [ ] **Step 1: Add `version`/`supersedes` to the brief template's frontmatter**

Current (inside the `## 4. Write the Grounding Brief` section):

```yaml
---
date: [YYYY-MM-DD]
topic: "[topic]"
thinker: "[Name]"
concept: "[concept]"
research_codes: [[code]]
archetype: [A1/A2/A3]
status: candidate
---
```

Replace with:

```yaml
---
date: [YYYY-MM-DD]
topic: "[topic]"
thinker: "[Name]"
concept: "[concept]"
research_codes: [[code]]
archetype: [A1/A2/A3]
version: [from `resolve_brief_version.py --next`, below]
supersedes: [previous version's path, from resolve_brief_version.py's plain (non-"--next") call, below -- omit this line entirely if version is 1]
status: candidate
---
```

- [ ] **Step 2: Rewrite the recency scan to resolve latest versions only**

Current:

```markdown
Read `references/pairing-map.md`. Find 2–3 rows whose concept plausibly fits the topic (prefer
map rows; only reach for `references/thinker-corpus-protocol.md` Path 2 if nothing fits). For
each candidate, check `references/safety-sensitive-handling.md` if its research code is
R5/R11/R12/R14, and check `rgs-briefs/` (glob the last ~20 files by date) for a recency flag —
deprioritize (don't exclude) a thinker used in the last ~5 briefs; flag an exact concept×code
repeat within the last ~15.
```

Replace with:

```markdown
Read `references/pairing-map.md`. Find 2–3 rows whose concept plausibly fits the topic (prefer
map rows; only reach for `references/thinker-corpus-protocol.md` Path 2 if nothing fits). For
each candidate, check `references/safety-sensitive-handling.md` if its research code is
R5/R11/R12/R14, and check `rgs-briefs/` (glob the last ~20 files by date, resolving each
topic-slug to its **latest version only** — an older version of a topic already re-grounded must
not be double-counted as a second use of its thinker) for a recency flag — deprioritize (don't
exclude) a thinker used in the last ~5 briefs; flag an exact concept×code repeat within the last
~15.
```

- [ ] **Step 3: Rewrite the "Save it" step to use the resolver**

Current (`### 5. Save it`):

```markdown
Write the brief to `rgs-briefs/YYYY-MM-DD-<topic-slug>.md` (see `rgs-briefs/README.md` for the
schema). Confirm the file was written before ending the turn.
```

Replace with:

```markdown
First, run `python scripts/resolve_brief_version.py --slug <topic-slug>` (no `--kind` — grounding
briefs don't have one) from the repo root. If it prints a path (not `NONE`), that's the current
version being superseded — remember its printed path verbatim for the `supersedes:` field below;
it's already `rgs-briefs/`-relative, don't prepend `rgs-briefs/` again.

Then run `python scripts/resolve_brief_version.py --slug <topic-slug> --next --date <YYYY-MM-DD>`
to get the exact filename and version number to write (first-ever brief for this topic-slug:
version 1, no `-v` suffix; a regrounding of an existing topic: the next version — this prints a
bare filename, not a path, so `rgs-briefs/<that filename>` below is correct as written). Set the
template's `version:` field to the printed version number, and — only when it's greater than 1 —
add `supersedes: <the path the first resolve_brief_version.py call above printed>`. Write the
brief to `rgs-briefs/<that filename>` (see `rgs-briefs/README.md` for the schema). Never edit an
existing file in this directory — a `PreToolUse` hook blocks it. Confirm the file was written
before ending the turn.
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/rgs-grounding/SKILL.md
git commit -m "feat(rgs-grounding): write versioned, immutable grounding briefs"
```

---

### Task 7: `rgs-pairing-review` SKILL.md — scan latest versions only

**Files:**
- Modify: `.claude/skills/rgs-pairing-review/SKILL.md`

**Interfaces:** None new — prose-only change.

- [ ] **Step 1: Update the `rgs-briefs/` grep step**

Find the section (around line 48) reading:

```markdown
Grep `rgs-briefs/*.md` for the literal heading `## Gap-fill flag` (see `rgs-grounding`'s
```

Read the full paragraph this line belongs to first (it continues past the
excerpt above), then add this sentence to the end of that paragraph:

```markdown
Resolve each topic-slug to its **latest version only** before grepping — a superseded (older)
version of a brief that already got its gap-fill flag reviewed must not be re-surfaced as if it
were new. `scripts/resolve_brief_version.py --slug <topic-slug>` (no `--kind`) returns the
current version's path for a given topic-slug.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/rgs-pairing-review/SKILL.md
git commit -m "feat(rgs-pairing-review): scan latest brief versions only"
```

---

### Task 8: `shorts-ideation` SKILL.md — File I/O contract

**Files:**
- Modify: `.claude/skills/shorts-ideation/SKILL.md`

**Interfaces:**
- Consumes: `scripts/resolve_brief_version.py` (Task 1).
- Produces: a `rgs-briefs/YYYY-MM-DD-<slug>-concept-brief.md` file for
  `shorts-scripting` (Task 9) to read.

- [ ] **Step 1: Append the File I/O contract section**

The file currently ends with:

```markdown
This skill's content carries `[C]` markers exclusively, with one exception: the "Optional
input: a companion grounding artifact" section above, marked `[I]` — an interface convention,
not a corpus claim. If a future edit needs another industry-practice or tool/policy claim, mark
it `[I]`/`[T]` explicitly rather than leaving it bare.
```

Append immediately after that paragraph:

```markdown

## File I/O contract

This skill participates in ContentStudio's file-based pipeline handoff (see
`docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md`). Two modes:

**App-driven** (a `pipeline-app` turn already told you an output path, e.g. "Write your final
concept brief to `runs/.../raw_output.md`"): follow that instruction exactly — write only to the
named path, overwrite it each turn as instructed. Do not also write to `rgs-briefs/` in this
mode; that stays `pipeline-app`'s job.

**Standalone** (no output path was given):

1. This skill has no upstream stage file to resolve — its input is a raw idea, plus optionally a
   companion grounding artifact (see "Optional input" above), which you locate by asking the user
   or by checking whether `rgs-grounding` already produced one for this topic.
2. Choose a `slug`: a short kebab-case identifier for this Short, derived from its working title
   (e.g. "Decline the Next Level" → `decline-the-next-level`). This slug is used by every
   downstream stage — state it explicitly in your final output so the human can carry it forward.
3. After assembling the concept brief, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind concept-brief --next --date <YYYY-MM-DD>`
   from the repo root. This prints `<filename>\t<version>`. Write the file at
   `rgs-briefs/<filename>` via the `Write` tool with this frontmatter (in addition to the
   concept-brief body template above):

   ```yaml
   ---
   date: <YYYY-MM-DD>
   kind: concept-brief
   slug: <slug>
   stage: 01-ideation
   version: <version from the resolver>
   supersedes: <previous version's path, exactly as the resolver printed it in step 1 — only if version > 1>
   grounding: <path to the companion grounding artifact, only if one was used>
   status: complete
   ---
   ```
4. State the exact file path you wrote in your final chat response, and the `slug` you chose, so
   `shorts-scripting` can be pointed at it directly.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this. A revision
(e.g. the user asks for a different angle on the same idea) is always a new, higher-version file
for the same slug.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/shorts-ideation/SKILL.md
git commit -m "feat(shorts-ideation): write versioned concept-brief files to rgs-briefs/"
```

---

### Task 9: `shorts-scripting` SKILL.md — File I/O contract

**Files:**
- Modify: `.claude/skills/shorts-scripting/SKILL.md`

**Interfaces:**
- Consumes: `rgs-briefs/YYYY-MM-DD-<slug>-concept-brief.md` (Task 8's output).
- Produces: `rgs-briefs/YYYY-MM-DD-<slug>-script.md` for `voiceover-brief`
  (Task 10) and `visual-prompts` (Task 11).

- [ ] **Step 1: Append the File I/O contract section**

The file is 215 lines. It currently ends with (the last two lines of
`## Reference files`):

```markdown
- `references/worked-example.md` — a complete concept-brief-to-script run with
  inline citations.
```

**Before editing, re-read the live file and confirm this is still its exact
tail** — an earlier draft of this plan anchored on the wrong bullet
(`beat-timing-model.md` instead of `worked-example.md`); don't repeat that
mistake by trusting this plan's quoted text over the file itself. Also note
every `SKILL.md` in this repo is CRLF-terminated (`\r\n`), not LF — construct
the `old_string` for your `Edit` call from what `Read` actually returns, not
by retyping the markdown shown in this plan.

Append immediately after the confirmed tail:

```markdown

## File I/O contract

This skill participates in ContentStudio's file-based pipeline handoff (see
`docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md`). Two modes:

**App-driven** (a `pipeline-app` turn already told you an output path): follow that instruction
exactly — write only to the named path, overwrite it each turn as instructed. Do not also write
to `rgs-briefs/` in this mode.

**Standalone** (no output path was given):

1. Resolve the upstream concept brief: run
   `python scripts/resolve_brief_version.py --slug <slug> --kind concept-brief` from the repo
   root (you need the `slug` the concept brief's author stated — ask for it if you don't have
   it). This prints `<path>\t<version>` where `<path>` is already `rgs-briefs/`-relative (or, if
   nothing is found yet, prints `NONE\t0` and exits 1 — that's the expected "no file yet, fall
   back to chat-pasted input" case, not an error). Read the file it reports. If it points at a
   `grounding:` field, treat that as the companion grounding artifact per "Optional input" above.
   **Staleness check:** re-run `resolve_brief_version.py --slug <slug> --kind concept-brief`
   again right before you finish — if a newer version now exists than the one you read, tell the
   user before proceeding rather than silently scripting against a stale concept.
2. After writing the script, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind script --next --date <YYYY-MM-DD>`.
   It prints `<filename>\t<version>` — a bare filename this time (no directory prefix). Write the
   file at `rgs-briefs/<filename>` via the `Write` tool with this frontmatter (in addition to the
   script body's own output contract above):

   ```yaml
   ---
   date: <YYYY-MM-DD>
   kind: script
   slug: <slug>
   stage: 02-scripting
   version: <version from the resolver>
   supersedes: <previous file's path, exactly as the resolver printed it in step 1 — only if version > 1>
   concept_brief: <the concept-brief file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative, don't prepend rgs-briefs/ again>
   grounding: <carried through from the concept brief, if present>
   total_runtime_seconds: <the script's total runtime, if the concept brief or your own timing states one>
   status: complete
   ---
   ```
3. State the exact file path you wrote in your final chat response.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/shorts-scripting/SKILL.md
git commit -m "feat(shorts-scripting): write versioned script files to rgs-briefs/"
```

---

### Task 10: `voiceover-brief` SKILL.md — File I/O contract

**Files:**
- Modify: `.claude/skills/voiceover-brief/SKILL.md`

**Interfaces:**
- Consumes: `rgs-briefs/YYYY-MM-DD-<slug>-script.md` (Task 9's output).
- Produces: `rgs-briefs/YYYY-MM-DD-<slug>-voiceover-brief.md` for
  `shorts-assembly` (Task 12).

- [ ] **Step 1: Append the File I/O contract section**

The file currently ends with (the last lines of `## Reference files`):

```markdown
- `references/production-and-loudness.md` — LUFS target, music ducking, consistency, re-rolls.
- `references/worked-example.md` — a full script excerpt run through to a finished brief.
```

Append immediately after:

```markdown

## File I/O contract

This skill participates in ContentStudio's file-based pipeline handoff (see
`docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md`). Two modes:

**App-driven** (a `pipeline-app` turn already told you an output path): follow that instruction
exactly — write only to the named path, overwrite it each turn as instructed. Do not also write
to `rgs-briefs/` in this mode.

**Standalone** (no output path was given):

1. Resolve the upstream script: run
   `python scripts/resolve_brief_version.py --slug <slug> --kind script` from the repo root. Read
   the file it reports, and follow its `concept_brief:`/`grounding:` pointer fields to resolve
   anything further upstream.
   **Staleness check:** re-run the resolver for `--kind script` again right before you finish —
   if a newer version now exists than the one you read, tell the user before proceeding.
2. After writing the brief, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind voiceover-brief --next --date <YYYY-MM-DD>`.
   Write the file at `rgs-briefs/<filename>` via the `Write` tool with this frontmatter (in
   addition to the brief body template above):

   ```yaml
   ---
   date: <YYYY-MM-DD>
   kind: voiceover-brief
   slug: <slug>
   stage: 03-voiceover
   version: <version from the resolver>
   supersedes: <previous version's path, exactly as the resolver printed it in step 1 — only if version > 1>
   script: <the script file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative, don't prepend rgs-briefs/ again>
   concept_brief: <carried through from the script, if present>
   grounding: <carried through from the script, if present>
   total_runtime_seconds: <carried through from the script, if present>
   status: complete
   ---
   ```
3. State the exact file path you wrote in your final chat response.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/voiceover-brief/SKILL.md
git commit -m "feat(voiceover-brief): write versioned voiceover-brief files to rgs-briefs/"
```

---

### Task 11: `visual-prompts` SKILL.md — File I/O contract

**Files:**
- Modify: `.claude/skills/visual-prompts/SKILL.md`

**Interfaces:**
- Consumes: `rgs-briefs/YYYY-MM-DD-<slug>-script.md` (Task 9's output).
- Produces: `rgs-briefs/YYYY-MM-DD-<slug>-visual-prompts.md` for
  `shorts-assembly` (Task 12).

- [ ] **Step 1: Append the File I/O contract section**

The file currently ends with (the last lines of `## Corpus coverage note`):

```markdown
- The i2v model-landscape table in `references/image-to-video.md` (Kling/Veo/Seedance/Sora/Omni/Runway
  tiering, pricing, and per-model limits) — this is the fastest-moving part of the whole corpus.
```

Append immediately after:

```markdown

## File I/O contract

This skill participates in ContentStudio's file-based pipeline handoff (see
`docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md`). Two modes:

**App-driven** (a `pipeline-app` turn already told you an output path): follow that instruction
exactly — write only to the named path, overwrite it each turn as instructed. Do not also write
to `rgs-briefs/` in this mode.

**Standalone** (no output path was given):

1. Resolve the upstream script: run
   `python scripts/resolve_brief_version.py --slug <slug> --kind script` from the repo root. Read
   the file it reports, and follow its `concept_brief:` pointer field if you need packaging
   direction.
   **Staleness check:** re-run the resolver for `--kind script` again right before you finish —
   if a newer version now exists than the one you read, tell the user before proceeding.
2. After emitting the prompt sheet, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind visual-prompts --next --date <YYYY-MM-DD>`.
   Write the file at `rgs-briefs/<filename>` via the `Write` tool with this frontmatter (in
   addition to the prompt sheet's own output format above):

   ```yaml
   ---
   date: <YYYY-MM-DD>
   kind: visual-prompts
   slug: <slug>
   stage: 03-visual
   version: <version from the resolver>
   supersedes: <previous version's path, exactly as the resolver printed it in step 1 — only if version > 1>
   script: <the script file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative, don't prepend rgs-briefs/ again>
   concept_brief: <carried through from the script, if present>
   visual_system: <path to a run-level visual-system document, if one was provided>
   motif_family: <the visual motif family this Short uses, if you named one while building the sheet>
   status: complete
   ---
   ```
3. State the exact file path you wrote in your final chat response.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/visual-prompts/SKILL.md
git commit -m "feat(visual-prompts): write versioned visual-prompts files to rgs-briefs/"
```

---

### Task 12: `shorts-assembly` SKILL.md — File I/O contract

**Files:**
- Modify: `.claude/skills/shorts-assembly/SKILL.md`

**Interfaces:**
- Consumes: `rgs-briefs/YYYY-MM-DD-<slug>-script.md`,
  `...-voiceover-brief.md`, `...-visual-prompts.md` (Tasks 9-11's outputs).
- Produces: `rgs-briefs/YYYY-MM-DD-<slug>-assembly.md` for `social-repurpose`
  (Task 13).

- [ ] **Step 1: Append the File I/O contract section**

The file currently ends with (the last lines of `## Gaps to flag honestly`):

```markdown
- The caption-density tension (full captions vs. front-loaded-only) is a genuine corpus split, not resolved by more research — always present it as a judgment call per `caption-overlay-system.md`, don't silently pick one side without saying why.
```

Append immediately after:

```markdown

## File I/O contract

This skill participates in ContentStudio's file-based pipeline handoff (see
`docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md`). Two modes:

**App-driven** (a `pipeline-app` turn already told you an output path): follow that instruction
exactly — write only to the named path, overwrite it each turn as instructed. Do not also write
to `rgs-briefs/` in this mode.

**Standalone** (no output path was given):

1. Resolve the three upstream inputs: run `python scripts/resolve_brief_version.py --slug <slug>
   --kind script`, `... --kind voiceover-brief`, and `... --kind visual-prompts` from the repo
   root. Read each file the resolver reports.
   **Staleness check:** re-run all three resolver calls again right before you finish — if a
   newer version now exists for any of them than the one you read, tell the user before
   proceeding.
2. After writing the plan, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind assembly --next --date <YYYY-MM-DD>`.
   Write the file at `rgs-briefs/<filename>` via the `Write` tool with this frontmatter:

   ```yaml
   ---
   date: <YYYY-MM-DD>
   kind: assembly
   slug: <slug>
   stage: 04-assembly
   version: <version from the resolver>
   supersedes: <previous version's path, exactly as the resolver printed it in step 1 — only if version > 1>
   script: <the script file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative, don't prepend rgs-briefs/ again>
   voiceover_brief: <the voiceover-brief file's path, exactly as the resolver printed it — already rgs-briefs/-relative>
   visual_prompts: <the visual-prompts file's path, exactly as the resolver printed it — already rgs-briefs/-relative>
   visual_system: <carried through from the visual-prompts file, if present>
   status: complete
   ---
   ```
3. State the exact file path you wrote in your final chat response.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/shorts-assembly/SKILL.md
git commit -m "feat(shorts-assembly): write versioned assembly files to rgs-briefs/"
```

---

### Task 13: `social-repurpose` SKILL.md — File I/O contract

**Files:**
- Modify: `.claude/skills/social-repurpose/SKILL.md`

**Interfaces:**
- Consumes: `rgs-briefs/YYYY-MM-DD-<slug>-script.md`,
  `...-assembly.md` (Tasks 9 and 12's outputs).
- Produces: `rgs-briefs/YYYY-MM-DD-<slug>-social-repurpose.md` (final stage,
  no further downstream skill).

- [ ] **Step 1: Append the File I/O contract section**

The file currently ends with (the last lines of `## Reference files`):

```markdown
- `references/worked-example.md` — a full run: a finished Short's script/packaging
  through to a complete multi-surface post-copy package, with markers intact.
```

Append immediately after:

```markdown

## File I/O contract

This skill participates in ContentStudio's file-based pipeline handoff (see
`docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md`). Two modes:

**App-driven** (a `pipeline-app` turn already told you an output path): follow that instruction
exactly — write only to the named path, overwrite it each turn as instructed. Do not also write
to `rgs-briefs/` in this mode.

**Standalone** (no output path was given):

1. Resolve the upstream script and assembly plan: run
   `python scripts/resolve_brief_version.py --slug <slug> --kind script` and
   `... --kind assembly` from the repo root. Read each file the resolver reports, and follow the
   script's `concept_brief:`/`grounding:` pointer fields if you need packaging direction or
   citation constraints to carry forward.
   **Staleness check:** re-run both resolver calls again right before you finish — if a newer
   version now exists for either than the one you read, tell the user before proceeding.
2. After assembling the post-copy package, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind social-repurpose --next --date <YYYY-MM-DD>`.
   Write the file at `rgs-briefs/<filename>` via the `Write` tool with this frontmatter:

   ```yaml
   ---
   date: <YYYY-MM-DD>
   kind: social-repurpose
   slug: <slug>
   stage: 05-repurpose
   version: <version from the resolver>
   supersedes: <previous version's path, exactly as the resolver printed it in step 1 — only if version > 1>
   script: <the script file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative, don't prepend rgs-briefs/ again>
   assembly: <the assembly file's path, exactly as the resolver printed it — already rgs-briefs/-relative>
   concept_brief: <carried through from the script, if present>
   grounding: <carried through from the script, if present>
   status: complete
   ---
   ```
3. State the exact file path you wrote in your final chat response. This is the pipeline's final
   stage — no downstream skill to point at, but this file remains the durable record of what
   copy was produced for this Short.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/social-repurpose/SKILL.md
git commit -m "feat(social-repurpose): write versioned social-repurpose files to rgs-briefs/"
```

---

## Final verification (after all 13 tasks)

- [ ] Run `python -m pytest tests/ -v` from the repo root — all pass
  (`resolve_brief_version`, `protect_briefs`, existing `lint_prompt_sheet`
  tests).
- [ ] Run `python -m pytest -v` from `pipeline-app/` — all pass (existing
  suite plus the new stage-page rendering test, minus the two removed
  supersede tests).
- [ ] Confirm all six generic skills landed their File I/O contract section:
  `grep -rl "File I/O contract" .claude/skills/` should list exactly six
  files (`shorts-ideation`, `shorts-scripting`, `voiceover-brief`,
  `visual-prompts`, `shorts-assembly`, `social-repurpose`).
- [ ] Confirm the two RGS-specific skills landed their edits (these don't
  contain the "File I/O contract" heading, so the check above won't catch a
  missed Task 6 or 7):
  `grep -l "resolve_brief_version" .claude/skills/rgs-grounding/SKILL.md .claude/skills/rgs-pairing-review/SKILL.md`
  should list both files.
