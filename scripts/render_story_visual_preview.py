"""Reuse an existing successful task's narration and footage to preview story cards."""

import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.story_visuals import insert_story_visuals


def seconds(value):
    hours, minutes, secs = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(secs)


def ass_time(value):
    centiseconds = round(seconds(value) * 100)
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--script", default="resource/scripts/2026-1013-visual-story.json")
    parser.add_argument("--output", default="storage/story_visuals/2026-1013-visual-story.mp4")
    parser.add_argument("--reuse-visuals", action="store_true", help="Reuse an existing illustrated video for subtitle-only repairs")
    args = parser.parse_args()
    task = ROOT / "storage/tasks" / args.task
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    script = json.loads((ROOT / args.script).read_text())
    for row in script:
        source_start, source_end = map(seconds, row["timestamp"].split("-"))
        row["duration"] = source_end - source_start
        audio = task / ("audio_" + row["timestamp"].replace(":", "_") + ".wav")
        if row["OST"] == 0:
            with wave.open(str(audio)) as handle:
                row["duration"] = round(handle.getnframes() / handle.getframerate(), 2)
    base = output.parent / "footage_with_existing_audio.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(task / "merger.mp4"),
                    "-i", str(task / "combined.mp4"), "-map", "0:v:0", "-map", "1:a:0",
                    "-c", "copy", "-shortest", str(base)], check=True)
    illustrated = str(output.parent / "illustrated_without_subtitles.mp4")
    # Reburn the existing task's exact subtitle cues after graphics are inserted.
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Source Han Sans SC,38,&H00F4EEE2,&H00FFFFFF,&H00101725,&H80101725,0,0,0,0,100,100,0,0,1,2,0,2,72,72,120,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for cue in (task / "script_subtitles.srt").read_text().strip().split("\n\n"):
        lines = cue.splitlines()
        if len(lines) < 3 or " --> " not in lines[1]:
            continue
        start, end = lines[1].split(" --> ")
        text = "\\N".join(lines[2:]).replace("{", "（").replace("}", "）")
        events.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{text}")
    captions = output.parent / "story_captions.ass"
    captions.write_text(header + "\n".join(events) + "\n")
    print("Rendering graphics and subtitles", flush=True)
    if args.reuse_visuals and Path(illustrated).is_file():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", illustrated,
                        "-vf", f"ass={captions}:fontsdir={ROOT / 'resource/fonts'}",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-threads", "2",
                        "-c:a", "copy", "-movflags", "+faststart", str(output)], check=True)
    else:
        insert_story_visuals(base, script, ROOT, output, subtitle_path=captions)
    print(output, flush=True)


if __name__ == "__main__":
    main()
