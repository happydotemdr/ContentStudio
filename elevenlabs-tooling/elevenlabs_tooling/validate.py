"""Payload/URL validation -- the hard gate before any ElevenLabs API call.

Structure mirrors scripts/lint_prompt_sheet.py (Gate C) in the parent repo: a
flat list of Finding(check, message) accumulated by running every check to
completion, never stopping at the first problem. "E#" findings block a send;
"W#" findings are informational only.

Every check that reads a payload field guards its type before comparing or
measuring it: a malformed payload must produce a Finding, never an uncaught
TypeError from a tool whose entire job is to fail safely on bad input.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit, SplitResult

PINNED_NARRATOR_VOICE_ID = "eDwT8Vhp2yxJzAMmuuPA"
ALLOWED_HOST = "api.elevenlabs.io"
ALLOWED_SCHEME = "https"
OUT_OF_SCOPE_PATH_MARKERS = (
    "/stream",
    "/compose_stream",
    "/music/detailed",
    "/compose_detailed",
    "/compose_detailed_stream",
)
SPEED_MIN, SPEED_MAX = 0.7, 1.2
SIMILARITY_WARN_ABOVE = 0.9
MAX_DICTIONARY_LOCATORS = 3
MAX_REQUEST_IDS = 3
SEED_MIN, SEED_MAX = 0, 4_294_967_295


@dataclass(frozen=True)
class Finding:
    check: str
    message: str


def is_blocking(finding: Finding) -> bool:
    return finding.check.startswith("E")


def validate(payload: dict, url: str) -> list[Finding]:
    """Run every check; return every finding. Never stops at the first one."""
    findings: list[Finding] = []
    findings.extend(_check_url(url))
    findings.extend(_check_shape(payload))
    findings.extend(_check_model_id(payload))
    findings.extend(_check_speed(payload))
    findings.extend(_check_stitching_conflict(payload, url))
    findings.extend(_check_pvc_v3(payload, url))
    findings.extend(_check_dictionary_locators(payload))
    findings.extend(_check_request_ids(payload))
    findings.extend(_check_seed_range(payload))
    findings.extend(_check_music_conflicts(payload))
    findings.extend(_check_output_format(url))
    findings.extend(_check_similarity_boost(payload))
    return findings


def _check_url(url: str) -> list[Finding]:
    findings: list[Finding] = []
    parts = urlsplit(url)
    if parts.scheme != ALLOWED_SCHEME or parts.hostname != ALLOWED_HOST:
        findings.append(Finding(
            "E1",
            f"URL must be {ALLOWED_SCHEME}://{ALLOWED_HOST}/... , got "
            f"{parts.scheme!r}://{parts.hostname!r}",
        ))
    lowered_path = parts.path.lower()
    for marker in OUT_OF_SCOPE_PATH_MARKERS:
        if marker in lowered_path:
            findings.append(Finding(
                "E2",
                f"URL path {parts.path!r} targets a v1-out-of-scope endpoint "
                f"({marker}) -- streaming and multipart-detailed responses "
                "are not supported by this tool",
            ))
            break
    return findings


def _check_shape(payload: dict) -> list[Finding]:
    has_text = bool(payload.get("text"))
    has_prompt = payload.get("prompt") is not None
    has_plan = payload.get("composition_plan") is not None
    music_field_count = sum([has_prompt, has_plan])

    if has_text and music_field_count == 0:
        return []
    if not has_text and music_field_count == 1:
        return []
    if has_text and music_field_count > 0:
        return [Finding(
            "E3",
            "payload has both a TTS field (text) and a music field "
            "(prompt/composition_plan) -- pick one shape",
        )]
    if music_field_count > 1:
        return [Finding(
            "E3",
            "payload has both prompt and composition_plan -- they are "
            "mutually exclusive",
        )]
    return [Finding(
        "E3",
        "payload is neither TTS-shaped (non-empty text) nor music-shaped "
        "(exactly one of prompt/composition_plan)",
    )]


def _voice_settings(payload: dict) -> dict:
    """Safely extract voice_settings as a dict; return {} if absent or wrong type."""
    raw_settings = payload.get("voice_settings")
    return raw_settings if isinstance(raw_settings, dict) else {}


def _check_model_id(payload: dict) -> list[Finding]:
    if not payload.get("model_id"):
        return [Finding("E4", "model_id must be present and non-empty")]
    return []


def _check_speed(payload: dict) -> list[Finding]:
    raw_settings = payload.get("voice_settings")
    if raw_settings is not None and not isinstance(raw_settings, dict):
        return [Finding("E5", f"voice_settings {raw_settings!r} must be a dict")]
    settings = _voice_settings(payload)
    speed = settings.get("speed")
    if speed is None:
        return []
    if not isinstance(speed, (int, float)) or isinstance(speed, bool):
        return [Finding("E5", f"voice_settings.speed {speed!r} must be a number")]
    if not (SPEED_MIN <= speed <= SPEED_MAX):
        return [Finding(
            "E5",
            f"voice_settings.speed {speed!r} is outside the valid range "
            f"{SPEED_MIN}-{SPEED_MAX}",
        )]
    return []


def _check_stitching_conflict(payload: dict, url: str) -> list[Finding]:
    query = parse_qs(urlsplit(url).query)
    enable_logging = query.get("enable_logging", ["true"])[0].lower()
    has_stitching = "previous_request_ids" in payload or "next_request_ids" in payload
    if enable_logging == "false" and has_stitching:
        return [Finding(
            "E6",
            "enable_logging=false in the URL disables request stitching, "
            "but the payload sets previous_request_ids/next_request_ids",
        )]
    return []


def _voice_id_from_tts_path(parts: SplitResult) -> str | None:
    """The path segment right after 'text-to-speech', or None.

    Not simply the last segment: /v1/text-to-speech/{voice_id}/with-timestamps
    is a real, in-scope path shape where the voice_id is NOT last.
    """
    segments = [segment for segment in parts.path.split("/") if segment]
    if "text-to-speech" not in segments:
        return None
    index = segments.index("text-to-speech")
    if index + 1 >= len(segments):
        return None
    return segments[index + 1]


def _check_pvc_v3(payload: dict, url: str) -> list[Finding]:
    parts = urlsplit(url)
    voice_id = _voice_id_from_tts_path(parts)
    model_id = str(payload.get("model_id") or "")
    if voice_id != PINNED_NARRATOR_VOICE_ID or "v3" not in model_id:
        return []
    if "use_pvc_as_ivc" not in payload:
        return [Finding(
            "E7",
            "the pinned narrator is a PVC on a v3 model; use_pvc_as_ivc "
            "must be set explicitly (true or false) -- see "
            "channel-voice.md Open action 3",
        )]
    if not isinstance(payload["use_pvc_as_ivc"], bool):
        return [Finding("E7", "use_pvc_as_ivc must be a boolean")]
    return []


def _check_dictionary_locators(payload: dict) -> list[Finding]:
    locators = payload.get("pronunciation_dictionary_locators")
    if locators is None:
        return []
    if not isinstance(locators, list):
        return [Finding("E8", "pronunciation_dictionary_locators must be a list")]
    if len(locators) > MAX_DICTIONARY_LOCATORS:
        return [Finding(
            "E8",
            f"pronunciation_dictionary_locators has {len(locators)} entries, "
            f"the maximum is {MAX_DICTIONARY_LOCATORS}",
        )]
    return []


def _check_request_ids(payload: dict) -> list[Finding]:
    findings: list[Finding] = []
    for field in ("previous_request_ids", "next_request_ids"):
        ids = payload.get(field)
        if ids is None:
            continue
        if not isinstance(ids, list):
            findings.append(Finding("E9", f"{field} must be a list"))
            continue
        if len(ids) > MAX_REQUEST_IDS:
            findings.append(Finding(
                "E9",
                f"{field} has {len(ids)} entries, the maximum is {MAX_REQUEST_IDS}",
            ))
    return findings


def _check_seed_range(payload: dict) -> list[Finding]:
    seed = payload.get("seed")
    if seed is None:
        return []
    if isinstance(seed, bool) or not isinstance(seed, int) or not (SEED_MIN <= seed <= SEED_MAX):
        return [Finding(
            "E10", f"seed {seed!r} must be an integer in {SEED_MIN}-{SEED_MAX}"
        )]
    return []


def _check_music_conflicts(payload: dict) -> list[Finding]:
    findings: list[Finding] = []
    has_prompt = payload.get("prompt") is not None
    plan = payload.get("composition_plan")
    has_plan = plan is not None

    if payload.get("seed") is not None and has_prompt:
        findings.append(Finding(
            "E11", "seed is plan-only and cannot be used together with prompt"
        ))
    if payload.get("force_instrumental") is not None and has_plan:
        findings.append(Finding(
            "E12",
            "force_instrumental is prompt-only and does not apply to composition_plan",
        ))
    if payload.get("music_length_ms") is not None and has_plan:
        findings.append(Finding(
            "E13",
            "music_length_ms is prompt-only; a composition_plan's length "
            "comes from its chunks",
        ))
    if has_plan and isinstance(plan, dict) and plan.get("chunks"):
        if payload.get("model_id") != "music_v2":
            findings.append(Finding(
                "E14",
                "composition_plan.chunks is set but model_id is not "
                "'music_v2' -- chunk plans require music_v2",
            ))
    return findings


def _check_output_format(url: str) -> list[Finding]:
    query = parse_qs(urlsplit(url).query)
    if "output_format" not in query:
        return [Finding(
            "W1",
            "URL has no output_format query param -- a default applies, "
            "but state the value chosen rather than leaving it implicit",
        )]
    return []


def _check_similarity_boost(payload: dict) -> list[Finding]:
    raw_settings = payload.get("voice_settings")
    if raw_settings is not None and not isinstance(raw_settings, dict):
        return [Finding("W2", f"voice_settings {raw_settings!r} must be a dict")]
    settings = _voice_settings(payload)
    similarity = settings.get("similarity_boost")
    if similarity is None:
        return []
    if not isinstance(similarity, (int, float)) or isinstance(similarity, bool):
        return [Finding(
            "W2", f"voice_settings.similarity_boost {similarity!r} must be a number"
        )]
    if similarity > SIMILARITY_WARN_ABOVE:
        return [Finding(
            "W2",
            f"voice_settings.similarity_boost {similarity!r} is above "
            f"{SIMILARITY_WARN_ABOVE} -- risk of an over-enunciated artifact "
            "(voice-selection.md) or reproducing reference noise "
            "(voice-settings.md, [T-unverified])",
        )]
    return []
