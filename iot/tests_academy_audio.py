import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.storage import FileSystemStorage
from django.test import SimpleTestCase

from iot import academy_audio as audio


class AudioCacheTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.storage = FileSystemStorage(location=self.root / "media")
        self.source = self.root / "original.mp4"
        self.source.write_bytes(b"first original")

    @staticmethod
    def fake_transcode(source, destination, executable):
        destination.write_bytes(source.read_bytes() + b" normalized")

    def test_cache_reuses_rendition_and_invalidates_for_a_changed_source_or_profile(self):
        with patch.object(audio, "normalize_file", side_effect=self.fake_transcode) as process:
            first = audio.optimize_for_storage(self.source, "ffmpeg", storage=self.storage)
            self.assertLessEqual(len(first), 100)
            self.assertEqual(audio.optimize_for_storage(self.source, None, storage=self.storage), first)
            self.assertEqual(process.call_count, 1)
            self.source.write_bytes(b"second original")
            second = audio.optimize_for_storage(self.source, "ffmpeg", storage=self.storage)
            with patch.object(audio, "PROFILE", "new-profile"):
                third = audio.optimize_for_storage(self.source, "ffmpeg", storage=self.storage)
        self.assertEqual(len({first, second, third}), 3)
        self.assertEqual(process.call_count, 3)
        self.assertTrue(all(call.args[0] == self.source for call in process.call_args_list))
        with self.storage.open(first) as previous:
            self.assertEqual(previous.read(), b"first original normalized")

    def test_exported_cache_is_reused_without_ffmpeg_and_rejects_corrupt_data(self):
        cache = self.root / "portable"
        with patch.object(audio, "normalize_file", side_effect=self.fake_transcode) as process:
            portable = audio.export_rendition(self.source, cache, "ffmpeg")
            name = audio.optimize_for_storage(self.source, None, cache, storage=self.storage)
        self.assertEqual(process.call_count, 1)
        with self.storage.open(name) as optimized:
            self.assertEqual(optimized.read(), portable.read_bytes())

        portable.write_bytes(b"damaged")
        with self.assertRaisesRegex(audio.AudioNormalizationError, "introuvable"):
            audio.optimize_for_storage(self.source, None, cache,
                                       storage=FileSystemStorage(location=self.root / "separate"))

    def test_processing_error_cleans_temporary_files_and_keeps_original(self):
        def fail(source, destination, executable):
            destination.write_bytes(b"partial output")
            raise audio.AudioNormalizationError("fixture failure")

        with patch.object(audio, "normalize_file", side_effect=fail) as process:
            with self.assertRaisesRegex(audio.AudioNormalizationError, "fixture failure"):
                audio.optimize_for_storage(self.source, "ffmpeg", storage=self.storage)
        self.assertFalse(process.call_args.args[1].parent.exists())
        self.assertFalse((self.root / "media").exists())
        self.assertEqual(self.source.read_bytes(), b"first original")


class FFmpegAudioTests(SimpleTestCase):
    def test_real_normalization_peaks_video_copy_and_double_processing_guard(self):
        executable = audio.find_ffmpeg()
        if not executable:
            self.skipTest("FFmpeg absent")
        root = Path(self.enterContext(TemporaryDirectory()))
        source = root / "quiet.mp4"
        destination = root / "normalized.mp4"
        subprocess.run(
            [executable, "-nostdin", "-v", "error", "-f", "lavfi",
             "-i", "color=s=96x64:r=12:d=4", "-f", "lavfi",
             "-i", "sine=f=440:r=48000:d=4", "-af", "volume=0.04",
             "-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(source)],
            check=True, timeout=30,
        )
        before = audio.measure(executable, source)
        after = audio.normalize_file(source, destination, executable)
        self.assertGreater(float(after["input_i"]), float(before["input_i"]) + 10)
        self.assertAlmostEqual(float(after["input_i"]), audio.LOUDNESS, delta=1)
        self.assertLessEqual(float(after["input_tp"]), audio.MAX_PEAK)

        def video_hash(path):
            return subprocess.check_output(
                [executable, "-v", "error", "-i", str(path), "-map", "0:v:0", "-c", "copy", "-f", "hash", "-"],
                timeout=30,
            )

        self.assertEqual(video_hash(source), video_hash(destination))
        with self.assertRaisesRegex(audio.AudioNormalizationError, "déjà"):
            audio.normalize_file(destination, root / "twice.mp4", executable)
        self.assertFalse((root / "twice.mp4").exists())
