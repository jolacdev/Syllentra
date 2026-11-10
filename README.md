# Syllentra

Local batch transcription of audio and video with **Phonon-2.5 Multilingual**, using Python, pywebview, and React. Download the model once or select a verified local copy for offline first use. Transcription runs on your computer. The model supports [25 European languages](https://www.fermionresearch.com/models/phonon-2-5/), including English and Spanish; Japanese is not supported.

## Using the app

1. Add files, select multiple recordings, add folders recursively, or drop them into **Recordings**. Each import extends the current tree.
2. Choose recordings with file, folder, or extension checkboxes. **New batch** beside the import buttons starts an empty batch and resets export choices while preserving media and exported files.
3. Select SRT (default), TXT, and/or VTT. Save beside sources or to a custom folder that preserves imported folder hierarchy.
4. Review existing outputs with one skip, overwrite, or rename decision per recording, then start the batch.
5. Follow the current recording’s transcription percentage, measured from completed audio segments. Cancel the current recording or stop the queue as needed. Inspect results, **Expand** the read-only preview, copy text, and open or reveal exported files.

Model setup shows status and elapsed time. Finished batches show outcome counts and time spent. File details include duration and processing time.

Closing during active work asks for confirmation. **Keep open** continues processing; **Stop & quit** stops the work before closing and preserves files already exported.

**Audio tracks:** The optional **Preferred audio language** in general **Settings** applies only to files containing multiple audio tracks. It starts at **Use file default** and remembers your choice. Single-track recordings always use their only track, regardless of language. For multi-track files, standard ISO language codes and BCP 47 tags are normalized independently for each source; matching dialogue tracks take priority over commentary/audio description identified by standard track flags, then default flags and track order break ties. Without a language match, the file’s default or first audio track is used automatically. The workspace summarizes selections and fallback files without interrupting the queue. File details show track metadata and allow a manual override. Changing the effective track invalidates the previous session transcript; existing exports still use the normal output-conflict review.

Track languages are read from container metadata, which may be absent or incorrect; they are not verified against the spoken audio. The model independently recognizes the audio it receives.

Enable **Include audio language in subtitle filenames** in **Export settings** to get names like `Recording.en.srt` or `Recording.en.vtt` when the selected track has a recognized language tag. Files with unknown tags and TXT exports use plain filenames. This option is off by default and resets with each new batch.

Silence produces no empty outputs. Recoverable file errors allow the queue to continue; model-loading failures halt it. Failed exports can reuse the session transcript. Selections and previews last for the session; saved exports persist. Clearing or quitting protects transcripts with unsaved outputs. Settings supports English/Spanish and system/light/dark appearance, and lists the active model’s supported spoken languages.

## Models and portable storage

Settings shows the active model path and download storage folder:

- **Use local model** verifies and references an existing `model_phonon25_f25x1_48k_int6` folder in place, without copying or downloading.
- **Choose download folder** switches storage without moving or deleting older copies. Downloads use `speech/FermionResearch__Phonon-2.5/model_phonon25_f25x1_48k_int6` within that folder. Choose a download folder before downloading a replacement for an externally referenced model.
- **Back up model** creates a verified folder containing the model assets and attribution. Transfer it to another machine and select it with **Use local model**. Existing backups are preserved.

### Portable by default

Syllentra automatically creates **Syllentra Data** next to the application for settings, logs, and downloaded models. Move the application and this folder together. Settings shows the active data and model folders.

Existing settings are copied on first use; existing models stay in place. To take an older or external model with you, use **Back up model** to save it inside `Syllentra Data`, then select the backup with **Use local model**. Existing portable data is reused without importing system settings again.

If portable storage cannot be created or written to, Syllentra uses the normal **PyWhisper Studio** system data folder. Move the application to a writable location and relaunch to use portable storage.

`SYLLENTRA_DATA_DIR` overrides storage; `PYWHISPER_DATA_DIR` remains supported. These overrides bypass automatic migration. Original system data is preserved.

## Development

Use **Python 3.13**, **Node.js 22**, and **pnpm 12.3.4**.

```sh
pnpm initialize
pnpm dev:frontend
# In another terminal:
pnpm dev:backend
```

Initialization installs both JavaScript dependency trees and the target's hash-locked Python dependencies in `.venv`. Use `pnpm start` for the compiled frontend, or `pnpm build` for a native candidate in `dist/`. Development stores data in the Git-ignored `Syllentra Data` folder at the repository root. Builds replace `dist`; move packaged applications elsewhere before first use.

Targets: macOS arm64 (14+), Windows x64, and Linux x64. Intel macOS is deferred because of the Python/runtime dependency combination. Windows needs .NET/WebView2; see [Windows builds](docs/WINDOWS_BUILD.md). Linux uses PySide6/QtWebEngine; Ubuntu 24.04 needs `libegl1 libgl1 libnss3 libasound2t64 libxkbcommon-x11-0 libxcb-cursor0`.

Browser development uses explicit simulated previews: `http://localhost:3000/?preview=ready`. Other scenarios are `empty`, `conflicts`, `error`, and `large` (10,000 nested recordings). Production builds exclude the mock.

## Checks

GitHub Actions runs these checks on all three targets. Native application packaging stays local with `pnpm build`; CI does not upload application bundles.

```sh
node scripts/python.mjs lint
node scripts/python.mjs format
node scripts/python.mjs types
node scripts/python.mjs test
pnpm check-api
pnpm --dir frontend lint:no-fix
pnpm --dir frontend test
pnpm _build-frontend
```

After intentional bridge changes, run `pnpm gen-api`. See [code conventions](docs/CODE_STYLE.md), [architecture](docs/ARCHITECTURE.md), and [dependency locks](docs/DEPENDENCIES.md).

## Licenses

Application: [BSD 3-Clause](LICENSE). [Fermion runtime](https://github.com/fermionresearch/phonon): Apache-2.0. [Phonon-2.5 Multilingual](https://huggingface.co/FermionResearch/Phonon-2.5), derived from NVIDIA Parakeet TDT 0.6B v3: CC-BY-4.0. Preserve model attribution and bundled dependency notices when distributing builds.
