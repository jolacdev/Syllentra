"""Serialize normalized transcripts without dialogs or filesystem side effects."""

from schemas.batch import ExportFormat, InferenceOutput
from utils.time_utils import format_seconds_to_srt_time


def render_output(transcript: InferenceOutput, format: ExportFormat) -> str:
    """Serialize original text or timed cues with Unicode and format-specific escaping."""
    if format == "txt":
        return transcript["text"].strip() + "\n"
    if format not in ("srt", "vtt"):
        raise ValueError("Choose TXT, SRT or VTT.")
    blocks = []
    for index, segment in enumerate(transcript["segments"], 1):
        start = format_seconds_to_srt_time(segment["start"])
        end = format_seconds_to_srt_time(segment["end"])
        text = segment["text"]
        if format == "vtt":
            start, end = start.replace(",", "."), end.replace(",", ".")
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        blocks.append(f"{index}\n{start} --> {end}\n{text}\n")
    return ("WEBVTT\n\n" if format == "vtt" else "") + "\n".join(blocks)
