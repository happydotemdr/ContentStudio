# Task 1 Report: Package scaffold and `naming.py`

## Summary

Implemented the package scaffold and complete `naming.py` module for the automated asset stitcher. All 13 tests pass. The module provides:
- `slugify(text: str) -> str` function for filename normalization
- Constants: `SUPERSAMPLE_FINAL=4`, `SUPERSAMPLE_DRAFT=1`, `MAX_PATH_LEN=255`
- `Workspace` frozen dataclass with 23 methods/properties for workspace path management

## What I Implemented

### Files Created
1. **`stitcher/requirements.txt`** — Dependency pins (floors, not exact):
   - `pydantic>=2.9`
   - `Pillow>=11.0`
   - `pytest>=8.3`
   - Updated comment per ruling R2 to clarify that versions are floors and golden images are generated locally per-machine, not committed.

2. **`stitcher/stitcher/__init__.py`** — Empty package file

3. **`stitcher/tests/__init__.py`** — Empty test package file

4. **`stitcher/pytest.ini`** — Pytest configuration with pythonpath=. and testpaths=tests, required for relative imports in test_spec fixtures that haven't been written yet

5. **`stitcher/tests/test_naming.py`** — 13 test cases (copied exactly from brief)

6. **`stitcher/stitcher/naming.py`** — Complete implementation with:
   - `slugify()` function using regex for lowercasing, hyphenation, and truncation to 40 chars
   - `Workspace` dataclass (frozen) with all required properties and methods:
     - Directory properties: `base`, `assets_dir`, `work_dir`, `shots_dir`, `overlays_dir`, `audio_dir`, `out_dir`, `logs_dir`
     - Artifact methods: `asset()`, `shot_clip()`, `overlay_png()`, `overlay_bbox()`, `audio_step()`, `log_path()`
     - Deliverable methods: `out_master()`, `out_cover()`, `out_srt()`, `out_ass()`, `out_qa_json()`, `out_qa_md()`, `out_contact_sheet()`, `draft_master()`
     - Utility methods: `ensure_dirs()`, `next_version()`
     - Constants and private regex patterns

### Files Modified
- **`.gitignore`** — Added:
  - `renders/` (asset stitcher workspace outputs, per brief)
  - `.superpowers/` (SDD scratch directory, controller-directed in Task 1 dispatch)

## TDD Evidence

### RED: Failing Test Run

Command:
```bash
cd /c/Projects/ContentStudio/.claude/worktrees/automated-asset-stitcher-c5961a/stitcher && python -m pytest tests/test_naming.py -v
```

Output (excerpt):
```
collecting ... collected 0 items / 1 error

=================================== ERRORS ====================================
____________________ ERROR collecting tests/test_naming.py ____________________
ImportError while importing test module '...\tests\test_naming.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
...
tests\test_naming.py:5: in <module>
    from stitcher.naming import Workspace, slugify
E   ModuleNotFoundError: No module named 'stitcher.naming'
=========================== short test summary info ===========================
ERROR tests/test_naming.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

**Expected failure reason:** Module `stitcher.naming` does not exist yet. ✓

### GREEN: Passing Test Run

Command:
```bash
cd /c/Projects/ContentStudio/.claude/worktrees/automated-asset-stitcher-c5961a/stitcher && python -m pytest tests/test_naming.py -v
```

Output (excerpt):
```
============================= test session starts =============================
platform win32 -- Python 3.14.4, pytest-8.3.5, pluggy-1.6.0 -- C:\Python314\python.exe
...
tests/test_naming.py::test_slugify_lowercases_and_hyphenates PASSED      [  7%]
tests/test_naming.py::test_slugify_strips_punctuation_and_collapses_separators PASSED [ 15%]
tests/test_naming.py::test_slugify_truncates_long_text_without_trailing_hyphen PASSED [ 23%]
tests/test_naming.py::test_work_dir_is_partitioned_by_mode PASSED        [ 30%]
tests/test_naming.py::test_shot_clip_is_ordinal_id_label_and_sorts_in_playback_order PASSED [ 38%]
tests/test_naming.py::test_overlay_png_and_bbox_share_a_stem PASSED      [ 46%]
tests/test_naming.py::test_audio_step_uses_chain_order_ordinals PASSED   [ 53%]
tests/test_naming.py::test_next_version_is_one_on_an_empty_workspace PASSED [ 61%]
tests/test_naming.py::test_next_version_increments_past_the_highest_existing PASSED [ 69%]
tests/test_naming.py::test_next_version_ignores_draft_outputs PASSED     [ 76%]
tests/test_naming.py::test_out_master_is_version_stamped PASSED          [ 84%]
tests/test_naming.py::test_draft_master_is_not_versioned PASSED          [ 92%]
tests/test_naming.py::test_master_path_lives_in_work_not_out PASSED      [100%]

============================== 13 passed, 482 warnings in 0.07s =======================
```

**Result:** All 13 tests pass. ✓

## Files Changed

- **Created:**
  - `stitcher/requirements.txt`
  - `stitcher/stitcher/__init__.py`
  - `stitcher/tests/__init__.py`
  - `stitcher/pytest.ini`
  - `stitcher/tests/test_naming.py`
  - `stitcher/stitcher/naming.py`

- **Modified:**
  - `.gitignore` (+2 lines)

## Self-Review Findings

### Completeness
- All 13 interfaces from the brief are implemented and functional
- All test assertions pass without modification
- No interface signatures were altered

### Quality
- Module docstring clearly explains single-source-of-truth pattern
- Constants are documented with rationales (SUPERSAMPLE factors, MAX_PATH_LEN context)
- Regex patterns are private (_SLUG_STRIP, _SLUG_MAX) and named clearly
- Workspace properties use @property decorator consistently for computed paths
- Path formatting uses consistent naming scheme (ordinal:03d padding, slug interpolation)

### Testing
- Tests cover all major code paths: slugify edge cases, workspace partitioning, filename generation, versioning logic
- Fixture-based workspace instantiation enables parametric testing
- Test names clearly express the assertion being verified

### Adherence to Specification
- Applied ruling R2 correctly: changed `==` pins to `>=` floors and updated comment
- Applied ruling R4 correctly: added `.superpowers/` to .gitignore
- No files touched outside `stitcher/` except `.gitignore`
- Commit message matches brief exactly, with required trailer

### Pytest Output Cleanliness

Initial run emitted 482 DeprecationWarnings from pytest-asyncio plugin (globally installed, auto-hooking into collection). This was flagged during review.

## Deviations from Brief

**None.** The brief's code was correct and required no modification. All tests pass without loosening any assertions.

## Concerns

**Pytest warning noise (initial run)** — Flagged by reviewer. Fixed in subsequent commit.

## Commit (Initial)

```
e5b1ade feat(stitcher): package scaffold and workspace naming
```

The commit includes all 6 created files and the .gitignore modification, with the specified trailer.

---

## Fix Report: Suppress pytest-asyncio warnings

### Change Made
Updated `stitcher/pytest.ini` to suppress pytest-asyncio plugin warnings:
- Added `addopts = -p no:asyncio` to pytest configuration
- Rationale: pytest-asyncio is globally installed and auto-hooks into test collection on Python 3.14, emitting 482 DeprecationWarnings about deprecated `asyncio.iscoroutinefunction()`. This project uses no asyncio, so the warnings are pure environmental noise. All 15 tasks inherit pytest.ini, so suppressing this early prevents all downstream tests from reporting noisy output.

### Covering Test Run

Command:
```bash
cd /c/Projects/ContentStudio/.claude/worktrees/automated-asset-stitcher-c5961a/stitcher && python -m pytest tests/test_naming.py -v
```

Output:
```
============================= test session starts =============================
platform win32 -- Python 3.14.4, pytest-8.3.5, pluggy-1.6.0 -- C:\Python314\python.exe
cachedir: .pytest_cache
rootdir: C:\Projects\ContentStudio\.claude\worktrees\automated-asset-stitcher-c5961a\stitcher
configfile: pytest.ini
plugins: anyio-4.13.0, xdist-3.8.0
collecting ... collected 13 items

tests/test_naming.py::test_slugify_lowercases_and_hyphenates PASSED      [  7%]
tests/test_naming.py::test_slugify_strips_punctuation_and_collapses_separators PASSED [ 15%]
tests/test_naming.py::test_slugify_truncates_long_text_without_trailing_hyphen PASSED [ 23%]
tests/test_naming.py::test_work_dir_is_partitioned_by_mode PASSED        [ 30%]
tests/test_naming.py::test_shot_clip_is_ordinal_id_label_and_sorts_in_playback_order PASSED [ 38%]
tests/test_naming.py::test_overlay_png_and_bbox_share_a_stem PASSED      [ 46%]
tests/test_naming.py::test_audio_step_uses_chain_order_ordinals PASSED   [ 53%]
tests/test_naming.py::test_next_version_is_one_on_an_empty_workspace PASSED [ 61%]
tests/test_naming.py::test_next_version_increments_past_the_highest_existing PASSED [ 69%]
tests/test_naming.py::test_next_version_ignores_draft_outputs PASSED     [ 76%]
tests/test_naming.py::test_out_master_is_version_stamped PASSED          [ 84%]
tests/test_naming.py::test_draft_master_is_not_versioned PASSED          [ 92%]
tests/test_naming.py::test_master_path_lives_in_work_not_out PASSED      [100%]

============================= 13 passed in 0.05s ==============================
```

**Result:** 13 passed with zero warnings. ✓ The pytest-asyncio plugin is successfully suppressed without affecting test behavior.
