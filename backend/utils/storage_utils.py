import shutil
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from platformdirs import user_data_dir

from constants import APP_DATA_NAME


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
        staging.rename(portable)


def get_data_directory() -> Path:
    """Keep application writes beside the portable executable or app bundle."""
    executable = Path(sys.executable).resolve()
    base = executable.parent
    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        base = executable.parents[3]
    elif not getattr(sys, "frozen", False):
        base = Path(__file__).resolve().parents[2]
    portable = base / "Syllentra Data"
    legacy = Path(user_data_dir(APP_DATA_NAME)).resolve()
    if portable.resolve() != portable:
        raise ValueError(f"Portable data cannot use a linked directory: {portable}")
    if not portable.exists():
        _initialize_portable(portable, legacy)
    _check_writable(portable)
    return portable
