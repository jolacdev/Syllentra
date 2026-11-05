"""Verify timed, offline inference and model reuse in source or frozen builds."""

import argparse
import json
import multiprocessing
import socket
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic
from unittest.mock import patch

import fermion
import numpy as np

from service.phonon_service import PhononEngine, WorkerConnection, run_worker
from utils.audio_utils import prepare_audio


def reject_connection(_socket: socket.socket, _address: object) -> None:
    """Refuse network connections while checking local inference."""
    raise OSError("Network access is disabled for the offline runtime verification.")


def ignore_progress(_value: float | None) -> None:
    """Keep verification output machine-readable without decoder progress noise."""


def verify(model: Path, recordings: list[Path]) -> None:
    """Load weights once and report timed results with outbound connections blocked."""
    with patch.object(socket.socket, "connect", reject_connection), TemporaryDirectory() as temporary:
        started = monotonic()
        speech = fermion.load_speech(str(model))
        print(json.dumps({"event": "loaded", "seconds": monotonic() - started, "profile": speech.profile}))
        for recording in recordings:
            started = monotonic()
            with prepare_audio(recording, Path(temporary), Event(), ignore_progress) as prepared:
                audio = np.memmap(prepared.path, dtype=np.float32, mode="r", shape=(prepared.samples,))
                try:
                    output = speech.transcribe_array_detailed(audio)
                finally:
                    # A memmap's view must be released before Windows can remove its backing file.
                    del audio
            if output.text and (not output.timed or not output.words):
                raise ValueError("The model returned speech without word timings.")
            if output.truncated:
                raise ValueError("The model returned truncated output.")
            print(
                json.dumps(
                    {
                        "event": "transcript",
                        "source": str(recording),
                        "text": output.text,
                        "words": len(output.words),
                        "segments": len(output.segments),
                        "duration": output.audio_seconds,
                        "seconds": monotonic() - started,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )


def offline_worker(connection: WorkerConnection, cache: str) -> None:
    """Block connections in the actual spawned child while exercising the production worker."""
    with (
        patch.object(socket.socket, "connect", reject_connection),
        patch.object(socket.socket, "connect_ex", reject_connection),
    ):
        run_worker(connection, cache)


def ignore_phase(_phase: str, _progress: float | None) -> None:
    """Keep supervised probe output independent of intermediate phase traffic."""


def verify_supervised(model: Path, recordings: list[Path]) -> None:
    """Verify the same cancellable worker and decoder used by the desktop application."""
    engine = PhononEngine(model.parents[2], worker_target=offline_worker)
    if engine.model_path.resolve() != model.resolve():
        raise ValueError("Pass the canonical prepared Phonon-2.5 model directory.")
    try:
        for recording in recordings:
            started = monotonic()
            output = engine.transcribe(recording, Event(), ignore_phase)
            process = engine._process
            print(
                json.dumps(
                    {
                        "event": "supervised_transcript",
                        "source": str(recording),
                        "pid": process.pid if process else None,
                        "text": output["text"],
                        "segments": len(output["segments"]),
                        "seconds": monotonic() - started,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    finally:
        engine.close()


class Arguments(argparse.Namespace):
    """Describe validated parser fields without leaking argparse's dynamic result types."""

    model: Path
    recordings: list[Path]
    supervised: bool


def main() -> None:
    """Accept an already prepared model and recordings without initiating downloads."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("recordings", nargs="+", type=Path)
    parser.add_argument("--supervised", action="store_true")
    arguments = parser.parse_args(namespace=Arguments())
    if not arguments.model.is_dir():
        parser.error("The local model directory does not exist.")
    if arguments.supervised:
        verify_supervised(arguments.model, arguments.recordings)
    else:
        verify(arguments.model, arguments.recordings)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
