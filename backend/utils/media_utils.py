from constants import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS


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
