"""Single source of truth for every path and filename in a render workspace.

Filename conventions are behaviour, not formatting: they are asserted in
tests/test_naming.py. Nothing outside this module builds a workspace path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Supersample factor for Ken Burns moves. Position quantization at the working
# resolution is 1/SUPERSAMPLE output pixels; 4 gives 0.25px, invisible under
# lanczos. Draft skips supersampling entirely for speed.
SUPERSAMPLE_FINAL = 4
SUPERSAMPLE_DRAFT = 1

# Windows MAX_PATH. Long-path support is not assumed.
MAX_PATH_LEN = 255

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_SLUG_MAX = 40


def slugify(text: str) -> str:
    """Lowercase, hyphenate, and truncate text for use inside a filename."""
    lowered = _SLUG_STRIP.sub("-", text.lower()).strip("-")
    return lowered[:_SLUG_MAX].rstrip("-")


@dataclass(frozen=True)
class Workspace:
    """Every path for one Short, in one run mode."""

    root: Path
    slug: str
    mode: str  # "final" | "draft"

    # --- directories -----------------------------------------------------

    @property
    def base(self) -> Path:
        return self.root / self.slug

    @property
    def assets_dir(self) -> Path:
        return self.base / "assets"

    @property
    def work_dir(self) -> Path:
        return self.base / "work" / self.mode

    @property
    def shots_dir(self) -> Path:
        return self.work_dir / "shots"

    @property
    def overlays_dir(self) -> Path:
        return self.work_dir / "overlays"

    @property
    def audio_dir(self) -> Path:
        return self.work_dir / "audio"

    @property
    def out_dir(self) -> Path:
        return self.base / "out"

    @property
    def logs_dir(self) -> Path:
        return self.base / "logs"

    def ensure_dirs(self) -> None:
        for directory in (
            self.assets_dir,
            self.shots_dir,
            self.overlays_dir,
            self.audio_dir,
            self.out_dir,
            self.logs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    # --- work artifacts --------------------------------------------------

    @property
    def spec_path(self) -> Path:
        return self.base / "render-spec.json"

    @property
    def manifest_path(self) -> Path:
        return self.work_dir / "manifest.json"

    @property
    def concat_path(self) -> Path:
        return self.work_dir / "concat.txt"

    @property
    def graph_path(self) -> Path:
        return self.work_dir / "graph_assemble.txt"

    @property
    def master_path(self) -> Path:
        """Stage D output. Promoted to out/ only on a QA pass (spec §2 rule 5)."""
        return self.work_dir / "master.mp4"

    def asset(self, filename: str) -> Path:
        return self.assets_dir / filename

    def shot_clip(self, ordinal: int, shot_id: str, label: str) -> Path:
        return self.shots_dir / f"{ordinal:03d}_{shot_id}_{slugify(label)}.mkv"

    def overlay_png(self, ordinal: int, overlay_id: str, label: str) -> Path:
        return self.overlays_dir / f"{ordinal:03d}_{overlay_id}_{slugify(label)}.png"

    def overlay_bbox(self, ordinal: int, overlay_id: str, label: str) -> Path:
        return self.overlay_png(ordinal, overlay_id, label).with_suffix(".json")

    def audio_step(self, ordinal: str, label: str) -> Path:
        return self.audio_dir / f"{ordinal}_{label}.wav"

    def log_path(self, timestamp: str) -> Path:
        return self.logs_dir / f"{timestamp}_{self.mode}.log"

    # --- deliverables ----------------------------------------------------

    def out_master(self, version: int) -> Path:
        return self.out_dir / f"{self.slug}_v{version:02d}_1080x1920.mp4"

    def out_cover(self, version: int) -> Path:
        return self.out_dir / f"{self.slug}_v{version:02d}_cover_1080x1920.png"

    def out_srt(self, version: int) -> Path:
        return self.out_dir / f"{self.slug}_v{version:02d}.srt"

    def out_ass(self, version: int) -> Path:
        return self.out_dir / f"{self.slug}_v{version:02d}.ass"

    def out_qa_json(self, version: int) -> Path:
        return self.out_dir / f"{self.slug}_v{version:02d}_qa.json"

    def out_qa_md(self, version: int) -> Path:
        return self.out_dir / f"{self.slug}_v{version:02d}_qa.md"

    def out_contact_sheet(self, version: int) -> Path:
        return self.out_dir / f"{self.slug}_v{version:02d}_contact-sheet.png"

    def draft_master(self) -> Path:
        """Drafts are disposable and never consume a version number."""
        return self.out_dir / f"{self.slug}_draft_1080x1920.mp4"

    def next_version(self) -> int:
        """One above the highest version already promoted into out/."""
        pattern = re.compile(rf"^{re.escape(self.slug)}_v(\d+)_1080x1920\.mp4$")
        highest = 0
        if self.out_dir.exists():
            for entry in self.out_dir.iterdir():
                match = pattern.match(entry.name)
                if match:
                    highest = max(highest, int(match.group(1)))
        return highest + 1
