import copy
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.services.editing_timeline import (
    attach_rendered_clips,
    build_editing_timeline,
    seconds_to_milliseconds,
)
from app.services import subtitle_merger, update_script


def segment(item_id, ost=1, timestamp="00:00:01-00:00:03", **extra):
    return dict(_id=item_id, OST=ost, timestamp=timestamp, **extra)


def speech(item_id, duration, **extra):
    return dict(_id=item_id, duration=duration, audio_file="speech.wav", **extra)


class EditingTimelineTests(unittest.TestCase):
    def plan(self, script, tts=(), **options):
        return build_editing_timeline(script, tts, "one.mp4", ["one.mp4", "two.mp4"], **options)

    def test_ost_rules_preserve_milliseconds_and_source_offsets(self):
        script = [segment(0, 0), segment(1, 1, "00:00:05.001-00:00:06.234"),
                  segment(2, 2, "00:00:10-00:00:12", video_id=2)]
        plan = self.plan(script, [speech(0, 1.001), speech(2, 2.003)])
        self.assertEqual([1.001, 1.233, 2.003], [s["duration"] for s in plan])
        self.assertEqual([0, 1001, 2234], [s["timeline_start_ms"] for s in plan])
        self.assertEqual(4237, plan[-1]["timeline_end_ms"])
        self.assertEqual("00:00:01,000-00:00:02,001", plan[0]["sourceTimeRange"])
        self.assertEqual("00:00:02,234-00:00:04,237", plan[2]["editedTimeRange"])
        self.assertEqual("two.mp4", plan[2]["video"])
        self.assertEqual("", plan[1]["audio"])

    def test_duplicate_timestamps_use_ids_not_last_matching_result(self):
        plan = self.plan([segment(1, 0), segment(2, 2)],
                         [speech(2, 2.5), speech(1, 1.5)])
        self.assertEqual([1.5, 2.5], [s["duration"] for s in plan])

    def test_unambiguous_legacy_tts_timestamp_fallback(self):
        plan = self.plan([segment(1, 0)],
                         [dict(duration=1.234, audio_file="a.wav", timestamp="00:00:01-00:00:03")])
        self.assertEqual(1.234, plan[0]["duration"])

    def test_ambiguous_tts_fallback_is_rejected(self):
        results = [speech(8, 1, timestamp="00:00:01-00:00:03"),
                   speech(9, 2, timestamp="00:00:01-00:00:03")]
        with self.assertRaisesRegex(ValueError, "匹配不唯一"):
            self.plan([segment(1, 0)], results)

    def test_video_name_takes_precedence_over_video_id(self):
        plan = self.plan([segment(1, video_id=1, video_name="two.mp4")])
        self.assertEqual("two.mp4", plan[0]["video"])

    def test_existing_explicit_source_takes_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "explicit.mp4"
            source.touch()
            plan = self.plan([segment(1, video_id=2, source_video_path=str(source))])
        self.assertEqual(str(source), plan[0]["video"])

    def test_source_and_audio_limits_are_applied_before_later_offsets(self):
        calls = []
        durations = {"one.mp4": 3.004, "two.mp4": 8, "speech.wav": 1.002}
        def read(path):
            calls.append(path)
            return durations[path]
        plan = self.plan([segment(1, 2, "00:00:02.001-00:00:05"),
                          segment(2, 0, video_id=2), segment(3, 1)],
                         [speech(1, 3), speech(2, 4)], media_duration=read)
        self.assertEqual([1.002, 1.002, 2], [s["duration"] for s in plan])
        self.assertEqual([0, 1002, 2004], [s["timeline_start_ms"] for s in plan])
        self.assertEqual(1, calls.count("one.mp4"))
        self.assertEqual(1, calls.count("speech.wav"))

    def test_missing_tts_does_not_silently_drop_segment(self):
        with self.assertRaisesRegex(ValueError, "片段 2.*缺失配音"):
            self.plan([segment(1), segment(2, 0)])

    def test_invalid_durations_and_ranges_are_rejected(self):
        for duration in (0, -1, float("nan"), float("inf"), "bad", None):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                self.plan([segment(1, 0)], [speech(1, duration)])
        for timestamp in ("bad", "00:00:03-00:00:01", "00:00:60-00:01:02"):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                self.plan([segment(1, timestamp=timestamp)])

    def test_duplicate_ids_and_unknown_ost_are_rejected(self):
        for script in ([segment(1), segment(1)], [segment(None)], [segment(1, 9)]):
            with self.subTest(script=script), self.assertRaises(ValueError):
                self.plan(script)
        with self.assertRaisesRegex(ValueError, "重复的配音"):
            self.plan([segment(1, 0)], [speech(1, 1), speech(1, 2)])

    def test_source_exhausted_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "没有可用时长"):
            self.plan([segment(1)], media_duration=lambda _: 0.5)

    def test_long_timeline_accumulates_integer_milliseconds(self):
        script = [segment(i, timestamp="00:00:00.000-00:00:00.001") for i in range(1000)]
        plan = self.plan(script)
        self.assertEqual(1000, plan[-1]["timeline_end_ms"])
        self.assertEqual("00:00:00,999-00:00:01,000", plan[-1]["editedTimeRange"])
        self.assertEqual(1001, seconds_to_milliseconds(1.001))

    def test_rendered_paths_do_not_change_timeline_or_mutate_inputs(self):
        script = [segment(1, 0), segment(2)]
        original = copy.deepcopy(script)
        plan = self.plan(script, [speech(1, 1.001)])
        rendered = attach_rendered_clips(plan, {1: "random-name.mp4", 2: "also-random.mp4"})
        self.assertEqual(original, script)
        self.assertEqual("one.mp4", plan[0]["video"])
        for before, after in zip(plan, rendered):
            for field in ("duration", "sourceTimeRange", "editedTimeRange", "timeline_start_ms"):
                self.assertEqual(before[field], after[field])
            self.assertFalse(after["use_source_timerange"])

    def test_missing_clip_stops_output(self):
        with self.assertRaisesRegex(ValueError, "缺少裁剪结果"):
            attach_rendered_clips(self.plan([segment(1), segment(2)]), {1: "one.mp4"})

    def test_legacy_timestamp_update_keeps_millisecond_precision(self):
        result = update_script.update_script_timestamps(
            [segment(1), segment(2)],
            {1: "vid_00-00-01-000@00-00-02-001.mp4",
             2: "vid_00-00-03-000@00-00-04-002.mp4"},
        )
        self.assertEqual(1.001, result[0]["duration"])
        self.assertEqual("00:00:01,001-00:00:02,003", result[1]["editedTimeRange"])

    def test_subtitle_fallback_offsets_follow_shared_timeline(self):
        with tempfile.TemporaryDirectory() as directory:
            subtitle = Path(directory) / "speech.srt"
            subtitle.write_text("1\n00:00:00,000 --> 00:00:00,500\n测试\n", encoding="utf-8")
            plan = self.plan([segment(1, timestamp="00:00:00-00:00:01.001"), segment(2, 0)],
                             [speech(2, 1, subtitle_file=str(subtitle))])
            output = str(Path(directory) / "merged.srt")
            subtitle_merger.merge_subtitle_files(plan, output)
            self.assertIn("00:00:01,001 --> 00:00:01,501", Path(output).read_text())


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class TimelineMediaSmokeTests(unittest.TestCase):
    def test_planned_ranges_render_at_expected_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            source = str(Path(directory) / "source.mp4")
            def run(args):
                return subprocess.run(args, check=True, capture_output=True, text=True)
            run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                 "testsrc2=size=160x90:rate=100", "-t", "3", "-c:v", "libx264", "-y", source])
            def duration(path):
                return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                  "-of", "csv=p=0", path]).stdout.strip())
            plan = build_editing_timeline(
                [segment(1, timestamp="00:00:00.200-00:00:01.210"),
                 segment(2, timestamp="00:00:02.500-00:00:04")], [], source,
                media_duration=duration,
            )
            clips = {}
            for item in plan:
                output = str(Path(directory) / f"clip-{item['_id']}.mp4")
                run(["ffmpeg", "-v", "error", "-ss", str(item["source_start_time"]),
                     "-i", source, "-t", str(item["duration"]), "-c:v", "libx264", "-y", output])
                self.assertAlmostEqual(item["duration"], duration(output), places=2)
                clips[item["_id"]] = output
            rendered = attach_rendered_clips(plan, clips)
            self.assertEqual(1510, rendered[-1]["timeline_end_ms"])


if __name__ == "__main__":
    unittest.main()
