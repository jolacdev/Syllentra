"""Exercise real multi-track containers, deterministic selection, and batch plan ownership."""

import tempfile
import unittest
from collections import Counter
from pathlib import Path
from shutil import copyfile
from threading import Event
from unittest.mock import patch

import av
import numpy as np

from schemas.batch import AudioSelection, InferenceOutput
from service.export_service import ExportService
from service.file_selection_service import FileSelectionService
from service.phonon_service import PhononEngine
from service.preferences_service import PreferencesService
from service.transcription_service import TranscriptionService
from utils.audio_tracks import inspect_audio, resolve_audio
from utils.audio_utils import prepare_audio
from utils.language_utils import normalize_language


def make_container(
    source: Path, languages: list[str], default: int | None = 0, modern: list[str | None] | None = None
) -> None:
    """Mux a video stream before distinguishable audio tracks to expose audio/stream index mistakes."""
    with av.open(str(source), "w", format="matroska", options={"write_crc32": "0"}) as output:
        video = output.add_stream("ffv1", rate=1)
        video.width = video.height = 16
        video.pix_fmt = "yuv420p"
        streams = []
        for index, language in enumerate(languages):
            stream = output.add_stream("pcm_s16le", rate=16_000)
            stream.layout = "mono"
            stream.metadata["language"] = language
            tag = modern[index] if modern else None
            if tag is not None:
                stream.metadata["title"] = " " * (len(tag) + 1)
            stream.disposition = (
                av.stream.Disposition.default if index == default else av.stream.Disposition(0)
            )
            streams.append(stream)
        image = av.VideoFrame.from_ndarray(np.zeros((16, 16, 3), dtype=np.uint8), format="rgb24")
        image.pts = 0
        for packet in video.encode(image):
            output.mux(packet)
        for packet in video.encode(None):
            output.mux(packet)
        for index, stream in enumerate(streams):
            data = np.full((1, 1600), (index + 1) * 1000, dtype=np.int16)
            frame = av.AudioFrame.from_ndarray(data, format="s16", layout="mono")
            frame.sample_rate = 16_000
            # Keep an offset against video time zero to test subtitle timeline preservation.
            frame.pts = 4000
            for packet in stream.encode(frame):
                output.mux(packet)
            for packet in stream.encode(None):
                output.mux(packet)

    if modern:
        encoded = source.read_bytes()
        for tag in modern:
            if tag is not None:
                # Replace a reserved Name element with the actual LanguageBCP47 element of equal length.
                old = bytes.fromhex("536e") + bytes([0x80 | (len(tag) + 1)]) + b" " * (len(tag) + 1)
                new = bytes.fromhex("22b59d") + bytes([0x80 | len(tag)]) + tag.encode("ascii")
                assert old in encoded
                encoded = encoded.replace(old, new, 1)
        source.write_bytes(encoded)


class AudioTrackTests(unittest.TestCase):
    """Verify selection against actual PyAV headers and samples without loading a speech model."""

    def setUp(self) -> None:
        """Create isolated media and exports for every selection scenario."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "Episode.mkv"

    def test_matches_standard_codes_and_tags_only(self) -> None:
        """Match ISO aliases and regional/extended tags without interpreting names or titles."""
        for label in ("en", "eng", "ENG", "EN-us", "en-Latn-US", "en-US-u-ca-gregory", "en-x-private"):
            with self.subTest(label=label):
                self.assertEqual(normalize_language(label), "en")
        for label in ("deu", "ger"):
            self.assertEqual(normalize_language(label), "de")
        for unknown_label in (
            None,
            "und",
            "mul",
            "zxx",
            "",
            "English",
            "Deutsch",
            "en_GB",
            "English commentary",
            "not-a-language",
        ):
            self.assertIsNone(normalize_language(unknown_label))

    def test_decodes_selected_track_using_actual_stream_index_and_timeline(self) -> None:
        """English audio track two is stream two when a video stream precedes it."""
        make_container(self.source, ["spa", "eng"])
        selection = inspect_audio(self.source, "en")
        self.assertEqual(selection["reason"], "preferred")
        self.assertEqual(selection["selectedIndex"], 2)
        self.assertEqual([track["number"] for track in selection["tracks"]], [1, 2])
        with prepare_audio(
            self.source, self.root / "work", Event(), lambda _: None, selection["selectedIndex"]
        ) as audio:
            samples = np.fromfile(audio.path, dtype=np.float32)
            self.assertEqual(audio.stream_index, 2)
            self.assertEqual(audio.samples, 5600)
            np.testing.assert_array_equal(samples[:4000], 0)
            np.testing.assert_allclose(samples[4000:], 2000 / 32768)
        self.assertFalse(audio.path.exists())

    def test_modern_language_overrides_conflicting_legacy_language(self) -> None:
        """The real LanguageBCP47 element takes priority even when FFmpeg exposes only the legacy tag."""
        make_container(self.source, ["eng", "spa"], modern=["es-ES", "en-US"])
        selection = inspect_audio(self.source, "en")
        self.assertEqual(selection["selectedIndex"], 2)
        self.assertEqual([track["rawLanguage"] for track in selection["tracks"]], ["es-ES", "en-US"])
        self.assertEqual([track["language"] for track in selection["tracks"]], ["es", "en"])

    def test_spanish_regions_match_one_simple_language_preference(self) -> None:
        """Regional variants are shown but do not add regional ranking or another user setting."""
        make_container(self.source, ["spa", "spa"], default=1, modern=["es-ES", "es-419"])
        selection = inspect_audio(self.source, "es")
        self.assertEqual(selection["selectedIndex"], 2)
        self.assertEqual(selection["reason"], "preferred")
        self.assertEqual([track["rawLanguage"] for track in selection["tracks"]], ["es-ES", "es-419"])
        make_container(self.source, ["spa", "spa"], default=None, modern=["es", "es"])
        self.assertEqual(inspect_audio(self.source, "es")["selectedIndex"], 1)

    def test_malformed_modern_tag_does_not_fall_back_to_legacy_language(self) -> None:
        """Reject names in modern metadata without substituting the conflicting legacy language."""
        make_container(self.source, ["eng", "spa"], modern=["English", None])
        selection = inspect_audio(self.source, "en")
        self.assertIsNone(selection["tracks"][0]["language"])
        self.assertEqual(selection["reason"], "fallback")

    def test_single_track_ignores_english_preference(self) -> None:
        """Unrelated single-track recordings must remain included in their own language."""
        make_container(self.source, ["spa"])
        selection = inspect_audio(self.source, "en")
        self.assertEqual(selection["reason"], "single")
        self.assertEqual(selection["selectedIndex"], 1)
        self.assertEqual(selection["tracks"][0]["language"], "es")

    def test_default_and_unmatched_fallback_are_distinct(self) -> None:
        """Unknown or absent preferred languages must preserve the default, with no per-file interruption."""
        make_container(self.source, ["fra", "deu"], default=1)
        for preference, reason in ((None, "default"), ("en", "fallback")):
            selection = inspect_audio(self.source, preference)
            self.assertEqual(selection["selectedIndex"], 2)
            self.assertEqual(selection["reason"], reason)
        make_container(self.source, ["und", "und"], default=None)
        self.assertEqual(inspect_audio(self.source, "en")["selectedIndex"], 1)

    def test_matching_dialogue_beats_default_commentary_and_description(self) -> None:
        """Role flags outrank default flags, with deterministic default/ordinal tie breaking."""
        make_container(self.source, ["eng", "eng", "eng"])
        selection = inspect_audio(self.source, "en")
        selection["tracks"][0]["isCommentary"] = True
        selection["tracks"][1]["isAudioDescription"] = True
        self.assertEqual(resolve_audio(selection, "en")["selectedIndex"], 3)
        selection["tracks"][1]["isAudioDescription"] = False
        self.assertEqual(resolve_audio(selection, "en")["selectedIndex"], 2)
        selection["tracks"][2]["isDefault"] = True
        self.assertEqual(resolve_audio(selection, "en")["selectedIndex"], 3)

    def test_missing_selected_stream_never_silently_decodes_another(self) -> None:
        """A stale stream or video stream index must fail while removing normalized temporary audio."""
        make_container(self.source, ["spa", "eng"])
        for index in (0, 42):
            with (
                self.assertRaisesRegex(ValueError, "selected audio track"),
                prepare_audio(self.source, self.root / "work", Event(), lambda _: None, index),
            ):
                self.fail("An unavailable selected audio stream must not be replaced")
        self.assertEqual(list((self.root / "work").iterdir()), [])

    def test_override_and_preference_invalidate_only_changed_transcripts(self) -> None:
        """Export retries must never reuse another track, while unchanged effective choices retain speech."""
        make_container(self.source, ["spa", "eng"])
        files = FileSelectionService()
        files.scan([str(self.source)], Event(), lambda *_: None)
        item = files.snapshot()["items"][0]
        item.update({"resultId": "retained", "errorStage": "export"})
        files.replace(item)
        revision = files.revision
        files.select_audio_track(item["id"], 1)
        self.assertEqual(files.revision, revision + 1)
        self.assertEqual(files.get(item["id"])["resultId"], "retained")
        files.select_audio_track(item["id"], 1)
        self.assertEqual(files.revision, revision + 1)
        files.set_audio_language("en")
        self.assertEqual(files.revision, revision + 1)
        self.assertEqual(files.get(item["id"])["audio"]["selectedIndex"], 1)
        files.select_audio_track(item["id"], None)
        self.assertEqual(files.revision, revision + 2)
        updated = files.get(item["id"])
        self.assertIsNone(updated["resultId"])
        self.assertEqual(updated["audio"]["selectedIndex"], 2)
        plan = ExportService().prepare(
            files.snapshot(), {"formats": ["srt"], "destination": None, "includeAudioLanguage": False}
        )
        self.assertEqual(plan["items"][0]["audioStreamIndex"], 2)
        with self.assertRaises(ValueError):
            files.select_audio_track(item["id"], 0)

    def test_reimport_refreshes_tracks_and_removes_obsolete_override(self) -> None:
        """Replacing source media must discard stream identities from its previous container."""
        make_container(self.source, ["spa", "eng"])
        files = FileSelectionService("en")
        files.scan([str(self.source)], Event(), lambda *_: None)
        item = files.snapshot()["items"][0]
        files.select_audio_track(item["id"], 2)
        make_container(self.source, ["fra"])
        files.scan([str(self.source)], Event(), lambda *_: None)
        audio = files.get(item["id"])["audio"]
        self.assertEqual(audio["selectedIndex"], 1)
        self.assertIsNone(audio["overrideIndex"])

    def test_preference_survives_restart_and_legacy_settings_default_to_off(self) -> None:
        """The additive preference must preserve existing appearance choices and normalize saved aliases."""
        preferences = PreferencesService(self.root)
        preferences.path.write_text('{"version":2,"theme":"dark","interfaceLanguage":"es-ES"}')
        settings, _ = preferences.read()
        self.assertIsNone(settings["preferredAudioLanguage"])
        settings["preferredAudioLanguage"] = "eng"
        preferences.write(settings)
        restored, _ = preferences.read()
        self.assertEqual(restored["preferredAudioLanguage"], "en")
        self.assertEqual(restored["theme"], "dark")

    def test_corrupt_media_is_reported_without_aborting_import(self) -> None:
        """An unreadable container must remain a per-file diagnostic rather than stop a large batch scan."""
        self.source.write_bytes(b"corrupt media")
        selection: AudioSelection = inspect_audio(self.source, "en")
        self.assertEqual(selection["reason"], "unavailable")
        self.assertIsNotNone(selection["probeError"])

    def test_500_mixed_files_resolve_independently_without_filtering(self) -> None:
        """A large mixed batch must preserve single tracks and resolve each file's metadata independently."""
        cases = [
            (["spa"], 0),
            (["spa", "eng"], 0),
            (["eng", "spa"], 1),
            (["fra", "deu"], 1),
            (["und", "und"], None),
        ]
        templates = []
        for index, (languages, default) in enumerate(cases):
            source = self.root / f"template-{index}.mkv"
            make_container(source, languages, default)
            templates.append(source)
        batch = self.root / "Batch"
        batch.mkdir()
        for index in range(500):
            copyfile(templates[index % len(cases)], batch / f"file-{index:03}.mkv")
        files = FileSelectionService("en")
        files.scan([str(batch)], Event(), lambda *_: None)
        workspace = files.snapshot()
        self.assertEqual(len(workspace["items"]), 500)
        self.assertTrue(all(item["isIncluded"] for item in workspace["items"]))
        self.assertEqual(
            Counter(item["audio"]["reason"] for item in workspace["items"]),
            {"single": 100, "preferred": 200, "fallback": 200},
        )
        plan = ExportService().prepare(
            workspace, {"formats": ["srt"], "destination": None, "includeAudioLanguage": True}
        )
        self.assertEqual(len(plan["items"]), 500)
        self.assertEqual([item["audioStreamIndex"] for item in plan["items"]], [1, 2, 1, 2, 1] * 100)
        self.assertEqual(
            [Path(item["outputs"][0]["path"]).name for item in plan["items"]],
            [
                f"file-{index:03}{suffix}.srt"
                for index, suffix in enumerate([".es", ".en", ".en", ".de", ""] * 100)
            ],
        )

    def test_subtitle_filenames_follow_manual_track_and_keep_language_on_rename(self) -> None:
        """A manual choice controls the filename and a conflict rename retains its language suffix."""
        make_container(self.source, ["eng", "spa"], modern=[None, "es-419"])
        files = FileSelectionService("en")
        files.scan([str(self.source)], Event(), lambda *_: None)
        files.select_audio_track(files.snapshot()["items"][0]["id"], 2)
        self.source.with_suffix(".es.srt").write_text("existing subtitle")

        exports = ExportService()
        plan = exports.prepare(
            files.snapshot(),
            {"formats": ["srt", "vtt", "txt"], "destination": None, "includeAudioLanguage": True},
        )
        outputs = plan["items"][0]["outputs"]
        self.assertEqual(
            [Path(output["path"]).name for output in outputs],
            ["Episode.es.srt", "Episode.es.vtt", "Episode.txt"],
        )
        self.assertEqual(outputs[0]["action"], "ask")
        renamed = exports.resolve(plan, [outputs[0]["id"]], "rename")["items"][0]["outputs"]
        self.assertEqual(
            [Path(output["path"]).name for output in renamed],
            ["Episode (2).es.srt", "Episode (2).es.vtt", "Episode (2).txt"],
        )

    def test_queue_passes_frozen_stream_and_persists_preference(self) -> None:
        """Carry the selected stream through inference and preserve preferences across appearance changes."""
        make_container(self.source, ["spa", "eng"])
        engine = PhononEngine(self.root / "models")
        output: InferenceOutput = {
            "text": "English speech.",
            "duration": 1.0,
            "language": None,
            "segments": [{"id": 0, "start": 0.0, "end": 1.0, "text": "English speech."}],
        }
        with (
            patch.object(engine, "is_ready", return_value=True),
            patch.object(engine, "transcribe", return_value=output) as transcribe,
        ):
            service = TranscriptionService(engine, self.root / "settings")
            self.addCleanup(service.close)
            service.set_audio_language("en")
            service.set_appearance("dark", "es-ES")
            self.assertEqual(service.snapshot()["preferences"]["preferredAudioLanguage"], "en")
            service.import_paths([str(self.source)])
            assert service._thread is not None
            service._thread.join(2)
            plan = service.prepare_batch()
            self.assertEqual(plan["items"][0]["audioStreamIndex"], 2)
            service.start_batch(plan["id"])
            assert service._thread is not None
            service._thread.join(2)
            self.assertEqual(service.snapshot()["batch"]["completed"], 1)
            self.assertEqual(transcribe.call_args.kwargs["audio_stream_index"], 2)
            self.assertIn("English speech.", self.source.with_suffix(".srt").read_text())

    def test_policy_and_override_changes_reject_old_plans(self) -> None:
        """A reviewed plan must never be admitted after its selected stream policy changes."""
        make_container(self.source, ["spa", "eng"])
        engine = PhononEngine(self.root / "models")
        with patch.object(engine, "is_ready", return_value=True):
            service = TranscriptionService(engine, self.root / "settings")
            self.addCleanup(service.close)
            service.import_paths([str(self.source)])
            assert service._thread is not None
            service._thread.join(2)
            for choice in (None, 1):
                plan = service.prepare_batch()
                if choice is None:
                    service.set_audio_language("en")
                else:
                    service.select_audio_track(service.workspace()["items"][0]["id"], choice)
                with self.assertRaisesRegex(ValueError, "selection changed"):
                    service.start_batch(plan["id"])
