# Pipeline Turn Resilience & Specialist Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make aborted pipeline-app turns recoverable and visible instead of silently losing work, close the permission-scoping gap that lets a pipeline turn shell out or touch `docs/`/`.claude/skills/`, and make the `specialist` sidebar label truthfully describe whether that specialist is auto-invoked or a manual hand-off.

**Architecture:** No new subsystems. Every task is a targeted fix inside the existing `pipeline-app` FastAPI app: the SSE turn generator (`turn_service.py`), the subprocess argv builder (`cli_runner.py`), the transcript renderer (routes + `base.html`), the pipeline topology loader (`pipeline_config.py`), and two prompt/skill text files.

**Tech Stack:** Python 3.14, FastAPI/Starlette, pytest + pytest-asyncio, Jinja2, vanilla JS (no build step) in `base.html`.

## Global Constraints

- TDD for every Python change: write the failing test, watch it fail, then write the minimal code to pass it.
- Run `cd pipeline-app && python -m pytest -q` after every task; it must stay green. Baseline right now: **164 passed, 1 skipped**.
- Don't touch any file not named in this plan. No drive-by refactors, no unrelated cleanup.
- Commit after every task with its own commit — don't batch multiple tasks into one commit.
- Do not push to `origin` — commit locally only. Ask before pushing.
- `.claude/skills/elevenlabs-audio/` and `.claude/skills/midjourney-prompting/` must keep existing on disk with a `SKILL.md` each — Task 5 adds a startup check that enforces this for any `specialist:` declared in `pipeline.yaml`.
- Two `.md` content edits (Tasks 7's `.claude/skills/visual-prompts/SKILL.md` renumbering) have no code behavior to test — that task has no test step, by design, not an oversight.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `pipeline_app/turn_service.py` | Captures the Claude session id and any partial cost the instant they're known, so an aborted turn is resumable and its cost isn't silently dropped | 1, 2 |
| `pipeline_app/cli_runner.py` | Adds `--disallowedTools` to the subprocess argv so a pipeline turn genuinely cannot shell out, hit the web, spawn subagents, or write outside `runs/`/`rgs-briefs/` | 3 |
| `pipeline_app/routes/stages.py` | `_load_transcript` also surfaces intermediate assistant text and tool-use lines, not just the final result | 4 |
| `pipeline_app/templates/base.html` | Live SSE handler renders those intermediate lines as they arrive, plus a running/ended status line | 4 |
| `pipeline_app/pipeline_config.py` | `StageDef` gains `specialist_mode`; topology load validates a declared `specialist` actually has a skill on disk | 5 |
| `pipeline.yaml` | Declares `specialist_mode: manual` for voiceover, `specialist_mode: auto` for visual | 5 |
| `pipeline_app/templates/partials/sidebar.html` | Renders the mode-aware specialist label | 5 |
| `stage_templates/visual.md` | Kickoff prompt names the full deliverable (stills + i2v + cover), not just "the Midjourney prompt sheet" | 6 |
| `.claude/skills/visual-prompts/SKILL.md` | Workflow step numbering fixed (currently skips step 5) | 7 |
| `stage_templates/voiceover.md` | Gets the `{% if grounding_pointer %}` block every other stage template already has | 8 |

---

### Task 1: Persist the Claude session id the instant it's known

**Files:**
- Modify: `pipeline_app/turn_service.py:159-170` (the streaming loop inside `run_stage_turn`)
- Test: `pipeline-app/tests/test_turn_service.py`

**Interfaces:**
- Consumes: `db_mod.update_stage_session(conn, stage_row_id: int, session_id: str) -> None` (already exists, `pipeline_app/db.py:83-85`)
- Produces: nothing new for later tasks — this is a standalone behavior fix.

- [ ] **Step 1: Write the failing test**

Add to `pipeline-app/tests/test_turn_service.py`, right after `test_disconnected_turn_is_marked_aborted_not_left_running`:

```python
@pytest.mark.asyncio
async def test_aborted_turn_still_persists_session_id_captured_from_init_event(conn, project, monkeypatch, tmp_path):
    """A disconnect must not throw away a session id the CLI already handed
    back -- without it, the next attempt can't resume and re-pays for the
    whole kickoff prompt (see turn_service.py's is_first_turn check)."""
    events = [
        {"type": "system", "subtype": "init", "session_id": "session-1"},
        {"type": "assistant", "message": {}},
        {"type": "result", "result": "done", "is_error": False},
    ]

    async def _slow_gen(prompt, cwd, resume_session_id, **kwargs):
        for event in events:
            yield event

    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn", _slow_gen)

    stage_def = STAGES[0]
    agen = turn_service.run_stage_turn(
        conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
        project["project_id"], "abc-20260725-120000", stage_def, STAGES, "idea",
    )
    await agen.__anext__()  # consume only the init event, then simulate a dropped connection
    await agen.aclose()

    updated_stage = db.get_stage(conn, project["project_id"], "ideation")
    assert updated_stage["claude_session_id"] == "session-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_turn_service.py::test_aborted_turn_still_persists_session_id_captured_from_init_event -v`
Expected: FAIL — `updated_stage["claude_session_id"]` is `None`, not `"session-1"`.

- [ ] **Step 3: Write minimal implementation**

In `pipeline_app/turn_service.py`, inside the streaming loop (currently):

```python
        async with contextlib.aclosing(turn_stream):
            with events_path.open("a", encoding="utf-8") as f:
                async for event in turn_stream:
                    collected.append(event)
                    f.write(json.dumps(event) + "\n")
                    yield event
```

change to:

```python
        async with contextlib.aclosing(turn_stream):
            with events_path.open("a", encoding="utf-8") as f:
                async for event in turn_stream:
                    collected.append(event)
                    f.write(json.dumps(event) + "\n")
                    # Captured the moment it's known, not just on success --
                    # an aborted turn (see except below) still resumes from
                    # this session on the next attempt instead of re-paying
                    # for the whole kickoff prompt.
                    if (
                        event.get("type") == "system"
                        and event.get("subtype") == "init"
                        and event.get("session_id")
                    ):
                        db_mod.update_stage_session(conn, stage_row["id"], event["session_id"])
                    yield event
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_turn_service.py::test_aborted_turn_still_persists_session_id_captured_from_init_event -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `cd pipeline-app && python -m pytest -q`
Expected: 165 passed, 1 skipped

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/turn_service.py pipeline-app/tests/test_turn_service.py
git commit -m "fix(pipeline-app): persist claude session id as soon as the init event arrives"
```

---

### Task 2: Persist cost data when a result event was captured before an abort

**Files:**
- Modify: `pipeline_app/turn_service.py:171-192` (the `except BaseException` block)
- Test: `pipeline-app/tests/test_turn_service.py`

**Interfaces:**
- Consumes: `cli_runner.extract_turn_result(events: list[dict]) -> TurnResult` (already exists, `pipeline_app/cli_runner.py:98-110` — safe to call on a partial event list, returns `None` fields for whatever never arrived) and `db_mod.update_turn(conn, turn_id: int, status: str, finished_at: str | None = None, cost_usd: float | None = None) -> None` (already exists, `pipeline_app/db.py:97-102`).
- Produces: nothing new for later tasks.

- [ ] **Step 1: Write the failing test**

Add to `pipeline-app/tests/test_turn_service.py`, right after Task 1's test:

```python
@pytest.mark.asyncio
async def test_aborted_turn_persists_cost_when_a_result_event_was_captured(conn, project, monkeypatch, tmp_path):
    """Rare but real: the disconnect can land after the CLI already sent its
    `result` event (with the turn's cost) but before run_stage_turn finished
    its own bookkeeping. That cost must not be thrown away."""
    events = [
        {"type": "system", "subtype": "init", "session_id": "session-1"},
        {"type": "result", "result": "done", "total_cost_usd": 0.42, "is_error": False},
        {"type": "system", "subtype": "extra"},
    ]

    async def _slow_gen(prompt, cwd, resume_session_id, **kwargs):
        for event in events:
            yield event

    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn", _slow_gen)

    stage_def = STAGES[0]
    agen = turn_service.run_stage_turn(
        conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
        project["project_id"], "abc-20260725-120000", stage_def, STAGES, "idea",
    )
    await agen.__anext__()  # init
    await agen.__anext__()  # result -- cost is now inside `collected`
    await agen.aclose()      # disconnect happens after the result, before natural completion

    turns = db.list_turns(conn, project["stage_row_id"])
    assert turns[-1]["status"] == "aborted"
    assert turns[-1]["cost_usd"] == 0.42
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_turn_service.py::test_aborted_turn_persists_cost_when_a_result_event_was_captured -v`
Expected: FAIL — `turns[-1]["cost_usd"]` is `None`, not `0.42`.

- [ ] **Step 3: Write minimal implementation**

In `pipeline_app/turn_service.py`, the `except BaseException:` block currently ends with:

```python
        db_mod.update_stage_status(conn, stage_row["id"], new_status)
        db_mod.update_turn(conn, turn_id, "aborted", _utcnow())
        raise
```

change to:

```python
        db_mod.update_stage_status(conn, stage_row["id"], new_status)
        # extract_turn_result is safe to call on a partial `collected` -- it
        # simply returns None fields for whatever never arrived. Covers the
        # rare case where a `result` event (and its cost) was captured just
        # before the disconnect, instead of always discarding it.
        partial = cli_runner.extract_turn_result(collected)
        db_mod.update_turn(conn, turn_id, "aborted", _utcnow(), partial.cost_usd)
        raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_turn_service.py::test_aborted_turn_persists_cost_when_a_result_event_was_captured -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `cd pipeline-app && python -m pytest -q`
Expected: 166 passed, 1 skipped

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/turn_service.py pipeline-app/tests/test_turn_service.py
git commit -m "fix(pipeline-app): persist partial turn cost on abort instead of discarding it"
```

---

### Task 3: Deny dangerous tools and out-of-scope writes for pipeline turns

**Files:**
- Modify: `pipeline_app/cli_runner.py:28-64` (`build_claude_argv`) and `pipeline_app/cli_runner.py:176-213` (`stream_claude_turn`)
- Test: `pipeline-app/tests/test_cli_runner.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `PIPELINE_DISALLOWED_TOOLS: str` module constant in `cli_runner.py` — a later task could reference it, but none in this plan do.

Background (already verified against the installed CLI, not guessed): `claude --help` confirms `--disallowedTools, --disallowed-tools <tools...>` — "Comma or space-separated list of tool names to deny (e.g. \"Bash(git *) Edit\")" — same pattern syntax as the already-working `--allowedTools`. `--allowedTools` alone is additive/auto-approve, not a sandbox (confirmed empirically: a real turn's log showed the `Bash` tool executing even though it's absent from the current allow-list). `--disallowedTools` is the subtractive rule that actually blocks a tool.

- [ ] **Step 1: Write the failing tests**

Add to `pipeline-app/tests/test_cli_runner.py`, after `test_build_claude_argv_resume_turn_includes_session_id`:

```python
def test_build_claude_argv_appends_disallowed_tools_when_provided():
    argv = build_claude_argv(
        "prompt text",
        resume_session_id=None,
        allowed_tools="Read,Glob,Grep,Write,Edit",
        settings_path=None,
        disallowed_tools="Bash,WebFetch",
        which_fn=lambda name: "claude",
    )
    assert "--disallowedTools" in argv
    idx = argv.index("--disallowedTools")
    assert argv[idx + 1] == "Bash,WebFetch"


def test_build_claude_argv_omits_disallowed_tools_when_not_provided():
    argv = build_claude_argv(
        "prompt text",
        resume_session_id=None,
        allowed_tools="Read,Glob,Grep,Write,Edit",
        settings_path=None,
        which_fn=lambda name: "claude",
    )
    assert "--disallowedTools" not in argv
```

Add to `pipeline-app/tests/test_cli_runner.py`, right after `test_prompt_is_passed_via_stdin_not_argv` (it already defines `_FakeProcess` above itself — this new test reuses it):

```python
@pytest.mark.asyncio
async def test_stream_claude_turn_denies_bash_and_web_tools_by_default(monkeypatch, tmp_path: Path):
    """A pipeline-stage turn must never shell out, reach the live web, or
    write outside runs/**/rgs-briefs/** -- see CLAUDE.md's permission-scoping
    requirement. --allowedTools alone doesn't enforce this (it's an additive
    allow-list); --disallowedTools is the subtractive rule that's documented
    (`claude --help`) to actually block a tool regardless of permission mode.
    This test only proves the flag is constructed correctly -- it does not
    prove runtime enforcement, which the real `claude` CLI would have to
    verify (see this task's Step 5 manual smoke check)."""
    from pipeline_app import cli_runner

    monkeypatch.setattr(cli_runner, "resolve_claude_binary", lambda *a, **k: "claude")

    captured: dict = {}

    async def fake_exec(*argv, **kwargs):
        captured["argv"] = list(argv)
        return _FakeProcess([b'{"type": "result", "result": "ok"}\n'])

    monkeypatch.setattr(cli_runner.asyncio, "create_subprocess_exec", fake_exec)

    async for _ in cli_runner.stream_claude_turn("prompt", tmp_path, None):
        pass

    argv = captured["argv"]
    assert "--disallowedTools" in argv
    idx = argv.index("--disallowedTools")
    disallowed = argv[idx + 1].split(",")
    for tool in ("Bash", "WebFetch", "WebSearch", "Write(docs/**)", "Write(.claude/skills/**)"):
        assert tool in disallowed, tool
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_cli_runner.py -k "disallowed or denies" -v`
Expected: all 3 FAIL — `build_claude_argv()` raises `TypeError: unexpected keyword argument 'disallowed_tools'`, and `stream_claude_turn`'s argv never contains `--disallowedTools`.

- [ ] **Step 3: Write minimal implementation**

In `pipeline_app/cli_runner.py`, add this constant right after the `TurnResult` dataclass (before `resolve_claude_binary`):

```python
# A pipeline-stage turn must never shell out, reach the live web, or write to
# docs/, output/, or .claude/skills/ -- see CLAUDE.md's permission-scoping
# requirement. --allowedTools is additive/auto-approve only; this subtractive
# list is what actually blocks a tool. Verified against `claude --help`,
# 2026-07-27: --disallowedTools takes the same comma-separated Tool(pattern)
# syntax as --allowedTools.
#
# Task is deliberately NOT denied here: midjourney-prompting's SKILL.md (its
# Gate B, "production"-stage only) dispatches one fresh agent for adversarial
# art-direction review, and visual-prompts auto-invokes midjourney-prompting
# mid-turn. Denying Task would silently degrade that documented quality gate
# with no error surfaced to the user -- a real scope-vs-capability trade-off,
# not an oversight.
PIPELINE_DISALLOWED_TOOLS = (
    "Bash,WebFetch,WebSearch,"
    "Write(docs/**),Edit(docs/**),"
    "Write(output/**),Edit(output/**),"
    "Write(.claude/skills/**),Edit(.claude/skills/**)"
)
```

`build_claude_argv`'s real body has a multi-line comment (explaining why `--verbose` is required) between `"--include-partial-messages"` and `"--verbose"` that isn't reproduced below — don't use a whole-function block as a literal find/replace. Make these two small, precisely anchored edits instead, leaving everything else in the function untouched:

Edit 1 — the signature (this exact 7-line block is the real, complete signature, safe to match literally):

```python
def build_claude_argv(
    prompt: str,
    resume_session_id: str | None,
    allowed_tools: str,
    settings_path: str | None,
    which_fn: Callable[[str], str | None] = shutil.which,
) -> list[str]:
```

becomes:

```python
def build_claude_argv(
    prompt: str,
    resume_session_id: str | None,
    allowed_tools: str,
    settings_path: str | None,
    disallowed_tools: str | None = None,
    which_fn: Callable[[str], str | None] = shutil.which,
) -> list[str]:
```

Edit 2 — insert the new `if` block right after the existing `--allowedTools` line and before `if resume_session_id:`:

```python
        "--allowedTools", allowed_tools,
    ]
    if resume_session_id:
```

becomes:

```python
        "--allowedTools", allowed_tools,
    ]
    if disallowed_tools:
        argv += ["--disallowedTools", disallowed_tools]
    if resume_session_id:
```

Change `stream_claude_turn`'s signature and its `build_claude_argv` call from:

```python
async def stream_claude_turn(
    prompt: str,
    cwd: Path,
    resume_session_id: str | None,
    allowed_tools: str = "Read,Glob,Grep,Write,Edit",
    settings_path: str | None = None,
) -> AsyncIterator[dict]:
    argv = _platform_argv(build_claude_argv(prompt, resume_session_id, allowed_tools, settings_path))
```

to:

```python
async def stream_claude_turn(
    prompt: str,
    cwd: Path,
    resume_session_id: str | None,
    allowed_tools: str = "Read,Glob,Grep,Write,Edit,Skill",
    disallowed_tools: str = PIPELINE_DISALLOWED_TOOLS,
    settings_path: str | None = None,
) -> AsyncIterator[dict]:
    argv = _platform_argv(build_claude_argv(
        prompt, resume_session_id, allowed_tools, settings_path, disallowed_tools,
    ))
```

(`Skill` is added to the default allow-list explicitly — it already works today without being listed, but naming it documents that specialist auto-delegation, e.g. `visual-prompts` invoking `midjourney-prompting`, is an intentional, protected capability, not an accident of permissive defaults.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_cli_runner.py -k "disallowed or denies" -v`
Expected: all 3 PASS

- [ ] **Step 5: Manual smoke check (the automated tests only prove argv construction, not runtime enforcement)**

If a `claude` binary is available and it's acceptable to spend a small amount of real usage: start the dev server preview, submit one real chat message on any unlocked stage, and inspect that turn's `events/*.jsonl` file afterward — confirm no `tool_use` event names `Bash`, `WebFetch`, or `WebSearch`, and that `--disallowedTools` genuinely blocks them rather than merely being present in argv. If this isn't practical right now (cost/time), skip it and note in the commit message that runtime enforcement is unverified — the argv-construction tests still catch a regression in what gets passed to the CLI.

- [ ] **Step 6: Run the full suite**

Run: `cd pipeline-app && python -m pytest -q`
Expected: 169 passed, 1 skipped

- [ ] **Step 7: Commit**

```bash
git add pipeline-app/pipeline_app/cli_runner.py pipeline-app/tests/test_cli_runner.py
git commit -m "fix(pipeline-app): deny Bash/WebFetch/WebSearch and out-of-scope writes for pipeline turns"
```

---

### Task 4: Show live turn progress in the chat UI

**Files:**
- Modify: `pipeline_app/routes/stages.py:14-26` (`_load_transcript`)
- Modify: `pipeline_app/templates/base.html:9-61` (`attachSSEChat`)
- Test: `pipeline-app/tests/test_routes_stages.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: a transcript entry shape `{"type": "assistant", "text": str}` used identically by both the reload path (`_load_transcript`) and the live SSE path (`base.html`) — later tasks don't depend on it.

Background: `base.html`'s `attachSSEChat` currently only renders a line when it sees `event.type === "result"`, and `_load_transcript` only replays `result`-type events from disk on reload. A turn runs 1–4+ minutes (longer once a specialist skill like `midjourney-prompting` loads mid-turn) — for that whole time the page shows nothing. That silence is the most likely reason a user reloads/navigates away mid-turn, which is exactly what produces the `aborted` status this plan's Tasks 1–2 are making more recoverable. This task makes the wait itself visible instead.

- [ ] **Step 1: Write the failing test**

Add to `pipeline-app/tests/test_routes_stages.py`, right after `test_stage_page_shows_input_output_and_transcript`:

```python
def test_stage_page_transcript_shows_intermediate_assistant_and_tool_use_events(client):
    """_load_transcript must not wait for the final `result` event -- a
    reloaded page after an aborted turn should still show whatever the
    assistant said/did before the connection dropped, not an empty panel."""
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    stage_dir = run_dir / "01-ideation"
    events_dir = stage_dir / "events"
    events_dir.mkdir(parents=True)
    lines = [
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Reading the concept brief first."},
        ]}}),
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "x.md"}},
        ]}}),
    ]
    (events_dir / "1.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert "Reading the concept brief first." in page.text
    # Not "Read" -- that word already appears in the text block above ("Reading
    # the concept brief"), so a bare substring check would pass even if the
    # tool_use branch were never implemented. "↪ Read" is what only the
    # tool_use branch produces.
    assert "↪ Read" in page.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_routes_stages.py::test_stage_page_transcript_shows_intermediate_assistant_and_tool_use_events -v`
Expected: FAIL — neither string appears; `_load_transcript` currently only reads `type == "result"` events, and this fixture has none.

- [ ] **Step 3: Write minimal implementation**

In `pipeline_app/routes/stages.py`, change `_load_transcript` from:

```python
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
```

to:

```python
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
            if event.get("type") == "assistant":
                for block in event.get("message", {}).get("content", []) or []:
                    if block.get("type") == "text" and block.get("text", "").strip():
                        messages.append({"type": "assistant", "text": block["text"]})
                    elif block.get("type") == "tool_use":
                        messages.append({"type": "assistant", "text": f"↪ {block.get('name')}"})
            elif event.get("type") == "result":
                messages.append({"type": "assistant", "text": event.get("result", "")})
    return messages
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_routes_stages.py::test_stage_page_transcript_shows_intermediate_assistant_and_tool_use_events -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `cd pipeline-app && python -m pytest -q`
Expected: 170 passed, 1 skipped

- [ ] **Step 6: Commit the backend half**

```bash
git add pipeline-app/pipeline_app/routes/stages.py pipeline-app/tests/test_routes_stages.py
git commit -m "fix(pipeline-app): replay intermediate assistant/tool-use lines on transcript reload"
```

- [ ] **Step 7: Update the live SSE handler (no automated test — vanilla JS, no test harness in this repo)**

In `pipeline_app/templates/base.html`, replace the whole `attachSSEChat` function (currently lines 9-51) with:

```js
    function attachSSEChat(formEl) {
      formEl.addEventListener("submit", async (e) => {
        e.preventDefault();
        const textarea = formEl.querySelector("textarea[name=message]");
        const message = textarea.value;
        textarea.value = "";
        const transcript = document.querySelector(formEl.dataset.transcriptTarget);
        const userLine = document.createElement("p");
        userLine.innerHTML = `<strong>you:</strong> ${message}`;
        transcript.appendChild(userLine);

        // Kept visible (and updated in place) for the whole turn -- previously
        // the panel showed nothing at all until the final `result` event,
        // which for a 1-4+ minute turn reads as "did this die?" and is the
        // most likely reason someone reloads mid-turn.
        const statusLine = document.createElement("p");
        statusLine.className = "turn-status";
        statusLine.textContent = "running…";
        transcript.appendChild(statusLine);

        const response = await fetch(formEl.action, {
          method: "POST",
          headers: {"Content-Type": "application/x-www-form-urlencoded"},
          body: `message=${encodeURIComponent(message)}`,
        });
        if (!response.ok) {
          statusLine.remove();
          const line = document.createElement("p");
          line.textContent = `Error: ${await response.text()}`;
          transcript.appendChild(line);
          return;
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
          const {done, value} = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, {stream: true});
          const parts = buffer.split("\n\n");
          buffer = parts.pop();
          for (const part of parts) {
            if (!part.startsWith("data: ")) continue;
            const event = JSON.parse(part.slice(6));
            if (event.type === "assistant" && event.message && event.message.content) {
              for (const block of event.message.content) {
                if (block.type === "text" && block.text && block.text.trim()) {
                  const line = document.createElement("p");
                  line.innerHTML = `<strong>assistant:</strong> ${block.text}`;
                  transcript.insertBefore(line, statusLine);
                } else if (block.type === "tool_use") {
                  const line = document.createElement("p");
                  line.innerHTML = `<strong>assistant:</strong> ↪ ${block.name}`;
                  transcript.insertBefore(line, statusLine);
                }
              }
            } else if (event.type === "result" && event.result) {
              statusLine.remove();
              const line = document.createElement("p");
              line.innerHTML = `<strong>assistant:</strong> ${event.result}`;
              transcript.appendChild(line);
            }
          }
        }
        // Stream ended without a `result` event -- the turn was aborted
        // (client disconnect, server restart, etc.). Say so instead of
        // silently leaving "running…" up or silently removing it.
        if (statusLine.isConnected) {
          statusLine.textContent = "Turn ended without finishing — reload the page to check status.";
        }
      });
    }
```

- [ ] **Step 8: Manually verify in the browser**

Start the dev server preview and drive it exactly as a user would:

1. `preview_start({name: "pipeline-app"})` (or, if port 8420 is already in use by another session, `preview_start({url: "http://127.0.0.1:8420/"})`).
2. Navigate to an existing project's `ideation` (or any unlocked) stage page.
3. Submit a chat message via the real form (fill the textarea, submit — not a raw `fetch` call) and, over the following ~30-60s, call `read_page` or `get_page_text` a few times to confirm: a `running…` line appears immediately, then intermediate `assistant:` lines appear as the turn progresses (not just at the very end), and the final line replaces `running…` once the turn completes.
4. Confirm `read_console_messages` shows no JS errors during the whole exchange.
5. If time allows, force an abort (e.g. `javascript_tool` calling `window.stop()` mid-turn or navigating away and back) and confirm the reloaded page's transcript shows the intermediate lines captured before the abort (proves Step 1-6's backend change and this JS change agree on the same event shapes).

- [ ] **Step 9: Commit the frontend half**

```bash
git add pipeline-app/pipeline_app/templates/base.html
git commit -m "feat(pipeline-app): stream intermediate assistant/tool-use lines live during a turn"
```

---

### Task 5: Make the `specialist` field mean something

**Files:**
- Modify: `pipeline_app/pipeline_config.py` (`StageDef`, `load_topology`, `_validate_topology`, `build_stage_nav`)
- Modify: `pipeline.yaml`
- Modify: `pipeline_app/templates/partials/sidebar.html`
- Modify (fixture updates, required so existing tests still pass): `pipeline-app/tests/test_routes_projects.py`, `pipeline-app/tests/test_routes_stages.py`
- Test: `pipeline-app/tests/test_pipeline_config.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `StageDef.specialist_mode: str | None`, and a `build_stage_nav` entry shape `{"id": ..., "status": ..., "specialist": ..., "specialist_mode": ...}` — no later task in this plan depends on it.

Background: today `specialist` is purely cosmetic (only reaches the sidebar label) and nothing validates the named skill exists. The two real stages actually differ: `visual-prompts` auto-invokes `midjourney-prompting` mid-turn (confirmed working via a real run's event log: `tool_use: Skill {"skill": "midjourney-prompting"}` → success), while `voiceover-brief` deliberately does **not** auto-invoke `elevenlabs-audio` — its own `SKILL.md` frames that as a hand-off the *user* makes afterward, once they need the executable ElevenLabs config. Both currently render the identical sidebar arrow, which misrepresents the manual one as automatic.

- [ ] **Step 1: Write the failing tests**

In `pipeline-app/tests/test_pipeline_config.py`, change the `_stage_def` helper (currently):

```python
def _stage_def(id, dir_prefix, specialist=None, depends_on=None):
    return StageDef(
        id=id, skill=f"skill-{id}", dir_prefix=dir_prefix,
        depends_on=depends_on or [], specialist=specialist,
    )
```

to:

```python
def _stage_def(id, dir_prefix, specialist=None, specialist_mode=None, depends_on=None):
    return StageDef(
        id=id, skill=f"skill-{id}", dir_prefix=dir_prefix,
        depends_on=depends_on or [], specialist=specialist, specialist_mode=specialist_mode,
    )
```

Change `test_build_stage_nav_carries_status_and_specialist` (currently):

```python
def test_build_stage_nav_carries_status_and_specialist():
    stage_defs = [_stage_def("visual", "03", specialist="midjourney-prompting")]
    stage_rows = [{"stage_id": "visual", "status": "awaiting_review"}]
    nav = build_stage_nav(stage_defs, stage_rows)
    assert nav == [[{"id": "visual", "status": "awaiting_review", "specialist": "midjourney-prompting"}]]
```

to:

```python
def test_build_stage_nav_carries_status_and_specialist():
    stage_defs = [_stage_def("visual", "03", specialist="midjourney-prompting", specialist_mode="auto")]
    stage_rows = [{"stage_id": "visual", "status": "awaiting_review"}]
    nav = build_stage_nav(stage_defs, stage_rows)
    assert nav == [[{
        "id": "visual", "status": "awaiting_review",
        "specialist": "midjourney-prompting", "specialist_mode": "auto",
    }]]
```

Add these new tests after `test_ideation_has_no_specialist`:

```python
def test_voiceover_stage_specialist_mode_is_manual():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    voiceover = next(s for s in stages if s.id == "voiceover")
    assert voiceover.specialist_mode == "manual"


def test_visual_stage_specialist_mode_is_auto():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    visual = next(s for s in stages if s.id == "visual")
    assert visual.specialist_mode == "auto"
```

Add these new tests after `test_load_topology_accepts_valid_graph` (the last test in the file):

```python
def test_load_topology_accepts_specialist_that_has_a_skill_dir(tmp_path: Path):
    (tmp_path / ".claude" / "skills" / "some-specialist").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "some-specialist" / "SKILL.md").write_text(
        "---\nname: some-specialist\n---\n", encoding="utf-8",
    )
    path = _write_topology(
        tmp_path,
        "stages:\n"
        "  - id: visual\n    skill: visual-prompts\n    dir_prefix: \"03\"\n    depends_on: []\n"
        "    specialist: some-specialist\n    specialist_mode: auto\n",
    )
    stages = load_topology(path)
    assert stages[0].specialist == "some-specialist"
    assert stages[0].specialist_mode == "auto"


def test_load_topology_rejects_specialist_with_no_skill_dir(tmp_path: Path):
    path = _write_topology(
        tmp_path,
        "stages:\n"
        "  - id: visual\n    skill: visual-prompts\n    dir_prefix: \"03\"\n    depends_on: []\n"
        "    specialist: ghost-specialist\n",
    )
    with pytest.raises(ValueError, match="ghost-specialist"):
        load_topology(path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_pipeline_config.py -v`
Expected: the four new tests FAIL. Also — because Step 1 changed the shared `_stage_def` helper to pass `specialist_mode=` into `StageDef(...)`, which doesn't accept that keyword yet — every other `_stage_def`-based test now fails too with the same `TypeError`: `test_build_stage_nav_groups_stages_sharing_dir_prefix`, `test_build_stage_nav_omits_stages_with_no_matching_row`, and `test_build_stage_nav_preserves_stage_defs_order_not_dir_prefix_sort`. That's expected and temporary — Step 3 fixes all of it at once by adding the field to `StageDef`. Only tests in *other* files are unaffected.

- [ ] **Step 3: Write minimal implementation**

In `pipeline_app/pipeline_config.py`, change `StageDef` (currently ends at `specialist: str | None = None`) to add one field:

```python
@dataclass
class StageDef:
    id: str
    skill: str
    dir_prefix: str
    depends_on: list[str] = field(default_factory=list)
    brand_scope: str | None = None
    specialist: str | None = None
    specialist_mode: str | None = None
```

Change `load_topology` from:

```python
def load_topology(path: Path) -> list[StageDef]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    stages = [
        StageDef(
            id=s["id"],
            skill=s["skill"],
            dir_prefix=s["dir_prefix"],
            depends_on=list(s.get("depends_on", [])),
            brand_scope=s.get("brand_scope"),
            specialist=s.get("specialist"),
        )
        for s in data["stages"]
    ]
    _validate_topology(stages)
    return stages
```

to:

```python
def load_topology(path: Path) -> list[StageDef]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    stages = [
        StageDef(
            id=s["id"],
            skill=s["skill"],
            dir_prefix=s["dir_prefix"],
            depends_on=list(s.get("depends_on", [])),
            brand_scope=s.get("brand_scope"),
            specialist=s.get("specialist"),
            specialist_mode=s.get("specialist_mode"),
        )
        for s in data["stages"]
    ]
    _validate_topology(stages, path.parent)
    return stages
```

Change `_validate_topology`'s signature and add the new check at the end (keep the existing duplicate-id and cycle checks exactly as they are — only the signature and the new loop are new):

```python
def _validate_topology(stages: list[StageDef], repo_root: Path) -> None:
    seen: set[str] = set()
    for stage in stages:
        if stage.id in seen:
            raise ValueError(f"pipeline.yaml: duplicate stage id '{stage.id}'")
        seen.add(stage.id)
    for stage in stages:
        for dep in stage.depends_on:
            if dep not in seen:
                raise ValueError(
                    f"pipeline.yaml: stage '{stage.id}' depends_on unknown stage '{dep}'"
                )
    _check_no_cycles(stages)
    for stage in stages:
        if stage.specialist is not None:
            skill_md = repo_root / ".claude" / "skills" / stage.specialist / "SKILL.md"
            if not skill_md.exists():
                raise ValueError(
                    f"pipeline.yaml: stage '{stage.id}' specialist '{stage.specialist}' has no "
                    f"skill at {skill_md}"
                )
```

Change `build_stage_nav`'s entry dict (currently `entry = {"id": stage_def.id, "status": row["status"], "specialist": stage_def.specialist}`) to:

```python
        entry = {
            "id": stage_def.id, "status": row["status"],
            "specialist": stage_def.specialist, "specialist_mode": stage_def.specialist_mode,
        }
```

In `pipeline.yaml` (repo root), change the `voiceover` and `visual` stage entries from:

```yaml
  - id: voiceover
    skill: voiceover-brief
    specialist: elevenlabs-audio
    dir_prefix: "03"
    depends_on: [scripting]
  - id: visual
    skill: visual-prompts
    specialist: midjourney-prompting
    dir_prefix: "03"
    depends_on: [scripting]
```

to:

```yaml
  - id: voiceover
    skill: voiceover-brief
    specialist: elevenlabs-audio
    specialist_mode: manual
    dir_prefix: "03"
    depends_on: [scripting]
  - id: visual
    skill: visual-prompts
    specialist: midjourney-prompting
    specialist_mode: auto
    dir_prefix: "03"
    depends_on: [scripting]
```

In `pipeline_app/templates/partials/sidebar.html`, change:

```html
        {% if stage.specialist %}
        <div class="specialist">&#8618; {{ stage.specialist }}</div>
        {% endif %}
```

to:

```html
        {% if stage.specialist %}
        <div class="specialist">
          {% if stage.specialist_mode == "manual" %}
          &#8618; {{ stage.specialist }} (manual hand-off)
          {% else %}
          &#8618; {{ stage.specialist }} (auto-delegated)
          {% endif %}
        </div>
        {% endif %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_pipeline_config.py -v`
Expected: PASS. Also run `cd pipeline-app && python -m pytest -q` — expect two failures at this point: `test_project_home_groups_parallel_stages_and_shows_specialist` and `test_stage_page_shows_grouped_parallel_pair_in_nav`, both because their own hand-written `pipeline.yaml` fixtures declare a `specialist:` with no matching `.claude/skills/<name>/SKILL.md` in their `tmp_path`, and now hit the new validation `ValueError` at `create_app()`. Fix them in Step 5.

- [ ] **Step 5: Fix the two existing test fixtures**

In `pipeline-app/tests/test_routes_projects.py`, in `test_project_home_groups_parallel_stages_and_shows_specialist`, right before the existing `(tmp_path / "pipeline.yaml").write_text(...)` call, insert:

```python
    (tmp_path / ".claude" / "skills" / "elevenlabs-audio").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "elevenlabs-audio" / "SKILL.md").write_text(
        "---\nname: elevenlabs-audio\n---\n", encoding="utf-8",
    )
    (tmp_path / ".claude" / "skills" / "midjourney-prompting").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "midjourney-prompting" / "SKILL.md").write_text(
        "---\nname: midjourney-prompting\n---\n", encoding="utf-8",
    )
```

In `pipeline-app/tests/test_routes_stages.py`, in `test_stage_page_shows_grouped_parallel_pair_in_nav`, replace the whole test with:

```python
def test_stage_page_shows_grouped_parallel_pair_in_nav(tmp_path: Path, monkeypatch):
    # The shared `client` fixture's pipeline.yaml has no parallel pair, so it
    # can never exercise grouping through the stage route — this test uses
    # its own pipeline.yaml specifically to cover that gap.
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".claude" / "skills" / "elevenlabs-audio").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "elevenlabs-audio" / "SKILL.md").write_text(
        "---\nname: elevenlabs-audio\n---\n", encoding="utf-8",
    )
    (tmp_path / ".claude" / "skills" / "midjourney-prompting").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "midjourney-prompting" / "SKILL.md").write_text(
        "---\nname: midjourney-prompting\n---\n", encoding="utf-8",
    )
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n    depends_on: []\n"
        "  - id: voiceover\n    skill: voiceover-brief\n    specialist: elevenlabs-audio\n"
        "    specialist_mode: manual\n    dir_prefix: \"03\"\n    depends_on: [scripting]\n"
        "  - id: visual\n    skill: visual-prompts\n    specialist: midjourney-prompting\n"
        "    specialist_mode: auto\n    dir_prefix: \"03\"\n    depends_on: [scripting]\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app, follow_redirects=False)
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    page = test_client.get(f"/projects/{project_id}/stages/voiceover")
    assert page.status_code == 200
    assert "elevenlabs-audio" in page.text
    assert "midjourney-prompting" in page.text
    assert "manual hand-off" in page.text
    assert "auto-delegated" in page.text
    # scripting is its own step; voiceover+visual share dir_prefix "03" and
    # must render inside ONE grouped step, not two.
    assert page.text.count('class="pipeline-step"') == 2
    # voiceover is the current stage on this page
    assert 'class="pipeline-stage current"' in page.text
```

- [ ] **Step 6: Run the full suite**

Run: `cd pipeline-app && python -m pytest -q`
Expected: 174 passed, 1 skipped

- [ ] **Step 7: Commit**

```bash
git add pipeline-app/pipeline_app/pipeline_config.py pipeline.yaml pipeline-app/pipeline_app/templates/partials/sidebar.html pipeline-app/tests/test_pipeline_config.py pipeline-app/tests/test_routes_projects.py pipeline-app/tests/test_routes_stages.py
git commit -m "feat(pipeline-app): validate specialist skills exist and label auto vs manual delegation"
```

---

### Task 6: Fix the visual-prompts kickoff prompt's deliverable description

**Files:**
- Modify: `stage_templates/visual.md`
- Test: `pipeline-app/tests/test_prompt_builder.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new for later tasks.

Background: the kickoff prompt currently asks for "the Midjourney prompt sheet," but the skill's own `SKILL.md` also requires i2v prompts (Kling/Seedance/Veo) for beats needing real motion, and an explicit cover/thumbnail decision — neither is a Midjourney still. Naming the deliverable after just the still-image tool risks the agent treating i2v/cover as optional.

- [ ] **Step 1: Write the failing test**

Add to `pipeline-app/tests/test_prompt_builder.py`, right after `test_visual_template_includes_grounding_block_when_present`:

```python
def test_visual_template_deliverable_names_i2v_and_cover_not_just_stills():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "visual", {
        "skill": "visual-prompts",
        "user_message": "",
        "grounding_pointer": None,
        "input_file": "runs/x/02-scripting/artifact.v1.md",
        "raw_output_path": "runs/x/03-visual/raw_output.md",
    })
    assert "i2v" in prompt.lower()
    assert "cover" in prompt.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_prompt_builder.py::test_visual_template_deliverable_names_i2v_and_cover_not_just_stills -v`
Expected: FAIL — neither "i2v" nor "cover" appears in the current prompt text.

- [ ] **Step 3: Write minimal implementation**

Change `stage_templates/visual.md` from:

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

to:

```
/{{ skill }}

Read the script at `{{ input_file }}` and produce the visual prompt sheet: per-beat Midjourney
stills, any i2v (image-to-video) prompts for beats that need real motion, and the cover/thumbnail
decision.
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}` — carry forward any
citations or constraints it names.
{% endif %}
{{ user_message }}

Write your final prompt sheet to `{{ raw_output_path }}` (overwrite it completely each time you
produce a new draft).
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_prompt_builder.py::test_visual_template_deliverable_names_i2v_and_cover_not_just_stills -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `cd pipeline-app && python -m pytest -q`
Expected: 175 passed, 1 skipped

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/stage_templates/visual.md pipeline-app/tests/test_prompt_builder.py
git commit -m "fix(pipeline-app): name i2v and cover in the visual-stage kickoff prompt, not just stills"
```

---

### Task 7: Fix visual-prompts SKILL.md's workflow step numbering

**Files:**
- Modify: `.claude/skills/visual-prompts/SKILL.md`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing.

Background: the `## Workflow` section's headings currently run `### 1.`, `### 2.`, `### 3.`, `### 4.`, `### 6.`, `### 7.`, `### 8.` — step 5 doesn't exist. This is prose read by the agent executing the turn, not code; there's no test to write. An agent following a numbered procedure with a gap in it may infer a missing instruction that was never actually dropped.

- [ ] **Step 1: Renumber the three misnumbered headings**

In `.claude/skills/visual-prompts/SKILL.md`, change three workflow section headings (steps 1-4 are already numbered correctly and don't change):

- `### 6. Decide, per beat, whether a still suffices...` → `### 5. Decide, per beat, whether a still suffices...`
- `### 7. Decide the cover/thumbnail image` → `### 6. Decide the cover/thumbnail image`
- `### 8. Emit the prompt sheet` → `### 7. Emit the prompt sheet`

- [ ] **Step 2: Fix the one known cross-reference**

Line 191, inside the step-4 delegation example, currently reads:

```
  [Dedicated prompt from midjourney-prompting — see step 7]
```

Change `see step 7` to `see step 6` — it points at the cover/thumbnail decision, which is what Step 1 above just renumbered from 7 to 6.

- [ ] **Step 3: Proofread for any other stale reference**

Read the file top to bottom once after editing to confirm nothing else was missed, then grep to be sure: `grep -in "step 6\|step 7\|step 8" .claude/skills/visual-prompts/SKILL.md` — every remaining hit should be a current, correct heading or the line-191 reference you just fixed, not a leftover pointing at the old numbering.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/visual-prompts/SKILL.md
git commit -m "fix(visual-prompts): renumber workflow steps to close the gap at step 5"
```

---

### Task 8: Give voiceover's kickoff prompt the grounding-pointer block it's missing

**Files:**
- Modify: `stage_templates/voiceover.md`
- Test: `pipeline-app/tests/test_prompt_builder.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new for later tasks.

Background: `routes/stages.py`'s `stage_chat` already computes `grounding_pointer` for every non-grounding stage on a `raisinggoodsports` project (including `voiceover`), and `stage_page`'s Input panel already renders the grounding companion for `voiceover` too. But `stage_templates/voiceover.md` is the one stage template (besides `assembly.md`/`repurpose.md`, which drop it defensibly since it flows through upstream artifacts by then) that has no `{% if grounding_pointer %}` block — so the value the route computes and the panel promises never actually reaches the prompt.

- [ ] **Step 1: Write the failing tests**

Add to `pipeline-app/tests/test_prompt_builder.py`, right after `test_scripting_template_references_input_file`:

```python
def test_voiceover_template_omits_grounding_block_when_none():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "voiceover", {
        "skill": "voiceover-brief",
        "user_message": "",
        "grounding_pointer": None,
        "input_file": "runs/x/02-scripting/artifact.v1.md",
        "raw_output_path": "runs/x/03-voiceover/raw_output.md",
    })
    assert "companion grounding artifact" not in prompt


def test_voiceover_template_includes_grounding_block_when_present():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "voiceover", {
        "skill": "voiceover-brief",
        "user_message": "",
        "grounding_pointer": "rgs-briefs/2026-07-25-idea.md",
        "input_file": "runs/x/02-scripting/artifact.v1.md",
        "raw_output_path": "runs/x/03-voiceover/raw_output.md",
    })
    assert "rgs-briefs/2026-07-25-idea.md" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_prompt_builder.py -k voiceover_template -v`
Expected: `test_voiceover_template_omits_grounding_block_when_none` PASSes trivially (there's no block at all yet, so the string is absent either way — that's fine, it's the guard test); `test_voiceover_template_includes_grounding_block_when_present` FAILs — the pointer text never appears.

- [ ] **Step 3: Write minimal implementation**

Change `stage_templates/voiceover.md` from:

```
/{{ skill }}

Read the script at `{{ input_file }}` and produce the ElevenLabs voiceover production brief.

{{ user_message }}

Write your final brief to `{{ raw_output_path }}` (overwrite it completely each time you produce a
new draft).
```

to:

```
/{{ skill }}

Read the script at `{{ input_file }}` and produce the ElevenLabs voiceover production brief.
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}` — carry forward any
citations or constraints it names.
{% endif %}
{{ user_message }}

Write your final brief to `{{ raw_output_path }}` (overwrite it completely each time you produce a
new draft).
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_prompt_builder.py -k voiceover_template -v`
Expected: both PASS

- [ ] **Step 5: Run the full suite**

Run: `cd pipeline-app && python -m pytest -q`
Expected: 177 passed, 1 skipped

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/stage_templates/voiceover.md pipeline-app/tests/test_prompt_builder.py
git commit -m "fix(pipeline-app): pass the grounding pointer into the voiceover kickoff prompt"
```

---

## Final check

After Task 8, run the full suite once more (`cd pipeline-app && python -m pytest -q`) and confirm **177 passed, 1 skipped** — 13 more than the 164/1 baseline (1 in Task 1, 1 in Task 2, 3 in Task 3, 1 in Task 4, 4 in Task 5, 1 in Task 6, 0 in Task 7, 2 in Task 8). If the count doesn't land exactly on 177, trust the actual `pytest -q` output over this arithmetic — the important thing is it only went up and nothing regressed. Do not push to `origin` — stop after the last commit and report status.
