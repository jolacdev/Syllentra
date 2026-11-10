"""Decode local containers into temporary, timeline-aligned 16 kHz mono audio."""

import math
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Event
from typing import BinaryIO

import av
import numpy as np
from av.audio.frame import AudioFrame
from av.audio.resampler import AudioResampler

SAMPLE_RATE = 16_000
AudioProgress = Callable[[float | None], None]


class AudioCancelledError(Exception):
    """Signal cancellation between bounded decoder operations."""


@dataclass(frozen=True)
class PreparedAudio:
    """Describe an app-owned float32 file without moving samples through IPC."""

    path: Path
    samples: int
    stream_index: int

    @property
    def duration(self) -> float:
        """Return the normalized source timeline duration in seconds."""
        return self.samples / SAMPLE_RATE


def _check_cancelled(cancel: Event) -> None:
    """Stop decoding before another frame or padding block is written."""
    if cancel.is_set():
        raise AudioCancelledError


def _write_frame(handle: BinaryIO, frame: AudioFrame, samples: int, origin: float, cancel: Event) -> int:
    """Write one resampled frame while preserving gaps and discarding overlapping samples."""
    _check_cancelled(cancel)
    data = np.asarray(frame.to_ndarray(), dtype=np.float32).reshape(-1)
    position = samples
    if frame.pts is not None and frame.time_base is not None:
        seconds = float(frame.pts * frame.time_base) - origin
        if not math.isfinite(seconds):
            raise ValueError("The recording contains invalid audio timestamps.")
        position = round(seconds * SAMPLE_RATE)
    gap = max(0, position - samples)
    silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
    while gap:
        _check_cancelled(cancel)
        count = min(gap, SAMPLE_RATE)
        handle.write(silence[:count].tobytes())
        samples += count
        gap -= count
    overlap = max(0, samples - position)
    remaining = data[overlap:]
    handle.write(remaining.tobytes())
    return samples + int(remaining.size)


@contextmanager
def prepare_audio(
    source: Path, directory: Path, cancel: Event, report: AudioProgress, stream_index: int | None = None
) -> Iterator[PreparedAudio]:
    """Decode the admitted stream, or the container default, while preserving its original timeline."""
    directory.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=directory, suffix=".f32", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with av.open(str(source)) as container:
            streams = list(container.streams.audio)
            if not streams:
                raise ValueError("This recording has no audio stream.")
            if stream_index is None:
                stream = next(
                    (item for item in streams if item.disposition & av.stream.Disposition.default), streams[0]
                )
            else:
                selected = next((item for item in streams if item.index == stream_index), None)
                if selected is None:
                    raise ValueError(
                        "The selected audio track is no longer available. Add the recording again."
                    )
                stream = selected
            resampler = AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
            origin = container.start_time / av.time_base if container.start_time is not None else 0.0
            duration = container.duration / av.time_base if container.duration else None
            samples = 0
            report(0.0 if duration else None)
            with temporary.open("wb") as output:
                for frame in container.decode(stream):
                    _check_cancelled(cancel)
                    for normalized in resampler.resample(frame):
                        samples = _write_frame(output, normalized, samples, origin, cancel)
                    report(min(99.0, samples / SAMPLE_RATE / duration * 100) if duration else None)
                for normalized in resampler.resample(None):
                    samples = _write_frame(output, normalized, samples, origin, cancel)
            _check_cancelled(cancel)
            if not samples:
                raise ValueError("This recording contains no decodable audio.")
            yield PreparedAudio(temporary, samples, stream.index)
    finally:
        temporary.unlink(missing_ok=True)
