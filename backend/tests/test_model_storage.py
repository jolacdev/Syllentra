"""Verify offline import, safe backups, and relocatable model references."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from constants import MODEL_FOLDER
from service.model_storage_service import ModelStorageService
from service.phonon_service import PhononEngine


class ModelStorageTests(unittest.TestCase):
    """Exercise model storage using small pinned assets without native loading or downloads."""

    def setUp(self) -> None:
        """Create separate portable application data, external weights, and backup destinations."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.data = self.root / "Syllentra Data"
        self.source = self.root / "USB" / MODEL_FOLDER
        self.source.mkdir(parents=True)
        (self.source / "config.json").write_bytes(b"config")
        (self.source / "model.fermion").write_bytes(b"weights")
        self.pins = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in self.source.iterdir()
        }
        for module in ("service.phonon_service.MODEL_FILES", "service.model_storage_service.MODEL_FILES"):
            patcher = patch(module, self.pins)
            patcher.start()
            self.addCleanup(patcher.stop)
        network = patch("socket.socket.connect", side_effect=AssertionError("Network must not be used"))
        network.start()
        self.addCleanup(network.stop)
        self.engine = PhononEngine(self.data / "models")
        self.addCleanup(self.engine.close)
        self.storage = ModelStorageService(self.engine, self.data)

    def test_local_import_is_a_persisted_reference(self) -> None:
        """First-use offline import must not copy weights into the application's default cache."""
        self.storage.use_local(self.source)
        self.assertTrue(self.engine.is_ready())
        self.assertFalse(self.engine.directory.exists())
        restored = PhononEngine(self.data / "models")
        ModelStorageService(restored, self.data)
        self.assertEqual(restored.model_path, self.source)
        self.assertTrue(restored.is_ready())

    def test_invalid_import_preserves_active_model(self) -> None:
        """A damaged replacement must not discard a working local reference."""
        self.storage.use_local(self.source)
        bad = self.root / "bad" / MODEL_FOLDER
        bad.mkdir(parents=True)
        with self.assertRaises(ValueError):
            self.storage.use_local(bad)
        self.assertEqual(self.engine.model_path, self.source)
        self.assertTrue(self.engine.is_ready())

    def test_backup_is_verified_and_does_not_overwrite(self) -> None:
        """The exported folder must work offline and leave existing backups unchanged."""
        self.storage.use_local(self.source)
        destination = self.root / "Backups"
        destination.mkdir()
        (self.source / "unrelated-secret.txt").write_text("Do not copy")
        self.storage.backup(destination)
        target = destination / MODEL_FOLDER
        self.assertEqual((target / "model.fermion").read_bytes(), b"weights")
        self.assertFalse((target / "unrelated-secret.txt").exists())
        with self.assertRaises(FileExistsError):
            self.storage.backup(destination)
        self.assertEqual(self.engine.model_path, self.source)

    def test_portable_paths_survive_relocation(self) -> None:
        """Moving portable application data must retain model paths relative to that data folder."""
        self.data.mkdir()
        self.storage.choose_storage(self.data)
        expected = self.engine.model_path.relative_to(self.data)
        moved = self.root / "Moved Data"
        self.data.rename(moved)
        restored = PhononEngine(moved / "models")
        ModelStorageService(restored, moved)
        self.assertEqual(restored.model_path, moved / expected)
        self.assertTrue(self.source.exists())
