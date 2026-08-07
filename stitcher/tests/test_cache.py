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


def test_payload_digest_rejects_sets():
    """Sets are non-deterministic and must be rejected."""
    try:
        payload_digest({"a", "b", "c"})
        assert False, "Should have raised TypeError"
    except TypeError as e:
        assert "set" in str(e).lower()


def test_payload_digest_rejects_frozensets():
    """Frozensets are also non-deterministic and must be rejected."""
    try:
        payload_digest(frozenset([1, 2, 3]))
        assert False, "Should have raised TypeError"
    except TypeError as e:
        assert "frozenset" in str(e).lower()


def test_payload_digest_parts_are_separated():
    """Different logical inputs must produce different digests."""
    # Concatenation without separation could collide:
    # ("ab", "c") and ("a", "bc") should differ
    digest1 = payload_digest("ab", "c")
    digest2 = payload_digest("a", "bc")
    assert digest1 != digest2, "Parts must be properly separated in digest"


def test_loading_a_corrupt_manifest_yields_an_empty_one(tmp_path: Path):
    """A manifest with invalid JSON should degrade to empty, not raise."""
    path = tmp_path / "corrupt.json"
    path.write_text("{not valid json")
    manifest = Manifest.load(path)
    assert manifest.get("anything") is None


def test_loading_a_non_dict_json_manifest_yields_an_empty_one(tmp_path: Path):
    """A manifest that is valid JSON but not a dict should degrade to empty."""
    path = tmp_path / "non_dict.json"
    path.write_text("[1, 2, 3]")
    manifest = Manifest.load(path)
    assert manifest.get("anything") is None


def test_payload_digest_rejects_sets_nested_in_lists():
    """Nested sets in lists are also non-deterministic and must be rejected."""
    try:
        payload_digest([1, {2, 3}])
        assert False, "Should have raised TypeError for nested set in list"
    except TypeError as e:
        assert "set" in str(e).lower()


def test_payload_digest_rejects_sets_nested_in_dicts():
    """Nested sets in dicts are also non-deterministic and must be rejected."""
    try:
        payload_digest({"key": {1, 2, 3}})
        assert False, "Should have raised TypeError for nested set in dict"
    except TypeError as e:
        assert "set" in str(e).lower()


def test_payload_digest_rejects_arbitrary_objects():
    """Arbitrary objects with no custom __repr__ are non-deterministic and must be rejected."""
    class UnknownObject:
        pass

    try:
        payload_digest(UnknownObject())
        assert False, "Should have raised TypeError for arbitrary object"
    except TypeError as e:
        assert "unknownobject" in str(e).lower()


def test_payload_digest_accepts_path_objects():
    """Path objects should be serializable and deterministic."""
    p1 = Path("/tmp/test.txt")
    p2 = Path("/tmp/test.txt")
    digest1 = payload_digest(p1)
    digest2 = payload_digest(p2)
    assert digest1 == digest2, "Same Path should produce same digest"

    # Different paths should produce different digests
    p3 = Path("/tmp/other.txt")
    digest3 = payload_digest(p3)
    assert digest1 != digest3, "Different Paths should produce different digests"


def test_payload_digest_accepts_paths_in_nested_structures():
    """Path objects nested in lists and dicts should be serializable."""
    p = Path("/tmp/test.txt")
    digest1 = payload_digest([p, "data"])
    digest2 = payload_digest([p, "data"])
    assert digest1 == digest2, "Paths in lists should be deterministic"

    digest3 = payload_digest({"path": p, "name": "test"})
    digest4 = payload_digest({"path": p, "name": "test"})
    assert digest3 == digest4, "Paths in dicts should be deterministic"
