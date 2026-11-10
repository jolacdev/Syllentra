"""Verify queue admission, cancellation, partial outputs, and transport independence."""

import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from schemas.batch import BatchAppState, InferenceOutput, ModelInfo, OutputArtifact
from service.engine import CancelledError, PhaseCallback
from service.transcription_service import TranscriptionService


class FakeBatchEngine:
    """Provide controlled native-operation boundaries without a model or network access."""

    def __init__(self) -> None:
        """Track inference calls and optionally block one named recording until cancellation or release."""
        self.ready = True
        self.calls: list[str] = []
        self.blocked_name = ""
        self.started = Event()
        self.release = Event()

    def get_info(self) -> ModelInfo:
        """Supply model metadata through the same contract as a production engine."""
        return {"name": "Test engine", "languages": ["en"], "sourceUrl": "https://example.test/model"}

    def is_ready(self) -> bool:
        """Return explicitly configured local readiness."""
        return self.ready

    def setup(self, cancel: Event, report: PhaseCallback) -> None:
        """Represent explicit setup without acquiring any external files."""
        if cancel.is_set():
            raise CancelledError
        self.ready = True

    def transcribe(
        self, source: Path, cancel: Event, report: PhaseCallback, *, audio_stream_index: int | None = None
    ) -> InferenceOutput:
        """Return deterministic speech or pause at a cancellable inference boundary."""
        self.calls.append(source.name)
        report("transcribing", None)
        if source.name == self.blocked_name:
            self.started.set()
            while not self.release.wait(0.01):
                if cancel.is_set():
                    raise CancelledError
        if source.name == "bad.wav":
            raise ValueError("Invalid media")
        silent = source.name == "silence.wav"
        return {
            "text": "" if silent else "Recorded speech.",
            "duration": 2.0,
            "language": None,
            "segments": [] if silent else [{"id": 0, "start": 0.0, "end": 1.5, "text": "Recorded speech."}],
        }

    def close(self) -> None:
        """Release a blocked fake operation during test cleanup."""
        self.release.set()


class BatchServiceTests(unittest.TestCase):
    """Exercise actual file commits around a deterministic inference adapter."""

    def setUp(self) -> None:
        """Create isolated source and application storage for every queue scenario."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.sources = self.root / "Sources"
        self.sources.mkdir()
        self.engine = FakeBatchEngine()
        self.service = TranscriptionService(self.engine, self.root / "app")
        self.addCleanup(self.service.close)
        self.settled = Event()
        self.service.subscribe(self._observe)

    def _observe(self, state: BatchAppState) -> None:
        """Signal terminal operations without arbitrary timing assumptions."""
        if (
            not state["scan"]["isRunning"]
            and state["model"]["status"] not in ("preparing", "cancelling")
            and state["batch"]["status"] not in ("running", "stopping")
        ):
            self.settled.set()

    def _import(self, *names: str) -> None:
        """Create readable fixtures and wait for their background discovery."""
        for name in names:
            (self.sources / name).write_bytes(b"media fixture")
        self.settled.clear()
        self.service.import_paths([str(self.sources)])
        self.assertTrue(self.settled.wait(2), "Discovery did not settle")

    def _start(self) -> None:
        """Submit a conflict-free plan and wait for the queue's terminal snapshot."""
        plan = self.service.prepare_batch()
        self.settled.clear()
        self.service.start_batch(plan["id"])
        self.assertTrue(self.settled.wait(3), "Queue did not settle")

    def test_close_stops_transcription_and_cancels_the_queue(self) -> None:
        """A close warning preserves work until confirmation, then cleanup settles the active batch."""
        self._import("a.wav", "b.wav")
        self.engine.blocked_name = "a.wav"
        plan = self.service.prepare_batch()
        self.service.start_batch(plan["id"])
        self.assertTrue(self.engine.started.wait(2))
        self.service.request_close(True)
        self.assertTrue(self.service.is_busy())
        self.assertFalse(self.service._cancel.is_set())
        self.service.request_close(False)
        self.assertTrue(self.service.is_busy())
        self.service.close()
        self.assertFalse(self.service.is_busy())
        self.assertEqual(self.engine.calls, ["a.wav"])
        self.assertEqual(self.service.snapshot()["batch"]["cancelled"], 2)
        self.assertFalse((self.sources / "a.srt").exists())
        self.assertFalse((self.sources / "b.srt").exists())

    def test_exports_all_formats_once_per_file(self) -> None:
        """A serial mixed batch must produce each requested format with one inference pass."""
        self._import("a.wav", "b.mp4")
        self.service.set_exports(
            {"formats": ["srt", "txt", "vtt"], "destination": None, "includeAudioLanguage": False}
        )
        self._start()
        self.assertEqual(self.engine.calls, ["a.wav", "b.mp4"])
        self.assertEqual(self.service.snapshot()["batch"]["completed"], 2)
        batch = self.service.snapshot()["batch"]
        self.assertGreater(batch["elapsedSeconds"], 0)
        self.assertTrue((self.sources / "a.vtt").read_text().startswith("WEBVTT\n\n"))
        self.assertEqual((self.sources / "b.txt").read_text(), "Recorded speech.\n")

    def test_silence_is_successful_without_empty_outputs(self) -> None:
        """No speech must not create empty subtitles or masquerade as a failed recording."""
        self._import("silence.wav")
        self._start()
        self.assertEqual(self.service.snapshot()["batch"]["noSpeech"], 1)
        self.assertFalse((self.sources / "silence.srt").exists())
        self.assertTrue(self.service.workspace()["items"][0]["noSpeech"])

    def test_file_error_does_not_stop_later_files(self) -> None:
        """A bad recording must leave independent queued recordings processable."""
        self._import("bad.wav", "good.wav")
        with patch("service.transcription_service.logger.exception"):
            self._start()
        self.assertEqual(self.service.snapshot()["batch"]["failed"], 1)
        self.assertEqual(self.service.snapshot()["batch"]["completed"], 1)
        self.assertTrue((self.sources / "good.srt").exists())

    def test_unresolved_conflicts_and_stale_plans_are_rejected(self) -> None:
        """Preflight must prevent inference on unresolved outputs or a changed inclusion revision."""
        self._import("a.wav")
        (self.sources / "a.srt").write_text("existing")
        plan = self.service.prepare_batch()
        with self.assertRaisesRegex(ValueError, "Resolve"):
            self.service.start_batch(plan["id"])
        item = self.service.workspace()["items"][0]
        self.service.include([item["id"]], False)
        with self.assertRaisesRegex(ValueError, "selection changed"):
            self.service.start_batch(plan["id"])
        self.assertEqual(self.engine.calls, [])

    def test_all_skipped_outputs_avoid_loading_the_model(self) -> None:
        """An entirely skipped recording requires no inference or model setup."""
        self._import("a.wav")
        self.engine.ready = False
        (self.sources / "a.srt").write_text("existing")
        plan = self.service.prepare_batch()
        output = plan["items"][0]["outputs"][0]
        plan = self.service.resolve_conflicts(plan["id"], [output["id"]], "skip")
        self.settled.clear()
        self.service.start_batch(plan["id"])
        self.assertTrue(self.settled.wait(2))
        self.assertEqual(self.engine.calls, [])
        self.assertEqual(self.service.snapshot()["batch"]["skipped"], 1)

    def test_partial_export_retries_without_inference_or_source(self) -> None:
        """A retained transcript must recover a failed artifact while preserving a successful format."""
        self._import("a.wav")
        self.service.set_exports(
            {"formats": ["srt", "txt"], "destination": None, "includeAudioLanguage": False}
        )
        original = self.service._exports.write

        def fail_subtitle(output: OutputArtifact, result: InferenceOutput) -> OutputArtifact:
            """Simulate a per-format filesystem failure after inference completes."""
            if output["format"] == "srt":
                raise PermissionError("read-only target")
            return original(output, result)

        with patch.object(self.service._exports, "write", side_effect=fail_subtitle):
            self._start()
        self.assertTrue(self.service.has_unexported_results())
        self.assertTrue((self.sources / "a.txt").exists())
        (self.sources / "a.wav").unlink()
        plan = self.service.prepare_batch(failed_only=True)
        self.assertFalse(any(output["action"] == "ask" for output in plan["items"][0]["outputs"]))
        self.settled.clear()
        self.service.start_batch(plan["id"])
        self.assertTrue(self.settled.wait(2))
        self.assertEqual(self.engine.calls, ["a.wav"])
        self.assertTrue((self.sources / "a.srt").exists())
        self.assertFalse(self.service.has_unexported_results())

    def test_late_output_conflict_preserves_other_application_file(self) -> None:
        """A target appearing during inference must produce a retryable export failure."""
        self._import("a.wav")
        self.engine.blocked_name = "a.wav"
        plan = self.service.prepare_batch()
        self.settled.clear()
        self.service.start_batch(plan["id"])
        self.assertTrue(self.engine.started.wait(2))
        (self.sources / "a.srt").write_text("other application")
        self.engine.release.set()
        self.assertTrue(self.settled.wait(2))
        self.assertEqual((self.sources / "a.srt").read_text(), "other application")
        self.assertEqual(self.service.workspace()["items"][0]["errorStage"], "export")

    def test_cancel_current_continues_later_items(self) -> None:
        """Cancelling one identified attempt must leave the remaining queue usable."""
        self._import("a.wav", "b.wav")
        self.engine.blocked_name = "a.wav"
        plan = self.service.prepare_batch()
        self.settled.clear()
        self.service.start_batch(plan["id"])
        self.assertTrue(self.engine.started.wait(2))
        state = self.service.snapshot()
        item_id = state["batch"]["activeItemId"]
        self.assertIsNotNone(item_id)
        self.service.cancel_current(state["batch"]["id"], item_id or "")
        self.assertTrue(self.settled.wait(2))
        self.assertEqual(self.service.snapshot()["batch"]["cancelled"], 1)
        self.assertEqual(self.service.snapshot()["batch"]["completed"], 1)
        self.assertFalse((self.sources / "a.srt").exists())
        self.assertTrue((self.sources / "b.srt").exists())

    def test_stale_item_cancellation_cannot_cancel_its_successor(self) -> None:
        """A delayed cancel from the previous row must not affect the current recording."""
        self._import("a.wav", "b.wav")
        self.engine.blocked_name = "b.wav"
        plan = self.service.prepare_batch()
        self.settled.clear()
        self.service.start_batch(plan["id"])
        self.assertTrue(self.engine.started.wait(2))
        state = self.service.snapshot()
        self.service.cancel_current(state["batch"]["id"], plan["items"][0]["itemId"])
        self.engine.release.set()
        self.assertTrue(self.settled.wait(2))
        self.assertEqual(self.service.snapshot()["batch"]["completed"], 2)
        self.assertEqual(self.service.snapshot()["batch"]["cancelled"], 0)

    def test_stop_settles_pending_items_and_rejects_duplicate_start(self) -> None:
        """Stop must cancel active and pending work while overlapping admission stays rejected."""
        self._import("a.wav", "b.wav", "c.wav")
        self.engine.blocked_name = "a.wav"
        plan = self.service.prepare_batch()
        self.settled.clear()
        self.service.start_batch(plan["id"])
        self.assertTrue(self.engine.started.wait(2))
        with self.assertRaisesRegex(ValueError, "current operation"):
            self.service.start_batch(plan["id"])
        self.service.stop_batch(self.service.snapshot()["batch"]["id"])
        self.assertTrue(self.settled.wait(2))
        self.assertEqual(self.service.snapshot()["batch"]["cancelled"], 3)
        self.assertEqual(self.engine.calls, ["a.wav"])

    def test_setup_is_explicit_and_preserves_sources(self) -> None:
        """Model unavailability must not initiate a download or discard the selection."""
        self._import("a.wav")
        self.engine.ready = False
        plan = self.service.prepare_batch()
        with self.assertRaisesRegex(ValueError, "Prepare Phonon"):
            self.service.start_batch(plan["id"])
        self.settled.clear()
        self.service.setup_model()
        self.assertTrue(self.settled.wait(2))
        self.assertEqual(self.service.snapshot()["model"]["status"], "ready")
        self.assertEqual(len(self.service.workspace()["items"]), 1)
        self.assertEqual(self.engine.calls, [])

    def test_setup_elapsed_time_survives_hydration_and_cancellation(self) -> None:
        """A reloaded frontend must recover measured setup time while cancellation stays responsive."""
        started = Event()
        release = Event()
        self.engine.ready = False

        def controlled_setup(cancel: Event, _report: PhaseCallback) -> None:
            """Hold a simulated preparation operation without downloading or loading native code."""
            started.set()
            release.wait(2)
            if cancel.is_set():
                raise CancelledError

        with (
            patch.object(self.engine, "setup", side_effect=controlled_setup),
            patch("service.transcription_service.monotonic", return_value=100.0) as clock,
        ):
            self.settled.clear()
            self.service.setup_model()
            try:
                self.assertTrue(started.wait(1))
                clock.return_value = 112.0
                self.assertEqual(self.service.snapshot()["model"]["elapsedSeconds"], 12)
                clock.return_value = 125.0
                self.service.cancel_setup()
                model = self.service.snapshot()["model"]
                self.assertEqual(model["status"], "cancelling")
                self.assertEqual(model["elapsedSeconds"], 25)
            finally:
                release.set()
            self.assertTrue(self.settled.wait(1))
            self.assertEqual(self.service.snapshot()["model"]["status"], "missing")
            self.assertEqual(self.service.snapshot()["model"]["elapsedSeconds"], 25)

    def test_source_changes_after_preflight_fail_as_source_errors(self) -> None:
        """An admitted fingerprint must be rechecked immediately before inference."""
        self._import("a.wav")
        plan = self.service.prepare_batch()
        (self.sources / "a.wav").write_bytes(b"changed")
        self.settled.clear()
        with patch("service.transcription_service.logger.exception"):
            self.service.start_batch(plan["id"])
            self.assertTrue(self.settled.wait(2))
        self.assertEqual(self.service.workspace()["items"][0]["errorStage"], "source")
        self.assertEqual(self.engine.calls, [])

    def test_new_batch_restores_defaults_without_deleting_outputs(self) -> None:
        """Starting another batch must clear session references and restore SRT beside-source defaults."""
        self._import("a.wav")
        self.service.set_exports({"formats": ["txt"], "destination": None, "includeAudioLanguage": True})
        self._start()
        self.service.new_batch()
        self.assertEqual(self.service.workspace()["items"], [])
        self.assertEqual(
            self.service.snapshot()["exportSettings"],
            {"formats": ["srt"], "destination": None, "includeAudioLanguage": False},
        )
        self.assertTrue((self.sources / "a.txt").exists())
