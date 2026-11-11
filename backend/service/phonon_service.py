"""Supervise one reusable Phonon worker without exposing vendor state to the application."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import shutil
import stat
import sys
from collections.abc import Callable
from multiprocessing.process import BaseProcess
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, RLock
from time import monotonic
from typing import Literal, TypedDict
from uuid import uuid4

import fermion
import numpy as np
from numpy.typing import NDArray

from constants import MODEL_FOLDER
from schemas.batch import InferenceOutput, ModelInfo
from service.engine import CancelledError
from utils.audio_utils import SAMPLE_RATE, prepare_audio
from utils.audio_windows import audio_windows
from utils.transcript_utils import parse_output, require_number, require_string

# Duplex pipes use named-pipe connections on Windows and socket connections on POSIX.
if sys.platform == "win32":
    from multiprocessing.connection import PipeConnection as _PlatformConnection
else:
    from multiprocessing.connection import Connection as _PlatformConnection

type WorkerConnection = _PlatformConnection


REPORT_INTERVAL = 0.25
MODEL_ID = "FermionResearch/Phonon-2.5"
MODEL_PATH = Path("speech") / "FermionResearch__Phonon-2.5" / MODEL_FOLDER
# These members belong to the canonical profile pinned by fermion-research 0.2.15.
MODEL_FILES = {
    "config.json": "b8ee2310784b2ffb62200bc9d2301cdc0576141ee9c53f7a41a5a2d181910cc9",
    "packed_manifest.json": "2c98e5d0e1349fa146f21cdc168d681b186711c78abcfac47af16c25649f5c89",
    "model.fermion": "17cb62d08e751a41819eb779db089aa7ac4eb2bab433ba5c2991d8cbd3cfefb9",
}
PhaseCallback = Callable[[str, float | None], None]
WorkerTarget = Callable[[WorkerConnection, str], None]


class WorkerRequest(TypedDict):
    """Keep the admitted source and stream together in the JSON worker protocol."""

    mode: Literal["setup", "transcribe"]
    source: str
    directory: str
    audioStreamIndex: int | None


def _send(
    connection: WorkerConnection, request_id: str, kind: str, phase: str = "", progress: float | None = None
) -> None:
    """Send a bounded status message without a Python object serialization contract."""
    connection.send_bytes(
        json.dumps({"id": request_id, "kind": kind, "phase": phase, "progress": progress}).encode()
    )


def _run_audio(
    connection: WorkerConnection,
    request_id: str,
    speech: fermion.SpeechModel,
    request: WorkerRequest,
) -> None:
    """Decode one recording and save normalized output inside its parent-owned session directory."""
    last_report = 0.0
    source = Path(request["source"])
    directory = Path(request["directory"])

    def report(progress: float | None) -> None:
        """Coalesce decoder progress without parsing vendor log messages."""
        nonlocal last_report
        now = monotonic()
        if now - last_report >= REPORT_INTERVAL:
            last_report = now
            _send(connection, request_id, "phase", "preparing", progress)

    with prepare_audio(source, directory, Event(), report, request["audioStreamIndex"]) as prepared:
        audio = np.memmap(prepared.path, dtype=np.float32, mode="r", shape=(prepared.samples,))
        try:
            output = transcribe_audio(
                speech,
                audio,
                lambda progress: _send(connection, request_id, "phase", "transcribing", progress),
            )
        finally:
            del audio
    (directory / "result.json").write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    _send(connection, request_id, "complete")


def normalize_result(result: fermion.SpeechResult) -> InferenceOutput:
    """Use the SDK's normalized subtitle segments instead of rejecting raw decoder word overlaps."""
    if result.truncated:
        raise ValueError("The model returned an incomplete transcript. No outputs were written.")
    if result.text and (not result.timed or not result.segments):
        raise ValueError("The model returned speech without usable timestamps.")
    output: InferenceOutput = {
        "text": result.text.strip(),
        "duration": result.audio_seconds,
        "language": None,
        "segments": [
            {"id": index, "start": segment["start"], "end": segment["end"], "text": segment["text"]}
            for index, segment in enumerate(result.segments)
        ],
    }
    output = parse_output(output)
    if " ".join(" ".join(segment["text"] for segment in output["segments"]).split()) != " ".join(
        output["text"].split()
    ):
        raise ValueError("The model returned subtitle segments that do not cover the transcript text.")
    return output


def transcribe_audio(
    speech: fermion.SpeechModel, audio: NDArray[np.float32], report: Callable[[float], None]
) -> InferenceOutput:
    """Decode pause-aligned windows with absolute captions and progress based on completed source samples."""
    total = audio.size
    if not total:
        raise ValueError("This recording contains no decodable audio.")
    output: InferenceOutput = {"text": "", "duration": total / SAMPLE_RATE, "language": None, "segments": []}
    texts: list[str] = []
    report(0.0)
    for start, end in audio_windows(audio):
        result = normalize_result(speech.transcribe_array_detailed(audio[start:end]))
        if result["text"]:
            texts.append(result["text"])
        for segment in result["segments"]:
            output["segments"].append(
                {
                    **segment,
                    "id": len(output["segments"]),
                    "start": round(segment["start"] + start / SAMPLE_RATE, 3),
                    "end": round(segment["end"] + start / SAMPLE_RATE, 3),
                }
            )
        report(end / total * 100)
    output["text"] = " ".join(texts)
    return parse_output(output)


def run_worker(connection: WorkerConnection, cache: str) -> None:
    """Resolve heavy speech modules only inside a spawned process and reuse one loaded model."""
    os.environ["FERMION_CACHE_DIR"] = cache
    os.environ["HF_HOME"] = str(Path(cache) / "hub")
    os.environ["HF_HUB_CACHE"] = str(Path(cache) / "hub" / "cache")
    os.environ["HF_XET_CACHE"] = str(Path(cache) / "hub" / "xet")
    os.environ["HF_ASSETS_CACHE"] = str(Path(cache) / "hub" / "assets")
    os.environ["HF_TOKEN_PATH"] = str(Path(cache) / "hub" / "token")
    speech: fermion.SpeechModel | None = None
    try:
        while True:
            try:
                value: object = json.loads(connection.recv_bytes())
            except EOFError:
                return
            if not isinstance(value, dict):
                raise ValueError("Invalid worker request")
            request_id = require_string(value.get("id"))
            mode = require_string(value.get("mode"))
            model = require_string(value.get("model"))
            try:
                if mode == "setup":
                    _send(connection, request_id, "phase", "setup")
                    speech = fermion.load_speech(MODEL_ID)
                elif speech is None:
                    _send(connection, request_id, "phase", "loading")
                    speech = fermion.load_speech(model)
                if speech.profile != "five-value-25":
                    raise ValueError("The local folder is not the canonical Phonon-2.5 Multilingual model.")
                if mode == "setup":
                    _send(connection, request_id, "complete")
                else:
                    stream_index = value.get("audioStreamIndex")
                    if stream_index is not None and (type(stream_index) is not int or stream_index < 0):
                        raise ValueError("Invalid audio stream index")
                    request: WorkerRequest = {
                        "mode": "transcribe",
                        "source": require_string(value.get("source")),
                        "directory": require_string(value.get("directory")),
                        "audioStreamIndex": stream_index,
                    }
                    _run_audio(connection, request_id, speech, request)
            except (Exception, SystemExit) as error:
                connection.send_bytes(
                    json.dumps({"id": request_id, "kind": "error", "error": str(error)}).encode()
                )
    finally:
        connection.close()


class PhononEngine:
    """Isolate native inference, explicit setup, cancellation, and crash recovery behind a small adapter."""

    def __init__(self, directory: Path, worker_target: WorkerTarget = run_worker) -> None:
        """Keep model paths local and defer native imports and weights until setup or transcription."""
        self.directory = directory.absolute()
        self.model_path = self.directory / MODEL_PATH
        self._context = multiprocessing.get_context("spawn")
        self._lock = RLock()
        self._process: BaseProcess | None = None
        self._connection: WorkerConnection | None = None
        self._worker_target = worker_target
        self._worker_cache: TemporaryDirectory[str] | None = None
        self._verified: tuple[tuple[str, int, int, int], ...] | None = None

    def get_info(self) -> ModelInfo:
        """Expose the pinned model's published language coverage independently of interface translations."""
        return {
            "name": "Phonon-2.5 Multilingual",
            "sourceUrl": "https://www.fermionresearch.com/models/phonon-2-5/",
            "languages": [
                "en",
                "es",
                "fr",
                "de",
                "it",
                "pt",
                "nl",
                "pl",
                "ru",
                "uk",
                "ro",
                "cs",
                "sk",
                "bg",
                "hr",
                "sv",
                "da",
                "fi",
                "et",
                "lv",
                "lt",
                "hu",
                "sl",
                "mt",
                "el",
            ],
        }

    def is_ready(self) -> bool:
        """Inspect only the expected local assets without using the network or loading native code."""
        try:
            if self.model_path.resolve() != self.model_path:
                return False
            signatures = []
            for name in MODEL_FILES:
                path = self.model_path / name
                if not path.is_file() or path.is_symlink():
                    return False
                stat = path.stat()
                signatures.append((name, stat.st_size, stat.st_mtime_ns, stat.st_ino))
            signature = tuple(signatures)
            if signature != self._verified:
                for name, digest in MODEL_FILES.items():
                    with (self.model_path / name).open("rb") as handle:
                        if hashlib.file_digest(handle, "sha256").hexdigest() != digest:
                            return False
                self._verified = signature
            return True
        except OSError:
            return False

    def _start(self, cache: Path | None) -> WorkerConnection:
        """Start a clean child with a private connection and no native window side effects."""
        if self._process is None or not self._process.is_alive() or self._connection is None:
            self._stop()
            if cache is None:
                self._ensure_model_directory(self.directory)
                self._worker_cache = TemporaryDirectory(prefix="syllentra-worker-", dir=self.directory)
                cache = Path(self._worker_cache.name)
            parent, child = self._context.Pipe()
            self._process = self._context.Process(
                target=self._worker_target, args=(child, str(cache)), daemon=True
            )
            self._process.start()
            child.close()
            self._connection = parent
        return self._connection

    def _stop(self) -> None:
        """Terminate and reap native work before discarding its connection or admitting a successor."""
        process = self._process
        if process is not None:
            if process.is_alive():
                process.terminate()
                process.join(0.5)
            if process.is_alive():
                process.kill()
                # Reaping a Metal worker can take longer under load even after termination is requested.
                process.join(1.5)
            if process.is_alive():
                raise RuntimeError(
                    "The native worker could not be stopped. Wait before starting another task."
                )
            process.close()
        if self._connection is not None:
            self._connection.close()
        self._process = None
        self._connection = None
        if self._worker_cache is not None:
            self._worker_cache.cleanup()
            self._worker_cache = None

    def _execute(
        self,
        request: WorkerRequest,
        cancel: Event,
        report: PhaseCallback,
        *,
        cache: Path | None = None,
    ) -> None:
        """Wait for one identified request while allowing bounded cancellation and crash detection."""
        with self._lock:
            if cancel.is_set():
                raise CancelledError
            connection = self._start(cache)
            request_id = uuid4().hex
            connection.send_bytes(
                json.dumps(
                    {
                        **request,
                        "id": request_id,
                        "model": str(self.model_path),
                    }
                ).encode()
            )
            try:
                while True:
                    if cancel.is_set():
                        self._stop()
                        raise CancelledError
                    if not connection.poll(0.05):
                        if self._process is None or not self._process.is_alive():
                            raise RuntimeError(
                                "The transcription worker stopped unexpectedly. Retry this recording."
                            )
                        continue
                    value: object = json.loads(connection.recv_bytes())
                    if not isinstance(value, dict) or value.get("id") != request_id:
                        raise RuntimeError("The transcription worker returned an invalid response.")
                    kind = value.get("kind")
                    if kind == "error":
                        raise RuntimeError(require_string(value.get("error")))
                    if kind == "complete":
                        if cancel.is_set():
                            self._stop()
                            raise CancelledError
                        return
                    if kind != "phase":
                        raise RuntimeError("The transcription worker returned an unknown response.")
                    progress: object = value.get("progress")
                    report(
                        require_string(value.get("phase")),
                        require_number(progress) if progress is not None else None,
                    )
            except (EOFError, BrokenPipeError, OSError) as error:
                self._stop()
                raise RuntimeError(
                    "The transcription worker stopped unexpectedly. Retry this recording."
                ) from error

    def _ensure_model_directory(self, path: Path) -> None:
        """Create a portable directory after checking for redirected ancestors."""
        if path.resolve() != path:
            raise ValueError(f"Model storage cannot use linked directories: {path}")
        path.mkdir(parents=True, exist_ok=True)

    def _require_free_model_path(self) -> None:
        """Keep occupied or redirected model paths untouched."""
        if self.model_path.exists() or self.model_path.is_symlink() or self.model_path.is_junction():
            raise FileExistsError(
                f"Move the incomplete or occupied model folder before retrying: {self.model_path}"
            )

    def _install_model(self, staging: Path) -> None:
        """Publish only a complete, verified copy from portable staging."""
        self._verify_model(staging)
        self._ensure_model_directory(self.model_path.parent)
        self._require_free_model_path()
        staging.rename(self.model_path)

    def _verify_model(self, staging: Path) -> None:
        """Check the pinned files without changing the active model."""
        verifier = PhononEngine(staging.parent)
        verifier.model_path = staging
        if not verifier.is_ready():
            raise ValueError("The selected files do not match the verified Phonon-2.5 Multilingual model.")

    def import_model(self, source: Path) -> None:
        """Copy only pinned model assets into the portable store."""
        with self._lock:
            source = source.resolve(strict=True)
            if source.name != MODEL_FOLDER:
                raise ValueError(f"Select the model folder named {MODEL_FOLDER}.")
            if self.is_ready():
                # All supported imports have the same pinned bytes.
                if source != self.model_path:
                    self._verify_model(source)
                return
            self._require_free_model_path()
            self._ensure_model_directory(self.directory)
            with TemporaryDirectory(prefix="syllentra-import-", dir=self.directory) as temporary:
                staging = Path(temporary) / MODEL_FOLDER
                staging.mkdir()
                for name in MODEL_FILES:
                    member = source / name
                    if not stat.S_ISREG(member.lstat().st_mode) or member.resolve() != member:
                        raise ValueError(f"Expected a regular model file: {member}")
                    shutil.copyfile(member, staging / name)
                self._install_model(staging)

    def setup(self, cancel: Event, report: PhaseCallback) -> None:
        """Download in portable staging and install a verified model."""
        with self._lock:
            if cancel.is_set():
                raise CancelledError
            if self.is_ready():
                return
            self._require_free_model_path()
            self._ensure_model_directory(self.directory)
            self._stop()
            with TemporaryDirectory(prefix="syllentra-download-", dir=self.directory) as temporary:
                cache = Path(temporary)
                try:
                    self._execute(
                        {"mode": "setup", "source": "", "directory": "", "audioStreamIndex": None},
                        cancel,
                        report,
                        cache=cache,
                    )
                finally:
                    self._stop()
                if cancel.is_set():
                    raise CancelledError
                self._install_model(cache / MODEL_PATH)

    def transcribe(
        self, source: Path, cancel: Event, report: PhaseCallback, *, audio_stream_index: int | None = None
    ) -> InferenceOutput:
        """Transcribe a local container while preserving worker reuse and cleaning session audio."""
        if not self.is_ready():
            raise ValueError("Prepare Phonon-2.5 before transcribing recordings.")
        with TemporaryDirectory(prefix="syllentra-audio-") as directory:
            self._execute(
                {
                    "mode": "transcribe",
                    "source": str(source),
                    "directory": directory,
                    "audioStreamIndex": audio_stream_index,
                },
                cancel,
                report,
            )
            value: object = json.loads((Path(directory) / "result.json").read_text(encoding="utf-8"))
            return parse_output(value)

    def close(self) -> None:
        """Release the loaded model after the caller has cancelled or completed active work."""
        with self._lock:
            self._stop()
