"""Protect normalized SDK cues and measurable long-audio transcription progress."""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from pathlib import Path

import fermion
import numpy as np
from numpy.typing import NDArray

from service.phonon_service import normalize_result, transcribe_audio
from utils.audio_utils import SAMPLE_RATE
from utils.audio_windows import MAX_WINDOW_SECONDS, audio_windows


@dataclass
class SpeechResult:
    """Represent public SDK output including raw timings unsuitable for direct subtitle validation."""

    text: str = "Hello world."
    audio_seconds: float = 2.0
    decode_seconds: float = 0.0
    truncated: bool = False
    timed: bool = True
    words: list[fermion.TimedText] = field(default_factory=list)
    segments: list[fermion.TimedText] = field(
        default_factory=lambda: [
            {"text": "Hello world.", "start": 0.0, "end": 1.0},
        ]
    )


class SpeechModel:
    """Return normalized cues per window while recording public-API input durations."""

    path = Path("model")
    profile = "five-value-25"

    def __init__(self) -> None:
        """Track window sample counts without loading a native engine."""
        self.samples: list[int] = []

    def transcribe_array_detailed(self, audio: NDArray[np.float32]) -> SpeechResult:
        """Return one local cue while simulating raw same-frame decoder words."""
        self.samples.append(audio.size)
        return SpeechResult(
            audio_seconds=audio.size / SAMPLE_RATE,
            words=[
                {"text": "Hello", "start": 0.0, "end": 0.8},
                {"text": "world.", "start": 0.5, "end": 0.5},
            ],
        )


class PhononProgressTests(unittest.TestCase):
    """Verify caption normalization, source coverage, offsets, and phase progress."""

    def test_raw_overlaps_and_zero_length_words_do_not_discard_valid_subtitles(self) -> None:
        """A valid SDK subtitle result must survive expected decoder word-timing degeneracies."""
        output = normalize_result(
            SpeechModel().transcribe_array_detailed(np.zeros(SAMPLE_RATE * 2, np.float32))
        )
        self.assertEqual(output["text"], "Hello world.")
        self.assertEqual(output["segments"][0]["end"], 1.0)

    def test_genuinely_invalid_subtitles_and_incomplete_text_still_fail(self) -> None:
        """Accepting raw word overlaps must not bypass subtitle or transcript completeness checks."""
        with self.assertRaises(ValueError):
            normalize_result(SpeechResult(segments=[{"text": "Hello world.", "start": 1.0, "end": 0.0}]))
        with self.assertRaises(ValueError):
            normalize_result(SpeechResult(text="Some other words."))
        with self.assertRaises(ValueError):
            normalize_result(SpeechResult(truncated=True))

    def test_long_audio_progress_tracks_completed_samples_and_preserves_offsets(self) -> None:
        """Progress must advance after real window completions and retain absolute source timing."""
        audio = np.ones(SAMPLE_RATE * 80, dtype=np.float32) * 0.1
        model = SpeechModel()
        progress: list[float] = []
        output = transcribe_audio(model, audio, progress.append)
        self.assertEqual(model.samples, [SAMPLE_RATE * 30, SAMPLE_RATE * 30, SAMPLE_RATE * 20])
        self.assertEqual(progress, [0.0, 37.5, 75.0, 100.0])
        self.assertEqual([cue["start"] for cue in output["segments"]], [0.0, 30.0, 60.0])
        self.assertEqual(output["duration"], 80.0)
        self.assertEqual(output["text"], " ".join(["Hello world."] * 3))

    def test_pause_cuts_are_contiguous_and_bounded(self) -> None:
        """Planning must prefer a real pause without skipping or repeating source samples."""
        audio = np.ones(SAMPLE_RATE * 90, dtype=np.float32) * 0.1
        audio[SAMPLE_RATE * 27 : SAMPLE_RATE * 29] = 0
        windows = list(audio_windows(audio))
        self.assertEqual(windows[0], (0, SAMPLE_RATE * 28))
        self.assertEqual(windows[0][0], 0)
        self.assertEqual(windows[-1][1], audio.size)
        self.assertTrue(all(a[1] == b[0] for a, b in zip(windows, windows[1:], strict=False)))
        self.assertTrue(all(end - start <= SAMPLE_RATE * MAX_WINDOW_SECONDS for start, end in windows))

    def test_short_clip_is_submitted_once(self) -> None:
        """Short recordings must retain the existing single public inference call."""
        model = SpeechModel()
        transcribe_audio(model, np.zeros(SAMPLE_RATE * 2, np.float32), lambda _value: None)
        self.assertEqual(model.samples, [SAMPLE_RATE * 2])
