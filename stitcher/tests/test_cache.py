from pathlib import Path

from stitcher.cache import Manifest, file_digest, payload_digest


def test_file_digest_changes_with_content(tmp_path: Path):
    target = tmp_path / "a.bin"
    target.write_bytes(b"one")
    first = file_digest(target)
    target.write_bytes(b"two")
    assert file_digest(target) != first


def test_file_digest_of_a_missing_file_is_stable_and_distinct(tmp_path: Path):
    missing = tmp_path / "nope.bin"
    assert file_digest(missing) == file_digest(missing)
    present = tmp_path / "yes.bin"
    present.write_bytes(b"")
    assert file_digest(missing) != file_digest(present)


def test_payload_digest_is_order_sensitive():
    assert payload_digest("a", "b") != payload_digest("b", "a")


def test_payload_digest_is_stable_across_calls():
    assert payload_digest({"k": 1}, [2, 3]) == payload_digest({"k": 1}, [2, 3])


def test_is_fresh_requires_both_a_matching_digest_and_a_present_artifact(tmp_path: Path):
    manifest = Manifest(tmp_path / "manifest.json")
    artifact = tmp_path / "shot.mkv"
    manifest.set("shots/001", "abc")

    assert manifest.is_fresh("shots/001", "abc", artifact) is False  # artifact missing
    artifact.write_bytes(b"x")
    assert manifest.is_fresh("shots/001", "abc", artifact) is True
    assert manifest.is_fresh("shots/001", "different", artifact) is False
    assert manifest.is_fresh("shots/999", "abc", artifact) is False


def test_manifest_round_trips_through_disk(tmp_path: Path):
    path = tmp_path / "manifest.json"
    manifest = Manifest(path)
    manifest.set("audio/mix", "deadbeef")
    manifest.save()

    reloaded = Manifest.load(path)
    assert reloaded.get("audio/mix") == "deadbeef"


def test_loading_a_missing_manifest_yields_an_empty_one(tmp_path: Path):
    manifest = Manifest.load(tmp_path / "absent.json")
    assert manifest.get("anything") is None
