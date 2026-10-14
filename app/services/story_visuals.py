"""Insert explanatory graphics into a finished clip timeline without changing audio."""

import json
import math
import subprocess
from pathlib import Path


def plan_visual_overlays(script, project_root):
    root = Path(project_root).resolve()
    asset_root = (root / "resource" / "visuals").resolve()
    timeline = 0.0
    result = []
    for segment in script:
        if "timeline_start_ms" in segment:
            timeline = segment["timeline_start_ms"] / 1000
        duration = float(segment.get("duration", 0))
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("图解时间线缺少有效片段时长")
        overlays = segment.get("visual_overlays") or []
        if isinstance(overlays, str):
            overlays = json.loads(overlays)
        if not isinstance(overlays, list):
            raise ValueError("visual_overlays 必须是列表或 JSON 列表字符串")
        previous_end = 0.0
        for overlay in overlays:
            start = float(overlay["start_ratio"])
            end = float(overlay["end_ratio"])
            if not 0 <= start < end <= 1 or start < previous_end:
                raise ValueError("图解比例必须在 0 到 1 之间，且不能重叠")
            image = (root / overlay["image"]).resolve()
            if not image.is_relative_to(asset_root) or not image.is_file():
                raise ValueError(f"图解文件不存在或不在 resource/visuals 中: {overlay['image']}")
            if segment.get("OST") == 1:
                raise ValueError("原声片段不能被全屏图解覆盖")
            transition = float(overlay.get("transition", .35))
            if not math.isfinite(transition) or not 0 <= transition <= 2:
                raise ValueError("图解转场时长必须在 0 到 2 秒之间")
            result.append({"image": str(image), "start": timeline + start * duration,
                           "end": timeline + end * duration,
                           "transition": min(transition, (end - start) * duration / 2),
                           "layout": overlay.get("layout", "card")})
            previous_end = end
        timeline += duration
    return result


def insert_story_visuals(video_path, script, project_root, output_path, subtitle_path=None):
    if not any(segment.get("visual_overlays") for segment in script):
        return str(video_path)
    overlays = plan_visual_overlays(script, project_root)
    if not overlays:
        return str(video_path)
    metadata = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration", "-of", "json", str(video_path),
    ], check=True, capture_output=True, text=True)
    info = json.loads(metadata.stdout)
    width, height = info["streams"][0]["width"], info["streams"][0]["height"]
    duration = float(info["format"]["duration"])
    if overlays[-1]["end"] > duration + .1:
        raise ValueError("图解时间线超过视频时长")
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_path)]
    filters = ["[0:v]setpts=PTS-STARTPTS[base]"]
    previous = "base"
    # Reuse each image input when the same graphic appears more than once.
    inputs = {}
    for overlay in overlays:
        if overlay["image"] not in inputs:
            inputs[overlay["image"]] = len(inputs) + 1
            # Graphics are static. Decode once per second; framesync reuses them
            # at the footage's frame rate instead of decoding eight PNGs per frame.
            command += ["-loop", "1", "-framerate", "1", "-i", overlay["image"]]
    for index, overlay in enumerate(overlays):
        source = inputs[overlay["image"]]
        padding = "0x00000000" if overlay["layout"] == "overlay" else "0x101725"
        transition = overlay['transition']
        fade = ""
        if transition:
            fade = (f",fade=t=in:st={overlay['start']:.6f}:d={transition:.6f}:alpha=1"
                    f",fade=t=out:st={overlay['end']-transition:.6f}:d={transition:.6f}:alpha=1")
        filters.append(
            f"[{source}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"format=rgba,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={padding},"
            f"setsar=1,fps=30{fade}[image{index}]"
        )
        filters.append(
            f"[{previous}][image{index}]overlay=0:0:shortest=1:"
            f"enable='gte(t,{overlay['start']:.6f})*lt(t,{overlay['end']:.6f})'[out{index}]"
        )
        previous = f"out{index}"
    if subtitle_path is not None:
        # Render captions after graphics in the same pass.
        def escape_filter_path(value):
            return str(value).replace("\\", "\\\\").replace(":", "\\:").replace("'", "'\\''")
        captions = escape_filter_path(subtitle_path)
        fonts = escape_filter_path(Path(project_root) / "resource/fonts")
        filters.append(f"[{previous}]ass=filename='{captions}':fontsdir='{fonts}'[captioned]")
        previous = "captioned"
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    command += ["-filter_complex_threads", "1", "-filter_complex", ";".join(filters),
                "-map", f"[{previous}]", "-map", "0:a?", "-c:v", "libx264",
                "-preset", "fast", "-crf", "18", "-threads", "2", "-pix_fmt", "yuv420p",
                "-c:a", "copy", "-t", f"{duration:.6f}", "-movflags", "+faststart", str(destination)]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"图解合成失败: {error.stderr[-2000:]}") from error
    return str(destination)
