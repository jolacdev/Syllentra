"""Read Matroska's modern language headers omitted by the bundled FFmpeg demuxer."""

from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

MAX_ID_BYTES = 4
MAX_METADATA_BYTES = 4096
AUDIO_TRACK = 2

SEGMENT = 0x18538067
TRACKS = 0x1654AE6B
TRACK_ENTRY = 0xAE
TRACK_TYPE = 0x83
LANGUAGE_BCP47 = 0x22B59D


def _integer(handle: BinaryIO, *, identifier: bool = False) -> tuple[int, int]:
    """Read an EBML variable-length integer, retaining the marker bits for element IDs."""
    first = handle.read(1)
    if not first or not first[0]:
        raise ValueError("Invalid Matroska element header.")
    length = 9 - first[0].bit_length()
    if identifier and length > MAX_ID_BYTES:
        raise ValueError("Invalid Matroska element ID.")
    tail = handle.read(length - 1)
    if len(tail) != length - 1:
        raise ValueError("Truncated Matroska element header.")
    head = first[0] if identifier else first[0] & ((1 << (8 - length)) - 1)
    return int.from_bytes(bytes([head]) + tail, "big"), length


def _elements(handle: BinaryIO, end: int) -> Iterator[tuple[int, int]]:
    """Visit sibling headers by seeking over their payloads, including media clusters."""
    while handle.tell() < end:
        identifier, _ = _integer(handle, identifier=True)
        size, length = _integer(handle)
        if size == (1 << (7 * length)) - 1:
            if identifier != SEGMENT:
                raise ValueError("Cannot locate Matroska tracks after an unknown-sized element.")
            element_end = end
        else:
            element_end = handle.tell() + size
        if element_end > end:
            raise ValueError("Truncated Matroska element.")
        yield identifier, element_end
        handle.seek(element_end)


def _audio_language(handle: BinaryIO, end: int) -> tuple[bool, str | None]:
    """Read only a track's type and modern language; other track metadata remains owned by PyAV."""
    audio = False
    language = None
    for identifier, element_end in _elements(handle, end):
        if identifier in (TRACK_TYPE, LANGUAGE_BCP47):
            size = element_end - handle.tell()
            if size > MAX_METADATA_BYTES:
                raise ValueError("Invalid Matroska track metadata size.")
            value = handle.read(size)
            if identifier == TRACK_TYPE:
                audio = int.from_bytes(value, "big") == AUDIO_TRACK
            else:
                language = value.decode("ascii")
    return audio, language


def matroska_languages(source: Path) -> list[str | None] | None:
    """Return modern tags in audio-track order, or None for non-EBML containers, without reading samples."""
    with source.open("rb") as handle:
        if handle.read(4) != bytes.fromhex("1a45dfa3"):
            return None
        handle.seek(0)
        for identifier, segment_end in _elements(handle, source.stat().st_size):
            if identifier != SEGMENT:
                continue
            for child, tracks_end in _elements(handle, segment_end):
                if child != TRACKS:
                    continue
                languages = []
                for entry, entry_end in _elements(handle, tracks_end):
                    if entry == TRACK_ENTRY:
                        audio, language = _audio_language(handle, entry_end)
                        if audio:
                            languages.append(language)
                return languages
        return []
