from pathlib import Path

import pytest

from stitcher.naming import Workspace, slugify


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    return Workspace(root=tmp_path, slug="nobody-asked-the-kid", mode="final")


def test_slugify_lowercases_and_hyphenates():
    assert slugify("Best Part Was The MUD") == "best-part-was-the-mud"


def test_slugify_strips_punctuation_and_collapses_separators():
    assert slugify("Charlotte Mason -- 1886!") == "charlotte-mason-1886"


def test_slugify_truncates_long_text_without_trailing_hyphen():
    result = slugify("a" * 100)
    assert len(result) == 40
    assert not result.endswith("-")


def test_work_dir_is_partitioned_by_mode(tmp_path: Path):
    final = Workspace(root=tmp_path, slug="s", mode="final")
    draft = Workspace(root=tmp_path, slug="s", mode="draft")
    assert final.work_dir != draft.work_dir
    assert final.work_dir.name == "final"
    assert draft.work_dir.name == "draft"


def test_shot_clip_is_ordinal_id_label_and_sorts_in_playback_order(ws: Workspace):
    first = ws.shot_clip(1, "B-01", "hook")
    tenth = ws.shot_clip(10, "B-10", "payoff-research-2")
    assert first.name == "001_B-01_hook.mkv"
    assert tenth.name == "010_B-10_payoff-research-2.mkv"
    assert sorted([tenth.name, first.name])[0] == first.name


def test_overlay_png_and_bbox_share_a_stem(ws: Workspace):
    png = ws.overlay_png(1, "hook-1", "best-part-was-the-mud")
    bbox = ws.overlay_bbox(1, "hook-1", "best-part-was-the-mud")
    assert png.suffix == ".png"
    assert bbox.suffix == ".json"
    assert png.stem == bbox.stem


def test_audio_step_uses_chain_order_ordinals(ws: Workspace):
    assert ws.audio_step("04a", "bed_conformed").name == "04a_bed_conformed.wav"


def test_next_version_is_one_on_an_empty_workspace(ws: Workspace):
    ws.ensure_dirs()
    assert ws.next_version() == 1


def test_next_version_increments_past_the_highest_existing(ws: Workspace):
    ws.ensure_dirs()
    ws.out_master(1).write_bytes(b"")
    ws.out_master(7).write_bytes(b"")
    assert ws.next_version() == 8


def test_next_version_ignores_draft_outputs(ws: Workspace):
    ws.ensure_dirs()
    ws.draft_master().write_bytes(b"")
    assert ws.next_version() == 1


def test_out_master_is_version_stamped(ws: Workspace):
    assert ws.out_master(3).name == "nobody-asked-the-kid_v03_1080x1920.mp4"


def test_draft_master_is_not_versioned(ws: Workspace):
    assert ws.draft_master().name == "nobody-asked-the-kid_draft_1080x1920.mp4"


def test_master_path_lives_in_work_not_out(ws: Workspace):
    assert ws.master_path.parent == ws.work_dir
    assert ws.master_path.name == "master.mp4"
