"""Keep immutable transcript previews on disk for the lifetime of one application session."""

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from uuid import uuid4

from schemas.batch import BatchTranscript, InferenceOutput, TranscriptPage
from utils.transcript_utils import parse_output, require_number, require_string

PREVIEW_PAGE_SIZE = 200


class ResultService:
    """Bound resident result memory without creating persisted history or copying source media."""

    def __init__(self) -> None:
        """Create a private session directory and an index of results owned by this process."""
        self._temporary = TemporaryDirectory(prefix="syllentra-results-")
        self._directory = Path(self._temporary.name)
        self._ids: set[str] = set()
        self._lock = RLock()

    def put(self, item_id: str, source: str, output: InferenceOutput, seconds: float) -> str:
        """Store one completed normalized result before attempting its output artifacts."""
        result_id = uuid4().hex
        transcript: BatchTranscript = {
            "id": result_id,
            "itemId": item_id,
            "sourcePath": source,
            "createdAt": datetime.now(UTC).isoformat(),
            "processingSeconds": seconds,
            "output": output,
        }
        with self._lock:
            (self._directory / f"{result_id}.json").write_text(
                json.dumps(transcript, ensure_ascii=False), encoding="utf-8"
            )
            self._ids.add(result_id)
        return result_id

    def get(self, result_id: str) -> BatchTranscript:
        """Validate a known session result without accepting arbitrary filesystem paths."""
        with self._lock:
            if result_id not in self._ids:
                raise ValueError("This session transcript is no longer available.")
            value: object = json.loads((self._directory / f"{result_id}.json").read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("This session transcript is invalid.")
        return {
            "id": require_string(value.get("id")),
            "itemId": require_string(value.get("itemId")),
            "sourcePath": require_string(value.get("sourcePath")),
            "createdAt": require_string(value.get("createdAt")),
            "processingSeconds": require_number(value.get("processingSeconds")),
            "output": parse_output(value.get("output")),
        }

    def page(self, result_id: str, offset: int = 0) -> TranscriptPage:
        """Read a bounded cue page and include full copyable text only on the initial page."""
        if offset < 0:
            raise ValueError("Choose a valid transcript page.")
        result = self.get(result_id)
        output = result["output"]
        return {
            "id": result_id,
            "text": output["text"] if offset == 0 else "",
            "duration": output["duration"],
            "processingSeconds": result["processingSeconds"],
            "totalSegments": len(output["segments"]),
            "offset": offset,
            "segments": output["segments"][offset : offset + PREVIEW_PAGE_SIZE],
        }

    def clear(self) -> None:
        """Remove only this session's transcript files while preserving exported artifacts."""
        with self._lock:
            for result_id in self._ids:
                (self._directory / f"{result_id}.json").unlink(missing_ok=True)
            self._ids.clear()

    def close(self) -> None:
        """Remove the private session directory after all workers and reads have settled."""
        with self._lock:
            self._ids.clear()
            self._temporary.cleanup()
