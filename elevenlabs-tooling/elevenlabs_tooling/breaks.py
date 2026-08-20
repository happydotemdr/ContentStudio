"""Compose ElevenLabs SSML <break> tags into a beat-by-beat script for a
single continuous TTS generation.

<break time="Xs" /> is supported on eleven_multilingual_v2, eleven_flash_v2,
and eleven_flash_v2_5 (NOT eleven_v3, which uses bracketed audio tags
instead) -- verified against ElevenLabs' own help-center docs, 2026-08-19.
Real breaks measured via /with-timestamps ground truth run long by roughly
50-210ms versus the requested duration (a consistent, one-directional
bias) -- see docs/superpowers/plans/2026-08-19-vo-architecture-test-plan.md
§6c. Size requested durations with that overshoot in mind, not as exact.
"""

from __future__ import annotations


def compose_break_tagged_text(beats: list[str], break_seconds: list[float]) -> str:
    """Join `beats` with `<break time="Xs" />` tags between each pair.

    len(break_seconds) must be exactly len(beats) - 1 -- one break between
    every pair of adjacent beats, none before the first or after the last.
    """
    if len(beats) < 1:
        raise ValueError("beats must contain at least one beat")
    if len(break_seconds) != len(beats) - 1:
        raise ValueError(
            f"break_seconds must have exactly {len(beats) - 1} entries "
            f"(one between each pair of {len(beats)} beats), got {len(break_seconds)}"
        )
    for seconds in break_seconds:
        if not (0 < seconds <= 3.0):
            raise ValueError(
                f"break duration {seconds}s is outside ElevenLabs' documented "
                "0-3s range for <break> tags"
            )

    parts = [beats[0]]
    for beat, seconds in zip(beats[1:], break_seconds):
        parts.append(f'<break time="{seconds:.1f}s" />')
        parts.append(beat)
    return " ".join(parts)
