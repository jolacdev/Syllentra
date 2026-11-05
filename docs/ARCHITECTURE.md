# Architecture

Python services own application state and workflow decisions. `PyWebViewApi` owns native dialogs, drops, close handling, and OS file actions. React owns presentation state. Coding and contract conventions are in [CODE_STYLE.md](CODE_STYLE.md).

```text
React workspace → generated API → PyWebViewApi → TranscriptionService
                                                   ├─ FileSelectionService
                                                   ├─ ExportService
                                                   ├─ ResultService
                                                   └─ PreferencesService
Native model controls → ModelStorageService → PhononEngine
TranscriptionService → TranscriptionEngine → PhononEngine
                                             └─ spawned worker: PyAV → Phonon
```

`backend/main.py` calls `multiprocessing.freeze_support()` before importing the native composition in `application.py`. Inference children never create windows.

## Service boundaries

| Component | Responsibility |
| --- | --- |
| `FileSelectionService` | Recursive discovery, link/junction exclusion, identity/path deduplication, overlapping-root merging, stable IDs, inclusion, and source metadata refresh on reimport. Unavailable supported files remain visible. |
| `ExportService` | Concrete preflight paths, existing/intra-batch conflict handling, shared rename stems, source fingerprints, and independent atomic artifact commits. |
| `ResultService` | Immutable session JSON, known-ID lookup, and preview pages of at most 200 cues. Full copy text accompanies only the first page. |
| `PreferencesService` | Versioned interface preferences, one-time legacy backup, and atomic replacement. |
| `ModelStorageService` | Verified external model references, persisted locations, chosen download roots, and verified backups containing only pinned assets plus attribution. |
| `TranscriptionService` | Exclusive admission to scan/setup/planning/processing, frozen queue plans, sequential execution, cancellation, outcome counts, export retries, and close coordination. |

Completed inference is retained before export. A failed export can retry without the source or another inference pass. Cancellation uses batch and item IDs so a stale request cannot affect a successor. Model-loading failures halt pending work; recoverable recording failures do not.

Snapshots are copied under locks and published outside them. Transport failures cannot change transcription outcomes. Small `BatchAppState` snapshots carry monotonic state/collection revisions; a bounded row-change journal provides collection deltas, with full-snapshot recovery after structural changes or stale cursors.

The pinned pywebview 6.1 embeds initial shared state in an unescaped JavaScript string. Windows backslashes, apostrophes, and newlines can break that injection. `PyWebViewApi` keeps shared state empty during `before_load`, then publishes the latest snapshot on `loaded` as a serialized JSON object through pywebview's state proxy. Native state mutation is locked against initialization; JavaScript execution stays outside that lock because `before_load` runs on the GUI thread. The same lifecycle applies to reloads; updates during loading are recovered from the service snapshot. React waits for both native commands and the shared-state event interface before mounting the workspace.

## Inference and media

`TranscriptionEngine` defines model metadata, readiness, explicit setup, transcription, and close. Each engine supplies its model identity, source URL, and supported language codes; the interface localizes the language names. Vendor values stay inside the Phonon adapter; JSON-only `TypedDict` schemas define application transport. A narrow Fermion stub supports strict MyPy checks against the pinned public speech API.

`PhononEngine` supervises one reusable spawned worker through identified JSON pipe messages. Samples and results use parent-owned temporary files. The supervisor polls cancellation every 50 ms, terminates/reaps native work before its successor, and replaces crashed workers.

Only explicit setup resolves the remote repository. Transcription loads a local canonical directory. Readiness verifies pinned member digests, cached against file metadata; failed repair restores the previous app-owned model directory. External model references are verified in place and remain user-owned.

PyAV decodes the marked-default audio stream, falling back to the first, into mono float32 audio at 16 kHz. Container/frame timestamps preserve leading silence and gaps. Cues use the SDK’s normalized subtitle segments, which handle same-frame and overlapping decoder words; invalid, nonfinite, overlapping, truncated, or untimed output is rejected. The public SDK has no progress callback. The adapter submits pause-aligned windows of at most 35 seconds through its public API and reports completed samples as current-recording progress. Language metadata stays null because the SDK does not expose detected language. No external FFmpeg command is needed.

Exports use temporary sibling files and independent atomic publication. Overwrites recheck reviewed regular files; late conflicts fail without clobbering. POSIX no-clobber publication requires hard links; unsupported destinations retain the transcript for retry.

## Frontend and persistence

`useTranscription` subscribes before hydration, rejects stale revisions, merges collection deltas, tracks pending commands by key, and handles command errors. `useTranscript` owns paged preview reads and stale-selection protection. `useNativeDrop` binds after hydration and requires full native paths.

`BatchWorkspaceScreen` composes selection, exports, queue controls, previews, and dialogs. Inclusion, expansion, keyboard focus, and inspection are separate. The tree renders expanded branches with ARIA hierarchy metadata and roving keyboard focus. Expanded preview uses a wide native dialog; one conflict action applies to each recording's existing output set.

Queue state, export choices, and previews are session scoped. Settings and model locations persist in automatically created portable storage. First initialization atomically copies legacy settings and rebases model references without copying weights. Existing portable data wins; initialization/write failures use system storage, and environment overrides bypass migration. Settings shows the active data directory. See [portable storage](../README.md#portable-by-default).

## Packaging

Per-target Python 3.13 locks select CPU Torch on Windows/Linux and MLX on macOS arm64. Linux includes PySide6. The desktop and runtime-probe specs share `scripts/runtime_assets.py`, which collects dynamic Fermion sources, matching native libraries and checksum sidecars, package metadata, and MLX/Metal resources while excluding foreign binaries. Vendor integrity checks remain enabled.

Native Windows/Linux verification and distribution signing remain outstanding. Build guidance is in [WINDOWS_BUILD.md](WINDOWS_BUILD.md); the [offline runtime probe](../backend/verify_runtime.py) checks inference using existing model assets.
