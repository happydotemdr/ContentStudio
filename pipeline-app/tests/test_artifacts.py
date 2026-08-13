import os
import threading
from pathlib import Path

import pytest
import yaml

from pipeline_app import artifacts
from pipeline_app.artifacts import (
    _atomic_write_text,
    ArtifactExistsError,
    compute_sha256,
    latest_artifact_path,
    next_version_number,
    parse_frontmatter,
    release_version,
    render_frontmatter,
    reserve_version,
    resolve_latest_artifact,
    stamp_final,
    write_artifact,
    write_reserved_artifact,
)
from pipeline_app import grounding_service
from pipeline_app.grounding_service import write_pointer


def test_render_and_parse_frontmatter_roundtrip():
    meta = {"schema_version": 1, "stage": "shorts-ideation", "depends_on": []}
    text = render_frontmatter(meta, "# Concept Brief\n\nBody text here.")
    parsed_meta, body = parse_frontmatter(text)
    assert parsed_meta["schema_version"] == 1
    assert parsed_meta["stage"] == "shorts-ideation"
    assert "Concept Brief" in body


def test_parse_frontmatter_on_plain_text_returns_empty_meta():
    meta, body = parse_frontmatter("just plain text, no frontmatter")
    assert meta == {}
    assert body == "just plain text, no frontmatter"


def test_unterminated_frontmatter_raises_instead_of_masquerading_as_unversioned(tmp_path):
    """FAULT. A-68: an opening --- with no closing delimiter fell through the
    loop and returned ({}, text) -- exactly the shape a crash-truncated
    artifact takes (A-63), reported as a legitimate plain-markdown file."""
    truncated = "---\nschema_version: 1\nstatus: final\nversion: 1\n"
    with pytest.raises(artifacts.MalformedArtifactError) as exc:
        artifacts.parse_frontmatter(truncated)
    assert "never closed" in str(exc.value)


def test_truncated_artifact_is_distinguishable_from_a_genuinely_plain_one(tmp_path):
    """DISTINGUISHABILITY. Three conditions used to collapse to the same
    indistinguishable ({}, text)."""
    plain = tmp_path / "artifact.v1.md"
    plain.write_text("just a plain markdown artifact, no frontmatter", encoding="utf-8")
    truncated = tmp_path / "artifact.v2.md"
    truncated.write_text("---\nstatus: final\nversion: 2\n", encoding="utf-8")

    plain_result = artifacts.read_artifact(plain)
    assert plain_result == ({}, "just a plain markdown artifact, no frontmatter")

    with pytest.raises(artifacts.MalformedArtifactError):
        artifacts.read_artifact(truncated)


def test_a_truncated_artifact_names_its_own_path_in_the_error(tmp_path):
    """SURFACING. The human-reachable signal is a typed error naming the file;
    an operator (or an obs event recorded by the caller) can act on it. Before,
    nothing anywhere logged that a --- was opened and never closed."""
    bad = tmp_path / "artifact.v1.md"
    bad.write_text("---\nstatus: final\n", encoding="utf-8")
    with pytest.raises(artifacts.MalformedArtifactError) as exc:
        artifacts.read_artifact(bad)
    assert str(bad) in str(exc.value)
    assert exc.value.path == bad


def test_empty_frontmatter_block_is_still_an_empty_mapping(tmp_path):
    """A genuinely empty block is benign and must keep working."""
    assert artifacts.parse_frontmatter("---\n---\n\nbody") == ({}, "body")


@pytest.mark.parametrize("block,kind", [
    ("---\njust a string\n---\n\nbody", "str"),
    ("---\n- a\n- b\n---\n\nbody", "list"),
    ("---\n42\n---\n\nbody", "int"),
])
def test_non_mapping_frontmatter_raises_a_named_error_not_attributeerror(block, kind):
    """A-69(a): yaml.safe_load returned whatever the block parsed to, and every
    caller immediately called .get() on it -- AttributeError and a bare 500
    with no indication of which artifact was at fault."""
    with pytest.raises(artifacts.MalformedArtifactError) as exc:
        artifacts.parse_frontmatter(block)
    assert "not a mapping" in str(exc.value)
    assert kind in str(exc.value)


def test_malformed_yaml_is_contained_into_one_predictable_error(tmp_path):
    """A-69(b): yaml.YAMLError propagated uncaught into the route, approval and
    staleness paths. The worst site is propagate_staleness's phase-1 loop,
    where one malformed dependent aborted the cascade MID-ITERATION."""
    bad = tmp_path / "artifact.v1.md"
    bad.write_text("---\nstatus: 'unterminated\nversion: 1\n---\n\nbody", encoding="utf-8")
    with pytest.raises(artifacts.MalformedArtifactError) as exc:
        artifacts.read_artifact(bad)
    assert "not valid YAML" in str(exc.value)
    assert str(bad) in str(exc.value)
    assert isinstance(exc.value.__cause__, yaml.YAMLError)


def test_a_body_starting_with_a_horizontal_rule_is_rejected_not_misparsed():
    """The reachable-by-accident case: a body that begins with a markdown
    horizontal rule was mistaken for a frontmatter opener."""
    with pytest.raises(artifacts.MalformedArtifactError):
        artifacts.parse_frontmatter("---\n\nA heading\n\n---\n\nmore body")


def test_next_version_number_empty_dir_is_one(tmp_path: Path):
    assert next_version_number(tmp_path) == 1


def test_next_version_number_increments(tmp_path: Path):
    (tmp_path / "artifact.v1.md").write_text("x", encoding="utf-8")
    (tmp_path / "artifact.v2.md").write_text("x", encoding="utf-8")
    assert next_version_number(tmp_path) == 3


def test_latest_artifact_path_picks_highest_version(tmp_path: Path):
    (tmp_path / "artifact.v1.md").write_text("old", encoding="utf-8")
    (tmp_path / "artifact.v2.md").write_text("new", encoding="utf-8")
    assert latest_artifact_path(tmp_path).name == "artifact.v2.md"


def test_latest_artifact_path_none_when_empty(tmp_path: Path):
    assert latest_artifact_path(tmp_path) is None


def test_write_artifact_creates_versioned_file(tmp_path: Path):
    path = write_artifact(tmp_path, 1, {"stage": "shorts-ideation"}, "hello body")
    assert path.name == "artifact.v1.md"
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["stage"] == "shorts-ideation"
    assert "hello body" in body


def test_compute_sha256_is_stable(tmp_path: Path):
    f = tmp_path / "a.md"
    f.write_text("same content", encoding="utf-8")
    h1 = compute_sha256(f)
    h2 = compute_sha256(f)
    assert h1 == h2
    assert len(h1) == 64


def test_stamp_final_sets_status_and_hash_reflects_stamped_content(tmp_path: Path):
    path = write_artifact(tmp_path, 1, {"status": "draft"}, "content")
    hash_before_stamp = compute_sha256(path)
    stamp_final(path, "2026-07-25T00:00:00+00:00")
    meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["status"] == "final"
    assert meta["finalized_at"] == "2026-07-25T00:00:00+00:00"
    hash_after_stamp = compute_sha256(path)
    # The file's bytes changed because of the stamp, so the hash a downstream
    # stage would record must be taken AFTER stamping, never before.
    assert hash_before_stamp != hash_after_stamp


def test_two_overrides_on_one_artifact_both_survive(tmp_path):
    """A-38: record_gate_override assigned meta["gate_override_reason"] = ...,
    overwriting any prior value -- approving the same artifact twice with
    different reasons left only the second."""
    path = write_artifact(tmp_path, 1, {"status": "final", "version": 1}, "body")
    artifacts.record_gate_override(path, "accepted: known false positive",
                                   at="2026-08-08T10:00:00+00:00", actor="brian")
    artifacts.record_gate_override(path, "accepted again after re-review",
                                   at="2026-08-08T11:00:00+00:00", actor="brian")

    overrides = artifacts.read_gate_overrides(path)
    assert [o["reason"] for o in overrides] == [
        "accepted: known false positive",
        "accepted again after re-review",
    ]


def test_an_override_on_an_already_final_artifact_carries_a_timestamp(tmp_path):
    """A-38: the record_gate_override branch deliberately did not touch
    finalized_at, so an override applied to an already-final artifact carried
    NO timestamp at all -- only stages.approved_at moved, and nothing linked
    the two."""
    path = write_artifact(tmp_path, 1, {"status": "final", "version": 1}, "body")
    artifacts.record_gate_override(path, "accepted", at="2026-08-08T12:00:00+00:00")
    entry = artifacts.read_gate_overrides(path)[0]
    assert entry["at"] == "2026-08-08T12:00:00+00:00"
    assert entry["actor"]


def test_stamp_final_override_lands_in_the_same_append_only_list(tmp_path):
    path = write_artifact(tmp_path, 1, {"status": "draft", "version": 1}, "body")
    artifacts.stamp_final(path, "2026-08-08T09:00:00+00:00",
                          gate_override_reason="accepted at approval")
    entry = artifacts.read_gate_overrides(path)[0]
    assert entry["reason"] == "accepted at approval"
    assert entry["at"] == "2026-08-08T09:00:00+00:00"


def test_a_legacy_scalar_override_is_migrated_forward_not_dropped(tmp_path):
    """The old scalar field is the only record of an override applied before
    this change; it must survive into the list."""
    path = write_artifact(
        tmp_path, 1,
        {"status": "final", "version": 1, "gate_override_reason": "old decision"},
        "body",
    )
    artifacts.record_gate_override(path, "new decision", at="2026-08-08T12:00:00+00:00")
    reasons = [o["reason"] for o in artifacts.read_gate_overrides(path)]
    assert reasons == ["old decision", "new decision"]


def test_read_gate_overrides_is_empty_for_an_artifact_with_none(tmp_path):
    """A-37's render accessor: the gates panel iterates this. An artifact with
    no override must yield [] -- not None, not a KeyError."""
    path = write_artifact(tmp_path, 1, {"status": "final", "version": 1}, "body")
    assert artifacts.read_gate_overrides(path) == []


def test_resolve_latest_artifact_delegates_for_non_grounding_stage(tmp_path: Path):
    stage_dir = tmp_path / "01-ideation"
    write_artifact(stage_dir, 1, {"stage": "shorts-ideation"}, "body")
    resolved = resolve_latest_artifact(tmp_path, "ideation", stage_dir)
    assert resolved == stage_dir / "artifact.v1.md"


def test_resolve_latest_artifact_grounding_resolves_via_pointer(tmp_path: Path):
    rgs_briefs = tmp_path / "rgs-briefs"
    rgs_briefs.mkdir()
    brief = rgs_briefs / "2026-07-27-x.md"
    brief.write_text("---\nstatus: candidate\n---\n\nbody", encoding="utf-8")
    stage_dir = tmp_path / "runs" / "r1" / "00-grounding"
    write_pointer(stage_dir, "rgs-briefs/2026-07-27-x.md", tmp_path)

    assert resolve_latest_artifact(tmp_path, "grounding", stage_dir) == brief


def test_resolve_latest_artifact_grounding_no_pointer_returns_none(tmp_path: Path):
    stage_dir = tmp_path / "runs" / "r1" / "00-grounding"
    stage_dir.mkdir(parents=True)
    assert resolve_latest_artifact(tmp_path, "grounding", stage_dir) is None


def test_resolve_latest_artifact_grounding_pointer_target_missing_returns_none(tmp_path: Path):
    """The pointer file exists but the brief it names was deleted after the
    pointer was written -- must return None, not raise. This is the exact
    case the old inline branches in approval_service.py and routes/stages.py
    got wrong in two of three copies (they skipped the .exists() check)."""
    rgs_briefs = tmp_path / "rgs-briefs"
    rgs_briefs.mkdir()
    brief = rgs_briefs / "will-be-deleted.md"
    brief.write_text("body", encoding="utf-8")
    stage_dir = tmp_path / "runs" / "r1" / "00-grounding"
    write_pointer(stage_dir, "rgs-briefs/will-be-deleted.md", tmp_path)
    brief.unlink()
    assert resolve_latest_artifact(tmp_path, "grounding", stage_dir) is None


def test_atomic_write_leaves_prior_bytes_intact_when_the_write_dies_midway(tmp_path, monkeypatch):
    """A-63: the whole point. Path.write_text opens "w", truncating the target
    to zero before a byte of new content lands. Kill the write partway and the
    previous content must still be there, in full, and still parseable."""
    target = tmp_path / "artifact.v1.md"
    original = "---\nstatus: final\nversion: 1\n---\n\napproved body\n"
    target.write_text(original, encoding="utf-8")

    real_fsync = os.fsync

    def die_after_partial_write(fd):
        real_fsync(fd)
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "fsync", die_after_partial_write)

    with pytest.raises(OSError):
        _atomic_write_text(target, "---\nstatus: final\nversion: 2\n---\n\nnew body\n")

    assert target.read_text(encoding="utf-8") == original
    meta, body = artifacts.parse_frontmatter(target.read_text(encoding="utf-8"))
    assert meta["status"] == "final"
    assert "approved body" in body


def test_atomic_write_leaves_no_temp_file_behind_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "artifact.v1.md"
    target.write_text("original", encoding="utf-8")
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))

    with pytest.raises(OSError):
        _atomic_write_text(target, "replacement")

    assert target.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.iterdir()) == [target]


def test_write_artifact_refuses_to_overwrite_an_existing_version(tmp_path):
    """A-65/A-73: write_text overwrote silently, so two callers that computed
    the same N discarded one artifact version and its recorded gate results
    with no error surfaced anywhere."""
    write_artifact(tmp_path, 1, {"stage": "shorts-styleboard"}, "the real world lock")

    with pytest.raises(ArtifactExistsError) as exc:
        write_artifact(tmp_path, 1, {"stage": "shorts-styleboard"}, "clobber")

    assert "artifact.v1.md" in str(exc.value)
    assert "the real world lock" in (tmp_path / "artifact.v1.md").read_text(encoding="utf-8")


def test_write_artifact_uses_the_atomic_primitive(tmp_path, monkeypatch):
    calls = []
    real = artifacts._atomic_write_text
    monkeypatch.setattr(
        artifacts, "_atomic_write_text",
        lambda p, t: (calls.append(p), real(p, t))[1],
    )
    write_artifact(tmp_path, 1, {"stage": "x"}, "body")
    assert (tmp_path / "artifact.v1.md") in calls


def test_approval_stamp_does_not_destroy_the_approved_artifact_on_crash(tmp_path, monkeypatch):
    """A-63's sharpest edge: stamp_final is a read-modify-write over the ONLY copy
    of an already-approved artifact. A crash mid-write loses the approved output."""
    path = write_artifact(tmp_path, 1, {"status": "final", "version": 1}, "approved content")
    before = path.read_text(encoding="utf-8")

    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("power loss")))

    with pytest.raises(OSError):
        stamp_final(path, "2026-08-08T00:00:00+00:00")

    assert path.read_text(encoding="utf-8") == before
    meta, _ = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["status"] == "final"


def test_two_concurrent_callers_get_two_distinct_versions(tmp_path):
    """A-65: next_version_number globs and returns max+1 with no lock, and its
    caller runs the entire gate suite between the read and the write. Two
    overlapping edit POSTs both computed N, and the second silently overwrote
    the first -- an artifact version and its gate results gone, no error."""
    barrier = threading.Barrier(2)
    results: list[int] = []
    lock = threading.Lock()

    def allocate():
        barrier.wait(timeout=5)          # force the two scans to interleave
        res = reserve_version(tmp_path)
        with lock:
            results.append(res.version)

    threads = [threading.Thread(target=allocate) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert sorted(results) == [1, 2], f"lost write: both callers got {results}"


def test_many_concurrent_callers_all_get_distinct_versions(tmp_path):
    n = 12
    barrier = threading.Barrier(n)
    results: list[int] = []
    lock = threading.Lock()

    def allocate():
        barrier.wait(timeout=10)
        res = reserve_version(tmp_path)
        with lock:
            results.append(res.version)

    threads = [threading.Thread(target=allocate) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert len(set(results)) == n
    assert sorted(results) == list(range(1, n + 1))


def test_a_reservation_is_invisible_to_latest_artifact_path(tmp_path):
    """A held reservation must not be selectable as the stage's output --
    latest_artifact_path is what the approval and staleness paths read."""
    write_artifact(tmp_path, 1, {"stage": "x"}, "real")
    res = reserve_version(tmp_path)
    assert res.version == 2
    assert artifacts.latest_artifact_path(tmp_path).name == "artifact.v1.md"
    assert not list(tmp_path.glob("artifact.v2.md"))


def test_write_reserved_artifact_lands_at_the_reserved_version(tmp_path):
    res = reserve_version(tmp_path)
    path = write_reserved_artifact(res, {"stage": "x", "version": res.version}, "body")
    assert path.name == "artifact.v1.md"
    assert not res.reservation_path.exists()


def test_deleting_the_newest_artifact_does_not_reissue_its_version(tmp_path):
    """A-66: the sequence used to be whatever the directory currently contained,
    so deleting artifact.v3.md made the next write v3 again -- the version
    number, the supersedes chain and the `version:` field all lying about
    history, and any dependent whose depends_on recorded the old v3 hash now
    comparing against a different file at the same path."""
    for v in (1, 2, 3):
        write_artifact(tmp_path, v, {"version": v}, f"body {v}")
    (tmp_path / "artifact.v3.md").unlink()

    assert artifacts.next_version_number(tmp_path) == 4
    assert reserve_version(tmp_path).version == 4


def test_high_water_mark_survives_deleting_every_artifact(tmp_path):
    write_artifact(tmp_path, 1, {"version": 1}, "a")
    write_artifact(tmp_path, 2, {"version": 2}, "b")
    for p in tmp_path.glob("artifact.v*.md"):
        p.unlink()
    assert artifacts.next_version_number(tmp_path) == 3


def test_read_artifact_rejects_a_frontmatter_version_that_disagrees_with_the_filename(tmp_path):
    """A rename desynchronizes them permanently and silently -- nothing ever
    cross-checked the two."""
    write_artifact(tmp_path, 1, {"version": 1, "status": "final"}, "body")
    renamed = tmp_path / "artifact.v9.md"
    (tmp_path / "artifact.v1.md").rename(renamed)

    with pytest.raises(artifacts.MalformedArtifactError) as exc:
        artifacts.read_artifact(renamed)
    assert "does not match filename" in str(exc.value)


def test_corrupt_high_water_mark_is_warned_and_ignored_not_fatal(tmp_path, monkeypatch):
    events = []
    monkeypatch.setattr(artifacts.obs, "log", lambda e, **k: events.append((e, k)))
    write_artifact(tmp_path, 1, {"version": 1}, "a")
    (tmp_path / ".artifact-version-hwm").write_text("not a number", encoding="utf-8")

    assert artifacts.next_version_number(tmp_path) == 2
    assert any(e == "artifacts.hwm_unreadable" for e, _ in events)


def test_released_version_is_burnt_not_reissued(tmp_path):
    """A released number must never be reissued: anything that observed it --
    a log line, a `supersedes` field, a half-written temp -- must not be able
    to point at different content later (A-66)."""
    res = reserve_version(tmp_path)
    release_version(res)
    assert reserve_version(tmp_path).version == res.version + 1


def test_high_water_mark_sidecar_never_regresses_under_racing_writers(tmp_path):
    """A-66 follow-up: _record_high_water_mark's read (_high_water_mark) and
    write (_atomic_write_text) are two separate operations. Without a lock
    around that span, a low-version caller's read can happen before any
    higher-numbered value exists, get descheduled, and then have its stale
    "write low" land *after* a higher-version caller has already written a
    bigger number -- regressing the sidecar back down. This calls
    _record_high_water_mark directly (bypassing reserve_version) so the exact
    values racing are controlled, with a barrier forcing every thread to
    start its read-decide-write span at the same instant -- the scenario most
    likely to interleave a low write after a high one. Every value is written
    by some thread; the assertion is that the sidecar's FINAL on-disk value is
    the max of everything written, never a value some other thread already
    beat it with."""
    values = [1, 12, 2, 11, 3, 10, 4, 9, 5, 8, 6, 7]
    n = len(values)
    barrier = threading.Barrier(n)

    def record(v):
        barrier.wait(timeout=10)
        artifacts._record_high_water_mark(tmp_path, v)

    threads = [threading.Thread(target=record, args=(v,)) for v in values]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert artifacts._high_water_mark(tmp_path) == max(values), (
        "sidecar regressed: a lower-version writer's stale write landed after "
        "the highest-version writer's write"
    )


def test_zero_padded_duplicate_does_not_make_latest_artifact_nondeterministic(tmp_path):
    """A-67: artifact.v07.md and artifact.v7.md both parsed to 7, and
    max(..., key=...) resolved the tie by glob iteration order -- which one the
    app treated as the stage's output was filesystem-dependent."""
    (tmp_path / "artifact.v7.md").write_text("the real one", encoding="utf-8")
    (tmp_path / "artifact.v07.md").write_text("an OS copy", encoding="utf-8")

    assert artifacts.latest_artifact_path(tmp_path).name == "artifact.v7.md"
    assert [v for v, _ in artifacts._versions_in(tmp_path)] == [7]


def test_unparseable_sibling_is_warned_and_enumerable_not_silently_dropped(tmp_path, monkeypatch):
    """A rescued or hand-annotated artifact used to vanish from the app while
    sitting in plain sight in the directory."""
    events = []
    monkeypatch.setattr(artifacts.obs, "log", lambda e, **k: events.append((e, k)))
    (tmp_path / "artifact.v1.md").write_text("real", encoding="utf-8")
    (tmp_path / "artifact.vfinal.md").write_text("rescued", encoding="utf-8")
    (tmp_path / "artifact.v3 (copy).md").write_text("os copy", encoding="utf-8")

    artifacts._versions_in(tmp_path)
    assert sum(1 for e, _ in events if e == "artifacts.unversioned_sibling") == 2

    names = {p.name for p in artifacts.list_unversioned_siblings(tmp_path)}
    assert names == {"artifact.vfinal.md", "artifact.v3 (copy).md"}


def test_v10_still_outranks_v9(tmp_path):
    """Verified non-issue -- pinned so nobody "fixes" the numeric comparison
    into a string one."""
    (tmp_path / "artifact.v9.md").write_text("nine", encoding="utf-8")
    (tmp_path / "artifact.v10.md").write_text("ten", encoding="utf-8")
    assert artifacts.latest_artifact_path(tmp_path).name == "artifact.v10.md"


class TestDurabilityContract:
    """Every path that rewrites a file an operator can lose must satisfy all
    four clauses. F-18: nothing asserted that a write is atomic, that version
    allocation is exclusive, or that a migration cannot overwrite an existing
    file -- and all three S0s live in that gap.

    Crash injection is done by monkeypatching os.replace / os.fsync rather than
    by killing a subprocess: the failure point is exact and the test is
    deterministic, and the conftest guard (P0) blocks unmarked subprocess use
    anyway. The property under test is "the target is old-bytes or new-bytes,
    never in between", which does not need a real SIGKILL to exercise.
    """

    WRITERS = ["write_artifact", "stamp_final", "record_gate_override", "write_pointer"]

    @staticmethod
    def _prepare(tmp_path, writer):
        """Returns (target_path, invoke_callable) for the named writer."""
        if writer == "write_pointer":
            briefs = tmp_path / "rgs-briefs"
            briefs.mkdir()
            (briefs / "a.md").write_text("a", encoding="utf-8")
            (briefs / "b.md").write_text("b", encoding="utf-8")
            sd = tmp_path / "runs" / "r1" / "00-grounding"
            grounding_service.write_pointer(sd, "rgs-briefs/a.md", tmp_path)
            return sd / "pointer.yaml", lambda: grounding_service.write_pointer(
                sd, "rgs-briefs/b.md", tmp_path)
        path = write_artifact(tmp_path, 1, {"status": "final", "version": 1}, "approved body")
        if writer == "write_artifact":
            return path, lambda: artifacts.write_artifact(
                tmp_path, 2, {"status": "draft", "version": 2}, "v2 body")
        if writer == "stamp_final":
            return path, lambda: artifacts.stamp_final(path, "2026-08-08T00:00:00+00:00")
        return path, lambda: artifacts.record_gate_override(
            path, "accepted", at="2026-08-08T00:00:00+00:00")

    @pytest.mark.parametrize("writer", WRITERS)
    @pytest.mark.parametrize("break_at", ["fsync", "replace"])
    def test_prior_bytes_survive_a_crash_at_any_point(self, tmp_path, monkeypatch,
                                                      writer, break_at):
        target, invoke = self._prepare(tmp_path, writer)
        before = target.read_bytes()
        monkeypatch.setattr(
            os, break_at,
            lambda *a, **k: (_ for _ in ()).throw(OSError(f"crash at {break_at}")),
        )
        with pytest.raises(OSError):
            invoke()
        assert target.read_bytes() == before

    @pytest.mark.parametrize("writer", WRITERS)
    def test_no_temp_file_is_left_behind_or_selectable(self, tmp_path, monkeypatch, writer):
        target, invoke = self._prepare(tmp_path, writer)
        monkeypatch.setattr(os, "replace",
                            lambda *a, **k: (_ for _ in ()).throw(OSError("crash")))
        with pytest.raises(OSError):
            invoke()
        assert not list(target.parent.glob("*.tmp"))
        assert artifacts.latest_artifact_path(target.parent) in (None, target) or \
            target.name == "pointer.yaml"

    @pytest.mark.parametrize("writer", WRITERS)
    def test_the_target_is_never_observed_zero_length(self, tmp_path, monkeypatch, writer):
        """The specific shape truncation takes: a zero-byte or half-written
        target that parse_frontmatter used to report as a legitimate
        no-frontmatter artifact (A-63 -> A-68)."""
        target, invoke = self._prepare(tmp_path, writer)
        sizes = []
        real_replace = os.replace

        def observe(src, dst, *a, **k):
            sizes.append(Path(dst).stat().st_size if Path(dst).exists() else -1)
            return real_replace(src, dst, *a, **k)

        monkeypatch.setattr(os, "replace", observe)
        invoke()
        assert all(s != 0 for s in sizes), "the target was truncated before the rename"
        assert target.stat().st_size > 0
