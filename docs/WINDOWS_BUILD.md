# Windows builds

Build locally on Windows x64. [PyInstaller builds for its host OS](https://pyinstaller.org/en/stable/operating-mode.html); a macOS build does not produce a Windows executable.

## Local build

Install **64-bit Python 3.13**, **Node.js 22**, and **pnpm 12.3.4**, with Python and Node on PATH. Obtain the repository through Git or a source ZIP, then run in PowerShell:

```powershell
npm install --global pnpm@12.3.4
pnpm initialize
pnpm build
```

Run the [source checks](../README.md#checks) before distributing. Initialization needs internet access and installs the Windows CPU dependency lock into `.venv`. Prebuilt wheels/bootloader support the normal build without a compiler.

Distribute the **entire `dist\Syllentra` folder**, containing `Syllentra.exe` and `_internal`. It is a folder candidate, not an installer. Recipients do not need Python, Node, pnpm, or an external FFmpeg command.

## Runtime and offline use

Recipients need pywebview's [.NET Framework and WebView2 prerequisites](https://github.com/r0x0r/pywebview/blob/master/docs/guide/installation.md). Microsoft's [WebView2 distribution guide](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution) covers offline installers for machines without the runtime.

Move the application folder out of `dist` before first use. **Syllentra Data** is created automatically next to the application. Move the entire folder when transferring the app; exclude personal data when distributing a fresh copy.

For offline first use, transfer the verified model folder and select it with **Import local model**. See [portable storage](../README.md#portable-by-default).

## GitHub Actions

The [validation workflow](../.github/workflows/validate.yml) runs source checks and builds the web frontend on Windows, macOS, and Linux, without packaging or uploading application bundles. Use the local build steps above to produce the Windows application.

Windows native execution and distribution signing remain release requirements; defining or passing source checks does not certify the package.
