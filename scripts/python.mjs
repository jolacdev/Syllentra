import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import os from "node:os";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const isWindows = process.platform === "win32";
const python = path.join(
  root,
  ".venv",
  isWindows ? "Scripts/python.exe" : "bin/python",
);

/** Pass literal argument arrays so paths with spaces never require a shell. */
const run = (command, args) => {
  const result = spawnSync(command, args, {
    cwd: root,
    stdio: "inherit",
    env: { ...process.env, PYTHONUTF8: "1", PYTHONPATH: path.join(root, "backend") },
  });
  if (result.error) {
    console.error(result.error.message);
  }
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
};

const versionCheck = [
  "-c",
  'import sys; sys.exit("Python 3.13 is required by the target dependency locks.") if sys.version_info[:2] != (3, 13) else None',
];
const action = process.argv[2];
if (action === "initialize") {
  // Reuse the project's interpreter when the system command points to another version.
  if (!existsSync(python)) {
    const systemPython = process.env.PYTHON ?? (isWindows ? "python" : "python3");
    run(systemPython, versionCheck);
    run(systemPython, ["-m", "venv", ".venv"]);
  }
  run(python, versionCheck);
  const targets = {
    "darwin-arm64": "macos-arm64-py313.lock",
    "win32-x64": "windows-x64-py313.lock",
    "linux-x64": "linux-x64-py313.lock",
  };
  const lock = targets[`${process.platform}-${os.arch()}`];
  if (!lock) {
    throw new Error("Supported development targets: macOS arm64, Windows x64, Linux x64.");
  }
  run(python, ["-m", "pip", "install", "--require-hashes", "-r", `requirements/${lock}`]);
} else {
  const commands = {
    backend: ["backend/main.py"],
    lint: ["-m", "ruff", "check", "--config", "backend/pyproject.toml", "backend", "scripts/runtime_assets.py"],
    format: ["-m", "ruff", "format", "--check", "--config", "backend/pyproject.toml", "backend", "scripts/runtime_assets.py"],
    types: ["-m", "mypy", "--config-file", "backend/pyproject.toml", "backend", "scripts/runtime_assets.py"],
    test: ["-m", "unittest", "discover", "-s", "backend/tests"],
    generate: ["scripts/generate_api.py"],
    check: ["scripts/generate_api.py", "--check"],
    package: ["-m", "PyInstaller", "--noconfirm", "pyinstaller/pywebview-react.spec"],
  };
  if (!commands[action]) {
    throw new Error(`Unknown Python action: ${action}`);
  }
  run(python, versionCheck);
  run(python, commands[action]);
}
