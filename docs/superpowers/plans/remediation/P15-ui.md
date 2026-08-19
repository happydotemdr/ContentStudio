# P15 — UI: templates, stylesheet, Browse

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` or
> `superpowers:executing-plans` to work this file task-by-task. Every task is TDD:
> failing test → run it → see it fail for the right reason → implement → see it pass → commit.
>
> Parent: [`../2026-08-08-audit-remediation.md`](../2026-08-08-audit-remediation.md). Its
> **Global Constraints**, **test standard** and **Frozen interfaces** apply to every task here
> and are not restated.
>
> Both commands below are run from `pipeline-app/`:
> ```
> cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app"
> python -m pytest tests/test_header.py tests/test_routes_browse.py tests/test_browse_service.py -q
> ```

---

> ## 0. Amendment — live-state check before starting (2026-08-18)
>
> Before dispatching Task 1, every one of P15's 16 findings was checked against the live repo
> (P3, P6, P7, P8, P9 and one out-of-programme feature branch have all merged since this plan was
> written, and several touched files P15 will soon own exclusively). Verdict: **13 of 16 findings
> are untouched — proceed exactly as written.** Three tasks (T9, T10, T22) have their blocking
> "Consumes P3" dependency already satisfied, and two of those three templates already carry a
> partial, differently-shaped implementation that this amendment describes so the task's
> "delete the old block" step isn't dispatched against stale line numbers.
>
> **What already landed, and why:** P3 (Wave B2) merged its full gate/approval contract —
> `gate_view[]`, `has_blocking_gate`, `error_banner`, `artifact_version/created_at/finalized_at`,
> `gate_override`, and the 409-re-renders-`stage.html` behavior — plus `edit_allowed`,
> `edit_blocked_reason`, `edit_action`, `edit_field` for the `inputs[]` disclosure T22 renders.
> All of it exists in `routes/stages.py`/`approval_service.py` exactly as this plan's §7
> "Consumes P3" notes assume. **None of this is a P15 finding and none of it required any
> amendment to what P3 shipped** — it means T8, T9, T10 and T22 can start immediately with no
> wait, which the original wave table already scheduled correctly (P15 was always meant to land
> after P3), but is worth confirming explicitly since three other Wave-B4 packages (P6/P7/P8/P9)
> landed in between and it was not re-verified until now.
>
> **T9 (E-02) — the old block to delete is not empty, and not at the plan's assumed position.**
> `templates/stage.html` currently has a WORKING gate-rendering block, added incidentally by
> whichever commit adopted P3's `gate_view` contract (not a P15 change) — it is not the pre-P3
> `output_gates`/`input_html` shape T9's "Run: fails" step describes.
> Current shape, for the record (verified live, not from the diff that introduced it):
> - Position: `stage.html:47-70`, rendered **below** the artifact body (`output_html` at line 49,
>   `.gates-panel` opening at line 50) — the plan wants it **above**, per T9's own failing test
>   `test_gate_panel_renders_above_the_artifact_body`.
> - Guard: `{% if gate_view %}` (line 50) — when `gate_view` is empty (no gate registered for the
>   stage at all, as opposed to one registered-but-`never_ran`), the **entire panel vanishes**,
>   not just a status line. T9's own template ships a `{% if not gate_view %}` "No gate is
>   registered for this stage." explainer for exactly this case — that case is not yet handled.
> - CSS classes: `status-blocking` / `status-ok` (line 55) — two classes, not one-per-`state`.
>   T9's plan replaces these with `status-{{ gate.state }}` (five values:
>   `passed/failed/errored/never_ran/unknown`), which also requires the five new CSS rules T9
>   adds to `static/style.css` (none of which exist yet — confirmed, `style.css` has no
>   `.status-never_ran`/`.status-unknown` rule today).
> - No `never_ran`/`unknown` explainer text, no `partials/gate_strip.html` extraction (the whole
>   block is inline in `stage.html`) — both are new work, exactly as T9 already plans.
>
> **Net effect on T9:** delete `stage.html:47-70`'s current inline block (not the plan's assumed
> "lines 35–55" — line numbers have drifted; find the block by content, `<div class="gates-panel">`
> through its matching `{% endif %}`), not just move it. Everything else in T9's own text —
> the new `partials/gate_strip.html`, the five CSS rules, the four tests — applies unchanged.
>
> **T10 (E-03) — half already done, half still open.** `has_blocking_gate` already gates the
> override `<input>` (`stage.html:75-78`), and a blocked approve already re-renders full
> `stage.html` at **409** via `_stage_conflict` (`routes/stages.py:369-378`) rather than a bare
> `PlainTextResponse` — both are pre-existing, correct, and need no work. Still open, exactly as
> T10 plans: no inline blocking-reason paragraph (`id="approve-blocked-reason"` or similar) next
> to the override field, no `approval_block_reasons` key read anywhere in the template, and the
> error banner element uses `class="error-banner"` with no `data-error-kind` attribute — T10's own
> failing tests will catch all three; no change to T10's task text is needed, only awareness that
> the override-field and 409-shape halves will already be green before this task's own edits land.
>
> **T22 (P3 `inputs[]`/`edit_*`, no P15 finding) — same shape as T10.** `routes/stages.py` already
> computes and passes `edit_allowed`/`edit_blocked_reason`/`edit_action`/`edit_field`, and
> `stage.html:13-26` already has a per-dependency loop distinguishing present/malformed/missing
> inputs (a different, `input-card`-less shape than T22's planned markup) — but the `edit_*` keys
> are computed and **completely unused** in the template today. T22 proceeds as written; the
> `inputs[]` half needs re-shaping to the plan's card markup, the `edit_*` disclosure needs adding
> from scratch.
>
> **B-74 (T15) — the underlying data already agrees; only the guard is missing.** The seven
> `<option>` values in `discovery_handles.html` (`youtube, bluesky, instagram, linkedin-profile,
> linkedin-company, facebook, x`) already match `run_discovery_cron.build_adapters().keys()`
> exactly — this finding carries no live bug today, only unguarded risk. T15 proceeds exactly as
> written; it is pinning a coincidence, not fixing a drift.
>
> **Everything else (D-41, D-42, E-13, E-08, E-06, E-01, E-09, E-10, E-12, E-14a/b/c, D-47, E-15,
> E-16, T0) — confirmed NOT STARTED, no amendment needed.** htmx is still CDN-loaded
> (`templates/base.html:7`, `https://unpkg.com/htmx.org@2.0.0`); `browse_service.py` has no
> sanitizer and `_has_md_below`/`resolve_grounding_pointer` still collapse absent/broken into one
> falsy value; `discovery_runs.html`/`discovery_handles.html` carry none of the planned CSS status
> modifiers; `doctor.html` still bare-prints `{{ orphaned_count }}` (literally renders the string
> `"None"` today) and duplicates the skill list instead of linking it. Every task not named above
> applies exactly as written, against exactly the "before" state each task's own failing test
> already assumes.

## 1. Scope

### Files this package owns (no other package may touch these)

```
pipeline-app/pipeline_app/templates/**            (all of it)
  base.html
  stage.html
  browse.html
  discovery_handles.html
  discovery_runs.html
  doctor.html
  inspector.html
  project_home.html
  project_list.html
  skill_editor.html
  skill_list.html
  partials/header.html
  partials/sidebar.html
  partials/browse_file.html
  partials/browse_tree_items.html
pipeline-app/pipeline_app/static/style.css
pipeline-app/pipeline_app/routes/browse.py
pipeline-app/pipeline_app/browse_service.py
pipeline-app/tests/test_routes_browse.py
pipeline-app/tests/test_browse_service.py
pipeline-app/tests/test_header.py
```

**New files this package creates** (both inside directories no other package claims):

- `pipeline-app/pipeline_app/static/htmx-2.0.0.min.js` — the vendored library (T1).
- `pipeline-app/pipeline_app/templates/partials/gate_strip.html` — extracted stage gate
  panel (T8). `templates/**` is owned wholesale, so new partials are in scope.

**Explicitly NOT touched:** `routes/stages.py`, `routes/skills.py`, `routes/doctor.py`,
`routes/discovery.py`, `routes/projects.py`, `routes/inspector.py`, `db.py`, `main.py`,
`schema.sql`, `requirements.txt`. Where a finding has a server-side half, that half is named
in §7 as an input consumed and the task is sequenced behind it.

### Finding IDs (16)

`B-74`, `D-41`, `D-42`, `D-47`, `E-01`, `E-02`, `E-03`, `E-06`, `E-08`, `E-09`, `E-10`,
`E-12`, `E-13`, `E-14`, `E-15`, `E-16`.

### Test-file convention

`test_header.py` is this package's **rendered-template suite**, not just a header test. Every
template assertion that is not about `/browse` lives there. T0 renames its module docstring to
say so; the filename stays put because another package owning `test_routes_stages.py`,
`test_routes_discovery.py`, `test_routes_doctor.py` and `test_routes_skills.py` must not be
able to collide with a new file we invent. All three test files assert on **rendered HTML via
the existing FastAPI `TestClient`**. No browser automation anywhere in this package.

---

## 2. Finding → task map

Total coverage: 16 findings, 16 rows, every row carries a task number.

| Finding | Severity | Mode | Task(s) | What P15 does |
|---|---|---|---|---|
| D-41 | S2 | latent | **T1** | Vendor htmx into `static/`; delete the `unpkg.com` `<script>`; add a no-external-hosts guard test over `templates/**` |
| D-42 | S2 | silent | **T1**, **T2** | Same vendoring removes the offline failure; T2 adds the visible signal for every remaining htmx failure |
| E-13 | S2 | silent | **T2**, **T3** | Global `htmx:responseError`/`htmx:sendError` banner, per-target error text, `once` dropped from the tree trigger; T3 makes `/browse/*` return a *rendered* error instead of a 500 |
| E-08 | S3 | latent | **T4**, **T5**, **T6**, **T7** | Three-section IA; `<aside>` only when there is a rail; clickable breadcrumb; real project Overview |
| E-06 | S3 | silent | **T8** | Status strip under the stage heading: status pill, `artifact_version`, `artifact_created_at`, `artifact_finalized_at`, `gate_override.reason` |
| E-02 | S2 | silent | **T9** | Gate strip moved **above** the artifact body and rendered from P3's `gate_view` (registry-aware), so a never-ran gate is a row, not an absence; all five `state` values get an explicit arm |
| E-03 | S2 | loud | **T10** | Override field renders whenever `has_blocking_gate`; the blocking reason is stated inline; the 409 re-render shows `error_banner` in place |
| E-01 | S2 | silent | **T11** | Server-rendered `turn-complete` affordance the SSE `result` branch reveals, replacing the bare `statusLine.remove()` |
| E-09 | S2 | silent | **T12** | `.status-completed` / `.status-completed_with_errors` / `.status-failed` / `.status-queued` modifiers + an error count on the run line |
| E-10 | S2 | silent | **T13** | Per-handle results render `platform/handle (display name)`, errored results hoisted first, long result lists collapsed |
| E-12 | S3 | silent | **T14** | `.status-*` modifiers for the four handle states; the invalid reason (or an explicit "no reason recorded"); poller gets `res.ok` + `try/catch` + a terminal "status unknown — reload" state |
| B-74 | S3 | latent | **T15** | Pinning test: the `<option>` values in `discovery_handles.html` must equal `build_adapters().keys()` |
| E-14 | S2 | silent | **T16**, **T17**, **T18** | (a) unreadable folder becomes a visible disabled row, (b) malformed `pointer.yaml` becomes a visible broken entry, (c) a zero-entry root gets an explicit empty line |
| D-47 | S2 | latent | **T19** | Stdlib allowlist sanitizer in `browse_service`, applied at the Browse producer site; published for P3/P5 to adopt at theirs |
| E-15 | S3 | silent | **T20** | Kickoff-template form renders only when the skill maps to a stage; otherwise an explicit line saying so |
| E-16 | S3 | silent | **T21** | Doctor renders P1's `recent_events`; `orphaned_count is none` renders differently from `0`; the duplicated skill-name list becomes a link |
| *(none — contract conformance)* | — | — | **T22** | Renders P3's `inputs[]` cards and the `edit_*` disclosure. E-05/E-07 are **P3's** findings, but their markup lands in `stage.html`, which is P15's file. Listed so the keys are not published into a template that ignores them. |

---

## 3. Tasks

### T0 — Retitle the rendered-template suite

- [ ] **Edit** `pipeline-app/tests/test_header.py`, adding a module docstring above line 1:

```python
"""Rendered-template assertions for the P15 UI package.

Despite the filename this covers every template except the two Browse
partials (those live in test_routes_browse.py): the shared shell, the
three-section nav, the stage page, the discovery pages, the skill editor
and doctor. Everything here asserts on rendered HTML through the FastAPI
TestClient -- there is no browser automation in this suite.
"""
```

- [ ] Run the suite; it must still pass unchanged.
- [ ] Commit: `docs(tests): state what test_header.py actually covers`

---

### T1 — Vendor htmx; forbid external hosts in templates (D-41, D-42)

**Failing test first.** Append to `tests/test_header.py`:

```python
def test_no_template_references_an_external_host():
    """CLAUDE.md says local-only. A CDN <script> is an undocumented outbound
    dependency with no SRI (D-41) and a silent offline failure (D-42)."""
    from pipeline_app.main import PACKAGE_DIR
    offenders = []
    for path in sorted((PACKAGE_DIR / "templates").rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        for scheme in ("https://", "http://", "//unpkg.com"):
            if scheme in text:
                offenders.append(f"{path.name}: {scheme}")
    assert offenders == []


def test_htmx_is_served_from_the_local_static_mount(client: TestClient):
    from pipeline_app.main import PACKAGE_DIR
    vendored = PACKAGE_DIR / "static" / "htmx-2.0.0.min.js"
    assert vendored.is_file(), "htmx must be vendored, not fetched from a CDN"
    assert vendored.stat().st_size > 10_000, "vendored htmx looks truncated"

    resp = client.get("/")
    assert '<script src="/static/htmx-2.0.0.min.js"></script>' in resp.text

    served = client.get("/static/htmx-2.0.0.min.js")
    assert served.status_code == 200
    assert "javascript" in served.headers["content-type"]
```

- [ ] Run: both fail — the first on `base.html: https://`, the second on the missing file.
- [ ] **Implement.** Place htmx 2.0.0's minified build at
      `pipeline-app/pipeline_app/static/htmx-2.0.0.min.js`. Get it from an existing local copy
      if one is on the machine; otherwise this is the **one** permitted network fetch in this
      package — a one-time vendoring step, not a runtime dependency:

```bash
curl -fsSL https://unpkg.com/htmx.org@2.0.0/dist/htmx.min.js \
  -o pipeline-app/pipeline_app/static/htmx-2.0.0.min.js
```

- [ ] Edit `templates/base.html` line 7:

```html
  <!-- Vendored, not CDN-loaded. A third-party <script> with no integrity hash
       runs with full same-origin authority over an unauthenticated local app
       whose POST routes rewrite skill files, commit to git, spend Anthropic
       credit and start billed Bright Data jobs (D-41) -- and when the CDN is
       unreachable the Browse tree dies with no UI signal at all (D-42).
       Serving it from /static removes both at once and needs no SRI. -->
  <script src="/static/htmx-2.0.0.min.js"></script>
```

- [ ] Run: both pass.

> **Amendment (2026-08-18, found at Opus checkpoint A after T0-T7 landed):** the comment shown
> above ends "removes both **at once** and needs no SRI" — that line contains the substring
> `once`. T2's own test `test_browse_tree_expansion_can_be_retried_after_a_failure` asserts
> `assert "once" not in resp.text` against a page that includes `base.html`'s content, so pasting
> this comment literally makes T2 fail the moment it's written, before T2 even starts its own
> work. T1's implementer caught this and reworded the comment to "removes both **problems** and
> needs no SRI" — same meaning, no collision. Shipped as part of commit `b4826d6`. Recorded here
> per this programme's recurring-bug-class protocol (a bug in the plan's own shown text, not in
> the live repo).
- [ ] Commit: `fix(ui): vendor htmx locally instead of loading it from unpkg`

---

### T2 — Give every htmx request a visible failure path (E-13, D-42)

**Failing test first.** Append to `tests/test_routes_browse.py`:

```python
def test_browse_page_carries_a_global_htmx_error_banner(client):
    test_client, _ = client
    resp = test_client.get("/browse")
    assert 'id="htmx-error-banner"' in resp.text
    assert 'role="alert"' in resp.text
    assert "htmx:responseError" in resp.text
    assert "htmx:sendError" in resp.text


def test_browse_tree_expansion_can_be_retried_after_a_failure(client):
    """`once` meant a subtree whose first fetch failed stayed empty forever."""
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "thinkers" / "plato.md")
    resp = test_client.get("/browse")
    assert 'hx-trigger="toggle from:closest details"' in resp.text
    assert "once" not in resp.text
```

- [ ] Run: fails — no banner, and the trigger still says `toggle once from:closest details`.

> **Amendment (2026-08-18, found at Opus checkpoint A after T0-T7 landed):** `assert "once" not
> in resp.text` bans the English word "once" from the ENTIRE rendered `/browse` page forever —
> not just the `hx-trigger` attribute it was written to pin. `templates/stage.html:36` already
> contains "once" in ordinary prose today, and later browse-partial rewrites (T16-T18) could
> easily introduce the word in an explainer sentence without anyone connecting it to this test.
> Narrowed to `assert "toggle once" not in resp.text` — pins exactly the defect (a `once`
> modifier on the tree's `hx-trigger`) without banning an ordinary word from the page. Fixed in
> a follow-up commit after the Opus checkpoint A review; see the ledger for the commit hash.
- [ ] **Implement.** In `templates/base.html`, immediately after `{% include "partials/header.html" %}`:

```html
  <div id="htmx-error-banner" class="htmx-error-banner" role="alert" hidden></div>
```

Add to the inline `<script>` in `base.html`, inside the existing `DOMContentLoaded` handler:

```js
      // htmx does not swap on a non-2xx response and does nothing at all on a
      // network error, so before this every failed hx-get left the previously
      // viewed document on screen -- a click that looks like it did nothing
      // while showing content belonging to a different file (E-13). Offline,
      // the whole tree was inert with no signal (D-42).
      const banner = document.getElementById("htmx-error-banner");
      const showHtmxError = (text, target) => {
        if (banner) {
          banner.textContent = text;
          banner.hidden = false;
        }
        if (target && target.id !== "htmx-error-banner") {
          const p = document.createElement("p");
          p.className = "browse-error";
          p.textContent = text;
          target.replaceChildren(p);
        }
      };
      document.body.addEventListener("htmx:responseError", (e) => {
        const status = e.detail.xhr ? e.detail.xhr.status : "?";
        showHtmxError(
          `Request to ${e.detail.requestConfig.path} failed (HTTP ${status}). ` +
          "Nothing on this page was updated.",
          e.detail.target,
        );
      });
      document.body.addEventListener("htmx:sendError", (e) => {
        showHtmxError(
          `Could not reach the app at ${e.detail.requestConfig.path}. ` +
          "The server may have stopped. Nothing on this page was updated.",
          e.detail.target,
        );
      });
      document.body.addEventListener("htmx:beforeRequest", () => {
        if (banner) { banner.hidden = true; }
      });
```

In `templates/partials/browse_tree_items.html`, line 18:

```html
           hx-trigger="toggle from:closest details"
```

Add to `static/style.css`:

```css
.htmx-error-banner {
  margin: 0 2rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid #ff5f5f;
  border-radius: 0.25rem;
  background: color-mix(in srgb, #ff5f5f 15%, transparent);
  color: #ff5f5f;
  font-family: var(--font-mono);
  font-size: 0.9rem;
}
```

- [ ] Run: passes.
- [ ] Commit: `fix(ui): surface htmx response and network errors instead of swallowing them`

---

### T3 — `/browse/tree` and `/browse/file` render an error instead of 500ing (E-13)

This is the server half of E-13: today an unexpected exception inside either handler produces
a 500, htmx refuses to swap it, and the operator sees the *previous* document.

**Failing test first.** Append to `tests/test_routes_browse.py`:

```python
def test_browse_file_unexpected_exception_renders_an_error_not_a_500(client, monkeypatch):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "thinkers" / "plato.md", "---\na: 1\n---\n\nBody.\n")

    def _boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr("pipeline_app.browse_service.render_md_file", _boom)
    resp = test_client.get("/browse/file", params={"path": "thinkers/plato.md"})
    assert resp.status_code == 200          # htmx only swaps 2xx
    assert "Could not render this document" in resp.text
    assert "kaboom" in resp.text


def test_browse_file_render_failure_is_distinct_from_an_empty_document(client, monkeypatch):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "thinkers" / "empty.md", "---\na: 1\n---\n")
    ok = test_client.get("/browse/file", params={"path": "thinkers/empty.md"}).text

    def _boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr("pipeline_app.browse_service.render_md_file", _boom)
    broken = test_client.get("/browse/file", params={"path": "thinkers/empty.md"}).text
    assert broken != ok
    assert "browse-error" in broken
    assert "browse-error" not in ok
```

- [ ] Run: fails — `TestClient` re-raises the `RuntimeError`.
- [ ] **Implement** in `routes/browse.py`. Wrap the two htmx handlers:

```python
def _render_partial_error(request: Request, template: str, message: str, exc: Exception):
    # htmx does not swap a non-2xx response, so raising here leaves the
    # operator looking at the PREVIOUS document with no cue that the click
    # failed (E-13). Render the failure into the swap target instead, at 200,
    # and name the exception so the message is diagnosable rather than vague.
    return request.app.state.templates.TemplateResponse(
        request, template, {"error": f"{message}: {type(exc).__name__}: {exc}"}
    )


@router.get("/browse/tree")
def browse_tree(request: Request, path: str = "", root: str = "output"):
    try:
        context = _folder_context(request, root, path)
    except Exception as exc:  # noqa: BLE001 - deliberate: see _render_partial_error
        return _render_partial_error(
            request, "partials/browse_tree_items.html", "Could not list this folder", exc
        )
    context["root"] = root
    return request.app.state.templates.TemplateResponse(
        request, "partials/browse_tree_items.html", context
    )
```

and the same wrapper around the body of `browse_file`, with
`"Could not render this document"` and `"partials/browse_file.html"`.

- [ ] Run: passes.
- [ ] Commit: `fix(browse): render htmx handler failures into the swap target`

---

### T4 — Commit the three-section IA in the header (E-08)

**Failing test first.** Replace `test_every_page_renders_shared_header` and
`test_active_nav_marks_the_current_top_nav_link` in `tests/test_header.py` (see §5 for the
inversion record) and add:

```python
@pytest.mark.parametrize("url", ["/", "/skills", "/doctor", "/inspector"])
def test_every_page_renders_the_three_section_top_nav(client: TestClient, url: str):
    resp = client.get(url)
    assert resp.status_code == 200
    assert 'class="wordmark"' in resp.text
    assert 'class="top-nav"' in resp.text
    assert 'class="status-dot' in resp.text
    # Exactly three top-level sections -- Skills/Doctor/Inspector/Browse are
    # demoted into Library, and the two Discovery entries collapse to one.
    import re
    nav = re.search(r'<nav class="top-nav">(.*?)</nav>', resp.text, re.S).group(1)
    assert re.findall(r'<a href="([^"]+)"', nav) == ["/", "/discovery/handles", "/browse"]
    assert ">Projects<" in nav and ">Discovery<" in nav and ">Library<" in nav
    assert "Discovery Runs" not in nav


@pytest.mark.parametrize(
    "url,expected",
    [
        ("/skills", ["/browse", "/skills", "/doctor", "/inspector"]),
        ("/doctor", ["/browse", "/skills", "/doctor", "/inspector"]),
        ("/inspector", ["/browse", "/skills", "/doctor", "/inspector"]),
    ],
)
def test_library_pages_render_the_library_tab_strip(client: TestClient, url, expected):
    import re
    resp = client.get(url)
    strip = re.search(r'<nav class="sub-nav">(.*?)</nav>', resp.text, re.S).group(1)
    assert re.findall(r'<a href="([^"#]+)', strip) == expected


def test_the_current_section_and_tab_are_both_marked_active(client: TestClient):
    resp = client.get("/doctor")
    assert '<a href="/browse" class="active">Library</a>' in resp.text
    assert '<a href="/doctor" class="active">System</a>' in resp.text


def test_projects_page_has_no_tab_strip(client: TestClient):
    resp = client.get("/")
    assert 'class="sub-nav"' not in resp.text
```

- [ ] Run: fails — seven flat links, no `sub-nav`.
- [ ] **Implement.** Rewrite `templates/partials/header.html`:

```html
{# The section is derived from the `active_nav` key the routes already pass,
   so collapsing seven flat peers into three sections needs no route change.
   Projects is a hierarchy, Discovery is a subsystem with co-equal views, and
   everything else is a utility drawer -- ranking those four as siblings of
   the whole production pipeline is what made this "unwieldy" (E-08). #}
{% set _an = active_nav | default('') %}
{% set nav_section = {
     'projects': 'projects',
     'discovery_handles': 'discovery', 'discovery_runs': 'discovery',
     'browse': 'library', 'skills': 'library',
     'doctor': 'library', 'inspector': 'library',
   }.get(_an, '') %}
<header class="site-header">
  <a class="wordmark" href="/">ContentStudio</a>
  <nav class="top-nav">
    <a href="/" class="{{ 'active' if nav_section == 'projects' }}">Projects</a>
    <a href="/discovery/handles" class="{{ 'active' if nav_section == 'discovery' }}">Discovery</a>
    <a href="/browse" class="{{ 'active' if nav_section == 'library' }}">Library</a>
  </nav>
  {% if project %}
  <div class="breadcrumb">
    <a href="/projects/{{ project.id }}">{{ project.run_id }}</a>
    {% if stage_id %} / <span class="breadcrumb-current">{{ stage_id }}</span>{% endif %}
  </div>
  {% endif %}
  <div class="cli-status">
    <span class="status-dot {{ 'online' if cli_available else 'offline' }}"></span>
    {{ "SYSTEM ONLINE" if cli_available else "CLI UNAVAILABLE" }}
  </div>
</header>
{% if nav_section in ('discovery', 'library') %}
<nav class="sub-nav">
  {% if nav_section == 'discovery' %}
  <a href="/discovery/handles" class="{{ 'active' if _an == 'discovery_handles' }}">Sources</a>
  <a href="/discovery/runs" class="{{ 'active' if _an == 'discovery_runs' }}">Runs</a>
  {# Schedule is a section of the Sources page, not its own route: splitting it
     out needs routes/discovery.py, which belongs to P8. The anchor is the
     in-package approximation and the section id it targets is added in T14. #}
  <a href="/discovery/handles#schedule">Schedule</a>
  {% else %}
  <a href="/browse" class="{{ 'active' if _an == 'browse' }}">Files</a>
  <a href="/skills" class="{{ 'active' if _an == 'skills' }}">Skills</a>
  <a href="/doctor" class="{{ 'active' if _an == 'doctor' }}">System</a>
  <a href="/inspector" class="{{ 'active' if _an == 'inspector' }}">Open by path</a>
  {% endif %}
</nav>
{% endif %}
```

Add to `static/style.css`:

```css
.sub-nav {
  display: flex;
  gap: 1.25rem;
  padding: 0.4rem 1.5rem;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border);
  font-family: var(--font-mono);
  font-size: 0.9rem;
}
.sub-nav a { color: var(--text-dim); }
.sub-nav a:hover { color: var(--text); text-decoration: none; }
.sub-nav a.active { color: var(--accent-cyan); text-shadow: 0 0 4px var(--accent-cyan); }
.breadcrumb-current { color: var(--text); }
```

- [ ] Run: passes.
- [ ] Commit: `feat(ui): collapse seven flat nav peers into Projects / Discovery / Library`

---

### T4a — Align page headings with the new tab labels (E-08 follow-up, found at Opus checkpoint A)

**Not one of the plan's original 16 findings.** T4 renamed the nav tabs but left every page's own
`<h1>` unchanged, so a page can now contradict the tab that linked to it:

| Tab (`partials/header.html`) | Page `<h1>` before this task |
|---|---|
| Files | `browse.html` — "Browse" |
| System | `doctor.html` — "Doctor" |
| Open by path | `inspector.html` — "MD Inspector" |
| Sources | `discovery_handles.html` — "Discovery: Handles" |
| Runs | `discovery_runs.html` — "Discovery: Run History" |

E-08 is precisely "the IA is unwieldy / inconsistent" — a renamed tab landing on a contradicting
heading is the same defect one layer down, and leaving it unfixed would read as a regression in
authorial care mid-package, not a deferred nice-to-have. All five files are already `templates/**`
files P15 owns wholesale.

**Failing test first.** Append to `tests/test_header.py`:

```python
@pytest.mark.parametrize(
    "url,heading",
    [
        ("/browse", "Files"),
        ("/doctor", "System"),
        ("/inspector", "Open by path"),
        ("/discovery/handles", "Sources"),
        ("/discovery/runs", "Runs"),
    ],
)
def test_page_heading_matches_its_own_tab_label(client: TestClient, url, heading):
    resp = client.get(url)
    assert f"<h1>{heading}</h1>" in resp.text
```

- [ ] Run: fails on all five — the old headings are still in place.
- [ ] **Implement.** In each of the five templates, change the `<h1>` text only (no other markup)
      to match its tab label exactly: `browse.html` → `<h1>Files</h1>`, `doctor.html` →
      `<h1>System</h1>`, `inspector.html` → `<h1>Open by path</h1>`,
      `discovery_handles.html` → `<h1>Sources</h1>`, `discovery_runs.html` → `<h1>Runs</h1>`.
- [ ] Run: passes.
- [ ] Commit: `fix(ui): align page headings with their tab labels`

---

### T5 — Stop shipping an empty `<aside>` on every non-project page (E-08)

**Failing test first.** In `tests/test_header.py`, replace `test_page_shell_wraps_sidebar_and_main`
(§5) with:

```python
def test_pages_without_a_stage_rail_ship_no_aside_at_all(client: TestClient):
    resp = client.get("/")
    assert 'class="app-shell"' in resp.text
    assert 'class="app-main"' in resp.text
    assert "<aside" not in resp.text


def test_a_project_page_does_ship_the_stage_rail_aside(client_with_stage):
    test_client, _app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert 'class="app-sidebar"' in page.text
    assert 'class="pipeline-nav"' in page.text
```

- [ ] Run: the first fails — `base.html:112` renders `<aside>` unconditionally.

> **Amendment (2026-08-18, found during T5 execution):** the shown `<div>` markup below
> conflicts with its own paired test. `class="app-shell{% if not nav %} app-shell-full{% endif %}"`
> renders `class="app-shell app-shell-full"` on any page where `nav` is falsy (e.g. `/`) — which
> does **not** contain the literal substring `class="app-shell"` that
> `test_pages_without_a_stage_rail_ship_no_aside_at_all` asserts (the assertion requires the
> attribute value to be the bare string, closing quote immediately after). Implemented instead:
> keep `<div class="app-shell">` unconditional (so the literal test passes), move the
> full-width modifier onto `<body{% if not nav %} class="app-shell-full"{% endif %}>`, and change
> the CSS hook to `.app-shell-full .app-shell { padding-left: 2rem; }` (replacing the old
> `.app-sidebar:not(:has(*)) { flex: 0 0 0; }` collapse hack, same as the plan intended). Same
> observable behavior — no aside when `nav` is falsy, full-width padding applied — different
> mechanism. Landed in commit `f17534e`.
- [ ] **Implement.** `templates/base.html`:

```html
  <div class="app-shell{% if not nav %} app-shell-full{% endif %}">
    {% if nav %}<aside class="app-sidebar">{% block sidebar %}{% include "partials/sidebar.html" %}{% endblock %}</aside>{% endif %}
    <main class="app-main">{% block content %}{% endblock %}</main>
  </div>
```

In `static/style.css`, replace the `:has()` collapse hack (line 135) — it is now dead:

```css
.app-shell-full { padding-left: 2rem; }
```

- [ ] Run: passes.
- [ ] Commit: `fix(ui): render the sidebar element only when there is a stage rail in it`

---

### T6 — Make the breadcrumb a link back to the project (E-08)

The markup landed in T4. This task is the assertion that pins it.

**Failing test first** — extend the existing stage-page breadcrumb test in `tests/test_header.py`:

```python
def test_stage_breadcrumb_links_back_to_the_project(client_with_stage):
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert f'<a href="/projects/{project_id}">{project["run_id"]}</a>' in page.text
    assert "ideation" in page.text
```

- [ ] Run: fails if T4 regressed; otherwise passes immediately — in that case **re-order**:
      write this test *before* T4's header rewrite and watch it fail against the old inert
      `<div class="breadcrumb">{{ project.run_id }} / {{ stage_id }}</div>`.
- [ ] Commit: `test(ui): pin the breadcrumb as a link back to the project`

---

### T7 — Turn the project home into a real Overview (E-08)

`routes/projects.py` already passes `nav` (a list of groups of stages, each with `id`,
`status`, `specialist`). Everything below is computed from that in the template — **no route
change required**.

**Failing test first.** Append to `tests/test_header.py`:

```python
def test_project_home_shows_a_gate_roll_up_and_a_next_action(client_with_stage):
    test_client, _app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    page = test_client.get(f"/projects/{project_id}")
    assert page.status_code == 200
    assert 'class="project-rollup"' in page.text
    assert "Next action" in page.text
    # A fresh project's only stage is ready -- the overview must name it and
    # link straight to it rather than making the operator read the rail.
    assert f'href="/projects/{project_id}/stages/ideation"' in page.text
    assert "ready" in page.text
```

- [ ] Run: fails — `project_home.html` is four lines and renders one `<h1>`.
- [ ] **Implement.** Rewrite `templates/project_home.html`:

```html
{% extends "base.html" %}
{% block content %}
{# Before this, the stage rail WAS the project home: the body was a single
   <h1>, so the pipeline's overall state was unreadable without opening each
   stage in turn (E-08). Everything below is derived from `nav`, which the
   route already passes -- no new context key. #}
{% set stages = nav | map('list') | sum(start=[]) %}
{% set counts = {} %}
{% for s in stages %}{% set _ = counts.update({s.status: counts.get(s.status, 0) + 1}) %}{% endfor %}
{% set attention = stages | selectattr('status', 'equalto', 'stale') | list
                 + stages | selectattr('status', 'equalto', 'awaiting_review') | list
                 + stages | selectattr('status', 'equalto', 'running') | list
                 + stages | selectattr('status', 'equalto', 'ready') | list %}

<h1>{{ project.run_id }}</h1>
<p class="project-meta">brand: {{ project.brand }} &middot; created: {{ project.created_at }}</p>

<section class="project-rollup">
  <h2>Pipeline</h2>
  <p>
    {% for status, n in counts | dictsort %}
    <span class="status status-{{ status }}">{{ n }} {{ status }}</span>
    {% endfor %}
  </p>
  <p class="project-next-action">
    <strong>Next action:</strong>
    {% if attention %}
    <a href="/projects/{{ project.id }}/stages/{{ attention[0].id }}">{{ attention[0].id }}</a>
    &mdash; <span class="status status-{{ attention[0].status }}">{{ attention[0].status }}</span>
    {% else %}
    nothing is waiting on you &mdash; every stage is approved or locked.
    {% endif %}
  </p>
</section>
{% endblock %}
```

Add to `static/style.css`:

```css
.project-meta { color: var(--text-dim); font-family: var(--font-mono); font-size: 0.9rem; }
.project-rollup { margin: 1.5rem 0; }
.project-rollup .status { margin-right: 0.5rem; }
.project-next-action { margin-top: 0.75rem; }
```

- [ ] Run: passes.
- [ ] Commit: `feat(ui): give the project home a gate roll-up and a next-action line`

---

### T8 — Status strip: the stage page states its own status, version and age (E-06)

**Consumes P3** (§7): `stage_status` (already passed), plus `artifact_version`,
`artifact_created_at`, `artifact_finalized_at` — three pass-through fields P3 adds because
`stages.py:100` parses them into `output_meta` and discards them — and `gate_override`
(`{reason, at}`), read as `gate_override.reason`.

**Failing test first.** Append to `tests/test_header.py`:

```python
def test_stage_page_status_strip_states_status_version_and_generated_at(client_with_stage):
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    stage_dir = app.state.repo_root / "runs" / project["run_id"] / "01-ideation"
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / "artifact.v3.md").write_text(
        "---\nversion: 3\ncreated_at: '2026-08-08T10:00:00+00:00'\n"
        "finalized_at: '2026-08-08T10:05:00+00:00'\n"
        "gate_override:\n  reason: dash is inside a verbatim 1886 quote\n"
        "  at: '2026-08-08T10:05:00+00:00'\n---\n\nBody.\n",
        encoding="utf-8",
    )
    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert 'class="status-strip"' in page.text
    assert "artifact v3" in page.text
    assert "2026-08-08T10:00:00+00:00" in page.text
    assert "dash is inside a verbatim 1886 quote" in page.text
```

- [ ] Run: fails — the heading is `run_id — stage_id` and nothing else.
- [ ] **Implement.** In `templates/stage.html`, directly under the `<h1>`:

```html
{# The page never stated its own status, and version / created_at /
   finalized_at were parsed into output_meta and then thrown away, so an
   operator could not tell whether the body on screen was v1 or v7 (E-06). #}
<div class="status-strip">
  <span class="status status-{{ stage_status }}">{{ stage_status }}</span>
  {% if artifact_version %}<span class="strip-item">artifact v{{ artifact_version }}</span>{% endif %}
  {% if artifact_created_at %}<span class="strip-item">generated {{ artifact_created_at }}</span>{% endif %}
  {% if artifact_finalized_at %}<span class="strip-item">finalized {{ artifact_finalized_at }}</span>{% endif %}
</div>
{% if gate_override %}
<p class="override-record">
  Approved over a gate{% if gate_override.at %} on {{ gate_override.at }}{% endif %}.
  Reason on record: {{ gate_override.reason }}
</p>
{% endif %}
```

Add to `static/style.css`:

```css
.status-strip {
  display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;
  margin: 0.25rem 0 1rem;
  font-family: var(--font-mono); font-size: 0.9rem; color: var(--text-dim);
}
.override-record {
  color: var(--accent-amber); font-size: 0.9rem; margin: 0 0 1rem;
}
```

- [ ] Run: passes.

> **Amendment (2026-08-18, found during T8 execution):** landing the status strip made a
> pre-existing test in **P3's own file**, `tests/test_routes_stages.py::
> test_a_malformed_gates_value_shows_a_sensible_notice_not_garbage`, start failing —
> `assert page.text.count('status-') < 5` is a loose regression guard against a specific old
> bug (character-iterating a malformed `gates` value), and the strip's own two legitimate
> `status-` occurrences (`status-strip`, `status-{stage_status}`) pushed the real count from
> 4 to 6, still nowhere near the double-digit count the guarded bug would produce. (Corrected
> 2026-08-18 at Opus checkpoint B: this line originally said "under 5 to 7" — the measured counts
> are 4 and 6. The conclusion and the `< 9` threshold were unaffected either way.)
> `tests/test_routes_stages.py` is not in P15's owned-file list (§1) — it is P3's, already
> merged with no other package currently active on it — so this is a genuine cross-package
> ripple, not scope creep: raised the threshold from `< 5` to `< 9` with an inline comment
> explaining why, preserving the test's actual regression-guard intent. Landed as part of
> commit `1cd7f32`.
- [ ] Commit: `feat(ui): add a stage status strip with version and generation time`

---

### T9 — Gates above the artifact, and a never-ran gate is a row not an absence (E-02)

**Consumes P3** (§7): `gate_view[]`, each entry `{name, state, status_raw, blocking, findings}` with
`state ∈ {passed, failed, errored, never_ran, unknown}`.

**Failing test first.** Append to `tests/test_header.py`:

```python
def _stage_with_artifact(app, project_run_id, frontmatter):
    stage_dir = app.state.repo_root / "runs" / project_run_id / "01-ideation"
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / "artifact.v1.md").write_text(
        f"---\n{frontmatter}---\n\n# Artifact body\n", encoding="utf-8"
    )
    return stage_dir


def test_gate_panel_renders_above_the_artifact_body(client_with_stage):
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    _stage_with_artifact(app, project["run_id"], "gates:\n  - name: gate-x\n    status: pass\n")
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert page.index('class="gates-panel"') < page.index("Artifact body"), \
        "the gate verdict is the page's most decision-relevant fact and must precede the body"


def test_a_gate_that_never_ran_is_rendered_as_never_ran(client_with_stage):
    """THE E-02/E-03 test. An artifact carrying no result for a registered
    gate must not present as a clean pass."""
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    _stage_with_artifact(app, project["run_id"], "version: 1\n")   # no `gates:` key at all
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert 'class="gates-panel"' in page, "the panel must not vanish when no gate ran"
    assert "never ran" in page
    assert "status-never_ran" in page


def test_never_ran_page_differs_from_a_genuinely_clean_pass(client_with_stage):
    """Distinguishability: broken != legitimately-fine."""
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    url = f"/projects/{project_id}/stages/ideation"

    _stage_with_artifact(app, project["run_id"], "version: 1\n")
    never_ran = test_client.get(url).text

    stage_dir = app.state.repo_root / "runs" / project["run_id"] / "01-ideation"
    (stage_dir / "artifact.v2.md").write_text(
        "---\nversion: 2\ngates:\n  - name: gate-x\n    status: pass\n---\n\n# Artifact body\n",
        encoding="utf-8",
    )
    clean = test_client.get(url).text

    assert never_ran != clean
    assert "never ran" in never_ran and "never ran" not in clean


def test_an_unrecognised_gate_status_reads_as_unverified_not_as_a_pass(client_with_stage):
    """P3's fifth state. A typo'd or future status string must not fall
    through to something that looks benign."""
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    _stage_with_artifact(app, project["run_id"], "gates:\n  - name: gate-x\n    status: passsed\n")
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert "status-unknown" in page
    assert "unrecognised result" in page
    assert "passsed" in page          # status_raw is shown, not swallowed
    assert "status-passed" not in page
```

- [ ] Run: fails — `{% if output_gates %}` deletes the whole panel and it sits below the body.
- [ ] **Implement.** Create `templates/partials/gate_strip.html`:

```html
{# Rendered from `gate_view`, which P3 builds from GATE_REGISTRY unioned with
   the artifact's recorded results -- NOT from the frontmatter alone. Reading
   only the frontmatter made an absent `gates` key indistinguishable from a
   clean run, which is exactly the silent pass of an unknown result that
   approval_service was written to refuse (E-02).

   Every one of P3's five states gets an explicit arm. `unknown` is the state
   for a recorded result whose `status` string matches no known verdict -- a
   typo'd or future gate status -- and it must read as "we cannot tell", never
   fall through to something that looks benign. `status_raw` is rendered beside
   it so the unrecognised string is visible rather than swallowed. #}
{% set _labels = {
     "passed": "passed", "failed": "failed", "errored": "errored",
     "never_ran": "never ran", "unknown": "unrecognised result",
   } %}
<div class="gates-panel">
  <h3>Gates</h3>
  {% if not gate_view %}
  <p class="gate-none">No gate is registered for this stage.</p>
  {% endif %}
  {% for gate in gate_view %}
  <div class="gate-result">
    <span class="status status-{{ gate.state }}">
      {{ gate.name }}: {{ _labels.get(gate.state, gate.state) }}
    </span>
    {% if gate.blocking %}<span class="gate-blocking-tag">blocks approval</span>{% endif %}
    {% if gate.state == "never_ran" %}
    <p class="gate-explainer">
      This gate is registered for the stage but the artifact records no result for it —
      it was never run. That is not a pass. Regenerate the stage to run it, or approve
      with an override reason below.
    </p>
    {% elif gate.state == "unknown" %}
    <p class="gate-explainer">
      The artifact records this gate's status as <code>{{ gate.status_raw }}</code>, which is
      not a verdict this app recognises. Treat it as unverified, not as a pass.
    </p>
    {% endif %}
    {% if gate.findings %}
    <ul class="gate-findings">
      {% for finding in gate.findings %}
      {% if finding.kind == "skipped" %}
      <li class="gate-finding gate-finding-skipped">[skipped] {{ finding.check }}{% if finding.beat %} ({{ finding.beat }}){% endif %}: {{ finding.message }}</li>
      {% else %}
      <li class="gate-finding gate-finding-blocking">[{{ finding.check }}]{% if finding.beat %} ({{ finding.beat }}){% endif %}: {{ finding.message }}</li>
      {% endif %}
      {% endfor %}
    </ul>
    {% endif %}
  </div>
  {% endfor %}
</div>
```

In `templates/stage.html`, delete the old inline gates block (lines 35–55) and put this at the
**top** of the output panel, before the body:

```html
<section class="output-panel">
  <h2>Output</h2>
  {% include "partials/gate_strip.html" %}
  {% if output_html %}<div class="rendered-markdown">{{ output_html | safe }}</div>{% else %}<p>No output yet.</p>{% endif %}
```

Add to `static/style.css`:

```css
/* One modifier per state in P3's `gate_view.state` enum. never_ran and unknown
   are deliberately amber-dashed rather than red: they are "we do not know",
   which must not look like a pass and must not look like a measured failure. */
.status-passed { background: color-mix(in srgb, var(--accent-green) 20%, transparent); color: var(--accent-green); border-color: var(--accent-green); }
.status-failed { background: color-mix(in srgb, #ff5f5f 25%, transparent); color: #ff5f5f; border-color: #ff5f5f; }
.status-errored { background: color-mix(in srgb, #ff5f5f 25%, transparent); color: #ff5f5f; border-color: #ff5f5f; }
.status-never_ran { background: color-mix(in srgb, var(--accent-amber) 25%, transparent); color: var(--accent-amber); border-color: var(--accent-amber); border-style: dashed; }
.status-unknown { background: color-mix(in srgb, var(--accent-amber) 25%, transparent); color: var(--accent-amber); border-color: var(--accent-amber); border-style: dashed; }
.gate-blocking-tag { margin-left: 0.5rem; font-family: var(--font-mono); font-size: 0.8rem; color: #ff5f5f; }
.gate-explainer { font-size: 0.9rem; color: var(--accent-amber); margin: 0.25rem 0 0; }
.gate-none { font-size: 0.9rem; color: var(--text-dim); }
```

- [ ] Run: passes.

> **Amendment (2026-08-18, found during T9 execution):** two departures from this task's literal
> text, both confined to files this task already owns.
>
> 1. **`gate-x` is not a real registered gate name.** `test_never_ran_page_differs_from_a_
> genuinely_clean_pass`'s "clean" fixture records `gates:\n  - name: gate-x\n    status: pass\n`,
> but `ideation`'s real `gates.GATE_REGISTRY` entry is `gate_o_ideation_contract`. Because
> `approval_service.classify_gates` unions recorded results with the registry **by name**, a
> recorded result under the wrong name leaves the real registered gate still `never_ran` — so
> the brief's own "clean" page would ALSO show "never ran", collapsing exactly the
> never-ran-vs-clean distinction the test exists to pin. Fixed by using the real registered name
> in the "clean" fixture. Another instance of a placeholder value in the plan's own shown test
> code not matching live registry state.
> 2. **`{% if finding.kind == "skipped" %}` (brief's literal) → `{% if finding.kind in
> non_blocking_kinds %}` (shipped).** The old block already read `non_blocking_kinds` from
> context (P3's `gates._NON_BLOCKING_KINDS`, currently `{"skipped", "info"}`), and two
> pre-existing tests in P3's `tests/test_routes_stages.py` (out of this package's scope, already
> merged) depend on that dynamic behavior — one exercises an `info`-kind finding, the other
> monkeypatches `_NON_BLOCKING_KINDS` itself and asserts the template follows it. The brief's
> hardcoded `"skipped"`-only check would have silently regressed both. Kept the context-driven
> check; the new `gate_strip.html` is otherwise identical to the brief, **with one further small
> departure the original amendment undersold** (corrected 2026-08-18 at Opus checkpoint B): the
> brief's `<li>` bracket text is the literal `[skipped]`; shipped is `[{{ finding.kind }}]`
> (carried over from the old block). This is correct behavior — an `info`-kind finding should not
> say "skipped" — but it is a third departure from the brief text, not covered by "otherwise
> identical."
>
> Both landed in commit `84b1f55`.
- [ ] Commit: `fix(ui): render gates above the artifact and show a never-ran gate as never-ran`

---

### T10 — Break the unescapable approve loop (E-03)

**Consumes P3** (§7): `has_blocking_gate`, `approval_block_reasons`, `error_banner`
(`{kind, message}`), and the approve POST re-rendering `stage.html` at **409** instead of
returning `PlainTextResponse`.

**Failing test first.** Append to `tests/test_header.py`:

```python
def test_never_ran_gate_page_offers_a_usable_next_action(client_with_stage):
    """THE mandated E-03 test. A gate that never ran must (a) say so and
    (b) leave a way to complete the approval from inside the UI."""
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    _stage_with_artifact(app, project["run_id"], "version: 1\n")   # no gate result recorded

    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert "never ran" in page                                  # (a) it says so
    assert 'name="override_reason"' in page                     # (b) the field exists
    assert 'id="approve-blocked-reason"' in page                # and the reason is inline


def test_a_blocked_approve_re_renders_the_stage_page_not_plain_text(client_with_stage):
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    _stage_with_artifact(app, project["run_id"], "version: 1\n")

    blocked = test_client.post(
        f"/projects/{project_id}/stages/ideation/approve",
        data={"override_reason": ""}, follow_redirects=False,
    )
    assert blocked.status_code == 409
    assert 'class="top-nav"' in blocked.text          # a real page, not a text document
    assert 'class="approval-error"' in blocked.text
    assert "data-error-kind=" in blocked.text         # P3's error_banner.kind
    assert 'name="override_reason"' in blocked.text   # retry without navigating back


def test_a_healthy_stage_approve_form_has_no_override_field(client_with_stage):
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    _stage_with_artifact(app, project["run_id"], "gates:\n  - name: gate-x\n    status: pass\n")
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert 'name="override_reason"' not in page
```

- [ ] Run: fails — `has_failing_gate` is False for a never-ran gate, so no field renders.
- [ ] **Implement.** Replace the approve form in `templates/stage.html` (lines 59–65):

```html
{# `error_banner` is P3's ONE error channel for this page -- gate blocks, stage
   locked, another turn running, edit refusals all arrive here, distinguished by
   `kind`. Before this every one of them was a bare PlainTextResponse: an
   unstyled text document with no header, no nav and no form to retry from
   (E-04, P3's), reached by a POST the operator could only escape with
   browser-back. #}
{% if error_banner %}
<p class="approval-error" role="alert" data-error-kind="{{ error_banner.kind }}">
  {{ error_banner.message }}
</p>
{% endif %}
<form method="post" action="/projects/{{ project.id }}/stages/{{ stage_id }}/approve">
  {% if has_blocking_gate %}
  {# `has_failing_gate` was "any recorded fail/error", strictly narrower than
     what approval_service actually blocks on. A never-ran gate therefore
     rendered a form WITHOUT this field, the POST 409'd into a bare text page,
     and back-navigation returned to the same field-less form -- no way to
     finish the approval from the UI at all (E-03). `has_blocking_gate` is
     computed by the route from the same condition it raises on, so the two
     cannot drift again. #}
  <p id="approve-blocked-reason" class="approve-blocked-reason">
    Approval is blocked:
    {% for reason in approval_block_reasons %}{{ reason }}{% if not loop.last %}; {% endif %}{% endfor %}.
    Fix the findings and regenerate, or record a reason below to approve anyway.
  </p>
  <label for="override_reason">Override reason (required to approve past the block)</label>
  <input type="text" id="override_reason" name="override_reason" required
         placeholder="e.g. dash is inside a verbatim 1886 quote">
  {% endif %}
  <button type="submit">Mark Approved</button>
</form>
```

Add to `static/style.css`:

```css
.approval-error {
  padding: 0.5rem 0.75rem; margin: 0.75rem 0;
  border: 1px solid #ff5f5f; border-radius: 0.25rem;
  background: color-mix(in srgb, #ff5f5f 15%, transparent); color: #ff5f5f;
}
.approve-blocked-reason { color: var(--accent-amber); font-size: 0.9rem; }
```

- [ ] Run: passes.

> **Amendment (2026-08-18, found during T10 execution):** §7's contract table and this task's own
> "Consumes P3" line both claim `approval_block_reasons` was "added by P3 at P15's request" and
> already exists in `routes/stages.py`. It does not — grepped the live repo, zero matches
> anywhere in `pipeline_app/`. This is the inverse of the shape §0 otherwise found for this
> package (drift that pre-satisfies a task): here a claimed-satisfied dependency turned out to be
> unmet. Rather than block T10 on adding it to P3's already-merged `routes/stages.py` (out of
> P15's file scope), the template above derives the same information from `gate_view` — which
> DOES already exist and is P3's one gate classifier, also driving the gate strip above — filtered
> to `blocking` entries: `{% set blocking_gates = gate_view | selectattr("blocking") | list %}`,
> then rendered as `{{ gate.name }} ({{ gate.state.replace("_", " ") }})` per entry, joined with
> `; `. This is a strict improvement over the plan's `approval_block_reasons` binding: the reason
> list and the gate strip now derive from the same classifier and cannot say different things
> about why approval is blocked. §7's table entry for `approval_block_reasons` should be read as
> **not produced by P3**, superseded by this in-template derivation from `gate_view`. Landed in
> commit `41a2e08`. A second, smaller fixture-name correction (the brief's third test used the
> placeholder `gate-x`; changed to the real registered `gate_o_ideation_contract`, same root cause
> as T9's amendment above) landed in the same commit.
- [ ] Commit: `fix(ui): render the override field whenever approval is blocked, including never-ran gates`

---

### T11 — A finished turn says its panels are stale (E-01)

**Failing test first.** Append to `tests/test_header.py`:

```python
def test_stage_page_ships_a_hidden_turn_complete_affordance(client_with_stage):
    test_client, _app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert 'id="turn-complete"' in page
    assert "hidden" in page.split('id="turn-complete"')[1][:200]
    assert "Output and Gates below are from before this turn" in page
    assert 'id="turn-complete-reload"' in page


def test_the_sse_result_branch_reveals_the_affordance(client_with_stage):
    """The result branch used to do nothing but statusLine.remove(), which
    reads as 'the turn produced nothing' (E-01)."""
    test_client, _app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert 'document.getElementById("turn-complete")' in page
    assert "turnComplete.hidden = false" in page
```

- [ ] Run: fails on both.
- [ ] **Implement.** The affordance is **server-rendered** (so it is assertable without a
      browser) and merely revealed by the SSE handler. In `templates/stage.html`, inside the
      chat panel just below `<div id="transcript">…</div>`:

```html
  {# Server-rendered and hidden rather than built in JS, so the affordance is
     assertable from a template test. Before this, a completed turn removed the
     "running…" line and left Output and Gates showing the PREVIOUS state with
     no cue to reload -- the natural read being that the turn produced nothing
     (E-01). #}
  <p id="turn-complete" class="turn-complete" hidden>
    Turn complete. Output and Gates below are from before this turn.
    <button type="button" id="turn-complete-reload">Reload to see the new output</button>
  </p>
```

In `templates/base.html`, replace the `result` branch body (currently just `statusLine.remove();`):

```js
              } else if (event.type === "result" && event.result) {
                // The final assistant text block is byte-identical to
                // event.result on a real recorded turn, so re-rendering it
                // here would show the answer twice. Clear the status line and
                // reveal the (server-rendered, initially hidden) affordance --
                // the Output and Gates panels below are now stale.
                statusLine.remove();
                const turnComplete = document.getElementById("turn-complete");
                if (turnComplete) { turnComplete.hidden = false; }
              }
```

and, inside the `DOMContentLoaded` handler:

```js
      const reloadBtn = document.getElementById("turn-complete-reload");
      if (reloadBtn) {
        reloadBtn.addEventListener("click", () => window.location.reload());
      }
```

Add to `static/style.css`:

```css
.turn-complete {
  margin: 0.5rem 0;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--accent-green);
  border-radius: 0.25rem;
  background: color-mix(in srgb, var(--accent-green) 12%, transparent);
  color: var(--accent-green);
  font-size: 0.9rem;
}
.turn-status { color: var(--accent-amber); font-family: var(--font-mono); }
```

- [ ] Run: passes.
- [ ] Commit: `fix(ui): tell the operator the output panels are stale after a turn completes`

---

### T12 — `completed` and `completed_with_errors` stop looking identical (E-09)

**Failing test first.** Append to `tests/test_header.py`:

```python
def _seed_run(app, status, error_message=None):
    conn = app.state.conn
    conn.execute(
        "INSERT INTO discovery_runs (run_id, trigger, mode, status, started_at) "
        "VALUES (?, 'manual', 'incremental', ?, '2026-08-08T06:00:00+00:00')",
        (f"run-{status}", status),
    )
    run_row_id = conn.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
    conn.execute(
        "INSERT INTO handles (platform, handle, cohort, added_at) "
        "VALUES ('youtube', '@thinkmedia', 'creator-ed', '2026-08-01T00:00:00+00:00')"
    )
    handle_id = conn.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
    conn.execute(
        "INSERT INTO discovery_run_handles (run_id, handle_id, status, items_downloaded, error_message) "
        "VALUES (?, ?, ?, 0, ?)",
        (run_row_id, handle_id, "error" if error_message else "ok", error_message),
    )
    conn.commit()
    return run_row_id


def test_terminal_run_states_are_visually_distinguishable(client: TestClient):
    app = client.app
    _seed_run(app, "completed")
    _seed_run(app, "completed_with_errors", error_message="HTTP 403 from the API")
    page = client.get("/discovery/runs").text
    assert "status-completed_with_errors" in page
    assert "status-completed" in page

    css = (Path(__import__("pipeline_app.main", fromlist=["x"]).PACKAGE_DIR)
           / "static" / "style.css").read_text(encoding="utf-8")
    for modifier in (".status-completed_with_errors",
                     ".status-completed",
                     ".status-failed",
                     ".status-queued"):
        assert modifier in css, f"{modifier} pill has no styling -- it renders as a bare pill"


def test_a_run_with_errors_carries_an_error_count_on_its_line(client: TestClient):
    _seed_run(client.app, "completed_with_errors", error_message="HTTP 403 from the API")
    page = client.get("/discovery/runs").text
    assert "1 handle error" in page
```

- [ ] Run: fails — no modifiers exist and there is no count.
- [ ] **Implement.** Add to `static/style.css` (extending the existing pill primitive, per the
      audit's Q8 verdict that the system is sound and only its coverage is not):

```css
/* Discovery run + handle states. Before this every one of them fell through to
   the unstyled base .status pill, so "did last night's run go cleanly?" -- the
   entire purpose of the runs page -- was unanswerable at a glance (E-09). */
.status-queued { background: color-mix(in srgb, var(--text-dim) 20%, transparent); color: var(--text-dim); border-color: var(--border); }
.status-completed { background: color-mix(in srgb, var(--accent-green) 20%, transparent); color: var(--accent-green); border-color: var(--accent-green); }
.status-completed_with_errors { background: color-mix(in srgb, var(--accent-amber) 25%, transparent); color: var(--accent-amber); border-color: var(--accent-amber); }
.status-failed { background: color-mix(in srgb, #ff5f5f 25%, transparent); color: #ff5f5f; border-color: #ff5f5f; }
.status-ok { background: color-mix(in srgb, var(--accent-green) 20%, transparent); color: var(--accent-green); border-color: var(--accent-green); }
```

In `templates/discovery_runs.html`, add the count on the run line:

```html
    {% set errored = entry.handle_results | selectattr('status', 'equalto', 'error') | list %}
    {% if errored %}
    <span class="status status-failed">{{ errored | length }} handle error{{ "s" if errored | length != 1 }}</span>
    {% endif %}
```

- [ ] Run: passes.

> **Amendment (2026-08-18, found during T12 execution):** the brief's `_seed_run` helper inserts a
> handle with a hardcoded name (`'@thinkmedia'`) and no per-call uniqueness. `handles` carries a
> `UNIQUE (platform, handle)` constraint (frozen interface, P1/`schema.sql`), and
> `test_terminal_run_states_are_visually_distinguishable` calls `_seed_run` twice in the same
> test (once per status) — the second call's insert would violate the constraint as written.
> Fixed by suffixing the handle name with the status (`f"@thinkmedia-{status}"`), keeping every
> other column unchanged. **T13 (next) also shows its own copy of `_seed_run` in its brief text
> with the same bug** — when dispatching T13, do not paste that duplicate definition over this
> already-fixed one; reuse the fixed helper already in `tests/test_header.py`. Landed in commit
> `1750228`.
- [ ] Commit: `fix(ui): give discovery run states real pill styling and an error count`

---

### T13 — Name the handle that broke (E-10)

**Consumes P8** (§7): `discovery_runs_page` joins `handles`, so each `handle_results` row
carries `platform`, `handle` and `display_name` alongside the existing columns. Until it does,
the template must not lie — it says so.

**Failing test first.** Append to `tests/test_header.py`:

```python
def test_a_failed_handle_is_named_not_numbered(client: TestClient):
    _seed_run(client.app, "completed_with_errors", error_message="HTTP 403 from the API")
    page = client.get("/discovery/runs").text
    assert "youtube/@thinkmedia" in page
    assert "handle #" not in page, "a bare row id is not an answer to 'which source broke?'"
    assert "HTTP 403 from the API" in page


def test_errored_handle_results_are_listed_before_healthy_ones(client: TestClient):
    app = client.app
    run_row_id = _seed_run(app, "completed_with_errors", error_message="HTTP 403 from the API")
    app.state.conn.execute(
        "INSERT INTO handles (platform, handle, cohort, added_at) "
        "VALUES ('bluesky', 'ok.bsky.social', 'creator-ed', '2026-08-01T00:00:00+00:00')"
    )
    ok_id = app.state.conn.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
    app.state.conn.execute(
        "INSERT INTO discovery_run_handles (run_id, handle_id, status, items_downloaded) "
        "VALUES (?, ?, 'ok', 4)", (run_row_id, ok_id),
    )
    app.state.conn.commit()
    page = client.get("/discovery/runs").text
    assert page.index("@thinkmedia") < page.index("ok.bsky.social")
```

- [ ] Run: fails — the template renders `handle #{{ hr.handle_id }}`.
- [ ] **Implement.** Rewrite the inner list in `templates/discovery_runs.html`:

```html
    {# `handle #7: error` attached the only failure signal on the page to an
       anonymous database id -- answering "which source broke?" meant opening
       pipeline.db by hand (E-10). Errored results sort first so the answer is
       at the top of the run, not buried in it. #}
    {% set ordered = (entry.handle_results | selectattr('status', 'equalto', 'error') | list)
                   + (entry.handle_results | rejectattr('status', 'equalto', 'error') | list) %}
    <details {% if errored %}open{% endif %}>
      <summary>{{ ordered | length }} handle result{{ "s" if ordered | length != 1 }}</summary>
      <ul>
        {% for hr in ordered %}
        <li>
          <span class="status status-{{ hr.status }}">{{ hr.status }}</span>
          {% if hr.platform is defined and hr.platform %}
          <code>{{ hr.platform }}/{{ hr.handle }}</code>{% if hr.display_name %} ({{ hr.display_name }}){% endif %}
          {% else %}
          <code>unresolved handle id {{ hr.handle_id }}</code>
          <span class="browse-error">— the run row could not be joined to a handle</span>
          {% endif %}
          — {{ hr.items_downloaded }} item{{ "s" if hr.items_downloaded != 1 }}
          {% if hr.error_message %}<div class="gate-finding-blocking">{{ hr.error_message }}</div>{% endif %}
        </li>
        {% endfor %}
      </ul>
    </details>
```

The `<details>` wrapper is also the render-side bound on this page: `db.list_runs` has no
`LIMIT` and the route joins nothing, so today every run ever plus every per-handle result is
laid out flat on each load. Collapsing per-run results keeps the page readable while the real
pagination — `db.list_runs(conn, limit=…)` (**P1**) plumbed through `discovery_runs_page`
(**P8**) — lands separately. Add a rendered note so the truncation is never invisible:

```html
{% if runs_with_results | length >= 50 %}
<p class="browse-placeholder">Showing every run on record. Pagination is not implemented yet.</p>
{% endif %}
```

- [ ] Run: passes (the `unresolved handle id` branch is what renders until P8 lands the join;
      the first test therefore stays red until then — that is the correct TDD ordering, and
      the branch guarantees the page never silently shows a wrong name).

> **Amendment (2026-08-18, found during T13 execution):** "the first test therefore stays red
> until then" undersold it — empirically **both** new tests fail until P8 lands the join, not
> just the first. `db.list_run_handle_results` (`SELECT * FROM discovery_run_handles WHERE
> run_id = ?`, no join) means every `hr` in `entry.handle_results` lacks a `platform` attribute,
> so `hr.platform is defined` is `False` for every row, and the ordering test's
> `page.index("@thinkmedia")` never finds the substring either — same root cause, not an
> implementation mistake (verified with a throwaway Jinja probe against a real `sqlite3.Row`
> missing the column).
>
> More importantly: a literally red, checked-in test contradicts this programme's own "both
> suites are fully green with no documented exceptions" definition of done — the plan's "stays
> red" phrasing was never reconciled with that constraint. The repo already has an established
> precedent for exactly this shape (a test blocked on a column/join a later task adds):
> `tests/test_db.py::test_handles_creator_id_is_covered_by_an_index`'s own docstring documents
> carrying `xfail(strict=True)` through two prior tasks until the dependency landed, specifically
> to avoid "the suite is red but we know why" becoming how a real regression gets waved through.
> Both new tests are marked `@pytest.mark.xfail(strict=True, reason=...)`, reason naming P8 and
> instructing marker removal once the join lands — `strict=True` means an unexpected pass (i.e.
> P8 landing without the marker being removed) fails the suite immediately, so this cannot rot
> silently. Landed in commit `c1a4184`. **Handoff note for whoever lands P8:** remove both xfail
> markers in `tests/test_header.py` once `discovery_runs_page` joins `handles`.
- [ ] Commit: `fix(ui): identify failed discovery handles by platform and handle`

---

### T14 — Handle states, failure reasons, and a poller that cannot stall (E-12)

**Failing test first.** Append to `tests/test_header.py`:

```python
def test_handle_states_have_distinct_pill_styling(client: TestClient):
    from pipeline_app.main import PACKAGE_DIR
    css = (PACKAGE_DIR / "static" / "style.css").read_text(encoding="utf-8")
    for modifier in (".status-pending", ".status-validating", ".status-validated", ".status-invalid"):
        assert modifier in css


def test_an_invalid_handle_states_a_reason_or_says_none_was_recorded(client: TestClient):
    conn = client.app.state.conn
    conn.execute(
        "INSERT INTO handles (platform, handle, cohort, status, added_at) "
        "VALUES ('youtube', '@gone', 'creator-ed', 'invalid', '2026-08-01T00:00:00+00:00')"
    )
    conn.commit()
    page = client.get("/discovery/handles").text
    assert "status status-invalid" in page
    # No error column exists on `handles` yet, so the honest render is to say
    # so -- never to show a bare word with no recourse.
    assert "no reason recorded" in page


def test_the_status_poller_stops_and_reports_when_a_fetch_fails(client: TestClient):
    page = client.get("/discovery/handles").text
    assert "res.ok" in page
    assert "catch" in page
    assert "status unknown — reload" in page
    assert "clearInterval(poll)" in page
```

- [ ] Run: fails on all three.
- [ ] **Implement.** Add to `static/style.css`:

```css
.status-pending { background: color-mix(in srgb, var(--text-dim) 20%, transparent); color: var(--text-dim); border-color: var(--border); }
.status-validating { background: color-mix(in srgb, var(--accent-amber) 25%, transparent); color: var(--accent-amber); border-color: var(--accent-amber); }
.status-validated { background: color-mix(in srgb, var(--accent-green) 20%, transparent); color: var(--accent-green); border-color: var(--accent-green); }
.status-invalid { background: color-mix(in srgb, #ff5f5f 25%, transparent); color: #ff5f5f; border-color: #ff5f5f; }
```

In `templates/discovery_handles.html`, give the pill its modifier and state the reason:

```html
      <td>
        <span class="status status-{{ h.status }}" data-handle-status="{{ h.id }}">{{ h.status }}</span>
        {% if h.status == "invalid" %}
        {# `handles` has no error column, so an invalid handle could never say
           WHY -- the operator saw a word and had no recourse (E-12). Persisting
           a reason is P8/P1 territory; saying out loud that none was recorded is
           this package's half, and it is strictly better than silence. #}
        <div class="gate-finding-blocking">
          {{ h.error_message if h.error_message is defined and h.error_message else "no reason recorded" }}
        </div>
        {% endif %}
      </td>
```

Add `id="schedule"` to the schedule heading (the T4 tab anchor target):

```html
<h2 id="schedule">Schedule</h2>
```

Replace the inline poller entirely:

```html
<script>
  // The old loop had no res.ok check and no try/catch: one failed fetch left
  // an unhandled rejection inside setInterval, the interval was never cleared,
  // and the row said "pending" forever with nothing surfaced (E-12).
  document.querySelectorAll("[data-handle-status]").forEach((el) => {
    const status = el.textContent.trim();
    if (status !== "pending" && status !== "validating") return;
    const handleId = el.dataset.handleStatus;
    let failures = 0;
    const stall = (message) => {
      clearInterval(poll);
      el.textContent = message;
      el.className = "status status-invalid";
    };
    const poll = setInterval(async () => {
      try {
        const res = await fetch(`/discovery/handles/${handleId}/status`);
        if (!res.ok) {
          stall(`status unknown — reload (HTTP ${res.status})`);
          return;
        }
        const data = await res.json();
        if (data.status !== "pending" && data.status !== "validating") {
          clearInterval(poll);
          window.location.reload();
        }
      } catch (err) {
        failures += 1;
        if (failures >= 3) {
          stall("status unknown — reload (app unreachable)");
        }
      }
    }, 3000);
  });
</script>
```

- [ ] Run: passes.
- [ ] Commit: `fix(ui): style handle states, state the invalid reason, and stop the stalling poller`

---

### T15 — Pin the platform picker to the adapter registry (B-74)

The audit offers two fixes; the registry-in-context one needs `routes/discovery.py` (P8). The
test-pin is fully inside this package and is the one that actually makes the drift *loud*.

**Failing test first.** Append to `tests/test_header.py`:

```python
def test_platform_options_match_the_adapter_registry_exactly():
    """The seven <option> values are the only enumeration of trackable
    platforms an operator ever sees, hand-duplicated from build_adapters().
    They agree today and nothing enforced it: a new adapter was silently
    untrackable through the only supported entry point (B-74)."""
    import re
    from pipeline_app.main import PACKAGE_DIR
    from run_discovery_cron import build_adapters

    html = (PACKAGE_DIR / "templates" / "discovery_handles.html").read_text(encoding="utf-8")
    select = re.search(r'<select name="platform">(.*?)</select>', html, re.S).group(1)
    options = set(re.findall(r'<option value="([^"]+)"', select))
    assert options == set(build_adapters().keys())
```

`run_discovery_cron` sits at `pipeline-app/`, which is already the app suite's rootdir, so the
import resolves without a path hack. If it does not, import it by file path with
`importlib.util.spec_from_file_location` — never by mutating `sys.path` in a test.

- [ ] Run: it **passes immediately** against today's code (the two lists agree). That is not a
      TDD violation — it is a *pinning* test, and the required proof is the inverse. Prove it
      fails when it should: temporarily add `"tiktok": None` to `build_adapters()`, run, see
      the test fail naming `tiktok`, then revert.
- [ ] Record that manual falsification in the commit body.
- [ ] Commit: `test(ui): pin the platform picker options to build_adapters()`

---

> **Amendment (2026-08-18, found at Opus checkpoint B after T8-T15 landed):** three findings,
> resolved in one consolidated fix commit before continuing to T16.
>
> 1. **Important — `gate.name` fallback dropped; the page can render the literal `None`.** The
> pre-T9 inline block read `{{ gate.name or "unknown gate" }}`; T9's `partials/gate_strip.html`
> (and this task's own blocking-reason loop in `stage.html`) dropped the guard — the plan's own
> shown markup for both never carried it either, same recurring bug class as everywhere else in
> this package. `approval_service.classify_gates` uses `g.get("name")`, so any recorded gate
> entry without a `name` key (the malformed-gates case P3's own test exercises, and any future
> caller) renders the Python string `None` directly into operator-facing copy — exactly the
> silent-degradation class this package exists to remove. Fixed: restored `{{ gate.name or
> "unknown gate" }}` in both `gate_strip.html` and `stage.html`'s reason loop; added a
> `.status-malformed` CSS rule (amber, alongside `never_ran`/`unknown` — "we cannot tell", not a
> pass and not a hard fail) since it had none before; added a `"None:" not in page.text`
> assertion to the malformed-gates test so this can't regress silently again.
> 2. **Important — T10's `error-banner` → `approval-error` class rename hollowed out three P3
> tests.** `tests/test_routes_stages.py:1025,1040,1057` (P3's file, already merged, same
> cross-package-ripple authorization as T8's) assert `"error-banner" in resp.text`. T10 renamed
> the stage-page banner's class, but `base.html` unconditionally renders `id="htmx-error-banner"`
> on every page, so the substring `"error-banner"` still matches — the three tests kept passing
> while no longer verifying the banner they were written to pin (blocked-approve 409, locked-stage
> edit 409, grounding edit refusal). Fixed: updated all three assertions to
> `'class="approval-error"' in resp.text`.
> 3. **Important — the P8 handoff for T13's two `xfail(strict=True)` markers was not routed where
> P8 will look.** The `xfail(strict=True)` mechanism itself is airtight (an unexpected pass fails
> the suite immediately), but `docs/superpowers/plans/remediation/P8-engine-cron.md`'s "Open
> handoffs → P15" section listed `health`/`pending_spawns`/`.status-*`/`consecutive_failures` and
> said nothing about the `handles` join or the two markers to remove — the discoverable spot P1's
> own equivalent handoff used. Fixed: added a line to that section naming the join and the two
> markers in `tests/test_header.py`. Also corrected this plan's own §7 P8 row, which still read
> "the first test stays red" (T13's own amendment already established both tests block, and
> neither is checked in red — both are `xfail(strict=True)`).
>
> Two Minor doc-accuracy slips also corrected in the same pass: T8's amendment overstated the
> `status-` occurrence count (said 5→7, measured 4→6 — conclusion and `< 9` threshold unaffected);
> T9's amendment claimed `gate_strip.html` was "otherwise identical to the brief" when a third,
> correct-but-undisclosed departure (`[{{ finding.kind }}]` instead of the brief's literal
> `[skipped]`) also shipped — noted inline at T9 instead of left solely in the ledger.

### T16 — Browse: an unreadable folder is unreadable, not absent (E-14a)

**Failing tests first** (all three Three-Test-Rule roles). Append to `tests/test_browse_service.py`:

```python
def test_md_below_state_reports_unreadable_not_empty(root, tmp_path, monkeypatch):
    """FAULT. _has_md_below returned False on OSError, and list_children used
    it as the include test -- so an unreadable folder was omitted from its
    parent's listing entirely and the operator saw a shorter tree (E-14a)."""
    subfolder = root / "sub"
    subfolder.mkdir()
    _touch(subfolder / "note.md")

    real_scandir = os.scandir

    def _raise_for_subfolder(path, *args, **kwargs):
        if Path(path) == subfolder:
            raise OSError("permission denied")
        return real_scandir(path, *args, **kwargs)

    monkeypatch.setattr(os, "scandir", _raise_for_subfolder)
    assert browse_service._md_below_state(subfolder, tmp_path) == "unreadable"


def test_unreadable_folder_is_distinguishable_from_an_empty_one(root, tmp_path, monkeypatch):
    """DISTINGUISHABILITY."""
    empty = root / "genuinely_empty"
    (empty / "notes").mkdir(parents=True)
    unreadable = root / "unreadable"
    unreadable.mkdir()

    real_scandir = os.scandir

    def _raise_for_unreadable(path, *args, **kwargs):
        if Path(path) == unreadable:
            raise OSError("permission denied")
        return real_scandir(path, *args, **kwargs)

    monkeypatch.setattr(os, "scandir", _raise_for_unreadable)
    assert browse_service._md_below_state(empty, tmp_path) == "empty"
    assert browse_service._md_below_state(unreadable, tmp_path) == "unreadable"

    names = {e.name: e for e in browse_service.list_children(root, root, tmp_path)}
    assert "genuinely_empty" not in names          # no content: correctly hidden
    assert "unreadable" in names                   # broken: shown, and marked
    assert names["unreadable"].unreadable is True
```

and in `tests/test_routes_browse.py` (surfacing):

```python
def test_unreadable_folder_renders_as_a_disabled_row_with_a_reason(client, monkeypatch):
    """SURFACING."""
    test_client, tmp_path = client
    import os as _os
    unreadable = tmp_path / "output" / "locked"
    unreadable.mkdir()
    real_scandir = _os.scandir

    def _raise_for_locked(path, *args, **kwargs):
        if Path(path) == unreadable:
            raise OSError("permission denied")
        return real_scandir(path, *args, **kwargs)

    monkeypatch.setattr(_os, "scandir", _raise_for_locked)
    resp = test_client.get("/browse")
    assert "locked" in resp.text
    assert "browse-unreadable" in resp.text
    assert "could not be read" in resp.text
```

- [ ] Run: fails — `_md_below_state` does not exist and `Entry` has no `unreadable` field.
- [ ] **Implement** in `browse_service.py`. Replace `_has_md_below`:

```python
def _md_below_state(folder: Path, repo_root: Path) -> str:
    """One of "content", "empty", "unreadable".

    The tri-state is the whole point. The old boolean returned False for both
    "nothing to show here" and "I could not look", and list_children used it as
    the include test -- so a permission-denied folder was not rendered as
    unreadable, it vanished from its parent's listing and the operator saw a
    shorter tree with no error anywhere (E-14a)."""
    try:
        with os.scandir(folder) as it:
            for entry in it:
                if entry.is_symlink():
                    continue
                if entry.is_file() and entry.name == "raw_output.md":
                    # Must agree with list_children's exclusion below.
                    continue
                if entry.is_file() and _is_md_name(entry.name):
                    return "content"
                if entry.is_file() and entry.name == "pointer.yaml":
                    target, error = resolve_grounding_pointer_state(folder, repo_root)
                    if target is not None or error is not None:
                        # A BROKEN pointer is content too: it must be listed so
                        # the operator can click it and read the reason (E-14b).
                        return "content"
                if entry.is_dir():
                    below = _md_below_state(Path(entry.path), repo_root)
                    if below in ("content", "unreadable"):
                        return below
    except OSError:
        return "unreadable"
    return "empty"
```

Extend `Entry` (the two new fields default False/None so every existing construction is
unchanged):

```python
@dataclass(frozen=True)
class Entry:
    name: str
    rel_path: str
    is_dir: bool
    unreadable: bool = False
    broken_reason: str | None = None
```

In `list_children`, replace the `if _has_md_below(path, repo_root):` include test:

```python
                if entry.is_dir():
                    state = _md_below_state(path, repo_root)
                    if state == "content":
                        dirs.append(Entry(name=entry.name, rel_path=rel_path, is_dir=True))
                    elif state == "unreadable":
                        dirs.append(Entry(
                            name=entry.name, rel_path=rel_path, is_dir=True,
                            unreadable=True,
                            broken_reason="this folder could not be read (permission denied, or it changed during the scan)",
                        ))
```

In `templates/partials/browse_tree_items.html`, render the disabled row:

```html
    {% if entry.unreadable %}
    <div class="browse-unreadable">
      {{ entry.name }} — {{ entry.broken_reason }}
    </div>
    {% elif entry.is_dir %}
```

Add to `static/style.css`:

```css
.browse-unreadable { margin-left: 0.25rem; color: #ff5f5f; font-style: italic; cursor: not-allowed; }
.browse-broken { margin-left: 1.25rem; color: #ff5f5f; font-style: italic; }
```

- [ ] Run: passes. Update the four remaining `_has_md_below` callers in
      `tests/test_browse_service.py` per §5.

> **Amendment (2026-08-18, found during T16 execution):** two departures from this task's literal
> text.
>
> 1. **Forward reference to T17.** The `_md_below_state` sample above calls
> `resolve_grounding_pointer_state(folder, repo_root)` — a function T17 (next) introduces; it does
> not exist yet at T16. Implemented instead: the `pointer.yaml` branch calls the already-existing
> `grounding_service.read_pointer(folder)` directly (catching `InvalidPointerError`), and treats
> any syntactically-valid, non-empty `rgs_brief_path` as `"content"` regardless of whether the
> target file currently exists on disk — reproducing exactly the tri-state distinctions this
> task's own tests require without introducing T17's not-yet-specified error-detail plumbing.
> **When dispatching T17: `_md_below_state`'s `pointer.yaml` branch (in `browse_service.py`) may
> be worth revisiting to call the new `resolve_grounding_pointer_state` for consistency once it
> exists** (not required — the current logic is already correct for `_md_below_state`'s own
> tri-state contract, which only needs "is there content", not the reason for a break — but T17's
> implementer should be aware of this branch's existence before assuming `_md_below_state` is
> untouched by T17).
> 2. **Five `_has_md_below` callers found, not four, plus the OSError one already covered by this
> task's own new tests (six total).** Handled: the OSError-scenario test
> (`test_has_md_below_scandir_oserror_returns_false`) was **deleted**, not renamed — it asserted
> the old (now-wrong) behavior `list_children(...) == []` for a permission-denied folder, fully
> superseded by this task's own new tests. Four other callers were renamed with `is True`/`is
> False` → `== "content"`/`== "empty"` as the count/status implied; one was **inverted** per §5
> (`test_has_md_below_false_when_pointer_target_missing` → `test_md_below_state_counts_a_broken_
> pointer_as_content`, `== "content"`); a sixth, un-named caller inside
> `test_resolve_grounding_pointer_returns_none_when_pointer_not_a_mapping` was also updated
> (renamed call, `== "empty"`, not inverted — malformed YAML stays empty, only a valid pointer
> with a missing target counts as broken content).
>
> Both landed in commit `452e433`.
- [ ] Commit: `fix(browse): show an unreadable folder as unreadable instead of omitting it`

---

### T17 — Browse: a malformed `pointer.yaml` is visible and clickable (E-14b)

**Failing tests first.** Append to `tests/test_browse_service.py`:

```python
def test_pointer_state_reports_malformed_yaml_as_an_error(tmp_path):
    """FAULT."""
    pointer_dir = tmp_path / "runs" / "my-run" / "00-grounding"
    pointer_dir.mkdir(parents=True)
    (pointer_dir / "pointer.yaml").write_text("brief_path: [unclosed\n", encoding="utf-8")
    target, error = browse_service.resolve_grounding_pointer_state(pointer_dir, tmp_path)
    assert target is None
    assert error is not None and "could not be parsed" in error


def test_malformed_pointer_is_distinguishable_from_no_pointer(tmp_path):
    """DISTINGUISHABILITY. Both used to return a bare None."""
    no_pointer = tmp_path / "runs" / "a" / "00-grounding"
    no_pointer.mkdir(parents=True)
    broken = tmp_path / "runs" / "b" / "00-grounding"
    broken.mkdir(parents=True)
    (broken / "pointer.yaml").write_text("brief_path: [unclosed\n", encoding="utf-8")

    assert browse_service.resolve_grounding_pointer_state(no_pointer, tmp_path) == (None, None)
    assert browse_service.resolve_grounding_pointer_state(broken, tmp_path)[1] is not None


def test_list_children_lists_a_broken_pointer_instead_of_skipping_it(root, tmp_path):
    grounding_dir = root / "00-grounding"
    grounding_dir.mkdir(parents=True)
    (grounding_dir / "pointer.yaml").write_text("brief_path: [unclosed\n", encoding="utf-8")
    entries = browse_service.list_children(grounding_dir, root, tmp_path)
    assert [e.name for e in entries] == ["pointer.yaml (unresolvable)"]
    assert entries[0].broken_reason is not None
```

and in `tests/test_routes_browse.py` (surfacing):

```python
def test_broken_grounding_pointer_stays_reachable_through_the_tree(client):
    """SURFACING. The route's 'Grounding pointer could not be resolved.'
    message was unreachable: list_children skipped the entry, so there was
    nothing left to click (E-14b)."""
    test_client, tmp_path = client
    grounding = tmp_path / "runs" / "my-run-20260728-120000" / "00-grounding"
    grounding.mkdir(parents=True)
    (grounding / "pointer.yaml").write_text("brief_path: [unclosed\n", encoding="utf-8")

    project = test_client.get(
        "/browse/tree", params={"root": "pipeline", "path": "my-run-20260728-120000"}
    )
    assert "00-grounding" in project.text            # the folder did not vanish

    stage = test_client.get(
        "/browse/tree",
        params={"root": "pipeline", "path": "my-run-20260728-120000/00-grounding"},
    )
    assert "unresolvable" in stage.text
    assert "browse-broken" in stage.text
```

- [ ] Run: fails — `resolve_grounding_pointer_state` does not exist.
- [ ] **Implement** in `browse_service.py`:

```python
def resolve_grounding_pointer_state(pointer_dir: Path, repo_root: Path) -> tuple[Path | None, str | None]:
    """Return (target, error). Exactly one is non-None, or both are None when
    there is simply no pointer here.

    The old single-return-value form collapsed "no pointer" and "the pointer is
    broken" into the same bare None, so a hand-edited or truncated pointer.yaml
    was invisible: list_children skipped the entry and its folder could vanish
    with it (E-14b). pointer.yaml's content comes off disk rather than from the
    request, so its target is still a trust boundary and keeps its explicit
    containment check against the real rgs-briefs/ folder."""
    if not (pointer_dir / "pointer.yaml").is_file():
        return None, None
    try:
        target_rel = grounding_service.read_pointer(pointer_dir)
    except (yaml.YAMLError, AttributeError, TypeError) as exc:
        return None, f"pointer.yaml could not be parsed: {type(exc).__name__}: {exc}"
    if not target_rel:
        return None, "pointer.yaml records no brief path."
    rgs_briefs_root = (repo_root / "rgs-briefs").resolve()
    target = (repo_root / target_rel).resolve()
    if not target.is_relative_to(rgs_briefs_root):
        return None, f"pointer.yaml points outside rgs-briefs/: {target_rel}"
    if not target.exists():
        return None, f"pointer.yaml points at a file that does not exist: {target_rel}"
    return target, None


def resolve_grounding_pointer(pointer_dir: Path, repo_root: Path) -> Path | None:
    """Back-compat wrapper: target or None. Callers that need to tell a broken
    pointer from an absent one must use resolve_grounding_pointer_state."""
    return resolve_grounding_pointer_state(pointer_dir, repo_root)[0]
```

In `list_children`, replace the `pointer.yaml` branch:

```python
                    elif entry.name == "pointer.yaml":
                        target, error = resolve_grounding_pointer_state(folder, repo_root)
                        if target is not None:
                            files.append(Entry(
                                name=f"current-brief.md ({target.name})",
                                rel_path=rel_path, is_dir=False,
                            ))
                        elif error is not None:
                            files.append(Entry(
                                name="pointer.yaml (unresolvable)",
                                rel_path=rel_path, is_dir=False,
                                broken_reason=error,
                            ))
```

In `routes/browse.py`, make the file view report the actual reason instead of a generic line:

```python
        elif file_path.name == "pointer.yaml":
            target, pointer_error = browse_service.resolve_grounding_pointer_state(
                file_path.parent, repo_root
            )
            if target is None:
                context = {"error": pointer_error or "Grounding pointer could not be resolved."}
            else:
                context = browse_service.render_md_file(target)
```

In `templates/partials/browse_tree_items.html`, the file branch:

```html
    {% elif entry.broken_reason %}
    <div class="browse-broken" title="{{ entry.broken_reason }}">
      <a href="#"
         hx-get="/browse/file?path={{ entry.rel_path | urlencode }}&root={{ root }}"
         hx-target="#browse-doc" hx-swap="innerHTML"
         hx-sync="#browse-doc:replace"
         hx-indicator="#browse-spinner">{{ entry.name }}</a>
      — {{ entry.broken_reason }}
    </div>
    {% else %}
```

- [ ] Run: passes.
- [ ] Commit: `fix(browse): list a broken grounding pointer instead of silently skipping it`

---

### T18 — Browse: a root that resolves to zero entries says so (E-14c)

**Failing test first.** Append to `tests/test_routes_browse.py`:

```python
def test_an_empty_root_renders_an_explicit_empty_line_not_blank_space(client):
    test_client, tmp_path = client
    # output/ exists (the fixture makes it) and contains nothing at all.
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert "Nothing to show here yet." in resp.text


def test_an_empty_root_is_distinguishable_from_an_unreadable_one(client, monkeypatch):
    test_client, tmp_path = client
    empty_page = test_client.get("/browse").text

    import os as _os
    def _raise(*args, **kwargs):
        raise OSError("permission denied")
    monkeypatch.setattr(_os, "scandir", _raise)
    broken_page = test_client.get("/browse").text

    assert empty_page != broken_page
    assert "Nothing to show here yet." in empty_page
    assert "Could not read folder:" in broken_page
```

- [ ] Run: the first fails — `_folder_context` returns `{"entries": []}`, the partial falls
      through to a for-loop over nothing, and the heading is followed by blank space.
- [ ] **Implement** in `routes/browse.py`. Add one helper and route both `entries` returns
      through it:

```python
def _entries_context(entries: list) -> dict:
    # {"entries": []} rendered as literal blank space under the heading, which
    # reads as a broken page rather than an empty folder (E-14c).
    if not entries:
        return {"entries": [], "empty_message": "Nothing to show here yet."}
    return {"entries": entries}
```

Use it at both `return {"entries": …}` sites (`is_pipeline_top` and the general branch).

- [ ] Run: passes.
- [ ] Commit: `fix(browse): render an explicit empty state instead of blank space`

---

### T19 — Sanitize rendered markdown at the Browse producer (D-47)

Calibrated honestly: this is an unauthenticated single-user localhost app, so the real blast
radius is **stored third-party content executing script in the operator's browser with
same-origin access to the app's own mutating routes** — skill-file rewrites, git commits,
billed Bright Data runs. Worth closing; not a data-breach path. Neither `nh3` nor `bleach` is
installed and `requirements.txt` belongs to P0, so this is a stdlib allowlist filter — which
also keeps the "local only" rule intact.

**Failing tests first.** Append to `tests/test_browse_service.py`:

```python
import pytest


@pytest.mark.parametrize(
    "dangerous,must_not_contain",
    [
        ("<script>alert(1)</script>", "<script"),
        ('<img src=x onerror="alert(1)">', "onerror"),
        ('<a href="javascript:alert(1)">x</a>', "javascript:"),
        ('<iframe src="http://evil"></iframe>', "<iframe"),
        ('<div onclick="alert(1)">x</div>', "onclick"),
    ],
)
def test_sanitize_html_strips_script_vectors(dangerous, must_not_contain):
    out = browse_service.sanitize_html(dangerous)
    assert must_not_contain not in out


def test_sanitize_html_keeps_ordinary_markdown_output():
    out = browse_service.sanitize_html(
        '<h1>Title</h1><p><strong>bold</strong> <a href="https://example.com">link</a></p>'
        "<table><tr><td>cell</td></tr></table><pre><code>x = 1</code></pre>"
    )
    for keep in ("<h1>", "<strong>", 'href="https://example.com"', "<table>", "<code>"):
        assert keep in out


def test_render_md_file_body_html_is_sanitized(tmp_path):
    path = tmp_path / "post.md"
    path.write_text(
        "---\nurl: https://example.com\n---\n\n"
        "A captured post.\n\n<script>fetch('/discovery/run-now', {method:'POST'})</script>\n",
        encoding="utf-8",
    )
    result = browse_service.render_md_file(path)
    assert "A captured post." in result["body_html"]
    assert "<script" not in result["body_html"]
    assert "discovery/run-now" not in result["body_html"]
```

- [ ] Run: fails — `sanitize_html` does not exist and `markdown.markdown()` passes HTML through
      verbatim (Python-Markdown 3.7 performs no sanitization).
- [ ] **Implement** in `browse_service.py`:

```python
from html.parser import HTMLParser
from html import escape as _html_escape

# Python-Markdown performs no sanitization: <script>, onerror= and
# javascript: hrefs all survive it verbatim. The discovery cron writes
# third-party post bodies straight to disk as markdown and /browse renders
# exactly those files, so anything executing here has same-origin authority
# over every unauthenticated mutating route in the app (D-47). Sanitizing at
# the PRODUCER keeps the templates' `| safe` honest and covers any future
# render site; sanitizing per-template does not. Allowlist, not blocklist --
# a blocklist of dangerous tags is a list you will always be behind on.
_ALLOWED_TAGS = {
    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "em", "b", "i", "u", "s", "code", "pre", "blockquote",
    "ul", "ol", "li", "dl", "dt", "dd",
    "table", "thead", "tbody", "tr", "th", "td",
    "a", "img", "span", "div",
}
_ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "th": {"align"}, "td": {"align"},
}
_VOID_TAGS = {"br", "hr", "img"}
_DANGEROUS_SCHEMES = ("javascript:", "data:", "vbscript:")


def _safe_url(value: str | None) -> str | None:
    """Drop a URL whose scheme can execute. Whitespace inside the scheme is
    stripped first -- `java\\tscript:alert(1)` is a real browser-accepted form
    and a naive startswith() misses it."""
    if value is None:
        return None
    candidate = value.strip()
    lowered = "".join(candidate.lower().split())
    if lowered.startswith(_DANGEROUS_SCHEMES):
        return None
    return candidate


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in _ALLOWED_TAGS:
            return
        kept = []
        for name, value in attrs:
            # Every on* handler is dropped by the allowlist below anyway; the
            # allowlist is per-tag so no attribute survives by accident.
            if name not in _ALLOWED_ATTRS.get(tag, set()):
                continue
            if name in ("href", "src"):
                value = _safe_url(value)
                if value is None:
                    continue
            kept.append(f' {name}="{_html_escape(value or "", quote=True)}"')
        slash = " /" if tag in _VOID_TAGS else ""
        self.out.append(f"<{tag}{''.join(kept)}{slash}>")

    def handle_endtag(self, tag):
        if tag in _ALLOWED_TAGS and tag not in _VOID_TAGS:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        self.out.append(_html_escape(data, quote=False))


def sanitize_html(html: str) -> str:
    """Allowlist-filter rendered markdown HTML. Published for P3 (routes/
    stages.py) and P5 (routes/inspector.py) to adopt at their own producer
    sites -- the `| safe` filters in stage.html and inspector.html are only
    honest once every producer feeding them runs through here."""
    parser = _Sanitizer()
    parser.feed(html)
    parser.close()
    return "".join(parser.out)
```

and in `render_md_file`:

```python
        "body_html": sanitize_html(markdown.markdown(body, extensions=["tables"])),
```

**Published, not consumed:** `browse_service.sanitize_html`. P3 wraps `routes/stages.py:78,94,102`
and P5 wraps `routes/inspector.py:45` with it; those two call sites are the remaining `| safe`
render paths and are out of this package's file list.

- [ ] Run: passes. Re-run the whole app suite — `test_browse_file_renders_frontmatter_and_body`
      and the pipeline-artifact render tests must still pass unchanged (they assert `<h1>Plato</h1>`,
      which the allowlist keeps).
- [ ] Commit: `fix(browse): sanitize rendered markdown at the producer`

---

### T20 — Kill the phantom kickoff-template editor (E-15)

**Consumes P5** (§7): `kickoff_stage_id: str | None` in the `skill_editor.html` context.

**Failing test first.** Append to `tests/test_header.py`:

```python
@pytest.fixture
def client_with_skills(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    for name in ("shorts-ideation", "midjourney-prompting"):
        d = tmp_path / ".claude" / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app)


def test_a_skill_with_no_stage_mapping_shows_no_kickoff_editor(client_with_skills):
    """STAGE_ID_BY_SKILL maps 8 of 13 skills. The other five rendered an empty
    textarea with a live Save button targeting a template that does not exist,
    and "no kickoff template" was indistinguishable from "it is empty" (E-15)."""
    page = client_with_skills.get("/skills/midjourney-prompting").text
    assert 'value="kickoff_template"' not in page
    assert "This skill is not bound to a pipeline stage" in page


def test_a_mapped_skill_still_shows_the_kickoff_editor(client_with_skills):
    page = client_with_skills.get("/skills/shorts-ideation").text
    assert 'value="kickoff_template"' in page
    assert 'name="content"' in page
```

- [ ] Run: fails — the form renders unconditionally.
- [ ] **Implement.** `templates/skill_editor.html`:

```html
<h2>Kickoff template</h2>
{% if kickoff_stage_id %}
<form method="post" action="/skills/{{ skill_name }}/save">
  <input type="hidden" name="target" value="kickoff_template">
  <textarea name="content" rows="10">{{ kickoff_template_content }}</textarea>
  <button type="submit">Save kickoff template</button>
</form>
{% else %}
{# Rendering this form for an unmapped skill gave the operator a live Save
   button pointed at a file that cannot exist, and no way to tell an absent
   template from an empty one (E-15). #}
<p class="browse-placeholder">
  This skill is not bound to a pipeline stage, so it has no kickoff template.
  Kickoff templates exist only for the stages declared in <code>pipeline.yaml</code>.
</p>
{% endif %}
```

- [ ] Run: red until P5 publishes `kickoff_stage_id` (see §7). **Sequence T20 after P5's
      context task.** Until then `kickoff_stage_id` is undefined → falsy → the form is hidden
      for *every* skill, which fails `test_a_mapped_skill_still_shows_the_kickoff_editor`
      loudly rather than shipping a wrong page quietly.
- [ ] Commit: `fix(ui): hide the kickoff-template editor for skills with no stage`

---

### T21 — Doctor becomes the place to look when something broke overnight (E-16)

**Consumes P1** (§7): `recent_events`.

**Failing test first.** Append to `tests/test_header.py`:

```python
def test_doctor_renders_unacknowledged_error_events(client: TestClient):
    conn = client.app.state.conn
    conn.execute(
        "INSERT INTO events (occurred_at, kind, severity, source, message, detail, run_id, acknowledged) "
        "VALUES ('2026-08-08T06:02:00+00:00', 'adapter.fetch_failed', 'error', "
        "'discovery_youtube', 'yt-dlp exited 1 for @thinkmedia', '{\"handle\": \"@thinkmedia\"}', 4, 0)"
    )
    conn.commit()
    page = client.get("/doctor").text
    assert "adapter.fetch_failed" in page
    assert "yt-dlp exited 1 for @thinkmedia" in page
    assert "discovery_youtube" in page
    assert "status-error" in page


def test_doctor_says_so_when_there_is_nothing_to_report(client: TestClient):
    page = client.get("/doctor").text
    assert "No unacknowledged errors in the last 7 days." in page


def test_doctor_no_longer_duplicates_the_skill_list(client: TestClient):
    page = client.get("/doctor").text
    assert "Skills discovered:" not in page
    assert 'href="/skills"' in page


def test_a_skipped_orphan_sweep_renders_differently_from_a_clean_one(client: TestClient):
    """P1 types orphaned_count as `int | None`. None means the sweep never ran;
    0 means it ran and found nothing. Rendering both the same -- or printing
    the literal string "None" -- is the same empty-vs-broken confusion this
    programme exists to remove."""
    client.app.state.orphaned_count = 0
    clean = client.get("/doctor").text
    client.app.state.orphaned_count = None
    skipped = client.get("/doctor").text

    assert clean != skipped
    assert "not checked" in skipped
    assert "not checked" not in clean
    assert "None" not in skipped
```

- [ ] Run: fails on all three.
- [ ] **Implement.** Rewrite `templates/doctor.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>System</h1>
<ul>
  <li>Repo root: <code>{{ repo_root }}</code></li>
  <li>DB path: <code>{{ db_path }}</code></li>
  <li>Claude CLI: {% if cli.available %}found at <code>{{ cli.path }}</code>{% else %}NOT FOUND — {{ cli.error }}{% endif %}</li>
  {# P1 types this `int | None`, and None (the sweep did not run) must NOT
     render as 0 (the sweep ran and found nothing) -- that is precisely the
     empty-vs-broken confusion this programme exists to remove. Bare
     `{{ orphaned_count }}` would print the string "None". #}
  <li>Orphaned turns reconciled at startup:
    {% if orphaned_count is none %}
    <span class="status status-unknown">not checked — the startup sweep did not run</span>
    {% else %}
    {{ orphaned_count }}
    {% endif %}
  </li>
  <li><a href="/skills">Skills</a> — the list lives on its own page; duplicating it here told
      the operator nothing they could not already see.</li>
</ul>

<h2>Recent errors</h2>
{# Until this existed there was nowhere in the whole product to look when
   something broke overnight: 35 stderr diagnostics on the scheduled path go to
   a console Task Scheduler destroys (E-16, D-02). These are the unacknowledged
   error/critical events of the last 7 days, newest first, from P1's `events`
   table. #}
{% if recent_events %}
<table>
  <thead>
    <tr><th>When</th><th>Severity</th><th>Source</th><th>Kind</th><th>Message</th><th>Run</th></tr>
  </thead>
  <tbody>
    {% for e in recent_events %}
    <tr>
      <td><code>{{ e.occurred_at }}</code></td>
      <td><span class="status status-{{ e.severity }}">{{ e.severity }}</span></td>
      <td>{{ e.source }}</td>
      <td><code>{{ e.kind }}</code></td>
      <td>{{ e.message }}{% if e.detail %}<div class="event-detail">{{ e.detail }}</div>{% endif %}</td>
      <td>{{ e.run_id if e.run_id is not none else "—" }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% else %}
<p>No unacknowledged errors in the last 7 days.</p>
{% endif %}
{% endblock %}
```

Add to `static/style.css`:

```css
.status-critical { background: color-mix(in srgb, #ff5f5f 35%, transparent); color: #fff; border-color: #ff5f5f; }
.status-warning { background: color-mix(in srgb, var(--accent-amber) 25%, transparent); color: var(--accent-amber); border-color: var(--accent-amber); }
.status-info { background: color-mix(in srgb, var(--text-dim) 20%, transparent); color: var(--text-dim); border-color: var(--border); }
.event-detail { color: var(--text-dim); font-family: var(--font-mono); font-size: 0.8rem; }
```

- [ ] Run: `test_doctor_no_longer_duplicates_the_skill_list` and
      `test_doctor_says_so_when_there_is_nothing_to_report` pass immediately; the events test
      stays red until P1 lands the `events` table and passes `recent_events` (see §7).
- [ ] Commit: `feat(ui): render unacknowledged error events on the System page`

---

### T22 — Render P3's `inputs[]` and edit affordance (contract conformance, no P15 finding)

**Not one of this package's 16 findings.** E-05 (missing upstream dropped silently) and E-07
(the edit route has no UI) are P3's findings, but their *rendering* lands in `stage.html`,
which is P15's file. P3 publishes `inputs[]`, `edit_allowed`, `edit_blocked_reason`,
`edit_action` and `edit_field` and has nowhere to put them without this task. Sequenced after
P3's context task, same as T8–T10.

**Failing test first.** Append to `tests/test_header.py`:

```python
def test_every_declared_upstream_gets_a_card_including_missing_ones(client_with_stage):
    """A dependency with no artifact used to be dropped by an `is not None`
    guard, so the operator reviewed a partial input believing it complete."""
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert 'class="input-card"' in page
    assert "No upstream input." not in page or 'class="input-card"' in page


def test_a_missing_upstream_is_labelled_missing_not_omitted(client_with_stage):
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    # `ideation` declares no deps, so this asserts the shape holds at zero;
    # the multi-dep case is P3's fixture. What must never appear is a card
    # that is silently absent.
    assert "input-card-missing" in page or "This stage has no upstream dependencies." in page


def test_the_edit_output_disclosure_exists_when_editing_is_allowed(client_with_stage):
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    _stage_with_artifact(app, project["run_id"], "version: 1\n")
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert "Edit output" in page
    assert 'name="body"' in page or "edit_field" in page
```

- [ ] Run: fails — `stage.html` concatenates resolved upstream bodies into one blob and no
      template in the repo posts to the edit route at all.
- [ ] **Implement.** Replace the input panel in `templates/stage.html`:

```html
<section class="input-panel">
  <h2>Input</h2>
  {% if grounding_input_html %}
  <div class="input-card">
    <h3>Grounding companion</h3>
    <div class="rendered-markdown">{{ grounding_input_html | safe }}</div>
  </div>
  {% endif %}
  {# One card per DECLARED dependency, present or not. Concatenating only the
     ones that resolved meant a missing upstream left no gap on the page -- and
     the same partial context was what the turn was actually given. #}
  {% for up in inputs %}
  <div class="input-card{% if not up.present %} input-card-missing{% endif %}">
    <h3>
      From {{ up.stage_id }}
      {% if up.present %}
      <span class="strip-item">{{ up.artifact }}</span>
      {% else %}
      <span class="status status-no_artifact">missing</span>
      {% endif %}
    </h3>
    {% if up.present %}
    <div class="rendered-markdown">{{ up.html | safe }}</div>
    {% else %}
    <p class="gate-explainer">
      This stage declares <code>{{ up.stage_id }}</code> as a dependency and no artifact for it
      was found. The turn was given this same partial context.
    </p>
    {% endif %}
  </div>
  {% endfor %}
  {% if not inputs and not grounding_input_html %}
  <p>This stage has no upstream dependencies.</p>
  {% endif %}
</section>
```

and add the edit disclosure at the end of the output panel:

```html
  {# 60 lines of carefully-reasoned re-gating behaviour that no template posted
     to. Without this the only way to fix a typo in an output is to re-run a
     whole turn or edit the file on disk, which bypasses exactly the re-gating
     the route exists to guarantee. #}
  {% if edit_allowed %}
  <details class="edit-output">
    <summary>Edit output</summary>
    <form method="post" action="{{ edit_action }}">
      <textarea name="{{ edit_field }}" rows="20">{{ output_body }}</textarea>
      <button type="submit">Save as a new version and re-run gates</button>
    </form>
  </details>
  {% elif edit_blocked_reason %}
  <p class="browse-placeholder">Editing is unavailable: {{ edit_blocked_reason }}</p>
  {% endif %}
```

Add to `static/style.css`:

```css
.input-card { border: 1px solid var(--border); border-radius: 0.25rem; padding: 0.5rem 0.75rem; margin-bottom: 0.75rem; }
.input-card-missing { border-color: var(--accent-amber); border-style: dashed; }
.edit-output { margin-top: 1rem; }
.edit-output summary { cursor: pointer; font-family: var(--font-mono); color: var(--accent-magenta); }
```

- [ ] Run: passes once P3's context lands.
- [ ] Commit: `feat(ui): render per-dependency input cards and the edit-output disclosure`

---

## 4. Finding → test map

`silent` findings carry all three Three-Test-Rule roles. `latent` / `loud` findings carry a
fault + surfacing pair; a distinguishability test is only meaningful where a broken state can
be mistaken for a legitimately empty one, and is marked **n/a** where it cannot.

| Finding | Mode | Test(s) | Role |
|---|---|---|---|
| D-41 | latent | `test_no_template_references_an_external_host` | fault |
| | | `test_htmx_is_served_from_the_local_static_mount` | surfacing |
| D-42 | silent | `test_no_template_references_an_external_host` | fault (the dependency is gone, so the offline path cannot be entered) |
| | | `test_browse_page_carries_a_global_htmx_error_banner` | distinguishability (a dead fetch renders a message, not an empty tree that looks like "no artifacts") |
| | | `test_browse_tree_expansion_can_be_retried_after_a_failure` | surfacing |
| E-13 | silent | `test_browse_file_unexpected_exception_renders_an_error_not_a_500` | fault |
| | | `test_browse_file_render_failure_is_distinct_from_an_empty_document` | distinguishability |
| | | `test_browse_page_carries_a_global_htmx_error_banner` | surfacing |
| E-08 | latent | `test_every_page_renders_the_three_section_top_nav` | fault |
| | | `test_library_pages_render_the_library_tab_strip`, `test_the_current_section_and_tab_are_both_marked_active`, `test_projects_page_has_no_tab_strip` | surfacing |
| | | `test_pages_without_a_stage_rail_ship_no_aside_at_all` / `test_a_project_page_does_ship_the_stage_rail_aside` | distinguishability (no rail vs. a rail) |
| | | `test_stage_breadcrumb_links_back_to_the_project` | surfacing |
| | | `test_project_home_shows_a_gate_roll_up_and_a_next_action` | surfacing |
| E-06 | silent | `test_stage_page_status_strip_states_status_version_and_generated_at` | fault + surfacing |
| | | (distinguishability is carried by E-02's never-ran pair, which is the state E-06's strip exists to expose) | n/a |
| E-02 | silent | `test_a_gate_that_never_ran_is_rendered_as_never_ran` | fault |
| | | `test_never_ran_page_differs_from_a_genuinely_clean_pass` | distinguishability |
| | | `test_an_unrecognised_gate_status_reads_as_unverified_not_as_a_pass` | fault + distinguishability for P3's `unknown` state |
| | | `test_gate_panel_renders_above_the_artifact_body` | surfacing |
| E-03 | loud | `test_never_ran_gate_page_offers_a_usable_next_action` | fault (**the mandated test**: page says "never ran" AND offers the override field) |
| | | `test_a_healthy_stage_approve_form_has_no_override_field` | distinguishability |
| | | `test_a_blocked_approve_re_renders_the_stage_page_not_plain_text` | surfacing |
| E-01 | silent | `test_the_sse_result_branch_reveals_the_affordance` | fault |
| | | `test_stage_page_ships_a_hidden_turn_complete_affordance` | distinguishability (a stale panel is labelled stale; an up-to-date one is not) + surfacing |
| E-09 | silent | `test_terminal_run_states_are_visually_distinguishable` | fault + distinguishability |
| | | `test_a_run_with_errors_carries_an_error_count_on_its_line` | surfacing |
| E-10 | silent | `test_a_failed_handle_is_named_not_numbered` | fault |
| | | `test_errored_handle_results_are_listed_before_healthy_ones` | surfacing |
| | | (the `unresolved handle id …` branch is the distinguishability guard: an unjoinable row renders as unresolved, never as a plausible name) | distinguishability |
| E-12 | silent | `test_the_status_poller_stops_and_reports_when_a_fetch_fails` | fault |
| | | `test_an_invalid_handle_states_a_reason_or_says_none_was_recorded` | distinguishability (invalid-with-reason vs. invalid-with-none-recorded, never a bare word) |
| | | `test_handle_states_have_distinct_pill_styling` | surfacing |
| B-74 | latent | `test_platform_options_match_the_adapter_registry_exactly` | fault (falsified manually in T15 by adding a fake adapter) |
| E-14 | silent | `test_md_below_state_reports_unreadable_not_empty` | fault (a) |
| | | `test_unreadable_folder_is_distinguishable_from_an_empty_one` | distinguishability (a) |
| | | `test_unreadable_folder_renders_as_a_disabled_row_with_a_reason` | surfacing (a) |
| | | `test_pointer_state_reports_malformed_yaml_as_an_error` | fault (b) |
| | | `test_malformed_pointer_is_distinguishable_from_no_pointer` | distinguishability (b) |
| | | `test_list_children_lists_a_broken_pointer_instead_of_skipping_it`, `test_broken_grounding_pointer_stays_reachable_through_the_tree` | surfacing (b) |
| | | `test_an_empty_root_renders_an_explicit_empty_line_not_blank_space` | fault (c) |
| | | `test_an_empty_root_is_distinguishable_from_an_unreadable_one` | distinguishability + surfacing (c) |
| D-47 | latent | `test_sanitize_html_strips_script_vectors` (5 params) | fault |
| | | `test_render_md_file_body_html_is_sanitized` | surfacing |
| | | `test_sanitize_html_keeps_ordinary_markdown_output` | distinguishability (sanitized ≠ gutted) |
| E-15 | silent | `test_a_skill_with_no_stage_mapping_shows_no_kickoff_editor` | fault |
| | | `test_a_mapped_skill_still_shows_the_kickoff_editor` | distinguishability |
| | | (the explanatory line asserted in the fault test) | surfacing |
| E-16 | silent | `test_doctor_renders_unacknowledged_error_events` | fault + surfacing |
| | | `test_doctor_says_so_when_there_is_nothing_to_report` | distinguishability (nothing broke vs. nothing rendered) |
| | | `test_a_skipped_orphan_sweep_renders_differently_from_a_clean_one` | distinguishability (`None` vs. `0` on P1's `orphaned_count`) |
| | | `test_doctor_no_longer_duplicates_the_skill_list` | surfacing |
| *(T22, no finding)* | — | `test_every_declared_upstream_gets_a_card_including_missing_ones`, `test_a_missing_upstream_is_labelled_missing_not_omitted`, `test_the_edit_output_disclosure_exists_when_editing_is_allowed` | conformance to P3's `inputs[]` / `edit_*` keys; the findings themselves (E-05, E-07) are scored against P3 |

---

## 5. Tests deleted or inverted

All six are in files this package owns. None is one of the audit's named defect-affirming
tests except the first, which is a genuine instance of the same class: it asserts a defect
(E-14a) is correct behavior.

| File:line | Test | Disposition | Replacement |
|---|---|---|---|
| `pipeline-app/tests/test_browse_service.py:155-172` | `test_has_md_below_scandir_oserror_returns_false` | **Inverted.** Its name states the defect and its body freezes it: an unreadable folder returns `False` *and* is asserted absent from its parent's listing. That is exactly E-14a. | `test_md_below_state_reports_unreadable_not_empty` + `test_unreadable_folder_is_distinguishable_from_an_empty_one` (T16) |
| `pipeline-app/tests/test_browse_service.py:332-338` | `test_has_md_below_true_when_valid_grounding_pointer_present` | **Updated** (API rename only). | `assert browse_service._md_below_state(grounding_dir, tmp_path) == "content"` |
| `pipeline-app/tests/test_browse_service.py:341-351` | `test_has_md_below_false_when_only_raw_output_md_present` | **Updated** (API rename only). Behavior is correct and stays pinned. | `assert browse_service._md_below_state(stage_dir, tmp_path) == "empty"` |
| `pipeline-app/tests/test_browse_service.py:354-356` | `test_has_md_below_false_when_no_pointer_and_no_md` | **Updated** (API rename only). | `… == "empty"` |
| `pipeline-app/tests/test_browse_service.py:359-362` | `test_has_md_below_false_when_pointer_target_missing` | **Inverted.** A pointer whose target is missing is *broken*, not *empty* — under T17 it must be listed with a reason, so `"empty"` would freeze half of E-14b. | rename to `test_md_below_state_counts_a_broken_pointer_as_content` asserting `… == "content"`, plus the T17 entry tests |
| `pipeline-app/tests/test_routes_browse.py:51-63` | `test_browse_tree_items_carry_htmx_attributes_not_ids` | **Inverted (one assertion).** Line 56 asserts `hx-trigger="toggle once from:closest details"`; `once` is precisely why a failed subtree expansion could never be retried (E-13). | assertion becomes `hx-trigger="toggle from:closest details"`; the rest of the test is unchanged |
| `pipeline-app/tests/test_routes_browse.py:72-77` | `test_browse_root_marks_nav_link_active` | **Updated.** Asserts a top-level `Browse` link that the committed IA removes. | asserts `<a href="/browse" class="active">Library</a>` in the top nav **and** `<a href="/browse" class="active">Files</a>` in the tab strip |
| `pipeline-app/tests/test_header.py:18-27` | `test_every_page_renders_shared_header` | **Replaced.** Asserts `href="/skills"`, `href="/doctor"`, `href="/inspector"` are present on *every* page — the seven-flat-peers arrangement E-08 is about. | `test_every_page_renders_the_three_section_top_nav` (T4) |
| `pipeline-app/tests/test_header.py:30-34` | `test_page_shell_wraps_sidebar_and_main` | **Inverted.** Asserts `class="app-sidebar"` on `/`, i.e. that a non-project page ships the empty `<aside>` E-08 names. | `test_pages_without_a_stage_rail_ship_no_aside_at_all` + `test_a_project_page_does_ship_the_stage_rail_aside` (T5) |
| `pipeline-app/tests/test_header.py:37-48` | `test_active_nav_marks_the_current_top_nav_link` | **Replaced.** Asserts four top-level active links that no longer exist as top-level links. | `test_the_current_section_and_tab_are_both_marked_active` (T4) |
| `pipeline-app/tests/test_header.py:51-59` | `test_project_home_and_stage_page_mark_projects_active_with_breadcrumb` | **Updated.** Line 59 asserts `class="breadcrumb" not in resp.text` on the project home; the committed header renders a breadcrumb whenever `project` is present, stage or no stage. | assertion becomes: breadcrumb *is* present and contains the run_id as a link, with no ` / ` stage segment |

Nothing is deleted outright. Every inversion keeps its original coverage and adds the state
the old assertion made unreachable.

---

## 6. The committed IA

Evaluated the audit's §2 proposal and **adopted it**, with two deliberate deviations, both
forced by file exclusivity and both stated in the templates themselves:

1. **`/discovery/schedule` is not a route.** Splitting the Schedule block off the Sources page
   needs `routes/discovery.py`, which is P8's. Schedule is a tab that anchors to the
   `id="schedule"` section of the Sources page (T14). When P8 lands the route, the tab's
   `href` is the only line that changes.
2. **Inspector is a fourth Library tab, not absorbed into Files.** Folding "open by path" into
   the Browse page needs `routes/inspector.py` (P5). Demoting it out of the top nav — which is
   the actual E-08 complaint — is done; absorbing it is left as a follow-up.

```
ContentStudio                                     [CLI: online / offline]   ← header row 1
│
├─ Projects                        /
│  ├─ list + create form
│  └─ <run-id>                     /projects/{id}          ← Overview: brand, created-at,
│     │                                                      status roll-up, "Next action" link
│     └─ Stage: <stage-id>         /projects/{id}/stages/{stage}
│        ├─ breadcrumb  <run-id> / <stage-id>   ← run-id is a link back to the Overview
│        ├─ status strip           status pill · artifact vN · generated · finalized
│        ├─ Input
│        ├─ Chat                   + hidden "turn complete — panels are stale" affordance
│        └─ Output                 gates ABOVE the body; approve + override live here
│           └─ stage rail          <aside>, rendered only where `nav` exists
│
├─ Discovery                       /discovery/handles                       ← header row 2 (tabs)
│  ├─ Sources                      /discovery/handles
│  ├─ Runs                         /discovery/runs
│  └─ Schedule                     /discovery/handles#schedule   (own route deferred to P8)
│
└─ Library                         /browse                                  ← header row 2 (tabs)
   ├─ Files                        /browse
   ├─ Skills                       /skills
   ├─ System                       /doctor          ← CLI, DB, orphan count, recent errors
   └─ Open by path                 /inspector       (absorption into Files deferred to P5)
```

Seven flat top-level links → **three**. Two Discovery entries → **one**. Every non-project page
ships **no** `<aside>` at all. `active_nav` — the key the routes already pass — is mapped to a
section inside `partials/header.html`, so no route in any other package has to change for this.

---

## 7. Inputs consumed

Every key below is produced by another package. Where a key is missing, the bound task's test
is **red**, never green-with-a-fallback — a template that silently degrades is the defect this
programme exists to remove.

### From P3 — gate state and approval, into `stage.html`

`routes/stages.py` and `approval_service.py` are P3's. **P3's names are canonical** — the
orchestrator adopted them after validation caught that P15's first draft had bound to an
entirely disjoint set (`gate_states`, `approval_blocked`, `approval_error`, `output_meta`).
Zero names overlapped, and because Jinja renders an undefined key as empty, the stage page
would have shown *nothing at all* for gate state — silently reimplementing E-03, the defect
this package exists to fix. Every key below is P3's spelling.

| Key | Type | Notes |
|---|---|---|
| `gate_view` | `list[dict]` | One entry per gate in `GATE_REGISTRY[stage_id]`, unioned with any recorded result whose name is not registered. Replaces `output_gates`. Each entry: `name: str`; `state: "passed" \| "failed" \| "errored" \| "never_ran" \| "unknown"`; `status_raw: str \| None` (the verbatim frontmatter string, rendered for `unknown`); `blocking: bool`; `findings: list[dict]` with `kind`/`check`/`beat`/`message`. **All five states get an explicit arm in `partials/gate_strip.html`** — `unknown` reads as "unverified", never falls through to something benign. |
| `has_blocking_gate` | `bool` | True iff approve would raise without an override — i.e. any `gate_view` entry with `blocking` true. **Replaces `has_failing_gate`**, whose narrower "recorded fail/error only" condition is the E-03 defect. Drives the override field in T10. |
| `approval_block_reasons` | `list[str]` | **Not actually produced by P3** — verified absent from the live repo at T10 execution (see T10's amendment above). T10 derives the equivalent reason list in-template from `gate_view | selectattr("blocking")` instead. This row is historical (what was planned, not what shipped). |
| `error_banner` | `dict \| None` | `{kind: str, message: str}`. P3's single error channel for the page — gate block, stage locked, turn running, edit refusal — distinguished by `kind`, which T10 renders as `data-error-kind`. |
| `gate_override` | `dict \| None` | `{reason: str, at: str}`. Read as `gate_override.reason` (+ `.at`) in T8's status strip. Written by `approval_service.py:70,76` and displayed nowhere today. |
| `artifact_version` | `int \| None` | Pass-through P3 adds at P15's request: `stages.py:100` parses this into `output_meta` and throws it away (E-06). |
| `artifact_created_at` | `str \| None` | Same. Aware-UTC ISO 8601. |
| `artifact_finalized_at` | `str \| None` | Same. |
| `inputs` | `list[dict]` | `{stage_id, present, artifact, body, html}`, one per **declared** dependency including absent ones. Rendered as per-dependency cards in T22. |
| `edit_allowed` | `bool` | Whether the edit-output disclosure renders (T22). |
| `edit_blocked_reason` | `str \| None` | Rendered in place of the disclosure when editing is refused (e.g. `grounding`). |
| `edit_action` | `str` | Form action for the edit POST. |
| `edit_field` | `str` | Form field name the edit route reads the body from. |

**Status codes P15 binds to:** approve POST → `303` on success; `409` **re-rendering
`stage.html`** with `error_banner` populated, not `PlainTextResponse` (P3's E-04).

**Retired by this rebind:** `output_gates`, `has_failing_gate` and `output_meta` are no longer
read by any template in this package.

### From P1 — observability, into `doctor.html`

| Key | Type | Meaning |
|---|---|---|
| `recent_events` | `list[Row \| dict]` | Unacknowledged `error` / `critical` rows from the frozen `events` table, `occurred_at` within the last 7 days, newest first. Fields read by the template: `occurred_at`, `severity`, `source`, `kind`, `message`, `detail`, `run_id` — exactly the `events` columns as frozen in the orchestration plan. Empty list is a legitimate state and renders "No unacknowledged errors in the last 7 days." |
| `orphaned_count` | `int \| None` | Already passed today, but **`None` must not render as `0`**: `None` is "the startup sweep did not run", `0` is "it ran and found nothing". Bare `{{ orphaned_count }}` prints the literal string `None`. T21 gives each its own arm and `test_a_skipped_orphan_sweep_renders_differently_from_a_clean_one` pins the distinction. |

### From P5 — skill editor, into `skill_editor.html`

| Key | Type | Meaning |
|---|---|---|
| `kickoff_stage_id` | `str \| None` | `STAGE_ID_BY_SKILL.get(skill_name)` — already computed at `routes/skills.py:58` as the local `stage_id` and simply not forwarded. Falsy for the five unmapped skills and for `rgs-pairing-review`, whose map value is an explicit `None`. **T20 is sequenced after this.** |

### From P8 — discovery runs, into `discovery_runs.html`

| Key | Type | Meaning |
|---|---|---|
| `handle_results[*].platform`, `.handle`, `.display_name` | `str` | `discovery_runs_page` joins `handles` so each result names its source. Until it lands, T13's template renders `unresolved handle id N`, and **both** of T13's new tests (not just the first) are marked `xfail(strict=True)` in `tests/test_header.py` — remove both markers once this join lands (corrected 2026-08-18 at Opus checkpoint B; see T13's own amendment). |

### From P8 / P1 — runs pagination (render-side bounded here, not solved here)

`db.list_runs` has no `LIMIT` (P1's `db.py`) and `discovery_runs_page` passes every run with
every per-handle result (P8's route). T13 bounds the *render* — per-run results collapse into a
`<details>` — and prints an explicit note when the list is unbounded. The query bound itself is
not this package's to make.

### Published by P15 for others

| Symbol | Consumer |
|---|---|
| `browse_service.sanitize_html(html: str) -> str` | **P3** at `routes/stages.py:78,94,102` and **P5** at `routes/inspector.py:45` — the remaining `| safe` producer sites (D-47). The filter is stdlib-only (`html.parser`), so adopting it adds no dependency and needs no `requirements.txt` change. |
