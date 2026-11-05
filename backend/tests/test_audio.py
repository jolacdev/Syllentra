"""Exercise actual media decoding without a model, network, or external executable."""

import tempfile
import unittest
import wave
from pathlib import Path
from threading import Event

import numpy as np

from utils.audio_utils import SAMPLE_RATE, AudioCancelledError, prepare_audio


class AudioTests(unittest.TestCase):
    """Verify resampling, cancellation, and temporary audio ownership."""

    def setUp(self) -> None:
        """Create an isolated stereo recording at a non-model sample rate."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "Grabación.wav"
        signal = (np.sin(np.arange(8_000) * 0.1) * 8_000).astype(np.int16)
        with wave.open(str(self.source), "wb") as recording:
            recording.setnchannels(2)
            recording.setsampwidth(2)
            recording.setframerate(8_000)
            recording.writeframes(np.column_stack((signal, signal)).tobytes())

    def test_resamples_stereo_and_removes_temporary_audio(self) -> None:
        """Actual decoded samples must be mono float32 at the model rate."""
        progress: list[float | None] = []
        with prepare_audio(self.source, self.root / "work", Event(), progress.append) as audio:
            self.assertEqual(audio.samples, SAMPLE_RATE)
            self.assertEqual(audio.duration, 1.0)
            self.assertEqual(audio.path.stat().st_size, SAMPLE_RATE * 4)
            data = np.fromfile(audio.path, dtype=np.float32)
            self.assertGreater(float(np.abs(data).max()), 0.1)
            path = audio.path
        self.assertFalse(path.exists())
        self.assertTrue(progress)
        self.assertTrue(self.source.exists())

    def test_cancelled_decode_cleans_up(self) -> None:
        """Cancellation must not retain normalized audio or change source media."""
        cancel = Event()
        cancel.set()
        with (
            self.assertRaises(AudioCancelledError),
            prepare_audio(self.source, self.root / "work", cancel, lambda _value: None),
        ):
            self.fail("Cancelled audio must not be yielded")
        self.assertEqual(list((self.root / "work").iterdir()), [])

    def test_invalid_container_cleans_up(self) -> None:
        """A supported extension must not hide a corrupt container error."""
        self.source.write_bytes(b"invalid wav")
        with (
            self.assertRaises(ValueError),
            prepare_audio(self.source, self.root / "work", Event(), lambda _value: None),
        ):
            self.fail("Invalid audio must not be yielded")
        self.assertEqual(list((self.root / "work").iterdir()), [])
