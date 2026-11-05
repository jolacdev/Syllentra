"""Compose the native desktop only after frozen subprocess startup has been handled."""

import logging
from pathlib import Path

import webview

from api.api import PyWebViewApi
from constants import APP_NAME, ENABLE_BUNDLED_LOGGING, LOGGING_FILENAME
from helpers.logging_helpers import setup_logging
from helpers.webview_helpers import configure_native_window, get_frontend_entrypoint, is_running_bundled
from service.model_storage_service import ModelStorageService
from service.phonon_service import PhononEngine
from service.transcription_service import TranscriptionService
from utils.storage_utils import get_data_directory


def run_application() -> None:
    """Build the session services and native window without leaking UI startup into inference children."""
    bundled = is_running_bundled()
    directory = get_data_directory()
    setup_logging(
        APP_NAME,
        LOGGING_FILENAME,
        not bundled or ENABLE_BUNDLED_LOGGING,
        logging.INFO,
        directory=directory / "logs",
    )
    engine = PhononEngine(directory / "models")
    models = ModelStorageService(engine, directory)
    service = TranscriptionService(engine, directory, models.location())
    api = PyWebViewApi(service, models)
    window = webview.create_window(
        title=APP_NAME,
        url=get_frontend_entrypoint(str(Path(__file__).parent)),
        js_api=api,
        width=1280,
        height=820,
        min_size=(760, 620),
        background_color="#f6f6f2",
    )
    if window is None:
        raise RuntimeError("Could not create the desktop window.")
    window.events.before_show += configure_native_window
    api._attach(window)
    try:
        webview.start(debug=not bundled)
    finally:
        service.close()
