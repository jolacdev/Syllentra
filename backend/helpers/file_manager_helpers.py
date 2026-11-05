"""Open generated artifacts using literal native commands on each supported desktop."""

import os
import subprocess
import sys
from pathlib import Path


def open_generated_file(path: Path, reveal: bool) -> None:
    """Open a validated artifact or reveal its location without invoking a shell."""
    if sys.platform == "win32":
        if reveal:
            subprocess.Popen(["explorer.exe", f"/select,{path}"])
        else:
            os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)] if reveal else ["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent if reveal else path)])
