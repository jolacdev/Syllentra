"""Expose typed native commands while application services own all batch decisions."""

import logging
from collections.abc import Callable
from functools import partial
from pathlib import Path

import webview
from webview.dom import DOMEventHandler
from webview.dom.element import Element

from helpers.file_manager_helpers import open_generated_file
from schemas.app_state import InterfaceLanguage, Theme
from schemas.batch import (
    BatchAppState,
    BatchPlan,
    CommandError,
    CommandReply,
    ConflictAction,
    ExportSettings,
    PlanReply,
    TranscriptPage,
    WorkspaceDelta,
)
from service.model_storage_service import ModelStorageService
from service.transcription_service import BusyError, TranscriptionService
from utils.media_utils import get_media_dialog_file_types

logger = logging.getLogger(__name__)


def command_error(error: Exception) -> CommandError:
    """Translate known command failures into stable codes while preserving technical detail."""
    if isinstance(error, BusyError):
        return {"code": "busy", "details": str(error)}
    if isinstance(error, (ValueError, TypeError)):
        return {"code": "invalid_request", "details": str(error)}
    if isinstance(error, OSError):
        return {"code": "unavailable", "details": str(error)}
    logger.exception("Native command failed")
    return {"code": "unexpected", "details": str(error)}


def dropped_paths(event: object) -> list[str]:
    """Validate native drop payloads without guessing full paths from browser filenames."""
    if not isinstance(event, dict):
        raise ValueError("The native drop payload is unavailable. Use Add files or Add folder.")
    transfer: object = event.get("dataTransfer")
    if not isinstance(transfer, dict):
        raise ValueError("The native drop payload is unavailable. Use Add files or Add folder.")
    files: object = transfer.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("No native file paths were received. Use Add files or Add folder.")
    paths: list[str] = []
    for file in files:
        if not isinstance(file, dict):
            raise ValueError("A dropped path is unavailable. Use Add files or Add folder.")
        path: object = file.get("pywebviewFullPath")
        if not isinstance(path, str) or not path:
            raise ValueError("A dropped path is unavailable. Use Add files or Add folder.")
        paths.append(path)
    return paths


class PyWebViewApi:
    """Keep pywebview, native pickers, and transport error handling outside domain services."""

    def __init__(self, service: TranscriptionService, models: ModelStorageService | None = None) -> None:
        """Inject the session coordinator without loading inference or creating a window."""
        self._service = service
        self._models = models
        self._window: webview.Window | None = None
        self._drop_element: Element | None = None
        self._allow_close = False

    def _attach(self, window: webview.Window) -> None:
        """Publish top-level snapshots and preserve drop/close lifecycle across frontend reloads."""
        self._window = window
        window.events.loaded += self._reset_dropzone
        window.events.closing += self._on_closing
        window.events.closed += self._service.close
        self._service.subscribe(self._publish_state)
        self._publish_state(self._service.snapshot())

    def _publish_state(self, state: BatchAppState) -> None:
        """Replace one top-level property because nested pywebview mutations are not tracked."""
        self._get_window().state.app = state

    def _get_window(self) -> webview.Window:
        """Require the native host only for operations that actually need its UI."""
        if self._window is None:
            raise RuntimeError("The desktop window is not ready.")
        return self._window

    def _command(self, operation: Callable[[], None]) -> CommandReply:
        """Return expected native command failures as data with a stable localization code."""
        try:
            operation()
            return {"error": None}
        except Exception as error:
            return {"error": command_error(error)}

    def _planned(self, operation: Callable[[], BatchPlan]) -> PlanReply:
        """Return a concrete reviewable output plan or an explicit preflight failure."""
        try:
            return {"plan": operation(), "error": None}
        except Exception as error:
            return {"plan": None, "error": command_error(error)}

    def get_state(self) -> BatchAppState:
        """Hydrate frontend state without admitting or restarting work."""
        return self._service.snapshot()

    def get_workspace(self, after_revision: int = -1) -> WorkspaceDelta:
        """Fetch the file collection separately from lightweight progress snapshots."""
        return self._service.workspace_changes(after_revision)

    def _pick_files(self, folder: bool) -> None:
        """Normalize native file or recursive-folder selection through the shared discovery service."""
        window = self._get_window()
        result = (
            window.create_file_dialog(webview.FileDialog.FOLDER)
            if folder
            else window.create_file_dialog(
                webview.FileDialog.OPEN, allow_multiple=True, file_types=get_media_dialog_file_types()
            )
        )
        if result:
            self._service.import_paths([str(value) for value in result])

    def add_files(self) -> CommandReply:
        """Add one or multiple recordings using the native file picker."""
        return self._command(partial(self._pick_files, False))

    def add_folder(self) -> CommandReply:
        """Add a source folder recursively using the native folder picker."""
        return self._command(partial(self._pick_files, True))

    def cancel_import(self) -> CommandReply:
        """Stop recursive discovery while retaining already discovered files."""
        return self._command(self._service.cancel_import)

    def set_inclusion(self, item_ids: list[str], included: bool) -> CommandReply:
        """Apply file, folder, or extension selections to the same backend-owned leaves."""
        return self._command(partial(self._service.include, item_ids, included))

    def set_exports(self, settings: ExportSettings) -> CommandReply:
        """Set batch-scoped format choices and a validated destination mode."""
        return self._command(partial(self._service.set_exports, settings))

    def _pick_destination(self) -> None:
        """Keep the current export configuration intact when a native folder dialog is cancelled."""
        result = self._get_window().create_file_dialog(webview.FileDialog.FOLDER)
        if result:
            settings = self._service.snapshot()["exportSettings"]
            self._service.set_exports({**settings, "destination": str(Path(str(result[0])).resolve())})

    def choose_destination(self) -> CommandReply:
        """Choose one custom export destination without requesting a Save dialog per output."""
        return self._command(self._pick_destination)

    def prepare_batch(self, failed_only: bool = False) -> PlanReply:
        """Detect filesystem and intra-batch output conflicts before inference begins."""
        return self._planned(partial(self._service.prepare_batch, failed_only))

    def resolve_conflicts(self, plan_id: str, artifact_ids: list[str], action: ConflictAction) -> PlanReply:
        """Apply explicit skip, overwrite, or shared-stem rename decisions to known artifacts."""
        return self._planned(partial(self._service.resolve_conflicts, plan_id, artifact_ids, action))

    def start_batch(self, plan_id: str) -> CommandReply:
        """Admit an already reviewed immutable plan exactly once."""
        return self._command(partial(self._service.start_batch, plan_id))

    def cancel_current(self, batch_id: str, item_id: str) -> CommandReply:
        """Cancel the identified active item without affecting its successor."""
        return self._command(partial(self._service.cancel_current, batch_id, item_id))

    def stop_batch(self, batch_id: str) -> CommandReply:
        """Cancel active and queued work while retaining every committed artifact."""
        return self._command(partial(self._service.stop_batch, batch_id))

    def _model_files(self, action: str) -> None:
        """Resolve native folder selections and serialize model changes with queue admission."""
        models = self._models
        if models is None:
            raise ValueError("Model storage is unavailable in this host.")
        selected = self._get_window().create_file_dialog(webview.FileDialog.FOLDER)
        if not selected:
            return
        path = Path(str(selected[0]))
        operation = {"local": models.use_local, "storage": models.choose_storage, "backup": models.backup}[
            action
        ]
        self._service.manage_model(partial(operation, path), models.location)

    def use_local_model(self) -> CommandReply:
        """Select a verified local Phonon folder for completely offline first use."""
        return self._command(partial(self._model_files, "local"))

    def choose_model_storage(self) -> CommandReply:
        """Choose the directory used for future model downloads without deleting existing copies."""
        return self._command(partial(self._model_files, "storage"))

    def backup_model(self) -> CommandReply:
        """Export a verified model folder to a selected destination for offline machines."""
        return self._command(partial(self._model_files, "backup"))

    def setup_model(self) -> CommandReply:
        """Explicitly acquire and prepare Phonon-2.5 Multilingual."""
        return self._command(self._service.setup_model)

    def cancel_setup(self) -> CommandReply:
        """Cancel explicit model preparation at a supervised process boundary."""
        return self._command(self._service.cancel_setup)

    def get_transcript(self, item_id: str, offset: int = 0) -> TranscriptPage:
        """Read one bounded page of a completed, immutable session transcript."""
        return self._service.transcript(item_id, offset)

    def _open_artifact(self, artifact_id: str, reveal: bool) -> None:
        """Resolve backend-owned generated paths before invoking the operating system."""
        open_generated_file(self._service.artifact_path(artifact_id), reveal)

    def open_artifact(self, artifact_id: str, reveal: bool = False) -> CommandReply:
        """Open a generated file or reveal its location in the platform file manager."""
        return self._command(partial(self._open_artifact, artifact_id, reveal))

    def set_appearance(self, theme: Theme, language: InterfaceLanguage) -> CommandReply:
        """Persist interface language and appearance independently of spoken language."""
        return self._command(partial(self._service.set_appearance, theme, language))

    def new_batch(self, discard_unexported: bool = False) -> CommandReply:
        """Start a clean session selection with explicit protection for unsaved results."""
        return self._command(partial(self._service.new_batch, discard_unexported))

    def _on_closing(self) -> bool:
        """Defer native close to an in-app decision when work or unexported previews remain."""
        if self._allow_close:
            return True
        if self._service.is_busy() or self._service.has_unexported_results():
            self._service.request_close(True)
            return False
        return True

    def _quit(self) -> None:
        """Settle workers and session files before allowing the confirmed native close."""
        self._service.close()
        self._allow_close = True
        self._get_window().destroy()

    def quit_app(self) -> CommandReply:
        """Stop and quit after the user confirms the pending-work/session warning."""
        return self._command(self._quit)

    def keep_open(self) -> CommandReply:
        """Dismiss a native close request and keep the current batch processing."""
        return self._command(partial(self._service.request_close, False))

    def _reset_dropzone(self) -> None:
        """Discard DOM element references when the webview reloads its page."""
        self._drop_element = None

    def bind_dropzone(self) -> bool:
        """Bind the stable workspace drop region while keeping native pickers available on failure."""
        try:
            if self._drop_element is not None:
                self._drop_element.off("drop", self._on_drop)
            self._drop_element = self._get_window().dom.get_element("#file-dropzone")
            if self._drop_element is None:
                return False
            self._drop_element.on(
                "drop", DOMEventHandler(self._on_drop, prevent_default=True, stop_propagation=True)
            )
            return True
        except Exception:
            logger.exception("Native drop binding failed")
            return False

    def _on_drop(self, event: object) -> None:
        """Import every validated native file/folder path through the shared scanner."""
        try:
            self._service.import_paths(dropped_paths(event))
        except (ValueError, OSError) as error:
            self._service.notify(str(error))
