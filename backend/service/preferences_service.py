"""Migrate interface preferences without changing installed data or deleting legacy assets."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from schemas.batch import InterfacePreferences
from utils.language_utils import normalize_language

PREFERENCES_VERSION = 2


class PreferencesService:
    """Persist the small interface contract independently of model and media state."""

    def __init__(self, directory: Path) -> None:
        """Keep the original data identity and reserve a one-time migration backup."""
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "preferences.json"
        self.backup = directory / "preferences.legacy.json"

    def read(self) -> tuple[InterfacePreferences, str | None]:
        """Recover valid interface choices from old or new JSON without accepting unchecked values."""
        preferences: InterfacePreferences = {
            "version": 2,
            "theme": "system",
            "interfaceLanguage": "system",
            "preferredAudioLanguage": None,
        }
        if not self.path.exists():
            return preferences, None
        try:
            value: object = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("Invalid preferences")
            theme: object = value.get("theme")
            language: object = value.get("interfaceLanguage")
            audio_language: object = value.get("preferredAudioLanguage")
            if isinstance(audio_language, str):
                preferences["preferredAudioLanguage"] = normalize_language(audio_language)
            if theme == "dark":
                preferences["theme"] = "dark"
            elif theme == "light":
                preferences["theme"] = "light"
            if language == "en":
                preferences["interfaceLanguage"] = "en"
            elif language == "es-ES":
                preferences["interfaceLanguage"] = "es-ES"
            return preferences, None
        except (OSError, ValueError):
            return preferences, "preferences_unreadable"

    def write(self, preferences: InterfacePreferences) -> None:
        """Back up legacy settings once and atomically publish the new interface schema."""
        if self.path.exists() and not self.backup.exists():
            try:
                value: object = json.loads(self.path.read_text(encoding="utf-8"))
            except ValueError:
                value = None
            if not isinstance(value, dict) or value.get("version") != PREFERENCES_VERSION:
                with self.backup.open("xb") as backup:
                    backup.write(self.path.read_bytes())
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(mode="w", dir=self.path.parent, encoding="utf-8", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(preferences, handle, ensure_ascii=False, indent=2)
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
