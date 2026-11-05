"""Discover local source trees and maintain one canonical inclusion model."""

import os
from collections import deque
from collections.abc import Callable, Iterator
from copy import deepcopy
from pathlib import Path
from threading import Event, RLock
from uuid import uuid4

from schemas.batch import MediaItem, SourceRoot, Workspace, WorkspaceDelta
from utils.media_utils import is_media_file

DiscoveryCallback = Callable[[str, int, int, int], None]


class FileSelectionService:
    """Own source identities and selection without dialogs, engines, or output decisions."""

    def __init__(self) -> None:
        """Initialize a session-local collection with no filesystem side effects."""
        self._lock = RLock()
        self._roots: dict[str, SourceRoot] = {}
        self._items: dict[str, MediaItem] = {}
        self._identities: dict[tuple[int, int], str] = {}
        self._item_identities: dict[str, tuple[int, int]] = {}
        self._paths: dict[str, str] = {}
        self._revision = 0
        self._changes: deque[tuple[int, str | None]] = deque(maxlen=4096)

    def _changed(self, item_id: str | None) -> None:
        """Record a bounded row change or structural reset without copying the collection."""
        self._revision += 1
        self._changes.append((self._revision, item_id))

    @property
    def revision(self) -> int:
        """Read collection freshness without copying every source item on progress ticks."""
        with self._lock:
            return self._revision

    def snapshot(self) -> Workspace:
        """Return an immutable-by-ownership copy for serialization and preflight."""
        with self._lock:
            workspace: Workspace = {
                "revision": self._revision,
                "roots": list(self._roots.values()),
                "items": list(self._items.values()),
            }
            return deepcopy(workspace)

    def changes(self, after_revision: int) -> WorkspaceDelta:
        """Fetch bounded row changes while retaining a full-snapshot recovery path for reloads."""
        with self._lock:
            changes = [
                (revision, item_id) for revision, item_id in self._changes if revision > after_revision
            ]
            reset = after_revision < 0 or after_revision > self._revision
            if self._changes and after_revision < self._changes[0][0] - 1:
                reset = True
            if any(item_id is None for _revision, item_id in changes):
                reset = True
            if reset:
                return {**self.snapshot(), "reset": True}
            ids = {item_id for _revision, item_id in changes if item_id is not None}
            return {
                "revision": self._revision,
                "reset": False,
                "roots": [],
                "items": deepcopy([item for key, item in self._items.items() if key in ids]),
            }

    def get(self, item_id: str) -> MediaItem:
        """Resolve a known source without exposing mutable internal dictionaries."""
        with self._lock:
            if item_id not in self._items:
                raise ValueError("The selected recording is no longer available.")
            return deepcopy(self._items[item_id])

    def replace(self, item: MediaItem) -> None:
        """Update a known item's lifecycle while retaining its stable identity."""
        with self._lock:
            if item["id"] not in self._items:
                raise ValueError("The selected recording is no longer available.")
            self._items[item["id"]] = deepcopy(item)
            self._changed(item["id"])

    def include(self, item_ids: list[str], included: bool) -> None:
        """Apply one explicit inclusion choice to known eligible leaves."""
        with self._lock:
            if any(item_id not in self._items for item_id in item_ids):
                raise ValueError("The file selection changed. Review the collection and try again.")
            for item_id in item_ids:
                item = self._items[item_id]
                item["isIncluded"] = included and item["isAvailable"]
            self._changed(None)

    def clear(self) -> None:
        """Discard session references without deleting recordings or generated files."""
        with self._lock:
            self._roots.clear()
            self._items.clear()
            self._identities.clear()
            self._item_identities.clear()
            self._paths.clear()
            self._changed(None)

    def _root(self, path: Path, folder: bool) -> SourceRoot:
        """Merge overlapping imports under their outermost explicitly imported folder."""
        directory = path if folder else path.parent
        with self._lock:
            for candidate in self._roots.values():
                if candidate["isFolder"] and directory.is_relative_to(candidate["path"]):
                    return candidate
            existing = next((root for root in self._roots.values() if root["path"] == str(directory)), None)
            names = {root["alias"].casefold() for root in self._roots.values()}
            alias = directory.name or str(directory)
            suffix = 2
            while alias.casefold() in names and existing is None:
                alias = f"{directory.name} ({suffix})"
                suffix += 1
            root: SourceRoot = existing or {
                "id": uuid4().hex,
                "path": str(directory),
                "name": directory.name or str(directory),
                "alias": alias,
                "isFolder": folder,
            }
            root["isFolder"] = root["isFolder"] or folder
            self._roots[root["id"]] = root
            if folder:
                for item in self._items.values():
                    source = Path(item["path"])
                    if source.is_relative_to(directory):
                        item["rootId"] = root["id"]
                        item["relativePath"] = source.relative_to(directory).as_posix()
                used = {item["rootId"] for item in self._items.values()}
                self._roots = {
                    key: value
                    for key, value in self._roots.items()
                    if key == root["id"] or key in used or not Path(value["path"]).is_relative_to(directory)
                }
            self._changed(None)
            return root

    def _walk(self, source: Path, cancel: Event) -> Iterator[Path]:
        """Visit folders deterministically without following links or blocking cancellation."""
        pending = [source]
        while pending and not cancel.is_set():
            path = pending.pop()
            yield path
            if path.is_symlink() or path.is_junction():
                continue
            if path.is_dir():
                try:
                    entries = sorted(
                        path.iterdir(), key=lambda item: (item.name.casefold(), item.name), reverse=True
                    )
                except OSError:
                    continue
                pending.extend(entries)

    def scan(self, paths: list[str], cancel: Event, report: DiscoveryCallback) -> None:
        """Add discovered media incrementally and report ignored, duplicate, and unavailable entries."""
        added = ignored = duplicates = 0
        for value in paths:
            if cancel.is_set():
                break
            source = Path(value).expanduser().absolute()
            if source.is_symlink() or source.is_junction():
                ignored += 1
                report(str(source), added, ignored, duplicates)
                continue
            source = source.resolve()
            root = self._root(source, source.is_dir())
            for path in self._walk(source, cancel):
                if path.is_symlink() or path.is_junction():
                    ignored += 1
                elif path.is_dir():
                    if not os.access(path, os.R_OK | os.X_OK):
                        ignored += 1
                elif is_media_file(str(path)):
                    if self._add(path, root):
                        added += 1
                    else:
                        duplicates += 1
                else:
                    ignored += 1
                report(str(path), added, ignored, duplicates)

    def _add(self, path: Path, root: SourceRoot) -> bool:
        """Deduplicate file identities and preserve unavailable supported sources for review."""
        canonical = path.resolve()
        key = os.path.normcase(str(canonical))
        size = modified = 0
        error = None
        identity = None
        try:
            metadata = canonical.stat()
            identity = (metadata.st_dev, metadata.st_ino) if metadata.st_ino else None
            size, modified = metadata.st_size, metadata.st_mtime_ns
            if not canonical.is_file() or not os.access(canonical, os.R_OK) or size == 0:
                error = "This recording is empty or unreadable."
        except OSError:
            error = "This recording is missing or unreadable."
        with self._lock:
            known_id = self._paths.get(key) or (
                self._identities.get(identity) if identity is not None else None
            )
            if known_id is not None:
                self._paths[key] = known_id
                self._refresh(known_id, canonical, (size, modified), error, identity)
                return False
            item: MediaItem = {
                "id": uuid4().hex,
                "rootId": root["id"],
                "path": str(canonical),
                "name": path.name,
                "relativePath": path.relative_to(root["path"]).as_posix(),
                "extension": path.suffix.lower(),
                "size": size,
                "modifiedNs": str(modified),
                "isIncluded": error is None,
                "isAvailable": error is None,
                "status": "ready",
                "error": error,
                "errorStage": "source" if error else None,
                "resultId": None,
                "noSpeech": False,
                "outputs": [],
            }
            self._paths[key] = item["id"]
            if identity is not None:
                self._identities[identity] = item["id"]
                self._item_identities[item["id"]] = identity
            self._items[item["id"]] = item
            self._changed(item["id"])
            return True

    def _refresh(
        self,
        item_id: str,
        path: Path,
        fingerprint: tuple[int, int],
        error: str | None,
        identity: tuple[int, int] | None,
    ) -> None:
        """Revalidate explicitly re-added sources while preserving stable IDs and intentional exclusions."""
        size, modified = fingerprint
        item = self._items[item_id]
        if item["path"] != str(path):
            return
        if (item["size"], item["modifiedNs"], item["isAvailable"]) == (size, str(modified), error is None):
            return
        was_available = item["isAvailable"]
        item.update(
            {
                "size": size,
                "modifiedNs": str(modified),
                "isAvailable": error is None,
                "isIncluded": error is None and (item["isIncluded"] or not was_available),
                "status": "ready",
                "error": error,
                "errorStage": "source" if error else None,
                "resultId": None,
                "outputs": [],
                "noSpeech": False,
            }
        )
        previous = self._item_identities.pop(item_id, None)
        if previous is not None:
            self._identities.pop(previous, None)
        if identity is not None:
            self._identities[identity] = item_id
            self._item_identities[item_id] = identity
        self._changed(item_id)
