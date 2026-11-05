# Python dependency locks

`node scripts/python.mjs initialize` selects the Python 3.13 target lock and installs it with pip `--require-hashes`. Locks include runtime and developer dependencies; PyInstaller determines what ships. Audit packages in a fresh environment because reused environments can retain obsolete dependencies.

| Lock | Target/status |
| --- | --- |
| `macos-arm64-py313.lock` | Locally validated macOS arm64 environment; current Torch/MLX wheels require macOS 14+. |
| `windows-x64-py313.lock` | Cross-resolved CPU candidate; native validation pending. |
| `linux-x64-py313.lock` | Cross-resolved CPU/PySide6 candidate; requires glibc 2.28+ and Qt system libraries; native validation pending. |

## Regeneration

Use `uv==0.9.5`. On macOS arm64:

```sh
MACOSX_DEPLOYMENT_TARGET=14.0 uv pip compile requirements-dev.txt --python-version 3.13 --generate-hashes --no-header --no-annotate --output-file requirements/macos-arm64-py313.lock
```

For Windows/Linux, use the appropriate target and output file:

```sh
uv pip compile requirements-dev.txt --python-version 3.13 --python-platform x86_64-pc-windows-msvc --torch-backend cpu --index https://download.pytorch.org/whl/cpu --generate-hashes --emit-index-url --no-header --no-annotate --output-file requirements/windows-x64-py313.lock
uv pip compile requirements-dev.txt --python-version 3.13 --python-platform x86_64-unknown-linux-gnu --torch-backend cpu --index https://download.pytorch.org/whl/cpu --generate-hashes --emit-index-url --no-header --no-annotate --output-file requirements/linux-x64-py313.lock
```

Keep the CPU index/backend to avoid selecting CUDA dependencies. Every accepted distribution remains hash constrained. Dependency updates require the [native offline probe](../backend/verify_runtime.py); cross-resolution alone proves dependency availability.
