"""Manage explicit offline model locations and verified portable directory backups."""

import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from schemas.batch import ModelLocation
from service.phonon_service import MODEL_FILES, MODEL_FOLDER, PhononEngine


class ModelStorageService:
    """Keep model files outside executable bundles and preserve user-selected locations."""

    def __init__(self, engine: PhononEngine, data: Path) -> None:
        """Restore a location without downloading, copying, or loading native inference."""
        self.engine = engine
        self.data = data
        self.config = data / "model-location.json"
        try:
            value: object = json.loads(self.config.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                storage, model = value.get("storage"), value.get("model")
                if isinstance(storage, str) and isinstance(model, str):
                    engine.directory = (data / storage).resolve()
                    engine.model_path = (data / model).resolve()
        except (OSError, ValueError):
            pass

    def location(self) -> ModelLocation:
        """Describe the actual model path and the chosen root for future downloads."""
        return {"path": str(self.engine.model_path), "downloadDirectory": str(self.engine.directory)}

    def _save(self) -> None:
        """Store relocatable paths for assets inside portable data and absolute external references."""
        self.data.mkdir(parents=True, exist_ok=True)
        values = {}
        for key, path in (("storage", self.engine.directory), ("model", self.engine.model_path)):
            values[key] = str(path.relative_to(self.data)) if path.is_relative_to(self.data) else str(path)
        with TemporaryDirectory(dir=self.data) as temporary:
            staging = Path(temporary) / "location.json"
            staging.write_text(json.dumps(values, indent=2), encoding="utf-8")
            staging.replace(self.config)

    def use_local(self, source: Path) -> None:
        """Verify and reference a canonical model folder in place without requiring network access."""
        source = source.resolve()
        if source.name != MODEL_FOLDER:
            raise ValueError(f"Select the model folder named {MODEL_FOLDER} inside your backup.")
        previous = self.engine.model_path
        self.engine.close()
        self.engine.model_path = source
        if not self.engine.is_ready():
            self.engine.model_path = previous
            raise ValueError("This folder does not contain the verified Phonon-2.5 Multilingual assets.")
        try:
            self._save()
        except OSError:
            self.engine.model_path = previous
            raise

    def choose_storage(self, directory: Path) -> None:
        """Select where future downloads live without moving or deleting any existing assets."""
        directory = directory.resolve()
        if not directory.is_dir():
            raise ValueError("Choose an existing model storage folder.")
        self.engine.close()
        previous = self.engine.directory, self.engine.model_path
        self.engine.directory = directory
        self.engine.model_path = directory / "speech" / "FermionResearch__Phonon-2.5" / MODEL_FOLDER
        try:
            self._save()
        except OSError:
            self.engine.directory, self.engine.model_path = previous
            raise

    def backup(self, destination: Path) -> None:
        """Publish a verified model directory without overwriting files already in the destination."""
        if not self.engine.is_ready():
            raise ValueError("Select or download a verified model before creating a backup.")
        destination = destination.resolve()
        target = destination / MODEL_FOLDER
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"A model backup already exists at {target}. Choose another folder.")
        if destination.is_relative_to(self.engine.model_path):
            raise ValueError("Choose a backup destination outside the active model folder.")
        with TemporaryDirectory(prefix="syllentra-backup-", dir=destination) as temporary:
            staging = Path(temporary) / MODEL_FOLDER
            staging.mkdir()
            for name in MODEL_FILES:
                shutil.copyfile(self.engine.model_path / name, staging / name)
            (staging / "README.txt").write_text(
                "Phonon-2.5 Multilingual by Fermion Research, derived from NVIDIA Parakeet TDT 0.6B v3.\n"
                "Model license: CC-BY-4.0. https://huggingface.co/FermionResearch/Phonon-2.5\n"
                "Use this folder through Syllentra Settings > Use local model.\n",
                encoding="utf-8",
            )
            verifier = PhononEngine(destination)
            verifier.model_path = staging
            if not verifier.is_ready():
                raise ValueError("The copied model failed verification. No backup was published.")
            staging.rename(target)
