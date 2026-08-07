import json
from pathlib import Path

import pytest

from stitcher import cli
from stitcher.naming import Workspace
from stitcher.verify import Check, FAIL, PASS
from tests.test_spec import MINIMAL, write


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    ws = Workspace(root=tmp_path / "renders", slug="demo", mode="final")
    ws.ensure_dirs()
    ws.spec_path.write_text(json.dumps(MINIMAL), encoding="utf-8")
    for name in ("a.png", "b.png", "cover.png", "vo.wav", "bed.mp3"):
        ws.asset(name).write_bytes(b"x")
    return ws


def stub_pipeline(monkeypatch, checks: list[Check]):
    """Replace every stage with a fast fake, leaving orchestration real."""
    monkeypatch.setattr(cli.preflight, "run_preflight",
                        lambda spec, ws, mode: cli.preflight.PreflightReport())
    monkeypatch.setattr(cli.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 8.0.1")
    monkeypatch.setattr(cli.shots, "render_all",
                        lambda *a, **k: [a[1].shots_dir / "001_x_y.mkv"])
    monkeypatch.setattr(cli, "render_overlays", lambda spec, ws, manifest: {})

    def fake_audio(spec, ws, mode, log_path, missing, manifest=None):
        target = ws.audio_step("06", "mix_final")
        target.write_bytes(b"wav")
        return cli.audio.AudioResult(target, None, None, -18.0, {})

    monkeypatch.setattr(cli.audio, "build_audio", fake_audio)

    def fake_assemble(spec, ws, mode, clips, pngs, mix, log_path, manifest=None):
        ws.master_path.write_bytes(b"mp4")
        return ws.master_path

    monkeypatch.setattr(cli.assemble, "assemble", fake_assemble)
    monkeypatch.setattr(cli.verify, "verify", lambda *a, **k: checks)
    monkeypatch.setattr(cli.verify, "contact_sheet", lambda *a, **k: None)
    monkeypatch.setattr(cli.derive, "render_cover", lambda *a, **k: None)


def test_validate_exits_zero_on_a_good_spec(workspace):
    assert cli.cmd_validate(workspace.spec_path) == cli.EXIT_OK


def test_validate_exits_one_on_a_bad_spec(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][1]["in"] = 3.5
    assert cli.cmd_validate(write(tmp_path, payload)) == cli.EXIT_PREFLIGHT


def test_preflight_failure_aborts_before_any_render(workspace, monkeypatch):
    report = cli.preflight.PreflightReport(errors=["asset not found: a.png"])
    monkeypatch.setattr(cli.preflight, "run_preflight", lambda spec, ws, mode: report)
    called: list[str] = []
    monkeypatch.setattr(cli.shots, "render_all",
                        lambda *a, **k: called.append("rendered") or [])
    code = cli.cmd_render("demo", workspace.root, "final", force=False)
    assert code == cli.EXIT_PREFLIGHT
    assert called == []


def test_a_passing_run_promotes_the_master_into_out(workspace, monkeypatch):
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])
    code = cli.cmd_render("demo", workspace.root, "final", force=False)
    assert code == cli.EXIT_OK
    assert workspace.out_master(1).is_file()
    assert not workspace.master_path.exists()


def test_a_failing_qa_leaves_the_master_in_work_and_burns_no_version(
    workspace, monkeypatch
):
    stub_pipeline(monkeypatch, [Check("true_peak", FAIL, "-0.4 exceeds -1.5")])
    code = cli.cmd_render("demo", workspace.root, "final", force=False)
    assert code == cli.EXIT_QA
    assert workspace.master_path.is_file()
    assert not workspace.out_master(1).exists()
    assert workspace.next_version() == 1
    assert list(workspace.logs_dir.glob("*_qa.md"))


def test_a_stage_e_failure_promotes_nothing_and_burns_no_version(workspace, monkeypatch):
    """Stage E, the contact sheet and the QA report used to run AFTER
    shutil.move and outside every handler, so a failure in any of them left a
    version-stamped master in out/ with no cover, no sidecars and no QA
    report -- plus an uncaught traceback whose exit code collided with
    EXIT_PREFLIGHT. Reachable today: preflight validated cover.source with
    ffprobe while stage E opened it with Pillow."""
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])

    def explode(*args, **kwargs):
        raise OSError("cannot identify image file 'cover.png'")

    monkeypatch.setattr(cli.derive, "render_cover", explode)
    code = cli.cmd_render("demo", workspace.root, "final", force=False)

    assert code == cli.EXIT_RENDER
    assert workspace.master_path.is_file()          # still in work/
    assert not workspace.out_master(1).exists()     # nothing promoted
    assert workspace.next_version() == 1            # no version burned
    assert list(workspace.out_dir.iterdir()) == []  # no partial deliverables


def test_a_late_stage_e_failure_rolls_back_what_it_already_wrote(workspace, monkeypatch):
    """The sidecars are written before the contact sheet, so a contact-sheet
    failure has to remove them again rather than leaving a version's worth of
    orphans behind a master that never arrived."""
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])

    def explode(*args, **kwargs):
        raise cli.ffmpeg.FFmpegError("ffmpeg failed extracting a contact-sheet frame")

    monkeypatch.setattr(cli.verify, "contact_sheet", explode)
    code = cli.cmd_render("demo", workspace.root, "final", force=False)

    assert code == cli.EXIT_RENDER
    assert list(workspace.out_dir.iterdir()) == []
    assert workspace.master_path.is_file()


def test_the_contact_sheet_is_taken_before_the_master_moves(workspace, monkeypatch):
    """It reads whichever master it is handed, so it must be handed the one in
    work/ -- the promoted path does not exist yet at that point."""
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])
    seen: list[Path] = []
    monkeypatch.setattr(
        cli.verify, "contact_sheet",
        lambda spec, master, out, log: seen.append(Path(master)) or None,
    )
    cli.cmd_render("demo", workspace.root, "final", force=False)
    assert seen == [workspace.master_path]


def test_versions_increment_across_successful_runs(workspace, monkeypatch):
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])
    cli.cmd_render("demo", workspace.root, "final", force=False)
    cli.cmd_render("demo", workspace.root, "final", force=True)
    assert workspace.out_master(1).is_file()
    assert workspace.out_master(2).is_file()


def test_a_total_cache_hit_is_a_no_op_that_mints_no_version(workspace, monkeypatch):
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])
    cli.cmd_render("demo", workspace.root, "final", force=False)
    code = cli.cmd_render("demo", workspace.root, "final", force=False)
    assert code == cli.EXIT_OK
    assert not workspace.out_master(2).exists()


def test_force_mints_a_new_version_despite_a_total_cache_hit(workspace, monkeypatch):
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])
    cli.cmd_render("demo", workspace.root, "final", force=False)
    cli.cmd_render("demo", workspace.root, "final", force=True)
    assert workspace.out_master(2).is_file()


def test_draft_writes_an_unversioned_master(workspace, monkeypatch):
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])
    code = cli.cmd_render("demo", workspace.root, "draft", force=False)
    assert code == cli.EXIT_OK
    assert workspace.out_master(None).is_file()
    assert workspace.next_version() == 1


def test_run_digest_changes_with_the_ffmpeg_build(workspace):
    from stitcher.spec import load_spec
    spec, _ = load_spec(workspace.spec_path)
    a = cli.run_digest(spec, workspace, "final", "ffmpeg 8.0")
    b = cli.run_digest(spec, workspace, "final", "ffmpeg 8.1")
    assert a != b


def test_run_digest_changes_when_a_font_file_changes(workspace, tmp_path):
    from stitcher.spec import load_spec
    font = tmp_path / "f.ttf"
    font.write_bytes(b"one")
    payload = json.loads(json.dumps(MINIMAL))
    payload["styles"]["card"]["font_file"] = str(font)
    workspace.spec_path.write_text(json.dumps(payload), encoding="utf-8")
    spec, _ = load_spec(workspace.spec_path)

    before = cli.run_digest(spec, workspace, "final", "ffmpeg 8.0")
    font.write_bytes(b"two")
    assert cli.run_digest(spec, workspace, "final", "ffmpeg 8.0") != before


def test_run_digest_changes_between_modes(workspace):
    from stitcher.spec import load_spec
    spec, _ = load_spec(workspace.spec_path)
    assert (cli.run_digest(spec, workspace, "final", "ff")
            != cli.run_digest(spec, workspace, "draft", "ff"))


def test_verify_without_work_returns_the_incomplete_code(workspace, monkeypatch):
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])
    cli.cmd_render("demo", workspace.root, "final", force=False)
    monkeypatch.setattr(
        cli.verify, "verify",
        lambda *a, **k: [Check("duck_depth", cli.verify.UNAVAILABLE, "work/ cleaned")],
    )
    assert cli.cmd_verify("demo", workspace.root, 1) == cli.EXIT_INCOMPLETE


def test_clean_removes_work_but_keeps_out_and_logs(workspace, monkeypatch):
    stub_pipeline(monkeypatch, [Check("container", PASS, "ok")])
    cli.cmd_render("demo", workspace.root, "final", force=False)
    assert cli.cmd_clean("demo", workspace.root, "final") == cli.EXIT_OK
    assert not workspace.work_dir.exists()
    assert workspace.out_master(1).is_file()
    assert workspace.logs_dir.exists()


def test_main_dispatches_and_returns_the_command_code(workspace, monkeypatch):
    monkeypatch.setattr(cli, "cmd_validate", lambda path: 7)
    assert cli.main(["validate", str(workspace.spec_path)]) == 7
