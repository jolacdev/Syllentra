import os
import sys
from typing import cast

import webview

if sys.platform == "darwin":
    from AppKit import NSWindow, NSWindowTabbingModeDisallowed, NSWindowTitleHidden


def configure_native_window(window: webview.Window) -> None:
    """Keep macOS window controls native and show branding only in the application sidebar."""
    if sys.platform == "darwin":
        # Run before_show on Cocoa's main thread; avoid duplicate or clipped native title/tab labels.
        native = cast(NSWindow, window.native)
        native.setTabbingMode_(NSWindowTabbingModeDisallowed)
        native.setTitleVisibility_(NSWindowTitleHidden)


def is_running_bundled() -> bool:
    """Return True if running inside a PyInstaller bundle, False otherwise."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_frontend_entrypoint(backend_dir_path: str) -> str:
    """Return the frontend entrypoint depending on context."""

    live_server = os.getenv("LIVE_SERVER", "0") == "1"
    if live_server:
        return "http://localhost:3000"

    paths = (
        "../frontend_dist/index.html",  # Development build (not frozen): Compiled but not bundled.
        "../Resources/frontend_dist/index.html",  # macOS executable (frozen): Bundled via PyInstaller.
        "./frontend_dist/index.html",  # Windows: extracted by PyInstaller.
    )

    for rel_path in paths:
        frontend_entrypoint_path = os.path.join(backend_dir_path, rel_path)
        if os.path.exists(frontend_entrypoint_path):
            return os.path.abspath(frontend_entrypoint_path)

    raise Exception("No index.html found")
