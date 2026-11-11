from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

import av
from av.container import InputContainer

from constants import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS


def _reject_secondary_input(url: str, _flags: int, _options: dict[str, str]) -> BinaryIO:
    """Prevent a recording from opening a second file or a network resource."""
    raise OSError(f"External media references are unavailable: {url}")


@contextmanager
def open_recording(path: Path) -> Iterator[InputContainer]:
    """Give the decoder a read-only stream for the selected file."""
    with (
        path.open("rb") as stream,
        av.open(
            stream,
            mode="r",
            io_open=_reject_secondary_input,
            options={
                "format_whitelist": "mov,matroska,webm,avi,mpegts,mp3,wav,flac,aac,ogg,aiff",
                "protocol_whitelist": "pipe",
            },
        ) as container,
    ):
        yield container


def is_media_file(file_path: str) -> bool:
    """Check if the file is a media file."""
    if not file_path:
        return False

    return any(
        file_path.lower().endswith(ext.replace("*", "")) for ext in AUDIO_EXTENSIONS + VIDEO_EXTENSIONS
    )


def get_media_dialog_file_types() -> tuple[str, ...]:
    """Get media file dialog file types."""
    file_types = (
        f"Media Files ({';'.join(AUDIO_EXTENSIONS + VIDEO_EXTENSIONS)})",
        f"Audio Files ({';'.join(AUDIO_EXTENSIONS)})",
        f"Video Files ({';'.join(VIDEO_EXTENSIONS)})",
    )
    return file_types
