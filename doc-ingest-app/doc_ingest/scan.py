"""Read-only tree walk + magic-byte content sniffing. Never opens a file for
writing; never moves or deletes anything under the input root (spec §4 step
2). Sniffing exists not just to keep video out but to correctly *include* the
6 real PDFs and 1 PNG hiding among this corpus's 19 extensionless files
(spec §2) -- extension-based classification alone silently drops them."""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
from pathlib import Path
from typing import Iterator

_CONVERTIBLE_EXTENSIONS = {"pdf", "docx", "xlsx", "txt", "md", "ppt"}
_GDOC_EXTENSIONS = {"gdoc", "gsheet"}
_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
_VIDEO_EXTENSIONS = {"mov", "mp4"}

_SNIFF_SIZE = 32


def sniff_signature(path: Path) -> str | None:
    with open(path, "rb") as fh:
        head = fh.read(_SNIFF_SIZE)
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12]
        # 'qt  ' is QuickTime/.mov's own brand; everything else with an
        # ftyp box at this offset is an ISO-base-media (mp4-family) file.
        return "mov" if brand == b"qt  " else "mp4"
    return None


def classify(extension: str, sniffed: str | None) -> str:
    ext = extension.lower()
    if ext == "":
        if sniffed == "pdf":
            return "convertible"
        if sniffed in ("png", "jpg"):
            return "catalog_only"
        if sniffed in ("mov", "mp4"):
            return "excluded_media"
        return "blocked_unknown"
    if ext in _CONVERTIBLE_EXTENSIONS:
        return "convertible"
    if ext in _GDOC_EXTENSIONS:
        return "gdoc_pointer"
    if ext in _IMAGE_EXTENSIONS:
        return "catalog_only"
    if ext in _VIDEO_EXTENSIONS:
        return "excluded_media"
    return "blocked_unknown"


@dataclasses.dataclass(frozen=True)
class ScannedEntry:
    rel_path: str
    extension: str
    sniffed_signature: str | None
    size_bytes: int
    mtime_iso: str
    content_hash: str | None  # None for catalog_only/excluded_media/blocked_unknown -- see walk_source_tree


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def walk_source_tree(root: Path) -> Iterator[ScannedEntry]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(root).as_posix()
        extension = path.suffix[1:].lower() if path.suffix else ""
        sniffed = sniff_signature(path) if extension == "" else None
        stat = path.stat()
        mtime_iso = dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc).isoformat()
        # Only hash what change-detection actually needs: 'convertible'
        # local files (content_hash drives their enqueue comparison) and
        # 'gdoc_pointer' stubs (always 176 bytes regardless, so hashing them
        # is free even though drive_modified_time, not this hash, drives
        # their change detection). Hashing everything unconditionally would
        # mean sha256'ing all 60 video files in the real corpus -- up to
        # 1.1GB each -- on every 30-minute wake, for a value nothing
        # downstream ever reads (excluded_media is never enqueued, spec §2).
        classification = classify(extension, sniffed)
        content_hash = _sha256_file(path) if classification in ("convertible", "gdoc_pointer") else None
        yield ScannedEntry(
            rel_path=rel_path,
            extension=extension,
            sniffed_signature=sniffed,
            size_bytes=stat.st_size,
            mtime_iso=mtime_iso,
            content_hash=content_hash,
        )
