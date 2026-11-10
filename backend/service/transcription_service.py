"""Coordinate session-local batch work while keeping native transport and inference separate."""

import logging
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from threading import Event, RLock, Thread
from time import monotonic
from typing import Literal
from uuid import uuid4

from schemas.batch import (
    BatchAppState,
    BatchPlan,
    BatchState,
    ConflictAction,
    ExportSettings,
    InterfacePreferences,
    ItemPlan,
    MediaItem,
    ModelLocation,
    OutputArtifact,
    ScanState,
    TranscriptPage,
    Workspace,
    WorkspaceDelta,
)
from service.engine import CancelledError, TranscriptionEngine
from service.export_service import ExportService
from service.file_selection_service import FileSelectionService
from service.preferences_service import PreferencesService
from service.result_service import ResultService
from utils.language_utils import normalize_language

logger = logging.getLogger(__name__)
REPORT_INTERVAL = 0.25


class BusyError(ValueError):
    """Identify temporary admission failures independently of invalid input."""


class SourceError(ValueError):
    """Identify source changes separately from inference or model failures."""


def empty_batch() -> BatchState:
    """Create an idle queue whose counters do not imply successful processing."""
    return {
        "id": "",
        "status": "idle",
        "total": 0,
        "completed": 0,
        "failed": 0,
        "skipped": 0,
        "cancelled": 0,
        "noSpeech": 0,
        "activeItemId": None,
        "phase": "",
        "progress": None,
        "elapsedSeconds": 0.0,
    }


def empty_scan() -> ScanState:
    """Create an inactive import without losing the distinction between complete and cancelled discovery."""
    return {
        "isRunning": False,
        "isCancelled": False,
        "discovered": 0,
        "ignored": 0,
        "duplicates": 0,
        "currentPath": "",
    }


def default_exports() -> ExportSettings:
    """Start each batch with plain SRT filenames beside their sources."""
    return {"formats": ["srt"], "destination": None, "includeAudioLanguage": False}


class TranscriptionService:
    """Own selection, admission, preferences, queue transitions, and session result references."""

    def __init__(
        self, engine: TranscriptionEngine, directory: Path, location: ModelLocation | None = None
    ) -> None:
        """Compose concrete services without loading weights or reading source recordings."""
        self.engine = engine
        self._lock = RLock()
        self._exports = ExportService()
        self._results = ResultService()
        self._preferences = PreferencesService(directory)
        preferences, notice = self._preferences.read()
        self._files = FileSelectionService(preferences["preferredAudioLanguage"])
        self._publish_callback: Callable[[BatchAppState], None] | None = None
        self._operation: Literal["scan", "planning", "setup", "batch"] | None = None
        self._thread: Thread | None = None
        self._cancel = Event()
        self._stop = Event()
        self._scan_cancel = Event()
        self._plan: BatchPlan | None = None
        self._started = 0.0
        self._setup_started = 0.0
        self._last_scan_report = 0.0
        self._state: BatchAppState = {
            "revision": 0,
            "collectionRevision": 0,
            "modelInfo": engine.get_info(),
            "modelLocation": location
            or {"path": "", "downloadDirectory": "", "dataDirectory": str(directory)},
            "preferences": preferences,
            "exportSettings": default_exports(),
            "scan": empty_scan(),
            "model": {
                "status": "ready" if engine.is_ready() else "missing",
                "error": None,
                "elapsedSeconds": 0.0,
            },
            "batch": empty_batch(),
            "notice": notice,
            "closeRequested": False,
        }

    def subscribe(self, callback: Callable[[BatchAppState], None]) -> None:
        """Attach a transport publisher without importing native UI libraries."""
        with self._lock:
            self._publish_callback = callback

    def snapshot(self) -> BatchAppState:
        """Read a consistent lightweight state revision without copying the file collection."""
        with self._lock:
            state = deepcopy(self._state)
            if state["model"]["status"] in ("preparing", "cancelling"):
                state["model"]["elapsedSeconds"] = monotonic() - self._setup_started
            return state

    def workspace(self) -> Workspace:
        """Read collection metadata only when requested by its revision."""
        return self._files.snapshot()

    def workspace_changes(self, after_revision: int) -> WorkspaceDelta:
        """Fetch changed rows instead of serializing a large tree for each queue transition."""
        return self._files.changes(after_revision)

    def _publish(self) -> None:
        """Copy state under the lock and deliver it outside the lock without failing domain work."""
        with self._lock:
            self._state["revision"] += 1
            self._state["collectionRevision"] = self._files.revision
            snapshot = self.snapshot()
            callback = self._publish_callback
        if callback is not None:
            try:
                callback(snapshot)
            except Exception:
                logger.exception("Bridge state publication failed")

    def _require_idle(self) -> None:
        """Serialize changes against scans, preflight, setup, and active queue admission."""
        if self._operation is not None:
            raise BusyError("Wait for the current operation to finish or cancel it first.")

    def notify(self, message: str | None) -> None:
        """Publish technical native-operation details separately from localized UI labels."""
        with self._lock:
            self._state["notice"] = message
        self._publish()

    def set_appearance(
        self, theme: Literal["system", "light", "dark"], language: Literal["system", "en", "es-ES"]
    ) -> None:
        """Persist validated interface choices without changing the current recording workflow."""
        if theme not in ("system", "light", "dark") or language not in ("system", "en", "es-ES"):
            raise ValueError("Choose a supported interface language and appearance.")
        with self._lock:
            preferences: InterfacePreferences = {
                **self._state["preferences"],
                "theme": theme,
                "interfaceLanguage": language,
            }
            self._preferences.write(preferences)
            self._state["preferences"] = preferences
        self._publish()

    def set_audio_language(self, language: str | None) -> None:
        """Remember an optional multi-track preference and invalidate stale stream/output plans."""
        normalized = normalize_language(language) if isinstance(language, str) else None
        if language is not None and normalized not in self.engine.get_info()["languages"]:
            raise ValueError("Choose a supported preferred audio language or use the file default.")
        with self._lock:
            self._require_idle()
            preferences: InterfacePreferences = {
                **self._state["preferences"],
                "preferredAudioLanguage": normalized,
            }
            self._preferences.write(preferences)
            self._state["preferences"] = preferences
            self._files.set_audio_language(normalized)
            self._plan = None
        self._publish()

    def select_audio_track(self, item_id: str, stream_index: int | None) -> None:
        """Apply a known file's override without permitting a frontend-supplied media path."""
        with self._lock:
            self._require_idle()
            self._files.select_audio_track(item_id, stream_index)
            self._plan = None
        self._publish()

    def import_paths(self, paths: list[str]) -> None:
        """Admit one cancellable background import from native pickers or full-path drops."""
        if not paths:
            return
        with self._lock:
            self._require_idle()
            self._operation = "scan"
            self._scan_cancel.clear()
            self._state["scan"] = {**empty_scan(), "isRunning": True}
            self._state["notice"] = None
            self._last_scan_report = 0.0
            self._plan = None
            thread = Thread(target=self._scan, args=(paths,), daemon=True)
            self._thread = thread
        self._publish()
        thread.start()

    def _scan_report(self, path: str, added: int, ignored: int, duplicates: int) -> None:
        """Coalesce discovery updates while retaining the latest actual counts."""
        with self._lock:
            self._state["scan"].update(
                {"currentPath": path, "discovered": added, "ignored": ignored, "duplicates": duplicates}
            )
        now = monotonic()
        if now - self._last_scan_report >= REPORT_INTERVAL:
            self._last_scan_report = now
            self._publish()

    def _scan(self, paths: list[str]) -> None:
        """Keep partial imports available after cancellation and surface unexpected discovery failures."""
        try:
            self._files.scan(paths, self._scan_cancel, self._scan_report)
        except Exception as error:
            logger.exception("Source discovery failed")
            with self._lock:
                self._state["notice"] = str(error)
        finally:
            with self._lock:
                self._state["scan"]["isRunning"] = False
                self._state["scan"]["isCancelled"] = self._scan_cancel.is_set()
                self._operation = None
            self._publish()

    def cancel_import(self) -> None:
        """Stop discovering more entries while retaining already imported files and choices."""
        with self._lock:
            if self._operation == "scan":
                self._scan_cancel.set()

    def include(self, item_ids: list[str], included: bool) -> None:
        """Apply leaf, folder, or extension bulk inclusion through the same canonical operation."""
        with self._lock:
            self._require_idle()
            self._files.include(item_ids, included)
            self._plan = None
        self._publish()

    def set_exports(self, settings: ExportSettings) -> None:
        """Validate batch-scoped formats and destination before invalidating the old output plan."""
        if any(format not in ("srt", "txt", "vtt") for format in settings["formats"]):
            raise ValueError("Choose SRT, TXT, or VTT output formats.")
        if len(set(settings["formats"])) != len(settings["formats"]):
            raise ValueError("Choose each output format once.")
        include_language = settings.get("includeAudioLanguage", False)
        if not isinstance(include_language, bool):
            raise ValueError("Choose whether to include audio language in subtitle filenames.")
        destination = settings["destination"]
        if destination is not None and not Path(destination).is_dir():
            raise ValueError("Choose an existing destination folder.")
        with self._lock:
            self._require_idle()
            self._state["exportSettings"] = {**deepcopy(settings), "includeAudioLanguage": include_language}
            self._plan = None
        self._publish()

    def prepare_batch(self, failed_only: bool = False) -> BatchPlan:
        """Freeze selected sources and every output path without starting inference or writing outputs."""
        with self._lock:
            self._require_idle()
            self._operation = "planning"
            if failed_only:
                workspace = self._files.snapshot()
                selected = [
                    item["id"] for item in workspace["items"] if item["status"] in ("failed", "cancelled")
                ]
                self._files.include([item["id"] for item in workspace["items"]], False)
                self._files.include(selected, True)
            workspace = self._files.snapshot()
            settings = deepcopy(self._state["exportSettings"])
        try:
            plan = self._exports.prepare(workspace, settings)
            with self._lock:
                self._plan = plan
            return deepcopy(plan)
        finally:
            with self._lock:
                self._operation = None
            self._publish()

    def resolve_conflicts(self, plan_id: str, artifact_ids: list[str], action: ConflictAction) -> BatchPlan:
        """Resolve reviewed artifacts without allowing the frontend to substitute destination paths."""
        with self._lock:
            self._require_idle()
            if (
                self._plan is None
                or self._plan["id"] != plan_id
                or self._plan["revision"] != self._files.revision
            ):
                raise ValueError("The file selection changed. Prepare the batch again.")
            self._operation = "planning"
            plan = deepcopy(self._plan)
        try:
            resolved = self._exports.resolve(plan, artifact_ids, action)
            with self._lock:
                self._plan = resolved
            return deepcopy(resolved)
        finally:
            with self._lock:
                self._operation = None

    def start_batch(self, plan_id: str) -> None:
        """Atomically reserve a resolved plan before launching the single queue worker."""
        with self._lock:
            self._require_idle()
            if (
                self._plan is None
                or self._plan["id"] != plan_id
                or self._plan["revision"] != self._files.revision
            ):
                raise ValueError("The file selection changed. Prepare the batch again.")
            plan = deepcopy(self._plan)
            if any(output["action"] == "ask" for item in plan["items"] for output in item["outputs"]):
                raise ValueError("Resolve existing outputs before starting the batch.")
            inference_needed = any(
                item["resultId"] is None and any(output["action"] != "skip" for output in item["outputs"])
                for item in plan["items"]
            )
            if inference_needed and not self.engine.is_ready():
                raise ValueError("Prepare Phonon-2.5 before transcribing recordings.")
            self._operation = "batch"
            self._stop.clear()
            self._cancel.clear()
            self._started = monotonic()
            batch_id = uuid4().hex
            self._state["batch"] = {
                **empty_batch(),
                "id": batch_id,
                "status": "running",
                "total": len(plan["items"]),
            }
            for planned in plan["items"]:
                item = self._files.get(planned["itemId"])
                item.update(
                    {"status": "queued", "outputs": planned["outputs"], "error": None, "errorStage": None}
                )
                self._files.replace(item)
            self._plan = None
            thread = Thread(target=self._run, args=(plan,), daemon=True)
            self._thread = thread
        self._publish()
        thread.start()

    def _phase(self, phase: str, progress: float | None) -> None:
        """Publish actual phases and update collection metadata only on item-state transitions."""
        with self._lock:
            if self._cancel.is_set():
                return
            batch = self._state["batch"]
            batch.update(
                {"phase": phase, "progress": progress, "elapsedSeconds": monotonic() - self._started}
            )
            item_id = batch["activeItemId"]
            if item_id is not None:
                item = self._files.get(item_id)
                status = "transcribing" if phase == "transcribing" else "preparing"
                if item["status"] != status:
                    item["status"] = "transcribing" if phase == "transcribing" else "preparing"
                    self._files.replace(item)
        self._publish()

    def _export(self, item: MediaItem, result_id: str) -> None:
        """Commit artifacts independently and retain each success if another format fails."""
        result = self._results.get(result_id)
        item["status"] = "exporting"
        self._files.replace(item)
        with self._lock:
            self._state["batch"].update({"phase": "exporting", "progress": None})
        self._publish()
        outputs: list[OutputArtifact] = []
        for output in item["outputs"]:
            if self._cancel.is_set():
                item["errorStage"] = "export"
                raise CancelledError
            try:
                outputs.append(self._exports.write(output, result["output"]))
            except (OSError, ValueError) as error:
                outputs.append({**output, "status": "failed", "error": str(error)})
            item["outputs"] = [*outputs, *item["outputs"][len(outputs) :]]
            self._files.replace(item)
        if any(output["status"] == "failed" for output in outputs):
            item.update(
                {
                    "status": "failed",
                    "errorStage": "export",
                    "error": "One or more outputs could not be saved.",
                }
            )
        else:
            item["status"] = "completed"

    def _infer(self, item: MediaItem, planned: ItemPlan) -> str:
        """Revalidate the admitted source and retain normalized speech before exporting."""
        source = Path(planned["sourcePath"])
        try:
            info = source.stat()
        except OSError as error:
            raise SourceError("The recording was moved, deleted, or is no longer readable.") from error
        if info.st_size != planned["size"] or str(info.st_mtime_ns) != planned["modifiedNs"]:
            raise SourceError("The recording changed after review. Add it again before processing.")
        item["resultId"] = None
        self._phase("preparing", None)
        started = monotonic()
        output = self.engine.transcribe(
            source, self._cancel, self._phase, audio_stream_index=planned["audioStreamIndex"]
        )
        if self._cancel.is_set():
            raise CancelledError
        result_id = self._results.put(item["id"], item["path"], output, monotonic() - started)
        item["resultId"] = result_id
        item["noSpeech"] = not output["text"]
        return result_id

    def _count_outcome(self, item: MediaItem) -> None:
        """Record one terminal outcome without repeatedly scanning the entire queue."""
        self._files.replace(item)
        with self._lock:
            batch = self._state["batch"]
            if item["status"] == "completed":
                batch["completed"] += 1
                batch["noSpeech"] += int(item["noSpeech"])
            elif item["status"] == "failed":
                batch["failed"] += 1
            elif item["status"] == "skipped":
                batch["skipped"] += 1
            else:
                batch["cancelled"] += 1
        self._publish()

    def _process(self, planned: ItemPlan) -> bool:
        """Process one source or reuse its failed-export result and report fatal model failure."""
        item = self._files.get(planned["itemId"])
        with self._lock:
            self._cancel.clear()
            self._state["batch"]["activeItemId"] = item["id"]
        fatal = False
        try:
            if self._stop.is_set():
                raise CancelledError
            if all(output["action"] == "skip" for output in item["outputs"]):
                item["status"] = (
                    "completed"
                    if any(output["status"] == "written" for output in item["outputs"])
                    else "skipped"
                )
                item["outputs"] = [
                    output if output["status"] == "written" else {**output, "status": "skipped"}
                    for output in item["outputs"]
                ]
            else:
                result_id = planned["resultId"] or self._infer(item, planned)
                if self._cancel.is_set():
                    raise CancelledError
                if item["noSpeech"]:
                    item["status"] = "completed"
                    item["outputs"] = [{**output, "status": "not_needed"} for output in item["outputs"]]
                else:
                    self._export(item, result_id)
        except CancelledError:
            item["status"] = "cancelled"
        except Exception as error:
            logger.exception("Batch item %s failed", item["id"])
            fatal = self.snapshot()["batch"]["phase"] == "loading"
            stage: Literal["source", "model", "inference"] = (
                "model" if fatal else "source" if isinstance(error, SourceError) else "inference"
            )
            item.update({"status": "failed", "error": str(error), "errorStage": stage})
            if fatal:
                with self._lock:
                    self._state["model"] = {"status": "failed", "error": str(error), "elapsedSeconds": 0.0}
        self._count_outcome(item)
        return fatal

    def _run(self, plan: BatchPlan) -> None:
        """Run the frozen queue serially and settle every remaining item after stop or fatal setup failure."""
        fatal = False
        try:
            for planned in plan["items"]:
                if self._stop.is_set() or fatal:
                    item = self._files.get(planned["itemId"])
                    item["status"] = "cancelled"
                    self._files.replace(item)
                    with self._lock:
                        self._state["batch"]["cancelled"] += 1
                else:
                    fatal = self._process(planned)
        finally:
            with self._lock:
                self._state["batch"].update(
                    {
                        "status": "failed" if fatal else "cancelled" if self._stop.is_set() else "completed",
                        "activeItemId": None,
                        "phase": "",
                        "progress": None,
                        "elapsedSeconds": monotonic() - self._started,
                    }
                )
                self._operation = None
            self._publish()

    def cancel_current(self, batch_id: str, item_id: str) -> None:
        """Cancel only the current attempt of the identified batch without affecting a successor batch."""
        with self._lock:
            if self._operation != "batch" or self._state["batch"]["id"] != batch_id:
                return
            if self._state["batch"]["activeItemId"] != item_id:
                return
            item = self._files.get(item_id)
            if item["status"] in ("completed", "failed", "cancelled", "skipped"):
                return
            self._cancel.set()
            item["status"] = "cancelling"
            self._files.replace(item)
            self._state["batch"].update({"phase": "cancelling", "progress": None})
        self._publish()

    def stop_batch(self, batch_id: str) -> None:
        """Stop the identified batch while preserving every output that has already committed."""
        with self._lock:
            if self._operation != "batch" or self._state["batch"]["id"] != batch_id:
                return
            self._stop.set()
            self._state["batch"]["status"] = "stopping"
            item_id = self._state["batch"]["activeItemId"]
            self._cancel.set()
        if item_id is not None:
            self.cancel_current(batch_id, item_id)
        else:
            self._publish()

    def manage_model(self, operation: Callable[[], None], location: Callable[[], ModelLocation]) -> None:
        """Reserve model configuration or copying against active work and publish refreshed readiness."""
        with self._lock:
            self._require_idle()
            self._operation = "setup"
        try:
            operation()
        finally:
            with self._lock:
                self._state["modelLocation"] = location()
                self._state["model"] = {
                    "status": "ready" if self.engine.is_ready() else "missing",
                    "error": None,
                    "elapsedSeconds": 0.0,
                }
                self._operation = None
            self._publish()

    def setup_model(self) -> None:
        """Start explicit model acquisition without exposing a catalog or changing source choices."""
        with self._lock:
            self._require_idle()
            self._operation = "setup"
            self._cancel.clear()
            self._setup_started = monotonic()
            self._state["model"] = {"status": "preparing", "error": None, "elapsedSeconds": 0.0}
            thread = Thread(target=self._setup, daemon=True)
            self._thread = thread
        self._publish()
        thread.start()

    def _setup(self) -> None:
        """Keep setup errors distinct from recording errors and refresh readiness after cancellation."""
        try:
            self.engine.setup(self._cancel, self._setup_phase)
            state = "ready"
            error = None
        except CancelledError:
            state = "ready" if self.engine.is_ready() else "missing"
            error = None
        except Exception as reason:
            logger.exception("Phonon setup failed")
            state = "failed"
            error = str(reason)
        with self._lock:
            self._state["model"] = {
                "status": "failed" if state == "failed" else "ready" if state == "ready" else "missing",
                "error": error,
                "elapsedSeconds": monotonic() - self._setup_started,
            }
            self._operation = None
        self._publish()

    def _setup_phase(self, _phase: str, _progress: float | None) -> None:
        """Keep explicit setup separate from queue progress and allow the engine to observe cancellation."""

    def cancel_setup(self) -> None:
        """Request cancellation of explicit model preparation without changing the queue."""
        with self._lock:
            if self._operation == "setup":
                self._cancel.set()
                self._state["model"]["status"] = "cancelling"
        self._publish()

    def transcript(self, item_id: str, offset: int = 0) -> TranscriptPage:
        """Resolve a known item's immutable result and read only the requested cue page."""
        result_id = self._files.get(item_id)["resultId"]
        if result_id is None:
            raise ValueError("This recording has no completed transcript yet.")
        return self._results.page(result_id, offset)

    def artifact_path(self, artifact_id: str) -> Path:
        """Resolve only generated, recorded outputs for native open and reveal actions."""
        for item in self._files.snapshot()["items"]:
            for output in item["outputs"]:
                if output["id"] == artifact_id and output["status"] == "written":
                    path = Path(output["path"])
                    if not path.is_file():
                        raise ValueError("The generated output was moved or deleted.")
                    return path
        raise ValueError("This generated output is not available.")

    def has_unexported_results(self) -> bool:
        """Detect session previews that would be lost before all required outputs were written."""
        return any(
            item["resultId"] is not None and item["errorStage"] == "export"
            for item in self._files.snapshot()["items"]
        )

    def is_busy(self) -> bool:
        """Report admission state for native close handling without inspecting presentation state."""
        with self._lock:
            return self._operation is not None

    def request_close(self, requested: bool) -> None:
        """Let the native titlebar request an accessible in-app close decision."""
        with self._lock:
            self._state["closeRequested"] = requested
        self._publish()

    def new_batch(self, discard_unexported: bool = False) -> None:
        """Clear session references only after explicit confirmation when exports remain unsaved."""
        with self._lock:
            self._require_idle()
            if self.has_unexported_results() and not discard_unexported:
                raise ValueError(
                    "Some transcripts have unsaved outputs. Confirm before discarding this session."
                )
            self._files.clear()
            self._results.clear()
            self._plan = None
            self._state.update(
                {
                    "batch": empty_batch(),
                    "scan": empty_scan(),
                    "exportSettings": default_exports(),
                    "notice": None,
                }
            )
        self._publish()

    def close(self) -> None:
        """Cancel background work, reap native inference, and clean only this session's results."""
        self._scan_cancel.set()
        self._stop.set()
        self._cancel.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(2.0)
            if thread.is_alive():
                raise RuntimeError("The current operation is still stopping. Please wait before quitting.")
        self.engine.close()
        self._results.close()
