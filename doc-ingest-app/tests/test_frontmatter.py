import pytest
import yaml

from doc_ingest import frontmatter


def _base(source_path="Folder/Notes.docx"):
    return {
        "source_path": source_path,
        "source_type": "docx",
        "source_hash": "abc123",
        "source_modified_at": "2026-08-01T00:00:00+00:00",
        "converted_at": "2026-08-13T00:00:00+00:00",
        "conversion_tool": "firecrawl-parse",
        "version": 1,
        "status": "current",
        "business_line": "freedom2beu",
        "gauntlet_passed_at": "2026-08-13T00:00:01+00:00",
    }


def test_build_frontmatter_merges_base_and_extras():
    fm = frontmatter.build_frontmatter(_base(), {"word_count": 42})
    assert fm["word_count"] == 42
    assert fm["business_line"] == "freedom2beu"


def test_serialize_round_trips_through_a_real_yaml_parser():
    fm = frontmatter.build_frontmatter(_base(), {"word_count": 42})
    assembled = frontmatter.serialize(fm, "# Body\n\ncontent here")
    parsed_fm, body = frontmatter.parse(assembled)
    assert parsed_fm["word_count"] == 42
    assert parsed_fm["source_path"] == "Folder/Notes.docx"
    assert body.strip() == "# Body\n\ncontent here"


def test_serialize_handles_special_characters_from_real_source_paths():
    special_path = "Client's Notes & Session #3: Recap.docx"
    fm = frontmatter.build_frontmatter(_base(source_path=special_path), {})
    assembled = frontmatter.serialize(fm, "body")
    parsed_fm, _ = frontmatter.parse(assembled)
    assert parsed_fm["source_path"] == special_path


def test_serialize_uses_a_real_yaml_library_not_string_interpolation():
    fm = frontmatter.build_frontmatter(_base(), {})
    assembled = frontmatter.serialize(fm, "body")
    header = assembled.split("---")[1]
    reparsed = yaml.safe_load(header)
    assert reparsed["source_path"] == fm["source_path"]


def test_parse_raises_on_malformed_yaml():
    broken = "---\nsource_path: [unterminated\n---\nbody"
    with pytest.raises(yaml.YAMLError):
        frontmatter.parse(broken)


def test_parse_raises_on_missing_frontmatter_delimiters():
    with pytest.raises(ValueError):
        frontmatter.parse("just a body, no frontmatter at all")
