"""Verify worker supervision and session persistence boundaries without model downloads."""

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from threading import Event, Timer
from time import monotonic
from unittest.mock import patch

from schemas.batch import InferenceOutput, InterfacePreferences
from service.engine import CancelledError
from service.phonon_service import PhononEngine, WorkerConnection
from service.preferences_service import PreferencesService
from service.result_service import ResultService

OUTPUT: InferenceOutput = {
    "text": "Local speech.",
    "duration": 2.0,
    "language": None,
    "segments": [{"id": 0, "start": 0.0, "end": 1.0, "text": "Local speech."}],
}


def controlled_worker(connection: WorkerConnection, _cache: str) -> None:
    """Exercise the real spawn protocol with deterministic results, native crashes, and blocked work."""
    while True:
        try:
            value = json.loads(connection.recv_bytes())
        except EOFError:
            return
        source = Path(value["source"])
        if source.name == "crash.wav":
            os._exit(1)
        connection.send_bytes(
            json.dumps({"id": value["id"], "kind": "phase", "phase": "transcribing"}).encode()
        )
        if source.name == "hang.wav":
            Event().wait()
        output = OUTPUT
        if source.name == "track.wav":
            text = f"Track {value['audioStreamIndex']}."
            output = {**OUTPUT, "text": text, "segments": [{"id": 0, "start": 0.0, "end": 1.0, "text": text}]}
        (Path(value["directory"]) / "result.json").write_text(json.dumps(output), encoding="utf-8")
        connection.send_bytes(json.dumps({"id": value["id"], "kind": "complete"}).encode())


def ignore_phase(_phase: str, _progress: float | None) -> None:
    """Discard deterministic worker progress while testing terminal outcomes."""


class WorkerTests(unittest.TestCase):
    """Test process reuse, bounded cancellation, crash recovery, and asset integrity."""

    def setUp(self) -> None:
        """Use isolated cache files and a spawned worker with no network or inference dependency."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.engine = PhononEngine(Path(temporary.name), controlled_worker)
        self.addCleanup(self.engine.close)

    def test_worker_reused_and_reaped_after_cancel(self) -> None:
        """Cancellation must terminate native work promptly and admit a fresh worker afterward."""
        with patch.object(self.engine, "is_ready", return_value=True):
            self.assertEqual(self.engine.transcribe(Path("one.wav"), Event(), ignore_phase), OUTPUT)
            worker = self.engine._process
            self.engine.transcribe(Path("two.wav"), Event(), ignore_phase)
            self.assertIs(self.engine._process, worker)
            cancel = Event()
            timer = Timer(0.3, cancel.set)
            timer.start()
            started = monotonic()
            try:
                with self.assertRaises(CancelledError):
                    self.engine.transcribe(Path("hang.wav"), cancel, ignore_phase)
            finally:
                timer.cancel()
            self.assertLess(monotonic() - started, 2)
            self.assertIsNone(self.engine._process)
            self.assertEqual(self.engine.transcribe(Path("three.wav"), Event(), ignore_phase), OUTPUT)

    def test_native_crash_is_recoverable(self) -> None:
        """A dead child must produce an actionable error and be replaced on the next item."""
        with patch.object(self.engine, "is_ready", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "stopped unexpectedly"):
                self.engine.transcribe(Path("crash.wav"), Event(), ignore_phase)
            self.assertEqual(self.engine.transcribe(Path("retry.wav"), Event(), ignore_phase), OUTPUT)

    def test_selected_stream_survives_spawn_protocol(self) -> None:
        """The stream frozen by preflight must reach the reusable worker through JSON IPC."""
        with patch.object(self.engine, "is_ready", return_value=True):
            output = self.engine.transcribe(Path("track.wav"), Event(), ignore_phase, audio_stream_index=3)
            self.assertEqual(output["text"], "Track 3.")

    def test_readiness_validates_content_and_not_only_filenames(self) -> None:
        """Corrupt or changed model assets must not be advertised as ready after restart."""
        self.engine.model_path.mkdir(parents=True)
        member = self.engine.model_path / "model.fermion"
        member.write_bytes(b"valid")
        with patch("service.phonon_service.MODEL_FILES", {member.name: hashlib.sha256(b"valid").hexdigest()}):
            self.assertTrue(self.engine.is_ready())
            member.write_bytes(b"damaged")
            self.assertFalse(self.engine.is_ready())

    def test_failed_repair_restores_previous_cache(self) -> None:
        """An interrupted explicit repair must preserve the original app-owned assets."""
        self.engine.model_path.mkdir(parents=True)
        member = self.engine.model_path / "model.fermion"
        member.write_bytes(b"damaged")
        with (
            patch.object(self.engine, "_execute", side_effect=CancelledError),
            self.assertRaises(CancelledError),
        ):
            self.engine.setup(Event(), ignore_phase)
        self.assertEqual(member.read_bytes(), b"damaged")


class SessionStorageTests(unittest.TestCase):
    """Protect preference migration and bounded immutable result reads."""

    def test_legacy_and_malformed_preferences_have_one_time_backup(self) -> None:
        """Migrating appearance must preserve the exact legacy file and recover malformed JSON."""
        for original in ('{"theme":"dark","interfaceLanguage":"es-ES","model":"whisper"}', "{bad"):
            with self.subTest(original=original), tempfile.TemporaryDirectory() as directory:
                preferences = PreferencesService(Path(directory))
                preferences.path.write_text(original)
                recovered, notice = preferences.read()
                self.assertEqual(notice, "preferences_unreadable" if original == "{bad" else None)
                expected: InterfacePreferences = {
                    "version": 2,
                    "theme": "light",
                    "interfaceLanguage": "en",
                    "preferredAudioLanguage": None,
                }
                preferences.write(expected)
                self.assertEqual(preferences.backup.read_text(), original)
                preferences.write(recovered)
                self.assertEqual(preferences.backup.read_text(), original)
                self.assertNotIn("model", preferences.path.read_text())

    def test_result_pages_are_bounded_and_unknown_ids_rejected(self) -> None:
        """Large previews must send only one cue page and copy text only with the initial page."""
        service = ResultService()
        self.addCleanup(service.close)
        output: InferenceOutput = {
            **OUTPUT,
            "duration": 500,
            "segments": [
                {"id": index, "start": float(index), "end": index + 0.5, "text": "cue"}
                for index in range(450)
            ],
        }
        result_id = service.put("source", "/recording.wav", output, 3)
        self.assertEqual(len(service.page(result_id)["segments"]), 200)
        self.assertEqual(service.page(result_id)["text"], OUTPUT["text"])
        self.assertEqual(len(service.page(result_id, 400)["segments"]), 50)
        self.assertEqual(service.page(result_id, 200)["text"], "")
        with self.assertRaises(ValueError):
            service.page("../../outside")
        service.clear()
        with self.assertRaises(ValueError):
            service.page(result_id)
