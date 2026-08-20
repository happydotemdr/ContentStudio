from pathlib import Path

from stitcher import vo_split as vs
from stitcher.vo_alignment import Segment


def test_split_segments_writes_one_file_per_segment_with_correct_trim_args(tmp_path, monkeypatch):
    calls = []

    def fake_run(args, log_path):
        calls.append(args)
        Path(args[-1]).write_bytes(b"wav")
        return ""

    monkeypatch.setattr(vs.ffmpeg, "run", fake_run)

    source = tmp_path / "single_take.mp3"
    source.write_bytes(b"src")
    out_dir = tmp_path / "segments"
    log_path = tmp_path / "log.txt"
    segments = [
        Segment(name="beat1", at=0.0, duration=5.538),
        Segment(name="beat2", at=6.142, duration=5.99),
    ]

    outputs = vs.split_segments(source, segments, out_dir, log_path)

    assert outputs == [out_dir / "beat1.wav", out_dir / "beat2.wav"]
    assert len(calls) == 2
    assert calls[0][calls[0].index("-ss") + 1] == "0.000000"
    assert calls[0][calls[0].index("-t") + 1] == "5.538000"
    assert calls[1][calls[1].index("-ss") + 1] == "6.142000"
    assert calls[1][calls[1].index("-t") + 1] == "5.990000"
    assert calls[0][calls[0].index("-ac") + 1] == "2"
    assert "pcm_s16le" in calls[0]
    for out_path in outputs:
        assert out_path.is_file()


def test_split_segments_creates_out_dir_if_missing(tmp_path, monkeypatch):
    def fake_run(args, log_path):
        Path(args[-1]).write_bytes(b"wav")
        return ""

    monkeypatch.setattr(vs.ffmpeg, "run", fake_run)

    source = tmp_path / "src.mp3"
    source.write_bytes(b"src")
    out_dir = tmp_path / "does" / "not" / "exist" / "yet"
    segments = [Segment(name="only", at=0.0, duration=1.0)]

    vs.split_segments(source, segments, out_dir, tmp_path / "log.txt")

    assert out_dir.is_dir()


def test_split_segments_empty_list_writes_nothing(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(vs.ffmpeg, "run", lambda args, log_path: calls.append(args))

    outputs = vs.split_segments(tmp_path / "src.mp3", [], tmp_path / "out", tmp_path / "log.txt")

    assert outputs == []
    assert calls == []
