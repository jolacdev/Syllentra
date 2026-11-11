"""Import verified models into the portable installation."""

from pathlib import Path

from schemas.batch import ModelLocation
from service.phonon_service import PhononEngine


class ModelStorageService:
    """Expose the fixed model location and its offline import operation."""

    def __init__(self, engine: PhononEngine, data: Path) -> None:
        """Use the engine's portable model directory."""
        self.engine = engine
        self.data = data

    def location(self) -> ModelLocation:
        """Describe the portable data and model directories."""
        return {"path": str(self.engine.model_path), "dataDirectory": str(self.data)}

    def use_local(self, source: Path) -> None:
        """Import a verified copy from a user-selected folder."""
        self.engine.import_model(source)
