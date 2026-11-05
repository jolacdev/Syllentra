"""Protect native drop normalization and timed export contracts at input boundaries."""

import math
import unittest

from api.api import command_error, dropped_paths
from schemas.batch import InferenceOutput
from service.transcription_service import BusyError
from utils.export_utils import render_output
from utils.transcript_utils import parse_output


class NativeDropTests(unittest.TestCase):
    """Require real native paths for every dropped file or folder."""

    def test_mixed_paths_and_identical_basenames_are_retained(self) -> None:
        """Multi-drop must not collapse distinct recordings or folders into browser basenames."""
        paths = ["/one/Interview.wav", "/two/Interview.wav", "/three/Folder"]
        event = {"dataTransfer": {"files": [{"pywebviewFullPath": path} for path in paths]}}
        self.assertEqual(dropped_paths(event), paths)

    def test_one_missing_native_path_rejects_the_whole_payload(self) -> None:
        """A partial drop must fail visibly instead of importing an incomplete guessed selection."""
        invalid: list[object] = [
            None,
            {},
            {"dataTransfer": {"files": []}},
            {"dataTransfer": {"files": [{"name": "Interview.wav"}]}},
            {"dataTransfer": {"files": [{"pywebviewFullPath": "/one.wav"}, {"name": "two.wav"}]}},
        ]
        for event in invalid:
            with self.subTest(event=event), self.assertRaises(ValueError):
                dropped_paths(event)

    def test_busy_error_is_not_localized_by_message_matching(self) -> None:
        """Admission failures must retain a stable code independently of their technical text."""
        self.assertEqual(command_error(BusyError("any detail"))["code"], "busy")
        self.assertEqual(command_error(ValueError("any detail"))["code"], "invalid_request")


class CaptionTests(unittest.TestCase):
    """Verify timestamp preservation and valid serialized captions for multilingual text."""

    def test_invalid_subtitle_times_are_rejected(self) -> None:
        """Normalized subtitle cues must still reject nonfinite, reversed, and overlapping intervals."""
        for start, end in [(math.nan, 1.0), (0.0, math.inf), (-1.0, 1.0), (1.0, 0.0)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                parse_output(
                    {
                        "text": "word",
                        "duration": 2.0,
                        "language": None,
                        "segments": [{"text": "word", "start": start, "end": end}],
                    }
                )

    def test_hour_rounding_unicode_and_vtt_escaping(self) -> None:
        """Exports must remain valid across hour rollover and preserve original copy text."""
        output: InferenceOutput = {
            "text": "Español <français> & 日本語.",
            "duration": 3601,
            "language": None,
            "segments": [
                {"id": 0, "start": 3599.9996, "end": 3600.5, "text": "Español <français> & 日本語."}
            ],
        }
        parsed = parse_output(output)
        self.assertIn("01:00:00,000 --> 01:00:00,500", render_output(parsed, "srt"))
        vtt = render_output(parsed, "vtt")
        self.assertTrue(vtt.startswith("WEBVTT\n\n"))
        self.assertIn("01:00:00.000 --> 01:00:00.500", vtt)
        self.assertIn("&lt;français&gt; &amp; 日本語", vtt)
        self.assertEqual(render_output(parsed, "txt"), output["text"] + "\n")
