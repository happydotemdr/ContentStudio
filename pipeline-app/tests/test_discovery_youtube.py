import json
from pathlib import Path

from pipeline_app import discovery_youtube as yt


def test_on_disk_ids_matches_id_prefix_before_double_underscore(tmp_path: Path):
    handle_dir = tmp_path / "output" / "brand-intel" / "youtube" / "romayroh"
    handle_dir.mkdir(parents=True)
    (handle_dir / "abc123__original-title.md").write_text("x", encoding="utf-8")
    (handle_dir / "def456__retitled-now.md").write_text("x", encoding="utf-8")
    assert yt.on_disk_ids(tmp_path, "@Romayroh") == {"abc123", "def456"}


def test_on_disk_ids_empty_for_new_handle(tmp_path: Path):
    assert yt.on_disk_ids(tmp_path, "@BrandNew") == set()


def test_enumerate_newest_first_applies_keyword_filter(monkeypatch):
    fake_output = json.dumps({"entries": [
        {"id": "v1", "title": "Adam Grant on focus"},
        {"id": "v2", "title": "Unrelated video"},
        {"id": "v3", "title": "adam grant interview"},
    ]})

    class FakeProc:
        returncode = 0
        stdout = fake_output
        stderr = ""

    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: FakeProc())
    items = yt.enumerate_newest_first("@bigthink", keyword_filter="Adam Grant")
    assert [i["id"] for i in items] == ["v1", "v3"]
    assert all(i["published"] is None for i in items)


def test_enumerate_newest_first_no_filter_returns_all(monkeypatch):
    fake_output = json.dumps({"entries": [{"id": "v1", "title": "A"}, {"id": "v2", "title": "B"}]})

    class FakeProc:
        returncode = 0
        stdout = fake_output
        stderr = ""

    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: FakeProc())
    items = yt.enumerate_newest_first("@a", keyword_filter=None)
    assert [i["id"] for i in items] == ["v1", "v2"]


def test_enumerate_newest_first_returns_empty_on_failure(monkeypatch):
    class FakeProc:
        returncode = 1
        stdout = ""
        stderr = "channel not found"

    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: FakeProc())
    assert yt.enumerate_newest_first("@dead-handle", keyword_filter=None) == []


def test_peek_upload_date_reads_info_json(monkeypatch, tmp_path):
    def fake_run(cmd, capture_output, text):
        # simulate yt-dlp writing the info.json next to -o's stem
        out_flag_index = cmd.index("-o")
        stem = Path(cmd[out_flag_index + 1].replace(".%(ext)s", ""))
        stem.with_suffix(".info.json").write_text(
            json.dumps({"upload_date": "20260415"}), encoding="utf-8"
        )
        class FakeProc:
            returncode = 0
            stdout = ""
            stderr = ""
        return FakeProc()

    monkeypatch.setattr(yt.subprocess, "run", fake_run)
    monkeypatch.chdir(tmp_path)
    assert yt.peek_upload_date("v1") == "2026-04-15"


def test_peek_upload_date_returns_none_when_no_info_json(monkeypatch, tmp_path):
    class FakeProc:
        returncode = 1
        stdout = ""
        stderr = "error"
    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: FakeProc())
    monkeypatch.chdir(tmp_path)
    assert yt.peek_upload_date("v1") is None
