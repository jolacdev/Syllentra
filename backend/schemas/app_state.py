"""Bind the lightweight batch state to pywebview's top-level shared property."""

from typing import Literal, TypedDict

from schemas.batch import BatchAppState

Theme = Literal["system", "light", "dark"]
InterfaceLanguage = Literal["system", "en", "es-ES"]


class BridgeState(TypedDict):
    """Generate the same shared state contract consumed by the desktop and browser preview."""

    app: BatchAppState
