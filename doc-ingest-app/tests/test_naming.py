from doc_ingest.config import Config
from doc_ingest import naming


def test_sanitize_strips_forbidden_windows_characters():
    assert naming.sanitize_component('a<b>c:d"e/f\\g|h?i*j') == "abcdefghij"


def test_sanitize_strips_trailing_spaces_and_periods():
    assert naming.sanitize_component("Report. . ") == "Report"


def test_sanitize_collapses_whitespace_runs():
    assert naming.sanitize_component("Coaching   Agreement") == "Coaching Agreement"


def test_sanitize_preserves_ordinary_characters_and_casing():
    assert naming.sanitize_component("Client's Notes & Plan #2") == "Client's Notes & Plan #2"


def test_build_dest_rel_path_preserves_full_extension_as_stem():
    cfg = Config()
    dest = naming.build_dest_rel_path("Folder/Coaching Agreement Template.docx", version=1, cfg=cfg)
    assert dest == "Folder/Coaching Agreement Template.docx.md"


def test_build_dest_rel_path_versions_beyond_v1():
    cfg = Config()
    dest = naming.build_dest_rel_path("Folder/Notes.pdf", version=3, cfg=cfg)
    assert dest == "Folder/Notes.pdf.v3.md"


def test_build_dest_rel_path_eliminates_cross_type_stem_collision():
    cfg = Config()
    pdf_dest = naming.build_dest_rel_path("F2BU_12Week_Accelerator_Infographic.pdf", version=1, cfg=cfg)
    png_dest = naming.build_dest_rel_path("F2BU_12Week_Accelerator_Infographic.png", version=1, cfg=cfg)
    assert pdf_dest != png_dest
    assert pdf_dest == "F2BU_12Week_Accelerator_Infographic.pdf.md"
    assert png_dest == "F2BU_12Week_Accelerator_Infographic.png.md"


def _realistic_long_source():
    # Deliberately not single-character folder segments: a segment that's
    # already shorter than its own shortened form must never be "shortened"
    # into something longer (that was the exact bug this fixture caught).
    # Modeled on real corpus paths, which are already 300+ chars before the
    # output root is even added (spec §6).
    return "/".join([
        "Client Coaching Session Recordings And Notes",
        "2026 Individual Sessions Archive",
        "Very Long Coaching Session Transcript With A Lot Of Detail In The Name.docx",
    ])


def test_build_dest_rel_path_shortens_when_over_threshold():
    cfg = Config(long_path_threshold_chars=120)
    dest = naming.build_dest_rel_path(_realistic_long_source(), version=1, cfg=cfg)
    assert len(dest) <= cfg.long_path_threshold_chars
    assert dest.endswith(".md")


def test_build_dest_rel_path_shortening_never_makes_a_path_longer():
    # The regression case: a folder tree of already-short segments must not
    # come out longer than it went in just because the shortener touched it.
    cfg = Config(long_path_threshold_chars=10)  # unreachably tight on purpose
    long_source = "A/" * 20 + "B.docx"
    unshortened_len = len(long_source.replace(".docx", ".docx.md"))
    dest = naming.build_dest_rel_path(long_source, version=1, cfg=cfg)
    assert len(dest) <= unshortened_len


def test_build_dest_rel_path_shortening_is_deterministic():
    cfg = Config(long_path_threshold_chars=120)
    source = _realistic_long_source()
    dest1 = naming.build_dest_rel_path(source, version=1, cfg=cfg)
    dest2 = naming.build_dest_rel_path(source, version=1, cfg=cfg)
    assert dest1 == dest2


def test_build_dest_rel_path_honors_prefix_len_for_the_full_absolute_path():
    # A relative path that fits cfg.long_path_threshold_chars on its own can
    # still push the FULL path (converted_root + separator + relative path)
    # over the limit -- prefix_len is how the caller (Gate 2) accounts for
    # that (spec §6). threshold=200 is picked so prefix_len=0 needs no
    # shortening at all but prefix_len=60 does -- otherwise both branches
    # could trivially agree without the parameter having done anything.
    cfg = Config(long_path_threshold_chars=200)
    source = _realistic_long_source()
    dest_no_prefix = naming.build_dest_rel_path(source, version=1, cfg=cfg, prefix_len=0)
    dest_with_prefix = naming.build_dest_rel_path(source, version=1, cfg=cfg, prefix_len=60)
    assert len(dest_with_prefix) < len(dest_no_prefix)
    assert len(dest_with_prefix) + 60 <= cfg.long_path_threshold_chars


def test_resolve_collision_returns_unchanged_when_not_taken():
    dest, collided = naming.resolve_collision("Folder/Notes.pdf.md", is_taken=lambda p: False)
    assert dest == "Folder/Notes.pdf.md"
    assert collided is False


def test_resolve_collision_appends_hash_suffix_when_taken():
    taken = {"Folder/Notes.pdf.md"}
    dest, collided = naming.resolve_collision("Folder/Notes.pdf.md", is_taken=lambda p: p in taken)
    assert dest != "Folder/Notes.pdf.md"
    assert dest.endswith(".md")
    assert collided is True


def test_long_path_prefixes_an_absolute_path(tmp_path):
    target = tmp_path / "a.md"
    result = naming.long_path(target)
    assert result.startswith("\\\\?\\")
    assert str(target.resolve()) in result


def test_long_path_is_idempotent_on_an_already_prefixed_path(tmp_path):
    target = tmp_path / "a.md"
    once = naming.long_path(target)
    twice = naming.long_path(once)
    assert once == twice
