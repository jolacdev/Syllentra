"""Plan bounded, pause-aligned inference windows for measurable long-recording progress."""

from collections.abc import Iterator

import numpy as np
from numpy.typing import NDArray

from utils.audio_utils import SAMPLE_RATE

MAX_WINDOW_SECONDS = 35
TARGET_WINDOW_SECONDS = 30
MIN_WINDOW_SECONDS = 25
ENERGY_BLOCK_SAMPLES = SAMPLE_RATE // 20
NOISE_FLOOR = 0.004
RELATIVE_SILENCE = 0.18


def audio_windows(audio: NDArray[np.float32]) -> Iterator[tuple[int, int]]:
    """Cover all samples once and prefer the middle of the longest nearby quiet pause for each cut."""
    total = audio.size
    start = 0
    while total - start > MAX_WINDOW_SECONDS * SAMPLE_RATE:
        low = start + MIN_WINDOW_SECONDS * SAMPLE_RATE
        high = start + MAX_WINDOW_SECONDS * SAMPLE_RATE
        block = ENERGY_BLOCK_SAMPLES
        # Inspect only one bounded window rather than allocating energy arrays for the complete recording.
        samples = audio[start:high].reshape(-1, block)
        energy = np.sqrt(np.mean(np.square(samples), axis=1))
        threshold = max(NOISE_FLOOR, float(energy.max()) * RELATIVE_SILENCE)
        quiet = energy[(low - start) // block :] <= threshold
        cut = start + TARGET_WINDOW_SECONDS * SAMPLE_RATE
        longest = 0
        run = 0
        distance = float("inf")
        for index, is_quiet in enumerate(quiet):
            run = run + 1 if is_quiet else 0
            midpoint = low + (2 * index + 2 - run) * block // 2
            offset = abs(midpoint - (start + TARGET_WINDOW_SECONDS * SAMPLE_RATE))
            if run > longest or (run == longest and run > 0 and offset < distance):
                longest, distance, cut = run, float(offset), midpoint
        yield start, cut
        start = cut
    if start < total:
        yield start, total
