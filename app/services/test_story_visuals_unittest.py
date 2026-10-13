import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.services.story_visuals import insert_story_visuals, plan_visual_overlays


class StoryVisualsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        target = self.root / "resource/visuals/card.png"
        target.parent.mkdir(parents=True)
        asset = Path(__file__).resolve().parents[2] / "resource/visuals/got_s01e01/map_01.png"
        shutil.copyfile(asset, target)
        self.overlay = {"image": "resource/visuals/card.png", "start_ratio": .2, "end_ratio": .8}

    def test_timing_uses_actual_aligned_duration(self):
        plan = plan_visual_overlays([
            {"duration": 4, "OST": 0},
            {"duration": 10, "OST": 0, "visual_overlays": json.dumps([self.overlay])},
        ], self.root)
        self.assertEqual((plan[0]["start"], plan[0]["end"]), (6, 12))

    def test_path_escape_and_overlap_rejected(self):
        with self.assertRaises(ValueError):
            plan_visual_overlays([{"duration": 4, "visual_overlays": [dict(self.overlay, image="../../outside.png")]}], self.root)
        with self.assertRaises(ValueError):
            plan_visual_overlays([{"duration": 4, "visual_overlays": [self.overlay, self.overlay]}], self.root)

    def test_original_dialogue_cannot_be_covered(self):
        with self.assertRaises(ValueError):
            plan_visual_overlays([{"duration": 4, "OST": 1, "visual_overlays": [self.overlay]}], self.root)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_transparent_graphic_keeps_footage_visible_and_fades_in(self):
        asset = Path(__file__).resolve().parents[2] / "resource/visuals/got_s01e01_natural/trust.png"
        shutil.copyfile(asset, self.root / "resource/visuals/card.png")
        source, output = self.root / "blue.mp4", self.root / "overlay.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "color=blue:s=320x568:r=30:d=2", "-c:v", "libx264", str(source)], check=True)
        insert_story_visuals(source, [{"duration": 2, "visual_overlays": [
            dict(self.overlay, layout="overlay", transition=.5)
        ]}], self.root, output)
        def pixel(time, x, y):
            frame = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", str(time), "-i", str(output),
                "-frames:v", "1", "-vf", f"crop=2:2:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
            return frame[2]
        self.assertGreater(pixel(1, 160, 284), 230)  # Film remains visible behind transparent pixels.
        self.assertGreater(pixel(.43, 160, 80), pixel(1, 160, 80) + 50)  # Entry is gradual.
        self.assertGreater(pixel(1.8, 160, 80), 230)  # Graphic has left the frame.

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_video_render_preserves_timeline_audio_and_returns_to_footage(self):
        source, output = self.root / "source.mp4", self.root / "result.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=blue:s=320x568:r=30:d=3",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:v", "libx264", "-c:a", "aac",
                        "-pix_fmt", "yuv420p", "-shortest", str(source)], check=True)
        insert_story_visuals(source, [
            {"duration": 1.5, "visual_overlays": [self.overlay]},
            {"duration": 1.5, "visual_overlays": [self.overlay]},
        ], self.root, output)
        def metadata(file):
            return json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                "format=duration:stream=width,height,codec_type", "-of", "json", str(file)]))
        self.assertAlmostEqual(float(metadata(source)["format"]["duration"]), float(metadata(output)["format"]["duration"]), delta=.08)
        self.assertEqual(metadata(source)["streams"], metadata(output)["streams"])
        def audio_hash(file):
            return subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(file), "-map", "0:a", "-c", "copy", "-f", "hash", "-"])
        self.assertEqual(audio_hash(source), audio_hash(output))
        def blue_channel(time):
            frame = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", str(time), "-i", str(output),
                "-frames:v", "1", "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
            return frame[2]
        self.assertGreater(blue_channel(.1), 200)
        self.assertLess(blue_channel(.7), 150)
        self.assertGreater(blue_channel(1.4), 200)


if __name__ == "__main__":
    unittest.main()
