"""Verify offline imports and relocation of the portable model store."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from constants import MODEL_FOLDER
from service.model_storage_service import ModelStorageService
from service.phonon_service import MODEL_PATH, PhononEngine, WorkerRequest


def ignore_phase(_phase: str, _progress: float | None) -> None:
    """Ignore setup progress when checking the published files."""


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
        self.enterContext(patch("service.phonon_service.MODEL_FILES", self.pins))
        network = patch("socket.socket.connect", side_effect=AssertionError("Network must not be used"))
        network.start()
        self.addCleanup(network.stop)
        self.engine = PhononEngine(self.data / "models")
        self.addCleanup(self.engine.close)
        self.storage = ModelStorageService(self.engine, self.data)

    def test_local_import_survives_removal_of_source(self) -> None:
        """An imported model must be a verified, independent portable copy."""
        (self.source / "notes.pdf").write_bytes(b"personal document")
        self.storage.use_local(self.source)
        self.assertTrue(self.engine.is_ready())
        self.assertEqual((self.source / "notes.pdf").read_bytes(), b"personal document")
        self.assertEqual({path.name for path in self.engine.model_path.iterdir()}, set(self.pins))
        self.assertFalse((self.source / "model.fermion").samefile(self.engine.model_path / "model.fermion"))
        self.source.rename(self.root / "offline-source")
        restored = PhononEngine(self.data / "models")
        self.assertTrue(restored.is_ready())

    def test_invalid_import_preserves_active_model(self) -> None:
        """A damaged replacement must not discard a working local reference."""
        self.storage.use_local(self.source)
        bad = self.root / "bad" / MODEL_FOLDER
        bad.mkdir(parents=True)
        with self.assertRaises(ValueError):
            self.storage.use_local(bad)
        self.assertEqual(self.engine.model_path, self.data / "models" / MODEL_PATH)
        self.assertTrue(self.engine.is_ready())

    def test_import_preserves_occupied_target(self) -> None:
        """An incomplete destination may contain files that do not belong to the model."""
        self.engine.model_path.mkdir(parents=True)
        document = self.engine.model_path / "notes.pdf"
        document.write_bytes(b"original")
        with self.assertRaises(FileExistsError):
            self.storage.use_local(self.source)
        self.assertEqual(list(self.engine.model_path.iterdir()), [document])
        self.assertEqual(document.read_bytes(), b"original")

    def test_download_uses_portable_staging_and_ignores_legacy_destination(self) -> None:
        """Downloads may publish only from private staging inside the fixed store."""
        self.data.mkdir()
        legacy = self.data / "model-location.json"
        legacy.write_text('{"storage": "../USB", "model": "../USB/model"}', encoding="utf-8")
        ModelStorageService(self.engine, self.data)

        def download(_request: WorkerRequest, _cancel: Event, _report: object, *, cache: Path) -> None:
            """Stand in for the download worker and check where it writes."""
            self.assertEqual(cache.parent, self.engine.directory)
            staged = cache / MODEL_PATH
            staged.mkdir(parents=True)
            for name in self.pins:
                (staged / name).write_bytes((self.source / name).read_bytes())

        with patch.object(self.engine, "_execute", side_effect=download):
            self.engine.setup(Event(), ignore_phase)
        self.assertTrue(self.engine.is_ready())
        self.assertEqual(set(self.source.parent.iterdir()), {self.source})
        self.assertEqual(legacy.read_text(encoding="utf-8"), '{"storage": "../USB", "model": "../USB/model"}')

    def test_portable_paths_survive_relocation(self) -> None:
        """Moving portable application data must retain model paths relative to that data folder."""
        self.storage.use_local(self.source)
        expected = self.engine.model_path.relative_to(self.data)
        moved = self.root / "Moved Data"
        self.data.rename(moved)
        restored = PhononEngine(moved / "models")
        self.assertEqual(restored.model_path, moved / expected)
        self.assertTrue(restored.is_ready())
        self.assertTrue(self.source.exists())
