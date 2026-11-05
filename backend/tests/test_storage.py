"""Verify automatic portable storage, upgrade preservation, and unwritable-location fallback."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from constants import MODEL_FOLDER
from service.model_storage_service import ModelStorageService
from service.phonon_service import PhononEngine
from utils.storage_utils import _check_writable, get_data_directory


@patch.dict(os.environ, {}, clear=True)
class PortableStorageTests(unittest.TestCase):
    """Select storage without touching real user data or needing privileged filesystem permissions."""

    def setUp(self) -> None:
        """Use isolated application and legacy data roots for every startup scenario."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.app = self.root / "Application"
        self.app.mkdir()
        self.legacy = self.root / "Legacy Data"
        self.portable = self.app / "Syllentra Data"
        for target, value in (
            ("sys.frozen", True),
            ("sys.platform", "win32"),
            ("sys.executable", str(self.app / "Syllentra.exe")),
            ("utils.storage_utils.user_data_dir", lambda _name: str(self.legacy)),
        ):
            self.enterContext(patch(target, value, create=True))

    def test_fresh_launch_creates_portable_data(self) -> None:
        """Windows and Linux folder distributions must need no manual marker folder."""
        for platform in ("win32", "linux"):
            with self.subTest(platform=platform), patch("sys.platform", platform):
                self.assertEqual(get_data_directory(), self.portable)
                self.assertTrue(self.portable.is_dir())
                self.assertEqual(list(self.portable.iterdir()), [])
        self.assertFalse(self.legacy.exists())

    def test_macos_data_is_outside_bundle(self) -> None:
        """A frozen macOS application must create data beside its .app, outside Contents."""
        executable = self.app / "Syllentra.app" / "Contents" / "MacOS" / "Syllentra"
        with patch("sys.platform", "darwin"), patch("sys.executable", str(executable)):
            self.assertEqual(get_data_directory(), self.portable)
            self.assertTrue(self.portable.is_dir())

    def test_source_launch_uses_repository_root(self) -> None:
        """Source startup must use the project root rather than the interpreter's directory."""
        source = self.app / "backend" / "utils" / "storage_utils.py"
        with patch("sys.frozen", False), patch("utils.storage_utils.__file__", str(source)):
            self.assertEqual(get_data_directory(), self.portable)

    def test_existing_settings_and_cached_model_are_preserved(self) -> None:
        """Migration must copy settings once, reference old weights, and default new downloads locally."""
        self.legacy.mkdir()
        preferences = '{"version": 2, "theme": "dark", "interfaceLanguage": "es-ES"}'
        (self.legacy / "preferences.json").write_text(preferences)
        (self.legacy / "preferences.legacy.json").write_text("legacy backup")
        model = self.legacy / "models" / "speech" / "FermionResearch__Phonon-2.5" / MODEL_FOLDER
        model.mkdir(parents=True)
        (model / "weights").write_bytes(b"existing model")
        data = get_data_directory()
        self.assertEqual((data / "preferences.json").read_text(), preferences)
        self.assertEqual((data / "preferences.legacy.json").read_text(), "legacy backup")
        engine = PhononEngine(data / "models")
        storage = ModelStorageService(engine, data)
        self.assertEqual(engine.model_path, model)
        self.assertEqual(engine.directory, data / "models")
        self.assertEqual(storage.location()["dataDirectory"], str(data))
        self.assertFalse((data / "models").exists())
        self.assertEqual((model / "weights").read_bytes(), b"existing model")
        (data / "preferences.json").write_text("new settings")
        self.assertEqual(get_data_directory(), data)
        self.assertEqual((data / "preferences.json").read_text(), "new settings")
        self.assertEqual((self.legacy / "preferences.json").read_text(), preferences)

    def test_custom_and_relative_model_locations_survive_migration(self) -> None:
        """Relative paths must keep their original base and custom download roots must stay selected."""
        self.legacy.mkdir()
        config = {"storage": "../Custom Models", "model": "../External Model"}
        source = self.legacy / "model-location.json"
        source.write_text(json.dumps(config))
        data = get_data_directory()
        engine = PhononEngine(data / "models")
        ModelStorageService(engine, data)
        self.assertEqual(engine.directory, self.root / "Custom Models")
        self.assertEqual(engine.model_path, self.root / "External Model")
        self.assertEqual(json.loads(source.read_text()), config)

    def test_existing_empty_portable_folder_starts_fresh(self) -> None:
        """An explicitly supplied portable folder must never inherit or overwrite system settings."""
        self.portable.mkdir()
        self.legacy.mkdir()
        (self.legacy / "preferences.json").write_text("old settings")
        self.assertEqual(get_data_directory(), self.portable)
        self.assertEqual(list(self.portable.iterdir()), [])

    def test_invalid_model_config_preserves_system_storage(self) -> None:
        """Unreadable migration metadata must not publish a fresh folder that hides existing choices."""
        self.legacy.mkdir()
        config = self.legacy / "model-location.json"
        config.write_text("{invalid")
        with self.assertLogs("utils.storage_utils", level="WARNING"):
            self.assertEqual(get_data_directory(), self.legacy)
        self.assertFalse(self.portable.exists())
        self.assertEqual(config.read_text(), "{invalid")

    def test_unwritable_app_or_existing_data_uses_system_storage(self) -> None:
        """Both first creation and a later write failure must recover to the compatible system root."""
        with (
            patch("utils.storage_utils._initialize_portable", side_effect=PermissionError),
            self.assertLogs("utils.storage_utils", level="WARNING"),
        ):
            self.assertEqual(get_data_directory(), self.legacy)
        self.portable.mkdir()

        def reject_portable(directory: Path) -> None:
            """Model a read-only portable folder without depending on OS privilege settings."""
            if directory == self.portable:
                raise PermissionError("Read-only location")
            _check_writable(directory)

        with (
            patch("utils.storage_utils._check_writable", side_effect=reject_portable),
            self.assertLogs("utils.storage_utils", level="WARNING"),
        ):
            self.assertEqual(get_data_directory(), self.legacy)
        self.assertTrue(self.legacy.is_dir())

    def test_interrupted_migration_does_not_publish_partial_portable_data(self) -> None:
        """A failed settings copy must leave originals intact and allow initialization to retry."""
        self.legacy.mkdir()
        (self.legacy / "preferences.json").write_text("original")
        with (
            patch("utils.storage_utils.shutil.copyfile", side_effect=OSError("Copy failed")),
            self.assertLogs("utils.storage_utils", level="WARNING"),
        ):
            self.assertEqual(get_data_directory(), self.legacy)
        self.assertFalse(self.portable.exists())
        self.assertEqual(list(self.app.iterdir()), [])
        self.assertEqual(get_data_directory(), self.portable)
        self.assertEqual((self.portable / "preferences.json").read_text(), "original")

    def test_overrides_bypass_portable_creation_and_migration(self) -> None:
        """Both environment names remain supported and the current name takes precedence."""
        for overrides, expected in (
            ({"PYWHISPER_DATA_DIR": "legacy-override"}, "legacy-override"),
            ({"PYWHISPER_DATA_DIR": "legacy", "SYLLENTRA_DATA_DIR": "current"}, "current"),
        ):
            with self.subTest(overrides=overrides), patch.dict(os.environ, overrides, clear=True):
                self.assertEqual(get_data_directory(), Path(expected))
                self.assertFalse(self.portable.exists())


if __name__ == "__main__":
    unittest.main()
