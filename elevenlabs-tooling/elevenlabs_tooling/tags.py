"""Compose bracket-audio-tag script text for a single continuous
eleven_v3 TTS generation.

Bracket audio tags ([excited], [whispers], [sighs], [pause], etc.) are
supported on eleven_v3 only -- NOT eleven_multilingual_v2, eleven_flash_v2,
or eleven_flash_v2_5 (breaks.py's compose_break_tagged_text is those
models' equivalent mechanism, using SSML <break> instead). eleven_v3 has no
<break> tag at all (verified against ElevenLabs' own help-center docs,
2026-08-19, and confirmed live 2026-08-21: eleven_v3 replaces <break> with
bracketed audio tags and punctuation-based pacing).

Beats are joined with a blank line ("\\n\\n"), matching
stitcher.vo_alignment.derive_segments_v3's own paragraph-split convention --
the two must stay in lockstep: derive_segments_v3 recovers segment
boundaries by splitting the submitted text on the exact same separator.
"""

from __future__ import annotations


def compose_tagged_text(beats: list[str], beat_tags: list[str | None]) -> str:
    """Join `beats` with a blank line between each pair, prefixing each
    beat with its bracket tag(s) -- a literal string like "[excited]" or a
    stacked "[pause][whispers]" -- or leaving it untagged when
    `beat_tags[i]` is None. Not every beat needs a tag: per this project's
    anti-invention discipline, a beat with no genuinely-fitting catalog tag
    should get None here and rely on punctuation alone, rather than an
    invented tag presented as known-good.

    len(beat_tags) must equal len(beats).
    """
    if len(beats) < 1:
        raise ValueError("beats must contain at least one beat")
    if len(beat_tags) != len(beats):
        raise ValueError(
            f"beat_tags must have exactly {len(beats)} entries (one per beat), "
            f"got {len(beat_tags)}"
        )
    pieces = [f"{tag} {beat}" if tag else beat for beat, tag in zip(beats, beat_tags)]
    return "\n\n".join(pieces)
