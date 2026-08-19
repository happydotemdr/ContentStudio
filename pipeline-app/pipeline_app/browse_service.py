# pipeline_app/browse_service.py
"""Read-only folder/file access scoped under repo_root/output, for the
Browse page. Pure logic only -- no FastAPI or Jinja imports here."""

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape as _html_escape
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath, PureWindowsPath

import markdown

from pipeline_app import artifacts, grounding_service
from pipeline_app import db as db_mod

MAX_FILE_BYTES = 5 * 1024 * 1024

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
# All HTML5 void elements -- these never emit a matching end tag, whether or
# not this sanitizer allows them. Used only to decide whether a *disallowed*
# start tag should push _skip_depth: doing that for a void-like tag (e.g. a
# disallowed <meta>) would wait forever for a </meta> that will never arrive,
# leaving _skip_depth stuck above zero and silently dropping every character
# of the document after that point.
_HTML_VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


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
        # Depth of nested disallowed elements we're currently inside (e.g.
        # <script>...</script>). A dropped tag's own inner text must not
        # leak through handle_data -- the tag ban is pointless if the payload
        # still shows up as plain text right below it.
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag not in _ALLOWED_TAGS:
            if tag not in _HTML_VOID_ELEMENTS:
                self._skip_depth += 1
            return
        if self._skip_depth:
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
        if tag not in _ALLOWED_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag not in _VOID_TAGS:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if self._skip_depth:
            return
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


class PathSafetyError(Exception):
    """Raised when a requested path would resolve outside output/."""


class FolderReadError(Exception):
    """Raised when a folder cannot be scanned (permission error, folder
    removed between the route's existence check and the scan, etc.)."""


def output_root(repo_root: Path) -> Path:
    return (repo_root / "output").resolve()


def runs_root(repo_root: Path) -> Path:
    return (repo_root / "runs").resolve()


def root_path(repo_root: Path, root: str) -> Path:
    if root == "output":
        return output_root(repo_root)
    if root == "pipeline":
        return runs_root(repo_root)
    raise ValueError(f"unknown browse root: {root!r}")


_RUN_ID_TIMESTAMP_RE = re.compile(r"-(\d{8}-\d{6})$")


def _parse_created_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_run_id_timestamp(name: str) -> datetime | None:
    m = _RUN_ID_TIMESTAMP_RE.search(name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        # Shape-valid (8 digits, 6 digits) but calendar-invalid (e.g. Feb
        # 31st, hour 25) -- treat the same as "no parseable timestamp"
        # rather than letting this crash the whole /browse page.
        return None


def list_pipeline_projects(conn, repo_root: Path) -> list["Entry"]:
    runs_dir = runs_root(repo_root)
    if not runs_dir.is_dir():
        return []

    brand_and_created: dict[str, tuple[str, str]] = {
        row["run_id"]: (row["brand"], row["created_at"]) for row in db_mod.list_projects(conn)
    }

    candidates: list[tuple[str, str | None, str | None]] = []
    try:
        with os.scandir(runs_dir) as it:
            for entry in it:
                if entry.is_symlink() or not entry.is_dir():
                    continue
                brand, created_at = brand_and_created.get(entry.name, (None, None))
                candidates.append((entry.name, brand, created_at))
    except OSError as exc:
        raise FolderReadError(str(exc)) from exc

    _EPOCH = datetime.min.replace(tzinfo=timezone.utc)

    def sort_tuple(item: tuple[str, str | None, str | None]):
        # DB created_at is ISO 8601 ("2026-07-28T12:00:00+00:00"); an
        # orphan folder's fallback key is parsed from its run_id suffix
        # ("20260728-120000"). These two string formats do NOT compare
        # correctly against each other lexically (e.g. "2026-...": the
        # "-" at index 4 sorts below the "0" a compact-format string has
        # at the same index) -- both are parsed to real datetimes here so
        # comparison is always by actual chronological value, never by
        # incidental string shape.
        name, _brand, created_at = item
        when = _parse_created_at(created_at) if created_at else _parse_run_id_timestamp(name)
        return (when is not None, when or _EPOCH, name.lower())

    candidates.sort(key=sort_tuple, reverse=True)
    return [
        Entry(
            name=f"{name} ({brand})" if brand else name,
            rel_path=name,
            is_dir=True,
        )
        for name, brand, _created_at in candidates
    ]


def resolve_grounding_pointer_state(
    pointer_dir: Path, repo_root: Path
) -> tuple[Path | None, str | None]:
    """Return (target, error). Exactly one is non-None, or both are None when
    there is simply no pointer here.

    The old single-return-value form collapsed "no pointer" and "the pointer
    is broken" into the same bare None, so a hand-edited or truncated
    pointer.yaml was invisible: list_children skipped the entry and its
    folder could vanish with it (E-14b). pointer.yaml's content comes off
    disk rather than from the request, so its target is still a trust
    boundary and keeps its explicit containment check against the real
    rgs-briefs/ folder."""
    if not (pointer_dir / "pointer.yaml").is_file():
        return None, None
    try:
        target_rel = grounding_service.read_pointer(pointer_dir)
    except grounding_service.InvalidPointerError as exc:
        return None, f"pointer.yaml could not be parsed: {exc}"
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
    """Back-compat wrapper: target or None. Callers that need to tell a
    broken pointer from an absent one must use resolve_grounding_pointer_state."""
    return resolve_grounding_pointer_state(pointer_dir, repo_root)[0]


def resolve_under_output(root: Path, rel_path: str) -> Path:
    rel_path = (rel_path or "").strip()
    if rel_path in ("", ".", "/"):
        return root

    normalized = rel_path.replace("\\", "/")

    # A colon anywhere (not just a leading drive letter) also catches
    # Windows drive-relative forms like "C:foo", which pathlib's
    # is_absolute() does NOT flag as absolute.
    if ":" in normalized:
        raise PathSafetyError("':' is not allowed in path")
    if PureWindowsPath(normalized).is_absolute() or PurePosixPath(normalized).is_absolute():
        raise PathSafetyError("absolute paths are not allowed")

    segments = [seg for seg in normalized.split("/") if seg]
    if any(seg == ".." for seg in segments):
        raise PathSafetyError("'..' is not allowed in path")

    candidate = (root / "/".join(segments)).resolve()
    if not candidate.is_relative_to(root):
        raise PathSafetyError("path escapes output/")
    return candidate


@dataclass(frozen=True)
class Entry:
    name: str
    rel_path: str
    is_dir: bool
    unreadable: bool = False
    broken_reason: str | None = None


def _is_md_name(name: str) -> bool:
    return name.lower().endswith(".md")


def _md_below_state(folder: Path, repo_root: Path) -> str:
    """One of "content", "empty", "unreadable".

    The tri-state is the whole point. The old boolean (_has_md_below)
    returned False for both "nothing to show here" and "I could not look",
    and list_children used it as the include test -- so a permission-denied
    folder was not rendered as unreadable, it vanished from its parent's
    listing and the operator saw a shorter tree with no error anywhere
    (E-14a)."""
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
                    target, error = resolve_grounding_pointer_state(Path(entry.path).parent, repo_root)
                    if target is not None or error is not None:
                        # A pointer.yaml that exists -- whether it resolves
                        # cleanly, points at a missing/out-of-bounds target,
                        # or fails to parse at all -- is content: the
                        # operator must be able to click through and read
                        # why (E-14b). It must not be silently treated as
                        # empty, which would make the malformed-pointer
                        # folder itself vanish from its parent's listing.
                        return "content"
                if entry.is_dir():
                    below = _md_below_state(Path(entry.path), repo_root)
                    if below in ("content", "unreadable"):
                        return below
    except OSError:
        return "unreadable"
    return "empty"


_ARTIFACT_VERSION_RE = re.compile(r"artifact\.v(\d+)\.md$", re.IGNORECASE)


def _file_sort_key(entry: "Entry") -> tuple:
    m = _ARTIFACT_VERSION_RE.match(entry.name)
    if m:
        return (0, int(m.group(1)), entry.name.lower())
    return (1, 0, entry.name.lower())


def list_children(folder: Path, root: Path, repo_root: Path) -> list["Entry"]:
    dirs: list[Entry] = []
    files: list[Entry] = []
    try:
        with os.scandir(folder) as it:
            for entry in it:
                if entry.is_symlink():
                    continue
                path = Path(entry.path)
                rel_path = path.relative_to(root).as_posix()
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
                elif entry.is_file():
                    if entry.name == "raw_output.md":
                        # Pre-versioning scratch state, already captured in
                        # the corresponding artifact.vN.md body -- showing
                        # both is redundant clutter, not useful history.
                        continue
                    if _is_md_name(entry.name):
                        files.append(Entry(name=entry.name, rel_path=rel_path, is_dir=False))
                    elif entry.name == "pointer.yaml":
                        target, error = resolve_grounding_pointer_state(folder, repo_root)
                        if target is not None:
                            files.append(Entry(
                                name=f"current-brief.md ({target.name})",
                                rel_path=rel_path,
                                is_dir=False,
                            ))
                        elif error is not None:
                            files.append(Entry(
                                name="pointer.yaml (unresolvable)",
                                rel_path=rel_path,
                                is_dir=False,
                                broken_reason=error,
                            ))
    except OSError as exc:
        # Unlike an empty folder, this must surface as an error rather than
        # silently returning [] -- to the caller those would look identical.
        raise FolderReadError(str(exc)) from exc
    dirs.sort(key=lambda e: e.name.lower())
    files.sort(key=_file_sort_key)
    return dirs + files


def render_md_file(path: Path) -> dict:
    try:
        size = path.stat().st_size
    except OSError as exc:
        # e.g. the file was deleted on disk between the route's existence
        # check and this call -- a real (if narrow) TOCTOU window given
        # this is a live filesystem browser, not a security boundary
        # concern here (single-user, read-only local app).
        return {"error": f"Could not read file: {exc}"}
    if size > MAX_FILE_BYTES:
        return {
            "oversize": True,
            "size_mb": size / (1024 * 1024),
            "cap_mb": MAX_FILE_BYTES / (1024 * 1024),
            "abs_path": str(path),
        }

    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return {"error": f"Could not read file: {exc}"}

    try:
        meta, body = artifacts.parse_frontmatter(text)
    except artifacts.MalformedArtifactError as exc:
        if "not valid YAML" in exc.reason:
            return {"error": "Frontmatter is not valid YAML."}
        return {"error": "Frontmatter is not a key/value mapping."}

    return {
        "frontmatter": meta,
        "body_html": sanitize_html(markdown.markdown(body, extensions=["tables"])),
    }
