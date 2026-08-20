from native_pipeline.flagging import flag_outliers


def test_flag_outliers_skips_windows_under_min_duck_window(monkeypatch, tmp_path):
    calls = []

    def fake_measure_window(path, start, duration, log_path):
        calls.append((start, duration))
        return -20.0

    monkeypatch.setattr("native_pipeline.flagging.measure_window", fake_measure_window)

    spans = [("beat1", 0.0, 0.2), ("beat2", 1.0, 5.0)]  # beat1 is 0.2s, under the 0.4s floor
    flag_outliers(tmp_path / "take.wav", spans, tmp_path / "log.txt")

    assert calls == [(1.0, 5.0)]


def test_flag_outliers_flags_the_beat_deviating_from_median(monkeypatch, tmp_path):
    lufs_by_start = {0.0: -14.0, 5.0: -14.5, 10.0: -25.0}

    def fake_measure_window(path, start, duration, log_path):
        return lufs_by_start[start]

    monkeypatch.setattr("native_pipeline.flagging.measure_window", fake_measure_window)

    spans = [("beat1", 0.0, 5.0), ("beat2", 5.0, 5.0), ("beat3", 10.0, 5.0)]
    flags = flag_outliers(tmp_path / "take.wav", spans, tmp_path / "log.txt")

    assert [f["label"] for f in flags] == ["beat3"]
    assert flags[0]["lufs"] == -25.0


def test_flag_outliers_returns_empty_list_when_all_beats_are_close(monkeypatch, tmp_path):
    monkeypatch.setattr("native_pipeline.flagging.measure_window", lambda path, start, duration, log_path: -14.0)
    spans = [("beat1", 0.0, 5.0), ("beat2", 5.0, 5.0)]
    assert flag_outliers(tmp_path / "take.wav", spans, tmp_path / "log.txt") == []


def test_flag_outliers_returns_empty_list_with_fewer_than_two_measurable_spans(monkeypatch, tmp_path):
    monkeypatch.setattr("native_pipeline.flagging.measure_window", lambda path, start, duration, log_path: -14.0)
    spans = [("beat1", 0.0, 5.0)]
    assert flag_outliers(tmp_path / "take.wav", spans, tmp_path / "log.txt") == []
