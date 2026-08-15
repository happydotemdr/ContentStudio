import datetime
import html as html_escape
import json
from html.parser import HTMLParser

import markdown
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from pipeline_app import (
    approval_service,
    artifacts,
    db as db_mod,
    gates,
    grounding_service,
    obs,
    turn_service,
)
from pipeline_app.approval_service import classify_gates
from pipeline_app.pipeline_config import build_stage_nav, stage_dir_name
from pipeline_app.state_machine import is_locked_or_running

router = APIRouter()

# Allowlist, not a denylist (per the amendment to T21's brief): a denylist of
# "dangerous" tags misses whatever nobody thought of, but markdown.markdown()
# only ever emits from a small, known vocabulary, so enumerating that
# vocabulary is exhaustive by construction, not by vigilance.
_ALLOWED_TAGS = frozenset({
    "p", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li",
    "strong", "em", "b", "i", "a", "code", "pre", "blockquote",
    "table", "thead", "tbody", "tr", "th", "td",
    "img",
})
# Self-closing/void elements in the allowlist -- HTMLParser reports these via
# handle_startendtag or a start tag with no matching end tag, so they must
# never be pushed onto the "wait for matching close" stack below.
_VOID_TAGS = frozenset({"br", "hr", "img"})
# Attributes whose value is a URL markdown.markdown() can emit unfiltered
# (image src, link href) -- javascript: is the OWASP #1 bypass for a
# tag-allowlist-only sanitizer, and `[click](javascript:alert(1))` is
# ordinary Markdown syntax, not raw HTML a model would need to reach for.
_URL_ATTRS = frozenset({"href", "src"})
_URL_SAFE_SCHEMES = frozenset({"http", "https", "mailto"})


def _is_safe_url(value: str) -> bool:
    """A relative/scheme-relative URL, or one using an allowlisted scheme.

    Strips leading whitespace and drops embedded control characters first --
    `java\\tscript:` and a leading newline before `javascript:` are classic
    scheme-check bypasses that survive a naive `.startswith()` check (browsers
    historically ignored tab/newline/CR inside a scheme name)."""
    stripped = "".join(ch for ch in value if ch not in "\t\n\r").strip()
    colon = stripped.find(":")
    slash = stripped.find("/")
    if colon == -1 or (slash != -1 and slash < colon):
        return True  # no scheme before the first '/' -> relative/scheme-relative
    scheme = stripped[:colon].lower()
    return scheme in _URL_SAFE_SCHEMES


def _escape_attr_value(value: str) -> str:
    """Escape a value being re-serialized into a `"..."`-quoted attribute.

    HTMLParser hands `handle_starttag` already-entity-decoded values (e.g.
    `&quot;` -> `"`), so a value that looks inert at parse time can break out
    of the quotes once this class writes it back out verbatim -- re-escaping
    on OUR OWN output, not trusting how the input arrived, is what closes
    that gap."""
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class _HTMLSanitizer(HTMLParser):
    """Stdlib-only allowlist sanitizer for `markdown.markdown()` output.

    Artifact bodies are model-generated and hand-editable text that becomes
    HTML rendered with Jinja's `| safe` -- untrusted by construction. This
    walks the parse tree rather than regexing tags, so a `<script>` split
    across attributes or an `onerror=` spelled with mixed case still gets
    caught (regex-based stripping is exactly the kind of denylist this
    amendment rejects)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._out = []
        self._skip_depth = 0  # >0 while inside a <script>/<style> (or nested one)

    def _build_attr_str(self, attrs) -> str:
        parts = []
        for name, value in attrs:
            lname = name.lower()
            if lname.startswith("on") or value is None:
                continue
            if lname in _URL_ATTRS and not _is_safe_url(value):
                continue  # drop just this attribute, keep the rest of the tag
            parts.append(f' {name}="{_escape_attr_value(value)}"')
        return "".join(parts)

    def handle_starttag(self, tag, attrs):
        # `style` gets the same CDATA treatment as `script` (C2): HTMLParser's
        # CDATA_CONTENT_ELEMENTS is ("script", "style") -- for either tag,
        # handle_data receives the tag's raw unparsed innards, not markup this
        # sanitizer has walked, so both must be dropped whole rather than
        # falling through to the "drop tag, keep text" branch below.
        if tag in ("script", "style"):
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag not in _ALLOWED_TAGS:
            return  # drop the tag, keep its text content (handled by handle_data)
        self._out.append(f"<{tag}{self._build_attr_str(attrs)}>")

    def handle_startendtag(self, tag, attrs):
        if tag in ("script", "style") or self._skip_depth:
            return
        if tag not in _ALLOWED_TAGS:
            return
        self._out.append(f"<{tag}{self._build_attr_str(attrs)} />")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in _ALLOWED_TAGS and tag not in _VOID_TAGS:
            self._out.append(f"</{tag}>")

    def handle_data(self, data):
        # HTMLParser(convert_charrefs=True) hands this method already
        # entity-DECODED text (C1) -- markdown escapes `<script>` inside a
        # fenced/inline code block to `&lt;script&gt;`, HTMLParser decodes
        # that back to `<script>` before it reaches here, and appending it
        # verbatim would reconstitute live markup from what should stay
        # inert text. Escaping on the way OUT closes that regardless of how
        # the entity arrived.
        if not self._skip_depth:
            self._out.append(html_escape.escape(data, quote=False))

    def get_html(self) -> str:
        return "".join(self._out)


def _sanitize_html(html: str) -> str:
    sanitizer = _HTMLSanitizer()
    sanitizer.feed(html)
    sanitizer.close()
    return sanitizer.get_html()


def _render(body: str | None) -> str | None:
    """Markdown -> sanitized HTML. Artifact bodies are model-generated and
    hand-editable, so `markdown.markdown` output is untrusted by construction:
    a raw <script> or an onerror= attribute in a pasted prompt sheet reaches the
    template's `| safe` otherwise. Sanitizing at the PRODUCER means a new
    consumer (an htmx fragment, a partial, a future panel) cannot forget."""
    return _sanitize_html(markdown.markdown(body)) if body else None


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
            # The final `result` event's `result` string is byte-identical to
            # the last assistant text block on a real recorded turn (verified
            # empirically) -- the assistant-text branch above already
            # rendered it, so appending it again here would show the turn's
            # final answer twice. No separate entry for `result` events.
    return messages


def _resolve_project_stage(request: Request, project_id: int, stage_id: str):
    """Resolve (project, stage_def, stage_row) or raise the right 404.

    stage_def comes from the full pipeline.yaml topology, but create_project
    only materialises the stage ROWS whose brand_scope matches the project's
    brand — so a `generic` project has no `grounding` row even though the
    topology defines that stage. Without the stage_row check the grounding
    routes would render a phantom page and blow up with a TypeError deeper in
    turn_service."""
    conn = request.app.state.conn
    project = db_mod.get_project(conn, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    stage_defs = request.app.state.stage_defs
    stage_def = next((s for s in stage_defs if s.id == stage_id), None)
    if stage_def is None:
        raise HTTPException(status_code=404, detail="Stage not found")
    stage_row = db_mod.get_stage(conn, project_id, stage_id)
    if stage_row is None:
        raise HTTPException(status_code=404, detail="Stage not applicable to this project")
    return project, stage_def, stage_row


def _stage_context(request: Request, project_id: int, stage_id: str, *, error_banner=None) -> dict:
    project, stage_def, stage_row = _resolve_project_stage(request, project_id, stage_id)
    stage_defs = request.app.state.stage_defs
    run_dir = request.app.state.repo_root / "runs" / project["run_id"]
    stage_dir = run_dir / stage_dir_name(stage_def)

    # One card per DECLARED dependency, present or not (E-05). Concatenating only
    # the ones that resolved made a partial input look complete.
    inputs = []
    for dep_id in stage_def.depends_on:
        up_def = next(s for s in stage_defs if s.id == dep_id)
        up_latest = artifacts.latest_artifact_path(run_dir / stage_dir_name(up_def))
        body = None
        malformed = False
        if up_latest is not None:
            try:
                _, body = artifacts.read_artifact(up_latest)
            except artifacts.MalformedArtifactError:
                # E-05 extends to an unreadable upstream, not just an absent
                # one: the card must show "present but broken", not silently
                # drop body/html and look identical to a clean stage that
                # simply produced nothing.
                malformed = True
        inputs.append({
            "stage_id": dep_id,
            "present": up_latest is not None,
            "malformed": malformed,
            "artifact": up_latest.name if up_latest is not None else None,
            "body": body,                # raw source text -- never rendered via `| safe`
            "html": _render(body),       # sanitized at the producer
        })
    # Keep input_body/input_html populated for one release: a later package's
    # task migrates the template off them, but any template code not yet
    # updated to read `inputs` must still work.
    input_body = "\n\n---\n\n".join(
        f"## From {i['stage_id']}\n\n{i['body']}" for i in inputs if i["present"]
    ) or None
    input_html = _render(input_body)

    # Grounding is an optional RGS companion, not a formal `depends_on` --
    # the chat/turn_service path already hands it to the AI via
    # grounding_pointer (see stage_chat below), so the Input panel must show
    # it too or the page looks like grounding produced nothing usable.
    grounding_input_body = None
    if project["brand"] == "raisinggoodsports" and stage_id != "grounding":
        grounding_dir = run_dir / "00-grounding"
        grounding_path = artifacts.resolve_latest_artifact(
            request.app.state.repo_root, "grounding", grounding_dir
        )
        if grounding_path is not None:
            _, grounding_input_body = artifacts.parse_frontmatter(
                grounding_path.read_text(encoding="utf-8")
            )
    grounding_input_html = _render(grounding_input_body)

    output_body = None
    output_gates = []
    output_meta = {}
    error_banner_from_malformed = None
    latest = artifacts.resolve_latest_artifact(request.app.state.repo_root, stage_id, stage_dir)
    if latest is not None:
        try:
            output_meta, output_body = artifacts.read_artifact(latest)
        except artifacts.MalformedArtifactError as exc:
            error_banner_from_malformed = {
                "kind": "malformed_artifact",
                "message": f"{exc.path.name} is malformed ({exc.reason}). Fix the file or "
                           "regenerate the stage.",
            }
        else:
            output_gates = output_meta.get("gates") or []
    output_html = _render(output_body)
    # An explicit error_banner (e.g. _stage_conflict re-rendering a 409 for a
    # blocking gate or a locked stage) is the caller's own diagnosis of THIS
    # request and takes priority over one discovered incidentally while
    # re-reading the output file for the page shell -- the caller's banner is
    # what the operator was actually trying to do; a malformed artifact
    # discovered along the way is real but secondary, and would otherwise
    # silently replace a more specific, more relevant message.
    error_banner = error_banner or error_banner_from_malformed
    # gate_view/has_blocking_gate are the ONE classifier every surface reads
    # (approve_stage, the per-gate tag, and the page-level flag) -- see
    # classify_gates's docstring. A never-ran gate is blocking; only an
    # explicit "pass" is not. classify_gates assumes a list of dicts;
    # approval_service.approve_stage validates that shape before it ever gets
    # here and raises a 409 on anything else, but a re-render via
    # _stage_conflict (this exact malformed-gates case, via approve_stage's
    # ValueError) re-reads the same frontmatter independently, so this must
    # not trust the shape either -- fail-closed (blocking, not a 500).
    if isinstance(output_gates, list) and all(isinstance(g, dict) for g in output_gates):
        gate_view = classify_gates(stage_id, output_gates)
    else:
        gate_view = [{
            "name": None, "state": "malformed", "status_raw": output_gates,
            "blocking": True, "findings": [],
        }]
    has_blocking_gate = any(g["blocking"] for g in gate_view)

    edit_blocked_reason = None
    if stage_id == "grounding":
        edit_blocked_reason = ("Grounding's output lives in rgs-briefs/ -- edit that file "
                               "directly, not through this app.")
    elif is_locked_or_running(stage_row["status"]):
        edit_blocked_reason = f"Stage is {stage_row['status']} and cannot be edited yet."

    # Skip re-reading a file _stage_context already found malformed above --
    # read_gate_overrides calls read_artifact internally too, and would raise
    # the identical MalformedArtifactError a second time for no new signal.
    overrides = (
        artifacts.read_gate_overrides(latest)
        if latest is not None and error_banner_from_malformed is None
        else []
    )

    transcript = _load_transcript(stage_dir)
    stage_rows = db_mod.list_stages(request.app.state.conn, project_id)
    nav = build_stage_nav(stage_defs, stage_rows)

    return {
        "project": project, "stage_id": stage_id, "stage_status": stage_row["status"],
        "input_body": input_body, "input_html": input_html, "inputs": inputs,
        "grounding_input_body": grounding_input_body, "grounding_input_html": grounding_input_html,
        "output_body": output_body, "output_html": output_html,
        "output_gates": output_gates, "gate_view": gate_view,
        "has_blocking_gate": has_blocking_gate,
        # stage.html's finding-styling block reads this rather than hardcoding
        # its own tuple, so the closed `kind` vocabulary has exactly two
        # guarded copies (this constant and scripts/lint_script_language.py's
        # NON_BLOCKING_KINDS) instead of a third, undocumented one drifting
        # silently in the template.
        "non_blocking_kinds": gates._NON_BLOCKING_KINDS,
        "edit_allowed": edit_blocked_reason is None and output_body is not None,
        "edit_blocked_reason": edit_blocked_reason,
        "edit_action": f"/projects/{project_id}/stages/{stage_id}/edit",
        "edit_field": "body",
        # P15's E-06: these three were parsed into output_meta and then thrown
        # away, so the page could not say whether the body on screen was v1 or
        # v7. None means the key was absent, and artifact_finalized_at is None
        # is the reliable "still a draft" signal (stage_status moves
        # independently of it).
        "artifact_version": output_meta.get("version"),
        "artifact_created_at": output_meta.get("created_at"),
        "artifact_finalized_at": output_meta.get("finalized_at"),
        # Append-only per P2's A-38 fix; the singular is the most recent entry.
        "gate_overrides": overrides,
        "gate_override": overrides[-1] if overrides else None,
        "transcript": transcript, "nav": nav,
        "active_nav": "projects",
        "cli_available": request.app.state.cli_available,
        "error_banner": error_banner,
    }


def _stage_conflict(request: Request, project_id: int, stage_id: str, message: str,
                     *, kind: str = "conflict", status_code: int = 409):
    """E-04: an expected failure returns the page it came from, with a banner --
    same status code, recoverable UI. PlainTextResponse threw away the header,
    the nav, the form and any typed content."""
    context = _stage_context(request, project_id, stage_id,
                              error_banner={"kind": kind, "message": message})
    return request.app.state.templates.TemplateResponse(
        request, "stage.html", context, status_code=status_code
    )


@router.get("/projects/{project_id}/stages/{stage_id}", response_class=HTMLResponse)
def stage_page(request: Request, project_id: int, stage_id: str):
    return request.app.state.templates.TemplateResponse(
        request, "stage.html", _stage_context(request, project_id, stage_id)
    )


@router.post("/projects/{project_id}/stages/{stage_id}/chat")
async def stage_chat(request: Request, project_id: int, stage_id: str, message: str = Form(...)):
    project, stage_def, stage_row = _resolve_project_stage(request, project_id, stage_id)
    # Pre-check for a clean 409, same rationale as the any_turn_running check
    # below: turn_service.run_stage_turn enforces this invariant itself too
    # (StageNotRunnableError), but that check does not execute until the
    # StreamingResponse body generator is first iterated, by which point a
    # 200 and SSE headers are already committed.
    if is_locked_or_running(stage_row["status"]):
        return _stage_conflict(
            request, project_id, stage_id,
            f"Stage '{stage_id}' is {stage_row['status']} and cannot accept chat messages yet.",
        )
    conn = request.app.state.conn
    repo_root = request.app.state.repo_root
    stage_defs = request.app.state.stage_defs
    run_dir = repo_root / "runs" / project["run_id"]
    templates_dir = repo_root / "pipeline-app" / "stage_templates"

    # Checked here, before any response is started: run_stage_turn also checks
    # internally, but that check does not execute until the StreamingResponse
    # body generator is first iterated — by then a 200 and SSE headers are
    # already committed, so the client would see a broken stream instead of an
    # explicit "already running" error. Checking here lets a concurrent
    # request get a clean 409 with no response ever started.
    if turn_service.any_turn_running(conn):
        return _stage_conflict(
            request, project_id, stage_id, "Another stage turn is already running."
        )

    grounding_pointer = None
    if project["brand"] == "raisinggoodsports" and stage_id != "grounding":
        grounding_dir = run_dir / "00-grounding"
        status = grounding_service.verify_pointer(grounding_dir, repo_root)
        if status.state == "ok":
            grounding_pointer = grounding_service.read_pointer(grounding_dir)
        elif status.state != "no_pointer":
            # no_pointer means the stage never ran grounding at all -- not an
            # error, just nothing to inject. Anything else (missing_target,
            # hash_mismatch, unpinned) is a real staleness/corruption signal.
            obs.record_event(
                conn, kind="grounding.pointer_invalid", severity="warning",
                source="routes.stages", message=(
                    f"grounding pointer for project {project_id} is {status.state} "
                    f"-- omitting it from this turn's context"
                ),
                detail={"project_id": project_id, "state": status.state},
            )

    if stage_id == "grounding":
        async def event_stream():
            rgs_briefs_dir = repo_root / "rgs-briefs"
            grounding_dir = run_dir / "00-grounding"
            before = grounding_service.snapshot_rgs_briefs(rgs_briefs_dir)

            async for event in turn_service.run_stage_turn(
                conn, repo_root, run_dir, templates_dir,
                project_id, project["run_id"], stage_def, stage_defs, message,
                finalize_artifact=False,
            ):
                yield f"data: {json.dumps(event)}\n\n"

            # The grounding skill's real artifact lands in rgs-briefs/, not
            # runs/ — finalize_artifact=False above skips turn_service's
            # normal artifact/status handling so this stage-specific path can
            # take over: identify which file appeared and point at it. The
            # grounding skill always writes a new versioned filename (see
            # rgs-grounding's SKILL.md), so there is nothing to archive —
            # the previous version is simply no longer the pointer target.
            after = grounding_service.snapshot_rgs_briefs(rgs_briefs_dir)
            change = grounding_service.classify_brief_change(before, after)
            stage_row = db_mod.get_stage(conn, project_id, "grounding")
            if change.brief is not None:
                grounding_service.write_pointer(
                    grounding_dir, f"rgs-briefs/{change.brief}", repo_root
                )
                db_mod.update_stage_status(conn, stage_row["id"], "awaiting_review")
            else:
                obs.record_event(
                    conn, kind="grounding.brief_not_identified", severity="warning",
                    source="routes.stages", message=change.reason,
                    detail={"project_id": project_id, "added": change.added,
                            "modified": change.modified},
                )
                db_mod.update_stage_status(conn, stage_row["id"], "no_artifact")

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    async def event_stream():
        async for event in turn_service.run_stage_turn(
            conn, repo_root, run_dir, templates_dir,
            project_id, project["run_id"], stage_def, stage_defs, message,
            grounding_pointer=grounding_pointer,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/projects/{project_id}/stages/{stage_id}/approve")
def approve_stage_route(
    request: Request,
    project_id: int,
    stage_id: str,
    override_reason: str = Form(""),
):
    project, _stage_def, _stage_row = _resolve_project_stage(request, project_id, stage_id)
    conn = request.app.state.conn
    repo_root = request.app.state.repo_root
    stage_defs = request.app.state.stage_defs
    run_dir = repo_root / "runs" / project["run_id"]
    try:
        approval_service.approve_stage(
            conn, repo_root, run_dir, project_id, stage_defs, stage_id,
            override_reason=override_reason,
        )
    except ValueError as exc:
        # Nothing to approve yet, the locked/running invariant, or a failing
        # gate -- approval_service raises for all three; an explicit conflict
        # state, never a 500.
        return _stage_conflict(request, project_id, stage_id, str(exc))
    return RedirectResponse(url=f"/projects/{project_id}/stages/{stage_id}", status_code=303)


@router.post("/projects/{project_id}/stages/{stage_id}/edit")
def edit_stage_output_route(request: Request, project_id: int, stage_id: str, body: str = Form(...)):
    project, stage_def, stage_row = _resolve_project_stage(request, project_id, stage_id)
    if stage_id == "grounding":
        return _stage_conflict(
            request, project_id, stage_id,
            "Grounding's output lives in rgs-briefs/ -- edit that file directly, not through this app.",
        )
    if is_locked_or_running(stage_row["status"]):
        return _stage_conflict(
            request, project_id, stage_id,
            f"Stage '{stage_id}' is {stage_row['status']} and cannot be edited yet.",
        )
    conn = request.app.state.conn
    repo_root = request.app.state.repo_root
    stage_defs = request.app.state.stage_defs
    run_dir = repo_root / "runs" / project["run_id"]
    stage_dir = run_dir / stage_dir_name(stage_def)

    stage_dir.mkdir(parents=True, exist_ok=True)
    # The edit path gets its OWN scratch file, never the turn path's shared
    # raw_output.md (A-64): that file is turn_service's before_mtime baseline,
    # and truncating it here made a hand edit look like a turn's output. The
    # extension is deliberately not `.md` so browse_service's stage listing
    # (which shows every *.md except raw_output.md) never surfaces it.
    scratch = stage_dir / ".edit_scratch.tmp"
    try:
        scratch.write_text(body, encoding="utf-8")
        upstream_by_stage = gates.resolve_upstream_by_stage(run_dir, stage_defs, stage_def)
        gate_results = gates.run_gates_for_stage(repo_root, stage_id, scratch, upstream_by_stage)
    except Exception as exc:  # noqa: BLE001 -- an escaped gate is a conflict, not a 500
        obs.log("gate.escaped", level="error", stage=stage_id, project_id=project_id,
                error=str(exc))
        obs.record_event(
            conn, kind="gate.escaped", severity="error", source="routes.stages",
            message=f"hand edit of '{stage_id}' aborted: {exc}",
            detail={"project_id": project_id, "stage_id": stage_id},
        )
        return _stage_conflict(request, project_id, stage_id, str(exc))
    finally:
        scratch.unlink(missing_ok=True)

    # Version allocation is EXCLUSIVE and taken after the gate, not before it:
    # next_version_number is advisory only now, and a read-then-write spanning
    # a full linter load and run is exactly the window two concurrent edit
    # POSTs collide in. Reserve, write, or release.
    reservation = artifacts.reserve_version(stage_dir)
    try:
        meta = {
            "schema_version": 1,
            "run_id": project["run_id"],
            "stage": stage_def.skill,
            "version": reservation.version,
            "status": "draft",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(
                timespec="seconds"
            ),
            "finalized_at": None,
            "supersedes": (
                f"artifact.v{reservation.version - 1}.md" if reservation.version > 1 else None
            ),
            # A list of PATHS in, [{path, sha256}] out. turn_service.run_stage_turn
            # records the same shape from the same helper, so the two write paths
            # cannot produce different provenance (A-60).
            "depends_on": artifacts.compute_depends_on(
                run_dir, list(upstream_by_stage.values())
            ),
            "gates": gate_results,
        }
        artifacts.write_reserved_artifact(reservation, meta, body)
    except BaseException:
        artifacts.release_version(reservation)
        raise

    # Design spec §2: a hand edit mints artifact.v{N+1}.md exactly like a
    # regenerate does, so it gets the same downstream treatment — approved
    # dependents whose recorded hash no longer matches go stale, and this
    # stage drops back to awaiting_review because a fresh unapproved draft
    # now exists (even if the stage had already been approved).
    turn_service.propagate_staleness(conn, run_dir, stage_defs, project_id, stage_id)
    db_mod.update_stage_status(conn, stage_row["id"], "awaiting_review")
    approval_service.relock_unsatisfied_dependents(conn, run_dir, stage_defs, project_id)

    return RedirectResponse(url=f"/projects/{project_id}/stages/{stage_id}", status_code=303)
