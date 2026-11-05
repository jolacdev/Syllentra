import json
import logging
import os
import shutil
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from platformdirs import user_data_dir

from constants import APP_DATA_NAME, MODEL_FOLDER


def _check_writable(directory: Path) -> None:
    """Check actual write access rather than permission bits, which differ across platforms."""
    directory.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(prefix=".syllentra-write-", dir=directory):
        pass


def _initialize_portable(portable: Path, legacy: Path) -> None:
    """Publish initial settings atomically while leaving existing model assets in place."""
    with TemporaryDirectory(prefix=".syllentra-init-", dir=portable.parent) as temporary:
        staging = Path(temporary) / portable.name
        staging.mkdir()
        for name in ("preferences.json", "preferences.legacy.json"):
            source = legacy / name
            if source.is_file():
                shutil.copyfile(source, staging / name)
        config = legacy / "model-location.json"
        value: object = json.loads(config.read_text(encoding="utf-8")) if config.is_file() else {}
        if not isinstance(value, dict):
            raise ValueError("Invalid legacy model location")
        storage, model = value.get("storage"), value.get("model")
        if config.is_file() and not (isinstance(storage, str) and isinstance(model, str)):
            raise ValueError("Invalid legacy model location paths")
        old_storage = legacy / "models"
        old_model = old_storage / "speech" / "FermionResearch__Phonon-2.5" / MODEL_FOLDER
        if isinstance(storage, str) and isinstance(model, str):
            old_storage = (legacy / storage).resolve()
            old_model = (legacy / model).resolve()
        if config.is_file() or old_model.is_dir():
            # Future default downloads belong to portable data; the existing model stays usable in place.
            location = {
                "storage": "models" if old_storage == legacy / "models" else str(old_storage),
                "model": str(old_model),
            }
            (staging / config.name).write_text(json.dumps(location, indent=2), encoding="utf-8")
        staging.rename(portable)


def get_data_directory() -> Path:
    """Prefer automatic portable storage, retaining overrides and a writable system fallback."""
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
    legacy = Path(user_data_dir(APP_DATA_NAME)).resolve()
    try:
        if not portable.exists():
            _initialize_portable(portable, legacy)
        _check_writable(portable)
        return portable
    except (OSError, ValueError):
        logging.getLogger(__name__).warning(
            "Could not initialize portable storage at %s; using %s", portable, legacy, exc_info=True
        )
        _check_writable(legacy)
        return legacy
