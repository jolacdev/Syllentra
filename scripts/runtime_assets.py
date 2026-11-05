"""Collect the platform-specific assets required by the pinned Fermion speech runtime."""

import platform
import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

Asset = tuple[str, str]
NATIVE_SUFFIXES = {".so", ".dll", ".dylib", ".exe"}


def is_python_module(name: str) -> bool:
    """Exclude foreign native libraries that module discovery mistakes for extension modules."""
    return not name.rsplit(".", 1)[-1].startswith("lib")


def is_platform_library(path: str) -> bool:
    """Select only native speech libraries for the executable's operating system and architecture."""
    machine = platform.machine().lower()
    if sys.platform == "darwin":
        return f"-macos-{machine}" in Path(path).name
    if sys.platform == "win32":
        return "-windows-x64" in Path(path).name and machine in ("amd64", "x86_64")
    architecture = "aarch64" if machine in ("aarch64", "arm64") else "x86_64"
    return f"-linux-{architecture}" in Path(path).name


def collect_phonon_assets() -> tuple[list[Asset], list[Asset], list[str]]:
    """Preserve dynamic source loading and checksum sidecars without collecting foreign binaries."""
    data: list[Asset] = [
        (source, target)
        for source, target in collect_data_files("fermion", include_py_files=True)
        if Path(source).suffix not in NATIVE_SUFFIXES
    ]
    data += copy_metadata("fermion-research", recursive=True)
    binaries: list[Asset] = [
        (source, target) for source, target in collect_dynamic_libs("fermion") if is_platform_library(source)
    ]
    hidden: list[str] = collect_submodules("fermion._speech", filter=is_python_module)
    if sys.platform == "darwin" and platform.machine() == "arm64":
        # MLX's extension imports Python helpers, and mlx-audio discovers registry kinds on disk.
        data += collect_data_files("mlx", include_py_files=True, excludes=["**/*.so", "**/*.dylib"])
        data += collect_data_files("mlx_audio", include_py_files=True)
        binaries += collect_dynamic_libs("mlx")
        hidden += [
            "mlx_audio.stt.models.parakeet",
            "mlx_audio.stt.models.parakeet.tokenizer",
            "mlx_audio.stt.models.parakeet.attention",
        ]
    return data, binaries, hidden
