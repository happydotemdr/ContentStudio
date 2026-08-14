"""Frontmatter is always built as a dict and serialized via PyYAML's safe
dumper -- never hand-formatted string interpolation. Real source_path values
in this corpus contain curly apostrophes, '&', ':', '#' (spec §7); a dumper
quotes/escapes these correctly by construction, hand-formatting would not."""
from __future__ import annotations

import yaml

REQUIRED_BASE_FIELDS = (
    "source_path", "source_type", "source_hash", "source_modified_at",
    "converted_at", "conversion_tool", "version", "status", "business_line",
    "gauntlet_passed_at",
)


def build_frontmatter(base: dict, extras: dict) -> dict:
    merged = dict(base)
    merged.update(extras)
    return merged


def serialize(fm: dict, body: str) -> str:
    header = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{header}---\n\n{body}"


def parse(assembled_markdown: str) -> tuple[dict, str]:
    if not assembled_markdown.startswith("---\n"):
        raise ValueError("no frontmatter delimiter at start of file")
    _, _, rest = assembled_markdown.partition("---\n")
    header, sep, body = rest.partition("\n---\n")
    if not sep:
        raise ValueError("no closing frontmatter delimiter found")
    fm = yaml.safe_load(header)
    if not isinstance(fm, dict):
        raise ValueError("frontmatter did not parse to a mapping")
    return fm, body.lstrip("\n")
