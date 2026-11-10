"""Protect recursive selection, path reservation, and safe artifact publication."""

import tempfile
import unittest
from pathlib import Path
from threading import Event

from schemas.batch import ExportSettings, InferenceOutput
from service.export_service import ExportService
from service.file_selection_service import FileSelectionService


def ignore_discovery(_path: str, _added: int, _ignored: int, _duplicates: int) -> None:
    """Discard progress when asserting the resulting collection directly."""


class BatchFilesTests(unittest.TestCase):
    """Test real temporary filesystem behavior without inference libraries."""

    def setUp(self) -> None:
        """Provide a nested source tree with duplicate output stems and an unsupported file."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.sources = self.root / "Series"
        self.child = self.sources / "Episode"
        self.child.mkdir(parents=True)
        (self.child / "interview.MP4").write_bytes(b"test media")
        (self.child / "interview.wav").write_bytes(b"other media")
        (self.sources / "notes.md").write_text("ignored")
        self.files = FileSelectionService()
        self.exports = ExportService()
        self.settings: ExportSettings = {
            "formats": ["srt", "txt"],
            "destination": None,
            "includeAudioLanguage": False,
        }
        self.result: InferenceOutput = {
            "text": "A <local> recording.",
            "duration": 2.0,
            "language": None,
            "segments": [{"id": 0, "start": 0.0, "end": 1.5, "text": "A <local> recording."}],
        }

    def _scan(self, *paths: Path) -> None:
        """Import source references through the same scanner used by picker and native drop."""
        self.files.scan([str(path) for path in paths], Event(), ignore_discovery)

    def test_overlapping_roots_preserve_ids_and_manual_selection(self) -> None:
        """Adding an ancestor must merge the tree without duplicating or reselecting a leaf."""
        self._scan(self.child)
        first = self.files.snapshot()["items"][0]
        self.files.include([first["id"]], False)
        self._scan(self.sources)
        workspace = self.files.snapshot()
        self.assertEqual(len(workspace["items"]), 2)
        self.assertEqual(len(workspace["roots"]), 1)
        self.assertEqual(workspace["roots"][0]["path"], str(self.sources))
        self.assertFalse(self.files.get(first["id"])["isIncluded"])
        self.assertEqual(self.files.get(first["id"])["relativePath"], "Episode/interview.MP4")

    def test_directory_links_are_not_traversed(self) -> None:
        """A recursive link must not duplicate files or keep discovery running indefinitely."""
        (self.child / "cycle").symlink_to(self.sources, target_is_directory=True)
        self._scan(self.sources)
        self.assertEqual(len(self.files.snapshot()["items"]), 2)

    def test_zero_byte_media_is_visible_but_not_included(self) -> None:
        """Unavailable supported media must have a reason rather than silently disappearing."""
        empty = self.sources / "empty.mp3"
        empty.touch()
        self._scan(empty)
        item = self.files.snapshot()["items"][0]
        self.assertFalse(item["isAvailable"])
        self.assertFalse(item["isIncluded"])
        self.assertIsNotNone(item["error"])

    def test_same_stem_sources_never_reserve_the_same_output(self) -> None:
        """Distinct media extensions must not overwrite another item in the same batch."""
        self._scan(self.sources)
        plan = self.exports.prepare(self.files.snapshot(), self.settings)
        outputs = [output["path"] for item in plan["items"] for output in item["outputs"]]
        self.assertEqual(len(set(outputs)), 4)
        self.assertTrue(any("interview (2).srt" in path for path in outputs))
        self.assertFalse(any(Path(path).exists() for path in outputs))

    def test_custom_destination_preserves_imported_hierarchy(self) -> None:
        """Folder exports must preserve source provenance without creating directories during preflight."""
        self._scan(self.sources)
        destination = self.root / "Exports"
        plan = self.exports.prepare(self.files.snapshot(), {**self.settings, "destination": str(destination)})
        self.assertEqual(
            Path(plan["items"][0]["outputs"][0]["path"]).parent, destination / "Series" / "Episode"
        )
        self.assertFalse(destination.exists())

    def test_skip_is_per_artifact_and_rename_keeps_formats_together(self) -> None:
        """Existing subtitles must not suppress a missing text export or split a renamed set."""
        self._scan(self.child / "interview.wav")
        existing = self.child / "interview.srt"
        existing.write_text("original")
        plan = self.exports.prepare(self.files.snapshot(), self.settings)
        artifact = plan["items"][0]["outputs"][0]
        skipped = self.exports.resolve(plan, [artifact["id"]], "skip")
        self.assertEqual(skipped["items"][0]["outputs"][1]["action"], "create")
        self.assertEqual(
            self.exports.write(skipped["items"][0]["outputs"][0], self.result)["status"], "skipped"
        )
        renamed = self.exports.resolve(plan, [artifact["id"]], "rename")
        self.assertEqual(
            {Path(output["path"]).stem for output in renamed["items"][0]["outputs"]}, {"interview (2)"}
        )
        self.assertEqual(existing.read_text(), "original")

    def test_racing_output_is_never_overwritten(self) -> None:
        """An output created after preflight must survive a no-clobber commit attempt."""
        self._scan(self.child / "interview.wav")
        output = self.exports.prepare(self.files.snapshot(), self.settings)["items"][0]["outputs"][0]
        target = Path(output["path"])
        target.write_text("other application")
        with self.assertRaises(FileExistsError):
            self.exports.write(output, self.result)
        self.assertEqual(target.read_text(), "other application")
        self.assertEqual(
            sorted(path.name for path in self.child.iterdir()),
            ["interview.MP4", "interview.srt", "interview.wav"],
        )

    def test_explicit_overwrite_rechecks_the_reviewed_target(self) -> None:
        """Changing an approved output after review requires another explicit decision."""
        self._scan(self.child / "interview.wav")
        target = self.child / "interview.srt"
        target.write_text("original")
        plan = self.exports.prepare(self.files.snapshot(), self.settings)
        output = plan["items"][0]["outputs"][0]
        approved = self.exports.resolve(plan, [output["id"]], "overwrite")["items"][0]["outputs"][0]
        self.exports.write(approved, self.result)
        self.assertIn("00:00:00,000 --> 00:00:01,500", target.read_text())
        with self.assertRaises(FileExistsError):
            self.exports.write(approved, self.result)

    def test_changed_source_invalidates_preflight(self) -> None:
        """A source fingerprint change must require refreshed metadata before inference."""
        source = self.child / "interview.wav"
        self._scan(source)
        source.write_bytes(b"changed recording")
        with self.assertRaisesRegex(ValueError, "source changed"):
            self.exports.prepare(self.files.snapshot(), self.settings)

    def test_incremental_rows_and_structural_reset(self) -> None:
        """Progress transport must send changed rows and recover snapshots after structural changes."""
        self._scan(self.sources)
        initial = self.files.changes(-1)
        item = initial["items"][0]
        self.files.replace({**item, "status": "transcribing"})
        changed = self.files.changes(initial["revision"])
        self.assertFalse(changed["reset"])
        self.assertEqual(len(changed["items"]), 1)
        self.assertEqual(changed["items"][0]["status"], "transcribing")
        self.files.clear()
        self.assertTrue(self.files.changes(changed["revision"])["reset"])
        self.assertEqual(self.files.changes(changed["revision"])["items"], [])

    def test_reimport_refreshes_changed_source_without_reselecting(self) -> None:
        """Reimport must refresh stale metadata while retaining exclusion and identity."""
        source = self.child / "interview.wav"
        self._scan(source)
        before = self.files.snapshot()["items"][0]
        self.files.include([before["id"]], False)
        source.write_bytes(b"replacement source recording")
        self._scan(source)
        after = self.files.get(before["id"])
        self.assertEqual(after["size"], source.stat().st_size)
        self.assertFalse(after["isIncluded"])
        self.assertEqual(len(self.files.snapshot()["items"]), 1)
