import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from webui.utils.video_sources import list_video_source_files, resolve_video_source_directory


class VideoSourceDirectoryTests(unittest.TestCase):
    def test_nested_videos_and_uppercase_extensions_without_copying(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "episodes").mkdir()
            for filename in ("film.mp4", "episodes/EP01.MKV", "notes.txt"):
                (root / filename).write_bytes(b"source")
            (root / "folder.mp4").mkdir()
            before = sorted(str(path) for path in root.rglob("*"))
            videos = list_video_source_files(directory)
            self.assertEqual(set(videos), {str(root / "film.mp4"), str(root / "episodes/EP01.MKV")})
            self.assertEqual(before, sorted(str(path) for path in root.rglob("*")))
            self.assertTrue(all(Path(filename).read_bytes() == b"source" for filename in videos))

    def test_missing_directory_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"
            with self.assertRaises(NotADirectoryError):
                list_video_source_files(missing)
            self.assertFalse(missing.exists())

    def test_environment_overrides_local_configuration(self):
        with patch.dict(os.environ, {"NARRATO_VIDEO_SOURCE_DIR": "/mounted/videos"}):
            self.assertEqual(resolve_video_source_directory("/default", "/configured"), "/mounted/videos")
        with patch.dict(os.environ, {"NARRATO_VIDEO_SOURCE_DIR": ""}):
            self.assertEqual(resolve_video_source_directory("/default", "/configured"), "/configured")
            self.assertEqual(resolve_video_source_directory("/default"), "/default")


if __name__ == "__main__":
    unittest.main()
