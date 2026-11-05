"""Exercise console-free startup without launching the desktop or downloading a model."""

import subprocess
import sys
import unittest
from pathlib import Path


class StartupTests(unittest.TestCase):
    """Protect dependency progress output in the GUI process and spawned workers."""

    def test_download_progress_without_console(self) -> None:
        """The real Hub progress implementation must work when Windows omits standard streams."""
        entrypoint = Path(__file__).resolve().parents[1] / "main.py"
        code = """
import runpy
import sys
from huggingface_hub.utils import tqdm

original_stdout, original_stderr = sys.stdout, sys.stderr
missing_stdout, missing_stderr = sys.argv[2:]
if missing_stdout == 'yes':
    sys.stdout = None
if missing_stderr == 'yes':
    sys.stderr = None
runpy.run_path(sys.argv[1], run_name='__mp_main__')
assert sys.stdout is not None and sys.stderr is not None
if missing_stdout == 'no':
    assert sys.stdout is original_stdout
if missing_stderr == 'no':
    assert sys.stderr is original_stderr
for _ in tqdm(range(1), disable=False):
    pass
sys.stdout.write('ready')
sys.stdout.flush()
sys.stderr.flush()
"""
        for stdout, stderr in (("yes", "yes"), ("yes", "no"), ("no", "yes"), ("no", "no")):
            with self.subTest(stdout=stdout, stderr=stderr):
                result = subprocess.run(
                    [sys.executable, "-c", code, str(entrypoint), stdout, stderr],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
