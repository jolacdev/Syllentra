"""Handle frozen multiprocessing before importing the native desktop composition."""

import multiprocessing
import os
import sys

# Windowed Windows builds have no console streams; vendor download progress requires writable handles.
# https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#sys-stdin-sys-stdout-and-sys-stderr-in-noconsole-windowed-applications-windows-only
# These replacement streams must remain open for the process lifetime.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from application import run_application

    run_application()
