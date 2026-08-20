"""build_music_plan -- turns an operator-authored, structured bed_arc
(translating music-brief's prose movements) into an Eleven Music music_v2
composition plan. Chunks are built at bed-arc MOVEMENT boundaries, not per
real segment/gap: Eleven Music bounds every chunk's duration_ms to
3,000-120,000ms, and real inter-beat gaps (0.848-1.428s in the validated
take) fall well under that floor. Fine-grained response to a specific pause
or emphasis inside a movement is a style-prompt instruction (style_notes),
not a hard chunk boundary."""

from __future__ import annotations

from native_pipeline.errors import ChunkDurationTooShortError

MIN_CHUNK_MS = 3_000
MAX_CHUNK_MS = 120_000
MAX_CHUNKS = 30
TOTAL_DURATION_TOLERANCE_MS = 50

DENSITY_STYLES = {
    "sparse": (["sparse pad, minimal percussion"], ["vocals", "lyrics"]),
    "medium": (["moderate arrangement, gentle rhythm"], ["vocals", "lyrics"]),
    "full": (["full arrangement, rhythmic emphasis"], ["vocals", "lyrics"]),
}


def build_music_plan(bed_arc: list[dict], runtime: float) -> dict:
    chunks = []
    for movement in bed_arc:
        label = movement["label"]
        duration_ms = round((movement["end_s"] - movement["start_s"]) * 1000)
        if duration_ms < MIN_CHUNK_MS:
            raise ChunkDurationTooShortError(
                f"movement {label!r} is {duration_ms}ms, under Eleven Music's {MIN_CHUNK_MS}ms floor "
                f"-- merge with an adjacent movement"
            )
        if duration_ms > MAX_CHUNK_MS:
            raise ChunkDurationTooShortError(
                f"movement {label!r} is {duration_ms}ms, over Eleven Music's {MAX_CHUNK_MS}ms ceiling "
                f"-- split into two movements"
            )
        positive, negative = DENSITY_STYLES[movement["density"]]
        positive = list(positive)
        if movement.get("style_notes"):
            positive.append(movement["style_notes"])
        chunks.append({"duration_ms": duration_ms, "positive_styles": positive, "negative_styles": list(negative)})

    if len(chunks) > MAX_CHUNKS:
        raise ChunkDurationTooShortError(
            f"{len(chunks)} chunks exceeds Eleven Music's {MAX_CHUNKS}-chunk ceiling -- merge adjacent movements"
        )

    total_ms = sum(c["duration_ms"] for c in chunks)
    expected_ms = round(runtime * 1000)
    if abs(total_ms - expected_ms) > TOTAL_DURATION_TOLERANCE_MS:
        raise ChunkDurationTooShortError(
            f"composition plan totals {total_ms}ms, take runtime is {expected_ms}ms "
            f"(off by {abs(total_ms - expected_ms)}ms) -- bed_arc movements must cover the full take"
        )

    return {"model_id": "music_v2", "force_instrumental": True, "composition_plan": {"chunks": chunks}}
