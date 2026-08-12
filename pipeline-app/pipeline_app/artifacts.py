import hashlib
import os
import re
import tempfile
from pathlib import Path

import yaml

from pipeline_app import grounding_service

_DELIM = "---"
_VERSION_RE = re.compile(r"artifact\.v(\d+)\.md$")


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


def parse_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.split("\n")
    if not lines or lines[0].strip() != _DELIM:
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == _DELIM:
            yaml_text = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1:])
            meta = yaml.safe_load(yaml_text) or {}
            return meta, body.lstrip("\n")
    return {}, text


def render_frontmatter(meta: dict, body: str) -> str:
    yaml_text = yaml.safe_dump(meta, sort_keys=False, default_flow_style=False).strip()
    return f"{_DELIM}\n{yaml_text}\n{_DELIM}\n\n{body.strip()}\n"


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _versions_in(stage_dir: Path) -> list[tuple[int, Path]]:
    versions = []
    for p in stage_dir.glob("artifact.v*.md"):
        m = _VERSION_RE.match(p.name)
        if m:
            versions.append((int(m.group(1)), p))
    return versions


def next_version_number(stage_dir: Path) -> int:
    versions = _versions_in(stage_dir)
    return (max(v for v, _ in versions) if versions else 0) + 1


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


def _record_high_water_mark(stage_dir: Path, version: int) -> None:
    pass  # T6 replaces this body with the real sidecar-file writer.


def stamp_final(path: Path, finalized_at: str, gate_override_reason: str | None = None) -> None:
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    meta["status"] = "final"
    meta["finalized_at"] = finalized_at
    if gate_override_reason:
        # Recorded alongside the failing gate result, which is deliberately left
        # untouched -- an override says a human accepted the finding, not that
        # the finding was wrong.
        meta["gate_override_reason"] = gate_override_reason
    path.write_text(render_frontmatter(meta, body), encoding="utf-8")


def record_gate_override(path: Path, gate_override_reason: str) -> None:
    """Record an override reason on an artifact that is ALREADY stamped final.

    Re-approving an already-final artifact deliberately skips stamp_final
    (see approval_service.approve_stage) so that finalized_at -- and therefore
    the file's sha256 -- does not churn on a no-op re-approval. But an
    override reason supplied on that path is a real decision, not a no-op,
    and dropping it silently would be exactly the "unknown gate result
    quietly passes" failure mode this whole mechanism exists to close. This
    writes only gate_override_reason: status, finalized_at, and the `gates`
    entry itself are left untouched -- an override says a human accepted the
    finding, not that the finding was wrong."""
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    meta["gate_override_reason"] = gate_override_reason
    path.write_text(render_frontmatter(meta, body), encoding="utf-8")
