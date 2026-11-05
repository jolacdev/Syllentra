import os
import sys
from pathlib import Path

from platformdirs import user_data_dir

from constants import APP_DATA_NAME


def get_data_directory() -> Path:
    """Preserve installed data and accept both current and legacy development overrides."""
    override = os.environ.get("SYLLENTRA_DATA_DIR") or os.environ.get("PYWHISPER_DATA_DIR")
    if override:
        return Path(override)
    executable = Path(sys.executable).resolve()
    base = executable.parent
    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        base = executable.parents[3]
    elif not getattr(sys, "frozen", False):
        base = Path(__file__).resolve().parents[2]
    portable = base / "Syllentra Data"
    return portable if portable.is_dir() else Path(user_data_dir(APP_DATA_NAME))
