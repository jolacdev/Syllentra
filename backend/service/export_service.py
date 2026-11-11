"""Plan collision-free output sets and commit each artifact without silent clobbering."""

import ntpath
import os
import stat
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from schemas.batch import (
    BatchPlan,
    ConflictAction,
    ExportFormat,
    ExportSettings,
    InferenceOutput,
    OutputArtifact,
    Workspace,
)
from utils.export_utils import render_output


def _key(path: Path) -> str:
    """Reserve paths conservatively across both case-sensitive and case-insensitive volumes."""
    return str(path.absolute()).casefold()


def _signature(path: Path, *, overwrite: bool = False) -> str | None:
    """Fingerprint an existing directory entry without following output symlinks."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if overwrite and (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise ValueError(f"Only regular output files without other links can be overwritten: {path}")
    return f"{info.st_dev}:{info.st_ino}:{info.st_mode}:{info.st_size}:{info.st_mtime_ns}:{info.st_nlink}"


def _check_parent(path: Path) -> None:
    """Reject non-directory destination ancestors before inference without creating output folders."""
    parent = path.parent
    if parent.resolve() != parent:
        raise ValueError(f"The output folder uses a linked or redirected path: {parent}")
    while not parent.exists() and not parent.is_symlink():
        parent = parent.parent
    if not parent.is_dir() or parent.is_symlink() or not os.access(parent, os.W_OK | os.X_OK):
        raise ValueError(f"The output folder is unavailable or not writable: {parent}")


def _output_name(stem: str, format: ExportFormat, subtitle_language: str | None) -> str:
    """Keep the language immediately before the subtitle extension, even on renamed copies."""
    language_suffix = f".{subtitle_language}" if subtitle_language and format != "txt" else ""
    return f"{stem}{language_suffix}.{format}"


class ExportService:
    """Keep deterministic preflight and independent artifact writes outside inference and dialogs."""

    def prepare(self, workspace: Workspace, settings: ExportSettings) -> BatchPlan:
        """Reserve every requested output, including collisions between distinct source files."""
        formats = settings["formats"]
        if (
            not formats
            or len(set(formats)) != len(formats)
            or any(f not in ("srt", "txt", "vtt") for f in formats)
        ):
            raise ValueError("Select at least one output format.")
        roots = {root["id"]: root for root in workspace["roots"]}
        plan: BatchPlan = {"id": uuid4().hex, "revision": workspace["revision"], "items": []}
        reserved: set[str] = set()
        for item in workspace["items"]:
            if not item["isIncluded"] or not item["isAvailable"]:
                continue
            source = Path(item["path"])
            reusable = item["resultId"] if item["errorStage"] == "export" else None
            if reusable is None:
                info = source.stat()
                if (
                    not source.is_file()
                    or info.st_size != item["size"]
                    or str(info.st_mtime_ns) != item["modifiedNs"]
                ):
                    raise ValueError(f"The source changed. Add it again before processing: {source}")
            destination = settings["destination"]
            parent = source.parent
            if destination is not None:
                root = roots[item["rootId"]]
                parent = Path(destination).resolve()
                if root["isFolder"]:
                    parent = parent / root["alias"] / Path(item["relativePath"]).parent
            stream_index = item["audio"]["selectedIndex"]
            subtitle_language = None
            if settings.get("includeAudioLanguage", False):
                subtitle_language = next(
                    (
                        track["language"]
                        for track in item["audio"]["tracks"]
                        if track["index"] == stream_index
                    ),
                    None,
                )
            stem = source.stem
            suffix = 2
            while any(
                _key(parent / _output_name(stem, format, subtitle_language)) in reserved for format in formats
            ):
                stem = f"{source.stem} ({suffix})"
                suffix += 1
            artifacts: list[OutputArtifact] = []
            for format in formats:
                target = parent / _output_name(stem, format, subtitle_language)
                _check_parent(target)
                signature = _signature(target)
                already_written = (
                    reusable is not None
                    and signature is not None
                    and any(
                        output["status"] == "written" and output["path"] == str(target)
                        for output in item["outputs"]
                    )
                )
                artifacts.append(
                    {
                        "id": uuid4().hex,
                        "format": format,
                        "path": str(target),
                        "action": "skip" if already_written else "ask" if signature is not None else "create",
                        "status": "written" if already_written else "planned",
                        "conflict": signature is not None,
                        "existingSignature": signature,
                        "error": None,
                    }
                )
                reserved.add(_key(target))
            plan["items"].append(
                {
                    "itemId": item["id"],
                    "sourcePath": str(source),
                    "size": item["size"],
                    "modifiedNs": item["modifiedNs"],
                    "resultId": reusable,
                    "outputs": artifacts,
                    "audioStreamIndex": stream_index,
                    "subtitleLanguage": subtitle_language,
                }
            )
        if not plan["items"]:
            raise ValueError("Include at least one available recording.")
        return plan

    def resolve(self, original: BatchPlan, artifact_ids: list[str], action: ConflictAction) -> BatchPlan:
        """Apply an explicit conflict decision and reserve one shared rename stem per source."""
        if action not in ("skip", "overwrite", "rename"):
            raise ValueError("Choose skip, overwrite, or rename for existing outputs.")
        plan = deepcopy(original)
        known = {output["id"] for item in plan["items"] for output in item["outputs"]}
        if not set(artifact_ids).issubset(known):
            raise ValueError("The output plan changed. Review conflicts again.")
        requested = set(artifact_ids)
        reserved = {_key(Path(output["path"])) for item in plan["items"] for output in item["outputs"]}
        for item in plan["items"]:
            affected = [output for output in item["outputs"] if output["id"] in requested]
            if not affected:
                continue
            if action == "rename":
                first = item["outputs"][0]
                path = Path(first["path"])
                language = item["subtitleLanguage"]
                base = path.name.removesuffix(_output_name("", first["format"], language))
                suffix = 2
                while True:
                    stem = f"{base} ({suffix})"
                    targets = [
                        path.with_name(_output_name(stem, output["format"], language))
                        for output in item["outputs"]
                    ]
                    if all(_key(target) not in reserved and _signature(target) is None for target in targets):
                        break
                    suffix += 1
                for output, target in zip(item["outputs"], targets, strict=True):
                    output.update(
                        {
                            "path": str(target),
                            "action": "rename",
                            "existingSignature": None,
                            "status": "planned",
                            "conflict": False,
                            "error": None,
                        }
                    )
                    reserved.add(_key(target))
            else:
                for output in affected:
                    path = Path(output["path"])
                    if action == "overwrite" and (
                        output["existingSignature"] is None
                        or _signature(path, overwrite=True) != output["existingSignature"]
                    ):
                        raise FileExistsError(f"The output changed after review: {path}")
                    output["action"] = action
        return plan

    def write(self, output: OutputArtifact, transcript: InferenceOutput) -> OutputArtifact:
        """Write one artifact atomically while preserving late conflicts and approved overwrite scope."""
        artifact = deepcopy(output)
        if artifact["status"] == "written":
            return artifact
        if artifact["action"] == "skip":
            artifact["status"] = "skipped"
            return artifact
        if artifact["action"] == "ask":
            raise ValueError("Resolve existing outputs before starting the batch.")
        target = Path(artifact["path"])
        if target.suffix != f".{artifact['format']}" or artifact["format"] not in ("srt", "txt", "vtt"):
            raise ValueError(f"Invalid subtitle output path: {target}")
        if os.name == "nt" and any(ntpath.isreserved(part) for part in target.parts[1:]):
            raise ValueError(f"Invalid Windows output path: {target}")
        _check_parent(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.parent.resolve() != target.parent:
            raise ValueError(f"The output folder changed after review: {target.parent}")
        content = render_output(transcript, artifact["format"])
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=target.parent, delete=False
            ) as handle:
                temporary = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            if artifact["action"] == "overwrite":
                signature = _signature(target, overwrite=True)
                if signature is None or signature != artifact["existingSignature"]:
                    raise FileExistsError(f"The output changed after review: {target}")
                temporary.replace(target)
            elif os.name == "nt":
                # Windows rename refuses an existing target, unlike POSIX rename.
                temporary.rename(target)
            else:
                # Linking on the same volume publishes complete bytes without overwriting a racing target.
                os.link(temporary, target)
            artifact["status"] = "written"
            artifact["error"] = None
            return artifact
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
