import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from constants import APP_NAME
from utils.storage_utils import get_data_directory


class StorageIdentityTests(unittest.TestCase):
    """Protect installed models and existing developer setups across the rebrand."""

    @patch.dict(os.environ, {}, clear=True)
    def test_syllentra_uses_previous_data_identity_by_default(self) -> None:
        """Changing the displayed name must not change the platform storage identity."""
        with patch("utils.storage_utils.user_data_dir", return_value="/existing-data") as directory:
            self.assertEqual(APP_NAME, "Syllentra")
            self.assertEqual(get_data_directory(), Path("/existing-data"))
            directory.assert_called_once_with("PyWhisper Studio")

    @patch.dict(os.environ, {"PYWHISPER_DATA_DIR": "/legacy-override"}, clear=True)
    def test_legacy_override_remains_supported(self) -> None:
        """Existing isolated setups must keep their chosen storage location."""
        self.assertEqual(get_data_directory(), Path("/legacy-override"))

    @patch.dict(
        os.environ,
        {"PYWHISPER_DATA_DIR": "/legacy-override", "SYLLENTRA_DATA_DIR": "/current-override"},
        clear=True,
    )
    def test_syllentra_override_takes_precedence(self) -> None:
        """The current brand's explicit override wins when both names are configured."""
        self.assertEqual(get_data_directory(), Path("/current-override"))


if __name__ == "__main__":
    unittest.main()


class PortableStorageTests(unittest.TestCase):
    """Protect explicit portable storage detection on a frozen executable layout."""

    @patch.dict(os.environ, {}, clear=True)
    def test_sibling_data_folder_enables_portable_mode(self) -> None:
        """A marker folder beside the executable must contain portable application data."""
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            portable = directory / "Syllentra Data"
            portable.mkdir()
            with (
                patch("sys.frozen", True, create=True),
                patch("sys.platform", "win32"),
                patch("sys.executable", str(directory / "Syllentra.exe")),
            ):
                self.assertEqual(get_data_directory(), portable)

    @patch.dict(os.environ, {}, clear=True)
    def test_new_portable_folder_changes_only_subsequent_storage_selection(self) -> None:
        """Creating portable storage must leave the original data intact and require a new selection."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            original = root / "normal-data"
            original.mkdir()
            preferences = original / "preferences.json"
            preferences.write_text('{"theme":"dark"}')
            app = root / "app"
            app.mkdir()
            with (
                patch("sys.frozen", True, create=True),
                patch("sys.platform", "win32"),
                patch("sys.executable", str(app / "Syllentra.exe")),
                patch("utils.storage_utils.user_data_dir", return_value=str(original)),
            ):
                active_directory = get_data_directory()
                portable = app / "Syllentra Data"
                portable.mkdir()
                self.assertEqual(active_directory, original)
                self.assertEqual(get_data_directory(), portable)
                self.assertEqual(list(portable.iterdir()), [])
                self.assertEqual(preferences.read_text(), '{"theme":"dark"}')
