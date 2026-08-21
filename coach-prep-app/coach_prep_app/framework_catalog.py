# coach-prep-app/coach_prep_app/framework_catalog.py
"""The framework activity catalog: one compact entry per usable ACTIVITY
across the Frameworks-to-consider corpus.

Why a catalog and not a search index. The corpus is 90 files and ~712KB of
body text -- far too much for one prompt, but small enough that a distilled
index of the whole thing fits in about 12K tokens. Selection therefore sees
EVERY option at once, rather than whatever a similarity search happened to
surface. It also keeps the tool-denied generation subprocess intact: nothing
has to fetch anything at draft time, because the chosen activities are already
embedded in the prompt by then.

framework_catalog.yaml in the repo is the source of truth and the file a human
edits. The SQLite table is a query cache, rebuilt from the YAML. Data never
flows the other way."""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
from pathlib import Path

import yaml

from coach_prep_app import db

KINDS = ("concept", "activity", "assessment", "reading", "meditation")

# Kinds Ryan can actually run inside a session, as opposed to assign. Part 4
# of the prep doc needs one of these -- a `reading` cannot be done live.
LIVE_KINDS = ("activity", "meditation", "assessment")

_REQUIRED = ("id", "title", "framework", "kind", "rel_path", "source_label", "one_line")


@dataclasses.dataclass(frozen=True)
class CatalogEntry:
    id: str
    title: str
    framework: str
    kind: str
    rel_path: str
    source_label: str
    one_line: str
    use_when: tuple[str, ...] = ()
    anchor: str | None = None
    source_version: int | None = None
    live_ready: bool = False
    duration_min: int | None = None
    curated: bool = False

    def to_yaml_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "framework": self.framework,
            "kind": self.kind, "rel_path": self.rel_path, "anchor": self.anchor,
            "source_version": self.source_version, "source_label": self.source_label,
            "one_line": self.one_line, "use_when": list(self.use_when),
            "live_ready": self.live_ready, "duration_min": self.duration_min,
            "curated": self.curated,
        }

    def index_line(self) -> str:
        """One entry as it appears in the selection prompt. Deliberately terse
        -- the whole corpus has to fit alongside the client material, and a
        verbose entry format is what would push it out of budget."""
        bits = [f"{self.id} | {self.title} | {self.kind}"]
        if self.duration_min:
            bits.append(f"{self.duration_min}min")
        if self.live_ready:
            bits.append("live-ready")
        if self.use_when:
            bits.append("when: " + ",".join(self.use_when))
        return " | ".join(bits) + f"\n    {self.one_line}"


class CatalogError(ValueError):
    """A malformed catalog. Raised rather than skipped: a silently dropped
    entry is an activity Ryan never gets offered, with nothing to notice."""


def _entry_from_dict(raw: dict, index: int) -> CatalogEntry:
    if not isinstance(raw, dict):
        raise CatalogError(f"entry {index}: expected a mapping, got {type(raw).__name__}")
    missing = [field for field in _REQUIRED if not raw.get(field)]
    if missing:
        raise CatalogError(f"entry {index} ({raw.get('id', '?')}): missing {', '.join(missing)}")
    if raw["kind"] not in KINDS:
        raise CatalogError(
            f"entry {raw['id']}: kind {raw['kind']!r} is not one of {', '.join(KINDS)}"
        )
    use_when = raw.get("use_when") or []
    if not isinstance(use_when, list):
        raise CatalogError(f"entry {raw['id']}: use_when must be a list")
    return CatalogEntry(
        id=raw["id"], title=raw["title"], framework=raw["framework"], kind=raw["kind"],
        rel_path=raw["rel_path"], source_label=raw["source_label"], one_line=raw["one_line"],
        use_when=tuple(str(tag) for tag in use_when),
        anchor=raw.get("anchor"), source_version=raw.get("source_version"),
        live_ready=bool(raw.get("live_ready", False)),
        duration_min=raw.get("duration_min"), curated=bool(raw.get("curated", False)),
    )


def load_catalog(path: Path) -> list[CatalogEntry]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        raise CatalogError(f"{path}: expected a list of entries, got {type(raw).__name__}")
    entries = [_entry_from_dict(item, index) for index, item in enumerate(raw)]
    seen: dict[str, int] = {}
    for index, entry in enumerate(entries):
        if entry.id in seen:
            raise CatalogError(
                f"duplicate id {entry.id!r} at entries {seen[entry.id]} and {index} -- "
                f"selection validates picks by id, so a duplicate makes one entry unreachable"
            )
        seen[entry.id] = index
    return entries


def write_catalog(path: Path, entries: list[CatalogEntry]) -> None:
    path.write_text(
        yaml.safe_dump(
            [entry.to_yaml_dict() for entry in entries],
            sort_keys=False, allow_unicode=True, width=100,
        ),
        encoding="utf-8",
    )


def merge(existing: list[CatalogEntry], rebuilt: list[CatalogEntry]) -> tuple[list[CatalogEntry], list[str]]:
    """Fold a rebuild into the current catalog, never overwriting a hand-edited
    entry. Returns the merged list and the ids kept as-is because they are
    curated, so the caller can say so out loud -- a curated entry pinned to a
    source that has since changed is a real staleness risk, and keeping it
    silently is how the catalog rots."""
    by_id = {entry.id: entry for entry in existing}
    kept_curated = []
    merged = list(existing)
    for entry in rebuilt:
        prior = by_id.get(entry.id)
        if prior is None:
            merged.append(entry)
            continue
        if prior.curated:
            kept_curated.append(entry.id)
            continue
        merged[merged.index(prior)] = entry
    merged.sort(key=lambda e: (e.framework, e.rel_path, e.id))
    return merged, sorted(kept_curated)


def needs_rebuild(entries: list[CatalogEntry], rel_path: str, source_version: int | None) -> bool:
    """True when a corpus file has no entries yet, or any of its entries was
    built from a different version of it."""
    for_path = [entry for entry in entries if entry.rel_path == rel_path]
    if not for_path:
        return True
    return any(entry.source_version != source_version for entry in for_path)


def sync_to_db(conn, entries: list[CatalogEntry], now_iso: str | None = None) -> int:
    """Replace the cache table wholesale. The YAML is truth; a partial upsert
    would leave rows behind for entries a human deleted from it."""
    now_iso = now_iso or dt.datetime.now(dt.timezone.utc).isoformat()
    with db.transaction(conn):
        conn.execute("DELETE FROM framework_catalog")
        for entry in entries:
            conn.execute(
                "INSERT INTO framework_catalog (id, title, framework, kind, rel_path, anchor, "
                "source_version, source_label, one_line, use_when_json, live_ready, "
                "duration_min, curated, loaded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (entry.id, entry.title, entry.framework, entry.kind, entry.rel_path,
                 entry.anchor, entry.source_version, entry.source_label, entry.one_line,
                 json.dumps(list(entry.use_when)), int(entry.live_ready),
                 entry.duration_min, int(entry.curated), now_iso),
            )
    return len(entries)


def render_index(entries: list[CatalogEntry]) -> str:
    """The catalog block embedded in the selection prompt, grouped by framework
    so a model scanning it sees the corpus's actual shape."""
    by_framework: dict[str, list[CatalogEntry]] = {}
    for entry in entries:
        by_framework.setdefault(entry.framework, []).append(entry)
    blocks = []
    for framework in sorted(by_framework):
        lines = "\n".join(
            entry.index_line() for entry in sorted(by_framework[framework], key=lambda e: e.id)
        )
        blocks.append(f"### {framework}\n{lines}")
    return "\n\n".join(blocks)
