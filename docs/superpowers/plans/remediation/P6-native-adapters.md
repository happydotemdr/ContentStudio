# P6 — Native adapters (YouTube, YouTube Data API, Bluesky)

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` or
> `superpowers:executing-plans`. Every task is a checkbox. The **Global Constraints**, **test
> standard** and **Frozen interfaces** of
> [`../2026-08-08-audit-remediation.md`](../2026-08-08-audit-remediation.md) are binding and are
> not restated here.

**Wave B.** Depends on P0 (the `allow_subprocess` marker and the network guard) and P1 (`obs.log`).
No other package may touch the files below, and this package touches nothing else — in particular
**not** `brightdata_job.py`, whose module docstring (`brightdata_job.py:6-10`) states the invariant
this package exists to bring the two native adapters into line with:

> a job that times out or reports 'failed' MUST raise, never return `[]`. An empty list means "the
> job completed and there was genuinely nothing" … the exact bug that shipped in the first
> Instagram adapter.

That contract is already enforced for the four Bright Data platforms. YouTube and Bluesky violate
it. **Closing that violation is the spine of this plan**; the remaining findings hang off it.

---

## 1. Scope

### Files owned (exclusive)

```
pipeline-app/pipeline_app/discovery_youtube.py
pipeline-app/pipeline_app/discovery_youtube_api.py
pipeline-app/pipeline_app/discovery_bluesky.py
pipeline-app/tests/test_discovery_youtube.py
pipeline-app/tests/test_discovery_youtube_api.py
pipeline-app/tests/test_discovery_bluesky.py
```

### Findings owned (18)

`B-04`, `B-05`, `B-06`, `B-07`, `B-08`, `B-09`, `B-10`, `B-11`, `B-12`, `B-13`, `B-14`, `B-15`,
`B-16`, `B-17`, `D-52`, `F-12`, `F-20`, `F-24`

Severities: **S1 ×5** (B-06, B-10, B-12, F-12, F-20), S2 ×7, S3 ×1, S4 ×5.
`failure_mode: silent` ×9 (B-05, B-06, B-07, B-08, B-10, B-11, B-12, B-13, B-14, F-12 — the
Three-Test Rule applies to every one of them).

### The three structural changes everything else depends on

1. **`_run_ytdlp()`** — one chokepoint for all three `subprocess.run` sites in
   `discovery_youtube.py`, carrying `encoding="utf-8", errors="replace"`, normalising `stdout`/
   `stderr` from `None` to `""`, and returning the return code to a caller that is now obliged to
   look at it. Closes B-10 and B-16 at the source instead of in three places.
2. **Typed failures — `YouTubeEnumerationError`, `TranscriptFetchBlocked`, `BlueskyFetchError`.**
   Enumeration and transport failures *raise*; a genuinely empty listing *returns `[]`*. The two
   states stop sharing a representation, which is what makes them impossible to confuse.
3. **A retryable transcript state.** `transcript_status` gains a third value, `pending_retry`, and
   `on_disk_ids()` re-offers items carrying it. A bot-blocked capture stops being permanent.

---

## 2. Finding → task map

| Finding | Sev | Mode | Task(s) |
|---|---|---|---|
| B-10 · cp1252 subprocess decoding crashes or corrupts enumeration | S1 | silent | **T1**, **T2** |
| B-16 · subprocess return codes ignored; `peek`'s `json.loads` unguarded | S3 | latent | **T3** |
| B-11 · a failed `/videos` enumeration is reported as a quiet day | S2 | silent | **T4** |
| B-14 · new handle, no key, bot-block → captures nothing, silently | S2 | silent | **T5**, **T7** |
| F-24 · `fetch_upload_dates` has no test at all | S2 | coverage-gap | **T5**, **T7** |
| B-15 · "no Data API key" warning printed once per video | S4 | latent | **T6** |
| D-52 · Data API key travels in the request URL query string | S4 | latent | **T8** |
| B-13 · transcript fallback's bare except hides rate-limits and IP blocks | S2 | silent | **T9** |
| B-12 · a bot-blocked download writes a permanent transcript-less capture | S1 | silent | **T10**, **T11** |
| B-04 · YouTube writes `upload_date`, not the contract's `published` | S4 | docs-drift | **T12** |
| B-05 · Bluesky enumerate reports every fetch error as an empty feed | S2 | silent | **T13**, **T14** |
| F-12 · a test codifies the "empty ≠ failed" violation | S1 | silent | **T13** |
| B-06 · a transient Bluesky failure permanently disables the handle | S1 | silent | **T15** |
| B-08 · keyword filter matches only the first 60 characters | S2 | silent | **T16** |
| B-09 · `peek_upload_date`'s "dead code" comment is false | S4 | docs-drift | **T17** |
| B-07 · `download_item` re-walks the whole feed once per item | S2 | silent | **T18** |
| F-20 · no adapter-contract test | S1 | coverage-gap | **T19** |
| B-17 · YouTube re-enumerates the entire catalogue every run | S4 | latent | **T20** |

**18/18 mapped.**

---

## 3. Tasks

Each task is one TDD cycle: **write the failing test → run it → read the failure → implement → run
→ green → commit.** Run the app suite as `cd pipeline-app && python -m pytest tests/<file> -q`
(never a bare `pytest`, never from the repo root — the root `scripts/` shadows the app's).

Shared test helper, added once in T1 and reused throughout. It must live in the three owned test
files (P0 owns `tests/conftest.py`; this package does not touch it):

```python
# top of each of the three owned test files
import pytest
from pipeline_app import obs


@pytest.fixture
def logged(monkeypatch):
    """Capture obs.log() as data.

    Not a call-spy: the assertions below are on the event kind, level and
    fields an operator actually reads out of app-YYYY-MM-DD.log, which is a
    durable artifact, unlike the stderr print() that D-02 showed nobody sees.
    """
    records: list[dict] = []

    def fake_log(event, *, level="info", **fields):
        records.append({"event": event, "level": level, **fields})

    monkeypatch.setattr(obs, "log", fake_log)
    return records
```

---

### T1 · One encoded subprocess chokepoint, and `stdout` can never be `None` (B-10)

- [ ] **Write the failing tests** in `pipeline-app/tests/test_discovery_youtube.py`:

```python
import subprocess
import sys


@pytest.mark.allow_subprocess
def test_run_ytdlp_round_trips_a_non_cp1252_title_byte_identically():
    """B-10, the reproduction, as a test.

    U+1F60D's UTF-8 bytes include 0x8D, which is undefined in cp1252: under
    text=True the reader thread dies and subprocess.run returns stdout=None.
    U+1F525's bytes are all cp1252-defined, so it decodes into four mojibake
    characters instead of crashing. Both are in this title, plus a Latin-1
    letter whose corruption is visible in a filename.
    """
    title = "Playa \U0001F60D Ocotal \U0001F525 naïve wins"
    script = (
        "import sys, json;"
        "sys.stdout.buffer.write(json.dumps("
        f"{{'entries': [{{'id': 'v1', 'title': {title!r}}}]}}"
        ", ensure_ascii=False).encode('utf-8'))"
    )
    monkey_bin = [sys.executable, "-c", script]
    proc = yt._run_ytdlp(monkey_bin[1:], binary=monkey_bin[:1], label="test")

    assert proc.returncode == 0
    entry = json.loads(proc.stdout)["entries"][0]
    assert entry["title"] == title
    assert entry["title"].encode("utf-8") == title.encode("utf-8")


def test_run_ytdlp_never_returns_none_stdout(monkeypatch):
    """The AttributeError branch: a dead reader thread yields stdout=None."""
    class DeadReader:
        returncode = 0
        stdout = None
        stderr = None

    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: DeadReader())
    proc = yt._run_ytdlp(["-J"], label="test")
    assert proc.stdout == ""
    assert proc.stderr == ""
    assert proc.stdout.strip() == ""  # would AttributeError today


def test_run_ytdlp_passes_utf8_encoding_not_bare_text_mode(monkeypatch):
    seen = {}
    monkeypatch.setattr(yt.subprocess, "run",
                        lambda *a, **k: seen.update(k) or _proc(0, "{}", ""))
    yt._run_ytdlp(["-J"], label="test")
    assert seen["encoding"] == "utf-8"
    assert seen["errors"] == "replace"
    assert "text" not in seen
```

with a shared factory near the top of the file:

```python
def _proc(returncode, stdout, stderr):
    class FakeProc:
        pass
    FakeProc.returncode = returncode
    FakeProc.stdout = stdout
    FakeProc.stderr = stderr
    return FakeProc()
```

- [ ] **Run** → `AttributeError: module 'pipeline_app.discovery_youtube' has no attribute '_run_ytdlp'`.
- [ ] **Implement** in `discovery_youtube.py`, above `_enumerate_tab`:

```python
from pipeline_app import obs

YTDLP_BIN = ["yt-dlp"]


class YtDlpUnavailable(RuntimeError):
    """yt-dlp is not on PATH. Not a quiet channel -- an unusable environment."""


def _run_ytdlp(args: list[str], *, label: str,
               binary: list[str] | None = None) -> subprocess.CompletedProcess:
    """The single place this module spawns yt-dlp.

    encoding="utf-8", errors="replace" is load-bearing on Windows: bare
    text=True decodes yt-dlp's UTF-8 output with the host ANSI codepage
    (cp1252 here), which either kills the reader thread -- leaving
    stdout=None for the caller to trip over -- or silently mojibakes a title
    into the filename, the corpus and the daily email. Both were reproduced;
    see finding B-10.

    stdout/stderr are normalised to "" so no caller can ever face None.
    """
    cmd = [*(binary or YTDLP_BIN), *args]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="replace",
        )
    except FileNotFoundError as exc:
        obs.log("adapter.tool_missing", level="error", platform="youtube",
                tool=cmd[0], label=label)
        raise YtDlpUnavailable(f"yt-dlp not found on PATH (needed for {label})") from exc
    if proc.stdout is None:
        proc.stdout = ""
    if proc.stderr is None:
        proc.stderr = ""
    return proc
```

- [ ] **Run** → green. **Commit** `fix(youtube): decode yt-dlp output as utf-8, never as cp1252 (B-10)`.

---

### T2 · A real emoji survives enumerate → title → filename → body (B-10)

- [ ] **Write the failing tests** — the round trip through the module's own code path, not through
      the helper:

```python
_EMOJI_TITLE = "Playa \U0001F60D Ocotal \U0001F525 naïve wins"


def _real_ytdlp_emitting(payload: dict) -> list[str]:
    """A binary substitute that writes real UTF-8 bytes to stdout."""
    script = ("import sys, json;"
              f"sys.stdout.buffer.write(json.dumps({payload!r}, ensure_ascii=False)"
              ".encode('utf-8'))")
    return [sys.executable, "-c", script]


@pytest.mark.allow_subprocess
def test_enumerate_preserves_an_emoji_title_byte_identically(monkeypatch):
    monkeypatch.setattr(yt, "YTDLP_BIN", _real_ytdlp_emitting(
        {"entries": [{"id": "v1", "title": _EMOJI_TITLE}]}))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates",
                        lambda ids, **k: {"v1": "2026-07-01"})
    items = yt.enumerate_newest_first("@c", None)
    assert items[0]["title"] == _EMOJI_TITLE


def test_download_item_filename_and_h1_carry_the_original_characters(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "v1", _EMOJI_TITLE)

    dest_dir = tmp_path / "output" / "brand-intel" / "youtube" / "testhandle"
    (written,) = list(dest_dir.glob("v1__*.md"))
    # cp1252 corruption of "naïve" is "naÃ¯ve"; slugify keeps the \w chars, so
    # the mojibake is visible in the filename as "naÃve".
    assert "naïve" in written.name
    assert "Ã" not in written.name
    body = written.read_text(encoding="utf-8")
    assert f"# {_EMOJI_TITLE}" in body
```

- [ ] **Run** → fails: `enumerate_newest_first` still calls `subprocess.run` directly, so
      `YTDLP_BIN` is ignored and the emoji test errors on `FileNotFoundError`/decode.
- [ ] **Implement** — route `_enumerate_tab` through `_run_ytdlp` (the returncode logic is T4's;
      here only the call site moves):

```python
def _enumerate_tab(handle: str, tab: str, content_type: str) -> list[dict]:
    url = f"https://www.youtube.com/{handle}/{tab}"
    proc = _run_ytdlp(
        ["-J", "--flat-playlist", "--ignore-errors", *_cookie_args(), url],
        label=f"enumerate {handle}/{tab}",
    )
    ...
```

- [ ] Update the existing fakes in this file — `_fake_tabs`, `_ytdlp_ok`, `_ytdlp_blocked` and the
      four `def fake_run(cmd, capture_output, text)` signatures — to `(*args, **kwargs)` and to
      patch `yt._run_ytdlp` rather than `yt.subprocess.run`, e.g.:

```python
def _ytdlp_ok(info: dict):
    def fake_run(args, *, label, binary=None):
        stem = Path(args[args.index("-o") + 1].replace(".%(ext)s", ""))
        stem.with_suffix(".info.json").write_text(json.dumps(info), encoding="utf-8")
        return _proc(0, "", "")
    return fake_run
```

- [ ] **Run** → green. **Commit** `test(youtube): prove an emoji title survives to the filename (B-10)`.

---

### T3 · Return codes are read; `peek`'s JSON parse is guarded (B-16)

- [ ] **Write the failing tests:**

```python
def test_peek_upload_date_reports_a_failed_ytdlp_instead_of_returning_none(monkeypatch, logged):
    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(1, "", "HTTP Error 429"))
    assert yt.peek_upload_date("v1") is None
    assert [r for r in logged if r["event"] == "adapter.peek_failed"
            and r["level"] == "warning" and "429" in r["stderr"]]


def test_peek_upload_date_survives_a_truncated_info_json(monkeypatch, logged):
    def fake_run(args, *, label, binary=None):
        stem = Path(args[args.index("-o") + 1].replace(".%(ext)s", ""))
        stem.with_suffix(".info.json").write_text('{"upload_date": "2026', encoding="utf-8")
        return _proc(0, "", "")

    monkeypatch.setattr(yt, "_run_ytdlp", fake_run)
    assert yt.peek_upload_date("v1") is None          # today: JSONDecodeError escapes
    assert [r for r in logged if r["event"] == "adapter.info_json_unparseable"]


def test_download_item_logs_a_nonzero_ytdlp_exit(monkeypatch, tmp_path, logged):
    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(1, "", "Sign in to confirm"))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    monkeypatch.setattr(yt.youtube_api, "fetch_one", lambda *a, **k: dict(_API_RECORD))
    yt.download_item(tmp_path, "@testhandle", "v1", "T")
    assert [r for r in logged if r["event"] == "adapter.download_tool_failed"
            and r["level"] == "warning" and r["video_id"] == "v1"]
```

- [ ] **Run** → the truncated-`info.json` test raises `json.JSONDecodeError`; the other two fail on
      the missing log records.
- [ ] **Implement** in `peek_upload_date`:

```python
        proc = _run_ytdlp(
            ["--skip-download", "--write-info-json", "--no-warnings",
             "--ignore-errors", *_cookie_args(), "-o", str(tmp_stem) + ".%(ext)s", url],
            label=f"peek {video_id}",
        )
        if proc.returncode != 0:
            obs.log("adapter.peek_failed", level="warning", platform="youtube",
                    video_id=video_id, returncode=proc.returncode,
                    stderr=proc.stderr.strip()[:200])
        info_path = tmp_stem.with_suffix(".info.json")
        if not info_path.exists():
            return None
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            # download_item already guards the structurally identical parse;
            # the same corrupt file must not be fatal on one path and tolerated
            # on the other (B-16).
            obs.log("adapter.info_json_unparseable", level="warning",
                    platform="youtube", video_id=video_id, error=type(exc).__name__)
            return None
```

and in `download_item`, replacing the bare `subprocess.run(cmd, ...)`:

```python
    proc = _run_ytdlp([...], label=f"download {video_id}")
    ytdlp_ok = proc.returncode == 0
    if not ytdlp_ok:
        obs.log("adapter.download_tool_failed", level="warning", platform="youtube",
                handle=handle, video_id=video_id, returncode=proc.returncode,
                stderr=proc.stderr.strip()[:200])
```

`ytdlp_ok` is consumed by T10; keep it now.

- [ ] **Run** → green. **Commit** `fix(youtube): read yt-dlp return codes and guard peek's json parse (B-16)`.

---

### T4 · Enumeration failure raises; only an absent `/shorts` tab is legitimately empty (B-11)

This is the zero-vs-failure fix for YouTube.

- [ ] **Write the failing tests** (the fault / distinguishability / surfacing triple):

```python
def test_enumerate_raises_when_the_videos_tab_fetch_fails(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp",
                        lambda *a, **k: _proc(1, "", "ERROR: unable to download API page: HTTP Error 429"))
    with pytest.raises(yt.YouTubeEnumerationError) as exc:
        yt.enumerate_newest_first("@dead-handle", keyword_filter=None)
    assert "@dead-handle" in str(exc.value)
    assert "429" in str(exc.value)


def test_a_failed_fetch_is_distinguishable_from_a_channel_with_no_uploads(monkeypatch):
    """The Three-Test Rule's distinguishability case, stated directly."""
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {})
    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(0, json.dumps({"entries": []}), ""))
    genuinely_empty = yt.enumerate_newest_first("@quiet", keyword_filter=None)
    assert genuinely_empty == []

    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(1, "", "HTTP Error 503"))
    with pytest.raises(yt.YouTubeEnumerationError):
        yt.enumerate_newest_first("@quiet", keyword_filter=None)


def test_enumerate_failure_is_surfaced_as_a_structured_error_event(monkeypatch, logged):
    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(1, "", "HTTP Error 503"))
    with pytest.raises(yt.YouTubeEnumerationError):
        yt.enumerate_newest_first("@c", keyword_filter=None)
    (record,) = [r for r in logged if r["event"] == "adapter.enumerate_failed"]
    assert record["level"] == "error"
    assert record["platform"] == "youtube" and record["handle"] == "@c" and record["tab"] == "videos"


def test_empty_stdout_with_a_zero_exit_raises_rather_than_reporting_a_quiet_day(monkeypatch):
    """The B-10(a) aftermath: a dead reader thread now yields "" not None,
    and "" from a supposedly successful run is a failure, not an empty channel."""
    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(0, "", ""))
    with pytest.raises(yt.YouTubeEnumerationError):
        yt.enumerate_newest_first("@c", keyword_filter=None)


def test_unparseable_listing_json_raises_the_typed_error(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp", lambda *a, **k: _proc(0, "{not json", ""))
    with pytest.raises(yt.YouTubeEnumerationError):
        yt.enumerate_newest_first("@c", keyword_filter=None)


def test_absent_shorts_tab_is_still_a_legitimate_empty(monkeypatch, logged):
    def fake_run(args, *, label, binary=None):
        if args[-1].endswith("/shorts"):
            return _proc(1, "", "ERROR: [youtube:tab] @c: This channel does not have a shorts tab")
        return _proc(0, json.dumps({"entries": [{"id": "v1", "title": "v"}]}), "")

    monkeypatch.setattr(yt, "_run_ytdlp", fake_run)
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {"v1": "2026-07-01"})
    assert [i["id"] for i in yt.enumerate_newest_first("@c", None)] == ["v1"]
    assert not [r for r in logged if r["level"] == "error"]


def test_a_failing_shorts_tab_is_not_treated_as_an_absent_one(monkeypatch):
    """A 429 on /shorts must never be laundered into "this channel has no Shorts"."""
    def fake_run(args, *, label, binary=None):
        if args[-1].endswith("/shorts"):
            return _proc(1, "", "ERROR: unable to download API page: HTTP Error 429")
        return _proc(0, json.dumps({"entries": [{"id": "v1", "title": "v"}]}), "")

    monkeypatch.setattr(yt, "_run_ytdlp", fake_run)
    with pytest.raises(yt.YouTubeEnumerationError):
        yt.enumerate_newest_first("@c", None)
```

- [ ] **Run** → every one fails; the current `_enumerate_tab` returns `[]` for all of them.
- [ ] **Implement:**

```python
class YouTubeEnumerationError(RuntimeError):
    """A channel-tab listing could not be fetched.

    Never raised for a tab that genuinely does not exist, and never for a tab
    that exists and is empty -- those return []. brightdata_job.py:6-10 states
    the invariant: an empty list means "the walk completed and there was
    nothing there". Returning [] on a failed fetch made a bot-block, a DNS
    outage and a quiet channel one indistinguishable state, which the engine
    recorded as the healthy 'no_new_content' (B-11).
    """


# yt-dlp exits non-zero both for "this tab does not exist" and for "the fetch
# failed". Only /shorts is legitimately absent -- every channel has /videos --
# and only these stderr shapes mean absence. Anything else is a failure.
_ABSENT_TAB_MARKERS = (
    "does not have a shorts tab",
    "this channel does not have",
    "http error 404",
)


def _is_absent_tab(tab: str, stderr: str) -> bool:
    if tab != "shorts":
        return False
    lowered = stderr.lower()
    return any(marker in lowered for marker in _ABSENT_TAB_MARKERS)


def _enumerate_tab(handle: str, tab: str, content_type: str) -> list[dict]:
    url = f"https://www.youtube.com/{handle}/{tab}"
    proc = _run_ytdlp(
        ["-J", "--flat-playlist", "--ignore-errors", *_cookie_args(), url],
        label=f"enumerate {handle}/{tab}",
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        if _is_absent_tab(tab, proc.stderr):
            return []
        detail = proc.stderr.strip()[:200] or f"exit {proc.returncode}, empty stdout"
        obs.log("adapter.enumerate_failed", level="error", platform="youtube",
                handle=handle, tab=tab, returncode=proc.returncode, stderr=detail)
        print(f"  !! yt-dlp enumerate failed for {handle}/{tab}: {detail}", file=sys.stderr)
        raise YouTubeEnumerationError(f"{handle}/{tab}: {detail}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        obs.log("adapter.enumerate_failed", level="error", platform="youtube",
                handle=handle, tab=tab, returncode=proc.returncode, stderr=str(exc)[:200])
        raise YouTubeEnumerationError(f"{handle}/{tab}: unparseable listing JSON") from exc
    return [
        {"id": e["id"], "title": e.get("title") or e["id"], "published": None,
         "content_type": content_type}
        for e in (data.get("entries") or []) if e and e.get("id")
    ]
```

- [ ] **Run** → green. **Commit** `fix(youtube): raise on a failed enumeration instead of reporting a quiet day (B-11)`.

---

### T5 · Without Data API dates, Shorts are kept, not dropped (B-14, F-24)

`discovery_youtube.py:102-110` today drops **every Short** on a key-less run with only a stderr
line. The ordering guarantee genuinely cannot be met without dates — so the fix is to state that
honestly on every item rather than to silently narrow the corpus.

- [ ] **Write the failing tests:**

```python
def test_shorts_are_not_dropped_when_no_api_dates_are_available(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs(
        [{"id": "v1", "title": "v"}, {"id": "v2", "title": "v"}],
        [{"id": "s1", "title": "s"}]))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {})
    ids = [i["id"] for i in yt.enumerate_newest_first("@c", None)]
    assert set(ids) == {"v1", "v2", "s1"}, "no Short may be silently dropped (B-14/F-24)"


def test_undated_enumeration_interleaves_rather_than_concatenating(monkeypatch):
    """Concatenation is what makes the drop invisible: process_handle breaks on
    consecutive-on-disk inside the /videos block and never reaches a Short."""
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs(
        [{"id": "v1", "title": "v"}, {"id": "v2", "title": "v"}],
        [{"id": "s1", "title": "s"}, {"id": "s2", "title": "s"}]))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {})
    assert [i["id"] for i in yt.enumerate_newest_first("@c", None)] == ["v1", "s1", "v2", "s2"]


def test_undated_enumeration_marks_its_order_approximate(monkeypatch, logged):
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs(
        [{"id": "v1", "title": "v"}], [{"id": "s1", "title": "s"}]))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {})
    items = yt.enumerate_newest_first("@c", None)
    assert {i["order_confidence"] for i in items} == {"approximate"}
    assert [r for r in logged if r["event"] == "adapter.ordering_degraded"
            and r["level"] == "warning" and r["shorts"] == 1]


def test_dated_enumeration_marks_its_order_exact(monkeypatch):
    monkeypatch.setattr(yt, "_run_ytdlp", _fake_tabs([{"id": "v1", "title": "v"}], []))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {"v1": "2026-07-01"})
    assert yt.enumerate_newest_first("@c", None)[0]["order_confidence"] == "exact"
```

- [ ] **Run** → fails; `items = videos` still discards the Shorts.
- [ ] **Implement**, replacing the `elif per_tab["short"]:` block:

```python
import itertools


def _interleave(videos: list[dict], shorts: list[dict]) -> list[dict]:
    """Merge two independently newest-first tabs with no dates to order by.

    Round-robin, not concatenation. Concatenation puts every Short after every
    video, so process_handle's consecutive-on-disk break ends the walk inside
    the /videos block and no Short is ever reached -- which is why the previous
    code dropped them outright instead. Round-robin is not a true global order
    (that is impossible without dates), so callers get order_confidence
    "approximate" and the condition is reported rather than silently narrowing
    the capture (B-14).
    """
    return [i for pair in itertools.zip_longest(videos, shorts)
            for i in pair if i is not None]
```

```python
    dates = youtube_api.fetch_upload_dates([i["id"] for i in items])
    if dates:
        for item in items:
            item["published"] = dates.get(item["id"])
            item["order_confidence"] = "exact"
        items.sort(key=lambda i: i["published"] or "", reverse=True)
    else:
        if per_tab["short"]:
            obs.log("adapter.ordering_degraded", level="warning", platform="youtube",
                    handle=handle, shorts=len(per_tab["short"]), videos=len(videos))
            print(f"  ! no Data API dates for {handle}: Shorts and videos cannot be "
                  f"date-ordered, so the merged list is approximate. Set YOUTUBE_API_KEY "
                  f"for an exact order.", file=sys.stderr)
        items = _interleave(videos, per_tab["short"])
        for item in items:
            item["order_confidence"] = "approximate"
```

- [ ] **Run** → green (this deletes `test_without_api_dates_falls_back_to_videos_only_and_warns`,
      see §5). **Commit** `fix(youtube): keep Shorts when Data API dates are unavailable (B-14, F-24)`.

---

### T6 · The "no Data API key" warning fires once per process (B-15)

- [ ] **Write the failing test** in `test_discovery_youtube_api.py`:

```python
def test_no_key_warning_is_printed_once_per_process(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv(api.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(api, "KEY_FILE", tmp_path / "absent.txt")
    monkeypatch.setattr(api, "_NO_KEY_WARNED", False)
    for _ in range(50):
        api.fetch_metadata(["v1"])
    assert capsys.readouterr().err.count("no YouTube Data API key") == 1
```

- [ ] **Run** → `assert 50 == 1`.
- [ ] **Implement:**

```python
# One fact about the environment, not a per-video event: fetch_one() calls
# fetch_metadata() once per video from both download_item and
# peek_upload_date, so an unguarded warning emits hundreds of identical lines
# and drowns the escalations that matter (B-15). Mirrors
# discovery_youtube._TRANSCRIPT_API_MISSING_WARNED.
_NO_KEY_WARNED = False


def _warn_no_key(caller: str) -> None:
    global _NO_KEY_WARNED
    obs.log("adapter.api_key_missing", level="warning", platform="youtube",
            caller=caller, env_var=KEY_ENV_VAR)
    if _NO_KEY_WARNED:
        return
    _NO_KEY_WARNED = True
    print(f"  ! no YouTube Data API key ({KEY_ENV_VAR} env var or {KEY_FILE.name}) "
          f"-- falling back to yt-dlp for metadata", file=sys.stderr)
```

and in `fetch_metadata`, replace the inline `print` with `_warn_no_key("fetch_metadata")`.

- [ ] **Run** → green. Update `test_fetch_metadata_returns_empty_without_key` to reset
      `_NO_KEY_WARNED` first. **Commit** `fix(youtube-api): warn once per process about a missing key (B-15)`.

---

### T7 · `fetch_upload_dates` reports its no-key path (B-14, F-24)

25 statements, never named in the 19-test file. Its silent `{}` is what collapses the ordering.

- [ ] **Write the failing tests:**

```python
def test_fetch_upload_dates_reports_a_missing_key_instead_of_returning_silently(
        monkeypatch, tmp_path, logged):
    monkeypatch.delenv(api.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(api, "KEY_FILE", tmp_path / "absent.txt")
    monkeypatch.setattr(api, "_NO_KEY_WARNED", False)
    assert api.fetch_upload_dates(["v1"]) == {}
    (record,) = [r for r in logged if r["event"] == "adapter.api_key_missing"]
    assert record["level"] == "warning" and record["caller"] == "fetch_upload_dates"


def test_fetch_upload_dates_maps_ids_to_dates(monkeypatch):
    monkeypatch.setattr(api, "_http_get_json",
                        lambda url, key=None: {"items": [_api_item(id="v1"), _api_item(id="v2")]})
    assert api.fetch_upload_dates(["v1", "v2"], key="k") == {
        "v1": "2025-08-16", "v2": "2025-08-16"}


def test_fetch_upload_dates_batches_at_50(monkeypatch):
    calls = []
    monkeypatch.setattr(api, "_http_get_json",
                        lambda url, key=None: calls.append(url) or {"items": []})
    api.fetch_upload_dates([f"v{i}" for i in range(120)], key="k")
    assert len(calls) == 3


def test_fetch_upload_dates_omits_ids_with_a_malformed_publishedAt(monkeypatch):
    monkeypatch.setattr(api, "_http_get_json", lambda url, key=None: {"items": [
        {"id": "good", "snippet": {"publishedAt": "2026-07-01T00:00:00Z"}},
        {"id": "short", "snippet": {"publishedAt": "2026"}},
        {"id": "none", "snippet": {}},
    ]})
    assert api.fetch_upload_dates(["good", "short", "none"], key="k") == {"good": "2026-07-01"}


def test_fetch_upload_dates_survives_a_failed_batch(monkeypatch):
    responses = [None, {"items": [{"id": "v99", "snippet": {"publishedAt": "2026-07-01T00:00:00Z"}}]}]
    monkeypatch.setattr(api, "_http_get_json", lambda url, key=None: responses.pop(0))
    assert api.fetch_upload_dates([f"v{i}" for i in range(60)], key="k") == {"v99": "2026-07-01"}
```

- [ ] **Run** → the first fails (no log record); the rest fail on `_http_get_json`'s signature
      until T8 lands, so write T8's signature change into this task's implementation or run T8 first.
      **Order T7 before T8 and use `lambda url, key=None:` from the start**, so T8 is a pure move.
- [ ] **Implement** — one line in `fetch_upload_dates`:

```python
    key = key or api_key()
    if not key:
        _warn_no_key("fetch_upload_dates")
        return {}
```

- [ ] **Run** → green. **Commit** `test(youtube-api): cover fetch_upload_dates and report its no-key path (F-24, B-14)`.

---

### T8 · The Data API key travels in a header, not the URL (D-52)

- [ ] **Write the failing tests:**

```python
def test_api_key_never_appears_in_the_request_url(monkeypatch):
    seen = {}
    monkeypatch.setattr(api, "_http_get_json",
                        lambda url, key=None: seen.update(url=url, key=key) or {"items": []})
    api.fetch_metadata(["v1"], key="SECRET-KEY")
    assert "SECRET-KEY" not in seen["url"]
    assert "key=" not in seen["url"]
    assert seen["key"] == "SECRET-KEY"


def test_http_get_json_sends_the_key_as_a_header(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"items": []}'

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        return FakeResponse()

    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)
    api._http_get_json("https://example.test?part=snippet", key="SECRET-KEY")
    assert "SECRET-KEY" not in captured["url"]
    assert captured["headers"]["X-goog-api-key"] == "SECRET-KEY"


def test_an_unexpected_exception_cannot_leak_the_key_in_its_traceback(monkeypatch):
    def boom(req, timeout):
        raise ValueError(f"unknown url type: {req.full_url}")

    monkeypatch.setattr(api.urllib.request, "urlopen", boom)
    with pytest.raises(ValueError) as exc:
        api._http_get_json("https://example.test?part=snippet", key="SECRET-KEY")
    assert "SECRET-KEY" not in str(exc.value)
```

- [ ] **Run** → all three fail; the key is interpolated into the query string today.
- [ ] **Implement:**

```python
def _http_get_json(url: str, key: str | None = None) -> dict | None:
    """Isolated for monkeypatching in tests.

    The key goes in X-goog-api-key, never in the query string: the two except
    clauses below are careful not to print the URL, but any exception outside
    them escapes with the full URL -- and therefore the live key -- in a
    traceback the discovery cron writes to its log (D-52). Bright Data and
    Resend are already header-borne; this was the one that was not.
    """
    headers = {"X-goog-api-key": key} if key else {}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    ...
```

and drop `"key": key` from both `urlencode` dicts, passing `key` through instead:
`payload = _http_get_json(f"{API_URL}?{query}", key)` in `fetch_metadata` and `fetch_upload_dates`.

- [ ] Update the four existing `lambda url: ...` stubs in this file to `lambda url, key=None: ...`
      and `raise_403(url, timeout)` to `raise_403(request, timeout)`.
- [ ] **Run** → green. **Commit** `fix(youtube-api): send the key in X-goog-api-key, not the URL (D-52)`.

---

### T9 · A blocked transcript is not an absent transcript (B-13)

- [ ] **Write the failing tests** in `test_discovery_youtube.py`:

```python
def _install_fake_transcript_api(monkeypatch, exc_names, raising):
    """Install a stand-in youtube_transcript_api whose fetch() raises `raising`."""
    module = type(sys)("youtube_transcript_api")
    for name in exc_names:
        setattr(module, name, type(name, (Exception,), {}))

    class FakeApi:
        def fetch(self, vid):
            raise getattr(module, raising)("boom")

    module.YouTubeTranscriptApi = FakeApi
    monkeypatch.setitem(sys.modules, "youtube_transcript_api", module)
    return module


_EXC_NAMES = ("TranscriptsDisabled", "NoTranscriptFound", "VideoUnavailable",
              "IpBlocked", "RequestBlocked", "TooManyRequests", "YouTubeRequestFailed")


def test_a_genuinely_captionless_video_returns_none(monkeypatch):
    _install_fake_transcript_api(monkeypatch, _EXC_NAMES, "TranscriptsDisabled")
    assert yt._fetch_transcript_fallback("v1") is None


@pytest.mark.parametrize("blocked", ["IpBlocked", "RequestBlocked", "TooManyRequests",
                                     "YouTubeRequestFailed"])
def test_a_blocked_transcript_fetch_raises(monkeypatch, blocked):
    _install_fake_transcript_api(monkeypatch, _EXC_NAMES, blocked)
    with pytest.raises(yt.TranscriptFetchBlocked):
        yt._fetch_transcript_fallback("v1")


def test_blocked_is_distinguishable_from_captionless(monkeypatch):
    _install_fake_transcript_api(monkeypatch, _EXC_NAMES, "NoTranscriptFound")
    assert yt._fetch_transcript_fallback("v1") is None
    _install_fake_transcript_api(monkeypatch, _EXC_NAMES, "IpBlocked")
    with pytest.raises(yt.TranscriptFetchBlocked):
        yt._fetch_transcript_fallback("v1")


def test_an_unrecognised_transcript_exception_is_treated_as_blocked(monkeypatch, logged):
    """Fail toward retryable. Mis-classifying a block as "no captions" writes a
    permanent transcript-less capture (B-12); the reverse costs one retry."""
    _install_fake_transcript_api(monkeypatch, (*_EXC_NAMES, "SomeNewLibraryError"),
                                 "SomeNewLibraryError")
    with pytest.raises(yt.TranscriptFetchBlocked):
        yt._fetch_transcript_fallback("v1")
    assert [r for r in logged if r["event"] == "adapter.transcript_error_unclassified"]
```

- [ ] **Run** → `AttributeError: ... has no attribute 'TranscriptFetchBlocked'`.
- [ ] **Implement:**

```python
class TranscriptFetchBlocked(RuntimeError):
    """The transcript API refused or could not be reached.

    Distinct from "this video has no captions". The bare `except Exception:
    return None` collapsed IP-blocks, rate-limits, disabled transcripts and
    video-unavailable into one None, so an IP block during a 300-video run
    produced 300 permanently transcript-less captures indistinguishable from
    300 genuinely caption-free videos (B-13).
    """


# Exceptions that mean "there is no transcript for this video" -- a real,
# terminal answer. Resolved by name because the library's exception surface
# varies across versions and the import is lazy. Anything NOT named here is
# treated as a block: failing toward retryable costs one extra attempt, while
# failing the other way is B-12.
_BENIGN_TRANSCRIPT_ERRORS = (
    "TranscriptsDisabled", "NoTranscriptFound", "NoTranscriptAvailable",
    "VideoUnavailable", "VideoUnplayable",
)


def _is_benign_transcript_error(module, exc: BaseException) -> bool:
    classes = tuple(
        cls for cls in (getattr(module, name, None) for name in _BENIGN_TRANSCRIPT_ERRORS)
        if isinstance(cls, type) and issubclass(cls, BaseException)
    )
    return bool(classes) and isinstance(exc, classes)
```

and the body of `_fetch_transcript_fallback`:

```python
    try:
        import youtube_transcript_api as _yta
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        ...unchanged warn-once branch...
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id)
        parts = [getattr(s, "text", "") for s in fetched]
        text = "\n".join(t for t in (p.strip() for p in parts) if t)
        return text or None
    except Exception as exc:  # noqa: BLE001 - re-classified, not swallowed
        if _is_benign_transcript_error(_yta, exc):
            return None
        obs.log("adapter.transcript_error_unclassified", level="warning",
                platform="youtube", video_id=video_id, error=type(exc).__name__)
        raise TranscriptFetchBlocked(
            f"{type(exc).__name__} while fetching transcript for {video_id}") from exc
```

The `# noqa: BLE001` is not widened: the catch stays, the *telling* is what changed.

- [ ] **Run** → green. **Commit** `fix(youtube): distinguish a blocked transcript fetch from an absent one (B-13)`.

---

### T10 · A blocked capture is written as `pending_retry`, not `missing` (B-12)

- [ ] **Write the failing tests:**

```python
def test_bot_blocked_download_with_api_metadata_is_marked_retryable(monkeypatch, tmp_path, logged):
    """The B-12 configuration exactly: stale cookies.txt + a working API key."""
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_blocked)
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    monkeypatch.setattr(yt.youtube_api, "fetch_one", lambda *a, **k: dict(_API_RECORD))

    result = yt.download_item(tmp_path, "@testhandle", "v1", "T")
    assert result["ok"] is True                       # the metadata is real and worth keeping
    meta, _ = _written(tmp_path, "v1")
    assert meta["transcript_status"] == "pending_retry"
    assert meta["transcript_attempts"] == 1
    assert [r for r in logged if r["event"] == "adapter.transcript_pending_retry"]


def test_a_captionless_video_is_terminal_not_retryable(monkeypatch, tmp_path):
    """The distinguishability test: yt-dlp ran clean and the video simply has
    no captions. That is an answer, not a failure."""
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "v2", "T")
    meta, _ = _written(tmp_path, "v2")
    assert meta["transcript_status"] == "missing"
    assert meta["transcript_attempts"] == 0


def test_a_blocked_transcript_api_also_marks_pending_retry(monkeypatch, tmp_path):
    def blocked(*a, **k):
        raise yt.TranscriptFetchBlocked("IpBlocked")

    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", blocked)
    yt.download_item(tmp_path, "@testhandle", "v3", "T")
    meta, _ = _written(tmp_path, "v3")
    assert meta["transcript_status"] == "pending_retry"


def test_attempts_accumulate_and_the_status_becomes_terminal_at_the_cap(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_blocked)
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    monkeypatch.setattr(yt.youtube_api, "fetch_one", lambda *a, **k: dict(_API_RECORD))
    for _ in range(yt.MAX_TRANSCRIPT_ATTEMPTS):
        yt.download_item(tmp_path, "@testhandle", "v4", "T")
    meta, _ = _written(tmp_path, "v4")
    assert meta["transcript_attempts"] == yt.MAX_TRANSCRIPT_ATTEMPTS
    assert meta["transcript_status"] == "missing"      # bounded: never loops forever


def test_a_recovered_transcript_clears_the_pending_state(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_blocked)
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    monkeypatch.setattr(yt.youtube_api, "fetch_one", lambda *a, **k: dict(_API_RECORD))
    yt.download_item(tmp_path, "@testhandle", "v5", "T")
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: "the real transcript")
    yt.download_item(tmp_path, "@testhandle", "v5", "T")
    meta, body = _written(tmp_path, "v5")
    assert meta["transcript_status"] == "present"
    assert "the real transcript" in body
```

- [ ] **Run** → fails; today the first case writes `transcript_status: "missing"`.
- [ ] **Implement:**

```python
MAX_TRANSCRIPT_ATTEMPTS = 3

TRANSCRIPT_PRESENT = "present"
TRANSCRIPT_MISSING = "missing"        # terminal: yt-dlp ran clean and there are no captions
TRANSCRIPT_PENDING = "pending_retry"  # transient: the fetch was blocked, try again next run


def _prior_transcript_attempts(dest: Path) -> int:
    if not dest.exists():
        return 0
    try:
        meta, _ = artifacts.parse_frontmatter(dest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    value = meta.get("transcript_attempts")
    return value if isinstance(value, int) and value >= 0 else 0
```

in `download_item`, after `dest` is computed and before `meta` is built:

```python
    transcript_blocked = False
    if not transcript:
        try:
            fb = _fetch_transcript_fallback(video_id)
        except TranscriptFetchBlocked as exc:
            transcript_blocked = True
            obs.log("adapter.transcript_blocked", level="warning", platform="youtube",
                    handle=handle, video_id=video_id, reason=str(exc))
        else:
            if fb:
                transcript, source = fb, "youtube-transcript-api"

    attempts = _prior_transcript_attempts(dest)
    if transcript.strip():
        status = TRANSCRIPT_PRESENT
    elif transcript_blocked or not ytdlp_ok:
        # Metadata succeeded but no transcript was OBTAINED -- not the same as
        # a video that has none. on_disk_ids() re-offers this item so the next
        # run tries again, bounded by MAX_TRANSCRIPT_ATTEMPTS so a genuinely
        # transcript-less video cannot loop forever (B-12).
        attempts += 1
        status = TRANSCRIPT_PENDING if attempts < MAX_TRANSCRIPT_ATTEMPTS else TRANSCRIPT_MISSING
        obs.log("adapter.transcript_pending_retry", level="warning", platform="youtube",
                handle=handle, video_id=video_id, attempts=attempts, final=status)
    else:
        status = TRANSCRIPT_MISSING
```

and in the `meta` dict: `"transcript_status": status, "transcript_attempts": attempts,`.
The existing `_fetch_transcript_fallback` call site above the metadata block is deleted — this
replaces it.

- [ ] **Run** → green. **Commit** `fix(youtube): mark a blocked capture retryable instead of permanently missing (B-12)`.

---

### T11 · `on_disk_ids` re-offers a `pending_retry` capture (B-12)

Without this, T10 is a label with no effect.

- [ ] **Write the failing tests:**

```python
def test_on_disk_ids_re_offers_a_pending_retry_capture(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_blocked)
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    monkeypatch.setattr(yt.youtube_api, "fetch_one", lambda *a, **k: dict(_API_RECORD))
    yt.download_item(tmp_path, "@testhandle", "blocked", "T")
    assert yt.on_disk_ids(tmp_path, "@testhandle") == set()


def test_on_disk_ids_keeps_a_terminal_capture(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "captionless", "T")
    assert yt.on_disk_ids(tmp_path, "@testhandle") == {"captionless"}


def test_on_disk_ids_treats_an_unreadable_file_as_captured(tmp_path, logged):
    """Fail toward not re-downloading: an unreadable file is an operator
    problem, not a licence to re-pay for the whole back catalogue."""
    directory = tmp_path / "output" / "brand-intel" / "youtube" / "testhandle"
    directory.mkdir(parents=True)
    (directory / "weird__t.md").write_bytes(b"\xff\xfe not frontmatter")
    assert yt.on_disk_ids(tmp_path, "@testhandle") == {"weird"}
    assert [r for r in logged if r["event"] == "adapter.capture_unreadable"]
```

- [ ] **Run** → the first fails: `on_disk_ids` reads filenames only.
- [ ] **Implement:**

```python
def _awaiting_transcript_retry(path: Path) -> bool:
    try:
        meta, _ = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        obs.log("adapter.capture_unreadable", level="warning", platform="youtube",
                path=str(path), error=type(exc).__name__)
        return False
    return meta.get("transcript_status") == TRANSCRIPT_PENDING


def on_disk_ids(repo_root: Path, handle: str) -> set[str]:
    """Video ids already fully captured for `handle`.

    A capture whose transcript is pending_retry is deliberately NOT reported:
    it exists on disk but is incomplete, and returning it here is what made a
    bot-blocked capture permanent (B-12). download_item writes to the same
    dest path, so re-offering is idempotent.
    """
    directory = handle_dir(repo_root, "youtube", handle)
    if not directory.exists():
        return set()
    return {
        path.name.split("__", 1)[0]
        for path in directory.glob("*__*.md")
        if not _awaiting_transcript_retry(path)
    }
```

- [ ] **Run** → green. **Commit** `fix(youtube): re-offer pending_retry captures from on_disk_ids (B-12)`.

---

### T12 · YouTube frontmatter carries `published` as well as `upload_date` (B-04)

- [ ] **Write the failing test:**

```python
def test_frontmatter_carries_both_published_and_upload_date(monkeypatch, tmp_path):
    """The platform contract names `published`; YouTube only wrote upload_date,
    which works solely because discovery_digest carries a YouTube-shaped
    fallback. Emit both: `published` for the contract, `upload_date` so files
    already on disk keep their spelling (B-04)."""
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({"upload_date": "20260415"}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "v1", "T")
    meta, _ = _written(tmp_path, "v1")
    assert meta["published"] == "2026-04-15"
    assert meta["upload_date"] == "2026-04-15"


def test_both_date_keys_are_none_together_when_no_date_is_known(monkeypatch, tmp_path):
    monkeypatch.setattr(yt, "_run_ytdlp", _ytdlp_ok({}))
    monkeypatch.setattr(yt, "_fetch_transcript_fallback", lambda *a, **k: None)
    yt.download_item(tmp_path, "@testhandle", "v2", "T")
    meta, _ = _written(tmp_path, "v2")
    assert meta["published"] is None and meta["upload_date"] is None
```

- [ ] **Run** → `KeyError: 'published'`.
- [ ] **Implement** in the `meta` dict:

```python
        # Two spellings of one date, deliberately. `published` is the platform
        # contract's field name (CLAUDE.md); `upload_date` is what every file
        # already on disk uses, and discovery_digest's fallback reads it. See
        # the P9 contract note in this plan before removing either.
        "published": upload_date or None,
        "upload_date": upload_date or None,
```

- [ ] **Run** → green. **Commit** `fix(youtube): emit the contract's published key alongside upload_date (B-04)`.

---

### T13 · Bluesky raises on a transport failure — and F-12 is inverted (B-05, F-12)

- [ ] **Delete** `pipeline-app/tests/test_discovery_bluesky.py:56-60`
      (`test_enumerate_newest_first_returns_empty_on_fetch_failure`) — see §5.
- [ ] **Write the replacement tests** in its place:

```python
import pytest


def test_enumerate_newest_first_raises_on_fetch_failure(monkeypatch):
    """Inverts the test that used to live here.

    brightdata_job.py:6-10 states the invariant for every adapter: a failed
    fetch MUST raise, never return []. The old test asserted the opposite and
    froze B-05 and B-06 in place -- B-06 permanently disables a valid handle
    after one momentary outage.
    """
    def raise_error(url):
        raise OSError("network down")

    monkeypatch.setattr(bsky, "_http_get", raise_error)
    with pytest.raises(bsky.BlueskyFetchError) as exc:
        bsky.enumerate_newest_first("dead.bsky.social", keyword_filter=None)
    assert "dead.bsky.social" in str(exc.value)


def test_a_fetch_failure_is_distinguishable_from_an_empty_feed(monkeypatch):
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps({"feed": []}).encode("utf-8"))
    assert bsky.enumerate_newest_first("quiet.bsky.social", keyword_filter=None) == []

    def raise_error(url):
        raise OSError("network down")

    monkeypatch.setattr(bsky, "_http_get", raise_error)
    with pytest.raises(bsky.BlueskyFetchError):
        bsky.enumerate_newest_first("quiet.bsky.social", keyword_filter=None)


def test_a_fetch_failure_is_surfaced_as_a_structured_error_event(monkeypatch, logged):
    def raise_error(url):
        raise OSError("network down")

    monkeypatch.setattr(bsky, "_http_get", raise_error)
    with pytest.raises(bsky.BlueskyFetchError):
        bsky.enumerate_newest_first("dead.bsky.social", keyword_filter=None)
    (record,) = [r for r in logged if r["event"] == "adapter.enumerate_failed"]
    assert record["level"] == "error" and record["platform"] == "bluesky"
    assert record["handle"] == "dead.bsky.social" and record["error"] == "OSError"


def test_malformed_json_raises_rather_than_reporting_an_empty_feed(monkeypatch):
    monkeypatch.setattr(bsky, "_http_get", lambda url: b"{not json")
    with pytest.raises(bsky.BlueskyFetchError):
        bsky.enumerate_newest_first("x.bsky.social", keyword_filter=None)
```

- [ ] **Run** → `AttributeError: ... has no attribute 'BlueskyFetchError'`.
- [ ] **Implement** in `discovery_bluesky.py`:

```python
from pipeline_app import obs


class BlueskyFetchError(RuntimeError):
    """A getAuthorFeed page could not be fetched or parsed.

    The bare `except Exception: break` this replaces made DNS failure,
    connection reset, HTTP error, timeout and malformed JSON produce the same
    [] a genuinely quiet account produces -- which discovery_engine records as
    the healthy 'no_new_content', and which process_handle_validate turns into
    a permanent status='invalid', included=False for a perfectly good handle
    (B-05, B-06). brightdata_job.py:6-10 states the invariant this restores.
    """
```

and in `enumerate_newest_first`:

```python
        try:
            raw = _http_get(f"{BLUESKY_API}?{urllib.parse.urlencode(params)}")
            data = json.loads(raw)
        except Exception as exc:  # noqa: BLE001 - re-raised as a typed error, not swallowed
            obs.log("adapter.enumerate_failed", level="error", platform="bluesky",
                    handle=handle, page=page_index, pages_walked=page_index,
                    error=type(exc).__name__)
            print(f"  !! bluesky enumerate failed for {handle} on page {page_index + 1}: "
                  f"{type(exc).__name__}", file=sys.stderr)
            raise BlueskyFetchError(
                f"{handle}: page {page_index + 1} of {page_limit} failed "
                f"({type(exc).__name__})") from exc
```

with `for page_index in range(page_limit):` replacing `for _ in range(page_limit):`, and
`import sys` added.

- [ ] **Run** → green. **Commit** `fix(bluesky): raise on a transport failure instead of returning an empty feed (B-05, F-12)`.

---

### T14 · A partial multi-page walk is never presented as a complete one (B-05)

- [ ] **Write the failing test:**

```python
def test_a_failure_mid_pagination_raises_rather_than_truncating_the_walk(monkeypatch):
    """A failure on page 3 of 5 used to return pages 1-2 as if the walk had
    completed, silently shortening a new handle's 90-day lookback."""
    pages = [
        {"feed": [_post("rkey1", "2026-07-29")], "cursor": "p2"},
        {"feed": [_post("rkey2", "2026-07-28")], "cursor": "p3"},
    ]
    calls = {"n": 0}

    def flaky(url):
        calls["n"] += 1
        if calls["n"] > len(pages):
            raise TimeoutError("appview timeout")
        return json.dumps(pages[calls["n"] - 1]).encode("utf-8")

    monkeypatch.setattr(bsky, "_http_get", flaky)
    with pytest.raises(bsky.BlueskyFetchError) as exc:
        bsky.enumerate_newest_first("x.bsky.social", keyword_filter=None)
    assert "page 3" in str(exc.value)


def test_a_complete_short_walk_is_not_a_failure(monkeypatch):
    """Distinguishability: a feed that runs out of cursor before page_limit is
    a completed walk, and must still return normally."""
    pages = [{"feed": [_post("rkey1", "2026-07-29")]}]
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(pages[0]).encode("utf-8"))
    assert [i["id"] for i in bsky.enumerate_newest_first("x.bsky.social", None)] == ["rkey1"]
```

with a helper near the top of the file:

```python
def _post(rkey: str, day: str, text: str = "hello") -> dict:
    return {"post": {"uri": f"at://did/app.bsky.feed.post/{rkey}",
                     "record": {"text": text, "createdAt": f"{day}T10:00:00Z"}}}
```

- [ ] **Run** → passes already if T13 landed cleanly; if it does not, the `break`-on-empty-feed
      path is still short-circuiting. Confirm the failure is on the `"page 3"` message before
      touching code.
- [ ] **Implement** — the page index in the message comes from T13; no further change expected.
      Keep the task so the invariant has its own named test.
- [ ] **Run** → green. **Commit** `test(bluesky): a partial page walk must not present as complete (B-05)`.

---

### T15 · A transient failure cannot mark a valid handle invalid (B-06)

The engine's validate path is P8's file; the adapter-side guarantee is that the two states never
share a return value, which is what lets `discovery_engine.py:272`'s error branch fire instead of
`:255`'s auto-exclude.

- [ ] **Write the failing tests:**

```python
def test_validate_shaped_call_raises_on_a_transient_failure(monkeypatch):
    """process_handle_validate treats an empty enumerate as ok:False and
    run_discovery then sets status='invalid' AND included=False, permanently,
    with nothing ever retrying it. A blip must therefore never look empty."""
    def blip(url):
        raise ConnectionResetError("reset by peer")

    monkeypatch.setattr(bsky, "_http_get", blip)
    with pytest.raises(bsky.BlueskyFetchError):
        bsky.enumerate_newest_first("valid.bsky.social", keyword_filter=None, page_limit=1)


def test_a_genuinely_nonexistent_actor_still_returns_empty(monkeypatch):
    """The legitimate invalid-handle case the auto-exclude exists for: the
    AppView answers, with an empty feed. This must NOT raise, or a real typo
    would be recorded as an infrastructure error."""
    monkeypatch.setattr(bsky, "_http_get",
                        lambda url: json.dumps({"feed": []}).encode("utf-8"))
    assert bsky.enumerate_newest_first("typo.bsky.social", keyword_filter=None) == []


def test_the_two_validate_outcomes_have_different_types(monkeypatch):
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps({"feed": []}).encode("utf-8"))
    empty = bsky.enumerate_newest_first("typo.bsky.social", None)

    def blip(url):
        raise ConnectionResetError("reset by peer")

    monkeypatch.setattr(bsky, "_http_get", blip)
    with pytest.raises(bsky.BlueskyFetchError) as exc:
        bsky.enumerate_newest_first("valid.bsky.social", None)
    assert empty == [] and isinstance(exc.value, bsky.BlueskyFetchError)
```

- [ ] **Run** → green if T13 is correct. If any passes trivially, tighten it before proceeding —
      a test that cannot fail proves nothing.
- [ ] **Implement** — no production change expected; this task exists to name B-06's invariant.
      **Note for P8:** `discovery_engine.py`'s validate path must now let `BlueskyFetchError`
      reach its `except` branch at `:272` rather than converting it to `invalid`/`included=False`.
- [ ] **Commit** `test(bluesky): a blip must not permanently disable a valid handle (B-06)`.

---

### T16 · The keyword filter reads the whole post, not the first 60 characters (B-08)

- [ ] **Write the failing test:**

```python
def test_keyword_filter_matches_beyond_the_first_sixty_characters(monkeypatch):
    """`title` is text[:60] for display; every other text-bearing adapter
    filters the full body. A keyword past character 60 was silently
    non-matching, producing a quietly under-populated capture (B-08)."""
    long_text = ("x" * 90) + " permaculture"
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(
        {"feed": [_post("rkey1", "2026-07-29", long_text)]}).encode("utf-8"))
    items = bsky.enumerate_newest_first("x.bsky.social", keyword_filter="permaculture")
    assert [i["id"] for i in items] == ["rkey1"]


def test_keyword_filter_still_excludes_a_genuine_non_match(monkeypatch):
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(
        {"feed": [_post("rkey1", "2026-07-29", "nothing relevant here")]}).encode("utf-8"))
    assert bsky.enumerate_newest_first("x.bsky.social", keyword_filter="permaculture") == []
```

- [ ] **Run** → the first fails; `keyword_filter in i["title"]` sees only 60 characters.
- [ ] **Implement:**

```python
    if keyword_filter:
        # Filter the full text, not the 60-char display title -- Instagram
        # filters `caption` and LinkedIn/Facebook/X filter `body` (B-08).
        needle = keyword_filter.lower()
        items = [i for i in items if needle in (i.get("text") or "").lower()]
```

- [ ] **Run** → green. **Commit** `fix(bluesky): filter on the full post text, not the truncated title (B-08)`.

---

### T17 · Undated Bluesky rows are dropped and counted, making the peek comment true (B-09)

- [ ] **Write the failing tests:**

```python
def test_a_row_with_no_usable_created_at_is_dropped(monkeypatch, logged):
    """peek_upload_date's comment claims enumerate always populates
    'published'. It did not: a short/absent createdAt yielded None, and for a
    new handle five of those in a row aborted the whole walk with a healthy
    status. The Bright Data adapters drop such rows in _normalize_row; match
    them, and report the drop (B-09)."""
    feed = {"feed": [
        _post("good", "2026-07-29"),
        {"post": {"uri": "at://did/app.bsky.feed.post/bad", "record": {"text": "t", "createdAt": "2026"}}},
        {"post": {"uri": "at://did/app.bsky.feed.post/none", "record": {"text": "t"}}},
    ]}
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(feed).encode("utf-8"))
    items = bsky.enumerate_newest_first("x.bsky.social", None)
    assert [i["id"] for i in items] == ["good"]
    assert all(i["published"] for i in items)
    (record,) = [r for r in logged if r["event"] == "adapter.undated_rows_dropped"]
    assert record["level"] == "warning" and record["count"] == 2


def test_indexed_at_is_accepted_when_created_at_is_absent(monkeypatch):
    feed = {"feed": [{"post": {"uri": "at://did/app.bsky.feed.post/i1",
                               "indexedAt": "2026-07-29T10:00:00Z",
                               "record": {"text": "t"}}}]}
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(feed).encode("utf-8"))
    assert bsky.enumerate_newest_first("x.bsky.social", None)[0]["published"] == "2026-07-29"
```

- [ ] **Run** → fails; the undated rows come back with `published: None`.
- [ ] **Implement:**

```python
            created = record.get("createdAt") or post.get("indexedAt") or ""
            if len(created) < 10:
                undated += 1
                continue
            items.append({"id": rkey, "title": text[:60], "text": text,
                          "published": created[:10]})
```

with `undated = 0` before the loop and, after the walk:

```python
    if undated:
        obs.log("adapter.undated_rows_dropped", level="warning", platform="bluesky",
                handle=handle, count=undated)
```

and the comment on `peek_upload_date` corrected to state why it is now genuinely dead:

```python
def peek_upload_date(item_id: str) -> str | None:
    # Genuinely dead code as of B-09: enumerate_newest_first drops any row it
    # cannot date, so every item it yields carries 'published'. Kept because
    # the PlatformAdapter contract requires the method.
    return None
```

- [ ] **Run** → green. **Commit** `fix(bluesky): drop and report undated rows so published is always set (B-09)`.

---

### T18 · `download_item` reads a cache instead of re-walking the feed (B-07)

- [ ] **Write the failing tests:**

```python
def test_download_item_reuses_the_enumerate_walk(monkeypatch):
    """Downloading N posts cost up to 5(N+1) requests against a public
    unauthenticated endpoint -- 55 round-trips for 10 posts (B-07)."""
    calls = {"n": 0}
    feed = {"feed": [_post(f"rkey{i}", "2026-07-29") for i in range(3)]}

    def counting(url):
        calls["n"] += 1
        return json.dumps(feed).encode("utf-8")

    monkeypatch.setattr(bsky, "_http_get", counting)
    bsky.enumerate_newest_first("x.bsky.social", None)
    before = calls["n"]
    for i in range(3):
        bsky.download_item(tmp_path_factory(), "x.bsky.social", f"rkey{i}", "t")
    assert calls["n"] == before, "download_item must not re-walk the feed"


def test_download_item_reports_a_reason_when_the_item_is_not_found(monkeypatch, tmp_path, logged):
    monkeypatch.setattr(bsky, "_http_get",
                        lambda url: json.dumps({"feed": [_post("other", "2026-07-29")]}).encode("utf-8"))
    bsky.enumerate_newest_first("x.bsky.social", None)
    result = bsky.download_item(tmp_path, "x.bsky.social", "target", "t")
    assert result["ok"] is False
    assert result["reason"] == "not-found-in-feed"
    assert [r for r in logged if r["event"] == "adapter.item_not_found"]


def test_download_item_propagates_a_transport_failure_rather_than_reporting_not_found(
        monkeypatch, tmp_path):
    """A cache miss falls back to one re-fetch. If THAT fails, it is a failure,
    not an aged-out item."""
    bsky.clear_feed_cache()

    def raise_error(url):
        raise OSError("network down")

    monkeypatch.setattr(bsky, "_http_get", raise_error)
    with pytest.raises(bsky.BlueskyFetchError):
        bsky.download_item(tmp_path, "x.bsky.social", "target", "t")


def test_the_cache_holds_unfiltered_rows(monkeypatch, tmp_path):
    """A keyword-filtered enumerate must still be able to serve a download of
    any row it saw, or the filter silently breaks the download path."""
    feed = {"feed": [_post("a", "2026-07-29", "permaculture"), _post("b", "2026-07-28", "other")]}
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(feed).encode("utf-8"))
    bsky.enumerate_newest_first("x.bsky.social", keyword_filter="permaculture")
    assert bsky._FEED_CACHE["x.bsky.social"].keys() == {"a", "b"}
```

(Use the `tmp_path` fixture in the first test rather than the placeholder factory.)

- [ ] **Run** → fails; `download_item` calls `enumerate_newest_first` unconditionally.
- [ ] **Implement:**

```python
# Normalized rows from the last enumerate, keyed by handle then rkey. Matches
# the pattern all four Bright Data adapters already use: enumerate pays for
# the walk once and download_item reads from it, instead of re-walking the
# whole 5-page feed per item (B-07). Populated BEFORE keyword filtering so a
# filtered enumerate can still serve any row it saw.
_FEED_CACHE: dict[str, dict[str, dict]] = {}


def clear_feed_cache(handle: str | None = None) -> None:
    _FEED_CACHE.clear() if handle is None else _FEED_CACHE.pop(handle, None)
```

in `enumerate_newest_first`, immediately before the keyword filter:

```python
    _FEED_CACHE[handle] = {i["id"]: i for i in items}
```

and in `download_item`, replacing the re-walk:

```python
    match = _FEED_CACHE.get(handle, {}).get(rkey)
    if match is None:
        # One bounded re-fetch, then give up with a reason. A transport failure
        # in here raises (B-05) -- "the fetch broke" and "the item aged out of
        # page_limit=5" are different answers and must not share a return value.
        enumerate_newest_first(handle, keyword_filter=None, page_limit=5)
        match = _FEED_CACHE.get(handle, {}).get(rkey)
    if match is None:
        obs.log("adapter.item_not_found", level="warning", platform="bluesky",
                handle=handle, item_id=rkey)
        return {"id": rkey, "ok": False, "published": None, "reason": "not-found-in-feed"}
```

- [ ] Update `test_download_item_returns_ok_false_when_refetch_finds_no_match`
      (`test_discovery_bluesky.py:85-108`) to assert the `reason` key alongside `ok: False`.
- [ ] **Run** → green. **Commit** `fix(bluesky): serve downloads from the enumerate cache with a reason on miss (B-07)`.

---

### T19 · A parametrized native-adapter contract sweep (F-20)

Six adapters, ~185 adapter tests, and no sweep asserting the contract CLAUDE.md and
`brightdata_job.py` both state. This task closes the native half; **P7 extends the same table to
its four Bright Data platforms**, and the guard test below fails loudly if a native platform is
ever added without an entry.

- [ ] **Write the failing tests**, in `test_discovery_bluesky.py` (the file F-20 cites, and the
      file the defect-affirming test lived in), under a `# Native-adapter contract sweep (F-20)`
      heading:

```python
import datetime as _dt

from pipeline_app import discovery_youtube as yt


# platform -> (module, a fixture that makes enumerate raise, a download driver)
_NATIVE_ADAPTERS = {
    "bluesky": bsky,
    "youtube": yt,
}


@pytest.mark.parametrize("platform", sorted(_NATIVE_ADAPTERS))
def test_every_native_adapter_raises_on_a_transport_failure(platform, monkeypatch):
    """The invariant brightdata_job.py:6-10 already enforces for the other four:
    a failed fetch raises; [] means the walk completed and found nothing."""
    module = _NATIVE_ADAPTERS[platform]
    if platform == "bluesky":
        monkeypatch.setattr(module, "_http_get", _raiser(OSError("down")))
    else:
        monkeypatch.setattr(module, "_run_ytdlp", lambda *a, **k: _proc(1, "", "HTTP Error 503"))
    with pytest.raises(Exception) as exc:
        module.enumerate_newest_first("handle.example", keyword_filter=None)
    assert type(exc.value) is not AssertionError
    assert exc.value.args and "handle.example" in str(exc.value)


@pytest.mark.parametrize("platform", sorted(_NATIVE_ADAPTERS))
def test_every_native_adapter_returns_empty_for_a_genuinely_empty_source(platform, monkeypatch):
    module = _NATIVE_ADAPTERS[platform]
    if platform == "bluesky":
        monkeypatch.setattr(module, "_http_get", lambda url: json.dumps({"feed": []}).encode())
    else:
        monkeypatch.setattr(module, "_run_ytdlp",
                            lambda *a, **k: _proc(0, json.dumps({"entries": []}), ""))
        monkeypatch.setattr(module.youtube_api, "fetch_upload_dates", lambda ids, **k: {})
    assert module.enumerate_newest_first("handle.example", keyword_filter=None) == []


@pytest.mark.parametrize("platform", sorted(_NATIVE_ADAPTERS))
def test_every_native_adapter_writes_an_aware_utc_fetched_at(platform, tmp_path, monkeypatch):
    """CLAUDE.md: fetched_at is the only MANDATORY frontmatter field -- it is
    the watermark, and an item without it is excluded from the run forever."""
    meta = _capture_one(platform, tmp_path, monkeypatch)
    stamp = meta["fetched_at"]
    assert isinstance(stamp, str)
    parsed = _dt.datetime.fromisoformat(stamp)
    assert parsed.tzinfo is not None and parsed.utcoffset() == _dt.timedelta(0)
    assert parsed.second == parsed.replace(microsecond=0).second
    assert "." not in stamp, "timespec must be seconds"


@pytest.mark.parametrize("platform", sorted(_NATIVE_ADAPTERS))
def test_every_native_adapter_writes_a_url(platform, tmp_path, monkeypatch):
    assert _capture_one(platform, tmp_path, monkeypatch)["url"].startswith("https://")


@pytest.mark.parametrize("platform", sorted(_NATIVE_ADAPTERS))
def test_every_native_adapter_writes_the_contract_published_key(platform, tmp_path, monkeypatch):
    meta = _capture_one(platform, tmp_path, monkeypatch)
    assert "published" in meta, "the platform contract names `published` (B-04)"


def test_the_sweep_covers_every_native_platform():
    """A seventh native adapter must not slip in uncovered -- that is exactly
    how YouTube and Bluesky ended up with tests agreeing with the violation."""
    assert set(_NATIVE_ADAPTERS) == {"youtube", "bluesky"}
```

with two small local helpers (`_raiser`, and `_capture_one` driving each adapter's
`download_item` with its own stubbed transport and returning the parsed frontmatter).

- [ ] **Run** → the `published`-key case fails for Bluesky/YouTube until T12 lands; run this task
      **after** T12.
- [ ] **Implement** — no production change; if a sweep case fails, the bug is in the adapter and
      belongs to whichever earlier task owns it.
- [ ] **Commit** `test(discovery): parametrized contract sweep over the native adapters (F-20)`.

---

### T20 · Bound the channel walk (B-17)

877 items per channel enumerated daily, every id then batched through the Data API, purely to date
material already on disk.

- [ ] **Write the failing tests:**

```python
def test_enumeration_is_bounded_by_playlist_end(monkeypatch):
    seen = {}
    monkeypatch.setattr(yt, "_run_ytdlp",
                        lambda args, **k: seen.update(args=args) or _proc(0, json.dumps({"entries": []}), ""))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {})
    yt.enumerate_newest_first("@c", None)
    assert "--playlist-end" in seen["args"]
    assert seen["args"][seen["args"].index("--playlist-end") + 1] == str(yt.ENUMERATE_MAX_ITEMS)


def test_a_full_walk_can_still_be_requested(monkeypatch):
    seen = {}
    monkeypatch.setattr(yt, "_run_ytdlp",
                        lambda args, **k: seen.update(args=args) or _proc(0, json.dumps({"entries": []}), ""))
    monkeypatch.setattr(yt.youtube_api, "fetch_upload_dates", lambda ids, **k: {})
    yt.enumerate_newest_first("@c", None, max_items=None)
    assert "--playlist-end" not in seen["args"]
```

- [ ] **Run** → `--playlist-end` is absent.
- [ ] **Implement:**

```python
# --flat-playlist with no bound lists a channel's entire lifetime catalogue
# (measured: 877 items for one channel), and every id is then batched through
# the Data API -- daily, mostly to re-date material already on disk. 200 is a
# generous multiple of any plausible per-run item count and still covers a new
# handle's 90-day lookback for any real channel. Pass max_items=None for a
# deliberate full backfill (B-17).
ENUMERATE_MAX_ITEMS = 200


def _enumerate_tab(handle: str, tab: str, content_type: str,
                   max_items: int | None = ENUMERATE_MAX_ITEMS) -> list[dict]:
    bound = ["--playlist-end", str(max_items)] if max_items else []
    proc = _run_ytdlp(
        ["-J", "--flat-playlist", "--ignore-errors", *bound, *_cookie_args(), url],
        label=f"enumerate {handle}/{tab}",
    )
```

and thread `max_items` through `enumerate_newest_first(handle, keyword_filter, *, max_items=ENUMERATE_MAX_ITEMS)`
— keyword-only with a default, so `discovery_engine`'s two-positional-argument call site is
untouched.

- [ ] **Run** → green. **Commit** `perf(youtube): bound the channel enumeration to the newest N items (B-17)`.

---

## 4. Finding → test map

`F` = fault, `D` = distinguishability, `S` = surfacing (Three-Test Rule; required for the nine
`silent` findings, marked ●).

| Finding | Named test(s) | Role |
|---|---|---|
| **B-10** ● | `test_run_ytdlp_round_trips_a_non_cp1252_title_byte_identically` | F |
| | `test_run_ytdlp_never_returns_none_stdout`, `test_run_ytdlp_passes_utf8_encoding_not_bare_text_mode` | F |
| | `test_enumerate_preserves_an_emoji_title_byte_identically` | D (correct vs mojibake) |
| | `test_download_item_filename_and_h1_carry_the_original_characters` | D + S (durable filename/body) |
| | `test_empty_stdout_with_a_zero_exit_raises_rather_than_reporting_a_quiet_day` | S (typed raise) |
| **B-16** | `test_peek_upload_date_reports_a_failed_ytdlp_instead_of_returning_none` | F + S |
| | `test_peek_upload_date_survives_a_truncated_info_json` | F |
| | `test_download_item_logs_a_nonzero_ytdlp_exit` | S |
| **B-11** ● | `test_enumerate_raises_when_the_videos_tab_fetch_fails`, `test_unparseable_listing_json_raises_the_typed_error` | F |
| | `test_a_failed_fetch_is_distinguishable_from_a_channel_with_no_uploads` | **D** |
| | `test_enumerate_failure_is_surfaced_as_a_structured_error_event` | **S** |
| | `test_absent_shorts_tab_is_still_a_legitimate_empty`, `test_a_failing_shorts_tab_is_not_treated_as_an_absent_one` | D |
| **B-14** ● | `test_shorts_are_not_dropped_when_no_api_dates_are_available` | F |
| | `test_undated_enumeration_marks_its_order_approximate` vs `test_dated_enumeration_marks_its_order_exact` | **D** |
| | `test_fetch_upload_dates_reports_a_missing_key_instead_of_returning_silently` | **S** |
| | `test_undated_enumeration_interleaves_rather_than_concatenating` | F |
| **F-24** | `test_fetch_upload_dates_maps_ids_to_dates`, `_batches_at_50`, `_omits_ids_with_a_malformed_publishedAt`, `_survives_a_failed_batch`, `_reports_a_missing_key_instead_of_returning_silently` | coverage + S |
| **B-15** | `test_no_key_warning_is_printed_once_per_process` | F |
| **D-52** | `test_api_key_never_appears_in_the_request_url` | F |
| | `test_http_get_json_sends_the_key_as_a_header` | F |
| | `test_an_unexpected_exception_cannot_leak_the_key_in_its_traceback` | F |
| **B-13** ● | `test_a_blocked_transcript_fetch_raises` (×4 params) | **F** |
| | `test_blocked_is_distinguishable_from_captionless` | **D** |
| | `test_an_unrecognised_transcript_exception_is_treated_as_blocked` | **S** (log record) |
| | `test_a_genuinely_captionless_video_returns_none` | D |
| **B-12** ● | `test_bot_blocked_download_with_api_metadata_is_marked_retryable` | **F** |
| | `test_a_captionless_video_is_terminal_not_retryable` | **D** |
| | `test_on_disk_ids_re_offers_a_pending_retry_capture` | **S** (durable frontmatter + re-offer) |
| | `test_a_blocked_transcript_api_also_marks_pending_retry`, `test_attempts_accumulate_and_the_status_becomes_terminal_at_the_cap`, `test_a_recovered_transcript_clears_the_pending_state`, `test_on_disk_ids_keeps_a_terminal_capture`, `test_on_disk_ids_treats_an_unreadable_file_as_captured` | F/D |
| **B-04** | `test_frontmatter_carries_both_published_and_upload_date`, `test_both_date_keys_are_none_together_when_no_date_is_known` | F |
| **B-05** ● | `test_enumerate_newest_first_raises_on_fetch_failure`, `test_malformed_json_raises_rather_than_reporting_an_empty_feed` | **F** |
| | `test_a_fetch_failure_is_distinguishable_from_an_empty_feed` | **D** |
| | `test_a_fetch_failure_is_surfaced_as_a_structured_error_event` | **S** |
| | `test_a_failure_mid_pagination_raises_rather_than_truncating_the_walk` vs `test_a_complete_short_walk_is_not_a_failure` | F + D |
| **F-12** ● | replaces the deleted test; same three as B-05 above | F/D/S |
| **B-06** ● | `test_validate_shaped_call_raises_on_a_transient_failure` | **F** |
| | `test_a_genuinely_nonexistent_actor_still_returns_empty`, `test_the_two_validate_outcomes_have_different_types` | **D** |
| | `test_a_fetch_failure_is_surfaced_as_a_structured_error_event` (shared) | **S** |
| **B-08** ● | `test_keyword_filter_matches_beyond_the_first_sixty_characters` | **F** |
| | `test_keyword_filter_still_excludes_a_genuine_non_match` | **D** |
| | (surfacing: n/a — a fixed filter has no failure state to report) | — |
| **B-09** | `test_a_row_with_no_usable_created_at_is_dropped` | F + S (log record) |
| | `test_indexed_at_is_accepted_when_created_at_is_absent` | D |
| **B-07** ● | `test_download_item_reuses_the_enumerate_walk` | **F** |
| | `test_download_item_propagates_a_transport_failure_rather_than_reporting_not_found` | **D** |
| | `test_download_item_reports_a_reason_when_the_item_is_not_found` | **S** |
| | `test_the_cache_holds_unfiltered_rows` | F |
| **F-20** | `test_every_native_adapter_raises_on_a_transport_failure`, `test_every_native_adapter_returns_empty_for_a_genuinely_empty_source`, `test_every_native_adapter_writes_an_aware_utc_fetched_at`, `test_every_native_adapter_writes_a_url`, `test_every_native_adapter_writes_the_contract_published_key`, `test_the_sweep_covers_every_native_platform` | coverage |
| **B-17** | `test_enumeration_is_bounded_by_playlist_end`, `test_a_full_walk_can_still_be_requested` | F |

**All 18 findings mapped to at least one named test. Every `silent` finding has all three roles.**

### On the surfacing role in an adapter

An adapter has no DB connection, so `obs.record_event(conn, ...)` is not callable here — the
`events` row is written by whichever caller catches the typed exception (P8's `discovery_engine`).
This package's surfacing signals are therefore, in order of preference:

1. a **durable artifact on disk** — `transcript_status: pending_retry` in the written frontmatter,
   the byte-identical filename;
2. a **typed exception** whose message names the handle, the tab/page and the cause, which the
   engine persists as a per-handle `error`;
3. an **`obs.log()` record**, asserted as data (event kind, level, fields) via the `logged`
   fixture — this writes to `pipeline-app/logs/app-YYYY-MM-DD.log`, which is durable, unlike the
   `print()` to a console Task Scheduler destroys (D-02).

`print(..., file=sys.stderr)` is kept everywhere it exists — it is useful interactively — but is
never the thing a test asserts on for a surfacing role.

---

## 5. Tests deleted or inverted

| # | File:line | Test | Action |
|---|---|---|---|
| 1 | `pipeline-app/tests/test_discovery_bluesky.py:56-60` | `test_enumerate_newest_first_returns_empty_on_fetch_failure` | **Inverted** (T13) |
| 2 | `pipeline-app/tests/test_discovery_youtube.py:67-74` | `test_enumerate_newest_first_returns_empty_on_failure` | **Inverted** (T4) |
| 3 | `pipeline-app/tests/test_discovery_youtube.py:460-467` | `test_without_api_dates_falls_back_to_videos_only_and_warns` | **Deleted and replaced** (T5) |
| 4 | `pipeline-app/tests/test_discovery_youtube.py:258-264` | `test_transcript_status_missing_when_no_transcript` | **Split** (T10) |

**1 — F-12, the named case.** `test_discovery_bluesky.py:56-60`:

```python
def test_enumerate_newest_first_returns_empty_on_fetch_failure(monkeypatch):
    def raise_error(url):
        raise OSError("network down")
    monkeypatch.setattr(bsky, "_http_get", raise_error)
    assert bsky.enumerate_newest_first("dead.bsky.social", keyword_filter=None) == []
```

The test's **name states the bug as the requirement**. `brightdata_job.py:6-10` names that exact
behavior as "the exact bug that shipped in the first Instagram adapter", and
`test_brightdata_job.py:97,127` assert the opposite — the suite holds one invariant in two
directions, and the direction it pins covers the corpus's two largest cohorts. Replaced by
`test_enumerate_newest_first_raises_on_fetch_failure` +
`test_a_fetch_failure_is_distinguishable_from_an_empty_feed` +
`test_a_fetch_failure_is_surfaced_as_a_structured_error_event` (T13), plus the parametrized
`test_every_native_adapter_raises_on_a_transport_failure` (T19).

**2 — the same defect, in YouTube's suite, unnamed by any finding.**
`test_discovery_youtube.py:67-74` asserts that a yt-dlp exit of 1 on `/videos` yields `[]`. It is
F-12's twin and blocks B-11 identically. Replaced by
`test_enumerate_raises_when_the_videos_tab_fetch_fails` and
`test_a_failed_fetch_is_distinguishable_from_a_channel_with_no_uploads` (T4). Note that
`test_missing_shorts_tab_is_not_an_error` (`:470-482`) is **kept** and strengthened — it pins the
one legitimate empty case, and losing it would let T4's fix turn every Shorts-less channel into a
permanent error.

**3 — the enshrined Shorts drop.** `test_discovery_youtube.py:460-467` asserts
`[i["id"] for i in items] == ["v1"]` when no Data API dates are available — i.e. it asserts that
the Short *is* dropped, which is SEED-8/B-14. Replaced by
`test_shorts_are_not_dropped_when_no_api_dates_are_available`,
`test_undated_enumeration_interleaves_rather_than_concatenating` and
`test_undated_enumeration_marks_its_order_approximate` (T5). The retained half of its intent — the
condition must be loud — moves into the `adapter.ordering_degraded` assertion.

**4 — an over-broad assertion, not a defect-affirming test.**
`test_transcript_status_missing_when_no_transcript` asserts `missing` for a case that after T10 is
`missing` only when yt-dlp ran clean. It is kept, with its fake corrected to `_ytdlp_ok(...)` and
an explicit `transcript_attempts == 0`, and the blocked case becomes the separate
`test_bot_blocked_download_with_api_metadata_is_marked_retryable`.

The programme-level check
`grep -rn "returns_empty_on_fetch_failure" pipeline-app/tests/` must return nothing after T13.

### Existing tests requiring mechanical updates (not inversions)

- `test_discovery_youtube.py` — every `def fake_run(cmd, capture_output, text)` and every
  `monkeypatch.setattr(yt.subprocess, "run", ...)` moves to `yt._run_ytdlp` with the
  `(args, *, label, binary=None)` signature (T2). Affects `_fake_tabs`, `_ytdlp_ok`,
  `_ytdlp_blocked` and four inline fakes.
- `test_discovery_youtube_api.py` — every `lambda url: ...` stub for `_http_get_json` becomes
  `lambda url, key=None: ...`, and `raise_403(url, timeout)` becomes `raise_403(request, timeout)`
  (T8). `test_fetch_metadata_returns_empty_without_key` also resets `_NO_KEY_WARNED` (T6).
- `test_discovery_bluesky.py:85-108` — `test_download_item_returns_ok_false_when_refetch_finds_no_match`
  gains the `reason` assertion (T18). Its existing `out_dir` path uses the un-slugified handle and
  so asserts nothing; correct it to `handle_dir(tmp_path, "bluesky", ...)` while there.

---

## 6. Contract for P9 — `published` vs `upload_date`

**The question P9 must answer, not this package.** T12 makes `discovery_youtube.download_item`
write **both** keys with the same value:

```python
"published":   upload_date or None,   # the platform contract's field name
"upload_date": upload_date or None,   # what every already-captured file uses
```

Why both, and not a rename: files already on disk carry only `upload_date`, and re-writing the
corpus to rename a key is exactly the kind of migration that has no upside here. Emitting both
makes YouTube conform to the contract **going forward** without invalidating anything captured to
date.

**What P9 owns.** `discovery_digest.py:191` carries

```python
meta.get("published") or meta.get("upload_date")
```

— a YouTube-shaped fallback in a module the platform contract says needs **no adapter-specific
code**. B-04 filed this as docs-drift precisely because the reference adapter contradicts the
contract it is supposed to demonstrate. After T12:

1. **The fallback must stay** for at least one full re-capture cycle — every YouTube `.md` already
   on disk still has `upload_date` and no `published`. Removing it as apparent dead code now would
   blank the publish date for the whole historical YouTube corpus in the daily email. P9 should
   add a comment saying so at the fallback, and a test that a `published`-less,
   `upload_date`-bearing file still renders its date.
2. **P9 decides which key is canonical in the render**, and must not read `upload_date` for any
   non-YouTube platform — no other adapter emits it, and a generic `or meta.get("upload_date")`
   invites a seventh adapter to invent a third spelling (B-98's failure mode).
3. **P14 (doc truth) should amend CLAUDE.md's contract text** to say `published` is the field name
   and that YouTube additionally emits a legacy `upload_date` alias, so a future adapter author is
   not looking at two contradictory examples. That amendment is P14's, not this package's and not
   P9's — flagged here so it is not lost.

This package makes no change to `discovery_digest.py` or any other P9 file.

---

## 7. Cross-package notes (no action by this package)

- **P0** must register the `allow_subprocess` marker and let it through the network/subprocess
  guard: T1/T2's byte-identity proof spawns `sys.executable -c` (a subprocess, no network). Without
  the marker the two B-10 round-trip tests cannot run, and B-10 is the S1 that motivates this
  package.
- **P1**'s `obs.log` is imported by all three adapter modules. `obs.record_event` is **not** called
  here — adapters have no connection.
- **P8** (`discovery_engine.py`) now receives three new exception types from its adapters:
  `YouTubeEnumerationError`, `YtDlpUnavailable`, `BlueskyFetchError`. Its existing per-handle
  `except` records `error`, which is the intended outcome. The one branch it must **change** is the
  validate path: `discovery_engine.py:255` must not convert a `BlueskyFetchError` into
  `status='invalid'` + `included=False` (B-06); the error branch at `:272` is the correct
  destination. It also gains an optional `max_items=None` opt-in for a deliberate full backfill
  (B-17) and may pass `order_confidence` through to its run record (B-14).
- **P7** should hoist `_NATIVE_ADAPTERS` from T19 into a shared table covering all six platforms;
  `test_the_sweep_covers_every_native_platform` fails loudly if a native platform is added without
  an entry, which is the guard F-20 asks for.
