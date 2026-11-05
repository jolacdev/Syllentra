"""Describe the public speech surface verified against fermion-research 0.2.15."""

from pathlib import Path
from typing import Protocol, TypedDict

import numpy as np
from numpy.typing import NDArray

class TimedText(TypedDict):
    """Describe a timed word or normalized speech segment."""

    text: str
    start: float
    end: float

class SpeechResult(Protocol):
    """Expose only the detailed result fields used by the application."""

    text: str
    decode_seconds: float
    audio_seconds: float
    segments: list[TimedText]
    words: list[TimedText]
    timed: bool
    truncated: bool

class SpeechModel(Protocol):
    """Describe a loaded model that accepts normalized local audio."""

    path: Path
    profile: str
    def transcribe_array_detailed(self, audio: NDArray[np.float32]) -> SpeechResult:
        """Transcribe normalized audio using the model's public detailed API."""
        ...

def load_speech(model: str, *, quiet: bool = True) -> SpeechModel:
    """Load a local model or explicitly acquire a named model during setup."""
    ...
