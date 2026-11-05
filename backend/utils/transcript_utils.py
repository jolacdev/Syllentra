"""Validate normalized transcript JSON and subtitle timing invariants."""

import math

from schemas.batch import InferenceOutput
from schemas.transcription import TranscriptionSegment


def require_string(value: object) -> str:
    """Validate a string received from a vendor, session file, or worker message."""
    if not isinstance(value, str):
        raise ValueError("A transcript or worker message contains invalid text.")
    return value


def require_number(value: object) -> float:
    """Validate a finite numeric duration or timestamp without accepting booleans."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError("The transcript contains an invalid timestamp.")
    return float(value)


def parse_output(value: object) -> InferenceOutput:
    """Validate an immutable normalized result at a JSON boundary."""
    if not isinstance(value, dict) or not isinstance(value.get("segments"), list):
        raise ValueError("The transcription result is invalid.")
    duration = require_number(value.get("duration"))
    if duration <= 0:
        raise ValueError("The recording has no valid duration.")
    raw_segments: object = value.get("segments")
    if not isinstance(raw_segments, list):
        raise ValueError("The transcription result has no valid segments.")
    segments: list[TranscriptionSegment] = []
    previous = 0.0
    for raw in raw_segments:
        if not isinstance(raw, dict):
            raise ValueError("The transcription result contains an invalid segment.")
        start, end = require_number(raw.get("start")), require_number(raw.get("end"))
        if start < previous or end <= start or end > duration + 0.1:
            raise ValueError("The transcript has invalid or overlapping subtitle timings.")
        segments.append(
            {"id": len(segments), "start": start, "end": end, "text": require_string(raw.get("text"))}
        )
        previous = end
    language: object = value.get("language")
    if language is not None and not isinstance(language, str):
        raise ValueError("The reported language is invalid.")
    return {
        "text": require_string(value.get("text")),
        "duration": duration,
        "language": language,
        "segments": segments,
    }
