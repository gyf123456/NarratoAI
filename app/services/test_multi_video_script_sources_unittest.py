import json
import os
import tempfile
import unittest
import shutil
import subprocess
from pathlib import Path
from unittest import mock

from app.services import clip_video
from app.services.editing_timeline import build_editing_timeline, attach_rendered_clips
from app.utils import check_script


class TestMultiVideoScriptSources(unittest.TestCase):
    def test_failed_clip_stops_composition_instead_of_shifting_timeline(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mp4"
            source.write_bytes(b"video")
            script = [
                {"_id": 1, "OST": 1, "timestamp": "00:00:00-00:00:01"},
                {"_id": 2, "OST": 1, "timestamp": "00:00:01-00:00:02"},
            ]
            def process(_source, item, output_dir, *_args):
                if item["_id"] == 2:
                    return None
                output = Path(output_dir) / "one.mp4"
                output.write_bytes(b"clip")
                return str(output)
            with (
                mock.patch.object(clip_video, "check_hardware_acceleration", return_value=None),
                mock.patch.object(clip_video.ffmpeg_utils, "probe_media_duration", return_value=5),
                mock.patch.object(clip_video, "_process_original_audio_segment", side_effect=process),
                self.assertRaisesRegex(RuntimeError, "停止合成"),
            ):
                clip_video.clip_video_unified(str(source), script, [], output_dir=directory)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_ffmpeg_consumes_shared_ranges_for_all_ost_types(self):
        with tempfile.TemporaryDirectory() as directory:
            source = str(Path(directory) / "source.mp4")
            audio = str(Path(directory) / "speech.wav")
            subprocess.run([
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=100",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                "-t", "4", "-c:v", "libx264", "-c:a", "aac", "-y", source,
            ], check=True, capture_output=True)
            subprocess.run([
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=880",
                "-t", "1.23", "-y", audio,
            ], check=True, capture_output=True)
            script = [
                {"_id": 1, "OST": 0, "timestamp": "00:00:00-00:00:03"},
                {"_id": 2, "OST": 1, "timestamp": "00:00:01.230-00:00:02.460"},
                {"_id": 3, "OST": 2, "timestamp": "00:00:02.000-00:00:04"},
            ]
            tts = [{"_id": i, "duration": 1.23, "audio_file": audio} for i in (1, 3)]
            plan = build_editing_timeline(script, tts, source,
                                         media_duration=clip_video.ffmpeg_utils.probe_media_duration)
            with mock.patch.object(clip_video, "check_hardware_acceleration", return_value=None):
                clips = clip_video.clip_video_unified(
                    source, script, tts, output_dir=str(Path(directory) / "clips"), timeline=plan,
                )
            output = attach_rendered_clips(plan, clips)
            self.assertEqual(3690, output[-1]["timeline_end_ms"])
            for item in output:
                actual = clip_video.ffmpeg_utils.probe_media_duration(item["video"])
                # Encoded media is quantized to frame/sample boundaries.
                self.assertLess(abs(actual - item["duration"]), 0.05)
                probe = subprocess.run([
                    "ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                    "-of", "csv=p=0", item["video"],
                ], check=True, capture_output=True, text=True)
                self.assertEqual(item["OST"] != 0, "audio" in probe.stdout)

    def test_clip_command_uses_input_fast_seek(self):
        encoder_config = clip_video.get_safe_encoder_config(None)

        cmd = clip_video._build_ffmpeg_command_with_audio_control(
            input_path="/tmp/input.mp4",
            output_path="/tmp/output.mp4",
            start_time="00:27:32.240",
            end_time="00:27:38.240",
            encoder_config=encoder_config,
            hwaccel_args=[],
            remove_audio=False,
        )

        self.assertLess(cmd.index("-ss"), cmd.index("-i"))
        self.assertEqual("6", cmd[cmd.index("-t") + 1])
        self.assertNotIn("-to", cmd)

    def test_check_format_accepts_optional_video_source_fields(self):
        script = [
            {
                "_id": 1,
                "video_id": 2,
                "video_name": "2.mp4",
                "timestamp": "00:00:00,000-00:00:03,000",
                "picture": "画面",
                "narration": "解说",
                "OST": 0,
            }
        ]

        result = check_script.check_format(json.dumps(script, ensure_ascii=False))

        self.assertTrue(result["success"])

    def test_clip_video_unified_resolves_source_by_video_id_and_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video_1 = os.path.join(temp_dir, "1.mp4")
            video_2 = os.path.join(temp_dir, "2.mp4")
            for video_path in [video_1, video_2]:
                with open(video_path, "wb") as file:
                    file.write(b"video")

            output_dir = os.path.join(temp_dir, "clips")
            used_sources = []

            def fake_process(source_video_path, script_item, output_dir_arg, *_args):
                used_sources.append(source_video_path)
                output_path = os.path.join(output_dir_arg, f"{script_item['_id']}.mp4")
                with open(output_path, "wb") as file:
                    file.write(b"clip")
                return output_path

            script_list = [
                {
                    "_id": 1,
                    "video_id": 2,
                    "timestamp": "00:00:00,000-00:00:03,000",
                    "picture": "视频2画面",
                    "narration": "播放原片1",
                    "OST": 1,
                },
                {
                    "_id": 2,
                    "video_name": "1.mp4",
                    "timestamp": "00:00:03,000-00:00:06,000",
                    "picture": "视频1画面",
                    "narration": "播放原片2",
                    "OST": 1,
                },
            ]

            with (
                mock.patch.object(clip_video, "check_hardware_acceleration", return_value=None),
                mock.patch.object(clip_video.ffmpeg_utils, "probe_media_duration", return_value=10),
                mock.patch.object(clip_video, "_process_original_audio_segment", side_effect=fake_process),
            ):
                result = clip_video.clip_video_unified(
                    video_origin_path=video_1,
                    video_origin_paths=[video_1, video_2],
                    script_list=script_list,
                    tts_results=[],
                    output_dir=output_dir,
                    task_id="multi-video-test",
                )

            self.assertEqual([video_2, video_1], used_sources)
            self.assertEqual({1, 2}, set(result.keys()))


if __name__ == "__main__":
    unittest.main()
