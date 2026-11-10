"""Keep application orchestration independent of inference vendors and model catalogs."""

from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import Protocol

from schemas.batch import InferenceOutput, ModelInfo

PhaseCallback = Callable[[str, float | None], None]


class CancelledError(Exception):
    """Stop one identified operation without conflating cancellation and failure."""


class TranscriptionEngine(Protocol):
    """Describe the small engine lifecycle required by the batch coordinator."""

    def get_info(self) -> ModelInfo:
        """Describe this engine's model and supported spoken languages without loading weights."""
        ...

    def is_ready(self) -> bool:
        """Inspect local model readiness without network activity."""
        ...

    def setup(self, cancel: Event, report: PhaseCallback) -> None:
        """Prepare the engine only after an explicit setup command."""
        ...

    def transcribe(
        self, source: Path, cancel: Event, report: PhaseCallback, *, audio_stream_index: int | None = None
    ) -> InferenceOutput:
        """Return normalized speech while reporting only measurable phases and progress."""
        ...

    def close(self) -> None:
        """Release runtime resources after active work has settled."""
        ...
