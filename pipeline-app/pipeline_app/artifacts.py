import hashlib
import os
import re
import tempfile
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

from pipeline_app import obs

_DELIM = "---"
# Injective by construction: exactly one filename maps to any given version, so
# a zero-padded duplicate cannot produce an arbitrary tie-break (A-67).
_VERSION_RE = re.compile(r"^artifact\.v(0|[1-9]\d*)\.md$")
_RESERVED_RE = re.compile(r"^\.artifact\.v(0|[1-9]\d*)\.reserved$")


class MalformedArtifactError(Exception):
    """An artifact file exists but cannot be read as an artifact.

    One typed error for every way an artifact can be unreadable, always naming
    the offending path. Before this, three distinct conditions -- no
    frontmatter, an unterminated block, and a non-mapping YAML value --
    collapsed into the same indistinguishable ({}, text) return (A-68), and
    yaml.YAMLError propagated uncaught into route, approval and staleness
    paths (A-69).
    """

    def __init__(self, reason: str, path: Path | None = None):
        self.reason = reason
        self.path = path
        super().__init__(f"{path if path is not None else '<text>'}: {reason}")


class ArtifactExistsError(Exception):
    """Refused to overwrite an artifact file that already exists."""


def _atomic_write_text(path: Path, text: str) -> None:
    """Write `text` to `path` such that a crash leaves either the old bytes or
    the new bytes -- never a truncation.

    Path.write_text opens in "w" mode: the existing file is truncated to zero
    before a byte of new content is written, and nothing is fsynced. For
    stamp_final and record_gate_override that target is the ONLY copy of an
    already-approved artifact and runs/ is git-ignored, so a crash mid-write
    destroyed the approved output with nothing to recover from (A-63). Worse,
    a partial write typically loses the closing `---`, and parse_frontmatter
    used to report that wreckage as a legitimate no-frontmatter artifact
    rather than as damage.

    The temp file is named with a leading dot and a .tmp suffix so it can never
    match the `artifact.v*.md` glob, and is unlinked on any failure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _load_frontmatter_yaml(yaml_text: str) -> dict:
    """One predictable failure mode for a frontmatter block that is not a
    mapping. Two uncontained failures shared one root (A-69): safe_load's
    return was used unvalidated, and YAMLError escaped the parse boundary."""
    try:
        meta = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise MalformedArtifactError(f"frontmatter is not valid YAML: {exc}") from exc
    if meta is None:
        return {}
    if not isinstance(meta, dict):
        raise MalformedArtifactError(
            f"frontmatter parsed to {type(meta).__name__}, not a mapping"
        )
    return meta


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """The frontmatter mapping and the body.

    Returns ({}, text) for EXACTLY one condition: the text does not open with a
    `---` delimiter -- i.e. a legitimately plain markdown artifact. Every other
    departure raises MalformedArtifactError.

    Three distinct conditions used to collapse into that same ({}, text)
    return: no frontmatter at all, an opening `---` with no closing delimiter,
    and an empty YAML block (A-68). The middle one is precisely the shape a
    crash-truncated artifact takes (A-63), so returning it as "an artifact with
    no provenance" is how truncation became invisible -- downstream,
    depends_on yielded [], gates yielded [], and status yielded None so an
    already-final artifact was re-stamped.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != _DELIM:
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() != _DELIM:
            continue
        yaml_text = "\n".join(lines[1:i])
        body = "\n".join(lines[i + 1:])
        meta = _load_frontmatter_yaml(yaml_text)
        return meta, body.lstrip("\n")
    raise MalformedArtifactError(
        "frontmatter block opened with '---' and was never closed -- the file is "
        "truncated, not unversioned"
    )


def render_frontmatter(meta: dict, body: str) -> str:
    yaml_text = yaml.safe_dump(meta, sort_keys=False, default_flow_style=False).strip()
    return f"{_DELIM}\n{yaml_text}\n{_DELIM}\n\n{body.strip()}\n"


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relpath_in_run(path: Path, run_dir: Path) -> str:
    """A run-relative, forward-slashed artifact path -- the exact key shape
    state_machine.is_stale compares against."""
    return str(path.relative_to(run_dir)).replace("\\", "/")


def compute_depends_on(run_dir: Path, upstream_paths: Iterable[Path]) -> list[dict]:
    """The `depends_on` list for a new artifact version, computed from the
    upstream artifacts that exist RIGHT NOW.

    The canonical implementation. Copying a prior artifact's depends_on forward
    is what made staleness sticky (A-61): once a node records [], every later
    version inherits it and the entire downstream cascade terminates there.
    """
    return [
        {"path": relpath_in_run(p, run_dir), "sha256": compute_sha256(p)}
        for p in upstream_paths
    ]


def _versions_in(stage_dir: Path) -> list[tuple[int, Path]]:
    versions: list[tuple[int, Path]] = []
    for p in sorted(stage_dir.glob("artifact.v*.md")):
        m = _VERSION_RE.match(p.name)
        if not m:
            obs.log(
                "artifacts.unversioned_sibling",
                level="warning",
                path=str(p),
                detail="matches artifact.v*.md but not artifact.v<N>.md; invisible to "
                       "version allocation and to latest-artifact resolution",
            )
            continue
        versions.append((int(m.group(1)), p))
    return sorted(versions)


def list_unversioned_siblings(stage_dir: Path) -> list[Path]:
    """Files that look like artifacts but that the version regex rejects.

    Exposed so /doctor (P1) can show an operator the rescued or hand-annotated
    file the app is ignoring, instead of it vanishing silently (A-67).
    """
    if not stage_dir.exists():
        return []
    return sorted(
        p for p in stage_dir.glob("artifact.v*.md") if not _VERSION_RE.match(p.name)
    )


def latest_artifact_path(stage_dir: Path) -> Path | None:
    versions = _versions_in(stage_dir)
    if not versions:
        return None
    return max(versions, key=lambda t: t[0])[1]


def resolve_latest_artifact(repo_root: Path, stage_id: str, stage_dir: Path) -> Path | None:
    """A stage's current artifact, accounting for grounding's pointer-based
    storage. Every stage except grounding writes artifact.v{N}.md into its
    own stage_dir, resolved via latest_artifact_path. Grounding's real
    output lands in rgs-briefs/ at the repo root instead, referenced by a
    pointer.yaml file the turn route writes into stage_dir -- so this is
    the one place that split has to be reconciled back into a single Path."""
    if stage_id == "grounding":
        # Deferred: grounding_service imports this module for _atomic_write_text,
        # and this is the only place artifacts needs grounding_service back.
        from pipeline_app import grounding_service
        pointer = grounding_service.read_pointer(stage_dir)
        if not pointer:
            return None
        path = repo_root / pointer
        return path if path.exists() else None
    return latest_artifact_path(stage_dir)


def write_artifact(stage_dir: Path, version: int, meta: dict, body: str) -> Path:
    """Mint artifact.v{version}.md. Refuses to overwrite: an existing file at
    that path means the caller's version allocation raced or was hardcoded
    (A-65, A-73), and overwriting silently discarded an artifact version and
    its recorded gate results. Callers that are about to write should allocate
    with reserve_version() rather than next_version_number()."""
    stage_dir.mkdir(parents=True, exist_ok=True)
    path = stage_dir / f"artifact.v{version}.md"
    if path.exists():
        raise ArtifactExistsError(
            f"{path} already exists; refusing to overwrite an artifact. "
            "Allocate a version with reserve_version() instead of reusing one."
        )
    _atomic_write_text(path, render_frontmatter(meta, body))
    _record_high_water_mark(stage_dir, version)
    return path


_HWM_NAME = ".artifact-version-hwm"

# Guards _record_high_water_mark's read-decide-write span (A-66 follow-up). The
# read (_high_water_mark) and the write (_atomic_write_text) are two separate
# operations; without a lock, a low-version thread's read can observe an empty
# sidecar, get descheduled, and then land its stale "write N" *after* a
# higher-version thread has already written a bigger number, regressing the
# sidecar downward. The lock only serializes callers within this process --
# it does not close a cross-process race (two OS processes writing the same
# stage_dir). A real cross-process guarantee needs a database row, and
# schema.sql/db.py belong to P1, out of this package's file ownership; the
# sidecar has always been a best-effort, lock-free-across-processes design.
_HWM_LOCK = threading.Lock()


def _high_water_mark(stage_dir: Path) -> int:
    """The highest version number ever ALLOCATED in this stage dir, not the
    highest currently on disk.

    A-66: with no table recording versions, the sequence was whatever the
    directory happened to contain, and runs/ is git-ignored and hand-managed --
    an ordinary operator deletion silently reissued a live version number. A
    sidecar high-water mark keeps allocation monotonic without a schema change
    (schema.sql and db.py belong to P1).
    """
    seen = [v for v, _ in _versions_in(stage_dir)]
    seen += _reserved_versions_in(stage_dir)
    hwm_path = stage_dir / _HWM_NAME
    if hwm_path.exists():
        # Windows: _atomic_write_text's os.replace briefly makes the destination
        # unreadable mid-rename (ERROR_SHARING_VIOLATION -> PermissionError) to a
        # concurrent reader here -- reserve_version calls this under many
        # simultaneous threads, all racing writes to the same sidecar file. The
        # window is exactly one rename syscall, so a few immediate retries clear
        # it without needing a lock.
        raw = None
        for attempt in range(50):
            try:
                raw = hwm_path.read_text(encoding="utf-8").strip()
                break
            except (PermissionError, FileNotFoundError):
                if attempt == 49:
                    raise
                time.sleep(0.001)
        if raw.isdigit():
            seen.append(int(raw))
        else:
            obs.log(
                "artifacts.hwm_unreadable",
                level="warning",
                stage_dir=str(stage_dir),
                raw=raw[:80],
                detail="version high-water mark is not an integer; falling back to the "
                       "filesystem, which can reissue a deleted version number",
            )
    return max(seen) if seen else 0


def _record_high_water_mark(stage_dir: Path, version: int) -> None:
    """Read-decide-write span guarded by _HWM_LOCK (see comment there): closes
    the in-process TOCTOU race where a low-version caller's read predates a
    higher-version caller's write, but the low-version caller's own write
    lands after it and regresses the sidecar back down. Does NOT close a
    cross-process race -- see _HWM_LOCK's comment."""
    with _HWM_LOCK:
        # >=, not >: both call sites (write_artifact, reserve_version) invoke this
        # AFTER the artifact file or reservation marker for `version` already
        # exists on disk, so _high_water_mark's own scan already counts `version`
        # among `seen` -- `version > _high_water_mark(...)` can never be true at
        # either call site and the sidecar would never actually get written.
        if version >= _high_water_mark(stage_dir):
            # Windows: reserve_version's concurrency test drives many threads to
            # replace this exact sidecar file at once. os.replace needs the
            # destination free of any handle lacking delete-sharing, and a sibling
            # thread's read of the same path (in _high_water_mark, above) can hold
            # one for a moment -- os.replace then raises PermissionError
            # (WinError 5) rather than blocking. The write itself is idempotent
            # (same or higher version), so retrying is safe.
            for attempt in range(50):
                try:
                    _atomic_write_text(stage_dir / _HWM_NAME, f"{version}\n")
                    break
                except PermissionError:
                    if attempt == 49:
                        raise
                    time.sleep(0.001)


def next_version_number(stage_dir: Path) -> int:
    """Advisory: the version reserve_version() will TRY first.

    This is no longer an allocator -- it is an unlocked read and always was
    (A-65). Kept for read-only introspection and for callers not yet migrated;
    anything about to WRITE must call reserve_version().
    """
    return _high_water_mark(stage_dir) + 1


def read_artifact(path: Path) -> tuple[dict, str]:
    """parse_frontmatter over a file, naming the path in every failure and
    cross-checking the frontmatter `version` against the filename (A-66)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise MalformedArtifactError(f"unreadable: {type(exc).__name__}: {exc}", path=path) from exc
    try:
        meta, body = parse_frontmatter(text)
    except MalformedArtifactError as exc:
        # Chain to the original root cause (e.g. the yaml.YAMLError from
        # _load_frontmatter_yaml) rather than to this intermediate wrapper,
        # so callers can still isinstance-check __cause__ for the real fault.
        raise MalformedArtifactError(exc.reason, path=path) from (exc.__cause__ or exc)
    m = _VERSION_RE.match(path.name)
    if m is not None and isinstance(meta.get("version"), int) and meta["version"] != int(m.group(1)):
        raise MalformedArtifactError(
            f"frontmatter version {meta['version']} does not match filename version "
            f"{int(m.group(1))} -- the file was renamed or hand-copied",
            path=path,
        )
    return meta, body


@dataclass(frozen=True)
class VersionReservation:
    version: int
    stage_dir: Path
    reservation_path: Path

    @property
    def artifact_path(self) -> Path:
        return self.stage_dir / f"artifact.v{self.version}.md"


def reserve_version(stage_dir: Path, *, max_attempts: int = 256) -> VersionReservation:
    """Exclusively allocate the next artifact version.

    next_version_number is an unlocked read-then-write, and on the edit path
    the read and the write are separated by the whole gate run -- a window wide
    enough to load and execute a linter (A-65). Reservation closes it by making
    the ALLOCATION the exclusive operation: O_CREAT|O_EXCL either creates the
    marker or fails, atomically, at the filesystem. There is no lock to
    acquire, nothing to release on a hard kill, and the worst outcome of a
    crash is a burnt version number -- never a lost artifact.

    The marker is dot-prefixed so it cannot match the artifact.v*.md glob and
    can never be selected as a stage's output.
    """
    stage_dir.mkdir(parents=True, exist_ok=True)
    # §0 amendment: seed from next_version_number(), NOT _high_water_mark() directly --
    # _high_water_mark is defined in T6, which has not run yet at T5. next_version_number
    # is the pre-existing equivalent (max version on disk, default 0, + 1); T6 later
    # redefines next_version_number to route through _high_water_mark, which upgrades
    # this call's behaviour automatically with no further edit here.
    candidate = next_version_number(stage_dir)
    for _ in range(max_attempts):
        marker = stage_dir / f".artifact.v{candidate}.reserved"
        try:
            fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            candidate += 1
            continue
        os.close(fd)
        _record_high_water_mark(stage_dir, candidate)
        return VersionReservation(candidate, stage_dir, marker)
    raise RuntimeError(
        f"could not reserve an artifact version in {stage_dir} after {max_attempts} attempts"
    )


def write_reserved_artifact(reservation: VersionReservation, meta: dict, body: str) -> Path:
    """Write the artifact a reservation holds, then drop the marker."""
    path = reservation.artifact_path
    if path.exists():
        raise ArtifactExistsError(f"{path} already exists; the reservation was not honoured.")
    _atomic_write_text(path, render_frontmatter(meta, body))
    reservation.reservation_path.unlink(missing_ok=True)
    return path


def release_version(reservation: VersionReservation) -> None:
    """Drop a reservation whose write never happened.

    Deliberately does NOT lower the high-water mark. A released number is
    burnt: reissuing it would let two different bodies occupy the same version
    over the life of a stage, which is exactly the history-lying failure A-66
    describes.
    """
    reservation.reservation_path.unlink(missing_ok=True)


def _reserved_versions_in(stage_dir: Path) -> list[int]:
    out = []
    for p in stage_dir.glob(".artifact.v*.reserved"):
        m = _RESERVED_RE.match(p.name)
        if m:
            out.append(int(m.group(1)))
    return out


_DEFAULT_ACTOR = "operator"


def _append_override(meta: dict, reason: str, at: str | None, actor: str | None) -> None:
    """Append an override rather than assign one.

    A-38: this was `meta["gate_override_reason"] = reason` -- last-write-wins,
    with no actor anywhere and, on the record_gate_override path, no timestamp
    at all. A migrated legacy scalar is carried into the list rather than
    dropped, because it is the only record of an override applied before this
    change.
    """
    history = meta.get("gate_overrides")
    if not isinstance(history, list):
        history = []
    legacy = meta.pop("gate_override_reason", None)
    if isinstance(legacy, str) and legacy.strip():
        history.append({"reason": legacy, "at": None, "actor": None})
    history.append({"reason": reason, "at": at, "actor": actor or _DEFAULT_ACTOR})
    meta["gate_overrides"] = history


def stamp_final(path: Path, finalized_at: str, gate_override_reason: str | None = None,
                *, actor: str | None = None) -> None:
    meta, body = read_artifact(path)
    meta["status"] = "final"
    meta["finalized_at"] = finalized_at
    if gate_override_reason:
        # Recorded alongside the failing gate result, which is deliberately left
        # untouched -- an override says a human accepted the finding, not that
        # the finding was wrong.
        _append_override(meta, gate_override_reason, finalized_at, actor)
    _atomic_write_text(path, render_frontmatter(meta, body))


def record_gate_override(path: Path, gate_override_reason: str, *,
                         at: str, actor: str | None = None) -> None:
    """Record an override on an artifact that is ALREADY stamped final.

    `at` is required and keyword-only: the old signature had no timestamp
    parameter and deliberately did not touch finalized_at, so an override on an
    already-final artifact carried no time anywhere in the file (A-38).
    Writes only the override history: status, finalized_at and the `gates`
    entry itself are left untouched.
    """
    meta, body = read_artifact(path)
    _append_override(meta, gate_override_reason, at, actor)
    _atomic_write_text(path, render_frontmatter(meta, body))


def read_gate_overrides(path: Path) -> list[dict]:
    """Every override recorded on an artifact, oldest first.

    A-37: gate_override_reason was write-only -- stage_page read only
    output_meta.get("gates") and stage.html never referenced the override, so
    an operator saw a red failing gate with no indication that anyone
    consciously accepted it or why. This is the accessor the gates panel
    renders (see the P3/P15 contract in the plan).
    """
    meta, _ = read_artifact(path)
    history = meta.get("gate_overrides")
    if isinstance(history, list):
        return [h for h in history if isinstance(h, dict)]
    legacy = meta.get("gate_override_reason")
    if isinstance(legacy, str) and legacy.strip():
        return [{"reason": legacy, "at": None, "actor": None}]
    return []
