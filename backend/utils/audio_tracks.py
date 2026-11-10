"""Inspect container tracks and resolve a language preference separately for every source."""

from pathlib import Path

import av

from schemas.batch import AudioSelection
from utils.language_utils import normalize_language
from utils.matroska_languages import matroska_languages


def resolve_audio(selection: AudioSelection, preferred_language: str | None) -> AudioSelection:
    """Apply overrides first and use language preferences only when more than one audio track exists."""
    tracks = selection["tracks"]
    if not tracks:
        return {**selection, "selectedIndex": None, "reason": "unavailable"}
    override = next((track for track in tracks if track["index"] == selection["overrideIndex"]), None)
    if override is not None:
        return {**selection, "selectedIndex": override["index"], "reason": "override"}
    if len(tracks) == 1:
        return {**selection, "selectedIndex": tracks[0]["index"], "reason": "single"}
    matches = [track for track in tracks if preferred_language and track["language"] == preferred_language]
    if matches:
        chosen = min(
            matches,
            key=lambda track: (
                track["isCommentary"] or track["isAudioDescription"],
                not track["isDefault"],
                track["number"],
            ),
        )
        return {**selection, "selectedIndex": chosen["index"], "reason": "preferred"}
    chosen = next((track for track in tracks if track["isDefault"]), tracks[0])
    return {
        **selection,
        "selectedIndex": chosen["index"],
        "reason": "fallback" if preferred_language else "default",
    }


def inspect_audio(source: Path, preferred_language: str | None) -> AudioSelection:
    """Probe headers during background import and retain probe failures for per-file diagnostics."""
    selection: AudioSelection = {
        "tracks": [],
        "selectedIndex": None,
        "overrideIndex": None,
        "reason": "unavailable",
        "probeError": None,
    }
    try:
        with av.open(str(source)) as container:
            streams = list(container.streams.audio)
            modern = matroska_languages(source)
            if modern is not None and len(modern) != len(streams):
                raise ValueError("Matroska audio track headers do not match decoded streams.")
            for number, stream in enumerate(streams, 1):
                metadata = {key.casefold(): value for key, value in stream.metadata.items()}
                raw = metadata.get("language")
                if modern is not None and modern[number - 1] is not None:
                    raw = modern[number - 1]
                title = metadata.get("title", "")
                selection["tracks"].append(
                    {
                        "index": stream.index,
                        "number": number,
                        "language": normalize_language(raw),
                        "rawLanguage": raw,
                        "title": title,
                        "codec": stream.codec_context.name,
                        "channels": stream.codec_context.channels,
                        "isDefault": bool(stream.disposition & av.stream.Disposition.default),
                        "isCommentary": bool(stream.disposition & av.stream.Disposition.comment),
                        "isAudioDescription": bool(
                            stream.disposition & av.stream.Disposition.visual_impaired
                        ),
                    }
                )
            if not selection["tracks"]:
                selection["probeError"] = "This recording has no audio stream."
    except (OSError, ValueError) as error:
        selection["tracks"] = []
        selection["probeError"] = str(error)
    return resolve_audio(selection, preferred_language)
