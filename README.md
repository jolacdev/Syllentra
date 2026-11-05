# Syllentra

Local batch transcription of audio and video with **Phonon-2.5 Multilingual**, using Python, pywebview, and React. Download the model once or select a verified local copy for offline first use. Transcription runs on your computer. The model supports [25 European languages](https://www.fermionresearch.com/models/phonon-2-5/), including English and Spanish; Japanese is not supported.

## Using the app

1. Add files, select multiple recordings, add folders recursively, or drop them into **Recordings**. Each import extends the current tree.
2. Choose recordings with file, folder, or extension checkboxes. **New batch** beside the import buttons starts an empty batch and resets export choices while preserving media and exported files.
3. Select SRT (default), TXT, and/or VTT. Save beside sources or to a custom folder that preserves imported folder hierarchy.
4. Review existing outputs with one skip, overwrite, or rename decision per recording, then start the batch.
5. Follow the current recording’s transcription percentage, measured from completed audio segments. Cancel the current recording or stop the queue as needed. Inspect results, **Expand** the read-only preview, copy text, and open or reveal exported files.

Silence produces no empty outputs. Recoverable file errors allow the queue to continue; model-loading failures halt it. Failed exports can reuse the session transcript. Selections and previews last for the session; saved exports persist. Clearing or quitting protects transcripts with unsaved outputs. Settings supports English/Spanish and system/light/dark appearance, and lists the active model’s supported spoken languages.

## Models and portable storage

Settings shows the active model path and download storage folder:

- **Use local model** verifies and references an existing `model_phonon25_f25x1_48k_int6` folder in place, without copying or downloading.
- **Choose download folder** switches storage without moving or deleting older copies. Downloads use `speech/FermionResearch__Phonon-2.5/model_phonon25_f25x1_48k_int6` within that folder. Choose a download folder before downloading a replacement for an externally referenced model.
- **Back up model** creates a verified folder containing the model assets and attribution. Transfer it to another machine and select it with **Use local model**. Existing backups are preserved.

### Enabling portable mode

**Syllentra Data** is an ordinary folder you create with that exact name. It stores the app's settings, logs, and default model cache. Put it in the **same parent folder as the application**, outside the macOS app bundle:

```text
macOS                         Windows / Linux
My portable apps/             My portable apps/Syllentra/
├── Syllentra.app             ├── Syllentra.exe (or Syllentra on Linux)
└── Syllentra Data/            ├── _internal/
                              └── Syllentra Data/
```

1. Copy the application to its final location outside `dist`, which subsequent builds replace.
2. Create `Syllentra Data` in the location shown above. You can do this while the app is open, including after its first use.
3. If you want to carry the downloaded model with the app, use **Back up model** to save it into the new folder before quitting.
4. Quit and relaunch Syllentra. Storage is selected at startup; creating the folder does not switch a running session.

An empty portable folder starts with fresh settings and no model selected. **Existing settings and models stay in their original location; nothing is moved or copied automatically.** In Settings, use **Use local model** to reference your existing model. To carry the model with the app, create a backup inside `Syllentra Data`, then select the resulting `model_phonon25_f25x1_48k_int6` folder with **Use local model**. You can create that backup before quitting the original session or after selecting the existing model in the portable session.

Move the application and `Syllentra Data` together. Model references inside that folder are stored relatively; references to models elsewhere still depend on those external locations. Session temporary files use the OS temporary directory.

Normal installations retain the **PyWhisper Studio** platform data directory for compatibility. `SYLLENTRA_DATA_DIR` overrides storage; `PYWHISPER_DATA_DIR` remains supported. Existing Whisper caches are unused and left intact. Legacy appearance settings receive a one-time backup when migrated settings are saved.

## Development

Use **Python 3.13**, **Node.js 22**, and **pnpm 12.3.4**.

```sh
pnpm initialize
pnpm dev:frontend
# In another terminal:
pnpm dev:backend
```

Initialization installs both JavaScript dependency trees and the target's hash-locked Python dependencies in `.venv`. Use `pnpm start` for the compiled frontend, or `pnpm build` for a native candidate in `dist/`. Building replaces `dist`, so keep portable user data elsewhere.

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
