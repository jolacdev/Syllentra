"""Protect native bridge initialization from paths embedded in pywebview's initial script."""

import tempfile
import unittest
from pathlib import Path
from threading import Event, Thread
from unittest.mock import patch

import webview

from api.api import PyWebViewApi
from service.phonon_service import PhononEngine
from service.transcription_service import TranscriptionService


class BridgeLifecycleTests(unittest.TestCase):
    """Keep initial injection empty and hydrate state only through escaped runtime updates."""

    def setUp(self) -> None:
        """Compose real state and window objects without starting a native GUI or downloading a model."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        engine = PhononEngine(directory / "models")
        self.service = TranscriptionService(
            engine,
            directory,
            {
                "path": r"C:\Users\O'Brien\Español\model",
                "dataDirectory": str(directory),
            },
        )
        self.addCleanup(self.service.close)
        self.window = webview.Window("bridge-test", "Bridge test", None)
        self.run_js = self.enterContext(patch.object(self.window, "run_js"))
        self.api = PyWebViewApi(self.service)
        self.api._attach(self.window)

    def test_initial_injection_does_not_embed_windows_paths(self) -> None:
        """Commands hydrate the latest snapshot while initial shared-state injection remains JSON-safe."""
        self.assertEqual(dict(self.window.state), {})
        self.service.notify("Loading O'Brien's files\nC:\\new\\test")
        self.assertEqual(dict(self.window.state), {})
        self.assertEqual(self.api.get_state(), self.service.snapshot())
        self.api._on_loaded()
        self.assertEqual(self.window.state.app, self.service.snapshot())

    def test_close_warning_does_not_block_the_native_gui(self) -> None:
        """Return the native close veto while the warning's JavaScript waits for the GUI thread."""
        self.api._on_loaded()
        publishing = Event()
        release = Event()
        returned = Event()

        def wait_for_gui(_script: str) -> None:
            """Simulate JavaScript queued behind the native close callback."""
            publishing.set()
            release.wait(2)

        def native_close() -> None:
            """Dispatch the actual synchronous pywebview closing event."""
            self.assertTrue(self.window.events.closing.set())
            returned.set()

        with (
            patch.object(self.service, "is_busy", return_value=True),
            patch.object(self.window, "run_js", side_effect=wait_for_gui),
        ):
            native = Thread(target=native_close)
            native.start()
            try:
                self.assertTrue(publishing.wait(1))
                self.assertTrue(returned.wait(1), "Native close blocked on the warning dialog")
                self.assertTrue(self.service.snapshot()["closeRequested"])
                self.assertFalse(self.service._cancel.is_set())
            finally:
                release.set()
                native.join(2)
        self.assertEqual(self.api.keep_open(), {"error": None})
        self.assertFalse(self.service.snapshot()["closeRequested"])

    def test_confirmed_quit_waits_for_cleanup_before_destroying_window(self) -> None:
        """A failed stop must keep the window open so the user can retry safely."""
        with patch.object(self.window, "destroy") as destroy:
            with patch.object(self.service, "close", side_effect=RuntimeError("Still stopping")):
                self.assertIsNotNone(self.api.quit_app()["error"])
                destroy.assert_not_called()
                self.assertFalse(self.api._allow_close)

            def stopped_before_destroy() -> None:
                """Check that native destruction cannot race service cleanup."""
                destroy.assert_not_called()

            with patch.object(self.service, "close", side_effect=stopped_before_destroy) as close:
                self.assertEqual(self.api.quit_app(), {"error": None})
                close.assert_called_once()
                destroy.assert_called_once()
                self.assertTrue(self.api._on_closing())

    def test_idle_close_does_not_prompt(self) -> None:
        """Allow ordinary close when no active work or unsaved outputs need protection."""
        self.assertFalse(self.window.events.closing.set())
        self.assertFalse(self.service.snapshot()["closeRequested"])

    def test_reload_clears_state_and_resumes_escaped_publication(self) -> None:
        """Reloading after path-bearing updates must not reintroduce unsafe initial-state JSON."""
        with patch.object(self.window, "run_js") as run_js:
            self.api._on_loaded()
            self.assertEqual(self.window.state.app, self.service.snapshot())
            self.window.events.before_load.set()
            self.assertEqual(dict(self.window.state), {})
            run_js.reset_mock()
            self.service.notify("Reloading C:\\new\\test\nO'Brien")
            self.assertEqual(dict(self.window.state), {})
            run_js.assert_not_called()
            self.api._on_loaded()
            self.assertEqual(self.window.state.app, self.service.snapshot())
            run_js.assert_called_once()
            self.service.notify("Ready")
            self.assertEqual(self.window.state.app, self.service.snapshot())
            self.assertEqual(run_js.call_count, 2)

    def test_reload_does_not_wait_for_javascript_on_the_gui_thread(self) -> None:
        """A pending native script must not deadlock before_load while it clears initial state."""
        self.api._on_loaded()
        executing = Event()
        release = Event()
        prepared = Event()

        def wait_for_gui(_script: str) -> None:
            """Represent a background publisher waiting for the GUI to execute JavaScript."""
            executing.set()
            release.wait(2)

        def prepare_reload() -> None:
            """Represent the GUI's synchronous before_load callback."""
            self.window.events.before_load.set()
            prepared.set()

        with patch.object(self.window, "run_js", side_effect=wait_for_gui):
            publisher = Thread(target=self.api._publish_state, args=(self.service.snapshot(),))
            publisher.start()
            reloader = Thread(target=prepare_reload)
            try:
                self.assertTrue(executing.wait(1))
                reloader.start()
                self.assertTrue(prepared.wait(1))
                self.assertEqual(dict(self.window.state), {})
            finally:
                release.set()
                publisher.join(2)
                if reloader.ident is not None:
                    reloader.join(2)
