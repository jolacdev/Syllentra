"""Define engine-independent batch, selection, output, and result contracts."""

from typing import Literal, TypedDict

from schemas.transcription import TranscriptionSegment

ExportFormat = Literal["srt", "txt", "vtt"]
ConflictAction = Literal["ask", "create", "skip", "overwrite", "rename"]
ItemStatus = Literal[
    "ready",
    "queued",
    "preparing",
    "transcribing",
    "exporting",
    "cancelling",
    "completed",
    "skipped",
    "cancelled",
    "failed",
]


class SourceRoot(TypedDict):
    """Preserve an imported source boundary and its unique destination folder name."""

    id: str
    path: str
    name: str
    alias: str
    isFolder: bool


class OutputArtifact(TypedDict):
    """Track an individual output decision and its independent write outcome."""

    id: str
    format: ExportFormat
    path: str
    action: ConflictAction
    status: Literal["planned", "skipped", "written", "failed", "not_needed"]
    conflict: bool
    existingSignature: str | None
    error: str | None


class MediaItem(TypedDict):
    """Describe one canonical source, inclusion choice, and processing outcome."""

    id: str
    rootId: str
    path: str
    name: str
    relativePath: str
    extension: str
    size: int
    modifiedNs: str
    isIncluded: bool
    isAvailable: bool
    status: ItemStatus
    error: str | None
    errorStage: Literal["source", "model", "inference", "export"] | None
    resultId: str | None
    noSpeech: bool
    outputs: list[OutputArtifact]


class Workspace(TypedDict):
    """Fetch collection metadata separately from high-frequency progress snapshots."""

    revision: int
    roots: list[SourceRoot]
    items: list[MediaItem]


class WorkspaceDelta(Workspace):
    """Return changed source rows or an explicit full reset when collection structure changes."""

    reset: bool


class ExportSettings(TypedDict):
    """Keep output choices scoped to the current batch."""

    formats: list[ExportFormat]
    destination: str | None


class ItemPlan(TypedDict):
    """Freeze a source fingerprint and its reserved output paths before admission."""

    itemId: str
    sourcePath: str
    size: int
    modifiedNs: str
    resultId: str | None
    outputs: list[OutputArtifact]


class BatchPlan(TypedDict):
    """Describe a revision-bound output plan that must be resolved before processing."""

    id: str
    revision: int
    items: list[ItemPlan]


class InferenceOutput(TypedDict):
    """Normalize actual speech and timings without leaking vendor result objects."""

    text: str
    duration: float
    language: str | None
    segments: list[TranscriptionSegment]


class BatchTranscript(TypedDict):
    """Keep an immutable session result available for preview and export-only retry."""

    id: str
    itemId: str
    sourcePath: str
    createdAt: str
    processingSeconds: float
    output: InferenceOutput


class TranscriptPage(TypedDict):
    """Read a bounded portion of an immutable transcript without retaining every result in React."""

    id: str
    text: str
    duration: float
    processingSeconds: float
    totalSegments: int
    offset: int
    segments: list[TranscriptionSegment]


class InterfacePreferences(TypedDict):
    """Persist only versioned interface preferences while preserving the legacy data identity."""

    version: Literal[2]
    theme: Literal["system", "light", "dark"]
    interfaceLanguage: Literal["system", "en", "es-ES"]


class ScanState(TypedDict):
    """Report bounded import activity independently of the collection payload."""

    isRunning: bool
    isCancelled: bool
    discovered: int
    ignored: int
    duplicates: int
    currentPath: str


class ModelState(TypedDict):
    """Show readiness for one fixed model without a catalog or tuning controls."""

    status: Literal["missing", "preparing", "cancelling", "ready", "failed"]
    error: str | None


class BatchState(TypedDict):
    """Publish lightweight queue totals and the current measured phase."""

    id: str
    status: Literal["idle", "running", "stopping", "completed", "cancelled", "failed"]
    total: int
    completed: int
    failed: int
    skipped: int
    cancelled: int
    noSpeech: int
    activeItemId: str | None
    phase: str
    progress: float | None
    elapsedSeconds: float


class ModelInfo(TypedDict):
    """Describe engine-owned model identity and supported spoken-language codes."""

    name: str
    languages: list[str]
    sourceUrl: str


class ModelLocation(TypedDict):
    """Expose the actual local model and download directory without accepting frontend paths."""

    path: str
    downloadDirectory: str


class BatchAppState(TypedDict):
    """Keep frequently published state small and fetch collection/results by revision."""

    revision: int
    collectionRevision: int
    modelInfo: ModelInfo
    modelLocation: ModelLocation
    preferences: InterfacePreferences
    exportSettings: ExportSettings
    scan: ScanState
    model: ModelState
    batch: BatchState
    notice: str | None
    closeRequested: bool


class CommandError(TypedDict):
    """Separate localized user-facing error identity from optional technical details."""

    code: Literal["invalid_request", "unavailable", "busy", "unexpected"]
    details: str


class CommandReply(TypedDict):
    """Return expected command failure as data instead of depending on English exception phrases."""

    error: CommandError | None


class PlanReply(TypedDict):
    """Return a prepared plan or a structured error before inference starts."""

    plan: BatchPlan | None
    error: CommandError | None
