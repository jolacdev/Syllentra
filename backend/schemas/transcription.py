from typing import TypedDict


class TranscriptionSegment(TypedDict):
    """Represent one timed text segment independently of the inference library."""

    id: int
    text: str
    start: float
    end: float
